#!/usr/bin/env python3
"""atlas — the estate-side BANK: derive each part's status from exit codes, stamp the
commit, write an immutable snapshot, build the board, push it through an adapter.

WHAT THIS CLOSES. Every estate already knows things about itself that nobody can read:
which gates are armed, which fixtures pass, which part of the map is claimed done. That
knowledge lives in a session's head and dies with it, and the map a human keeps by hand
starts lying the week after it is written. Atlas does not ask anyone to remember: a
tracked git hook fires this script at every commit, it RUNS the tests the map binds, and
it derives the map from the exit codes. Nothing on the map is typed in by hand.

THE STATUS LAW (the whole point — `references/status-law.md` is the long form):

  · A part is **done** only when a test THAT COULD FAIL passed.
  · A done with **no test** is demoted to wip and REPORTED — never quietly green.
  · A done whose test **fails** becomes **wip + failing**.
  · **status and evidence are separate fields**, so the map says "claims done, evidence
    none" out loud instead of hiding it behind a check mark. Evidence may only DEMOTE a
    claim, never promote one: a passing test does not turn wip into done, because the
    claim is the author's and the evidence is the machine's.
  · RED is narrower than failing, on purpose: the board is RED when a part CLAIMED done
    has a failing test — a regression against a standing claim. A wip whose test is red
    is ordinary work (that is what red-first looks like) and is reported, not alarmed.

FALSIFIABILITY, HONESTLY BOUNDED. `_can_fail()` is a STATIC, CONSERVATIVE reading of the
command: `true`, `:`, `exit 0`, a bare `echo`, or anything trailing `|| true` cannot fail
and is therefore not a test. It cannot prove an arbitrary command CAN fail — no static
check can. Two things do that work instead, and both are recorded: `proven_red` per part
(this estate has banked a snapshot where that very test failed) and the estate-level
born-red proof (`wire --prove`).

VERBS AND EXIT CODES — the contract other lanes call:

  atlas.py key --mint --label <who> [--keyring P]   print the key ONCE; append its hash
  atlas.py key --check [--key K] [--quiet]          0 = a valid key · 7 = none/invalid
     on 0 (only) stdout is exactly: notrest-access: ok ring=<12hex> path=<ring>
     — require that line verbatim; an exit code alone proves no interpreter read this file
     (the key file, and every private-store path, resolve under ${NOTREST_HOME:-~/.notrest}
      — the same store the hooks read, because two answers to one gate question is worse
      than a closed gate)
  atlas.py key --revoke <label>                     0 = removed · 7 = no such label
  atlas.py key --list                               labels + dates (never a key)
  atlas.py bank [--root .] [--adapter file|http|none] [--hub D] [--no-board] [--dry-run]
  atlas.py wire [--root .] [--prove] [--unwire] [--force]
  atlas.py status [--root .] [--json]

  0  ok / green
  2  usage, or a declared input that could not be read
  3  nothing to derive: not a git repo, no HEAD, or no map and no gates (an estate with
     no contract is never certified green — that is gate-check.py's exit 3, same law)
  4  banked locally, but the PUSH failed (the local truth stands; the hub does not have it)
  5  RED or REFUSED: bank = a claimed-done part is failing · wire = a foreign post-commit
     hook is in the way · key --mint = that label is already in the keyring
  6  status = HEAD is NOT banked (the commit that never banked — the born-red signal) ·
     wire --prove = the proof did not go red, so the detector cannot detect
  7  no valid access key (`key --check`, and `wire --prove` which needs the hook to bank)

WHAT IT NEVER DOES. It never commits, never stages, never pushes git, never edits a file
the estate authored. It observes and records. The http adapter NEVER SENDS — this file
imports no network module at all, and eval's NETWORK-EGRESS check re-proves that on every
run rather than taking this sentence's word for it.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

VERSION = "1.0.0"
SCHEMA = "notrest.atlas/1"
BOARD_SCHEMA = "notrest.atlas.board/1"
CONFIG_SCHEMA = "notrest.atlas.config/1"

HERE = os.path.dirname(os.path.abspath(__file__))
# scripts/ -> atlas/ -> skills/ -> plugins/notrest. NOTREST_PLUGIN_ROOT overrides it, and
# exists for exactly one reason: a COPY of this script under test (the fixture's mutation
# arms) must still find the real gate-check.py and hook body, or every mutation would look
# like it broke the gates when it only moved the file.
PLUGIN_ROOT = os.path.abspath(os.environ.get("NOTREST_PLUGIN_ROOT")
                              or os.path.join(HERE, "..", "..", ".."))
GATE_CHECK = os.path.join(PLUGIN_ROOT, "hooks", "gate-check.py")
BANK_HOOK = os.path.join(PLUGIN_ROOT, "hooks", "atlas-bank-hook.sh")
DEFAULT_KEYRING = os.path.join(PLUGIN_ROOT, ".access", "keys.sha256")

# The shim git actually runs. The MARK is how `wire` tells its own hook from somebody
# else's — a hook we did not write is never overwritten without --force.
HOOK_MARK = "notrest-atlas-hook"
CAP = 1024 * 1024                      # per-test output kept in memory (gate-check's cap)
CLAIMS = ("done", "wip", "planned", "blocked")
STATUS_ORDER = {"done": 0, "wip": 1, "blocked": 2, "planned": 3}

KEY_PREFIX = "nrk_"
KEY_LINE_RE = re.compile(r"^([0-9a-f]{64}):([A-Za-z0-9._-]{1,64}):(\d{4}-\d{2}-\d{2})\s*$")
LABEL_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
KEYRING_HEADER = (
    "# notrest access keyring — one line per key: sha256(key):label:YYYY-MM-DD\n"
    "# The key itself is NEVER stored, only its hash. Mint with\n"
    "#   atlas.py key --mint --label <who>\n"
    "# and revoke by deleting the line (atlas.py key --revoke <label>).\n"
)

# The map grammar, deliberately the same shape as gates/ACTIVE.md's GATE:/CHECK: — one
# directive per line, and directives inside a fenced block are DOCUMENTATION and are
# never run. A map that SHOWS you how to declare a part must not thereby declare one.
PART_RE = re.compile(r"^\s{0,3}(?:[-*]\s+)?PART:\s*(.+?)\s*$")
TEST_RE = re.compile(r"^\s{0,3}(?:[-*]\s+)?TEST:\s*(.+?)\s*$")
CLAIM_RE = re.compile(r"^\s{0,3}(?:[-*]\s+)?CLAIM:\s*([A-Za-z]+)\s*$")
PATH_RE = re.compile(r"^\s{0,3}(?:[-*]\s+)?PATH:\s*(.+?)\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```+|~~~+)")
ID_SPLIT_RE = re.compile(r"\s+[—–-]\s+")

# STATIC falsifiability. Conservative by construction: it says "this cannot fail", never
# "this can". Everything it lets through is still only a candidate until a real red is
# observed (proven_red) or the born-red proof runs.
CANNOT_FAIL = (
    re.compile(r"^(true|:|/bin/true|/usr/bin/true|exit\s+0)$"),
    re.compile(r"\|\|\s*(true|:)\s*$"),
    re.compile(r";\s*(true|:|exit\s+0)\s*$"),
    re.compile(r"^echo\b[^|;&]*$"),
)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def sha(b):
    if isinstance(b, str):
        b = b.encode("utf-8", "replace")
    return hashlib.sha256(b).hexdigest()


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def write_atomic(path, text, mode=0o644):
    """Prepare in full, land by rename. A reader never sees a half-written map."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".atlas-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def git(root, *args, **kw):
    """(rc, stdout). Never raises; a missing git is rc 127, like a shell would say."""
    try:
        p = subprocess.run(["git"] + list(args), cwd=root, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=kw.get("timeout", 30))
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def estate_name(root):
    return re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(os.path.abspath(root))) or "estate"


