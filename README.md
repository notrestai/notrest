# Not Rest Inc. — Claude Code plugins

The **`notrest`** plugin marketplace by [Not Rest Inc.](https://do.not.rest).

## Install

```
/plugin marketplace add notrestai/ORACLE
/plugin install oracle-suite@notrest
```

## Plugins

### ORACLE Suite (`oracle-suite`)
A working-session toolkit — structured thinking from intake to handoff, built on three principles: **token-lean** (progressive disclosure, `--quick` modes, built-in search budgets), **verified** (real tiered sources, disconfirmation passes, honesty labels on every claim), and **model-agnostic** (the discipline lives in the skills, so any model runs them reliably):

| Skill | What it does |
|---|---|
| **oracle** | Session intake — six setup questions (Objective, Role, Architecture, Content, Leverage, Evaluation) + loads/creates the `CLAUDE.md` foundation. Invoke with "hey oracle" or `/oracle`. |
| **researcher** | Rigorous multi-pass research → a background doc + a decision dossier. |
| **marketresearcher** | Funnel-shaped market research → sizing, competitors, whitespace, an opportunity dossier. |
| **stepbystep** | Turns a goal/docs into a stress-tested, converged, ordered action plan. |
| **actionplan** | Expands a stepbystep plan into a copy-paste-ready runbook (exact commands per host). |
| **critic** | Adversarial red-team of any document — steelman, attack, alternatives, severity-tiered verdict. |
| **explainer** | Layered understanding of any topic — a correct mental model, plain → working → expert layers, the standard misconceptions, verify-it-yourself checks. |
| **decider** | Structures any decision — weighted criteria, evidence per option, sensitivity ("which assumption flips the winner"), pre-mortem, recommendation with reversibility framing. |
| **factcheck** | Claim-by-claim verification against real sources — ✅ CONFIRMED / 🟡 PLAUSIBLE / 🔴 REFUTED / 🔵 MISLEADING / ⚪ UNVERIFIABLE, with daisy-chained sources detected. |
| **introspect** | Validated workspace self-reports — a black-box instrument inspired by Anthropic's J-space research: two-layer sealed snapshots (scored tokens + readable glosses) scored against subsequent behavior (verbalized / silent / turnover) with predictive lift vs a context-only control agent. Ships with a real example ledger. |
| **game-forge** | Complete playable games from a short request — fixed-timestep engine templates (browser + pygame), genre playbooks, juice/audio references, and a hard playtest gate: no game ships unrun. |
| **gpt** | Chat-first GPT lane (5.6 family, Codex CLI on your ChatGPT account): `/gpt` just talks to a persistent conversation after a 2-question guided setup — thinking level + how agentic. `--once` one-shots, `--task` background jobs with verified deliverables, `--vs` blind comparisons, `--here` repo-aware mode, and a no-questions `--setup` path for orchestrators. Opinions labeled, never treated as sources. |
| **chatroom** | Shared rooms for AI sessions — any Claude session joins via a tiny script (append-only room file, flock-atomic posts, armed watches as wakes), GPT joins through a persistent-memory bridge (`gpt-bridge --once`, mention-triggered, throttled). Local-machine v1; strict no-secrets rule. |
| **archivist** | Content continuity — scans every ORACLE output folder into one greppable `oracle-index.md` (title, date, path, each dossier's Read Me First), so "what do we already know about X?" costs one `find` instead of a re-spent search budget. Consult-before-spending; the index is a finding aid, never a source. |
| **spend** | The token receipt — an append-only `spend/ledger.md` of every observed model spend (subagent counts, workflow totals, gpt tokens-used), graded observed/estimate; `report` prints the per-model split and **exits 4 if Fable ever rode below the seat** — the routing rule, made checkable. |
| **director** | Chains the other skills into a pipeline (e.g. `marketresearcher → critic → stepbystep`). |
| **fable-director** | Seats and runs the **"3 DEVS AND A RELAY"** multi-session dev arrangement — a metered Fable/Opus director that applies all code, flat Opus dev/QC lanes handing EDIT SPECS, per-lane blackboard files with token-watch wakes, a QC refuter relay, and a self-carrying rotation ritual. Bundles the V4 protocol of record + a repo scaffolder. Invoke with `/fable-director`. |
| **agentswarm** | The **fast delegation arrangement** — the seat (the main session's model: Fable or Opus alike) keeps decompose, judge, apply all edits, gate ships, and offloads everything else to concurrent in-session **Opus** lanes; the harness is the wire (no blackboards, no watches, no rotation — deaf lanes and split-brain deleted by construction). Owner model policy: every offloaded job runs on Opus. QC refuter runs as code after every finding; spend-ledger receipts per lane; archivist consult before fan-outs. Use fable-director only when lanes must outlive the machine or span accounts. |
| **sessionend** | Captures session state into START-HERE / HANDOFF / STATE / CLAUDE.md so the next session resumes seamlessly. |
| **fable-mode** | The Fable behavioral contract: the ORIENT → PROBE → ACT → PROVE → BANK loop, hard rules — including the **offload model policy** (Fable never rides in a subagent: every offloaded job runs on explicit Opus, never inherited Fable credit; delegation via agentswarm) — THE FABLE DIFFERENCE (instinct → fable move), a consumer-side verification cookbook, the outage playbook (reroute, stage, never stall), tool-graph craft, and situational profiles. Auto-anchored every session by the SessionStart hook; full contract via `/fable-mode`. |

`oracle` + `sessionend` are bookends: ORACLE loads the foundation at the start, sessionend updates it at the end — together they make sessions continuous. **fable-mode** is the posture in between: the SessionStart hook injects its discipline anchor every session, so reliable working habits are on by default without anyone typing `/fable-mode`.

## Continuity & discipline hooks
- **SessionStart** — self-updates the plugin from git (fire-and-forget `--ff-only`; note: marketplace-cache installs aren't git clones — there the update path is `claude plugin update oracle-suite@notrest`); injects the **fable-discipline anchor** AND the **offload model policy hard rule** (Fable sessions offload every spawned job on explicit Opus — never sonnet/haiku, never inherited Fable — with agentswarm as the default delegation arrangement) every session; **auto-creates `COORD.md`** — the session coordination ledger (the fable-coord behavior, generalized) — at any git-repo root and nudges reading its tail when it exists; detects `START-HERE.md` / `HANDOFF.md` and adds a resume nudge; detects per-lane `COORD-<LANE>.md` (or legacy `FABLE-COORD*.md`) blackboards and nudges seating the fable-director.
- **UserPromptSubmit** — when `COORD.md` exists, injects a one-line reminder on every prompt: append one honest ledger line when this prompt's work lands (ask → landed | evidence).
- **PreCompact** — reminds that a deliberate `/sessionend` handoff preserves more than automatic compaction.
- **SubagentStop** — when a spawned agent finishes inside a git repo, auto-writes one machine-written line (id · model · last conclusion · transcript path) to `COORD-AGENTS.md` at the repo root, so the session's decision pattern — which agents were consulted and what each concluded — lands in the repo at zero model-token cost (the archivist indexes it; entries point at the full transcripts).

## 10-minute tutorial
[docs/TUTORIAL.md](docs/TUTORIAL.md) — install → the shape of every skill → your first full loop → which-skill-when → chains worth knowing.

## Visual: how an ORACLE session flows
[docs/oracle-skill-flow.html](docs/oracle-skill-flow.html) — a one-page, self-contained diagram of the oracle intake (foundation & resume → the six questions → routing → the continuity loop). GitHub shows HTML as source — open the file locally in a browser, or via GitHub Pages if enabled for this repo.

## License
MIT © 2026 Not Rest Inc.
