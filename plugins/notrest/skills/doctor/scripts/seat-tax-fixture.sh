#!/bin/bash
# seat-tax-fixture.sh — asserts the seat-tax cut: the SubagentStop hook's spend
# auto-receipt (agent-ledger.sh), render-check.sh, and gategrep.sh, each against
# a synthetic harness in a throwaway git repo. Self-relative: runs from anywhere.
# PASS/FAIL per assertion, summary at the end, nonzero exit if anything failed.
set -uo pipefail

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SD/../../../hooks/agent-ledger.sh"
SPEND="$SD/../../spend/scripts/spend.py"
RENDER="$SD/render-check.sh"
GATEGREP="$SD/gategrep.sh"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "PASS  $1"; }
no()   { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }
chk()  { if [ "$2" = "$3" ]; then ok "$1"; else no "$1" "want '$3' got '$2'"; fi; }

for f in "$HOOK" "$SPEND" "$RENDER" "$GATEGREP"; do
  [ -f "$f" ] || { echo "FATAL: missing $f"; exit 9; }
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; [ -n "${RC_PORT:-}" ] && "$RENDER" --close "$RC_PORT" >/dev/null 2>&1; exit' EXIT INT TERM

# ── synthetic repo A: has a spend ledger (opted in) ──────────────────────────
A="$TMP/repo-a"; mkdir -p "$A"; git -C "$A" init -q 2>/dev/null
python3 "$SPEND" log --model claude-opus-5 --tokens 42 --lane subagent \
  --purpose "seed line" --root "$A" >/dev/null 2>&1
[ -f "$A/spend/ledger.md" ] && ok "seed: spend.py created ledger in repo A" \
  || no "seed: spend.py created ledger in repo A"

# transcript WITH usage: 100+50+1000+10 = 1160
T1="$A/agent-agt_usage.jsonl"
cat > "$T1" <<'EOF'
{"type":"user","message":{"role":"user","content":"do the thing"}}
{"type":"assistant","message":{"role":"assistant","model":"claude-opus-5","usage":{"input_tokens":100,"output_tokens":50,"cache_read_input_tokens":1000,"cache_creation_input_tokens":10},"content":[{"type":"text","text":"Conclusion: the auto-receipt now writes itself at zero seat cost, and the ledger stays parseable."}]}}
EOF

# transcript WITHOUT usage
T2="$A/agent-agt_nousage.jsonl"
cat > "$T2" <<'EOF'
{"type":"assistant","message":{"role":"assistant","model":"claude-opus-5","content":[{"type":"text","text":"No usage data in this transcript at all."}]}}
EOF

run_hook() { # $1 repo  $2 agent id  $3 transcript path
  ( cd "$1" && printf '{"agent_id":"%s","transcript_path":"%s"}' "$2" "$3" | bash "$HOOK" ) \
    >"$TMP/hook.out" 2>"$TMP/hook.err"
  echo "$?" > "$TMP/hook.rc"
}

# ── 1. auto-receipt: exactly one observed line for a transcript with usage ────
run_hook "$A" agt_usage "$T1"
chk "hook exits 0" "$(cat "$TMP/hook.rc")" "0"
chk "hook is silent (stdout)" "$(wc -c <"$TMP/hook.out" | tr -d ' ')" "0"
chk "hook is silent (stderr)" "$(wc -c <"$TMP/hook.err" | tr -d ' ')" "0"
LEDGER="$A/spend/ledger.md"
N1=$(grep -c 'agent=agt_usage$' "$LEDGER" || true)
chk "auto-receipt: exactly one line for agt_usage" "$N1" "1"
LINE1="$(grep 'agent=agt_usage$' "$LEDGER" | head -1)"
echo "      line: $LINE1"
case "$LINE1" in
  *"tokens=1160"*) ok "auto-receipt: token total summed from usage (1160)" ;;
  *) no "auto-receipt: token total summed from usage (1160)" "$LINE1" ;;
esac
case "$LINE1" in
  *"grade=observed"*) ok "auto-receipt: derived total graded observed" ;;
  *) no "auto-receipt: derived total graded observed" ;;
esac
case "$LINE1" in
  *'purpose="auto-receipt: Conclusion: the auto-receipt'*) ok "auto-receipt: purpose carries the last conclusion" ;;
  *) no "auto-receipt: purpose carries the last conclusion" ;;
