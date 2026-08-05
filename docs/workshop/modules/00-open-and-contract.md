# Module 00 — Open, and the contract every skill shares

**20 minutes.** Setup is folded in here. Hard cap — at minute 20 you move on.

---

## Purpose

Three things: get everyone to a known state, name the four failures the day is about, and
teach the one contract that makes the other nine modules cheap.

## Success condition

Every attendee has a scratch folder with a session open in it, has read an exit code aloud,
and can name the five parts of the skill contract without looking.

---

## Run it

### Minutes 0-5 — the scratch folder and one exit code

```bash
mkdir -p ~/harness-workshop && cd ~/harness-workshop
```

Not a real project — we're going to establish files in it and deliberately break things.

Open a session there and run:

```
/doctor
```

You want an exit code across the room. `0` and `5` both mean the install works.

Someone will have `5` and assume they're broken. Get ahead of it — put this on the board
and leave it there all day:

> **`5` is WARNINGS. A warning never blocks. A failure always does.**

You'll return to it properly in module 04. Right now it just stops the anxiety.

### Minutes 5-10 — the four failures

Name them, fast, and ask for a show of hands on each. The hands are the point: this room
already knows these, they just don't have names for them.

1. **The session that looked governed and wasn't.** You set up instructions and assume
   they're in force. Nothing errors. Nothing logs. It looks exactly like one that did.
2. **"Done" that wasn't.** Fixed, working, deployed — a claim with no receipt.
3. **The context that evaporated.** The session ends, compacts, or dies, and everything it
   worked out goes with it. The next one re-derives it badly and charges you again.
4. **Delegation that lost the plot.** Work farmed out comes back unattributable, unpriced,
   and impossible to audit.

Then the sentence the whole day hangs on:

> **Presence is not establishment.** An instruction being installed is not a project being
> governed. Governance is files, and files have to be written by somebody.

And its generalization, which is what they'll actually take to work:
**installed ≠ in force · configured ≠ verified · a test existing ≠ a test testing.**

### Minutes 10-17 — the contract every skill shares

This is the highest-leverage seven minutes in the workshop. Everything after it is cheaper
because of it.

There are 31 verbs. **You do not learn 31 things.** Every working skill follows one
contract:

| part | what it means |
|---|---|
| **Natural language triggers it** | "research X", "help me decide", "is this true?" — or invoke it explicitly as `/verb` |
| **Two files out** | `background.md` — all the working-out, auditable. `Dossier.md` — the answer, self-contained, plain-language summary at the top |
| **`--quick` mode** | chat-only, no files, compressed — for exploration, and *honestly labelled as such* |
| **Honesty labels** | `[cited]` · `[recall]` · `[estimate]` · `[unverified]`, on every claim |
| **A self-check** | the skill verifies its own output against its own rules before it finishes |

Two things to draw out, because they're the design and not the feature list:

**The two files are a separation of concerns.** The dossier is what you read; the
background is what you audit when you don't believe the dossier. Most tools give you only
the first, which means disagreeing with the output costs you a full re-run.

**`--quick` is honest about being quick.** It doesn't silently give you a worse answer —
it tells you it's the compressed one. A mode that degrades quality without saying so is
the "done that wasn't" failure wearing a convenience label.

Then the frame for the day:

> **`/oracle` opens a session. `/sessionend` closes it. `/fable-mode` is the posture in
> between.** The bookends make sessions continuous; the posture makes each one trustworthy.

Everything else you'll meet today is an instrument you reach for inside that frame.

### Minutes 17-20 — pair the stragglers, go

Anyone not working gets paired: one drives, one reads the checks aloud. Do not debug an
individual install in front of thirty people. Note who they are; catch them at the break.

## Facilitator notes

- **Don't skip reading the exit code aloud.** The whole workshop runs on people being
  comfortable reading a status rather than a vibe, and this is where the habit starts.
- **The contract table is worth the time.** Facilitators under clock pressure cut it first
  and then find every later module has to re-explain the same five things. Cut the failure
  hands-up instead if you must.
- If the room is ahead, do **not** start module 01 early. Have them read the cheatsheet.
  You will want that buffer in module 08.

## Fallback

If more than half the room can't get a session open, switch to **demo mode** for modules
01-07: you drive on the projector, they read the checks aloud with you. Module 08 becomes
a walkthrough.

Say clearly that you've switched, and why. Pretending the hands-on is happening when it
isn't is the same species of failure the workshop is about.
