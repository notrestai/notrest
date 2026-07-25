#!/usr/bin/env python3
"""compile.py — mine the estate for repeated work. Detection is a SCRIPT.

The model never reads the ledgers to find what repeats; this does — the same
economics as graph.py and archivist's index.py: the machine reads, the session
pays nothing.

Subcommands:
  scan   --root DIR [--transcripts DIR] [--out DIR] [--sim F] [--min-df N]
         Cluster the estate's recorded work by SHAPE; write <out>/candidates.md
         (machine-written; never hand-edit) and <out>/candidates.json (the data
         report and the ritual read).
  report --root DIR [--out DIR]
         One line per ripe candidate, for a hook or /oracle to consume.
         Exit 3 when at least one RIPE candidate is still NEW; exit 0 otherwise —
         including when nothing has been scanned yet, so a hook never breaks.
  decide --root DIR --slug S --status NEW|PROPOSED|COMPILED|DECLINED
         [--alias A] [--note T] [--out DIR]
         Append a ruling to <out>/decisions.md; the next scan carries it over.

The thesis, stated where it is implemented: in a ledger of work, FREQUENT tokens
carry the PROCEDURE and RARE tokens carry the PARAMETERS. So similarity weights
every shared token by its document frequency — the opposite of IDF, deliberately.
Here repetition is the signal, not the noise.

Honesty: the ranking measures REPETITION, never value. A candidate is ripe
because the estate recorded the same shape three or more times. Whether it is
worth compiling is a judgment the ritual makes — never the scanner.
"""
import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# ── knobs (all overridable on the command line) ───────────────────────────────
MIN_DF = 3            # a token joins the procedure vocabulary at this many entries
BOILER = 0.85         # ...and leaves it again above this share (format boilerplate)
SIM = 0.24            # df-weighted Jaccard threshold, average-link. Swept against
                      # this repo's real estate (sim 0.20→0.34 × min-df 2→3): 0.20
                      # over-merges the release ritual with unrelated ships (15
                      # members, cohesion 0.18); 0.28+ splits it three ways. 0.24
                      # recovers it whole at 9 members. Raise it when candidates
                      # read over-merged; lower it when one ritual shows up twice.
FUSE = 0.60           # df-weighted core containment that merges two candidates
CORE_SHARE = 0.60     # a token is CORE when this share of members carry it
RIPE_AT = 3           # occurrences that make a candidate ripe
LIST_AT = 2           # occurrences that make a candidate worth listing at all
MAX_ITEMS = 400       # per family; oldest are dropped and the drop is reported
GRAM = 5              # transcript command n-gram width
MAX_TRANSCRIPTS = 400
READ_CAP = 20_000_000  # bytes read per transcript file

STATUSES = ("NEW", "PROPOSED", "COMPILED", "DECLINED")
CANDIDATES_MD = "candidates.md"
CANDIDATES_JSON = "candidates.json"
DECISIONS_MD = "decisions.md"

