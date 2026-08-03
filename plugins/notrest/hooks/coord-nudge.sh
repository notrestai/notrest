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
exit 0
