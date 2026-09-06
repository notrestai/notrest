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

# ── NR-STDIN (E2, 4.6.2) — BOUNDED READ: the payload or nothing, never a hang.
# Contract, rationale and the bash-3.2 measurements live in hooks/pretool-gate.sh, which
# owns the budget; the loop is copied rather than sourced because sourcing a sibling
# costs a fork on that hook's fast path and would make reading stdin depend on a second
# file. TOTAL stdin wall time is bounded by NR_STDIN_WAIT (5 s) plus the sub-second
# granularity of SECONDS — not per read — and an idle stdin yields "", on which this
# hook fails open.
# The wait is a knob for fixtures, so it is VALIDATED, not trusted: a non-numeric -t
# makes read fail instantly (a silently disarmed hook) and a huge one restores the
# hang this fixes. Anything but 1-99 falls back to 5. `case`, so still no fork.
case "${NR_STDIN_WAIT:-}" in [1-9]|[1-9][0-9]) ;; *) NR_STDIN_WAIT=5 ;; esac
NR_RAW=""; NR_DL=$((SECONDS + NR_STDIN_WAIT))
while :; do
  NR_T=$((NR_DL - SECONDS))   # the REMAINING budget, never a fresh one per read (F4)
  [ "$NR_T" -ge 1 ] || break
  NR_LINE=""
  IFS= read -r -t "$NR_T" NR_LINE || { NR_RAW="$NR_RAW$NR_LINE"; break; }
  NR_RAW="$NR_RAW$NR_LINE"
done
PAYLOAD="$NR_RAW"

# ── NOTHING TO CHECK IS NOT A MALFUNCTION (F7, 4.6.2). An EMPTY payload used to print
# the unreadable-payload notice, so every stop with no payload on stdin — the fixtures,
# any loader that hands the hook nothing — read as a gate that had failed. Empty means
# no stop to gate: exit silently. A NON-EMPTY payload we cannot parse is still a
# malfunction and still says so on stderr, per the fail-open law above.
[ -n "$PAYLOAD" ] || exit 0

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
# ── THE ACCESS KEY (4.8): no key, no harness. This gate BLOCKS, and a block is the
# loudest thing the suite does — an unlicensed machine gets none of it. The DENY rules of
# spawn-gate.sh and pretool-gate.sh are the deliberate exception and stay armed.
[ -n "${NR_ACCESS:-}" ] || exit 0
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


