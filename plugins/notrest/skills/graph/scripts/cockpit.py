#!/usr/bin/env python3
"""cockpit.py — one page, always on: the estate live.

The graph skill's other verbs draw a MOMENT (a scan, a river, a journey) and
they are deterministic by law. The cockpit is the other thing: a local window
that stays open while you work, re-reading the estate's own files every few
seconds so the session you are running shows up on a screen instead of in a
scrollback.

  serve [--root .] [--port 8788] [--no-open]

Two laws hold it honest.

  A WINDOW PLUS ONE MAIL SLOT, NOT A CONTROL PANEL. Every route is a read
  except `POST /room/<name>`, which posts a chat line — and that one shells to
  chatroom's own `room.py post`, so the no-secrets screen is chatroom's, not a
  copy. The cockpit adds no gate and bypasses none. There is no endpoint that
  edits a ledger, bumps a version, runs a skill, or writes a finding. If you
  want the estate changed, a session changes it; the cockpit watches.

  THE PICTURES STAY DETERMINISTIC; THE COCKPIT IS LIVE. `/pic/*` regenerates by
  shelling to graph.py, whose byte-identical law is untouched — same inputs,
  same page. The cockpit page itself reads a clock, because a live monitor that
  cannot tell you how stale it is would be worse than no monitor. The staleness
  stamp comes from the RESPONSE header (`X-Cockpit-Generated`), never the
  browser's clock, so the page reports the server's read time, not the viewer's.

Binds 127.0.0.1 only, always. Port 8788 by default and on purpose: doctor's
render-check owns 8790-8799, so the cockpit can stay up while a render is
being gated on the same machine.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# the river's own parsers — importing them means the brief-containment refusal
# here IS the refusal there, not a second copy that can drift from it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph as G                                        # noqa: E402

DEFAULT_PORT = 8788
# The always-on OPT-IN marker. A project that wants its window open says so ONCE, on
# disk, and every later session can find that out without asking the owner to remember
# (2026-08-04: the cockpit was doing exactly what the owner wanted and nothing surfaced
# it — presence is not display). Per-machine state, not shared history: this repo's
# .gitignore already ignores /graph/, and SKILL.md tells user projects to do the same.
ALWAYS_MARKER = "graph/.cockpit-always"
HEALTH_TIMEOUT = 0.5        # a probe, not a wait: status must never hang a session start
COORD_TAIL = 40
AGENT_TAIL = 30
ROOM_TAIL = 40
PIC_DEBOUNCE = 5.0          # seconds; a reload storm must not re-render per hit
POST_CAP = 64 * 1024
CMD_TIMEOUT = 60
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LANES_WINDOW_MIN = 60

PIC = {
    "river":   {"out": "graph/river.html",   "argv": ["river"]},
    "journey": {"out": "graph/journey.html", "argv": ["journey"]},
    "graph":   {"out": "graph/graph.html",   "argv": ["scan"]},
}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(argv, cwd=None, timeout=CMD_TIMEOUT):
    """A sibling script's CLI is its contract — shell it, keep its exit code.
    Never raises: a broken sibling degrades one panel, never the server."""
    try:
        p = subprocess.run(argv, cwd=str(cwd) if cwd else None, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout)
        return (p.returncode, p.stdout.decode("utf-8", "replace"),
                p.stderr.decode("utf-8", "replace"))
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except OSError as exc:
        return 127, "", str(exc)


def skills_dir():
    """.../skills — this script lives at .../skills/graph/scripts/cockpit.py."""
    return pathlib.Path(os.path.abspath(__file__)).parent.parent.parent


def sibling(skill, script):
    p = skills_dir() / skill / "scripts" / script
    return p if p.is_file() else None


def unavailable(what, why):
    return {"available": False, "what": what, "why": why}


# ------------------------------------------------------------------ the panels

def data_coord(root):
    """The active COORD volume's tail, parsed by the river's own line reader."""
    items = G.read_coord_lines(root)
    tail = items[-COORD_TAIL:]
    return {"available": True, "volumes": G.coord_volumes(root),
            "total": len(items), "shown": len(tail),
            "lines": [{"ts": c["ts"], "lane": c["lane"], "ask": c["ask"],
                       "landed": c["landed"], "evidence": c["evidence"],
                       "flag": c["flag"], "ref": c["ref"]} for c in tail]}


def data_agents(root):
    """COORD-AGENTS tail with the commission pointers already resolved — same
    read_agent_lines the river draws its ruled-sheet glyphs from."""
    lanes = G.read_agent_lines(root)
    tail = lanes[-AGENT_TAIL:]
    for l in tail:
        l.pop("_k", None)
    recent = 0
    cutoff = time.time() - LANES_WINDOW_MIN * 60
    for l in tail:
        try:
            t = datetime.strptime(G.tskey(l["ts"]), "%Y-%m-%dT%H:%M:%S")
            if t.replace(tzinfo=timezone.utc).timestamp() >= cutoff:
                recent += 1
        except ValueError:
            pass
    return {"available": True, "total": len(lanes), "shown": len(tail),
            "commissions": sum(1 for l in tail if l["commission"]),
            "recent_window_min": LANES_WINDOW_MIN, "recent": recent,
            # the ledger is written at SubagentStop: it records lanes that
            # FINISHED. Nothing here can count a lane still running, and the
            # panel says so rather than implying a live process count.
            "recent_means": "lanes that FINISHED in the window — the agent ledger "
                            "is written at SubagentStop, so a running lane is not in it",
            "lanes": tail}


def data_brief(root, ident):
    """One banked commission, in full. Containment is graph.read_brief's rule:
    a pointer that resolves outside the root is refused unread."""
    if not SAFE_NAME.match(ident):
        return {"available": False, "why": "unsafe brief id"}, 400
    rel = "briefs/agent-%s.md" % ident if not ident.startswith("agent-") else "briefs/%s.md" % ident
    head, ok, why = G.read_brief(root, rel)
    if not ok:
        return {"available": False, "brief": rel, "state": why,
                "why": {"missing": "no such file — the pointer is dead",
                        "outside-root": "refused unread: the path escapes the root",
                        "unreadable": "the file could not be read",
                        "unresolvable": "the path could not be resolved",
                        "none": "no pointer"}.get(why, why)}, 404
    p = (root / rel)
    text = G._slurp(p) or ""
    body = text.split("\n---\n", 1)[1].strip() if "\n---\n" in text else text
    return {"available": True, "brief": rel, "state": why, "head": head,
            "text": body, "bytes": len(text.encode("utf-8"))}, 200


def data_spend(root):
    s = sibling("spend", "spend.py")
    if not s:
        return unavailable("spend", "spend/scripts/spend.py is not installed")
    rc, out, err = run([sys.executable, str(s), "report", "--json", "--root", str(root)])
    try:
        blob = json.loads(out)
        blob.update({"available": True, "exit": rc,
                     "verdict": "VIOLATION" if rc == 4 else ("CLEAN" if rc == 0 else "exit %d" % rc)})
        return blob
    except ValueError:
        # no --json, or it broke: keep the verdict line rather than nothing
        rc2, out2, err2 = run([sys.executable, str(s), "report", "--root", str(root)])
        line = next((l for l in reversed(out2.splitlines()) if l.strip()), "")
        return {"available": True, "exit": rc2, "json": False, "verdict_line": line[:400],
                "verdict": "VIOLATION" if rc2 == 4 else ("CLEAN" if rc2 == 0 else "exit %d" % rc2),
                "note": (err or err2 or "spend.py has no --json report").strip()[:300]}


def data_pulse(root):
    """The newest `[pulse]` line already in COORD.md — pulse.sh writes it; the
    cockpit never runs a pulse, it reads the one the estate recorded."""
    newest = None
    for fn in G.coord_volumes(root):
        text = G._slurp(root / fn)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = re.match(r"^-\s*\[(?P<ts>[^\]]+)\]\s*\[pulse\]\s*(?P<body>.+)$", line.strip())
            if m:
                k = G.tskey(m.group("ts"))
                if newest is None or k >= newest["_k"]:
                    newest = {"_k": k, "ts": m.group("ts").strip(),
                              "body": m.group("body").strip(), "ref": f"{fn}:{i}"}
    if not newest:
        return unavailable("pulse", "no [pulse] line in any COORD volume — run doctor's pulse.sh")
    body = newest["body"]
    fields = dict(re.findall(r"(\w[\w-]*)=(\S+)", body))
    verdict = "OK"
    for k in ("doctor", "eval"):
        if fields.get(k) not in (None, "0"):
            verdict = "ATTENTION"
    if fields.get("spend") not in (None, "CLEAN"):
        verdict = "ATTENTION"
    return {"available": True, "ts": newest["ts"], "ref": newest["ref"],
            "line": body, "fields": fields, "verdict": verdict}


def data_watch(root):
    """Watchlist rows straight out of the markdown table, plus the newest drift
    block, plus watch.py's own due count (its arithmetic, not a re-derivation)."""
    wl = root / "watch" / "watchlist.md"
    text = G._slurp(wl)
    if text is None:
        return unavailable("watch", "no watch/watchlist.md — nothing under watch")
    rows, source = [], ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            source = s[3:].strip()
            continue
        if not s.startswith("|") or s.startswith("|--") or s.startswith("| ID"):
            continue
        c = [x.strip() for x in s.strip("|").split("|")]
        if len(c) >= 8 and re.match(r"^W\d+$", c[0]):
            rows.append({"id": c[0], "claim": c[1], "source_url": c[2], "tier": c[3],
                         "first": c[4], "last": c[5], "status": c[6], "cadence": c[7],
                         "section": source})
    drift, dtext = "", G._slurp(root / "watch" / "drift-log.md")
    if dtext:
        blocks = dtext.split("\n## ")
        drift = ("## " + blocks[-1]).strip() if len(blocks) > 1 else ""
    due, due_line = None, ""
    w = sibling("watch", "watch.py")
    if w:
        rc, out, err = run([sys.executable, str(w), "due", "--root", str(root)])
        due_line = next((l for l in out.splitlines() if l.strip()), "").strip()
        m = re.search(r"(\d+)\s+due", due_line)
        due = int(m.group(1)) if m else None
    return {"available": True, "rows": rows, "count": len(rows), "due": due,
            "due_line": due_line, "drift_block": drift[:4000],
            "drifted": sum(1 for r in rows if r["status"] not in ("HOLDS",))}


