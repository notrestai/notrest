#!/usr/bin/env python3
"""establish.py — the establishment verb's instrument.

The harness auto-nudges every session, but PRESENCE IS NOT ESTABLISHMENT. This script
answers the two file-level questions the seat cannot answer by vibe — *is the harness
established in this project* (`check`) and *make it so* (`establish`) — and nothing else.
The seat reads the lines and judges; the script only reports facts and writes surfaces.

Constraints this file is built under:
  - python3 stdlib ONLY. No network, no model calls — this runs in a stranger's project
    on a bare interpreter.
  - EVERY write is idempotent and atomic (tmp file + os.replace in the same directory).
    Running `establish` twice must leave the project byte-identical to running it once.
  - BYTE-EXACT ROUND TRIP on any file we rewrite. Reading with errors="replace" and
    universal newlines, then writing the whole file back, silently destroys latin-1 bytes
    (they become U+FFFD, permanently) and rewrites every CRLF as LF. So a round-tripped
    file is read AND written with errors="surrogateescape", newline="" — the bytes we did
    not author come back exactly as they went in.
  - NOTHING is written outside the resolved root; a path whose realpath escapes the root
    is refused rather than followed, and an in-root symlink is written THROUGH (we operate
    on its realpath) so the link survives instead of being replaced by a regular file.
  - The root is refused rather than guessed. $HOME is never a project, a subdirectory of a
    git repo is never a root (every hook would resolve to the toplevel instead), and a
    directory with no project marker is refused outright.
  - REPORT/JUDGE SPLIT (load-bearing): establishment checks drive the exit code; adoption
    facts are INFO and can never move it. "Is this session actually following the plugin"
    is a judgment, and it belongs to the seat reading these lines.

Exit codes: 0 established · 5 partially established · 6 not established · 2 usage/refusal.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"
EXIT_OK, EXIT_USAGE, EXIT_PARTIAL, EXIT_NONE = 0, 2, 5, 6

# A directory only counts as a project if it carries one of these. NOTE the absence of
# `.claude`: ~/.claude exists on every machine this harness runs on, so that one entry
# made $HOME a project — and `/notrest` from a home directory would have written COORD.md
# and a CLAUDE.md there, the CLAUDE.md that Claude Code then loads into every session on
# the machine. Found by the adversarial round, 2026-08-02.
PROJECT_MARKERS = ("CLAUDE.md", "README.md", "package.json", "pyproject.toml", "COORD.md")

PROTOCOL_VERSION = 1
BLOCK_CLOSE = "<!-- /notrest:protocol -->"
# Line-anchored on purpose, and every search runs over FENCE-MASKED text: an unanchored
# search matches the marker inside a fenced documentation EXAMPLE, and a file that merely
# *describes* the block must never read as a file that *carries* it. Our own SKILL.md and
# CHANGELOG quote these markers.
BLOCK_OPEN_RE = re.compile(r"^[ \t]*<!--[ \t]*notrest:protocol[ \t]+v(\d+)\b[^>]*-->[ \t]*\r?$",
                           re.M)
BLOCK_CLOSE_RE = re.compile(r"^[ \t]*<!--[ \t]*/notrest:protocol[ \t]*-->[ \t]*\r?$", re.M)

# The COORD scaffold is REPRODUCED VERBATIM from hooks/session-start.sh (2026-08-02).
# Two writers, one shape: a session that starts in a git repo and a project established
# by hand must produce the same file, or /recap, /compile and /archivist meet two
# dialects of their own ledger. The fixture asserts the two byte-for-byte.
COORD_SCAFFOLD = """# COORD.md — session coordination ledger

Append-only, newest at the bottom, one line per substantive prompt when its work
lands: `- [YYYY-MM-DD HH:MMZ] [session-or-lane] <what was asked> -> <what landed> | evidence: <exit code / commit / path / status>`.
Honest entries only: in-progress is "in progress", untested is "untested". Never
compacted: past ~500 ledger lines this file is SEALED WHOLE as the next COORD-<NNN>.md
and a fresh active volume starts — sealed volumes are immutable, sessions read this
active tail, /recap + /compile + /archivist read every volume. In a fable-director
arrangement, lane blackboards live beside this file as COORD-<LANE>.md (never all
digits — that is a sealed volume); this file is the ship/main ledger.

