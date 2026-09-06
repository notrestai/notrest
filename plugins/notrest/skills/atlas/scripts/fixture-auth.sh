#!/usr/bin/env bash
# fixture-auth.sh — the arms for atlas_auth.py (docket 4.9, lane A3).
#
# IDENTITY-CONTRACT.md §1 (device flow and its exact statuses), §2 (refresh, JWKS), §4 (revoked).
# Every arm is red-first: it fails if the guard it names is removed. The hub is mockhub.py (lane
# A1) on 127.0.0.1 — no network leaves this box. The verdict is atlas_token.py (lane A2), so an
# arm that says "verdict ok" is the REAL verifier saying it, not this script's opinion.
#
# The last arm is the one that matters most: the minted token's middle 20 characters must not
# appear anywhere in anything this fixture printed — client output, hub log, or error path.
# A login client that fails honestly must also fail quietly about the secret.
#
#   usage: bash fixture-auth.sh [-v]        exit 0 = all arms passed

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/usr/bin/python3
AUTH="$HERE/atlas_auth.py"
MOCKHUB="$HERE/mockhub.py"
TOKEN_MOD="$HERE/atlas_token.py"
VERBOSE="${1:-}"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/fixture-auth.XXXXXX")"
LOG="$WORK/fixture.log"
: >"$LOG"
: >"$WORK/pids"

PASS=0
FAIL=0
RC=0

cleanup() {
    if [ -f "$WORK/pids" ]; then
        while read -r p; do
            [ -n "$p" ] && kill "$p" 2>/dev/null
        done <"$WORK/pids"
    fi
    rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

say()  { printf '%s\n' "$*" | tee -a "$LOG"; }
arm()  { say ""; say "ARM $*"; }
ok()   { PASS=$((PASS + 1)); say "  PASS $*"; }
bad()  { FAIL=$((FAIL + 1)); say "  FAIL $*"; }

# run <tag> <cmd...> — stdout to $WORK/<tag>.out, stderr to $WORK/<tag>.err, both into the log.
run() {
    tag="$1"; shift
    "$@" >"$WORK/$tag.out" 2>"$WORK/$tag.err"
    RC=$?
    {
        echo "--- $tag  rc=$RC  cmd: $*"
        echo "--- $tag stdout:"; cat "$WORK/$tag.out"
        echo "--- $tag stderr:"; cat "$WORK/$tag.err"
    } >>"$LOG"
    if [ -n "$VERBOSE" ]; then
        echo "  ($tag rc=$RC)"
    fi
    return 0
}

now_ms() { "$PY" -c 'import time;print(int(time.time()*1000))'; }

mode_of() {  # portable "0600" read
    stat -f '%Lp' "$1" 2>/dev/null || stat -c '%a' "$1" 2>/dev/null
}

free_port() {  # a port nothing is listening on: bind, read, close
    "$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));p=s.getsockname()[1];s.close();print(p)'
}

# verdict <home> — the REAL atlas_token verdict: prints the reason, exits 0 (ok) or 7 (not).
verdict() {
    "$PY" -c '
import sys
sys.path.insert(0, sys.argv[1])
import atlas_token
ok, reason, claims = atlas_token.verdict(sys.argv[2])
print(reason)
sys.exit(0 if ok else 7)
' "$HERE" "$1"
}

claim() {  # claim <home> <name> — one claim value, or "" when the token does not verify
    "$PY" -c '
import sys
sys.path.insert(0, sys.argv[1])
import atlas_token
ok, reason, claims = atlas_token.verdict(sys.argv[2])
print((claims or {}).get(sys.argv[3], "") if ok else "")
' "$HERE" "$1" "$2"
}

post_json() {  # post_json <url> <json> — a control call to the mock hub (never a bearer)
    "$PY" -c '
import json, sys, urllib.request
req = urllib.request.Request(sys.argv[1], data=sys.argv[2].encode(), method="POST")
req.add_header("content-type", "application/json")
with urllib.request.urlopen(req, timeout=5) as r:
    sys.stdout.write(str(r.getcode()))
' "$1" "$2"
}

start_hub() {  # start_hub <name> <mode> <auto-approve-after> ; sets HUB
    name="$1"; mode="$2"; auto="$3"
    "$PY" "$MOCKHUB" --port 0 --mode "$mode" --auto-approve-after "$auto" --print-port \
        >"$WORK/hub-$name.port" 2>"$WORK/hub-$name.log" &
    echo $! >>"$WORK/pids"
    wait_for_port "$name"
}

start_nearhub() {  # a mockhub whose FIRST token expires in 3 days (inside the §2 refresh window)
    "$PY" "$WORK/nearhub.py" "$HERE" >"$WORK/hub-near.port" 2>"$WORK/hub-near.log" &
    echo $! >>"$WORK/pids"
    wait_for_port "near"
}

wait_for_port() {
    name="$1"; HUB=""; i=0
    while [ $i -lt 150 ]; do
        p="$(head -n1 "$WORK/hub-$name.port" 2>/dev/null)"
        case "$p" in
            ''|*[!0-9]*) ;;
            *) HUB="http://127.0.0.1:$p"; return 0 ;;
        esac
        sleep 0.1
        i=$((i + 1))
    done
    say "  (hub $name never printed a port; log follows)"
    cat "$WORK/hub-$name.log" | tee -a "$LOG"
    return 1
}

