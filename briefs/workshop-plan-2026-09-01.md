# Workshop rebuild — planning lane return (read-only, 2026-09-01; seed for the build; owner decisions in §4)

# Workshop rebuild — plan (read-only; nothing written)

## 0. Ground truth captured live (working tree, mid-4.6.2)

`eval.py check --root .` → **exit 0, 32 skills, 15 checks, 0 fail, 0 warn, 0.22s**. `doctor.py check --root .` → **exit 5, 12 checks, 9 pass, 3 warn, 0 fail** (MAP.md:191 says *2* warn — the third is `INSTALL FRESHNESS: tree=v4.6.2 HEAD=v4.6.1`, which disappears when the release commits; the pack must not hard-code 2 or 3, see §4). `establish.py continuation --brief --root .` → ESTABLISHED, **protocol v3**, exit 0. `RELEASE-SURFACE` currently reads **62 surfaces all present** — every file the rebuild adds or removes moves that number and must land in `evals/golden-release-surface.txt` in the same commit (`eval.py:892-928`).

---

## 1. Proposed taxonomy

Seven categories. Definition = *the job it does in a session*, which is the owner's movement-2 ask.

| # | Category | One-line definition |
|---|---|---|
| A | **Bookends & posture** | Open, close, and set the discipline of a session; nothing else runs without them |
| B | **Instruments** | Read-only graders that answer a question about the estate at zero model tokens and exit with a code |
| C | **Knowledge verbs** | Turn an open question into validated, labelled finding records in the store |
| D | **Judgment verbs** | Take an artifact and return a structured verdict, decision, plan, or sendable — never the thing itself |
| E | **Arrangements** | Seat a *way of working* across more than one worker; they shape sessions, not artifacts |
| F | **Bridges** | Cross a boundary — process, machine, or vendor — carrying work with it |
| G | **Specialists** | Build one kind of deliverable end to end |

**Placements** (evidence in parentheses; `MAP§3` = the roster table, `FM` = SKILL.md front-matter read this session):

- **A (4)** — `oracle`, `notrest`, `sessionend`, `fable-mode`. *MAP§5 names oracle/sessionend "the bookends" and fable-mode "the posture"; MAP§3 puts all four in the spine.*
- **B (7)** — `doctor`, `eval`, `spend`, `graph`, `recap`, `compile`, `introspect`. *MAP§2 lists each under "the runnable tools"; MAP§1 division of labour "doctor checks the INSTALL, eval checks the LAWS"; MAP§3 puts spend/compile/introspect under "instruments and specialists".*
- **C (6)** — `researcher`, `marketresearcher`, `factcheck`, `watch`, `archivist`, `explainer`. *MAP§4 "`archive/findings.jsonl` — written by the knowledge verbs, via `index.py add`"; CAPABILITIES.md:100 heading "Skills — knowledge verbs".*
- **D (6)** — `decider`, `critic`, `refuter`, `stepbystep`, `actionplan`, `draft`. *CAPABILITIES.md:163 "decision & outbound verbs"; FM: draft "never sends", decider "the user decides", refuter "finds, never fixes".*
- **E (5)** — `agentswarm`, `tieredswarm`, `director`, `fable-director`, `mentor`. *MAP§3 "arrangements and lanes"; FM `director` "For orchestrating SESSIONS instead, see fable-director"; FM `mentor` "two PEER sessions".*
- **F (3)** — `chatroom`, `gpt`, `beam`. *MAP§2 "The lanes and bridges"; FM: gpt "prompts leave the machine to OpenAI", chatroom "the bridge sends room content to another vendor", beam "respawn the remaining work in the cloud".*
- **G (1)** — `game-forge`. *MAP§2 "not an instrument: a runnable pygame starter template"; MAP§3 groups it with instruments only by residue.*

**Hooks (11 lifecycle + 2 non-hooks = the 13 files in `hooks/`).** Canon: MAP.md:588 rules **11 lifecycle hooks**; `eval` HOOK-CONTRACT confirmed 11 live. Sub-taxonomy by what they do:

