#!/usr/bin/env python3
"""runbook_lint.py — hold a runbook to actionplan's own laws BEFORE a human pastes any of
it into production at 2am.

The skill writes commands and never runs them, which is right — but it left nothing that
checks a block is even syntactically valid, that a step kept its verify and its rollback,
that every placeholder is defined, that a destructive line carries its ⛔, or that a
credential slipped into the file. This does, mechanically, with no model in the loop.

  runbook_lint.py <runbook.md> [--json] [--quiet]

The rules, each finding printed as file:line plus the rule it broke:

  bash-syntax             every fenced bash/sh/zsh block parses under `bash -n`
  shellcheck-error        …and shellcheck's error-severity findings, WHEN shellcheck is
                          installed. Absent, the run prints that it degraded and keeps
                          going: failing for a missing linter only teaches people to skip
                          the gate, and `bash -n` still ran.
  step-missing-verify     every step keeps its "done when" check
  step-missing-rollback   …and its rollback — an explicit "Rollback: none — <restore
                          path>" counts, silence does not
  phase-missing-host      every phase says which machine to run it on (the most common
                          runbook failure is the right command on the wrong host)
  placeholder-undeclared  every <PLACEHOLDER> used is defined in the values table
  destructive-unmarked    every destructive op carries ⛔ at or above its line
  secret-shape            nothing in the file matches a credential shape

Exit: 0 clean · 5 findings · 2 usage/missing file. Zero model tokens.

It reads; it never edits the runbook and never executes a command out of it — `bash -n`
parses without running, and the block handed to it is a copy in a temp file.

THE SECRET CLASSES ARE NOT DEFINED HERE. They are imported from chatroom's
scripts/room.py (SECRET_PATTERNS / screen) — one list, one place, because two lists drift
and the one that drifts is the one that misses the key. Sourced at
../../chatroom/scripts/room.py, overridable with $NOTREST_ROOM_PY. If that file cannot be
imported (a loose install of this skill alone), the screen is reported UNAVAILABLE in the
output — never silently skipped, and never re-invented here.
"""
import argparse, importlib.util, json, os, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOM_PY = pathlib.Path(os.environ.get(
    "NOTREST_ROOM_PY", str(HERE.parent.parent / "chatroom" / "scripts" / "room.py")))

FENCE_RE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})\s*([A-Za-z0-9_.+-]*)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S")
PHASE_RE = re.compile(r"^\s{0,3}#{2,6}\s+.*\bphase\b", re.I)
HOST_RE = re.compile(r"\brun on\b\s*:", re.I)
STEP_RE = re.compile(r"^\s{0,3}(\d{1,3})[.)]\s+\S")
VERIFY_RE = re.compile(r"^\s*(?:[-*>]\s*)*(?:\*\*)?verif(?:y|ication)\b", re.I | re.M)
ROLLBACK_RE = re.compile(r"^\s*(?:[-*>]\s*)*(?:\*\*)?roll[\s-]?back\b", re.I | re.M)
TABLE_ROW_RE = re.compile(r"^\s{0,3}\|(.+)$")
# The placeholder grammar the skill states: <UPPER_SNAKE>. Only these are held to the
# values table — a token the grammar does not recognise is not silently "declared".
PLACEHOLDER_RE = re.compile(r"<([A-Z][A-Z0-9_]{2,})>")
# …but ANY <bare-word> is desugared before `bash -n`, because `<FOO>` is two redirections
# to the shell (`< FOO >` with no target) and would report a syntax error the runbook does
# not have. Substituting a plain word first is the difference between checking syntax and
# manufacturing false findings.
ANGLE_WORD_RE = re.compile(r"<([A-Za-z_][A-Za-z0-9_.-]*)>")
BASH_LANGS = {"bash", "sh", "zsh", "shell"}
STOP = "⛔"  # ⛔

