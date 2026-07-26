#!/bin/bash
# fixture.sh — proves director.py's three structural claims against synthetic runs.
#
# The point of this instrument is that the director's own failure mode ("the last
# stage never ran") must FIRE, not merely be described. So every case here is a
# negative control as much as a positive one: verify must exit 3 on an unticked box,
# an empty stage folder and a drifted handoff, and must exit 0 the moment — and only
# the moment — the run is genuinely complete.
#
# Self-relative, runs from any cwd, writes only inside its own mktemp dir.
# Usage: bash <director-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
D="$SD/director.py"
[ -f "$D" ] || { echo "FATAL: missing $D"; exit 9; }

W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT INT TERM
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF -- "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — not found: $2"; fi; }
inout(){ if printf '%s' "$1" | grep -qF -- "$2"; then ok "$3"; else no "$3 — output was: $1"; fi; }

# Real sibling skills, so resolution is exercised against the shipped tree rather
# than a mock that would agree with itself.
S1=recap; S2=critic
TICK(){ # TICK <run> <slug> <label>
  python3 - "$1/$2background.md" "$3" <<'PY'
import re,sys
p,label=sys.argv[1],sys.argv[2]
t=open(p,encoding="utf-8").read()
open(p,"w",encoding="utf-8").write(t.replace("- [ ] %s"%label,"- [x] %s"%label))
PY
}

echo "── A · plan resolves the chain and scaffolds the run"
R="$W/repo"; mkdir -p "$R"
OUT="$(python3 "$D" plan --chain "$S1,$S2" --topic "Widget rollout" --root "$R" 2>&1)"
t "plan exits 0" "$?" "0"
RUN="$R/pipeline"
t "run dir created" "$([ -d "$RUN" ] && echo yes)" "yes"
t "stage folder 01 scaffolded" "$([ -d "$RUN/01-$S1" ] && echo yes)" "yes"
t "stage folder 02 scaffolded" "$([ -d "$RUN/02-$S2" ] && echo yes)" "yes"
SLUG=widget-rollout
t "checklist file written" "$([ -f "$RUN/${SLUG}background.md" ] && echo yes)" "yes"
has "checklist box for stage 01" "- [ ] 01-$S1" "$RUN/${SLUG}background.md"
has "checklist box for stage 02" "- [ ] 02-$S2" "$RUN/${SLUG}background.md"
has "the perform-from-SKILL.md law survives into the scaffold" \
  "never by invoking the sub-skill through the Skill tool" "$RUN/${SLUG}background.md"
t "run.json written" "$([ -f "$RUN/run.json" ] && echo yes)" "yes"
t "each stage carries a resolved SKILL.md path" \
  "$(python3 -c "
import json;r=json.load(open('$RUN/run.json'))
import os;print(all(os.path.isfile(s['skill_md']) for s in r['chain']))")" "True"
inout "$OUT" "planned 2 stage(s)" "plan reports the stage count"

echo "── B · a missing skill fails fast, and scaffolds NOTHING"
R2="$W/repo2"; mkdir -p "$R2"
OUT="$(python3 "$D" plan --chain "$S1,definitely-not-a-skill" --topic "X" --root "$R2" 2>&1)"
t "plan with an unresolvable skill exits 2" "$?" "2"
inout "$OUT" "cannot resolve 1 skill(s)" "names how many it could not resolve"
inout "$OUT" "definitely-not-a-skill" "names the missing skill"
inout "$OUT" "looked in:" "prints the search path it tried"
t "no run dir was created" "$([ -d "$R2/pipeline" ] && echo yes || echo no)" "no"

echo "── C · verify fires on the director's own failure mode"
t "fresh run (both stages empty, boxes unticked) → exit 3" \
  "$(python3 "$D" verify --run "$RUN" >"$W/v1.out" 2>&1; echo $?)" "3"
has "names the empty stage folder" "stage folder is empty" "$W/v1.out"
has "names the unticked box" "checklist box is UNTICKED" "$W/v1.out"
has "verdict line says INCOMPLETE" "pipeline: INCOMPLETE" "$W/v1.out"

echo "── D · a ticked box with an empty folder is still caught (the tick is not evidence)"
TICK "$RUN" "$SLUG" "01-$S1"
t "ticked box + empty folder → still exit 3" \
  "$(python3 "$D" verify --run "$RUN" >"$W/v2.out" 2>&1; echo $?)" "3"
has "the empty folder is still the finding" "stage folder is empty" "$W/v2.out"

