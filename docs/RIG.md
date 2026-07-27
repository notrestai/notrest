# RIG.md — the product spec for rig.rest

Drafted 2026-07-27 against the v3.14.0 tree (HEAD `5fed263`, 29 skills). Decision record:
**F-8** in `archive/findings.jsonl` (`kind=decision`, `status=live`). This is a SPEC — no
code in this document is written yet, and the build starts in a fresh session from the
kickoff payload in section 8.

---

## 1. THE VISION

The owner, 2026-07-27, verbatim:

> "rig.rest is a portal I own: the portal you sign into, and you set up your harness —
> connect models (Claude and ChatGPT for the first build), then you work inside the
> harness: its own features like Claude Code with the monitoring and graph and all the
> features happening inside it. The chatroom core value becomes a reality — you can set
> up your ChatGPT and Claude to work on an idea. If you want to continue mid-session
> with another model, it is easy — all the COORD and methods we use load up the new
> model. And the many other things we built."

**The plugin was the spec and the test-bed; rig.rest is the shell that owns the loop.**
For two and a half days this repo has been building a harness *inside* somebody else's
session loop — anchoring discipline through a SessionStart echo, receipting lanes through
a SubagentStop hook, blocking a bad push through a PreToolUse gate. Every one of those is
a hook because a hook was the only door available. The estate underneath them was never
coupled to that door: `COORD.md` is a markdown ledger, `archive/findings.jsonl` is
newline JSON behind a validator, and all ten instruments are stdlib Python (11,301 lines,
zero third-party imports — grep-verified; the plugin audit found notrest has **zero hard
dependencies**, `docs/PLUGIN-AUDIT-2026-07-26.md`). That is why the port is possible at
all: the laws live in files and exit codes, not in an integration. rig.rest stops
borrowing the loop and runs it, and the harness stops being a passenger.

The honest scope of what that buys: the estate, the instruments, the pictures, the rooms
and the continuity files move over largely unchanged. The loop, the sign-in, the second
vendor and the surface around all of it do not exist in any form and are a real build.
Sections 2 and 6 keep those two lists strictly apart.

---

## 2. THE PORT MAP

Verdicts: **PORTS** = moves as-is, at most a path change · **ADAPTS** = the logic survives,
its *door* changes (a hook event becomes a loop callback, a CLI becomes an API) · **NEW** =
nothing in this tree does this job.

