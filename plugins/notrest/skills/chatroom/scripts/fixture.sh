#!/bin/bash
# fixture.sh — asserts room.py's no-secrets law, the join round-trip, and the bridge's
# spend receipt. Self-relative: runs from any cwd, writes only inside its own mktemp
# dir, never touches a real room and never calls the real codex (a stub named `codex`
# is put on PATH; the "nothing was sent" assertions check that stub was never reached).
# Usage: bash <chatroom-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
R="$(cd "$(dirname "$0")" && pwd)/room.py"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
export CHATROOM_ROOT="$W/rooms"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
lines(){ wc -l < "$CHATROOM_ROOT/$1/room.md" | tr -d ' '; }

python3 "$R" create fix >/dev/null

# ── A · the no-secrets law: every class refuses with exit 5, writes nothing ──────────
echo "── A · secret screen (refuse = exit 5, room unchanged, class named, text never echoed)"
refused(){ # <label> <class> <payload>
  local before after out rc
  before="$(lines fix)"
  out="$(python3 "$R" post fix tester "$3" 2>&1)"; rc=$?
  after="$(lines fix)"
  t "$1 · exit code" "$rc" "5"
  t "$1 · nothing written" "$after" "$before"
  case "$out" in *"$2"*) ok "$1 · names class [$2]";; *) no "$1 · class [$2] not named — got: $out";; esac
  case "$out" in *"$3"*) no "$1 · LEAKED the matched text into the error";;
                      *) ok "$1 · matched text never echoed";; esac
}
refused "private-key-header" "private-key-header" "-----BEGIN RSA PRIVATE KEY-----"
refused "aws-access-key-id"  "aws-access-key-id"  "creds AKIAIOSFODNN7EXAMPLE here"
refused "openai-key(bare)"   "openai-style-key"   "sk-abcdefghijklmnopqrstuvwx"
refused "openai-key(proj)"   "openai-style-key"   "sk-proj-abcdefghijklmnopqrst"
refused "github-token"       "github-token"       "ghp_abcdefghijklmnopqrst12"
refused "slack-token"        "slack-token"        "xoxb-123456789012-abcdefghij"
refused "generic-assignment" "generic-credential-assignment" "api_key: abcdefghijklmnop1234"
refused "dotenv-line"        "dotenv-secret-line"  "$(printf 'SESSION_BLOB=%s' "$(head -c 40 < /dev/zero | tr '\0' 'a')")"

# ── B · the screen does not eat honest traffic (false-positive control) ──────────────
echo "── B · clean traffic still posts"
clean(){ # <label> <payload>
  local before after rc
  before="$(lines fix)"
  python3 "$R" post fix tester "$2" >/dev/null 2>&1; rc=$?
  after="$(lines fix)"
  t "$1 · exit code" "$rc" "0"
  t "$1 · appended one line" "$((after - before))" "1"
}
clean "plain message" "hello room, starting the safety lane"
clean "a sha256 is not a secret" "fixture hash sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
clean "keyword without a value"  "the password: is on a sticky note on my desk"

# ── C · join: read the tail, print the re-arm line, arm the watch — one call ─────────
echo "── C · join"
OUT="$(python3 "$R" join fix --handle qc --tail 2 --no-watch 2>&1)"; t "join --no-watch exits 0" "$?" "0"
case "$OUT" in *"re-arm: "*"watch fix --lines"*) ok "join prints the re-arm line with the count";;
                                              *) no "join printed no re-arm line — got: $OUT";; esac
case "$OUT" in *"hello room, starting the safety lane"*|*"sticky note"*) ok "join printed the tail";;
                                              *) no "join printed no room tail";; esac
python3 "$R" join fix --handle qc --tail 1 --interval 0.2 --timeout 6 > "$W/join.out" 2>&1 &
JP=$!
( sleep 1; python3 "$R" post fix other "a message that should wake the joiner" >/dev/null 2>&1 ) &
wait $JP; t "armed join wakes on a new post (exit 0)" "$?" "0"
grep -q "should wake the joiner" "$W/join.out" \
  && ok "armed join printed the new line" || no "armed join did not print the new line"

