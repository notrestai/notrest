#!/usr/bin/env python3
"""plan_lint.py — check the two things a plan is most worth checking for, and the two the
skill was grading in its own prose: dependency ordering, and convergence.

Everything else in stepbystep is judgement. But "no step depends on work that happens
later", "every step says how you know it worked", "every one-way door has a rollback or an
admission that it has none", and "every Low-confidence step carries a mitigation" are
mechanical — and a model marking its own homework on them is the weakest link in the loop.

  plan_lint.py check <plan.md> [--json] [--quiet]
  plan_lint.py converge --prev <planA.md> --curr <planB.md> [--threshold 0.98] [--json]
  plan_lint.py <plan.md>                    # shorthand for `check`

check — the rules, each finding printed as file:line, the step, and the rule it broke:

  done-when-missing      every step carries a concrete "done when"
  dep-forward            a step depends only on steps EARLIER than itself
  dep-dangling           …and only on steps that exist
  dep-cycle              the dependency graph is acyclic (the cycle is printed)
  duplicate-step-number  step numbers are unique across phases, or `depends on: step N`
                         cannot resolve
  oneway-no-rollback     every [ONE-WAY] step has a rollback, or says in words that it
                         cannot be undone
  low-no-mitigation      every Low-confidence step carries a mitigation

  Exit: 0 clean · 5 findings · 2 usage/missing file. Zero model tokens.

converge — measures the distance between two candidate plans (v2 → v3) so the iteration
log carries a NUMBER instead of an assurance. Material change (the skill's word: content,
ordering, reversibility, risk, confidence) is counted after normalising away wording and
whitespace, so a reworded plan is visibly the same plan. It exits 0 whatever it measures:
the ratio is the output, the loop decision stays the skill's.

Reads only; it never edits a plan, and it never judges whether a step is RIGHT — only
whether it is the shape the skill promised to deliver.
"""
import argparse, difflib, json, pathlib, re, sys

FENCE_RE = re.compile(r"^\s{0,3}(?:`{3,}|~{3,})")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+\S")
PLAN_HEAD_RE = re.compile(r"^\s{0,3}(#{1,6})\s+.*\bthe plan\b", re.I)
PHASE_RE = re.compile(r"^\s{0,3}(#{1,6})\s+.*\bphase\b", re.I)
# A numbered line in Sources is a citation, not a step. Grading it as one is how a linter
# loses the reader it was built for.
STOP_SECTION_RE = re.compile(r"^\s{0,3}#{1,6}\s+.*\b(sources|references|appendix|glossary|"
                             r"checkpoints|if things go wrong|confidence)\b", re.I)
STEP_RE = re.compile(r"^\s{0,3}(\d{1,3})[.)]\s+\S")
DONE_WHEN_RE = re.compile(r"\bdone\s+when\b", re.I)
DEP_RE = re.compile(r"^\s*(?:[-*>]\s*)*(?:\*\*)?depends?\s+on\b\s*:?\s*(.*)$", re.I | re.M)
DEP_NONE_RE = re.compile(r"^\s*(?:\*\*)?\s*(nothing|none|n/?a|-|—)\b", re.I)
STEP_REF_RE = re.compile(r"\bsteps?\s*#?\s*(\d{1,3})", re.I)
BARE_LIST_RE = re.compile(r"^[\d\s,;&+]+$")
ONEWAY_RE = re.compile(r"\[one[-\s]?way\]", re.I)
ROLLBACK_RE = re.compile(r"\broll(?:ing|s|ed)?[-\s]?back\b|\bcannot be undone\b|"
                         r"\bcan'?t be undone\b|\bno undo\b|\bundone\b|\bnot reversible\b|"
                         r"\brestore (?:from|path|point)\b|"
                         r"\birreversible[^.\n]{0,40}\bno\b", re.I)
