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
# v4.1.0 — the swarm band runs on these two derived fields, so the receipt must carry
# them for a transcript that has tool calls and timestamps, and degrade to ? when it
# cannot. Free at stop time: the transcript is already open.
case "$LINE1" in
  *"calls="*) ok "auto-receipt: carries a tool-call count for the swarm band" ;;
  *) no "auto-receipt: carries a tool-call count for the swarm band" ;;
esac
case "$LINE1" in
  *"secs="*) ok "auto-receipt: carries a wall-clock for the swarm band" ;;
  *) no "auto-receipt: carries a wall-clock for the swarm band" ;;
esac
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

# ── 2b. DUPLICATE DELIVERY: the harness can send the same SubagentStop twice ──
# This is the defect that put 27 byte-identical duplicate lines into the real
# COORD-AGENTS.md while spend/ledger.md stayed clean: the receipt block checked for
# its own prior line, the COORD block checked nothing. Race the invocations rather
# than running them in sequence, so the flock is actually exercised.
C="$TMP/repo-c"; mkdir -p "$C"; git -C "$C" init -q 2>/dev/null
python3 "$SPEND" log --model claude-opus-5 --tokens 1 --lane subagent \
  --purpose "seed" --root "$C" >/dev/null 2>&1
T4="$C/agent-agt_race.jsonl"; cp "$T1" "$T4"

race() { # $1 agent id  $2 transcript  $3 how many racers
  local i pids=()
  for i in $(seq 1 "$3"); do
    ( cd "$C" && printf '{"agent_id":"%s","transcript_path":"%s"}' "$1" "$2" \
        | bash "$HOOK" ) >"$TMP/race.$i.out" 2>"$TMP/race.$i.err" &
    pids+=($!)
  done
  for i in "${pids[@]}"; do wait "$i"; done
}

race agt_race "$T4" 5
CA="$C/COORD-AGENTS.md"; CL="$C/spend/ledger.md"
chk "race: 5 concurrent invocations → exactly ONE COORD-AGENTS line" \
  "$(grep -c 'agent=agt_race ' "$CA" 2>/dev/null || true)" "1"
chk "race: 5 concurrent invocations → exactly ONE spend receipt" \
  "$(grep -c 'agent=agt_race$' "$CL" 2>/dev/null || true)" "1"
chk "race: every racer still exited 0" \
  "$(cat "$TMP/race.1.out" "$TMP/race.2.out" "$TMP/race.3.out" "$TMP/race.4.out" "$TMP/race.5.out" | wc -c | tr -d ' ')" "0"
chk "race: COORD header written exactly once" \
  "$(grep -c '^## LEDGER' "$CA" 2>/dev/null || true)" "1"

# a sequential redelivery (the common case) is equally a no-op for both files
run_hook "$C" agt_race "$T4"
chk "redelivery: COORD still one line" "$(grep -c 'agent=agt_race ' "$CA" || true)" "1"
chk "redelivery: spend still one receipt" "$(grep -c 'agent=agt_race$' "$CL" || true)" "1"

# ── 2c. a RESUMED lane is a different stop event and must still earn its line ──
# The real ledger shows one lane stopping at bytes=1050279, 1243214, 1420927 — the
# guard keys on the stop event (transcript size + snippet), never on the agent id,
# so growth is recorded and only redelivery is dropped.
cat >> "$T4" <<'EOF'
{"type":"assistant","message":{"role":"assistant","model":"claude-opus-5","usage":{"input_tokens":5,"output_tokens":5},"content":[{"type":"text","text":"Round two: same lane resumed, more work done, transcript grew."}]}}
EOF
run_hook "$C" agt_race "$T4"
chk "resume: a grown transcript earns a SECOND COORD line" \
  "$(grep -c 'agent=agt_race ' "$CA" || true)" "2"
chk "resume: that second line is not a duplicate of the first" \
  "$(grep 'agent=agt_race ' "$CA" | sort -u | wc -l | tr -d ' ')" "2"
race agt_race "$T4" 3
chk "resume: redelivering the RESUMED stop adds nothing" \
  "$(grep -c 'agent=agt_race ' "$CA" || true)" "2"

