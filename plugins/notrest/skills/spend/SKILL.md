---
name: spend
description: "The token receipt — an append-only spend/ledger.md logging every observed model spend (subagent fan-outs, gpt-lane calls, workflow runs) so the offload routing rule is CHECKABLE instead of merely asserted. Use on /spend, \"log the spend\", \"spend report\", \"token report\", \"how much fable did we burn\", \"audit the model routing\", or at the close of any session that spawned agents. Each entry graded observed or estimate; main-loop totals aren't exposed to the model and the ledger says so."
---

# spend — the receipt behind the routing rule

v2.7.0 hardcoded the rule (Fable is the orchestrator seat, not the fan-out) in the
SessionStart hook and fable-mode Hard Rule 11; since v2.9.0 the owner policy (2026-07-15)
routes every offloaded job to explicit Opus —
but a rule without an instrument is an assertion. This skill is the instrument: every model
spend the session can *observe* gets one append-only ledger line, and `report` computes the
model split and flags any offload lane that ran on anything but Opus.

Script: `scripts/spend.py` (python3 stdlib; flock-atomic appends, same DNA as chatroom's
room.py). Ledger: `<root>/spend/ledger.md`. Fixture: `scripts/fixture.sh` — 41 assertions
over synthetic ledgers proving the gate both fires and stays quiet in the right cases
(never touches the real ledger).

## Commands

- **Log:** `python3 <skill>/scripts/spend.py log --model <id> [--tokens N] [--lane main|director|seat|subagent|workflow|gpt|<name>] [--grade observed|estimate] [--purpose "..."] [--root <project>]`
  — tokens optional (`unknown` is honest and allowed); grade defaults to `observed`.
- **Report:** `python3 <skill>/scripts/spend.py report [--root <project>] [--since YYYY-MM-DD] [--json]`
  — entries and token totals per model with share %, count of estimate-grade entries, and
  the routing verdict. **Exits 4 on a violation**, so it can gate a script or a ship
  ritual. `--since` narrows to entries dated on or after a day; `--json` emits the same
  findings machine-readably with the same exit codes.

## What counts as a violation

The verdict line names the rule version it enforces — `policy 2026-07-15: opus-only
offload` — so a gate log is greppable and a stale rule cannot hide behind the word
"CLEAN". An **offload lane** is any lane that is not a seat lane (main/director/seat).

- **Violation (exit 4)** — an offload lane on a known non-Opus model, dated after the
  policy day.
- **Policy-date guard** — an entry is judged by the law in force when it was logged.
  Entries dated on or before 2026-07-15 fall under the rule that was live then ("Fable
  never rides in a subagent"), so a pre-policy non-Opus lane is lawful-at-the-time and is
  counted as `pre-policy`, while a pre-policy Fable subagent still exits 4 as a **legacy
  violation**. The policy day itself is grandfathered — the ledger stamps minutes, but the
  hour the policy was set is not recorded. A timestamp that will not parse gets no
  exemption: it is judged by the live rule, so a garbled stamp cannot buy amnesty.
- **Cross-vendor allowlist** — `lane=gpt` and `lane=chatroom-gpt` run another vendor's
  models by design; exempt, and reported on their own count ("cross-vendor lanes: N,
  exempt") rather than folded into "compliant".
- **Unverifiable, not clean** — an offload entry whose model is `?` (the auto-receipt could
  not read the transcript) is **not** called a violation, because absence of evidence is
  not evidence of one. It gets its own reported line saying routing is not provable for it.
  Chase it by reading the transcript the COORD-AGENTS.md entry points at.

## When to log (the whole discipline)

Log at the moment the number is in front of you — it is not exposed twice:
- **Subagent completes** → the task notification carries its token count; log one line per
  agent: `--lane subagent --model <what you set> --tokens <count> --grade observed`.
- **Workflow finishes** → log `budget.spent()` (or the run's reported total) as one
  `--lane workflow` line; fan-out details go in `--purpose`.
- **gpt lane call** → codex echoes `tokens used`; log it `--lane gpt --grade observed`.
- **No number available** → log the call anyway with `--tokens` omitted or your honest
  guess as `--grade estimate`. A model-only entry still audits routing perfectly — the
  model name is always known, and routing is what the rule is about.
- Session close (`/sessionend`) → run `report`; paste the verdict line into the handoff.

## Honesty rules

- **Routing compliance is exact; token totals are not.** Every entry's `model` is what was
  actually set on the call — the violation check is airtight. Token sums cover only what
  the harness exposed; the main loop's own consumption is NOT visible to the model and is
  never in the ledger. Say both facts when reporting; never present the ledger total as
  the session's total bill.
- **Grades are load-bearing.** `observed` = a number the harness printed; `estimate` =
  your inference (and the report counts how many of those there are). Never launder an
  estimate into observed.
- **Append-only through the script** — flock keeps multi-session repos safe; hand-edits
  break the audit trail. Wrong entry? Log a correcting line, don't rewrite history.
- No secrets in `--purpose` — the ledger is a plain project file that travels with the repo.

## Self-check before finishing

- Every agent/workflow/gpt call you made this turn has a ledger line (or you said which
  were unobservable and why).
- The report's verdict line is in the transcript when you claimed the routing was clean —
  "clean" without a run report is `[unverified]`.
- Token claims carried their grade; nothing estimated was presented as observed.
- If report exited 4, the violation was surfaced to the user verbatim — never smoothed.

## Finishing up

Chains: `report` at `/sessionend` (verdict into HANDOFF.md); a violation feeds `/critic`
("how did the routing rule get bypassed?"); a `fable-director` seat can log per-burst and
show the owner an actual sonnet/opus split per round. Pairs with `archivist` — the ledger
is greppable estate, and the index can carry its path.
