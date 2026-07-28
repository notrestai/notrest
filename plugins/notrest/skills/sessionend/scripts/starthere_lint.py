#!/usr/bin/env python3
"""starthere_lint.py — hold a START-HERE.md to the one promise its name makes: that a
reader who has never seen this project can RESUME from it.

Why this exists (record F-20, 2026-07-27). A cross-model acceptance test handed a
non-Claude loop a project directory and a START-HERE.md written an hour earlier. It stated
the project's status correctly and then could not state the next action — because the
document never did. The file carried STATUS where the contract promises ORDERED RESUME
INSTRUCTIONS, and it read perfectly to its author. Prose review had already passed it.
So the check is mechanical: a document is not finished because its writer recognises it.

The four FAIL rules, each earned against that file:

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

The rules are disjoint by construction — one defect lights exactly one rule. A missing
section is NO-NEXT-ACTION and never NOT-ACTIONABLE; a dead COORD.md citation is
DEAD-REFERENCE (the doc did name the trail) and never NO-STATE-ANCHOR.

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
}
WARNS = {
    "NO-VERSION-ANCHOR":
        "no version or commit anchor — a resume file that cannot say WHICH state it "
        "describes goes stale invisibly",
    "NO-DONE-CONDITION":
        "the next-action names no verifiable done-condition — say what the reader should "
        "see when the step worked",
}


def lint(text, root):
    lines = text.splitlines()
    fenced = fence_map(lines)
    secs = sections(lines, fenced)
    fails, warns, notes = [], [], []

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
    return fails, warns, notes


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
or command-bearing step under it, one COORD/HANDOFF/STATE-class file named, and every
cited path real. Printed only — starthere_lint never writes; sessionend writes, this
judges.
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

    fails, warns, notes = lint(p.read_text(encoding="utf-8", errors="replace"), root)
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
        print(HINT_WHY, end="")

    sys.exit(6 if fails else (5 if warns else 0))


if __name__ == "__main__":
    main()
