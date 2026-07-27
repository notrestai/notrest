#!/bin/bash
# pulse-fixture.sh — the contract test for pulse.sh (the estate heartbeat).
#
# Self-relative: runs from any cwd, writes only inside its own mktemp dir, never touches
# a real estate and never reaches the network. Every instrument is a STUB whose exit code
# and output the fixture chooses, so the assertions are about pulse's own logic — the
# grading rule, the line format, the single append — and not about whatever this laptop's
# doctor happens to report today.
#
# Usage: bash <doctor-skill>/scripts/pulse-fixture.sh   (exit 0 = every assertion held)
set -u
PULSE_SRC="$(cd "$(dirname "$0")" && pwd)/pulse.sh"
W="$(mktemp -d)"
cleanup(){ rm -rf "$W"; return 0; }
trap cleanup EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
# -F throughout: the strings asserted here contain [brackets], which a basic-regex grep
# would read as character classes and match against nothing.
hasnt(){ if printf '%s' "$2" | grep -F -q -- "$3"; then no "$1 — found [$3]"; else ok "$1"; fi; }
inc(){ if printf '%s' "$2" | grep -F -q -- "$3"; then ok "$1"; else no "$1 — [$3] not in output"; fi; }

# ── a fake skills tree: pulse finds its instruments at ../../<skill>/scripts/ ────────
SK="$W/skills"
for d in doctor eval watch compile spend graph; do mkdir -p "$SK/$d/scripts"; done
cp "$PULSE_SRC" "$SK/doctor/scripts/pulse.sh"
PULSE="$SK/doctor/scripts/pulse.sh"

# Stubs read their exit code and payload from the environment, so a single tree serves
# every scenario and no assertion depends on rewriting a file mid-run. Each one also
# LOGS ITS OWN CALL to $FIX_CALLS — that counter is what makes "the freshness door ran
# no instruments" a measurement instead of a hope. It lives in $W, outside every fake
# estate, so the read-only assertion below still hashes an untouched tree.
export FIX_CALLS="$W/calls.log"
: > "$FIX_CALLS"
calls_reset(){ : > "$FIX_CALLS"; }
calls_n(){ local n; n="$(wc -l < "$FIX_CALLS" 2>/dev/null | tr -d ' ')"; [ -n "$n" ] || n=0; echo "$n"; }

cat > "$SK/doctor/scripts/doctor.py" <<'PY'
import os, sys
open(os.environ.get("FIX_CALLS", "/dev/null"), "a").write("doctor\n")
print("doctor: OK — 10 checks · 10 pass, 0 warn, 0 fail, 0 skip")
sys.exit(int(os.environ.get("FIX_DOCTOR_RC", "0")))
PY
cat > "$SK/eval/scripts/eval.py" <<'PY'
import os, sys
open(os.environ.get("FIX_CALLS", "/dev/null"), "a").write("eval\n")
print("SUMMARY PASS — 28 skills, 12 checks, 0 fail, 0 warn, 0.10s, 0 model tokens")
sys.exit(int(os.environ.get("FIX_EVAL_RC", "0")))
PY
cat > "$SK/watch/scripts/watch.py" <<'PY'
import os, sys
open(os.environ.get("FIX_CALLS", "/dev/null"), "a").write("watch\n")
if os.environ.get("FIX_WATCH_GARBAGE"):
    print("watch: no watchlist — run /watch add first")
else:
    print("watch: %s due of 2 rows (0 never-due: -)" % os.environ.get("FIX_WATCH_N", "2"))
sys.exit(int(os.environ.get("FIX_WATCH_RC", "3")))
PY
cat > "$SK/compile/scripts/compile.py" <<'PY'
import os, sys
open(os.environ.get("FIX_CALLS", "/dev/null"), "a").write("compile\n")
n = os.environ.get("FIX_COMPILE_N", "4")
print("[compile] %s ripe candidate(s) not yet ruled on — /compile <slug> reconstructs it." % n)
sys.exit(int(os.environ.get("FIX_COMPILE_RC", "3")))
PY
cat > "$SK/spend/scripts/spend.py" <<'PY'
import os, sys
open(os.environ.get("FIX_CALLS", "/dev/null"), "a").write("spend\n")
print("routing: %s — policy 2026-07-15: opus-only offload (41 checked, 0 violations)"
      % os.environ.get("FIX_SPEND_WORD", "CLEAN"))