# ── normalization ─────────────────────────────────────────────────────────────
PLACEHOLDERS = [
    (re.compile(r"\bv?\d+\.\d+(?:\.\d+)*\b"), " <ver> "),
    (re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b"), " <sha> "),
    # Bare integers are deleted, not placeheld. Measured on this repo: a `<num>`
    # placeholder is the single highest-frequency token in any work ledger
    # ("round 3", "5 findings", "44/44") and it clustered nine unrelated spend
    # purposes into a candidate whose entire shared shape was "contains a number".
    (re.compile(r"\b\d[\d,]*\b"), " "),
]
SPLIT = re.compile(r"[^a-z0-9<>]+")
SUFFIXES = ("ings", "ing", "ied", "ies", "ed", "es", "s")

_STOP_RAW = """a an and the of to in on for with at by from as is are was were be been it its
this that these those or but if then so not no into per via vs all any one two new now more most
than when what which who how why up out over under after before first last next also only just
still both each same other some own do does did done can will would should could has have had
we our you your they their he she i me my ok yes non let than through while about across against
between during without within upon toward again here there where than thing things stuff"""


def _stem(t):
    if t.startswith("<") or len(t) <= 3:
        return t
    for suf in SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            t = t[: -len(suf)]
            break
    if len(t) > 3 and t[-1] == t[-2] and t[-1] not in "aeiou":
        t = t[:-1]
    if len(t) > 3 and t.endswith("e"):
        t = t[:-1]
    if len(t) > 3 and t.endswith("y"):
        t = t[:-1]
    return t


STOP = {_stem(w) for w in _STOP_RAW.split()}

# Estate vocabulary — the harness's words for its OWN machinery, not for the work.
#
# Measured defect (2026-07-25): the top candidate on this repo was `lan` at 31
# occurrences, same-shape 0.15, and its whole evidence set was spend purposes —
# "comprehensive review: model-policy lane (…)", "visual-plan research lane (…)".
# The scanner had clustered the seat's word for a LANE and called it a workflow.
#
# Cause, and why the fix belongs here rather than in the threshold: spend purposes
# share this vocabulary BY CONSTRUCTION — every lane is a "lane", every build has
# "rounds", "gates", "fixtures", every ship is "shipped". Because similarity is
# df-weighted (inverse-IDF, deliberately: frequent tokens carry the procedure),
# these are the HEAVIEST tokens in the corpus — exactly backwards here. They are
# frequent because of how the estate writes itself down, not because a procedure
# repeated. Dropped AFTER masking and BEFORE weighting, so they never reach the
# document-frequency count, the signatures, the slug, or the fusion weights.
#
# The bar for adding a word: it describes the RECORDING apparatus (who ran it, in
# what arrangement, with what receipt) rather than the job that was run.
_ESTATE_STOP_RAW = """lane lanes round rounds seat gate gated gates fixture fixtures shipped
ship spend ledger evidence verified agent agents opus model tokens purpose receipt receipts"""

ESTATE_STOP = {_stem(w) for w in _ESTATE_STOP_RAW.split()}


def tokens(text):
    """Lowercase → mask volatile literals → split → stem → drop stopwords/shorts.

    Volatile literals become placeholders on purpose: `v2.16.1` and `v3.0.0` are
    the same procedural marker with different parameters, which is the entire
    distinction this skill exists to make.
    """
    t = text.lower()
    for rx, rep in PLACEHOLDERS:
        t = rx.sub(rep, t)
    out = []
    for raw in SPLIT.split(t):
        if not raw:
            continue
        s = raw if raw.startswith("<") else _stem(raw)
        if s in STOP or s in ESTATE_STOP or (len(s) < 3 and not s.startswith("<")):
            continue
        out.append(s)
    return out


# ── estate readers ────────────────────────────────────────────────────────────
COORD_RE = re.compile(
    r"^-\s*\[(?P<ts>\d{4}-\d{2}-\d{2}[^\]]*)\]\s*(?:\[(?P<lane>[^\]]*)\]\s*)?(?P<body>.+)$")
AGENT_RE = re.compile(
    r"^-\s*\[(?P<ts>\d{4}-\d{2}-\d{2}[^\]]*)\]\s*agent=(?P<id>\S+).*?\|\s*last:\s*"
    r"(?P<last>.*?)\s*\|\s*transcript:\s*(?P<tp>\S+)\s*$")
SPEND_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+lane=(?P<lane>\S+)\s+model=(?P<model>\S+).*?"
    r'purpose="(?P<purpose>.*)"\s*$')


class Item:
    __slots__ = ("family", "ref", "ts", "text", "toks", "sig")

    def __init__(self, family, ref, ts, text):
        self.family = family
        self.ref = ref
        self.ts = ts
        self.text = re.sub(r"\s+", " ", text).strip()
        self.toks = tokens(self.text)
        self.sig = frozenset()


