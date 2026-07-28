#!/bin/bash
# notrest PreToolUse hook — THE HARD GATE. Every other hook in this suite nudges;
# this one can BLOCK a Bash call outright. Two rules, both descended from live
# incidents on this machine (2026-07-25):
#   RULE 1 · SHIP GATE    — `git push` out of THIS harness repo while doctor or eval
#                           is red. The instruments exist; nothing made them binding.
#   RULE 2 · SHADOW GUARD — the consumer install flow. An installed notrest@notrest
#                           takes the name and silently SHADOWS the skills-dir runtime
#                           (CLAUDE.md law; live-proven at 20:13Z, caught only by doctor).
#
# CONTRACT — verified against Claude Code 2.1.207 (strings on the binary) and
# code.claude.com/docs/en/hooks:
#   payload   {"hook_event_name":"PreToolUse","tool_name":"Bash","cwd":"…",
#              "tool_input":{"command":"…","description":"…"},"tool_use_id":"…"}
#   BLOCK     exit 2. The runner: `if(ce.status===2){…yield{blockingError:{blockingError:
#             `[${cmd}]: ${ce.stderr||"No stderr output"}`},outcome:"blocking"}…}` — so
#             the tool call is denied and STDERR is what the model is shown, verbatim.
#             The same reason is ALSO written to stdout in the PreToolUse decision
#             channel (hookSpecificOutput.permissionDecision:"deny", schema-validated in
#             the binary: "Valid types are: allow, deny, ask, defer"), so a loader that
#             reads the decision instead of the exit code blocks identically. On 2.1.207
#             exit 2 short-circuits before stdout is parsed; the JSON is the belt.
#   ALLOW     exit 0, silent — no decision emitted, so the normal permission flow runs.
#             (We never emit permissionDecision:"allow": that would BYPASS the user's
#             own permission prompt, which is not this gate's business.)
# FAIL-OPEN — no set -e; every unexpected path (bad JSON, no python3, no git, slow
#             stdin) exits 0 ALLOW. A broken gate must never brick the machine.
# BUDGET    — fires on EVERY Bash call on this machine. The miss path is one builtin
#             read and one `case`: no fork, no python, no git, no repo detection.

# ------------------------------------------------------------------ fast path
# Builtin read (no fork). -t 5 so a stdin that never closes cannot hang the machine;
# a truncated read simply misses the tokens below and allows.
IFS= read -r -d '' -t 5 RAW
# Neither rule can fire unless one of these literal two-word tokens is in the raw
# payload. Tight on purpose: this repo's own paths ("…/oracle-suite-plugin",
# "…/.claude/projects/…") must never match, or every call here would pay for python.
case "$RAW" in
  *"git push"*|*"claude plugin"*|*"plugin install"*|*"plugin update"*|*"plugin marketplace"*) ;;
  *) exit 0 ;;
esac

# -------------------------------------------------------------- payload parse
META="$(printf '%s' "$RAW" | python3 -c 'import sys, json
d = json.load(sys.stdin)
ti = d.get("tool_input") or {}
cmd = ti.get("command") or ""
sys.stdout.write("%s\n%s\n%s" % (d.get("tool_name") or "", d.get("cwd") or "",
                                 " ".join(cmd.split())[:4000]))' 2>/dev/null)"
[ -n "$META" ] || exit 0
{ IFS= read -r TOOL; IFS= read -r CWD; IFS= read -r CMD; } <<< "$META"
[ "$TOOL" = "Bash" ] || exit 0
[ -n "$CMD" ] || exit 0

# Space-padded, lowercased, every non-alphanumeric run squeezed to one space — so every
# match below is word-bounded and `git pushup` can never match " git push ".
NORM=" $(printf '%s' "$CMD" | tr '[:upper:]' '[:lower:]' 2>/dev/null \
        | tr -c 'a-z0-9' ' ' 2>/dev/null | tr -s ' ' 2>/dev/null) "

# The block message tells the owner to "rerun with NOTREST_GATE_OVERRIDE=1", and the
# natural way to do that is to PREFIX the command — which sets the env of the COMMAND,
# never of this hook. Both forms therefore count, or the escape hatch is a lie.
OVERRIDE=""
[ "$NOTREST_GATE_OVERRIDE" = "1" ] && OVERRIDE="env"
case "$CMD" in *NOTREST_GATE_OVERRIDE=1*) OVERRIDE="inline" ;; esac

