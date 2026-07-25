#!/bin/bash
# notrest UserPromptSubmit hook — per-prompt COORD.md ledger discipline.
# One short line only: this fires on EVERY prompt, so it must stay token-cheap.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/COORD.md" ]; then
  echo "[notrest] COORD: when this work lands, append one honest ledger line (ask -> landed | evidence)."
fi
exit 0