def _read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def read_coord(root):
    """COORD.md ledger lines: `- [ts] [lane] ask -> landed | evidence: ...`.

    The lane tag is parsed OFF, never tokenized: it is on every line by
    construction, so it carries no information about what the work was.
    """
    # The ledger rolls into VOLUMES: COORD.md is the active volume, sealed ones
    # are COORD-<NNN>.md (immutable, oldest first). COORD-ARCHIVE.md is the
    # retired compaction scheme — still read so legacy repos keep their history.
    sealed = sorted(p.name for p in root.glob("COORD-*.md")
                    if p.stem.split("-")[-1].isdigit() and p.stem.count("-") == 1)
    items = []
    for fn in sealed + ["COORD-ARCHIVE.md", "COORD.md"]:
        text = _read(root / fn)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = COORD_RE.match(line.strip())
            if m:
                items.append(Item("coord", f"{fn}:{i}", m.group("ts"), m.group("body")))
    return items


def read_agents(root):
    """COORD-AGENTS.md entries. Where the hook wrote `last: ?` (transcript not yet
    on disk when it fired), fall back to the sibling agent-<id>.meta.json, which
    carries the lane's description — archivist's trick, applied to detection."""
    items = []
    text = _read(root / "COORD-AGENTS.md")
    if text is None:
        return items
    for i, line in enumerate(text.splitlines(), 1):
        m = AGENT_RE.match(line.strip())
        if not m:
            continue
        last, tp = m.group("last"), m.group("tp")
        if last in ("", "?"):
            meta = pathlib.Path(tp).with_suffix("").as_posix() + ".meta.json"
            raw = _read(pathlib.Path(meta))
            if raw:
                try:
                    last = str(json.loads(raw).get("description") or "").strip()
                except Exception:
                    last = ""
        if not last or last == "?":
            continue
        items.append(Item("agents", f"COORD-AGENTS.md:{i}", m.group("ts"), last))
    return items


def read_spend(root):
    """spend/ledger.md purpose= strings — the most explicit statement of what a
    lane was FOR that the estate contains."""
    items = []
    text = _read(root / "spend" / "ledger.md")
    if text is None:
        return items
    for i, line in enumerate(text.splitlines(), 1):
        m = SPEND_RE.match(line.strip())
        if m and m.group("purpose").strip():
            items.append(Item("spend", f"spend/ledger.md:{i}", m.group("ts"),
                              m.group("purpose")))
    return items


# ── clustering: frequent tokens are the procedure ─────────────────────────────
def procedure_vocab(items, min_df, boiler):
    df = Counter()
    for it in items:
        df.update(set(it.toks))
    n = max(1, len(items))
    return {t: c for t, c in df.items() if c >= min_df and c <= boiler * n}


def wjaccard(a, b, w):
    if not a or not b:
        return 0.0
    inter = sum(w.get(t, 1) for t in (a & b))
    if not inter:
        return 0.0
    union = sum(w.get(t, 1) for t in (a | b))
    return inter / union if union else 0.0


def agglomerate(sigs, w, thr):
    """Average-link agglomerative merge. Average-link (not single-link) on
    purpose: single-link chains two unrelated rituals together through one
    shared word, and a chained cluster is a lie about what repeated."""
    clusters = [[i] for i in range(len(sigs))]
    cache = {}

    def link(ca, cb):
        key = (id(ca), id(cb))
        if key in cache:
            return cache[key]
        tot = 0.0
        for i in ca:
            for j in cb:
                tot += wjaccard(sigs[i], sigs[j], w)
        v = tot / (len(ca) * len(cb))
        cache[key] = v
        return v

    while True:
        best = None
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                s = link(clusters[a], clusters[b])
                if s >= thr and (best is None or s > best[0]):
                    best = (s, a, b)
        if best is None:
            break
        _, a, b = best
        clusters[a] = clusters[a] + clusters.pop(b)
        cache.clear()
    return clusters


NOISE_SLUG = {"<ver>", "<sha>", "evidenc", "lane", "session", "agent"}


