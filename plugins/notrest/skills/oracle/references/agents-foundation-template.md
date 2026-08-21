# AGENTS.md — [project name]

<!-- Codex project foundation. Keep only stable instructions that a future task should
auto-load. Volatile status belongs in HANDOFF.md and STATE.md. -->

Last updated: YYYY-MM-DD

## Operating protocol

- ORIENT → PROBE → ACT → PROVE → BANK.
- A completed claim needs consumer-side evidence or `[unverified]`.
- Bank substantive landed work in the append-only `COORD.md` trail.

## Runtime and delegation

- Runtime: Codex.
- Delegation is used only when the user asks or host policy permits it.
- Authorized workers use explicit `model: "gpt-5.6-sol"` with `fork_turns: "none"`
  or a bounded recent-turn fork; the seat keeps judgment, application, and gates.
- Codex plugin hooks are not claimed in v4.3.0; use explicit Doctor and Eval checks.

## Project

- Purpose: [...]
- Architecture: [...]
- Build/test commands: [...]
- Important paths: [...]
- Current-plan pointer: [HANDOFF.md / START-HERE.md / other]

## Conventions

- [...]

## Safety and release gates

- [...]

## Maintenance

Keep a line only when a future task would otherwise get it wrong or waste effort
rediscovering it. Merge; never clobber user instructions. Remove stale rules. Keep
progress, blockers, and next actions in HANDOFF.md / STATE.md, not here.
