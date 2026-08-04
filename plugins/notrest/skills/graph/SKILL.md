---
name: graph
description: "Two script-built views, self-contained HTML at zero model tokens, then OPENED: the FILE GRAPH (every file and reference — Obsidian for a codebase) and the RIVER (findings.jsonl + COORD volumes as a river toward the goal — side channels, backtrack loops, conflict rocks, milestone flags). Plus text queries over the last scan. Use on /graph, cockpit, \"project graph\", \"/graph river\", \"what links to this file\", \"orphans\", \"stale files\", \"all projects graph\"."
---

# graph — how this project connects, and how it got here

`archivist` says what the estate *knows*. This skill draws three things it cannot:

- **the file graph** — how the project *connects*: every file a node, every reference the
  scanner can see an edge. The Obsidian graph view, for a codebase.
- **the river** (`/graph river`) — how the work *moved*: the findings ledger and the COORD
  volumes as a river flowing left→right into the goal, with the side routes, the
  backtracks, the rocks it hit and the flags it passed.
- **the journey** (`/graph journey`) — how the harness *opens*: what a user types → the
  shape `router.sh` calls it → the verb that runs → what that verb hands off to, with the
  skills nothing routes to drawn in their own band instead of hidden.

**The economics are the point.** The model never reads files to build either view — the
script does, and the model reads a one-line summary (or opens the page). Same pattern as
the SubagentStop hook and archivist's `index.py`: the machine writes, the session pays
nothing.

> **Token-efficiency law (owner, 2026-07-25).** Renders are script-built at zero model
> tokens — the model never hand-draws a diagram; a new visualization is a new script
> subcommand (the compile doctrine applied to graphs).

Its teeth: layout is deterministic, there are no external or vendored JS libraries (inline
hand-rolled SVG/CSS only), and **identical inputs render a byte-identical page** — every
list is sorted and nothing reads the clock, so the page is stamped with the newest *input*
timestamp unless you pass `--now`. If a re-render produces a different file from the same
ledger, that is a bug in this script, not noise.

Script: `scripts/graph.py` (python3 stdlib only). Output: `<root>/graph/graph.json` +
`graph.html` (the file graph), `<root>/graph/river.json` + `river.html` (the river) and
`<root>/graph/journey.json` + `journey.html` (the journey) — each regenerated on every
run, data inlined, zero network requests.

**Router shape:** `file-graph`

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

## `/graph river` — the journey, not the map

`/graph river` (or "show me the river") draws the *work*, not the files. Same three steps
— build, open, one line — with `river` in place of `scan`.
(Asking how the project got to where it is belongs to **`/recap`**, which answers it in
prose; a river is the picture you reach for once you want the *shape* of the trail.)

```bash
python3 <graph-skill>/scripts/graph.py river --root "$ROOT"     # → graph/river.{json,html}
```

**What it reads.** `archive/findings.jsonl` (append-only, one JSON record per line:
`id · ts · session · skill · kind · ask · statement · evidence[] · relation · links[] ·
status`) — plus, **always**, the COORD ledger volumes and `COORD-AGENTS.md`. The COORD
overlay is not a fallback: ships, gates and corrections fly as flags on the bank of every
river, because the ledger is where this estate already records its milestones.

**How the water is drawn.**

| the shape | what it means |
|---|---|
| the wide main channel | `relation: toward` — the flow that got to the goal |
| a side channel below | `relation: lateral` — a route taken off the main line |
| an explicit fork | `kind: side-route` — always opens its own channel |
| a channel that curves back in | a later `toward` record links it: **the side route rejoined** |
| a channel that tapers and stops | nothing ever linked it again: **dead end**, marked as one |
| an upstream loop arrow | `relation: back` — a backtrack to something already passed |
| a red rock in the channel | `kind: conflict`, or any record whose effective status is `refuted` |
| a long-dashed red arrow *into* a stone | **rests on refuted** — that stone is live, but it cites ground a refutation took out |
| a stone | every record — every stone turned, whether or not it led anywhere |
| a flag on the top bank | a COORD ledger line: ship · gate · correction |
| a tick on the bottom bank | a `COORD-AGENTS.md` entry — which lane was running when |
| a ruled sheet hanging below the tick row | a **commission**: that lane's exact prompt is banked on disk, and the card shows it |
| the green bank on the right | the GOAL the river runs toward |

**Effective status is link-walked, not declared.** A later record that links an older one
and says it *supersedes* or *refutes* it overrides that record's own `status` (refuted
outranks superseded). Superseded stones fade and strike through; refuted ones become rocks.
Hover any glyph for its ask → statement → evidence refs with their honesty labels; click to
pin the card.