# ---------------------------------------------------------------------- preflight

say "fixture-auth — atlas_auth.py against mockhub.py on 127.0.0.1"
say "work: $WORK"

for f in "$AUTH" "$MOCKHUB" "$TOKEN_MOD"; do
    if [ ! -f "$f" ]; then
        say "MISSING $f — this fixture needs lanes A1 (mockhub.py) and A2 (atlas_token.py)"
        exit 1
    fi
done
if ! command -v node >/dev/null 2>&1; then
    say "MISSING node — mockhub.py signs its Ed25519 tokens with it (see mockhub.py's docstring)"
    exit 1
fi

cat >"$WORK/nearhub.py" <<'PY_EOF'
"""A mockhub.py whose FIRST minted token sits inside the 7-day refresh window.

mockhub mints exp = now + 30 days for everything, so the §2 rule "refresh only when
exp - now < 7 days" has no reachable true-branch against it. Rather than fork the hub,
this subclasses it and overrides one method: token #1 expires in 3 days, every later one
(i.e. the refresh) in 30 — so a rotation is visible as a longer life, not just a new string.
"""
import importlib.util
import sys
import time

scripts = sys.argv[1]
spec = importlib.util.spec_from_file_location("mockhub", scripts + "/mockhub.py")
mockhub = importlib.util.module_from_spec(spec)
sys.modules["mockhub"] = mockhub
spec.loader.exec_module(mockhub)


class NearHub(mockhub.MockHub):
    minted = 0

    def build_claims(self, *a, **k):
        claims = mockhub.MockHub.build_claims(self, *a, **k)
        days = 3 if self.minted == 0 else 30
        claims["exp"] = int(time.time()) + days * 86400
        self.minted += 1
        return claims


httpd = NearHub(("127.0.0.1", 0), mockhub._Handler, mode="ok", auto_approve_after=1)
print(httpd.server_address[1])
sys.stdout.flush()
httpd.serve_forever()
PY_EOF

# ---------------------------------------------------------------------- arm 0

arm 0 "atlas_auth.py compiles under $($PY -V 2>&1)"
run compile "$PY" -m py_compile "$AUTH"
if [ $RC -eq 0 ]; then ok "py_compile"; else bad "py_compile rc=$RC"; fi

# ---------------------------------------------------------------------- arm 1

arm 1 "login happy path — 428 then 200, token 0600, the real verdict says ok"
H1="$WORK/home1"
start_hub ok ok 1 || bad "hub ok did not start"
HUB_OK="$HUB"
run login1 "$PY" "$AUTH" login --base "$HUB_OK" --home "$H1"

[ $RC -eq 0 ] && ok "exit 0" || bad "exit $RC (expected 0)"

lines=$(wc -l <"$WORK/login1.err" | tr -d ' ')
[ "$lines" = "2" ] && ok "exactly two lines on stderr" || bad "stderr had $lines lines, expected 2"
grep -q "^Open $HUB_OK/activate and enter the code: ..*" "$WORK/login1.err" \
    && ok "line 1: Open <uri> and enter the code: <code>" \
    || bad "line 1 wrong: $(head -n1 "$WORK/login1.err")"
grep -q '^Waiting (expires in 30 s)' "$WORK/login1.err" \
    && ok "line 2: Waiting (expires in 30 s)" \
    || bad "line 2 wrong: $(sed -n 2p "$WORK/login1.err")"
grep -q '^atlas-token: ok ' "$WORK/login1.out" \
    && ok "stdout: atlas-token: ok …" || bad "stdout: $(cat "$WORK/login1.out")"

