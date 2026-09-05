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
  hook wrote `last: ?`), `spend/ledger.md` (`purpose=` strings — the estate's most
  explicit statement of what a lane was *for*, minus the `lane=daemon` lines the compiler
  writes about itself) and `archive/findings.jsonl` (the `learning` and `open` records —
  lessons, below). Clusters them by **shape**, then writes
  `<root>/compile/candidates.md` (the reading copy) and `candidates.json` (what `report` and
  the ritual read). Optional `--transcripts DIR` adds repeated Bash-command 5-grams from
  session `.jsonl` files; it is never required and never assumed.
  **Runtime, measured (F5, 2026-09-01):** ~2 s on a 378-entry estate (260 COORD lines, 78
  agent lines, 40 spend lines) on an idle M-series laptop — **seconds, not minutes**. It was
  **~45 s** through v4.6.1: cProfile put 96% of the wall clock inside the pairwise
  similarity, which recomputed the union weight of every signature pair on every merge pass;
  the arithmetic is now done once and the output is byte-identical (proven by an A/B on a
  frozen corpus). Cost grows with the SQUARE of the largest family, so a many-thousand-line
  COORD will still take minutes. **`scan` narrates itself on stderr** — one line per ledger
  family with its entry count and elapsed time, plus a "still merging" line at least every
  10 s — so a long scan is visibly alive rather than indistinguishable from a hang. stdout
  stays the machine surface; redirect stderr if you want it silent.
- **`report`** — one `[compile] RIPE …` line per ripe candidate. **Exit 3** when at least one
  ripe candidate is still `NEW`, so a hook can branch on it for free; **exit 0** otherwise —
  including when nothing has been scanned yet, because a hook must never break.
- **`decide --slug S --status NEW|PROPOSED|DRAFTED|COMPILED|ADOPTED|PARKED|DECLINED
  [--alias A] [--note T] [--evidence KIND=REF]`** — appends a ruling to
  `compile/decisions.md`, which the next scan carries back into `candidates.md`. Rulings match
  on slug **and** on the recorded `sig=` core, so a candidate the scanner renames as the ledger
  grows keeps its ruling. `ADOPTED` is the one status that needs receipts — all three of
  `fixture=`, `benchmark=`, `refuter=`, or it is refused at exit 2 having written nothing.
  The three statuses the pipeline adds: **DRAFTED** (contract + skeleton exist, nothing built),
  **ADOPTED** (all gates green; the estate may use it — still installed nowhere), **PARKED**
  (failed twice unattended; never retried until the owner re-arms it).
- **`draft [--all-ripe | --slug S]`** — scaffolds every ripe `NEW` candidate into its own
  `compile/<slug>/` (contract, skeleton, benchmark harness) and records it `DRAFTED`. Zero
  model tokens, idempotent, and it **never touches an existing slug**. **Exit 0** even with
  nothing scanned, because the pulse daemon calls it after every scan and a hook must not
  break; **3** for a `--slug` the scan never saw.
- **`auto-run [--next | --slug S] [--runner CMD] [--dry-run] [--model M] [--max-turns T]
  [--timeout S] [--today YYYY-MM-DD]`** — the unattended pipeline (see below). With neither
  `--next` nor `--slug`, it behaves as `--next`.
- **`auto [--on [--unattended --daily-cap N --run-cap M --max-turns T --stop-cooldown H]|--off]`** — the standing
  authorization (see below). `--on` writes `~/.notrest/auto-build/<estate-sha>.json`
  (owner-private, outside the repo — v4.5), `--off` removes it, bare prints status **and all
  four rails**: **exit 0** opted in, **exit 5** not, **exit 2** on a cap flag without
  `--unattended` (a budget for something that never runs is a setting nobody reads). Without
  `--unattended` it authorizes DISPATCH only; installation is untouched either way.

The same script also carries the ritual's two scaffolding verbs — documented where they are
used, in Steps 1 and 2:

- **`contract --slug S [--max-rows N] [--write PATH]`** — the Step-1 responsibility table
  pre-filled with trail citations mined from the same three ledgers. **Exit 3** when nothing in
  the estate matches the slug.
- **`scaffold --slug S`** — the `compile/<slug>/` runtime skeleton. **Exit 2** if the directory
  already exists; it never overwrites a runtime.

