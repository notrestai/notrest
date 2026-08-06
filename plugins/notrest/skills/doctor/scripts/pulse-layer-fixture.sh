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
cleanup(){ pkill -f "estate-pulse.sh $W" 2>/dev/null; pkill -f "swarm.py watch --root $W" 2>/dev/null; sleep 0.3; rm -rf "$W"; }
trap cleanup EXIT INT TERM
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF -- "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — [$2] not in $3"; fi; }
waitfor(){ for _ in $(seq 1 40); do [ -f "$1" ] && return 0; sleep 0.25; done; return 1; }

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
t "estate-pulse never writes COORD" "$(grep -c '\[pulse\]' "$E/COORD.md" 2>/dev/null || true)" "0"
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
t "a spawned refresher is NOT a child of its spawner" "$(pgrep -P $$ 2>/dev/null | wc -l | tr -d ' ')" "0"
# THE PROOF IS THE PPID: "backgrounded" is not "detached". A survivor must be reparented
# to init (ppid 1), never held by this fixture or any ancestor of it.
PPIDS="$(for q in $(pgrep -f "estate-pulse.sh $E" 2>/dev/null); do ps -o ppid= -p "$q" 2>/dev/null | tr -d ' '; done | sort -u | tr '\n' ',')"
case "${PPIDS:-none}" in
  none|1,|1) ok "any surviving refresher is reparented to init (ppid=${PPIDS:-none})" ;;
  *) no "a refresher survived with ppid=${PPIDS} — detach did not reparent" ;;
esac
for _ in $(seq 1 40); do [ -f "$E/pulse/pulse.json" ] && break; sleep 0.25; done
t "…and it still did its work after reparenting" \
  "$([ -f "$E/pulse/pulse.json" ] && echo y || echo n)" "y"
( cd "$E" && python3 "$SWARM" watch --root "$E" --once >/dev/null 2>&1 )
t "watch --once leaves no children behind" "$(pgrep -P $$ 2>/dev/null | wc -l | tr -d ' ')" "0"
( cd "$E" && python3 "$SWARM" watch --root "$E" >/dev/null 2>&1 ); sleep 1
WP="$(pgrep -f "swarm.py watch --root $E" 2>/dev/null | head -1)"
if [ -n "$WP" ]; then
  t "a daemonized watcher is reparented to init" "$(ps -o ppid= -p "$WP" 2>/dev/null | tr -d ' ')" "1"
  pkill -f "swarm.py watch --root $E" 2>/dev/null
else
  ok "the watcher self-terminated (no corpses to watch)"
fi
t "…and it is not a child of this fixture" "$(pgrep -P $$ 2>/dev/null | wc -l | tr -d ' ')" "0"

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
