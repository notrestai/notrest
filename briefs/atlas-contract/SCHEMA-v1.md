# atlas-hub/1 — the WIRE format

`atlas-hub/1` is `atlas-hub/0` plus the four facts a map needs before anyone can *trust* it: what a node **is** (`kind`), what it **contains** (`parent`), what it **connects to** (`edges`), and whether its parts are actually **proven** (`evidence` + `check`), together with where the claims came from (`source`, `sources`, `head`).

**Both versions are live.** `hub/validate.mjs` dispatches on `schema_version`: `"atlas-hub/0"` takes the frozen /0 path, `"atlas-hub/1"` takes the /1 path, anything else is one refusal that names both. A /0 pusher does not have to change anything, ever — `upgrade(wire0)` exists so the hub can read old snapshots in the new shape without asking the estate to re-push.

Read `SCHEMA-v0.md` first: the `nodes`/`parts` naming collision, the counts-only findings law, and the derived-blockers law are all unchanged and are not restated here.

## Exports

| export | what it is |
|---|---|
| `validate(body, project)` | `{ok:true, snap}` \| `{ok:false, error}` — dispatches on `schema_version` |
| `upgrade(wire0)` | a /0 wire in, a /1 wire out, losslessly (below) |
| `rollup(snap)` | derived counts; same shape for /0, two extra keys for /1 |
| `WIRE_VERSION` | `"atlas-hub/0"` — still the hub's own reported version |
| `WIRE_VERSION_1` | `"atlas-hub/1"` |
| `WIRE_VERSIONS` | `["atlas-hub/0", "atlas-hub/1"]` |
| `STATES` `NODE_KINDS` `EDGE_KINDS` `EVIDENCE` `SOURCE_FRESHNESS` `SOURCE_STATES` `LIMITS` | the closed sets and the bounds |

The validator is **pure**: no I/O, no clock, no network. It is the same module the worker imports, so what the hub accepts is exactly what `node hub/test-validate.mjs` proves.

**Ownership of the objects that cross the boundary**, stated so no caller has to guess:

- `validate(body, project)` returns the caller's own `body` **by identity** as `.snap`. It never copies and never mutates. This is /0's behaviour and it is kept on /1 — the worker validates and then stores the same object, and a copy on that path would be a needless clone of every snapshot the hub ingests.
- `upgrade(wire0)` returns a **deep copy** (`structuredClone`, falling back to a JSON round trip). Mutating the input afterwards cannot reach the output, and the input is never touched. It has to be a copy, because upgrade drops and rewrites keys.

## Top level

| field | required | notes |
|---|---|---|
| `schema_version` | yes | fixed `"atlas-hub/1"` |
| `project` | yes | must equal the URL's `:project` |
| `stamp` | yes | verbatim from the snapshot |
| `taken_at` | yes | ISO-8601 UTC, must end in `Z` **and** satisfy `Number.isFinite(Date.parse(v))` — ending in Z is a shape, being a date is the fact the viewer's "stamp age" needs |
| `playbook` | no | the playbook version the estate DECLARES; a non-empty string |
| `head` | no | the git commit the snapshot was taken at — `/^[0-9a-f]{7,40}$/`, lowercase. This is the one field that lets a reader check the map against the tree |
| `sources` | no | `{ [collector]: "available"\|"stale"\|"unknown"\|"unsupported" }`, ≤ 32 entries. Freshness of the collectors that BUILT the snapshot, so a viewer can say "this map is half-blind" instead of silently under-reporting |
| `nodes` | yes | see below |
| `edges` | no | see below |
| `journey` | no | exactly as /0 |
| `findings` | no | exactly as /0, counts only, plus a wider text guard |
| `links` | no | exactly as /0, `[{label,url}]`, `https://` only |

Unknown top-level fields are **ignored**, as in /0. A field the hub does not know is a field a future lane may be adding; refusing it would make the wire unshippable in halves.

`"unsupported"` exists only at the top level: it is a fact about the estate (a collector this estate does not run), never about one node — so `nodes[].source.state` cannot claim it.

## `nodes[]`

| field | required | notes |
|---|---|---|
| `id` | yes | unique across `nodes` |
| `kind` | **yes** | one of `product` `component` `agent` `surface` `capability` `module` `service` `contract` `host` `other` |
| `title` `milestone` `active_owner` | no | as /0 |
| `parent` | no | another node's `id`. Must exist; a node is never its own parent; no cycles. A child may be listed **before** its parent — the wire is a set, not a sorted tree |
| `parts` | yes | array, ids unique within the node |
| `source` | no | provenance, below |

`kind` is mandatory because "what is this thing" is the question a map exists to answer, and a default would be a guess the hub made on the estate's behalf.

### Ids are addresses

