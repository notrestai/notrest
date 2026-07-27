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
  library    the cross-project shelf: register / list / find / track — every
             registered project's store, read where it lives (see below)

THE LIBRARY IS FEDERATED, NOT CENTRAL. Each project's store stays in its own repo,
versioned and beamed with the code it describes. The library is an INDEX OF ROOTS
(~/.claude/notrest-library/registry.jsonl, append-only) so a question answered in
one project is findable — and citable — from another: evidence `{"type":"record",
"ref":"<project>:F-<n>"}`.

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
# An index block's pointer line is `folder: <d> · path: <rel>` — `path:` is NEVER at
# the start of the line, so an anchored pattern matched nothing and the body sweep
# re-reported every dossier the index had already answered for.
INDEX_PATH_RE = re.compile(r"\bpath: (\S+)")

# ---------------------------------------------------------------- the store
STORE = "archive/findings.jsonl"
FIELDS = ("id", "ts", "session", "skill", "kind", "ask", "statement",
          "evidence", "relation", "links", "status")
KINDS = ("finding", "result", "decision", "conflict", "backtrack", "side-route")
RELATIONS = ("toward", "lateral", "back")
STATUSES = ("live", "superseded", "refuted")
EV_TYPES = ("url", "path", "command", "coord-line", "record")
EV_LABELS = ("cited", "estimate", "recall", "unverified", "model-opinion")
EVIDENCE_REQUIRED = ("finding", "result", "decision")
STR_FIELDS = ("ts", "session", "skill", "ask")

URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://[^\s/]+", re.I)
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
ID_RE = re.compile(r"^F-(\d+)$")
# The resolution grammar: a tombstone declares its flip in the statement HEAD and
# names its target in links. Both must hold, or the flip does not count.
TOMB_RE = re.compile(r"^(supersedes|refutes)\s+(F-\d+)\b", re.I)

# ---------------------------------------------------------------- the library
# The shelf is a REGISTRY OF ROOTS, never a copy of anyone's store: each project
# keeps its own archive/findings.jsonl, in its own repo, versioned with the code
# it describes. Registering only tells this machine where a store lives.
LIB_ENV = "NOTREST_LIBRARY_ROOT"
LIB_DEFAULT = pathlib.Path.home() / ".claude" / "notrest-library"
REGISTRY = "registry.jsonl"           # append-only {root, name, ts}
PROJECTS = "oracle-projects.txt"      # graph.py's registry: one absolute root per line
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# THE CITATION GRAMMAR: `F-<n>` is this store; `<project>:F-<n>` is the library's.
REC_REF_RE = re.compile(r"^(?:([A-Za-z0-9][A-Za-z0-9._-]*):)?F-(\d+)$")


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
def check_record_refs(refs, known_ids, lib, notes):
    """THE CROSS-PROJECT CITATION RULE. A `record` evidence ref is `F-<n>` (this
    store) or `<project>:F-<n>` (a project on the library shelf). The shape is
    always checked. A LOCAL id must exist, exactly like `links`. A CROSS-PROJECT
    id is existence-checked when that project is registered AND its store is
    reachable — and when it is not, the ref is ACCEPTED WITH A NOTE, never
    rejected: a parallel machine's repo may simply be offline, and federation
    that fails closed is federation nobody can use."""
    idx = None
    for ref in refs:
        m = REC_REF_RE.match(ref)
        if not m:
            raise Reject("record-ref-shape",
                         "record evidence ref %r must be F-<n> (this store) or "
                         "<project>:F-<n> (the library)" % ref)
        proj, fid = m.group(1), "F-%s" % m.group(2)
        if not proj:
            if fid not in known_ids:
                raise Reject("record-ref-unknown",
                             "record evidence names %s — no such record in this store" % fid)
            continue
        if idx is None:
            idx = {p["name"]: p for p in read_registry(lib)}
        entry = idx.get(proj)
        if entry is None:
            notes.append("%s:%s cited — %r is not registered in %s; accepted unverified"
                         % (proj, fid, proj, registry_file(lib)))
            continue
        recs, _bad = load_store_safe(entry["root"])
        if recs is None:
            notes.append("%s:%s cited — %s is unreachable from here; accepted unverified"
                         % (proj, fid, entry["root"]))
            continue
        if fid not in {r.get("id") for r in recs}:
            raise Reject("record-ref-unknown",
                         "record evidence names %s:%s — that project's store holds no %s"
                         % (proj, fid, fid))


