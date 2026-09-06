#!/usr/bin/env python3
# to-wire.py — kernel snapshot -> atlas-hub/1 wire. © 2026 Not Rest Inc. Part of Atlas; licensed with the notrest plugin. Authored by the Atlas seat (atlas-ce), 2026-09-06.
"""to-wire (atlas-hub/1) — AtlasSnapshot (atlas-snapshot/1.x) -> the NEW hub wire.

Successor of tools/atlas2/to-wire.py (which emits atlas-hub/0). Everything /0
emits is emitted here unchanged; /1 ADDS kinds, a parent hierarchy, typed edges,
per-part evidence and per-card source refs.

THE NAMING COLLISION STILL LIVES IN ONE FUNCTION (hub/SCHEMA-v0.md):
    snapshot.modules[]  ->  wire.nodes[]  (the cards; kind != "module")
    snapshot.nodes[]    ->  wire.nodes[].parts[]  (grouped by .module)
and /1 adds, ABOVE the cards:
    MODULE-MAP.json modules[]  ->  wire.nodes[] of kind "module" (the group tree)

No field is invented. Every mapping judgment is written down in
kit/README-to-wire.md; the snapshot field each one reads is named there with the
SCHEMA.md / schema.py line it was read from.

usage: to-wire.py SNAPSHOT.json [project]   -> wire JSON on stdout
env:   ATLAS_NOW=<iso8601Z>   pin source.verified_at (tests use this)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

WIRE_VERSION = "atlas-hub/1"
PLAYBOOK = "2.0"
BOARD_URL = "https://atlas.not.rest/v1/board/kernel"

# the wire's node kinds (the seat's interface spec)
KINDS = ("product", "component", "agent", "surface", "capability", "module",
         "service", "contract", "host", "other")
# the kernel's own edge legend (tools/atlas2/schema.py:31 EDGE_KINDS)
EDGE_KINDS = ("authority", "data", "effect", "evidence", "control")
WIRE_EDGE_KINDS = EDGE_KINDS + ("composes", "implements", "other")

# ---- kind: a card is a "component" unless the estate's OWN group tree says
# otherwise. The only signals used are (a) the MODULE-MAP group leaf, whose
# label IS the word ("Hosts", "Contracts", "Agents", "Capabilities",
# "Product"), and (b) the module title carrying the word "Surface".
GROUP_LEAF_KIND = {
    "hosts": "host",            # MODULE-MAP label "Hosts": "the only doors to reality"
    "contracts": "contract",    # MODULE-MAP label "Contracts"
    "agents": "agent",          # MODULE-MAP label "Agents"
    "capabilities": "capability",  # MODULE-MAP label "Capabilities"
}
PRODUCT_PREFIX = "notrest/rig/product"  # MODULE-MAP label "Product"

PATH_RE = re.compile(
    r"\b[A-Za-z0-9_][A-Za-z0-9_.\-/]*\.(?:sh|py|md|json|html|js|mjs|toml|rs|wit|txt)\b")
ADR_RE = re.compile(r"\bADR-(\d{3})(-[A-Z])?\b")
BARE_NUM_RE = re.compile(r"(?<![A-Za-z0-9-])(\d{3})(-[A-Z])?(?![A-Za-z0-9-])")


# --------------------------------------------------------------------------
# helpers


def kernel_root(snapshot_path):
    """<root>/doctrine/atlas-snapshots/<stamp>.json -> <root>."""
    p = os.path.abspath(snapshot_path)
    return os.path.dirname(os.path.dirname(os.path.dirname(p)))


def git_head(root):
    """git sha of the estate HEAD, or None. Read with git; never guessed."""
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    sha = out.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{7,40}", sha) else None


def load_module_map(root):
    """doctrine/atlas-evolution/MODULE-MAP.json -> (groups[], assign{}) or (None, {})."""
    p = os.path.join(root, "doctrine/atlas-evolution/MODULE-MAP.json")
    if not os.path.exists(p):
        return None, {}
    try:
        M = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None, {}
    groups = M.get("modules") or []
    assign = {k: (v[0] if isinstance(v, list) and v else None)
              for k, v in (M.get("assign") or {}).items()}
    return groups, assign


def adr_ids(text):
    """'ADR-001 · 010 · 022' -> [ADR-001, ADR-010, ADR-022].

    The bare-number expansion only fires when the string ALREADY names an ADR;
    a string with no ADR token yields nothing (so '§13' / 'M4 brief' stay out).
    """
    if not text:
        return []
    hits = [f"ADR-{n}{s or ''}" for n, s in ADR_RE.findall(text)]
    if not hits:
        return []
    stripped = ADR_RE.sub(" ", text)
    hits += [f"ADR-{n}{s or ''}" for n, s in BARE_NUM_RE.findall(stripped)]
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def path_tokens(*texts):
    seen, out = set(), []
    for t in texts:
        for m in PATH_RE.findall(t or ""):
            if m not in seen:
                seen.add(m)
                out.append(m)
    return out


def part_word_re(part_id):
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(part_id) + r"(?![A-Za-z0-9])",
                      re.IGNORECASE)


# --------------------------------------------------------------------------
# the conversion


def to_wire(snap, project, root, now):
    report = {"edges_unresolved": 0, "unresolved": [], "groups": 0,
              "proven": 0, "unverified": 0, "failing": 0, "parents": 0,
              "downgraded": [], "edges_intranode": 0, "edges_duplicate": 0,
              "refused": []}

    tests_by_module = {}
    for t in snap.get("tests", []):        # schema.py:161-167 tests[]{id,module,index,name,passing}
        tests_by_module.setdefault(t.get("module"), []).append(t)
    verify = (snap.get("evidence") or {}).get("verify", {})  # schema.py:184-190 evidence.verify

    parts_by_module = {}
    for n in snap.get("nodes", []):        # schema.py:105-114 nodes[]{id,module,part,order,label,status}
        parts_by_module.setdefault(n.get("module"), []).append(n)

    groups, assign = load_module_map(root)

    nodes = []
    card_ids = set()
    part_ids = set()

    # ---- 1. the group tree (kind "module"), parents first -----------------
    group_ids = set()
    if groups:
        for g in groups:
            path = g.get("path")
            if not path:
                continue
            group_ids.add(path)
            node = {"id": path, "kind": "module", "parts": []}
            if g.get("label"):
                node["title"] = g["label"]
            parent = path.rsplit("/", 1)[0] if "/" in path else None
            if parent:
                node["parent"] = parent
            nodes.append(node)
        report["groups"] = len(group_ids)

    # ---- 2. the cards (snapshot.modules[]) -------------------------------
    for m in snap.get("modules", []):      # schema.py:66-73 modules[]{id,title,milestone,adrs,active_owner,...}
        mid = m["id"]
        if mid in group_ids:
            sys.exit(f"to-wire: id collision — card {mid!r} is also a MODULE-MAP "
                     f"group path; refusing rather than silently reparenting")
        card_ids.add(mid)
        mtests = tests_by_module.get(mid, [])

        ps = []
        for n in sorted(parts_by_module.get(mid, []), key=lambda x: x.get("order", 0)):
            p = {"id": n["part"], "status": n["status"]}
            if n.get("label"):
                p["label"] = n["label"]
            status, ev, check = part_evidence(n, mtests)
            if status != n["status"]:
                # THE STATUS LAW: a done whose recorded check is failing is not
                # done. The wire says wip+failing and REPORTS the downgrade.
                p["status"] = status
                report["downgraded"].append(f"{mid}.{n['part']}")
            if ev:
                p["evidence"] = ev
                report[ev] = report.get(ev, 0) + 1
                if check:
                    p["check"] = check
            ps.append(p)
            part_ids.add(f"{mid}.{n['part']}")

        node = {"id": mid, "kind": card_kind(m, assign.get(mid)), "parts": ps}
        if m.get("title"):
            node["title"] = m["title"]
        if m.get("milestone"):
            node["milestone"] = m["milestone"]
        if m.get("active_owner"):
            node["active_owner"] = m["active_owner"]
        gp = assign.get(mid)
        if gp and gp in group_ids:
            node["parent"] = gp
            report["parents"] += 1
        src = card_source(m, verify.get(mid) or {}, root, now)
        if src:
            node["source"] = src
        nodes.append(node)

    # ---- 3. edges --------------------------------------------------------
    edges = []
    seen_edge = set()
    for ed in snap.get("edges", []):       # schema.py:128-136 edges[]{from,to,label,kind,milestone,order}
        a, b = ed.get("from"), ed.get("to")
        if not (resolves(a, card_ids, part_ids) and resolves(b, card_ids, part_ids)):
            report["edges_unresolved"] += 1
            report["unresolved"].append(f"{a} -> {b}")
            continue
        k = ed.get("kind")
        e = {"from": a, "to": b, "kind": k if k in WIRE_EDGE_KINDS else "other"}
        if ed.get("label"):
            e["relation"] = ed["label"]
        # THE HUB'S EDGE LAWS (hub/validate.mjs round 2): an edge whose ends sit
        # inside ONE node is the containment the tree already draws, and a
        # duplicate states nothing new. Both are refused there, so both are
        # dropped here — LOUDLY, never silently.
        if owner_of(a, part_ids) == owner_of(b, part_ids):
            report["edges_intranode"] += 1
            report["refused"].append(
                f"intra-node {a} -> {b} ({e['kind']} · {e.get('relation', '')})")
            continue
        sig = (a, b, e["kind"], e.get("relation"))
        if sig in seen_edge:
            report["edges_duplicate"] += 1
            report["refused"].append(f"duplicate {a} -> {b} ({e['kind']})")
            continue
        seen_edge.add(sig)
        edges.append(e)

    # ---- 4. the wire -----------------------------------------------------
    wire = {
        "schema_version": WIRE_VERSION,
        "project": project,
        "stamp": snap["stamp"],            # SCHEMA.md:58 top-level stamp
        "taken_at": snap["taken_at"],      # SCHEMA.md:57 top-level taken_at
        "playbook": PLAYBOOK,
    }
    head = git_head(root)
    if head:
        wire["head"] = head
    wire["sources"] = {"snapshot": "available",
                       "git": "available" if head else "unknown",
                       "tests": "unknown"}   # nothing was RUN here
    wire["nodes"] = nodes
    if edges:
        wire["edges"] = edges

    # ---- journey / findings / links: byte-for-byte the /0 behaviour ------
    mission = snap.get("mission")
    if mission and mission.get("journey_path"):
        wire["journey"] = {
            "name": mission.get("name") or mission.get("id") or "journey",
            "objective": mission.get("objective", ""),
            "steps": [
                {"step_id": s["step_id"], "label": s.get("label", s["step_id"]),
                 "order": s.get("order", i), "refs": s.get("refs", [])}
                for i, s in enumerate(mission["journey_path"])
            ],
        }

    # findings: COUNTS ONLY — finding text never leaves the estate.
    f = snap.get("findings")
    if isinstance(f, list):
        wire["findings"] = {"count": len(f)}
        rec = os.path.join(root, "doctrine/atlas-evolution/recurrence.json")
        if os.path.exists(rec):
            try:
                R = json.load(open(rec, encoding="utf-8"))
                wire["findings"]["recurring"] = sum(
                    1 for r in R.get("recurrences", [])
                    if r.get("counted", 0) >= 2 or (r.get("asserted") or 0) >= 2)
            except Exception:
                pass  # a missing/!parseable recurrence file omits the field

    wire["links"] = [{"label": "Fractal Atlas (full board)", "url": BOARD_URL}]
    return wire, report


def resolves(ref, card_ids, part_ids):
    return ref in part_ids or ref in card_ids


def owner_of(ref, part_ids):
    """the NODE an endpoint belongs to: '<card>.<part>' -> '<card>', else itself."""
    return ref.split(".", 1)[0] if ref in part_ids else ref


def card_kind(module, group_path):
    """component unless the estate's own data clearly says otherwise."""
    if group_path:
        leaf = group_path.rsplit("/", 1)[-1]
        if leaf in GROUP_LEAF_KIND:
            return GROUP_LEAF_KIND[leaf]
        if group_path == PRODUCT_PREFIX or group_path.startswith(PRODUCT_PREFIX + "/"):
            return "product"
    if re.search(r"\bsurface\b", module.get("title") or "", re.IGNORECASE):
        return "surface"
    return "component"


