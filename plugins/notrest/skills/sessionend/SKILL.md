---
name: sessionend
description: Capture task/session state into four continuity files — START-HERE.md, HANDOFF.md, STATE.md, and the runtime foundation (AGENTS.md on Codex, CLAUDE.md on Claude; merged, never clobbered) — verify a memoryless successor can resume, then open a live line when the host exposes one. Use on /sessionend or asks to wrap up, save state, or write a handoff.
---

# Session End — Handoff & State Capture

## Runtime adapter (applies to the whole skill)

Set `FOUNDATION` to `AGENTS.md` on Codex and `CLAUDE.md` on Claude. Every unqualified
`CLAUDE.md` instruction below means `FOUNDATION` on Codex. Use
`references/agents-foundation-template.md` for Codex and
`references/claude-foundation-template.md` for Claude. Do not create both unless the
project explicitly serves both runtimes.

Resolve `<plugin-root>` from this selected `SKILL.md` (two directories above this skill
directory) and substitute its absolute path before running a command; never execute the
placeholder literally. Claude may use `CLAUDE_PLUGIN_ROOT` as the same value.

Codex task/thread tools replace Claude session tools when exposed. Never create a new task
unless the user asked. If no live wire is available, the four files plus COORD are the
handoff and the skill says so. Claude's SessionEnd hook is a Claude-only cushion; on Codex,
run the explicit closing steps and never claim that hook fired.

Run at the end of a working session to snapshot everything the *next* session needs to pick up exactly where this one stopped. It produces a small set of continuity files and — critically — a `START-HERE.md` that tells the next session what to read and what to do, in order. This is the bookend to the `oracle` intake: `oracle` loads context at the start, `sessionend` saves it at the end.

**Each file has a distinct job:** `FOUNDATION` is stable project instruction;
`HANDOFF.md` / `STATE.md` hold volatile status and decisions; `START-HERE.md` is the ordered
resume path; `COORD.md` is the append-only per-prompt trail and tiebreaker. On Claude the
hook can roll and cushion it automatically; on Codex those closing actions are explicit.
Volatile things never go in the foundation; the foundation is never restated in status.

## When to run

**Router shape:** `handoff`

Run when the user invokes **/sessionend** (or clearly asks to end/wrap up the session, save state, or write a handoff). It's a deliberate end-of-session action — don't run it mid-flow unless asked.

## Where the files go (Code / Cowork / chats)
Detect the environment and write where files actually persist:
- **Claude Code:** write into the repo. `CLAUDE.md` goes at the **project root** so Claude Code reads it automatically — that's the whole point of making the foundation a CLAUDE.md. The status files (`START-HERE.md`, `HANDOFF.md`, `STATE.md`) go at root or a `docs/` / `.handoff/` folder if the project uses one. Commit-ready.
- **Cowork:** write into the working directory the user can see.
- **Claude.ai chats:** write to the outputs area, then **present every file for download** — and tell the user plainly that chats don't persist across conversations, so they must save these and **re-upload them at the start of the next session** (then run `oracle` / open `START-HERE.md` to resume).
If unsure where a project keeps docs, ask once or default to the project root.

## Honesty rules (the whole point is a *truthful* snapshot)
- **Capture what actually happened.** Never invent decisions, code, or status. If a thing was tried but not finished, say "in progress." If code was written but not run, say "untested." A confident-but-wrong handoff makes the next session build on sand.
- **Mark uncertainty.** Flag anything unverified, assumed, or half-done — don't smooth it into "done."
- **Update, don't clobber.** `CLAUDE.md` (the foundation) is long-lived — **merge** new learnings into the existing file; never overwrite its history or the user's wording. `STATE.md` is append-only (add this session, keep prior). `START-HERE.md` and `HANDOFF.md` are current-snapshot (replace).
- **Real references only.** Every file path, function name, and command you cite must be real and current — no plausible-sounding fictions.

## Phase 1 — Reconstruct the session
Review the conversation/work and extract, accurately:
- **Goal** of the session and how far it got.
- **What got done** (concrete outcomes, files created/changed).
- **Decisions made** — each with its *why* and the alternatives weighed.
- **Code & changes** — the key snippets and what changed where (not a full dump; capture the load-bearing parts and point to files for the rest).
- **In progress / half-done** — what's started but incomplete, and its current state.
- **Blockers & open questions** — what's stuck or undecided.
- **Next steps** — the immediate actions to resume, in order.
- **Foundation-worthy learnings** — anything stably true (a convention, a machine/path, a gotcha) that earns a place in `CLAUDE.md` rather than the volatile status files.

