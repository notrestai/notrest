#!/bin/bash
# notrest SessionStart hook — continuity nudge + self-update.

# ── UNATTENDED RUNS GET NOTHING (4.7.0). NOTREST_UNATTENDED=1 marks a session with no
# human at the keyboard — a scheduled runner, an auto-build lane. Every line this hook
# prints is stdout injected as session context: nudges, the packet, the discipline anchor.
# All of it is addressed to a person who is not there, and all of it is tokens the runner
# pays for. THE SELF-UPDATE GOES TOO, and that is the load-bearing half: a `git pull`
# under an unattended run would move the tree beneath work already in flight, with nobody
# watching. First statement in the file, before any side effect.
[ "${NOTREST_UNATTENDED:-}" = "1" ] && exit 0

# ── THE ACCESS KEY (4.8), before ANY side effect — the self-update included. notrest is
# part of Atlas from this release: without a key the harness does nothing here except say
# so, in one line, at EVERY SessionStart — this hook has no memory across sessions and
# does not try to build one; the line is cheap and a keyless machine should be told each
# time it starts, not once and then silently.
#
# THE HOOK DIRECTORY, ABSOLUTE, ONCE (4.9). Two things below need it — the remedy the
# keyless line prints, and the identity client the keyed path fires — and both of them
# NAME A SCRIPT. estate-root.sh's V5c ruling applies verbatim: a relative hook dir
# resolves against whatever cwd the caller chose, so a planted tree under that cwd would
# be the thing the owner is told to run (and the thing this hook executes). `cd`+`pwd`
# returns an absolute path or nothing; nothing degrades both users of it, never guesses.
NR_HOOKDIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
case "${NR_HOOKDIR:-}" in /*) ;; *) NR_HOOKDIR="" ;; esac
. "${0%/*}/estate-root.sh" 2>/dev/null || true
if [ -z "${NR_ACCESS:-}" ]; then
  case "${NR_ACCESS_WHY:-nokey}" in
    # `atlas.py key --check` answers licensed-or-not; it does not enumerate WHY not, so
    # the only distinction worth drawing here is a verifier that could not be asked at
    # all — an install fault, not a licence one, and a different thing to go and fix.
    noverifier) NR_ACCESS_TAIL=" (the key verifier is missing from this install — reinstall the plugin)" ;;
    *)          NR_ACCESS_TAIL="" ;;
  esac
  # 4.9: the line NAMES THE REMEDY. "ask the owner" was true and useless — an Atlas
  # identity is now something the holder mints for themselves at the portal, so the one
  # line a keyless machine gets is the command that fixes it. The absolute path is the
  # point: a bare `atlas_auth.py login` is not runnable from wherever the session opened.
  # Without an absolute hook dir there is no honest command to print, so the sentence
  # says where to look instead of printing a path that would resolve somewhere else.
  if [ -n "$NR_HOOKDIR" ]; then
    NR_ACCESS_FIX="Log in:  python3 $NR_HOOKDIR/../skills/atlas/scripts/atlas_auth.py login   (or place the owner's access key)."
  else
    NR_ACCESS_FIX="Log in with skills/atlas/scripts/atlas_auth.py login in this plugin (or place the owner's access key)."
  fi
  echo "[notrest] notrest is part of Atlas — no Atlas identity on this machine. ${NR_ACCESS_FIX} The harness is inactive here.${NR_ACCESS_TAIL}"
  exit 0
fi

# ── THE ATLAS IDENTITY REFRESH (4.9). IDENTITY-CONTRACT §2: a token inside 7 days of exp
# is refreshed silently while online, JWKS is re-fetched so a rotated kid still verifies;
# §4: the revoked list is cached HERE, because "online sessions learn it at SessionStart"
# is the only moment the plugin is promised a network. All three are one bounded call —
# `atlas_auth.py sessionstart` — that always exits 0 and prints nothing.
#
# IT RUNS IN THE BACKGROUND, AND THAT IS THE WHOLE DESIGN. This hook's wall clock is
# session-start latency the owner pays on every single session; a network call inside it
# would put a hub outage (or a captive-portal hang) directly in front of every session on
# the machine. So the hook FIRES AND FORGETS: the work lands in ~/.notrest before the NEXT
# session start, which is exactly when a refresh is needed, and this session pays a fork.
#   · stdout and stderr both to /dev/null — SessionStart stdout is injected as session
#     context, so one stray line from the client would become tokens the owner pays for;
#     and a background job holding the hook's stdout open can hold the session open.
#   · a WATCHDOG, because macOS ships no `timeout(1)`: --budget-ms is the client's own
#     promise, and a promise is not a bound. A backgrounded process that hangs forever is
#     leaked, not harmless, so a sleeper kills it and is itself killed when it is not
#     needed. 6 s is 3x the budget — long enough that the watchdog never wins a race with
#     an honest client, short enough that a wedged one is gone before the next session.
#   · NO-OP UNTIL IT IS REAL: no token file (nobody has logged in) or no client on disk
#     (A3 has not landed / an older install) and nothing runs at all.
#   · a SYMLINKED client is refused, never followed — estate-root.sh refuses a symlinked
#     atlas.py for the same reason, and this one is EXECUTED.
NR_ATLAS_HOME="${NOTREST_HOME:-$HOME/.notrest}"
NR_ATLAS_AUTH="$NR_HOOKDIR/../skills/atlas/scripts/atlas_auth.py"
if [ -n "$NR_HOOKDIR" ] && [ -f "$NR_ATLAS_HOME/atlas-token" ] \
   && [ -f "$NR_ATLAS_AUTH" ] && [ ! -L "$NR_ATLAS_AUTH" ] && [ -x /usr/bin/python3 ]; then
  (
    /usr/bin/python3 "$NR_ATLAS_AUTH" sessionstart --budget-ms 2000 >/dev/null 2>&1 &
    NR_ATLAS_PID=$!
    ( sleep 6; kill -9 "$NR_ATLAS_PID" 2>/dev/null ) >/dev/null 2>&1 &
    NR_ATLAS_DOG=$!
    wait "$NR_ATLAS_PID" 2>/dev/null
    kill "$NR_ATLAS_DOG" 2>/dev/null
  ) >/dev/null 2>&1 &
  disown 2>/dev/null || true
fi

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
# CLAUDE_PLUGIN_ROOT is set by the plugin loader, and is NOT set when the hook is run
# any other way (a fixture, a shell, a loader that forgets) — the banner then printed
# "v?" and the one line that answers "is notrest installed?" said nothing. $0 always
# knows: this file lives at <plugin root>/hooks/, so the root is its parent (F7, 4.6.2).
NR_PLUG="${CLAUDE_PLUGIN_ROOT:-}"
[ -n "$NR_PLUG" ] || NR_PLUG="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
NV="$(sed -n 's/.*"version": "\([^"]*\)".*/\1/p' "$NR_PLUG/.claude-plugin/plugin.json" 2>/dev/null | head -1)"
echo "[notrest] v${NV:-?} @skills-dir — live from the repo tree (the /plugin UI hides skills-dir plugins; verify with: claude plugin list)"

