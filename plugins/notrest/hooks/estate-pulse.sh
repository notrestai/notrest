#!/bin/bash
# notrest estate-pulse — the background refresher for the PULSE LAYER.
#
# Owner's order (2026-08-05): "we need to write them automatically like what we do with
# coord.md — the files need to get created immediately at /notrest and then get written
# over at the end of each swarm, very fast in the background if possible, can happen all
# the time." So the instruments stop being on-demand and become MACHINE-WRITTEN READINGS,
# refreshed at the estate's own moments. This is the COORD principle — the machine writes,
# the session pays nothing — extended from ledgers to readings.
#
# NEVER REGISTERED AS ITS OWN EVENT. Other hooks call it; it has no hooks.json entry.
# CALLERS DETACH IT (subshell + &, the session-start git-pull pattern), so a caller
# returns in milliseconds no matter how long the instruments take.
#
# NEVER WRITES COORD. A pulse per lane-stop would spam the ledger into uselessness; the
# `[pulse]` COORD line stays a deliberate act by pulse.sh. This layer writes only pulse/.
#
# Silent on every failure. Always exit 0. Never blocks its caller.
#
# THE HEARTBEAT MARKER (owner, 2026-08-05): "having a marker in the coord or any file that
# will say where and when the last checkpoint was". pulse.json carries `generated` (WHEN)
# and `trigger` (WHAT fired it) — together they are the checkpoint, and every reader shows
# both, so a pulse that quietly stopped is visible as an old stamp rather than as silence.
#
# Usage: bash estate-pulse.sh [ROOT] [TRIGGER]
#   TRIGGER ∈ lane-stop | session-end | establish | prompt-stale | manual   (default manual)

# ── DAEMON REPARENTING (live-proven 2026-08-05, on the lane that built this).
# "Detached" used to mean `( cmd & )` — backgrounded, but still a CHILD of the spawner.
# That is not enough: the Claude harness notifies a finished agent only when it has NO
# live background children, so a long-running refresher held its spawning lane in
# mid-turn state forever. The lane looked DEAD from outside while it was working, the
# seat concluded it had hung, and killed it. A daemon that stays parented to its spawner
# can therefore cost you the agent that started it.
# So: double-fork + setsid. The worker is reparented to init, owns no controlling
# terminal, and is nobody's child. NR_PULSE_DAEMON=1 marks the re-exec — and doubles as
# the FOREGROUND escape hatch fixtures use to run this synchronously.
if [ -z "${NR_PULSE_DAEMON:-}" ]; then
  NR_PULSE_DAEMON=1 python3 -c '
import os, sys
if os.fork() > 0:            # spawner returns in milliseconds
    sys.exit(0)
os.setsid()                  # new session: no controlling terminal
if os.fork() > 0:            # orphan the worker -> reparented to init
    os._exit(0)
fd = os.open(os.devnull, os.O_RDWR)
os.dup2(fd, 0); os.dup2(fd, 1); os.dup2(fd, 2)
os.execv("/bin/bash", ["bash"] + sys.argv[1:])
' "$0" "$@" >/dev/null 2>&1 </dev/null
  exit 0
fi

# ── the estate root: the same shared resolver every other estate hook uses, so the
# pulse lands in the project the session actually belongs to.
NR_PULSE_ROOT="${1:-}"
NR_PULSE_TRIGGER="${2:-manual}"
if [ -z "$NR_PULSE_ROOT" ]; then
  . "$(cd "$(dirname "$0")" && pwd)/estate-root.sh" 2>/dev/null || true
  NR_PULSE_ROOT="${NR_ESTATE_ROOT:-}"
fi
[ -n "$NR_PULSE_ROOT" ] || exit 0
[ -d "$NR_PULSE_ROOT" ] || exit 0

NR_SKILLS="$(cd "$(dirname "$0")/../skills" 2>/dev/null && pwd)"
[ -n "$NR_SKILLS" ] || exit 0

export NR_PULSE_ROOT NR_SKILLS NR_PULSE_TRIGGER
python3 <<'PY' >/dev/null 2>&1 || true
import fcntl, hashlib, json, os, subprocess, sys, time

DEBOUNCE = 60.0          # seconds; a swarm landing five lanes must produce ONE refresh