LOW_RE = re.compile(r"confidence\s*[:\-–—]?\s*\[?\s*(?:L|low)\b\]?", re.I)
MITIGATION_RE = re.compile(r"\bmitigat|\brises? to\b|\braise[sd]? (?:it|the score|confidence)\b|"
                           r"\bwhat would raise\b|\bresolve[- ]first\b|\bresolve .{0,20}first\b|"
                           r"\bspike\b|\bdry[- ]?run\b|\bsign[- ]?off\b|\[needs expert\]|"
                           r"\bcheckpoint\b|\bpilot\b|\btest .{0,25}(?:staging|first)\b", re.I)
FALLBACK_HEAD_RE = re.compile(r"^\s{0,3}#{1,6}\s+.*\b(if things go wrong|contingenc|"
                              r"rollback)\b", re.I)
CONF_HEAD_RE = re.compile(r"^\s{0,3}#{1,6}\s+.*\bconfidence\b", re.I)
MATERIAL_HINT_RE = re.compile(r"\[one[-\s]?way\]|\bdone when\b|\bdepends on\b|confidence", re.I)


def die(msg, code=2):
    sys.stderr.write("plan_lint: %s\n" % msg)
    sys.exit(code)


def fence_map(lines):
    """Indices inside a fenced block — pasted output is opaque to every rule below."""
    out, inside = set(), False
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            out.add(i)
            inside = not inside
            continue
        if inside:
            out.add(i)
    return out


def section(lines, fenced, head_re):
    """The body text of the first section whose heading matches, '' if there is none."""
    start = lvl = None
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        if start is None:
            m = head_re.match(line)
            if m:
                start = i + 1
                lvl = len(HEADING_RE.match(line).group(1))
            continue
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) <= lvl:
            return "\n".join(lines[start:i])
    return "\n".join(lines[start:]) if start is not None else ""


def plan_scope(lines, fenced):
    """(start, end, how) — where the steps live. `## The Plan` when the delivered shape is
    there, else the phase sections, else the document down to the first Sources-ish head."""
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        m = PLAN_HEAD_RE.match(line)
        if m:
            lvl = len(m.group(1))
            for j in range(i + 1, len(lines)):
                mm = HEADING_RE.match(lines[j])
                if j not in fenced and mm and len(mm.group(1)) <= lvl:
                    return i + 1, j, "the `%s` section" % line.strip().lstrip("# ")
            return i + 1, len(lines), "the `%s` section" % line.strip().lstrip("# ")
    first = None
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        m = PHASE_RE.match(line)
        if m and first is None:
            first, lvl = i, len(m.group(1))
            continue
        if first is not None:
            mm = HEADING_RE.match(line)
            if mm and len(mm.group(1)) <= lvl and not PHASE_RE.match(line):
                return first, i, "the phase sections"
    if first is not None:
        return first, len(lines), "the phase sections"
    for i, line in enumerate(lines):
        if i not in fenced and STOP_SECTION_RE.match(line):
            return 0, i, "the whole document above `%s`" % line.strip().lstrip("# ")
    return 0, len(lines), "the whole document"


def parse_steps(lines, fenced):
    start, end, how = plan_scope(lines, fenced)
    steps, cur = [], None
    for i in range(start, end):
        if i in fenced:
            continue
        line = lines[i]
        if HEADING_RE.match(line):
            if cur:
                cur["end"] = i
                cur = None
            continue
        m = STEP_RE.match(line)
        if m:
            if cur:
                cur["end"] = i
            cur = {"n": int(m.group(1)), "line": i + 1, "start": i, "end": end}
            steps.append(cur)
    if cur:
        cur["end"] = end
    for s in steps:
        s["body"] = "\n".join(lines[s["start"]:s["end"]])
    return steps, how


def deps_of(body):
    """Declared dependencies as step numbers. `step N` wins; a bare list ("3, 5") is read
    only when the line is nothing but numbers — otherwise "under 1s" becomes step 1."""
    refs = []
    for m in DEP_RE.finditer(body):
        tail = m.group(1).strip()
        if not tail or DEP_NONE_RE.match(tail):
            continue
        found = [int(x) for x in STEP_REF_RE.findall(tail)]
        if not found and BARE_LIST_RE.match(tail):
            found = [int(x) for x in re.findall(r"\d{1,3}", tail)]
        refs.extend(found)
    return refs


