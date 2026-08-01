#!/usr/bin/env python3
"""graph.py — an Obsidian-style file graph for a project, built by SCRIPT.

The model never reads the repo to draw this graph; the scanner does (same
economics as the SubagentStop hook and archivist's index.py).

Subcommands:
  scan --root DIR [--out graph/]      walk the repo, write graph/graph.json and
                                      REGENERATE graph/graph.html (data inlined —
                                      the page opens over file:// with zero fetches)
  register   --root DIR [--registry F]   add the absolute root to the project registry
  unregister --root DIR [--registry F]   remove it (both idempotent)
  all [--registry F] [--out DIR]      merge every registered project's graph.json
                                      into one cross-project PM view
  river [--session S] [--out F]       the journey, not the map: findings.jsonl +
                                      the COORD volumes drawn as a river flowing
                                      left→right into the GOAL bank (graph/river.
                                      {json,html}, self-contained)
  journey [--out F]                   the DOOR, not the work: router.sh's shapes,
                                      oracle's intake routes and each skill's own
                                      chain lines drawn as user-phrase → shape →
                                      skill → chains-to (graph/journey.{json,html})
  domains (--paths…|--changed|--all)  partition files into DISJOINT lanes along
          [--lanes N] [--json]        the link graph — connected components with
                                      the hubs pulled out into seat_held, so a
                                      swarm can be scoped without two lanes
                                      being handed the same file (in memory; no
                                      prior scan needed, nothing written)
  links <path> | orphans | stale      plain-text queries over the last scan

Honesty: the graph shows REFERENCES that a text scan can see — not importance.
A disconnected node is information (nothing in the repo points at it), not garbage.

Renders are script-built at zero model tokens, and deterministic: identical
inputs produce a byte-identical page (everything sorted, no clock read unless
--now is passed). A new visualization is a new subcommand here, never a diagram
the model draws by hand.
"""
import argparse
import json
import math
import os
import pathlib
import posixpath
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone

READ_CAP = 200_000          # bytes read per file (tail of a big file is not scanned)
MENTIONS_PER_FILE = 60      # cap on prose path-mention edges from one file
MAX_EXTERNAL = 300          # cap on external (out-of-repo) reference nodes
DEFAULT_REGISTRY = pathlib.Path.home() / ".claude" / "oracle-projects.txt"
DEFAULT_ALL_OUT = pathlib.Path.home() / ".claude" / "oracle-graph"

SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "env", "dist", "build",
             "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
             ".next", ".nuxt", ".tox", "target", ".idea", ".gradle", "vendor",
             ".terraform", "coverage", ".cache", "site-packages"}

BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff",
              ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
              ".mp3", ".mp4", ".mov", ".avi", ".wav", ".m4a", ".webm",
              ".woff", ".woff2", ".ttf", ".otf", ".eot",
              ".so", ".dylib", ".dll", ".exe", ".bin", ".o", ".a", ".class",
              ".jar", ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".pack",
              ".jsonl", ".parquet", ".xlsx", ".docx", ".pptx", ".key", ".numbers"}

DOC_EXT = {".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc", ".org"}
CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".sh", ".bash",
            ".zsh", ".fish", ".rb", ".go", ".rs", ".java", ".kt", ".swift", ".c",
            ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".pl", ".lua", ".r",
            ".sql", ".html", ".htm", ".css", ".scss", ".vue", ".svelte", ".m"}
CONFIG_EXT = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
              ".lock", ".properties", ".plist", ".xml", ".gitignore",
              ".editorconfig", ".npmrc", ".nvmrc"}
CONFIG_NAMES = {"Makefile", "Dockerfile", "Procfile", "LICENSE", "Gemfile",
                "Rakefile", "Justfile", "CODEOWNERS", ".gitignore",
                ".gitattributes", ".editorconfig", "requirements.txt"}

ESTATE_NAMES = {"CLAUDE.md", "oracle-index.md", "AGENTS.md"}
ESTATE_PREFIXES = ("COORD", "START-HERE", "HANDOFF", "STATE.")
ESTATE_DIRS = ("spend/",)

PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}
SH_EXT = {".sh", ".bash", ".zsh", ".fish"}
JS_RESOLVE = [".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".json",
              "/index.js", "/index.ts", "/index.jsx", "/index.tsx"]

RE_WIKILINK = re.compile(r"\[\[([^\]\|#]+)")
RE_MDLINK = re.compile(r"\[[^\]\n]*\]\(\s*<?([^)\s>]+)")
RE_PY_FROM = re.compile(r"^[ \t]*from[ \t]+([.\w]+)[ \t]+import[ \t]+([^\n#]+)", re.M)
RE_PY_IMPORT = re.compile(r"^[ \t]*import[ \t]+([\w.]+(?:[ \t]*,[ \t]*[\w.]+)*)", re.M)
RE_JS = re.compile(r"""(?:from|import|require)\s*\(?\s*['"]([^'"\n]+)['"]""")
RE_SH = re.compile(
    r"""(?:^|[;&|(]|\s)(?:source|\.|bash|sh|zsh|python3?|node|npx)[ \t]+["']?"""
    r"""((?:[\w./${}-]|\$\()+\.(?:sh|bash|zsh|py|js|mjs|ts))""", re.M)
RE_MENTION = re.compile(r"[\w~.][\w./@+-]*\.[A-Za-z0-9]{1,6}")
RE_TRANSCRIPT = re.compile(r"transcript:\s*(\S+)")

# relpaths too ubiquitous to be a meaningful cross-project link. The estate files
# are here by construction — every ORACLE project has them, so their co-presence
# carries no information (the project hub already stands for the project).
COMMON_PATHS = {"README.md", "LICENSE", ".gitignore", "package.json",
                "package-lock.json", "requirements.txt", "setup.py", "index.js",
                "index.ts", "__init__.py", "main.py", "Makefile", "Dockerfile",
                "tsconfig.json", "CHANGELOG.md", ".editorconfig",
                "CLAUDE.md", "COORD.md", "COORD-AGENTS.md", "COORD-ARCHIVE.md",
                "START-HERE.md", "HANDOFF.md", "STATE.md", "oracle-index.md",
                "spend/ledger.md"}


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def die(msg, code=2):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


# ---------------------------------------------------------------- file listing

def git_files(root):
    """Tracked + untracked-but-not-ignored files — git applies .gitignore for us.
    None when this isn't a git repo (caller falls back to os.walk)."""
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z",
                            "--cached", "--others", "--exclude-standard"],
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]
    return out


def walk_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS and not d.startswith(".git"))
        for fn in sorted(filenames):
            if fn == ".DS_Store":
                continue
            p = pathlib.Path(dirpath) / fn
            try:
                out.append(p.relative_to(root).as_posix())
            except ValueError:
                continue
    return out


def list_files(root, exclude_prefix=None):
    rels = git_files(root)
    mode = "git"
    if rels is None:
        rels = walk_files(root)
        mode = "walk"
    keep, skipped = [], 0
    for rel in rels:
        if exclude_prefix and (rel == exclude_prefix.rstrip("/")
                               or rel.startswith(exclude_prefix)):
            continue
        parts = rel.split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]) or parts[-1] == ".DS_Store":
            continue
        p = root / rel
        if not p.is_file() or p.is_symlink():
            skipped += 1
            continue
        keep.append(rel)
    return sorted(set(keep)), mode, skipped


def read_text(path):
    """Text of a file, capped; None for binary/unreadable."""
    if path.suffix.lower() in BINARY_EXT:
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read(READ_CAP)
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", "replace")


# ------------------------------------------------------------------- bucketing

def bucket(rel):
    name = rel.rsplit("/", 1)[-1]
    if name in ESTATE_NAMES or name.startswith(ESTATE_PREFIXES):
        return "estate"
    if any(rel.startswith(d) for d in ESTATE_DIRS):
        return "estate"
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name[1:] else ""
    if name.startswith(".") and "." not in name[1:]:
        ext = name.lower()
    if ext in DOC_EXT:
        return "doc"
    if ext in CODE_EXT:
        return "code"
    if ext in CONFIG_EXT or name in CONFIG_NAMES:
        return "config"
    return "other"


# ------------------------------------------------------------------ resolution

def norm(p):
    p = posixpath.normpath(p)
    if p.startswith("./"):
        p = p[2:]
    return p


class Repo:
    def __init__(self, root, rels):
        self.root = root
        self.ids = set(rels)
        self.by_base = {}
        for r in rels:
            self.by_base.setdefault(r.rsplit("/", 1)[-1], []).append(r)
        self.unique_base = {k: v[0] for k, v in self.by_base.items() if len(v) == 1}

    def resolve(self, token, fromdir, extra_ext=()):
        """A repo-relative id for a raw reference token, or None."""
        if not token:
            return None
        t = token.strip().strip("`'\"<>,;:*")
        if not t or t.startswith(("http://", "https://", "mailto:", "#", "data:")):
            return None
        t = t.split("#", 1)[0].split("?", 1)[0]
        # ${VAR}/x or $VAR/x or $(dirname "$0")/x -> keep the tail
        if "$" in t:
            t = t.rsplit("/", 1)[-1]
        t = t.strip()
        if not t or t in (".", "..", "/"):
            return None
        if t.startswith("~/") or t.startswith("/"):
            ap = pathlib.Path(os.path.expanduser(t))
            try:
                t = ap.resolve().relative_to(self.root).as_posix()
            except (ValueError, OSError):
                return None
        cands = []
        if fromdir:
            cands.append(norm(posixpath.join(fromdir, t)))
        cands.append(norm(t))
        for c in cands:
            if c.startswith("..") or not c:
                continue
            if c in self.ids:
                return c
            for e in (".md",) + tuple(extra_ext):
                if (c + e) in self.ids:
                    return c + e
        if "/" not in t:
            hit = self.unique_base.get(t)
            if hit:
                return hit
            hit = self.unique_base.get(t + ".md")
            if hit:
                return hit
        return None


# ----------------------------------------------------------------- edge mining

def py_targets(text):
    """Module strings referenced by python imports (dots preserved)."""
    out = []
    for m in RE_PY_FROM.finditer(text):
        mod, names = m.group(1), m.group(2)
        out.append((mod, [n.strip().split(" as ")[0].strip()
                          for n in names.replace("(", "").replace(")", "").split(",")
                          if n.strip() and n.strip() != "*"]))
    for m in RE_PY_IMPORT.finditer(text):
        for mod in m.group(1).split(","):
            mod = mod.strip().split(" as ")[0].strip()
            if mod:
                out.append((mod, []))
    return out


def resolve_py(repo, mod, names, fromdir):
    hits = []
    dots = len(mod) - len(mod.lstrip("."))
    base = fromdir
    if dots:
        for _ in range(dots - 1):
            base = posixpath.dirname(base)
        mod = mod[dots:]
    path = mod.replace(".", "/")
    stems = []
    if path:
        stems.append(path)
    for n in names:
        stems.append(posixpath.join(path, n) if path else n)
    for st in stems:
        for cand in ([norm(posixpath.join(base, st))] if (dots or base) else []) + [norm(st)]:
            if cand.startswith(".."):
                continue
            for suf in (".py", "/__init__.py"):
                if (cand + suf) in repo.ids:
                    hits.append(cand + suf)
    return hits


def resolve_js(repo, spec, fromdir):
    if not spec.startswith(("./", "../", "/")) and "/" not in spec:
        return None            # bare package specifier -> node_modules, not a repo file
    return repo.resolve(spec, fromdir, extra_ext=JS_RESOLVE)


def file_edges(repo, rel, text, add):
    """All reference edges out of one file. `add(to, kind)` records them."""
    fromdir = posixpath.dirname(rel)
    ext = ("." + rel.rsplit(".", 1)[-1].lower()) if "." in rel.rsplit("/", 1)[-1] else ""
    b = bucket(rel)

    if b in ("doc", "estate") or ext in DOC_EXT:
        for m in RE_WIKILINK.finditer(text):
            t = repo.resolve(m.group(1), fromdir)
            if t:
                add(t, "wikilink")
        for m in RE_MDLINK.finditer(text):
            t = repo.resolve(m.group(1), fromdir)
            if t:
                add(t, "link")

    if ext in PY_EXT:
        for mod, names in py_targets(text):
            for t in resolve_py(repo, mod, names, fromdir):
                add(t, "import")

    if ext in JS_EXT:
        for m in RE_JS.finditer(text):
            t = resolve_js(repo, m.group(1), fromdir)
            if t:
                add(t, "import")

    if ext in SH_EXT:
        for m in RE_SH.finditer(text):
            t = repo.resolve(m.group(1), fromdir)
            if t:
                add(t, "source")

    # prose / comment path mentions — only what actually matches a repo file
    n = 0
    for m in RE_MENTION.finditer(text):
        if n >= MENTIONS_PER_FILE:
            break
        tok = m.group(0)
        if "/" not in tok and tok not in repo.unique_base:
            continue
        t = repo.resolve(tok, fromdir)
        if t:
            add(t, "mention")
            n += 1


def estate_edges(repo, rels, texts, add_edge, add_node):
    """Estate-specific structure: COORD-AGENTS transcripts (external refs) and
    dossier/background pairs inside an output folder."""
    ext_n = 0
    for rel in rels:
        name = rel.rsplit("/", 1)[-1]
        if name.startswith("COORD-AGENTS") and texts.get(rel):
            for m in RE_TRANSCRIPT.finditer(texts[rel]):
                if ext_n >= MAX_EXTERNAL:
                    break
                p = m.group(1).strip().rstrip(".,;`")
                if not p or p in ("?", "-"):
                    continue
                add_node(p, "external")
                add_edge(rel, p, "transcript")
                ext_n += 1
    lowers = {r: r.rsplit("/", 1)[-1].lower() for r in rels}
    for rel in rels:
        low = lowers[rel]
        if not low.endswith("dossier.md"):
            continue
        d = posixpath.dirname(rel)
        stem = low[: -len("dossier.md")].rstrip("-_ ")
        for other in rels:
            if other == rel or posixpath.dirname(other) != d:
                continue
            ol = lowers[other]
            if "background" in ol and (not stem or ol.startswith(stem[:6])):
                add_edge(rel, other, "pair")
    return ext_n


# ------------------------------------------------------------------- scan verb

def build_graph(root, out_rel):
    rels, mode, skipped = list_files(root, exclude_prefix=out_rel)
    repo = Repo(root, rels)
    nodes, texts = {}, {}
    for rel in rels:
        p = root / rel
        try:
            st = p.stat()
        except OSError:
            skipped += 1
            continue
        nodes[rel] = {"id": rel, "type": bucket(rel), "size": st.st_size,
                      "mtime": int(st.st_mtime), "degree": 0}
        t = read_text(p)
        if t is None:
            if p.suffix.lower() not in BINARY_EXT:
                skipped += 1
        else:
            texts[rel] = t

    seen, edges = set(), []

    def add_node(nid, typ):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": typ, "size": 0, "mtime": 0, "degree": 0}

    def add_edge(a, b, kind):
        if a == b or a not in nodes or b not in nodes:
            return
        if (a, b) in seen:
            return
        seen.add((a, b))
        edges.append({"from": a, "to": b, "kind": kind})

    for rel, text in texts.items():
        file_edges(repo, rel, text, lambda t, k, _r=rel: add_edge(_r, t, k))
    estate_edges(repo, rels, texts, add_edge, add_node)

    for e in edges:
        nodes[e["from"]]["degree"] += 1
        nodes[e["to"]]["degree"] += 1

    return {"generated": now_stamp(), "root": str(root), "listing": mode,
            "skipped": skipped,
            "nodes": [nodes[k] for k in sorted(nodes)], "edges": edges}


