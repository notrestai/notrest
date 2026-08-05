# Module 01 — `/oracle` — how a session starts

**10 minutes.** Short by design. It's the front door, not a destination.

---

## The failure it prevents

Sessions start cold. You open one, start typing, and the agent has no idea what project
this is, what you decided last week, or what it must not re-litigate. So it guesses — and
a confident guess is more expensive than an admission of ignorance, because you act on it.

The resume case is worse. "Pick up where we left off" means the agent reconstructs from
whatever's nearest, and reconstruction is where the confident wrongness lives.

## Overview — what the verb is

`/oracle` (or just saying **"hey oracle"**) is the session's front door. It does three
things, in order:

**Loads the foundation.** It reads the project's `CLAUDE.md` — the durable instructions —
or scaffolds one if there isn't any.

**Offers to resume.** If a previous session left resume files, it finds them and picks up
from them rather than from your memory of what happened.

**Asks six questions**, each of which is skippable:

| | question | what it pins down |
|---|---|---|
| **O** | Objective | what done looks like |
| **R** | Role | who you are in this and what you're accountable for |
| **A** | Architecture | what the thing is made of |
| **C** | Content | what material exists already |
| **L** | Leverage | what would make this dramatically easier |
| **E** | Evaluation | how we'll know it worked |

Then it routes you to whichever verb fits the work you described.

**The bookend framing** — say it here and repeat it in module 08: `/oracle` opens,
`/sessionend` closes, and together they make sessions *continuous* rather than a series of
cold starts.

## Test drive (5 min)

In their scratch folder:

```
hey oracle
```

Have them answer **two** questions honestly and skip the rest. The skipping is deliberate
and worth calling out — a front door you must complete in full is a front door people
route around.

Then verify a foundation now exists:

```bash
ls CLAUDE.md && wc -l CLAUDE.md
```

**Success condition: `CLAUDE.md` exists.** Before this module, their scratch folder had no
durable instructions. Now it has a file that every future session in this folder will read.

## What just happened

They created the thing that makes the *next* session cheaper. Point at it directly:

> The six questions aren't a form. They're the answers a future session would otherwise
> have to guess at — written down once, at the moment you actually know them.

The law underneath, which applies far beyond this verb:

> **A session that starts by reading is cheaper than one that starts by guessing** — and
> the difference compounds, because a guess gets built on.

## Facilitator notes

- **Keep this to ten minutes.** The temptation is to let people fill in all six questions
  properly for a real project. That's a great use of their Tuesday and a terrible use of
  your workshop clock. Two answers, skip the rest, move.
- If someone asks why it's called oracle rather than "init" or "start" — it isn't only for
  starting. The same verb resumes, which is why it's the door rather than the switch.
- Attendees with an existing `CLAUDE.md` in their scratch folder (rare) will see it *load*
  rather than scaffold. That's a better demo — get them to say what it read.

## Fallback

If the verb isn't available, show the six questions on a slide and have them write two
answers on paper, then create the foundation by hand:

```bash
printf '# Harness workshop scratch\n\n## Objective\n\n## Evaluation\n' > CLAUDE.md
```

The artifact is the lesson; the automation is just how it usually gets made.
