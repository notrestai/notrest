# JOURNEY.md — the harness as user journeys

Drafted 2026-07-25 (v3.8.0 tree, 28 skills). `CAPABILITIES.md` is the register: what each skill
*is*. This is the map: **where a user meets it**, what fires without anyone typing, what the
user sees, what lands on disk, and how each verb hands off to the next. Six journeys; every skill
appears in at least one, and the coverage matrix is the proof.

> **v3.9.0 (2026-07-25): all eighteen gaps below SHIPPED in one six-lane batch.** The
> G-sections remain as the build record; `graph.py journey` now renders this page's
> content as a flow diagram at zero model tokens.

**Reading a step.** **HOOK** = fires automatically, nobody typed anything. **INVOKE** = the user
names the verb, or a skill's own chain line names it. **SEES** = what appears in the transcript.
**LANDS** = what is on disk afterwards — a record kind, a ledger line, a receipt. Phrases in
`code` are **verbatim** from `plugins/notrest/hooks/router.sh` or the named skill's own
`SKILL.md`; nothing here paraphrases a trigger.

## The routing law — the spine under all six

A task shape routes to the suite's verb for it, enforced in four layers: **intake**
(`skills/oracle/SKILL.md` routes once, at session start, from the Objective) · **per-prompt**
(`hooks/router.sh`, 14 shapes → one ≤160-char nudge, first match wins) · **discipline**
(fable-mode Hard Rule 12) · **fingerprint** (`eval.py` check ROUTER asserts the table is wired and
every verb it emits is a real skill dir). **Overriding a route deliberately is fine. Silently
ad-hoc'ing a job a skill already owns is the violation** — the router says as much in its own
nudge: *"(fine to skip deliberately)"*.

## The six

- **J1 "I have a question"** — route → prior art → researcher records → factcheck → watch → draft.
- **J2 "I have a decision"** — store evidence → decider's six passes → critic/refuter → a decision record carrying its hinge → stepbystep → actionplan.
- **J3 "A build/ship session"** — hooks anchor → fable-mode → agentswarm lanes → auto-receipts → refuter gate → doctor+eval → compile → sessionend.
- **J4 "Help me understand / think with someone else"** — explainer, the gpt lane, chatroom rooms, introspect.
- **J5 "What do we already know / how did we get here?"** — archivist track+find, the river, the file graph, recap's story, the drift log, the PM view.
- **J6 "Make me something playable"** — game-forge, start to playtested finish.

---

## J1 — "I have a question"

**Step 0 — the session opens · HOOK.** `hooks/session-start.sh` echoes the two standing laws
(J3 step 0) and adds conditional nudges: `START-HERE.md` present → suggest `/oracle`; no
`COORD.md` at the git root → **scaffold it**; a ripe `NEW` row in `compile/candidates.json` →
name the slug and its count. **LANDS** `COORD.md` seeded with
`- [UTC] [hook] COORD.md scaffolded by notrest SessionStart`.

**Step 1 — the user types · HOOK.** Two UserPromptSubmit hooks run in order: `coord-nudge.sh`
(one 96-char ledger reminder), then `router.sh`, which lowercases, strips to space-padded words,
and walks an ordered `case` chain — first match wins.

> User: *"can you **look into** which cache layer fits our read path — a **deep dive**, not a skim"*

**SEES** `[notrest] route: this looks research-shaped — /notrest:researcher is the suite's verb
for it (fine to skip deliberately).` The router is **silent** on a prompt starting `/`, one
containing `/notrest:`, fewer than 4 words, no shape match, or one already naming the verb.
Research arm, verbatim: `" research"` · `" find sources"` · `" look into"` · `" deep dive"`.
Market-shaped instead? `" market size"` · `" tam "` · `" competitor"` · `" pricing landscape"` →
**marketresearcher**.

**Step 2 — prior art before spend · INVOKE (contractual).** researcher's own contract: one
`index.py find "<topic>"` **before Pass 1**, searching the findings store, the legacy index and
dossier bodies. On a hit, surface it (id or path, date, statement) and offer *reuse* / *extend* /
*fresh* — **the user picks**. The router hoists this above research on purpose:
`" what do we already know"` · `" have we research"` · `" already research"` → **archivist**,
because "have we researched this" is a superset of "research this". **LANDS** nothing; `find` is
read-only.

**Step 3 — five passes, and the records that survive them.** Baseline → ≥5 alternatives →
evidence → comparison → disconfirmation. The passes are the working-out; **the records are the
output**, emitted the moment a pass earns one, never batched at the end. Passes 1–3 land
`kind=finding`/`relation=toward`; sources disagreeing at origin land `kind=conflict`/`lateral`
with both positions named and **never averaged**; a corrected pass gets the better record plus
`index.py supersede F-<old> --by F-<new>`; an abandoned route lands `kind=backtrack`/`back`,
because dead ends are findings; the recommendation lands last as `kind=result`, `links` naming
what it rests on. **LANDS** `archive/findings.jsonl`, append-only under `flock` — every line
passed the door of 19 named rejection rules, and `add` exits **2 naming the rule it broke** while
writing nothing (a `[cited]` url must be a real `scheme://host`). Never hand-append.
**SEES** the passes as prose, then the assigned `F-<n>` ids and one command,
`index.py track --status live`. **The record bodies are never pasted back into chat.**

