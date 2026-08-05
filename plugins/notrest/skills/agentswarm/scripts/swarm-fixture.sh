#!/bin/bash
# swarm-fixture.sh — the decomposition gauge, asserted against synthetic estates.
#
# A metric nobody can falsify is a number, not a measurement. This builds estates whose
# right answer is known by construction — a green lane, a monolith, a degraded receipt,
# and an OLD receipt with no calls/secs whose numbers must be derived from a transcript —
# then asserts the rows, the aggregates, both exit codes, --json key stability, and that
# two runs over an unchanged estate are byte-identical.
#
# Self-relative, hermetic: writes only inside its own mktemp dir, reads no real estate.
# Usage: bash <agentswarm-skill>/scripts/swarm-fixture.sh   (exit 0 = all pass)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SW="$HERE/swarm.py"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF -- "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — [$2] not in $3"; fi; }
ckt(){ cksum < "$1" | awk '{print $1"-"$2}'; }
J(){ python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
k=sys.argv[2]
print(d[k] if k in d else '<MISSING>')" "$1" "$2"; }

# ── an estate with no receipts at all ────────────────────────────────────────────────
E0="$W/empty"; mkdir -p "$E0"
python3 "$SW" report --root "$E0" > "$W/o" 2>&1; t "no receipts → exit 6" "$?" "6"
has "…and says why, not just a code" "NO USABLE DATA" "$W/o"

# ── the seeded estate: every band by construction ────────────────────────────────────
E="$W/estate"; mkdir -p "$E/spend" "$E/briefs"
# a GREEN lane: 12 calls, 4 minutes
# a MONOLITH by CALLS: 60 calls, 5 minutes
# a MONOLITH by CLOCK: 10 calls, 20 minutes
# a DEGRADED receipt: the shape the hook writes when it can read nothing
# an OLD receipt: no calls=/secs= at all — must be DERIVED from its transcript
{ echo "# ledger"
  echo "[2026-08-04 10:00Z] lane=subagent model=claude-opus-4 tokens=1000 grade=observed purpose=\"auto-receipt: narrow\" calls=12 secs=240 agent=greenlane"
  echo "[2026-08-04 11:00Z] lane=subagent model=claude-opus-4 tokens=9000 grade=observed purpose=\"auto-receipt: fat\" calls=60 secs=300 agent=monocalls"
  echo "[2026-08-04 12:00Z] lane=subagent model=claude-opus-4 tokens=9000 grade=observed purpose=\"auto-receipt: slow\" calls=10 secs=1200 agent=monosecs"
  echo "[2026-08-04 13:00Z] lane=subagent model=? tokens=unknown grade=estimate purpose=\"auto-receipt: \" calls=? secs=? agent=degraded1"
  echo "[2026-08-04 14:00Z] lane=subagent model=claude-opus-4 tokens=500 grade=observed purpose=\"auto-receipt: old\" agent=oldlane"
  echo "[2026-08-04 15:00Z] lane=seat model=claude-opus-4 tokens=999 grade=estimate kind=seat-estimate purpose=\"seat burn\""
} > "$E/spend/ledger.md"

# the OLD lane's transcript: 3 tool calls across 6 minutes, to be derived not guessed
TR="$W/agent-oldlane.jsonl"
{ echo '{"timestamp":"2026-08-04T14:00:00Z","type":"user","message":{"role":"user","content":[{"type":"text","text":"BRIEF: do the narrow thing"}]}}'
  echo '{"timestamp":"2026-08-04T14:02:00Z","type":"assistant","message":{"role":"assistant","model":"claude-opus-4","content":[{"type":"tool_use","id":"t1","name":"Bash","input":{}}]}}'
  echo '{"timestamp":"2026-08-04T14:04:00Z","type":"assistant","message":{"role":"assistant","model":"claude-opus-4","content":[{"type":"tool_use","id":"t2","name":"Read","input":{}}]}}'
  echo '{"timestamp":"2026-08-04T14:06:00Z","type":"assistant","message":{"role":"assistant","model":"claude-opus-4","content":[{"type":"tool_use","id":"t3","name":"Edit","input":{}},{"type":"text","text":"done"}]}}'
} > "$TR"
{ echo "# COORD-AGENTS.md"; echo; echo "## LEDGER"
  echo "- [2026-08-04 14:06Z] agent=oldlane model=claude-opus-4 bytes=10 | last: done | transcript: $TR"
  echo "- [2026-08-04 13:00Z] agent=degraded1 model=? bytes=? | last: ? | transcript: /nonexistent/agent-degraded1.jsonl"
} > "$E/COORD-AGENTS.md"
: > "$E/briefs/agent-greenlane.md"
: > "$E/briefs/agent-oldlane.md"
{ echo "# COORD.md — session coordination ledger"; echo; echo "## LEDGER"
  echo "- [2026-08-04 10:30Z] [seat] gated the build -> doctor=5 eval=0 | evidence: exit codes"
  echo "- [2026-08-04 11:30Z] [seat] bad patch -> rollback landed | evidence: git revert"
  echo "- [2026-08-04 12:30Z] [seat] repaired the lane -> rework round | evidence: fixture"
} > "$E/COORD.md"

python3 "$SW" report --root "$E" > "$W/r" 2>&1; t "seeded estate → exit 5 (monoliths present)" "$?" "5"
python3 "$SW" report --root "$E" --json > "$W/j1" 2>&1

t "the seat lane is not counted as a swarm lane" "$(J "$W/j1" lanes)" "5"
t "green lanes counted" "$(J "$W/j1" band_green)" "2"
t "monoliths counted (calls AND clock)" "$(J "$W/j1" band_monolith)" "2"
t "degraded receipts counted" "$(J "$W/j1" receipts_degraded)" "1"
t "briefs joined from disk" "$(J "$W/j1" briefs_banked)" "2"

has "the calls monolith names the number that tripped it" "60 calls >= 45" "$W/r"
has "the clock monolith names the number that tripped it" "20m 0s >= 15m" "$W/r"
has "the green lane shows its measurement" "12 calls, 4m 0s" "$W/r"
has "a degraded lane says the band cannot see it" "no calls/secs on the receipt" "$W/r"
has "the band's thresholds are printed with the report" "GREEN <=30 calls AND <=10m" "$W/r"
has "the window is anchored on data, not the wall clock" "not the wall clock" "$W/r"

# DERIVATION: the old receipt carries no calls=/secs=; both must come from the transcript.
has "an old receipt is enriched from its transcript" "[derived]" "$W/r"
t "derived call count is read, not guessed" \
  "$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print([r['calls'] for r in d['rows'] if r['agent']=='oldlane'][0])" "$W/j1")" "3"
