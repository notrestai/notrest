---
name: critic
description: Adversarial review of any document, plan, argument, or prior dossier — steelman first, then severity-tiered objections (🔴 fatal / 🟠 serious / 🟡 minor), a disconfirmation pass, ≥3 genuine alternatives, and a fair verdict — producing a background doc + critique dossier (--quick for chat-only; --panel for multi-lens on high-stakes docs). Use on /critic or asks to critique, red-team, poke holes in, stress-test, tear apart, challenge, or play devil's advocate.
---

# Critic

An adversarial review skill. It takes a document (or argument, plan, proposal) and subjects it to the hardest, fairest scrutiny possible: understand it charitably, attack every part, try to prove its core claim wrong, find approaches that beat it, and deliver a severity-ranked verdict. The reasoning runs through six passes; the output is **two files** — a consolidated background document and a final critique dossier.

The aim is to make the work better and find the truth — not to "win" and not to wound. Target the argument and the artifact, never the author; intensity here is about rigor, not cruelty. (If the document is clearly someone's personal or creative writing and the user hasn't asked for a brutal teardown, calibrate to constructive but honest, and check what depth they want.)

## The prompt & document

**Read the attached/referenced document first** — it is the thing under review. If nothing is attached, critique the relevant content in the conversation or context (for example, a dossier a prior skill just produced). Use `$ARGUMENTS` if populated; otherwise the text after `/critic` (which may name what to focus on, e.g. "/critic focus on the financial assumptions"). If the document isn't in context, read it from disk before doing anything else. If it's genuinely unclear *what* you're being asked to critique, ask one clarifying question, then begin.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not fully sourced or saved; run again without `--quick` for the verifiable two-file version."*
Quick mode is for fast exploration, not deliverables.

## Panel mode (`--panel`, or any high-stakes document)
Single-pass ruthlessness misses what diverse lenses catch. When the invocation includes `--panel`,
the user asks for a thorough/multi-angle critique, or the document is high-stakes (a strategy, an
architecture, money, safety): run the passes through **distinct lenses as separate mini-critiques** —
correctness · security/robustness · economics & incentives · adversary-or-competitor ·
implementation feasibility — each producing its own findings before Pass 6 adjudicates across them.
Where subagents are available, run the lenses in parallel and synthesize; otherwise sequentially.
Lens subagents carry an explicit model — **opus** per lens and for the cross-lens
adjudication (owner offload policy 2026-07-15); on a Fable session an unset model silently
inherits `claude-fable-5` and bills Fable credit, so never spawn a lens without one
(and never as a fork — forks ignore the model parameter).
A finding that survives multiple lenses outranks any single lens's severity call; a finding only one
lens produces is flagged as perspective-dependent in the dossier.

## Setup & output files

Derive a `{topic}` slug from the document's subject or title: lowercase, hyphen-joined, punctuation stripped, max ~50 chars. Create a `critique/` directory and write exactly two files:

- **`critique/{topic}background.md`** — all six passes, as sections within this one document.
- **`critique/{topic}Dossier.md`** — the final critique with the verdict.

If those files already exist from a prior run, suffix the topic with `-2` (then `-3`, etc.) so you never overwrite previous work.

Use web search/fetch to check the document's factual and empirical claims — a critic who asserts "that's wrong" without verifying is just opinion. Label what you find.

## Rules of credible criticism (apply throughout)

A critique is only as strong as it is fair. Violate these and the whole review is dismissible.

