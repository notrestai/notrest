---
name: graph
description: An Obsidian-style file graph for any project — a script walks the repo and renders a self-contained, force-directed HTML graph of every file and the references between them (wikilinks, markdown links, imports, requires, sourced scripts, estate pointers), at ZERO model tokens, then OPENS IT. Use on /graph, "file graph", "project graph", "map the files", "show me the graph", "open the graph", "what links to this file", "connect the projects", "all projects graph". Default behaviour is scan-then-open with no questions asked; also registers projects into a cross-project registry so one PM session can hold the merged map of every project at once. The scanner reads the files; the model never has to.
---

# graph — how this project connects

`archivist` says what the estate *knows*. This says how it *connects*: one page, every file
as a node, every reference the scanner can see as an edge — the Obsidian graph view, for a
codebase, built by a script.

**The economics are the point.** The model never reads files to build this graph — `scan`
does, and the model only reads a one-line summary (or opens the page). Same pattern as the
SubagentStop hook and archivist's `index.py`: the machine writes, the session pays nothing.

Script: `scripts/graph.py` (python3 stdlib only). Output: `<root>/graph/graph.json` (the
data) and `<root>/graph/graph.html` (the viewer — regenerated on every scan, data inlined,
opens over `file://` with zero network requests).

## `/graph` — the default run: SCAN, then OPEN. No questions.

Invoking this skill means "show me the graph". Do all three steps, in order, without
asking anything. Ask only if a step fails.

### (a) Refresh first — always

Resolve the target, then scan:

- **No argument** → the current directory's git root: `git rev-parse --show-toplevel`
  (not a git repo? use the cwd).
- **A path argument** (`/graph ~/code/thing`) → that path is the target.
- **The argument `all`** (`/graph all`) → skip the single-project scan; build the merged
  cross-project view with `graph.py all` instead (see *The PM pattern*), and open **that**
  page in step (b). Its file is `~/.claude/oracle-graph/all-projects-graph.html`.

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"     # or the given path
python3 <skill>/scripts/graph.py scan --root "$ROOT"
```

A scan is script-only and costs no context — never skip it to "save time", and never
open a stale page instead.

### (b) Open the result — always, environment-aware

Walk this list top-down and take the **first** case that matches your environment:

1. **Claude Code desktop with the browser pane** (you have preview/browser-pane tools) —
   **serve it over localhost, don't hand the pane a `file://` URL.** The pane renders
   `file://` pages outside the project as *static snapshots*: the HTML paints, the
   JavaScript never runs, and a force-directed graph with dead JS is a blank box. Serve
   the directory holding the page, then open `http://127.0.0.1:<port>/…`:

```bash
DIR="$ROOT"; PAGE="graph/graph.html"          # /graph all: DIR=~/.claude/oracle-graph
                                              #             PAGE=all-projects-graph.html
for PORT in 8790 8791 8792 8793 8794 8795 8796 8797 8798 8799; do
  (cd "$DIR" && python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &)
  sleep 1
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/$PAGE" && break
done
echo "http://127.0.0.1:$PORT/$PAGE"           # <- open THIS in the browser pane
```

   A taken port is not a failure — the loop moves to the next one (8790…8799), and the
   `curl` check means you only ever hand the pane a URL that is *proven* to serve the page
   (it also harmlessly reuses a server already serving it). The server is throwaway and
   bound to loopback only; kill it when you're done (`pkill -f "http.server $PORT"`) or
   leave it — either is fine, just say which.
2. **macOS, no browser pane (plain CLI)** — `open "$ROOT/graph/graph.html"`. A real
   browser runs `file://` JavaScript fine; the page is self-contained, so no server is
   needed.
   (Linux equivalent: `xdg-open`.)
3. **Anything else** (headless, container, remote shell, plain chat) — print the absolute
   path and say: *"open this in any browser"*. Do not pretend it was displayed.

### (c) Close with one line

Report: **nodes · edges · the `generated` stamp · which viewer path you used** (served on
`127.0.0.1:<port>` / opened locally / path printed only). One line, then stop — the page
is the deliverable, not a description of it.

## Commands

Installed as a plugin the script lives at
`${CLAUDE_PLUGIN_ROOT}/skills/graph/scripts/graph.py` (loose installs: `.claude/skills/…`
or `~/.claude/skills/…`). `<graph-skill>` below means that path.

- **Scan a project:** `python3 <graph-skill>/scripts/graph.py scan --root <project> [--out graph]`
  In a git repo it lists tracked + untracked-not-ignored files (`.gitignore` respected for
  free); otherwise it walks, skipping `.git/`, `node_modules/`, `venv/`, `dist/`, `build/`
  and friends. Binaries are nodes but never read. Prints
  `…/graph.html: N nodes, M edges (git|walk listing, K skipped)`.
- **Register for the cross-project view:** `python3 <graph-skill>/scripts/graph.py register --root <project>`
  Appends the absolute path to `~/.claude/oracle-projects.txt` (idempotent; `--registry <file>`
  to point elsewhere). `unregister --root <project>` removes it.
- **Merge every registered project:** `python3 <graph-skill>/scripts/graph.py all [--registry <file>] [--out <dir>] [--per-project-cap N]`
  Reads each registered root's `graph/graph.json`, colours each project as its own cluster
  with a hub node, adds cross-project edges, and writes `all-projects-graph.{html,json}` to
  `--out` (default `~/.claude/oracle-graph/`). Projects never scanned are counted and named
  in the summary, not silently dropped. `--per-project-cap` (default 300) keeps big projects
  legible: the estate is always kept, then the best-connected files.

