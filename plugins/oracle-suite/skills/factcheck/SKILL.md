---
name: factcheck
description: Verify claims against real sources — extract the load-bearing claims from a statement, document, or answer, hunt primary sources (two independent ones for CONFIRMED; daisy-chains detected and collapsed), and deliver claim-by-claim verdicts ✅ CONFIRMED / 🟡 PLAUSIBLE / 🔴 REFUTED / 🔵 MISLEADING / ⚪ UNVERIFIABLE with dated citations — producing a background doc + verdict dossier (or --quick for the top claims in chat). Use on /factcheck or "is this true", "fact-check / verify / double-check this", "did X really say/do that".
---

# Factcheck

Takes any claim-bearing thing — a statement, an article, a forwarded message, a report, or an AI answer (including this suite's own dossiers) — and verifies what it actually asserts: extract the claims that carry the weight, chase each to real sources, detect when ten citations are really one origin wearing costumes, and return verdicts a reader can act on. The reasoning runs through four passes; the output is **two files** — a consolidated background document and a final verdict dossier.

The special power of this skill is the **🔵 MISLEADING** verdict: the claim that's technically true but framed to make you believe something false. Pure true/false checkers miss it; it's where most real-world deception lives.

## The prompt & subject

The subject is what the user passed — pasted text, an attached document, a URL to fetch, or "the answer you just gave me." Use `$ARGUMENTS` if populated; otherwise the text after `/factcheck`. If the subject document isn't in context, read/fetch it first. If it's genuinely unclear what to check, ask exactly one clarifying question, then begin.

Web search/fetch is this skill's engine. If those tools are unavailable, say so plainly — a fact-check without live sources is just an opinion with a rubric — and offer only clearly-labeled `[recall]` assessments.

**Consult the index first (if present).** If the repo carries an `oracle-index.md` — or the **archivist** skill is installed and prior ORACLE output folders exist — run one `find` on the subject before Pass 1: a prior `factcheck/` dossier on the same claims means offer *reuse* / *re-verify* (claims age) / *fresh* rather than re-spending the per-claim budget blind.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Check only the 2–3 most load-bearing claims, with real searches but fewer of them.
- **Output in chat only:** the **Read Me First** block this skill defines (the headline verdicts), then one line per checked claim with its verdict + best source. Unchecked claims are listed as unchecked — never silently dropped.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — top claims only; run again without `--quick` for the full claim-by-claim version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output files

Derive a `{topic}` slug from the subject: lowercase, hyphen-joined, punctuation stripped, max ~50 chars. Create a `factcheck/` directory and write exactly two files:

- **`factcheck/{topic}background.md`** — all four passes, as sections within this one document.
- **`factcheck/{topic}Dossier.md`** — the final verdict dossier.

If those files already exist from a prior run, suffix the topic with `-2` (then `-3`, etc.).

**Search budget (token discipline):** ~3 searches/fetches per claim, ~25 total default (~5 in `--quick`). Spend them where the stakes are — the load-bearing claims get the depth; trivia gets triage.

## Rules of credible verification (apply throughout)

- **Quote before you judge.** Every claim is captured **verbatim** (or as a tight faithful paraphrase marked as such) before any verdict. Checking a paraphrase you wrote is how strawmen get "refuted."
- **Independence is about origin, not outlet.** Two independent sources = two different *origins* of the information (e.g. a regulator filing and a first-hand account) — not two websites repeating the same wire story. When every source traces to one origin, say so: that's **one** source.
- **Primary beats secondary.** Chase the filing, the paper, the transcript, the dataset, the original post — not the article about it. Tier and date every source (Tier 1 primary / Tier 2 reputable secondary / Tier 3 restatement — a Tier 3 alone never carries a verdict).
- **Refutation needs the same rigor as confirmation.** 🔴 REFUTED requires solid contradicting evidence — not just "I couldn't confirm it" (that's ⚪ or 🟡).
- **Absence of evidence ≠ evidence of absence.** Log what you searched so "not found" is auditable.
- **Symmetry check (your own bias):** would you accept this quality of evidence if it pointed the other way? If not, keep digging or downgrade the verdict.
- **Label everything** `[cited]` (with URL + access date), `[recall]`, or `[unverified]`; never invent sources, quotes, or figures.
- **Verdicts attach to claims, not people.** The output judges assertions; it doesn't editorialize about who made them.

## The verdict grammar (use exactly these five)

- ✅ **CONFIRMED** — ≥2 independent sources agree; no credible contradiction found.
- 🟡 **PLAUSIBLE** — supported but under-sourced (one source, indirect evidence, or expert consensus without primary data). Often the honest ceiling.
- 🔴 **REFUTED** — credible evidence contradicts it; show the contradiction.
- 🔵 **MISLEADING** — the literal words survive checking, but the framing implies something false: cherry-picked window, dropped base rate, true-but-outdated, real quote out of context, technically-true subset sold as the whole. State *what's true*, *what's implied*, and *why the implication fails*.
- ⚪ **UNVERIFIABLE** — cannot be checked with available sources (private data, vague quantifier, prediction, matter of definition). Say *why* — the reason is often the finding: an unverifiable claim doing load-bearing work is a red flag on its own.

## The four passes — all written into `factcheck/{topic}background.md`

```markdown
# <Subject> — Factcheck Background
> Working document. All four passes. The verdicts live in {topic}Dossier.md.

## Pass 1 — Extract & triage claims
## Pass 2 — Verify (claim by claim)
## Pass 3 — Daisy-chains & framing
## Pass 4 — Adjudicate
```

### Pass 1 — Extract & triage claims
Pull out the claims **verbatim** and classify each: checkable fact / opinion (not checkable — excluded, listed as such) / prediction (not yet checkable — noted) / too vague to check (⚪ candidate; note what's missing). Then triage by load: which claims does the subject's whole point rest on? **Default cap: the ~10 most load-bearing claims** (user can ask for exhaustive). Excluded and deferred claims are listed, never silently dropped.

### Pass 2 — Verify (claim by claim)
For each claim in load order: search primary-first, record what you find *and what you searched* — supporting evidence, contradicting evidence, source tiers + dates. Note where the evidence is one origin echoed many times. Numbers get special care: check the unit, the year, the base, and whether the cited figure measures what the claim says it measures.

### Pass 3 — Daisy-chains & framing
Two sweeps across everything found:
- **Daisy-chain audit:** for claims resting on "many" sources, trace them back — how many independent origins are there really? Collapse echoes.
- **Framing audit:** for claims that survived literally, does the *presentation* mislead — cherry-picked timeframe, missing denominator, outdated truth, context-stripped quote? This is where 🔵 MISLEADING verdicts are earned, with the true/implied/why-it-fails triple drafted.

### Pass 4 — Adjudicate
Assign each claim its verdict per the grammar, with confidence (High/Med/Low) and the one strongest piece of evidence either way. Run the symmetry check on every 🔴 and every ✅ that took effort. Compute the honest headline: "of N load-bearing claims: X confirmed, Y plausible, Z refuted, W misleading, V unverifiable — and the subject's core point <stands / stands weakened / falls>."

## The dossier — `factcheck/{topic}Dossier.md`

Write this **after** the background doc. Self-contained. **Read Me First and the verdict table up top.**

```markdown
# <Subject> — Factcheck

## 📌 Read Me First
Plain-language, 3–5 bullets, skimmable in 20 seconds.
- **What was checked:** <the subject, one line — and how many claims>
- **The headline:** <X confirmed · Y plausible · Z refuted · W misleading · V unverifiable>
- **The core point:** <stands / stands weakened / falls — because …>
- **The most important finding:** <the single verdict that changes the reading most>

---

## Verdict Table
| # | Claim (short) | Verdict | Confidence | Best evidence |
|---|---------------|---------|------------|---------------|

## The Claims
One card per checked claim, in load-bearing order:

### <n>. "<claim, verbatim>"
- **Verdict:** <emoji + word> · confidence <H/M/L>
- **Evidence:** <what supports / contradicts, with tiers + dates> [cited: URL]
- **Independence:** <N truly independent origins — daisy-chain notes if any>
- **Nuance:** <for 🔵: what's true, what's implied, why the implication fails; for ⚪: why it can't be checked>

## Not Checked
<opinions, predictions, below-cap claims — listed so nothing is silently dropped>

## Search Log
<the queries run, so "not found" is auditable>

## Sources
<numbered, de-duplicated, real URLs with access dates and tiers>
```

### Example — what a good 🔵 MISLEADING card looks like
*(Illustrative.)*

> ### 3. "Our app was the #1 downloaded finance app."
> - **Verdict:** 🔵 MISLEADING · confidence High
> - **Evidence:** store-ranking archive confirms a #1 position in the "Finance — new releases" subcategory, in one country, for two days in March [cited, Tier 1 — archive link, accessed 2026-07-09].
> - **Independence:** 4 articles found, all tracing to the company's own press release — one origin.
> - **Nuance:** *True:* it hit #1 in a narrow subcategory briefly. *Implied:* sustained overall #1. *Why the implication fails:* the overall-chart peak was #47; the claim swaps a two-day subcategory spike for the category crown.

## Self-check before finishing
Before declaring done, verify the dossier and fix any miss:
- Every checked claim is quoted verbatim; every verdict uses the five-verdict grammar.
- Every ✅ has ≥2 *independent origins*; every 🔴 has real contradicting evidence, not mere absence.
- Every 🔵 states the true/implied/fails triple; every ⚪ states why it can't be checked.
- Daisy-chains were traced; no verdict rests on a lone Tier-3 echo.
- The search log exists; excluded claims are listed; nothing silently dropped.
- The symmetry check ran on the hard calls; no invented sources anywhere.

## Finishing up

Write `{topic}background.md` first (all four passes), then `{topic}Dossier.md`. Give the user a short chat summary: the headline count, whether the core point stands, the single most important verdict, and the paths to both files. Don't paste the files into chat. Offer to go exhaustive beyond the claim cap — or to chain onward: `/critic` if what needs attacking is the argument rather than the facts, `/researcher` if a refuted claim opens a real question, `/watch add` on the confirmed load-bearing claims if the answer has to stay true past today (verdicts have shelf lives).

## Notes on tone and rigor

- Division of labour: `/factcheck` judges **claims against sources**; `/critic` judges **arguments and reasoning**. A piece can be factually clean and logically broken — or the reverse. Chain them for both.
- Calm beats gotcha. The dossier should read like a lab report, not a takedown; the evidence does the talking.
- On genuinely contested factual territory, present the strongest evidence per side and verdict 🟡 with the disagreement named — don't manufacture false certainty either way.
- The claim cap is a feature: ten claims checked well beat forty checked thin. Say what was left unchecked.
