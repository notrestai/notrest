#!/bin/bash
# notrest UserPromptSubmit hook — THE ROUTING LAW: a task shape routes to the
# suite's verb for it; ad-hoc'ing a job a skill already owns is the violation.
# Authority for the table: skills/oracle/SKILL.md (intake routing) — keep in step.
# Fires on EVERY prompt: no set -e, every path exits 0, one nudge max, <=160 chars.

RAW="$(python3 -c 'import sys,json;d=json.load(sys.stdin);p=d.get("prompt") or d.get("user_prompt") or "";sys.stdout.write(p.strip()[:2000])' 2>/dev/null)"
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
[ -n "$SKILL" ] || exit 0

# The prompt already named the verb — nudging it would be noise. Exempt: an arm
# whose own trigger phrase IS the verb's name ("project graph", "spend report") —
# there the word is the task shape, not the user naming the skill, and applying the
# guard would leave the arm permanently dead.
if [ -z "$SELFNAMED" ]; then
  case "$NORM" in *" $SKILL "*) exit 0 ;; esac
fi

echo "[notrest] route: this looks ${SHAPE}-shaped — /notrest:${SKILL} is the suite's verb for it (fine to skip deliberately)."
exit 0
