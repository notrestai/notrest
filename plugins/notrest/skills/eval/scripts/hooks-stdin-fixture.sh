#!/usr/bin/env bash
# hooks-stdin-fixture — the KERNEL arm for docket 4.6.2 E2 + F7.
#
# E2: five hooks read stdin unbounded (`cat` / json.load(sys.stdin)); a stdin that is
# open and idle blocks them forever. The CLI normally closes stdin after the payload, so
# the hazard is bounded by the CLI's own hook timeout rather than proven live — but a
# hung hook is the worst failure mode this suite has (it takes the session with it),
# and the guard costs one builtin read. This fixture holds each hook's stdin OPEN with a
# fifo sleeper and asserts the hook still returns 0 inside CAP seconds.
#
# The guard is only half the assertion. A reader that cannot hang because it reads
# nothing is not a fix, so every no-hang arm is paired with a REAL-EFFECT arm on the same
# hook: spawn-gate still denies, router still nudges, agent-ledger still writes its
# receipt, session-end still cushions, completion-gate still fails open loudly on a
# malformed payload. Two of them fire a multi-KB payload: a truncated read yields invalid
# JSON, so the effect arm going silent IS the truncation detector.
#
# F7: session-start prints its version with CLAUDE_PLUGIN_ROOT unset; completion-gate is
# silent on EMPTY stdin (nothing to check) but still notices a MALFORMED one; the twelve
# hook scripts are all executable and hooks.json is not; every hooks.json event declares
# an explicit timeout.
#
# Exit 0 = every assertion held. No network, no model calls, no writes outside mktemp -d
# — every hook that writes an estate is run from a scratch estate, never from this repo.

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
H="$SD/../../../hooks"
PASS=0
FAIL=0

[ -d "$H" ] || { echo "FATAL: missing $H"; exit 9; }

ok() { PASS=$((PASS+1)); echo "PASS  $1"; }
no() { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }

# CAP is the wall clock a hook gets in these arms. The shipped stdin bound is 5s
# (NR_STDIN_WAIT in each hook), so an idle stdin must cost ~5s and never more than 8.
CAP="${NR_FIXTURE_CAP:-8}"

