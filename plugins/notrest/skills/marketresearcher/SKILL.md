---
name: marketresearcher
description: Funnel-shaped market research — scope, two-way sizing (top-down + bottom-up, reconciled), competitor map with the graveyard, gap/whitespace verdicts, feasibility scoring, drafted entry ideas — producing a background doc + opportunity dossier (or --quick). Use on /marketresearcher or asks to size a market, map or analyze competitors, find gaps/whitespace or a niche, assess market entry, or validate a business/product idea. Research to inform a decision — never investment advice.
---

# Market Researcher

A staged, funnel-shaped workflow that takes a market or product idea and drives it from a broad landscape scan down to a defended shortlist of entry opportunities with drafted ideas. It deliberately *narrows*: each stage filters, so you end with the strongest few options. The reasoning runs through seven stages, but the output is just **two files**: a consolidated background document holding all stage work, and a final opportunity dossier.

This produces **research inputs for a decision, not financial or investment advice.** Never tell the user to invest, spend, or commit capital. Present feasibility and risk with confidence levels and let them decide. State plainly this is not a substitute for professional due diligence.

## The prompt

The research target is everything the user passed when invoking the skill (a market, industry, product idea, or "should I build X" question). Use `$ARGUMENTS` if populated; otherwise the text after `/marketresearcher`. If the target is too vague to scope (e.g. just "fintech"), ask exactly one clarifying question — ideally about the buyer or the angle — then begin. Treat the original target as the fixed yardstick.

**Consult the index first (if present).** If the repo carries an `oracle-index.md` — or the **archivist** skill is installed and prior ORACLE output folders exist — run one `find` on the target before Stage 1. On a hit, surface it (path, date, headline) and offer *reuse* / *extend* / *fresh* — market data ages fast, so say the date out loud — never silently re-spend the search budget.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not fully sourced or saved; run again without `--quick` for the verifiable two-file version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output files

Derive a `{topic}` slug from the prompt: lowercase, hyphen-joined, punctuation stripped, max ~50 chars (e.g. "AI tools for dentists" → `ai-tools-for-dentists`). Create a `market-research/` directory and write exactly two files:

- **`market-research/{topic}background.md`** — all seven stages, as sections within this one document.
- **`market-research/{topic}Dossier.md`** — the final consolidated opportunity document.

If those files already exist from a prior run, suffix the topic with `-2` (then `-3`, etc.) so you never overwrite previous work.

This workflow depends on web search and fetch tools. If they're unavailable, say so plainly — market research without live sources is nearly worthless because the data goes stale fast — and ask whether to proceed on labeled recall only.

**Search budget (token discipline):** default to ~25 searches/fetches for the whole funnel (~5 in `--quick`) — sizing and the competitor map deserve the largest share. Exceed it only for a load-bearing number still unpinned, and say so when you do.

## Honesty rules (apply throughout — stricter than general research)

Market data is the most fabrication-prone category there is. A market report that invents numbers is worse than none because someone may risk real money on it.

