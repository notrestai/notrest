#!/bin/bash
# fixture-token.sh — asserts atlas_token.py against NODE-SIGNED tokens in a mktemp dir.
#
# node (OpenSSL Ed25519) SIGNS every fixture; python (atlas_token.py -> the vendored
# vendor/verify_token.py, stdlib only) VERIFIES it. Two independent implementations must
# agree, so a bug in either one shows up as a failed arm — the same arrangement Atlas's
# own kit/test-verify-token.sh uses, and the reason a fixture the module's author wrote
# is still worth something.
#
# Every key is generated FRESH at each run and only public halves are written; no private
# key and no real credential ever touches this tree. Every home is a scratch directory:
# the machine's real ~/.notrest is never read and never written.
#
# RED-FIRST. Section M mutates a COPY of atlas_token.py (one guard removed per mutant)
# and asserts the arm that guards it now gives the WRONG answer. An arm that cannot be
# made to fail is not evidence, and this section is how that claim gets checked rather
# than asserted. ATLAS_TOKEN_PY overrides the module under test for the same reason.
#
# Usage: bash plugins/notrest/skills/atlas/scripts/fixture-token.sh   (exit 0 = all held)
set -u
# This module resolves its home from NOTREST_HOME. An inherited one would aim every arm
# at the operator's real private store — which is exactly the class of bug the atlas
# fixture already paid for once with GIT_DIR.
unset NOTREST_HOME NOTREST_ACCESS_KEY NOTREST_ACCESS_KEY_FILE

S="$(cd "$(dirname "$0")" && pwd)"
T="${ATLAS_TOKEN_PY:-$S/atlas_token.py}"
CONTRACT="$(cd "$S/../../../../.." 2>/dev/null && pwd)/briefs/atlas-contract/kit/verify-token.py"
W="$(mktemp -d)"
FIX="$W/fix"
NOW=1789000000
cleanup(){ chmod -R u+w "$W" 2>/dev/null; rm -rf "$W"; rm -rf "$S/vendor/__pycache__" "$S/__pycache__"; return 0; }
trap cleanup EXIT

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }

# expect_ok NAME HOME [extra args...]
expect_ok(){
  local name="$1" h="$2"; shift 2
  local out rc
  out="$(python3 "$T" check --home "$h" --now "$NOW" "$@" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    no "$name — expected exit 0, got $rc ($(printf '%s' "$out" | head -n1))"
  else
    ok "$name"
  fi
}
# expect_red NAME HOME REASON [extra args...]
expect_red(){
  local name="$1" h="$2" reason="$3"; shift 3
  local out rc first
  out="$(python3 "$T" check --home "$h" --now "$NOW" "$@" 2>&1)"; rc=$?
  first="$(printf '%s\n' "$out" | head -n1)"
  if [ "$rc" -ne 7 ]; then
    no "$name — expected exit 7, got $rc (output: $first)"
  elif [ "$first" != "RED $reason" ]; then
    no "$name — expected 'RED $reason', got '$first'"
  else
    ok "$name"
  fi
}

echo "atlas token fixture · $T"

command -v node >/dev/null 2>&1 || { echo "FATAL: node >= 18 is required to sign the fixtures"; exit 1; }
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ] \
  || { echo "FATAL: node >= 18 required (Ed25519 in crypto); found $(node -v)"; exit 1; }

mkdir -p "$FIX" "$W/homes"

# ── the fingerprint this machine really has: the fixtures are minted FOR it ──────────
# Not a constant and not a mock — the mid arms are only worth something if the `mid` the
# hub would have stamped is the one this box computes, through the real platform branch.
FP="$(python3 "$T" fingerprint --home "$W/homes/_fp" 2>/dev/null)"
case "$FP" in
  [0-9a-f]*) [ "${#FP}" -eq 64 ] && ok "fingerprint is 64 hex" || no "fingerprint is not 64 hex — [$FP]" ;;
  *) no "fingerprint is not hex — [$FP]" ;;