# ── fable discipline: bolted to the metal. Unconditional every session so the
# working posture is present without anyone typing /fable-mode. The anchor is
# always in context; the full contract is one skill-load away. Trivial single-
# question turns may skip. stdout is injected as session context.
echo "[notrest] Fable discipline is active: ORIENT -> PROBE -> ACT -> PROVE -> BANK. Probe the live system before reasoning; a done/works/fixed claim needs in-transcript evidence (exit code, diff, status) or say 'unverified'; bank state before stopping. Full contract: /notrest:fable-mode."

# ── offload model policy: unconditional, so it reaches every fan-out surface
# (Agent tool, Workflow/ultracode, deep-research, review panels) even when no
# notrest skill is loaded. Owner-set 2026-07-15; amended 2026-09-01: the seat picks
# the model by task difficulty and records the choice in the brief.
echo "[notrest] HARD RULE — offload: the seat picks each lane's model BY TASK DIFFICULTY and DECLARES it in the brief — opus (tier: judgment) for design, debugging, kernel surfaces, reviews, anything ambiguous; sonnet (tier: bounded) when the done-when is a runnable check; opus when unsure (owner 2026-09-01). Never haiku, never subagent_type \"fork\" (forks inherit the seat); omitting model is a violation, not a default. Delegate via /notrest:agentswarm; builds run ONE persistent lane — feedback RESUMES it (SendMessage), never a new spawn. Receipts auto-log; never hand-log. Never /model-switch the seat."

