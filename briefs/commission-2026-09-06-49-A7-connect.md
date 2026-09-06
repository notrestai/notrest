# Commission 4.9 · A7 · the connect text — model: opus (tier: judgment; user-facing, served verbatim by the hub)

Read COMMON first. Contract: IDENTITY-CONTRACT.md §10 (bootstrap: the exact ordered steps, helper BEFORE any
marketplace command), §9 (the helper line, verbatim), §1 (device flow = headless path); HUB-CONTRACT.md §3 (secret
files by path). Also read NOTREST-ON-THE-NAS.md (the current hand-carried flow this replaces) and
docs/DOCKET-4.9.md "The change in one paragraph".

**Write** `docs/ATLAS-CONNECT.md` — the text the Atlas MCP tool `atlas_connect` returns and the portal's "connect
Claude Code" page prints. Two audiences, two sections, each a numbered list of runnable commands with one sentence
of why per step, nothing else:
- **A · Claude Code with a browser** (the MCP path): the token arrives from `atlas_connect`; step 1 write it to
  `${NOTREST_HOME:-~/.notrest}/atlas-token` 0600 (dir 0700) — show the exact `umask 077 && mkdir -p … && printf` form
  that avoids a trailing newline problem; step 2 the §9 helper line verbatim; step 3 marketplace add of
  `https://atlas.not.rest/git/notrest.git`; step 4 install `notrest`; step 5 verify: `python3 ~/.claude/plugins/…/atlas_token.py check`
  (state the real path a marketplace install uses — find it in the plugin's docs/doctor, do not guess) → `atlas-token: ok`;
  step 6 open a new session; the first line reads `[notrest] v4.9.0 …`.
- **B · Headless (NAS, containers)**: clone via the helper after login is impossible before the plugin exists, so:
  the owner-provided one-file `atlas_auth.py` is NOT assumed — instead: step 1 the §9 helper line with a token the
  user pastes from the portal's device page (the portal shows the token once after `/activate`), then the same
  marketplace steps, then `atlas_auth.py login` from the installed plugin for the machine-bound token; state the
  order and why (the pasted token is `roaming` scope; login replaces it with a `mid`-bound one).
- **What must never happen** (four lines): token in a URL; token in a commit; the marketplace command before the
  helper; two machines sharing one token file.
- **Exit codes** the user will see (from COMMON) and the one banner line when keyless (from A6's commission).
Every command must be runnable as written on macOS and Linux; the seat runs a dead-reference lint on the file.
Write with the plugin's voice: short declaratives, no marketing, no "simply".

**TOUCH-ONLY:** `docs/ATLAS-CONNECT.md` (new). **DONE-WHEN:** `python3 plugins/notrest/skills/sessionend/scripts/starthere_lint.py check --file docs/ATLAS-CONNECT.md --root .` → exit 0 (cite paths that exist or none).
