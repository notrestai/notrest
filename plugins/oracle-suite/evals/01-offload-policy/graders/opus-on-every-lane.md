---
type: llm
weight: 1
---

Every delegation call in the response pins the model to opus explicitly.

PASS if: the response writes out subagent/delegation calls, and each one carries an
explicit model parameter whose value is opus (e.g. `model: "opus"`).

FAIL if: any written call omits the model parameter; or leaves it as "default",
"inherit", or the seat's own model; or sets it to sonnet, haiku, or fable; or the
response writes no concrete calls at all. Saying opus should be used somewhere in prose
while leaving a call unpinned is a FAIL — the parameter has to be on every call.