## LEDGER
"""

# The managed block's BODY, keyed by protocol version. Keeping the historical bodies is
# what lets an upgrade tell an untouched block (safe to replace) from one somebody edited
# by hand (replace, but bank a copy and say so).
BODY_V1 = """## notrest protocol

- **Fable discipline** — ORIENT -> PROBE -> ACT -> PROVE -> BANK. Probe the live
  system before reasoning; a done/works/fixed claim needs in-transcript evidence
  (exit code, diff, status) or it is labeled unverified; bank state before stopping.
  Full contract: `/notrest:fable-mode`.
- **Offload HARD RULE** — every spawned lane sets model `"opus"` explicitly. Never
  sonnet, never haiku, never a fork (a fork inherits the seat and bills its credit);
  omitting the model is a violation, not a default. Delegate via `/notrest:agentswarm`;
  a build runs ONE persistent lane and feedback RESUMES that lane, never a fresh spawn.
- **COORD law** — one honest ledger line per substantive prompt when its work lands:
  `ask -> landed | evidence`. `COORD.md` is append-only and is never compacted: at
  ~500 lines it seals whole as `COORD-<NNN>.md` and a fresh volume opens.
- **Close** a working session with `/sessionend`. **Drift check:** `/notrest check`."""

CANONICAL_BODIES = {1: BODY_V1}


def open_marker(version):
    return ("<!-- notrest:protocol v%d (do not edit inside markers; managed by /notrest) -->"
            % version)


def protocol_block(version=PROTOCOL_VERSION):
    return "%s\n%s\n%s\n" % (open_marker(version), CANONICAL_BODIES[version], BLOCK_CLOSE)


# ── io ────────────────────────────────────────────────────────────────────────────────
def read_rt(path):
    """ROUND-TRIP read: surrogateescape keeps bytes we cannot decode recoverable, and
    newline="" keeps CRLF (and lone CR) exactly as they sit on disk. Anything we may
    later write back must be read through here."""
    try:
        with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as f:
            return f.read()
    except OSError:
        return None


def read_text(path):
    """Read-only inspection where round-trip fidelity is irrelevant (the COORD checks)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def atomic_write(path, text, roundtrip=False):
    """tmp file in the SAME directory + os.replace — a reader never sees a half-file, and
    a crash mid-write leaves the original intact. `roundtrip` preserves the byte and
    line-ending fidelity of a file we did not author."""
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".notrest-", suffix=".tmp")
    try:
        if roundtrip:
            fh = os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="")
        else:
            fh = os.fdopen(fd, "w", encoding="utf-8")
        with fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def blank_line(line):
    """Same length, same newline, no content — masking that preserves every offset."""
    return "".join(c if c in "\r\n" else " " for c in line)


def mask_fences(txt):
    """Blank out CLOSED fenced (``` / ~~~) regions, preserving offsets and line numbers.

    An opener with no closer masks NOTHING — the dangling backticks are treated as the
    literal text they are. The first version masked to end-of-file, which hid a real
    protocol block from every search: `check` reported no block while it sat in plain
    sight, and `establish` appended a fresh one on every run (4 blocks after 3 runs — the
    idempotency law, broken by a masking bug). Our consumer is a model reading CLAUDE.md
    as instructions, and an unterminated fence hides nothing from it either."""
    lines = txt.splitlines(True)
    toks = []
    for line in lines:
        st = line.lstrip()
        toks.append("```" if st.startswith("```") else ("~~~" if st.startswith("~~~") else None))
    out, i = list(lines), 0
    while i < len(lines):
        if toks[i]:
            j = i + 1
            while j < len(lines) and toks[j] != toks[i]:
                j += 1
            if j < len(lines):                      # a CLOSED fence: mask opener..closer
                for k in range(i, j + 1):
                    out[k] = blank_line(lines[k])
                i = j + 1
                continue
        i += 1                                       # unclosed opener: literal, mask nothing
    return "".join(out)