# ── WILL THE PACKET FIRE? Decided BEFORE the continuity nudges, because those nudges
# ORDER a session to go read the very trail the packet is about to hand it. Field-proven
# 2026-09-01: a session given the packet still obeyed "read START-HERE.md before starting
# work" and "read its ledger tail before starting", re-derived everything, and burned
# ~88k tokens on an orientation the packet delivered for ~800 — and the START-HERE it
# dutifully read was five weeks stale. Two instructions that contradict each other are
# worse than either alone; the packet wins and the duplicated nudges stand down.
# This is only the CHEAP predicate (the same one the packet block re-tests); the packet
# still gates on exit code + terminator, and if it fails the nudges below are restored.
. "$(cd "$(dirname "$0")" && pwd)/estate-root.sh" 2>/dev/null || true
NR_PACKET_LIKELY=""
if [ -n "${NR_ESTATE_ROOT:-}" ] && [ -f "${NR_ESTATE_ROOT}/COORD.md" ] \
   && [ ! -e "${NR_ESTATE_ROOT}/.notrest-quiet" ] && [ ! -L "${NR_ESTATE_ROOT}/.notrest-quiet" ]; then
  for NR_F in AGENTS.md CLAUDE.md; do
    if [ -f "${NR_ESTATE_ROOT}/$NR_F" ] && grep -q '<!-- notrest:protocol v' "${NR_ESTATE_ROOT}/$NR_F" 2>/dev/null; then
      NR_PACKET_LIKELY=1; break
    fi
  done
fi

# ── continuity nudge: stdout is injected as session context.
if [ -f "START-HERE.md" ] && [ -z "$NR_PACKET_LIKELY" ]; then
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
  if [ -n "$NR_PACKET_LIKELY" ]; then
    # The tail is being handed over below; only the APPEND half of the law is owed here.
    echo "[notrest] COORD.md is live — append one honest line per substantive prompt when its work lands (ask -> landed | evidence). The trail tail is in the packet below; re-read it only if the packet is missing or you need more than its 8 lines."
  else
    echo "[notrest] COORD.md is live in this repo — read its ledger tail before starting (prior sessions' trail), and append one line per substantive prompt's work (ask -> landed | evidence)."
  fi
elif [ -z "$REPO_ROOT" ] && [ "$PWD" != "$HOME" ] && [ "$PWD" != "/" ]; then
  for NR_MARK in CLAUDE.md README.md package.json pyproject.toml; do
    if [ -e "$PWD/$NR_MARK" ]; then
      echo "[notrest] Project-like directory without git — estate hooks are limited here. Say /notrest to establish the harness in this project (COORD ledger + CLAUDE.md protocol)."
      break
    fi
  done
