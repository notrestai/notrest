---
name: atlas
description: "The estate-side half of Atlas — the BANK and the DOOR. A tracked git hook runs the tests the map binds at every commit, derives each part's status from the exit codes (done only when a test that COULD fail passed; a done with no test is demoted; a failing done becomes wip+failing), writes an immutable snapshot plus the board, and pushes both to the one hub. It also holds this machine's identity: the Atlas token the portal issues, verified OFFLINE against a vendored Ed25519 verifier, with the committed access ring as the owner's break-glass. Use on /atlas, \"bank the map\", \"wire the atlas hook\", \"is this commit banked\", \"born-red proof\", \"log in to Atlas\", \"mint an access key\"."
---

# atlas — the estate tells the truth about itself, at every commit

A map somebody maintains by hand is a map that starts lying the week it is written. The
part was done, then the test broke and nobody retyped the row; the component was
"blocked", then it wasn't, and the board still says so six weeks later. Every project
tracker in the world has this disease and none of them can be cured by discipline,
because the cure is asking humans to do arithmetic they get no feedback on.

**atlas is the estate-side half of Atlas, and it does two jobs.** The **bank** runs at
every commit from a tracked git hook nobody has to remember: it runs the tests the map
binds, derives every part's status **from the exit codes**, stamps the commit, writes an
immutable snapshot, builds the board, and pushes both. The **door** decides whether this
machine is admitted at all — an Atlas identity token verified offline, with the access
ring behind it. Nothing on the map is typed in by a person, so nothing on the map can go
stale between two commits.

**What it is not:** a tracker (nobody moves a card here), a CI system (it runs the tests
the map already declares, it does not decide what to build), and above all **it has no
authority over anything it describes**. It cannot deploy, approve, or execute anything but
the checks the estate armed. It observes and records. That boundary is what makes it
trustworthy — and it never commits, never stages, and never edits a file the estate wrote.

**Router shape:** `bank` · notrest v4.9.0

## Do this first — put an estate on the map

Run these from the estate's root, in this order. Each one's exit code is the answer.

```bash
python3 plugins/notrest/skills/atlas/scripts/atlas.py key --check --quiet   # 0 = this machine is admitted, 7 = it is not
python3 plugins/notrest/skills/atlas/scripts/atlas.py wire   --root .       # install the tracked post-commit hook; idempotent
python3 plugins/notrest/skills/atlas/scripts/atlas.py bank   --root .       # the first bank
python3 plugins/notrest/skills/atlas/scripts/atlas.py wire   --prove        # the born-red proof — expect exit 0
python3 plugins/notrest/skills/atlas/scripts/atlas.py status --root .       # expect HEAD banked, exit 0
```

Stop at the first non-zero you did not expect. `key --check` returning 7 means the door is
shut, and no later step will do anything: get an identity first (below). `wire --prove`
returning 6 means the estate must NOT join the map — a detector nobody watched fail is not
a detector. `status` returning 6 means HEAD is simply not banked yet, which the next commit
fixes by itself.

## Identity — who this machine is

Twelve lines, because the whole model has to fit in one head:

1. A **token** admits a machine — one Ed25519-signed JWT per seat, issued by the Atlas
   portal (`iss` · `aud` · `sub` · `seat` · `mid` · `prj` · `scp` · `jti` · `iat` · `exp`,
   30 days), landing mode 0600 at `${NOTREST_HOME:-~/.notrest}/atlas-token`. It is never
   printed, never in argv, never in a URL.
2. It is verified **offline, here** — Atlas's own RFC 8032 verifier, vendored at
   `plugins/notrest/skills/atlas/scripts/vendor/verify_token.py`: no network, no
   third-party import, one fact per refusal. The `mid` claim binds the token to
   `sha256(machine-id)`; the **hostname is never an input**, so a rename costs no seat.
3. Signing keys and revocations are **caches**, refreshed at SessionStart inside a 2 s
   budget and silent when the hub is unreachable. An offline holder keeps working until `exp`.
4. The **access ring** is the owner's break-glass and still admits the fleet: `key --check`
   asks the token first and the ring second, and both open the same gate, same sentinel.

Getting one: the script's `login` verb runs the device flow (a URL and a code, then the token is
stored and the host-scoped git credential helper installed). The consumer-facing bootstrap
— the text the hub serves verbatim — is `docs/ATLAS-CONNECT.md`. The contract this
implements is `briefs/atlas-contract/IDENTITY-CONTRACT.md`.

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
with no contract is never certified green — is
`plugins/notrest/skills/atlas/references/status-law.md`. Read it before changing any of the
above; the rules interlock.

