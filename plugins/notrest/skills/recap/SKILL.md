---
name: recap
description: "Walks the recorded trail — COORD.md, COORD-AGENTS.md, git history, spend/ledger.md, the dossier folders — in timestamp order and delivers the decision track: a narrated timeline, a who-was-consulted table, ships, costs, and a clickable decision map (HTML). Every claim cites a trail line, a commit, or a path; anything without one is [unverified]. Use on /recap, \"recap the project\", \"how did we get here\", \"decision history\", \"what happened here\"."
---

# recap — the trail, turned into understanding

The suite records everything: `COORD.md` logs what each prompt landed, `COORD-AGENTS.md` logs
which agents were consulted and where their transcripts live, git logs what actually changed,
`spend/ledger.md` logs what it cost, and the dossier folders hold what was learned. That estate
is written — and unread. **recap is the read side.** It walks the trail in timestamp order and
turns it into the thing nobody has: the project's *decision story* — why this shape, who ruled
what, which agent's finding moved it, what got reversed — plus a map you can click.

The whole skill rests on one rule: **it derives, it never invents.** A recap is not what you
remember about the project; it is what the project wrote down about itself. Where memory and
the trail disagree, **the trail wins** (agentswarm's trail-walk tiebreaker — the trail was
written when the work landed).

## The prompt (all inputs optional)

**Router shape:** `recap`

Everything after `/recap` refines the walk. With no arguments, walk the whole estate.

- **A time window** — "this week", "since v2.13", "the last 10 commits", "2026-07-15 onward",
  "this session". Resolve it to a concrete span (first/last timestamp) and state that span in
  the output; never leave "this week" un-resolved.
- **A topic filter** — "the model-routing story", "everything about the hook". Filter by
  matching trail lines (case-insensitive `grep` across the trail files), then **keep one hop of
  context on either side** of each hit so the story doesn't read as disconnected fragments.
- **`--quick`** — chat only.

If the window and the estate disagree (asked for "since v2.13" but the ledger starts later),
say so and walk what exists.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or "quick", "brief", "no files", "just the story"):
- **No files.** Nothing written — no background, no dossier, **no map**, and **no record**:
  quick mode never touches the findings store either.
- **Same walk, compressed.** Still run `walk.py` and still read the whole stream in timestamp
  order — the shortcut is the write-up, never the evidence. (`--quick` skips `prefill`, not
  `walk`: the walk is the cheap half.)
- **Output in chat only:** the **Read Me First** block, then the decision track as ~5–12
  narrated beats, each with its citation token.
- End with one line: *"Quick recap — no map, no files; run again without `--quick` for the
  decision map and the two-file version."*

## Step 1 — run the walker; read its stream, not the files

**`scripts/walk.py` does the walking.** It is the whole estate — every COORD volume, the agent
ledger, git, the spend ledger, the findings store — merged onto one timestamp-sorted stream with
the estate inventory printed above it. **Token economics: the biggest read in the suite becomes
zero model tokens, and the citation token arrives pre-computed instead of being retyped from
memory 40k tokens later — which is where a recap invents a citation.**

```bash
WALK="${CLAUDE_PLUGIN_ROOT}/skills/recap/scripts/walk.py"     # loose install: scripts/walk.py beside this file
python3 "$WALK" walk  --root .                                # inventory + the merged stream
python3 "$WALK" spans --root .                                # per-source / per-day / per-session counts
python3 "$WALK" walk  --root . --since 2026-07-15 --until 2026-07-25   # a resolved window
python3 "$WALK" walk  --root . --json                         # same walk, machine-readable
```

