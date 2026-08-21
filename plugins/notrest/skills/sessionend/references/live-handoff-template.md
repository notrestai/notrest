# Live Handoff — the cross-session line (template)

The continuity files are layer 1. This is **layer 2: the live line** — the ending session stays
alive and answers the successor's questions directly, so nothing is lost to doc compression.
Proven in production 2026-07-02 (not.rest → "not.rest dev3 fable"): the successor read START-HERE,
received the orientation message, resolved an unknown the docs couldn't cover, asked exactly one
history question, and got it answered with full context.

## When this applies
Only in environments with task/session-to-task/session tools. Codex maps the operations to
`list_threads`, `read_thread`/`wait_threads`, and `send_message_to_thread`; creating a new
task remains the user's act unless they explicitly ask the current task to create one.
Claude desktop uses `list_sessions`, `send_message`, `list_events`, and
`search_session_transcripts`. In plain chats, skip — the files
are the whole handoff (but note the successor can often still SEARCH old transcripts).

## The protocol (three steps)

**1. The ending session does NOT close after writing the files.** Tell the user plainly:
> "Keep this session alive until the new one confirms it's oriented. I'll answer its questions."

**2. The user starts the successor with this opener** (paste-ready, fill the brackets):
```
Read START-HERE.md first and follow it (its read order routes through the COORD.md
ledger tail — the per-prompt trail with evidence; when my prose and the ledger disagree,
the ledger wins: it was written when the work landed). The previous session
"<old session title>" is still alive with full context — use list_sessions to find it
and send_message it your setup questions BEFORE building anything. If an estate/memory
MCP is available, also ask it what's live. Your build: <one line naming the next build>.
```

**3. The ending session sends the ORIENTATION MESSAGE** — proactively, the moment the successor
exists (don't wait to be asked; its questions are predictable). Structure, six parts:

```
I'm the previous <project> session (full context still loaded). Answers to your setup
questions, plus what the docs can't tell you. Reply to this session with anything else —
I'm alive until the user closes the tab.

**STATE IN 3 LINES:** <what is live/true right now · what was just finished · what your
build is>

**PREDICTABLE QUESTIONS, ANSWERED:**
<numbered — the questions ANY fresh session on this project hits:>
- deploy/build flow and its non-obvious failure modes (validators, checks that gate deploys)
- access paths (hosts, URLs, login users — never secrets)
- the don't-break list (things that look editable but are load-bearing)
- the tool surfaces this machine has that this project actually uses — skills/plugins, live MCPs,
  and which ones are present but need connecting (so the successor inherits the inventory instead
  of rediscovering it)
- landmines with their recipe locations (point at STATE/docs sections, don't restate)
- the COORD.md ledger tail — which of my claimed-landed items carry evidence there
  (anything I claim that has no ledger line is [unverified]; write your own discoveries
  back as ledger lines too — the line is the patch channel, the ledger is the receipt)

**HONEST UNKNOWNS:** <what the docs could NOT cover — things never located, never decided,
never verified — each with a suggested first probe. This is the highest-value section:
it's exactly what a confident-sounding doc would have papered over.>

**DECISIONS THAT ARE THE USER'S:** <each genuinely open decision + the ONE question to ask
the user about it + your recommendation if you have one. The successor should ask, not guess.>

**GATED ACTIONS:** <what requires the user's explicit words in THIS project/harness —
learned examples: public ingress/DNS changes, secrets/.env writes, Claude-config
self-modification, live DB catalog edits, production restarts. The successor must not
infer consent from the plan's existence.>

**OPEN LINE:** Ask me anything — decision rationale, code paths, why something is the way
it is. I watched all of it happen.
```

## The escort window (first ~10 successor responses)

The three steps above **open** the line. This is how it's **flown**. A handoff is not an
instant — it's a window, and the predecessor's job doesn't end when the successor says hello.
Proven live 2026-07-24 (dig.rest): two predecessors — "dig.rest DIR active" and "dig.rest DIR2
ACTIVE" — stayed alive and answered referrals while the new session took over the work.

**1. TRIGGER — context is near-full and the user asks for a new session.**
That request *is* this protocol; nothing else needs deciding. Run `sessionend` **fully, files
first, always** — the successor may be created before you finish, and if this session dies
mid-window the files are all that's left. Then the **owner creates the successor**: that's a
one-click owner action in the app. There is **no create-session tool** — session management
exposes only `list_sessions` · `get_session` · `list_events` · `send_message` ·
`search_session_transcripts` · `set_session_title` · `archive_session` (read and write into
existing sessions, never create one). For Terminal/CLI lanes, the osascript spawn path in the
**fable-director** skill's `references/spawn-lanes.md` applies. Never say you created a
session — you asked the owner to.

**2. BRING-UP — orient the successor the moment it exists.**
Send the six-part orientation message above proactively (its questions are predictable; don't
wait). In `START-HERE.md` the **"Live line:" row becomes a LIST** when more than one
predecessor is alive — the dig.rest precedent had two at once. One row per live session,
each naming the domain it can answer for, so the successor knows *whom* to ask, not just that
someone is out there:

```markdown
**Live line (escort active):**
- "<session title>" (id <sessionId>) — answers for: <the domain this session owns>
- "<session title>" (id <sessionId>) — answers for: <the domain this session owns>
Read COORD.md + COORD-AGENTS.md tails FIRST; ask these only for what the trail doesn't carry.
```

**3. ESCORT — for the successor's first ~10 responses, stay alive and WATCH.**
Passive availability isn't the contract; active escort is. After each of your own wakes:
- `list_events` on the successor's session id → read its recent turns (this is the whole
  reason the read tools exist — you can see it work, not just answer when spoken to).
