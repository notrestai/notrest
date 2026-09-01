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
  - The root is refused rather than guessed. $HOME is never a project, a dot-directory
    directly under $HOME (~/.codex, ~/.claude — per-machine configuration) is refused on
    both its named and resolved path, a subdirectory of a git repo is never a root (every
    hook would resolve to the toplevel instead), and a directory with no project marker
    is refused outright.
  - RUNTIME-EXPLICIT: Codex writes AGENTS.md, Claude writes CLAUDE.md, and `both` writes
    both. Auto-detection is conservative and can always be overridden with `--surface`.
    HOST SIGNALS DECIDE THE RUNTIME (owner ruling, 4.5): files may only narrow WITHIN a
    detected host, never pick one; no signal at all means claude, the historical default,
    now actually enforced. And under `auto` a foundation file is never CREATED for a host
    nothing detected — reads still grade whatever files exist.
  - A FILE'S MODE IS PART OF THE FILE. Every rewrite carries the target's mode across the
    atomic replace, and a target its owner marked READ-ONLY is refused, not rewritten.
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
PROJECT_MARKERS = ("AGENTS.md", "CLAUDE.md", "README.md", "package.json", "pyproject.toml",
                   "COORD.md")

PROTOCOL_VERSION = 2
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

BODY_V2 = """## notrest protocol

- **Fable discipline** — ORIENT -> PROBE -> ACT -> PROVE -> BANK. Probe the live
  system before reasoning; a done/works/fixed claim needs in-transcript evidence
  (exit code, diff, status) or it is labeled `[unverified]`; bank state before stopping.
  Full contract: `/notrest:fable-mode`.
- **Runtime-explicit offload rule** — delegate only when the user asks or the host policy
  permits it. Claude lanes set model `\"opus\"` explicitly and never use
  `subagent_type: \"fork\"`. Codex lanes set model `\"gpt-5.6-sol\"` explicitly and,
  because a model override cannot use a full-history inherited fork, use
  `fork_turns: \"none\"` or a bounded recent-turn fork. Never silently substitute one
  runtime's model for the other. A build keeps one persistent builder lane per domain and
  resumes it for feedback.
- **Enforcement honesty** — Claude lifecycle hooks may enforce and receipt laws. Codex
  v4.3 has no equivalent plugin hook surface: `AGENTS.md`, the selected skill, Doctor,
  Eval, and consumer-side evidence carry the law. Never claim a hook ran on Codex.
- **COORD law** — one honest ledger line per substantive prompt when its work lands:
  `ask -> landed | evidence`. `COORD.md` is append-only and is never compacted: at
  ~500 lines it seals whole as `COORD-<NNN>.md` and a fresh volume opens.
- **Close** a working session with `/sessionend`. **Drift check:** `/notrest check`."""

CANONICAL_BODIES = {1: BODY_V1, 2: BODY_V2}

# ── STRICTNESS REGRESSION GUARD (S57).
#
# An upgrade REPLACES the managed span. The existing net catches HAND-EDITS inside the
# markers and banks them — but it does not catch the case where the CANONICAL body of the
# older version asserts something STRICTER than the newer one. That block is "untouched",
# so it takes the safe-to-replace path silently, and a rule an estate relies on is
# weakened by an upgrade nobody read.
#
# The live instance: v1 says the offload rule is UNCONDITIONAL ("every spawned lane sets
# model opus ... omitting the model is a violation, not a default"). v2 makes delegation
# CONDITIONAL ("delegate only when the user asks or the host policy permits it"). An
# estate that adopted v1 deliberately, and enforces it with a session hook, would have
# that override quietly relaxed by `establish`.
#
# Each entry is (label, pattern). A regression is: PRESENT in the body being replaced and
# ABSENT from the body replacing it. The guard is DECLARATIVE on purpose — it does not try
# to reason about what "stricter" means, because a tool that infers rule semantics is a
# tool that will infer them wrongly.
#
# ⛔ ITS BOUND, STATED WHERE IT IS IMPLEMENTED: this guard is only as complete as this
# list. A future clause that is stricter in some way nobody enumerated here is NOT
# protected, and this comment is the only thing that says so.
# ⛔ MEMBERSHIP FOLLOWS **STATUS**, NOT **LAYOUT** (Architecture Master, 2026-08-26).
#
# A clause earns a row here by being OWNER-RATIFIED, and it is enumerated by RULE
# IDENTITY. It is never protected by happening to share a block with a clause that
# already has a row. That accident is how the width law below was protected before this
# entry existed, and:
#
#   a rule at the estate's strongest status depending on a neighbour's sentence for its
#   protection is an accident wearing a guarantee's clothes.
#
# So the question when a clause is proposed for this list is NOT "is it strict?" and NOT
# "does it sit near something we already guard?" — it is "what status did the owner give
# it?". Declining to protect an owner-ratified rule would be an owner's call to make;
# protecting one is not.
#
# This rides ALONGSIDE the completeness note above, and they say different things: that
# one says the list can be SHORT; this one says how a clause EARNS ITS ROW.
STRICTER_CLAUSES = (
    ("unconditional offload rule", re.compile(r"Offload HARD RULE", re.I)),
    # Owner-ratified 2026-08-12 (R73 + R73-A). Keyed on the rule's IDENTITY and
    # deliberately not on its date or rule ids, so a re-ratification does not silently
    # drop the protection. Matched against the clause as it is actually written inside
    # the markers, not a hand-typed approximation of it.
    ("owner-ratified width law", re.compile(r"Width law\s*\(OWNER-RATIFIED", re.I)),
)