**Step 4 — verify what the answer rests on · chained from researcher.** researcher's finishing
line offers `/factcheck`; the user's own words are `" fact check"` · `" factcheck"` ·
`" verify claim"` · `" is it true"`. Four passes, and **one `kind=finding` per checked claim,
the verdict first in the statement** (✅ CONFIRMED / 🟡 PLAUSIBLE / 🔴 REFUTED / 🔵 MISLEADING / ⚪
UNVERIFIABLE), then the claim verbatim, then what carries it. Two independent origins for a ✅ —
and **the label is per source, not per claim**: an `[unverified]` item is never promoted by
sitting next to a good one. A `kind=result` headline record lands last.

**Step 5 — facts have shelf lives · chained from factcheck.** factcheck's chain line: *`/watch
add` on the confirmed load-bearing claims if the answer has to stay true past today*. User-side:
`"watch this claim"` · `"keep this fresh"` · `"recheck weekly"`; router shape `" watch this"` ·
`" recheck"` · `" on a cadence"`. `watch.py` owns everything that never needed a model — `due`
(exit **3** = something is due), `probe <ID>` (**0** unchanged · **3** changed · **4**
DEAD-SOURCE, via strong-ETag conditional GET plus sha256 against the row's stored hash), and
`append`. Subjects may be `F-<id>` store records, not only dossier paths, so the watchlist
stops carrying a second copy of a URL the store owns. **LANDS** a `watch/watchlist.md` row, a
dated block in the append-only `watch/drift-log.md`, and one COORD line
`- [UTC] [watch] recheck: N due -> X holds / Y drifted / Z dead | evidence: watch/drift-log.md <date>`.
**SEES** the headline only — *N due, X held, Y drifted*, the drifted ones by name.

**Step 6 — when the answer has to leave the building · route: outbound.** `" write the email"`
· `" write the memo"` · `" write an announcement"` · `" write the update"` → **draft**; also
`"make this sendable"`, `"write it up for <audience>"`. One law: **every factual sentence traces
to a line in the source and keeps its honesty label.** Framing choices are listed as choices;
persuasion never upgrades a label — `[estimate]` stays hedged, `[unverified]` drops or carries its
hedge. Produces a background file (claims table · 3-line audience brief · framing list ·
source-map) plus the deliverable, and **the last line every time: the draft is written; sending is
yours.**

**Step 7 — the trail is already drawn.** `graph.py river --root .` reads
`archive/findings.jsonl` plus the COORD volumes — every record a stone, the `toward` run the main
channel, ships and gates as flags. Zero model tokens; full treatment in J5.

**Unhappy — a finding is refuted.** F-3 says the vendor's page states X, `[cited]`, Tier 2.
Two weeks later factcheck's Pass 2 finds the page retracted: `index.py refute F-3 --evidence
https://…/retraction` writes a **tombstone** (`kind=result`, `relation=back`, `links:["F-3"]`,
statement opening `refutes F-3`). Nothing is edited in place — a status flip is a new line.
`track` resolves effective status by **walking links**, and both conditions must hold: named in
`links` **and** the statement opens with the flip verb; a passing mention flips nothing, and the
last tombstone in `ts` order wins (refuted outranks superseded). So `track --status live` drops
F-3, the river draws it as a **red rock** (a superseded stone would fade and strike through), and
F-3 stays on disk forever beside the record that killed it.

**Unhappy — the route is overridden on purpose.** Router nudges `/notrest:researcher`; the user
says *"no, just answer from what you know, I need it in 30 seconds."* Take it, and **label the
answer `[recall]`** — Hard Rule 12 is explicit that a deliberate override is lawful. The violation
is the silent version: running the five passes ad-hoc under no contract and calling the output
research.

---

## J2 — "I have a decision"

**Step 1 — the shape.** `" should i "` · `" choose between"` · `" compare options"` ·
`" decide"` · `" deciding"` → **decider**; skill-side `"X or Y"`, `"what are the tradeoffs"`.

**Step 2 — evidence comes from the store, not from scratch.** `index.py find "<topic>"` before
Pass 1. Prior `kind=finding` records are **ready-made Pass-3 evidence**, carried with their own
labels and dates. A prior `kind=decision` on the same question is surfaced before re-deciding it —
and if this run overturns it, that is a `supersede`, **not a second opinion left lying beside the
first**.

**Step 3 — six passes into one record.** Pass 1 options (**always including do-nothing/wait**)
and Pass 2 weighted criteria land nothing; Pass 3 evidence per option lands `kind=finding` per
load-bearing fact; Pass 4 score & sensitivity lands `kind=conflict` where the evidence fights;
Pass 5's pre-mortem lands `kind=backtrack` for an option it kills; Pass 6 lands the
**`kind=decision`**.

**The hinge lives in the statement.** A decision recorded without the assumption that flips it
is a decision nobody can audit later; the statement carries, in 1–3 sentences, the pick, the
confidence, the door (two-way / one-way) and the hinge, with `links` naming the findings it rests
on. It is written **after** Pass 6, so it carries the pre-mortem's damage. **SEES** recommendation
+ confidence + door + hinge + the record id, plus `index.py track --kind decision` as the one
command showing every call this project has made.

