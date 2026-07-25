---
name: actionplan
description: Expand a stepbystep plan dossier into a copy-paste runbook — exact ordered commands per host, a verify + rollback on every step, ⛔ warnings before destructive ops, placeholders instead of invented environment specifics (reads an optional map.md). Use on /actionplan or asks to "turn this plan into commands", "make this copy-paste", "write the runbook", or "give me the exact steps/code". If no stepbystep plan exists yet, suggest /stepbystep first.
---

# Action Plan (Runbook builder)

Takes the high-level, validated plan from `stepbystep` and turns it into an executable **runbook**: for every phase, the exact, ordered, copy-paste-ready commands and code, annotated with which machine to run them on, how to verify each worked, and where to undo them. The goal is that the user can work top-to-bottom — copy a block, run it, check it, move to the next — and finish the job themselves, offline.

Division of labour: `stepbystep` decides *what to do and in what order, and validates it*; `actionplan` decides *exactly how to do each step on the user's real machines*. This skill produces the runbook; it does not execute anything.

## Inputs

- **The stepbystep document (required).** Read the stepbystep **Dossier** (the phases and steps, with their "done when" checks and flags) and its **background** if available (the per-step deep research has the implementation detail that makes commands accurate). Use `$ARGUMENTS`/the text after `/actionplan` to locate it; otherwise look in `action-plan/`. If no plan is found, ask the user to provide the stepbystep dossier — or suggest running `/stepbystep` first (or `/director stepbystep → actionplan`). Don't invent a plan.
- **`map.md` (optional, strongly helpful).** If the user provides a `map.md`, read it first — it describes the environment (machines/hosts, addresses, OS, paths, topology, connectivity). Use it to fill in concrete values so fewer questions are needed.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No files.** Write nothing to disk — no background, no dossier. Skip the "Setup & output files" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — not fully sourced or saved; run again without `--quick` for the verifiable two-file version."*
Quick mode is for fast exploration, not deliverables.

## Setup & output files

Derive a `{topic}` slug from the plan's goal. Create a `runbook/` directory and write two files:

- **`runbook/{topic}background.md`** — the environment profile gathered, the per-phase expansion reasoning, tooling/version decisions, and all assumptions.
- **`runbook/{topic}Dossier.md`** — the runbook itself (titled "<goal> — Runbook"): the copy-paste sequence.

If those already exist, suffix the topic with `-2` (then `-3`, etc.).

Use web search/fetch to confirm exact command syntax, flags, and version-specific details — getting a flag wrong makes a copy-paste step fail. Label what you verify.

## Honesty & safety rules (apply throughout)

A runbook that's wrong or dangerous gets run verbatim on real machines. These are non-negotiable.

- **Never invent environment specifics.** Hosts, IPs, paths, ports, usernames, credentials, versions — these come from `map.md`, the user's answers, or become explicit placeholders. A fabricated path or hostname is far worse than a clearly-marked `<PLACEHOLDER>`.
- **Mark every placeholder** the user must fill, and collect them in one values table: placeholder → what it is → where to find it.
- **Verify version/syntax-sensitive commands** (search where it matters) and label `[cited]` / `[recall]` / `[unverified]`. Flag anything the user should confirm against their exact version.
- **Flag destructive and irreversible commands loudly** — put a ⛔ warning *before* the block (data loss, `rm -rf`, `DROP`, disk/partition ops, overwriting config), tell the user to back up first, and give the restore path. Carry stepbystep's `[ONE-WAY]` flags through.
- **Never hardcode secrets.** Use placeholders or environment variables; remind the user not to paste real credentials into shared files.
- **Respect offline / air-gapped constraints.** If the environment has no internet (check `map.md`/ask), don't emit commands that assume it — flag any artifact that must be pre-downloaded and transferred in.
- **Defer on high-stakes ops.** Production data, security/access config, anything with serious blast radius keeps a `[needs expert]` / verify-first note from the source plan; the runbook makes execution easier, it doesn't make a risky action safe.
- **Keep every verification.** Each step retains its "done when" check so the user knows it worked before proceeding.

## The phases

### Phase 1 — Read the plan & map; build the environment profile → background
Read the stepbystep dossier (and background) and `map.md` if provided. Extract an **environment profile**: the machines/hosts and how to reach each, OS/distro + versions, shell, already-installed tooling, key paths/directories, connectivity (online / offline / air-gapped), access method (e.g. SSH), and permissions (sudo?). Mark each item **known** (from map/plan) or **unknown**.

### Phase 2 — Targeted environment Q&A (elicitation)
Work out exactly which specifics the concrete commands will need that aren't already known. Ask the user a **grouped, minimal batch** of questions — only what's needed for *this* plan, about the machines and where things live — not a generic interrogation. 
- If the user answers, fold the values in.
- If the user declines, or you're running non-interactively (e.g. inside `director`), **don't block** — proceed using `map.md` plus clearly-labeled placeholders and assumptions, and list every unknown at the top of the runbook for them to resolve. Never paper over an unknown with a guess.

