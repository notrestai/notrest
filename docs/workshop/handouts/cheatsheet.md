# Session Harness — one-page reference

Keep this next to you all day.

---

## The frame

> **`/oracle` opens a session. `/sessionend` closes it. `/fable-mode` is the posture in
> between.** The bookends make sessions continuous; the posture makes each one trustworthy.
> Everything else is an instrument you reach for inside that frame.

## The ten verbs you'll drive today

| verb | what it's for | leaves behind |
|---|---|---|
| `/oracle` | Opens a session — loads or scaffolds the foundation, resumes from a handoff, six skippable questions | `CLAUDE.md` |
| `/notrest` | **Establishes** a project — or, if it's already established, **continues the build** | `COORD.md` + a protocol block |
| `/fable-mode` | The discipline contract: the loop, the labels, the evidence bar | a posture |
| `/doctor` | Is the **install** healthy? | exit code + a fix per finding |
| `/eval` | Do the **laws** hold? | exit code, ~0.2s, zero tokens |
| `/recap` | The trail turned into a decision story + a clickable map | understanding |
| `/graph` | The live window — file graph, river, the cockpit | HTML, zero tokens |
| `/agentswarm` | Delegate to background lanes, properly | banked commissions |
| `/spend` | The receipt — what it cost, and whether routing obeyed policy | `spend/ledger.md` |
| `/sessionend` | Closes a session so a memoryless one can resume | resume + handoff files |

There are **32** in total. These are the ones for today.

## The contract every skill shares

Learn it once; every other skill is a variation.

1. **Natural language triggers it** — or invoke `/verb` explicitly
2. **Two files out** — `background.md` (the working-out, auditable) · `Dossier.md` (the answer)
3. **`--quick`** — chat-only, compressed, and *honestly labelled as such*
4. **Honesty labels** on every claim
5. **A self-check** before it finishes

## The loop

**ORIENT → PROBE → ACT → PROVE → BANK**

| step | in one line |
|---|---|
| **ORIENT** | read the project's own state first |
| **PROBE** | read the live system before reasoning about it — inspection is free, spend it |
| **ACT** | smallest verifiable step |
| **PROVE** | evidence in the transcript, or say **unverified** |
| **BANK** | write down what landed, the moment it lands |

## The labels

| `[cited]` | I read it, this turn |
|---|---|
| `[recall]` | remembering, not reading |
| `[estimate]` | derived, not measured |
| **`unverified`** | **no evidence — say it out loud. It is not a failure.** |

## Exit codes

| code | means | blocks a ship? |
|---|---|---|
| `0` | all clear | — |
| `5` | **warnings** — echoed, never swallowed | **no** |
| `6` | failures | **yes** |
| `2` | refused root — it won't scatter files somewhere dangerous | nothing written |

**Memorize:** a **WARN never blocks; a FAIL always does.**

## The ledger line

One honest line per substantive prompt, the moment its work lands. Append-only.

```
- [2026-08-04 21:38Z] [session] what was asked -> what landed | evidence: exit 0, 12 tests pass
```

Three parts, all required: **the ask · what landed · the evidence.** A line without evidence
is a rumour with a timestamp. Stamp the time from the clock, never by hand.

**Earn-its-line test:** keep a line only if the next session would otherwise re-explain it,
get it wrong, or burn tokens rediscovering it.

## Continuing someone else's build

**Verify as little as the evidence allows.** More verification is not more rigour.

| tier 0 | always | the gates + git state vs what the packet claimed |
|---|---|---|
| tier 1 | only if a gate wasn't green | re-run **the specific check the trail names** |
| tier 2 | only on a contradiction | **the trail wins** — probe that one claim only |

## Laws worth stealing, even if you never install anything

- **Presence is not establishment.** Installed ≠ in force · configured ≠ verified · a test existing ≠ a test testing.
- **Present → displayed → readable → navigable.** Each one feels like done. The first three aren't.
- **The trail wins.** When memory and the record disagree, the record wins — including when the memory is yours.
- **A test that passed — is it still testing anything?** An assertion that can no longer fail defends nothing.
- **Absence of records is not evidence of absence.** "Found nothing" and "couldn't look" produce identical output.
- **Never widen a margin.** A flaky test fixed by raising the timeout passes because the machine was fast enough.
- **A gate that blocks on the unfixable trains people to bypass it** — and a bypassed gate protects nothing.
- **A count that moved?** Identify the reason; never approve the direction.
- **The operator is part of the live system.** When a bug keeps returning, "a human did it through a surface I can't see" belongs on the list — and asking is the cheapest probe.

## If you get stuck

Blocked is not stopped. Bank what you have, move to a lane that isn't blocked, come back with
a cheap probe. Tell your facilitator the **exact error text**, not a paraphrase — the character
of a failure is evidence about the character of the problem.
