#!/bin/bash
# pulse-layer-positive-controls.sh — S71 / DW1.
#
# ⛔ A GREEN CHECK NOBODY HAS EVER SEEN GO RED IS NOT EVIDENCE, IT IS FURNITURE.
#
# pulse-layer-fixture.sh asserted a clean process tree with `pgrep -P $$ 2>/dev/null | wc -l`
# compared against "0". `pgrep` is not installed on this host, so that pipeline PRINTED THE
# EXPECTED VALUE ON FAILURE and the assertions could not go red. This script plants, for every
# repaired assertion, the condition that assertion exists to catch, and requires the fixture's
# own verdict machinery to print FAIL.
#
# Each assertion gets THREE controls, because a repaired check has three outcomes:
#   · negative control — the honest world, must be GREEN (a repair that is always red is not a
#     repair; the first draft of this one was, and only driving it showed that)
#   · POSITIVE control — the defect planted, must be RED
#   · PROBE-UNAVAILABLE control — the instrument itself broken, must be RED and must SAY SO
#
# HOW IT JUDGES, AND WHY NOT THE OBVIOUS WAY: it extracts the fixture's probe+verdict block
# verbatim and reads the VERDICT LINE that block prints — what a reader of a doctor run
# actually sees. It does NOT reuse t()/tprobe() to grade itself. ⛔ A test written in the
# subject's vocabulary cannot find the subject's blind spot.
#
# Every scenario runs as its own top-level `bash` process, never a subshell: `$$` inside a
# subshell is the PARENT's pid, which would silently measure the wrong process tree.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX="$HERE/pulse-layer-fixture.sh"
[ -f "$FIX" ] || { echo "positive-controls: no fixture at $FIX" >&2; exit 2; }

SB="$(mktemp -d)"; PROBES="$SB/probes.sh"
cleanup(){ rm -rf "$SB"; }
trap cleanup EXIT INT TERM

sed -n '/^ok(){ PASS=/,/^# <<< S71-PROBES-END/p' "$FIX" > "$PROBES"
NDEF="$(/usr/bin/grep -c -E '^[a-z_]+\(\) *\{' "$PROBES")"
if [ "$NDEF" -lt 10 ]; then
  echo "positive-controls: extracted only $NDEF helper definitions (expected >=10)." >&2
  echo "  The S71-PROBES markers in $FIX have moved. REFUSING TO RUN: a control harness that" >&2
  echo "  silently tests an empty extraction is the very defect this script exists to catch." >&2
  exit 2
fi

# A genuine orphan. `setsid` alone does NOT reparent — driven 2026-08-26, a setsid'd child
# kept its spawning shell as parent. Only the PARENT EXITING reparents a process, so this
# double-forks and reaps the middle process. (Verified on this host: an orphan lands on
# ppid 1, whose cmdline is `sleep infinity` — a container init, but a real reaper.)
cat > "$SB/orphan.py" <<'ORPHEOF'
import os, sys
mk = sys.argv[1]
r, w = os.pipe()
if os.fork() == 0:
    os.close(r)
    grandchild = os.fork()
    if grandchild == 0:
        os.close(w); os.setsid(); os.execv('/bin/bash', ['bash', mk])
    os.write(w, str(grandchild).encode()); os.close(w); os._exit(0)
os.close(w)
sys.stdout.write(os.read(r, 32).decode()); os.close(r)
os.wait()
ORPHEOF

CPASS=0; CFAIL=0
drive(){   # drive <setup> <assertion> -> whatever that scenario printed (stdout+stderr)
  { echo 'set +u'; echo 'PASS=0; FAIL=0'; echo "SBX=\"$SB\""; echo ". \"$PROBES\""
    echo "$1"; echo "$2"; } > "$SB/case.sh"
  bash "$SB/case.sh" 2>&1
}
control(){ # control <RED|GREEN> <name> <setup> <assertion> [<verdict must contain>]
  local want="$1" name="$2" saw
  drive "$3" "$4" > "$SB/out.txt"
  # grep applied DIRECTLY to a file — no pipeline, no suppressed stderr.
  if   /usr/bin/grep -q -E '^[[:space:]]*FAIL ' "$SB/out.txt"; then saw=RED
  elif /usr/bin/grep -q -E '^[[:space:]]*PASS ' "$SB/out.txt"; then saw=GREEN
  else saw=NO-VERDICT; fi
  if [ "$saw" != "$want" ]; then
    CFAIL=$((CFAIL+1)); echo "  CONTROL-FAIL  $name — wanted $want, the fixture said $saw"
    sed 's/^/                  | /' "$SB/out.txt"; return
  fi
  if [ -n "${5:-}" ] && ! /usr/bin/grep -q -F -- "$5" "$SB/out.txt"; then
    CFAIL=$((CFAIL+1)); echo "  CONTROL-FAIL  $name — verdict was $saw but never said [$5]"
    sed 's/^/                  | /' "$SB/out.txt"; return
  fi
  CPASS=$((CPASS+1)); echo "  CONTROL-OK    [$saw] $name"
}

BROKEN_PROBE='children_of(){ echo "children_of: simulated instrument failure" >&2; return 3; }'
PLANT_CHILD='sleep 30 & CHILDPID=$!'
REAP='kill $CHILDPID 2>/dev/null; wait 2>/dev/null'

