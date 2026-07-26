#!/usr/bin/env python3
"""index.py — archivist: the findings store, plus the legacy dossier index.

The store is `archive/findings.jsonl` (repo-root relative): one JSON record per
line, APPEND-ONLY, written under an exclusive flock. Nothing is ever edited in
place — a status flip is a NEW tombstone record, and `track` resolves the
effective status by walking links.

Subcommands:
  add        validate one finding record at the door and append it; prints its id
  track      print the session track in ts order (--json for machines); a live record
             whose links name an effectively-refuted id carries RESTS-ON-REFUTED
  supersede  append a tombstone flipping a record to superseded
  refute     append a tombstone flipping a record to refuted, with evidence
  scan       rebuild oracle-index.md from every *Dossier.md found (legacy estate)
  find       search findings statements + index entries + dossier bodies

The index and the store are finding aids, never sources — cite the evidence ref.
Never hand-edit either one: re-run scan, or append a correcting record.
"""
import argparse
import fcntl
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------- legacy index
DIRS = ["research", "market-research", "understanding", "decision", "factcheck",
        "critique", "action-plan", "runbook", "pipeline", "introspection", "recap",
        "draft"]
INDEX = "oracle-index.md"
LEDGER = "COORD-AGENTS.md"  # the SubagentStop hook's agent activity ledger
CANDIDATES = "compile/candidates.md"       # compile.py's repeated-work table
CANDIDATES_DATA = "compile/candidates.json"

# A dossier's own date line beats the filesystem's mtime (a copy or a re-clone
# rewrites mtime; the document's date is what the document claims).
DATE_DECL_RE = re.compile(
    r"^[\s>*_#|-]*(?:\*\*)?\s*"
    r"(?:date|dated|generated|written|last\s+(?:updated|scan)|as\s+of|run(?:\s+on)?)"
    r"\b[^0-9\n]{0,24}(\d{4}-\d{2}-\d{2})", re.I | re.M)
DATE_BARE_RE = re.compile(r"^[\s>*_-]*(\d{4}-\d{2}-\d{2})\s*$", re.M)

# ---------------------------------------------------------------- the store
STORE = "archive/findings.jsonl"
FIELDS = ("id", "ts", "session", "skill", "kind", "ask", "statement",
          "evidence", "relation", "links", "status")
KINDS = ("finding", "result", "decision", "conflict", "backtrack", "side-route")
RELATIONS = ("toward", "lateral", "back")
STATUSES = ("live", "superseded", "refuted")
EV_TYPES = ("url", "path", "command", "coord-line")
EV_LABELS = ("cited", "estimate", "recall", "unverified", "model-opinion")
EVIDENCE_REQUIRED = ("finding", "result", "decision")
STR_FIELDS = ("ts", "session", "skill", "ask")

URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://[^\s/]+", re.I)
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
ID_RE = re.compile(r"^F-(\d+)$")
# The resolution grammar: a tombstone declares its flip in the statement HEAD and
# names its target in links. Both must hold, or the flip does not count.
TOMB_RE = re.compile(r"^(supersedes|refutes)\s+(F-\d+)\b", re.I)


class Reject(Exception):
    """A record turned away at the door. Carries the rule it broke."""

    def __init__(self, rule, detail):
        super().__init__("%s: %s" % (rule, detail))
        self.rule, self.detail = rule, detail