def data_library(root):
    """The shelf: the newest concepts generation and the registered projects."""
    lib = pathlib.Path(os.environ.get("NOTREST_LIBRARY_ROOT")
                       or (pathlib.Path.home() / ".claude" / "notrest-library"))
    cpath, rpath = lib / "concepts.jsonl", lib / "registry.jsonl"
    if not cpath.is_file() and not rpath.is_file():
        return unavailable("library", f"no shelf at {lib} — nothing registered yet")
    concepts, gens = [], {}
    text = G._slurp(cpath) or ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if isinstance(o, dict) and o.get("id"):
            gens.setdefault(str(o.get("ts") or ""), []).append(o)
    if gens:
        concepts = gens[max(gens)]
    projects = []
    rtext = G._slurp(rpath) or ""
    for line in rtext.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if isinstance(o, dict) and o.get("name"):
            projects.append({"name": o["name"], "root": o.get("root", ""),
                             "ts": o.get("ts", ""), "here": o.get("root") == str(root)})
    return {"available": True, "shelf": str(lib), "generation": max(gens) if gens else "",
            "generations": len(gens),
            "concepts": [{"id": c.get("id"), "name": c.get("name") or "?",
                          "status": c.get("status") or "", "settled": c.get("settled"),
                          "cohesion": c.get("cohesion"),
                          "members": len(c.get("members") or []),
                          "projects": c.get("projects") or [],
                          "terms": (c.get("terms") or [])[:6]} for c in concepts],
            "named": sum(1 for c in concepts if (c.get("name") or "?") != "?"),
            "projects": projects}