fi
# ── AUTO-CONTINUATION (owner-ordered, v4.5). A new session in an ESTABLISHED estate
# should arrive already knowing where the build stands — nobody types /notrest to find
# out what the last session did. A SessionStart hook's stdout IS session context, so the
# hook injects the packet itself.
#
# THE GATE IS CHEAP ON PURPOSE. `establish.py check` would answer "is this established?"
# authoritatively, but it would run python at EVERY session start in EVERY project just
# to decide whether to run python. So the gate is two file tests the hook can afford: a
# COORD.md, and a runtime foundation carrying a protocol marker. Both true is close
# enough to established that the packet is worth its cost; the packet itself then applies
# the real laws (containment, PASS states) and simply prints nothing when they fail.
#
# OPT-OUT: an estate that does not want this creates `.notrest-quiet` at its root and the
# packet is suppressed — the nudges stay. Some estates are noisy, and an injection nobody
# can turn off is a tax rather than a service. The test is `-e` OR `-L`, never `-f`: `-f`
# is FALSE for a directory named .notrest-quiet and FALSE for a dangling symlink, so both
# of those silently failed to opt the estate out. Anything present under that name — file,
# directory, live symlink, dangling symlink — is the owner saying no.
#
# SILENT ON FAILURE, ALWAYS. A missing, broken or unreadable establish.py, a refusal, an
# escaping ledger, a run that hangs — every one of them injects NOTHING and the session
# continues on the ordinary nudges. A convenience that can break a session start is not a
# convenience.
NR_QUIET="${REPO_ROOT:-/nonexistent}/.notrest-quiet"
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/COORD.md" ] && [ ! -e "$NR_QUIET" ] && [ ! -L "$NR_QUIET" ]; then
  NR_FOUNDED=""
  for NR_F in CLAUDE.md AGENTS.md; do
    if [ -f "$REPO_ROOT/$NR_F" ] && grep -q '<!-- notrest:protocol v' "$REPO_ROOT/$NR_F" 2>/dev/null; then
      NR_FOUNDED=1; break
    fi
  done
  if [ -n "$NR_FOUNDED" ]; then
    # hooks/ and skills/ are siblings in the plugin; resolved from THIS script's own
    # directory so it works from a skills-dir runtime, a marketplace install, or a copy.
    NR_EST="$(cd "$(dirname "$0")" && pwd)/../skills/notrest/scripts/establish.py"
    NR_BRIEF=""; NR_RC=1
    if [ -f "$NR_EST" ]; then
      # A WALL-CLOCK BOUND on the only unbounded thing this hook does. establish.py caps
      # what it reads, but a stalled filesystem or a pathological repo must not hold a
      # session start open; `timeout` is absent on stock macOS, so use it when present and
      # accept the unbounded call when it is not.
      if command -v timeout >/dev/null 2>&1; then
        NR_BRIEF="$(timeout 5 python3 "$NR_EST" continuation --brief --root "$REPO_ROOT" 2>/dev/null)"
      else
        NR_BRIEF="$(python3 "$NR_EST" continuation --brief --root "$REPO_ROOT" 2>/dev/null)"
      fi
      NR_RC=$?
    fi
    # THE GATE IS THE EXIT CODE, and then the TERMINATOR — never "did it print something".
    # establish.py prints its REFUSALS on stdout too ("NOT ESTABLISHED — … carries no
    # continuable estate", an escaping ledger), so a non-empty test injected refusals and
    # crash-truncated half-packets under a "this estate has a live build" preamble. Exit 0
    # says the run succeeded; the END marker says the packet arrived WHOLE. Nothing quoted
    # inside the packet can forge that marker: every data line is prefixed, so only this
    # script's own output can sit at column 0.
    if [ "$NR_RC" -eq 0 ] && printf '%s\n' "$NR_BRIEF" | grep -q '^notrest BRIEF PACKET END$'; then
      echo "[notrest] AUTO-CONTINUATION — this estate has a live build; you are its successor session. The brief packet follows; operate under the protocol from this turn (tier-0 verify only: doctor+eval+git vs the packet's claims; the trail wins over any recollection; bank one line when your first work lands). Full packet: /notrest."
      printf '%s\n' "$NR_BRIEF"
    fi
  fi
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
  COMPILE_DRAFTED="$(python3 -c 'import json,sys