echo "── E · handoff manifests input + output with sha256"
printf '# stage one dossier\nfindings\n' > "$RUN/01-$S1/widget-rolloutDossier.md"
printf '# stage one background\nworking\n' > "$RUN/01-$S1/widget-rolloutbackground.md"
OUT="$(python3 "$D" handoff --run "$RUN" --stage 01 2>&1)"; t "handoff stage 01 exits 0" "$?" "0"
t "handoff.json written" "$([ -f "$RUN/01-$S1/handoff.json" ] && echo yes)" "yes"
J(){ python3 -c "
import json,sys;m=json.load(open('$1'));print(eval(sys.argv[1],{'m':m}))" "$2"; }
t "stage 1 input is the seed, not a fabricated file" \
  "$(J "$RUN/01-$S1/handoff.json" "m['input'].get('kind')=='seed'")" "True"
t "output is the dossier, not the background" \
  "$(J "$RUN/01-$S1/handoff.json" "m['output']['path'].endswith('Dossier.md')")" "True"
t "output sha256 is a real digest" \
  "$(J "$RUN/01-$S1/handoff.json" "len(m['output']['sha256'])==64")" "True"
t "sha matches the file on disk" \
  "$(J "$RUN/01-$S1/handoff.json" "m['output']['sha256']")" \
  "$(python3 -c "import hashlib;print(hashlib.sha256(open('$RUN/01-$S1/widget-rolloutDossier.md','rb').read()).hexdigest())")"

echo "── F · stage 2's input is stage 1's real output (the handoff is genuine)"
printf '# stage two dossier\ncritique\n' > "$RUN/02-$S2/widget-rolloutDossier.md"
python3 "$D" handoff --run "$RUN" --stage 02 >/dev/null 2>&1; t "handoff stage 02 exits 0" "$?" "0"
t "stage 2 input path is stage 1's dossier" \
  "$(J "$RUN/02-$S2/handoff.json" "'01-$S1' in m['input']['path'] and m['input']['path'].endswith('Dossier.md')")" "True"
t "stage 2 records which stage it came from" \
  "$(J "$RUN/02-$S2/handoff.json" "m['input'].get('from')")" "01-$S1"

echo "── G · the run only verifies when it is genuinely complete"
t "stage 02 box still unticked → exit 3" \
  "$(python3 "$D" verify --run "$RUN" >"$W/v3.out" 2>&1; echo $?)" "3"
has "…and the finding is the box, not the folder" "02-$S2: checklist box is UNTICKED" "$W/v3.out"
TICK "$RUN" "$SLUG" "02-$S2"
t "complete run → exit 0" "$(python3 "$D" verify --run "$RUN" >"$W/v4.out" 2>&1; echo $?)" "0"
has "verdict line says VERIFIED" "pipeline: VERIFIED" "$W/v4.out"
has "verify refuses to overclaim (structure only)" "structure only" "$W/v4.out"

echo "── H · drift is caught: the file handed forward is not the file that is there"
printf '# stage one dossier\nSOMEONE REWROTE THIS AFTER THE HANDOFF\n' \
  > "$RUN/01-$S1/widget-rolloutDossier.md"
t "a rewritten output → exit 3" \
  "$(python3 "$D" verify --run "$RUN" >"$W/v5.out" 2>&1; echo $?)" "3"
has "names the drift" "changed since it was recorded" "$W/v5.out"
python3 "$D" handoff --run "$RUN" --stage 01 >/dev/null 2>&1
python3 "$D" handoff --run "$RUN" --stage 02 >/dev/null 2>&1
t "re-recording the handoff clears it" "$(python3 "$D" verify --run "$RUN" >/dev/null 2>&1; echo $?)" "0"

echo "── I · a missing handoff input is caught too"
rm -f "$RUN/01-$S1/widget-rolloutDossier.md"
t "stage 1's output deleted → exit 3" \
  "$(python3 "$D" verify --run "$RUN" >"$W/v6.out" 2>&1; echo $?)" "3"
has "names the gone file" "handoff input is gone" "$W/v6.out"

echo "── J · records that land outside the stage folder are allowed, manifest-verified"
R3="$W/repo3"; mkdir -p "$R3/archive"
python3 "$D" plan --chain "$S1" --topic "Records run" --root "$R3" >/dev/null 2>&1
RUN3="$R3/pipeline"
printf '{"id":"F-1"}\n' > "$R3/archive/findings.jsonl"
python3 "$D" handoff --run "$RUN3" --stage 01 --output "$R3/archive/findings.jsonl" \
  >/dev/null 2>&1; t "handoff with an external output exits 0" "$?" "0"
t "marked external in the manifest" \
  "$(J "$RUN3/01-$S1/handoff.json" "m['external_output']")" "True"
TICK "$RUN3" "records-run" "01-$S1"
t "empty stage folder + external output → exit 0" \
  "$(python3 "$D" verify --run "$RUN3" >"$W/v7.out" 2>&1; echo $?)" "0"
has "the allowance is stated, not silent" "outputs live outside the stage folder" "$W/v7.out"
rm -f "$R3/archive/findings.jsonl"
t "…but the external output must still EXIST" \
  "$(python3 "$D" verify --run "$RUN3" >/dev/null 2>&1; echo $?)" "3"

echo "── K · a second run does not collide with the first"
python3 "$D" plan --chain "$S1" --topic "Second topic" --root "$R" >/dev/null 2>&1
t "second plan exits 0" "$?" "0"
t "…and lands in pipeline-2/" "$([ -f "$R/pipeline-2/run.json" ] && echo yes)" "yes"
t "the first run's stage folders are untouched" \
  "$([ -f "$RUN/02-$S2/handoff.json" ] && echo yes)" "yes"

echo "── L · argument handling"
python3 "$D" verify --run "$W/nowhere" >"$W/v8.out" 2>&1; t "verify on a non-run dir exits 2" "$?" "2"
has "…and says why" "is not a planned run dir" "$W/v8.out"
python3 "$D" handoff --run "$RUN" --stage 09 >"$W/v9.out" 2>&1; t "handoff on an unknown stage exits 2" "$?" "2"
python3 "$D" bogus --root "$R" >/dev/null 2>&1; t "unknown subcommand exits 2" "$?" "2"
python3 "$D" plan --chain "" --topic X --root "$W/x" >/dev/null 2>&1; t "an empty chain exits 2" "$?" "2"

echo
echo "director fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