def strictness_regressions(old_body, new_body):
    """Clauses asserted by `old_body` that `new_body` drops. Empty list = safe."""
    return [label for label, pat in STRICTER_CLAUSES
            if pat.search(old_body or "") and not pat.search(new_body or "")]

SURFACE_FILES = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}
SURFACE_LABELS = {"claude": "CLAUDE-BLOCK", "codex": "AGENTS-BLOCK"}


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


def readonly_refusal(path):
    """A refusal message when `path` exists and its owner marked it read-only, else None.

    `os.replace` needs the DIRECTORY's write bit, not the file's, so the atomic path would
    cheerfully overwrite a file a plain `open(w)` cannot touch. The fixture used to
    celebrate that as "atomic write wins". Winning there IS the defect (F4): read-only is
    an instruction from the file's owner, and this tool is a guest in their project."""
    try:
        mode = os.stat(path).st_mode & 0o7777
    except OSError:
        return None
    if os.access(path, os.W_OK):
        return None
    return ("%s is read-only (mode 0%03o) — refusing to rewrite a file its owner marked "
            "read-only. `chmod u+w %s` and re-run if the estate should write here."
            % (os.path.basename(path), mode, os.path.basename(path)))


def atomic_write(path, text, roundtrip=False):
    """tmp file in the SAME directory + os.replace — a reader never sees a half-file, and
    a crash mid-write leaves the original intact. `roundtrip` preserves the byte and
    line-ending fidelity of a file we did not author.

    MODE IS PART OF THE FILE (F4). `mkstemp` creates 0600, so a bare tmp+replace silently
    re-permissioned every foundation file it rewrote — somebody else's 0644 CLAUDE.md came
    back 0600 and nothing said so. The target's mode is stat'd first and stamped onto the
    tmp BEFORE the replace, and a read-only target is refused rather than rewritten."""
    d = os.path.dirname(path) or "."
    refusal = readonly_refusal(path)
    if refusal:
        raise PermissionError(refusal)
    try:
        mode = os.stat(path).st_mode & 0o7777
    except OSError:
        # A file we are CREATING: mkstemp's 0600 would make every fresh foundation
        # owner-only — a CLAUDE.md a teammate cannot read (review round, 2026-09-01).
        # Honor the process umask exactly as open(w) would have.
        um = os.umask(0); os.umask(um)
        mode = 0o666 & ~um
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".notrest-", suffix=".tmp")
    try:
        if roundtrip:
            fh = os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape", newline="")
        else:
            fh = os.fdopen(fd, "w", encoding="utf-8")
        with fh:
            fh.write(text)
        if mode is not None:
            os.chmod(tmp, mode)
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


def in_root(root, rel):
    """The realpath of `root/rel` when it stays inside the root, else None.

    EVERY ESTATE READ GOES THROUGH HERE (refuter RA-2). Round 1 contained the foundation
    read and stopped there — so an escaping COORD.md still let `check` grade another
    project's ledger PASS, and handed `continuation` a stranger's trail as this project's
    own history. Containment is not a property of one file; it is what "this project"
    means."""
    return contain(root, os.path.join(root, rel))


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


# ── runtime surface ───────────────────────────────────────────────────────────────────
#
# ⛔ HOST SIGNALS DECIDE THE RUNTIME (owner ruling, 4.5 docket item 1, option (a)).
#
# The pre-4.5 Claude branch probed CLAUDE_PLUGIN_ROOT / CLAUDE_CONFIG_DIR. Neither is
# exported by a real Claude Code session, so THE BRANCH WAS DEAD and the file tie-break
# governed every `auto` run: a Claude session in a repo carrying an upstream AGENTS.md and
# no CLAUDE.md established the WRONG runtime's foundation and exited 0 ESTABLISHED
# (confirmed live at the v4.3.0 ship). A detector whose evidence does not exist is not
# conservative — it is a coin flip wearing a rule's clothes.
#
# CLAUDE_SIGNAL_* below are what `env | grep ^CLAUDE` ACTUALLY SHOWS in a Claude Code
# session, probed on the live host 2026-08-31: CLAUDECODE=1, CLAUDE_PID, and a
# CLAUDE_CODE_* family (ENTRYPOINT, SESSION_ID, …). Any one of them is the host saying so.
CLAUDE_SIGNAL_VARS = ("CLAUDECODE", "CLAUDE_PID")
CLAUDE_SIGNAL_PREFIX = "CLAUDE_CODE_"
# ⚠️ UNVERIFIED FROM HERE, and labelled rather than dressed up: no Codex session was
# available to probe from the host that made this change, so these keep the names the 4.3
# adapter shipped with. If a real Codex session exports neither, this branch is dead the
# way the Claude branch was — but the failure mode is now benign: no signal falls to the
# claude default, and the write guard below refuses to CREATE an AGENTS.md nobody detected
# a host for, so the tool asks for `--surface codex` instead of writing the wrong file.
CODEX_SIGNAL_VARS = ("CODEX_THREAD_ID", "CODEX_SANDBOX")


