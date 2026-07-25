# ORACLE Suite

A working-session toolkit for Claude Code by [Not Rest Inc.](https://do.not.rest) — structured
thinking from intake to handoff. Twenty-three skills that compose:

- **oracle** — session intake (the ORACLE six-question setup) + loads/scaffolds the `CLAUDE.md` foundation. Say "hey oracle" or `/oracle`.
- **researcher** — multi-pass research → background + decision dossier.
- **marketresearcher** — market sizing, competitors, whitespace → opportunity dossier.
- **stepbystep** — goal/docs → a stress-tested, converged, ordered action plan.
- **actionplan** — a stepbystep plan → a copy-paste runbook (exact commands per host).
- **critic** — adversarial red-team with a severity-tiered verdict.
- **explainer** — a correct mental model + three depth layers + misconceptions + verify-it-yourself.
- **decider** — weighted criteria, evidence, the hinge ("what flips the winner"), pre-mortem → a reversibility-aware recommendation.
- **factcheck** — claim-by-claim verdicts (✅/🟡/🔴/🔵/⚪) against independent real sources.
- **watch** — facts have shelf lives: a small watchlist of a dossier's load-bearing cited
  claims, re-verified on a cadence with factcheck's rigor and grammar → a dated drift log
  (HOLDS / DRIFTED / DEAD-SOURCE / UNVERIFIABLE) that stamps what it actually fetched; a dead
  source is never a refutation, and scheduling (where the scheduled-tasks MCP exists) is always
  owner-confirmed, never faked.
- **introspect** — validated workspace self-reports (a black-box J-space instrument): two-layer
  sealed snapshots (scored token spine + readable glosses) scored against behavior, with a
  context-only control for predictive lift.
- **game-forge** — complete, playable games on the fly with the craft baked in (fixed-timestep
  engine templates, genre playbooks, juice/audio) — and never delivered unrun: a headless
  playtest gate is part of the workflow.
- **gpt** — chat-first GPT lane: /gpt just talks (persistent, remembered) after a 2-question
  guided setup (thinking level + how agentic); --once one-shots, --task background jobs with
  verified deliverables, --vs blind comparisons, --here repo-aware runs; [model-opinion]
  labeled, never evidence; director-safe by design.
- **chatroom** — shared rooms where any Claude session and GPT work together: append-only
  room files as the wire, armed watches as wakes, a gpt-bridge member with persistent
  memory; no-secrets boundary (rooms feed other vendors' models).
- **archivist** — content continuity: one greppable `oracle-index.md` over every dossier
  the project has produced; consult before re-spending a search budget (reuse/extend/fresh).
- **graph** — an Obsidian-style file graph: a script walks the repo and renders a
  self-contained force-directed HTML view of every file and the references between them
  (wikilinks, links, imports, sourced scripts, estate pointers) at zero model tokens;
  `register` + `all` merge every registered project into one cross-project PM map.
- **spend** — append-only model-spend ledger + report with a routing verdict (exits 4 if
  Fable ever rode below the seat) — makes the v2.7.0 routing hard rule checkable.
- **recap** — the read side of the estate: walks COORD / COORD-AGENTS / git / spend in
  timestamp order and turns the recorded trail into the project's decision story — a
  narrated timeline, who was consulted (transcript paths existence-checked), ships, costs,
  open threads — plus a self-contained clickable decision map (nodes = rulings, decisions,
  agent consultations, ships; edges = led-to / informed-by / reversed). Every claim cites a
  trail line; anything without one is labeled `[unverified]`. Derives, never invents.
- **director** — chains the skills into a pipeline (e.g. `researcher → critic → stepbystep`).
- **fable-director** — seats and runs the "3 DEVS AND A RELAY" multi-session dev arrangement
  (metered director + flat lanes over per-lane blackboard files with token-watch wakes;
  V4 protocol + repo scaffolder bundled).
- **agentswarm** — the fast delegation arrangement: the seat (the main session's model —
  Fable or Opus alike) keeps decompose, judge, apply, gate; everything else offloads to
  concurrent in-session **Opus** lanes; the harness is the wire (no blackboards, no watches,
  no rotation). The default way any seat delegates; fable-director remains the multi-day /
  multi-machine choice.
- **sessionend** — writes START-HERE / HANDOFF / STATE / CLAUDE.md for a seamless next session.
- **fable-mode** — the Fable behavioral contract: the discipline loop + hard rules (incl.
  the offload model policy — Fable never rides in a subagent; every offloaded job runs on
  explicit Opus, never sonnet/haiku, never forks), consumer-side verification, the outage playbook
  (reroute, stage, never stall), tool-graph craft, and situational profiles — auto-anchored
  into every session by the SessionStart hook.

Most skills also support `--quick` (chat-only, no files) and write a paired *background* +
*Dossier* file for anything substantial.

## Evals
`evals/` holds the suite's release-gate eval cases (5 cases, 13 graders) for Claude Code's
plugin eval runner — they guard the offload policy, COORD discipline, honesty labels,
intake routing, and graph's zero-token rule. Run per `evals/README.md`; eval runs cost
real tokens, so they gate releases rather than run on hooks.

## Install
```
/plugin marketplace add notrestai/ORACLE
/plugin install oracle-suite@notrest
```
Then invoke any skill as `/oracle-suite:<name>` (e.g. `/oracle-suite:researcher`), or just
`/researcher` when unambiguous.

## Note on `director`
`director` orchestrates the sibling skills by reading their `SKILL.md` files directly. It resolves
them from `${CLAUDE_PLUGIN_ROOT}/skills/` when installed as a plugin, and falls back to
`.claude/skills/` (project) or `~/.claude/skills/` (global) — so chaining works whether the suite
is installed as a plugin or dropped in as loose skills. (`fable-director` is different: it
orchestrates *sessions*, not skills — a multi-session dev arrangement over blackboard files.)

MIT © 2026 Not Rest Inc.
