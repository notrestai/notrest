#!/bin/bash
# pulse-layer-fixture.sh — the machine-written PULSE LAYER, asserted end to end.
#
# The layer's whole value is that nobody waits for it, so the assertions are about
# TIMING and RESTRAINT as much as content: the caller returns immediately, the detached
# refresh really completes, five stops in a row produce ONE refresh, and COORD is never
# touched by any of it.
#
# TRAP LAW (2026-08-05): this fixture spawns DETACHED background refreshers. A fixture
# that leaves stray processes chewing on a deleted mktemp dir is a defect, so the trap
# reaps every child it started before removing the sandbox.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOKS="$(cd "$HERE/../../../hooks" && pwd)"
EST="$(cd "$HERE/../../notrest/scripts" && pwd)/establish.py"
SWARM="$(cd "$HERE/../../agentswarm/scripts" && pwd)/swarm.py"
W="$(mktemp -d)"
# pkill is ABSENT on this host, so the old reaper was a silent no-op that leaked every
# process it claimed to reap. kill_matching (below) reads /proc and says when it cannot.
cleanup(){ kill_matching "estate-pulse.sh $W"; kill_matching "swarm.py watch --root $W"; sleep 0.3; rm -rf "$W"; }
trap cleanup EXIT INT TERM
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF -- "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — [$2] not in $3"; fi; }
waitfor(){ for _ in $(seq 1 40); do [ -f "$1" ] && return 0; sleep 0.25; done; return 1; }

