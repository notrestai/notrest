#!/usr/bin/env bash
# pretool-fixture — pipes real PreToolUse payloads through hooks/pretool-gate.sh and
# asserts the harness's first HARD gate: the two rules BLOCK (exit 2 + a deny decision
# on stdout + the reason on stderr), everything else is allowed silently and fast.
# Exit 0 = every assertion held. No network, no model calls, no writes to this repo
# (rule 1 is proven against a scratch git repo with stub instruments).

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── THE ACCESS KEY (4.8). The harness only runs where the owner minted a key, so this
# fixture mints its own and runs a KEYED COPY of the hooks: the committed keyring holds
# the owner's hashes, which a fixture must never need (or be able) to add to. Same bytes
# (cp -p), plus a keyring the verifier will find at <plugin>/.access/keys.sha256.
NRK_WORK="$(mktemp -d)"
NRK_KEY="fixture-access-key-$$-$RANDOM"
NRK_SHA="$(printf '%s' "$NRK_KEY" | python3 -c 'import hashlib,sys;sys.stdout.write(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"
mkdir -p "$NRK_WORK/plug/.access" "$NRK_WORK/home"
cp -Rp "$SD/../../../hooks" "$NRK_WORK/plug/hooks"
printf '# fixture keyring\n%s:fixture:2026-09-06\n' "$NRK_SHA" > "$NRK_WORK/plug/.access/keys.sha256"
mkdir -p "$NRK_WORK/plug/skills/atlas/scripts"
cp -p "$SD/../../../skills/atlas/scripts/atlas.py" "$NRK_WORK/plug/skills/atlas/scripts/atlas.py" 2>/dev/null
export NOTREST_ACCESS_KEY="$NRK_KEY"
export NOTREST_HOME="$NRK_WORK/home"
NRK_HOOKS="$NRK_WORK/plug/hooks"
trap 'rm -rf "$NRK_WORK"' EXIT
GATE="$SD/../../../hooks/pretool-gate.sh"
PASS=0
FAIL=0

[ -f "$GATE" ] || { echo "FATAL: missing $GATE"; exit 9; }

ok() { PASS=$((PASS+1)); echo "PASS  $1"; }
no() { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }
bad() { no "$1" "${2:-}"; }
# chk <label> <want> <got> — the spawn-gate section's exit-code comparator.
chk() { if [ "$2" = "$3" ]; then ok "$1 ($3)"; else no "$1" "want exit $2, got $3"; fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The harness hands the hook a PreToolUse payload on stdin. Built with python3 so no
# command string can be mangled by quoting on the way in.
payload() { # payload <command> <cwd> [tool_name]
  python3 -c 'import json, sys
print(json.dumps({"session_id": "pretool-fixture", "hook_event_name": "PreToolUse",
                  "transcript_path": "/Users/x/.claude/projects/oracle-suite-plugin/t.jsonl",
                  "permission_mode": "default", "cwd": sys.argv[2],
                  "tool_name": sys.argv[3] if len(sys.argv) > 3 else "Bash",
                  "tool_input": {"command": sys.argv[1], "description": "fixture"},
                  "tool_use_id": "toolu_fixture"}))' "$1" "$2" ${3:+"$3"}
}

# fire <command> <cwd> [tool_name] -> sets RC / OUT / ERRTXT. OVERRIDE_ENV=1 puts the
# override in the HOOK's environment (the other form is written into the command).
fire() {
  payload "$1" "$2" ${3:+"$3"} > "$TMP/in.json"
  if [ "${OVERRIDE_ENV:-}" = "1" ]; then
    NOTREST_GATE_OVERRIDE=1 bash "$GATE" < "$TMP/in.json" > "$TMP/out" 2> "$TMP/err"
  else
    bash "$GATE" < "$TMP/in.json" > "$TMP/out" 2> "$TMP/err"
  fi
  RC=$?
  OUT="$(cat "$TMP/out")"
  ERRTXT="$(cat "$TMP/err")"
}

# allows <label> <command> [cwd] — exit 0 AND silent on both streams.
allows() {
  fire "$2" "${3:-$TMP}"
  if [ "$RC" -ne 0 ]; then no "$1 -> allow" "exit $RC"
  elif [ -n "$ERRTXT" ] || [ -n "$OUT" ]; then no "$1 -> allow silently" "said: ${ERRTXT}${OUT}"
  else ok "$1 -> allow (silent, exit 0)"; fi
}

# allows_noisy <label> <expected-stderr-substring> <command> [cwd] — exit 0, but the gate
# SAYS something. A warning that is swallowed is a warning that does not exist, so the
# WARN-grade path must be audibly allowed rather than silently allowed.
allows_noisy() {
  fire "$3" "${4:-$TMP}"
  if [ "$RC" -ne 0 ]; then no "$1 -> allow" "exit $RC"
  elif ! printf '%s' "$ERRTXT" | grep -qF "$2"; then no "$1 -> allow with notice" "stderr: $ERRTXT"
  else ok "$1 -> allow, notice printed (exit 0)"; fi
}

# blocks <label> <expected-stderr-substring> <command> [cwd] — exit 2, the reason on
# stderr, and a schema-valid deny in the PreToolUse decision channel on stdout.
blocks() {
  fire "$3" "${4:-$TMP}"
  if [ "$RC" -ne 2 ]; then no "$1 -> BLOCK" "exit $RC (want 2), stderr: ${ERRTXT:-<none>}"; return; fi
  case "$ERRTXT" in
    *"$2"*) ;;
    *) no "$1 -> reason on stderr" "want *${2}*, got: ${ERRTXT:-<none>}"; return ;;
  esac
  verdict="$(printf '%s' "$OUT" | python3 -c 'import sys, json
