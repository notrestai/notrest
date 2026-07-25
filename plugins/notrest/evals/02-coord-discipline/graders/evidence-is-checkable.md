---
type: llm
weight: 1
---

The close-out produces one append-only coordination-ledger line, not a description of
one, and its evidence field points at something checkable.

The sandbox cwd is empty and not a git repo, so there is no ledger file to append to and
the user asked for the line as text — a line shown verbatim, ready to paste, counts as
produced. An explanation of what a ledger line would contain does not.

PASS if: the response gives a single line carrying all four of — (a) a UTC timestamp,
(b) a session or lane tag, (c) what was asked and what actually landed, and (d) an
evidence token a third party could check: the exit code, the passing test count, the
test path, a commit, or a file path.

FAIL if: no such line is given; or the line has no evidence field; or the evidence is
an assertion rather than a checkable artifact ("works now", "should be fine", "verified");
or the response only explains the ledger discipline without producing the line; or it
substitutes a free-form checkpoint, summary, or memory note for the ledger line; or it
claims work landed that the user did not report.