t "derived wall-clock is read, not guessed" \
  "$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print([r['secs'] for r in d['rows'] if r['agent']=='oldlane'][0])" "$W/j1")" "360"

# THE TWO-SIDED GUARD: size is meaningless without rework beside it.
t "rework: gate lines counted in window" "$(J "$W/j1" rework_gates)" "1"
t "rework: correction/repair lines counted in window" "$(J "$W/j1" rework_corrections)" "2"
has "…and the report says why the pairing matters" "the band is TWO-SIDED" "$W/r"

# AGGREGATES
# NEAREST-RANK, deliberately: lanes with call data are 3,10,12,60 and the p50 is 10 — a
# number a lane actually recorded, not an interpolated 11 that no lane ever ran.
t "calls median is nearest-rank (a real lane's number)" "$(J "$W/j1" calls_median)" "10"
t "calls max" "$(J "$W/j1" calls_max)" "60"
t "longest lane wall-clock" "$(J "$W/j1" secs_max)" "1200"

# DETERMINISM — a gauge whose reading drifts between runs cannot gate anything.
python3 "$SW" report --root "$E" > "$W/r2" 2>&1
t "text report byte-identical twice" "$(ckt "$W/r")" "$(ckt "$W/r2")"
python3 "$SW" report --root "$E" --json > "$W/j2" 2>&1
t "--json byte-identical twice" "$(ckt "$W/j1")" "$(ckt "$W/j2")"
t "--json keys sorted (stable order)" \
  "$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print(list(d)==sorted(d))" "$W/j1")" "True"

# AN ALL-GREEN ESTATE EXITS 0 — the flag must be earned, not permanent.
G="$W/green"; mkdir -p "$G/spend"
{ echo "# ledger"
  echo "[2026-08-04 10:00Z] lane=subagent model=claude-opus-4 tokens=100 grade=observed purpose=\"auto-receipt: a\" calls=8 secs=120 agent=g1"
  echo "[2026-08-04 10:05Z] lane=subagent model=claude-opus-4 tokens=100 grade=observed purpose=\"auto-receipt: b\" calls=19 secs=200 agent=g2"
} > "$G/spend/ledger.md"
python3 "$SW" report --root "$G" > "$W/g" 2>&1; t "an all-green estate exits 0" "$?" "0"
has "…and says it is in band" "swarm: IN BAND" "$W/g"

# WINDOW: --window filters on the receipts' own stamps, anchored on the newest.
python3 "$SW" report --root "$E" --window 1d --json > "$W/jw" 2>&1
t "--window narrows the lane set" "$(J "$W/jw" window_days)" "1"
python3 "$SW" report --root "$E" --window bogus >/dev/null 2>&1
t "a malformed --window is a usage error, not a guess" "$?" "2"

echo
echo "swarm-fixture: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