**RESTS-ON-REFUTED — the rule, pinned.** *A live record whose links contain an effectively
refuted id rests on refuted ground.* The refutation kills the finding; it does not
automatically kill everything built on it — but it does mean somebody has to look. So the
river draws the inbound edge from the refuted source to that stone as a **long-dashed red
arrow** (its own edge kind `rests`, distinct from the rock glyph and from the short-dashed
`refute` arc), rings the stone in dashed red, and the hover card opens with
`RESTS-ON-REFUTED <id>`. The count is in the legend and in `counts.rests_on_refuted`.

Three things it deliberately does **not** do:
- **It is one hop, not transitive.** A record resting on a record that rests on refuted
  ground is not flagged — the rule reads a record's own `links`, and a transitive claim
  about ground nobody cited would be the river inventing a dependency.
- **The refuter is never resting.** A record that refutes X links X; that is an attack, not
  a foundation, and it is excluded.
- **It is not a verdict.** "Rests on refuted" says the citation graph now has a hole in it,
  not that the conclusion is wrong. Read the record before you retract anything — feeding it
  to `/refuter` is the honest next move.

`archivist`'s finding-store track implements the same rule over the same records, so a
stone flagged here and a record flagged there are the same claim about the same ground.

**Commissions are visible, or the value is a slogan (owner core value, 2026-07-27).** What a
lane was *actually asked* must be readable without asking the seat — otherwise a seat that
narrows a commission can narrow it invisibly, and at fan-out scale nobody would ever know.
The chain is by construction, and the river is only its last link: the **SubagentStop hook
banks** each lane's first user-role message verbatim to `briefs/agent-<id>.md` → the
**receipt points** at it (` | brief: briefs/agent-<id>.md` on the `COORD-AGENTS.md` line) →
**the river marks it**. A tick whose pointer resolves to a real file inside the root becomes
a **commission**: a ruled-sheet glyph on its own row below the tick line, on a stem back to
the waterline, with a purple `COMMISSIONS — N lanes whose exact prompt is banked on disk`
banner beside it and a legend entry; its hover card carries the first ~200 characters of the
prompt (read from the file at render time, zero model tokens as ever) plus the full path to
the rest. Everything else stays a plain tick and says why, in the card's own words: a
receipt with **no pointer** reads *"not banked (pre-v3.13 lane)"*, a pointer whose **file is
gone** names the dead path. `counts.commissions` and the `N/M lanes commissioned` figure on
the summary line are the number to quote. Two refusals hold this honest: the brief is never
summarized (it is the prompt or it is nothing), and a pointer that resolves **outside the
root is refused unread** — `COORD-AGENTS.md` is machine-written text, not a capability.

**No findings ledger? It degrades, and says so.** With no `archive/findings.jsonl` the river
is built from the COORD lines themselves — every node marked `inferred: true`, its kind and
relation read off the line's own words by heuristic, its links chronological rather than
authored, and the legend saying exactly that on the page. In that mode the river never
claims a supersession: synthesized links are not evidence of one.

Flags: `--session <lane>` (one lane's river), `--cap N` (default 500 records, newest kept —
the page says "showing the last N of M"), `--out <file.html>`, `--open` / `--no-open`
(default: write only, then open with the environment-aware door above), `--now` (stamp with
clock time instead of the newest input — breaks byte-identical re-renders).

## `/graph journey` — the door, not the work

The river draws what the *work* did. `/graph journey` draws what the *harness* does when
somebody types something — the front door nothing else in the suite has ever rendered:

```bash
python3 <graph-skill>/scripts/graph.py journey --root "$ROOT"   # → graph/journey.{json,html}
```

Three columns, left to right: **what someone types** → **the shape `router.sh` calls it**
→ **the skill that runs**, then chain arrows from each skill to the verbs its own SKILL.md
hands off to. Skills nothing routes to are drawn in a **BY NAME ONLY** band at the bottom —
that band is the most useful thing on the page, because it names every verb a user can only
reach by knowing it exists.

**What it reads — three authorities, named on the page.**

| source | what it contributes |
|---|---|
| `hooks/router.sh` | the `SKILL=`/`SHAPE=` case arms, in table order (order *is* precedence — first match wins). Same parse `eval.py`'s ROUTER check uses. |
| `skills/oracle/SKILL.md` | the intake routing bullet — `phrase → /verb` pairs, drawn as green dashed pills that bypass the shape column, because the hook never fires them; the intake conversation does |
| every `skills/*/SKILL.md` | the Chains / Finishing-up section, mined for explicit `` `/verb` `` references → the chain arrows |

**The chain arrows are best-effort text parsing, and the page says exactly where it failed.**
Only an explicit `/verb` reference inside a Chains / Finishing-up section becomes an arrow. A
skill with no such section is *named* in the notes; a skill with a section whose hand-offs are
written in prose ("researcher / marketresearcher → draft") is *also named*, and draws nothing.
A guessed arrow would be this script inventing a hand-off nobody wrote.

