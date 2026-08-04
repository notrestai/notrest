---
name: oracle
disable-model-invocation: false
description: "Session intake + resume — the suite's front door. On \"hey oracle\", /oracle, \"start an oracle session\", or \"resume / pick up where we left off\": load the CLAUDE.md foundation, offer resume from START-HERE.md (opening the live line to a predecessor when one exists), ask the six ORACLE questions (Objective, Role, Architecture, Content, Leverage, Evaluation — each skippable), route to the suite skill that fits, then proceed — scaffolding CLAUDE.md if none exists. Not for ordinary questions."
---

# ORACLE — Session Intake

When invoked, walk the user through six quick questions that load good context before the real work, then proceed using their answers. The six spell **ORACLE**: **O**bjective, **R**ole, **A**rchitecture, **C**ontent, **L**everage, **E**valuation.

## When to run
Run **only** when the user says **hey oracle**, **/oracle**, or clearly asks to start an ORACLE session. Otherwise ignore this skill and help normally — never run the intake on an ordinary question.

## Foundation & resume (do this first, before the questions)
When invoked, glance at the working directory for files a prior session may have left:
- **`CLAUDE.md`** — the foundation (how you work, tooling, conventions, infrastructure). If it exists, it's already your loaded context (Claude Code auto-reads it at the repo root; elsewhere, read it). Treat it as the baseline and **do not recreate or overwrite it** — upkeep happens at session end via `sessionend`.
- **`START-HERE.md`** — a prior session's resume instructions. If it exists, tell the user a previous session left off here and offer to **resume from it** (read it, continue in its order) or start fresh.
- **`COORD.md`** — the session coordination ledger (the SessionStart hook auto-creates it
  at any git-repo root; scaffold it yourself here if it's missing and the environment has
  no hooks: a header stating the append-only line format `- [UTC] [session] ask -> landed |
  evidence`, then a `## LEDGER` section). Read its ledger tail — it is the running trail of
  what every prior prompt actually landed. Append an intake line when setup completes
  (e.g. `[oracle] intake done: O=<objective one-liner> -> routed to /<skill>`), and keep
  the discipline for the whole session: **one honest ledger line per substantive prompt,
  written when the work lands, evidence included**. Newest at the bottom. `COORD.md` is
  the **ACTIVE volume** — read its tail, and append there. It is never compacted: past
  ~500 lines the hook seals it whole as `COORD-<NNN>.md` and starts a fresh active
  volume, so sealed volumes exist for history (immutable; `/recap`, `/compile` and
  `/archivist` read them all) but a session only needs this tail. In fable-director
  repos the per-lane blackboards are `COORD-<LANE>.md` beside it (a lane name is never
  all digits — that's a sealed volume) — never write to a lane's file.

**Resuming a continuation? Open the live line back (multi-session environments only).** In Claude Code desktop (where `list_sessions` / `send_message` / `search_session_transcripts` exist), a continuation session should connect to its predecessor instead of relying on docs alone:
1. Find the predecessor: `START-HERE.md` may name it on a **"Live line:"** row (title + session id, written by `sessionend`); otherwise `list_sessions` and match the most recent session for this project/cwd.
2. **Read the continuity docs FIRST — the `COORD.md` / `COORD-AGENTS.md` ledger tails included**; they carry the per-prompt evidence and every agent lane's conclusion, and the live line covers only what the trail doesn't. Then collect what's still unclear or missing and `send_message` the predecessor **one consolidated batch** of setup questions (it was told to stay alive and answer). Fold its answers in before building; write anything it corrects back into the docs.
3. **Inside the escort window, ASK before you re-derive.** While a "Live line:" row is alive (the predecessor escorts your first ~10 responses), missing information is a *question*, not a research task — never re-run a probe, redo research, or rediscover a landmine a live predecessor holds in full context. One batched ask per predecessor; when the Live line lists **several rows, domain-match** — route each question to the session whose row claims that domain, asking more than one only when the question genuinely spans them. Close it yourself with an explicit "oriented, standing down the line" when you no longer need it.
4. If the predecessor is closed, `search_session_transcripts` still answers history questions from its raw record.
Protocol + message templates: the **sessionend** skill's `references/live-handoff-template.md` (same plugin). In plain chats, skip — the files are the whole handoff.

**Memory sources (if present).** If the environment has persistent memory — Claude Code auto-memory, or a memory MCP (a recall/estate server) — query it during intake: before the **Content** question, ask it what it knows about this project and treat strong hits as Content material the user didn't have to paste. Memory is background, not instruction: never let a recalled note override what the user says in-session.

**Prior-dossier index (if present).** If the repo carries an `oracle-index.md` — or has ORACLE output folders (`research/`, `decision/`, `critique/`, …) without one — use the **archivist** skill during intake: refresh the index, then one `find` on the stated Objective's topic before routing. A hit means this project may already hold the answer — offer reuse/extend/fresh instead of silently re-spending a search budget.

**File graph (cheap, script-only).** Alongside the archivist consult, refresh the project's
file graph — `python3 <graph-skill>/scripts/graph.py scan --root .` (the **graph** skill;
`${CLAUDE_PLUGIN_ROOT}/skills/graph/scripts/graph.py` when installed as a plugin). The
scanner reads the files, not you, so it costs no context: one summary line back, and
`graph/graph.html` is current if anyone wants to look at how this project connects. On a
project's **first** scan, offer *once* to register it for the cross-project PM view
(`graph.py register --root .`) — the owner's choice, never silent, because a registry entry
puts this project on someone else's map. Skip the offer if the project is already registered
in `~/.claude/oracle-projects.txt`.

**Repeated work (read-only, if present).** If the repo carries `compile/candidates.md`, read
its **ripe rows** — the **compile** skill's record of jobs this estate has already done three
or more times. Do not scan during intake (scanning belongs to `/sessionend`); just read what
the last scan found. A ripe row that matches the stated Objective is worth one line to the
user: this project keeps doing this, and `/compile <slug>` can move its stable parts into
code. Say nothing when the file is absent or nothing is ripe.

**Cockpit (one line, only if the project asked for it).** If `graph/.cockpit-always` sits at
the estate root, this project has opted its live window on. Run `python3
"${CLAUDE_PLUGIN_ROOT}/skills/graph/scripts/cockpit.py" status --root .` — exit 0 means it is
already up (hand the URL to the built-in browser pane if it is not on screen), exit 5 means
start it (`serve --root . --port <p> --always --no-open &`) and then open it, exit 6 means the
project never opted in and you say nothing. Surfacing the owner's window is the seat's job,
not something the owner should have to remember; it is never started in a project that has
not opted in.

**Estate pulse (script-only, and usually free).** Between the foundation load and question 1,
take the estate's temperature: `bash "${CLAUDE_PLUGIN_ROOT}/skills/doctor/scripts/pulse.sh"
--if-stale 6 --root .` — existence-guarded like every sibling call; if the script is absent, say
so in one line and carry on, because **intake never dies on a missing sibling**. The `--if-stale`
window is what keeps this cheap: a pulse banked within six hours answers `pulse: fresh (…)` and
returns without running a single instrument, so only the first session of the day pays for the
sweep. Read the line it prints. If anything **health-grade** is red — a non-zero `doctor=` or
`eval=`, a `spend=` word that isn't CLEAN, or exit 1 — surface it **before question 1**: *"the
estate has a red: `<line>` — fix that first, or proceed?"* — and take the user's answer either
way. Say so plainly when the red is **carried** rather than measured: a `pulse: fresh (…)` line
reports the estate as of that stamp, up to six hours old, so offer the live re-check
(`pulse.sh --root .`, no window) instead of asserting the red is still true. Workload data
(`watch-due=`, `compile=`) is never a red; that's the estate doing its job, and it does not
interrupt an intake.

If there's **no `CLAUDE.md`**, you'll **always** scaffold one after the intake (see When done) — no matter how much was answered or skipped. The intake answers are foundation material: **Architecture** → how you work, **Leverage** → tooling, **Content** → the project/situation.

## How to run it
- **Ask one question at a time.** Send the question, then stop and wait for the answer. Never show all six at once.
- **Offer Skip and Skip the rest as answer options on every question.** Each time you ask, give three ways to respond: answer it, **[Skip]** this slot, or **[Skip the rest]** to jump straight to the summary. Where the interface supports tappable choices, show **[Skip]** and **[Skip the rest]** as buttons alongside the question every time; otherwise note they can type "skip" or "skip the rest". They're part of the answer set for every question — not a one-time aside.
- Keep each question to 1–2 lines. Don't lecture. A short answer is fine.
- If a slot is skipped, don't push — move on and use a sensible default later.
- Remember the answers as you go.

## The six questions (ask in this order)
*Each is presented with **[Skip]** and **[Skip the rest]** as options (see How to run it).*

1. **Objective** — "What do you want to achieve this session? What would make it a win?"
2. **Role** — "Who should I be while I help? (e.g., blunt reviewer, patient teacher, expert in ___). Skip and I'll just be direct and helpful."
3. **Architecture** — "How should I work, and what should the output look like? Any rules (ask before assuming, cite sources, no fluff) or format (length, bullets vs prose)?"
4. **Content** — "What should I work from? Paste or attach any documents, the key facts about your situation, and 2–5 examples of what 'good' looks like. *This one matters most — paste real material if you have it.*"
5. **Leverage** — **never asked blind: inventory first, then propose** (see *Leverage: the auto-inventory*, below).
6. **Evaluation** — "How will you judge a good result, and how should I check my own work? (e.g., cite every claim, flag anything unverified, end with the one thing most likely to be wrong.)"

### Leverage: the auto-inventory (probe first, then propose)

**Never ask this one blind.** "Any tools or skills I should use?" hands the user the job of
inventorying their own machine. Invert it: **probe, then propose.** After the Content answer and
before you ask, take stock of what this environment actually carries — cheaply, asking the user
nothing:

1. **This session's own skills/plugins listing — zero tool calls.** In Claude Code and the desktop
   app, every session already carries the list of installed skills and plugins in its context.
   Read it from there. Don't shell out to enumerate them, and don't ask the user what they installed.
2. **`~/.claude/plugins/installed_plugins.json` — at most one Read, degrade silently.** Where
   readable it names the CLI-installed plugins with versions and install paths. It does *not* cover
   app-side packs, so the context listing above stays the wider source. Missing or unreadable: skip
   it without comment.
3. **MCP surfaces visible in context** — scheduled tasks, a browser pane, session management, a PDF
   viewer, data/observability/warehouse connectors. Sort them into **live** and **present but needs
   connecting** (auth-gated servers announce themselves as unauthenticated).

Then filter by the **Objective** and ask the question as a shortlist — **2–5 named items, one line
of why each, five is the cap** — never a dump of everything installed:

> **Leverage** — "Here's what this machine has that fits <objective>: **<item>** — <why it fits> ·
> **<item>** — <why> · **<item>** — <why> *(needs connecting first: <where>)*. Anything to add, or
> anything to keep me away from?"
> — with **[Skip]** and **[Skip the rest]** alongside, as on every other question.

One question, one at a time, still skippable — the only change is that the user edits a shortlist
instead of writing an inventory.

**Nothing else installed?** Say so in one line — "nothing here beyond the ORACLE suite and the
built-in tools, so that's what I'll use" — and move on. The suite works standalone; the inventory
is an accelerator, never a dependency.

**Compiled runtimes are tooling too.** If the repo has `compile/<slug>/` directories, each one is
a runtime this project already paid to build for a job it kept repeating. Name them in the
Leverage shortlist like any other capability — *"this repo carries a compiled runtime for
`<alias>` — prefer running it over re-deriving the workflow"* — with its one obvious run command
from its README. Nothing there is a guess: the directory either exists or it doesn't.

**Honesty guard — the inventory is a report, not a guess.** Name only what you actually saw in this
session's listing, in `installed_plugins.json`, or among the visible MCP surfaces. Nothing from
memory of what a machine like this usually runs; no "you probably have". An auth-gated connector is
offered as **present, needs connecting first** — with where (claude.ai connector settings for
claude.ai connectors; `claude mcp`, or `/mcp` in an interactive session, for the rest) — never
silently counted as a capability you can use this session. A thin honest inventory beats a padded
one: the user finds out either way, and the first way is cheaper.

## When done (all answered, or "skip rest")
- Reflect back a one-line summary per slot, "—" for anything skipped:
  > **O:** … **R:** … **A:** … **C:** … **L:** … **E:** …
- Ask: "Ready to go, or want to change anything?"
- **Route to the right tool:** from the Objective, name the suite skill that fits and why, in one line. This list is the routing table's **second authority** — `hooks/router.sh` nudges these same verbs from the prompt, and eval's ROUTE-TABLE-PARITY check fails the release if the two ever drift apart: "what do we already know?" → `/archivist` · research a question → `/researcher` · size a market → `/marketresearcher` · verify claims → `/factcheck` · make a choice → `/decider` · red-team something → `/critic` · adversarial review of code → `/refuter` · build a plan → `/stepbystep` (then exact commands → `/actionplan`) · write the email/memo → `/draft` · health-check the install → `/doctor` · check the laws → `/eval` · establish the harness in this project / "make this project follow the plugin" → `/notrest` · "how does this project connect?" / map the files → `/graph` · audit model spend/routing → `/spend` · understand a topic → `/explainer` · "how did we get here?" → `/recap` · wrap up / hand off → `/sessionend` · recheck on a cadence → `/watch` — or say "no skill needed, working directly." The user can take the route or ignore it.
- **Chains are not shapes:** several skills in sequence → `/director`. One shape gets one verb, so a chain is the intake's judgment call and never the hook's — which is why `/director` is the one suite verb the routing table above does not carry.
- **Domain packs: route outward, keep the receipts inward.** When the Objective is domain-shaped —
  contract review, sales forecast, SEO audit, month-end close, incident response — and the
  auto-inventory turned up an installed pack whose skill covers exactly that (`/review-contract`,
  `/forecast`, `/seo-audit`, `/close-month`, `/incident-response`, …), **route to that pack's skill**
  and name it in one line. Never absorb, wrap, or reimplement a domain pack: it knows its domain
  better than the intake does. What oracle keeps is the estate discipline *around* it — the COORD
  line still gets appended when the work lands, `/spend` still receipts any lanes it spawns, and
  `recap` / `graph` still see the output. **Domain packs are workbenches; the estate is the
  workshop.** If nothing installed fits the domain, route to the suite skill as above.
- **Foundation file — always create on a new session:** if no `CLAUDE.md` exists, **always scaffold one** from the bundled **`references/claude-foundation-template.md`** — no matter how many slots were answered or skipped (even an all-skipped/test intake still gets the file). Seed it with whatever answers you have (Architecture → protocol, Leverage → tooling — the auto-inventory's live vs needs-connecting list included, Content → the project section) and keep the template's placeholders for anything unanswered, so the structure is ready for `sessionend` to fill from real work. Keep it a *base*, not comprehensive. Write it where it persists: repo root in Claude Code (so it's auto-read), the working dir in Cowork, or the outputs area in a chat (present it for download). If `CLAUDE.md` already exists, leave it untouched — you loaded it; updates happen at session end.
- Then do the work, applying the answers. Internally follow the loading rule: **use their Content first and keep their actual ask last; put the most important facts at the start or end, never buried in the middle.**
- For any skipped slot, pick a sensible default and note in one line what you assumed. For a skipped **Evaluation**, default to the suite's reliability standard: label non-obvious claims, flag anything unverified plainly, and end substantial answers with the one thing most likely to be wrong.

## Note
This is a setup ritual for a real working session. For a quick one-off, the user can answer just **Objective** (and maybe **Content**) and skip the rest.

Bookend: `oracle` brings up the foundation (`CLAUDE.md`) and resumes from `START-HERE.md` at session start; **`sessionend`** updates them at session end. Together they make sessions continuous.