def not_utf8(path):
    """A description when the file is plainly not UTF-8, else None. Appending a UTF-8
    block to a UTF-16 file "preserves the bytes" and destroys the file for its own reader
    — the block is unreadable mojibake and the next round-trip read raises. Refuse."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return None
    for bom, name in ((b"\xff\xfe\x00\x00", "UTF-32 LE BOM"),
                      (b"\x00\x00\xfe\xff", "UTF-32 BE BOM"),
                      (b"\xff\xfe", "UTF-16 LE BOM"), (b"\xfe\xff", "UTF-16 BE BOM")):
        if head.startswith(bom):
            return name
    if head and head.count(b"\x00") > max(1, len(head) // 64):
        return "NUL bytes in the first %d bytes (UTF-16/32 without a BOM)" % len(head)
    return None


def lineno(txt, pos):
    return txt.count("\n", 0, pos) + 1


def contain(root, path):
    """The realpath to operate on, or None when it escapes the root. Returning the
    REALPATH is what lets an in-root symlink survive an atomic replace: we rewrite the
    file the link points at instead of replacing the link with a regular file."""
    try:
        r = os.path.realpath(root)
        p = os.path.realpath(path)
        return p if p == r or p.startswith(r + os.sep) else None
    except OSError:
        return None


def git(root, *args):
    try:
        p = subprocess.run(["git"] + list(args), cwd=root, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=20)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def git_toplevel(root):
    rc, out = git(root, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if rc == 0 and out else ""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")


# ── root resolution ───────────────────────────────────────────────────────────────────
def resolve_root(explicit):
    """(root, error). --root wins; else the git root; else the cwd IF it looks like a
    project; else a refusal that NAMES what it looked for. Always realpath'd."""
    if explicit:
        r = os.path.realpath(os.path.expanduser(explicit))
        if not os.path.isdir(r):
            return None, "--root %s is not a directory" % explicit
    else:
        top = git_toplevel(os.getcwd())
        if top:
            r = top
        else:
            cwd = os.path.realpath(os.getcwd())
            if not any(os.path.exists(os.path.join(cwd, m)) for m in PROJECT_MARKERS):
                return None, ("%s is not a git repo and carries no project marker (looked "
                              "for: %s) — refusing to establish the estate here. Pass "
                              "--root <project> if this really is the project root."
                              % (cwd, ", ".join(PROJECT_MARKERS)))
            r = cwd

    # $HOME and the filesystem root are refused however they were reached, --root
    # included: a CLAUDE.md in $HOME is loaded into every session on this machine, and
    # there is no such thing as a legitimate $HOME estate.
    home = os.path.realpath(os.path.expanduser("~"))
    if r == home:
        return None, ("%s is your HOME directory, not a project — refusing. A CLAUDE.md "
                      "here is loaded into every session on this machine; establish "
                      "inside the project itself." % r)
    if r == os.path.dirname(r):
        return None, "%s is a filesystem root, not a project — refusing." % r
    for wk in ("Desktop", "Documents", "Downloads"):
        if r == os.path.join(home, wk):
            return None, ("%s is a well-known home folder, not a project — refusing. Its "
                          "SUBdirectories are ordinary projects; establish in the one you "
                          "mean." % r)

    # A subdirectory of a git repo is never a root: every estate hook resolves to the
    # TOPLEVEL, so an estate established here would be written by nobody and read by
    # nobody. Refuse, and name the path that actually works.
    top = git_toplevel(r)
    if top and top != r:
        return None, ("%s is inside the git repo at %s — every estate hook resolves to "
                      "that toplevel, so an estate here would be dead on arrival. Use "
                      "--root %s instead." % (r, top, top))
    return r, None


# ── the establishment surfaces ────────────────────────────────────────────────────────
def coord_state(root):
    """(status, detail). PASS = a ledger a reader can append to."""
    p = os.path.join(root, "COORD.md")
    try:
        empty = os.path.getsize(p) == 0 if os.path.isfile(p) else True
    except OSError:
        empty = True
    if empty:
        return FAIL, "COORD.md absent (or empty) — the project has no session ledger"
    txt = read_text(p) or ""
    if "## LEDGER" not in txt:
        return WARN, ("COORD.md present but carries no '## LEDGER' header — every estate "
                      "reader (/recap, /compile, /archivist) parses for it. Repair by "
                      "appending one line '## LEDGER'; this tool never rewrites a ledger")
    return PASS, "COORD.md present with the ledger header"


def find_blocks(txt):
    """(masked_text, [(version, open_match, close_match_or_None)]) over masked text."""
    masked = mask_fences(txt)
    out = []
    for m in BLOCK_OPEN_RE.finditer(masked):
        c = BLOCK_CLOSE_RE.search(masked, m.end())
        out.append((int(m.group(1)), m, c))
    return masked, out


