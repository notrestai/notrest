# DOCKET 4.9 — WAVE A — the common brief every lane reads first

*Owner approved 2026-09-06 ("start the docket 4.9 yes"). Docket: docs/DOCKET-4.9.md. Contract files
(verbatim, hash-verified): briefs/atlas-contract/. The seat is the notrest Director (Fable); you are
one lane of eight running in parallel. Read THIS file, then your own commission, then only the
contract sections your commission names.*

## Laws (non-negotiable)

1. **TOUCH-ONLY.** Edit only the paths your commission lists. New files only where it says. Never
   edit `plugins/notrest/skills/atlas/scripts/atlas.py` — the seat wires your module into it at
   integration. Never edit hooks unless you are lane A6.
2. **Vendored files are byte-exact.** Anything copied from briefs/atlas-contract/ keeps its first
   line (the Atlas license line) verbatim and is never modified. If it does not fit, wrap it, do
   not edit it. Prove byte-equality with `shasum -a 256` in your return.
3. **Secrets by path, never by value.** No token, key, or secret is ever printed, logged, put in
   argv, an env value, a URL, or a commit. Fixtures generate their own throwaway keys.
4. **/usr/bin/python3 (3.9), stdlib only** for anything a hook may import. No pip, no third-party.
5. **Red-first arms.** Every guard you add gets a fixture arm that FAILS without it. Your
   done-when is a command the seat runs; its exit code is the verdict.
6. **This machine runs notrest@skills-dir.** NEVER run the consumer install flow
   (marketplace add / plugin install) here — the pretool gate refuses it; do not try to override.
7. **No network in fixtures** except 127.0.0.1 (the mock hub). The live hub is out of scope for
   wave A (Atlas sits in a sandbox; the owner will wire it).
8. **Return tight**, in the format below. No prose tour of what you read.

## Fixed interfaces (the seat's; do not redesign — file a defect if one is wrong)

- `HOME = os.environ.get("NOTREST_HOME") or os.path.expanduser("~/.notrest")`
- Identity token: `HOME/atlas-token` (0600). Legacy: `HOME/access-key` may hold EITHER the ring key
  (starts with `nrk_`) OR, during transition, a JWT (three base64url segments). Rule: a value with
  exactly two dots and a header that parses as `{alg: EdDSA}` is a token; otherwise ring.
- Ingest secret (push): `HOME/credentials/atlas-ingest-<project>`; legacy `HOME/credentials/atlas-token`
  read with ONE warning to stderr. View secret: `HOME/credentials/atlas-view`.
- JWKS cache: `HOME/atlas-jwks.json`; revoked cache: `HOME/atlas-revoked.json`; machine id (containers
  only): `HOME/machine-id` (32 random bytes hex, 0600, written once).
- Fingerprint (RULING): `sha256(machine_id)` hex where machine_id = Linux `/etc/machine-id`
  (fallback `/var/lib/dbus/machine-id`) → macOS `IOPlatformUUID` via
  `ioreg -rd1 -c IOPlatformExpertDevice` → else the persisted random id. **Hostname is never an input.**
- Hub base URL: `ATLAS_HUB_BASE` env, default `https://atlas.not.rest`. Mock: `http://127.0.0.1:<port>`.
- Module layout (new files, all under `plugins/notrest/skills/atlas/scripts/`):
  `atlas_token.py` (A2) · `atlas_auth.py` (A3) · `mockhub.py` (A1) · `atlas_helper.py` (A4) ·
  `atlas_wire.py` (A5) · `vendor/verify_token.py` (A2, byte-exact copy of
  briefs/atlas-contract/kit/verify-token.py) · `vendor/__init__.py` (empty).
  MCP: `plugins/notrest/skills/atlas/mcp/server.mjs` (A9, byte-exact) + `atlas-mcp.sh` wrapper.
- Public functions (signatures are the contract between lanes):
  - `atlas_token.read_token(home) -> str|None` · `machine_id(home) -> str` · `fingerprint(home) -> str`
    · `load_keys(home) -> dict[kid, bytes]` (pinned `PINNED_JWKS` constant, initially `{"keys": []}`, merged
    with the cache) · `load_revoked(home) -> dict|None` · `verdict(home, now=None) -> (ok: bool, reason: str, claims: dict|None)`
    where reason is the verifier's one-fact string or `token: absent` / `keys: none pinned or cached`.
  - `atlas_auth.device_login(home, base, out=sys.stderr) -> dict claims` (raises `AuthError(reason)`) ·
    `refresh(home, base, timeout=2.0) -> bool` · `fetch_jwks(home, base, timeout=2.0) -> bool` ·
    `fetch_revoked(home, base, timeout=2.0) -> bool`. All silent on failure (return False), never print values.
  - `atlas_helper.credential_fill(stdin_text, home, hub_host) -> str` (git credential protocol) ·
    `install(hub_url) -> bool` (writes the §9 line via `git config --global`) · `check(hub_url) -> bool`.
  - `atlas_wire.to_wire(snapshot: dict, project: str, board_url: str|None) -> (wire: dict, report: dict)` ·
    `push_http(snapshot, board_html, credential_path, base, project, timeout=60) -> (ok: bool, hub_commit: str|None, reason: str)`.
  - `mockhub.py --port N [--auto-approve-after K] [--mode ok|expired|denied|slow]` and `--selftest`.
- Exit codes stay the plugin's: 0 ok · 7 no valid key/token · 5 red · 6 not established/unbanked.

## Return format (paste exactly; the ledger hook banks the card)

```
RETURN — lane <id> · <name>
FILES: <path> (new|edited, +N/-M) …
DONE-WHEN: <the command> → exit <n>   (paste the last 3 lines of its output)
VENDORED: <path> sha256 <hash> == briefs/atlas-contract/<path> sha256 <hash>   (if any)
DEFECTS IN THE CONTRACT: <section: one fact> … or none
OPEN: <what you could not verify and why> … or none
CARD: TESTS <n ran, n passed> · OPEN <n> · FINDINGS <n> · LEARNINGS <one line each, or none>
```

## Amendments (seat, during the wave — every lane applies them at its gate)

- **HOME (A2 defect, accepted):** `HOME = os.path.expanduser(os.environ.get("NOTREST_HOME") or "~/.notrest")` —
  the env value is expanded too, matching atlas.py's `notrest_home()`. One home for the hook and the script.
- `verdict` reason on success is the string `"ok"`.
- `PINNED_JWKS` stays empty until Atlas publishes its signing key (hub phase I-A); the seat fills it at the ship.
  Until then a machine with no JWKS cache reads `keys: none pinned or cached` — that is the truthful state.
