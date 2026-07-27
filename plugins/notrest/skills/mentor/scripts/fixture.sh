#!/bin/bash
# fixture.sh — asserts mentor.py's charter idempotency, the LIVE engine read in the escort,
# the checkpoint parse (gated vs ungated, NEEDS states, exit 3), the status line, malformed
# room tolerance, the inherited no-secrets screen, and the no-writes law.
#
# Self-relative: runs from any cwd, writes only inside its own mktemp dir, never touches a
# real room (CHATROOM_ROOT is redirected) and never sends anything anywhere.
# Usage: bash <mentor-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
M="$(cd "$(dirname "$0")" && pwd)/mentor.py"
R="$(cd "$(dirname "$0")" && pwd)/../../chatroom/scripts/room.py"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
export CHATROOM_ROOT="$W/rooms"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ case "$2" in *"$3"*) ok "$1";; *) no "$1 — not found in output: [$3]";; esac; }
hasnt(){ case "$2" in *"$3"*) no "$1 — present but must not be: [$3]";; *) ok "$1";; esac; }
lines(){ wc -l < "$CHATROOM_ROOT/$1/room.md" | tr -d ' '; }
# content fingerprints, folded to one number so a failure prints a diff-able value
# instead of a thousand paths
manifest(){ find "$1" -type f 2>/dev/null | sort | while read -r f; do
              printf '%s %s\n' "$(cksum < "$f")" "$f"; done | cksum; }
# everything in the sandbox EXCEPT the room root (which mentor.py may write through
# room.py) and $W/out (which exists only because the operator named --out)
outside(){ find "$W" \( -path "$CHATROOM_ROOT" -o -path "$W/out" \) -prune -o -type f \
             -print 2>/dev/null | sort \
             | while read -r f; do printf '%s %s\n' "$(cksum < "$f")" "$f"; done | cksum; }

# ── a scratch ENGINE, so every "read live" claim is checked against known values ─────
E="$W/engine"
mkdir -p "$E/plugins/notrest/.claude-plugin" "$E/archive"
printf '{"name":"notrest","version":"9.9.9-fixture"}\n' \
  > "$E/plugins/notrest/.claude-plugin/plugin.json"
for s in alpha beta gamma doctor eval; do mkdir -p "$E/plugins/notrest/skills/$s"
  printf -- '---\nname: %s\n---\n' "$s" > "$E/plugins/notrest/skills/$s/SKILL.md"; done
mkdir -p "$E/plugins/notrest/skills/alpha/scripts" "$E/plugins/notrest/skills/doctor/scripts" \
         "$E/plugins/notrest/skills/eval/scripts"
printf 'print(1)\n' > "$E/plugins/notrest/skills/alpha/scripts/alpha.py"
printf 'print(1)\n' > "$E/plugins/notrest/skills/doctor/scripts/doctor.py"
printf 'print(1)\n' > "$E/plugins/notrest/skills/eval/scripts/eval.py"
# present: CLAUDE.md CHANGELOG.md COORD.md README.md archive/findings.jsonl
# absent : docs/CAPABILITIES.md docs/JOURNEY.md COORD-AGENTS.md  (the existence check)
for f in CLAUDE.md CHANGELOG.md COORD.md README.md; do printf 'scratch\n' > "$E/$f"; done
printf '{}\n' > "$E/archive/findings.jsonl"
git -C "$E" init -q 2>/dev/null
git -C "$E" -c user.email=f@x -c user.name=f add -A >/dev/null 2>&1
git -C "$E" -c user.email=f@x -c user.name=f commit -qm scratch >/dev/null 2>&1
HEAD="$(git -C "$E" rev-parse --short HEAD 2>/dev/null)"
PLAIN="$W/plain-engine"; mkdir -p "$PLAIN"        # no git, no plugin dir

# ── A · charter ─────────────────────────────────────────────────────────────────────
echo "── A · charter (creates through room.py, posts once, never re-charters)"
OUT="$(python3 "$M" charter --room build --mentor mx --builder bx --engine "$E" \
        --note "v0.1 shell" 2>&1)"; t "charter exits 0" "$?" "0"