**The stamp is the commit, not the clock and not an mtime.** `river` stamps from the newest
input timestamp; that would be wrong here, because the inputs are tracked files whose mtimes
every clone rewrites — two checkouts of the same commit would stamp differently. `journey`
stamps from `git rev-parse --short HEAD`, suffixed `+dirty` when tracked files are modified,
and says `(no git HEAD)` on the page when git is unavailable. Touching an input does not
change one byte of the render; editing one does.

Flags: `--root`, `--out <file.html>` (default `graph/journey.html`; json written beside it),
`--open` / `--no-open` (default: write only, then open with the environment-aware door above).
Exit 2 if no directory holding `skills/` can be found under the root.

## `/graph cockpit` — one page, always on

The other three verbs draw a *moment*. The cockpit is the thing you leave open: a local
page that re-reads the estate's own files every five seconds, so the work a session is
doing right now shows up on a screen instead of in a scrollback.

```bash
python3 <graph-skill>/scripts/cockpit.py serve --root "$ROOT"      # → http://127.0.0.1:8788/
```

**Serve, then open — the same environment-aware door as the river,** with one simplification:
the cockpit *is* a server, so there is no `file://` trap to route around. Hand the browser
pane `http://127.0.0.1:8788/` directly; on a plain macOS CLI the command opens it for you
(`--no-open` to suppress). **Port 8788 is reserved for it** and chosen to stay clear of
`render-check.sh`'s 8790-8799, so a cockpit can stay up while a render is being gated on the
same machine. It binds **127.0.0.1 only, always** — there is no flag to widen that. Stop it
with Ctrl-C in the shell that owns it, or kill the pid that shell reports.

### Always-on — surfacing it is the seat's job, not the owner's to remember

A window nobody opens is not a window. The cockpit did exactly what the owner wanted for
weeks and **nothing surfaced it**: no session opened it, and no project remembered wanting
it. **Presence is not display** — the same law as `/notrest`'s *presence is not
establishment*, one floor up. The fix is an opt-in the project states once and the harness
carries from then on:

**(i) Opt in — once, by the owner.**

```bash
python3 <graph-skill>/scripts/cockpit.py serve --root "$ROOT" --always --no-open &
```

`--always` writes `<root>/graph/.cockpit-always` — a one-key JSON marker holding the
**port actually bound** (not the one requested; those differ the moment a port is taken).
It is written *after* the bind, atomically. `serve` **without** `--always` never touches an
existing marker: opting in is deliberate, and so is opting out. The marker is **per-machine
state, not shared history** — this repo's `.gitignore` already ignores `/graph/`, and a
user project that opts in should do the same (`/graph/` anchored, so it never swallows a
skill directory of that name). Nothing enforces that; it is yours to add.

**(ii) At every session start — probe, and start it if it is down.** The SessionStart hook
prints one line when the marker is there. It only *echoes*: a hook that probes ports or
spawns servers is a hook that can hang a session start. The probing is the seat's:

```bash
python3 <graph-skill>/scripts/cockpit.py status --root "$ROOT"
#   exit 0 → running (the URL is on the line)
#   exit 5 → opted in and DOWN  → start it:
#            python3 <graph-skill>/scripts/cockpit.py serve --root "$ROOT" --port <p> --always --no-open &
#   exit 6 → never opted in     → say nothing, do nothing
```

`status` probes `/health` on loopback with a half-second timeout, so it can never stall an
intake. If the server answers but reports a **different root**, the line says so — some
other project's cockpit holds that port, and the seat should notice rather than report a
window onto someone else's estate as this project's.

**(iii) Then OPEN it — for the owner, not for yourself.** In an environment with the
**built-in browser pane**, hand the pane the printed `http://127.0.0.1:<port>/` and leave
it open. Otherwise use the system opener (plain `serve` does it for you; `--no-open`
suppresses it). This step is the whole point: the owner should find the estate already on
screen, not discover later that a window they asked for has been sitting closed.

**(iv) Stopping is the owner's call, always.** Kill the process that owns the port, and
`rm <root>/graph/.cockpit-always` to opt out. The harness never stops a cockpit, never
removes the marker, and never starts one in a project that has not opted in.

**THE WINDOW-NOT-CONTROL-PANEL LAW.** Every route is a read except exactly one:
`POST /room/<name>`, which posts a line to a chatroom by shelling to chatroom's own
`room.py post`. **The no-secrets screen is chatroom's, and the cockpit neither pre-screens
nor overrides it** — a refusal comes back as room.py's own exit 5 (HTTP 422) with nothing
written. There is no endpoint that edits a ledger, bumps a version, runs a skill, appends a
finding, or repairs anything. If you want the estate changed, a session changes it; the
cockpit watches. A `POST` to any other path is a 404 on purpose.

