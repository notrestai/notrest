#!/bin/bash
# fixture.sh — asserts starthere_lint.py: a contract-shaped START-HERE passes; each of the
# five FAIL rules fires on its own injected defect and ONLY its own; the F-20 shape (status
# + read-order + "Run it", no resume instruction) is caught; the clean-clone rule catches a
# command standing on a gitignored artifact and clears one that is recreated in-file;
# heading variants the estate really writes are accepted; --fix-hint writes nothing; exit
# codes 0/5/6/2 hold.
# Self-relative; writes only inside its own mktemp dir; spawns no lane and calls no model.
# Usage: bash <sessionend-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
D="$(cd "$(dirname "$0")" && pwd)"
L="$D/starthere_lint.py"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -q -- "$2" "$1"; then ok "$3"; else no "$3 — [$2] not in $1"; fi; }
hasnt(){ if grep -q -- "$2" "$1"; then no "$3"; else ok "$3"; fi; }
# run the lint over $1 with root $W; stdout to $W/out.txt; echoes the exit code
run(){ python3 "$L" check --file "$1" --root "$W" > "$W/out.txt" 2>&1; echo $?; }
nfails(){ grep -c '^FAIL' "$W/out.txt"; }

# a project tree the resume files can honestly cite
mkdir -p "$W/docs" "$W/src"
printf '# ledger\n- line\n' > "$W/COORD.md"
printf '# handoff\n' > "$W/HANDOFF.md"
printf '# state\n' > "$W/STATE.md"
printf '# foundation\n' > "$W/CLAUDE.md"
printf 'print(1)\n' > "$W/src/app.py"
printf 'echo ok\n' > "$W/run.sh"

# ── A · a contract-shaped START-HERE passes ─────────────────────────────────────────────
echo "── A · the good file"
cat > "$W/good.md" <<'EOF'
# Start Here — demo project
**Status in one line:** shipped at v1.4.0 (commit a1b2c3d), instruments green.

## Read these first, in order
1. HANDOFF.md — where we are and what's next
2. COORD.md — the ledger tail; when prose disagrees, the ledger wins
3. STATE.md — decisions + code, newest on top
4. CLAUDE.md — the foundation

## Then do this, in order
1. Run `bash run.sh` — expect it to print `ok` and exit 0.
2. Read `src/app.py` and finish the half-written parser; verify with the fixture.

## Watch out for
- The ledger is append-only; corrections are appended, never edited.
EOF
t "a contract-shaped START-HERE exits 0" "$(run "$W/good.md")" "0"
has "$W/out.txt" "PASS" "reports PASS"
has "$W/out.txt" "next-action: heading" "found the next-action section"
has "$W/out.txt" "state anchor" "named the state anchor"
has "$W/out.txt" "0 model tokens" "states the zero-token claim"

# ── B · each FAIL rule fires on its own defect, and ONLY its own ─────────────────────────
echo "── B · the four rules, isolated"

# B1 · NO-NEXT-ACTION — status and a read-order, no resume instruction
cat > "$W/no-next.md" <<'EOF'
# Start Here — demo project
**Status in one line:** shipped at v1.4.0, instruments green.

## Read these first, in order
1. HANDOFF.md — where we are
2. COORD.md — the ledger tail
3. STATE.md — decisions + code

## Where the project stands
- T1 is done. T2 shipped. T3 is in flight as of the ledger's tail.
EOF
t "NO-NEXT-ACTION fires (exit 6)" "$(run "$W/no-next.md")" "6"
has "$W/out.txt" "NO-NEXT-ACTION" "names the rule"
t "and it is the ONLY rule that fires" "$(nfails)" "1"
has "$W/out.txt" "record F-20" "cites the record that earned the rule"

# B2 · NEXT-ACTION-NOT-ACTIONABLE — the section exists, wearing status prose
cat > "$W/costume.md" <<'EOF'
# Start Here — demo project
**Status in one line:** v1.4.0, instruments green.

## Read these first, in order
1. COORD.md — the ledger tail
2. HANDOFF.md — the snapshot