def cmd_scan(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        die(f"not a directory: {root}")
    out = pathlib.Path(a.out).expanduser()
    out = out if out.is_absolute() else (root / a.out)
    out = out.resolve()
    try:
        out_rel = out.relative_to(root).as_posix().rstrip("/") + "/"
    except ValueError:
        out_rel = None
    g = build_graph(root, out_rel)
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text(json.dumps(g, indent=1), encoding="utf-8")
    (out / "graph.html").write_text(render_html(g, title=root.name), encoding="utf-8")
    print(f"{out/'graph.html'}: {len(g['nodes'])} nodes, {len(g['edges'])} edges "
          f"({g['listing']} listing, {g['skipped']} skipped)")
    return 0


# --------------------------------------------------------------- registry verbs

def registry_path(a):
    return pathlib.Path(getattr(a, "registry", None) or DEFAULT_REGISTRY).expanduser()


def read_registry(p):
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line not in out:
            out.append(line)
    return out


def cmd_register(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        die(f"not a directory: {root}")
    reg = registry_path(a)
    reg.parent.mkdir(parents=True, exist_ok=True)
    cur = read_registry(reg)
    if str(root) in cur:
        print(f"{reg}: already registered ({len(cur)} project(s))")
        return 0
    with open(reg, "a", encoding="utf-8") as f:
        f.write(str(root) + "\n")
    print(f"{reg}: registered {root} ({len(cur) + 1} project(s))")
    return 0


def cmd_unregister(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    reg = registry_path(a)
    cur = read_registry(reg)
    if str(root) not in cur:
        print(f"{reg}: not registered ({len(cur)} project(s))")
        return 0
    keep = [c for c in cur if c != str(root)]
    reg.write_text("".join(c + "\n" for c in keep), encoding="utf-8")
    print(f"{reg}: unregistered {root} ({len(keep)} project(s))")
    return 0


# ---------------------------------------------------------------- merge verb

PALETTE = ["#7F77DD", "#1D9E75", "#D89A3A", "#C2607A", "#4A8FD4", "#8C8A7E",
           "#A06BC9", "#3FA5A0", "#B4703F", "#6E8F3A"]


def cmd_all(a):
    reg = registry_path(a)
    roots = read_registry(reg)
    if not roots:
        die(f"no registered projects in {reg} — run: graph.py register --root <dir>")
    out = pathlib.Path(a.out).expanduser().resolve()
    cap = a.per_project_cap

    projects, nodes, edges, missing = [], [], [], 0
    names = {}
    for i, r in enumerate(roots):
        rp = pathlib.Path(r).expanduser()
        gj = rp / "graph" / "graph.json"
        if not gj.is_file():
            missing += 1
            continue
        try:
            g = json.loads(gj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            missing += 1
            continue
        name = rp.name or str(rp)
        while name in names:
            name += "'"
        names[name] = str(rp)
        pn = len(projects)
        color = PALETTE[pn % len(PALETTE)]
        keep = g["nodes"]
        if cap and len(keep) > cap:
            est = [n for n in keep if n["type"] == "estate"]
            rest = sorted((n for n in keep if n["type"] != "estate"),
                          key=lambda n: -n.get("degree", 0))
            keep = est + rest[: max(0, cap - len(est))]
        kept = {n["id"] for n in keep}
        hub = f"{name}::"
        projects.append({"name": name, "root": str(rp), "color": color,
                         "nodes": len(keep), "edges": 0, "hub": hub})
        nodes.append({"id": hub, "label": name, "type": "project", "project": name,
                      "size": 0, "mtime": 0, "degree": 0})
        for n in keep:
            nodes.append({"id": f"{name}::{n['id']}", "label": n["id"],
                          "type": n["type"], "project": name,
                          "size": n.get("size", 0), "mtime": n.get("mtime", 0),
                          "degree": 0})
        pe = 0
        for e in g["edges"]:
            if e["from"] in kept and e["to"] in kept:
                edges.append({"from": f"{name}::{e['from']}",
                              "to": f"{name}::{e['to']}", "kind": e["kind"]})
                pe += 1
        projects[-1]["edges"] = pe
        # hub spokes: the estate + the five best-connected files of this project
        spokes = [n["id"] for n in keep if n["type"] == "estate"][:12]
        spokes += [n["id"] for n in sorted(keep, key=lambda n: -n.get("degree", 0))[:5]]
        for s in dict.fromkeys(spokes):
            edges.append({"from": hub, "to": f"{name}::{s}", "kind": "hub"})

    if not projects:
        die(f"no scanned projects found (registry {reg}: {len(roots)} root(s), "
            f"{missing} without graph/graph.json) — run scan in each first")

    ids = {n["id"] for n in nodes}
    cross = 0
    # 1) an out-of-repo reference that points inside another registered project
    for n in list(nodes):
        if n["type"] != "external":
            continue
        for p in projects:
            if p["name"] == n["project"]:
                continue
            tag = p["root"].replace("/", "-")
            if p["root"] in n["label"] or tag in n["label"]:
                edges.append({"from": n["id"], "to": p["hub"], "kind": "cross-ref"})
                cross += 1
    # 2) the same distinctive relative path present in two projects
    byrel = {}
    for n in nodes:
        if n["type"] in ("project", "external"):
            continue
        byrel.setdefault(n["label"], []).append(n)
    for rel, group in sorted(byrel.items()):
        if len(group) < 2 or len(group) > 4 or rel in COMMON_PATHS:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                edges.append({"from": group[i]["id"], "to": group[j]["id"],
                              "kind": "shared-path"})
                cross += 1

    deg = {}
    for e in edges:
        if e["from"] in ids and e["to"] in ids:
            deg[e["from"]] = deg.get(e["from"], 0) + 1
            deg[e["to"]] = deg.get(e["to"], 0) + 1
    for n in nodes:
        n["degree"] = deg.get(n["id"], 0)
    edges = [e for e in edges if e["from"] in ids and e["to"] in ids]

    g = {"generated": now_stamp(), "root": f"{len(projects)} registered project(s)",
         "mode": "merged", "projects": projects, "registry": str(reg),
         "skipped": missing, "nodes": nodes, "edges": edges}
    out.mkdir(parents=True, exist_ok=True)
    (out / "all-projects-graph.json").write_text(json.dumps(g, indent=1), encoding="utf-8")
    (out / "all-projects-graph.html").write_text(
        render_html(g, title="all projects"), encoding="utf-8")
    print(f"{out/'all-projects-graph.html'}: {len(projects)} projects, "
          f"{len(nodes)} nodes, {len(edges)} edges ({cross} cross-project, "
          f"{missing} unscanned)")
    return 0


# ------------------------------------------------------------------ the viewer

def render_html(g, title="project"):
    data = json.dumps(g, separators=(",", ":")).replace("</", "<\\/")
    hdr = g.get("root", "")
    counts = f"{len(g['nodes'])} nodes · {len(g['edges'])} edges"
    return (TEMPLATE
            .replace("__TITLE__", esc(title))
            .replace("__ROOT__", esc(hdr))
            .replace("__GENERATED__", esc(g.get("generated", "")))
            .replace("__COUNTS__", esc(counts))
            .replace('"__GRAPH_DATA__"', data))


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>file graph — __TITLE__</title>
<style>
:root{
  --surface-0:#f7f6f2; --surface-1:#ffffff; --border:#e6e3da; --border-strong:#d2cfc4;
  --text-primary:#20201d; --text-secondary:#57564f; --text-muted:#86857b;
  --edge:#b9b6aa; --edge-hi:#20201d;
  --c-estate:#7F77DD; --c-doc:#1D9E75; --c-code:#D89A3A; --c-config:#8f8e84;
  --c-other:#a8a69a; --c-external:#C2607A; --c-project:#4A8FD4;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --surface-0:#141413; --surface-1:#1f1f1d; --border:#37362e; --border-strong:#4b4a40;
    --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
    --edge:#4a493f; --edge-hi:#f2f1ea;
    --c-estate:#9a92ea; --c-doc:#3fc79c; --c-code:#e6b45c; --c-config:#9d9c92;
    --c-other:#76756c; --c-external:#dd7f97; --c-project:#6fa9e6;
  }
}
:root[data-theme="dark"]{
  --surface-0:#141413; --surface-1:#1f1f1d; --border:#37362e; --border-strong:#4b4a40;
  --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
  --edge:#4a493f; --edge-hi:#f2f1ea;
  --c-estate:#9a92ea; --c-doc:#3fc79c; --c-code:#e6b45c; --c-config:#9d9c92;
  --c-other:#76756c; --c-external:#dd7f97; --c-project:#6fa9e6;
}
*{box-sizing:border-box}
html{height:100%;width:100%}
body{margin:0;width:100vw;height:100vh;background:var(--surface-0);color:var(--text-primary);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  display:flex;flex-direction:column;overflow:hidden}
header{display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:center;padding:.6rem .9rem;
  border-bottom:1px solid var(--border);background:var(--surface-1)}
h1{font-size:14px;font-weight:500;margin:0}
.sub{font-size:12px;color:var(--text-muted)}
.path{max-width:52ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.grow{flex:1}
input[type=search]{font:inherit;font-size:12px;padding:.3rem .55rem;border-radius:999px;
  border:1px solid var(--border);background:var(--surface-0);color:var(--text-primary);width:190px}
input[type=search]:focus{outline:none;border-color:var(--border-strong)}
button{background:var(--surface-0);color:var(--text-secondary);border:1px solid var(--border);
  border-radius:999px;padding:.3rem .7rem;font-size:12px;cursor:pointer;font-family:inherit}
button:hover{border-color:var(--border-strong)}
main{flex:1;display:flex;min-height:0;min-width:0;position:relative}
#stage{flex:1;position:relative;min-width:0;min-height:0;overflow:hidden}
/* the canvas is sized in JS (CSS px + backing store + transform together) — never
   by percentages, so its intrinsic attribute size can't feed back into layout */
canvas{position:absolute;left:0;top:0;display:block;cursor:grab}
canvas.drag{cursor:grabbing}
#legend{position:absolute;left:.7rem;bottom:.7rem;pointer-events:none;background:var(--surface-1);
  border:1px solid var(--border);border-radius:10px;padding:.45rem .6rem;font-size:11.5px;
  color:var(--text-secondary);display:flex;flex-wrap:wrap;gap:.25rem .7rem;max-width:min(560px,80%)}
#legend span{display:inline-flex;align-items:center;gap:.3rem}
.dot{width:9px;height:9px;border-radius:50%;flex:none}
#tip{position:absolute;pointer-events:none;background:var(--surface-1);border:1px solid var(--border-strong);
  border-radius:7px;padding:.25rem .5rem;font-size:12px;display:none;max-width:60ch;
  box-shadow:0 2px 10px rgba(0,0,0,.14);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#panel{width:290px;flex:none;border-left:1px solid var(--border);background:var(--surface-1);
  padding:.7rem .8rem;overflow:auto;font-size:12.5px}
#panel h2{font-size:13px;margin:.1rem 0 .3rem;word-break:break-all;font-weight:500}
#panel .meta{color:var(--text-muted);font-size:11.5px;margin-bottom:.6rem}
#panel .lbl{font-size:11px;letter-spacing:.03em;color:var(--text-secondary);margin:.7rem 0 .25rem}
#panel ul{list-style:none;margin:0;padding:0}
#panel li{padding:.16rem 0;border-bottom:1px solid var(--border);word-break:break-all;cursor:pointer;
  color:var(--text-secondary)}
#panel li:hover{color:var(--text-primary)}
#panel li .k{color:var(--text-muted);font-size:10.5px}
.empty{color:var(--text-muted)}
@media (max-width:720px){#panel{display:none}#panel.open{display:block;position:absolute;right:0;top:0;bottom:0;z-index:5}}
</style>
</head>
<body>
<header>
  <div>
    <h1>file graph — <span class="mono">__TITLE__</span></h1>
    <div class="sub mono path" title="__ROOT__">__ROOT__</div>
  </div>
  <div class="sub">__COUNTS__ · generated __GENERATED__</div>
  <span class="grow"></span>
  <input id="q" type="search" placeholder="filter nodes…" autocomplete="off">
  <span id="qn" class="sub"></span>
  <button id="fit" type="button">fit</button>
  <button id="reheat" type="button">re-layout</button>
  <button id="theme" type="button">light / dark</button>
</header>
<main>
  <div id="stage">
    <canvas id="cv"></canvas>
    <div id="tip"></div>
    <div id="legend"></div>
  </div>
  <aside id="panel"><div class="empty">Click a node to pin it and see what it links to.<br><br>
    Drag a node to move it · drag the background to pan · scroll to zoom.</div></aside>
</main>
<script>
(function(){
var DATA = "__GRAPH_DATA__";
var merged = DATA.mode === "merged";
var cv = document.getElementById('cv'), ctx = cv.getContext('2d');
var tip = document.getElementById('tip'), panel = document.getElementById('panel');
var root = document.documentElement, W = 0, H = 0, DPR = 1;

/* ---- model ---- */
var nodes = DATA.nodes.map(function(n, i){
  var h = 0, s = n.id; for (var k = 0; k < s.length; k++) h = (h * 31 + s.charCodeAt(k)) | 0;
  var ang = (h % 1000) / 1000 * Math.PI * 2, rad = 60 + ((h >> 7) % 320);
  return {id:n.id, label:n.label || n.id, type:n.type, project:n.project||null,
          size:n.size||0, mtime:n.mtime||0, deg:n.degree||0,
          x:Math.cos(ang)*rad, y:Math.sin(ang)*rad, vx:0, vy:0, pin:false, on:true};
});
var index = {}; nodes.forEach(function(n,i){ index[n.id] = i; });
var edges = [];
DATA.edges.forEach(function(e){
  var a = index[e.from], b = index[e.to];
  if (a === undefined || b === undefined) return;
  edges.push({a:a, b:b, kind:e.kind});
});
var out = {}, inc = {};
edges.forEach(function(e){
  (out[e.a] = out[e.a] || []).push(e); (inc[e.b] = inc[e.b] || []).push(e);
});
var clusters = {};
if (merged && DATA.projects) DATA.projects.forEach(function(p, i){
  /* cluster centres on a ring wide enough for the biggest project */
  var r = 150 + Math.sqrt(DATA.nodes.length) * 26 + DATA.projects.length * 20;
  var a = i / DATA.projects.length * Math.PI * 2;
  clusters[p.name] = {x:Math.cos(a)*r, y:Math.sin(a)*r, color:p.color, name:p.name};
});
nodes.forEach(function(n){
  var c = n.project && clusters[n.project];
  if (c) { n.x = c.x + n.x * 0.35; n.y = c.y + n.y * 0.35; }
});

/* ---- colors ---- */
var COL = {};
function readColors(){
  var cs = getComputedStyle(root);
  ['estate','doc','code','config','other','external','project'].forEach(function(t){
    COL[t] = cs.getPropertyValue('--c-' + t).trim() || '#888';
  });
  COL.edge = cs.getPropertyValue('--edge').trim();
  COL.edgeHi = cs.getPropertyValue('--edge-hi').trim();
  COL.text = cs.getPropertyValue('--text-primary').trim();
  COL.muted = cs.getPropertyValue('--text-muted').trim();
}
function colorOf(n){
  if (merged && n.project && clusters[n.project] && n.type !== 'external')
    return n.type === 'project' ? clusters[n.project].color : clusters[n.project].color;
  return COL[n.type] || COL.other;
}
var GENERIC = /^(SKILL\.md|README\.md|CLAUDE\.md|index\.[a-z]+|__init__\.py|package\.json|graph\.json)$/;
function shortLabel(n){
  var parts = n.label.split('/'), base = parts[parts.length - 1];
  return (parts.length > 1 && GENERIC.test(base)) ? parts[parts.length - 2] + '/' + base : base;
}
function radius(n){
  return (n.type === 'project' ? 9 : 3) + Math.min(11, Math.sqrt(n.deg) * 1.7);
}

/* ---- physics: repulsion + springs + gravity, cooled ---- */
var alpha = 1, view = {x:0, y:0, k:1};
function step(){
  var i, j, n, m, dx, dy, d2, d, f;
  for (i = 0; i < nodes.length; i++){
    n = nodes[i];
    for (j = i + 1; j < nodes.length; j++){
      m = nodes[j];
      dx = m.x - n.x; dy = m.y - n.y; d2 = dx*dx + dy*dy;
      if (d2 > 90000 || d2 === 0){ if (d2 === 0){ m.x += 0.7; m.y -= 0.7; } continue; }
      f = 900 / d2;
      dx *= f; dy *= f;
      n.vx -= dx; n.vy -= dy; m.vx += dx; m.vy += dy;
    }
  }
  for (i = 0; i < edges.length; i++){
    n = nodes[edges[i].a]; m = nodes[edges[i].b];
    dx = m.x - n.x; dy = m.y - n.y; d = Math.sqrt(dx*dx + dy*dy) || 0.01;
    f = (d - 46) * 0.012;
    dx = dx / d * f; dy = dy / d * f;
    n.vx += dx; n.vy += dy; m.vx -= dx; m.vy -= dy;
  }
  for (i = 0; i < nodes.length; i++){
    n = nodes[i];
    var cx = 0, cy = 0, g = 0.014;
    var c = merged && n.project && clusters[n.project];
    if (c){ cx = c.x; cy = c.y; g = 0.03; }
    n.vx += (cx - n.x) * g; n.vy += (cy - n.y) * g;
    if (n.pin || n === dragging){ n.vx = n.vy = 0; continue; }
    n.vx *= 0.82; n.vy *= 0.82;
    n.x += n.vx * alpha * 2.2; n.y += n.vy * alpha * 2.2;
  }
  alpha *= 0.988;
}
function fitView(){
  if (!nodes.length) return;
  var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (var i = 0; i < nodes.length; i++){
    var n = nodes[i];
    if (n.x < x0) x0 = n.x; if (n.x > x1) x1 = n.x;
    if (n.y < y0) y0 = n.y; if (n.y > y1) y1 = n.y;
  }
  var w = Math.max(1, x1 - x0), h = Math.max(1, y1 - y0);
  view.k = Math.max(0.15, Math.min(2.2, Math.min((W - 90) / w, (H - 90) / h)));
  view.x = -(x0 + x1) / 2; view.y = -(y0 + y1) / 2;
}

/* ---- draw ---- */
var hover = null, selected = null, dragging = null, query = '';
var stage = document.getElementById('stage');
/* ONE place that sizes the canvas: CSS box, backing store and transform together,
   always against the CURRENT viewport. Returns true when anything changed. */
function sizeCanvas(){
  var r = stage.getBoundingClientRect();
  var cssW = Math.max(1, Math.round(r.width)), cssH = Math.max(1, Math.round(r.height));
  var dpr = window.devicePixelRatio || 1;
  var bw = Math.round(cssW * dpr), bh = Math.round(cssH * dpr);
  if (cssW === W && cssH === H && cv.width === bw && cv.height === bh && dpr === DPR)
    return false;
  W = cssW; H = cssH; DPR = dpr;
  cv.style.width = cssW + 'px'; cv.style.height = cssH + 'px';
  cv.width = bw; cv.height = bh;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  return true;
}
function toScreen(n){ return {x:(n.x + view.x) * view.k + W/2, y:(n.y + view.y) * view.k + H/2}; }
function toWorld(px, py){ return {x:(px - W/2) / view.k - view.x, y:(py - H/2) / view.k - view.y}; }
function litEdge(e){
  var s = selected === null ? -1 : selected;
  return e.a === s || e.b === s || (hover !== null && (e.a === hover || e.b === hover));
}
function draw(){
  ctx.clearRect(0, 0, W, H);
  ctx.lineWidth = Math.min(1.4, 0.9 / Math.sqrt(view.k)) * view.k;
  for (var i = 0; i < edges.length; i++){
    var e = edges[i], n = nodes[e.a], m = nodes[e.b];
    var lit = litEdge(e);
    if (!lit && (!n.on || !m.on)) continue;
    var A = toScreen(n), B = toScreen(m);
    ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y);
    ctx.strokeStyle = lit ? COL.edgeHi : COL.edge;
    ctx.globalAlpha = lit ? 0.85 : (query ? 0.18 : 0.42);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  var labelAll = view.k > 1.25;
  var degMin = view.k > 0.9 ? 6 : (view.k > 0.55 ? 10 : 16);
  for (var k = 0; k < nodes.length; k++){
    var nd = nodes[k], P = toScreen(nd), r = radius(nd) * Math.min(1.6, Math.max(0.55, view.k));
    if (P.x < -40 || P.y < -40 || P.x > W + 40 || P.y > H + 40) continue;
    ctx.globalAlpha = nd.on ? 1 : 0.2;
    ctx.beginPath(); ctx.arc(P.x, P.y, r, 0, 6.2832);
    ctx.fillStyle = colorOf(nd); ctx.fill();
    if (k === selected || k === hover || nd.pin){
      ctx.lineWidth = 2; ctx.strokeStyle = COL.edgeHi; ctx.stroke();
    }
    if (nd.on && (labelAll || k === selected || k === hover || nd.type === 'project'
                  || nd.deg >= degMin)){
      var t = shortLabel(nd);
      ctx.font = (nd.type === 'project' ? '600 ' : '') + '11px -apple-system,system-ui,sans-serif';
      ctx.fillStyle = (k === selected || k === hover) ? COL.text : COL.muted;
      ctx.globalAlpha = nd.on ? 1 : 0.2;
      ctx.fillText(t, P.x + r + 3, P.y + 3.5);
    }
  }
  ctx.globalAlpha = 1;
}
var ticks = 0, userMoved = false, guard = 0;
function frame(){
  /* viewport guard: a resize event can be missed (panes, zoom, dpr changes) —
     re-check the box periodically and re-frame whenever it actually moved */
  if ((guard = (guard + 1) % 10) === 0 && sizeCanvas()) fitView();
  if (alpha > 0.004 && !dragging){
    step(); ticks++;
    if (!userMoved && ticks % 4 === 0) fitView();   /* auto-frame while it settles */
  }
  draw();
  requestAnimationFrame(frame);
}

/* ---- picking + interaction ---- */
function pick(px, py){
  var best = null, bd = 1e9;
  for (var i = 0; i < nodes.length; i++){
    var P = toScreen(nodes[i]), dx = P.x - px, dy = P.y - py, d = dx*dx + dy*dy;
    var r = radius(nodes[i]) * Math.min(1.6, Math.max(0.55, view.k)) + 5;
    if (d < r*r && d < bd){ bd = d; best = i; }
  }
  return best;
}
var pan = null, moved = false;
cv.addEventListener('mousedown', function(ev){
  var r = cv.getBoundingClientRect(), px = ev.clientX - r.left, py = ev.clientY - r.top;
  var i = pick(px, py); moved = false;
  if (i !== null){ dragging = nodes[i]; dragging._i = i; }
  else { pan = {x:px, y:py, vx:view.x, vy:view.y}; }
  cv.classList.add('drag');
});
window.addEventListener('mousemove', function(ev){
  var r = cv.getBoundingClientRect(), px = ev.clientX - r.left, py = ev.clientY - r.top;
  if (dragging){
    var w = toWorld(px, py); dragging.x = w.x; dragging.y = w.y;
    dragging.vx = dragging.vy = 0; moved = true; userMoved = true;
    alpha = Math.max(alpha, 0.12); return;
  }
  if (pan){ view.x = pan.vx + (px - pan.x) / view.k; view.y = pan.vy + (py - pan.y) / view.k;
            moved = true; userMoved = true; return; }
  if (px < 0 || py < 0 || px > W || py > H){ hover = null; tip.style.display = 'none'; return; }
  var i = pick(px, py);
  hover = i;
  if (i === null){ tip.style.display = 'none'; cv.style.cursor = 'grab'; return; }
  var n = nodes[i];
  cv.style.cursor = 'pointer';
  tip.textContent = n.label + '  ·  ' + n.deg + ' link' + (n.deg === 1 ? '' : 's');
  tip.style.display = 'block';
  tip.style.left = Math.min(W - 30, px + 14) + 'px';
  tip.style.top = (py + 16) + 'px';
});
window.addEventListener('mouseup', function(){
  if (dragging && !moved){ select(dragging._i, true); }
  dragging = null; pan = null; cv.classList.remove('drag');
});
cv.addEventListener('wheel', function(ev){
  ev.preventDefault();
  userMoved = true;
  var r = cv.getBoundingClientRect(), px = ev.clientX - r.left, py = ev.clientY - r.top;
  var before = toWorld(px, py);
  view.k = Math.max(0.15, Math.min(6, view.k * (ev.deltaY < 0 ? 1.12 : 1/1.12)));
  var after = toWorld(px, py);
  view.x += after.x - before.x; view.y += after.y - before.y;
}, {passive:false});

/* ---- side panel ---- */
function fmt(n){
  var kb = n.size >= 1024 ? (n.size/1024).toFixed(1) + ' KB' : n.size + ' B';
  var d = n.mtime ? new Date(n.mtime * 1000).toISOString().slice(0, 10) : '—';
  return n.type + ' · ' + (n.size ? kb : 'external') + ' · ' + d;
}
function list(items, dir){
  if (!items.length) return '<div class="empty">none</div>';
  return '<ul>' + items.map(function(e){
    var other = dir === 'out' ? nodes[e.b] : nodes[e.a];
    return '<li data-i="' + (dir === 'out' ? e.b : e.a) + '">' + esc(other.label) +
           ' <span class="k">' + esc(e.kind) + '</span></li>';
  }).join('') + '</ul>';
}
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
  return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]; }); }
function select(i, pinIt){
  selected = i;
  var n = nodes[i];
  if (pinIt) n.pin = true;
  panel.classList.add('open');
  panel.innerHTML = '<h2>' + esc(n.label) + '</h2><div class="meta">' + esc(fmt(n)) +
    ' · ' + n.deg + ' link' + (n.deg === 1 ? '' : 's') +
    (n.project ? ' · ' + esc(n.project) : '') + '</div>' +
    '<button id="unpin" type="button">' + (n.pin ? 'unpin' : 'pin') + '</button> ' +
    '<button id="center" type="button">center</button>' +
    '<div class="lbl">links out (' + (out[i] || []).length + ')</div>' + list(out[i] || [], 'out') +
    '<div class="lbl">links in (' + (inc[i] || []).length + ')</div>' + list(inc[i] || [], 'in');
  panel.querySelectorAll('li').forEach(function(li){
    li.addEventListener('click', function(){ select(+li.dataset.i, false); });
  });
  document.getElementById('unpin').addEventListener('click', function(){
    n.pin = !n.pin; alpha = Math.max(alpha, 0.2); select(i, false);
  });
  document.getElementById('center').addEventListener('click', function(){
    view.x = -n.x; view.y = -n.y;
  });
}

/* ---- search, legend, theme ---- */
var q = document.getElementById('q'), qn = document.getElementById('qn');
q.addEventListener('input', function(){
  query = q.value.trim().toLowerCase();
  var shown = 0;
  nodes.forEach(function(n){
    n.on = !query || n.label.toLowerCase().indexOf(query) >= 0;
    if (n.on) shown++;
  });
  qn.textContent = query ? shown + '/' + nodes.length : '';
});
function legend(){
  var el = document.getElementById('legend'), items = [];
  if (merged && DATA.projects){
    DATA.projects.forEach(function(p){
      items.push(['<span><i class="dot" style="background:' + p.color + '"></i>' +
                  esc(p.name) + ' <span style="color:var(--text-muted)">' + p.nodes +
                  '</span></span>'].join(''));
    });
    items.push('<span><i class="dot" style="background:var(--c-external)"></i>external</span>');
  } else {
    [['estate','estate (COORD / CLAUDE.md / START-HERE / spend)'], ['doc','docs'],
     ['code','code'], ['config','config'], ['other','other'],
     ['external','external ref']].forEach(function(p){
      var n = nodes.filter(function(x){ return x.type === p[0]; }).length;
      if (n) items.push('<span><i class="dot" style="background:var(--c-' + p[0] + ')"></i>' +
                        p[1] + ' <span style="color:var(--text-muted)">' + n + '</span></span>');
    });
  }
  el.innerHTML = items.join('');
}
document.getElementById('theme').addEventListener('click', function(){
  var cur = root.getAttribute('data-theme') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  root.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark');
  readColors();
});
document.getElementById('fit').addEventListener('click', fitView);
document.getElementById('reheat').addEventListener('click', function(){
  alpha = 1; ticks = 0; userMoved = false; nodes.forEach(function(n){ n.pin = false; });
});
function onViewportChange(){ sizeCanvas(); fitView(); }
window.addEventListener('resize', onViewportChange);
window.addEventListener('orientationchange', onViewportChange);
if (window.ResizeObserver) new ResizeObserver(onViewportChange).observe(stage);
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', readColors);

