#!/usr/bin/env python3
"""spend.py — append-only model-spend ledger; makes offload model routing checkable.

Subcommands:
  log --model M [--tokens N] [--lane L] [--grade observed|estimate] [--purpose TEXT] [--root DIR]
  report [--root DIR] [--since YYYY-MM-DD] [--json]

Ledger: <root>/spend/ledger.md — one line per entry, flock-atomic append.

THE RULE `report` ENFORCES (owner-set 2026-07-15): every job a session OFFLOADS runs on
an explicit opus model. An offload lane is any lane that is not a seat lane
(main/director/seat) — the seat is where a non-opus orchestrator legitimately sits.

Two guards keep the verdict honest rather than merely loud:

  · POLICY-DATE GUARD — an entry is judged by the law in force when it was logged, never
    by one that did not yet exist. Entries dated on or before the policy day fall under
    the rule that WAS live then (v2.7.0: "Fable never rides in a subagent"), so a
    pre-policy sonnet lane is lawful-at-the-time and a pre-policy fable subagent is still
    a violation. The policy DAY itself is grandfathered: the ledger stamps minutes, but
    the hour the owner set the policy is not recorded, so an entry dated 2026-07-15
    cannot be proven post-policy. An entry whose timestamp will not parse gets no
    exemption — it is judged by the live rule, so a garbled stamp can never buy amnesty.

  · CROSS-VENDOR ALLOWLIST — lane=gpt and lane=chatroom-gpt run another vendor's models
    by design. They are exempt and counted separately, never silently folded into
    "compliant".

An offload entry whose model is unknown ("?") is NOT called a violation: absence of
evidence is not evidence of one. It is counted and named on its own line, because
routing is not PROVABLE for it — the honest state is "unverifiable", not "clean".

report exits 4 on a violation so it can gate scripts and ship rituals; 0 when clean.
"""
import argparse, fcntl, json, pathlib, re, sys
from datetime import datetime, timezone

# ── lanes ────────────────────────────────────────────────────────────────────
SEAT_LANES = {"main", "director", "seat"}
CROSS_VENDOR_LANES = {"gpt", "chatroom-gpt"}

# ── the policy, as data (so the verdict can name the rule version it enforces) ─
POLICY_DATE = "2026-07-15"          # the day the owner set opus-only offload
POLICY_BINDS_FROM = "2026-07-16"    # first day an entry is judged by it (see guard above)
POLICY_NAME = "policy 2026-07-15: opus-only offload"
LEGACY_NAME = "pre-2026-07-15 rule: fable never below the seat"

OPUS_RE = re.compile(r"opus", re.I)
FABLE_RE = re.compile(r"fable", re.I)
UNKNOWN_MODELS = {"", "?", "-", "unknown", "none", "null"}

ENTRY_RE = re.compile(r"^\[(.*?)\] lane=(\S+) model=(\S+) tokens=(\S+) grade=(\S+)")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def ledger(root):
    return pathlib.Path(root).resolve() / "spend" / "ledger.md"


def entry_date(ts):
    """The YYYY-MM-DD an entry claims, or "" when the stamp will not parse.

    "" is deliberately NOT treated as pre-policy: an undatable entry is judged by the
    live rule (fail closed), so a malformed timestamp cannot be used to dodge the gate.
    """
    m = DATE_RE.match((ts or "").strip())
    return m.group(1) if m else ""


def classify(ts, lane, model):
    """Judge one ledger entry. Returns one of:

    seat          — not an offload lane; the rule does not apply
    cross-vendor  — allowlisted foreign-vendor lane; exempt, counted separately
    pre-policy    — offload lane, dated on/before the policy day, lawful at the time
    legacy-violation — pre-policy, but broke the rule that WAS live then (fable below seat)
    compliant     — offload lane, post-policy, explicit opus
    unverifiable  — offload lane, post-policy, model unknown; routing not provable
    violation     — offload lane, post-policy, a known non-opus model
    """
    lane = (lane or "").strip()
    model = (model or "").strip()
    if lane in SEAT_LANES:
        return "seat"
    if lane in CROSS_VENDOR_LANES:
        return "cross-vendor"
    d = entry_date(ts)
    if d and d < POLICY_BINDS_FROM:
        return "legacy-violation" if FABLE_RE.search(model) else "pre-policy"
    if model.lower() in UNKNOWN_MODELS:
        return "unverifiable"
    if OPUS_RE.search(model):
        return "compliant"
    return "violation"


def cmd_log(a):
    p = ledger(a.root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# spend ledger — append-only via spend.py; "
                     "grades: observed|estimate\n", encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    tokens = str(a.tokens) if a.tokens is not None else "unknown"
    purpose = re.sub(r"\s+", " ", a.purpose or "").strip()
    line = (f"[{ts}] lane={a.lane} model={a.model} tokens={tokens} "
            f"grade={a.grade} purpose=\"{purpose}\"\n")
    with open(p, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line)
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)
    print("logged:", line.strip())


