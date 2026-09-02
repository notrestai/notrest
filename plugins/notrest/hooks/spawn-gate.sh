#!/bin/bash
# notrest PreToolUse hook — THE OFFLOAD LAW, ENFORCED IN CODE.
#
# Pattern adopted from cloudflare-os (Apache 2.0), whose spawner PINS THE CHILD'S MODEL
# IN CODE rather than asking the parent to remember. Ours was prose (fable-mode, the
# SessionStart echo, agentswarm) plus a POST-HOC audit (spend.py report exits 4 on a
# violation) — which means a mis-routed lane was caught after it had already burned the
# wrong credit. This closes that gap: the violation is refused at the door.
#
# THE LAW (owner-set 2026-07-15; amended 2026-09-01, superseding the 2026-08-30
# sonnet clause): THE SEAT CHOOSES EACH LANE'S MODEL BY THE DIFFICULTY OF THE TASK
# AND DECLARES THE CHOICE IN THE DISPATCHING BRIEF — "model: opus — tier: judgment"
# for judgment-bearing work (design, debugging, root-cause, kernel surfaces,
# refuters and reviews, merges, anything ambiguous or under-specified), "model:
# sonnet — tier: bounded" for bounded, well-specified work whose done-when is a
# runnable check the seat wrote before dispatch; when unsure, opus.
#
# WHAT THIS GATE REFUSES IS NOT A MATTER OF DIFFICULTY, and is unchanged by the
# amendment: never haiku (a tier declaration does not launder it), never
# subagent_type "fork" (a fork inherits the seat and bills its credit), and a spawn
# that omits the model is a violation, not a default. The tier discipline itself
# lives in the brief and the receipts (spend.py) — this hook cannot read briefs.
#
# PAYLOAD, verified against this repo's own transcripts before this hook was written
# (87 real spawns): tool_name is "Agent" in this harness; other surfaces call it "Task".
# Both are matched. tool_input keys: description · model · prompt · subagent_type.
#   {"hook_event_name":"PreToolUse","tool_name":"Agent","cwd":"…",
#    "tool_input":{"description":"…","prompt":"…","model":"opus",
#                  "subagent_type":"general-purpose"},"tool_use_id":"…"}
#
# PHILOSOPHY, matching hooks/pretool-gate.sh: a violation BLOCKS (that is the point),
# NOTREST_GATE_OVERRIDE=1 permits with a LOUD receipt (a bypassed gate that says nothing
# is worse than no gate), and ANY malformed input passes through silently — a broken
# hook must never break a session.

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
PAYLOAD="$NR_RAW"
[ -n "$PAYLOAD" ] || exit 0

# Parse defensively. Anything unexpected → empty fields → the pass-through path below.
FIELDS="$(printf '%s' "$PAYLOAD" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    if not isinstance(d, dict):
        raise ValueError
    ti = d.get("tool_input") or {}
    if not isinstance(ti, dict):
        ti = {}
    def s(v):
        return "" if v is None else str(v).replace("\t", " ").replace("\n", " ")
    sys.stdout.write("\t".join([s(d.get("tool_name")), s(ti.get("model")),
                                s(ti.get("subagent_type")), s(ti.get("description"))]))
except Exception:
    pass' 2>/dev/null)"
[ -n "$FIELDS" ] || exit 0

TOOL="$(printf '%s' "$FIELDS" | cut -f1)"
MODEL="$(printf '%s' "$FIELDS" | cut -f2)"
STYPE="$(printf '%s' "$FIELDS" | cut -f3)"
DESC="$(printf '%s' "$FIELDS" | cut -f4)"

# Not a spawn → this gate has no opinion. Every other tool is somebody else's business.
case "$TOOL" in
  Agent|Task) : ;;
  *) exit 0 ;;
esac

OVERRIDE=""
[ "${NOTREST_GATE_OVERRIDE:-}" = "1" ] && OVERRIDE="env"

block() {
  printf '%s\n' "$1" >&2
  [ -n "${2:-}" ] && printf '%s\n' "$2" >&2
  printf '%s' "$1" | python3 -c 'import sys, json
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                  "permissionDecision": "deny",
                  "permissionDecisionReason": sys.stdin.read()}}))' 2>/dev/null
  exit 2
}

overridden() {
  printf '[notrest] SPAWN GATE OVERRIDDEN (%s): %s\n' "$OVERRIDE" "$1" >&2
  printf '%s\t%s' "$OVERRIDE" "$1" | python3 -c 'import sys, json
how, what = sys.stdin.read().split("\t", 1)
msg = "[notrest] spawn gate OVERRIDDEN via %s — %s" % (how, what)
print(json.dumps({"systemMessage": msg,
                  "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                         "additionalContext": msg}}))' 2>/dev/null
  exit 0
}

FIX='   fix: declare the model on the Agent/Task call, chosen by task difficulty:
   model="opus" for judgment-bearing work, model="sonnet" for a bounded, well-specified
   job whose done-when is a runnable check; when unsure, opus. Never haiku, never
   subagent_type="fork" (a fork inherits the seat and bills its credit). Omitting the
   model is a violation, not a default; the brief records the tier.
   Contract: /notrest:agentswarm · receipts: /notrest:spend'

# ── RULE 1 · THE FORK BAN. A fork ignores the model parameter and inherits the seat,
# so it is never a lawful offload however it is spelled.
case "$STYPE" in
  fork|Fork|FORK)
    [ -n "$OVERRIDE" ] && overridden "subagent_type=fork on \"$DESC\""
    block "notrest spawn gate: subagent_type=\"fork\" is banned — a fork inherits the seat and bills its credit, so it is not an offload at all. Rerun with NOTREST_GATE_OVERRIDE=1 only if you mean it." "$FIX"
    ;;
esac

# ── RULE 2 · THE MODEL MUST BE EXPLICIT: OPUS OR SONNET (owner-amended 2026-09-01).
# WHICH of the two is the seat's call, made on the difficulty of the task and declared in
# the brief; this hook cannot read briefs and does not try to. It enforces the half that
# is not a judgment: haiku and omitted models are refused at the door.
NORM="$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]')"
case "$NORM" in
  *opus*|*sonnet*) exit 0 ;;             # lawful: explicit opus or sonnet
  "")
    [ -n "$OVERRIDE" ] && overridden "model omitted on \"$DESC\""
    block "notrest spawn gate: this Agent/Task call sets NO model — omitting it is a violation, not a default. It would silently inherit the seat's model and bill its credit." "$FIX"
    ;;
  *)
    [ -n "$OVERRIDE" ] && overridden "model=$MODEL on \"$DESC\""
    block "notrest spawn gate: model=\"$MODEL\" — the offload law allows explicit opus or sonnet only; the seat picks between them by task difficulty and declares the tier in the brief (owner 2026-09-01). haiku and other models are refused at the door rather than audited after the burn." "$FIX"
    ;;
esac

exit 0
