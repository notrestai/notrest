#!/usr/bin/env python3
"""score_snapshot.py — deterministic metrics for introspect snapshots.

Usage:
  score_snapshot.py --snapshot "a, b, c" --output-file out.md
                    [--control "x, y"] [--prev "a, d"] [--output-text "..."]

Prints a JSON object:
  verbalized[], silent[], verbalized_rate, control_hits, control_rate,
  lift (model_hits - control_hits over snapshot size; null without control),
  turnover_vs_prev (1 - Jaccard; null without --prev), sizes.

Matching is deliberately crude and DETERMINISTIC: lowercase, hyphens folded to
spaces; single-word concepts match on word boundary with naive s/es/ed/ing
stemming; multi-word concepts match as substrings of the folded text. Semantic
matches are a human/model judgment — tag them [sem] in the ledger, never here.
"""
import argparse, json, re, sys


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, help="comma-separated concepts")
    ap.add_argument("--control", default="", help="context-only control concepts")
    ap.add_argument("--prev", default="", help="previous snapshot, for turnover")
    ap.add_argument("--output-file", default=None)
    ap.add_argument("--output-text", default=None)
    a = ap.parse_args()

    if a.output_file:
        with open(a.output_file, "r", encoding="utf-8") as f:
            text = f.read()
    elif a.output_text is not None:
        text = a.output_text
    else:
        sys.exit("need --output-file or --output-text")

    snap = parse_concepts(a.snapshot)
    ctrl = parse_concepts(a.control)
    prev = parse_concepts(a.prev)
    if not snap:
        sys.exit("empty snapshot")

    tf = fold(text)
    tw = word_set(tf)

    verbalized = [c for c in snap if concept_hit(c, tw, tf)]
    silent = [c for c in snap if c not in verbalized]
    ctrl_hits = [c for c in ctrl if concept_hit(c, tw, tf)]

    res = {
        "snapshot_size": len(snap),
        "verbalized": verbalized,
        "silent": silent,
        "verbalized_rate": round(len(verbalized) / len(snap), 3),
        "control_size": len(ctrl),
        "control_hits": ctrl_hits,
        "control_rate": round(len(ctrl_hits) / len(ctrl), 3) if ctrl else None,
        "lift": round((len(verbalized) - len(ctrl_hits)) / len(snap), 3)
        if ctrl
        else None,
        "turnover_vs_prev": round(
            1 - len(set(snap) & set(prev)) / len(set(snap) | set(prev)), 3
        )
        if prev
        else None,
        "output_chars": len(text),
    }
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
