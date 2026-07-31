#!/usr/bin/env python3
"""starthere_lint.py — hold a START-HERE.md to the one promise its name makes: that a
reader who has never seen this project can RESUME from it.

Why this exists (record F-20, 2026-07-27). A cross-model acceptance test handed a
non-Claude loop a project directory and a START-HERE.md written an hour earlier. It stated
the project's status correctly and then could not state the next action — because the
document never did. The file carried STATUS where the contract promises ORDERED RESUME
INSTRUCTIONS, and it read perfectly to its author. Prose review had already passed it.
So the check is mechanical: a document is not finished because its writer recognises it.

Then the defect class bit a SECOND time (rig.rest, 2026-07-31), which is when a habit has
to become a check. That START-HERE cited commands a fresh clone could not run: the
artifacts they stand on (`.venv`, `.engine`) are GITIGNORED, and the command that recreates
them lived in a different file. DEAD-REFERENCE passed it — in the WORKING TREE those paths
exist. The lint proved a path was PRESENT; it never proved a command was RUNNABLE BY A
STRANGER. Rule 5 asks the only question that separates the two.

The five FAIL rules, each earned against a real file:

  NO-NEXT-ACTION            no section says what to DO next. Status, a read-order and a
                            "Run it" section are not a resume instruction — that exact
                            shape is what stranded the F-20 reader.
  NEXT-ACTION-NOT-ACTIONABLE  the section exists but carries no imperative step — no
                            command, no verb-led line. Status prose in a next-action
                            costume is the same defect wearing the heading.
  DEAD-REFERENCE            a path it cites does not exist under --root. sessionend's own
                            law: every cited path must be runnable exactly as written.
  NO-STATE-ANCHOR           nothing names where the trail lives (COORD/HANDOFF/STATE or
                            equivalent), so a cold reader cannot verify the status it was
                            handed against anything.
  UNRUNNABLE-FROM-CLEAN-CLONE  an instruction stands on a gitignored artifact and the file
                            never says how to recreate it. It exists here; it will not
                            exist there. The command runs for its author and fails for the
                            stranger the file is written for.

The rules are disjoint by construction — one defect lights exactly one rule. A missing
section is NO-NEXT-ACTION and never NOT-ACTIONABLE; a dead COORD.md citation is
DEAD-REFERENCE (the doc did name the trail) and never NO-STATE-ANCHOR; and a path that is
BOTH gitignored and absent from the working tree is DEAD-REFERENCE, never rule 5 — it is
already broken here, which is the plainer and more urgent thing to say. Rule 5 judges only
paths that exist, because "exists here, missing there" is the whole defect it names.

  starthere_lint.py check --file START-HERE.md [--root .] [--json] [--quiet] [--fix-hint]
  starthere_lint.py check --fix-hint            # skeleton only, no file needed

Exit: 0 clean · 5 warnings only · 6 any fail · 2 usage/missing file.
Zero model tokens. It reads and judges; it never writes — sessionend writes the file, this
only refuses to call it finished. --fix-hint PRINTS a skeleton, it does not apply one.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

# ── the shapes a next-action section really takes ───────────────────────────────────────
# Derived from what the contract ships and what the estate actually writes, not invented:
# sessionend's own template ("Then do this, in order"), rig.rest ("NEXT ACTION — do this
# first", the post-F-20 repair), finance ("To resume dig.rest work"), story.not.rest
# ("FIRST ACTION — the LIVE BLOCKER"), draft's formats ("Next steps", "Next").
NEXT_ACTION_SIGNALS = [
    r"then\s+do\s+this", r"\bdo\s+th(?:is|ese)\b", r"\bdo\s+next\b", r"what\s+to\s+do",
    r"next\s+action", r"next\s+step", r"^next\b", r"\bup\s+next\b", r"immediate",
    r"first\s+action", r"first\s+move", r"first\s+thing", r"do\s+this\s+first",
    r"\bresum(?:e|ing)\b", r"pick(?:ing)?\s+up", r"\bcontinu(?:e|ing)\b",
    r"kick\s?off", r"action\s+items?", r"\bto-?do\b", r"where\s+to\s+start",
    r"start\s+with", r"your\s+(?:task|build)", r"the\s+task\b", r"get(?:ting)?\s+started",
]
# Sections that describe the project rather than instruct the reader. "Run it" is on this
# list deliberately: flowb-run3 — the F-20 file — had a "Run it" section full of working
# commands and still could not tell a stranger what to do next. How-to-run is not resume.
NOT_NEXT_ACTION = [
    r"^run\s+it\b", r"how\s+to\s+run", r"^usage\b", r"^install", r"^setup\b",
    r"^status\b", r"where\s+(?:things|the\s+\w+)\s+stands?", r"what\s+this\s+is",
    r"\bread\s+(?:these|this|first|me)\b", r"read\s+.*in\s+order", r"watch\s+out",
    r"^the\s+laws?\b", r"who\s+to\s+ask", r"open\s+items?", r"known\s+", r"^notes?\b",
    r"^start[\s-]?here\b", r"live\s+line", r"^background\b", r"^context\b",
]
READ_FLAVOURED = re.compile(r"\bread\b|\bin\s+order\b|\bfiles?\b|\bindex\b", re.I)

# ── what counts as an imperative step ───────────────────────────────────────────────────
VERBS = set("""add apply archive ask audit bank build bump call cancel capture check clean
clear close commit compare compile confirm connect continue copy create decide delete
deploy diagnose disable do document draft drop edit enable ensure execute expand export
extend file fill find finish fix flip follow gate generate get go grep hand help hold
implement import initialize inspect install investigate keep kick land launch link list
load make measure merge message migrate move note open patch pick pin ping post prepare
probe promote prove publish pull purge push put read rebase rebuild reboot record refactor
refresh register reinstall release reload remove rename repeat replace report request
rerun reset resolve restart restore resume return review revert rewrite roll run save scan
schedule seal send set ship show skip slim split stage start stop submit swap switch sync
tag take tell test tidy tighten trace track trim try uninstall unpin update upgrade use
validate verify wait walk watch wire write""".split())
CMD_HEADS = set("""python python3 py bash sh zsh git npm npx node pnpm yarn make cd pytest
cargo go docker curl wget claude open rm cp mv ls grep rg sed awk find chmod source export
./ code brew pip pip3 uv ruff mypy tsc deno rake mvn gradle""".split())
CMD_RE = re.compile(r"^\s*(?:[-*+]\s*|\d+[.)]\s*|>\s*|\$\s*)*`{0,3}\s*(\./\S+|[A-Za-z0-9_.]+)")
DONE_COND = re.compile(
    r"\bexpect(?:s|ed|ing)?\b|\bshould\b|→|->|\bverif|\bconfirm|\bexit\s*(?:code\s*)?\d"
    r"|\bPASS\b|\bgreen\b|\buntil\b|\bdone\s+when\b|\bsucceed|\b0\s*[-\s]?fail|\bHEALTHY\b"
    r"|\bmust\s+(?:print|say|show|return|report)\b|\bclean\b", re.I)
VERSION_ANCHOR = re.compile(r"\bv?\d+\.\d+\.\d+\b|\bversion\s+\d|\b[0-9a-f]{7,40}\b|"
                            r"\bcommit\b|\btag\s+v?\d", re.I)

# ── what counts as naming the trail ─────────────────────────────────────────────────────
ANCHOR_STEMS = ("coord", "handoff", "state", "claude", "journal", "ledger", "log", "notes",
                "changelog", "history", "decision", "session", "progress", "status",
                "todo", "tasks", "backlog", "worklog", "diary")

# ── path citation extraction ────────────────────────────────────────────────────────────
EXTS = ("md|markdown|py|sh|bash|zsh|fish|json|jsonl|ndjson|html|htm|txt|yaml|yml|toml|ini|"
        "cfg|conf|js|mjs|cjs|ts|tsx|jsx|css|scss|sql|csv|tsv|xml|svg|png|jpg|jpeg|gif|pdf|"
        "rs|go|rb|java|kt|swift|c|h|cpp|hpp|php|pl|lua|env|lock|plist|service|sock")
PATH_RE = re.compile(r"(?<![\w/.\-])((?:~|\.{1,2})?/?(?:[\w.@+\-]+/)*[\w.@+\-]+\.(?:%s))"
                     r"(?![\w])" % EXTS)
DIR_IN_TICKS_RE = re.compile(r"`((?:~|\.{1,2})?/?(?:[\w.@+\-]+/)+[\w.@+\-]*)`")
PLACEHOLDER = re.compile(r"[<>{}$*?|\\]|\.\.\.|\bNNN\b|\bYYYY\b|\bxxx\b", re.I)
STRIP_FIRST = re.compile(r"https?://\S+|\bwww\.\S+|\S+@\S+\.\w+")

# ── the clean-clone check ───────────────────────────────────────────────────────────────
# A path-shaped token inside a command, extension or not: cited_paths() only sees paths
# with a known extension, and `.venv/bin/python` has none — yet it is precisely the thing a
# fresh clone is missing. Used by rule 5 only; the older rules keep the citation set they
# were built and fixtured against.
CMD_TOKEN_RE = re.compile(r"^(?:\./)?(?:[\w.@+\-]+/)+[\w.@+\-]*$")
# What a line has to do to count as RECREATING an artifact rather than merely using it.
# `.venv/bin/python app.py serve` uses it; `python3 -m venv .venv` creates it.
CREATE_RE = re.compile(
    r"\b(?:mkdir|venv|virtualenv|clone|worktree\s+add|pip3?\s+install|npm\s+(?:ci|i|install)"
    r"|yarn\s+install|pnpm\s+install|install|bootstrap|scaffold|re-?creat\w*|re-?generat\w*"
    r"|re-?build\w*|restore|download|fetch|unzip|untar|initiali[sz]e|\binit\b|creates?|created"
    r"|generates?|generated|builds?|built|make|set\s?up|provision)\b", re.I)
# What a line has to do to count as POINTING somewhere else for the bootstrap.
POINTER_RE = re.compile(
    r"\b(?:see|read|refer|per|instructions?|documented|describe[sd]?|explain(?:s|ed)?|steps?"
    r"|details?|how\s+to|covered|lives?\s+in|is\s+in|are\s+in|follow|according)\b", re.I)


def die(msg, code=2):
    sys.stderr.write("starthere_lint: %s\n" % msg)
    sys.exit(code)


# ── document model ──────────────────────────────────────────────────────────────────────
def fence_map(lines):
    """[bool] per line — True when the line sits inside a fenced code block."""
    inside, out = False, []
    for ln in lines:
        if re.match(r"^\s{0,3}(?:```|~~~)", ln):
            out.append(True)          # the fence line itself is code, not prose
            inside = not inside
            continue
        out.append(inside)
    return out


def headings(lines, fenced):
    """[(index, level, text)] — ATX headings plus bold-only lines used as pseudo-headings."""
    out = []
    for i, ln in enumerate(lines):
        if fenced[i]:
            continue
        m = re.match(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$", ln)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
            continue
        m = re.match(r"^\s{0,3}\*\*(.+?)\*\*:?\s*$", ln)
        if m:
            out.append((i, 6, m.group(1)))
    return out


def sections(lines, fenced):
    """[(index, level, text, body_start, body_end)] — body runs to the next heading of
    the same or shallower level."""
    hs, out = headings(lines, fenced), []
    for n, (i, lvl, txt) in enumerate(hs):
        end = len(lines)
        for j, l2, _t in hs[n + 1:]:
            if l2 <= lvl:
                end = j
                break
        out.append((i, lvl, txt, i + 1, end))
    return out


def norm_heading(text):
    """Heading text stripped of decoration, for signal matching."""
    t = re.sub(r"[`*_#]", "", text)
    t = re.sub(r"^[^\w]+", "", t)          # leading emoji / arrows / warning signs
    return t.strip().lower()


def is_next_action_heading(text):
    t = norm_heading(text)
    if any(re.search(p, t) for p in NOT_NEXT_ACTION):
        return False
    return any(re.search(p, t) for p in NEXT_ACTION_SIGNALS)


def first_token(line):
    m = CMD_RE.match(line)
    return m.group(1) if m else ""


def is_command_line(line, fenced_line):
    if fenced_line and line.strip():
        return True
    s = line.strip()
    if re.match(r"^\s*(?:[-*+]\s*|\d+[.)]\s*|>\s*)*\$\s+\S", line):
        return True
    for span in re.findall(r"`([^`]+)`", s):
        head = span.strip().split()[0] if span.strip().split() else ""
        if head in CMD_HEADS or head.startswith("./"):
            return True
    tok = first_token(line)
    return tok in CMD_HEADS or tok.startswith("./")


def is_verb_led(line):
    """First word of a step is an imperative verb — after stripping list markers,
    blockquote markers, numbering and bold."""
    s = re.sub(r"^\s*(?:>\s*)*(?:[-*+]\s+|\d+[.)]\s+)?", "", line)
    s = re.sub(r"^[`*_\"'(\[]+", "", s).strip()
    if not s:
        return False
    word = re.split(r"[\s,;:.!?()\[\]`*]+", s)[0].lower().strip(".,;:!?")
    if word in VERBS:
        return True
    if "-" in word:                       # sanity-check, re-run, double-check
        return word.split("-")[-1] in VERBS
    return False


def actionable(lines, fenced, start, end):
    """(bool, first_line_index) — does this span carry an imperative step?"""
    for i in range(start, end):
        ln = lines[i]
        if not ln.strip():
            continue
        if is_command_line(ln, fenced[i]) or is_verb_led(ln):
            return True, i
    return False, -1


def numbered_do_list(lines, fenced, secs):
    """Fallback shape: a numbered list of imperatives with no next-action heading over it.
    Read-order lists are excluded — 'what to read' is not 'what to do'; keeping them apart
    is the distinction the contract draws."""
    read_spans = []
    for (i, _lvl, txt, bs, be) in secs:
        t = norm_heading(txt)
        if READ_FLAVOURED.search(t) and not is_next_action_heading(txt):
            read_spans.append((bs, be))
    runs, cur = [], []
    for i, ln in enumerate(lines):
        if fenced[i]:
            continue
        if re.match(r"^\s{0,3}\d+[.)]\s+\S", ln):
            cur.append(i)
        elif not ln.strip():
            continue
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    for run in runs:
        if len(run) < 2:
            continue
        if any(bs <= run[0] < be for bs, be in read_spans):
            continue
        hits = [i for i in run if is_verb_led(lines[i]) or is_command_line(lines[i], False)]
        if len(hits) >= 2:
            return run[0], run[-1] + 1
    return None


# ── citations ───────────────────────────────────────────────────────────────────────────
def cited_paths(lines):
    """[(line_no, raw)] — every path-shaped citation, placeholders and URLs removed."""
    out, seen = [], set()
    for n, ln in enumerate(lines, 1):
        clean = STRIP_FIRST.sub(" ", ln)
        cands = list(PATH_RE.findall(clean)) + list(DIR_IN_TICKS_RE.findall(clean))
        for c in cands:
            if PLACEHOLDER.search(c) or c in (".", "..", "./", "../"):
                continue
            if (n, c) in seen:
                continue
            seen.add((n, c))
            out.append((n, c))
    return out


def resolve(root, raw):
    if raw.startswith("~"):
        return pathlib.Path(os.path.expanduser(raw))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else pathlib.Path(root) / raw


SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
             ".pytest_cache", "dist", "build", ".next", ".tox"}


def elsewhere(root, raw, budget=20000):
    """Where a cited basename actually lives, if it lives somewhere else under root.
    A wrong path is the common case and a fixable one — naming the real location turns
    the finding into a one-line repair instead of a search."""
    want, seen = pathlib.Path(raw.rstrip("/")).name, 0
    hits = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in list(filenames) + list(dirnames):
            seen += 1
            if seen > budget:
                return hits
            if name == want:
                rp = os.path.relpath(os.path.join(dirpath, name), str(root))
                hits.append(rp)
                if len(hits) >= 3:
                    return hits
    return hits


# ── clean-clone machinery ───────────────────────────────────────────────────────────────
def instruction_map(lines, fenced):
    """[bool] per line — True when the line INSTRUCTS the reader (a command, or a verb-led
    step) rather than describing the project. Rule 5 reads instructions, not prose: a
    sentence that merely mentions an ignored directory is not an order to use it, and is
    often the file honestly disclosing the gap ("`.engine` and `.venv` are gitignored")."""
    return [bool(ln.strip()) and (is_command_line(ln, fenced[i]) or is_verb_led(ln))
            for i, ln in enumerate(lines)]


def command_spans(line, fenced_line):
    """The parts of a line that are COMMAND text — the whole line inside a fence or after a
    `$` prompt, otherwise the backticked spans that open with a command head. Rule 5 also
    accepts a PATH-SHAPED head, which the older is_command_line deliberately does not:
    `.venv/bin/python app.py` is a command whose interpreter is itself the missing artifact,
    and refusing to look inside it is how the defect stayed invisible. Local to this rule —
    the older rules keep the command test they were fixtured against."""
    if fenced_line and line.strip():
        return [line]
    if re.match(r"^\s*(?:[-*+]\s*|\d+[.)]\s*|>\s*)*\$\s+\S", line):
        return [line]
    out = []
    for span in re.findall(r"`([^`]+)`", line):
        head = span.strip().split()[0] if span.strip().split() else ""
        if head in CMD_HEADS or head.startswith("./") or CMD_TOKEN_RE.match(head):
            out.append(span)
    return out


def command_paths(lines, fenced):
    """[(line_no, raw)] — path-shaped tokens inside command text, extension or not."""
    out, seen = [], set()
    for n, ln in enumerate(lines, 1):
        for span in command_spans(ln, fenced[n - 1]):
            for tok in span.split():
                tok = tok.strip("`\"'()[]{},;").rstrip(":")
                if not tok or tok.startswith("-") or "=" in tok or "://" in tok:
                    continue
                if PLACEHOLDER.search(tok) or not CMD_TOKEN_RE.match(tok):
                    continue
                if (n, tok) in seen:
                    continue
                seen.add((n, tok))
                out.append((n, tok))
    return out


def probe_path(p):
    """An absolute path for git to judge, with the DIRECTORY chain resolved but the final
    component left alone. Resolving the whole thing is wrong: `.venv/bin/python` is a
    symlink to a system interpreter, and realpath() would march it out of the repo and hide
    the very artifact the rule exists to catch (caught live against rig.rest). Resolving
    nothing is also wrong: /tmp is a symlink to /private/tmp on macOS, and git reports the
    resolved root."""
    ap = os.path.abspath(str(p))
    return os.path.join(os.path.realpath(os.path.dirname(ap)), os.path.basename(ap))


def git_ignored(root, paths):
    """{abs_path: matching-ignore-pattern} for the paths a fresh clone would NOT carry —
    or None when the question cannot be asked honestly (no git, no repo, git refuses).
    A skip is REPORTED, never silently read as "nothing is ignored".

    `git check-ignore` is index-aware by default, and that is exactly the semantics wanted:
    a TRACKED file matching an ignore rule still arrives in the clone, and git says so."""
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    if top.returncode != 0 or not top.stdout.strip():
        return None
    toproot = os.path.realpath(top.stdout.strip())
    inside = []
    for p in paths:
        rp = str(p)
        # git refuses a path outside its worktree and kills the whole batch — filter first.
        if rp == toproot or rp.startswith(toproot + os.sep):
            inside.append(rp)
    if not inside:
        return {}
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "-v", "--stdin"],
                           input="\n".join(inside) + "\n",
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if r.returncode not in (0, 1):        # 0 = some ignored, 1 = none, anything else = ask nothing
        return None
    out = {}
    for ln in r.stdout.splitlines():
        if "\t" not in ln:
            continue
        left, path = ln.split("\t", 1)
        bits = left.split(":", 2)         # <source>:<linenum>:<pattern>
        out[path.strip()] = bits[2] if len(bits) == 3 else ""
    return out


def ignored_artifact(raw, pattern):
    """The NAME of the thing the clone will be missing — the ignore pattern when it names a
    concrete path (`/.engine/` → `.engine`), else the cited path itself (`*.pyc` names no
    one thing, so the citation is the honest label)."""
    pat = (pattern or "").strip().lstrip("!").strip("/")
    if pat and not re.search(r"[*?\[\]]", pat):
        return pat
    return raw


def mentions(line, name):
    return re.search(r"(?<![\w.\-])%s(?![\w])" % re.escape(name), line) is not None


def mask(line, names):
    """The line with every ignored artifact and citation blanked out. Without this the rule
    passes itself vacuously: `.venv/bin/python .engine/…/index.py` USES both artifacts and
    creates neither, yet the artifact's own name carries the word `venv` — caught live
    against rig.rest before this line existed. A creation signal only counts when it
    survives the removal of the thing it is supposed to be creating."""
    out = line
    for nm in sorted(names, key=len, reverse=True):
        out = re.sub(r"(?<![\w.\-])%s(?![\w])" % re.escape(nm), " ", out)
    return out


def recreate_step(lines, instr, art, raws, blanks=()):
    """Line index of the instruction that CREATES the artifact, or -1. It must be an
    instruction, name the artifact, AND carry a creation signal in what is left of the line
    once every ignored path on it is masked out.

    Stated limit: this proves a bootstrap step is PRESENT, not that it is complete or
    correct. A line that installs INTO the artifact counts. The lint refuses the file that
    never tells the reader to build the thing at all — it cannot run the command for you."""
    names = set(blanks) | {art} | set(raws)
    for i, ln in enumerate(lines):
        if not instr[i]:
            continue
        if not (mentions(ln, art) or any(mentions(ln, r) for r in raws)):
            continue
        if CREATE_RE.search(mask(ln, names)):
            return i
    return -1


def recreate_pointer(lines, art, raws):
    """(line index, the file it defers to) — a line that names the artifact and sends the
    reader to another document for the bootstrap, or (-1, "")."""
    for i, ln in enumerate(lines):
        if not (mentions(ln, art) or any(mentions(ln, r) for r in raws)):
            continue
        if not POINTER_RE.search(ln):
            continue
        others = [c for _n, c in cited_paths([ln])
                  if c not in raws and not c.startswith(art)]
        if others:
            return i, others[0]
    return -1, ""


def anchors(cites):
    hits = []
    for _n, raw in cites:
        base = pathlib.Path(raw.rstrip("/")).name.lower()
        if any(base.startswith(s) for s in ANCHOR_STEMS):
            hits.append(raw)
    return sorted(set(hits))


# ── the lint ────────────────────────────────────────────────────────────────────────────
RULES = {
    "NO-NEXT-ACTION":
        "no section states what to DO next — START-HERE holds ordered resume "
        "instructions, not status (record F-20)",
    "NEXT-ACTION-NOT-ACTIONABLE":
        "the next-action section carries no imperative step — no command, no verb-led "
        "line; status prose in a next-action costume is not a resume instruction",
    "DEAD-REFERENCE":
        "a cited path does not exist under --root — every path a resume file cites must "
        "be runnable exactly as written",
    "NO-STATE-ANCHOR":
        "nothing names where the trail lives (COORD.md / HANDOFF.md / STATE.md or "
        "equivalent) — a cold reader cannot verify the status it was handed",
    "UNRUNNABLE-FROM-CLEAN-CLONE":
        "an instruction stands on a GITIGNORED artifact and the file never says how to "
        "recreate it — the path exists here and will NOT exist in a fresh clone, so the "
        "command runs for its author and fails for the stranger the file is written for",
}
WARNS = {
    "NO-VERSION-ANCHOR":
        "no version or commit anchor — a resume file that cannot say WHICH state it "
        "describes goes stale invisibly",
    "NO-DONE-CONDITION":
        "the next-action names no verifiable done-condition — say what the reader should "
        "see when the step worked",
    "RECREATE-ELSEWHERE":
        "the recreate step for a gitignored artifact is only a POINTER to another file — a "
        "resume file that outsources its own bootstrap is one file away from stranding its "
        "reader; the pointer is at least honest, so this warns rather than fails",
}


def lint(text, root):
    lines = text.splitlines()
    fenced = fence_map(lines)
    secs = sections(lines, fenced)
    fails, warns, notes = [], [], []
    extras = []                                # artifacts rule 5 wants a recreate step for

    # 1 / 2 — the resume instruction
    na = None
    for (i, _lvl, txt, bs, be) in secs:
        if i == 0 and _lvl == 1:
            continue                       # the document title is never the instruction
        if is_next_action_heading(txt):
            na = ("heading", i + 1, norm_heading(txt), bs, be)
            break
    if na is None:
        run = numbered_do_list(lines, fenced, secs)
        if run:
            na = ("numbered do-list", run[0] + 1, "numbered do-list", run[0], run[1])
    if na is None:
        fails.append(("NO-NEXT-ACTION", 0,
                      "no next-action section found; a status section, a read-order and a "
                      "how-to-run section do not answer 'what do I do now'"))
    else:
        kind, line_no, label, bs, be = na
        notes.append("next-action: %s at line %d (%s)" % (kind, line_no, label))
        act, at = actionable(lines, fenced, bs, be)
        if not act:
            fails.append(("NEXT-ACTION-NOT-ACTIONABLE", line_no,
                          "section '%s' has no command and no verb-led step" % label))
        elif not DONE_COND.search("\n".join(lines[bs:be])):
            warns.append(("NO-DONE-CONDITION", line_no,
                          "section '%s' says what to do but not how to know it worked"
                          % label))
        if act:
            notes.append("first imperative step at line %d" % (at + 1))

    # 3 — dead references
    cites = cited_paths(lines)
    # One path cited six times is one defect, not six findings — a repeated citation is
    # reported once at its first line with the repeat count. A precise report beats a pile.
    dead = {}
    for n, raw in cites:
        if resolve(root, raw).exists():
            continue
        if raw in dead:
            dead[raw][1] += 1
        else:
            dead[raw] = [n, 1]
    for raw, (n, count) in sorted(dead.items(), key=lambda kv: kv[1][0]):
        where = elsewhere(root, raw)
        hint = (" — it lives at %s" % ", ".join(where)) if where else ""
        more = (" (cited on %d lines — first at line %d)" % (count, n)) if count > 1 else ""
        fails.append(("DEAD-REFERENCE", n,
                      "cites %s — not found under %s%s%s" % (raw, root, hint, more)))
    notes.append("%d path citation(s) checked" % len(cites))

    # 5 — the clean-clone check (the F-20 defect class, second bite: rig.rest 2026-07-31).
    # DEAD-REFERENCE proves a path is THERE. It cannot prove a stranger will have it. The
    # rig file cited `.venv/…` and `.engine/…` inside its own commands: both present in the
    # working tree, both gitignored, and the command that recreates them living in another
    # file. The lint passed a START-HERE that could not run on a fresh clone. Only paths
    # that EXIST are judged here — absent ones are DEAD-REFERENCE's finding, so one defect
    # still lights exactly one rule.
    instr = instruction_map(lines, fenced)
    cand = {}                                   # abs path -> (first line, raw as cited)
    for n, raw in list(cites) + command_paths(lines, fenced):
        if not instr[n - 1]:
            continue
        p = resolve(root, raw)
        if not p.exists():
            continue
        key = probe_path(p)
        if key not in cand or n < cand[key][0]:
            cand[key] = (n, raw)
    # asked even with nothing to check, so a non-repo root is REPORTED as a skip rather
    # than silently reading as "nothing here is ignored"
    ignored = git_ignored(root, list(cand))
    if ignored is None:
        notes.append("clean-clone check SKIPPED — %s is not a git repo (or git could not "
                     "answer), so nothing can be asked about what a clone would carry"
                     % root)
    else:
        groups = {}                             # artifact -> [first line, [raws], pattern]
        for key, (n, raw) in sorted(cand.items(), key=lambda kv: kv[1][0]):
            if key not in ignored:
                continue
            art = ignored_artifact(raw, ignored[key])
            g = groups.setdefault(art, [n, [], ignored[key]])
            g[0] = min(g[0], n)
            if raw not in g[1]:
                g[1].append(raw)
        # every ignored name on the page, so a line that merely USES them cannot pose as
        # the line that CREATES one of them
        blanks = set(groups) | {r for g in groups.values() for r in g[1]}
        for art, (n, raws, pat) in sorted(groups.items(), key=lambda kv: kv[1][0]):
            where = ", ".join(raws[:3]) + (" +%d more" % (len(raws) - 3) if len(raws) > 3
                                           else "")
            rec = recreate_step(lines, instr, art, raws, blanks)
            if rec >= 0:
                notes.append("clean-clone: %s is gitignored, and line %d recreates it"
                             % (art, rec + 1))
                continue
            pi, target = recreate_pointer(lines, art, raws)
            if pi >= 0:
                warns.append(("RECREATE-ELSEWHERE", n,
                              "%s is gitignored (%s) and this file only POINTS at %s for "
                              "how to recreate it (line %d)" % (art, pat, target, pi + 1)))
                continue
            fails.append(("UNRUNNABLE-FROM-CLEAN-CLONE", n,
                          "instruction uses %s, and %s is gitignored (%s) — it exists here "
                          "and a FRESH CLONE WILL NOT HAVE IT; no step in this file "
                          "creates it" % (where, art, pat)))
            extras.append(art)
        if not groups:
            notes.append("clean-clone: no instruction stands on a gitignored artifact")

    # 4 — the state anchor (citation, not existence: existence is DEAD-REFERENCE's job)
    anc = anchors(cites)
    if anc:
        notes.append("state anchor(s): %s" % ", ".join(anc[:4]))
    else:
        fails.append(("NO-STATE-ANCHOR", 0,
                      "names no COORD/HANDOFF/STATE/CLAUDE-class file the reader can "
                      "check the status against"))

    if not VERSION_ANCHOR.search(text):
        warns.append(("NO-VERSION-ANCHOR", 0, "no version string or commit sha anywhere"))
    return fails, warns, notes, extras


FIX_HINT = """\
# Start Here — <project>
**Status in one line:** <where things stand>