| harness asset (verified path) | rig component | verdict |
|---|---|---|
| `COORD.md` + sealed volumes `COORD-<NNN>.md` (500-line roll, `hooks/session-end.sh`) | the session ledger — one line per prompt, per project | **PORTS** |
| `COORD-AGENTS.md` + `hooks/agent-ledger.sh` auto-receipt (flock'd, idempotent) | the lane index behind the lanes panel | **ADAPTS** — SubagentStop → loop's subagent-completion callback |
| `archive/findings.jsonl` + `archivist/scripts/index.py` (validated at the door, `add`/`track`/`find`) | the knowledge store per project | **PORTS** |
| `index.py library register\|list\|find\|track\|concepts\|update\|crown` (the cross-project shelf, registry `~/.claude/notrest-library`) | the knowledge plane; org-shared at v0.3 | **PORTS** at v0.1 · **ADAPTS** for multi-user |
| `spend/ledger.md` + `spend/scripts/spend.py` (append-only, `report` exits 4 on a routing violation, policy-dated) | the billing meter and the routing gate | **ADAPTS** — add per-connector price tables and a per-account rollup |
| `briefs/agent-<id>.md`, write-once by `O_EXCL` (agent-ledger.sh) | the transparency surface — every commission one click from the UI | **ADAPTS** — same extraction, new event source |
| `doctor/scripts/doctor.py` (10 checks, exit 0/5/6, read-only) | the rig self-check | **ADAPTS** — install/shadow checks become deployment checks; ESTATE/TOKEN/RENDER port |
| `eval/scripts/eval.py` (12 static law checks, 0.12s, zero model tokens) | law conformance over the shipped verbs | **PORTS** |
| `doctor/scripts/pulse.sh` (`--if-stale`, one COORD line, exit 1 on red) | the heartbeat behind the pulse chip | **PORTS** |
| `graph/scripts/graph.py` `scan`/`river`/`journey`/`links`/`orphans`/`stale` (3,341 lines, byte-identical renders) | the pictures, native | **PORTS** |
| `graph/scripts/cockpit.py serve` (1,063 lines, stdlib HTTP, 127.0.0.1:8788) | **the UI seed** — the rig shell is this app grown up | **ADAPTS** — see §3 |
| `chatroom/scripts/room.py` (append-only rooms, flock posts, 7-class secret screen, codex bridge) | the multi-model room | **ADAPTS** — the bridge's transport changes, the room and the screen do not |
| `sessionend` four files: `START-HERE.md` · `HANDOFF.md` · `STATE.md` · `CLAUDE.md` | **the model-switch payload** | **PORTS** |
| `oracle` intake (six questions, resume offer, routing) | new-session / new-project onboarding | **PORTS** |
| `beam/scripts/beam.py` (checkpoint → `refs/heads/beam/<ts>` → respawn → recall) | estate transport; the tenancy seed | **ADAPTS** — see §5 |
| `hooks/router.sh` (18 verbs, UserPromptSubmit, ≤160-char nudge) | in-loop routing policy | **ADAPTS** — hook → loop's pre-turn callback |
| `hooks/session-start.sh` (identity line + discipline + offload law) | system-context injection at loop construction | **ADAPTS** — stdout echo → `systemPrompt` append |
| `hooks/pretool-gate.sh` (PreToolUse **hard block**, exit 2, fail-open) | the policy engine | **ADAPTS** — same rules, SDK's tool-permission callback |
| `watch/scripts/watch.py` (HTTP probe + sha baselines, zero-token STANDS/DRIFTED/DEAD-SOURCE) | the freshness engine | **PORTS** |
| `compile/scripts/compile.py` (repeat-work scanner, 18 candidates today) | same | **PORTS** |
| the 29 skills (`SKILL.md` + `scripts/`) | the rig's verbs, exposed as tools | **PORTS** |
| — | **auth / the portal you sign into** | **NEW** |
| — | **session-loop hosting** (Claude side, via claude-agent-sdk) | **NEW** |
| — | **the OpenAI connector** (product-grade, API) | **NEW** |
| — | **UI shell beyond one page** (multi-session, project switcher, editor) | **NEW** |
| — | **key management** (BYO keys at rest) | **NEW** |
| — | **packaging** (install, update, run-as-app) | **NEW** |
| — | **per-user estate isolation / tenancy** (v0.2) | **NEW** |

**Count: 21 existing assets — 10 PORT, 10 ADAPT, 1 both (the library: ports at v0.1,
adapts for multi-user) — against 7 NEW components.**

**Be honest about where the line falls.** Everything *below the loop* is files plus stdlib
scripts plus exit codes, and it ports. Everything *at and above the loop* — the loop
itself, who you are, the second vendor, and the surface — is new. The 21-vs-7 split is
flattering to the port only if you count assets; by engineering effort the seven NEW
components are the whole first release (§6 tiers them). The port's real value is not that
it saves the most hours: it is that **every law that survived a fixture here arrives
already proven**, and none of the harness's honesty has to be re-argued.

---

## 3. ARCHITECTURE — v0.1, LOCAL-FIRST

F-8's hinge, verbatim from the record: *"v0.1 ships local-first (the portal shell on the
owner machine, BYO keys, single tenant) before any hosted multi-user build."* Nothing in
this section requires a server, a database, or an account.

### 3.1 The shell — the cockpit grown up

`cockpit.py` already is the shape: one page, stdlib `ThreadingHTTPServer`, bound to
`127.0.0.1` with **no flag that widens the bind**, serving a status bar, three
self-rebuilding pictures and five live feeds off the estate's own files. It also already
carries the law the product needs:

> **THE WINDOW-NOT-CONTROL-PANEL LAW.** Every route is a read except exactly one:
> `POST /room/<name>` … the cockpit adds no gate and bypasses none.
> (`skills/graph/SKILL.md`)

v0.1 keeps the law and adds exactly one class of write: **starting and feeding a session.**
The shell becomes three panes over the same file-watching core.

- **Session panel** — start a session in a project dir, see its turns, type into it. This
  is the new surface; everything it displays is already produced by the loop below it.
- **Pictures** — the existing `/pic/{river,journey,graph}.html` tabs, unchanged. Renders
  stay byte-identical and deterministic; the *page* is live. That distinction is already
  written down and already fixture-proven (60/0), and it must not be softened.
- **Feeds** — COORD tail, lanes & commissions (each with its banked prompt one click
  away), library concepts, chatroom, findings. Unchanged.

Everything the shell shows about a running session it reads from the estate, not from the
loop's memory. That is the property that makes the monitoring free: `cockpit.py`'s own
SKILL.md says *"a session running in this repo appears in the window within five seconds
without knowing the window exists."* Keep that. A session that must report to the UI is a
session that can lie to it.

### 3.2 The Claude loop — claude-agent-sdk

The V3 vector in `docs/CAPABILITIES.md` already names the path: *"a minimal
claude-agent-sdk app that boots with the laws injected, the estate mounted, and one verb
end-to-end."* v0.1 is that app, wired to the shell.

- **The laws are system context.** `hooks/session-start.sh` echoes the identity line, the
  Fable discipline anchor, and the offload law into every session as stdout. In the SDK
  those become an appended system prompt built at loop construction — same text, no hook.
- **The estate is the working directory.** The loop runs with cwd = the project dir, so
  `COORD.md`, `archive/findings.jsonl`, `spend/ledger.md`, `briefs/` and `graph/` are just
  files it writes, exactly as today. No estate API, no daemon, no sync.
- **Skills are tools.** Each `SKILL.md` is a prompt-side contract whose load-bearing parts
  are already exit-code scripts by design — `index.py add` validates a record at the door,
  `doctor.py` returns 0/5/6, `spend.py report` returns 4 on a routing violation,
  `room.py post` returns 5 on a secret. A tool wrapper over a script that already owns its
  own refusal is a thin wrapper. This is not luck; it is the token-efficiency law
  ("script owns procedure, the model keeps only judgment") paying its second dividend.
- **Hooks become loop policy.** `router.sh` is a pre-turn callback, `agent-ledger.sh` is a
  subagent-completion callback, `pretool-gate.sh` is a tool-permission callback. Each keeps
  its fail-open discipline — *"a broken gate must never brick the machine"* (pretool-gate
  header). **[unverified]** — that the SDK exposes each of these three points with the
  fidelity the current hooks assume is the single largest technical unknown in v0.1, and
  proving it is spike task 1 in §8, not an assumption in this document.

### 3.3 The ChatGPT side — an API bridge, and where the line is

Today `room.py` reaches GPT through `codex_call()` (line 224): it shells to `codex exec`,
OpenAI's own CLI, authenticated against **the owner's own ChatGPT plan**, in an empty
`.gptwork` subdir, with the answer parsed from the `\ncodex\n` marker and the token count
receipted to `spend.py --lane chatroom-gpt`. On the owner's machine, for the owner, that
is a person using their own subscription through the vendor's own tool.

**It is not a product connector, and v0.1 must not pretend otherwise.** The moment rig.rest
ships to a second person, "the bridge" would mean automating *someone else's* consumer
ChatGPT account — logging in on their behalf, driving a subscription UI, or shipping their
plan credentials through our process. That is the line, and it is a hard one:

> **rig.rest connects to OpenAI through the official OpenAI API with a key the user
> supplies. No consumer-account automation, no credential relay, no headless sign-in to
> chatgpt.com — not as a fallback, not as a "power user" option.**

