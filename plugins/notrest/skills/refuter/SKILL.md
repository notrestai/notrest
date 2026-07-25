---
name: refuter
description: "The adversarial reviewer for code and load-bearing artifacts — a lane other than the builder attacks ONE narrow target under a brief: CONFIRMED findings with a reproduction, PLAUSIBLE ones with a failure scenario, and what survived. Use on /refuter, \"refute this\", \"attack this before we ship\", \"QC that lane's work\", \"red-team this\", or as the agentswarm gate before shipping code that pushes, installs, or writes the estate. It finds, never fixes; `critic` is the document-side sibling."
---

# Refuter

The adversarial reviewer, as a contract.

Every harness re-improvises this: "have a lane check the work." Improvised refuters read code and opine. They return "concerns" nobody can reproduce, they miss the path that pushes on a swallowed exit code, and they burn twenty minutes on one brief so broad it becomes a code review.

This skill fixes the shape. One narrow target. A written brief. A numbered attack ladder. A verdict grammar where a finding without a reproduction or a concrete failure scenario **is not a finding**.

The bar is empirical. The best run this harness has had returned three CONFIRMED criticals, each with a command and its output — a JSON key reorder that de-pinned a version-pinned tombstone and committed at exit 0; a validator failure string-matched into "CLI absent, proceed" that reached push and install; and proof that a "5/5 byte-identical PARITY PASS" was overclaimed, because two of the five surfaces were algebraic round-trips and the largest text clause was never compared at all. Nothing below that bar is worth the tokens.

## When to run

Blast-radius tiered. The seat picks the tier; the tier is not negotiable upward by the builder.

| The artifact | The review |
|---|---|
| Code that pushes, installs, deletes, or writes the estate | **Full refuter.** Always. No exceptions for "it's a small patch." |
| Code that only reads, or writes inside an isolated dir | Full refuter if it gates a decision; grep-and-read otherwise. |
| Docs, README rows, prose | Grep-and-read. Check the claims resolve; skip the ladder. |
| Cosmetic — whitespace, wording, a renamed variable | Nothing. Do not spend a lane on it. |

Two hard rules on timing:

- **Before the seat accepts the work.** Not after the gate, not after the commit. A refuter that runs post-ship is an incident report.
- **A different lane than the builder.** Including review-the-fix: the lane that wrote the repair does not certify the repair. The builder's context is exactly the blind spot you are paying to cover. Resume the builder lane for the *repair*; spawn a fresh lane for the *check*.

## The brief

The refuter is only as good as its brief, and the brief is the seat's job — but most of a
brief is mechanical, and the mechanical parts are the ones that get skipped under time
pressure. **The seat mints it with the script:**

```bash
python3 plugins/notrest/skills/refuter/scripts/brief.py --target <path> --budget 12 \
  --contract "<what must never happen if this is correct>" [--priorities <file>]
```

`scripts/brief.py` fills what a script can know from the target itself — the artifact
inlined in a fenced block with its byte count and sha256 (so the bytes under review are
pinned, not merely referenced), a freshly minted isolated scratch dir, the budget stamp,
and the prohibitions — and leaves exactly two fields marked `<<< SEAT MUST FILL >>>`: the
contract paragraph and the specialized ladder. Those two are judgment; nothing else in the
brief is. It prints the brief on stdout, ready to paste as the lane's whole prompt, and
tells you on stderr what is still unfilled (`--strict` turns that into exit 5). `--no-inline`
cites a path instead of pinning bytes, and says in the brief that the file may change under
the lane. The lane runs on explicit `model: "opus"`, is a different lane than the builder,
and gets receipted with `spend.py` like any other.

What the brief must say — six parts, all required (they render as the template's seven
numbered sections, budget and return contract being the last two):

1. **The target and its contract, in one paragraph.** What is this thing supposed to guarantee? A refuter that does not know the contract can only find crashes, and crashes are the least interesting failures.
2. **The artifact inline, or its exact absolute path.** Inline is better — it pins the bytes under review. If you give a path, say the commit or say "current working tree", because the file may change under the lane.
3. **An isolated scratch dir.** Give it one and name it. Every fixture, every clone, every destructive experiment lives there.
4. **The hard prohibitions.** Never run destructive or irreversible paths against the real tree. Never push, never install, never publish. Never edit the target. Never touch the estate ledgers.
5. **A numbered attack priority list, written per target.** Specialize the generic ladder below. Numbered, because the budget runs out and the order decides what gets cut.
6. **The budget and the return contract.** Tool calls, wall clock, and the exact shape of the answer wanted back.

State the artifact's own success claim in the brief, verbatim. Half the good findings come from testing the banner rather than the code.

## Attack priorities

The generic ladder. Specialize it per target — rewrite each rung in the target's own nouns, drop the rungs that cannot apply, and renumber.

1. **Irreversible-path safety.** Can any input or state reach a push, install, publish, or delete *despite an earlier failure*? Hunt error-string matching that misclassifies a failure as an absence ("command not found" read as "tool absent, proceed"). Hunt swallowed exit codes — `| tail`, `|| true`, unchecked `$?`, a subshell whose status nobody reads. Ask of every guard: what does it do when the check itself errors?
2. **Integrity invariants.** Pins, anchors, orderings, and identities that hold *by luck*. Key order in a serialized rewrite. First-match parsing where a second match exists. A version pin that survives only because nothing has re-serialized the file yet. Is the invariant re-asserted after the write, or only assumed before it?
3. **Claim honesty.** Does the artifact's own success banner overclaim? Look for tautological comparisons (a value checked against itself), round-trip identities (encode-then-decode proving only that the codec is a function), and surfaces the artifact *writes* but the check *excludes*. "N/N verified" is a claim about the denominator — audit the denominator.
4. **Partial-failure states.** Non-atomic multi-file writes. No rollback. What is on disk after an abort at each step? Can a half-applied state be re-run safely, or does the second run compound it?
5. **Test honesty.** Asserts graded by the very thing they validate. Mocks that agree with the implementation by construction. Greps that match the fixture's own injected string. Coverage that carefully skips the dangerous path. Ask: if the implementation were wrong, which of these tests would go red?
6. **Environment assumptions.** Shell and OS differences (`sed -i`, `date`, `readlink`, GNU vs BSD). Absent binaries. Locale and encoding. Concurrency — two lanes, one file. Paths with spaces.

