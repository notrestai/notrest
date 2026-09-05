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
  decide --root DIR --slug S --status NEW|PROPOSED|DRAFTED|COMPILED|ADOPTED|PARKED|DECLINED
         [--alias A] [--note T] [--evidence fixture=REF] [--evidence benchmark=REF]
         [--evidence refuter=REF] [--out DIR]
         Append a ruling to <out>/decisions.md; the next scan carries it over.
         ADOPTED REFUSES without all three --evidence receipts (exit 2): an adoption
         that cannot show its fixture, its benchmark and its refuter round is a claim.

  draft  --root DIR [--all-ripe | --slug S] [--out DIR]
         Scaffold every ripe NEW candidate into its own isolated compile/<slug>/ —
         contract + runtime skeleton + benchmark harness — and record it DRAFTED.
         Zero model tokens, idempotent, and it NEVER touches an existing slug.

  auto-run --root DIR [--next | --slug S] [--runner CMD] [--dry-run] [--model M]
         [--max-turns T] [--out DIR]
         The unattended pipeline: oldest DRAFTED candidate → BUILD (headless model
         run) → fixture → REFUTE (headless model run) → benchmark → ADOPT. Every
         rail (estate lock, per-run ceiling, daily cap, two strikes, receipts,
         quiet auth stop) is enforced here rather than hoped for.

The thesis, stated where it is implemented: in a ledger of work, FREQUENT tokens
carry the PROCEDURE and RARE tokens carry the PARAMETERS. So similarity weights
every shared token by its document frequency — the opposite of IDF, deliberately.
Here repetition is the signal, not the noise.

Honesty: the ranking measures REPETITION, never value. A candidate is ripe
because the estate recorded the same shape three or more times. Whether it is
worth compiling is a judgment the ritual makes — never the scanner.
"""
import argparse
import fcntl
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
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

STATUSES = ("NEW", "PROPOSED", "DRAFTED", "COMPILED", "ADOPTED", "PARKED", "DECLINED")
CANDIDATES_MD = "candidates.md"
CANDIDATES_JSON = "candidates.json"
DECISIONS_MD = "decisions.md"
# The lessons half of detection (docket F). A learning or an open question the estate
# wrote down THREE TIMES is not a note any more — it is a rule nobody encoded, and the
# compiled form of a rule is a hook arm or an eval check, not another paragraph.
FINDINGS_STORE = ("archive", "findings.jsonl")
LESSON_KINDS = ("learning", "open")
RULE_MIN_TOKENS = 3   # a statement under this many content tokens is too thin to group on

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
    r"^-\s*\[(?P<ts>\d{4}-\d{2}-\d{2}[^\]]*)\]\s*(?:\[(?P<lane>[^\]]*)\]\s*)?"
    r"agent=(?P<id>\S+).*?\|\s*last:\s*"
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
            if m and not is_machinery_tag(m.group("lane")):
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
        if not m or is_machinery_tag(m.group("lane")):
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


# ⛔ THE OUROBOROS. `auto-run` receipts every headless call to spend/ledger.md with
# lane=daemon and a purpose reading "compile auto-run build: candidate <slug>". Those
# lines are ledger entries like any other — so on the third unattended run the scanner
# clustered THE COMPILER'S OWN RECEIPTS into a ripe candidate, `draft --all-ripe`
# scaffolded it, and `auto-run` would have spent real tokens compiling the act of
# compiling. Found on this lane's own smoke test, 2026-09-05, before the fixture arms
# were written; the estate would have paid for it nightly.
#
# The fix is the ESTATE_STOP principle applied one level up, at the LINE rather than the
# token: a daemon receipt describes the RECORDING APPARATUS — that automation ran and
# what it cost — never a job somebody did. So the lane is dropped at the reader, before
# it can reach the vocabulary, the signatures or the fusion weights. Dropped, not
# stopworded: no wording of the purpose string can smuggle it back in.
DAEMON_LANE_SKIP = "daemon"

# ⛔ THE OUROBOROS HAS A SECOND DOOR (refuter B4, BLOCKER, 2026-09-05). Filtering
# `lane=daemon` in the spend ledger closed the door the daemon writes through — and left
# open the one the OPERATOR writes through. `decide --status ADOPTED` prints a COORD line
# for a human to paste, `auto-run` prints another, and the pulse log lines get pasted too.
# The refuter pasted 12 adopt lines and 12 pulse lines and `scan` returned THREE ripe
# candidates, `slug-adopt-benchmark` at 12x among them. With the marker merely opted,
# estate-pulse runs `draft --all-ripe` on every pulse — so the compiler's own paperwork
# becomes a drafted candidate, on its own, overnight.
#
# THE TAG IS THE TEST. These are the estate's names for its MACHINERY: a line tagged with
# one of them was written BY the harness ABOUT the harness, and no amount of it repeating
# is evidence that a human did the same job twice. Dropped at the reader, before the
# vocabulary, exactly as `lane=daemon` is — one principle, two doors.
MACHINERY_TAGS = {"compile", "hook", "daemon", "pulse"}


def is_machinery_tag(tag):
    return (tag or "").strip().strip("[]").lower() in MACHINERY_TAGS


def read_spend(root):
    """spend/ledger.md purpose= strings — the most explicit statement of what a
    lane was FOR that the estate contains. lane=daemon lines are the exception: see
    the ouroboros note above."""
    items = []
    text = _read(root / "spend" / "ledger.md")
    if text is None:
        return items
    for i, line in enumerate(text.splitlines(), 1):
        m = SPEND_RE.match(line.strip())
        if m and m.group("lane") == DAEMON_LANE_SKIP:
            continue
        if m and m.group("purpose").strip():
            items.append(Item("spend", f"spend/ledger.md:{i}", m.group("ts"),
                              m.group("purpose"),
                              {"lane": m.group("lane"), "model": m.group("model")}))
    return items


def read_lessons(root):
    """`learning` and `open` records from the archivist store — the estate's OWN lessons.

    Read directly rather than through `index.py track --json`: this runs inside the
    pulse layer's 10 s budget, the file is append-only JSONL, and a subprocess per scan
    buys nothing. Malformed lines are skipped, never fatal — one bad byte in a store must
    not take a scan (or the hook that calls it) down.

    Effectively-superseded records are NOT resolved here. That resolution lives in
    index.py, and duplicating it would be a second copy of the tombstone grammar; a
    record whose own `status` field says superseded or refuted is dropped, which is the
    part that is a fact about the line itself.
    """
    p = root.joinpath(*FINDINGS_STORE)
    text = _read(p)
    if text is None:
        return []
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line[0] != "{":
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict) or rec.get("kind") not in LESSON_KINDS:
            continue
        if rec.get("status") in ("superseded", "refuted"):
            continue
        stmt = str(rec.get("statement") or "").strip()
        if not stmt:
            continue
        out.append({"id": str(rec.get("id") or "?"), "kind": rec["kind"],
                    "ts": str(rec.get("ts") or ""), "statement": stmt,
                    "line": i, "tag": str(rec.get("tag") or "")})
    return out


def rule_candidates(lessons, ripe_at=None):
    """A lesson the estate wrote down ripe_at times is a RULE nobody encoded.

    Grouping is by NORMALIZED TEXT, using the same normalization repeated work gets:
    mask the volatile literals, stem, drop the stopwords, then key on the resulting token
    SET. Two records that say the same thing in different words — and in different
    sessions, months apart, which is how this actually happens — land in one group; a
    record that merely shares a word does not, because the key is the whole set.

    ⛔ THE FLOOR IS DELIBERATE. A statement with fewer than RULE_MIN_TOKENS content
    tokens is skipped rather than grouped: "it did not work" normalizes to almost
    nothing and would collect every terse record in the store into one triumphant
    candidate that means nothing. A rule has to have said something to recur.
    """
    ripe_at = RIPE_AT if ripe_at is None else ripe_at
    groups = defaultdict(list)
    for L in lessons:
        toks = [t for t in tokens(L["statement"]) if not t.startswith("<")]
        if len(set(toks)) < RULE_MIN_TOKENS:
            continue
        groups[tuple(sorted(set(toks)))].append(L)
    out = []
    for key, members in groups.items():
        n = len(members)
        if n < ripe_at:
            continue
        members = sorted(members, key=lambda L: (L["ts"], L["line"]))
        ranked = sorted(key, key=lambda t: (-len(t), t))
        out.append({
            "slug": ("rule-" + "-".join(ranked[:3]))[:48].strip("-") or "rule-candidate",
            "alias": "", "occurrences": n, "shape": 1.0,
            # A rule is ripe at the same bar as any other candidate; the group already
            # cleared it, so this is a statement of the rule rather than a second test.
            "ripe": n >= ripe_at, "status": "NEW", "kind": "rule",
            "core": sorted(key)[:8], "signature": sorted(key)[:14],
            "sources": {"findings": n},
            # The record ids are the whole point: the ruling reads them, and the compiled
            # form (a hook arm, an eval check) has to cite what it was built from.
            "records": [L["id"] for L in members],
            "evidence": [{"ref": "%s:%s" % ("/".join(FINDINGS_STORE), L["id"]),
                          "ts": L["ts"], "text": ("[%s] %s" % (L["kind"], L["statement"]))[:180]}
                         for L in members],
        })
    out.sort(key=lambda c: (-c["occurrences"], c["slug"]))
    return out


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


def _wsum(sig, w):
    return sum(w.get(t, 1) for t in sig)


# F5: 96% of a 45 s estate scan was spent inside wjaccard (cProfile, 2026-09-01: 86.3 s
# of 89.7 s cumulative, 437 M generator calls under `sum`). TWO recomputations, both
# avoidable, neither changing a single output byte:
#   1. |a ∪ b| was summed from scratch on every call. Weights are INTEGER document
#      frequencies, so sum(a|b) == sum(a) + sum(b) - sum(a&b) EXACTLY — no float drift
#      to reason about — and each signature's own total is computed once.
#   2. agglomerate clears its cluster-pair cache after every merge (it must: the
#      clusters changed). The ITEM-pair scores it is built from never change, so they
#      were being recomputed from zero on every one of the merge passes. Memoized here.
# ⛔ THE ALGORITHM IS UNTOUCHED. Average-link, the same merge order, the same threshold
# test. This is the same arithmetic performed once instead of many times — proven by
# byte-comparing candidates.json/md before and after on this estate.
def agglomerate(sigs, w, thr, progress=None):
    """Average-link agglomerative merge. Average-link (not single-link) on
    purpose: single-link chains two unrelated rituals together through one
    shared word, and a chained cluster is a lie about what repeated."""
    clusters = [[i] for i in range(len(sigs))]
    cache = {}
    totals = [_wsum(sg, w) for sg in sigs]
    pw = {}

    def pair(i, j):
        key = (i, j) if i < j else (j, i)
        v = pw.get(key)
        if v is None:
            a_, b_ = sigs[key[0]], sigs[key[1]]
            if not a_ or not b_:
                v = 0.0
            else:
                inter = sum(w.get(t, 1) for t in (a_ & b_))
                if not inter:
                    v = 0.0
                else:
                    union = totals[key[0]] + totals[key[1]] - inter
                    v = inter / union if union else 0.0
            pw[key] = v
        return v

    def link(ca, cb):
        key = (id(ca), id(cb))
        if key in cache:
            return cache[key]
        tot = 0.0
        for i in ca:
            for j in cb:
                tot += pair(i, j)
        v = tot / (len(ca) * len(cb))
        cache[key] = v
        return v

    merges = 0
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
        merges += 1
        if progress:
            progress(len(clusters), merges)
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
                         "ts": (m.group("ts") or "") if m else "",
                         "sig": [s for s in raw.get("sig", "").split(",") if s],
                         "evidence": raw.get("evidence", ""),
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
        "**`job`** is JOB-LIKENESS: the share of a candidate's cited rows carrying a",
        "runnable token — a flag, an exit code, a command, a path. A row recording what a",
        "machine DID names something a machine can do; a row narrating a decision does not.",
        f"A candidate scoring 0.00 is `narration, not a job` and is never drafted; `draft`",
        "takes the highest scores first, and the rest wait for the next pass.",
        "",
        "**`weak-source`** marks a candidate whose evidence is >"
        f"{int(WEAK_SPEND_SHARE * 100)}% spend-ledger purposes",
        "with no COORD line behind it. Spend purposes say what a lane was CALLED; COORD",
        "lines say what was ASKED and what LANDED. Such candidates are demoted below every",
        "other candidate — read them as shared vocabulary until the ledger says otherwise.",
        "",
        "**kind `rule`** is a lesson, not a workflow: a `learning` or `open` record in",
        f"`{'/'.join(FINDINGS_STORE)}` whose statement recurred {RIPE_AT}+ times. Its compiled form is a",
        "hook arm or an eval check, never a paragraph — and its `records:` line names the",
        "record ids it was built from, which is what a ruling has to read first.",
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
          "| # | candidate | occ | same-shape | job | ripe | status | kind | sources |",
          "|---|---|---|---|---|---|---|---|---|"]
    if not data["candidates"]:
        b.append("| — | *(nothing repeated twice yet — a thin estate gets an empty table, "
                 "not an invented one)* | | | | | | |")
    for c in data["candidates"]:
        name = (c["slug"] + (f" ({c['alias']})" if c.get("alias") else "")
                + (" **weak-source**" if c.get("weak_source") else ""))
        srcs = " ".join(f"{k}={v}" for k, v in c["sources"].items())
        b.append(f"| {c['rank']} | {name} | {c['occurrences']} | {c['shape']:.2f} | "
                 f"{c.get('score', 0.0):.2f} | "
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
        if c.get("records"):
            b.append(f"records: `{', '.join(c['records'])}`"
                     " — the lessons this rule was built from; read them before ruling")
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

    # F5: the scan is an O(n^2)-per-merge-pass clustering over the whole estate and takes
    # TENS OF SECONDS. A tool that prints nothing for that long is indistinguishable from
    # a hung one — the 4.6.1 audit lane killed it at 120 s and filed it as a hang. So it
    # says what it is doing, on stderr (stdout stays the machine surface), per estate
    # family and then no less often than every ~10 s inside the merge.
    def say(msg):
        sys.stderr.write("compile scan: %s\n" % msg)
        sys.stderr.flush()

    say("%d entries across %d ledger families — clustering (seconds; the cost is the "
        "per-family merge, which reports below)"
        % (sum(len(v) for v in families.values()), len(families)))

    cands = []
    for fam, items in families.items():
        if len(items) > MAX_ITEMS:
            notes.append(f"{fam}: {len(items)} entries, newest {MAX_ITEMS} scanned")
            items = items[-MAX_ITEMS:]
        if len(items) < LIST_AT:
            say("%s: %d entries — under the %d-entry floor, not clustered"
                % (fam, len(items), LIST_AT))
            continue
        df = procedure_vocab(items, a.min_df, BOILER)
        for it in items:
            it.sig = frozenset(t for t in it.toks if t in df)
        say("%s: clustering %d entries over a %d-token vocabulary…" % (fam, len(items), len(df)))
        t0 = [time.time()]

        def tick(remaining, merges, _fam=fam, _t0=t0):
            now = time.time()
            if now - _t0[0] >= 10.0:
                _t0[0] = now
                say("%s: still merging — %d clusters left, %d merges so far"
                    % (_fam, remaining, merges))

        started = time.time()
        cands += build_candidates(items, df,
                                  agglomerate([i.sig for i in items], df, a.sim, tick))
        say("%s: done in %.1fs" % (fam, time.time() - started))
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

    # Docket F: lessons are candidates too. Added AFTER `fuse` on purpose — fusion merges
    # candidates whose CORES describe the same job, and a rule is not a job; folding a
    # recurring lesson into a release ritual because they share vocabulary would destroy
    # the one thing that makes the rule readable, which is the record ids behind it.
    lessons = read_lessons(root)
    rules = rule_candidates(lessons)
    cands += rules
    sources.append({"name": "/".join(FINDINGS_STORE),
                    "present": root.joinpath(*FINDINGS_STORE).is_file(),
                    "items": len(lessons)})
    if rules:
        say("findings store: %d lesson record(s) → %d rule candidate(s)"
            % (len(lessons), len(rules)))

    for c in cands:
        c["score"] = job_score([e.get("text", "") for e in c.get("evidence") or []])
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


def candidate_sig(out, slug):
    """(sig, known) — the scanned candidate's core, for rename-proof carry-over."""
    raw = _read(out / CANDIDATES_JSON)
    if raw:
        try:
            for c in json.loads(raw).get("candidates", []):
                if c["slug"] == slug:
                    return ",".join(c["core"]), True
        except Exception:
            pass
    return "", False


