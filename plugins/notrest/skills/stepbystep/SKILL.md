---
name: stepbystep
description: Turn a goal + documents into a dependency-ordered, stress-tested action plan with a per-step "done when" check and honest confidence scores, refined by a research→critique loop until it converges (hard cap 5 rounds) — landing a decision record + [ONE-WAY] findings (or --quick). Use on /stepbystep or asks for a step-by-step / action plan, "how do I do X", a checklist or playbook, or "turn this into a plan I can execute" — technical or not.
---

# Step By Step

Turns a goal plus its supporting documents into an action plan that is (a) correctly **ordered** by dependency, (b) **verifiable** step by step, (c) **stress-tested** before you execute it, (d) **deep-researched and iteratively refined until the findings stabilise**, and (e) honestly **confidence-scored**. An initial plan is built over six passes, then a deep-research → critique → redraft loop runs until it **converges** — until a fresh iteration stops surfacing new findings and reproduces the prior plan. The output is the converged plan, delivered in chat, plus **validated records** in the archivist store: one `kind=decision` for the plan shape it settled on — the riskiest dependency named as the hinge — and one `kind=finding` per `[ONE-WAY]` step the sequencing exposed. The passes are the working-out; the records are what a later session, or `/actionplan`, can act on.

This skill produces a plan to inform and guide action; it is not professional advice. For high-stakes domains — medical, legal, financial, structural/electrical/gas, or anything where a mistake causes injury, legal exposure, or large loss — the plan must explicitly route the risky steps to a qualified professional rather than substitute for one.

**Router shape:** `planning`

## The prompt & documents

**Read every attached or referenced document first** — they are the source of truth for the goal, constraints, and context. The goal may also be stated in the prompt text itself; use both. Use `$ARGUMENTS` if populated; otherwise the text after `/stepbystep`.

If no documents are attached and the goal is thin, ask exactly one clarifying question (ideally: what does "done" look like, or what's the hard constraint) then begin. If documents are attached but the content isn't already in context, read them from disk before doing anything else. Treat the stated goal as the fixed yardstick — every pass serves *this* objective.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No records.** Write nothing to the store. Skip the "Setup & output" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not sourced into the store; run again without `--quick` for the recorded, verifiable version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output — the findings store

**No action-plan folder. No two-file write.** The converged plan is delivered in chat (the shape is below); what lands is **records** appended to the archivist store (`archive/findings.jsonl`, append-only, validated at the door): one `kind=finding` per `[ONE-WAY]` step, and one `kind=decision` for the plan shape, written last. The passes and the refinement loop below still run in full — they are what earns a sequence; they just do not land as files.

The sink:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{…}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder.) It prints the assigned `F-<n>` on success and **exits 2 naming the rule** on rejection — a decision with an empty evidence list, or a `[cited]` url that is not a URL, does not enter the store. Fix the record, re-run; never hand-append to the JSONL.

**Consult the store first.** Run one `index.py find "<goal>"` before Pass 1: a prior `kind=decision` on this same goal means offer *reuse* / *extend* / *fresh* — and if this run lands on a different plan shape, that is a `supersede`, not a second plan left lying beside the first.

Web search/fetch may help for steps that depend on current facts (versions, prices, procedures, regulations). Use them when the plan's correctness turns on something that could be out of date, and label what you found.

## Honesty, safety & scoring rules (apply throughout)

A confident-sounding plan that's wrong is dangerous — someone acts on it. These are non-negotiable.

