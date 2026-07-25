---
name: decider
description: "Structure any decision — options (always including do-nothing/wait), criteria weighted by what the user actually cares about, evidence per option, a reasoned scoring matrix with a sensitivity check (\"which assumption flips the winner\"), a pre-mortem on the front-runner, and a recommendation with confidence + reversibility framing — landing a validated DECISION RECORD in the archivist store (or --quick). Use on /decider or \"should I…\", \"help me decide/choose\", \"X or Y\", \"compare these options\", \"what are the tradeoffs\". The user decides; this structures."
---

# Decider

Takes a decision — technical, business, or personal — and gives it a structure that makes the choice visible: what the real options are, what actually matters to *this* user, what the evidence says, which assumption the whole thing hinges on, and what the front-runner looks like after an honest attempt to break it. The reasoning runs through six passes; the output is a **validated decision record** in the archivist store, with the hinge in its statement.

Two framing rules govern everything: **facts vs values** (evidence is checkable; how much the user cares about each criterion is theirs — never substitute your weights for theirs silently), and **reversibility** (a two-way door rewards deciding fast and learning; a one-way door rewards resolving the load-bearing unknown first).

## The prompt

The decision is everything the user passed when invoking the skill. Use `$ARGUMENTS` if populated; otherwise the text after `/decider`. Attached documents (a research dossier, a spec, a comparison someone sent) are evidence — read them first. If the decision or its options are genuinely unclear, ask exactly one clarifying question (ideally: "what are you deciding between, and by when?"), then begin.

For decisions with professional stakes — medical, legal, large financial commitments — structure the thinking, flag `[needs expert]` where licensed judgment is required, and say plainly the final call needs a professional, not a framework.

**Consult the store first.** Run one `index.py find "<topic>"` before Pass 1: prior `kind=finding` records are ready-made Pass-3 evidence (carried with their own labels and dates), and a prior `kind=decision` on the same question deserves to be surfaced before re-deciding it — if this run overturns it, that is a `supersede`, not a second opinion left lying beside the first.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No records.** Write nothing to the store. Skip the "Setup & output" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass depth.
- **Output in chat only:** the **Read Me First** block this skill defines (recommendation, the hinge, the reversibility call), then a short options comparison. No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not sourced into the store; run again without `--quick` for the recorded, verifiable version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output — the findings store

**No decision folder. No two-file write.** This skill's output is a **decision record** appended to the archivist store (`archive/findings.jsonl`, append-only, validated at the door), with any load-bearing evidence the passes turned up landing as its own record first. The six passes below still run in full — they are what earns the statement; they just do not land as files.

The sink:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{…}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder.) It prints the assigned `F-<n>` on success and **exits 2 naming the rule** on rejection — a decision with an empty evidence list, or a `[cited]` url that is not a URL, does not enter the store. Fix the record, re-run; never hand-append to the JSONL.

Web search/fetch: use where the decision turns on checkable facts (prices, capabilities, deadlines, track records). **Search budget (token discipline):** ~10 searches default (~2 in `--quick`); a preference-dominated decision may need none — say so instead of decorating it with searches.

## Honesty rules (a structured wrong answer is still wrong)

