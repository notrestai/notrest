---
name: stepbystep
description: Turn a goal + documents into a dependency-ordered, stress-tested action plan with a per-step "done when" check and honest confidence scores, refined by a research→critique loop until it converges (hard cap 5 rounds) — producing a background doc + executable plan dossier (or --quick). Use on /stepbystep or asks for a step-by-step / action plan, "how do I do X", a checklist or playbook, or "turn this into a plan I can execute" — technical or not.
---

# Step By Step

Turns a goal plus its supporting documents into an action plan that is (a) correctly **ordered** by dependency, (b) **verifiable** step by step, (c) **stress-tested** before you execute it, (d) **deep-researched and iteratively refined until the findings stabilise**, and (e) honestly **confidence-scored**. An initial plan is built over six passes, then a deep-research → critique → redraft loop runs until it **converges** — until a fresh iteration stops surfacing new findings and reproduces the prior plan. The output is just **two files** — a consolidated background document and a final, conclusive executable plan, chosen as the best achievable from the documents provided at the prompt stage.

This skill produces a plan to inform and guide action; it is not professional advice. For high-stakes domains — medical, legal, financial, structural/electrical/gas, or anything where a mistake causes injury, legal exposure, or large loss — the plan must explicitly route the risky steps to a qualified professional rather than substitute for one.

## The prompt & documents

**Read every attached or referenced document first** — they are the source of truth for the goal, constraints, and context. The goal may also be stated in the prompt text itself; use both. Use `$ARGUMENTS` if populated; otherwise the text after `/stepbystep`.

