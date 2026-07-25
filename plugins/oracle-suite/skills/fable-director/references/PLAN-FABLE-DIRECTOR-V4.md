# PLAN-FABLE-DIRECTOR-V4 — "3 DEVS AND A RELAY" (the reusable edition)

**Supersedes V3.** V3 was the battle-tested field report; **V4 is the same machine promoted to
its final shape and packaged for reuse on any project**: the owner-christened topology
("3 devs and a relay", all lanes on the latest Opus — the `opus` alias, never a pinned
point-version), rotation as a first-class self-carrying ritual, and every rotation-killer
CRITICALLY flagged. Evidence base: one real production run
(tell.rest, 2026-07-05/06 — ~32 director bursts, 25+ directives, 5 shipped rounds
v0.153–v0.157, 6 confirmed bugs fixed incl. 2 donor-money, 2 adversarial reviews, 2 session
rotations, live archive/kickoff automation).

Companion file (REQUIRED, versioned together): **`_fable/KICKOFF-DIRECTOR.md`** — the
canonical director launcher prompt; the self-carrying chain link between director
generations. ⚠ CRITICAL: when this plan changes, update the kickoff file in the same commit.

---

## 0. Premise (evidence, one paragraph)

Route by **decision density × blast radius, per dollar**. The metered director's proven edge:
foreman decomposition (near-zero rework), judgment-on-briefs (caught every dev false positive
before damage), pre-ship gates, escalation triage, and — owner's inversion — **applying all
code** safely because devs hand exact EDIT SPECS and the director verifies each claim against
the file before cutting. The flat lanes' proven edge: volume with rigor — multi-agent sweeps,
adversarial refuter passes (killed 6/14 raw findings), full-ritual verification, honest scope
corrections. The owner stays above both: rulings, ships, secrets, billing, session creation.

---

## 1. Topology of record — "3 DEVS AND A RELAY"

```
  OWNER (rulings · ships · secrets · billing · session creation · confirm clicks)
     │
  DIRECTOR (claude-fable-5, metered, bursty; applies ALL code; judges; gates)
     │            one blackboard file PER LANE — the only wire
  ┌──┴───────────────┬───────────────────┬──────────────────┐
  dev-A SHIP lane     dev-B RESEARCH      dev-C CONTENT/OPS   QC — THE RELAY
  ritual·golden·tars  surveys·specs·web   seeding QA·checkl.  verifies EVERY brief,
  commits·STATE       research            assets·test specs   aggregates → 1 ping
  (latest-Opus flat)  (latest-Opus flat)  (latest-Opus flat;  to the director
                                           Sonnet valve OK)   (latest-Opus flat)
```

- **QC relay flow:** lanes end reviewable completions with `→PING-QC` (in their OWN file);
  QC watches all lane files for that token, verifies each brief via the §6 refuter checklist,
  kills false positives with evidence, then pings the DIRECTOR once per batch from ITS file.
  Escalations/blockers still go lane→director direct (SEV-1). **Director wakes go DOWN as
  lane count goes up.**
- **QC charter (hard):** originates nothing (no code, no specs, no surveys), approves
  nothing; pure adversarial verification + aggregation + completeness-critic; also owns the
  weekly context-fill probe, rotation recommendations, and compaction policing. Reads every
  file, writes ONLY its own.
- Scale down by not replacing a rotated lane (post-launch steady state ≈ 1–2 devs + QC).
- **Director model policy (fallback):** the director runs `claude-fable-5`; if Fable is
  UNAVAILABLE (it has been pulled/suspended before), fall back to the **latest Opus** —
  `--model opus` in the launcher (harness-resolved, no pin to update) or `/model opus`
  in-app — LOG the fallback in the ledger, and continue: the protocol is model-agnostic
  and every rule (§3/§4/§9) applies unchanged. The skill ships a probing launcher
  (`scripts/fable-launcher.sh`) that does this automatically. Lanes are NEVER Fable.
- ⚠ Subscription caps burn ~2× faster than a two-lane setup — watch weekly limits; drop
  dev-C to Sonnet for mechanical stretches first.

---