# ── 2d. the observed unknown-grade duplicate (model=? bytes=?) also collapses ──
# Real case: agent=ae4b4eb43312b7208 landed twice at 08:03Z with model=? bytes=?.
# An unreadable transcript still yields a known agent id, so the entry is written —
# but only once.
race agt_unknown "$C/does-not-exist.jsonl" 4
chk "unknown-grade entry written once despite 4 racers" \
  "$(grep -c 'agent=agt_unknown ' "$CA" || true)" "1"
grep -q 'agent=agt_unknown model=? bytes=?' "$CA" \
  && ok "unknown-grade entry keeps its honest '?' fields" \
  || no "unknown-grade entry keeps its honest '?' fields" "$(grep 'agt_unknown' "$CA" || true)"

# ── 2e. LANE BRIEF extraction: the commission is estate-visible by construction ─
# The owner caught a seat narrowing their ask inside a lane brief, invisibly. The hook
# now extracts the first user-role message — the exact prompt the seat passed — so any
# commission can be read without asking the seat. These assertions are the guarantee.
D="$TMP/repo-d"; mkdir -p "$D"; git -C "$D" init -q 2>/dev/null
BRIEF_BODY='Build the ledger instrument.

SCOPE NARROWED: the owner asked for X and Y; I am commissioning only X.

- bullet one
- bullet two'
T5="$D/agent-agt_brief.jsonl"
python3 - "$T5" "$BRIEF_BODY" <<'PYEOF'
import json, sys
p, brief = sys.argv[1], sys.argv[2]
rows = [
  {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": brief}]}},
  {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5",
     "usage": {"input_tokens": 10, "output_tokens": 5},
     "content": [{"type": "text", "text": "Working on it."}]}},
  {"type": "user", "message": {"role": "user",
     "content": [{"type": "tool_result", "text": "LATER-USER-TURN-NOT-THE-COMMISSION"}]}},
  {"type": "user", "message": {"role": "user", "content": "PLAIN-LATER-USER-TURN"}},
  {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5",
     "content": [{"type": "text", "text": "Done: the instrument ships."}]}},
]
open(p, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
PYEOF

run_hook "$D" agt_brief "$T5"
BF="$D/briefs/agent-agt_brief.md"
DCA="$D/COORD-AGENTS.md"
chk "brief: hook still exits 0" "$(cat "$TMP/hook.rc")" "0"
[ -f "$BF" ] && ok "brief: briefs/agent-<id>.md created" || no "brief: briefs/agent-<id>.md created"
chk "brief: receipt line carries the pointer" \
  "$(grep -c ' | brief: briefs/agent-agt_brief.md$' "$DCA" 2>/dev/null || true)" "1"

# the body after the --- separator must be the commission, byte-for-byte
GOT="$(awk 'f{print} /^---$/{f=1}' "$BF" | tail -n +2)"
if [ "$GOT" = "$BRIEF_BODY" ]; then ok "brief: body is the commission VERBATIM (newlines, bullets intact)"
else no "brief: body verbatim" "got: $GOT"; fi
grep -q 'LATER-USER-TURN-NOT-THE-COMMISSION' "$BF" \
  && no "brief: a later tool_result turn leaked in" || ok "brief: later tool_result turn excluded"
grep -q 'PLAIN-LATER-USER-TURN' "$BF" \
  && no "brief: a post-assistant user turn leaked in" || ok "brief: post-assistant user turn excluded"

# header fields
grep -q '^# lane brief — agent-agt_brief$' "$BF" && ok "brief header: title names the agent" || no "brief header: title"
grep -qE '^- extracted: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}Z$' "$BF" && ok "brief header: UTC timestamp" || no "brief header: UTC timestamp"
grep -q '^- agent: agt_brief$' "$BF" && ok "brief header: agent id" || no "brief header: agent id"
grep -q '^- model: claude-opus-5$' "$BF" && ok "brief header: model" || no "brief header: model"
grep -q "^- transcript: $T5\$" "$BF" && ok "brief header: transcript path" || no "brief header: transcript path"

# idempotence: racers and redelivery create exactly ONE brief and never rewrite it
mtime() { stat -f '%m' "$1" 2>/dev/null || stat -c '%Y' "$1"; }
BSUM0="$(md5 -q "$BF" 2>/dev/null || md5sum "$BF" | cut -d' ' -f1)"
BMT0="$(mtime "$BF")"
CBEFORE="$C"; C="$D"          # race() writes into $C
race agt_brief "$T5" 5
C="$CBEFORE"
chk "brief: 5 racers → still exactly one brief file" \
  "$(ls "$D/briefs" | wc -l | tr -d ' ')" "1"
chk "brief: 5 racers → still exactly one receipt line" \
  "$(grep -c 'agent=agt_brief ' "$DCA" || true)" "1"
chk "brief: content untouched by racers" \
  "$(md5 -q "$BF" 2>/dev/null || md5sum "$BF" | cut -d' ' -f1)" "$BSUM0"

# an EXISTING brief is never rewritten, even when the transcript's commission changes
python3 - "$T5" <<'PYEOF'
import json, sys
p = sys.argv[1]
rows = [{"type": "user", "message": {"role": "user", "content": "REWRITTEN-COMMISSION"}},
        {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-5",
         "content": [{"type": "text", "text": "Second stop, grown transcript."}]}}]
