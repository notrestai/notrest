---
name: compile
description: "Compile repeated work into code — a script mines the estate for the same job done three or more times, then a ritual builds an isolated runtime under compile/{slug}/ and fair-benchmarks it against that history. Use on \"/compile\", \"compile this workflow\", \"what should we compile\", \"workflow compiler\", \"make repeat work cheaper\". Runtimes stay isolated until the owner ships them."
---

# compile — the estate's fourth verb

**Runtime adapter.** Authorized Codex builder/refuter lanes use explicit
`model: "gpt-5.6-sol"` with `fork_turns: "none"` or a bounded recent-turn fork. Claude
uses explicit `model: "opus"` and never `subagent_type: "fork"`. Resolve
`<plugin-root>` from this selected `SKILL.md`; never execute a literal placeholder.

`archivist` says what the estate *knows*. `graph` says how it *connects*. `recap` says what
happened *over time*. **compile** says what happened over time **more than once** — and does
something about it.

**The credo: the estate already recorded the repetition. Compile moves the stable parts into
code and leaves the model only the judgment. Script owns procedure; the model is a component,
not the engine.**

That inverts the usual shape of an agent. The usual shape is one long instruction and a model
that interprets it, plans, explores, picks tools, reconstructs its own state, decides
everything, checks its own work, and decides when to stop. A compiled workflow is: thin
activation → deterministic adapters → typed state → deterministic routing and eligibility →
a **bounded** model call exactly where judgment is irreducible → deterministic validation and
side-effect gates → typed output → an explicit terminal state.

Compiling is **not** a shorter prompt, a cheaper model, a cached answer, a fine-tune, rigid
automation, judgment deleted, or functionality quietly dropped to flatter a benchmark. Any of
those is a failed compile even when the numbers look good. The full contract, the fair-
benchmark laws, and the token-accounting rules live in
`references/compiler-doctrine.md` — read it before the first compile in a repo.

## Three parts, three owners

The original idea for this skill was a single mega-prompt that did all of it — ironically the
exact pattern it criticizes. In this harness it splits, because each third has a different
right owner:

| | who owns it | why |
|---|---|---|
| **1 · Detection** | `scripts/compile.py` | Finding what repeated is counting, not judging. A script does it deterministically at **zero model tokens** — graph.py's economics. |
| **2 · Compilation** | a seat-run **ritual** | Reconstructing a contract and gating a benchmark is exactly the seat's judgment work, run through the swarm's builder/refuter lanes. |
| **3 · Installation** | the **ship ritual** | A compiled runtime is a normal versioned release, gated by the owner. Never a flag, never automatic. |

---

# Part 1 · Detection is a script