## Next steps
The build is currently in flight. T3 remains unfinished and the connector is blocked on
the owner, who alone can clear it. Everything else is proceeding normally.
EOF
t "NEXT-ACTION-NOT-ACTIONABLE fires (exit 6)" "$(run "$W/costume.md")" "6"
has "$W/out.txt" "NEXT-ACTION-NOT-ACTIONABLE" "names the rule"
t "and it is the ONLY rule that fires" "$(nfails)" "1"
hasnt "$W/out.txt" "NO-NEXT-ACTION " "does not also light NO-NEXT-ACTION (the section exists)"
has "$W/out.txt" "costume" "explains the defect in the law text"

# B3 · DEAD-REFERENCE — a cited path that is not there
cat > "$W/dead.md" <<'EOF'
# Start Here — demo project
**Status in one line:** v1.4.0, instruments green.

## Read these first, in order
1. COORD.md — the ledger tail
2. HANDOFF.md — the snapshot

## Then do this, in order
1. Run `bash run.sh` — expect `ok`.
2. Read `docs/DESIGN-NOTE.md` and finish the section it marks TODO.
EOF
t "DEAD-REFERENCE fires (exit 6)" "$(run "$W/dead.md")" "6"
has "$W/out.txt" "DEAD-REFERENCE" "names the rule"
has "$W/out.txt" "line 10" "reports the line number of the dead path"
has "$W/out.txt" "docs/DESIGN-NOTE.md" "names the dead path"
t "and it is the ONLY rule that fires" "$(nfails)" "1"
hasnt "$W/out.txt" "NO-STATE-ANCHOR" "a dead path does not also light NO-STATE-ANCHOR"

# a dead path whose basename lives elsewhere is told where to look
mkdir -p "$W/tools/inner"
printf 'x\n' > "$W/tools/inner/build.sh"
cat > "$W/moved.md" <<'EOF'
# Start Here — demo project
**Status:** v1.4.0
## Read these first
1. COORD.md — the ledger tail
## Then do this, in order
1. Run `build.sh` — expect exit 0.
EOF
t "a misplaced path still fails" "$(run "$W/moved.md")" "6"
has "$W/out.txt" "tools/inner/build.sh" "names where the cited file actually lives"

# one path cited many times is ONE finding, not a pile
cat > "$W/repeat.md" <<'EOF'
# Start Here — demo project
**Status:** v1.4.0
## Read these first
1. COORD.md — the ledger tail
## Then do this, in order
1. Open `docs/GONE.md` — expect the TODO section.
2. Finish `docs/GONE.md`, then re-read `docs/GONE.md` to check it.
EOF
t "a repeated dead path still fails" "$(run "$W/repeat.md")" "6"
t "but is reported ONCE, not per citation" "$(nfails)" "1"
has "$W/out.txt" "cited on 2 lines" "counts the citation lines"
has "$W/out.txt" "first at line 6" "points at the first citation"

# B4 · NO-STATE-ANCHOR — actionable, all paths real, but no trail named
cat > "$W/no-anchor.md" <<'EOF'
# Start Here — demo project
**Status in one line:** v1.4.0, instruments green.

## Then do this, in order
1. Run `bash run.sh` — expect it to print `ok`.
2. Read `src/app.py` and finish the parser; verify it exits 0.
EOF
t "NO-STATE-ANCHOR fires (exit 6)" "$(run "$W/no-anchor.md")" "6"
has "$W/out.txt" "NO-STATE-ANCHOR" "names the rule"
t "and it is the ONLY rule that fires" "$(nfails)" "1"

# ── C · the F-20 regression: "Run it" is not a resume instruction ────────────────────────
echo "── C · the F-20 shape"
cat > "$W/f20.md" <<'EOF'
# START HERE — demo product

**What this is.** The product spec of record is `docs/SPEC.md`.

## Read these, in this order
1. **`COORD.md`** — the ledger. Its tail is the current truth.
2. **`docs/SPEC.md`** — the product spec.