## Everything this skill ships

One row per file. Nothing under this skill is undocumented, and nothing here is optional
scenery — if a file is not in this table it is not shipped.

| File | What it is |
|---|---|
| `plugins/notrest/skills/atlas/SKILL.md` | this page — the judgment half |
| `plugins/notrest/skills/atlas/scripts/atlas.py` | **the instrument.** `key` · `login` · `helper` · `bank` · `wire` · `status`. python3, stdlib only |
| `plugins/notrest/skills/atlas/scripts/atlas_token.py` | the deciding half of identity: read the token, fingerprint the machine, ask the verifier. Network-free, so every hook may import it |
| `plugins/notrest/skills/atlas/scripts/atlas_auth.py` | the talking half: device login, refresh inside the last 7 days, JWKS and revoked caches. Silent on failure by contract |
| `plugins/notrest/skills/atlas/scripts/atlas_helper.py` | the git credential helper for the hub host only — install, check by round trip, uninstall. It never reads the token; it writes the line that will |
| `plugins/notrest/skills/atlas/scripts/atlas_wire.py` | snapshot → the `atlas-hub` v1 wire, and the one HTTP push. Counts, never finding text |
| `plugins/notrest/skills/atlas/scripts/vendor/verify_token.py` | **Atlas's file, vendored byte-exact.** Its licence line is line 1 and is never edited — if it does not fit, wrap it |
| `plugins/notrest/skills/atlas/scripts/vendor/__init__.py` | empty, so `vendor` imports as a package |
| `plugins/notrest/skills/atlas/scripts/mockhub.py` | **fixtures only.** A stdlib hub bound to 127.0.0.1 that plays Atlas well enough to drive login, refresh, revocation and push. Never used at runtime |
| `plugins/notrest/skills/atlas/scripts/fixture.sh` | the bank's arms, in scratch git repos |
| `plugins/notrest/skills/atlas/scripts/fixture-token.sh` | node signs, python verifies — two implementations must agree |
| `plugins/notrest/skills/atlas/scripts/fixture-auth.sh` | the device flow's every status against the mock, and the no-leak grep |
| `plugins/notrest/skills/atlas/scripts/fixture-helper.sh` | the credential protocol, against a scratch `HOME` |
| `plugins/notrest/skills/atlas/scripts/fixture-wire.sh` | the wire table, the size refusals, the bearer-never-travels arms |
| `plugins/notrest/skills/atlas/mcp/server.mjs` | Atlas's **read-only** MCP server, vendored byte-exact with its licence line |
| `plugins/notrest/skills/atlas/mcp/atlas-mcp.sh` | its launcher: the secret by path, `node >= 22` refused in one line and exit 6 |
| `plugins/notrest/skills/atlas/mcp/fixture-mcp.sh` | the server's arms, hermetic |
| `plugins/notrest/skills/atlas/references/status-law.md` | the long form of the law above |

Every fixture is a command, and its exit code is the whole verdict:

```bash
bash plugins/notrest/skills/atlas/scripts/fixture.sh          # the bank
bash plugins/notrest/skills/atlas/scripts/fixture-token.sh    # identity, verified
bash plugins/notrest/skills/atlas/scripts/fixture-auth.sh     # identity, fetched
bash plugins/notrest/skills/atlas/scripts/fixture-helper.sh   # git's side of it
bash plugins/notrest/skills/atlas/scripts/fixture-wire.sh     # the push
bash plugins/notrest/skills/atlas/mcp/fixture-mcp.sh          # the read server
/usr/bin/python3 plugins/notrest/skills/atlas/scripts/mockhub.py --selftest
```

They build scratch dirs under `mktemp`, never touch the real repository or the real
`${NOTREST_HOME:-~/.notrest}`, mint their own throwaway keys, and reach no address but
127.0.0.1.

## The one script, and what it answers

`plugins/notrest/skills/atlas/scripts/atlas.py` is the whole instrument. **Run it; don't
re-improvise it** — the status law lives in exactly one function so there is exactly one
place it can be wrong. The Call column below is what follows the script's path.