def now_z():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def die(rule, detail):
    """A turned-away record always names the rule it broke, and always exits 2."""
    sys.stderr.write("reject: %s — %s\n" % (rule, detail))
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# validation — the door
# ---------------------------------------------------------------------------
def validate(raw, known_ids):
    """Return a normalized record, or raise Reject naming the rule it broke."""
    if not isinstance(raw, dict):
        raise Reject("record-object", "record must be a JSON object, got %s"
                     % type(raw).__name__)
    unknown = [k for k in raw if k not in FIELDS]
    if unknown:
        raise Reject("unknown-field", "field(s) not in the schema: %s (schema: %s)"
                     % (", ".join(sorted(unknown)), ", ".join(FIELDS)))
    if "id" in raw:
        raise Reject("id-assigned", "id is assigned by the store, never by the caller")

    rec = {}
    for f in STR_FIELDS:
        v = raw.get(f, "")
        if v is None:
            v = ""
        if not isinstance(v, str):
            raise Reject("field-type", "%s must be a string, got %s" % (f, type(v).__name__))
        rec[f] = v.strip()
    rec["ts"] = rec["ts"] or now_z()
    if not TS_RE.match(rec["ts"]):
        raise Reject("ts-format", "ts must be ISO8601 Z (YYYY-MM-DDTHH:MM:SSZ), got %r"
                     % rec["ts"])

    stmt = raw.get("statement", "")
    if not isinstance(stmt, str) or not stmt.strip():
        raise Reject("statement-required", "statement is the finding — it cannot be empty")
    rec["statement"] = stmt.strip()

    kind = raw.get("kind")
    if kind not in KINDS:
        raise Reject("kind-enum", "kind %r outside %s" % (kind, list(KINDS)))
    rec["kind"] = kind

    relation = raw.get("relation", "toward")
    if relation not in RELATIONS:
        raise Reject("relation-enum", "relation %r outside %s" % (relation, list(RELATIONS)))
    rec["relation"] = relation

    status = raw.get("status", "live")
    if status not in STATUSES:
        raise Reject("status-enum", "status %r outside %s" % (status, list(STATUSES)))
    rec["status"] = status

    links = raw.get("links", [])
    if links is None:
        links = []
    if not isinstance(links, list) or any(not isinstance(x, str) for x in links):
        raise Reject("links-shape", "links must be a list of id strings")
    for lid in links:
        if lid not in known_ids:
            raise Reject("links-unknown", "links names %r — no such record in the store" % lid)
    rec["links"] = links

    ev = raw.get("evidence", [])
    if ev is None:
        ev = []
    if not isinstance(ev, list):
        raise Reject("evidence-shape", "evidence must be a list of {type, ref, label}")
    clean = []
    for item in ev:
        if not isinstance(item, dict):
            raise Reject("evidence-shape", "evidence item must be an object, got %s"
                         % type(item).__name__)
        extra = [k for k in item if k not in ("type", "ref", "label")]
        if extra:
            raise Reject("evidence-shape", "evidence item has field(s) %s — only type, ref, label"
                         % ", ".join(sorted(extra)))
        etype, ref, label = item.get("type"), item.get("ref"), item.get("label")
        if not isinstance(ref, str) or not ref.strip():
            raise Reject("evidence-shape", "evidence item needs a non-empty ref")
        if etype not in EV_TYPES:
            raise Reject("evidence-type-enum", "evidence type %r outside %s"
                         % (etype, list(EV_TYPES)))
        if label not in EV_LABELS:
            raise Reject("evidence-label-enum", "evidence label %r outside %s"
                         % (label, list(EV_LABELS)))
        if label == "cited" and etype == "url" and not URL_RE.match(ref.strip()):
            raise Reject("cited-url-needs-url",
                         "[cited] url evidence needs a real URL, got %r" % ref.strip())
        clean.append({"type": etype, "ref": ref.strip(), "label": label})
    if not clean and rec["kind"] in EVIDENCE_REQUIRED:
        raise Reject("evidence-required",
                     "kind=%s must carry at least one evidence item" % rec["kind"])
    rec["evidence"] = clean

    return {f: rec[f] for f in FIELDS if f in rec}