WORK="$(mktemp -d)"
NOEST="$WORK/not-an-estate"          # no git, no COORD.md -> every estate hook exits 0
mkdir -p "$NOEST"
cleanup() {
  [ -n "${HOLD_PID:-}" ] && kill "$HOLD_PID" 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT

json() { python3 -c 'import json,sys;sys.stdout.write(json.dumps(json.loads(sys.stdin.read())))'; }

# ---------------------------------------------------------------- bounded runner
# No `timeout` binary on stock macOS. Run the hook as a background process (exec, so the
# background pid IS the hook), poll, and kill it if it outlives CAP. RB_RC=124 marks a
# hook that had to be killed — the hang signature.
RB_RC=0; RB_SECS=0; RB_SEC_F=0
run_bounded() {   # run_bounded <cap> <cwd> <stdin-path> <hook-path> [env-assignments...]
  local cap="$1" cwd="$2" fin="$3" hook="$4"; shift 4
  local t0=$SECONDS pid waited=0
  # SECONDS is integer, and the SessionEnd arm below is decided at 1.5 s — so the float
  # clock comes from python3, which every hook here already depends on.
  local tf0; tf0="$(python3 -c 'import time;print(time.time())')"
  : > "$WORK/out"; : > "$WORK/err"
  ( cd "$cwd" && exec env "$@" bash "$hook" <"$fin" >"$WORK/out" 2>"$WORK/err" ) &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$waited" -ge $((cap * 10)) ]; then
      kill -9 "$pid" 2>/dev/null
      wait "$pid" 2>/dev/null
      RB_RC=124; RB_SECS=$((SECONDS - t0))
      RB_SEC_F="$(python3 -c 'import time,sys;print("%.2f" % (time.time()-float(sys.argv[1])))' "$tf0")"
      return 0
    fi
    sleep 0.1
    waited=$((waited + 1))
  done
  wait "$pid"; RB_RC=$?
  RB_SECS=$((SECONDS - t0))
  RB_SEC_F="$(python3 -c 'import time,sys;print("%.2f" % (time.time()-float(sys.argv[1])))' "$tf0")"
  return 0
}

# nohang <label> <hook-file> <cwd> — stdin is a fifo held open by a sleeper and never
# written to. The hook must return 0 within CAP.
nohang() {
  local label="$1" hook="$2" cwd="$3"
  local d="$WORK/fifo.$$.$RANDOM"
  mkdir -p "$d"; mkfifo "$d/in"
  ( exec 3>"$d/in"; sleep $((CAP * 3)) ) &
  HOLD_PID=$!
  disown "$HOLD_PID" 2>/dev/null   # the sleeper is killed on purpose; no job notice
  run_bounded "$CAP" "$cwd" "$d/in" "$H/$hook"
  kill "$HOLD_PID" 2>/dev/null; HOLD_PID=""
  rm -rf "$d"
  if [ "$RB_RC" -eq 124 ]; then
    no "$label: idle stdin returns inside ${CAP}s" "HUNG — killed at ${RB_SECS}s (rc=124)"
  elif [ "$RB_RC" -ne 0 ]; then
    no "$label: idle stdin returns inside ${CAP}s" "rc=$RB_RC after ${RB_SECS}s"
  else
    ok "$label: idle stdin -> rc=0 in ${RB_SECS}s (cap ${CAP}s)"
  fi
}

echo "── E2 · no hook blocks on an open, idle stdin (fifo held by a sleeper)"
nohang "router.sh"          router.sh          "$NOEST"
nohang "spawn-gate.sh"      spawn-gate.sh      "$NOEST"
nohang "agent-ledger.sh"    agent-ledger.sh    "$NOEST"
nohang "completion-gate.sh" completion-gate.sh "$NOEST"
nohang "session-end.sh"     session-end.sh     "$NOEST"
nohang "pretool-gate.sh"    pretool-gate.sh    "$NOEST"

# ------------------------------------------------------------- real-effect arms
# fire <hook> <cwd> <payload> -> stdin is a normal pipe that CLOSES, as the CLI does.
# Sets FRC / FOUT / FERR.
FRC=0; FOUT=""; FERR=""
fire() {
  local hook="$1" cwd="$2" payload="$3"
  printf '%s' "$payload" > "$WORK/payload"
  run_bounded "$CAP" "$cwd" "$WORK/payload" "$H/$hook"
  FRC=$RB_RC; FOUT="$(cat "$WORK/out")"; FERR="$(cat "$WORK/err")"
}

echo "── E2 · a payload that arrives normally still produces the hook's real effect"

SPAWN_BASE='{"hook_event_name":"PreToolUse","tool_name":"Agent","cwd":"/tmp","tool_input":'

denies() {   # denies <label> <tool_input-json>
  fire spawn-gate.sh "$NOEST" "$SPAWN_BASE$2}"
  if [ "$FRC" -eq 2 ] && [ -n "$FERR" ]; then ok "spawn-gate denies $1 (rc=2, reason on stderr)"
  else no "spawn-gate denies $1" "rc=$FRC err=${FERR:-<silent>}"; fi
}
denies "a model-omitted spawn" '{"description":"d","prompt":"p","subagent_type":"general-purpose"}'
denies "subagent_type=fork"    '{"description":"d","model":"opus","subagent_type":"fork"}'
denies "model=haiku"           '{"description":"d","model":"haiku","subagent_type":"general-purpose"}'

fire spawn-gate.sh "$NOEST" "$SPAWN_BASE"'{"description":"d","model":"opus","subagent_type":"general-purpose"}}'
if [ "$FRC" -eq 0 ] && [ -z "$FOUT" ] && [ -z "$FERR" ]; then ok "spawn-gate allows a lawful opus spawn (rc=0, silent)"
else no "spawn-gate allows a lawful opus spawn" "rc=$FRC out=$FOUT err=$FERR"; fi

# MULTI-KB: a 64 KB prompt. A truncated read leaves invalid JSON -> the gate parses
# nothing and passes through silently, so rc=2 here proves the whole payload was read.
BIG="$(python3 -c 'import json,sys
ti={"description":"d","prompt":"P"*65536,"subagent_type":"general-purpose"}
sys.stdout.write(json.dumps({"hook_event_name":"PreToolUse","tool_name":"Agent","cwd":"/tmp","tool_input":ti}))')"
fire spawn-gate.sh "$NOEST" "$BIG"
if [ "$FRC" -eq 2 ]; then ok "spawn-gate reads a 64 KB payload whole (still denies, rc=2)"
else no "spawn-gate reads a 64 KB payload whole" "rc=$FRC — payload truncated?"; fi

# The adversarial delivery: the payload arrives complete and the writer keeps stdin OPEN.
# The bound must cost time, not the payload.
d="$WORK/held"; mkdir -p "$d"; mkfifo "$d/in"
( exec 3>"$d/in"; printf '%s\n' "$SPAWN_BASE"'{"description":"d","prompt":"p","subagent_type":"general-purpose"}}' >&3; sleep $((CAP * 3)) ) &
HOLD_PID=$!
disown "$HOLD_PID" 2>/dev/null
run_bounded "$CAP" "$NOEST" "$d/in" "$H/spawn-gate.sh"
kill "$HOLD_PID" 2>/dev/null; HOLD_PID=""
if [ "$RB_RC" -eq 2 ]; then ok "spawn-gate still denies when the writer leaves stdin open (${RB_SECS}s)"
else no "spawn-gate still denies when the writer leaves stdin open" "rc=$RB_RC after ${RB_SECS}s"; fi
rm -rf "$d"

echo "── F3 · the NR_STDIN_WAIT knob is VALIDATED, not trusted (refuter, 2026-09-01)"
# Without the clamp, a hostile or fat-fingered value silently DISARMS the gate rather
# than slowing it: `read -t abc` errors out instantly, the payload is never read, and the
# hook fails open — an unlawful spawn admitted, with nothing on stderr to show for it.
# Every arm delays the payload by a second, because a payload already sitting in the pipe
# would be read even by a broken timeout: the delay is what makes the defect observable.
DELAYED='{"description":"d","model":"haiku","subagent_type":"general-purpose"}}'
knob() {   # knob <label> <NR_STDIN_WAIT value> <hook> <want-rc> <want-effect-grep>
  local label="$1" val="$2" hook="$3" want="$4" pay="$5"
  local d="$WORK/knob.$RANDOM"; mkdir -p "$d"; mkfifo "$d/in"
  ( exec 3>"$d/in"; sleep 1; printf '%s\n' "$pay" >&3; sleep $((CAP * 3)) ) &
  HOLD_PID=$!; disown "$HOLD_PID" 2>/dev/null
  run_bounded "$CAP" "$NOEST" "$d/in" "$H/$hook" NR_STDIN_WAIT="$val"
  kill "$HOLD_PID" 2>/dev/null; HOLD_PID=""; rm -rf "$d"
  if [ "$RB_RC" = "$want" ]; then ok "$hook holds with NR_STDIN_WAIT=$label (rc=$want in ${RB_SECS}s)"
  else no "$hook holds with NR_STDIN_WAIT=$label" "rc=$RB_RC (want $want) after ${RB_SECS}s"; fi
}
knob "abc"     abc     spawn-gate.sh 2 "$SPAWN_BASE$DELAYED"
knob "0"       0       spawn-gate.sh 2 "$SPAWN_BASE$DELAYED"
knob "(empty)" ""      spawn-gate.sh 2 "$SPAWN_BASE$DELAYED"
knob "999999"  999999  spawn-gate.sh 2 "$SPAWN_BASE$DELAYED"
# a second hook, so the arm is about the shared guard and not about spawn-gate alone
ROUTEPAY='{"hook_event_name":"UserPromptSubmit","prompt":"can you research how vector databases handle deletes"}'
d="$WORK/knobr"; mkdir -p "$d"; mkfifo "$d/in"
( exec 3>"$d/in"; sleep 1; printf '%s\n' "$ROUTEPAY" >&3; sleep $((CAP * 3)) ) &
HOLD_PID=$!; disown "$HOLD_PID" 2>/dev/null
run_bounded "$CAP" "$NOEST" "$d/in" "$H/router.sh" NR_STDIN_WAIT=abc
kill "$HOLD_PID" 2>/dev/null; HOLD_PID=""
case "$(cat "$WORK/out")" in
  *"/notrest:researcher"*) ok "router still nudges with NR_STDIN_WAIT=abc (${RB_SECS}s)" ;;
  *) no "router still nudges with NR_STDIN_WAIT=abc" "rc=$RB_RC got: $(cat "$WORK/out")" ;;
