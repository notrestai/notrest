#!/usr/bin/env python3
"""watch.py — the recheck protocol's mechanical half: due-computation, source probing,
and the atomic drift-log write. The model is left with the only job that needs a model
(judging a page that actually CHANGED); everything else resolves at zero model tokens.

Subcommands:
  add   --from-findings [--root .] [--cadence C] [--today YYYY-MM-DD]
        build watchlist rows straight from the archivist's findings store: every
        effectively-live finding|result carrying [cited] url evidence becomes a row
        (Source = F-<id>, so the store keeps owning the URL). Idempotent — a record any
        row already names is skipped, and what was left off says why. exit 0.

  due   [--root .] [--today YYYY-MM-DD]
        parse watch/watchlist.md, print the rows whose cadence has come round — AND the
        findings store's live `open` records whose `recheck` date has arrived, which are
        the same kind of thing on the same calendar. exit 3 = something is due (branch
        here in a hook) · 0 = nothing due.

  close O-<n> --exit N [--command CMD] [--ran TEXT] [--note TEXT] [--root .]
        close an open question by recording, through index.py's own door, the check that
        closed it: a kind=result record citing the open id in `links` and headed
        `closes O-<n>`. Refuses a second closure (exit 5) and a non-zero exit with no
        note (exit 2). exit 0 = closed.

  probe <row-id> [--root .] [--url URL] [--scratch DIR] [--timeout 10]
        HEAD, then a conditional GET (If-None-Match/If-Modified-Since from the last
        probe's validators) of the row's source. Reports the status code and the body
        sha256 against the row's stored Hash cell — adding that column if the table
        predates it. exit 0 UNCHANGED · 3 CHANGED (body written to scratch, path
        printed — this is the only case that costs the model anything) · 4 DEAD-SOURCE.

  append --json <file|-> [--root .]
        write the dated drift-log block and update each row's Last checked/Status/Hash.
        Counts are COMPUTED from the findings, never asserted; a HOLDS whose URL is not
        on the Fetched-this-run line is refused (exit 5), because that is exactly the
        law the block's honesty stamp exists to make checkable.

Stdlib only. Files: <root>/watch/watchlist.md, <root>/watch/drift-log.md, and a derived
validator cache at <root>/watch/.probe-cache.json (machine-written, safe to delete).
"""
import argparse, hashlib, json, os, pathlib, re, subprocess, sys, tempfile
from datetime import date, datetime, timedelta, timezone
from urllib import error as uerror, request as urequest

CADENCE_DAYS = {"daily": 1, "weekly": 7, "fortnightly": 14, "monthly": 30,
                "quarterly": 91, "yearly": 365, "annually": 365}
NEVER_DUE = {"retired", "on-demand", "on demand", "ondemand", "paused"}
STATUSES = ("HOLDS", "DRIFTED", "DEAD-SOURCE", "UNVERIFIABLE")
MARK = {"HOLDS": "✅", "DRIFTED": "🔴", "DEAD-SOURCE": "⚫", "UNVERIFIABLE": "⚪"}
ORDER = {"DRIFTED": 0, "HOLDS": 1, "DEAD-SOURCE": 2, "UNVERIFIABLE": 3}
UA = {"User-Agent": "notrest-watch/1.0 (+source recheck; HEAD then conditional GET)"}
FINDING_RE = re.compile(r"\bF-(\d+)\b")
URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
_FINDINGS = {}


def die(msg, code=2):
    sys.stderr.write("watch: %s\n" % msg)
    sys.exit(code)


def wdir(root):
    return pathlib.Path(root).resolve() / "watch"


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower().replace("-", " "))


def today(a):
    if getattr(a, "today", None):
        try:
            return datetime.strptime(a.today, "%Y-%m-%d").date()
        except ValueError:
            die("--today must be YYYY-MM-DD, got %r" % a.today)
    return date.today()


# ── the watchlist table ─────────────────────────────────────────────────────
class Row(object):
    """One watched claim: its cells, where in the file they live, and the `##` subject
    they sit under (a dossier path for legacy rows, `F-<id>` for findings-store rows)."""

    def __init__(self, idx, cells, cols, table, section=""):
        self.idx, self.cells, self.cols, self.table = idx, cells, cols, table
        self.section = section

    def get(self, name, default=""):
        i = self.cols.get(name)
        return self.cells[i].strip() if i is not None and i < len(self.cells) else default

    def set(self, name, value):
        i = self.cols.get(name)
        if i is None or i >= len(self.cells):
            return False
        self.cells[i] = " %s " % value
        return True

    @property
    def id(self):
        return self.get("id")

    @property
    def claim(self):
        return self.get("claim (verbatim)") or self.get("claim")

    @property
    def url(self):
        src = self.get("source")
        m = re.search(r"\((https?://[^)\s]+)\)", src) or re.search(r"(https?://\S+)", src)
        return m.group(1) if m else src

    @property
    def cadence(self):
        return self.get("cadence").lower()

    def render(self):
        return "|" + "|".join(self.cells) + "|"


