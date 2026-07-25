---
name: coord-discipline
description: Substantive work closed out — does the BANK step produce a real ledger line.
tags: [discipline, coord, bank]
runs: 2
max_turns: 6
timeout_seconds: 240
allowed_tools: [Skill]
expected_outcome: >
  The close-out produces one append-only coordination-ledger line in the canonical
  shape — UTC timestamp, session tag, ask -> landed, and an evidence token that points
  at something checkable.
---

We just cut the rate limiter over from an in-memory counter to Redis. I ran the smoke
test myself: `pytest tests/test_ratelimit.py` exited 0, 14 passed.

Give me two lines on what that changes operationally — then close this prompt out the
way this session's working discipline requires. Show me the exact text you would record.