def block_problem(txt):
    """(detail, None) when the markers are unusable — ambiguity that must never be
    written through. (None, blocks) when they are usable."""
    masked, blocks = find_blocks(txt)
    if len(blocks) > 1:
        first_v, first_m, first_c = blocks[0]
        # A second OPEN inside the first span means the "block" swallows real content.
        if first_c and blocks[1][1].start() < first_c.start():
            return ("multiple/ambiguous protocol markers — a second open marker at line %d "
                    "sits INSIDE the block opened at line %d, so everything between them "
                    "would be swallowed. Resolve by hand; nothing was written."
                    % (lineno(masked, blocks[1][1].start()),
                       lineno(masked, first_m.start())), None)
        extras = ", ".join("line %d (v%d)" % (lineno(masked, b[1].start()), b[0])
                           for b in blocks[1:])
        return ("duplicate protocol blocks — %d in this file; the first opens at line %d, "
                "the extras at %s. Only one can be managed; resolve by hand, nothing was "
                "written." % (len(blocks), lineno(masked, blocks[0][1].start()), extras),
                None)
    return None, blocks


def claude_state(root):
    """(status, detail, version)."""
    p = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(p):
        return FAIL, "CLAUDE.md absent — no protocol block, so nothing states the contract", None
    enc = not_utf8(p)
    if enc:
        return WARN, ("CLAUDE.md is not UTF-8 (%s) — this tool will not write into it; a "
                      "UTF-8 block appended here would be unreadable to its own reader" % enc), None
    txt = read_rt(p)
    if txt is None:
        return WARN, "CLAUDE.md is unreadable", None
    problem, blocks = block_problem(txt)
    if problem:
        return WARN, problem, None
    if not blocks:
        if BLOCK_OPEN_RE.search(txt):
            return WARN, ("protocol markers exist only inside a fenced/masked region "
                          "(a code-fence example, or an unterminated fence) — not a live "
                          "block; add the block outside the fence by hand — nothing written"), None
        return FAIL, "CLAUDE.md present but carries no notrest:protocol block", None
    v, _m, c = blocks[0]
    if c is None:
        return WARN, "notrest:protocol block is unterminated (no closing marker)", None
    if v < PROTOCOL_VERSION:
        return WARN, ("notrest:protocol block is v%d; current is v%d — run `establish` to "
                      "replace it in place" % (v, PROTOCOL_VERSION)), v
    return PASS, "notrest:protocol block present at v%d" % v, v


# ── adoption facts (INFO ONLY — never move the exit code) ─────────────────────────────
SHIP_RE = re.compile(r"(\bship(?:s|ped|ping)?\b|\brelease[ds]?\b|\bv\d+\.\d+\.\d+\b)", re.I)
GATE_RE = re.compile(r"(\bgat(?:e|es|ed|ing)\b)", re.I)
CORR_RE = re.compile(r"(\bcorrection\b|\bcorrected\b|\brevert\w*\b|\brolled back\b|"
                     r"\brollback\b|\bwithdraw\w*\b|\bstopped\b|\bnot landed\b)", re.I)
COORD_TAIL, AGENT_TAIL, FLAG_TAIL = 25, 10, 5

LEDGER_LINE_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})Z\]")
SCAFFOLD_MARK = "COORD.md scaffolded by"