So v0.1's OpenAI connector is a **promotion of the codex pattern, not a port of it**: the
same room protocol, the same cursor, the same 4-posts-per-minute throttle, the same
`[model-opinion]` labelling, the same spend receipt — with `codex exec` replaced by an HTTPS
call to the official API carrying the user's own key. `room.py`'s structure survives whole;
one function's body changes. Consequences to write into the connector's own docs: the user
pays OpenAI directly for API usage (a ChatGPT Plus subscription does not cover it), and
the local `codex` path may remain as an owner-machine developer convenience but is never
what a signed-in user gets.

### 3.4 The invariants for v0.1

- **Estates are per-project directories, exactly as today.** A project is a folder with a
  `COORD.md` in it. No import step, no migration, no database. A user who already has this
  repo checked out is already a rig user.
- **BYO keys.** Anthropic key and OpenAI key, supplied by the user, stored by the OS
  keychain where one exists and a `0600` file where one does not. Never in the estate,
  never in a room, never in a render. The `.gitignore` anchors that already keep derived
  output out of git are the precedent to extend.
- **Single tenant, loopback only.** No account, no server, no listener beyond `127.0.0.1`.
  Auth (§5) is what changes this, and it is deliberately not in v0.1.
- **The no-secrets screen sits at every cross-vendor boundary.** `room.py`'s screen already
  refuses on 7 classes with exit 5 and never echoes the matched text. Whatever the OpenAI
  connector sends passes the same function — imported, not copied. The cockpit already
  demonstrates the discipline: its 422 *is* room.py's exit 5.

---

## 4. THE THREE SIGNATURE FLOWS

### (a) Two models on one idea

**What the user does:** opens a project, clicks *Room*, names it, picks members — their
Claude session and GPT. Types the idea.

**What happens.** `room.py create` mints `rooms/<name>/room.md`, append-only, flock-atomic
through the script only. The Claude loop joins with `room.py join <room> --handle claude`
— which prints the tail, arms the watch and prints the re-arm line *in one call*, because
the manual three-step version is *"exactly where sessions go deaf"* (`docs/CAPABILITIES.md`,
the chatroom entry that commissioned `join`). The
OpenAI connector holds a cursor over the same file and answers when `@gpt` is mentioned.
The human is a third member typing into the shell's room pane — the mail slot the cockpit
already ships.

**What the estate records, with nobody remembering to log anything:** every post is in
`room.md` with its author and timestamp; every GPT call is receipted to `spend.py --lane
chatroom-gpt` graded `observed` when the API returns a token count and `estimate` when it
does not; every load-bearing outcome the session decides to keep goes to `index.py add` as
a validated record with its evidence. The **river** (`graph.py river`) then draws both
models' contributions as stones in one channel, because the river reads the findings store
and the COORD volumes and neither has a "which vendor" column — the picture was
multi-model before there was a second model in it.

**Done when:** two vendors have posted to one room file, the spend report shows both lanes,
and the river renders the session with both contributions and stays byte-identical on
re-render.

### (b) Mid-session model continuation — the "switch model" button

**What the user does:** clicks *Continue with…* and picks the other model. That is the
whole interaction.

**What happens — three steps, all of which already exist:**

1. **Bank.** Run `sessionend`'s Phase 3–3.6 against the live session: write
   `START-HERE.md` (ordered resume instructions), `HANDOFF.md` (volatile status),
   `STATE.md` (append-only decisions), merge `CLAUDE.md` (the foundation, *never*
   clobbered), then the estate closes — archivist scan, spend report, compile scan, graph
   refresh, one COORD close line.
2. **Verify.** sessionend's own bar is that *"a memoryless session could resume from them
   alone"* (its front-matter description). The button enforces it rather than trusting it:
   every path and command cited in `START-HERE.md` is grepped against the tree, and a dead
   reference blocks the switch. (This is the `sessionend verify` mode already designed in
   `CAPABILITIES.md`; the button is its first real consumer.)
3. **Boot.** Start the other model's loop in the same project dir with the same laws in
   system context and one instruction: read `START-HERE.md` and follow it. Its read order
   already routes through the COORD tail, and the rule is already written: *"when my prose
   and the ledger disagree, the ledger wins: it was written when the work landed"*
   (`sessionend/references/live-handoff-template.md`).