def record_decision(out, slug, status, alias="", note="", evidence=None, sig=""):
    """Append one ruling to decisions.md and return the line. ONE writer, so `decide`,
    `draft` and `auto-run` cannot drift into three grammars for the same file."""
    out.mkdir(parents=True, exist_ok=True)
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
    note = re.sub(r"\s+", " ", note or "").strip().replace('"', "'")
    ev = " · ".join("%s=%s" % (k, v) for k, v in (evidence or {}).items())
    line = (f'- [{ts}] slug={slug} status={status}'
            + (f' alias={alias}' if alias else "")
            + (f' sig={sig}' if sig else "")
            + (f' evidence="{ev}"' if ev else "")
            + f' note="{note}"\n')
    with open(p, "a", encoding="utf-8") as f:
        f.write(line)
    return line


# ⛔ AN ADOPTED RUNTIME ENTERS THE REPO DELIBERATELY. Seat ruling, 2026-09-05: DRAFTED
# scaffolds stay OUT of git (`.gitignore` carries `/compile/*/` with an allow-list), because
# an unattended daemon that drafts 36 directories overnight must not also decide what the
# repository contains. So adoption prints the exact command that admits one — `-f` because
# the ignore rule is what it is overriding, and typed by a person because that is the point.
def git_add_line(slug):
    return "git add -f compile/%s" % slugify(slug)


# The three receipts an adoption stands on. Named as data so the refusal message, the
# gate and `auto-run`'s own adopt step cannot disagree about what "green" meant.
ADOPT_RECEIPTS = ("fixture", "benchmark", "refuter")


def parse_evidence(pairs):
    """`--evidence fixture=REF` → {"fixture": "REF"}. Refuses anything else, loudly:
    a receipt whose kind nobody can read is not a receipt."""
    out = {}
    for raw in pairs or []:
        k, _sep, v = str(raw).partition("=")
        k, v = k.strip().lower(), v.strip()
        if not _sep or not k or not v:
            sys.stderr.write("[compile] --evidence must be KIND=REF (one of %s), got %r\n"
                             % ("|".join(ADOPT_RECEIPTS), raw))
            return None
        if k not in ADOPT_RECEIPTS:
            sys.stderr.write("[compile] --evidence kind %r is not one of %s\n"
                             % (k, "|".join(ADOPT_RECEIPTS)))
            return None
        out[k] = v.replace('"', "'")
    return out


def cmd_decide(a):
    out = outdir(a)
    out.mkdir(parents=True, exist_ok=True)
    status = a.status.upper()
    if status not in STATUSES:
        sys.exit(f"status must be one of {'|'.join(STATUSES)}")
    ev = parse_evidence(getattr(a, "evidence", None))
    if ev is None:
        return 2
    # ⛔ ADOPTED IS THE ONE STATUS THAT CHANGES WHAT THE ESTATE RUNS. Every other ruling
    # is bookkeeping; this one says "start using it". So it is the one status that cannot
    # be written on somebody's say-so: without a fixture receipt, a benchmark receipt and
    # a refuter receipt there is nothing to re-read, and "we checked" is not a check.
    if status == "ADOPTED":
        missing = [k for k in ADOPT_RECEIPTS if not ev.get(k)]
        if missing:
            sys.stderr.write(
                "[compile] REFUSED — ADOPTED needs a receipt for each of %s; missing: %s\n"
                % (", ".join(ADOPT_RECEIPTS), ", ".join(missing)))
            sys.stderr.write(
                "[compile] adoption is the ruling that makes the estate USE the runtime. "
                "An adoption that cannot show its fixture run, its FAIR benchmark and its "
                "refuter round is a claim about all three, and Step 7's quality law "
                "outranks any of them. Nothing was written.\n")
            sys.stderr.write("[compile] e.g. decide --slug %s --status ADOPTED %s\n"
                             % (a.slug, " ".join("--evidence %s=<ref>" % k
                                                 for k in ADOPT_RECEIPTS)))
            return 2
    sig, known = candidate_sig(out, a.slug)
    line = record_decision(out, a.slug, status, a.alias, a.note, ev, sig)
    print("recorded:", line.strip())
    if status == "ADOPTED":
        # The ledger-ready receipt: the seat pastes this into COORD verbatim, so the
        # adoption and its three receipts land in the append-only record together.
        print("COORD line: - [%s] [compile] adopt %s -> ADOPTED | evidence: %s"
              % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"), a.slug,
                 " · ".join("%s=%s" % (k, ev[k]) for k in ADOPT_RECEIPTS)))
        print("git: the scaffold is gitignored while DRAFTED. Admit this one deliberately:")
        print("    %s" % git_add_line(a.slug))
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
#
# ── WHERE IT LIVES, AND WHY IT MOVED (v4.5, docket item 8c) ───────────────────
# It used to live at `compile/.auto-build`, INSIDE the estate. The refuter's finding
# (2026-09-01, graded PLAUSIBLE) is that this puts the owner's standing authorization
# inside the one place every lane can write: a lane could grant itself the authority to
# be dispatched, and a clone carried a stranger's opt-in into a fresh tree. A .gitignore
# entry does not touch either problem — it hides the file from git, not from a writer.
#
# Authorization is therefore OWNER-PRIVATE MACHINE STATE now:
#
#     ${NOTREST_HOME:-~/.notrest}/auto-build/<sha256 of the estate realpath>.json
#
# outside every repo, so nothing in a tree can forge it and no clone can carry it. The
# filename is the hash of the estate's REALPATH — one marker per estate, no directory
# tree mirroring anyone's paths under $HOME — and the marker names its estate inside,
# so a copied ~/.notrest cannot silently authorize a different tree. NOTREST_HOME is an
# override for fixtures; the default is the only shipped path.
#
# The legacy in-repo marker is IGNORED, not migrated: honoring it would preserve the
# exact hole the move exists to close. `auto` says so, once, when it finds one.
AUTO_MARK = ".auto-build"          # legacy, in-repo — read by nobody, reported by `auto`

# ── THE UNATTENDED RAILS, AS SHIPPED DEFAULTS ────────────────────────────────
# Director-set 2026-09-05 after the owner's "fully unattended" ruling. Spending tokens
# with nobody watching is only defensible if every way it can run away is bounded FIRST,
# and a bound nobody wrote down is a bound nobody can check. These four are the bounds;
# the owner changes any of them on the marker, and `auto` prints all four back.
#
#   daily_cap_tokens — the whole day's `lane=daemon` receipts. Checked from the LEDGER,
#                      not from a counter this process keeps, so a crash cannot reset it.
#   run_cap_tokens   — one auto-run invocation. Stops the pipeline mid-way rather than
#                      letting a single candidate eat the day.
#   max_turns        — passed to the headless runner. A turn limit is the only bound that
#                      applies INSIDE a step, where neither cap can reach: the caps notice
#                      a step was expensive after it finished, this stops it running on.
#                      60 is ~2x the longest hand-run compile lane this estate has
#                      recorded and well under a runaway loop; it is a ceiling, not a
#                      budget, and a build that needs more than 60 turns is a build the
#                      owner should be watching.
#   STRIKES_MAX      — two failures of the SAME slug's build or refute step park it.
#                      An unattended loop that retries forever is a bill with a heartbeat.
DEFAULT_DAILY_CAP = 1_500_000
DEFAULT_RUN_CAP = 400_000
DEFAULT_MAX_TURNS = 60
STRIKES_MAX = 2


def notrest_home():
    """The owner-private machine state root. Never inside an estate."""
    base = os.environ.get("NOTREST_HOME") or os.path.join(
        os.path.expanduser("~"), ".notrest")
    return pathlib.Path(base)


def auto_home():
    """The owner-private authorization store. Never inside an estate."""
    return notrest_home() / "auto-build"


# ── the credential the daemon runs on ────────────────────────────────────────
#
# ⛔ WHY A FILE AND NOT AN EXPORT. `claude setup-token` prints a long-lived token but does
# NOT log the CLI in (live, 2026-09-05: `auth status` still said loggedIn false afterwards
# and headless probes kept failing). And the pulse daemon is spawned by hooks INSIDE the
# app, so a token the owner exports in a shell never reaches it — there is no shell in the
# chain. The only place both sides can meet is a file on the owner's own disk.
#
# It sits beside the authorization marker, under the same owner-private root, for the same
# reason: nothing inside an estate can write it and no clone can carry it.
#
#     ${NOTREST_HOME:-~/.notrest}/credentials/claude-oauth-token
#
# Mode 0600, in a directory with no group or other bits, both owned by the running user. A
# credential a second account can read is a credential that account has. The check is a
# REFUSAL, not a warning: silently using a world-readable token would teach the owner that
# the mode does not matter.
#
# ⛔ AND THE VALUE NEVER LEAVES THIS FUNCTION EXCEPT INTO THE CHILD'S ENVIRONMENT. It is
# never printed, logged, receipted, put in a status line, or included in an error. Every
# surface says only WHICH SOURCE was used: `credential: env` · `credential: file` ·
# `credential: none`. A secret that appears in a pulse log is a secret in a file the owner
# thought was diagnostics.
# The one command every "you need a credential" message names. Built from this script's
# own path so the message is copy-pasteable wherever the plugin is installed.
SELF = os.path.abspath(__file__)
CRED_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
CRED_REL = ("credentials", "claude-oauth-token")


def cred_file():
    return notrest_home().joinpath(*CRED_REL)


def read_credential():
    """(token, source, problem). `token` is None unless source == "file".

    source: "env"  — already in this process's environment; the file is never read
            "file" — read from the owner-private credential file
            "cli"  — neither is set, so the CLI uses its own login; we try the run
            "none" — a file exists but cannot be used; `problem` says why
    problem: "" or a reason naming WHAT IS WRONG WITH THE FILE — its mode, its owner, its
    directory or its emptiness. Never any part of its contents.
    """
    if os.environ.get(CRED_ENV, "").strip():
        return None, "env", ""
    p = cred_file()
    if not p.exists():
        # ⛔ NOT A BLOCK. Owner ruling 2026-09-05: the credential step is OPTIONAL. A user
        # whose terminal is already logged in must never meet it — so with no env var and
        # no file we call the runner anyway and let the CLI use its OWN login. Only an
        # auth-shaped failure coming BACK from that call is a block, and only then do we
        # tell anyone about `credential --setup`. Absence of a file is not evidence of
        # absence of a login.
        return None, "cli", ""
    try:
        st, dst = p.stat(), p.parent.stat()
    except OSError as exc:
        return None, "none", "%s cannot be stat'd (%s)" % (p, exc.__class__.__name__)
    uid = os.getuid()
    if st.st_uid != uid:
        return None, "none", ("%s is owned by uid %d, not by the user running the daemon "
                              "(uid %d)" % (p, st.st_uid, uid))
    if dst.st_uid != uid:
        return None, "none", ("%s is owned by uid %d, not by the user running the daemon "
                              "(uid %d)" % (p.parent, dst.st_uid, uid))
    if st.st_mode & 0o077:
        return None, "none", ("%s is mode %04o — a credential readable by group or other is "
                              "a credential they have. Fix it: chmod 600 %s"
                              % (p, st.st_mode & 0o777, p))
    if dst.st_mode & 0o077:
        return None, "none", ("%s is mode %04o — the directory must be owner-only, or the "
                              "file's own mode can be worked around. Fix it: chmod 700 %s"
                              % (p.parent, dst.st_mode & 0o777, p.parent))
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "none", "%s cannot be read (%s)" % (p, exc.__class__.__name__)
    token = squeeze(raw)
    if not token:
        return None, "none", "%s is empty — a blank credential is not a credential" % p
    return token, "file", ""


# ⛔ ALL WHITESPACE, NOT JUST THE TRAILING NEWLINE. Live owner failure, 2026-09-05: the
# terminal WRAPPED the printed token, the clipboard carried the wrap as a real line break,
# and the CLI rejected it — "a line break at character 80 (110 characters on 2 lines)".
# A credential is one opaque string; every space, tab, CR and newline inside it came from a
# terminal, an editor or a clipboard, never from the issuer. So they all go, and a token
# split across two lines is reassembled instead of being half-used.
def squeeze(raw):
    """A credential with every whitespace character removed. Never logs, never returns
    anything derived from the value except the value itself."""
    return re.sub(r"\s+", "", raw or "")


def auto_marker(root):
    """The one marker path for this estate: <store>/<sha256 of realpath>.json."""
    real = os.path.realpath(str(pathlib.Path(root).expanduser()))
    return auto_home() / (hashlib.sha256(real.encode("utf-8")).hexdigest() + ".json")