**Step 4 — attack the front-runner before acting on it.** An argument, plan, dossier or prose
goes to **critic**: `" red team"` · `" poke holes"` · `" stress test"` · `" critique"`; skill-side
`"play devil's advocate"`. Steelman first, then 🔴 fatal / 🟠 serious / 🟡 minor, a disconfirmation
pass, ≥3 genuine alternatives, a fair verdict; `--panel` runs 5 lenses as explicit-Opus lanes.
Anything with an **exit code** goes to **refuter**: `" review this code"` ·
`" code review"` · `" refute"` · `" adversarial review"`; skill-side `"attack this before we
ship"`. The division is mechanical — **a thesis is a critic job; an exit code is a refuter job** —
and the same split governs facts vs arguments: factcheck judges *claims against sources*, critic
judges *arguments and reasoning*, and a piece can be factually clean and logically broken. Chain
them for both.

**Step 5 — the decision spawns work.** `" plan the steps"` · `" how do we migrate"` ·
`" roadmap"` → **stepbystep**; skill-side `"turn this into a plan I can execute"`. Nine passes,
dependency-ordered, a per-step **"done when"**, H/M/L confidence per step, `[ONE-WAY]` and
`[needs expert]` flags, refined by a research→critique loop with a **hard cap of 5 iterations**
and an oscillation guard.

**Step 6 — from plan to keyboard.** `" runbook"` · `" exact commands"` · `" copy paste"` →
**actionplan**; skill-side `"make this copy-paste"`, `"give me the exact steps/code"`. Exact
ordered commands per host, **a verify and a rollback on every step**, ⛔ before destructive ops,
placeholders instead of invented environment specifics (reads an optional `map.md`). It writes; it
never executes. No stepbystep dossier yet? The skill says so and suggests
`/stepbystep` first.

**Step 7 — announce it.** **decider → draft is the canonical pair.** Make the call, then
announce it.

**Alternate — run the whole chain unattended.** `/director` (`"do X then Y then Z"`, e.g.
*"research this, critique it, then plan it"*) reads each stage's `SKILL.md` **from disk** and
performs it — never the Skill tool, so stages stay isolated. One numbered folder per stage, stage
N's output is stage N+1's input, and a `[ ] NN-<skill>` checklist in
`{topic}background.md` is the resume source of truth. For orchestrating **sessions** instead of
skills, that is `fable-director` (J3).

**Unhappy — the pre-mortem kills the front-runner.** Not a failed run: it lands a
`kind=backtrack`/`relation=back` record, the river draws an **upstream loop arrow** back to
something already passed, the decision record names the survivor, and the killed option stays
auditable forever.

**Unhappy — the plan will not converge.** stepbystep hits the 5-iteration cap. **Say it hit the
cap** in the chat summary; never declare a convergence the iteration log does not show.

**Unhappy — refuter comes back CONFIRMED.** refuter **finds, never fixes**, and
`verdict_lint.py <report.md>` exits **5** when a CONFIRMED lacks a fenced command+output. The
finding returns as a numbered repair spec, and the seat resumes the **same** builder lane to apply
it (J3 step 3).

---

## J3 — "A build/ship session"

**Step 0 — discipline arrives before the first prompt · HOOK.** `session-start.sh` echoes both
laws unconditionally, so they are present even when no notrest skill is loaded: *Fable discipline
is active: ORIENT -> PROBE -> ACT -> PROVE -> BANK* (a done/works/fixed claim needs in-transcript
evidence — exit code, diff, status — or say "unverified"), and *HARD RULE — offload: every spawned
agent/Workflow lane sets `model "opus"` explicitly.* `pre-compact.sh` re-anchors the same posture
before auto-compaction, so a long session does not quietly lose it.

**Step 1 — load the contract · INVOKE.** `/fable-mode`, `"work like fable"`, `"fable
discipline"`, `"prove it like fable"` loads the loop, 11 hard rules, the outage playbook and the
verification cookbook. Hard Rule 11 is the offload policy; Hard Rule 12 is the routing law.

**Step 2 — delegate · INVOKE, or by default.** `/agentswarm`, `"swarm this"`, `"offload this"`
— **or by default whenever a session delegates substantial work.** The seat keeps decompose /
judge / apply / gate; everything else goes to background lanes. **MODEL POLICY, non-negotiable:**
every offloaded job sets `model: "opus"` explicitly. No sonnet, no haiku, never `subagent_type:
"fork"` (forks inherit the seat and ignore the model parameter).
**Omitting `model` is a violation, not a default.**

**Step 3 — the seat-builder ritual.** Substantive builds go to **ONE persistent Opus builder
lane per domain**. Feedback rounds **RESUME THE SAME LANE** via SendMessage — never a fresh spawn;
the lane's context of the code it wrote is the token saving. Diagnosis is the opposite shape:
parallel one-shots that finish. Several persistent lanes (one per domain) plus diagnosis fan-outs
plus refuter panels compose freely.

