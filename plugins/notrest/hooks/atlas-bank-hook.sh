#!/bin/sh
# atlas-bank-hook.sh — the TRACKED body of the estate's git post-commit bank.
#
# `atlas.py wire` installs a four-line shim at <git-dir>/hooks/post-commit that does
# nothing but point here, so the logic that runs at every commit lives in the repo, is
# reviewed like code, and updates with the plugin — a hook body copied into .git/hooks
# is a fork nobody can see.
#
# LAW: a post-commit hook must never cost anyone their commit. No `set -e`, every step
# fails open, and the last statement is `exit 0` — the commit already happened, and a
# bank that could not run is a stale map, not a lost change.
#
# FOUR FAST PATHS, in order, each silent:
#   1. no python3            → nothing can run
#   2. no atlas/ in the repo → this estate is not on the map (never wired)
#   3. no valid access key   → notrest is part of Atlas; without a key the harness is
#                              quiet on this machine (docket 4.8 A), and quiet means
#                              quiet: no banner, no partial bank, no nagging
#   4. already banking       → re-entrancy guard, in case a check ever commits
#
# ENV: NOTREST_ATLAS_PY (the shim exports it) · NOTREST_ATLAS_NO_BOARD=1 skips the board
# collectors · NOTREST_ATLAS_BOARD_TIMEOUT bounds each one (default 20s inside a hook,
# where a slow collector is felt).

[ -n "${NOTREST_ATLAS_BANKING:-}" ] && exit 0
NOTREST_ATLAS_BANKING=1
export NOTREST_ATLAS_BANKING

command -v python3 >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$ROOT" ] || exit 0
[ -d "$ROOT/atlas" ] || exit 0

# ROOT was resolved with git's hook environment intact; from here it is passed EXPLICITLY
# and that environment is dropped, so nothing atlas runs inherits a .git it was not given.
# PREFIX RULE, not a denylist: git's environment is open-ended and a named list leaks
# whatever the next release adds (GIT_OBJECT_DIRECTORY, GIT_COMMON_DIR, GIT_CONFIG_GLOBAL,
# GIT_CEILING_DIRECTORIES, GIT_NAMESPACE, … all walked through the first cut). Strip every
# GIT_* except the few that carry no repository identity.
for _v in $(env | sed -n 's/^\(GIT_[A-Za-z0-9_]*\)=.*/\1/p'); do
    case "$_v" in
        GIT_TERMINAL_PROMPT|GIT_SSH_COMMAND|GIT_SSH) : ;;
        *) unset "$_v" 2>/dev/null || : ;;
    esac
done

ATLAS="${NOTREST_ATLAS_PY:-}"
if [ -z "$ATLAS" ]; then
    HOOKS_DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd)
    ATLAS="$HOOKS_DIR/../skills/atlas/scripts/atlas.py"
fi
[ -r "$ATLAS" ] || exit 0

# THE SENTINEL, REQUIRED VERBATIM (refuter round, 4.8). An exit code alone proves only
# that SOMETHING on PATH called python3 exited 0 — a stub, a wrapper, an interpreter that
# never parsed atlas.py all answer "0" and would have walked straight past this gate. So
# the gate requires the one line only atlas.py can print, carrying the digest of the ring
# it actually read. No sentinel, no bank, and still not one word on stdout.
RING=$(python3 "$ATLAS" key --check --quiet 2>/dev/null) || exit 0
case "$RING" in
    "notrest-access: ok ring="*) : ;;
    *) exit 0 ;;
esac

BOARD=""
[ "${NOTREST_ATLAS_NO_BOARD:-0}" = "1" ] && BOARD="--no-board"

python3 "$ATLAS" bank --root "$ROOT" --quiet \
    --board-timeout "${NOTREST_ATLAS_BOARD_TIMEOUT:-20}" $BOARD 2>&1

# The bank's exit code is DELIBERATELY dropped. A red board is a true fact about the
# commit that just landed — the snapshot records it and `atlas.py status` reports it —
# but it is not a reason to make `git commit` look broken. The map tells the truth; it
# does not punish.
exit 0
