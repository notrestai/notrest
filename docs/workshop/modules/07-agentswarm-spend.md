# Module 07 — `/agentswarm` and `/spend` — delegate, then audit

**20 minutes.** Two verbs, one story: how work leaves your session, and how you get it back
in a form you can check.

---

## The failure it prevents

You farm work out to sub-agents because your own context is the scarce resource. What comes
back is a wall of text you can't attribute, can't price, and can't audit. You don't know
which model ran it, what it was actually asked, what it cost, or whether the summary you're
reading is a digest or a verdict someone already made for you.

Delegation solved your context problem and bought you an accountability problem.

## Overview — what the verbs are

**`/agentswarm`** is the delegation *arrangement*, not a spawn button. The division of
labour is the design: the seat — your main session — keeps **decompose, judge, apply every
edit, and gate the ship.** Everything else goes to concurrent background lanes.

Four rules, each one there because its absence cost somebody something:

**1 — Every lane declares its model, explicitly.** Not by default, not by inheritance.
Omitting the model isn't a neutral choice that picks something sensible — it silently
inherits whatever the seat is, and bills accordingly. **The omission is the violation.**
That's a genuinely useful way to think about defaults far beyond this tool.

**2 — One persistent lane per domain; feedback resumes it.** The instinct is a fresh agent
per round of feedback. Don't. The lane that wrote the code already holds the context of the
code it wrote, and that context *is* the saving. A fresh spawn pays for it again from zero.

**3 — The commission is never hidden.** Every delegated prompt is banked to disk the moment
the lane finishes. If a lane produced something strange, the first question is *"what did we
actually ask it?"* — and that has to be answerable with the verbatim text, not a paraphrase
written afterwards.

**4 — Synthesis at fan-in is a digest, never a verdict.** When several lanes report, the
summarising step compresses; it does not decide. A summariser that quietly renders verdicts
turns delegation into an oracle you can't cross-examine.

**`/spend`** is the receipt. An append-only ledger of every observed model spend, graded
*observed* or *estimate*, with a report that prints the per-model split — and **exits non-zero
if the routing policy was violated.** That's the point worth dwelling on: it makes the rule
*checkable* rather than merely asserted.

One rule that surprises people: **receipts log themselves. Never hand-log one.** Hand-logging
double-counts, and a spend ledger that double-counts is worse than none, because it's wrong
in a direction that looks responsible.

## Test drive (10 min)

Keep the work genuinely small — the lesson is the paperwork, not the task. Ask the session to
delegate one trivial job to a background lane, naming the model explicitly. Counting the lines
in `README.md` and returning just the number is plenty.

When it finishes, go looking for the paperwork nobody typed:

```bash
ls briefs/ 2>/dev/null && tail -3 spend/ledger.md 2>/dev/null
```

Then the audit:

```
/spend report
```

**Success condition: they can point at two files they did not write** — the verbatim
commission, and the cost receipt — and say what the report's exit code means.

Have them open the brief and compare it to what they *thought* they asked for. That gap —
between the request in your head and the commission on disk — is the entire reason the brief
exists.

## What just happened

Three things worth naming before you move on.

**The policy became checkable.** "We only delegate to approved models" is a claim. A report
that exits non-zero when it didn't happen is a control. This is module 03's rule wearing
different clothes: *configured is not verified* — and here's what it costs to close that gap.

**Delegation buys context, not judgment.** Fanning five lanes at a question you haven't framed
properly gets you five well-researched answers to the wrong question, and now you have to read
all five.

**Automated grouping proposes; you dispose.** Tooling that partitions work by analysing which
files reference each other knows about *links*, not *meaning*. Two files that never import
each other can be deeply coupled conceptually. Let the tool propose the split; apply your own
judgment to it.

## Facilitator notes

- **If lanes are slow or unavailable, skip the spawn entirely** and inspect the artefacts
  instead — bring a `briefs/` directory and a spend ledger from a real project and walk them
  through on the projector. The paperwork is the content; the spawn is only how it got there.
- Expect *"isn't banking every prompt to disk a privacy problem?"* It's a fair question.
  Answer straight: yes, the commissions are readable, that's deliberate, and auditability and
  confidentiality genuinely pull against each other here. Don't wave it away.
- Ask early: *how many of you know which model your last sub-agent ran on?* Very few hands.
  That's the module, in one show of hands.
- Don't let this drift into general multi-agent architecture. Twenty minutes.

## Fallback

No lanes available at all: run the four rules and the "what delegation doesn't fix" section as
discussion, and demo the artefacts from pre-captured files. Everything essential survives
without a live spawn.
