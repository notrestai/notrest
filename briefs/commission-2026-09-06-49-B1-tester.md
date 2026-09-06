# Commission 4.9 · B1 · TESTER — model: opus (tier: judgment) — finds only, never fixes, never edits product code

Read COMMON (+Amendments), docs/DOCKET-4.9.md, the three contract files under briefs/atlas-contract/ (3f4390f), and every
`fixture*.sh` under plugins/notrest/skills/atlas/. You are the second builder: you own tests and your report, nothing else.
**Attack the integrated build end to end, red-first, in your OWN file** `plugins/notrest/skills/atlas/scripts/fixture-e2e.sh`
(new) against mockhub.py on 127.0.0.1, in a sandboxed HOME/NOTREST_HOME/GIT_CONFIG_GLOBAL (never the real store, never the real
gitconfig): the whole journey a consumer takes — `atlas.py login` (auto-approve) → token 0600 + helper installed (amended §9 line,
decline-on-missing) → `key --check --quiet` sentinel with ` via=token` → hooks admit (estate-root.sh exits 0 with a token and NO
ring key) → establish `--atlas` in a scratch estate → `bank` with adapter http → 201, hub_commit == head, board pushed, replay
idempotent → revoke the jti on the mock → `atlas_auth.py sessionstart` → `key --check` exits 7 `jti: revoked` → the ring key
alone still admits (break-glass) → expired token + no ring → 7 → SessionStart hook keyless prints the one remedy line naming
atlas.py login → the MCP wrapper refuses node < 22 (fake PATH) and serves tools/list otherwise. Plus the negative space: token
in a URL never appears in any log; the ingest value never appears; a token from a foreign key → 7 `signature: invalid`; a wrong
`mid` → 7; `roaming` → 0; two machines sharing a token file → the second's fingerprint fails. Every arm names the contract
section it proves. **Report** (your RETURN) lists every defect as `file:line · one fact · the arm`; do NOT fix anything —
the seat routes each to its lane. Also state which contract sections have NO arm anywhere (coverage gaps).
**TOUCH-ONLY:** `fixture-e2e.sh` (new). **DONE-WHEN:** `bash plugins/notrest/skills/atlas/scripts/fixture-e2e.sh` → exit 0 with
`0 failed`, OR a report of the failing arms with the defect list (a red arm on a real defect is a PASS for the tester).
