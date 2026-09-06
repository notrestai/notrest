#!/usr/bin/env bash
# test-verify-token.sh — cross-implementation test for kit/verify-token.py.
#
# node (OpenSSL Ed25519) SIGNS every fixture; python (kit/verify-token.py,
# stdlib only) VERIFIES it.  Two independent implementations must agree, so a
# bug in either one shows up as a failed arm.  The RFC 8032 section 7.1
# vectors are checked too, as an anchor neither implementation authored.
#
# Usage: bash kit/test-verify-token.sh
# Exit 0 = every arm passed.

set -u

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIX="$KIT/fixtures/tokens"
VERIFY="$KIT/verify-token.py"
RFC="$FIX/rfc8032-7.1.json"

PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }

# expect_red NAME REASON -- <verify-token.py args...>
expect_red() {
  local name="$1" reason="$2"; shift 3
  local out rc first
  out="$(python3 "$VERIFY" "$@" 2>&1)"; rc=$?
  first="$(printf '%s\n' "$out" | head -n1)"
  if [ "$rc" -ne 7 ]; then
    bad "$name" "expected exit 7, got $rc (output: $first)"
  elif [ "$first" != "RED $reason" ]; then
    bad "$name" "expected 'RED $reason', got '$first'"
  else
    ok "$name"
  fi
}

# expect_ok NAME -- <verify-token.py args...>
expect_ok() {
  local name="$1"; shift 2
  local out rc
  out="$(python3 "$VERIFY" "$@" 2>&1)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    bad "$name" "expected exit 0, got $rc (output: $(printf '%s' "$out" | head -n1))"
  elif ! printf '%s' "$out" | grep -q '"iss": "https://atlas.not.rest"'; then
    bad "$name" "exit 0 but claims JSON not printed"
  else
    ok "$name"
  fi
}

echo "test-verify-token: generating fixtures with node (the signer)"

command -v node >/dev/null 2>&1 || { echo "FATAL: node >= 22 is required to sign the fixtures"; exit 1; }
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "FATAL: node >= 18 required (Ed25519 in crypto); found $(node -v)"; exit 1
fi
[ -f "$RFC" ] || { echo "FATAL: missing static RFC vector file $RFC"; exit 1; }