# ----------------------------------------------------------------- decisions
# block <reason> [detail] — reason first and verbatim: it is the line the model reads.
block() {
  printf '%s\n' "$1" >&2
  [ -n "$2" ] && printf '%s\n' "$2" >&2
  printf '%s' "$1" | python3 -c 'import sys, json
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                  "permissionDecision": "deny",
                  "permissionDecisionReason": sys.stdin.read()}}))' 2>/dev/null
  exit 2
}

# The override must never be silent — a bypassed gate that says nothing is worse than
# no gate. Told to the user (systemMessage) and to the model (additionalContext).
overridden() {
  printf '[notrest] GATE OVERRIDDEN (%s): %s\n' "$OVERRIDE" "$1" >&2
  printf '%s\t%s' "$OVERRIDE" "$1" | python3 -c 'import sys, json
how, what = sys.stdin.read().split("\t", 1)
msg = "[notrest] gate OVERRIDDEN via %s — %s" % (how, what)
print(json.dumps({"systemMessage": msg,
                  "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                         "additionalContext": msg}}))' 2>/dev/null
  exit 0
}

# ------------------------------------------------------- RULE 2 · SHADOW GUARD
# Applies on ANY cwd: the incident came from outside the repo. Checked first — it is
# pure string work, where the ship gate has to shell out to the instruments.
SHADOW=""
case "$NORM" in
  *" claude plugin install "*|*" claude plugin update "*)
      case "$NORM" in *notrest*) SHADOW=1 ;; esac ;;
esac
case "$NORM" in
  *" claude plugin marketplace add "*)
      case "$NORM" in *notrest*|*oracle*) SHADOW=1 ;; esac ;;
esac
if [ -n "$SHADOW" ]; then
  [ -n "$OVERRIDE" ] && overridden "shadow guard on: $CMD"
  block "SHADOW GUARD: this machine runs notrest@skills-dir; the consumer flow shadows it (CLAUDE.md law, live-proven 2026-07-25). Override: NOTREST_GATE_OVERRIDE=1." \
        "   remedy if already shadowed: claude plugin uninstall notrest@notrest && claude plugin marketplace remove notrest  (both are allowed by this gate)"
fi

# ---------------------------------------------------------- RULE 1 · SHIP GATE
case "$NORM" in *" git push "*) ;; *) exit 0 ;; esac

# THIS harness repo only — every other repo on the machine pushes untouched. The
# marker is doctor.py itself: if the tree does not ship the instruments, there is
# nothing to gate with.
GITROOT="$(git -C "${CWD:-$PWD}" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$GITROOT" ] || exit 0
DOCTOR="$GITROOT/plugins/notrest/skills/doctor/scripts/doctor.py"
EVALPY="$GITROOT/plugins/notrest/skills/eval/scripts/eval.py"
[ -f "$DOCTOR" ] || exit 0
[ -f "$EVALPY" ] || exit 0

[ -n "$OVERRIDE" ] && overridden "ship gate on $GITROOT — doctor/eval NOT run"

python3 "$DOCTOR" check --root "$GITROOT" >/dev/null 2>&1; DRC=$?
python3 "$EVALPY" check --root "$GITROOT" >/dev/null 2>&1; ERC=$?
# WARN (5) is not a ship blocker; FAIL (6) is. Learned the hard way 2026-07-27: doctor's
# SHADOW-APPSIDE warns about ANOTHER application's provisioning store — true, useful, and
# with no CLI remedy — so a gate that blocks on 5 would block every push forever and train
# the override reflex. A habitually-overridden gate is worse than no gate. Warnings are
# echoed (never swallowed) and the push proceeds; a FAIL still stops it dead.
if [ "$DRC" -eq 5 ] || [ "$ERC" -eq 5 ]; then
  printf '[notrest] ship gate: warnings present (doctor=%s eval=%s) — not blocking; run the instruments to read them\n' \
    "$DRC" "$ERC" >&2
fi
[ "$DRC" -ne 6 ] && [ "$ERC" -ne 6 ] && [ "$DRC" -lt 6 ] && [ "$ERC" -lt 6 ] && exit 0

# doctor: 0 ok · 5 warn · 6 fail (2 usage, 3 target) — eval: 0 ok · 5 warn · 6 fail.
# The codes are printed rather than summarised so the owner can tell a WARN from a FAIL
# without re-running anything.
block "notrest ship gate: doctor=$DRC eval=$ERC — fix, or rerun with NOTREST_GATE_OVERRIDE=1" \
      "   python3 $DOCTOR check --root $GITROOT
   python3 $EVALPY check --root $GITROOT"

exit 0
