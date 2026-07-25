---
type: llm
weight: 1
---

The answer is a shipped script that walks the repo, not the model reading the repo.

PASS if: the response names a concrete command that runs the graph skill's bundled
scanner — graph.py, invoked with a scan over a project root — and presents that script
as the thing that reads the files, so the model never has to pull the project into
context itself.

FAIL if: the response proposes that the model read, glob, or grep the project's files to
work out the links; or proposes writing a new parser or script from scratch; or
recommends an external tool (Obsidian itself, madge, dependency-cruiser, a graph
library) instead of the bundled scanner; or gives only a described approach with no
runnable command.