try: c = json.load(open(sys.argv[1]))["candidates"]
except Exception: sys.exit(0)
d = [x for x in c if x.get("status") == "DRAFTED"]
if d: print(d[0]["slug"])' "$REPO_ROOT/compile/candidates.json" 2>/dev/null)"
  if [ -n "$COMPILE_TOP" ] || [ -n "$COMPILE_DRAFTED" ]; then
    CSLUG=""; CSEEN=""
    [ -n "$COMPILE_TOP" ] && read -r CSLUG CSEEN <<< "$COMPILE_TOP"
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
    if [ -n "$NR_AUTOBUILD" ] && [ -n "$CSLUG" ]; then
      echo "[notrest] AUTO-BUILD opted in: dispatch ONE opus builder lane this session for ripe candidate $CSLUG (/compile $CSLUG) — isolated under compile/$CSLUG/, benchmarked, receipted; NEVER installed: shipping stays the owner's act."
    elif [ -n "$CSLUG" ]; then
      echo "[notrest] Ripe compile candidate: $CSLUG seen ${CSEEN}x — repeated work the estate already recorded. Say /compile $CSLUG to move its stable parts into code (or compile.py decide --status DECLINED to silence)."
    fi
  fi
  # ── THE DRAFTED SLUG (4.7.0). `draft --all-ripe` runs from the pulse, so by the time a
  # session opens, the daemon may already have scaffolded a candidate. Naming it is the
  # difference between work waiting in the tree and work nobody knows about.
  if [ -n "$COMPILE_DRAFTED" ]; then
    if [ -n "$NR_AUTOBUILD" ]; then
      echo "[notrest] AUTO-BUILD dispatch ready: $COMPILE_DRAFTED is DRAFTED (contract + skeleton already scaffolded under compile/$COMPILE_DRAFTED/) — dispatch ONE opus builder lane for it this session. Isolated, benchmarked, receipted; NEVER installed: shipping stays the owner's act."
    else
      echo "[notrest] compile: $COMPILE_DRAFTED is DRAFTED and waiting under compile/$COMPILE_DRAFTED/ — say /compile $COMPILE_DRAFTED to build it, or compile.py decide --status DECLINED to retire it."
    fi
  fi
fi
# ── THE 24-HOUR GATE SWEEPER (refuter B3, 2026-09-05). A lane that dies without ever
# reaching SubagentStop — killed, crashed, the session closed — leaves its gates section
# behind, and an unretireable gate holds the seat's Stop red forever. Nothing else in the
# estate would ever clear it. So every session start retires any `## lane <key> · opened
# <ts>` section older than 24h and says so in COORD-AGENTS.md, where the lane's own row
# lives. Hand-written sections carry no `opened` stamp and are never touched.
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/gates/ACTIVE.md" ]; then
  NR_SWEPT="$(python3 -c '
import os, re, sys, time

