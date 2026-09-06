# Defects and questions filed against the Atlas contract files by the plugin lanes (4.9)

Batched by the seat; sent to the Atlas seat by message when the wave lands. Each line: section · one fact · found by.

- IDENTITY §9 helper line · when the token file is missing the shell function still prints `username=atlas` and an
  empty `password=`, so git attempts Basic auth with an empty password and gets a 401 instead of declining; a guard
  (`[ -r "$f" ] || exit 0`) before the echo would make the helper decline cleanly · A4 (fixture arm E asserts the
  current behavior verbatim).
- mcp/server.mjs §fixtureGet `/v1/history` (≈lines 201–203) · guards the project name but not the wire's absence:
  with `hub/fixtures/kernel-wire1.json` missing it reads `snap.taken_at` on `undefined` and the process throws an
  uncaught TypeError, so `--selftest` CRASHES in a vendored location instead of returning the per-tool
  "project: no snapshot stored" the other kernel tools return · A9 (asserted as a bound in fixture-mcp.sh, file not edited).
