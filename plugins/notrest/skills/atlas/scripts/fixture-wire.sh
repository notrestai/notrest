#!/bin/bash
# fixture-wire.sh — asserts atlas_wire.py: the HUB-CONTRACT §4 table, the SCHEMA-v1 wire,
# and the http push against a hub bound to 127.0.0.1 and nothing else.
#
# It never touches the real repository (every input is written into a mktemp dir), never
# reaches a network address other than loopback, and mints its own throwaway ingest
# secret — no real credential is read, and the fixture's own log is grep-armed to prove
# the secret value never appeared in a line this harness printed.
#
# The hub is A1's mockhub.py when that file exists and answers a probe push; otherwise
# this fixture starts its own minimal loopback stub, and SAYS SO in its output. The arms
# are identical either way, so the verdict is about atlas_wire.py and not about which
# hub answered.
#
# Usage: bash <atlas-skill>/scripts/fixture-wire.sh      (exit 0 = every assertion held)
# ATLAS_WIRE overrides the module under test — the estate's red-first convention: an arm
# must be shown to FAIL against a mutated module before it is trusted to pass here.
set -u
unset GIT_DIR GIT_INDEX_FILE GIT_PREFIX GIT_WORK_TREE
unset NOTREST_HOME ATLAS_HUB_BASE

HERE="$(cd "$(dirname "$0")" && pwd)"
AW="${ATLAS_WIRE:-$HERE/atlas_wire.py}"
MOCK="$HERE/mockhub.py"
PY="${PYTHON:-/usr/bin/python3}"
W="$(mktemp -d)"
LOG="$W/fixture.log"
HUBPID=""
cleanup(){ [ -n "$HUBPID" ] && kill "$HUBPID" 2>/dev/null; wait "$HUBPID" 2>/dev/null; rm -rf "$W"; return 0; }
trap cleanup EXIT

