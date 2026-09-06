# verify-token.py — Atlas token verifier (Ed25519 / RFC 8032, stdlib only). © 2026 Not Rest Inc. Part of Atlas; licensed with the notrest plugin. Authored by the Atlas seat (atlas-ce), 2026-09-06.

The offline half of IDENTITY-CONTRACT.md §2. One file, no dependencies, no
network: the notrest plugin can call it in every hook and decide, locally,
whether the token in `${NOTREST_HOME:-~/.notrest}/atlas-token` admits this
machine. Any failure is the plugin's **exit 7** ("no valid key").

## Vendoring it

Copy the one file. That is the whole install.

```
cp kit/verify-token.py <plugin>/lib/verify_token.py
```

* python3 ≥ 3.8 (tested on 3.11), **standard library only** — `hashlib`,
  `base64`, `binascii`, `json`, `time`, `argparse`. No `cryptography`, no
  `pynacl`, no C extension, no compiler.
* Name the vendored copy `verify_token.py` (underscore) so it is importable;
  the kit keeps the hyphen because it is also run as a CLI.
* It never reads the network, the environment, or any path you do not hand it.
  It never writes anything. It never touches the private key — there is no
  signing code here at all.

Loading it from the hyphenated path, without renaming:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("verify_token", "kit/verify-token.py")
verify_token = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_token)
```

## API

```python
from verify_token import verify, keys_from_jwks, ed25519_verify, TokenError

keys   = keys_from_jwks(json.load(open("atlas-jwks.json")))   # {kid: 32 raw bytes}
claims = verify(token, keys, now=None, expect_mid=machine_fp, revoked=revoked)
```

| | |
|---|---|
| `verify(token, keys, now=None, expect_mid=None, revoked=None) -> dict` | returns the claims on success; raises `TokenError` |
| `token` | the compact JWT as a string (surrounding whitespace is stripped) |
| `keys` | `{kid: bytes}` — raw 32-byte Ed25519 public keys |
| `now` | epoch seconds; `None` = the system clock |
| `expect_mid` | this machine's fingerprint. `None` skips the check; a token whose `scp` contains `"roaming"` skips it too |
| `revoked` | a set/list of revoked `jti`, **or** the hub's `GET /v1/auth/revoked` shape `{"jti": [...], "sub": [...]}` |
| `keys_from_jwks(obj) -> dict` | `{"keys":[{kty:"OKP",crv:"Ed25519",kid,x}]}` → `{kid: raw}`. Entries of another `kty`/`crv` are skipped (a JWKS may legitimately carry them); a malformed Ed25519 entry raises `ValueError`. |
| `ed25519_verify(public_key, message, signature) -> bool` | the raw primitive, if you need it for something other than a JWT. Returns False, never raises. |
| `TokenError.reason` | the one-fact string, also `str(exc)` |

`key_from_pem_or_raw()` is deliberately absent: the hub publishes JWKS, the
plugin pins the raw 32 bytes, and PEM parsing would be a second format to get
wrong.

### The rule set (IDENTITY-CONTRACT.md §2, in this order)

1. three base64url segments, header parses as a JSON object
2. `alg` is exactly `EdDSA`; `typ`, if present, is `JWT`
3. `kid` is a string present in `keys`
4. **signature verifies** over `header.payload` — nothing in the payload is
   read or believed before this line
5. `iss == "https://atlas.not.rest"`, exact
6. `aud == "notrest-plugin"` (a JSON array containing it is also accepted)
7. `now - 60 < exp` — expired otherwise (60 s of clock skew)
8. `iat - 60 <= now` — a token dated in the future is refused
9. `mid == expect_mid`, unless `"roaming"` in `scp` or `expect_mid is None`
10. `jti` not revoked; `sub` not revoked

Required claims and their types — `iss`, `aud`, `sub`, `seat`, `mid`, `prj`
(list of str), `scp` (list of str), `jti`, `iat`, `exp` — are checked after the
signature; anything missing or of the wrong type is `token: malformed`.

## Reason strings

Exactly one fact each. Print them verbatim; do not decorate.

| reason | means |
|---|---|
| `token: malformed` | not three base64url segments, unparseable JSON, or a required claim missing or wrongly typed |
| `header: alg must be EdDSA` | `alg` is `none`, `HS256`, or anything else — every algorithm-confusion attempt lands here |
| `header: typ must be JWT` | a `typ` that is present and is not `JWT` |
| `kid: unknown` | no `kid`, or no such key in the JWKS/pin |
| `signature: invalid` | the signature does not verify under that key — **including a token signed by a foreign key**, a flipped bit, a tampered payload, a non-64-byte signature, `S ≥ L`, or a bad point encoding |
| `iss: mismatch` | issuer is not `https://atlas.not.rest` |
| `aud: mismatch` | audience is not `notrest-plugin` |
| `exp: expired` | `now ≥ exp + 60` |
| `iat: in the future` | `iat > now + 60` |
| `mid: mismatch` | machine fingerprint differs and `scp` has no `roaming` |
| `jti: revoked` | this token id is on the cached revocation list |
| `sub: revoked` | this user is on the cached revocation list (the §4 "removing a user revokes every token of that `sub`" case) |

