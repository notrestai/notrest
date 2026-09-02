#!/usr/bin/env python3
"""score_snapshot.py — deterministic metrics for introspect snapshots, and the
instrument that turns them into a ledger nobody has to hand-total.

Subcommands (the flat legacy form still works — a bare `--snapshot …` is read as
`score`, so every invocation written before this file grew subcommands still runs):

  score  --snapshot "a, b, c" (--output-file F | --output-text T)
         [--control "x, y"] [--prev "a, d"]
         Print the JSON metrics object. Computes nothing else, writes nothing.

  append --snapshot … --output-file F [--control …] [--prev …]
         --label "<checkpoint>" [--mode now|session|experiment] [--root DIR]
         [--glossed "…"] [--control-absent "<why>"] [--interpretation "<one line>"]
         Score, write the run as JSON under <root>/introspection/runs/, and APPEND
         the ledger entry to <root>/introspection/ledger.md. Append-only: entries are
         never rewritten, and a correcting run is a new run.

  report [--root DIR]
         Aggregate the runs: mean verbalized/silent rates, mean lift, mean turnover, N.
         REFUSES trend language under N=10 — prints "N=<n> — no trend claims below 10"
         and exits 3. That refusal is the whole point of the subcommand: /introspect
         report is advertised in the skill, and until now the aggregation was a claim
         no code performed, which is exactly the shape of a confabulated result.

Matching is deliberately crude and DETERMINISTIC: lowercase, hyphens folded to
spaces; single-word concepts match on word boundary with naive s/es/ed/ing
stemming; multi-word concepts match as substrings of the folded text. Semantic
matches are a human/model judgment — tag them [sem] in the ledger, never here.

The metrics are honest about what they are NOT: no activations are observed, so a
positive lift is evidence that a self-report carried signal an outsider's guess did
not — never evidence of introspection in any deeper sense.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

RUNS_DIR = "runs"
LEDGER = "ledger.md"
TREND_FLOOR = 10          # below this N, no trend language is emitted. Ever.


def parse_concepts(raw):
    if not raw:
        return []
    out = []
    for c in raw.split(","):
        c = c.strip().lower().strip("-• ").replace("-", " ").strip()
        if c:
            out.append(c)
    return out


def fold(text):
    return re.sub(r"[-_]", " ", text.lower())


def word_set(text_folded):
    return set(re.findall(r"[a-z0-9']+", text_folded))


def stems(w):
    yield w
    for suf in ("s", "es", "ed", "ing"):
        yield w + suf
        if len(w) > len(suf) + 2 and w.endswith(suf):
            yield w[: -len(suf)]


def concept_hit(concept, tw, tf):
    if " " in concept:
        return concept in tf
    return any(v in tw for v in stems(concept))


def die(msg, code=2):
    """F4: refuse in ONE line at rc=2, the posture every sibling lint already keeps
    (plan_lint, runbook_lint, verdict_lint). A traceback is a crash report, not a
    refusal — it tells the reader the tool broke when in fact the tool was misused."""
    sys.stderr.write("score_snapshot: %s\n" % msg)
    sys.exit(code)


def load_output(a):
    if a.output_file:
        try:
            with open(a.output_file, "r", encoding="utf-8") as f:
                return f.read(), a.output_file
        except IsADirectoryError:
            die("--output-file is a directory, not a file: %s" % a.output_file)
        except FileNotFoundError:
            die("no such --output-file: %s" % a.output_file)
        except OSError as e:
            die("cannot read --output-file %s: %s" % (a.output_file, e.strerror or e))
        except UnicodeDecodeError:
            die("--output-file is not UTF-8 text: %s" % a.output_file)
    if a.output_text is not None:
        return a.output_text, "(inline text)"
    die("need --output-file or --output-text")


def score(a):
    """The four metrics. Pure: reads the output, returns numbers, writes nothing."""
    text, src = load_output(a)
    snap = parse_concepts(a.snapshot)
    ctrl = parse_concepts(a.control)
    prev = parse_concepts(a.prev)
    if not snap:
        die("empty snapshot: --snapshot must name at least one concept")

    tf = fold(text)
    tw = word_set(tf)

    verbalized = [c for c in snap if concept_hit(c, tw, tf)]
    silent = [c for c in snap if c not in verbalized]
    ctrl_hits = [c for c in ctrl if concept_hit(c, tw, tf)]

    return {
        "snapshot_size": len(snap),
        "verbalized": verbalized,
        "silent": silent,
        "verbalized_rate": round(len(verbalized) / len(snap), 3),
        "control_size": len(ctrl),
        "control_hits": ctrl_hits,
        "control_rate": round(len(ctrl_hits) / len(ctrl), 3) if ctrl else None,
        "lift": round((len(verbalized) - len(ctrl_hits)) / len(snap), 3) if ctrl else None,
        "turnover_vs_prev": round(
            1 - len(set(snap) & set(prev)) / len(set(snap) | set(prev)), 3
        ) if prev else None,
        "output_chars": len(text),
        "output_source": src,
        "output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }, snap, ctrl, prev


def cmd_score(a):
    res, _snap, _ctrl, _prev = score(a)
    res.pop("output_source", None)
    res.pop("output_sha256", None)
    print(json.dumps(res, indent=2))
    return 0


# ── append ───────────────────────────────────────────────────────────────────
RUN_RE = re.compile(r"^run-(\d+)-")


def introspection_dir(root):
    return pathlib.Path(root).expanduser().resolve() / "introspection"


def next_run_number(runs):
    n = 0
    if runs.is_dir():
        for p in runs.glob("run-*.json"):
            m = RUN_RE.match(p.name)
            if m:
                n = max(n, int(m.group(1)))
    return n + 1


def slugify(text, cap=32):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:cap].strip("-") or "run"


def ledger_entry(run):
    m = run["metrics"]
    compact = {"verbalized": m["verbalized_rate"], "silent": m["silent"],
               "lift": m["lift"], "turnover_vs_prev": m["turnover_vs_prev"]}
    ctrl = (", ".join(run["control"]) if run["control"]
            else "absent — %s" % (run.get("control_absent")
                                  or "no control agent run for this snapshot"))
    return "\n".join([
        "",
        "## Run %d — %s — %s" % (run["n"], run["label"], run["date"]),
        "- mode: %s" % run["mode"],
        "- snapshot: %s" % ", ".join(run["snapshot"]),
        "- glossed: %s" % (run.get("glossed") or "(not recorded)"),
        "- control (context-only): %s" % ctrl,
        "- output: %s (%d chars, sha256:%s)"
        % (m["output_source"], m["output_chars"], m["output_sha256"][:12]),
        "- metrics: %s" % json.dumps(compact),
        "- interpretation (one line, run-sized confidence): %s"
        % (run.get("interpretation")
           or "[unverified] not recorded — one run is one run; the ledger is the instrument"),
        "",
    ])


def cmd_append(a):
    if not a.output_file:
        die("append needs --output-file: a scored output must exist on disk, so the "
            "ledger entry can point at the thing that was scored")
    metrics, snap, ctrl, prev = score(a)
    d = introspection_dir(a.root)
    runs = d / RUNS_DIR
    runs.mkdir(parents=True, exist_ok=True)
    n = next_run_number(runs)
    run = {
        "n": n,
        "label": a.label,
        "mode": a.mode,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"),
        "snapshot": snap,
        "control": ctrl,
        "control_absent": a.control_absent,
        "prev": prev,
        "glossed": a.glossed,
        "interpretation": a.interpretation,
        "metrics": metrics,
    }
    rp = runs / ("run-%03d-%s.json" % (n, slugify(a.label)))
    rp.write_text(json.dumps(run, indent=1) + "\n", encoding="utf-8")

    lp = d / LEDGER
    if not lp.exists():
        lp.write_text(
            "# introspection/ledger.md — append-only, written by score_snapshot.py\n"
            "\n"
            "Never overwrite an entry: a snapshot edited after seeing what came next is\n"
            "worthless data. A correction is a NEW run with an interpretation saying so.\n"
            "Aggregates are computed by `score_snapshot.py report`, never typed in here.\n",
            encoding="utf-8")
    with open(lp, "a", encoding="utf-8") as f:
        f.write(ledger_entry(run))

    print("[introspect] run %d appended" % n)
    print("  run json: %s" % rp)
    print("  ledger  : %s" % lp)
    print("  verbalized %.2f · silent %d/%d · lift %s · turnover %s"
          % (metrics["verbalized_rate"], len(metrics["silent"]), metrics["snapshot_size"],
             metrics["lift"] if metrics["lift"] is not None else "—",
             metrics["turnover_vs_prev"] if metrics["turnover_vs_prev"] is not None else "—"))
    return 0


# ── report ───────────────────────────────────────────────────────────────────
def mean(xs):
    return sum(xs) / len(xs) if xs else None


def cmd_report(a):
    d = introspection_dir(a.root)
    runs_dir = d / RUNS_DIR
    rows = []
    if runs_dir.is_dir():
        for p in sorted(runs_dir.glob("run-*.json")):
            try:
                rows.append(json.loads(p.read_text(encoding="utf-8")))
            except ValueError:
                print("[introspect] unreadable run file, skipped: %s" % p)
    n = len(rows)
    verb = [r["metrics"]["verbalized_rate"] for r in rows
            if r.get("metrics", {}).get("verbalized_rate") is not None]
    lifts = [r["metrics"]["lift"] for r in rows if r.get("metrics", {}).get("lift") is not None]
    turns = [r["metrics"]["turnover_vs_prev"] for r in rows
             if r.get("metrics", {}).get("turnover_vs_prev") is not None]

    print("[introspect] %s — %d run(s)" % (runs_dir, n))
    if n:
        mv = mean(verb)
        print("  verbalized rate : mean %.3f  (silent rate mean %.3f) over %d run(s)"
              % (mv, 1 - mv, len(verb)))
        print("  predictive lift : %s over %d run(s) with a control"
              % ("mean %+.3f" % mean(lifts) if lifts else "—", len(lifts)))
        print("  turnover        : %s over %d consecutive pair(s)"
              % ("mean %.3f" % mean(turns) if turns else "—", len(turns)))
        print("  modes           : %s"
              % ", ".join("%s=%d" % (m, sum(1 for r in rows if r.get("mode") == m))
                          for m in sorted({r.get("mode", "?") for r in rows})))
    else:
        print("  nothing scored yet — run `score_snapshot.py append …` at a checkpoint")

    if n < TREND_FLOOR:
        print("N=%d — no trend claims below %d" % (n, TREND_FLOOR))
        print("The means above are the arithmetic of a small sample and nothing more: with "
              "N below %d, direction, drift and 'lift is positive' are not claims this data "
              "can carry. Insufficient data is a result — report it as one." % TREND_FLOOR)
        return 3

    direction = ("positive — self-reports matched the output better than the context-only "
                 "control did" if mean(lifts) and mean(lifts) > 0 else
                 "≈ zero or negative — reports are not distinguishable from an outsider's "
                 "inference on this data (consistent with confabulation)") if lifts else \
                ("unavailable — no run carried a control, so lift cannot be claimed at any N")
    print("N=%d — trend language is permitted at this N; lift trend: %s" % (n, direction))
    print("Still black-box: no activations were observed, and lift measures only that a "
          "report beat a context-only guess against the same output.")
    return 0


def main():
    argv = sys.argv[1:]
    # Legacy shim: `score_snapshot.py --snapshot …` predates subcommands and is what the
    # skill body and the existing ledger runs use. Read a leading flag as `score`.
    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv = ["score"] + argv

    ap = argparse.ArgumentParser(
        description="score, ledger and aggregate introspect snapshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "the verbless (legacy) form:\n"
            "  score_snapshot.py --snapshot \"a, b, c\" --output-file out.md\n"
            "  A leading flag is read as the `score` subcommand, so every invocation\n"
            "  written before this file grew subcommands still runs verbatim. It is\n"
            "  what introspect/SKILL.md documents; BOTH forms are supported and\n"
            "  neither is deprecated.\n"
            "\n"
            "refusals: a misuse (missing/unreadable --output-file, empty --snapshot,\n"
            "  unknown subcommand) is one line on stderr at exit 2, never a traceback.\n"
            "  `report` exits 3 below N=%d — that is a refusal, not a failure." % TREND_FLOOR))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def scoring_args(p):
        p.add_argument("--snapshot", required=True, help="comma-separated concepts")
        p.add_argument("--control", default="", help="context-only control concepts")
        p.add_argument("--prev", default="", help="previous snapshot, for turnover")
        p.add_argument("--output-file", default=None)
        p.add_argument("--output-text", default=None)

    s = sub.add_parser("score", help="print the metrics JSON; writes nothing "
                       "(also the verbless form: a leading flag implies it)")
    scoring_args(s)
    s.set_defaults(f=cmd_score)

    ap_ = sub.add_parser("append", help="score, write a run json, append the ledger entry")
    scoring_args(ap_)
    ap_.add_argument("--root", default=".")
    ap_.add_argument("--label", required=True, help="the checkpoint label")
    ap_.add_argument("--mode", default="now", choices=["now", "session", "experiment"])
    ap_.add_argument("--glossed", default="", help="the ★/· gloss line, verbatim")
    ap_.add_argument("--control-absent", dest="control_absent", default="",
                     help="why no control was run (recorded instead of a blank)")
    ap_.add_argument("--interpretation", default="",
                     help="one line, run-sized confidence")
    ap_.set_defaults(f=cmd_append)

    r = sub.add_parser("report", help="aggregate the runs; exit 3 below N=%d" % TREND_FLOOR)
    r.add_argument("--root", default=".")
    r.set_defaults(f=cmd_report)

    a = ap.parse_args(argv)
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
