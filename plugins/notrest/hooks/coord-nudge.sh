#!/bin/bash
# notrest UserPromptSubmit hook — per-prompt COORD.md ledger discipline.
# One short line only: this fires on EVERY prompt, so it must stay token-cheap.
# ── estate root: ONE resolver, shared by every estate hook (hooks/estate-root.sh).
# git root, else the nearest COORD.md walking up at most 3 levels — stopping at any
# directory carrying its OWN project marker (a project boundary is never walked through,
# 2026-08-02 adversarial round) and never reaching $HOME or /. An escaping-symlink
# COORD.md is skipped, never adopted. Neither answer: exit 0 silently, having written
# nothing, exactly as before. The variable keeps its historical name; it is the ESTATE
# root, not only a git one.
. "$(cd "$(dirname "$0")" && pwd)/estate-root.sh" 2>/dev/null || true
GIT_ROOT="${NR_ESTATE_ROOT:-}"
[ -z "$GIT_ROOT" ] && exit 0
if [ -n "$GIT_ROOT" ] && [ -f "$GIT_ROOT/COORD.md" ]; then
  echo "[notrest] COORD: when this work lands, append one honest ledger line (ask -> landed | evidence)."
fi

# ── SELF-RESTART (owner, 2026-08-05): "my experience with the pulse is that it stops
# between check ins and does need to manually restart". Event-driven refreshes only fire
# when events flow; a session that is thinking rather than spawning lanes went silent.
# This hook fires on EVERY prompt, so it is the right heartbeat: one stat, and if the
# pulse is absent or older than 30 minutes, kick a DETACHED refresh. estate-pulse.sh's
# own 60s debounce remains the floor, so a burst of prompts still produces one refresh.
# Result: event-driven when events flow, prompt-driven when they do not, dead only when
# the machine is — and the heartbeat's age says which.
NR_PULSE_JSON="$GIT_ROOT/pulse/pulse.json"
NR_STALE=1
if [ -f "$NR_PULSE_JSON" ]; then
  NR_AGE="$(python3 -c '
import os, sys, time
try:
    sys.stdout.write(str(int(time.time() - os.path.getmtime(sys.argv[1]))))
except Exception:
    pass' "$NR_PULSE_JSON" 2>/dev/null)"
  case "$NR_AGE" in
    ''|*[!0-9]*) NR_STALE=1 ;;
    *) [ "$NR_AGE" -lt 1800 ] && NR_STALE="" ;;
  esac
fi
if [ -n "$NR_STALE" ]; then
  ( bash "$(cd "$(dirname "$0")" && pwd)/estate-pulse.sh" "$GIT_ROOT" prompt-stale >/dev/null 2>&1 & ) 2>/dev/null
fi

# ── THE WATCHER REACHES THE SEAT. A stalled lane used to be found by hand, by reading
# file mtimes. swarm.py watch writes its alerts to pulse/swarm-live.txt; this surfaces
# them on the next prompt — one echo, and ONLY when an alert actually exists.
NR_LIVE="$GIT_ROOT/pulse/swarm-live.txt"
if [ -f "$NR_LIVE" ] && grep -q '^ALERT' "$NR_LIVE" 2>/dev/null; then
  NR_ALERTS="$(grep -c '^ALERT' "$NR_LIVE" 2>/dev/null || true)"
  NR_FIRST="$(grep -m1 '^ALERT' "$NR_LIVE" 2>/dev/null | cut -c1-140)"
  echo "[notrest] SWARM WATCH: ${NR_ALERTS} alert(s) on running lanes — ${NR_FIRST} · full sweep in pulse/swarm-live.txt. Probe, resume or stop the lane; do not wait it out."
fi
exit 0