def data_findings(root):
    idx = sibling("archivist", "index.py")
    if not idx:
        return unavailable("findings", "archivist/scripts/index.py is not installed")
    rc, out, err = run([sys.executable, str(idx), "track", "--json", "--root", str(root)])
    try:
        blob = json.loads(out)
    except ValueError:
        return unavailable("findings", (err or out or "track --json produced no JSON")[:300])
    recs = blob.get("records") or []
    blob["available"] = True
    blob["exit"] = rc
    blob["by_status"] = {s: sum(1 for r in recs if r.get("status") == s)
                         for s in ("live", "superseded", "refuted")}
    blob["records"] = recs[-25:]
    return blob


def data_version(root):
    """Version from the manifest, HEAD from git — the two identities of a tree."""
    ver, where = "", ""
    for cand in (root / "plugins" / "notrest" / ".claude-plugin" / "plugin.json",
                 root / ".claude-plugin" / "plugin.json"):
        t = G._slurp(cand)
        if t:
            try:
                ver = json.loads(t).get("version", "")
                where = str(cand.relative_to(root))
                break
            except ValueError:
                pass
    head, dirty = "", False
    rc, out, _ = run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], timeout=15)
    if rc == 0:
        head = out.strip()
        rc2, out2, _ = run(["git", "-C", str(root), "status", "--porcelain",
                            "--untracked-files=no"], timeout=30)
        dirty = rc2 == 0 and bool(out2.strip())
    return {"available": True, "version": ver, "manifest": where,
            "head": head or "(no git HEAD)", "dirty": dirty,
            "stamp": (head + "+dirty" if dirty else head) or "(no git HEAD)"}


DATA = {"coord": data_coord, "agents": data_agents, "spend": data_spend,
        "pulse": data_pulse, "watch": data_watch, "library": data_library,
        "findings": data_findings, "version": data_version}


# ------------------------------------------------------------- the pictures