**Step 4 — the receipts write themselves · HOOK.** SubagentStop fires `agent-ledger.sh`: two
appends, flock'd, deduped **at the stop-event key** (five racing deliveries land one line) —
`COORD-AGENTS.md` gets `- [ts] agent=<id> model=<m> bytes=<n> | last: <snippet> | transcript:
<path>`, `spend/ledger.md` gets `[ts] lane=subagent model=<m> tokens=<n> grade=<observed|estimate>
purpose="auto-receipt: …" agent=<id>`, byte-compatible with
`spend.py`'s own writer. **Never hand-log.** The grade is honest: `observed` when the payload
carried a token count, `estimate` otherwise.

**Step 5 — the QC gate.** `brief.py --target <path> --budget 12` mints the refuter brief
(inlines the artifact's bytes and sha, mints the scratch dir, stamps the budget). An
**independent** lane — never the builder — attacks one narrow target up a 6-rung ladder and
returns CONFIRMED / PLAUSIBLE / SURVIVED; `verdict_lint.py` holds the report to that grammar.
Severity order: irreversible-safety > claim-honesty > degrades > cosmetic.

**Step 6 — the ship gate.** `doctor.py check --root .` (exit 0/2/3/5/6) then
`eval.py check --root .` (exit 0/2/5/6), both under `plugins/notrest/skills/<skill>/scripts/`.
**doctor checks the INSTALL; eval checks the LAWS.** Ten checks each, run **exit-code checked —
never piped to `tail`**, which throws the exit code away. doctor's fixtures assert each injected
defect flips exactly its own check; eval's `router-fixture.sh` pipes real `UserPromptSubmit`
payloads through the routing table (14 routes, 5 suppressions, 2 malformed stdin) — the one
behavior fixture in the suite that costs nothing.

**Step 7 — the spend verdict.** `spend.py report [--since] [--json]` exits **4** on a routing
violation. Live policy: any post-2026-07-15 offload lane not on opus is a violation; policy-day
entries are grandfathered (the ledger cannot prove intra-day order); `gpt` / `chatroom-gpt` are
exempt-but-counted. Main-loop totals are not exposed to the model, **and the ledger says so.**

**Step 8 — the estate notices repetition.** `compile.py scan` (zero model tokens) mines COORD
volumes, the agent ledger and spend purposes for the same job done **three or more times**. A ripe
`NEW` candidate surfaces at the **next** SessionStart — the hook reads the last scan, it never
scans. `/compile <slug>` then runs the nine-step ritual (contract from the trail → partition →
builder lane → refuter → gate → fair benchmark → quality law → cost → deliverable) into an
isolated `compile/<slug>/` that stays isolated until the owner ships it.

**Step 9 — close · INVOKE.** `" wrap up"` · `" end session"` · `" handoff"` · `" hand off"` →
**sessionend**. Four files (START-HERE, HANDOFF, STATE, CLAUDE.md merged never clobbered), then
**Phase 3.6 closes the estate**: archivist `scan`, `spend.py report` with the verdict pasted
into HANDOFF (violations **verbatim, never smoothed**), `compile.py scan` with the top ripe slug
named, watch's due rows, a recap's map path, and the COORD close line
`- [UTC] [sessionend] session closed: <outcome> | handoff: START-HERE.md`.

**Scaled up — multi-day, multi-machine.** `/fable-director`, `"3 devs and a relay"`, or a repo
carrying `COORD-<LANE>.md` blackboards: a metered director session, flat dev/QC lanes, per-lane
blackboards, token-watch wakes. The same V4 discipline agentswarm runs — plus the sessions.

**Unhappy — the gate fails.** doctor exit **6** = FAIL and the ship stops; every check prints
**the exact fix command**, and doctor never repairs, never bumps, never commits. eval exit 6
cites `file:line` plus a fix hint.

**Unhappy — a lane rode the wrong model.** `spend.py report` exits 4 and the violation goes into
HANDOFF.md verbatim. Do not re-run the lane and quietly drop the line — the ledger is append-only,
and its whole point is that the policy is **checkable instead of asserted**.

**Unhappy — the session dies mid-build.** `session-end.sh` fires on any termination — clean
exit, `/clear`, crash, closed terminal — appending one `[hook] … auto-cushion …` line to COORD.md
and enforcing the volume law (COORD at 500 lines, COORD-AGENTS at 1000: **sealed whole**, never
compacted). Read the signal in reverse on resume: a cushion line in the tail means the previous
session ended abruptly and its status files may lag the ledger.

---

## J4 — "Help me understand / think with someone else"

**explainer — build the mental model.** `" explain"` · `" why does"` · `" how does"` →
**explainer**; skill-side `"help me understand"`, `"what is X really"`, `"ELI5"`, `"teach me
X"`. A correct mental model, three depth layers (plain → working → expert), the standard
misconceptions, and how to verify the load-bearing claims yourself. **Every analogy states where
it breaks.** For genuine understanding-building — a quick factual question gets answered directly,
not routed here. **LANDS** `understanding/{topic}background.md` + `{topic}Dossier.md`.
**Chains** `/factcheck` to verify the load-bearing claims independently; `/decider` if the
understanding was in service of a choice.

**gpt — a second opinion from outside the house.** `/gpt`, `"ask gpt"`, `"gpt second opinion"`,
`"leave gpt a task"`. First use runs a 2-question guided setup (thinking level, how agentic);
every message after continues the same persistent GPT-5.6 conversation through Codex CLI on the
owner's ChatGPT account, with `--once`, `--task`, `--vs`, `--new`, `--setup` when asked. Two laws:
**opinions are never sources** — everything returns labeled `[model-opinion]` — and
**prompts leave the machine to OpenAI, so no secrets, ever.** `gpt.sh` does the invocation,
parses the echoed token count, and auto-receipts to `spend.py --lane gpt`, so the cross-vendor
lane cannot silently go unlogged.

**chatroom — sessions and models in one room.** `/chatroom`, `"join the chatroom <name>"`,
`"let claude and gpt talk to each other"`. An append-only room file under `~/.claude/chatrooms`
is the wire, armed watches are the wakes, and a gpt-bridge lets GPT read and post like any member.
`room.py join` does read-tail + arm-watch + print the re-arm line **in one call** — the manual
three-step protocol is exactly where sessions go deaf, and a deaf member stalls the room. Since
v3.8.0 the no-secrets law is **code, not prose**: post and bridge paths refuse seven secret
classes (private keys, AWS/OpenAI/GitHub/Slack tokens, credential assignments,
`.env` lines), **exit 5, class named, match never echoed**.

**introspect — measure the self-report, don't trust it.** `/introspect`, `"what are you
thinking right now"`, `"snapshot your workspace"`, `"j-space check"`. The model emits a fast,
unjustified snapshot of the concepts most active in its thinking; `score_snapshot.py` scores that
report against subsequent behavior — verbalized vs silent concepts, predictive lift against a
**context-only control agent** (an explicit-Opus lane), turnover across checkpoints — into an
append-only ledger. **It does not observe internal activations, and it says so** in any
user-facing summary. Sessions are disposable; the ledger is not — it survives rotations and grows
across models, so snapshots from different models on the same task are comparable.

**Unhappy — the bridge refuses.** `room.py post` exits 5 and names the class. **Rewrite the
message. Never route around the screen** — it exists because room content ships verbatim to
another vendor's model.

---

## J5 — "What do we already know / how did we get here?"

**archivist — the content-continuity store.** `/archivist`, `"what do we already know about X"`,
`"show me the session track"`, `"index the dossiers"`; router shape `" what do we already know"`
· `" have we research"`. `index.py track [--session S] [--kind K] [--status live] [--json]` prints
the session's records in `ts` order, one compact line each — `id · kind · relation ·
statement-head · [labels]`, with ` · SUPERSEDED by F-n` inline on a flipped record. `index.py find
"<term>"` matches statements and asks in the store, **then** legacy index entries, **then dossier
bodies** (a term buried in a body used to be invisible). `index.py scan` walks the twelve legacy
output folders for `*Dossier.md`, rewrites `oracle-index.md`, dates each entry from **the
dossier's own date line** when it declares one (a copy rewrites mtime; the document's date is what
the document claims), and adds a pointer entry each for the store,
`COORD-AGENTS.md` and `compile/candidates.md`.

**graph — three views, all script-built.** `/graph`, `"project graph"`, `"/graph river"`,
`"what links to this file"`, `"orphans"`, `"stale files"`, `"all projects graph"`. **`scan`**
draws the file graph (every file and reference — Obsidian for a codebase); **`river`** draws the
journey, reading `archive/findings.jsonl` **plus, always, the COORD volumes and
`COORD-AGENTS.md`** — the overlay is not a fallback, because the ledger is where this estate
already records its milestones; **`links` / `orphans` / `stale`** answer in text over the last
scan, no page to open.

The river's grammar: wide main channel = `relation: toward` · side channel below = `lateral` ·
explicit fork = `kind: side-route` · a channel curving back in = the side route rejoined · a
channel that tapers and stops = **dead end, marked as one** · upstream loop arrow = `relation:
back` · **red rock** = `kind: conflict` or an effectively-refuted record · a stone = every record,
whether or not it led anywhere · flag on the top bank = a COORD line (ship · gate · correction) ·
tick on the bottom bank = a `COORD-AGENTS.md` entry, i.e. which lane was running when · **green
bank on the right = the goal.** **The token-efficiency law:** renders are script-built at zero
model tokens and the model never hand-draws — a picture this skill cannot produce is a missing
subcommand, not a drawing job.

**recap — the story, in prose, with citations.** `/recap`, `"recap the project"`, `"tell me the
story of this project"`, `"what happened here"`; router shape `" recap"` · `" decision story"` ·
`" what happened"`. Walks COORD volumes, `COORD-AGENTS.md`, `TZ=UTC git log`, `spend/ledger.md`
and the dossier folders **in timestamp order** into a narrated timeline, a who-was-consulted
table, ships, costs, and a clickable decision map behind a mandatory render gate. **Every claim
cites a trail line, a commit, or a path; anything without one is `[unverified]`.** The division of
labour, from graph's own chain section: archivist = what the estate *says* · graph = how it
*connects* · **river = how it got here, drawn** · recap = what happened *over time, in prose*.

**watch — the drift log is trail material.** Dated blocks in timestamp order, which a recap
walks alongside COORD and git to show **when the project's facts moved under it**.

**The cross-project view.** `graph.py register --root .` puts this project on the shared map —
offered **once**, on a project's first scan, and never silent, because a registry entry puts this
project on someone else's map. Then `graph.py all` merges every registered project (per-project
cap 300) into the PM view.

