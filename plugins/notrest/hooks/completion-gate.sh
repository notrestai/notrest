#!/bin/bash
# notrest Stop hook — THE COMPLETION GATE (docket item 8b).
#
# The estate already gates the SHIP (hooks/pretool-gate.sh refuses `git push` while the
# instruments are red) and the SPAWN (hooks/spawn-gate.sh refuses an unlawful lane). The
# hole between them is the CLAIM: a session can declare the work done while the very
# checks the commission named are red, and nothing in the harness contradicts it. This
# hook closes it — the vacuous-pass killer applied to "done", not only to the push.
#
# CONTRACT — the estate declares its gates in ONE file, `gates/ACTIVE.md` at the estate
# root, in the CHECK:/EXPECT: format hooks/gate-check.py runs (see that file's header).
# No `gates/ACTIVE.md` → this hook does nothing at all, in every repo on the machine.
# That is deliberate: a gate that arms itself is a gate nobody chose.
#
#   BLOCK   exit 2 with the reason on stderr — the Stop-hook contract feeds stderr back
#           to the model as the reason it may not stop. The same reason is ALSO written
#           to stdout as {"decision":"block","reason":…}, the documented JSON channel,
#           so a loader that reads the decision instead of the exit code blocks
#           identically. Belt and braces, exactly as pretool-gate.sh does for deny.
#   ALLOW   exit 0, silent.
#
# LOOP GUARD — the harness re-runs Stop hooks after a block, and a hook that blocks
# unconditionally wedges the session forever. `stop_hook_active` is true on any such
# re-entry and is honored here: the gate speaks ONCE, then gets out of the way.
#
# FAIL-OPEN — no set -e; a missing checker, a missing python3, a malformed payload, an
# unreadable gates file: every one of them ALLOWS, with a one-line note on stderr. A
# broken gate must never be able to trap a session. The note is not optional: a gate
# that fails silently is indistinguishable from a gate that passed.

PAYLOAD="$(cat 2>/dev/null || true)"

# ── loop guard first: cheapest, and the one path that must never be skipped.
# A payload we cannot parse ALLOWS rather than blocks — the loop guard lives in that
# payload, so blocking on an unreadable one is exactly how a gate wedges a session
# forever. Unparseable is a malfunction of ours, and a malfunction never blocks.
PSTATE="$(printf '%s' "$PAYLOAD" | python3 -c 'import sys, json
try:
    d = json.load(sys.stdin)
    if not isinstance(d, dict):
        raise ValueError
    sys.stdout.write("active" if d.get("stop_hook_active") is True else "ok")
except Exception:
    sys.stdout.write("bad")' 2>/dev/null)"
case "$PSTATE" in
  active) exit 0 ;;
  ok)     : ;;
  *)      printf '[notrest] completion gate: unreadable Stop payload — gates NOT checked this stop (failing open).\n' >&2
          exit 0 ;;
esac

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── estate root: the ONE resolver every estate hook shares. No root → not our estate.
. "$HOOK_DIR/estate-root.sh" 2>/dev/null || true
ROOT="${NR_ESTATE_ROOT:-}"
if [ -z "$ROOT" ]; then
  # RB-7 (refuter, 2026-09-01): this path was MUTE, and this file's own law says a gate
  # that fails silently cannot be told apart from a gate that passed. The note is raised
  # only where something was actually DECLARED — a session stopping in a plain directory
  # has no contract to fail open on, and a line printed at every stop on the machine
  # would be noise, not evidence.
  [ -f "./gates/ACTIVE.md" ] && printf '[notrest] completion gate: ./gates/ACTIVE.md declares a contract but no estate root resolves here — gates NOT checked this stop (failing open).\n' >&2
  exit 0
fi

ACTIVE="$ROOT/gates/ACTIVE.md"
[ -f "$ACTIVE" ] || exit 0

# Containment, the same law COORD.md and the auto-build marker are held to: a gates file
# that resolves OUTSIDE the estate is not this estate's contract.
if command -v python3 >/dev/null 2>&1; then
  CONTAINED="$(python3 -c 'import os, sys
