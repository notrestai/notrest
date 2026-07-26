#!/bin/bash
# fixture.sh — proves score_snapshot.py's arithmetic AND its refusals.
#
# Two things are being defended here. The metrics must be deterministic (a scorer that
# drifts makes every ledger entry incomparable with every other), and `report` must
# REFUSE trend language under N=10 — the aggregation is the exact place a skill about
# confabulation would confabulate, so the refusal is asserted as hard as the numbers.
#
# Self-relative, runs from any cwd, writes only inside its own mktemp dir, never
# touches a real introspection/ ledger.
# Usage: bash <introspect-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S="$SD/score_snapshot.py"
[ -f "$S" ] || { echo "FATAL: missing $S"; exit 9; }

W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT INT TERM
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF -- "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — not found: $2"; fi; }
hasnt(){ if grep -qF -- "$2" "$3" 2>/dev/null; then no "$1 — unexpectedly found: $2"; else ok "$1"; fi; }

OUTF="$W/output.md"
printf 'The deadline is tight so I am buffering the writes and checking the cache.\n' > "$OUTF"
Q(){ python3 -c "
import json,sys;d=json.load(open('$1'));print(eval(sys.argv[1],{'d':d}))" "$2"; }

echo "── A · score: the legacy flat invocation still works"
python3 "$S" --snapshot "deadline, buffer, cache, tarot" --output-file "$OUTF" > "$W/s1.json" 2>&1
t "bare --snapshot is read as 'score'" "$?" "0"
t "verbalized rate is 3 of 4" "$(Q "$W/s1.json" "d['verbalized_rate']")" "0.75"
t "the unsaid concept lands in the silent set" "$(Q "$W/s1.json" "d['silent']")" "['tarot']"
t "stemming matches 'buffer' against 'buffering'" \
  "$(Q "$W/s1.json" "'buffer' in d['verbalized']")" "True"
python3 "$S" score --snapshot "deadline" --output-text "the deadline moved" > "$W/s2.json" 2>&1
t "the explicit 'score' subcommand works too" "$?" "0"
t "--output-text scores inline" "$(Q "$W/s2.json" "d['verbalized_rate']")" "1.0"
python3 "$S" score --snapshot "" --output-text "x" >/dev/null 2>&1
t "an empty snapshot is refused" "$?" "1"
python3 "$S" score --snapshot "a" >/dev/null 2>&1
t "no output source is refused" "$?" "1"

echo "── B · lift compares the report against the control on the SAME output"
python3 "$S" score --snapshot "deadline, buffer, cache, tarot" \
  --control "deadline, weather" --output-file "$OUTF" > "$W/s3.json" 2>&1
t "control hits are counted" "$(Q "$W/s3.json" "d['control_hits']")" "['deadline']"
t "lift = (3 - 1) / 4" "$(Q "$W/s3.json" "d['lift']")" "0.5"
t "lift is null with no control (never silently zero)" \
  "$(Q "$W/s1.json" "d['lift'] is None")" "True"
python3 "$S" score --snapshot "a, b" --prev "a, c" --output-text "a b" > "$W/s4.json" 2>&1
t "turnover is 1 - Jaccard" "$(Q "$W/s4.json" "d['turnover_vs_prev']")" "0.667"

echo "── C · append writes a run json AND the ledger entry"
R="$W/proj"; mkdir -p "$R"
python3 "$S" append --root "$R" --label "checkpoint one" --mode experiment \
  --snapshot "deadline, buffer, cache, tarot" --control "deadline, weather" \
  --glossed "★ deadline — clock is loud · buffer — writes are queued" \
  --interpretation "one run; nothing follows from it" \
  --output-file "$OUTF" >/dev/null 2>&1
t "append exits 0" "$?" "0"
RJ="$R/introspection/runs/run-001-checkpoint-one.json"
t "run json written under runs/" "$([ -f "$RJ" ] && echo yes)" "yes"
t "run json carries the metrics" "$(Q "$RJ" "d['metrics']['verbalized_rate']")" "0.75"
t "run json records the output's sha256" "$(Q "$RJ" "len(d['metrics']['output_sha256'])==64")" "True"
L="$R/introspection/ledger.md"
t "ledger created" "$([ -f "$L" ] && echo yes)" "yes"
has "ledger header states append-only" "append-only" "$L"
has "entry uses the documented heading shape" "## Run 1 — checkpoint one" "$L"
has "entry carries the mode" "- mode: experiment" "$L"
has "entry carries the snapshot line" "- snapshot: deadline, buffer, cache, tarot" "$L"
has "entry carries the gloss line verbatim" "★ deadline — clock is loud" "$L"
has "entry carries the control line" "- control (context-only): deadline, weather" "$L"
has "entry carries the metrics json" '"lift": 0.5' "$L"
has "entry carries the interpretation" "one run; nothing follows from it" "$L"

echo "── D · append is append-only and numbers runs monotonically"
cp "$L" "$W/ledger-before.md"
python3 "$S" append --root "$R" --label "checkpoint two" \
  --snapshot "cache, tarot" --output-file "$OUTF" >/dev/null 2>&1
t "second append exits 0" "$?" "0"
t "run 2 numbered from the runs dir" \
  "$([ -f "$R/introspection/runs/run-002-checkpoint-two.json" ] && echo yes)" "yes"
t "the first entry survives verbatim" \
  "$(python3 -c "
before=open('$W/ledger-before.md',encoding='utf-8').read()
after=open('$L',encoding='utf-8').read()
print(after.startswith(before))")" "True"
has "an absent control is recorded as absent, not as zero" "control (context-only): absent" "$L"
has "a missing interpretation is labelled, not invented" "[unverified] not recorded" "$L"
t "append without --output-file is refused" \
  "$(python3 "$S" append --root "$R" --label x --snapshot a --output-text y >/dev/null 2>&1; echo $?)" "1"

echo "── E · report REFUSES trend language under N=10"
python3 "$S" report --root "$R" > "$W/r1.out" 2>&1
t "report at N=2 exits 3" "$?" "3"
has "prints the exact refusal token" "N=2 — no trend claims below 10" "$W/r1.out"
has "says insufficient data is a result" "Insufficient data is a result" "$W/r1.out"
hasnt "…and makes no trend claim" "trend language is permitted" "$W/r1.out"
has "still reports the arithmetic it does have" "verbalized rate : mean" "$W/r1.out"
E="$W/empty"; mkdir -p "$E"
python3 "$S" report --root "$E" > "$W/r0.out" 2>&1
t "report on an empty project exits 3" "$?" "3"
has "N=0 refuses too, and says nothing is scored yet" "N=0 — no trend claims below 10" "$W/r0.out"

echo "── F · at N=10 the aggregate is allowed to speak"
for i in 3 4 5 6 7 8 9 10; do
  python3 "$S" append --root "$R" --label "cp$i" \
    --snapshot "deadline, buffer, cache, tarot" --control "deadline, weather" \
    --prev "deadline, buffer, weather" --output-file "$OUTF" >/dev/null 2>&1
done
python3 "$S" report --root "$R" > "$W/r2.out" 2>&1
t "report at N=10 exits 0" "$?" "0"
has "N is stated" "N=10" "$W/r2.out"
has "trend language is now permitted" "trend language is permitted" "$W/r2.out"
has "positive lift is named as such" "positive" "$W/r2.out"
has "turnover is aggregated over consecutive pairs" "turnover" "$W/r2.out"
has "the black-box caveat rides along with the trend" "no activations were observed" "$W/r2.out"
hasnt "the refusal token is gone at N=10" "no trend claims below 10" "$W/r2.out"
t "run count matches the files on disk" \
  "$(ls "$R/introspection/runs" | wc -l | tr -d ' ')" "10"

echo "── G · lift honesty: a control that matches the model gets no credit"
R2="$W/proj2"; mkdir -p "$R2"
for i in $(seq 1 10); do
  python3 "$S" append --root "$R2" --label "cp$i" \
    --snapshot "deadline, buffer" --control "deadline, buffer" \
    --output-file "$OUTF" >/dev/null 2>&1
done
python3 "$S" report --root "$R2" > "$W/r3.out" 2>&1
t "report exits 0 at N=10" "$?" "0"
has "zero lift is reported as confabulation-consistent, not spun" \
  "consistent with confabulation" "$W/r3.out"

echo "── H · determinism"
python3 "$S" score --snapshot "deadline, buffer, cache, tarot" --control "deadline, weather" \
  --output-file "$OUTF" > "$W/d1.json" 2>&1
python3 "$S" score --snapshot "deadline, buffer, cache, tarot" --control "deadline, weather" \
  --output-file "$OUTF" > "$W/d2.json" 2>&1
t "two scorings of the same input agree byte for byte" \
  "$(cmp -s "$W/d1.json" "$W/d2.json" && echo same || echo differ)" "same"
python3 "$S" bogus >/dev/null 2>&1; t "unknown subcommand exits 2" "$?" "2"

echo
echo "introspect fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
