#!/bin/bash
# pulse.sh — the estate heartbeat, in one unattended command.
#
# Runs every read-only instrument the harness owns, banks ONE line to COORD.md, and
# exits 0 (green) or 1 (something wants a human). Nothing else is written: pulse is a
# reader with a single append, so a scheduler can run it every morning without ever
# wondering what it changed.
#
#   bash pulse.sh [--root .] [--strict] [--no-coord]
#
# Silent-fail-open, per the hook law: no `set -e`, no instrument's crash becomes
# pulse's crash, a missing file is reported as `-` rather than a stack trace. The exit
# code is the only alarm, and it is never raised by pulse's own plumbing.
#
# ── the exit rule, and the one judgement in it ──────────────────────────────────────
# Green means "no instrument is asking for a human". Two instruments in this suite use
# a non-zero exit as a SIGNAL rather than a fault, and they are documented that way:
#
#   watch.py due     exit 3 = something is due  ("a hook can branch on this")
#   compile.py report exit 3 = ripe candidates exist
#
# Wiring those straight to the alarm would make the heartbeat permanently red on any
# estate doing its job — 11 ripe candidates and a due watch are the system WORKING —
# and an alarm that is always on is an alarm nobody reads. So pulse splits health from
# workload: doctor / eval / spend / graph decide the colour, and watch-due + compile-ripe
# are carried on the line as DATA (`watch-due=<n>`, `compile=<ripe|none>`) — which is
# exactly the shape the COORD line asks for, while doctor and eval are carried as their
# raw exit codes. Workload is reported; only health alarms.
#
# `--strict` restores the literal reading — ANY non-zero instrument exits 1 — for a
# caller who wants the unnuanced gate.
set -u

ROOT="."
STRICT=0
NO_COORD=0
SELF="$(cd "$(dirname "$0")" && pwd)"
SKILLS="$(cd "$SELF/../.." && pwd)"

usage() {
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --root)     ROOT="${2:-.}"; shift 2 ;;
        --strict)   STRICT=1; shift ;;
        --no-coord) NO_COORD=1; shift ;;
        -h|--help)  usage; exit 0 ;;
        *) echo "pulse: unknown argument $1 (try --help)" >&2; exit 2 ;;
    esac
done

if [ ! -d "$ROOT" ]; then
    echo "pulse: --root $ROOT is not a directory" >&2
    exit 2
fi
ROOT="$(cd "$ROOT" && pwd)"

RED=0          # anything that wants a human
NOTES=""       # human-readable trailer, one clause per unhappy instrument

note() { NOTES="$NOTES${NOTES:+ · }$1"; }

# run_tool <script> <args...> — sets RC and OUT. Never returns non-zero itself, so a
# missing python3 or a scanner that dies mid-write cannot take the heartbeat down.
RC=0
OUT=""
run_tool() {
    local script="$1"; shift
    if [ ! -f "$script" ]; then
        RC=127; OUT="pulse: no such instrument: $script"
        return 0
    fi
    OUT="$(python3 "$script" "$@" 2>&1)"
    RC=$?
    return 0
}

# grade <label> <rc> <green-codes...> — marks red unless rc is in the green set.
# In --strict the green set collapses to {0}.
grade() {
    local label="$1" rc="$2" ok="" c
    shift 2
    if [ "$STRICT" -eq 1 ]; then
        set -- 0
    fi
    for c in "$@"; do
        [ "$rc" = "$c" ] && ok=1
    done
    if [ -z "$ok" ]; then
        RED=1
        note "$label=$rc"
    fi
}

last_match() {  # last_match <sed-expression> — last capture in $OUT, or empty
    printf '%s\n' "$OUT" | sed -n "$1" | tail -1
}

# ── the instruments ─────────────────────────────────────────────────────────────────

run_tool "$SKILLS/doctor/scripts/doctor.py" check --root "$ROOT"
DOCTOR_RC=$RC
DOCTOR_SUM="$(last_match 's/^doctor: \(.*\)$/\1/p')"
grade doctor "$DOCTOR_RC" 0

run_tool "$SKILLS/eval/scripts/eval.py" check --root "$ROOT"
EVAL_RC=$RC
EVAL_SUM="$(last_match 's/^SUMMARY \(.*\)$/\1/p')"
grade eval "$EVAL_RC" 0