try:
    h = json.load(sys.stdin).get("hookSpecificOutput") or {}
except Exception:
    print("UNPARSEABLE"); raise SystemExit
print("%s|%s|%s" % (h.get("hookEventName"), h.get("permissionDecision"),
                    "reason" if h.get("permissionDecisionReason") else "NOREASON"))' 2>/dev/null)"
  if [ "$verdict" = "PreToolUse|deny|reason" ]; then
    ok "$1 -> BLOCK (exit 2 + deny decision + reason)"
  else
    no "$1 -> deny decision on stdout" "got: ${verdict:-<no json>}"
  fi
}

# overridden <label> <command> [cwd] — allowed, but never silently.
overridden() {
  fire "$2" "${3:-$TMP}"
  if [ "$RC" -ne 0 ]; then no "$1 -> override allows" "exit $RC"
  elif [ "${ERRTXT#*GATE OVERRIDDEN}" = "$ERRTXT" ]; then
    no "$1 -> override announces itself" "stderr: ${ERRTXT:-<silent>}"
  else ok "$1 -> allowed, override announced"; fi
}

# ---------------------------------------------------------------- scratch repos
# RED: instruments exit 6 (FAIL) — the shape the gate must refuse to push. WARNR:
# exit 5 (WARN) — reported, never blocked (2026-07-27: doctor warns about ANOTHER app's
# store with no CLI remedy, so blocking on 5 would block every push forever). GREEN: the same repo with both instruments exiting 0.
# PLAIN: a git repo that ships no instruments — every other repo on the machine.
mkrepo() { # mkrepo <dir> <doctor-exit> <eval-exit>
  mkdir -p "$1/plugins/notrest/skills/doctor/scripts" "$1/plugins/notrest/skills/eval/scripts"
  printf 'import sys\nsys.exit(%s)\n' "$2" > "$1/plugins/notrest/skills/doctor/scripts/doctor.py"
  printf 'import sys\nsys.exit(%s)\n' "$3" > "$1/plugins/notrest/skills/eval/scripts/eval.py"
  git -C "$1" init -q 2>/dev/null || git -C "$1" init 2>/dev/null >/dev/null
}
RED="$TMP/red";     mkdir -p "$RED";   mkrepo "$RED" 6 0     # FAIL-grade: the ship blocker
WARNR="$TMP/warn";  mkdir -p "$WARNR"; mkrepo "$WARNR" 5 0     # WARN-grade: notice, never a block
GREEN="$TMP/green"; mkdir -p "$GREEN"; mkrepo "$GREEN" 0 0
BOTHRED="$TMP/both"; mkdir -p "$BOTHRED"; mkrepo "$BOTHRED" 6 6
PLAIN="$TMP/plain"; mkdir -p "$PLAIN"; git -C "$PLAIN" init -q 2>/dev/null
NOGIT="$TMP/nogit"; mkdir -p "$NOGIT"

echo "── miss path (the gate runs on EVERY Bash call — these must cost nothing)"
allows "plain ls"                "ls -la"
allows "git status"              "git status --short"
allows "git pushup (word-bound)" "git pushup --now"
allows "the word push alone"     "make push-images"
allows "a repo path with plugin" "grep -rn foo plugins/notrest/skills/ | head"
allows "docs quoting the flow"   "grep -n 'claude plugin update' CLAUDE.md"

echo "── RULE 2 · shadow guard (any cwd — the incident came from outside the repo)"
blocks "plugin update notrest"   "SHADOW GUARD" "claude plugin update notrest@notrest"
blocks "plugin install notrest"  "SHADOW GUARD" "claude plugin install notrest@notrest"
blocks "marketplace add notrest" "SHADOW GUARD" "claude plugin marketplace add notrest"
blocks "marketplace add ORACLE"  "SHADOW GUARD" "claude plugin marketplace add ./oracle-suite-plugin"
blocks "the full consumer flow"  "SHADOW GUARD" "claude plugin marketplace update notrest && claude plugin update notrest@notrest"
blocks "shadow guard from ~"     "SHADOW GUARD" "claude plugin update notrest@notrest" "$HOME"
allows "plugin list"             "claude plugin list"
allows "uninstall (the remedy)"  "claude plugin uninstall notrest@notrest"
allows "marketplace remove"      "claude plugin marketplace remove notrest"
allows "marketplace update only" "claude plugin marketplace update notrest"
allows "another plugin entirely" "claude plugin update someone-else@theirs"

echo "── RULE 1 · ship gate (this harness repo only)"
blocks "push, doctor FAIL"       "notrest ship gate: doctor=6 eval=0" "git push origin main" "$RED"
blocks "push, both red"          "notrest ship gate: doctor=6 eval=6" "git push --force"     "$BOTHRED"
blocks "push names the escape"   "NOTREST_GATE_OVERRIDE=1"            "git push"             "$RED"
allows_noisy "push, doctor WARN only" "warnings present (doctor=5 eval=0)" "git push origin main" "$WARNR"
allows "push, gate green"        "git push origin main"  "$GREEN"
allows "push, no instruments"    "git push origin main"  "$PLAIN"
allows "push, not a git repo"    "git push origin main"  "$NOGIT"
allows "push in a chain, green"  "git commit -m wip && git push" "$GREEN"
allows "git pushup in harness"   "git pushup" "$RED"

