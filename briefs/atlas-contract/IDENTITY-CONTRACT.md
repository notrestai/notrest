# ATLAS IDENTITY CONTRACT — v0 (2026-09-06)

*Ruling by the atlas seat on the plugin seat's ask (briefs/ask-2026-09-06-atlas-identity-contract.md). Two halves, marked on every section: **LIVE** = served by https://atlas.not.rest today and covered by the hub's verify; **PROPOSED** = the hub side is not built; the owner decides, then the atlas seat builds and the plugin builds to it. Secrets never appear here.*

## 0. The ruling in five lines

1. **One token, three jobs** — yes. One Ed25519-signed token admits the harness on a machine, authenticates the bank's push, and attributes every snapshot to a user and a seat.
2. **Signed, verified offline** — yes. EdDSA (Ed25519) compact JWT; the plugin pins the current public key and caches JWKS; hooks verify locally in pure python, no network, under 100 ms.
3. **Issued by the portal through a device flow** — yes, that is v1. The MCP OAuth channel is v2.
4. **Revocation** = the user's token ids are listed by the hub; online sessions learn it at SessionStart; offline holders die at expiry (30 days). Same sentence on both sides.
5. **Push by token** — yes, and the legacy per-project ingest secret keeps working through the transition so nothing that pushes today breaks.

## 1. LOGIN — device flow (PROPOSED)

The plugin drives it; works headless.

| step | request | response |
|---|---|---|
| start | `POST /v1/auth/device/start` `{client:"notrest-plugin", version:"4.9.0", machine:{name:"<hostname>", fp:"<sha256 of a stable machine fingerprint>"}}` | `200 {device_code, user_code:"ABCD-EFGH", verification_uri:"https://atlas.not.rest/activate", interval:5, expires_in:900}` |
| user | opens `/activate` (house login: the owner's email code today; a seat's email tomorrow), enters `user_code`, sees machine name + requested scope, approves and picks the projects the seat may push | the portal calls `POST /v1/auth/device/approve` with the session cookie |
| poll | `POST /v1/auth/device/poll {device_code}` every `interval` s | `428 {error:"authorization_pending"}` · `200 {token, expires_at, jwks:"https://atlas.not.rest/.well-known/atlas-jwks.json", kid}` · `410 {error:"expired_token"}` · `403 {error:"access_denied"}` · `429 {error:"slow_down"}` |
| store | the plugin writes `token` to **`${NOTREST_HOME:-~/.notrest}/atlas-token`** (0600) — the ONE credential file; `access-key` and `credentials/atlas-token` retire | |

`atlas.py login` = start → print URL + code → poll → store → `key --check` green.

## 2. THE TOKEN (PROPOSED)

Compact JWT, `alg: EdDSA` (Ed25519), `kid` in the header. Claims:

```
iss  "https://atlas.not.rest"        aud  "notrest-plugin"
sub  "<user id — the login email>"    seat "<machine name as approved>"
mid  "<machine fingerprint sha256>"   prj  ["kernel","atlas"] or ["*"] (owner)
scp  ["harness","push","view"]        jti  "<uuid>"
iat  <epoch s>                        exp  iat + 30 days
```

Verification rule (both sides, identical): signature valid against the pinned key or a JWKS key with the header's `kid`; `iss`/`aud` exact; `now < exp` (60 s skew); `mid` equals this machine's fingerprint unless `scp` contains `"roaming"`; `jti` not in the cached revocation list. Any failure = the same exit 7 the ring returns today. The plugin ships the verifier: **pure-python Ed25519 verify (RFC 8032), no dependencies** — the atlas seat provides the reference implementation and a fixture (`kit/verify-token.py`, PROPOSED), measured under 50 ms on this box.

**Refresh:** `POST /v1/auth/refresh` with `Authorization: Bearer <token>` while it is still valid and `exp - now < 7 days` → `200 {token, expires_at}`. The SessionStart hook does this silently when online; offline it does nothing. A token past `exp` cannot refresh — log in again.

**Keys:** `GET /.well-known/atlas-jwks.json` (public, no auth) → `{keys:[{kty:"OKP",crv:"Ed25519",kid,x}]}`. Rotation: a new `kid` is published at least 30 days before the old one stops signing; the plugin pins the current key in its release and refreshes JWKS at SessionStart. The private key is a worker secret (`ATLAS_TOKEN_KEY`), minted at deploy, never in the repo.