def _slug(core, counts, n, df, members, items):
    """Name the candidate from what is most CHARACTERISTIC of it — core tokens
    first, ranked by how many of its own members carry them, then topped up from
    the wider signature so a name has something to hold onto.

    Placeholders and pure bookkeeping never name a candidate: a slug reading
    `ver-sha` tells a reader nothing. A machine-derived name is a handle, not a
    title — `decide --alias release-ritual` is how a candidate gets its real one.
    """
    def rank(pool):
        return sorted((t for t in pool if t not in NOISE_SLUG and not t.startswith("<")),
                      key=lambda t: (-counts.get(t, 0), -df.get(t, 0), t))
    picked = rank(core)
    if len(picked) < 3:
        topup = [t for t in rank(counts) if t not in picked and counts[t] >= 0.4 * n]
        picked += topup[: 3 - len(picked)]
    if not picked:
        picked = [t for t in items[members[0]].toks if not t.startswith("<")][:3]
    return "-".join(picked[:3]) or "candidate"


def build_candidates(items, df, clusters, kind="estate"):
    out = []
    for members in clusters:
        n = len(members)
        if n < LIST_AT:
            continue
        counts = Counter()
        for i in members:
            counts.update(items[i].sig)
        core = {t for t, c in counts.items() if c >= CORE_SHARE * n}
        # same-shape ratio = mean pairwise (unweighted) signature overlap. Read it
        # as cohesion: ~0.5+ is one ritual recorded many times; ~0.15 is a loose
        # family the clustering swept together and a reader should distrust.
        pairs = [(i, j) for k, i in enumerate(members) for j in members[k + 1:]]
        shape = (sum(len(items[i].sig & items[j].sig) / len(items[i].sig | items[j].sig)
                     for i, j in pairs if items[i].sig | items[j].sig)
                 / len(pairs)) if pairs else 1.0
        sigunion = sorted(counts, key=lambda t: (-counts[t], -df.get(t, 0), t))
        srcs = Counter(items[i].family for i in members)
        ev = [{"ref": items[i].ref, "ts": items[i].ts, "text": items[i].text[:180]}
              for i in sorted(members, key=lambda i: items[i].ref)]
        out.append({
            "slug": _slug(core, counts, n, df, members, items),
            "alias": "",
            "occurrences": n,
            "shape": round(shape, 2),
            "ripe": n >= RIPE_AT,
            "status": "NEW",
            "kind": kind,
            "core": sorted(core, key=lambda t: (-df.get(t, 0), t)),
            "signature": sigunion[:14],
            "sources": dict(sorted(srcs.items())),
            "evidence": ev,
        })
    return out


def fuse(cands, gdf, thr):
    """Merge candidates whose CORES describe the same job.

    Two reasons this is not optional. The release ritual leaves lines in COORD
    AND purposes in the spend ledger, so counting them separately understates the
    repetition twice over. And one ritual drifts in wording across a year of
    ledger — measured here, the same release ritual split into a
    `<ver>·commit·follows` shape and a `<ver>·commit·plugin·hook·ship` shape.

    So the test is df-weighted CONTAINMENT, not Jaccard: when the smaller core is
    mostly inside the larger one, it is the same ritual recorded in less detail.
    Weights are global document frequency — the shared marker carries the weight,
    the extra detail does not veto the match."""
    cands = sorted(cands, key=lambda c: -c["occurrences"])
    merged = []
    for c in cands:
        for m in merged:
            a, b = set(c["core"]), set(m["core"])
            inter = sum(gdf.get(t, 1) for t in (a & b))
            small = min(sum(gdf.get(t, 1) for t in a), sum(gdf.get(t, 1) for t in b))
            if len(a) >= 2 and len(b) >= 2 and small and inter / small >= thr:
                m["occurrences"] += c["occurrences"]
                m["evidence"] += c["evidence"]
                for k, v in c["sources"].items():
                    m["sources"][k] = m["sources"].get(k, 0) + v
                m["signature"] = sorted(set(m["signature"]) | set(c["signature"]))[:14]
                m["core"] = sorted(b | a)
                m["shape"] = round(min(m["shape"], c["shape"]), 2)
                m["ripe"] = m["occurrences"] >= RIPE_AT
                break
        else:
            merged.append(dict(c))
    return merged


WEAK_SPEND_SHARE = 0.80   # above this share of spend evidence, with no COORD line...


