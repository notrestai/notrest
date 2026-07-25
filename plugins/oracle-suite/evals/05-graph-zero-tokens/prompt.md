---
name: graph-zero-tokens
description: A file-graph ask — reach for the shipped scanner, or read the repo by hand.
tags: [graph, scripts, token-cost]
runs: 2
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
expected_outcome: >
  The answer is the shipped scanner — graph.py scan over the project root — not a plan
  to read, glob, or grep the project's files and work the links out in context.
---

I want an Obsidian-style file graph of a repo: every file a node, every reference
between files an edge — imports, requires, wikilinks, markdown links, sourced scripts —
rendered as something I can click around in a browser.

How do I get that here? Name the exact command.