## Phase 2 — Locate environment & existing files
Detect the environment (per above) and find any existing `START-HERE.md`, `HANDOFF.md`, `STATE.md`, `CLAUDE.md` to decide create-vs-update for each. Read the existing ones before changing them.

## Phase 3 — Write/update the four files
Write each per its spec and create-vs-update rule (below).

## Phase 3.5 — Deposit into memory (if a memory layer exists)
If the environment has writable persistent memory — Claude Code auto-memory, or a memory MCP with a
write tool (e.g. `remember`) — deposit a 5–10 line handoff digest: project · date · what shipped ·
what's in progress · the next step · pointer to `START-HERE.md`. Future sessions can then recall the
handoff even without the files in front of them. The files remain the source of truth; memory is the
finding aid.

## Phase 3.6 — Close the estate: index + spend (if those skills are present)
One-command closes, run after the files are written:
- **archivist** installed and the project has ORACLE output folders → re-run its `scan` so
  `oracle-index.md` includes every dossier this session produced; the next session's oracle
  intake then starts already knowing the estate.
- **spend** installed and this session spawned agents / workflows / gpt calls → run its
  `report` and paste the verdict line into `HANDOFF.md` — and any ROUTING VIOLATIONS
  verbatim, never smoothed.
- **compile** installed → run its scan, `python3 <compile-skill>/scripts/compile.py scan
  --root .` (script-only, zero model tokens — the same spirit as the archivist re-scan). If
  it reports ripe NEW candidates, **name the top one in `HANDOFF.md`** ("repeated work worth
  compiling: `<slug>`, seen N×") so the next session inherits the finding instead of
  rediscovering it — the SessionStart hook will surface it too, but the handoff is what a
  cold reader reads first.
- **graph** installed → refresh both pictures the estate closes on — script-only, zero model
  tokens, the same spirit as the archivist re-scan. Guard each with a one-line existence
  check; **`sessionend` must never die on a missing sibling**:
  ```bash
  G="<plugin-root>/skills/graph/scripts/graph.py"
  if [ -f "$G" ]; then
    python3 "$G" scan  --root .            # the file graph, refreshed
    python3 "$G" river --root . --no-open  # the journey, banked at close
  else echo "graph.py absent — graph refresh skipped"; fi
  ```
  Expected output — one summary line each, written to stdout (the counts are the project's;
  `river` adds its `data:` line and any notes):
  ```
  <repo>/graph/graph.html: <N> nodes, <M> edges (git listing, 0 skipped)
  <repo>/graph/river.html: <N> records · <C> channels (0 merged, 0 dead-end) · <R> rocks (0 resting on refuted) · <B> backtracks · <M> milestones · mode=findings+coord
    data: <repo>/graph/river.json
  ```
  Read those lines; don't parse them — `graph` owns the field list and adds to it. What you
  need from them is that both files were written and `mode=` says which inputs the river had.
  The `scan` is what graph's own chain line already promises happens here, so the next
  session's `oracle` opens on a current map instead of a stale one. The `river` banks the
  journey the ledger just finished writing — `mode=findings+coord`, or `mode=coord-only` plus
  a note when `archive/findings.jsonl` is absent. `--no-open` because a closing session must
  never pop a browser. If either command is missing its script or exits non-zero, **note it in
  `HANDOFF.md` and close anyway**: a refreshed picture is a courtesy to the next session, never
  a gate on this one's close.
- **doctor** installed → bank a closing heartbeat, guarded exactly like the graph block above:
  ```bash
  P="<plugin-root>/skills/doctor/scripts/pulse.sh"
  if [ -f "$P" ]; then bash "$P" --if-stale 1 --root .
  else echo "pulse.sh absent — pulse skipped"; fi
  ```
  `--if-stale 1` because a pulse banked within the last hour is still the truth about this
  estate: the door prints `pulse: fresh (…)` and returns without running one instrument.
  Otherwise it runs every read-only instrument and appends its own `[pulse]` line to `COORD.md`,
  so the ledger's last word on this session is a measured verdict rather than a claim. Exit 1
  means an instrument wants a human — **note that line in `HANDOFF.md` and close anyway**, same
  rule as the graph refresh. **The overlap with the block above is deliberate:** a full pulse
  re-runs `river` and `scan`, both idempotent and both zero model tokens, so the repeat costs a
  few seconds and changes nothing. Restructuring the phase to dodge a harmless repeat would cost
  more than the repeat does — and the redundancy means the close still gets its pictures if
  either caller is ever skipped.
Skip silently only when the skills aren't installed.
- A **recap** was produced this session → put its map/dossier paths in `HANDOFF.md` (the
  decision track is part of the handoff).
- **watch** installed and `watch/watchlist.md` exists → note which rows are **due** (last
  checked + cadence ≤ today) in `HANDOFF.md`, so the next session inherits the calendar and
  not just the conclusions. Don't run the cycle here; just say what's due.
- **COORD.md** present (the session coordination ledger) → append the closing line:
  `- [UTC] [sessionend] session closed: <one-line outcome> | handoff: START-HERE.md`.
  **Never compact it.** The ledger is permanent bookkeeping; it ROLLS INTO VOLUMES
  instead. `COORD.md` is the ACTIVE volume; past ~500 ledger lines the hook seals it
  WHOLE as the next `COORD-<NNN>.md` (001, 002, …) and starts a fresh active volume
  that opens with a `> Continues COORD-<NNN>.md · volume <N>` line. Sealed volumes are
  immutable — never edited, never appended to, never deleted.
- **COORD-AGENTS.md** present (the hook-written agent activity ledger) → same law at
  ~1000 lines, sealed as `COORD-AGENTS-<NNN>.md`. Machine-written: never hand-edit.
- **Why sealing, not archiving:** archiving MOVES lines (a crash window on every
  compaction, and the archive is never actually read); sealing PRESERVES them —
  immutable, complete, chronological. Sessions read only the ACTIVE volume's tail, so
  a resume stays short, while `/recap`, `/compile` and `/archivist` read every volume
  in order for full history. Legacy `COORD-ARCHIVE.md` / `COORD-AGENTS-ARCHIVE.md` are
  the retired scheme: leave them exactly as found, never migrate them.

**The SessionEnd hook is the always-on cushion under all of this.** `hooks/session-end.sh`
fires whenever a session terminates — clean exit, `/clear`, crash, closed terminal — and does
two things silently, at zero model tokens: it appends one `[hook] … auto-cushion …` line to
`COORD.md` when the last ledger line is neither a `[sessionend]` close nor already a cushion,
and it enforces the volume law above (COORD.md >500 ledger lines → sealed whole as the next
`COORD-<NNN>.md`, fresh active volume; COORD-AGENTS.md >1000 → `COORD-AGENTS-<NNN>.md`), sealed
copy fsync'd before the active file is atomically replaced. So `/sessionend` never
*has* to run for the ledger to stay short and resumable — but it remains the deliberate,
richer close: the four continuity files, the estate closes, the honest one-line outcome the
hook cannot know. Read the signal in reverse when you resume: a cushion line in the tail means
the previous session ended abruptly and its status files may lag the ledger; a `[sessionend]`
close means someone finished on purpose. The cushion's one limitation, by design — it cannot
tell a session that did real work from one that only read, so the dedupe guard is simply "never
two cushion lines in a row."

## Phase 4 — Verify resumability (self-check)

**Run the lint first — it is the mechanical floor under everything below** (script-only, zero
model tokens):
```bash
python3 "<plugin-root>/skills/sessionend/scripts/starthere_lint.py" \
  check --file START-HERE.md --root .
```
Exit **0** clean · **5** warnings (advice, never a gate) · **6** a FAIL · **2** usage. **A FAIL
means the file is not finished** — repair it and re-run before you close. Five rules, each
naming the offending line: `NO-NEXT-ACTION` (no section says what to DO next — status, a
read-order and a "Run it" section are not a resume instruction), `NEXT-ACTION-NOT-ACTIONABLE`
(the section exists but carries no command and no verb-led step — status prose in a
next-action costume), `DEAD-REFERENCE` (a cited path does not exist under `--root`, and the
finding names where it actually lives), `NO-STATE-ANCHOR` (nothing names where the trail lives,
so a cold reader cannot check the status it was handed against anything), and
`UNRUNNABLE-FROM-CLEAN-CLONE` (an instruction stands on a **gitignored** artifact — `.venv`,
`.engine`, a built dir — and the file never says how to recreate it; it exists here and will
not exist there). Warnings add `RECREATE-ELSEWHERE`: the bootstrap exists but only as a
*pointer* to another file. `--fix-hint` prints the minimal skeleton that satisfies it, plus a
recreate skeleton per artifact when the clean-clone rule fires — **prints only; sessionend
writes the file, the lint only judges it.** `scripts/fixture.sh` is its self-test (107 asserts,
zero model tokens).

**Why the clean-clone rule (the same defect class, second bite — rig.rest, 2026-07-31).** That
`START-HERE.md` cited commands a fresh clone could not run: the artifacts they stand on
(`.venv`, `.engine`) are gitignored, and the command that recreates them lived in a different
file. `DEAD-REFERENCE` passed it — **in the working tree those paths exist**. The lint proved a
path was PRESENT; it never proved a command was RUNNABLE BY A STRANGER. So the rule asks `git
check-ignore` (index-aware, so a tracked file matching an ignore rule still counts as shipped)
and then looks for a recreate step in the same file. It reads *instructions*, not prose — a
sentence that merely mentions an ignored directory is not an order to use it — and it judges
only paths that **exist**, so a path both ignored and missing stays one finding under
`DEAD-REFERENCE`. When `--root` is not a git repo the rule **skips and says so**; it never
guesses.

**Why a script sits under a prose check (record F-20, 2026-07-27).** A cross-model acceptance
test handed a non-Claude loop a project directory and a `START-HERE.md` written an hour
earlier. The loop stated the project's status correctly and then **could not state the next
action — because the document never did**: it carried status where this contract promises
*ordered resume instructions*. The file read perfectly to its author, and this very
cold-reader prose check had already passed it. A document is not finished because its writer
recognises it. So the mechanical check runs first and the judgment below runs on top of it —
**the lint cannot tell you the plan is right, only that a stranger can find one.**

Then confirm — and fix any miss:
- **Could a fresh session with zero memory resume from `START-HERE.md` alone?** It must name what to read and what to do, in order.
- Every "next step" is concrete and correctly ordered.
- `STATE.md`/`HANDOFF.md` reflect what *actually* happened — no invented decisions or code; half-done work marked as such — and they agree with the `COORD.md` ledger tail (the trail is the tiebreaker: it was written when the work landed).
- `CLAUDE.md` (the foundation) was **merged**, not overwritten, and only stably-true things were added to it (volatile status stayed in HANDOFF/STATE).
- All cited paths/commands are real.
- If archivist/spend are installed: the index was re-scanned after the last dossier landed, and the spend verdict line is in `HANDOFF.md`.
- If graph is installed: `scan` and `river` both ran and printed their summary lines — or the one that didn't is named in `HANDOFF.md`, and the close went ahead regardless.
- In a chat: every file was presented for download with the re-upload reminder.

## Phase 5 — Open the live line (multi-session environments only)

> **The successor can also knock first.** A fresh session in the same folder can open the line itself with `/notrest` — its continuation ritual asks the previous same-cwd session as a mentor — **with no `/sessionend` required**, so a session that died mid-build is still continuable.
Files are lossy; the ending session's context is not. Where session-to-session tools exist
(Claude Code desktop: `list_sessions` / `send_message` / `search_session_transcripts`), the handoff
gets a second layer — full protocol and message templates in
**`references/live-handoff-template.md`**. **When context is near-full and the user asks for a new
session, this protocol IS the answer**: run this skill fully — *files first, always* — then the
**owner** creates the successor (a one-click owner action; the harness has no create-session tool),
and the **escort is this session's duty**, not the owner's. In short:
1. **Don't close this session after writing the files.** Tell the user to keep it alive until the
   successor confirms it's oriented; give them the paste-ready successor opener from the template.
   **Record the line in `START-HERE.md`**: add the "Live line:" row (this session's title, and id if
   known) so the successor's `oracle` intake knows exactly whom to call — and when more than one
   predecessor is alive (proven: two at once), the row becomes a **LIST**, one row per live session
   naming the domain it can answer for.
2. When the successor exists, **proactively send it the six-part orientation message** (state in 3
   lines · predictable questions answered · **honest unknowns** · decisions that are the user's ·
   gated actions · open line). `send_message` prompts the user each time — that's the consent gate.
3. **Escort it through the window** — the template's **"The escort window (first ~10 successor
   responses)"**: stay alive and *watch* (read its recent turns with `list_events` after each of your
   wakes), proactively correcting it when it's missing context, going wrong, or re-deriving what you
   already know. Answer from full context, marking fact vs recommendation vs user's-call; the
   `COORD.md` / `COORD-AGENTS.md` tails are the first referral answer, and discoveries get written
   back into the continuity files (docs stay truth; the line is a patch channel). Stand down at ~10
   responses or on its explicit "oriented" — write the final COORD line; **the owner** archives.
