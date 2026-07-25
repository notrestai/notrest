---
name: researcher
description: Rigorous multi-pass research on any question — baseline, ≥5 alternatives, tiered real sources, comparison, disconfirmation — producing a background doc + decision dossier (or --quick for chat-only). Use on /researcher or natural asks to research, deeply investigate, compare alternatives, find best practices, or "find the best X for my situation" — any open-ended question that deserves evidence over vibes. Not for simple lookups you can answer directly.
---

# Researcher

A staged research workflow that takes a single prompt and drives it from a first-cut answer to a defended recommendation. The reasoning runs through five passes, but the output is just **two files**: a consolidated background document holding all the pass work, and a final dossier holding the decision.

## The prompt

The research question is everything the user passed when invoking the skill. Use `$ARGUMENTS` if it is populated; otherwise use the text the user typed after `/researcher`. If the prompt is empty or one ambiguous word, ask exactly one clarifying question before starting — otherwise begin immediately. Treat the original prompt as the fixed yardstick: every later pass is judged against *this* question, not whatever interesting tangents appear along the way.

**Consult the index first (if present).** If the repo carries an `oracle-index.md` — or the **archivist** skill is installed and prior ORACLE output folders exist — run one `find` on the question's topic before Pass 1. On a hit, surface it (path, date, headline) and offer *reuse* / *extend* (this run, seeded with the old dossier) / *fresh* — never silently re-spend the search budget on a question this project already answered.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not fully sourced or saved; run again without `--quick` for the verifiable two-file version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output files

Derive a `{topic}` slug from the prompt: lowercase, words joined by hyphens, stripped of punctuation, max ~50 chars (e.g. "best CRM for early-stage startups" → `best-crm-for-early-stage-startups`). Create a `research/` directory in the current working directory and write exactly two files into it:

- **`research/{topic}background.md`** — all five passes, as sections within this one document.
- **`research/{topic}Dossier.md`** — the final consolidated decision document.

If those files already exist from a prior run, suffix the topic with `-2` (then `-3`, etc.) so you never overwrite previous work.

This workflow depends on web search and fetch tools. If they're unavailable, tell the user the research will be limited to your own knowledge (clearly labeled as such) and ask whether to proceed.

**Search budget (token discipline):** default to ~20 searches/fetches across the whole run (~4 in `--quick`), spent where they matter most — Passes 3 and 5 usually deserve the largest share. Exceed the budget only when a load-bearing claim is still unverified or the user asked for exhaustive depth, and say so when you do.

## Honesty rules (apply throughout)

These are non-negotiable because a research tool that fabricates is worse than no tool.