def rel(root, path):
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


# ---------------------------------------------------------------------------
# the keyring — mint / check / revoke / list
# ---------------------------------------------------------------------------
def keyring_path(args):
    return os.path.abspath(getattr(args, "keyring", None)
                           or os.environ.get("NOTREST_KEYRING")
                           or DEFAULT_KEYRING)


# THE SENTINEL (refuter round, 4.8). `key --check` exiting 0 is not proof that ATLAS
# answered: a `python3` on PATH that exits 0 for every argument — a stub, a wrapper, an
# interpreter that never parsed this file — exits 0 too, and a hook that trusts the code
# alone reads that as "licensed". So a positive answer must CARRY something only this
# script can produce: the digest of the keyring bytes it actually read, and the path it
# read them from. A hook requires the line verbatim; nothing else on stdout, ever.
SENTINEL = "notrest-access: ok ring=%s path=%s"


def ring_digest(path):
    """First 12 hex of sha256 over the keyring's BYTES — the ring, fingerprinted."""
    try:
        with open(path, "rb") as fh:
            return sha(fh.read())[:12]
    except OSError:
        return "000000000000"


def keyring_guard(path):
    """→ a refusal reason, or "". A keyring reached through a SYMLINK is a keyring
    somebody else can re-point without touching this repo, and a directory or device at
    that path is not a keyring at all. `--keyring` / NOTREST_KEYRING still choose WHICH
    ring (the fixtures need that); they do not get to choose a ring that is not a file."""
    if os.path.islink(path):
        return "%s is a symlink — a keyring must be a regular file (a re-pointable ring " \
               "is a re-pointable gate)" % path
    if os.path.exists(path) and not os.path.isfile(path):
        return "%s is not a regular file" % path
    return ""


def keyring_read(path):
    """→ [(hash, label, date, raw_line)] — malformed lines are IGNORED, never guessed at.
    A keyring is an allowlist: a line nobody can parse admits nobody."""
    txt = read(path) or ""
    out = []
    for line in txt.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = KEY_LINE_RE.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2), m.group(3), line))
    return out


def notrest_home():
    """The private store, `${NOTREST_HOME:-~/.notrest}` — ONE resolution, shared with the
    hooks and the auto-build marker. Parity arm (lane H, 4.8): resolving the key file at a
    hardcoded ~/.notrest while the hooks honour NOTREST_HOME gives a machine that sets it
    "the hook says licensed, atlas.py says no" — two answers to one question, which is the
    one thing an access gate may never have."""
    return os.path.expanduser(os.environ.get("NOTREST_HOME") or "~/.notrest")


def resolve_key(args):
    """(key, where) — flag, then env, then the machine's key file. Never a default."""
    if getattr(args, "key", None):
        return args.key.strip(), "--key"
    env = os.environ.get("NOTREST_ACCESS_KEY", "").strip()
    if env:
        return env, "NOTREST_ACCESS_KEY"
    p = os.path.expanduser(os.environ.get("NOTREST_ACCESS_KEY_FILE")
                           or os.path.join(notrest_home(), "access-key"))
    txt = read(p)
    if txt:
        for line in txt.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line, p
    return "", ""


def cmd_key(args):
    path = keyring_path(args)
    picked = [bool(args.mint), bool(args.check), bool(args.revoke), bool(args.list)]
    if sum(1 for x in picked if x) != 1:
        sys.stderr.write("atlas key: choose exactly one of --mint / --check / --revoke / --list\n")
        return 2
    bad = keyring_guard(path)
    if bad:
        if not args.quiet:
            sys.stderr.write("atlas key: REFUSED — %s\n" % bad)
        return 7
    rows = keyring_read(path)

    if args.list:
        if not rows:
            print("atlas keyring: %s — empty (no keys minted)" % path)
            return 0
        print("atlas keyring: %s" % path)
        for h, label, date, _ in rows:
            print("  %-24s minted %s  sha256 %s…" % (label, date, h[:12]))
        return 0

    if args.mint:
        if not args.label or not LABEL_RE.match(args.label):
            sys.stderr.write("atlas key --mint: --label must match [A-Za-z0-9._-]{1,64} "
                             "(a ':' would break the line format)\n")
            return 2
        if any(label == args.label for _h, label, _d, _l in rows):
            sys.stderr.write("atlas key --mint: REFUSED — label %r is already in %s. "
                             "Revoke it first: atlas.py key --revoke %s\n"
                             % (args.label, path, args.label))
            return 5
        key = KEY_PREFIX + secrets.token_urlsafe(32)
        line = "%s:%s:%s\n" % (sha(key), args.label, today())
        base = read(path)
        if base is None:
            base = KEYRING_HEADER
        elif base and not base.endswith("\n"):
            base += "\n"
        write_atomic(path, base + line)
        print("atlas: minted an access key for %r" % args.label)
        print("")
        print("  %s" % key)
        print("")
        print("THIS IS THE ONLY TIME IT IS PRINTED — the keyring stores the hash, never the")
        print("key. Give it to the holder; they put it in ~/.notrest/access-key (or the")
        print("NOTREST_ACCESS_KEY env var). Keyring line appended to %s" % path)
        return 0

    if args.revoke:
        if not LABEL_RE.match(args.revoke):
            sys.stderr.write("atlas key --revoke: %r is not a label\n" % args.revoke)
            return 2
        keep, dropped = [], 0
        for line in (read(path) or "").splitlines():
            m = KEY_LINE_RE.match(line.strip())
            if m and m.group(2) == args.revoke:
                dropped += 1
                continue
            keep.append(line)
        if not dropped:
            sys.stderr.write("atlas key --revoke: no key labelled %r in %s\n"
                             % (args.revoke, path))
            return 7
        write_atomic(path, "\n".join(keep).rstrip("\n") + "\n")
        print("atlas: revoked %d key line(s) labelled %r — %s"
              % (dropped, args.revoke, path))
        return 0

    # --check: the gate every hook calls. Quiet by contract; the exit code is the answer.
    key, where = resolve_key(args)
    if not key:
        if not args.quiet:
            sys.stderr.write("atlas key --check: no access key on this machine "
                             "(looked at --key, NOTREST_ACCESS_KEY, ~/.notrest/access-key)\n")
        return 7
    h = sha(key)
    for kh, label, date, _ in rows:
        if kh == h:
            # stdout is the MACHINE channel and carries the sentinel alone — `--quiet`
            # keeps it, because it is not chatter, it is the proof. Everything a human
            # wants goes to stderr, where no hook is parsing.
            print(SENTINEL % (ring_digest(path), path))
            if not args.quiet:
                sys.stderr.write("atlas key: valid — label %s, minted %s (from %s)\n"
                                 % (label, date, where))
            return 0
    if not args.quiet:
        sys.stderr.write("atlas key --check: the key from %s is not in %s\n" % (where, path))
    return 7


