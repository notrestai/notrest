# Commission 4.9 · A9 · the Atlas MCP read server inside the plugin — model: opus (tier: judgment; registration is unproven)

Read COMMON first. Contract: IDENTITY-CONTRACT.md §5 (the 11 tools, auth by token file), RULINGS §4 (node ≥ 22
soft dependency). The file: briefs/atlas-contract/mcp/server.mjs (read its header: ENV, FLAGS, fixture mode).

**Do:**
1. Vendor byte-exact: `plugins/notrest/skills/atlas/mcp/server.mjs` (shasum equality in your return).
2. `plugins/notrest/skills/atlas/mcp/atlas-mcp.sh`: a wrapper that sets `ATLAS_VIEW_FILE` default to
   `${NOTREST_HOME:-$HOME/.notrest}/credentials/atlas-view` (the server reads that name today; the token file comes
   with hub phase I-B — leave a one-line comment), `ATLAS_HUB_BASE` pass-through, checks `node` ≥ 22 and prints
   ONE line `[notrest] atlas mcp: node >= 22 required (found <v|none>)` to stderr + exit 6 if not, else exec node.
3. Registration: find out how a Claude Code plugin declares an MCP server (`.mcp.json` at the plugin root, or a
   `mcpServers` field in plugin.json — check the plugin docs via the claude-code-guide agent if needed: `model:
   "sonnet"` for that lookup, declare it) and add the declaration for `atlas` pointing at the wrapper with a
   RELATIVE plugin path. Then PROVE what happens on THIS machine (skills-dir): does `claude mcp list` show it after
   a reload? If skills-dir does not load plugin MCP declarations, say so as an OPEN with the evidence — do not pretend.
4. `doctor`: add ONE check `check_atlas_mcp` in `plugins/notrest/skills/doctor/scripts/doctor.py`: node present and
   ≥ 22 → ok line; absent/old → a single WARN line (never a failure; doctor's exit code must not change for the
   node case). Add its arm to doctor's own fixture if one exists.
5. Fixture `plugins/notrest/skills/atlas/mcp/fixture-mcp.sh`: `ATLAS_MCP_FIXTURE=1` drive of the server over stdio:
   `initialize` → serverInfo name `atlas`; `tools/list` → 11 tools; `tools/call atlas_projects` → `demo` row present
   (the `kernel` fixture wire is not vendored — that is expected; say so); `atlas_relevant_context(demo, "token
   rotation")` → ≤ 3900 bytes and `matched_on` non-empty; the bearer never appears in output. `--selftest` will
   report kernel failures because `hub/fixtures/kernel-wire1.json` is not here — record that as a known bound,
   do not vendor a kernel fixture and do not edit the server.

**TOUCH-ONLY:** the `mcp/` dir (new), the MCP declaration file at the plugin root (new or the one field),
`doctor.py` (one function + its registration), doctor's fixture. **DONE-WHEN:** `bash plugins/notrest/skills/atlas/mcp/fixture-mcp.sh` → exit 0
AND `/usr/bin/python3 plugins/notrest/skills/doctor/scripts/doctor.py check` → exit ≤ 5.