PASS=0; FAIL=0
say(){ echo "$1" | tee -a "$LOG" >/dev/null; echo "$1"; }
ok(){ PASS=$((PASS+1)); say "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); say "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
# LITERAL containment: a `case` pattern would read "[a-z][a-z0-9-]{0,31}" as a glob
# character class and match text that does not contain it at all.
inn(){ if printf '%s' "$2" | grep -qF -- "$3"; then ok "$1"; else no "$1 — [$3] not in [$2]"; fi; }
notin(){ if printf '%s' "$2" | grep -qF -- "$3"; then no "$1 — [$3] found in [$2]"; else ok "$1"; fi; }

OUTF="$W/out"; ERRF="$W/err"
run(){ "$@" >"$OUTF" 2>"$ERRF"; RC=$?; cat "$OUTF" "$ERRF" >> "$LOG" 2>/dev/null; return $RC; }

# ── the throwaway ingest secret. mockhub.py mints exactly this value per project, so the
#    arms read the same either way. It is a fixture value; it is still never echoed.
PROJ="notrest-plugin"
SECRET="mock-ingest-$PROJ"
export NOTREST_HOME="$W/home"
mkdir -p "$NOTREST_HOME/credentials"
CRED="$W/cred-ingest"; printf '%s\n' "$SECRET" > "$CRED"; chmod 600 "$CRED"
BADCRED="$W/cred-bad"; printf 'not-the-ingest-secret\n' > "$BADCRED"; chmod 600 "$BADCRED"

say "atlas_wire fixture · $AW"

# ───────────────────────────────────────────────────────────────────────────────
# the helpers this fixture writes into its own scratch dir
# ───────────────────────────────────────────────────────────────────────────────
cat > "$W/q.py" <<'PY'
# q.py WIRE node part field  -> the field, or ABSENT / NO-SUCH-NODE / NO-SUCH-PART
import json, sys
w = json.load(open(sys.argv[1]))
n = next((x for x in w.get("nodes", []) if x.get("id") == sys.argv[2]), None)
if n is None:
    print("NO-SUCH-NODE"); raise SystemExit(0)
if len(sys.argv) == 4:
    print(json.dumps(n.get(sys.argv[3], "ABSENT"))); raise SystemExit(0)
p = next((x for x in n.get("parts", []) if x.get("id") == sys.argv[3]), None)
if p is None:
    print("NO-SUCH-PART"); raise SystemExit(0)
print(p.get(sys.argv[4], "ABSENT"))
PY

cat > "$W/top.py" <<'PY'
# top.py WIRE key [subkey] -> a top-level field as compact JSON
import json, sys
w = json.load(open(sys.argv[1]))
v = w.get(sys.argv[2], "ABSENT")
if len(sys.argv) > 3 and isinstance(v, dict):
    v = v.get(sys.argv[3], "ABSENT")
print(v if isinstance(v, str) else json.dumps(v, sort_keys=True, separators=(",", ":")))
PY

cat > "$W/ids.py" <<'PY'
# ids.py WIRE -> one line per id that breaks the address law; silence = clean
import json, sys
w = json.load(open(sys.argv[1]))
bad = []
for n in w.get("nodes", []):
    ids = [("node", n.get("id"))] + [("part", p.get("id")) for p in n.get("parts", [])]
    for kind, i in ids:
        s = i if isinstance(i, str) else repr(i)
        if not isinstance(i, str) or not s or "." in s or s != s.strip() or \
                any(c.isspace() for c in s):
            bad.append("%s id %r" % (kind, s))
for b in bad:
    print(b)
PY

# the SCHEMA-v1 checker — written from briefs/atlas-contract/SCHEMA-v1.md, deliberately
# NOT sharing code with the converter: a checker that imports the thing it checks agrees
# with it by construction.
cat > "$W/check_wire.py" <<'PY'
import json, re, sys
from datetime import datetime

KINDS = {"product", "component", "agent", "surface", "capability", "module",
         "service", "contract", "host", "other"}
EDGE_KINDS = {"authority", "data", "effect", "evidence", "control", "composes",
              "implements", "other"}
EVIDENCE = {"proven", "unverified", "stale", "failing"}
FRESH = {"available", "stale", "unknown", "unsupported"}
STATES = {"todo", "wip", "done"}
COUPLE = {"todo": set(), "wip": {"failing", "unverified", "stale"},
          "done": {"proven", "unverified", "stale"}}
CAP = 4096
E = []


def bad(path, fact):
    E.append("%s: %s" % (path, fact))


def s_ok(path, v, required=True):
    if v is None and not required:
        return False
    if not isinstance(v, str) or not v.strip():
        bad(path, "not a non-empty string"); return False
    if len(v) > CAP:
        bad(path, "%d chars exceeds limit %d" % (len(v), CAP)); return False
    return True


def id_ok(path, v):
    if not s_ok(path, v):
        return False
    if "." in v:
        bad(path, 'contains "." — ids are addresses'); return False
    if v != v.strip():
        bad(path, "carries leading or trailing whitespace"); return False
    return True


def parses(v):
    for f in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            datetime.strptime(v, f); return True
        except ValueError:
            pass
    return False


w = json.load(open(sys.argv[1]))
project = sys.argv[2] if len(sys.argv) > 2 else None
if w.get("schema_version") != "atlas-hub/1":
    bad("schema_version", 'expected "atlas-hub/1", got %r' % w.get("schema_version"))
if not re.match(r"^[a-z][a-z0-9-]{0,31}$", str(w.get("project", ""))):
    bad("project", "does not match [a-z][a-z0-9-]{0,31}")
elif project and w["project"] != project:
    bad("project", "does not equal the URL segment %r" % project)
s_ok("stamp", w.get("stamp"))
if s_ok("taken_at", w.get("taken_at")):
    if not w["taken_at"].endswith("Z"):
        bad("taken_at", "does not end in Z")
    elif not parses(w["taken_at"]):
        bad("taken_at", "ends in Z but is not a date")
if "playbook" in w:
    s_ok("playbook", w["playbook"])
if "head" in w and not re.match(r"^[0-9a-f]{7,40}$", str(w["head"])):
    bad("head", "not 7-40 lowercase hex")
src = w.get("sources")
if src is not None:
    if not isinstance(src, dict):
        bad("sources", "not an object")
    else:
        if len(src) > 32:
            bad("sources", "%d entries exceeds limit 32" % len(src))
        for k, v in src.items():
            if v not in FRESH:
                bad("sources.%s" % k, "not one of %s (got %r)" % ("|".join(sorted(FRESH)), v))
nodes = w.get("nodes")
if not isinstance(nodes, list) or not nodes:
    bad("nodes", "not a non-empty array")
    nodes = []
if len(nodes) > 500:
    bad("nodes", "%d exceeds limit 500" % len(nodes))
seen_nodes, addr = set(), set()
total = 0
for i, n in enumerate(nodes):
    p = "nodes[%d]" % i
    if not isinstance(n, dict):
        bad(p, "not an object"); continue
    if id_ok(p + ".id", n.get("id")):
        if n["id"] in seen_nodes:
            bad(p + ".id", "duplicate %r" % n["id"])
        seen_nodes.add(n["id"])
    if n.get("kind") not in KINDS:
        bad(p + ".kind", "not one of %s (got %r)" % ("|".join(sorted(KINDS)), n.get("kind")))
    parts = n.get("parts")
    if not isinstance(parts, list):
        bad(p + ".parts", "not an array"); continue
    seen_parts = set()
    for j, q in enumerate(parts):
        pp = "%s.parts[%d]" % (p, j)
        total += 1
        if not isinstance(q, dict):
            bad(pp, "not an object"); continue
        if id_ok(pp + ".id", q.get("id")):
            if q["id"] in seen_parts:
                bad(pp + ".id", "duplicate %r within the node" % q["id"])
            seen_parts.add(q["id"])
            addr.add("%s.%s" % (n.get("id"), q["id"]))
        st = q.get("status")
        if st not in STATES:
            bad(pp + ".status", "not one of todo|wip|done (got %r)" % st)
            st = None
        ev = q.get("evidence")
        if ev is not None:
            if ev not in EVIDENCE:
                bad(pp + ".evidence", "not one of %s (got %r)"
                    % ("|".join(sorted(EVIDENCE)), ev))
            elif st and ev not in COUPLE[st]:
                bad(pp + ".evidence", "status %r may not carry evidence %r" % (st, ev))
        if ev == "proven" and not str(q.get("check") or "").strip():
            bad(pp + ".check", 'evidence "proven" requires a non-empty check')
        for k in ("label", "title", "check"):
            if k in q:
                s_ok("%s.%s" % (pp, k), q[k])
if total > 5000:
    bad("parts", "%d exceeds limit 5000" % total)
edges = w.get("edges")
if edges is not None:
    if not isinstance(edges, list):
        bad("edges", "not an array")
    else:
        if len(edges) > 5000:
            bad("edges", "%d exceeds limit 5000" % len(edges))
        sig = set()
        for i, e in enumerate(edges):
            p = "edges[%d]" % i
            if not isinstance(e, dict):
                bad(p, "not an object"); continue
            for end in ("from", "to"):
                v = e.get(end)
                if not isinstance(v, str) or (v not in seen_nodes and v not in addr):
                    bad("%s.%s" % (p, end), "unknown id %r" % v)
            if e.get("kind") not in EDGE_KINDS:
                bad(p + ".kind", "not one of %s" % "|".join(sorted(EDGE_KINDS)))
            a, b = str(e.get("from")), str(e.get("to"))
            if a.split(".", 1)[0] == b.split(".", 1)[0]:
                bad(p, "self or intra-node edge")
            k = (a, b, e.get("kind"), e.get("relation"))
            if k in sig:
                bad(p, "duplicate edge")
            sig.add(k)
f = w.get("findings")
if f is not None:
    if not isinstance(f, dict):
        bad("findings", "not an object")
    else:
        for k, v in f.items():
            if k not in ("count", "recurring"):
                bad("findings.%s" % k, "not allowed — the wire is counts only")
            elif not isinstance(v, int) or isinstance(v, bool) or v < 0:
                bad("findings.%s" % k, "not a non-negative integer")
links = w.get("links")
if links is not None:
    if not isinstance(links, list):
        bad("links", "not an array")
    else:
        for i, l in enumerate(links):
            if not isinstance(l, dict):
                bad("links[%d]" % i, "not an object"); continue
            s_ok("links[%d].label" % i, l.get("label"))
            if s_ok("links[%d].url" % i, l.get("url")) and \
                    not str(l["url"]).startswith("https://"):
                bad("links[%d].url" % i, "not https://")
for e in E:
    print(e)
sys.exit(1 if E else 0)
PY

# the snapshot generator: one part per row of the HUB-CONTRACT §4 table
cat > "$W/mksnap.py" <<'PY'
import json, sys
ROWS = [
    ("row-done-passed",    "done",    "passed",        "echo proof"),
    ("row-done-none",      "done",    "none",          ""),
    ("row-done-unfals",    "done",    "unfalsifiable", "true"),
    ("row-done-failed",    "done",    "failed",        "false"),
    ("row-wip-failed",     "wip",     "failed",        "false"),
    ("row-wip-passed",     "wip",     "passed",        "echo proof"),
    ("row-wip-none",       "wip",     "none",          ""),
    ("row-planned",        "planned", "none",          ""),
    ("row-planned-passed", "planned", "passed",        "echo proof"),
    ("row-blocked",        "blocked", "none",          ""),
    ("row-blocked-failed", "blocked", "failed",        "false"),
    ("row-done-nocheck",   "done",    "passed",        ""),
    ("row-done-notrun",    "done",    "not-run",       "echo proof"),
]
parts = [{"id": "t:%s" % i, "title": "the %s row" % i, "claim": s, "status": s,
          "evidence": e, "test": c, "paths": [], "source": "map"}
         for i, s, e, c in ROWS]
parts.append({"id": "mod.with.dots:x.y", "title": "an id carrying dots", "claim": "done",
              "status": "done", "evidence": "passed", "test": "echo dots", "source": "map"})
parts.append({"id": "plain part", "title": "an id carrying whitespace", "claim": "wip",
              "status": "wip", "evidence": "none", "test": "", "source": "map"})
snap = {"schema": "notrest.atlas/1", "estate": "fixture-estate",
        "commit": sys.argv[2], "parent": "", "branch": "main",
        "ts": "2026-09-06T12:00:00Z", "generator": "fixture",
        "sources": {"map": {"ok": True, "parts": len(parts), "file": "atlas/map.md"},
                    "gates": {"ok": False, "reason": "no gates"}},
        "parts": parts,
        "summary": {"parts": len(parts), "done": 2, "wip": 6, "planned": 2, "blocked": 2,
                    "failing": 3, "red": False},
        "findings": {"count": 7, "recurring": 2, "note": "prose that must never ship"}}
json.dump(snap, open(sys.argv[1], "w"), indent=1, sort_keys=True)
PY

# a snapshot whose wire is deliberately over the hub's 2 MiB body cap
cat > "$W/mkbig.py" <<'PY'
import json, sys
label = "L" * 4000
check = "C" * 4000
parts = [{"id": "big:p%04d" % i, "title": label, "claim": "done", "status": "done",
          "evidence": "passed", "test": check, "source": "map"} for i in range(300)]
snap = {"schema": "notrest.atlas/1", "estate": "fixture-estate",
        "commit": "b" * 40, "ts": "2026-09-06T12:00:00Z", "parts": parts,
        "sources": {"map": {"ok": True}}, "summary": {"parts": len(parts)}}
json.dump(snap, open(sys.argv[1], "w"))
PY

# post a wire the converter would never emit, through the module's own transport half
cat > "$W/post_raw.py" <<'PY'
import importlib.util, json, sys
# load the module UNDER TEST by PATH — ATLAS_WIRE must really override, and a mutant
# under another filename must be the thing this arm exercises.
spec = importlib.util.spec_from_file_location("atlas_wire_under_test", sys.argv[1])
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
wire = json.load(open(sys.argv[2]))
secret = open(sys.argv[3]).read().strip()     # BY PATH — the value never rides in argv
ok, head, reason = A.post_wire(wire, None, secret, sys.argv[4], sys.argv[5], 20)
print(reason)
sys.exit(0 if ok else 4)
PY

# the fallback hub: loopback only, silent, and just the endpoints these arms need
cat > "$W/stubhub.py" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LAST = {}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return                       # a request line is never logged, a header never seen

    def reply(self, code, obj, ctype="application/json"):
        b = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        seg = [s for s in self.path.split("?")[0].strip("/").split("/") if s]
        if len(seg) != 3 or seg[0] != "v1" or seg[1] not in ("snapshot", "board"):
            return self.reply(404, {"error": "not found"})
        project = seg[2]
        limit = 2 * 1024 * 1024 if seg[1] == "snapshot" else 4 * 1024 * 1024
        if len(body) > limit:
            return self.reply(413, {"error": "body: %d bytes exceeds limit %d"
                                             % (len(body), limit)})
        if (self.headers.get("Authorization") or "") != "Bearer mock-ingest-%s" % project:
            return self.reply(401, {"error": "authorization: bad bearer"})
        if seg[1] == "board":
            return self.reply(201, {"stored": "board:%s" % project, "project": project,
                                    "bytes": len(body)})
        try:
            wire = json.loads(body.decode("utf-8"))
        except Exception:
            return self.reply(400, {"error": "body: not parseable JSON"})
        if wire.get("schema_version") not in ("atlas-hub/0", "atlas-hub/1"):
            return self.reply(422, {"error": 'schema_version: expected one of '
                                             '"atlas-hub/0" | "atlas-hub/1", got %r'
                                             % wire.get("schema_version")})
        for i, node in enumerate(wire.get("nodes") or []):
            for j, part in enumerate(node.get("parts") or []):
                if part.get("evidence") == "proven" and not str(part.get("check") or "").strip():
                    return self.reply(422, {"error": 'nodes[%d].parts[%d].check: evidence '
                                                     '"proven" requires a non-empty check'
                                                     % (i, j)})
        key = (wire.get("head"), hashlib.sha256(body).hexdigest())
        if LAST.get(project) == key:
            return self.reply(200, {"stored": "snap:%s" % project, "project": project,
                                    "idempotent": True})
        LAST[project] = key
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S000Z")
        return self.reply(201, {"stored": "snap:%s:%s" % (project, ts),
                                "project": project,
                                "nodes": len(wire.get("nodes") or [])})


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
sys.stdout.write("%d\n" % srv.server_address[1])
sys.stdout.flush()
srv.serve_forever()
PY

# ───────────────────────────────────────────────────────────────────────────────
say "── A · the §4 status/evidence table, row for row"
COMMIT="0123456789abcdef0123456789abcdef01234567"
SNAP="$W/snap-table.json"
run "$PY" "$W/mksnap.py" "$SNAP" "$COMMIT"; t "the table snapshot is written" "$?" "0"
WIRE="$W/wire-table.json"
"$PY" "$AW" convert "$SNAP" --project "$PROJ" --root "$W" > "$WIRE" 2>"$W/report.txt"
t "convert exits 0" "$?" "0"
cat "$W/report.txt" >> "$LOG"
q(){ "$PY" "$W/q.py" "$WIRE" "$@"; }

t "done/passed          -> status done"        "$(q t row-done-passed status)"    "done"
t "done/passed          -> evidence proven"    "$(q t row-done-passed evidence)"  "proven"
t "…and carries the check the proof needs"     "$(q t row-done-passed check)"     "echo proof"
t "done/none            -> status wip"         "$(q t row-done-none status)"      "wip"
t "done/none            -> evidence unverified" "$(q t row-done-none evidence)"   "unverified"
t "done/unfalsifiable   -> status wip"         "$(q t row-done-unfals status)"    "wip"
t "done/unfalsifiable   -> evidence unverified" "$(q t row-done-unfals evidence)" "unverified"
t "done/failed          -> status wip"         "$(q t row-done-failed status)"    "wip"
t "done/failed          -> evidence failing"   "$(q t row-done-failed evidence)"  "failing"
t "wip/failed           -> status wip"         "$(q t row-wip-failed status)"     "wip"
t "wip/failed           -> evidence failing"   "$(q t row-wip-failed evidence)"   "failing"
t "wip/passed           -> status done"        "$(q t row-wip-passed status)"     "done"
t "wip/passed           -> evidence proven"    "$(q t row-wip-passed evidence)"   "proven"
t "wip/none             -> status wip"         "$(q t row-wip-none status)"       "wip"
t "wip/none             -> evidence unverified" "$(q t row-wip-none evidence)"    "unverified"
t "planned/none         -> status todo"        "$(q t row-planned status)"        "todo"
t "planned/none         -> NO evidence key"    "$(q t row-planned evidence)"      "ABSENT"
t "planned/passed       -> status todo"        "$(q t row-planned-passed status)" "todo"
t "planned/passed       -> NO evidence key"    "$(q t row-planned-passed evidence)" "ABSENT"
t "blocked/none         -> status wip"         "$(q t row-blocked status)"        "wip"
t "blocked/none         -> evidence unverified" "$(q t row-blocked evidence)"     "unverified"
t "blocked/failed       -> status wip"         "$(q t row-blocked-failed status)" "wip"
t "blocked/failed       -> evidence failing"   "$(q t row-blocked-failed evidence)" "failing"
t "done/not-run         -> status wip"         "$(q t row-done-notrun status)"    "wip"
t "done/not-run         -> evidence unverified" "$(q t row-done-notrun evidence)" "unverified"

say "── B · a done with no check is never proven (the guard)"
t "done/passed with NO test -> status wip"      "$(q t row-done-nocheck status)"   "wip"
t "…and evidence unverified, never proven"      "$(q t row-done-nocheck evidence)" "unverified"
t "…and carries no check key"                   "$(q t row-done-nocheck check)"    "ABSENT"
inn "…and the downgrade is REPORTED, not silent" "$(cat "$W/report.txt")" \
    "t.row-done-nocheck: done/passed -> wip/unverified (proven requires a check)"
inn "the demoted done rows are reported too" "$(cat "$W/report.txt")" \
    "t.row-done-failed: done/failed -> wip/failing"
inn "a promotion is reported as a promotion" "$(cat "$W/report.txt")" \
    "PROMOTED t.row-wip-passed: wip/passed -> done/proven"
t "…and the counts line names every bucket" \
  "$(grep -c 'proven=3 unverified=7 failing=3 todo=2' "$W/report.txt")" "1"

say "── C · ids are addresses, and findings are counts"
IDBAD="$("$PY" "$W/ids.py" "$WIRE")"
t "no id carries a '.' or whitespace" "$(printf '%s' "$IDBAD" | grep -c . )" "0"
t "a dotted PART GROUP becomes one node"  "$(q mod-with-dots x-y status)" "done"
inn "…and the rename is reported"  "$(cat "$W/report.txt")" \
    "RENAMED mod.with.dots:x.y -> mod-with-dots.x-y"
t "an id with whitespace lands under the estate node" \
  "$(q fixture-estate plain-part status)" "wip"
t "findings carries the count"      "$("$PY" "$W/top.py" "$WIRE" findings)" \
  '{"count":7,"recurring":2}'
inn "…and the prose key is dropped, loudly" "$(cat "$W/report.txt")" \
    "findings.note: dropped — the wire is counts only"
t "head is the snapshot's commit" "$("$PY" "$W/top.py" "$WIRE" head)" "$COMMIT"
"$PY" "$AW" convert "$SNAP" --project "$PROJ" --root "$W" > "$W/w-up.json" 2>/dev/null
run "$PY" "$W/mksnap.py" "$W/snap-up.json" "$(echo "$COMMIT" | tr 'a-f' 'A-F')"
"$PY" "$AW" convert "$W/snap-up.json" --project "$PROJ" --root "$W" > "$W/w-up.json" 2>/dev/null
t "an uppercase-hex commit is lowercased, not dropped" \
  "$("$PY" "$W/top.py" "$W/w-up.json" head)" "$COMMIT"
run "$PY" "$W/mksnap.py" "$W/snap-bh.json" "abc1234-dirty"
"$PY" "$AW" convert "$W/snap-bh.json" --project "$PROJ" --root "$W" > "$W/w-bh.json" 2>"$W/rep-bh.txt"
t "a commit that is not a commit is OMITTED, never guessed" \
  "$("$PY" "$W/top.py" "$W/w-bh.json" head)" "ABSENT"
inn "…and the omission is reported" "$(cat "$W/rep-bh.txt")" \
    "head: 'abc1234-dirty' is not a 7-40 char lowercase hex commit"
t "…sources.git then reads unknown, honestly" \
  "$("$PY" "$W/top.py" "$W/w-bh.json" sources git)" "unknown"
run "$PY" "$W/check_wire.py" "$W/w-bh.json" "$PROJ"
t "…and the headless wire still validates" "$?" "0"
t "playbook is declared"          "$("$PY" "$W/top.py" "$WIRE" playbook)" "2.0"
t "taken_at is the snapshot's ts" "$("$PY" "$W/top.py" "$WIRE" taken_at)" "2026-09-06T12:00:00Z"
t "sources.git reads available"   "$("$PY" "$W/top.py" "$WIRE" sources git)" "available"
t "sources.tests reads available" "$("$PY" "$W/top.py" "$WIRE" sources tests)" "available"
[ -n "$("$PY" "$W/top.py" "$WIRE" stamp)" ] && ok "a stamp is always present" \
  || no "the wire has no stamp"
t "no board_url means no links key" "$("$PY" "$W/top.py" "$WIRE" links)" "ABSENT"
"$PY" "$AW" convert "$SNAP" --project "$PROJ" --root "$W" --board-url http://evil.example \
  > "$W/wire-http.json" 2>"$W/report-http.txt"
t "an http board_url yields no links key" "$("$PY" "$W/top.py" "$W/wire-http.json" links)" "ABSENT"
inn "…and says why" "$(cat "$W/report-http.txt")" "is not an https:// URL"
"$PY" "$AW" convert "$SNAP" --project "$PROJ" --root "$W" \
  --board-url https://atlas.not.rest/v1/board/notrest-plugin > "$W/wire-https.json" 2>/dev/null
inn "an https board_url becomes a link" "$("$PY" "$W/top.py" "$W/wire-https.json" links)" \
    "https://atlas.not.rest/v1/board/notrest-plugin"

say "── D · the wire validates against SCHEMA-v1 (an independent checker)"
run "$PY" "$W/check_wire.py" "$WIRE" "$PROJ"; t "the table wire validates" "$?" "0"
[ -s "$OUTF" ] && say "        $(cat "$OUTF")"
# red-first: the checker must REFUSE the shapes the converter refuses to emit
mkbad(){ "$PY" - "$WIRE" "$1" "$2" <<'PY'
import json, sys
w = json.load(open(sys.argv[1]))
kind = sys.argv[3]
if kind == "proven-no-check":
    p = w["nodes"][0]["parts"][0]; p["evidence"] = "proven"; p.pop("check", None)
elif kind == "dotted-id":
    w["nodes"][0]["id"] = "a.b"
elif kind == "findings-text":
    w["findings"] = {"count": 1, "note": "prose"}
elif kind == "bad-taken-at":
    w["taken_at"] = "2026-13-45T99:99:99Z"
elif kind == "done-failing":
    p = w["nodes"][0]["parts"][0]; p["status"] = "done"; p["evidence"] = "failing"
elif kind == "no-kind":
    w["nodes"][0].pop("kind", None)
json.dump(w, open(sys.argv[2], "w"))
PY
}
for K in proven-no-check dotted-id findings-text bad-taken-at done-failing no-kind; do
  mkbad "$W/bad.json" "$K"
  run "$PY" "$W/check_wire.py" "$W/bad.json" "$PROJ"
  t "the checker REFUSES $K" "$?" "1"
done
mkbad "$W/bad.json" proven-no-check
run "$PY" "$W/check_wire.py" "$W/bad.json" "$PROJ"
inn "…naming the hub's own fact" "$(cat "$OUTF")" 'evidence "proven" requires a non-empty check'

say "── E · this estate's own latest snapshot converts and validates"
REAL="$(ls -t "$HERE/../../../../../atlas/snapshots/"*.json 2>/dev/null | head -1)"
if [ -z "$REAL" ]; then REAL="$(ls -t atlas/snapshots/*.json 2>/dev/null | head -1)"; fi
if [ -n "$REAL" ] && [ -f "$REAL" ]; then
  "$PY" "$AW" convert "$REAL" --project "$PROJ" > "$W/wire-real.json" 2>"$W/report-real.txt"
  t "the real snapshot converts (exit 0)" "$?" "0"
  cat "$W/report-real.txt" >> "$LOG"
  run "$PY" "$W/check_wire.py" "$W/wire-real.json" "$PROJ"
  t "…and its wire validates against SCHEMA-v1" "$?" "0"
  [ -s "$OUTF" ] && say "        $(cat "$OUTF")"
  t "…with no id breaking the address law" \
    "$("$PY" "$W/ids.py" "$W/wire-real.json" | grep -c . )" "0"
  t "…and head = the snapshot's commit" \
    "$("$PY" "$W/top.py" "$W/wire-real.json" head)" \
    "$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["commit"])' "$REAL")"
else
  say "  SKIP  no atlas/snapshots/*.json in this estate to convert"
fi

say "── F · the body cap is refused CLIENT-SIDE, before a byte is sent"
DEAD="http://127.0.0.1:1"
run "$PY" "$AW" push "$SNAP" --project "$PROJ" --credential "$CRED" --base "$DEAD"
t "a small body against a dead port exits 4" "$?" "4"
inn "…and says the hub is unreachable (so the port really is dead)" \
    "$(cat "$OUTF")" "hub unreachable at $DEAD"
run "$PY" "$W/mkbig.py" "$W/snap-big.json"; t "the oversize snapshot is written" "$?" "0"
run "$PY" "$AW" push "$W/snap-big.json" --project "$PROJ" --credential "$CRED" --base "$DEAD"
t "an oversize body exits 4" "$?" "4"
inn "…with the hub's 413 shape" "$(cat "$OUTF")" "413 body:"
inn "…and exceeds limit 2097152" "$(cat "$OUTF")" "exceeds limit 2097152"
inn "…refused client-side: NOTHING was sent to the dead port" "$(cat "$OUTF")" "not sent"
notin "…so it never reported the connection failure" "$(cat "$OUTF")" "unreachable"

# RFC 2606 reserves .invalid: the host can never resolve, so this arm proves the guard
# WITHOUT the fixture ever being able to leave 127.0.0.1 — even under a mutation of it.
say "── G · the bearer never travels over plain http to a non-loopback host"
run "$PY" "$AW" push "$SNAP" --project "$PROJ" --credential "$CRED" --base http://hub.invalid
t "an http:// hub exits 4" "$?" "4"
inn "…refusing before any connection" "$(cat "$OUTF")" \
    "refusing to send the bearer over http to hub.invalid"
run "$PY" "$AW" push "$SNAP" --project "NotAProject" --credential "$CRED" --base "$DEAD"
t "a project id the hub would refuse is refused here" "$?" "4"
inn "…naming the pattern" "$(cat "$OUTF")" "does not match [a-z][a-z0-9-]{0,31}"
run "$PY" "$AW" push "$SNAP" --project "$PROJ" --credential "$W/no-such-file" --base "$DEAD"
t "a missing credential exits 4" "$?" "4"
inn "…naming the PATH, never a value" "$(cat "$OUTF")" "no ingest secret at $W/no-such-file"

say "── H · the push, against a hub on 127.0.0.1"
# NOT a command substitution: that runs in a subshell, and the HUBPID it set would be
# lost — leaving a server bound to a port after this fixture exited. PORT is a global.
start_hub(){
  : > "$W/hub.log"
  "$@" > "$W/hub.log" 2>&1 &
  HUBPID=$!
  disown "$HUBPID" 2>/dev/null || true   # the shell must not print "Terminated" after
                                         # the summary line the caller reads
  for _ in $(seq 1 60); do
    PORT="$(grep -Eo '^[0-9]+$' "$W/hub.log" 2>/dev/null | head -1)"
    [ -n "$PORT" ] && return 0
    kill -0 "$HUBPID" 2>/dev/null || { PORT=""; return 1; }
    sleep 0.1
  done
  PORT=""; return 1
}
HUB=""; PORT=""
if [ -f "$MOCK" ]; then
  start_hub "$PY" "$MOCK" --port 0 --print-port || PORT=""
  if [ -n "$PORT" ]; then
    printf '%s\n' "mock-ingest-notrest-probe" > "$W/cred-probe"
    run "$PY" "$AW" push "$SNAP" --project notrest-probe --credential "$W/cred-probe" \
        --base "http://127.0.0.1:$PORT"
    if [ "$RC" = "0" ]; then HUB="mockhub.py"; else PORT=""; fi
  fi
  [ -z "$PORT" ] && { [ -n "$HUBPID" ] && kill "$HUBPID" 2>/dev/null; HUBPID=""; }
fi
if [ -z "$PORT" ]; then
  start_hub "$PY" "$W/stubhub.py" || PORT=""
  HUB="the fixture's own loopback stub"
  [ -f "$MOCK" ] && say "  NOTE  mockhub.py did not answer a probe push — using the stub"
  [ -f "$MOCK" ] || say "  NOTE  mockhub.py (lane A1) is not present yet — using the stub"
fi
if [ -z "$PORT" ]; then
  no "no hub could be started on 127.0.0.1 — the push arms cannot run"
else
  BASE="http://127.0.0.1:$PORT"
  say "  hub: $HUB on $BASE"
  HEAD="$("$PY" "$W/top.py" "$WIRE" head)"
  printf '<!doctype html><title>fixture board</title><p>board</p>\n' > "$W/board.html"

  run "$PY" "$AW" push "$SNAP" --project "$PROJ" --credential "$CRED" --base "$BASE" \
      --board "$W/board.html"
  t "push exits 0" "$?" "0"
  inn "…and reports the stored key" "$(cat "$OUTF")" "stored snap:$PROJ"
  inn "…and the board landed too" "$(cat "$OUTF")" "board stored"
  t "…and hub_commit IS the head we sent" \
    "$(sed -n 's/.*hub_commit \([0-9a-f]*\) .*/\1/p' "$OUTF")" "$HEAD"

  run "$PY" "$AW" push "$SNAP" --project "$PROJ" --credential "$CRED" --base "$BASE"
  t "the same wire pushed again exits 0" "$?" "0"
  inn "…and is idempotent, not a second store" "$(cat "$OUTF")" "idempotent"
  t "…still carrying the same hub_commit" \
    "$(sed -n 's/.*hub_commit \([0-9a-f]*\) .*/\1/p' "$OUTF")" "$HEAD"

  run "$PY" "$AW" push "$SNAP" --project "$PROJ" --credential "$BADCRED" --base "$BASE"
  t "a bad bearer exits 4" "$?" "4"
  inn "…with the hub's one fact, verbatim" "$(cat "$OUTF")" "401 authorization: bad bearer"

  mkbad "$W/bad-wire.json" proven-no-check
  run "$PY" "$W/post_raw.py" "$AW" "$W/bad-wire.json" "$CRED" "$BASE" "$PROJ"
  t "a wire claiming proven with no check is refused by the hub" "$?" "4"
  inn "…with the hub's 422 text" "$(cat "$OUTF")" \
      'evidence "proven" requires a non-empty check'
  inn "…and the refusal names the path" "$(cat "$OUTF")" "422 nodes["

  say "── I · the legacy credential name warns exactly once"
  mkdir -p "$NOTREST_HOME/credentials"
  printf '%s\n' "$SECRET" > "$NOTREST_HOME/credentials/atlas-token"
  chmod 600 "$NOTREST_HOME/credentials/atlas-token"
  run "$PY" "$AW" push "$W/snap-table.json" --project "$PROJ" --base "$BASE"
  t "a push with no --credential finds the legacy file and exits 0" "$?" "0"
  t "…warning EXACTLY once" \
    "$(grep -c 'reading the legacy ingest secret' "$ERRF")" "1"
  inn "…and naming the new file" "$(cat "$ERRF")" "credentials/atlas-ingest-$PROJ"
  notin "…never the secret itself" "$(cat "$ERRF")" "$SECRET"
  printf '%s\n' "$SECRET" > "$NOTREST_HOME/credentials/atlas-ingest-$PROJ"
  chmod 600 "$NOTREST_HOME/credentials/atlas-ingest-$PROJ"
  run "$PY" "$AW" push "$W/snap-table.json" --project "$PROJ" --base "$BASE"
  t "with the new name present, the push still exits 0" "$?" "0"
  t "…and warns not at all" "$(grep -c 'legacy ingest secret' "$ERRF")" "0"
fi

say "── J · the secret never appears in anything this fixture printed"
cat "$W/hub.log" >> "$LOG" 2>/dev/null
t "the ingest secret value is absent from the whole fixture log" \
  "$(grep -c -- "$SECRET" "$LOG" 2>/dev/null || true)" "0"
t "…and no Bearer header was ever printed" \
  "$(grep -ci -- "authorization: bearer" "$LOG" 2>/dev/null || true)" "0"

say ""
say "atlas_wire fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