def key_ok(args_keyring=None):
    """The same gate, callable in-process (wire --prove needs it before it starts)."""
    class _A(object):
        key = None
        keyring = args_keyring
        quiet = True
        mint = check = list = None
        revoke = None
    a = _A()
    a.check = True
    return cmd_key(a) == 0


# ---------------------------------------------------------------------------
# the map — parts, tests, and the status law
# ---------------------------------------------------------------------------
def parse_map(text):
    """→ (parts, problem). Same fence law as gate-check.py: an unterminated fence is not
    documentation, it is a file we failed to read, and it is reported rather than
    silently swallowing every part below it."""
    parts, fence, fence_line, swallowed = [], "", 0, 0
    for n, raw in enumerate(text.splitlines(), 1):
        f = FENCE_RE.match(raw)
        if f:
            tok = f.group(1)
            if not fence:
                fence, fence_line = tok[0] * 3, n
            elif tok.startswith(fence):
                fence, fence_line = "", 0
            continue
        if fence:
            if PART_RE.match(raw) or TEST_RE.match(raw) or CLAIM_RE.match(raw):
                swallowed += 1
            continue
        m = PART_RE.match(raw)
        if m:
            head = m.group(1)
            bits = ID_SPLIT_RE.split(head, 1)
            pid = bits[0].strip()
            title = bits[1].strip() if len(bits) > 1 else pid
            parts.append({"id": pid, "title": title, "claim": "wip", "test": "",
                          "paths": [], "line": n, "source": "map"})
            continue
        if not parts:
            continue
        m = TEST_RE.match(raw)
        if m:
            parts[-1]["test"] = m.group(1)
            continue
        m = CLAIM_RE.match(raw)
        if m:
            c = m.group(1).lower()
            parts[-1]["claim"] = c if c in CLAIMS else "wip"
            continue
        m = PATH_RE.match(raw)
        if m:
            parts[-1]["paths"].append(m.group(1))
    problem = ""
    if fence:
        problem = ("unterminated code fence opened on line %d — it swallowed %d "
                   "PART/TEST/CLAIM directive(s), so the map was not read as written"
                   % (fence_line, swallowed))
    return parts, problem


def can_fail(cmd):
    c = " ".join((cmd or "").split())
    if not c:
        return False
    for rx in CANNOT_FAIL:
        if rx.search(c):
            return False
    return True


def run_test(cmd, cwd, timeout):
    """(exit, outsha, bytes) — output to a FILE, only a capped window read back, exactly
    like gate-check.py. A test emitting 20 MB inside a commit hook is a cost nobody
    signed up for, and a sha over a silently clipped window is stated as such."""
    try:
        with tempfile.TemporaryFile() as fh:
            try:
                p = subprocess.run([shutil.which("bash") or "/bin/bash", "-c", cmd],
                                   cwd=cwd, stdout=fh, stderr=subprocess.STDOUT,
                                   timeout=timeout)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = 124
            fh.flush()
            total = fh.tell()
            fh.seek(0)
            out = fh.read(CAP).decode("utf-8", "replace")
        return rc, sha(out), total
    except Exception as exc:                                   # unrunnable command
        return 127, sha("atlas: could not run: %s" % exc), 0


def derive(claim, has_test, falsifiable, rc):
    """THE STATUS LAW, in one function so there is exactly one place it can be wrong.
    → (status, evidence, demoted, failing)."""
    if not has_test:
        return ("wip" if claim == "done" else claim, "none", claim == "done", False)
    if not falsifiable:
        # A command that cannot fail is not a test; a done resting on it is a done
        # resting on nothing, and is demoted exactly like a done with no test at all.
        return ("wip" if claim == "done" else claim, "unfalsifiable", claim == "done", False)
    if rc == 0:
        # Evidence may only DEMOTE. A passing test does not promote wip to done: the
        # claim belongs to the author, the evidence belongs to the machine.
        return (claim, "passed", False, False)
    return ("wip" if claim == "done" else claim, "failed", False, True)


def history_reds(root):
    """Part ids this estate has ALREADY banked a red for — the earned half of
    falsifiability. Newest 50 snapshots; a corrupt one is skipped, not fatal."""
    seen = set()
    snaps = sorted(glob.glob(os.path.join(root, "atlas", "snapshots", "*.json")),
                   key=lambda p: os.path.getmtime(p), reverse=True)[:50]
    for p in snaps:
        try:
            blob = json.loads(read(p) or "{}")
        except ValueError:
            continue
        for part in blob.get("parts") or []:
            if part.get("evidence") == "failed":
                seen.add(part.get("id"))
    return seen


def slug(text, n=40):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:n] or "gate")


def gate_parts(root, gates_file, timeout, budget):
    """Every gate in gates/ACTIVE.md becomes a part CLAIMED done — a standing completion
    contract is precisely a claim that it holds. The verdicts come from gate-check.py
    itself: the kernel instrument that already owns the CHECK/EXPECT grammar is not
    re-implemented here, because a second copy of a rule is a second rule."""
    path = os.path.join(root, gates_file)
    if not os.path.isfile(path):
        return [], {"ok": False, "reason": "no %s" % gates_file}
    if not os.path.isfile(GATE_CHECK):
        return [], {"ok": False, "reason": "gate-check.py not found at %s — gates not "
                                           "derived (stale)" % GATE_CHECK}
    cmd = [sys.executable, GATE_CHECK, path, "--json", "--cwd", root,
           "--timeout", str(timeout)]
    if budget:
        cmd += ["--budget", str(budget)]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout * 4 + 30)
        blob = json.loads(p.stdout.decode("utf-8", "replace"))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return [], {"ok": False, "reason": "gate-check did not answer (%s)" % exc}
    if blob.get("verdict") == "UNREADABLE":
        # The estate declares a contract it cannot read. That is one red part, named —
        # never a silent absence of gates.
        return ([{"id": "gates:contract", "title": "the declared gate contract is readable",
                  "claim": "done", "status": "wip", "evidence": "failed", "exit": 3,
                  "test": "gate-check.py %s" % gates_file, "falsifiable": True,
                  "proven_red": False, "demoted": False, "failing": True,
                  "outsha": "", "paths": [gates_file], "source": "gates"}],
                {"ok": False, "reason": blob.get("problem", "contract unreadable")})
    parts, used = [], {}
    for g in blob.get("gates") or []:
        base = "gate:" + slug(g.get("name") or g.get("check"))
        used[base] = used.get(base, 0) + 1
        pid = base if used[base] == 1 else "%s-%d" % (base, used[base])
        parts.append({"id": pid, "title": g.get("name") or "", "claim": "done",
                      "test": g.get("check") or "", "paths": [gates_file],
                      "line": g.get("line") or 0, "source": "gates",
                      "_exit": (0 if g.get("pass") else (g.get("exit") if g.get("exit") is not None else 1)),
                      "_outsha": g.get("outsha") or ""})
    return parts, {"ok": True, "gates": len(parts), "file": gates_file}