def find_cycles(edges):
    """Edges are step -> [deps]. Returns the set of (a, b) edges lying on a cycle, plus a
    readable path for the first one found."""
    on_cycle, path_out, state, stack = set(), [], {}, []

    def walk(u):
        state[u] = 1
        stack.append(u)
        for v in edges.get(u, []):
            if v not in edges:
                continue
            if state.get(v) == 1:                      # back edge — a real cycle
                cyc = stack[stack.index(v):] + [v]
                for a, b in zip(cyc, cyc[1:]):
                    on_cycle.add((a, b))
                if not path_out:
                    path_out.append(" → ".join("step %d" % s for s in cyc))
            elif state.get(v, 0) == 0:
                walk(v)
        stack.pop()
        state[u] = 2

    for n in sorted(edges):
        if state.get(n, 0) == 0:
            walk(n)
    return on_cycle, (path_out[0] if path_out else "")


def references_step(text, n):
    """Lines in a fallback section that name this step (plus the two lines under them)."""
    lines, ref = text.splitlines(), re.compile(r"\bstep\s*#?\s*%d\b" % n, re.I)
    for i, line in enumerate(lines):
        if ref.search(line):
            yield "\n".join(lines[i:i + 3])


def lint(text):
    lines = text.splitlines()
    fenced = fence_map(lines)
    steps, how = parse_steps(lines, fenced)
    fallback = section(lines, fenced, FALLBACK_HEAD_RE)
    confidence = section(lines, fenced, CONF_HEAD_RE)
    findings = []

    def add(line, step, rule, message):
        findings.append({"line": line, "step": step, "rule": rule, "message": message})

    if not steps:
        add(1, None, "no-steps",
            "no numbered steps found in %s — a plan whose steps cannot be located cannot "
            "be checked for ordering, verification, or reversibility" % how)
        return findings, {"steps": 0, "scope": how, "oneway": 0, "low": 0}, lines

    seen = {}
    for s in steps:
        if s["n"] in seen:
            add(s["line"], s["n"], "duplicate-step-number",
                "step %d is numbered twice (first at line %d) — number steps continuously "
                "across phases, or `depends on: step %d` cannot resolve to one step"
                % (s["n"], seen[s["n"]], s["n"]))
        else:
            seen[s["n"]] = s["line"]
        s["deps"] = deps_of(s["body"])

    edges = {s["n"]: [d for d in s["deps"]] for s in steps}
    on_cycle, cycle_path = find_cycles(edges)
    if on_cycle:
        first = steps[0]
        for s in steps:
            if any((s["n"], d) in on_cycle for d in s["deps"]):
                first = s
                break
        add(first["line"], first["n"], "dep-cycle",
            "the dependency graph has a cycle: %s — nothing in it can start, so the plan "
            "cannot be executed as ordered" % (cycle_path or "see depends-on lines"))

    numbers = set(seen)
    for s in steps:
        if not DONE_WHEN_RE.search(s["body"]):
            add(s["line"], s["n"], "done-when-missing",
                "step %d has no \"done when\" — a step with no verification is not finished "
                "being planned" % s["n"])
        for d in s["deps"]:
            if (s["n"], d) in on_cycle:
                continue                              # already reported as the cycle
            if d not in numbers:
                add(s["line"], s["n"], "dep-dangling",
                    "step %d depends on step %d, which does not exist in this plan"
                    % (s["n"], d))
            elif d == s["n"]:
                add(s["line"], s["n"], "dep-self",
                    "step %d depends on itself" % s["n"])
            elif d > s["n"]:
                add(s["line"], s["n"], "dep-forward",
                    "step %d depends on step %d, which comes LATER — a plan cannot depend "
                    "on work that has not happened yet; re-sequence it" % (s["n"], d))
        if ONEWAY_RE.search(s["body"]) and not ROLLBACK_RE.search(s["body"]):
            if not any(ROLLBACK_RE.search(chunk) for chunk in references_step(fallback, s["n"])):
                add(s["line"], s["n"], "oneway-no-rollback",
                    "step %d is [ONE-WAY] with no rollback and no admission that it has "
                    "none — say how to undo it, or say in words that it cannot be undone; "
                    "the door the doer cannot walk back through is the one that must be "
                    "explicit" % s["n"])
        if LOW_RE.search(s["body"]) and not MITIGATION_RE.search(s["body"]):
            if not any(MITIGATION_RE.search(chunk) for chunk in references_step(confidence, s["n"])):
                add(s["line"], s["n"], "low-no-mitigation",
                    "step %d is Low confidence with no mitigation — every Low step owes a "
                    "resolve-first, a test/spike, a checkpoint or an expert sign-off, and "
                    "what would raise the score" % s["n"])
    findings.sort(key=lambda f: (f["line"], f["rule"]))
    stats = {"steps": len(steps), "scope": how,
             "oneway": sum(1 for s in steps if ONEWAY_RE.search(s["body"])),
             "low": sum(1 for s in steps if LOW_RE.search(s["body"])),
             "with_deps": sum(1 for s in steps if s["deps"])}
    return findings, stats, lines