Exit `0` ok · `2` usage · **`3` the estate is empty** — an exit 3 is the honest short recap,
delivered as one paragraph naming what would make the next one richer. Do not pad it.
(`scripts/fixture.sh` is the walker's own test — run it if you change the walker.)

Each stream line is `ts | source | kind | cite | ref | head`:

| Column | What it is |
|---|---|
| `ts` | **verbatim, in that source's own shape** — COORD's `2026-07-25 04:30Z`, a record's `2026-07-25T04:30:00Z` |
| `source` | `coord` · `agents` · `git` · `spend` · `findings` |
| `kind` | first-pass classification — `ruling` · `decision` · `ship` · `commit` · `consult` · `cost` · `finding`, plus `+open-thread`, `+reversal`, `+dead-pointer`, `+thin`, `+unrecoverable` |
| `cite` | **the citation token to print in Step 3** — already in the grammar below |
| `ref` | `COORD-001.md:42`, `spend/ledger.md:17`, or a short sha — where to go back to |
| `head` | the entry as recorded (`--head 0` for the untruncated line; `--json` also carries the full `text`) |

The walker also does the three things a hand-walk gets wrong:

- **UTC for git, structurally.** Plain `git log --date=format:'…Z'` prints the *author's local*
  time with a `Z` you did not earn, and it will not sort against COORD's UTC lines. `walk.py`
  reads `%at` — the author epoch, timezone-independent — and formats UTC itself, so there is no
  `TZ` to get wrong. **Do not hand-run `git log` for the walk.**
- **Clock shapes differ; the instant does not.** A record's `ts` is strict ISO8601
  (`2026-07-25T04:30:00Z`); a COORD line reads `2026-07-25 04:30Z`. The walker merges on the
  **instant** and still prints each one **verbatim in its own shape** — normalizing a timestamp
  to make a table tidy breaks the verbatim rule below.
- **Existence-checks every pointer it emits** — transcripts, `agent-<id>.meta.json` siblings,
  brief paths, a record's `type:"path"` evidence, and dossier paths named in a COORD evidence
  clause. A dead one is marked `!! DEAD: <path>` on its own stream line and listed again under
  the walk.

**The walker covers the timestamped sources. These stay a cheap look, and the walker's inventory
already tells you whether they exist:** `oracle-index.md` (the dossiers the story references),
the dossier folders (`research/ market-research/ understanding/ decision/ factcheck/ critique/
action-plan/ runbook/ pipeline/ introspection/ recap/`), `START-HERE.md` · `HANDOFF.md` ·
`STATE.md` (the last session's own account of where things stood), and `CHANGELOG.md` (the
shipped-version narrative). Open the two or three the story actually turns on — not all of them.

Then **write the inventory down** — the walker's table, verbatim, including **what is missing, by
name**. "No `spend/ledger.md` — costs are absent from this recap, not zero" is a finding.

## Step 2 — read the stream forward

The merge is done; the reading is yours. Read the stream forward — one entry per trail line **or
store record**, already tagged with the file it came from. The findings store is not a separate
pass: its records already sit in the same timestamp-merged walk. `spans` gives you the sittings
to hang beats on. You are looking for six things (the walker's `kind` is a first pass over the
words; the judgment is yours):

- **RULING** — an owner decision recorded in the trail ("owner ruling:", "ratified", "do NOT").
  These are the load-bearing nodes: everything downstream inherits them.
- **DECISION / PIVOT** — a direction chosen, changed, or abandoned; a scope cut; a rename; a
  correction of an earlier claim.
- **CONSULTATION** — a `COORD-AGENTS.md` entry: who was asked, what it concluded, its
  transcript path. **The path was verified before it was cited** — a ledger line whose
  transcript is gone is a pointer, not evidence, and must be labeled as such; the walker marks
  it `+dead-pointer` and its citation token already reads `— transcript missing`. When a line is
  thin (`model=? bytes=? | last: ?`), the walker has already looked for the sibling
  **`agent-<id>.meta.json`** next to the transcript: it carries the lane's `description` and
  `model`, which fills the gap the hook left (flagged `+from-meta`). If neither file exists the
  entry is flagged `+unrecoverable` — say so, and treat that agent's conclusion as unrecoverable.
  Note also that one agent id can appear **more than once**: a resumed lane fires the hook again
  per round, so the entry timestamp is when a *round* finished, and the `.meta.json` description
  may be stale from the original spawn.
- **SHIP** — a version bump, a release commit, a deploy.
- **COST** — a `spend/ledger.md` line, attached to the round it paid for.
- **FINDING** — an `archive/findings.jsonl` record: what a lane concluded, already validated at
  the door and already carrying its own evidence items and honesty labels. Cite it **by id**
  (`F-<n>`) and quote its `statement` — the id is stable, so a record is the one trail entry you
  do not have to re-verify to use. Two things to read, not just the statement: a record whose
  `status` is `superseded` or `refuted` is the trail's own reversal (↩︎) — show the tombstone
  **and** what it flipped, never only the survivor; and `links` names the records a conclusion
  rests on, which is a ready-made `informed-by` edge for the graph in Step 3.

Plus one more, which most trails carry and no summary ever surfaces: **OPEN THREAD** — anything
recorded as "in progress", "PENDING", "parked", "untested", or a papercut noted and not fixed.
Carry these to the end; the story is not over where the ledger stops.

**Trust order when sources disagree** (state the conflict, never average it):
- **Machine-written beats model-written on facts and clocks** — git author dates, `spend.py`
  lines, SubagentStop lines, file mtimes were written by code; COORD timestamps were typed by a
  model and can drift by minutes. A store record sits in between: `index.py` stamps `ts` at the
  door **unless the caller supplied one**, so treat a record's clock as machine-written by
  default and say so if a backdated `ts` is what makes two entries disagree.
- **Model-written beats machine-written on intent** — git says *what changed*; COORD says
  *why*, and a rename or a reversal is only legible from the COORD line.
- Append order is not timestamp order. Ledgers are appended; a line can carry a timestamp
  earlier or later than its neighbours. Sort by timestamp, and if append order and timestamps
  conflict, show both.

## Step 3 — synthesize the decision track

The track is the story with its receipts attached. **Every claim ends with a citation token**:

| Token | Means |
|---|---|
| `[COORD 2026-07-15 20:10Z]` | that ledger line, quoted timestamp verbatim |
| `[commit 9522ded]` | that commit (short sha + subject where it matters) |
| `[COORD-AGENTS <agent-id> → transcript]` | that agent line **and** its transcript verified present |
| `[COORD-AGENTS <agent-id> — transcript missing]` | the line exists; the transcript does not |
| `[spend 2026-07-21 05:24Z]` | that ledger line |
| `[F-12]` | that findings-store record, by id — quote its `statement`, carry its label, and add `(superseded)` / `(refuted)` when its `status` says so |
| `[dossier <path>]` | a dossier the story references |
| `[unverified]` | **no trail line supports this** — say it out loud, in the sentence |

A claim without a citation token is `[unverified]`, and an `[unverified]` claim may never be the
load-bearing beat of the story. If the story only holds together with an uncited link, write the
gap instead: *"the trail does not record why X changed between [COORD …] and [commit …]"*.

Then build the **graph** — this is what makes it a map and not a list:
- **Nodes** = the RULING / DECISION / CONSULTATION / SHIP entries from Step 2.
- **Edges** = `led-to` (this caused that), `informed-by` (a consultation's finding fed a
  decision), `reversed` (this undid or corrected that). **Only draw an edge the trail supports**
  — an evidence line that names the other node, a commit that fixes a named finding, a
  consultation whose conclusion appears in the next decision. Inferred edges are allowed only
  when labeled `inferred` in the data and shown dashed-faint in the legend.

## Step 4 — MANDATORY render gate

The map is a deliverable that *renders*. **Serve it, never `open file://`** — a `file://` page
silently breaks relative reads and gives you a blank board that looks like a render:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/doctor/scripts/render-check.sh" recap/{slug}map.html
#   proves HTTP 200, prints the http://127.0.0.1:<port>/… URL, leaves the server up
#   exit 0 ok · 2 usage · 3 no free port · 4 served but NOT 200 — a 4 is a failed gate
bash "${CLAUDE_PLUGIN_ROOT}/skills/doctor/scripts/render-check.sh" --close <port>
```

Open that URL and confirm: it draws, the edges land on the nodes, clicking a node shows its
citation, the theme toggle flips, and the console is clean. Check both themes, then close the
port. A screenshot of a blank board is not a render.

If you cannot open it, you do not get to imply you did. Say plainly, in chat *and* at the top of
the dossier: **"`{slug}map.html` was written but NOT render-verified."** (game-forge's
no-unrun-ships ethos, applied to a page.)

## Outputs — two files and one visual

Derive a `{slug}` from the window/topic (lowercase, hyphens, ≤50 chars; default `project`).
Create `recap/` in the working directory and write exactly three files; if they exist from a
prior run, suffix the slug `-2`, `-3`, … so no earlier recap is overwritten.

### `recap/{slug}background.md` — the walk (raw extraction)

```markdown
# <Project> — Recap Background
> Working document: the estate inventory and the raw timestamp-ordered walk.
> The story lives in {slug}Dossier.md; the map in {slug}map.html.

## Estate inventory
Source | Present? | Span | Entries | Notes
(one row per source from Step 1 — missing sources named, not omitted)

## The walk — every trail line in timestamp order
| Timestamp (verbatim) | Source | Kind | Entry (as recorded) |
(RULING / DECISION / CONSULTATION / SHIP / COST / OPEN THREAD — no interpretation yet)

## Conflicts found
(each: source A says X, source B says Y, both quoted, no resolution invented)

## Graph derivation
(node list with ids; edge list with the trail line that justifies each edge)
```

### `recap/{slug}Dossier.md` — the decision story

```markdown
# <Project> — Decision Recap

## 📌 Read Me First
- **What this is:** the project's decision story, derived from its own trail — not from memory.
- **Window walked:** <resolved span> across <N> sources.
- **The shape of it:** <the story in one plain sentence — what this project became and why>.
- **Biggest turn:** <the one decision that changed the most downstream>.
- **What the trail can't tell you:** <the honest gap — or "nothing load-bearing">.

**Three files:** `{slug}background.md` (the raw walk + conflicts) · `{slug}Dossier.md` (this —
the story) · `{slug}map.html` (the clickable decision map — open in a browser).
<render-gate line: verified in both themes, or NOT render-verified>

---

## The decision track
Narrated timeline — one beat per decision point, in order. Each beat: what was decided, what it
changed, and its citation token. Rulings marked ⚖️, reversals marked ↩︎.

## Who was consulted
| When | Agent | Model | Concluded | Transcript |
(from COORD-AGENTS.md; transcript column says verified-present or MISSING)

## Ships
| When | Version / commit | What shipped | Evidence |

## Costs
(per-model totals and the rounds they paid for, with [spend …] tokens; "not recorded" if absent)

## Conflicts in the record
(carried up from the background — the ones a reader must know about)

## Open threads
(everything still marked in progress / PENDING / parked / untested, with its citation)
```

### `recap/{slug}map.html` — the decision map

Copy `${CLAUDE_PLUGIN_ROOT}/skills/recap/assets/decision-map-template.html` (or
`assets/decision-map-template.html` beside this file) to `recap/{slug}map.html` and **replace
only the `RECAP_DATA` block** — from its `/* ==== RECAP_DATA` header down to and including the
closing `};`, leaving the `/* ==== END RECAP_DATA` line and everything below it alone. The
template's layout, theming, and interaction logic are generic, so any project's trail renders
the same way.

**Do not hand-type the nodes.** The walker emits that block with `nodes`, `ts` and `cites`
already filled from the walk — verbatim, existence-checked, in order:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/recap/scripts/walk.py" prefill --root . --out recap/{slug}data.js
#   --project NAME   the project label (default: the root directory's name)
#   --max-nodes N    cap the map (default 60); every drop is reported inside the block
#   --now ISO        the ONLY clock input; `generated` otherwise = the newest walked entry
```

Splice it in, then **you** supply the three things the machine cannot: the **edges**, and a
rewrite of each `title` (the ledger's own ask, cut to length) and `summary` (its `landed` half)
into the beat you want the reader to see. Node ids arrive as `n1…nN` in timestamp order, so the
edges you write refer to ids that already exist. A findings record arrives as `kind:"consult"` —
it is what a lane concluded, and the template has four lanes, not five.

```js
const RECAP_DATA = {
  project: "<name>",
  window:  "<resolved span, verbatim timestamps>",
  generated: "<YYYY-MM-DD>",
  sources: ["COORD.md (N lines)", "git (N commits)", "…"],   // shown in the footer
  nodes: [
    { id: "n1",
      ts: "2026-07-15 20:10Z",        // verbatim from the trail
      kind: "ruling",                  // ruling | decision | consult | ship
      title: "Keep all five continuity files",
      summary: "Redundancy is a deliberate safety cushion; do not consolidate.",
      cites: [ { type: "coord",      text: "- [2026-07-15 20:10Z] [fable-main] owner ruling: …" },
               { type: "commit",     text: "b2f4cac COORD: owner ruling — five continuity files stay" },
               { type: "transcript", text: "/abs/path/agent-….jsonl", note: "verified present" },
               { type: "finding",    text: "F-12 — <the record's statement, quoted>", note: "archive/findings.jsonl" } ],
      flag: ""                         // "unverified" | "inferred" | "" — rendered as a badge
    }
  ],
  edges: [ { from: "n1", to: "n2", rel: "led-to", why: "the COORD line names the ruling" } ]
  //  rel: "led-to" | "informed-by" | "reversed"; add inferred:true for an unproven edge
};
```

Rules for filling it: `ts` verbatim from the trail (never reformatted), one node per real trail
event (do not merge two decisions into a tidy one), `cites` non-empty for every node — a node
with no citation carries `flag: "unverified"` and says why in `summary`.

The template labels the six cite types it knows (`coord` · `commit` · `transcript` · `spend` ·
`dossier` · `note`) and **falls back to the raw type name for anything else** — so
`type: "finding"` renders as `finding` and needs no template edit. Cite a record by its id in
`text`, and put the store path in `note`; a record's `links` are the trail evidence for an
`informed-by` edge, so an edge derived from them is *not* `inferred`.

## Bank the recap — one record in the store

recap reads the findings store (Step 1) and it also **writes back to it, exactly once**. After
the three files land and the render gate has run, emit **one** record — `kind=result`, because a
recap *is* a result: it is what the walk concluded about the project. That is what makes the
story findable by `index.py find` and by the *next* recap's Step-1 inventory, instead of being a
file nobody remembers is there.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"recap-2026-07-25",
  "skill":"recap",
  "kind":"result",
  "ask":"how did this project get here — the decision story for 2026-07-15 → 2026-07-25",
  "statement":"Walked 2026-07-15 19:18Z → 2026-07-25 04:30Z across 6 sources (COORD 214 lines, COORD-AGENTS 38 entries, git 61 commits, spend 12 lines, 2 store records, 9 dossiers): the harness became a marketplace plugin after the rename ruling, and the biggest turn was pulling evals in-house. 3 open threads; the trail does not record why the external runner was tried first.",
  "evidence":[{"type":"path","ref":"recap/projectDossier.md","label":"cited"},
              {"type":"coord-line","ref":"- [2026-07-25 04:30Z] [fable-main] JOURNEY.md — the harness as six user journeys …","label":"cited"}],
  "relation":"toward",
  "links":["F-12","F-14"]}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder. No archivist
script on disk → skip this step silently; the three files are still the deliverable.)

- **One record, not a stream.** `researcher` emits one per pass because each pass earns a
  separate claim; a recap has exactly one claim — the shape of the story — and the dossier
  already holds the working-out.
- **The two evidence items are the whole point.** `type:"path"` → the dossier you just wrote,
  the thing a reader opens. `type:"coord-line"` → **the close line: the last trail line inside
  the walked window, quoted verbatim** — the instant this record is accountable to, and what
  lets a later walk check whether the story still holds. No COORD in the estate? Ship the
  `path` item alone (one item satisfies the door) and say in the `statement` that the window
  had no ledger.
- **`links` names the records the story leaned on.** Every id must already exist in the store or
  the door rejects with `links-unknown`; `[]` is the honest value when the story cited none.
- **The door validates — you don't.** `add` prints the assigned `F-<n>` on success and **exits 2
  naming the rule** it broke on rejection. Fix the record and re-run; **never hand-append to the
  JSONL.** Report the `F-<n>` in the chat summary.
- **This is an append, never an edit** — the one write recap makes outside `recap/`, and the
  reason it is now both sides of the store: it reads records as trail, and leaves one behind.
- **Not in `--quick`.** A recap whose render gate failed still gets its record — the failure
  belongs in the `statement`, not in silence.

## Honesty rules

- **Derive, never invent.** Every node, edge, and sentence traces to a trail line, a commit, a
  transcript, or a dossier. No reconstructed dialogue, no "the team then decided" without a line.
- **Timestamps verbatim.** Copy them exactly as recorded, including the `Z`. Do not normalize,
  round, or re-timezone. If two sources timestamp the same event differently, print both.
- **Never rewrite history.** recap is read-only over the estate: it writes only into `recap/` —
  plus the single appended record above, which is an append to a store built for appends, never
  an edit. It never edits COORD, COORD-AGENTS, the spend ledger, a dossier, or an existing
  record — a wrong ledger line gets *quoted and flagged*, never corrected in place, and a record
  the story disagrees with gets cited **with** the disagreement stated; recap never supersedes
  or refutes another skill's record.
- **A ledger line is an index, not a source.** COORD-AGENTS entries summarize; the transcript is
  the evidence. Before stating what an agent concluded in load-bearing terms, open the
  transcript — and if it is gone, say the conclusion is unverifiable beyond the one-line summary.
- **Surface conflicts; do not smooth them.** Two sources disagreeing is a finding, and often the
  most useful one in the whole recap.
- **A thin estate gets a short recap.** Young repo, no COORD, five commits? Say exactly that,
  produce the honest short version, and name what would make the next recap richer (usually:
  start appending COORD lines). Padding a thin trail is the failure mode this skill exists to
  avoid.
- **Costs are what the ledger says.** Never estimate spend the ledger did not record; "not
  recorded" is the honest answer.

## Self-check before finishing

- **`walk.py` was run and its stream is what got read** — no ledger was hand-merged, and no
  `git log` was hand-run for the walk.
- The estate inventory names every source **and every missing source**, with spans.
- The walk is in timestamp order, and git timestamps were taken in **UTC**.
- Every beat in the decision track carries a citation token; nothing load-bearing is
  `[unverified]`.
- Every transcript path cited was existence-checked; missing ones are labeled MISSING.
- Every edge in the graph names the trail line that justifies it, or is flagged `inferred`.
- Conflicts between sources appear in the dossier, not just the background.
- Open threads are listed — the recap does not end tidier than the project actually is.
- **The map was served by `render-check.sh` (exit 0) and looked at** (both themes, console
  clean), and the port was closed — or the dossier says plainly that it was not.
- **The one `kind=result` record was emitted and the store printed its `F-<n>`** — or `--quick`,
  or no archivist script on disk. Nothing was hand-appended to the JSONL.
- Nothing in the estate was modified: `git status` shows changes only under `recap/`, plus the
  one appended line in `archive/findings.jsonl`.

## Finishing up

Write `{slug}background.md` first (inventory + walk + conflicts + graph derivation), then
`{slug}Dossier.md`, then `{slug}map.html` — then run the render gate, then bank the one record.
Give the user a short chat summary: the shape of the story in a sentence, the biggest turn, the
honest gap, the three paths, and the `F-<n>` the store assigned — pointing them at the map
first, because that is the part they cannot get from chat. Don't paste the files into chat.

Chains:
- **`/archivist`** — the store is both an input and an output here: `track` lists the records the
  walk cites, one `find` pulls up the dossiers the story names, and a fresh `scan` makes the next
  recap see the estate the same way — which now includes this recap's own record.
- **`/critic`** — a recap surfaces conclusions the project has been running on for weeks;
  pointing critic at the dossier red-teams the one that matters most.
- **`/sessionend`** — when a recap was produced this session, its `map.html` path belongs in the
  handoff: the next session gets the whole decision history in one link instead of re-walking it.
- **`/spend`** — if the costs section reads thin, the ledger is the thing to fix, not the recap.