sys.exit(int(os.environ.get("FIX_SPEND_RC", "0")))
PY
cat > "$SK/graph/scripts/graph.py" <<'PY'
import os, sys
verb = sys.argv[1] if len(sys.argv) > 1 else "?"
open(os.environ.get("FIX_CALLS", "/dev/null"), "a").write("graph-%s\n" % verb)
if len(sys.argv) > 1 and sys.argv[1] == "river":
    print("/tmp/river.html: 2 records · 1 channels · 1 rocks · mode=findings+coord")
    sys.exit(int(os.environ.get("FIX_RIVER_RC", "0")))
print("graph: scanned")
sys.exit(int(os.environ.get("FIX_SCAN_RC", "0")))
PY

# ── a fake estate ───────────────────────────────────────────────────────────────────
newroot(){  # newroot <name> — a root with a COORD.md, returns its path on stdout
    local r="$W/$1"
    mkdir -p "$r"
    printf '# COORD.md — session coordination ledger (active volume)\n\n- [2026-07-01 00:00Z] [seed] existing line\n' > "$r/COORD.md"
    echo "$r"
}
# `grep -c` already prints 0 on no-match (and exits 1), so a `|| echo 0` fallback would
# emit a SECOND zero and every count assertion would compare against "0\n0".
count(){ local n; n="$(grep -F -c -- "$2" "$1" 2>/dev/null)"; [ -n "$n" ] || n=0; echo "$n"; }
pulse_lines(){ count "$1/COORD.md" "[pulse] estate pulse ->"; }
occurrences(){ count "$1/COORD.md" "$2"; }

# ── seeding the ledger for the --if-stale door ──────────────────────────────────────
# `ago <minutes>` is computed in python3, not `date`: BSD wants -v-30M and GNU wants
# -d '30 minutes ago', and this fixture has to run on either. UTC, like the ledger.
ago(){ python3 -c 'import sys, datetime; print((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=float(sys.argv[1]))).strftime("%Y-%m-%d %H:%MZ"))' "$1"; }
seed_pulse(){  # seed_pulse <root> <stamp> — one real-shaped pulse line, already banked
    printf '%s\n' "- [$2] [pulse] estate pulse -> doctor=0 eval=0 watch-due=1 compile=none spend=CLEAN river=coord-only | evidence: pulse.sh" >> "$1/COORD.md"
}

echo "── green path ──────────────────────────────────────────────────────────────"
R="$(newroot green)"
OUT="$(bash "$PULSE" --root "$R" 2>&1)"; RC=$?
t "green estate exits 0" "$RC" "0"
inc "reports GREEN" "$OUT" "pulse: GREEN"
LINE="$(printf '%s\n' "$OUT" | grep '\[pulse\]')"
inc "line has the pulse tag"      "$LINE" "[pulse] estate pulse ->"
inc "line carries doctor rc"      "$LINE" "doctor=0"
inc "line carries eval rc"        "$LINE" "eval=0"
inc "line carries the due COUNT"  "$LINE" "watch-due=2"
inc "line carries compile=ripe"   "$LINE" "compile=ripe"
inc "line carries the spend word" "$LINE" "spend=CLEAN"
inc "line carries the river mode" "$LINE" "river=findings+coord"
inc "line carries the evidence"   "$LINE" "| evidence: pulse.sh"
case "$LINE" in
    "- ["*"Z] [pulse] estate pulse -> "*) ok "line is a dated ledger entry" ;;
    *) no "line is a dated ledger entry — got [$LINE]" ;;
esac
t "COORD gained exactly one pulse line" "$(pulse_lines "$R")" "1"

echo "── the signal exits are workload, not alarm ────────────────────────────────"
# watch.py due exit 3 (something is due) and compile.py report exit 3 (ripe candidates)
# are documented signals. If they alarmed, this heartbeat would be red on every healthy
# estate — the defect this grading rule exists to prevent.
t "watch=3 + compile=3 alone stay green" "$RC" "0"
R="$(newroot nothing_due)"
FIX_WATCH_RC=0 FIX_WATCH_N=0 FIX_COMPILE_RC=0 FIX_COMPILE_N=0 \
    bash "$PULSE" --root "$R" >"$W/o" 2>&1
