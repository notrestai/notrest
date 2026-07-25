#!/usr/bin/env bash
# router-fixture — pipes real UserPromptSubmit payloads through hooks/router.sh and
# asserts the ROUTING LAW end to end: every shape reaches its verb, every suppression
# stays silent, and the nudge is one line under 160 chars.
# Exit 0 = every assertion held. No network, no model calls, no repo writes.

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUTER="$SD/../../../hooks/router.sh"
PASS=0
FAIL=0

[ -f "$ROUTER" ] || { echo "FATAL: missing $ROUTER"; exit 9; }

ok()  { PASS=$((PASS+1)); echo "PASS  $1"; }
no()  { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }

# The harness hands the hook a JSON payload on stdin; the prompt is .prompt.
fire() {
  printf '%s' "$1" \
    | python3 -c 'import sys,json;print(json.dumps({"session_id":"router-fixture","hook_event_name":"UserPromptSubmit","prompt":sys.stdin.read()}))' \
    | bash "$ROUTER" 2>/dev/null
}

# routes <label> <expected-skill> <prompt>
routes() {
  out="$(fire "$3")"
  case "$out" in
    *"/notrest:$2 "*) ;;
    *) no "$1 -> /notrest:$2" "got: ${out:-<silent>}"; return ;;
  esac
  lines="$(printf '%s\n' "$out" | grep -c .)"
  chars="$(printf '%s' "$out" | python3 -c 'import sys;sys.stdout.write(str(len(sys.stdin.read().rstrip())))')"
  if [ "$lines" -ne 1 ]; then no "$1 -> one nudge only" "got $lines lines"
  elif [ "$chars" -gt 160 ]; then no "$1 -> nudge <=160 chars" "got $chars"
  else ok "$1 -> /notrest:$2 ($chars chars)"; fi
}

# silent <label> <prompt>
silent() {
  out="$(fire "$2")"
  if [ -z "$out" ]; then ok "$1 -> silent"; else no "$1 -> silent" "got: $out"; fi
}

echo "── routing table (first match wins, one nudge max)"
routes "research ask"        researcher       "can you research how vector databases handle deletes"
routes "market sizing ask"   marketresearcher "what is the market size for AI observability tooling"
routes "claim to verify"     factcheck        "is it true that postgres 17 dropped that flag"
routes "a choice"            decider          "should i use sqlite or postgres for this service"
routes "red-team ask"        critic           "poke holes in this launch plan before friday"
routes "code review ask"     refuter          "please review this code before i merge it"
routes "migration plan"      stepbystep       "how do we migrate off the legacy queue"
routes "runbook ask"         actionplan       "give me the exact commands to roll this out"
routes "outbound ask"        draft            "write the email to the team about the outage"
routes "explanation ask"     explainer        "explain how the prompt cache actually works"
routes "prior-art ask"       archivist        "have we researched this vendor before on this project"
routes "recap ask"           recap            "tell me what happened in the last release"
routes "handoff ask"         sessionend       "lets wrap up and hand the state over"
routes "cadence ask"         watch            "recheck that pricing claim on a cadence every friday"

echo "── suppressions (the router owes silence)"
silent "prompt already names a suite verb" "run /notrest:researcher on vector databases for me"
silent "prompt under four words"           "research vector databases"
silent "a slash command"                   "/eval check the laws now please"
silent "prompt already names the skill"    "use the researcher skill on vector databases"
silent "no routable shape"                 "add a null check to the parser module"

echo "── malformed input (a hook never breaks a prompt)"
out="$(printf 'not json at all' | bash "$ROUTER" 2>/dev/null)"; rc=$?
if [ -z "$out" ] && [ "$rc" -eq 0 ]; then ok "garbage stdin -> silent, exit 0"
else no "garbage stdin -> silent, exit 0" "exit $rc, out: $out"; fi
out="$(printf '' | bash "$ROUTER" 2>/dev/null)"; rc=$?
if [ -z "$out" ] && [ "$rc" -eq 0 ]; then ok "empty stdin -> silent, exit 0"
else no "empty stdin -> silent, exit 0" "exit $rc, out: $out"; fi

echo "----"
echo "router-fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