readColors(); legend(); sizeCanvas(); fitView(); frame();
})();
</script>
</body>
</html>
"""


# ============================================================== river: the data
#
# The river answers a different question than the file graph. The file graph is
# SPACE (what points at what); the river is TIME (how the work moved toward the
# goal, where it went sideways, where it doubled back, what it hit on the way).
# Input is the append-only findings ledger; the COORD volumes supply the
# milestone flags and COORD-AGENTS.md the lane activity along the banks.

RIVER_KINDS = ("finding", "result", "decision", "conflict", "backtrack", "side-route")
RIVER_RELS = ("toward", "lateral", "back")
RIVER_STATUS = ("live", "superseded", "refuted")
RIVER_CAP = 500            # nodes drawn; older ones are dropped, never silently
RIVER_LANE_CAP = 300       # agent-ledger ticks drawn along the bottom bank
BRIEF_HEAD = 200           # chars of a lane brief shown on its hover card
FINDINGS_REL = "archive/findings.jsonl"

# layout constants — every coordinate below is a pure function of these and the
# record order, so two runs over the same ledger produce byte-identical geometry.
RX0 = 190.0          # x of the first record
RXSTEP = 150.0       # x per time index
RCH_GAP = 158.0      # y between channel centrelines (side channels run BELOW)
RMEANDER_A = 24.0    # meander amplitude
RMEANDER_W = 0.55    # meander frequency (radians per time index)
RTOP_BANK = 215.0    # milestone bank above the main channel
RBOT_BANK = 195.0    # lane bank below the lowest channel
RBANK_INSET = 66.0   # waterline → the sand it runs between
RCOMM_BAND = 92.0    # extra bottom sand when commission glyphs need a row of it
RGOAL_PAD = 300.0    # river mouth → goal bank

RIVER_COORD_RE = re.compile(
    r"^-\s*\[(?P<ts>\d{4}-\d{2}-\d{2}[^\]]*)\]\s*(?:\[(?P<lane>[^\]]*)\]\s*)?(?P<body>.+)$")
RIVER_AGENT_RE = re.compile(
    r"^-\s*\[(?P<ts>\d{4}-\d{2}-\d{2}[^\]]*)\]\s*agent=(?P<agent>\S+)(?P<rest>.*)$")
# COORD lines are overlaid on EVERY river, not only the degraded one: the flags
# are the milestones the ledger already records — what shipped, what was gated,
# what was taken back. Ship outranks gate outranks correction on one line.
RIVER_SHIP_RE = re.compile(
    r"(\bship(?:s|ped|ping)?\b|\brelease[ds]?\b|\bv\d+\.\d+\.\d+\b)", re.I)
RIVER_GATE_RE = re.compile(r"(\bgat(?:e|es|ed|ing)\b)", re.I)
RIVER_CORR_RE = re.compile(
    r"(\bcorrection\b|\bcorrected\b|\brevert\w*\b|\brolled back\b|\brollback\b|"
    r"\bwithdraw\w*\b|\bstopped\b|\bdisproven\b|\bnot landed\b)", re.I)
RIVER_VER_RE = re.compile(r"\bv\d+\.\d+\.\d+\b")
RE_SUPERSEDE = re.compile(r"supersed", re.I)
RE_REFUTE = re.compile(r"\brefut", re.I)

# COORD-only degrade mode: the ledger has no relation/kind fields, so these
# HEURISTICS read the line's own words. They are declared as heuristics in the
# JSON (`inferred: true` on every node), in the legend, and in SKILL.md — the
# river never presents an inference as an authored record.
RE_CO_CONFLICT = re.compile(
    r"\b(conflict|refut\w*|disproven|defect|blocker|violation|root cause|regression|"
    r"broke\w*|bug|fail\w*)\b", re.I)
RE_CO_BACK = re.compile(
    r"\b(correction|corrected|revert\w*|rollback|rolled back|withdraw\w*|stopped|"
    r"abandon\w*|not landed|misread|undone|disproven)\b", re.I)
RE_CO_DECISION = re.compile(
    r"\b(ruling|owner order|owner design|decision|decided|verdict|policy|law)\b", re.I)
RE_CO_LATERAL = re.compile(
    r"\b(side-?finding|papercut|parked|deferred|backlog|assessment|analysis|inventor\w+|"
    r"explor\w+|diagnos\w+|audit|cross-check|delivered|scope|probe)\b", re.I)


def _slurp(path):
    """Whole-file text, uncapped and never binary-sniffed — the ledgers are text
    by contract, and read_text() deliberately refuses .jsonl for the file graph."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def tskey(s):
    """A sortable, comparable key from either timestamp dialect the estate uses:
    findings ISO8601Z (2026-07-25T14:55:00Z) and COORD (2026-07-25 14:55Z)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ]?(\d{2})?:?(\d{2})?:?(\d{2})?", str(s or "").strip())
    if not m:
        return ""
    y, mo, d, h, mi, sec = m.groups()
    return f"{y}-{mo}-{d}T{h or '00'}:{mi or '00'}:{sec or '00'}"


def id_key(i):
    m = re.match(r"^(.*?)(\d+)$", str(i))
    return (m.group(1), int(m.group(2))) if m else (str(i), 0)


def _clip(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def normalize_record(o, ref):
    """One findings.jsonl object → the river's record shape. Every field is
    coerced, never trusted: a malformed ledger degrades the drawing, not the run."""
    kind = str(o.get("kind") or "").strip().lower()
    if kind not in RIVER_KINDS:
        kind = "finding"
    rel = str(o.get("relation") or "").strip().lower()
    if rel not in RIVER_RELS:
        # a missing relation is inferable from the kind, and only from the kind
        rel = {"backtrack": "back", "side-route": "lateral"}.get(kind, "toward")
    status = str(o.get("status") or "").strip().lower()
    if status not in RIVER_STATUS:
        status = "live"
    ev = []
    raw_ev = o.get("evidence")
    if isinstance(raw_ev, list):
        for e in raw_ev:
            if isinstance(e, dict):
                ev.append({"type": str(e.get("type") or ""),
                           "ref": str(e.get("ref") or ""),
                           "label": str(e.get("label") or "unverified")})
            elif e:
                ev.append({"type": "", "ref": str(e), "label": "unverified"})
    links = [str(x) for x in (o.get("links") or []) if x] if isinstance(o.get("links"), list) else []
    return {"id": str(o.get("id")), "ts": str(o.get("ts") or ""),
            "session": str(o.get("session") or ""), "skill": str(o.get("skill") or ""),
            "kind": kind, "relation": rel, "ask": str(o.get("ask") or ""),
            "statement": str(o.get("statement") or ""), "evidence": ev,
            "links": links, "status": status, "inferred": False, "ref": ref}


def read_findings(path, rel_name, session=None):
    """archive/findings.jsonl → records. Bad lines are counted, never fatal."""
    text = _slurp(path)
    if text is None:
        return [], 0, 0
    recs, bad, total = [], 0, 0
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            o = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if not isinstance(o, dict) or not o.get("id"):
            bad += 1
            continue
        total += 1
        if session and str(o.get("session") or "") != session:
            continue
        recs.append(normalize_record(o, f"{rel_name}:{i}"))
    return recs, bad, total


def coord_volumes(root):
    """Sealed volumes oldest-first, then the retired archive, then the active one
    — the same order compile.py reads them in."""
    sealed = sorted(p.name for p in root.glob("COORD-*.md")
                    if p.stem.split("-")[-1].isdigit() and p.stem.count("-") == 1)
    return sealed + ["COORD-ARCHIVE.md", "COORD.md"]


def read_coord_lines(root, session=None):
    """COORD ledger lines: `- [ts] [lane] ask -> landed | evidence: …`."""
    items = []
    for fn in coord_volumes(root):
        text = _slurp(root / fn)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = RIVER_COORD_RE.match(line.strip())
            if not m:
                continue
            lane = (m.group("lane") or "").strip()
            if session and lane != session:
                continue
            body = m.group("body").strip()
            head, _, ev = body.partition("| evidence:")
            ask, _, landed = head.partition(" -> ")
            flag = ("ship" if RIVER_SHIP_RE.search(body) else
                    "gate" if RIVER_GATE_RE.search(body) else
                    "correction" if RIVER_CORR_RE.search(body) else None)
            items.append({"ts": m.group("ts").strip(), "lane": lane,
                          "ask": ask.strip(), "landed": landed.strip(),
                          "evidence": ev.strip(), "body": body,
                          "ref": f"{fn}:{i}", "flag": flag, "ship": flag == "ship",
                          "_k": tskey(m.group("ts"))})
    return items


def read_brief(root, rel):
    """A receipt's `brief:` pointer → (head, ok, why).

    COMMISSION TRANSPARENCY (owner core value, 2026-07-27): what a lane was
    actually asked must be visible without asking the seat. The SubagentStop hook
    banks the prompt; the receipt points at it; this reads it. Three honest
    outcomes and no fourth: banked (head text), pointer with no file (`missing`),
    no pointer at all (`none`) — a dead pointer is never drawn as a commission.

    The pointer is text from a ledger file, so it is treated as untrusted: a path
    that resolves outside the root is REFUSED, not read. The ledger is
    machine-written today; `../../..` in it must still never make this open a
    file the river was not pointed at."""
    if not rel:
        return "", False, "none"
    try:
        p = (root / rel).resolve()
        if not str(p).startswith(str(root.resolve()) + os.sep):
            return "", False, "outside-root"
    except (OSError, ValueError):
        return "", False, "unresolvable"
    if not p.is_file():
        return "", False, "missing"
    text = _slurp(p)
    if text is None:
        return "", False, "unreadable"
    # the hook writes a generated header, then `---`, then the verbatim prompt.
    # The prompt is the point; showing 200 chars of our own header would be a
    # commission nobody can read. No separator → the whole file is the brief.
    body = text.split("\n---\n", 1)[1] if "\n---\n" in text else text
    return _clip(body.strip(), BRIEF_HEAD), True, "banked"


def read_agent_lines(root, session=None):
    """COORD-AGENTS.md → lane activity ticks. The hook writes `model=?` when the
    transcript wasn't on disk yet; that stays a `?`, it is not guessed. A receipt
    that carries `| brief: <path>` and whose file is really there becomes a
    COMMISSION tick — the lane's exact prompt, drawn."""
    items = []
    text = _slurp(root / "COORD-AGENTS.md")
    if text is None:
        return items
    for i, line in enumerate(text.splitlines(), 1):
        m = RIVER_AGENT_RE.match(line.strip())
        if not m:
            continue
        rest = m.group("rest")
        mm = re.search(r"model=(\S+)", rest)
        model = mm.group(1) if mm else "?"
        last = re.search(r"\|\s*last:\s*(.*?)\s*\|\s*transcript:", rest)
        bm = re.search(r"\|\s*brief:\s*(\S+)", rest)
        brel = bm.group(1) if bm else ""
        head, ok, why = read_brief(root, brel)
        items.append({"ts": m.group("ts").strip(), "agent": m.group("agent"),
                      "model": model, "last": _clip(last.group(1) if last else "", 160),
                      "brief": brel, "brief_head": head, "commission": ok,
                      "brief_state": why,
                      "ref": f"COORD-AGENTS.md:{i}", "_k": tskey(m.group("ts"))})
    if session:
        items = [x for x in items if session in x["last"]]
    return items


def records_from_coord(coord_items):
    """DEGRADE PATH — no findings ledger, so the ledger lines themselves become
    the river. Kind and relation are read off the line's words by heuristic and
    every node carries `inferred: true`; links are chronological, not authored
    (a lateral line rejoins at the next toward line because that is when the work
    came back, not because anything in the ledger says so)."""
    recs = []
    last_toward = None
    open_side = []          # ids of the lateral run still off the main channel
    for n, c in enumerate(coord_items, 1):
        body = c["body"]
        # relation first, and the RARER signal wins: "correction / stopped /
        # withdrawn" is always a return upstream, while ship words are on most
        # lines of a release day and mean nothing on their own.
        if RE_CO_BACK.search(body):
            rel = "back"
        elif c["flag"] in ("ship", "gate"):
            rel = "toward"                      # a release or a gate is the main channel
        elif RE_CO_LATERAL.search(body):
            rel = "lateral"
        else:
            rel = "toward"
        if rel == "back":
            kind = "backtrack"
        elif RE_CO_CONFLICT.search(body):
            kind = "conflict"
        elif RE_CO_DECISION.search(body):
            kind = "decision"
        elif c["evidence"]:
            kind = "result"
        else:
            kind = "finding"
        rid = f"C-{n}"
        links = []
        if rel == "toward":
            if open_side:
                links.append(open_side[-1])     # the side run rejoins here
                open_side = []
            elif last_toward:
                links.append(last_toward)
            last_toward = rid
        else:
            links = [open_side[-1] if open_side else last_toward] if (open_side or last_toward) else []
            if rel == "lateral":
                open_side.append(rid)
        ev = [{"type": "coord-line", "ref": c["evidence"] or c["ref"],
               "label": "cited" if c["evidence"] else "unverified"}]
        recs.append({"id": rid, "ts": c["ts"], "session": c["lane"], "skill": "coord",
                     "kind": kind, "relation": rel, "ask": c["ask"] or c["body"],
                     "statement": c["landed"], "evidence": ev,
                     "links": [x for x in links if x], "status": "live",
                     "inferred": True, "ref": c["ref"]})
    return recs


def resolve_status(recs):
    """Effective status by link-walking: a LATER record that links an older one
    and says it supersedes/refutes it overrides that record's declared status.
    Refuted outranks superseded; a record's own declared status is the floor."""
    rank = {"live": 0, "superseded": 1, "refuted": 2}
    eff = {r["id"]: r["status"] for r in recs}
    by, over, pairs = {}, {}, set()
    for i, r in enumerate(recs):
        by[r["id"]] = i
    for i, r in enumerate(recs):
        if r.get("inferred"):
            # COORD-only nodes carry SYNTHESIZED links (chronology, not authorship).
            # Reading "refuter verdict…" on such a record and marking the previous
            # ledger line refuted would be the river inventing a claim. It doesn't.
            continue
        st = r["statement"] or ""
        verb = "refuted" if RE_REFUTE.search(st) else ("superseded" if RE_SUPERSEDE.search(st) else None)
        if not verb:
            continue
        for l in r["links"]:
            if l in by and by[l] < i:
                pairs.add((r["id"], l))
                over.setdefault(l, []).append(r["id"])
                if rank[verb] > rank[eff[l]]:
                    eff[l] = verb
    return eff, over, pairs


def assign_channels(recs):
    """One deterministic pass in time order.

    channel 0 is the main channel (relation `toward`). A `lateral` record joins
    the side channel of a node it links, or opens a new one; `side-route` ALWAYS
    forks a new channel (that is what the kind means). A `back` record stays in
    the flow it interrupts — the channel of the record before it."""
    chan, chans = {}, {0: {"id": 0, "kind": "main", "origin": None, "nodes": []}}
    prev = None
    for r in recs:
        rel, kind = r["relation"], r["kind"]
        known = [l for l in r["links"] if l in chan]
        if kind == "side-route" or (rel == "lateral" and not any(chan[l] for l in known)):
            # a fork: new channel, mouth at the linked node (else the last node)
            cid = max(chans) + 1
            origin = known[0] if known else prev
            chans[cid] = {"id": cid, "kind": "side", "origin": origin, "nodes": []}
            c = cid
        elif rel == "lateral":
            c = min(chan[l] for l in known if chan[l])
        elif rel == "back":
            c = chan.get(prev, 0)
        else:
            c = 0
        chan[r["id"]] = c
        chans[c]["nodes"].append(r["id"])
        prev = r["id"]
    return chan, chans


def river_stamp(keys, use_now):
    """REPRODUCIBILITY LAW: identical inputs must render byte-identical output, so
    the page is stamped with the newest INPUT timestamp — not the wall clock.
    `--now` opts back into clock time when you actually want run time."""
    if use_now:
        return now_stamp(), "wall-clock"
    keys = [k for k in keys if k]
    if not keys:
        return "(no dated input)", "newest-input"
    return max(keys).replace("T", " ")[:16] + "Z", "newest-input"