# watch: 0 = nothing due · 3 = something due (both healthy) · 2 = no watchlist yet,
# which is a fresh estate, not a fault — reported as `-`, never as an alarm.
run_tool "$SKILLS/watch/scripts/watch.py" due --root "$ROOT"
WATCH_RC=$RC
WATCH_DUE="$(last_match 's/^watch: \([0-9][0-9]*\) due of .*/\1/p')"
[ -n "$WATCH_DUE" ] || WATCH_DUE="-"
grade watch "$WATCH_RC" 0 3 2

# compile: 0 = nothing ripe · 3 = ripe candidates await a ruling (both healthy).
run_tool "$SKILLS/compile/scripts/compile.py" report --root "$ROOT"
COMPILE_RC=$RC
COMPILE_N="$(last_match 's/.*[^0-9]\([0-9][0-9]*\) ripe candidate.*/\1/p')"
if [ "$COMPILE_RC" = "127" ]; then
    COMPILE="-"
elif [ -n "$COMPILE_N" ] && [ "$COMPILE_N" != "0" ]; then
    COMPILE="ripe"
else
    COMPILE="none"
fi
grade compile "$COMPILE_RC" 0 3

# spend: the routing verdict word — CLEAN, or the word the gate actually printed.
run_tool "$SKILLS/spend/scripts/spend.py" report --root "$ROOT"
SPEND_RC=$RC
SPEND="$(last_match 's/^routing: \([A-Za-z][A-Za-z-]*\).*/\1/p')"
[ -n "$SPEND" ] || SPEND="-"
grade spend "$SPEND_RC" 0

# graph: explicitly guarded by existence and non-fatal — a repo with no graph skill
# still has a heartbeat. `river` renders the journey; `scan` refreshes the file graph.
RIVER="-"
if [ -f "$SKILLS/graph/scripts/graph.py" ]; then
    run_tool "$SKILLS/graph/scripts/graph.py" river --root "$ROOT" --no-open
    RIVER_RC=$RC
    RIVER="$(last_match 's/.*mode=\([A-Za-z0-9+_-]*\).*/\1/p')"
    [ -n "$RIVER" ] || RIVER="-"
    grade river "$RIVER_RC" 0

    run_tool "$SKILLS/graph/scripts/graph.py" scan --root "$ROOT"
    grade scan "$RC" 0
fi

# ── the one line ────────────────────────────────────────────────────────────────────

TS="$(date -u '+%Y-%m-%d %H:%MZ')"
LINE="- [$TS] [pulse] estate pulse -> doctor=$DOCTOR_RC eval=$EVAL_RC watch-due=$WATCH_DUE compile=$COMPILE spend=$SPEND river=$RIVER | evidence: pulse.sh"

COORD_NOTE="skipped (--no-coord)"
if [ "$NO_COORD" -eq 0 ]; then
    COORD="$ROOT/COORD.md"
    if [ ! -f "$COORD" ]; then
        COORD_NOTE="skipped (no COORD.md at $COORD)"
    else
        # Appended under an exclusive lock, exactly like the SessionEnd hook: two pulses
        # racing land two lines, never a torn one. An identical line already in the file
        # is a no-op — re-running a pulse is safe, and same-minute reruns of an unchanged
        # estate do not pad the ledger.
        PULSE_LINE="$LINE" PULSE_COORD="$COORD" python3 - <<'PY' 2>/dev/null
import fcntl, os, sys
line = os.environ["PULSE_LINE"] + "\n"
try:
    fd = os.open(os.environ["PULSE_COORD"], os.O_RDWR | os.O_APPEND)
    with os.fdopen(fd, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            text = f.read()
            if line.strip() in text:
                sys.exit(9)
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write(line)
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
except SystemExit:
    raise
except Exception:
    sys.exit(1)
PY
        case $? in
            0) COORD_NOTE="appended to COORD.md" ;;
            9) COORD_NOTE="already present — not duplicated" ;;
            *) COORD_NOTE="FAILED to append (estate left untouched)" ;;
        esac
    fi
fi

# ── the report ──────────────────────────────────────────────────────────────────────

echo "pulse: ${DOCTOR_SUM:-doctor unavailable}"
echo "pulse: ${EVAL_SUM:-eval unavailable}"
echo "$LINE"
echo "pulse: COORD $COORD_NOTE"

if [ "$RED" -eq 0 ]; then
    echo "pulse: GREEN — every instrument healthy (exit 0)"
    exit 0
fi
echo "pulse: ATTENTION — $NOTES (exit 1)"
exit 1