def validate(raw, known_ids, lib=None, notes=None):
    """Return a normalized record, or raise Reject naming the rule it broke."""
    lib = lib or library_root(None)
    notes = notes if notes is not None else []
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
    clean, rec_refs = [], []
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
        if etype == "record":
            rec_refs.append(ref.strip())
        clean.append({"type": etype, "ref": ref.strip(), "label": label})
    if rec_refs:
        check_record_refs(rec_refs, known_ids, lib, notes)
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


def load_store_safe(root):
    """Read a store that is NOT ours — another project's, on the library shelf.
    A corrupt line is counted and skipped, never fatal (the loud `parse_lines`
    is for this repo's own store, where a corruption is our bug to fix).
    Returns (records, bad_line_count), or (None, 0) when it is unreachable."""
    p = pathlib.Path(root).expanduser() / STORE
    try:
        if not p.is_file():
            return None, 0
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, 0
    recs, bad = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(obj, dict):
            recs.append(obj)
        else:
            bad += 1
    return recs, bad


# ---------------------------------------------------------------------------
# the library — where the shelf lives
# ---------------------------------------------------------------------------
def library_root(a=None):
    """`--library-root` beats $NOTREST_LIBRARY_ROOT beats ~/.claude/notrest-library.
    One knob moves the WHOLE shelf (registry + projects file), which is what makes
    the fixture provable without ever touching the real one."""
    v = getattr(a, "library_root", None) or os.environ.get(LIB_ENV) or ""
    return pathlib.Path(v).expanduser().resolve() if v.strip() else LIB_DEFAULT


def registry_file(lib):
    return lib / REGISTRY


def projects_file(lib):
    """graph.py's cross-project registry — the shelf's sibling, so ONE registration
    feeds both consumers (the library's find, and `graph.py all`'s PM view)."""
    return lib.parent / PROJECTS


def read_registry(lib):
    """Every registered project, in registration order, last entry per root winning.
    A corrupt or foreign line is skipped, never fatal — the registry is append-only
    and may be written by a newer version of this script than the one reading it.
    Keys beyond {root, name, ts} are CARRIED, not dropped: the line's shape is open
    on purpose, so per-project metadata can land later without a migration."""
    p = registry_file(lib)
    try:
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        root = str(rec.get("root") or "").strip()
        if not root:
            continue
        name = str(rec.get("name") or "").strip() or pathlib.Path(root).name
        entry = dict(rec)
        entry.update({"root": root, "name": name, "ts": str(rec.get("ts") or "")})
        out[root] = entry
    return list(out.values())


def read_projects(p):
    """graph.py's own reader, mirrored: one path per line, '#' comments, deduped."""
    try:
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line not in out:
            out.append(line)
    return out


def append_record(root, raw, lib=None, notes=None):
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
            rec = validate(raw, known, lib=lib, notes=notes)
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
    notes = []
    try:
        # The id goes to stdout alone — callers capture it. Notes go to stderr.
        rid = append_record(root, raw, lib=library_root(a), notes=notes)
    except Reject as r:
        die(r.rule, r.detail)
    print(rid)
    for n in notes:
        sys.stderr.write("note: %s\n" % n)


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
    notes = []
    try:
        rid = append_record(root, raw, lib=library_root(a), notes=notes)
    except Reject as r:
        die(r.rule, r.detail)
    print(rid)
    for n in notes:
        sys.stderr.write("note: %s\n" % n)


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
            m = INDEX_PATH_RE.search(b)
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
# library commands — the shelf, read where each store lives
# ---------------------------------------------------------------------------
def project_state(entry):
    """(records|None, bad_lines, reachable) for one shelf entry. A root that is
    gone is `missing`; a root that is there without a store has zero records."""
    root = pathlib.Path(entry["root"]).expanduser()
    if not root.is_dir():
        return None, 0, False
    recs, bad = load_store_safe(root)
    return (recs if recs is not None else []), bad, True


