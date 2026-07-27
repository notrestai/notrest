#!/usr/bin/env bash
# cockpit-fixture — the live window, asserted against a scratch estate.
#
# The cockpit is a SERVER, so the fixture is a client: it stands one up on a
# throwaway root and a throwaway chatroom dir, then proves the things a monitor
# must never get wrong — that it binds loopback and nothing else, that every
# panel answers with parseable JSON, that a brief pointer escaping the root is
# refused unread, that a render is rebuilt when its inputs move and NOT rebuilt
# again inside the debounce, that the one write route is the mail slot and that
# chatroom's own refusal passes through it untouched, and that everything else
# is a 404. Then it reaps the server.
#
# Exit 0 = every assertion held. No network beyond 127.0.0.1, no model calls, no
# writes to the real repo, no writes to the real ~/.claude/chatrooms.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
COCKPIT="$HERE/cockpit.py"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/notrest-cockpit-fixture.XXXXXX")"
R="$TMP/estate"
PASSES=0
FAILS=0
PID=""

cleanup() {
  [ -n "$PID" ] && kill "$PID" 2>/dev/null
  [ -n "$PID" ] && wait "$PID" 2>/dev/null
  rm -rf "$TMP"
}
trap cleanup EXIT

ok()  { PASSES=$((PASSES+1)); echo "PASS  $1"; }
bad() { FAILS=$((FAILS+1));   echo "FAIL  $1"; }
chk() { if [ "$2" = "$3" ]; then ok "$1 = $2"; else bad "$1: expected $2, got $3"; fi; }

code() { curl -s -o /dev/null -w '%{http_code}' --max-time 60 "$@"; }
body() { curl -s --max-time 60 "$@"; }
hdr()  { curl -sI --max-time 60 "$1" | tr -d '\r'; }
jok()  { python3 -c "import json,sys;json.load(sys.stdin)" >/dev/null 2>&1; }
jval() { python3 -c "
import json,sys
d=json.load(sys.stdin)
for k in sys.argv[1].split('.'):
    d = d[int(k)] if k.lstrip('-').isdigit() else d[k]
print(d)" "$1" 2>/dev/null || echo "<ERR>"; }

PORT="$(python3 - <<'PY'
import socket, sys
for p in range(8760, 8780):          # deliberately clear of 8788 and 8790-8799
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p)); print(p); sys.exit(0)
    except OSError:
        pass
    finally:
        s.close()
sys.exit(3)
PY
)"
[ -n "$PORT" ] || { echo "no free port in 8760-8779"; exit 3; }
U="http://127.0.0.1:$PORT"

# ─────────────────────────────────────────────────────── the scratch estate
mkdir -p "$R/archive" "$R/briefs" "$R/watch" "$R/spend" \
         "$R/plugins/notrest/hooks" "$R/plugins/notrest/skills/alpha" \
         "$R/plugins/notrest/skills/oracle"
printf 'OUTSIDE-ROOT-CANARY-mustnotbeserved\n' > "$TMP/outside-secret.md"

cat > "$R/archive/findings.jsonl" <<'EOF'
{"id":"F-1","ts":"2026-07-27T09:00:00Z","session":"lane-a","skill":"researcher","kind":"finding","ask":"does the cockpit read the estate","statement":"it reads the files, it never runs a skill","evidence":[],"relation":"toward","links":[],"status":"live"}
{"id":"F-2","ts":"2026-07-27T10:00:00Z","session":"lane-a","skill":"researcher","kind":"result","ask":"is it a control panel","statement":"no — one mail slot, every other route is a read","evidence":[],"relation":"toward","links":["F-1"],"status":"live"}
EOF
cat > "$R/COORD.md" <<'EOF'
# COORD.md — session coordination ledger

## LEDGER
- [2026-07-27 09:15Z] [lane-a] cockpit scaffolded -> server up | evidence: this fixture
- [2026-07-27 09:30Z] [lane-a] cockpit gated -> v9.9.9 shipped | evidence: commit abc1234
- [2026-07-27 09:45Z] [pulse] estate pulse -> doctor=0 eval=0 watch-due=1 compile=cold spend=CLEAN river=findings+coord | evidence: pulse.sh
EOF
cat > "$R/COORD-AGENTS.md" <<'EOF'
# COORD-AGENTS.md — agent activity ledger (auto-written)