if [ -f "$H1/atlas-token" ]; then
    m=$(mode_of "$H1/atlas-token")
    [ "$m" = "600" ] && ok "token file 0600" || bad "token file mode $m, expected 600"
    dm=$(mode_of "$H1")
    [ "$dm" = "700" ] && ok "home dir 0700" || bad "home dir mode $dm, expected 700"
else
    bad "no token at $H1/atlas-token"
fi
[ -s "$H1/atlas-jwks.json" ] && ok "jwks cached" || bad "no jwks cache"
[ -s "$H1/atlas-revoked.json" ] && ok "revoked list cached" || bad "no revoked cache"

# The real verifier. This also proves the fingerprint sent in the start body came back as
# `mid` — a wrong fp anywhere in the chain lands here as `mid: mismatch`, not as a pass.
run verdict1 verdict "$H1"
[ $RC -eq 0 ] && ok "atlas_token.verdict: ok" || bad "verdict rc=$RC ($(cat "$WORK/verdict1.out"))"

# ---------------------------------------------------------------------- arm 2

arm 2 "410 expired_token → exit 7 with the exact fact"
start_hub expired expired 1 || bad "hub expired did not start"
run login2 "$PY" "$AUTH" login --base "$HUB" --home "$WORK/home2"
[ $RC -eq 7 ] && ok "exit 7" || bad "exit $RC (expected 7)"
grep -qF 'RED login: code expired — run login again' "$WORK/login2.err" \
    && ok "RED login: code expired — run login again" \
    || bad "wrong fact: $(cat "$WORK/login2.err")"
[ -f "$WORK/home2/atlas-token" ] && bad "a failed login left a token behind" \
    || ok "no token written on a failed login"

# ---------------------------------------------------------------------- arm 3

arm 3 "403 access_denied → exit 7 with the exact fact"
start_hub denied denied 1 || bad "hub denied did not start"
run login3 "$PY" "$AUTH" login --base "$HUB" --home "$WORK/home3"
[ $RC -eq 7 ] && ok "exit 7" || bad "exit $RC (expected 7)"
grep -qF 'RED login: denied in the portal' "$WORK/login3.err" \
    && ok "RED login: denied in the portal" || bad "wrong fact: $(cat "$WORK/login3.err")"

# ---------------------------------------------------------------------- arm 4

arm 4 "429 slow_down → the client waits LONGER (interval += 5) and still succeeds"
start_hub slow slow 1 || bad "hub slow did not start"
t0=$(now_ms)
run login4 "$PY" "$AUTH" login --base "$HUB" --home "$WORK/home4"
t1=$(now_ms)
el=$((t1 - t0))
[ $RC -eq 0 ] && ok "exit 0 (a 429 is not fatal)" || bad "exit $RC (expected 0)"
# interval is 1 s; one 429 must push the next poll out by 5 s. Under 5 s means the client
# ignored slow_down — the arm that fails when the `interval += 5` line is deleted.
[ "$el" -ge 5000 ] && ok "second poll waited ${el} ms (≥ 5000: slow_down honoured)" \
    || bad "only ${el} ms elapsed — slow_down was not honoured"
[ "$el" -lt 20000 ] && ok "and did not stall (< 20 s)" || bad "took ${el} ms"

# ---------------------------------------------------------------------- arm 5

arm 5 "hub down → exit 7, one fact, no stack trace"
DEAD="http://127.0.0.1:$(free_port)"
run login5 "$PY" "$AUTH" login --base "$DEAD" --home "$WORK/home5"
[ $RC -eq 7 ] && ok "exit 7" || bad "exit $RC (expected 7)"
grep -qF "RED hub unreachable at $DEAD" "$WORK/login5.err" \
    && ok "RED hub unreachable at $DEAD" || bad "wrong fact: $(cat "$WORK/login5.err")"
grep -q 'Traceback' "$WORK/login5.err" && bad "a traceback reached the user" \
    || ok "no traceback"

# ---------------------------------------------------------------------- arm 6a