# ── THE LEARNINGS GATE (4.6.3). The gates above ask "are the declared checks green?";
# this asks the other half of "done": WAS THE LESSON BANKED? `index.py learnings
# --triggers --json` answers it — the trigger tags, the window and the citation
# check are ONE implementation, over there, and this hook only formats the refusal.
# A lesson lived and not written down means the loop never closed, so this blocks
# exactly like a red gate does.
#
# ARMED BY THE STORE, never by this hook: no archive/findings.jsonl, no COORD.md, no
# index.py, no python3, or an index.py that does not know the verb → return, silently,
# having done nothing. Every failure path here is silent on purpose (brief 4.6.3): this
# runs at EVERY stop in every estate on the machine, and a note on each one would be
# noise rather than evidence — unlike the gates path, where a contract was declared.
nr_learnings_gate() {
  [ -f "$ROOT/archive/findings.jsonl" ] || return 0
  [ -f "$ROOT/COORD.md" ] || return 0
  NR_IDX="$HOOK_DIR/../skills/archivist/scripts/index.py"
  [ -f "$NR_IDX" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0

  NR_LREASON="$(NR_ROOT="$ROOT" NR_IDX="$NR_IDX" python3 <<'NRPY' 2>/dev/null
import json, os, re, subprocess, sys

# THE HOOK MATCHES NOTHING (seat correction, 2026-09-05). Trigger extraction — the regex,
# the window, and which triggers are already cited — lives ONCE, in index.py, behind
# `learnings --triggers --uncited`. A copy of that logic here would be a second authority
# that drifts silently the first time the tag set changes. This block asks, and formats.
root = os.environ["NR_ROOT"]
idx = os.environ["NR_IDX"]

try:
    p = subprocess.run([sys.executable, idx, "learnings", "--root", root,
                        "--triggers", "--json"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
    # A refusal, a missing verb, a bad payload: all one answer — no basis to block.
    if p.returncode != 0:
        raise SystemExit(0)
    blob = json.loads(p.stdout.decode("utf-8", "replace") or "null")

    # THE CONTRACT (seat-relayed, 2026-09-05), and nothing else is read:
    #   {"armed": bool, "floor": "<ts>|null", "regex": "...",
    #    "uncited": [{"ts": "[…]", "headline": "…"}], "cited": <n>}
    # ARMED IS THE ARMING FLOOR. A store with no learnings has no floor, and without one
    # every old line in the ledger looks unbanked — live-proven on the seat, which was
    # blocked over a line from 2026-07-25. Not armed, or the key absent (an older verb),
    # means this gate says nothing at all. Absence is treated as UNARMED on purpose: the
    # gate that cannot tell must not be the gate that blocks.
    if not isinstance(blob, dict) or blob.get("armed") is not True:
        raise SystemExit(0)
    # TWO WAYS A STOP IS UNEARNED, both answered by the same call (4.7.0):
    #   uncited  — the estate PAID for a lesson and nobody banked it;
    #   untested — the session ADMITTED it did not verify something, and no `open` record
    #              carries that admission forward. An untested claim with no open record
    #              is how "we'll check later" becomes never.
    # uncited is reported first: a paid lesson lost is the more expensive of the two.
    unc = blob.get("uncited") if isinstance(blob.get("uncited"), list) else []
    unt = blob.get("untested") if isinstance(blob.get("untested"), list) else []
    if not unc and not unt:
        raise SystemExit(0)
    items, mode = (unc, "uncited") if unc else (unt, "untested")

    first = items[0] if isinstance(items[0], dict) else {}
    ts = str(first.get("ts") or "").strip()
    line = str(first.get("headline") or "").strip()
    if not ts and not line:
        raise SystemExit(0)
    ts = ts.strip("[]")
    # The excerpt is clipped by BYTES, not characters: the ledger is UTF-8 and a
    # character clip can still blow a byte budget.
    line = line.encode("utf-8")[:200].decode("utf-8", "ignore")

    idxpath = "$CLAUDE_PLUGIN_ROOT/skills/archivist/scripts/index.py"
    if mode == "uncited":
        head = ("notrest completion gate: completion is not earned — a lesson was lived "
                "and never banked.\n"
                "The COORD line at [%s] is trigger-tagged and no learning cites it:" % ts)
        fix = ("Bank it before you stop (statement <=300 chars; evidence and scope are "
               "both required):\n"
               "   python3 %s add --kind learning --tag LEARNED \\\n"
               "     --statement '<what will be done differently, in one sentence>' \\\n"
               "     --evidence '[%s]' --scope '<path glob, skill name, or estate>'"
               % (idxpath, ts))
    else:
        head = ("notrest completion gate: completion is not earned — something was left "
                "UNTESTED and nothing carries it forward.\n"
                "The COORD line at [%s] admits it was not verified, and no open record "
                "cites it:" % ts)
        fix = ("Open it before you stop (an untested claim needs an owner and a date, or "
               "it is never revisited):\n"
               "   python3 %s add --kind open \\\n"
               "     --statement '<what is still unverified>' \\\n"
               "     --closes-when '<the check that would settle it>' \\\n"
               "     --owner '<seat or a lane id>' --recheck YYYY-MM-DD \\\n"
               "     --evidence '[%s]' --scope '<path glob, skill name, or estate>'"
               % (idxpath, ts))

    sys.stdout.write("%s\n   %s\n\n%s\n\nOverride (states itself in the transcript): "
                     "NOTREST_GATE_OVERRIDE=1" % (head, line.strip(), fix))
    raise SystemExit(7)
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
NRPY
)"
  [ "$?" -eq 7 ] || return 0
  [ -n "$NR_LREASON" ] || return 0

  # The override stays LOUD, exactly as the gates path treats it: a bypassed gate that
  # says nothing is worse than no gate.
  if [ "${NOTREST_GATE_OVERRIDE:-}" = "1" ]; then
    printf '[notrest] LEARNINGS GATE OVERRIDDEN (env): a trigger-tagged COORD line is still unbanked.\n' >&2
    return 0
  fi
  printf '%s\n' "$NR_LREASON" >&2
  printf '%s' "$NR_LREASON" | python3 -c 'import sys, json
print(json.dumps({"decision": "block", "reason": sys.stdin.read()}))' 2>/dev/null
  exit 2
}

ACTIVE="$ROOT/gates/ACTIVE.md"
# No declared gates is not the end of the stop any more: the learnings gate is armed by
# the STORE, not by gates/ACTIVE.md, so it runs on this path too.
[ -f "$ACTIVE" ] || { nr_learnings_gate; exit 0; }

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
# session capped it), --budget bounds all of them together. The harness caps this hook in
# turn, via the "timeout" field on the Stop COMMAND OBJECT in hooks.json — three layers,
# none of them trusting the one below it. (Placement corrected 2026-09-01: that timeout
# sat on the matcher GROUP from 4.5.0, where the schema does not read it, so the outer
# layer was configured and not in effect. 60 s outer vs --budget 50 is the margin.)
REPORT="$(python3 "$CHECKER" "$ACTIVE" --cwd "$ROOT" --quiet --timeout 30 --budget 50 2>&1)"
RC=$?

# 0 = green · 3 = the declared contract could not be PARSED · 5 = a gate is red.
# ANY other code is the instrument itself failing (2 unreadable at the OS level, 127 no
# interpreter, …) and must not be read as a verdict.
if [ "$RC" -eq 0 ]; then
  nr_learnings_gate   # gates green — now the other half of "done" (4.6.3)
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