esac
rm -rf "$d"

echo "── F4 · the bound is on the TOTAL wall time, not on each read"
# Each read gets only the REMAINING budget. The old form handed every read a fresh 5 s,
# so a drip — a line, a 4 s gap, the payload, a writer that never closes — measured
# real 9.06 s. The cap here FOLLOWS FROM THE LAW: NR_STDIN_WAIT + 2 s of margin for the
# 1-second granularity of SECONDS and process start.
CAP4=7
d="$WORK/drip1"; mkdir -p "$d"; mkfifo "$d/in"
( exec 3>"$d/in"; printf 'a\n' >&3; sleep 4; printf '%s\n' "$SPAWN_BASE$DELAYED" >&3; sleep $((CAP4 * 4)) ) &
HOLD_PID=$!; disown "$HOLD_PID" 2>/dev/null
run_bounded "$CAP4" "$NOEST" "$d/in" "$H/spawn-gate.sh"
kill "$HOLD_PID" 2>/dev/null; HOLD_PID=""; rm -rf "$d"
# rc is the fail-open 0 on purpose: a junk line ahead of the JSON is unparseable for ANY
# reader, `cat` included. This arm is about the CLOCK, and the clock is the defect.
if [ "$RB_RC" -ne 124 ]; then ok "drip feed (junk, 4s gap, payload, held open) returns in ${RB_SEC_F}s (cap ${CAP4}s)"
else no "drip feed returns inside ${CAP4}s" "killed at ${RB_SEC_F}s — per-read budget, not total"; fi
d="$WORK/drip2"; mkdir -p "$d"; mkfifo "$d/in"
( exec 3>"$d/in"; sleep 3; printf '%s\n' "$SPAWN_BASE$DELAYED" >&3; sleep $((CAP4 * 4)) ) &
HOLD_PID=$!; disown "$HOLD_PID" 2>/dev/null
run_bounded "$CAP4" "$NOEST" "$d/in" "$H/spawn-gate.sh"
kill "$HOLD_PID" 2>/dev/null; HOLD_PID=""; rm -rf "$d"
if [ "$RB_RC" -eq 2 ]; then ok "a payload 3s late is still CAUGHT inside the budget (deny in ${RB_SEC_F}s)"
else no "a payload 3s late is still caught inside the budget" "rc=$RB_RC after ${RB_SEC_F}s"; fi