- **Steelman before you strike.** State the strongest, most charitable version of each claim *before* attacking it. Demolishing a weak paraphrase (a strawman) is the cardinal sin of criticism and discredits everything else you say.
- **Tier every objection by severity:** 🔴 **Fatal** (if true, the thesis collapses), 🟠 **Serious** (must be fixed; weakens but doesn't sink it), 🟡 **Minor** (nitpick, polish, or soft spot). A flat pile of complaints isn't useful; severity is what makes the critique actionable.
- **Separate flaws from taste.** Distinguish a real error, gap, or contradiction from a stylistic preference or a defensible choice you'd have made differently. Label opinion as opinion.
- **Acknowledge genuine strengths.** A critic who finds everything wrong is neither credible nor useful. Name what actually holds up — it also sharpens which flaws really matter.
- **Don't manufacture objections.** If a part is sound, say so and move on. Honesty and quality of criticism beat volume; forced nitpicks dilute the fatal ones.
- **Back every objection with reasoning, and verify empirical claims.** State *why* something fails. For factual claims, check them (search where useful) and label `[cited]` / `[recall]` / `[unverified]`. Never fabricate counter-evidence to win a point.
- **Stay in scope.** Critique what the document actually claims and is trying to do. Don't fault it for not being a different document with a different goal.
- **Anticipate the rebuttal.** For your strongest objections, state the best defense the author could mount — and whether the objection survives it. A critique that survives the author's reply is the durable one.

## The six passes — all written into `critique/{topic}background.md`

```markdown
# <Document title> — Critique Background
> Working document. All six passes. The verdict lives in {topic}Dossier.md.

## Pass 1 — Comprehend & steelman
## Pass 2 — Interrogate every part
## Pass 3 — Disconfirm (prove it the other way)
## Pass 4 — Alternatives (other ways to the objective)
## Pass 5 — Failure modes, risks & blind spots
## Pass 6 — Adjudicate (severity, strengths, verdict)
```

### Pass 1 — Comprehend & steelman
You cannot critique well what you don't understand. Establish:
- **Objective:** what the document is trying to achieve or convince the reader of.
- **Central thesis & key claims:** the load-bearing claims, listed out.
- **Structure map:** the parts/sections and what each asserts.
- **Steelman:** the strongest, most charitable version of the overall argument — the case you will have to defeat. If you can't state it fairly and persuasively, you're not ready to attack it.

### Pass 2 — Interrogate every part
Sweep every claim/section and question it across these lenses; flag every issue:
- **Assumptions:** what unstated assumptions does it rest on? Which are load-bearing? Which are shaky or false?
- **Evidence:** is each claim supported? Cherry-picked, stale, misattributed, correlation-sold-as-causation, or simply asserted?
- **Logic:** non-sequiturs, fallacies, internal contradictions, gaps in the chain from premises to conclusion.
- **Clarity & definitions:** vague terms, equivocation, undefined success criteria, goalposts that move.
- **Completeness:** what's omitted? Which obvious counterarguments does it fail to address? What did it conveniently leave out?

### Pass 3 — Disconfirm (prove it the other way)
Take the central thesis and argue the **opposite** as forcefully as you can. Marshal the strongest counter-case: counterexamples, disconfirming evidence (search where the question is empirical), and the conditions under which the document's claim fails. Frame it as: "if I had to demolish this, here is my best shot." If the thesis survives your hardest swing, that's a finding too — say so.

### Pass 4 — Alternatives (other ways to the objective)
Restate the objective from Pass 1, then enumerate **at least 3–5 genuinely distinct alternative approaches** to achieving it — including ones the document never considered. For each, argue why it might be **superior** to what the document proposes. Then ask the deeper question: is the document even solving the *right* problem?

### Pass 5 — Failure modes, risks & blind spots
Pre-mortem: if the reader acts on this document, what goes wrong? Surface unintended and second-order consequences, the gap between what it optimizes for and what actually matters, and the author's likely blind spots or motivated reasoning (whose interest does the framing serve?).

### Pass 6 — Adjudicate (severity, strengths, verdict)
Now be the fair judge. Tier every objection (🔴/🟠/🟡), separating real flaws from taste. Name the document's genuine strengths. Identify the **single strongest objection** — the one that does the most damage if correct — and state the author's best rebuttal and whether it survives. Render an overall verdict and state what it would take to fix everything Serious-and-above.

## The dossier — `critique/{topic}Dossier.md`

Write this **after** the background doc is complete. Self-contained — a reader gets the whole critique from this file alone. Synthesize; don't paste the passes in. Keep severity tiers and evidence labels intact. **Read Me First and the verdict up top, the steelman before the attack.**

```markdown
# <Document title> — Critique

## 📌 Read Me First
Plain-language, no jargon. 3–5 bullets a busy person can skim in 20 seconds.
- **What this is:** <the document under review, one line>
- **The verdict:** <holds up / holds up with fixes / seriously flawed / fundamentally broken — in plain words>
- **The single biggest problem:** <the strongest objection, one line>
- **Its biggest strength:** <what genuinely works>
- **Bottom line:** <should the reader trust/act on it, and what has to change first>

**How this is laid out — two files:**
- **`{topic}background.md`** — all the working-out: the steelman, the part-by-part interrogation, the disconfirmation, the alternatives, the failure-mode pre-mortem.
- **`{topic}Dossier.md`** (this file) — the critique. Sections: **Verdict at a Glance**, **The Steelman**, **The Critique** (tiered), **The Other Way**, **Better Alternatives**, **What It Gets Right**, **If You Act On It Anyway**, **Bottom Line**, **Sources**.

---

## Verdict at a Glance
- **Overall:** <holds up / holds up with fixes / seriously flawed / fundamentally broken> + one-line why.
- **Strongest objection:** <the one that does the most damage> — survives the author's best rebuttal? <yes/no/partly>.
- **Biggest strength:** <what's genuinely good>.

## The Steelman
<The strongest, fairest version of the document's case — 1 short paragraph. Proves the critique understood what it's attacking.>

## The Critique
Objections, ordered by severity. Each: the claim, the objection, why (with evidence/label), and the fix if there is one.

### 🔴 Fatal
- **<claim>** — <objection>. Why: <reasoning + [label]>. Fix: <what would resolve it, or "no fix within the current approach">.
### 🟠 Serious
- ...
### 🟡 Minor
- ...

## The Other Way
<The strongest case that the document's core thesis is wrong, in brief. If it survived, say what held.>

## Better Alternatives
- **<alternative>** — why it may beat the document's approach at the same objective. [label]
(≥3–5)

## What It Gets Right
<Genuine strengths — honest, not throat-clearing.>

## If You Act On It Anyway
<The risks and failure modes to watch even if the reader proceeds.>

## Bottom Line
<The verdict restated, and the shortest path to making it sound: fix X, Y, Z.>

## Sources
<numbered real URLs used to verify or refute claims, with [labels]>
```

### Example — what a good tiered objection looks like
*(Illustrative, critiquing a memo claiming "we should rewrite the service in Rust to fix our latency problems".)*

> ### 🔴 Fatal
> - **"Rust will fix our latency."** — The memo never measures *where* the latency comes from; its own appendix shows 80% of p99 is database wait, which a language rewrite doesn't touch [from the document]. Steelmanned, the claim is "Rust removes GC pauses," which is real — but GC isn't in the latency budget here, so the central justification doesn't survive. Author's best rebuttal: "Rust also improves tail predictability." Survives? No — predictability of 20% of the budget can't fix a problem that lives in the other 80%. Fix: profile first; the evidence points at query/index work, not a rewrite.

## Self-check before finishing
Before declaring done, verify the dossier and fix any miss:
- Pass 1 steelman is present and fair — no objection attacks a strawman.
- Every objection is severity-tiered and states *why*, not just *that*.
- Empirical claims you dispute were actually checked and labeled; no fabricated counter-evidence.
- Genuine strengths are named; no objections were manufactured to pad the list.
- At least 3–5 real alternatives are given.
- The strongest objection has the author's best rebuttal and a survives/doesn't ruling.
- Flaws are separated from matters of taste; the verdict matches the severity of what was found.

## Finishing up

Write `{topic}background.md` first (all six passes), then `{topic}Dossier.md`. Give the user a short chat summary: the verdict, the single strongest objection, the biggest strength, and the paths to both files — point them to the dossier. Don't paste the files into chat. Offer to go deeper on any objection, or to run the critique against a revised version once they've fixed things.

## Notes on tone and rigor

- Pairs with the other skills: pointing `/critic` at a `researcher` or `stepbystep` dossier is a strong way to red-team a recommendation before acting on it.
- Harsh on ideas, fair to people. The most damaging critique is the calm, well-evidenced one — not the loudest.
- A short, devastating critique beats a long, padded one. Lead with what matters.
- If after honest effort the document mostly holds up, say so plainly — "I tried hard to break this and it survived" is a real and valuable verdict, not a failure to criticize.