esac

GEN="$W/gen.js"
cat > "$GEN" <<'JSEOF'
// node signs, python verifies. Fresh keys each run; only public halves are written.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const FIX = process.argv[2];
const MID = process.argv[3];
const b64u = (b) => Buffer.from(b).toString('base64')
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const write = (n, t) => fs.writeFileSync(path.join(FIX, n), t);

const KID = 'atlas-2026-09';
const NOW = 1789000000;               // fixed clock: the fixtures are reproducible
const DAY = 86400;
const OTHER_MID = crypto.createHash('sha256').update('some-other-laptop').digest('hex');
const SUB = 'spaceup@nava.house';
const SEAT = 'notrest-plugin-mac';
const JTI = '6f1c0a52-3b8e-4a71-9a6e-2c4d5e6f7a80';
const JTI_REV = 'de1e7ed0-0000-4000-8000-000000000001';
const SUB_REV = 'gone@nava.house';

const k1 = crypto.generateKeyPairSync('ed25519');   // the hub's signing key
const k2 = crypto.generateKeyPairSync('ed25519');   // a foreign key (born-red)
const jwk = (kp, kid) => Object.assign({ kid }, kp.publicKey.export({ format: 'jwk' }));

write('jwks.json', JSON.stringify({ keys: [jwk(k1, KID)] }, null, 2));
write('jwks-foreign.json', JSON.stringify({ keys: [jwk(k2, KID)] }, null, 2));

const base = (over) => Object.assign({
  iss: 'https://atlas.not.rest', aud: 'notrest-plugin',
  sub: SUB, seat: SEAT, mid: MID,
  prj: ['notrest-plugin'], scp: ['harness', 'push', 'view'],
  jti: JTI, iat: NOW, exp: NOW + 30 * DAY,
}, over || {});
function jwt(header, claims, key) {
  const h = b64u(JSON.stringify(header));
  const p = b64u(JSON.stringify(claims));
  return h + '.' + p + '.' + b64u(crypto.sign(null, Buffer.from(h + '.' + p, 'ascii'), key));
}
const HDR = { alg: 'EdDSA', typ: 'JWT', kid: KID };
const tok = (name, over, key) => {
  const t = jwt(HDR, base(over), key || k1.privateKey);
  write(name, t + '\n');
  return t;
};

tok('good.jwt', {});
tok('expired.jwt', { iat: NOW - 40 * DAY, exp: NOW - DAY });
tok('foreign.jwt', {}, k2.privateKey);
tok('wrongmid.jwt', { mid: OTHER_MID });
tok('roaming.jwt', { mid: OTHER_MID, scp: ['harness', 'roaming'] });
tok('revoked-jti.jwt', { jti: JTI_REV });
tok('revoked-sub.jwt', { sub: SUB_REV });

write('revoked.json', JSON.stringify(
  { jti: [JTI_REV], sub: [SUB_REV], as_of: '2026-09-06T00:00:00Z' }, null, 2));