| Call | Does | Exit |
|---|---|---|
| `key --mint --label <who>` | mints a ring key, prints it **once**, appends `sha256:label:date` to the keyring | 0 · **5** that label already exists |
| `key --check [--key K]` | the gate every hook asks: token first, then flag, `NOTREST_ACCESS_KEY`, `${NOTREST_HOME:-~/.notrest}/access-key`. On **0 only**, stdout carries one line — the **sentinel** | **0** valid · **7** none, invalid, or a symlinked/non-regular keyring |
| `key --revoke <label>` | deletes that label's line — revocation is deletion | 0 · **7** no such label |
| `key --list` | labels and mint dates (never a key), plus whether a token is present | 0 |
| `login [--base URL]` | the §1 device flow: URL + code, poll, store 0600, verify, install the helper | **0** admitted · **7** the flow failed, one fact on stderr |
| `helper --install \| --check \| --uninstall` | the host-scoped git credential helper; `--check` is a real `git credential fill` round trip, never a look at the config | 0 · **1** not installed, git refused, or the round trip returned no credential · **2** pick exactly one |
| `bank --root .` | run the tests, derive the map, snapshot, board, push | **0** green · **5** board RED · **4** banked but the push failed · **3** nothing to derive |
| `wire --root .` | install the tracked post-commit hook; idempotent | 0 · **5** a foreign post-commit hook is in the way (never clobbered) |
| `wire --prove` | the **born-red proof**, in a scratch git repo | **0** it went red · **6** it did NOT · **7** no valid key or token |
| `wire --unwire` | remove atlas's hook (and restore any hook it backed up) | 0 |
| `status --root .` | HEAD vs last banked, snapshot age, hub, hook | **0** green · **5** board RED · **6** **HEAD is NOT banked** |

Exit codes, one sentence each: **0** ok · **2** usage or an unreadable declared input ·
**3** nothing to derive (not a git repo, or no map and no gates) · **4** banked locally,
the push failed · **5** RED or REFUSED · **6** HEAD is not banked / the proof did not go
red / node is unusable · **7** no valid access key or token.

The modules carry their own CLIs, and they are the ones to reach for when a single
question needs answering without the bank around:

```bash
/usr/bin/python3 plugins/notrest/skills/atlas/scripts/atlas_token.py check         # 0 admitted · 7 with the one fact
/usr/bin/python3 plugins/notrest/skills/atlas/scripts/atlas_token.py fingerprint   # this machine's id, exit 0
/usr/bin/python3 plugins/notrest/skills/atlas/scripts/atlas_auth.py sessionstart   # what the hook calls; exit 0 and silent, always ($ATLAS_HUB_BASE)
/usr/bin/python3 plugins/notrest/skills/atlas/scripts/atlas_helper.py check        # the credential round trip
/usr/bin/python3 plugins/notrest/skills/atlas/scripts/atlas_wire.py --help         # convert · push
```

## Wiring an estate onto the map

`wire` writes a four-line shim at `<git-dir>/hooks/post-commit` (honouring
`core.hooksPath`) that points at the tracked hook body
`plugins/notrest/hooks/atlas-bank-hook.sh` — so the logic that runs at every commit lives
**in the repo**, reviewed like code, updated with the plugin. A hook body copied into
`.git/hooks` is a fork nobody can see. `wire` also seeds `atlas/map.md` and
`atlas/config.json` if they are absent, and it **never overwrites a post-commit hook it did
not write** (exit 5; `--force` keeps the original as `post-commit.pre-atlas`).

The hook is silent by design and can never cost you a commit: no `set -e`, four fast paths
(no python3 · no `atlas/` dir · **no valid key or token** · already banking), and `exit 0`
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
verdict taken from `plugins/notrest/hooks/gate-check.py` — the instrument that already owns
the `CHECK:`/`EXPECT:` grammar. Directives inside a fenced code block are documentation and
are never run.

### The born-red proof — an estate joins the map only after it goes red

`wire --prove` builds a **scratch git repo** — never this estate's history, never a commit
here — wires it, and walks three commits: hook live → **green**; hook disabled → the map
must go **RED** (`status` exit 6 — a commit that never banked); hook restored → green
again. If step two comes back green the proof **fails** (exit 6) and the estate must not
join the map. The one thing it writes into **this** estate is the receipt,
`atlas/born-red.json` (creating `atlas/` if absent), which then rides on every later
snapshot — so the proof is a fact the estate holds rather than a claim about a directory
that no longer exists. `--no-receipt` runs the proof and writes nothing.

## Where the bytes go — one destination, secrets by path

One adapter contract: `push(snapshot, board, credential) -> (ok, hub_commit, reason)`.

- **`file`** — real, and the one to test against: writes
  `<hub>/<estate>/snapshots/<commit>.json` (immutable there too), the board and `HEAD`, then
  **reads `HEAD` back** — "the hub has it" is a fact read from the hub, not an assumption
  made after a write.
