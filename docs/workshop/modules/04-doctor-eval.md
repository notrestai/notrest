# Module 04 — `/doctor` and `/eval` — the two gates

**15 minutes.** First module after the break — open with the hands-on, not the theory.

---

## The failure it prevents

Two different failures, which is exactly why there are two verbs.

**You don't know the install is broken.** A skill stops firing. Nothing announces it. The
session behaves slightly worse and you assume the model had an off day.

**You ship on a red light — or you stop shipping because of a light that can never go
green.** Both are gate failures, and the second is the one nobody expects.

## Overview — what the verbs are

They answer different questions, and the distinction is the module:

> **`/doctor` checks the *install*. `/eval` checks the *laws*.**

**`/doctor`** — one read-only pass, a series of named PASS / WARN / FAIL checks, each with
a fix command attached. It looks at things like front-matter a real YAML parser would
reject (the kind that makes a skill *invisible while the file sits on disk*), version pins
across the places a number is written, hook scripts that exist and parse, estate integrity,
and whether what's installed matches what's in the tree. **It reads only** — it never
repairs, never bumps, never commits.

**`/eval`** — a static pass asking whether every law the suite claims actually left a
fingerprint in the shipped text. Its doctrine is worth quoting:

> **A law that is well-encoded leaves a static fingerprint — check the fingerprint, not the
> behaviour.**

That's why it takes about a fifth of a second and **zero model tokens**. It isn't running
the system; it's checking that the rules are actually written down where they'd have to be.

Both exit `0` / `5` warnings / `6` any failure, and both take `--json`. Each also has one
code for *"I could not find a thing to grade"* — `3` for doctor, `2` for eval — and that is
the one attendees hit first.

## Test drive (8 min)

**Point them at the harness, not at the scratch project.** These two grade the *plugin*;
the attendee's folder is not one. Run bare in the scratch project, `/doctor` exits `3` (no
plugin there) and `/eval` exits `2` (no skills there) — neither is a health reading. Give
them a target and the codes become the ones this module is about:

```bash
python3 <plugin-root>/skills/doctor/scripts/doctor.py check --plugin <plugin-root>
python3 <plugin-root>/skills/eval/scripts/eval.py   check --root   <plugin-repo>
```

*Verified live from a scratch project: bare → doctor 3, eval 2 · targeted → doctor 5, eval 0.*

```
/doctor
```

```
/eval
```

Have them read both codes aloud, then find one WARN in the doctor output and read **its fix
line** — every finding carries one.

**Success condition: they can say which of their two codes would block a ship and which
wouldn't.**

## What just happened

Now land the rule properly — they met it in module 00 as an anxiety-stopper, and this is
where it earns its keep:

> **A WARN never blocks. A FAIL always does.** Warnings are echoed, never swallowed.

This was earned the hard way. A release once got blocked on a warning about a condition
with **no available fix** — the gate was refusing to let anything ship for a reason nobody
could ever clear. The repair wasn't to ignore that warning; it was to make the *category*
correct.

The general lesson outlives the specific rule, and it's the one to send them home with:

> **A gate that blocks on things people cannot fix trains them to bypass the gate — and a
> bypassed gate protects nothing.**

Ask the room: *who has a CI check everyone has learned to click through?* The hands go up.
That's this failure, in their own build.

One more, quickly, because it's the most transferable idea in the module:

> **A count that moved? Identify the reason; never approve the direction.**

A test count that drops because a redundant test was retired and one that drops because
coverage was lost look **identical** from the outside. Diff the labels, not the number.

## Facilitator notes

- **Lead with the run.** They're back from a break; give them something to type in the first
  ninety seconds.
- The doctor/eval distinction is the thing people get wrong afterwards. Say it three times
  in three ways: install vs laws · is it wired up vs does it obey itself · the plumbing vs
  the constitution.
- Expect "why doesn't eval just run the system and check the behaviour?" Good question, real
  answer: because that costs model tokens and time, and a law that's properly encoded is
  visible in the text. It's a deliberate trade — cheap and static beats thorough and slow
  for something you want to run before *every* ship. There's an opt-in behavioural path that
  sits deliberately outside the ship gate.
- If someone's `/doctor` shows a WARN they can't clear, that's the module's own lesson
  arriving live. Use it.

## Fallback

Both verbs are near-instant and read-only, so they survive almost any environment. If a
session can't run them, show your own output on the projector — a real WARN with a real fix
line is the artefact that matters.
