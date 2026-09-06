# verify-token.py — Atlas token verifier (Ed25519 / RFC 8032, stdlib only). © 2026 Not Rest Inc. Part of Atlas; licensed with the notrest plugin. Authored by the Atlas seat (atlas-ce), 2026-09-06.
"""Atlas token verifier — one file, python3 >= 3.8, standard library only.

Verifies the Atlas token defined by IDENTITY-CONTRACT.md section 2: a compact JWT,
alg EdDSA (Ed25519), header {alg, typ, kid}, claims
iss/aud/sub/seat/mid/prj/scp/jti/iat/exp.

Everything below is stdlib: hashlib (SHA-512), base64, json, argparse, time.
The Ed25519 verify is implemented here in pure python per RFC 8032 section 5.1.7.

    from verify_token import verify, keys_from_jwks, TokenError
    claims = verify(token, keys_from_jwks(jwks), expect_mid=machine_fp)

Failures raise TokenError(reason) where reason is exactly one fact:

    token: malformed              header: alg must be EdDSA
    header: typ must be JWT       kid: unknown
    signature: invalid            iss: mismatch
    aud: mismatch                 exp: expired
    iat: in the future            mid: mismatch
    jti: revoked                  sub: revoked

CLI (the plugin's convention: exit 7 = no valid key):

    python3 verify-token.py --token-file T --jwks-file J [--now N] [--mid M]
                            [--revoked-file R] [--bench]
    python3 verify-token.py --rfc-file kit/fixtures/tokens/rfc8032-7.1.json
"""

import base64
import binascii
import hashlib
import json
import sys
import time

__all__ = ["TokenError", "verify", "keys_from_jwks", "ed25519_verify",
           "ISS", "AUD", "SKEW"]

# ---------------------------------------------------------------------------
# contract constants (IDENTITY-CONTRACT.md section 2)
# ---------------------------------------------------------------------------

ISS = "https://atlas.not.rest"
AUD = "notrest-plugin"
SKEW = 60          # seconds of clock skew allowed on exp and iat
ALG = "EdDSA"
EXIT_NO_VALID_KEY = 7

# ---------------------------------------------------------------------------
# Ed25519 — RFC 8032, pure python
#
# Curve: edwards25519, a = -1, over GF(2^255 - 19).
# Points are held in extended coordinates (X : Y : Z : T) with x = X/Z, y = Y/Z
# and T = XY/Z ("Twisted Edwards Curves Revisited", Hisil-Wong-Carter-Dawson);
# the add/double formulas are the ones in RFC 8032 Appendix A.
#
# CHECK VARIANT: cofactorless.  We accept a signature iff
#
#       [S]B - [k]A == R          (as curve points, k = SHA-512(R||A||M) mod L)
#
# RFC 8032 section 5.1.7 defines the check as the cofactored group equation
# [8][S]B = [8]R + [8][k]A and then says it is "sufficient, but not required,
# to instead check [S]B = R + [k]A".  We take the permitted cofactorless form
# for three reasons:
#   1. it is strictly stronger — every signature it accepts the cofactored
#      equation also accepts, and it additionally rejects signatures that
#      differ from a valid one by a point in the order-8 torsion subgroup, so
#      a token's signature is not malleable into a second accepted encoding;
#   2. it is what OpenSSL (hence node's crypto.verify, hence the Atlas hub's
#      signer-side self-test), ref10 and libsodium do — the plugin and the hub
#      therefore agree on the *same* accepted set, with no signature that one
#      side takes and the other refuses;
#   3. it costs nothing: no cofactor multiplication.
# We also apply the RFC's mandatory canonicity rules: S is rejected unless
# 0 <= S < L, and a non-canonical point encoding (y >= p) is rejected.
# ---------------------------------------------------------------------------

_P = (1 << 255) - 19
_L = (1 << 252) + 27742317777372353535851937790883648493
# d = -121665/121666 mod p, sqrt(-1) = 2^((p-1)/4) mod p, and the base point B
# (y = 4/5, x even) — the edwards25519 constants of RFC 8032 section 5.1, written
# out rather than derived so that importing this module costs no modular
# exponentiation (that derivation measured ~6.4 ms, most of the import).  The
# cheap self-check below re-earns them: it fails if any literal is off by a bit.
_D = 37095705934669439343138083508754565189542113879843219016388785533085940283555
_SQRT_M1 = 19681161376707505956807079304988542015446066515923890162744021073123829784752
_BX = 15112221349535400772501151409588531511454012693041857206046113283949847762202
_BY = 46316835694926478169428394003475163141307993866256225615783033603165251855960
_IDENT = (0, 1, 1, 0)

