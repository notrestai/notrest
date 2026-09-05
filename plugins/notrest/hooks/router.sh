#!/bin/bash
# notrest UserPromptSubmit hook — THE ROUTING LAW: a task shape routes to the
# suite's verb for it; ad-hoc'ing a job a skill already owns is the violation.
# Authority for the table: skills/oracle/SKILL.md (intake routing) — keep in step.
# Fires on EVERY prompt: no set -e, every path exits 0, one nudge max, <=160 chars.

# ── NR-STDIN (E2, 4.6.2) — BOUNDED READ: the payload or nothing, never a hang.
# Contract, rationale and the bash-3.2 measurements live in hooks/pretool-gate.sh, which
# owns the budget; the loop is copied rather than sourced because sourcing a sibling
# costs a fork on that hook's fast path and would make reading stdin depend on a second
# file. TOTAL stdin wall time is bounded by NR_STDIN_WAIT (5 s) plus the sub-second
# granularity of SECONDS — not per read — and an idle stdin yields "", on which this
# hook fails open.
# The wait is a knob for fixtures, so it is VALIDATED, not trusted: a non-numeric -t
# makes read fail instantly (a silently disarmed hook) and a huge one restores the
# hang this fixes. Anything but 1-99 falls back to 5. `case`, so still no fork.
case "${NR_STDIN_WAIT:-}" in [1-9]|[1-9][0-9]) ;; *) NR_STDIN_WAIT=5 ;; esac
NR_RAW=""; NR_DL=$((SECONDS + NR_STDIN_WAIT))
while :; do
  NR_T=$((NR_DL - SECONDS))   # the REMAINING budget, never a fresh one per read (F4)
  [ "$NR_T" -ge 1 ] || break
  NR_LINE=""
  IFS= read -r -t "$NR_T" NR_LINE || { NR_RAW="$NR_RAW$NR_LINE"; break; }
  NR_RAW="$NR_RAW$NR_LINE"
done
[ -n "$NR_RAW" ] || exit 0

RAW="$(printf '%s' "$NR_RAW" | python3 -c 'import sys,json;d=json.load(sys.stdin);p=d.get("prompt") or d.get("user_prompt") or "";sys.stdout.write(p.strip()[:2000])' 2>/dev/null)"
[ -n "$RAW" ] || exit 0