## LEDGER
- [2026-07-27 09:20Z] agent=aaa111 model=claude-opus-5 bytes=1000 | last: banked one | transcript: /tmp/a1.jsonl | brief: briefs/agent-aaa111.md
- [2026-07-27 09:25Z] agent=bbb222 model=claude-opus-5 bytes=2000 | last: dead pointer | transcript: /tmp/a2.jsonl | brief: briefs/agent-bbb222.md
- [2026-07-27 09:35Z] agent=ccc333 model=? bytes=? | last: no pointer | transcript: /tmp/a3.jsonl
- [2026-07-27 09:40Z] agent=ddd444 model=claude-opus-5 bytes=10 | last: escapes root | transcript: /tmp/a4.jsonl | brief: ../outside-secret.md
EOF
cat > "$R/briefs/agent-aaa111.md" <<'EOF'
# lane brief — agent-aaa111

- extracted: 2026-07-27 09:20Z
- agent: aaa111

Auto-extracted by the notrest SubagentStop hook.

---

BUILD THE COCKPIT: one page, always on, the estate live. VERBATIM-COMMISSION-CANARY.
EOF
cat > "$R/watch/watchlist.md" <<'EOF'
# watchlist — facts under watch

## CLAUDE.md:1 — a watched claim · added 2026-07-27
| ID | Claim (verbatim) | Source | Tier | First verified | Last checked | Status | Cadence | Hash |
|----|------------------|--------|------|----------------|--------------|--------|---------|------|
| W1 | "the cockpit binds loopback only" | https://example.invalid/docs | T1 | 2026-07-27 | 2026-07-27 | HOLDS | weekly | deadbeefdeadbeef |
EOF
cat > "$R/watch/drift-log.md" <<'EOF'
# drift-log — dated recheck cycles

## 2026-07-27 — recheck cycle
**Result:** 1 HOLDS · 0 DRIFTED (of 1 due)
EOF
printf -- '---\nname: alpha\n---\n# alpha\n\n## Chains\n\nHand off to `/oracle`.\n' \
  > "$R/plugins/notrest/skills/alpha/SKILL.md"
printf -- '---\nname: oracle\n---\n# oracle\n\n- **Route to the right tool:** do a thing → `/alpha`\n' \
  > "$R/plugins/notrest/skills/oracle/SKILL.md"
cat > "$R/plugins/notrest/hooks/router.sh" <<'EOF'
#!/bin/bash
SKILL=""; SHAPE=""
case "$NORM" in
  *" do a thing"*)  SKILL=alpha; SHAPE=thing ;;
esac
exit 0
EOF

export CHATROOM_ROOT="$TMP/chatrooms"
export CHATROOM_NO_SPEND=1
export NOTREST_LIBRARY_ROOT="$TMP/library"
mkdir -p "$NOTREST_LIBRARY_ROOT"
printf '{"id":"C-1","ts":"2026-07-27T09:00:00Z","name":"the cockpit","terms":["cockpit","live"],"members":["e:F-1"],"projects":["estate"],"cohesion":0.9,"status":"OPEN","settled":null}\n' \
  > "$NOTREST_LIBRARY_ROOT/concepts.jsonl"
printf '{"name":"estate","root":"%s","ts":"2026-07-27T09:00:00Z"}\n' "$R" \
  > "$NOTREST_LIBRARY_ROOT/registry.jsonl"

echo "── phase A: the server ─────────────────────────────────────────────────"
python3 "$COCKPIT" serve --root "$R" --port "$PORT" --no-open > "$TMP/serve.log" 2>&1 &
PID=$!
UP=""
for _ in $(seq 1 60); do
  [ "$(code "$U/health")" = "200" ] && { UP=1; break; }
  sleep 0.25
done
if [ -n "$UP" ]; then ok "server answers /health on 127.0.0.1:$PORT"
else bad "server never came up"; sed 's/^/      /' "$TMP/serve.log"; echo "fixture: $PASSES passed, $((FAILS)) failed"; exit 1; fi

chk "health reports the loopback bind" "127.0.0.1" "$(body "$U/health" | jval bind)"
# the SOCKET, not the server's own claim about itself
LISTEN="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | tail -n +2 | awk '{print $9}' | head -1)"
case "$LISTEN" in
  127.0.0.1:*) ok "the listening socket is bound to 127.0.0.1 ($LISTEN)" ;;
  "")          ok "lsof unavailable — bind asserted from /health only" ;;
  *)           bad "socket is not loopback-only: $LISTEN" ;;