if (_SQRT_M1 * _SQRT_M1 + 1) % _P != 0:
    raise RuntimeError("verify-token: sqrt(-1) constant is corrupt")
if (-_BX * _BX + _BY * _BY - 1 - _D * _BX * _BX * _BY * _BY) % _P != 0:
    raise RuntimeError("verify-token: base point or d constant is corrupt")
if _BY * 5 % _P != 4 or _BX & 1:
    raise RuntimeError("verify-token: base point is not the RFC 8032 one")


def _point_add(P, Q):
    """Unified add in extended coordinates (RFC 8032 Appendix A)."""
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _P
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _P
    C = 2 * P[3] * Q[3] * _D % _P
    D = 2 * P[2] * Q[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _point_double(P):
    """Doubling in extended coordinates (RFC 8032 Appendix A)."""
    A = P[0] * P[0] % _P
    B = P[1] * P[1] % _P
    Ch = 2 * P[2] * P[2] % _P
    H = A + B
    E = H - (P[0] + P[1]) * (P[0] + P[1]) % _P
    G = A - B
    F = Ch + G
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _point_eq(P, Q):
    """Projective equality: X1*Z2 == X2*Z1 and Y1*Z2 == Y2*Z1 (no inversion)."""
    if (P[0] * Q[2] - Q[0] * P[2]) % _P != 0:
        return False
    return (P[1] * Q[2] - Q[1] * P[2]) % _P == 0


def _point_negate(P):
    return ((_P - P[0]) % _P, P[1], P[2], (_P - P[3]) % _P)


def _recover_x(y, sign):
    """x from y and the sign bit; None if no such point exists."""
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _decompress(data):
    """32-byte little-endian point encoding -> extended point, or None.

    A non-canonical encoding (the y coordinate not reduced mod p) is refused;
    real signers never emit one."""
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _P:
        return None
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _window_table(P):
    """[0]P .. [15]P for a 4-bit window."""
    t = [_IDENT, P]
    for i in range(2, 16):
        t.append(_point_add(t[i - 1], P))
    return t


# The base point B is fixed, so its window table is built once, at import.
_B = (_BX, _BY, 1, _BX * _BY % _P)
_B_TABLE = _window_table(_B)


def _double_scalar_mult(s, tab_s, k, tab_k):
    """s*P + k*Q from precomputed 4-bit window tables (Straus-Shamir)."""
    R = _IDENT
    started = False
    for i in range(63, -1, -1):
        if started:
            R = _point_double(R)
            R = _point_double(R)
            R = _point_double(R)
            R = _point_double(R)
        shift = 4 * i
        a = (s >> shift) & 15
        b = (k >> shift) & 15
        if a:
            R = _point_add(R, tab_s[a])
            started = True
        if b:
            R = _point_add(R, tab_k[b])
            started = True
    return R


# decompressed-public-key cache: hooks verify with the same one or two keys.
_A_CACHE = {}
_A_CACHE_MAX = 32


def _public_point(public_key):
    hit = _A_CACHE.get(public_key)
    if hit is not None:
        return hit[0]
    A = _decompress(public_key)
    if A is None:
        return None
    if len(_A_CACHE) >= _A_CACHE_MAX:
        _A_CACHE.clear()
    _A_CACHE[public_key] = (A, _window_table(_point_negate(A)))
    return A


def _neg_table(public_key):
    return _A_CACHE[public_key][1]


def ed25519_verify(public_key, message, signature):
    """RFC 8032 Ed25519 (PureEdDSA) verify. True/False, never raises."""
    if not isinstance(public_key, (bytes, bytearray)):
        return False
    if not isinstance(signature, (bytes, bytearray)):
        return False
    public_key = bytes(public_key)
    signature = bytes(signature)
    if len(public_key) != 32 or len(signature) != 64:
        return False
    r_enc = signature[:32]
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:                      # RFC 8032: S must be canonical
        return False
    A = _public_point(public_key)
    if A is None:
        return False
    R = _decompress(r_enc)
    if R is None:
        return False
    k = int.from_bytes(
        hashlib.sha512(r_enc + public_key + bytes(message)).digest(), "little") % _L
    # cofactorless: [S]B + [k](-A) == R
    P = _double_scalar_mult(s, _B_TABLE, k, _neg_table(public_key))
    return _point_eq(P, R)


# ---------------------------------------------------------------------------
# token layer
# ---------------------------------------------------------------------------


class TokenError(Exception):
    """Verification failed. `reason` is exactly one fact."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


_B64URL_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


def _b64u_decode(segment, err="token: malformed"):
    if not segment or not _B64URL_CHARS.issuperset(segment):
        raise TokenError(err)
    if len(segment) % 4 == 1:
        raise TokenError(err)
    try:
        return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (binascii.Error, ValueError):
        raise TokenError(err)


def _json_object(raw, err="token: malformed"):
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise TokenError(err)
    if not isinstance(obj, dict):
        raise TokenError(err)
    return obj


def _str_claim(claims, name):
    v = claims.get(name)
    if not isinstance(v, str) or not v:
        raise TokenError("token: malformed")
    return v


def _int_claim(claims, name):
    v = claims.get(name)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TokenError("token: malformed")
    return int(v)


def _str_list_claim(claims, name):
    v = claims.get(name)
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise TokenError("token: malformed")
    return v


def _revoked_sets(revoked):
    """Accept a set/list of jti, or the hub's {jti:[...], sub:[...]} shape."""
    if revoked is None:
        return frozenset(), frozenset()
    if isinstance(revoked, dict):
        return (frozenset(revoked.get("jti") or ()),
                frozenset(revoked.get("sub") or ()))
    return frozenset(revoked), frozenset()


def verify(token, keys, now=None, expect_mid=None, revoked=None):
    """Verify an Atlas token. Returns the claims dict; raises TokenError.

    keys        {kid: 32-byte raw Ed25519 public key}
    now         epoch seconds (default: time.time())
    expect_mid  this machine's fingerprint; skipped when None or when the
                token's scp contains "roaming"
    revoked     set of revoked jti, or {"jti": [...], "sub": [...]}

    Order: structure -> alg -> kid -> signature -> iss -> aud -> exp -> iat
    -> mid -> jti.  No claim is trusted before the signature is checked.
    """
    if not isinstance(token, str):
        raise TokenError("token: malformed")
    token = token.strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("token: malformed")
    header_seg, payload_seg, sig_seg = parts

    header = _json_object(_b64u_decode(header_seg))
    if header.get("alg") != ALG:
        # covers "none", "HS256" and every other algorithm-confusion attempt
        raise TokenError("header: alg must be EdDSA")
    typ = header.get("typ")
    if typ is not None and typ != "JWT":
        raise TokenError("header: typ must be JWT")

    kid = header.get("kid")
    if not isinstance(kid, str) or kid not in (keys or {}):
        raise TokenError("kid: unknown")
    public_key = keys[kid]
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
        raise TokenError("kid: unknown")

    signature = _b64u_decode(sig_seg)
    if len(signature) != 64:
        raise TokenError("signature: invalid")
    signing_input = (header_seg + "." + payload_seg).encode("ascii")
    if not ed25519_verify(bytes(public_key), signing_input, signature):
        raise TokenError("signature: invalid")

    # --- signature is good; only now may the payload be believed ------------
    claims = _json_object(_b64u_decode(payload_seg))
    iss = _str_claim(claims, "iss")
    sub = _str_claim(claims, "sub")
    _str_claim(claims, "seat")
    mid = _str_claim(claims, "mid")
    jti = _str_claim(claims, "jti")
    _str_list_claim(claims, "prj")
    scp = _str_list_claim(claims, "scp")
    iat = _int_claim(claims, "iat")
    exp = _int_claim(claims, "exp")
    aud = claims.get("aud")
    if not isinstance(aud, str) and not (
            isinstance(aud, list) and all(isinstance(x, str) for x in aud)):
        raise TokenError("token: malformed")

    if iss != ISS:
        raise TokenError("iss: mismatch")
    if AUD != aud and not (isinstance(aud, list) and AUD in aud):
        raise TokenError("aud: mismatch")

    if now is None:
        now = time.time()
    now = int(now)
    if now - SKEW >= exp:
        raise TokenError("exp: expired")
    if iat - SKEW > now:
        raise TokenError("iat: in the future")

    if expect_mid is not None and "roaming" not in scp and mid != expect_mid:
        raise TokenError("mid: mismatch")

    jti_revoked, sub_revoked = _revoked_sets(revoked)
    if jti in jti_revoked:
        raise TokenError("jti: revoked")
    if sub in sub_revoked:
        raise TokenError("sub: revoked")

    return claims


def keys_from_jwks(json_obj):
    """JWKS -> {kid: 32-byte raw public key}. OKP/Ed25519 keys only.

    Keys of another kty/crv are skipped (a JWKS may legitimately hold them);
    an OKP/Ed25519 entry with a bad kid or x raises ValueError."""
    if isinstance(json_obj, dict):
        entries = json_obj.get("keys")
    else:
        entries = json_obj
    if not isinstance(entries, list):
        raise ValueError("jwks: no keys array")
    keys = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("jwks: key is not an object")
        if entry.get("kty") != "OKP" or entry.get("crv") != "Ed25519":
            continue
        kid = entry.get("kid")
        if not isinstance(kid, str) or not kid:
            raise ValueError("jwks: key has no kid")
        x = entry.get("x")
        if not isinstance(x, str) or not _B64URL_CHARS.issuperset(x):
            raise ValueError("jwks: key %s has a bad x" % kid)
        try:
            raw = base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))
        except (binascii.Error, ValueError):
            raise ValueError("jwks: key %s has a bad x" % kid)
        if len(raw) != 32:
            raise ValueError("jwks: key %s is not 32 bytes" % kid)
        keys[kid] = raw
    if not keys:
        raise ValueError("jwks: no Ed25519 keys")
    return keys


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _load_revoked(path):
    raw = _read_text(path).strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except ValueError:
        return set(line.strip() for line in raw.splitlines() if line.strip())
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        return set(obj)
    raise ValueError("revoked: unreadable")