def pic_inputs(root, name):
    if name == "river":
        ps = [root / "archive" / "findings.jsonl", root / "COORD.md",
              root / "COORD-AGENTS.md"]
        ps += sorted(root.glob("COORD-*.md"))
        b = root / "briefs"
        if b.is_dir():
            ps += sorted(b.glob("*.md"))
        return ps
    if name == "journey":
        ps, pdir = [], root / "plugins"
        if pdir.is_dir():
            for pl in sorted(p for p in pdir.iterdir() if p.is_dir()):
                ps.append(pl / "hooks" / "router.sh")
                ps += sorted((pl / "skills").glob("*/SKILL.md"))
        ps.append(root / "hooks" / "router.sh")
        ps += sorted((root / "skills").glob("*/SKILL.md"))
        return ps
    # the FILE GRAPH's input is the whole repo, which is too expensive to stat
    # per request. Its trigger is the git index (any add/commit/checkout) plus
    # the two directory mtimes — disclosed, with ?force=1 for anything else.
    return [root / ".git" / "index", root, root / "plugins"]


def newest_mtime(paths):
    best = 0.0
    for p in paths:
        try:
            best = max(best, p.stat().st_mtime)
        except OSError:
            pass
    return best


class Pictures(object):
    """Regenerate a render only when its INPUTS moved, and never more than once
    per PIC_DEBOUNCE — a browser that reloads in a loop must not turn into a
    render loop. Zero model tokens either way: the script draws, always."""

    def __init__(self, root, script):
        self.root, self.script = root, script
        self.last = {}
        self.lock = threading.Lock()

    def path(self, name):
        return self.root / PIC[name]["out"]

    def ensure(self, name, force=False):
        out = self.path(name)
        with self.lock:
            now = time.monotonic()
            last = self.last.get(name, 0.0)
            debounced = (now - last) < PIC_DEBOUNCE
            if debounced and not force and out.is_file():
                return "debounced", 0, ""
            stale = (not out.is_file()) or \
                    newest_mtime(pic_inputs(self.root, name)) > out.stat().st_mtime
            if not (stale or force):
                return "fresh", 0, ""
            argv = [sys.executable, str(self.script)] + list(PIC[name]["argv"]) + \
                   ["--root", str(self.root)]
            argv += ["--out", "graph"] if name == "graph" else \
                    ["--out", PIC[name]["out"], "--no-open"]
            rc, o, e = run(argv, timeout=180)
            self.last[name] = time.monotonic()
            return ("rebuilt" if rc == 0 else "failed"), rc, (e or o)[-600:]


# ------------------------------------------------------------------ the server