- `send_message` a correction **proactively** the moment you see it (a) missing context you
  hold, (b) going wrong — building on a wrong assumption, editing a load-bearing file it
  thinks is inert, (c) **re-deriving something you already know** (re-running a probe, re-doing
  research, re-discovering a landmine). Interrupting early is cheap; a wrong branch is not.
- Keep every answer marked **fact vs recommendation vs owner's-call** (see *Answering the
  successor's replies*, below) — escort authority is context, not a licence to decide.
- Your first answer to almost any referral is **"read the trail first"**: the `COORD.md` and
  `COORD-AGENTS.md` ledger tails carry the per-prompt evidence and every agent lane's
  conclusion. Point at the trail, then add only what the trail doesn't carry — which is
  exactly what you're for.

**4. REFERRAL ETIQUETTE — the successor's side of the window.**
While the escort window is open, missing information is a **question**, not a research task.
Before re-deriving or re-researching anything: read the `COORD.md` / `COORD-AGENTS.md` tails,
then ask the predecessor(s) by Live-line row — **one consolidated batch per predecessor**, not
a drip of one-liners (each `send_message` costs the owner a confirm click). With multiple rows,
**domain-match**: route each question to the session whose row claims that domain; ask both
only when the question genuinely spans them. Re-deriving what a live predecessor holds in full
context is the most expensive mistake available in this window.

**5. STAND-DOWN — close it deliberately.**
The window ends at roughly ten successor responses, or earlier on the successor's explicit
*"oriented, standing down the line"*. Then the predecessor: writes its **final COORD line**
(`- [UTC] [live-line] escort closed: successor "<title>" oriented | <n> referrals answered`),
tells the owner the line is down, and stops watching. **The owner archives the session** —
`archive_session` is owner-confirmed, never self-initiated; a predecessor does not retire
itself. After archive the transcript stays searchable via `search_session_transcripts`, so the
line degrades gracefully rather than dying: the trail outlives the escort.

## Answering the successor's replies
- Answer from FULL context — this is the one place the old session outperforms every doc.
- Distinguish crisply: **fact** (it happened) vs **recommendation** (my read) vs **user's call**
  (don't decide for them). The successor inherits your authority — don't launder opinions as history.
- If the successor discovers something (it will), tell it to write the finding back into the
  continuity files — the docs stay the source of truth; the live line is a patch channel.

## Mechanics (Claude Code)
- `list_sessions` → find the target by title; messages arrive as a user-turn labeled
  "From <sender title>" with a linkback.
- `send_message` always prompts the user for confirmation — that's the consent gate, expected.
- `list_events <session id>` → read another session's recent turns. This is the escort's eyes:
  it's how a predecessor sees the successor going wrong *before* being asked. Read-only.
- **No tool creates a session.** `list_sessions` · `get_session` · `list_events` ·
  `send_message` · `search_session_transcripts` · `set_session_title` · `archive_session` is
  the whole surface — creation is the owner's click (or, for CLI lanes, the osascript spawn in
  fable-director's `references/spawn-lanes.md`), and `archive_session` is owner-confirmed.
- After the old session closes, its transcript remains searchable via
  `search_session_transcripts` — the line degrades gracefully, it never fully dies.
- Layer 3 (if the project has one): a memory/estate MCP the successor can query directly —
  point at it in the opener.