write('meta.json', JSON.stringify({
  now: NOW, sub: SUB, seat: SEAT,
  exp_iso: new Date((NOW + 30 * DAY) * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z'),
}, null, 2));
JSEOF

node "$GEN" "$FIX" "$FP" || { echo "FATAL: fixture generation failed"; exit 1; }
GOODTOK="$(cat "$FIX/good.jwt")"
SUB_EXP="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["sub"])' "$FIX/meta.json")"
SEAT_EXP="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["seat"])' "$FIX/meta.json")"
ISO_EXP="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["exp_iso"])' "$FIX/meta.json")"

# home NAME [token-file] [jwks-file] [revoked-file] — echoes the path
home(){
  local h="$W/homes/$1"; mkdir -p "$h"
  [ "${2:-}" = "-" ] || { cp "$FIX/$2" "$h/atlas-token"; chmod 600 "$h/atlas-token"; }
  [ "${3:-}" = "-" ] || cp "$FIX/$3" "$h/atlas-jwks.json"
  [ "${4:--}" = "-" ] || cp "$FIX/$4" "$h/atlas-revoked.json"
  echo "$h"
}

echo "── A · the token that admits this machine"
HG="$(home good good.jwt jwks.json)"
expect_ok "a good token verifies" "$HG"
SENT="$(python3 "$T" check --home "$HG" --now "$NOW" 2>/dev/null)"
t "check prints the sentinel, and only claims" "$SENT" \
  "atlas-token: ok sub=$SUB_EXP seat=$SEAT_EXP exp=$ISO_EXP"
python3 "$T" claims --home "$HG" --now "$NOW" 2>/dev/null | grep -q '"iss": "https://atlas.not.rest"' \
  && ok "claims prints the claims as JSON" || no "claims printed no claims JSON"
t "--quiet says nothing on 0" \
  "$(python3 "$T" check --home "$HG" --now "$NOW" --quiet 2>&1 | wc -c | tr -d ' ')" "0"

echo "── B · the two conditions the verifier never sees"
expect_red "no token at all" "$(home empty - jwks.json)" "token: absent"
expect_red "a token but no keys, pinned or cached" "$(home nokeys good.jwt -)" \
  "keys: none pinned or cached"
HC="$(home corruptjwks good.jwt jwks.json)"; printf 'not json {' > "$HC/atlas-jwks.json"
expect_red "a corrupt JWKS cache is not-there, not a crash" "$HC" "keys: none pinned or cached"
HM="$(home malformed - jwks.json)"; printf 'this-is-not-a-token\n' > "$HM/atlas-token"
expect_red "a garbled atlas-token is malformed, not absent" "$HM" "token: malformed"
t "--quiet says nothing on 7" \
  "$(python3 "$T" check --home "$HM" --now "$NOW" --quiet 2>&1 | wc -c | tr -d ' ')" "0"
mkdir -p "$W/mut/novendor" && cp "$S/atlas_token.py" "$W/mut/novendor/atlas_token.py"
NV="$(python3 "$W/mut/novendor/atlas_token.py" check --home "$HG" --now "$NOW" 2>&1)"; NVRC=$?
t "a missing vendor/ is exit 7, not a traceback" "$NVRC" "7"
printf '%s' "$NV" | grep -q 'Traceback' \
  && no "a broken install threw out of the hook — [$NV]" \
  || ok "…and says one fact ($(printf '%s' "$NV" | head -n1))"

echo "── C · the reds, each one fact"
expect_red "expired" "$(home expired expired.jwt jwks.json)" "exp: expired"
expect_red "signed by a foreign key (the born-red case)" \
  "$(home foreign foreign.jwt jwks.json)" "signature: invalid"
expect_red "a good token against the wrong JWKS" \
  "$(home wrongjwks good.jwt jwks-foreign.json)" "signature: invalid"
expect_red "another machine's mid" "$(home wrongmid wrongmid.jwt jwks.json)" "mid: mismatch"
expect_red "revoked jti, from the cache" \
  "$(home revjti revoked-jti.jwt jwks.json revoked.json)" "jti: revoked"
expect_red "revoked sub — removing the user kills every token" \
  "$(home revsub revoked-sub.jwt jwks.json revoked.json)" "sub: revoked"

echo "── D · roaming, and the legacy access-key"
expect_ok "roaming scope admits a foreign mid" "$(home roaming roaming.jwt jwks.json)"
HL="$(home legacy - jwks.json)"; cp "$FIX/good.jwt" "$HL/access-key"; chmod 600 "$HL/access-key"
expect_ok "a JWT in the legacy access-key is read" "$HL"
HR="$(home ring - jwks.json)"; printf 'nrk_%s\n' "AAAABBBBCCCCDDDDEEEEFFFF" > "$HR/access-key"
expect_red "an nrk_ ring key in access-key is NOT a token" "$HR" "token: absent"
TUP="$(python3 - "$S" "$HR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import atlas_token
print(repr(atlas_token.verdict(sys.argv[2], now=1789000000)))
PY
)"
t "…and verdict returns the exact tuple" "$TUP" "(False, 'token: absent', None)"
HB="$(home both good.jwt jwks.json)"; printf 'nrk_%s\n' "ZZZZYYYYXXXXWWWWVVVVUUUU" > "$HB/access-key"
expect_ok "atlas-token wins when both files exist" "$HB"

