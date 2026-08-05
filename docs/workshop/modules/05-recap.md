# Module 05 — `/recap` — the trail, written and read

**15 minutes.** Two halves: how a line gets written, and what reading them back buys you.

---

## The failure it prevents

The session ends, compacts, or dies. Everything it worked out — the two approaches already
tried and rejected, the reason the obvious fix doesn't work, the constraint discovered at
minute forty — goes with it.

The next session starts confident and uninformed, re-derives it badly, and charges you for
the privilege. You've paid for that reasoning twice and got the worse version the second
time.

## Overview — the write side and the read side

**Writing:** one honest line per substantive prompt, the moment its work lands.

```
- [2026-08-04 21:38Z] [session] what was asked -> what landed | evidence: how you know
```

Three parts, all load-bearing. **The ask**, so a stranger knows why the work happened.
**What landed**, so they know where it got to. **The evidence**, so they know whether to
trust it. A line without evidence is a rumour with a timestamp.

Two properties that are the whole design:

**Append-only.** You never edit history. If a line turns out to be wrong you append a
correction — the wrong line stays. A record you can quietly revise is not a record.

**Never compacted — it rolls.** When it gets long the file seals whole and immutable and a
fresh volume opens. Summarising a trail destroys exactly what a trail is for. "Fixed several
auth issues" is what compaction leaves you, and it's worthless to the session that needs to
know *which* and *why that fix*.

**Reading: `/recap`.** The read side of the estate. It walks the ledger, the agent index,
git, and the spend ledger in timestamp order and delivers the project's **decision story** —
a narrated timeline, who was consulted, what shipped, what it cost, what's still open, plus
a clickable decision map. Every claim carries its trail citation.

The critical property: **it derives, it never invents.** Which means `/recap` is only ever
as good as the lines underneath it — and that's why this module teaches both halves.

## Test drive (10 min)

### Part 1: grade three lines (4 min)

Put these up. Let the room grade them before you say anything.

**A** — `- [14:22Z] [me] fixed the bug`

**B** — `- [14:22Z] [me] login returns 500 on empty password -> null guard at auth.py:42 | evidence: repro curl now 401 not 500; 3 new tests pass`

**C** — `- [14:22Z] [me] refactored auth for clarity -> should be much more maintainable now | evidence: looks good`

**A** has a timestamp and nothing else — a rumour with a timestamp.

**B** is the shape. A stranger can act on it: symptom, exact location, two independent
pieces of evidence.

**C** is the one worth the most time. It *looks* like B — all three sections present. But
**"should be" is a prediction wearing the costume of a result**, and *"looks good"* is a
feeling with a colon in front of it.

C is the failure mode your attendees will actually produce. A is too obviously bad to tempt
anyone.

### Part 2: write one, then read them back (6 min)

Have them do a genuinely small piece of work, then note the count, bank a line, and check:

```bash
wc -l < COORD.md
```

…do the work, ask the session to append the ledger line, then:

```bash
wc -l < COORD.md && tail -1 COORD.md
```

**Success condition: the count went up by exactly one, and the line has all three parts.**

Have them read their own line to a neighbour whose only job is to ask: *"could you act on
this if you'd never seen this project?"*

Then:

```
/recap
```

Point out what just happened: **that is what a new session gets for free**, and reading it
costs a fraction of re-deriving it.

## What just happened

The filter for what deserves a line — the **earn-its-line test**:

> Keep a line only if the next session would otherwise **re-explain it, get it wrong, or
> burn tokens rediscovering it.**

That's the whole test, and it matters because a trail nobody reads is overhead. The fastest
way to make one unreadable is to log everything.

## Facilitator notes

- The grading exercise works best with no preamble. Put the three lines up and go quiet.
- If someone argues C is fine because the refactor probably *was* fine — that's the right
  argument to have. The line might be true. It's still unusable, because nothing in it lets
  a reader tell a true one from a false one. The standard isn't "is it true", it's **"can a
  stranger check it."**
- Watch for the count going up by more than one. Usually a hook also wrote something. Name
  it — parts of the trail get written automatically, which is the point.

## Fallback

If the session won't write the line, have them append it by hand — the format is the lesson.
One caution worth passing on: **stamp the time from the clock, not from your head.** A
hand-typed timestamp in this project's own ledger once landed ten minutes in the future,
which put the trail out of order for every later reader.
