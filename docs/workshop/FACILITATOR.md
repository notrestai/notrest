# Facilitator guide

Run the workshop from this file. Read it once end-to-end before the day, then keep it open
beside the module you're in.

---

## The arc, in one paragraph

You are teaching **four failures and their answers**, verb by verb. The verbs are the way in;
the laws are the payload. Attendees who never install anything should still leave with the
laws. Attendees who do install should leave with a working project. Keep that dual audience
in mind whenever you're tempted to go deep on implementation — the implementation is the least
transferable part of the day.

## The one thing that must land

If the room forgets everything else, they should remember **presence is not establishment**,
and that it generalizes: an instruction being installed is not it being in force, a limit
being configured is not it having stopped anything, a test existing is not it testing
something.

Say it in module 00, prove it in 02, point at it again in 03, 04 and 06, and land it in 09.
Module 06 is where it gets its best illustration — *present → displayed → readable →
navigable*, four levels of "done" that weren't.

## Timing at a glance

| # | module | min | ends at |
|---|---|---:|---:|
| 00 | Open + the shared contract | 20 | 0:20 |
| 01 | `/oracle` | 10 | 0:30 |
| 02 | `/notrest` | 15 | 0:45 |
| 03 | `/fable-mode` | 15 | 1:00 |
| — | break | 10 | 1:10 |
| 04 | `/doctor` + `/eval` | 15 | 1:25 |
| 05 | `/recap` | 15 | 1:40 |
| 06 | `/graph` | 15 | 1:55 |
| — | break | 10 | 2:05 |
| 07 | `/agentswarm` + `/spend` | 20 | 2:25 |
| 08 | **Finale — kill and continue** | 25 | 2:50 |
| 09 | Close | 10 | 3:00 |

Write the end-times on the board at the start. Public timing keeps you honest and lets the
room self-regulate.

## Before the day

**Two weeks out.** Send the prerequisites from `README.md`. Be explicit that installs happen
*before* arrival, not during module 00.

**One week out.** Ask for a reply confirming Claude Code opens and replies. Non-repliers are
your module 00 stragglers — plan to pair them with someone ready.

**The day before, run the whole thing yourself.** Not a skim — actually do every test drive,
in a fresh folder, and time it. Two things you're checking:

1. Every command still works as written.
2. Every success condition can still come out **red**. Break something on purpose and watch
   the check fail. A workshop full of checks that always pass teaches the opposite of the
   lesson.

**Room setup.** Power at every seat. Seat people in pairs — module 08's extension uses them,
and moving people mid-workshop costs five minutes you won't have.

## Timing discipline

The two failure modes are opposite and both fatal:

- **Setup overrun.** Module 00 is capped at 20 minutes *including* the contract. At the cap
  you move on with stragglers paired. Do not debug one person's install in front of thirty.
- **Finale starvation.** Module 08 is last and it's the payoff. If you're behind at the second
  break, take it from module 09 — which compresses to five minutes and still works. Module 08
  does not.

If you must drop a whole module, drop **06 (`/graph`)**. It's the most enjoyable and the least
load-bearing; nothing later depends on it.

## Per-module watch-outs

| module | what tends to go wrong |
|---|---|
| **00** | Facilitators cut the contract table under clock pressure, then every later module re-explains the same five things. Cut the show-of-hands instead |
| **01** | People want to fill in all six questions properly. Two answers, skip the rest, move |
| **02** | Rushing beat 2. The pause between "I'm getting reminders" and "this project has no trail" *is* the module |
| **03** | Explaining the trick before they run it. Stay quiet |
| **04** | The doctor/eval distinction gets muddled. Say it three ways: install vs laws · wired up vs obeys itself · plumbing vs constitution |
| **05** | Someone defends line C because the refactor was probably fine. That's the right argument — the standard is "can a stranger check it", not "is it true" |
| **06** | Turning into a graph-layout discussion. Fifteen minutes |
| **07** | Drifting into general multi-agent architecture. Twenty minutes |
| **08** | Attendees *helping* the new session before testing it. Warn them twice |

