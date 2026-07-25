#!/usr/bin/env bash
# new-fable-project.sh — scaffold the "3 DEVS AND A RELAY" blackboards into a repo.
# FILE-ONLY: creates dirs + copies V4/kickoff + generates one blackboard per lane with
# correct absolute paths and end-anchored tokens. Spawns NOTHING (session creation is
# owner-only / references/spawn-lanes.md). Idempotent-ish: refuses to clobber existing
# COORD*.md unless --force.
#
# Usage:  new-fable-project.sh <repo-root> [--force] [lane-spec ...]
#   lane-spec = NAME:ROLE   ROLE ∈ {ship,research,content,qc}
#   default lanes: D1:ship D2:research D3:content Q1:qc
# The FIRST ship lane owns COORD.md (no suffix) + STATE + a DIRECTOR-RESUME stub.
set -eu

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REF="$SKILL_DIR/references"

die(){ echo "new-fable-project: $*" >&2; exit 1; }
[ $# -ge 1 ] || die "usage: new-fable-project.sh <repo-root> [--force] [NAME:ROLE ...]"
REPO="$1"; shift
[ -d "$REPO" ] || die "repo root not a directory: $REPO"
REPO="$(cd "$REPO" && pwd)"
PROJECT="$(basename "$REPO")"

FORCE=0; LANES=""
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    *:*)     LANES="$LANES $a" ;;
    *)       die "bad lane-spec '$a' (want NAME:ROLE)" ;;
  esac
done
[ -n "$LANES" ] || LANES="D1:ship D2:research D3:content Q1:qc"

mkdir -p "$REPO/_fable" "$REPO/_reports"
: > /dev/null
[ -f "$REPO/COORD-ARCHIVE.md" ] || : > "$REPO/COORD-ARCHIVE.md"

# carry the protocol + kickoff (repo copy is authoritative once present)
for f in PLAN-FABLE-DIRECTOR-V4.md; do
  [ -f "$REPO/$f" ] || cp "$REF/$f" "$REPO/$f"
done
[ -f "$REPO/_fable/KICKOFF-DIRECTOR.md" ] || sed "s/<PROJECT>/$PROJECT/g" "$REF/KICKOFF-DIRECTOR.md" > "$REPO/_fable/KICKOFF-DIRECTOR.md"

NOW="$(date -u '+%Y-%m-%d %H:%MZ' 2>/dev/null || echo unknown)"
ship_done=0