def collect_parts(root, cfg, args):
    """→ (parts, sources, problem). Parts carry their derived status; sources says what
    each input contributed, including what it could NOT contribute and why."""
    sources, problem = {}, ""
    raw = []
    map_file = cfg.get("map", "atlas/map.md")
    mtxt = read(os.path.join(root, map_file))
    if mtxt is None:
        sources["map"] = {"ok": False, "reason": "no %s" % map_file}
    else:
        mparts, mproblem = parse_map(mtxt)
        if mproblem:
            problem = "%s: %s" % (map_file, mproblem)
        sources["map"] = {"ok": not mproblem, "parts": len(mparts), "file": map_file,
                          "reason": mproblem}
        raw.extend(mparts)

    gparts, gsrc = ([], {"ok": False, "reason": "gates not read (--no-gates)"})
    if not args.no_gates:
        gparts, gsrc = gate_parts(root, cfg.get("gates", "gates/ACTIVE.md"),
                                  args.timeout, args.budget)
    sources["gates"] = gsrc
    raw.extend(gparts)

    reds = history_reds(root)
    parts = []
    for p in raw:
        if "status" in p:                       # already derived (the gates:contract part)
            p["proven_red"] = p["id"] in reds or p.get("proven_red", False)
            parts.append(p)
            continue
        test = p.get("test") or ""
        has = bool(test)
        fals = can_fail(test) if has else False
        if "_exit" in p:                        # gate-check already ran it
            rc, outsha = p.pop("_exit"), p.pop("_outsha", "")
        elif has and not args.dry_run:
            rc, outsha, _n = run_test(test, root, args.timeout)
        elif has:
            rc, outsha = None, ""               # --dry-run: nothing is executed
        else:
            rc, outsha = None, ""
        if rc is None and has:
            status, evidence, demoted, failing = (p["claim"], "not-run", False, False)
        else:
            status, evidence, demoted, failing = derive(p["claim"], has, fals, rc)
        parts.append({"id": p["id"], "title": p.get("title") or p["id"],
                      "claim": p["claim"], "status": status, "evidence": evidence,
                      "exit": rc, "test": test, "falsifiable": fals,
                      "proven_red": p["id"] in reds, "demoted": demoted,
                      "failing": failing, "outsha": outsha,
                      "paths": p.get("paths") or [], "source": p.get("source", "map")})
    # Two sources may name the same part; the map wins and the collision is reported.
    seen, deduped, dupes = set(), [], []
    for p in parts:
        if p["id"] in seen:
            dupes.append(p["id"])
            continue
        seen.add(p["id"])
        deduped.append(p)
    if dupes:
        sources["collisions"] = sorted(set(dupes))
    deduped.sort(key=lambda p: (STATUS_ORDER.get(p["status"], 9), p["id"]))
    return deduped, sources, problem


def summarize(parts):
    s = {"parts": len(parts), "done": 0, "wip": 0, "planned": 0, "blocked": 0,
         "failing": 0, "demoted": 0, "unfalsifiable": 0, "untested": 0, "proven_red": 0}
    for p in parts:
        s[p["status"]] = s.get(p["status"], 0) + 1
        s["failing"] += 1 if p["failing"] else 0
        s["demoted"] += 1 if p["demoted"] else 0
        s["unfalsifiable"] += 1 if p["evidence"] == "unfalsifiable" else 0
        s["untested"] += 1 if p["evidence"] == "none" else 0
        s["proven_red"] += 1 if p.get("proven_red") else 0
    # THE RED LAW: a claim of done with a failing test. Narrower than "something failed"
    # on purpose — red-first work is red by design and must not cry wolf.
    s["red"] = any(p["claim"] == "done" and p["evidence"] == "failed" for p in parts)
    return s


# ---------------------------------------------------------------------------
# the board — graph + river + the records card, each collector bounded and honest
# ---------------------------------------------------------------------------
def _collector(cmd, timeout, cwd):
    try:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, ""
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)


def build_board(root, commit, summary, args):
    """The estate's full board: graph.py's file graph, graph.py's river, and archivist's
    records CARD — COUNTS ONLY. No statement text ever enters the board, because the
    board is the thing that leaves the estate, and a finding's text is not the hub's
    business. A collector that fails or times out says STALE out loud; it never makes
    something up and it never fails the bank."""
    sources = {}
    out_dir = os.path.join(root, "atlas", "board")
    if args.no_board:
        for k in ("graph", "river", "records"):
            sources[k] = {"ok": False, "stale": True, "reason": "board collection disabled (--no-board)"}
        return {"schema": BOARD_SCHEMA, "commit": commit, "ts": utcnow(),
                "estate": estate_name(root), "generator": "atlas.py %s" % VERSION,
                "sources": sources, "summary": summary}
    os.makedirs(out_dir, exist_ok=True)
    gp = os.path.join(PLUGIN_ROOT, "skills", "graph", "scripts", "graph.py")
    ix = os.path.join(PLUGIN_ROOT, "skills", "archivist", "scripts", "index.py")
    t = args.board_timeout

    if os.path.isfile(gp):
        rc, _o = _collector([sys.executable, gp, "scan", "--root", root, "--out", out_dir], t, root)
        blob = {}
        try:
            blob = json.loads(read(os.path.join(out_dir, "graph.json")) or "{}")
        except ValueError:
            blob = {}
        sources["graph"] = ({"ok": True, "path": rel(root, os.path.join(out_dir, "graph.json")),
                             "nodes": len(blob.get("nodes") or []),
                             "edges": len(blob.get("edges") or [])}
                            if rc == 0 and blob else
                            {"ok": False, "stale": True,
                             "reason": "graph scan %s" % ("timed out after %ss" % t if rc == 124
                                                          else "exit %s" % rc)})
        river = os.path.join(out_dir, "river.html")
        rc, _o = _collector([sys.executable, gp, "river", "--root", root,
                             "--out", river, "--no-open"], t, root)
        # ok means THE ARTIFACT IS THERE, not merely that a process exited 0. A collector
        # that returns success and leaves nothing behind is the exact shape of a board
        # that looks fresh and is not.
        sources["river"] = ({"ok": True, "path": rel(root, river)}
                            if rc == 0 and os.path.isfile(river) else
                            {"ok": False, "stale": True,
                             "reason": "river %s" % ("timed out after %ss" % t if rc == 124
                                                     else "exit %s, no page written" % rc
                                                     if rc == 0 else "exit %s" % rc)})
    else:
        for k in ("graph", "river"):
            sources[k] = {"ok": False, "stale": True, "reason": "graph.py not installed"}

    if os.path.isfile(ix):
        rc, out = _collector([sys.executable, ix, "card", "--json", "--root", root], t, root)
        counts = {}
        try:
            counts = (json.loads(out) or {}).get("counts") or {}
        except ValueError:
            counts = {}
        sources["records"] = ({"ok": True, "counts": counts}       # counts, never text
                              if rc == 0 and counts else
                              {"ok": False, "stale": True,
                               "reason": "records card %s" % ("timed out after %ss" % t
                                                              if rc == 124 else "exit %s" % rc)})
    else:
        sources["records"] = {"ok": False, "stale": True, "reason": "index.py not installed"}

    return {"schema": BOARD_SCHEMA, "commit": commit, "ts": utcnow(),
            "estate": estate_name(root), "generator": "atlas.py %s" % VERSION,
            "sources": sources, "summary": summary}


