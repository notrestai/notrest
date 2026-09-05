# MAP.md — the complete notrest plugin map

**Version mapped:** v4.7.1 (`plugins/notrest/.claude-plugin/plugin.json`), commit: the v4.7.1 release commit (`git log -1 --grep "v4.7.1"`).
**Mapped:** 2026-09-01, by probing the live tree — every claim below comes from a file read
or a command run during the mapping session. Nothing here is recalled.

**What notrest is, in one paragraph.** It is a Claude Code plugin that turns a project into
an *estate*: a directory that keeps its own written record of what happened in it. Lifecycle
hooks write that record automatically, at zero cost to the model. Skills are named verbs the
session can invoke. Instruments are small read-only scripts that answer questions about the
estate without asking the model anything. The design principle repeated everywhere: **the
machine writes, the session pays nothing, and a claim without evidence is labeled unverified.**

**Counts in this map:** 11 hooks · 1 hook-adjacent checker · 22 skills that own scripts
(≈50 runnable tools) · 32 skills · 8 estate files.

---

## 1. Hooks — 11 scripts

Hooks are shell scripts the Claude Code harness runs at fixed moments. Nine are wired to
lifecycle events in `plugins/notrest/hooks/hooks.json`. Two are shared helpers other hooks
call. **Every wired command now declares its own `timeout`** (4.6.2) — 10 s to 300 s, sized per
hook — and the field sits on the **command object**, not on the matcher group, which is where
the documented schema reads it; before this, only `Stop` was bounded and the rest rode the CLI
default. Verified by parse, not by eye: group-level `timeout` is `None` on all eight groups. All eleven follow the same house law, asserted by `eval.py`'s HOOK-CONTRACT check:
**no `set -e`, always exit 0, silent on failure.** A hook that breaks must never break a
session.

### Wired to lifecycle events

**1. `session-start.sh` — SessionStart**
Runs once when a session opens. It is the estate's welcome desk: it prints who's installed,
what the standing rules are, and what the project already knows.
- **Writes:** `COORD.md` at the repo root if a git-backed estate has none (scaffolded with a
  header plus one `[hook]` ledger line). Also fires a detached `git pull --ff-only` on the
  plugin's own clone. Everything else is echo only.
- **Echoes (stdout is injected as session context):** the installed version and runtime
  (`v4.5.0 @skills-dir`); the Fable discipline anchor (ORIENT → PROBE → ACT → PROVE → BANK);
  the offload model rule; a resume nudge if `START-HERE.md` or `HANDOFF.md` exists; the pulse
  reading (`doctor=… eval=… swarm=… compile=…` plus how long ago it refreshed); the top ripe
  compile candidate; a cockpit line if the project opted always-on; a fable-director line if
  lane blackboards exist. Where the owner has opted in, that compile line is a **directive**
  rather than a nudge — *dispatch ONE opus builder lane this session for ripe candidate
  `<slug>`* — and it says in the same breath that the runtime is isolated, benchmarked,
  receipted and **never installed**. Two authorization guards ride with it: an opt-in store
  that resolves *inside* the estate is **IGNORED** with the reason (an in-estate marker is
  writable by any lane and travels with a clone, so it is not the owner's private
  authorization), and a legacy `compile/.auto-build` with no marker beside it gets a one-line
  **IGNORED-since-v4.5** notice naming the re-authorization command. It also **sweeps
  `gates/ACTIVE.md` sections older than 24 h** — a lane that died without stopping cleanly
  leaves its gates armed forever — recording each removal as a `COORD-AGENTS.md` row
  `gates SWEPT lane=<key>`, and deleting a file that is nothing but an empty husk — the silent lapse that
  sent this estate back to nudging for weeks after it had already opted in.
- **Safety property:** *never does work.* It reads the last background readings rather than
  refreshing them, because a SessionStart hook that shells out is a hook that can hang a
  session start. It also refuses to scaffold in a non-git directory — establishing an estate
  is `/notrest`'s deliberate act, never a hook's side effect.

**2. `session-end.sh` — SessionEnd**
Runs when a session terminates *however* it terminates — clean exit, `/clear`, crash, closed
terminal. The estate's crash cushion.
- **Writes:** two things. (a) If the session did not close deliberately with `/sessionend`, one
  line appended to `COORD.md` saying so and pointing the successor at the tail. (b) The
  **volume roll**: past ~500 ledger lines the whole active `COORD.md` is sealed byte-identical
  as the next `COORD-<NNN>.md` and a fresh active file continues (`COORD-AGENTS.md` at 1000).
- **Safety property:** silent on success *and* on every failure, always exit 0, whole body
  wrapped. The seal is crash-ordered: the sealed copy is written and fsync'd first, so an
  interruption leaves a complete copy beside an untouched original — never a lost line.

**3. `coord-nudge.sh` — UserPromptSubmit**
Fires on every prompt. Three cheap jobs: remind the session to append a ledger line when the
work lands; act as the pulse's heartbeat; surface swarm alerts.
- **Writes:** echo only. It *triggers* a detached `estate-pulse.sh` refresh when `pulse/pulse.json`
  is missing or older than 30 minutes.
- **Safety property:** token-cheap by construction (it fires on *every* prompt), and the
  pulse kick is detached so the prompt never waits on it.

**4. `router.sh` — UserPromptSubmit**
The routing law's enforcer. It reads the prompt, matches its shape against an ordered table,
and suggests the suite verb that owns that shape — one line, under 160 characters.
- **Writes:** echo only, **at most one line, ever**. Since 4.7.0 that line may instead be a
  banked lesson — `[notrest] a banked lesson applies: L-n … (all of them: /notrest:archivist
  learnings --scope <token>)`, an **accepted** one only, never a lane's proposal — and only on the paths where a route nudge would not have
  spoken anyway: no route matched, or the prompt already names its verb. The miss path stays
  fork-free: it reaches for the store only when the prompt carries a path-like token or a
  skill name *and* `archive/findings.jsonl` exists, because this fires on every prompt.
- **Safety property:** it stays silent when the prompt is a slash command, already names a
  suite verb, or is under four words (greetings are not task shapes). The table is a plain
  greppable `case` chain on purpose, so `eval.py` can check it against `oracle`'s routing
  bullet — verified live: **19 verbs, agreeing across both files.**

**5. `spawn-gate.sh` — PreToolUse, matcher `Agent|Task`**
The offload law, enforced in code rather than asked for in prose. It inspects an
agent-spawn call before it runs and refuses an unlawful one.
- **Writes:** echo only (stderr on a block; a loud stderr receipt on an override).
- **Blocks:** `subagent_type="fork"` (a fork inherits the seat and bills its credit, so it is
  not an offload); an omitted `model`; any model other than explicit `opus` or `sonnet`.