Work the ladder in order and stop at the budget. Rung 1 findings are worth more than a complete sweep of rung 6.

## Verdict grammar

Two verdict words. They are not interchangeable, and the difference is evidence.

**CONFIRMED** — you reproduced it. The finding carries the exact command you ran and the output you observed, pasted, not paraphrased. If you cannot paste an observation, it is not CONFIRMED.

**PLAUSIBLE** — you did not reproduce it, but you can state a concrete failure scenario: these inputs, this state, therefore this wrong outcome. Name it PLAUSIBLE explicitly and say why you stopped (budget, no fixture, needs the real remote). **PLAUSIBLE is not evidence.** The seat must be able to tell at a glance which findings survived contact with a shell.

Anything that is neither — a worry, a smell, a "this could be fragile" with no scenario — **delete it before returning.** It is noise that costs the seat a read and buys nothing.

Severity, ranked:

**breaks-irreversible-safety** > **breaks-claim-honesty** > **degrades** > **cosmetic**

Claim honesty outranks degradation on purpose. A tool that quietly does less than it says corrupts every decision made downstream of its banner; a tool that is merely slow does not.

Then, always: **state what SURVIVED, by name.** "Attacked the exit-code path in the install branch with a forced non-zero — it aborted correctly." An attack surface that held is information the seat needs, and it is the only way the seat can tell a clean report from a lazy one.

## Budget law

The speed discipline, applied to QC.

- **~12 tool calls, one narrow target.** That is the shape. If the target needs more, the target is too broad — split it.
- **Empirical where cheap.** A five-second shell test beats a paragraph of reasoning. Reach for the shell first, on the smallest fixture that can distinguish the outcomes.
- **PLAUSIBLE beyond budget.** When a check would cost more than it is worth, write the scenario and label it. Do not silently upgrade reasoning to evidence.
- **Never re-run the builder's full fixture.** The seat does that at the gate. Re-running it is the single most common way a refuter spends its whole budget confirming what was already known.
- **One broad refuter is worse than three narrow ones.** Split by attack surface — one lane on the irreversible paths, one on the claim's honesty, one on the tests — and run them in parallel. Three focused reports beat one that ran out of budget in the middle of rung 2.

## Honesty and boundaries

Named flat, because each one is a way this skill gets diluted:

- **The refuter never fixes what it finds.** Findings route to the builder as a repair spec. A refuter that patches has just become an unreviewed builder.
- **Repairs are capped at two rounds.** If round two still fails, the design is wrong — escalate to the seat, do not iterate.
- **The refuter never grades its own prior findings.** Verification of a repair goes to a third lane, or to the seat.
- **A target that changes under you must be re-confirmed against the current bytes** — and you say so in the report, naming what you re-ran.
- **The refuter does not review the builder.** It reviews the artifact. No commentary on the lane, its choices, or its competence.
- **Absence of findings is a result.** Report a clean sweep, list what you attacked, and do not manufacture a rung-6 nit to look thorough.

## The seat's gate on the returned report

A report is not accepted because it looks thorough. Before the seat reads a finding as
real — and long before a repair is scheduled off it:

```bash
python3 plugins/notrest/skills/refuter/scripts/verdict_lint.py <report.md>
```

`scripts/verdict_lint.py` holds the report to the grammar above: exit **5** when a
CONFIRMED carries no fenced command+output block, when a PLAUSIBLE names no failure
scenario, when a numbered finding is neither (the noise the skill says to delete), or when
the SURVIVED list or the budget line is missing. Exit **0** means the shape is right. It
reads only, never edits the report, and it does not judge whether a finding is *correct* —
only whether it is the shape the seat agreed to accept. A rejected report goes back to the
lane for the missing evidence; it does not get read charitably.

Fixture: `bash plugins/notrest/skills/refuter/scripts/fixture.sh` — exit 0 = every
assertion held. It lints a canned good report and one canned report per way of breaking
the grammar, and checks that a numbered line inside pasted output is not mistaken for a
finding.

## Self-check before returning

Run this list. It is short on purpose. (`verdict_lint.py` mechanizes the first four; run
it on your own report before returning it.)

- Every CONFIRMED has a command and pasted output.
- Every PLAUSIBLE has inputs, a state, and a wrong outcome — and the word PLAUSIBLE.
- Nothing remains that is neither.
- Findings are numbered and severity-ranked, worst first.
- The SURVIVED list is present and specific.
- Nothing was edited, pushed, or installed; the scratch dir holds everything you wrote.
- Budget spent is stated.

## Chains

- **agentswarm** — gate step 4 invokes the refuter. That is the default path into this skill.
- **critic** — the document-side sibling. Arguments, plans, dossiers, prose. Not executables. If the target has an exit code, it is a refuter job; if it has a thesis, it is a critic job. `critic --panel` is the multi-lens form for high-stakes documents.
- **The builder lane** — findings return as a numbered repair spec, and the seat resumes the *same* builder lane to apply them (its context of the code it wrote is the saving).
- **spend** — receipt the refuter lane like any other, on explicit Opus.
- **compile** — a compiled runtime is attacked by an independent refuter before the fair benchmark. Same contract, same ladder.