DESTRUCTIVE = [
    ("DROP", re.compile(r"\bDROP\s+(?:DATABASE|SCHEMA|TABLE|INDEX|VIEW|USER|ROLE|COLUMN|"
                        r"CONSTRAINT|TABLESPACE)\b", re.I)),
    ("dd", re.compile(r"\bdd\s+[a-z]{1,3}=")),
    ("mkfs", re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\b")),
    ("truncate", re.compile(r"\btruncate\b", re.I)),
    # /dev/null, /dev/stdout, /dev/stderr, /dev/tty and /dev/fd/N are the harmless ones.
    ("> on a device", re.compile(r">\s*/dev/(?!null\b|stdout\b|stderr\b|tty\b|fd/)")),
    ("kubectl delete", re.compile(r"\bkubectl\b[^\n]*\bdelete\b")),
    ("git push --force", re.compile(r"\bgit\s+push\b[^\n]*(?:--force(?:-with-lease)?|\s-f\b)")),
]
RM_RE = re.compile(r"\brm\b((?:\s+-{1,2}[A-Za-z][A-Za-z-]*)+)")


def die(msg, code=2):
    sys.stderr.write("runbook_lint: %s\n" % msg)
    sys.exit(code)


def load_screen():
    """(screen_fn | None, note). chatroom owns the credential shapes; this borrows them."""
    try:
        spec = importlib.util.spec_from_file_location("notrest_room_patterns", str(ROOM_PY))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.screen, ("secret screen: %d class(es) imported from %s"
                            % (len(mod.SECRET_PATTERNS), ROOM_PY))
    except Exception as exc:                                   # loose install, moved file
        return None, ("secret screen UNAVAILABLE — could not import %s (%s). The credential "
                      "check did NOT run; it is chatroom's list and is deliberately not "
                      "duplicated here. Set $NOTREST_ROOM_PY or install the full plugin."
                      % (ROOM_PY, type(exc).__name__))


def rm_is_recursive_force(flags):
    """`rm -rf`, `rm -r -f`, `rm --recursive --force` — the destructive shape, not bare rm."""
    short, longs = "", []
    for tok in flags.split():
        if tok.startswith("--"):
            longs.append(tok.lower())
        elif tok.startswith("-"):
            short += tok[1:].lower()
    rec = "r" in short or any(l.startswith("--recursive") for l in longs)
    force = "f" in short or any(l.startswith("--force") for l in longs)
    return rec and force


def scan(lines):
    """One pass: fenced blocks (with their language and 1-based start line) and the set of
    line indices that live inside a fence."""
    blocks, inside, marker, cur, start, lang = [], False, "", [], 0, ""
    fenced = set()
    for i, line in enumerate(lines):
        m = FENCE_RE.match(line)
        if m and not inside:
            inside, marker, cur, start, lang = True, m.group(2)[0], [], i + 1, m.group(3).lower()
            fenced.add(i)
            continue
        if m and inside and m.group(2)[0] == marker and not m.group(3):
            blocks.append({"start": start, "lang": lang, "body": cur})
            inside, cur = False, []
            fenced.add(i)
            continue
        if inside:
            fenced.add(i)
            cur.append(line)
    if inside:                                                  # unterminated fence
        blocks.append({"start": start, "lang": lang, "body": cur})
    return blocks, fenced


def steps_and_phases(lines, fenced):
    """Steps are the numbered items inside a `### Phase …` section — the shape the skill's
    template defines. Numbered lines inside a fenced block are pasted output, never steps."""
    phases, steps, phase_open, cur = [], [], False, None
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        if HEADING_RE.match(line):
            if cur:
                cur["end"] = i
                cur = None
            if PHASE_RE.match(line):
                phases.append({"line": i + 1, "text": line})
                phase_open = True
            else:
                phase_open = False
            continue
        if not phase_open:
            continue
        m = STEP_RE.match(line)
        if m:
            if cur:
                cur["end"] = i
            cur = {"n": m.group(1), "line": i + 1, "start": i, "end": len(lines)}
            steps.append(cur)
    if cur:
        cur["end"] = len(lines)
    for s in steps:
        s["body"] = "\n".join(lines[s["start"]:s["end"]])
    return phases, steps


def check_blocks(lines, blocks, path, findings, notes):
    """`bash -n` on every shell block, and shellcheck's errors when shellcheck exists."""
    sc = shutil.which("shellcheck")
    if sc:
        try:
            ver = subprocess.run([sc, "--version"], capture_output=True, text=True,
                                 timeout=20).stdout
            ver = next((l.split()[-1] for l in ver.splitlines() if l.startswith("version:")),
                       "unknown")
        except (OSError, subprocess.SubprocessError):
            ver = "unknown"
        notes.append("shellcheck %s present — error-severity findings are reported "
                     "(warnings/info are not: a runbook is not a program)" % ver)
    else:
        notes.append("shellcheck NOT installed — `bash -n` ran, the deeper pass did not. "
                     "Install shellcheck for it; its absence is never a failure here.")
    shell_blocks = [b for b in blocks if b["lang"] in BASH_LANGS]
    skipped = sorted({b["lang"] or "(no language)" for b in blocks if b["lang"] not in BASH_LANGS})
    if skipped:
        notes.append("%d non-shell block(s) not syntax-checked: %s"
                     % (len(blocks) - len(shell_blocks), ", ".join(skipped)))
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="runbook-lint-"))
    for n, b in enumerate(shell_blocks):
        src = ANGLE_WORD_RE.sub(lambda m: "__PH_%s__" % m.group(1).upper().replace("-", "_"),
                                "\n".join(b["body"]) + "\n")
        f = tmp / ("block%02d.sh" % n)
        f.write_text(src, encoding="utf-8")
        try:
            r = subprocess.run(["bash", "-n", str(f)], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError) as exc:
            notes.append("bash -n could not run (%s) — syntax was NOT checked" % exc)
            break
        if r.returncode != 0:
            for msg in [l for l in r.stderr.splitlines() if l.strip()][:3]:
                m = re.search(r"line (\d+):\s*(.*)", msg)
                off, why = (int(m.group(1)), m.group(2)) if m else (1, msg.strip())
                findings.append({"line": b["start"] + off, "rule": "bash-syntax",
                                 "message": "block fails `bash -n`: %s — a runbook block "
                                            "that will not parse cannot be pasted" % why})
        if sc:
            try:
                r = subprocess.run([sc, "-s", "bash", "-S", "error", "-f", "gcc", str(f)],
                                   capture_output=True, text=True, timeout=30)
            except (OSError, subprocess.SubprocessError):
                continue
            for out in r.stdout.splitlines():
                m = re.match(r"^[^:]+:(\d+):(\d+):\s*error:\s*(.*)$", out)
                if m:
                    findings.append({"line": b["start"] + int(m.group(1)), "rule": "shellcheck-error",
                                     "message": "shellcheck error: %s" % m.group(3)})
    shutil.rmtree(tmp, ignore_errors=True)
    return len(shell_blocks)


