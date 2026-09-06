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


# ── THE ACCESS KEY (4.8). notrest is part of Atlas from this release: the harness runs on
# a machine that holds a key the owner minted, and on no other. `nr_access_ok` leaves the
# answer in NR_ACCESS ("1" = licensed, "" = not) and the reason in NR_ACCESS_WHY.
#
# IT ASKS THE AUTHORITY. IT DOES NOT DECIDE (refuter ruling, 2026-09-06). The first cut
# read the keyring and hashed the key in shell, with an mtime-checked cache, to keep the
# per-prompt hooks fast. That bought ~50 ms and cost the gate:
#   · the cache was existence-and-mtime only, so `NOTREST_HOME=/tmp/evil` with a forged
#     marker beside a bogus key answered LICENSED while atlas.py answered 7 — and a
#     `touch -r` on a swapped key did the same;
#   · six keyring line shapes (uppercase hash, short or malformed dates, empty or spaced
#     label, trailing junk) the shell admitted and atlas.py rejects;
#   · a key file with a leading comment or a blank line atlas.py accepts and the shell
#     did not, and NOTREST_ACCESS_KEY_FILE went unread entirely.
# Two implementations of one law is one law too many. `atlas.py key --check --quiet` is
# the authority — exit 0 licensed, 7 not — and this asks it and takes the answer. Parity
# is now by construction rather than by fixture.
#
# THE COST IS ONE python START PER HOOK FIRE, measured and accepted: the per-prompt hooks
# already fork python to parse their payload, so the marginal cost is one more start. Any
# failure to ask — no python3, no atlas.py, an exit that is neither 0 nor 7 — is DARK with
# NR_ACCESS_WHY=noverifier: a gate that cannot ask must not answer yes.
#
# pretool-gate.sh does not source this file and is deliberately never gated: its deny
# rules must outlive any licence question.
nr_access_ok() {
  NR_ACCESS=""; NR_ACCESS_WHY="nokey"

  # V5c (refuter): THE HOOK DIRECTORY MUST BE ABSOLUTE. A relative one — `.` after a
  # source by bare name — resolves against whatever cwd the caller chose, and a planted
  # ./skills/atlas/scripts/atlas.py then answers the licence question. Three sources
  # tried, each only if it is absolute; none absolute = dark.
  nr_src="${BASH_SOURCE[0]:-}"
  nr_hookdir=""
  case "$nr_src" in /*) nr_hookdir="${nr_src%/*}" ;; esac
  if [ -z "$nr_hookdir" ]; then
    case "${0:-}" in /*) nr_hookdir="${0%/*}" ;; esac
  fi
  if [ -z "$nr_hookdir" ] && [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    case "$CLAUDE_PLUGIN_ROOT" in /*) nr_hookdir="$CLAUDE_PLUGIN_ROOT/hooks" ;; esac
  fi
  case "$nr_hookdir" in
    /*) ;;
    *) NR_ACCESS_WHY="hookdir"; return 0 ;;
  esac

  # V1 (refuter): THE KEYRING IS PINNED, NOT CHOSEN. $NOTREST_KEYRING let a caller point
  # the verifier at a keyring they had minted into, and a symlinked .access/keys.sha256
  # was followed to wherever it led. The path is passed EXPLICITLY, the environment that
  # could redirect it is stripped, and a keyring that is a symlink or not a regular file
  # is refused outright. The KEY may still arrive by env or from the store — that is the
  # holder's own secret; the RING is the estate's.
  # The pinned ring, built by STRING SURGERY so it is normalized without a fork: the hook
  # dir is absolute and ends in /hooks, so the plugin root is the prefix. The `..` form is
  # the fallback, and it is the one case where the sentinel's path= cannot be compared —
  # said out loud rather than quietly skipped.
  nr_ringcmp=1
  case "$nr_hookdir" in
    */hooks) nr_ring="${nr_hookdir%/hooks}/.access/keys.sha256" ;;
    *)       nr_ring="$nr_hookdir/../.access/keys.sha256"; nr_ringcmp="" ;;
  esac
  if [ -L "$nr_ring" ] || [ ! -f "$nr_ring" ]; then
    NR_ACCESS_WHY="ring"
    return 0
  fi
  nr_atlas="$nr_hookdir/../skills/atlas/scripts/atlas.py"
  if [ -L "$nr_atlas" ] || [ ! -f "$nr_atlas" ]; then
    NR_ACCESS_WHY="noverifier"
    return 0
  fi

  # V2 (refuter): A FAKE python3 ON $PATH ANSWERED "licensed" BY EXITING 0. Two guards:
  # the system interpreter is preferred over whatever PATH offers, and the answer must
  # carry atlas.py's stdout SENTINEL — `notrest-access: ok ring=<12 hex>` — whose ring
  # fingerprint must equal the sha256 of the keyring pinned above. An exit code alone is
  # a claim anything can make; the sentinel has to be computed from the file we chose.
  nr_py="/usr/bin/python3"
  [ -x "$nr_py" ] || nr_py="$(command -v python3 2>/dev/null)"
  if [ -z "$nr_py" ]; then
    NR_ACCESS_WHY="noverifier"
    return 0
  fi
  # Stock macOS ships /usr/bin/shasum; openssl is the fallback. With NEITHER, the ring
  # fingerprint cannot be recomputed here, so the check degrades to requiring the literal
  # sentinel prefix — weaker, and said out loud rather than hidden.
  nr_ringhash=""
  if [ -x /usr/bin/shasum ]; then
    nr_ringhash="$(/usr/bin/shasum -a 256 "$nr_ring" 2>/dev/null)"
  elif command -v openssl >/dev/null 2>&1; then
    nr_ringhash="$(openssl dgst -sha256 "$nr_ring" 2>/dev/null)"
    nr_ringhash="${nr_ringhash##*= }"
  fi
  nr_ringhash="${nr_ringhash%% *}"

  nr_out="$(env -u NOTREST_KEYRING -u NOTREST_ACCESS_KEY_FILE \
              "$nr_py" "$nr_atlas" key --check --quiet --keyring "$nr_ring" 2>/dev/null)"
  case "$?" in
    0) ;;
    7) NR_ACCESS_WHY="nokey"; return 0 ;;
    *) NR_ACCESS_WHY="noverifier"; return 0 ;;
  esac
  case "$nr_out" in
    *"notrest-access: ok ring="*) ;;
    *) NR_ACCESS_WHY="nosentinel"; return 0 ;;
  esac
  if [ -n "$nr_ringhash" ]; then
    case "$nr_out" in
      *"notrest-access: ok ring=${nr_ringhash:0:12}"*) ;;
      *) NR_ACCESS_WHY="ringmismatch"; return 0 ;;
    esac
  fi
  # ...and the sentinel must name the very file we pinned (lane A, 2026-09-06): a correct
  # hash for SOMEBODY ELSE'S keyring is still somebody else's keyring.
  if [ -n "$nr_ringcmp" ]; then
    case "$nr_out" in
      *"path=$nr_ring"*) ;;
      *) NR_ACCESS_WHY="ringpath"; return 0 ;;
    esac
  fi
  NR_ACCESS=1; NR_ACCESS_WHY="ok"
  return 0
}

nr_access_ok
# NR_SKIP_ROOT=1: the caller wants only the access verdict. Root resolution forks `git`,
# and router.sh asks this question on every prompt — the verdict is builtins-only, so a
# hook that needs the gate and not the root should not pay for the root.
[ -n "${NR_SKIP_ROOT:-}" ] || nr_estate_root

# SOURCED (the four hooks) → return here. EXECUTED directly (the fixture's
# four-hooks-agree assert runs it as a script and reads NR_ESTATE_ROOT off stdout) →
# `return` fails outside a function, so the printing path below runs instead. The
# trailing `exit 0` also satisfies the HOOK-CONTRACT law, which reads every hooks/*.sh
# and requires that last statement — a sourced file must therefore never REACH it.
return 0 2>/dev/null || true
printf '%s\n' "$NR_ESTATE_ROOT"
exit 0