| Sub-category | Members (all from `hooks.json`, read this session) |
|---|---|
| **Writers** (put bytes in the estate) | `session-start.sh` (SessionStart), `session-end.sh` (SessionEnd), `agent-ledger.sh` (SubagentStop) |
| **Nudges** (echo only) | `coord-nudge.sh`, `router.sh` (both UserPromptSubmit), `pre-compact.sh` (PreCompact/auto) |
| **Gates** (refuse) | `spawn-gate.sh` (PreToolUse `Agent\|Task`), `pretool-gate.sh` (PreToolUse `Bash`), `completion-gate.sh` (Stop) |
| **Plumbing** (never fired by an event) | `estate-root.sh` (sourced library), `estate-pulse.sh` (detached daemon) |
| **Not hooks** | `gate-check.py` (an instrument the Stop hook *runs*), `hooks.json` (the wiring itself) |

**Named instruments → owning skill:** `doctor.py`/`pulse.sh`/`gategrep.sh`/`render-check.sh` → B/doctor · `eval.py` → B/eval · `spend.py` → B/spend · `graph.py` **and `cockpit.py`** → B/graph · `establish.py` → **A/notrest** (it is the establishment verb's engine, not a grader) · `gate-check.py` → B, ownerless (see below).

**Tools that resist categorization — flag these to the owner:**
1. `introspect` — measures *the model*, not the estate; it is the only "instrument" whose subject isn't a file.
2. `compile` — a scanner (B), a build ritual (E), and an owner authorization surface (`~/.notrest/auto-build/`, MAP§4) in one skill.
3. `recap` — MAP§3 files it under the spine, CAPABILITIES.md:138 under knowledge verbs. Both defensible; it *reads* the estate and *narrates* it.
4. `game-forge` — a category of one. Either give it its own box or drop it from the taught roster.
5. `gate-check.py` and `estate-root.sh` — MAP loose thread #14 ("the hook count depends on where you draw the line") plus its own canon ruling at MAP.md:586. **The pack must cite that paragraph rather than invent a fourth number.**
6. The commission's `NOTREST_ROLE` — **it does not exist.** `grep -o "NOTREST_[A-Z_]*"` over `plugins/` + `docs/` returns only `NOTREST_HOME`, `NOTREST_GATE_OVERRIDE`, `NOTREST_LIBRARY_ROOT`, `NOTREST_ROOM_PY`, `NOTREST_KEYFILE`, `NOTREST_WATCH_QUIET`, `NOTREST_WATCH_POLL`, `NOTREST_PLUGIN_ROOT`. Roles are set **by prompt** — an agentswarm lane's commission, or a `NAME:ROLE` lane-spec to `new-fable-project.sh:9` (`ROLE ∈ {ship,research,content,qc}`). Movement 4 must teach the real mechanism.

---

## 2. Module-by-module plan (owner's four movements)

Ten module slots retained (see §4 for the shape decision); numbering re-cut to the movements.

| # | Module | Learning goal | Draws on | REUSE | RETIRE | Must reproduce live |
|---|---|---|---|---|---|---|
| **M0** | Open + the shared contract | Name the five parts of the skill contract; read an exit code aloud | `modules/00`, `handouts/cheatsheet.md:30-67` | Whole contract table + exit-code table + the four failures | The "ten verbs" framing (the pack now teaches 32) | doctor bare → **3**, `--plugin` → **5**; eval bare → **2** |
| **M1** | **Structure & architecture** *(new)* | Draw the tree from memory: manifests → hooks → skills → scripts → ledgers → estate files; say where the law lives vs where it is enforced | `MAP.md §1,§4,§5`; `hooks/hooks.json`; `plugins/notrest/.claude-plugin/plugin.json` | `modules/02`'s "presence is not establishment" as the module's spine | — (no existing module covers architecture) | `hooks.json` registers **7 events**, 9 script entries, **11 lifecycle hooks**; every command carries its own `timeout` (10–300s), group-level `timeout` is `None` |
| **M2** | **The categories** *(new)* | Given any verb, name its category and its job in a session | §1 above; `MAP.md §3`; `CAPABILITIES.md:100/163/219` | — | `MAP§3`'s 9/12/7/4 split *if* the owner adopts the 7-category cut | 32 skills, 4+7+6+6+5+3+1; `eval` TRIGGER-SANITY confirms 32 dirs == 32 names |
| **M3** | Bookends & posture (cat. A) | Drive oracle → fable-mode → sessionend; `/notrest`'s four exit codes | `modules/01`, `02`, `03`, `08` | 01's `CLAUDE.md`-exists condition; 02's refusal beat + ordering warning; 03's "assertion that fails on purpose" | 08's *finale* framing (it becomes M6's simulation, not a climax) | notrest `2 → 6 → 0`; `~/Desktop` refused by **identity, not spelling**; protocol block **v3**, a v2 block is **STALE at exit 5**, not absent (`establish.py:979`) |
| **M4** | Instruments (cat. B) | Read six exit codes and say which blocks a ship | `modules/04`, `05`, `06`, `07` (spend half) | 04 whole (best module in the pack); 05's grade-three-ledger-lines drill; 06's *present→displayed→readable→navigable* ladder | 07's agentswarm half → moves to M5 | eval **exit 0 / 15 checks / 0.22s**; doctor **exit 5 / 12 checks**; spend **exit 4** (routing gate firing, not a bug); compile report **exit 3**; cockpit `0/5/6`; gate-check `0/2/3` |
| **M5** | Knowledge + judgment verbs (C, D) | Pick the right verb from the shape of the ask; read the router's own table | `router.sh:47-100`; `MAP§3`; FM of all 12 | 05's honesty-label content | — | router + oracle agree on **19 verbs** (ROUTE-TABLE-PARITY); ROUTE-CONFORMANCE is a **permanent SKIP by convention** (MAP.md:594) |
| **M6** | Arrangements + bridges (E, F) | Delegate lawfully; read a receipt you didn't write | `modules/07`; `MAP§2` swarm/beam/chatroom/gpt | 07's "two files you did not write" condition (briefs/ + spend ledger) | 07's "general multi-agent architecture" warn-off — now it *is* the topic | spawn-gate blocks `fork`, blocks an omitted `model`, blocks anything but explicit `opus`/`sonnet`; `NOTREST_GATE_OVERRIDE=1` permits **loudly** |
| **M7** | **The session, schematically** *(new — §3)* | Trace one prompt through all 7 events and name the file each step wrote | §3 below; all 11 hooks | 08's kill-and-continue drill as the *last third* | — | the full chain, exit codes per §3 |
| **M8** | **Adding a session / adding a tool** *(new)* | Stand up a new lane and ship a new skill that passes doctor+eval | §3 below; `golden-release-surface.txt`; `eval.py:892` | 02's establish beats | — | after adding a skill: doctor RENDER SURFACES "32-skill" claim must move to 33 **on four surfaces**; RELEASE-SURFACE count moves off **62** |
| **M9** | Close — honest limits, Monday | One habit, one project, one week | `modules/09` | Whole module | — | none |