# >>> S71-PROBES-BEGIN (extracted verbatim by pulse-layer-positive-controls.sh)
# ── PROBE ACCEPTANCE (S71). An instrument that cannot run must SAY SO, never pass.
# What this replaced, and why: the child-count checks below were written as
#   pgrep -P $$ 2>/dev/null | wc -l | tr -d ' '   compared against "0"
# On a host with no pgrep that pipeline prints "0" — EXACTLY the value the assertion
# expects. A suppressed producer failure was indistinguishable from a true zero, so the
# checks could not go red; driven with a real child spawned, the old probe still said 0.
# The subject here is a PROCESS TREE and the only instrument on this host that holds it
# is /proc. (SKILL.md:153's "ask the instrument, not pgrep" names `swarm.py report`, whose
# population is the RECEIPTS LEDGER — a detached refresher never enters that corpus, so
# its silence about one would not be evidence. Ask what would have put the subject in the
# corpus at all.)
# Contract for every probe below: a count/value on stdout and exit 0, or the REASON on
# stderr and exit 3. Never silent, never suppressed.
children_of() {   # children_of <pid> -> number of live children of <pid>
  python3 - "$1" <<'PY'
import os, sys
pid = sys.argv[1]

def _ppid(p):
    with open("/proc/%s/stat" % p) as fh:
        raw = fh.read()
    return raw[raw.rindex(")") + 1:].split()[1]

try:
    kids = set()
    tasks = "/proc/%s/task" % pid
    for tid in os.listdir(tasks):
        with open(os.path.join(tasks, tid, "children")) as fh:
            kids.update(fh.read().split())
except OSError as exc:
    sys.stderr.write("children_of: cannot probe pid %s via /proc: %s\n" % (pid, exc))
    raise SystemExit(3)

# EXCLUDE THE PROBE'S OWN LINEAGE. Measuring a process tree from inside it adds a branch
# to the thing measured: this python process, and the command-substitution subshell that
# forked it, ARE children of the target while the probe runs. Driven 2026-08-26: without
# this a childless script probes as 1, so the assertion could never be GREEN -- the exact
# mirror of the defect being repaired. `pgrep -P $$` had the same flaw; it was invisible
# only because pgrep never ran.
try:
    cur = str(os.getpid())
    while cur != "1":
        par = _ppid(cur)
        kids.discard(cur)
        if par == pid:
            break
        cur = par
except (OSError, ValueError, IndexError):
    pass          # the chain vanished mid-walk; the count printed is then a ceiling
print(len(kids))
PY
}
ppid_of() {       # ppid_of <pid> -> the parent pid of <pid>
  python3 - "$1" <<'PY'
import sys
pid = sys.argv[1]
try:
    with open("/proc/%s/stat" % pid) as fh:
        raw = fh.read()
    # comm may contain spaces and parens, so PPID is the 2nd field AFTER the final ')'
    print(raw[raw.rindex(")") + 1:].split()[1])
except (OSError, ValueError, IndexError) as exc:
    sys.stderr.write("ppid_of: cannot probe pid %s via /proc: %s\n" % (pid, exc))
    raise SystemExit(3)
PY
}
pids_matching() { # pids_matching <substring> -> pids whose cmdline contains <substring>
  python3 - "$1" <<'PY'
import os, sys
pat = sys.argv[1]
try:
    entries = [p for p in os.listdir("/proc") if p.isdigit()]
except OSError as exc:
    sys.stderr.write("pids_matching: cannot read /proc: %s\n" % exc)
    raise SystemExit(3)

# NEVER MATCH SELF OR AN ANCESTOR. A cmdline search matches any process that merely
# MENTIONS the pattern -- including this script, the shell that launched it, and any
# editor or heredoc carrying the text on its command line. Driven 2026-08-26: an earlier
# build of the reaper below matched the invoking shell and KILLED IT (exit 144). The old
# `pkill -f` form had exactly this hazard and was saved only by pkill being absent.
# A reaper must never kill the tree it is running inside.
def _ppid(q):
    with open("/proc/%s/stat" % q) as fh:
        raw = fh.read()
    return raw[raw.rindex(")") + 1:].split()[1]

mine = set()
cur = str(os.getpid())
try:
    while cur and cur != "0":
        mine.add(cur)
        if cur == "1":
            break
        cur = _ppid(cur)
except (OSError, ValueError, IndexError):
    pass          # a partial chain still excludes everything walked so far
me = str(os.getpid())
for p in entries:
    try:
        with open("/proc/%s/cmdline" % p, "rb") as fh:
            cmd = fh.read().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        continue      # exited between listdir and open - a race, not a probe failure
    if pat in cmd and p not in mine:
        print(p)
PY
}
count_in() {      # count_in <literal> <file> -> occurrences of <literal> in <file>
  local rc
  if [ ! -f "$2" ]; then echo "count_in: no such file: $2" >&2; return 3; fi
  # -c DIRECTLY ON A FILE is the clean form; a composite (... | grep -c .) loses NUL-bearing
  # lines silently. `command grep` bypasses the seat's ugrep wrapper; NEVER backslash-grep.
  command grep -c -F -- "$1" "$2"; rc=$?
  # grep -c exits 1 when the count is zero and STILL prints 0 - a real count, not a failure.
  case "$rc" in 0|1) return 0 ;; *) echo "count_in: grep exit $rc on $2" >&2; return 3 ;; esac
}
# A check whose PROBE can fail has THREE outcomes, not two: PASS, FAIL, and
# PROBE UNAVAILABLE - which is reported as a FAIL, because a check that did not run is
# not a check that passed. DECLINED (loud) and SKIPPED (silent) are both distinct from a
# true negative, and neither is a green.
tprobe() {        # tprobe <label> <expected> <probe-command> [args...]
  local label="$1" want="$2"; shift 2
  local got rc
  got="$("$@")"; rc=$?
  if [ "$rc" -ne 0 ]; then
    no "$label - PROBE UNAVAILABLE ($1 exit $rc): this check DID NOT RUN"
    return
  fi
  t "$label" "$(printf '%s' "$got" | tr -d ' ')" "$want"
}
kill_matching() { # best-effort reaper; pkill is ABSENT on this host (and is a shell
                  # function in an interactive seat, which a script never inherits)
  local p
  for p in $(pids_matching "$1" || true); do
    [ -e "/proc/$p" ] || continue
    kill "$p" || echo "  note: could not kill $p" >&2
  done
}
# <<< S71-PROBES-END

E="$W/estate"; mkdir -p "$E"; ( cd "$E" && git init -q ) >/dev/null 2>&1; : > "$E/README.md"
python3 "$EST" establish --root "$E" >/dev/null 2>&1

echo "── the refresher itself"
# establish ALREADY seeded this estate in the background, so a second call inside the
# 60s window correctly debounces and writes nothing. Clear the layer first, so what is
# asserted below is a refresh this fixture actually caused.
waitfor "$E/pulse/pulse.json" || true
rm -rf "$E/pulse"
NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$E"; t "estate-pulse exits 0" "$?" "0"
t "pulse.json landed" "$([ -f "$E/pulse/pulse.json" ] && echo y || echo n)" "y"
for i in eval compile swarm doctor; do
  t "pulse/$i.txt landed" "$([ -f "$E/pulse/$i.txt" ] && echo y || echo n)" "y"