- **Don't fabricate steps.** If the documents don't specify something a step needs, say so and make it an assumption or an open question — never invent a precise-sounding instruction to fill the gap.
- **Label every non-obvious claim** `[cited]` (retrieved this run, with URL), `[from docs]` (stated in the provided documents), `[recall]` (training knowledge, unverified), or `[assumption]` (you're supplying it — say so).
- **Defer on expertise you can't verify.** If a step needs licensed/specialist judgment or carries real physical/legal/financial danger, flag it `[needs expert]` and tell the user to get professional sign-off rather than presenting a do-it-yourself instruction with false authority.
- **Surface conflicts** in the documents or sources instead of smoothing them over.
- **Confidence scoring is transparent, never a bare number.** Use High / Medium / Low per step and overall, on these criteria:
  - **High** — well-understood, proven method, verifiable, reversible or low blast-radius, no blocking unknowns.
  - **Medium** — mostly clear but has a meaningful unknown, an external dependency, or a moderate failure cost.
  - **Low** — rests on an unresolved blocking unknown, is irreversible/high-cost, needs unconfirmed expertise, or leans on a shaky assumption.
  - Every **Low** step must carry a mitigation: resolve-first, test/spike, checkpoint, or expert sign-off. State what would raise the score.

## The six passes — the reasoning that earns the records

Run all passes in order, in full, as working prose in the session. The records land late — a `[ONE-WAY]` step is only worth recording once the refinement loop has stopped moving it:

```
Pass 1 — Understand (goal, situation, task-type)  → (reasoning — said vs assumed)
Pass 2 — Unknowns & assumptions                   → (reasoning — blocking vs not)
Pass 3 — Decompose & sequence                     → (reasoning — deps, critical path, [ONE-WAY] tags)
Pass 4 — Per-step validation                      → (reasoning — every "done when")
Pass 5 — Stress-test (dry-run/pre-mortem/red-team)→ (reasoning — what broke, what changed)
Pass 6 — Risk, contingency & confidence           → Candidate Plan v1
Pass 7 — Deep research per step                   ┐ repeat 7→8, checking convergence each loop
Pass 8 — Critic & redraft (v2, v3, …)             ┘ (iteration log: plan_lint.py converge, per round)
Pass 9 — Conclude → plan_lint.py check (the gate)  → records: kind=finding per surviving [ONE-WAY] step
                                                    record:  kind=decision — the plan shape, hinge inside
```

Passes 1–6 are detailed below exactly as before; Passes 7–9 add the iterative deep-research-and-critique engine.

### Pass 1 — Understand (goal, situation, task-type)
Read the documents. Establish the foundation the whole plan rests on:
- **Goal / definition of done:** the end state in concrete, checkable terms.
- **Current state:** where things stand now (the starting point).
- **Constraints:** time, budget, skills/people available, tools, access, legal/policy limits.
- **Doer & context:** who executes this and their apparent capability level (calibrate step granularity to it).
- **Task type:** classify it — e.g. technical/build, operational/process, creative, research, personal/habit, regulatory/compliance, troubleshooting/recovery — and note how that shapes the plan's vocabulary, rigor, and risk posture.
- **Said vs. assumed:** separate what the documents actually state `[from docs]` from what you're inferring `[assumption]`.

### Pass 2 — Unknowns & assumptions
Before planning, expose the holes:
- **Open questions / missing info**, each marked **blocking** (must resolve before starting) or **non-blocking** (resolve during execution).
- **Explicit assumptions** the plan will rely on, with how risky each is if wrong.
- **Expert-radar:** what would a seasoned practitioner in this task type worry about that the documents don't mention? (surfacing unknown-unknowns).

### Pass 3 — Decompose & sequence
Build the skeleton:
- **Atomic steps:** break the goal into concrete, individually doable actions.
- **Dependency map:** for each step, what must be true/done before it. Identify the **critical path**, what can run in **parallel**, and any prerequisite **gates**.
- **Reversibility tag:** mark each step **[reversible]** or **[ONE-WAY]** (hard/impossible to undo) — this drives where caution and checkpoints go.
- **Forks:** where the path depends on a condition discovered along the way, make it a **decision point** with branches rather than forcing a single line. If the whole task is condition-driven, structure it as a decision-tree/playbook instead of a linear list.

### Pass 4 — Per-step validation
Make every step checkable. For each step record: the **action** (what to do), **preconditions/inputs** (what must be in place), **output** (what it produces), and — critically — **"done when…"**: the concrete signal that the step worked. A step with no verification isn't finished being planned.

### Pass 5 — Stress-test (dry-run / pre-mortem / red-team)
Try to break the plan before reality does, with three distinct lenses:
- **Dry-run:** mentally execute the plan start to finish *as the doer*. Catch ordering bugs, missing prerequisites, steps that need an output a later step produces, circular dependencies.
- **Pre-mortem:** assume the plan failed badly. Work backward — what were the most likely causes?
- **Red-team:** actively attack it. Weakest link? Which external dependency could break? What's the worst case at each **[ONE-WAY]** door?
Then **revise the plan** from what these found, and note what changed.

### Pass 6 — Risk, contingency & confidence
For the revised plan:
- **Risk register:** the key risks (rough likelihood × impact) on the steps that matter.
- **Contingencies:** a fallback/recovery for each high risk, and rollback notes for irreversible steps.
- **Checkpoints:** explicit stop-and-verify gates — points where you confirm things are good before proceeding, so you don't stack ten steps on a broken foundation.
- **Confidence scoring:** score each phase and the plan overall per the rubric above; flag every Low step with its mitigation and what would raise it.

This completes **Candidate Plan v1**. The refinement loop below takes over.

### Optional checkpoint after v1
The refinement loop is search-heavy and slow. If the task is large or the user is cost/time-sensitive, you may pause **here, once** — briefly show the shape of Candidate Plan v1 and ask whether to run the full refinement loop or stop with v1. Default to running the loop unless the user asked to keep it quick or set a low cap. Never pause mid-loop; this is the only permitted interruption.

### Pass 7 — Deep research per step
Take the current candidate plan and research each step in depth — don't trust the first-pass phrasing. Work through the steps (prioritise the **high-risk, low-confidence, and [ONE-WAY]** ones first) and for each, find:
- the **best-practice method** for that specific step, and whether a materially **better way to do that step** exists `[cited]`;
- **common pitfalls / failure modes** practitioners hit on it;
- **prerequisites people routinely forget**;
- **current, correct specifics** the step depends on (versions, prices, procedures, regulations) — verify, don't recall;
- whether the **prompt documents already constrain** how this step must be done. When documents and generic best practice conflict, the documents win — note the conflict.

Record findings per step with labels and sources. **On iterations after the first, only re-research steps that changed in the last redraft or that the critic flagged** — each loop should be cheaper than the one before.

### Pass 8 — Critic & redraft
Put on a skeptical reviewer's hat and look across **everything so far** — all passes, the per-step deep research, and the current candidate plan:
- **Criticise:** where is the plan wrong, mis-ordered, missing a step, over-confident, or contradicted by the new research? Is there a fundamentally **better overall approach** to the goal — not just better individual steps? Re-apply the Pass-5 lenses (dry-run / pre-mortem / red-team) to whatever changed.
- **Redraft:** produce a **new candidate plan** (v2, v3, …) folding in the valid criticism and the research — re-sequenced, re-scored, flags updated. Judge "best" strictly against the **documents from the prompt stage**; they are the source of truth, deep research serves them.
- **Delta log:** record what changed from the previous version and *why*, so the evolution is auditable.

### The refinement loop & convergence (repeat Passes 7→8)
After each redraft, run the **convergence check**:
- Classify every change this iteration as **material** (alters a step's content, ordering, reversibility, risk, confidence, or the overall approach) or **cosmetic** (wording only).
- If **deep research surfaced nothing new** *and* **only cosmetic changes remain** ⇒ **converged — stop.** Repetition is the signal you're done.
- Otherwise iterate again (re-research the changed/flagged steps → critic → redraft).

**Measure the convergence; don't declare it.** "Nothing new surfaced" and "only cosmetic changes remain" are the two claims in this skill a model is worst placed to grade about its own draft. So write each candidate to a scratch file (`v2.md`, `v3.md`, … — working files, never deliverables) and after every redraft run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/stepbystep/scripts/plan_lint.py" converge --prev v2.md --curr v3.md
```

(Loose install: `scripts/plan_lint.py` relative to this skill folder.) Zero model tokens. It prints a **similarity ratio** over normalised lines and splits the diff exactly the way the check above asks you to: **material** line changes (content, ordering, reversibility, risk, confidence — what survives after emphasis, case, spacing and sentence punctuation are normalised away) versus **cosmetic-only** ones, plus what moved structurally (steps, `[ONE-WAY]` doors, Low steps, phases). Zero material change is what convergence looks like from outside the model.

**The ratio goes in the iteration log** — one line per round, e.g. `v2→v3 · similarity 0.972 · 4 material · 11 cosmetic · MOVING (phases 2→3)`. It exits 0 whatever it measures: it is a measurement, not a verdict, and the loop decision below stays yours.

Guardrails so the loop always terminates:
- **Hard cap: 5 iterations** by default (the user may request fewer, e.g. "max 3"). Most goals converge in 2–4.
- If the cap is reached **without** convergence, stop anyway, finalise the best plan so far, and state plainly — in the delivered plan *and* inside the decision record's statement — that it did **not** fully stabilise and which parts are still moving.
- **Each iteration must narrow,** not widen. If iterations keep expanding scope, the goal or documents are underspecified — stop looping and surface the blocking unknowns instead.
- **Oscillation guard:** if a redraft reverts toward a version you already produced (the plan is flip-flopping A→B→A rather than settling), stop iterating — this is not non-convergence to push through, it means two defensible answers exist. Present both as viable approaches with their tradeoff in the delivered plan, and land them as one `kind=conflict` record, rather than burning iterations bouncing between them.

### Pass 9 — Conclude
Lock the converged (or capped-best) candidate as the final plan. Record how many iterations it took, whether it **converged or hit the cap**, and what stabilised. This is the conclusive plan — the best achievable from the documents available at the prompt stage — and it is what the delivered plan renders and what the `kind=decision` record fixes.

**Then lint it — before it is delivered and before any record is emitted:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/stepbystep/scripts/plan_lint.py" check v3.md
```

Zero model tokens. It holds the final plan to the four things that are mechanical rather than a matter of judgement — the ones self-graded prose reads charitably at the end of a long loop:

- every step carries a concrete **"done when"**;
- the dependency graph is **acyclic**, and every `depends on` points at an **earlier** step that **exists** — a forward reference, a dangling reference, a duplicate step number and a cycle are each named with their step numbers, and the cycle is printed as a path;
- every `[ONE-WAY]` step has a rollback or says in words that it cannot be undone (one stated in **If Things Go Wrong** counts, if it names the step);
- every **Low**-confidence step carries a mitigation (one stated in the **Confidence** section counts, if it names the step).

Exit **0** clean · **5** findings, each printed as `file:line` + the step + the rule · **2** usage. **Fix what it finds and re-run** — and note that a fix which re-sequences a step is a *material* change, so the loop is not converged and you owe another round (re-measure with `converge`). If a finding stands deliberately — the plan genuinely cannot verify a step yet — it is **disclosed in the `kind=decision` record's statement**, naming the rule, never quietly dropped.

Fixture: `bash plugins/notrest/skills/stepbystep/scripts/fixture.sh` — exit 0 = every assertion held. It lints a canned converged plan, one canned plan per way of breaking the grammar, and measures `converge` on a known pair (identical, reworded, re-sequenced).

## The plan — delivered in chat

Deliver it **after** Pass 9, so it renders the **converged** plan from the refinement loop (Passes 7–9). It's the self-contained, executable plan — a doer should be able to act from this message alone. Synthesize; don't paste the passes in. Keep labels and confidence intact. **Read Me First and At-a-Glance up top, then Before You Start, then The Plan.**

```markdown
# <Goal, as a title> — Action Plan

## 📌 Read Me First
Plain-language, no jargon. 3–5 bullets a busy person can skim in 20 seconds.
- **The goal:** <what we're achieving, one short line>
- **The plan in a sentence:** <the overall approach, plainly>
- **How sure I am:** <high / medium / low, in plain words> — <refined over N research rounds until the plan stopped changing / hit the iteration cap and is still moving on X>
- **The catch:** <the single biggest risk or unknown to watch>
- **Before you dive in:** <the one thing to sort out first, if any>

**What lands where:** the working-out — understanding, unknowns, sequencing, the stress-test, the per-step deep research, every refinement round (v1 → vN) — stays in this session as prose; the plan below is what you execute; the store keeps the shape decision and every `[ONE-WAY]` step (`index.py track --kind decision`). Sections here: **At a Glance**, **Before You Start**, **The Plan** (ordered phases, each step with a "done when" check), **Checkpoints**, **If Things Go Wrong**, **Confidence**, **Sources**.

---

## At a Glance
- **Definition of done:** <how you'll know the whole thing succeeded>
- **Rough effort / time:** <estimate, labeled — or "not estimable: <why>">
- **Overall confidence:** <High/Med/Low + one-line why>
- **How this was built:** <N deep-research iterations; converged / hit cap — final round measured: similarity <x.xxx>, <n> material changes>
- **Biggest risk:** <the headline risk>

## Before You Start
- **Prerequisites:** <what must be in place first>
- **Resources / tools needed:** <list>
- **Assumptions this plan relies on:** <each, flagged if risky>
- **Resolve first (blocking unknowns):** <questions to answer before step 1, or "none">

## The Plan
Ordered phases. Show dependencies and what can run in parallel. Where the path forks, use a decision point. Each step carries flags as needed: [ONE-WAY] irreversible · [high-risk] · [needs expert] · confidence [H/M/L].

### Phase 1 — <name>
1. **<Step>** — <what to do>. Done when: <verification>. <flags + confidence>
   - depends on: <prior step(s) / nothing>
2. ...

### Decision point: <condition?>
- If <A> → go to <…>
- If <B> → go to <…>

(continue phases)

## Checkpoints
- **After <step/phase>:** verify <what> before proceeding.

## If Things Go Wrong
- **<Risk / failure point>:** <contingency / fallback>. Rollback: <how to undo, for irreversible-adjacent steps>.

## Confidence
- **Overall:** <H/M/L>. Why: <reasoning>.
- **Convergence:** <converged after N iterations / capped at N without full convergence — still moving on: …>. Measured, final round: <similarity x.xxx · n material line changes>.
- **Low-confidence steps:** <step — mitigation — what would raise it>.

## Sources
<numbered real URLs and/or the documents relied on, with [labels]>
```

### Example — what a good step looks like
*(Illustrative, from a plan to "migrate a production database to PostgreSQL". Note the concrete "done when", the reversibility reasoning, the confidence + what raises it, and the explicit dependencies.)*

> ### Phase 2 — Cutover
> 4. **Switch the application's connection string to the Postgres primary and deploy.** Done when: the app boots, health checks pass, and a read-and-write smoke test against three core tables succeeds. [ONE-WAY] (rolling back means re-syncing rows written after cutover) · [high-risk] · confidence [M] — rises to [H] once the dry-run cutover in staging has passed.
>    - depends on: replication lag under 1s (step 3); maintenance window announced (step 1).

## The output — the records

**One `kind=finding` per `[ONE-WAY]` step, then one `kind=decision` for the plan shape.** Write them after Pass 9, so they carry the convergence: recording a step the loop is still moving is recording a draft.

- **Each `[ONE-WAY]` step that survived to the final plan:** `kind=finding`, `relation=toward` — the statement says what becomes irreversible, its "done when", and the rollback (or the explicit "cannot be undone"). These are the steps a doer cannot take back, so they are the ones worth finding a year later.
- **The plan shape:** `kind=decision`, `relation=toward`, written last. The statement carries the approach in one line, the confidence, whether it **converged after N iterations or hit the cap** — with the *measured* final-round similarity and material-change count from `plan_lint.py converge`, and any `plan_lint.py check` finding left standing — and **the hinge — the riskiest dependency**: the one thing that, if it fails or turns out false, re-sequences the whole plan. A plan recorded without its hinge is a plan nobody can audit when it breaks. `links` names the `[ONE-WAY]` records it rests on.
- **An approach the critic killed mid-loop:** `kind=backtrack`, `relation=back` — the v1 that lost to v3 is a finding.
- **Two defensible plans the oscillation guard exposed:** `kind=conflict`, `relation=lateral` — both approaches with their tradeoff, never a coin-flip presented as a decision.
- **A prior plan for this goal that this run replaces:** `index.py supersede F-<old> --by F-<new>`.

### The snippet, filled

*(The same Postgres cutover, recorded.)*

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"stepbystep-2026-07-25",
  "skill":"stepbystep",
  "kind":"finding",
  "ask":"migrate the production database to PostgreSQL",
  "statement":"[ONE-WAY] Phase 2 step 4 — switching the app connection string to the Postgres primary. Done when: app boots, health checks pass, read-and-write smoke test across three core tables succeeds. Rolling back means re-syncing every row written after cutover, so the rollback is a restore, not an undo. Confidence M, rises to H once the staging dry-run cutover passes.",
  "evidence":[{"type":"path","ref":"docs/migration-brief.md","label":"cited"},
              {"type":"command","ref":"psql -c \"SELECT pg_last_wal_receive_lsn()\"","label":"estimate"},
              {"type":"url","ref":"https://www.postgresql.org/docs/current/logical-replication.html","label":"cited"}],
  "relation":"toward",
  "links":[]}'
```

Then the decision record, last, with the hinge inside it:

```bash
… add --root . --json '{"session":"stepbystep-2026-07-25","skill":"stepbystep","kind":"decision",
  "ask":"migrate the production database to PostgreSQL",
  "statement":"Plan shape: logical-replication cutover in a 20-minute window, 4 phases, 2 [ONE-WAY] doors — chosen over dump-and-restore (8h downtime) and dual-write (2 weeks of app work). Converged after 3 refinement rounds; confidence M. THE HINGE — the riskiest dependency: replication lag holding under 1s at production write volume. If it does not, the whole sequence reverts to dump-and-restore with a maintenance window, so prove the lag in staging before Phase 2.",
  "evidence":[{"type":"path","ref":"docs/migration-brief.md","label":"cited"},
              {"type":"command","ref":"pgbench -c 32 -T 300 staging","label":"estimate"}],
  "relation":"toward","links":["F-71","F-72"]}'
