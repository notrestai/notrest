#!/usr/bin/env python3
"""verdict_lint.py — hold a returned refuter report to the verdict grammar, before the
seat spends a read on it (and long before a repair is scheduled off it).

The grammar the skill states, checked mechanically:
  * CONFIRMED means reproduced — the finding carries the command AND its observed output
    in a fenced block. No paste, not CONFIRMED.
  * PLAUSIBLE means a concrete failure scenario — inputs, a state, a wrong outcome. A
    worry with no scenario is not a finding.
  * A numbered finding carrying neither verdict word is the noise the skill says to
    delete before returning.
  * SURVIVED and the budget line are required: a report without them cannot be told
    apart from a lazy one.

  verdict_lint.py <report.md> [--json] [--quiet]

Exit: 0 clean · 5 the report breaks the grammar · 2 usage/missing file.
It reads; it never edits the report, and it never judges whether a finding is RIGHT —
only whether it is the shape the seat agreed to accept.
"""
import argparse, json, pathlib, re, sys

FENCE_RE = re.compile(r"^\s*(?:```|~~~)", re.M)
HEAD_RE = re.compile(r"^\s{0,3}(?:#{1,6}\s+)?(?:[-*]\s+)?(?:\*\*)?(\d{1,2})[.)]\s+\S")
CONFIRMED_RE = re.compile(r"\bCONFIRMED\b")
PLAUSIBLE_RE = re.compile(r"\bPLAUSIBLE\b")
SURVIVED_RE = re.compile(r"\bSURVIVED\b")
BUDGET_RE = re.compile(r"budget\s+spent|tool calls used|spent[^.\n]{0,20}tool calls|"
                       r"\b\d+\s*(?:of\s*~?\d+\s*)?tool calls\b", re.I)
# A scenario is a condition AND a consequence — the two halves of "these inputs, this
# state, therefore this wrong outcome".
COND_RE = re.compile(r"\b(if|when|whenever|given|suppose|should|once|where)\b", re.I)
CONSEQ_RE = re.compile(r"(→|->)|\b(then|therefore|so that|results? in|resulting|produces?|"
                       r"would|will|could|leads? to|ends? up|reaches?|silently|instead)\b", re.I)
SCENARIO_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?scenario\b", re.I | re.M)


def die(msg, code=2):
    sys.stderr.write("verdict_lint: %s\n" % msg)
    sys.exit(code)


def fenced_blocks(text):
    """Fenced blocks with at least two non-empty lines — a command and its output."""
    out, cur, inside = [], [], False
    for line in text.splitlines():
        if re.match(r"^\s*(?:```|~~~)", line):
            if inside:
                out.append(cur)
                cur, inside = [], False
            else:
                inside = True
            continue
        if inside:
            cur.append(line)
    if inside and cur:
        out.append(cur)
    return [b for b in out if len([l for l in b if l.strip()]) >= 2]


def split_findings(text):
    """[(label, body)] — segments starting at a numbered finding heading. Fenced blocks
    are opaque: a `2)` inside pasted output must never start a new finding."""
    lines, starts, fence = text.splitlines(), [], False
    for i, line in enumerate(lines):
        if re.match(r"^\s*(?:```|~~~)", line):
            fence = not fence
            continue
        if fence:
            continue
        m = HEAD_RE.match(line)
        if m and not SURVIVED_RE.search(line):
            starts.append((i, m.group(1)))
    out = []
    for n, (i, label) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        out.append((label, "\n".join(lines[i:end])))
    return out


def lint(text):
    problems, checked = [], []
    findings = split_findings(text)
    if not findings:
        # A clean sweep is a legitimate result — but it still owes SURVIVED + budget.
        problems.append(("report", "no numbered findings found — if this is a clean "
                                   "sweep, say so; findings must be numbered and "
                                   "severity-ranked worst first"))
    for label, body in findings:
        conf, plaus = CONFIRMED_RE.search(body), PLAUSIBLE_RE.search(body)
        if conf:
            if not fenced_blocks(body):
                problems.append(("finding %s" % label,
                                 "CONFIRMED with no fenced command+output block — "
                                 "if you cannot paste an observation, it is PLAUSIBLE"))
            checked.append("%s CONFIRMED" % label)
        elif plaus:
            if not (SCENARIO_RE.search(body) or
                    (COND_RE.search(body) and CONSEQ_RE.search(body))):
                problems.append(("finding %s" % label,
                                 "PLAUSIBLE with no failure scenario — name the inputs, "
                                 "the state, and the wrong outcome that follows"))
            checked.append("%s PLAUSIBLE" % label)
        else:
            problems.append(("finding %s" % label,
                             "carries neither CONFIRMED nor PLAUSIBLE — a worry with no "
                             "reproduction and no scenario is not a finding; delete it"))
    if not SURVIVED_RE.search(text):
        problems.append(("report", "no SURVIVED section — an attack surface that held is "
                                   "information, and its absence makes a clean report "
                                   "indistinguishable from a lazy one"))
    if not BUDGET_RE.search(text):
        problems.append(("report", "no budget line — say the tool calls spent and what "
                                   "you did not get to"))
    return problems, checked, len(findings)


def main():
    ap = argparse.ArgumentParser(description="lint a refuter report against the verdict grammar")
    ap.add_argument("report")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    p = pathlib.Path(a.report)
    if not p.is_file():
        die("no such report: %s" % p)
    problems, checked, n = lint(p.read_text(encoding="utf-8", errors="replace"))
    if a.json:
        print(json.dumps({"report": str(p), "findings": n, "checked": checked,
                          "problems": [{"where": w, "why": y} for w, y in problems],
                          "verdict": "REJECT" if problems else "ACCEPT"}, indent=2))
    elif not a.quiet:
        for w, y in problems:
            print("REJECT  %-12s %s" % (w, y))
        print("verdict_lint: %d finding(s) — %s%s"
              % (n, ", ".join(checked) or "none typed",
                 " · %d problem(s)" % len(problems) if problems else " · grammar clean"))
    sys.exit(5 if problems else 0)


if __name__ == "__main__":
    main()
