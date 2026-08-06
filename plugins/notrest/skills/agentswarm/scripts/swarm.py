#!/usr/bin/env python3
"""swarm.py — the decomposition gauge.

The swarm had a computed decomposition (`graph.py domains`) and a speed law, and no way
to tell whether either was working. This reads the receipts the estate already writes and
answers one question: **were the lanes the right size?**

    report [--root .] [--window 7d] [--json]

Joins `spend/ledger.md` (the receipts) with `COORD-AGENTS.md` (the transcript pointers)
and `briefs/` (the banked commissions), one row per lane, then bands each lane by the two
numbers that describe its size: **tool calls** and **wall-clock**.

THE BAND IS MEASURED, NOT INVENTED. Its numbers come from this estate's own receipts —
narrow lanes clustered at ~20 calls / ~3.5 min, monoliths at 72-77 calls / 22-24 min — so:

    GREEN     <= 30 calls AND <= 10 min
    WIDE      anything between (a note, not a flag)
    MONOLITH  >= 45 calls OR >= 15 min

TWO-SIDED ON PURPOSE. A gauge that only rewards smaller lanes drives you off the other
cliff, so rework is reported beside size: gate and correction lines in the same window.
Lanes shrinking while rework climbs is over-decomposition, and the pairing is the metric.

Constraints: python3 stdlib only, zero model calls, no network. The window is measured
back from the NEWEST RECEIPT rather than the wall clock, so two runs over an unchanged
estate are byte-identical. The script reports; the seat judges.

Exit: 0 all green · 5 monoliths and/or degraded receipts present · 6 no usable data · 2 usage.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

EXIT_OK, EXIT_USAGE, EXIT_FLAGGED, EXIT_NODATA = 0, 2, 5, 6

GREEN_CALLS, GREEN_SECS = 30, 10 * 60
MONO_CALLS, MONO_SECS = 45, 15 * 60

RECEIPT_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+lane=(?P<lane>\S+)\s+model=(?P<model>\S+)\s+"
    r"tokens=(?P<tokens>\S+)\s+grade=(?P<grade>\S+)")
CALLS_RE = re.compile(r"\bcalls=(\S+)")
SECS_RE = re.compile(r"\bsecs=(\S+)")
AGENT_RE = re.compile(r"\bagent=(\S+)")
AGENTS_LINE_RE = re.compile(r"^- \[(?P<ts>[^\]]+)\]\s+agent=(?P<agent>\S+)")
TRANSCRIPT_RE = re.compile(r"\btranscript:\s*(\S+)")
COORD_TS_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})Z\]")
GATE_RE = re.compile(r"\bgat(?:e|es|ed|ing)\b", re.I)
CORR_RE = re.compile(r"(\bcorrection\b|\bcorrected\b|\brevert\w*\b|\brolled back\b|"
                     r"\brollback\b|\bwithdraw\w*\b|\bre-?work\b|\brepair\w*\b)", re.I)


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def parse_ts(v):
    """Receipt/ledger stamps are 'YYYY-MM-DD HH:MMZ' — 16 chars plus the Z, and slicing
    17 kept the Z, so every stamp silently failed to parse and --window filtered nothing.
    Unparseable → None, never a guess."""
    try:
        return datetime.strptime(v.strip()[:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def derive_from_transcript(path):
    """(calls, secs) for a receipt written before the hook recorded them. Reads the file
    the ledger already points at — zero model tokens. Unreadable → (None, None)."""
    if not path or not os.path.isfile(path):
        return None, None
    calls, first, last = 0, "", ""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                for k in ("timestamp", "ts", "time"):
                    v = obj.get(k)
                    if isinstance(v, str) and v:
                        first = first or v
                        last = v
                        break
                msg = obj.get("message")
                content = msg.get("content") if isinstance(msg, dict) else obj.get("content")
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            calls += 1
    except OSError:
        return None, None
    secs = None
    if first and last:
        try:
            f2 = lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))
            secs = int(round((f2(last) - f2(first)).total_seconds()))
        except ValueError:
            secs = None
    return calls, secs


def band(calls, secs):
    """(band, why) — the verdict AND the number that tripped it. A threshold reported
    without its measurement is an opinion."""
    if calls is None and secs is None:
        return "UNKNOWN", "no calls/secs on the receipt and no readable transcript"
    c = calls if calls is not None else 0
    s = secs if secs is not None else 0
    if c >= MONO_CALLS:
        return "MONOLITH", "%d calls >= %d" % (c, MONO_CALLS)
    if s >= MONO_SECS:
        return "MONOLITH", "%dm %ds >= %dm" % (s // 60, s % 60, MONO_SECS // 60)
    if c <= GREEN_CALLS and s <= GREEN_SECS:
        return "GREEN", "%d calls, %dm %ds" % (c, s // 60, s % 60)
    return "WIDE", "%d calls, %dm %ds" % (c, s // 60, s % 60)


def pct(vals, p):
    """Nearest-rank percentile — no interpolation, so the number printed is a number a
    lane actually recorded."""
    if not vals:
        return None
    xs = sorted(vals)
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * len(xs) + 0.5)) - 1))
    return xs[k]


def collect(root, window_days):
    receipts = []
    for line in (read(os.path.join(root, "spend", "ledger.md")) or "").splitlines():
        m = RECEIPT_RE.match(line.strip())
        if not m or m.group("lane") == "seat":
            continue
        a = AGENT_RE.search(line)
        c, s = CALLS_RE.search(line), SECS_RE.search(line)
        num = lambda mm: (int(mm.group(1)) if mm and mm.group(1).isdigit() else None)
        receipts.append({
            "ts": m.group("ts").strip(), "when": parse_ts(m.group("ts")),
            "lane": m.group("lane"), "model": m.group("model"),
            "tokens": m.group("tokens"), "grade": m.group("grade"),
            "agent": a.group(1) if a else "?",
            "calls": num(c), "secs": num(s),
        })
    if not receipts:
        return None, [], {}, 0

    newest = max([r["when"] for r in receipts if r["when"]] or [None])
    if newest and window_days:
        cutoff = newest - timedelta(days=window_days)
        receipts = [r for r in receipts if r["when"] and r["when"] >= cutoff]

    transcripts = {}
    for line in (read(os.path.join(root, "COORD-AGENTS.md")) or "").splitlines():
        m = AGENTS_LINE_RE.match(line)
        if not m:
            continue
        t = TRANSCRIPT_RE.search(line)
        if t and t.group(1) != "?":
            transcripts[m.group("agent")] = t.group(1)

    try:
        briefs = {f[len("agent-"):-3] for f in os.listdir(os.path.join(root, "briefs"))
                  if f.startswith("agent-") and f.endswith(".md")}
    except OSError:
        briefs = set()

    for r in receipts:
        if r["calls"] is None and r["secs"] is None:
            c, s = derive_from_transcript(transcripts.get(r["agent"]))
            r["calls"], r["secs"] = c, s
            r["derived"] = c is not None or s is not None
        else:
            r["derived"] = False
        r["brief"] = r["agent"] in briefs
        r["band"], r["why"] = band(r["calls"], r["secs"])
        r["degraded"] = (r["model"] == "?" or r["tokens"] == "unknown")
    return newest, receipts, transcripts, len(briefs)


def rework(root, receipts):
    """Gate and correction lines inside the window — the other half of the metric."""
    lo = min([r["when"] for r in receipts if r["when"]] or [None])
    gates = corrections = 0
    for line in (read(os.path.join(root, "COORD.md")) or "").splitlines():
        m = COORD_TS_RE.match(line)
        if not m:
            continue
        when = parse_ts("%s %sZ" % (m.group(1), m.group(2)))
        if lo and when and when < lo:
            continue
        if CORR_RE.search(line):
            corrections += 1
        elif GATE_RE.search(line):
            gates += 1
    return gates, corrections


def build(root, window_days):
    newest, receipts, _t, nbriefs = collect(root, window_days)
    if not receipts:
        return None
    calls = [r["calls"] for r in receipts if r["calls"] is not None]
    secs = [r["secs"] for r in receipts if r["secs"] is not None]
    gates, corrections = rework(root, receipts)
    monoliths = [r for r in receipts if r["band"] == "MONOLITH"]
    degraded = [r for r in receipts if r["degraded"]]
    return {
        "root": root,
        "window_days": window_days,
        "window_anchor": newest.strftime("%Y-%m-%d %H:%MZ") if newest else None,
        "lanes": len(receipts),
        "band_green": sum(1 for r in receipts if r["band"] == "GREEN"),
        "band_wide": sum(1 for r in receipts if r["band"] == "WIDE"),
        "band_monolith": len(monoliths),
        "band_unknown": sum(1 for r in receipts if r["band"] == "UNKNOWN"),
        "calls_median": pct(calls, 50), "calls_p90": pct(calls, 90),
        "calls_max": max(calls) if calls else None,
        "secs_max": max(secs) if secs else None,
        "receipts_degraded": len(degraded),
        "briefs_banked": sum(1 for r in receipts if r["brief"]),
        "briefs_on_disk": nbriefs,
        "rework_gates": gates, "rework_corrections": corrections,
        "thresholds": {"green_calls": GREEN_CALLS, "green_secs": GREEN_SECS,
                       "monolith_calls": MONO_CALLS, "monolith_secs": MONO_SECS},
        "background": background_inventory(),
        "rows": [{k: r[k] for k in ("ts", "agent", "model", "tokens", "calls", "secs",
                                    "brief", "band", "why", "degraded", "derived")}
                 for r in receipts],
    }


def hm(s):
    return "?" if s is None else "%dm%02ds" % (s // 60, s % 60)


def cmd_report(args):
    root = os.path.realpath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        sys.stderr.write("swarm: not a directory: %s\n" % root)
        return EXIT_USAGE
    m = re.match(r"^(\d+)d?$", str(args.window or "").strip()) if args.window else None
    if args.window and not m:
        sys.stderr.write("swarm: --window wants <n>d, got %r\n" % args.window)
        return EXIT_USAGE
    days = int(m.group(1)) if m else 0
    rep = build(root, days)
    if rep is None:
        if args.json:
            print(json.dumps({"root": root, "lanes": 0, "usable": False},
                             indent=1, sort_keys=True))
        else:
            print("swarm: NO USABLE DATA — no subagent receipts in %s/spend/ledger.md. "
                  "Lanes receipt themselves at SubagentStop; run a swarm first." % root)
        return EXIT_NODATA
    if args.json:
        print(json.dumps(rep, indent=1, sort_keys=True))
    else:
        print("swarm report — %s" % root)
        print("  window: %s (anchored on the newest receipt %s — not the wall clock, so "
              "this report is reproducible)"
              % ("all receipts" if not days else "last %dd" % days, rep["window_anchor"]))
        print("  band: GREEN <=%d calls AND <=%dm · MONOLITH >=%d calls OR >=%dm · "
              "between = WIDE" % (GREEN_CALLS, GREEN_SECS // 60, MONO_CALLS, MONO_SECS // 60))
        print()
        print("  %-4s %-19s %-22s %8s %6s %7s %-6s %s"
              % ("", "agent", "model", "tokens", "calls", "secs", "brief", "band"))
        for r in rep["rows"]:
            mark = {"MONOLITH": "!!", "WIDE": " ~", "UNKNOWN": " ?"}.get(r["band"], "  ")
            print("  %-4s %-19s %-22s %8s %6s %7s %-6s %s (%s)%s"
                  % (mark, r["agent"][:19], r["model"][:22], r["tokens"],
                     "?" if r["calls"] is None else r["calls"], hm(r["secs"]),
                     "yes" if r["brief"] else "no", r["band"], r["why"],
                     " [derived]" if r["derived"] else ""))
        print()
        print("  lanes: %d · green %d · wide %d · MONOLITH %d · unknown %d"
              % (rep["lanes"], rep["band_green"], rep["band_wide"],
                 rep["band_monolith"], rep["band_unknown"]))
        print("  calls/lane: median %s · p90 %s · max %s"
              % (rep["calls_median"], rep["calls_p90"], rep["calls_max"]))
        print("  longest lane: %s" % hm(rep["secs_max"]))
        print("  commissions banked: %d/%d lanes" % (rep["briefs_banked"], rep["lanes"]))
        print("  REWORK in window: %d gate line(s) · %d correction line(s)"
              % (rep["rework_gates"], rep["rework_corrections"]))
        print("    the band is TWO-SIDED: rework climbing while lanes shrink is "
              "over-decomposition, not progress")
        if rep["receipts_degraded"]:
            print("  DEGRADED RECEIPTS: %d of %d carry model=? or tokens=unknown — the "
                  "band cannot see those lanes" % (rep["receipts_degraded"], rep["lanes"]))
        verdict = ("FLAGGED" if (rep["band_monolith"] or rep["receipts_degraded"])
                   else "IN BAND")
        code = (EXIT_FLAGGED if (rep["band_monolith"] or rep["receipts_degraded"])
                else EXIT_OK)
        # LIVE SECTION — deliberately OUTSIDE the byte-identical guarantee. Everything
        # above reads the estate and is reproducible; this reads the PROCESS TABLE, whose
        # ages tick and whose rows come and go. Marked so a reader (and a fixture) knows
        # which half is the reproducible reading and which is a live probe.
        bg = background_inventory()
        print("\n  background: %d notrest process(es) live  [LIVE — not part of the "
              "byte-identical reading above]" % len(bg))
        for b in bg:
            print("    pid %-7s ppid %-6s age %-11s %s%s"
                  % (b["pid"], b["ppid"], b["age"], b["cwd"],
                     ("  [" + " ".join(b["flags"]) + "]") if b["flags"] else ""))
        if not bg:
            print("    (none — no refreshers or watchers running for any project)")
        print("\nswarm: %s — %d lane(s), %d monolith(s), %d degraded receipt(s) (exit %d)"
              % (verdict, rep["lanes"], rep["band_monolith"], rep["receipts_degraded"], code))
    return (EXIT_FLAGGED if (rep["band_monolith"] or rep["receipts_degraded"]) else EXIT_OK)


# ---------------------------------------------------------------- the watcher
# The owner asked for "always running a lane for checking on them". The suite's economics
# law says script where script suffices, so this is a DETACHED POLLER, not a lane: zero
# model tokens, no context, no seat attention until it has something to say.
STALL_SECS = 10 * 60          # transcript frozen this long, never receipted → STALL
# DISCOVERY WINDOW (2026-08-05, seat-proven on the real estate): without one, every
# transcript ever written counted as a running lane. An eleven-day-old transcript from
# the degraded-receipt era — no receipt ever landed — was classified `running` and raised
# a permanent false STALL, and the prompt banner fired "41 alert(s)" at the owner.
# UNRECEIPTED HISTORY IS NOT A RUNNING LANE. A transcript qualifies as live only if it
# moved within this window or postdates the watcher's own start; everything older is
# counted in the header as unreceipted-history — visible, and never an alert.
WATCH_WINDOW = 24 * 3600
# Overridable ONLY so the fixture can exercise the DAEMON LOOP in seconds instead of
# minutes. The loop path shipped broken once (NameError at birth) because every fixture
# ran --once and no test ever entered the loop — a vacuous pass on the process dimension.
POLL_SECS = float(os.environ.get("NOTREST_WATCH_POLL", "30"))
QUIET_ROUNDS = int(os.environ.get("NOTREST_WATCH_QUIET", "4"))


def project_slug(root):
    return "-" + os.path.realpath(root).lstrip("/").replace("/", "-")


def transcript_sources(root):
    """[(label, path, agent_id)] across EVERY location a lane may transcribe to.

    LIVE FINDING 2026-08-05: the first real swarm under the new laws read `watching 0`
    and self-terminated seconds after dispatch. Its lanes were transcribing to the
    SESSION TASKS DIR — `/private/tmp/claude-501/<slug>/<session>/tasks/<agent-id>.output`
    — not to `~/.claude/projects/<slug>/**/subagents/`. The disclosed limit ("a lane
    transcribing elsewhere is invisible") turned out to cover the PRIMARY case: lanes
    spawned by the Agent tool in this harness's own sessions. Both locations are now
    swept, and the header says what each contributed.

    Deduped by AGENT ID, because in some sessions the tasks entry is a SYMLINK back into
    the classic location — the same lane, reachable two ways, must count once."""
    slug = project_slug(root)
    seen, out = {}, []

    classic = os.path.expanduser(os.path.join("~/.claude/projects", slug))
    if os.path.isdir(classic):
        for d, _sub, files in os.walk(classic):
            if os.path.basename(d) != "subagents":
                continue
            for fn in files:
                if fn.startswith("agent-") and fn.endswith(".jsonl"):
                    aid = fn[len("agent-"):-len(".jsonl")]
                    if aid not in seen:
                        seen[aid] = 1
                        out.append(("classic", os.path.join(d, fn), aid))

    tasks_base = os.path.join("/private/tmp/claude-501", slug)
    if os.path.isdir(tasks_base):
        try:
            sessions = os.listdir(tasks_base)
        except OSError:
            sessions = []
        for sess in sessions:
            td = os.path.join(tasks_base, sess, "tasks")
            if not os.path.isdir(td):
                continue
            try:
                files = os.listdir(td)
            except OSError:
                continue
            for fn in files:
                if not fn.endswith(".output"):
                    continue
                aid = fn[:-len(".output")]
                if aid in seen:
                    continue          # same lane, already found via the classic path
                seen[aid] = 1
                out.append(("tasks", os.path.join(td, fn), aid))
    return out


def live_lanes(root, receipted, started=None):
    """(rows, watched, history). Rows are transcripts inside the discovery window; history
    counts older, never-receipted ones, which are reported and never alerted."""
    sources = transcript_sources(root)
    if not sources:
        return [], 0, 0, {"classic": 0, "tasks": 0}
    rows, now, history = [], time.time(), 0
    by_loc = {"classic": 0, "tasks": 0}
    floor = now - WATCH_WINDOW
    if started:
        floor = min(floor, started)
    for label, path, agent in sources:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime < floor:
            if agent not in receipted:
                history += 1
            continue
        calls, _secs = derive_from_transcript(path)
        by_loc[label] = by_loc.get(label, 0) + 1
        rows.append({"agent": agent, "calls": calls or 0, "loc": label,
                     "idle_secs": int(now - mtime),
                     "receipted": agent in receipted, "path": path})
    rows.sort(key=lambda r: r["idle_secs"])
    return rows, len(rows), history, by_loc


def sweep(root, started=None):
    """One pass. Returns (lines, alerts, active) — the report, its alerts, and how many
    lanes still look alive."""
    receipted = set()
    for line in (read(os.path.join(root, "spend", "ledger.md")) or "").splitlines():
        a = AGENT_RE.search(line)
        if a:
            receipted.add(a.group(1))
    rows, watched, history, by_loc = live_lanes(root, receipted, started)
    lines, alerts, active = [], [], 0
    lines.append("# notrest swarm watch — machine-written, derived, disposable")
    lines.append("# watching %d transcript(s) this poller can SEE — %d from the classic "
                 "store (~/.claude/projects/<slug>/**/subagents), %d from the session tasks "
                 "dir (/private/tmp/claude-501/<slug>/*/tasks); deduped by agent id"
                 % (watched, by_loc.get("classic", 0), by_loc.get("tasks", 0)))
    lines.append("# unreceipted-history: %d (older than %dh and never receipted — shown "
                 "here, never alerted: old work is not a running lane)"
                 % (history, WATCH_WINDOW // 3600))
    bg = background_inventory()
    lines.append("# background: %d notrest process(es) live%s"
                 % (len(bg), "".join("\n#   pid %s ppid %s age %s %s%s"
                    % (b["pid"], b["ppid"], b["age"], b["cwd"],
                       ("  [" + " ".join(b["flags"]) + "]") if b["flags"] else "")
                    for b in bg)))
    lines.append("")
    for r in rows:
        if r["receipted"]:
            state = "done"
        else:
            active += 1
            state = "running"
        lines.append("  %-19s %-8s calls=%-4d idle=%dm%02ds"
                     % (r["agent"][:19], state, r["calls"],
                        r["idle_secs"] // 60, r["idle_secs"] % 60))
        if not r["receipted"] and r["idle_secs"] >= STALL_SECS:
            alerts.append("ALERT STALL %s — no transcript growth for %dm and no receipt; "
                          "probe, resume or stop it"
                          % (r["agent"][:19], r["idle_secs"] // 60))
        if not r["receipted"] and r["calls"] >= MONO_CALLS:
            alerts.append("ALERT MONOLITH-IN-PROGRESS %s — %d live calls past the %d band "
                          "while still running; the NEXT contract for this work splits further"
                          % (r["agent"][:19], r["calls"], MONO_CALLS))
    return lines + ([""] + alerts if alerts else []), alerts, active


BG_PATTERNS = ("estate-pulse.sh", "swarm.py watch")


def background_inventory():
    """Live notrest background processes: what is actually running, how old, and where.
    Answers "is anything still going?" with a reading instead of pgrep archaeology —
    and flags the two species that bite: ancient survivors, and workers whose cwd is a
    temp/fixture path (a wedged sandbox child, which is how a working lane got killed
    on 2026-08-05). Best-effort by construction: ps output is the only source."""
    rows = []
    try:
        out = subprocess.run(["ps", "-eo", "pid=,ppid=,etime=,command="],
                             stdout=subprocess.PIPE, timeout=10
                             ).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return rows
    for line in out.splitlines():
        if not any(pat in line for pat in BG_PATTERNS):
            continue
        if " -eo " in line or "grep " in line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, etime, cmd = parts
        cwd = ""
        for tok in cmd.split():
            if tok.startswith("/") and os.path.isdir(tok):
                cwd = tok
                break
        flags = []
        # etime is [[dd-]hh:]mm:ss — a dash or 3 colon-groups means >= a day
        if "-" in etime or etime.count(":") >= 2:
            flags.append("ANCIENT>24h")
        low = (cwd or cmd).lower()
        if any(k in low for k in ("/tmp", "/var/folders", "fixture", "/t/tmp.")):
            flags.append("TEMP/FIXTURE-CWD")
        if ppid.strip() not in ("1",):
            flags.append("PARENTED(ppid=%s)" % ppid.strip())
        rows.append({"pid": pid, "ppid": ppid, "age": etime,
                     "cwd": cwd or "?", "flags": flags,
                     "cmd": cmd[:110]})
    return rows


def daemonize():
    """Double-fork + setsid. DAEMON REPARENTING (live-proven 2026-08-05): a background
    process that stays a CHILD of its spawner holds that agent in mid-turn state — the
    harness notifies a finished agent only when it has no live children — so a watcher
    parented to the lane that started it makes that lane look dead and gets it killed.
    The worker must be nobody's child."""
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    fd = os.open(os.devnull, os.O_RDWR)
    os.dup2(fd, 0); os.dup2(fd, 1); os.dup2(fd, 2)


def cmd_watch(args):
    root = os.path.realpath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        sys.stderr.write("swarm: not a directory: %s\n" % root)
        return EXIT_USAGE
    pdir = os.path.join(root, "pulse")
    try:
        os.makedirs(pdir, exist_ok=True)
    except OSError:
        return EXIT_NODATA
    out = os.path.join(pdir, "swarm-live.txt")

    def write(lines):
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, out)

    started = time.time()
    if not args.once and not args.foreground:
        daemonize()
    if args.once:
        lines, alerts, _active = sweep(root, started)
        write(lines)
        return EXIT_FLAGGED if alerts else EXIT_OK

    quiet, seen = 0, {}
    while True:
        lines, alerts, active = sweep(root, started)
        write(lines)
        sig = {}
        for l in lines:
            if l.startswith("  "):
                sig[l[:40]] = l
        if sig == seen and not active:
            quiet += 1
        elif not active:
            # nothing inside the discovery window at all: there is no swarm to watch.
            quiet += 1
        else:
            quiet = 0
        seen = sig
        # SELF-TERMINATION: every lane receipted and nothing grew for QUIET_ROUNDS polls.
        # A watcher that outlives its swarm is a background process nobody asked for.
        if quiet >= QUIET_ROUNDS:
            write(lines + ["", "# watch ended: every known lane receipted and nothing grew "
                                "for %d polls" % QUIET_ROUNDS])
            return EXIT_OK
        time.sleep(POLL_SECS)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="swarm.py", description="Measure whether the swarm's lanes were the right size.")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("report", help="per-lane rows + the band, from the receipts")
    r.add_argument("--root", default=".")
    r.add_argument("--window", help="only receipts within the last <n>d of the newest one")
    r.add_argument("--json", action="store_true", help="machine output, stable key order")
    w = sub.add_parser("watch", help="detached zero-token poller over running lanes")
    w.add_argument("--root", default=".")
    w.add_argument("--once", action="store_true", help="a single deterministic sweep")
    w.add_argument("--foreground", action="store_true",
                   help="do not daemonize (fixtures and debugging)")
    w.set_defaults(once=False)
    args = ap.parse_args(argv)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "watch":
        return cmd_watch(args)
    ap.print_usage(sys.stderr)
    sys.stderr.write("swarm.py: expected 'report' or 'watch'\n")
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
