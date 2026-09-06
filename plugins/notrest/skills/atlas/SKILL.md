---
name: atlas
description: "The estate-side bank for Atlas — a tracked git hook runs the tests the map binds at every commit, derives each part's status from the exit codes (done only when a test that COULD fail passed; a done with no test is demoted; a failing done becomes wip+failing), writes an immutable snapshot under atlas/snapshots/<commit>.json plus the board, and pushes both through an adapter. Also mints and checks the access keys the harness gates on. Use on /atlas, \"bank the map\", \"wire the atlas hook\", \"is this commit banked\", \"born-red proof\", \"mint an access key\"."
---

# atlas — the estate tells the truth about itself, at every commit

A map somebody maintains by hand is a map that starts lying the week it is written. The
part was done, then the test broke and nobody retyped the row; the component was
"blocked", then it wasn't, and the board still says so six weeks later. Every project
tracker in the world has this disease and none of them can be cured by discipline,
because the cure is asking humans to do arithmetic they get no feedback on.

**atlas is the estate-side half of Atlas: the bank.** It runs at every commit, from a
tracked git hook nobody has to remember. It **runs the tests the map binds**, derives
every part's status **from the exit codes**, stamps the commit, writes an immutable
snapshot, builds the estate's board, and pushes both through an adapter. Nothing on the
map is typed in by a person, so nothing on the map can go stale between two commits.

**What it is not:** a tracker (nobody moves a card here), a CI system (it runs the tests
the map already declares, it does not decide what to build), and above all **it has no
authority over anything it describes**. It cannot deploy, approve, or execute anything but
the checks the estate armed. It observes and records. That boundary is what makes it
trustworthy — and it never commits, never stages, and never edits a file the estate wrote.

**Router shape:** `bank`

## The status law (the whole point)

| The claim | The test | → status | evidence |
|---|---|---|---|
| `done` | passed, and it could have failed | **done** | `passed` |
| `done` | none bound | **wip** | `none` — **demoted, and reported** |
| `done` | `true` / `: ` / `exit 0` / `… \|\| true` | **wip** | `unfalsifiable` — a command that cannot fail is not a test |
| `done` | failed | **wip + failing** | `failed` — and the board goes **RED** |
| `wip` | failed | **wip + failing** | `failed` — red-first work, reported, not alarmed |
| `wip` | passed | **wip** | `passed` — evidence may DEMOTE, never promote |

`claim`, `status` and `evidence` are **three separate fields** on every part, so the map
says *claims done, evidence none* out loud instead of hiding it behind one green check.
**RED** is narrower than "something failed" on purpose: only a **claimed-done part with a
failing test** reddens the board, because a board that cries wolf at ordinary red-first
work is a board people learn to ignore.

The long form — falsifiability, `proven_red`, where parts come from, and why an estate
with no contract is never certified green — is `references/status-law.md`. Read it before
changing any of the above; the rules interlock.

## The script owns all of it

`scripts/atlas.py` (python3, stdlib only) is the whole instrument. **Run it; don't
re-improvise it** — the status law lives in exactly one function so there is exactly one
place it can be wrong.

| Call | Does | Exit |
|---|---|---|
| `atlas.py key --mint --label <who>` | mints a key, prints it **once**, appends `sha256:label:date` to the keyring | 0 · **5** that label already exists |
| `atlas.py key --check [--key K]` | the gate every hook asks: flag, then `NOTREST_ACCESS_KEY`, then `${NOTREST_HOME:-~/.notrest}/access-key`. On **0 only**, stdout carries one line — the **sentinel** | **0** valid · **7** none, invalid, or a symlinked/non-regular keyring |
| `atlas.py key --revoke <label>` | deletes that label's line — revocation is deletion | 0 · **7** no such label |
| `atlas.py key --list` | labels and mint dates (never a key) | 0 |
| `atlas.py bank --root .` | run the tests, derive the map, snapshot, board, push | **0** green · **5** board RED · **4** banked but the push failed · **3** nothing to derive |
| `atlas.py wire --root .` | install the tracked post-commit hook; idempotent | 0 · **5** a foreign post-commit hook is in the way (never clobbered) |
| `atlas.py wire --prove` | the **born-red proof**, in a scratch git repo | **0** it went red · **6** it did NOT · **7** no access key |
| `atlas.py wire --unwire` | remove atlas's hook (and restore any hook it backed up) | 0 |
| `atlas.py status --root .` | HEAD vs last banked, snapshot age, hub, hook | **0** green · **5** board RED · **6** **HEAD is NOT banked** |

