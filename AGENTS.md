# AGENTS.md — notrest Codex foundation

This repository is the source marketplace for the Not Rest harness. Codex uses
`plugins/notrest/.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`;
Claude uses the existing `.claude-plugin` manifests and `plugins/notrest/hooks/`.

## Protocol

- Work under ORIENT → PROBE → ACT → PROVE → BANK.
- A completed claim needs consumer-side evidence or the label `[unverified]`.
- Keep `COORD.md` append-only and bank one honest line when substantive work lands.
- On authorized delegation, Codex workers use explicit `model: "gpt-5.6-sol"` with
  `fork_turns: "none"` or a bounded recent-turn fork. Claude workers use explicit
  `model: "opus"` and never `subagent_type: "fork"`.
- Close a working task with `sessionend`; use `notrest check --surface codex` for drift.

## KERNEL SURFACES

- `plugins/notrest/hooks/**` — the Claude lifecycle adapter.
- `plugins/notrest/skills/notrest/scripts/establish.py` — writes `COORD.md` and the
  runtime foundation block into other projects.
- `plugins/notrest/.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` —
  the Codex discovery and install boundary.
- Anything that consumes or writes the estate ledgers.

A kernel change must pass deterministic fixtures, Doctor, and Eval. The existing project
law additionally calls for an independent refuter round; if the host cannot run the
required independent model, report that review as unperformed instead of treating static
tests as a substitute.

## Release invariants

- Claude manifest, Claude marketplace entry, and Codex manifest share one base version.
- The `oracle-suite` tombstone remains pinned at `9.0.0`.
- Codex manifests never claim Claude hooks.
- Update `CHANGELOG.md` and the golden release surface deliberately.

<!-- notrest:protocol v3 (do not edit inside markers; managed by /notrest) -->
## notrest protocol

- **Fable discipline** — ORIENT -> PROBE -> ACT -> PROVE -> BANK. Probe the live
  system before reasoning; a done/works/fixed claim needs in-transcript evidence
  (exit code, diff, status) or it is labeled `[unverified]`; bank state before stopping.
  Full contract: `/notrest:fable-mode`.
- **Runtime-explicit offload rule** — delegate only when the user asks or the host policy
  permits it. Claude lanes set the model EXPLICITLY, chosen by the seat on the difficulty
  of the task and declared in the dispatching brief: `"opus"` for judgment-bearing work,
  `"sonnet"` for bounded well-specified work whose done-when is a runnable check the seat
  wrote before dispatch. When unsure, opus. Never haiku, never `subagent_type: "fork"`;
  omitting the model is a violation, not a default. Codex lanes set `"gpt-5.6-sol"`
  explicitly and, because a model override cannot use a full-history inherited fork, use
  `fork_turns: "none"` or a bounded recent-turn fork. Never substitute one runtime's model
  for the other. A build keeps one persistent builder lane per domain, resumed for feedback.
- **Enforcement honesty** — Claude lifecycle hooks may enforce and receipt laws. Codex
  v4.3 has no equivalent plugin hook surface: `AGENTS.md`, the selected skill, Doctor,
  Eval, and consumer-side evidence carry the law. Never claim a hook ran on Codex.
- **COORD law** — one honest ledger line per substantive prompt when its work lands:
  `ask -> landed | evidence`. `COORD.md` is append-only and is never compacted: at
  ~500 lines it seals whole as `COORD-<NNN>.md` and a fresh volume opens.
- **Close** a working session with `/sessionend`. **Drift check:** `/notrest check`.
<!-- /notrest:protocol -->