```

Each `add` prints its `F-<n>`. A non-zero exit means the record was turned away with its rule named — fix it and re-run.

## Self-check before finishing
Before declaring done, verify the records and fix any miss:
- **`plan_lint.py check` exited 0 on the final plan** — or every finding it printed is disclosed in the `kind=decision` statement with its rule. It mechanizes the four items marked ✓ below; run it rather than reading for them.
- **The convergence is measured, not asserted** — `plan_lint.py converge` ran on the last pair, its ratio and material count are in the iteration log, and the same numbers reach the delivered plan and the decision record.
- **Records validated at the door (`add` exited 0)** — every id was printed by the script, nothing hand-appended.
- ✓ Every step has a concrete "done when…" verification — no unverifiable steps.
- ✓ Dependencies are stated; no step needs an output a later step produces (re-run the dry-run mentally).
- ✓ Every [ONE-WAY] step has a rollback note or an explicit "cannot be undone" warning — and its own `kind=finding` record.
- **The hinge is in the `kind=decision` statement**, named as the riskiest dependency, with the convergence status beside it.
- ✓ Every Low-confidence step has a mitigation and what would raise it.
- High-stakes steps are flagged [needs expert] rather than given false DIY authority.
- Convergence status is stated (converged after N, or capped and still moving on X).
- Claims are labeled; nothing was fabricated to fill a gap the documents left open.

## Finishing up

Run the passes and the refinement loop (measuring each round with `scripts/plan_lint.py converge`), lint the final plan with `scripts/plan_lint.py check` and fix what it finds, deliver the converged plan in chat in the shape above, then emit the `[ONE-WAY]` records and the `kind=decision` last — the lint before the records, so nothing enters the store that the gate has not seen. Close with the goal, the overall confidence, **how many iterations it took to converge (or that it hit the cap)**, the single biggest risk, and the record ids — plus `index.py track --kind decision` as the one command that shows every plan shape this project has settled on. Offer to dig deeper on any pass, to expand any phase into finer steps — or to chain onward: `/actionplan` to turn the decision record into a copy-paste runbook, `/critic` to attack the plan before executing it.

## Notes on tone and rigor

- The refinement loop is search-heavy and slow **by design**; the iteration cap and the narrow-each-round rule keep it bounded. If the user wants it fast, honour a lower cap and say what was traded away.
- Convergence is the goal, not iteration count — stop the moment results repeat; don't pad rounds to look thorough.

- Match step granularity to the doer's apparent level: a novice needs smaller, more explicit steps; an expert wants the plan, not a lecture.
- Sequencing is the value. If you're unsure of an ordering dependency, say so rather than guessing confidently.
- A plan that's mostly checkpoints and contingencies for a risky task is a *good* plan, not an over-cautious one.
- It's valid to conclude "this isn't ready to plan yet — resolve these blocking unknowns first," and hand back the unknowns instead of a shaky plan.
- If a pass produces little, say so honestly in the session and write no record for it — padding the store is worse than a thin track.