# ── D · the bridge send path: screened before anything leaves the machine ────────────
echo "── D · gpt-bridge"
mkdir -p "$W/bin"
cat > "$W/bin/codex" <<EOF
#!/bin/bash
# stub codex: records that it was reached, then emits a canned transcript.
echo reached >> "$W/codex-calls"
cat "\$CANNED"
EOF
chmod +x "$W/bin/codex"
export PATH="$W/bin:$PATH"
cat > "$W/canned-observed.txt" <<'EOF'
--------
workdir: /tmp/empty
model: gpt-5.6
reasoning effort: low
session id: 0f3d5a7c-1111-2222-3333-444455556666
--------
user
ping

codex
ack from the stub — nothing real left this machine

tokens used: 1,234
EOF
sed '/^tokens used/d' "$W/canned-observed.txt" > "$W/canned-noecho.txt"
export CANNED="$W/canned-observed.txt"
export CHATROOM_SPEND_ROOT="$W/estate"
mkdir -p "$W/estate/spend"

# D1 — a secret already in the room (hand-edited, the way the law gets broken) must
#      never reach the vendor: the send path refuses and the stub is never called.
python3 "$R" create leak >/dev/null
printf '[2026-07-25 00:00Z] @owner: @gpt use AKIAIOSFODNN7EXAMPLE to fetch it\n' \
  >> "$CHATROOM_ROOT/leak/room.md"
BEFORE="$(lines leak)"
OUT="$(python3 "$R" gpt-bridge leak --once --all 2>&1)"; RC=$?
t "bridge refuses to send room content matching a secret shape" "$RC" "5"
t "bridge posted nothing" "$(lines leak)" "$BEFORE"
t "the vendor stub was never reached" "$([ -f "$W/codex-calls" ] && echo reached || echo never)" "never"
case "$OUT" in *"aws-access-key-id"*) ok "bridge names the class";; *) no "bridge named no class — got: $OUT";; esac
case "$OUT" in *AKIAIOSFODNN7EXAMPLE*) no "bridge LEAKED the matched text";; *) ok "bridge never echoed the match";; esac

# D2 — a clean room: the bridge calls the stub, posts the reply, and receipts the spend.
python3 "$R" create clean >/dev/null
python3 "$R" post clean owner "@gpt please ack" >/dev/null
python3 "$R" gpt-bridge clean --once --all >/dev/null 2>&1
t "bridge exits 0 on a clean room" "$?" "0"
t "the vendor stub was reached" "$([ -f "$W/codex-calls" ] && echo reached || echo never)" "reached"
grep -q "ack from the stub" "$CHATROOM_ROOT/clean/room.md" \
  && ok "bridge posted the reply" || no "bridge posted no reply"
L="$W/estate/spend/ledger.md"
t "spend receipt written" "$([ -f "$L" ] && echo yes || echo no)" "yes"
grep -q 'lane=chatroom-gpt' "$L" && ok "receipt carries lane=chatroom-gpt" || no "no chatroom-gpt lane in the receipt"
grep -q 'tokens=1234 grade=observed' "$L" \
  && ok "parsed token count graded observed" || no "token count not parsed as observed: $(tail -1 "$L")"

# D3 — no `tokens used` echo: the receipt degrades to an estimate, never to silence.
export CANNED="$W/canned-noecho.txt"
python3 "$R" post clean owner "@gpt one more" >/dev/null
python3 "$R" gpt-bridge clean --once --all >/dev/null 2>&1
t "unparsable tokens still exits 0" "$?" "0"
t "second receipt appended" "$(grep -c 'lane=chatroom-gpt' "$L")" "2"
tail -1 "$L" | grep -q 'grade=estimate' \
  && ok "unparsable token count graded estimate" || no "not graded estimate: $(tail -1 "$L")"
python3 "$(cd "$(dirname "$0")" && pwd)/../../spend/scripts/spend.py" report --root "$W/estate" >/dev/null 2>&1
t "the ledger these receipts wrote is spend.py-parseable and clean" "$?" "0"

echo
echo "chatroom fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
