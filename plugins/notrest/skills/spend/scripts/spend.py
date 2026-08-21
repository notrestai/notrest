#!/usr/bin/env python3
"""spend.py — append-only model-spend ledger; makes offload model routing checkable.

Subcommands:
  log --model M [--tokens N] [--lane L] [--grade observed|estimate] [--purpose TEXT] [--root DIR]
  log --seat-estimate N --note TEXT [--model M] [--root DIR]
  report [--root DIR] [--since YYYY-MM-DD] [--json]

THE SEAT'S OWN SPEND (--seat-estimate). Every cost number this ledger can produce is a
LANE subtotal sitting next to a session whose largest consumer — the seat itself — is
invisible: the main loop's totals are not exposed to the model. The ledger has always
said so honestly, and that honesty left the gap the exact size of the reader's
imagination. `--seat-estimate` writes the seat's own guess down as what it is: a
`lane=seat`, `grade=estimate`, `kind=seat-estimate` line, kept OUT of the observed
token totals and reported on its own count line. It is informational and never
offload-gated — the seat is where a different orchestrator legitimately sits, so a seat
line cannot be a routing violation, and an estimate must never be able to move a gate.

Ledger: <root>/spend/ledger.md — one line per entry, flock-atomic append.

THE RULE `report` ENFORCES: every offload names the runtime's explicit frontier worker.
Claude uses opus. The Codex adapter (v4.3.0, 2026-08-06) uses gpt-5.6-sol. An offload lane
is any lane that is not a seat lane (main/director/seat).

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
# Lanes that legitimately run another vendor's model: exempt from the worker offload
# rule, counted separately, never silently. EXACT NAMES ONLY — an allowlist that grows by
# pattern (connector-*) stops being an allowlist, so each new lane is added deliberately,
# here, with its reason. `connector-openai` added 2026-07-27 for the rig.rest connector:
# an honest receipt for a lawful cross-vendor call was grading as a ROUTING VIOLATION
# (exit 4) because the gate had never been told that lane exists.
CROSS_VENDOR_LANES = {"gpt", "chatroom-gpt", "connector-openai"}

# ── the policy, as data (so the verdict can name the rule version it enforces) ─
POLICY_DATE = "2026-07-15"          # the day the owner set opus-only Claude offload
POLICY_BINDS_FROM = "2026-07-16"    # first day an entry is judged by it (see guard above)
CODEX_POLICY_DATE = "2026-08-06"    # Codex adapter release day (day itself grandfathered)
CODEX_BINDS_FROM = "2026-08-07"
POLICY_NAME = "policy v4.3: runtime worker (Claude=opus, Codex=gpt-5.6-sol)"
LEGACY_NAME = "pre-2026-07-15 rule: fable never below the seat"

OPUS_RE = re.compile(r"opus", re.I)
CODEX_RE = re.compile(r"(?:^|[-_/])gpt-5\.6-sol(?:$|[-_/])", re.I)
FABLE_RE = re.compile(r"fable", re.I)
UNKNOWN_MODELS = {"", "?", "-", "unknown", "none", "null"}

ENTRY_RE = re.compile(r"^\[(.*?)\] lane=(\S+) model=(\S+) tokens=(\S+) grade=(\S+)")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
KIND_RE = re.compile(r"\bkind=(\S+)")
SEAT_ESTIMATE_KIND = "seat-estimate"


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
    compliant     — offload lane, explicit worker valid for the law then in force
    unverifiable  — offload lane, post-policy, model unknown; routing not provable
    violation     — offload lane, a known model outside the law then in force
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
    # The Codex model becomes lawful only after the adapter exists. A backdated Codex
    # receipt must not rewrite the policy that actually governed that old lane.
    if CODEX_RE.search(model) and (not d or d >= CODEX_BINDS_FROM):
        return "compliant"
    return "violation"


def cmd_log(a):
    seat = a.seat_estimate is not None
    if seat:
        if a.lane and a.lane not in SEAT_LANES:
            sys.exit(f"--seat-estimate is the SEAT's own consumption; lane={a.lane!r} is an "
                     f"offload lane. Log the lane's spend normally, with its observed tokens.")
        if a.seat_estimate < 0:
            sys.exit("--seat-estimate must be a token count, not a negative number")
        note = re.sub(r"\s+", " ", (a.note or a.purpose or "")).strip()
        if not note:
            sys.exit("--seat-estimate needs --note: a naked number nobody can interpret is "
                     "worse than the gap it fills (say what the session was doing)")
        lane, grade = (a.lane or "seat"), "estimate"
        model, tokens, kind, purpose = (a.model or "?"), str(a.seat_estimate), \
            SEAT_ESTIMATE_KIND, note
    else:
        if not a.model:
            sys.exit("log needs --model (or --seat-estimate for the seat's own consumption)")
        lane, grade = (a.lane or "main"), a.grade
        model = a.model
        tokens = str(a.tokens) if a.tokens is not None else "unknown"
        kind = None
        purpose = re.sub(r"\s+", " ", (a.purpose or a.note or "")).strip()

    p = ledger(a.root)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# spend ledger — append-only via spend.py; "
                     "grades: observed|estimate\n", encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    line = (f"[{ts}] lane={lane} model={model} tokens={tokens} grade={grade} "
            + (f"kind={kind} " if kind else "")
            + f"purpose=\"{purpose}\"\n")
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
        km = KIND_RE.search(line)
        entries.append({
            "raw": m.group(0),
            "ts": ts, "lane": lane, "model": model, "grade": grade,
            "tokens": int(tokens) if tokens.isdigit() else 0,
            "tokens_known": tokens.isdigit(),
            "kind": km.group(1) if km else "",
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
    # Seat estimates are the seat's guess at its own consumption. They are counted, but
    # never mixed into the observed token totals or the per-model share table: an
    # estimate that can move a percentage is an estimate laundered into a measurement.
    seat_est = [e for e in entries if e["kind"] == SEAT_ESTIMATE_KIND]
    seat_est_tokens = sum(e["tokens"] for e in seat_est)
    for e in entries:
        if e["grade"] == "estimate":
            estimates += 1
        buckets[e["verdict"]].append(e)
        if e["kind"] == SEAT_ESTIMATE_KIND:
            continue
        d = by_model.setdefault(e["model"], [0, 0])
        d[0] += 1
        d[1] += e["tokens"]
        total_known += e["tokens"]

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
            "seat_estimates": {"entries": len(seat_est), "tokens": seat_est_tokens,
                               "gated": False,
                               "note": "the seat's own consumption, self-estimated; "
                                       "informational, excluded from tokens_known"},
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
          "consumption is not exposed to the model and is not in these totals."
          + (f" ({len(seat_est)} seat estimate(s) below are the seat's own guess at that "
             f"gap, deliberately kept out of these totals.)" if seat_est else ""))
    for model, (n, t) in sorted(by_model.items(), key=lambda kv: -kv[1][1]):
        share = f"{100 * t / total_known:.0f}%" if total_known else "—"
        print(f"  {model:<24} entries={n:<4} tokens={t:<10} share={share}")

    if seat_est:
        print(f"seat estimates: {len(seat_est)}, informational — not offload-gated "
              f"(~{seat_est_tokens} tokens self-reported by the seat; grade=estimate, "
              f"excluded from the totals and shares above)")
        for e in seat_est:
            print("  " + e["raw"])

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
              f"({len(violations)} offload entries on an unsupported worker model, "
              f"{len(legacy)} legacy)")
        sys.exit(4)
    print(f"routing: CLEAN — {POLICY_NAME} "
          f"({offload_checked} offload entries checked, 0 violations)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("log")
    l.add_argument("--model", help="required unless --seat-estimate is given")
    l.add_argument("--tokens", type=int)
    l.add_argument("--lane", default=None)
    l.add_argument("--grade", default="observed", choices=["observed", "estimate"])
    l.add_argument("--purpose", default="")
    l.add_argument("--seat-estimate", dest="seat_estimate", type=int, metavar="TOKENS",
                   help="the seat's own consumption, self-estimated: logs lane=seat "
                        "grade=estimate kind=seat-estimate; informational, never gated")
    l.add_argument("--note", default="", help="what the seat was doing (required with "
                                              "--seat-estimate); also usable as --purpose")
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
