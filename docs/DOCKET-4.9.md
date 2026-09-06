# DOCKET 4.9 — the portal owns identity; the hub owns the plugin's git

**STATUS: DRAFT v4 — all four questions to Atlas ruled; awaiting the owner's approval. No lane is dispatched until the owner says go.**
*Drafted 2026-09-06 by the Director seat. Contract files, received verbatim and banked with provenance under `briefs/atlas-contract/`:
`IDENTITY-CONTRACT.md` (192b6f5), `HUB-CONTRACT.md` (14fb684), `SCHEMA-v1.md`. All vendorable files received and
hash-verified (`briefs/atlas-contract/README.md`): `kit/to-wire.py`, `mcp/server.mjs`, `kit/verify-token.py` +
suite + RFC fixture + README. The verifier's suite passes on this Mac: 38/38.
Our ask: `briefs/ask-2026-09-06-atlas-identity-contract.md`.*

## The change in one paragraph

4.8.1 admits a machine by a key the owner mints and carries by hand, hashed against a ring
committed to the repo. 4.9 admits a machine by an Atlas token the portal issues to a paying seat:
ONE Ed25519-signed JWT (alg EdDSA, kid; claims iss/aud/sub/seat/mid/prj/scp/jti/iat/exp, 30 d)
that also authenticates the bank's push and the clone / self-update of the plugin from the hub's
git mirror. The plugin verifies OFFLINE with the RFC 8032 verifier Atlas supplies; refresh when
exp−now < 7 d; the revoked list is cached at SessionStart; offline holders die at exp. The token
lives at `${NOTREST_HOME:-~/.notrest}/atlas-token` (access-key accepted as an alias in transition).
A consumer starts from the Atlas MCP server (OAuth 2.1, `atlas_connect` returns token + OUR
bootstrap text); a headless box logs in with the device flow.

## Decisions for the owner at approval

- **D1 — verification = signed token (Atlas ruling).** Atlas supplies the verifier + fixture; we
  vendor it. Recommend ACCEPT. (The cached-verdict alternative is dropped.)
- **D2 — ship gate, in two halves.** The PUSH half is provable live today (ingest secret): its
  live arm is a ship condition now. The TOKEN half (login, verify, refresh, revoke, git helper)
  is gated green against the mock and ships labeled "hub I-A pending" until its live arm passes;
  the ring keeps admitting the fleet meanwhile. Recommend ACCEPT.
- **D3 — hub phases.** Atlas has asked the owner for its own go on I-A → I-B → I-C. Our Phase A
  needs only the contract text; our live arm needs I-A.

## Interfaces the seat fixes BEFORE dispatch (so lanes never wait on each other)

- `atlas_token.py`: `verify(token_str, keys) -> Claims | raise TokenError(reason)`;
  `load_keys()` (pinned + JWKS cache); `read_token(home) -> str|None` (atlas-token, alias
  access-key); `verdict_cache(home)` read/write `{jti, exp, mid, checked_at}`.
- `atlas_auth.py`: `device_login(base_url, home) -> Claims`; `refresh(home)`; `fetch_revoked(home)`.
- `mockhub.py`: one stdlib http.server implementing device/start, activate, poll (428/200/410/403/429),
  refresh, revoked, jwks, snapshot push — from the contract, with a test signing key.
- Hook contract: every hook calls `atlas.py key --check --quiet` exactly as today; the verdict
  comes from the cache + offline verify; exit codes unchanged (0 / 7).
- Push: `push_http(snapshot, board, credential)` keeps its signature; bearer = the token;
  idempotent by head + body hash; hub_commit = the head we sent; error texts verbatim from the contract.

## Waves and lanes (tiered swarm: seat → opus lanes → sonnet workers as tools, depth ≤ 3)

### Wave A — all in parallel on the go (~2.5 h wall)