esac
case "$LINE1" in
  *"model=claude-opus-5"*) ok "auto-receipt: model scraped from transcript" ;;
  *) no "auto-receipt: model scraped from transcript" ;;
esac
case "$LINE1" in
  *"lane=subagent"*) ok "auto-receipt: lane=subagent (routing rule stays checkable)" ;;
  *) no "auto-receipt: lane=subagent (routing rule stays checkable)" ;;
esac
# byte-shape must satisfy spend.py's own report regex
if echo "$LINE1" | grep -qE '^\[[^]]+\] lane=[^ ]+ model=[^ ]+ tokens=[^ ]+ grade=[^ ]+ purpose="'; then
  ok "auto-receipt: matches spend.py's report regex shape"
else
  no "auto-receipt: matches spend.py's report regex shape"
fi
[ -s "$A/COORD-AGENTS.md" ] && ok "COORD-AGENTS.md still written" || no "COORD-AGENTS.md still written"

# ── 2. IDEMPOTENCE: a second hook run for the SAME agent adds nothing ─────────
BEFORE="$(md5 -q "$LEDGER" 2>/dev/null || md5sum "$LEDGER" | cut -d' ' -f1)"
LBEFORE=$(wc -l <"$LEDGER" | tr -d ' ')
run_hook "$A" agt_usage "$T1"
AFTER="$(md5 -q "$LEDGER" 2>/dev/null || md5sum "$LEDGER" | cut -d' ' -f1)"
LAFTER=$(wc -l <"$LEDGER" | tr -d ' ')
chk "idempotence: ledger byte-identical after re-run" "$AFTER" "$BEFORE"
chk "idempotence: line count unchanged ($LBEFORE)" "$LAFTER" "$LBEFORE"
chk "idempotence: still exactly one agt_usage line" "$(grep -c 'agent=agt_usage$' "$LEDGER" || true)" "1"
chk "idempotence: second run still exits 0" "$(cat "$TMP/hook.rc")" "0"

# ── 3. no usage data → grade=estimate, no token count ────────────────────────
run_hook "$A" agt_nousage "$T2"
LINE2="$(grep 'agent=agt_nousage$' "$LEDGER" | head -1)"
echo "      line: $LINE2"
case "$LINE2" in
  *"tokens=unknown"*) ok "no-usage: token count omitted (tokens=unknown)" ;;
  *) no "no-usage: token count omitted (tokens=unknown)" "$LINE2" ;;
esac
case "$LINE2" in
  *"grade=estimate"*) ok "no-usage: graded estimate, never guessed" ;;
  *) no "no-usage: graded estimate, never guessed" ;;
esac
chk "no-usage: exactly one line" "$(grep -c 'agent=agt_nousage$' "$LEDGER" || true)" "1"

# ── 4. repo with NO spend ledger → nothing created, COORD-AGENTS still written ─
B="$TMP/repo-b"; mkdir -p "$B"; git -C "$B" init -q 2>/dev/null
T3="$B/agent-agt_optout.jsonl"; cp "$T1" "$T3"
run_hook "$B" agt_optout "$T3"
chk "opt-out: hook exits 0" "$(cat "$TMP/hook.rc")" "0"
[ -e "$B/spend" ] && no "opt-out: no spend/ dir created" "$B/spend exists" \
  || ok "opt-out: no spend/ dir created"
[ -e "$B/spend/ledger.md" ] && no "opt-out: no ledger created" || ok "opt-out: no ledger created"
grep -q 'agent=agt_optout' "$B/COORD-AGENTS.md" 2>/dev/null \
  && ok "opt-out: COORD-AGENTS.md still written" || no "opt-out: COORD-AGENTS.md still written"

# ── 5. spend.py report still parses the ledger, auto lines counted ────────────
python3 "$SPEND" report --root "$A" >"$TMP/report.out" 2>&1; RRC=$?
if [ "$RRC" = "0" ] || [ "$RRC" = "4" ]; then ok "report: exit $RRC (0 clean / 4 violation)"
else no "report: exit code" "got $RRC"; fi
ENTRIES="$(sed -n 's/^entries: \([0-9]*\).*/\1/p' "$TMP/report.out" | head -1)"
chk "report: counts all 3 ledger entries (seed + 2 auto)" "$ENTRIES" "3"
grep -q 'tokens (known): 1202' "$TMP/report.out" \
  && ok "report: auto tokens folded into total (42+1160=1202)" \
  || no "report: auto tokens folded into total" "$(head -1 "$TMP/report.out")"
