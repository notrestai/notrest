#!/usr/bin/env python3
"""atlas_wire.py — the plugin's snapshot -> the atlas-hub/1 WIRE, and the http push.

Two jobs, kept in one file because they are one contract:

  to_wire(snapshot, project, board_url) -> (wire, report)
      atlas.py's snapshot (schema notrest.atlas/1) rendered as the hub's wire
      (briefs/atlas-contract/SCHEMA-v1.md), with the status/evidence mapping of
      HUB-CONTRACT.md §4 applied EXACTLY and every judgment REPORTED. Nothing is
      downgraded, dropped or renamed silently: the report is a return value, not a
      log line somebody may not be reading.

  push_http(snapshot, board_html, credential_path, base, project, timeout)
          -> (ok, hub_commit, reason)
      POST the wire to /v1/snapshot/<project>, then the board to /v1/board/<project>
      (HUB-CONTRACT §2), bearer read BY PATH from the ingest secret file and built
      into the header IN MEMORY. On 201 the hub stores the wire verbatim, so
      hub_commit is the head we sent (§5). Errors come back one fact at a time,
      verbatim from the hub. Never retried blind.

LAWS THIS FILE KEEPS (each one is armed in fixture-wire.sh):
  · A SECRET IS A PATH, NEVER A VALUE. The ingest secret is read from a file and put
    into one header. It is never printed, never logged, never in argv, never in a URL,
    and never in an exception message. The only thing this file ever names is the PATH.
  · A DONE WITHOUT A CHECK IS NOT PROVEN. evidence "proven" is emitted only with a
    non-empty check; anything else claiming done comes out wip/unverified, reported.
  · THE BEARER DOES NOT TRAVEL. Redirects are refused (a 3xx would resend the header to
    whatever host it named), and plain http is refused for anything but loopback.
  · COUNTS, NEVER TEXT. findings carries {count, recurring} and nothing else — the
    estate's finding prose never leaves the estate.
  · CLIENT-SIDE REFUSAL. A body over the hub's 2 MiB (or a board over 4 MiB) is refused
    here, before a byte is sent, with the hub's own 413 shape.

Stdlib only, /usr/bin/python3 (3.9). Part of notrest 4.9.

usage:
  atlas_wire.py convert SNAPSHOT.json --project P [--board-url URL] [--root DIR]
  atlas_wire.py push SNAPSHOT.json --project P [--board FILE] [--credential PATH]
                                   [--base URL] [--timeout S]
env:
  ATLAS_HUB_BASE   default hub base URL (default https://atlas.not.rest)
  NOTREST_HOME     default ~/.notrest — where credentials/ lives
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

WIRE_VERSION = "atlas-hub/1"
PLAYBOOK = "2.0"
DEFAULT_BASE = "https://atlas.not.rest"

# the hub's bounds (SCHEMA-v1.md "Limits"; the byte caps are the worker's, §2)
MAX_BODY = 2 * 1024 * 1024
MAX_BOARD = 4 * 1024 * 1024
MAX_STRING = 4096
MAX_NODES = 500
MAX_PARTS = 5000

PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
HEAD_RE = re.compile(r"^[0-9a-f]{7,40}$")
BASE_RE = re.compile(r"^(https?)://(\[[^\]]+\]|[^/:]+)(?::(\d+))?(/.*)?$")
WS_RE = re.compile(r"\s+")
SEP_RE = re.compile(r"[:/]")
LOOPBACK = ("127.0.0.1", "localhost", "::1", "[::1]")

# the plugin's own vocabulary (atlas.py CLAIMS + derive()'s evidence words)
PLUGIN_STATUS = ("done", "wip", "planned", "blocked")

# GIT'S OWN HOOK ENVIRONMENT — the same law atlas.py learned the hard way (commit
# b60816c): a post-commit hook hands every child GIT_DIR/GIT_INDEX_FILE and friends, so a
# `git -C <root>` run underneath it reads somebody else's repository. The rule is a PREFIX
# with a named allowlist, never a denylist.
GIT_KEEP = ("GIT_TERMINAL_PROMPT", "GIT_SSH_COMMAND", "GIT_SSH")

_LEGACY_WARNED = False           # the legacy credential name warns ONCE per process


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def notrest_home():
    """COMMON Amendment (A2 defect, accepted): the ENV VALUE is expanded too, matching
    atlas.py's notrest_home(). A machine that sets NOTREST_HOME=~/store must not get one
    answer from the hook and another from the script."""
    return os.path.expanduser(os.environ.get("NOTREST_HOME") or "~/.notrest")


def child_env():
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_") and k not in GIT_KEEP:
            del env[k]
    return env


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def one_line(text):
    """A wire string is one line and ≤ 4096 chars — newlines would break the stamp."""
    s = " ".join(str(text or "").split())
    return s[:MAX_STRING]


def wire_id(text, fallback="part"):
    """An id is an ADDRESS: '.' joins a node to a part, so a '.' inside either one makes
    'a.b.c' mean two things at once (SCHEMA-v1 "Ids are addresses"). Whitespace is
    collapsed for the same reason — two ids that look identical must not differ. Slashes
    stay legal: 'notrest/rig' is a real naming."""
    s = WS_RE.sub("-", str(text or "").strip()).replace(".", "-")
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if len(s) > MAX_STRING:
        s = s[:MAX_STRING].rstrip("-")
    return s or fallback


def split_group(part_id, default_group):
    """'gate:the-laws-hold' -> ('gate', 'the-laws-hold'); 'example' -> (<estate>, 'example').

    The plugin's part ids carry their group in a prefix (atlas.py names every gate
    'gate:<slug>'), so the PART GROUP is the prefix up to the first ':' or '/'. A part
    with no prefix belongs to the estate's own node."""
    s = str(part_id or "").strip()
    m = SEP_RE.search(s)
    if m and m.start() > 0 and s[m.end():].strip():
        return s[:m.start()], s[m.end():]
    return default_group, s


