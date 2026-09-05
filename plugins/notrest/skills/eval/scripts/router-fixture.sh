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

echo "── the instruments (a harness question routes to the harness's own verb)"
routes "health-check ask"    doctor           "is the harness healthy after that release"
routes "install ask"         doctor           "can you check the install for me now"
routes "law-check ask"       eval             "can you check the laws before we ship"
routes "file-graph ask"      graph            "show me the project graph for this repo"
routes "spend-audit ask"     spend            "give me a token report for the session"
routes "history ask"         recap            "so how did we get here with the auth rewrite"

echo "── self-named arms (the trigger phrase IS the verb — the arm must still fire)"
# `graph` and `spend` name themselves in their own trigger phrases. Without the
# SELFNAMED exemption the "prompt already named the verb" guard swallows every match
# and both arms are dead code that no other assertion would notice.
routes "self-named graph ask" graph           "show me the file graph for this project"
routes "self-named spend ask" spend           "give me the spend report for today"

echo "── first-match order (a new arm must not steal an older shape)"
# The instrument block sits ABOVE recap/explainer, so a history question carrying
# instrument-adjacent words ("checks", "reports") has to fall past all four arms.
routes "history beats instruments" recap      "how did we get here after all those checks and reports"
# and the reverse direction: research outranks the health-check arm it sits above
routes "research beats health check" researcher "research how health checks work in kubernetes"

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
echo "── 4.6.3 · the banked lesson speaks only when the route does not"
# A scratch PLUGIN (hooks + the tree's index.py) and a scratch ESTATE, because this hook
# now reads a store and this repo's store is not a fixture.
RWORK="$(mktemp -d)"
RPLUG="$RWORK/plug"; mkdir -p "$RPLUG/skills/archivist/scripts"
cp -Rp "$SD/../../../hooks" "$RPLUG/hooks"
RIDX_SRC="$SD/../../../skills/archivist/scripts/index.py"
[ -f "$RIDX_SRC" ] && cp -p "$RIDX_SRC" "$RPLUG/skills/archivist/scripts/index.py"
for rsk in "$SD"/../../../skills/*/; do [ -d "$rsk" ] && mkdir -p "$RPLUG/skills/$(basename "$rsk")"; done
REST="$RWORK/est"; mkdir -p "$REST/archive"
printf '# COORD.md\n\n- [2026-09-05 04:10Z] [seat] scratch\n' > "$REST/COORD.md"
printf '%s\n' '{"id":"L-1","kind":"learning","ts":"2026-09-05T04:50:00Z","tag":"LEARNED","statement":"run every fixture from a scratch estate","evidence":[{"ref":"[2026-09-05 04:45Z]"}],"scope":["plugins/notrest/hooks/**"],"source":"seat"}' > "$REST/archive/findings.jsonl"
rfire() {   # rfire <prompt> -> the hook's stdout, fired from the scratch estate
  printf '%s' "$1" \
    | python3 -c 'import sys,json;print(json.dumps({"session_id":"router-fixture","hook_event_name":"UserPromptSubmit","prompt":sys.stdin.read()}))' \
    | ( cd "$REST" && bash "$RPLUG/hooks/router.sh" 2>/dev/null )
}
if [ -f "$RPLUG/skills/archivist/scripts/index.py" ] \
   && python3 "$RPLUG/skills/archivist/scripts/index.py" learnings --root "$REST" --digest >/dev/null 2>&1; then
  OUT="$(rfire "take another look at plugins/notrest/hooks/router.sh before we call it done")"
  LN="$(printf '%s' "$OUT" | grep -c .)"
  case "$OUT" in
    *"a banked lesson applies: L-1"*)
        if [ "$LN" -eq 1 ]; then ok "a path in scope -> ONE banked-lesson line"
        else no "a path in scope -> exactly one line" "got $LN lines"; fi ;;
    *) no "a path in scope -> the banked lesson speaks" "got: ${OUT:-<silent>}" ;;
  esac
  OUT="$(rfire "can you research how vector databases handle deletes in plugins/notrest/hooks/router.sh")"
  LN="$(printf '%s' "$OUT" | grep -c .)"
  case "$OUT" in
    *"/notrest:researcher"*)
        case "$OUT" in
          *"banked lesson"*) no "the ROUTE outranks the lesson (one line per prompt)" "both lines were printed" ;;
          *) if [ "$LN" -eq 1 ]; then ok "the ROUTE outranks the lesson — still one line per prompt"
             else no "the route outranks the lesson" "got $LN lines"; fi ;;
        esac ;;
    *) no "the route still fires when a path is also named" "got: ${OUT:-<silent>}" ;;
  esac
  OUT="$(rfire "have a look at docs/TUTORIAL.md and tell me whether it still reads right")"
  if [ -z "$OUT" ]; then ok "a path with NO learning in scope -> silent"
  else no "a path with no learning in scope stays silent" "got: $OUT"; fi
  # THE LIVE CONDITION FIRST: the seat's defect needed an ESTATE-scoped record in the
  # store, because that is what makes any junk token match something. Seeding it here is
  # what makes the tokenizer arms below red on the old code instead of accidentally green.
  printf '%s\n' '{"id":"L-9","kind":"learning","ts":"2026-09-05T06:00:00Z","tag":"LEARNED","statement":"an estate-wide lesson that must never become router furniture","evidence":[{"ref":"[2026-09-05 05:00Z]"}],"scope":["estate"],"source":"seat"}' > "$REST/archive/findings.jsonl"
  # ── SPECIFIC SCOPE ONLY + THE TOKENIZER (seat, live defect 2026-09-05). The seat was
  # shown a lesson on a SYSTEM NOTIFICATION because "<task-id>…</task-id>" contains a
  # slash, and because an 'estate'-scoped record matches every prompt ever typed.
  OUT="$(rfire "--scope <task-id>ad1b941f8c2e4b1d9f3a</task-id> please continue the work")"
  if [ -z "$OUT" ]; then ok "a <task-id> system notification is not a path -> silent"
  else no "a <task-id> notification must not look like a path" "got: $OUT"; fi
  for junk in "look at 'quoted/path.md' now please" "check [bracketed/thing] for me please"; do
    OUT="$(rfire "$junk")"
    if [ -z "$OUT" ]; then ok "a quoted/bracketed token is not a path -> silent"
    else no "quoted/bracketed tokens are not paths" "got: $OUT"; fi
  done
  # an ESTATE-scoped store must stay quiet however specific the prompt is: those lessons
  # ride the packet and the lane digest, never this line
  printf '%s\n' '{"id":"L-9","kind":"learning","ts":"2026-09-05T06:00:00Z","tag":"LEARNED","statement":"an estate-wide lesson that must never become router furniture","evidence":[{"ref":"[2026-09-05 05:00Z]"}],"scope":["estate"],"source":"seat"}' > "$REST/archive/findings.jsonl"
  OUT="$(rfire "take another look at plugins/notrest/hooks/router.sh before we call it done")"
  if [ -z "$OUT" ]; then ok "an ESTATE-only store prints nothing (estate lessons are not router furniture)"
  else no "an estate-only store prints nothing" "got: $OUT"; fi
  # and a store holding BOTH still speaks — but only for the specific one
  printf '%s\n' '{"id":"L-9","kind":"learning","ts":"2026-09-05T06:00:00Z","tag":"LEARNED","statement":"an estate-wide lesson","evidence":[{"ref":"[2026-09-05 05:00Z]"}],"scope":["estate"],"source":"seat"}
{"id":"L-1","kind":"learning","ts":"2026-09-05T04:50:00Z","tag":"LEARNED","statement":"run every fixture from a scratch estate","evidence":[{"ref":"[2026-09-05 04:45Z]"}],"scope":["plugins/notrest/hooks/**"],"source":"seat"}' > "$REST/archive/findings.jsonl"
  OUT="$(rfire "take another look at plugins/notrest/hooks/router.sh before we call it done")"
  LN="$(printf '%s' "$OUT" | grep -c .)"
  case "$OUT" in
    *"L-1"*) if [ "$LN" -eq 1 ]; then ok "estate + path-scoped store -> one line, and it is the PATH-scoped lesson"
             else no "estate + path store -> one line" "got $LN lines"; fi ;;
    *) no "estate + path-scoped store still speaks for the specific one" "got: ${OUT:-<silent>}" ;;
  esac

  rm -f "$REST/archive/findings.jsonl"
  OUT="$(rfire "take another look at plugins/notrest/hooks/router.sh before we call it done")"
  if [ -z "$OUT" ]; then ok "NO store at all -> silent (the line is armed by the store)"
  else no "no store means no lesson line" "got: $OUT"; fi
else
  echo "SKIP  index.py has no 'learnings' verb in this tree — the lesson arms are UNRUN"
  FAIL=$((FAIL+1))
fi
rm -rf "$RWORK"

echo "router-fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