- **Also rewrites (4.7.0):** on a call it *allows*, it appends the **scoped LEARNINGS digest**
  to the lane's prompt via `hookSpecificOutput.updatedInput` — scope tokens read out of the
  brief (path-like substrings, known skill names), the digest read from `index.py learnings`.
  It is the **only** hook permitted to touch the `Agent` prompt, because when several
  PreToolUse hooks rewrite one input the last writer wins. A denied call is never rewritten.
- **Also arms (4.7.0):** an explicitly marked block in the Agent prompt (`NOTREST-GATES:` … `END-GATES` at column 0, never inside a code fence at any indent) — starting at
  column 0, ending at the first blank line, because a fenced block is documentation — is
  written to `gates/ACTIVE.md` as `## lane <8-hex key> · opened <UTC>`, each line under
  `# lane <key> · from the commission's DONE-WHEN block`. The file is created if absent and no
  other section is ever rewritten. The key is random, and the gate appends it to the prompt
  tail as `[notrest lane-key: <key>]` so the lane can see the contract it is under.
  `agent-ledger.sh` retires the section **by key** when the lane stops; a red reads
  `RED: lane <key> gate N — exit=…`.
- **Safety property:** `NOTREST_GATE_OVERRIDE=1` permits, but *loudly* — a bypassed gate that
  says nothing is worse than no gate. Any malformed payload passes through silently.

**6. `pretool-gate.sh` — PreToolUse, matcher `Bash`**
The hard gate. Two rules, both descended from real incidents on this machine.
- **RULE 1 · SHIP GATE** — refuses `git push` out of the harness repo while `doctor` or `eval`
  is red.
- **RULE 2 · SHADOW GUARD** — refuses the consumer install flow on this machine, because an
  installed `notrest@notrest` takes the name and silently shadows the live skills-dir runtime.