# ---------------------------------------------------------------------------
# push adapters — push(snapshot, board, credential) -> (ok, hub_commit, reason)
# ---------------------------------------------------------------------------
def credential_for(cfg, adapter):
    """Presence, never contents. A token this script does not read is a token this
    script cannot leak into a snapshot, a log line, or an error message."""
    if adapter == "file":
        return {"kind": "file", "hub": cfg.get("hub") or "", "present": bool(cfg.get("hub"))}
    if adapter == "http":
        p = os.path.expanduser(cfg.get("credential")
                               or os.path.join(notrest_home(), "credentials", "atlas-token"))
        return {"kind": "token", "path": p, "present": os.path.isfile(p),
                "hub_url": cfg.get("hub_url") or ""}
    return {"kind": "none", "present": False}


def push_file(snapshot, board, credential):
    """The REAL adapter. A local hub directory, laid out exactly as the remote one:
    <hub>/<estate>/HEAD · snapshots/<commit>.json · board.json. The hub's snapshot is
    immutable too — an existing one is never overwritten, and that is reported as a
    success (it is already there), not as a failure."""
    hub = credential.get("hub") or ""
    if not hub:
        return (False, None, "file adapter: no hub directory configured (atlas/config.json 'hub')")
    est = snapshot["estate"]
    base = os.path.join(os.path.expanduser(hub), est)
    try:
        os.makedirs(os.path.join(base, "snapshots"), exist_ok=True)
        target = os.path.join(base, "snapshots", "%s.json" % snapshot["commit"])
        already = os.path.exists(target)
        if not already:
            write_atomic(target, json.dumps(snapshot, indent=1, sort_keys=True) + "\n", 0o444)
        write_atomic(os.path.join(base, "board.json"),
                     json.dumps(board, indent=1, sort_keys=True) + "\n")
        write_atomic(os.path.join(base, "HEAD"), snapshot["commit"] + "\n")
        stored = (read(os.path.join(base, "HEAD")) or "").strip()
    except OSError as exc:
        return (False, None, "file adapter: %s" % exc)
    if stored != snapshot["commit"]:
        return (False, stored or None, "file adapter: hub HEAD did not take the commit")
    return (True, stored, "file hub %s%s" % (base, " (snapshot already present)" if already else ""))


def push_http(snapshot, board, credential):
    """THE STUB, and the ONLY function that would ever speak to the hub.

    It does not send. It cannot send: this file imports no network module at all, and
    eval's NETWORK-EGRESS check re-proves that on every run, so the claim in this
    docstring is not something you have to believe. The body shape, the auth header, the
    idempotency key and the error contract are all defined by the hub, and this estate
    has not verified any of them — writing a plausible POST here would be inventing a
    protocol and calling it an integration.

    [unverified — awaiting ATLAS-PLAYBOOK/WIRING]"""
    return (False, None, "hub contract unverified — awaiting ATLAS-PLAYBOOK/WIRING")


def push_none(snapshot, board, credential):
    return (False, None, "no hub configured")


ADAPTERS = {"file": push_file, "http": push_http, "none": push_none}


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
def default_config(root):
    return {"schema": CONFIG_SCHEMA, "estate": estate_name(root), "adapter": "none",
            "hub": "", "hub_url": "",
            "credential": os.path.join(notrest_home(), "credentials", "atlas-token"),
            "map": "atlas/map.md", "gates": "gates/ACTIVE.md"}


def load_config(root, args):
    cfg = default_config(root)
    txt = read(os.path.join(root, "atlas", "config.json"))
    if txt:
        try:
            cfg.update({k: v for k, v in (json.loads(txt) or {}).items() if v != ""})
        except ValueError:
            pass                       # a broken config is a config we do not have
    if getattr(args, "adapter", None):
        cfg["adapter"] = args.adapter
    if getattr(args, "hub", None):
        cfg["hub"], cfg["adapter"] = args.hub, (args.adapter or "file")
    if cfg["adapter"] not in ADAPTERS:
        cfg["adapter"] = "none"
    return cfg


# ---------------------------------------------------------------------------
# bank
# ---------------------------------------------------------------------------
def head_of(root):
    rc, out = git(root, "rev-parse", "HEAD")
    return out if rc == 0 and re.match(r"^[0-9a-f]{7,40}$", out) else ""