def host_signals(env=None):
    """(claude, codex) — what the ENVIRONMENT says about which runtime is running us."""
    env = os.environ if env is None else env
    claude = (any(env.get(v) for v in CLAUDE_SIGNAL_VARS)
              or any(k.startswith(CLAUDE_SIGNAL_PREFIX) and env.get(k) for k in env))
    codex = any(env.get(v) for v in CODEX_SIGNAL_VARS)
    return bool(claude), bool(codex)


SURFACE_ASK = ("pass --surface codex|claude|both")


def resolve_surface(requested, root=None, writing=True):
    """(surface, error) — the whole surface law in one place.

    Explicit `--surface` always wins, unchanged. Otherwise:

    · BOTH families signal → CLAUDE-PREFERRED, and the files may only WIDEN to `both`
      when both foundations already exist. They may NEVER take the surface to codex-only.
      (Refuter RA-1: CODEX_THREAD_ID is exported by a Codex session and INHERITED by
      everything that session launches, so a Claude seat started from a Codex shell wears
      a stale codex signal for its whole life. "Narrow to the file we see" then handed an
      AGENTS.md-only repo straight back to the codex surface — F2 resurrected entire, by
      the very mechanism meant to fix it. A signal that cannot go stale can decide; one
      that can, cannot.)
    · ONE family signals → that runtime.
    · NO signal at all → the files may only answer a question the environment could not:
      both foundations present means `both` (upgrade what is there, create nothing);
      nothing present means the stated claude default; and AGENTS.md ALONE is a REFUSAL,
      because writing CLAUDE.md over a codex-shaped repo is the same wrong-runtime write
      the guard already refuses in the other direction (refuter RA-3 — the guard was
      one-directional). The tool asks instead of guessing.

    Existence is probed THROUGH containment: a foundation that resolves outside the root
    is not evidence about this project (RA-2)."""
    if requested and requested != "auto":
        return requested, None, None
    claude, codex = host_signals()
    has_agents = bool(root) and os.path.isfile(contain(root, os.path.join(root, "AGENTS.md")) or os.devnull)
    has_claude = bool(root) and os.path.isfile(contain(root, os.path.join(root, "CLAUDE.md")) or os.devnull)
    if claude and codex:
        return ("both" if (has_agents and has_claude) else "claude"), None, None
    if codex:
        return "codex", None, None
    if claude:
        return "claude", None, None
    if has_agents and has_claude:
        return "both", None, None
    if has_agents:
        if not writing:
            # REVIEW-THE-FIX verdict (2026-09-01), followed by the seat: the refusal is a
            # WRITE-safety rule — check and continuation create nothing, so they grade
            # what exists and hand the ambiguity to the seat as a WARN instead of taking
            # the judgment away (the file's own report/judge split). If the UNVERIFIED
            # codex vars are wrong, a read verb degrades to a report, never to silence.
            # "Grading every foundation present" means the ones that EXIST: an
            # AGENTS-only estate is graded on its codex surface — an absent CLAUDE.md
            # is not a failure of a repo that never claimed one.
            return "codex", None, ("nothing in this environment says which runtime is "
                                   "running — grading the foundation present, AGENTS.md "
                                   "(pass --surface to pin it)")
        return None, ("nothing in this environment says which runtime is running (looked "
                      "for: %s, %s*, %s), and %s carries AGENTS.md but no CLAUDE.md — "
                      "refusing to guess, because establishing the wrong runtime's "
                      "foundation is the defect this rule exists to prevent. Nothing was "
                      "written: %s."
                      % (", ".join(CLAUDE_SIGNAL_VARS), CLAUDE_SIGNAL_PREFIX,
                         ", ".join(CODEX_SIGNAL_VARS), root, SURFACE_ASK)), None
    return "claude", None, None


def detect_surface(requested, root=None):
    """The surface alone, or None when the environment must be asked (see
    `resolve_surface`, which is what every command in this file calls). None is returned
    rather than a guess on purpose: a caller that ignores it raises on the next line
    instead of quietly writing the wrong runtime's file."""
    return resolve_surface(requested, root)[0]  # writing default: the safe side


