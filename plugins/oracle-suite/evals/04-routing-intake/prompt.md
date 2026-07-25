---
name: routing-intake
description: A "hey oracle" intake ask that also dangles an easy question to answer.
tags: [routing, intake, oracle]
runs: 2
max_turns: 6
timeout_seconds: 240
allowed_tools: [Skill]
expected_outcome: >
  The intake starts — one question is put to the user (Objective) and the turn stops —
  instead of the queue-library question being answered on the spot.
---

hey oracle — I'm trying to work out which job-queue library to use for a side project.
