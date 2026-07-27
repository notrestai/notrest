#!/bin/bash
# notrest SessionStart hook — continuity nudge + self-update.

# ── self-update: if this plugin lives in a git clone, quietly pull latest.
# Fire-and-forget: never blocks session start; --ff-only never clobbers local
# edits (dirty/diverged clones are silently left alone). Updates apply from
# the NEXT session. Note: this executes whatever the origin repo ships —
# point it only at a repo you control.
PLUGIN_GIT_ROOT="$(git -C "$(cd "$(dirname "$0")" && pwd)" rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$PLUGIN_GIT_ROOT" ]; then
  ( cd "$PLUGIN_GIT_ROOT" && git pull --ff-only --quiet >/dev/null 2>&1 & ) 2>/dev/null
fi

# ── identity: one line that answers "is notrest installed?" in every session.
# The /plugin UI does not list skills-dir runtimes — live-proven 2026-07-26/27: the
# owner, not finding notrest there, reinstalled a marketplace copy FOUR times, each
# one silently shadowing this runtime. This line is the visible truth; never cut it.
NV="$(sed -n 's/.*"version": "\([^"]*\)".*/\1/p' "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" 2>/dev/null | head -1)"
echo "[notrest] v${NV:-?} @skills-dir — live from the repo tree (the /plugin UI hides skills-dir plugins; verify with: claude plugin list)"

# ── fable discipline: bolted to the metal. Unconditional every session so the
# working posture is present without anyone typing /fable-mode. The anchor is
# always in context; the full contract is one skill-load away. Trivial single-
# question turns may skip. stdout is injected as session context.
echo "[notrest] Fable discipline is active: ORIENT -> PROBE -> ACT -> PROVE -> BANK. Probe the live system before reasoning; a done/works/fixed claim needs in-transcript evidence (exit code, diff, status) or say 'unverified'; bank state before stopping. Full contract: /notrest:fable-mode."

# ── offload model policy: unconditional, so it reaches every fan-out surface
# (Agent tool, Workflow/ultracode, deep-research, review panels) even when no
# notrest skill is loaded. Owner-set 2026-07-15: opus-only offload.
echo "[notrest] HARD RULE — offload: every spawned agent/Workflow lane sets model \"opus\" explicitly. Never sonnet, haiku, or subagent_type \"fork\" (forks inherit the seat); omitting model is a violation, not a default. Delegate via /notrest:agentswarm; builds run ONE persistent lane — feedback RESUMES it (SendMessage), never a new spawn. Receipts auto-log; never hand-log. Never /model-switch the seat."

# ── continuity nudge: stdout is injected as session context.
if [ -f "START-HERE.md" ]; then
  echo "[notrest] START-HERE.md exists in this directory — a previous session left resume instructions (and possibly a 'Live line:' to a predecessor session that can answer setup questions). Suggest /oracle to the user to resume properly, or read START-HERE.md before starting work."
fi
if [ -f "HANDOFF.md" ] && [ ! -f "START-HERE.md" ]; then
  echo "[notrest] HANDOFF.md exists here — prior session state is available; consider reading it before starting work."
fi
# ── COORD.md: the session coordination ledger (the fable-coord behavior, generalized
# to every session). Auto-created at the git root of any repo a session starts in;
# the UserPromptSubmit hook (coord-nudge.sh) injects the per-prompt append discipline.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$REPO_ROOT" ] && [ ! -f "$REPO_ROOT/COORD.md" ] && ! ls "$REPO_ROOT"/FABLE-COORD*.md >/dev/null 2>&1; then
  cat > "$REPO_ROOT/COORD.md" <<'COORDEOF'
# COORD.md — session coordination ledger

Append-only, newest at the bottom, one line per substantive prompt when its work
lands: `- [YYYY-MM-DD HH:MMZ] [session-or-lane] <what was asked> -> <what landed> | evidence: <exit code / commit / path / status>`.
Honest entries only: in-progress is "in progress", untested is "untested". Never
compacted: past ~500 ledger lines this file is SEALED WHOLE as the next COORD-<NNN>.md
and a fresh active volume starts — sealed volumes are immutable, sessions read this
active tail, /recap + /compile + /archivist read every volume. In a fable-director
arrangement, lane blackboards live beside this file as COORD-<LANE>.md (never all
digits — that is a sealed volume); this file is the ship/main ledger.

## LEDGER
COORDEOF
  echo "- [$(date -u '+%Y-%m-%d %H:%MZ')] [hook] COORD.md scaffolded by notrest SessionStart" >> "$REPO_ROOT/COORD.md"
  echo "[notrest] COORD.md created at the repo root — the session coordination ledger. Append one ledger line per substantive prompt when its work lands (ask -> landed | evidence)."
elif [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/COORD.md" ]; then
  echo "[notrest] COORD.md is live in this repo — read its ledger tail before starting (prior sessions' trail), and append one line per substantive prompt's work (ask -> landed | evidence)."
fi
# ── compile: surface a ripe candidate the estate has already recorded three or
# more times. This READS the last scan only — scanning belongs to /sessionend, and
# a SessionStart hook must never do work. Silent when absent, unreadable, or when
# every ripe candidate has already been ruled on.
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/compile/candidates.json" ]; then
  COMPILE_TOP="$(python3 -c 'import json,sys
try: c = json.load(open(sys.argv[1]))["candidates"]
except Exception: sys.exit(0)
r = [x for x in c if x.get("ripe") and x.get("status") == "NEW"]
if r: print(r[0]["slug"], r[0]["occurrences"])' "$REPO_ROOT/compile/candidates.json" 2>/dev/null)"
  if [ -n "$COMPILE_TOP" ]; then
    read -r CSLUG CSEEN <<< "$COMPILE_TOP"
    echo "[notrest] Ripe compile candidate: $CSLUG seen ${CSEEN}x — repeated work the estate already recorded. Say /compile $CSLUG to move its stable parts into code (or compile.py decide --status DECLINED to silence)."
  fi
fi
# A lane blackboard is COORD-<LANE>.md — NOT the machine-written ledgers
# (COORD-AGENTS.md, COORD-ARCHIVE.md, COORD-AGENTS-ARCHIVE.md), which exist in
# every ORACLE repo and used to false-fire this nudge. Nor the SEALED LEDGER
# VOLUMES, whose suffix is purely numeric (COORD-001.md, COORD-AGENTS-007.md):
# a lane name is never all digits, so that test separates them cleanly.
LANE_BLACKBOARD=""
for f in COORD-*.md FABLE-COORD*.md; do
  [ -f "$f" ] || continue
  case "$f" in
    COORD-AGENTS.md|COORD-ARCHIVE.md|COORD-AGENTS-ARCHIVE.md) continue ;;
  esac
  COORD_SUF="${f#COORD-}"; COORD_SUF="${COORD_SUF%.md}"
  COORD_SUF="${COORD_SUF#AGENTS-}"
  case "$COORD_SUF" in
    ''|*[!0-9]*) : ;;   # has a non-digit -> a real lane name
    *) continue ;;      # all digits -> a sealed ledger volume, not a lane
  esac
  LANE_BLACKBOARD="$f"
  break
done
if [ -n "$LANE_BLACKBOARD" ] || [ -f "PLAN-FABLE-DIRECTOR-V4.md" ]; then
  echo "[notrest] Per-lane COORD blackboards (COORD-<LANE>.md / legacy FABLE-COORD*.md) exist here — a fable-director arrangement lives in this repo. If this session is meant to direct (or rejoin) it, load the fable-director skill (notrest:fable-director): it reads the repo's PLAN-FABLE-DIRECTOR-V4.md + blackboards and re-arms watches before anything else."
fi
exit 0