### Phase 3 — Expand each phase into exact, ordered, copy-paste steps → (drafted, lands in the runbook)
Walk each phase/step from stepbystep and produce the concrete implementation. A single stepbystep step may expand into several runbook commands. For each command/block:
- **Host & context:** which machine to run it on, and which directory/user.
- **The exact block:** copy-paste-ready, with placeholders for any value from `map.md`/answers.
- **Verify:** the concrete check that it worked (carry the "done when").
- **Rollback:** how to undo it, where reversible; an explicit "no rollback" where not.
- **Flags:** ⛔ destructive/irreversible, `[needs expert]`, offline-staging needed.
Keep prose between blocks minimal — the experience should be copy, run, verify, next.

### Phase 4 — Validate the runbook (consistency pass) → background
Dry-run it mentally end to end: are blocks in correct execution order? Does each step's prerequisites get met by an earlier step? Is every placeholder defined in the values table? Does every destructive step have a ⛔ warning and a backup/restore note? Any secret hardcoded? Any step missing its verify? Fix what this finds, and note the check in the background.

## The dossier (runbook) — `runbook/{topic}Dossier.md`

Self-contained and executable top-to-bottom. **Read Me First, then Before You Start, then the runbook.**

```markdown
# <Goal> — Runbook

## 📌 Read Me First
Plain-language, 3–5 bullets, skimmable in 20 seconds.
- **What this does:** <the end state, one line>
- **How to use it:** copy each block in order, run it on the machine named, check the "verify" line, then continue.
- **Environment assumed:** <OS/hosts in one line — from map.md/answers>
- **⛔ Biggest danger:** <the most destructive/irreversible step to be careful with>
- **Fill these in first:** <values you must supply — see the table below>

**Files:** `{topic}background.md` (environment profile + how each step was expanded) · `{topic}Dossier.md` (this runbook).

---

## Before You Start
- **Prerequisites:** <what must be true/installed before step 1>
- **Connectivity:** <online / offline / air-gapped — and any artifacts to pre-stage>
- **Back up first:** <what to snapshot before the destructive steps>
- **Values to fill in:**

| Placeholder | What it is | Where to find it |
|-------------|------------|------------------|
| `<EXAMPLE_HOST>` | ... | map.md → ... / `command to discover it` |

## The Runbook
Ordered. Run top to bottom. Each step says where to run it and how to confirm it worked.

### Phase 1 — <name>   ·   run on: <host>
1. <short description of what this does>
   ```bash
   <exact command>
   ```
   - Verify: `<check>` → <expected result>
   - Rollback: `<undo command>`  (or: no rollback — <why / restore path>)
   - <flags: ⛔ destructive · [needs expert] · pre-stage offline · confidence [label]>
2. ...

### Phase 2 — <name>   ·   run on: <host>
...

## Unknowns & Assumptions
<anything not pinned down, labeled — placeholders still open, versions to confirm>

## If Something Fails
<the key failure points and how to recover — carried from the plan's contingencies>

## Sources
<numbered real URLs used to verify command syntax/versions, with [labels]>
```

### Example — what a good runbook step looks like
*(Illustrative, expanding a stepbystep cutover step for a Postgres migration.)*

> ### Phase 2 — Cutover   ·   run on: app-server (`<APP_HOST>`)
> 1. Stop the application so no new writes hit the old database.
>    ```bash
>    sudo systemctl stop myapp.service
>    ```
>    - Verify: `systemctl is-active myapp.service` → `inactive`
>    - Rollback: `sudo systemctl start myapp.service`
> 2. ⛔ **DESTRUCTIVE — back up first.** Confirm your dump from Phase 1 exists, then drop the legacy database.
>    ```bash
>    psql -h <DB_HOST> -U <DB_ADMIN> -c 'DROP DATABASE legacy_db;'
>    ```
>    - Verify: `psql -h <DB_HOST> -U <DB_ADMIN> -lqt | cut -d '|' -f1 | grep -qw legacy_db && echo STILL-THERE || echo dropped` → `dropped`
>    - Rollback: none — restore from the Phase-1 dump (`pg_restore`) if needed. `[needs expert]`

## Self-check before finishing
Before declaring done, verify and fix any miss:
- Every command block is copy-paste runnable and in correct execution order.
- No invented hosts/paths/ports/credentials — all are real (from map.md/answers) or marked placeholders defined in the values table.
- Every destructive/irreversible step has a ⛔ warning and a backup/restore note; no secrets are hardcoded.
- Every step carries a "verify" check.
- Offline constraints respected; artifacts needing pre-staging are flagged.
- Version/syntax-sensitive commands were verified or flagged to confirm.
- All open unknowns/assumptions are listed at the top.

## Finishing up

Write `{topic}background.md` first (profile + expansion reasoning), then `{topic}Dossier.md` (the runbook). Give the user a short chat summary: what the runbook accomplishes, the environment it assumes, the most dangerous step to watch, any values they still need to fill, and the path to the files — point them to the runbook. Don't paste it into chat. Offer to fill in placeholders once they share the missing details, or to expand any phase further.

## Notes on tone and rigor

- Pairs with `stepbystep` (run it first, then `/actionplan` on its dossier) and `director` (`stepbystep → actionplan`). Inside `director` or any non-interactive run, skip the Q&A and rely on `map.md` + labeled assumptions, listing unknowns up top.
- The runbook is executed by the user on their own machines — this skill writes it, it never runs commands.
- A placeholder the user fills in 10 seconds is safe; a guessed hostname that points at the wrong machine is not. Always prefer the placeholder.
- Lead each block with where to run it. The most common runbook failure is running the right command on the wrong host.
