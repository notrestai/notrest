# The status law — long form

*The one rule that makes an atlas worth reading: **a status is derived, never typed.***

Every project map that ever died of disbelief died the same way. Someone typed `done`, the
code moved, nobody retyped it, and within three weeks the map was a museum of intentions.
Atlas does not ask anyone to retype anything. You write the **claim**; the machine runs the
**test**; the **status** is what falls out of the exit code.

## The four rules

**1 · Done needs a test that could fail.**
A part is `done` only when a test that could fail *passed*. Not "someone reviewed it", not
"the session said it worked" — a command, an exit code, a fingerprint of its output.

**2 · A done with no test is demoted, and said out loud.**
`status: wip · evidence: none · demoted: true`. Not an error, not a nag — a fact. The estate
is allowed to have parts nobody has bound a test to yet. It is not allowed to call them done.

**3 · A failing done becomes wip + failing.**
The claim stays on the record (`claim: done`), because what the author intended is evidence
about the estate too. The status moves, because the proof broke. This is the regression
signal: the map shows it the same day, without anyone noticing.

**4 · Status and evidence are separate fields.**
A single green check mark is where honesty goes to die: it cannot tell "a test passed" from
"someone said so". Atlas carries `claim`, `status` and `evidence` side by side, so the map
can say *claims done, evidence none* instead of hiding it.

    claim      what the author asserts      done · wip · planned · blocked
    status     what the evidence permits    done · wip · planned · blocked
    evidence   how we know                  passed · failed · none · unfalsifiable · not-run

**Evidence may only demote, never promote.** A passing test does not turn a `wip` into a
`done`. The claim belongs to the author; the evidence belongs to the machine; the machine
gets a veto, not a vote.

## RED is narrower than failing

The board is **RED** when a part **claimed done** has a **failing** test. That and nothing
else.

A `wip` whose test is red is not an alarm — it is what red-first work looks like on a
Tuesday, and a board that screamed about it would be a board people learn to ignore. Both
facts are still on the map (`failing: true` is recorded either way, and the summary counts
it); only the claimed-done regression turns the estate red.

## Falsifiability: what is checked, and what is not

`can_fail()` in `scripts/atlas.py` is a **static, conservative** reading of the command. It
refuses `true`, `:`, `exit 0`, a bare `echo …`, and anything trailing `|| true` or `; true`.
A done resting on one of those is demoted exactly like a done with no test at all, because a
command that cannot fail is not a test — it is a green light wired to the mains.

What it cannot do is prove that an arbitrary command *can* fail. Nothing static can. Two
other things carry that weight, and both are recorded rather than asserted:

- **`proven_red` (per part).** This estate has already banked a snapshot in which *this
  part's test failed*. Not an argument — a receipt. It is read from the last 50 snapshots on
  every bank, so falsifiability compounds instead of being re-argued.
- **The born-red proof (per estate).** `atlas.py wire --prove` disables the hook in a scratch
  git repo, commits, and requires the map to go **red** before restoring it. An estate joins
  the map only after its detector has been *seen* to detect. A detector nobody watched fail
  is not a detector.

## Where the parts come from

- **`atlas/map.md`** — one `PART:` per thing worth knowing the state of, with `CLAIM:`,
  optional `TEST:` and `PATH:`. Directives inside a fenced code block are documentation and
  are never run: a map that *shows* you how to declare a part must not thereby declare one.
- **`gates/ACTIVE.md`** — every armed gate is picked up automatically as a part **claimed
  done**, because a standing completion contract is exactly a claim that it holds. The
  verdicts come from `hooks/gate-check.py` itself; the CHECK/EXPECT grammar has one owner and
  atlas is not a second one. A gates file that exists and cannot be parsed becomes one named
  red part (`gates:contract`) — never a silent absence of gates.

An estate with **no parts and no gates** is not banked at all (exit 3). Certifying an empty
contract green is the one failure mode that would make every other rule here decorative.

## What the snapshot is for

`atlas/snapshots/<commit>.json` is written once, chmod `0444`, and never rewritten. A re-bank
of the same commit re-derives, compares, and *reports the difference* — then leaves the
snapshot alone. History is what the estate looked like when that commit landed; if it looks
different now, that is a fact about now, and now needs a new commit.