arm 6a "refresh INSIDE the 7-day window rotates the token and extends its life"
H6="$WORK/home6"
start_nearhub || bad "nearhub did not start"
HUB_NEAR="$HUB"
run login6 "$PY" "$AUTH" login --base "$HUB_NEAR" --home "$H6"
[ $RC -eq 0 ] && ok "login ok" || bad "login exit $RC"
before=$(shasum -a 256 <"$H6/atlas-token" | awk '{print $1}')
exp_before=$(claim "$H6" exp)
run refresh6 "$PY" "$AUTH" refresh --base "$HUB_NEAR" --home "$H6"
[ $RC -eq 0 ] && ok "refresh exit 0" || bad "refresh exit $RC (expected 0)"
after=$(shasum -a 256 <"$H6/atlas-token" | awk '{print $1}')
[ "$before" != "$after" ] && ok "the token on disk changed" || bad "the token did not rotate"
run verdict6 verdict "$H6"
[ $RC -eq 0 ] && ok "the rotated token verifies" || bad "rotated token: $(cat "$WORK/verdict6.out")"
exp_after=$(claim "$H6" exp)
if [ -n "$exp_before" ] && [ -n "$exp_after" ] && [ "$exp_after" -gt "$exp_before" ]; then
    ok "exp moved out by $((exp_after - exp_before)) s"
else
    bad "exp did not extend ($exp_before → $exp_after)"
fi
m=$(mode_of "$H6/atlas-token")
[ "$m" = "600" ] && ok "rotated token still 0600" || bad "rotated token mode $m"
[ "$(mode_of "$H6")" = "700" ] && ok "home still 0700" || bad "home mode changed"

# ---------------------------------------------------------------------- arm 6b

arm 6b "refresh OUTSIDE the window does nothing — no call, no rotation, exit 1"
before=$(shasum -a 256 <"$H1/atlas-token" | awk '{print $1}')
run refresh1 "$PY" "$AUTH" refresh --base "$HUB_OK" --home "$H1"
[ $RC -eq 1 ] && ok "exit 1" || bad "exit $RC (expected 1: 30 days left, nothing to do)"
after=$(shasum -a 256 <"$H1/atlas-token" | awk '{print $1}')
[ "$before" = "$after" ] && ok "the token was left alone" || bad "a 30-day token was rotated"
[ ! -s "$WORK/refresh1.out" ] && [ ! -s "$WORK/refresh1.err" ] \
    && ok "silent" || bad "refresh printed something"

# ---------------------------------------------------------------------- arm 7

arm 7 "sessionstart with a black-hole hub: exit 0, nothing on stdout, inside the budget"
# A closed port fails instantly and would prove nothing. This socket accepts the connection
# and then never answers — the case that actually hangs a SessionStart hook.
"$PY" -c '
import socket, sys, time
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", 0)); s.listen(16)
print(s.getsockname()[1]); sys.stdout.flush()
while True: time.sleep(3600)
' >"$WORK/hub-blackhole.port" 2>"$WORK/hub-blackhole.log" &
echo $! >>"$WORK/pids"
wait_for_port blackhole || bad "black-hole listener did not start"
BLACKHOLE="$HUB"
t0=$(now_ms)
run session7 "$PY" "$AUTH" sessionstart --base "$BLACKHOLE" --home "$H1" --budget-ms 1500
t1=$(now_ms)
el=$((t1 - t0))
[ $RC -eq 0 ] && ok "exit 0 (a hook never fails a session start)" || bad "exit $RC (expected 0)"
[ ! -s "$WORK/session7.out" ] && ok "nothing on stdout" || bad "stdout: $(cat "$WORK/session7.out")"
[ ! -s "$WORK/session7.err" ] && ok "nothing on stderr either" || bad "stderr: $(cat "$WORK/session7.err")"
# 1500 ms of budget, three steps: without the shared deadline this is 3 × the default timeout.
[ "$el" -lt 3000 ] && ok "returned in ${el} ms (budget 1500)" || bad "took ${el} ms — budget ignored"
[ "$el" -ge 900 ] && ok "and it really did reach for the hub (${el} ms)" \
    || bad "returned in ${el} ms — it never tried"

# ---------------------------------------------------------------------- arm 8

arm 8 "§4 revocation: the hub lists the jti, the fetch caches it, the verdict turns red"
JTI=$(claim "$H1" jti)
[ -n "$JTI" ] && ok "read the live jti from the claims" || bad "no jti in the claims"
code=$(post_json "$HUB_OK/_mock/revoke" "{\"jti\": \"$JTI\"}")
[ "$code" = "200" ] && ok "hub accepted the revocation" || bad "hub said $code"
run revoked8 "$PY" "$AUTH" revoked --base "$HUB_OK" --home "$H1"
[ $RC -eq 0 ] && ok "revoked fetch exit 0" || bad "revoked fetch exit $RC"
[ ! -s "$WORK/revoked8.out" ] && [ ! -s "$WORK/revoked8.err" ] && ok "silent" \
    || bad "the revoked fetch printed something"