def mark_weak_source(cands):
    """Flag candidates whose evidence is almost entirely spend-ledger purposes.

    Not all sources are equal witnesses. A COORD line records what was ASKED and
    what LANDED — it is a statement about the work. A spend purpose records what a
    lane was CALLED — it is a label the seat typed while paying for the lane, and
    labels rhyme with each other even when the jobs do not. So a cluster built
    only out of purposes is evidence that the seat NAMES things consistently,
    which is not the same claim as "this procedure repeated".

    Demotion, never deletion: the cluster may still be real, and hiding it would
    be the scanner deciding instead of reporting. It is marked `weak-source` and
    sorted below every candidate with any other support, so it can never present
    itself as the #1 thing to compile on the strength of shared vocabulary alone.
    """
    for c in cands:
        srcs = c.get("sources", {})
        total = sum(srcs.values()) or 1
        c["weak_source"] = (srcs.get("spend", 0) / total > WEAK_SPEND_SHARE
                            and not srcs.get("coord", 0))
    return cands


# ── transcripts (optional, never required) ────────────────────────────────────
def _tool_uses(obj, out):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name") == "Bash":
            cmd = (obj.get("input") or {}).get("command")
            if isinstance(cmd, str):
                out.append(cmd)
        for v in obj.values():
            _tool_uses(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _tool_uses(v, out)


def transcript_candidates(tdir, estate_cands):
    """Repeated Bash command n-grams. Cheap by construction: a line is only JSON
    -parsed when the raw text already contains "Bash"."""
    base = pathlib.Path(tdir).expanduser()
    files = sorted(base.rglob("*.jsonl"))[:MAX_TRANSCRIPTS] if base.is_dir() else []
    grams = defaultdict(list)
    for p in files:
        try:
            if p.stat().st_size > READ_CAP:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        cmds = []
        for line in text.splitlines():
            if '"Bash"' not in line:
                continue
            try:
                _tool_uses(json.loads(line), cmds)
            except Exception:
                continue
        for c in cmds:
            w = [x.strip("'\"`") for x in c.lower().split()]
            if len(w) < GRAM:
                continue
            for k in range(len(w) - GRAM + 1):
                grams[" ".join(w[k:k + GRAM])].append(p.name)
    out = []
    for g, hits in grams.items():
        if len(hits) < LIST_AT:
            continue
        gt = set(tokens(g))
        overlaps = ""
        for ec in estate_cands:
            core = set(ec["core"])
            if core and gt and len(core & gt) / len(core | gt) >= 0.34:
                overlaps = ec["slug"]
                break
        seen, refs = set(), []
        for h in hits:
            if h not in seen:
                seen.add(h)
                refs.append(h)
        out.append({
            "slug": "cmd-" + "-".join(
                re.sub(r"[^a-z0-9]+", "", x) for x in g.split()[:3] if x)[:48].strip("-"),
            "alias": "", "occurrences": len(hits), "shape": 1.0,
            "ripe": len(hits) >= RIPE_AT, "status": "NEW", "kind": "cmd",
            "core": sorted(gt), "signature": sorted(gt)[:14],
            "sources": {"transcripts": len(hits)},
            "overlaps": overlaps,
            "evidence": [{"ref": f"transcripts/{r}", "ts": "", "text": g} for r in refs[:5]],
        })
    out.sort(key=lambda c: -c["occurrences"])
    return out[:10], len(files)


# ── decisions (status carry-over) ─────────────────────────────────────────────
DEC_RE = re.compile(r"^-\s*(?:\[(?P<ts>[^\]]*)\]\s*)?(?P<kv>.*)$")


def read_decisions(out):
    p = out / DECISIONS_MD
    text = _read(p)
    if text is None:
        return []
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        m = DEC_RE.match(line)
        raw = {k: (quoted or bare) for k, quoted, bare in
               re.findall(r'(\w+)=(?:"([^"]*)"|(\S+))', m.group("kv"))}
        if raw.get("slug") and raw.get("status", "").upper() in STATUSES:
            rows.append({"slug": raw["slug"], "status": raw["status"].upper(),
                         "alias": raw.get("alias", ""),
                         "sig": [s for s in raw.get("sig", "").split(",") if s],
                         "note": raw.get("note", "")})
    return rows


def apply_decisions(cands, decs):
    """Latest ruling per slug wins. A slug can drift between scans as a ledger
    grows, so a ruling also matches on its recorded core (Jaccard >= 0.6): a
    DECLINED candidate stays declined even when the scanner renames it."""
    latest = {}
    for d in decs:
        latest[d["slug"]] = d
    for c in cands:
        d = latest.get(c["slug"])
        if d is None:
            best, bs = None, 0.0
            for cand_d in latest.values():
                a, b = set(cand_d["sig"]), set(c["core"])
                if a and b:
                    s = len(a & b) / len(a | b)
                    if s >= 0.6 and s > bs:
                        best, bs = cand_d, s
            d = best
        if d:
            c["status"] = d["status"]
            c["alias"] = d.get("alias", "") or c["alias"]
            c["note"] = d.get("note", "")
    return cands


# ── rendering ─────────────────────────────────────────────────────────────────
def render_md(data):
    p = data["params"]
    b = [
        "# compile/candidates.md — repeated work, mined from the estate",
        "",
        "**Machine-written by `compile.py scan`. NEVER hand-edit — the next scan",
        "overwrites this file.** To rule on a candidate use `compile.py decide`",
        f"(it appends to `{DECISIONS_MD}`, which the next scan carries over here).",
        "",
        "**Ranking measures REPETITION, not value.** A candidate is RIPE because the",
        f"estate recorded the same shape {RIPE_AT}+ times — never because compiling it is",
        "worth doing. That judgment belongs to `/compile <slug>`, and to the owner.",
        "",
        "**`weak-source`** marks a candidate whose evidence is >"
        f"{int(WEAK_SPEND_SHARE * 100)}% spend-ledger purposes",
        "with no COORD line behind it. Spend purposes say what a lane was CALLED; COORD",
        "lines say what was ASKED and what LANDED. Such candidates are demoted below every",
        "other candidate — read them as shared vocabulary until the ledger says otherwise.",
        "",
        f"Last scan: {data['generated']} · root: `{data['root']}`",
        "",
        "| source | present | entries |",
        "|---|---|---|",
    ]
    for s in data["sources"]:
        b.append(f"| {s['name']} | {'yes' if s['present'] else 'NO'} | {s['items']} |")
    b += ["",
          f"Parameters: sim={p['sim']} · min-df={p['min_df']} · core-share={CORE_SHARE} · "
          f"ripe>={RIPE_AT} · listed>={LIST_AT}",
          ""]
    if data.get("notes"):
        b += ["Notes: " + " · ".join(data["notes"]), ""]
    b += ["## Ranked candidates", "",
          "| # | candidate | occ | same-shape | ripe | status | kind | sources |",
          "|---|---|---|---|---|---|---|---|"]
    if not data["candidates"]:
        b.append("| — | *(nothing repeated twice yet — a thin estate gets an empty table, "
                 "not an invented one)* | | | | | | |")
    for c in data["candidates"]:
        name = (c["slug"] + (f" ({c['alias']})" if c.get("alias") else "")
                + (" **weak-source**" if c.get("weak_source") else ""))
        srcs = " ".join(f"{k}={v}" for k, v in c["sources"].items())
        b.append(f"| {c['rank']} | {name} | {c['occurrences']} | {c['shape']:.2f} | "
                 f"{'RIPE' if c['ripe'] else '—'} | {c['status']} | {c['kind']} | {srcs} |")
    b += ["", "## Evidence", ""]
    for c in data["candidates"]:
        b.append(f"### {c['rank']} · {c['slug']}"
                 + (f" ({c['alias']})" if c.get("alias") else "")
                 + f" — {c['occurrences']}× · same-shape {c['shape']:.2f} · "
                 + ("RIPE" if c["ripe"] else "not ripe") + f" · {c['status']}"
                 + (" · **weak-source** (spend purposes only, no COORD support)"
                    if c.get("weak_source") else ""))
        b.append(f"core: `{', '.join(c['core']) or '(none)'}`")
        b.append(f"signature: `{', '.join(c['signature'])}`")
        if c.get("overlaps"):
            b.append(f"overlaps estate candidate: `{c['overlaps']}`")
        if c.get("note"):
            b.append(f"ruling note: {c['note']}")
        b.append("")
        for e in c["evidence"][:12]:
            b.append(f"- `{e['ref']}` — {e['text']}")
        if len(c["evidence"]) > 12:
            b.append(f"- …and {len(c['evidence']) - 12} more")
        b.append("")
    return "\n".join(b) + "\n"


# ── commands ──────────────────────────────────────────────────────────────────
def outdir(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    o = pathlib.Path(a.out).expanduser()
    return (o if o.is_absolute() else root / o)


def cmd_scan(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    out = outdir(a)
    out.mkdir(parents=True, exist_ok=True)
    notes = []

    families = {"coord": read_coord(root), "agents": read_agents(root),
                "spend": read_spend(root)}
    sources = [
        {"name": "COORD.md", "present": (root / "COORD.md").is_file(),
         "items": sum(1 for i in families["coord"] if i.ref.startswith("COORD.md"))},
        {"name": "COORD-ARCHIVE.md", "present": (root / "COORD-ARCHIVE.md").is_file(),
         "items": sum(1 for i in families["coord"] if i.ref.startswith("COORD-ARCHIVE"))},
        {"name": "COORD-AGENTS.md", "present": (root / "COORD-AGENTS.md").is_file(),
         "items": len(families["agents"])},
        {"name": "spend/ledger.md", "present": (root / "spend" / "ledger.md").is_file(),
         "items": len(families["spend"])},
    ]

    cands = []
    for fam, items in families.items():
        if len(items) > MAX_ITEMS:
            notes.append(f"{fam}: {len(items)} entries, newest {MAX_ITEMS} scanned")
            items = items[-MAX_ITEMS:]
        if len(items) < LIST_AT:
            continue
        df = procedure_vocab(items, a.min_df, BOILER)
        for it in items:
            it.sig = frozenset(t for t in it.toks if t in df)
        cands += build_candidates(items, df, agglomerate([i.sig for i in items], df, a.sim))
    # Fusion weights come from ONE global document frequency: per-family weights
    # are not comparable across ledgers with different vocabularies.
    gdf = Counter()
    for items in families.values():
        for it in items:
            gdf.update(set(it.toks))
    cands = fuse(cands, gdf, FUSE)

    tcount = 0
    if a.transcripts:
        tc, tcount = transcript_candidates(a.transcripts, cands)
        cands += tc
    sources.append({"name": "transcripts", "present": bool(a.transcripts),
                    "items": tcount})

    cands = mark_weak_source(cands)
    cands = apply_decisions(cands, read_decisions(out))
    # weak-source first in the key: a spend-purpose-only cluster never outranks a
    # candidate the COORD ledger actually witnessed, however many times it recurs.
    cands.sort(key=lambda c: (c["weak_source"], not c["ripe"], -c["occurrences"],
                              -c["shape"], c["slug"]))
    for i, c in enumerate(cands, 1):
        c["rank"] = i

    data = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"),
            "root": root.as_posix(), "sources": sources, "notes": notes,
            "params": {"sim": a.sim, "min_df": a.min_df, "boiler": BOILER,
                       "core_share": CORE_SHARE, "ripe_at": RIPE_AT},
            "candidates": cands}
    (out / CANDIDATES_JSON).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    (out / CANDIDATES_MD).write_text(render_md(data), encoding="utf-8")
    ripe = [c for c in cands if c["ripe"]]
    print(f"{out / CANDIDATES_MD}: {len(cands)} candidate(s), {len(ripe)} ripe "
          f"(from {sum(len(v) for v in families.values())} estate entries"
          + (f", {tcount} transcript(s)" if a.transcripts else "") + ")")
    return 0


def cmd_report(a):
    out = outdir(a)
    p = out / CANDIDATES_JSON
    raw = _read(p)
    if raw is None:
        print(f"[compile] no scan yet at {out} — run: compile.py scan --root "
              f"{pathlib.Path(a.root).expanduser().resolve()}")
        return 0
    try:
        data = json.loads(raw)
    except Exception:
        print(f"[compile] {p} is unreadable — re-run scan")
        return 0
    ripe = [c for c in data.get("candidates", []) if c.get("ripe")]
    fresh = [c for c in ripe if c.get("status") == "NEW"]
    for c in ripe:
        name = c["slug"] + (f" ({c['alias']})" if c.get("alias") else "")
        print(f"[compile] RIPE {name} · {c['occurrences']}× · shape "
              f"{c['shape']:.2f} · {c['status']} · {c['kind']}"
              + (" · weak-source" if c.get("weak_source") else ""))
    if fresh:
        print(f"[compile] {len(fresh)} ripe candidate(s) not yet ruled on — "
              f"/compile {fresh[0]['slug']} reconstructs its contract from the trail; "
              f"compile.py decide records a ruling either way.")
    elif not ripe:
        print(f"[compile] no ripe candidates (ripe needs >= {RIPE_AT} occurrences; "
              f"{len(data.get('candidates', []))} tracked) · scanned {data.get('generated')}")
    else:
        print(f"[compile] {len(ripe)} ripe candidate(s), all ruled on · "
              f"scanned {data.get('generated')}")
    return 3 if fresh else 0


def cmd_decide(a):
    out = outdir(a)
    out.mkdir(parents=True, exist_ok=True)
    status = a.status.upper()
    if status not in STATUSES:
        sys.exit(f"status must be one of {'|'.join(STATUSES)}")
    sig, known = "", False
    raw = _read(out / CANDIDATES_JSON)
    if raw:
        try:
            for c in json.loads(raw).get("candidates", []):
                if c["slug"] == a.slug:
                    sig, known = ",".join(c["core"]), True
                    break
        except Exception:
            pass
    p = out / DECISIONS_MD
    if not p.exists():
        p.write_text(
            "# compile/decisions.md — rulings on repeated-work candidates\n"
            "#\n"
            "# Append-only, via `compile.py decide` (hand-written lines in the same\n"
            "# shape are parsed too). The latest line per slug wins, and a ruling also\n"
            "# matches on its recorded `sig=` core, so a candidate the scanner renames\n"
            "# keeps its ruling. Statuses: " + " | ".join(STATUSES) + "\n\n",
            encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    note = re.sub(r"\s+", " ", a.note or "").strip().replace('"', "'")
    line = (f'- [{ts}] slug={a.slug} status={status}'
            + (f' alias={a.alias}' if a.alias else "")
            + (f' sig={sig}' if sig else "")
            + f' note="{note}"\n')
    with open(p, "a", encoding="utf-8") as f:
        f.write(line)
    print("recorded:", line.strip())
    if not known:
        print(f"[compile] note: {a.slug!r} is not in the last scan — ruling stored anyway "
              f"(no sig recorded, so carry-over is slug-exact only)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="mine the estate for repeated work")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="cluster the estate and write candidates.md")
    s.add_argument("--root", default=".")
    s.add_argument("--out", default="compile")
    s.add_argument("--transcripts", default=None,
                   help="optional dir of session .jsonl transcripts (never required)")
    s.add_argument("--sim", type=float, default=SIM)
    s.add_argument("--min-df", dest="min_df", type=int, default=MIN_DF)
    s.set_defaults(f=cmd_scan)

    r = sub.add_parser("report", help="one line per ripe candidate; exit 3 if any is NEW")
    r.add_argument("--root", default=".")
    r.add_argument("--out", default="compile")
    r.set_defaults(f=cmd_report)

    d = sub.add_parser("decide", help="record a ruling that survives the next scan")
    d.add_argument("--root", default=".")
    d.add_argument("--out", default="compile")
    d.add_argument("--slug", required=True)
    d.add_argument("--status", required=True)
    d.add_argument("--alias", default="")
    d.add_argument("--note", default="")
    d.set_defaults(f=cmd_decide)

    a = ap.parse_args()
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