`"."` is the separator that joins a node id to a part id, so **no node id and no part id may contain `"."`** — otherwise `"a.b.c"` means two things at once and an edge endpoint is unresolvable. Ids also may not carry leading or trailing whitespace (two ids that look identical in a viewer must not resolve differently) and may not be empty after trimming. **Slashes stay legal**: group ids like `notrest/rig` are a real naming, and only `"."` and whitespace are load-bearing in an address.

Ids are refused rather than silently normalised, because rewriting an id here would break every `journey.refs` entry and every edge that already points at it.

## `nodes[].parts[]`

| field | required | notes |
|---|---|---|
| `id` | yes | unique within the node |
| `status` | yes | `todo` \| `wip` \| `done` (unchanged from /0) |
| `label` / `title` | no | strings |
| `evidence` | no | `proven` \| `unverified` \| `stale` \| `failing` |
| `check` | no | the command that settles the claim |

**`evidence: "proven"` REQUIRES a non-empty `check`** (trimmed before the test, so `"   "` is a blank check wearing whitespace). A proof nobody can re-run is an assertion.

**Evidence is COUPLED to status**, the same derivation the collector kit makes, so the hub and the kit can never disagree about what a part claims:

| status | evidence it may carry |
|---|---|
| `todo` | **none** — no `evidence` key at all; nothing has been built to check |
| `wip` | `failing` \| `unverified` \| `stale` |
| `done` | `proven` (with a `check`) \| `unverified` \| `stale` — **never `failing`** |

A done part whose check broke is not a done part: it becomes `wip` + `failing`. That is the one transition the coupling exists to force.

**Absence means unverified.** A part with no `evidence` key is counted as `unverified` by `rollup`, never as proven and never as a separate "unknown" bucket — so a map that was never checked reads as a map that was never checked.

## `nodes[].source` (optional)

| field | notes |
|---|---|
| `repo` | non-empty string |
| `paths` `symbols` `tests` `contracts` `adrs` | arrays of non-empty strings — an empty entry is provenance with nothing behind it |
| `runtime` | `{kind?, id?, url?}`, each a non-empty string when present |
| `verified_at` | non-empty string; ISO-8601 UTC (`…Z`) is the recommended form |
| `state` | `available` \| `stale` \| `unknown` |

## `edges[]` (optional)

| field | required | notes |
|---|---|---|
| `from` | yes | a node `id` **or** a `"<node>.<part>"` id — both must resolve |
| `to` | yes | same |
| `kind` | yes | one of `authority` `data` `effect` `evidence` `control` `composes` `implements` `other` |
| `relation` | no | a free-text refinement of the kind (`"guards"`, `"reads"`), non-empty |

Bound: ≤ 5000 edges. Endpoints are checked for whitespace and length like ids, but may of course contain the one `"."` that joins a node to a part.

**Self-edges are refused, at NODE level.** `from === to` is refused outright, and so is any edge whose two endpoints *resolve to the same node* — `"a.b" -> "a"`, `"a" -> "a.b"`, and `"a.b" -> "a.c"` all state containment the tree already shows, and would draw as a loop nobody reads. An edge naming an id that is not a node or a `<node>.<part>` is refused, so a drawn edge is always a real one.

**Duplicate edges are refused** — two edges with the same `from`, `to`, `kind` and `relation` are one fact pushed twice, and a viewer counting them would double it.

`from`/`to` resolve against the SAME id space the journey's `refs` use, which is why a step ref and an edge endpoint can never mean different things.

## `findings` (optional) — counts only, harder

`findings` is an **allowlist** on /1: `count` (required, non-negative integer) and `recurring` (optional, non-negative integer) are the ONLY keys permitted. Any other key — whatever its type — is refused as `findings.<key>: not allowed — the wire is counts only`.

/0 used a denylist, which only ever knows the prose it has already met: `findings.note`, `findings.summary`, `findings.detail` all rode straight through it. Finding text never leaves the estate; the wire carries the number, not the content.

## Limits

| bound | value | applies to |
|---|---|---|
| `nodes` | 500 | `nodes[]` |
| `parts` | 5000 | every `parts[]` summed |
| `steps` | 200 | `journey.steps[]` |
| `bytes` | 2 MiB | the request body (enforced in the worker) |
| `edges` | 5000 | `edges[]` |
| `sources` | 32 | `sources` entries |
| `sourceArray` | 200 | each of `source.paths\|symbols\|tests\|contracts\|adrs` |
| `refs` | 200 | each `journey.steps[].refs` |
| `string` | 4096 chars | every free string: `stamp`, node/part `title`, part `label`, `check`, edge `relation`, every `source` string, link `label` and `url`, and every id |

The /0 bounds are unchanged. Every cap refusal names the path, the actual size and the limit — `nodes[0].source.paths: 201 entries exceeds limit 200`.

## Refusals

One fact, naming the offending path — the estate's `gate/000` law, unchanged:

```
nodes[3].parts[1].status: not one of todo|wip|done (got "DONE")
nodes[0].parts[0].check: evidence "proven" requires a non-empty check
nodes[1].parent: cycle "gate -> edge -> gate"
edges[4].from: unknown id "ghost" — no such node or <node>.<part>
sources.git: not one of available|stale|unknown|unsupported (got "fresh")
schema_version: expected one of "atlas-hub/0" | "atlas-hub/1", got "atlas-hub/2"
```

The version refusal names **both** wires, so a pusher on the wrong one learns what to send, not merely that it was wrong.

## `rollup(snap)`

Unchanged for /0 — same keys, same values, byte for byte. The shipped viewer reads a /0 rollup and must not start seeing keys under a version the estate never pushed.

For /1 it adds exactly two:

| key | value |
|---|---|
| `evidence` | `{proven, unverified, stale, failing}` — every part lands in exactly one bucket; a part with no `evidence` key counts as `unverified` |
| `edges` | the edge count; `0` when there is no `edges` key, never absent |

## `upgrade(wire0) -> wire1`

Every /0 **fact** survives. The only additions are the version string and the one field /1 makes mandatory. `upgrade(validate(wire0, p).snap)` validates as /1 — that round trip is an arm in the suite, not a claim here.

| /0 | /1 |
|---|---|
| `schema_version: "atlas-hub/0"` | `"atlas-hub/1"` |
| every node | gains `kind: "component"` (a /0 card is a component unless it already spelled a legal /1 kind) |
| every part | keeps `id`/`status`/`label`; gains **no** `evidence` key |
| — | no `edges`, no `head`, no `sources`, no `parent`, no `source` are invented |
| everything else | copied verbatim, into a deep copy |

### What upgrade NORMALISES, and why that is not a loss

/1 polices seven things /0 never checked at all. A /0 wire could therefore hold a value that /0 gave no meaning to and /1 refuses. Upgrade **drops** those — it never invents a replacement:

| dropped | because |
|---|---|
| `head` unless `/^[0-9a-f]{7,40}$/` (lowercased first if it is uppercase hex) | `"HEAD"`, `"abc1234-dirty"` and `""` are not commits; guessing one would be the hub asserting a provenance nobody pushed |
| `sources` entries whose value is not in the freshness enum, and the whole map if nothing legal is left or it is not a plain object | `{git:"yes"}` is not a freshness reading |
| `playbook` unless a string | `1.0` the number is not a version the hub can compare |
| `parent`, on every node | /0 has no parent contract: a /0 `parent` may name nothing, or the node itself |
| `edges`, whole | /0 has no edge contract at all — whatever was under that key was never validated, and promoting it would make the hub draw a graph nobody checked |
| `source`, on every node | /0 has no provenance contract, so a /0 `source.state` may claim `"unsupported"`, which only the top level may say |
| `check`, `label`, `title` on a part unless a string | `7` is not a command and not a label |
| `findings` keys outside `count`/`recurring` | /1's allowlist is stricter than /0's denylist; the wire is counts only under both |

Ids and `journey.steps[].refs` are **trimmed** (the same trim on both sides, so a ref still resolves to the part it named). Nothing else is rewritten.

### What upgrade will NOT fix

A handful of /0-legal shapes are refused by /1 and are deliberately left to be refused, because the only fix would be worse than the refusal: a node or part id containing `"."` — renaming it would break every ref and edge pointing at it, silently; a free string over the 4096-char cap — truncating the estate's own words is a lie; a `taken_at` that ends in `Z` but is not a date; `journey.steps[].refs` over 200 entries. None of these occur in the real kernel wire. When one does occur, the estate re-pushes; the hub does not quietly rewrite what an estate said.

### The counts must not move

The real kernel wire (`fixtures/kernel-wire.json`, 29 nodes / 92 parts) is upgraded in the suite and its rollup asserted **identical** to the /0 rollup on `counts`, `total`, the whole `journey` object and `findings`. An upgrade that moved a number by one would be a new claim about the estate, which is exactly what an upgrade must not be. Parts gain no `evidence` because a /0 push never claimed evidence. Absence reads as unverified, which is the honest reading of a map that was never checked; writing `"unverified"` in would be the hub asserting on the estate's behalf.

## Refuted and fixed

An independent refuter attacked the /1 path. All eight findings are fixed, each with an arm in `test-validate.mjs` that fails without the fix: (1) findings prose rode unlisted keys → allowlist; (2) `upgrade` could emit invalid /1 → normalises the seven fields; (3) `upgrade` returned views onto its input → deep copy; (4) `"a.b"` was two addresses → `"."` refused in ids, self-edges compared at node level; (5) evidence and status could contradict → coupling table; (6) the cycle walk was quadratic → colour-marked single pass (~1 ms at 500 deep); (7) provenance arrays and free strings were unbounded → 200 / 4096 caps; (8) ids and stamps were sloppy → trim, duplicate edges refused, `taken_at` must parse.