open(p, "a").write("\n".join(json.dumps(r) for r in rows) + "\n")
PYEOF
run_hook "$D" agt_brief "$T5"
chk "brief: existing brief content unchanged (never rewritten)" \
  "$(md5 -q "$BF" 2>/dev/null || md5sum "$BF" | cut -d' ' -f1)" "$BSUM0"
chk "brief: existing brief mtime unchanged" "$(mtime "$BF")" "$BMT0"
grep -q 'REWRITTEN-COMMISSION' "$BF" && no "brief: a later run overwrote the commission" \
  || ok "brief: the original commission survives a later stop"
chk "brief: the grown transcript still earned a second receipt line" \
  "$(grep -c 'agent=agt_brief ' "$DCA" || true)" "2"

# ── 2f. extraction failures never produce a dead pointer ─────────────────────
run_hook "$D" agt_nofile "$D/does-not-exist.jsonl"
chk "no transcript: hook still exits 0" "$(cat "$TMP/hook.rc")" "0"
chk "no transcript: receipt line still lands" \
  "$(grep -c 'agent=agt_nofile ' "$DCA" || true)" "1"
grep 'agent=agt_nofile ' "$DCA" | grep -q 'brief:' \
  && no "no transcript: receipt carries no brief field" || ok "no transcript: receipt carries no brief field"
[ -f "$D/briefs/agent-agt_nofile.md" ] && no "no transcript: no brief file created" \
  || ok "no transcript: no brief file created"

T6="$D/agent-agt_nouser.jsonl"
printf '%s\n' '{"type":"assistant","message":{"role":"assistant","model":"claude-opus-5","content":[{"type":"text","text":"no user turn at all"}]}}' > "$T6"
run_hook "$D" agt_nouser "$T6"
chk "no user turn: receipt still lands" "$(grep -c 'agent=agt_nouser ' "$DCA" || true)" "1"
grep 'agent=agt_nouser ' "$DCA" | grep -q 'brief:' \
  && no "no user turn: receipt carries no brief field" || ok "no user turn: receipt carries no brief field"

# ── 2g. briefs/ is TRACKED estate — no ignore rule may swallow it ────────────
if git -C "$SD/../../../.." check-ignore -q briefs/agent-x.md 2>/dev/null; then
  no "briefs/ is tracked estate (not gitignored)" "a .gitignore rule matches briefs/"
else
  ok "briefs/ is tracked estate (not gitignored)"
fi

# ── 3. no usage data → grade=estimate, no token count ────────────────────────
run_hook "$A" agt_nousage "$T2"
LINE2="$(grep 'agent=agt_nousage$' "$LEDGER" | head -1)"
echo "      line: $LINE2"
# v4.5 (docket 7): a no-usage transcript no longer surrenders to unknown — the receipt
# carries a bytes-derived figure GRADED estimate, and says where it came from.
case "$LINE2" in
  *"grade=estimate"*) ok "no-usage: bytes-derived figure, graded estimate" ;;
  *) no "no-usage: bytes-derived figure, graded estimate" "$LINE2" ;;
esac
case "$LINE2" in
  *"est from"*"transcript bytes"*) ok "…and the receipt names its derivation" ;;
  *) no "…and the receipt names its derivation" "$LINE2" ;;
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