- **`http`** — real, and the **ONE egress destination in the entire plugin**: the Atlas hub
  at `$ATLAS_HUB_BASE`, default `https://atlas.not.rest`, and nothing else, ever. It sends
  **by delegation**: the wire (schema `atlas-hub` v1, per
  `briefs/atlas-contract/SCHEMA-v1.md`) and the POST live in
  `plugins/notrest/skills/atlas/scripts/atlas_wire.py`, so the bank hands over exactly once
  and the bank script itself still imports no network module. eval's NETWORK-EGRESS names
  every doorway to that base on every run — the auth client, the wire module, the bank's own
  push, and the MCP read server, each re-proved to take its base from the environment — and
  **no hook ever waits on the network**. What goes up is the **banked** snapshot whenever the
  commit already has one, never today's re-derivation, so a replay of one commit is not new
  news. The bearer is the ingest secret read **by path** from
  `${NOTREST_HOME:-~/.notrest}/credentials/atlas-ingest-<project>` (the 4.8
  `${NOTREST_HOME:-~/.notrest}/credentials/atlas-token` is still read, with one warning to
  stderr). Redirects are refused — a 3xx would resend the bearer to whatever host it named —
  and plain http is refused for anything but loopback. A 201 is receipted 0600 at
  `${NOTREST_HOME:-~/.notrest}/atlas-push-<project>.json`, and `status` reads **that receipt,
  never the hub**: it can therefore say what this machine sent without a view secret, and it
  names the hub's ~2 min edge-cache window instead of calling a cache RED. With no secret on
  the box the push refuses by PATH and the bank still exits 0 on a green board —
  `http — no ingest secret at <path>`. `[cited — probed 2026-09-06, after I2]`
- **`none`** — the default. "No hub configured" is a *state*, not a failure: the bank still
  exits 0 on a green board.

**Secrets by path, never by value.** Every credential in this skill is named by the file
that holds it and is read at the moment it is used: the identity token at
`${NOTREST_HOME:-~/.notrest}/atlas-token`, the push secret at
`${NOTREST_HOME:-~/.notrest}/credentials/atlas-ingest-<project>`, the read secret at
`${NOTREST_HOME:-~/.notrest}/credentials/atlas-view`. No secret is ever printed, logged,
put in argv, an env value, a URL, or a commit — the fixtures grep their own output for the
value they minted, so the claim is armed rather than asserted. The hub contract these paths
serve is `briefs/atlas-contract/HUB-CONTRACT.md`.

**The bound, stated plainly.** Everything here has been proven against
`plugins/notrest/skills/atlas/scripts/mockhub.py` on 127.0.0.1 — the mock the fixtures
start and stop themselves. The **live Atlas hub is unproven from this estate** until the
owner puts the ingest and view secrets on the machine and a live arm returns an exit code.
Until then nothing in this skill says "live", and a hub answer is labeled, never believed.
`[unverified — live hub pending the owner's wiring]`

## The snapshot and the board

`atlas/snapshots/<commit>.json` is written once, `0444`, and **never rewritten**. A re-bank
of the same commit re-derives, compares, and *reports that today's derivation differs* —
then leaves the snapshot standing. History is what the estate looked like when that commit
landed; a new state needs a new commit.

The estate's live board is `atlas/board.json`: graph's file graph, its river, and
archivist's records card — **counts only, never statement text**, because the board is the
thing that leaves the estate and a finding's text is not the hub's business. (Both
collectors are `plugins/notrest/skills/graph/scripts/graph.py`'s own outputs.) Each
collector is bounded (`--board-timeout`) and, when it fails or times out, says **stale** out
loud with the reason. It never invents a number and it never fails the bank.

## The access ring — the owner's break-glass

The keyring is `plugins/notrest/.access/keys.sha256` — one line per key,
`sha256(key):label:YYYY-MM-DD`. The key itself is never stored, so minting prints it exactly
once and revocation is deleting the line. Without a valid token **or** key on a machine,
this hook and the harness's other hooks exit **silently**.

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
When a token rather than the ring opened the gate the line gains a trailing ` via=token`, so
a reader can tell WHICH door answered without the token leaving the machine. A hook matches
the `notrest-access: ok ring=` prefix verbatim before it does anything, and may pin the
`ring=` digest and the `path=`. The keyring must be a **regular file**: a symlinked ring is
refused (exit 7, with the reason) because a re-pointable ring is a re-pointable gate.

State the bound honestly whenever it comes up: **the gate controls the harness on a
machine, not the source files.** Anyone holding a copy of the repository holds the source.
It is a belt beside the private-repo braces, and it is never described as more than that.

## The MCP read server

`plugins/notrest/skills/atlas/mcp/server.mjs` is Atlas's own read-only MCP server, vendored
byte-exact (its licence line is the second line of the file and is never edited). It
exposes eleven tools — `atlas_projects`, `atlas_project`, `atlas_subtree`,
`atlas_relevant_context`, `atlas_blockers`, `atlas_findings`, `atlas_history`,
`atlas_diff`, `atlas_objective`, `atlas_playbook`, `atlas_search` — and **every one is a
read**. Nothing it offers can write to an estate.

`plugins/notrest/skills/atlas/mcp/atlas-mcp.sh` launches it: it exports the *name* of the
view-secret file (never its contents), passes `$ATLAS_HUB_BASE` through untouched rather
than keeping a second copy of the default, and when node is missing or older than 22 it
prints exactly one stderr line and exits 6 — a soft dependency named, not a broken harness.
Registration is `plugins/notrest/.mcp.json`; unlike this page it is **not** live-reloaded, so
a running session needs `/reload-plugins` or a restart to see it.

## Honesty rules

- **Derived, never invented.** Every field on the map traces to an exit code, a commit, or
  a pushed snapshot. Unknown is printed as unknown; a stale collector says stale.
- **A green check is not evidence.** If the evidence is `none`, the status is not `done` —
  no exceptions, no "but it obviously works".
- **A dead collector is not a red part.** A board source that timed out is *stale*, and it
  never turns into a claim about the estate's parts. (Same law as watch's dead source.)