gp = sys.argv[1]
try:
    with open(gp, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
except OSError:
    raise SystemExit(0)

now = time.time()
out, swept, skip = [], [], False
for ln in lines:
    m = re.match(r"^## lane ([0-9a-f]{4,32}) . opened "
                 r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$", ln)
    if m:
        try:
            age = now - time.mktime(time.strptime(m.group(2), "%Y-%m-%dT%H:%M:%SZ")) \
                + time.timezone
        except ValueError:
            age = 0
        if age > 86400:
            skip = True
            swept.append(m.group(1))
            continue
        skip = False
    elif skip and ln.startswith("## "):
        skip = False
    if not skip:
        out.append(ln)
if not swept:
    raise SystemExit(0)
while out and not out[-1].strip():
    out.pop()
# the same gate-less husk the ledger avoids: a file with no CHECK: left is exit 3 from
# gate-check ("declares no gate"), which blocks every Stop until someone deletes it
live = [l for l in out if l.strip() and not l.lstrip().startswith(("#", "<!--", "-->"))]
armed = [l for l in out if re.match(r"^\s{0,3}(?:[-*]\s+)?CHECK:", l)]
try:
    if not armed and not live:
        os.remove(gp)
    else:
        tmp = gp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        os.replace(tmp, gp)
except OSError:
    raise SystemExit(0)
sys.stdout.write(",".join(swept))' "$REPO_ROOT/gates/ACTIVE.md" 2>/dev/null)"
  if [ -n "$NR_SWEPT" ] && [ -f "$REPO_ROOT/COORD-AGENTS.md" ]; then
    # one row, in the ledger the lanes already write to — a gate that vanished without a
    # trace would be indistinguishable from one that was never written.
    printf -- '- [%s] gates SWEPT lane=%s | a gates/ACTIVE.md section outlived its 24h TTL and was retired at session start; the lane never reached SubagentStop\n' \
      "$(date -u '+%Y-%m-%d %H:%MZ')" "$NR_SWEPT" >> "$REPO_ROOT/COORD-AGENTS.md" 2>/dev/null
  fi
  [ -n "$NR_SWEPT" ] && echo "[notrest] gates: retired stale lane section(s) $NR_SWEPT from gates/ACTIVE.md (older than 24h — the lane never stopped)."
fi
# ── THE UNATTENDED DAEMON'S OWN STATUS (4.7.0). A daemon that stops working stops
# QUIETLY: on this estate the headless CLI's OAuth expired, every auto-run refused
# authorization, and nothing said so — the pulse simply produced no builds. lane C writes
# one overwritten line to pulse/auto-run.status; this surfaces it, but ONLY when it is bad
# news (BLOCKED / COOLDOWN). OK and IDLE stay silent: a daemon that is working is not news,
# and a banner every session is how a banner stops being read.
# `compile.py auto` is again the ONE reader of the marker — unattended-ness is its answer,
# not this hook's parse. The whole probe is behind a file test, so an estate without the
# daemon pays nothing. Under NOTREST_UNATTENDED=1 this hook has already exited: the runner
# is the daemon, and it does not need to be told about itself.
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/pulse/auto-run.status" ] \
   && [ -f "$NR_PLUG/skills/compile/scripts/compile.py" ]; then
  if python3 "$NR_PLUG/skills/compile/scripts/compile.py" auto --root "$REPO_ROOT" 2>/dev/null \
     | grep -q "unattended: YES"; then
    # ONCE PER UTC DAY (owner ruling, 2026-09-05). A stuck daemon stays stuck for as
    # long as it takes the owner to fix it, and a line that repeats every session is a
    # line that stops being read — the nag is how a real warning becomes wallpaper. The
    # stamp is a date in pulse/auto-run.banner-day, written ONLY when the banner actually
    # printed, so a day with no banner never spends the day's one telling.
    # BLOCKED auth carries the remedy; COOLDOWN does not — a cooldown needs no command,
    # it needs the clock.
    NR_ARSTAT="$(python3 -c '
import os, re, sys, time

status, stampf = sys.argv[1], sys.argv[2]
try:
    with open(status, "r", encoding="utf-8", errors="replace") as f:
        line = (f.readline() or "").strip()
except OSError:
    raise SystemExit(0)
# the state word is the one after the [stamp]; anything else is not this grammar
m = re.match(r"^\[[^\]]*\]\s+(BLOCKED|COOLDOWN)\b(.*)$", line)
if not m:
    raise SystemExit(0)

today = time.strftime("%Y-%m-%d", time.gmtime())
try:
    with open(stampf, "r", encoding="utf-8", errors="replace") as f:
        if f.read(32).strip() == today:
            raise SystemExit(0)          # already told today
except OSError:
    pass

out = line
if m.group(1) == "BLOCKED" and m.group(2).strip().lower().startswith("auth"):
    out += (" — run: python3 $CLAUDE_PLUGIN_ROOT/skills/compile/scripts/"
            "compile.py credential --setup")
out = out.encode("utf-8")[:240].decode("utf-8", "ignore")

try:
    tmp = stampf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(today + "\n")
    os.replace(tmp, stampf)              # stamped only because we are about to print
except OSError:
    pass                                 # unstampable: say it anyway, and say it again
sys.stdout.write(out)' \
      "$REPO_ROOT/pulse/auto-run.status" "$REPO_ROOT/pulse/auto-run.banner-day" 2>/dev/null)"
    [ -n "$NR_ARSTAT" ] && echo "[notrest] unattended compile: $NR_ARSTAT"
  fi
fi
# ── THE LEGACY MARKER (4.7.0): hoisted OUT of the ripe-candidate block above, where it
# only spoke when a NEW ripe candidate happened to exist — an estate whose authorization
# had silently stopped working could go a long time without being told. One line, and
# only when the old file is really there and no valid marker replaced it.
if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/compile/.auto-build" ] && [ -z "$NR_AUTOBUILD" ]; then
  echo "[notrest] compile/.auto-build is IGNORED since v4.5 — an in-estate marker is writable by any lane and travels with a clone, so it is not the owner's authorization. Re-authorize with: compile.py auto --on --root $REPO_ROOT (writes to ~/.notrest/auto-build/), then delete the old file."
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
