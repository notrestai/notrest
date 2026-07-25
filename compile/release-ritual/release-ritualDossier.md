# release-ritual — the maiden compile

**The notrest ship ritual, compiled into 853 lines of stdlib Python that makes zero model
calls.** Working notes and full evidence: `background.md`. Visual verdict: `verdict.html`.

---

## 📌 Read Me First

1. **The release ritual is now a script.** Twelve clauses that used to be a model reading a
   checklist and editing nine files by hand are now one command. It makes **zero model calls**
   — not a cheaper model, not a shorter prompt: none.
2. **It reproduced five real historical ships exactly.** Replayed `f3b148a`, `fbe1e07`,
   `4c78590`, `f115695`, `5c422ed` — every one `surfaces=9 · differs=0 · PARITY PASS`, about
   1.2 seconds each.
3. **On one of them it did better than history did.** The v3.1.0 replay reports `drift=3`: the
   ritual corrected three skill-count inconsistencies that the real ship shipped wrong.
4. **The evidence is DIRECTIONAL, not PROVEN — and that matters.** Two of the nine compared
   surfaces are round-trip identities that *cannot fail* by construction. Five fair scenarios,
   but the surface set is not uniformly independent. Read the verdict screen, not just the
   PASS.
5. **Nothing is installed and nothing has really shipped.** It lives isolated under
   `compile/release-ritual/`. It has never executed a live ship — push and install are
   replay-only so far. The old workflow stays warm as the rollback.

---

## THE VERDICT SCREEN

| | OLD — the seat does the ship | NEW — `ship.py` does the ship |
|---|---|---|
| **Model calls at runtime** | every step (a model read the ritual and edited each file) | **0** |
| **LLM invocations** | one long session per ship | **0** |
| **Latency** | a session's worth of turns *(not separately metered — `unavailable`)* | **~1.2 s** per replayed scenario · **775 ms** ship-pipeline · clone 290 · seed 48 · extract 58 · parity 54 *(observed)* |
| **Tool calls** | dozens of reads/edits/greps per ship *(never counted at the time — `unavailable`)* | **1** command, plus the script's own subprocesses (`git`, `spend.py`, `claude` CLI) |
| **Quality / parity** | history is the baseline | **PARITY PASS — 5/5 scenarios, `surfaces=9 · differs=0`**, plus `drift=3` where the ritual **corrected** history |
| **Evidence label** | — | **DIRECTIONAL** — five fair scenarios, but 2 of the 9 compared surfaces are round-trip identities that cannot fail, and 2 more of the count surfaces are rewritten without being compared |

**Cheaper-but-worse would be a failed compile.** It is not cheaper-but-worse: the compiled
side matched every compared surface on every scenario and improved three of them on one.

**Old-side token cost is deliberately not stated as a number.** The historical ships were run
before per-ship token metering existed in this estate; inventing a figure to make a ratio
would violate the token-accounting rule. The honest comparison is **0 model calls vs. an
unmetered session**, and that is the comparison above.

---

## Before / after

**Before** — for each of ten ships in the trail:

> seat reads CLAUDE.md's release ritual → bumps `plugin.json` → bumps `marketplace.json`
> (metadata **and** the notrest entry, without touching the tombstone) → counts skill dirs →
> rewrites the spelled count in four prose surfaces and the numeral in two more → patches the
> flow-page header stamp → patches the footer stamp → writes and prepends the CHANGELOG
> section → appends the COORD line → remembers to run the spend report → remembers to run
> `claude plugin validate` → `git add -A` → commit with the trailer → push → marketplace update
> → plugin update → writes a paragraph about what it thinks it did.
>
> Every step a model turn. Every step a chance to skip a surface — and history proves three
> got skipped at v3.1.0.

**After** — one command:

```bash
python3 compile/release-ritual/ship.py ship --version 3.2.0 --gates-passed \
  --message "v3.2.0 — <what landed>" \
  --changelog-file /tmp/section.md \
  --coord-line "- [2026-07-26 09:00Z] [fable-main] v3.2.0 shipped | evidence: ..." \
  --push --install
```

> The human writes three prose artifacts and makes one ruling. The script does the other
> twelve clauses, asserts each one, and prints a typed summary line. Any failure after the
> first write restores every path it touched with `git checkout --` and leaves a clean tree.

---

## Responsibility crosswalk

