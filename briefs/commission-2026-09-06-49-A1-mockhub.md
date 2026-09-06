# Commission 4.9 · A1 · mock hub — model: sonnet (tier: bounded; done-when is a runnable selftest)

Read briefs/commission-2026-09-06-49-COMMON.md first. Contract: briefs/atlas-contract/IDENTITY-CONTRACT.md
§1 (device flow), §2 (token, refresh, JWKS), §4 (revoked); HUB-CONTRACT.md §2 (push endpoints, refusals).

**Build** `plugins/notrest/skills/atlas/scripts/mockhub.py` — one stdlib `http.server` on 127.0.0.1 that
plays the Atlas hub for fixtures. Endpoints, exact bodies and status codes from the contract:
- `POST /v1/auth/device/start` → 200 `{device_code, user_code, verification_uri, interval:1, expires_in:30}`
- `POST /v1/auth/device/poll {device_code}` → 428 `{error:"authorization_pending"}` until approved; then
  200 `{token, expires_at, jwks, kid}`; `--mode expired` → 410; `--mode denied` → 403; `--mode slow` → 429 once then normal.
  Approval: `--auto-approve-after K` polls, or `POST /_mock/approve {device_code}`.
- `POST /v1/auth/refresh` (bearer) → 200 `{token, expires_at}` for a valid bearer, 401 otherwise.
- `GET /v1/auth/revoked` → `{jti:[…], sub:[…], as_of}`; `POST /_mock/revoke {jti}` adds one.
- `GET /.well-known/atlas-jwks.json` → `{keys:[{kty:"OKP",crv:"Ed25519",kid,x}]}`.
- `POST /v1/snapshot/<p>` (bearer = ingest secret `mock-ingest-<p>` or a valid token with scp push) →
  201 `{stored, project, nodes}`; body over 2 MiB → 413; unparseable → 400; `schema_version` not
  `atlas-hub/1` → 422 `schema_version: expected one of "atlas-hub/0" | "atlas-hub/1", got …`; a part
  with `evidence:"proven"` and no `check` → 422 `nodes[i].parts[j].check: evidence "proven" requires a non-empty check`;
  identical head+body hash as the last stored → 200 `{stored, idempotent:true}`.
- `POST /v1/board/<p>` → 201 `{stored:"board:<p>", project, bytes}`. `GET /v1/snapshot/<p>` → the stored wire.
- **Signing:** mint tokens per §2 (claims iss/aud/sub/seat/mid/prj/scp/jti/iat/exp, exp = now+30d) signed
  Ed25519 with a throwaway key generated at start. Python stdlib cannot sign Ed25519: sign through
  `node -e` using `crypto.sign(null, …)` exactly as briefs/atlas-contract/kit/test-verify-token.sh does
  (read its generator). If `node` is absent, exit 6 with one line `mockhub: node >= 18 required to sign`.
  The `mid` claim = the value passed in `machine.fp` at device/start.
- `--selftest`: starts on a free port, drives every endpoint with urllib, verifies the minted token with
  `briefs/atlas-contract/kit/verify-token.py` (load by path, importlib) against the served JWKS, prints
  `mockhub selftest: N passed, 0 failed`, exit 0.
- `--print-port` writes the bound port to stdout once ready (fixtures wait on it). Never log bearer values.

**TOUCH-ONLY:** `plugins/notrest/skills/atlas/scripts/mockhub.py` (new). Nothing else.
**DONE-WHEN:** `/usr/bin/python3 plugins/notrest/skills/atlas/scripts/mockhub.py --selftest` → exit 0.
Other lanes (A3, A5) integrate against your file as soon as it exists — land within ~30 minutes.