def build_river(root, session=None, cap=RIVER_CAP, use_now=False):
    notes = []
    fpath = root / "archive" / "findings.jsonl"
    recs, bad, total_recs = [], 0, 0
    if fpath.is_file():
        recs, bad, total_recs = read_findings(fpath, FINDINGS_REL, session)
        if bad:
            notes.append(f"{bad} unparseable line(s) in {FINDINGS_REL} skipped")
    coord_all = read_coord_lines(root, session)
    mode = "findings+coord"
    if not recs:
        mode = "coord-only"
        if not fpath.is_file():
            notes.append(f"{FINDINGS_REL} absent — COORD-only river: every node is a "
                         "ledger line, its kind and relation inferred by heuristic")
        elif session and total_recs:
            notes.append(f"{FINDINGS_REL} holds {total_recs} record(s) but none for "
                         f"session '{session}' — COORD-only river")
        else:
            notes.append(f"{FINDINGS_REL} holds no usable records — COORD-only river")
        recs = records_from_coord(coord_all)
    elif not coord_all:
        notes.append("no COORD ledger lines found — no milestone flags on the bank")

    recs.sort(key=lambda r: (tskey(r["ts"]), id_key(r["id"]), r["id"]))
    total = len(recs)
    capped = None
    if cap and total > cap:
        recs = recs[-cap:]
        capped = {"shown": len(recs), "total": total}
        notes.append(f"showing the last {len(recs)} of {total} records (--cap {cap})")
    kept = {r["id"] for r in recs}
    for r in recs:
        r["links"] = [l for l in r["links"] if l in kept]

    eff, over, override_pairs = resolve_status(recs)
    # ---- RESTS-ON-REFUTED: a record that is itself LIVE but whose links contain
    # an effectively-refuted id is standing on refuted ground. Deliberately ONE
    # HOP — the rule reads the record's own links and does not walk the chain
    # transitively, because a transitive claim about ground nobody cited would be
    # the river inventing a dependency. The refuter is excluded: a record that
    # refutes another one is not resting on it.
    rests = {}
    for r in recs:
        if eff[r["id"]] != "live":
            continue
        src = [l for l in dict.fromkeys(r["links"])
               if eff.get(l) == "refuted" and (r["id"], l) not in override_pairs]
        if src:
            rests[r["id"]] = sorted(src, key=id_key)
    chan, chans = assign_channels(recs)
    idx = {r["id"]: i for i, r in enumerate(recs)}

    # ---- geometry: x is the time index, y is the channel (+ a fixed meander)
    nodes = []
    for i, r in enumerate(recs):
        c = chan[r["id"]]
        x = RX0 + i * RXSTEP
        y = c * RCH_GAP + RMEANDER_A * math.sin(i * RMEANDER_W + c * 1.31)
        n = dict(r)
        n.update({"i": i, "channel": c, "x": round(x, 2), "y": round(y, 2),
                  "effective": eff[r["id"]], "superseded_by": over.get(r["id"], []),
                  "rock": r["kind"] == "conflict" or eff[r["id"]] == "refuted",
                  "rests_on": rests.get(r["id"], []),
                  "_k": tskey(r["ts"])})
        nodes.append(n)
    pos = {n["id"]: n for n in nodes}

    # ---- merges: the first MAIN-channel record that links into a side channel
    # rejoins it. Supersede/refute links are excluded — a refutation is not a
    # rejoining of the flow, and drawing it as one would be a lie about the shape.
    merge_of = {}
    for n in nodes:
        if n["channel"] != 0:
            continue
        for l in n["links"]:
            c = chan.get(l)
            if not c or c in merge_of or (n["id"], l) in override_pairs:
                continue
            if idx[l] < n["i"]:
                merge_of[c] = {"into": n["id"], "from": l}

    # ---- channel geometry: the point list each band is drawn through
    channels, edges = [], []
    for cid in sorted(chans):
        ch = chans[cid]
        ids = ch["nodes"]
        pts = [[pos[i_]["x"], pos[i_]["y"]] for i_ in ids]
        outcome, merge = ("goal" if cid == 0 else "dead-end"), merge_of.get(cid)
        if cid == 0:
            if pts:
                pts = [[pts[0][0] - 260.0, pts[0][1]]] + pts
        else:
            # a side channel leaves and rejoins the parent GRADUALLY — the lead-in
            # and lead-out points are what make it read as water diverging rather
            # than a spike dropped through the main flow.
            org = ch["origin"]
            if org in pos and pts:
                o, f = [pos[org]["x"], pos[org]["y"]], pts[0]
                pts = [o, [round(o[0] + (f[0] - o[0]) * 0.45, 2),
                           round(o[1] + (f[1] - o[1]) * 0.74, 2)]] + pts
            if merge:
                outcome = "merged"
                m, l = [pos[merge["into"]]["x"], pos[merge["into"]]["y"]], pts[-1]
                pts = pts + [[round(m[0] - (m[0] - l[0]) * 0.45, 2),
                              round(l[1] + (m[1] - l[1]) * 0.26, 2)], m]
            elif pts:
                pts = pts + [[round(pts[-1][0] + 95.0, 2), round(pts[-1][1] + 26.0, 2)]]
        for a, b in zip(ids, ids[1:]):
            edges.append({"from": a, "to": b, "kind": "flow"})
        if cid and ch["origin"] in pos and ids:
            edges.append({"from": ch["origin"], "to": ids[0], "kind": "branch"})
        if merge:
            edges.append({"from": merge["from"], "to": merge["into"], "kind": "merge"})
        channels.append({"id": cid, "kind": ch["kind"], "origin": ch["origin"],
                         "first": ids[0] if ids else None, "last": ids[-1] if ids else None,
                         "outcome": outcome, "merge_into": merge["into"] if merge else None,
                         "nodes": ids, "y": round(cid * RCH_GAP, 2),
                         "points": [[round(p[0], 2), round(p[1], 2)] for p in pts]})

    drawn = {(e["from"], e["to"]) for e in edges}
    for n in nodes:
        for l in n["links"]:
            if (n["id"], l) in override_pairs:
                kind = "refute" if eff.get(l) == "refuted" else "supersede"
                edges.append({"from": n["id"], "to": l, "kind": kind})
            elif n["relation"] == "back":
                edges.append({"from": n["id"], "to": l, "kind": "back"})
            elif (l, n["id"]) not in drawn and (n["id"], l) not in drawn:
                edges.append({"from": n["id"], "to": l, "kind": "link"})
    for n in nodes:                       # a backtrack with no link still loops
        if n["relation"] == "back" and not n["links"]:
            prevs = [m for m in nodes if m["i"] < n["i"] and m["channel"] == n["channel"]]
            if prevs:
                edges.append({"from": n["id"], "to": prevs[-1]["id"], "kind": "back"})
    # the INBOUND edge from each refuted source to the live stone standing on it.
    # It is its own edge kind because the flow edge between two adjacent stones is
    # never drawn (the water band IS that edge) — restyling it would show nothing.
    for rid in sorted(rests, key=lambda k: (idx.get(k, 0), k)):
        for src in rests[rid]:
            edges.append({"from": src, "to": rid, "kind": "rests",
                          "rests_on_refuted": True})

    # ---- the banks: milestone flags (ship/gate COORD lines) and lane ticks
    def x_for(key, ref=None):
        if ref:
            for n in nodes:
                if n["ref"] == ref:
                    return n["x"]
        prev_x = None
        for n in nodes:
            if n["_k"] <= key:
                prev_x = n["x"]
            else:
                return (prev_x + RXSTEP * 0.5) if prev_x is not None else RX0 - RXSTEP * 0.6
        return (prev_x + RXSTEP * 0.4) if prev_x is not None else RX0

    milestones = []
    for m in [c for c in coord_all if c["flag"]]:
        ver = RIVER_VER_RE.search(m["body"])
        milestones.append({"ts": m["ts"], "lane": m["lane"], "flag": m["flag"],
                           "ask": m["ask"], "landed": m["landed"], "evidence": m["evidence"],
                           "ref": m["ref"], "label": ver.group(0) if ver else _clip(m["ask"], 22),
                           "x": round(x_for(m["_k"], m["ref"] if mode == "coord-only" else None), 2)})
    lanes_all = read_agent_lines(root)
    lanes = lanes_all[-RIVER_LANE_CAP:]
    if len(lanes_all) > len(lanes):
        notes.append(f"lane ticks: last {len(lanes)} of {len(lanes_all)} agent entries")
    commissioned = sum(1 for l in lanes if l["commission"])
    dead = sorted({l["brief"] for l in lanes
                   if l["brief"] and not l["commission"]})
    if dead:
        notes.append(f"{len(dead)} receipt(s) point at a brief that is not readable "
                     f"({', '.join(dead[:3])}{'…' if len(dead) > 3 else ''}) — drawn as a "
                     f"plain tick, never as a commission")
    if lanes and not commissioned:
        notes.append("no lane on this river banked its commission — every tick predates the "
                     "brief-extracting hook, or the briefs/ directory is gone")
    stamp_keys = ([tskey(r["ts"]) for r in recs] + [c["_k"] for c in coord_all]
                  + [l["_k"] for l in lanes])
    for l in lanes:
        l["x"] = round(x_for(l["_k"]), 2)
        l.pop("_k", None)
    for n in nodes:
        n.pop("_k", None)

    xs = [n["x"] for n in nodes] or [RX0]
    ys = [n["y"] for n in nodes] or [0.0]
    goal_x = max(xs) + RGOAL_PAD
    # the commission row needs sand under it, so the bottom bank GROWS rather than
    # the glyphs spilling past the shore — the extent and the waterline move
    # together, leaving the water itself exactly where it was.
    bot_inset = RBANK_INSET + (RCOMM_BAND if commissioned else 0.0)
    extent = {"x0": round(min(xs) - 320.0, 2), "y0": round(min(ys) - RTOP_BANK, 2),
              "x1": round(goal_x + 150.0, 2),
              "y1": round(max(ys) + RBOT_BANK + (bot_inset - RBANK_INSET), 2)}
    if channels and channels[0]["points"]:
        channels[0]["points"] = channels[0]["points"] + [[round(goal_x - 26.0, 2),
                                                          channels[0]["points"][-1][1]]]

    counts = {"records": len(nodes), "total_records": total,
              "toward": sum(1 for n in nodes if n["relation"] == "toward"),
              "lateral": sum(1 for n in nodes if n["relation"] == "lateral"),
              "back": sum(1 for n in nodes if n["relation"] == "back"),
              "side_route": sum(1 for n in nodes if n["kind"] == "side-route"),
              "conflicts": sum(1 for n in nodes if n["kind"] == "conflict"),
              "rocks": sum(1 for n in nodes if n["rock"]),
              "live": sum(1 for n in nodes if n["effective"] == "live"),
              "superseded": sum(1 for n in nodes if n["effective"] == "superseded"),
              "refuted": sum(1 for n in nodes if n["effective"] == "refuted"),
              "rests_on_refuted": len(rests),
              "channels": len(channels),
              "side_channels": sum(1 for c in channels if c["kind"] == "side"),
              "merged": sum(1 for c in channels if c["outcome"] == "merged"),
              "dead_end": sum(1 for c in channels if c["outcome"] == "dead-end"),
              "edges": len(edges), "milestones": len(milestones),
              "ships": sum(1 for m in milestones if m["flag"] == "ship"),
              "gates": sum(1 for m in milestones if m["flag"] == "gate"),
              "corrections": sum(1 for m in milestones if m["flag"] == "correction"),
              "coord_lines": len(coord_all), "lanes": len(lanes),
              "commissions": commissioned,
              "lanes_uncommissioned": len(lanes) - commissioned}
    stamp, stamp_from = river_stamp(stamp_keys, use_now)
    return {"generated": stamp, "stamp_from": stamp_from,
            "root": str(root), "mode": mode, "session": session, "cap": cap,
            "sources": {"findings": FINDINGS_REL if fpath.is_file() else None,
                        "coord": coord_volumes(root), "agents": "COORD-AGENTS.md"},
            "goal": {"x": round(goal_x, 2), "label": "GOAL"},
            "bankInset": {"top": RBANK_INSET, "bottom": bot_inset},
            "extent": extent, "capped": capped, "notes": notes, "counts": counts,
            "channels": channels, "nodes": nodes, "edges": edges,
            "milestones": milestones, "lanes": lanes}


# ============================================================ river: the viewer

def render_river_html(r, title="project"):
    data = json.dumps(r, separators=(",", ":")).replace("</", "<\\/")
    c = r["counts"]
    counts = (f"{c['records']} records · {c['channels']} channels · "
              f"{c['rocks']} rocks · {c['milestones']} flags")
    mode = ("findings + COORD" if r["mode"] == "findings+coord" else "COORD-only")
    return (RIVER_TEMPLATE
            .replace("__TITLE__", esc(title))
            .replace("__ROOT__", esc(r.get("root", "")))
            .replace("__GENERATED__", esc(r.get("generated", "")))
            .replace("__STAMPFROM__", esc(r.get("stamp_from", "")))
            .replace("__MODE__", esc(mode))
            .replace("__COUNTS__", esc(counts))
            .replace('"__RIVER_DATA__"', data))


RIVER_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>river — __TITLE__</title>
<style>
:root{
  --surface-0:#f7f6f2; --surface-1:#ffffff; --border:#e6e3da; --border-strong:#d2cfc4;
  --text-primary:#20201d; --text-secondary:#57564f; --text-muted:#86857b;
  --water:#5C98D6; --water-core:#9CC8F0; --water-side:#7FA8C4; --sheen:#ffffff;
  --bank:#ddd7c6; --sand:#efeade; --rock:#C2554E; --dead:#B4633A;
  --stone:#9a988c; --stone-edge:#6f6e64; --goal:#1D9E75;
  --back:#D89A3A; --flag-ship:#7F77DD; --flag-gate:#1D9E75; --flag-corr:#D89A3A;
  --lane:#a8a69a; --link:#b9b6aa; --commission:#7F77DD;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --surface-0:#141413; --surface-1:#1f1f1d; --border:#37362e; --border-strong:#4b4a40;
    --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
    --water:#2F6FA8; --water-core:#6FA9E6; --water-side:#44718c; --sheen:#cfe6ff;
    --bank:#332f26; --sand:#1c1b18; --rock:#DD7F77; --dead:#d98a5e;
    --stone:#6c6b62; --stone-edge:#a7a69b; --goal:#3fc79c;
    --back:#e6b45c; --flag-ship:#9a92ea; --flag-gate:#3fc79c; --flag-corr:#e6b45c;
    --lane:#5d5c53; --link:#4a493f; --commission:#9a92ea;
  }
}
:root[data-theme="dark"]{
  --surface-0:#141413; --surface-1:#1f1f1d; --border:#37362e; --border-strong:#4b4a40;
  --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
  --water:#2F6FA8; --water-core:#6FA9E6; --water-side:#44718c; --sheen:#cfe6ff;
  --bank:#332f26; --sand:#1c1b18; --rock:#DD7F77; --dead:#d98a5e;
  --stone:#6c6b62; --stone-edge:#a7a69b; --goal:#3fc79c;
  --back:#e6b45c; --flag-ship:#9a92ea; --flag-gate:#3fc79c; --flag-corr:#e6b45c;
  --lane:#5d5c53; --link:#4a493f; --commission:#9a92ea;
}
*{box-sizing:border-box}
html{height:100%;width:100%}
body{margin:0;width:100vw;height:100vh;background:var(--surface-0);color:var(--text-primary);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  display:flex;flex-direction:column;overflow:hidden}
header{display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:center;padding:.6rem .9rem;
  border-bottom:1px solid var(--border);background:var(--surface-1)}
h1{font-size:14px;font-weight:500;margin:0}
.sub{font-size:12px;color:var(--text-muted)}
.path{max-width:52ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.grow{flex:1}
input[type=search]{font:inherit;font-size:12px;padding:.3rem .55rem;border-radius:999px;
  border:1px solid var(--border);background:var(--surface-0);color:var(--text-primary);width:190px}
input[type=search]:focus{outline:none;border-color:var(--border-strong)}
button{background:var(--surface-0);color:var(--text-secondary);border:1px solid var(--border);
  border-radius:999px;padding:.3rem .7rem;font-size:12px;cursor:pointer;font-family:inherit}
button:hover{border-color:var(--border-strong)}
main{flex:1;display:flex;min-height:0;min-width:0;position:relative}
#stage{flex:1;position:relative;min-width:0;min-height:0;overflow:hidden}
svg{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;
  touch-action:none;background:var(--surface-0)}
svg.drag{cursor:grabbing}
/* --- the water --- */
.sandband{fill:var(--sand)}
.bankline{stroke:var(--bank);stroke-width:2;fill:none}
.band{fill:none;stroke:var(--water);stroke-linecap:round;stroke-linejoin:round;opacity:.34}
.band.side{stroke:var(--water-side);opacity:.30}
.core{fill:none;stroke:var(--water-core);stroke-linecap:round;stroke-linejoin:round;opacity:.75}
.flow{fill:none;stroke:var(--sheen);stroke-linecap:round;opacity:.30;
  stroke-dasharray:16 190;animation:drift 11s linear infinite}
@keyframes drift{to{stroke-dashoffset:-206}}
@media (prefers-reduced-motion: reduce){.flow{animation:none;opacity:.14}}
.goalbank{fill:var(--goal);opacity:.14;stroke:var(--goal);stroke-opacity:.5;stroke-width:1.5}
.goaltext{fill:var(--goal);font-size:26px;font-weight:600;letter-spacing:.22em}
.goalsub{fill:var(--text-muted);font-size:12px}
/* --- stones and rocks --- */
.stone{fill:var(--stone);stroke:var(--stone-edge);stroke-width:1.1}
.rockglyph{fill:var(--rock);stroke:var(--rock);stroke-width:1.2;fill-opacity:.85}
.node{cursor:pointer}
/* the halo doubles as the hit area — fill:transparent, so a stone stays easy to
   hover when the whole river is zoomed out to a hairline */
.node .halo{fill:transparent;stroke:var(--text-primary);stroke-width:2;opacity:0}
.node:hover .halo{opacity:.85}
.node:hover .halo,.node.pin .halo{opacity:.85}
.node.st-superseded .stone{fill-opacity:.28;stroke-dasharray:3 2.5}
.node.st-superseded .nlabel{opacity:.5;text-decoration:line-through}
.node.st-refuted .halo{stroke:var(--rock)}
.node.dim{opacity:.16}
.dot{fill:var(--surface-1);opacity:.75}
.ring{fill:none;stroke:var(--stone-edge);stroke-width:1.2;opacity:.9}
.forkmark{fill:none;stroke:var(--water-side);stroke-width:2;stroke-linecap:round}
.nlabel{fill:var(--text-secondary);font-size:11.5px;text-anchor:middle}
svg.far .nlabel,svg.far .flaglabel,svg.far .deadlabel,svg.far .arclabel,
svg.far .restlabel{display:none}
.wake{fill:none;stroke:var(--sheen);stroke-width:1.4;opacity:.5}
/* --- arcs --- */
.arc{fill:none;stroke-width:2;opacity:.85}
.arc.back{stroke:var(--back);stroke-dasharray:7 4}
.arc.supersede{stroke:var(--text-muted);stroke-dasharray:2 4}
.arc.refute{stroke:var(--rock);stroke-dasharray:2 4}
/* rests-on-refuted: the same red as a rock, but a LONG dash and a forward arrow
   — the eye must not confuse "this was refuted" with "this stands on refuted". */
.arc.rests{stroke:var(--rock);stroke-dasharray:10 5;stroke-width:2.4;opacity:.92}
.arc.link{stroke:var(--link);stroke-width:1.2;opacity:.55;stroke-dasharray:1 5}
.ah-back{fill:var(--back)}.ah-sup{fill:var(--text-muted)}.ah-ref{fill:var(--rock)}
.arclabel{fill:var(--back);font-size:11px;text-anchor:middle}
.restlabel{fill:var(--rock);font-size:11px;text-anchor:middle}
.restmark{fill:none;stroke:var(--rock);stroke-width:1.3;stroke-dasharray:3 3;opacity:.9}
.deadmark{stroke:var(--dead);stroke-width:2.2;fill:none;stroke-linecap:round}
.deadlabel{fill:var(--dead);font-size:11px}
/* --- banks --- */
.pole{stroke:var(--bank);stroke-width:1.6}
.pennant.ship{fill:var(--flag-ship)}.pennant.gate{fill:var(--flag-gate)}
.pennant.correction{fill:var(--flag-corr)}
.flaglabel{font-size:11.5px;fill:var(--text-secondary)}
.flag{cursor:pointer}.flag:hover .flaglabel{fill:var(--text-primary)}
.lanetick{fill:var(--lane);opacity:.75;cursor:pointer}
.lanetick:hover{opacity:1}
/* COMMISSION — a lane whose exact prompt is banked on disk. Deliberately the
   loudest thing on the bottom bank: a commission nobody can see is the failure
   this glyph exists to make impossible. */
.lanetick.commission{opacity:.95}
.commsheet{fill:var(--surface-1);stroke:var(--commission);stroke-width:1.5}
.commrule{stroke:var(--commission);stroke-width:1.3;stroke-linecap:round;opacity:.85}
.commstem{stroke:var(--commission);stroke-width:1.1;opacity:.55}
.lanetick.commission:hover .commsheet{fill:var(--commission);fill-opacity:.22}
.commcount{fill:var(--commission);font-size:11px;letter-spacing:.06em}
svg.far .commcount{display:none}
.banklabel{fill:var(--text-muted);font-size:11px;letter-spacing:.08em}
/* --- chrome --- */
#legend{position:absolute;left:.7rem;bottom:.7rem;background:var(--surface-1);
  border:1px solid var(--border);border-radius:10px;padding:.5rem .65rem;font-size:11.5px;
  color:var(--text-secondary);max-width:min(680px,92%);max-height:42%;overflow:auto}
#legend>summary{cursor:pointer;list-style:none;color:var(--text-muted);font-size:11px;
  letter-spacing:.06em;margin:-.15rem 0 0}
#legend>summary::-webkit-details-marker{display:none}
#legend:not([open]){padding:.3rem .6rem}
#legend:not([open])>summary{margin:0}
#legend .row{display:flex;flex-wrap:wrap;gap:.25rem .8rem;align-items:center}
#legend .row+.row{margin-top:.35rem;padding-top:.35rem;border-top:1px solid var(--border)}
#legend span.it{display:inline-flex;align-items:center;gap:.32rem}
#legend .n{color:var(--text-muted)}
#legend .note{color:var(--text-muted);line-height:1.45}
.sw{width:16px;height:9px;border-radius:3px;flex:none;display:inline-block}
#card{position:absolute;display:none;max-width:min(430px,72vw);max-height:56vh;overflow:auto;
  background:var(--surface-1);
  border:1px solid var(--border-strong);border-radius:10px;padding:.55rem .7rem;font-size:12.5px;
  box-shadow:0 6px 24px rgba(0,0,0,.18);pointer-events:none;z-index:6;line-height:1.45}
#card.pinned{pointer-events:auto}
#card .k{display:inline-block;font-size:10.5px;padding:.05rem .4rem;border-radius:999px;
  border:1px solid var(--border);color:var(--text-secondary);margin-right:.25rem}
#card .ask{font-weight:600;margin:.35rem 0 .15rem}
#card .st{color:var(--text-secondary)}
#card .lbl{font-size:10.5px;letter-spacing:.04em;color:var(--text-muted);margin:.5rem 0 .2rem}
#card code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;
  word-break:break-all;color:var(--text-secondary)}
#card .evrow{display:flex;gap:.35rem;align-items:baseline;padding:.1rem 0}
.ev{font-size:10px;padding:.03rem .35rem;border-radius:999px;flex:none;
  border:1px solid var(--border-strong);color:var(--text-secondary)}
.ev-cited{background:color-mix(in srgb,var(--goal) 22%,transparent);border-color:var(--goal)}
.ev-estimate{background:color-mix(in srgb,var(--back) 22%,transparent);border-color:var(--back)}
.ev-recall{background:color-mix(in srgb,var(--flag-ship) 20%,transparent);border-color:var(--flag-ship)}
.ev-unverified{background:color-mix(in srgb,var(--rock) 18%,transparent);border-color:var(--rock)}
.ev-model-opinion{background:color-mix(in srgb,var(--rock) 18%,transparent);border-color:var(--rock)}
#card .foot{color:var(--text-muted);font-size:10.5px;margin-top:.45rem}
#card .rests{color:var(--rock);font-weight:600;font-size:11.5px;letter-spacing:.03em;
  margin:.4rem 0 .1rem}
#card .brief{border-left:2px solid var(--commission);padding:.1rem 0 .1rem .5rem;
  color:var(--text-primary);white-space:pre-wrap;font-size:12px}
#card .nocomm{color:var(--text-muted);font-size:12px}
.sw.dash{background:none!important;height:0;border-radius:0;border-top:3px dashed var(--rock)}
.sw.sheet{background:var(--surface-0);border:1.4px solid var(--commission);border-radius:2px;
  width:10px;height:13px}
#empty{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  color:var(--text-muted);font-size:13px;text-align:center;padding:2rem}
</style>
</head>
<body>
<header>
  <div>
    <h1>river — <span class="mono">__TITLE__</span></h1>
    <div class="sub mono path" title="__ROOT__">__ROOT__</div>
  </div>
  <div class="sub">__COUNTS__ · __MODE__ · __GENERATED__ <span title="stamp source">(__STAMPFROM__)</span></div>
  <span class="grow"></span>
  <input id="q" type="search" placeholder="filter records…" autocomplete="off">
  <span id="qn" class="sub"></span>
  <button id="fit" type="button">fit</button>
  <button id="zin" type="button">+</button>
  <button id="zout" type="button">−</button>
  <button id="theme" type="button">light / dark</button>
</header>
<main><div id="stage">
  <svg id="sv" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="ah-back" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="7" markerHeight="6"
              orient="auto-start-reverse"><path class="ah-back" d="M0,0 L10,4 L0,8 z"/></marker>
      <marker id="ah-sup" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="6" markerHeight="5"
              orient="auto-start-reverse"><path class="ah-sup" d="M0,0 L10,4 L0,8 z"/></marker>
      <marker id="ah-ref" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="6" markerHeight="5"
              orient="auto-start-reverse"><path class="ah-ref" d="M0,0 L10,4 L0,8 z"/></marker>
    </defs>
    <g id="scene"></g>
  </svg>
  <div id="card"></div>
  <details id="legend" open><summary>LEGEND — click to fold</summary></details>
  <div id="empty" hidden></div>
