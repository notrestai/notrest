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
import errno
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
        bg, bg_err = background_reading()
        if bg_err:
            print("\n  background: UNKNOWN  [LIVE — not part of the byte-identical "
                  "reading above]")
            print("    DETECTOR-BROKEN — %s" % bg_err)
            print("    an unreadable process table is NOT a count of zero")
        else:
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
    # LIVENESS IS MEASURED, NOT INFERRED. STALL used to mean "unreceipted and quiet",
    # which is a statement about the LEDGER, not about the lane — so a lane that died
    # before its receipt landed alerted forever and no seat could ever clear it. An alert
    # that cannot be satisfied is the mirror of a rule that cannot fail. The 2026-08-05
    # DISCOVERY WINDOW narrowed the population that defect could appear in; it did not
    # remove the defect, and narrowing is not fixing. STALL now requires a POSITIVELY
    # IDENTIFIED LIVE HOST PROCESS for the lane.
    procs, det_err = process_table()
    control_ok, control_detail = (False, det_err or "control not run")
    if not det_err:
        control_ok, control_detail = detector_control(procs)
    detector_ok = (not det_err) and control_ok
    bg, bg_err = background_reading(procs, det_err)
    hosts = lane_hosts(root, procs) if detector_ok else []
    if detector_ok:
        lines.append("# background: %d notrest process(es) live%s"
                     % (len(bg), "".join("\n#   pid %s ppid %s age %s %s%s"
                        % (b["pid"], b["ppid"], b["age"], b["cwd"],
                           ("  [" + " ".join(b["flags"]) + "]") if b["flags"] else "")
                        for b in bg)))
        lines.append("# lane hosts: %d live claude process(es) bound to this estate%s"
                     % (len(hosts), "".join("\n#   pid %s up %s started %s %s"
                        % (h["pid"], fmt_age(h["age_secs"]),
                           datetime.fromtimestamp(h["start"], timezone.utc)
                           .strftime("%Y-%m-%dT%H:%M:%SZ"), h["cwd"] or "?")
                        for h in hosts)))
        lines.append("# liveness detector: OK — %s" % control_detail)
    else:
        why = bg_err or control_detail or det_err
        lines.append("# background: UNKNOWN — the liveness detector is broken, and an "
                     "unreadable process table is not a zero")
        lines.append("# lane hosts: UNKNOWN")
        lines.append("# liveness detector: DETECTOR-BROKEN — %s" % why)
        alerts.append("ALERT DETECTOR-BROKEN — process state is unreadable (%s). STALL is "
                      "NOT evaluated this sweep, and the receipt heuristic is NOT used as "
                      "a fallback: with liveness unknown, a lane's state is UNKNOWN, never "
                      "assumed. Fix the detector, then read again." % why)
    lines.append("")
    for r in rows:
        host = None
        if detector_ok and not r["receipted"]:
            host = lane_host_for(r, hosts)
        if r["receipted"]:
            state, why = "done", ""
        elif not detector_ok:
            state, why = "unknown", "  (liveness unreadable)"
        elif host is None and not hosts:
            # RULED (Director, 2026-08-26): FAILING TO RECOGNISE A HOST IS **UNKNOWN**, NOT
            # **DEAD**. If the recognition predicate matched NOTHING AT ALL, the detector has
            # not established that this lane's host is gone -- it has established that it
            # could not find one, AND THOSE ARE DIFFERENT FACTS that render identically as
            # silence unless they are split. Host recognition rests on basename(arg0) and a
            # cwd/cmdline match, so a seat launched via a wrapper, a shim, or from another
            # cwd is invisible to it -- and under a single state every lane beneath such a
            # seat goes quiet WITH A CONFIDENT REASON STRING ATTACHED.
            # AN ALERT THAT NEVER FIRES CANNOT BE NOTICED, WHEREAS ONE THAT FIRES FOREVER
            # EVENTUALLY GETS SOMEONE'S ATTENTION. So this branch HOLDS the alert.
            state, why = "unresolvable", "  (no host process recognised at all -- not a finding that this lane is dead)"
        elif host is None:
            # Hosts WERE recognised; none of them predates this lane's last write. That is a
            # real determination rather than a failure to look, so it may resolve to dead.
            state, why = "dead-host", "  (%d host(s) recognised, none predates its last write)" % len(hosts)
        else:
            active += 1
            state, why = "running", "  host=pid %s" % host["pid"]
        lines.append("  %-19s %-9s calls=%-4d idle=%dm%02ds%s"
                     % (r["agent"][:19], state, r["calls"],
                        r["idle_secs"] // 60, r["idle_secs"] % 60, why))
        if (detector_ok and host is None and not hosts and not r["receipted"]
                and r["idle_secs"] >= STALL_SECS):
            alerts.append("ALERT STALL-UNRESOLVABLE %s — frozen %dm with no receipt, and the "
                          "detector RECOGNISED NO HOST PROCESS AT ALL. This is NOT a finding "
                          "that the lane is dead: the recognition predicate found nothing to "
                          "judge it against. The alert is HELD rather than resolved."
                          % (r["agent"][:19], r["idle_secs"] // 60))
        if (detector_ok and host is not None and not r["receipted"]
                and r["idle_secs"] >= STALL_SECS):
            alerts.append("ALERT STALL %s — no transcript growth for %dm, no receipt, and "
                          "its host process IS LIVE (pid %s, up %s); probe, resume or stop it"
                          % (r["agent"][:19], r["idle_secs"] // 60,
                             host["pid"], fmt_age(host["age_secs"])))
        if not r["receipted"] and r["calls"] >= MONO_CALLS:
            alerts.append("ALERT MONOLITH-IN-PROGRESS %s — %d live calls past the %d band "
                          "while still running; the NEXT contract for this work splits further"
                          % (r["agent"][:19], r["calls"], MONO_CALLS))
    return lines + ([""] + alerts if alerts else []), alerts, active


BG_PATTERNS = ("estate-pulse.sh", "swarm.py watch")

# A LANE IS NOT AN OS PROCESS. Measured on the real estate 2026-08-26: a lane that was
# actively running at the moment of the reading held NO file descriptor on its own
# transcript, named itself in NO command line, and owned NO pid — subagents run inside the
# `claude` process that owns their session. So per-lane liveness is not on offer from this
# host, and the finest grain that IS real is THE LANE'S HOST: a live claude process for
# this estate that was already running when the lane last wrote. Coarser than per-lane,
# and it is still a MEASUREMENT of process state rather than an inference drawn from a
# missing receipt.
HOST_ARG0 = "claude"


def fmt_age(secs):
    """[[dd-]hh:]mm:ss — the shape ps prints, so one flag rule serves both readers."""
    s = int(max(0, secs))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return "%d-%02d:%02d:%02d" % (d, h, m, s)
    if h:
        return "%02d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)


def etime_secs(etime):
    """ps etime is [[dd-]hh:]mm:ss. None when it is not."""
    try:
        days = 0
        if "-" in etime:
            d, etime = etime.split("-", 1)
            days = int(d)
        bits = [int(b) for b in etime.split(":")]
        while len(bits) < 3:
            bits.insert(0, 0)
        return days * 86400 + bits[0] * 3600 + bits[1] * 60 + bits[2]
    except (ValueError, IndexError):
        return None


def proc_table_from_proc():
    """(rows, err) from /proc. Every row carries an absolute START EPOCH, because the
    liveness question is not "how old is it" but "was it already running then"."""
    rows = []
    if not os.path.isdir("/proc"):
        return rows, "/proc is not present"
    try:
        hz = os.sysconf("SC_CLK_TCK")
        btime = None
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("btime "):
                    btime = int(line.split()[1])
                    break
        if not btime or not hz:
            return rows, "/proc/stat carries no usable btime — a process cannot be aged"
        entries = os.listdir("/proc")
    except (OSError, ValueError, AttributeError) as e:
        return rows, "/proc unreadable: %s" % e
    now = time.time()
    for name in entries:
        if not name.isdigit():
            continue
        base = "/proc/" + name
        try:
            with open(base + "/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            with open(base + "/stat", "rb") as f:
                stat = f.read().decode("utf-8", "replace")
        except (OSError, IOError):
            continue                      # it exited between the listing and the read
        if not cmd:
            continue                      # kernel thread, never a lane host
        rp = stat.rfind(")")
        fields = stat[rp + 2:].split() if rp >= 0 else []
        try:
            ppid = fields[1]
            start = btime + int(fields[19]) / float(hz)
        except (IndexError, ValueError):
            continue
        try:
            cwd = os.readlink(base + "/cwd")
        except OSError:
            cwd = ""
        rows.append({"pid": name, "ppid": ppid, "start": start,
                     "age_secs": max(0.0, now - start), "cmd": cmd, "cwd": cwd})
    if not rows:
        return rows, "/proc listed no readable processes"
    return rows, ""


def proc_table_from_ps():
    """(rows, err) from ps, for hosts that have it. No cwd: ps does not carry one."""
    try:
        out = subprocess.run(["ps", "-eo", "pid=,ppid=,etime=,command="],
                             stdout=subprocess.PIPE, timeout=10
                             ).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as e:
        return [], "ps unavailable: %s" % e
    rows, now = [], time.time()
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, etime, cmd = parts
        if not pid.isdigit():
            continue
        secs = etime_secs(etime)
        rows.append({"pid": pid, "ppid": ppid,
                     "start": (now - secs) if secs is not None else 0.0,
                     "age_secs": secs if secs is not None else 0.0,
                     "cmd": cmd, "cwd": ""})
    if not rows:
        return rows, "ps returned no parseable rows"
    return rows, ""


def process_table():
    """(rows, err) — the live process table, /proc first, ps second.

    WHY /proc FIRST: measured 2026-08-26 on this estate's own host, `ps` DOES NOT EXIST.
    The previous reader shelled out to ps only, swallowed the OSError, and returned [] —
    so the watcher printed "background: 0 notrest process(es) live" while a `swarm.py
    watch` was running four feet away. A detector that cannot tell EMPTY from BLIND is
    not a detector, and every caller here now receives the reason as well as the rows."""
    # A RAISE IS A STARVED DETECTOR, NOT A CRASH. The watcher's job is to say "I cannot
    # see" — an escaping exception kills the sweep and takes the honest DETECTOR-BROKEN
    # report with it, which is the loudest possible way to say nothing.
    try:
        rows, err = proc_table_from_proc()
        if rows:
            return rows, ""
    except Exception as e:                                   # noqa: BLE001 — see above
        rows, err = [], "/proc reader raised: %r" % (e,)
    try:
        rows2, err2 = proc_table_from_ps()
        if rows2:
            return rows2, ""
    except Exception as e:                                   # noqa: BLE001 — see above
        rows2, err2 = [], "ps reader raised: %r" % (e,)
    return [], "%s; %s" % (err or "no /proc rows", err2 or "no ps rows")


def detector_control(rows):
    """POSITIVE CONTROL on the process table. It runs on EVERY sweep and it GATES the
    whole liveness reading — nothing below is believed unless this passes.

      ARM A, must be SEEN:   this interpreter's own pid. It is live by construction; a
                             table that cannot see the process doing the looking sees
                             nothing, which is exactly how the ps-less blindness hid.
      ARM B, must be ABSENT: a pid proven not to exist right now — kill(pid, 0) raising
                             ESRCH and no /proc entry. Without arm B a table that simply
                             said yes to everything would pass arm A.

    THE ARMS ARE PROVEN DISTINCT BEFORE ANYTHING ELSE IS PROVEN: a control whose two arms
    are the same object tests nothing and passes. Arm B is drawn from pids above our own
    and re-drawn until it differs, the equality is refused explicitly, and both numbers
    are reported so a reader can see for themselves that they are two different objects.

    Returns (ok, detail)."""
    live = os.getpid()
    dead = None
    for cand in range(live + 1, live + 8192):
        if cand == live:
            continue                      # never let the arms collapse
        if os.path.exists("/proc/%d" % cand):
            continue
        try:
            os.kill(cand, 0)
            continue                      # it exists — not provably absent
        except OSError as e:
            if getattr(e, "errno", None) == errno.ESRCH:
                dead = cand
                break
            continue                      # EPERM: exists but is not ours
    if dead is None:
        return False, ("control could not draw a provably-absent pid to contrast with "
                       "%d — the second arm is unavailable, so the control is vacuous"
                       % live)
    if dead == live:
        return False, ("control arms collapsed onto the same pid %d — two arms that are "
                       "one object test nothing" % live)
    seen = set(r["pid"] for r in rows)
    a_ok = str(live) in seen
    b_ok = str(dead) not in seen
    detail = ("arms are distinct objects: live=%d vs provably-absent=%d · saw-itself=%s · "
              "absent-stayed-absent=%s · %d process(es) enumerated"
              % (live, dead, a_ok, b_ok, len(rows)))
    return (a_ok and b_ok), detail


def background_reading(procs=None, err=None):
    """(rows, err) — the background inventory AND why it is empty when it is empty.

    Live notrest background processes: what is actually running, how old, and where.
    Flags the two species that bite: ancient survivors, and workers whose cwd is a
    temp/fixture path (a wedged sandbox child, which is how a working lane got killed on
    2026-08-05). Empty-with-an-error is a REFUSAL TO ANSWER, never a zero."""
    if procs is None:
        procs, err = process_table()
    if err:
        return [], err
    ok, detail = detector_control(procs)
    if not ok:
        return [], "positive control FAILED: " + detail
    out = []
    for p in procs:
        line = p["cmd"]
        if not any(pat in line for pat in BG_PATTERNS):
            continue
        if " -eo " in line or "grep " in line:
            continue
        cwd = p["cwd"]
        if not cwd:
            for tok in line.split():
                if tok.startswith("/") and os.path.isdir(tok):
                    cwd = tok
                    break
        flags = []
        if p["age_secs"] >= 86400:
            flags.append("ANCIENT>24h")
        low = (cwd or line).lower()
        if any(k in low for k in ("/tmp", "/var/folders", "fixture", "/t/tmp.")):
            flags.append("TEMP/FIXTURE-CWD")
        if str(p["ppid"]).strip() not in ("1",):
            flags.append("PARENTED(ppid=%s)" % str(p["ppid"]).strip())
        out.append({"pid": p["pid"], "ppid": p["ppid"], "age": fmt_age(p["age_secs"]),
                    "cwd": cwd or "?", "flags": flags, "cmd": line[:110],
                    "start": p["start"]})
    return out, ""


def background_inventory():
    """Rows only, for callers that already handle the empty case themselves. Prefer
    background_reading(): this shape cannot distinguish 'nothing running' from 'blind'."""
    rows, _err = background_reading()
    return rows


def lane_hosts(root, procs):
    """Live processes that could be RUNNING a lane of this estate: the `claude` CLI, bound
    to this estate by cwd or by the root naming itself on the command line."""
    root = os.path.realpath(root)
    out = []
    for p in procs:
        cmd = p["cmd"]
        arg0 = cmd.split(" ", 1)[0]
        if os.path.basename(arg0) != HOST_ARG0:
            continue
        cwd = os.path.realpath(p["cwd"]) if p["cwd"] else ""
        if cwd != root and root not in cmd:
            continue
        out.append(p)
    return out


def lane_host_for(row, hosts, now=None):
    """The live host that could still be running this lane: one that was ALREADY RUNNING
    when the lane last wrote. A host that started AFTER the lane's final byte cannot be
    the process that wrote it, so it cannot be the process still running it.

    No such host -> the lane's host is GONE. The lane is dead or finished, and a lane with
    no live host is NOT A STALL: it is the unclearable alert this predicate exists to
    stop raising. Returns the host row, or None."""
    last_write = (now or time.time()) - row["idle_secs"]
    best = None
    for h in hosts:
        if h["start"] <= last_write and (best is None or h["start"] > best["start"]):
            best = h
    return best


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