- **Writes:** echo only. Blocks with exit 2 (stderr becomes the model's reason) *and* a
  `permissionDecision:"deny"` on stdout — belt and braces.
- **Safety property:** fail-open plus a fast path. The miss path is one builtin read and one
  `case` — no fork, no python, no git — because this fires on every Bash call on the machine.

**7. `pre-compact.sh` — PreCompact, matcher `auto`**
Fires when context is about to auto-compact.
- **Writes:** echo only, one sentence: run `/sessionend` if the session is near its end, and
  either way append a COORD line first, because the ledger survives compaction.
- **Safety property:** it is a single `echo` and an `exit 0`. Nothing to break.

**8. `agent-ledger.sh` — SubagentStop**
Fires when a subagent finishes. The estate's auto-index for delegated work, at zero model
tokens.
- **Writes:** three things. (a) One line per finished lane into `COORD-AGENTS.md` (which agent,
  what it concluded, where its transcript lives). (b) The lane's verbatim commission prompt to
  `briefs/agent-<id>.md` — this is what makes commission transparency structural rather than
  a promise. (c) A spend receipt appended to `spend/ledger.md`, deduplicated, so hand-logging
  is never needed. It then fires a detached pulse refresh.
- **Safety property:** silent on success and on every failure; all shared-file writes go
  through `fcntl.flock` (shell `flock` one-liners aren't reliable on macOS); the append is
  idempotent, so a re-fired hook does not double-count.
- **Also banks (4.7.0):** the lane's **return card**. A return ending in the fixed
  `TESTS / OPEN / FINDINGS / LEARNINGS` block is parsed and each checkbox line is written to
  the findings store through `index.py add`, with `lane:<id>` as `source` and the banked brief
  as evidence — so a lane that wrote its card has banked its work by construction. The judgment
  kinds land **`status=proposed`** (the door refuses a lane-sourced learning/open/alternative
  claiming otherwise) and travel nowhere until the seat runs `index.py accept` or `reject
  --why`; tests and findings are ungated data. A malformed card **banks nothing** and says so in
  the `COORD-AGENTS.md` row — though a header whose count disagrees with its items is *reported,
  not refused*, a miscount being no corruption. It also retires the lane's `gates/ACTIVE.md`
  section by key.

**9. `completion-gate.sh` — Stop (timeout 60s)**
The newest gate (v4.5). The estate already gates the *ship* and the *spawn*; this closes the
hole between them — **the claim**. It stops a session from declaring work done while the very
checks the commission named are red.
- **Contract:** the estate declares its gates in one file, `gates/ACTIVE.md`, in the
  `CHECK:` / `EXPECT:` format `gate-check.py` runs. **No `gates/ACTIVE.md` → that half of the
  hook does nothing at all, in every repo on the machine** — a gate that arms itself is a gate
  nobody chose.
- **Second rule (4.7.0) — the lesson.** After the gates check, it looks for **trigger** lines
  in the active COORD volume — a correction, a refuter defect, a `RED:`, a `HALTED` — newer
  than the newest banked learning, and blocks a "done" that leaves one uncited. The block
  names the trigger's timestamp and hands back the exact `index.py add --kind learning …`
  command. It reads its trigger regex from `index.py learnings --trigger-regex`, the same
  source `eval`'s LEARNING-LOOP check reads, so the gate and its audit cannot drift apart.
  With no learning banked yet the loop is **UNARMED** and owes nothing; once armed it is
  bounded by a **floor** — the earliest evidence stamp any learning cites — so banking the
  first lesson does not retroactively indict the project's whole history. With no store at all
  it is inert, like the gates half.
- **Third rule (4.7.0) — the unverified claim.** A return or ledger line **admitting** a gap —
  *not tested*, *could not be verified*, *has not been verified*, *never ran/tested/checked*,
  *not yet fully verified* — with no `open` record behind it blocks the same way. The grammar
  covers the perfect tense and the *never* forms deliberately: "it was never tested" and "it is
  not tested" are the same admission, and a checker that only caught one would teach the
  vocabulary that evades it. Not-tested is a legitimate outcome; **not-tested and unrecorded** is how
  it stops being one.
- **Writes:** echo only (stderr, plus `{"decision":"block","reason":…}` on stdout).
- **Safety property:** two of them. A **loop guard** (`stop_hook_active`) so the gate speaks
  once and then gets out of the way, because a hook that blocks unconditionally wedges a
  session forever. And **fail-open with a note** — a missing checker, a missing python3, an
  unreadable gates file all allow, but always say so on stderr, because a gate that fails
  silently is indistinguishable from a gate that passed.

### Shared helpers (not registered — other hooks call them)

**10. `estate-root.sh` — sourced by session-start, session-end, coord-nudge, agent-ledger**
The single answer to "which project does this session belong to". Sets `NR_ESTATE_ROOT`.
- **Writes:** nothing. Never prints, never exits its caller.
- **Resolution:** the git toplevel; failing that, the nearest `COORD.md` walking up at most
  three levels.
- **Safety property:** *containment*. It stops at any directory carrying its own project
  marker (a project boundary is never walked through), refuses `$HOME` and `/` outright, and
  skips a `COORD.md` symlink that escapes the estate. Four hooks that disagree about the root
  are four different estates, and the disagreement is invisible until something lands in the
  wrong project.

**11. `estate-pulse.sh` — called detached by coord-nudge and agent-ledger**
The background refresher. It runs the four read-only instruments and banks their output as
machine-written readings, so a session can see the estate's state without spending a token
asking.
- **Writes:** `pulse/pulse.json` (with `generated` and `trigger` — when, and what fired it)
  plus `pulse/{doctor,eval,swarm,compile}.txt`. Since 4.7.0 it also runs `compile.py draft
  --all-ripe` after a fresh scan when the estate is opted in — every ripe NEW candidate
  scaffolded into its own isolated dir, idempotently, at zero model tokens — and then, where
  the authorization also says *unattended*, `compile.py auto-run --next`, which **does** spend
  model tokens: a headless opus CLI run builds the oldest drafted candidate, a free fixture
  gates it, a second headless run attacks it, a script benchmarks it, and only then do green
  gates adopt it. **Never writes COORD** — a pulse per lane-stop would spam the ledger into
  uselessness.
- **It never parses the marker.** `compile.py auto` is the single reader of that file; the hook
  branches on its **exit code and its printed line** and nothing else, because a hook that read
  the JSON itself would become a second authority on what *authorized* means. Both calls are
  detached like the scan, `auto-run` is self-locking (a second caller exits 0 `BUSY` at once)
  and logs to `pulse/auto-run.log`, so a long unattended build can never slow a prompt.
- **The unattended rails** (each armed, because unwatched spending is only defensible when
  every failure is bounded first): one estate-wide lock, so never two runs and never during a
  live session's own compile; an owner-set `daily_cap_tokens` in the marker that the runner
  **refuses to breach**, saying so in a pulse line; a `spend.py log` receipt per headless run
  carrying the CLI's own observed token count (`lane=daemon`, model explicit); a **quiet stop
  with no retry storm** when auth fails; an injectable `--runner` so fixtures never spend a
  token; and `NOTREST_UNATTENDED=1` on every headless run, which the hooks honor by suppressing
  the AUTO-BUILD echo and refusing lane spawns from inside a run — one level deep, never a
  tree.
- **Safety property:** double-fork + `setsid`, so the worker is reparented to init and is
  nobody's child. This is load-bearing: the harness only notifies a finished agent when it has
  no live background children, so a daemon still parented to its spawner could cost you the
  agent that started it. A 60-second `flock` debounce means five lanes landing at once produce
  one refresh.

### The checker the Stop gate runs

**`gate-check.py`** — not a hook and not registered; `completion-gate.sh` executes it.
It reads a commission or gates file for `GATE:` / `CHECK:` / `EXPECT:` directives and runs
them. A gate passes iff the command exits 0 **and** every `EXPECT` regex matches the output.
Directives inside a fenced code block are documentation and are never executed. It records
evidence: the exit code, output byte length, output sha256, and once at the top the resolved
shell, cwd and PATH — because "it passed on my machine" is a claim about an environment.
**Exits:** `0` every gate green · `2` file missing/unreadable · `3` contract could not be
parsed (never a green — an existing gates file is a declaration that a contract exists).
Output is capped at 1 MB with the truncation stated, and every regex match runs under a
5-second alarm so a pathological pattern makes the gate red rather than hanging the session.

---

## 2. Instruments — the runnable tools, by owning skill

Every path below is relative to `plugins/notrest/skills/`. Each was confirmed on disk this
session; the `--help` or read-only invocation output is the source for what it does.

**Two families.** *Instruments* answer a question about the estate. *Fixtures* prove an
instrument still keeps its contract — they build a synthetic estate in a `mktemp` dir, assert
against it, and touch no real project. Every fixture is `exit 0 = all assertions held`.

### doctor — "is the install healthy?"
- **`doctor.py check`** — one read-only pass over the harness: front-matter YAML, manifest and
  tombstone pins, skill-count drift, **roster parity** (4.6.2 — every skill directory is
  actually NAMED on `README.md`'s table, `plugins/notrest/README.md`, `docs/TUTORIAL.md` and
  the marketplace description, because the older check matched the literal count "32" rather
  than the roster and so let a 29-row table pass), hooks that parse and ever fired, estate
  integrity, which build is really running, the token budget, gitignore rules that swallow
  skills, stale render stamps **and the counts they claim** (4.6.2 — a rendered "N-skill"
  phrase is a claim the reader believes, so it is checked against the tree, not just the
  version stamp). Never repairs; every FAIL carries its fix command.
  **Exits:** `0` all pass · `5` warnings only · `6` any fail · `3` target unusable · `2` usage.
  Since 4.7.0 the **ESTATE** check also prints one detail line for the learnings store
  (`learnings: N records, newest <age>`) — a detail, not a status: the PASS/WARN never turns on
  it — and **LOOP HEALTH**, the thirteenth check, reads the loop itself: uncited triggers,
  untested admissions with no `open` record, open questions by age, learnings per week, and
  candidates drafted or proposed but never decided. It PASSes while the loop turns and WARNs
  when it stops; it never FAILs, because a quiet week is not a broken install.
  *Live now (mid-4.7.0, working tree — `doctor.py check` prints the current line):* 13 checks,
  10 pass, 3 warn, 0 fail, exit 5 — the warns are the pre-existing unparseable COORD line
  (2026-08-27, append-only so it stays), the app-side shadow packs that only the owner panel
  can remove, and LOOP HEALTH reporting six untested admissions with no `open` record behind
  them — the newest check doing exactly its job on its first live estate.
- **`pulse.sh`** — the estate heartbeat in one unattended command: runs every read-only
  instrument, banks one line to COORD, exits `0` green or `1` something wants a human. Built
  for a scheduler.
- **`gategrep.sh <file> <phrase> [n]`** — counts a phrase the way a *reader* sees it, not the
  way grep does (markdown wraps split a visual line across source lines, producing false
  zeros). **Exits:** `0` match · `1` mismatch · `2` usage.
- **`render-check.sh <html>`** — proves an HTML file actually serves over 127.0.0.1 and hands
  back a URL, because `file://` silently breaks fetches and module scripts in the browser pane.
- **Fixtures:** `fixture.sh`, `coord-volume-fixture.sh` (the seal-don't-archive law),
  `pulse-fixture.sh`, `pulse-layer-fixture.sh` (asserts *timing and restraint*, not just
  content), `seat-tax-fixture.sh`.

### eval — "do the laws still leave a fingerprint?"
- **`eval.py check`** — a static pass asking whether every law left a mark in the shipped
  files: offload policy, honesty labels, scripts that compile, cited files that exist,
  append-only ledgers, worker contracts, safe front-matter, safety laws, silent hooks, the
  routing enforcer, router/oracle route-table parity, network egress, the kernel-surface law,
  the agreed release surface, and (4.7.0) **LEARNING-LOOP** — every correction, refuter defect
  or red gate the ledger records is cited by a banked `kind=learning` record, SKIPping as
  `loop not armed` on a store with none. Pure stdlib, pure read, zero model tokens.
  **Exits:** `0` all pass · `5` warnings only · `6` any FAIL · `2` usage.
  *Live now (mid-4.7.0, working tree, measured — the `SUMMARY` line is always the current
  count):* 32 skills, 16 checks, 0 fail, 0 warn, 0.39s.
- **`eval.py behavior`** — prints an opt-in bounded model case; does **not** run it.
- **Fixtures:** `fixture.sh` (builds a passing mini-harness, then injects one violation per
  check and asserts each flips *exactly* its own check), `pretool-fixture.sh` (pipes real
  PreToolUse payloads through the hard gate), `router-fixture.sh` (pipes real prompts through
  the routing law), and **`hooks-stdin-fixture.sh`** (new in 4.6.2 — drives every stdin-reading
  hook from a fifo that is held open and idle, so a hook that reads unbounded is caught as a
  hang rather than discovered in a session; the arm was watched red against the 4.6.1 hooks).

*The division of labour: **doctor checks the INSTALL, eval checks the LAWS.***

### notrest — "is the harness established here?"
- **`establish.py check --root .`** — read-only: does this project have the estate at all?
  Reports COORD presence, the CLAUDE.md protocol block version, git, ledger line count and
  age, and which auxiliary ledgers exist. *Live now:* ESTABLISHED, protocol **v3**, exit 0.
- **`establish.py establish`** — writes the establishment surfaces, idempotent. *(Writes —
  not run this session.)* This is a kernel surface: it writes into other people's projects.
- **`establish.py continuation`** — read-only: the packet a successor seat needs to continue
  a build already running. Since 4.7.0 it carries a **LEARNINGS** block after the ledger tail
  — the total banked plus the newest three digest lines, under the packet's own byte law, and
  **absent rather than empty** when the store holds none — plus the card counts line, and
  **LIBRARY LEARNINGS** (the newest two from the shelf) where a shelf exists, so a lesson
  another project paid for arrives before this one repeats it.

**The protocol block moved v2 → v3 in 4.6.2** (`PROTOCOL_VERSION = 3`, `establish.py:62`),
carrying the owner's 2026-09-01 offload ruling as its own bullet — the seat picks each lane's
model by the difficulty of the task and declares it. The upgrade is a version bump with
manners, and the manners are the point:
- **`BODY_V2` is KEPT as history, not deleted** (`:114`), beside `BODY_V3` (`:138`), because
  an estate's block must be recognizable at the version it actually adopted.
- **A block one version behind is STALE, not absent** (`:979`) — the older `found >=
  PROTOCOL_VERSION` reading would have told every v2 estate "already established" and left
  it there forever. `check` now reports the block STALE and exits `5`.
- **The packet keeps emitting while it says STALE.** A stale block is a thing to upgrade, not
  a reason to withhold the trail from a successor; the packet carries `protocol_current` and
  `protocol_stale` (`:1004-1005`) so the reader knows which it got.
- **`establish` upgrades in place, byte-for-byte outside the markers**, and a body that was
  HAND-EDITED away from the canonical v2 text is banked to `<file>.notrest-v2.bak` (`:1468`)
  before it is replaced — a local override is never silently relaxed.
*This repo is already at v3* (`CLAUDE.md:55`, `AGENTS.md:38`), so `check` here now exits 0;
the STALE-at-5 path was gated by the seat on this repo before the upgrade landed (COORD
2026-09-02 00:20Z), not by me. `[verified: code read + live check/packet run]`
- **`fixture.sh`** — asserts establish.py *and* the hook closures it depends on; runnable from
  a clean clone with only python3, bash and git.

### spend — "was the model routing lawful, and what did it cost?"
- **`spend.py report`** — reads the append-only `spend/ledger.md` and grades every observed
  lane against the runtime worker policy. **Exit `4` is the routing gate firing**, not a bug.
  Entries are graded `observed` or `estimate`; the seat's own consumption is invisible to the
  model and the ledger says so, logged separately as `--seat-estimate`.
  *Live now:* VIOLATION, exit 4, 7 offload entries on an unsupported worker model.
- **`spend.py log`** — appends one entry, flock-atomic. *(Writes; the SubagentStop hook does
  this automatically — hand-logging double-counts.)*
- **`fixture.sh`** — proves the violation predicate against synthetic ledgers; every case is a
  negative, because a gate that never fires is an unproven gate.

### graph — "what does this project look like?"
- **`graph.py scan`** — scans a project into `graph/graph.{json,html}`. *(Writes.)*
- **`graph.py river` / `journey`** — the trail as a drawing: the river renders
  `findings.jsonl` plus COORD volumes as a river toward the goal (side channels, backtrack
  loops, conflict rocks, milestone flags); the journey renders router shapes, intake routes
  and chains. *(Writes HTML.)*
- **`graph.py links|orphans|stale|domains`** — text queries over the last scan. `orphans` is
  honest about its own limits: no edge means nothing in *this* repo points at a file, which
  looks identical to an entry point or a hook target.
- **`graph.py all|register|unregister`** — the cross-project registry and merged PM view.
- **`cockpit.py status`** — is the opted-in cockpit actually up? **Exits:** `0` up · `5` not
  opted in · `6` opted but down. *Live now:* opted always-on at :8788, down.
- **`cockpit.py serve`** — serves the estate live on 127.0.0.1. *(Starts a server.)*
- **Fixtures:** `cockpit-fixture.sh`, `river-fixture.sh` (a synthetic estate whose river shape
  is known by arithmetic), `journey-fixture.sh` (asserted against the real repo),
  `domains-fixture.sh`.

### agentswarm — "were the lanes the right size?"
- **`swarm.py report`** — per-lane rows plus a decomposition band, computed from the receipts.
  It also reports live background processes separately, labeled as live rather than folded
  into the byte-identical reading. *Live now:* FLAGGED, exit 5 — 198 lanes, 15 monoliths,
  87 degraded receipts.
- **`swarm.py watch`** — a detached zero-token poller over running lanes; writes alerts to
  `pulse/swarm-live.txt`, which `coord-nudge.sh` surfaces on the next prompt. *(Writes.)*
- **`dead-by-marker-arm.sh`** — distinguishes a lane that was *interrupt-killed* (transcript
  ends in a terminal marker) from one that is *frozen and unreceipted*. Two states that look
  identical from the outside.
- **`swarm-fixture.sh`** — the decomposition gauge asserted against estates whose right answer
  is known by construction, because a metric nobody can falsify is a number, not a measurement.

### compile — "what work have we done three times?"
- **`compile.py scan`** — clusters the estate and writes `compile/candidates.md`. *(Writes.)*
  Since 4.7.0 it also reads the findings store's **learning** and **open** records: a statement
  recurring three or more times becomes a candidate of kind **`rule`**, citing the record ids —
  the compiled form of a repeated lesson being a hook arm or an eval check, not a paragraph.
  Since 4.6.2 it **narrates itself on stderr** (`compile.py:708`; stdout stays the machine
  surface) — per ledger family, then no less often than every ~10 s inside the merge — because
  the 4.6.1 audit lane killed a silent 120 s run and filed it as a hang. A tool that prints
  nothing for tens of seconds is indistinguishable from a dead one.
- **`compile.py report`** — one line per ripe candidate. **Exit `3` if any is NEW** (unruled).
  *Live now:* exit 3, 27 ripe candidates not yet ruled on.
- **`compile.py decide`** — records a ruling that survives the next scan. *(Writes.)*
- **`compile.py contract`** — the responsibility table pre-filled with trail citations.
- **`compile.py auto`** — the owner's standing authorization to dispatch a builder lane.
  Bare invocation is status (`0` opted, `5` not). Since v4.5 the marker lives **outside** the
  estate at `~/.notrest/auto-build/<sha256>.json`, because an in-repo marker is writable by any
  lane — a lane could grant itself the authority to be dispatched.
- **`compile.py scaffold`** — creates a `compile/<slug>/` skeleton; never overwrites (exit 2).
- **`compile.py draft --all-ripe`** — the unattended half of 4.7.0's auto-build: every ripe NEW
  candidate scaffolded (contract + skeleton + benchmark harness), recorded `DRAFTED`, existing
  slugs untouched. Idempotent, zero model tokens — which is what makes it safe to run from a
  daemon.
- **`compile.py decide --status ADOPTED`** — now refuses without `--evidence` for the fixture,
  the FAIR benchmark and the refuter verdict, and prints the ledger-ready receipt line. An
  adoption that cannot show three receipts cannot be written down.
- **`fixture.sh`** — asserts compile.py against a synthetic estate, and since 4.6.2 carries a
  **permanent runtime arm** (§M): a seeded 260-entry corpus over a ~48-token vocabulary — the
  shape of a real estate's largest family — must finish inside a **10 s** bound. The number is
  argued, not picked: measured 2.1 s after the fix and 17.5 s before it, so the bound has ~4.6x
  headroom against CI flake while still FAILING on a regression to the old quadratic
  recomputation. Cost grows with the SQUARE of the largest family, so a bigger corpus means
  re-measuring the bound rather than nudging it. Two promises are gated, and neither is "it got
  faster": a bounded corpus finishes inside a bound the SKILL.md states, and the run narrates
  itself so a reader can tell working from wedged.

### recap — "how did we get here?"
- **`walk.py walk`** — merges COORD volumes, COORD-AGENTS, git history, the spend ledger and
  dossier folders into one timestamp-ordered stream, plus an estate inventory. Zero model tokens.
- **`walk.py spans`** — per-source / per-day / per-session spans and counts.
- **`walk.py prefill`** — the RECAP_DATA block with nodes and citations pre-filled.
- **Exits:** `0` ok · `2` usage · `3` the estate is empty.
- **`fixture.sh`** — asserts walk.py against a synthetic estate.

### archivist — "what do we already know?"
- **`index.py find`** — searches findings, index entries and dossier bodies.
- **`index.py track`** — prints the session track (the running list of finding records).
- **`index.py add`** — appends one validated finding record; **rejects at the door with exit 2**
  and names the rule it broke (schema, enums, honesty labels, real URLs behind cited links).
- **`index.py supersede` / `refute`** — append a tombstone; an append-only status flip that
  edits no existing byte.
- **`index.py scan`** — rebuilds `oracle-index.md` for the legacy dossier estate.
- **`index.py learnings`** — the estate's banked lessons (`kind=learning`, tagged
  `INHERITED` / `RULED` / `LEARNED`, each carrying required `evidence` and `scope`).
  `--digest` prints the one framed line format every consumer reads — the continuation packet,
  the spawn gate, the router — `--scope` narrows to a lane's own paths and skills (plus
  `estate`), `--since` to what is newer than a ledger timestamp, and `--trigger-regex` prints
  the pattern the Stop gate and eval's LEARNING-LOOP both match trigger lines with.
- **`index.py card`** — the estate's state of play in four boxes: TESTS / OPEN / FINDINGS /
  LEARNINGS, with counts. The same shape a lane's return card is written in, which is why the
  hook can bank a return by parsing it rather than translating it.
- **`index.py promote L-<n>`** — copies a learning scoped `library` to the shelf, where every
  project's packet reads it back. The one thing that crosses the federation line, and only on
  an explicit scope token.
- **`index.py library`** — the cross-project shelf: register, list, find, track.
- **`fixture.sh`** — proves every validation rule turns its record away and names itself.

### watch — "are these facts still true?"
- **`watch.py due`** — which watched claims are past their re-check date — and, since 4.7.0,
  which **open records** are: a question the project left open carries a `recheck` date and
  ages on the same calendar as a fact.
- **`watch.py close <open-id>`** — closes an open question by appending the closing record
  through `index.py`, citing the open id, so the answer stays linked to the question.
  *Live now:* 2 due of 2 rows.
- **`watch.py add` / `probe` / `append`** — add a claim to the watchlist, fetch a source, and
  make the atomic drift-log write. *(Writes.)*
- **`fixture.sh`** — asserts against a synthetic watchlist and a real local HTTP server on an
  ephemeral port; never reaches the network beyond 127.0.0.1.

### mentor — the mentor/builder ritual's deterministic half
- **`mentor.py charter`** — create or annotate the room and post the charter. *(Writes.)*
- **`mentor.py escort`** — prints the filled orientation escort; **never sends**.
- **`mentor.py checkpoints`** — the checkpoint ledger. **Exit `3` if any checkpoint is ungated.**
- **`mentor.py status`** — one line for a scheduler or a pulse.
- **`fixture.sh`** — asserts charter idempotency, the live engine read, the checkpoint parse,
  malformed-room tolerance, the inherited no-secrets screen, and the no-writes law.

### director — chaining skills into a pipeline
- **`director.py plan`** — resolves the chain and scaffolds the run folder. *(Writes.)*
- **`director.py handoff`** — records a stage's input/output manifest with sha256. *(Writes.)*
- **`director.py verify`** — **exit `3`** on an unticked box, an empty stage, or drift.
- **`fixture.sh`** — every case makes the director's own failure mode ("the last stage never
  ran") actually fire, rather than merely describing it.

### refuter — the adversarial reviewer's tooling
- **`brief.py --target T`** — mints a filled attack brief that pins the target bytes inline
  and stamps the tool-call budget. `--strict` exits `5` if a seat field is still unfilled.
- **`verdict_lint.py <report>`** — lints a refuter report against the verdict grammar.
- **`fixture.sh`** — asserts both; spawns no lane and calls no model.

### The linters — one per planning verb
- **`stepbystep/scripts/plan_lint.py check`** — holds a plan to the ordering and verification
  rules; **`converge`** measures the distance between two candidate plans, so the refine loop
  is measured rather than trusted.
- **`actionplan/scripts/runbook_lint.py <runbook>`** — lints a runbook *before a human pastes
  it into production*. Its fixture also asserts the honest degradations (shellcheck absent,
  chatroom's secret list unreachable), because a check that silently stops checking is worse
  than one never written.
- **`sessionend/scripts/starthere_lint.py check`** — lints a `START-HERE.md` for
  resume-readiness: five FAIL rules, plus a clean-clone rule.
- **`introspect/scripts/score_snapshot.py score`** — prints the metrics JSON, writes nothing;
  **`append`** ledgers a run; **`report`** aggregates and **exits `3` below N=10** samples.

### The lanes and bridges
- **`beam/scripts/beam.py`** — `bank`, `manifest`, `snapshot`, `mark`, `rail`, `down`,
  `status`. Checkpoints an in-flight lane and can respawn it elsewhere. Its no-touch law:
  `snapshot` publishes the *current* tree state, dirty files and all, onto a git ref without
  ever checking out or switching.
- **`chatroom/scripts/room.py`** — `create`, `post`, `read`, `lines`, `join`, `watch`,
  `gpt-bridge`. Shared rooms where sessions and a GPT bridge talk. Its fixture asserts the
  no-secrets law and that a stub `codex` was *never reached*.
- **`gpt/scripts/gpt.sh`** — `chat` (persistent conversation), `once` (one-shot, nothing
  saved — the director-safe form), `task` (background job in an empty workspace), `parse`.
  Receipts every call to the spend ledger. Its fixture uses a stub codex: no OpenAI call, no
  quota spent, no network.
- **`fable-director/scripts/new-fable-project.sh`** — scaffolds the "3 devs and a relay"
  blackboards into a repo. **File-only: it spawns nothing** (session creation is owner-only)
  and refuses to clobber existing `COORD*.md` without `--force`.
- **`fable-director/scripts/fable-launcher.sh`** — starts a director session, probing for
  `claude-fable-5` and falling back to the latest Opus. The API key is scoped to the process,
  never exported globally.
- **`game-forge/assets/engine.py`** — not an instrument: a runnable pygame starter template
  with a headless smoke-test mode.

**Ten skills own no scripts** and are pure prose contracts: critic, decider, draft, explainer,
fable-mode, factcheck, marketresearcher, oracle, researcher, tieredswarm.

---

## 3. Skills — all 32

Descriptions below are derived from each `SKILL.md`'s own frontmatter, read this session.

### The harness spine (9) — the skills that run the harness itself

| Skill | What you'd tell a stranger |
|---|---|
| **notrest** | Sets the harness up in a project, or picks up a build already running there. |
| **oracle** | The front door: opens or resumes a session, asks six context questions, then routes you to the right verb. |
| **sessionend** | Closes a session properly — writes four continuity files so a successor with no memory can resume. |
| **fable-mode** | The working posture: probe before believing, prove before claiming, bank before stopping. |
| **doctor** | Checks whether the plugin is correctly installed and healthy. Reads only. |
| **eval** | Checks whether the plugin's own laws are still honored in its shipped files. |
| **recap** | Walks the recorded trail and tells you the story of how the project got here, every claim cited. |
| **graph** | Draws the project — a file graph and a river of the trail — as self-contained HTML, then opens it. |
| **agentswarm** | The delegation arrangement: the seat decides and judges, background lanes do the work. |

### Knowledge verbs (12) — skills that produce findings, documents, or answers

| Skill | What you'd tell a stranger |
|---|---|
| **researcher** | Multi-pass research on an open question, landing validated finding records instead of vibes. |
| **factcheck** | Checks whether specific claims are actually true, with dated citations and a verdict per claim. |
| **marketresearcher** | Sizes a market and maps competitors — including the graveyard of ones that died. |
| **archivist** | The findings store: what do we already know, and where is the session's whole track? |
| **explainer** | Builds real understanding of a topic in three depth layers, including the standard misconceptions. |
| **decider** | Structures a decision into options, weighted criteria, a scored matrix, and a pre-mortem. You still decide. |
| **critic** | Attacks a document or plan — steelman first, then severity-tiered objections and real alternatives. |
| **refuter** | Attacks *code* before it ships. A lane other than the builder, under a brief. It finds, never fixes. |
| **stepbystep** | Turns a goal into a dependency-ordered plan where every step says how you know it's done. |
| **actionplan** | Turns that plan into exact copy-paste commands, with a verify and a rollback on every step. |
| **draft** | Turns a finding or decision into the thing you actually send. It never sends — that's yours. |
| **watch** | Facts expire; this re-checks them on a schedule and logs what drifted. |

### Arrangements and lanes (7) — skills that seat or shape a way of working

| Skill | What you'd tell a stranger |
|---|---|
| **tieredswarm** | The three-layer delegation shape, plus the measured gate saying when it's actually worth it. |
| **director** | Chains suite skills into a pipeline, each stage's output feeding the next. |
| **fable-director** | Seats a metered director session running dev and QC lanes on per-lane blackboards. |
| **mentor** | Two peer sessions on one room: one builds, one escorts and gates the checkpoints. |
| **chatroom** | A shared room where sessions — and a GPT bridge — talk and work together. No secrets. |
| **beam** | Checkpoints a running lane so you can walk away and pick it up somewhere else. |
| **gpt** | A persistent GPT conversation as a second opinion. Opinions, never sources. |

### Instruments and specialists (4)

| Skill | What you'd tell a stranger |
|---|---|
| **spend** | The token receipt — an append-only ledger that makes the routing rule checkable, not just asserted. |
| **compile** | Finds work done three or more times and turns it into code, benchmarked against that history. |
| **introspect** | The model reports what it's attending to, and the harness scores those reports against what it then does. |
| **game-forge** | Builds a complete, playable game from a short request. No game ships unrun. |

**Total: 9 + 12 + 7 + 4 = 32.**

---

## 4. The estate files

These live at the project root, not in the plugin. They are the durable record.

**The compile queue does not ship (4.7.0).** `/compile/*/` is now ignored — the daemon's
`DRAFTED` scaffolds are a work queue, not release content, and an unattended drafter that
committed every scaffold would fill the repo with runtimes nobody ruled on. `release-ritual/`
is negated back in, and a runtime enters git only when it is **ADOPTED**: the adoption step
prints the `git add -f compile/<slug>` that puts it there, so the one thing that makes a
runtime part of the estate stays a deliberate act with a receipt.

**Derived output does not ship (4.6.2).** `plugins/notrest/graph/` held four tracked
scan artefacts — `graph.{html,json}` and `river.{html,json}`, 125 KB generated 2026-07-27
and referenced by nothing — which escaped `.gitignore` because the `/graph/` rule is
anchored to the repo root and doctor's GITIGNORE check never looked inside the package.
They were untracked in 4.6.2 and the gate now looks there. Every graph and river view is
regenerated on demand by `graph.py`; a shipped copy is a stale claim about a tree that has
since moved.

| File | Who writes it | Who reads it |
|---|---|---|
| **`COORD.md`** | The **session**, one honest line per substantive prompt (`ask → landed \| evidence`). Scaffolded and cushioned by hooks. | Every next session (the tail), `recap`, `compile`, `archivist`, `doctor`. Append-only; never compacted — sealed whole as `COORD-<NNN>.md` at ~500 lines. |
| **`COORD-AGENTS.md`** | The **`agent-ledger.sh` hook**, automatically, one line per finished lane. | `recap`, `swarm.py report`, and any session wanting the delegation history. |
| **`spend/ledger.md`** | The **`agent-ledger.sh` hook**, auto-receipting each lane (idempotent). Hand-logging double-counts. | `spend.py report`, `doctor`, `recap`. Append-only. |
| **`briefs/`** | The **`agent-ledger.sh` hook**, banking each lane's verbatim commission as `agent-<id>.md`. | The owner and any reviewer — this is what makes commission transparency structural. |
| **`archive/findings.jsonl`** | The **knowledge verbs**, via `index.py add`, validated at the door — findings about the world; `kind=learning`, what the estate learned about working here; `open`, what was *not* tested or could not be verified, with a recheck date; `alternative`, a road not taken; and `result`, which must name what ran, the command and the exit code. Since 4.7.0 the **`agent-ledger.sh` hook** writes here too, banking every lane's return card — its judgment kinds as `proposed`, awaiting the seat's `accept` / `reject --why`. | `archivist find/track/learnings`, `graph river`, `recap` — plus, for learnings, the continuation packet, `spawn-gate.sh`, `router.sh`, `completion-gate.sh` and eval's LEARNING-LOOP. Append-only; status flips are tombstones. |
| **`gates/ACTIVE.md`** | The **owner or director**, declaring the commission's gates as runnable `CHECK:`/`EXPECT:` lines — and, since 4.7.0, `spawn-gate.sh`, appending a lane's own unfenced `DONE-WHEN:` block under `## lane <8-hex key> · opened <UTC>` with a provenance comment per line (retired by key when the lane stops, swept by `session-start.sh` after 24 h). | `completion-gate.sh` via `gate-check.py`, at every Stop. Absent → the gate is inert. |
| **`pulse/`** | The **`estate-pulse.sh` daemon**, in the background. `pulse.json` plus one `.txt` per instrument. | `session-start.sh` (echoes the reading), `coord-nudge.sh` (surfaces swarm alerts), the cockpit. Derived and disposable — the ledgers remain the record. |
| **`~/.notrest/auto-build/`** | The **owner**, via `compile.py auto --on`. Deliberately outside the estate. | `session-start.sh`, to decide whether to echo a nudge or a directive. Authorizes *dispatching* a lane and nothing else — installing is still the owner's act. |

---

## 5. How it all fits

A session opens and `oracle` seats it; a session closes and `sessionend` banks it — those are
the bookends, and the SessionStart/SessionEnd hooks make sure something is written even when
nobody runs either one. Between them, `fable-mode` is the posture: probe the live system,
prove at the consumer, label anything unproven, bank before stopping. The trail is the whole
point — COORD for what a human decided, COORD-AGENTS and briefs and the spend ledger for what
was delegated and what it cost, findings.jsonl for what was learned. All four are written by
machines at zero model cost, and all four are append-only, so the record cannot be quietly
revised. Three gates make the rules binding rather than merely stated: the spawn gate refuses
an unlawful lane at the door, the Bash gate refuses a push while the instruments are red, and
the Stop gate refuses a "done" while the commission's own checks are red — or while a
correction the session took has not been banked as a lesson. That last one closes the estate's
oldest leak: a lesson learned in one session used to live as prose in COORD and reach the next
session only if it scrolled that far. Now it is a record with evidence and a scope, and the
harness carries it forward on its own — into the continuation packet, into every lane's prompt
at the spawn gate, into a router line when a prompt touches what it covers — with eval's
LEARNING-LOOP auditing the whole loop from the other end and doctor's LOOP HEALTH reading
whether it is still turning. 4.7.0 closes the same circle around a *lane*: its commission's
`DONE-WHEN` block becomes its Stop gates at dispatch, and its return card is parsed straight
into records at receipt — what it tested, what it left open, what it found, what it learned —
so delegated work banks itself instead of being summarized. And the compiler now runs the same
way: repeated work (and a lesson repeated three times) is drafted unattended by scripts, built
and attacked by lanes a session can see, and adopted only when the fixture, the fair benchmark
and the refuter are all green — automation bounded by gates rather than by asking. Delegation runs
through `agentswarm` — one persistent lane per domain, resumed rather than respawned — and
every lane's work comes back to a reviewer who is not its author, because nothing here grades
itself. Continuity is the through-line: every hook fails open and silent, every instrument
reads rather than repairs, and every claim carries an exit code, a path, or a label saying it
doesn't.

---

## Loose threads found while mapping

Gap candidates for the owner's review. Each is stated with the evidence that produced it.

1. **The completion gate is dormant in the estate that built it.** `ls gates` →
   `No such file or directory`. `completion-gate.sh` shipped in v4.5 and does nothing at all
   in this repo, because no `gates/ACTIVE.md` exists. The estate that wrote the vacuous-pass
   killer has not armed it on itself.

2. **Three surfaces state two different offload laws.** `spawn-gate.sh:102` allows
   `*opus*|*sonnet*` ("owner-amended 2026-08-30; was opus-only 2026-07-15"). But
   `session-start.sh` still echoes into *every session*: `HARD RULE — offload: … Never
   sonnet, haiku, or subagent_type "fork"`. The project `CLAUDE.md` and the global standing
   order also still say opus-only. A session is told one rule and gated by another.

3. **The door and the audit disagree about sonnet.** `spend.py report` exits 4 —
   `routing: VIOLATION — policy v4.3: runtime worker (Claude=opus, Codex=gpt-5.6-sol)
   (7 offload entries on an unsupported worker model, 0 legacy)` — flagging seven
   `claude-sonnet-5` lanes that `spawn-gate.sh` would have admitted without complaint. The
   post-hoc audit is enforcing a stricter law than the gate at the door.

4. **`eval`'s ROUTE-CONFORMANCE check has never had data.** `SKIP ROUTE-CONFORMANCE … no
   'routed to /<skill>' lines across 2 ledger file(s)`. The check asks whether a recorded
   route left downstream evidence; no session has ever written the line it looks for, so the
   check has been permanently skipped rather than ever passing or failing.

5. **`swarm.py report` is red and has been left red.** `swarm: FLAGGED — 198 lane(s),
   15 monolith(s), 87 degraded receipt(s) (exit 5)`. Nearly half the receipts are degraded.
   Either the receipt writer is losing information, or the flag is being routinely ignored.

6. **27 ripe compile candidates are unruled.** `compile.py report` exits 3 with
   `27 ripe candidate(s) not yet ruled on`, including `builder-resum` at 8× and
   `compil-releas-ritual` at 5×. The compile skill's own premise — work done 3+ times should
   become code — is not being applied to a backlog this size.

7. **Both watched claims are four weeks overdue.** `watch.py due` → `2 due of 2 rows`, both
   `last=2026-07-26 due=2026-08-02`. One of them watches this repo's own CLAUDE.md claim about
   how the skills-dir runtime loads. Nothing has re-verified it.

8. **One COORD line is unparseable.** `doctor` WARN: `COORD.md: 1/210 ledger lines
   unparseable (first: - [2026-08-27T20:07Z] [seat] owner: how did we connect gpt previously,)`
   — an ISO `T` separator where the ledger grammar expects a space. The scaffold header shows
   the intended format but nothing rejects a malformed line at write time.

9. **`doctor` warns about 23 app-side packs.** `WARN SHADOW-APPSIDE — 23 app-side pack(s) in
   1 store(s) · this tree ships 32 verbs · store: ~/Library/Application Support/Claude/
   local-agent-mode-sessions`. Given the shadowing history that produced the pretool-gate's
   RULE 2, this warning's persistence is worth a decision rather than a standing WARN.

10. **The graph scan is stale relative to the release.** `graph.py orphans` reports
    `scanned 2026-08-22 17:53Z`, but v4.5.0 shipped at `bd9fec0` after that. Every text query
    over "the last scan" is answering about a pre-release tree.

11. **`fable-launcher.sh` carries a credential placeholder in a tracked file.**
    `export ANTHROPIC_API_KEY="PASTE-REAL-KEY-HERE"     # ← PASTE-REAL-KEY (owner only)`.
    The comment says owner-only and the key is process-scoped, but the instruction is to paste
    a live secret into a git-tracked file. There is no gitignore or template split protecting it.

12. **The cockpit is opted always-on and down.** `graph/.cockpit-always` exists;
    `cockpit.py status` reports `down (opted always-on)`. `session-start.sh` echoes a line
    telling the seat to probe and start it — an instruction that has evidently not been acted
    on, which is the exact failure mode the always-on marker was added to fix.

13. **No estate on this machine holds an auto-build authorization.**
    `~/.notrest/auto-build/` does not exist (`~/.notrest/` holds `build/`, `control-build/`,
    `mcp-bridge/`, `suite-build/` — all unrelated, last touched in July). The v4.5 relocation
    out of the repo is implemented and fixture-covered, but the feature has zero live users,
    so the new path's real-world behavior is untested outside the fixture.

14. **The hook count depends on where you draw the line.** `plugins/notrest/hooks/` holds
    **12** executable files. `eval`'s HOOK-CONTRACT names 11 (excluding `gate-check.py`), and
    `hooks.json` registers 9 scripts across 8 events. The three numbers are all defensible but
    none of them is written down anywhere, so "how many hooks does notrest have" has three
    answers depending on which instrument you ask.


## Canon rulings (2026-09-01, closing the map's own loose threads)

**The hook count.** Canonical number: **11 lifecycle hooks** — the scripts eval's
HOOK-CONTRACT counts. `estate-root.sh` is a sourced library (every hook's shared resolver,
never fired by an event), and `gate-check.py` is an instrument the Stop hook *runs*, not a
hook. `hooks.json` registers 7 events; two events carry matcher-split entries, which is why
"registered entries" undercounts scripts. When three numbers disagree, cite this paragraph.

**ROUTE-CONFORMANCE stays SKIP by convention.** No `routed to /<skill>` line has ever been
banked, so the check has no data. The convention going forward: when a seat deliberately
FOLLOWS a router nudge, its COORD line for that work includes `routed to /<skill>`; when it
deliberately overrides, nothing is owed. The check is WARN-grade by design and a permanent
SKIP is honest absence, not a defect.