**The bookend.** `oracle` at the start (foundation, resume, six questions, route) and
`sessionend` at the close (four files, estate closes, live line to the successor) are one loop:
**the next session's oracle resumes from exactly the files sessionend wrote.**

**Unhappy — the store comes back empty.** **Empty result ≠ never investigated.** The store only
sees what was written under the scanned root. Say where you looked.

**Unhappy — the hit is stale.** **A live record is not "still true."** It is a snapshot of its
`ts`. Re-verify load-bearing `[cited]` claims that could have moved, and **say which ones you
re-verified** — the gap J1's watch step exists to fill.

**Unhappy — no findings store yet.** `graph.py river` degrades to building from the COORD lines
themselves: every node marked `inferred: true`, kind and relation read off the line's own words by
heuristic, links chronological rather than authored, and **the legend on the page says exactly
that**. In that mode the river never claims a supersession — synthesized links are not evidence of
one.

---

## J6 — "Make me something playable"

`/game-forge`, or any casual ask: `"something fun to play"`, *"build a little game about a cat
dodging rain"*, `"a game like X but Y"`. No router shape — this journey is invoke-only.
**Templates, not blank pages**: `assets/engine.html` (browser Canvas, default) or `engine.py`
(pygame), plus references for the loop, juice, audio and four genre playbooks. **Self-contained,
always**: visuals from Canvas/SVG shapes, audio from WebAudio, one file — no external assets or
CDNs, no `localStorage`/`sessionStorage` (unavailable in the artifact sandbox, and they throw),
keyboard **and** pointer/touch with both paths kept. **The playtest is the gate**:
`scripts/playtest.mjs` runs headless Chromium, fails on any console or page error, injects
keys, detects a blank canvas, screenshots, and **exits with a code** — because the named
anti-pattern is *delivering unrun code*, and "it looks right" is not "it runs".

