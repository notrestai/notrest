# The compiler doctrine

The full contract behind `/compile`. Read it once per repo, before the first compile.
`SKILL.md` is the procedure; this is the reasoning the procedure is defending.

---

## 1 · What compiling actually means

**Compiling = moving stable PROCEDURE into deterministic code, and leaving the model exactly
the irreducible semantic judgment.**

The distinction that does all the work is **procedure vs parameter**. "Cut the release for the
parser" and "cut the release for the viewer" are the same procedure with a different
parameter. A workflow is compilable to the extent that its procedure is stable while its
parameters vary — and the estate, which recorded both, is what lets you tell them apart
without guessing.

Every model call that survives compilation earns its place under five conditions:

1. **One named purpose.** Not "handle the item" — "decide whether this ledger line describes a
   release". A call you cannot name in a noun phrase is a call you have not bounded.
2. **The smallest sufficient input.** Not the conversation; not the file; the fields.
3. **A typed output.** A schema, not prose to be re-parsed downstream.
4. **Validated by code.** The validator runs on every response, including the ones that look fine.
5. **Bounded retries.** A number, and a defined terminal state when the number is exhausted.

### The two shapes

**OLD — model-first.** A long instruction, and a model that interprets it, plans, explores,
picks tools, reconstructs its own state, decides everything, validates itself, and decides
when to stop. Every one of those verbs is a place where the same work is redone from scratch
on every run, at model prices, with model variance.

**NEW — compiled.** Thin activation → deterministic adapters → typed state → deterministic
normalization, routing and eligibility → **bounded** model call where judgment is irreducible
→ deterministic validation and side-effect gates → bounded model call where *language* is
needed → typed output → an explicit terminal state.

### What compiling is NOT

Not a shorter prompt. Not a cheaper model. Not caching one answer. Not a fine-tune. Not rigid
automation that removes the judgment the workflow actually needed. And above all **not
dropping functionality to flatter a benchmark** — a parity claim over a quietly reduced scope
is the one failure mode this doctrine exists to prevent, because it is the one that looks like
success.

---

## 2 · Prior art — the house has been compiling all along

This skill did not invent the pattern; it names it, and makes it repeatable. Five workflows in
this repo were already compiled, each by the same move — take the stable procedure away from
the model, leave it the judgment:

| shipped artifact | what used to be model work | what the model does now |
|---|---|---|
| `hooks/agent-ledger.sh` (SubagentStop) | "remember to write down which agents ran, with their models and transcripts" | nothing — the hook writes `COORD-AGENTS.md` at **zero prompt overhead**; the seat reads the index |
| `archivist/scripts/index.py` | re-reading every dossier to answer "have we studied this already" | one `find` against `oracle-index.md` |
| `graph/scripts/graph.py` | reading files to work out how a project connects | opens a page a script built; **the model never reads the repo** |
| `spend/scripts/spend.py` | keeping a routing audit in the model's head and asserting it was clean | logs a line, runs `report`, quotes an exit code |
| `hooks/session-start.sh` | the user typing `/fable-mode` and hoping the discipline stuck | the discipline arrives as injected context, unconditionally |

Read the table as a design lesson rather than a trophy case: in every row the model kept the
judgment (*is this finding real, does this dossier answer the question, is this cluster
suspicious, was the routing rule broken*) and lost the bookkeeping. That is the target shape.

Note what all five have in common — **the compiled artifact is small, boring, and stdlib-only.**
A compiled runtime that needs a dependency tree is usually a workflow that was not ready.

---

## 3 · Detection doctrine

Detection is deterministic because counting is not judging. The rules it follows:

- **Cluster by the underlying JOB, not the wording.** Volatile literals are masked (`v2.16.1`
  and `v3.0.0` are both `<ver>`) so the parameters stop hiding the procedure.
- **Frequent tokens carry the procedure; rare tokens carry the parameters.** Similarity is
  df-**weighted** — the inverse of IDF — because in a ledger of work, repetition is the signal.
