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

Honesty: the graph shows REFERENCES that a text scan can see — not importance.
A disconnected node is information (nothing in the repo points at it), not garbage.
"""
import argparse
import json
import os
import pathlib
import posixpath
import re
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

    args = ap.parse_args()
    raise SystemExit(args.f(args) or 0)


if __name__ == "__main__":
    main()
