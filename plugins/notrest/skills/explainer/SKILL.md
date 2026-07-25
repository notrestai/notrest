---
name: explainer
description: Build genuine understanding of any topic, system, or document — a correct mental model, three depth layers (plain → working → expert), the standard misconceptions, and how to verify the load-bearing claims yourself — producing a background doc + understanding dossier (or --quick for the chat-only mental model). Use on /explainer or asks to explain, "help me understand", "what is X really", "break this down", "ELI5", or "teach me X". For real understanding-building — answer quick factual questions directly.
---

# Explainer

Turns any topic, system, concept, or document into understanding that survives contact with reality: a mental model that's actually correct, layered depth the reader can climb at their own pace, the misconceptions they'd otherwise absorb, and the means to check the important claims themselves. The reasoning runs through five passes; the output is **two files** — a consolidated background document and a final understanding dossier.

The bar is *understanding*, not coverage: a reader should finish able to predict how the thing behaves, explain it to someone else, and spot nonsense about it — not just recognize the vocabulary.

## The prompt

The subject is everything the user passed when invoking the skill — a topic, a question, a system, or an attached document to be understood. Use `$ARGUMENTS` if populated; otherwise the text after `/explainer`. If a document is referenced but not in context, read it from disk first. If the subject is genuinely ambiguous ("explain the thing"), ask exactly one clarifying question, then begin. Note any stated audience ("for my mom", "I'm a senior engineer") — it calibrates every layer.

**Consult the index first (if present).** If the repo carries an `oracle-index.md` — or the **archivist** skill is installed and prior ORACLE output folders exist — run one `find` on the subject before Pass 1: a prior `understanding/` dossier on the same subject means offer *reuse* / *extend* / *fresh* instead of rebuilding the mental model from scratch.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the mental model in plain language), then the plain layer and the top 2–3 misconceptions. No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not fully sourced or saved; run again without `--quick` for the verifiable two-file version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output files

Derive a `{topic}` slug from the subject: lowercase, hyphen-joined, punctuation stripped, max ~50 chars. Create an `understanding/` directory and write exactly two files:

- **`understanding/{topic}background.md`** — all five passes, as sections within this one document.
- **`understanding/{topic}Dossier.md`** — the final understanding dossier.

If those files already exist from a prior run, suffix the topic with `-2` (then `-3`, etc.).

Web search/fetch: use it where correctness is date-sensitive (versions, prices, laws, live systems) or where you're not certain — a wrong explanation taught confidently is worse than none. **Search budget (token discipline):** ~8 searches/fetches default (~2 in `--quick`); a stable, well-understood topic may honestly need none — then label recall as recall.

## Honesty rules (an explanation that lies is worse than no explanation)

- **Label non-obvious claims** `[cited]` (retrieved this run, with URL), `[recall]` (training knowledge, not freshly verified), or `[unverified]`. Date-stamp anything fast-moving.
- **Analogies must not lie.** Every analogy states where it breaks — an analogy taught without its breaking point becomes the reader's next misconception.
- **Contested is contested.** Where experts genuinely disagree, name the positions and who holds them — don't teach one side as settled fact.
- **No invented history or attribution.** No made-up origins, quotes, or "studies show".
- **Simplification ≠ distortion.** Each layer may omit detail; it may not say things the deeper layers contradict. The plain layer is a subset of the truth, never a different truth.
- **Say what you don't know.** A visible gap beats a smooth fabrication.

## The five passes — all written into `understanding/{topic}background.md`

```markdown
# <Subject> — Understanding Background
> Working document. All five passes. The explanation lives in {topic}Dossier.md.

## Pass 1 — Scope & calibrate
## Pass 2 — The mental model
## Pass 3 — The three layers
## Pass 4 — Misconceptions & edges
## Pass 5 — Verify it yourself
```

