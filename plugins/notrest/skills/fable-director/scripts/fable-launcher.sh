#!/usr/bin/env bash
# fable-launcher.sh — start a FABLE DIRECTOR session with automatic model fallback.
# Probes claude-fable-5 availability on the API; any non-200 → launches as the LATEST
# OPUS instead ("--model opus" — the harness resolves the newest Opus, no pin to update).
# The key lives ONLY here, scoped to this process (never export globally — it would
# silently bill every flat session). Owner fills the marker; secrets never touch Claude.
#
# Usage: fable-launcher.sh [initial prompt ...]     (defaults to the kickoff pointer)
set -eu

# The key lives OUTSIDE the tree (map thread 11: a credential placeholder in a
# git-tracked file is the shape the secret screens exist to catch). Owner creates it
# once: printf 'sk-ant-...' > ~/.notrest/fable-key && chmod 600 ~/.notrest/fable-key
NOTREST_KEYFILE="${NOTREST_HOME:-$HOME/.notrest}/fable-key"
[ -r "$NOTREST_KEYFILE" ] || { echo "fable-launcher: no key at $NOTREST_KEYFILE — create it (owner only, chmod 600)" >&2; exit 3; }
export ANTHROPIC_API_KEY="$(cat "$NOTREST_KEYFILE")"

PRIMARY="claude-fable-5"
FALLBACK="opus"                                     # harness-resolved latest Opus

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
  https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d "{\"model\":\"$PRIMARY\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}]}" \
  || echo "000")

if [ "$code" = "200" ]; then
  MODEL="$PRIMARY"
  echo "fable-launcher: $PRIMARY available — launching (probe cost ≈ 1 token)."
else
  MODEL="$FALLBACK"
  echo "fable-launcher: $PRIMARY UNAVAILABLE (HTTP $code) → falling back to latest Opus." >&2
  echo "fable-launcher: log the fallback in your first ledger line (V4 model policy)." >&2
fi

PROMPT="${*:-Read _fable/KICKOFF-DIRECTOR.md in this repo and execute it. Model policy: log which model you are running in your first ledger line.}"
exec claude --model "$MODEL" --permission-mode acceptEdits "$PROMPT"
