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

# ── RULE 0 · AN UNATTENDED RUN DOES NOT FAN OUT (4.7.0). NOTREST_UNATTENDED=1 marks a
# session with nobody at the keyboard. A lane spawned there answers to no one: its
# returns are read by nothing, its spend is nobody's decision, and a runner that fans out
# multiplies an unsupervised burn by the width of the fan. One runner, one lane. Checked
# BEFORE the model rules because it is not a question of which model — no model is
# lawful here. The override still works, and still says so out loud.
if [ "${NOTREST_UNATTENDED:-}" = "1" ]; then
  [ -n "$OVERRIDE" ] && overridden "fan-out from an unattended run: \"$DESC\""
  block "notrest spawn gate: unattended runs do not fan out — one runner, one lane. This session is marked NOTREST_UNATTENDED=1, so there is nobody to read a lane's return or to own its spend. Do the work in this session, or run it attended." \
        "   fix: drop the spawn and do the work here; or run the job attended (unset NOTREST_UNATTENDED) if a fan-out is genuinely wanted.
   Override (states itself in the transcript): NOTREST_GATE_OVERRIDE=1"
fi

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

# ── THE LEARNINGS DIGEST (4.6.3) — the ONLY place this hook touches the Agent prompt.
# A lane that repeats a mistake the estate already banked is the estate paying twice for
# one lesson. The deny checks above are unchanged and run FIRST: a denied call is never
# reached from here, so nothing about a refusal — exit code, stderr, JSON — can move.
#
# MECHANISM: hookSpecificOutput.updatedInput, documented as a PARTIAL object (send only
# the keys you change) with LAST PRETOOLUSE WRITER WINS. spawn-gate is the only hook in
# this suite permitted to write the Agent prompt; if another one is ever added, one of
# them will silently lose. FAIL-OPEN AND SILENT throughout: no estate, no store, no
# index.py, an index.py that does not know the verb, an empty digest, a bad payload —
# every one of them exits 0 having printed nothing, and the lane is spawned unchanged.
# Cost lands only on a LAWFUL spawn (rare, and already past two python parses); the deny
# path pays nothing.
nr_learnings_inject() {
  . "$(cd "$(dirname "$0")" && pwd)/estate-root.sh" 2>/dev/null || true
  # ── THE ACCESS KEY (4.8). Only the INJECTION half is gated: the deny rules above have
  # already run, and they stay armed on a keyless machine on purpose — a machine without
  # a key must not become a machine without laws.
  [ -n "${NR_ACCESS:-}" ] || return 0
  NR_ROOT="${NR_ESTATE_ROOT:-}"
  [ -n "$NR_ROOT" ] || return 0
  NR_IDX="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)/skills/archivist/scripts/index.py"
  NR_ROOT="$NR_ROOT" NR_IDX="$NR_IDX" NR_PAYLOAD="$PAYLOAD" python3 <<'NRPY' 2>/dev/null
import binascii, json, os, re, subprocess, sys, time

try:
    root, idx = os.environ["NR_ROOT"], os.environ["NR_IDX"]
    d = json.loads(os.environ.get("NR_PAYLOAD") or "")
    ti = d.get("tool_input") or {}
    prompt = ti.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise SystemExit(0)
    lane_key = ""

    # ── THE COMMISSION'S GATES BECOME THE ESTATE'S GATES (4.7.0; hardened after the
    # refuter round, 2026-09-05).
    # A commission that says CHECK:/EXPECT: has already written a runnable contract; until
    # 4.7.0 it lived only in the lane's prompt, so the seat could call the work done while
    # the lane's own checks were red. Copied into gates/ACTIVE.md under this lane's
    # section, where completion-gate.sh already runs whatever it finds.
    #
    # B1 — SHELL INJECTION INTO THE SEAT, and the reason the harvest is now narrow.
    # The first version harvested ANY line matching CHECK:, including lines inside ```
    # fences. gate-check's own law is that a fenced directive is DOCUMENTATION, so a
    # commission that merely QUOTED an example gate had that example promoted to a live
    # command run at the seat's next Stop — proven by a fenced `CHECK: touch …FENCED_RAN`
    # that created the file. Two rules close it, and both are conservative:
    #   1. FENCE-AWARE — nothing inside a ``` or ~~~ block is ever harvested.
    #   2. ONE BLOCK ONLY — the harvest is the contiguous block that begins with
    #      DONE-WHEN: at column 0 and ends at the first blank line. A CHECK: anywhere
    #      else in the prompt — prose, an aside, a quoted transcript — is not a contract
    #      the dispatcher wrote, and is not harvested.
    # Every harvested line carries its provenance, so a reader of gates/ACTIVE.md can see
    # which lane put it there and that it came from a DONE-WHEN block rather than by hand.
    # F3 (refuter): TWO repros closed at once.
    #   V6  — an INDENTED fence (```` ```  ````) slipped past a column-0 fence test, so a
    #         quoted example was harvested again.
    #   SM5 — a lane PASTING another commission's brief into its own prompt had that
    #         brief's DONE-WHEN block harvested as if the dispatcher had written it.
    # So the fence test is now whitespace-insensitive, and DONE-WHEN alone no longer opens
    # anything: the harvest happens ONLY between an explicit `NOTREST-GATES:` line at
    # column 0 and `END-GATES` at column 0. Those markers are the seat's signature — a
    # pasted brief carries prose, not the estate's marker pair, and DONE-WHEN: survives
    # inside the block as the human label it always was.
    _fence, _inblock = None, False
    _block = []
    for _ln in prompt.splitlines():
        _fm = re.match(r"^\s*(```+|~~~+)", _ln)
        if _fm:
            _tok = _fm.group(1)[0]
            if _fence is None:
                _fence = _tok
            elif _fence == _tok:
                _fence = None
            continue
        if _fence is not None:
            continue                       # inside a fence: documentation, never a gate
        if re.match(r"^NOTREST-GATES:", _ln):
            _inblock = True
            continue
        if re.match(r"^END-GATES\s*$", _ln):
            _inblock = False
            continue
        if _inblock:
            _block.append(_ln)

    _checks = [ln.rstrip() for ln in _block
               if re.match(r"^\s{0,3}(?:[-*]\s+)?CHECK:\s*\S", ln)
               or re.match(r"^\s{0,3}(?:[-*]\s+)?EXPECT:", ln)]
    if _checks:
        # B3 — AN EXPLICIT KEY, NOT A HASH. The pairing used to be sha1(prompt[:400]),
        # which agent-ledger had to reproduce from the transcript — and could not, once a
        # prompt contained the LEARNINGS marker itself (the cut moved) or when two lanes
        # shared a 400-char preamble (one section for two lanes). A section that cannot be
        # matched cannot be retired, and an unretireable gate holds the seat's Stop red
        # forever. So the key is generated HERE, written into the section header, and
        # carried in the prompt as its LAST line for the other end to read back verbatim.
        _key = binascii.hexlify(os.urandom(4)).decode("ascii")
        _now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _head = "## lane %s · opened %s" % (_key, _now)
        _desc = str(ti.get("description") or "").replace("\n", " ")[:80]
        _prov = "# lane %s · from the commission's NOTREST-GATES block" % _key
        _sec = [_head,
                "<!-- written by hooks/spawn-gate.sh at spawn; retired by"
                " hooks/agent-ledger.sh on lane stop, or by hooks/session-start.sh after"
                " 24h. description: %s -->" % _desc]
        for _dw in _block:
            if re.match(r"^\s{0,3}(?:[-*]\s+)?DONE-WHEN:", _dw):
                _sec.append("<!-- %s -->" % _dw.strip()[:300])
                break
        # N2 (refuter): gate-check prints `RED: <name> — <why> [<cmd>]`, and the name is
        # whatever a GATE: line last said. Naming each check `lane <key> gate N` makes a
        # red gate say WHOSE it is — the seat reading the block should not have to open
        # gates/ACTIVE.md to find out which lane is holding the Stop.
        _n = 0
        for _c in _checks:
            if re.match(r"^\s{0,3}(?:[-*]\s+)?CHECK:", _c):
                _n += 1
                _sec.append("GATE: lane %s gate %d" % (_key, _n))
            _sec.append(_prov)
            _sec.append(_c)
        _sec.append("")
        _gp = os.path.join(root, "gates", "ACTIVE.md")
        try:
            os.makedirs(os.path.dirname(_gp), exist_ok=True)
            try:
                with open(_gp, "r", encoding="utf-8", errors="replace") as _f:
                    _old = _f.read().splitlines()
            except OSError:
                _old = ["# gates/ACTIVE.md — the gates this estate is under RIGHT NOW.",
                        "# Sections are written by hooks and by hand; each one is its own"
                        " contract.", ""]
            while _old and not _old[-1].strip():
                _old.pop()
            _out = _old + ([""] if _old else []) + _sec
            _tmp = _gp + ".tmp"
            with open(_tmp, "w", encoding="utf-8") as _f:
                _f.write("\n".join(_out) + "\n")
            os.replace(_tmp, _gp)
            lane_key = _key
        except OSError:
            pass

    # ── THE SCOPED DIGEST. Optional: a lane with no lessons in scope still gets its
    # lane-key line, and a lane with neither gets no updatedInput at all.
    digest = ""
    if os.path.isfile(os.path.join(root, "archive", "findings.jsonl")) and os.path.isfile(idx):
        toks = []
        for m in re.findall(r"[A-Za-z0-9_.*/-]*/[A-Za-z0-9_.*/-]+", prompt):
            t = m.strip(".,;:)'\"")
            if t and t not in toks:
                toks.append(t)
        sk = os.path.normpath(os.path.join(os.path.dirname(idx), "..", "..", ".."))
        low = prompt.lower()
        try:
            for name in sorted(os.listdir(os.path.join(sk, "skills"))):
                if re.search(r"\b%s\b" % re.escape(name.lower()), low) and name not in toks:
                    toks.append(name)
        except OSError:
            pass
        toks = toks[:12] + ["estate"]
        pr = subprocess.run([sys.executable, idx, "learnings", "--root", root, "--digest",
                             "--limit", "5", "--scope"] + toks,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        if pr.returncode == 0:
            digest = (pr.stdout or b"").decode("utf-8", "replace").strip()

    new_prompt = prompt
    if digest:
        new_prompt += ("\n\n[notrest LEARNINGS — banked lessons in scope; read before "
                       "acting]\n" + digest + "\n")
    if lane_key:
        # THE LAST LINE, ALWAYS. agent-ledger reads this line off the banked brief to know
        # which gates section to retire — it never hashes anything, so a prompt that
        # already contains the LEARNINGS marker, or two lanes sharing a preamble, cannot
        # confuse the pairing (B3/N1, refuter 2026-09-05).
        new_prompt += "\n[notrest lane-key: %s]" % lane_key
    if new_prompt == prompt:
        raise SystemExit(0)

    # THE WHOLE TOOL INPUT, WITH ONE FIELD REPLACED — docs vs runtime, 2026-09-05. The
    # hooks docs describe updatedInput as a PARTIAL object; CLI 2.1.237 rejected a real
    # Agent call with "required parameter `description` is missing", so it validates the
    # object as the COMPLETE tool input and replaces rather than merges. Copy the
    # original, overwrite exactly one key, invent nothing.
    ui = dict(ti)
    ui["prompt"] = new_prompt
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "updatedInput": ui}}))
except SystemExit:
    raise
except Exception:
    raise SystemExit(0)
NRPY
  return 0
}

NORM="$(printf '%s' "$MODEL" | tr '[:upper:]' '[:lower:]')"
case "$NORM" in
  # lawful: explicit opus or sonnet. The ONLY branch that reaches the digest — a refusal
  # never carries one, so a denied call's bytes are exactly what they were in 4.6.2.
  *opus*|*sonnet*) nr_learnings_inject; exit 0 ;;
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