**Connect your Claude to it.** Nothing plugs in — that is the design. Sessions already write
the estate (COORD lines, the agent ledger with its banked commissions, findings, the spend
ledger, watch rows); the cockpit just reads those files. So a session running in this repo
appears in the window within five seconds without knowing the window exists. The two-way wire
is the **chatroom panel**: a session that joins a room (`/chatroom`) and a person watching the
cockpit are in the same room, and the mail slot is how the watcher answers.

| route | serves |
|---|---|
| `GET /` | the page (built at startup, also written to `<root>/graph/cockpit.html`) |
| `GET /data/coord.json` | the active COORD volume's tail (40 lines, the river's own parser) |
| `GET /data/agents.json` | `COORD-AGENTS.md` tail (30) with each commission pointer resolved |
| `GET /data/briefs/<id>.json` | one banked commission, verbatim — root-contained |
| `GET /data/spend.json` | `spend.py report --json`, else the captured verdict line |
| `GET /data/pulse.json` | the newest `[pulse]` line already in COORD (never runs a pulse) |
| `GET /data/watch.json` | watchlist rows, `watch.py due`, the newest drift block |
| `GET /data/library.json` | the shelf's newest concepts generation + registered projects |
| `GET /data/findings.json` | `index.py track --json` |
| `GET /data/version.json` | manifest version + git HEAD (`+dirty` when it is) |
| `GET /pic/{river,journey,graph}.html` | the renders, rebuilt only when their inputs moved |
| `GET /room/<name>` | a room's tail |
| **`POST /room/<name>`** | **the only write** — `{handle, text}` → `room.py post` |
| anything else | 404, with the route list |

**The renders stay deterministic; the cockpit is live — and the difference is deliberate.**
`/pic/*` shells to `graph.py`, whose byte-identical law is untouched: same inputs, same page.
A render is regenerated **only** when its input files' mtimes are newer than the output, and
never more than once per **5 seconds** (a browser reloading in a loop must not become a render
loop); `?force=1` overrides both. The cockpit *page* reads the wall clock — it polls every 5s
— because a live monitor that cannot say how stale it is would be worse than none. **This does
not dilute the byte-identical law:** the law is about *renders*, and the renders it serves are
still deterministic. The staleness stamp is taken from the `X-Cockpit-Generated` **response
header**, never the browser's clock, so the page reports the server's read time — a viewer
with a skewed clock cannot make the page lie about freshness.