**Why this works — and exactly how far the proof goes.** The four files were built
model-agnostic by construction: they name no model, no vendor and no context window, and
the plugin's own manifest states the design goal that *the trail survives "compaction,
crashes and model changes."* The mechanism is load-bearing and exercised daily — this
repo's active COORD volume carries 13 `[hook] session ended without /sessionend —
auto-cushion` lines and a `RESTART LANDED` entry at `2026-07-27 02:40Z` where the session
picked back up from the estate after an app restart. **Honest limit: every resume on record has been
Claude→Claude.** A cold boot of a *non-Claude* model from these files has never been run,
so "loads up the new model" is `[unverified]` until flow (b) runs end-to-end. It is
therefore the v0.1 acceptance test, not a v0.1 claim.

**Done when:** a GPT-side loop, given only `START-HERE.md` and the project dir, states the
current version, the last three ledger entries and the next step, and its first action
matches what the Claude session was about to do.

### (c) Always-on monitoring

**Already live.** `cockpit.py serve` shipped in v3.14.0 with a 60/0 fixture. The port is
UI work, not mechanism work: five status chips (pulse verdict, version + HEAD, spend
verdict, watch-due count, lane activity), three picture tabs that rebuild only when their
input mtimes move and never more than once per 5 seconds, five feeds.

Two honesty properties come with it and must survive contact with a product designer:

- **The lane chip counts lanes that *finished* in the last 60 minutes, not lanes running,**
  because the agent ledger is written at stop time and a working lane is in no file the
  cockpit can read. The chip says so in its tooltip. In rig the loop *does* know what is
  running — so the chip may become truthful, but only by reading the loop's own state and
  saying which source it used. It must never quietly relabel the 60-minute count as "now."
- **The staleness stamp comes from the `X-Cockpit-Generated` response header, never the
  browser clock** — a viewer with a skewed clock cannot make the page lie about freshness.

---

## 5. v0.2 / v0.3 STAGING

**v0.2 — hosted rig.rest.** Auth and tenancy, which is where `beam` generalizes: it
already solves "move a unit of work to a machine that isn't this one" with plain files on
a git ref, and its transport laws are scars, not theory — *untracked files never travel*,
*prompts are context-bounded but repositories are not*, *the far side lands on the wrong
branch by default*, *the harness does not travel by itself* (`beam/SKILL.md`). A per-user
hosted estate is that payload with an owner column. Two product requirements are promoted
directly from incidents, and neither is negotiable:

- **The runtime always announces itself.** Four shadow reinstalls (F-1, F-5, F-6; concept
  C-1) happened because a UI did not list a runtime that was in fact loaded, so the owner
  reinstalled it looking for it. The fix shipped as one line in every session — version,
  where it is loaded from, and the command to verify. rig.rest shows, always and
  unprompted: which model, which key, which estate, which version.
- **Commissions are always visible.** Not a debug view, not a settings toggle.

**v0.3 — team rooms.** The room file is already multi-writer-safe through the script
(flock), already append-only, and already has a no-secrets screen at the boundary. Team
rooms are the same file with more members and an access rule. The etiquette section is
already written and is genuinely load-bearing at more than two members.

**v0.3 — the library as a shared knowledge plane.** `index.py library` already does
cross-project `find`/`track`, `concepts --rebuild` (clustering donor-imported from
`compile.py`, never reimplemented), `update` (re-probe url evidence at zero model tokens),
and `crown` (record a convergence, with refusals, and *a crown buys no immunity*). Point
the registry at an org shelf and concepts cluster across *users* instead of across
projects. The known seam is on record and must be closed before this ships to teams:
cross-project RESTS-ON-REFUTED walks record evidence one hop — deeper chains are not yet
followed.

**v0.3 — a marketplace of harness laws.** The plugin already *is* a marketplace entry, and
`eval.py` already proves conformance to a law set in 0.12s at zero model tokens. A
published law set that a user can install and that the rig can *verify* is a product only
because the verifier exists first. Do not ship the marketplace before the verifier runs
against third-party law sets.

---

## 6. WHAT IS GENUINELY NEW

No self-deception: nothing in this list has a donor in the tree. Tiers are relative effort
(**S** ≈ days · **M** ≈ weeks · **L** ≈ months), no dates.

| # | piece | why nothing donates | tier |
|---|---|---|---|
| N1 | **Session-loop hosting** — constructing, running, streaming, interrupting and persisting a claude-agent-sdk loop | the harness has always been a passenger in someone else's loop | **L** |
| N2 | **UI shell beyond one page** — multi-session, project switcher, transcript view, input, editor | `cockpit.py` is one read-only page with one mail slot | **L** |
| N3 | **The OpenAI connector** — official API, streaming, tool-use parity, error taxonomy, throttle | `codex_call()` is 29 lines shelling to a local CLI on the owner's own plan | **M** |
| N4 | **Auth / the portal** — sign-in, sessions, account state | v0.1 has no concept of a user | **M** (v0.2; **L** with tenancy) |
| N5 | **Key management** — BYO keys at rest, keychain integration, rotation, never-in-estate | keys have never been stored, only read from the environment | **M** |
| N6 | **Packaging** — install, update, run-as-app, first-run setup | today's install is a git clone and a symlink | **M** |
| N7 | **Per-user estate isolation** — tenancy boundaries, quotas, deletion | `beam` moves an estate; it does not fence one | **L** (v0.2) |
| N8 | **Loop-aware policy adapters** — the three hooks re-expressed as SDK callbacks | the *rules* port; the wiring does not, and §3.2 flags it `[unverified]` | **S** |
| N9 | **Connector-aware spend** — per-vendor price tables and per-account rollup | `spend.py` counts tokens and grades routing; it has never priced anything | **S** |

The shortest honest summary: **the harness ports, the product does not exist yet.**

---

## 7. RISKS, AND THE LAWS THAT TRAVEL

Each of these is already a law here. In rig.rest each becomes a **product requirement**,
because a law that only holds when a careful seat is watching is not a law.

- **Commission transparency (owner, 2026-07-27).** Verbatim in `agentswarm/SKILL.md`:
  *"the commission is never hidden — named at dispatch, banked on disk, marked in the
  pictures."* In the product: every agent's exact prompt is banked write-once (`O_EXCL`)
  and reachable from the UI in one click, and a brief that narrows the owner's ask says so
  in its first lines (fable-mode 12a). **Risk if dropped:** the exact failure that created
  the law — a lane silently narrowed the owner's ask and it took cross-examination to
  surface (F-7).
- **Honesty chips.** A UI that cannot know something must say so where the number is, not
  in a footnote. The lane chip's "N in 60m" and the header-clock stamp are the shipped
  examples. **Risk:** a designer "cleans up" a caveat and the page starts lying at a
  glance.
- **Window, not control panel — for observers.** Read-only is the default surface. The
  cockpit's single write is the chatroom post, through chatroom's own screen. In rig the
  session panel is a second write and must be *scoped by role*: watching a session and
  driving one are different permissions. **Risk:** a monitoring URL that can also fire a
  ship.
- **The no-secrets screen at every cross-vendor boundary.** The screen is imported, never
  copied — `cockpit.py` shells to `room.py post` precisely so there is one screen. Its own
  documented limit stays in the product copy: *"a floor, not a guarantee — it catches
  shapes, not judgment."* **Risk:** a second connector with its own inlined check that
  drifts from the first.
- **Zero-token renders.** *"a new visualization is a new script subcommand"* (graph
  SKILL.md, owner 2026-07-25). Renders stay deterministic and byte-identical; the live
  page is a declared exception with a stated reason. **Risk:** a product asks the model to
  draw a chart, and every dashboard load starts costing inference.
- **Fail-open policy, fail-closed secrets.** The gate never bricks the machine
  (`pretool-gate.sh` exits 0 on every unexpected path); the secret screen refuses and stops
  (a refusal in a standing bridge halts it *on purpose*). These two defaults point in
  opposite directions deliberately — keep them that way.
- **The estate is the source of truth, not the UI.** The ledger wins over prose because it
  was written when the work landed. A product feature that records state *only* in the app
  breaks every resume, every picture and every audit downstream.

**Two risks that are new to the product and have no law yet.** (i) *Vendor coupling* — the
whole port rests on the estate being files; the first feature that stores session state in
a service instead of a directory quietly ends the property that made this possible.
(ii) *Cost surface* — today the owner pays two vendors directly and `spend.py` audits
routing; the moment rig.rest holds keys or resells inference, metering becomes a
correctness problem with a bill attached, and N9 is the smallest honest starting point.

---

## 8. KICKOFF PAYLOAD

Paste this into a fresh session to start the build.

```
Repo: /Users/ethanabot/Desktop/oracle-suite-plugin  (branch main)
Build: rig.rest v0.1 — LOCAL-FIRST. Read, in this order:

  1. docs/RIG.md                      — this spec (vision, port map, architecture, flows)
  2. archive/findings.jsonl → F-8     — the decision record and its hinge
  3. docs/CAPABILITIES.md             — the register; the V3 vector is the port path
  4. plugins/notrest/skills/graph/scripts/cockpit.py         — the UI seed (1,063 lines)
  5. plugins/notrest/skills/graph/SKILL.md § "/graph cockpit" — the window-not-control-panel law
  6. plugins/notrest/skills/chatroom/scripts/room.py          — rooms + the 7-class secret screen
  7. plugins/notrest/skills/sessionend/SKILL.md                — the model-switch machinery
  8. plugins/notrest/hooks/{session-start,router,pretool-gate,agent-ledger}.sh — laws as policy

