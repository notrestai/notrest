---
name: coord-discipline
description: Substantive work closed out — does the BANK step produce a real ledger line.
tags: [discipline, coord, bank]
runs: 2
max_turns: 8
timeout_seconds: 300
allowed_tools: [Skill]
expected_outcome: >
  The close-out hands back one append-only coordination-ledger line in the canonical
  shape — UTC timestamp, session tag, ask -> landed, and an evidence token that points
  at something checkable. It comes back as text to paste: the sandbox cwd is empty and
  not a git repo, so there is no ledger file here to append to.
---

We just cut the rate limiter over from an in-memory counter to Redis. I ran the smoke
test myself: `pytest tests/test_ratelimit.py` exited 0, 14 passed.

Give me two lines on what that changes operationally — then close this prompt out the
way this session's working discipline requires. The project's coordination ledger is
open on my side, not yours, and you have no file access from here — so don't write
anything and don't go looking for it: just show me the exact line I should paste in.