- **Never invent sources.** No made-up URLs, paper titles, author names, dates, or statistics. If you can't find support for a claim, write "unverified" and move on.
- **Label every factual claim** as one of: `[cited]` (backed by a source you actually retrieved this run), `[recall]` (from your own training knowledge, not freshly verified), `[estimate]` (you computed it — show the math and assumptions), or `[unverified]` (you believe it but couldn't confirm).
- **Surface disagreement.** When sources conflict, show the conflict explicitly — name both positions and who holds each. Do not average them into a smooth consensus that no source actually states.
- **Give confidence levels** (high / medium / low) on conclusions, and state what new evidence would change them.
- **Cite real links.** Every `[cited]` claim must carry the URL you pulled it from.
- **Tier your sources, and prefer primary from Pass 1 on.** Tier 1 = primary (peer-reviewed papers, official docs/specs, standards bodies, government/regulator data, the maker's own documentation). Tier 2 = reputable secondary (named analysts, established outlets, recognized practitioners). Tier 3 = SEO/content-marketing blogs repeating others — treat as a *lead*, chase the primary it cites, and never let a Tier-3 claim stand alone. Note each source's tier and date inline; when a Tier-1 source is reachable, don't settle for a Tier-3 restatement of it.

## The five passes — all written into `research/{topic}background.md`

Run all five passes in order and record each as a section of the single background document, using this top-level skeleton:

```markdown
# <Prompt, as a title> — Research Background
> Working document. All five passes. The decision lives in {topic}Dossier.md.

## Pass 1 — Baseline
## Pass 2 — Alternatives
## Pass 3 — Evidence
## Pass 4 — Comparison & critique
## Pass 5 — Deep dive & disconfirmation
```

### Pass 1 — Baseline
Run an initial search and answer the prompt directly, the way a knowledgeable person would on first pass. Capture the mainstream/default answer and the 3–6 most relevant sources.
- **Prompt:** the original prompt, verbatim.
- **Working answer:** the straightforward answer, 1–3 paragraphs.
- **Sources:** title — url — one line on what it contributes `[cited]`.
- **Open questions carried forward.**

### Pass 2 — Alternatives (≥5)
Widen the scope. Find **at least 5 genuinely distinct alternatives** — different approaches, tools, or schools of thought, not five flavors of one. For each: what it is (1–2 lines), best for (when it wins), and at least one source. If you genuinely can't find 5, say so and explain why.

### Pass 3 — Evidence & best practices
Search specifically for **recent** research, studies, benchmarks, and best-practice guidance (prefer the last ~2 years; note dates). Then:
- **Recent findings** — finding — source with date `[label]`.
- **Evidence mapped to alternatives** — for each Pass-2 option, what the evidence says + confidence.
- **Conflicts in the literature** — position 1 (who) vs position 2 (who).
- **Gaps** — where evidence is missing or weak.

### Pass 4 — Comparison & critique
Build a comparison across the alternatives on the dimensions that matter *for the original prompt*. Steelman each option, then state its real weaknesses. Cross-reference Passes 1–3 and call out where your own earlier passes were wrong or overconfident. Then decide:
- **Comparison table:** option | strengths | weaknesses | fit for the prompt.
- **Cross-references / corrections:** where earlier passes need revising.
- **Decision:** best fit; why it wins for *this* prompt; confidence + what would change it; honorable mention / when to pick something else.

### Pass 5 — Deep dive & disconfirmation
Go deep on the chosen answer: implementation detail, edge cases, failure modes, and **actively try to find reasons the Pass 4 pick is wrong**. If you find strong disconfirming evidence, revise the decision and say so explicitly. Record what you tried to use to kill the pick and what held up, plus any residual uncertainty.

## The dossier — `research/{topic}Dossier.md`

Write this **after** the background doc is complete, so it reflects any revision the Pass 5 deep dive forced. This is the self-contained decision document — a reader should absorb the whole conclusion from this file alone. Synthesize; don't paste the passes in. Keep labels and confidence levels intact. **State Summary first, Solution Space second.**

```markdown
# <Prompt, as a title> — Dossier

## 📌 Read Me First
Plain-language, no jargon. 3–5 bullets a busy person can skim in 20 seconds.
- **What you asked:** <the question in one short line>
- **What I found:** <the answer in one plain sentence — what to do>
- **How sure I am:** <high / medium / low, in plain words>
- **The catch:** <the single biggest caveat, if any>

**How this research is laid out — two files:**
- **`{topic}background.md`** — all the working-out: the passes (baseline → alternatives → evidence → comparison → deep dive). Read this if you want to see *how* I got here.
- **`{topic}Dossier.md`** (this file) — the answer. Sections below: **State Summary** (the gist), **Solution Space** (every option, rated), **Decision & Reasoning** (the pick and why), **Sources**.

---

## State Summary
- **Question:** <the original prompt, verbatim>
- **Bottom line:** <1–3 sentences: the recommendation + confidence level>
- **Key findings at a glance:** <3–6 bullets, each with its [label] + confidence>
- **Open tensions:** <unresolved conflicts or gaps, 1–2 bullets — don't hide these>

## Solution Space
One compact card per option considered (every alternative from Pass 2). Lead each with a verdict tag: ✅ Recommended / 🟡 Conditional / 🔴 Not advised.

### <Option> — <one-line verdict> [✅ / 🟡 / 🔴]
- What it is: <1–2 lines>
- Evidence: <what supports or undercuts it, with [label] + confidence>
- Wins when: <the conditions under which this is the right pick>
- Caveats / why it lost: <honest weaknesses>

## Decision & Reasoning
- **Chosen:** <option(s)>
- **Why, traced to evidence:** <reasoning that points back to specific findings, not vibes>
- **Decision trail:** <how the conclusion evolved across passes — note where earlier passes were corrected>
- **What would change this:** <the evidence that would flip the call>

## Sources
<numbered, de-duplicated, real URLs actually used>
```

### Example — what a good Solution Space card looks like
*(Illustrative, for the question "best Python framework for a small REST API". Note how it leans on a primary source and labels tiers.)*

> ### FastAPI — Recommended for new async REST APIs [✅]
> - What it is: modern ASGI framework with built-in request validation and auto-generated OpenAPI docs.
> - Evidence: official docs confirm native async support and Pydantic-based validation [cited, Tier 1 — fastapi.tiangolo.com, 2025]; broad recent adoption in ecosystem surveys [cited, Tier 2]. Confidence: high.
> - Wins when: a new service with async I/O where you want typed request/response and free API docs.
> - Caveats / why it might lose: smaller batteries-included ecosystem than Django; overkill for a server-rendered app.

## Self-check before finishing
Before declaring done, verify the dossier against this list and fix any miss:
- Every factual claim carries a label; every `[cited]` has a real URL, a date where it matters, and a tier.
- No invented sources, figures, or quotes; nothing presented more confidently than the evidence supports.
- Each Pass-2 alternative appears in the Solution Space with a verdict.
- The recommendation states a confidence level and what would change it.
- Source conflicts are shown, not averaged away; no lone Tier-3 claim carries a key conclusion.
- The Read Me First is genuinely plain-language and skimmable in ~20 seconds.

## Finishing up

Write `{topic}background.md` first (all five passes), then `{topic}Dossier.md`. Give the user a short chat summary: the recommendation, its confidence level, and the paths to both files — point them to the dossier as the main read. Don't paste the files into chat. Offer to dig deeper on any single pass — or to run `/critic` on the dossier to red-team the recommendation, or `/factcheck` to verify its load-bearing claims, before acting on it.

## Notes on tone and rigor

- Prefer paraphrase over quotation; keep any quote short and attributed.
- Quality of sources matters: favor primary sources, peer-reviewed work, official docs, and reputable outlets over content farms and SEO filler.
- It's fine — good, even — to conclude "there is no single best answer; it depends on X" when that's the truth. Say so plainly rather than forcing a winner.
- If a pass produces nothing useful, say so honestly in the background doc instead of padding it.