## 2. Roles — the never-list (each line was earned)

| | OWNER | DIRECTOR | LANES |
|---|---|---|---|
| Does | rulings, one-word calls, ships/DNS/secrets/billing, permission grants, session creation, confirm clicks | intent→directives, judges QC-verified briefs, **applies ALL code** (verify-before-apply), pre-ship gate, protocol+kickoff upkeep, rotation ritual | research, sweeps, EDIT SPECS, ritual-of-record, golden/tars/stage-by-name commits (ship lane), STATE (ship lane), QC verification (QC) |
| Never | — | explores the repo at large · runs the lanes' ritual as routine · **spawns in-session subagents (they bill the metered key — the lanes ARE the explorers)** · touches secrets/live boxes | edits app/engine/scripts/tests · ships · expands its own permissions (classifier blocks it BY DESIGN — owner must grant in-session) · send_message after bootstrap |

**Auth isolation, proof-not-promise:** the API key exists ONLY in the director's launcher.
Every session PROVES at bootstrap (ledger line): env has no ANTHROPIC_API_KEY/AUTH_TOKEN;
watches log task ids; hooks demonstrate a real denial.

---

## 3. The PING system ⚠ CRITICAL — the #1 historical failure

**An idle session cannot "watch" anything — it runs only when invoked.** A lane without an
ARMED watch sleeps through every burst (happened; cost three bursts). The mechanism:

- Background watch per side, per file (detached, `run_in_background`):
  ```
  f="<ABS PATH TO COORD FILE>"; base=$(grep -E 'PING-<WHO>$' "$f" | tail -1 | md5); while :; do sleep 20; cur=$(grep -E 'PING-<WHO>$' "$f" | tail -1 | md5); [ "$cur" != "$base" ] && exit 0; done
  ```
- Tokens per-recipient, **END-ANCHORED** (`$`): →PING-DIRECTOR · →PING-DEV7 · →PING-QC …
  ⚠ token at LINE END only, when actually pinging — a mid-prose mention false-fires
  (paid for twice; the anchor helps, the hygiene rule stays).
- Ping ONLY on trigger events (drained · brief ready · escalation · blocked); batch,
  never per-directive — every director wake is a cold read.
- ⚠ Re-arm: lanes at EVERY idle; director at EVERY burst-close. Proof = the task id in the
  ledger. Watches die with the app; fallback = the owner opens the session.
- ⚠ Queued ≠ delivered: after posting directives, the wake must be VERIFIED (the ACK ledger
  line), not assumed.
- **send_message = bootstrap/rotation-only** (it always prompts the owner; dies in `auto`
  mode). The files are the wire.

---

## 4. Edit authority ⚠ CRITICAL — who touches code

**Code changes are the DIRECTOR'S hands only.** Lanes hand EDIT SPECS
(`file · exact location · before→after · why · risk`); doubtful/beyond-capacity → owner
first. The three safety legs (keep all three):
1. **Verify-before-apply** — the director reads the target region AND greps the claim:
   callers, route/dispatch layer (string-keyed, onclick, window.*), and **test harnesses**
   (a "dead" function was unit-tested by the smoke suite; a "never-passed" param was live on
   an API route; a "dead" prompt-half fed the shaping model — all caught here).
