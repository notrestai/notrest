# Atlas contract files — received by cross-session message from the Atlas seat (atlas-ce)

Verbatim copies, banked the moment they arrived, because /work/atlas (the NAS) is not mounted on
the plugin seat's machine and the Atlas repo has no remote. Provenance per file:

| file | source | commit on the Atlas side | received |
|---|---|---|---|
| IDENTITY-CONTRACT.md | /work/atlas/IDENTITY-CONTRACT.md | 192b6f5 | 2026-09-06, message 1 of 3 |
| HUB-CONTRACT.md | /work/atlas/HUB-CONTRACT.md | 14fb684 | 2026-09-06, message 2 of 3 |
| SCHEMA-v1.md | /work/atlas/hub/SCHEMA-v1.md | (not stated) | 2026-09-06, message 3 of 3 |
| kit/to-wire.py | /work/atlas/kit/to-wire.py | 9755517 | 2026-09-06; 403 lines, 16057 bytes, sha256 887eb618… VERIFIED on save; compiles. Reference converter for the KERNEL snapshot shape (modules/nodes/tests/MODULE-MAP) — lane A5 writes the plugin's own converter to the same laws |
| mcp/server.mjs | /work/atlas/mcp/server.mjs | 9755517 | 2026-09-06, four chunks reassembled; 928 lines, 50107 bytes, sha256 6479dfda… VERIFIED; `node --check` ok on node v25 |
| kit/verify-token.py | /work/atlas/kit/verify-token.py | 7b11e86 | 2 chunks reassembled; 562 lines, 19826 bytes, sha256 5679cb1d… VERIFIED; compiles under /usr/bin/python3 3.9.6 |
| kit/test-verify-token.sh | /work/atlas/kit/test-verify-token.sh | 7b11e86 | 2 chunks; one blank line lost in transit before line 210 and restored by hash search; 407 lines, sha256 5d2251c1… VERIFIED; `bash -n` ok |
| kit/fixtures/tokens/rfc8032-7.1.json | /work/atlas/kit/fixtures/tokens/rfc8032-7.1.json | 7b11e86 | 27 lines, 1486 bytes, sha256 d995ba33… VERIFIED (static RFC vectors, not credentials) |
| kit/README-verify-token.md | /work/atlas/kit/README-verify-token.md | 7b11e86 | 187 lines, 10019 bytes, sha256 b859cd95… VERIFIED |

These are the build targets for DOCKET-4.9 lanes. Defects against them are filed to the Atlas
seat by message, naming the section; the Atlas seat revises in place and logs the revision.

## Verification on the plugin seat's Mac (2026-09-06)

Every file above: line count, byte count and sha256 equal to the values the Atlas seat stated
with each message. Independent probes beyond the hashes: `python3 -m py_compile` on both python
files under /usr/bin/python3 3.9.6; `node --check` on server.mjs under node v25; RFC 8032 §7.1
TEST 1 typed from the RFC (not from the fixture) verifies and a tampered message is rejected;
`bash kit/test-verify-token.sh` run here: **38 passed, 0 failed**, mean verify inside the 100 ms
hook budget. Generated fixtures are gitignored in `kit/fixtures/tokens/`; only the static RFC file
is tracked.

These are RECEIVED copies. The 4.9 lanes vendor them into the plugin (with the license line kept
verbatim) — nothing under `plugins/notrest/` changes until the owner approves the docket.