Session discipline: /fable-mode. Offload: /agentswarm, every lane model:"opus", never a
fork. Ledger every substantive prompt to COORD.md. Ship gate: doctor.py check + eval.py
check both green, commit and push as two separately gated acts.

The first three tasks of v0.1, in order:

  T1 — THE SPIKE (proves or kills §3.2's [unverified]).
       A minimal claude-agent-sdk app that boots in a project dir with (a) the
       session-start.sh laws as appended system context, (b) the estate as cwd, and
       (c) ONE verb end-to-end: run researcher, write a record via index.py add, and
       have graph.py river draw it. Then prove all three policy points attach:
       pre-turn (router), tool-permission (pretool-gate), subagent-completion
       (agent-ledger). Return an exit-coded report per point: ATTACHES / DOES-NOT /
       ATTACHES-DIFFERENTLY-AND-HERE-IS-HOW. This gates T2 and T3.

  T2 — THE SHELL. Grow cockpit.py into the rig shell: keep every read route and the
       single chatroom mail slot untouched, add a session pane (start a session in a
       project dir, stream its turns, send input). Loopback-only stays; no flag widens
       the bind. Fixture parity or better — the cockpit ships at 60/0 today.

  T3 — THE CONNECTOR. Promote room.py's bridge from `codex exec` to the official
       OpenAI API with a user-supplied key: same room protocol, same cursor, same
       throttle, same [model-opinion] label, same spend receipt, same imported secret
       screen. No consumer-account automation of any kind — API keys only. Fixture must
       assert the screen refuses BEFORE any network call (the current fixture proves
       "nothing was sent" with a stub on PATH; keep that technique).

Acceptance test for v0.1 (flow (b), the one thing never proven): a GPT-side loop, given
only START-HERE.md and the project dir, states the current version, the last three ledger
entries and the next step, and its first action matches what the Claude session was about
to do. Until that runs, "loads up the new model" stays labelled [unverified].
```

---

*Instruments at the time of writing, on this tree plus this file: `doctor.py check --root .`
→ HEALTHY, 10 checks, 10 pass, exit 0. `eval.py check --root .` → PASS, 29 skills, 12
checks, 0 fail, exit 0.*