## Where the project stands
- **T1 (the spike) — DONE.** Graded with receipts.
- **T2 (the shell) — SHIPPED.** Fixture 231/0.
- **T3 (the connector) — IN FLIGHT** as of the ledger's tail.

## Run it

```bash
bash run.sh --port 8780 --no-open
```

## The laws that travel with this repo
Evidence or say "unverified" — "should work" is banned.
EOF
printf '# spec\n' > "$W/docs/SPEC.md"
t "the F-20 shape fails (exit 6)" "$(run "$W/f20.md")" "6"
has "$W/out.txt" "NO-NEXT-ACTION" "caught the exact defect the cross-model test found"
t "one rule, not a pile" "$(nfails)" "1"
hasnt "$W/out.txt" "NEXT-ACTION-NOT-ACTIONABLE" "a 'Run it' section is not counted as the resume instruction"

# ── D · heading-variant acceptance (real shapes, not one rigid heading) ──────────────────
echo "── D · heading variants the estate really writes"
variant(){ # $1 = heading line, $2 = label
  cat > "$W/v.md" <<EOF
# Start Here — demo project
**Status in one line:** v1.4.0.

## Read these first, in order
1. COORD.md — the ledger tail

$1
1. Run \`bash run.sh\` — expect \`ok\` and exit 0.
2. Read \`src/app.py\`; verify the fixture passes.
EOF
  t "$2" "$(run "$W/v.md")" "0"
}
variant '## Then do this, in order'            "accepts the shipped template heading"
variant '## NEXT ACTION — do this first'       "accepts NEXT ACTION (the post-F-20 repair)"
variant '## Next steps'                        "accepts Next steps"
variant '## To resume work (the current arrangement)' "accepts a Resume heading"
variant '## ⚠️ FIRST ACTION — the LIVE BLOCKER' "accepts an emoji-led FIRST ACTION heading"
variant '**Next:**'                            "accepts a bold pseudo-heading"

# a bare numbered do-list with no heading over it still counts
cat > "$W/bare-list.md" <<'EOF'
# Start Here — demo project
**Status in one line:** v1.4.0. The ledger is COORD.md.

1. Run `bash run.sh` — expect `ok` and exit 0.
2. Read `src/app.py` and finish the parser.
EOF
t "a bare numbered do-list satisfies the rule" "$(run "$W/bare-list.md")" "0"

# but a read-order list alone does NOT — reading is not doing
cat > "$W/read-only.md" <<'EOF'
# Start Here — demo project
**Status in one line:** v1.4.0.

## Read these first, in order
1. Read COORD.md — the ledger tail
2. Read HANDOFF.md — the snapshot
3. Read STATE.md — decisions
EOF
t "a read-order list alone does not satisfy it" "$(run "$W/read-only.md")" "6"
has "$W/out.txt" "NO-NEXT-ACTION" "reading is not doing"

# ── E · warnings never fail (exit 5) ────────────────────────────────────────────────────
echo "── E · the warn tier"
cat > "$W/warn.md" <<'EOF'
# Start Here — demo project
**Status in one line:** the parser rewrite landed.

## Read these first, in order
1. COORD.md — the ledger tail

## Then do this, in order
1. Run `bash run.sh`.
2. Read `src/app.py` and finish the parser.
EOF
t "warnings alone exit 5, never 6" "$(run "$W/warn.md")" "5"
has "$W/out.txt" "NO-VERSION-ANCHOR" "warns on a missing version/commit anchor"
has "$W/out.txt" "NO-DONE-CONDITION" "warns on a next-action with no done-condition"
t "no FAIL lines in a warn-only run" "$(nfails)" "0"

# ── F · --json shape ────────────────────────────────────────────────────────────────────
echo "── F · --json"
python3 "$L" check --file "$W/dead.md" --root "$W" --json > "$W/j.json" 2>&1
t "--json exits 6 on a failing file" "$?" "6"
jq_(){ python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(eval(sys.argv[2],{'d':d}))" "$W/j.json" "$1"; }
t "--json verdict is FAIL" "$(jq_ "d['verdict']")" "FAIL"
t "--json names the rule" "$(jq_ "d['fails'][0]['rule']")" "DEAD-REFERENCE"
t "--json carries the line number" "$(jq_ "d['fails'][0]['line']")" "10"
t "--json carries the law text with the finding" "$(jq_ "'runnable exactly as written' in d['fails'][0]['law']")" "True"
t "--json publishes all five rules" "$(jq_ "len(d['rules'])")" "5"
t "--json publishes the warn rules" "$(jq_ "len(d['warn_rules'])")" "3"
t "--json carries notes" "$(jq_ "len(d['notes'])>0")" "True"
python3 "$L" check --file "$W/good.md" --root "$W" --json > "$W/j2.json" 2>&1
t "--json on a clean file exits 0" "$?" "0"
t "--json verdict is PASS" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['verdict'])" "$W/j2.json")" "PASS"

# ── G · --fix-hint prints, never writes ─────────────────────────────────────────────────
echo "── G · --fix-hint is print-only"
SUM_BEFORE="$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$W/no-next.md")"
python3 "$L" check --file "$W/no-next.md" --root "$W" --fix-hint > "$W/hint.txt" 2>&1
t "--fix-hint keeps the verdict's exit code" "$?" "6"
SUM_AFTER="$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$W/no-next.md")"
t "the linted file is byte-identical after --fix-hint" "$SUM_AFTER" "$SUM_BEFORE"
has "$W/hint.txt" "Then do this, in order" "printed the skeleton"
has "$W/hint.txt" "never writes" "says plainly that it does not write"
t "no file was created beside it" "$(ls "$W"/no-next.md* | wc -l | tr -d ' ')" "1"
python3 "$L" check --fix-hint > "$W/hint2.txt" 2>&1
t "--fix-hint alone (no --file) exits 0" "$?" "0"
has "$W/hint2.txt" "Watch out for" "the skeleton stands alone"

# ── H · usage errors exit 2 ─────────────────────────────────────────────────────────────
echo "── H · usage"
python3 "$L" check --file "$W/nope.md" --root "$W" >/dev/null 2>&1
t "a missing file exits 2" "$?" "2"
python3 "$L" check --file "$W/good.md" --root "$W/nowhere" >/dev/null 2>&1
t "a missing root exits 2" "$?" "2"
python3 "$L" check --root "$W" >/dev/null 2>&1
t "check with neither --file nor --fix-hint exits 2" "$?" "2"

# ── J · the clean-clone rule (record F-20's defect class, second bite: rig.rest) ─────────
# The lint proved a path was PRESENT; it never proved a command was RUNNABLE BY A STRANGER.
# Everything above runs with --root "$W", which is NOT a git repo — so the rule is skipped
# there and the older asserts keep the behaviour they were written against. These run
# against a real scratch repo with real ignore rules.
echo "── J · the clean-clone rule"
G="$W/clone-repo"
git init -q "$G" 2>/dev/null
printf '/.engine/\n/.venv/\ntracked-anyway.md\n' > "$G/.gitignore"
mkdir -p "$G/.engine/plugins" "$G/.venv/bin" "$G/shell"
printf 'print(1)\n' > "$G/.engine/plugins/index.py"
printf '#!/bin/sh\n'  > "$G/.venv/bin/python"
printf '# ledger\n'   > "$G/COORD.md"
printf '# handoff\n'  > "$G/HANDOFF.md"
printf 'echo ok\n'    > "$G/run.sh"
printf '# readme\n'   > "$G/shell/README.md"
printf '# tracked\n'  > "$G/tracked-anyway.md"
git -C "$G" add -f .gitignore tracked-anyway.md COORD.md >/dev/null 2>&1
git -C "$G" -c user.email=f@x -c user.name=fixture commit -qm init >/dev/null 2>&1
rung(){ python3 "$L" check --file "$1" --root "$G" > "$W/out.txt" 2>&1; echo $?; }
# $1 = the body that follows the shared, contract-shaped head
mkjd(){ { printf '# Start Here — clone demo\n**Status in one line:** v2.0.0 (commit a1b2c3d).\n\n## Read these first, in order\n1. COORD.md — the ledger tail\n\n'; cat; } > "$W/j.md"; }

# J1 · a command standing on a gitignored dir, with no recreate step anywhere
mkjd <<'EOF'
## Then do this, in order
1. Run `python3 .engine/plugins/index.py track` — expect exit 0.
EOF
t "UNRUNNABLE-FROM-CLEAN-CLONE fires (exit 6)" "$(rung "$W/j.md")" "6"
has "$W/out.txt" "UNRUNNABLE-FROM-CLEAN-CLONE" "names the rule"
has "$W/out.txt" ".engine" "names the gitignored artifact"
has "$W/out.txt" "FRESH CLONE WILL NOT HAVE IT" "says plainly what a stranger gets"
t "and it is the ONLY rule that fires" "$(nfails)" "1"
hasnt "$W/out.txt" "DEAD-REFERENCE" "the path is present here, so DEAD-REFERENCE stays quiet"

# J1b · --fix-hint hands back the missing recreate skeleton
python3 "$L" check --file "$W/j.md" --root "$G" --fix-hint > "$W/jhint.txt" 2>&1
t "--fix-hint keeps the FAIL exit code" "$?" "6"
has "$W/jhint.txt" "A fresh clone needs this first" "printed the recreate skeleton"
has "$W/jhint.txt" "gitignored" "the skeleton says why the step is needed"

# J2 · the same file, with the recreate command present in-file → clean
mkjd <<'EOF'
## A fresh clone needs this first
```bash
git -C /elsewhere worktree add .engine abc1234
```

## Then do this, in order
1. Run `python3 .engine/plugins/index.py track` — expect exit 0.
EOF
t "a recreate command in the file clears the rule (exit 0)" "$(rung "$W/j.md")" "0"
has "$W/out.txt" "recreates it" "the note says which line recreates it"
hasnt "$W/out.txt" "UNRUNNABLE" "no finding when the bootstrap is present"

# J3 · the recreate step exists only as a POINTER to another file → WARN, never FAIL
mkjd <<'EOF'
`.engine` is created by the bootstrap — see `shell/README.md` for the instructions.

## Then do this, in order
1. Run `python3 .engine/plugins/index.py track` — expect exit 0.
EOF
t "a pointer to another file WARNS, not FAILS (exit 5)" "$(rung "$W/j.md")" "5"
has "$W/out.txt" "RECREATE-ELSEWHERE" "names the warn rule"
has "$W/out.txt" "shell/README.md" "names the file it outsources to"
t "no FAIL line — the pointer is at least honest" "$(nfails)" "0"

# J4 · a cited path that is NOT ignored behaves exactly as before (no false positive)
mkjd <<'EOF'
## Then do this, in order
1. Run `bash run.sh` — expect `ok` and exit 0.
2. Read `shell/README.md`; verify it names the port.
EOF
t "a tracked path fires nothing (exit 0)" "$(rung "$W/j.md")" "0"
hasnt "$W/out.txt" "UNRUNNABLE" "no finding for a path a clone will carry"
has "$W/out.txt" "no instruction stands on a gitignored artifact" "says so in the notes"

# J5 · a file matching an ignore pattern but TRACKED anyway is still in the clone
mkjd <<'EOF'
## Then do this, in order
1. Read `tracked-anyway.md` — expect the TODO list; then run `bash run.sh`.
EOF
t "a tracked-but-ignored-pattern file is not flagged (exit 0)" "$(rung "$W/j.md")" "0"
hasnt "$W/out.txt" "UNRUNNABLE" "git check-ignore is index-aware, and so is the rule"

# J6 · a PROSE mention of an ignored dir is not an instruction (the rig sessions/ shape)
mkjd <<'EOF'
`.engine` and `.venv` are gitignored, so this repo's clone carries neither of them.

## Then do this, in order
1. Run `bash run.sh` — expect `ok` and exit 0.
EOF
t "prose that merely MENTIONS an ignored path fires nothing (exit 0)" "$(rung "$W/j.md")" "0"
hasnt "$W/out.txt" "UNRUNNABLE" "the rule reads instructions, not prose"

# J7 · the vacuous pass, caught live against rig.rest before this assert existed: a line
# that USES two ignored artifacts must never count as the line that CREATES one, even
# though `.venv` carries the word "venv" inside its own name.
mkjd <<'EOF'
## Then do this, in order
1. Run `.venv/bin/python .engine/plugins/index.py track` — expect exit 0.
EOF
t "a use-line does not recreate what it uses (exit 6)" "$(rung "$W/j.md")" "6"
t "both artifacts are reported, neither self-cleared" "$(nfails)" "2"
has "$W/out.txt" "\.venv is gitignored" "the artifact's own name is not a creation signal"
has "$W/out.txt" "\.engine is gitignored" "and neither is its neighbour's"

# J8 · DISJOINTNESS — a path both gitignored AND absent is DEAD-REFERENCE, never rule 5.
# Decided deliberately: it is already broken HERE, which is the plainer, more urgent thing
# to say, and it keeps the older rule's behaviour exactly as fixtured.
mkjd <<'EOF'
## Then do this, in order
1. Run `python3 .engine/plugins/GONE.py track` — expect exit 0.
EOF
t "an ignored AND missing path fails (exit 6)" "$(rung "$W/j.md")" "6"
t "exactly one rule fires" "$(nfails)" "1"
has "$W/out.txt" "DEAD-REFERENCE" "and it is DEAD-REFERENCE"
hasnt "$W/out.txt" "UNRUNNABLE" "rule 5 judges only paths that exist"

# J9 · a non-git root: the rule SKIPS honestly and every other rule still runs
mkjd <<'EOF'
## Then do this, in order
1. Run `python3 .engine/plugins/index.py track` — expect exit 0.
EOF
t "a non-git root still produces a verdict (exit 6)" "$(run "$W/j.md")" "6"
has "$W/out.txt" "clean-clone check SKIPPED" "the skip is reported, never a silent pass"
hasnt "$W/out.txt" "UNRUNNABLE" "no guessing about ignore rules without a repo"
has "$W/out.txt" "DEAD-REFERENCE" "the other rules still run"

# J10 · --json publishes the new rule with its finding
mkjd <<'EOF'
## Then do this, in order
1. Run `python3 .engine/plugins/index.py track` — expect exit 0.
EOF
python3 "$L" check --file "$W/j.md" --root "$G" --json > "$W/j3.json" 2>&1
t "--json exits 6 on the new rule" "$?" "6"
jq3(){ python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(eval(sys.argv[2],{'d':d}))" "$W/j3.json" "$1"; }
t "--json names the new rule" "$(jq3 "d['fails'][0]['rule']")" "UNRUNNABLE-FROM-CLEAN-CLONE"
t "--json carries its law text" "$(jq3 "'fresh clone' in d['fails'][0]['law']")" "True"

# ── I · the instrument never touches what it judges ─────────────────────────────────────
echo "── I · read-only against this repo's real START-HERE"
REPO="$(cd "$D/../../../../.." && pwd)"
if [ -f "$REPO/START-HERE.md" ]; then
  B="$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$REPO/START-HERE.md")"
  python3 "$L" check --file "$REPO/START-HERE.md" --root "$REPO" > "$W/real.txt" 2>&1
  RC=$?
  A="$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$REPO/START-HERE.md")"
  t "the repo's own START-HERE is byte-identical after linting" "$A" "$B"
  case "$RC" in 0|5|6) ok "the repo's own START-HERE produces a verdict (exit $RC)";;
    *) no "unexpected exit $RC on the repo's own START-HERE";; esac
  has "$W/real.txt" "starthere_lint:" "printed a verdict line"
  echo "        (informational — this repo's verdict: $(grep '^starthere_lint:' "$W/real.txt"))"
else
  ok "no repo START-HERE.md to check (skipped)"
fi

echo
echo "sessionend fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