| OLD (seat did it) | NEW component | OWNER | WHY |
|---|---|---|---|
| "Did we pass the gates?" | `--gates-passed` refusal switch (exit 10) | **HUMAN** (enforced by CODE) | A script may enforce that the ruling was made. It may never make it. |
| Bump `plugin.json` + `marketplace.json`, leave the tombstone alone | clause 2 — entries located **by name**, post-write byte-for-byte tombstone re-assert (exits 11/12) | **CODE** | Two manifests must agree and a third entry must not move. Mechanical, and exactly what humans get wrong. |
| Recount skills, rewrite six prose surfaces | clause 3 — `ls skills/` then rewrite; checker wider than rewriter (exit 13) | **CODE** | Counting directories is arithmetic. History skipped three surfaces at v3.1.0. |
| Patch the flow-page header + footer | clause 4 — each pattern must match **exactly once** (exit 14) | **CODE** | Two fixed patterns; "exactly once" is the safety property. |
| Write the release narrative | `--changelog-file` | **HUMAN** | What a release *means* is not derivable from a diff. |
| Prepend it correctly, with the right date | clause 5 — first line must read `## X.Y.Z — <today UTC>` (exit 15) | **CODE** | Placement and date assertion are mechanics. |
| Write the COORD testimony | `--coord-line` | **HUMAN** | Testimony about what happened is the seat's, not the script's. |
| Append it in ledger format | clause 6 — each line must start `- [` (exit 16) | **CODE** | Format is mechanical. |
| Remember to run the spend report | clause 7 — `spend.py report`; **its exit 4 aborts the ship** (exit 17) | **CODE** | The routing policy already existed; only its enforcement was optional. |
| Remember to validate the plugin | clause 8 — `claude plugin validate .`; absence detected **only** by `FileNotFoundError` (exit 18) | **CODE** | The old string-match turned a real failure into "CLI absent, proceed". |
| Write the commit message | `--message` | **HUMAN** | Same reason as the changelog. |
| `git add -A` + commit with the `Co-Authored-By` trailer | clause 9 (exit 19) | **CODE** | Mechanical, and the trailer is policy that got forgotten. |
| Decide whether to push | `--push` flag | **HUMAN** | Irreversible. |
| Push safely and prove it landed | clause 10 — exact object `<sha>:refs/heads/<branch>`, detached HEAD refused, `ls-remote` read back, empty result is its own failure (exit 20) | **CODE** | Proving the push landed is verification, not judgment. |
| Decide whether to install | `--install` flag | **HUMAN** | Mutates the user's installed toolchain. |
| Run marketplace update + plugin update, confirm the version | clause 11 — output parsed for the target version (exit 21) | **CODE** | Two fixed commands and an assertion. |
| Write a paragraph about what happened | clause 12 — one typed summary line | **CODE** | A typed terminal state beats a model's account of its own work. |

---

## What was compiled · what stays human · what is unchanged

**Compiled to CODE (bucket A):** all twelve clauses' mechanics — manifest bumping with the
tombstone assertion, count reconciliation, flow-page stamping, changelog placement with its
date assertion, COORD append, the spend gate, the validator gate, staging and commit, the
exact-object push with `ls-remote` verification, the install with its version assertion, and
the typed summary. Atomic writes throughout; `git checkout --` rollback of every touched path
on any abort after the first write.

**Model judgment retained (bucket B): NONE.** Zero model calls at runtime. This is the real
finding of the maiden compile: once the three prose artifacts exist, no remaining step needed
semantic judgment. It is also the claim most worth attacking, which is why an independent
refuter lane was pointed straight at it.

**Human approval (bucket C) — five decisions, all preserved, none softened into a default:**
the `--gates-passed` ruling · the changelog prose · the COORD line · the commit message ·
the `--push` and `--install` flags. Omit `--push` and the run stops after the commit and says
so. Omit `--install` and it prints the two CLI commands for you to run yourself.

**Unchanged:** the ritual itself — same twelve clauses, same order, same manifests, same
CHANGELOG, same COORD ledger, same marketplace commands. Nothing was dropped to flatter a
benchmark. The old hand-run path still works and stays warm as the rollback until the owner
retires it.

---

## ONE-TIME COMPILATION COST

Reported separately, **never amortized into per-run metrics**, and no break-even math (none
was asked for).

| lane | observed opus tokens |
|---|---|
| builder round 1 | 108,400 |
| builder round 2 | 125,790 |
| builder round 3 | 208,275 |
| refuter | 100,027 |
| **TOTAL** | **542,492 observed opus tokens** |

Every lane carried `model: "opus"` explicitly, per standing policy. Seat orchestration is
**not** in that number.

**Spend's caveat, stated plainly:** the ledger covers what the harness exposed. The main
loop's own consumption is **not visible to the model**. **542,492 is not the session's bill.**

---

## Readiness — three tiers

