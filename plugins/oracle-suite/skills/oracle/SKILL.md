---
name: oracle
disable-model-invocation: false
description: Session intake + resume — the suite's front door. On "hey oracle", /oracle, "start an oracle session", or "resume / pick up where we left off": load the CLAUDE.md foundation, offer to resume from START-HERE.md (in multi-session environments, open the live line back to the predecessor and fold its answers in), ask the six ORACLE questions one at a time (Objective, Role, Architecture, Content, Leverage, Evaluation — each skippable), recommend which suite skill fits the objective, then proceed — scaffolding a starter CLAUDE.md if none exists. Not for ordinary questions.
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
  written when the work lands, evidence included**. Newest at the bottom; compact to
  `COORD-ARCHIVE.md` at ~40 lines. In fable-director repos the per-lane blackboards are
  `COORD-<LANE>.md` beside it — never write to a lane's file.

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
5. **Leverage** — "Any tools or skills I should use or avoid? (web search, a specific Skill, work offline, etc.)"
6. **Evaluation** — "How will you judge a good result, and how should I check my own work? (e.g., cite every claim, flag anything unverified, end with the one thing most likely to be wrong.)"

## When done (all answered, or "skip rest")
- Reflect back a one-line summary per slot, "—" for anything skipped:
  > **O:** … **R:** … **A:** … **C:** … **L:** … **E:** …
- Ask: "Ready to go, or want to change anything?"
- **Route to the right tool:** from the Objective, name the suite skill (or chain) that fits and why, in one line — research a question → `/researcher` · understand a topic → `/explainer` · make a choice → `/decider` · verify claims → `/factcheck` · size a market → `/marketresearcher` · build a plan → `/stepbystep` (then `/actionplan` for commands) · red-team something → `/critic` · "what do we already know?" → `/archivist` · "how does this project connect?" / map the files → `/graph` · audit model spend/routing → `/spend` · several in sequence → `/director` — or say "no skill needed, working directly." The user can take the route or ignore it.
- **Foundation file — always create on a new session:** if no `CLAUDE.md` exists, **always scaffold one** from the bundled **`references/claude-foundation-template.md`** — no matter how many slots were answered or skipped (even an all-skipped/test intake still gets the file). Seed it with whatever answers you have (Architecture → protocol, Leverage → tooling, Content → the project section) and keep the template's placeholders for anything unanswered, so the structure is ready for `sessionend` to fill from real work. Keep it a *base*, not comprehensive. Write it where it persists: repo root in Claude Code (so it's auto-read), the working dir in Cowork, or the outputs area in a chat (present it for download). If `CLAUDE.md` already exists, leave it untouched — you loaded it; updates happen at session end.
- Then do the work, applying the answers. Internally follow the loading rule: **use their Content first and keep their actual ask last; put the most important facts at the start or end, never buried in the middle.**
- For any skipped slot, pick a sensible default and note in one line what you assumed. For a skipped **Evaluation**, default to the suite's reliability standard: label non-obvious claims, flag anything unverified plainly, and end substantial answers with the one thing most likely to be wrong.

## Note
This is a setup ritual for a real working session. For a quick one-off, the user can answer just **Objective** (and maybe **Content**) and skip the rest.

Bookend: `oracle` brings up the foundation (`CLAUDE.md`) and resumes from `START-HERE.md` at session start; **`sessionend`** updates them at session end. Together they make sessions continuous.
