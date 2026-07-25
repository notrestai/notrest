# Blackboard scaffold + templates (fable-director skill reference)

## 1. Coord-file scaffold — create ONE per lane, absolute paths filled in

```markdown
# COORD[-<LANE>].md — Fable-director ↔ <LANE> blackboard

<LANE>'s OWN wire (one coord file PER lane — no shared writes). Director writes DIRECTIVES +
→A answers HERE; <LANE> writes everything else HERE and ONLY here. Never write other lanes'
files (reading is fine). Never COORD-files outside this arrangement. Never send_message.
Owner sits above all. Protocol of record: PLAN-FABLE-DIRECTOR-V4.md (repo root).

## PROTOCOL
1. On wake: read THIS file end-to-end. Work →<LANE> directives by priority; flip [ ]→[x]/[!]
   with a LEDGER line + evidence when a DONE-WHEN resolves.
2. Never block on the director: 2 failed attempts → ESCALATIONS; taste/architecture calls →
   QUESTIONS (always with your DEFAULT); then move on.
3. READ-ONLY on the repo tree unless a directive grants named paths (ship lane: you own the
   ritual-of-record, golden re-bases only on the director's line, tars, stage-by-name
   commits, STATE). Never git add -A. Deploys/secrets = owner via paste blocks.
4. EDIT AUTHORITY: code changes are the DIRECTOR'S hands only — you hand EDIT SPECS
   (file · exact location · before→after · why · risk).
5. PING: on trigger events ONLY (drained · brief ready · escalation · blocked), append a
   LEDGER line ENDING with →PING-QC (reviewable work) or →PING-DIRECTOR (escalations/
   blockers, SEV-1). Token at LINE END only, never mid-prose. The director/QC pings you
   with a line ending →PING-<LANE>. RE-ARM YOUR WATCH AT EVERY IDLE (log its task id).
6. Ledger tag [<LANE>]; append-only; `date -u` stamps; re-read the tail before appending;
   compact past ~40 lines to COORD-ARCHIVE.md.

### <LANE> WATCH — re-arm at every idle (verbatim, run_in_background)
```
f="<ABS_PATH_TO_THIS_FILE>"; base=$(grep -E 'PING-<LANE>$' "$f" | tail -1 | md5); while :; do sleep 20; cur=$(grep -E 'PING-<LANE>$' "$f" | tail -1 | md5); [ "$cur" != "$base" ] && exit 0; done
```
### DIRECTOR WATCH on this file — re-arm at every burst-close (director, verbatim)
```
f="<ABS_PATH_TO_THIS_FILE>"; base=$(grep -E 'PING-DIRECTOR$' "$f" | tail -1 | md5); while :; do sleep 20; cur=$(grep -E 'PING-DIRECTOR$' "$f" | tail -1 | md5); [ "$cur" != "$base" ] && exit 0; done
```

## STATE  (ship-lane file ONLY — owner-confirmed live reality, never inferred)
## DIRECTIVES  (director writes; lane flips)
- [ ] D-001 →<LANE> P0  OBJECTIVE: bootstrap — adopt the protocol + prove auth isolation +
      arm your watch. DONE-WHEN: LEDGER line [<LANE>] — env has NO ANTHROPIC_API_KEY
      (subscription) + your model + THIS file's watch armed end-anchored (task id logged).
## ESCALATIONS →director
(none)
## BRIEF-UP →QC/director  (≤40 lines; EDIT-SPEC format for code findings)
(none)
## QUESTIONS →director  (taste-calls WITH a default)
(none)
## LEDGER  (append-only, newest at bottom)
- <HH:MM>Z [director] blackboard created; D-001 posted; bootstrap message sent.
```

For the QC file additionally paste into its PROTOCOL: the V4 §6 refuter checklist + SEV
levels, and: "QC arms a watch per LANE file grepping 'PING-QC$' + one on its own file for
'PING-<QC-NAME>$' (its own session name); verifies every brief vs the tree; aggregates;
pings the director ONCE per batch from THIS file; originates nothing; approves nothing."

## 2. Lane bootstrap message template (the ONE send_message per lane)

> You are <LANE>, the <role> lane in the Fable split for <project> ("3 DEVS AND A RELAY",
> PLAN-FABLE-DIRECTOR-V4.md). Read V4 §2–§9, then YOUR blackboard COORD-<LANE>.md
> end-to-end. ARM YOUR WATCH FIRST (verbatim in the file; run_in_background; log the task
> id) — without it you are deaf. Then drain D-001.. by priority. Never git add -A ·
> deploys/secrets = owner · EDIT SPECS, never edits · ping per your PROTOCOL §5, token at
> line end. Acknowledge in YOUR ledger, not here.

## 3. Deny-hook pattern (owner approves live in a lane session; adapt targets per project)

`.claude/settings.json` → PreToolUse matcher "Bash" → command hook that exits 2 on:
`git add -A|git add \.|git add --all|rm -rf|rm -fr|ssh <deploy-host>|scp .*<deploy-host>`
(fail-OPEN wrapper so a missing guard file never blocks; keep broad ALLOW lists in each
lane's git-ignored settings.local.json — owner-granted only).