| Lane | Model · tier | TOUCH-ONLY | Done-when (runnable) | Tokens |
|---|---|---|---|---|
| A1 mockhub | sonnet · bounded | `skills/atlas/scripts/mockhub.py` (new) | serves every endpoint in the contract; `python3 mockhub.py --selftest` exit 0 | 1–2M |
| A2 token module | opus · judgment | `skills/atlas/scripts/atlas_token.py` (new) + vendored verifier | verify/claims/JWKS/cache per the interface; unit fixture: good, expired, wrong kid, bad sig, wrong aud/mid, revoked | 8–12M |
| A3 auth client | opus · judgment | `skills/atlas/scripts/atlas_auth.py` (new) | device flow incl. 428/410/403/429 paths, refresh at <7 d, revoked cache; passes against A1 | 8–12M |
| A4 git + helper | sonnet · bounded | `atlas.py credential-helper` subcommand, `login` writes the host-scoped helper config line from §9 | `git credential fill` returns username atlas / password = token for the hub host and nothing for others; no token in any URL or config (grep arm) | 1–2M |
| A5 push adapter | opus · judgment | `push_http` + a snapshot→wire converter in `atlas.py` | wire atlas-hub/1 per SCHEMA-v1 with the HUB-CONTRACT §4 status/evidence table; bearer from the credential file by path; 201 → hub_commit = head; errors verbatim; **LIVE arm today** against atlas.not.rest with an ingest secret the Atlas seat mints for this estate (the push half does not wait on hub I-A) | 8–12M |
| A9 MCP read server | opus · judgment | vendor Atlas `mcp/server.mjs` under `skills/atlas/mcp/`, plugin MCP registration, `doctor` node-presence check | server starts on this Mac with the token file; `atlas_relevant_context` answers for this estate; doctor names a missing `node` as one line, never a failure of the harness | 4–6M |
| A6 hooks | opus · judgment (kernel) | `hooks/session-start.sh`, `hooks/estate-root.sh`, `hooks/atlas-bank-hook.sh`, hook fixture | SessionStart: refresh + revoked fetch bounded ≤2 s, silent on failure; banner names the login; hook fixture arms green; `eval check` 0 | 8–12M |
| A7 connect text | opus · judgment | `docs/ATLAS-CONNECT.md` (new) — the bootstrap the hub serves verbatim | helper-before-marketplace order; every command runnable; NAS/headless variant; sent to Atlas | 4–6M |
| A8 manifest + stamps | sonnet · bounded | `.claude-plugin/*.json`, `plugins/notrest/.claude-plugin/plugin.json`, flow-html stamps | versions match; both tombstones pinned 9.0.0 / 4.7.1 (asserted); `doctor check` ≤ 5 | 0.5–1M |

### Wave B — after the seat integrates A2/A3/A4/A5 into `atlas.py` (~30 min seat) (~1.5 h wall)