def may_create_surface(surface, requested):
    """(allowed, why_not) — THE WRITE GUARD (ruling option (b), folded in).

    `establish` under `auto` never CREATES a foundation file for a host nothing detected.
    Reads and checks still grade whatever files exist (read-only honesty), and an explicit
    `--surface` always wins. The no-signal default may still create CLAUDE.md — that IS
    the default, stated in the CLI help since 4.0.

    Today `detect_surface` cannot route an undetected host here at all. The guard is kept
    anyway, and asserted directly by the fixture, because an invariant that holds only
    while its caller stays correct is not an invariant — it is a coincidence."""
    if requested and requested != "auto":
        return True, ""
    if surface != "codex":
        return True, ""
    _claude, codex = host_signals()
    if codex:
        return True, ""
    return False, ("nothing in this environment says a Codex session is running (looked "
                   "for: %s) — refusing to CREATE %s on a hunch. Re-run with `--surface "
                   "codex` (or `--surface both`) if that is what you mean; nothing was "
                   "written." % (", ".join(CODEX_SIGNAL_VARS), SURFACE_FILES["codex"]))


def selected_surfaces(surface):
    return ("claude", "codex") if surface == "both" else (surface,)


# ── root resolution ───────────────────────────────────────────────────────────────────
def same_dir(a, b):
    """Inode identity, guarded for existence — a STRING compare is not an identity
    compare. On a case-insensitive volume (macOS default) `/users/me` and `/Users/me` are
    ONE directory spelled two ways, and the whole home-refusal family was string compares:
    `--root /users/me` walked straight past $HOME, past Desktop/Documents/Downloads and
    past the dot-dir refusal. Pre-existing since 4.0; found by the 2026-08-21 review
    lane, docketed as 4.4 item 4."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def account_homes():
    """Every directory that is A HOME for this run — the ACCOUNT home from the password
    database ALWAYS, plus the $HOME-derived one when HOME is set.

    ⛔ Deriving the home from $HOME ALONE meant that exporting HOME elsewhere — a test
    harness, a launchd job, a container, a plain `env HOME=/tmp/x …` — left the REAL
    account home entirely unprotected, and that is precisely the directory whose CLAUDE.md
    every session on the machine loads. The refuter reached it by setting HOME to a
    sandbox (RA-P). $HOME is a hint the environment can move; the password database is
    the account. Both are refused, so neither can be used to unprotect the other."""
    out = []
    try:
        import pwd
        out.append(os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir))
    except Exception:
        pass
    if os.environ.get("HOME"):
        h = os.path.realpath(os.path.expanduser("~"))
        if h not in out:
            out.append(h)
    if not out:
        out.append(os.path.realpath(os.path.expanduser("~")))
    return out


def resolve_root(explicit):
    """(root, error). --root wins; else the git root; else the cwd IF it looks like a
    project; else a refusal that NAMES what it looked for. Always realpath'd."""
    if explicit:
        # lex keeps the path AS NAMED (symlinks unresolved): the dot-dir refusal below
        # must hold for ~/.codex even when its realpath leaves HOME (dotfiles managers).
        lex = os.path.normpath(os.path.abspath(os.path.expanduser(explicit)))
        r = os.path.realpath(lex)
        if not os.path.isdir(r):
            return None, "--root %s is not a directory" % explicit
    else:
        top = git_toplevel(os.getcwd())
        if top:
            r = lex = top
        else:
            env_pwd = os.environ.get("PWD", "")
            lex = (os.path.normpath(env_pwd)
                   if env_pwd and os.path.realpath(env_pwd) == os.path.realpath(os.getcwd())
                   else os.path.normpath(os.getcwd()))
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
    # HOME="" (set but empty — launchd/CI shells) made expanduser("~") return "/" and
    # silently disarmed every refusal below (review-the-fix round, 2026-08-21); HOME
    # pointed ELSEWHERE left the real account home unprotected (refuter RA-P). Both are
    # answered the same way: every home this run has is refused, not just the one $HOME
    # currently names.
    homes = account_homes()
    for home in homes:
        if r == home or same_dir(r, home):
            return None, ("%s is your HOME directory, not a project — refusing. A "
                          "CLAUDE.md here is loaded into every session on this machine; "
                          "establish inside the project itself." % r)
    if r == os.path.dirname(r) or same_dir(r, os.path.dirname(r)):
        return None, "%s is a filesystem root, not a project — refusing." % r
    for home in homes:
        for wk in ("Desktop", "Documents", "Downloads"):
            if r == os.path.join(home, wk) or same_dir(r, os.path.join(home, wk)):
                return None, ("%s is a well-known home folder, not a project — refusing. "
                              "Its SUBdirectories are ordinary projects; establish in the "
                              "one you mean." % r)

    # A dot-directory directly under $HOME is per-machine configuration territory:
    # ~/.codex/AGENTS.md and ~/.claude/CLAUDE.md are loaded into every session of their
    # runtimes, so establishing one is the $HOME defect one level down — and the rule
    # holds for the path AS NAMED as well as its realpath, because ~/.codex symlinked
    # into a dotfiles tree is still ~/.codex to every tool that loads it. Found by the
    # 2026-08-21 refuter rounds (F1 + review-the-fix).
    # The PARENT is realpath'd (so /var-vs-/private/var aliasing or a symlinked $HOME
    # cannot dodge the compare) while the LEAF stays as named — the leaf's own symlink
    # is exactly what must not be followed before judging it.
    # The PARENT compare is inode identity (4.4 docket item 4); the LEAF stays lexical,
    # AS NAMED — the leaf's own symlink is exactly what must not be followed before
    # judging it, and ".codex" is ".codex" however the volume folds its case.
    def _dot_under_home(p):
        parent = os.path.dirname(p)
        return (any(os.path.realpath(parent) == home or same_dir(parent, home)
                    for home in homes)
                and os.path.basename(p).startswith("."))
    for cand in (r, lex):
        if _dot_under_home(cand):
            return None, ("%s is a dot-directory directly under your HOME — refused: "
                          "these are per-machine configuration territory, and a "
                          "foundation file here is loaded into every session on this "
                          "machine. If this really is a project, establish a "
                          "subdirectory of it, or house it outside the leading-dot "
                          "namespace." % cand)

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
    p = in_root(root, "COORD.md")
    if p is None:
        return FAIL, ("COORD.md resolves outside %s — refusing to READ a ledger from "
                      "outside the root. A project's history is its own; grading this "
                      "estate on another project's trail is a false report" % root)
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