- **Never invent a market size, growth rate, CAGR, revenue figure, funding amount, valuation, headcount, or market share.** If you can't find it, say "not found" — do not estimate it into existence and present it as fact.
- **Every quantitative claim carries source + date + tier.** Tier 1 = primary (filings/10-Ks, government/regulator data, audited figures, a company's own pricing page). Tier 2 = reputable analyst or press (named firm, major outlet). Tier 3 = secondary blog citing someone else — treat as a *lead*, chase the primary; never let a Tier 3 number stand alone.
- **Label every claim:** `[cited]` (retrieved this run, with URL + date), `[estimate]` (you computed it — show the math + assumptions), `[recall]` (training knowledge, unverified), or `[unverified]`. A bottom-up size you build is `[estimate]`, never `[cited]`.
- **Watch for daisy-chains.** When every source repeats one figure, it usually traces to a single (often paywalled) origin. Say so.
- **Absence of evidence is not evidence of absence.** "I found no competitor" is a claim about *your search*, not the market. Log what you searched.
- **Competitor facts change fast** (pricing, funding, status) — date them and flag staleness.
- **Surface conflicts** rather than averaging them into false consensus.
- **Give confidence levels** (high/med/low) on every conclusion and say what would change them.

## The seven stages — all written into `market-research/{topic}background.md`

Run all stages in order as sections of the single background document. Keep the funnel disciplined: by Stage 5 you should be narrowing, not still expanding.

```markdown
# <Market / idea> — Market Research Background
> Working document. All seven stages. The decision lives in {topic}Dossier.md.

## Stage 1 — Scope & framing
## Stage 2 — Landscape & sizing
## Stage 3 — Competitive landscape
## Stage 4 — Gaps & whitespace
## Stage 5 — Feasibility & scoring
## Stage 6 — Shortlist deep-dive & ideas
## Stage 7 — (synthesis happens in the dossier)
```

### Stage 1 — Scope & framing
Before searching, define the playing field: market boundary (what's in and explicitly out), buyer/ICP (who pays, who uses, the job they're hiring it for), geography & horizon, the sizing approach (top-down sources to seek + the bottom-up formula to build), and the 3–6 decision-driving questions this research must answer.

### Stage 2 — Landscape & sizing
Search for the market's shape and size. Produce TAM/SAM/SOM **two ways** — top-down from cited reports *and* bottom-up from unit economics (units × price × adoption) — and reconcile the gap (which to trust + confidence). **Sanity check:** if the two methods differ by more than ~10×, treat that as a red flag — usually a definitional mismatch (different segment, geography, or year) or a bad source — and investigate before reporting either figure. Capture growth/trends, demand signals (evidence real demand exists, not just analyst optimism), and structural dynamics (regulation, distribution, platform shifts).

### Stage 3 — Competitive landscape
Map who's actually in the market, segmented (incumbents, challengers, adjacent, substitutes/DIY). For each: offering, pricing, positioning, and traction/funding where findable and dated. Then:
- **Substitutes & "do nothing":** how the buyer solves this today without any of them.
- **The graveyard:** who tried and failed/pivoted, and why — often the most valuable signal.
- **Concentration & moats:** fragmented or locked up? what defends incumbents?
- **Optional lens — Porter's Five Forces:** where it adds signal, read the market through rivalry, threat of new entrants, threat of substitutes, buyer power, and supplier power, and let it sharpen the moats/concentration call. Use it only when it clarifies; don't force the frame.
- **Search log:** the queries you ran, so "no competitor found" is auditable.

### Stage 4 — Gaps & whitespace
Identify unmet needs, underserved segments, jobs-to-be-done no one addresses well, and friction points. For **every** candidate gap, run the discipline check: *why isn't this already filled?* Give a verdict per gap — real opening | mirage (no real demand) | graveyard (tried and failed) — with confidence and the evidence behind it. **Optional lens — Jobs-to-be-Done:** frame each gap as a concrete job the buyer is trying to get done and currently can't, which keeps gaps anchored in real demand rather than feature wishlists.

### Stage 5 — Feasibility & scoring
Score each *real* gap on two axes and narrow to the final 2–3. Show the components, never a bare number. Frame entry feasibility as analysis, not a recommendation to spend.
- **Attractiveness:** market size/growth, pain intensity, willingness to pay, durability.
- **Feasibility:** barriers to entry, capital intensity, time-to-market, competitive intensity, regulatory load, distribution access, operator/founder fit if known.
Record the scoring table, barriers-to-entry detail for survivors, the shortlist (with why each advances + confidence), and what was cut and why.

### Stage 6 — Shortlist deep-dive & drafted ideas
Go deep on the survivors. For each, search for implementation detail, edge cases, and **disconfirming evidence — actively try to kill it**; if you find a fatal flaw, drop or demote it and say so. Then draft a concrete opportunity: the idea (2–3 sentences), wedge & positioning (the beachhead, differentiated vs Stage 3 players), rough GTM (how the Stage 1 ICP is reached), a unit-economics sketch if estimable `[estimate]`, the disconfirming evidence you sought, key risks & kill-criteria, and a confidence level. **Optional lens — SWOT:** a quick strengths/weaknesses/opportunities/threats pass on each shortlisted opportunity can surface blind spots; include it only where it earns its place.

## The dossier — `market-research/{topic}Dossier.md`

Write this **after** the background doc is complete. Self-contained — a reader absorbs the whole project from this file alone. Synthesize, don't concatenate. Keep all labels and confidence levels. **State Summary first, Opportunity Space second.**

```markdown
# <Market / idea> — Opportunity Dossier

## 📌 Read Me First
Plain-language, no jargon. 3–5 bullets a busy person can skim in 20 seconds.
- **What you asked:** <the market/idea in one short line>
- **What I found:** <the headline in one plain sentence — where the opportunity is, or that there isn't one>
- **How sure I am:** <high / medium / low, in plain words>
- **The catch:** <the single biggest unknown or risk>
- **Reminder:** this is research to help you decide, not advice to spend money.

**How this research is laid out — two files:**
- **`{topic}background.md`** — all the working-out: the stages (scope → sizing → competitors → gaps → feasibility → shortlist). Read this if you want to see *how* I got here.
- **`{topic}Dossier.md`** (this file) — the answer. Sections below: **State Summary** (the gist), **Opportunity Space** (every gap, rated), **Decision & Reasoning** (where to play and why), **Sources**, **Disclaimer**.

---

## State Summary
- **Target:** <verbatim prompt>
- **Bottom line:** <2–3 sentences: recommended opportunity/opportunities + confidence, framed as analysis not advice>
- **Market at a glance:** <size (both methods, labeled), growth, key dynamic — each with [label]>
- **Competitive reality:** <fragmented/locked, key players, graveyard lesson>
- **Open tensions / biggest unknowns:** <what's unresolved — don't hide it>

## Opportunity Space
One card per gap considered (from Stage 4), with a verdict tag: ✅ Recommended / 🟡 Conditional / 🔴 Not advised.

### <Gap/opportunity> — <one-line verdict> [✅ / 🟡 / 🔴]
- The opening: <what it is>
- Why it's real (or not): <evidence + the "why unfilled" answer> [label]
- Attractiveness × feasibility: <the scoring logic in brief>
- If pursued: <wedge, positioning, key risk>

## Decision & Reasoning
- **Where to play:** <the shortlisted pick(s)>
- **Why, traced to evidence:** <reasoning pointing back to specific findings>
- **Decision trail:** <how it narrowed across stages; where earlier stages were corrected>
- **What would change this:** <the evidence that would flip it>

## Sources
<numbered, de-duplicated, real URLs with access dates and tier>

## Disclaimer
This is structured research to inform your own judgment, not financial, investment, or legal advice. Verify critical figures against primary sources before committing resources.
```

### Example — what a good Opportunity Space card looks like
*(Illustrative, for "AI tools for independent dental practices". Note the labels, the "absence ≠ proof" discipline, and the tier-chasing.)*

> ### Automated insurance pre-auth for small practices — Conditional [🟡]
> - The opening: solo and 2–3-dentist practices burn hours on insurance pre-authorizations; existing tools target large DSOs.
> - Why it's real (or not): practice-management forums repeatedly cite pre-auth as a top admin burden [cited, Tier 3 — chase the primary]; no reviewed competitor targets sub-5-chair practices [from search log — absence of evidence, not proof of a gap]. Why unfilled: small-practice willingness-to-pay is unproven. Confidence: medium.
> - Attractiveness × feasibility: high recurring pain, but fragmented buyers and slow sales cycles lower feasibility.
> - If pursued: wedge on the single most painful payer first; key risk is integration with legacy practice-management software.

## Self-check before finishing
Before declaring done, verify the dossier and fix any miss:
- No invented market sizes, growth rates, funding, valuations, or shares — anything not found says "not found".
- Every quantitative claim has source + date + tier; no lone Tier-3 number carries a conclusion.
- Top-down and bottom-up sizing are both present and reconciled (or the >10× gap is flagged and explained).
- Every Stage-4 gap has a "why isn't this filled?" answer and a real / mirage / graveyard verdict.
- Each shortlisted opportunity carries a confidence level and its key risk; the framing is analysis, not advice.
- The disclaimer is present.

## Finishing up

Write `{topic}background.md` first (all seven stages), then `{topic}Dossier.md`. Give the user a short chat summary: the recommended opportunity, its confidence level, and the paths to both files — point to the dossier as the main read. Don't paste the files into chat. Offer to dig deeper on any single stage — or to chain onward: `/critic` to red-team the opportunity, `/stepbystep` to plan the entry.

## Notes on tone and rigor

- Favor primary sources (filings, regulator data, the company's own pages) over analyst summaries, and those over content-marketing blogs.
- Show sizing arithmetic; never present a bottom-up estimate as a cited fact.
- It's a valid, valuable outcome to conclude "no attractive entry point — the gaps are graveyards or mirages." Say so plainly rather than manufacturing an opportunity.
- If a stage produces little, write that honestly instead of padding it.