def iso_z(value):
    """SCHEMA-v1: taken_at must END in Z **and** actually parse. Ending in Z is a shape;
    being a date is the fact the viewer's stamp age needs."""
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            datetime.strptime(s, fmt)
            return s
        except ValueError:
            pass
    return None


def git_subject(commit, root):
    """The commit subject, read from git — never guessed. None when git cannot answer."""
    try:
        p = subprocess.run(["git", "-C", root or ".", "log", "-1", "--pretty=%s",
                            commit, "--"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=10, env=child_env())
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    lines = p.stdout.decode("utf-8", "replace").strip().splitlines()
    return one_line(lines[0]) if lines and lines[0].strip() else None


# ---------------------------------------------------------------------------
# THE §4 TABLE — in one function, so there is exactly one place it can be wrong
# ---------------------------------------------------------------------------
def wire_part_status(status, evidence, has_check):
    """(plugin status, plugin evidence, does a check exist) -> (wire status, wire evidence).

    HUB-CONTRACT §4, row for row:

        done    / passed              -> done / proven      (check REQUIRED)
        done    / none|unfalsifiable  -> wip  / unverified   a done with no test is not done
        done    / failed              -> wip  / failing      a failing done is wip+failing
        wip     / failed              -> wip  / failing
        wip     / passed              -> done / proven       a passing test IS done
        wip     / none                -> wip  / unverified
        planned / *                   -> todo / (no evidence key at all)
        blocked / *                   -> wip  / unverified, or failing if a test failed

    'not-run' (atlas.py --dry-run) carries no verdict, so it reads exactly like 'none'.
    'proven' without a check is refused HERE rather than by the hub's 422: a proof
    nobody can re-run is an assertion, and we do not send assertions."""
    st = str(status or "").strip().lower()
    ev = str(evidence or "none").strip().lower()
    if st == "planned":
        return ("todo", None)
    if st == "blocked":
        return ("wip", "failing" if ev == "failed" else "unverified")
    if ev == "passed":
        return ("done", "proven") if has_check else ("wip", "unverified")
    if ev == "failed":
        return ("wip", "failing")
    return ("wip", "unverified")


# ---------------------------------------------------------------------------
# the conversion
# ---------------------------------------------------------------------------
def to_wire(snapshot, project, board_url=None, root=None):
    """snapshot (notrest.atlas/1) -> (wire atlas-hub/1, report).

    report = {downgraded[], dropped[], promoted[], renamed[], notes[], counts{}} — every
    judgment this function made, returned to the caller. Nothing happens silently."""
    report = {"downgraded": [], "dropped": [], "promoted": [], "renamed": [],
              "notes": [], "counts": {}}
    snap = snapshot if isinstance(snapshot, dict) else {}
    estate = str(snap.get("estate") or "").strip()
    default_group = wire_id(estate, "estate")

    if not PROJECT_RE.match(str(project or "")):
        report["notes"].append(
            "project: %r does not match [a-z][a-z0-9-]{0,31} — the hub will refuse it"
            % str(project or ""))

    commit = str(snap.get("commit") or "").strip().lower()
    head = commit if HEAD_RE.match(commit) else None
    if commit and head is None:
        report["dropped"].append(
            "head: %r is not a 7-40 char lowercase hex commit — omitted rather than guessed"
            % commit[:64])

    # ---- nodes: one per PART GROUP -----------------------------------------
    order, groups = [], {}
    total_parts = 0
    capped_parts = capped_nodes = False
    for raw in (snap.get("parts") or []):
        if not isinstance(raw, dict):
            report["dropped"].append("parts[]: a non-object entry")
            continue
        raw_id = str(raw.get("id") or "").strip()
        if not raw_id:
            report["dropped"].append("parts[]: an entry with no id")
            continue
        gkey, pkey = split_group(raw_id, default_group)
        gid, pid = wire_id(gkey, "estate"), wire_id(pkey, "part")
        if gid not in groups:
            if len(order) >= MAX_NODES:
                if not capped_nodes:
                    capped_nodes = True
                    report["dropped"].append(
                        "nodes: more than %d groups — the excess is dropped (hub limit)"
                        % MAX_NODES)
                continue
            order.append(gid)
            groups[gid] = []
        if total_parts >= MAX_PARTS:
            if not capped_parts:
                capped_parts = True
                report["dropped"].append(
                    "parts: more than %d — the excess is dropped (hub limit)" % MAX_PARTS)
            continue

        addr = "%s.%s" % (gid, pid)
        if pid != pkey.strip() or gid != gkey.strip():
            report["renamed"].append("%s -> %s (an id may not carry '.' or whitespace)"
                                     % (raw_id, addr))

        test = str(raw.get("test") or "").strip()
        has_check = bool(test) and len(test) <= MAX_STRING
        if test and not has_check:
            report["dropped"].append(
                "%s.check: %d chars exceeds the 4096 cap — the check is dropped, so the "
                "part cannot claim proven" % (addr, len(test)))

        pstatus = str(raw.get("status") or "").strip().lower()
        pev = str(raw.get("evidence") or "none").strip().lower()
        wstatus, wev = wire_part_status(pstatus, pev, has_check)
        if pstatus and pstatus not in PLUGIN_STATUS:
            report["notes"].append("%s: unknown plugin status %r read as wip"
                                   % (addr, pstatus))

        part = {"id": pid, "status": wstatus}
        label = one_line(raw.get("title") or raw.get("label") or "")
        raw_label = str(raw.get("title") or raw.get("label") or "")
        if len(raw_label) > MAX_STRING:
            report["dropped"].append("%s.label: %d chars exceeds the 4096 cap — dropped "
                                     "rather than truncated" % (addr, len(raw_label)))
        elif label:
            part["label"] = label
        if wev:
            part["evidence"] = wev
        if has_check:
            part["check"] = test

        if pstatus == "done" and wstatus != "done":
            why = " (proven requires a check)" if pev == "passed" else ""
            report["downgraded"].append("%s: done/%s -> %s/%s%s"
                                        % (addr, pev, wstatus, wev, why))
        elif pstatus in ("wip", "blocked") and wstatus == "done":
            report["promoted"].append("%s: %s/%s -> done/proven" % (addr, pstatus, pev))

        seen = {p["id"] for p in groups[gid]}
        if part["id"] in seen:
            n = 2
            while "%s-%d" % (part["id"], n) in seen:
                n += 1
            report["renamed"].append("%s -> %s.%s-%d (ids are unique within a node)"
                                     % (raw_id, gid, part["id"], n))
            part["id"] = "%s-%d" % (part["id"], n)
        groups[gid].append(part)
        total_parts += 1

    nodes = [{"id": gid, "kind": "component", "parts": groups[gid]} for gid in order]

    # ---- the wire ----------------------------------------------------------
    taken_at = iso_z(snap.get("ts"))
    if taken_at is None:
        taken_at = utcnow()
        report["dropped"].append(
            "taken_at: %r is not an ISO-8601 Z timestamp — stamped at conversion time "
            "instead" % str(snap.get("ts") or "")[:64])

    stamp = snap.get("stamp")
    if isinstance(stamp, str) and stamp.strip():
        stamp = one_line(stamp)
    else:
        stamp = git_subject(head, root) if head else None
    if not stamp:
        s = snap.get("summary") or {}
        stamp = one_line("%s @ %s · %s parts · %s done · %s failing"
                         % (estate or "estate", (head or "no-commit")[:12],
                            s.get("parts", total_parts), s.get("done", 0),
                            s.get("failing", 0)))

    ran = any(isinstance(p, dict) and str(p.get("evidence") or "").lower()
              in ("passed", "failed") for p in (snap.get("parts") or []))
    msrc = (snap.get("sources") or {}).get("map")
    wire = {
        "schema_version": WIRE_VERSION,
        "project": project,
        "stamp": stamp,
        "taken_at": taken_at,
        "playbook": PLAYBOOK,
    }
    if head:
        wire["head"] = head
    wire["sources"] = {
        "git": "available" if head else "unknown",
        "tests": "available" if ran else "unknown",
        "map": "available" if isinstance(msrc, dict) and msrc.get("ok") else "unknown",
    }
    # …and `gates` ONLY when this estate runs that collector (COMMON Amendment). A
    # freshness reading for a collector the snapshot never mentions would be invented.
    gsrc = (snap.get("sources") or {}).get("gates")
    if isinstance(gsrc, dict):
        wire["sources"]["gates"] = "available" if gsrc.get("ok") else "unknown"
    wire["nodes"] = nodes

    # findings: COUNTS ONLY. /1 is an allowlist — count and recurring, nothing else, ever.
    # A number we do not have is 0, never the estate's prose.
    count = recurring = 0
    f = snap.get("findings")
    if isinstance(f, list):
        count = len(f)
    elif isinstance(f, dict):
        for key, dest in (("count", "count"), ("recurring", "recurring")):
            v = f.get(key)
            if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
                if dest == "count":
                    count = v
                else:
                    recurring = v
        extra = [k for k in f if k not in ("count", "recurring")]
        if extra:
            report["dropped"].append(
                "findings.%s: dropped — the wire is counts only" % ",".join(sorted(extra)[:4]))
    wire["findings"] = {"count": count, "recurring": recurring}

    if board_url:
        u = str(board_url).strip()
        if u.startswith("https://") and len(u) <= MAX_STRING:
            wire["links"] = [{"label": "Atlas board", "url": u}]
        else:
            report["dropped"].append(
                "links: board_url %r is not an https:// URL within the cap — dropped"
                % u[:120])

    report["counts"] = {
        "nodes": len(nodes), "parts": total_parts,
        "proven": sum(1 for n in nodes for p in n["parts"] if p.get("evidence") == "proven"),
        "unverified": sum(1 for n in nodes for p in n["parts"]
                          if p.get("evidence") == "unverified"),
        "failing": sum(1 for n in nodes for p in n["parts"] if p.get("evidence") == "failing"),
        "todo": sum(1 for n in nodes for p in n["parts"] if p["status"] == "todo"),
    }
    return wire, report


def report_lines(report):
    """The report as stderr lines — the same facts the return value carries."""
    c = report.get("counts") or {}
    out = ["atlas_wire[%s] nodes=%d parts=%d proven=%d unverified=%d failing=%d todo=%d "
           "downgraded=%d promoted=%d dropped=%d renamed=%d"
           % (WIRE_VERSION, c.get("nodes", 0), c.get("parts", 0), c.get("proven", 0),
              c.get("unverified", 0), c.get("failing", 0), c.get("todo", 0),
              len(report.get("downgraded") or []), len(report.get("promoted") or []),
              len(report.get("dropped") or []), len(report.get("renamed") or []))]
    for tag in ("downgraded", "promoted", "dropped", "renamed", "notes"):
        for entry in report.get(tag) or []:
            out.append("atlas_wire: %s %s" % (tag.upper(), entry))
    return out


# ---------------------------------------------------------------------------
# credentials — BY PATH. A value never rides in argv, an env var, or a log line.
# ---------------------------------------------------------------------------
def credential_path_for(project, home=None, explicit=None):
    """-> (path, legacy). The ruling (RULINGS-2026-09-06 §2): the ingest secret is
    credentials/atlas-ingest-<project>; the old credentials/atlas-token is still read
    during the transition, with ONE warning."""
    if explicit:
        p = os.path.expanduser(str(explicit))
        return p, os.path.basename(p) == "atlas-token"
    h = home or notrest_home()
    new = os.path.join(h, "credentials", "atlas-ingest-%s" % project)
    if os.path.isfile(new):
        return new, False
    legacy = os.path.join(h, "credentials", "atlas-token")
    if os.path.isfile(legacy):
        return legacy, True
    return new, False


def read_secret(path, project="", legacy=False, out=sys.stderr):
    """The secret, or None. The PATH may be named; the value never is."""
    global _LEGACY_WARNED
    if legacy and not _LEGACY_WARNED:
        _LEGACY_WARNED = True
        out.write("atlas_wire: reading the legacy ingest secret at %s — rename it to "
                  "credentials/atlas-ingest-%s (the old name retires with 4.9)\n"
                  % (path, project or "<project>"))
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read(8192)
    except OSError:
        return None
    return raw.strip() or None


# ---------------------------------------------------------------------------
# the push
# ---------------------------------------------------------------------------
class Unreachable(Exception):
    """The hub did not answer. The message never carries the bearer."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx would resend the Authorization header to whatever host it named. Returning
    None here declines the redirect, so the 3xx surfaces as a refusal instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(url, body, secret, ctype, timeout):
    """-> (status, text). The bearer is built into the header IN MEMORY and appears
    nowhere else: not in argv, not in the URL, not in any exception this raises."""
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + secret)
    req.add_header("Content-Type", ctype)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "notrest-atlas/1")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            txt = exc.read(65536).decode("utf-8", "replace")
        except Exception:                                    # noqa: BLE001 - body is optional
            txt = ""
        return exc.code, txt
    except urllib.error.URLError as exc:
        raise Unreachable(str(getattr(exc, "reason", exc))[:120])
    except OSError as exc:
        raise Unreachable(str(exc)[:120])


def error_text(txt):
    """The hub's one fact, verbatim: {"error": "<fact>"} -> "<fact>"."""
    try:
        body = json.loads(txt)
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("error"), str) and body["error"].strip():
        return " ".join(body["error"].split())
    return " ".join((txt or "").split())[:200] or "(no body)"