def foundation_state(root, surface):
    """(status, detail, version) for one runtime foundation.

    THE REPORT IS CONTAINED THE WAY THE WRITERS ARE (F3). Write containment always held,
    but this reader followed an escaping symlink and graded a file OUTSIDE the estate —
    so `check` could print PASS, and `establish` ESTABLISHED exit 0, off a foundation the
    project does not own. An escape is a FAIL finding, never a PASS read from outside."""
    filename = SURFACE_FILES[surface]
    p = contain(root, os.path.join(root, filename))
    if p is None:
        return FAIL, ("%s resolves outside %s — refusing to READ a foundation from "
                      "outside the root; a PASS asserted from a file this project does "
                      "not own is a false report" % (filename, root)), None
    if not os.path.isfile(p):
        return FAIL, "%s absent — no protocol block, so nothing states the contract" % filename, None
    enc = not_utf8(p)
    if enc:
        return WARN, ("%s is not UTF-8 (%s) — this tool will not write into it; a "
                      "UTF-8 block appended here would be unreadable to its own reader"
                      % (filename, enc)), None
    txt = read_rt(p)
    if txt is None:
        return WARN, "%s is unreadable" % filename, None
    problem, blocks = block_problem(txt)
    if problem:
        return WARN, problem, None
    if not blocks:
        if BLOCK_OPEN_RE.search(txt):
            return WARN, ("protocol markers exist only inside a fenced/masked region "
                          "(a code-fence example, or an unterminated fence) — not a live "
                          "block; add the block outside the fence by hand — nothing written"), None
        return FAIL, "%s present but carries no notrest:protocol block" % filename, None
    v, _m, c = blocks[0]
    if c is None:
        return WARN, "notrest:protocol block is unterminated (no closing marker)", None
    if v < PROTOCOL_VERSION:
        return WARN, ("notrest:protocol block is v%d; current is v%d — run `establish` to "
                      "replace it in place" % (v, PROTOCOL_VERSION)), v
    return PASS, "notrest:protocol block present at v%d" % v, v


def claude_state(root):
    """Compatibility alias for callers outside this file."""
    return foundation_state(root, "claude")


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
    cp = in_root(root, "COORD.md")
    if cp is None:
        out.append((INFO, "LEDGER-LINES",
                    "COORD.md resolves outside the root — not read, not counted"))
        cp = None
    txt = read_text(cp) if cp and os.path.isfile(cp) else None
    if txt is None:
        if cp is not None:
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
        p = in_root(root, rel)
        out.append((INFO, name, "%s %s" % (rel, "resolves outside the root — not read"
                                           if p is None
                                           else ("present" if os.path.exists(p) else "absent"))))
    return out


NONGIT_WARNS = [
    "automatic self-update is unavailable — there is no project clone to pull from",
    "ship gates are weaker — no commit, no diff, no HEAD-vs-tree check; 'what changed' has "
    "no answer a machine can produce",
    "the trail is not diffable — COORD.md still records what landed, but nothing binds a "
    "ledger line to a revision of the files it describes",
]


# ── subcommands ───────────────────────────────────────────────────────────────────────
def tail_lines(path, cap):
    """The last `cap` ledger lines of a file, oldest first. Missing file → []. A None
    path is an ESCAPING one (in_root refused it) and reads as empty — never as somebody
    else's ledger."""
    if path is None:
        return []
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
    txt = read_text(in_root(root, "spend/ledger.md") or os.devnull)
    if txt is None or not txt.strip():
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


