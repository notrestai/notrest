---
name: marketresearcher
description: Funnel-shaped market research — scope, two-way sizing (top-down + bottom-up, reconciled), competitor map with the graveyard, gap/whitespace verdicts, feasibility scoring, drafted entry ideas — landing finding records (--dossier keeps the card; --quick). Use on /marketresearcher or asks to size a market, map or analyze competitors, find gaps/whitespace or a niche, assess market entry, or validate a business/product idea. Research to inform a decision — never investment advice.
---

# Market Researcher

A staged, funnel-shaped workflow that takes a market or product idea and drives it from a broad landscape scan down to a defended shortlist of entry opportunities with drafted ideas. It deliberately *narrows*: each stage filters, so you end with the strongest few options. The reasoning runs through seven stages; the output is a handful of **validated finding records** in the archivist store — one per sizing or competitor conclusion, then one `kind=result` verdict on where to play. The stages are the working-out, the records are what survives.

This produces **research inputs for a decision, not financial or investment advice.** Never tell the user to invest, spend, or commit capital. Present feasibility and risk with confidence levels and let them decide. State plainly this is not a substitute for professional due diligence.

**Router shape:** `market-sizing`

## The prompt

The research target is everything the user passed when invoking the skill (a market, industry, product idea, or "should I build X" question). Use `$ARGUMENTS` if populated; otherwise the text after `/marketresearcher`. If the target is too vague to scope (e.g. just "fintech"), ask exactly one clarifying question — ideally about the buyer or the angle — then begin. Treat the original target as the fixed yardstick.

**Consult the store first.** Run one `index.py find "<target>"` before Stage 1 — it searches the findings store, the legacy index, and dossier bodies. On a hit, surface it (id or path, date, statement) and offer *reuse* / *extend* (this run, seeded with the prior records) / *fresh* — market data ages fast, so say the date out loud — never silently re-spend the search budget.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No records.** Write nothing to the store, and no files. Skip the "Setup & output" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not sourced into the store; run again without `--quick` for the recorded, verifiable version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output — the findings store

**No market-research folder by default. No two-file write.** This skill's output is **finding records** appended to the archivist store (`archive/findings.jsonl`, append-only, validated at the door): one per sizing or competitor conclusion as the funnel earns it, plus one `kind=result` verdict record at the end. The seven stages below still run in full — they are what earns a number; they just do not land as files.

The sink:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{…}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder.) It prints the assigned `F-<n>` on success and **exits 2 naming the rule** on rejection — an empty evidence list, or a `[cited]` url that is not a URL, does not enter the store. Fix the record, re-run; never hand-append to the JSONL.

**`--dossier` (kept, opt-in).** The rated Opportunity Space card — one per gap, carrying its "why isn't this filled?" answer — is the readable thing people circulate here, so the legacy two-file write survives behind a flag. With `--dossier`, *also* derive a `{topic}` slug (lowercase, hyphen-joined, punctuation stripped, max ~50 chars — "AI tools for dentists" → `ai-tools-for-dentists`), create `market-research/`, and write `market-research/{topic}background.md` (all seven stages as sections) and `market-research/{topic}Dossier.md` (the template below), suffixing the topic `-2`, `-3`, … if they already exist. The records are emitted either way; the files never replace them.

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

## The seven stages — the reasoning that earns the records

Run all stages in order, in full, as working prose in the session (under `--dossier`, also as sections of the background document). Keep the funnel disciplined: by Stage 5 you should be narrowing, not still expanding. Emit a record the moment a stage produces a conclusion — do not batch them at the end.

