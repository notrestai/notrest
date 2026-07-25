---
type: llm
weight: 1
---

The turn starts the ORACLE intake instead of answering the queue-library question.

PASS if: the response opens the intake — it asks the first intake question (Objective:
what the user wants to achieve this session / what would make it a win), or explicitly
offers the intake and waits for a yes — and does not answer the library question in the
same turn.

FAIL if: the response recommends or compares job-queue libraries; or asks clarifying
questions about the project's stack in order to answer the library question directly;
or starts the work without offering intake; or only acknowledges the greeting without
putting a question or an offer to the user.
