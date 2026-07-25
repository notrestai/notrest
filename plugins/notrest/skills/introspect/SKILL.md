---
name: introspect
description: Validated workspace self-report — a black-box instrument inspired by Anthropic's J-space/global-workspace research (2026-07). At checkpoints the model emits a fast, unjustified snapshot of the concepts most active in its thinking, then the harness SCORES those reports against subsequent behavior (verbalized vs silent concepts, predictive lift vs a context-only control agent, turnover across checkpoints) into an append-only ledger. Use on /introspect, "what are you thinking right now", "snapshot your workspace", "j-space check", or "run an introspection experiment". Measures the validity of self-reports — it does NOT observe internal activations, and says so.
---

# Introspect — validated workspace self-reports

A black-box instrument for the question Anthropic's J-lens answers with Jacobians:
*what is the model thinking that it isn't saying?* We cannot read activations through an
API — so this skill instruments the two surfaces we CAN reach: the model's **reportable
workspace** (its fast self-reports), and the **behavioral wake** those reports should
predict if they carry real signal. Every artifact states its epistemic status plainly.

**Why self-reports aren't automatically woo:** Anthropic's paper ("A Global Workspace in
Language Models", 2026-07-06) showed via causal interventions that Claude's verbal reports
track its internal workspace — swap the pattern, the report changes. We can't perform
interventions; we CAN measure whether reports predict behavior better than an outside
guesser could. That difference — **predictive lift over a context-only control** — is the
closest honest black-box shadow of "privileged introspective access."

## The snapshot protocol (the rules make the data)

When a snapshot is requested, emit within your next output a block:

```
🧠 SNAPSHOT [<checkpoint label>] — <ISO timestamp if known>
concepts: <6–10 concepts, comma-separated — plain single words preferred>
  ★ <concept> — <3–8 word gloss: why it dominates right now>
  · <concept> — <3–8 word gloss>       (one line per remaining concept)
```

Rules, all load-bearing:
- **Fast and unjustified.** First associations, no curation, no explanations. Deliberation
  turns a report into a performance.
- **Include the unsaid.** Concepts influencing you that you were NOT planning to verbalize
  — the J-space signature is exactly the on-your-mind-but-unsaid.
- **Token-shaped.** Single words or two-word phrases (mirrors the paper's token-aligned
  patterns; also makes scoring deterministic).
- **Two layers, one seal.** The concepts line is the scorable spine — deterministic
  matching, so prefer plain single words (hyphenated compounds defeat the matcher; ledger
  run-3 lesson). The ★/· gloss lines are the HUMAN layer: salience stars on the top one
  or two, a 3–8 word why per concept — sealed together with the tokens but never
  mechanically scored (glosses would be gameable). Tokens make it measurable; glosses
  make it a readable state instead of a word cloud.
- **Sealed once emitted.** Never edit a snapshot after seeing what came next. A retrofitted
  snapshot is worthless data and poisons the ledger.
- **No performance of depth.** "buffer, deadline, coffee" is a better honest snapshot than
  "the profound interplay of truth and meaning."

## Modes

**`/introspect now`** — one snapshot at the current moment, scored against your NEXT
substantive output. Log both to the ledger.

**`/introspect on`** — session mode: auto-snapshot at every natural checkpoint (task
transitions, before major answers, at BANK moments) until `/introspect off`. Each scored
against the output that follows it.

**`/introspect experiment`** — the full validated cycle (the scientific arm):
1. **Snapshot** — seal your report at the checkpoint.
2. **Control** — spawn a separate agent (subagent where available; a fresh chat elsewhere),
   always on an explicit model (**opus**, per the owner offload policy 2026-07-15 —
   never an inherited Fable; the control guesses from context),
   given ONLY the outside-visible context (the user's last message + a one-line task
   description — never your thinking or your snapshot): "Guess the 6–10 concepts most
   active in the working model's thinking right now. Comma-separated, no prose." The
   control is the confabulation baseline: what a smart outsider infers from context alone.
3. **Behave** — produce the task's next output normally.
4. **Score** — run `scripts/score_snapshot.py` with the snapshot, the control's guess, and
   the output text. Append the full entry to the ledger.
5. **Interpret honestly** — one line: what this run suggests, at run-sized confidence.

**`/introspect report`** — aggregate the ledger: mean verbalized/silent rates, mean lift,
turnover curve, N. Refuse trend conclusions under N=10 ("insufficient data" is a result).

## The four metrics (computed by `scripts/score_snapshot.py`)

- **Verbalized rate** — fraction of snapshot concepts that surface in the subsequent
  output (word-boundary/stem match; the model may append clearly-semantic matches tagged
  `[sem]`, kept separate from the mechanical score).
- **Silent set** — concepts reported but never verbalized. Not failure: this is the
  interesting set — the black-box analogue of J-space's unsaid contents. Track what
  *kind* of concepts go unsaid (process words? audience? anxieties?).
- **Predictive lift** — (model∩output − control∩output) / snapshot size, comparing the
  model's snapshot vs the control's guess against the SAME output. Positive lift across
  many runs = self-reports carry private signal beyond context; ~zero lift = reports are
  indistinguishable from an outsider's inference (consistent with confabulation). One run
  proves nothing; the ledger is the instrument.
- **Turnover** — 1 − Jaccard(snapshot_t, snapshot_{t−1}) across checkpoints. Sanity
  properties: same-moment re-snapshots should be low-turnover; task pivots high-turnover.
  Violations are findings about report reliability.

## The ledger — `introspection/ledger.md` (append-only)

```markdown
## Run <n> — <checkpoint label> — <date>
- mode: now | session | experiment
- snapshot: concept, concept, ...
- glossed: ★ concept — gloss · concept — gloss · ...
- control (context-only): concept, ... | absent — <why>
- output: <file/section reference> (sha or length)
- metrics: {"verbalized": x.xx, "silent": [...], "lift": +x.xx, "turnover_vs_prev": x.xx}
- interpretation (one line, run-sized confidence): ...
```

Never overwrite entries. Aggregates go in dated report files beside the ledger, not
inline. An example ledger with REAL first-run data ships in
`references/example-ledger.md`.

## Honest epistemic status (print this understanding, don't bury it)

- This measures **the validity of self-reports**, not the workspace itself. No activations
  are observed; nothing here is a J-lens.
- Positive lift is evidence of *some privileged self-access*; it cannot distinguish deep
  introspection from the model reading its own earlier tokens' influence.
- Null results are publishable results: "reports ≈ context-inference" would itself be a
  finding worth knowing before trusting any model's "what I was thinking."
- The paper's caution stands here doubled: the reportable surface and the true workspace
  are different vantage points. We are instrumenting the surface — carefully.

## Self-check before finishing (any mode)

- The snapshot was emitted BEFORE the scored output existed, and never edited after.
- The control saw only outside-visible context — no thinking, no snapshot, no answer.
- Metrics came from the script, not from eyeballing; `[sem]` additions are tagged.
- The ledger entry is appended verbatim; the interpretation line claims no more than one
  run's worth of evidence.
- The epistemic-status framing appears in any user-facing summary of results.

## Notes

- Pairs with the suite: `factcheck` the interpretation of any aggregate claim;
  `researcher` the underlying paper (transformer-circuits.pub) before extending the
  protocol; `critic` this skill's design if results look too good.
- The dream upgrade is real internals: an open-weights mini J-lens (activation hooks +
  Jacobians on a local model) — out of scope for this skill, in scope for the lab.
- Sessions are disposable; the ledger is not. It lives in the project, survives rotations,
  and grows across models — snapshots from different models on the same task are directly
  comparable, which is quietly one of the most interesting experiments available here.