Script: `<plugin-root>/skills/compile/scripts/compile.py` (python3 stdlib only; loose
installs: `.claude/skills/…` or `~/.claude/skills/…`). `<compile-skill>` below means that path.

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
python3 <compile-skill>/scripts/compile.py scan --root "$ROOT"
python3 <compile-skill>/scripts/compile.py report --root "$ROOT"
```

- **`scan --root DIR [--transcripts DIR] [--out DIR] [--sim F] [--min-df N]`** — reads
  `COORD.md` plus any sealed `COORD-<NNN>.md` volumes in order (+ legacy
  `COORD-ARCHIVE.md`) (the `ask -> landed | evidence` lines), `COORD-AGENTS.md`
  (each lane's last conclusion, falling back to the sibling `agent-<id>.meta.json` where the
  hook wrote `last: ?`), and `spend/ledger.md` (`purpose=` strings — the estate's most
  explicit statement of what a lane was *for*). Clusters them by **shape**, then writes
  `<root>/compile/candidates.md` (the reading copy) and `candidates.json` (what `report` and
  the ritual read). Optional `--transcripts DIR` adds repeated Bash-command 5-grams from
  session `.jsonl` files; it is never required and never assumed.
- **`report`** — one `[compile] RIPE …` line per ripe candidate. **Exit 3** when at least one
  ripe candidate is still `NEW`, so a hook can branch on it for free; **exit 0** otherwise —
  including when nothing has been scanned yet, because a hook must never break.
- **`decide --slug S --status NEW|PROPOSED|COMPILED|DECLINED [--alias A] [--note T]`** —
  appends a ruling to `compile/decisions.md`, which the next scan carries back into
  `candidates.md`. Rulings match on slug **and** on the recorded `sig=` core, so a candidate
  the scanner renames as the ledger grows keeps its ruling.

The same script also carries the ritual's two scaffolding verbs — documented where they are
used, in Steps 1 and 2:

- **`contract --slug S [--max-rows N] [--write PATH]`** — the Step-1 responsibility table
  pre-filled with trail citations mined from the same three ledgers. **Exit 3** when nothing in
  the estate matches the slug.
- **`scaffold --slug S`** — the `compile/<slug>/` runtime skeleton. **Exit 2** if the directory
  already exists; it never overwrites a runtime.

Exit codes: `scan` 0 · `report` 0/3 · `contract` 0/3 · `scaffold` 0/2 · bad arguments 2 · an
invalid status 1.

The skill's own contract test is `scripts/fixture.sh` — 80 assertions over a synthetic estate;
run it after any change to `compile.py`.

### How it decides two entries are the same job

**In a ledger of work, FREQUENT tokens carry the procedure and RARE tokens carry the
parameters.** "Cut the release for the parser" and "cut the release for the viewer" differ
only in their parameter. So the scanner masks volatile literals (`v2.16.1` and `v3.0.0` both
become `<ver>`), and weights every shared token by its document frequency — the *opposite* of
IDF, deliberately, because here repetition is the signal and not the noise. Clustering is
average-link, never single-link: single-link chains two unrelated rituals through one shared
word, and a chained cluster is a lie about what repeated.

Then a **cross-source fusion** pass merges candidates whose cores describe the same job. It
has to: one ritual leaves lines in COORD *and* purposes in the spend ledger, and its wording
drifts over a year of ledger, so counting those separately understates the repetition twice
over.

### Reading `candidates.md` honestly

- **The ranking measures REPETITION, never value.** A candidate is RIPE because the estate
  recorded the same shape three or more times. Whether it is worth compiling is the ritual's
  judgment and the owner's decision — never the scanner's.
- **`same-shape` is cohesion, not confidence** — mean pairwise signature overlap. ~0.5+ is one
  ritual recorded many times; ~0.15 is a loose family the clustering swept together, and a
  reader should distrust it. Quote the number when you quote the candidate.
- **One ritual can still surface as sibling rows.** Read the rows adjacent to your candidate
  before reconstructing its contract; a release ritual and its install half are two rows.
- **`--sim` is the dial.** Raise it when candidates read over-merged, lower it when one ritual
  appears twice. The default was swept against a real estate, not guessed.
- **Never hand-edit `candidates.md` or `candidates.json`** — regenerated on every scan, edits
  lost. Rule with `decide`; fix the estate, re-scan.
- **A thin estate gets an empty table, not an invented one.** No repetition yet is a finding:
  say so, and say that appending honest COORD lines is what makes the next scan see anything.
- **Estate vocabulary is not a workflow — hence the stopwords and the `weak-source` mark.**
  Spend purposes share a vocabulary by construction: every job is a "lane", with "rounds",
  "gates" and "fixtures", and things get "shipped". Because similarity is df-weighted those
  were the *heaviest* tokens in the corpus, which once made `lan` the #1 candidate at 31×
  (same-shape 0.15) out of nothing but the seat's own word for a lane. Those words are now
  dropped before weighting (`ESTATE_STOP` in `compile.py`, list and reasoning in-code), so a
  candidate has to repeat in the words of the WORK. Separately, a candidate whose evidence is
  >80% spend purposes with no COORD support is marked **weak-source** and sorted below every
  other candidate — a purpose says what a lane was CALLED, a COORD line says what was ASKED
  and what LANDED. Demoted, never deleted: read a weak-source row as shared vocabulary until
  the ledger says otherwise.

---

# Part 2 · Compilation is a ritual run

`/compile` with no argument: **scan, then report the ripe candidates in one short table and
ask which one** (or say plainly that nothing is ripe). `/compile <candidate>` runs the ritual
below on that candidate. Do not run the ritual on a candidate the owner did not pick.

The ritual is the seat's, run through **agentswarm** — the seat decomposes, judges, applies,
and gates; lanes build and attack. Every offloaded lane carries `model: "opus"`.

**Name it first.** On first contact with a candidate, give it a human name —
`compile.py decide --slug <machine-slug> --status PROPOSED --alias <human-name>` — before
writing a word of the contract. Machine slugs are derived from clustering (`commit-follow-lan`
is a real one); if the ritual starts using them, they become the project's working vocabulary
and nobody will remember what they meant in a month.

## Step 1 — reconstruct the FUNCTIONAL CONTRACT from the trail

**Start with the script, not a blank table:**

```
python3 <skill>/scripts/compile.py contract --slug <candidate> --root . [--max-rows N] [--write PATH]
```

It walks the estate for you — COORD volumes, COORD-AGENTS.md and the spend ledger — and emits
the responsibility table **pre-filled**: rows in timestamp order (Step 1's own rule), each with
its trail citation, its source line ref, and an *Owner today* mined from the ledger's `lane=` /
`model=` rather than assumed. The line numbers and timestamps are already on disk; having the
seat re-derive them by reading ledgers is the exact spend this skill exists to remove, and a
hand-typed citation is the one kind that can be wrong. Exit 3 means **no trail evidence matched
the slug** — that is a finding ("there is nothing to reconstruct a contract from"), not a cue to
start inventing rows.

What it deliberately leaves blank is what you are for: **required for parity**, **owner after**
and **why** come back as `?`, and each Responsibility cell carries the raw ledger quote it came
from, not the answer. Rewrite every cell into a real responsibility. A pre-filled judgment would
be a guess wearing a citation's clothes.

Then do the part no grep can: walk the transcript pointers it lists (recap's trail-walk: COORD
line → COORD-AGENTS entry → the transcript on it → `git diff` → the spend line). **The script
reads ledger lines only** — any responsibility that exists only inside a transcript is missing
from its draft, and its coverage section says so.

Every row carries a trail token (`[COORD 2026-07-25 06:05Z]`, `[commit 5c422ed]`,
`[spend 2026-07-25 04:30Z]`, `[COORD-AGENTS <id> → transcript]`); a row with no token is
`[unverified]` and may not be load-bearing.

| # | Responsibility | Evidence | Required for parity? | Owner today | Owner after | Why |
|---|---|---|---|---|---|---|

Two laws here, both from the original contract and both easy to break by accident:

- **Reconstruct the COMPLETE workflow.** Never omit a hard responsibility because it would
  make the benchmark look worse. A parity claim over a subset is a lie about the subset.
- **Never claim history you could not access.** State the evidence coverage plainly: which
  ledgers, which spans, how many transcripts were actually readable, what is compacted away.

## Step 2 — partition the responsibilities

Every row lands in exactly one bucket, and the *why* is the interesting column:

- **A · deterministic runtime** — parsing, normalization, routing, eligibility, state
  reconstruction, validation, retries, side-effect gates, output shaping. Stable procedure.
- **B · bounded model call** — where semantic judgment is irreducible. Each retained call gets
  **one named purpose, the smallest sufficient input, a typed output, code that validates it,
  and bounded retries**. A call that "does the task" is not bounded.
- **C · human approval** — anything irreversible, anything the owner gates today.
- **D · thin activation** — the surface that starts it. Thin means thin.

If bucket B swallows the workflow, say so and stop: **that workflow is not compilable yet**,
and the honest deliverable is the contract plus what evidence would change the answer.

**Only once the partition says A is real, scaffold the runtime:**

```
python3 <skill>/scripts/compile.py scaffold --slug <candidate> --root .
```

It creates `compile/<slug>/` with `runner.py` (a stub whose `run` exits **4**, so a half-built
runtime can never quietly report success), `README.md` (carrying the *what it does NOT do* and
retained-model-call sections — a compiled runtime silent about its gaps gets read as complete),
`fixture.sh`, and `BENCHMARK.md` with Step 6's symmetry checklist ready to fill. **It never
overwrites an existing directory — exit 2** — because that directory is where the work is.

Scaffold after the partition, not before: the skeleton's sections are the partition written
down, and a skeleton created first gets filled in by habit instead of by the contract.

## Step 3 — one persistent Opus builder lane emits the runtime

Seat-builder ritual, unchanged: spec at the seat, **one persistent lane per domain**, feedback
rounds **resume the same lane** via SendMessage — never a fresh spawn. Everything lands in the
directory Step 2 scaffolded — `compile/<slug>/`, isolated, installed nowhere — and the lane's
job is to replace the stubs, not to re-invent the shape:

- `README.md` — what it does, what it does not, and **one obvious run command**.
- the runner + the deterministic adapters (replay/dry-run adapters for anything with side
  effects — a drafted message is never evidence a message was sent).
- typed schemas for every retained model call — purpose, input shape, output shape, validator.
- validators, and tests that exercise the real logic (not mocks agreeing with themselves).
- replay fixtures drawn from the historical scenarios, plus the benchmark scripts.

## Step 4 — an independent refuter lane attacks it

A different lane than the builder (agentswarm's review-the-fix law). Its brief: find the
responsibility that was dropped, the model call that is not actually bounded, the test that
passes without exercising anything, the fixture that hands the compiled side pre-chewed work,
and the benchmark asymmetry. Every finding needs a concrete failure scenario or it is
downgraded to PLAUSIBLE.

## Step 5 — the seat gates, multiple ways

The seat never accepts a lane's self-report. Re-run the tests exit-code-checked (never piped
through `| tail`/`| head` — they eat the exit code); `py_compile`/`bash -n`/`json.load` each
artifact by kind; grep every claimed edit against the tree; read the runner at the seat; and
when the deliverable renders, **open it and look** — both themes, console clean.

## Step 6 — the FAIR benchmark

**Method A — the estate is the historical side.** The old workflow's cost and behavior are
what the trail recorded; the compiled side replays from **equivalent raw inputs** at the same
point in time. Method B (isolated old-vs-new on the same current inputs) is the fallback when
the trail is too thin to replay.

The laws that make it fair, all of which are easy to violate silently:

- **Equivalent raw inputs, both sides.** Never feed the compiled version intermediate work the
  old agent had to produce for itself. That single mistake invalidates every number after it.
- **Separate the cost components** — model calls, tool calls, latency, tokens — and report them
  separately, never as one blended figure.
- **Token accounting carries provenance per metric**, reusing spend's grades: `observed` (a
  number the harness printed), `estimate` (your inference, labeled), `unavailable` (say so and
  move on). Never launder an estimate into observed.
- **Judge calls are excluded from recurring economics.** Grading is measurement, not runtime.
- **Rubric before judging**, blind comparison where practical, ties reported as ties.
- **Holdout scenarios** when there is enough history to hold any out.

Evidence label, in house grammar, stated on the verdict:

| label | earned when |
|---|---|
| **PROVEN** | ≥5 fair scenarios, every metric provenance-backed |
| **DIRECTIONAL** | fewer scenarios, or a metric that is estimate-grade |
| **UNMEASURED** | it runs; nothing was fairly compared. Say it in those words. |

## Step 7 — the quality law (it outranks every number)

**Cheaper-but-worse is a FAILED compile, not a tradeoff.** Parity is judged against the
functional contract from Step 1, on a rubric written *before* anything is judged. Ties are
reported honestly. **Max two bounded repair rounds** — past that, report the gap instead of
grinding. The owner is the final arbiter of quality, always.

## Step 8 — the one-time compilation cost, reported separately

Log every lane to the spend ledger as it completes
(`spend.py log --lane subagent --model <the id observed in the lane transcript> --tokens N
--grade observed --purpose "compile <slug>: …"`), and report the total in its **own section**.

**It is never amortized, never allocated into per-run metrics, and no break-even math appears
unless the owner asks for it.** State spend's own caveat alongside it: the ledger covers what
the harness exposed, the main loop's own consumption is not visible to the model, and the
ledger total is not the session's bill.

## Step 9 — the deliverable

Lead with the practical result, not the method. Two files plus one visual, in house style:

- **`compile/<slug>/background.md`** — evidence coverage, the full responsibility table, the
  partition, the per-scenario benchmark including failures and outliers.
- **`compile/<slug>/<slug>Dossier.md`** — 📌 Read Me First; the **verdict screen** (old vs new:
  tokens, latency, model calls, tool calls, quality — parity PASS/FAIL, evidence label); the
  before/after flow; the responsibility crosswalk (OLD → NEW component → OWNER **CODE / LLM /
  HUMAN** → WHY); what was compiled, what stayed model-judgment, what needs human approval,
  what is unchanged; the **ONE-TIME COMPILATION COST** section; the three readiness tiers; the
  10-condition success standard each marked PASS / FAIL / UNTESTED / DISCLOSED; and the
  installation decision, which is a recommendation and not an action.
- **`compile/<slug>/verdict.html`** — self-contained, both themes, **render-gated**: open it
  and look before delivering, or say plainly in chat *and* in the dossier that it was written
  but NOT render-verified.

---

# Part 3 · Installation is a release, not a flag

A compiled runtime lives isolated under `compile/<slug>/` until the owner says ship. Wiring it
into a skill, a hook, or a command is then a **normal versioned release through this repo's
ship ritual** — manifests, CHANGELOG, README, commit, marketplace update — with the owner
gating it like any other. Three readiness tiers, and the ritual states which one it reached:

| tier | means | proof required |
|---|---|---|
| **DEMO IT** | replay against historical scenarios, zero side effects | the replay ran; output attached |
| **USE IT** | isolated live-equivalent run | **VERIFIED** or **NOT-LIVE-VERIFIED**, in those words |
| **INSTALL IT** | the steps to wire it in | **described, NOT EXECUTED** — always |

**Never auto-install. Never replace the existing path.** The old workflow stays warm as the
rollback until the owner retires it.

## Safety

Local only. No publishing, sending, committing, pushing, installing, or replacing as part of a
compile. Side-effectful workflows get replay/dry-run adapters — **a draft is never evidence it
was sent**. Pause and ask before a benchmark run that would spend more than a few dollars.

## When there is nothing to compile — say so

If no candidate can be compiled fairly, the deliverable is: the candidate list, the **blocker**,
the **missing evidence** by name, and the **smallest next step** that would change the answer.
**Never fabricate success.** Common honest outcomes: the estate is too thin (fix: append COORD
lines); the ritual is mostly judgment (bucket B swallowed it); the trail records outcomes but
not inputs, so no fair replay exists.

## Self-check before finishing

- The scan was run by the script this turn and its summary line is in the transcript — the
  model did not eyeball the ledgers to decide what repeats.
- Every responsibility in the contract carries a trail citation; nothing load-bearing is
  `[unverified]`; evidence coverage is stated, including what was unreadable.
- Both benchmark sides started from equivalent raw inputs, and you can say *how* you know.
- Every metric carries its provenance grade; judge calls are out of the recurring economics.
- The parity verdict came from a rubric written before judging, and cheaper-but-worse was
  called a failure.
- The one-time compilation cost has its own section and was not amortized anywhere.
- `compile/<slug>/` is the only place anything was installed, and the readiness tier claimed
  matches what was actually run.
- The verdict page was opened and looked at — or the dossier says plainly that it was not.
- Every lane carried `model: "opus"` and has a spend ledger line; `spend.py report` ran.

## Chains

`/recap` supplies the trail-walk the contract is reconstructed from · `/archivist` says whether
this candidate was already studied · `/graph` shows what the compiled runtime would touch ·
`/critic --panel` red-teams the parity claim before the owner sees it · `/spend` receipts the
one-time cost · `/sessionend` banks the candidate list so the next session does not re-scan
blind. The doctrine, in full: `references/compiler-doctrine.md`.