If no documents are attached and the goal is thin, ask exactly one clarifying question (ideally: what does "done" look like, or what's the hard constraint) then begin. If documents are attached but the content isn't already in context, read them from disk before doing anything else. Treat the stated goal as the fixed yardstick — every pass serves *this* objective.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not fully sourced or saved; run again without `--quick` for the verifiable two-file version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output files

Derive a `{topic}` slug from the goal: lowercase, hyphen-joined, punctuation stripped, max ~50 chars (e.g. "migrate our app database to Postgres" → `migrate-app-database-to-postgres`). Create an `action-plan/` directory and write exactly two files:

- **`action-plan/{topic}background.md`** — every pass plus all refinement iterations, as sections within this one document.
- **`action-plan/{topic}Dossier.md`** — the final executable action plan.

If those files already exist from a prior run, suffix the topic with `-2` (then `-3`, etc.) so you never overwrite previous work.

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

## The six passes — all written into `action-plan/{topic}background.md`

Run all passes in order as sections of the single background document:

```markdown
# <Goal, as a title> — Action Plan Background
> Working document. Initial build (Passes 1–6), then the refinement loop (Passes 7–8) iterated to convergence, then conclude. The executable plan lives in {topic}Dossier.md.

## Pass 1 — Understand (goal, situation, task-type)
## Pass 2 — Unknowns & assumptions
## Pass 3 — Decompose & sequence
## Pass 4 — Per-step validation
## Pass 5 — Stress-test (dry-run / pre-mortem / red-team)
## Pass 6 — Risk, contingency & confidence    ← produces Candidate Plan v1
## Pass 7 — Deep research per step             ┐ repeat 7→8,
## Pass 8 — Critic & redraft (v2, v3, …)       ┘ checking convergence each loop
## Iteration log — v1 → v2 → … (deltas + convergence check per round)
## Pass 9 — Conclude (the converged / capped-best plan)
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

Guardrails so the loop always terminates:
- **Hard cap: 5 iterations** by default (the user may request fewer, e.g. "max 3"). Most goals converge in 2–4.
- If the cap is reached **without** convergence, stop anyway, finalise the best plan so far, and state plainly in the dossier that it did **not** fully stabilise and which parts are still moving.
- **Each iteration must narrow,** not widen. If iterations keep expanding scope, the goal or documents are underspecified — stop looping and surface the blocking unknowns instead.
- **Oscillation guard:** if a redraft reverts toward a version you already produced (the plan is flip-flopping A→B→A rather than settling), stop iterating — this is not non-convergence to push through, it means two defensible answers exist. Present both as viable approaches with their tradeoff in the dossier rather than burning iterations bouncing between them.

### Pass 9 — Conclude
Lock the converged (or capped-best) candidate as the final plan. Record how many iterations it took, whether it **converged or hit the cap**, and what stabilised. This is the conclusive plan — the best achievable from the documents available at the prompt stage — and it is what the dossier renders.

## The dossier — `action-plan/{topic}Dossier.md`

Write this **after** the background doc is complete, so it renders the **converged** plan from the refinement loop (Passes 7–9). It's the self-contained, executable plan — a doer should be able to act from this file alone. Synthesize; don't paste the passes in. Keep labels and confidence intact. **Read Me First and At-a-Glance up top, then Before You Start, then The Plan.**

```markdown
# <Goal, as a title> — Action Plan

## 📌 Read Me First
Plain-language, no jargon. 3–5 bullets a busy person can skim in 20 seconds.
- **The goal:** <what we're achieving, one short line>
- **The plan in a sentence:** <the overall approach, plainly>
- **How sure I am:** <high / medium / low, in plain words> — <refined over N research rounds until the plan stopped changing / hit the iteration cap and is still moving on X>
- **The catch:** <the single biggest risk or unknown to watch>
- **Before you dive in:** <the one thing to sort out first, if any>

**How this is laid out — two files:**
- **`{topic}background.md`** — all the working-out: understanding, unknowns, sequencing, validation, the stress-test, the per-step deep research, and every refinement round (v1 → vN). Read this for the *why* behind the steps.
- **`{topic}Dossier.md`** (this file) — the plan to execute. Sections: **At a Glance**, **Before You Start**, **The Plan** (ordered phases, each step with a "done when" check), **Checkpoints**, **If Things Go Wrong**, **Confidence**, **Sources**.

---

## At a Glance
- **Definition of done:** <how you'll know the whole thing succeeded>
- **Rough effort / time:** <estimate, labeled — or "not estimable: <why>">
- **Overall confidence:** <High/Med/Low + one-line why>
- **How this was built:** <N deep-research iterations; converged / hit cap>
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
- **Convergence:** <converged after N iterations / capped at N without full convergence — still moving on: …>.
- **Low-confidence steps:** <step — mitigation — what would raise it>.

## Sources
<numbered real URLs and/or the documents relied on, with [labels]>
```

### Example — what a good step looks like
*(Illustrative, from a plan to "migrate a production database to PostgreSQL". Note the concrete "done when", the reversibility reasoning, the confidence + what raises it, and the explicit dependencies.)*

> ### Phase 2 — Cutover
> 4. **Switch the application's connection string to the Postgres primary and deploy.** Done when: the app boots, health checks pass, and a read-and-write smoke test against three core tables succeeds. [ONE-WAY] (rolling back means re-syncing rows written after cutover) · [high-risk] · confidence [M] — rises to [H] once the dry-run cutover in staging has passed.
>    - depends on: replication lag under 1s (step 3); maintenance window announced (step 1).

## Self-check before finishing
Before declaring done, verify the dossier and fix any miss:
- Every step has a concrete "done when…" verification — no unverifiable steps.
- Dependencies are stated; no step needs an output a later step produces (re-run the dry-run mentally).
- Every [ONE-WAY] step has a rollback note or an explicit "cannot be undone" warning.
- Every Low-confidence step has a mitigation and what would raise it.
- High-stakes steps are flagged [needs expert] rather than given false DIY authority.
- Convergence status is stated (converged after N, or capped and still moving on X).
- Claims are labeled; nothing was fabricated to fill a gap the documents left open.

## Finishing up

Write `{topic}background.md` first (the six build passes plus every refinement round), then `{topic}Dossier.md`. Give the user a short chat summary: the goal, the overall confidence, **how many iterations it took to converge (or that it hit the cap)**, the single biggest risk, and the paths to both files — point them to the dossier as the thing to execute from. Don't paste the files into chat. Offer to dig deeper on any pass, to expand any phase into finer steps — or to chain onward: `/actionplan` to turn the dossier into a copy-paste runbook, `/critic` to attack the plan before executing it.

## Notes on tone and rigor

- The refinement loop is search-heavy and slow **by design**; the iteration cap and the narrow-each-round rule keep it bounded. If the user wants it fast, honour a lower cap and say what was traded away.
- Convergence is the goal, not iteration count — stop the moment results repeat; don't pad rounds to look thorough.

- Match step granularity to the doer's apparent level: a novice needs smaller, more explicit steps; an expert wants the plan, not a lecture.
- Sequencing is the value. If you're unsure of an ordering dependency, say so rather than guessing confidently.
- A plan that's mostly checkpoints and contingencies for a risky task is a *good* plan, not an over-cautious one.
- It's valid to conclude "this isn't ready to plan yet — resolve these blocking unknowns first," and hand back the unknowns instead of a shaky plan.
- If a pass produces little, say so honestly in the background doc rather than padding it.