def auto_store_fault(root):
    """Why this estate's authorization store cannot be trusted — else "".

    RB-4 (refuter, 2026-09-01). NOTREST_HOME exists so fixtures never write the real
    home, and nothing stopped it being pointed back INSIDE the estate. A store under the
    tree reinstates the exact hole 8c closed: writable by any lane, carried by a clone.
    The override stays (a fixture that writes $HOME is worse), but a store that lands
    inside the estate is refused by BOTH readers rather than quietly honored.
    """
    try:
        r = os.path.realpath(str(pathlib.Path(root).expanduser()))
        base = os.path.realpath(str(auto_home()))
    except Exception:
        return ""
    if base == r or base.startswith(r + os.sep):
        return ("the authorization store %s is inside the estate %s — an in-estate store "
                "is writable by any lane and travels with a clone, which is the hole the "
                "owner-private marker exists to close" % (base, r))
    return ""


def auto_marker_escapes(p):
    """True when the marker resolves OUTSIDE its own store — a planted symlink.

    RB-5: session-start already applied this law and `auto` did not, so `auto` printed
    ON for a marker the hook refused. Two readers of one file disagreeing about it is
    worse than either answer alone.
    """
    try:
        rp = os.path.realpath(str(p))
        rb = os.path.realpath(str(auto_home()))
        return not (rp == rb or rp.startswith(rb + os.sep))
    except Exception:
        return True


def _auto_opted(p, root=None):
    """True only for a well-formed opt-in that names THIS estate, read from a store the
    marker does not escape.

    A corrupt marker is not an opt-in. Neither is one whose `estate` field names some
    other tree (a copied store, a restored backup): the filename alone is a hash anyone
    could recompute, so the marker has to say what it authorizes. Nor is one that is a
    symlink out of the store — RB-5, the containment session-start already applied.
    """
    if auto_marker_escapes(p):
        return False
    raw = _read(p)
    if not raw:
        return False
    try:
        d = json.loads(raw)
    except Exception:
        return False
    if not (isinstance(d, dict) and d.get("opted") is True):
        return False
    if root is not None and isinstance(d.get("estate"), str) and d["estate"]:
        if os.path.realpath(d["estate"]) != os.path.realpath(str(root)):
            return False
    return True


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


def auto_config(root):
    """The marker as a config dict, or None when this estate is not opted in.

    ONE reader for `auto`'s status print and `auto-run`'s authorization gate — two
    readers of one file disagreeing about it is the RB-5 defect, and it would be worse
    here, where the disagreement decides whether tokens get spent.
    """
    p = auto_marker(root)
    if auto_store_fault(root) or not _auto_opted(p, root):
        return None
    try:
        d = json.loads(_read(p) or "")
    except Exception:
        return None
    def _int(key, default):
        v = d.get(key)
        return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else default
    return {"stamp": d.get("stamp", "?"),
            "unattended": d.get("unattended") is True,
            "daily_cap_tokens": _int("daily_cap_tokens", DEFAULT_DAILY_CAP),
            "run_cap_tokens": _int("run_cap_tokens", DEFAULT_RUN_CAP),
            "max_turns": _int("max_turns", DEFAULT_MAX_TURNS),
            "stop_cooldown_hours": _int("stop_cooldown_hours", DEFAULT_STOP_COOLDOWN_H),
            "path": p}


def print_rails(cfg):
    """All four rails, every time — a bound the owner cannot see is a bound they cannot
    change, and an unattended budget nobody has read is not a budget."""
    print("auto-build: unattended: %s" % ("YES — the daemon may spend tokens on this "
                                          "estate" if cfg["unattended"] else
                                          "no (dispatch-only: a session builds, the "
                                          "daemon never spends)"))
    if not cfg["unattended"]:
        # The numbers below are real defaults, but they bound nothing yet. Printing them
        # without saying so would read as "these caps are protecting you".
        print("auto-build:   (the four rails below are the DEFAULTS that would apply; "
              "with unattended off they bound nothing, because nothing runs)")
    print("auto-build:   daily cap  : %s tokens/day (sum of today's lane=daemon receipts "
          "in spend/ledger.md)" % f"{cfg['daily_cap_tokens']:,}")
    print("auto-build:   run cap    : %s tokens per auto-run invocation"
          % f"{cfg['run_cap_tokens']:,}")
    print("auto-build:   max turns  : %d per headless runner call" % cfg["max_turns"])
    print("auto-build:   stop cooldown: %gh before a slug that quietly stopped is "
          "retried; %d consecutive stops count as one strike"
          % (cfg["stop_cooldown_hours"], STOPS_PER_STRIKE))
    print("auto-build:   two strikes: a slug whose build or refute fails %d times is "
          "PARKED and never retried unattended (re-arm with `decide --status DRAFTED`)"
          % STRIKES_MAX)
    print("auto-build:   one at a time: an estate-wide lock — never two runs, never "
          "alongside a live session's own compile")
    if cfg["unattended"]:
        _tok, src, problem = read_credential()
        if problem:
            print("auto-build:   credential: UNUSABLE — %s" % problem)
            print("auto-build:                 fix it with ONE command: python3 %s "
                  "credential --setup" % SELF)
        elif src == "cli":
            # OPTIONAL, and said so. A terminal that is already logged in needs nothing
            # here, and telling that owner to go and configure a credential would be
            # inventing a chore. The command is named for the case where it IS needed.
            print("auto-build:   credential: none stored — unattended runs will use the "
                  "CLI's OWN login, which is fine if this machine is logged in.")
            print("auto-build:                 If it is not, runs stop with BLOCKED auth "
                  "and ONE command fixes it:")
            print("auto-build:                 python3 %s credential --setup" % SELF)
            print("auto-build:                 (it writes %s, mode 0600 in an owner-only "
                  "directory)" % cred_file())
        else:
            print("auto-build:   credential: %s (present; its value is never printed, "
                  "logged or receipted)" % src)


