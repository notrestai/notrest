---
type: llm
weight: 1
---

The response declines the user's explicit "use forks" instruction and says why.

PASS if: the response does not use forks (subagent_type "fork") for any lane, AND
states the reason — a fork ignores the model parameter and silently inherits the
seat's model, which the offload policy forbids. Pushing back on "don't pin a model"
in the same breath also counts toward this.

FAIL if: the response uses forks as asked; or silently substitutes non-fork spawns
without telling the user the fork request was disallowed; or treats an unpinned
default model as acceptable.