echo "── E · the fingerprint (RULING §1) — stable, and never the hostname"
FP2="$(python3 "$T" fingerprint --home "$W/homes/_fp2" 2>/dev/null)"
t "stable across two calls, in two processes" "$FP2" "$FP"
HOSTFP="$(python3 -c 'import hashlib,socket;print(hashlib.sha256(socket.gethostname().encode()).hexdigest())')"
[ "$FP" != "$HOSTFP" ] && ok "the fingerprint is not sha256(hostname)" \
  || no "the fingerprint IS sha256(hostname) — the one input the RULING excludes"
[ -e "$W/homes/_fp/machine-id" ] \
  && no "the platform id was persisted — machine-id is the CONTAINER case only" \
  || ok "no machine-id file written where the platform has an id"
CONT="$(python3 - "$S" "$W/homes/_container" <<'PY'
import os, sys
sys.path.insert(0, sys.argv[1])
import atlas_token
home = sys.argv[2]
os.makedirs(home, exist_ok=True)
atlas_token._linux_machine_id = lambda: None      # the container case: neither platform
atlas_token._macos_machine_id = lambda: None      # source exists, so one is minted once
atlas_token._MID_CACHE.clear()
first = atlas_token.machine_id(home)
atlas_token._MID_CACHE.clear()
second = atlas_token.machine_id(home)
path = os.path.join(home, "machine-id")
print("%s %s %d %s" % (first == second, len(first),
                       os.stat(path).st_mode & 0o777, first.strip("0123456789abcdef") == ""))
PY
)"
t "container branch: minted once, stable, 64 hex, 0600" "$CONT" "True 64 384 True"

echo "── F · no secret in any output"
ALL="$(python3 "$T" check --home "$HG" --now "$NOW" 2>&1
       python3 "$T" claims --home "$HG" --now "$NOW" 2>&1
       python3 "$T" check --home "$HM" --now "$NOW" 2>&1
       python3 "$T" check --home "$HR" --now "$NOW" 2>&1
       python3 "$T" fingerprint --home "$HG" 2>&1)"
printf '%s' "$ALL" | grep -qF "$GOODTOK" \
  && no "the token value appeared in output" || ok "the token value never appears in output"
printf '%s' "$ALL" | grep -qF "$(printf '%s' "$GOODTOK" | cut -d. -f3)" \
  && no "the token's signature appeared in output" || ok "no signature segment in output"
printf '%s' "$ALL" | grep -q 'nrk_' \
  && no "a ring key appeared in output" || ok "no ring key in output"

echo "── G · the vendored verifier is byte-exact (law 2)"
if [ -f "$CONTRACT" ]; then
  t "vendor/verify_token.py == briefs/atlas-contract/kit/verify-token.py" \
    "$(shasum -a 256 "$S/vendor/verify_token.py" | cut -d' ' -f1)" \
    "$(shasum -a 256 "$CONTRACT" | cut -d' ' -f1)"
  head -n1 "$S/vendor/verify_token.py" | grep -q '© 2026 Not Rest Inc' \
    && ok "the license line is intact on line 1" || no "the license line is gone from line 1"
else
  ok "contract copy not present (consumer install) — sha comparison skipped"
fi