mkdir -p "$FIX"
# only the generated fixtures are removed; the static RFC vector file stays.
rm -f "$FIX"/*.jwt "$FIX"/jwks*.json "$FIX"/revoked*.json "$FIX"/meta.json \
      "$FIX"/differential.jsonl
# the differential arm loads verify-token.py by path; -B keeps it from
# leaving a __pycache__ in the kit, but tidy any older one away too.
rm -rf "$KIT/__pycache__"

GEN="$(mktemp "${TMPDIR:-/tmp}/atlas-gen-XXXXXX.js")"
trap 'rm -f "$GEN"' EXIT

cat > "$GEN" <<'JSEOF'
// Fixture generator: node signs, python verifies.  No secrets here — every
// key is generated fresh at each run and only the public half is written out.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const FIX = process.argv[2];
const b64u = (b) => Buffer.from(b).toString('base64')
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const write = (name, text) => fs.writeFileSync(path.join(FIX, name), text);

const KID = 'atlas-2026-09';
const KID_NEXT = 'atlas-2027-01';
const NOW = 1789000000;              // fixed clock: fixtures are reproducible
const DAY = 86400;
const MID = crypto.createHash('sha256').update('atlas-test-machine').digest('hex');
const OTHER_MID = crypto.createHash('sha256').update('some-other-laptop').digest('hex');
const JTI = '6f1c0a52-3b8e-4a71-9a6e-2c4d5e6f7a80';
const JTI_REVOKED = 'de1e7ed0-0000-4000-8000-000000000001';
const SUB = 'spaceup@nava.house';
const SUB_REVOKED = 'gone@nava.house';

const k1 = crypto.generateKeyPairSync('ed25519');   // the hub's signing key
const k2 = crypto.generateKeyPairSync('ed25519');   // a foreign key (born-red)
const k3 = crypto.generateKeyPairSync('ed25519');   // a rotation-neighbour key

const jwk = (kp, kid) => Object.assign({ kid }, kp.publicKey.export({ format: 'jwk' }));

write('jwks.json', JSON.stringify({ keys: [jwk(k1, KID)] }, null, 2));
// rotation: two live keys, plus an RSA entry a real JWKS may carry and that
// keys_from_jwks must skip rather than choke on.
write('jwks-rotation.json', JSON.stringify({
  keys: [jwk(k1, KID), jwk(k3, KID_NEXT),
         { kty: 'RSA', kid: 'legacy-rsa', n: 'AQAB', e: 'AQAB' }]
}, null, 2));
write('jwks-foreign.json', JSON.stringify({ keys: [jwk(k2, KID)] }, null, 2));

const baseClaims = (over) => Object.assign({
  iss: 'https://atlas.not.rest',
  aud: 'notrest-plugin',
  sub: SUB,
  seat: 'atlas-ce',
  mid: MID,
  prj: ['kernel', 'atlas'],
  scp: ['harness', 'push', 'view'],
  jti: JTI,
  iat: NOW,
  exp: NOW + 30 * DAY,
}, over || {});

function jwt(header, claims, key) {
  const h = b64u(JSON.stringify(header));
  const p = b64u(JSON.stringify(claims));
  const s = b64u(crypto.sign(null, Buffer.from(h + '.' + p, 'ascii'), key));
  return h + '.' + p + '.' + s;
}
const edHeader = (kid) => ({ alg: 'EdDSA', typ: 'JWT', kid: kid || KID });
const tok = (name, claims, opts) => {
  const o = opts || {};
  const t = jwt(o.header || edHeader(), baseClaims(claims), o.key || k1.privateKey);
  write(name, t + '\n');
  return t;
};

// --- the good token, and the shapes that must still pass -------------------
const good = tok('good.jwt', {});
tok('roaming-wrong-mid.jwt', { mid: OTHER_MID, scp: ['harness', 'push', 'roaming'] });
tok('exp-within-skew.jwt', { exp: NOW - 30 });          // 30 s < 60 s skew
tok('aud-list.jwt', { aud: ['notrest-plugin', 'atlas-portal'] });
tok('rotated-kid.jwt', {}, { header: edHeader(KID_NEXT), key: k3.privateKey });
tok('no-typ.jwt', {}, { header: { alg: 'EdDSA', kid: KID } });

// --- the shapes that must be refused ---------------------------------------
tok('expired.jwt', { exp: NOW - 90 });                  // 90 s > 60 s skew
tok('wrong-aud.jwt', { aud: 'someone-elses-plugin' });
tok('wrong-iss.jwt', { iss: 'https://evil.example' });
tok('wrong-mid.jwt', { mid: OTHER_MID });
tok('revoked.jwt', { jti: JTI_REVOKED });
tok('revoked-sub.jwt', { sub: SUB_REVOKED });
tok('future-iat.jwt', { iat: NOW + 3600 });
tok('unknown-kid.jwt', {}, { header: edHeader('atlas-9999-99') });
tok('foreign-key.jwt', {}, { key: k2.privateKey });     // same kid, other key
tok('bad-typ.jwt', {}, { header: { alg: 'EdDSA', typ: 'at+jwt', kid: KID } });

// two tokens for the REAL clock (no --now): one long dead, one minted now.
const REAL = Math.floor(Date.now() / 1000);
tok('ancient.jwt', { iat: 1600000000, exp: 1600000000 + 30 * DAY });
tok('fresh.jwt', { iat: REAL, exp: REAL + 30 * DAY });

// missing a required claim (no exp)
{
  const c = baseClaims({}); delete c.exp;
  write('missing-exp.jwt', jwt(edHeader(), c, k1.privateKey) + '\n');
}

// signature with one bit flipped
{
  const parts = good.split('.');
  const sig = Buffer.from(parts[2].replace(/-/g, '+').replace(/_/g, '/'), 'base64');
  sig[10] ^= 0x01;
  write('flipped-sig.jwt', parts[0] + '.' + parts[1] + '.' + b64u(sig) + '\n');
}
// payload altered after signing (prj widened to ["*"])
{
  const parts = good.split('.');
  const p = b64u(JSON.stringify(baseClaims({ prj: ['*'] })));
  write('tampered-payload.jwt', parts[0] + '.' + p + '.' + parts[2] + '\n');
}
// alg: none — the classic unsigned-token attack
write('alg-none.jwt',
  b64u(JSON.stringify({ alg: 'none', typ: 'JWT', kid: KID })) + '.' +
  b64u(JSON.stringify(baseClaims({}))) + '.' + '\n');
// alg: HS256, MAC'd with the raw public key as the secret — algorithm confusion
{
  const h = b64u(JSON.stringify({ alg: 'HS256', typ: 'JWT', kid: KID }));
  const p = b64u(JSON.stringify(baseClaims({})));
  const raw = Buffer.from(k1.publicKey.export({ format: 'jwk' }).x, 'base64url');
  const mac = crypto.createHmac('sha256', raw).update(h + '.' + p).digest();
  write('alg-hs256.jwt', h + '.' + p + '.' + b64u(mac) + '\n');
}
// structurally broken
write('malformed-2seg.jwt', good.split('.').slice(0, 2).join('.') + '\n');
write('malformed-b64.jwt', 'not*base64.also*not.nope\n');
write('empty.jwt', '\n');
// a 63-byte signature: right shape, wrong length
{
  const parts = good.split('.');
  const sig = Buffer.from(parts[2].replace(/-/g, '+').replace(/_/g, '/'), 'base64');
  write('short-sig.jwt', parts[0] + '.' + parts[1] + '.' + b64u(sig.subarray(0, 63)) + '\n');
}

// revocation lists
write('revoked.json', JSON.stringify({ jti: [JTI_REVOKED], sub: [SUB_REVOKED],
                                       as_of: NOW }, null, 2));
write('revoked-list.json', JSON.stringify([JTI_REVOKED], null, 2));

// differential corpus: 150 raw Ed25519 cases, each labelled with OpenSSL's
// verdict, so the pure-python verify can be checked against it case by case.
{
  const rows = [];
  for (let i = 0; i < 150; i++) {
    const kp = crypto.generateKeyPairSync('ed25519');
    const pub = Buffer.from(kp.publicKey.export({ format: 'jwk' }).x, 'base64url');
    const msg = crypto.randomBytes(1 + (i % 61));
    let sig = crypto.sign(null, msg, kp.privateKey);
    let m = msg;
    switch (i % 5) {
      case 1: sig = Buffer.from(sig); sig[crypto.randomInt(64)] ^= 1 << crypto.randomInt(8); break;
      case 2: m = Buffer.from(msg); m[crypto.randomInt(m.length)] ^= 1; break;
      case 3: sig = crypto.randomBytes(64); break;
      case 4: sig = Buffer.from(sig); sig[63] ^= 0x80; break;   // drives S out of range
      default: break;                                           // case 0: untouched, must verify
    }
    let ok = false;
    try { ok = crypto.verify(null, m, kp.publicKey, sig); } catch (e) { ok = false; }
    rows.push(JSON.stringify({ pub: pub.toString('hex'), msg: m.toString('hex'),
                               sig: sig.toString('hex'), openssl: ok }));
  }
  write('differential.jsonl', rows.join('\n') + '\n');
}

// what the shell needs to drive the arms
write('meta.json', JSON.stringify({
  now: NOW, mid: MID, other_mid: OTHER_MID, kid: KID, kid_next: KID_NEXT,
  jti: JTI, jti_revoked: JTI_REVOKED, sub: SUB, sub_revoked: SUB_REVOKED,
  node: process.versions.node,
}, null, 2));

// node verifies its own good token back, so a generator bug is caught here
const parts = good.split('.');
const okSelf = crypto.verify(null, Buffer.from(parts[0] + '.' + parts[1], 'ascii'),
  k1.publicKey, Buffer.from(parts[2], 'base64url'));
if (!okSelf) { console.error('generator: node cannot verify its own signature'); process.exit(1); }
console.log('generated ' + fs.readdirSync(FIX).filter(f => f.endsWith('.jwt')).length +
            ' tokens with node ' + process.versions.node);
JSEOF

node "$GEN" "$FIX" || { echo "FATAL: fixture generation failed"; exit 1; }

NOW="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["now"])' "$FIX/meta.json")"
MID="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["mid"])' "$FIX/meta.json")"
J="$FIX/jwks.json"

echo
echo "test-verify-token: arms"

# --- accepted --------------------------------------------------------------
expect_ok "good token (no mid pinned)" -- \
  --token-file "$FIX/good.jwt" --jwks-file "$J" --now "$NOW"
expect_ok "good token with the matching mid" -- \
  --token-file "$FIX/good.jwt" --jwks-file "$J" --now "$NOW" --mid "$MID"
expect_ok "roaming scope survives a foreign mid" -- \
  --token-file "$FIX/roaming-wrong-mid.jwt" --jwks-file "$J" --now "$NOW" --mid "$MID"
expect_ok "exp 30 s in the past is inside the 60 s skew" -- \
  --token-file "$FIX/exp-within-skew.jwt" --jwks-file "$J" --now "$NOW"
expect_ok "aud as a list containing notrest-plugin" -- \
  --token-file "$FIX/aud-list.jwt" --jwks-file "$J" --now "$NOW"
expect_ok "rotation: second kid in a two-key JWKS" -- \
  --token-file "$FIX/rotated-kid.jwt" --jwks-file "$FIX/jwks-rotation.json" --now "$NOW"
expect_ok "old kid still verifies from the rotated JWKS (RSA entry skipped)" -- \
  --token-file "$FIX/good.jwt" --jwks-file "$FIX/jwks-rotation.json" --now "$NOW"
expect_ok "header without typ is accepted" -- \
  --token-file "$FIX/no-typ.jwt" --jwks-file "$J" --now "$NOW"
expect_ok "revocation list that names other ids" -- \
  --token-file "$FIX/good.jwt" --jwks-file "$J" --now "$NOW" \
  --revoked-file "$FIX/revoked.json"

# --- refused ---------------------------------------------------------------
expect_red "flipped signature bit" "signature: invalid" -- \
  --token-file "$FIX/flipped-sig.jwt" --jwks-file "$J" --now "$NOW"
expect_red "payload tampered after signing" "signature: invalid" -- \
  --token-file "$FIX/tampered-payload.jwt" --jwks-file "$J" --now "$NOW"
expect_red "born-red: token signed with a different key" "signature: invalid" -- \
  --token-file "$FIX/foreign-key.jwt" --jwks-file "$J" --now "$NOW"
expect_red "good token against a JWKS holding the wrong key" "signature: invalid" -- \
  --token-file "$FIX/good.jwt" --jwks-file "$FIX/jwks-foreign.json" --now "$NOW"
expect_red "63-byte signature" "signature: invalid" -- \
  --token-file "$FIX/short-sig.jwt" --jwks-file "$J" --now "$NOW"
expect_red "expired (90 s past exp, beyond skew)" "exp: expired" -- \
  --token-file "$FIX/expired.jwt" --jwks-file "$J" --now "$NOW"
expect_red "wrong aud" "aud: mismatch" -- \
  --token-file "$FIX/wrong-aud.jwt" --jwks-file "$J" --now "$NOW"
expect_red "wrong iss" "iss: mismatch" -- \
  --token-file "$FIX/wrong-iss.jwt" --jwks-file "$J" --now "$NOW"
expect_red "unknown kid" "kid: unknown" -- \
  --token-file "$FIX/unknown-kid.jwt" --jwks-file "$J" --now "$NOW"
expect_red "wrong mid, no roaming scope" "mid: mismatch" -- \
  --token-file "$FIX/wrong-mid.jwt" --jwks-file "$J" --now "$NOW" --mid "$MID"
expect_red "good token on the wrong machine" "mid: mismatch" -- \
  --token-file "$FIX/good.jwt" --jwks-file "$J" --now "$NOW" --mid "deadbeef"
expect_red "iat an hour in the future" "iat: in the future" -- \
  --token-file "$FIX/future-iat.jwt" --jwks-file "$J" --now "$NOW"
expect_red "revoked jti (hub-shaped list)" "jti: revoked" -- \
  --token-file "$FIX/revoked.jwt" --jwks-file "$J" --now "$NOW" \
  --revoked-file "$FIX/revoked.json"
expect_red "revoked jti (bare JSON array)" "jti: revoked" -- \
  --token-file "$FIX/revoked.jwt" --jwks-file "$J" --now "$NOW" \
  --revoked-file "$FIX/revoked-list.json"
expect_red "revoked sub" "sub: revoked" -- \
  --token-file "$FIX/revoked-sub.jwt" --jwks-file "$J" --now "$NOW" \
  --revoked-file "$FIX/revoked.json"
expect_red "alg: none" "header: alg must be EdDSA" -- \
  --token-file "$FIX/alg-none.jwt" --jwks-file "$J" --now "$NOW"
expect_red "alg: HS256 MAC'd with the public key (algorithm confusion)" \
  "header: alg must be EdDSA" -- \
  --token-file "$FIX/alg-hs256.jwt" --jwks-file "$J" --now "$NOW"
expect_red "wrong typ" "header: typ must be JWT" -- \
  --token-file "$FIX/bad-typ.jwt" --jwks-file "$J" --now "$NOW"
expect_red "two segments" "token: malformed" -- \
  --token-file "$FIX/malformed-2seg.jwt" --jwks-file "$J" --now "$NOW"
expect_red "non-base64url segments" "token: malformed" -- \
  --token-file "$FIX/malformed-b64.jwt" --jwks-file "$J" --now "$NOW"
expect_red "empty token file" "token: malformed" -- \
  --token-file "$FIX/empty.jwt" --jwks-file "$J" --now "$NOW"
expect_red "signed token missing the exp claim" "token: malformed" -- \
  --token-file "$FIX/missing-exp.jwt" --jwks-file "$J" --now "$NOW"

# --- the clock is real when --now is absent --------------------------------
expect_ok "freshly minted token against the real clock (no --now)" -- \
  --token-file "$FIX/fresh.jwt" --jwks-file "$J"
expect_red "a 2020 token against the real clock (no --now)" "exp: expired" -- \
  --token-file "$FIX/ancient.jwt" --jwks-file "$J"

# --- differential: pure python vs OpenSSL on 150 raw cases ------------------
diff_out="$(python3 -B - "$VERIFY" "$FIX/differential.jsonl" <<'PYARM'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("verify_token", sys.argv[1])
vt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vt)
agree = disagree = accepted = 0
for line in open(sys.argv[2]):
    line = line.strip()
    if not line:
        continue
    case = json.loads(line)
    mine = vt.ed25519_verify(bytes.fromhex(case["pub"]), bytes.fromhex(case["msg"]),
                             bytes.fromhex(case["sig"]))
    if mine == case["openssl"]:
        agree += 1
    else:
        disagree += 1
    accepted += 1 if case["openssl"] else 0
print("%d agree, %d disagree, %d of them valid signatures"
      % (agree, disagree, accepted))
sys.exit(1 if disagree or accepted == 0 else 0)
PYARM
)"; diff_rc=$?
if [ "$diff_rc" -eq 0 ]; then
  ok "pure python agrees with OpenSSL on 150 raw cases ($diff_out)"
else
  bad "pure python agrees with OpenSSL on 150 raw cases" "$diff_out"
fi

# --- RFC 8032 section 7.1 --------------------------------------------------
rfc_out="$(python3 "$VERIFY" --rfc-file "$RFC" 2>&1)"; rfc_rc=$?
if [ "$rfc_rc" -eq 0 ] && printf '%s' "$rfc_out" | grep -q 'rfc8032: 3/3 vectors verified'; then
  ok "RFC 8032 7.1 vectors 1-3 verify in pure python"
else
  bad "RFC 8032 7.1 vectors 1-3 verify in pure python" "$(printf '%s' "$rfc_out" | tail -n1)"
fi

# --- the module is importable and parseable --------------------------------
if python3 -c "import ast,sys;ast.parse(open(sys.argv[1]).read())" "$VERIFY" 2>/dev/null; then
  ok "verify-token.py parses"
else
  bad "verify-token.py parses" "ast.parse failed"
fi

# --- timing ----------------------------------------------------------------
bench_out="$(python3 "$VERIFY" --token-file "$FIX/good.jwt" --jwks-file "$J" \
             --now "$NOW" --bench 2>&1)"; bench_rc=$?
bench_line="$(printf '%s\n' "$bench_out" | grep '^bench:' || true)"
mean="$(printf '%s' "$bench_line" | sed -n 's/^bench: mean \([0-9.]*\) ms.*/\1/p')"
if [ "$bench_rc" -ne 0 ] || [ -z "$mean" ]; then
  bad "bench prints a mean over 20 runs" "no bench line (rc=$bench_rc)"
else
  printf '  ---  %s   (budget 100 ms; asserted < 250 ms)\n' "$bench_line"
  if python3 -c "import sys;sys.exit(0 if float(sys.argv[1]) < 250.0 else 1)" "$mean"; then
    ok "mean verify time under 250 ms"
  else
    bad "mean verify time under 250 ms" "measured ${mean} ms"
  fi
  if python3 -c "import sys;sys.exit(0 if float(sys.argv[1]) < 100.0 else 1)" "$mean"; then
    ok "mean verify time inside the 100 ms hook budget"
  else
    bad "mean verify time inside the 100 ms hook budget" "measured ${mean} ms"
  fi
fi

echo
echo "test-verify-token: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