def cmd_bank(args):
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        sys.stderr.write("atlas bank: no such root %s\n" % root)
        return 2
    rc, _ = git(root, "rev-parse", "--is-inside-work-tree")
    if rc != 0:
        sys.stderr.write("atlas bank: %s is not a git work tree — a snapshot with no "
                         "commit to stamp is not evidence of anything\n" % root)
        return 3
    commit = head_of(root)
    if not commit:
        sys.stderr.write("atlas bank: no HEAD commit yet — nothing to stamp\n")
        return 3
    cfg = load_config(root, args)
    parts, sources, problem = collect_parts(root, cfg, args)
    if problem:
        sys.stderr.write("atlas bank: %s\n" % problem)
        return 3
    if not parts:
        sys.stderr.write(
            "atlas bank: nothing to derive — no parts in %s and no gates in %s. An estate "
            "with no declared contract is never certified green; declare a PART or arm a "
            "GATE.\n" % (cfg.get("map"), cfg.get("gates")))
        return 3

    summary = summarize(parts)
    _rc, branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    _rc, parent = git(root, "rev-parse", "HEAD^")
    born = {}
    btxt = read(os.path.join(root, "atlas", "born-red.json"))
    if btxt:
        try:
            b = json.loads(btxt)
            born = {"present": True, "ts": b.get("ts"), "verdict": b.get("verdict")}
        except ValueError:
            born = {"present": False, "reason": "born-red.json unreadable"}
    else:
        born = {"present": False, "reason": "no born-red proof recorded (wire --prove)"}

    snapshot = {"schema": SCHEMA, "estate": estate_name(root), "commit": commit,
                "parent": parent if _rc == 0 else "", "branch": branch,
                "ts": utcnow(), "generator": "atlas.py %s" % VERSION,
                "born_red_proof": born, "sources": sources,
                "parts": parts, "summary": summary}

    board = build_board(root, commit, summary, args)
    snapshot["board_sha256"] = sha(json.dumps(board, indent=1, sort_keys=True))

    snap_dir = os.path.join(root, "atlas", "snapshots")
    snap_path = os.path.join(snap_dir, "%s.json" % commit)
    snap_state = "dry-run (nothing written)"
    if not args.dry_run:
        os.makedirs(snap_dir, exist_ok=True)
        if os.path.exists(snap_path):
            # IMMUTABLE. A snapshot is what this commit looked like when it landed; a
            # re-bank that rewrote it would make history a function of when you asked.
            # A different derivation now is a fact about NOW, and now needs a new commit.
            prev = ""
            try:
                prev = sha(json.dumps((json.loads(read(snap_path) or "{}")).get("parts"),
                                      sort_keys=True))
            except ValueError:
                prev = ""
            cur = sha(json.dumps(parts, sort_keys=True))
            snap_state = ("immutable — the banked snapshot stands"
                          + ("; today's derivation DIFFERS (a new state needs a new commit)"
                             if prev and prev != cur else ""))
        else:
            write_atomic(snap_path, json.dumps(snapshot, indent=1, sort_keys=True) + "\n", 0o444)
            snap_state = "written"
        write_atomic(os.path.join(root, "atlas", "board.json"),
                     json.dumps(board, indent=1, sort_keys=True) + "\n")

    adapter = cfg["adapter"]
    cred = credential_for(cfg, adapter)
    if args.dry_run:
        ok, hub_commit, reason = (False, None, "dry-run: nothing pushed")
    else:
        ok, hub_commit, reason = ADAPTERS[adapter](snapshot, board, cred)
    push = {"adapter": adapter, "ok": ok, "hub_commit": hub_commit, "reason": reason,
            "credential_present": cred.get("present", False)}

    if args.json:
        print(json.dumps({"snapshot": rel(root, snap_path), "snapshot_state": snap_state,
                          "push": push, "summary": summary, "parts": parts,
                          "board": board}, indent=2, sort_keys=True))
    elif args.quiet:
        # The snapshot state rides on the quiet line too: a run whose derivation differs
        # from the snapshot that stands is exactly the moment a reader must not be told
        # only the new numbers.
        print("atlas: banked %s · %d parts · %d done · %d failing · %d demoted · board %s "
              "· snapshot %s · push: %s"
              % (commit[:12], summary["parts"], summary["done"], summary["failing"],
                 summary["demoted"], "RED" if summary["red"] else "green",
                 snap_state, reason if not ok else "ok"))
    else:
        print("atlas %s · %s @ %s (%s)" % (VERSION, snapshot["estate"], commit[:12], branch))
        print("")
        print("  %-28s %-8s %-9s %s" % ("PART", "CLAIM", "STATUS", "EVIDENCE"))
        for p in parts:
            note = p["evidence"]
            if p["evidence"] == "passed":
                note = "passed (exit 0, out %s…)" % (p["outsha"][:8] or "-")
            elif p["evidence"] == "failed":
                note = "FAILED (exit %s)" % p["exit"]
            elif p["evidence"] == "none":
                note = "none — no test bound"
            elif p["evidence"] == "unfalsifiable":
                note = "unfalsifiable — that command cannot fail"
            flags = []
            if p["demoted"]:
                flags.append("DEMOTED from done")
            if p["failing"]:
                flags.append("failing")
            if p.get("proven_red"):
                flags.append("proven-red")
            print("  %-28s %-8s %-9s %s%s"
                  % (p["id"][:28], p["claim"], p["status"], note,
                     ("  [%s]" % ", ".join(flags)) if flags else ""))
        print("")
        print("SUMMARY : %d parts · %d done · %d wip · %d failing · %d demoted · "
              "%d untested · board %s"
              % (summary["parts"], summary["done"], summary["wip"], summary["failing"],
                 summary["demoted"], summary["untested"],
                 "RED" if summary["red"] else "GREEN"))
        print("SNAPSHOT: %s (%s)" % (rel(root, snap_path), snap_state))
        print("BOARD   : %s" % " · ".join(
            "%s %s" % (k, "ok" if v.get("ok") else "STALE (%s)" % v.get("reason"))
            for k, v in sorted(board["sources"].items())))
        print("PUSH    : %s — %s" % (adapter, reason if not ok else "pushed · hub HEAD %s"
                                     % (hub_commit or "")[:12]))
        if summary["red"]:
            for p in parts:
                if p["claim"] == "done" and p["evidence"] == "failed":
                    print("RED: %s — claims done, its test exits %s   [%s]"
                          % (p["id"], p["exit"], p["test"][:80]))

    if summary["red"]:
        return 5
    if not ok and adapter != "none" and not args.dry_run:
        return 4
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
def hooks_dir(root):
    rc, hp = git(root, "config", "--get", "core.hooksPath")
    if rc == 0 and hp:
        return hp if os.path.isabs(hp) else os.path.join(root, hp)
    rc, gd = git(root, "rev-parse", "--git-dir")
    if rc != 0 or not gd:
        return ""
    return os.path.join(root, gd, "hooks") if not os.path.isabs(gd) else os.path.join(gd, "hooks")


def wired_state(root):
    d = hooks_dir(root)
    if not d:
        return (False, "", "not a git work tree")
    p = os.path.join(d, "post-commit")
    txt = read(p)
    if txt is None:
        return (False, p, "no post-commit hook")
    if HOOK_MARK in txt:
        return (True, p, "wired")
    return (False, p, "a post-commit hook exists that atlas did not write")


def cmd_status(args):
    root = os.path.abspath(args.root)
    rc, _ = git(root, "rev-parse", "--is-inside-work-tree")
    if rc != 0:
        sys.stderr.write("atlas status: %s is not a git work tree\n" % root)
        return 3
    commit = head_of(root)
    if not commit:
        # A repo with no commit is not an estate that failed to bank — it is an estate
        # with nothing to bank. Reporting exit 6 (the born-red signal) here would make
        # "never committed" indistinguishable from "committed and skipped the bank".
        sys.stderr.write("atlas status: no HEAD commit yet in %s — nothing to bank\n" % root)
        return 3
    snap_dir = os.path.join(root, "atlas", "snapshots")
    snaps = sorted(glob.glob(os.path.join(snap_dir, "*.json")))
    if not os.path.isdir(os.path.join(root, "atlas")):
        sys.stderr.write("atlas status: no atlas/ in %s — this estate is not on the map "
                         "(atlas.py wire)\n" % root)
        return 3
    snap_path = os.path.join(snap_dir, "%s.json" % commit) if commit else ""
    banked = bool(snap_path) and os.path.exists(snap_path)
    blob = {}
    if banked:
        try:
            blob = json.loads(read(snap_path) or "{}")
        except ValueError:
            blob = {}
    summary = blob.get("summary") or {}
    cfg = load_config(root, args)
    cred = credential_for(cfg, cfg["adapter"])
    if cfg["adapter"] == "file" and cred.get("hub"):
        stored = (read(os.path.join(os.path.expanduser(cred["hub"]),
                                    estate_name(root), "HEAD")) or "").strip()
        hub = ("in sync (%s)" % stored[:12]) if stored == commit else (
            "BEHIND — hub holds %s, HEAD is %s" % (stored[:12] or "nothing", commit[:12]))
    elif cfg["adapter"] == "http":
        hub = "unverified — the http adapter never sent (hub contract unverified)"
    else:
        hub = "no hub configured"
    is_wired, hook_path, hook_why = wired_state(root)
    age = ""
    if banked:
        try:
            age = "%.1f h" % ((datetime.now(timezone.utc)
                               - datetime.strptime(blob.get("ts", ""), "%Y-%m-%dT%H:%M:%SZ")
                               .replace(tzinfo=timezone.utc)).total_seconds() / 3600.0)
        except (ValueError, TypeError):
            age = "unknown"

    code = 0 if banked and not summary.get("red") else (5 if banked else 6)
    verdict = {0: "GREEN", 5: "RED — a part claims done and its test fails",
               6: "RED — HEAD is NOT banked: this commit never ran the bank"}[code]
    if args.json:
        print(json.dumps({"estate": estate_name(root), "head": commit, "banked": banked,
                          "snapshot": rel(root, snap_path) if banked else None,
                          "snapshot_age_hours": age, "snapshots": len(snaps),
                          "summary": summary, "adapter": cfg["adapter"], "hub": hub,
                          "wired": is_wired, "hook": hook_why, "verdict": verdict,
                          "exit": code}, indent=2, sort_keys=True))
        return code
    print("atlas status · %s @ %s" % (estate_name(root), commit[:12] or "no HEAD"))
    print("  banked   : %s%s" % ("yes — %s" % rel(root, snap_path) if banked
                                 else "NO — this commit has no snapshot",
                                 " (age %s)" % age if age else ""))
    print("  snapshots: %d" % len(snaps))
    if summary:
        print("  board    : %d parts · %d done · %d failing · %d demoted · %s"
              % (summary.get("parts", 0), summary.get("done", 0), summary.get("failing", 0),
                 summary.get("demoted", 0), "RED" if summary.get("red") else "green"))
    print("  hub      : %s (adapter %s)" % (hub, cfg["adapter"]))
    print("  hook     : %s" % ("wired at %s" % rel(root, hook_path) if is_wired else hook_why))
    print("  VERDICT  : %s" % verdict)
    return code


