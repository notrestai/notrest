#!/bin/bash
# fixture.sh — proves the spend gate's violation predicate against synthetic ledgers.
#
# A gate that never fires is an unproven gate, so every case below is a NEGATIVE
# control as much as a positive one: the live policy (owner-set 2026-07-15, opus-only
# offload) must bite a post-policy sonnet lane and must NOT bite the pre-policy sonnet
# lanes that were lawful when they were logged.
#
# Never touches the real spend/ledger.md — every case writes its own throwaway ledger
# under a mktemp estate. Self-relative: runs from anywhere.
# PASS/FAIL per assertion, summary at the end, nonzero exit if anything failed.
set -uo pipefail

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEND="$SD/spend.py"
[ -f "$SPEND" ] || { echo "FATAL: missing $SPEND"; exit 9; }

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS  $1"; }
no()  { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1" "want '$3' got '$2'"; fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
OUT="$TMP/report.out"

# mk <case-name> <ledger-line>...  → writes a scratch ledger, returns its root
N=0
mk() {
  N=$((N+1))
  local root="$TMP/case$N"
  mkdir -p "$root/spend"
  printf '# spend ledger — append-only via spend.py; grades: observed|estimate\n' \
    > "$root/spend/ledger.md"
  local ln
  for ln in "$@"; do printf '%s\n' "$ln" >> "$root/spend/ledger.md"; done
  echo "$root"
}

# run <root> [extra args...] → report into $OUT, echoes exit code
run() { local r="$1"; shift; python3 "$SPEND" report --root "$r" "$@" >"$OUT" 2>&1; echo "$?"; }

E() { printf '[%s] lane=%s model=%s tokens=100 grade=observed purpose="fixture"' "$1" "$2" "$3"; }

echo "── 1. the live rule bites: post-policy non-opus offload lanes"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-sonnet-5)")
chk "post-policy sonnet on subagent → exit 4" "$(run "$R")" "4"
grep -q 'ROUTING VIOLATIONS (1)' "$OUT" && ok "  names it a routing violation" || no "  names it a routing violation" "$(cat "$OUT")"
grep -q 'policy 2026-07-15: opus-only offload' "$OUT" \
  && ok "  verdict names the rule version it enforces (greppable fingerprint)" \
  || no "  verdict names the rule version it enforces"

R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-haiku-4)")
chk "post-policy haiku on subagent → exit 4" "$(run "$R")" "4"
R=$(mk "$(E '2026-07-20 10:00Z' workflow claude-sonnet-5)")
chk "post-policy sonnet on a workflow lane → exit 4" "$(run "$R")" "4"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-fable-5)")
chk "post-policy fable on subagent → exit 4 (old rule still subsumed)" "$(run "$R")" "4"

echo "── 2. compliant post-policy lanes stay clean"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-opus-5)")
chk "post-policy opus-5 → exit 0" "$(run "$R")" "0"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-opus-4-8)")
chk "post-policy opus-4-8 → exit 0" "$(run "$R")" "0"

echo "── 3. policy-date guard: lawful-at-the-time is never a violation"
R=$(mk "$(E '2026-07-14 10:00Z' subagent claude-sonnet-5)")
chk "pre-policy sonnet → exit 0 (grandfathered)" "$(run "$R")" "0"
grep -q '1 pre-policy' "$OUT" && ok "  counted as pre-policy, not as compliant" \
  || no "  counted as pre-policy" "$(cat "$OUT")"
R=$(mk "$(E '2026-07-15 19:27Z' subagent claude-sonnet-5)")
chk "policy-DAY sonnet → exit 0 (hour of adoption unrecorded)" "$(run "$R")" "0"
R=$(mk "$(E '2026-07-16 00:01Z' subagent claude-sonnet-5)")
chk "day-after sonnet → exit 4 (the boundary bites)" "$(run "$R")" "4"

echo "── 4. the pre-policy era is judged by the rule that WAS live then"
R=$(mk "$(E '2026-07-10 10:00Z' subagent claude-fable-5)")
chk "pre-policy fable below the seat → exit 4 (legacy rule)" "$(run "$R")" "4"
grep -q 'LEGACY VIOLATIONS (1)' "$OUT" && ok "  labelled a legacy violation, not a live one" \
  || no "  labelled a legacy violation" "$(cat "$OUT")"

echo "── 5. an undatable stamp buys no amnesty (fail closed)"
R=$(mk 'lane=subagent model=claude-sonnet-5 tokens=1 grade=observed purpose="x"' \
       "$(E 'not-a-date' subagent claude-sonnet-5)")
chk "garbled timestamp + sonnet → exit 4" "$(run "$R")" "4"

echo "── 6. cross-vendor allowlist: exempt, but counted separately"
R=$(mk "$(E '2026-07-20 10:00Z' gpt gpt-5.6)")
chk "lane=gpt post-policy → exit 0" "$(run "$R")" "0"
grep -q 'cross-vendor lanes: 1, exempt' "$OUT" && ok "  reported 'cross-vendor lanes: 1, exempt'" \
  || no "  reported cross-vendor count" "$(cat "$OUT")"