- **Average-link, never single-link.** Single-link chains two unrelated rituals together
  through one shared word, and a chained cluster is a false claim about what repeated.
- **A candidate is ripe at 3 occurrences**, with a stable skeleton, identifiable inputs, a
  clear terminal state, and a safe replay path. Fewer than three is an anecdote.
- **Ranking is by repetition, never value.** The scanner has no opinion about what is worth
  compiling and must never be quoted as if it did.
- **Occurrence counts are FLOORS.** Compaction, archived ledgers and missing transcripts all
  remove evidence and never add it. Say "at least N", not "N".

The scanner is also the only part of this skill that is cheap enough to run habitually. Run it
often; run the ritual rarely.

---

## 4 · Reconstruction doctrine — the functional contract

Before anything is built, the old workflow is written down **completely**, from the trail:

- **Every responsibility gets a row**, including the awkward ones — error handling, the
  eligibility check nobody documented, the manual step the owner always does.
- **Every row cites the trail** — a COORD line, a commit, a spend line, a transcript path
  (existence-checked before it is cited). Uncited is `[unverified]`, and `[unverified]` may
  never be load-bearing.
- **Evidence coverage is declared honestly.** Which ledgers, which spans, how many transcripts
  were readable, what is compacted away. **Never claim history you could not access.**
- **Required-for-parity is a separate column from owner-after.** Conflating them is how scope
  quietly shrinks.

Then the partition — **A** deterministic runtime · **B** bounded model call · **C** human
approval · **D** thin activation — with the *why* recorded per row. If **B** swallows the
workflow, the honest answer is "not compilable yet", and that answer is a real deliverable.

---

## 5 · Fair-benchmark laws

A benchmark that is not fair is worse than no benchmark, because it is quoted later.

1. **Equivalent raw inputs on both sides.** **Never feed the compiled version intermediate work
   the old agent had to produce for itself** — no pre-extracted fields, no pre-selected
   records, no pre-summarized context. This is the most common way a compile lies, and it
   invalidates every number downstream of it.
2. **Method A — the estate is the historical side.** The old workflow's recorded cost and
   behavior come from the trail; the compiled side replays from the same point-in-time inputs.
   **Method B** — isolated old-vs-new on the same current inputs — is the fallback when the
   trail is too thin to replay. Name which method ran.
3. **Separate the cost components.** Model calls, tool calls, tokens, latency — reported
   separately. A single blended "cost" number hides the thing the reader needs.
4. **Judge calls are excluded from recurring economics.** Grading is measurement, not runtime.
   Report the grading cost, in the measurement section, where it belongs.
5. **Rubric before judging.** Written down before a single output is compared, blind where
   practical, and ties reported as ties rather than resolved toward the new thing.
6. **Holdouts when the data allows.** Below ~5 scenarios there is nothing to hold out; say that
   instead of pretending to a split.
7. **Show the failures and the outliers per scenario.** A benchmark table with no failures in
   it has usually had its failures defined away.
8. **Quality outranks every number: cheaper-but-worse is a FAILED compile**, not a tradeoff to
   be weighed. Max two bounded repair rounds, then report the gap. The owner is the final
   arbiter.

### Evidence labels

| label | earned when |
|---|---|
| **PROVEN** | ≥5 fair scenarios, every metric provenance-backed |
| **DIRECTIONAL** | fewer scenarios, or any metric that is estimate-grade |
| **UNMEASURED** | it runs; nothing was fairly compared — say it in exactly those words |

---

## 6 · Token accounting — provenance per metric

Reuse `spend`'s grades verbatim, per metric and not per report:

- **`observed`** — a number the harness printed (a subagent's completion count, a workflow
  budget, a `tokens used` echo). Quote it as printed.
- **`estimate`** — your inference, labeled as such wherever it appears. Never launder an
  estimate into observed; a report that mixes them without labels is unusable.
- **`unavailable`** — the harness does not expose it. Say so and move on. An unavailable metric
  is an honest row in the table, not a reason to guess.

