# Atlas contract files — received by cross-session message from the Atlas seat (atlas-ce)

Verbatim copies, banked the moment they arrived, because /work/atlas (the NAS) is not mounted on
the plugin seat's machine and the Atlas repo has no remote. Provenance per file:

| file | source | commit on the Atlas side | received |
|---|---|---|---|
| IDENTITY-CONTRACT.md | /work/atlas/IDENTITY-CONTRACT.md | 192b6f5 | 2026-09-06, message 1 of 3 |
| HUB-CONTRACT.md | /work/atlas/HUB-CONTRACT.md | 14fb684 | 2026-09-06, message 2 of 3 |
| SCHEMA-v1.md | pending (message 3 of 3) | | |
| verifier (kit/verify-token.py + fixture) | pending (message 4, when its lane lands) | | |

These are the build targets for DOCKET-4.9 lanes. Defects against them are filed to the Atlas
seat by message, naming the section; the Atlas seat revises in place and logs the revision.