echo "── the escape hatch (a hard gate must never strand the owner)"
overridden "inline override, ship gate"   "NOTREST_GATE_OVERRIDE=1 git push origin main" "$RED"
overridden "inline override, shadow"      "NOTREST_GATE_OVERRIDE=1 claude plugin update notrest@notrest"
OVERRIDE_ENV=1 overridden "env override, ship gate" "git push origin main" "$RED"
OVERRIDE_ENV=1 overridden "env override, shadow"    "claude plugin update notrest@notrest"
unset OVERRIDE_ENV

echo "── fail-open (a broken gate must never brick the machine)"
out="$(printf 'not json at all' | bash "$GATE" 2>&1)"; rc=$?
if [ "$rc" -eq 0 ] && [ -z "$out" ]; then ok "garbage stdin -> allow, exit 0"
else no "garbage stdin -> allow, exit 0" "exit $rc, said: $out"; fi
out="$(printf '' | bash "$GATE" 2>&1)"; rc=$?
if [ "$rc" -eq 0 ] && [ -z "$out" ]; then ok "empty stdin -> allow, exit 0"
else no "empty stdin -> allow, exit 0" "exit $rc, said: $out"; fi
out="$(printf '{"tool_name":"Bash","tool_input":{"command":"git push"}' | bash "$GATE" 2>&1)"; rc=$?
if [ "$rc" -eq 0 ] && [ -z "$out" ]; then ok "truncated JSON -> allow, exit 0"
else no "truncated JSON -> allow, exit 0" "exit $rc, said: $out"; fi
out="$(printf '{"hook_event_name":"PreToolUse","tool_name":"Bash"}' | bash "$GATE" 2>&1)"; rc=$?
if [ "$rc" -eq 0 ] && [ -z "$out" ]; then ok "no tool_input -> allow, exit 0"
else no "no tool_input -> allow, exit 0" "exit $rc, said: $out"; fi

echo "── wrong tool (the matcher says Bash; the hook must not trust it alone)"
fire "claude plugin update notrest@notrest" "$TMP" "Edit"
if [ "$RC" -eq 0 ] && [ -z "$ERRTXT" ]; then ok "non-Bash tool -> allow (matcher belt+braces)"
else no "non-Bash tool -> allow" "exit $RC, stderr: $ERRTXT"; fi

echo "── budget (this is on the critical path of every Bash call)"
payload "grep -rn foo plugins/notrest/skills/ | head -20" "$PWD" > "$TMP/miss.json"
START="$(python3 -c 'import time; print(time.time())')"
for _ in $(seq 1 20); do bash "$GATE" < "$TMP/miss.json" >/dev/null 2>&1; done
PER="$(python3 -c 'import sys, time; print("%.1f" % ((time.time() - float(sys.argv[1])) * 50))' "$START")"
if python3 -c 'import sys; raise SystemExit(0 if float(sys.argv[1]) < 100 else 1)' "$PER"; then
  ok "miss path ${PER} ms/call (< 100 ms bound)"
else
  no "miss path under 100 ms/call" "measured ${PER} ms/call"
fi


echo "── the SPAWN GATE: the offload law, enforced in code ────────────────────"
# Adopted from cloudflare-os (Apache 2.0): pin the child's model IN CODE instead of
# asking the parent to remember. Payload shape verified against 87 real spawns in this
# repo's own transcripts before the gate was written — tool_name "Agent" here, "Task"
# on other surfaces, tool_input {description, model, prompt, subagent_type}.
SG="$NRK_HOOKS/spawn-gate.sh"

# spawn <tool> <model|-> <subagent_type|-> → the gate's exit code.
#
# THE PAYLOAD IS BUILT BY python3, NOT BY STRING CONCATENATION (2026-09-01). The old
# form was `sp x "{$AGENT,\"tool_input\":{\"model\":\"haiku\"…}}"` nested inside a
# command substitution, and bash re-parsed the escaped quotes at the outer layer,
# leaving the braces unquoted: `bash -x` shows the hook actually receiving
# `"tool_input":"model":"haiku"`. The gate then correctly ignored a payload that was no
# longer a spawn and exited 0 — so five assertions about the offload law were being
# satisfied by a mangled payload rather than by the law. (`chk` and `bad` were also
# undefined, so even the mismatch printed "command not found" and the fixture reported
# "0 failed". Two vacuous-pass layers over the same block.)
spawn(){
  python3 -c 'import json, sys
ti = {"description": "lane"}
if sys.argv[2] != "-": ti["model"] = sys.argv[2]
if sys.argv[3] != "-": ti["subagent_type"] = sys.argv[3]
print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": sys.argv[1],
                  "tool_input": ti}))' "$1" "$2" "$3" | bash "$SG" >/dev/null 2>&1
  echo $?
}
# The payload builder must itself be proven, or the arms below are trusting the very
# layer that failed last time.
PROBE="$(python3 -c 'import json, sys
ti = {"description": "lane"}
ti["model"] = "haiku"
print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Agent",
                  "tool_input": ti}))')"
case "$PROBE" in
  *'"tool_input": {"description": "lane", "model": "haiku"}'*)
      ok "spawn payloads reach the gate intact (no brace-expansion mangling)" ;;
  *)  no "spawn payload builder is mangling the JSON" "$PROBE" ;;
esac

