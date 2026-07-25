---
name: decider
description: Structure any decision — options (always including do-nothing/wait), criteria weighted by what the user actually cares about, evidence per option, a reasoned scoring matrix with a sensitivity check ("which assumption flips the winner"), a pre-mortem on the front-runner, and a recommendation with confidence + reversibility framing — producing a background doc + decision dossier (or --quick). Use on /decider or "should I…", "help me decide/choose", "X or Y", "compare these options", "what are the tradeoffs". The user decides; this structures.
---

# Decider

Takes a decision — technical, business, or personal — and gives it a structure that makes the choice visible: what the real options are, what actually matters to *this* user, what the evidence says, which assumption the whole thing hinges on, and what the front-runner looks like after an honest attempt to break it. The reasoning runs through six passes; the output is **two files** — a consolidated background document and a final decision dossier.

Two framing rules govern everything: **facts vs values** (evidence is checkable; how much the user cares about each criterion is theirs — never substitute your weights for theirs silently), and **reversibility** (a two-way door rewards deciding fast and learning; a one-way door rewards resolving the load-bearing unknown first).

## The prompt

The decision is everything the user passed when invoking the skill. Use `$ARGUMENTS` if populated; otherwise the text after `/decider`. Attached documents (a research dossier, a spec, a comparison someone sent) are evidence — read them first. If the decision or its options are genuinely unclear, ask exactly one clarifying question (ideally: "what are you deciding between, and by when?"), then begin.

For decisions with professional stakes — medical, legal, large financial commitments — structure the thinking, flag `[needs expert]` where licensed judgment is required, and say plainly the final call needs a professional, not a framework.

**Consult the index first (if present).** If the repo carries an `oracle-index.md` — or the **archivist** skill is installed and prior ORACLE output folders exist — run one `find` on the decision's topic before Pass 1: a prior research/decision dossier is ready-made Pass-3 evidence (carried with its own labels and date), and a prior decision on the same question deserves to be surfaced before re-deciding it.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (recommendation, the hinge, the reversibility call), then a short options comparison. No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not fully sourced or saved; run again without `--quick` for the verifiable two-file version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output files

Derive a `{topic}` slug from the decision: lowercase, hyphen-joined, punctuation stripped, max ~50 chars. Create a `decision/` directory and write exactly two files:

- **`decision/{topic}background.md`** — all six passes, as sections within this one document.
- **`decision/{topic}Dossier.md`** — the final decision dossier.

If those files already exist from a prior run, suffix the topic with `-2` (then `-3`, etc.).

Web search/fetch: use where the decision turns on checkable facts (prices, capabilities, deadlines, track records). **Search budget (token discipline):** ~10 searches default (~2 in `--quick`); a preference-dominated decision may need none — say so instead of decorating it with searches.

## Honesty rules (a structured wrong answer is still wrong)