In plain chats, skip this phase — but note the successor can often still search old transcripts.

## The files

### `START-HERE.md` — the entry point (create/replace)
The master index the next session opens first. Plain and ordered.
```markdown
# Start Here — <project/session name>
**Status in one line:** <where things stand>
**Live line:** previous session "<this session's title>" (id <sessionId if known>) — still alive;
message it your setup questions before building. If closed, search its transcript.

## Read these first, in order
1. HANDOFF.md — where we are and what's next (the curated snapshot)
2. COORD.md — the ledger tail: the per-prompt trail with evidence, current to the
   last prompt even if this handoff is stale or the session died before sessionend
3. STATE.md — decisions made + code/changes (newest at top)
4. <FOUNDATION> — AGENTS.md on Codex or CLAUDE.md on Claude

## Then do this, in order
1. <first action to resume>
2. <next> …

## Watch out for
- <the top gotcha / blocker the next session will hit>
```
**"Then do this" is the load-bearing section, and the one that goes missing.** It must contain
imperative steps — a command, or a verb-led line — not a restatement of status; and each step
should say how the reader knows it worked. The heading wording is free (`NEXT ACTION`, `Next
steps`, `Resume`, `First action` and a bare numbered do-list all pass the lint) — what is not
optional is that *some* section tells a stranger what to do. Phase 4's
`scripts/starthere_lint.py` fails the file when it doesn't.