def cmd_auto(a):
    if not a.on and (a.unattended or a.daily_cap is not None or a.run_cap is not None
                     or a.max_turns is not None or a.stop_cooldown is not None):
        sys.stderr.write("auto-build: --unattended and the cap flags WRITE the marker, so "
                         "they need --on. Bare `auto` reports; `auto --off` revokes.\n")
        return 2
    root = outdir(a).parent
    real = _estate_root_mismatch(str(root))
    if real:
        sys.stderr.write("auto-build: %s is not the estate root the hooks resolve — the "
                         "marker there would be read by nobody. Use --root %s\n"
                         % (root, real))
        return 2
    fault = auto_store_fault(root)
    if fault:
        sys.stderr.write("auto-build: refused — %s\n" % fault)
        sys.stderr.write("auto-build: set NOTREST_HOME to a path outside the estate, or "
                         "unset it to use ~/.notrest\n")
        return 2
    p = auto_marker(root)
    legacy = outdir(a) / AUTO_MARK
    # ⛔ DOCKET B1 — AN AUTHORIZATION THAT LAPSES IN SILENCE. The v4.5 move to the
    # owner-private store did not MIGRATE the in-repo marker, so this estate's own opt-in
    # went quietly back to nudging for weeks and nobody was told. The legacy file is still
    # ignored — honoring it would reinstate the exact hole the move closed — but it is now
    # a WARN rather than a shrug, and only when it matters: with a valid new marker there
    # is nothing to warn about, just a stale file to delete.
    if legacy.exists() and not _auto_opted(p, root):
        print("auto-build: WARN — a LEGACY in-repo marker exists and this estate is NOT "
              "authorized. %s is IGNORED since v4.5 (an in-estate marker is writable by "
              "any lane and travels with a clone), so an estate that opted in before the "
              "move has been silently un-authorized ever since." % legacy)
        print("auto-build: WARN — migrate it: compile.py auto --on --root %s   "
              "(authorization now lives at %s; then delete %s)" % (a.root, p, legacy))
    elif legacy.exists():
        print("auto-build: NOTE — %s is IGNORED since v4.5 and this estate is already "
              "authorized at %s; delete the old file at your convenience." % (legacy, p))
    if a.off:
        was = p.exists()
        try:
            p.unlink()
        except OSError:
            pass
        print("auto-build: OFF" + ("" if was else " (was already off)") + f" — {p}")
        return 0
    if a.on:
        for flag, val in (("--daily-cap", a.daily_cap), ("--run-cap", a.run_cap),
                          ("--max-turns", a.max_turns),
                          ("--stop-cooldown", a.stop_cooldown)):
            if val is not None and not a.unattended:
                sys.stderr.write("auto-build: %s is an UNATTENDED rail — it bounds what "
                                 "the daemon may spend, and without --unattended the "
                                 "daemon spends nothing, so the number would be a "
                                 "setting nobody reads. Pass --unattended too.\n" % flag)
                return 2
            if val is not None and val <= 0:
                sys.stderr.write("auto-build: %s must be a positive number, got %r — a "
                                 "zero or negative bound is not a budget\n" % (flag, val))
                return 2
        p.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
        mark = {"opted": True, "stamp": stamp, "estate": os.path.realpath(str(root))}
        if a.unattended:
            # The opt-in and its budget live in ONE file on purpose: revoking the
            # authorization revokes the budget, and a cap cannot outlive the permission
            # it was written for.
            mark["unattended"] = True
            mark["daily_cap_tokens"] = a.daily_cap or DEFAULT_DAILY_CAP
            mark["run_cap_tokens"] = a.run_cap or DEFAULT_RUN_CAP
            mark["max_turns"] = a.max_turns or DEFAULT_MAX_TURNS
            mark["stop_cooldown_hours"] = a.stop_cooldown or DEFAULT_STOP_COOLDOWN_H
        # tmp + replace: a half-written marker must never be readable as an opt-in.
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(mark) + "\n", encoding="utf-8")
        tmp.replace(p)
        try:
            os.chmod(p, 0o600)          # owner-private, and legibly so
        except OSError:
            pass
        print(f"auto-build: ON ({stamp}) — {p}")
        cfg = auto_config(root)
        if cfg:
            print_rails(cfg)
        if a.unattended:
            print("[compile] UNATTENDED: the pulse daemon may run `auto-run` and SPEND "
                  "tokens on this estate under the caps above. It still never installs "
                  "anything — shipping a compiled runtime stays the owner's act.")
        else:
            print("[compile] this authorizes DISPATCH only: a compiled runtime still never "
                  "auto-installs. Shipping stays the owner's act.")
            print("[compile] the daemon spends NOTHING until you add --unattended "
                  "(e.g. auto --on --unattended --daily-cap %d)." % DEFAULT_DAILY_CAP)
        return 0
    cfg = auto_config(root)
    if cfg:
        print("auto-build: ON since %s — %s" % (cfg["stamp"], p))
        print_rails(cfg)
        return 0
    if p.exists() or os.path.islink(str(p)):
        why = ("marker escapes the authorization store — treated as OFF, exactly as the "
               "SessionStart hook treats it" if auto_marker_escapes(p)
               else "marker present but not a valid opt-in for this estate — treated as OFF")
        print("auto-build: OFF (%s) — %s" % (why, p))
    else:
        print("auto-build: OFF"
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
- `benchmark.sh` — the FAIR benchmark as a RUNNABLE harness (Step 6). Exits 4 until
  written; `compile.py auto-run` gates adoption on it exiting 0, so a runtime nobody
  benchmarked cannot be adopted on the strength of a paragraph.
- `BENCHMARK.md` — the fair-benchmark notes and scenario table. Fill it BEFORE quoting
  a number; `benchmark.sh` replays what this file cites.
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

SCAFFOLD_BENCH_SH = '''#!/bin/bash
# benchmark.sh — the FAIR benchmark for `{slug}`, as a RUNNABLE harness. STUB.
#
# Scaffolded {when}. Exits 4 until it is written, which is the point: `auto-run` gates
# adoption on this script exiting 0, so a runtime nobody benchmarked can never be
# adopted by a daemon at 3am on the strength of a paragraph in BENCHMARK.md.
#
# ⛔ THE ASYMMETRY IS THE FAILURE MODE, not the arithmetic. Step 6's whole point is that
# an unfair benchmark is worse than none: it launders a preference into a measurement.
# So this script must replay the HISTORICAL SCENARIOS cited in BENCHMARK.md's table —
# the same responsibilities on both sides, failure cases included, old-side numbers
# carrying their grade — and it must exit NON-ZERO when the compiled side is worse.
# Cheaper and worse is a regression (Step 7), and a regression reports itself.
set -u
SD="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

echo "[{slug}] benchmark: STUB — no scenarios replayed, so there is no number to quote."
echo "[{slug}] fill this in from BENCHMARK.md's scenario table before claiming parity."
exit 4
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


def slugify(raw):
    return re.sub(r"[^a-z0-9._-]+", "-", (raw or "").lower()).strip("-")


def scaffold_runtime(out, slug):
    """Write compile/<slug>/ and return its file names. Caller has already ruled that
    the directory does not exist — this never overwrites, and never checks twice."""
    d = out / slug
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    d.mkdir(parents=True)
    files = {
        "README.md": SCAFFOLD_README.format(slug=slug, when=when),
        "runner.py": SCAFFOLD_RUNNER.format(slug=slug, when=when),
        "fixture.sh": SCAFFOLD_FIXTURE.format(slug=slug),
        "benchmark.sh": SCAFFOLD_BENCH_SH.format(slug=slug, when=when),
        "BENCHMARK.md": SCAFFOLD_BENCH.format(slug=slug, when=when),
    }
    for fn, body in files.items():
        p = d / fn
        p.write_text(body, encoding="utf-8")
        if fn.endswith((".py", ".sh")):
            p.chmod(0o755)
    return d, files


def cmd_scaffold(a):
    out = outdir(a)
    slug = slugify(a.slug)
    if not slug:
        print(f"[compile] {a.slug!r} is not a usable directory name")
        return 2
    d = out / slug
    if d.exists():
        print(f"[compile] {d} already exists — scaffold never overwrites a runtime "
              f"(that is where the work is). Delete it deliberately, or pass a "
              f"different --slug.")
        return 2
    d, files = scaffold_runtime(out, slug)
    print(f"[compile] scaffolded {d}/ — {', '.join(sorted(files))}")
    print(f"[compile] isolated and installed nowhere. Run it: "
          f"python3 {d / 'runner.py'} run --dry-run  (exits 4 until do_run is written)")
    print(f"[compile] next: Step 3 builds it in ONE persistent Opus lane; "
          f"Step 4 has a DIFFERENT lane attack it.")
    return 0


# ── draft: Step 1 + the skeleton, for every ripe candidate, at zero tokens ────
#
# The gap this closes (docket B2): scanning was automatic, the nudge was automatic, and
# then a human had to type `/compile <slug>` before anything existed to work ON. But the
# expensive half of Step 1 is a GREP the script already does, and the skeleton is a
# template. Neither needs a model, so neither should wait for one.
#
# ⛔ IT NEVER TOUCHES AN EXISTING SLUG. compile/<slug>/ is where the WORK is once a lane
# has started building; a "refresh" that rewrote a runner.py would destroy exactly the
# thing this pipeline exists to produce. An existing directory is skipped and SAID, which
# is also what makes re-running this after every pulse scan a no-op rather than a hazard.
MACHINERY_DOMINANT = 0.50
# ⛔ A PER-PASS CAP. The pulse daemon calls `draft --all-ripe` after every scan, and on this
# estate one dense release turned into 38 drafted directories overnight. Ranking decides
# WHICH; this decides HOW MANY, because "the best five each pass" is a queue and "every ripe
# candidate at once" is a flood. The rest keep their NEW status and their place in line.
DEFAULT_DRAFT_MAX = 5

# ── JOB-LIKENESS ─────────────────────────────────────────────────────────────
# The fraction of a candidate's cited rows that carry a RUNNABLE TOKEN: a flag, an exit
# code, a command, or a path. The thesis is that a row recording something a machine did
# names something a machine can do, while a row narrating a decision does not.
#
# ⛔ IT IS SCORED ON THE LEDGER LINE, NEVER ON THE CONTRACT ROW. Measured here first: every
# CONTRACT.md row carries its own citation (`COORD.md:321`) BY CONSTRUCTION, so scoring the
# row scored the scaffolding and returned 1.00 for all 38 drafted slugs on this estate. The
# score reads the cited line's own body, with the citation columns never in view.
RUNNABLE_RE = re.compile(
    r"--[a-z][a-z0-9-]{2,}"                                   # a flag
    r"|\bexits?\s+\d+\b|\bexit[ -]code\b|\brc=\d+\b"          # an exit code
    r"|\b(?:python3?|bash|sh|git|npm|make|pytest|node)\s+\S"   # a command
    # A path is a path: a known extension, OR anything carrying a directory separator.
    # The narrow extension list scored `evidence: inv.pdf` at zero and called an invoice
    # job narration — the artifact a job produces is exactly the evidence it is a job.
    r"|\b[\w./-]+\.(?:py|sh|json|jsonl|ya?ml|html|txt|md|pdf|csv|log|png|xlsx|sql)\b"
    r"|\b[\w.-]+/[\w./-]+\b"                                   # a path
    r"|`[^`]+`"                                               # a literal
    # ⛔ A VERSION AND A COMMIT ARE RUNNABLE REFERENCES TOO, and leaving them out was not a
    # near-miss — it scored the RELEASE RITUAL at 0.00 and declined the canonical example of
    # compilable work as narration. "cut the release for the parser -> v1.2.0 shipped,
    # changelog and manifest bumped | evidence: commit aa11bb2" names a thing a machine can
    # be pointed at (`git show aa11bb2`) and a parameter it was run with. These are the two
    # literals the scanner ALREADY masks as `<ver>` and `<sha>` because they are the
    # signature of a parameterised procedure — so counting them here is the same judgement
    # applied twice, not a threshold nudged until the tests passed.
    r"|\bv?\d+\.\d+(?:\.\d+)*\b"                              # a version
    r"|\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")                     # a commit


def job_score(texts):
    """Fraction of rows carrying a runnable token. 0.0 for an empty row set."""
    rows = [t for t in texts if (t or "").strip()]
    if not rows:
        return 0.0
    return round(sum(1 for t in rows if RUNNABLE_RE.search(t)) / float(len(rows)), 2)


def cited_bodies(root, cand, cache=None):
    """The BODY of each cited ledger line — what was asked and what landed, without the
    citation the contract wraps it in."""
    cache = {} if cache is None else cache
    out = []
    for e in cand.get("evidence") or []:
        ref = str(e.get("ref") or "")
        fn, sep, num = ref.rpartition(":")
        if not sep or not num.isdigit() or not fn:
            continue
        text = cache.get(fn)
        if text is None:
            got = _read(root / fn)
            cache[fn] = got if got is not None else ""
            text = cache[fn]
        lines = text.splitlines()
        n = int(num)
        if n < 1 or n > len(lines):
            continue
        line = lines[n - 1].strip()
        m = COORD_RE.match(line)
        out.append(m.group("body") if m else line)
    return out


def machinery_share(root, cand, cache=None):
    """(machinery rows, total resolvable rows) among a candidate's cited evidence.

    ⛔ DEFENCE IN DEPTH, and it earns its keep. Dropping machinery lines at the reader
    stops NEW candidates being built from them — it does nothing about a candidates.json
    written by an older scan, which `draft --all-ripe` will happily pick up on the next
    pulse. So the last thing standing between the compiler's own paperwork and a drafted
    runtime re-reads the cited lines THEMSELVES and asks what wrote them. A candidate
    mostly made of the harness talking about itself is not a workflow.
    """
    cache = {} if cache is None else cache
    mach = tot = 0
    for e in cand.get("evidence") or []:
        ref = str(e.get("ref") or "")
        fn, _sep, num = ref.rpartition(":")
        if not _sep or not num.isdigit() or not fn:
            continue
        text = cache.get(fn)
        if text is None:
            text = _read(root / fn)
            cache[fn] = text if text is not None else ""
            text = cache[fn]
        lines = text.splitlines()
        n = int(num)
        if n < 1 or n > len(lines):
            continue
        line = lines[n - 1].strip()
        tot += 1
        m = COORD_RE.match(line) or AGENT_RE.match(line)
        if m:
            try:
                if is_machinery_tag(m.group("lane")):
                    mach += 1
            except IndexError:
                pass
            continue
        sm = SPEND_RE.match(line)
        if sm and sm.group("lane") == DAEMON_LANE_SKIP:
            mach += 1
    return mach, tot


def draft_one(root, out, cand, log):
    """Draft one candidate. Returns "drafted" | "skipped:<why>"."""
    slug = slugify(cand.get("slug") or "")
    if not slug:
        return "skipped:%r is not a usable directory name" % cand.get("slug")
    mach, tot = machinery_share(root, cand)
    if tot and (mach / float(tot)) > MACHINERY_DOMINANT:
        return ("machinery:%d of %d cited rows were written by the harness about itself "
                "(tagged %s, or lane=daemon) — that is paperwork repeating, not work"
                % (mach, tot, "/".join("[%s]" % t for t in sorted(MACHINERY_TAGS))))
    d = out / slug
    if d.exists():
        return "skipped:%s already exists — never overwritten" % d

    # The CONTRACT IS BUILT FIRST, into a temp file, and only then does anything land on
    # disk. A candidate whose trail no longer yields rows must leave NOTHING behind — a
    # scaffolded directory with no contract is a slug that can never be drafted again
    # (the existence check above would skip it forever) and that `auto-run` would happily
    # feed to a builder with no contract to build against.
    tmp = out / (".draft-%s.contract.tmp" % slug)
    ns = argparse.Namespace(root=str(root), out=str(out), slug=cand.get("slug"),
                            max_rows=MAX_ROWS, write=str(tmp))
    try:
        rc = cmd_contract(ns)
    except Exception as exc:                        # never let one candidate kill the run
        rc, exc_name = 1, exc.__class__.__name__
        log("draft: %s — contract raised %s" % (slug, exc_name))
    if rc != 0 or not tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
        return ("skipped:contract exited %s — nothing to build against, so nothing was "
                "created" % rc)

    d, files = scaffold_runtime(out, slug)
    tmp.replace(d / "CONTRACT.md")
    return "drafted"


# The citations `draft` wrote into CONTRACT.md, which is where a DRAFTED slug keeps the
# rows it was built from. This is the only place they survive: once the readers started
# dropping machinery lines, the candidates built from them vanished from candidates.json
# altogether — so a slug already on disk cannot be re-judged from the current scan, only
# from its own contract.
CONTRACT_REF_RE = re.compile(r"`([A-Za-z0-9_./-]+\.md):(\d+)`")


def contract_evidence(d):
    """A pseudo-candidate carrying the refs CONTRACT.md cites, for machinery_share."""
    text = _read(d / "CONTRACT.md")
    if text is None:
        return None
    seen, ev = set(), []
    for fn, num in CONTRACT_REF_RE.findall(text):
        ref = "%s:%s" % (fn, num)
        if ref not in seen:
            seen.add(ref)
            ev.append({"ref": ref})
    return {"evidence": ev}


def cmd_recheck(a):
    """RETROACTIVE GUARD. Re-judge every DRAFTED slug already on disk.

    ⛔ WHY THIS IS NOT THE SAME PASS AS `draft`. The machinery filter stops NEW candidates
    being built and stops `draft` scaffolding an old one — neither touches a slug that was
    ALREADY scaffolded before the filter existed. On this estate the pulse daemon drafted
    36 of them, several out of the compiler's own paperwork, and each is a runtime
    `auto-run --next` would happily pick up and spend on. A guard that only protects the
    future leaves the actual exposure exactly where it is.

    The rows are re-read from the CURRENT ledgers, through each slug's own CONTRACT.md,
    because a machinery-built candidate no longer exists in candidates.json to be judged.
    Nothing is deleted: a DECLINED ruling takes the slug out of `auto-run`'s reach, and
    what to do with the directory is the owner's call, not a script's.
    """
    root = pathlib.Path(a.root).expanduser().resolve()
    out = outdir(a)
    if not out.is_dir():
        print("[compile] recheck: no %s — nothing drafted here" % out)
        return 0
    drafted, order = {}, []
    for r in read_decisions(out):
        if r["slug"] not in drafted:
            order.append(r["slug"])
        drafted[r["slug"]] = r["status"]
    slugs = [sl for sl in order if drafted[sl] == "DRAFTED"]
    cache, declined, kept, skipped = {}, [], [], []
    for sl in slugs:
        d = out / slugify(sl)
        cand = contract_evidence(d)
        if cand is None:
            skipped.append((sl, "no CONTRACT.md at %s — nothing to re-read" % d))
            continue
        mach, tot = machinery_share(root, cand, cache)
        if not tot:
            skipped.append((sl, "none of its %d cited row(s) resolve in the ledgers today"
                            % len(cand["evidence"])))
            continue
        score = job_score(cited_bodies(root, cand, cache))
        if score <= 0.0:
            sig, _k = candidate_sig(out, sl)
            record_decision(out, sl, "DECLINED", "",
                            "draft --recheck REFUSED: narration, not a job — job-likeness "
                            "0.00 over %d cited row(s): none carries a runnable token (a "
                            "flag, an exit code, a command, a path). Ruled by the scanner, "
                            "not the owner — re-rule with decide --status DRAFTED if this "
                            "is work somebody did. The directory is left alone." % tot,
                            None, sig)
            declined.append((sl, mach, tot))
            print("DECLINE %-32s narration, not a job (job 0.00)" % sl)
            continue
        if (mach / float(tot)) > MACHINERY_DOMINANT:
            why = ("%d of %d cited rows were written by the harness about itself (tagged "
                   "%s, or lane=daemon) — that is paperwork repeating, not work"
                   % (mach, tot, "/".join("[%s]" % t for t in sorted(MACHINERY_TAGS))))
            sig, _k = candidate_sig(out, sl)
            record_decision(out, sl, "DECLINED", "",
                            "draft --recheck REFUSED: %s. Ruled by the scanner, not the "
                            "owner — re-rule with decide --status DRAFTED if this really "
                            "is work somebody did. The directory is left alone." % why,
                            None, sig)
            declined.append((sl, mach, tot))
            print("DECLINE %-32s %d/%d machinery" % (sl, mach, tot))
        else:
            kept.append((sl, mach, tot))
            print("KEEP    %-32s %d/%d machinery · job %.2f" % (sl, mach, tot, score))
    for sl, why in skipped:
        print("SKIP    %-32s %s" % (sl, why))
    print("[compile] recheck: %d DRAFTED slug(s) · %d declined, %d kept, %d unjudgeable"
          % (len(slugs), len(declined), len(kept), len(skipped)))
    if declined:
        print("[compile] a DECLINED slug is out of auto-run's reach. Its directory is left "
              "on disk untouched — deleting the owner's files is not a script's call.")
    return 0


def cmd_draft(a):
    if getattr(a, "recheck", False):
        return cmd_recheck(a)
    root = pathlib.Path(a.root).expanduser().resolve()
    out = outdir(a)
    if not a.all_ripe and not a.slug:
        sys.stderr.write("[compile] draft needs --all-ripe, --slug S or --recheck\n")
        return 2
    raw = _read(out / CANDIDATES_JSON)
    if raw is None:
        # Hook-safe, exactly like `report`: the pulse daemon calls this after a scan, and
        # an estate that has never been scanned is a state, not a failure.
        print(f"[compile] draft: no scan yet at {out} — nothing to draft "
              f"(run: compile.py scan --root {root})")
        return 0
    try:
        cands = json.loads(raw).get("candidates", [])
    except Exception:
        print(f"[compile] draft: {out / CANDIDATES_JSON} is unreadable — re-run scan")
        return 0

    if a.slug:
        picked = [c for c in cands if a.slug in (c.get("slug"), c.get("alias"))]
        if not picked:
            sys.stderr.write("[compile] draft: no scanned candidate named %r — a slug the "
                             "scan never saw has no cluster and no contract behind it\n"
                             % a.slug)
            return 3
    else:
        # RIPE and NEW: ripe because the estate recorded it 3+ times, NEW because a
        # candidate the owner already ruled on is not waiting for a draft.
        picked = [c for c in cands if c.get("ripe") and c.get("status") == "NEW"
                  and (latest_status(out, c.get("slug")) or "NEW") in ("NEW", "DRAFTED")]
        # Highest job-likeness first, ties broken by how often the estate recorded it.
        picked.sort(key=lambda c: (-float(c.get("score") or 0.0),
                                   -int(c.get("occurrences") or 0), c.get("slug") or ""))

    def log(msg):
        sys.stderr.write("compile draft: %s\n" % msg)
        sys.stderr.flush()

    drafted, skipped, held = [], [], []
    cap = a.max_drafts if a.max_drafts and a.max_drafts > 0 else DEFAULT_DRAFT_MAX
    # ⛔ A MISSING SCORE IS NOT A SCORE OF ZERO. A candidates.json written before the score
    # existed carries no `score` key, and reading that absence as 0.00 would decline every
    # candidate in it as "narration" — condemning real work for a missing field. It is
    # computed from the cited rows instead, exactly as `--recheck` does.
    _sc = {}
    for c in picked:
        if "score" not in c:
            c["score"] = job_score(cited_bodies(root, c, _sc))
    for c in list(picked):
        # (3) NARRATION IS NOT A JOB. A candidate whose cited rows carry no runnable token
        # at all would produce a contract with nothing runnable in it — there is no work in
        # there to compile, only an account of work. Declined by the scanner, re-rulable by
        # the owner, and never drafted.
        if float(c.get("score") or 0.0) <= 0.0:
            sig, _k = candidate_sig(out, c["slug"])
            record_decision(out, c["slug"], "DECLINED", c.get("alias", ""),
                            "draft REFUSED: narration, not a job — job-likeness 0.00: none "
                            "of its cited rows carry a runnable token (a flag, an exit "
                            "code, a command, a path). Ruled by the scanner, not the owner "
                            "— re-rule with decide --status NEW if this is work somebody "
                            "did.", None, sig)
            skipped.append((c.get("slug"), "narration, not a job (job-likeness 0.00)"))
            print("REFUSE  %-32s narration, not a job (job 0.00)" % c["slug"])
            picked.remove(c)
    # ⛔ THE CAP COUNTS WORK, NOT ROLL-CALL. A candidate already scaffolded consumes no
    # slot: it is reported and stepped over. Otherwise the highest-scoring slug — which is
    # already drafted — eats the single slot on every pass and the queue never advances,
    # which is a cap that has quietly become a stop.
    runnable, already = [], []
    for c in picked:
        (already if (out / slugify(c.get("slug") or "")).exists() else runnable).append(c)
    for c in already:
        skipped.append((c.get("slug"), draft_one(root, out, c, log).split(":", 1)[1]))
        print("SKIP    %-32s already drafted — not counted against the cap" % c["slug"])
    picked, held = runnable[:cap], runnable[cap:]
    for c in picked:
        verdict = draft_one(root, out, c, log)
        if verdict == "drafted":
            drafted.append(c)
            sig, _known = candidate_sig(out, c["slug"])
            record_decision(out, c["slug"], "DRAFTED", c.get("alias", ""),
                            "draft --all-ripe: contract + skeleton + benchmark harness "
                            "scaffolded at %s/%s/ (zero model tokens); not built, not "
                            "benchmarked, not adopted"
                            % (a.out, slugify(c["slug"])), None, sig)
            print("DRAFT   %-32s %d× · %s/%s/" % (c["slug"], c["occurrences"], a.out,
                                                  slugify(c["slug"])))
        elif verdict.startswith("machinery:"):
            why = verdict.split(":", 1)[1]
            # DECLINED, not left NEW: a pseudo-candidate left NEW is re-examined and
            # re-noted on every pulse, which turns one defect into a growing file. The
            # note says who ruled and how the owner overrides it.
            sig, _known = candidate_sig(out, c["slug"])
            record_decision(out, c["slug"], "DECLINED", c.get("alias", ""),
                            "draft REFUSED: %s. Ruled by the scanner, not the owner — "
                            "re-rule it with decide --status NEW if this really is work "
                            "somebody did." % why, None, sig)
            skipped.append((c.get("slug"), why))
            print("REFUSE  %-32s %s" % (c["slug"], why))
        else:
            skipped.append((c.get("slug"), verdict.split(":", 1)[1]))
    # Never dropped silently: every candidate this run left alone says why.
    for slug, why in skipped:
        if "already exists" not in (why or ""):
            print("SKIP    %-32s %s" % (slug, why))
    for c in held:
        print("HOLD    %-32s not drafted: below the per-pass cap (job %.2f, %d\u00d7)"
              % (c["slug"], float(c.get("score") or 0.0), c.get("occurrences", 0)))
    print("[compile] draft: %d drafted, %d refused, %d held below the per-pass cap of %d "
          "(highest job-likeness first) · DRAFTED recorded in %s"
          % (len(drafted), len(skipped), len(held), cap, (out / DECISIONS_MD)))
    if drafted:
        print("[compile] a DRAFT is a contract and a skeleton, nothing more: runner.py "
              "exits 4, benchmark.sh exits 4, and no number has been measured. Building "
              "it is `auto-run` (unattended) or the ritual (in-session).")
    return 0


# ── auto-run: the unattended pipeline, and the rails that make it defensible ──
#
# The owner's ruling (2026-09-05): "the daemon should spend tokens too, make it fully
# unattended." That is a real change of kind — every other automatic thing in this skill
# is free, and free automation that goes wrong costs an apology. This one costs money,
# runs at 3am, and nobody is reading the output.
#
# So the whole design is the RAILS, and the pipeline is what runs between them:
#   · ONE ESTATE LOCK      — never two runs, never alongside a live session's compile.
#   · A DAILY CAP          — read from the LEDGER, not from a counter this process keeps,
#                            so a crash, a kill, or a second machine cannot reset it.
#   · A PER-RUN CEILING    — one candidate cannot eat the day.
#   · A TURN LIMIT         — the only bound that reaches INSIDE a step.
#   · TWO STRIKES          — a slug that fails twice is PARKED. An unattended loop that
#                            retries forever is a bill with a heartbeat.
#   · A RECEIPT PER CALL   — same ledger, same routing gate, no exemption for work nobody
#                            watched. Tokens the CLI did not report are logged as UNKNOWN,
#                            never as a plausible number.
#   · A QUIET AUTH STOP    — "Not logged in" ends the run with one line and no retry.
# Each of those is armed in scripts/fixture.sh with a FAKE runner. A rail nobody has seen
# fire is a rail nobody has tested.
AUTORUN_LOCK = ".auto-run.lock"
PULSE_LOG = ("pulse", "auto-run.log")
RED_MARK = "auto-run RED"
# A cap-stop also re-asserts DRAFTED (the status is deliberately unchanged), so it has to be
# excluded from the strike RESET for the same reason a red line is. Otherwise a slug could
# alternate red · capped · red · capped and never reach two strikes — the retry loop the
# rail exists to stop, wearing a budget line as camouflage.
CAP_MARK = "auto-run CAPPED"
# ⛔ A QUIET STOP MUST BACK OFF. Live on this estate, 2026-09-05: the marker was armed, the
# pulse ran the real pipeline, and the builder exited 1 on THREE consecutive pulses (06:12Z,
# 06:18Z x2) — each one logged "strike 0 of 2", because a stop is deliberately not a strike.
# Nothing was spent (the CLI failed before reporting usage) and that was luck, not design: a
# CLI that fails AFTER starting would have been paid for on every pulse, forever. A stop is
# now STAMPED per slug, the slug is not retried until a cooldown has passed, and three
# consecutive stops are worth one strike — so a permanently broken runner parks the slug
# instead of dialling it every few minutes.
STOP_MARK = "auto-run STOPPED"
STOPS_PER_STRIKE = 3
DEFAULT_STOP_COOLDOWN_H = 6
# The runner is exec'd by a pulse daemon that hooks spawned from inside a LIVE Claude
# session, so it inherits that session's own environment. A headless `claude -p` starting up
# inside another Claude's env is at best confusing to debug and at worst refused outright —
# and "runner exited 1" with no stderr is exactly the report that cannot tell you which.
# These are scrubbed before exec so the child starts from a clean shell, whatever the CLI
# does about nesting.
ENV_SCRUB_EXACT = ("CLAUDECODE",)
ENV_SCRUB_PREFIX = ("CLAUDE_CODE_",)
# ⛔ THE SCRUB MUST NOT TAKE THE KEYS WITH IT. A daemon cannot answer /login, so if the
# owner gives it a long-lived credential that credential has to survive — and one of them
# (CLAUDE_CODE_OAUTH_TOKEN) sits squarely inside the prefix being scrubbed. These names are
# passed through by name only: this script never reads a value, never logs one, and never
# puts one in a receipt or a status line.
ENV_KEEP = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")
STDERR_TAIL = 400              # bytes of the runner's stderr kept in the log and the receipt
STEP_TIMEOUT = 3600            # seconds per runner call; a hung CLI is not a budget
USAGE_KEYS = ("input_tokens", "output_tokens",
              "cache_creation_input_tokens", "cache_read_input_tokens")
DAEMON_LANE = "daemon"
DAEMON_RE = re.compile(
    r"^\[(?P<day>\d{4}-\d{2}-\d{2})[^\]]*\]\s+lane=daemon\s+model=(?P<model>\S+)\s+"
    r"tokens=(?P<tokens>\S+)\s+grade=(?P<grade>\S+)")

BUILD_PROMPT = """You are the BUILDER lane for the compiled runtime `{slug}`.

Your working directory IS the runtime: `{d}`. Read `CONTRACT.md` (the Step-1 functional
contract, reconstructed from this estate's own trail) and `README.md` first.

Build the runtime:
  · Fill in `runner.py` — `do_run` and `do_selfcheck`. Deterministic, python3 stdlib
    only unless CONTRACT.md says otherwise. Exit 0 clean · 2 usage · 3 a real finding ·
    4 not implemented. Every retained model call goes behind a typed boundary with a
    validator and bounded retries, never an unbounded "do the task" call.
  · Replace `fixture.sh`'s scaffold cases with REAL ones: one per historical scenario in
    CONTRACT.md, one per validator, one proving the dry-run adapter performs no side
    effect. A test that mocks the thing it tests passes by agreeing with itself.
  · Write `benchmark.sh` so it replays the historical scenarios and EXITS NON-ZERO when
    the compiled side is worse. Cheaper and worse is a failed compile, not a win.
  · Fill in README.md's "What it does" and "What it does NOT do". The second one is
    load-bearing: a runtime silent about its gaps gets read as complete.

⛔ TOUCH-ONLY `{d}`. Nothing outside this directory. Do not install anything, do not
edit the harness, do not spawn sub-agents. You are running UNATTENDED: nobody will see a
question, so a blocker is something you WRITE DOWN in README.md, not something you ask.

Finish by printing a last line of exactly: BUILD: DONE
"""

REFUTE_PROMPT = """You are the REFUTER for the compiled runtime `{slug}` — a DIFFERENT
lane from the one that built it, and your job is to attack it, never to fix it.

Working directory: `{d}`. Read `CONTRACT.md`, then `runner.py`, `fixture.sh` and
`benchmark.sh`. Hunt for these in order:
  1. A fixture that agrees with itself — mocks standing in for the logic under test.
  2. A responsibility in CONTRACT.md the runtime silently does not do (parity claimed
     over a subset is a lie about the subset).
  3. A benchmark that could only produce a favourable number — pre-chewed input on the
     compiled side, failure cases missing from the sample, the old side re-run to lose.
  4. A side effect with no dry-run adapter, or one whose dry-run still performs it.
  5. A claim in README.md that nothing in the tree supports.

Write your findings to `REFUTER.md` with a grade for each (CONFIRMED / PLAUSIBLE /
SPECULATIVE) and the file:line that shows it. Change no other file.

⛔ Your LAST line must be exactly one of:
    REFUTER: CLEAN
    REFUTER: DEFECT <one line saying what>
Absence of a verdict line is read as a DEFECT. That is deliberate: this runs unattended,
and silence must never be able to promote a runtime.
"""


def spend_script():
    """spend.py, from the plugin tree this script lives in (env override for fixtures)."""
    env = os.environ.get("NOTREST_SPEND_PY")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parents[2] / "spend" / "scripts" / "spend.py"


def pulse_line(root, msg):
    """One line, to stdout AND to pulse/auto-run.log.

    The daemon's stdout goes wherever the daemon's stdout goes — which at 3am is often
    nowhere. So every decision this runner makes also lands in a file under pulse/
    (machine-written, derived, disposable) where the next session can read what happened
    while nobody was watching. A rail that fires silently is indistinguishable from a
    rail that never fired.
    """
    line = "[compile auto-run] %s" % msg
    print(line)
    try:
        p = root.joinpath(*PULSE_LOG)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n"
                    % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"), msg))
    except OSError:
        pass                      # a pulse that cannot be written must not stop the rail


COUNTED_AS_RE = re.compile(r"\bcounted-as=(\d+)")


def daemon_spend_today(root, day, unknown_as=DEFAULT_RUN_CAP):
    """(tokens, unknown_receipts) for lane=daemon on `day`, read from the LEDGER.

    ⛔ FROM THE LEDGER, NEVER FROM A COUNTER. A cap this process kept in memory would be
    reset by every crash, every kill and every second invocation — which is to say it
    would bound nothing on exactly the days it mattered. The ledger is append-only and
    survives all three.

    ⛔ AND AN UNCOUNTED RUN IS COUNTED CONSERVATIVELY (refuter D1, 2026-09-05). Summing
    only the numeric receipts meant a runner whose result carried no `usage` cost ZERO
    against the cap — so the daily cap was bypassed entirely by a CLI that simply stopped
    reporting, and the disclosure line said so while gating nothing. A disclosure that
    changes no decision is a comment. An unknown run is therefore charged at the RUN CAP:
    the most it could have cost under this estate's own rails. That over-counts, on
    purpose — the failure this bounds is a bill, and the safe direction to be wrong in is
    "stopped early". The charged figure is written into the receipt as `counted-as=<n>`
    and read back from there, so the arithmetic is reproducible from the ledger alone.
    """
    text = _read(root / "spend" / "ledger.md")
    if text is None:
        return 0, 0
    total, unknown = 0, 0
    for line in text.splitlines():
        m = DAEMON_RE.match(line.strip())
        if not m or m.group("day") != day:
            continue
        tok = m.group("tokens")
        if tok.isdigit():
            total += int(tok)
        else:
            unknown += 1
            cm = COUNTED_AS_RE.search(line)
            total += int(cm.group(1)) if cm else unknown_as
    return total, unknown


def parse_runner_json(stdout_text):
    """(tokens, model, text, is_error) from a headless CLI result.

    ⛔ NOTHING IS INVENTED. A result whose JSON carries no usage yields tokens=None, and
    the receipt says `tokens=unknown` — a plausible-looking number in a spend ledger is
    worse than a gap, because a gap is visibly a gap.
    """
    text = stdout_text or ""
    try:
        obj = json.loads(text)
    except Exception:
        return None, None, text, False
    if isinstance(obj, list):
        obj = next((x for x in reversed(obj)
                    if isinstance(x, dict) and ("usage" in x or "result" in x)), None)
    if not isinstance(obj, dict):
        return None, None, text, False
    tokens, usage = None, obj.get("usage")
    if isinstance(usage, dict):
        got = [usage[k] for k in USAGE_KEYS
               if isinstance(usage.get(k), int) and not isinstance(usage.get(k), bool)]
        if got:
            tokens = sum(got)
    model = obj.get("model")
    if not isinstance(model, str) or not model.strip():
        mu = obj.get("modelUsage")
        model = sorted(mu)[0] if isinstance(mu, dict) and mu else None
    result = obj.get("result")
    # ⛔ `is_error` OUTRANKS THE EXIT CODE. Probed live: the CLI answers an expired OAuth
    # session with {"subtype":"success","is_error":true,...} and can exit 0 doing it. A
    # runner judged on its exit code alone would have read that as a completed build and
    # walked on to the refuter, paying for a second call against the same dead session.
    return (tokens, (model or None), (result if isinstance(result, str) else text),
            obj.get("is_error") is True)


def receipt(root, model, tokens, purpose, counted_as=DEFAULT_RUN_CAP):
    """One `spend.py log` line per headless call. Returns the exit code of that call.

    lane=daemon, model explicit — the same ledger and the same routing gate as any other
    lane, because work nobody watched is exactly the work that should be checkable. When
    the CLI reported no usage the receipt carries the estate's existing grammar for an
    uncounted call (`tokens=unknown grade=estimate`, as agent-ledger.sh and gpt.sh already
    write it) and SAYS in the purpose that the figure is unverifiable.
    """
    cmd = [sys.executable, str(spend_script()), "log", "--root", str(root),
           "--lane", DAEMON_LANE, "--model", model]
    if tokens is None:
        # The number is NOT invented — `tokens=unknown` stays on the line. What is stated
        # is what the CAP charged it, which is a fact about our own accounting, not a
        # claim about the run.
        cmd += ["--grade", "estimate", "--purpose",
                purpose + " · tokens=unknown counted-as=%d — the CLI result carried no "
                          "usage; unverifiable, never invented, and charged against the "
                          "daily cap at the run ceiling" % counted_as]
    else:
        cmd += ["--tokens", str(tokens), "--grade", "observed", "--purpose", purpose]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return r.returncode
    except (OSError, subprocess.SubprocessError):
        return 1


def child_env(token=None):
    """The environment a headless runner starts from.

    NOTREST_UNATTENDED=1 is set here, once, for every child: the hooks read it to suppress
    the AUTO-BUILD echo and to refuse lane spawns from inside an unattended run. One level
    deep, never a tree.

    ⛔ AND THE SESSION'S OWN VARIABLES ARE SCRUBBED. The pulse daemon is spawned by hooks
    from inside a LIVE Claude session, so without this the runner inherits that session's
    CLAUDECODE / CLAUDE_CODE_* and a headless `claude -p` boots up inside another Claude's
    environment. Whether the CLI refuses that outright or merely behaves oddly, the child
    should not be able to see it — and "runner exited 1" with no stderr is precisely the
    report that cannot tell you which of the two happened.

    ENV_KEEP is the exception: a daemon cannot answer /login, so the credentials an owner
    may hand it survive the scrub. By name only — no value is ever read or logged here.
    """
    env = dict(os.environ)
    for k in list(env):
        if k in ENV_KEEP:
            continue
        if k in ENV_SCRUB_EXACT or k.startswith(ENV_SCRUB_PREFIX):
            del env[k]
    env["NOTREST_UNATTENDED"] = "1"
    if token:
        # The ONLY place the value goes. Not a log line, not a receipt, not a status.
        env[CRED_ENV] = token
    return env


def tail_err(*texts):
    """The last STDERR_TAIL bytes of what the child said, on one line.

    A diagnosis nobody can read is not a diagnosis: the live finding on this estate was
    three identical `runner exited 1` lines with nothing else in them, which named the
    symptom and hid every cause.
    """
    blob = " ".join((t or "").strip() for t in texts if (t or "").strip())
    blob = " ".join(blob.split())
    if not blob:
        return "(the runner said nothing on stdout or stderr)"
    return ("…" + blob[-STDERR_TAIL:]) if len(blob) > STDERR_TAIL else blob


def run_runner(cmd, prompt, cwd, timeout, token=None):
    """(rc, stdout, stderr) — a headless model call, from a scrubbed environment carrying
    only the credential the owner put on disk for it."""
    env = child_env(token)
    try:
        r = subprocess.run(cmd, shell=True, input=(prompt or "").encode("utf-8"),
                           cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           env=env, timeout=timeout)
        return (r.returncode, r.stdout.decode("utf-8", "replace"),
                r.stderr.decode("utf-8", "replace"))
    except subprocess.TimeoutExpired:
        return 124, "", "runner exceeded %ss" % timeout
    except OSError as exc:
        return 127, "", "%s: %s" % (exc.__class__.__name__, exc)


def run_script(path, cwd, timeout=900):
    """(rc, output) for a free gate — the fixture and the benchmark. No tokens."""
    env = child_env()
    try:
        r = subprocess.run(["bash", str(path)], cwd=str(cwd), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, env=env, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, "exceeded %ss" % timeout
    except OSError as exc:
        return 127, "%s: %s" % (exc.__class__.__name__, exc)


# ⛔ WHAT AN AUTH FAILURE ACTUALLY LOOKS LIKE, probed at the seat on this estate
# (2026-09-05). Two different strings from two different environments:
#   clean env : "Not logged in · Please run /login"
#   this env  : "Failed to authenticate: OAuth session expired and could not be refreshed"
# The second contains none of the words the first does, so a marker list built from one
# report would have sailed straight past the other. Both are here, and the `is_error`
# check below is what catches the third one nobody has seen yet.
AUTH_MARKERS = ("not logged in", "please run /login", "failed to authenticate",
                "oauth session expired", "invalid api key", "authentication_error",
                "credit balance is too low")


def looks_unauthenticated(*texts):
    blob = " ".join(t or "" for t in texts).lower()
    return any(m in blob for m in AUTH_MARKERS)


# ── the status line: one line, overwritten, for whoever asks next ─────────────
# The daemon's stdout goes nowhere at 3am and the pulse LOG only grows, so "is the
# unattended pipeline stuck?" was a question you answered by reading a file backwards.
# This is the answer as a single line, in a grammar a SessionStart banner can branch on:
#   [ts] BLOCKED auth: <reason>      — it cannot run at all; the owner must act
#   [ts] COOLDOWN <slug> until <ts>  — deliberately waiting after quiet stops
#   [ts] OK <slug> <step>            — it ran; the pipeline is healthy
#   [ts] IDLE nothing drafted        — nothing to do, which is not a fault
# BLOCKED and COOLDOWN are the two a banner should surface: they are the states where
# silence would otherwise be indistinguishable from success.
STATUS_FILE = ("pulse", "auto-run.status")


def write_status(root, line):
    try:
        p = root.joinpath(*STATUS_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text("[%s] %s\n"
                       % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"), line),
                       encoding="utf-8")
        tmp.replace(p)                    # a reader never sees half a status
    except OSError:
        pass                              # a status that cannot be written stops nothing


def strikes(out, slug):
    """How many times auto-run has failed THIS slug since it was last armed.

    A fresh arming resets the count — `draft`'s DRAFTED line, or the owner's own
    `decide --status DRAFTED` re-arm. Our own red lines re-assert DRAFTED (the status is
    deliberately unchanged by a failure) but carry RED_MARK, so they never reset it.
    """
    n = 0
    for r in read_decisions(out):
        if r["slug"] != slug:
            continue
        note = r.get("note") or ""
        if RED_MARK in note:
            n += 1
        elif CAP_MARK in note or STOP_MARK in note:
            continue        # a budget stop or a quiet stop is neither a strike nor an arming
        elif r["status"] in ("DRAFTED", "NEW", "PROPOSED"):
            n = 0
    return n


def quiet_stops(out, slug):
    """(consecutive quiet stops, ts of the last one) for this slug.

    CONSECUTIVE is the load-bearing word. A stop followed by a red, an arming or an
    adoption is not part of a run of stops — only an unbroken sequence means "this runner
    is simply broken", which is the thing worth converting into a strike.
    """
    n, last = 0, ""
    for r in read_decisions(out):
        if r["slug"] != slug:
            continue
        note = r.get("note") or ""
        if STOP_MARK in note:
            n += 1
            last = r.get("ts") or ""
        elif CAP_MARK in note:
            continue                       # a budget stop says nothing about the runner
        else:
            n, last = 0, ""
    return n, last


def cooling_down(out, slug, hours, now=None):
    """"" or why this slug is still in its post-stop cooldown.

    ⛔ THE BACK-OFF. Live, 2026-09-05: the builder exited 1 on three consecutive pulses,
    each logged "strike 0 of 2", because a stop is deliberately not a strike. Nothing was
    spent only because the CLI failed BEFORE reporting usage — a CLI that fails after
    starting would have been paid for on every pulse, forever. So a stopped slug waits.
    """
    n, last = quiet_stops(out, slug)
    if not n or not last:
        return ""
    try:
        when = datetime.strptime(last.strip(), "%Y-%m-%d %H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        # An unreadable stamp is not evidence the cooldown has passed. Fail closed: a
        # clock nobody can read is exactly when a retry loop should NOT start.
        return "last stop stamp %r will not parse — held back rather than retried" % last
    now = now or datetime.now(timezone.utc)
    age_h = (now - when).total_seconds() / 3600.0
    if age_h >= hours:
        return ""
    return ("stopped %.1fh ago (%d consecutive quiet stop(s)); the cooldown is %gh, so it "
            "is retried in %.1fh" % (age_h, n, hours, hours - age_h))


def latest_status(out, slug):
    st = None
    for r in read_decisions(out):
        if r["slug"] == slug:
            st = r["status"]
    return st


def pick_candidate(out, slug=None, cooldown_h=DEFAULT_STOP_COOLDOWN_H):
    """(slug, dir, kind) for the candidate to run, or (None, why, kind).

    `kind` is what the STATUS LINE needs to say: "ok" · "idle" · "cooldown" · "parked" ·
    "error". The caller must not have to re-derive that from a sentence.

    --next takes the OLDEST DRAFTED candidate: first armed, first run. Order comes from
    the append-only decisions file's own order, which is the only order that cannot be
    contradicted by a stamp. A slug still inside its post-stop cooldown is SKIPPED rather
    than run — and the run moves on to the next drafted candidate, because one broken
    runner should not stall a queue it is not at the head of forever.
    """
    rows = read_decisions(out)
    if slug:
        st = latest_status(out, slug)
        if st is None:
            return None, "%r has no ruling in %s — draft it first" % (slug, DECISIONS_MD), "error"
        if st == "PARKED":
            return None, ("%s is PARKED after %d failed run(s) — it is never retried "
                          "unattended. Re-arm it deliberately: decide --slug %s "
                          "--status DRAFTED" % (slug, STRIKES_MAX, slug)), "parked"
        d = out / slugify(slug)
        if not (d / "CONTRACT.md").is_file():
            return None, "%s has no CONTRACT.md — nothing to build against" % d, "error"
        why = cooling_down(out, slug, cooldown_h)
        if why:
            return None, "%s is cooling down: %s" % (slug, why), "cooldown"
        return slug, d, "ok"
    seen, order = {}, []
    for r in rows:
        if r["slug"] not in seen:
            order.append(r["slug"])
        seen[r["slug"]] = r["status"]
    # ⛔ HIGHEST JOB-LIKENESS FIRST, THEN OLDEST. `--next` used to mean "first armed, first
    # run", which is fair and blind: with 38 drafted slugs it spends the night's budget on
    # whichever narration happened to be scaffolded earliest. Ranking first means the
    # runnable-looking work gets the tokens; the append-only order still breaks every tie,
    # so the rule stays deterministic and un-gameable by a stamp.
    scores = {}
    raw = _read(out / CANDIDATES_JSON)
    if raw:
        try:
            for c in json.loads(raw).get("candidates", []):
                scores[c.get("slug")] = float(c.get("score") or 0.0)
        except Exception:
            pass
    # The arming order is captured BEFORE the sort: `order.index()` inside the key reads a
    # list the sort is halfway through rearranging, which raises the moment the first
    # element moves. The tie-break has to be a snapshot, not a live lookup.
    pos = dict((sl, i) for i, sl in enumerate(order))
    order.sort(key=lambda sl: (-scores.get(sl, 0.0), pos[sl]))
    cooling = []
    for sl in order:
        if seen[sl] != "DRAFTED":
            continue
        d = out / slugify(sl)
        if not (d / "CONTRACT.md").is_file():
            continue
        why = cooling_down(out, sl, cooldown_h)
        if why:
            cooling.append((sl, why))
            continue
        return sl, d, "ok"
    if cooling:
        return None, ("every drafted candidate is cooling down after a quiet stop: %s"
                      % " · ".join("%s (%s)" % (sl, w) for sl, w in cooling)), "cooldown"
    return None, ("nothing DRAFTED and buildable in %s (draft --all-ripe scaffolds ripe "
                  "candidates; PARKED and ADOPTED slugs are never picked)" % out), "idle"


def cmd_auto_run(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    out = outdir(a)
    day = a.today or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fault = auto_store_fault(root)
    if fault:
        sys.stderr.write("auto-run: refused — %s\n" % fault)
        return 2
    cfg = auto_config(root)
    if cfg is None:
        print("auto-run: NOT AUTHORIZED — this estate has no valid opt-in marker at %s. "
              "Nothing was run and nothing was spent." % auto_marker(root))
        return 5
    if not cfg["unattended"]:
        print("auto-run: authorized for DISPATCH ONLY — the marker says opted, not "
              "unattended, so a session builds and the daemon spends nothing.")
        print("auto-run: turn it on deliberately: compile.py auto --on --unattended "
              "--daily-cap %d --root %s" % (DEFAULT_DAILY_CAP, a.root))
        return 5

    max_turns = a.max_turns or cfg["max_turns"]
    runner = a.runner or ("claude -p --model %s --output-format json --max-turns %d"
                          % (a.model, max_turns))
    spent_day, unknown = daemon_spend_today(root, day, cfg["run_cap_tokens"])

    # ── the plan, and nothing else (--dry-run spends nothing and takes no lock) ──
    if a.dry_run:
        slug, d, _kind = pick_candidate(out, a.slug, cfg["stop_cooldown_hours"])
        print("auto-run PLAN (--dry-run: nothing runs, nothing is spent, no lock taken)")
        print("  estate        : %s" % root)
        print("  candidate     : %s" % (slug if slug else "(none) — %s" % d))
        if slug:
            print("  runtime       : %s" % d)
            print("  strikes       : %d of %d before PARKED" % (strikes(out, slug),
                                                                STRIKES_MAX))
        print("  runner        : %s" % runner)
        print("  stop cooldown : %gh after a quiet stop; %d consecutive stops = 1 strike"
              % (cfg["stop_cooldown_hours"], STOPS_PER_STRIKE))
        _tok, src, problem = read_credential()
        print("  credential    : %s%s"
              % (src, (" — UNUSABLE: %s" % problem) if problem else
                 (" (the CLI's own login; if it is not logged in, run: python3 %s "
                  "credential --setup)" % SELF if src == "cli" else "")))
        print("  env           : NOTREST_UNATTENDED=1, CLAUDECODE/CLAUDE_CODE_* scrubbed "
              "(hooks suppress the echo and refuse lane spawns)")
        print("  daily cap     : %s spent today (conservative) of %s%s"
              % (f"{spent_day:,}", f"{cfg['daily_cap_tokens']:,}",
                 " — includes %d unknown-usage run(s) charged at the %s run ceiling"
                 % (unknown, f"{cfg['run_cap_tokens']:,}") if unknown else ""))
        print("  run cap       : %s tokens for this invocation" % f"{cfg['run_cap_tokens']:,}")
        print("  steps         : BUILD (tokens) → fixture.sh (free) → REFUTE (tokens) "
              "→ benchmark.sh (free) → decide --status ADOPTED")
        print("  adopt needs   : %s — all three, or the status stays put"
              % ", ".join(ADOPT_RECEIPTS))
        print("  on adoption   : prints `%s` — the scaffold is gitignored while DRAFTED "
              "and a person admits it" % git_add_line(slug or "<slug>"))
        return 0

    # ── the estate lock: one candidate at a time, and never beside a live compile ──
    out.mkdir(parents=True, exist_ok=True)
    lock_path = out / AUTORUN_LOCK
    try:
        lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as exc:
        sys.stderr.write("auto-run: cannot open the lock at %s (%s)\n" % (lock_path, exc))
        return 2
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(lock_fd)
        # BUSY IS NOT AN ERROR. The daemon fires on a schedule; a run still going is the
        # system working. Exit 0, one line, no queue, no retry — a queue of unattended
        # runs is how one slow build becomes ten concurrent ones.
        # THE LOCK WORKING, said in words. Two pulses landing in the same second and one
        # standing down is the design, not a fault — and a log that only says BUSY beside
        # a STOPPED from the other run reads like a race nobody planned.
        pulse_line(root, "BUSY — %s is held by another run (or a live session's own "
                         "compile), so this one stood down. THIS IS THE LOCK WORKING: one "
                         "candidate at a time, estate-wide. Nothing started, nothing spent."
                   % lock_path)
        return 0
    try:
        return _auto_run_locked(a, root, out, cfg, runner, day)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except OSError:
            pass


def _auto_run_locked(a, root, out, cfg, runner, day):
    slug, d, kind = pick_candidate(out, a.slug, cfg["stop_cooldown_hours"])
    if slug is None:
        pulse_line(root, "nothing to do — %s" % d)
        if kind == "cooldown":
            write_status(root, "COOLDOWN %s until cooldown expires — %s"
                         % (a.slug or "all drafted", d))
        elif kind == "idle":
            write_status(root, "IDLE nothing drafted")
        return 0
    n = strikes(out, slug)
    if n >= STRIKES_MAX:
        record_decision(out, slug, "PARKED", note=(
            "auto-run: %d strike(s) already recorded and the slug was still DRAFTED — "
            "PARKED without running. Re-arm with decide --status DRAFTED" % n))
        pulse_line(root, "%s already carries %d strike(s) — PARKED, not run" % (slug, n))
        return 0

    # ── the credential, resolved ONCE, before a single token is spent ──────────
    # A run that cannot authenticate should never reach the runner at all: calling it
    # anyway buys three identical failures and a cooldown for a slug that did nothing
    # wrong. The value is read here and goes nowhere but the child's environment.
    token, cred_src, cred_problem = read_credential()
    if cred_problem:
        # The MODE is the message. Silently falling back to "no credential" would teach
        # the owner that a world-readable token is merely ineffective, not dangerous.
        pulse_line(root, "BLOCKED before %s: the credential file is unusable — %s "
                         "(credential: none)" % (slug, cred_problem))
        write_status(root, "BLOCKED auth: credential file unusable — %s" % cred_problem)
        return 0
    spent_run = [0]
    pulse_line(root, "start %s (strike %d of %d) · runner=%s · credential: %s"
               % (slug, n, STRIKES_MAX, runner.split()[0] if runner else "?", cred_src))

    def cap_stop(step):
        """The reason this step must not START, or ""."""
        spent_day, unknown = daemon_spend_today(root, day, cfg["run_cap_tokens"])
        note = (" (includes %d run(s) whose usage the CLI never reported, each charged at "
                "the %s run ceiling — conservative, because an uncounted run that costs "
                "nothing against a cap is a cap with a hole in it)"
                % (unknown, f"{cfg['run_cap_tokens']:,}")) if unknown else ""
        if spent_day >= cfg["daily_cap_tokens"]:
            return ("DAILY CAP reached: %s of %s daemon tokens already spent on %s%s"
                    % (f"{spent_day:,}", f"{cfg['daily_cap_tokens']:,}", day, note))
        if spent_run[0] >= cfg["run_cap_tokens"]:
            return ("RUN CAP reached: %s of %s tokens spent by this invocation"
                    % (f"{spent_run[0]:,}", f"{cfg['run_cap_tokens']:,}"))
        return ""

    def capped(step):
        """True when THIS INVOCATION has now spent past its ceiling.

        Checked AFTER each token step as well as before, because a cap can only be
        checked before a step against what is already spent — the step's own cost is not
        knowable until it has been paid. So the ceiling bounds the run in two ways: it
        refuses to START a step past it, and it STOPS the pipeline the moment a step
        carries the run over. The stop is RECORDED, not just printed: a run that ended
        because it ran out of budget must not be indistinguishable, tomorrow, from one
        that ended because the work was done.
        """
        if spent_run[0] < cfg["run_cap_tokens"]:
            return False
        record_decision(out, slug, "DRAFTED", note=(
            "auto-run CAPPED after %s: this invocation spent %s tokens against a run cap "
            "of %s — pipeline stopped, status unchanged, no adoption. Nothing is wrong "
            "with the candidate; it ran out of budget"
            % (step, f"{spent_run[0]:,}", f"{cfg['run_cap_tokens']:,}")))
        pulse_line(root, "CAPPED after %s on %s — %s tokens spent against a run cap of "
                         "%s. Stopped; retried on the next run."
                   % (step, slug, f"{spent_run[0]:,}", f"{cfg['run_cap_tokens']:,}"))
        return True

    def quiet_stop(step, why, is_auth):
        """Record a stop: stamp it, cool the slug down, and convert a RUN of them.

        A stop is not the candidate's fault, so it is not a strike — but a runner that
        stops forever is indistinguishable from one that will never work, and %d in a row
        is where that stops being a distinction worth keeping.
        """ % STOPS_PER_STRIKE
        n, _last = quiet_stops(out, slug)
        n += 1
        cool = cfg["stop_cooldown_hours"]
        if n >= STOPS_PER_STRIKE:
            # The run of stops becomes ONE strike, and the counter starts again.
            k = strikes(out, slug) + 1
            status = "PARKED" if k >= STRIKES_MAX else "DRAFTED"
            record_decision(out, slug, status, note=(
                "%s %s (strike %d/%d, from %d consecutive quiet stops): %s%s"
                % (RED_MARK, step, k, STRIKES_MAX, n, why,
                   " — PARKED: never retried unattended. Re-arm with decide --slug "
                   "%s --status DRAFTED" % slug if status == "PARKED" else "")))
            pulse_line(root, "STOPPED on %s (%d in a row) — counted as strike %d/%d%s: %s"
                       % (step, n, k, STRIKES_MAX,
                          ", slug PARKED" if status == "PARKED" else "", why))
        else:
            record_decision(out, slug, "DRAFTED", note=(
                "%s %s (quiet stop %d/%d; not a strike): %s — status unchanged; this slug "
                "is not retried for %gh"
                % (STOP_MARK, step, n, STOPS_PER_STRIKE, why, cool)))
            pulse_line(root, "STOPPED on %s: %s — status unchanged, NO retry: %s is in a "
                             "%gh cooldown (quiet stop %d of %d before it counts as a "
                             "strike)." % (step, why, slug, cool, n, STOPS_PER_STRIKE))
        if is_auth:
            # Named here and only here: with no env var and no file we were relying on the
            # CLI's own login, and this is the moment it demonstrably is not there.
            pulse_line(root, "BLOCKED auth (credential: %s). Fix it with ONE command: "
                             "python3 %s credential --setup" % (cred_src, SELF))
            write_status(root, "BLOCKED auth: %s — run: python3 %s credential --setup"
                         % (why, SELF))
        else:
            write_status(root, "COOLDOWN %s until +%gh — %s" % (slug, cool, why))

    def red(step, why):
        """A gate came back red. The status is UNCHANGED — the reason is what is new."""
        k = strikes(out, slug) + 1
        if k >= STRIKES_MAX:
            record_decision(out, slug, "PARKED", note=(
                "%s %s (strike %d/%d): %s — PARKED: never retried unattended. Re-arm "
                "with decide --slug %s --status DRAFTED"
                % (RED_MARK, step, k, STRIKES_MAX, why, slug)))
            pulse_line(root, "RED %s on %s — strike %d/%d, slug PARKED: %s"
                       % (step, slug, k, STRIKES_MAX, why))
            write_status(root, "OK %s red at %s (parked)" % (slug, step))
        else:
            record_decision(out, slug, "DRAFTED", note=(
                "%s %s (strike %d/%d): %s — status unchanged, will be retried"
                % (RED_MARK, step, k, STRIKES_MAX, why)))
            pulse_line(root, "RED %s on %s — strike %d/%d: %s"
                       % (step, slug, k, STRIKES_MAX, why))
            write_status(root, "OK %s red at %s" % (slug, step))
        return 3

    def token_step(step, prompt):
        """(verdict, text) where verdict is "ok" | "stop" | "cap" | a red reason."""
        why = cap_stop(step)
        if why:
            pulse_line(root, "REFUSED to start %s on %s — %s. Nothing spent."
                       % (step, slug, why))
            write_status(root, "OK %s capped before %s" % (slug, step))
            return "cap", ""
        rc, sout, serr = run_runner(runner, prompt, d, a.timeout, token)
        tokens, model, text, is_error = parse_runner_json(sout)
        model = model or a.model
        # Diagnosability: whatever the child said, kept. The live report was three
        # identical "runner exited 1" lines carrying no cause at all.
        detail = tail_err(text if is_error else "", serr, sout if not text else "")
        auth = looks_unauthenticated(sout, serr, text)
        # THE RECEIPT COMES FIRST, before any verdict on the run. A call that failed
        # still cost tokens, and a ledger that only records successful spending is a
        # ledger that under-reports exactly when it matters.
        why = ""
        if auth:
            why = "AUTH: %s" % (str(text or serr or "").strip()[:200] or "not authenticated")
        elif is_error:
            why = "the CLI reported is_error: %s" % (str(text or "").strip()[:200]
                                                    or "(no result text)")
        elif rc != 0:
            why = "runner exited %d: %s" % (rc, detail)
        receipt(root, model, tokens,
                "compile auto-run %s: candidate %s (unattended, no session watching)%s"
                % (step, slug, (" — STOPPED: %s" % why) if why else ""),
                counted_as=cfg["run_cap_tokens"])
        spent_run[0] += tokens or 0
        if why:
            # ⛔ QUIET, NO RETRY THIS RUN, AND A BACK-OFF BEFORE THE NEXT ONE. `is_error`
            # is checked regardless of the exit code: the CLI answers an expired OAuth
            # session with subtype "success", is_error true, and exit 0, so a runner
            # judged on rc alone would have called this a finished build and gone on to
            # pay for a refuter against the same dead session.
            quiet_stop(step, why, auth)
            return "stop", text
        return "ok", text

    # ── 1 · BUILD (tokens) ────────────────────────────────────────────────────
    verdict, _text = token_step("build", BUILD_PROMPT.format(slug=slug, d=d))
    if verdict == "stop":
        return 0
    if verdict == "cap" or capped("build"):
        return 6

    # ── 2 · FIXTURE (free). Deliberately BEFORE the refuter, which the addendum
    # ordered after it: the fixture costs nothing and a runtime that fails its own
    # tests has nothing worth attacking. Spending refuter tokens on it would be
    # paying to be told what a free script already said.
    fx = d / "fixture.sh"
    if not fx.is_file():
        return red("fixture", "no fixture.sh in %s — a runtime with no test is not a "
                              "candidate for adoption" % d)
    rc, fxout = run_script(fx, d)
    if rc != 0:
        return red("fixture", "fixture.sh exited %d: %s"
                   % (rc, " ".join(fxout.split())[-160:]))
    fixture_receipt = "%s/fixture.sh exit 0" % d.name

    # ── 3 · REFUTE (tokens) ───────────────────────────────────────────────────
    verdict, text = token_step("refute", REFUTE_PROMPT.format(slug=slug, d=d))
    if verdict == "stop":
        return 0
    if verdict == "cap" or capped("refute"):
        return 6
    ref_md = _read(d / "REFUTER.md") or ""
    # FAIL CLOSED: only an explicit CLEAN verdict is clean. Silence, a crash, a refuter
    # that wandered off — all read as a defect, because this runs with nobody watching
    # and the alternative is silence promoting a runtime.
    if "REFUTER: CLEAN" not in (text or "") and "REFUTER: CLEAN" not in ref_md:
        first = next((ln for ln in (text or "").splitlines()
                      if ln.strip().startswith("REFUTER:")), "")
        return red("refute", first.strip() or "no `REFUTER: CLEAN` verdict in the result "
                                              "or REFUTER.md — silence reads as a defect")
    refuter_receipt = "%s/REFUTER.md CLEAN" % d.name

    # ── 4 · BENCHMARK (free) ──────────────────────────────────────────────────
    bm = d / "benchmark.sh"
    if not bm.is_file():
        return red("benchmark", "no benchmark.sh in %s — a parity claim with no harness "
                                "is a claim" % d)
    rc, bmout = run_script(bm, d)
    if rc != 0:
        return red("benchmark", "benchmark.sh exited %d (4 = still the scaffold stub): %s"
                   % (rc, " ".join(bmout.split())[-160:]))
    benchmark_receipt = "%s/benchmark.sh exit 0" % d.name

    # ── 5 · ADOPT ─────────────────────────────────────────────────────────────
    ev = {"fixture": fixture_receipt, "benchmark": benchmark_receipt,
          "refuter": refuter_receipt}
    sig, _known = candidate_sig(out, slug)
    line = record_decision(out, slug, "ADOPTED", note=(
        "auto-run: build, fixture, refuter and FAIR benchmark all green under the "
        "unattended rails (run spend %s tokens)" % f"{spent_run[0]:,}"), evidence=ev,
        sig=sig)
    write_status(root, "OK %s adopted" % slug)
    pulse_line(root, "ADOPTED %s — %s" % (slug, " · ".join(
        "%s=%s" % (k, ev[k]) for k in ADOPT_RECEIPTS)))
    print("recorded:", line.strip())
    print("COORD line: - [%s] [compile] auto-run %s -> ADOPTED | evidence: %s"
          % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"), slug,
             " · ".join("%s=%s" % (k, ev[k]) for k in ADOPT_RECEIPTS)))
    print("git: the scaffold is gitignored while DRAFTED. Admit this one deliberately:")
    print("    %s" % git_add_line(slug))
    print("[compile] ADOPTED rules that the estate may USE this runtime. It is still "
          "INSTALLED NOWHERE: wiring it into the harness is a versioned release the "
          "owner ships (Part 3), and no marker has ever authorized that.")
    return 0


# ── credential: put the token where the daemon can find it, safely ───────────
#
# LIVE OWNER FAILURE, 2026-09-05, and the reason this verb exists: the owner ran
# `claude setup-token`, the terminal WRAPPED the printed token, the clipboard carried the
# wrap as a real line break, and the CLI rejected it — "a line break at character 80 (110
# characters on 2 lines)". Every step of that is normal behaviour by a terminal, a
# clipboard and a CLI; the only thing missing was something that took the paste and made
# it into a credential. So: read it without echoing it, squeeze the whitespace out, check
# it before writing it, write it with the mode the reader demands, and — with --verify —
# spend ONE turn proving it actually works before an unattended run finds out at 3am.
#
# ⛔ THE VALUE IS NEVER PRINTED, LOGGED OR RECEIPTED. Not on success, not in an error, not
# in a refusal. Everything below reports its LENGTH, its SHAPE or its SOURCE, never a
# character of it. The verify probe is the one place it is used, and it goes there in the
# child's environment only.
CRED_CHARSET = re.compile(r"^[A-Za-z0-9._~+/=-]+$")
CRED_MIN_LEN = 16
# Counting a known prefix is how "did they paste two of them?" is answered without ever
# looking at the value: a credential carries its issuer's prefix once.
CRED_PREFIXES = ("sk-ant-", "sk-")
VERIFY_CMD = "claude -p --model sonnet --max-turns 1 --output-format json"


def cred_shape_problem(token, lines_joined):
    """Why this input is not one credential — or "". Never quotes the value."""
    if not token:
        return "the input was empty once whitespace was removed"
    if len(token) < CRED_MIN_LEN:
        return ("the input is %d characters once whitespace is removed, under the %d-character "
                "floor — that is a truncated paste, not a token" % (len(token), CRED_MIN_LEN))
    if not CRED_CHARSET.match(token):
        bad = sorted({c for c in token if not CRED_CHARSET.match(c)})
        return ("the input carries %d character(s) no credential contains (%s) — that looks "
                "like a label or a shell prompt came along with the paste"
                % (len(bad), " ".join(repr(c) for c in bad)))
    for pre in CRED_PREFIXES:
        if token.count(pre) > 1:
            return ("the input contains the issuer prefix %r %d times — that is more than one "
                    "credential pasted together, and this file holds exactly one"
                    % (pre, token.count(pre)))
    return ""


def write_credential(token):
    """Write the token at 0600 in a 0700 directory, atomically. Returns the path."""
    p = cred_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(p.parent), 0o700)
    except OSError:
        pass
    tmp = p.with_name(p.name + ".tmp")
    # The mode is set BEFORE the bytes land: a credential must never exist, even for an
    # instant, at a mode another account could read.
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    os.replace(str(tmp), str(p))
    try:
        os.chmod(str(p), 0o600)
    except OSError:
        pass
    return p


def verify_credential(token):
    """(ok, detail) — one headless turn under this credential and nothing else.

    The probe runs the REAL `claude` from PATH on purpose: the question is whether this
    token works with the CLI the daemon will call, and an injectable runner would answer a
    different question. Fixtures put a fake `claude` earlier in PATH.
    """
    env = child_env(token)
    try:
        r = subprocess.run(VERIFY_CMD, shell=True, input=b"Reply with the single word: ok",
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                           timeout=120)
    except subprocess.TimeoutExpired:
        return False, "the probe did not answer within 120s"
    except OSError as exc:
        return False, "%s running the probe" % exc.__class__.__name__
    sout = r.stdout.decode("utf-8", "replace")
    serr = r.stderr.decode("utf-8", "replace")
    _tok, _model, text, is_error = parse_runner_json(sout)
    if r.returncode != 0 or is_error or looks_unauthenticated(sout, serr, text):
        detail = " ".join((text or serr or sout or "the CLI said nothing").split())
        return False, detail[:120]
    return True, ""


SETUP_CMD = "claude setup-token"


def extract_token(stdout_text):
    """(token, problem) — the ONE token `claude setup-token` printed, or why not.

    ⛔ A WRAPPED TOKEN IS ONE CANDIDATE, NOT TWO. This is the live failure the whole verb
    exists for: the terminal wraps the printed token and the break is real in the output.
    So ADJACENT lines that are pure token characters are joined — that is exactly what a
    wrap looks like — and candidates are separated by blank lines or prose. A token split
    over two lines is therefore one candidate; two tokens with anything between them are
    two, and two is refused. Prose lines (which contain spaces) never join anything.
    """
    groups, cur = [], []
    for raw in (stdout_text or "").splitlines():
        line = raw.strip()
        if line and " " not in line and "\t" not in line and CRED_CHARSET.match(line):
            cur.append(line)
            continue
        if cur:
            groups.append("".join(cur))
            cur = []
    if cur:
        groups.append("".join(cur))
    cands = [g for g in groups if not cred_shape_problem(g, 1)]
    if not cands:
        return "", ("no token in the output of `%s` — %d candidate line group(s) were "
                    "examined and none had the shape of a credential" % (SETUP_CMD, len(groups)))
    if len(cands) > 1:
        return "", ("%d separate tokens in the output of `%s` — this file holds exactly "
                    "one, and guessing which is not something to do with a credential"
                    % (len(cands), SETUP_CMD))
    return cands[0], ""


def cmd_credential(a):
    p = cred_file()
    if a.setup:
        # ⛔ THE USER'S OWN TTY. `claude setup-token` opens a browser and waits for the
        # human — so stdin and stderr are INHERITED (they see the prompt, the URL, and
        # whatever it asks) and only stdout is captured, because stdout is where the token
        # comes back. Capturing all three would hide the browser step behind a hang.
        print("credential: running `%s` — complete the browser step it opens." % SETUP_CMD)
        print("credential: its output is captured; the token is never printed here.")
        try:
            r = subprocess.run(SETUP_CMD, shell=True, stdout=subprocess.PIPE, timeout=900)
        except subprocess.TimeoutExpired:
            sys.stderr.write("credential: `%s` did not finish within 15 minutes — nothing "
                             "written\n" % SETUP_CMD)
            return 5
        except OSError as exc:
            sys.stderr.write("credential: could not run `%s` (%s) — is the CLI on PATH?\n"
                             % (SETUP_CMD, exc.__class__.__name__))
            return 5
        out = r.stdout.decode("utf-8", "replace")
        if r.returncode != 0:
            sys.stderr.write("credential: `%s` exited %d — nothing written\n"
                             % (SETUP_CMD, r.returncode))
            return 5
        token, problem = extract_token(out)
        if problem:
            # The OUTPUT is never echoed back on failure: it is the one place the token
            # certainly is.
            sys.stderr.write("credential: REFUSED — %s\n" % problem)
            sys.stderr.write("credential: nothing was written to %s. If the CLI printed a "
                             "token you can see, paste it instead: python3 %s credential "
                             "--set --verify\n" % (p, SELF))
            return 2
        lines = len([ln for ln in out.splitlines() if ln.strip()])
        ok, detail = verify_credential(token)
        if not ok:
            print("credential: invalid — %s" % detail)
            sys.stderr.write("credential: nothing was written to %s\n" % p)
            return 5
        written = write_credential(token)
        print("credential: written to %s (mode 0600, directory mode 0700)" % written)
        print("credential: %d characters, recovered from %d line(s) of output — whitespace "
              "stripped; the value is never printed, logged or receipted"
              % (len(token), lines))
        print("credential: ok")
        return 0
    if a.status:
        _tok, src, problem = read_credential()
        if src == "env":
            print("credential: env (CLAUDE_CODE_OAUTH_TOKEN is set in this environment; "
                  "the file is not read)")
            return 0
        if not p.exists():
            print("credential: absent — no file at %s" % p)
            print("credential: unattended runs will use the CLI's OWN login. That is "
                  "enough on a machine whose terminal is logged in; storing one is "
                  "OPTIONAL.")
            print("credential: if runs stop with BLOCKED auth, ONE command fixes it: "
                  "python3 %s credential --setup" % SELF)
            return 5
        try:
            st, dst = p.stat(), p.parent.stat()
            print("credential: present at %s (file mode %04o, directory mode %04o)"
                  % (p, st.st_mode & 0o777, dst.st_mode & 0o777))
        except OSError as exc:
            print("credential: unreadable at %s (%s)" % (p, exc.__class__.__name__))
            return 5
        if problem:
            print("credential: UNUSABLE — %s" % problem)
            return 5
        print("credential: usable (its value is never printed by this tool)")
        return 0

    if not a.set:
        sys.stderr.write("credential needs --setup, --set or --status\n")
        return 2

    # Echo OFF when a human is typing; a plain read when a script is piping.
    if sys.stdin.isatty():
        import getpass
        print("Paste the token from `claude setup-token` (input is hidden; a wrapped paste "
              "is fine — every line break and space is stripped):")
        try:
            raw = getpass.getpass("token: ")
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\ncredential: cancelled — nothing written\n")
            return 2
    else:
        raw = sys.stdin.read()
    lines = len([ln for ln in (raw or "").splitlines() if ln.strip()])
    token = squeeze(raw)
    problem = cred_shape_problem(token, lines)
    if problem:
        sys.stderr.write("credential: REFUSED — %s\n" % problem)
        sys.stderr.write("credential: nothing was written to %s\n" % p)
        return 2
    if a.verify:
        # ⛔ VERIFY BEFORE WRITING. A token that does not work should not become the file
        # an unattended run at 3am depends on.
        ok, detail = verify_credential(token)
        if not ok:
            print("credential: invalid — %s" % detail)
            sys.stderr.write("credential: nothing was written to %s\n" % p)
            return 5
    written = write_credential(token)
    # LENGTH AND LINE COUNT ONLY. Saying the paste arrived on two lines is what tells the
    # owner the wrap was handled; saying anything about the characters would not.
    print("credential: written to %s (mode 0600, directory mode 0700)" % written)
    print("credential: %d characters, from %d pasted line(s) — whitespace stripped; the "
          "value is never printed, logged or receipted" % (len(token), lines))
    if a.verify:
        print("credential: ok")
    else:
        print("credential: not verified — re-run with --verify to spend one turn proving "
              "it works before an unattended run depends on it")
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
    d.add_argument("--evidence", action="append", metavar="KIND=REF",
                   help="repeatable receipt, one of %s=REF; ALL THREE are required for "
                        "--status ADOPTED (refused, exit 2, without them)"
                        % "|".join(ADOPT_RECEIPTS))
    d.set_defaults(f=cmd_decide)

    dr = sub.add_parser("draft",
                        help="scaffold every ripe NEW candidate (contract + skeleton + "
                             "benchmark harness) and record it DRAFTED; zero tokens")
    dr.add_argument("--root", default=".")
    dr.add_argument("--out", default="compile")
    dg = dr.add_mutually_exclusive_group()
    dg.add_argument("--all-ripe", dest="all_ripe", action="store_true",
                    help="every ripe candidate whose status is still NEW")
    dg.add_argument("--slug", default="", help="one scanned candidate by slug or alias")
    dr.add_argument("--max", dest="max_drafts", type=int, default=DEFAULT_DRAFT_MAX,
                    metavar="N",
                    help="draft at most N candidates per pass, highest job-likeness first "
                         "(default %d); the rest stay NEW and wait" % DEFAULT_DRAFT_MAX)
    dg.add_argument("--recheck", action="store_true",
                    help="RETROACTIVE: re-judge every DRAFTED slug already on disk against "
                         "the machinery test, reading its cited rows from today's ledgers; "
                         "DECLINES the machinery-derived ones, deletes nothing")
    dr.set_defaults(f=cmd_draft)

    arr = sub.add_parser("auto-run",
                         help="the unattended pipeline: oldest DRAFTED candidate → build "
                              "→ fixture → refute → benchmark → ADOPTED, under the caps")
    arr.add_argument("--root", default=".")
    arr.add_argument("--out", default="compile")
    ag = arr.add_mutually_exclusive_group()
    ag.add_argument("--next", action="store_true",
                    help="the oldest DRAFTED candidate (the default when neither is given)")
    ag.add_argument("--slug", default="", help="one candidate by slug")
    arr.add_argument("--runner", default="",
                    help="the headless model command; the prompt arrives on ITS STDIN. "
                         "Default: claude -p --model <model> --output-format json "
                         "--max-turns <n>. Injectable so fixtures never spend a token.")
    arr.add_argument("--model", default="opus",
                     help="the model asked for, and recorded on every receipt")
    arr.add_argument("--max-turns", dest="max_turns", type=int, default=None,
                     help="override the marker's turn limit for this run")
    arr.add_argument("--timeout", type=int, default=STEP_TIMEOUT,
                     help="seconds per runner call (default %d)" % STEP_TIMEOUT)
    arr.add_argument("--today", default="",
                     help="the day the daily cap is summed over (default: UTC today)")
    arr.add_argument("--dry-run", dest="dry_run", action="store_true",
                     help="print the plan; spend nothing, take no lock, change nothing")
    arr.set_defaults(f=cmd_auto_run)

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
    g.add_argument("--on", action="store_true",
                   help="write the owner-private marker under ~/.notrest/auto-build/")
    g.add_argument("--off", action="store_true", help="remove that marker")
    au.add_argument("--unattended", action="store_true",
                    help="with --on: authorize the pulse daemon to RUN the pipeline and "
                         "SPEND tokens, under the caps below")
    au.add_argument("--daily-cap", dest="daily_cap", type=int, default=None,
                    metavar="N", help="daemon tokens per day (default %d)" % DEFAULT_DAILY_CAP)
    au.add_argument("--run-cap", dest="run_cap", type=int, default=None, metavar="M",
                    help="tokens per auto-run invocation (default %d)" % DEFAULT_RUN_CAP)
    au.add_argument("--max-turns", dest="max_turns", type=int, default=None, metavar="T",
                    help="turn limit passed to each headless runner call (default %d)"
                         % DEFAULT_MAX_TURNS)
    au.add_argument("--stop-cooldown", dest="stop_cooldown", type=int, default=None,
                    metavar="H",
                    help="hours a slug waits after a quiet stop before it is retried "
                         "(default %d); %d consecutive stops count as one strike"
                         % (DEFAULT_STOP_COOLDOWN_H, STOPS_PER_STRIKE))
    au.set_defaults(f=cmd_auto)

    cr = sub.add_parser("credential",
                        help="put the `claude setup-token` token where the unattended "
                             "runner reads it: %s" % "/".join(CRED_REL))
    cg = cr.add_mutually_exclusive_group(required=True)
    cg.add_argument("--setup", action="store_true",
                    help="THE ONE COMMAND: run `claude setup-token` on your terminal, "
                         "recover the token from its output (wrapped or not), write it at "
                         "mode 0600 and verify it in one turn")
    cg.add_argument("--set", action="store_true",
                    help="read the token from stdin (hidden when interactive), strip ALL "
                         "whitespace, and write it at mode 0600")
    cg.add_argument("--status", action="store_true",
                    help="present/absent and the modes — never the value")
    cr.add_argument("--verify", action="store_true",
                    help="with --set: spend ONE headless turn proving the token works "
                         "BEFORE writing it; prints `credential: ok` or "
                         "`credential: invalid — <reason>`")
    cr.set_defaults(f=cmd_credential)

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