**SEES** the game, plus the playtest's screenshot and exit code. **LANDS** the game file and
its screenshot — **nothing in the estate.** See gap G2.

---

## Coverage matrix — 28 skills

Trigger key: **P** = user phrase · **R** = `router.sh` shape · **O** = oracle intake route ·
**C** = chained from another skill.

| skill | trigger | consumes | produces | chains to |
|---|---|---|---|---|
| oracle | P `hey oracle` · `/oracle` · `resume` | CLAUDE.md · START-HERE.md · COORD tail · index · graph · candidates | COORD `[oracle] intake done: … -> routed to /<skill>` · scaffolded CLAUDE.md | every verb (it routes) · archivist · graph · compile |
| archivist | P `what do we already know about X` · `show me the session track` · R prior-art · O · C researcher/factcheck/decider pre-run | `archive/findings.jsonl` · legacy dossier bodies · COORD-AGENTS · candidates | validated records (`add`) · tombstones · `oracle-index.md` | graph (`track --json`) · researcher · factcheck · decider · refuter |
| researcher | P `find the best X for my situation` · R research (`look into`, `deep dive`) · O | store `find` hit · ~20 searches | `kind=finding` / `conflict` / `backtrack` / `result` records | factcheck · critic · refuter · watch · decider · draft |
| marketresearcher | P `size a market` · R market-sizing (`market size`, `tam `, `competitor`) · O | ~25 searches · two-way sizing inputs | `market-research/` background + opportunity **dossier** | critic · stepbystep · draft |
| factcheck | P `is this true` · `did X really say/do that` · R fact-check · C researcher/explainer | claims verbatim · ~3 searches/claim, ~10-claim cap | one `kind=finding` per claim (verdict first) + `kind=result` headline · `refute` tombstones | watch · critic · researcher |
| watch | P `keep this fresh` · `recheck weekly` · R recheck · C factcheck | `watch/watchlist.md` rows · `F-<id>` or dossier subjects · 2 fetches/claim | drift blocks in `watch/drift-log.md` · updated rows · COORD `[watch]` line | factcheck · researcher · recap · sessionend · archivist |
| explainer | P `help me understand` · `ELI5` · R explanation (`explain`, `why does`, `how does`) · O | the topic · ~8 searches (may honestly be zero) | `understanding/` background + **dossier** | factcheck · decider |
| decider | P `should I…` · `what are the tradeoffs` · R decision · O | store `find` hits as Pass-3 evidence · prior `kind=decision` | `kind=decision` record **with the hinge in the statement** + supporting findings | critic · refuter · researcher · stepbystep · draft |
| critic | P `play devil's advocate` · R red-team (`red team`, `poke holes`, `stress test`) · O · C anything with a thesis | a document, plan, argument, dossier, river dead end | `critique/` background + **dossier**; `--panel` = 5 explicit-Opus lenses | stepbystep · draft · the author |
| refuter | P `attack this before we ship` · R adversarial-review (`code review`, `refute`) · C agentswarm gate step 4 | `brief.py` brief · one narrow target · ~12 tool calls | CONFIRMED (with reproduction) / PLAUSIBLE / SURVIVED report, `verdict_lint.py`-gated | the builder lane (repair spec) · spend · compile |
| stepbystep | P `turn this into a plan I can execute` · R planning (`plan the steps`, `roadmap`) · O · C decider | goal + documents + the decision record | `action-plan/` background + plan **dossier** (done-when, H/M/L, `[ONE-WAY]`) | actionplan · critic · draft |
| actionplan | P `make this copy-paste` · R runbook (`exact commands`) · O · C stepbystep | a stepbystep dossier · optional `map.md` | `runbook/` background + runbook (verify + rollback per step, ⛔) | the operator · draft |
| draft | P `make this sendable` · R outbound (`write the email`, `write the memo`) · C decider/recap/researcher | a dossier, decision, recap · `references/formats.md` budgets | `draft/{slug}background.md` (source-map) + the deliverable, **unsent** | critic (high-stakes) · the owner sends · sessionend |
| director | P `do X then Y then Z` · O several-in-sequence | an ordered skill chain + seed input · each stage's `SKILL.md` from disk | numbered `pipeline/` run folder per stage + summary | every chained skill · the seat |
| agentswarm | P `swarm this` · `offload this` · default on substantial delegation | a decomposed task list · the opus-only policy | background Opus lanes · a persistent builder lane per domain | refuter (gate) · spend · archivist · sessionend |
| fable-mode | P `work like fable` · `prove it like fable` · SessionStart anchor | the session itself | the discipline contract in context (loop + 12 hard rules) | agentswarm · every gate |
| fable-director | P `3 devs and a relay` · a repo holding `COORD-<LANE>.md` | `PLAN-FABLE-DIRECTOR-V4.md` · lane blackboards · token watches | seated lanes · burst agendas · rotation handoffs | agentswarm (single-session sibling) · spend |
| spend | P `audit the model routing` · `spend report` · C SubagentStop hook · sessionend Phase 3.6 | `spend/ledger.md` (hook-fed) | append-only receipts · a verdict line, **exit 4** on violation | sessionend (HANDOFF) · critic · compile · recap |
| compile | P `what should we compile` · SessionStart ripe-candidate nudge · C sessionend scan | COORD volumes · COORD-AGENTS · spend purposes | `compile/candidates.{json,md}` · an isolated `compile/<slug>/` runtime | refuter · critic --panel · spend · recap · archivist |
| doctor | P `health check` · `why isn't X triggering` · C every ship gate | the install, the manifests, the estate, the hooks | 10 PASS/WARN/FAIL lines, each with its fix command; exit 0/2/3/5/6 | eval · the release ritual |
| eval | P `check the laws` · `conformance check` · C every ship gate | the shipped text of every skill, script, hook | 10 static checks citing `file:line` + fix hint; exit 0/2/5/6; `--baseline` diff | doctor · compile · spend |
| recap | P `tell me the story of this project` · R recap (`what happened`) | COORD volumes · COORD-AGENTS · `TZ=UTC git log` · spend · dossier folders | `recap/` background + **dossier** + clickable `map.html` (render-gated) | archivist · critic · sessionend · draft · spend |
| graph | P `project graph` · `/graph river` · `orphans` · C oracle intake | the repo tree · `archive/findings.jsonl` · COORD volumes | `graph/graph.{json,html}` · `graph/river.{json,html}` · CLI query output | critic (dead ends) · refuter (rocks) · stepbystep · explainer |
| sessionend | P `write a handoff` · R handoff (`wrap up`, `end session`) | the session · the estate · spend/compile/archivist/watch outputs | START-HERE · HANDOFF · STATE · merged CLAUDE.md · COORD close line | oracle (the next session) · archivist · spend · compile |
| gpt | P `ask gpt` · `gpt second opinion` · `leave gpt a task` | the prompt (leaves the machine) · the saved profile | `[model-opinion]` answers · `--task` artifacts · a spend receipt | chatroom (bridge) · spend · the seat's judgment |
| chatroom | P `let claude and gpt talk to each other` · `join the chatroom <name>` | room files under `~/.claude/chatrooms` · armed watches | append-only room posts · bridge spend receipts | gpt · watch (the wakes) · state docs |
| introspect | P `what are you thinking right now` · `j-space check` | sealed snapshots · a context-only control lane's output | `score_snapshot.py` JSON + an append-only introspection ledger | factcheck (the interpretation) · researcher · critic |
| game-forge | P `something fun to play` · `a game like X but Y` | a short request · engine templates + genre playbooks | a self-contained playable game + `playtest.mjs` exit code + screenshot | — (see gap G2) |

