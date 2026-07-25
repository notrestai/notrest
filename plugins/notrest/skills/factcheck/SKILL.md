---
name: factcheck
description: "Verify claims against real sources — extract the load-bearing claims from a statement, document, or answer, hunt primary sources (two independent ones for CONFIRMED; daisy-chains detected and collapsed), and deliver claim-by-claim verdicts ✅ CONFIRMED / 🟡 PLAUSIBLE / 🔴 REFUTED / 🔵 MISLEADING / ⚪ UNVERIFIABLE with dated citations — landing one validated FINDING RECORD per claim in the archivist store (or --quick for the top claims in chat). Use on /factcheck or \"is this true\", \"fact-check / verify / double-check this\", \"did X really say/do that\"."
---

# Factcheck

Takes any claim-bearing thing — a statement, an article, a forwarded message, a report, or an AI answer (including this suite's own records) — and verifies what it actually asserts: extract the claims that carry the weight, chase each to real sources, detect when ten citations are really one origin wearing costumes, and return verdicts a reader can act on. The reasoning runs through four passes; the output is **one validated finding record per checked claim**, verdict first in the statement.

The special power of this skill is the **🔵 MISLEADING** verdict: the claim that's technically true but framed to make you believe something false. Pure true/false checkers miss it; it's where most real-world deception lives.

## The prompt & subject

The subject is what the user passed — pasted text, an attached document, a URL to fetch, or "the answer you just gave me." Use `$ARGUMENTS` if populated; otherwise the text after `/factcheck`. If the subject document isn't in context, read/fetch it first. If it's genuinely unclear what to check, ask exactly one clarifying question, then begin.

Web search/fetch is this skill's engine. If those tools are unavailable, say so plainly — a fact-check without live sources is just an opinion with a rubric — and offer only clearly-labeled `[recall]` assessments.

**Consult the store first.** Run one `index.py find "<subject>"` before Pass 1: prior records on the same claims mean offer *reuse* / *re-verify* (claims age) / *fresh* rather than re-spending the per-claim budget blind. A record this run REFUTES gets flipped, not shadowed — `index.py refute F-<id> --evidence <url>`.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No records.** Write nothing to the store. Skip the "Setup & output" step entirely.
- **Reason, compressed.** Check only the 2–3 most load-bearing claims, with real searches but fewer of them.
- **Output in chat only:** the **Read Me First** block this skill defines (the headline verdicts), then one line per checked claim with its verdict + best source. Unchecked claims are listed as unchecked — never silently dropped.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — top claims only, not recorded; run again without `--quick` for the full claim-by-claim version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output — the findings store

**No factcheck folder. No two-file write.** This skill's output is **one finding record per checked claim** appended to the archivist store (`archive/findings.jsonl`, append-only, validated at the door), plus one `kind=result` headline record. The four passes below still run in full — they are what earns a verdict; they just do not land as files.

The sink:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{…}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder.) It prints the assigned `F-<n>` on success and **exits 2 naming the rule** on rejection — a verdict with no evidence, or a `[cited]` url that is not a URL, does not enter the store. That door is this skill's own rule made mechanical. Fix the record, re-run; never hand-append to the JSONL.

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

## The four passes — the reasoning that earns the verdicts

Run all four in order, in full, as working prose in the session. A verdict is only as good as the pass behind it; the record is the receipt, not the work.

