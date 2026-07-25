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
- **`evidence`** — `[{type: url|path|command|coord-line, ref, label}]`, label one of
  `cited` · `estimate` · `recall` · `unverified` · `model-opinion`.
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
  flipped record. `--json` is the machine surface (`graph` consumes it): every schema field
  plus `effective_status` and `status_by`.
- **Flip:** `index.py supersede F-3 --by F-9 [--note "…"]` ·
  `index.py refute F-3 --evidence <url|path> [--type …] [--label …]`.
- **Search:** `index.py find "<term>" [--root .]` — matches statements and asks in the store,
  then legacy index entries, then **dossier bodies** (the index carries only each dossier's
  Read Me First head, so a term buried in the body used to be invisible).
- **Legacy index:** `index.py scan [--root .]` — walks the known output folders for every
  `*Dossier.md` and REPLACES `oracle-index.md`, adding one pointer entry each for the findings
  store, `COORD-AGENTS.md`, and `compile/candidates.md`. Idempotent; run it freely.
- **Prove it:** `bash scripts/fixture.sh` — every kind lands, every rule turns its record away
  with exit 2, the track round-trips, the flips resolve, `find` sees bodies. Exit 0 = green.

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
   `find` first. On a hit, surface it — id or path, date, statement — and offer the real
   choices: *reuse*, *extend* (seed the run with it), or *fresh* (it moved on). The user picks.
2. **Emit as you go, not at the end.** A record per thing learned, written when it is learned.
   A track assembled afterwards is a memory, not a record.
3. **Answer "what do we know about X"** from `find` + `track`, with labels and dates intact.
4. **Correct by appending.** Wrong record? `supersede` it with the better one. Contradicted by
   evidence? `refute` it with the ref. Never delete, never rewrite.

## Honesty rules

- **The store is a finding aid, never a source.** Cite the `ref` inside the evidence, not the
  record line. A `[recall]` record stays `[recall]` when quoted.
- **A live record is not "still true".** It is a snapshot of its `ts`. Re-verify load-bearing
  `[cited]` claims that could have moved, and say which you re-verified.
- **Validation is not verification.** `add` exiting 0 means the record is well-formed and says
  what it rests on — not that the claim is right.
- **Empty result ≠ never investigated.** The store only sees what was written under the scanned
  root. Say where you looked.

## Self-check before finishing

- Every record was written by the script and **validated at the door (`add` exited 0)** — none
  hand-appended to the JSONL.
- Each statement reads alone, in 1–3 sentences, with its evidence attached.
- Corrections went in as `supersede`/`refute` tombstones; nothing on disk was edited in place.
- Anything told to the user came from a record or dossier actually opened this turn.
- If a legacy dossier landed this session, `scan` ran after it.

## Finishing up

Report the ids written and the track's live count — not the record bodies. Chains: `track
--json` feeds `/graph` for the rendered session track; a stale-but-relevant hit seeds
`/researcher` or `/factcheck`; live records feed `/decider` as evidence; `/refuter` attacks a
record and its finding becomes the `refute` evidence. At `/sessionend`, one `scan` leaves the
next session's intake already knowing the estate.
