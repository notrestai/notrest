---
name: graph
description: An Obsidian-style file graph for any project — a script walks the repo and renders a self-contained, force-directed HTML graph of every file and the references between them (wikilinks, markdown links, imports, requires, sourced scripts, estate pointers), at ZERO model tokens. Use on /graph, "file graph", "project graph", "map the files", "show me the graph", "what links to this file", "connect the projects", "all projects graph". Also registers projects into a cross-project registry so one PM session can hold the merged map of every project at once. The scanner reads the files; the model never has to.
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

**Open the HTML before saying it works.** A scan that writes a file is not a graph that
draws. Open `graph/graph.html` (or the merged page) in a real browser, confirm nodes render
and the counts in the header match the summary line, then report. If you cannot open a
browser, say the page was written but not rendered — never claim a view you did not see.

## Self-check before finishing

- The scan was run by the script this turn, and its summary line (nodes, edges, listing
  mode, skipped) is in the transcript.
- The page was actually opened, or the report says it wasn't.
- Any claim about what links to what came from the graph data or the file itself — not from
  a guess about how the project is probably organised.
- If you called a node orphaned, you said where you looked and what wouldn't show up there.
- If you registered a project, the owner said yes.

## Chains

`archivist` = what the estate *says* (dossiers, the agent ledger) · **graph** = how it
*connects* (files and references) · `recap` = what happened *over time*. Run the scan at
`/sessionend` so the next session's oracle opens on a current map; feed a suspicious cluster
to `/critic`, a tangle to `/stepbystep`, and an unfamiliar corner to `/explainer`.