done
has "each reading declares itself derived and disposable" "derived, disposable" "$E/pulse/eval.txt"
has "the doctor reading discloses that nothing was skipped" "Nothing is skipped or cached here" "$E/pulse/doctor.txt"
t "pulse.json keys are stable" \
  "$(python3 -c "import json,sys;print(list(json.load(open(sys.argv[1])))==sorted(json.load(open(sys.argv[1]))))" "$E/pulse/pulse.json")" "True"
t "every instrument reported an exit code" \
  "$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))['instruments']
print(all('exit' in v and 'verdict' in v and 'secs' in v for v in d.values()) and len(d)==4)" "$E/pulse/pulse.json")" "True"

echo "── THE LEDGER IS NOT THE PULSE"
# Was: grep -c '\[pulse\]' ... 2>/dev/null || true — a missing COORD.md printed nothing and
# `|| true` swallowed the exit 2, so the check could not say WHY it had no count.
tprobe "estate-pulse never writes COORD" "0" count_in "[pulse]" "$E/COORD.md"
COORDCK="$(cksum < "$E/COORD.md")"

echo "── debounce: a swarm landing five lanes produces ONE refresh"
B="$(cksum < "$E/pulse/pulse.json")"
for _ in 1 2 3 4 5; do NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$E"; done
t "five rapid fires leave the reading untouched" "$(cksum < "$E/pulse/pulse.json")" "$B"