def lint(text, path):
    lines = text.splitlines()
    findings, notes = [], []
    blocks, fenced = scan(lines)
    phases, steps = steps_and_phases(lines, fenced)
    n_shell = check_blocks(lines, blocks, path, findings, notes)

    # ── structure: phases name a host, steps keep verify + rollback ──────────────────
    if not phases:
        findings.append({"line": 1, "rule": "no-phase-sections",
                         "message": "no `### Phase N — <name>` section found — the runbook "
                                    "shape this lint checks (steps, verifies, rollbacks) "
                                    "lives under phase headings"})
    for ph in phases:
        if not HOST_RE.search(ph["text"]):
            findings.append({"line": ph["line"], "rule": "phase-missing-host",
                             "message": "phase heading names no host (`· run on: <host>`) — "
                                        "the commonest runbook failure is the right command "
                                        "on the wrong machine"})
    for s in steps:
        if not VERIFY_RE.search(s["body"]):
            findings.append({"line": s["line"], "rule": "step-missing-verify",
                             "message": "step %s has no Verify line — a step whose 'done "
                                        "when' check is missing cannot be confirmed before "
                                        "the next one runs" % s["n"]})
        if not ROLLBACK_RE.search(s["body"]):
            findings.append({"line": s["line"], "rule": "step-missing-rollback",
                             "message": "step %s has no Rollback line — write the undo, or "
                                        "write `Rollback: none — <restore path>`; silence "
                                        "is not an answer at 2am" % s["n"]})

    # ── placeholders: every one used is defined in the values table ──────────────────
    declared, used = set(), {}
    for i, line in enumerate(lines):
        m = TABLE_ROW_RE.match(line)
        if m and i not in fenced:
            first = m.group(1).split("|")[0]
            declared.update(PLACEHOLDER_RE.findall(first))
            continue
        for tok in PLACEHOLDER_RE.findall(line):
            used.setdefault(tok, i + 1)
    for tok, ln in sorted(used.items(), key=lambda kv: kv[1]):
        if tok not in declared:
            findings.append({"line": ln, "rule": "placeholder-undeclared",
                             "message": "<%s> is used but never defined in the values table "
                                        "— an operator cannot fill in a placeholder nobody "
                                        "told them about" % tok})

    # ── destructive ops carry ⛔ at or above their line ──────────────────────────────
    step_at = {}
    for s in steps:
        for i in range(s["start"], s["end"]):
            step_at[i] = s
    for i, line in enumerate(lines):
        hits = [name for name, rx in DESTRUCTIVE if rx.search(line)]
        m = RM_RE.search(line)
        if m and rm_is_recursive_force(m.group(1)):
            hits.insert(0, "rm -rf")
        if not hits:
            continue
        s = step_at.get(i)
        window = lines[s["start"]:i + 1] if s else lines[max(0, i - 5):i + 1]
        if any(STOP in w for w in window):
            continue
        findings.append({"line": i + 1, "rule": "destructive-unmarked",
                         "message": "%s runs with no %s warning above it%s — flag it, say "
                                    "what to back up first, and give the restore path"
                                    % (hits[0], STOP,
                                       " (step %s)" % s["n"] if s else "")})

    # ── credential shapes: chatroom's classes, never a second list ───────────────────
    screen, note = load_screen()
    notes.append(note)
    if screen:
        seen = set()
        for i, line in enumerate(lines):
            for cls in screen(line):
                if cls in seen:
                    continue
                seen.add(cls)
                findings.append({"line": i + 1, "rule": "secret-shape",
                                 "message": "matches secret-shape class '%s' — the matching "
                                            "text is deliberately not echoed. Replace it with "
                                            "a placeholder or an env var and rotate it if it "
                                            "was ever real." % cls})
        for cls in screen(text):
            if cls not in seen:
                seen.add(cls)
                findings.append({"line": 1, "rule": "secret-shape",
                                 "message": "matches secret-shape class '%s' across lines — "
                                            "text not echoed" % cls})
    findings.sort(key=lambda f: (f["line"], f["rule"]))
    return findings, notes, {"steps": len(steps), "phases": len(phases),
                             "blocks": len(blocks), "shell_blocks": n_shell,
                             "placeholders": len(used), "declared": len(declared)}


def main():
    ap = argparse.ArgumentParser(
        description="lint a runbook before a human pastes it into production")
    ap.add_argument("runbook")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="findings only, no notes/summary")
    a = ap.parse_args()
    p = pathlib.Path(a.runbook)
    if not p.is_file():
        die("no such runbook: %s" % p)
    findings, notes, stats = lint(p.read_text(encoding="utf-8", errors="replace"), str(p))
    if a.json:
        print(json.dumps({"runbook": str(p), "stats": stats, "notes": notes,
                          "findings": findings,
                          "verdict": "FINDINGS" if findings else "CLEAN"}, indent=2))
    else:
        if not a.quiet:
            for n in notes:
                print("note: %s" % n)
        for f in findings:
            print("FINDING  %s:%d  [%s]  %s" % (p, f["line"], f["rule"], f["message"]))
        if not a.quiet:
            print("runbook_lint: %d step(s) in %d phase(s), %d shell block(s), %d "
                  "placeholder(s) — %s"
                  % (stats["steps"], stats["phases"], stats["shell_blocks"],
                     stats["placeholders"],
                     "%d finding(s)" % len(findings) if findings else "clean"))
    sys.exit(5 if findings else 0)


if __name__ == "__main__":
    main()
