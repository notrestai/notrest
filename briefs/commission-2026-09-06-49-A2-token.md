# Commission 4.9 · A2 · token module — model: opus (tier: judgment; verifier integration + fingerprint)

Read COMMON first. Contract: IDENTITY-CONTRACT.md §2 (token + verification rule), §4 (revocation);
RULINGS-2026-09-06.md §1 (fingerprint); kit/README-verify-token.md (API).

**Build** `plugins/notrest/skills/atlas/scripts/atlas_token.py` + `vendor/__init__.py` + `vendor/verify_token.py`
(byte-exact copy of briefs/atlas-contract/kit/verify-token.py; prove with shasum). Implement the fixed
interface: `read_token`, `machine_id`, `fingerprint`, `load_keys`, `load_revoked`, `verdict`, plus a CLI:
`atlas_token.py check [--quiet] [--home H] [--now N]` (exit 0/7; prints `atlas-token: ok sub=<sub> seat=<seat> exp=<iso>`
or `RED <reason>`), `fingerprint`, `claims`. `verdict` order: read token (atlas-token, else access-key if it is a JWT)
→ keys (pinned ∪ cache; none → `keys: none pinned or cached`) → `vendor.verify_token.verify(token, keys, now, expect_mid=fingerprint(home), revoked=load_revoked(home))`.
Machine id per the RULING; the macOS branch must work on this Mac; the container branch persists 0600 once.
Import cost matters: the hooks call this ~100 ms budget — measure `python3 -c "import atlas_token"` and one
`verdict` and report both in ms.

**Fixture** `plugins/notrest/skills/atlas/scripts/fixture-token.sh` (new), red-first, node-signed like Atlas's
suite (copy the generator pattern from kit/test-verify-token.sh; throwaway keys; never store a private key):
arms — good token → 0; absent → 7 `token: absent`; expired → 7; foreign key → 7 `signature: invalid`; wrong mid → 7
`mid: mismatch`; roaming scope over wrong mid → 0; revoked jti via cache → 7; legacy access-key holding a JWT → 0;
access-key holding `nrk_…` → `verdict` returns (False, "token: absent", None) (the ring path is the seat's, not yours);
fingerprint stable across two calls and never equal to sha256(hostname); no token value in any output (grep arm).

**TOUCH-ONLY:** the three files above + the fixture. **DONE-WHEN:** `bash plugins/notrest/skills/atlas/scripts/fixture-token.sh` → exit 0, last line `fixture-token: N passed, 0 failed`.
