# DOCKET 4.9 — the portal owns identity; the hub owns the plugin's git

**STATUS: DRAFT — awaiting the owner's approval. No lane is dispatched until the owner says go.**
*Drafted 2026-09-06 by the Director seat. Contract ask to Atlas: `briefs/ask-2026-09-06-atlas-identity-contract.md`.*

## The change in one paragraph

4.8.1 admits a machine by a key the owner mints and carries by hand, hashed against a ring
committed to the repo. 4.9 admits a machine by an Atlas token the portal issues to a paying seat.
The same token authenticates the bank's push and the clone / self-update of the plugin from the
hub's own git. The ring shrinks to the owner's break-glass key. A consumer starts from the Atlas
MCP server (Claude Code's native OAuth login) because no plugin exists on their machine yet; a
headless box logs in with a device flow.

## Decision the owner must make at approval (D1)

How hooks verify a token OFFLINE. Stdlib Python has no asymmetric crypto, and the hooks may not
depend on anything else.

- **D1-a (recommended): opaque token, hub-verified, verdict cached.** `atlas.py login` and the
  SessionStart hook verify with the hub when online (one bounded call, ≤2 s, silent) and write a
  verdict cache under `~/.notrest/` bound to the token hash + expiry + machine. Every other hook
  checks the cache, offline, in the same ~100 ms as today. Revocation is instant when online and
  ≤ expiry offline. No crypto ships in the plugin. A user who forges their own cache defeats only
  their own gate — the push still needs a valid token at the hub, and the gate controls the
  harness on a machine, not the source.
- **D1-b: signed token (Ed25519), verified locally.** Ships a pure-Python RFC 8032 verifier
  (~150 lines, ~20–50 ms per verify, so verify once per token and cache). Stronger offline
  guarantee, more kernel surface to refute, and the hub must run a signing key. Can be added
  later as an upgrade of D1-a without changing the store.

## Phases

**Phase 0 — contract-independent, can start on approval.** Login client (device flow) against a
MOCK hub the fixture runs; the token store; the credential helper; `key --check` accepting a
cached verdict beside the ring; SessionStart refresh; the keyless banner reworded to name the
login; fixture arms red-first; the marketplace manifest and bootstrap text. Transport lives in
one adapter module so the Atlas reply changes one file.

**Phase 1 — after the Atlas reply.** The http push adapter to the real contract; token/endpoint
alignment; the MCP projection pointer in lane briefs (agentswarm); the bootstrap text finalized
to what the MCP tool returns.

**Phase 2 — ship.** Refuter round on the kernel surfaces (LAW), eval law arms, doctor check for
the helper, docs (README, CHANGELOG, NAS handoff v2, SKILL.md), stamp with the pin-asserting
script (both tombstones untouched), gates green, ship 4.9.0.

## Lanes

| Lane | Model · tier | Scope (TOUCH-ONLY) | Done-when | Tokens | Wall-clock |
|---|---|---|---|---|---|
| K · kernel builder | opus · judgment | `skills/atlas/scripts/atlas.py`, `skills/atlas/SKILL.md` | `login` (device flow vs mock hub), token store, credential helper, verdict cache, `key --check` accepts cache or ring; fixture arms green | 18–22M | 2.5–3 h |
| H · hooks builder | opus · judgment | `hooks/session-start.sh`, `hooks/estate-root.sh`, `hooks/atlas-bank-hook.sh`, hook fixture | SessionStart refresh (bounded, silent), banner text, call sites read the cache; hook fixture arms green; `eval check` 0 | 10–14M | 2 h |
| T · tester | opus · judgment | `skills/atlas/scripts/fixture.sh`, `evals/**` only — never product code | Red-first arms: expired, revoked, wrong machine, offline-with-cache, offline-without, helper protocol, token-in-URL refused; report only | 6–9M | 1.5 h |
| K (resumed) · push adapter | opus · judgment | same as K | `push_http` to the Atlas contract, JWKS/verify endpoint, rejected-push error surfaced, `bank` exit codes unchanged | 8–12M | 1.5 h |
| R · refuter | opus · judgment | read-only on the tree | Attacks K+H+push before ship; two rounds budgeted (last two rounds here came back NOT CLEAN first) | 10–16M | 1–2 h |
| D · docs | opus · judgment | `README.md`, `CHANGELOG.md`, `NOTREST-ON-THE-NAS.md` → v2, `docs/ATLAS-CONNECT.md` (bootstrap text), workshop deck delta | Every command in the docs runs (`starthere_lint`-style check on the connect doc) | 8–12M | 1.5 h |
| M · manifest + stamps | sonnet · bounded | `.claude-plugin/*.json`, `plugins/notrest/.claude-plugin/plugin.json`, `docs/oracle-skill-flow.html` stamps | Runnable: versions match, both tombstones pinned (9.0.0 / 4.7.1), `doctor check` ≤ 5 | 0.5–1.5M | 20 min |

Seat (Fable): commissions banked before dispatch, gates exit-code-checked, merges, ship — the
seat's own context cost is not receipted per lane; expect it in the same order as one refuter round.

**Totals:** 60–86M lane tokens · roughly ONE full usage window for Phase 0 (K, H, T in
parallel, ~3 h wall) and a SECOND for Phases 1–2 (~4 h wall, gated on the Atlas reply).
For scale: the 4.7 build receipted ~100M+ across its lanes and hit the limit once; 4.8.0 shipped
inside one morning at ~25M.

## Parallelism and order

1. On go: commission K, H, T together (interfaces declared in the briefs: the verdict-cache file
   format and the helper's name are fixed by the seat before dispatch so K and H do not wait on
   each other). M runs any time before the stamp.
2. K resumes (never respawns) when Atlas answers. If Atlas has not answered by the end of Phase
   0, the seat gates Phase 0 and the estate waits — nothing ships half-wired.
3. R after K-resume lands; K/H resume for fixes; R again if the first round is not clean.
4. D in parallel with R. Stamp, gates, ship.

## Bounds stated now

- Repo access for consumers = the hub's git. Until the hub serves it, this repo's marketplace
  entry keeps working for the fleet (skills-dir on this Mac, clone on the NAS).
- The device flow and push are built against a mock until the contract arrives; the transport
  adapter is the only file expected to change.
- D1-b (signing) is not in this docket unless the owner picks it at approval.
- No lane spawns before the owner's go; no lane spawns while the owner has said the window is
  near its limit.
