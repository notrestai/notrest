#!/bin/bash
# fixture.sh — asserts brief.py (a minted brief pins the bytes and stamps the budget)
# and verdict_lint.py (a good report passes; each way of breaking the grammar is caught).
# Self-relative; writes only inside its own mktemp dir; spawns no lane and calls no model.
# Usage: bash <refuter-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
D="$(cd "$(dirname "$0")" && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -q -- "$2" "$1"; then ok "$3"; else no "$3 — [$2] not in $1"; fi; }
hasnt(){ if grep -q -- "$2" "$1"; then no "$3"; else ok "$3"; fi; }

# ── A · brief.py ─────────────────────────────────────────────────────────────────────
echo "── A · brief"
cat > "$W/target.sh" <<'EOF'
#!/bin/bash
# the artifact under review
git push origin main | tail -1
echo "PARITY PASS 5/5"
EOF
SHA="$(python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$W/target.sh")"
python3 "$D/brief.py" --target "$W/target.sh" --budget 9 --minutes 15 \
  --scratch "$W/scratch" > "$W/b.md" 2>"$W/b.err"
t "brief exits 0" "$?" "0"
has "$W/b.md" "You are a REFUTER lane" "carries the template's role framing"
has "$W/b.md" "$SHA" "pins the target's sha256"
has "$W/b.md" "git push origin main" "inlines the artifact's bytes"
has "$W/b.md" "$W/scratch" "names the isolated scratch dir"
[ -d "$W/scratch" ] && ok "minted the scratch dir" || no "scratch dir not created"
has "$W/b.md" "~9 tool calls, 15 minutes." "stamps the budget it was given"
has "$W/b.md" "Never push, install, publish" "keeps the hard prohibitions"
has "$W/b.md" "SEAT MUST FILL" "flags the fields only the seat can write"
has "$W/b.err" "still need the SEAT" "says so on stderr too"
t "all 7 sections present" "$(grep -c '^## [1-7]\.' "$W/b.md")" "7"
python3 "$D/brief.py" --target "$W/target.sh" --scratch "$W/s2" \
  --contract "It must never push when the validator failed." \
  --priorities "$W/target.sh" > "$W/b2.md" 2>"$W/b2.err"
t "a filled brief exits 0" "$?" "0"
has "$W/b2.md" "never push when the validator failed" "uses the seat's contract paragraph"
hasnt "$W/b2.md" "SEAT MUST FILL" "no unfilled markers when both fields are given"
has "$W/b2.err" "complete — every field filled" "says the brief is complete"
python3 "$D/brief.py" --target "$W/target.sh" --scratch "$W/s3" --strict >/dev/null 2>&1
t "--strict refuses a half-filled brief (exit 5)" "$?" "5"
python3 "$D/brief.py" --target "$W/nope.sh" >/dev/null 2>&1
t "a missing target exits 2" "$?" "2"
python3 "$D/brief.py" --target "$W/target.sh" --scratch "$W/s4" --no-inline > "$W/b3.md" 2>&1
has "$W/b3.md" "may change under you" "--no-inline warns the bytes are unpinned"
hasnt "$W/b3.md" "git push origin main" "--no-inline does not paste the artifact"

# ── B · verdict_lint.py: the good report ────────────────────────────────────────────
echo "── B · lint accepts a report that meets the grammar"
cat > "$W/good.md" <<'EOF'
MODEL: claude-opus-4

1. **CONFIRMED · breaks-irreversible-safety** — `ship.sh:41` pushes despite a failed validator.

The guard string-matches "command not found" and treats it as "CLI absent, proceed":

```
$ bash ship.sh --dry-run
validator: command not found
proceeding: validator absent
+ git push origin main
```

Repair spec: check the exit code, not the message.

2. **PLAUSIBLE · breaks-claim-honesty** — the "5/5 PARITY PASS" denominator is unaudited.