def part_evidence(node, module_tests):
    """-> (status, evidence, check). The status may be DOWNGRADED; see below.

    done + a green test that NAMES this part -> proven (with the check).

    The snapshot records tests per MODULE (schema.py:161), never per part, so
    the only honest per-part tie is a test whose NAME contains the part id as a
    word, inside the part's own module. done with no such test -> unverified
    (never 'proven' without a check). todo -> no evidence at all.

    THE STATUS LAW (hub/validate.mjs round 2, seat ruling): status "done"
    REFUSES evidence "failing" — a done whose check broke is not done. So a
    done part with a failing matched test comes out as **wip + failing**, with
    the check kept, and the converter reports the downgrade by part id.
    """
    status = node.get("status")
    if status != "done":
        return status, None, None
    rx = part_word_re(node.get("part", ""))
    matched = [t for t in module_tests if rx.search(t.get("name") or "")]
    if not matched:
        return status, "unverified", None
    failing = [t for t in matched if not t.get("passing")]
    if failing:
        return "wip", "failing", " · ".join(t["name"] for t in failing)
    return status, "proven", " · ".join(t["name"] for t in matched)


def card_source(module, verify_entry, root, now):
    """ADR ids -> adrs[], the verify command -> tests[], path tokens -> paths[].

    state is "available" ONLY when every extracted path was found on disk.
    """
    cmd = (verify_entry or {}).get("command") or ""
    src = {}
    paths = path_tokens(module.get("adrs"), cmd)
    if paths:
        src["paths"] = paths
    if cmd:
        src["tests"] = [cmd]
    adrs = adr_ids(module.get("adrs"))
    if adrs:
        src["adrs"] = adrs
    if not src:
        return None
    if paths:
        ok = all(os.path.exists(os.path.join(root, p)) for p in paths)
        src["verified_at"] = now
        src["state"] = "available" if ok else "unknown"
    else:
        src["state"] = "unknown"
    return src


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 else "kernel"
    snap = json.load(open(path, encoding="utf-8"))
    root = kernel_root(path)
    now = os.environ.get("ATLAS_NOW") or \
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wire, rep = to_wire(snap, project, root, now)
    json.dump(wire, sys.stdout, ensure_ascii=False)
    sys.stderr.write(
        "to-wire[atlas-hub/1] nodes=%d (cards=%d groups=%d parented=%d) parts=%d "
        "edges=%d edges_unresolved=%d edges_intranode=%d edges_duplicate=%d "
        "proven=%d unverified=%d failing=%d downgraded=%d\n" % (
            len(wire["nodes"]),
            len(wire["nodes"]) - rep["groups"], rep["groups"], rep["parents"],
            sum(len(n["parts"]) for n in wire["nodes"]),
            len(wire.get("edges", [])), rep["edges_unresolved"],
            rep["edges_intranode"], rep["edges_duplicate"], rep["proven"], rep["unverified"], rep["failing"],
            len(rep["downgraded"])))
    for u in rep["unresolved"]:
        sys.stderr.write("to-wire: DROPPED unresolvable edge %s\n" % u)
    for r in rep["refused"]:
        sys.stderr.write("to-wire: REFUSED edge (hub edge law) %s\n" % r)
    for d in rep["downgraded"]:
        sys.stderr.write("to-wire: DOWNGRADED done->wip (failing check) %s\n" % d)


if __name__ == "__main__":
    main()
