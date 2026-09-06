#!/bin/bash
# atlas-mcp.sh — the launcher for the vendored Atlas read-only MCP server.
#
# The server itself (server.mjs) is vendored BYTE-EXACT from the Atlas contract and is
# never edited. Everything the plugin needs to say about how it runs on a notrest machine
# is said here instead: where the secret FILE lives, which hub it points at, and the one
# soft dependency (node >= 22, RULINGS 2026-09-06 §4).
#
# LAWS
#   secrets by path — this script exports the NAME of a file. It never reads the secret,
#                     never puts it in argv, an env VALUE, or a log line.
#   one line, one    — a node that cannot run the server produces exactly one stderr line
#   exit code          and exit 6 (the plugin's "not established / unusable" code). It is
#                      never a stack trace and never a silent failure.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
SERVER="$HERE/server.mjs"

# The view secret, BY PATH. server.mjs reads ATLAS_VIEW_FILE today; the identity token file
# (ATLAS_TOKEN_FILE, default ~/.notrest/atlas-token) arrives with hub phase I-B — IDENTITY-CONTRACT §5.
ATLAS_HOME="${NOTREST_HOME:-$HOME/.notrest}"
export ATLAS_VIEW_FILE="${ATLAS_VIEW_FILE:-$ATLAS_HOME/credentials/atlas-view}"

# ATLAS_HUB_BASE passes THROUGH untouched — the server owns the default (https://atlas.not.rest),
# so a value set here would be a second copy of it, and the copy nobody watches is the one that drifts.
if [ -n "${ATLAS_HUB_BASE:-}" ]; then export ATLAS_HUB_BASE; fi

NODE_BIN="${NODE:-node}"
NODE_V=""
if command -v "$NODE_BIN" >/dev/null 2>&1; then
  NODE_V="$("$NODE_BIN" --version 2>/dev/null | head -n 1)"
fi
NODE_MAJOR="$(printf '%s' "$NODE_V" | sed -n 's/^v\{0,1\}\([0-9][0-9]*\).*$/\1/p')"
if [ -z "$NODE_MAJOR" ] || [ "$NODE_MAJOR" -lt 22 ]; then
  echo "[notrest] atlas mcp: node >= 22 required (found ${NODE_V:-none})" >&2
  exit 6
fi

exec "$NODE_BIN" "$SERVER" "$@"