def stored_key(txt):
    try:
        body = json.loads(txt)
    except ValueError:
        return ""
    if isinstance(body, dict) and isinstance(body.get("stored"), str):
        return body["stored"]
    return ""


def base_ok(base):
    m = BASE_RE.match(str(base or ""))
    if not m:
        return False, "hub: %r is not an http(s) base URL" % str(base or "")[:80]
    if m.group(1) == "http" and m.group(2) not in LOOPBACK:
        return False, ("hub: refusing to send the bearer over http to %s — https required"
                       % m.group(2))
    return True, ""


def post_wire(wire, board_html, secret, base, project, timeout=60):
    """The transport half, taking a wire somebody else built — so a fixture can send a
    wire this converter would never emit, and prove the hub refuses it."""
    body = json.dumps(wire, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_BODY:
        return (False, None, "413 body: %d bytes exceeds limit %d (refused client-side, "
                             "not sent)" % (len(body), MAX_BODY))
    board_bytes = None
    if board_html:
        board_bytes = (board_html.encode("utf-8") if isinstance(board_html, str)
                       else bytes(board_html))
        if len(board_bytes) > MAX_BOARD:
            return (False, None, "413 board: %d bytes exceeds limit %d (refused "
                                 "client-side, not sent)" % (len(board_bytes), MAX_BOARD))
    head = wire.get("head") if isinstance(wire, dict) else None
    root = str(base).rstrip("/")

    try:
        status, txt = _post("%s/v1/snapshot/%s" % (root, project), body, secret,
                            "application/json", timeout)
    except Unreachable:
        return (False, None, "hub unreachable at %s" % root)
    if status == 201:
        stored = stored_key(txt)
        reason = "stored %s" % stored if stored else "stored"
    elif status == 200:
        reason = "idempotent"
    elif 300 <= status < 400:
        return (False, None, "%d redirect refused — the bearer is never followed to "
                             "another host" % status)
    else:
        # ONE FACT, VERBATIM, and NEVER a blind retry: the hub already said what is wrong.
        return (False, None, "%d %s" % (status, error_text(txt)))

    if board_bytes is not None:
        try:
            bstatus, btxt = _post("%s/v1/board/%s" % (root, project), board_bytes, secret,
                                  "text/html; charset=utf-8", timeout)
        except Unreachable:
            return (False, head, "%s · board: hub unreachable at %s" % (reason, root))
        if bstatus == 201:
            reason += " · board stored"
        elif bstatus == 200:
            reason += " · board idempotent"
        elif 300 <= bstatus < 400:
            return (False, head, "%s · board: %d redirect refused" % (reason, bstatus))
        else:
            return (False, head, "%s · board: %d %s" % (reason, bstatus, error_text(btxt)))
    return (True, head, reason)


def push_http(snapshot, board_html, credential_path, base=None, project=None, timeout=60,
              board_url=None, root=None, report_to=None):
    """-> (ok, hub_commit, reason). hub_commit is the head we sent (HUB-CONTRACT §5): the
    hub stores the wire verbatim, and a GET inside ~60 s would read the edge cache."""
    project = str(project or wire_id(str((snapshot or {}).get("estate") or ""), "")).strip()
    if not PROJECT_RE.match(project):
        return (False, None, "project: %r does not match [a-z][a-z0-9-]{0,31}" % project)
    hub = str(base or os.environ.get("ATLAS_HUB_BASE") or DEFAULT_BASE).rstrip("/")
    fine, why = base_ok(hub)
    if not fine:
        return (False, None, why)

    path, legacy = credential_path_for(project, explicit=credential_path)
    secret = read_secret(path, project=project, legacy=legacy)
    if not secret:
        return (False, None, "no ingest secret at %s" % path)

    wire, report = to_wire(snapshot, project, board_url, root=root)
    if report_to is not None:
        for line in report_lines(report):
            report_to.write(line + "\n")
    return post_wire(wire, board_html, secret, hub, project, timeout)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atlas_wire.py", add_help=True,
                                 description="snapshot -> atlas-hub/1 wire, and the push")
    sub = ap.add_subparsers(dest="cmd")

    c = sub.add_parser("convert", help="wire JSON on stdout, the report on stderr")
    c.add_argument("snapshot")
    c.add_argument("--project", required=True)
    c.add_argument("--board-url", default=None)
    c.add_argument("--root", default=None, help="the estate root (for the commit subject)")

    p = sub.add_parser("push", help="POST the wire and the board to the hub")
    p.add_argument("snapshot")
    p.add_argument("--project", required=True)
    p.add_argument("--board", default=None, help="path to the board HTML")
    p.add_argument("--credential", default=None, help="path to the ingest secret file")
    p.add_argument("--base", default=None)
    p.add_argument("--board-url", default=None)
    p.add_argument("--root", default=None)
    p.add_argument("--timeout", type=float, default=60.0)

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 2

    try:
        snap = load_json(args.snapshot)
    except (OSError, ValueError) as exc:
        sys.stderr.write("atlas_wire: cannot read %s (%s)\n" % (args.snapshot, exc))
        return 3

    if args.cmd == "convert":
        wire, report = to_wire(snap, args.project, args.board_url, root=args.root)
        sys.stdout.write(json.dumps(wire, ensure_ascii=False, sort_keys=True))
        sys.stdout.write("\n")
        for line in report_lines(report):
            sys.stderr.write(line + "\n")
        return 0

    board = None
    if args.board:
        try:
            with open(args.board, "r", encoding="utf-8", errors="replace") as fh:
                board = fh.read()
        except OSError as exc:
            sys.stderr.write("atlas_wire: cannot read board %s (%s)\n" % (args.board, exc))
            return 4
    ok, hub_commit, reason = push_http(snap, board, args.credential, args.base,
                                       args.project, args.timeout,
                                       board_url=args.board_url, root=args.root,
                                       report_to=sys.stderr)
    print("atlas_wire: push %s · hub_commit %s · %s"
          % ("ok" if ok else "FAILED", hub_commit or "-", reason))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