2. The director MAY run cheap verification while applying (py_compile, focused pytest, even
   the full ritual pre-handoff). The ship lane still owns the ritual-of-record, golden
   re-bases (only on the director's explicit line / pre-approved exact-diff list), tars,
   stage-by-name commits, version bump every round.
3. **The classifier boundary:** lanes CANNOT self-expand permissions on a cross-session
   directive ("[Self-Modification]" denial — by design). Owner grants in-session
   (/fewer-permission-prompts). Deny-HOOKS in shared .claude/settings.json are fine when the
   owner approves live; broad allowlists live in each lane's git-ignored settings.local.json.

---

## 5. Files & ownership — one blackboard per lane

- `COORD.md` (ship lane) · `COORD-<LANE>.md` each other lane · shared
  `COORD-ARCHIVE.md`. ⚠ Two writers on one file = live edit collisions (observed).
  Lanes READ any file, WRITE only their own; the director writes DIRECTIVES + →A answers
  in each.
- Scaffold per file: header (who writes what; this file is the only channel) · PROTOCOL
  (the numbered rules incl. this plan's §3/§4 + the lane's watches VERBATIM) · STATE
  (ship-lane file only — owner-confirmed live reality, never inferred) · DIRECTIVES
  (`- [ ] D-001 →lane P0 OBJECTIVE/CONTEXT/CONSTRAINTS/DONE-WHEN(grep-able)`) ·
  ESCALATIONS · BRIEF-UP (≤40 lines) · QUESTIONS (+DEFAULT) · LEDGER (append-only,
  `date -u` stamps, [lane] tags, re-read tail before appending; expect and retry
  "modified since read" — use asserted python-heredoc appends on churning files).
- ⚠ Compaction: hard trigger at ~40 ledger lines → ARCHIVE (the director re-reads these
  files COLD every burst; size is a tax). QC polices it.
- Directors' burst agenda: QUESTIONS → ESCALATIONS → QC verdicts/BRIEF-UPs → objective →
  re-arm watches → close.

---

## 6. QC refuter checklist (codify in the QC file's PROTOCOL — every rule was paid for)

Route/dispatch-layer check on any "never-called/never-passed" claim · test harnesses in
every ref-sweep scope · string-name greps (onclick/event maps/window.*) ·
does-the-output-feed-something-downstream on any "dead output" claim · [doc]/[vendor]/
community labels + TWO sources on load-bearing external claims · independent scope
re-estimate (honest-scope corrections beat optimistic ones) · concrete failure scenario
required (inputs → wrong outcome) or the finding is PLAUSIBLE, not CONFIRMED.

SEV levels: SEV-1 = wake the director now (blocker, money-path, invariant breach) ·
SEV-2 = batch at next wake · SEV-3 = FYI, no token.

---

## 7. Review machinery (unchanged from V3 — it held)

Agentic reviews run on LANE flat tokens, dimension-fanned (correctness · races · money ·
security-delta · invariants/offline). Findings: severity · file:line · concrete scenario ·
CONFIRMED/PLAUSIBLE · one-line fix. **Adversarial refuter pass mandatory per finding**
(now QC's job). After the director applies fixes: **review-the-fix** by a different lane
than the finder. Residual LOWs get explicit accept-and-park ledger entries. The project
CLAUDE.md's hard-invariants + paid-for-pitfalls sections are the review SPEC — keep both
current; the whole quality system leans on them.

---

## 8. Ship gate (owner executes, always)

The ship lane preps a SHIP BLOCK: **fresh-named tar + inline member-verify chain that
fail-STOPs before anything leaves the machine** (grep each changed file's marker inside the
tar) · single-line comment-free shell-safe blocks · version bump every round (the director
bumps when applying; the version string is the live-confirm anchor) · post-ship proof steps.
The director runs a final gate check — proving each verify-grep against the tree — then hands
the blocks to the owner verbatim. Old origin stays warm as rollback. Live state is only ever
what the OWNER confirms.

---

## 9. ROTATION ⚠ CRITICAL — the self-carrying handoff (why this whole design survives)

**Everything lives in files; sessions are disposable.** Rotation is therefore cheap — IF the
ritual is followed exactly.

**Trigger:** the owner tells the sitting director:
`"context getting full — rotate; new sessions: <director-name> / <lane names…>"`

**The sitting director then does ALL of this:**
1. TRUE the open-threads block (ship-lane file, PROTOCOL "DIRECTOR RESUME" section) while
   its context still holds — live version, unconfirmed steps, launch/parked lists, deferred
   plans (pointer to memory/).
2. Send `_fable/KICKOFF-DIRECTOR.md`'s BODY to the owner-named fresh director
   (send_message; owner confirms).
3. Archive retired lane sessions (archive_session; owner confirms each).
4. STAY ALIVE, silent, as fallback — until the successor's first ledger line lands (the
   predecessor's still-armed watch catches it). Then the owner archives the predecessor
   (or it archives "self" on the owner's word).

**The fresh director then:** reads this plan → every coord file end-to-end → re-arms a
director watch per file → bootstraps owner-named fresh lanes onto the EXISTING blackboards
(one send_message each) → first directive everywhere: **compact inherited ledger → auth
proof → drain by priority**.

**⚠ ROTATION-KILLERS (each observed or near-missed — check every one):**
- A lane bootstrapped without ARMING its watch first = a deaf lane (the #1 failure; demand
  the task id).
- Archiving a session before its unfiled work is posted = lost work (stand-down order first:
  post partials as a handoff brief, kill watch, final ledger line).
- Two directors bursting simultaneously = split-brain (predecessor is READ-ONLY fallback
  after sending the kickoff).
- Token names not matching session naming (→PING-DEV7 must match the dev7 file's watch) =
  silent non-delivery.
- Skipping the inherited-ledger compaction = every future burst pays the history tax.
- Forgetting that transcript filenames ≠ session ids: map by content probe when measuring
  context fill (bytes ≈ 3–5× live tokens; valid as ranking only).
- The kickoff file drifting from the plan version = successors bootstrapping onto stale
  rules (update both in the same commit).

**Prompt transport, honestly:** the FILE path is the guaranteed wire (successors read
`_fable/KICKOFF-DIRECTOR.md` themselves); the MESSAGE path works but costs one owner
confirm-click per hop and dies in `auto`-mode sessions. Zero-touch is impossible by harness
design for APP-PANE sessions: their creation + confirm clicks are owner-side, forever.
(AMENDED 2026-07-06: CLI sessions ARE spawnable by the director via macOS Terminal
automation after a one-time owner grant — recipe + caveats in the fable-director skill's
`references/spawn-lanes.md`; the bootstrap rides the launch, removing the send-confirm too.) The owner's whole job:
create sessions · say the trigger phrase · click confirm.

---

## 10. DUPLICATION GUIDE — new project in ~20 minutes

1. Copy into the new repo root: this file + `_fable/KICKOFF-DIRECTOR.md` (fix its project
   name/paths) · create `COORD.md` + one `COORD-<LANE>.md` per lane from §5's
   scaffold (absolute paths into the watch commands; tokens named for YOUR sessions) ·
   `touch COORD-ARCHIVE.md` · `mkdir -p _fable _reports`.
2. Copy `.claude/hooks/deny-guard.py` + the PreToolUse block of `.claude/settings.json`;
   adapt deny patterns (deploy targets, ssh hosts). Owner approves it live in a lane session.
3. PREREQUISITES in the project's CLAUDE.md (the quality system stands on these): a
   hard-invariants list · a paid-for-pitfalls section · a one-command verification ritual.
   If they don't exist, the first directives create them.
4. Owner creates sessions: 1 director (metered key in the launcher ONLY) + lanes (flat,
   `auto` fine). Send each lane its bootstrap (template in the kickoff file / §9): read plan
   §2–§9 + your blackboard end-to-end · ARM YOUR WATCH FIRST (log task id) · auth proof ·
   drain. Proven opening sequence: D-001 auth proof · D-002 STATE from source-of-truth docs ·
   D-003 deny-hook with demonstrated denial.
5. Owner's standing knobs: one-word rulings · the ship gate · in-session permission grants ·
   the rotation trigger phrase.

---

## 11. Observed failure modes (V4 master list — all real)

Passive "watching" (no armed watch) · token-as-substring / mid-prose false fires ·
two writers one file · Edit read-state races on churning files (re-read + asserted appends) ·
staging overlap across rounds (harmless if ledgers list item-sets) · classifier denial on
self-permissioning (by design; owner grants) · **director-side subagents (metered burn;
owner killed it live — absolute rule)** · owner-instruction fidelity (execute the named
thing, not your improvement; ask first) · queued ≠ delivered (verify ACKs) · dev
false-positives without a refuter pass (6/14) · "dead" claims that skipped the test-harness/
route layer · coord-file bloat (compaction lag) · plan caps on flat (Sonnet valve) ·
self-serving rubric (the owner's blind judgment settles lane promotions, not this doc).