grep -q 'estimate-grade: 1' "$TMP/report.out" \
  && ok "report: the estimate-grade auto line is counted as such" \
  || no "report: the estimate-grade auto line is counted as such"

# ── 6. render-check: serves, proves 200, --close kills it ─────────────────────
HTMLDIR="$TMP/site"; mkdir -p "$HTMLDIR"
printf '<h1>seat tax</h1>\n' > "$HTMLDIR/page.html"
bash -n "$RENDER" && ok "render-check: bash -n clean" || no "render-check: bash -n clean"
"$RENDER" "$HTMLDIR/page.html" >"$TMP/rc.out" 2>"$TMP/rc.err"; RCRC=$?
chk "render-check: exit 0 on a good file" "$RCRC" "0"
grep -q 'HTTP 200' "$TMP/rc.out" && ok "render-check: proved HTTP 200" || no "render-check: proved HTTP 200"
RC_URL="$(sed -n 's/^URL:  *//p' "$TMP/rc.out" | head -1)"
RC_PORT="$(sed -n 's/^PORT:  *//p' "$TMP/rc.out" | head -1)"
echo "      url: ${RC_URL:-none}"
case "${RC_PORT:-0}" in 879[0-9]) ok "render-check: port in 8790-8799" ;; *) no "render-check: port in 8790-8799" "$RC_PORT" ;; esac
chk "render-check: URL is live after return" \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$RC_URL" 2>/dev/null)" "200"
"$RENDER" --close "$RC_PORT" >/dev/null 2>&1
sleep 0.4
DEAD="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$RC_URL" 2>/dev/null || echo dead)"
[ "$DEAD" = "200" ] && no "render-check: --close killed the server" "still 200" \
  || { ok "render-check: --close killed the server"; RC_PORT=""; }
"$RENDER" >/dev/null 2>&1; chk "render-check: no args → exit 2" "$?" "2"
"$RENDER" "$TMP/nope.html" >/dev/null 2>&1; chk "render-check: missing file → exit 2" "$?" "2"

# ── 7. gategrep: finds what a naive line-grep misses ──────────────────────────
WRAP="$TMP/wrapped.md"
cat > "$WRAP" <<'EOF'
- The hook now writes the spend receipt itself, so the
  seat never pays the lane-close tax again.
- Second mention: the seat never pays the lane-close tax again.
EOF
bash -n "$GATEGREP" && ok "gategrep: bash -n clean" || no "gategrep: bash -n clean"
grep -c 'the seat never pays the lane-close tax again' "$WRAP" >"$TMP/naive" 2>/dev/null
NAIVE="$(cat "$TMP/naive" 2>/dev/null || echo 0)"
chk "gategrep: naive grep undercounts the wrapped phrase" "$NAIVE" "1"
GG="$("$GATEGREP" "$WRAP" 'the seat never pays the lane-close tax again' 2)"; GGRC=$?
echo "      gategrep: $GG"
chk "gategrep: finds both (wrapped + inline) → exit 0" "$GGRC" "0"
case "$GG" in "2 (expected 2) PASS") ok "gategrep: output format '2 (expected 2) PASS'" ;;
  *) no "gategrep: output format" "$GG" ;; esac
"$GATEGREP" "$WRAP" 'the seat never pays the lane-close tax again' 5 >/dev/null 2>&1
chk "gategrep: wrong count → exit 1" "$?" "1"
"$GATEGREP" "$WRAP" >/dev/null 2>&1; chk "gategrep: too few args → exit 2" "$?" "2"
"$GATEGREP" "$TMP/nope.md" phrase >/dev/null 2>&1; chk "gategrep: missing file → exit 2" "$?" "2"
"$GATEGREP" "$WRAP" 'THE SEAT NEVER PAYS' >/dev/null 2>&1
chk "gategrep: case-sensitive (uppercase misses) → exit 1" "$?" "1"

echo
echo "── seat-tax fixture: $PASS PASS · $FAIL FAIL"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