ROUTE_PROMPT="can you research how vector databases handle deletes"
fire router.sh "$NOEST" "$(printf '{"hook_event_name":"UserPromptSubmit","prompt":"%s"}' "$ROUTE_PROMPT")"
case "$FOUT" in
  *"/notrest:researcher"*) ok "router still nudges a research-shaped prompt" ;;
  *) no "router still nudges a research-shaped prompt" "rc=$FRC got: ${FOUT:-<silent>}" ;;
esac

BIGP="$(python3 -c 'import json,sys
sys.stdout.write(json.dumps({"hook_event_name":"UserPromptSubmit",
  "prompt":"can you research how vector databases handle deletes " + "z"*65536}))')"
fire router.sh "$NOEST" "$BIGP"
case "$FOUT" in
  *"/notrest:researcher"*) ok "router reads a 64 KB payload whole (still nudges)" ;;
  *) no "router reads a 64 KB payload whole" "rc=$FRC got: ${FOUT:-<silent>} — payload truncated?" ;;
esac

# agent-ledger + session-end write the ESTATE, so they get a scratch one: a directory
# with a COORD.md and no git. Never this repo.
EST="$WORK/estate"; mkdir -p "$EST"; printf '# COORD.md\n\n- scratch estate\n' > "$EST/COORD.md"
AID="fixt-$$-$RANDOM"
fire agent-ledger.sh "$EST" "$(printf '{"hook_event_name":"SubagentStop","agent_id":"%s","transcript_path":"/nonexistent/agent-%s.jsonl"}' "$AID" "$AID")"
if [ "$FRC" -eq 0 ] && grep -q "agent=$AID" "$EST/COORD-AGENTS.md" 2>/dev/null; then
  ok "agent-ledger still appends its receipt (agent=$AID)"