```
Pass 1 — Extract & triage claims  → (reasoning — claims quoted verbatim)
Pass 2 — Verify (claim by claim)  → records: one kind=finding per claim, verdict first
Pass 3 — Daisy-chains & framing   → records: kind=conflict where origins fight; 🔵 nuance
Pass 4 — Adjudicate               → record:  kind=result, the headline count
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

## The output — one record per claim

**One `kind=finding` record per checked claim, the verdict first in the statement**, then the claim verbatim, then what carries it: independence count, and for 🔵 the true/implied/why-it-fails triple, for ⚪ why it cannot be checked. **The label on each evidence item is per-source, not per-claim** — the two independent origins that make a ✅ are two `[cited]` items; the thing you believe but could not confirm rides as `[unverified]` and never gets promoted by proximity to a good source.

- **Every checked claim:** `kind=finding`, `relation=toward`.
- **A claim whose sources disagree at origin:** `kind=conflict`, `relation=lateral` — both positions named.
- **The headline, last:** `kind=result`, the X/Y/Z/W/V count and whether the core point stands, `links` naming every claim record.
- **A record in the store this run refutes:** `index.py refute F-<id> --evidence <url>` — a refutation that leaves the old record live is not a refutation.

### The snippet, filled

*(For the 🔵 MISLEADING example: "Our app was the #1 downloaded finance app.")*

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"factcheck-2026-07-25",
  "skill":"factcheck",
  "kind":"finding",
  "ask":"is the launch post accurate?",
  "statement":"🔵 MISLEADING (confidence High) — \"Our app was the #1 downloaded finance app.\" TRUE: it hit #1 in the Finance new-releases subcategory, one country, two days in March. IMPLIED: a sustained overall #1. WHY IT FAILS: the overall-chart peak was #47. Independence: 4 articles, all tracing to the company press release — one origin.",
  "evidence":[{"type":"url","ref":"https://web.archive.org/web/2026/appstore-rankings","label":"cited"},
              {"type":"url","ref":"https://company.example/press/launch","label":"cited"},
              {"type":"path","ref":"inbox/launch-post.md","label":"cited"},
              {"type":"path","ref":"notes/overall-chart-peak.md","label":"unverified"}],
  "relation":"toward",
  "links":[]}'
```

Then the headline record, linking every claim it counts:

```bash
… add --root . --json '{"session":"factcheck-2026-07-25","skill":"factcheck","kind":"result",
  "ask":"is the launch post accurate?",
  "statement":"Of 6 load-bearing claims: 2 CONFIRMED, 1 PLAUSIBLE, 1 REFUTED, 1 MISLEADING, 1 UNVERIFIABLE — the post core point stands weakened: the ranking claim and the growth figure both shrink under checking. 18 queries run; the two not-found claims are ⚪ for that reason.",
  "evidence":[{"type":"url","ref":"https://web.archive.org/web/2026/appstore-rankings","label":"cited"},
              {"type":"url","ref":"https://company.example/press/launch","label":"cited"}],
  "relation":"toward","links":["F-31","F-32","F-33","F-34","F-35","F-36"]}'
```

**The door teaches the grammar.** `recall` is a *label*, never a `type` — an evidence item like `{"type":"recall", …}` comes back `reject: evidence-type-enum` and writes nothing. Same for a `[cited]` url whose ref is "the official docs" (`reject: cited-url-needs-url`) and a verdict with an empty evidence list (`reject: evidence-required`). Read the rule, fix the record, re-run.

## Self-check before finishing
Before declaring done, verify the records and fix any miss:
- **Records validated at the door (`add` exited 0)** — every id was printed by the script, nothing hand-appended.
- Every checked claim is quoted verbatim inside its statement; every verdict uses the five-verdict grammar.
- Every ✅ has ≥2 *independent origins* as separate `[cited]` evidence items; every 🔴 has real contradicting evidence, not mere absence.
- Every 🔵 states the true/implied/fails triple; every ⚪ states why it can't be checked.
- Daisy-chains were traced; no verdict rests on a lone Tier-3 echo.
- Excluded and below-cap claims were told to the user; nothing silently dropped.
- The symmetry check ran on the hard calls; no invented sources anywhere.
- A prior record this run contradicted was `refute`d, not left live beside the new one.

## Finishing up

Run the four passes, emitting a record per claim as each verdict lands, and write the `kind=result` headline last. Give the user a short chat summary: the headline count, whether the core point stands, the single most important verdict, and the record ids — plus `index.py track --kind finding --status live` to see the claims still standing. Don't paste the records into chat. Offer to go exhaustive beyond the claim cap — or to chain onward: `/critic` if what needs attacking is the argument rather than the facts, `/researcher` if a refuted claim opens a real question, `/watch add` on the confirmed load-bearing claims if the answer has to stay true past today (verdicts have shelf lives).

## Notes on tone and rigor

- Division of labour: `/factcheck` judges **claims against sources**; `/critic` judges **arguments and reasoning**. A piece can be factually clean and logically broken — or the reverse. Chain them for both.
- Calm beats gotcha. A record should read like a lab report, not a takedown; the evidence does the talking.
- On genuinely contested factual territory, present the strongest evidence per side and verdict 🟡 with the disagreement named — don't manufacture false certainty either way.
- The claim cap is a feature: ten claims checked well beat forty checked thin. Say what was left unchecked.
