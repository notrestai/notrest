# Commission 4.9 · A3 · auth client — model: opus (tier: judgment; a login flow that must fail honestly)

Read COMMON first. Contract: IDENTITY-CONTRACT.md §1 (device flow, exact statuses), §2 (refresh, JWKS), §4 (revoked).

**Build** `plugins/notrest/skills/atlas/scripts/atlas_auth.py` per the fixed interface, urllib stdlib only:
- `device_login(home, base, out)`: POST start with `{client:"notrest-plugin", version:<plugin.json version>,
  machine:{name:<hostname as a SUGGESTION only>, fp:<atlas_token.fingerprint(home)>}}`; print to `out` exactly
  two lines: `Open <verification_uri> and enter the code: <user_code>` and `Waiting (expires in <n> s)…`; poll
  every `interval` s honoring 428 (wait), 429 (interval += 5), 200 (store), 410 → `AuthError("login: code expired — run login again")`,
  403 → `AuthError("login: denied in the portal")`, network error → `AuthError("hub unreachable at <base>")`.
  On 200: write token to `HOME/atlas-token` 0600 (dir 0700), fetch JWKS → `HOME/atlas-jwks.json`, fetch revoked,
  then return `atlas_token.verdict(home)` claims (raise if the stored token does not verify — say so in one fact).
- `refresh(home, base, timeout)`: only when a valid token has `exp - now < 7 days`; POST /v1/auth/refresh bearer;
  store on 200; False otherwise; never raises. `fetch_jwks` / `fetch_revoked`: bounded, atomic writes (tmp+rename), False on failure.
- CLI: `atlas_auth.py login [--base B] [--home H]` (exit 0/7, prints the two lines then `atlas-token: ok …`),
  `refresh`, `jwks`, `revoked` (exit 0/1 silent), `sessionstart [--budget-ms 2000]` = refresh+revoked+jwks inside
  one wall-clock budget, always exit 0, nothing on stdout (the hook's entry point).
- A3 depends on A2's `atlas_token` (import by sibling path); if it is not there yet, stub the two functions you
  need in your fixture and note it in OPEN.

**Fixture** `fixture-auth.sh` (new) against `mockhub.py` (A1; wait for `--print-port`; if mockhub.py is absent when
you reach integration, start a minimal in-process stub in the fixture and say so in OPEN): arms — login happy path
(auto-approve) → token file 0600, verdict ok; 410 → exit 7 with the exact fact; 403 → exit 7; 429 slows; hub down →
exit 7 `hub unreachable`; refresh when exp-now < 7 d rotates the token, when > 7 d does nothing; `sessionstart`
with the hub down exits 0 within the budget (time it); revoked fetch then verdict → 7 `jti: revoked`; no token value
in any output (grep the whole fixture log for the minted token's middle 20 chars).

**TOUCH-ONLY:** `atlas_auth.py`, `fixture-auth.sh` (both new). **DONE-WHEN:** `bash plugins/notrest/skills/atlas/scripts/fixture-auth.sh` → exit 0.
