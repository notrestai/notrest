#!/usr/bin/env python3
"""spend.py — append-only model-spend ledger; makes subagent model routing checkable.

Subcommands:
  log --model M [--tokens N] [--lane L] [--grade observed|estimate] [--purpose TEXT] [--root DIR]
  report [--root DIR]

Ledger: <root>/spend/ledger.md — one line per entry, flock-atomic append.
Routing rule checked by report: Fable never rides in a subagent — any entry whose
lane is not a seat lane (main/director/seat) with a fable model is a VIOLATION
(report exits 4 so it can gate scripts and ship rituals).
"""
import argparse, fcntl, pathlib, re, sys
from datetime import datetime, timezone

SEAT_LANES = {"main", "director", "seat"}


def ledger(root):
    return pathlib.Path(root).resolve() / "spend" / "ledger.md"


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


def cmd_report(a):
    p = ledger(a.root)
    if not p.exists():
        sys.exit(f"no ledger at {p} — nothing logged yet")
    rx = re.compile(r"^\[(.*?)\] lane=(\S+) model=(\S+) tokens=(\S+) grade=(\S+)")
    rows = [m for m in (rx.match(l) for l in
                        p.read_text(encoding="utf-8").splitlines()) if m]
    if not rows:
        sys.exit("ledger has no parseable entries")
    by_model, violations, estimates, total_known = {}, [], 0, 0
    for m in rows:
        _, lane, model, tokens, grade = m.groups()
        t = int(tokens) if tokens.isdigit() else 0
        d = by_model.setdefault(model, [0, 0])
        d[0] += 1
        d[1] += t
        total_known += t
        if grade == "estimate":
            estimates += 1
        if lane not in SEAT_LANES and "fable" in model.lower():
            violations.append(m.group(0))
    print(f"entries: {len(rows)} · tokens (known): {total_known} · "
          f"estimate-grade: {estimates}")
    print("NOTE: ledger covers observed spend only — the main loop's own "
          "consumption is not exposed to the model and is not in these totals.")
    for model, (n, t) in sorted(by_model.items(), key=lambda kv: -kv[1][1]):
        share = f"{100 * t / total_known:.0f}%" if total_known else "—"
        print(f"  {model:<24} entries={n:<4} tokens={t:<10} share={share}")
    if violations:
        print(f"ROUTING VIOLATIONS ({len(violations)}) — Fable rode in a subagent:")
        for v in violations:
            print("  " + v)
        sys.exit(4)
    print("routing: CLEAN — Fable never rode below the seat")


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
    r.set_defaults(f=cmd_report)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