Exit codes: 0 with a one-line summary on success, 2 on bad arguments (missing root, unknown
subcommand, empty registry). Unreadable files are skipped and counted, never fatal.

## What becomes an edge

| kind | from → to |
|---|---|
| `wikilink` | `[[note]]` in markdown |
| `link` | `[text](path)` in markdown, resolved relative to the file then the root |
| `import` | python `import x` / `from x import y`, JS/TS `import`/`require` of repo-relative paths |
| `source` | shell `source x.sh`, `bash x.sh`, `python3 x.py` on a repo script |
| `mention` | a path in prose or a comment that resolves to a real repo file (`CLAUDE.md` → `plugins/…/plugin.json`) |
| `transcript` | `COORD-AGENTS.md` → the agent transcript it points at (an **external** node — outside the repo) |
| `pair` | a `{topic}Dossier.md` → its `{topic}background.md` sibling |

Node colour is the type bucket: **estate** (`COORD*`, `CLAUDE.md`, `START-HERE`, `HANDOFF`,
`STATE`, `oracle-index.md`, `spend/`) purple · **docs** teal · **code** amber · **config**
grey · **other**/**external** muted. Node size is degree. Bare package imports
(`node_modules`, stdlib) are not edges — nothing in the repo to point at.

## The viewer

Force-directed canvas, no libraries, both themes legible (system preference + a light/dark
toggle). Hover a node for its path and link count; **click to pin it** and get a side panel
listing links out and links in (each row clicks through); drag a node, drag the background
to pan, scroll to zoom; the search box filters by substring (`n/N` shown, the rest dimmed);
`fit` re-frames, `re-layout` re-runs the physics and unpins everything.

## The PM pattern — one session, every project

Registration is one command per project, once. Then a dedicated session — call it the **PM
session** — runs

```
python3 <graph-skill>/scripts/graph.py all
open ~/.claude/oracle-graph/all-projects-graph.html
```

and holds the connected map of *every* registered project: clusters per project, the hub of
each, the cross-project edges. That session answers "what's where", "which projects share
this file", "what have we got running" without opening a single repo. Keep it honest by
re-scanning each project before a merge (`all` merges the last scan, not live files — the
`generated` stamp in the header tells you how stale it is).

Cross-project edges are deliberately conservative: an out-of-repo reference that lands
inside another registered project, and the same *distinctive* relative path present in a
few projects. Files that exist in every project by construction (`README.md`,
`package.json`, and the whole ORACLE estate — `CLAUDE.md`, `COORD.md`, `spend/ledger.md`)
are **excluded** — their co-presence is not a connection, and drawing it would wire every
project to every other one for nothing.

## Oracle wiring

`oracle` intake refreshes the scan on any project it opens (script-only, so it costs
nothing) and, the **first** time a project is scanned, offers once to register it for the
cross-project view. Registration is the owner's choice and never silent — a registry entry
means this project shows up in someone's PM map.

**The intake refresh is scan-only and silent — it never opens anything.** Nobody typing
"hey oracle" asked for a browser window. The scan-then-**OPEN** behaviour above belongs to
explicit `/graph` invocations only.

## Honesty rules

- **The graph shows REFERENCES a text scan can see — not importance, not architecture.** A
  file with 20 mentions is talked about a lot; that is all the graph claims.
- **A disconnected node is information, not garbage.** It means nothing in this repo points
  at it — could be an entry point, could be dead, could be referenced from outside the scan
  (a hook, a CI job, another repo). Say which you checked before calling anything dead.
- **Mentions are textual, not semantic.** A path inside a code fence, a changelog line, or a
  "don't use this" warning all produce the same edge. Read the line before drawing a
  conclusion from it.
- **The scan is a snapshot.** Counts move as the repo moves (a lane writing files right now
  changes them). Quote the `generated` stamp with any count you report.
- **Never hand-edit `graph/graph.json` or `graph/graph.html`.** Both are regenerated on
  every scan; edits are lost. Fix the repo, re-scan.
- The graph sees what the listing sees: in a git repo, ignored files are absent by design;
  outside git, the skip list hides dependency directories. Say which listing mode ran (the
  summary line prints it) when the absence of a file matters.

## Render gate

**Open the HTML before saying it works** — which is why opening is step (b), not an
optional extra. A scan that writes a file is not a graph that draws. Confirm nodes actually
render and the header counts match the summary line, then report. Two traps that have both
bitten:
- **A `file://` page in the browser pane is a static snapshot** — JS dead, canvas blank.
  Serve over localhost there (step (b1)). A screenshot of a blank canvas is not a render.
- **Check it at the size you're actually viewing**, not just the size it loaded at: the
  viewer re-sizes its canvas (CSS box, backing store and dpr transform together) on every
  viewport change, and that path is worth a glance when you change window size.

If you cannot open a browser, say the page was written but not rendered — never claim a
view you did not see.

## Self-check before finishing

- The scan was run by the script this turn, and its summary line (nodes, edges, listing
  mode, skipped) is in the transcript.
- The page was actually opened — no questions asked, no "want me to open it?" — or the
  report says plainly which environment case blocked it.
- Any claim about what links to what came from the graph data or the file itself — not from
  a guess about how the project is probably organised.
- If you called a node orphaned, you said where you looked and what wouldn't show up there.
- If you registered a project, the owner said yes.

## Chains

`archivist` = what the estate *says* (dossiers, the agent ledger) · **graph** = how it
*connects* (files and references) · `recap` = what happened *over time*. Run the scan at
`/sessionend` so the next session's oracle opens on a current map; feed a suspicious cluster
to `/critic`, a tangle to `/stepbystep`, and an unfamiliar corner to `/explainer`.
