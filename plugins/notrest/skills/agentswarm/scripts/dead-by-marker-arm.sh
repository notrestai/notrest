#!/bin/bash
# S83 PART 1 — BORN-RED ARM for DEAD-BY-MARKER.
#
# A lane whose transcript ENDS IN A TERMINAL MARKER was interrupt-killed. That is a
# DIFFERENT FACT from "frozen and unreceipted" (STALL) and from "receipted" (done), and the
# watcher must say WHICH. Two states that look identical from the outside have been this
# estate's whole finding four times tonight.
#
# ⛔ EVERY STAMP IS COMPUTED FROM `date -u` AT RUN TIME. No literal dates: a fixture
# carrying one has an expiry and would flip silently as the clock moves (Master b3344ea).
# ⛔ VERDICT LAST.
set -u
# Subject resolved from this script's own location — a hardcoded author-machine path
# made this arm exit 2 on every other box (found by the 2026-08-31 battery: the arm
# had never run on the machine it shipped from).
ARMHERE="$(cd "$(dirname "$0")" && pwd)"
W="$ARMHERE/swarm.py"
[ -f "$W" ] || { echo "arm: SUBJECT MISSING - no swarm.py at $W" >&2; exit 2; }
SB="$(mktemp -d)"; trap 'rm -rf "$SB"' EXIT INT TERM
R="$SB/fixroot"; mkdir -p "$R/spend"

NOW_EPOCH="$(date -u +%s)"
RECEIPT_TS="$(date -u -d @"$((NOW_EPOCH - 3600))" '+%Y-%m-%d %H:%MZ')"
echo "     receipt stamp computed at run time: $RECEIPT_TS"

# one RECEIPTED lane, so collect() has receipts and the sweep proceeds at all
printf '[%s] lane=subagent model=claude-opus-5 tokens=1000 grade=observed purpose="done lane" agent=aRECEIPTEDLANE0001\n' \
  "$RECEIPT_TS" > "$R/spend/ledger.md"

