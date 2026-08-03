#!/bin/bash
# notrest estate-root resolver — THE single answer to "which project does this session
# belong to". SOURCED by every estate hook (session-start, coord-nudge, agent-ledger,
# session-end): four hooks that disagree about the root are four different estates, and
# the disagreement is invisible until something lands in the wrong project.
#
# Sets NR_ESTATE_ROOT to the resolved root, or "" when there is none. Never prints,
# never exits the caller, never fails a hook.
#
# LAW (2026-08-02, live failure): a project ESTABLISHED by /notrest carries COORD.md, and
# that file is a root marker in its own right — the estate follows the LEDGER, not git.
# LAW (2026-08-02, adversarial round): the walk must never cross a PROJECT BOUNDARY. The
# first resolver adopted any COORD.md within three levels, so a session working in an
# un-established subproject wrote its ledger lines — and its verbatim commission briefs —
# into an unrelated parent project that merely happened to be established. A directory
# carrying its own project marker is a boundary: no ledger there means no estate here,
# and the walk stops rather than borrowing someone else's.
# LAW: $HOME and the filesystem root are never an estate. A ledger there would capture
# every session on the machine that happens to start three levels beneath it.

# realpath containment: is $2 really inside $1 once every symlink is resolved? python3 is
# already a hard dependency of the hooks that call this; the check is gated on [ -L ] at
# the one call site, so the ordinary path never pays for a subprocess.
nr_contained() {
  python3 - "$1" "$2" <<'PY' 2>/dev/null
import os, sys
try:
    r = os.path.realpath(sys.argv[1])
    p = os.path.realpath(sys.argv[2])
    sys.exit(0 if p == r or p.startswith(r + os.sep) else 1)
except Exception:
    sys.exit(1)
PY
}

nr_estate_root() {
  NR_ESTATE_ROOT=""

  # 1. a git repo answers for itself — the toplevel, exactly as before.
  NR_ESTATE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$NR_ESTATE_ROOT" ] && return 0

  # 2. otherwise walk up at most 3 levels, applying one rule per level.
  nr_d="$(pwd -P 2>/dev/null || echo "$PWD")"
  nr_home="$(cd "${HOME:-/nonexistent}" 2>/dev/null && pwd -P || echo "${HOME:-}")"
  nr_i=0
  while [ "$nr_i" -lt 3 ]; do
    nr_i=$((nr_i + 1))

    # $HOME, the filesystem root and the well-known home folders are never an estate, and
    # the walk never passes them. Their SUBdirectories are ordinary projects; it is the
    # exact paths that are refused (2026-08-02 round 2).
    if [ "$nr_d" = "/" ] || { [ -n "$nr_home" ] && { [ "$nr_d" = "$nr_home" ] \
        || [ "$nr_d" = "$nr_home/Desktop" ] || [ "$nr_d" = "$nr_home/Documents" ] \
        || [ "$nr_d" = "$nr_home/Downloads" ]; }; }; then
      break
    fi

    # a usable ledger here → adopt. An ESCAPING or DANGLING one is never adopted (the
    # write would land outside the project it claims to record) and is itself a BOUNDARY:
    # a broken ledger means this directory HAS an estate that is currently unusable, so
    # walking past it to adopt a distant one would be exactly the wrong repair.
    if [ -e "$nr_d/COORD.md" ] || [ -L "$nr_d/COORD.md" ]; then
      if [ -f "$nr_d/COORD.md" ] && { [ ! -L "$nr_d/COORD.md" ] \
           || nr_contained "$nr_d" "$nr_d/COORD.md"; }; then
        NR_ESTATE_ROOT="$nr_d"
      fi
      return 0
    fi

    # a project boundary with no ledger → STOP. This directory is its own project and
    # simply is not established; the parent's estate is not ours to write into. The list
    # is THE MARKER LIST — CLAUDE.md and .claude included, because a CLAUDE.md-only
    # directory is the ordinary shape of a Claude Code project and leaving those two out
    # left the commonest subproject adopting its parent (2026-08-02 round 2).
    for nr_m in CLAUDE.md README.md package.json pyproject.toml .git .claude; do
      if [ -e "$nr_d/$nr_m" ]; then
        return 0
      fi
    done

    nr_p="$(dirname "$nr_d" 2>/dev/null || echo /)"
    [ "$nr_p" = "$nr_d" ] && break
    nr_d="$nr_p"
  done
  return 0
}

nr_estate_root

# SOURCED (the four hooks) → return here. EXECUTED directly (the fixture's
# four-hooks-agree assert runs it as a script and reads NR_ESTATE_ROOT off stdout) →
# `return` fails outside a function, so the printing path below runs instead. The
# trailing `exit 0` also satisfies the HOOK-CONTRACT law, which reads every hooks/*.sh
# and requires that last statement — a sourced file must therefore never REACH it.
return 0 2>/dev/null || true
printf '%s\n' "$NR_ESTATE_ROOT"
exit 0