def cmd_library_register(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        die("library-root-missing", "not a directory: %s" % root)
    name = (a.name or root.name).strip()
    if not NAME_RE.match(name):
        die("library-name-shape",
            "project name %r must match %s — it is half of every cross-project "
            "citation (<project>:F-<n>)" % (name, NAME_RE.pattern))

    lib = library_root(a)
    reg, pf = registry_file(lib), projects_file(lib)
    projects = read_registry(lib)
    by_root = {p["root"]: p for p in projects}
    by_name = {p["name"]: p for p in projects}

    existing = by_root.get(str(root))
    if existing:
        extra = ""
        if a.name and a.name.strip() != existing["name"]:
            extra = (" (--name %r not applied — re-registration is a no-op; the "
                     "registry is append-only)" % a.name.strip())
        print("registry %s: already registered as %r — no-op, %d project(s)%s"
              % (reg, existing["name"], len(projects), extra))
    else:
        clash = by_name.get(name)
        if clash:
            die("library-name-taken",
                "%r already names %s — pass --name to register %s under another name"
                % (name, clash["root"], root))
        reg.parent.mkdir(parents=True, exist_ok=True)
        with open(reg, "a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(json.dumps({"root": str(root), "name": name, "ts": now_z()},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        print("registry %s: registered %s -> %s (%d project(s))"
              % (reg, name, root, len(projects) + 1))

    # ONE registration, TWO consumers: graph.py's `all` mode reads this file.
    roots = read_projects(pf)
    if str(root) in roots:
        print("projects %s: already present (%d root(s))" % (pf, len(roots)))
    else:
        pf.parent.mkdir(parents=True, exist_ok=True)
        with open(pf, "a", encoding="utf-8") as fh:
            fh.write(str(root) + "\n")
        print("projects %s: added %s (%d root(s))" % (pf, root, len(roots) + 1))


def cmd_library_list(a):
    lib = library_root(a)
    projects = read_registry(lib)
    if not projects:
        print("no projects on the shelf (%s) — register one: index.py library register --root ."
              % registry_file(lib))
        return
    print("# library — %d project(s) · %s" % (len(projects), registry_file(lib)))
    for p in projects:
        recs, bad, up = project_state(p)
        if not up:
            print("%s · %s · records — · missing" % (p["name"], p["root"]))
            continue
        eff = resolve(recs)
        live = sum(1 for r in recs if eff.get(r.get("id"), ("live",))[0] == "live")
        tail = " · %d unreadable line(s)" % bad if bad else ""
        print("%s · %s · records %d (%d live) · reachable%s"
              % (p["name"], p["root"], len(recs), live, tail))


def library_line(name, rec, eff):
    """The shelf's citation line: <project>:F-<n> · kind · statement-head · [labels].
    A non-live record says so — a citation grammar that let a refuted record travel
    between projects would launder exactly the thing the store exists to catch."""
    status, by = eff.get(rec.get("id"), (rec.get("status", "live"), None))
    tail = "" if status == "live" else " · %s by %s" % (status.upper(), by or "?")
    return "%s:%s · %s · %s · [%s]%s" % (
        name, rec.get("id", "F-?"), rec.get("kind", "?"),
        head(rec.get("statement", "")), labels_of(rec), tail)


def cmd_library_find(a):
    lib = library_root(a)
    projects = read_registry(lib)
    terms = [t.lower() for t in a.terms if t.strip()]
    if not projects:
        msg = ("no projects on the shelf (%s) — register one: "
               "index.py library register --root ." % registry_file(lib))
        print(json.dumps({"generated": now_z(), "registry": str(registry_file(lib)),
                          "terms": a.terms, "projects": [], "hits": [],
                          "index_hits": [], "unreachable": [], "total": 0,
                          "note": msg}, ensure_ascii=False, indent=2)
              if a.json else msg)
        return
    if not terms:
        die("no-input", "library find needs at least one term")

    if not a.json:
        print("# library find %s — %d project(s) · %s"
              % (" ".join(repr(t) for t in a.terms), len(projects), registry_file(lib)))
    hits, hit_projects, down = 0, 0, []
    # --json is the machine surface: ask and statement travel WHOLE (the line
    # format's 90-char head is a reading convenience, never the record).
    out_hits, idx_hits, seen_projects = [], [], []
    for p in projects:
        recs, _bad, up = project_state(p)
        if not up:
            down.append(p)
            continue
        found = 0
        eff = resolve(recs)
        for r in sorted(recs, key=sort_key):
            if a.kind and r.get("kind") != a.kind:
                continue
            hay = ("%s %s" % (r.get("statement", "") or "", r.get("ask", "") or "")).lower()
            if not all(t in hay for t in terms):
                continue
            status, by = eff.get(r.get("id"), (r.get("status", "live"), None))
            item = dict(r)
            item.update({"project": p["name"], "root": p["root"],
                         "ref": "%s:%s" % (p["name"], r.get("id")),
                         "effective_status": status, "status_by": by,
                         "rests_on_refuted": rests_on_refuted(r, eff)})
            out_hits.append(item)
            if not a.json:
                print(library_line(p["name"], r, eff))
            found += 1
        # The legacy estate is on the shelf too: index HEADS only, never bodies —
        # the library reads across repos, so it stays cheap by construction.
        idx = pathlib.Path(p["root"]).expanduser() / INDEX
        try:
            text = idx.read_text(encoding="utf-8", errors="replace") if idx.is_file() else ""
        except OSError:
            text = ""
        for block in text.split("\n### ")[1:]:
            if not all(t in block.lower() for t in terms):
                continue
            m = INDEX_PATH_RE.search(block)
            entry = {"project": p["name"], "heading": block.splitlines()[0].strip(),
                     "path": m.group(1) if m else ""}
            idx_hits.append(entry)
            if not a.json:
                print("%s:index · %s%s"
                      % (p["name"], head(entry["heading"], 90),
                         " · " + entry["path"] if entry["path"] else ""))
            found += 1
        hits += found
        hit_projects += 1 if found else 0
        seen_projects.append({"name": p["name"], "root": p["root"],
                              "reachable": True, "records": len(recs), "hits": found})
    if a.json:
        print(json.dumps(
            {"generated": now_z(), "registry": str(registry_file(lib)),
             "terms": a.terms, "kind": a.kind,
             "projects": seen_projects + [{"name": p["name"], "root": p["root"],
                                           "reachable": False, "records": 0, "hits": 0}
                                          for p in down],
             "unreachable": [{"name": p["name"], "root": p["root"]} for p in down],
             "hits": out_hits, "index_hits": idx_hits, "total": hits},
            ensure_ascii=False, indent=2))
        return
    for p in down:
        print("(unreachable: %s · %s — never fatal; the repo may be on another machine)"
              % (p["name"], p["root"]))
    print("%d hit(s) in %d of %d project(s)%s"
          % (hits, hit_projects, len(projects),
             " · %d unreachable" % len(down) if down else ""))


def cmd_library_track(a):
    lib = library_root(a)
    projects = read_registry(lib)
    entry = next((p for p in projects if p["name"] == a.project), None)
    if entry is None:
        die("library-unknown-project",
            "%r is not on the shelf (%s) — registered: %s"
            % (a.project, registry_file(lib),
               ", ".join(p["name"] for p in projects) or "(none)"))
    root = pathlib.Path(entry["root"]).expanduser()
    if not root.is_dir():
        die("library-unreachable",
            "%s is registered at %s — that root is not reachable from here"
            % (a.project, entry["root"]))
    recs, bad = load_store_safe(root)
    if recs is None:
        recs, bad = [], 0
    # Remote read: the store is loaded from where it lives, nothing is copied here.
    shown, eff = select(recs, a)
    live = sum(1 for r in recs if eff.get(r.get("id"), ("live",))[0] == "live")
    print("# track — %s · %s · %d record(s), %d live%s"
          % (entry["name"], root / STORE, len(recs), live,
             " · %d unreadable line(s)" % bad if bad else ""))
    for r in shown:
        print(track_line(r, eff))
    if not shown:
        print("(no record matches the filters)")


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
    ad.add_argument("--library-root", default="",
                    help="the shelf (default $%s or ~/.claude/notrest-library)" % LIB_ENV)
    ad.set_defaults(f=cmd_add)

    lb = sub.add_parser("library", help="the cross-project shelf: register, list, find, track")
    lbs = lb.add_subparsers(dest="libcmd", required=True)

    def shelf(p):
        p.add_argument("--library-root", default="",
                       help="the shelf (default $%s or ~/.claude/notrest-library)" % LIB_ENV)
        return p

    lr = shelf(lbs.add_parser("register", help="put a project on the shelf (idempotent)"))
    lr.add_argument("--root", default=".")
    lr.add_argument("--name", default="", help="shelf name (default: the repo's dirname)")
    lr.set_defaults(f=cmd_library_register)

    shelf(lbs.add_parser("list", help="every registered project: records, reachable or missing")
          ).set_defaults(f=cmd_library_list)

    lf = shelf(lbs.add_parser("find", help="search every registered project's store"))
    lf.add_argument("terms", nargs="+", help="all terms must appear (statement + ask)")
    lf.add_argument("--kind", choices=KINDS)
    lf.add_argument("--json", action="store_true",
                    help="machine surface: whole ask + statement, never the 90-char head")
    lf.set_defaults(f=cmd_library_find)

    lt = shelf(lbs.add_parser("track", help="another project's track, read where it lives"))
    lt.add_argument("--project", required=True)
    lt.add_argument("--session")
    lt.add_argument("--kind", choices=KINDS)
    lt.add_argument("--status", choices=STATUSES)
    lt.set_defaults(f=cmd_library_track)

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