| Lane | Model · tier | TOUCH-ONLY | Done-when | Tokens |
|---|---|---|---|---|
| B1 tester | opus · judgment | `skills/atlas/scripts/fixture.sh`, `evals/**` — never product code | red-first arms: expired, revoked, wrong machine, offline-with-cache, offline-without, helper protocol, token-in-URL refused, push replay, keyless deny rules still deny; LIVE arm skips with "I-A pending" | 6–9M |
| B2 eval law + doctor | opus · judgment | `skills/eval/scripts/eval.py`, `skills/doctor/scripts/doctor.py` | **AMEND NETWORK-EGRESS**: 4.9 deliberately changes the no-egress promise — the ONE permitted destination is `ATLAS_HUB_BASE` (default atlas.not.rest), only from the named atlas modules (`atlas_auth.py`, `atlas_wire.py`, and `atlas.py`'s push), never from a hook synchronously (SessionStart backgrounds it); loopback-bound servers (`mockhub.py`) allowlisted by their bind; the check names the rationale. New checks: token file mode 0600, helper host-scoped, verifier fixture present, no token literal anywhere; `eval check` 0 with the arms red-first | 6–9M |
| B3 SKILL + workshop | opus · judgment | `skills/atlas/SKILL.md`, `WORKSHOP-SLIDES*.md` delta | every command in SKILL.md runs; exit-code table updated; **SKILL.md names every shipped script** (`atlas_token.py`, `atlas_auth.py`, `atlas_helper.py`, `atlas_wire.py`, `mockhub.py`, `vendor/verify_token.py`, the mcp wrapper) so SCRIPT-OWNS-SCANNING is green | 4–6M |
| B4 docs mechanical | sonnet · bounded | `README.md` table, `CHANGELOG.md`, `NOTREST-ON-THE-NAS.md` v2 | `starthere_lint`-style dead-reference check exit 0 on each | 1–2M |

### Wave C — refute and ship (~1.5 h wall)

| Lane | Model · tier | Scope | Done-when | Tokens |
|---|---|---|---|---|
| C1 refuter | opus · judgment | read-only on the tree (LAW: kernel surfaces) | verdict; two rounds budgeted — the last two rounds here came back NOT CLEAN first | 10–16M |
| fixes | resume A2/A3/A5/A6 | same lanes, never respawned | refuter clean | 4–8M |
| ship | seat | stamps, gates, CHANGELOG, tag | `doctor` ≤ 5 · `eval` 0 · `gate-check` 0 red · atlas fixture 0 failed · D2 satisfied or labeled | — |

## Totals

- **Lanes:** 13 + fixes (10 opus, 3 sonnet). **Tokens:** 75–115M lane tokens (parallelism buys
  wall-clock, not tokens: each lane carries its own context). Seat cost on top, about one refuter
  round. For scale: 4.7 receipted ~100M+ and hit the limit once; 4.8.0 ~25M in one morning.
- **Wall-clock:** ~5.5 h of lane time in three waves; realistically ONE long window or TWO
  (Wave A in the first, B+C in the second). The ship itself waits on D2.

## Rulings from Atlas (2026-09-06, banked at briefs/atlas-contract/RULINGS-2026-09-06.md)

- **Fingerprint = ours to fix.** Interface for A2/A3: `machine_id()` → Linux `/etc/machine-id`
  (fallback `/var/lib/dbus/machine-id`), macOS IOPlatformUUID via `ioreg`, else a random 32-byte
  id persisted once at `${NOTREST_HOME}/machine-id` 0600; `fingerprint = sha256(machine_id)`;
  hostname never in the hash. The mock hub and the fixture use the same function.
- **Files:** identity token `~/.notrest/atlas-token`; ingest secret
  `~/.notrest/credentials/atlas-ingest-<project>`; old `credentials/atlas-token` read with one
  warning until 4.9 retires it.
- **Live arm target:** project `notrest-plugin`; ingest + view secrets exist on the Atlas box and
  reach this Mac by the owner's hand (two files into `~/.notrest/credentials/`, 0600).
- **Vendored files** carry the Atlas license line verbatim; node ≥ 22 is a soft dependency.

## Board state during the build (honest, expected)

This estate's own bank goes RED from the first wave-A commit: `gate:the-laws-hold` fails on NETWORK-EGRESS (the new
atlas modules talk to the hub) and SCRIPT-OWNS-SCANNING (SKILL.md does not yet name the new scripts). Both are
laws catching up with a deliberate change, fixed by B2 and B3; the ship gate requires the board GREEN again.

## Open records from wave A (carried to the ship)

- A2: the Linux `/etc/machine-id` branch is unexercised here (no Linux box); the NAS exercises it first — the
  fingerprint's container branch is proven by stubbing. `PINNED_JWKS` is empty until Atlas publishes its key
  (I-A); the seat fills the pin at the ship. Measured on this Mac: import 7.6 ms, fingerprint 15.3 ms (one
  `ioreg`), verdict 0.1 ms with no token — inside the 100 ms hook budget.

- A9: `.mcp.json` at the plugin root is PROVEN to load on skills-dir at personal scope (`claude mcp list`:
  plugin:notrest:atlas Connected) — but it is not live-reloaded like SKILL.md: a running session needs
  /reload-plugins or a restart. The 11 tool schemas cost ~1k tokens always-on that doctor's TOKEN BUDGET does not
  count (measured as JSON bytes, not host tokens) — re-read the figure from a connected session before release.
  The ship stamp (A8) must add `plugins/notrest/.mcp.json` and `skills/atlas/mcp/*` to `evals/golden-release-surface.txt`.

## Bounds stated now

- Built against the mock until I-A is live; the transport base URL and the signing key are the
  only things the live arm changes. Nothing claims "live" without the live arm's exit code.
- Vendored verifier carries Atlas authorship and the license line Atlas names.
- No lane spawns before the owner's go; no lane spawns while the owner has said the window is near its limit.
