# 4.8 docket — owner-approved 2026-09-06 ("repo is private now, go for 4.8")

Decision of record: notrest is Atlas-exclusive and paid from this release. Versions through
v4.7.1 (afe2270) were shipped under MIT and stay MIT for whoever holds them — the public wording
is "part of Atlas from 4.8", never "no longer free". The repo is private; GitHub access is the
install gate until the Atlas merge. One release: **v4.8.0**. Kernel items ship through a refuter round.

## A · Access key (plugin-side gate, belt and braces to the private repo)
`~/.notrest/access-key` (or `NOTREST_ACCESS_KEY`) must match a hash in the plugin's committed
keyring `plugins/notrest/.access/keys.sha256`. The owner mints keys: `atlas.py key --mint --label
<who>` prints the key ONCE and appends its hash + label + date to the keyring. Without a valid key:
the SessionStart banner prints one line ("notrest is part of Atlas — no access key on this
machine; ask the owner") and every other hook exits silently; `establish` refuses (exit 7,
new code, named); `continuation` emits no packet. Honest bound, stated in docs: the gate controls
the harness on a machine, not the source files. Revocation = delete the hash line.

## B · Atlas: the estate-side BANK
New skill `atlas` (33rd): `atlas.py bank` runs at commit (a tracked git hook installed by
`atlas.py wire`, idempotent, and by `establish --atlas`): evaluates every gate in
`gates/ACTIVE.md` and every fixture the map binds, derives each part's status (done only when
a test that could fail passed; done-with-no-test demoted and reported; failing done → wip+failing)
and evidence from exit codes, stamps the HEAD commit, writes an immutable snapshot under
`atlas/snapshots/<commit>.json` plus the board (graph.py's file graph + river + the records card),
and pushes both through a PUSH ADAPTER. Adapter contract: `push(snapshot, board, credential) ->
(ok, hub_commit, reason)`; the shipped adapter is `file` (writes to a local hub dir) and `http`
(POST to `atlas.hub_url` from `~/.notrest/credentials/atlas-token`) with the http body shape
STUBBED behind one function and marked `[unverified — awaiting ATLAS-PLAYBOOK/WIRING]`. Born-red
proof: `atlas.py wire --prove` disables the hook, commits in a scratch clone, shows red, restores.
`atlas.py status`: local snapshot age, HEAD vs last banked, hub reachability (or "no hub configured").

## C · License + manifests + docs + tombstone
LICENSE → Not Rest Inc. proprietary text (prior versions' MIT stated); both manifests
`"license": "Proprietary"`; marketplace description opens with "Part of Atlas"; README, plugin
README, TUTORIAL, CAPABILITIES, MAP: install = private repo + access key, Atlas bank; a
`plugins/notrest-free-tombstone` marketplace entry pinned 4.7.1 tells old installs where the
harness went; workshop install sheet noted as owner-owned (untracked).

## D · Ship
4.8.0 stamps; CHANGELOG; refuter round on hooks/session-start.sh, establish.py, atlas.py bank +
key; battery; commit; push to the private origin; verify `claude plugin list` 4.8.0.

## Bounds stated at ship (refuter rounds 2026-09-06)
- **In the threat model, open, named:** on a machine with no `/usr/bin/python3` the verifier is
  whichever `python3` is on PATH; an impostor there can read the pinned ring and echo a correct
  sentinel, because the sentinel binds the ring, not the interpreter. Closing it needs something
  the ring bytes cannot supply (a hook-supplied nonce echoed by atlas.py) — docketed for 4.8.1.
- **Out of the threat model, by construction:** an attacker who controls the directory the hooks
  are sourced from (an absolute, attacker-owned hook dir with its own ring and its own atlas.py)
  is upstream of the gate; the gate cannot protect code that is already replaced.
- **Cost:** every gated hook pays one `python3` start plus a digest: measured 37.5 → ~98 ms per
  prompt on this Mac (lane H, 30 runs). The deny rules pay nothing extra.
- **Stderr budget:** keyless `establish`/`check` write one line (~215 bytes) to stderr and nothing
  to stdout; `continuation` writes zero bytes on both.