class Cockpit(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "notrest-cockpit"
    protocol_version = "HTTP/1.1"

    # the request log is noise on a live monitor polling every 5s
    def log_message(self, fmt, *args):
        if self.server.verbose:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---- plumbing
    def _send(self, code, body, ctype, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # THE STALENESS STAMP. The page shows the SERVER's read time from this
        # header — a client clock could be minutes off and would quietly lie.
        self.send_header("X-Cockpit-Generated", now_iso())
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200, extra=None):
        self._send(code, json.dumps(obj, indent=1, default=str), "application/json", extra)

    def _404(self, why="no such route"):
        self._json({"error": "not found", "why": why,
                    "routes": ["/", "/data/<%s>.json" % "|".join(sorted(DATA)),
                               "/data/briefs/<id>.json", "/pic/<river|journey|graph>.html",
                               "GET|POST /room/<name>"]}, 404)

    # ---- routing
    def do_GET(self):
        try:
            self.route_get()
        except Exception as exc:                                # never die on a request
            self._json({"error": "cockpit fault", "detail": str(exc)[:300]}, 500)

    do_HEAD = do_GET

    def route_get(self):
        path, _, query = self.path.partition("?")
        q = {}
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                q[k] = v
        srv = self.server

        if path in ("/", "/index.html", "/cockpit.html"):
            return self._send(200, srv.page, "text/html; charset=utf-8")
        if path == "/health":
            return self._json({"ok": True, "root": str(srv.root), "port": srv.server_address[1],
                               "bind": srv.server_address[0], "generated": now_iso()})

        m = re.match(r"^/data/briefs/([^/]+?)(?:\.json)?$", path)
        if m:
            body, code = data_brief(srv.root, m.group(1))
            return self._json(body, code)

        m = re.match(r"^/data/([a-z]+)(?:\.json)?$", path)
        if m and m.group(1) in DATA:
            return self._json(DATA[m.group(1)](srv.root))
        if m:
            return self._404("no such data panel: %s" % m.group(1))

        m = re.match(r"^/pic/([a-z]+)\.html$", path)
        if m and m.group(1) in PIC:
            name = m.group(1)
            state, rc, err = srv.pics.ensure(name, force=q.get("force") == "1")
            out = srv.pics.path(name)
            if not out.is_file():
                return self._json({"error": "render unavailable", "picture": name,
                                   "state": state, "exit": rc, "detail": err}, 503)
            try:
                body = out.read_bytes()
            except OSError as exc:
                return self._json({"error": "unreadable render", "detail": str(exc)}, 503)
            return self._send(200, body, "text/html; charset=utf-8",
                              {"X-Cockpit-Render": state})
        if m:
            return self._404("no such picture: %s" % m.group(1))

        m = re.match(r"^/room/([^/]+)$", path)
        if m:
            return self.room_read(m.group(1), q)
        return self._404()

    def do_POST(self):
        try:
            path, _, _q = self.path.partition("?")
            m = re.match(r"^/room/([^/]+)$", path)
            if not m:
                # THE ONLY WRITE THIS SERVER HAS IS THE MAIL SLOT. Everything
                # else is a read, and a POST anywhere else is a 404 on purpose.
                return self._404("the cockpit has exactly one write route: POST /room/<name>")
            return self.room_post(m.group(1))
        except Exception as exc:
            self._json({"error": "cockpit fault", "detail": str(exc)[:300]}, 500)

    # ---- the mail slot
    def _room_script(self):
        return sibling("chatroom", "room.py")

    def room_read(self, name, q):
        if not SAFE_NAME.match(name):
            return self._json({"error": "unsafe room name"}, 400)
        rp = self._room_script()
        if not rp:
            return self._json(unavailable("room", "chatroom/scripts/room.py is not installed"), 503)
        try:
            tail = max(1, min(400, int(q.get("tail", ROOM_TAIL))))
        except ValueError:
            tail = ROOM_TAIL
        rc, out, err = run([sys.executable, str(rp), "read", name, "--tail", str(tail)])
        if rc != 0:
            return self._json({"available": False, "room": name, "exit": rc,
                               "detail": (err or out).strip()[:400]}, 404 if rc == 2 else 200)
        return self._json({"available": True, "room": name, "exit": rc, "tail": tail,
                           "lines": out.splitlines()})

    def room_post(self, name):
        if not SAFE_NAME.match(name):
            return self._json({"error": "unsafe room name"}, 400)
        rp = self._room_script()
        if not rp:
            return self._json(unavailable("room", "chatroom/scripts/room.py is not installed"), 503)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > POST_CAP:
            return self._json({"error": "bad body", "why": "0 < Content-Length <= %d" % POST_CAP}, 413)
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw.decode("utf-8"))
            handle, text = str(body.get("handle") or "").strip(), str(body.get("text") or "")
        except (ValueError, UnicodeDecodeError):
            return self._json({"error": "body must be JSON {handle, text}"}, 400)
        if not SAFE_NAME.match(handle) or not text.strip():
            return self._json({"error": "handle must be a plain name and text must be non-empty"}, 400)
        # THE GATE IS ROOM.PY'S. Its no-secrets screen runs inside `post`; the
        # cockpit neither pre-screens nor overrides it, and hands back exit 5
        # verbatim so a refusal reads the same here as on the command line.
        rc, out, err = run([sys.executable, str(rp), "post", name, handle, text])
        payload = {"room": name, "handle": handle, "exit": rc,
                   "stdout": out.strip()[:800], "stderr": err.strip()[:800]}
        if rc == 5:
            payload.update({"posted": False, "refused": True,
                            "why": "chatroom's no-secrets law refused this post (exit 5) — "
                                   "the cockpit passes the refusal through untouched"})
            return self._json(payload, 422)
        payload["posted"] = rc == 0
        return self._json(payload, 200 if rc == 0 else 502)