chk "spawn gate: explicit opus PASSES" 0 "$(spawn Agent opus general-purpose)"
chk "spawn gate: model OMITTED is blocked (not a default)" 2 "$(spawn Agent - general-purpose)"
chk "spawn gate: explicit sonnet PASSES (owner-amended 2026-08-30)" 0 "$(spawn Agent sonnet -)"
chk "spawn gate: haiku is blocked" 2 "$(spawn Agent haiku -)"
chk "spawn gate: fork is blocked even WITH opus" 2 "$(spawn Agent opus fork)"
chk "spawn gate: the Task spelling is gated too" 2 "$(spawn Task haiku -)"
chk "spawn gate: non-spawn tools are untouched" 0 \
  "$(printf '%s' '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | bash "$SG" >/dev/null 2>&1; echo $?)"
chk "spawn gate: malformed payload passes through silently" 0 \
  "$(printf '%s' 'not json at all{' | bash "$SG" >/dev/null 2>&1; echo $?)"
chk "spawn gate: empty stdin passes through silently" 0 "$(printf '' | bash "$SG" >/dev/null 2>&1; echo $?)"

# ── 4.7.0 · AN UNATTENDED RUN DOES NOT FAN OUT. NOTREST_UNATTENDED=1 marks a session
# with nobody at the keyboard: a lane spawned there has no reader and no owner for its
# spend. Refused before the model rules, because no model is lawful here.
UOUT="$(printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"description":"lane","model":"opus","subagent_type":"general-purpose","prompt":"x"}}' \
        | NOTREST_UNATTENDED=1 bash "$SG" 2>&1 >/dev/null; )"
URC="$(printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"description":"lane","model":"opus","subagent_type":"general-purpose","prompt":"x"}}' \
        | NOTREST_UNATTENDED=1 bash "$SG" >/dev/null 2>&1; echo $?)"
case "$URC:$UOUT" in
  2:*"unattended runs do not fan out — one runner, one lane"*)
      ok "spawn gate: an unattended run is refused a lane, with the exact reason" ;;
  *)  no "spawn gate: an unattended run is refused a lane" "rc=$URC msg=$(printf '%s' "$UOUT" | head -c 90)" ;;
esac
UOUT="$(printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"description":"lane","model":"opus","subagent_type":"general-purpose","prompt":"x"}}' \
        | NOTREST_UNATTENDED=1 NOTREST_GATE_OVERRIDE=1 bash "$SG" 2>&1 >/dev/null)"
URC="$(printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"description":"lane","model":"opus","subagent_type":"general-purpose","prompt":"x"}}' \
        | NOTREST_UNATTENDED=1 NOTREST_GATE_OVERRIDE=1 bash "$SG" >/dev/null 2>&1; echo $?)"
case "$URC:$UOUT" in
  0:*"OVERRIDDEN"*) ok "spawn gate: the unattended ban is overridable, and says so out loud" ;;
  *) no "spawn gate: the unattended ban is overridable and loud" "rc=$URC msg=$(printf '%s' "$UOUT" | head -c 90)" ;;
esac
chk "spawn gate: an ATTENDED lawful lane is untouched by the unattended rule" 0 "$(spawn Agent opus general-purpose)"

# ── 4.6.3 · THE DIGEST NEVER TOUCHES A REFUSAL. spawn-gate may rewrite the Agent prompt
# (hookSpecificOutput.updatedInput) for a LAWFUL lane only. A denied call must come back
# byte-for-byte as it did in 4.6.2: exit 2, the reason on stderr, the deny decision on
# stdout, and nothing that could be read as an input rewrite.
inj(){   # inj <tool> <model|-> <subagent_type|-> -> the gate's stdout
  python3 -c 'import json, sys
ti = {"description": "lane", "prompt": "fix plugins/notrest/hooks/router.sh"}
if sys.argv[2] != "-": ti["model"] = sys.argv[2]
if sys.argv[3] != "-": ti["subagent_type"] = sys.argv[3]
print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": sys.argv[1],
                  "tool_input": ti}))' "$1" "$2" "$3" | bash "$SG" 2>/dev/null
}
for spec in "haiku:-" "-:general-purpose" "opus:fork"; do
  M="${spec%%:*}"; ST="${spec##*:}"
  OUT="$(inj Agent "$M" "$ST")"
  case "$OUT" in
    *updatedInput*) no "spawn gate: a DENIED call (model=$M type=$ST) is never rewritten" "deny carried updatedInput" ;;
    *'"permissionDecision": "deny"'*) ok "spawn gate: a DENIED call (model=$M type=$ST) carries the deny and no updatedInput" ;;
    *) no "spawn gate: a denied call still denies (model=$M type=$ST)" "got: ${OUT:-<silent>}" ;;
  esac
done
# A lawful lane OUTSIDE any estate has no store to read and must stay exactly as silent
# as it was before the digest existed.
NOEST_DIR="$(mktemp -d)"
OUT="$(cd "$NOEST_DIR" && inj Agent opus general-purpose)"
if [ -z "$OUT" ]; then ok "spawn gate: a lawful lane outside any estate stays silent (no digest, no output)"
else no "spawn gate: lawful lane outside an estate stays silent" "got: $(printf '%s' "$OUT" | head -c 90)"; fi
rm -rf "$NOEST_DIR"

# The escape hatch exists AND is loud — a bypassed gate that says nothing is worse than none.
# haiku, not sonnet: sonnet became lawful on 2026-08-30, so a sonnet spawn would exercise
# the ALLOW path and prove nothing about the override.
HAIKU="$(python3 -c 'import json
print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Agent",
                  "tool_input": {"model": "haiku", "description": "lane"}}))')"