# ---------------------------------------------------------------------------
# wire — install the tracked post-commit hook, and prove it can go red
# ---------------------------------------------------------------------------
SHIM = """#!/bin/sh
# %(mark)s — installed by `atlas.py wire`; remove with `atlas.py wire --unwire`.
# Banks this commit into the estate's atlas. It never blocks a commit: post-commit runs
# after the commit exists, this shim ignores every failure, and it always exits 0.
NOTREST_ATLAS_PY="%(atlas)s"
export NOTREST_ATLAS_PY
BODY="%(body)s"
[ -r "$BODY" ] || exit 0
sh "$BODY"
exit 0
"""

SEED_MAP = """# atlas/map.md — what this estate says it is building
#
# One PART per thing worth knowing the state of. The status is NOT what you write here:
# you write the CLAIM, atlas runs the TEST, and the status is derived from the exit code.
#
#   PART: <id> — <title>
#   CLAIM: done | wip | planned | blocked      (default: wip)
#   TEST: <a shell command that could fail>    (optional — but a done with no test is
#                                               demoted to wip and reported)
#   PATH: <where the code lives>               (optional, repeatable)
#
# Every gate in gates/ACTIVE.md is picked up automatically as a part CLAIMED done.
# Directives inside a fenced code block are documentation and are never run.

PART: example — replace me with a real part
CLAIM: planned
"""


def wire_paths(root):
    d = hooks_dir(root)
    return d, (os.path.join(d, "post-commit") if d else "")


def do_wire(root, force=False, quiet=False):
    """→ (exit, message). Idempotent: wiring an already-wired estate rewrites the same
    shim and says so. A post-commit hook atlas did not write is NEVER clobbered."""
    d, post = wire_paths(root)
    if not d:
        return 3, "not a git work tree: %s" % root
    os.makedirs(d, exist_ok=True)
    existing = read(post)
    already = existing is not None and HOOK_MARK in existing
    if existing is not None and not already:
        if not force:
            return 5, ("REFUSED — %s exists and atlas did not write it. Merge the two by "
                       "hand, or re-run with --force (the original is kept as "
                       "post-commit.pre-atlas)." % post)
        shutil.copy2(post, post + ".pre-atlas")
    body = SHIM % {"mark": HOOK_MARK, "atlas": os.path.abspath(__file__),
                   "body": os.path.abspath(BANK_HOOK)}
    write_atomic(post, body, 0o755)
    os.makedirs(os.path.join(root, "atlas"), exist_ok=True)
    if not os.path.exists(os.path.join(root, "atlas", "map.md")):
        write_atomic(os.path.join(root, "atlas", "map.md"), SEED_MAP)
    if not os.path.exists(os.path.join(root, "atlas", "config.json")):
        write_atomic(os.path.join(root, "atlas", "config.json"),
                     json.dumps(default_config(root), indent=1, sort_keys=True) + "\n")
    return 0, ("already wired — shim refreshed at %s" % post) if already else \
               ("wired: %s → %s" % (post, os.path.abspath(BANK_HOOK)))


def do_unwire(root):
    d, post = wire_paths(root)
    if not d:
        return 3, "not a git work tree: %s" % root
    txt = read(post)
    if txt is None:
        return 0, "not wired (no post-commit hook)"
    if HOOK_MARK not in txt:
        return 0, "left alone — %s is not atlas's hook" % post
    backup = post + ".pre-atlas"
    if os.path.exists(backup):
        shutil.move(backup, post)
        return 0, "unwired — restored the pre-atlas hook at %s" % post
    os.unlink(post)
    return 0, "unwired — removed %s" % post


PROOF_MAP = """# the born-red proof's scratch map — a part whose test really can fail.
PART: proof — the proof file is present
CLAIM: done
TEST: test -f proof.txt
"""


def _scratch_commit(repo, msg):
    git(repo, "add", "-A")
    rc, _o = git(repo, "-c", "user.email=atlas@notrest.local", "-c", "user.name=atlas",
                 "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", msg)
    return rc, head_of(repo)