esac
chk "GET / serves the page" 200 "$(code "$U/")"
if [ -f "$R/graph/cockpit.html" ]; then ok "cockpit.html was written into graph/"
else bad "graph/cockpit.html was not written"; fi
PAGE="$TMP/page.html"; body "$U/" > "$PAGE"
if grep -q "prefers-color-scheme: dark" "$PAGE" \
   && grep -q 'data-theme="dark"' "$PAGE" && grep -q 'data-theme="light"' "$PAGE"; then
  ok "both themes present in the page"
else bad "theme hooks missing from the cockpit page"; fi
EXT=$(grep -oE '(src|href)="[^"]+"|https?://[^"'"'"' )]+' "$PAGE" \
      | grep -v 'www.w3.org/2000/svg' | grep -vE '"/(pic|data|room)/' | wc -l | tr -d ' ')
chk "external assets referenced by the page" 0 "$EXT"
if hdr "$U/data/pulse.json" | grep -qi '^x-cockpit-generated:'; then
  ok "the staleness stamp ships as a response header"
else bad "no X-Cockpit-Generated header"; fi

echo "── phase B: every panel answers ────────────────────────────────────────"
for E in coord agents spend pulse watch library findings version; do
  C="$(code "$U/data/$E.json")"
  if [ "$C" = "200" ] && body "$U/data/$E.json" | jok; then
    ok "/data/$E.json 200 + parses"
  else
    bad "/data/$E.json: http $C or unparseable"
  fi
done
chk "coord parsed the seeded ledger"     3 "$(body "$U/data/coord.json"   | jval shown)"
chk "agents parsed the seeded lanes"     4 "$(body "$U/data/agents.json"  | jval shown)"
chk "agents resolved one commission"     1 "$(body "$U/data/agents.json"  | jval commissions)"
chk "pulse found the seeded line"    "2026-07-27 09:45Z" "$(body "$U/data/pulse.json" | jval ts)"
chk "pulse verdict"                 "OK" "$(body "$U/data/pulse.json"  | jval verdict)"
chk "watch parsed the row"               1 "$(body "$U/data/watch.json"   | jval count)"
chk "watch row status"             "HOLDS" "$(body "$U/data/watch.json"   | jval rows.0.status)"
chk "library read the shelf"    "the cockpit" "$(body "$U/data/library.json" | jval concepts.0.name)"
chk "version read the manifest-less root" "(no git HEAD)" "$(body "$U/data/version.json" | jval head)"

echo "── phase C: commissions and the containment refusal ────────────────────"
chk "a banked brief serves"   200 "$(code "$U/data/briefs/aaa111.json")"
if body "$U/data/briefs/aaa111.json" | grep -q "VERBATIM-COMMISSION-CANARY"; then
  ok "the brief is served verbatim, not summarized"
else bad "the brief text did not reach the endpoint"; fi
chk "brief state"          "banked" "$(body "$U/data/briefs/aaa111.json" | jval state)"
chk "a dead pointer 404s"      404 "$(code "$U/data/briefs/bbb222.json")"
chk "dead pointer state"  "missing" "$(body "$U/data/briefs/bbb222.json" | jval state)"
# the ledger names ../outside-secret.md; the id route can only ever build a
# briefs/agent-<id>.md path, and read_brief refuses anything that escapes anyway
chk "an unsafe brief id is refused" 400 "$(code "$U/data/briefs/..%2f..%2foutside-secret")"
if body "$U/data/agents.json" | grep -q "OUTSIDE-ROOT-CANARY"; then
  bad "an outside-root brief pointer leaked its content into /data/agents"
else
  ok "the outside-root pointer is refused unread (its content never appears)"
fi
chk "the escaping lane is marked, not followed" "outside-root" \
    "$(body "$U/data/agents.json" | python3 -c "
import json,sys
print({x['agent']:x for x in json.load(sys.stdin)['lanes']}['ddd444']['brief_state'])" 2>/dev/null || echo '<ERR>')"

