#!/bin/bash
# fixture.sh — asserts starthere_lint.py: a contract-shaped START-HERE passes; each of the
# four FAIL rules fires on its own injected defect and ONLY its own; the F-20 shape (status
# + read-order + "Run it", no resume instruction) is caught; heading variants the estate
# really writes are accepted; --fix-hint writes nothing; exit codes 0/5/6/2 hold.
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
t "--json publishes all four rules" "$(jq_ "len(d['rules'])")" "4"
t "--json publishes the warn rules" "$(jq_ "len(d['warn_rules'])")" "2"
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
