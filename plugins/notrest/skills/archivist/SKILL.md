---
name: archivist
description: "The suite's findings store — skills emit compact FINDING RECORDS into one append-only archive/findings.jsonl, validated at the door (schema, enums, honesty labels, real URLs behind cited links); archivist keeps the session's whole track and still indexes legacy dossiers into oracle-index.md. Use on /archivist, \"what do we already know about X\", \"show me the session track\", \"index the dossiers\", or before a researcher / factcheck / decider run."
---

# archivist — the findings store

`oracle` + `sessionend` keep *session* continuity (what was I doing). This keeps *content*
continuity (what do we already know) — and it is now a **store, not a filing cabinet**.

Per-skill dossier folders are retired. Working skills no longer each write a two-file dossier
into their own directory; they emit **finding records** — one compact, validated line per
thing learned — into the store this skill owns. The store is the session's full track: what
was asked, what was found, what it rests on, and how each step relates to the last.

Script: `scripts/index.py` (python3 stdlib, zero model tokens). Fixture: `scripts/fixture.sh`.

**Router shape:** `prior-art`

Store: **`archive/findings.jsonl`**, repo-root relative. One JSON record per line,
**append-only**, written under an exclusive `flock`. Nothing in it is ever edited in place —
not by a skill, not by the seat, not by this skill. **Never hand-edit it:** a correction is a
new record, and `track` resolves what is currently true.

## The record — the schema is pinned

```json
{
  "id": "F-7",
  "ts": "2026-07-25T14:03:11Z",
  "session": "builder-archivist",
  "skill": "researcher",
  "kind": "finding",
  "ask": "which cache for the read path?",
  "statement": "Redis 7 ships client-side caching over RESP3 tracking; invalidation is push-based.",
  "evidence": [{"type": "url", "ref": "https://redis.io/docs/latest/…", "label": "cited"}],
  "relation": "toward",
  "links": ["F-3"],
  "status": "live"
}
```

- **`id`** — assigned by the store, `F-<n>`, monotonic. A caller that supplies one is rejected.
- **`ts`** — ISO8601 Z. Caller-supplied or stamped now.
- **`session` · `skill`** — who wrote it. **`ask`** — the question it was answering.
- **`kind`** — `finding` · `result` · `decision` · `conflict` · `backtrack` · `side-route`.
- **`statement`** — the finding itself, 1–3 sentences. Self-contained: it must read alone.
- **`evidence`** — `[{type: url|path|command|coord-line|record, ref, label}]`, label one of
  `cited` · `estimate` · `recall` · `unverified` · `model-opinion`. A `record` ref cites
  another record: `F-<n>` here, `<project>:F-<n>` anywhere on the library shelf.
- **`relation`** — `toward` (progress on the ask) · `lateral` (sideways) · `back` (a retreat).
- **`links`** — ids this record answers, extends, or corrects. **`status`** — `live` ·
  `superseded` · `refuted` (as written; the *effective* status is resolved, see below).

## Validation at the door

`add` validates before it appends. A rejected record **exits 2 and names the rule it broke**;
nothing is written. This is where the suite's honesty-lint lives — a claim that cannot state
what it rests on does not enter the store.

| rule | turns a record away when |
|---|---|
| `statement-required` | statement missing or blank |
| `kind-enum` · `relation-enum` · `status-enum` | value outside its enum |
| `evidence-type-enum` · `evidence-label-enum` | evidence type or honesty label outside its enum |
| `evidence-shape` | evidence is not a list of `{type, ref, label}` with a non-empty ref |
| `cited-url-needs-url` | a `[cited]` url evidence ref is not a real URL (`scheme://host`) |
| `evidence-required` | `kind=finding\|result\|decision` with an empty evidence list |
| `links-unknown` · `links-shape` | links names an id the store does not hold, or is not a list |
| `record-ref-shape` | a `record` evidence ref is not `F-<n>` or `<project>:F-<n>` |
| `record-ref-unknown` | a local `F-<n>` is not in this store, or a **reachable** project's store has no such id |
| `unknown-field` · `id-assigned` · `ts-format` · `field-type` | the schema is pinned; ids and shapes are the store's |
| `json-parse` · `record-object` · `no-input` · `store-corrupt` | the input or the store is not what it claims |

## The resolution rule — append-only status flips

A JSONL store is append-only, so **no record's status is ever rewritten**. A flip is a new
**tombstone** record: `kind=result`, `relation=back`, the target in `links`, and a statement
opening `supersedes F-<id>` or `refutes F-<id>`. `supersede` and `refute` write those; both
validate like anything else.

**`track` resolves the effective status by walking links:** a record's effective status is the
status it was written with, unless a later tombstone (a) names it in `links` **and** (b) opens
its statement with the flip verb. Both conditions must hold — a passing mention flips nothing.
The last such tombstone in `ts` order wins. `--status live` filters on the *effective* status,
so a superseded record disappears from the live track while staying on disk, forever, with the
record that replaced it.

