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
- HUB-CONTRACT §3 · still says the default credential path is `~/.notrest/credentials/atlas-token`, which RULINGS §2
  superseded with `credentials/atlas-ingest-<project>`; the banked §3 text is stale on the Atlas side too if unamended · A5.
- HUB-CONTRACT §4 · no row for a `not-run` evidence (a part whose test was skipped, e.g. a dry run); the plugin maps it to
  `wip/unverified` (a verdict nobody took is not a proof) — confirm or add the row · A5.
- HUB-CONTRACT §2 · `<project>` must match `[a-z][a-z0-9-]{0,31}` but no refusal code is named for a bad one (a bare 404
  today); the plugin refuses client-side before sending · A5.