## 3. PUSH (LIVE today with the ingest secret; token as bearer PROPOSED)

| | |
|---|---|
| snapshot | `POST /v1/snapshot/<project>` · `Authorization: Bearer <token or ingest secret>` · `content-type: application/json` · body = wire **atlas-hub/1** (hub/SCHEMA-v1.md; the mapping from `atlas.py`'s snapshot is HUB-CONTRACT.md §4) · ≤ 2 MB bytes |
| board | `POST /v1/board/<project>` · same bearer · `content-type: text/html` · one self-contained HTML · ≤ 4 MB bytes |
| success | `201 {stored:"snap:<project>:<ts>", project, nodes}` / `201 {stored:"board:<project>", project, bytes}` |
| **stored commit** | the wire's own `head` — the hub stores the wire verbatim and serves `head` back on `GET /v1/snapshot/<project>`. Return `hub_commit = head` on 201. Do not read it back within ~60 s (KV edge cache); `status` waits up to 120 s before calling a mismatch red. |
| idempotent (PROPOSED) | a push whose `head` and body hash equal the latest stored snapshot returns `200 {stored:<existing>, idempotent:true}` instead of a new version |
| attribution (PROPOSED) | with a token bearer the hub records `{sub, seat, jti}` as metadata on the stored key (never inside the wire); history rows show `pushed_by` |
| errors to surface verbatim | `401 authorization: bad bearer` · `403 project: not in this token's projects` (PROPOSED) · `403 scope: push required` (PROPOSED) · `413 body: <n> bytes exceeds limit <m>` · `422 <path>: <one fact>` (the validator; e.g. `nodes[3].parts[1].evidence: status "done" cannot be "failing"`) · `400 body: not parseable JSON` |

Send the snapshot as `atlas.py` writes it **after** the §4 mapping; the hub refuses its native `status: blocked` / `evidence: passed` vocabulary — the table in HUB-CONTRACT.md is the bridge.

## 4. REVOCATION (PROPOSED) — the rule, stated once

> A token is revoked by its `jti` or by its `sub`. The hub lists revoked ids at `GET /v1/auth/revoked` (auth: any valid token; returns `{jti:[…], sub:[…], as_of}`); the plugin caches the list at SessionStart when online and refuses a cached-revoked token exactly as an invalid signature. Offline machines keep working until `exp` (≤ 30 days) and no longer. Removing a user in the portal revokes every token of that `sub` at once. There is no offline revocation and both sides say so.

The owner's break-glass key stays in the plugin's ring for the transition; the ring shrinks to that one entry when v4.9 ships.

## 5. PROJECTION — the MCP read tools (LIVE, local stdio; remote OAuth = v2)

Server: `node /work/atlas/mcp/server.mjs` (zero dependencies; will ship inside the plugin), auth = the same token file (`ATLAS_TOKEN_FILE`, default `~/.notrest/atlas-token`; today `ATLAS_VIEW_FILE`). Tools (all read-only, bounded, JSON in `content[0].text`): `atlas_projects()` · `atlas_project(project)` · `atlas_subtree(project, node_id, depth=1)` · `atlas_objective(project)` · `atlas_blockers(project)` (blocked steps + blocker centrality) · `atlas_findings(project)` (counts only) · `atlas_history(project, limit)` · `atlas_diff(project, a?, b?)` · `atlas_search(query)` · `atlas_playbook()` · **`atlas_relevant_context(project, task)`** → `{project, task, matched_on:[…], nodes:[{id,kind,title,parts:[{id,status,evidence,check}]}], edges:[…], journey_steps:[…], blockers:[…], recent_changes:[…], truncated:bool}` capped at 4 KB. A lane brief points at it as: *"context: atlas_relevant_context('<project>', '<the task sentence>')"*.

## 6. PLAYBOOK and WIRING (LIVE)

`GET /playbook` (markdown, v2.0) · `GET /playbook/version` · `GET /kit` + `GET /kit/<file>` — view-gated today (cookie or view secret; token with `view` scope once §2 lands). Repo copies: /work/atlas/ATLAS-PLAYBOOK.md, WIRING.md, HUB-CONTRACT.md, hub/SCHEMA-v1.md.

## 7. Repo access (PROPOSED, v2)

Out of the token's scope in v1. The portal collecting a GitHub handle and inviting it read-only needs a GitHub token as a worker secret and an owner-visible audit line per invite; the atlas seat will scope it after §1–4 are live. [SUPERSEDED by §9 — owner ruling 2026-09-06.]

## 8. Build plan for the hub side (PROPOSED — superseded by §11)

## 9. GIT — the hub hosts the plugin's repo (PROPOSED; owner ruling 2026-09-06 supersedes §7)

- **Transport:** git over HTTPS at `https://atlas.not.rest/git/notrest.git`, **read-only for consumers**. v1 serves the *dumb* HTTP protocol from a mirror the hub keeps (an R2 bucket the atlas seat refreshes from the origin with `git update-server-info` on every tag; the origin of record stays the private GitHub repo until the owner moves it). Dumb HTTP is enough for clone, fetch, `pull --ff-only` and for Claude Code's marketplace clone, and it is what a worker can serve today. Smart HTTP (`git-upload-pack`) is v2 if clone size makes it necessary.
- **Auth:** HTTP Basic, username `atlas`, **password = the Atlas token**; the hub verifies the token (signature, exp, `scp` contains `"harness"`) and refuses with `401` + `WWW-Authenticate: Basic realm="atlas"`. Never a token in a URL. The credential helper is host-scoped and reads the token file: `git config --global credential.https://atlas.not.rest.helper '!f(){ echo username=atlas; echo "password=$(tr -d "\r\n" < "${NOTREST_HOME:-$HOME/.notrest}/atlas-token")"; }; f'` (the plugin's `login` installs it; the token file is the same one §1 writes).
- **Tags:** every release tag (`v4.9.0` …) is visible in `info/refs`; the marketplace manifest pins one.
- **Versions seen:** each authenticated fetch logs `{sub, seat, ref or tag requested, plugin version from User-Agent when present, ts}` to a `pulls:` record — no IP, no body. The portal shows "seats × versions" so a stale fleet is visible; nothing else is done with it.

## 10. BOOTSTRAP — a consumer with no plugin yet (PROPOSED, v2 = I-C)

1. Claude Code connects the **remote Atlas MCP** (`https://atlas.not.rest/mcp`) and performs its native OAuth login: the hub is the OAuth 2.1 provider (authorization code + PKCE, dynamic client registration as the MCP spec requires); the human step is the house login on the portal.
2. The session calls **`atlas_connect()`**. It returns, once per login, `{token, expires_at, bootstrap}` where `bootstrap` is the exact ordered text the session performs: (1) write `token` to `${NOTREST_HOME:-~/.notrest}/atlas-token`, mode 600 (the one file; the plugin's `access-key` name is accepted as an alias during transition); (2) install the host-scoped credential helper above — **before** any marketplace command, because Claude Code clones marketplaces with the system git; (3) add the hub's git URL as the plugin marketplace, then install the `notrest` plugin from it. The plugin seat authors the bootstrap text; the hub serves it verbatim so both sides agree by construction. The device flow (§1) remains the headless path (NAS, containers).
3. `atlas_connect` is the only MCP tool that writes anything, and it writes a token, never state.

## 11. Revised hub build phases (PROPOSED — awaiting the owner's go)

| phase | scope | done when | est. |
|---|---|---|---|
| I-A | Ed25519 key as worker secret + JWKS; token mint/verify module; device flow start/poll/approve; `/activate`; pure-python verifier + fixture for the plugin | `key --check` accepts a portal token offline; foreign-key token = exit 7 | 1½ days · 500–800k |
| I-B | push by token (scope + project), attribution metadata, idempotent push, refresh, revocation list, portal seat admin; **git mirror over dumb HTTP from R2 with Basic-auth token + pull log** | kernel and atlas push by token; a clone of the plugin works through the helper; removing a user revokes | 2 days · 700k–1M |
| I-C | multi-user house login, remote MCP with OAuth 2.1 provider, `atlas_connect` bootstrap | a stranger with a granted seat logs in, bootstraps, pushes, is projected | 2–3 days · 800k–1.2M |

Ordering law: I-A before anything, because every other piece verifies the same token.

Nothing in this contract weakens a law: secrets by path, counts-only wire, Atlas never owns authority (a token admits a harness and a push; it never approves, deploys, or executes).