r = os.path.realpath(sys.argv[1]); p = os.path.realpath(sys.argv[2])
sys.stdout.write("y" if p == r or p.startswith(r + os.sep) else "")' "$ROOT" "$ACTIVE" 2>/dev/null)"
  if [ -z "$CONTAINED" ]; then
    # RB-7: refusing in silence looked exactly like passing. Refuse, and say it.
    printf '[notrest] completion gate: %s resolves OUTSIDE the estate — not this estate'"'"'s contract, gates NOT checked this stop (failing open).\n' \
      "$ACTIVE" >&2
    exit 0
  fi
fi

CHECKER="$HOOK_DIR/gate-check.py"
if [ ! -f "$CHECKER" ] || ! command -v python3 >/dev/null 2>&1; then
  printf '[notrest] completion gate: cannot run %s — gates NOT checked this stop (failing open).\n' \
    "$CHECKER" >&2
  exit 0
fi

OVERRIDE=""
[ "${NOTREST_GATE_OVERRIDE:-}" = "1" ] && OVERRIDE="env"

# --timeout bounds each CHECK (RB-2: nothing between an arbitrary shell line and the
# session capped it). The harness caps this hook in turn, via the "timeout" field on the
# Stop entry in hooks.json — three layers, none of them trusting the one below it.
REPORT="$(python3 "$CHECKER" "$ACTIVE" --cwd "$ROOT" --quiet --timeout 30 --budget 50 2>&1)"
RC=$?

# 0 = green · 3 = the declared contract could not be PARSED · 5 = a gate is red.
# ANY other code is the instrument itself failing (2 unreadable at the OS level, 127 no
# interpreter, …) and must not be read as a verdict.
if [ "$RC" -eq 0 ]; then
  exit 0
fi
if [ "$RC" -ne 5 ] && [ "$RC" -ne 3 ]; then
  printf '[notrest] completion gate: gate-check exited %s (not a verdict) — gates NOT checked this stop (failing open).\n' \
    "$RC" >&2
  exit 0
fi

# ── RB-1b (seat ruling): a declared contract nobody can read is a RED gate, not an
# absence. The alternative — failing open — is precisely the vacuous green the refuter
# found: an unterminated fence swallowed the estate's real `CHECK: false` and the stop
# was permitted. An estate that declares a contract and ships it broken gets told.
if [ "$RC" -eq 3 ]; then
  RED="$(printf '%s\n' "$REPORT" | grep 'CONTRACT UNREADABLE' | head -1 | sed 's/^/   /')"
  [ -n "$RED" ] || RED="   CONTRACT UNREADABLE: gates/ACTIVE.md could not be parsed"
else
  RED="$(printf '%s\n' "$REPORT" | grep '^RED:' | sed 's/^/   /')"
  [ -n "$RED" ] || RED="   (gate-check reported red but named nothing — read gates/ACTIVE.md)"
fi

if [ -n "$OVERRIDE" ]; then
  printf '[notrest] COMPLETION GATE OVERRIDDEN (%s): declared gates are RED and the stop was permitted anyway.\n%s\n' \
    "$OVERRIDE" "$RED" >&2
  printf '%s' "$RED" | python3 -c 'import sys, json
print(json.dumps({"systemMessage":
    "[notrest] completion gate OVERRIDDEN via env — red gates:\n" + sys.stdin.read()}))' 2>/dev/null
  exit 0
fi

if [ "$RC" -eq 3 ]; then
  HEADLINE="notrest completion gate: completion is not earned — gates/ACTIVE.md declares a contract that CANNOT BE READ, so nothing was verified:"
else
  HEADLINE="notrest completion gate: completion is not earned — gates/ACTIVE.md declares gates that are RED right now:"
fi

REASON="$HEADLINE
$RED

Do not report this work as done. Fix the red gates, or say plainly that they are red and
why you are stopping anyway. Re-run them yourself with:
   python3 $CHECKER $ACTIVE --cwd $ROOT
Override (states itself in the transcript): NOTREST_GATE_OVERRIDE=1"

printf '%s\n' "$REASON" >&2
printf '%s' "$REASON" | python3 -c 'import sys, json
print(json.dumps({"decision": "block", "reason": sys.stdin.read()}))' 2>/dev/null
exit 2

exit 0
