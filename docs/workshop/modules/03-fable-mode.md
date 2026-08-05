# Module 03 — `/fable-mode` — the posture between the bookends

**15 minutes.** Contains the best live moment in the workshop. Don't spoil it early.

---

## The failure it prevents

The agent says *fixed*. It says *working*, *deployed*, *done*. You believe it, because it
sounded like it knew. Two hours later you find out it wasn't — and the expensive part isn't
the bug, it's that you built on top of the claim.

## Overview — what the verb is

`/fable-mode` is a **behavioural contract**, not a capability. It doesn't make the model
smarter; it changes which reflex fires. Its core is a loop every task runs through:

**ORIENT → PROBE → ACT → PROVE → BANK**

| step | what it means | what it prevents |
|---|---|---|
| **ORIENT** | read the project's own state first | re-deriving what's already written down |
| **PROBE** | read the live system before reasoning about it — read-only inspection is free, spend it | confident answers built on stale assumptions |
| **ACT** | smallest verifiable step; destructive things get shown before they run | big irreversible moves on an unverified premise |
| **PROVE** | evidence in the transcript, or say **unverified** | "done" that wasn't |
| **BANK** | write down what landed, the moment it lands | work that dies with the session |

Two rules from the contract worth naming out loud, because they're the sharp end:

**Prove it at the consumer, not the producer.** The producer's success message is a claim;
the consumer's behaviour is the proof. You wrote the file — does the thing that *reads* it
see it? You deployed — does the route answer?

**The honesty labels.** `[cited]` (read it, this turn) · `[recall]` (remembering, not
reading) · `[estimate]` (derived, not measured) · **`unverified`** (no evidence).

Say plainly: **"unverified" is not an admission of failure.** It's a type annotation on a
claim. The failure is an unlabelled guess wearing a confident sentence.

It's also worth mentioning that this posture is on by default — a session-start hook anchors
it without anyone typing the verb. `/fable-mode` is how you read the full contract.

## Test drive (8 min) — the check that stopped checking

Everyone runs this. It's four commands and the payoff is visceral. **Do not explain first.**

```bash
cd ~/harness-workshop
printf 'hello world\n' > notes.txt
if grep -q "$PATTERN" notes.txt; then echo "PASS"; else echo "FAIL"; fi
```

It prints **PASS**. Now have them destroy the file's contents entirely and run the *same*
check:

```bash
printf 'totally different content\n' > notes.txt
if grep -q "$PATTERN" notes.txt; then echo "PASS"; else echo "FAIL"; fi
```

**PASS again.**

Let it sit. Then explain: `PATTERN` was never set, so the check searched for the empty
string, which matches every line of every non-empty file. It has been passing this whole
time while asserting **nothing at all** — and would pass forever, on any content.

Now fix it and watch it go red:

```bash
PATTERN=hello
if grep -q "$PATTERN" notes.txt; then echo "PASS"; else echo "FAIL (correctly)"; fi
```

**Success condition: they have watched an assertion fail on purpose.**

## What just happened

> **A test that quietly stops testing what it claims is the most dangerous defect class
> there is.** It reports green forever and defends nothing. Before trusting any check, make
> one assertion fail on purpose and watch it fail.

Tie it straight back to module 02: this is *presence is not establishment*, pointed at a
test. The check was present. It was not checking.

Three consequences, one sentence each — people recognise all three immediately:

**Never widen a margin.** A flaky test fixed by raising the timeout now passes because the
machine happened to be fast enough. Remove the clock instead: inject the window the product
uses and assert both extremes.

**Absence of records is not evidence of absence.** "Searched and found nothing" and
"couldn't search" produce identical output.

**Configured is not verified.** A limit that has never been observed firing is unverified
however carefully it was written. *"We set a limit"* and *"the limit stopped it"* are
different claims.

## Facilitator notes

- **The reveal only works if you stay quiet.** If you explain before they run it, it's a
  fact. If they see it first, it's a memory.
- Someone will note that `set -u` or a linter catches unset variables. Agree warmly, then
  widen it: the class is much bigger than unset variables — an assertion polling the wrong
  surface, a pattern that can no longer match, a check on a deleted code path. Tools catch
  a slice; the habit catches the rest.
- **Model the behaviour.** Say "unverified" out loud yourself at least twice during the day.
  If the facilitator never admits uncertainty, the workshop teaches that admitting it is for
  other people.

## Fallback

The demo needs only `grep`, so it survives almost anything. If someone's shell is configured
to error on unset variables, that's a good five seconds: their environment catches this
class and most don't.