def adoption(root):
    out = []
    cp = os.path.join(root, "COORD.md")
    txt = read_text(cp) if os.path.isfile(cp) else None
    if txt is None:
        out.append((INFO, "LEDGER-LINES", "no COORD.md to count"))
    else:
        lines = [ln for ln in txt.splitlines() if LEDGER_LINE_RE.match(ln)]
        real = [ln for ln in lines if SCAFFOLD_MARK not in ln]
        out.append((INFO, "LEDGER-LINES",
                    "%d ledger line(s) beyond the scaffold (%d total)" % (len(real), len(lines))))
        if lines:
            m = LEDGER_LINE_RE.match(lines[-1])
            try:
                stamp = datetime.strptime("%s %s" % (m.group(1), m.group(2)),
                                          "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                hrs = (datetime.now(timezone.utc) - stamp).total_seconds() / 3600.0
                out.append((INFO, "LEDGER-AGE",
                            "newest ledger line %s (%.1fh ago)" % (lines[-1][3:20], hrs)))
            except (ValueError, AttributeError):
                out.append((INFO, "LEDGER-AGE", "newest ledger line carries an unparseable stamp"))
        else:
            out.append((INFO, "LEDGER-AGE", "no stamped ledger lines yet"))
    for name, rel in (("AGENT-LEDGER", "COORD-AGENTS.md"), ("SPEND-LEDGER", "spend/ledger.md")):
        out.append((INFO, name, "%s %s" % (rel, "present"
                                           if os.path.exists(os.path.join(root, rel))
                                           else "absent")))
    return out


NONGIT_WARNS = [
    "self-update is dead — the SessionStart hook's `git pull --ff-only` has no clone to "
    "pull, so the harness cannot update itself here",
    "ship gates are weaker — no commit, no diff, no HEAD-vs-tree check; 'what changed' has "
    "no answer a machine can produce",
    "the trail is not diffable — COORD.md still records what landed, but nothing binds a "
    "ledger line to a revision of the files it describes",
]


# ── subcommands ───────────────────────────────────────────────────────────────────────
def tail_lines(path, cap):
    """The last `cap` ledger lines of a file, oldest first. Missing file → []."""
    txt = read_text(path)
    if txt is None:
        return []
    return [ln for ln in txt.splitlines() if ln.startswith("- ")][-cap:]


def sealed_volumes(root, prefix):
    """How many volumes this ledger has already sealed — the depth of the trail behind
    the tail you are about to read."""
    pat = re.compile(r"^%s-\d{3}\.md$" % re.escape(prefix))
    try:
        return sorted(f for f in os.listdir(root) if pat.match(f))
    except OSError:
        return []


def spend_verdict(root):
    """The spend ledger's own last line, READ not computed. Deliberately never shells to
    spend.py: continuation must stay read-only, deterministic and instant, and a report
    that can exit 4 is a gate, not a packet."""
    txt = read_text(os.path.join(root, "spend", "ledger.md"))
    if txt is None:
        return None
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip() and not ln.startswith("#")]
    return lines[-1] if lines else None


def git_facts(root):
    """(is_repo, head, dirty, subject). A repo with NO COMMITS YET is still a repo — it
    has a dirty count and no HEAD, and reporting it as "not a git repo" would be a plain
    lie to the successor about what the project is."""
    if git_toplevel(root) != root:
        return False, None, None, None
    rc, head = git(root, "rev-parse", "--short", "HEAD")
    rc2, status = git(root, "status", "--porcelain")
    rc3, subj = git(root, "log", "-1", "--pretty=%s")
    dirty = len([l for l in status.splitlines() if l.strip()]) if rc2 == 0 else None
    return True, (head if rc == 0 and head else None), dirty, (subj if rc3 == 0 and subj else None)


def packet(root):
    """Everything a fresh seat needs to continue, in one gulp. NO CLOCK: every timestamp
    here comes off a file, so the same estate yields the same packet twice."""
    coord = tail_lines(os.path.join(root, "COORD.md"), COORD_TAIL)
    agents = tail_lines(os.path.join(root, "COORD-AGENTS.md"), AGENT_TAIL)
    all_coord = tail_lines(os.path.join(root, "COORD.md"), 10 ** 9)
    flags = {"ship": [], "gate": [], "correction": []}
    for ln in all_coord:
        body = ln
        if CORR_RE.search(body):
            flags["correction"].append(ln)
        elif SHIP_RE.search(body):
            flags["ship"].append(ln)
        elif GATE_RE.search(body):
            flags["gate"].append(ln)
    try:
        briefs = len([f for f in os.listdir(os.path.join(root, "briefs"))
                      if f.endswith(".md")])
    except OSError:
        briefs = 0
    is_repo, head, dirty, subj = git_facts(root)
    cs, _cd = coord_state(root)
    ks, _kd, ver = claude_state(root)
    return {
        "root": root,
        "established": cs == PASS and ks == PASS,
        "coord_state": cs,
        "claude_block": ks,
        "protocol_version": ver,
        "coord_lines_shown": len(coord),
        "coord_tail": coord,
        "coord_sealed_volumes": len(sealed_volumes(root, "COORD")),
        "agents_tail": agents,
        "agents_sealed_volumes": len(sealed_volumes(root, "COORD-AGENTS")),
        "newest_ships": flags["ship"][-FLAG_TAIL:],
        "newest_gates": flags["gate"][-FLAG_TAIL:],
        "newest_corrections": flags["correction"][-FLAG_TAIL:],
        "briefs": briefs,
        "spend_last_line": spend_verdict(root),
        "git_repo": is_repo,
        "git_head": head,
        "git_dirty_files": dirty,
        "git_last_subject": subj,
    }