grep -qF "$JTI" "$H1/atlas-revoked.json" && ok "the jti is in the cache" \
    || bad "cache missing the jti: $(cat "$H1/atlas-revoked.json")"
run verdict8 verdict "$H1"
[ $RC -eq 7 ] && ok "verdict exit 7" || bad "verdict exit $RC (expected 7)"
[ "$(cat "$WORK/verdict8.out")" = "jti: revoked" ] \
    && ok "reason: jti: revoked" || bad "reason: $(cat "$WORK/verdict8.out")"

# ---------------------------------------------------------------------- arm 9

arm 9 "NOTREST_HOME is EXPANDED, not taken literally (COMMON amendment)"
# atlas.py, atlas_token.py and this client must resolve one home. `NOTREST_HOME=~/alt` read
# without expanduser gives a literal `./~/alt` directory next to the CWD — the hook and the
# script then answer the same gate question differently. HOME is redirected into the fixture's
# own tree, and the whole run happens inside $WORK so a mutant's literal `~` dir cannot land
# in the repo.
FAKE="$WORK/fakehome"
H9="$FAKE/atlas-alt"
mkdir -p "$FAKE"
cat >"$WORK/run-in.sh" <<'SH'
#!/bin/sh
cd "$1" || exit 1; shift
HOME="$1"; export HOME; shift
NOTREST_HOME='~/atlas-alt'; export NOTREST_HOME
exec "$@"
SH
start_hub tilde ok 1 || bad "hub tilde did not start"
run login9 sh "$WORK/run-in.sh" "$WORK" "$FAKE" "$PY" "$AUTH" login --base "$HUB"
[ $RC -eq 0 ] && ok "exit 0 (no --home: the env is the only resolution)" || bad "exit $RC"
if [ -f "$H9/atlas-token" ]; then
    ok "token landed at the EXPANDED path (\$HOME/atlas-alt)"
    m=$(mode_of "$H9/atlas-token")
    [ "$m" = "600" ] && ok "and still 0600" || bad "mode $m"
else
    bad "no token at $H9/atlas-token — NOTREST_HOME was not expanded"
fi
[ -e "$WORK/~" ] && bad "a literal '~' directory was created: the env value was used verbatim" \
    || ok "no literal '~' directory anywhere"
run verdict9 verdict "$H9"
[ $RC -eq 0 ] && ok "the real verdict on the expanded home: ok" \
    || bad "verdict rc=$RC ($(cat "$WORK/verdict9.out"))"

# ---------------------------------------------------------------------- arm 10

arm 10 "the secret never surfaced — grep every byte this fixture printed"
LEAK=0
for h in "$H1" "$H6" "$H9"; do
    tok=$(tr -d '\r\n' <"$h/atlas-token")
    len=${#tok}
    if [ "$len" -lt 40 ]; then bad "token at $h looks wrong ($len chars)"; continue; fi
    mid=$(( len / 2 - 10 ))
    needle=$(printf '%s' "$tok" | cut -c $((mid + 1))-$((mid + 20)))
    for f in "$LOG" "$WORK"/*.out "$WORK"/*.err "$WORK"/hub-*.log; do
        [ -f "$f" ] || continue
        if grep -qF "$needle" "$f"; then
            LEAK=$((LEAK + 1)); bad "20 chars of the token appear in $(basename "$f")"
        fi
        if grep -qF "$tok" "$f"; then
            LEAK=$((LEAK + 1)); bad "the whole token appears in $(basename "$f")"
        fi
    done
done
[ "$LEAK" -eq 0 ] && ok "no token value in any output, hub log or error path" \
    || bad "$LEAK leak(s)"
# and the token never rode in a URL: the hub logs its request lines, tokens ride in headers
if grep -qi 'token=' "$WORK"/hub-*.log 2>/dev/null; then
    bad "a token-looking query parameter reached the hub log"
else
    ok "no token-shaped query parameter anywhere"
fi

# ---------------------------------------------------------------------- verdict

say ""
say "fixture-auth: $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then
    say "log: $LOG (kept)"
    cp "$LOG" "${TMPDIR:-/tmp}/fixture-auth-failed.log" 2>/dev/null
    exit 1
fi
exit 0