## What goes wrong in the room

| symptom | what you do |
|---|---|
| A third of the room isn't installed at minute 10 | Pair them. Two at one terminal is fine — driver types, navigator reads the checks |
| Someone establishes in their home directory | It **refuses** and exits 2. Use it live — that's module 02's fourth law happening in the room |
| "It says exit 5, is that bad?" | The most common question of the day. Pre-empt it in module 00, put it on the board |
| A session compacts mid-workshop | Perfect. Have them run `/recap` and continue. Module 05 arriving early |
| Lanes unavailable in module 07 | Skip the spawn, inspect pre-captured artefacts. The paperwork is the content |
| Pairs can't reach each other in module 08 | Fall back to the files — *that's in the protocol*. The fallback is the lesson, not a failure of it |

## Questions you will be asked

**"Isn't this just git commits with extra steps?"**
Git records what changed in the code. The trail records *why the work happened, what was
tried, what was ruled out, and what the evidence was* — the reasoning that produced the diff,
which the diff cannot carry. A useful reply: *"show me the commit that tells you which two
approaches you already rejected, and why."*

**"Isn't this a lot of overhead for one person?"**
Honest answer: yes, some. The cost is one line per substantive prompt. The payoff shows up at
the seams — session death, a week away, a handover. If you never hit a seam you don't need
this. Most people hit seams constantly and pay for them without noticing.

**"What if the agent writes a dishonest ledger line?"**
It can. Nothing prevents it. The structure makes dishonesty *visible* — a line claiming
evidence names it, and a named receipt can be checked. Don't oversell: the trail raises the
cost of a false claim, it doesn't make one impossible.

**"Does this work with other agents?"**
The laws do — they're about evidence and record-keeping, not any vendor. The verbs are Claude
Code. Say which is which.

**"Why ten verbs and not thirty-two?"**
Because every skill shares one contract, and once you have it the rest are variations. Also
because a verb that doesn't finish while you're watching can't be taught hands-on — which is
why the roster leans on the instant, zero-token ones.

## Tone notes

- **Show the failures for real.** Don't describe the ungoverned session — produce one in front
  of them, exit code and all. The demo is the argument.
- **Say "unverified" out loud yourself, twice.** You're modelling the behaviour you're asking
  for. If the facilitator never admits uncertainty, the workshop teaches that admitting it is
  for other people.
- **When something breaks live, don't paper over it.** Run the loop on it in front of them —
  probe, read the actual error, name what you don't know. An unplanned failure handled honestly
  is the best ten minutes of teaching in the day.
- **Don't oversell.** This is infrastructure for reliability, not magic. The room will trust
  you more for the caveats than the claims.

## The story to keep in your back pocket

Module 08 works far better with a true story than a hypothetical, and there is one in this
repo's own trail.

The continuation feature — one session picking up another's build — shipped with its handoff
wire explicitly labelled **unproven** in its own release note: the author wrote that the first
real proof would have to be the next session.

The next session ran it. It worked — the successor read the trail, reached the predecessor,
and got a structured handoff back.

Then the interesting part. The successor checked two of the handed-over claims against the live
system, and **both were wrong**: a count quoted from a stale interface instead of the
instrument, and a timestamp typed by hand rather than read from the clock, which landed a
ledger entry ten minutes in the future and put the trail out of order. It sent both corrections
back. The predecessor accepted them, named the source of each error — *"the instrument beat the
UI and I had both; that one's on me"* — and adopted a practice fix.

Tell it in that order — **shipped unproven, proven, then immediately caught two errors** —
because the point isn't that the handoff worked. It's that the system was built to surface its
own mistakes, and did, within minutes, in both directions.

> A system that cannot be wrong in public cannot be corrected in public either.

## Close

Three beats, no summary — they just did the modules:

1. **The idea again.** Presence is not establishment.
2. **The smallest Monday.** One line, one project, one week.
3. **The honest limits.** People adopt tools they've been told the truth about.