else
  no "agent-ledger still appends its receipt" "rc=$FRC ledger=$(tail -1 "$EST/COORD-AGENTS.md" 2>/dev/null)"
fi

fire session-end.sh "$EST" '{"hook_event_name":"SessionEnd","reason":"other"}'
if [ "$FRC" -eq 0 ] && grep -q "auto-cushion" "$EST/COORD.md" 2>/dev/null; then
  ok "session-end still writes the auto-cushion line"
else
  no "session-end still writes the auto-cushion line" "rc=$FRC coord=$(tail -1 "$EST/COORD.md" 2>/dev/null)"
fi

echo "── F1 · SessionEnd's REAL budget is the CLI's shared ~1.5 s pool"
# A plugin SessionEnd hook runs under that pool whatever `timeout` hooks.json declares
# (the raise consults settings.json and agent hooks, never plugin hooks) [cited: refuter
# on CLI 2.1.237; unverified live here]. So this hook must not WAIT on stdin at all: the
# 5 s bound the others use would outlive the budget and the cushion — the whole point of
# the hook — would never be written. Held-open stdin, and the line must still land.
EST2="$WORK/estate2"; mkdir -p "$EST2"; printf '# COORD.md\n\n- scratch estate\n' > "$EST2/COORD.md"
d="$WORK/sefifo"; mkdir -p "$d"; mkfifo "$d/in"
( exec 3>"$d/in"; sleep $((CAP * 3)) ) &
HOLD_PID=$!; disown "$HOLD_PID" 2>/dev/null
run_bounded "$CAP" "$EST2" "$d/in" "$H/session-end.sh"
kill "$HOLD_PID" 2>/dev/null; HOLD_PID=""; rm -rf "$d"
if [ "$RB_RC" -eq 0 ] && python3 -c 'import sys; raise SystemExit(0 if float(sys.argv[1]) < 1.5 else 1)' "$RB_SEC_F" \
   && grep -q "auto-cushion" "$EST2/COORD.md" 2>/dev/null; then
  ok "session-end: idle stdin -> cushion line written in ${RB_SEC_F}s (< 1.5s pool)"
else
  no "session-end: idle stdin -> cushion written in < 1.5s" "rc=$RB_RC secs=$RB_SEC_F cushion=$(grep -c auto-cushion "$EST2/COORD.md" 2>/dev/null)"
fi

echo "── F7 · completion-gate: silent on nothing, honest about garbage"
fire completion-gate.sh "$NOEST" ""
if [ "$FRC" -eq 0 ] && [ -z "$FOUT" ] && [ -z "$FERR" ]; then
  ok "completion-gate: EMPTY stdin -> rc=0, wholly silent"
else
  no "completion-gate: EMPTY stdin -> rc=0, wholly silent" "rc=$FRC out=$FOUT err=$FERR"
fi
fire completion-gate.sh "$NOEST" 'not json at all'
case "$FRC:$FERR" in
  0:*"failing open"*) ok "completion-gate: MALFORMED stdin -> rc=0 with the fail-open notice" ;;
  *) no "completion-gate: MALFORMED stdin -> rc=0 with the fail-open notice" "rc=$FRC err=${FERR:-<silent>}" ;;
esac

echo "── F7 · session-start prints its version with CLAUDE_PLUGIN_ROOT unset"
# A scratch COPY of the hooks dir, with its own plugin.json: the banner must resolve the
# plugin root from $0's directory. Copying also keeps the arm off this repo's git — the
# hook's self-update pull finds no clone under the scratch tree and stays home.
PLUG="$WORK/plug"; mkdir -p "$PLUG/.claude-plugin"
cp -R "$H" "$PLUG/hooks"
printf '{\n  "name": "notrest",\n  "version": "9.9.9-fixture"\n}\n' > "$PLUG/.claude-plugin/plugin.json"
d="$WORK/ssin"; mkdir -p "$d"; : > "$d/in"
run_bounded "$CAP" "$NOEST" "$d/in" "$PLUG/hooks/session-start.sh" -u CLAUDE_PLUGIN_ROOT
SSOUT="$(cat "$WORK/out")"
case "$SSOUT" in
  *"[notrest] v9.9.9-fixture @skills-dir"*) ok "session-start banner: version from \$0's plugin root (no CLAUDE_PLUGIN_ROOT)" ;;
  *"[notrest] v? "*) no "session-start banner: version from \$0's plugin root" "printed 'v?'" ;;
  *) no "session-start banner: version from \$0's plugin root" "rc=$RB_RC got: $(printf '%s' "$SSOUT" | head -1)" ;;