t "nothing due, nothing ripe still green" "$?" "0"
inc "compile reads none" "$(cat "$W/o")" "compile=none"
inc "watch-due reads 0"  "$(cat "$W/o")" "watch-due=0"

echo "── red path ────────────────────────────────────────────────────────────────"
R="$(newroot red)"
OUT="$(FIX_DOCTOR_RC=5 bash "$PULSE" --root "$R" 2>&1)"; RC=$?
t "doctor exit 5 makes pulse exit 1" "$RC" "1"
inc "names the offender"     "$OUT" "doctor=5"
inc "reports ATTENTION"      "$OUT" "pulse: ATTENTION"
hasnt "does not claim GREEN" "$OUT" "pulse: GREEN"
t "a red pulse still banks its line" "$(pulse_lines "$R")" "1"

R="$(newroot red_eval)"
FIX_EVAL_RC=6 bash "$PULSE" --root "$R" >/dev/null 2>&1
t "eval failure makes pulse exit 1" "$?" "1"
R="$(newroot red_spend)"
OUT="$(FIX_SPEND_RC=4 FIX_SPEND_WORD=VIOLATION bash "$PULSE" --root "$R" 2>&1)"
t "a spend routing violation is red" "$?" "1"
inc "the verdict word travels" "$OUT" "spend=VIOLATION"

echo "── --strict restores the literal reading ───────────────────────────────────"
R="$(newroot strict)"
bash "$PULSE" --root "$R" --strict >/dev/null 2>&1
t "strict: any non-zero exits 1" "$?" "1"
R="$(newroot strict_clean)"
FIX_WATCH_RC=0 FIX_COMPILE_RC=0 bash "$PULSE" --root "$R" --strict >/dev/null 2>&1
t "strict: all-zero still exits 0" "$?" "0"

echo "── the append is exactly once, and idempotent ──────────────────────────────"
R="$(newroot once)"
L1="$(bash "$PULSE" --root "$R" 2>&1 | grep '\[pulse\]')"
L2="$(bash "$PULSE" --root "$R" 2>&1 | grep '\[pulse\]')"
t "the first line appears exactly once" "$(occurrences "$R" "$L1")" "1"
t "the second line appears exactly once" "$(occurrences "$R" "$L2")" "1"
# Minute-granular timestamps: two runs in the same minute over an unchanged estate
# produce the SAME line and must dedup to one; across a minute boundary they differ and
# both belong. Asserting the conditional keeps this test honest instead of flaky.
if [ "$L1" = "$L2" ]; then
    t "identical re-run deduped" "$(pulse_lines "$R")" "1"
else
    t "distinct minute appended" "$(pulse_lines "$R")" "2"
fi
inc "seed line survived" "$(cat "$R/COORD.md")" "[seed] existing line"

echo "── --if-stale: the freshness door ──────────────────────────────────────────"
# The in-session rhythm. A skill calls pulse with a WINDOW instead of a schedule, and the
# door's whole value is what it does NOT do — so every case here counts stub invocations
# ($FIX_CALLS) rather than trusting the banner. A full sweep is exactly seven calls:
# doctor · eval · watch · compile · spend · graph river · graph scan.
R="$(newroot fresh)"
seed_pulse "$R" "$(ago 30)"
calls_reset
OUT="$(bash "$PULSE" --root "$R" --if-stale 6 2>&1)"; RC=$?
t "a 30-minute-old pulse exits 0" "$RC" "0"
t "and NOT ONE instrument ran" "$(calls_n)" "0"
inc "says fresh, with the age"      "$OUT" "pulse: fresh ("
inc "carries the age unit"          "$OUT" "m old,"
inc "carries the last verdict"      "$OUT" "spend=CLEAN"
inc "and the last river mode"       "$OUT" "river=coord-only"
hasnt "summarises, not echoes (no evidence tail)" "$OUT" "evidence: pulse.sh"
hasnt "never claims GREEN — nothing was measured" "$OUT" "pulse: GREEN"
t "the door banks nothing" "$(pulse_lines "$R")" "1"