OUT="$(printf '%s' "$HAIKU" | NOTREST_GATE_OVERRIDE=1 bash "$SG" 2>&1)"
RC=$?
chk "spawn gate: override permits the spawn" 0 "$RC"
case "$OUT" in
  *OVERRIDDEN*) ok "spawn gate: the override announces itself" ;;
  *) bad "spawn gate: the override was SILENT — that is worse than no gate" ;;
esac
# a blocked spawn must state the law and the fix, not just refuse
OUT2="$(printf '%s' "$HAIKU" | bash "$SG" 2>&1)"
case "$OUT2" in
  *'model="opus"'*) ok "spawn gate: the refusal names the fix" ;;
  *) bad "spawn gate: the refusal does not name the fix" ;;
esac
case "$OUT2" in
  *permissionDecision*deny*) ok "spawn gate: emits a real PreToolUse deny decision" ;;
  *) bad "spawn gate: no deny decision in the hook output" ;;
esac
# and it must be registered, or it never runs
HJ="$(cd "$(dirname "$0")/../../../hooks" && pwd)/hooks.json"
if grep -q 'spawn-gate.sh' "$HJ" && grep -q 'Agent|Task' "$HJ"; then
  ok "spawn gate: registered under PreToolUse with the Agent|Task matcher"
else
  bad "spawn gate: not registered in hooks.json — it would never fire"
fi

echo "── COMMISSION GATES: done-when prose turned into mechanism (docket 8a/8b) ─"
# unlazy-inspired (leonxlnx/unlazy, owner-pointed 2026-09-01). A commission in briefs/
# may carry executable CHECK:/EXPECT: blocks; gate-check.py RUNS them and records
# EVIDENCE, and a Stop hook refuses a "done" claim while a declared gate is red. The
# vacuous-pass killer applied to the CLAIM, not only to the ship.
HD="$NRK_HOOKS"
GC="$HD/gate-check.py"
CG="$HD/completion-gate.sh"
GW="$TMP/gates"; mkdir -p "$GW"

# Every gate-check invocation is run under an OUTER `timeout`, on purpose: RB-2's red
# state was an UNBOUNDED spin inside re.search, and a fixture that hangs instead of
# failing is a fixture nobody can watch go red. 124 here means "did not return", which
# is a failure like any other.
gcrun(){ timeout 20 python3 "$GC" "$@" > "$TMP/gc.out" 2> "$TMP/gc.err"; echo $?; }
gchas(){ if grep -qF -- "$2" "$TMP/gc.out" 2>/dev/null; then ok "$1"; \
         else no "$1" "not in output: $2"; fi; }

# ── all green ────────────────────────────────────────────────────────────────
cat > "$GW/green.md" <<'GEOF'
# commission — lane B

Do the thing.

CHECK: printf 'ALL TESTS PASS\n'
EXPECT: ALL TESTS PASS

CHECK: true
GEOF
chk "gate-check: every CHECK green → exit 0" 0 "$(gcrun "$GW/green.md")"
gchas "gate-check: names each gate it ran" "printf 'ALL TESTS PASS"
gchas "gate-check: a CHECK with no EXPECT passes on exit 0 alone" "CHECK : true"
gchas "gate-check: records the exit code as evidence" "exit=0"
GSHA="$(printf 'ALL TESTS PASS\n' | shasum -a 256 | cut -d' ' -f1)"
gchas "gate-check: EVIDENCE fingerprints the output (sha256)" "outsha=$GSHA"
gchas "gate-check: records the shell + PATH it resolved (docket 8d)" "shell="
gchas "gate-check: reports the gate count" "2 gates"

# ── a red CHECK: nonzero exit ────────────────────────────────────────────────
cat > "$GW/red-exit.md" <<'GEOF'
CHECK: printf 'boom\n'; exit 3
EXPECT: boom
GEOF
chk "gate-check: a nonzero CHECK → exit 5" 5 "$(gcrun "$GW/red-exit.md")"
gchas "gate-check: the red gate is named, not merely counted" "exit=3"
gchas "gate-check: says which gates are red" "RED"

# ── a red EXPECT: the command succeeded but said the wrong thing ─────────────
cat > "$GW/red-expect.md" <<'GEOF'
CHECK: printf 'tests: 3 passed, 1 failed\n'
EXPECT: 0 failed
GEOF
chk "gate-check: exit 0 but EXPECT unmatched → exit 5" 5 "$(gcrun "$GW/red-expect.md")"
gchas "gate-check: an unmatched EXPECT is reported as such" "EXPECT"

# ── a fenced EXAMPLE is documentation, not a gate ────────────────────────────
cat > "$GW/fenced.md" <<'GEOF'
Write your gates like this:

```
CHECK: exit 9
EXPECT: never runs
```

CHECK: true
GEOF
chk "gate-check: fenced examples are NOT executed" 0 "$(gcrun "$GW/fenced.md")"
gchas "gate-check: …and only the real gate is counted" "1 gates"

# ── degenerate inputs ────────────────────────────────────────────────────────
# RB-1 (refuter, HIGH, 2026-09-01 — seat ruling): a gates file that EXISTS but yields
# ZERO parsed gates is a PARSE FAILURE, not an empty intent. The file's existence IS the
# estate's declaration that it has a contract; "I found nothing in your contract" must
# never be reported as "your contract is satisfied". Absence of the file stays the only
# silent-green path, and it lives in the hook, not here.
printf '# a commission with no gates at all\n' > "$GW/none.md"
chk "gate-check: an EXISTING file with zero parsed gates → exit 3, never a green" 3 \
  "$(gcrun "$GW/none.md")"
