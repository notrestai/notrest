# ORACLE Suite — Codex + Claude

A cross-runtime working-session toolkit by [Not Rest Inc.](https://do.not.rest) — structured
thinking from intake to handoff. Thirty-one skills share one estate and expose native
Codex and Claude adapters. Read `docs/CODEX.md` for the exact boundary.

- **oracle** — session intake + loads/scaffolds `AGENTS.md` on Codex or `CLAUDE.md` on Claude.
- **notrest** — the establishment verb: writes `COORD.md` + a marker-delimited protocol block in
  `AGENTS.md` (Codex), `CLAUDE.md` (Claude), or both (idempotent, atomic, nothing outside the markers touched), then binds the invoking
  session to the protocol. `check` is the read-only drift check — establishment facts drive the
  exit code, adoption facts stay INFO, and adherence is the seat's judgment, said out loud.
- **researcher** — multi-pass research → background + decision dossier.
- **marketresearcher** — market sizing, competitors, whitespace → opportunity dossier.
- **stepbystep** — goal/docs → a stress-tested, converged, ordered action plan.
- **actionplan** — a stepbystep plan → a copy-paste runbook (exact commands per host).
- **critic** — adversarial red-team with a severity-tiered verdict.
- **refuter** — critic's executable-side sibling: a lane other than the builder attacks one
  narrow target under a written brief (isolated scratch dir, hard prohibitions, a numbered
  attack ladder, ~12 tool calls) and returns CONFIRMED findings with a pasted reproduction,
  PLAUSIBLE ones with a concrete failure scenario, and what survived by name. Finds — never
  fixes.
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
- **spend** — append-only model-spend ledger + report with a date-guarded runtime routing
  verdict (Claude=opus, Codex=gpt-5.6-sol).
- **eval** — the harness's law-conformance suite: `eval.py check --root .` runs static
  checks over the shipped files — the dual runtime model map, inherited-fork ban,
  honesty labels, scanners that exist and compile, append-only ledgers, the
  worker contract, front-matter YAML accepts with a `/slash` trigger, the named safety
  laws, silent-on-failure hooks. A law that is well-encoded leaves a static fingerprint;
  check the fingerprint, not the behavior. ~0.1s, zero model tokens, file:line on every
  FAIL. Model-graded `behavior` cases are bounded, code-graded and opt-in.
- **doctor** — the harness's self-check: `doctor.py check --root .` runs eight named
  PASS/WARN/FAIL checks — front-matter that a real YAML load would reject (the unquoted
  colon-space that makes a skill invisible), manifest + tombstone pins, skill-count drift,
  hook files that exist and parse, estate integrity, install-vs-repo drift, unanchored
  gitignore rules, stale render stamps — each with the command that fixes it. Every check
  descends from a defect that actually shipped. Reads only; never repairs.
- **compile** — the estate's fourth verb: a python3-stdlib scanner mines COORD, the agent
  ledger and the spend ledger for the same job done three or more times (at zero model
  tokens), then a seat-run ritual reconstructs that job's contract from the trail, builds an
  isolated runtime under `compile/<slug>/`, has an independent lane attack it, and
  fair-benchmarks it against the history it came from. Cheaper-but-worse is a failed compile;
  the one-time cost is reported separately and never amortized; nothing installs itself.
- **recap** — the read side of the estate: walks COORD / COORD-AGENTS / git / spend in
  timestamp order and turns the recorded trail into the project's decision story — a
  narrated timeline, who was consulted (transcript paths existence-checked), ships, costs,
  open threads — plus a self-contained clickable decision map (nodes = rulings, decisions,
  agent consultations, ships; edges = led-to / informed-by / reversed). Every claim cites a
  trail line; anything without one is labeled `[unverified]`. Derives, never invents.
- **draft** — the outbound verb: a dossier, decision or recap → the thing you actually send
  (email, exec memo, slack update, one-pager, status update — each a skeleton with a hard
  length budget). Every factual sentence traces to a source line in a source-map and keeps its
  honesty label; framing choices are listed as choices; persuasion never upgrades a label
  ([estimate] stays hedged, [unverified] drops or hedges, never becomes fact). Numbers never
  invented, quotes never manufactured, recipients never guessed — and a draft is never sent:
  sending is the owner's act, and a draft file is never evidence of delivery.
- **beam** — checkpoints in-flight lanes to a pushed beam ref, respawns them in a cloud session, recalls the results home (`/beam up` · `/beam down`).
- **director** — chains the skills into a pipeline (e.g. `researcher → critic → stepbystep`).
- **fable-director** — seats and runs the "3 DEVS AND A RELAY" multi-session dev arrangement
  (metered director + flat lanes over per-lane blackboard files with token-watch wakes;
  V4 protocol + repo scaffolder bundled).
- **agentswarm** — the fast delegation arrangement: the seat keeps decompose, judge, apply,
  gate; authorized work offloads to explicit runtime workers (Codex `gpt-5.6-sol`, Claude
  `opus`); the harness is the wire (no blackboards, no watches,
  no rotation). The default way any seat delegates; fable-director remains the multi-day /
  multi-machine choice.
- **sessionend** — writes START-HERE / HANDOFF / STATE / the runtime foundation.
- **fable-mode** — the Fable behavioral contract: the discipline loop + hard rules (incl.
  the offload model policy — Fable never rides in a subagent; every offloaded job runs on
  explicit Opus, never sonnet/haiku, never forks), consumer-side verification, the outage playbook
  (reroute, stage, never stall), tool-graph craft, and situational profiles — auto-anchored
  into every session by the SessionStart hook.

Most skills also support `--quick` (chat-only, no files) and write a paired *background* +
*Dossier* file for anything substantial.

## Evals
`/eval` is the release gate: `skills/eval/scripts/eval.py` statically fingerprints the
shipped skills — offload policy, COORD discipline, honesty labels, intake routing, graph's
zero-token rule — in ~0.07s for **zero model tokens**, naming the file and line of every
failure. Run it with `/doctor` (installation health) before a version bump.

`evals-legacy-external-runner/` holds the retired `claude plugin eval` cases (5 cases, 13
graders), kept only as a record of what was measured: ~13 min per pass, $4.58 per graded
run, zero fixes in 45 minutes. **Never run as a ship gate.**

## Install — Claude
```
/plugin marketplace add notrestai/notrest
/plugin install notrest@notrest
```
Then invoke any skill as `/notrest:<name>` (e.g. `/notrest:researcher`), or just
`/researcher` when unambiguous.

**Renaming from `oracle-suite`?** Same harness, new id — the plugin was renamed
`oracle-suite` → `notrest` (the marketplace name is unchanged, hence `notrest@notrest`).
Install `notrest` as above, then remove the old entry with `claude plugin uninstall oracle-suite`.

## Install — Codex local build

Use this repo's `.agents/plugins/marketplace.json`, install
`notrest@notrest-codex-local`, and start a new Codex task. The native manifest is
`.codex-plugin/plugin.json`; it intentionally omits Claude hooks.

## Note on `director`
`director` orchestrates sibling skills by reading their `SKILL.md` files directly. It resolves
them relative to its own selected skill first, then the host's project/user skill directories — so chaining works whether the suite
is installed as a plugin or dropped in as loose skills. (`fable-director` is different: it
orchestrates *sessions*, not skills — a multi-session dev arrangement over blackboard files.)

MIT © 2026 Not Rest Inc.