# Newest by TIMESTAMP, not by position: a stale line appended after a young one must not
# reopen the door. (COORD is chronological in practice; a hand-edit needn't be.)
R="$(newroot fresh_unordered)"
seed_pulse "$R" "$(ago 900)"
seed_pulse "$R" "$(ago 20)"
seed_pulse "$R" "$(ago 800)"
calls_reset
OUT="$(bash "$PULSE" --root "$R" --if-stale 6 2>&1)"
t "the newest stamp wins, whatever the order" "$(calls_n)" "0"
inc "and it is the young one" "$OUT" "pulse: fresh (20m old"

R="$(newroot stale)"
seed_pulse "$R" "$(ago 600)"   # ten hours — well outside a six-hour window
calls_reset
OUT="$(bash "$PULSE" --root "$R" --if-stale 6 2>&1)"; RC=$?
t "a ten-hour-old pulse runs the full sweep" "$RC" "0"
t "every instrument ran" "$(calls_n)" "7"
inc "reports GREEN"      "$OUT" "pulse: GREEN"
hasnt "and never claims fresh" "$OUT" "pulse: fresh"
t "the sweep banks its own line" "$(pulse_lines "$R")" "2"

# Boundary: the window is measured, not rounded. 90 minutes is inside 2h and outside 1h.
R="$(newroot window_edges)"
seed_pulse "$R" "$(ago 90)"
calls_reset
bash "$PULSE" --root "$R" --if-stale 2 >/dev/null 2>&1
t "90 minutes is fresh inside a 2h window" "$(calls_n)" "0"
calls_reset
bash "$PULSE" --root "$R" --if-stale 1 >/dev/null 2>&1
t "the same line is stale in a 1h window" "$(calls_n)" "7"

echo "── the door fails OPEN — toward checking, never toward skipping ────────────"
R="$(newroot badstamp)"
printf '%s\n' "- [not-a-date] [pulse] estate pulse -> doctor=0 | evidence: pulse.sh" >> "$R/COORD.md"
calls_reset
OUT="$(bash "$PULSE" --root "$R" --if-stale 6 2>&1)"; RC=$?
t "an unparseable stamp runs the pulse" "$(calls_n)" "7"
t "and still exits cleanly" "$RC" "0"
hasnt "no traceback from the door" "$OUT" "Traceback"

# A stamp from the future is a skewed clock or a hand-edit — arithmetically "young", and
# exactly the case where trusting the number would silence the heartbeat indefinitely.
R="$(newroot futurestamp)"
seed_pulse "$R" "$(ago -600)"
calls_reset
bash "$PULSE" --root "$R" --if-stale 6 >/dev/null 2>&1
t "a stamp from the future runs the pulse" "$(calls_n)" "7"

R="$(newroot nopulseyet)"
calls_reset
bash "$PULSE" --root "$R" --if-stale 6 >/dev/null 2>&1
t "a COORD that has never been pulsed runs it" "$(calls_n)" "7"

R="$W/nocoord_stale"; mkdir -p "$R"
calls_reset
OUT="$(bash "$PULSE" --root "$R" --if-stale 6 2>&1)"; RC=$?
t "no COORD.md at all runs the pulse" "$(calls_n)" "7"
t "and exits 0 with nowhere to bank" "$RC" "0"

R="$(newroot window_zero)"
seed_pulse "$R" "$(ago 1)"
calls_reset
OUT="$(bash "$PULSE" --root "$R" --if-stale 0 2>&1)"
t "--if-stale 0 always runs, however young the line" "$(calls_n)" "7"
hasnt "and never claims fresh" "$OUT" "pulse: fresh"
calls_reset
bash "$PULSE" --root "$R" --if-stale banana >/dev/null 2>&1
t "a non-numeric window runs the pulse" "$(calls_n)" "7"

# No flag = no door: the scheduled path and every existing caller are untouched.
R="$(newroot nodoor)"
seed_pulse "$R" "$(ago 1)"
calls_reset
bash "$PULSE" --root "$R" >/dev/null 2>&1
t "without --if-stale a minute-old pulse still runs" "$(calls_n)" "7"