# ------------------------------------------------------------------- the page

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>cockpit — __TITLE__</title>
<style>
:root{
  --surface-0:#f7f6f2; --surface-1:#ffffff; --surface-2:#efeade;
  --border:#e6e3da; --border-strong:#d2cfc4;
  --text-primary:#20201d; --text-secondary:#57564f; --text-muted:#86857b;
  --ok:#1D9E75; --warn:#D89A3A; --bad:#C2554E; --accent:#5C98D6;
  --commission:#7F77DD; --lane:#a8a69a;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --surface-0:#141413; --surface-1:#1f1f1d; --surface-2:#26261f;
    --border:#37362e; --border-strong:#4b4a40;
    --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
    --ok:#3fc79c; --warn:#e6b45c; --bad:#DD7F77; --accent:#6FA9E6;
    --commission:#9a92ea; --lane:#5d5c53;
  }
}
:root[data-theme="dark"]{
  --surface-0:#141413; --surface-1:#1f1f1d; --surface-2:#26261f;
  --border:#37362e; --border-strong:#4b4a40;
  --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
  --ok:#3fc79c; --warn:#e6b45c; --bad:#DD7F77; --accent:#6FA9E6;
  --commission:#9a92ea; --lane:#5d5c53;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--surface-0);color:var(--text-primary);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  display:flex;flex-direction:column;overflow:hidden;font-size:13px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
header{display:flex;flex-wrap:wrap;gap:.4rem .7rem;align-items:center;padding:.5rem .8rem;
  border-bottom:1px solid var(--border);background:var(--surface-1);flex:none}
h1{font-size:13.5px;font-weight:600;margin:0;letter-spacing:.02em}
.grow{flex:1}
button{background:var(--surface-0);color:var(--text-secondary);border:1px solid var(--border);
  border-radius:999px;padding:.22rem .65rem;font-size:11.5px;cursor:pointer;font-family:inherit}
button:hover{border-color:var(--border-strong);color:var(--text-primary)}
button.on{background:var(--surface-2);color:var(--text-primary);border-color:var(--border-strong)}
main{flex:1;min-height:0;display:flex}
/* ONE VIEW AT A TIME, OWNING THE VIEWPORT (owner's redesign, 2026-08-04). No second
   column, no stacked panels: whatever is selected gets everything under the bar. The
   picture views cannot be starved by feeds, because the feeds are views of their own. */
.view{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column;overflow:auto}
[hidden]{display:none!important}
#stage{position:relative;padding:0;overflow:hidden}
iframe{flex:1;width:100%;border:0;background:var(--surface-0);min-height:0}
/* the escape hatch sits ON the picture, in its corner — discoverable, and out of the
   bar the owner asked to keep to six controls */
a.fullpage{position:absolute;right:.6rem;bottom:.6rem;z-index:2;
  background:color-mix(in srgb,var(--surface-1) 88%,transparent);
  color:var(--text-secondary);border:1px solid var(--border);border-radius:999px;
  padding:.2rem .6rem;font-size:11px;text-decoration:none;white-space:nowrap}
a.fullpage:hover{border-color:var(--border-strong);color:var(--text-primary)}
#v-coord,#v-lanes{padding:.5rem .8rem}
.feed{min-height:0}
/* THE STALENESS LAW SURVIVES THE REDESIGN (cockpit's own docstring: a live monitor
   that cannot tell you how stale it is is worse than no monitor). It is no longer a
   chip in the bar — it is one faint line in the corner, visually negligible and always
   there, still read from the SERVER's X-Cockpit-Generated header and never a browser
   clock. */
#stamp{position:fixed;right:.55rem;bottom:.4rem;z-index:3;pointer-events:none;
  font-size:10px;color:var(--text-muted);opacity:.6;font-family:var(--mono,ui-monospace,monospace)}
section>h2{margin:0 0 .4rem;font-size:10.5px;letter-spacing:.1em;color:var(--text-muted);
  font-weight:600;display:flex;align-items:center;gap:.4rem}
section>h2 .n{color:var(--text-secondary);letter-spacing:0;font-weight:500}
.row{padding:.24rem 0;border-top:1px dotted var(--border);line-height:1.4}
.row:first-of-type{border-top:none}
.t{color:var(--text-muted);font-size:10.5px}
.ask{color:var(--text-primary)}
.landed{color:var(--text-secondary)}
.flag{font-size:9.5px;border:1px solid var(--border-strong);border-radius:999px;
  padding:0 .32rem;color:var(--text-secondary);margin-left:.25rem}
.flag.ship{border-color:var(--commission);color:var(--commission)}
.flag.gate{border-color:var(--ok);color:var(--ok)}
.flag.correction{border-color:var(--warn);color:var(--warn)}
.lane{display:flex;gap:.4rem;align-items:flex-start;padding:.26rem 0;
  border-top:1px dotted var(--border)}
.lane:first-of-type{border-top:none}
.sheet{flex:none;width:13px;height:17px;border-radius:2px;border:1.4px solid var(--lane);
  background:var(--surface-0);position:relative;margin-top:1px}
.lane.comm .sheet{border-color:var(--commission);cursor:pointer}
.lane.comm .sheet::after{content:"";position:absolute;left:2px;right:2px;top:3px;height:1px;
  background:var(--commission);box-shadow:0 3px 0 var(--commission),0 6px 0 var(--commission)}
.lane.comm .sheet:hover{background:var(--commission);opacity:.75}
.lane .who{font-size:11px}
.pill{font-size:9.5px;border:1px solid var(--border-strong);border-radius:999px;
  padding:0 .3rem;color:var(--text-muted)}
.concept{padding:.24rem 0;border-top:1px dotted var(--border)}
.concept:first-of-type{border-top:none}
.crown{color:var(--warn)}
textarea,input[type=text]{width:100%;font:inherit;font-size:12px;padding:.3rem .45rem;
  border:1px solid var(--border);border-radius:7px;background:var(--surface-0);
  color:var(--text-primary);resize:vertical}
textarea:focus,input:focus{outline:none;border-color:var(--border-strong)}
.roomline{font-size:11.5px;padding:.15rem 0;border-top:1px dotted var(--border);
  white-space:pre-wrap;word-break:break-word}
.note{color:var(--text-muted);font-size:10.5px;line-height:1.45}
.empty{color:var(--text-muted);font-size:11.5px;padding:.2rem 0}
</style>
</head>
<body>
<header>
  <button data-view="river" class="on" type="button">river</button>
  <button data-view="graph" type="button">file graph</button>
  <button data-view="coord" type="button">coord</button>
  <span class="grow"></span>
  <button id="picreload" type="button">rebuild</button>