R=$(mk "$(E '2026-07-20 10:00Z' chatroom-gpt gpt-5.6)")
chk "lane=chatroom-gpt post-policy → exit 0" "$(run "$R")" "0"
grep -q 'cross-vendor lanes: 1, exempt' "$OUT" && ok "  chatroom-gpt counted cross-vendor" \
  || no "  chatroom-gpt counted cross-vendor"

echo "── 7. seat lanes are not offload lanes"
for lane in main director seat; do
  R=$(mk "$(E '2026-07-20 10:00Z' "$lane" claude-fable-5)")
  chk "lane=$lane running fable → exit 0 (rule N/A)" "$(run "$R")" "0"
done

echo "── 8. unknown model = unverifiable, never laundered into clean OR into a violation"
R=$(mk '[2026-07-20 10:00Z] lane=subagent model=? tokens=unknown grade=estimate purpose="x"')
chk "post-policy model=? → exit 0 (absence of evidence is not evidence)" "$(run "$R")" "0"
grep -q 'UNVERIFIABLE (1)' "$OUT" && ok "  surfaced as UNVERIFIABLE on its own line" \
  || no "  surfaced as UNVERIFIABLE" "$(cat "$OUT")"
grep -q 'routing is not provable' "$OUT" && ok "  says routing is not provable for it" \
  || no "  says routing is not provable"

echo "── 9. --since filters the window"
R=$(mk "$(E '2026-07-10 10:00Z' subagent claude-fable-5)" \
       "$(E '2026-07-20 10:00Z' subagent claude-opus-5)")
chk "unfiltered: legacy violation present → exit 4" "$(run "$R")" "4"
chk "--since 2026-07-16 drops it → exit 0" "$(run "$R" --since 2026-07-16)" "0"
grep -q 'entries: 1 (since 2026-07-16)' "$OUT" && ok "  scope echoed in the entries line" \
  || no "  scope echoed" "$(head -1 "$OUT")"
python3 "$SPEND" report --root "$R" --since nonsense >/dev/null 2>&1
chk "--since with a non-ISO value → usage error (exit 1)" "$?" "1"

echo "── 10. --json: machine-readable, same exit codes"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-sonnet-5)")
chk "--json on a violation still exits 4" "$(run "$R" --json)" "4"
python3 -c "
import json,sys
d=json.load(open('$OUT'))
assert d['verdict']=='VIOLATION', d['verdict']
assert d['exit']==4, d['exit']
assert d['policy']=='policy 2026-07-15: opus-only offload', d['policy']
assert len(d['violations'])==1, d['violations']
assert d['counts']['violation']==1, d['counts']
" 2>"$TMP/jerr" && ok "  json carries verdict/exit/policy/violations/counts" \
  || no "  json payload shape" "$(cat "$TMP/jerr")"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-opus-5)")
chk "--json on a clean ledger exits 0" "$(run "$R" --json)" "0"
python3 -c "import json;d=json.load(open('$OUT'));assert d['verdict']=='CLEAN'" \
  && ok "  json verdict CLEAN" || no "  json verdict CLEAN"

echo "── 11. report keeps its shape (doctor + seat-tax fixture depend on it)"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-opus-5)" \
       "$(E '2026-07-20 10:05Z' subagent claude-opus-5)")
run "$R" >/dev/null
grep -qE '^entries: 2 · tokens \(known\): 200 · estimate-grade: 0$' "$OUT" \
  && ok "first line unchanged (entries · tokens · estimate-grade)" \
  || no "first line unchanged" "$(head -1 "$OUT")"
grep -q '^NOTE: ledger covers observed spend only' "$OUT" \
  && ok "the main-loop honesty NOTE survives" || no "the main-loop honesty NOTE survives"
grep -qE '^  claude-opus-5 +entries=2 +tokens=200 +share=100%$' "$OUT" \
  && ok "per-model table row shape survives" || no "per-model table row shape" "$(cat "$OUT")"
grep -q '^routing: CLEAN' "$OUT" \
  && ok "verdict line still starts with 'routing:' (doctor greps this)" \
  || no "verdict line prefix" "$(cat "$OUT")"
R=$(mk "$(E '2026-07-20 10:00Z' subagent claude-sonnet-5)")
run "$R" >/dev/null
grep -q '^routing: VIOLATION' "$OUT" \
  && ok "violation verdict also starts with 'routing:'" || no "violation verdict prefix"

echo "── 12. log still appends through the script"
R="$TMP/logcase"; mkdir -p "$R"
python3 "$SPEND" log --model claude-opus-5 --tokens 7 --lane subagent \
  --purpose "fixture log" --root "$R" >/dev/null 2>&1
chk "log created the ledger" "$([ -f "$R/spend/ledger.md" ] && echo yes || echo no)" "yes"
chk "log wrote exactly one entry" "$(grep -c '^\[' "$R/spend/ledger.md")" "1"
chk "a freshly logged opus subagent line reports clean" "$(run "$R")" "0"

echo
echo "── spend fixture: $PASS PASS · $FAIL FAIL"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