**Handouts.** `cheatsheet.md` REUSE §The frame/§The loop/§The labels/§Exit codes/§Continuing someone else's build verbatim; RETIRE §The ten verbs table → replace with the 7-category card. `exercises.md` is 267 lines keyed 00–09 — re-key to M0–M9, reuse every success condition, add exercises for M1/M2/M7/M8.

**Release-shape obligations for every module:** the pack is 16 golden-surface files. Any file added/renamed/deleted **must** be edited into `evals/golden-release-surface.txt` in the same commit — `check_release_surface` FAILs both ways (a named file that doesn't exist, *and* a touched `docs/` path not in the list, `eval.py:906-925`). `CAPABILITIES.md:71-75` is already stale ("doctor.py (8 checks)", "eval.py (8 static law checks, 0.06s)") against the live 12/15/0.22s — do not copy those numbers into the pack.

---

## 3. The session simulation (M7), and the two "add" recipes

**One prompt, end to end** — each step names the hook and what it writes:

1. **SessionStart** → `hooks/session-start.sh` (338 lines). Echoes version + runtime (`v4.6.2 @skills-dir`, :25), the Fable anchor (:31), the offload HARD RULE (:37), a resume nudge if `START-HERE.md`/`HANDOFF.md` exist (:61,:64), the pulse reading (:235), the cockpit line (:210), the compile candidate (:309/:311). **Writes** `COORD.md` only if a git-backed estate has none (:111). Then the **AUTO-CONTINUATION packet** (:184) — `establish.py continuation --brief` under a 5s timeout (:170), guarded by an END marker so a crash-truncated half-packet is detectable. *Live shape verified: `root / ESTABLISHED protocol v3 / git+dirty / briefs banked / NEWEST SHIP / NEWEST GATE / NEWEST CORRECTION / LEDGER TAIL (8) / CONTINUABLE`.* Since 4.6.1 the packet **silences the resume nudges it duplicates** (:40-46) — a field-proven ~88k-token duplication.
2. **UserPromptSubmit**, in order: `coord-nudge.sh` (53 lines — ledger reminder, kicks a detached `estate-pulse.sh` if `pulse/pulse.json` is >30 min old, surfaces `pulse/swarm-live.txt`), then `router.sh` (109 lines — normalizes, exits silently on a slash command / a self-named verb / **under four words** (:40), else one ≤160-char nudge from the `case` chain at :47).
3. **Work.** The seat acts. Every `Bash` call passes **`pretool-gate.sh`** first (PreToolUse/`Bash`, timeout 300) — RULE 1 ship gate (no `git push` while doctor/eval red), RULE 2 shadow guard; blocks with **exit 2 plus `permissionDecision:"deny"`**; fail-open with a one-`case` fast path.
4. **Agent spawn** → **`spawn-gate.sh`** (PreToolUse `Agent|Task`, 144 lines). Refuses `subagent_type="fork"`, an omitted `model`, any model but explicit `opus`/`sonnet`. Override is loud.
5. **SubagentStop** → **`agent-ledger.sh`** (687 lines). Writes three things: a row in `COORD-AGENTS.md`; the lane's **verbatim first user-role message** as `briefs/agent-<id>.md` (:259-262, :440); a deduplicated receipt in `spend/ledger.md`. All shared writes via `fcntl.flock`. Fires a detached pulse refresh.
6. **Stop** → **`completion-gate.sh`** (181 lines, timeout 60) → runs `gate-check.py` (337 lines) over `gates/ACTIVE.md`. **No gates file → wholly inert** in every repo. Exits `0` green / `2` file missing / `3` contract unparseable; loop-guarded by `stop_hook_active`; fail-open *with a note on stderr*. **Teach the live gap:** MAP loose thread #1 — `gates/` does not exist in this repo, so the estate that wrote the vacuous-pass killer has not armed it on itself.
7. **SessionEnd** → `session-end.sh` (243 lines). The crash cushion: one COORD line if the session didn't close via `/sessionend`, plus the **volume roll** (COORD sealed byte-identical as `COORD-<NNN>.md` at ~500 lines, `COORD-AGENTS.md` at 1000), sealed-copy-fsync'd-first so an interruption never loses a line.
8. **The successor's packet** = step 1 again, now reading what steps 5–7 wrote. That loop is the whole argument.

**Adding a NEW session.** (a) *Role by prompt* — the lane's commission text sets the role; `agent-ledger.sh` banks that exact text to `briefs/`, which is what makes the role auditable. For a blackboard arrangement, `new-fable-project.sh <repo> D1:ship D2:research D3:content Q1:qc` — file-only, spawns nothing, refuses to clobber `COORD*.md` without `--force`. **There is no `NOTREST_ROLE`; do not teach one.** (b) *Establish in a fresh project* — `/notrest` → `establish.py check --root .` (expect **6**), `establish` (writes `COORD.md` + the marker-delimited v3 block, idempotent, byte-identical outside the markers, a hand-edited v2 body banked to `<file>.notrest-v2.bak`), `check` again (expect **0**). (c) *Continuation* — open a session in the established folder; SessionStart hands the packet; verify at **tier 0 only** (doctor + eval + git vs the packet's claims), tier 1 only if a gate was not green, tier 2 only on a contradiction — **the trail wins** (`cheatsheet.md:85-92`).