- **Never rewrite a snapshot.** A wrong snapshot is corrected by the next commit's
  snapshot, the way the append-only ledgers correct with a new line. History stays.
- **A refusal names one fact.** `RED token: expired at …` — never "invalid", never a stack
  trace, and never the value that was refused.
- **Every test and gate runs in a clean environment.** The bank strips every `GIT_*`
  variable (allowlist: `GIT_TERMINAL_PROMPT`, `GIT_SSH_COMMAND`, `GIT_SSH`) and the
  re-entrancy marker from the subprocesses it runs — including its own `git` calls — and
  passes the estate root explicitly. A hook hands its children `GIT_DIR`/`GIT_WORK_TREE`,
  and a `TEST:` that inherited them would read and *commit to* whichever repository fired
  the hook rather than the one it was given. Write tests that take their repo from the
  working directory, not from the environment.
- **The bank never writes what it did not measure**, never commits, never stages, and
  never edits a file the estate authored.
- **Say what did not run.** `--dry-run` and `--no-board` produce visibly incomplete boards
  and label themselves as such.

## Self-check before finishing

- The bank ran through the script — the status law was not re-derived by hand or
  paraphrased into chat.
- Every `done` on the board has `evidence: passed` from a test that could fail; every
  demotion was reported by name, not smoothed away.
- The snapshot for this commit exists, is `0444`, and was not rewritten; if the derivation
  differed from it, that was said.
- The board's stale collectors were named with their reasons; no count was carried over
  from a previous run as if it were fresh.
- The push line says which adapter ran, and for `http` which hub it named and whether the
  live arm has ever returned an exit code.
- No secret was read to be shown. Anything about a credential was said by PATH.
- `wire` was idempotent (a second run said "already wired") and no foreign post-commit
  hook was overwritten.
- The born-red proof ran in a scratch repo and actually **went red** at step two.
- If the estate has a COORD ledger, one append-only line records the bank — `COORD.md` is
  append-only and is never hand-edited:
  `- [YYYY-MM-DD HH:MMZ] [atlas] banked <commit12> — N parts, X done, Y failing | evidence: atlas/snapshots/<commit>.json`

## Finishing up

Give the headline in chat — *banked `<commit12>`, N parts, X done, Y failing, board
green/RED, pushed or not and why* — plus the snapshot path. Don't paste the JSON. If the
door was involved, say which one answered (token or ring) and never the value of either.

Chains:
- **`/eval` and `/doctor`** — the gates atlas banks are the same gates
  `plugins/notrest/skills/eval/scripts/eval.py` and
  `plugins/notrest/skills/doctor/scripts/doctor.py` run. atlas records *when* they were
  green; eval decides *whether the laws hold*.
- **`/graph`** — the board's file graph and river are graph's own outputs; open them there
  when a part's neighbourhood is the question.
- **`/archivist`** — the records card on the board is the store's four-box count. A part
  that keeps going red is a finding waiting to be banked.
- **`/refuter`** — the hooks and the identity gate are kernel surfaces; a change to either
  ships through a refuter round, and the born-red proof is the arm that catches a detector
  which cannot detect.
- **`/sessionend`** — an unbanked HEAD belongs in the handoff: the next session inherits a
  map that is honest about what it does not yet know.