The CLI prints these as `RED <reason>` and exits **7**. Its own I/O failures use
the same shape: `RED token: unreadable`, `RED jwks: unreadable`,
`RED jwks: not parseable JSON`, `RED revoked: unreadable`, and `RED jwks: …`
from `keys_from_jwks`.

## CLI

```
python3 verify-token.py --token-file PATH --jwks-file PATH \
                        [--now N] [--mid M] [--revoked-file PATH] [--bench]
python3 verify-token.py --rfc-file kit/fixtures/tokens/rfc8032-7.1.json
```

* success → the claims as pretty JSON on stdout, **exit 0**
* failure → `RED <reason>`, **exit 7**
* `--bench` prints `bench: mean X ms over 20 runs (min …, max …)` before the claims
* `--rfc-file` verifies the RFC 8032 §7.1 vectors with the pure-python
  primitive and exits 0 / 7 — a two-second proof that a vendored copy is intact

## The signature check: cofactorless, and why

RFC 8032 §5.1.7 defines the check as the cofactored group equation
`[8][S]B = [8]R + [8][k]A`, then says it is "sufficient, but not required, to
instead check `[S]B = R + [k]A`". **This implementation takes the cofactorless
form** (computed as `[S]B + [k](−A) == R`, one Straus–Shamir double-scalar
multiplication, compared projectively so no modular inversion is needed):

1. **It is strictly stronger.** Every signature it accepts, the cofactored
   equation accepts too; it additionally rejects signatures that differ from a
   valid one by a point of small order. An Atlas token therefore has one
   accepted signature encoding, not eight — a token cannot be mutated into a
   second byte-string that still verifies.
2. **It agrees with the signer.** OpenSSL (hence node's `crypto.verify`, hence
   the hub's worker), ref10 and libsodium all check cofactorless. The plugin and
   the hub accept exactly the same set of signatures, so no token can be good on
   one side and bad on the other.
3. It costs nothing — there is no cofactor multiplication to skip.

The RFC's mandatory canonicity rules are applied as well: `S` is rejected unless
`0 ≤ S < L`, and a non-canonical point encoding (`y ≥ p`) is refused.

Arithmetic is over GF(2²⁵⁵−19) with points in extended coordinates
(X : Y : Z : T), using the add/double formulas from RFC 8032 Appendix A. The
double-scalar multiplication uses 4-bit windows over both scalars (Straus–Shamir),
with the base point's window table built once at import. The curve constants
(d, √−1, B) are written out as literals rather than derived, and a cheap
on-curve self-check at import fails loudly if any literal is off by a bit.

## Measured timing (this box: Linux x86-64, CPython 3.11.2)

| | |
|---|---|
| **one `verify()`, warm** | **1.7 – 2.5 ms** (`--bench`: mean 1.78 ms over 20 runs) |
| module import | ≈ 8 ms, nearly all of it `hashlib` + `json` + `base64` |
| whole CLI process (interpreter start + import + one verify) | 33 – 43 ms; a bare `python3 -c pass` is 12.7 ms of that |

Against the ~100 ms hook budget in the contract there is roughly 50× headroom
in-process, and the whole-process path is inside the contract's stricter
"under 50 ms" line. The test asserts `< 250 ms` so a loaded CI box cannot make
it flaky, and prints the number it measured.

## Tests and fixtures

```
bash kit/test-verify-token.sh        # 38 arms; exit 0 = all passed
```

**node signs, python verifies.** `kit/test-verify-token.sh` generates every
fixture with node ≥ 18's `crypto` (OpenSSL Ed25519) into `kit/fixtures/tokens/`,
then drives them through the python CLI, asserting the exit code and the exact
reason string. Two independent implementations must agree, so a bug in either
shows up as a failed arm. Keys are generated fresh on each run; only public
halves are written; **no secret is ever stored**.

Covered: a good token · matching `mid` · `roaming` scope over a foreign `mid` ·
an `exp` inside the skew · `aud` as an array · kid rotation in a two-key JWKS
(with an RSA entry that must be skipped) · a header without `typ` · a
revocation list naming other ids · a flipped signature bit · a payload tampered
after signing · **a token signed with a different key (the contract's born-red
case → exit 7)** · a good token against the wrong JWKS · a 63-byte signature ·
expired · wrong `aud` · wrong `iss` · unknown `kid` · wrong `mid` · `iat` in the
future · revoked `jti` (both list shapes) · revoked `sub` · `alg: none` ·
`alg: HS256` MAC'd with the public key (algorithm confusion) · a wrong `typ` ·
two segments · non-base64url segments · an empty file · a signed token missing
`exp` · the real clock in both directions · a 150-case differential corpus where
python must match OpenSSL's verdict case for case · the RFC 8032 §7.1 vectors ·
`ast.parse` · the bench.

`kit/fixtures/tokens/rfc8032-7.1.json` is **static, not generated**: test
vectors 1–3 from RFC 8032 §7.1 (public key, message, signature, plus the RFC's
seed so they can be re-derived). The test script never overwrites it. Its
"secret keys" are published RFC test values, not credentials.