# ── converge ────────────────────────────────────────────────────────────────────────────

def norm(line):
    """Strip what the skill calls cosmetic — emphasis, case, spacing, sentence punctuation
    — and keep what changes meaning. Operator characters (/ - > < | & = $ %) survive, so
    `cmd > f` and `cmd >> f` stay two different lines while "primary." and "primary" become
    one. Material change is what remains after this."""
    s = line.strip().lower().replace("—", "-").replace("–", "-")
    s = re.sub(r"[*_`~#\"'“”‘’.,;:!?()\[\]]+", "", s)
    return re.sub(r"\s+", " ", s).strip(" -")


def counts(text):
    lines = text.splitlines()
    fenced = fence_map(lines)
    steps, _ = parse_steps(lines, fenced)
    return {"steps": len(steps),
            "oneway": sum(1 for s in steps if ONEWAY_RE.search(s["body"])),
            "low": sum(1 for s in steps if LOW_RE.search(s["body"])),
            "phases": sum(1 for i, l in enumerate(lines)
                          if i not in fenced and PHASE_RE.match(l))}


def changed_lines(a, b):
    """(added, removed, replaced) line counts from difflib opcodes."""
    add = rem = rep = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "insert":
            add += j2 - j1
        elif tag == "delete":
            rem += i2 - i1
        elif tag == "replace":
            rep += max(i2 - i1, j2 - j1)
    return add, rem, rep


def converge(prev_text, curr_text, threshold):
    p_raw = [l for l in prev_text.splitlines() if l.strip()]
    c_raw = [l for l in curr_text.splitlines() if l.strip()]
    p_norm, c_norm = [norm(l) for l in p_raw], [norm(l) for l in c_raw]
    ratio = difflib.SequenceMatcher(None, p_norm, c_norm).ratio()
    raw_ratio = difflib.SequenceMatcher(None, p_raw, c_raw).ratio()
    m_add, m_rem, m_rep = changed_lines(p_norm, c_norm)
    r_add, r_rem, r_rep = changed_lines(p_raw, c_raw)
    material = m_add + m_rem + m_rep
    cosmetic = max(0, (r_add + r_rem + r_rep) - material)
    pc, cc = counts(prev_text), counts(curr_text)
    structural = [k for k in ("steps", "oneway", "low", "phases") if pc[k] != cc[k]]
    if material == 0:
        verdict, why = "CONVERGED", ("no material change — this iteration reproduced the "
                                     "prior plan; %d cosmetic line(s) only" % cosmetic)
    elif ratio >= threshold:
        verdict, why = "NARROWING", ("%d material line change(s) at similarity %.3f (≥ %.2f) "
                                     "— the loop is narrowing, one more round is cheap"
                                     % (material, ratio, threshold))
    else:
        verdict, why = "MOVING", ("%d material line change(s) at similarity %.3f (< %.2f) — "
                                  "not converged%s"
                                  % (material, ratio, threshold,
                                     "; structure moved: " + ", ".join(structural)
                                     if structural else ""))
    return {"similarity": round(ratio, 4), "raw_similarity": round(raw_ratio, 4),
            "threshold": threshold, "material_lines": material, "cosmetic_lines": cosmetic,
            "added": m_add, "removed": m_rem, "replaced": m_rep,
            "prev_lines": len(p_raw), "curr_lines": len(c_raw),
            "prev": pc, "curr": cc, "structure_moved": structural,
            "verdict": verdict, "why": why}


