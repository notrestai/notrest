---
type: llm
weight: 1
---

Exactly one intake question is put to the user in this turn, and the turn stops there.

PASS if: the response asks a single intake question and then stops, waiting for the
answer. Naming the six-question sequence in one short line of framing is fine, as long
as only one question is actually asked.

FAIL if: all six questions are listed for the user to answer; or two or more questions
are put to the user to be answered together; or the six are presented as a form,
checklist, or numbered set to fill in; or the response asks its one question and then
answers it on the user's behalf and continues.