emit_blackboard(){          # $1=NAME $2=ROLE $3=abs-file-path
  name="$1"; role="$2"; file="$3"
  # A real blackboard has ## PROTOCOL — skip it. A COORD.md WITHOUT it is the
  # SessionStart hook's session-ledger stub: upgrade it in place (preserve its
  # ledger lines, rebuild as a full blackboard). Plain -e would silently skip
  # the SHIP blackboard on every hook-touched repo — the one lane that matters.
  stub_ledger=""
  if [ -e "$file" ] && [ "$FORCE" -eq 0 ]; then
    if grep -q '^## PROTOCOL' "$file" 2>/dev/null; then
      echo "skip (exists): $file"; return
    fi
    stub_ledger="$(grep '^- ' "$file" 2>/dev/null || true)"
    echo "upgrading session-ledger stub into blackboard: $file"
  fi
  {
    printf '# %s — Fable-director ↔ %s blackboard (role: %s)\n\n' "$(basename "$file" .md)" "$name" "$role"
    printf '%s OWN wire — one coord file PER lane, no shared writes. Director writes DIRECTIVES + →A\n' "$name"
    printf 'answers HERE; %s writes everything else HERE and ONLY here. Never write other lanes'"'"' files\n' "$name"
    printf '(reading is fine). Never send_message (bootstrap/rotation only). Owner above all.\n'
    printf 'Protocol of record: PLAN-FABLE-DIRECTOR-V4.md (repo root).\n\n'
    printf '## PROTOCOL\n'
    printf '1. On wake read THIS file end-to-end. Drain →%s directives by priority; flip [ ]→[x]/[!]\n' "$name"
    printf '   + a LEDGER line with evidence when a DONE-WHEN resolves.\n'
    printf '2. Never block: 2 fails → ESCALATION; taste/architecture → QUESTION with a DEFAULT; move on.\n'
    printf '3. READ-ONLY on the tree unless a directive grants paths. Never git add -A. Deploys/secrets\n'
    printf '   = owner via paste blocks. EDIT AUTHORITY: code = the DIRECTORS hands; you hand EDIT SPECS\n'
    printf '   (file · exact location · before→after · why · risk).\n'
    printf '4. PING on trigger events ONLY (drained · brief ready · escalation · blocked): a LEDGER line\n'
    printf '   ENDING with →PING-QC (reviewable work) or →PING-DIRECTOR (SEV-1 blocker/money/invariant).\n'
    printf '   Token at LINE END only, never mid-prose. RE-ARM YOUR WATCH AT EVERY IDLE (log its task id).\n'
    printf '5. Ledger tag [%s]; append-only; date -u stamps; re-read the tail before appending; compact\n' "$name"
    printf '   past ~40 lines to COORD-ARCHIVE.md.\n\n'
    printf '### %s WATCH — re-arm at every idle (verbatim, run_in_background)\n' "$name"
    printf '```\n'
    printf 'f="%s"; base=$(grep -E '"'"'PING-%s$'"'"' "$f" | tail -1 | md5); while :; do sleep 20; cur=$(grep -E '"'"'PING-%s$'"'"' "$f" | tail -1 | md5); [ "$cur" != "$base" ] && exit 0; done\n' "$file" "$name" "$name"
    printf '```\n'
    printf '### DIRECTOR WATCH on this file — re-arm at every burst-close (director, verbatim)\n'
    printf '```\n'
    printf 'f="%s"; base=$(grep -E '"'"'PING-DIRECTOR$'"'"' "$f" | tail -1 | md5); while :; do sleep 20; cur=$(grep -E '"'"'PING-DIRECTOR$'"'"' "$f" | tail -1 | md5); [ "$cur" != "$base" ] && exit 0; done\n' "$file"
    printf '```\n\n'

    if [ "$role" = qc ]; then
      cat <<'QCX'
### QC CHARTER + REFUTER CHECKLIST (this lane originates nothing, approves nothing)
QC arms a watch on EVERY lane file grepping 'PING-QC$' + one on this file. It verifies each
lane brief against the tree, kills false positives with evidence, aggregates, and pings the
director ONCE per batch from THIS file. Refuter checklist (every rule was paid for):
- route/dispatch-layer check on any "never-called/never-passed" claim
- test harnesses in EVERY ref-sweep scope (a deleted-but-tested fn turned verify RED)
- string-name greps (onclick / event maps / window.*)
- does-the-output-feed-something-downstream on any "dead output" claim
- [doc]/[vendor]/community labels + TWO sources on load-bearing external claims
- independent scope re-estimate (honest-scope beats optimistic)
- a CONCRETE failure scenario (inputs → wrong outcome) or the finding is PLAUSIBLE, not CONFIRMED
SEV: 1 = wake the director now (money/invariant/blocker) · 2 = batch · 3 = FYI, no token.

QCX
    fi

    if [ "$role" = ship ]; then
      cat <<'SHX'
## STATE  (SHIP LANE ONLY — owner-confirmed live reality, never inferred)
(empty — the first STATE-fill directive writes this: HEAD · version · what is LIVE (owner-
confirmed only) · in-flight · blockers)

### DIRECTOR RESUME  (fresh-director cold-start — read PLAN-FABLE-DIRECTOR-V4.md → every
### COORD*.md → re-arm a director watch per file → open threads below)
OPEN THREADS: (the sitting director keeps this trued before every rotation)

SHX
    fi

    printf '## DIRECTIVES  (director writes; lane flips [ ]→[x]/[!])\n'
    printf -- '- [ ] D-001 →%s P0  OBJECTIVE: bootstrap — adopt the protocol + prove auth isolation +\n' "$name"
    printf '      arm your watch. DONE-WHEN: LEDGER line [%s] — env has NO ANTHROPIC_API_KEY\n' "$name"
    printf '      (subscription) + your model + THIS file'"'"'s watch armed end-anchored (task id logged).\n'
    printf '## ESCALATIONS →director\n(none)\n'
    printf '## BRIEF-UP →QC/director  (≤40 lines; EDIT-SPEC format for code findings)\n(none)\n'
    printf '## QUESTIONS →director  (taste-calls WITH a DEFAULT)\n(none)\n'
    printf '## LEDGER  (append-only, newest at bottom)\n'
    [ -n "$stub_ledger" ] && printf '%s\n' "$stub_ledger"
    printf -- '- [%s] [director] blackboard scaffolded (new-fable-project.sh); D-001 posted.\n' "$NOW"
  } > "$file"
  echo "wrote: $file"
}

for spec in $LANES; do
  name="${spec%%:*}"; role="${spec##*:}"
  if [ "$role" = ship ] && [ "$ship_done" -eq 0 ]; then
    emit_blackboard "$name" ship "$REPO/COORD.md"; ship_done=1
  else
    emit_blackboard "$name" "$role" "$REPO/COORD-$name.md"
  fi
done

cat <<EOF

SCAFFOLD COMPLETE → $REPO
  protocol: PLAN-FABLE-DIRECTOR-V4.md   kickoff: _fable/KICKOFF-DIRECTOR.md
  archive:  COORD-ARCHIVE.md      dirs: _fable/ _reports/
NEXT (director / owner):
  1. Confirm the project CLAUDE.md has: hard-invariants list · paid-for-pitfalls · one-command ritual.
  2. Owner approves the deny-hook live (references/coord-scaffold.md §3).
  3. Create sessions (owner app-panes, or references/spawn-lanes.md after the macOS grant),
     send each lane its bootstrap (coord-scaffold.md §2), demand the proof trio.
This script spawned NOTHING — session creation is deliberately a separate, gated step.
EOF