echo "── phase D: the pictures ───────────────────────────────────────────────"
chk "/pic/river.html serves"   200 "$(code "$U/pic/river.html")"
chk "/pic/journey.html serves" 200 "$(code "$U/pic/journey.html")"
chk "/pic/graph.html serves"   200 "$(code "$U/pic/graph.html")"
chk "an unknown picture 404s"  404 "$(code "$U/pic/nope.html")"
# inside the debounce window a touched input must NOT trigger a second render
touch "$R/archive/findings.jsonl"
S1="$(hdr "$U/pic/river.html" | sed -n 's/^[Xx]-[Cc]ockpit-[Rr]ender: *//p')"
chk "a hit inside the debounce window does not rebuild" "debounced" "$S1"
# once the window has passed, a touched input DOES trigger one
sleep 6
touch "$R/archive/findings.jsonl"
S2="$(hdr "$U/pic/river.html" | sed -n 's/^[Xx]-[Cc]ockpit-[Rr]ender: *//p')"
chk "a touched input past the window rebuilds" "rebuilt" "$S2"
S3="$(hdr "$U/pic/river.html" | sed -n 's/^[Xx]-[Cc]ockpit-[Rr]ender: *//p')"
chk "the very next hit is debounced again" "debounced" "$S3"
sleep 6
S4="$(hdr "$U/pic/river.html" | sed -n 's/^[Xx]-[Cc]ockpit-[Rr]ender: *//p')"
chk "an untouched input past the window is left alone" "fresh" "$S4"
if grep -q "river —" "$R/graph/river.html" 2>/dev/null; then
  ok "the render on disk is graph.py's own river page"
else bad "graph/river.html is not a river render"; fi

echo "── phase E: the one mail slot ──────────────────────────────────────────"
python3 "$HERE/../../chatroom/scripts/room.py" create fixtureroom >/dev/null 2>&1
chk "GET /room/<name> reads the room" 200 "$(code "$U/room/fixtureroom")"
POST_OK=$(curl -s -o "$TMP/p1.json" -w '%{http_code}' --max-time 60 \
  -H 'Content-Type: application/json' \
  -d '{"handle":"fixture","text":"the cockpit is a window plus one mail slot"}' \
  "$U/room/fixtureroom")
chk "a normal post is accepted" 200 "$POST_OK"
chk "room.py exited 0"            0 "$(jval exit < "$TMP/p1.json")"
if body "$U/room/fixtureroom" | grep -q "window plus one mail slot"; then
  ok "the post round-trips into the room tail"
else bad "the posted line never appeared in the tail"; fi
# THE GATE IS ROOM.PY'S — the cockpit neither pre-screens nor overrides it
REF=$(curl -s -o "$TMP/p2.json" -w '%{http_code}' --max-time 60 \
  -H 'Content-Type: application/json' \
  -d '{"handle":"fixture","text":"api_key = sk-live-AbCdEf0123456789xyz"}' \
  "$U/room/fixtureroom")
chk "a secret-shaped post is refused"        422 "$REF"
chk "the refusal is room.py's own exit 5"      5 "$(jval exit < "$TMP/p2.json")"
chk "the payload says it was not posted"  "False" "$(python3 -c "
import json;print(json.load(open('$TMP/p2.json'))['posted'])" 2>/dev/null || echo '<ERR>')"
if grep -rq "sk-live-AbCdEf0123456789xyz" "$CHATROOM_ROOT" 2>/dev/null; then
  bad "the refused secret still reached the room file"
else
  ok "nothing was written for the refused post"
fi
chk "a bad body is rejected"    400 "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 \
  -H 'Content-Type: application/json' -d 'not json' "$U/room/fixtureroom")"
chk "an unsafe room name is rejected" 400 "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 \
  -H 'Content-Type: application/json' -d '{"handle":"f","text":"x"}' "$U/room/..%2fetc")"

echo "── phase F: everything else is a read, or a 404 ────────────────────────"
chk "an unknown route 404s"        404 "$(code "$U/nope")"
chk "an unknown data panel 404s"   404 "$(code "$U/data/nosuch.json")"
# THERE IS NO SECOND WRITE ROUTE. A POST anywhere but the mail slot is a 404.
for P in / data/coord.json pic/river.html data/briefs/aaa111.json; do
  C=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 -X POST -d '{}' "$U/$P")
  chk "POST /$P is not a write route" 404 "$C"
done

echo "── phase G: reap ───────────────────────────────────────────────────────"
kill "$PID" 2>/dev/null
wait "$PID" 2>/dev/null              # reap here, so the shell prints no job notice
for _ in $(seq 1 40); do kill -0 "$PID" 2>/dev/null || break; sleep 0.25; done
if kill -0 "$PID" 2>/dev/null; then bad "the server did not stop on SIGTERM"
else ok "the server stopped and released the port"; fi
PID=""
sleep 0.5
if [ "$(code "$U/health")" = "000" ]; then ok "nothing is listening on $PORT any more"
else bad "something is still answering on $PORT"; fi

echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
