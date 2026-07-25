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

# ── fable discipline: bolted to the metal. Unconditional every session so the
# working posture is present without anyone typing /fable-mode. The anchor is
# always in context; the full contract is one skill-load away. Trivial single-
# question turns may skip. stdout is injected as session context.
echo "[notrest] Fable discipline is active this session. Run substantive work (building, debugging, deploying, multi-step tasks) through the loop: ORIENT (read the project's state docs first) -> PROBE (inspect the live system before reasoning — read-only inspection is free, arguing from priors when a command could answer is a violation) -> ACT (smallest verifiable step; show-before-run on any mutating/production/irreversible action, then wait for explicit go) -> PROVE (a 'done/works/fixed' claim requires observable evidence in-transcript — exit code, HTTP status, pid, diff, log line; otherwise say 'unverified'; 'should work' is banned) -> BANK (checkpoint state + the exact resume payload; assume the session can die any minute). Also: verify handed-down claims (docs/memory go stale) against the live system before building on them; surface conflicts, never silently smooth; secrets never enter context. When tools or permissions degrade mid-session, reroute instead of stalling — smallest probes, stage-then-assemble, keep unblocked lanes moving (the fable-mode contract carries the full outage playbook). Load the full contract with the fable-mode skill (notrest:fable-mode). Skip only for trivial single-question turns."

# ── offload model policy: unconditional, so it reaches every fan-out surface
# (Agent tool, Workflow/ultracode, deep-research, review panels) even when no
# notrest skill is loaded. Owner-set 2026-07-15: opus-only offload.
echo "[notrest] HARD RULE — offload model policy (owner-set 2026-07-15): Fable never rides in a subagent, and every job this session offloads runs on OPUS — whatever model holds the seat (Fable or Opus alike). Every spawned agent/subagent (Agent tool, Workflow agent() calls, deep-research and review fan-outs, panel lenses, pipeline stages) MUST set model 'opus' explicitly — not sonnet, not haiku, never fable, and NEVER subagent_type 'fork' (forks ignore the model parameter and silently inherit Fable). Omitting the model silently inherits Fable and bills Fable credit — that omission is a violation, not a default. The seat is the orchestrator (decompose, judge, apply edits, gate ships) and delegates everything else — the seat stays the seat regardless of model. agentswarm (notrest:agentswarm) is the default delegation arrangement: batch-spawn background Opus lanes, keep lanes NARROW and parallel (wall-clock is the slowest lane, not the sum — split broad jobs), hand each lane its material inline so it works at call 1, and never idle the seat waiting on a non-ship-blocking lane, demand tight returns (conclusions, not dumps), refuter-check findings before acting, log every completed lane to the spend ledger (notrest:spend), consult the archivist index before research fan-outs, and never /model-switch the seat (cache burn — delegate instead). SEAT-BUILDER RITUAL (owner-ratified): substantive builds run through ONE persistent Opus builder lane per domain — the seat specs, the lane builds, the seat gates (exit-code-checked, never piped through tail) — and feedback rounds RESUME THE SAME LANE via SendMessage, never a fresh spawn; diagnosis stays parallel one-shot lanes."

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
Honest entries only: in-progress is "in progress", untested is "untested". Compact
to COORD-ARCHIVE.md at ~40 ledger lines. In a fable-director arrangement, lane
blackboards live beside this file as COORD-<LANE>.md; this file is the ship/main ledger.

## LEDGER
COORDEOF
  echo "- [$(date -u '+%Y-%m-%d %H:%MZ')] [hook] COORD.md scaffolded by notrest SessionStart" >> "$REPO_ROOT/COORD.md"
  echo "[notrest] COORD.md created at the repo root — the session coordination ledger. Append one ledger line per substantive prompt when its work lands (ask -> landed | evidence)."
elif [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/COORD.md" ]; then
  echo "[notrest] COORD.md is live in this repo — read its ledger tail before starting (prior sessions' trail), and append one line per substantive prompt's work (ask -> landed | evidence)."
fi
# A lane blackboard is COORD-<LANE>.md — NOT the machine-written ledgers
# (COORD-AGENTS.md, COORD-ARCHIVE.md, COORD-AGENTS-ARCHIVE.md), which exist in
# every ORACLE repo and used to false-fire this nudge.
LANE_BLACKBOARD=""
for f in COORD-*.md FABLE-COORD*.md; do
  [ -f "$f" ] || continue
  case "$f" in
    COORD-AGENTS.md|COORD-ARCHIVE.md|COORD-AGENTS-ARCHIVE.md) continue ;;
  esac
  LANE_BLACKBOARD="$f"
  break
done
if [ -n "$LANE_BLACKBOARD" ] || [ -f "PLAN-FABLE-DIRECTOR-V4.md" ]; then
  echo "[notrest] Per-lane COORD blackboards (COORD-<LANE>.md / legacy FABLE-COORD*.md) exist here — a fable-director arrangement lives in this repo. If this session is meant to direct (or rejoin) it, load the fable-director skill (notrest:fable-director): it reads the repo's PLAN-FABLE-DIRECTOR-V4.md + blackboards and re-arms watches before anything else."
fi
exit 0