def split_row(line):
    """Cells of a markdown table row, without the leading/trailing empties."""
    return line.strip().strip("|").split("|")


def is_sep(line):
    return bool(re.match(r"^\s*\|[\s:|-]+\|\s*$", line))


def parse_watchlist(root, required=True):
    """Return (path, lines, rows). Tables are located by their header row, so a table
    that has grown a Hash column parses exactly like one that has not.

    `required=False` is for `due`, which now also runs over the findings store's OPEN
    records: an estate that tracks open questions but keeps no watchlist has a real
    calendar, and dying at exit 2 would hide it."""
    p = wdir(root) / "watchlist.md"
    if not p.exists():
        if not required:
            return p, [], []
        die("no watchlist at %s — run /watch add first" % p, 2)
    lines = p.read_text(encoding="utf-8").splitlines()
    rows, cols, table, section = [], None, 0, ""
    for i, line in enumerate(lines):
        if not line.strip().startswith("|"):
            if line.startswith("##"):
                section = line.lstrip("#").strip()
            cols = None
            continue
        if is_sep(line):
            continue
        cells = split_row(line)
        head = [norm(c) for c in cells]
        if cols is None:
            if "id" in head:
                cols, table = dict((n, j) for j, n in enumerate(head)), table + 1
            continue
        rows.append(Row(i, cells, cols, table, section))
    return p, lines, rows


# ── where a row's source comes from ─────────────────────────────────────────
# Legacy rows carry a URL in the Source cell, under a `## <dossier path>` subject.
# Findings-store rows carry `F-<id>` (in the cell or the subject) and resolve through
# the archivist's store, whose `url` evidence refs are what actually gets fetched.
def index_script():
    env = os.environ.get("WATCH_INDEX_PY")
    if env:
        return pathlib.Path(env)
    base = os.environ.get("CLAUDE_PLUGIN_ROOT")
    root = pathlib.Path(base) if base else pathlib.Path(__file__).resolve().parents[3]
    return root / "skills" / "archivist" / "scripts" / "index.py"