</header>
<main>
  <div id="stage" class="view">
    <iframe id="pic" title="picture" src="/pic/river.html?embed=1"></iframe>
    <a id="picfull" class="fullpage" href="/pic/river.html" target="_blank" rel="noopener">open full page &#8599;</a>
  </div>
  <div id="v-coord" class="view" hidden><div id="coord" class="feed"></div></div>
</main>
<div id="stamp" title="server read time, from the X-Cockpit-Generated response header">—</div>

<script>
(function(){
var root = document.documentElement, live = true, timer = null;
function $(id){ return document.getElementById(id); }
function esc(s){
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function clip(s, n){ s = String(s || ''); return s.length <= n ? s : s.slice(0, n - 1) + '…'; }
/* THE STAMP IS THE SERVER'S. A browser clock can be minutes out; a monitor that
   reports the viewer's idea of "now" is a monitor that lies quietly. */
var lastStamp = '';
function get(path, cb){
  var x = new XMLHttpRequest();
  x.open('GET', path, true);
  x.onload = function(){
    var h = x.getResponseHeader('X-Cockpit-Generated');
    if (h){ lastStamp = h; $('stamp').textContent = 'read ' + h.replace('T',' ').replace('Z','Z'); }
    var d = null;
    try { d = JSON.parse(x.responseText); } catch(e){ d = {available:false, why:'bad JSON'}; }
    cb(d, x.status);
  };
  x.onerror = function(){ cb({available:false, why:'server unreachable'}, 0); };
  x.send();
}
/* ----------------------------------------------------------------- the feeds */
function pollCoord(){
  get('/data/coord.json', function(d){
    if (!d.available) { $('coord').innerHTML = '<div class="empty">no COORD ledger here</div>'; return; }
    var out = d.lines.slice().reverse().map(function(c){
      return '<div class="row"><span class="t mono">' + esc(c.ts) + '</span> ' +
        (c.lane ? '<span class="pill">' + esc(clip(c.lane, 22)) + '</span> ' : '') +
        (c.flag ? '<span class="flag ' + esc(c.flag) + '">' + esc(c.flag) + '</span> ' : '') +
        '<div class="ask">' + esc(clip(c.ask, 150)) + '</div>' +
        (c.landed ? '<div class="landed">→ ' + esc(clip(c.landed, 150)) + '</div>' : '') +
        '</div>';
    }).join('');
    $('coord').innerHTML = out || '<div class="empty">no ledger lines yet</div>';
  });
}
/* ----------------------------------------------------------------- the views
   OWNER'S REDESIGN (2026-08-04): five views, one at a time, each owning the whole
   viewport under a six-control bar. The chrome that used to ride the top — title,
   version/pulse/spend/watch/lane chips, the live toggle, the theme button — is gone
   on purpose: it reported the harness to the seat, and the ledgers already hold all
   of it. The window shows the WORK, not the paperwork. */
var pic = 'river', VIEWS = {river:1, graph:1};
function show(v){
  var isPic = !!VIEWS[v];
  $('stage').hidden = !isPic;
  $('v-coord').hidden = (v !== 'coord');
  /* rebuild acts on a PICTURE. On the feeds there is nothing to rebuild, so the
     control is hidden rather than left there doing nothing. */
  $('picreload').hidden = !isPic;
  if (isPic && v !== pic){
    pic = v;
    $('pic').src = '/pic/' + pic + '.html?embed=1';
    $('picfull').href = '/pic/' + pic + '.html';
  }
}
Array.prototype.forEach.call(document.querySelectorAll('[data-view]'), function(b){
  b.onclick = function(){
    Array.prototype.forEach.call(document.querySelectorAll('[data-view]'), function(o){
      o.classList.toggle('on', o === b);
    });
    show(b.getAttribute('data-view'));
  };
});
$('picreload').onclick = function(){
  $('pic').src = '/pic/' + pic + '.html?embed=1&force=1&t=' + Date.now();
};

/* ------------------------------------------------------------------ the loop
   Polling stays ALWAYS ON at 5s — the live toggle was chrome, and a monitor you have
   to switch on is a monitor that is off when it matters. Theme follows the OS via
   prefers-color-scheme; there is no button because there is no decision to make. */
function tick(){ pollCoord(); }
show('river');
tick();
setInterval(tick, 5000);
})();
</script>
</body>
</html>
"""


def build_page(root):
    return PAGE.replace("__TITLE__", G.esc(root.name))


def marker_path(root):
    return pathlib.Path(root) / ALWAYS_MARKER


def write_marker(root, port):
    """(ok, why). Atomic: tmp beside the target + os.replace, so a reader never sees a
    half-written marker and a crash cannot leave one. graph/ may not exist yet."""
    target = marker_path(root)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps({"port": int(port)}) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(target))
        return True, ""
    except OSError as exc:
        return False, str(exc)


def read_marker(root):
    """The opted port, or None. A malformed marker is NOT an error to shout about — it
    reads as 'not opted in', because the alternative is a broken JSON file that makes
    every session start noisy."""
    try:
        blob = json.loads(marker_path(root).read_text(encoding="utf-8"))
        port = blob.get("port")
        if isinstance(port, bool):
            return None
        port = int(port)
        return port if 1 <= port <= 65535 else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def probe_health(port, timeout=HEALTH_TIMEOUT):
    """(alive, served_root). Loopback only, stdlib only, one short probe."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                    timeout=timeout) as resp:
            blob = json.loads(resp.read().decode("utf-8", "replace"))
        return bool(blob.get("ok")), str(blob.get("root", "?"))
    except Exception:
        return False, ""


def cmd_status(a):
    """Is the window this project asked for actually open? One line, typed exit.
    0 = opted in and serving · 5 = opted in and DOWN (the interesting one: the project
    wants a cockpit and does not have one) · 6 = never opted in."""
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        G.die(f"not a directory: {root}")
    port = read_marker(root)
    if port is None:
        exists = marker_path(root).exists()
        why = "unreadable marker" if exists else f"no {ALWAYS_MARKER} marker"
        print(f"cockpit: unopted — {why} · opt in with: cockpit.py serve --root "
              f"{root} --always --no-open &")
        return 6
    url = f"http://127.0.0.1:{port}/"
    alive, served = probe_health(port)
    if alive:
        note = "" if served in ("", "?", str(root)) else f" · WARNING serving {served}"
        print(f"cockpit: {url} — running (opted always-on, root {root}){note}")
        return 0
    print(f"cockpit: {url} — down (opted always-on) · start it: cockpit.py serve "
          f"--root {root} --port {port} --always --no-open &")
    return 5


def cmd_serve(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        G.die(f"not a directory: {root}")
    script = pathlib.Path(os.path.abspath(__file__)).parent / "graph.py"
    if not script.is_file():
        G.die(f"graph.py is missing beside cockpit.py at {script}")
    page = build_page(root)
    out = root / "graph" / "cockpit.html"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        wrote = str(out)
    except OSError as exc:
        wrote = f"(not written: {exc})"

    srv = Cockpit(("127.0.0.1", a.port), Handler)      # LOOPBACK ONLY, always
    srv.root, srv.page, srv.verbose = root, page, a.verbose
    srv.pics = Pictures(root, script)
    host, port = srv.server_address[0], srv.server_address[1]
    url = f"http://{host}:{port}/"
    # --always writes the opt-in marker with the REAL bound port (never the requested
    # one — they differ the moment a port is taken). Without the flag an existing marker
    # is left exactly as it was: opting in is a deliberate act, and so is opting out.
    if getattr(a, "always", False):
        ok, why = write_marker(root, port)
        print(f"  always: {ALWAYS_MARKER} written (port {port})" if ok
              else f"  always: NOT written ({why})")
    print(f"cockpit: {url}")
    print(f"  root:  {root}")
    print(f"  page:  {wrote}")
    print(f"  bind:  {host} (loopback only) · port {port} "
          f"(render-check owns 8790-8799 — clear of it)")
    print(f"  data:  /data/{{{','.join(sorted(DATA))}}}.json · /data/briefs/<id>.json")
    print(f"  pics:  /pic/{{river,journey,graph}}.html (rebuilt when inputs move, "
          f"debounced {PIC_DEBOUNCE:.0f}s)")
    print("  write: POST /room/<name> only — every other route is a read")
    print("  stop:  Ctrl-C here, or kill the pid this shell reports")
    sys.stdout.flush()
    if a.open:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.run([opener, url], check=False, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except OSError:
            pass
    try:
        srv.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        print("\ncockpit: stopped")
    finally:
        srv.server_close()
    return 0


def main():
    ap = argparse.ArgumentParser(
        prog="cockpit.py",
        description="one page, always on: the estate live on 127.0.0.1")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="serve the cockpit on 127.0.0.1")
    s.add_argument("--root", default=".")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--open", dest="open", action="store_true", help="open a browser")
    s.add_argument("--no-open", dest="open", action="store_false")
    s.add_argument("--verbose", action="store_true", help="log every request")
    s.add_argument("--always", action="store_true",
                   help="opt this project in: write the always-on marker with the bound port")
    s.set_defaults(f=cmd_serve, open=True)
    st = sub.add_parser("status", help="is the opted-in cockpit actually up? (0/5/6)")
    st.add_argument("--root", default=".")
    st.set_defaults(f=cmd_status)
    args = ap.parse_args()
    raise SystemExit(args.f(args) or 0)


if __name__ == "__main__":
    main()