echo "── group A — the three child-count assertions (the three that could not go red)"
A1='tprobe "a spawned refresher is NOT a child of its spawner" "0" children_of $$'
A2='tprobe "watch --once leaves no children behind" "0" children_of $$'
A3='tprobe "…and it is not a child of this fixture" "0" children_of $$'
i=0
for ASSERT in "$A1" "$A2" "$A3"; do
  i=$((i+1))
  control GREEN "A$i negative control — a genuinely clean tree passes"            ''              "$ASSERT"
  control RED   "A$i POSITIVE CONTROL — a real live child is CAUGHT"              "$PLANT_CHILD"  "$ASSERT; $REAP"
  control RED   "A$i PROBE-UNAVAILABLE control — a broken instrument FAILS LOUD"  "$BROKEN_PROBE" "$ASSERT" "PROBE UNAVAILABLE"
done

echo "── group B — the reparenting assertion (a survivor's ppid must be 1)"
B='tprobe "a daemonized watcher is reparented to init" "1" ppid_of "$TARGET"'
control GREEN "B negative control — a genuine orphan (ppid 1) passes" \
  'MK="$SBX/s71-sleeper.sh"; printf "#!/bin/bash\nsleep 40\n" > "$MK"; chmod +x "$MK"
   TARGET="$(python3 "$SBX/orphan.py" "$MK")"
   for _ in 1 2 3 4 5 6 7 8 9 10; do [ "$(ppid_of "$TARGET")" = "1" ] && break; sleep 0.3; done' \
  "$B"' ; kill_matching "s71-sleeper"'
control RED   "B POSITIVE CONTROL — a merely-backgrounded child (ppid != 1) is CAUGHT" \
  'sleep 30 & TARGET=$!' \
  "$B"' ; kill $TARGET 2>/dev/null; wait 2>/dev/null'
control RED   "B PROBE-UNAVAILABLE control — a dead pid FAILS LOUD, saying why" \
  'TARGET=999999' "$B" "PROBE UNAVAILABLE"

echo "── group C — the COORD-untouched assertion"
C='tprobe "estate-pulse never writes COORD" "0" count_in "[pulse]" "$CO"'
control GREEN "C negative control — a COORD with no pulse line passes" \
  'CO="$SBX/c1.md"; printf "%s\n" "- [x] ordinary ledger line" > "$CO"' "$C"
control RED   "C POSITIVE CONTROL — a planted [pulse] line is CAUGHT" \
  'CO="$SBX/c2.md"; printf "%s\n" "- [2026-08-26 00:00Z] [pulse] estate pulse -> ok" > "$CO"' "$C"
control RED   "C PROBE-UNAVAILABLE control — a missing COORD.md FAILS LOUD, saying why" \
  'CO="$SBX/does-not-exist.md"' "$C" "PROBE UNAVAILABLE"

echo "── group E — the reaper must never match the tree it is running inside"
# ⛔ This one is not a repair of an assertion; it is a SAFETY control on the instrument.
# A cmdline search matches any process that merely MENTIONS the pattern. Driven: an earlier
# build of kill_matching matched the invoking shell (whose command line carried the pattern
# inside a heredoc) and KILLED IT — the run died at exit 144 mid-suite. `pkill -f` had the
# identical hazard and was saved only by pkill being absent from this host.
control GREEN "E SAFETY CONTROL — a search run from inside a matching process excludes self and ancestors" \
  'printf "#!/bin/bash\n. \"\$1/probes.sh\"\nHITS=\"\$(pids_matching s71-sleeper)\"\n[ -z \"\$HITS\" ] && echo CLEAN || echo \"LEAKED: \$HITS\"\n" > "$SBX/s71-sleeper-probe.sh"
   RES="$(bash "$SBX/s71-sleeper-probe.sh" "$SBX")"' \
  'if [ "$RES" = "CLEAN" ]; then ok "the reaper excludes its own tree ($RES)"; else no "the reaper would kill its own tree — $RES"; fi'

echo "── group D — THE REGRESSION ITSELF: old probe and new, same planted child"
drive 'sleep 30 & CHILDPID=$!' \
  'OLDV="$(pgrep -P $$ 2>/dev/null | wc -l | tr -d " ")"
   NEWV="$(children_of $$)"
   echo "old pgrep probe saw [$OLDV] · repaired /proc probe saw [$NEWV]"
   if [ "$OLDV" = "0" ] && [ "$NEWV" != "0" ]; then
     echo "OLD-PROBE-BLIND: it reported a clean tree while a real child was running"
   fi
   kill $CHILDPID 2>/dev/null; wait 2>/dev/null' > "$SB/regress.txt"
sed 's/^/                  | /' "$SB/regress.txt"
if /usr/bin/grep -q -F "OLD-PROBE-BLIND" "$SB/regress.txt"; then
  CPASS=$((CPASS+1)); echo "  CONTROL-OK    [DEMONSTRATED] the old probe is blind to what the new one catches"
else
  CFAIL=$((CFAIL+1)); echo "  CONTROL-FAIL  the old probe was NOT blind here — this host may have pgrep; re-derive S71"
fi

echo
echo "controls: $CPASS ok, $CFAIL failed"
[ "$CFAIL" -eq 0 ] || exit 1