### RESTS-ON-REFUTED — the ground under a live record

A tombstone flips **its target and nothing else**. Refute `F-3` and the `kind=decision` record
whose `links` names `F-3` stays `live` — correctly, because only a tombstone flips a status —
while the finding it was built on is gone. That is the store's quietest failure, so `track`
says it out loud: **a live record whose `links` names an effectively-refuted id rests on
refuted ground.**

- **On the line:** a trailing ` · RESTS-ON-REFUTED F-3` (comma-joined when there are several).
- **In `--json`:** `"rests_on_refuted": ["F-3"]` — present on **every** record, non-empty only
  on an effectively-live one, so a consumer tests truthiness rather than membership.
- **One hop**, through the links the record itself declares, resolved by the same link-walk as
  the status. A record that is not effectively live is never flagged (its own status already
  reports its footing), and a tombstone never rests on what it killed.

The flag is a **dependency made visible, not a verdict**. It does not refute the record and it
does not flip it: it says the evidence underneath moved, and leaves the judgment — does this
decision survive the loss of that finding? — to the reader who has to make it.

## Commands

**Write one record** (the sink every skill uses):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"<session>","skill":"<skill>","kind":"finding","ask":"<the question>",
  "statement":"<the finding, 1-3 sentences>",
  "evidence":[{"type":"url","ref":"https://…","label":"cited"}],
  "relation":"toward","links":[]}'
