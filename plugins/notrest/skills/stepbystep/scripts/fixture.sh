#!/bin/bash
# fixture.sh — asserts plan_lint.py: a converged plan passes, every way of breaking the
# ordering/verification grammar is caught with its step number, and `converge` measures a
# known pair instead of taking the loop's word for it.
# Self-relative; writes only inside its own mktemp dir; spawns no lane and calls no model.
# Usage: bash <stepbystep-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
D="$(cd "$(dirname "$0")" && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
L="$D/plan_lint.py"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -q -- "$2" "$1"; then ok "$3"; else no "$3 — [$2] not in $1"; fi; }
hasnt(){ if grep -q -- "$2" "$1"; then no "$3"; else ok "$3"; fi; }
run(){ python3 "$L" check "$1" > "$W/out.txt" 2>&1; echo $?; }
edit(){ python3 -c "
import pathlib,sys
p=pathlib.Path(sys.argv[1]); t=p.read_text()
assert sys.argv[2] in t, 'fixture edit found no anchor: %s' % sys.argv[2]
pathlib.Path(sys.argv[4]).write_text(t.replace(sys.argv[2], sys.argv[3], 1))" "$@"; }

# ── A · a plan that converged and says so ────────────────────────────────────────────
echo "── A · the good plan"
cat > "$W/good.md" <<'EOF'
# Migrate the production database to PostgreSQL — Action Plan

## 📌 Read Me First
- **The goal:** run on Postgres 16 with under 20 minutes of downtime.

## At a Glance
- **Overall confidence:** Medium
- **How this was built:** 3 deep-research iterations; converged

## The Plan
Ordered phases. Each step carries its flags.

### Phase 1 — Prepare
1. **Provision the Postgres primary.** Done when: `psql -c 'select 1'` answers from the app host. [reversible] · confidence [H]
   - depends on: nothing
2. **Set up logical replication.** Done when: `pg_stat_replication` shows one active subscriber and lag under 1s. confidence [M]
   - depends on: step 1

### Phase 2 — Cutover
3. **Announce the maintenance window.** Done when: the notice is posted and support has acked it. confidence [H]
   - depends on: nothing
4. **Switch the connection string and deploy.** Done when: the app boots, health checks pass, and a read-and-write smoke test across three core tables succeeds. [ONE-WAY] (rolling back means re-syncing every row written after cutover) · [high-risk] · confidence [M] — rises to [H] once the staging dry-run passes.
   - depends on: step 2; step 3
5. **Decommission the legacy instance.** Done when: the old host is powered off and its snapshot is retained. [ONE-WAY] · confidence [L]
   - depends on: step 4

## Checkpoints
- **After step 4:** verify error rates for 30 minutes before proceeding.

## If Things Go Wrong
- **Replication lag spikes:** hold the window. Rollback for step 5: none — the retained snapshot is the only restore path.

## Confidence
- **Overall:** M. **Convergence:** converged after 3 iterations.
- **Low-confidence steps:** step 5 — mitigation: expert sign-off plus 90-day snapshot retention before power-off; rises to M once retention lands.

## Sources
1. https://www.postgresql.org/docs/16/logical-replication.html [cited]
2. https://example.com/ops-brief [from docs]
EOF
t "a plan that meets the grammar exits 0" "$(run "$W/good.md")" "0"
has "$W/out.txt" "clean" "says the plan is clean"
has "$W/out.txt" "5 step(s)" "counted the steps"
has "$W/out.txt" "2 \[ONE-WAY\]" "counted the one-way doors"
has "$W/out.txt" "1 Low" "counted the Low-confidence steps"
hasnt "$W/out.txt" "FINDING" "a clean plan prints no findings"
ok "the numbered Sources list was not mistaken for steps (5 steps, not 7)"
ok "a [ONE-WAY] whose rollback lives in 'If Things Go Wrong' is accepted (step 5)"
ok "a Low step whose mitigation lives in the Confidence section is accepted (step 5)"
ok "'lag under 1s' was not read as a dependency on step 1"
python3 "$L" check "$W/good.md" --json > "$W/g.json" 2>&1
t "--json exits 0 too" "$?" "0"
t "--json verdict is CLEAN" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['verdict'])" "$W/g.json")" "CLEAN"
python3 "$L" "$W/good.md" > /dev/null 2>&1
t "the bare-path shorthand runs check" "$?" "0"

# ── B · every way of breaking the grammar ────────────────────────────────────────────
echo "── B · the rules, one broken at a time"
edit "$W/good.md" "Done when: \`psql -c 'select 1'\` answers from the app host." \
     "It should come up fine." "$W/nodone.md"
t "a step with no \"done when\" is caught" "$(run "$W/nodone.md")" "5"
has "$W/out.txt" "done-when-missing" "names the rule"
has "$W/out.txt" "step 1" "carries the step number"

edit "$W/good.md" "   - depends on: nothing
2." "   - depends on: step 3
2." "$W/forward.md"
t "a step depending on a LATER step is caught" "$(run "$W/forward.md")" "5"
has "$W/out.txt" "dep-forward" "names the forward-reference rule"
has "$W/out.txt" "which comes LATER" "says why it cannot stand"

edit "$W/good.md" "   - depends on: nothing
2." "   - depends on: step 9
2." "$W/dangling.md"
t "a dependency on a step that does not exist is caught" "$(run "$W/dangling.md")" "5"
has "$W/out.txt" "dep-dangling" "names the dangling-reference rule"