echo "── the caller never waits"
S=$(python3 -c "import time;print(int(time.time()*1000))")
( NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$E" >/dev/null 2>&1 & ) 2>/dev/null
D=$(( $(python3 -c "import time;print(int(time.time()*1000))") - S ))
if [ "$D" -lt 900 ]; then ok "detached call returned in ${D}ms (<900ms)"
else no "detached call took ${D}ms — the caller is waiting on the pulse"; fi

echo "── the detached refresh actually completes"
rm -rf "$E/pulse"
( NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$E" >/dev/null 2>&1 & ) 2>/dev/null
if waitfor "$E/pulse/pulse.json"; then ok "a detached refresh really lands its files"
else no "detached refresh never produced pulse.json"; fi

echo "── seeding at /notrest, per the owner's order"
E2="$W/seed"; mkdir -p "$E2"; : > "$E2/README.md"
python3 "$EST" establish --root "$E2" > "$W/o" 2>&1
has "establish says the layer is seeding" "PULSE" "$W/o"
if waitfor "$E2/pulse/pulse.json"; then ok "establish seeds the layer in the background"
else no "establish did not seed the pulse layer"; fi
python3 "$EST" continuation --root "$E2" > "$W/o2" 2>&1
has "continuation says where the readings land" "pulse/pulse.json" "$W/o2"

echo "── the reader: session-start echoes one line, and only with the file"
cp "$HOOKS"/*.sh "$E/"
( cd "$E" && bash ./session-start.sh ) > "$W/ss" 2>&1
has "session-start echoes the pulse verdicts" "Pulse (machine-written" "$W/ss"
has "…with the refresh age" "refreshed" "$W/ss"
has "…and says the ledgers remain the record" "ledgers remain the record" "$W/ss"
N="$W/nopulse"; mkdir -p "$N"; ( cd "$N" && git init -q ) >/dev/null 2>&1
python3 "$EST" establish --root "$N" >/dev/null 2>&1; rm -rf "$N/pulse"
cp "$HOOKS"/*.sh "$N/"
( cd "$N" && bash ./session-start.sh ) > "$W/ss2" 2>&1
if grep -q "Pulse (machine-written" "$W/ss2"; then no "session-start invented a pulse line with no file"
else ok "session-start stays silent without a pulse file"; fi
t "COORD untouched by every pulse in this fixture" "$(cksum < "$E/COORD.md")" "$COORDCK"

echo "── restraint: a root with nothing to read is silent, not noisy"
BARE="$W/bare"; mkdir -p "$BARE"
NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$BARE" > "$W/b" 2>&1; t "bare root exits 0" "$?" "0"
t "…and prints nothing at all" "$(wc -c < "$W/b" | tr -d ' ')" "0"
NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "/nonexistent/nowhere" >/dev/null 2>&1
t "a missing root is silent too" "$?" "0"

echo "── the heartbeat marker: WHEN it ran and WHAT fired it"
rm -rf "$E/pulse"
NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$E" lane-stop
t "trigger recorded: lane-stop" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['trigger'])" "$E/pulse/pulse.json")" "lane-stop"
rm -rf "$E/pulse"; NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$E" prompt-stale
t "trigger recorded: prompt-stale" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['trigger'])" "$E/pulse/pulse.json")" "prompt-stale"
rm -rf "$E/pulse"; NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$E"
t "trigger defaults to manual" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['trigger'])" "$E/pulse/pulse.json")" "manual"
( cd "$E" && bash ./session-start.sh ) > "$W/ss3" 2>&1
has "the reader shows WHAT fired the pulse, not just when" "refreshed" "$W/ss3"
has "…naming the trigger" "by manual" "$W/ss3"

echo "── self-restart: the pulse never needs a manual kick while anyone works"
cp "$HOOKS"/*.sh "$E/"
# FRESH pulse → the prompt hook must not fire a refresh
FRESHCK="$(cksum < "$E/pulse/pulse.json")"
( cd "$E" && bash "$HOOKS/coord-nudge.sh" ) >/dev/null 2>&1; sleep 2
t "a fresh pulse is left alone by the prompt hook" "$(cksum < "$E/pulse/pulse.json")" "$FRESHCK"
# STALE pulse (backdated past 30m) → exactly one detached refresh
python3 -c "
import os,sys,time
p=sys.argv[1]; old=time.time()-3600
os.utime(p,(old,old))" "$E/pulse/pulse.json"
( cd "$E" && bash "$HOOKS/coord-nudge.sh" ) >/dev/null 2>&1
for _ in $(seq 1 40); do
  NEW="$(python3 -c "import os,sys,time;print(int(time.time()-os.path.getmtime(sys.argv[1])))" "$E/pulse/pulse.json")"
  [ "$NEW" -lt 120 ] && break; sleep 0.25
done
t "a stale pulse is kicked back to life by the next prompt" \
  "$(python3 -c "import os,sys,time;print('fresh' if time.time()-os.path.getmtime(sys.argv[1])<120 else 'stale')" "$E/pulse/pulse.json")" "fresh"
t "…and the kick names itself in the marker" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['trigger'])" "$E/pulse/pulse.json")" "prompt-stale"
# a second prompt inside the debounce window must NOT refresh again
KICKCK="$(cksum < "$E/pulse/pulse.json")"
( cd "$E" && bash "$HOOKS/coord-nudge.sh" ) >/dev/null 2>&1; sleep 2
t "a double prompt still produces ONE refresh (debounce is the floor)" \
  "$(cksum < "$E/pulse/pulse.json")" "$KICKCK"
# no estate → the prompt hook stays silent and writes nothing
BARE2="$W/bare2"; mkdir -p "$BARE2"; cp "$HOOKS"/*.sh "$BARE2/"
( cd "$BARE2" && bash "$HOOKS/coord-nudge.sh" ) > "$W/bn" 2>&1
t "no estate → the prompt hook is silent" "$(wc -c < "$W/bn" | tr -d ' ')" "0"

echo "── the watcher surfaces alerts on the next prompt, and only then"
( cd "$E" && bash "$HOOKS/coord-nudge.sh" ) > "$W/noalert" 2>&1
if grep -q "SWARM WATCH" "$W/noalert"; then no "no alert file → no alert line"
else ok "no alert file → no alert line"; fi
printf '# live\n\nALERT STALL lane-x — no transcript growth for 12m and no receipt\n' \
  > "$E/pulse/swarm-live.txt"
( cd "$E" && bash "$HOOKS/coord-nudge.sh" ) > "$W/alert" 2>&1
has "an alert reaches the seat on the next prompt" "SWARM WATCH" "$W/alert"
has "…and carries the finding itself" "ALERT STALL lane-x" "$W/alert"

echo "── TRAP LAW: the spawner's process tree must be clean"
# Files landing is not enough. A daemon still parented to its spawner holds that agent in
# mid-turn state, suppresses its completion notification, and makes a working lane look
# dead — that is exactly how the lane building this got killed today. So assert the
# PROCESS TREE, not just the filesystem.
rm -rf "$E/pulse"
bash "$HOOKS/estate-pulse.sh" "$E" lane-stop        # daemonizing path, not foreground
sleep 1
tprobe "a spawned refresher is NOT a child of its spawner" "0" children_of $$
# THE PROOF IS THE PPID: "backgrounded" is not "detached". A survivor must be reparented
# to init (ppid 1), never held by this fixture or any ancestor of it.
# The old form collapsed THREE outcomes into one PASS: "reparented", "no survivors", and
# "the probe never ran". They are now three different sentences.
if ! SURV="$(pids_matching "estate-pulse.sh $E")"; then
  no "surviving refreshers are reparented to init - PROBE UNAVAILABLE (pids_matching): this check DID NOT RUN"
elif [ -z "$SURV" ]; then
  ok "no refresher survived the spawn window (nothing left to reparent)"
else
  BAD=""; PPIDS=""
  for q in $SURV; do
    if ! pp="$(ppid_of "$q")"; then
      no "surviving refresher $q - PROBE UNAVAILABLE (ppid_of exit 3): this check DID NOT RUN"
      BAD="probe"; break
    fi
    PPIDS="$PPIDS$pp,"
    [ "$pp" = "1" ] || BAD="$BAD $q(ppid=$pp)"
  done
  if [ -z "$BAD" ]; then ok "every surviving refresher is reparented to init (ppids=$PPIDS)"
  elif [ "$BAD" != "probe" ]; then no "a refresher survived still parented:$BAD - detach did not reparent"
  fi
fi
for _ in $(seq 1 40); do [ -f "$E/pulse/pulse.json" ] && break; sleep 0.25; done
t "…and it still did its work after reparenting" \
  "$([ -f "$E/pulse/pulse.json" ] && echo y || echo n)" "y"
( cd "$E" && python3 "$SWARM" watch --root "$E" --once ) > "$W/watch-once.log" 2>&1
tprobe "watch --once leaves no children behind" "0" children_of $$
( cd "$E" && python3 "$SWARM" watch --root "$E" ) > "$W/watchd.log" 2>&1; sleep 1
if ! WPS="$(pids_matching "swarm.py watch --root $E")"; then
  no "a daemonized watcher is reparented to init - PROBE UNAVAILABLE (pids_matching): this check DID NOT RUN"
elif [ -z "$WPS" ]; then
  ok "the watcher self-terminated (no corpses to watch)"
else
  for wp in $WPS; do
    tprobe "a daemonized watcher (pid $wp) is reparented to init" "1" ppid_of "$wp"
  done
  kill_matching "swarm.py watch --root $E"
fi
tprobe "…and it is not a child of this fixture" "0" children_of $$

echo "── the watcher: history is not a running lane"
LD="$W/fakeproj"; mkdir -p "$LD"
SUB="$HOME/.claude/projects/-${LD#/}"; SUB="${SUB//\//-}"
t "watch on a root with no transcript dir is silent, not noisy" \
  "$(python3 "$SWARM" watch --root "$LD" --once >/dev/null 2>&1; echo $?)" "0"

echo "── compile input-stamp: skip what has not moved, and SAY so"
CS="$W/stamped"; mkdir -p "$CS"; ( cd "$CS" && git init -q ) >/dev/null 2>&1; : > "$CS/README.md"
python3 "$EST" establish --root "$CS" >/dev/null 2>&1
for _ in $(seq 1 40); do [ -f "$CS/pulse/pulse.json" ] && break; sleep 0.25; done
rm -rf "$CS/pulse"
NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$CS" manual
V1="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['instruments']['compile']['verdict'])" "$CS/pulse/pulse.json")"
case "$V1" in *SKIPPED*) no "the FIRST scan must be real, not skipped" ;; *) ok "the first compile scan really runs" ;; esac
rm -f "$CS/pulse/pulse.json"
NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$CS" manual
has "an unchanged estate SKIPS the 8s scan" "SKIPPED" "$CS/pulse/compile.txt"
has "…naming the stamp it matched" "inputs unchanged since stamp" "$CS/pulse/compile.txt"
has "…and disclosing the verdict is the PRIOR one" "not re-measured on this pulse" "$CS/pulse/compile.txt"
t "…and pulse.json marks it skipped" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['instruments']['compile']['skipped'])" "$CS/pulse/pulse.json")" "True"
echo "- [2026-08-06 01:00Z] [x] touched -> landed | evidence: t" >> "$CS/COORD.md"
rm -f "$CS/pulse/pulse.json"
NR_PULSE_DAEMON=1 bash "$HOOKS/estate-pulse.sh" "$CS" manual
t "a touched ledger forces a REAL scan again" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['instruments']['compile']['skipped'])" "$CS/pulse/pulse.json")" "False"

echo
echo "pulse-layer-fixture: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
