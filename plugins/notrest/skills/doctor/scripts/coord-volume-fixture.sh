#!/bin/bash
# coord-volume-fixture.sh — asserts the COORD VOLUME law: the ledger is never
# compacted-and-archived; past threshold the ACTIVE volume is SEALED WHOLE as the
# next COORD-<NNN>.md and a fresh active volume starts. Exercises the SessionEnd
# hook (roll + auto-cushion) and the SessionStart hook's director-detect against
# synthetic throwaway git repos. Self-relative: runs from anywhere.
# PASS/FAIL per assertion, summary at the end, nonzero exit if anything failed.
set -uo pipefail

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
END_HOOK="$SD/../../../hooks/session-end.sh"
START_HOOK="$SD/../../../hooks/session-start.sh"

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS  $1"; }
no()  { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1" "want '$3' got '$2'"; fi; }
has() { if grep -qF -- "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1" "missing: $2"; fi; }
hasnt(){ if grep -qF -- "$2" "$3" 2>/dev/null; then no "$1" "present: $2"; else ok "$1"; fi; }

for f in "$END_HOOK" "$START_HOOK"; do
  [ -f "$f" ] || { echo "FATAL: missing $f"; exit 9; }
done

TMP="$(mktemp -d)"
# TRAP LAW: session-end.sh now fires the pulse refresher, which is DETACHED and may still
# be writing into the sandbox when the trap runs ("Directory not empty"). Reap our own
# daemons first — a fixture owns every process it causes, even the reparented ones.
trap 'pkill -f "estate-pulse.sh $TMP" 2>/dev/null; sleep 0.4; rm -rf "$TMP"' EXIT INT TERM

md5of() { md5 -q "$1" 2>/dev/null || md5sum "$1" 2>/dev/null | cut -d' ' -f1; }
ledger_n() { grep -c '^- ' "$1" 2>/dev/null || echo 0; }

# seed a COORD-style file: header block, ## LEDGER, N ledger lines. When $4 is
# "closed" the last line is a /sessionend close line (auto-cushion suppressed, so
# the pre-roll bytes equal the seed bytes exactly).
seed() {
  local path="$1" title="$2" n="$3" last="${4:-}"
  { echo "# $title"
    echo
    echo "Append-only, newest at the bottom. Never compacted — it rolls into volumes."
    echo
    echo "## LEDGER"
    local i=1
    while [ "$i" -le "$n" ]; do
      if [ "$i" -eq "$n" ] && [ "$last" = "closed" ]; then
        echo "- [2026-07-25 00:00Z] [sessionend] session closed: seed | handoff: START-HERE.md"
      else
        echo "- [2026-07-25 00:00Z] [seed] line $i -> landed | evidence: fixture"
      fi
      i=$((i+1))
    done
  } > "$path"
}

newrepo() { local r="$TMP/$1"; mkdir -p "$r"; git -C "$r" init -q 2>/dev/null; echo "$r"; }
runend()  { ( cd "$1" && bash "$END_HOOK" </dev/null; echo "rc=$?" ) ; }

# ── repo A: 505-line COORD ledger -> seals as COORD-001.md ───────────────────
A="$(newrepo repo-a)"
seed "$A/COORD.md" "COORD.md — session coordination ledger" 505 closed
PRE_MD5="$(md5of "$A/COORD.md")"
OUT="$(runend "$A" 2>&1)"
chk "A: hook exits 0"                 "$(printf '%s' "$OUT" | tail -1)" "rc=0"
chk "A: hook silent"                  "$(printf '%s' "$OUT" | grep -vc '^rc=')" "0"
[ -f "$A/COORD-001.md" ] && ok "A: sealed volume COORD-001.md exists" \
  || no "A: sealed volume COORD-001.md exists"
chk "A: sealed copy byte-identical (md5)" "$(md5of "$A/COORD-001.md")" "$PRE_MD5"
chk "A: sealed volume keeps all 505 ledger lines" "$(ledger_n "$A/COORD-001.md")" "505"
chk "A: fresh active volume has exactly 1 ledger line" "$(ledger_n "$A/COORD.md")" "1"
has  "A: fresh volume carries the header block"  "# COORD.md — session coordination ledger" "$A/COORD.md"
has  "A: fresh volume has the continues-line"    "> Continues COORD-001.md · volume 2" "$A/COORD.md"
has  "A: fresh volume has the LEDGER marker"     "## LEDGER" "$A/COORD.md"
has  "A: fresh volume records the roll"          "[hook] volume rolled — previous volume sealed as COORD-001.md" "$A/COORD.md"
hasnt "A: no COORD-ARCHIVE.md written"           "-" "$A/COORD-ARCHIVE.md"
chk  "A: no tmp file left behind" "$(ls "$A" | grep -c 'sessionend.tmp')" "0"

# second roll -> COORD-002.md, first volume untouched
S1_MD5="$(md5of "$A/COORD-001.md")"
i=1; while [ "$i" -le 504 ]; do
  echo "- [2026-07-25 01:00Z] [seed] second volume line $i -> landed | evidence: fixture" >> "$A/COORD.md"
  i=$((i+1)); done
echo "- [2026-07-25 01:00Z] [sessionend] session closed: seed2 | handoff: START-HERE.md" >> "$A/COORD.md"
runend "$A" >/dev/null 2>&1
[ -f "$A/COORD-002.md" ] && ok "A: second roll seals COORD-002.md" || no "A: second roll seals COORD-002.md"
chk "A: sealed volumes are immutable (001 md5 unchanged)" "$(md5of "$A/COORD-001.md")" "$S1_MD5"
has "A: volume 3 continues-line" "> Continues COORD-002.md · volume 3" "$A/COORD.md"

# ── repo B: 100-line ledger -> no roll, cushion still fires ──────────────────
B="$(newrepo repo-b)"
seed "$B/COORD.md" "COORD.md — session coordination ledger" 100
runend "$B" >/dev/null 2>&1
chk "B: 100-line ledger does not roll" "$(ls "$B" | grep -c '^COORD-[0-9][0-9][0-9]\.md$')" "0"
has "B: auto-cushion appended (cushion duty intact)" "auto-cushion" "$B/COORD.md"
chk "B: cushion adds exactly one line" "$(ledger_n "$B/COORD.md")" "101"
runend "$B" >/dev/null 2>&1
chk "B: second run adds no duplicate cushion" "$(ledger_n "$B/COORD.md")" "101"

# ── repo C: COORD-AGENTS.md at 1005 lines -> sealed COORD-AGENTS-001.md ──────
C="$(newrepo repo-c)"
seed "$C/COORD.md" "COORD.md — session coordination ledger" 5 closed
seed "$C/COORD-AGENTS.md" "COORD-AGENTS.md — agent activity ledger" 1005 closed
AG_MD5="$(md5of "$C/COORD-AGENTS.md")"
runend "$C" >/dev/null 2>&1
[ -f "$C/COORD-AGENTS-001.md" ] && ok "C: agents ledger seals at >1000" \
  || no "C: agents ledger seals at >1000"
chk "C: agents sealed copy byte-identical (md5)" "$(md5of "$C/COORD-AGENTS-001.md")" "$AG_MD5"
has "C: fresh agents volume continues-line" "> Continues COORD-AGENTS-001.md · volume 2" "$C/COORD-AGENTS.md"
chk "C: small COORD.md left unrolled" "$(ls "$C" | grep -c '^COORD-[0-9][0-9][0-9]\.md$')" "0"

# ── legacy: a repo with COORD-ARCHIVE.md keeps it untouched ──────────────────
L="$(newrepo repo-legacy)"
seed "$L/COORD.md" "COORD.md — session coordination ledger" 505 closed
printf '# COORD-ARCHIVE.md — retired scheme\n\n## ARCHIVE\n- [2026-01-01 00:00Z] [old] archived line\n' > "$L/COORD-ARCHIVE.md"
LEG_MD5="$(md5of "$L/COORD-ARCHIVE.md")"
runend "$L" >/dev/null 2>&1
chk "L: legacy COORD-ARCHIVE.md untouched" "$(md5of "$L/COORD-ARCHIVE.md")" "$LEG_MD5"
[ -f "$L/COORD-001.md" ] && ok "L: legacy repo still rolls into volumes" \
  || no "L: legacy repo still rolls into volumes"

# ── outside a git repo (2026-08-02): the volume law follows the LEDGER, not git.
# It used to follow git, and that is precisely the defect this fixture now guards:
# a whole session ran ungoverned in a non-git folder because every estate hook was
# git-gated. An ESTABLISHED non-git project (a COORD.md is what establishment
# means) gets the full treatment; a directory with no ledger within reach still
# gets absolute silence, which is the half of the old law that was always right.
N="$TMP/not-a-repo"; mkdir -p "$N"
seed "$N/COORD.md" "COORD.md — session coordination ledger" 505 closed
OUT="$( cd "$N" && bash "$END_HOOK" </dev/null 2>&1; echo "rc=$?" )"
chk "N: outside git exits 0"   "$(printf '%s' "$OUT" | tail -1)" "rc=0"
chk "N: outside git is silent" "$(printf '%s' "$OUT" | grep -vc '^rc=')" "0"
chk "N: established non-git project SEALS its volume" \
  "$(ls "$N" | grep -c '^COORD-[0-9][0-9][0-9]\.md$')" "1"
has "N: fresh non-git volume continues-line" "> Continues COORD-001.md · volume 2" "$N/COORD.md"

# no ledger anywhere within reach → the silence law, unchanged.
NB="$TMP/not-a-repo-bare/a/b/c"; mkdir -p "$NB"
OUT="$( cd "$NB" && bash "$END_HOOK" </dev/null 2>&1; echo "rc=$?" )"
chk "N: no-ledger dir exits 0"       "$(printf '%s' "$OUT" | tail -1)" "rc=0"
chk "N: no-ledger dir is silent"     "$(printf '%s' "$OUT" | grep -vc '^rc=')" "0"
chk "N: no-ledger dir writes nothing" "$(ls -A "$TMP/not-a-repo-bare" | wc -l | tr -d ' ')" "1"

# ── director-detect: sealed volumes must NOT look like lane blackboards ──────
# The hook is copied in so its fire-and-forget self-update targets the throwaway
# repo (which has no remote) instead of the real plugin clone.
D1="$(newrepo repo-vol)"; cp "$START_HOOK" "$D1/session-start.sh"
seed "$D1/COORD.md" "COORD.md — session coordination ledger" 3
cp "$D1/COORD.md" "$D1/COORD-001.md"; cp "$D1/COORD.md" "$D1/COORD-012.md"
cp "$D1/COORD.md" "$D1/COORD-AGENTS.md"; cp "$D1/COORD.md" "$D1/COORD-AGENTS-001.md"
OUT="$( cd "$D1" && bash ./session-start.sh </dev/null 2>/dev/null )"
case "$OUT" in *fable-director*) no "V: volumes do not fire director-detect" "it fired" ;;
                              *) ok "V: volumes do not fire director-detect" ;; esac

D2="$(newrepo repo-lane)"; cp "$START_HOOK" "$D2/session-start.sh"
seed "$D2/COORD.md" "COORD.md — session coordination ledger" 3
cp "$D2/COORD.md" "$D2/COORD-D1.md"
OUT="$( cd "$D2" && bash ./session-start.sh </dev/null 2>/dev/null )"
case "$OUT" in *fable-director*) ok "V: a real lane (COORD-D1.md) still fires director-detect" ;;
                              *) no "V: a real lane (COORD-D1.md) still fires director-detect" "silent" ;; esac

echo
echo "── coord-volume-fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