### Pass 1 — Scope & calibrate
Pin down: the exact subject (and what's explicitly out of scope), the audience and their apparent starting level, why they want to understand it (decision? curiosity? exam? using it at work?), and the 3–5 questions a real understanding must be able to answer. If a document is the subject, map its structure and claims here.

### Pass 2 — The mental model
The heart of the skill. Find the *smallest set of ideas that makes the whole thing make sense* — the causal story, the governing constraint, the "it's really just X managing Y" insight. Draft it in plain language, pick 1–2 analogies **with their breaking points**, and state what the model predicts (if the model is right, what follows?). Verify the model against sources where uncertain — this is where being wrong does the most damage.

### Pass 3 — The three layers
Write the explanation three times, each self-consistent with the model:
- **Plain** (anyone): no jargon, the analogy, what it is and why it matters. ~150 words.
- **Working** (someone who'll use it): the mechanism, the moving parts and how they interact, the vocabulary now earned, what you can *do* with it, rules of thumb.
- **Expert edges** (someone going deep): the boundaries — where the standard story breaks down, current debates, the sharpest known gotchas, what the textbooks gloss over.

### Pass 4 — Misconceptions & edges
The standard wrong beliefs — what do people who *half*-understand this get wrong? For each: the misconception, why it's tempting, why it's wrong, and the correction in one line. Include near-miss concepts commonly confused with the subject (X vs the thing people think is X). Check the explanation you just wrote against this list — fix anything in Pass 3 that feeds a misconception.

### Pass 5 — Verify it yourself
For the 3–6 load-bearing claims of the explanation: how the reader can check each one *without trusting you* — a primary source to read, an experiment or calculation to run, a thing to observe. Plus a short **Going Deeper** list: the 2–4 best next resources, each with one line on what it adds (real, labeled sources — not a link dump).

## The dossier — `understanding/{topic}Dossier.md`

Write this **after** the background doc. Self-contained — a reader gets the whole understanding from this file alone. **Read Me First and the mental model up top.**

```markdown
# <Subject> — Understanding

## 📌 Read Me First
Plain-language, 3–5 bullets, skimmable in 20 seconds.
- **What it is:** <one line>
- **The mental model:** <the core insight in one sentence>
- **Why it matters to you:** <tied to their stated purpose>
- **The #1 misconception:** <the one most people hold>
- **Confidence:** <how settled this knowledge is — and where it's contested>

---

## The Mental Model
<The Pass-2 story: the smallest set of ideas that makes it make sense. The analogy, with where it breaks.>

## Layer 1 — Plain
## Layer 2 — Working knowledge
## Layer 3 — Expert edges

## Common Traps
- **<misconception>** — why it's tempting; why it's wrong; the correction. <repeat>

## Check It Yourself
- **<load-bearing claim>** — how to verify it without trusting me. <repeat>

## Going Deeper
- <resource — what it adds> [label]

## Sources
<numbered real URLs used, with dates where they matter>
```

### Example — what a good mental-model section looks like
*(Illustrative, for "explain DNS".)*

> **The mental model:** DNS is a *distributed phone book with aggressive caching* — nobody holds the whole book; everyone holds the pages they were recently asked about, plus the number of someone who knows more. Every lookup is "check my notes → ask someone closer to the source → write down the answer with an expiry date (TTL)." The analogy breaks in one place: unlike a phone book, answers can differ by *who's asking and from where* (split-horizon, geo-routing) — the book is allowed to lie to you on purpose.

## Self-check before finishing
Before declaring done, verify the dossier and fix any miss:
- The mental model actually predicts behavior — it's an engine, not a slogan.
- No layer contradicts a deeper layer; simplifications are subsets, not distortions.
- Every analogy states where it breaks.
- Misconceptions are the *standard* ones, and Pass 3's text doesn't feed any of them.
- Contested areas are shown as contested; fast-moving facts are dated; claims are labeled.
- Check-It-Yourself covers the load-bearing claims, not trivia.

## Finishing up

Write `{topic}background.md` first (all five passes), then `{topic}Dossier.md`. Give the user a short chat summary: the mental model in a sentence or two, the #1 misconception, and the paths to both files — point them to the dossier. Don't paste the files into chat. Offer to go deeper on any layer — or to chain onward: `/factcheck` to verify the load-bearing claims independently, `/decider` if the understanding was in service of a choice.

## Notes on tone and rigor

- Understanding is the deliverable; length is a cost. The shortest explanation that produces real understanding wins.
- Meet the audience where they are: an expert asking "explain X" wants the edges, not the plain layer read aloud.
- It's valid to conclude "this is genuinely unsettled — here are the live positions" rather than manufacturing certainty.
- If the subject is a *document*, the mental model is the document's actual argument — explain what it says before what you think of it (that second part is `/critic`'s job).