```
Stage 1 — Scope & framing         → (reasoning — the boundary, the ICP, the sizing formula)
Stage 2 — Landscape & sizing      → records: kind=finding per sizing conclusion (both methods, reconciled)
Stage 3 — Competitive landscape   → records: kind=finding per competitor/graveyard read
Stage 4 — Gaps & whitespace       → records: kind=finding per gap verdict (real / mirage / graveyard)
Stage 5 — Feasibility & scoring   → records: kind=backtrack for a gap cut here
Stage 6 — Shortlist deep-dive     → records: the survivors; corrections supersede earlier stages
Stage 7 — Synthesis               → record:  kind=result — where to play, with confidence
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

## The output — finding records

**One record per conclusion, plus one `kind=result` verdict.** A record is not a note: the `statement` must read alone in 1–3 sentences, carry its own honesty label on every evidence item, and survive being read a month from now without the stages beside it. Keep confidence, tier, and **the date of the figure** inside the statement — the store validates shape, not judgment, and a market number without its date is a lie with a timestamp.

- **A sizing conclusion:** `kind=finding`, `relation=toward` — both methods and the size of their gap in the statement; the bottom-up half rides as `[estimate]`, never `cited`.
- **A competitor / graveyard read, or a Stage-4 gap verdict:** `kind=finding`, `relation=toward` — the verdict word (real opening | mirage | graveyard) leads the statement, with the "why isn't this filled?" answer.
- **Two credible figures that cannot both be right:** `kind=conflict`, `relation=lateral` — both numbers with their origins, never averaged into a middle nobody published.
- **A gap cut at Stage 5, or an idea Stage 6's disconfirmation killed:** `kind=backtrack`, `relation=back` — a dead entry point is the most valuable thing this skill finds.
- **An earlier stage you corrected:** write the better record, then `index.py supersede F-<old> --by F-<new>` — the store is append-only; corrections are new lines.
- **The verdict, last:** `kind=result`, `relation=toward`, `links` naming the records it rests on.

### The snippet, filled

*(For "AI tools for independent dental practices". Note the two methods, the arithmetic as evidence, and the reserved `.example` host standing in for the analyst source you would actually cite.)*

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"marketresearcher-2026-07-25",
  "skill":"marketresearcher",
  "kind":"finding",
  "ask":"AI tools for independent dental practices — where is the entry point?",
  "statement":"SAM for admin AI in US sub-5-chair dental practices reconciles at roughly $1.2-1.4B/yr as of 2026-07: top-down $1.2B [cited, Tier 2, 2025 analyst] against bottom-up 135k practices x $700/mo x 12% adoption = $1.36B [estimate]. The methods agree within 1.2x — well inside the 10x red flag — so the range is usable; confidence medium, and adoption is the soft input.",
  "evidence":[{"type":"url","ref":"https://www.ada.org/resources/research/health-policy-institute","label":"cited"},
              {"type":"url","ref":"https://analyst.example/dental-practice-management-2025","label":"cited"},
              {"type":"command","ref":"python3 -c \"print(135000*700*12*0.12)\"","label":"estimate"}],
  "relation":"toward",
  "links":[]}'
```

Then the verdict record, linking what it rests on:

```bash
… add --root . --json '{"session":"marketresearcher-2026-07-25","skill":"marketresearcher","kind":"result",
  "ask":"AI tools for independent dental practices — where is the entry point?",
  "statement":"Where to play: insurance pre-auth automation for sub-5-chair practices — the one Stage-4 gap that survived as a real opening. The other two were a mirage (no willingness-to-pay evidence found in 9 queries) and a graveyard (two funded attempts, both pivoted upmarket). Confidence medium as of 2026-07; flips if a DSO incumbent ships a small-practice tier. Research to inform the decision, not advice to spend.",
  "evidence":[{"type":"url","ref":"https://www.ada.org/resources/research/health-policy-institute","label":"cited"},
              {"type":"path","ref":"market-research/ai-tools-for-dentists-search-log.md","label":"unverified"}],
  "relation":"toward","links":["F-41","F-42","F-43"]}'
```

Each `add` prints its `F-<n>`. A non-zero exit means the record was turned away with its rule named — fix it and re-run.

## The `--dossier` output — `market-research/{topic}Dossier.md`

Only under `--dossier`, and only after the background doc is complete. Self-contained — a reader absorbs the whole project from this file alone. Synthesize, don't concatenate. Keep all labels and confidence levels. **State Summary first, Opportunity Space second.**

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
Before declaring done, verify the records and fix any miss:
- **Records validated at the door (`add` exited 0)** — every id was printed by the script, nothing hand-appended.
- No invented market sizes, growth rates, funding, valuations, or shares — anything not found says "not found".
- Every quantitative claim has source + date + tier; no lone Tier-3 number carries a conclusion.
- Top-down and bottom-up sizing are both present and reconciled (or the >10× gap is flagged and explained).
- Every Stage-4 gap has a "why isn't this filled?" answer and a real / mirage / graveyard verdict.
- Each shortlisted opportunity carries a confidence level and its key risk; the framing is analysis, not advice.
- The not-advice framing survives into the `kind=result` statement (and the disclaimer is present in the `--dossier` file, when one was written).
- Cut gaps and killed ideas landed as `kind=backtrack`; a corrected earlier stage was `supersede`d, not left standing beside its replacement.

## Finishing up

Run the seven stages, emitting records as conclusions land, and write the `kind=result` verdict last (under `--dossier`, write `{topic}background.md` then `{topic}Dossier.md` after the records, never instead of them). Give the user a short chat summary: the recommended opportunity, its confidence level, and the record ids — plus `index.py track --status live` as the one command that shows the whole trail. Don't paste the records into chat. Offer to dig deeper on any single stage — or to chain onward: `/critic` to red-team the opportunity, `/refuter` to attack the load-bearing sizing records, `/stepbystep` to plan the entry.

## Notes on tone and rigor

- Favor primary sources (filings, regulator data, the company's own pages) over analyst summaries, and those over content-marketing blogs.
- Show sizing arithmetic; never present a bottom-up estimate as a cited fact.
- It's a valid, valuable outcome to conclude "no attractive entry point — the gaps are graveyards or mirages." Say so plainly rather than manufacturing an opportunity.
- If a stage produces little, say so plainly and write no record for it — padding the store is worse than a thin track.