## Read these first, in order
1. HANDOFF.md — where we are and what's next
2. COORD.md — the ledger tail (the trail wins when prose disagrees)
3. STATE.md — decisions + code, newest on top
4. CLAUDE.md — the foundation

## Then do this, in order
1. <verb-led first action> — run `<the exact command>`; expect `<the observable result>`
2. <next action> — <how the reader knows it worked>

## Watch out for
- <the top gotcha the next session will hit>
"""
HINT_WHY = """\
Minimum to satisfy the lint: a next-action heading the reader can find (any of "Then do
this" / "NEXT ACTION" / "Next steps" / "Resume" / "First action"), at least one verb-led
or command-bearing step under it, one COORD/HANDOFF/STATE-class file named, every cited
path real, and a recreate step for anything gitignored that a command stands on. Printed
only — starthere_lint never writes; sessionend writes, this judges.
"""
RECREATE_HINT = """\
## A fresh clone needs this first
`%s` is gitignored — a clone of this repo arrives without it, so every command below that
stands on it fails for a stranger. Put the recreate command HERE, not one file away:

```bash
<the exact command that creates %s>
# e.g. python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# e.g. git -C <source repo> worktree add "$PWD/.engine" <pinned sha>
```
"""
RECREATE_WHY = """\
A pointer ("see install/README.md") downgrades this to a RECREATE-ELSEWHERE warning — it is
honest, and still one file away from stranding the reader.
"""


def main():
    ap = argparse.ArgumentParser(
        description="lint a START-HERE.md for resume-readiness (record F-20)")
    ap.add_argument("mode", choices=["check"])
    ap.add_argument("--file")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--fix-hint", action="store_true")
    a = ap.parse_args()

    if a.file is None:
        if a.fix_hint:
            print(FIX_HINT)
            print(HINT_WHY, end="")
            sys.exit(0)
        die("check needs --file <START-HERE.md> (or --fix-hint alone for the skeleton)")

    p = pathlib.Path(a.file)
    if not p.is_file():
        die("no such file: %s" % p)
    root = pathlib.Path(a.root)
    if not root.is_dir():
        die("no such root: %s" % root)

    fails, warns, notes, extras = lint(
        p.read_text(encoding="utf-8", errors="replace"), root)
    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")

    if a.json:
        print(json.dumps({
            "file": str(p), "root": str(root), "verdict": verdict,
            "rules": RULES, "warn_rules": WARNS,
            "fails": [{"rule": r, "line": n, "detail": d, "law": RULES[r]}
                      for r, n, d in fails],
            "warnings": [{"rule": r, "line": n, "detail": d, "law": WARNS[r]}
                         for r, n, d in warns],
            "notes": notes,
        }, indent=2))
    elif not a.quiet:
        for r, n, d in fails:
            print("FAIL  %-26s %s%s" % (r, ("line %d: " % n) if n else "", d))
            print("      law: %s" % RULES[r])
        for r, n, d in warns:
            print("WARN  %-26s %s%s" % (r, ("line %d: " % n) if n else "", d))
        for note in notes:
            print("      %s" % note)
        print("starthere_lint: %s — %s · %d fail, %d warn, 0 model tokens"
              % (verdict, p, len(fails), len(warns)))

    if a.fix_hint:
        print()
        print(FIX_HINT)
        for art in extras:                     # one skeleton per artifact rule 5 named
            print(RECREATE_HINT % (art, art))
        if extras:
            print(RECREATE_WHY, end="")
        print(HINT_WHY, end="")

    sys.exit(6 if fails else (5 if warns else 0))


if __name__ == "__main__":
    main()