| tier | status | what it means |
|---|---|---|
| **DEMO IT** | ✅ **VERIFIED** | Replay against historical scenarios, zero side effects. Ran, output attached in `background.md` §4. Command: `python3 compile/release-ritual/ship.py replay --at f3b148a --scratch /tmp/replay-a --time` — and the full battery: `bash compile/release-ritual/fixture.sh` (**51/51, exit 0**). |
| **USE IT** | ⚠️ **NOT-LIVE-VERIFIED** | The real command is `python3 compile/release-ritual/ship.py ship --version X.Y.Z --gates-passed --message "…" --changelog-file <f> --coord-line "- [...]" [--push] [--install]`. It has **never executed a real ship.** Everything proven is replay-proven. First live use should omit `--push` and `--install`, inspect the commit, then push by hand. |
| **INSTALL IT** | 📋 **DESCRIBED, NOT EXECUTED** | Wiring it into a skill/hook/command is itself a normal versioned release through this repo's ship ritual — manifests, CHANGELOG, README, commit, marketplace update — owner-gated like any other. Not done. Never automatic. |

---

## Success standard — 10 conditions

| # | condition | verdict |
|---|---|---|
| 1 | The complete workflow was reconstructed — no hard responsibility dropped | **PASS** — 12 clauses, including the two expensive irreversible ones |
| 2 | Every responsibility carries a trail citation; nothing load-bearing is `[unverified]` | **PASS** — `background.md` §2 |
| 3 | Evidence coverage stated, including what was unreadable | **PASS** — `background.md` §1 (COORD 2026-07-15→2026-07-25, commits `9522ded`→`f3b148a`; transcripts not relied on) |
| 4 | Both benchmark sides start from equivalent raw inputs | **PASS** — same three prose artifacts, tree at `sha~1`, count surfaces de-shipped so reconciliation is a real operation |
| 5 | Cost components reported separately, each with a provenance grade | **PASS with DISCLOSURE** — latency `observed`; model calls `observed` (0); old-side tokens `unavailable` and labeled so, never estimated into a ratio |
| 6 | Parity judged against the contract, cheaper-but-worse called a failure | **PASS** — 5/5 `differs=0`; `drift=3` is an improvement, reported separately and established by arithmetic |
| 7 | Evidence label honest about what the scenarios prove | **PASS (label: DIRECTIONAL)** — round-trips and uncompared count surfaces disclosed on the verdict screen, not in a footnote |
| 8 | An independent lane attacked it and its findings were resolved | **PASS** — 15 findings, 3 CONFIRMED criticals, all fixed in ONE bounded repair round (the quality law's second and final); the seat re-ran both critical repros |
| 9 | One-time cost in its own section, not amortized | **PASS** — 542,492 observed opus tokens, with spend's caveat |
| 10 | Runtime isolated; the readiness tier claimed matches what was actually run | **PASS with DISCLOSURE** — only `compile/release-ritual/` was written; DEMO IT VERIFIED, USE IT **NOT-LIVE-VERIFIED**, INSTALL IT **NOT EXECUTED**; version monotonicity **UNTESTED** (`ship --version 3.1.1` on a 3.3.0 tree succeeds); root `README.md`/`CLAUDE.md` numerals **UNTESTED** for parity |

**Render gate — RENDER-VERIFIED, with one limit stated.** `verdict.html` was opened in the
browser pane and looked at: dark theme screenshotted and correct; both palettes confirmed to
resolve (`data-theme="light"` → `rgb(247,246,242)` on `rgb(26,26,24)` ink; `data-theme="dark"`
→ `rgb(25,25,23)`); console **clean, zero errors**; exactly **one** script in the document (the
theme toggle, nothing else); no CDNs; five tables; no horizontal overflow at 1280px
(`scrollWidth == clientWidth`). **The limit:** the light theme was verified by computed style,
not by a light-theme *screenshot* — the browser pane went hidden mid-check and the follow-up
screenshot came back blank. Said plainly rather than rounded up to "looked at both themes".

---

## Installation decision — a recommendation, not an action

**Recommended: adopt at USE IT, gated, before considering INSTALL IT.**

Use `ship.py` for the next real release **without `--push` and without `--install`**. Inspect
the commit it produces, then push by hand. That converts the one gap that matters — the
runtime has never done a real ship — into evidence, at the cost of one manual push, with the
old hand-run path warm behind it and a `git checkout --` rollback armed if anything aborts.

Two things to fix before full adoption, neither blocking a gated first use:

1. **Version monotonicity** — add the assertion that the new version exceeds the current one.
2. **Root `README.md` / `CLAUDE.md` numerals** — either bring them into the parity set (which
   means fixing the historical drift first) or state permanently that clause 3 writes six
   surfaces and proves four.

**Do not auto-install. Do not replace the existing path.** The old workflow stays warm as the
rollback until the owner retires it — and the owner, not this dossier, makes that call.