try:
    root = os.environ["NR_PULSE_ROOT"]
    skills = os.environ["NR_SKILLS"]
    pdir = os.path.join(root, "pulse")
    os.makedirs(pdir, exist_ok=True)

    # ── DEBOUNCE + MUTUAL EXCLUSION, one lock for both. A non-blocking flock means a
    # refresh already running simply yields — five stops in two minutes do not queue
    # five refreshes behind each other.
    lockf = os.open(os.path.join(pdir, ".lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)                       # someone else is refreshing; nothing to add

    stamp = os.path.join(pdir, "pulse.json")
    if os.path.exists(stamp) and (time.time() - os.path.getmtime(stamp)) < DEBOUNCE:
        sys.exit(0)                       # fresh enough; the layer is eventually-fresh

    def run(argv, timeout):
        t0 = time.time()
        try:
            p = subprocess.run(argv, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=timeout)
            out = p.stdout.decode("utf-8", "replace")
            code = p.returncode
        except (OSError, subprocess.SubprocessError) as exc:
            out, code = "pulse: could not run %s (%s)\n" % (argv[0], exc), None
        return out, code, round(time.time() - t0, 2)

    def verdict(text):
        """The instrument's own last spoken line — never a re-interpretation of it."""
        lines = [l.rstrip() for l in text.splitlines() if l.strip()]
        return lines[-1][:300] if lines else "(no output)"

    py = sys.executable or "python3"
    jobs = [
        ("eval",     [py, os.path.join(skills, "eval/scripts/eval.py"), "check", "--root", root], 120),
        ("compile",  [py, os.path.join(skills, "compile/scripts/compile.py"), "scan", "--root", root], 180),
        ("swarm",    [py, os.path.join(skills, "agentswarm/scripts/swarm.py"), "report", "--root", root], 120),
        ("doctor",   [py, os.path.join(skills, "doctor/scripts/doctor.py"), "check", "--root", root], 180),
    ]

    # DOCTOR COST RULING (2026-08-05, measured on this machine before deciding): doctor's
    # TOKEN BUDGET check shells out to the `claude` CLI, and the fear was 10-30s. Measured:
    # the CLI call is ~1s and a FULL doctor run is ~1s — while `compile scan` is ~8s and is
    # the actual cost of this layer. So doctor runs COMPLETE and UNMODIFIED here. No skip
    # flag, no cached substitute: a background layer whose doctor means something different
    # from the doctor a human runs is a layer that lies quietly, and that is worse than a
    # layer that takes an extra second in a detached subshell nobody is waiting on.
    # ── INPUT-STAMP SKIP, adapted from cloudflare-os's run-local input stamping
    # (Apache 2.0). `compile scan` is this layer's 8s heavyweight and its inputs move
    # rarely: hash what it actually reads, and when nothing moved, reuse the previous
    # verdict. DISCLOSURE LAW: the pulse never lies about what ran — a skipped scan says
    # SKIPPED, names the stamp it matched, and carries the prior verdict forward as prior.
    def compile_stamp():
        parts = []
        for rel in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            if rel.startswith("COORD") and rel.endswith(".md"):
                parts.append(rel)
        parts += [os.path.join("archive", "findings.jsonl")]
        sig = []
        for rel in parts:
            fp = os.path.join(root, rel)
            try:
                st = os.stat(fp)
                sig.append("%s:%d:%d" % (rel, int(st.st_mtime), st.st_size))
            except OSError:
                sig.append("%s:-" % rel)
        return hashlib.sha256("|".join(sig).encode("utf-8")).hexdigest()[:16]

    stamp_file = os.path.join(pdir, ".compile-stamp")
    cur_stamp = compile_stamp()
    prev_stamp = ""
    try:
        prev_stamp = open(stamp_file, encoding="utf-8").read().strip()
    except OSError:
        prev_stamp = ""

    summary = {}
    for name, argv, tmo in jobs:
        if name == "compile" and cur_stamp == prev_stamp and prev_stamp:
            prior = ""
            try:
                prior = open(os.path.join(pdir, "compile.txt"),
                             encoding="utf-8", errors="replace").read()
            except OSError:
                prior = ""
            body = ("# SKIPPED — compile scan inputs unchanged since stamp %s\n"
                    "# (COORD volumes + COORD-AGENTS + archive/findings.jsonl: same\n"
                    "#  mtimes and sizes). The verdict below is the PRIOR scan's, carried\n"
                    "#  forward unchanged — it was not re-measured on this pulse.\n\n"
                    % cur_stamp) + prior
            tmp = os.path.join(pdir, ".compile.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(body)
            os.replace(tmp, os.path.join(pdir, "compile.txt"))
            summary[name] = {"exit": None, "verdict": "SKIPPED — inputs unchanged since "
                             "stamp %s (prior verdict carried forward)" % cur_stamp,
                             "secs": 0.0, "skipped": True,
                             "file": "pulse/%s.txt" % name}
            continue
        out, code, secs = run(argv, tmo)
        head = ("# notrest pulse — %s\n# machine-written, derived, disposable: the ledgers\n"
                "# remain the record. Regenerated in the background; do not hand-edit.\n"
                "# exit=%s  wall=%ss\n\n" % (name, code, secs))
        if name == "doctor":
            head += ("# every check ran, TOKEN BUDGET included (measured ~1s on the machine\n"
                     "# this layer was built for). Nothing is skipped or cached here.\n\n")
        tmp = os.path.join(pdir, ".%s.tmp" % name)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(head + out)
        os.replace(tmp, os.path.join(pdir, "%s.txt" % name))
        summary[name] = {"exit": code, "verdict": verdict(out), "secs": secs,
                         "skipped": False, "file": "pulse/%s.txt" % name}
        if name == "compile":
            try:
                with open(stamp_file, "w", encoding="utf-8") as f:
                    f.write(cur_stamp)
            except OSError:
                pass

    live = {}
    lv = os.path.join(pdir, "swarm-live.txt")
    try:
        if os.path.isfile(lv):
            txt = open(lv, encoding="utf-8", errors="replace").read()
            live = {"file": "pulse/swarm-live.txt",
                    "age_secs": int(time.time() - os.path.getmtime(lv)),
                    "alerts": [l.strip() for l in txt.splitlines()
                               if l.startswith("ALERT")][:10]}
    except OSError:
        live = {}

    blob = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "trigger": os.environ.get("NR_PULSE_TRIGGER", "manual"),
        "swarm_live": live,
        "root": root,
        "debounce_secs": DEBOUNCE,
        "note": ("derived and disposable — regenerated in the background at estate moments; "
                 "eventually-fresh, not realtime"),
        "instruments": summary,
    }
    tmp = os.path.join(pdir, ".pulse.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(blob, f, indent=1, sort_keys=True)
    os.replace(tmp, stamp)                 # atomic: a reader never sees a half-written pulse
except Exception:
    pass
sys.exit(0)
PY

exit 0
