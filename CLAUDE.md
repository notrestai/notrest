Last updated: 2026-07-25

# CLAUDE.md — notrest harness foundation

## Protocol
- Fable discipline every session — the hook anchors it, `/fable-mode` is the contract.
- Offload policy: the SessionStart echo is operative; `/agentswarm` is the arrangement.
- `/spend report` exits 4 on a routing violation; `/archivist` before research fan-outs.

## Project
- This repo IS the `notrest` marketplace: `plugins/notrest/` (28 skills); manifests
  `plugins/notrest/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` —
  **versions must match**. `plugins/oracle-suite-tombstone/` is the rename stub pinned
  at 9.0.0 — **never bump it**.
- Release: bump both manifests + CHANGELOG.md + README table + both version stamps in
  docs/oracle-skill-flow.html → commit → push → `claude plugin marketplace update notrest
  && claude plugin update notrest@notrest` (restart applies). The hook's git self-update
  no-ops on cache installs — the CLI path is the real one.
- `spend/ledger.md` is append-only; the SubagentStop hook auto-receipts each finished lane
  (idempotent) — hand-logging double-counts.
- COORD never compacts, it ROLLS: at 500 lines the active file seals as `COORD-<NNN>.md`
  (immutable) and a fresh volume opens; `COORD-AGENTS.md` at 1000.
- Ship gate: `doctor.py check` (install) + `eval.py check` (laws), both green.
- A compiled runtime under `compile/<slug>/` is tracked SOURCE, isolated until the owner
  ships it; only derived scan output is gitignored.