Exit codes, in one sentence each: **0** ok · **2** usage or an unreadable declared input ·
**3** nothing to derive (not a git repo, or no map and no gates) · **4** banked locally,
the push failed · **5** RED or REFUSED · **6** HEAD is not banked / the proof did not go
red · **7** no valid access key.

Fixture: `bash plugins/notrest/skills/atlas/scripts/fixture.sh` — exit 0 = every
assertion held. It builds **scratch git repos** in a mktemp dir and never touches the real
repository, never reaches the network, and mints its keys into a scratch keyring.

## Wiring an estate onto the map

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/atlas/scripts/atlas.py" wire   --root .
python3 "${CLAUDE_PLUGIN_ROOT}/skills/atlas/scripts/atlas.py" bank   --root .   # first bank
python3 "${CLAUDE_PLUGIN_ROOT}/skills/atlas/scripts/atlas.py" wire   --prove    # born-red
```

`wire` writes a four-line shim at `<git-dir>/hooks/post-commit` (honouring
`core.hooksPath`) that points at the tracked hook body `hooks/atlas-bank-hook.sh` — so the
logic that runs at every commit lives **in the repo**, reviewed like code, updated with
the plugin. A hook body copied into `.git/hooks` is a fork nobody can see. `wire` also
seeds `atlas/map.md` and `atlas/config.json` if they are absent, and it **never
overwrites a post-commit hook it did not write** (exit 5; `--force` keeps the original as
`post-commit.pre-atlas`).

The hook is silent by design and can never cost you a commit: no `set -e`, four fast paths
(no python3 · no `atlas/` dir · **no valid access key** · already banking), and `exit 0`
always. The bank's exit code is deliberately dropped there — a red board is a true fact
about the commit that just landed, not a reason to make `git commit` look broken.

### The map

```
PART: <id> — <title>
CLAIM: done | wip | planned | blocked      (default: wip)
TEST: <a shell command that could fail>    (optional — a done with no test is demoted)
PATH: <where the code lives>               (optional, repeatable)
```

Every gate in `gates/ACTIVE.md` is picked up automatically as a part **claimed done**, its
verdict taken from `hooks/gate-check.py` — the instrument that already owns the
`CHECK:`/`EXPECT:` grammar. Directives inside a fenced code block are documentation and
are never run.

### The born-red proof — an estate joins the map only after it goes red

`wire --prove` builds a **scratch git repo** — never this estate's history, never a commit
here — wires it, and walks three commits: hook live → **green**; hook disabled → the map
must go **RED** (`status` exit 6 — a commit that never banked); hook restored → green
again. If step two comes back green the proof **fails** (exit 6) and the estate must not
join the map: a detector nobody watched fail is not a detector. The one thing it writes into
**this** estate is the receipt, `atlas/born-red.json` (creating `atlas/` if it is absent), which
then rides on every later snapshot — so the proof is a fact the estate holds rather than a claim
about a directory that no longer exists.

## The push adapters

One contract: `push(snapshot, board, credential) -> (ok, hub_commit, reason)`.

- **`file`** — real, and the one to test against: writes `<hub>/<estate>/snapshots/<commit>.json`
  (immutable there too), `board.json` and `HEAD`, then **reads `HEAD` back** — "the hub has
  it" is a fact read from the hub, not an assumption made after a write.
- **`http`** — **stubbed, and it never sends.** It returns
  `hub contract unverified — awaiting ATLAS-PLAYBOOK/WIRING` from **one function**, and
  `atlas.py` imports no network module at all, so eval's NETWORK-EGRESS check re-proves
  the claim on every run instead of asking you to believe this paragraph. Writing a
  plausible POST for a body shape nobody has verified would be inventing a protocol and
  calling it an integration. `[unverified — awaiting ATLAS-PLAYBOOK/WIRING]`
- **`none`** — the default. "No hub configured" is a *state*, not a failure: the bank
  still exits 0 on a green board.

Credentials are handled by **presence, never contents**: a token this script does not read
is a token it cannot leak into a snapshot, a log line, or an error message.

## The snapshot and the board

`atlas/snapshots/<commit>.json` is written once, `0444`, and **never rewritten**. A
re-bank of the same commit re-derives, compares, and *reports that today's derivation
differs* — then leaves the snapshot standing. History is what the estate looked like when
that commit landed; a new state needs a new commit.

`atlas/board.json` is the estate's live board: `graph.py`'s file graph, `graph.py`'s
river, and archivist's records card — **counts only, never statement text**, because the
board is the thing that leaves the estate and a finding's text is not the hub's business.
Each collector is bounded (`--board-timeout`) and, when it fails or times out, says
**stale** out loud with the reason. It never invents a number and it never fails the bank.

## The access key

notrest is part of Atlas from v4.8.0, and the keyring is `plugins/notrest/.access/keys.sha256`
— one line per key, `sha256(key):label:YYYY-MM-DD`. The key itself is never stored, so
minting prints it exactly once and revocation is deleting the line. Without a valid key on
a machine, this hook (and the harness's other hooks) exit **silently**.

**Require the sentinel, never the exit code alone.** A caller that trusts `key --check`'s
exit code is trusting that *something* on `PATH` called `python3` exited 0 — a stub, a
wrapper, an interpreter that never parsed this file all exit 0 too, and every one of them
would have read as "licensed". So a positive answer carries the one line only this script
can print:

```
notrest-access: ok ring=<first 12 hex of sha256(keyring bytes)> path=<the keyring used>
```

Exactly that, on stdout, on exit 0 and **only** on exit 0 — `--quiet` keeps it, because it
is not chatter, it is the proof, and `--quiet` moves the human sentence to stderr instead.
A hook matches the `notrest-access: ok ring=` prefix verbatim before it does anything, and
may pin the `ring=` digest and the `path=` to the ring it expects. The keyring itself must
be a **regular file**: a symlinked ring is refused (exit 7, with the reason) because a
re-pointable ring is a re-pointable gate — `--keyring`/`NOTREST_KEYRING` choose *which*
ring, never a ring that is not a file.

The holder's key lives in the private store — **`${NOTREST_HOME:-~/.notrest}/access-key`**,
or the `NOTREST_ACCESS_KEY` env var. `atlas.py` resolves that store exactly as the hooks do,
and deliberately so: a machine that sets `NOTREST_HOME` must never get *"the hook says
licensed, atlas.py says no"*. One gate asked twice has to give one answer.

State the bound honestly whenever it comes up: **the gate controls the harness on a
machine, not the source files.** Anyone holding a copy of the repository holds the source.
It is a belt beside the private-repo braces, and it is never described as more than that.

## Honesty rules

- **Derived, never invented.** Every field on the map traces to an exit code, a commit, or
  a pushed snapshot. Unknown is printed as unknown; a stale collector says stale.
- **A green check is not evidence.** If the evidence is `none`, the status is not `done` —
  no exceptions, no "but it obviously works".
- **A dead collector is not a red part.** A board source that timed out is *stale*, and it
  never turns into a claim about the estate's parts. (Same law as watch's dead source.)
- **Never rewrite a snapshot.** A wrong snapshot is corrected by the next commit's
  snapshot, the way the append-only ledgers correct with a new line. History stays.
- **The bank never writes what it did not measure**, never commits, never stages, and
  never edits a file the estate authored.
- **Say what did not run.** `--dry-run` and `--no-board` produce visibly incomplete boards
  and label themselves as such.

## Self-check before finishing

- The bank ran through `scripts/atlas.py` — the status law was not re-derived by hand or
  paraphrased into chat.
- Every `done` on the board has `evidence: passed` from a test that could fail; every
  demotion was reported by name, not smoothed away.
- The snapshot for this commit exists, is `0444`, and was not rewritten; if the derivation
  differed from it, that was said.
- The board's stale collectors were named with their reasons; no count was carried over
  from a previous run as if it were fresh.
- The push line says which adapter ran and, for `http`, that it never sent.
- `wire` was idempotent (a second run said "already wired") and no foreign post-commit
  hook was overwritten.
- The born-red proof ran in a scratch repo and actually **went red** at step two.
- If the estate has a COORD ledger, one append-only line records the bank:
  `- [YYYY-MM-DD HH:MMZ] [atlas] banked <commit12> — N parts, X done, Y failing | evidence: atlas/snapshots/<commit>.json`

## Finishing up

Give the headline in chat — *banked `<commit12>`, N parts, X done, Y failing, board
green/RED, pushed or not and why* — plus the snapshot path. Don't paste the JSON.

Chains:
- **`/eval` and `/doctor`** — the gates atlas banks are the same gates those two run.
  atlas records *when* they were green; eval decides *whether the laws hold*.
- **`/graph`** — the board's file graph and river are graph.py's own outputs; open them
  there when a part's neighbourhood is the question.
- **`/archivist`** — the records card on the board is the store's four-box count. A part
  that keeps going red is a finding waiting to be banked.
- **`/refuter`** — the hooks and the key gate are kernel surfaces; a change to either
  ships through a refuter round, and the born-red proof is the arm that catches a
  detector which cannot detect.
- **`/sessionend`** — an unbanked HEAD belongs in the handoff: the next session inherits a
  map that is honest about what it does not yet know.
