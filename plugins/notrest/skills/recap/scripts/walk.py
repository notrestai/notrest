#!/usr/bin/env python3
"""walk.py — recap's estate walker. The script walks; the model narrates.

recap's read is the biggest in the suite — every COORD volume, the agent ledger,
git, the spend ledger and the findings store, merged in timestamp order. Doing
that by hand costs a fortune in tokens AND is exactly where a citation gets
invented: a model that re-types a ledger line from a summary it read 40k tokens
ago will eventually re-type it wrong. So the machine does the walking and hands
the session ONE stream with the citation token already computed per entry.

Subcommands:
  walk    --root DIR [--since ISO] [--until ISO] [--json] [--head N]
          The whole estate merged into one timestamp-sorted stream, preceded by
          the estate inventory (recap Step 1) — every source named, including
          the absent ones.
  spans   --root DIR [--since ISO] [--until ISO] [--gap MIN] [--json]
          Per-source / per-day / per-session spans and counts — the skeleton a
          narrator hangs beats on.
  prefill --root DIR [--since ISO] [--until ISO] [--out PATH] [--project NAME]
          [--max-nodes N] [--now ISO]
          The RECAP_DATA block for assets/decision-map-template.html with nodes
          and cites already filled. The model contributes edges and narrative.

exit: 0 ok · 2 usage · 3 the estate is empty (no entry in any source)

THREE CLOCK SHAPES, ONE INSTANT. COORD writes `[2026-07-25 04:30Z]`, the findings
store writes `2026-07-25T04:30:00Z`, git keeps an epoch. They are merged on the
INSTANT and printed in each source's own form — normalizing a timestamp to make
a table tidy breaks recap's verbatim rule, and merging on the printed string
sorts a store record after a COORD line it preceded.

GIT IS READ AS AN EPOCH, NEVER AS A FORMATTED DATE. `git log --date=format:...`
prints the AUTHOR'S LOCAL time with a `Z` you did not earn; the documented fix is
`TZ=UTC ... --date=format-local:`, which then depends on an environment variable
being right. This asks for `%at` (author epoch — timezone-independent by
construction) and formats the display string itself. There is no TZ to get wrong.

A LEDGER LINE IS AN INDEX, NOT A SOURCE. Every transcript path, brief path,
evidence path and dossier path this emits is existence-checked, and a dead one is
marked `!! DEAD:` in the stream and flagged `dead-pointer` in the JSON. recap may
then say "the line exists; the transcript does not" without opening anything.

DETERMINISTIC. No subcommand reads the wall clock. `prefill`'s `generated` field
defaults to the date of the newest walked entry (an estate fact, not a clock
read); `--now` overrides it explicitly. Identical inputs produce byte-identical
output, which is what makes a re-run a check rather than a coin flip.

Zero model tokens.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HEAD_DEFAULT = 140      # stream head truncation; --head 0 prints the whole line
GAP_DEFAULT = 90        # minutes of silence that end a session, for `spans`
MAX_NODES_DEFAULT = 60  # a decision map past this is a hairball, not a map
MAX_PATHS_PER_LINE = 4  # bound the existence-checking on a chatty COORD line
STATEMENT_HEAD = 200
# JS line terminators that JSON leaves raw — they would break a <script> block.
LS, PS = chr(0x2028), chr(0x2029)

# The template's four lanes (KINDS in decision-map-template.html). A node kind
# outside this set throws in the renderer — prefill must never emit one.
NODE_KINDS = ("ruling", "decision", "consult", "ship")
NODE_PRIORITY = {"ruling": 0, "ship": 1, "decision": 2, "consult": 3}

# Same-instant display order. This is a TIE-BREAK, not a causal claim: when a
# COORD line and a spend line carry the same minute, something has to print
# first, and it must be the same something on every run.
SOURCE_RANK = {"coord": 0, "agents": 1, "git": 2, "spend": 3, "findings": 4}


# ── clocks ────────────────────────────────────────────────────────────────────
TS_RE = re.compile(
    r"^\s*(\d{4})-(\d{2})-(\d{2})"
    r"(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?)?"
    r"\s*(Z|z|[+-]\d{2}:?\d{2})?\s*$")


def parse_ts(raw, end_of_day=False):
    """Any of the estate's clock shapes → (iso8601Z, epoch seconds), or None.

    A bare date means midnight, except on `--until` where it means the end of
    that day — otherwise `--until 2026-07-25` would silently drop everything
    recorded on the 25th, which is never what a person asking for a window means.
    """
    if raw is None:
        return None
    m = TS_RE.match(str(raw))
    if not m:
        return None
    y, mo, d, hh, mm, ss, off = m.groups()
    bare = hh is None
    hh = int(hh) if hh else (23 if (bare and end_of_day) else 0)
    mm = int(mm) if mm else (59 if (bare and end_of_day) else 0)
    ss = int(ss) if ss else (59 if (bare and end_of_day) else 0)
    try:
        dt = datetime(int(y), int(mo), int(d), hh, mm, ss, tzinfo=timezone.utc)
    except ValueError:
        return None
    if off and off not in ("Z", "z"):
        sign = 1 if off[0] == "+" else -1
        o = off[1:].replace(":", "")
        dt = dt - sign * _delta(int(o[:2]), int(o[2:4]))
    return (dt.strftime("%Y-%m-%dT%H:%M:%SZ"), int(dt.timestamp()))


def _delta(hours, minutes):
    return timedelta(hours=hours, minutes=minutes)


def epoch_to_coord(epoch):
    """Epoch → the estate's COORD shape. Only used for git, which has no textual
    form of its own in the trail."""
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def epoch_to_day(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d")


# ── entries ───────────────────────────────────────────────────────────────────
class Entry:
    __slots__ = ("ts", "iso", "epoch", "source", "kind", "ref", "eid",
                 "cite", "head", "text", "title", "summary", "flags", "paths", "seq",
                 "eff_epoch")

    def __init__(self, ts, iso, epoch, source, kind, ref, eid, cite, text,
                 head="", title="", summary="", flags=None, paths=None, seq=0):
        self.ts = ts                       # verbatim, in the source's own shape
        self.iso = iso
        self.epoch = epoch
        self.source = source
        self.kind = kind
        self.ref = ref                     # file:line, or a commit sha
        self.eid = eid                     # agent id / F-n / sha / ""
        self.cite = cite                   # the citation token recap should use
        # `text` is the WHOLE recorded line, verbatim — it is what a cite quotes.
        # `head` is the readable part, with the timestamp/lane prefix stripped
        # because the stream already prints those in their own columns.
        self.text = collapse(text)
        self.head = collapse(head) or self.text
        self.title = collapse(title) or self.head
        self.summary = collapse(summary)
        self.flags = flags or []
        self.paths = paths or []           # [{"ref":..., "abs":..., "exists":bool}]
        self.seq = seq
        # S81: the epoch this entry is ORDERED by. Defaults to its own stamp, so an
        # Entry built anywhere still sorts exactly as before; monotone_epochs() below
        # replaces it where a composed stamp would contradict positional truth.
        self.eff_epoch = epoch

    @property
    def sortkey(self):
        # S81: was `self.epoch`. A future-stamped ledger line sorted AFTER lines it
        # positionally precedes -- driven: ingestion seq [1,2,3,4] came back [1,3,2,4].
        return (self.eff_epoch, SOURCE_RANK.get(self.source, 9), self.seq)

    @property
    def dead(self):
        return [p for p in self.paths if not p["exists"]]

    def as_dict(self, head):
        return {
            "ts": self.ts, "ts_iso": self.iso, "epoch": self.epoch,
            "source": self.source, "kind": self.kind, "ref": self.ref,
            "id": self.eid, "cite": self.cite,
            "head": trunc(self.head, head), "text": self.text,
            "title": self.title, "summary": self.summary,
            "flags": self.flags, "paths": self.paths,
        }


def collapse(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def trunc(s, n):
    if not n or len(s) <= n:
        return s
    return s[: max(1, n - 1)].rstrip() + "…"


def read_text(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def check_path(root, raw):
    """Existence-check one emitted pointer. Absolute paths are checked where they
    point; relative ones against the estate root."""
    raw = str(raw).strip().rstrip(",;")
    p = pathlib.Path(raw)
    ap = p if p.is_absolute() else (root / raw)
    try:
        exists = ap.exists()
    except OSError:
        exists = False
    return {"ref": raw, "abs": str(ap), "exists": bool(exists)}


# ── source readers ────────────────────────────────────────────────────────────
COORD_RE = re.compile(
    r"^-\s*\[(?P<ts>[^\]]+)\]\s*(?:\[(?P<lane>[^\]]*)\]\s*)?(?P<body>.+)$")
AGENT_RE = re.compile(
    r"^-\s*\[(?P<ts>[^\]]+)\]\s*agent=(?P<id>\S+)"
    r"(?:\s+model=(?P<model>\S+))?(?:\s+bytes=(?P<bytes>\S+))?"
    r"\s*\|\s*last:\s*(?P<last>.*?)\s*\|\s*transcript:\s*(?P<tp>\S+)"
    r"(?:\s*\|\s*brief:\s*(?P<brief>\S+))?\s*$")
SPEND_RE = re.compile(
    r"^\[(?P<ts>[^\]]+)\]\s+lane=(?P<lane>\S+)\s+model=(?P<model>\S+)\s+"
    r"tokens=(?P<tokens>\S+)\s+grade=(?P<grade>\S+)\s+"
    r'purpose="(?P<purpose>.*?)"(?:\s+agent=(?P<agent>\S+))?\s*$')
SPEND_LOOSE = re.compile(r"^\[(?P<ts>[^\]]+)\]\s+(?P<body>.+)$")

RULING_RE = re.compile(
    r"owner ruling|owner-set|owner correction|owner-ratified|ratified|"
    r"\bdo NOT\b|\bnever\b .*\blaw\b|standing order|HARD RULE|policy set", re.I)
SHIP_RE = re.compile(r"\bv\d+\.\d+\.\d+\b|\breleas(e|ed)\b|\bshipped\b|\bdeploy(ed)?\b", re.I)
OPEN_RE = re.compile(
    r"\bin progress\b|\bPENDING\b|\bparked\b|\buntested\b|\bpapercut\b|"
    r"\bTODO\b|\bnot yet\b|\bstill owing\b|\bopen thread\b", re.I)
REVERSAL_RE = re.compile(
    r"\breversed?\b|\breverted?\b|\bcorrect(ed|ion)\b|\bundo(ne)?\b|\bsupersed(e|ed|es)\b|"
    r"\brolled back\b|\bwithdrawn\b", re.I)
# A path only counts as a pointer when it has a directory component — a bare
# `README.md` in prose is a word, not a citation, and flagging it DEAD is noise.
PATHY_RE = re.compile(
    r"(?<![\w./-])((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"
    r"\.(?:md|html|py|sh|json|jsonl|txt|ya?ml|css|js))(?![\w/])")


def coord_volumes(root):
    """The COORD ledger ROLLS, it does not compact: `COORD.md` is the active
    volume and sealed ones are `COORD-<NNN>.md`. `COORD-ARCHIVE.md` is the
    retired compaction scheme, still read so older repos keep their history.

    Returns (walked, skipped) — skipped names any other `COORD-*.md` (a lane
    blackboard, say) so the inventory can SAY it was not walked instead of the
    reader assuming it was.
    """
    sealed, skipped = [], []
    for p in sorted(root.glob("COORD-*.md")):
        stem = p.stem
        tail = stem.split("-")[-1]
        if stem.count("-") == 1 and tail.isdigit():
            sealed.append(p.name)
        elif p.name not in ("COORD-ARCHIVE.md", "COORD-AGENTS.md",
                            "COORD-AGENTS-ARCHIVE.md"):
            skipped.append(p.name)
    walked = [f for f in ["COORD-ARCHIVE.md"] if (root / f).exists()]
    walked += sorted(sealed)
    if (root / "COORD.md").exists():
        walked.append("COORD.md")
    return walked, sorted(skipped)


def classify_coord(body):
    """One primary kind plus flags. A line can be a ruling AND an open thread;
    collapsing that into a single label loses the half the recap needs."""
    flags = []
    if OPEN_RE.search(body):
        flags.append("open-thread")
    if REVERSAL_RE.search(body):
        flags.append("reversal")
    if RULING_RE.search(body):
        return "ruling", flags
    if SHIP_RE.search(body):
        return "ship", flags
    return "decision", flags


def split_coord(body):
    """`ask -> landed | evidence: ...` — the ledger's own three-part shape, which
    is exactly the title/summary split the decision map wants."""
    ev = re.split(r"\s\|\s*evidence:\s*", body, maxsplit=1)
    main = ev[0]
    parts = re.split(r"\s->\s|\s→\s", main, maxsplit=1)
    ask = parts[0].strip()
    landed = parts[1].strip() if len(parts) > 1 else ""
    return ask, landed


def monotone_epochs(entries):
    """S81: make the ORDER key non-decreasing within each source. Returns how many moved.

    ⛔ AN APPEND-ONLY FILE'S TRUE ORDER IS CARRIED BY POSITION; ITS STAMPS ASSERT AN ORDER
    THAT CAN CONTRADICT IT. A wrong stamp cannot reorder the file -- it can only mislead a
    reader who sorts by it. This module's own docstring already warned that it "sorts a
    store record after a COORD line it preceded."

    ONE bound: MONOTONE within each source — an entry never orders before one it
    positionally follows. Ties fall through to `seq`, which is that position.

    ⛔ NO WALL CLOCK. The first cut of this also bounded stamps at the current instant —
    doctor's upper-bound shape — and recap's own fixture caught it: "no subcommand reads the
    wall clock" went from 100/0 to 99/1. THIS MODULE IS DETERMINISTIC BY RULE, and reading
    the clock makes its output depend on when you ran it. The monotone bound needs no clock
    and closes the demonstrated inversion on its own, so the clock went, not the rule.

    (That arm greps this file for the clock-call spellings, so it matches them in PROSE as
    well as in code — naming the function in this comment was enough to fail it. Reported
    to the Director: it is the mention-versus-invocation defect this very lane is repairing,
    sitting in the arm that guards against it.)

    COST, STATED: a future-stamped entry drags the EFFECTIVE key of the entries after it in
    its own source up to its value, so those sort late against other sources. Within-source
    order — the append-only truth — is exact; cross-source placement of the infected tail is
    not. That is a worse cross-source answer than a clock would give and a better rule.

    ⛔ WHAT THIS DOES NOT FIX, STATED RATHER THAN LEFT FOR A READER: order ACROSS sources
    is still stamp-derived, because position across separate files does not exist. A
    cross-source inversion between two honestly-stamped entries is not recoverable here,
    and this function does not pretend to recover it.
    """
    bysrc = {}
    for e in entries:
        bysrc.setdefault(e.source, []).append(e)
    moved = 0
    for group in bysrc.values():
        group.sort(key=lambda e: e.seq)
        run = None
        for e in group:
            ep = e.epoch
            if ep is None:
                e.eff_epoch = run
                continue
            if run is not None and ep < run:
                e.eff_epoch = run
                moved += 1
            else:
                e.eff_epoch = ep
                run = ep
    return moved


def read_coord(root, inv):
    entries = []
    walked, skipped = coord_volumes(root)
    for name in skipped:
        # Named in the inventory precisely BECAUSE it was not walked — a reader
        # who sees `COORD-*.md` on disk and no row would assume it was.
        inv.append({"source": name, "path": name, "present": True,
                    "entries": 0, "malformed": 0, "first": "", "last": "",
                    "note": "NOT WALKED — not a numbered volume (lane blackboard "
                            "or unknown COORD-*.md)"})
    if not walked:
        inv.append({"source": "COORD.md", "path": "COORD.md", "present": False,
                    "entries": 0, "malformed": 0, "first": "", "last": "",
                    "note": "ABSENT — the intent layer is missing from this recap, not empty"})
        return entries
    seq = 0
    for fn in walked:
        text = read_text(root / fn)
        if text is None:
            continue
        n = bad = 0
        first = last = ""
        for i, line in enumerate(text.splitlines(), 1):
            line = line.rstrip()
            if not line.startswith("- ["):
                continue
            m = COORD_RE.match(line.strip())
            ts = parse_ts(m.group("ts")) if m else None
            if not m or not ts:
                bad += 1
                continue
            body = m.group("body")
            kind, flags = classify_coord(body)
            ask, landed = split_coord(body)
            paths = []
            for raw in PATHY_RE.findall(body)[:MAX_PATHS_PER_LINE]:
                if "://" in body[max(0, body.find(raw) - 8): body.find(raw)]:
                    continue
                paths.append(check_path(root, raw))
            if any(not p["exists"] for p in paths):
                flags = flags + ["dead-pointer"]
            seq += 1
            n += 1
            first = first or m.group("ts").strip()
            last = m.group("ts").strip()
            entries.append(Entry(
                ts=m.group("ts").strip(), iso=ts[0], epoch=ts[1], source="coord",
                kind=kind, ref="%s:%d" % (fn, i), eid="",
                cite="[COORD %s]" % m.group("ts").strip(),
                text=line.strip(), head=body, title=ask, summary=landed,
                flags=flags + (["lane:%s" % m.group("lane")] if m.group("lane") else []),
                paths=paths, seq=seq))
        inv.append({"source": fn, "path": fn, "present": True, "entries": n,
                    "malformed": bad, "first": first, "last": last,
                    "note": ("active volume" if fn == "COORD.md" else
                             "legacy compaction scheme (pre-volume)" if fn == "COORD-ARCHIVE.md"
                             else "sealed volume")})
    return entries


def read_agents(root, inv):
    entries = []
    files = [f for f in ("COORD-AGENTS-ARCHIVE.md", "COORD-AGENTS.md")
             if (root / f).exists()]
    if not files:
        inv.append({"source": "COORD-AGENTS.md", "path": "COORD-AGENTS.md",
                    "present": False, "entries": 0, "malformed": 0,
                    "first": "", "last": "",
                    "note": "ABSENT — who was consulted is unrecorded, not zero"})
        return entries
    seq = 0
    for fn in files:
        text = read_text(root / fn) or ""
        n = bad = 0
        first = last = ""
        for i, line in enumerate(text.splitlines(), 1):
            line = line.rstrip()
            if not line.startswith("- ["):
                continue
            m = AGENT_RE.match(line.strip())
            ts = parse_ts(m.group("ts")) if m else None
            if not m or not ts:
                bad += 1
                continue
            aid, tp = m.group("id"), m.group("tp")
            last_txt = (m.group("last") or "").strip()
            flags = []
            paths = [check_path(root, tp)]
            # The hook fires before the transcript is flushed, so `last: ?` is
            # common; the sibling meta.json carries the lane's own description
            # and fills the gap the hook left.
            meta = pathlib.Path(tp).with_suffix("").as_posix() + ".meta.json"
            mp = check_path(root, meta)
            if last_txt in ("", "?"):
                flags.append("thin")
                if mp["exists"]:
                    try:
                        j = json.loads(read_text(pathlib.Path(mp["abs"])) or "{}")
                        d = collapse(j.get("description") or "")
                        if d:
                            last_txt = d
                            flags.append("from-meta")
                    except Exception:
                        pass
                paths.append(mp)
            if m.group("brief"):
                paths.append(check_path(root, m.group("brief")))
            alive = paths[0]["exists"]
            if not alive:
                flags.append("dead-pointer")
            if not last_txt or last_txt == "?":
                last_txt = "(no last-line recorded and no meta.json — conclusion unrecoverable)"
                if "unrecoverable" not in flags:
                    flags.append("unrecoverable")
            seq += 1
            n += 1
            first = first or m.group("ts").strip()
            last = m.group("ts").strip()
            model = m.group("model") or "?"
            entries.append(Entry(
                ts=m.group("ts").strip(), iso=ts[0], epoch=ts[1], source="agents",
                kind="consult", ref="%s:%d" % (fn, i), eid=aid,
                cite=("[COORD-AGENTS %s → transcript]" % aid) if alive
                     else ("[COORD-AGENTS %s — transcript missing]" % aid),
                text=line.strip(), head="%s model=%s | %s" % (aid, model, last_txt),
                title="agent %s (%s)" % (aid, model),
                summary=last_txt, flags=flags, paths=paths, seq=seq))
        inv.append({"source": fn, "path": fn, "present": True, "entries": n,
                    "malformed": bad, "first": first, "last": last,
                    "note": "machine-written by the SubagentStop hook"})
    return entries


def read_spend(root, inv):
    entries = []
    rel = "spend/ledger.md"
    text = read_text(root / "spend" / "ledger.md")
    if text is None:
        inv.append({"source": rel, "path": rel, "present": False, "entries": 0,
                    "malformed": 0, "first": "", "last": "",
                    "note": "ABSENT — costs are absent from this recap, not zero"})
        return entries
    n = bad = 0
    first = last = ""
    seq = 0
    for i, line in enumerate(text.splitlines(), 1):
        line = line.rstrip()
        if not line.startswith("["):
            continue
        m = SPEND_RE.match(line.strip())
        flags = []
        if m:
            ts = parse_ts(m.group("ts"))
            purpose = collapse(m.group("purpose"))
            title = "%s %s" % (m.group("model"), m.group("tokens"))
            aid = m.group("agent") or ""
        else:
            lm = SPEND_LOOSE.match(line.strip())
            ts = parse_ts(lm.group("ts")) if lm else None
            if not lm or not ts:
                bad += 1
                continue
            # Timestamped but off-shape: kept, and SAID to be off-shape. A cost
            # line that vanishes because a field moved is a silent hole in the
            # one section of a recap nobody can reconstruct from memory.
            purpose = collapse(lm.group("body"))
            title = "(unparsed spend fields)"
            aid = ""
            flags.append("unparsed-fields")
        seq += 1
        n += 1
        first = first or (m or lm).group("ts").strip()
        last = (m or lm).group("ts").strip()
        entries.append(Entry(
            ts=last, iso=ts[0], epoch=ts[1], source="spend", kind="cost",
            ref="%s:%d" % (rel, i), eid=aid, cite="[spend %s]" % last,
            text=line.strip(), head="%s | %s" % (title, purpose),
            title=title, summary=purpose, flags=flags, seq=seq))
    inv.append({"source": rel, "path": rel, "present": True, "entries": n,
                "malformed": bad, "first": first, "last": last,
                "note": "append-only via spend.py"})
    return entries


def read_findings(root, inv):
    entries = []
    rel = "archive/findings.jsonl"
    text = read_text(root / "archive" / "findings.jsonl")
    if text is None:
        inv.append({"source": rel, "path": rel, "present": False, "entries": 0,
                    "malformed": 0, "first": "", "last": "",
                    "note": "ABSENT — no findings store; the reasoned layer is missing"})
        return entries
    n = bad = 0
    first = last = ""
    seq = 0
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if not isinstance(rec, dict):
                raise ValueError("not an object")
        except Exception:
            bad += 1
            continue
        ts = parse_ts(rec.get("ts"))
        if not ts:
            bad += 1
            continue
        rid = str(rec.get("id") or "F-?")
        status = str(rec.get("status") or "live")
        flags = []
        if status != "live":
            flags.append(status)          # superseded / refuted — the trail's own reversal
        paths = []
        for ev in (rec.get("evidence") or []):
            if isinstance(ev, dict) and ev.get("type") == "path" and ev.get("ref"):
                paths.append(check_path(root, ev["ref"]))
        if any(not p["exists"] for p in paths):
            flags.append("dead-pointer")
        links = [str(x) for x in (rec.get("links") or [])]
        if links:
            flags.append("links:" + ",".join(links))
        seq += 1
        n += 1
        raw_ts = str(rec.get("ts")).strip()
        first = first or raw_ts
        last = raw_ts
        entries.append(Entry(
            ts=raw_ts, iso=ts[0], epoch=ts[1], source="findings", kind="finding",
            ref="%s:%d" % (rel, i), eid=rid, cite="[%s]" % rid,
            text=collapse(rec.get("statement")),
            title="%s (%s/%s)" % (rid, rec.get("kind") or "?", status),
            summary=collapse(rec.get("statement")),
            flags=flags + ["skill:%s" % (rec.get("skill") or "?")],
            paths=paths, seq=seq))
    inv.append({"source": rel, "path": rel, "present": True, "entries": n,
                "malformed": bad, "first": first, "last": last,
                "note": "validated at the door by archivist/index.py; cite by id"})
    return entries


def read_git(root, inv):
    """Author epoch + subject. `%at` is timezone-independent, so no TZ variable
    can silently reorder the story."""
    entries = []
    try:
        probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-dir"],
                               capture_output=True, text=True, timeout=20)
        if probe.returncode != 0:
            raise RuntimeError("not a git repo")
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--no-color",
             "--pretty=format:%h%x1f%at%x1f%s"],
            capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise RuntimeError(collapse(out.stderr)[:80] or "git log failed")
    except Exception as exc:
        inv.append({"source": "git", "path": ".git", "present": False, "entries": 0,
                    "malformed": 0, "first": "", "last": "",
                    "note": "ABSENT — %s; ships are unrecorded here" % (exc,)})
        return entries
    n = bad = 0
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3 or not parts[1].strip().isdigit():
            if line.strip():
                bad += 1
            continue
        sha, at, subj = parts[0].strip(), int(parts[1]), parts[2]
        rows.append((at, sha, subj))
    # git prints newest-first; number the seq oldest-first so a same-second pair
    # keeps its commit order in the merged stream.
    rows.sort(key=lambda r: -r[0])
    for seq, (at, sha, subj) in enumerate(reversed(rows), 1):
        kind = "ship" if re.search(r"\bv\d+\.\d+\.\d+\b", subj) else "commit"
        n += 1
        entries.append(Entry(
            ts=epoch_to_coord(at),
            iso=datetime.fromtimestamp(at, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            epoch=at, source="git", kind=kind, ref=sha, eid=sha,
            cite="[commit %s]" % sha, text="%s %s" % (sha, collapse(subj)),
            head=collapse(subj), title=collapse(subj), summary="", seq=seq))
    firsts = sorted(e.ts for e in entries)
    inv.append({"source": "git", "path": ".git", "present": True, "entries": n,
                "malformed": bad,
                "first": firsts[0] if firsts else "", "last": firsts[-1] if firsts else "",
                "note": "author epoch (%at) formatted to UTC here — no TZ dependency"})
    return entries


# ── the extras: present/absent only, they carry no timestamps ─────────────────
EXTRA_FILES = ("oracle-index.md", "START-HERE.md", "HANDOFF.md", "STATE.md",
               "CHANGELOG.md", "README.md", "CLAUDE.md")
DOSSIER_DIRS = ("research", "market-research", "understanding", "decision",
                "factcheck", "critique", "action-plan", "runbook", "pipeline",
                "introspection", "recap", "briefs", "watch", "graph", "compile")


def read_extras(root):
    out = []
    for f in EXTRA_FILES:
        out.append({"name": f, "kind": "file", "present": (root / f).exists(), "count": 0})
    for d in DOSSIER_DIRS:
        p = root / d
        if p.is_dir():
            try:
                c = sum(1 for x in p.rglob("*") if x.is_file())
            except OSError:
                c = 0
            out.append({"name": d + "/", "kind": "dir", "present": True, "count": c})
        else:
            out.append({"name": d + "/", "kind": "dir", "present": False, "count": 0})
    return out


# ── the walk ──────────────────────────────────────────────────────────────────
def load(root):
    inv = []
    entries = []
    entries += read_coord(root, inv)
    entries += read_agents(root, inv)
    entries += read_git(root, inv)
    entries += read_spend(root, inv)
    entries += read_findings(root, inv)
    clamped = monotone_epochs(entries)
    if clamped:
        inv.append({"source": "STAMP-ORDER", "path": "-", "present": True,
                    "note": ("%d entr(y/ies) carry a stamp that contradicts their position in an "
                             "append-only source; ordered by position and DISCLOSED here, never "
                             "silently re-stamped" % clamped)})
    entries.sort(key=lambda e: e.sortkey)
    return entries, inv, read_extras(root)


def window(entries, since, until):
    lo = parse_ts(since) if since else None
    hi = parse_ts(until, end_of_day=True) if until else None
    if since and not lo:
        die("unparseable --since %r (use YYYY-MM-DD, 'YYYY-MM-DD HH:MMZ' or ISO8601Z)" % since)
    if until and not hi:
        die("unparseable --until %r (use YYYY-MM-DD, 'YYYY-MM-DD HH:MMZ' or ISO8601Z)" % until)
    out = [e for e in entries
           if (lo is None or e.epoch >= lo[1]) and (hi is None or e.epoch <= hi[1])]
    return out, (lo[0] if lo else None), (hi[0] if hi else None)


def die(msg, code=2):
    sys.stderr.write("walk.py: %s\n" % msg)
    sys.exit(code)


def source_counts(entries):
    c = defaultdict(int)
    for e in entries:
        c[e.source] += 1
    return dict(c)


def emit_inventory(w, inv, extras, entries, all_entries):
    w("## ESTATE INVENTORY  (recap Step 1 — every source named, present or not)")
    w("source | present | entries | malformed | first | last | note")
    for r in inv:
        w("%s | %s | %d | %d | %s | %s | %s" % (
            r["source"], "yes" if r["present"] else "NO", r["entries"],
            r["malformed"], r["first"] or "-", r["last"] or "-", r["note"]))
    present = [x["name"] for x in extras if x["present"] and x["kind"] == "file"]
    absent = [x["name"] for x in extras if not x["present"] and x["kind"] == "file"]
    dpres = ["%s(%d)" % (x["name"], x["count"]) for x in extras
             if x["present"] and x["kind"] == "dir"]
    w("")
    w("extras present: %s" % (", ".join(present) or "none"))
    w("extras ABSENT:  %s" % (", ".join(absent) or "none"))
    w("dossier dirs:   %s" % (", ".join(dpres) or "none"))
    w("")


def cmd_walk(args):
    root = pathlib.Path(args.root).resolve()
    all_entries, inv, extras = load(root)
    if not all_entries:
        sys.stderr.write("walk.py: the estate is empty — no COORD volume, agent ledger, "
                         "git history, spend ledger or findings store under %s\n" % root)
        return 3
    entries, lo, hi = window(all_entries, args.since, args.until)
    dead = [(e, p) for e in entries for p in e.dead]

    if args.json:
        print(json.dumps({
            "tool": "walk.py", "subcommand": "walk", "root": str(root),
            "window": {"since": lo, "until": hi,
                       "first": entries[0].iso if entries else None,
                       "last": entries[-1].iso if entries else None,
                       "estate_first": all_entries[0].iso,
                       "estate_last": all_entries[-1].iso},
            "inventory": inv, "extras": extras,
            "counts": source_counts(entries),
            "totals": {"entries": len(entries), "estate_entries": len(all_entries),
                       "dead_pointers": len(dead),
                       "malformed": sum(r["malformed"] for r in inv)},
            "entries": [e.as_dict(args.head) for e in entries],
        }, indent=2, ensure_ascii=False, sort_keys=False))
        return 0

    out = []
    w = out.append
    w("# recap walk — %s" % root)
    w("# the script walked; the model narrates. Every line below carries the citation")
    w("# token recap should print. Merged on the INSTANT, printed in each source's own shape.")
    w("")
    emit_inventory(w, inv, extras, entries, all_entries)
    w("## WINDOW")
    w("requested: since=%s until=%s" % (args.since or "(estate start)", args.until or "(estate end)"))
    w("estate:    %s -> %s (%d entries)" % (all_entries[0].ts, all_entries[-1].ts, len(all_entries)))
    if entries:
        w("walked:    %s -> %s (%d entries)" % (entries[0].ts, entries[-1].ts, len(entries)))
    else:
        w("walked:    EMPTY — the window excludes every recorded entry; the estate is not empty")
    w("")
    w("## THE WALK — %d entries in timestamp order" % len(entries))
    w("# ts | source | kind | cite | ref | head        (!! DEAD: = an emitted pointer that is gone)")
    for e in entries:
        flags = [f for f in e.flags if not f.startswith(("lane:", "skill:", "links:"))]
        line = "%s | %s | %s%s | %s | %s | %s" % (
            e.ts, e.source, e.kind,
            ("+" + ",".join(flags)) if flags else "",
            e.cite, e.ref, trunc(e.head, args.head))
        for p in e.dead:
            line += "  !! DEAD: %s" % p["ref"]
        w(line)
    w("")
    w("## SUMMARY")
    w("entries=%d  dead-pointers=%d  malformed-lines=%d" % (
        len(entries), len(dead), sum(r["malformed"] for r in inv)))
    w("per source: %s" % (", ".join("%s=%d" % kv for kv in sorted(source_counts(entries).items()))
                          or "none"))
    if dead:
        w("dead pointers (a ledger line is an index, not a source):")
        for e, p in dead:
            w("  %s %s -> %s" % (e.cite, e.ref, p["ref"]))
    print("\n".join(out))
    return 0


# ── spans ─────────────────────────────────────────────────────────────────────
def sessions(entries, gap_minutes):
    """A session is a run of entries with no silence longer than --gap. This is
    the shape a narrator actually needs: beats cluster by sitting, not by date,
    and a day boundary cuts a 03:00Z session in half."""
    out = []
    cur = []
    gap = gap_minutes * 60
    for e in entries:
        if cur and (e.epoch - cur[-1].epoch) > gap:
            out.append(cur)
            cur = []
        cur.append(e)
    if cur:
        out.append(cur)
    return out


def cmd_spans(args):
    root = pathlib.Path(args.root).resolve()
    all_entries, inv, extras = load(root)
    if not all_entries:
        sys.stderr.write("walk.py: the estate is empty — nothing to span under %s\n" % root)
        return 3
    entries, lo, hi = window(all_entries, args.since, args.until)

    per_source = {}
    for e in entries:
        s = per_source.setdefault(e.source, {"count": 0, "first": e.ts, "last": e.ts,
                                             "first_iso": e.iso, "last_iso": e.iso})
        s["count"] += 1
        s["last"] = e.ts
        s["last_iso"] = e.iso

    days = {}
    for e in entries:
        d = days.setdefault(epoch_to_day(e.epoch), {"total": 0, "sources": defaultdict(int)})
        d["total"] += 1
        d["sources"][e.source] += 1

    sess = sessions(entries, args.gap)
    sess_rows = []
    for i, grp in enumerate(sess, 1):
        counts = source_counts(grp)
        mins = int(round((grp[-1].epoch - grp[0].epoch) / 60.0))
        headline = next((x for x in grp if x.kind in ("ruling", "ship")), grp[0])
        sess_rows.append({
            "n": i, "start": grp[0].ts, "end": grp[-1].ts,
            "start_iso": grp[0].iso, "end_iso": grp[-1].iso,
            "minutes": mins, "entries": len(grp), "counts": counts,
            "anchor_kind": headline.kind, "anchor_cite": headline.cite,
            "anchor": trunc(headline.head, 110)})

    if args.json:
        print(json.dumps({
            "tool": "walk.py", "subcommand": "spans", "root": str(root),
            "window": {"since": lo, "until": hi,
                       "first": entries[0].iso if entries else None,
                       "last": entries[-1].iso if entries else None},
            "gap_minutes": args.gap,
            "totals": {"entries": len(entries), "days": len(days), "sessions": len(sess_rows)},
            "per_source": per_source,
            "per_day": [{"day": d, "total": v["total"], "sources": dict(v["sources"])}
                        for d, v in sorted(days.items())],
            "sessions": sess_rows,
        }, indent=2, ensure_ascii=False))
        return 0

    out = []
    w = out.append
    w("# recap spans — %s" % root)
    if not entries:
        w("EMPTY WINDOW — the estate holds %d entries (%s -> %s) but none inside the window."
          % (len(all_entries), all_entries[0].ts, all_entries[-1].ts))
        print("\n".join(out))
        return 0
    w("span: %s -> %s   (%d entries, %d days, %d sessions at a %d-minute gap)"
      % (entries[0].ts, entries[-1].ts, len(entries), len(days), len(sess_rows), args.gap))
    w("")
    w("## PER SOURCE")
    w("source | entries | first | last")
    for s in sorted(per_source):
        v = per_source[s]
        w("%s | %d | %s | %s" % (s, v["count"], v["first"], v["last"]))
    w("")
    w("## PER DAY (UTC)")
    w("day | entries | breakdown")
    for d in sorted(days):
        v = days[d]
        w("%s | %d | %s" % (d, v["total"],
                            " ".join("%s=%d" % kv for kv in sorted(v["sources"].items()))))
    w("")
    w("## SESSIONS (a run with no silence longer than %d min)" % args.gap)
    w("# | start | end | min | entries | breakdown | anchor")
    for r in sess_rows:
        w("%d | %s | %s | %d | %d | %s | %s %s" % (
            r["n"], r["start"], r["end"], r["minutes"], r["entries"],
            " ".join("%s=%d" % kv for kv in sorted(r["counts"].items())),
            r["anchor_cite"], r["anchor"]))
    print("\n".join(out))
    return 0


# ── prefill ───────────────────────────────────────────────────────────────────
def js_str(s):
    """A JS string literal. JSON strings are valid JS strings with two
    exceptions that matter inside a <script> block: `</` ends the element, and
    U+2028/9 are line terminators in JS but not in JSON."""
    t = json.dumps(str(s or ""), ensure_ascii=False)
    return (t.replace("</", "<\\/")
             .replace(LS, "\\u2028")
             .replace(PS, "\\u2029"))


def node_kind(e):
    """Map a walk entry onto one of the template's four lanes, or None.

    A findings record lands in `consult`: it is what a lane CONCLUDED, and the
    template's four lanes have no fifth. Its citation still carries `type:
    "finding"`, which the template renders by falling back to the raw type name.
    """
    if e.source == "coord":
        return e.kind if e.kind in ("ruling", "ship", "decision") else "decision"
    if e.source == "git":
        return "ship" if e.kind == "ship" else None
    if e.source == "agents":
        return None if ("unrecoverable" in e.flags) else "consult"
    if e.source == "findings":
        return "consult"
    return None          # spend lines are cost fabric, cited in beats, not nodes


def cite_for(e, root):
    if e.source == "coord":
        return {"type": "coord", "text": e.text}
    if e.source == "git":
        return {"type": "commit", "text": e.text}
    if e.source == "spend":
        return {"type": "spend", "text": e.text}
    if e.source == "agents":
        p = e.paths[0] if e.paths else {"ref": "", "exists": False}
        return {"type": "transcript", "text": p["ref"],
                "note": "verified present" if p["exists"] else "MISSING — dead pointer"}
    return {"type": "finding", "text": "%s — %s" % (e.eid, trunc(e.text, STATEMENT_HEAD)),
            "note": "archive/findings.jsonl"}


def cmd_prefill(args):
    root = pathlib.Path(args.root).resolve()
    all_entries, inv, extras = load(root)
    if not all_entries:
        sys.stderr.write("walk.py: the estate is empty — nothing to pre-fill under %s\n" % root)
        return 3
    entries, lo, hi = window(all_entries, args.since, args.until)

    cands = [(e, node_kind(e)) for e in entries]
    cands = [(e, k) for e, k in cands if k]
    dropped_thin = sum(1 for e in entries
                       if e.source == "agents" and "unrecoverable" in e.flags)
    kept = sorted(cands, key=lambda ek: (NODE_PRIORITY[ek[1]], ek[0].sortkey))
    over = max(0, len(kept) - args.max_nodes)
    kept = kept[: args.max_nodes]
    kept.sort(key=lambda ek: ek[0].sortkey)

    if args.now:
        n = parse_ts(args.now)
        if not n:
            die("unparseable --now %r" % args.now)
        generated = n[0][:10]
    elif entries:
        generated = entries[-1].iso[:10]
    else:
        generated = all_entries[-1].iso[:10]

    project = args.project or root.name
    if entries:
        win = "%s → %s" % (entries[0].ts, entries[-1].ts)
    else:
        win = "EMPTY WINDOW — estate spans %s → %s" % (all_entries[0].ts, all_entries[-1].ts)

    sources = []
    for r in inv:
        if not r["present"] or r["entries"] == 0:
            continue
        unit = {"git": "commits"}.get(r["source"], "entries")
        sources.append("%s (%d %s)" % (r["source"], r["entries"], unit))
    dc = sum(1 for e, _k in kept if e.dead)

    L = []
    a = L.append
    a("/* ============================ RECAP_DATA — REPLACE THIS BLOCK ============================")
    a("   MACHINE-PREFILLED by recap/scripts/walk.py — nodes, ts and cites are derived from the")
    a("   estate and are already verbatim; do not retype them.")
    a("   The MODEL still owns three things:")
    a("     1. edges  — only ones the trail supports (see the empty array below),")
    a("     2. title  — each is the ledger's own ask, cut to length; rewrite into a phrase,")
    a("     3. summary— each is the ledger's own 'landed' half; rewrite into the beat.")
    a("   kind:  ruling | decision | consult | ship   (a findings record maps to `consult` —")
    a("          it is what a lane concluded, and the template has no fifth lane)")
    a("   flag:  \"\" | \"unverified\" | \"inferred\"   ·  cites type: coord|commit|transcript|spend|")
    a("          dossier|note|finding (unknown types render as their raw name — no template edit)")
    a("   ts:    VERBATIM from the trail. Never reformat, never re-timezone.")
    a("   prefill: %d node(s) from %d walked entr(ies)%s%s" % (
        len(kept), len(entries),
        ("; %d dropped by --max-nodes %d (kept by priority ruling>ship>decision>consult, "
         "then oldest first — raise --max-nodes to see them)" % (over, args.max_nodes)) if over else "",
        ("; %d agent line(s) excluded as unrecoverable (no last-line, no meta.json)"
         % dropped_thin) if dropped_thin else ""))
    a("   dead pointers among these nodes: %d — each carries note \"MISSING — dead pointer\"" % dc)
    a("========================================================================================= */")
    a("const RECAP_DATA = {")
    a("  project: %s," % js_str(project))
    a("  window:  %s," % js_str(win))
    a("  generated: %s," % js_str(generated))
    a("  sources: [%s]," % ", ".join(js_str(s) for s in sources))
    a("  nodes: [")
    for i, (e, k) in enumerate(kept, 1):
        c = cite_for(e, root)
        flag = "unverified" if (e.source == "agents" and e.dead) else ""
        title = trunc(e.title or e.head, 90)
        summary = trunc(e.summary or "", 220)
        a("    { id:%s, ts:%s, kind:%s," % (js_str("n%d" % i), js_str(e.ts), js_str(k)))
        a("      title:%s," % js_str(title))
        a("      summary:%s," % js_str(summary))
        note = (", note:%s" % js_str(c["note"])) if c.get("note") else ""
        a("      cites:[{type:%s, text:%s%s}]," % (js_str(c["type"]), js_str(c["text"]), note))
        a("      flag:%s, ref:%s }%s" % (js_str(flag), js_str(e.ref),
                                         "," if i < len(kept) else ""))
    a("  ],")
    a("  edges: [")
    a("    /* MODEL FILLS THIS. One edge per link the TRAIL supports — an evidence line that")
    a("       names the other node, a commit that fixes a named finding, a consultation whose")
    a("       conclusion appears in the next decision. Anything else needs inferred:true.")
    a("       { from:\"n1\", to:\"n2\", rel:\"led-to\", why:\"<the trail line that justifies it>\" }")
    a("       rel: led-to | informed-by | reversed */")
    a("  ]")
    a("};")
    text = "\n".join(L) + "\n"

    if args.out in (None, "-"):
        sys.stdout.write(text)
    else:
        p = pathlib.Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print("wrote %s (%d nodes, %d entries walked)" % (p, len(kept), len(entries)))
    return 0


# ── cli ───────────────────────────────────────────────────────────────────────
def main(argv):
    ap = argparse.ArgumentParser(
        prog="walk.py",
        description="recap's estate walker — one timestamp-sorted stream, zero model tokens.",
        epilog="exit: 0 ok · 2 usage · 3 the estate is empty")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--root", default=".", help="estate root (default: .)")
        p.add_argument("--since", help="ISO date/timestamp, inclusive")
        p.add_argument("--until", help="ISO date/timestamp, inclusive (a bare date = end of day)")
        p.add_argument("--json", action="store_true", help="machine-readable output")

    w = sub.add_parser("walk", help="the merged, timestamp-ordered stream + estate inventory")
    common(w)
    w.add_argument("--head", type=int, default=HEAD_DEFAULT,
                   help="truncate each head at N chars (0 = never truncate)")

    s = sub.add_parser("spans", help="per-source / per-day / per-session spans and counts")
    common(s)
    s.add_argument("--gap", type=int, default=GAP_DEFAULT,
                   help="minutes of silence that end a session (default %d)" % GAP_DEFAULT)

    p = sub.add_parser("prefill", help="the RECAP_DATA block, nodes + cites pre-filled")
    common(p)
    p.add_argument("--out", default="-", help="output path, or - for stdout (default)")
    p.add_argument("--project", help="project name (default: the root directory's name)")
    p.add_argument("--max-nodes", type=int, default=MAX_NODES_DEFAULT,
                   help="cap the node count (default %d); drops are reported in the block"
                        % MAX_NODES_DEFAULT)
    p.add_argument("--now", help="ISO timestamp for `generated` (the ONLY clock input; "
                                 "default = the date of the newest walked entry)")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help(sys.stderr)
        return 2
    root = pathlib.Path(args.root)
    if not root.is_dir():
        die("--root %s is not a directory" % args.root)
    return {"walk": cmd_walk, "spans": cmd_spans, "prefill": cmd_prefill}[args.cmd](args)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        os._exit(0)
    except KeyboardInterrupt:
        sys.exit(130)