def cmd_continuation(args):
    """The successor's one-gulp read of where the build stands. Read-only, always."""
    root, err = resolve_root(args.root)
    if err:
        sys.stderr.write("notrest: %s\n" % err)
        return EXIT_USAGE
    p = packet(root)
    if not p["established"]:
        if args.json:
            print(json.dumps({"root": root, "established": False}, indent=1, sort_keys=True))
        else:
            print("notrest: NOT ESTABLISHED — %s carries no continuable estate. "
                  "Run `/notrest establish` first." % root)
        return EXIT_NONE
    if args.json:
        print(json.dumps(p, indent=1, sort_keys=True))
        return EXIT_OK
    print("notrest continuation — %s" % root)
    print("  ESTABLISHED · protocol v%s · COORD volumes sealed: %d · agent volumes sealed: %d"
          % (p["protocol_version"], p["coord_sealed_volumes"], p["agents_sealed_volumes"]))
    if p["git_repo"] and p["git_head"]:
        print("  git %s · %d dirty file(s) · last commit: %s"
              % (p["git_head"], p["git_dirty_files"], p["git_last_subject"]))
    elif p["git_repo"]:
        print("  git repo with no commits yet · %s dirty file(s) · no HEAD to compare against"
              % p["git_dirty_files"])
    else:
        print("  not a git repo — no HEAD, no diff; the ledger is the whole trail here")
    print("  briefs banked: %d%s" % (p["briefs"],
          ("" if p["spend_last_line"] is None else "\n  spend (last line): %s" % p["spend_last_line"])))
    for label, key in (("NEWEST SHIPS", "newest_ships"), ("NEWEST GATES", "newest_gates"),
                       ("NEWEST CORRECTIONS", "newest_corrections")):
        if p[key]:
            print("\n%s" % label)
            for ln in p[key]:
                print("  %s" % ln)
    print("\nCOORD TAIL (last %d)" % p["coord_lines_shown"])
    for ln in p["coord_tail"]:
        print("  %s" % ln)
    if p["agents_tail"]:
        print("\nAGENT TAIL (last %d)" % len(p["agents_tail"]))
        for ln in p["agents_tail"]:
            print("  %s" % ln)
    if seed_pulse(root):
        print("\n  pulse: refreshing in the background → pulse/pulse.json + pulse/*.txt "
              "(read them, do not wait on them)")
    print("\nnotrest: CONTINUABLE — %s (exit 0)" % root)
    return EXIT_OK


def emit(status, name, detail):
    print("  %-4s  %-13s — %s" % (status, name, detail))


def verdict(code, root, extra=""):
    word = {EXIT_OK: "ESTABLISHED", EXIT_PARTIAL: "PARTIALLY ESTABLISHED",
            EXIT_NONE: "NOT ESTABLISHED"}[code]
    print("notrest: %s — %s%s (exit %d)" % (word, root, extra, code))


def grade(states):
    if all(s == PASS for s in states):
        return EXIT_OK
    if any(s in (PASS, WARN) for s in states):
        return EXIT_PARTIAL
    return EXIT_NONE


def cmd_check(args):
    root, err = resolve_root(args.root)
    if err:
        sys.stderr.write("notrest: %s\n" % err)
        return EXIT_USAGE
    print("notrest check — %s" % root)
    cs, cd = coord_state(root)
    ks, kd, _v = claude_state(root)
    emit(cs, "COORD", cd)
    emit(ks, "CLAUDE-BLOCK", kd)
    emit(INFO, "GIT", "git repo — every estate hook operates at full strength"
         if git_toplevel(root) == root
         else "NOT a git repo — estate surfaces are limited (see /notrest, non-git section)")
    for s, n, d in adoption(root):
        emit(s, n, d)
    code = grade([cs, ks])
    verdict(code, root)
    return code