- **Never invent figures** — prices, dates, capabilities, success rates. Not found = "not found", labeled. (A computed comparison is `[estimate]` — show the math.)
- **Label evidence** `[cited]` (retrieved this run, with URL + date), `[from docs]` (in the user's documents), `[estimate]`, `[recall]`, or `[unverified]`. In the store, `[from docs]` is an evidence item of `type: path` labeled `cited` — the document is the citation; the path is the URL.
- **Scores are reasoning, never bare numbers.** Every cell of the matrix carries its one-line why. A number without a why is an opinion in costume.
- **The weights are the user's.** Infer them from what the user said if you must, but show them and invite correction — a perfect matrix under the wrong weights recommends the wrong thing.
- **Surface the hinge.** Every real decision has one or two assumptions that flip the outcome if wrong. Finding them is half this skill's value; hiding them is malpractice.
- **Don't manufacture a winner.** "These are genuinely close — the tiebreaker is your appetite for X" is a valid, valuable verdict.

## The six passes — the reasoning that earns the record

Run all six in order, in full, as working prose in the session. A decision record without the passes behind it is a preference with a timestamp.

```
Pass 1 — Frame                       → (reasoning)
Pass 2 — Criteria & weights          → (reasoning — the weights are the user's)
Pass 3 — Evidence per option         → records: kind=finding per load-bearing fact
Pass 4 — Score & sensitivity         → records: kind=conflict where the evidence fights
Pass 5 — Pre-mortem the front-runner → records: kind=backtrack for an option killed here
Pass 6 — Recommend                   → record:  kind=decision, the hinge in the statement
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

## The output — the decision record

Write it **after** Pass 6, so it carries the pre-mortem's damage. One `kind=decision` record, `relation=toward`, and **the hinge lives in the statement** — a decision recorded without the assumption that flips it is a decision nobody can audit later. The statement carries, in 1–3 sentences: the pick, the confidence, the door (two-way / one-way), and the hinge. `links` names the `kind=finding` records the pick rests on.

Evidence is the checkable substrate under the call — the source for a price, the doc for a capability, the command that measured the thing — each with its own label. `[cited]` needs a real URL; a matrix cell you computed is `[estimate]`; a capability you believe but did not verify is `[unverified]`. Labels never upgrade on the way into the store.

### The snippet, filled

*(For "should our 4-person team adopt trunk-based development or stay on GitFlow?")*

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"decider-2026-07-25",
  "skill":"decider",
  "kind":"decision",
  "ask":"trunk-based development or stay on GitFlow, 4-person team?",
  "statement":"Adopt trunk-based development — confidence medium, two-way door (revert to release branches in a sprint). THE HINGE: CI maturity. With real automated gates it wins 4 of 5 weighted criteria; without them it is the riskier option dressed as the modern one, so verify the gates first — checkable in an afternoon.",
  "evidence":[{"type":"url","ref":"https://dora.dev/research/","label":"cited"},
              {"type":"command","ref":"gh run list --limit 50 --json conclusion","label":"estimate"},
              {"type":"path","ref":"docs/incidents/2026-05-merge.md","label":"cited"},
              {"type":"coord-line","ref":"COORD.md:118","label":"recall"}],
  "relation":"toward",
  "links":["F-21","F-22"]}'
```

If this overturns a prior decision on the same question, flip it — never leave two live answers:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" supersede F-9 --by F-23 --note "CI gates verified since."
```

## Self-check before finishing
Before declaring done, verify the record and fix any miss:
- **Records validated at the door (`add` exited 0)** — the id was printed by the script, nothing hand-appended.
- Do-nothing/wait was genuinely considered, not listed and ignored.
- Must-haves were checked before fine-grained scoring; eliminated options say which must-have failed.
- Every matrix cell had a reason; weights were visible and attributed (user's vs inferred).
- **The hinge is in the statement**, and the confidence reflects it; the door is named.
- The pre-mortem attacked the front-runner, not a strawman; regret asymmetry was considered.
- Facts are labeled; nothing invented; values questions are handed to the user, not silently decided.
- A prior decision this one overturns was `supersede`d, not left standing beside it.

## Finishing up

Run the six passes, then write the decision record. Give the user a short chat summary: the recommendation with confidence, the door (two-way/one-way), the hinge, and the record id — plus `index.py track --kind decision` as the one command that shows every call this project has made. Don't paste the record into chat. Offer to re-run the matrix with corrected weights (a changed answer is a `supersede`) — or to chain onward: `/researcher` if an option needs deeper evidence, `/critic` or `/refuter` to red-team the recommendation, `/stepbystep` to plan the chosen path.

## Notes on tone and rigor

- The skill structures; the user decides. Guard that line — especially when they ask "just tell me what to do" on a values-heavy call: give the recommendation AND name the value judgment inside it.
- Speed matters on two-way doors: a fast, capped experiment usually beats another week of analysis. Say so when it's true.
- Watch for the option the user is emotionally holding — steelman it fairly; a decision framework that feels like an ambush gets ignored.
- Pairs well downstream of `/researcher` (its finding records are Pass-3 evidence — link them) or `/marketresearcher`, and upstream of `/stepbystep`.