</div></main>
<script>
(function(){
var D = "__RIVER_DATA__";
var NS = 'http://www.w3.org/2000/svg';
var root = document.documentElement;
var svg = document.getElementById('sv'), scene = document.getElementById('scene');
var stage = document.getElementById('stage'), card = document.getElementById('card');
var nodes = D.nodes || [], byId = {}, i;
for (i = 0; i < nodes.length; i++) byId[nodes[i].id] = nodes[i];
var groups = [], pinned = null, view = {x:0, y:0, k:1}, userMoved = false;
var LABELS = nodes.length <= 60;

function el(tag, attrs, cls){
  var e = document.createElementNS(NS, tag);
  if (cls) e.setAttribute('class', cls);
  for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) e.setAttribute(k, attrs[k]);
  return e;
}
function esc(s){
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function clip(s, n){ s = String(s || ''); return s.length <= n ? s : s.slice(0, n - 1) + '…'; }
function num(v){ return Math.round(v * 100) / 100; }

/* Catmull-Rom → cubic bezier: a river bends, it does not zigzag. */
function smooth(pts){
  if (!pts.length) return '';
  if (pts.length === 1) return 'M' + pts[0][0] + ',' + pts[0][1];
  var d = 'M' + pts[0][0] + ',' + pts[0][1], j;
  for (j = 0; j < pts.length - 1; j++){
    var p0 = pts[j - 1] || pts[j], p1 = pts[j], p2 = pts[j + 1], p3 = pts[j + 2] || p2;
    d += 'C' + num(p1[0] + (p2[0] - p0[0]) / 6) + ',' + num(p1[1] + (p2[1] - p0[1]) / 6) +
         ' ' + num(p2[0] - (p3[0] - p1[0]) / 6) + ',' + num(p2[1] - (p3[1] - p1[1]) / 6) +
         ' ' + p2[0] + ',' + p2[1];
  }
  return d;
}
/* deterministic stone shape: the id hashes to the same pebble every render */
function hash(s){
  var h = 2166136261, j;
  for (j = 0; j < s.length; j++){ h ^= s.charCodeAt(j); h = (h * 16777619) >>> 0; }
  return h;
}
function pebble(cx, cy, r, seed, sides, jag){
  var h = seed || 1, pts = [], j;
  for (j = 0; j < sides; j++){
    h = (h * 1103515245 + 12345) >>> 0;
    var f = 1 - jag + ((h >>> 9) % 100) / 100 * (jag * 2);
    var a = j / sides * Math.PI * 2 + ((h >>> 17) % 100) / 100 * 0.22;
    pts.push(num(cx + Math.cos(a) * r * f) + ',' + num(cy + Math.sin(a) * r * f * 0.84));
  }
  return pts.join(' ');
}
function loopPath(x1, y1, x0, y0){
  var lift = 74 + Math.min(150, Math.abs(x1 - x0) * 0.15);
  var top = Math.min(y0, y1) - lift;
  return 'M' + x1 + ',' + y1 + ' C' + num(x1 - (x1 - x0) * 0.28) + ',' + num(top) +
         ' ' + num(x0 + (x1 - x0) * 0.28) + ',' + num(top) + ' ' + x0 + ',' + y0;
}
function underPath(x1, y1, x0, y0){
  var drop = 54 + Math.min(120, Math.abs(x1 - x0) * 0.10);
  var bot = Math.max(y0, y1) + drop;
  return 'M' + x1 + ',' + y1 + ' C' + num(x1 - (x1 - x0) * 0.3) + ',' + num(bot) +
         ' ' + num(x0 + (x1 - x0) * 0.3) + ',' + num(bot) + ' ' + x0 + ',' + y0;
}

/* ---------------------------------------------------------------- the scene */
var BI = D.bankInset || {top:66, bottom:66};
var E = D.extent, TOPY = E.y0 + BI.top, BOTY = E.y1 - BI.bottom;
var gBank = el('g'), gWater = el('g'), gArc = el('g'), gNode = el('g'),
    gFlag = el('g'), gLane = el('g');
[gBank, gWater, gArc, gNode, gFlag, gLane].forEach(function(g){ scene.appendChild(g); });

/* banks: sand above and below, a hairline at each waterline */
gBank.appendChild(el('rect', {x:E.x0, y:E.y0, width:E.x1 - E.x0, height:TOPY - E.y0}, 'sandband'));
gBank.appendChild(el('rect', {x:E.x0, y:BOTY, width:E.x1 - E.x0, height:E.y1 - BOTY}, 'sandband'));
gBank.appendChild(el('path', {d:'M' + (E.x0 + 30) + ',' + TOPY + ' H' + (E.x1 - 30)}, 'bankline'));
gBank.appendChild(el('path', {d:'M' + (E.x0 + 30) + ',' + BOTY + ' H' + (E.x1 - 30)}, 'bankline'));
function bankLabel(x, y, t){
  var e = el('text', {x:x, y:y}, 'banklabel'); e.textContent = t; gBank.appendChild(e);
}
bankLabel(E.x0 + 34, TOPY - 16, 'COORD MILESTONES — ships · gates · corrections');
bankLabel(E.x0 + 34, BOTY + 24, 'LANES — COORD-AGENTS.md activity');
bankLabel(E.x0 + 34, (TOPY + BOTY) / 2, 'upstream — where we started');

/* the goal bank on the right edge: the river empties into it */
var gx = D.goal.x;
gBank.appendChild(el('rect', {x:gx, y:TOPY - 10, width:64, height:BOTY - TOPY + 20, rx:14}, 'goalbank'));
var gt = el('text', {x:gx + 40, y:(TOPY + BOTY) / 2,
  transform:'rotate(-90 ' + (gx + 40) + ' ' + ((TOPY + BOTY) / 2) + ')', 'text-anchor':'middle'}, 'goaltext');
gt.textContent = D.goal.label; gBank.appendChild(gt);

/* channels: a wide band, a bright core, a drifting sheen */
(D.channels || []).forEach(function(c){
  if (!c.points || c.points.length < 2) return;
  var main = c.kind === 'main', d = smooth(c.points);
  gWater.appendChild(el('path', {d:d, 'stroke-width':main ? 46 : 19}, 'band' + (main ? '' : ' side')));
  gWater.appendChild(el('path', {d:d, 'stroke-width':main ? 15 : 6}, 'core'));
  gWater.appendChild(el('path', {d:d, 'stroke-width':main ? 5 : 2.5}, 'flow'));
  if (c.outcome === 'dead-end'){
    var p = c.points[c.points.length - 1];
    gWater.appendChild(el('path', {d:'M' + (p[0] - 9) + ',' + (p[1] - 9) + ' l18,18 M' +
      (p[0] + 9) + ',' + (p[1] - 9) + ' l-18,18'}, 'deadmark'));
    var t = el('text', {x:p[0] + 16, y:p[1] + 5}, 'deadlabel');
    t.textContent = 'dead end — never rejoined'; gWater.appendChild(t);
  }
});

/* arcs the bands cannot carry: backtracks upstream, supersede/refute, stray links */
(D.edges || []).forEach(function(e){
  if (e.kind === 'flow' || e.kind === 'branch' || e.kind === 'merge') return;
  var a = byId[e.from], b = byId[e.to];
  if (!a || !b) return;
  var back = e.kind === 'back';
  var d = back ? loopPath(a.x, a.y, b.x, b.y) : underPath(a.x, a.y, b.x, b.y);
  var mk = back ? 'ah-back' : ((e.kind === 'refute' || e.kind === 'rests') ? 'ah-ref' : 'ah-sup');
  var at = {d:d};
  if (e.kind !== 'link') at['marker-end'] = 'url(#' + mk + ')';
  gArc.appendChild(el('path', at, 'arc ' + e.kind));
  if (back){
    var t = el('text', {x:num((a.x + b.x) / 2), y:num(Math.min(a.y, b.y) - 74 - Math.min(150, Math.abs(a.x - b.x) * 0.15) + 26)}, 'arclabel');
    t.textContent = 'backtrack'; gArc.appendChild(t);
  }
  if (e.kind === 'rests'){
    var rl = el('text', {x:num((a.x + b.x) / 2),
      y:num(Math.max(a.y, b.y) + 46 + Math.min(120, Math.abs(a.x - b.x) * 0.10))}, 'restlabel');
    rl.textContent = 'rests on refuted'; gArc.appendChild(rl);
  }
});

/* stones turned — one glyph per record, rocks where the flow hit something */
nodes.forEach(function(n, idx){
  var rests = !!(n.rests_on && n.rests_on.length);
  var g = el('g', {'data-i':idx}, 'node st-' + n.effective + (n.rock ? ' rock' : '') +
                                  (rests ? ' rests' : ''));
  var main = n.channel === 0, r = (main ? 12 : 9.5) + (n.kind === 'decision' ? 2 : 0);
  var seed = hash(n.id);
  if (rests) g.appendChild(el('circle', {cx:n.x, cy:n.y, r:r + 3.6}, 'restmark'));
  if (n.rock){
    g.appendChild(el('polygon', {points:pebble(n.x, n.y, r + 2.5, seed, 7, 0.34)}, 'rockglyph'));
    g.appendChild(el('path', {d:'M' + (n.x - r - 10) + ',' + (n.y + r) + ' q' + (r + 10) +
      ',' + (-r * 1.5) + ' ' + (2 * r + 20) + ',0'}, 'wake'));
  } else {
    g.appendChild(el('polygon', {points:pebble(n.x, n.y, r, seed, 6, 0.16)}, 'stone'));
  }
  if (n.kind === 'result') g.appendChild(el('circle', {cx:n.x, cy:n.y, r:3.2}, 'dot'));
  if (n.kind === 'decision') g.appendChild(el('circle', {cx:n.x, cy:n.y, r:r + 5}, 'ring'));
  if (n.kind === 'side-route')
    g.appendChild(el('path', {d:'M' + (n.x - 9) + ',' + (n.y - r - 9) + ' l9,7 l9,-7'}, 'forkmark'));
  g.appendChild(el('circle', {cx:n.x, cy:n.y, r:r + 6}, 'halo'));
  if (LABELS || n.rock){
    var t = el('text', {x:n.x, y:n.y + (main ? -r - 12 : r + 18)}, 'nlabel');
    t.textContent = clip(n.ask || n.statement || n.id, 26);
    g.appendChild(t);
  }
  gNode.appendChild(g); groups.push(g);
});

/* milestone flags along the top bank */
(D.milestones || []).forEach(function(m, idx){
  var g = el('g', {'data-m':idx}, 'flag'), y = TOPY - 30 - (idx % 3) * 30;
  g.appendChild(el('path', {d:'M' + m.x + ',' + y + ' V' + (TOPY - 2)}, 'pole'));
  g.appendChild(el('path', {d:'M' + m.x + ',' + y + ' l26,7 l-26,7 z'}, 'pennant ' + m.flag));
  var t = el('text', {x:m.x + 31, y:y + 11}, 'flaglabel');
  t.textContent = clip(m.label, 24); g.appendChild(t);
  gFlag.appendChild(g);
});

/* lane ticks along the bottom bank. A lane whose COMMISSION is banked gets a
   sheet glyph on its own row BELOW the plain ticks — the point of the row is
   that you can see, without hovering anything, how much of this river's work
   was commissioned in the open. */
var COMMY = BOTY + 96;                 /* the commission row's own centreline */
var comm = 0;
(D.lanes || []).forEach(function(l, idx){
  var g = el('g', {'data-l':idx}, 'lanetick' + (l.commission ? ' commission' : ''));
  if (l.commission){
    var y = COMMY + (comm % 2) * 22;
    comm++;
    g.appendChild(el('path', {d:'M' + l.x + ',' + (BOTY + 12) + ' V' + (y - 8)}, 'commstem'));
    g.appendChild(el('rect', {x:l.x - 6, y:y - 8, width:12, height:16, rx:1.8}, 'commsheet'));
    g.appendChild(el('path', {d:'M' + (l.x - 3.2) + ',' + (y - 3.5) + ' H' + (l.x + 3.2) +
      ' M' + (l.x - 3.2) + ',' + y + ' H' + (l.x + 3.2) +
      ' M' + (l.x - 3.2) + ',' + (y + 3.5) + ' H' + (l.x + 1.2)}, 'commrule'));
  } else {
    var yp = BOTY + 14 + (idx % 3) * 8;
    g.appendChild(el('path', {d:'M' + (l.x - 5) + ',' + (yp + 5) + ' l5,-6 l5,6 z'}));
  }
  gLane.appendChild(g);
});
/* the banner sits on its OWN line above the glyph row — a caption that overlaps
   the thing it captions is not a caption */
if (comm){
  var ct = el('text', {x:E.x0 + 34, y:BOTY + 68}, 'commcount');
  ct.textContent = 'COMMISSIONS — ' + comm + ' lane' + (comm === 1 ? '' : 's') +
                   ' whose exact prompt is banked on disk';
  gLane.appendChild(ct);
}

/* ------------------------------------------------------------------- cards */
function evRows(ev){
  if (!ev || !ev.length) return '<div class="evrow"><span class="ev">none</span>' +
    '<span class="st">no evidence refs on this record</span></div>';
  return ev.map(function(e){
    return '<div class="evrow"><span class="ev ev-' + esc(e.label || 'unverified') + '">' +
      esc(e.label || 'unverified') + '</span><span><code>' + esc(e.ref) + '</code>' +
      (e.type ? ' <span class="st">' + esc(e.type) + '</span>' : '') + '</span></div>';
  }).join('');
}
function nodeCard(n){
  var sup = n.superseded_by && n.superseded_by.length
    ? '<div class="foot">' + esc(n.effective) + ' by ' + esc(n.superseded_by.join(', ')) + '</div>' : '';
  /* the standing-on-refuted-ground warning: this record is live, but something it
     cites has been refuted. One hop only — the river says what the links say. */
  var rest = (n.rests_on && n.rests_on.length)
    ? '<div class="rests">RESTS-ON-REFUTED ' + esc(n.rests_on.join(', ')) + '</div>' : '';
  return '<div><span class="k">' + esc(n.kind) + '</span><span class="k">' + esc(n.relation) +
    '</span><span class="k">' + esc(n.effective) + '</span>' +
    (n.inferred ? '<span class="k">inferred</span>' : '') + '</div>' +
    '<div class="ask">' + esc(clip(n.ask, 300) || '(no ask recorded)') + '</div>' +
    (n.statement ? '<div class="st">' + esc(clip(n.statement, 420)) + '</div>' : '') + rest +
    '<div class="lbl">EVIDENCE</div>' + evRows(n.evidence) + sup +
    '<div class="foot">' + esc(n.ts) + ' · ' + esc(n.session || '—') + ' · ' +
    esc(n.skill || '—') + ' · channel ' + n.channel + ' · <code>' + esc(n.ref) + '</code>' +
    (n.links && n.links.length ? ' · links: ' + esc(n.links.join(', ')) : '') + '</div>';
}
function flagCard(m){
  return '<div><span class="k">COORD ' + esc(m.flag) + '</span><span class="k">' +
    esc(m.lane || '—') + '</span></div>' +
    '<div class="ask">' + esc(m.ask || '(no ask)') + '</div>' +
    (m.landed ? '<div class="st">→ ' + esc(m.landed) + '</div>' : '') +
    (m.evidence ? '<div class="lbl">EVIDENCE (the ledger\'s own claim)</div><div class="st"><code>' +
      esc(m.evidence) + '</code></div>' : '') +
    '<div class="foot">' + esc(m.ts) + ' · <code>' + esc(m.ref) + '</code></div>';
}
function laneCard(l){
  /* THE COMMISSION. Banked → the head of the prompt itself plus the path to the
     whole of it. Not banked → said plainly, never dressed up: a pointer with no
     file behind it is a worse lie than an admitted gap. */
  var c;
  if (l.commission){
    c = '<div class="lbl">COMMISSION — the exact prompt this lane was given</div>' +
        '<div class="brief">' + esc(l.brief_head || '(the brief file is empty)') + '</div>' +
        '<div class="foot">full text: <code>' + esc(l.brief) + '</code></div>';
  } else {
    c = '<div class="lbl">COMMISSION</div><div class="nocomm">not banked' +
        (l.brief ? ' — the receipt points at <code>' + esc(l.brief) +
                   '</code> but that file is not readable from here'
                 : ' (pre-v3.13 lane: its receipt carries no brief pointer)') + '</div>';
  }
  return '<div><span class="k">lane</span><span class="k">' + esc(l.model) + '</span>' +
    (l.commission ? '<span class="k">commissioned</span>' : '') + '</div>' +
    '<div class="ask">' + esc(l.agent) + '</div>' +
    '<div class="st">' + esc(l.last || '(no last line recorded)') + '</div>' + c +
    '<div class="foot">' + esc(l.ts) + ' · <code>' + esc(l.ref) + '</code></div>';
}
function showCard(html, ev){
  card.innerHTML = html + (pinned ? '<div class="foot">pinned — click the background to release</div>' : '');
  card.style.display = 'block';
  var r = stage.getBoundingClientRect(), w = card.offsetWidth, h = card.offsetHeight;
  var x = ev.clientX - r.left + 16, y = ev.clientY - r.top + 16;
  if (x + w > r.width - 8) x = Math.max(8, ev.clientX - r.left - w - 16);
  if (y + h > r.height - 8) y = Math.max(8, r.height - h - 8);
  card.style.left = x + 'px'; card.style.top = y + 'px';
}
function hideCard(){ if (!pinned) card.style.display = 'none'; }
function bodyFor(g){
  if (g.hasAttribute('data-i')) return nodeCard(nodes[+g.getAttribute('data-i')]);
  if (g.hasAttribute('data-m')) return flagCard(D.milestones[+g.getAttribute('data-m')]);
  return laneCard(D.lanes[+g.getAttribute('data-l')]);
}
function hitTarget(t){
  while (t && t !== scene){
    if (t.hasAttribute && (t.hasAttribute('data-i') || t.hasAttribute('data-m') ||
        t.hasAttribute('data-l'))) return t;
    t = t.parentNode;
  }
  return null;
}
svg.addEventListener('mousemove', function(ev){
  if (drag.on) return;
  var g = hitTarget(ev.target);
  if (g && !pinned){ showCard(bodyFor(g), ev); } else if (!pinned) hideCard();
});
svg.addEventListener('mouseleave', hideCard);
function unpin(){
  if (pinned) pinned.classList.remove('pin');
  pinned = null; card.classList.remove('pinned'); card.style.display = 'none';
}
svg.addEventListener('click', function(ev){
  if (drag.moved) return;
  var g = hitTarget(ev.target);
  if (!g){ unpin(); return; }
  if (pinned === g){ unpin(); return; }
  unpin(); pinned = g; g.classList.add('pin'); card.classList.add('pinned');
  showCard(bodyFor(g), ev);
});
document.addEventListener('keydown', function(ev){ if (ev.key === 'Escape') unpin(); });

/* ------------------------------------------------------- pan · zoom · fit */
function apply(){
  scene.setAttribute('transform', 'translate(' + num(view.x) + ',' + num(view.y) +
                     ') scale(' + (Math.round(view.k * 1e4) / 1e4) + ')');
  svg.classList.toggle('far', view.k < 0.34);      /* labels would be noise here */
}
/* A river is long. Fitting its whole length into the pane makes every stone a
   hairline, so `fit` fits the HEIGHT (channels, banks, both shores legible) and
   anchors upstream — you read it by panning downstream. Zoom out for the whole
   course when you want the shape rather than the records. */
function fit(){
  var r = stage.getBoundingClientRect();
  var w = Math.max(1, E.x1 - E.x0), h = Math.max(1, E.y1 - E.y0);
  view.k = Math.max(0.02, Math.min(1.15, r.height / h));
  view.x = (w * view.k <= r.width) ? (r.width - w * view.k) / 2 - E.x0 * view.k
                                   : 24 - E.x0 * view.k;
  view.y = (r.height - h * view.k) / 2 - E.y0 * view.k;
  userMoved = false; apply();
}
function zoomAt(cx, cy, f){
  var k = Math.max(0.02, Math.min(6, view.k * f));
  view.x = cx - (cx - view.x) * (k / view.k);
  view.y = cy - (cy - view.y) * (k / view.k);
  view.k = k; userMoved = true; apply();
}
var drag = {on:false, moved:false, x:0, y:0};
svg.addEventListener('mousedown', function(ev){
  drag.on = true; drag.moved = false; drag.x = ev.clientX; drag.y = ev.clientY;
  svg.classList.add('drag');
});
window.addEventListener('mousemove', function(ev){
  if (!drag.on) return;
  var dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
  view.x += dx; view.y += dy; drag.x = ev.clientX; drag.y = ev.clientY;
  userMoved = true; apply();
});
window.addEventListener('mouseup', function(){
  drag.on = false; svg.classList.remove('drag');
  setTimeout(function(){ drag.moved = false; }, 0);
});
svg.addEventListener('wheel', function(ev){
  ev.preventDefault();
  var r = stage.getBoundingClientRect();
  zoomAt(ev.clientX - r.left, ev.clientY - r.top, ev.deltaY < 0 ? 1.12 : 1 / 1.12);
}, {passive:false});
document.getElementById('fit').addEventListener('click', fit);
document.getElementById('zin').addEventListener('click', function(){
  var r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.25);
});
document.getElementById('zout').addEventListener('click', function(){
  var r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.25);
});
document.getElementById('theme').addEventListener('click', function(){
  var cur = root.getAttribute('data-theme') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  root.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark');
});
window.addEventListener('resize', function(){ if (!userMoved) fit(); });
/* the script runs before layout settles, so the first fit() can read a stage
   that is not its final size — re-fit on the next frame and on every resize of
   the stage itself (a wrapped header changes it without a window resize) */
if (window.ResizeObserver) new ResizeObserver(function(){ if (!userMoved) fit(); }).observe(stage);
window.requestAnimationFrame(function(){ if (!userMoved) fit(); });

