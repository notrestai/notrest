# The notrest harness in 10 minutes

The session harness — plus twenty-three skills — that make any Claude session **token-lean, verified, and continuous** — on any topic, with any model. This is the shortest path from install to your first full working loop.

## 1. Install (once)

```
/plugin marketplace add notrestai/notrest
/plugin install notrest@notrest
```

**Renaming from `oracle-suite`?** Same harness, new id (the marketplace is still `notrest`, so the
install id is `notrest@notrest` and skills invoke as `/notrest:<name>`). Install `notrest` as above,
then `claude plugin uninstall oracle-suite`.

That's it. Four hooks come alive immediately:
- **SessionStart** injects the fable-discipline anchor (verification-first working habits) AND the offload model policy (every job a Fable session delegates runs on explicit Opus) into every session, auto-creates `COORD.md` — the per-prompt session ledger — at any git-repo root, detects `START-HERE.md` / `HANDOFF.md` resume files, and self-updates the plugin from git (note: marketplace installs live in a version cache, not a git clone — there, update with `claude plugin update notrest@notrest`).
- **UserPromptSubmit** — when `COORD.md` exists, every prompt carries a one-line reminder: append a ledger line when the work lands (ask → landed | evidence). The ledger survives crashes and compaction even if `/sessionend` never runs.
- **PreCompact** reminds you to run `/sessionend` before context compaction eats your session state — or at minimum to append the COORD ledger line first.
- **SubagentStop** — when a spawned agent finishes inside a git repo, auto-writes one line (id · model · last conclusion · transcript path) to `COORD-AGENTS.md`, so which agents were consulted and what each concluded lands in the repo automatically, at zero model-token cost.

## 2. The shape of every skill

Every working skill follows the same contract, so you only learn it once:
- **Natural language triggers it** — "research the best X", "help me decide", "is this true?", "explain Y" — or invoke explicitly: `/researcher`, `/decider`, `/factcheck`, `/explainer`…
- **Two files out:** a `background.md` (all the working-out, auditable) and a `Dossier.md` (the answer — self-contained, plain-language "Read Me First" up top).
- **`--quick` mode:** chat-only, no files, compressed — for exploration, honestly labeled as such.
- **Honesty labels everywhere:** `[cited]` (real URL, retrieved this run) · `[recall]` (training knowledge) · `[estimate]` (computed — math shown) · `[unverified]`. Confidence levels on conclusions, plus "what would change this."
- **A self-check before finishing** — every skill verifies its own output against its rules.

## 3. Your first loop (the full experience)

1. **`hey oracle`** — the intake. Six quick questions (Objective, Role, Architecture, Content, Leverage, Evaluation), each skippable. It loads/scaffolds your `CLAUDE.md` foundation and routes you to the right skill.
2. **Run the work** — say what you need in plain words; the right skill picks it up (see the map below).
3. **`/sessionend`** — before you stop. It writes `START-HERE.md`, `HANDOFF.md`, `STATE.md`, updates the foundation, and (in Claude Code desktop) keeps a live line open to answer the next session's questions.
4. **Next session: `hey oracle`** again — it finds `START-HERE.md` and resumes exactly where you left off, reading in order: `HANDOFF.md` (curated snapshot) → the `COORD.md` ledger tail (the per-prompt trail with evidence — current to the last prompt even if the previous session crashed, and the tiebreaker when docs disagree) → `STATE.md` → `CLAUDE.md`.

Prefer a picture? [oracle-skill-flow.html](oracle-skill-flow.html) is a one-page visual of this whole loop (open it in a browser — GitHub shows HTML as source).

## 4. Which skill, when

| You want to… | Say / invoke |
|---|---|
| Understand something properly | "explain X" → **explainer** |
| Answer an open question with evidence | "research X" → **researcher** |
| Check if something is true | "is this true?" → **factcheck** |
| Keep a checked fact from going stale | "watch this claim" / "recheck weekly" → **watch** |
| Make a choice | "should I…?" → **decider** |
| Size a market / find a niche | "map this market" → **marketresearcher** |
| Get an ordered, verified plan | "plan how to X" → **stepbystep** |
| Turn the plan into exact commands | "make it copy-paste" → **actionplan** |
| Attack something before trusting it | "red-team this" → **critic** |
| Run several skills in sequence | "research X, critique it, then plan it" → **director** |
| Start / resume a session properly | "hey oracle" → **oracle** |
| Save everything before stopping | "/sessionend" → **sessionend** |
| Work with discipline all session | automatic (hook) · full contract: **/fable-mode** |
| Run a multi-SESSION dev team | "/fable-director" → **fable-director** |
| Delegate heavy work fast (any seat + Opus lanes) | "swarm this" / "/agentswarm" → **agentswarm** |
| Ask "what do we already know about X?" | "index the dossiers" → **archivist** |
| See how the files connect (or every project at once) | "map the files" / "/graph" → **graph** |
| Audit token spend / model routing | "spend report" → **spend** |
| How did we get here? | "recap the project" / "/recap" → **recap** |
| Get a GPT second opinion | "/gpt" → **gpt** |
| Let Claude sessions + GPT work in one room | "open a chatroom" → **chatroom** |
| Snapshot what the model is thinking (scored) | "/introspect" → **introspect** |
| Build a playable game | "make me a game about…" → **game-forge** |

## 5. Chains worth knowing

- `researcher → critic` — find the answer, then try to break it.
- `researcher → factcheck` — research, then independently verify its load-bearing claims.
- `marketresearcher → critic → stepbystep` — opportunity → stress-test → plan.
- `stepbystep → actionplan` — plan → copy-paste runbook.
- `researcher → decider` — evidence → structured choice.
- `recap → archivist → critic` — walk the trail into the decision story, pull the dossiers it references, then red-team the conclusion the project has been running on.

Say it naturally ("research X, then critique it, then plan it") — **director** parses the chain and runs every stage for real, each in its own context.

## 6. The reliability standard (why you can trust the output)

Every skill enforces: real sources only (invented citations are banned), tiered sourcing (primary beats secondary beats blogs), disconfirmation passes (each skill actively tries to break its own answer), severity/verdict grammars instead of vibes, and honest "unverified / not found / it depends" outcomes when that's the truth. The suite's job is not to sound right — it's to be checkably right, and to show its work.

## 7. Costs, quick

Full runs search the web and write files; `--quick` variants stay in chat and cost a fraction. Search budgets are built in (a researcher run defaults to ~20 searches, factcheck ~3 per claim). You can always say "max 5 searches" or "keep it quick" — the skills honor stated caps and say what was traded away. Delegated fan-out runs on explicit Opus whatever model holds the seat (the owner offload policy — and Fable never rides in a subagent), via **agentswarm**; the **spend** ledger receipts every lane so the routing stays checkable, not asserted.
