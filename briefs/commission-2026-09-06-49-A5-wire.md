# Commission 4.9 · A5 · wire converter + http push — model: opus (tier: judgment; the status/evidence mapping is law)

Read COMMON first. Contract: HUB-CONTRACT.md §1–§6 (adapter, endpoints, credentials, the §4 mapping table,
hub_commit, worked example); SCHEMA-v1.md (every field and refusal); kit/to-wire.py (the KERNEL's converter — the
reference for every mapping judgment, NOT a drop-in: the plugin's snapshot shape differs).

**First** read how `atlas.py` builds its snapshot (`cmd_bank`, the snapshot dict written to
`atlas/snapshots/<commit>.json`, and `atlas/map.md` PART/CLAIM/TEST) — read only, never edit atlas.py.

**Build** `plugins/notrest/skills/atlas/scripts/atlas_wire.py`:
- `to_wire(snapshot, project, board_url)`: one node per PART group (kind `component`; node id = a slug with no `.`
  and no whitespace), parts with `status`/`evidence`/`check` derived by the §4 table EXACTLY (done+passed → done/proven
  with check REQUIRED; done+none → wip/unverified; done+failed → wip/failing; planned → todo with NO evidence key;
  blocked → wip/…); `head` = the snapshot's commit (lowercase hex 7–40); `taken_at` ISO Z; `stamp` = commit subject;
  `playbook "2.0"`; `sources {git, tests, map}`; `findings {count, recurring}` COUNTS ONLY (0 if unknown — never text);
  `links` if board_url. Report: `{downgraded:[…], dropped:[…]}` returned, never silently.
- `push_http(snapshot, board_html, credential_path, base, project, timeout)`: read the secret by path (legacy
  `credentials/atlas-token` → one stderr warning naming the new name); POST snapshot then board per §2 with the header
  built in memory; 201 → `(True, wire["head"], "stored <stored>")`; 200 idempotent → `(True, head, "idempotent")`;
  any other → `(False, None, "<status> <the hub's one-fact error verbatim>")`; network error → `(False, None, "hub unreachable at <base>")`.
  Never retry blind. Never log the bearer.
- CLI: `atlas_wire.py convert SNAPSHOT.json --project P [--board-url U]` (wire JSON on stdout, report on stderr) ·
  `push SNAPSHOT.json --project P --board FILE --credential PATH [--base B]` (exit 0/4, one line).

**Fixture** `fixture-wire.sh` (new): arms with hand-written snapshots — every row of the §4 table produces the wire
row it says; a done part without a check comes out `wip/unverified`, never `proven`; ids contain no `.`; findings has
only count/recurring; a 2.1 MiB body is refused client-side before sending (`413`-shaped reason); push against
`mockhub.py` (A1) → 201 and `hub_commit == head`; replay → idempotent; bad bearer → `401 authorization: bad bearer`
verbatim; a wire with `evidence:"proven"` and no check → the mock's 422 text verbatim; legacy credential name →
warning once; grep arm: the ingest secret value never appears in the fixture log. Also convert THIS estate's latest
real snapshot (`ls atlas/snapshots/*.json | tail -1`) and validate the result against SCHEMA-v1 rules in your own checker.

**TOUCH-ONLY:** `atlas_wire.py`, `fixture-wire.sh` (both new). **DONE-WHEN:** `bash plugins/notrest/skills/atlas/scripts/fixture-wire.sh` → exit 0.