```

Prints the assigned id on success; exits 2 with the rule name on rejection. `--json` or stdin.
(Loose install: the script sits at `../archivist/scripts/index.py` relative to any sibling skill.)

- **Track:** `index.py track [--session S] [--kind K] [--status live] [--json] [--root .]` —
  the session's records in `ts` order, one compact line each:
  `id · kind · relation · statement-head · [labels]`, with ` · SUPERSEDED by F-n` inline on a
  flipped record and ` · RESTS-ON-REFUTED F-n` on a live one whose footing was refuted.
  `--json` is the machine surface (`graph` consumes it): every schema field plus
  `effective_status`, `status_by`, and `rests_on_refuted`. `--kind` takes **one** kind per
  call (chain two calls for two kinds); `--session`, `--status`, and `--kind` compose.
- **Flip:** `index.py supersede F-3 --by F-9 [--note "…"]` ·
  `index.py refute F-3 --evidence <url|path> [--type …] [--label …]`.
- **Search:** `index.py find "<term>" [--root .]` — matches statements and asks in the store,
  then legacy index entries, then **dossier bodies** (the index carries only each dossier's
  Read Me First head, so a term buried in the body used to be invisible).
- **Legacy index:** `index.py scan [--root .]` — walks the known output folders for every
  `*Dossier.md` and REPLACES `oracle-index.md`, adding one pointer entry each for the findings
  store, `COORD-AGENTS.md`, and `compile/candidates.md`. Idempotent; run it freely.
- **Library:** `index.py library register|list|find|track` — the cross-project shelf (above).
- **Prove it:** `bash scripts/fixture.sh` — every kind lands, every rule turns its record away
  with exit 2, the track round-trips, the flips resolve, a decision linking a refuted finding
  is flagged while its un-refuted control is not, `find` sees bodies, and the shelf registers
  idempotently, finds across two scratch repos, survives a deleted third, and validates every
  `record` ref. Exit 0 = green (it runs on a scratch shelf; the real one is never touched).

## The library — one shelf, many stores

A store that only its own session can read is a notebook. **The library makes every
project's store readable from every other project** — this machine's, today's and last
month's, the one running in a parallel lane right now.

**The federation law: stores stay where they live; the library only indexes them.** A
project's `archive/findings.jsonl` never moves, never gets copied to a central pile, and
never gets rewritten by the shelf. It stays in its repo — versioned with the code it
describes, and beam-able with it. The shelf is one append-only registry naming *where
the stores are*: `~/.claude/notrest-library/registry.jsonl`, one `{root, name, ts}` JSON
line per project (`$NOTREST_LIBRARY_ROOT` moves the whole shelf; `--library-root` moves
it for one call). Nothing else is central, so nothing else can rot, and a project you
delete simply reads as `missing` instead of corrupting a shared index.

**Registering feeds two consumers.** `library register` appends to the registry *and* to
`~/.claude/oracle-projects.txt` — graph.py's cross-project registry, the file `graph.py
all` reads to draw the estate-wide view. One registration, both surfaces; both writes
are independently idempotent.

```bash
IDX="${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py"
python3 "$IDX" library register [--root .] [--name <shelf-name>]  # idempotent; says so
python3 "$IDX" library list                                       # name · root · records · reachable
python3 "$IDX" library find <terms…> [--kind K] [--json]          # every store, seconds, 0 tokens
python3 "$IDX" library track --project <name> [--kind K] [--status live]
```

- **`register`** — the shelf name defaults to the repo's dirname; `--name` overrides it.
  Re-registering the same root is a **no-op that says so**. A name is refused if it is
  already taken by another root (`library-name-taken`) or contains a `:` or anything
  outside `[A-Za-z0-9._-]` (`library-name-shape`) — the name is half of every citation.
- **`find`** — searches **every registered project's** statements and asks (all terms must
  match), plus each repo's legacy `oracle-index.md` heads. One line per hit:
  `<project>:F-<n> · kind · statement-head · [labels]`, with ` · REFUTED by …` inline so a
  dead answer can never travel as a live one. `--json` is the machine surface: whole `ask`
  and whole `statement`, plus a citable `ref`. Unreachable roots are **reported, never
  fatal**.
- **`track`** — another project's whole track, read where it lives. No `cd`, no copy.

### Citing across the shelf

```json
{"type": "record", "ref": "notrest:F-5", "label": "cited"}
```

`F-<n>` cites this store (the id must exist, exactly like `links`). `<project>:F-<n>`
cites the shelf: the id is **checked when that project is reachable** and rejected if that
store has no such record — and when the project is unregistered or its repo is offline,
the ref is **accepted with a note on stderr**. Federation that fails closed is federation
nobody can use: another machine's repo being absent is not evidence that the record is
wrong. The note says the ref went in unverified; the reader gets to see that.

**The reuse law: a question the library already answers is a search budget you do not
spend.** Before a researcher / factcheck / marketresearcher fan-out, `library find` runs
first. A strong cross-project hit is cited as `record` evidence and the budget shrinks.
Re-deriving what another project already recorded is not thoroughness — it is the same
token spent twice.

## The legacy estate stays readable

History does not get rewritten. Dossiers written before the store still index: `scan` reads
`research/`, `market-research/`, `understanding/`, `decision/`, `factcheck/`, `critique/`,
`action-plan/`, `runbook/`, `pipeline/`, `introspection/`, `recap/`, `draft/`, and dates each
entry from **the dossier's own date line** when it declares one, falling back to file mtime.
`COORD-AGENTS.md` (which agents ran, what each concluded) and `compile/candidates.md` (what
this project keeps doing) get one pointer entry each — a pointer, never a copy. From a pointer
you `grep` the real file, and from a hit you read the transcript before citing it.

## The workflow

1. **Consult before spending.** About to run researcher / factcheck / decider / explainer? One
   `find` first, then one `library find` — this project, then every project on the shelf. On a
   hit, surface it — id or `<project>:F-<n>`, date, statement — and offer the real choices:
   *reuse*, *extend* (seed the run with it), or *fresh* (it moved on). The user picks.
2. **Emit as you go, not at the end.** A record per thing learned, written when it is learned.
   A track assembled afterwards is a memory, not a record.
3. **Answer "what do we know about X"** from `find` + `track`, with labels and dates intact.
4. **Correct by appending.** Wrong record? `supersede` it with the better one. Contradicted by
   evidence? `refute` it with the ref. Never delete, never rewrite.
5. **Re-read the track after a refute.** Anything now carrying `RESTS-ON-REFUTED` is a live
   record whose footing moved — say which, and either revisit it or state why it still stands.
   A refutation nobody propagated is a refutation the project never actually absorbed.

## Honesty rules

- **The store is a finding aid, never a source.** Cite the `ref` inside the evidence, not the
  record line. A `[recall]` record stays `[recall]` when quoted.
- **A live record is not "still true".** It is a snapshot of its `ts`. Re-verify load-bearing
  `[cited]` claims that could have moved, and say which you re-verified.
- **Validation is not verification.** `add` exiting 0 means the record is well-formed and says
  what it rests on — not that the claim is right.
- **Empty result ≠ never investigated.** The store only sees what was written under the scanned
  root — and the library only sees the projects that are **registered and reachable**. Say
  where you looked, and say which roots were unreachable when they were.
- **A cross-project ref accepted with a note is unverified.** The store said "that project is
  not on this machine right now", not "that record exists". Quote the note when you lean on it.

## Self-check before finishing

- Every record was written by the script and **validated at the door (`add` exited 0)** — none
  hand-appended to the JSONL.
- Each statement reads alone, in 1–3 sentences, with its evidence attached.
- Corrections went in as `supersede`/`refute` tombstones; nothing on disk was edited in place.
- Anything told to the user came from a record or dossier actually opened this turn.
- No record carrying `RESTS-ON-REFUTED` was reported as a live finding without that flag being
  said out loud — the flag travels with the record, the way a label does.
- If a legacy dossier landed this session, `scan` ran after it.
- Before any search fan-out, `library find` ran — and if this project is not on the shelf yet,
  `library register` ran, so the next session (here or anywhere) can read what this one learned.

## Finishing up

Report the ids written and the track's live count — not the record bodies. Chains: `track
--json` feeds `/graph` for the rendered session track; a stale-but-relevant hit seeds
`/researcher` or `/factcheck`; live records feed `/decider` as evidence; `/refuter` attacks a
record and its finding becomes the `refute` evidence. At `/sessionend`, one `scan` leaves the
next session's intake already knowing the estate.
