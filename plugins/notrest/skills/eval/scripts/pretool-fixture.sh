#!/usr/bin/env bash
# pretool-fixture — pipes real PreToolUse payloads through hooks/pretool-gate.sh and
# asserts the harness's first HARD gate: the two rules BLOCK (exit 2 + a deny decision
# on stdout + the reason on stderr), everything else is allowed silently and fast.
# Exit 0 = every assertion held. No network, no model calls, no writes to this repo
# (rule 1 is proven against a scratch git repo with stub instruments).

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="$SD/../../../hooks/pretool-gate.sh"
PASS=0
FAIL=0

[ -f "$GATE" ] || { echo "FATAL: missing $GATE"; exit 9; }

ok() { PASS=$((PASS+1)); echo "PASS  $1"; }
no() { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }

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

echo "----"
echo "pretool-fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
