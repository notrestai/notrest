---
name: researcher
description: "Rigorous multi-pass research on any question — baseline, ≥5 alternatives, tiered real sources, comparison, disconfirmation — landing validated FINDING RECORDS in the archivist store (or --quick for chat-only). Use on /researcher or natural asks to research, deeply investigate, compare alternatives, find best practices, or \"find the best X for my situation\" — any open-ended question that deserves evidence over vibes. Not for simple lookups you can answer directly."
---

# Researcher

A staged research workflow that takes a single prompt and drives it from a first-cut answer to a defended recommendation. The reasoning runs through five passes; the output is a handful of **validated finding records** in the archivist store — the passes are the working-out, the records are what survives.

**Router shape:** `research` — the UserPromptSubmit router (`hooks/router.sh`) nudges a prompt here when it looks like *"research …"*, *"find sources"*, *"look into"*, or *"deep dive"*. A prior-art phrasing (*"what do we already know?"*) outranks it and lands on `/archivist` instead; taking the nudge or deliberately skipping it is the user's call, silently doing this job by hand is the violation.

## The prompt

The research question is everything the user passed when invoking the skill. Use `$ARGUMENTS` if it is populated; otherwise use the text the user typed after `/researcher`. If the prompt is empty or one ambiguous word, ask exactly one clarifying question before starting — otherwise begin immediately. Treat the original prompt as the fixed yardstick: every later pass is judged against *this* question, not whatever interesting tangents appear along the way.

**Consult the store first.** Run one `index.py find "<topic>"` before Pass 1 — it searches the findings store, the legacy index, and dossier bodies. On a hit, surface it (id or path, date, statement) and offer *reuse* / *extend* (this run, seeded with the prior records) / *fresh* — never silently re-spend the search budget on a question this project already answered.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No records.** Write nothing to the store. Skip the "Setup & output" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass depth.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not sourced into the store; run again without `--quick` for the recorded, verifiable version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output — the findings store

**No dossier folder. No two-file write.** This skill's output is **finding records** appended to the archivist store (`archive/findings.jsonl`, append-only, validated at the door). One record per key result as you earn it, plus one `kind=result` summary record at the end. The prose passes below still run in full — they are what earns a statement; they just do not land as files.

The sink:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{…}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder.) It prints the assigned `F-<n>` on success and **exits 2 naming the rule** on rejection — an unlabeled claim, an empty evidence list, or a `[cited]` url that is not a URL does not enter the store. Fix the record, re-run; never hand-append to the JSONL.

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

## The five passes — the reasoning that earns the records

Run all five passes in order, in full, as working prose in the session. Depth is not optional: a statement worth storing is one a pass argued for. Emit a record the moment a pass produces a key result — do not batch them at the end.

```
Pass 1 — Baseline                    → records: the mainstream answer
Pass 2 — Alternatives                → records: each genuinely distinct option
Pass 3 — Evidence & best practices   → records: findings + any kind=conflict
Pass 4 — Comparison & critique       → records: corrections (supersede what Pass 1-3 got wrong)
Pass 5 — Deep dive & disconfirmation → records: the survivor, then one kind=result summary
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

## The output — finding records

**One record per key result, plus one `kind=result` summary.** A record is not a note: the `statement` must read alone in 1–3 sentences, carry its own honesty label on every evidence item, and survive being read a month from now without the passes beside it. Keep confidence and tier *inside the statement* — the store validates shape, not judgment.

- **Per key result** (a Pass-2 alternative that earned its place, a Pass-3 finding, the Pass-4/5 survivor): `kind=finding`, `relation=toward`.
- **A source conflict Pass 3 surfaced:** `kind=conflict`, `relation=lateral` — both positions in the statement, never averaged.
- **An earlier pass you corrected:** write the better record, then `index.py supersede F-<old> --by F-<new>` — the store is append-only; corrections are new lines.
- **A route you abandoned:** `kind=backtrack`, `relation=back` — dead ends are findings.
- **The recommendation, last:** `kind=result`, `relation=toward`, `links` naming the records it rests on.

### The snippet, filled

*(For the question "best Python framework for a small REST API".)*

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"researcher-2026-07-25",
  "skill":"researcher",
  "kind":"finding",
  "ask":"best Python framework for a small REST API",
  "statement":"FastAPI ships native async plus Pydantic request validation and auto-generated OpenAPI docs — the official docs confirm both. Tier 1 source, 2025; confidence high for new async services, lower for server-rendered apps.",
  "evidence":[{"type":"url","ref":"https://fastapi.tiangolo.com/features/","label":"cited"},
              {"type":"url","ref":"https://survey.stackoverflow.co/2025/","label":"cited"}],
  "relation":"toward",
  "links":[]}'
```

Then the summary record, linking what it rests on:

```bash
… add --root . --json '{"session":"researcher-2026-07-25","skill":"researcher","kind":"result",
  "ask":"best Python framework for a small REST API",
  "statement":"Recommend FastAPI for a new async REST API; Flask remains the pick for a small sync service with an existing extension stack. Confidence high — flips if the team needs Django-level batteries included.",
  "evidence":[{"type":"url","ref":"https://fastapi.tiangolo.com/features/","label":"cited"},
              {"type":"command","ref":"pip index versions fastapi","label":"estimate"}],
  "relation":"toward","links":["F-12","F-13","F-14"]}'
```

Each `add` prints its `F-<n>`. A non-zero exit means the record was turned away with its rule named — fix it and re-run.

## Self-check before finishing
Before declaring done, verify the records and fix any miss:
- **Records validated at the door (`add` exited 0)** — every id was printed by the script, nothing hand-appended.
- Every factual claim carries a label; every `[cited]` has a real URL, a date where it matters, and a tier.
- No invented sources, figures, or quotes; nothing presented more confidently than the evidence supports.
- Each Pass-2 alternative that survived has a record; abandoned ones landed as `backtrack`.
- The `kind=result` summary states a confidence level and what would change it, and links its supporting ids.
- Source conflicts landed as `kind=conflict`, shown not averaged; no lone Tier-3 claim carries a key conclusion.

## Finishing up

Run the five passes, emitting records as they land, and write the `kind=result` summary last. Give the user a short chat summary: the recommendation, its confidence level, and the record ids — plus `index.py track --status live` as the one command that shows the whole trail. Don't paste the records into chat. Offer to dig deeper on any single pass — or to run `/critic` to red-team the recommendation, `/refuter` to attack the load-bearing records, or `/factcheck` to verify their claims, before acting on it.

## Notes on tone and rigor

- Prefer paraphrase over quotation; keep any quote short and attributed.
- Quality of sources matters: favor primary sources, peer-reviewed work, official docs, and reputable outlets over content farms and SEO filler.
- It's fine — good, even — to conclude "there is no single best answer; it depends on X" when that's the truth. Say so plainly rather than forcing a winner.
- If a pass produces nothing useful, say so plainly and write no record for it — padding the store is worse than a thin track.
