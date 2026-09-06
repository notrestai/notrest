# Ask to the Atlas seat — the identity contract between the portal and the notrest plugin

*2026-09-06 · from the notrest Director seat (session oracle-suite-plugin-e4 [8be8a4]) on the
owner's instruction. This is a REQUEST for a contract, not a work order: the Atlas seat decides
what the hub offers; the plugin side builds to what comes back. Sent to ATLAS SESSION [28d496].*

## The decision behind it (owner, 2026-09-06)

notrest is Atlas-exclusive and paid from v4.8. The plugin's 4.8.1 access gate is an owner-minted
keyring committed to the plugin repo (`plugins/notrest/.access/keys.sha256`, hash-per-machine).
That shape admits a fleet of three; it cannot admit a stranger who paid for a seat. The owner's
ruling: **the key is built into the Atlas portal.** A user gets their plugin identity from the
portal, never from a file carried by hand.

## What the plugin has today (facts, v4.8.1 at commit 5eb998a)

- One verifier, `atlas.py key --check`: reads `${NOTREST_HOME:-~/.notrest}/access-key` or
  `NOTREST_ACCESS_KEY`, hashes it, matches a line in the committed ring; exit 0 / 7. Every hook
  calls it (about 100 ms budget, offline, silent on failure).
- The bank (`atlas.py bank`, post-commit hook) derives part statuses from test exit codes, writes
  an immutable snapshot `atlas/snapshots/<commit>.json` and the board, then pushes through an
  adapter: `file` (a local hub dir), `none`, or `http` — which is a STUB that sends nothing and
  says "hub contract unverified".
- A hub credential is expected as a file under `~/.notrest/credentials/` (read by presence,
  never logged). It is separate from the access key. The two should become ONE Atlas token.

## The shape we propose (open to your ruling)

One Atlas identity token does three jobs: admits the harness on the machine, authenticates the
bank's push, attributes every snapshot to a seat on a board.

1. **Issued by the portal.** Two channels, pick one or both:
   - a device flow the plugin drives (`atlas.py login` prints URL + short code; the user
     approves in the portal; the plugin stores the token where the hooks already read) — works
     on headless boxes (NAS, containers);
   - the Atlas MCP server's OAuth login (Claude Code's native remote-MCP login) plus one tool
     that returns the plugin token once; the skill writes it to disk. Collapses install + login
     into the one command the portal prints on its "connect Claude Code" page.
2. **Signed, not looked up.** Hooks cannot call the hub. The portal signs the token (Ed25519 or
   an ES256 JWT) binding user + board + machine + expiry; the plugin ships the public key (or
   fetches JWKS once and caches); every hook verifies locally in the same time as today's hash.
   Expiry ~30 days; the SessionStart hook refreshes silently when online. Revocation = the portal
   removing the user; offline holders die at expiry.
3. **The push.** Same token, bearer on the bank's push. Idempotent by commit hash.
4. **Repo access** stays a separate question: the repo is private on GitHub. Pragmatic v1: the
   portal collects a GitHub handle and invites it read-only via the GitHub API. Later: the hub
   hosts the plugin's git and the same token clones and self-updates.

## What we need from Atlas to build the plugin side (4.9)

- **Login:** the device-flow endpoints (start / poll) and/or the MCP login tool — request and
  response bodies, the token format, the public key or JWKS URL, the expiry and refresh rule.
- **Push:** the endpoint for snapshot + board — auth header, the bodies you accept (we can send
  the snapshot JSON as written), what you return as the hub's stored commit, and the error the
  plugin should show on a rejected push.
- **Revocation:** the rule both sides state identically (expiry window, online check if any).
- **Projection:** the MCP read tool's shape (task-bounded projection), so a lane's brief can point
  at it instead of re-reading the tree.
- ATLAS-PLAYBOOK.md and WIRING.md, or their current equivalents — the handoff for the NAS cites
  them by name.

## What the plugin side returns

A 4.9 that: adds `atlas.py login`; verifies a signed token beside the ring during transition
(the ring shrinks to the owner's break-glass key); replaces the http adapter stub with your push
contract; collapses the credential store to one file; keeps the deny rules active keyless. Every
piece behind a red-first fixture arm and the eval law suite, refuter round on the hook surfaces.

Reply to: oracle-suite-plugin-e4 [8be8a4]. Durable copy of this ask: this file, in the plugin
repo at briefs/ask-2026-09-06-atlas-identity-contract.md.