echo "── pulse writes NOTHING but that one line ──────────────────────────────────"
R="$(newroot readonly)"
mkdir -p "$R/watch"; printf 'untouched\n' > "$R/watch/watchlist.md"
printf 'untouched\n' > "$R/STATE.md"
BEFORE="$(find "$R" -type f ! -name COORD.md | sort | xargs shasum 2>/dev/null | shasum)"
bash "$PULSE" --root "$R" >/dev/null 2>&1
AFTER="$(find "$R" -type f ! -name COORD.md | sort | xargs shasum 2>/dev/null | shasum)"
t "estate untouched apart from COORD.md" "$AFTER" "$BEFORE"

echo "── a malformed estate is tolerated, never crashed on ───────────────────────"
R="$W/nocoord"; mkdir -p "$R"
OUT="$(bash "$PULSE" --root "$R" 2>&1)"; RC=$?
t "no COORD.md still exits cleanly" "$RC" "0"
inc "says the append was skipped" "$OUT" "no COORD.md"
hasnt "no python traceback" "$OUT" "Traceback"

R="$(newroot garbage)"
OUT="$(FIX_WATCH_GARBAGE=1 FIX_WATCH_RC=2 bash "$PULSE" --root "$R" 2>&1)"; RC=$?
inc "an unparseable due count reads -" "$OUT" "watch-due=-"
t "a watchlist-less estate is not an alarm" "$RC" "0"
hasnt "still no traceback" "$OUT" "Traceback"

echo "── missing instruments ─────────────────────────────────────────────────────"
mv "$SK/graph/scripts/graph.py" "$W/graph.py.bak"
R="$(newroot nograph)"
OUT="$(bash "$PULSE" --root "$R" 2>&1)"; RC=$?
t "a missing graph skill is non-fatal" "$RC" "0"
inc "river reads -" "$OUT" "river=-"
mv "$W/graph.py.bak" "$SK/graph/scripts/graph.py"

mv "$SK/doctor/scripts/doctor.py" "$W/doctor.py.bak"
R="$(newroot nodoctor)"
OUT="$(bash "$PULSE" --root "$R" 2>&1)"; RC=$?
t "a missing CORE instrument is red" "$RC" "1"
hasnt "no traceback on a missing core" "$OUT" "Traceback"
t "and it still banks a line" "$(pulse_lines "$R")" "1"
mv "$W/doctor.py.bak" "$SK/doctor/scripts/doctor.py"

echo "── argument handling ───────────────────────────────────────────────────────"
R="$(newroot nowrite)"
bash "$PULSE" --root "$R" --no-coord >/dev/null 2>&1
t "--no-coord writes no line" "$(pulse_lines "$R")" "0"
bash "$PULSE" --root "$W/does-not-exist" >/dev/null 2>&1
t "a bad --root exits 2" "$?" "2"

# A value-taking flag with no value used to SPIN: `shift 2` with one argument left fails,
# does not shift, and the while-loop never advances. These two run under a watchdog so a
# reintroduced hang fails the fixture in five seconds instead of wedging the gate forever.
bounded(){  # bounded <seconds> <cmd...> — the exit code, or 124 if it outran the budget
    local secs="$1"; shift
    "$@" >/dev/null 2>&1 &
    local pid=$!
    ( sleep "$secs"; kill -9 "$pid" 2>/dev/null ) >/dev/null 2>&1 &
    local wd=$!
    wait "$pid" 2>/dev/null; local rc=$?
    kill "$wd" 2>/dev/null; wait "$wd" 2>/dev/null
    [ "$rc" -gt 128 ] && rc=124
    echo "$rc"
}
t "--if-stale with no value exits 2, never spins" "$(bounded 5 bash "$PULSE" --if-stale)" "2"
t "--root with no value exits 2, never spins"     "$(bounded 5 bash "$PULSE" --root)" "2"
bash "$PULSE" --frobnicate >/dev/null 2>&1
t "an unknown flag exits 2" "$?" "2"
bash "$PULSE" --help >/dev/null 2>&1
t "--help exits 0" "$?" "0"
bash -n "$PULSE_SRC" 2>/dev/null
t "pulse.sh parses (bash -n)" "$?" "0"
if grep -qE '^[[:space:]]*set -e' "$PULSE_SRC"; then
    no "no set -e (silent-fail-open, per the hook law)"
else
    ok "no set -e (silent-fail-open, per the hook law)"
fi

echo
echo "pulse-fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