Exit codes: `scan` 0 · `report` 0/3 · `contract` 0/3 · `scaffold` 0/2 · `auto` 0/2/5 ·
`draft` 0/2/3 (`--recheck` 0) · `auto-run` 0/2/3/5/6 · `credential` 0/2/5 · bad arguments 2 · an invalid status 1.

`auto-run`'s codes are the ones a daemon branches on, so they are listed separately:
**0** ran to completion — adopted, nothing to do, BUSY (the lock was held), or a quiet stop
on a runner that failed or was not logged in · **2** usage/refused before anything ran ·
**3** a gate came back RED; the status is unchanged and the reason is in `decisions.md` ·
**5** not authorized for unattended spending (no marker, or a dispatch-only one) ·
**6** a cap stopped it; nothing further was spent.

The skill's own contract test is `scripts/fixture.sh` — 579 assertions over a synthetic estate,
including the whole unattended pipeline driven by a FAKE runner that spends nothing;
run it after any change to `compile.py`.

### Lessons become candidates too

The scan reads more than the ledgers. It also walks `archive/findings.jsonl`'s **learning**
and **open** records — both id spaces, `L-<n>` and `O-<n>` — and a lesson whose statement
recurs **three or more times** (normalized the same way repeated work is: the volatile
literals masked, stemmed, stopworded, then keyed on the whole token *set*, so the same lesson
in different words months apart still groups) becomes a candidate of kind **`rule`**, carrying
in `records:` the record ids it was built from. A record the store has marked `superseded` or
`refuted` never reaches one, and a statement with fewer than three content tokens is skipped
rather than grouped — *"it did not work"* normalizes to almost nothing and would sweep every
terse record in the store into one triumphant candidate that means nothing. It then enters the same pipeline as any other candidate — because the
compiled form of a lesson is not a paragraph, it is a **hook arm or an eval check**. A rule
nobody encoded is a rule the estate re-learns; three learnings saying the same thing are the
estate asking for a gate.

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

### Job-likeness — is this candidate work, or an account of work?

Every candidate carries a **`job`** score: the share of its cited rows carrying a **runnable
token** — a flag, an exit code, a command, a path, a version, a commit. A row recording what a
machine DID names something a machine can do; a row narrating a decision does not.

- **Scored on the ledger line, never on the contract row.** Every `CONTRACT.md` row carries
  its own citation by construction, so scoring the row scores the scaffolding — measured
  here: it returned 1.00 for all 38 drafted slugs on this estate.
- **A candidate scoring 0.00 is `narration, not a job`** and is never drafted; the scanner
  banks a `DECLINED` ruling naming itself as the author, and the owner can re-rule it.
- **`draft --all-ripe --max N`** (default 5) drafts the best N per pass, highest score first,
  ties by occurrence count; the rest stay NEW with `not drafted: below the per-pass cap`. A
  slug already scaffolded consumes no slot, or the queue never advances.
- **`auto-run --next`** takes the highest-scored DRAFTED slug, then the oldest — with 41
  drafted, blind first-armed order spends the night on whichever narration was scaffolded
  first.
- **A missing score is not a score of zero.** A `candidates.json` written before the score
  existed is re-scored from its cited rows, never condemned for a missing field.