def _rfc_vectors(path):
    """Verify the RFC 8032 section 7.1 vectors with the pure-python verify."""
    data = json.loads(_read_text(path))
    vectors = data["vectors"] if isinstance(data, dict) else data
    failed = 0
    for vec in vectors:
        pub = bytes.fromhex(vec["public_key"])
        msg = bytes.fromhex(vec["message"])
        sig = bytes.fromhex(vec["signature"])
        good = ed25519_verify(pub, msg, sig)
        # a one-bit change to the message must not verify
        tampered = bytearray(msg) or bytearray(b"\x00")
        tampered[0] ^= 0x01
        bad = ed25519_verify(pub, bytes(tampered), sig)
        ok = good and not bad
        print("%s %s" % ("ok  " if ok else "FAIL", vec.get("name", "?")))
        if not ok:
            failed += 1
    print("rfc8032: %d/%d vectors verified" % (len(vectors) - failed, len(vectors)))
    return 0 if failed == 0 else EXIT_NO_VALID_KEY


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(
        prog="verify-token.py",
        description="Verify an Atlas token (Ed25519 compact JWT), offline.")
    ap.add_argument("--token-file", help="file holding the compact JWT")
    ap.add_argument("--jwks-file", help="file holding the JWKS JSON")
    ap.add_argument("--now", type=int, default=None,
                    help="epoch seconds to verify at (default: the clock)")
    ap.add_argument("--mid", default=None,
                    help="this machine's fingerprint")
    ap.add_argument("--revoked-file", default=None,
                    help="JSON list of revoked jti, or {jti:[],sub:[]}")
    ap.add_argument("--bench", action="store_true",
                    help="also print the mean verify time over 20 runs")
    ap.add_argument("--rfc-file", default=None,
                    help="verify the RFC 8032 7.1 vectors in this file and exit")
    args = ap.parse_args(argv)

    if args.rfc_file:
        return _rfc_vectors(args.rfc_file)

    if not args.token_file or not args.jwks_file:
        print("RED token: --token-file and --jwks-file are required")
        return EXIT_NO_VALID_KEY

    try:
        token = _read_text(args.token_file).strip()
    except OSError:
        print("RED token: unreadable")
        return EXIT_NO_VALID_KEY
    try:
        jwks_obj = json.loads(_read_text(args.jwks_file))
    except OSError:
        print("RED jwks: unreadable")
        return EXIT_NO_VALID_KEY
    except ValueError:
        print("RED jwks: not parseable JSON")
        return EXIT_NO_VALID_KEY
    try:
        keys = keys_from_jwks(jwks_obj)
    except ValueError as exc:
        print("RED %s" % exc)
        return EXIT_NO_VALID_KEY
    revoked = None
    if args.revoked_file:
        try:
            revoked = _load_revoked(args.revoked_file)
        except (OSError, ValueError):
            print("RED revoked: unreadable")
            return EXIT_NO_VALID_KEY

    try:
        claims = verify(token, keys, now=args.now, expect_mid=args.mid,
                        revoked=revoked)
    except TokenError as exc:
        print("RED %s" % exc.reason)
        return EXIT_NO_VALID_KEY

    if args.bench:
        runs = 20
        samples = []
        for _ in range(runs):
            t0 = time.perf_counter()
            verify(token, keys, now=args.now, expect_mid=args.mid,
                   revoked=revoked)
            samples.append((time.perf_counter() - t0) * 1000.0)
        print("bench: mean %.2f ms over %d runs (min %.2f, max %.2f)"
              % (sum(samples) / runs, runs, min(samples), max(samples)))

    print(json.dumps(claims, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