esac

# The SessionStart echo is the only surface that states the offload law in EVERY session,
# so it carries the 2026-09-01 amendment verbatim in shape: difficulty chooses, the brief
# declares, and the three refusals are untouched.
LAWOK=1
for phrase in "BY TASK DIFFICULTY" "tier: judgment" "tier: bounded" "opus when unsure" \
              "Never haiku" "subagent_type" "omitting model is a violation"; do
  case "$SSOUT" in *"$phrase"*) ;; *) LAWOK=0; MISSING="$phrase" ;; esac
done
if [ "$LAWOK" -eq 1 ]; then ok "session-start echo states the 2026-09-01 offload law (difficulty chooses, brief declares)"
else no "session-start echo states the 2026-09-01 offload law" "missing: $MISSING"; fi

echo "── E2 · hooks.json declares a timeout on every COMMAND (not on the group)"
# PLACEMENT IS THE WHOLE ASSERTION (seat gate, 2026-09-01). `timeout` is read off the
# INDIVIDUAL hook entry — {"type":"command","command":"…","timeout":N} — not off the
# matcher-group object that holds the "hooks" array. A group-level "timeout" parses,
# ships, and does nothing: configured but not in effect, which is worse than absent
# because it reads as done. This arm therefore checks both halves — every command HAS
# one, and no group still CARRIES one.
HJ="$(python3 - "$H/hooks.json" <<'HJPY'
import json, sys
try:
    blob = json.load(open(sys.argv[1]))
except Exception as exc:
    print("unparseable: %s" % exc); sys.exit(0)
bad, n = [], 0
for event, groups in sorted((blob.get("hooks") or {}).items()):
    for i, g in enumerate(groups or []):
        if "timeout" in g:
            bad.append("%s[%d] group-level timeout=%r (not in effect)" % (event, i, g["timeout"]))
        for j, h in enumerate(g.get("hooks") or []):
            n += 1
            t = h.get("timeout")
            # >= 10s: the shipped stdin bound is 5s, and a hook killed mid-write is
            # exactly the half-done state the ledgers must never be left in.
            if not isinstance(t, int) or isinstance(t, bool) or t < 10:
                bad.append("%s[%d].hooks[%d] timeout=%r" % (event, i, j, t))
print("; ".join(bad) if bad else "ok %d commands" % n)
HJPY
)"
case "$HJ" in
  "ok "*) ok "hooks.json: every COMMAND declares timeout >= 10, no group-level timeout ($HJ)" ;;
  *)      no "hooks.json: every COMMAND declares timeout >= 10, no group-level timeout" "$HJ" ;;
esac

echo "── F7 · the twelve hook scripts are executable; hooks.json is not"
MODEBAD=""
for f in "$H"/*.sh "$H"/gate-check.py; do
  [ -x "$f" ] || MODEBAD="$MODEBAD $(basename "$f")"
done
if [ -n "$MODEBAD" ]; then no "all 12 hook scripts are executable" "not +x:$MODEBAD"
else ok "all 12 hook scripts are executable"; fi
if [ -x "$H/hooks.json" ]; then no "hooks.json is not executable" "it is +x"
else ok "hooks.json is not executable"; fi

echo "── syntax: every shipped hook still parses"
SYNBAD=""
for f in "$H"/*.sh; do
  bash -n "$f" 2>/dev/null || SYNBAD="$SYNBAD $(basename "$f")"
done
python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "$H/gate-check.py" 2>/dev/null \
  || SYNBAD="$SYNBAD gate-check.py"
if [ -n "$SYNBAD" ]; then no "bash -n / ast-parse on all 12" "broken:$SYNBAD"
else ok "bash -n / ast-parse clean on all 12"; fi

echo
echo "hooks-stdin-fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