def findings(root):
    """{F-id: record} from `index.py track --json`, read once per run. Never raises:
    an unreachable store degrades to a named reason, not a traceback."""
    key = str(root)
    if key in _FINDINGS:
        return _FINDINGS[key]
    script, recs, why = index_script(), {}, ""
    if not script.exists():
        why = "no findings-store reader at %s" % script
    else:
        try:
            r = subprocess.run([sys.executable, str(script), "track", "--json",
                                "--root", str(root)], timeout=60,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode != 0:
                why = "index.py track exited %d: %s" % (
                    r.returncode, r.stderr.decode("utf-8", "replace").strip()[:120])
            else:
                for rec in json.loads(r.stdout.decode("utf-8", "replace")).get("records") or []:
                    recs[str(rec.get("id", "")).upper()] = rec
                if not recs:
                    why = "the findings store holds no records"
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            why = "%s reading the findings store" % exc.__class__.__name__
    _FINDINGS[key] = (recs, why)
    return recs, why


def source_url(row, root):
    """(url, note) for a row. A findings id resolves to its first `url` evidence ref."""
    raw = row.get("source")
    if URL_RE.match(raw) or "](" in raw:
        return row.url, ""
    m = FINDING_RE.search(raw) or FINDING_RE.search(row.section or "")
    if not m:
        return row.url, ""
    fid = "F-%s" % m.group(1)
    recs, why = findings(root)
    rec = recs.get(fid)
    if rec is None:
        return "", "%s UNRESOLVED — %s" % (fid, why or "no such record in the store")
    urls = [str(e.get("ref", "")).strip() for e in (rec.get("evidence") or [])
            if e.get("type") == "url" and str(e.get("ref", "")).strip()]
    status = rec.get("effective_status") or rec.get("status") or "live"
    note = fid
    if status != "live":
        # Worth saying out loud: the store already judged this record.
        note += " [%s — watching a record the store no longer calls live]" % status
    if not urls:
        return "", ("%s carries no url evidence (types present: %s) — a claim with no "
                    "re-readable source cannot be watched"
                    % (fid, ", ".join(sorted({str(e.get("type")) for e in
                                              (rec.get("evidence") or [])})) or "none"))
    if len(urls) > 1:
        note += " (%d url evidence refs; watching the first)" % len(urls)
    return urls[0], note


def write_lines(path, lines):
    """Atomic per file: land the new bytes with os.replace, never a partial rewrite."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def ensure_hash_column(path, lines, rows):
    """Add the Hash column to every table that lacks it (minimal diff: one cell
    appended per line, existing alignment untouched). Returns fresh rows."""
    if not rows or all("hash" in r.cols for r in rows):
        return lines, rows, False
    out, cols = [], None
    for line in lines:
        if not line.strip().startswith("|"):
            cols = None
            out.append(line)
            continue
        if is_sep(line):
            out.append(line.rstrip() + "--------|" if cols is not None else line)
            continue
        cells = [norm(c) for c in split_row(line)]
        if cols is None and "id" in cells:
            cols = True
            out.append(line.rstrip() + " Hash |" if "hash" not in cells else line)
            continue
        out.append(line.rstrip() + "  |" if cols is not None else line)
    write_lines(path, out)
    _p, lines2, rows2 = parse_watchlist(path.parent.parent)
    return lines2, rows2, True


# ── add --from-findings ─────────────────────────────────────────────────────
# The factcheck→watch handoff as one command instead of a retyping job. The store
# already holds what was found and what it rests on; a watch row is that record plus a
# clock. Rows are BUILT from the record, never invented — and a column the store does
# not have (Tier) is left empty rather than guessed.
WATCH_ID_RE = re.compile(r"^\s*W(\d+)\s*$", re.I)
# Mirrors the archivist's tombstone grammar (index.py TOMB_RE). A status flip is
# bookkeeping about the store, not a claim about the world, so it is never watched.
TOMBSTONE_RE = re.compile(r"^(supersedes|refutes)\s+F-\d+\b", re.I)
ADD_KINDS = ("finding", "result")
COLS = ["ID", "Claim (verbatim)", "Source", "Tier", "First verified", "Last checked",
        "Status", "Cadence", "Hash"]
WATCHLIST_HEAD = [
    "# watchlist — facts under watch",
    "> Rows are APPENDED. Only `Last checked` and `Status` are edited in place, by `/watch run`.",
    "> Never delete a row — retire it by setting Cadence to `retired`. IDs are never reused.",
    "> Status: HOLDS · DRIFTED · DEAD-SOURCE · UNVERIFIABLE.",
    "> Cadence: weekly · monthly · quarterly · on-demand · retired.",
    "> A `|` inside a claim is escaped as `&#124;` so the row still parses.",
]


def cadence_for(n_cited):
    """Default cadence by how many re-readable [cited] urls the record carries: a claim
    standing on one page is one edit away from being wrong (weekly); corroboration buys
    time. Overridable per run with --cadence."""
    return {1: "weekly", 2: "monthly"}.get(n_cited, "quarterly")


def watchable(rec):
    """(url, n_cited, reason) — reason is '' when the record can become a row. The
    filter is the watch law, not a preference: a claim with no re-readable source
    cannot be watched, and a record the store no longer calls live is not a claim this
    project is leaning on."""
    status = rec.get("effective_status") or rec.get("status") or "live"
    if status != "live":
        return "", 0, "not effectively live (%s)" % status
    if rec.get("kind") not in ADD_KINDS:
        return "", 0, "kind=%s (rows come from %s)" % (rec.get("kind"), "|".join(ADD_KINDS))
    if TOMBSTONE_RE.match(rec.get("statement", "") or ""):
        return "", 0, "a status-flip tombstone, not a claim about the world"
    urls = [str(e.get("ref", "")).strip() for e in (rec.get("evidence") or [])
            if e.get("type") == "url" and e.get("label") == "cited"
            and str(e.get("ref", "")).strip()]
    if not urls:
        return "", 0, "no [cited] url evidence — nothing re-readable to watch"
    return urls[0], len(urls), ""


def claim_cell(rec):
    """The statement verbatim, made safe for a markdown row. Never paraphrased — a
    paraphrase is not the claim the project is leaning on."""
    return '"%s"' % " ".join((rec.get("statement") or "").split()).replace("|", "&#124;")


def fid_num(fid):
    m = FINDING_RE.search(fid or "")
    return int(m.group(1)) if m else 0


def cmd_add(a):
    if not a.from_findings:
        die("add builds rows from the findings store: watch.py add --from-findings "
            "[--root .]. Rows from a dossier or from pasted claims are written by the "
            "model against the table contract in SKILL.md.")
    recs, why = findings(a.root)
    if not recs:
        die("nothing to add — %s" % (why or "the findings store holds no records"))

    p = wdir(a.root) / "watchlist.md"
    if p.exists():
        p, lines, rows = parse_watchlist(a.root)
    else:
        lines, rows = list(WATCHLIST_HEAD), []

    # Idempotence: a record already named by ANY row — in its Source cell or its `##`
    # subject — is already watched. Re-running add is a no-op, not a duplicate row.
    watched, top = {}, 0
    for r in rows:
        for m in FINDING_RE.finditer("%s %s" % (r.get("source"), r.section or "")):
            watched.setdefault("F-%s" % m.group(1), r.id)
        m = WATCH_ID_RE.match(r.id or "")
        if m:
            top = max(top, int(m.group(1)))

    when, new, skipped, left = str(today(a)), [], [], []
    for fid in sorted(recs, key=fid_num):
        rec = recs[fid]
        url, n_cited, reason = watchable(rec)
        if reason:
            left.append((fid, reason))
            continue
        if fid in watched:
            skipped.append((fid, watched[fid]))
            continue
        top += 1
        wid = "W%d" % top
        # First verified is the record's own ts — the date the finding was written, not
        # today. Last checked starts equal to it, so the cadence runs from the finding.
        first = (rec.get("ts") or "")[:10] or when
        cad = a.cadence or cadence_for(n_cited)
        # Status HOLDS is the honest carry-over of the store's [cited] label, never a
        # fresh verification: watch has not re-read anything yet. The first `/watch run`
        # is what earns the next status.
        new.append((wid, fid, url, cad,
                    [" %s " % wid, " %s " % claim_cell(rec), " %s " % fid, " - ",
                     " %s " % first, " %s " % first, " HOLDS ", " %s " % cad, "  "]))

    if new:
        block = ["", "## findings store · added %s" % when,
                 "| " + " | ".join(COLS) + " |",
                 "|" + "|".join("-" * (len(c) + 2) for c in COLS) + "|"]
        block += ["|" + "|".join(cells) + "|" for _w, _f, _u, _c, cells in new]
        p.parent.mkdir(parents=True, exist_ok=True)
        write_lines(p, list(lines) + block)

    for wid, fid, url, cad, _cells in new:
        print("ADD   %-4s %-6s %-10s %s" % (wid, fid, cad, url))
    for fid, wid in skipped:
        print("SKIP  %-4s %-6s already watched — nothing appended" % (wid, fid))
    # Never dropped silently: every record this run left off says why.
    for fid, reason in left:
        print("LEFT  %-11s %s" % (fid, reason))
    print("watch: add --from-findings — %d row(s) appended, %d already watched, "
          "%d left off (of %d record%s) · %s"
          % (len(new), len(skipped), len(left), len(recs),
             "" if len(recs) == 1 else "s", p))


# ── open questions on the same clock (docket G) ─────────────────────────────
#
# The archivist's `open` kind records what was NOT tested or did not work, and it carries
# three required fields: what would CLOSE it, an OWNER who can, and a RECHECK date. That
# third field only means something if something READS it — otherwise an open question
# ages quietly into folklore, which is the exact failure the kind exists to prevent. So
# `due` runs over open records as well as watchlist rows: one calendar, two kinds of
# thing on it, one exit code.
#
# ⛔ THE CLOSING GRAMMAR, AND THE GAP IT PAPERS OVER. The store has no status flip for an
# open question: `index.py`'s tombstone grammar is `supersedes|refutes F-<n>` (F- ids
# only), and its `record` evidence refs are `[FL]-<n>`, so an `O-<n>` cannot legally be
# cited as evidence at all. Until the store grows one, closure is DERIVED here: a record
# whose statement head reads `closes O-<n>` AND whose `links` names that id closes it.
# Both halves are required, exactly as the tombstone grammar requires both — a sentence
# that merely mentions an id is not a flip. `watch.py close` writes precisely that shape.
# If index.py later adds a real `closes` tombstone, this derivation should be deleted and
# the store's own resolution read instead; two grammars for one flip is one too many.
OPEN_KIND = "open"
CLOSES_RE = re.compile(r"^closes\s+(O-\d+)\b", re.I)
OPEN_ID_RE = re.compile(r"^O-\d+$", re.I)


def open_records(root):
    """(open_recs, closed_by, why) — the store's live open questions and their closers.

    `closed_by` maps a closed open-id to the id of the record that closed it, so `due`
    can leave it off the calendar and `close` can refuse to close it twice.
    """
    recs, why = findings(root)
    opens, closed = [], {}
    for rec in recs.values():
        stmt = str(rec.get("statement") or "")
        m = CLOSES_RE.match(stmt.strip())
        if m:
            oid = m.group(1).upper()
            links = [str(x).upper() for x in (rec.get("links") or [])]
            if oid in links:
                closed[oid] = str(rec.get("id") or "?")
        if rec.get("kind") != OPEN_KIND:
            continue
        # A record the store no longer calls live is not a question this estate is
        # carrying — the store already ruled on it, and re-listing it would be this
        # script overriding that ruling.
        if (rec.get("effective_status") or rec.get("status") or "live") != "live":
            continue
        opens.append(rec)
    opens.sort(key=lambda r: (str(r.get("recheck") or ""), str(r.get("id") or "")))
    return opens, closed, why


def open_due(rec, now):
    """(is_due, why) for one open record. A missing or unparsable recheck date is DUE
    NOW and says so — the same ruling `next_due` makes for an unparsable Last checked,
    and for the same reason: a clock nobody can read is not a reason to stop watching.
    A date in the FUTURE is honoured; a date in the future is the whole point of one."""
    raw = str(rec.get("recheck") or "").strip()
    try:
        d = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return True, "unparsable recheck %r — treated as due now" % raw
    return d <= now, ""


# ── due ─────────────────────────────────────────────────────────────────────
def next_due(row):
    """(due-date, why) — None when the cadence means 'never on a clock'."""
    cad = row.cadence
    if cad in NEVER_DUE or not cad:
        return None, cad or "no cadence"
    days = CADENCE_DAYS.get(cad)
    if days is None:
        return None, "unknown cadence %r" % cad
    last = row.get("last checked")
    try:
        d = datetime.strptime(last, "%Y-%m-%d").date()
    except ValueError:
        return date.min, "unparsable Last checked %r" % last
    # S81: AN UPPER BOUND, doctor's shape. `Last checked` in the FUTURE is not evidence
    # that anything was checked -- but it pushes next_due past every `nd <= now` test, so
    # the row falls out of BOTH the due list and the held list and vanishes from the
    # output entirely. ⛔ A WATCH THAT NEVER FIRES IS INDISTINGUISHABLE FROM A WATCH WITH
    # NOTHING TO REPORT. An unparsable stamp is already treated as due-now (date.min); a
    # future one is no better evidence, so it is treated the same and SAYS WHY.
    # NOT FIRING TODAY: measured at this seat, the live watchlist's 2 rows are both dated
    # in the past. This closes a latent gap; it does not close a live defect.
    if d > date.today():
        return date.min, "Last checked %r is in the FUTURE — not evidence of a check" % last
    return d + timedelta(days=days), ""


def cmd_due(a):
    p, _l, rows = parse_watchlist(a.root, required=False)
    opens, closed, why = open_records(a.root)
    if not rows and not opens and not p.exists():
        die("no watchlist at %s and no open records in the findings store%s — "
            "run /watch add first" % (p, " (%s)" % why if why else ""), 2)
    now, due, held = today(a), [], []
    for r in rows:
        nd, why = next_due(r)
        if nd is None:
            held.append((r, why))
        elif nd <= now:
            due.append((r, nd, why))
    for r, nd, why in due:
        claim = r.claim
        claim = claim[:70] + "…" if len(claim) > 70 else claim
        note = "  [%s]" % why if why else ""
        url, src = source_url(r, a.root)
        print("DUE  %-4s %-9s last=%s due=%s  %s%s"
              % (r.id, r.cadence, r.get("last checked"), nd if nd != date.min else "?",
                 url or "(no fetchable source)", note))
        if src:
            print("       via %s" % src)
        print("       %s" % claim)
    print("watch: %d due of %d rows (%d never-due: %s)"
          % (len(due), len(rows), len(held),
             ", ".join("%s=%s" % (r.id, w) for r, w in held) or "-"))

    # ── the other half of the calendar: open questions whose recheck date has come ──
    odue = []
    for rec in opens:
        oid = str(rec.get("id") or "?").upper()
        if oid in closed:
            continue
        is_due, note = open_due(rec, now)
        if is_due:
            odue.append((rec, note))
    for rec, note in odue:
        oid = str(rec.get("id") or "?")
        stmt = " ".join(str(rec.get("statement") or "").split())
        print("OPEN %-5s recheck=%-10s owner=%-12s%s"
              % (oid, str(rec.get("recheck") or "?"), str(rec.get("owner") or "?"),
                 "  [%s]" % note if note else ""))
        print("       %s" % (stmt[:110] + "…" if len(stmt) > 110 else stmt))
        print("       closes when: %s" % " ".join(str(rec.get("closes_when") or "?").split()))
        print("       close it: watch.py close %s --exit <code> --root %s" % (oid, a.root))
    print("watch: %d open question(s) due of %d live open (%d already closed)%s"
          % (len(odue), len(opens), len(closed),
             " · %s" % why if (why and not opens) else ""))
    sys.exit(3 if (due or odue) else 0)


# ── close ───────────────────────────────────────────────────────────────────
def cmd_close(a):
    oid = a.open_id.upper()
    if not OPEN_ID_RE.match(oid):
        die("%r is not an open-record id (O-<n>)" % a.open_id, 2)
    opens, closed, why = open_records(a.root)
    rec = next((r for r in opens if str(r.get("id") or "").upper() == oid), None)
    if rec is None:
        recs, _why = findings(a.root)
        if oid in recs:
            die("%s is kind=%s, not an open question%s"
                % (oid, recs[oid].get("kind"),
                   "" if (recs[oid].get("effective_status") or "live") == "live"
                   else " (and the store no longer calls it live)"), 2)
        die("no open record %s in the findings store%s — open ids here: %s"
            % (oid, " (%s)" % why if why else "",
               ", ".join(str(r.get("id")) for r in opens) or "none"), 2)
    if oid in closed:
        die("%s was already closed by %s — an append-only store records a closure once; "
            "a second one would make the count of open questions a matter of opinion"
            % (oid, closed[oid]), 5)

    # An open question is closed by RUNNING its own closing check, so the closing record
    # is a `result`: what ran, the exact command, and the integer exit code. That is the
    # store's own bar for a result and it is exactly the right bar here — "we looked into
    # it" is not a closure.
    command = a.command or str(rec.get("closes_when") or "").strip()
    if not command:
        die("%s carries no closes_when and no --command was given — there is nothing to "
            "record as the check that closed it" % oid, 2)
    if a.exit_code != 0 and not (a.note or "").strip():
        # ⛔ A FAILING CHECK MAY STILL CLOSE A QUESTION — "we tried it and it does not
        # work" is an answer. It may never do so SILENTLY, though: without a note the
        # record would read as a closure and the exit code as a detail.
        die("closing %s with exit %d needs --note saying what the failure SETTLED — a "
            "non-zero check that closes a question is a finding, not a formality"
            % (oid, a.exit_code), 2)
    ran = a.ran or ("the closes_when check of %s" % oid)
    note = " ".join((a.note or "").split())
    head = "closes %s" % oid
    stmt = ("%s — %s" % (head, note) if note else
            "%s — %s exited %d" % (head, " ".join(command.split()), a.exit_code))
    if len(stmt) > 300:                       # index.py's STATEMENT_MAX
        stmt = stmt[:297] + "..."

    payload = {
        "session": a.session or "watch", "skill": "watch", "kind": "result",
        "ask": "close open question %s" % oid, "statement": stmt,
        "ran": ran, "command": command, "exit": a.exit_code,
        # The citation rides in `links`, not in evidence: index.py's record-evidence
        # grammar is [FL]-<n>, so an O- id cannot legally be cited there (gap disclosed
        # at the top of this section). `links` validates against the store's known ids,
        # so this is still a checked reference, not a string.
        "links": [oid],
        "evidence": [{"type": "command", "ref": command, "label": "cited"}],
        "relation": "toward",
    }
    script = index_script()
    if not script.exists():
        die("no findings-store writer at %s — the closing record has to go through the "
            "store's own door, so nothing was written" % script, 2)
    try:
        r = subprocess.run([sys.executable, str(script), "add", "--root", str(a.root)],
                           input=json.dumps(payload).encode("utf-8"), timeout=60,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.SubprocessError) as exc:
        die("%s writing the closing record" % exc.__class__.__name__, 2)
    out = r.stdout.decode("utf-8", "replace").strip()
    err = r.stderr.decode("utf-8", "replace").strip()
    if r.returncode != 0:
        die("the store REFUSED the closing record (index.py exit %d): %s\n"
            "watch: nothing was written — %s is still open"
            % (r.returncode, err or out, oid), 5)
    print("CLOSED %s by %s — %s" % (oid, out or "(new record)", stmt))
    print("       ran: %s" % ran)
    print("       command: %s (exit %d)" % (command, a.exit_code))
    if a.exit_code != 0:
        print("       note: the closing check FAILED (exit %d). The question is closed "
              "because the failure settled it, not because it passed." % a.exit_code)
    print("COORD line: - [%s] [watch] close %s -> closed by %s | evidence: %s exit %d"
          % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"), oid,
             out or "the new record", command, a.exit_code))
    return 0


# ── probe ───────────────────────────────────────────────────────────────────
def cache_path(root):
    return wdir(root) / ".probe-cache.json"


def load_cache(root):
    try:
        return json.loads(cache_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(root, cache):
    try:
        p = cache_path(root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def fetch(url, method, timeout, headers=None):
    """(status, headers, body, error) — never raises. A dead source is an outcome."""
    req = urequest.Request(url, method=method)
    for k, v in dict(UA, **(headers or {})).items():
        req.add_header(k, v)
    try:
        with urequest.urlopen(req, timeout=timeout) as r:
            body = r.read() if method == "GET" else b""
            status = getattr(r, "status", None) or getattr(r, "code", None) or 200
            return status, dict(r.headers), body, None
    except uerror.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return e.code, dict(e.headers or {}), body, None
    except (uerror.URLError, OSError, ValueError) as e:
        reason = getattr(e, "reason", e)
        return None, {}, b"", "%s: %s" % (e.__class__.__name__, reason)


def cmd_probe(a):
    p, lines, rows = parse_watchlist(a.root)
    lines, rows, migrated = ensure_hash_column(p, lines, rows)
    if migrated:
        print("watch: added the Hash column to watchlist.md (the table predated it)")
    row = next((r for r in rows if r.id.lower() == a.row_id.lower()), None)
    if row is None:
        die("no row %r in %s (ids: %s)" % (a.row_id, p, ", ".join(r.id for r in rows)))
    url, src = (a.url, "--url override") if a.url else source_url(row, a.root)
    if not URL_RE.match(url or ""):
        die("row %s has no fetchable source URL — %s. An unwatchable claim should never "
            "have been added; retire the row or source it with /factcheck."
            % (row.id, src or "the Source cell holds %r" % url))
    if src:
        print("watch: %s resolved to %s" % (src, url))
    stored = row.get("hash")
    cache = load_cache(a.root)
    val = cache.get(row.id, {})

    hstatus, hhead, _b, herr = fetch(url, "HEAD", a.timeout)
    # Conditional on a STRONG ETag only. `If-Modified-Since` is deliberately never sent:
    # HTTP dates have one-second granularity, so a page edited within the same second as
    # the last check answers 304 while its bytes have changed — a watch that reports
    # UNCHANGED over real drift. A weak ETag (W/"…") promises only semantic equivalence
    # and is refused for the same reason. The saving was bandwidth; the cost was findings.
    cond = {}
    etag = val.get("etag", "")
    if etag and not etag.startswith("W/"):
        cond["If-None-Match"] = etag
    status, head, body, err = fetch(url, "GET", a.timeout, cond)

    def out(verdict, digest, extra=""):
        print("PROBE %s verdict=%s head=%s http=%s sha256=%s stored=%s%s"
              % (row.id, verdict, hstatus if hstatus is not None else "ERR",
                 status if status is not None else "ERR", digest or "-",
                 stored or "-", extra))

    # A source that cannot be reached is a fact about the SOURCE. Resolved here,
    # at zero model tokens — and never as a refutation of the claim.
    if status is None or status >= 400:
        out("DEAD-SOURCE", "", "  reason=%s" % (err or herr or "HTTP %s" % status))
        print("note: DEAD-SOURCE is a fact about the source, not about the claim — "
              "the claim is not refuted.")
        sys.exit(4)
    if status == 304:
        out("UNCHANGED", stored, "  (304 Not Modified — strong-ETag conditional GET)")
        sys.exit(0)

    digest = hashlib.sha256(body).hexdigest()[:16]
    # last-modified is recorded for the reader, never used as a validator (see above).
    cache[row.id] = {"etag": head.get("ETag", ""),
                     "last-modified": head.get("Last-Modified", ""),
                     "sha256": digest, "url": url, "at": str(date.today())}
    save_cache(a.root, cache)

    if stored and stored == digest:
        out("UNCHANGED", digest)
        sys.exit(0)

    scratch = pathlib.Path(a.scratch or os.environ.get("WATCH_SCRATCH")
                           or os.path.join(tempfile.gettempdir(), "notrest-watch"))
    scratch.mkdir(parents=True, exist_ok=True)
    bp = scratch / ("%s-%s.body" % (row.id, date.today()))
    bp.write_bytes(body)
    first = not stored
    if first:
        # First observation: record the baseline so the NEXT probe can resolve for free.
        # A changed hash is never written here — that would retire the drift before a
        # model ever judged it. `append` banks the new hash when the verdict is recorded.
        row.set("hash", digest)
        lines[row.idx] = row.render()
        write_lines(p, lines)
    out("BASELINE" if first else "CHANGED", digest, "  body=%s" % bp)
    print("note: %s — the model reads %s and judges it; nothing else here needs one."
          % ("no stored hash, baseline recorded" if first else
             "content moved since the stored hash", bp))
    sys.exit(3)


# ── append ──────────────────────────────────────────────────────────────────
def cmd_append(a):
    raw = sys.stdin.read() if a.json == "-" else pathlib.Path(a.json).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except ValueError as e:
        die("--json is not valid JSON: %s" % e)
    findings = data.get("findings") or []
    if not findings:
        die("no findings — a recheck that writes nothing is a recheck nobody can audit")
    p, lines, rows = parse_watchlist(a.root)
    lines, rows, _m = ensure_hash_column(p, lines, rows)
    by_id = dict((r.id.lower(), r) for r in rows)
    when = data.get("date") or str(date.today())

    fetched, seen = [], set()
    for f in findings:
        u, code = (f.get("url") or "").strip(), str(f.get("http") or "").strip()
        if u and u not in seen:
            seen.add(u)
            fetched.append("%s (%s)" % (u, code or "?"))
    for extra in data.get("also_fetched") or []:
        if extra not in seen:
            seen.add(extra)
            fetched.append(extra)

    # The honesty stamp, as an exit code rather than a hope.
    for f in findings:
        fid, st = str(f.get("id", "")).strip(), str(f.get("status", "")).strip().upper()
        if fid.lower() not in by_id:
            die("finding %r names no row in %s" % (fid, p), 5)
        if st not in STATUSES:
            die("finding %s has status %r — must be one of %s" % (fid, st, "/".join(STATUSES)), 5)
        if st == "HOLDS" and not (f.get("url") or "").strip():
            die("finding %s is HOLDS with no URL: 'unchanged' requires the source actually "
                "re-read this run, and its URL on the Fetched-this-run line" % fid, 5)
        if st == "DRIFTED" and not (f.get("note") or "").strip():
            die("finding %s is DRIFTED with no note — drift is announced with the "
                "contradicting evidence read this run, never smoothed" % fid, 5)

    counts = dict((s, 0) for s in STATUSES)
    for f in findings:
        counts[str(f["status"]).strip().upper()] += 1
    n_due = data.get("due", len(findings))
    gap = n_due - len(findings)
    if gap != len(data.get("unchecked") or []):
        die("'due': %s with %d findings and %d 'unchecked' — the Result counts must "
            "account for every due row. Name the rows the budget skipped in 'unchecked' "
            "(they keep their old Last checked date); never shrink the denominator."
            % (n_due, len(findings), len(data.get("unchecked") or [])), 5)
    searches = int(data.get("searches", 0))

    body = ["## %s — recheck cycle" % when,
            "**Result:** %s (of %s due)"
            % (" · ".join("%d %s" % (counts[s], s) for s in STATUSES), n_due),
            "**Fetched this run:** %s"
            % " · ".join(fetched + ["%d search%s" % (searches,
                                                    "" if searches == 1 else "es")])]
    for f in sorted(findings, key=lambda f: ORDER[str(f["status"]).strip().upper()]):
        st = str(f["status"]).strip().upper()
        row = by_id[str(f["id"]).strip().lower()]
        line = "- %s %s — %s %s" % (MARK[st], st, row.id, row.claim)
        note = (f.get("note") or "").strip()
        if note:
            line += " — %s" % note
        if f.get("url"):
            line += " [cited: %s]" % f["url"]
        if st == "DEAD-SOURCE":
            line += " — the source died, the claim did not: this is not a refutation."
        if f.get("chain"):
            line += " → %s" % f["chain"]
        body.append(line)
    if data.get("not_due"):
        body.append("**Not due:** %s" % " · ".join(data["not_due"]))
    if data.get("unchecked"):
        body.append("**Not checked (budget):** %s — these rows keep their old Last checked date."
                    % " · ".join(data["unchecked"]))
    block = "\n".join(body)

    log = wdir(a.root) / "drift-log.md"
    old = log.read_text(encoding="utf-8") if log.exists() else (
        "# drift-log — dated recheck cycles\n"
        "> Append-only, newest block at the bottom. Written by `/watch run` only.\n")
    if block in old:
        print("watch: this exact block is already in the drift log — nothing appended "
              "(append is safe to re-run).")
        sys.exit(0)

    # Both files are fully prepared in memory before EITHER lands, and each lands via
    # os.replace, so no reader ever sees a half-written file.
    for f in findings:
        row = by_id[str(f["id"]).strip().lower()]
        row.set("last checked", when)
        row.set("status", str(f["status"]).strip().upper())
        if f.get("hash"):
            row.set("hash", str(f["hash"]).strip())
        lines[row.idx] = row.render()
    new_log = old.rstrip("\n") + "\n\n" + block + "\n"
    tmp_log = log.with_name(log.name + ".tmp")
    log.parent.mkdir(parents=True, exist_ok=True)
    tmp_log.write_text(new_log, encoding="utf-8")
    tmp_list = p.with_name(p.name + ".tmp")
    tmp_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(str(tmp_list), str(p))
    os.replace(str(tmp_log), str(log))

    print(block)
    print("\nwatch: appended to %s · updated %d row(s) in %s"
          % (log, len(findings), p))
    print("COORD line: - [%s] [watch] recheck: %s due -> %d holds / %d drifted / %d dead "
          "| evidence: watch/drift-log.md %s"
          % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ"), n_due, counts["HOLDS"],
             counts["DRIFTED"], counts["DEAD-SOURCE"], when))


def main():
    ap = argparse.ArgumentParser(description="watch — due computation, source probing, "
                                             "and the atomic drift-log write")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ad = sub.add_parser("add"); ad.add_argument("--root", default=".")
    ad.add_argument("--from-findings", action="store_true", dest="from_findings")
    ad.add_argument("--cadence", default="",
                    choices=[""] + sorted(set(CADENCE_DAYS) | {"on-demand", "retired"}))
    ad.add_argument("--today"); ad.set_defaults(f=cmd_add)
    d = sub.add_parser("due"); d.add_argument("--root", default=".")
    d.add_argument("--today"); d.set_defaults(f=cmd_due)
    pr = sub.add_parser("probe"); pr.add_argument("row_id")
    pr.add_argument("--root", default="."); pr.add_argument("--url")
    pr.add_argument("--scratch"); pr.add_argument("--timeout", type=float, default=10)
    pr.set_defaults(f=cmd_probe)
    ap_ = sub.add_parser("append"); ap_.add_argument("--json", required=True)
    ap_.add_argument("--root", default="."); ap_.set_defaults(f=cmd_append)
    cl = sub.add_parser("close", help="close an open question (O-<n>) by recording the "
                                      "check that closed it, citing the open id")
    cl.add_argument("open_id", metavar="O-<n>")
    cl.add_argument("--root", default=".")
    cl.add_argument("--exit", dest="exit_code", type=int, required=True,
                    help="the integer exit code of the closing check — 'it worked' is "
                         "not an exit code")
    cl.add_argument("--command", default="",
                    help="the exact command that ran (default: the record's closes_when)")
    cl.add_argument("--ran", default="", help="what was run, in words")
    cl.add_argument("--note", default="",
                    help="what the check settled; REQUIRED when --exit is non-zero")
    cl.add_argument("--session", default="")
    cl.set_defaults(f=cmd_close)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