def do_prove(root, args):
    """THE BORN-RED PROOF. An estate joins the map only after it has been SEEN to go red:
    wire the hook, commit (green), disable the hook, commit (must go RED), restore, commit
    (green again). A detector nobody watched fail is not a detector.

    It runs in a SCRATCH GIT REPO — never your history, never your working tree. The
    scratch is seeded with its own two-line map, so the proof tests the WIRING (does a
    commit that skipped the bank show up as red?) rather than your estate's tests."""
    if not key_ok(getattr(args, "keyring", None)):
        return 7, ["no access key on this machine — the bank hook exits silently without "
                   "one, so the proof would show red for the wrong reason. Mint a key "
                   "first: atlas.py key --mint --label <who>"], {}
    scratch = tempfile.mkdtemp(prefix="atlas-prove-")
    steps, log = [], []
    # The hook runs in a CHILD of this process and re-does the key check itself, so an
    # explicit --keyring has to reach it through the environment or the proof would go
    # red for the wrong reason. The board collectors are skipped: this proof is about
    # the WIRING, and three graph scans would be three minutes of proving nothing.
    if getattr(args, "keyring", None):
        os.environ["NOTREST_KEYRING"] = os.path.abspath(args.keyring)
    os.environ["NOTREST_ATLAS_NO_BOARD"] = "1"
    try:
        rc, _o = git(scratch, "-c", "init.defaultBranch=main", "init", "-q")
        if rc != 0:
            return 3, ["could not git init the scratch repo"], {}
        git(scratch, "config", "--local", "core.hooksPath", ".git/hooks")
        write_atomic(os.path.join(scratch, "proof.txt"), "the proof file\n")
        write_atomic(os.path.join(scratch, "atlas", "map.md"), PROOF_MAP)
        write_atomic(os.path.join(scratch, "atlas", "config.json"),
                     json.dumps(default_config(scratch), indent=1, sort_keys=True) + "\n")
        code, msg = do_wire(scratch)
        log.append("wire: %s" % msg)
        if code != 0:
            return code, log, {}

        class _S(object):                       # status args for the scratch
            json = False
            root = scratch
            adapter = hub = None
        st = _S()

        rc, c1 = _scratch_commit(scratch, "atlas proof: step 1 (hook live)")
        e1 = _quiet_status(st)
        steps.append({"step": 1, "what": "commit with the hook LIVE", "commit": c1,
                      "status_exit": e1, "want": 0})
        log.append("step 1 · hook live      · commit %s · status exit %d (want 0)" % (c1[:12], e1))

        d, post = wire_paths(scratch)
        shutil.move(post, post + ".off")
        write_atomic(os.path.join(scratch, "drift.txt"), "a commit that skips the bank\n")
        rc, c2 = _scratch_commit(scratch, "atlas proof: step 2 (hook DISABLED)")
        e2 = _quiet_status(st)
        steps.append({"step": 2, "what": "commit with the hook DISABLED", "commit": c2,
                      "status_exit": e2, "want": 6})
        log.append("step 2 · hook disabled  · commit %s · status exit %d (want 6 = RED)" % (c2[:12], e2))

        shutil.move(post + ".off", post)
        write_atomic(os.path.join(scratch, "drift.txt"), "restored\n")
        rc, c3 = _scratch_commit(scratch, "atlas proof: step 3 (hook restored)")
        e3 = _quiet_status(st)
        steps.append({"step": 3, "what": "commit with the hook RESTORED", "commit": c3,
                      "status_exit": e3, "want": 0})
        log.append("step 3 · hook restored  · commit %s · status exit %d (want 0)" % (c3[:12], e3))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    passed = [s["status_exit"] == s["want"] for s in steps]
    verdict = "PASS" if len(steps) == 3 and all(passed) else "FAIL"
    receipt = {"schema": "notrest.atlas.bornred/1", "ts": utcnow(),
               "generator": "atlas.py %s" % VERSION, "verdict": verdict, "steps": steps,
               "estate": estate_name(root),
               "bound": "proved in a scratch git repo seeded with its own map — never "
                        "this estate's history or working tree"}
    return (0 if verdict == "PASS" else 6), log, receipt


def _quiet_status(st):
    """cmd_status's exit code without its noise — the proof reports its own steps."""
    import io
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        return cmd_status(st)
    finally:
        sys.stdout = old


def cmd_wire(args):
    root = os.path.abspath(args.root)
    if args.unwire:
        code, msg = do_unwire(root)
        print("atlas wire: %s" % msg)
        return code
    if args.prove:
        code, log, receipt = do_prove(root, args)
        print("atlas born-red proof · %s" % estate_name(root))
        for line in log:
            print("  %s" % line)
        if receipt:
            print("  VERDICT: %s" % receipt["verdict"])
            if not args.no_receipt:
                p = os.path.join(root, "atlas", "born-red.json")
                write_atomic(p, json.dumps(receipt, indent=1, sort_keys=True) + "\n")
                print("  receipt: %s" % rel(root, p))
        if code == 6:
            sys.stderr.write("atlas wire --prove: the proof did NOT go red — a commit that "
                             "skipped the bank was reported as fine, so this estate's "
                             "detector cannot detect. Do not join the map.\n")
        return code
    code, msg = do_wire(root, force=args.force)
    print("atlas wire: %s" % msg)
    if code == 5:
        sys.stderr.write("atlas wire: %s\n" % msg)
    return code


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="atlas.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("key", help="mint / check / revoke the access keys")
    k.add_argument("--mint", action="store_true", help="mint a key and print it ONCE")
    k.add_argument("--label", default="", help="who the key is for (with --mint)")
    k.add_argument("--check", action="store_true",
                   help="exit 0 valid · 7 none or invalid. On 0 — and on 0 ONLY — stdout "
                        "carries exactly one line, the SENTINEL: 'notrest-access: ok "
                        "ring=<12 hex of sha256(keyring bytes)> path=<the ring used>'. "
                        "--quiet keeps it. A caller must REQUIRE that line verbatim: an "
                        "exit code alone is something a fake python3 can produce, the "
                        "sentinel is not. A symlinked or non-regular keyring is refused (7).")
    k.add_argument("--revoke", default="", metavar="LABEL", help="delete that label's line")
    k.add_argument("--list", action="store_true", help="labels and dates (never a key)")
    k.add_argument("--key", default=None, help="the key to check (else env, else the file)")
    k.add_argument("--keyring", default=None, help="keyring path (default: the plugin's)")
    k.add_argument("--quiet", action="store_true", help="say nothing; the exit code answers")
    k.set_defaults(f=cmd_key)

    b = sub.add_parser("bank", help="derive the map from exit codes, snapshot it, push it")
    b.add_argument("--root", default=".")
    b.add_argument("--adapter", default=None, choices=sorted(ADAPTERS), help="override the config")
    b.add_argument("--hub", default=None, help="file-adapter hub directory")
    b.add_argument("--no-board", action="store_true", help="skip the board collectors")
    b.add_argument("--no-gates", action="store_true", help="derive from the map only")
    b.add_argument("--board-timeout", type=int, default=45, help="per collector seconds")
    b.add_argument("--timeout", type=int, default=120, help="per TEST seconds")
    b.add_argument("--budget", type=int, default=0, help="wall-clock seconds for all gates")
    b.add_argument("--dry-run", action="store_true", help="derive and report; write nothing, run nothing")
    b.add_argument("--quiet", action="store_true", help="one summary line (what the hook uses)")
    b.add_argument("--json", action="store_true")
    b.set_defaults(f=cmd_bank)

    w = sub.add_parser("wire", help="install the tracked post-commit bank hook")
    w.add_argument("--root", default=".")
    w.add_argument("--prove", action="store_true", help="the born-red proof, in a scratch repo")
    w.add_argument("--unwire", action="store_true")
    w.add_argument("--force", action="store_true", help="overwrite a foreign post-commit hook")
    w.add_argument("--no-receipt", action="store_true", help="--prove: do not write atlas/born-red.json")
    w.add_argument("--keyring", default=None)
    w.set_defaults(f=cmd_wire)

    s = sub.add_parser("status", help="HEAD vs last banked, snapshot age, hub, hook")
    s.add_argument("--root", default=".")
    s.add_argument("--adapter", default=None, choices=sorted(ADAPTERS))
    s.add_argument("--hub", default=None)
    s.add_argument("--json", action="store_true")
    s.set_defaults(f=cmd_status)

    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
