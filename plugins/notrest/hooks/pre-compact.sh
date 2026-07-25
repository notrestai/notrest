#!/bin/bash
# notrest PreCompact hook — fires when context is about to auto-compact.
# This is exactly the moment session state is at risk of lossy compression:
# remind that a deliberate handoff beats an automatic summary.
echo "[notrest] Context is auto-compacting. If this session is near its natural end, run /sessionend first — a deliberate handoff (files + live line) preserves more than compaction will. If mid-task, carry on — but first append a COORD.md ledger line for any work that just landed (ask -> landed | evidence): the ledger is the per-prompt trail that survives compaction and crashes even when /sessionend never runs."
exit 0