LOW="$(printf '%s' "$RAW" | tr '[:upper:]' '[:lower:]' 2>/dev/null)"
case "$LOW" in
  /*)            exit 0 ;;   # a slash command already names its own route
  *"/notrest:"*) exit 0 ;;   # the prompt already names a suite verb
esac

# Normalize to space-padded lowercase words so every match is word-bounded.
NORM=" $(printf '%s' "$LOW" | tr -c 'a-z0-9' ' ' 2>/dev/null | tr -s ' ' 2>/dev/null) "
set -- $NORM
[ "$#" -ge 4 ] || exit 0    # greetings and acks are not task shapes

# ---------------------------------------------------------------- routing table
# Ordered, first match wins. Kept as a plain case chain on purpose: greppable
# is checkable (eval.py ROUTER + ROUTE-TABLE-PARITY read these SKILL=/SHAPE= pairs;
# skills/oracle/SKILL.md's routing bullet must name the same verbs).
# Specific multi-word phrases sit ABOVE the generic one-word arms — first match wins.
SKILL=""; SHAPE=""; SELFNAMED=""
case "$NORM" in
  # precedence: these phrases are supersets of the research arm below
  *" what do we already know"*|*" have we research"*|*" already research"*)
      SKILL=archivist;        SHAPE=prior-art ;;
  *" research"*|*" find sources"*|*" look into"*|*" deep dive"*)
      SKILL=researcher;       SHAPE=research ;;
  *" market size"*|*" tam "*|*" competitor"*|*" pricing landscape"*)
      SKILL=marketresearcher; SHAPE=market-sizing ;;
  *" fact check"*|*" factcheck"*|*" verify claim"*|*" verify this claim"*|*" verify the claim"*|*" is it true"*)
      SKILL=factcheck;        SHAPE=fact-check ;;
  *" should i "*|*" choose between"*|*" compare options"*|*" decide"*|*" deciding"*)
      SKILL=decider;          SHAPE=decision ;;
  *" red team"*|*" poke holes"*|*" stress test"*|*" critique"*)
      SKILL=critic;           SHAPE=red-team ;;
  *" review this code"*|*" review the code"*|*" code review"*|*" refute"*|*" adversarial review"*)
      SKILL=refuter;          SHAPE=adversarial-review ;;
  *" plan the steps"*|*" how do we migrate"*|*" roadmap"*)
      SKILL=stepbystep;       SHAPE=planning ;;
  *" runbook"*|*" exact commands"*|*" copy paste"*)
      SKILL=actionplan;       SHAPE=runbook ;;
  *" write the email"*|*" write an email"*|*" write the memo"*|*" write a memo"*|*" write the announcement"*|*" write an announcement"*|*" write the update"*)
      SKILL=draft;            SHAPE=outbound ;;
  # the instruments: multi-word phrases, so they sit above the generic arms below
  *" health check"*|*" is the harness healthy"*|*" check the install"*)
      SKILL=doctor;           SHAPE=health-check ;;
  *" check the laws"*|*" conformance check"*)
      SKILL=eval;             SHAPE=law-check ;;
  # the ESTABLISHMENT shape (2026-08-02): "does this project follow the plugin" is neither
  # an install question (/doctor) nor a law question (/eval) — it asks whether this project
  # has the estate at all. Deliberately carries no phrase containing the verb's own name:
  # "establish notrest" is a user who already named the route, and the guard below owns it.
  *" establish the harness"*|*" set up the plugin"*|*" follow the plugin"*|\
  *" following the plugin"*|*" follow the harness"*|*" following the harness"*|\
  *" continue the build"*|*" pick up the build"*|*" continue this build"*)
      SKILL=notrest;          SHAPE=establish ;;
  # SELFNAMED: the trigger phrase contains the verb's own name, so the
  # "prompt already named the verb" guard below would swallow every match.
  *" project graph"*|*" file graph"*)
      SKILL=graph;            SHAPE=file-graph;   SELFNAMED=1 ;;
  *" spend report"*|*" token report"*|*" audit the model routing"*)
      SKILL=spend;            SHAPE=spend-audit;  SELFNAMED=1 ;;
  *" explain"*|*" why does"*|*" how does"*)
      SKILL=explainer;        SHAPE=explanation ;;
  *" recap"*|*" decision story"*|*" what happened"*|*" how did we get here"*)
      SKILL=recap;            SHAPE=recap ;;
  *" wrap up"*|*" end session"*|*" end the session"*|*" handoff"*|*" hand off"*)
      SKILL=sessionend;       SHAPE=handoff ;;
  *" watch this"*|*" recheck"*|*" on a cadence"*)
      SKILL=watch;            SHAPE=recheck ;;
esac

# ── THE LEARNINGS LINE (4.6.3) — at most ONE, and only when the prompt names something a
# banked lesson is scoped to. The routing nudge outranks it: this hook's law is one line
# per prompt, so a prompt that routes never also carries a lesson (the lane it routes to
# gets the digest from spawn-gate instead).
#
# THE MISS PATH STAYS FORK-FREE. Everything before the index.py call is builtin: a `case`
# for a path-like word, bash's own word splitting to collect those words, and a GLOB over
# skills/*/ for the suite's verb names — a glob is pathname expansion, not a subprocess,
# and reading the roster off disk beats a hardcoded list that rots the day a skill lands.
# $0's directory is taken with parameter expansion for the same reason: $(dirname "$0")
# would be a fork on every prompt. Only a prompt that actually names a path or a verb
# pays for estate-root and the indexer.
nr_learnings_line() {
  NR_TOKS=""
  case "$LOW" in
    */*)
      set -- $RAW
      for NR_W in "$@"; do
        case "$NR_W" in
          # A SYSTEM NOTIFICATION IS NOT A PATH (live defect, 2026-09-05): the seat was
          # shown a lesson because "<task-id>ad1b941f…</task-id>" contains a slash and
          # was taken for a path. Angle brackets, quotes and square brackets never occur
          # in a scope token, so a word carrying one is rejected outright.
          *[\<\>\"\'\[\]]*) : ;;
          */*) NR_W="${NR_W%,}"; NR_W="${NR_W%.}"
               NR_TOKS="$NR_TOKS $NR_W" ;;
        esac
      done ;;
  esac
  for NR_D in "${0%/*}"/../skills/*/; do
    [ -d "$NR_D" ] || continue
    NR_N="${NR_D%/}"; NR_N="${NR_N##*/}"
    case " $NORM " in *" $NR_N "*) NR_TOKS="$NR_TOKS $NR_N" ;; esac
  done
  [ -n "$NR_TOKS" ] || return 0

  . "${0%/*}/estate-root.sh" 2>/dev/null || true
  NR_ROOT="${NR_ESTATE_ROOT:-}"
  [ -n "$NR_ROOT" ] || return 0
  [ -f "$NR_ROOT/archive/findings.jsonl" ] || return 0
  NR_IDX="${0%/*}/../skills/archivist/scripts/index.py"
  [ -f "$NR_IDX" ] || return 0

  # SPECIFIC SCOPE ONLY (seat ruling, 2026-09-05). An 'estate'-scoped learning matches
  # every prompt ever typed, so routing it here would make this line permanent furniture;
  # those lessons ride the packet and the lane digest instead. The estate-scoped set is
  # obtained by ASKING for it — a token that cannot match any real scope returns exactly
  # those records — and subtracted. No scope semantics are reimplemented here: index.py
  # still does every match, and the line printed is still the one it framed.
  NR_LINE="$(NR_IDX="$NR_IDX" NR_ROOT="$NR_ROOT" NR_TOKS="$NR_TOKS" python3 <<'NRPY' 2>/dev/null