t "the room file exists" "$([ -f "$CHATROOM_ROOT/build/room.md" ] && echo yes || echo no)" "yes"
t "header + one charter post" "$(lines build)" "2"
BODY="$(cat "$CHATROOM_ROOT/build/room.md")"
has "the charter marker is in the room" "$BODY" "MENTOR-DEV CHARTER"
has "the charter names the mentor" "$BODY" "MENTOR @mx"
has "the charter names the builder" "$BODY" "BUILDER @bx"
has "the charter carries the checkpoint format" "$BODY" \
    "CHECKPOINT <n>: <what> -> <evidence> | NEEDS:"
has "the charter states bidirectional correction" "$BODY" "CORRECTION RUNS BOTH WAYS"
has "the charter states the owner reads the room" "$BODY" "THE OWNER READS THE ROOM"
has "the charter carries the arrangement note" "$BODY" "v0.1 shell"
has "the charter read the engine live (version)" "$BODY" "9.9.9-fixture"
has "the charter read the engine live (skill count)" "$BODY" "5 skills"
has "the charter posted as the mentor handle" "$BODY" "@mx: MENTOR-DEV CHARTER"

OUT="$(python3 "$M" charter --room build --mentor mx --builder bx 2>&1)"
t "second charter exits 0 (idempotent)" "$?" "0"
t "second charter posted nothing" "$(lines build)" "2"
has "second charter reports the existing one" "$OUT" "already chartered"
has "second charter names who chartered it" "$OUT" "mentor @mx · builder @bx"

echo "── A2 · the inherited no-secrets screen (room.py's law, not a copy of it)"
BEFORE_OUT="$(outside)"
OUT="$(python3 "$M" charter --room leak --mentor mx --builder bx \
        --note "use AKIAIOSFODNN7EXAMPLE to fetch it" 2>&1)"; RC=$?
t "a secret-shaped charter is REFUSED with exit 5" "$RC" "5"
t "the room was created but nothing was posted" "$(lines leak)" "1"
has "the refusal names the class" "$OUT" "aws-access-key-id"
hasnt "the refusal never echoes the matched text" "$OUT" "AKIAIOSFODNN7EXAMPLE"

# ── B · escort ──────────────────────────────────────────────────────────────────────
echo "── B · escort (reads the engine live, prints, never sends)"
BEFORE_ENGINE="$(manifest "$E")"; BEFORE_LINES="$(lines build)"
OUT="$(python3 "$M" escort --room build --engine "$E" 2>&1)"; t "escort exits 0" "$?" "0"
has "version read live from plugin.json" "$OUT" "version: 9.9.9-fixture"
has "HEAD read live from git" "$OUT" "HEAD $HEAD"
has "skill count read live from the dirs" "$OUT" "skills: 5"
has "instruments read live (alpha)" "$OUT" "alpha/alpha.py"
has "instruments read live (doctor)" "$OUT" "doctor/doctor.py"
has "gate command built from the instrument that exists" "$OUT" \
    "eval/scripts/eval.py check --root ."
has "roles inferred from the room's charter" "$OUT" "I am @mx (mentor); you are"
has "reading order keeps a path that exists" "$OUT" "- CLAUDE.md —"
hasnt "reading order drops a path this engine lacks" "$OUT" "- docs/JOURNEY.md —"
has "the dropped paths are named as absent, not silently cut" "$OUT" \
    "absent in this engine"
has "the checkpoint protocol travels in the escort" "$OUT" "## CHECKPOINT PROTOCOL"
has "the first-reply contract asks for cwd state" "$OUT" "cwd state"
has "the first-reply contract demands recommended defaults" "$OUT" \
    "each carrying its own recommended default"
has "the traveling laws travel" "$OUT" "## LAWS THAT TRAVEL"
has "opus-only law is carried verbatim" "$OUT" 'model "opus" explicitly'
has "no hold by default" "$OUT" "NO HOLD is in force"
t "escort posted NOTHING to the room" "$(lines build)" "$BEFORE_LINES"
t "escort left the engine tree untouched" "$(manifest "$E")" "$BEFORE_ENGINE"

