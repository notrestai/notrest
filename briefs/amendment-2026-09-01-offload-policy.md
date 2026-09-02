# OFFLOAD POLICY — owner amendment 2026-09-01 (supersedes the 2026-08-30 sonnet clause)

Owner's words (2026-09-01, to the Director): "the orchestrator should be able to choose which
model to use sonnet or opus based on the difficulty of the task."

## The law as it now reads (single source of truth for 4.6.2 — every surface quotes THIS)

**The seat chooses each lane's model by the difficulty of the task, and declares the choice.**
- **opus** — judgment-bearing work: design, debugging, root-cause, kernel surfaces (hooks,
  establish.py, ledger writers), refuters and reviews, merges, anything ambiguous or
  under-specified, any commission whose done-when the seat cannot state as a command.
- **sonnet** — bounded, well-specified work: mechanical edits with an exact target, format
  conversions, inventory sweeps, fixture/battery runs, drafts under a tight contract, any job
  whose done-when is a runnable check the seat wrote before dispatch.
- **When unsure, opus.** Difficulty is the seat's call; the brief records it.
- **Declared, not implied:** the dispatching brief (briefs/commission-*.md or the Agent prompt)
  states `model: opus — tier: judgment` or `model: sonnet — tier: bounded` with one line of
  why, so the receipt (spend ledger, COORD-AGENTS) is checkable against the choice.
- **Unchanged bans:** never haiku (a tier declaration does not launder it); never
  `subagent_type: "fork"` (forks inherit the seat); a spawn that omits `model` is a violation,
  not a default; never `/model`-switch the seat. Fable never rides in a lane.
- **Enforcement:** `hooks/spawn-gate.sh` denies omitted-model / fork / haiku (unchanged);
  `spend.py report` grades receipts (sonnet lawful; the brief carries the tier); the
  SessionStart echo and every SKILL.md that states the policy quote this text.

## Surfaces that must carry it in 4.6.2 (owner of each in parentheses)
- hooks/session-start.sh echo + hooks/spawn-gate.sh header comment (lane H)
- skills/notrest/scripts/establish.py protocol-block template + skills/eval/scripts/eval.py
  OFFLOAD-POLICY check (accept the new wording; red on the old opus-only wording is NOT
  required — reject only haiku/fork/omitted) + fixtures (lane S)
- README.md, skills/fable-mode/SKILL.md, skills/agentswarm/SKILL.md (add the difficulty
  rubric above as the routing table), skills/tieredswarm/SKILL.md (lane D)
- CLAUDE.md (this repo) protocol block re-synced to the template; ~/.claude/CLAUDE.md
  standing order; memory file (seat)