def read(argname, value):
    p = pathlib.Path(value)
    if not p.is_file():
        die("no such %s: %s" % (argname, p))
    return p, p.read_text(encoding="utf-8", errors="replace")


def cmd_check(a):
    p, text = read("plan", a.plan)
    findings, stats, _ = lint(text)
    if a.json:
        print(json.dumps({"plan": str(p), "stats": stats, "findings": findings,
                          "verdict": "FINDINGS" if findings else "CLEAN"}, indent=2))
    else:
        for f in findings:
            print("FINDING  %s:%d  %-8s [%s]  %s"
                  % (p, f["line"], "step %s" % f["step"] if f["step"] else "plan",
                     f["rule"], f["message"]))
        if not a.quiet:
            print("plan_lint: %d step(s) in %s · %d [ONE-WAY] · %d Low — %s"
                  % (stats["steps"], stats["scope"], stats["oneway"], stats["low"],
                     "%d finding(s)" % len(findings) if findings else "clean"))
    sys.exit(5 if findings else 0)


def cmd_converge(a):
    pp, prev = read("prev plan", a.prev)
    cp, curr = read("curr plan", a.curr)
    r = converge(prev, curr, a.threshold)
    if a.json:
        print(json.dumps(dict(r, prev_file=str(pp), curr_file=str(cp)), indent=2))
    else:
        print("converge  %s → %s" % (pp, cp))
        print("  similarity     %.3f   (difflib ratio over normalised lines; raw %.3f)"
              % (r["similarity"], r["raw_similarity"]))
        print("  lines          prev %d · curr %d" % (r["prev_lines"], r["curr_lines"]))
        print("  material       +%d added · -%d removed · %d replaced  = %d line(s)"
              % (r["added"], r["removed"], r["replaced"], r["material_lines"]))
        print("  cosmetic only  %d line(s) (wording/whitespace — not a change of plan)"
              % r["cosmetic_lines"])
        print("  structure      steps %d→%d · [ONE-WAY] %d→%d · Low %d→%d · phases %d→%d"
              % (r["prev"]["steps"], r["curr"]["steps"], r["prev"]["oneway"],
                 r["curr"]["oneway"], r["prev"]["low"], r["curr"]["low"],
                 r["prev"]["phases"], r["curr"]["phases"]))
        print("  verdict        %s — %s" % (r["verdict"], r["why"]))
    sys.exit(0)                       # a measurement is not a verdict; the loop decides


def main():
    argv = sys.argv[1:]
    if argv and argv[0] not in ("check", "converge", "-h", "--help"):
        argv.insert(0, "check")       # `plan_lint.py plan.md` shorthand
    ap = argparse.ArgumentParser(description="lint a stepbystep plan; measure convergence")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="hold a plan to the ordering/verification rules")
    c.add_argument("plan")
    c.add_argument("--json", action="store_true")
    c.add_argument("--quiet", action="store_true")
    c.set_defaults(f=cmd_check)
    v = sub.add_parser("converge", help="measure the distance between two candidate plans")
    v.add_argument("--prev", required=True)
    v.add_argument("--curr", required=True)
    v.add_argument("--threshold", type=float, default=0.98)
    v.add_argument("--json", action="store_true")
    v.set_defaults(f=cmd_converge)
    a = ap.parse_args(argv)
    if not getattr(a, "f", None):
        ap.print_help()
        sys.exit(2)
    a.f(a)


if __name__ == "__main__":
    main()