echo "── H · the hook budget"
BUDGET="$(python3 - "$S" "$HG" <<'PY'
import sys, time
scripts, home = sys.argv[1], sys.argv[2]
sys.path.insert(0, scripts)
t0 = time.perf_counter(); import atlas_token; imp = (time.perf_counter() - t0) * 1000
t0 = time.perf_counter(); ok1, _, _ = atlas_token.verdict(home, now=1789000000)
cold = (time.perf_counter() - t0) * 1000
t0 = time.perf_counter(); ok2, _, _ = atlas_token.verdict(home, now=1789000000)
warm = (time.perf_counter() - t0) * 1000
print("import %.1f ms · first verdict %.1f ms (loads the verifier) · warm verdict %.1f ms"
      % (imp, cold, warm))
print("BUDGET-OK" if (ok1 and ok2 and imp < 250 and cold < 250) else "BUDGET-SLOW")
PY
)"
echo "  $(printf '%s' "$BUDGET" | head -n1)"
t "import + verdict inside the hook budget" "$(printf '%s' "$BUDGET" | tail -n1)" "BUDGET-OK"

echo "── M · red-first: each guard removed, its arm must go wrong"
mut(){ # NAME  SED-EXPR
  local d="$W/mut/$1"; mkdir -p "$d"
  cp "$S/atlas_token.py" "$d/atlas_token.py"; cp -R "$S/vendor" "$d/vendor"
  rm -rf "$d/vendor/__pycache__"
  sed -i.bak "$2" "$d/atlas_token.py"; rm -f "$d/atlas_token.py.bak"
  if cmp -s "$S/atlas_token.py" "$d/atlas_token.py"; then
    no "mutant $1 — the sed changed nothing (the guard moved; this arm is asleep)"; return 1
  fi
  python3 -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" "$d/atlas_token.py" 2>/dev/null \
    || { no "mutant $1 — does not parse"; return 1; }
  echo "$d/atlas_token.py"
}

M1="$(mut nojwtcheck 's/if legacy and looks_like_token(legacy):/if legacy:/')"
[ -n "${M1:-}" ] && {
  python3 "$M1" check --home "$HR" --now "$NOW" >/dev/null 2>&1
  t "without the JWT-shape check, the ring arm goes wrong" "$?" "7"
  R1="$(python3 "$M1" check --home "$HR" --now "$NOW" 2>&1 | head -n1)"
  [ "$R1" = "RED token: absent" ] \
    && no "the ring arm cannot fail — it passes without the guard too" \
    || ok "the ring arm has teeth (mutant says '$R1')"
}

M2="$(mut hostname 's|    value = _linux_machine_id() or _macos_machine_id() or _persisted_machine_id(home)|    value = __import__("socket").gethostname()|')"
[ -n "${M2:-}" ] && {
  MFP="$(python3 "$M2" fingerprint --home "$W/homes/_m2" 2>/dev/null)"
  [ "$MFP" = "$HOSTFP" ] \
    && ok "the hostname arm has teeth (a hostname-fed mutant is caught)" \
    || no "the hostname mutant did not produce sha256(hostname) — arm proves nothing"
  python3 "$M2" check --home "$HG" --now "$NOW" >/dev/null 2>&1
  t "…and a hostname fingerprint fails the good token" "$?" "7"
}

M3="$(mut nomid 's/expect_mid=fingerprint(home),/expect_mid=None,/')"
[ -n "${M3:-}" ] && {
  python3 "$M3" check --home "$W/homes/wrongmid" --now "$NOW" >/dev/null 2>&1
  t "without expect_mid, another machine's token is admitted" "$?" "0"
}

M4="$(mut norevoked 's/revoked=load_revoked(home))/revoked=None)/')"
[ -n "${M4:-}" ] && {
  python3 "$M4" check --home "$W/homes/revjti" --now "$NOW" >/dev/null 2>&1
  t "without the revocation cache, a revoked jti is admitted" "$?" "0"
}

echo ""
echo "fixture-token: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