/* ------------------------------------------------------------ filter · legend */
var q = document.getElementById('q'), qn = document.getElementById('qn');
q.addEventListener('input', function(){
  var s = q.value.trim().toLowerCase(), shown = 0;
  nodes.forEach(function(n, idx){
    var hay = (n.ask + ' ' + n.statement + ' ' + n.id + ' ' + n.kind + ' ' +
               n.skill + ' ' + n.session).toLowerCase();
    var on = !s || hay.indexOf(s) >= 0;
    groups[idx].classList.toggle('dim', !on);
    if (on) shown++;
  });
  qn.textContent = s ? shown + '/' + nodes.length : '';
});
(function legend(){
  var c = D.counts, L = document.getElementById('legend');
  function sw(v){ return '<i class="sw" style="background:' + v + '"></i>'; }
  var glyphs = [
    sw('var(--water)') + 'main channel — toward the goal <span class="n">' + c.toward + '</span>',
    sw('var(--water-side)') + 'side channel <span class="n">' + c.lateral + '</span>',
    sw('var(--back)') + 'backtrack loop <span class="n">' + c.back + '</span>',
    sw('var(--rock)') + 'rock — conflict / refuted <span class="n">' + c.rocks + '</span>',
    '<i class="sw dash"></i>rests on refuted — a live record citing refuted ground ' +
      '<span class="n">' + c.rests_on_refuted + '</span>',
    sw('var(--stone)') + 'stone turned <span class="n">' + c.records + '</span>',
    sw('var(--flag-ship)') + 'COORD flag <span class="n">' + c.milestones + '</span>',
    "<i class=\"sw sheet\"></i>commission — every marked lane's exact prompt is on disk; " +
      'click the tick for the path <span class="n">' + c.commissions + '</span>',
    sw('var(--goal)') + 'goal bank'
  ];
  var tallies = [
    'channels <span class="n">' + c.channels + '</span>',
    'merged back <span class="n">' + c.merged + '</span>',
    'dead ends <span class="n">' + c.dead_end + '</span>',
    'forks <span class="n">' + c.side_route + '</span>',
    'superseded <span class="n">' + c.superseded + '</span>',
    'refuted <span class="n">' + c.refuted + '</span>',
    'ships/gates/corrections <span class="n">' + c.ships + '/' + c.gates + '/' + c.corrections + '</span>',
    'lanes <span class="n">' + c.lanes + '</span>',
    'commissioned <span class="n">' + c.commissions + '/' + c.lanes + '</span>'
  ];
  var notes = (D.notes || []).slice();
  notes.push(D.mode === 'coord-only'
    ? 'COORD-only river: findings.jsonl was absent, so every node is a ledger line and its kind/relation is INFERRED from the line\'s words — side channels rejoin at the next forward line by chronology, not because the ledger says so.'
    : 'nodes come from ' + esc(D.sources.findings) + '; COORD flags and lane ticks are overlaid from the ledger volumes.');
  notes.push('stamped ' + esc(D.generated) + ' from the ' + esc(D.stamp_from) +
             ' — identical inputs render an identical page.');
  L.innerHTML = '<summary>LEGEND — click to fold</summary>' +
    '<div class="row">' + glyphs.map(function(g){ return '<span class="it">' + g + '</span>'; }).join('') + '</div>' +
    '<div class="row">' + tallies.map(function(t){ return '<span class="it">' + t + '</span>'; }).join('') + '</div>' +
    '<div class="row"><span class="note">' + notes.map(esc).join('<br>') + '</span></div>';
})();

