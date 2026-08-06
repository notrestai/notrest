Last updated: 2026-07-25

# CLAUDE.md — notrest harness foundation

## Protocol
- Fable discipline every session — the hook anchors it, `/fable-mode` is the contract.
- Offload policy: the SessionStart echo is operative; `/agentswarm` is the arrangement.
- `/spend report` exits 4 on a routing violation; `/archivist` before research fan-outs.
- **Commission transparency is a core value (owner, 2026-07-27):** every agent's prompt
  is user-visible — named at dispatch, banked by construction at `briefs/agent-<id>.md`
  (SubagentStop hook), marked graphically in the river. The commission is never hidden;
  scope-drift is disclosed at delivery (fable-mode 12a).

## KERNEL SURFACES — the higher bar

Convention adopted from cloudflare-os's AGENTS.md (Apache 2.0): name the places where a
mistake is an *estate-wide* mistake, so "be careful here" is a list rather than a feeling.

- `plugins/notrest/hooks/**` — every hook: they run in every session, and a broken one
  fails silently by design.
- `plugins/notrest/skills/notrest/scripts/establish.py` — writes COORD.md and the
  CLAUDE.md protocol block into other people's projects.
- Anything that consumes or writes the **estate ledgers**: `agent-ledger.sh`,
  `session-end.sh`, `spend/ledger.md` writers, the COORD volume roll.

**LAW: a kernel change ships only through a refuter round.** We have done this by habit
since the estate-writer rounds; here it stops being habit. The refuter attacks the change
before it ships, and `eval`'s KERNEL-REVIEW check asserts this list is named where it is
claimed — so the convention cannot quietly rot into prose nobody applies.

## Project
- This repo IS the `notrest` marketplace: `plugins/notrest/` (31 skills); manifests
  `plugins/notrest/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` —
  **versions must match**. `plugins/oracle-suite-tombstone/` is the rename stub pinned
  at 9.0.0 — **never bump it**.
- Release: bump both manifests + CHANGELOG.md + README table + both version stamps in
  docs/oracle-skill-flow.html → commit → push. This machine runs `notrest@skills-dir`
  (`~/.claude/skills/notrest` → this repo's `plugins/notrest`, loaded IN PLACE, zero cache
  copies): SKILL.md edits apply live, hook/manifest changes need `/reload-plugins` or a
  restart, and the SessionStart hook's `git pull --ff-only` genuinely self-updates.
  Consumers still install via the marketplace (`claude plugin marketplace update notrest
  && claude plugin update notrest@notrest`) — but NEVER run that flow on THIS machine:
  an installed notrest@notrest takes the name and silently SHADOWS the skills-dir
  runtime (live-proven 2026-07-25, reinstall at 20:13Z shadowed the tree until doctor
  caught it; remedy = `claude plugin uninstall notrest@notrest && claude plugin
  marketplace remove notrest` + cache purge).
- `spend/ledger.md` is append-only; the SubagentStop hook auto-receipts each finished lane
  (idempotent) — hand-logging double-counts.
- COORD never compacts, it ROLLS: at 500 lines the active file seals as `COORD-<NNN>.md`
  (immutable) and a fresh volume opens; `COORD-AGENTS.md` at 1000.
- Ship gate: `doctor.py check` (install) + `eval.py check` (laws), both green.
- A compiled runtime under `compile/<slug>/` is tracked SOURCE, isolated until the owner
  ships it; only derived scan output is gitignored.

<!-- notrest:protocol v1 (do not edit inside markers; managed by /notrest) -->
## notrest protocol

- **Fable discipline** — ORIENT -> PROBE -> ACT -> PROVE -> BANK. Probe the live
  system before reasoning; a done/works/fixed claim needs in-transcript evidence
  (exit code, diff, status) or it is labeled unverified; bank state before stopping.
  Full contract: `/notrest:fable-mode`.
- **Offload HARD RULE** — every spawned lane sets model `"opus"` explicitly. Never
  sonnet, never haiku, never a fork (a fork inherits the seat and bills its credit);
  omitting the model is a violation, not a default. Delegate via `/notrest:agentswarm`;
  a build runs ONE persistent lane and feedback RESUMES that lane, never a fresh spawn.
- **COORD law** — one honest ledger line per substantive prompt when its work lands:
  `ask -> landed | evidence`. `COORD.md` is append-only and is never compacted: at
  ~500 lines it seals whole as `COORD-<NNN>.md` and a fresh volume opens.
- **Close** a working session with `/sessionend`. **Drift check:** `/notrest check`.
<!-- /notrest:protocol -->