# Review round (2026-09-01): a clean parse with nothing armed gets a TRUE sentence —
# "declares no gate" — never "unreadable", which was a false statement about that file.
gchas "gate-check: …and calls it what it is (a contract with no gate armed)" "CONTRACT DECLARES NO GATE"
gchas "gate-check: …telling the author the remedy" "arm a CHECK: or delete the file"

# The vacuous-green that started it: an unterminated fence swallowed every gate below it
# and gate-check said "0 gates, 0 red" — exit 0 — while the estate's real `CHECK: false`
# sat inside the swallowed region. Repro from the refuter's matrix.sh (C10).
printf '```\nCHECK: echo example\nGATE: the real one\nCHECK: false\n' > "$GW/unclosed.md"
chk "gate-check: an UNTERMINATED fence is a parse failure (exit 3)" 3 "$(gcrun "$GW/unclosed.md")"
gchas "gate-check: …naming the line the fence opened on" "line 1"
gchas "gate-check: …and saying gates were swallowed, not that there were none" "swallow"

# Review round (2026-09-01): N × --timeout blew past the harness's 60s Stop cap and a
# hook killed mid-verdict FAILS OPEN — so gate-check gains a wall-clock budget across
# ALL gates, and a gate the budget cannot reach is RED, never skipped.
printf 'GATE: g1\nCHECK: sleep 4\nGATE: g2\nCHECK: sleep 4\nGATE: g3\nCHECK: echo never-reached\n' > "$GW/slow.md"
T0=$(date +%s)
chk "gate-check: --budget bounds the WHOLE run and reds the unreached" 5 \
  "$(gcrun "$GW/slow.md" --budget 6)"
T1=$(date +%s)
gchas "gate-check: …the unreached gate says exactly why it is red" "wall-clock budget exhausted"
if [ $((T1-T0)) -le 12 ]; then ok "gate-check: budget honoured in wall-clock ($((T1-T0))s ≤ 12s)"; else no "gate-check: budget honoured in wall-clock" "took $((T1-T0))s"; fi
# the same file, one CHECK, properly fenced-and-closed: still a real gate below it
printf '```\nCHECK: echo example\n```\n\nCHECK: true\n' > "$GW/closed.md"
chk "gate-check: a CLOSED fence still yields the real gate below it" 0 "$(gcrun "$GW/closed.md")"
chk "gate-check: a missing file → exit 2 (usage), never a false green" 2 \
  "$(gcrun "$GW/nope.md")"
chk "gate-check: --json on a red file still exits 5" 5 "$(gcrun "$GW/red-exit.md" --json)"
if python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))
raise SystemExit(0 if d["red"] == 1 and d["gates"][0]["exit"] == 3
                 and d["gates"][0]["outsha"] and "PATH" in d["env"] else 1)' "$TMP/gc.out"; then
  ok "gate-check: --json carries gates[], exits, fingerprints and the env"
else
  no "gate-check: --json shape" "$(head -c 300 "$TMP/gc.out")"
fi

# ── the COMPLETION GATE (Stop hook) ──────────────────────────────────────────
# fire_stop <cwd> [stop_hook_active] -> SRC / SOUT / SERR
fire_stop(){
  python3 -c 'import json, sys
print(json.dumps({"session_id": "gatefix", "hook_event_name": "Stop",
                  "transcript_path": "/tmp/t.jsonl",
                  "stop_hook_active": sys.argv[1] == "1"}))' "${2:-0}" \
    | ( cd "$1" && bash "${CGBIN:-$CG}" ) > "$TMP/st.out" 2> "$TMP/st.err"
  SRC=$?
  SOUT="$(cat "$TMP/st.out")"; SERR="$(cat "$TMP/st.err")"
}

GE="$TMP/gate-estate"; mkdir -p "$GE/gates"; git -C "$GE" init -q 2>/dev/null
fire_stop "$GE"
chk "completion gate: no gates/ACTIVE.md → exit 0" 0 "$SRC"
if [ -z "$SOUT$SERR" ]; then ok "completion gate: …and is completely silent"
else no "completion gate: silent with no ACTIVE.md" "said: $SOUT$SERR"; fi

printf 'CHECK: true\nEXPECT: \n' > "$GE/gates/ACTIVE.md"
printf 'CHECK: printf %%s ok\nEXPECT: ok\n' > "$GE/gates/ACTIVE.md"
fire_stop "$GE"
chk "completion gate: all gates green → exit 0" 0 "$SRC"
if [ -z "$SOUT$SERR" ]; then ok "completion gate: …and stays silent on green"
else no "completion gate: silent on green" "said: $SOUT$SERR"; fi

printf 'CHECK: printf "the suite is red\\n"; exit 1\nEXPECT: the suite is red\n' \
  > "$GE/gates/ACTIVE.md"
fire_stop "$GE"
chk "completion gate: a RED gate refuses the completion claim (exit 2)" 2 "$SRC"
case "$SERR" in
  *"completion is not earned"*) ok "completion gate: says the claim is not earned" ;;
  *) no "completion gate: the refusal is not stated" "stderr: ${SERR:-<none>}" ;;
esac
case "$SERR" in
  *"the suite is red"*|*"exit=1"*) ok "completion gate: names the red gate, not just a count" ;;
  *) no "completion gate: red gate unnamed" "stderr: ${SERR:-<none>}" ;;
esac
DEC="$(printf '%s' "$SOUT" | python3 -c 'import sys, json
try: d = json.load(sys.stdin)
except Exception: print("UNPARSEABLE"); raise SystemExit
print("%s|%s" % (d.get("decision"), "reason" if d.get("reason") else "NOREASON"))' 2>/dev/null)"
chk "completion gate: emits a Stop decision block on stdout" "block|reason" "$DEC"

