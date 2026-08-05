# Session Harness — a 3-hour hands-on workshop

**For:** people who already use Claude Code and have already been burned by it.
**Shape:** verb by verb. Each module is one skill — an overview, then they drive it.
**Duration:** 180 minutes.

**They leave with:** an established project, a ledger with their own lines in it, a live
cockpit over their own estate, one delegated lane with a receipt they can audit, and a
session they deliberately killed and then successfully continued from a different one.

---

## The problem this workshop is about

Everyone who uses an AI coding agent long enough hits the same four failures, usually
without a name for them:

1. **The session that looked governed and wasn't.** Nothing errors, nothing logs, and it
   looks exactly like one that did.
2. **"Done" that wasn't.** A claim with no receipt, discovered two hours later.
3. **The context that evaporated.** The session ends and takes what it learned with it.
4. **Delegation that lost the plot.** Work comes back unattributable, unpriced, unauditable.

Each verb in the run sheet exists because of one of these. Every module opens with the
failure, then hands them the verb.

## The single idea

> **Presence is not establishment.** An instruction being *installed* is not the same as a
> project being *governed*. Governance is files, and files have to be written by somebody.

It generalizes, and that generalization is the most portable thing in the day:
**installed ≠ in force · configured ≠ verified · a test existing ≠ a test testing.**

## Why this fits in three hours

Because every skill shares one contract, taught once in module 00 — natural language
triggers it, two files come out, `--quick` compresses it, honesty labels tag every claim,
and it self-checks before finishing. After that, each verb costs ten minutes instead of
twenty, because you're only teaching what's *different*.

The second reason: the roster is deliberately weighted toward verbs that **finish while
you're watching**. Several are zero model tokens and near-instant. A hands-on workshop
lives or dies on whether the thing completes before attention does.

## Run sheet — 180 minutes

| # | Module | Min | Verb | What they prove |
|---|---|---:|---|---|
| 00 | Open + the shared skill contract | 20 | — | can name the five parts of the contract |
| 01 | How a session starts | 10 | `/oracle` | a foundation file now exists |
| 02 | Presence is not establishment | 15 | `/notrest` | exit `2 → 6 → 0` |
| 03 | The posture between the bookends | 15 | `/fable-mode` | watched an assertion fail on purpose |
| — | **Break** | 10 | | |
| 04 | The gates | 15 | `/doctor` `/eval` | read two exit codes and know which blocks |
| 05 | The trail, written and read | 15 | `/recap` | ledger grew by exactly one good line |
| 06 | The live window | 15 | `/graph` | their own estate on screen |
| — | **Break** | 10 | | |
| 07 | Delegate and audit | 20 | `/agentswarm` `/spend` | two files on disk they didn't write |
| 08 | **Finale — kill it and continue** | 25 | `/sessionend` → `/notrest` | a memoryless session continued their build |
| 09 | Close — honest limits and Monday | 10 | — | one habit, one project, one week |

Module 08 is the payoff and gets the most time. If you are running behind, take it from
module 09, never from 08.

## The two bookends and the posture

Worth saying explicitly in module 00, because it's the mental model that holds the day
together:

**`/oracle` opens a session. `/sessionend` closes it. `/fable-mode` is the posture in
between.** Together the bookends make sessions continuous; the posture makes each one
trustworthy. Everything else is an instrument you reach for inside that frame.

## Prerequisites

Attendees need, **before** they walk in:

- Claude Code installed and working — they can open a session and get a reply.
- `git` and `python3` on PATH.
- A scratch folder they don't mind writing files into. Not a real project.

Send these ahead. The single biggest risk to a hands-on workshop is losing the first forty
minutes to installs — module 00 is built to catch stragglers, not to be the whole hour.

## How this pack is organized

```
docs/workshop/
├── README.md               ← you are here
├── FACILITATOR.md          ← run it from this file
├── modules/
│   ├── 00-open-and-contract.md
│   ├── 01-oracle.md
│   ├── 02-notrest.md
│   ├── 03-fable-mode.md
│   ├── 04-doctor-eval.md
│   ├── 05-recap.md
│   ├── 06-graph.md
│   ├── 07-agentswarm-spend.md
│   ├── 08-finale-continuity.md
│   └── 09-close.md
└── handouts/
    ├── cheatsheet.md       ← give it out at the door
    └── exercises.md        ← attendee-facing, printable, no spoilers
```

**Facilitators** read `FACILITATOR.md` first, then the modules in order.
**Attendees** get the two handouts and nothing else — the modules contain answers.

## The house rule, borrowed from the harness itself

Every exercise ends in a **machine-checkable success condition** — an exit code, a file
that now exists, a count that moved. Never "you should see something like this."

That isn't pedantry about workshop design; it's the subject matter applied to itself. A
check that cannot fail is a check that isn't checking. If you add an exercise to this pack,
give it a condition that can genuinely come out red — and confirm you've watched it do so.