def packet(root, surface="claude"):
    """Everything a fresh seat needs to continue, in one gulp. NO CLOCK: every timestamp
    here comes off a file, so the same estate yields the same packet twice."""
    coord_p = in_root(root, "COORD.md")
    coord = tail_lines(coord_p, COORD_TAIL)
    agents = tail_lines(in_root(root, "COORD-AGENTS.md"), AGENT_TAIL)
    all_coord = tail_lines(coord_p, 10 ** 9)
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
        briefs = len([f for f in os.listdir(in_root(root, "briefs") or os.devnull)
                      if f.endswith(".md")])
    except OSError:
        briefs = 0
    is_repo, head, dirty, subj = git_facts(root)
    cs, _cd = coord_state(root)
    states = {}
    for runtime in selected_surfaces(surface):
        st, _detail, ver = foundation_state(root, runtime)
        states[runtime] = {"status": st, "version": ver,
                           "file": SURFACE_FILES[runtime]}
    established = cs == PASS and all(v["status"] == PASS for v in states.values())
    versions = sorted(set(v["version"] for v in states.values() if v["version"] is not None))
    return {
        "root": root,
        "surface": surface,
        "established": established,
        "coord_state": cs,
        "foundation_blocks": states,
        "claude_block": states.get("claude", {}).get("status"),
        "agents_block": states.get("codex", {}).get("status"),
        "protocol_version": versions[0] if len(versions) == 1 else versions,
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
    surface, serr, snote = resolve_surface(args.surface, root, writing=False)
    if snote:
        print("# WARN surface: %s" % snote)
    if serr:
        sys.stderr.write("notrest: %s\n" % serr)
        return EXIT_USAGE
    p = packet(root, surface)
    if not p["established"]:
        # NAME THE BOUNDARY (RA-2). "Not established" is true but useless when the reason
        # is that this estate's ledger points into somebody else's project — the successor
        # seat needs to know it was refused a trail, not that there is none.
        cs, cd = coord_state(root)
        if args.json:
            print(json.dumps({"root": root, "established": False,
                              "coord_state": cs, "coord_detail": cd},
                             indent=1, sort_keys=True))
        else:
            print("notrest: NOT ESTABLISHED — %s carries no continuable estate (%s). "
                  "Run `/notrest establish` first." % (root, cd))
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


def grade(states, failures=()):
    """The exit code. FAILURES ARE PART OF THE GRADE (F3): a run that was REFUSED a write
    it was asked to make has not established anything, however the surfaces read
    afterwards — `ESTABLISHED · wrote: nothing (writes failed: AGENTS.md) · exit 0` was a
    live output of this function. `check` passes no failures: it never writes."""
    if all(s == PASS for s in states):
        code = EXIT_OK
    elif any(s in (PASS, WARN) for s in states):
        code = EXIT_PARTIAL
    else:
        code = EXIT_NONE
    if failures and code == EXIT_OK:
        return EXIT_PARTIAL
    return code


def cmd_check(args):
    root, err = resolve_root(args.root)
    if err:
        sys.stderr.write("notrest: %s\n" % err)
        return EXIT_USAGE
    surface, serr, snote = resolve_surface(args.surface, root, writing=False)
    if snote:
        emit(WARN, "SURFACE", snote)
    if serr:
        sys.stderr.write("notrest: %s\n" % serr)
        return EXIT_USAGE
    print("notrest check — %s (surface=%s)" % (root, surface))
    cs, cd = coord_state(root)
    emit(cs, "COORD", cd)
    foundation_states = []
    for runtime in selected_surfaces(surface):
        ks, kd, _v = foundation_state(root, runtime)
        foundation_states.append(ks)
        emit(ks, SURFACE_LABELS[runtime], kd)
    emit(INFO, "GIT", "git repo — revision, diff, and trail evidence are available"
         if git_toplevel(root) == root
         else "NOT a git repo — estate surfaces are limited (see /notrest, non-git section)")
    for s, n, d in adoption(root):
        emit(s, n, d)
    code = grade([cs] + foundation_states)
    verdict(code, root)
    return code


def write_foundation(root, surface, failures, allow_weakening=False, requested=None):
    """One runtime-foundation half of establish. Returns the 'wrote' descriptions.

    `requested` is the raw `--surface` the operator asked for ("auto" or None when they
    did not choose), because THE WRITE GUARD turns on that distinction: creating a
    foundation for an undetected host needs an explicit choice, not a detector's guess."""
    filename = SURFACE_FILES[surface]
    label = SURFACE_LABELS[surface]
    kp = os.path.join(root, filename)
    wrote = []
    block = protocol_block()
    target = contain(root, kp)
    if target is None:
        emit(FAIL, label, "%s resolves outside %s — refusing to write through it"
             % (filename, root))
        failures.append(filename)
        return wrote
    if not os.path.isfile(target):
        allowed, why = may_create_surface(surface, requested)
        if not allowed:
            emit(WARN, label, why)
            # Counted, not silent: the operator asked for a foundation and did not get
            # one, and an exit code that reads as success would be a lie about that.
            failures.append("%s (creation refused: no host signal)" % filename)
            return wrote
        try:
            atomic_write(target, "# %s — project foundation\n\n%s" % (filename, block))
            wrote.append(filename)
            emit(PASS, label, "%s created with the v%d protocol block"
                 % (filename, PROTOCOL_VERSION))
        except OSError as exc:
            emit(FAIL, label, "could not write %s: %s" % (filename, exc))
            failures.append(filename)
        return wrote

    enc = not_utf8(target)
    if enc:
        emit(WARN, label, "%s is not UTF-8 (%s) — nothing written. A UTF-8 "
             "block appended here would be mojibake to its own reader, and the next "
             "round-trip read would raise." % (filename, enc))
        return wrote
    txt = read_rt(target)
    if txt is None:
        emit(FAIL, label, "%s is unreadable — leaving it alone" % filename)
        failures.append(filename)
        return wrote
    problem, blocks = block_problem(txt)
    if problem:
        emit(WARN, label, problem)
        return wrote
    try:
        if not blocks:
            # BELT AND BRACES (2026-08-02 round 2): the masked search found nothing, so we
            # are about to APPEND. If the raw text carries a line-anchored opener anyway,
            # some masking rule swallowed a real block — and appending would add one more
            # every run, without bound. Never append past that disagreement.
            if BLOCK_OPEN_RE.search(txt):
                emit(WARN, label,
                     "protocol markers exist only inside a fenced/masked region (a code-fence "
                     "example, or an unterminated fence) — not a live block; add the block "
                     "outside the fence by hand — nothing written")
                return wrote
            ro = readonly_refusal(target)
            if ro:
                emit(FAIL, label, ro)
                failures.append(filename)
                return wrote
            sep = "" if txt.endswith("\n\n") else ("\n" if txt.endswith("\n") else "\n\n")
            atomic_write(target, txt + sep + block, roundtrip=True)
            wrote.append("%s (block appended)" % filename)
            # NOT "the file is untouched": os.replace hands the path a NEW INODE, so the
            # file object changed even though not one byte of their text did. Say the
            # true thing (F4) — an operator who checks inode or mtime must not find the
            # tool's own message contradicted by `ls -i`.
            emit(PASS, label, "v%d protocol block appended — existing content preserved "
                 "byte for byte (atomic replace: same path and mode, new inode)"
                 % PROTOCOL_VERSION)
            return wrote
        found, m, c = blocks[0]
        if c is None:
            emit(WARN, label, "block opens at v%d but never closes — left alone; "
                 "close the marker by hand, then re-run" % found)
            return wrote
        if found >= PROTOCOL_VERSION:
            emit(INFO, label, "v%d protocol block already current — left untouched"
                 % found)
            return wrote

        # An UPGRADE replaces the managed span, so anything hand-written inside the
        # markers would vanish silently. Compare against the canonical body of the version
        # found and bank a copy when they differ; an UNKNOWN version can never be proven
        # untouched, so it is treated as edited.
        old_body = txt[m.end():c.start()].strip("\r\n")

        # ⛔ S57: REFUSE TO WEAKEN. Checked BEFORE the hand-edit backup path, because the
        # dangerous case is the one where the block is perfectly canonical and therefore
        # looks safe to replace. The estate's law is the fixed point; the tool bends to it.
        dropped = strictness_regressions(old_body, CANONICAL_BODIES[PROTOCOL_VERSION])
        if dropped and not allow_weakening:
            emit(WARN, label, "REFUSED the v%d -> v%d upgrade: it would drop the %s this "
                 "block already asserts, and %s is left exactly as it was. Re-run with "
                 "--allow-protocol-weakening if the estate has decided to relax it."
                 % (found, PROTOCOL_VERSION, " and ".join(dropped), filename))
            # Counted, not silent: the tool did NOT do what it was asked to do, and an
            # operator reading only the exit code must not read that as success.
            failures.append("%s (protocol upgrade refused: would weaken %s)"
                            % (filename, ", ".join(dropped)))
            return wrote

        # Checked BEFORE the backup: a refusal that still leaves a .bak behind has
        # written into a project it just said it would not write into.
        ro = readonly_refusal(target)
        if ro:
            emit(FAIL, label, ro)
            failures.append(filename)
            return wrote

        canon = CANONICAL_BODIES.get(found)
        if canon is None or old_body.strip() != canon.strip():
            bak = target + ".notrest-v%d.bak" % found
            try:
                atomic_write(bak, old_body + "\n", roundtrip=True)
                emit(WARN, label, "in-block edits discarded on the v%d -> v%d "
                     "upgrade — the old body was saved to %s"
                     % (found, PROTOCOL_VERSION, os.path.basename(bak)))
            except OSError as exc:
                emit(WARN, label, "in-block edits found but the backup failed "
                     "(%s) — the block was left alone" % exc)
                # RA-4: the upgrade this run came for did NOT happen. Warning about it and
                # then printing a tail that lists only what succeeded is how a refused
                # write reads as a clean run.
                failures.append("%s (upgrade abandoned: backup failed)" % filename)
                return wrote
        atomic_write(target, txt[:m.start()] + block.rstrip("\n") + txt[c.end():],
                     roundtrip=True)
        wrote.append("%s (block v%d -> v%d)" % (filename, found, PROTOCOL_VERSION))
        emit(PASS, label, "protocol block replaced v%d -> v%d — nothing outside the "
             "markers changed (atomic replace: same path and mode, new inode)"
             % (found, PROTOCOL_VERSION))
    except OSError as exc:
        emit(FAIL, label, "could not write %s: %s" % (filename, exc))
        failures.append(filename)
    return wrote


def write_claude(root, kp, failures):
    """Compatibility wrapper retained for external imports and older fixtures."""
    return write_foundation(root, "claude", failures)


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
    surface, serr, _snote = resolve_surface(args.surface, root, writing=True)
    if serr:
        sys.stderr.write("notrest: %s\n" % serr)
        return EXIT_USAGE
    print("notrest establish — %s (surface=%s)" % (root, surface))
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

    # ── 2. Runtime foundation — AGENTS.md on Codex, CLAUDE.md on Claude, or both when
    # explicitly requested. The same versioned block and byte-preservation laws apply.
    for runtime in selected_surfaces(surface):
        wrote += write_foundation(root, runtime, failures,
                                  allow_weakening=getattr(args, 'allow_protocol_weakening', False),
                                  requested=getattr(args, 'surface', None))

    # ── 3. git. Never initialized uninvited: `git init` changes what a directory IS, and
    # that is the owner's decision, not a side effect of establishing a ledger.
    if git_toplevel(root) == root:
        emit(INFO, "GIT", "git repo — revision, diff, and trail evidence are available")
    elif args.git_init:
        rc, _out = git(root, "init")
        if rc == 0:
            emit(PASS, "GIT", "git init run (--git-init) — nothing added, nothing committed")
        else:
            emit(FAIL, "GIT", "git init failed — leaving the directory as it was")
    else:
        emit(INFO, "GIT", "NOT a git repo — establishment still holds; COORD.md remains "
                          "the project trail, but revision-bound evidence is unavailable")
        for w in NONGIT_WARNS:
            emit(WARN, "GIT-DEGRADED", w)
        emit(INFO, "GIT", "`establish --git-init` runs `git init` (and nothing else) — "
                          "opt-in only, never automatic")

    # ── the verdict is re-read from disk, and the per-surface STATE is re-emitted beside
    # it: a run that ends in 5 must say WHICH surface is unfinished, on the same screen.
    cs, cd = coord_state(root)
    emit(cs, "COORD", cd)
    foundation_states = []
    for runtime in selected_surfaces(surface):
        ks, kd, _v = foundation_state(root, runtime)
        foundation_states.append(ks)
        emit(ks, SURFACE_LABELS[runtime], kd)
    code = grade([cs] + foundation_states, failures)
    if seed_pulse(root):
        emit(INFO, "PULSE", "instrument readings seeding in the background → pulse/*.txt "
                            "+ pulse/pulse.json (derived, disposable; Claude hooks refresh "
                            "automatically, Codex refreshes through explicit harness actions)")
    if failures:
        # A PARTIAL run wrote SOMETHING and failed at something else. The old tail said
        # "wrote: nothing" whenever anything failed, which was simply false about the
        # files that did land (F3) — and the files that land are what an operator has to
        # go and look at.
        tail = " · wrote: %s · writes failed: %s" % (
            ", ".join(wrote) if wrote else "nothing",
            ", ".join(sorted(set(failures))))
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
    c.add_argument("--surface", choices=("auto", "codex", "claude", "both"), default="auto",
                   help="foundation surface (default: auto — host signals decide, files only "
                        "narrow within a detected host, no signal means claude)")
    e = sub.add_parser("establish", help="write the establishment surfaces (idempotent)")
    e.add_argument("--root", help="project root (default: git root, else a marked cwd)")
    e.add_argument("--surface", choices=("auto", "codex", "claude", "both"), default="auto",
                   help="foundation surface to write (default: auto — host signals decide, and "
                        "auto never CREATES a foundation file for a host it did not detect)")
    e.add_argument("--git-init", action="store_true",
                   help="also run `git init` (and nothing else) when the root is not a repo")
    e.add_argument("--allow-protocol-weakening", action="store_true",
                   help="permit a protocol upgrade that DROPS a stricter clause the existing "
                        "block asserts (refused by default; the estate's law is the fixed point)")
    n = sub.add_parser("continuation",
                       help="read-only: the packet a successor seat needs to continue")
    n.add_argument("--root", help="project root (default: git root, else a marked cwd)")
    n.add_argument("--surface", choices=("auto", "codex", "claude", "both"), default="auto",
                   help="foundation surface to read (default: auto — host signals decide)")
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