If two of the five surfaces are algebraic round-trips and the largest text clause is never
compared, then the banner reports 5/5 while three surfaces went unchecked — the seat would
ship on a claim that is false.

I stopped here because reproducing it needs the real remote.

**SURVIVED** — attacked the exit-code path in the install branch with a forced non-zero:
it aborted correctly. Attacked the tombstone pin with a key reorder: re-asserted after write.

**Budget spent** — 9 of ~12 tool calls; did not reach rung 6 (environment assumptions).
EOF
python3 "$D/verdict_lint.py" "$W/good.md" > "$W/g.txt" 2>&1
t "a well-formed report exits 0" "$?" "0"
has "$W/g.txt" "grammar clean" "says the grammar is clean"
has "$W/g.txt" "1 CONFIRMED" "typed the CONFIRMED finding"
has "$W/g.txt" "2 PLAUSIBLE" "typed the PLAUSIBLE finding"
python3 "$D/verdict_lint.py" "$W/good.md" --json > "$W/g.json" 2>&1
t "--json exits 0 too" "$?" "0"
t "--json verdict is ACCEPT" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['verdict'])" "$W/g.json")" "ACCEPT"

# ── C · verdict_lint.py: each way of breaking the grammar ────────────────────────────
echo "── C · lint rejects what the grammar forbids"
bad(){ python3 "$D/verdict_lint.py" "$1" > "$W/r.txt" 2>&1; echo $?; }

sed '/^```$/,/^```$/d' "$W/good.md" > "$W/no-repro.md"
t "CONFIRMED without a pasted reproduction is rejected" "$(bad "$W/no-repro.md")" "5"
has "$W/r.txt" "no fenced command+output block" "names the missing reproduction"

cat > "$W/no-scenario.md" <<'EOF'
1. **PLAUSIBLE · degrades** — the parser feels fragile.
Nothing else to add.
**SURVIVED** — nothing else attacked.
**Budget spent** — 3 of ~12 tool calls.
EOF
t "PLAUSIBLE without a scenario is rejected" "$(bad "$W/no-scenario.md")" "5"
has "$W/r.txt" "no failure scenario" "names the missing scenario"

cat > "$W/neither.md" <<'EOF'
1. **breaks-claim-honesty** — this could be fragile under load, worth a look.
**SURVIVED** — the exit-code path held.
**Budget spent** — 4 of ~12 tool calls.
EOF
t "a finding that is neither CONFIRMED nor PLAUSIBLE is rejected" "$(bad "$W/neither.md")" "5"
has "$W/r.txt" "neither CONFIRMED nor PLAUSIBLE" "names the untyped finding"

grep -v "SURVIVED" "$W/good.md" > "$W/no-survived.md"
t "a report with no SURVIVED section is rejected" "$(bad "$W/no-survived.md")" "5"
has "$W/r.txt" "no SURVIVED section" "names the missing SURVIVED list"

grep -v "Budget spent" "$W/good.md" | grep -v "tool calls" > "$W/no-budget.md"
t "a report with no budget line is rejected" "$(bad "$W/no-budget.md")" "5"
has "$W/r.txt" "no budget line" "names the missing budget"

python3 "$D/verdict_lint.py" "$W/missing.md" >/dev/null 2>&1
t "a missing report file exits 2" "$?" "2"

# the linter must not be fooled by a numbered line inside pasted output
cat > "$W/fenced-numbers.md" <<'EOF'
1. **CONFIRMED · degrades** — the installer renumbers its own steps.

```
$ bash install.sh
1) preparing
2) linking
error: exit 1
```

**SURVIVED** — the push guard held under a forced non-zero.
**Budget spent** — 5 of ~12 tool calls.
EOF
t "numbered lines inside a fenced block do not become findings" "$(bad "$W/fenced-numbers.md")" "0"
t "and the real finding is still counted" "$(grep -c '1 finding' "$W/r.txt")" "1"

echo
echo "refuter fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