OUT="$(python3 "$M" escort --room build --engine "$E" --hold "spec is pending my gate" 2>&1)"
has "--hold emits the HOLD line with its reason" "$OUT" "HOLD: spec is pending my gate"
has "--hold holds BUILDING only" "$OUT" "the hold is on BUILDING"
OUT="$(python3 "$M" escort --room build --engine "$PLAIN" 2>&1)"
t "escort on a bare tree still exits 0" "$?" "0"
has "an ungit engine says so honestly" "$OUT" "unknown (not a git repo here)"
has "no plugin.json is stated, never guessed" "$OUT" "unknown (no plugin.json read)"
has "no instruments is stated, never promised" "$OUT" "none found in this engine"
python3 "$M" escort --room build --engine "$W/nope" >/dev/null 2>&1
t "escort on a missing engine exits 2" "$?" "2"
mkdir -p "$W/out"
python3 "$M" escort --room build --engine "$E" --out "$W/out/escort.txt" >/dev/null 2>&1
t "--out <path> exits 0" "$?" "0"
t "--out <path> wrote the file the operator named" \
  "$([ -s "$W/out/escort.txt" ] && echo yes || echo no)" "yes"

# ── C · checkpoints ─────────────────────────────────────────────────────────────────
echo "── C · checkpoints (gated vs ungated, NEEDS states, malformed tolerated)"
p(){ python3 "$R" post build "$1" "$2" >/dev/null 2>&1; }
p bx "CHECKPOINT 1: seat oriented -> doctor exit 0, eval exit 0 | NEEDS: mentor-gate (build home)"
# the forward reference to CP5 is deliberate: it lands BEFORE CP5 exists, and a gate that
# counted it would be gating the future (section D re-checks CP5 is still ungated).
p mx "MENTOR GATE on CHECKPOINT 1: APPROVED, no hold. RIDERS: pin the engine hash. Numbering: the spike report arrives as CP5."
p bx "CHECKPOINT 2: auth tripwire fired, zero tokens billed | NEEDS: owner — run claude then /login"
p bx "CP3-AMENDMENT (drift absorbed): per-run binary stamps -> commit a733055 | NEEDS: nothing"
p bx "CHECKPOINT 4: plan posted; any raw-key demand = STOP + NEEDS: owner | NEEDS: mentor-gate on this plan"
p ox "just watching the room, no gate here"
printf 'a hand-pasted continuation line with no timestamp prefix\n' \
  >> "$CHATROOM_ROOT/build/room.md"

OUT="$(python3 "$M" checkpoints --room build 2>&1)"; RC=$?
t "exit 3 while any checkpoint is ungated" "$RC" "3"
has "the header counts the checkpoints" "$OUT" "4 checkpoint(s)"
has "CP1 is GATED by the mentor with its verdict" "$OUT" "CP 1 [CHECKPOINT] @bx"
has "the gate names the mentor and the verdict" "$OUT" "GATED by @mx APPROVED"
has "riders on a gate are surfaced" "$OUT" "+RIDERS"
has "CP1 what parsed from the format" "$OUT" "what: seat oriented"
has "CP1 evidence parsed from the format" "$OUT" "evidence: doctor exit 0, eval exit 0"
has "CP2 is ungated" "$OUT" "CP 2 [CHECKPOINT] @bx"
has "CP2 carries NEEDS: owner" "$OUT" "NEEDS: owner"
has "a checkpoint with no -> says the evidence is unstated" "$OUT" "evidence: (unstated"
has "an amendment keeps its tag" "$OUT" "CP 3 [AMENDMENT]"
has "a NEEDS: nothing post owes no gate" "$OUT" "UNGATED-INFO (declared NEEDS: nothing)"
has "the pipe-anchored NEEDS wins over a mid-body mention" "$OUT" \
    "CP 4 [CHECKPOINT] @bx"
has "the ungated list is the mentor's worklist" "$OUT" "UNGATED: CP 2, CP 4"
has "open owner escalations are listed" "$OUT" "OPEN NEEDS:owner: CP 2"
hasnt "a plain chat line is not a checkpoint" "$OUT" "@ox"
hasnt "a hand-pasted line with no prefix did not become a checkpoint" "$OUT" \
      "hand-pasted continuation"

python3 - "$M" <<'PY'
import json, subprocess, sys
out = subprocess.run([sys.executable, sys.argv[1], "checkpoints", "--room", "build",
                      "--json"], text=True, stdout=subprocess.PIPE)
