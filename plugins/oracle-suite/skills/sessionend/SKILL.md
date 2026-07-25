---
name: sessionend
description: Capture session state into four continuity files — START-HERE.md (ordered resume instructions), HANDOFF.md, STATE.md, and CLAUDE.md (the foundation, merged never clobbered) — verify a memoryless session could resume from them alone, then in multi-session environments open the live line to the successor (references/live-handoff-template.md). Use on /sessionend or when the user asks to end/wrap up the session, save state, or write a handoff. Works in Claude Code, Cowork, and chats.
---

# Session End — Handoff & State Capture

Run at the end of a working session to snapshot everything the *next* session needs to pick up exactly where this one stopped. It produces a small set of continuity files and — critically — a `START-HERE.md` that tells the next session what to read and what to do, in order. This is the bookend to the `oracle` intake: `oracle` loads context at the start, `sessionend` saves it at the end.

**Each file has a distinct job — they don't overlap:** `CLAUDE.md` = the stable **foundation** (how you work + tooling + conventions + infrastructure + per-project pointers), auto-read by Claude Code at repo root; `HANDOFF.md` / `STATE.md` = this session's **volatile status** and decisions; `START-HERE.md` = the ordered **resume instructions**. A fifth file exists beside these four but is not written here: `COORD.md`, the hook-owned **per-prompt ledger** — written all session long as work lands, the tiebreaker when the status files disagree; sessionend only appends its closing line (Phase 3.6) and compacts it. Volatile things never go in the foundation; the foundation is never restated in the status files.

## When to run
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
Two one-command closes, run after the files are written:
- **archivist** installed and the project has ORACLE output folders → re-run its `scan` so
  `oracle-index.md` includes every dossier this session produced; the next session's oracle
  intake then starts already knowing the estate.
- **spend** installed and this session spawned agents / workflows / gpt calls → run its
  `report` and paste the verdict line into `HANDOFF.md` — and any ROUTING VIOLATIONS
  verbatim, never smoothed.
Skip silently only when the skills aren't installed.
- A **recap** was produced this session → put its map/dossier paths in `HANDOFF.md` (the
  decision track is part of the handoff).
- **watch** installed and `watch/watchlist.md` exists → note which rows are **due** (last
  checked + cadence ≤ today) in `HANDOFF.md`, so the next session inherits the calendar and
  not just the conclusions. Don't run the cycle here; just say what's due.
- **COORD.md** present (the session coordination ledger) → append the closing line:
  `- [UTC] [sessionend] session closed: <one-line outcome> | handoff: START-HERE.md` —
  and if the ledger has grown past ~40 lines, compact the oldest entries into
  `COORD-ARCHIVE.md` now so the next session reads a short tail.
- **COORD-AGENTS.md** present (the hook-written agent activity ledger) and grown past
  ~100 lines → compact the oldest entries into `COORD-AGENTS-ARCHIVE.md` so the next
  session reads a short tail. It's machine-written — never hand-edit the entries, only
  move whole oldest lines into the archive.

## Phase 4 — Verify resumability (self-check)
Before finishing, confirm — and fix any miss:
- **Could a fresh session with zero memory resume from `START-HERE.md` alone?** It must name what to read and what to do, in order.
- Every "next step" is concrete and correctly ordered.
- `STATE.md`/`HANDOFF.md` reflect what *actually* happened — no invented decisions or code; half-done work marked as such — and they agree with the `COORD.md` ledger tail (the trail is the tiebreaker: it was written when the work landed).
- `CLAUDE.md` (the foundation) was **merged**, not overwritten, and only stably-true things were added to it (volatile status stayed in HANDOFF/STATE).
- All cited paths/commands are real.
- If archivist/spend are installed: the index was re-scanned after the last dossier landed, and the spend verdict line is in `HANDOFF.md`.
- In a chat: every file was presented for download with the re-upload reminder.

## Phase 5 — Open the live line (multi-session environments only)
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
4. CLAUDE.md — the foundation: how you work + infrastructure (auto-read in Code)

## Then do this, in order
1. <first action to resume>
2. <next> …

## Watch out for
- <the top gotcha / blocker the next session will hit>
```

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

### `CLAUDE.md` — the foundation (update/merge, by the bundled template)
The single, long-lived foundation file, auto-read by Claude Code at repo root. It holds what's stably true: how you work (protocol), tooling defaults, cross-project conventions, shared infrastructure, and short per-project pointers (including this repo's run/build/test specifics in its own project section). It is **not** volatile status — that's HANDOFF/STATE. Use the bundled **`references/claude-foundation-template.md`** as its canonical structure, and apply its discipline every time:
- **Earn-its-line test** — keep a line only if the next session would otherwise re-explain it, get it wrong, or burn tokens rediscovering it. Cut everything else; the foundation works by being small and solid, not comprehensive.
- **Merge, never clobber** — update the existing file in place; preserve its history and the user's wording.
- **Promote up** — if the same thing is true in two project sections, move it to Cross-Project Conventions (Part 3) or Shared Infrastructure (Part 4).
- **Budget & prune** — keep each project section to ~15–20 lines; cut lines unused for several sessions; archive inactive projects out of the file entirely.
- **Status stays out** — anything volatile (current progress, blockers, next steps) belongs in HANDOFF/STATE, not here.
Update the **Last updated** date, and for the current project touch only its Part 5 section — promoting anything genuinely shared up to Parts 3/4. **Normally `oracle` scaffolds this file at session start, so here you usually just *update* it; if it's missing (a session that didn't start with `oracle`), scaffold it from the template.**

## Finishing up
Give the user a short chat summary: what was captured, where the files are, and the one most important thing for next session. In a chat environment, present **all** files for download and remind them to re-upload next session. Don't paste the file contents into chat — point to them.

## Notes
- Bookend to `oracle`: this session's `START-HERE.md` is what the next session (or the next `oracle` intake) reads to resume, and `CLAUDE.md` is the foundation it loads.
- Accuracy beats completeness. A short, true handoff is worth more than a long, embellished one.
- Keep `STATE.md` from bloating: capture load-bearing decisions and snippets; reference files for the full detail rather than pasting everything.
- The foundation (`CLAUDE.md`) grows slowly and gets pruned; the status files (`HANDOFF`/`STATE`) carry the churn. Keeping that split is what stops `CLAUDE.md` from rotting.
