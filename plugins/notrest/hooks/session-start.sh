#!/bin/bash
# notrest SessionStart hook — continuity nudge + self-update.

# ── self-update: if this plugin lives in a git clone, quietly pull latest.
# Fire-and-forget: never blocks session start; --ff-only never clobbers local
# edits (dirty/diverged clones are silently left alone). Updates apply from
# the NEXT session. Note: this executes whatever the origin repo ships —
# point it only at a repo you control.
PLUGIN_GIT_ROOT="$(git -C "$(cd "$(dirname "$0")" && pwd)" rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$PLUGIN_GIT_ROOT" ]; then
  ( cd "$PLUGIN_GIT_ROOT" && git pull --ff-only --quiet >/dev/null 2>&1 & ) 2>/dev/null
fi

# ── identity: one line that answers "is notrest installed?" in every session.
# The /plugin UI does not list skills-dir runtimes — live-proven 2026-07-26/27: the
# owner, not finding notrest there, reinstalled a marketplace copy FOUR times, each
# one silently shadowing this runtime. This line is the visible truth; never cut it.
NV="$(sed -n 's/.*"version": "\([^"]*\)".*/\1/p' "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" 2>/dev/null | head -1)"
echo "[notrest] v${NV:-?} @skills-dir — live from the repo tree (the /plugin UI hides skills-dir plugins; verify with: claude plugin list)"

# ── fable discipline: bolted to the metal. Unconditional every session so the
# working posture is present without anyone typing /fable-mode. The anchor is
# always in context; the full contract is one skill-load away. Trivial single-
# question turns may skip. stdout is injected as session context.
echo "[notrest] Fable discipline is active: ORIENT -> PROBE -> ACT -> PROVE -> BANK. Probe the live system before reasoning; a done/works/fixed claim needs in-transcript evidence (exit code, diff, status) or say 'unverified'; bank state before stopping. Full contract: /notrest:fable-mode."

# ── offload model policy: unconditional, so it reaches every fan-out surface
# (Agent tool, Workflow/ultracode, deep-research, review panels) even when no
# notrest skill is loaded. Owner-set 2026-07-15: opus-only offload.
echo "[notrest] HARD RULE — offload: every spawned agent/Workflow lane sets its model explicitly — \"opus\" by default, \"sonnet\" only for a brief-declared mechanical/DRAFT-tier job (owner amendment 2026-08-30). Never haiku, never subagent_type \"fork\" (forks inherit the seat); omitting model is a violation, not a default. Delegate via /notrest:agentswarm; builds run ONE persistent lane — feedback RESUMES it (SendMessage), never a new spawn. Receipts auto-log; never hand-log. Never /model-switch the seat."

# ── continuity nudge: stdout is injected as session context.
if [ -f "START-HERE.md" ]; then
  echo "[notrest] START-HERE.md exists in this directory — a previous session left resume instructions (and possibly a 'Live line:' to a predecessor session that can answer setup questions). Suggest /oracle to the user to resume properly, or read START-HERE.md before starting work."
fi
if [ -f "HANDOFF.md" ] && [ ! -f "START-HERE.md" ]; then
  echo "[notrest] HANDOFF.md exists here — prior session state is available; consider reading it before starting work."
fi
# ── COORD.md: the session coordination ledger (the fable-coord behavior, generalized
# to every session). Auto-created at the git root of any repo a session starts in;
# the UserPromptSubmit hook (coord-nudge.sh) injects the per-prompt append discipline.
# ── non-git projects (2026-08-02 — live failure: a whole session ran in the non-git
# "not.rest website" folder believing the harness governed it; every estate hook was
# git-gated, so it got the discipline echoes and none of the estate). Two cases, and
# the difference between them is deliberate:
#   · ALREADY ESTABLISHED — the SHARED resolver (hooks/estate-root.sh) answers, exactly
#     as it answers for coord-nudge, agent-ledger and session-end, so all four hooks
#     agree about which project this session belongs to. Full treatment below.
#   · NOT ESTABLISHED — nudge, and write NOTHING. Auto-scaffolding a ledger into any
#     project-shaped directory a session happens to open is how the estate scatters;
#     establishing outside git is /notrest's deliberate act, never a hook's side effect.
#     The NUDGE branch stays cwd-only on purpose: it speaks about THIS directory. Its
#     marker list carries no `.claude`, because ~/.claude exists on every machine and
#     that one entry made $HOME a project (2026-08-02 adversarial round); $HOME and /
#     are refused outright, there being no legitimate $HOME estate.
. "$(cd "$(dirname "$0")" && pwd)/estate-root.sh" 2>/dev/null || true
REPO_ROOT="${NR_ESTATE_ROOT:-}"
GIT_BACKED=""
[ -n "$REPO_ROOT" ] && [ -d "$REPO_ROOT/.git" ] && GIT_BACKED=1
if [ -z "$GIT_BACKED" ] && [ -n "$REPO_ROOT" ]; then
  git -C "$REPO_ROOT" rev-parse --show-toplevel >/dev/null 2>&1 && GIT_BACKED=1
fi
# A dangling or escaping symlink at COORD.md would make the scaffold below write THROUGH
# it, outside the repo entirely — refuse rather than follow (2026-08-02 adversarial round).
COORD_SAFE=1
if [ -n "$REPO_ROOT" ] && [ -L "$REPO_ROOT/COORD.md" ] && ! nr_contained "$REPO_ROOT" "$REPO_ROOT/COORD.md"; then
  COORD_SAFE=""
fi
if [ -n "$REPO_ROOT" ] && [ -n "$GIT_BACKED" ] && [ -n "$COORD_SAFE" ] && [ ! -f "$REPO_ROOT/COORD.md" ] && ! ls "$REPO_ROOT"/FABLE-COORD*.md >/dev/null 2>&1; then
  cat > "$REPO_ROOT/COORD.md" <<'COORDEOF'
# COORD.md — session coordination ledger

Append-only, newest at the bottom, one line per substantive prompt when its work
lands: `- [YYYY-MM-DD HH:MMZ] [session-or-lane] <what was asked> -> <what landed> | evidence: <exit code / commit / path / status>`.
Honest entries only: in-progress is "in progress", untested is "untested". Never
compacted: past ~500 ledger lines this file is SEALED WHOLE as the next COORD-<NNN>.md
and a fresh active volume starts — sealed volumes are immutable, sessions read this
active tail, /recap + /compile + /archivist read every volume. In a fable-director
arrangement, lane blackboards live beside this file as COORD-<LANE>.md (never all
digits — that is a sealed volume); this file is the ship/main ledger.

## LEDGER
COORDEOF
  echo "- [$(date -u '+%Y-%m-%d %H:%MZ')] [hook] COORD.md scaffolded by notrest SessionStart" >> "$REPO_ROOT/COORD.md"
  echo "[notrest] COORD.md created at the repo root — the session coordination ledger. Append one ledger line per substantive prompt when its work lands (ask -> landed | evidence)."
elif [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/COORD.md" ]; then
  echo "[notrest] COORD.md is live in this repo — read its ledger tail before starting (prior sessions' trail), and append one line per substantive prompt's work (ask -> landed | evidence)."
elif [ -z "$REPO_ROOT" ] && [ "$PWD" != "$HOME" ] && [ "$PWD" != "/" ]; then
  for NR_MARK in CLAUDE.md README.md package.json pyproject.toml; do
    if [ -e "$PWD/$NR_MARK" ]; then
      echo "[notrest] Project-like directory without git — estate hooks are limited here. Say /notrest to establish the harness in this project (COORD ledger + CLAUDE.md protocol)."
      break
    fi
  done
fi
# ── cockpit (2026-08-04 — the owner's field note: the cockpit did exactly what they
# wanted and NOTHING SURFACED IT; no session opened it and no project remembered
# wanting it. Presence is not display, the same way presence is not establishment).
# A project opts in ONCE with `cockpit serve --always`, which leaves the marker below;
# from then on every session is TOLD, and surfacing the window becomes the seat's job
# rather than something the owner has to remember. This hook only ECHOES: it never
# probes the port, never spawns a server, never opens anything — a SessionStart hook
# must not do work, and a hook that shells out is a hook that can hang a session start.
# A malformed marker prints nothing at all.
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/graph/.cockpit-always" ]; then
  CK_PORT="$(python3 -c 'import json,sys
try:
    p = json.load(open(sys.argv[1])).get("port")
    if isinstance(p, bool):
        raise ValueError
    p = int(p)
    if 1 <= p <= 65535:
        sys.stdout.write(str(p))
except Exception:
    pass' "$REPO_ROOT/graph/.cockpit-always" 2>/dev/null)"
  if [ -n "$CK_PORT" ]; then
    echo "[notrest] Cockpit is opted always-on here (port $CK_PORT) — probe with cockpit.py status; if down, start it, then OPEN it in the built-in browser pane so the owner sees the estate live (graph SKILL.md, cockpit section)."
  fi
fi
# ── pulse layer: one line of machine-written readings, if the estate has them. READ
# ONLY — a SessionStart hook must never do work, so this never refreshes anything; the
# refresh happens in the background off SubagentStop and SessionEnd.
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/pulse/pulse.json" ]; then
  NR_PULSE="$(python3 -c '
import json, sys, time, os
try:
    p = sys.argv[1]
    d = json.load(open(p))
    ins = d.get("instruments") or {}
    age = int(time.time() - os.path.getmtime(p))
    a = ("%ds" % age) if age < 90 else ("%dm" % (age // 60) if age < 5400 else "%dh" % (age // 3600))
    parts = []
    for k in ("doctor", "eval", "swarm", "compile"):
        if k in ins:
            parts.append("%s=%s" % (k, ins[k].get("exit")))
    if parts:
        sys.stdout.write(" · ".join(parts) + " · refreshed " + a + " ago by " +
                         str(d.get("trigger", "?")))
except Exception:
    pass' "$REPO_ROOT/pulse/pulse.json" 2>/dev/null)"
  if [ -n "$NR_PULSE" ]; then
    echo "[notrest] Pulse (machine-written, background-refreshed): $NR_PULSE — full output in pulse/*.txt. Derived and disposable; the ledgers remain the record."
  fi
fi
# ── compile: surface a ripe candidate the estate has already recorded three or
# more times. This READS the last scan only — scanning belongs to /sessionend, and
# a SessionStart hook must never do work. Silent when absent, unreadable, or when
# every ripe candidate has already been ruled on.
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/compile/candidates.json" ]; then
  COMPILE_TOP="$(python3 -c 'import json,sys
try: c = json.load(open(sys.argv[1]))["candidates"]
except Exception: sys.exit(0)
r = [x for x in c if x.get("ripe") and x.get("status") == "NEW"]
if r: print(r[0]["slug"], r[0]["occurrences"])' "$REPO_ROOT/compile/candidates.json" 2>/dev/null)"
  if [ -n "$COMPILE_TOP" ]; then
    read -r CSLUG CSEEN <<< "$COMPILE_TOP"
    # THE OWNER'S STANDING AUTHORIZATION, written by `compile.py auto --on`. It upgrades
    # this line from a nudge a human must answer into a directive the seat may act on —
    # and it authorizes exactly ONE thing: DISPATCHING a builder lane. It never
    # authorizes installation. A compiled runtime still lives isolated under
    # compile/<slug>/ and shipping stays a release the owner gates, so the echo restates
    # that law rather than leaving it to be remembered.
    #
    # v4.5 (docket 8c): the marker lives OUTSIDE the estate, at
    #   ${NOTREST_HOME:-~/.notrest}/auto-build/<sha256 of the estate realpath>.json
    # because the old in-repo `compile/.auto-build` sat in the one place every lane can
    # write — a lane could grant itself the authority to be dispatched, and a clone
    # carried a stranger's opt-in. The legacy path is IGNORED here (honoring it would
    # keep the hole open) and named ONCE, so a standing authorization can never be lost
    # in silence.
    #
    # A missing, unreadable or malformed marker falls back to the old nudge SILENTLY:
    # a corrupt opt-in is not an opt-in, and a hook must never break the session. Three
    # further refusals, all in the same python probe: the marker must not be a symlink
    # OUT of the store (containment, the law the resolver applies to COORD.md), it must
    # name THIS estate if it names one at all, and anything unexpected reads as OFF.
    # RB-4 (refuter, 2026-09-01): NOTREST_HOME could be pointed back INSIDE the estate,
    # which reinstates the hole 8c closed — an in-estate store is writable by any lane
    # and travels with a clone. A store under the estate root is refused here and named
    # on stderr (an authorization that silently stops working is the failure mode the
    # marker exists to avoid); the probe prints `in-estate` for that case and `y` only
    # for a store the owner alone can write.
    NR_AUTOBUILD="$(python3 -c '
import hashlib, json, os, sys
try:
    root = os.path.realpath(sys.argv[1])
    base = os.path.join(os.environ.get("NOTREST_HOME") or
                        os.path.join(os.path.expanduser("~"), ".notrest"), "auto-build")
    rb = os.path.realpath(base)
    if rb == root or rb.startswith(root + os.sep):
        sys.stdout.write("in-estate:" + rb)      # a store a lane could write
        raise SystemExit(0)
    p = os.path.join(base, hashlib.sha256(root.encode("utf-8")).hexdigest() + ".json")
    rp = os.path.realpath(p)
    if not (rp == rb or rp.startswith(rb + os.sep)):
        raise SystemExit(0)                      # escapes the store: not ours
    d = json.load(open(p))
    if not (isinstance(d, dict) and d.get("opted") is True):
        raise SystemExit(0)
    e = d.get("estate")
    if isinstance(e, str) and e and os.path.realpath(e) != root:
        raise SystemExit(0)                      # names a different estate
    sys.stdout.write("y")
except Exception:
    pass' "$REPO_ROOT" 2>/dev/null)"
    case "$NR_AUTOBUILD" in
      in-estate:*)
        echo "[notrest] auto-build authorization IGNORED: the store ${NR_AUTOBUILD#in-estate:} sits inside the estate — an in-estate store is writable by any lane and travels with a clone, so it is not the owner's private authorization. Unset NOTREST_HOME (or point it outside the estate) and re-run: compile.py auto --on --root $REPO_ROOT"
        NR_AUTOBUILD=""
        ;;
    esac
    if [ -z "$NR_AUTOBUILD" ] && [ -f "$REPO_ROOT/compile/.auto-build" ]; then
      echo "[notrest] compile/.auto-build is IGNORED since v4.5 — an in-estate marker is writable by any lane and travels with a clone. Re-authorize with: compile.py auto --on --root $REPO_ROOT (writes to ~/.notrest/auto-build/), then delete the old file."
    fi
    if [ -n "$NR_AUTOBUILD" ]; then
      echo "[notrest] AUTO-BUILD opted in: dispatch ONE opus builder lane this session for ripe candidate $CSLUG (/compile $CSLUG) — isolated under compile/$CSLUG/, benchmarked, receipted; NEVER installed: shipping stays the owner's act."
    else
      echo "[notrest] Ripe compile candidate: $CSLUG seen ${CSEEN}x — repeated work the estate already recorded. Say /compile $CSLUG to move its stable parts into code (or compile.py decide --status DECLINED to silence)."
    fi
  fi
fi
# A lane blackboard is COORD-<LANE>.md — NOT the machine-written ledgers
# (COORD-AGENTS.md, COORD-ARCHIVE.md, COORD-AGENTS-ARCHIVE.md), which exist in
# every ORACLE repo and used to false-fire this nudge. Nor the SEALED LEDGER
# VOLUMES, whose suffix is purely numeric (COORD-001.md, COORD-AGENTS-007.md):
# a lane name is never all digits, so that test separates them cleanly.
LANE_BLACKBOARD=""
for f in COORD-*.md FABLE-COORD*.md; do
  [ -f "$f" ] || continue
  case "$f" in
    COORD-AGENTS.md|COORD-ARCHIVE.md|COORD-AGENTS-ARCHIVE.md) continue ;;
  esac
  COORD_SUF="${f#COORD-}"; COORD_SUF="${COORD_SUF%.md}"
  COORD_SUF="${COORD_SUF#AGENTS-}"
  case "$COORD_SUF" in
    ''|*[!0-9]*) : ;;   # has a non-digit -> a real lane name
    *) continue ;;      # all digits -> a sealed ledger volume, not a lane
  esac
  LANE_BLACKBOARD="$f"
  break
done
if [ -n "$LANE_BLACKBOARD" ] || [ -f "PLAN-FABLE-DIRECTOR-V4.md" ]; then
  echo "[notrest] Per-lane COORD blackboards (COORD-<LANE>.md / legacy FABLE-COORD*.md) exist here — a fable-director arrangement lives in this repo. If this session is meant to direct (or rejoin) it, load the fable-director skill (notrest:fable-director): it reads the repo's PLAN-FABLE-DIRECTOR-V4.md + blackboards and re-arms watches before anything else."
fi
exit 0
