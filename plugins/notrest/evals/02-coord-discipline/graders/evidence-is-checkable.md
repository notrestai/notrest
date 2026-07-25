---
type: llm
weight: 1
---

The close-out produces one append-only coordination-ledger line, not a description of
one, and its evidence field points at something checkable.

PASS if: the response records a single line carrying all four of — (a) a UTC timestamp,
(b) a session or lane tag, (c) what was asked and what actually landed, and (d) an
evidence token a third party could check: the exit code, the passing test count, the
test path, a commit, or a file path.

FAIL if: no such line is recorded; or the line has no evidence field; or the evidence is
an assertion rather than a checkable artifact ("works now", "should be fine", "verified");
or the response only explains the ledger discipline without producing the line; or it
claims work landed that the user did not report.