**The one-time compilation cost is measured and reported in its own section. It is never
amortized, never allocated into per-run metrics, and no break-even math appears unless the
owner asks for it.** The reason is not modesty: amortization silently converts a one-off spend
into a claim about the future, and the future is exactly what a benchmark cannot measure.

---

## 7 · The 10-condition success standard

Every compile closes with this table, each condition marked **PASS / FAIL / UNTESTED /
DISCLOSED**. `DISCLOSED` means the condition could not be met and the limitation is stated
plainly in the dossier — it is an honest outcome, not a soft pass.

| # | Condition |
|---|---|
| 1 | **Evidence coverage is honest** — sources, spans, and unreadable material named; no claimed history that could not be accessed |
| 2 | **The candidate genuinely repeats** — ≥3 cited occurrences, stable skeleton, safe to replay |
| 3 | **The functional contract is complete** — no responsibility dropped, and required-for-parity marked per row |
| 4 | **The partition is principled** — every retained model call has one purpose, smallest input, typed output, code validation, bounded retries |
| 5 | **The runtime runs** — one obvious command; tests exercise real logic, not mocks agreeing with themselves |
| 6 | **The benchmark is fair** — equivalent raw inputs both sides, no pre-chewed work, method named |
| 7 | **Every metric carries provenance** — observed / estimate / unavailable, per metric |
| 8 | **Quality was judged on a pre-written rubric** — parity verdict explicit; cheaper-but-worse called a failure |
| 9 | **One-time cost is separate** — measured, in its own section, never amortized |
| 10 | **Nothing was installed** — isolated under `compile/<slug>/`, readiness tier claimed equals what was actually run, owner decides |

---

## 8 · LIMITS — what this skill cannot see, in this harness

Stated here once so no dossier has to discover it late. All of these are honest `unavailable`s,
not defects to be worked around with estimates.

- **Main-loop tokens are invisible to the model.** The harness exposes subagent, workflow and
  gpt-lane counts; it does not expose the seat's own consumption. So the compiled-vs-old
  comparison can only be made at the *lane* level, and **no total here is ever the session's
  bill**. `spend`'s ledger says the same thing about itself.
- **Cached vs uncached, and reasoning-token splits, are not exposed.** A token count here is
  gross. A compiled runtime with a small repeated input may be flattered or penalised by prompt
  caching in ways this harness cannot attribute — say so rather than modelling it.
- **Latency is not recorded in the estate.** No ledger line carries wall-clock. Any latency
  comparison requires fresh runs on both sides (Method B); a replay can never produce one.
- **Transcripts compact.** `pre-compact.sh`, `COORD-ARCHIVE.md` and `COORD-AGENTS-ARCHIVE.md`
  make the trail lossy **by design**. Occurrence counts under-count; they never over-count.
- **COORD lines are model-written.** Their wording and their clocks can drift by minutes — only
  `spend.py` lines, SubagentStop lines and git are machine-written. Clustering over
  model-written prose inherits that noise, which is part of why `same-shape` is reported.
- **The scanner sees shape in words, not semantics.** Two entries worded alike but doing
  different jobs will cluster; one job described in two vocabularies may not. Read the evidence
  rows before trusting a candidate — the scanner finds candidates, it does not confirm them.
- **A dead transcript pointer is not evidence.** A `COORD-AGENTS.md` line whose transcript is
  gone is an index entry only; anything load-bearing must come from a file that still exists.
- **Old-side quality is usually unrecoverable.** The trail records what landed, rarely the
  intermediate outputs. Where the historical quality cannot be re-judged, the parity verdict is
  `DIRECTIONAL` at best — and saying that is the whole job.

---

## 9 · Safety

Local only. A compile never publishes, sends, commits, pushes, installs, or replaces. Output is
confined to `compile/<slug>/`. Side-effectful workflows get replay/dry-run adapters, and **a
draft is never evidence that anything was sent**. Pause and ask the owner before a benchmark
run that would spend more than a few dollars. If no candidate can be compiled fairly, deliver
the candidates, the blocker, the missing evidence by name, and the smallest next step —
**never fabricate success**.