def write_claude(root, kp, failures):
    """The CLAUDE.md half of establish. Returns the list of 'wrote' descriptions."""
    wrote = []
    block = protocol_block()
    target = contain(root, kp)
    if target is None:
        emit(FAIL, "CLAUDE-BLOCK", "CLAUDE.md resolves outside %s — refusing to write "
                                   "through it" % root)
        failures.append("CLAUDE.md")
        return wrote
    if not os.path.isfile(target):
        try:
            atomic_write(target, "# CLAUDE.md — project foundation\n\n" + block)
            wrote.append("CLAUDE.md")
            emit(PASS, "CLAUDE-BLOCK", "CLAUDE.md created with the v%d protocol block"
                 % PROTOCOL_VERSION)
        except OSError as exc:
            emit(FAIL, "CLAUDE-BLOCK", "could not write CLAUDE.md: %s" % exc)
            failures.append("CLAUDE.md")
        return wrote

    enc = not_utf8(target)
    if enc:
        emit(WARN, "CLAUDE-BLOCK", "CLAUDE.md is not UTF-8 (%s) — nothing written. A UTF-8 "
             "block appended here would be mojibake to its own reader, and the next "
             "round-trip read would raise." % enc)
        return wrote
    txt = read_rt(target)
    if txt is None:
        emit(FAIL, "CLAUDE-BLOCK", "CLAUDE.md is unreadable — leaving it alone")
        failures.append("CLAUDE.md")
        return wrote
    problem, blocks = block_problem(txt)
    if problem:
        emit(WARN, "CLAUDE-BLOCK", problem)
        return wrote
    try:
        if not blocks:
            # BELT AND BRACES (2026-08-02 round 2): the masked search found nothing, so we
            # are about to APPEND. If the raw text carries a line-anchored opener anyway,
            # some masking rule swallowed a real block — and appending would add one more
            # every run, without bound. Never append past that disagreement.
            if BLOCK_OPEN_RE.search(txt):
                emit(WARN, "CLAUDE-BLOCK",
                     "protocol markers exist only inside a fenced/masked region (a code-fence "
                     "example, or an unterminated fence) — not a live block; add the block "
                     "outside the fence by hand — nothing written")
                return wrote
            sep = "" if txt.endswith("\n\n") else ("\n" if txt.endswith("\n") else "\n\n")
            atomic_write(target, txt + sep + block, roundtrip=True)
            wrote.append("CLAUDE.md (block appended)")
            emit(PASS, "CLAUDE-BLOCK", "v%d protocol block appended — existing content "
                 "untouched, byte for byte" % PROTOCOL_VERSION)
            return wrote
        found, m, c = blocks[0]
        if c is None:
            emit(WARN, "CLAUDE-BLOCK", "block opens at v%d but never closes — left alone; "
                 "close the marker by hand, then re-run" % found)
            return wrote
        if found >= PROTOCOL_VERSION:
            emit(INFO, "CLAUDE-BLOCK", "v%d protocol block already current — left untouched"
                 % found)
            return wrote

        # An UPGRADE replaces the managed span, so anything hand-written inside the
        # markers would vanish silently. Compare against the canonical body of the version
        # found and bank a copy when they differ; an UNKNOWN version can never be proven
        # untouched, so it is treated as edited.
        old_body = txt[m.end():c.start()].strip("\r\n")
        canon = CANONICAL_BODIES.get(found)
        if canon is None or old_body.strip() != canon.strip():
            bak = target + ".notrest-v%d.bak" % found
            try:
                atomic_write(bak, old_body + "\n", roundtrip=True)
                emit(WARN, "CLAUDE-BLOCK", "in-block edits discarded on the v%d -> v%d "
                     "upgrade — the old body was saved to %s"
                     % (found, PROTOCOL_VERSION, os.path.basename(bak)))
            except OSError as exc:
                emit(WARN, "CLAUDE-BLOCK", "in-block edits found but the backup failed "
                     "(%s) — the block was left alone" % exc)
                return wrote
        atomic_write(target, txt[:m.start()] + block.rstrip("\n") + txt[c.end():],
                     roundtrip=True)
        wrote.append("CLAUDE.md (block v%d -> v%d)" % (found, PROTOCOL_VERSION))
        emit(PASS, "CLAUDE-BLOCK", "protocol block replaced in place v%d -> v%d — nothing "
             "outside the markers changed" % (found, PROTOCOL_VERSION))
    except OSError as exc:
        emit(FAIL, "CLAUDE-BLOCK", "could not write CLAUDE.md: %s" % exc)
        failures.append("CLAUDE.md")
    return wrote