import os, subprocess, sys, json

idx, root = os.environ["NR_IDX"], os.environ["NR_ROOT"]
toks = os.environ.get("NR_TOKS", "").split()


def ask(args):
    p = subprocess.run([sys.executable, idx, "learnings", "--root", root] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else ""


try:
    if not toks:
        raise SystemExit(0)
    wide = ask(["--json", "--scope", "__nr_no_specific_match__"])
    estate_ids = set()
    for r in (json.loads(wide or '{"records": []}').get("records") or []):
        if r.get("id"):
            estate_ids.add(str(r["id"]))
    for line in ask(["--digest", "--limit", "5", "--scope"] + toks).splitlines():
        parts = line.split()
        rid = parts[1] if len(parts) > 1 and parts[0] == "|" else ""
        if rid and rid not in estate_ids:
            sys.stdout.write(line)
            break
except Exception:
    raise SystemExit(0)
NRPY
)"
  [ -n "$NR_LINE" ] || return 0
  NR_FIRST="${NR_TOKS# }"; NR_FIRST="${NR_FIRST%% *}"
  echo "[notrest] a banked lesson applies: ${NR_LINE#| } (all of them: /notrest:archivist learnings --scope $NR_FIRST)"
  return 0
}

# No route matched — the one place a banked lesson may speak instead (4.6.3).
[ -n "$SKILL" ] || { nr_learnings_line; exit 0; }

# The prompt already named the verb — nudging it would be noise. Exempt: an arm
# whose own trigger phrase IS the verb's name ("project graph", "spend report") —
# there the word is the task shape, not the user naming the skill, and applying the
# guard would leave the arm permanently dead.
# DELIBERATE SILENCE, and it stays silent (arm-proven 2026-09-05): the prompt has already
# named the verb, so there is nothing to route AND nothing to add — a lesson line here
# would break the one-nudge law on the very path the estate chose to keep quiet. The
# banked lesson speaks only where nothing else does.
if [ -z "$SELFNAMED" ]; then
  case "$NORM" in *" $SKILL "*) exit 0 ;; esac
fi

echo "[notrest] route: this looks ${SHAPE}-shaped — /notrest:${SKILL} is the suite's verb for it (fine to skip deliberately)."
exit 0