**Row count: 28.** Every name verified present under `plugins/notrest/skills/`.

---

## Journey gaps

Every line is a mismatch between a journey above and what the tree actually enforces — concrete,
buildable, one line each.

- **G1 — four skills still write dossiers, so their work never enters the river.** `marketresearcher` · `critic` · `explainer` · `recap` write two-file dossiers, so J1's market arm and J2's critic step leave no stone in `graph.py river`. **Build:** rewire each to `index.py add`, as researcher/decider/factcheck already were.
- **G2 — game-forge is the only verb entirely outside the estate.** No record, no COORD line, no spend receipt, no indexed folder: J6 ends with a file and a screenshot and the estate never learns a game was built. **Build:** one `kind=result` record on playtest exit 0, carrying the screenshot path as `type=path` evidence.
- **G3 — `stepbystep` and `actionplan` were never named for store migration.** Their dossiers land in `action-plan/` and `runbook/` and are indexed by `scan`, but a plan and its runbook are invisible to `track`, to the river, and to `--status live`. **Build:** add both to the G1 migration list.
- **G4 — the factcheck→watch handoff is prose.** factcheck's chain line says *"`/watch add` on the confirmed load-bearing claims"* but nothing emits the rows; a human retypes them. **Build:** `watch.py add --from-findings --status live --verdict confirmed`, reading the store directly.
- **G5 — `draft` cannot read the store.** Its stated inputs are "a dossier, decision, or recap", but decider and factcheck now produce **records** — so J1 step 6 and J2 step 7 hand draft a thing that no longer exists. **Build:** teach draft to consume `index.py track --json --kind decision|result` and source-map against record ids.
- **G6 — `recap` does not read `archive/findings.jsonl`.** The estate's newest memory is invisible to the estate's storyteller; recap walks COORD, git, spend and dossier folders only. **Build:** add the store to recap's Step-1 inventory, cited by record id like any other trail line.
- **G7 — a decision resting on a refuted finding is never flagged.** Refute F-3, and a `kind=decision` record whose `links` names F-3 stays `live` with no marker anywhere. **Build:** `track` emits `RESTS-ON-REFUTED F-3` on any record linking an effectively-refuted id, and the river paints that stone's inbound edge red.
- **G8 — the two routing authorities are hand-kept in step.** `router.sh` carries 14 shapes, oracle's routing bullet names 11 targets, and the router's own comment says *"Authority for the table: skills/oracle/SKILL.md — keep in step"* while nothing checks it. **Build:** eval check `ROUTE-TABLE-PARITY` — every router verb appears in oracle's bullet and vice versa.
- **G9 — no skill acknowledges the router.** Fourteen shapes fire nudges into sessions, but no `SKILL.md` names its own shape, so a route can be renamed on one side and drift silently. **Build:** a `router-shape:` line in each routed skill's front matter, asserted by the same check.
- **G10 — `routed to /X` is written but never read.** oracle's COORD intake line is a model-written string; no script parses it, and neither instrument looks for evidence the route was taken. **Build:** eval check `ROUTE-CONFORMANCE` — a `routed to /X` with no later ledger line, record, or agent entry from X is an exit-6 finding.
- **G11 — `"how did we get here"` is a two-owner trigger.** Both `graph` and `recap` claim it verbatim in their descriptions and the router table has no entry for it, so the phrase reaches whichever skill the model picks. **Build:** one router shape naming one owner (river for the drawn answer, recap for the narrated one); cut the phrase from the other.
- **G12 — 14 skills have no router shape.** oracle, agentswarm, chatroom, compile, director, doctor, eval, fable-director, fable-mode, game-forge, gpt, graph, introspect and spend are invoke-only, so J3's whole ship gate and J5's graph views are reachable only by a user who already knows the verb. **Build:** shapes for at least `health check`→doctor, `check the laws`→eval, `project graph`→graph, `spend report`→spend.
- **G13 — `sessionend` never refreshes the graph.** graph's chain line says *"Run the scan at `/sessionend`"*, but Phase 3.6 runs archivist, spend, compile and watch — not `graph.py scan` — so oracle opens on a map the previous close left stale. **Build:** add the scan (and a `river` build) to Phase 3.6.
- **G14 — `director` verifies no handoff.** Its own named failure mode is "the last stage never ran", the `[ ] NN-<skill>` checklist is model-ticked, and there is no per-stage manifest; post-3.8.0 a stage whose skill now writes records leaves an **empty stage folder** while the work really landed. **Build:** `director.py verify` — non-zero on an unticked box, a missing stage output, or an empty stage folder with no matching record ids.
- **G15 — the compile ritual is nine hand-run steps.** Detection is code at zero tokens; every step after it is judgment with no scaffold, which is why J3 step 8 is the longest stretch of the build journey with no exit code in it. **Build:** `compile.py contract --slug S` pre-filled with trail citations, plus a runtime scaffolder.
- **G16 — `introspect` claims an aggregation no script performs.** `/introspect report` is advertised in J4, but the ledger is hand-written markdown and nothing parses it. **Build:** `score_snapshot.py append|report`, refusing trend claims under N=10.
- **G17 — the seat's own spend is never in the ledger.** J3's cost picture is lanes-only, since main-loop totals are not exposed to the model; the ledger says so honestly, but every J3 cost number is still a lane subtotal sitting next to a session. **Build:** a `--seat-estimate` line, graded `estimate`, so the shape of the gap is on the page instead of in the reader's head.
- **G18 — this page has no render.** The token-efficiency law says renders are script-built at zero model tokens and the model never hand-draws, so a journey diagram is **not a drawing job, it is a missing subcommand**. **Build:** `graph.py journey --root .`, reading the router table, oracle's routes and each skill's chain lines into a self-contained flow page, exactly the way `river` reads the store.