def seed_pulse(root):
    """Fire the background pulse refresher, DETACHED. The owner's order is that the
    readings exist from the moment a project is established — "created immediately at
    /notrest" — so establishment and continuation both kick it and neither waits. The
    hook debounces itself; a failure here is silent by design and never blocks the verb."""
    hook = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "..", "hooks", "estate-pulse.sh")
    hook = os.path.realpath(hook)
    if not os.path.isfile(hook):
        return False
    try:
        subprocess.Popen(["bash", hook, root, "establish"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except (OSError, ValueError):
        return False


def cmd_establish(args):
    root, err = resolve_root(args.root)
    if err:
        sys.stderr.write("notrest: %s\n" % err)
        return EXIT_USAGE
    print("notrest establish — %s" % root)
    wrote, failures = [], []

    # ── 1. COORD.md — the ledger. An existing ledger is the project's own history and is
    # never rewritten; an EMPTY one is treated as absent, because a zero-byte file is not
    # a ledger anybody can read.
    cp = os.path.join(root, "COORD.md")
    target = contain(root, cp)
    if target is None:
        emit(FAIL, "COORD", "COORD.md resolves outside %s — refusing to write through it"
             % root)
        failures.append("COORD.md")
    elif os.path.isfile(target) and os.path.getsize(target) > 0:
        emit(INFO, "COORD", "COORD.md already present — left untouched")
    else:
        try:
            atomic_write(target, COORD_SCAFFOLD + "- [%s] [notrest] COORD.md scaffolded by "
                         "/notrest establish\n" % now())
            wrote.append("COORD.md")
            emit(PASS, "COORD", "COORD.md written (scaffold + one ledger line)")
        except OSError as exc:
            emit(FAIL, "COORD", "could not write COORD.md: %s" % exc)
            failures.append("COORD.md")

    # ── 2. CLAUDE.md — the protocol block.
    wrote += write_claude(root, os.path.join(root, "CLAUDE.md"), failures)

    # ── 3. git. Never initialized uninvited: `git init` changes what a directory IS, and
    # that is the owner's decision, not a side effect of establishing a ledger.
    if git_toplevel(root) == root:
        emit(INFO, "GIT", "git repo — every estate hook operates at full strength")
    elif args.git_init:
        rc, _out = git(root, "init")
        if rc == 0:
            emit(PASS, "GIT", "git init run (--git-init) — nothing added, nothing committed")
        else:
            emit(FAIL, "GIT", "git init failed — leaving the directory as it was")
    else:
        emit(INFO, "GIT", "NOT a git repo — establishment still holds; the hooks honor a "
                          "COORD.md root, so the ledger and agent index work here")
        for w in NONGIT_WARNS:
            emit(WARN, "GIT-DEGRADED", w)
        emit(INFO, "GIT", "`establish --git-init` runs `git init` (and nothing else) — "
                          "opt-in only, never automatic")

    # ── the verdict is re-read from disk, and the per-surface STATE is re-emitted beside
    # it: a run that ends in 5 must say WHICH surface is unfinished, on the same screen.
    cs, cd = coord_state(root)
    ks, kd, _v = claude_state(root)
    emit(cs, "COORD", cd)
    emit(ks, "CLAUDE-BLOCK", kd)
    code = grade([cs, ks])
    if seed_pulse(root):
        emit(INFO, "PULSE", "instrument readings seeding in the background → pulse/*.txt "
                            "+ pulse/pulse.json (derived, disposable, refreshed on every "
                            "swarm stop and session end)")
    if failures:
        tail = " · wrote: nothing (writes failed: %s)" % ", ".join(sorted(set(failures)))
    else:
        tail = " · wrote: %s" % (", ".join(wrote) if wrote
                                 else "nothing (already established)")
    verdict(code, root, tail)
    return code


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="establish.py",
        description="Establish the notrest harness in a project, or check whether it is.")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="read-only: is the harness established here?")
    c.add_argument("--root", help="project root (default: git root, else a marked cwd)")
    e = sub.add_parser("establish", help="write the establishment surfaces (idempotent)")
    e.add_argument("--root", help="project root (default: git root, else a marked cwd)")
    e.add_argument("--git-init", action="store_true",
                   help="also run `git init` (and nothing else) when the root is not a repo")
    n = sub.add_parser("continuation",
                       help="read-only: the packet a successor seat needs to continue")
    n.add_argument("--root", help="project root (default: git root, else a marked cwd)")
    n.add_argument("--json", action="store_true", help="machine output, stable key order")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "establish":
        return cmd_establish(args)
    if args.cmd == "continuation":
        return cmd_continuation(args)
    ap.print_usage(sys.stderr)
    sys.stderr.write("establish.py: expected 'check', 'establish' or 'continuation'\n")
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