**Adding a NEW tool.** 1) `plugins/notrest/skills/<name>/SKILL.md` — dir name **must equal** front-matter `name`, description must load as YAML and carry a `/slash` trigger (eval TRIGGER-SANITY). 2) A worker skill needs a self-check section **and** a finishing-up/chains section (WORKER-CONTRACT, 25 skills today). 3) `scripts/<tool>.py` — must be *referenced by its own SKILL.md* and compile (SCRIPT-OWNS-SCANNING, 21 scanners today); no network beyond the loopback allowlist (NETWORK-EGRESS, 70 scripts scanned). 4) `scripts/fixture.sh` — 30 fixture files on disk today; `exit 0 = all assertions held`, built in a `mktemp` estate, touching no real project. 5) Every bare `references/`/`scripts/` path cited in the SKILL.md must exist (REFERENCES-CITED, 45 paths). 6) If it should be routable: add a `SKILL=`/`SHAPE=` arm to `router.sh`'s `case` chain **and** the matching verb to `oracle/SKILL.md`'s routing bullet — ROUTE-TABLE-PARITY fails on either alone (19 verbs today). 7) Add the SKILL.md (and any shipped script/fixture) to `evals/golden-release-surface.txt` in the same commit, with the reason in `CHANGELOG.md`. 8) Re-run: `eval` must stay exit 0; `doctor` will flag skill-count drift and the **rendered "N-skill" claim** on `README.md`, `plugins/notrest/README.md`, `docs/TUTORIAL.md`, the marketplace description **and** `docs/oracle-skill-flow.html` until all are updated (4.6.2 roster-parity check).

