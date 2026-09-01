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
    # S81: `seq` is the INGESTION POSITION -- the order read_coord walked the volumes
    # (sealed, then archive, then the active COORD.md) and the lines within them. An
    # append-only file's TRUE order is positional; its stamps can contradict it, and a
    # composed stamp then reorders lines that cannot have moved. Order keys on `seq`;
    # `ts` stays for display and for spans, where it is bounded instead.
    __slots__ = ("family", "ref", "ts", "text", "toks", "sig", "meta", "seq")

    def __init__(self, family, ref, ts, text, meta=None, seq=0):
        self.family = family
        self.ref = ref
        self.ts = ts
        self.seq = seq
        self.text = re.sub(r"\s+", " ", text).strip()
        self.toks = tokens(self.text)
        self.sig = frozenset()
        # Carried for `contract` only: the lane/model/transcript facts that make a
        # citation walkable. Clustering never reads it — those fields are on every
        # line by construction and would cluster the apparatus, not the work.
        self.meta = meta or {}


def _read(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _stamp_positions(families):
    """S81: stamp each item with its INGESTION POSITION within its family.

    An append-only file's true order is POSITIONAL; a composed stamp can assert an
    order that contradicts it, and sorting by the stamp then moves lines that cannot
    have moved. Position is recoverable here because read_coord walks the volumes in
    order (sealed oldest-first, then archive, then the active COORD.md) and the lines
    within each in order. Cross-family order was never positional -- those are
    different files -- so `seq` is per-family and the sort carries family as a
    tiebreak. This repairs the CONSUMER; no stamp anywhere is rewritten.
    """
    for fam in families.values():
        for n, it in enumerate(fam):
            it.seq = n
    return families


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
                items.append(Item("coord", f"{fn}:{i}", m.group("ts"), m.group("body"),
                                  {"lane": m.group("lane") or ""}))
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
        items.append(Item("agents", f"COORD-AGENTS.md:{i}", m.group("ts"), last,
                          {"id": m.group("id"), "transcript": tp}))
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
                              m.group("purpose"),
                              {"lane": m.group("lane"), "model": m.group("model")}))
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

    families = _stamp_positions({"coord": read_coord(root), "agents": read_agents(root),
                                 "spend": read_spend(root)})
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
    # tmp + replace (hooks-fight audit, 2026-09-01): three readers hit this file —
    # session-start's nudge, the pulse layer, and report — while the DETACHED pulse
    # scan rewrites it. Readers guard against torn JSON, but a torn write should be
    # impossible, not merely survivable.
    for name, body in ((CANDIDATES_JSON, json.dumps(data, indent=1) + "\n"),
                       (CANDIDATES_MD, render_md(data))):
        tmp = out / (name + ".tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(out / name)
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


# ── auto: the owner's standing authorization to BUILD a ripe candidate ────────
#
# The gap this closes: the scanner is automatic and the nudge is automatic, but the
# build waited on a human typing /compile. `auto --on` leaves a marker the SessionStart
# hook reads, which turns that nudge into a directive the seat may act on.
#
# What the marker authorizes is exactly one thing: DISPATCHING a builder lane. It does
# not authorize installation, and it never can. A compiled runtime stays isolated under
# compile/<slug>/ and wiring it in is a versioned release the owner gates — Part 3 of
# the skill, unchanged. Kept as a FILE rather than a flag so the standing authorization
# is visible on disk, survives the seat, and can be revoked by deleting it.
AUTO_MARK = ".auto-build"


def _auto_opted(p):
    """True only for a well-formed opt-in. A corrupt marker is not an opt-in."""
    raw = _read(p)
    if not raw:
        return False
    try:
        d = json.loads(raw)
    except Exception:
        return False
    return isinstance(d, dict) and d.get("opted") is True


def _estate_root_mismatch(root):
    """The path the HOOKS would resolve, when it differs from the given root — else None.
    Mirrors estate-root.sh only far enough to REFUSE rather than guess (refuter F2,
    2026-09-01: a marker written at a subdirectory is read by nobody, and --off at the
    real root cannot clear it). Git toplevel first; else the nearest ancestor carrying
    COORD.md within 3 levels. Duplicating the full resolver would be a second copy of
    it — this is a refusal predicate, not a resolver."""
    import os as _os
    import subprocess as _sp
    r = _os.path.realpath(str(root))
    try:
        top = _sp.run(["git", "-C", r, "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True, timeout=10)
        if top.returncode == 0:
            t = _os.path.realpath(top.stdout.strip())
            return t if t != r else None
    except Exception:
        pass
    if _os.path.isfile(_os.path.join(r, "COORD.md")):
        return None
    d = r
    for _ in range(3):
        d = _os.path.dirname(d)
        if not d or d == "/":
            break
        if _os.path.isfile(_os.path.join(d, "COORD.md")):
            return d
    return None


def cmd_auto(a):
    real = _estate_root_mismatch(str(outdir(a).parent))
    if real:
        sys.stderr.write("auto-build: %s is not the estate root the hooks resolve — the "
                         "marker there would be read by nobody. Use --root %s\n"
                         % (outdir(a).parent, real))
        return 2
    out = outdir(a)
    p = out / AUTO_MARK
    if a.off:
        was = p.exists()
        try:
            p.unlink()
        except OSError:
            pass
        print("auto-build: OFF" + ("" if was else " (was already off)") + f" — {p}")
        return 0
    if a.on:
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
        # tmp + replace: a half-written marker must never be readable as an opt-in.
        tmp = out / (AUTO_MARK + ".tmp")
        tmp.write_text(json.dumps({"opted": True, "stamp": stamp}) + "\n", encoding="utf-8")
        tmp.replace(p)
        print(f"auto-build: ON ({stamp}) — {p}")
        print("[compile] this authorizes DISPATCH only: a compiled runtime still never "
              "auto-installs. Shipping stays the owner's act.")
        return 0
    if _auto_opted(p):
        try:
            stamp = json.loads(_read(p)).get("stamp", "?")
        except Exception:
            stamp = "?"
        print(f"auto-build: ON since {stamp} — {p}")
        return 0
    print("auto-build: OFF" + (" (marker present but unreadable — treated as OFF)"
                               if p.exists() else "")
          + f" — turn it on with: compile.py auto --on --root {a.root}")
    return 5


# ── contract: Step 1 of the ritual, pre-filled from the trail ─────────────────
#
# Step 1 asks the seat to walk a candidate's evidence in timestamp order and cite
# every row with a trail token. That walk is a GREP — the estate already holds the
# line numbers, the timestamps, the lanes, the models and the transcript pointers.
# Having the seat re-derive them by reading ledgers is the exact spend this skill
# exists to remove, and a hand-typed citation is the one kind that can be wrong.
#
# What the script fills: the citations, the source line refs, the timestamp order,
# the owner-today column (mined from lane=/model=), and the honest coverage note.
# What it deliberately leaves blank: whether a responsibility is required for parity,
# who owns it after, and why. Those are judgments; a pre-filled judgment would be a
# guess wearing a citation's clothes.
CONTRACT_HEADER = "| # | Responsibility | Evidence | Required for parity? | Owner today | Owner after | Why |"
CONTRACT_RULE = "|---|---|---|---|---|---|---|"
MAX_ROWS = 40


def cite(it):
    """The trail token for one estate item, in the ritual's own citation grammar."""
    if it.family == "coord":
        return f"[COORD {it.ts}]"
    if it.family == "spend":
        return f"[spend {it.ts}]"
    if it.family == "agents":
        return f"[COORD-AGENTS {it.meta.get('id', '?')} → transcript]"
    return f"[{it.family} {it.ts}]"


def owner_today(it):
    """Who ran it, as the ledger recorded it — never as the reader assumes."""
    if it.family == "spend":
        return f"lane={it.meta.get('lane', '?')} model={it.meta.get('model', '?')}"
    if it.family == "agents":
        return "lane=subagent"
    lane = it.meta.get("lane") or "seat"
    return f"seat ({lane})" if lane != "seat" else "seat"


def query_tokens(slug, cands):
    """The slug's tokens — from the scan when the slug is a known candidate (its core
    and signature are what actually clustered), from the slug itself otherwise. The
    fallback is now reachable ONLY for a candidate that exists but clustered on an
    empty token set: `cmd_contract` refuses before it gets here when the scan holds no
    candidate for the slug at all (see `find_candidate`)."""
    for c in cands:
        if slug in (c.get("slug"), c.get("alias")):
            q = set(c.get("core") or []) | set(c.get("signature") or [])
            if q:
                return q, c
    return set(tokens(slug.replace("-", " "))), None


def find_candidate(slug, cands):
    """The scanned candidate this slug names, or None.

    Deliberately separate from `query_tokens`: "did the scan cluster this?" is a fact
    about the scan, "what do we search for?" is a fact about the tokens, and folding
    them together made a candidate with an empty token set indistinguishable from a
    slug the scan never saw. Only the first question may gate a contract."""
    for c in cands:
        if slug in (c.get("slug"), c.get("alias")):
            return c
    return None


def refuse_no_candidate(slug, cands, scanned, out, root):
    """No scanned candidate — print the refusal, emit NOTHING usable, return 3.

    A contract is a claim about a CLUSTER the scanner found. With no candidate there
    is no cluster, only a grep over the slug's own words — and a filled table reads as
    a finding whatever banner sits above it. This script used to print that warning and
    then hand over the table anyway; a caveat above a confident document is read as a
    caveat, so the document is the answer. Nothing goes to stdout here: a redirect must
    produce an empty file, not a document with a disclaimer at the top."""
    w = sys.stderr.write
    w(f"[compile] REFUSED — no scanned candidate named {slug!r}: there is nothing to "
      "reconstruct a contract from, and a pre-filled table would be the invention this "
      "skill exists to prevent. No contract written.\n")
    if scanned:
        known = sorted({c.get("slug") for c in cands if c.get("slug")}
                       | {c.get("alias") for c in cands if c.get("alias")})
        w(f"[compile] the scan at {(out / CANDIDATES_JSON).as_posix()} holds "
          f"{len(cands)} candidate(s):\n")
        for k in known:
            w(f"[compile]     {k}\n")
        w("[compile] use one of those slugs (or an alias) verbatim, or re-run "
          f"`scan --root {root.as_posix()}` if this workflow is newer than the scan.\n")
    else:
        w(f"[compile] no scan on disk — {(out / CANDIDATES_JSON).as_posix()} is absent "
          "or unreadable.\n")
        w(f"[compile] run `scan --root {root.as_posix()}` first, then name a candidate "
          "it produced.\n")
    w("[compile] a hand-named slug is NOT contractable: the scan is what makes a row "
      "set a cluster instead of a grep, and a pre-filled table over a grep is "
      "manufactured evidence for whatever you happened to type.\n")
    return 3


def cmd_contract(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    out = outdir(a)
    cands = []
    raw = _read(out / CANDIDATES_JSON)
    if raw:
        try:
            cands = json.loads(raw).get("candidates", [])
        except Exception:
            cands = []

    # REFUSE TO FILL. Asked before any mining: if the scan holds no candidate for this
    # slug there is nothing to reconstruct a contract FROM, and the only safe output is
    # no output. This is checked against the candidate itself, never against the row
    # count — a real candidate whose cluster comes back empty is a different condition
    # and keeps its own exit below.
    cand = find_candidate(a.slug, cands)
    if cand is None:
        return refuse_no_candidate(a.slug, cands, bool(cands), out, root)

    q, _cand = query_tokens(a.slug, cands)
    if not q:
        print(f"[compile] {a.slug!r} yields no searchable tokens — name the candidate "
              f"with words the ledgers contain, or run scan first")
        return 2

    families = _stamp_positions({"coord": read_coord(root), "agents": read_agents(root),
                                 "spend": read_spend(root)})
    all_items = [it for v in families.values() for it in v]
    # A short query must not match on one weak word; a rich one must not demand all of
    # them (a ledger line records part of a ritual, never the whole vocabulary).
    need = 1 if len(q) <= 2 else 2
    scored = []
    for it in all_items:
        hits = q & set(it.toks)
        if len(hits) >= need:
            scored.append((len(hits), it))
    scored.sort(key=lambda p: (-p[0], p[1].seq, p[1].family, p[1].ref))  # S81: positional tiebreak
    rows = [it for _s, it in scored[: a.max_rows]]
    # S81: was `(it.ts, it.ref)` -- "Step 1 walks in TIME order". A future-stamped line
    # sorted AFTER lines it positionally precedes (driven: ingestion [1,2,3,4] became
    # [1,3,2,4]). Position is the append-only truth and it is already carried, so order
    # keys on it. NOT a stamp repair: the record is untouched.
    rows.sort(key=lambda it: (it.seq, it.family, it.ref))   # Step 1 walks in POSITIONAL order
    known_refs = {e.get("ref") for e in (cand or {}).get("evidence", [])}

    if not rows:
        print(f"[compile] no trail evidence matches {a.slug!r} "
              f"(tokens: {', '.join(sorted(q))}) across "
              f"{len(all_items)} estate entries — there is nothing to reconstruct a "
              f"contract from, and inventing rows would be the failure this skill "
              f"exists to prevent")
        return 3

    b = [f"# Functional contract (DRAFT) — {(cand or {}).get('alias') or a.slug}",
         "",
         f"Pre-filled by `compile.py contract --slug {a.slug}` at "
         f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')} · root `{root.as_posix()}`",
         "",
         "**This is Step 1 half-done, not Step 1 done.** The script filled what the estate "
         "records: the citations, the line refs, the timestamp order, and who ran each entry. "
         "The three judgment columns are deliberately blank — *required for parity*, *owner "
         "after* and *why* are the seat's rulings, and a pre-filled ruling is a guess wearing "
         "a citation's clothes. Rewrite each Responsibility cell into a real responsibility; "
         "the raw ledger text is there as the quote it came from, not as the answer.",
         ""]
    if cand:
        b.append(f"Candidate `{cand['slug']}`"
                 + (f" (alias `{cand['alias']}`)" if cand.get("alias") else "")
                 + f" — {cand['occurrences']}× · same-shape {cand.get('shape')} · "
                 + f"status {cand.get('status')}"
                 + (" · **weak-source** (spend purposes only, no COORD line — read every row "
                    "below as shared vocabulary until a COORD line says otherwise)"
                    if cand.get("weak_source") else ""))
    else:
        # Unreachable: the gate above returns 3 when there is no candidate. Kept as a
        # raise, not as a banner, because the banner that used to live here IS the
        # defect — it announced the row set was a grep and then printed it as a table.
        raise AssertionError("contract reached the builder with no scanned candidate")
    b += ["", CONTRACT_HEADER, CONTRACT_RULE]
    for i, it in enumerate(rows, 1):
        text = it.text.replace("|", "\\|")
        if len(text) > 200:
            text = text[:197] + "…"
        star = " ★" if it.ref in known_refs else ""
        b.append(f"| {i} | _<rewrite as a responsibility>_ — {text} | {cite(it)} "
                 f"`{it.ref}`{star} | ? | {owner_today(it)} | ? | ? |")
    b += ["",
          "★ = also in the scanned candidate's own evidence set.",
          "",
          "## Trail pointers (walk these before ruling on a row)",
          ""]
    tps = [(it.ts, it.meta.get("id", "?"), it.meta.get("transcript", ""))
           for it in rows if it.family == "agents" and it.meta.get("transcript")]
    if tps:
        for ts, aid, tp in tps:
            b.append(f"- `{aid}` [{ts}] → `{tp}`")
    else:
        b.append("- none of the matched rows carry a transcript pointer "
                 "(COORD-AGENTS entries are where those live)")
    b += ["",
          "## Evidence coverage (state this plainly — never claim history you could not access)",
          "",
          "| ledger | present | entries read | matched this slug |",
          "|---|---|---|---|"]
    for fam, label, path in (("coord", "COORD volumes (+ archive)", "COORD*.md"),
                             ("agents", "COORD-AGENTS.md", "COORD-AGENTS.md"),
                             ("spend", "spend/ledger.md", "spend/ledger.md")):
        got = families[fam]
        matched = sum(1 for it in rows if it.family == fam)
        b.append(f"| {label} (`{path}`) | {'yes' if got else 'NO'} | {len(got)} | {matched} |")
    # S81: the span is a claim about TIME, not about order, so it is BOUNDED rather than
    # re-keyed: a stamp in the future is not evidence of when anything happened, and an
    # unbounded span "can END on a day that never happened". Excluded stamps are DISCLOSED,
    # never silently dropped -- a filtered corpus that does not say so is the founding species.
    _now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    _plaus = [it.ts for it in rows if it.ts <= _now]
    _future = len(rows) - len(_plaus)
    span = (f"{min(_plaus)} … {max(_plaus)}" if _plaus else "—")
    if _future:
        span += f" (⛔ {_future} row(s) carry a stamp in the FUTURE and are excluded from the span)"
    b += ["",
          f"- **Span covered:** {span} (the matched rows' own timestamps — not the ledgers').",
          f"- **Matched {len(rows)} of {len(scored)} matching entries** "
          + (f"(capped at --max-rows {a.max_rows}; raise it to see the rest)."
             if len(scored) > len(rows) else "(no cap hit)."),
          "- **Transcripts:** not read by this script. It reads ledger lines only, so any "
          "responsibility that exists ONLY inside a transcript is missing here — walk the "
          "pointers above before calling the contract complete.",
          "- **Compacted history is invisible.** Sealed COORD volumes are read; whatever a "
          "compaction dropped cannot be recovered and must not be guessed at.",
          "",
          "## Before Step 2",
          "",
          "- Reconstruct the COMPLETE workflow: a parity claim over a subset is a lie about "
          "the subset. If a row you remember is not above, the grep missed it — add it by "
          "hand with its own citation.",
          "- A row you cannot cite is `[unverified]` and may not be load-bearing.",
          ""]
    doc = "\n".join(b) + "\n"
    if a.write:
        p = pathlib.Path(a.write).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc, encoding="utf-8")
        print(f"[compile] contract draft written to {p} ({len(rows)} rows)")
    else:
        sys.stdout.write(doc)
    return 0


# ── scaffold: the runtime skeleton, so Step 3 starts from a shape ──────────────
SCAFFOLD_README = """# {slug} — compiled runtime (ISOLATED, installed nowhere)

Scaffolded by `compile.py scaffold --slug {slug}` on {when}.

Nothing here is wired into the harness. Installation is a release, not a flag
(compile SKILL.md Part 3) — until the owner ships it, this directory is a candidate.

## One obvious run command

    python3 {slug}/runner.py run --input <path> --dry-run

## What it does

<one paragraph: the responsibilities from the Step-1 contract that bucket A now owns>

## What it does NOT do

<the responsibilities still owned by a model call (bucket B), a human (C), or nobody
yet. This section is load-bearing: a compiled runtime that is silent about its gaps
gets read as complete.>

## Retained model calls (bucket B)

| purpose | input shape | output shape | validator | retries |
|---|---|---|---|---|
| <one named purpose> | <smallest sufficient> | <typed> | <the code that checks it> | <bounded> |

## Side effects

Every side-effecting path has a replay/dry-run adapter. A drafted message is never
evidence a message was sent.

## Files

- `runner.py` — the entry point (stub: fill in `do_run`).
- `fixture.sh` — the test that must exercise real logic, not mocks agreeing with themselves.
- `BENCHMARK.md` — the fair-benchmark notes (Step 6). Fill it BEFORE quoting a number.
"""

SCAFFOLD_RUNNER = '''#!/usr/bin/env python3
"""runner.py — compiled runtime for `{slug}`. STUB: scaffolded, not written.

Scaffolded by compile.py on {when}. Deliberately unimplemented: `run` exits 4 until
someone fills in `do_run`, so a half-built runtime can never quietly report success.

Contract: python3 stdlib only unless the contract says otherwise; exit 0 = clean,
2 = usage, 3 = a real finding, 4 = not implemented / refused to guess.
"""
import argparse
import sys


def do_run(args):
    """Implement the bucket-A responsibilities from the Step-1 contract here.

    Deterministic only. Every retained model call belongs behind a typed boundary
    with a validator and bounded retries — never an unbounded "do the task" call.
    """
    print("[{slug}] runner is a scaffold — do_run is not implemented")
    return 4


def do_selfcheck(args):
    """What the runtime can assert about itself without doing any work."""
    print("[{slug}] selfcheck: scaffold only — no logic to check yet")
    return 4


def main():
    ap = argparse.ArgumentParser(description="compiled runtime for {slug}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--input", required=False)
    r.add_argument("--dry-run", action="store_true",
                   help="side effects replayed, never performed")
    r.set_defaults(f=do_run)
    s = sub.add_parser("selfcheck")
    s.set_defaults(f=do_selfcheck)
    a = ap.parse_args()
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
'''

SCAFFOLD_FIXTURE = '''#!/bin/bash
# fixture.sh — tests for the `{slug}` compiled runtime. STUB.
#
# The law this file exists to keep: exercise the REAL logic. A test that mocks the
# thing it is testing passes by agreeing with itself, and the refuter lane (Step 4)
# looks for exactly that. Replay fixtures come from the historical scenarios in the
# Step-1 contract, not from freshly invented happy paths.
set -u
SD="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
R="$SD/runner.py"
PASS=0; FAIL=0
ok(){{ PASS=$((PASS+1)); echo "  PASS  $1"; }}
no(){{ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }}
t(){{ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }}

echo "── scaffold sanity (replace these with real cases)"
python3 "$R" --help >/dev/null 2>&1; t "runner --help exits 0" "$?" "0"
python3 "$R" run >/dev/null 2>&1; t "unimplemented run exits 4, never 0" "$?" "4"
python3 "$R" bogus >/dev/null 2>&1; t "unknown subcommand exits 2" "$?" "2"

# TODO: one case per historical scenario from the Step-1 contract.
# TODO: one case per validator on a retained model call (invalid output must be caught).
# TODO: one case proving the dry-run adapter performs NO side effect.

echo
echo "{slug} fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
'''

SCAFFOLD_BENCH = """# Benchmark notes — {slug}

Scaffolded {when}. **Fill this in before quoting a single number.** Step 6's whole
point is that an unfair benchmark is worse than none: it launders a preference into
a measurement.

## Method A — the estate is the historical side

The old workflow's cost and behavior come from what the ledgers actually recorded,
not from a re-run staged to lose.

| # | historical scenario | trail citation | old cost (observed/estimate) | new cost | notes |
|---|---|---|---|---|---|
|   |                     |                |                              |          |       |

## Symmetry checklist (each line is a way this benchmark could cheat)

- [ ] The compiled side is not handed pre-chewed input the old side had to parse.
- [ ] Both sides do the SAME responsibilities — the full contract, not a subset.
- [ ] Failure cases are in the sample, not only the runs that went well.
- [ ] Old-side numbers carry their grade (observed vs estimate) and say which.
- [ ] The one-time compilation cost is reported separately (Step 8), not amortized
      away silently.
- [ ] The quality law (Step 7) outranks every number here: cheaper and worse is a
      regression, and gets reported as one.

## Result

<state the finding, with its grade, and the scenario count it rests on>
"""


def cmd_scaffold(a):
    out = outdir(a)
    slug = re.sub(r"[^a-z0-9._-]+", "-", a.slug.lower()).strip("-")
    if not slug:
        print(f"[compile] {a.slug!r} is not a usable directory name")
        return 2
    d = out / slug
    if d.exists():
        print(f"[compile] {d} already exists — scaffold never overwrites a runtime "
              f"(that is where the work is). Delete it deliberately, or pass a "
              f"different --slug.")
        return 2
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    d.mkdir(parents=True)
    files = {
        "README.md": SCAFFOLD_README.format(slug=slug, when=when),
        "runner.py": SCAFFOLD_RUNNER.format(slug=slug, when=when),
        "fixture.sh": SCAFFOLD_FIXTURE.format(slug=slug),
        "BENCHMARK.md": SCAFFOLD_BENCH.format(slug=slug, when=when),
    }
    for fn, body in files.items():
        p = d / fn
        p.write_text(body, encoding="utf-8")
        if fn.endswith((".py", ".sh")):
            p.chmod(0o755)
    print(f"[compile] scaffolded {d}/ — {', '.join(sorted(files))}")
    print(f"[compile] isolated and installed nowhere. Run it: "
          f"python3 {d / 'runner.py'} run --dry-run  (exits 4 until do_run is written)")
    print(f"[compile] next: Step 3 builds it in ONE persistent Opus lane; "
          f"Step 4 has a DIFFERENT lane attack it.")
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

    c = sub.add_parser("contract",
                       help="Step 1 pre-filled: the responsibility table with trail citations")
    c.add_argument("--root", default=".")
    c.add_argument("--out", default="compile")
    c.add_argument("--slug", required=True)
    c.add_argument("--max-rows", dest="max_rows", type=int, default=MAX_ROWS)
    c.add_argument("--write", default=None, metavar="PATH",
                   help="write the draft to a file instead of stdout")
    c.set_defaults(f=cmd_contract)

    au = sub.add_parser("auto",
                        help="standing authorization to build a ripe candidate; "
                             "bare = status (0 opted / 5 not)")
    au.add_argument("--root", default=".")
    au.add_argument("--out", default="compile")
    g = au.add_mutually_exclusive_group()
    g.add_argument("--on", action="store_true", help="write compile/.auto-build")
    g.add_argument("--off", action="store_true", help="remove compile/.auto-build")
    au.set_defaults(f=cmd_auto)

    sc = sub.add_parser("scaffold",
                        help="create compile/<slug>/ skeleton; never overwrites (exit 2)")
    sc.add_argument("--root", default=".")
    sc.add_argument("--out", default="compile")
    sc.add_argument("--slug", required=True)
    sc.set_defaults(f=cmd_scaffold)

    a = ap.parse_args()
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