if (!nodes.length){
  var em = document.getElementById('empty');
  em.hidden = false;
  em.textContent = 'No records to draw — no archive/findings.jsonl and no COORD ledger ' +
    'lines under this root. Run a session, or point --root at the repo that has them.';
}
fit();
})();
</script>
</body>
</html>
"""


def cmd_river(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        die(f"not a directory: {root}")
    out = pathlib.Path(a.out).expanduser()
    out = out if out.is_absolute() else (root / a.out)
    if out.suffix.lower() in (".html", ".htm"):
        html_p, json_p = out, out.with_suffix(".json")
    else:
        html_p, json_p = out / "river.html", out / "river.json"
    r = build_river(root, session=a.session, cap=a.cap, use_now=a.now)
    html_p.parent.mkdir(parents=True, exist_ok=True)
    json_p.write_text(json.dumps(r, indent=1), encoding="utf-8")
    html_p.write_text(render_river_html(r, title=root.name), encoding="utf-8")
    c = r["counts"]
    print(f"{html_p}: {c['records']} records · {c['channels']} channels "
          f"({c['merged']} merged, {c['dead_end']} dead-end) · {c['rocks']} rocks "
          f"({c['rests_on_refuted']} resting on refuted) · "
          f"{c['back']} backtracks · {c['milestones']} milestones · "
          f"{c['commissions']}/{c['lanes']} lanes commissioned · mode={r['mode']}")
    for n in r["notes"]:
        print(f"  note: {n}")
    print(f"  data: {json_p}")
    if a.open:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.run([opener, str(html_p)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  opened with {opener}")
        except OSError:
            print(f"  could not run {opener} — open {html_p} in any browser")
    return 0


# =========================================================== journey: the doors
#
# The router is this harness's front door and nothing has ever drawn it. `journey`
# reads the THREE places a route is actually written down — hooks/router.sh (the
# SKILL=/SHAPE= case chain, the same parse eval.py's ROUTER check uses),
# skills/oracle/SKILL.md's intake routing bullet, and each skill's own
# chains/finishing-up section — and renders the whole door as one page: what a
# user types → the shape the router calls it → the verb that runs → what that
# verb hands off to. Skills nothing routes to are drawn, not hidden: "by name
# only" is a fact about the door, and the most useful thing on the page.

JPX = 26.0             # pill column left edge
JPW = 278.0            # pill max width (JPILL_CHARS * JCHAR + padding)
JSX = 372.0            # shape column left edge
JSW = 184.0
JKX = 668.0            # skill column left edge
JKW = 206.0
JCHAR = 6.6            # px per char at the node font size — layout without measuring
JPILL_CHARS = 38       # phrase clip, so the width estimate can never underrun
JPILL_H = 22.0
JPILL_GAP = 5.0
JNODE_H = 34.0
JROW_GAP = 22.0
JY0 = 104.0
JBAND_GAP = 96.0       # gap before the "by name only" band
JBAND_COLS = 4
JBAND_W = 190.0
JBAND_H = 32.0
JBAND_GX = 16.0
JBAND_GY = 12.0
JBULGE = 176.0         # how far right the chain arcs swing

RE_RT_PAT = re.compile(r'\*"([^"]+)"\*')
RE_RT_SKILL = re.compile(r"\bSKILL=([a-z][a-z0-9-]*)")
RE_RT_SHAPE = re.compile(r"\bSHAPE=([a-z][a-z0-9-]*)")
RE_OR_ROUTE = re.compile(r"→\s*`/(?:notrest:)?([a-z][a-z0-9-]*)`")
RE_CH_HDR = re.compile(r"^#{2,6}[ \t]*(?:chains?|chaining|finishing[ \t]+up|hand[ \t-]?off)\b",
                       re.I)
RE_CH_HEAD = re.compile(r"^#{2,6}[ \t]")
RE_CH_BT = re.compile(r"`/(?:notrest:)?([a-z][a-z0-9-]+)`")
RE_CH_BARE = re.compile(r"(?<![\w/.])/(?:notrest:)?([a-z][a-z0-9-]+)(?![\w/.-])")


def find_plugin(root):
    """The plugin tree under a repo root: a directory holding skills/ beside
    hooks/router.sh. Falls back to any skills/ dir so a plugin without a router
    still draws (with a note), and returns None when there is no skill tree."""
    cands = [root / "plugins" / "notrest", root]
    pdir = root / "plugins"
    if pdir.is_dir():
        cands += sorted(p for p in pdir.iterdir() if p.is_dir())
    for want_router in (True, False):
        for c in cands:
            if not (c / "skills").is_dir():
                continue
            if want_router and not (c / "hooks" / "router.sh").is_file():
                continue
            return c
    return None


def parse_router(path):
    """The SKILL=/SHAPE= case arms in TABLE ORDER — order is precedence here
    (first match wins), so the drawing keeps the chain's own sequence rather than
    sorting it into a lie. Arms that emit no route (the slash-command guard, the
    already-named-the-verb guard) drop their patterns at the `;;`."""
    text = _slurp(path)
    if text is None:
        return [], "no hooks/router.sh — nothing draws the shape column"
    routes, pend = [], []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        pats = [p.strip() for p in RE_RT_PAT.findall(s)]
        sk, sh = RE_RT_SKILL.search(s), RE_RT_SHAPE.search(s)
        if sk and sh:
            phr = [p for p in pend + pats if p and "$" not in p]
            routes.append({"shape": sh.group(1), "skill": sk.group(1),
                           "phrases": list(dict.fromkeys(phr))})
            pend = []
            continue
        pend += pats
        if ";;" in s or s == "esac":
            pend = []
    return routes, None


def parse_oracle_routes(path):
    """oracle/SKILL.md's intake routing bullet: `<what the user wants> → /verb`.
    These are INTAKE routes, not router shapes — the hook never fires them, the
    intake conversation does, and the page draws them as their own kind."""
    text = _slurp(path)
    if text is None:
        return [], "no oracle/SKILL.md — no intake routes drawn"
    line = next((l for l in text.splitlines() if "Route to the right tool" in l), None)
    if line is None:
        return [], "oracle/SKILL.md carries no 'Route to the right tool' bullet"
    # The bullet is one long line of `phrase → /verb` pairs joined by `·`, opened
    # by prose. Split on the separator FIRST, then keep only the tail of each
    # segment after its last prose colon/dash — that is what strips the bullet's
    # lead-in off the first pair instead of pinning half a sentence to a skill.
    out = []
    for seg in line.split("·"):
        prev = 0
        for m in RE_OR_ROUTE.finditer(seg):
            phrase = seg[prev:m.start()]
            prev = m.end()
            phrase = phrase.split("—")[-1].split(":")[-1].split("**")[-1]
            phrase = phrase.replace('"', "").replace("“", "").replace("”", "")
            phrase = phrase.strip(" ·*`'()[]").strip()
            if phrase:
                out.append({"phrase": phrase, "skill": m.group(1)})
    return out, None


def chains_of(text, name, known):
    """A skill's own hand-off lines. BEST EFFORT, and the page says so: only an
    explicit `/verb` reference inside a Chains / Finishing-up section becomes an
    arrow. A section that names its siblings in prose ("researcher /
    marketresearcher → draft") parses to nothing and is DISCLOSED — a guessed
    arrow would be this script inventing a hand-off the skill never wrote."""
    sec, on = [], False
    for ln in text.splitlines():
        if RE_CH_HEAD.match(ln):
            on = bool(RE_CH_HDR.match(ln))
            if on:
                continue
        if on:
            sec.append(ln)
    body = "\n".join(sec)
    if not body.strip():
        return [], False
    hits = set(RE_CH_BT.findall(body)) | set(RE_CH_BARE.findall(body))
    return sorted(n for n in hits if n in known and n != name), True


def git_stamp(root):
    """REPRODUCIBILITY LAW, journey edition. river stamps from the newest input
    timestamp; that is wrong here because the inputs are tracked FILES whose
    mtimes are rewritten by every clone — two checkouts of the same commit would
    stamp differently. The commit is the honest identity of this input set."""
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
        if r.returncode == 0:
            h = r.stdout.decode("utf-8", "replace").strip()
            if h:
                # a commit hash over a modified tree names the wrong inputs, so say
                # so: `+dirty` is the difference between "this is commit X" and
                # "this is commit X plus whatever is uncommitted right now".
                d = subprocess.run(["git", "-C", str(root), "status", "--porcelain",
                                    "--untracked-files=no"],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   timeout=30)
                dirty = d.returncode == 0 and d.stdout.strip()
                return (h + "+dirty" if dirty else h), "git-head"
    except (OSError, subprocess.SubprocessError):
        pass
    return "(no git HEAD)", "none"


def _jclip(s, n=JPILL_CHARS):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def build_journey(root):
    notes = []
    plug = find_plugin(root)
    if plug is None:
        die(f"no plugin tree under {root} — journey needs a directory holding "
            f"skills/ (looked at plugins/notrest, plugins/*, and the root itself)")
    sk_dir = plug / "skills"
    known = sorted(p.name for p in sk_dir.iterdir()
                   if p.is_dir() and (p / "SKILL.md").is_file())
    kset = set(known)
    if not known:
        die(f"no skills with a SKILL.md under {sk_dir}")

    routes, rnote = parse_router(plug / "hooks" / "router.sh")
    if rnote:
        notes.append(rnote)
    intake, onote = parse_oracle_routes(sk_dir / "oracle" / "SKILL.md")
    if onote:
        notes.append(onote)

    chains, nosec, nochain = {}, [], []
    for name in known:
        tgt, had = chains_of(_slurp(sk_dir / name / "SKILL.md") or "", name, kset)
        chains[name] = tgt
        if not had:
            nosec.append(name)              # no such section to read at all
        elif not tgt:
            nochain.append(name)            # a section, but nothing this parse can read

    # ---- rows: one per router shape (table order), then the intake-only skills
    rows, by_shape, row_of = [], {}, {}
    for rt in routes:
        if rt["skill"] not in kset:
            notes.append(f"router routes to /notrest:{rt['skill']} — no such skill "
                         f"directory (drawn anyway; eval's ROUTER check owns that fault)")
        if rt["shape"] in by_shape:
            row = by_shape[rt["shape"]]
            row["router"] += [p for p in rt["phrases"] if p not in row["router"]]
            continue
        row = {"skill": rt["skill"], "shape": rt["shape"],
               "router": list(rt["phrases"]), "intake": []}
        by_shape[rt["shape"]] = row
        rows.append(row)
        row_of.setdefault(rt["skill"], row)
    extra = {}
    for it in intake:
        if it["skill"] not in kset:
            notes.append(f"oracle intake names /{it['skill']} — no such skill directory")
        row = row_of.get(it["skill"]) or extra.get(it["skill"])
        if row is None:
            row = {"skill": it["skill"], "shape": None, "router": [], "intake": []}
            extra[it["skill"]] = row
        if it["phrase"] not in row["intake"]:
            row["intake"].append(it["phrase"])
    for name in sorted(extra):
        rows.append(extra[name])
        row_of[name] = extra[name]

    # ---- geometry
    pills, nodes, edges = [], [], []
    y = JY0
    for r in rows:
        items = ([("router", p) for p in r["router"]] +
                 [("intake", p) for p in r["intake"]])
        n = max(1, len(items))
        h = round(max(JNODE_H, n * JPILL_H + (n - 1) * JPILL_GAP), 2)
        cy = round(y + h / 2, 2)
        sid = ("shape:" + r["shape"]) if r["shape"] else None
        kid = "skill:" + r["skill"]
        if sid:
            nodes.append({"id": sid, "kind": "shape", "name": r["shape"], "skill": r["skill"],
                          "x": JSX, "y": round(cy - JNODE_H / 2, 2), "w": JSW, "h": JNODE_H,
                          "cx": round(JSX + JSW / 2, 2), "cy": cy,
                          "phrases": list(r["router"])})
        nodes.append({"id": kid, "kind": "skill", "name": r["skill"], "shape": r["shape"],
                      "routed": True, "x": JKX, "y": round(cy - JNODE_H / 2, 2),
                      "w": JKW, "h": JNODE_H, "cx": round(JKX + JKW / 2, 2), "cy": cy,
                      "router_phrases": list(r["router"]), "intake_phrases": list(r["intake"])})
        py = y
        for knd, txt in items:
            t = _jclip(txt)
            w = round(min(JPW, max(96.0, len(t) * JCHAR + 26.0)), 2)
            to = sid if (knd == "router" and sid) else kid
            pid = "p%d" % len(pills)
            pills.append({"id": pid, "text": t, "full": re.sub(r"\s+", " ", txt).strip(),
                          "kind": knd, "to": to, "skill": r["skill"],
                          "x": JPX, "y": round(py, 2), "w": w, "h": JPILL_H,
                          "cy": round(py + JPILL_H / 2, 2)})
            edges.append({"from": pid, "to": to,
                          "kind": "route" if knd == "router" else "intake"})
            py += JPILL_H + JPILL_GAP
        if sid:
            edges.append({"from": sid, "to": kid, "kind": "route"})
        y += h + JROW_GAP

    band_names = [n for n in known if n not in row_of]
    band_top = round(y - JROW_GAP + JBAND_GAP, 2)
    band_bot = band_top
    for i, name in enumerate(band_names):
        bx = JPX + (i % JBAND_COLS) * (JBAND_W + JBAND_GX)
        by = band_top + (i // JBAND_COLS) * (JBAND_H + JBAND_GY)
        nodes.append({"id": "skill:" + name, "kind": "skill", "name": name, "shape": None,
                      "routed": False, "x": round(bx, 2), "y": round(by, 2),
                      "w": JBAND_W, "h": JBAND_H, "cx": round(bx + JBAND_W / 2, 2),
                      "cy": round(by + JBAND_H / 2, 2),
                      "router_phrases": [], "intake_phrases": []})
        band_bot = max(band_bot, by + JBAND_H)

    have = {n["id"] for n in nodes}
    for name in known:
        for t in chains[name]:
            if "skill:" + name in have and "skill:" + t in have:
                edges.append({"from": "skill:" + name, "to": "skill:" + t, "kind": "chain"})

    byid = {n["id"]: n for n in nodes}
    into = {}
    for e in edges:
        if e["kind"] == "chain":
            into.setdefault(e["to"], []).append(e["from"][6:])
    for n in nodes:
        if n["kind"] != "skill":
            continue
        n["chains_to"] = chains.get(n["name"], [])
        n["chained_from"] = sorted(into.get(n["id"], []))
        n["has_chains_section"] = n["name"] not in nosec

    stamp, stamp_from = git_stamp(root)
    if stamp_from == "none":
        notes.append("git is unavailable or this is not a repo — the page carries no "
                     "commit stamp, so two renders of different trees look alike")
    elif stamp.endswith("+dirty"):
        notes.append(f"stamped {stamp}: the tree has uncommitted tracked changes, so the "
                     f"commit alone does not identify what was read")
    if nosec:
        notes.append("no Chains / Finishing-up section to parse in: " + ", ".join(nosec))
    if nochain:
        notes.append("a Chains / Finishing-up section with no explicit `/verb` reference "
                     "(hand-offs named in prose are NOT guessed at): " + ", ".join(nochain))

    x1 = max([n["x"] + n["w"] for n in nodes] + [JKX + JKW]) + JBULGE + 40.0
    extent = {"x0": 0.0, "y0": 0.0, "x1": round(x1, 2), "y1": round(band_bot + 70.0, 2)}
    counts = {"skills": sum(1 for n in nodes if n["kind"] == "skill"),
              "shapes": sum(1 for n in nodes if n["kind"] == "shape"),
              "routed": sum(1 for n in nodes if n["kind"] == "skill" and n["routed"]),
              "by_name_only": len(band_names),
              "phrases": len(pills),
              "router_phrases": sum(1 for p in pills if p["kind"] == "router"),
              "intake_phrases": sum(1 for p in pills if p["kind"] == "intake"),
              "chains": sum(1 for e in edges if e["kind"] == "chain"),
              "edges": len(edges),
              "no_chains_section": len(nosec), "chains_unparsed": len(nochain)}
    return {"generated": stamp, "stamp_from": stamp_from, "root": str(root),
            "plugin": str(plug), "sources": {
                "router": str((plug / "hooks" / "router.sh").relative_to(root))
                          if str(plug).startswith(str(root)) else str(plug / "hooks" / "router.sh"),
                "intake": "skills/oracle/SKILL.md", "chains": "skills/*/SKILL.md"},
            "extent": extent, "bandTop": band_top, "notes": notes, "counts": counts,
            "byName": band_names, "pills": pills, "nodes": nodes, "edges": edges}


JOURNEY_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>journey — __TITLE__</title>
<style>
:root{
  --surface-0:#f7f6f2; --surface-1:#ffffff; --border:#e6e3da; --border-strong:#d2cfc4;
  --text-primary:#20201d; --text-secondary:#57564f; --text-muted:#86857b;
  --phrase:#7F77DD; --phrase-bg:#eceaff; --intake:#1D9E75; --intake-bg:#e2f4ee;
  --shape:#5C98D6; --shape-bg:#e4eefa; --skill:#20201d; --skill-bg:#ffffff;
  --byname:#B4633A; --byname-bg:#f6ece5; --chain:#a8a69a; --wire:#b9b6aa;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --surface-0:#141413; --surface-1:#1f1f1d; --border:#37362e; --border-strong:#4b4a40;
    --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
    --phrase:#9a92ea; --phrase-bg:#2a2843; --intake:#3fc79c; --intake-bg:#1d3630;
    --shape:#6FA9E6; --shape-bg:#1e2c3d; --skill:#f2f1ea; --skill-bg:#26261f;
    --byname:#d98a5e; --byname-bg:#33261e; --chain:#5d5c53; --wire:#4a493f;
  }
}
:root[data-theme="dark"]{
  --surface-0:#141413; --surface-1:#1f1f1d; --border:#37362e; --border-strong:#4b4a40;
  --text-primary:#f2f1ea; --text-secondary:#b7b5a9; --text-muted:#8b8a7f;
  --phrase:#9a92ea; --phrase-bg:#2a2843; --intake:#3fc79c; --intake-bg:#1d3630;
  --shape:#6FA9E6; --shape-bg:#1e2c3d; --skill:#f2f1ea; --skill-bg:#26261f;
  --byname:#d98a5e; --byname-bg:#33261e; --chain:#5d5c53; --wire:#4a493f;
}
*{box-sizing:border-box}
html{height:100%;width:100%}
body{margin:0;width:100vw;height:100vh;background:var(--surface-0);color:var(--text-primary);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  display:flex;flex-direction:column;overflow:hidden}
header{display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:center;padding:.6rem .9rem;
  border-bottom:1px solid var(--border);background:var(--surface-1)}
h1{font-size:14px;font-weight:500;margin:0}
.sub{font-size:12px;color:var(--text-muted)}
.path{max-width:52ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.grow{flex:1}
input[type=search]{font:inherit;font-size:12px;padding:.3rem .55rem;border-radius:999px;
  border:1px solid var(--border);background:var(--surface-0);color:var(--text-primary);width:190px}
input[type=search]:focus{outline:none;border-color:var(--border-strong)}
button{background:var(--surface-0);color:var(--text-secondary);border:1px solid var(--border);
  border-radius:999px;padding:.3rem .7rem;font-size:12px;cursor:pointer;font-family:inherit}
button:hover{border-color:var(--border-strong)}
button.off{opacity:.5}
main{flex:1;display:flex;min-height:0;min-width:0;position:relative}
#stage{flex:1;position:relative;min-width:0;min-height:0;overflow:hidden}
svg{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;
  touch-action:none;background:var(--surface-0)}
svg.drag{cursor:grabbing}
.colcap{fill:var(--text-muted);font-size:11.5px;letter-spacing:.09em}
.colrule{stroke:var(--border);stroke-width:1;stroke-dasharray:2 5}
.pill rect{fill:var(--phrase-bg);stroke:var(--phrase);stroke-width:1}
.pill.intake rect{fill:var(--intake-bg);stroke:var(--intake);stroke-dasharray:4 3}
.pill text{fill:var(--text-primary);font-size:11.5px}
.nd rect{stroke-width:1.4}
.nd.shape rect{fill:var(--shape-bg);stroke:var(--shape)}
.nd.skill rect{fill:var(--skill-bg);stroke:var(--border-strong)}
.nd.skill.byname rect{fill:var(--byname-bg);stroke:var(--byname);stroke-dasharray:5 3}
.nd text{font-size:13px;font-weight:500;fill:var(--text-primary);text-anchor:middle}
.nd.shape text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;
  fill:var(--shape)}
.nd.skill.byname text{fill:var(--byname)}
.wire{fill:none;stroke:var(--wire);stroke-width:1.3;opacity:.8}
.wire.intake{stroke:var(--intake);stroke-dasharray:5 4;opacity:.75}
.wire.hop{stroke:var(--shape);stroke-width:1.8;opacity:.85}
.chain{fill:none;stroke:var(--chain);stroke-width:1.15;opacity:.42}
svg.nochain .chain,svg.nochain .chainhead{display:none}
.chainhead{fill:var(--chain);opacity:.5}
.pill,.nd{cursor:pointer}
.pill:hover rect,.nd:hover rect{stroke-width:2.2}
.dim{opacity:.13}
.hot .chain,.chain.hot{stroke:var(--phrase);opacity:.95;stroke-width:2}
svg.far .pill text,svg.far .colcap{display:none}
#legend{position:absolute;left:.7rem;bottom:.7rem;background:var(--surface-1);
  border:1px solid var(--border);border-radius:10px;padding:.5rem .65rem;font-size:11.5px;
  color:var(--text-secondary);max-width:min(720px,92%);max-height:44%;overflow:auto}
#legend>summary{cursor:pointer;list-style:none;color:var(--text-muted);font-size:11px;
  letter-spacing:.06em;margin:-.15rem 0 0}
#legend>summary::-webkit-details-marker{display:none}
#legend:not([open]){padding:.3rem .6rem}
#legend:not([open])>summary{margin:0}
#legend .row{display:flex;flex-wrap:wrap;gap:.25rem .8rem;align-items:center}
#legend .row+.row{margin-top:.35rem;padding-top:.35rem;border-top:1px solid var(--border)}
#legend span.it{display:inline-flex;align-items:center;gap:.32rem}
#legend .n{color:var(--text-muted)}
#legend .note{color:var(--text-muted);line-height:1.45}
.sw{width:16px;height:9px;border-radius:3px;flex:none;display:inline-block;
  border:1px solid var(--border-strong)}
#card{position:absolute;display:none;max-width:min(430px,72vw);max-height:56vh;overflow:auto;
  background:var(--surface-1);border:1px solid var(--border-strong);border-radius:10px;
  padding:.55rem .7rem;font-size:12.5px;box-shadow:0 6px 24px rgba(0,0,0,.18);
  pointer-events:none;z-index:6;line-height:1.45}
#card.pinned{pointer-events:auto}
#card .k{display:inline-block;font-size:10.5px;padding:.05rem .4rem;border-radius:999px;
  border:1px solid var(--border);color:var(--text-secondary);margin-right:.25rem}
#card .ttl{font-weight:600;margin:.35rem 0 .15rem;font-size:13.5px}
#card .lbl{font-size:10.5px;letter-spacing:.04em;color:var(--text-muted);margin:.5rem 0 .2rem}
#card .st{color:var(--text-secondary)}
#card code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;
  word-break:break-all;color:var(--text-secondary)}
#card .foot{color:var(--text-muted);font-size:10.5px;margin-top:.45rem}
</style>
</head>
<body>
<header>
  <div>
    <h1>journey — <span class="mono">__TITLE__</span></h1>
    <div class="sub mono path" title="__ROOT__">__ROOT__</div>
  </div>
  <div class="sub">__COUNTS__ · <span class="mono">__GENERATED__</span>
    <span title="stamp source">(__STAMPFROM__)</span></div>
  <span class="grow"></span>
  <input id="q" type="search" placeholder="filter phrases · skills…" autocomplete="off">
  <span id="qn" class="sub"></span>
  <button id="chains" type="button">chains</button>
  <button id="fit" type="button">fit</button>
  <button id="zin" type="button">+</button>
  <button id="zout" type="button">−</button>
  <button id="theme" type="button">light / dark</button>
</header>
<main><div id="stage">
  <svg id="sv" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="jh" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="6" markerHeight="5"
              orient="auto-start-reverse"><path class="chainhead" d="M0,0 L10,4 L0,8 z"/></marker>
    </defs>
    <g id="scene"></g>
  </svg>
  <div id="card"></div>
  <details id="legend" open><summary>LEGEND — click to fold</summary></details>
</div></main>
<script>
(function(){
var D = "__JOURNEY_DATA__";
var NS = 'http://www.w3.org/2000/svg';
var root = document.documentElement;
var svg = document.getElementById('sv'), scene = document.getElementById('scene');
var stage = document.getElementById('stage'), card = document.getElementById('card');
var nodes = D.nodes || [], pills = D.pills || [], byId = {}, i;
for (i = 0; i < nodes.length; i++) byId[nodes[i].id] = nodes[i];
for (i = 0; i < pills.length; i++) byId[pills[i].id] = pills[i];
var gById = {}, view = {x:0, y:0, k:1}, userMoved = false, pinned = null;

function el(tag, attrs, cls){
  var e = document.createElementNS(NS, tag);
  if (cls) e.setAttribute('class', cls);
  for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) e.setAttribute(k, attrs[k]);
  return e;
}
function esc(s){
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function num(v){ return Math.round(v * 100) / 100; }
/* an S-curve between two column edges — the wires read as flow, not as a truss */
function wire(x1, y1, x2, y2){
  var mx = (x1 + x2) / 2;
  return 'M' + num(x1) + ',' + num(y1) + ' C' + num(mx) + ',' + num(y1) + ' ' +
         num(mx) + ',' + num(y2) + ' ' + num(x2) + ',' + num(y2);
}
/* chains swing out to the right of the skill column so they never cross the wires */
function arc(x, y1, y2, out){
  return 'M' + num(x) + ',' + num(y1) + ' C' + num(x + out) + ',' + num(y1) + ' ' +
         num(x + out) + ',' + num(y2) + ' ' + num(x) + ',' + num(y2);
}

var E = D.extent;
var gCap = el('g'), gChain = el('g'), gWire = el('g'), gNode = el('g');
[gCap, gChain, gWire, gNode].forEach(function(g){ scene.appendChild(g); });

/* column captions */
function cap(x, t){
  var e = el('text', {x:x, y:56}, 'colcap'); e.textContent = t; gCap.appendChild(e);
  gCap.appendChild(el('path', {d:'M' + x + ',68 H' + (x + 240)}, 'colrule'));
}
cap(__JPX__, 'WHAT SOMEONE TYPES');
cap(__JSX__, 'SHAPE — router.sh');
cap(__JKX__, 'SKILL — the verb that runs');
var bt = el('text', {x:__JPX__, y:D.bandTop - 30}, 'colcap');
bt.textContent = 'BY NAME ONLY — no router arm, no intake route: these fire when you type the name';
gCap.appendChild(bt);
gCap.appendChild(el('path', {d:'M' + __JPX__ + ',' + (D.bandTop - 18) + ' H' + (E.x1 - 200)}, 'colrule'));

/* chains first, underneath everything */
(D.edges || []).forEach(function(e){
  if (e.kind !== 'chain') return;
  var a = byId[e.from], b = byId[e.to];
  if (!a || !b) return;
  var x = Math.max(a.x + a.w, b.x + b.w);
  var out = 40 + Math.min(__JBULGE__, Math.abs(a.cy - b.cy) * 0.30);
  var p = el('path', {d:arc(x, a.cy, b.cy, out), 'marker-end':'url(#jh)'}, 'chain');
  p.setAttribute('data-a', e.from); p.setAttribute('data-b', e.to);
  gChain.appendChild(p);
});

/* the wires: phrase -> shape -> skill, and the dashed intake shortcut */
(D.edges || []).forEach(function(e){
  if (e.kind === 'chain') return;
  var a = byId[e.from], b = byId[e.to];
  if (!a || !b) return;
  var y1 = a.cy !== undefined ? a.cy : a.y + a.h / 2;
  gWire.appendChild(el('path',
    {d:wire(a.x + a.w, y1, b.x, b.cy)},
    'wire' + (e.kind === 'intake' ? ' intake' : (a.kind === 'shape' ? ' hop' : ''))));
});

/* pills */
pills.forEach(function(p){
  var g = el('g', {'data-id':p.id}, 'pill' + (p.kind === 'intake' ? ' intake' : ''));
  g.appendChild(el('rect', {x:p.x, y:p.y, width:p.w, height:p.h, rx:11}));
  var t = el('text', {x:p.x + 11, y:p.y + p.h / 2 + 4});
  t.textContent = p.text; g.appendChild(t);
  gNode.appendChild(g); gById[p.id] = g;
});
/* shape and skill nodes */
nodes.forEach(function(n){
  var cls = 'nd ' + n.kind + (n.kind === 'skill' && !n.routed ? ' byname' : '');
  var g = el('g', {'data-id':n.id}, cls);
  g.appendChild(el('rect', {x:n.x, y:n.y, width:n.w, height:n.h, rx:8}));
  var t = el('text', {x:n.cx, y:n.cy + 4.5});
  t.textContent = n.name; g.appendChild(t);
  gNode.appendChild(g); gById[n.id] = g;
});

/* ------------------------------------------------------------------- cards */
function list(a){ return (a && a.length) ? a.map(esc).join(' · ') : '<span class="st">—</span>'; }
function nodeCard(n){
  if (n.kind === 'shape')
    return '<div><span class="k">router shape</span></div>' +
      '<div class="ttl mono">' + esc(n.name) + '</div>' +
      '<div class="st">routes to <code>/notrest:' + esc(n.skill) + '</code></div>' +
      '<div class="lbl">PHRASES THAT MATCH</div><div class="st">' + list(n.phrases) + '</div>' +
      '<div class="foot">first match wins — arms above this one take precedence</div>';
  return '<div><span class="k">skill</span>' +
    (n.routed ? '<span class="k">routed</span>' : '<span class="k">by name only</span>') +
    (n.has_chains_section ? '' : '<span class="k">no chains section</span>') + '</div>' +
    '<div class="ttl mono">/notrest:' + esc(n.name) + '</div>' +
    (n.shape ? '<div class="st">router shape <code>' + esc(n.shape) + '</code></div>'
             : '<div class="st">no router arm — nothing a user types fires this by itself</div>') +
    '<div class="lbl">ROUTER PHRASES</div><div class="st">' + list(n.router_phrases) + '</div>' +
    '<div class="lbl">ORACLE INTAKE</div><div class="st">' + list(n.intake_phrases) + '</div>' +
    '<div class="lbl">CHAINS TO</div><div class="st">' + list(n.chains_to) + '</div>' +
    '<div class="lbl">CHAINED FROM</div><div class="st">' + list(n.chained_from) + '</div>' +
    '<div class="foot">chain arrows are parsed from this skill\'s own Chains / Finishing-up ' +
    'section — text, not behaviour</div>';
}
function pillCard(p){
  return '<div><span class="k">' + (p.kind === 'intake' ? 'oracle intake' : 'router phrase') +
    '</span></div><div class="ttl">' + esc(p.full || p.text) + '</div>' +
    '<div class="st">' + (p.kind === 'intake'
      ? 'the intake conversation routes this to <code>/notrest:' + esc(p.skill) + '</code>'
      : 'matched word-bounded inside the prompt by <code>hooks/router.sh</code>') + '</div>' +
    '<div class="foot">the router only NUDGES — it prints one line and never blocks the prompt</div>';
}
function bodyFor(id){
  var n = byId[id];
  return n.kind === 'router' || n.kind === 'intake' ? pillCard(n) : nodeCard(n);
}
function showCard(html, ev){
  card.innerHTML = html + (pinned ? '<div class="foot">pinned — click the background to release</div>' : '');
  card.style.display = 'block';
  var r = stage.getBoundingClientRect(), w = card.offsetWidth, h = card.offsetHeight;
  var x = ev.clientX - r.left + 16, y = ev.clientY - r.top + 16;
  if (x + w > r.width - 8) x = Math.max(8, ev.clientX - r.left - w - 16);
  if (y + h > r.height - 8) y = Math.max(8, r.height - h - 8);
  card.style.left = x + 'px'; card.style.top = y + 'px';
}
function hitTarget(t){
  while (t && t !== scene){
    if (t.hasAttribute && t.hasAttribute('data-id')) return t;
    t = t.parentNode;
  }
  return null;
}
function highlight(id){
  var ch = gChain.childNodes, j;
  for (j = 0; j < ch.length; j++){
    var on = id && (ch[j].getAttribute('data-a') === id || ch[j].getAttribute('data-b') === id);
    ch[j].classList.toggle('hot', !!on);
  }
}
svg.addEventListener('mousemove', function(ev){
  if (drag.on || pinned) return;
  var g = hitTarget(ev.target);
  if (g){ showCard(bodyFor(g.getAttribute('data-id')), ev); highlight(g.getAttribute('data-id')); }
  else { card.style.display = 'none'; highlight(null); }
});
svg.addEventListener('mouseleave', function(){ if (!pinned){ card.style.display = 'none'; highlight(null); } });
function unpin(){ pinned = null; card.classList.remove('pinned'); card.style.display = 'none'; highlight(null); }
svg.addEventListener('click', function(ev){
  if (drag.moved) return;
  var g = hitTarget(ev.target);
  if (!g || pinned === g){ unpin(); return; }
  pinned = g; card.classList.add('pinned');
  showCard(bodyFor(g.getAttribute('data-id')), ev); highlight(g.getAttribute('data-id'));
});
document.addEventListener('keydown', function(ev){ if (ev.key === 'Escape') unpin(); });

/* ------------------------------------------------------- pan · zoom · fit */
function apply(){
  scene.setAttribute('transform', 'translate(' + num(view.x) + ',' + num(view.y) +
                     ') scale(' + (Math.round(view.k * 1e4) / 1e4) + ')');
  svg.classList.toggle('far', view.k < 0.42);
}
/* fit the WIDTH and anchor at the top: the page is a tall table of doors, read
   downward. Fitting the height would make every pill a hairline. */
function fit(){
  var r = stage.getBoundingClientRect();
  var w = Math.max(1, E.x1 - E.x0), h = Math.max(1, E.y1 - E.y0);
  view.k = Math.max(0.05, Math.min(1, (r.width - 36) / w));
  view.x = 18 - E.x0 * view.k;
  view.y = (h * view.k <= r.height) ? (r.height - h * view.k) / 2 - E.y0 * view.k
                                    : 14 - E.y0 * view.k;
  userMoved = false; apply();
}
function zoomAt(cx, cy, f){
  var k = Math.max(0.05, Math.min(6, view.k * f));
  view.x = cx - (cx - view.x) * (k / view.k);
  view.y = cy - (cy - view.y) * (k / view.k);
  view.k = k; userMoved = true; apply();
}
var drag = {on:false, moved:false, x:0, y:0};
svg.addEventListener('mousedown', function(ev){
  drag.on = true; drag.moved = false; drag.x = ev.clientX; drag.y = ev.clientY;
  svg.classList.add('drag');
});
window.addEventListener('mousemove', function(ev){
  if (!drag.on) return;
  var dx = ev.clientX - drag.x, dy = ev.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
  view.x += dx; view.y += dy; drag.x = ev.clientX; drag.y = ev.clientY;
  userMoved = true; apply();
});
window.addEventListener('mouseup', function(){
  drag.on = false; svg.classList.remove('drag');
  setTimeout(function(){ drag.moved = false; }, 0);
});
svg.addEventListener('wheel', function(ev){
  ev.preventDefault();
  var r = stage.getBoundingClientRect();
  zoomAt(ev.clientX - r.left, ev.clientY - r.top, ev.deltaY < 0 ? 1.12 : 1 / 1.12);
}, {passive:false});
document.getElementById('fit').addEventListener('click', fit);
document.getElementById('zin').addEventListener('click', function(){
  var r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1.25);
});
document.getElementById('zout').addEventListener('click', function(){
  var r = stage.getBoundingClientRect(); zoomAt(r.width / 2, r.height / 2, 1 / 1.25);
});
document.getElementById('chains').addEventListener('click', function(){
  svg.classList.toggle('nochain');
  this.classList.toggle('off', svg.classList.contains('nochain'));
});
document.getElementById('theme').addEventListener('click', function(){
  var cur = root.getAttribute('data-theme') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  root.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark');
});
window.addEventListener('resize', function(){ if (!userMoved) fit(); });
if (window.ResizeObserver) new ResizeObserver(function(){ if (!userMoved) fit(); }).observe(stage);
window.requestAnimationFrame(function(){ if (!userMoved) fit(); });

/* ------------------------------------------------------------ filter · legend */
var q = document.getElementById('q'), qn = document.getElementById('qn');
q.addEventListener('input', function(){
  var s = q.value.trim().toLowerCase(), shown = 0, all = pills.concat(nodes);
  all.forEach(function(o){
    var hay = ((o.text || '') + ' ' + (o.name || '') + ' ' + (o.skill || '') + ' ' +
               (o.shape || '')).toLowerCase();
    var on = !s || hay.indexOf(s) >= 0;
    if (gById[o.id]) gById[o.id].classList.toggle('dim', !on);
    if (on) shown++;
  });
  qn.textContent = s ? shown + '/' + all.length : '';
});
(function legend(){
  var c = D.counts, L = document.getElementById('legend');
  function sw(bg, br, dash){
    return '<i class="sw" style="background:' + bg + ';border-color:' + br +
      (dash ? ';border-style:dashed' : '') + '"></i>';
  }
  var glyphs = [
    sw('var(--phrase-bg)','var(--phrase)') + 'router phrase <span class="n">' + c.router_phrases + '</span>',
    sw('var(--intake-bg)','var(--intake)',1) + 'oracle intake phrase <span class="n">' + c.intake_phrases + '</span>',
    sw('var(--shape-bg)','var(--shape)') + 'router shape <span class="n">' + c.shapes + '</span>',
    sw('var(--skill-bg)','var(--border-strong)') + 'skill reached by a route <span class="n">' + c.routed + '</span>',
    sw('var(--byname-bg)','var(--byname)',1) + 'by name only <span class="n">' + c.by_name_only + '</span>',
    sw('transparent','var(--chain)') + 'chains-to arrow <span class="n">' + c.chains + '</span>'
  ];
  var tallies = [
    'skills <span class="n">' + c.skills + '</span>',
    'shapes <span class="n">' + c.shapes + '</span>',
    'phrases <span class="n">' + c.phrases + '</span>',
    'edges <span class="n">' + c.edges + '</span>',
    'no chains section <span class="n">' + c.no_chains_section + '</span>',
    'chains section, nothing parseable <span class="n">' + c.chains_unparsed + '</span>'
  ];
  var notes = (D.notes || []).slice();
  notes.push('read from ' + esc(D.sources.router) + ', ' + esc(D.sources.intake) +
             ' and ' + esc(D.sources.chains) + ' — this page draws what those files SAY, ' +
             'not what the harness does at runtime.');
  notes.push('stamped ' + esc(D.generated) + ' from the ' + esc(D.stamp_from) +
             ' — identical inputs at the same commit render an identical page.');
  L.innerHTML = '<summary>LEGEND — click to fold</summary>' +
    '<div class="row">' + glyphs.map(function(g){ return '<span class="it">' + g + '</span>'; }).join('') + '</div>' +
    '<div class="row">' + tallies.map(function(t){ return '<span class="it">' + t + '</span>'; }).join('') + '</div>' +
    '<div class="row"><span class="note">' + notes.map(esc).join('<br>') + '</span></div>';
})();
fit();
})();
</script>
</body>
</html>
"""


def render_journey_html(j, title="project"):
    data = json.dumps(j, separators=(",", ":")).replace("</", "<\\/")
    c = j["counts"]
    counts = (f"{c['skills']} skills · {c['shapes']} shapes · {c['phrases']} phrases · "
              f"{c['chains']} chains · {c['by_name_only']} by name only")
    return (JOURNEY_TEMPLATE
            .replace("__TITLE__", esc(title))
            .replace("__ROOT__", esc(j.get("root", "")))
            .replace("__GENERATED__", esc(j.get("generated", "")))
            .replace("__STAMPFROM__", esc(j.get("stamp_from", "")))
            .replace("__COUNTS__", esc(counts))
            .replace("__JPX__", str(JPX)).replace("__JSX__", str(JSX))
            .replace("__JKX__", str(JKX)).replace("__JBULGE__", str(JBULGE))
            .replace('"__JOURNEY_DATA__"', data))


def cmd_journey(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        die(f"not a directory: {root}")
    out = pathlib.Path(a.out).expanduser()
    out = out if out.is_absolute() else (root / a.out)
    if out.suffix.lower() in (".html", ".htm"):
        html_p, json_p = out, out.with_suffix(".json")
    else:
        html_p, json_p = out / "journey.html", out / "journey.json"
    j = build_journey(root)
    html_p.parent.mkdir(parents=True, exist_ok=True)
    json_p.write_text(json.dumps(j, indent=1), encoding="utf-8")
    html_p.write_text(render_journey_html(j, title=root.name), encoding="utf-8")
    c = j["counts"]
    print(f"{html_p}: {c['skills']} skills · {c['shapes']} router shapes · "
          f"{c['phrases']} phrases ({c['router_phrases']} router, {c['intake_phrases']} intake) · "
          f"{c['chains']} chain arrows · {c['by_name_only']} by name only · "
          f"stamp={j['generated']} ({j['stamp_from']})")
    for n in j["notes"]:
        print(f"  note: {n}")
    print(f"  data: {json_p}")
    if a.open:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.run([opener, str(html_p)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  opened with {opener}")
        except OSError:
            print(f"  could not run {opener} — open {html_p} in any browser")
    return 0


# ================================================== queries over the file graph

def load_graph(a):
    """The scan's own output — never re-derived here. A query answers from the
    last scan and says when that was; it never pretends to be live."""
    root = pathlib.Path(a.root).expanduser().resolve()
    out = pathlib.Path(a.out).expanduser()
    out = out if out.is_absolute() else (root / a.out)
    p = out if out.suffix == ".json" else (out / "graph.json")
    if not p.is_file():
        die(f"no scan data at {p}\nrun the scan first:\n"
            f"  python3 {pathlib.Path(__file__).name} scan --root {root}")
    try:
        return root, p, json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        die(f"{p}: not valid JSON ({e}) — re-run the scan")


def resolve_target(g, arg, root):
    """id, repo-relative path, absolute path inside the root, or a unique
    basename/substring — in that order, first unambiguous match wins."""
    ids = [n["id"] for n in g["nodes"]]
    s = str(arg)
    ap = pathlib.Path(s).expanduser()
    if ap.is_absolute():
        try:
            s = ap.resolve().relative_to(root).as_posix()
        except ValueError:
            s = ap.as_posix()
    s = s.lstrip("./")
    if s in ids:
        return s, []
    for pick in (lambda i: i.endswith("/" + s), lambda i: i.split("/")[-1] == s,
                 lambda i: s.lower() in i.lower()):
        hits = [i for i in ids if pick(i)]
        if len(hits) == 1:
            return hits[0], []
        if len(hits) > 1:
            return None, hits
    return None, []


def cmd_links(a):
    root, p, g = load_graph(a)
    node, hits = resolve_target(g, a.path, root)
    if not node:
        if hits:
            die(f"'{a.path}' matches {len(hits)} nodes — be more specific:\n  "
                + "\n  ".join(sorted(hits)[:12]))
        die(f"'{a.path}' is not in {p} (scanned {g.get('generated','?')}) — "
            "check the path, or re-run the scan if the file is new")
    meta = next(n for n in g["nodes"] if n["id"] == node)
    out = sorted(((e["kind"], e["to"]) for e in g["edges"] if e["from"] == node))
    inc = sorted(((e["kind"], e["from"]) for e in g["edges"] if e["to"] == node))
    print(f"{node}  ({meta.get('type','?')} · {meta.get('size',0)} B · degree {meta.get('degree',0)})")
    for title, rows in (("links out", out), ("links in", inc)):
        print(f"\n{title} ({len(rows)})")
        if not rows:
            print("  (none)")
        for kind, other in rows:
            print(f"  {kind:<10} {other}")
    print(f"\nfrom {p} · scanned {g.get('generated','?')} ({g.get('listing','?')} listing)")
    return 0


def cmd_orphans(a):
    root, p, g = load_graph(a)
    orph = [n for n in g["nodes"]
            if not n.get("degree") and n.get("type") not in ("external", "project")]
    orph.sort(key=lambda n: (n.get("type", ""), n["id"]))
    shown = orph if a.limit <= 0 else orph[:a.limit]
    print(f"{len(orph)} node(s) with no edges either way, of {len(g['nodes'])} scanned")
    for n in shown:
        print(f"  {n.get('type','?'):<9} {n['id']}")
    if len(shown) < len(orph):
        print(f"  … {len(orph) - len(shown)} more (--limit 0 for all)")
    print(f"\nfrom {p} · scanned {g.get('generated','?')} ({g.get('listing','?')} listing)")
    print("no edge means nothing in THIS repo's text points at it — an entry point, a "
          "hook target,\nor a file referenced from outside the scan looks identical to "
          "dead code here. Check before deleting.")
    return 0


def cmd_stale(a):
    root, p, g = load_graph(a)
    now = int(datetime.now(timezone.utc).timestamp())
    cut = a.days * 86400
    rows = [(now - n["mtime"], n) for n in g["nodes"]
            if n.get("mtime") and (now - n["mtime"]) >= cut]
    rows.sort(key=lambda r: (-r[0], r[1]["id"]))
    shown = rows if a.limit <= 0 else rows[:a.limit]
    print(f"{len(rows)} file(s) untouched for {a.days}+ days, of {len(g['nodes'])} scanned")
    for age, n in shown:
        stamp = datetime.fromtimestamp(n["mtime"], timezone.utc).strftime("%Y-%m-%d")
        print(f"  {stamp}  {age // 86400:>5}d  {n['id']}  ({n.get('type','?')}, "
              f"degree {n.get('degree', 0)})")
    if len(shown) < len(rows):
        print(f"  … {len(rows) - len(shown)} more (--limit 0 for all)")
    print(f"\nfrom {p} · scanned {g.get('generated','?')} ({g.get('listing','?')} listing)")
    print("mtime is the filesystem's, not the project's: a fresh clone or a checkout "
          "rewrites every\nmtime to now, and an untouched file can still be load-bearing. "
          "Age is a prompt, not a verdict.")
    return 0


# =========================================== domains — lane boundaries by graph
#
# The seat has been computing TOUCH-ONLY lists by hand every build, reasoning
# about dependencies the file graph already knows. This computes the mechanical
# half: which files move together, where the seams are, and which files belong
# to nobody. The seat still judges.

HUB_FLOOR = 4          # a hub needs at least this many in-scope neighbours …
HUB_MULT = 3           # … or this multiple of the MEDIAN degree — whichever is larger
#
# Why the median and not a share of the scope: a share scales the wrong way. At
# 0.30 a 200-file scope demanded degree >= 60, so a plugin.json linked by 25
# files rode into a lane precisely when lanes matter most — and under 5 files
# seat_held was provably empty as a silent structural property. 3x the median is
# scale-free: it asks "is this file far more connected than its neighbours", which
# is the actual question, and the floor of 4 keeps a tiny scope from calling a
# degree-2 file a hub.


def domains_listing(root):
    """The listing `scan` uses, git only. domains partitions a REAL tree: with
    no git listing there is no tracked set to partition, and a bare walk would
    quietly invent one out of whatever happens to be lying in the directory."""
    if git_files(root) is None:
        die(f"not a git repo: {root}\n"
            f"domains partitions git's own file listing (the same listing scan "
            f"uses) — run it inside a repo")
    rels, _mode, _skipped = list_files(root)
    return rels


def changed_paths(root):
    """(paths, deleted) from `git status --porcelain -z`. A rename reports its
    NEW side — that is the file a lane would edit. Deletions come back
    separately so the caller can DROP them and say so: nobody hand-named those,
    and a lane cannot be scoped to a file that is gone."""
    try:
        r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-z"],
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        die(f"could not read `git status` in {root}: {e}")
    if r.returncode != 0:
        die(f"`git status` failed in {root}:\n"
            + r.stderr.decode("utf-8", "replace").strip())
    fields = r.stdout.decode("utf-8", "replace").split("\0")
    keep, deleted = [], []
    i = 0
    while i < len(fields):
        f = fields[i]
        i += 1
        if len(f) < 4:
            continue
        xy, path = f[:2], f[3:]
        if "R" in xy or "C" in xy:
            i += 1                      # the ORIGIN path follows; we keep the new side
        if "D" in xy:                   # incl. RD: renamed, then the new side deleted
            deleted.append(path)
            continue
        keep.append(path)
    return sorted(set(keep)), sorted(set(deleted))


def expand_paths(root, raw_paths, listing, notes):
    """Explicit files and directories → repo-relative ids. A named path that is
    not in the tree is FATAL and named: instructions must not stand on missing
    artifacts, and this command does not partition fictions."""
    ids = set(listing)
    picked = set()
    for raw in raw_paths:
        p = pathlib.Path(raw).expanduser()
        ap = p if p.is_absolute() else (root / p)
        try:
            rel = ap.resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            die(f"outside the root: {raw}\n  root is {root}")
        if rel == ".":
            rel = ""
        if rel and rel in ids:
            picked.add(rel)
            continue
        if ap.is_dir():
            prefix = (rel + "/") if rel else ""
            hits = [i for i in listing if not prefix or i.startswith(prefix)]
            if not hits:
                notes.append(f"{raw}: a directory git lists no files under "
                             f"(ignored, empty, or all skipped) — 0 files scoped from it")
            picked.update(hits)
            continue
        if ap.exists():
            die(f"not in the tree: {raw}\n"
                f"  it exists on disk but git's listing does not carry it — ignored, "
                f"inside a skipped directory, or a symlink.\n"
                f"  domains partitions what the graph can see.")
        die(f"no such path: {raw}\n"
            f"  named explicitly but not in {root} — domains does not partition fictions")
    return sorted(picked)


def scope_edges(root, scoped, listing):
    """Undirected file pairs, from the SAME extraction scan uses, restricted to
    edges whose both ends are in scope. Nothing on disk is read but the scoped
    files, and no prior graph.json is consulted — this runs on a fresh clone.

    Resolution still sees the whole repo: a bare basename is only unambiguous
    against the full tree, so scoping the Repo would invent edges."""
    repo = Repo(root, listing)
    inscope = set(scoped)
    pairs = set()
    for rel in scoped:
        text = read_text(root / rel)
        if text is None:
            continue

        def add(to, _kind, _r=rel):
            if to != _r and to in inscope:
                pairs.add((_r, to) if _r < to else (to, _r))

        file_edges(repo, rel, text, add)
    return pairs


def hub_threshold(degrees):
    """max(4, 3 x median in-scope degree) — scale-free, deterministic."""
    if not degrees:
        return float(HUB_FLOOR), 0.0
    med = statistics.median(degrees)
    return max(float(HUB_FLOOR), HUB_MULT * med), med


def _numfmt(x):
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}"


def partition(scoped, pairs, sizes, lanes_req, notes):
    """Hubs out FIRST, connected components on the remainder SECOND, then
    merge-to-N. The order is load-bearing: in any real repo everything is
    transitively linked through manifests and shared config, so components over
    the FULL graph return one giant blob — and since a component is never split
    and --lanes only merges, the command would be a no-op on exactly the trees
    it exists for. Returns (lanes, seat_held); a lane is (files, n_components)."""
    nbrs = {f: set() for f in scoped}
    for a, b in pairs:
        nbrs[a].add(b)
        nbrs[b].add(a)

    degrees = [len(nbrs[f]) for f in scoped]
    thresh, med = hub_threshold(degrees)
    hubs = sorted(f for f in scoped if len(nbrs[f]) >= thresh)
    hubset = set(hubs)
    if hubs:
        notes.append(f"hub rule at degree >= {_numfmt(thresh)} "
                     f"(max of {HUB_FLOOR} and {HUB_MULT}x the median in-scope degree "
                     f"{_numfmt(med)}): {len(hubs)} file(s) pulled out of every lane into "
                     f"seat_held before components were computed")

    # components over what is LEFT
    seen, comps = set(), []
    for f in scoped:                     # scoped is sorted → deterministic order
        if f in hubset or f in seen:
            continue
        stack, comp = [f], []
        seen.add(f)
        while stack:
            c = stack.pop()
            comp.append(c)
            for nb in sorted(nbrs[c]):
                if nb in hubset or nb in seen:
                    continue
                seen.add(nb)
                stack.append(nb)
        comps.append((sorted(comp), 1))

    def wt(c):
        return sum(sizes.get(f, 0) for f in c[0])

    if lanes_req:
        if len(comps) > lanes_req:
            notes.append(f"{len(comps)} component(s) merged down to {lanes_req} lane(s), "
                         f"smallest-by-bytes first — merged lanes are still disjoint, and "
                         f"no component was split")
            while len(comps) > lanes_req:
                comps.sort(key=lambda c: (wt(c), c[0][0]))
                first, second = comps.pop(0), comps.pop(0)
                comps.append((sorted(first[0] + second[0]), first[1] + second[1]))
        elif len(comps) < lanes_req:
            notes.append(f"asked for {lanes_req} lane(s); the graph yields {len(comps)} — "
                         f"returning {len(comps)}. Padding would mean splitting a component, "
                         f"and a split manufactures the shared-file collision by construction")

    comps.sort(key=lambda c: (-wt(c), c[0][0]))
    return comps, [(h, len(nbrs[h])) for h in hubs]


def build_domains(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        die(f"not a directory: {root}")
    if a.lanes is not None and a.lanes < 1:
        die(f"--lanes must be 1 or more (got {a.lanes})")

    listing = domains_listing(root)
    notes = []

    if a.paths:
        scoped = expand_paths(root, a.paths, listing, notes)
    elif a.changed:
        raw, deleted = changed_paths(root)
        if deleted:
            shown = ", ".join(deleted[:8]) + (" …" if len(deleted) > 8 else "")
            notes.append(f"{len(deleted)} deleted path(s) dropped from the scope — "
                         f"a lane cannot be given a file that is gone: {shown}")
        ids = set(listing)
        unlisted = sorted(p for p in raw if p not in ids)
        if unlisted:
            shown = ", ".join(unlisted[:8]) + (" …" if len(unlisted) > 8 else "")
            notes.append(f"{len(unlisted)} changed path(s) git reports but the listing "
                         f"does not carry (skipped directory, symlink, unreadable): {shown}")
        scoped = sorted(p for p in raw if p in ids)
    else:
        scoped = sorted(listing)

    # An empty scope is FATAL, never a silent lanes:[] — a shrugged-off empty
    # answer is the exact moment a seat hand-partitions from memory instead,
    # which is the failure this command exists to prevent.
    if not scoped:
        die("nothing in scope — nothing to partition")

    sizes = {}
    for rel in scoped:
        try:
            sizes[rel] = (root / rel).stat().st_size
        except OSError:
            sizes[rel] = 0

    pairs = scope_edges(root, scoped, listing)
    lanes, seat_held = partition(scoped, pairs, sizes, a.lanes, notes)

    lane_of = {}
    for i, (files, _n) in enumerate(lanes, 1):
        for f in files:
            lane_of[f] = i
    hubset = {h for h, _d in seat_held}

    # a merged lane is a UNION of components — lane != domain. Say so per lane,
    # so a commission reader never reads a merge as a dependency cluster.
    for i, (_files, ncomp) in enumerate(lanes, 1):
        if ncomp > 1:
            notes.append(f"lane {i} = {ncomp} components merged for --lanes {a.lanes} — "
                         f"a merged lane is a bundle of unrelated domains, not one")

    out_lanes = []
    for i, (files, _n) in enumerate(lanes, 1):
        mine = set(files)
        bound = set()
        for a_, b_ in pairs:
            for src, dst in ((a_, b_), (b_, a_)):
                if src in mine and dst not in mine:
                    bound.add((src, dst, "seat-held" if dst in hubset else lane_of[dst]))
        out_lanes.append({
            "id": i,
            "files": files,
            "bytes": sum(sizes.get(f, 0) for f in files),
            "boundary": [{"from": f, "to": t, "lane": l}
                         for f, t, l in sorted(bound, key=lambda r: (r[0], r[1], str(r[2])))],
        })
    return root, out_lanes, [{"file": h, "degree": d} for h, d in seat_held], notes, sizes


def cmd_domains(a):
    root, lanes, seat_held, notes, sizes = build_domains(a)
    scope_count = sum(len(l["files"]) for l in lanes) + len(seat_held)

    if a.json:
        print(json.dumps({"root": str(root), "scope_count": scope_count,
                          "lanes": lanes, "seat_held": seat_held, "notes": notes},
                         indent=1))
        return 0

    print(f"domains: {root}")
    print(f"{scope_count} file(s) in scope · {len(lanes)} lane(s) · "
          f"{len(seat_held)} seat-held")
    print("a boundary line means: you may READ that file, never edit it.")
    for l in lanes:
        print(f"\nlane {l['id']} · {len(l['files'])} file(s) · {l['bytes']:,} B")
        for f in l["files"]:
            print(f"  {f}")
        for b in l["boundary"]:
            tag = b["lane"] if b["lane"] == "seat-held" else f"lane {b['lane']}"
            print(f"  boundary: {b['from']} -> {b['to']} ({tag})")
    if seat_held:
        print(f"\nseat-held · {len(seat_held)} file(s) — in no lane, the seat's to edit")
        for h in seat_held:
            print(f"  degree {h['degree']:<4} {h['file']}")
    if notes:
        print("\nnotes")
        for n in notes:
            print(f"  note: {n}")
    print("\nthe graph knows LINKS, not SEMANTICS: two files that never reference each "
          "other can\nstill collide at runtime. The tool proposes, the seat disposes.")
    return 0


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(
        prog="graph.py", description="Obsidian-style file graph, built by script.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan a project into graph/graph.{json,html}")
    s.add_argument("--root", default=".")
    s.add_argument("--out", default="graph", help="output dir (relative to --root unless absolute)")
    s.set_defaults(f=cmd_scan)

    for verb, fn in (("register", cmd_register), ("unregister", cmd_unregister)):
        p = sub.add_parser(verb, help=f"{verb} a project root in the cross-project registry")
        p.add_argument("--root", default=".")
        p.add_argument("--registry", default=None)
        p.set_defaults(f=fn)

    a = sub.add_parser("all", help="merge every registered project into one PM view")
    a.add_argument("--registry", default=None)
    a.add_argument("--out", default=str(DEFAULT_ALL_OUT))
    a.add_argument("--per-project-cap", type=int, default=300,
                   help="max nodes kept per project (estate always kept; 0 = no cap)")
    a.set_defaults(f=cmd_all)

    rv = sub.add_parser("river", help="draw the journey: findings + COORD as a river")
    rv.add_argument("--root", default=".")
    rv.add_argument("--out", default="graph/river.html",
                    help="output .html (json written beside it) or a directory")
    rv.add_argument("--session", default=None, help="only this session/lane")
    rv.add_argument("--cap", type=int, default=RIVER_CAP,
                    help=f"max records drawn, newest kept (default {RIVER_CAP}; 0 = all)")
    rv.add_argument("--now", action="store_true",
                    help="stamp with wall-clock time instead of the newest input ts "
                         "(breaks byte-identical re-renders)")
    rv.add_argument("--open", dest="open", action="store_true", help="open the page after writing")
    rv.add_argument("--no-open", dest="open", action="store_false")
    rv.set_defaults(f=cmd_river, open=False)

    jr = sub.add_parser("journey", help="draw the door: router shapes, intake routes, chains")
    jr.add_argument("--root", default=".")
    jr.add_argument("--out", default="graph/journey.html",
                    help="output .html (json written beside it) or a directory")
    jr.add_argument("--open", dest="open", action="store_true", help="open the page after writing")
    jr.add_argument("--no-open", dest="open", action="store_false")
    jr.set_defaults(f=cmd_journey, open=False)

    q = sub.add_parser("links", help="what links to and from a file (last scan)")
    q.add_argument("path")
    q.add_argument("--root", default=".")
    q.add_argument("--out", default="graph")
    q.set_defaults(f=cmd_links)

    o = sub.add_parser("orphans", help="files with no edges either way (last scan)")
    o.add_argument("--root", default=".")
    o.add_argument("--out", default="graph")
    o.add_argument("--limit", type=int, default=200, help="0 = no limit")
    o.set_defaults(f=cmd_orphans)

    st = sub.add_parser("stale", help="files untouched for N+ days (last scan)")
    st.add_argument("--root", default=".")
    st.add_argument("--out", default="graph")
    st.add_argument("--days", type=int, default=90)
    st.add_argument("--limit", type=int, default=200, help="0 = no limit")
    st.set_defaults(f=cmd_stale)

    dm = sub.add_parser(
        "domains", help="partition files into disjoint lanes along the link graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""Partition a set of files into non-overlapping lanes, so work can be
handed out without two lanes being given the same file.

A lane is a CONNECTED COMPONENT of the link graph restricted to the scoped
files: files that reference each other move together. A component is NEVER
split — splitting one manufactures the shared-file collision this command
exists to prevent.

ORDER IS LAW — hubs out FIRST, components SECOND. In-scope degree is computed
on the full scoped graph, hubs are extracted to seat_held, and only then are
components computed on the remainder. The other order is fatal: in a real repo
everything is transitively linked through manifests and shared config, so
components-on-the-full-graph return ONE giant component — and since components
are never split and --lanes only merges, the command would be a no-op on
exactly the trees it exists for.

HUB RULE: a scoped file whose in-scope degree (distinct neighbours, either
direction) is at least max(4, 3 x median in-scope degree) is pulled out of every
lane into seat_held. The median is statistics.median over every scoped file's
degree. Files everyone links to belong to no lane — they are the seat's
contracts (think manifests, shared config). One pass, no re-thresholding.

--lanes N: more components than N and the smallest (by total bytes) are merged
pairwise until N remain; fewer components than N and you get what exists plus a
note. Never padded. A merged lane is a UNION of components — LANE != DOMAIN —
and every merged lane says so in notes[].

Scope (exactly one): --paths takes files and directories (a directory expands
to the tracked files under it; a named path that is not in the tree is fatal and
named); --changed reads `git status --porcelain` (a rename reports its NEW side,
deletions are dropped and noted); --all takes the whole listing. An empty scope
exits 2 — a silent lanes:[] is the moment a seat shrugs and hand-partitions from
memory instead.

The graph is built IN MEMORY from the same extraction `scan` uses — no prior
graph/graph.json is needed and none is written, so this runs on a fresh clone.
Outside a git repo it exits 2: there is no tracked set to partition.

--json emits {root, scope_count, lanes[{id, files, bytes, boundary[{from, to,
lane}]}], seat_held[{file, degree}], notes[]}; a boundary's `lane` is the
integer lane id of the other end, or the string "seat-held".

THE GRAPH KNOWS LINKS, NOT SEMANTICS: two files that never reference each other
can still collide at runtime. The tool proposes, the seat disposes.""")
    dm.add_argument("--root", default=".")
    scope = dm.add_mutually_exclusive_group(required=True)
    scope.add_argument("--paths", nargs="+", metavar="P",
                       help="explicit files/dirs to partition")
    scope.add_argument("--changed", action="store_true",
                       help="the working tree's changed paths (git status)")
    scope.add_argument("--all", action="store_true", help="every file in the listing")
    dm.add_argument("--lanes", type=int, default=None,
                    help="target lane count (merge smallest-first; never splits)")
    dm.add_argument("--json", action="store_true", help="machine-readable output")
    dm.set_defaults(f=cmd_domains)

    args = ap.parse_args()
    raise SystemExit(args.f(args) or 0)


if __name__ == "__main__":
    main()