# ---------------------------------------------------------------------------
# store I/O
# ---------------------------------------------------------------------------
def parse_lines(text, source=""):
    """Parse JSONL, skipping blank lines. A corrupt line is loud, not silent."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            die("store-corrupt", "line %s%d is not JSON: %s" % (source and source + ":", n, exc))
    return out


def load_store(root):
    p = root / STORE
    if not p.is_file():
        return []
    return parse_lines(p.read_text(encoding="utf-8", errors="replace"), STORE)


def append_record(root, raw):
    """Validate under the lock (links are checked against what is really there),
    assign the next id, append one line. Returns the assigned id."""
    p = root / STORE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0)
            existing = parse_lines(fh.read(), STORE)
            known = {r.get("id") for r in existing}
            top = 0
            for r in existing:
                m = ID_RE.match(str(r.get("id", "")))
                if m:
                    top = max(top, int(m.group(1)))
            rec = validate(raw, known)
            rec["id"] = "F-%d" % (top + 1)
            ordered = {f: rec[f] for f in FIELDS if f in rec}
            fh.seek(0, os.SEEK_END)
            fh.write(json.dumps(ordered, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return rec["id"]


def sort_key(rec):
    m = ID_RE.match(str(rec.get("id", "")))
    return (rec.get("ts", ""), int(m.group(1)) if m else 0)


def resolve(records):
    """THE RESOLUTION RULE. The store is append-only, so no record's status is
    ever rewritten. A record's EFFECTIVE status is its own written status unless
    a later tombstone (a) names it in `links` and (b) opens its statement with
    `supersedes F-<id>` or `refutes F-<id>`. The last such tombstone in ts order
    wins. Returns {id: (effective_status, by_id_or_None)}."""
    eff = {r.get("id"): (r.get("status", "live"), None) for r in records}
    for r in sorted(records, key=sort_key):
        m = TOMB_RE.match(r.get("statement", "") or "")
        if not m:
            continue
        verb, target = m.group(1).lower(), m.group(2).upper()
        if target not in eff or target not in (r.get("links") or []):
            continue
        by = next((l for l in (r.get("links") or []) if l != target), r.get("id"))
        eff[target] = ("superseded" if verb == "supersedes" else "refuted", by)
    return eff


def rests_on_refuted(rec, eff):
    """THE RESTS-ON-REFUTED RULE. A record that is itself effectively LIVE, and whose
    `links` names an id whose EFFECTIVE status is `refuted`, is standing on ground the
    store has already knocked out — a live decision resting on a refuted finding. It is
    NOT flipped by this (only a tombstone flips a status); it is FLAGGED, so the reader
    sees the dependency the link-walk already knows about.

    Exactly one hop: the links this record itself declares, resolved through `resolve`.
    A record that is not effectively live is never flagged — a superseded record's
    footing is already reported by its own status. A tombstone does not rest on what it
    killed: the target of this record's own `supersedes`/`refutes` head is skipped.
    Returns the flagged ids in link order (possibly empty)."""
    if eff.get(rec.get("id"), (rec.get("status", "live"), None))[0] != "live":
        return []
    own = TOMB_RE.match(rec.get("statement", "") or "")
    killed = own.group(2).upper() if own else None
    out = []
    for lid in rec.get("links") or []:
        if lid == killed or lid in out:
            continue
        if eff.get(lid, (None, None))[0] == "refuted":
            out.append(lid)
    return out


def head(text, width=90):
    one = " ".join((text or "").split())
    return one if len(one) <= width else one[:width - 1] + "…"


def labels_of(rec):
    seen = []
    for e in rec.get("evidence") or []:
        if e.get("label") not in seen:
            seen.append(e.get("label"))
    return ",".join(seen) if seen else "-"


def track_line(rec, eff):
    status, by = eff.get(rec.get("id"), (rec.get("status", "live"), None))
    tail = "" if status == "live" else " · %s by %s" % (status.upper(), by or "?")
    rests = rests_on_refuted(rec, eff)
    if rests:
        tail += " · RESTS-ON-REFUTED %s" % ",".join(rests)
    return "%s · %s · %s · %s · [%s]%s" % (
        rec.get("id", "F-?"), rec.get("kind", "?"), rec.get("relation", "?"),
        head(rec.get("statement", "")), labels_of(rec), tail)


# ---------------------------------------------------------------------------
# legacy index
# ---------------------------------------------------------------------------
def dossier_date(text, path):
    """The dossier's own date line if it declares one in its first 40 lines;
    otherwise the filesystem mtime (labelled as such by the caller)."""
    headtext = "\n".join(text.splitlines()[:40])
    m = DATE_DECL_RE.search(headtext) or DATE_BARE_RE.search(headtext)
    if m:
        return m.group(1)
    return datetime.fromtimestamp(path.stat().st_mtime,
                                  timezone.utc).strftime("%Y-%m-%d")


def dossier_files(root):
    for d in DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*Dossier.md")):
            yield d, p


def entries(root):
    out = []
    for d, p in dossier_files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), p.stem)
        date = dossier_date(text, p)
        head_lines, in_rmf = [], False
        for l in lines:
            if re.match(r"^#{1,3} .*Read Me First", l):
                in_rmf = True
                continue
            if in_rmf:
                if l.startswith("#") or l.startswith("---"):
                    break
                if l.strip():
                    head_lines.append(l.strip()[:200])
                if len(head_lines) >= 6:
                    break
        out.append((d, title, date, p.relative_to(root).as_posix(), head_lines))
    return out


def agent_ledger(root):
    """One index entry for the hook-written agent activity ledger, if present at
    the repo root. Returns (rel_path, entry_count) or None; degrades silently if
    the file is unreadable. entry_count = lines that start '- [' (one per agent)."""
    p = root / LEDGER
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    count = sum(1 for l in text.splitlines() if l.startswith("- ["))
    return (p.relative_to(root).as_posix(), count)


def compile_candidates(root):
    """One index entry for compile.py's repeated-work table, if present. Returns
    (rel_path, ripe_count, total_count) or None; degrades silently when the table
    or its data file is missing or unreadable. Counts come from the JSON the same
    scan wrote — the markdown beside it is the reading copy."""
    p = root / CANDIDATES
    if not p.is_file():
        return None
    ripe = total = 0
    try:
        data = json.loads((root / CANDIDATES_DATA).read_text(encoding="utf-8"))
        cands = data.get("candidates", [])
        total = len(cands)
        ripe = sum(1 for c in cands if c.get("ripe"))
    except Exception:
        pass
    return (p.relative_to(root).as_posix(), ripe, total)


def findings_entry(root):
    """One index entry for the findings store, if present: counts, never a copy."""
    recs = load_store(root)
    if not recs:
        return None
    eff = resolve(recs)
    live = sum(1 for r in recs if eff.get(r.get("id"), ("live",))[0] == "live")
    return (STORE, len(recs), live)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_scan(a):
    root = pathlib.Path(a.root).resolve()
    es = entries(root)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    buf = ["# ORACLE index — generated by archivist; do not hand-edit (re-run scan)",
           f"Last scan: {now} · {len(es)} dossier(s)", ""]
    for d, title, date, rel, head_lines in es:
        buf.append(f"### {title} — {date}")
        buf.append(f"folder: {d} · path: {rel}")
        buf.extend(head_lines)
        buf.append("")
    suffix = ""
    fe = findings_entry(root)
    if fe is not None:
        rel, total, live = fe
        buf.append(f"### findings store — {total} record(s), {live} live")
        buf.append(f"folder: archive · path: {rel}")
        buf.append("the session track — every skill's finding records, append-only; "
                   "read it with: index.py track")
        buf.append("")
        suffix += f" + findings ({live}/{total} live)"
    led = agent_ledger(root)
    if led is not None:
        rel, count = led
        buf.append(f"### agent activity ledger — {count} entr{'y' if count == 1 else 'ies'}")
        buf.append(f"folder: (repo root) · path: {rel}")
        buf.append("agent activity ledger — which agents ran, what each concluded; "
                   "entries point at full transcripts")
        buf.append("")
        suffix += f" + agent ledger ({count})"
    cc = compile_candidates(root)
    if cc is not None:
        rel, ripe, total = cc
        buf.append(f"### compile candidates — {ripe} ripe of {total}")
        buf.append(f"folder: compile · path: {rel}")
        buf.append("compile candidates — repeated work the estate has recorded; "
                   "ripe rows are ready to compile")
        buf.append("")
        suffix += f" + compile candidates ({ripe}/{total} ripe)"
    (root / INDEX).write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(f"{root / INDEX}: {len(es)} entries{suffix}")


def read_payload(a):
    if a.json:
        text = a.json
    else:
        text = sys.stdin.read()
    if not text.strip():
        die("no-input", "pass --json '<record>' or pipe the record on stdin")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        die("json-parse", str(exc))


def cmd_add(a):
    root = pathlib.Path(a.root).resolve()
    raw = read_payload(a)
    try:
        print(append_record(root, raw))
    except Reject as r:
        die(r.rule, r.detail)


def select(records, a):
    eff = resolve(records)
    out = []
    for r in sorted(records, key=sort_key):
        if a.session and r.get("session") != a.session:
            continue
        if a.kind and r.get("kind") != a.kind:
            continue
        if a.status and eff.get(r.get("id"), ("live", None))[0] != a.status:
            continue
        out.append(r)
    return out, eff


def cmd_track(a):
    root = pathlib.Path(a.root).resolve()
    records = load_store(root)
    shown, eff = select(records, a)
    if a.json:
        payload = {"generated": now_z(), "root": str(root), "store": STORE,
                   "total": len(records), "shown": len(shown), "records": []}
        for r in shown:
            status, by = eff.get(r.get("id"), (r.get("status", "live"), None))
            item = dict(r)
            item["effective_status"] = status
            item["status_by"] = by
            # Always present, so a consumer can test truthiness instead of membership.
            # Non-empty only on an effectively-live record (see rests_on_refuted).
            item["rests_on_refuted"] = rests_on_refuted(r, eff)
            payload["records"].append(item)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not records:
        print("no findings store at %s — nothing recorded yet (write one: index.py add)"
              % (root / STORE))
        return
    live = sum(1 for r in records if eff.get(r.get("id"), ("live",))[0] == "live")
    print("# session track — %d record(s), %d live · %s" % (len(records), live, STORE))
    for r in shown:
        print(track_line(r, eff))
    if not shown:
        print("(no record matches the filters)")


def tombstone(a, target, statement, evidence, also=None):
    root = pathlib.Path(a.root).resolve()
    ids = {r.get("id") for r in load_store(root)}
    if target not in ids:
        die("links-unknown", "no record %s in %s" % (target, STORE))
    links = [target] + [x for x in (also or []) if x and x != target]
    raw = {"ts": a.ts or now_z(), "session": a.session, "skill": a.skill or "archivist",
           "kind": "result", "ask": a.ask, "statement": statement,
           "evidence": evidence, "relation": "back", "links": links, "status": "live"}
    try:
        print(append_record(root, raw))
    except Reject as r:
        die(r.rule, r.detail)


def cmd_supersede(a):
    target, by = a.id.upper(), a.by.upper()
    note = (" " + a.note.strip()) if a.note else ""
    stmt = "supersedes %s — replaced by %s.%s" % (target, by, note)
    ev = [{"type": "path", "ref": "%s#%s" % (STORE, by), "label": "cited"}]
    tombstone(a, target, stmt, ev, also=[by])


def cmd_refute(a):
    target = a.id.upper()
    ref = a.evidence.strip()
    etype = a.type or ("url" if URL_RE.match(ref) else "path")
    note = (" " + a.note.strip()) if a.note else ""
    stmt = "refutes %s — contradicted by %s.%s" % (target, ref, note)
    ev = [{"type": etype, "ref": ref, "label": a.label}]
    tombstone(a, target, stmt, ev)


def cmd_find(a):
    root = pathlib.Path(a.root).resolve()
    term = a.term.lower()
    hits = 0

    records = [r for r in load_store(root)
               if term in (r.get("statement", "") or "").lower()
               or term in (r.get("ask", "") or "").lower()]
    if records:
        eff = resolve(load_store(root))
        print("## findings — %d record(s) match %r" % (len(records), a.term))
        for r in sorted(records, key=sort_key):
            print(track_line(r, eff))
        print()
        hits += len(records)

    indexed = set()
    p = root / INDEX
    if p.exists():
        blocks = p.read_text(encoding="utf-8").split("\n### ")
        matched = [b for b in blocks[1:] if term in b.lower()]
        for b in matched:
            m = re.search(r"^path: (\S+)", b, re.M)
            if m:
                indexed.add(m.group(1))
            print("### " + b.strip() + "\n")
        hits += len(matched)
    else:
        print("(no %s — index entries not searched; run: index.py scan)" % INDEX)

    # Body sweep: the index carries only each dossier's Read Me First head, so a
    # term buried in the body was invisible. Read the files the index points at.
    body = 0
    for d, path in dossier_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in indexed:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [l.strip() for l in text.splitlines() if term in l.lower()]
        if not lines:
            continue
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")),
                     path.stem)
        print("### %s — %s  [body match]" % (title, dossier_date(text, path)))
        print("folder: %s · path: %s" % (d, rel))
        for l in lines[:2]:
            print("  " + head(l, 160))
        print()
        body += 1
    hits += body

    if not hits:
        print("no findings, index entries, or dossier bodies match %r "
              "(index may be stale — re-scan)" % a.term)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="archivist — findings store + dossier index")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="rebuild oracle-index.md (legacy dossier estate)")
    s.add_argument("--root", default=".")
    s.set_defaults(f=cmd_scan)

    f = sub.add_parser("find", help="search findings, index entries, dossier bodies")
    f.add_argument("term")
    f.add_argument("--root", default=".")
    f.set_defaults(f=cmd_find)

    ad = sub.add_parser("add", help="append one validated finding record")
    ad.add_argument("--json", help="the record as JSON; omit to read stdin")
    ad.add_argument("--root", default=".")
    ad.set_defaults(f=cmd_add)

    t = sub.add_parser("track", help="print the session track")
    t.add_argument("--session")
    t.add_argument("--kind", choices=KINDS)
    t.add_argument("--status", choices=STATUSES)
    t.add_argument("--json", action="store_true")
    t.add_argument("--root", default=".")
    t.set_defaults(f=cmd_track)

    for name, fn in (("supersede", cmd_supersede), ("refute", cmd_refute)):
        c = sub.add_parser(name, help="append a %s tombstone (append-only status flip)" % name)
        c.add_argument("id")
        c.add_argument("--session", default="")
        c.add_argument("--skill", default="")
        c.add_argument("--ask", default="")
        c.add_argument("--ts", default="")
        c.add_argument("--note", default="")
        c.add_argument("--root", default=".")
        if name == "supersede":
            c.add_argument("--by", required=True, help="the record that replaces it")
        else:
            c.add_argument("--evidence", required=True, help="the contradicting ref")
            c.add_argument("--type", choices=EV_TYPES, default="")
            c.add_argument("--label", choices=EV_LABELS, default="cited")
        c.set_defaults(f=fn)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