**What the page shows — five views, one at a time (the owner's redesign, 2026-08-04).**
The bar holds exactly four controls: `river` · `file graph` · `coord`, and `rebuild`.
Whatever is selected owns the entire viewport under that bar. **The `journey` and `lanes`
tabs were removed by the owner** (*"the journey tab is shit literaly not needed also with
the lanes not needed"*): the journey **render still exists** and stays reachable at
`/pic/journey.html` and through `/graph journey` — the cockpit simply no longer surfaces
it — and commission transparency lives where it already lived, on the river's commission
sheets, in `COORD-AGENTS.md` and in `briefs/`.

| view | what it is |
|---|---|
| river · file graph | the picture, full height, in the stage iframe (loaded `?embed=1`, legend folded); a small **open full page ↗** sits in the picture's own corner |
| coord | the **COORD tail** as the whole view — newest first, ship/gate/correction flags, its own scroll |

`rebuild` acts on the active *picture* and is hidden on the two feed views, where there is
nothing to rebuild. Theme follows `prefers-color-scheme`; polling is always on at 5s.

**What left the page, and why.** The status chips (version, pulse, spend, watch, lanes), the
title, the live toggle and the theme button are gone, and so are the library, chatroom,
findings and watch panels. The owner's verdict on the old page was *"how is this a graph
readable?"* — the chrome was reporting the harness to the seat while the picture it existed
to show was squeezed into a corner. **The ledgers already hold all of it**; the window now
shows the work, not the paperwork. This is a **UI removal only**: every `/data/*` route and
the `POST /room/<name>` mail slot are still served, still tested, and still available to any
API consumer.

**The staleness law survives the redesign.** A live monitor that cannot say how stale it is
would be worse than no monitor, so the server's `X-Cockpit-Generated` read time is still on
the page — one faint line in the bottom-right corner instead of a chip in the bar. Still the
server's stamp, never the browser's clock.

**Honesty about the lane chip.** It counts lanes that **finished** in the last hour, not lanes
running: the agent ledger is written at `SubagentStop`, so a lane still working is in no file
the cockpit can read. The chip's tooltip says exactly that. The file-graph picture's rebuild
trigger is the **git index** plus two directory mtimes, not a full repo walk — too expensive
per request; use `rebuild` (`?force=1`) after an untracked edit you want reflected.

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

- **Draw the river:** `python3 <graph-skill>/scripts/graph.py river --root <project> [--session S] [--cap N] [--out graph/river.html] [--open|--no-open] [--now]`
  Prints `…/river.html: N records · C channels (M merged, D dead-end) · R rocks (K resting on refuted) · B backtracks · F milestones · mode=…`,
  then one `note:` line per honesty note (degrade mode, cap, unparseable ledger lines).
- **Open the cockpit:** `python3 <graph-skill>/scripts/cockpit.py serve --root <project> [--port 8788] [--no-open] [--always]`
  A loopback-only live window over the estate. Prints the URL, the page path, the bind, the
  route list and the stop instruction, then serves until Ctrl-C. Reads everything; writes
  exactly one thing, a chatroom post, through chatroom's own screened `room.py post`.
  `--always` additionally writes the opt-in marker `graph/.cockpit-always` with the bound port.
- **Is the opted-in cockpit up?** `python3 <graph-skill>/scripts/cockpit.py status [--root <project>]`
  One line — URL plus running / down / unopted — and a typed exit: **0** running · **5**
  opted in but down (start it) · **6** never opted in (say nothing). Reads the marker and
  probes `/health` on loopback with a half-second timeout. Writes nothing, ever.
- **Draw the journey:** `python3 <graph-skill>/scripts/graph.py journey --root <project> [--out graph/journey.html] [--open|--no-open]`
  Prints `…/journey.html: N skills · S router shapes · P phrases (R router, I intake) · C chain arrows · B by name only · stamp=<commit> (git-head)`,
  then one `note:` line per disclosure (no router, no chains section, prose-only hand-offs,
  a dirty tree, a missing git HEAD).

### `domains` — the lane boundaries, computed instead of reasoned

```bash
python3 <graph-skill>/scripts/graph.py domains --root <project> \
  (--paths P1 P2 … | --changed | --all) [--lanes N] [--json]
```

**When.** Before dispatching a swarm. `agentswarm` says "scope the lanes by domain" and
"split along file boundaries" — this computes that split from the link graph instead of the
seat reasoning about dependencies by hand every build. Output is a lane per domain, a file
list per lane, and `boundary:` lines that paste straight into a commission.

- **Scope, exactly one flag.** `--paths` takes files and directories (a directory expands to
  the tracked files under it); `--changed` reads `git status --porcelain` (a rename reports
  its **new** side; deletions are dropped and named); `--all` takes the whole listing.
- **Lanes are connected components** of the link graph over the scoped set. A component is
  **never split** — splitting one manufactures the shared-file collision the command exists
  to prevent. `--lanes N` merges the smallest components (by bytes) until N remain; with
  fewer components than N you get what exists and a note. Never padded.
- **Hubs out first, components second.** In-scope degree is computed on the full scoped
  graph, hubs are pulled into `seat_held`, and only then are components computed on the
  remainder. The other order is fatal: everything in a real repo is transitively linked
  through manifests, so components-first returns one giant lane and the command is
  decorative.
- **Hub rule:** in-scope degree ≥ `max(4, 3 × median in-scope degree)`. Files everyone links
  to belong to no lane — they are the seat's own contracts (manifests, shared config).
- **No prior scan needed.** The graph is built in memory from the same extraction `scan`
  uses; nothing is read but the scoped files and nothing is written. It runs on a fresh
  clone.
- **Exit 2** on: no scope flag, a named path that is not in the tree (it is **named** — this
  command does not partition fictions), a non-git root, and an **empty scope**. A silent
  `lanes: []` is the moment a seat shrugs and hand-partitions from memory instead.

`--json` emits `{root, scope_count, lanes[{id, files, bytes, boundary[{from, to, lane}]}],
seat_held[{file, degree}], notes[]}`; a boundary's `lane` is the other end's integer lane id
or the string `"seat-held"`.

> **The honest limit: THE GRAPH KNOWS LINKS, NOT SEMANTICS.** Two files that never reference
> each other can still collide at runtime — a shared convention, a hook that fires on both,
> two lanes editing different files that must agree. A boundary line is a *read-only*
> instruction, not a proof of independence, and a merged lane (`--lanes N`) is a **bundle of
> unrelated domains**, not one — every merged lane says so in `notes`. **The tool proposes,
> the seat disposes:** read the partition, then decide.

### Queries over the last scan

These answer from `graph/graph.json` — the scan's own output. They never re-derive it and
never pretend to be live: every answer ends with the `generated` stamp it came from. If
there is no scan yet they say so and exit 2 (run `scan` first).

- **`links <path>`** — what this file points at and what points at it, by edge kind. Takes
  an id, a repo-relative path, an absolute path inside the root, or a unique basename; an
  ambiguous name lists the candidates and exits 2 rather than guessing.
- **`orphans`** — nodes with no edges either way. Ends with the honest reading: no edge
  means nothing in *this repo's text* points at it — an entry point, a hook target and dead
  code look identical from here.
- **`stale [--days N]`** (default 90) — files untouched for N+ days, oldest first, with the
  caveat that mtime is the filesystem's: a fresh clone rewrites every one of them.

Both take `--limit N` (default 200, `0` for all).

Exit codes: 0 with a one-line summary on success, 2 on bad arguments (missing root, unknown
subcommand, empty registry, no scan data, unresolvable path). Unreadable files are skipped
and counted, never fatal.

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
- **A `domains` partition is a proposal about FILES, not about work.** It proves no two
  lanes were handed the same file; it cannot see a shared convention, a hook that fires on
  both, or two unlinked files that must agree at runtime. Never report a partition as
  "the lanes are independent" — report it as "no lane shares a file", which is all it says.
- **The scan is a snapshot.** Counts move as the repo moves (a lane writing files right now
  changes them). Quote the `generated` stamp with any count you report.
- **Never hand-edit the six generated files** (`graph.json`/`graph.html`,
  `river.json`/`river.html`, `journey.json`/`journey.html`). All are regenerated on every
  run; edits are lost. Fix the source, re-run.
- **The journey draws what the files SAY, not what the harness DOES.** A shape on the page
  means `router.sh` has an arm for it, not that the arm ever fires on real prompts; a chain
  arrow means a SKILL.md names that verb in its hand-off section, not that anyone follows
  it. Never quote the journey as evidence of runtime behaviour — `eval`'s ROUTER check is
  what proves the router is wired at all.
- **"By name only" is a statement about the routing table, not about a skill's worth.** It
  means nothing in `router.sh` or oracle's intake bullet points there — which is the correct
  design for `/eval`, `/spend`-style instruments and for anything a user should invoke
  deliberately. Read the band as a list of doors that need a key, not a list of orphans.
- **A plain tick is not proof a lane was uncommissioned — only that no readable brief is
  pointed at.** Pre-v3.13 receipts carry no pointer at all, and a `briefs/` directory that
  was cleaned up leaves live pointers dead. The card says which of the two it is; never
  report an uncommissioned tick as a lane that was *given* no brief.
- **A commission is the prompt, never a summary of it.** The card shows the file's first
  ~200 characters verbatim and the path to the rest. If you need to characterise what a lane
  was asked, read the file — do not paraphrase the card and present it as the commission.
- **"Rests on refuted" is a hole in the citation graph, not a verdict.** It says a live
  record cites ground a refutation took out. One hop, never transitive, and the record may
  still be right for other reasons. Read it before you retract it.
- The graph sees what the listing sees: in a git repo, ignored files are absent by design;
  outside git, the skip list hides dependency directories. Say which listing mode ran (the
  summary line prints it) when the absence of a file matters.
- **The river draws the ledgers, not the truth.** A record's evidence labels are the
  labels its author wrote; the river displays them and verifies none of them. `[cited]` on
  a node means someone claimed a citation, not that this skill checked it.
- **Inferred is not authored.** In COORD-only mode kind, relation and links are heuristics
  over the ledger's words — the shape is a reading of the trail, and every node says
  `inferred`. Never quote a coord-only river's channel counts as if the sessions had
  declared them.
- **A dead end is a shape, not a judgement.** It says nothing later linked that route —
  which is what an abandoned experiment and an unfinished-but-live one both look like.

## Provable interaction

**Handler presence is not interaction working.** The river shipped with correct pan, zoom
and click handlers bound to its `<svg>`, and the pan was **dead**: `#empty` — the
empty-state overlay, `position:absolute; inset:0` — carried the `hidden` attribute but its
own rule set `display:flex`, and an ID selector outranks the UA sheet's `[hidden]{display:
none}`. The overlay sat on top of the whole stage forever with `pointer-events:auto`, so
every `mousedown`, wheel and click landed on **it** and the svg never received one real
event. Every fixture stayed green throughout, because every fixture asked whether the
handlers were *in the file*. **Nothing had ever hit-tested the stage.**

So each interactive render now proves itself:

```bash
open '…/river.html?selftest=1'      # tab title becomes: SELFTEST PASS 5/5
```

`?selftest=1` hit-tests its own stage, drives a synthetic pan, a wheel zoom and a click,
and writes the verdict into **`document.title`** (`SELFTEST PASS n/n` / `SELFTEST FAIL
<step>`) plus a `#selftest` node carrying per-step results. It is DOM-and-state only — no
pixel reads, no `requestAnimationFrame` dependency — so it is just as valid in a hidden or
background tab, where a canvas cannot repaint at all. Query string at runtime: the rendered
bytes are identical with or without it, and it composes with `?embed=1`.

**The step that matters is `background-hit-reaches-<surface>`** — the one assertion that
would have caught the defect above on the day it shipped.

## Readable by default

**A correct render nobody can read is a failed render.** Every view here draws the whole
truth; above a certain density, drawing all of it at once is an inventory, not a picture. So
each one opens **staged** — the important thing first, the rest one gesture away — and every
threshold is **derived from the data's own counts, never from the clock**, so the same estate
stages identically twice and the byte-identical law is untouched. All staging is client-side
JS; the rendered HTML does not change.

| view | first load | how to get the rest |
|---|---|---|
| **file graph** | labels for the top **K = min(40, nodes/8)** nodes by degree (floored at 8); the header states *"labels: top K of N by degree"* | zoom past 1.25×, or search — a **match always gets its label** |
| **journey** | above **30 phrases**, phrases fold into one *"N phrases ▸"* pill per shape; above **40 chains**, chain arrows start off | click a fold, hit the `chains` button, or type in the filter — **a match auto-opens its fold** |
| **river** | flags closer than one bank span collapse to a single glyph carrying **+K** | click the cluster to expand it in place |
| **cockpit** | pictures load `?embed=1` — legend folded, picture full height | the legend's own summary, or **open full page ↗** |

**Staging is never hiding.** Nothing is dropped from the data, the JSON, the hit-testing or
the panel — a staged node is drawn, clickable and countable, it just has not been given a
label yet, and the page **says so in words** where the reader will see it. A view that
quietly omitted records would be a lying picture; a view that defers labels and says which
ones is a readable one.

**`?embed=1`** is the cockpit's request for the compact first screen. It is read from the
query string at runtime, so a page served with it and without it is **byte-identical** — the
determinism law and the legibility work never touch each other.

## Render gate

**Open the HTML before saying it works.** A run that writes a file is not a page that
draws. Confirm the glyphs actually render, the header counts match the summary line, the
first screen is **legible** at the width you are viewing, **and that it is NAVIGABLE where
it claims to be — pan, zoom and click PROVEN in the surface being viewed (`?selftest=1`
plus a real drag), never inferred from handler presence.** **A correct render
nobody can read fails this gate**: that is not a style note, it is the defect that produced
the readability work above, reported by the owner as *"how is this a graph readable?"* about
a page whose every number was right. Two traps that have both bitten:
- **A `file://` page in the browser pane is a static snapshot** — JS dead, canvas blank.
  Verify by serving it, never by an `open file://`: `doctor/scripts/render-check.sh
  <page.html>` binds 127.0.0.1 on a private port, curls the page, and only prints a URL
  once it has proved **HTTP 200** (exit 0 · 4 = served but not 200; reap with
  `render-check.sh --close <port>`). A screenshot of a blank canvas is not a render.
- **Check it at the size you're actually viewing.** All three viewers re-fit on viewport
  change — and the first fit runs before layout settles, which is why they re-fit on the
  next frame and on every stage resize. Glance at that path when you change window size.
  They fit different axes on purpose: the river fits its **height** (you pan downstream),
  the journey fits its **width** and never zooms past 1:1 (you pan down the table of doors).

If you cannot open a browser, say the page was written but not rendered — never claim a
view you did not see.

## Fixtures

- `scripts/river-fixture.sh` — a synthetic estate whose river shape is known exactly
  (every kind, relation and status; a merge, two dead ends, a fork, a backtrack, a rock, a
  supersede, a refute), asserting the counts, the channel outcomes, the edge-kind
  breakdown, the degrade path, the cap, byte-identical re-render, both theme hooks, zero
  external assets, a real render-check 200, and all three query verbs. Its phase G pins the
  **rests-on-refuted** rule against a purpose-built pair: a record citing the refuted ground
  *before* the tombstone lands and one citing it *after* are both flagged, while the refuter
  itself and an untouched control pair stay clean. Its phase H pins **commissions** across
  all four states — pointer + file (glyph, prompt head, path), pointer with no file, no
  pointer, and a pointer escaping the root (refused unread, its content proved absent from
  the page) — plus the widened bottom bank, byte-identical re-render with brief text inlined,
  and an edited brief actually reaching the next render. Exit 0 = all held.
- `scripts/journey-fixture.sh` — the journey asserted against **the real repo**, because the
  journey draws this harness's own door: every skill directory on disk owns exactly one node,
  every `SKILL=` verb the router can emit lands as a routed skill, routed + by-name-only
  accounts for all of them, no edge dangles, the page re-renders byte for byte, both themes
  and zero external assets, a real render-check 200, and the size cap. Then two synthetic
  phases it fully owns: a plugin tree with no `router.sh` (shapes 0, disclosed, not silently
  empty) and a throwaway git repo proving the stamp is the **commit** — a touched input
  re-renders identically, an edited one turns the stamp `+dirty`. Exit 0 = all held.
- `scripts/domains-fixture.sh` — the lane partitioner, asserted on scratch repos whose graph
  shape is known before the command runs. Two laws are checked in **every** phase: lanes are
  disjoint, and lanes + `seat_held` account for the whole scope. Its phase D is **the star**
  — N files all linking one manifest, which returns 1 lane if components are computed before
  hubs are extracted and N if the order is right; phase E pins the threshold on **outcome**,
  with one scope where the 3×median multiplier binds and one where the floor of 4 does, plus
  a 20-file scope where a share-of-scope rule and the median rule disagree about a degree-5
  file. Then: a component refusing to split under `--lanes`, the merge notes accounting for
  every component, the `--json` key set in order, all four exit-2 refusals (missing path,
  non-git root, no scope flag, empty scope three ways), `--changed` taking a rename's new
  side and naming the deletion it dropped, a real-repo run under 2s, and a byte-identical
  re-partition. Exit 0 = all held.
- `scripts/cockpit-fixture.sh` — the live window, asserted as a **client**: it stands a server
  up on a scratch estate (and a scratch `CHATROOM_ROOT`), then proves the loopback bind at the
  socket, every `/data` panel 200-and-parses against seeded files, a banked brief served
  verbatim while an outside-root pointer is refused unread, a render rebuilt when its input
  moves and *not* rebuilt inside the debounce, the mail slot round-tripping a post and passing
  chatroom's exit-5 refusal through as 422 with nothing written, a POST to any other route
  404-ing, and the server reaping its own port. Its always-on phase proves the opt-in on its
  OWN scratch root and an EPHEMERAL port — so it can never collide with, or reap, a cockpit
  the owner is actually using: `--always` writes the **real bound port** (asserted against
  `--port 0`, where a marker recording the *requested* port would say `0`), `serve` without
  the flag leaves an existing marker byte-identical, and `status` returns 0 / 5 / 6 for
  running / opted-but-down / unopted, treating a malformed marker as unopted and never
  repairing it. Exit 0 = all held.

## Self-check before finishing

- The scan (or `river`, or `journey`) was run by the script this turn, and its summary line
  is in the transcript.
- The page was actually opened — no questions asked, no "want me to open it?" — or the
  report says plainly which environment case blocked it.
- Any claim about what links to what came from the graph data or the file itself — not from
  a guess about how the project is probably organised.
- If you called a node orphaned, you said where you looked and what wouldn't show up there.
- If you reported a river, you said which mode it ran in — and if it was COORD-only, you
  said the kinds and relations were inferred before quoting a single count.
- If you called a stone "rests on refuted", you said it is one hop over the record's own
  links — not a verdict on the record, and not transitive.
- If you quoted a commission count, you said what the *other* ticks are: pointer-less
  receipts, dead pointers, or both. An uncommissioned tick is a gap in the record, not
  evidence that a lane went uncommissioned.
- If you reported a journey, you repeated its disclosures (which skills had no chains
  section, which had one nothing could be parsed from) before quoting the chain count, and
  you did not present a drawn arrow as evidence of runtime behaviour.
- You drew nothing by hand. A picture this skill can't produce is a missing subcommand.
- If you registered a project, the owner said yes.

## Chains

`archivist` = what the estate *says* (dossiers, the agent ledger) · **graph** = how it
*connects* (files and references) · **`graph river`** = how it *got here* (the ledgered
work, drawn) · **`graph journey`** = how it *opens* (the router's own door, drawn) ·
`recap` = what happened *over time*, in prose. A river answers "where did we go sideways";
a journey answers "what do I type to get X, and what can I only reach by name"; a recap
answers "what happened".

- **`/refuter`** — a river's rocks, and every stone the river marks **rests-on-refuted**:
  those are the live conclusions standing on ground a refutation already took out.
- **`/critic`** — a river's dead ends, and a suspicious cluster in the file graph.
- **`/eval`** — the journey draws the routing table; eval's ROUTER check *proves* it is
  wired. A shape on the page and a passing ROUTER check are two different claims.
- **`/doctor`** — a skill that stopped firing shows up on the journey as a missing arm or a
  by-name-only band entry; doctor says whether the front matter is why.
- **`/sessionend`** — run the scan so the next session's oracle opens on a current map.
- **`/stepbystep`** for a tangle, **`/explainer`** for an unfamiliar corner.
