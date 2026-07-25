#!/bin/bash
# fixture.sh — asserts gpt.sh against a STUB codex (a canned transcript on disk). The
# real codex is never invoked: no OpenAI call, no quota spent, no network. The stub
# records its own argv, which is how flag order and sandbox choice are asserted rather
# than assumed. Self-relative; writes only inside its own mktemp dir.
# Usage: bash <gpt-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
G="$(cd "$(dirname "$0")" && pwd)/gpt.sh"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -q -- "$2" "$1"; then ok "$3"; else no "$3 — [$2] not in $1"; fi; }

export GPT_LANE_ROOT="$W/lane"
export GPT_SPEND_ROOT="$W/estate"
mkdir -p "$W/estate/spend" "$W/bin"

cat > "$W/canned.txt" <<'EOF'
--------
workdir: /tmp/empty
model: gpt-5.6-codex
provider: openai
reasoning effort: medium
session id: 11112222-3333-4444-5555-666677778888
--------
user
ping

codex
pong from the stub

tokens used: 4,096
EOF
sed '/^tokens used/d' "$W/canned.txt" > "$W/canned-noecho.txt"

cat > "$W/bin/codex" <<EOF
#!/bin/bash
printf '%s\n' "\$*" >> "$W/argv.log"
pwd >> "$W/cwd.log"
ls -A . | wc -l | tr -d ' ' >> "$W/cwdfiles.log"
cat "\${CANNED:-$W/canned.txt}"
EOF
chmod +x "$W/bin/codex"
export GPT_CODEX_BIN="$W/bin/codex"

# ── A · parse: the receipt's arithmetic, on a canned transcript ──────────────────────
echo "── A · parse"
bash "$G" parse "$W/canned.txt" > "$W/p.txt" 2>&1; t "parse exits 0" "$?" "0"
has "$W/p.txt" "SESSION=11112222-3333-4444-5555-666677778888" "parses the session id"
has "$W/p.txt" "TOKENS=4096" "parses tokens used, comma stripped"
has "$W/p.txt" "EFFORT=medium" "parses the effort echo (the proof the level applied)"
bash "$G" parse "$W/nope.txt" >/dev/null 2>&1; t "parse of a missing file exits 2" "$?" "2"

# ── B · chat: fresh then resume, id saved once ───────────────────────────────────────
echo "── B · chat"
bash "$G" chat "first message" --think medium > "$W/c1.txt" 2>"$W/c1.err"; t "chat exits 0" "$?" "0"
has "$W/c1.txt" "pong from the stub" "relays the transcript"
t "session id saved" "$(cat "$W/lane/chats/main.id" 2>/dev/null)" "11112222-3333-4444-5555-666677778888"
has "$W/argv.log" "exec --skip-git-repo-check --sandbox read-only" "first call: fresh session, read-only"
bash "$G" chat "second message" >/dev/null 2>&1; t "second chat exits 0" "$?" "0"
tail -1 "$W/argv.log" > "$W/last.txt"
has "$W/last.txt" "exec --sandbox read-only -c model_reasoning_effort=medium resume" \
  "resume flag ORDER: --sandbox/-c before resume"
has "$W/last.txt" "resume 11112222-3333-4444-5555-666677778888 --skip-git-repo-check" \
  "resume carries the saved id, then --skip-git-repo-check"
t "the id file was written once, not overwritten" "$(cat "$W/lane/chats/main.id")" \
  "11112222-3333-4444-5555-666677778888"
t "every call ran in an EMPTY cwd (codex reads its cwd)" "$(sort -u "$W/cwdfiles.log" | tr -d ' \n')" "0"

# ── C · the profile is honored, --think overrides it ────────────────────────────────
echo "── C · effort"
printf 'LEVEL=low\nMODE=worker\n' > "$W/lane/chats/main.profile"
bash "$G" chat "third" >/dev/null 2>&1
tail -1 "$W/argv.log" | grep -q "model_reasoning_effort=low" \
  && ok "profile LEVEL is used when no flag is given" || no "profile LEVEL ignored"
bash "$G" chat "fourth" --think high >/dev/null 2>&1
tail -1 "$W/argv.log" | grep -q "model_reasoning_effort=high" \
  && ok "--think overrides the profile" || no "--think did not override"
bash "$G" chat "fifth" --think minimal >/dev/null 2>&1
t "an effort outside the ladder is refused (minimal 400s on the 5.6 family)" "$?" "2"

# ── D · once and task: sandbox and session semantics ─────────────────────────────────
echo "── D · once / task"
bash "$G" once "a one-shot" >/dev/null 2>&1; t "once exits 0" "$?" "0"
tail -1 "$W/argv.log" | grep -q "resume" && no "once must never resume a session" || ok "once never resumes"
t "once saved no session file" "$(ls "$W/lane/chats" | grep -c 'once')" "0"
bash "$G" task demo "build a thing" >/dev/null 2>&1; t "task exits 0" "$?" "0"
tail -1 "$W/argv.log" | grep -q -- "--sandbox workspace-write" \
  && ok "task is the only shape that gets workspace-write" || no "task sandbox wrong"
t "task ran in its own workspace" "$(tail -1 "$W/cwd.log")" "$W/lane/work/demo"
t "task saved its session for follow-ups" \
  "$([ -s "$W/lane/work/demo.id" ] && echo yes || echo no)" "yes"
bash "$G" task demo "follow up" >/dev/null 2>&1
tail -1 "$W/argv.log" | grep -q "resume" && ok "a task follow-up resumes the same session" \
  || no "task follow-up did not resume"

# ── E · the auto-receipt ─────────────────────────────────────────────────────────────
echo "── E · spend receipt"
L="$W/estate/spend/ledger.md"
t "ledger written" "$([ -f "$L" ] && echo yes || echo no)" "yes"
has "$L" "lane=gpt" "receipts land on lane=gpt"
has "$L" "tokens=4096 grade=observed" "the echoed count is graded observed"
has "$L" "model=gpt-5.6-codex" "names the model that actually ran"
N="$(grep -c 'lane=gpt ' "$L")"
CANNED="$W/canned-noecho.txt" bash "$G" chat "no token echo" >/dev/null 2>&1
t "a call with no tokens-used echo still exits 0" "$?" "0"
t "and still receipts" "$(grep -c 'lane=gpt ' "$L")" "$((N + 1))"
tail -1 "$L" | grep -q "grade=estimate" \
  && ok "an unparsable count degrades to estimate, never to silence" || no "not graded estimate"
python3 "$(cd "$(dirname "$0")" && pwd)/../../spend/scripts/spend.py" report --root "$W/estate" >/dev/null 2>&1
t "the ledger these receipts wrote is spend.py-parseable and routing-clean" "$?" "0"
GPT_NO_SPEND=1 bash "$G" chat "quiet" >/dev/null 2>&1
t "GPT_NO_SPEND suppresses the ledger write" "$(grep -c 'lane=gpt ' "$L")" "$((N + 1))"

# ── F · a missing CLI hands over the install block and stops ─────────────────────────
echo "── F · absent CLI"
GPT_CODEX_BIN="$W/bin/not-installed" bash "$G" chat "hello" > "$W/f.txt" 2>&1
t "absent codex exits 3" "$?" "3"
has "$W/f.txt" "npm install -g @openai/codex" "hands over the install block"
grep -q "codex login" "$W/f.txt" && ok "tells the user to log in themselves" || no "no login line"

echo
echo "gpt fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