# THE LOOP GUARD: the harness re-runs Stop hooks after a block. A gate that blocks
# again forever wedges the session — stop_hook_active is the documented escape.
fire_stop "$GE" 1
chk "completion gate: stop_hook_active=true never blocks again (loop guard)" 0 "$SRC"

# The escape hatch, loud.
SRC=0; OUT_SAVE=""
printf '%s' '{"hook_event_name":"Stop","stop_hook_active":false}' \
  | ( cd "$GE" && NOTREST_GATE_OVERRIDE=1 bash "$CG" ) > "$TMP/st.out" 2> "$TMP/st.err"
chk "completion gate: override permits the stop" 0 "$?"
case "$(cat "$TMP/st.err")" in
  *OVERRIDDEN*) ok "completion gate: the override announces itself" ;;
  *) no "completion gate: the override was SILENT" "$(cat "$TMP/st.err")" ;;
esac

# FAIL-OPEN: a broken instrument must never wedge a session.
BH="$TMP/brokenhooks"; mkdir -p "$BH"
mkdir -p "$TMP/.access" "$TMP/skills/atlas/scripts"
cp -p "$NRK_WORK/plug/.access/keys.sha256" "$TMP/.access/keys.sha256" 2>/dev/null
cp -p "$NRK_WORK/plug/skills/atlas/scripts/atlas.py" "$TMP/skills/atlas/scripts/atlas.py" 2>/dev/null
cp "$CG" "$BH/" 2>/dev/null; cp "$HD/estate-root.sh" "$BH/" 2>/dev/null
CGBIN="$BH/completion-gate.sh" fire_stop "$GE"
chk "completion gate: a MISSING checker fails OPEN (exit 0)" 0 "$SRC"
case "$SERR" in
  *notrest*) ok "completion gate: …and says so on stderr rather than dying mute" ;;
  *) no "completion gate: a broken gate was silent" "stderr: ${SERR:-<none>}" ;;
esac
printf 'not json at all{' | ( cd "$GE" && bash "$CG" ) >/dev/null 2>&1
chk "completion gate: a malformed payload passes through (exit 0)" 0 "$?"
printf '%s' '{"hook_event_name":"Stop"}' | ( cd "$TMP" && bash "$CG" ) >/dev/null 2>&1
chk "completion gate: no estate root → exit 0, silent" 0 "$?"

# registration + the hook contract, or it never runs / breaks eval
if grep -q 'completion-gate.sh' "$HD/hooks.json" && \
   python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))
raise SystemExit(0 if any("completion-gate.sh" in h.get("command","")
                          for e in d["hooks"].get("Stop", []) for h in e["hooks"]) else 1)' \
     "$HD/hooks.json"; then
  ok "completion gate: registered under Stop in hooks.json"
else
  no "completion gate: not registered under Stop — it would never fire"
fi
if grep -qE '^\s*set -e' "$CG"; then
  no "completion gate: carries 'set -e' (eval HOOK-CONTRACT forbids it)"
else
  ok "completion gate: no set -e (eval HOOK-CONTRACT)"
fi
chk "completion gate: last statement is 'exit 0' (eval HOOK-CONTRACT)" "exit 0" \
  "$(grep -v '^[[:space:]]*$' "$CG" | tail -1 | sed 's/^[[:space:]]*//')"

echo "── refuter repair round RB-1b / RB-2 / RB-7 / RB-8 ──────────────────────"

# ── RB-1b: an UNREADABLE declared contract is a RED gate, not an absence. The hook
# used to fail open on any non-{0,5} checker code, so the unclosed-fence file above
# would have gone from "vacuously green" straight to "silently allowed".
printf '```\nCHECK: echo example\nCHECK: false\n' > "$GE/gates/ACTIVE.md"
fire_stop "$GE"
chk "completion gate: an unreadable contract BLOCKS (exit 2), never fails open" 2 "$SRC"
case "$SERR" in
  *"contract"*) ok "completion gate: the refusal says the contract could not be read" ;;
  *) no "completion gate: unreadable contract not explained" "stderr: ${SERR:-<none>}" ;;
esac
case "$SERR" in
  *"line 1"*) ok "completion gate: …and carries the parse detail through to the seat" ;;
  *) no "completion gate: parse detail dropped on the way out" "stderr: ${SERR:-<none>}" ;;
esac
DEC="$(printf '%s' "$SOUT" | python3 -c 'import sys, json
try: d = json.load(sys.stdin)
except Exception: print("UNPARSEABLE"); raise SystemExit
print(d.get("decision"))' 2>/dev/null)"
chk "completion gate: …and emits a real Stop decision block" "block" "$DEC"

# a checker that fails in some OTHER way is a malfunction, and a malfunction never blocks
CH="$TMP/crashhooks"; mkdir -p "$CH"
mkdir -p "$TMP/.access" "$TMP/skills/atlas/scripts"
cp -p "$NRK_WORK/plug/.access/keys.sha256" "$TMP/.access/keys.sha256" 2>/dev/null
cp -p "$NRK_WORK/plug/skills/atlas/scripts/atlas.py" "$TMP/skills/atlas/scripts/atlas.py" 2>/dev/null
cp "$CG" "$CH/"; cp "$HD/estate-root.sh" "$CH/"
printf '#!/usr/bin/env python3\nimport sys; sys.exit(9)\n' > "$CH/gate-check.py"
CGBIN="$CH/completion-gate.sh" fire_stop "$GE"
chk "completion gate: a CRASHING checker (exit 9) still fails OPEN" 0 "$SRC"
case "$SERR" in
  *"not a verdict"*) ok "completion gate: …and says the exit was not a verdict" ;;
  *) no "completion gate: crash was silent" "stderr: ${SERR:-<none>}" ;;
