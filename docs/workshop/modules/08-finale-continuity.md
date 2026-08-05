# Module 08 — Finale: `/sessionend` → `/notrest` — kill it and continue

**25 minutes.** The payoff. Everything so far exists to make this work.

If you are running behind, take the time from module 09. Never from here.

---

## The failure it prevents

All four at once. A session ends — planned or not — and the build stops with it. Someone
picks it up later, or someone else does, and they begin by reconstructing what was already
known. The reconstruction is slow, partial, and confidently wrong in places.

## Overview — the two verbs closing the loop

**`/sessionend`** captures state into continuity files — ordered resume instructions, a
curated handoff, the state, and the foundation (merged, never clobbered). It's the difference
between a session that *ended* and one that merely *stopped*.

**`/notrest`**, in a folder that's already governed, takes its second mode: it doesn't
re-establish, it **continues**. Four steps, and the order matters:

| step | what happens |
|---|---|
| **PACKET** | read the trail in one gulp — state, recent work with evidence, gates, git position |
| **MENTOR** | if a predecessor session is reachable, ask it once, in a single batched question |
| **VERIFY** | at tier 0 only |
| **GO** | say what you're continuing, bank a line, work |

The counter-intuitive rule sits in step three, and it's worth stating *before* they do it:

> **Verify as little as the evidence allows.** More verification is not more rigour. It's
> latency the trail already paid for.

| tier | when | what |
|---|---|---|
| **0** | **always — and usually the only tier** | the two gates from module 04, plus git state against what the packet claimed |
| **1** | only if a gate wasn't green, or you landed mid-ship | re-run **the specific check the trail names** — not the suite |
| **2** | only on a live contradiction between what you were told and what's written | **the trail wins.** Probe that one claim, nothing else |

Explicitly forbidden: spawning verification work when tier 0 is green, re-deriving decisions
the trail already records, re-asking a predecessor what the packet already told you. Each
trades a cheap fact for an expensive one.

## Test drive (15 min) — everyone, solo

No partner needed. The successor is *themselves, with no memory*.

**Step 1.** One more small piece of real work in the scratch project — something with shape,
like starting a file and deliberately leaving it half-finished. Bank a line for it.

**Step 2.** Close the session properly:

```
/sessionend
```

**Step 3.** Open a **completely new session** in the same folder:

```
/notrest
```

Because the project is governed, they get the continuation path — the packet, not a fresh
establishment.

**Step 4 — the actual test.** *Before telling the new session anything*, ask it:

> What am I building here, and what was the last thing that landed?

**Success condition: it answers correctly, unaided.**

Have them compare its answer against what they know. That gap — or its absence — is the
measurement the whole workshop has been building toward.

### The extension, if the environment supports it (3 min)

Where sessions can message each other, the successor sends **one batched question** to the
predecessor — not a conversation — covering current state, anything in flight, standing
decisions not to re-litigate, the next step, watch-outs, and what they'd verify first.

Two rules keep this from turning into telephone:

**The trail outranks the recollection.** The packet is cited; a session's memory of its own
work is recall. When they disagree, the written record wins — *including when the recollection
is yours*.

**Never block on a wire that isn't there.** If no predecessor is reachable, continue from the
files and say so in one honest line. The mentor is an accelerator, not a dependency.

## What just happened — and the story

Tell them the true one. It's in `FACILITATOR.md` in full; the short form:

The continuation feature shipped with its handoff wire labelled **unproven** in its own
release note — the author wrote that the first real proof would have to be the next session.
The next session ran it, and it worked.

Then the part that matters. The successor checked two of the claims it had been handed against
the live system, and **both were wrong**: a count quoted from a stale interface instead of the
instrument, and a timestamp typed by hand rather than read from the clock, landing a ledger
entry ten minutes in the future. It sent both corrections back. The predecessor accepted them,
named the cause of each, and changed the practice.

> The point isn't that the handoff worked. It's that the system surfaced its own errors, within
> minutes, in both directions — and **a system that cannot be wrong in public cannot be
> corrected in public either.**

## Facilitator notes

- **Protect this module's clock.** It is the module people describe when someone asks what the
  workshop was about.
- The most common stumble is attendees *helping* the new session — telling it what they were
  doing before asking it. Warn them twice. The test only works if they stay quiet.
- When someone's new session gets it **wrong**, that's a finding, not a broken exercise. Ask
  them to read their own trail and identify which line should have carried the missing fact.
  That diagnosis teaches more than a clean pass does.
- Before moving on, ask what surprised them. The usual answer: how little the new session
  needed.

## Fallback

No second session possible: run it once on the projector. Seeing it happen once still lands,
and the story carries the rest.