edit "$W/good.md" "   - depends on: step 1" "   - depends on: step 4" "$W/cycle.md"
t "a dependency cycle is caught" "$(run "$W/cycle.md")" "5"
has "$W/out.txt" "dep-cycle" "names the cycle rule"
has "$W/out.txt" "step 2 → step 4 → step 2" "prints the cycle path"
t "the cycle is reported once, not once per edge" "$(grep -c 'dep-cycle' "$W/out.txt")" "1"

edit "$W/good.md" "3. **Announce" "2. **Announce" "$W/dup.md"
t "a step number used twice is caught" "$(run "$W/dup.md")" "5"
has "$W/out.txt" "duplicate-step-number" "names the duplicate rule"
has "$W/out.txt" "cannot resolve" "says why the graph stops meaning anything"

edit "$W/good.md" " (rolling back means re-syncing every row written after cutover)" "" "$W/oneway.md"
t "a [ONE-WAY] step with no rollback is caught" "$(run "$W/oneway.md")" "5"
has "$W/out.txt" "oneway-no-rollback" "names the one-way rule"
has "$W/out.txt" "step 4" "carries the step number"

edit "$W/good.md" "- **Low-confidence steps:** step 5 — mitigation: expert sign-off plus 90-day snapshot retention before power-off; rises to M once retention lands." \
     "- **Low-confidence steps:** none listed." "$W/low.md"
t "a Low-confidence step with no mitigation is caught" "$(run "$W/low.md")" "5"
has "$W/out.txt" "low-no-mitigation" "names the mitigation rule"
has "$W/out.txt" "step 5" "carries the step number"

printf '# A plan with no steps\n\nJust prose about what we might do.\n' > "$W/nosteps.md"
t "a document with no numbered steps is caught" "$(run "$W/nosteps.md")" "5"
has "$W/out.txt" "no-steps" "names the missing-steps rule"

cat > "$W/fenced.md" <<'EOF'
## The Plan
### Phase 1 — Inspect
1. **Read the queue.** Done when: the listing prints. confidence [H]
   - depends on: nothing

   ```
   1. first job — not a step
   2. second job — not a step
   ```
EOF
t "numbered lines inside a fenced block are not steps" "$(run "$W/fenced.md")" "0"
has "$W/out.txt" "1 step(s)" "counted exactly one real step"

python3 "$L" check "$W/missing.md" > /dev/null 2>&1
t "a missing plan exits 2" "$?" "2"

# ── C · converge — the ratio is measured, not declared ───────────────────────────────
echo "── C · converge on a known pair"
cv(){ python3 "$L" converge --prev "$1" --curr "$2" > "$W/cv.txt" 2>&1; echo $?; }
cvj(){ python3 "$L" converge --prev "$1" --curr "$2" --json \
       | python3 -c "import json,sys;print(json.load(sys.stdin)[sys.argv[1]])" "$3"; }

t "identical plans converge" "$(cv "$W/good.md" "$W/good.md")" "0"
has "$W/cv.txt" "CONVERGED" "verdict CONVERGED"
t "identical similarity is exactly 1.0" "$(cvj "$W/good.md" "$W/good.md" similarity)" "1.0"
t "identical material change is 0" "$(cvj "$W/good.md" "$W/good.md" material_lines)" "0"

# wording-only: bold moved, a period dropped, whitespace doubled
python3 -c "
import pathlib
t = pathlib.Path('$W/good.md').read_text()
t = t.replace('**Provision the Postgres primary.**', '**Provision the Postgres primary**')
t = t.replace('Ordered phases.', 'Ordered   phases')
pathlib.Path('$W/cosmetic.md').write_text(t)"
t "a reworded plan still converges" "$(cv "$W/good.md" "$W/cosmetic.md")" "0"
has "$W/cv.txt" "CONVERGED" "wording-only change reads as converged"
t "…with 0 material lines" "$(cvj "$W/good.md" "$W/cosmetic.md" material_lines)" "0"
t "…and the cosmetic lines are counted, not hidden" \
  "$(python3 -c "print($(cvj "$W/good.md" "$W/cosmetic.md" cosmetic_lines) > 0)")" "True"

t "a plan whose dependencies moved does NOT converge" "$(cv "$W/good.md" "$W/forward.md")" "0"
has "$W/cv.txt" "MOVING" "verdict MOVING"
t "…and the material change is counted" \
  "$(python3 -c "print($(cvj "$W/good.md" "$W/forward.md" material_lines) >= 1)")" "True"
t "…with similarity below 1.0" \
  "$(python3 -c "print($(cvj "$W/good.md" "$W/forward.md" similarity) < 1.0)")" "True"

python3 -c "
import pathlib
t = pathlib.Path('$W/good.md').read_text()
t = t.replace('### Phase 2 — Cutover', '''### Phase 2 — Rehearse
6. **Dry-run the cutover in staging.** Done when: the staging smoke test passes. confidence [M]
   - depends on: step 2

### Phase 3 — Cutover''')
pathlib.Path('$W/v3.md').write_text(t)"
t "a plan that grew a phase reports the structure move" "$(cv "$W/good.md" "$W/v3.md")" "0"
has "$W/cv.txt" "structure moved: steps, phases" "names what moved structurally"
has "$W/cv.txt" "steps 5→6 " "prints the before→after step counts"
has "$W/cv.txt" "phases 2→3" "and the phase counts"
t "converge exits 0 even when it says MOVING (a measurement is not a verdict)" \
  "$(cv "$W/good.md" "$W/v3.md")" "0"
python3 "$L" converge --prev "$W/good.md" --curr "$W/gone.md" > /dev/null 2>&1
t "converge on a missing file exits 2" "$?" "2"

echo
echo "stepbystep fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