esac

# ── RB-2 (HIGH): a catastrophic EXPECT pattern used to spin forever inside re.search,
# with no timeout anywhere between it and the session — `timeout 15` had to kill the
# Stop hook. An EXPECT that cannot be decided is a RED gate, not a hang.
cat > "$GW/redos.md" <<'GEOF'
CHECK: printf %s aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
EXPECT: (a+)+b
GEOF
REDOS_T0="$(python3 -c 'import time; print(time.time())')"
REDOS_RC="$(gcrun "$GW/redos.md")"
REDOS_EL="$(python3 -c 'import sys, time; print("%.1f" % (time.time() - float(sys.argv[1])))' "$REDOS_T0")"
chk "gate-check: a catastrophic EXPECT is RED, not a hang (exit 5)" 5 "$REDOS_RC"
if python3 -c 'import sys; raise SystemExit(0 if float(sys.argv[1]) < 12 else 1)' "$REDOS_EL"; then
  ok "gate-check: …and it returns in ${REDOS_EL}s (bounded, was unbounded)"
else
  no "gate-check: the EXPECT guard did not bound the match" "took ${REDOS_EL}s"
fi
gchas "gate-check: …and says the pattern did not complete" "did not complete"
# and the whole chain is bounded: the hook caps the checker, the harness caps the hook
case "$(grep -c -- '--timeout' "$CG")" in
  0) no "completion gate: passes no --timeout to the checker (unbounded checker)" ;;
  *) ok "completion gate: passes an explicit --timeout to the checker" ;;
esac
# PLACEMENT, not merely presence (2026-09-01): this arm read the timeout off the matcher
# GROUP, which is where it sat from 4.5.0 — and the CLI reads `timeout` off the
# individual COMMAND object, so the outer cap was configured and never in effect while
# this fixture called it green. A group-level key is now the failure, not the pass.
if python3 -c 'import json,sys
d = json.load(open(sys.argv[1]))
groups = d["hooks"]["Stop"]
if any("timeout" in g for g in groups):
    raise SystemExit(1)   # on the group = parsed, shipped, not in effect
raise SystemExit(0 if any(int(h.get("timeout", 0)) > 0
                          for g in groups for h in g.get("hooks", [])) else 1)' "$HD/hooks.json"; then
  ok "completion gate: the Stop COMMAND carries a harness wall-clock timeout"
else
  no "completion gate: the Stop timeout is missing or sits on the matcher group (not in effect)"
fi

# ── RB-7: the two remaining fail-open paths were MUTE, and the file's own law says a
# gate that fails silently cannot be told apart from a gate that passed.
mkdir -p "$TMP/outside-gates"
printf 'CHECK: false\n' > "$TMP/outside-gates/EVIL.md"
rm -f "$GE/gates/ACTIVE.md"
ln -sf "$TMP/outside-gates/EVIL.md" "$GE/gates/ACTIVE.md"
fire_stop "$GE"
chk "completion gate: an ACTIVE.md escaping the estate is refused (exit 0)" 0 "$SRC"
case "$SERR" in
  *notrest*) ok "completion gate: …and says so rather than going mute" ;;
  *) no "completion gate: escaping ACTIVE.md was refused in silence" "stderr: ${SERR:-<none>}" ;;
esac
rm -f "$GE/gates/ACTIVE.md"

NOROOT="$TMP/norootgates"; mkdir -p "$NOROOT/gates"
printf 'CHECK: false\n' > "$NOROOT/gates/ACTIVE.md"
fire_stop "$NOROOT"
chk "completion gate: a declared contract with NO estate root fails open (exit 0)" 0 "$SRC"
case "$SERR" in
  *notrest*) ok "completion gate: …and says the contract could not be bound to an estate" ;;
  *) no "completion gate: unbindable contract was silent" "stderr: ${SERR:-<none>}" ;;
esac
# and a directory with no contract at all stays completely silent — silence is only
# wrong where something was declared.
fire_stop "$TMP"
chk "completion gate: no contract anywhere → exit 0" 0 "$SRC"
if [ -z "$SOUT$SERR" ]; then ok "completion gate: …and no note is invented for a plain directory"
else no "completion gate: noisy in a directory that declared nothing" "said: $SOUT$SERR"; fi

# ── RB-8: an unbounded CHECK could hand gate-check a 20 MB string (≈100 MB RSS
# measured) inside a Stop hook. Capture is capped; the sha is over the captured
# window, and the truncation is STATED — a fingerprint over a silently clipped
# window would be a fingerprint of something other than what it names.
printf 'CHECK: head -c 3000000 /dev/zero | tr "\\\\0" "z"; false\n' > "$GW/huge.md"
chk "gate-check: an oversized CHECK is still a verdict (exit 5)" 5 "$(gcrun "$GW/huge.md")"
gchas "gate-check: …output capture is capped at 1 MiB" "bytes=1048576"
gchas "gate-check: …and the truncation is stated next to the fingerprint" "truncated"
HUGESHA="$(head -c 1048576 /dev/zero | tr '\0' 'z' | shasum -a 256 | cut -d' ' -f1)"
gchas "gate-check: …with the sha taken over the window it actually kept" "outsha=$HUGESHA"

echo "----"
echo "pretool-fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