# the MARKER-DEAD lane, transcribed to the tasks dir this host really uses
SLUG="-$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]).lstrip("/").replace("/","-"))' "$R")"
TD="/tmp/claude-$(id -u)/$SLUG/sess1/tasks"
mkdir -p "$TD"
DEAD=aDEADBYMARKER00001
python3 - "$TD/$DEAD.output" <<'PY'
import json, sys
p = sys.argv[1]
recs = [
  {"type": "assistant", "message": {"role": "assistant",
      "content": [{"type": "text", "text": "working on it"}]}},
  {"type": "user", "message": {"role": "user",
      "content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
]
open(p, "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in recs) + "\n")
PY
# idle well past STALL_SECS (600) so the CURRENT watcher would call it STALL - computed, not literal
# os.utime, not `touch -d "@epoch"`: that @-form is GNU-only — on BSD/macOS touch
# rejects it, the mtime silently stays NOW, idle reads 0s, and no stall-class
# alert can ever fire (second Linuxism found by the 2026-08-31 battery).
python3 -c 'import os,sys; t=int(sys.argv[2]); os.utime(sys.argv[1],(t,t))' "$TD/$DEAD.output" "$((NOW_EPOCH - 3000))"

# ⛔ NEGATIVE CONTROL, and it is the arm that matters most: a lane that is NOT marker-dead,
# equally idle and equally unreceipted, MUST STILL ALERT. Without it, a change that
# suppressed every alert would pass all three assertions above and look like a fix.
CTRL=aSTILLSTALLING0001
python3 - "$TD/$CTRL.output" <<'PY'
import json, sys
recs = [{"type": "assistant", "message": {"role": "assistant",
         "content": [{"type": "text", "text": "still working, no terminal marker here"}]}}]
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in recs) + "\n")
PY
python3 -c 'import os,sys; t=int(sys.argv[2]); os.utime(sys.argv[1],(t,t))' "$TD/$CTRL.output" "$((NOW_EPOCH - 3000))"
echo "     transcript idle by: $(( (NOW_EPOCH - (NOW_EPOCH - 3000)) / 60 ))m (computed)"

# `report` reads RECEIPTS; the liveness/STALL sweep is `watch`. The first draft drove
# `report`, found no lane line at all, and two of its three arms then passed VACUOUSLY -
# a pass over an absent subject is not a pass.
# `watch --once` writes its sweep to <root>/pulse/swarm-live.txt, not to stdout.
python3 "$W" watch --root "$R" --once > "$SB/watch.stdout" 2>&1; rc=$?
OUT="$(cat "$R/pulse/swarm-live.txt" 2>/dev/null)"
echo "     watch --once exit=$rc · sweep lines=$(printf '%s' "$OUT" | /usr/bin/grep -c . )"
LANE_LINE="$(printf '%s' "$OUT" | /usr/bin/grep -F "$DEAD" | head -2)"
echo "     lane line(s):"
printf '%s\n' "$LANE_LINE" | sed 's/^/       | /'

pass=0; fail=0; cant=0
# PRECONDITION: the arm must find its subject before it may judge it.
if [ -z "$LANE_LINE" ]; then
  cant=1
  echo "  ⛔ COULD-NOT-TEST  the sweep produced no line for $DEAD - the arm never found its"
  echo "                    subject, so every verdict below would be a pass over nothing."
  printf '%s\n' "$OUT" | head -12 | sed 's/^/       | /'
  echo
  echo "arm: 0 ok, 0 red, 1 could-not-test"
  exit 2
fi
if printf '%s' "$OUT" | /usr/bin/grep -qiF 'DEAD-BY-MARKER'; then
  pass=$((pass+1)); echo "  OK   the report labels the interrupted lane DEAD-BY-MARKER"
else
  fail=$((fail+1)); echo "  RED  the report does NOT label it DEAD-BY-MARKER - an interrupt-killed lane is indistinguishable from a stall"
fi
if printf '%s' "$LANE_LINE" | /usr/bin/grep -qiE '\bdone\b'; then
  fail=$((fail+1)); echo "  RED  it COLLAPSED into 'done' - a killed lane is not a completed one"
else
  pass=$((pass+1)); echo "  OK   it did not collapse into 'done'"
fi
if printf '%s' "$OUT" | /usr/bin/grep -qE "ALERT STALL[^-]* $DEAD|ALERT STALL $DEAD"; then
  fail=$((fail+1)); echo "  RED  a STALL alert fired for a lane that is dead by marker - nothing to probe, resume or stop"
else
  pass=$((pass+1)); echo "  OK   no STALL alert for the marker-dead lane"
fi

CTRL_LINE="$(printf '%s' "$OUT" | /usr/bin/grep -F "$CTRL" | head -2)"
echo "     control lane line(s):"
printf '%s\n' "$CTRL_LINE" | sed 's/^/       | /'
if [ -z "$CTRL_LINE" ]; then
  cant=1; echo "  ⛔ COULD-NOT-TEST  the control lane never appeared - cannot show alerts still fire"
elif printf '%s' "$OUT" | /usr/bin/grep -qE "ALERT STALL(-UNRESOLVABLE)? $CTRL"; then
  pass=$((pass+1)); echo "  OK   NEGATIVE CONTROL: a non-marker lane STILL ALERTS - the change did not silence the watcher"
else
  fail=$((fail+1)); echo "  RED  NEGATIVE CONTROL FAILED: no alert for a lane that is merely stalled - alerts were suppressed too broadly"
fi
if printf '%s' "$CTRL_LINE" | /usr/bin/grep -qiF 'dead-marker'; then
  fail=$((fail+1)); echo "  RED  the control lane was mislabelled dead-marker - the predicate is too loose"
else
  pass=$((pass+1)); echo "  OK   the control lane was NOT labelled dead-marker"
fi

echo
echo "arm: $pass ok, $fail red, ${cant:-0} could-not-test"          # VERDICT LAST
[ "$fail" -eq 0 ] || exit 1
