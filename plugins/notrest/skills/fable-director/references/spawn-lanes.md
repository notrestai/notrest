# spawn-lanes — a skill/director CREATING real Claude Code sessions itself

## The capability map (honest)
- **Desktop-app panes: NOT creatable by tools** — the app's MCP exposes list/send/archive
  only. App sessions remain owner-created, forever.
- **CLI sessions: fully creatable** via macOS Terminal automation — `osascript` opens a
  Terminal window running `claude` with the bootstrap as its first prompt. These are REAL
  interactive Claude Code sessions in the SAME cwd; the file-wire + token watches work
  IDENTICALLY (they're shell-level). This removes BOTH owner steps: session creation AND
  the bootstrap send (the prompt rides the launch — no send_message, no confirm click).
- (`tmux` variant exists for headless window management — install via brew if wanted;
  same commands inside `tmux new-session -d`.)

## The recipe (verbatim; spawn ONLY on explicit owner instruction — never speculatively)

1. Write the lane's bootstrap prompt to a file (avoids quote-hell):
```
cat > "<REPO>/_fable/boot-<LANE>.txt" <<'EOF'
You are <LANE>, the <role> lane in the Fable split for <project> ("3 DEVS AND A RELAY").
Read PLAN-FABLE-DIRECTOR-V4.md §2-§9, then YOUR blackboard COORD-<LANE>.md
end-to-end. ARM YOUR WATCH FIRST (verbatim in the file; run_in_background; log the task
id). Then drain D-001.. by priority. Never git add -A · deploys/secrets = owner · EDIT
SPECS, never edits · ping per PROTOCOL §5, token at line end. Acknowledge in YOUR ledger.
EOF
```
2. Spawn (one Terminal window per lane):
```
osascript -e 'tell application "Terminal" to do script "cd \"<REPO>\" && claude --permission-mode acceptEdits \"$(cat _fable/boot-<LANE>.txt)\""'
```
3. Log the spawn to the ledger; then verify the proof trio ARRIVES in the lane's
   blackboard (watch task id · auth env check · first ledger ACK) — spawned ≠ seated.

## Caveats (each one load-bearing)
1. **One-time owner grant:** the first osascript→Terminal call triggers macOS Automation
   permission (System Settings → Privacy → Automation). After the grant: zero-click forever.
2. **CLI lanes don't appear in the desktop app's session list** — app-side send_message /
   archive_session can't reach them. Operation is unaffected (the files are the wire);
   "archiving" a CLI lane = a stand-down directive (kill watch · final ledger line · `exit`)
   or closing its window.
3. **Auth proof stays mandatory** — CLI claude uses the logged-in subscription unless the
   env carries a key; D-001's env check is non-negotiable per spawn.
4. **Mode:** pass `--permission-mode acceptEdits` (+ per-lane settings.local.json
   allowlists, owner-granted); `auto` availability varies on CLI.
5. **Avoid `claude -p` (headless) for lanes** — interactive CLI shares the flat pool;
   headless print-mode may draw a separate credit pool.
6. **Watches work in CLI sessions** (same harness, same run_in_background semantics);
   re-arm discipline unchanged.

## Rotation, fully automated (V4 §9 amended)
With the Automation grant in place, the sitting director executes the WHOLE rotation on the
trigger phrase: true open-threads → spawn the successor director (same recipe, kickoff file
as the prompt) → spawn fresh lanes → stand down old CLI lanes via the file (app-pane lanes:
owner archives) → silent fallback until the successor's first ledger line. The owner's
remaining role: the trigger phrase + oversight. App-pane participants still require owner
creation — mixed fleets are fine (the wire doesn't care where a session lives).
