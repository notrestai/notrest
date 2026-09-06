# Atlas contract files — received by cross-session message from the Atlas seat (atlas-ce)

Verbatim copies, banked the moment they arrived, because /work/atlas (the NAS) is not mounted on
the plugin seat's machine and the Atlas repo has no remote. Provenance per file:

| file | source | commit on the Atlas side | received |
|---|---|---|---|
| IDENTITY-CONTRACT.md | /work/atlas/IDENTITY-CONTRACT.md | 192b6f5 | 2026-09-06, message 1 of 3 |
| HUB-CONTRACT.md | /work/atlas/HUB-CONTRACT.md | 14fb684 | 2026-09-06, message 2 of 3 |
| SCHEMA-v1.md | /work/atlas/hub/SCHEMA-v1.md | (not stated) | 2026-09-06, message 3 of 3 |
| kit/to-wire.py | /work/atlas/kit/to-wire.py | 9755517 | 2026-09-06; 403 lines, 16057 bytes, sha256 887eb618… VERIFIED on save; compiles. Reference converter for the KERNEL snapshot shape (modules/nodes/tests/MODULE-MAP) — lane A5 writes the plugin's own converter to the same laws |
| mcp/server.mjs | pending (four chunks) | | |
| verifier (kit/verify-token.py + test + fixtures) | pending (when its suite is green) | | |

These are the build targets for DOCKET-4.9 lanes. Defects against them are filed to the Atlas
seat by message, naming the section; the Atlas seat revises in place and logs the revision.