**And every command must run on a FRESH CLONE.** If a step stands on something gitignored — a
`.venv`, a vendored or pinned checkout, a built directory — the recreate command belongs **in
this file**, not one file away:
```markdown
## A fresh clone needs this first
`.venv` is gitignored — a clone arrives without it. Create it before anything below:
`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
```
A path that exists on the author's machine and nowhere else is the same F-20 defect wearing a
working command.

### `HANDOFF.md` — where we are (create/replace)
Plain-language, skimmable. The session's "read me first."
```markdown
# Handoff — <date>
- **This session did:** <what got accomplished>
- **Current status:** <done / in progress / blocked, plainly>
- **Next up:** <the immediate next move>
- **Open questions / blockers:** <or "none">
- **Must-know for next session:** <anything that would trip them up>
```

### `STATE.md` — decisions + code + changes (append; newest on top)
The receipts. Add this session's dated entry; keep all prior entries below it.
```markdown
## Session <date>
### Decisions
- **<decision>** — why: <reason>; alternatives considered: <…>
### Code & changes
- `<file>` — <what changed>; key snippet:
  ```<lang>
  <the load-bearing code>
  ```
### In progress (state it honestly)
- <what's half-done and exactly where it stands; untested? say so>
```

### `FOUNDATION` — the runtime foundation (update/merge, by the bundled template)
The single, long-lived foundation is `AGENTS.md` on Codex or `CLAUDE.md` on Claude. It
holds what is stably true and auto-loadable for that runtime. It is **not** volatile status.
Use the runtime template named at the top of this skill and apply its discipline every time:
- **Earn-its-line test** — keep a line only if the next session would otherwise re-explain it, get it wrong, or burn tokens rediscovering it. Cut everything else; the foundation works by being small and solid, not comprehensive.
- **Merge, never clobber** — update the existing file in place; preserve its history and the user's wording.
- **Promote up** — if the same thing is true in two project sections, move it to Cross-Project Conventions (Part 3) or Shared Infrastructure (Part 4).
- **Budget & prune** — keep each project section to ~15–20 lines; cut lines unused for several sessions; archive inactive projects out of the file entirely.
- **Status stays out** — anything volatile (current progress, blockers, next steps) belongs in HANDOFF/STATE, not here.
Update the **Last updated** date, and for the current project touch only its Part 5 section — promoting anything genuinely shared up to Parts 3/4. **Normally `oracle` scaffolds this file at session start, so here you usually just *update* it; if it's missing (a session that didn't start with `oracle`), scaffold it from the template.**

## Finishing up
Give the user a short chat summary: what was captured, where the files are, and the one most important thing for next session. In a chat environment, present **all** files for download and remind them to re-upload next session. Don't paste the file contents into chat — point to them.

## Notes
- Bookend to `oracle`: this task/session's `START-HERE.md` is what the successor reads to
  resume, and `FOUNDATION` is the stable instruction it loads.
- Accuracy beats completeness. A short, true handoff is worth more than a long, embellished one.
- Keep `STATE.md` from bloating: capture load-bearing decisions and snippets; reference files for the full detail rather than pasting everything.
- The foundation (`CLAUDE.md`) grows slowly and gets pruned; the status files (`HANDOFF`/`STATE`) carry the churn. Keeping that split is what stops `CLAUDE.md` from rotting.