- **⛔ IT DOES NOT SEPARATE EVERY CORPUS, AND SAYS SO.** Measured on this estate: all 41
  drafted slugs score **0.93–1.00**, so `--recheck` declines **none** of them. They are the
  seat's own narration about building a release — and that narration is *dense with runnable
  tokens* because the work it describes is runnable (`eval rc=0`, `fixture.sh`, `--daily-cap`).
  Job-likeness separates work from talk; it does not separate work from *talk about work*.
  What bounds the flood here is the per-pass cap and the ranking, not the refusal.

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
- **The compiler never reads its own paperwork — the ouroboros has TWO doors.** Door one is
  the daemon's own `lane=daemon` spend receipts (below). Door two is the **operator**:
  `decide --status ADOPTED` and `auto-run` both print a COORD line for a human to paste, and
  the pulse log gets pasted too. The refuter pasted 12 adopt lines and 12 pulse lines and
  `scan` returned **three ripe candidates**, `slug-adopt-benchmark` at 12× among them — and
  with the marker merely opted, estate-pulse runs `draft --all-ripe` on every pulse, so the
  compiler's own paperwork becomes a drafted runtime overnight. **The tag is the test:** the
  COORD and COORD-AGENTS readers drop any line tagged `[compile]`, `[hook]`, `[daemon]` or
  `[pulse]` — the estate's names for its own machinery. A line written *by* the harness
  *about* the harness is not evidence a human did the same job twice, however often it
  repeats. Dropped at the reader, before the vocabulary, exactly as `lane=daemon` is.
  **`draft --recheck` is the retroactive half:** it re-judges every slug already DRAFTED on
  disk, reading each one's cited rows from *today's* ledgers through its own `CONTRACT.md`
  (a machinery-built candidate no longer exists in `candidates.json` to be judged from), and
  DECLINES the machinery-derived ones. It deletes nothing — a `DECLINED` ruling takes a slug
  out of `auto-run`'s reach, and what happens to the directory is the owner's call. A slug
  with no contract is reported **unjudgeable**, never declined by default.
  As defence in depth, **`draft` re-reads the cited rows** and refuses a candidate more than
  half of whose evidence is machinery-tagged — because dropping lines at the reader does
  nothing about a `candidates.json` an older scan already wrote, which is the file the next
  pulse actually reads. The refusal is banked as a ruling (`DECLINED`, naming the scanner as
  its author and the owner's override) so it is not re-examined and re-noted every pulse.
- **The compiler never reads its own receipts — door one.** `auto-run` writes a
  `lane=daemon` line to `spend/ledger.md` for every headless call, and those are ledger lines
  like any other: on the third unattended run the scanner clustered *the compiler's own
  spending* into a ripe candidate, which `draft` would scaffold and `auto-run` would then pay
  to compile. Found on this lane's own smoke test before the arms for it existed; the estate
  would have paid for it nightly. `lane=daemon` is now dropped **at the reader**, before the
  vocabulary, the signatures or the fusion weights — the `ESTATE_STOP` principle applied to a
  whole line rather than a token, so no wording of the purpose string can smuggle it back in.

---

## Auto-build — standing authorization

Detection is automatic and the SessionStart nudge is automatic; the *build* used to wait on
a human typing `/compile`. `compile.py auto --on` closes that gap without moving the safety
line one inch.

- `python3 <compile-skill>/scripts/compile.py auto --on --root "$ROOT"` writes
  `~/.notrest/auto-build/<estate-sha>.json` (owner-private, outside the repo — v4.5) — one JSON line, `{"opted": true, "stamp": "<UTC>"}`. Adding `--unattended --daily-cap N` puts `unattended: true` and `daily_cap_tokens` in the same marker: the opt-in and its budget live together, so revoking one revokes the other. `--off` removes
  it; bare `auto` prints status (exit 0 opted in, exit 5 not). The marker is the **owner's
  standing authorization**, on disk where it can be read and revoked.
- With the marker present and a ripe `NEW` candidate scanned, the SessionStart hook stops
  nudging and prints **`[notrest] AUTO-BUILD opted in: …`**. **Treat that echo as a
  directive**: dispatch ONE persistent Opus builder lane for the named candidate, this
  session, without asking again.
- **One candidate per session — never more.** The echo names exactly one; the rest keep
  waiting. A session that compiles two candidates has exceeded the authorization.
- **From dispatch onward the ritual is unchanged**: Step 1 contract → Steps 2–3 build →
  Step 4 an independent refuter lane → Steps 5–6 the seat's gates and the FAIR benchmark →
  Step 7 the quality law. Standing authorization buys the *start*, never a shortcut.
- A missing or malformed marker is **not** an opt-in: the hook falls back to the old nudge
  silently, and `auto` reports OFF. A corrupt opt-in is no opt-in.
- **A legacy marker is a warning, not a silent no.** Before v4.5 the opt-in lived at
  `compile/.auto-build` inside the repo. The move to `~/.notrest/auto-build/` did not migrate
  it, so an estate that had opted in went quietly back to nudging for weeks and nobody was
  told. Now `auto` and the SessionStart hook both **WARN once** when the legacy marker exists
  and the new one does not, and the message names the migration. An authorization that lapses
  in silence is worse than one that was never given.

### Automatic end to end — the owner's 2026-09-05 ruling

The owner ruled the whole pipeline automatic, superseding the older *installation is
owner-gated forever* line above it. Each step still leaves a ledger line, and the safety that
mattered is kept in a different place — **in the gates**, not in a human clicking through:

1. **Draft is automatic and costs nothing.** After a fresh scan the pulse daemon runs
   `compile.py draft --all-ripe`: every ripe `NEW` candidate is scaffolded into its own
   isolated `compile/<slug>/` — contract, skeleton, benchmark harness — idempotently, never
   touching an existing slug, recorded as `DRAFTED`. Zero model tokens.
2. **Build and refuter run unattended.** Owner ruling, same day: *"the daemon should spend
   tokens too, make it fully unattended."* `compile.py auto-run --next` is the pipeline runner
   the pulse daemon calls after a scan. It takes the **oldest DRAFTED** candidate and runs
   **BUILD → `fixture.sh` → REFUTE → `benchmark.sh` → adopt**, the two token steps as headless
   `claude -p --model opus --output-format json --max-turns 60` calls with the contract as the
   prompt (the free script gates sit between them on purpose — see the rails below). `--next`
   takes the oldest drafted candidate, `--slug` names one, `--model` is recorded on every
   receipt, and `--dry-run` prints the plan while spending nothing and taking no lock.
   **Exit codes:** `0` adopted, a quiet stop, or `BUSY` · `2` usage · `3` a step went red (a
   strike — the status is unchanged and it will be retried) · `5` no valid marker, or
   authorized for dispatch only · `6` a cap stopped it.
   In-session automation stays as it was: the SessionStart echo names the
   candidate and the seat dispatches the builder and refuter lanes without asking again.
3. **The rails are what make that safe, and each one is armed.** Spending tokens with nobody
   watching is only defensible if every way it can go wrong is bounded *first*:
   - **One estate-wide lock** at `compile/.auto-run.lock` (flock, non-blocking). Never two
     runs at once, and never while a live session is running its own compile — a session
     running the ritual by hand takes the same file. A held lock is **exit 0 `BUSY`**, never
     a queue: a queue of unattended runs is how one slow build becomes ten concurrent ones.
     A `BUSY` beside another run's `STOPPED` in the same second is **the lock working**, and
     the log says so in those words — two pulses raced and one stood down.
   - **Two strikes and the slug is PARKED.** A candidate whose build, fixture, refuter or
     benchmark comes back red twice is written `PARKED` with the reason and is **never
     retried unattended**; the owner re-arms it with `decide --slug S --status DRAFTED`.
     (The owner's rule names build and refute; fixture and benchmark reds count too, because
     a slug that fails its own fixture every night is the same bill.) An unattended loop that
     retries forever is a bill with a heartbeat.
   - **The run cap is an IN-FLIGHT bound, not a post-hoc count.** *Live, first unattended
     day:* `decisions.md` 10:00Z recorded `doctor-refuter-tre` — *"CAPPED after build: this
     invocation spent 1,409,130 tokens against a run cap of 400,000"*. The cap noticed 3.5x
     over budget **after the money was gone**, because a token count only exists once the
     call has finished. So the ceiling is now handed to the CLI, which bounds the call while
     it runs: every runner invocation carries **`--max-budget-usd`**, derived from the
     marker's `run_cap_usd` (default = the run cap at $25/million — 400,000 tokens → $10.00;
     owner-settable with `auto --on --unattended --run-cap-usd N`, and `auto` prints it).
     The flag is appended to **whatever** the runner is, not only the built-in default, so
     the rail can be armed. The result's `total_cost_usd` is written into the receipt beside
     the token count, and a call the CLI stopped on budget is recorded as
     **`CAPPED-IN-FLIGHT`** with its cost — a **strike**, like any red, because a candidate
     that cannot be built inside its budget is one that needs a person. The token run cap
     stays as the backstop for a runner that ignores the flag.
   - **The status line never calls a stop `OK`.** `OK <slug> capped before build` was a
     contradiction in four words. The grammar is `CAPPED <slug> daily cap reached` ·
     `CAPPED <slug> run cap reached` · `CAPPED-IN-FLIGHT <slug> <usd>`.
   - **An unreported run is charged at the run ceiling.** The daily cap summed only the
     *numeric* receipts, so a runner whose result carried no `usage` cost **zero** against
     it — the cap was bypassed entirely by a CLI that simply stopped reporting, while the
     line beside it said "unverifiable" and gated nothing. *A disclosure that changes no
     decision is a comment.* An unknown-usage run is now counted at the **run ceiling** (the
     most it could have cost under this estate's own rails), the receipt records
     `tokens=unknown counted-as=<n>` — the token count is still never invented, only the
     charge is stated — and `--dry-run` shows the conservative sum. It over-counts on
     purpose: what is being bounded is a bill, and the safe direction to be wrong in is
     "stopped early".
   - **Caps the owner sets, on two clocks.** `auto --on --unattended --daily-cap N --run-cap M
     --max-turns T` writes `unattended: true` and the budgets into the marker (defaults:
     1,500,000 tokens/day, 400,000 per invocation, 60 turns per runner call). The runner
     **refuses to start a step that would breach one**, and the refusal is a pulse line rather
     than a silence. Two clocks because they fail differently: a run-cap bounds one runaway
     build, a daily cap bounds a week of small ones.
   - **Every headless run is receipted.** `spend.py log` records the observed token count from
     the CLI's own JSON result, with `lane=daemon` and the model explicit — the same ledger,
     the same routing gate, no exemption for work nobody watched. The receipt is written
     **before** any verdict on the run, so a call that failed is still counted. A result whose
     JSON carries no usage is logged `tokens=unknown grade=estimate` and says so in the
     purpose: **a plausible-looking number in a spend ledger is worse than a gap**, because a
     gap is visibly a gap. Those `lane=daemon` lines are then **excluded from `scan`** — see
     the ouroboros note in Part 1, without which the compiler compiles its own receipts.
   - **The fixture runs between build and refute, and the refuter's verdict fails closed.**
     The order is BUILD → `fixture.sh` → REFUTE → `benchmark.sh` → adopt: the two script gates
     cost nothing, and paying a refuter to tell you what a free script already said is a
     waste. The refuter must end with a literal **`REFUTER: CLEAN`** (in its result or in
     `REFUTER.md`); silence, a crash, or a wandered-off lane all read as a **defect**. Nobody
     is watching, so silence must never be able to promote a runtime.
   - **A quiet stop backs off, and a run of them counts.** A runner that fails — non-zero
     exit, an auth refusal, or a result whose JSON says `is_error` — ends the run with one
     pulse line, the status unchanged, and **no retry**. It is *not* a strike (the candidate
     did nothing wrong), so the slug is **stamped and cooled down** for
     `--stop-cooldown H` hours (default 6, on the marker) and **three consecutive quiet
     stops are converted into one strike** — a permanently broken runner therefore parks its
     slug instead of being dialled every pulse. An explicit `decide --status DRAFTED` clears
     both the cooldown and the run. *Live, 2026-09-05:* before this existed, an armed marker
     had the pulse retry one slug on three consecutive pulses, each logged "strike 0 of 2";
     nothing was spent only because the CLI failed **before** reporting usage.
   - **`is_error` outranks the exit code, and the reason is kept.** Probed at the seat: an
     expired session comes back as `{"subtype":"success","is_error":true,"result":"Failed to
     authenticate: OAuth session expired…"}` **at exit 0**, and a clean environment says
     `Not logged in · Please run /login` instead — two reports with no words in common. So
     the result is judged on `is_error` whatever the exit code, and the reason (the result
     string, or the last 400 bytes of stderr) goes into the pulse line **and the receipt
     purpose**. The live report was three identical `runner exited 1` lines carrying no cause
     at all; a diagnosis nobody can read is not a diagnosis.
   - **The credential step is OPTIONAL** (owner ruling, 2026-09-05). Precedence is
     `CLAUDE_CODE_OAUTH_TOKEN` in the environment → the owner's file → **the CLI's own
     login**. With neither of the first two, `auto-run` **calls the runner anyway** and lets
     the CLI use whatever login the machine has — so an owner whose terminal is already
     logged in never meets a credential step at all. *Absence of a file is not evidence of
     absence of a login.* Only an **auth-shaped `is_error` coming back from that call** is a
     block, and that is the one moment anything mentions setting a credential up.
   - **When it IS needed, one command does it.** `claude setup-token` prints a long-lived
     token but does **not** log the CLI in (live probe: `auth status` still said
     `loggedIn false` afterwards), and the pulse daemon is spawned by hooks *inside the app*
     — there is no shell in the chain, so an export can never reach it. So:

         python3 <compile-skill>/scripts/compile.py credential --setup

     runs `claude setup-token` on the owner's own TTY (they complete the browser step),
     captures its stdout, recovers the single token from it, **verifies it with a one-turn
     probe**, and only then writes
     **`${NOTREST_HOME:-~/.notrest}/credentials/claude-oauth-token`** at **mode 0600 in a
     0700 directory**. It prints exactly `credential: ok` or `credential: invalid — <first
     120 chars>`. `--set` (hidden stdin paste) and `--status` (present/absent + modes) stay
     as fallbacks. A token that fails the probe is never written — a 3am run should not be
     the thing that discovers it.
   - **A wrapped token is one token.** Live failure, 2026-09-05: the terminal wrapped the
     printed token, the clipboard carried the break, and the CLI rejected *"a line break at
     character 80 (110 characters on 2 lines)"*. Every step of that is normal behaviour by a
     terminal, a clipboard and a CLI; what was missing was something that turned the paste
     into a credential. So **all** whitespace — newlines, CR, spaces, tabs — is stripped
     from the file's contents *and* from any paste, and `--setup` joins **adjacent**
     token-shaped output lines (which is exactly what a wrap looks like) before deciding
     how many candidates it found. Zero candidates or more than one is refused, never
     guessed between; so are a label that came along with the paste, a truncated paste
     (under 16 characters), and an issuer prefix appearing twice.
   - **The mode rule is kept, and a bad mode still blocks.** File and directory must have no
     group or other bits and be owned by the user running the daemon. Anything else is
     **refused with a `BLOCKED` status naming the mode problem**, never silently downgraded
     to "no credential" — that would teach the owner a world-readable token is merely
     ineffective rather than dangerous. A block costs the slug **no strike and no cooldown**:
     an estate-wide problem is not the candidate's fault.
   - **The value goes to exactly one place: the child's environment.** It is never printed,
     logged, receipted, put in a status line, or included in an error — not even in the
     refusal that rejects it. Every surface says only which source was used
     (`credential: env` · `file` · `cli` · `none`) and, at most, the token's *length* and
     how many lines it was recovered from. Env wins when both exist, and the file is then
     not read at all.
   - **The child starts from a scrubbed environment.** The pulse daemon is spawned by hooks
     inside a *live* Claude session, so the runner would otherwise inherit that session's
     `CLAUDECODE` / `CLAUDE_CODE_*` and boot a headless `claude -p` inside another Claude.
     Those are removed before exec. Credentials are the exception and pass through by name
     (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`) — a daemon
     cannot answer `/login`. No value is ever read, logged, or receipted.
   - **One status line anyone can branch on.** `pulse/auto-run.status` is a single
     overwritten line: `[ts] BLOCKED auth: <reason>` · `[ts] COOLDOWN <slug> until <ts>` ·
     `[ts] OK <slug> <step>` · `[ts] IDLE nothing drafted`. **BLOCKED** and **COOLDOWN** are
     the two a SessionStart banner should surface — they are the states where silence is
     indistinguishable from success. A BUSY run never overwrites it: that status belongs to
     the run that holds the lock.
   - **The runner is injectable, and the plan is printable.** `--runner <cmd>` lets the
     fixtures drive the whole pipeline without spending a token — which is why this path can be
     tested at all — and `auto-run --dry-run` prints what would happen while spending nothing,
     taking no lock and changing no state.
   - **`NOTREST_UNATTENDED=1` on every headless run**, and the hooks honor it: no AUTO-BUILD
     echo, and **no lane spawns from inside an unattended run**. One level deep, never a tree.
   One candidate at a time either way — the echo names exactly one, the runner takes the oldest
   one — which is what keeps "automatic" from meaning "unbounded".
### The credential — optional, and one command

**Nothing else in this plugin needs a credential.** Every other verb, hook and instrument is a
local script. This one thing — the daemon spending tokens while nobody is at the keyboard — is
the exception, and it is **opt-in**: no `auto --on --unattended`, no credential, no question.

The runner resolves one in order, and the first that works wins:

1. **`CLAUDE_CODE_OAUTH_TOKEN`** in the environment.
2. **The owner file** `${NOTREST_HOME:-~/.notrest}/credentials/claude-oauth-token` — mode
   `0600` in a directory with no group or other bits. A bad mode is a **refusal, not a
   warning**: silently using a world-readable token would teach the owner that the mode does
   not matter.
3. **The CLI's own login.** A logged-in terminal needs nothing at all.

*Why a file and not an export:* `claude setup-token` prints a long-lived token but does **not**
log the CLI in, and the pulse daemon is spawned by hooks **inside the app** — there is no shell
in that chain, so a token exported in a terminal never reaches it. A file on the owner's own
disk is the only place both sides can meet, and it sits beside the authorization marker for the
same reason: nothing inside an estate can write it and no clone can carry it.

**When none of the three works, nothing breaks and nothing hides.** Drafting still runs (it is
free), the runner writes `BLOCKED` to `pulse/auto-run.status`, and the SessionStart banner says
so **once per UTC day** — a line that repeats every session is a line that stops being read —
carrying the single remedy:

```bash
python3 <compile-skill>/scripts/compile.py credential --setup
```

`--setup` runs `claude setup-token` on the owner's terminal, recovers the token from its output
(wrapped or not), writes it at `0600` in a `0700` directory and verifies it — one turn, printing
only `credential: ok` or `credential: invalid — <reason>`. `--set` takes a hidden paste and `--status` reports present/absent and
the modes; `--verify` spends one headless turn proving a token works **before** writing it.
**The value is never printed, logged, receipted or put in an error** — every surface names only
which source was used: `credential: env` · `credential: file` · `credential: none`. A secret in
a pulse log is a secret in a file the owner thought was diagnostics.

4. **Adoption is automatic under green gates.** Fixture green **and** a FAIR benchmark green
   **and** the refuter CLEAN → the seat's gate step writes `decide --status ADOPTED` with the
   receipt line, and the estate starts using the runtime. `decide --status ADOPTED` refuses
   (exit 2, writing nothing) without `--evidence fixture=REF --evidence benchmark=REF
   --evidence refuter=REF` — all three, each a ref a reader can go and check — so an adoption
   that cannot show its receipts cannot be written; `decide --status DECLINED` revokes one.
   Because DRAFTED scaffolds are **gitignored** (`/compile/*/` with an allow-list — an
   unattended daemon that drafts 36 directories overnight must not also decide what the
   repository contains), adoption prints the exact **`git add -f compile/<slug>`** that
   admits one, and `auto-run --dry-run` names it in advance. The `-f` is the point: it
   overrides the ignore rule, and a person types it.
   **ADOPTED is still not INSTALLED**: it rules that the estate may *use* the runtime, and
   wiring it into the harness remains the versioned release of Part 3 that the owner ships.
   No marker has ever authorized that, and none can. Cheaper-but-worse is still a *failed*
   compile (Step 7) — the quality law outranks the automation exactly as it outranks a number.


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

**Under the unattended pipeline none of that moves — the asking does.** A run nobody is
watching cannot pause for a question, so the owner answers once, in advance, with the
`--daily-cap` on the marker; the runner refuses the step that would breach it rather than
guessing what the owner would have said. Adoption still marks a runtime as the estate's chosen
path and **installs nothing** — shipping a compiled runtime remains a normal versioned release
the owner gates by hand.

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
- If this run started from an AUTO-BUILD echo, exactly ONE candidate was built and nothing
  was installed — the standing authorization covers dispatch, never the ship.
- The verdict page was opened and looked at — or the dossier says plainly that it was not.
- Every lane carried `model: "opus"` and has a spend ledger line; `spend.py report` ran.

## Chains

`/recap` supplies the trail-walk the contract is reconstructed from · `/archivist` says whether
this candidate was already studied · `/graph` shows what the compiled runtime would touch ·
`/critic --panel` red-teams the parity claim before the owner sees it · `/spend` receipts the
one-time cost · `/sessionend` banks the candidate list so the next session does not re-scan
blind. The doctrine, in full: `references/compiler-doctrine.md`.