- **Never invent figures** — prices, dates, capabilities, success rates. Not found = "not found", labeled. (A computed comparison is `[estimate]` — show the math.)
- **Label evidence** `[cited]` (retrieved this run, with URL + date), `[from docs]` (in the user's documents), `[estimate]`, `[recall]`, or `[unverified]`.
- **Scores are reasoning, never bare numbers.** Every cell of the matrix carries its one-line why. A number without a why is an opinion in costume.
- **The weights are the user's.** Infer them from what the user said if you must, but show them and invite correction — a perfect matrix under the wrong weights recommends the wrong thing.
- **Surface the hinge.** Every real decision has one or two assumptions that flip the outcome if wrong. Finding them is half this skill's value; hiding them is malpractice.
- **Don't manufacture a winner.** "These are genuinely close — the tiebreaker is your appetite for X" is a valid, valuable verdict.

## The six passes — all written into `decision/{topic}background.md`

```markdown
# <Decision> — Decision Background
> Working document. All six passes. The recommendation lives in {topic}Dossier.md.

## Pass 1 — Frame
## Pass 2 — Criteria & weights
## Pass 3 — Evidence per option
## Pass 4 — Score & sensitivity
## Pass 5 — Pre-mortem the front-runner
## Pass 6 — Recommend
```

### Pass 1 — Frame
- **The decision in one sentence**, and the deadline (real or "none").
- **The options** — enumerate honestly, always including **do nothing / wait** and any obvious hybrid. If the user gave two options, check whether a third they didn't name dominates both.
- **Reversibility class:** two-way door (cheap to undo) or one-way door (hard/expensive to undo) — with the *why*. This drives the whole posture.
- **Stakes:** what's actually at risk (money, time, health, reputation, optionality), roughly sized.

### Pass 2 — Criteria & weights
What actually matters to this user, extracted from what they said and asked back where unclear: ≤7 criteria, each with a weight (visible scale, e.g. sums to 100). Separate **must-haves** (a fail here eliminates the option — no amount of other goodness compensates) from **tradeables**. State which weights you inferred vs. which the user gave.

### Pass 3 — Evidence per option
For each option: what's true, with labels — capability against each criterion, cost, track record, what its advocates and detractors say. Check must-haves first (an option that fails one exits here, cheaply). Search where facts are checkable and load-bearing; date what moves fast.

### Pass 4 — Score & sensitivity
- **The matrix:** options × criteria, each cell = verdict + one-line reason (+ label where evidence-based). Weighted totals *shown as arithmetic*, not revealed truth.
- **Sensitivity — the hinge check:** which single weight change or disproven assumption flips the winner? Test the 2–3 most plausible ones. If the winner survives all of them, say so — that's a robust pick. If a hair of weight flips it, the "decision" is really a values question — name it.

### Pass 5 — Pre-mortem the front-runner
Assume it's 12 months later and picking the front-runner failed badly. Work backward: the most likely causes, in order. Then argue the runner-up's best case honestly. Check **regret asymmetry**: which wrong choice hurts more, and can the worse-case be capped (a trial, a checkpoint, an exit)?

### Pass 6 — Recommend
The pick (or the honest "it hinges on X — resolve that first"), with: confidence (High/Med/Low + why), what would change it, the reversibility-aware framing — two-way door: "decide now, here's the cheap test and the exit"; one-way door: "resolve <the hinge> first; here's how" — and the first concrete step for the chosen path.

## The dossier — `decision/{topic}Dossier.md`

Write this **after** the background doc. Self-contained. **Read Me First and the recommendation up top.**

```markdown
# <Decision> — Decision Dossier

## 📌 Read Me First
Plain-language, 3–5 bullets, skimmable in 20 seconds.
- **The decision:** <one line>
- **My recommendation:** <the pick + confidence, plainly — or "genuinely close; the tiebreaker is yours: X">
- **The door:** <two-way (try it, here's the exit) / one-way (resolve X first)>
- **The hinge:** <the assumption that flips this if wrong>
- **First step:** <the concrete next action>

---

## The Decision
<Frame: options considered (including do-nothing), deadline, stakes, reversibility class + why.>

## Options Compared
One card per option:
### <Option> — <one-line verdict> [✅ pick / 🟡 viable / 🔴 eliminated]
- Case for: <strongest honest case> [labels]
- Case against: <same rigor> [labels]
- Fails a must-have? <no / yes — which>
- Wins when: <the conditions under which this would be the right pick>

## The Scoring
<The matrix with reasoning per cell, the weights (user's vs inferred), the weighted arithmetic.>

## What Would Change This
- <sensitivity results: the hinge assumptions and what flips the winner>

## If You Pick Differently
<The runner-up's honest best case, and how to cap the downside of either choice.>

## Sources
<numbered real URLs used, with dates>
```

### Example — what a good matrix cell and hinge look like
*(Illustrative, for "should our 4-person team adopt trunk-based development or stay on GitFlow?")*

> **Trunk-based × "release safety": strong** — small batches mean each deploy carries less risk, *provided* CI gates are real [recall — team's CI maturity unverified]. **GitFlow × "release safety": moderate** — release branches isolate risk but batch it; big-bang merges are where their last two incidents lived [from docs].
> **The hinge:** everything flips on CI maturity. With solid automated tests, trunk-based wins 4 of 5 weighted criteria; without them, it's the riskier option dressed as the modern one. Resolve that first — it's checkable in an afternoon.

## Self-check before finishing
Before declaring done, verify the dossier and fix any miss:
- Do-nothing/wait was genuinely considered, not listed and ignored.
- Must-haves were checked before fine-grained scoring; eliminated options say which must-have failed.
- Every matrix cell has a reason; weights are visible and attributed (user's vs inferred).
- The sensitivity check names the hinge; the recommendation's confidence reflects it.
- The pre-mortem attacked the front-runner, not a strawman; regret asymmetry was considered.
- Facts are labeled; nothing invented; values questions are handed to the user, not silently decided.

## Finishing up

Write `{topic}background.md` first (all six passes), then `{topic}Dossier.md`. Give the user a short chat summary: the recommendation with confidence, the door (two-way/one-way), the hinge, and the paths to both files. Don't paste the files into chat. Offer to re-run the matrix with corrected weights — or to chain onward: `/researcher` if an option needs deeper evidence, `/critic` to red-team the recommendation, `/stepbystep` to plan the chosen path.

## Notes on tone and rigor

- The skill structures; the user decides. Guard that line — especially when they ask "just tell me what to do" on a values-heavy call: give the recommendation AND name the value judgment inside it.
- Speed matters on two-way doors: a fast, capped experiment usually beats another week of analysis. Say so when it's true.
- Watch for the option the user is emotionally holding — steelman it fairly; a decision framework that feels like an ambush gets ignored.
- Pairs well downstream of `/researcher` or `/marketresearcher` (their dossiers are Pass-3 evidence), and upstream of `/stepbystep`.