---

## 4. Open decisions for the owner

1. **Audience and length.** The current pack is 180 min for "people already burned by Claude Code" and teaches 10 verbs. The four movements are a *reference* arc covering 32 + 13 + 6 — that is a different product. Options: (a) keep 3h and teach the taxonomy with only ~10 verbs driven, table the rest; (b) go to a full day; (c) split into a 3h workshop plus a reference pack that isn't run in a room.
2. **Ten-module shape vs four movement files.** §2 keeps 10 slots so the 16 golden-surface filenames survive (fewer surface edits, and `RELEASE-SURFACE` FAILs on any file it names that stops existing). Moving to four movement files means deleting six paths and adding four — legal, but it must land in one commit with a CHANGELOG reason.
3. **Full page vs table row, for 32 tools.** Movement 3 says "each tool with explanation" — 32 full pages is ~2,000 lines. Recommended cut: full page for the 4 bookends + the 7 instruments + `agentswarm`/`refuter` (13), table row for the remaining 19. Owner decides the line.
4. **Which taxonomy is canon.** MAP.md§3 (9/12/7/4), CAPABILITIES.md (3 headings), and §1 above (7) all disagree. The workshop should not be the fourth. Pick one and let the others cite it.
5. **Whether the pack quotes doctor's warn count.** It is release-state-dependent (3 warns now, 2 after the v4.6.2 commit). Recommend teaching *the exit code* (5) and "0 fail", never the warn tally.
6. **Whether to arm `gates/ACTIVE.md` on this repo before the pack ships.** M7 step 6 teaches a gate the estate has never armed on itself; that is either the pack's most honest moment or its weakest claim.
7. **Fixture count discipline.** `find … -name '*fixture*.sh'` → **30**; `COORD.md` 2026-09-02 00:58Z claims a "31/31" battery. Resolve before either number goes in a handout.

### Critical Files for Implementation
- /Users/ethanabot/Desktop/oracle-suite-plugin/docs/MAP.md
- /Users/ethanabot/Desktop/oracle-suite-plugin/evals/golden-release-surface.txt
- /Users/ethanabot/Desktop/oracle-suite-plugin/plugins/notrest/hooks/hooks.json
- /Users/ethanabot/Desktop/oracle-suite-plugin/plugins/notrest/skills/eval/scripts/eval.py
- /Users/ethanabot/Desktop/oracle-suite-plugin/docs/workshop/FACILITATOR.md