d = json.loads(out.stdout)
def t(label, got, want):
    print(("  PASS  %s (%s)" % (label, got)) if got == want
          else ("  FAIL  %s — expected [%s] got [%s]" % (label, want, got)))
    return got == want
res = [t("--json is valid JSON with every checkpoint", len(d["checkpoints"]), 4),
       t("--json exit code still signals ungated", out.returncode, 3),
       t("--json ungated list", d["ungated"], [2, 4]),
       t("--json informational list", d["ungated_info"], [3]),
       t("--json roles resolved from the charter", (d["mentor"], d["builder"]), ("mx", "bx")),
       t("--json role source is the charter", d["roles_from"], "charter"),
       t("--json CP4 NEEDS is the declaration, not the mid-body prose",
         d["checkpoints"][3]["needs"], "mentor-gate"),
       t("--json keeps CP4's what verbatim (untruncated)",
         "STOP + NEEDS: owner" in d["checkpoints"][3]["what"], True),
       t("--json gate verdict", d["checkpoints"][0]["gate"]["verdict"], "APPROVED")]
sys.exit(0 if all(res) else 1)
PY
JRC=$?
if [ "$JRC" -eq 0 ]; then PASS=$((PASS+9)); else FAIL=$((FAIL+1)); fi

p mx "MENTOR GATE on CP2: APPROVED — owner action relayed."
p mx "MENTOR GATE on CP4: GREEN, T2 cleared."
python3 "$M" checkpoints --room build >/dev/null 2>&1
t "exit 0 once every owing checkpoint is gated" "$?" "0"
python3 "$M" charter --room quiet --mentor mx --builder bx >/dev/null 2>&1
OUT="$(python3 "$M" checkpoints --room quiet 2>&1)"; t "a chartered-but-quiet room exits 0" "$?" "0"
has "a quiet room reports zero checkpoints" "$OUT" "0 checkpoint(s)"
OUT="$(python3 "$M" checkpoints --room ghost 2>&1)"; t "a missing room exits 2" "$?" "2"
has "the missing-room message names the room" "$OUT" "ghost"
t "a missing room was NOT created by asking about it" \
  "$([ -d "$CHATROOM_ROOT/ghost" ] && echo created || echo absent)" "absent"
MENTOR_ROOM_PY="$W/nope.py" python3 "$M" checkpoints --room build >/dev/null 2>&1
t "no room.py = exit 2, never a reimplementation" "$?" "2"

# ── D · status ──────────────────────────────────────────────────────────────────────
echo "── D · status (one line a scheduler can read)"
p bx "CHECKPOINT 5: shell built -> fixture 60/0 | NEEDS: owner — approve the port"
CPS="$(python3 "$M" checkpoints --room build 2>&1)"; RC=$?
t "a forward reference made before CP5 existed never gated it (order rule)" "$RC" "3"
hasnt "CP5 carries no gate from the earlier mention" \
      "$(printf '%s\n' "$CPS" | grep -m1 '^CP 5 ')" "GATED by"
OUT="$(python3 "$M" status --room build 2>&1)"; t "status exits 0" "$?" "0"
t "status is exactly one line" "$(printf '%s\n' "$OUT" | wc -l | tr -d ' ')" "1"
has "status counts the checkpoints" "$OUT" "5 checkpoint(s)"
has "status names what is ungated" "$OUT" "1 ungated (CP 5)"
has "status counts the informational posts" "$OUT" "1 informational"
has "status reports the last activity" "$OUT" "last activity"
has "status names the open owner escalation" "$OUT" "NEEDS:owner open: CP 5"
OUT="$(python3 "$M" status --room quiet 2>&1)"
has "a quiet room says so without inventing state" "$OUT" "0 checkpoint(s)"
has "no owner item is stated plainly" "$OUT" "no open NEEDS:owner"

# ── E · the no-writes law ───────────────────────────────────────────────────────────
echo "── E · nothing is written outside the room"
python3 "$M" escort --room build --engine "$E" >/dev/null 2>&1
python3 "$M" checkpoints --room build >/dev/null 2>&1
python3 "$M" status --room build >/dev/null 2>&1
t "every command since the refused charter wrote nothing outside the room" \
  "$(outside)" "$BEFORE_OUT"
t "the engine tree is byte-identical after every command" "$(manifest "$E")" "$BEFORE_ENGINE"

echo
echo "mentor fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