def collect(path, since):
    """Parse the ledger into classified entries. `since` filters by date (inclusive)."""
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ENTRY_RE.match(line)
        if not m:
            continue
        ts, lane, model, tokens, grade = m.groups()
        if since:
            d = entry_date(ts)
            if not d or d < since:
                continue
        entries.append({
            "raw": m.group(0),
            "ts": ts, "lane": lane, "model": model, "grade": grade,
            "tokens": int(tokens) if tokens.isdigit() else 0,
            "tokens_known": tokens.isdigit(),
            "verdict": classify(ts, lane, model),
        })
    return entries


def cmd_report(a):
    p = ledger(a.root)
    if not p.exists():
        sys.exit(f"no ledger at {p} — nothing logged yet")
    since = entry_date(a.since) if a.since else ""
    if a.since and not since:
        sys.exit(f"--since {a.since!r} is not an ISO date (YYYY-MM-DD)")
    entries = collect(p, since)
    if not entries:
        sys.exit("ledger has no parseable entries"
                 + (f" on or after {since}" if since else ""))

    by_model, total_known, estimates = {}, 0, 0
    buckets = {k: [] for k in ("seat", "cross-vendor", "pre-policy", "legacy-violation",
                               "compliant", "unverifiable", "violation")}
    for e in entries:
        d = by_model.setdefault(e["model"], [0, 0])
        d[0] += 1
        d[1] += e["tokens"]
        total_known += e["tokens"]
        if e["grade"] == "estimate":
            estimates += 1
        buckets[e["verdict"]].append(e)

    violations = buckets["violation"]
    legacy = buckets["legacy-violation"]
    unverifiable = buckets["unverifiable"]
    offload_checked = len(buckets["compliant"]) + len(violations) + len(unverifiable)
    verdict = "VIOLATION" if (violations or legacy) else "CLEAN"

    if a.json:
        print(json.dumps({
            "policy": POLICY_NAME,
            "legacy_policy": LEGACY_NAME,
            "policy_binds_from": POLICY_BINDS_FROM,
            "ledger": str(p),
            "since": since or None,
            "entries": len(entries),
            "tokens_known": total_known,
            "estimate_grade": estimates,
            "by_model": {m: {"entries": n, "tokens": t,
                             "share_pct": round(100 * t / total_known, 1) if total_known else None}
                         for m, (n, t) in sorted(by_model.items(), key=lambda kv: -kv[1][1])},
            "counts": {k.replace("-", "_"): len(v) for k, v in buckets.items()},
            "offload_checked": offload_checked,
            "violations": [e["raw"] for e in violations],
            "legacy_violations": [e["raw"] for e in legacy],
            "unverifiable_entries": [e["raw"] for e in unverifiable],
            "verdict": verdict,
            "exit": 4 if verdict == "VIOLATION" else 0,
        }, indent=2))
        if verdict == "VIOLATION":
            sys.exit(4)
        return

    scope = f" (since {since})" if since else ""
    print(f"entries: {len(entries)}{scope} · tokens (known): {total_known} · "
          f"estimate-grade: {estimates}")
    print("NOTE: ledger covers observed spend only — the main loop's own "
          "consumption is not exposed to the model and is not in these totals.")
    for model, (n, t) in sorted(by_model.items(), key=lambda kv: -kv[1][1]):
        share = f"{100 * t / total_known:.0f}%" if total_known else "—"
        print(f"  {model:<24} entries={n:<4} tokens={t:<10} share={share}")

    print(f"offload lanes: {offload_checked} checked under {POLICY_NAME} · "
          f"{len(buckets['pre-policy'])} pre-policy (dated on/before {POLICY_DATE}, "
          f"lawful at the time) · cross-vendor lanes: {len(buckets['cross-vendor'])}, exempt · "
          f"seat lanes: {len(buckets['seat'])}, rule N/A")
    if unverifiable:
        print(f"UNVERIFIABLE ({len(unverifiable)}) — offload entries carrying no model id; "
              f"routing is not provable for these (not counted as violations):")
        for e in unverifiable:
            print("  " + e["raw"])
    if legacy:
        print(f"LEGACY VIOLATIONS ({len(legacy)}) — {LEGACY_NAME}:")
        for e in legacy:
            print("  " + e["raw"])
    if violations:
        print(f"ROUTING VIOLATIONS ({len(violations)}) — {POLICY_NAME}:")
        for e in violations:
            print("  " + e["raw"])
    if verdict == "VIOLATION":
        print(f"routing: VIOLATION — {POLICY_NAME} "
              f"({len(violations)} offload entries on a non-opus model, "
              f"{len(legacy)} legacy)")
        sys.exit(4)
    print(f"routing: CLEAN — {POLICY_NAME} "
          f"({offload_checked} offload entries checked, 0 violations)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("log")
    l.add_argument("--model", required=True)
    l.add_argument("--tokens", type=int)
    l.add_argument("--lane", default="main")
    l.add_argument("--grade", default="observed", choices=["observed", "estimate"])
    l.add_argument("--purpose", default="")
    l.add_argument("--root", default=".")
    l.set_defaults(f=cmd_log)
    r = sub.add_parser("report")
    r.add_argument("--root", default=".")
    r.add_argument("--since", metavar="YYYY-MM-DD",
                   help="only entries dated on or after this day (date granularity)")
    r.add_argument("--json", action="store_true",
                   help="machine-readable report; same exit codes")
    r.set_defaults(f=cmd_report)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
