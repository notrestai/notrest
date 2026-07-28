---
name: actionplan
description: Expand a stepbystep plan into a copy-paste runbook — exact ordered commands per host, a verify + rollback on every step, ⛔ warnings before destructive ops, placeholders instead of invented environment specifics (reads an optional map.md). Use on /actionplan or asks to "turn this plan into commands", "make this copy-paste", "write the runbook", or "give me the exact steps/code". If no stepbystep plan exists yet, suggest /stepbystep first.
---

# Action Plan (Runbook builder)

Takes the high-level, validated plan from `stepbystep` and turns it into an executable **runbook**: for every phase, the exact, ordered, copy-paste-ready commands and code, annotated with which machine to run them on, how to verify each worked, and where to undo them. The goal is that the user can work top-to-bottom — copy a block, run it, check it, move to the next — and finish the job themselves, offline.

Division of labour: `stepbystep` decides *what to do and in what order, and validates it*; `actionplan` decides *exactly how to do each step on the user's real machines*. This skill produces the runbook; it does not execute anything.

The runbook is a **file** — it has to survive the session that wrote it, because the operator reads it at 2am on another machine. So the file stays the deliverable, and one `kind=result` record in the archivist store tracks it, carrying the runbook's path as evidence.

**Router shape:** `runbook`

## Inputs

- **The plan (required).** Prefer the store: `index.py find "<goal>"`, then `index.py track --kind decision` — the `stepbystep` **decision record** gives the plan shape, the convergence status, and the hinge; its linked `[ONE-WAY]` finding records give the irreversible steps with their "done when" checks and rollbacks. Read the plan prose too if it is still in this session (the per-step deep research has the implementation detail that makes commands accurate), and read a legacy `action-plan/{topic}Dossier.md` if one exists from an older run. Use `$ARGUMENTS`/the text after `/actionplan` to name the goal. If no plan record and no plan document is found, ask the user for one — or suggest running `/stepbystep` first (or `/director stepbystep → actionplan`). Don't invent a plan.
- **`map.md` (optional, strongly helpful).** If the user provides a `map.md`, read it first — it describes the environment (machines/hosts, addresses, OS, paths, topology, connectivity). Use it to fill in concrete values so fewer questions are needed. If they don't have one, hand them `references/map-template.md` — the shape this skill reads (hosts, services, paths, connectivity, tooling, known-unknowns) with a filled example, and the one law that keeps it safe to hold: **credentials go in by reference, never by value.** Name the vault item, the env var, the key file or the person; a `map.md` that needs rotating is a liability, not an input. Asking for the map is cheaper than asking twelve questions in Phase 2.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or a clear equivalent — "quick", "brief", "no files", "just the summary"), run lightweight instead of the full workflow:
- **No file, no record.** Write nothing to disk and nothing to the store. Skip the "Setup & output" step entirely.
- **Reason, compressed.** Still work through this skill's core logic and search where it normally would, but skip the full multi-pass write-up.
- **Output in chat only:** the **Read Me First** block this skill defines (the plain-language gist), then a short summary (a few sentences or bullets). No sources/reference list.
- **Stay honest anyway.** Don't fabricate; still flag a claim inline as `[recall]`/`[unverified]` if it is. End with one line: *"Quick read — nothing written or recorded; run again without `--quick` for the runbook file and its record."*
Quick mode is for fast exploration, not deliverables.

## Setup & output — the runbook file, tracked by a record

**One file, one record.** Derive a `{topic}` slug from the plan's goal, create a `runbook/` directory, and write **`runbook/{topic}Runbook.md`** — the runbook itself (titled "<goal> — Runbook"): the copy-paste sequence. If it already exists, suffix the topic with `-2` (then `-3`, etc.) so you never overwrite a runbook someone may be halfway through. **No background file:** the environment profile, the per-phase expansion reasoning, and the tooling/version decisions stay in this session as prose, and the assumptions that matter travel *inside* the runbook's own Unknowns & Assumptions section, where the operator will actually see them.

Then one `kind=result` record in the archivist store (`archive/findings.jsonl`, append-only, validated at the door) so the runbook is findable from `track` and the river instead of only from the filesystem:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{…}'
```

(Loose install: `../archivist/scripts/index.py` relative to this skill folder.) It prints the assigned `F-<n>` on success and **exits 2 naming the rule** on rejection — a runbook record with an empty evidence list, or a `[cited]` url that is not a URL, does not enter the store. Fix the record, re-run; never hand-append to the JSONL. The record never replaces the file: a runbook you can't open at 2am is not a runbook.

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

### Phase 1 — Read the plan & map; build the environment profile → (reasoning)
Read the plan — the `stepbystep` decision record and its linked `[ONE-WAY]` findings, plus the plan prose or a legacy dossier if either is available — and `map.md` if provided. Extract an **environment profile**: the machines/hosts and how to reach each, OS/distro + versions, shell, already-installed tooling, key paths/directories, connectivity (online / offline / air-gapped), access method (e.g. SSH), and permissions (sudo?). Mark each item **known** (from map/plan) or **unknown**.

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

### Phase 4 — Validate the runbook (consistency pass) → (reasoning, then the record)
Dry-run it mentally end to end: are blocks in correct execution order? Does each step's prerequisites get met by an earlier step? Is every placeholder defined in the values table? Does every destructive step have a ⛔ warning and a backup/restore note? Any secret hardcoded? Any step missing its verify? Fix what this finds, and note the check in the background.

### Phase 5 — Lint the runbook → (the gate, run before the record is emitted)
Phase 4 is judgement, and judgement is the thing that reads its own work charitably at the end of a long session. This phase is mechanical. Run it over the written file **before** the summary and **before** the record:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/actionplan/scripts/runbook_lint.py" runbook/{topic}Runbook.md
```

(Loose install: `scripts/runbook_lint.py` relative to this skill folder.) Zero model tokens. It reads the file; it never edits it and it never executes a command out of it — `bash -n` *parses* a copy of each block and does not run it, so the "writes, never executes" law holds. What it checks:

- every fenced `bash`/`sh`/`zsh` block parses under `bash -n`, and — when `shellcheck` is installed — its error-severity findings too. If shellcheck is absent the run prints that it degraded and keeps going: its absence is never a failure here, and `bash -n` still ran.
- every step keeps a **Verify** line and a **Rollback** line. An explicit `Rollback: none — <restore path>` counts; silence does not.
- every phase heading names the host to run it on.
- every `<PLACEHOLDER>` used appears in the values table.
- every destructive op — `rm -rf`, `DROP`, `dd`, `mkfs`, `truncate`, a redirect onto a device, `kubectl delete`, `git push --force` — carries its ⛔ at or above its line.
- nothing in the file matches a credential shape. The secret classes are **chatroom's** (`chatroom/scripts/room.py`), imported rather than re-declared — one list, one place, because two lists drift and the one that drifts is the one that misses the key. A match names the class only; the matching text is never echoed. If that file is unreachable (a loose install), the output says the screen is **UNAVAILABLE** rather than passing silently.

Exit **0** clean · **5** findings, each printed as `file:line` with the rule it broke · **2** usage. **Fix what it finds and re-run.** A finding you consciously leave — an unmarked command the operator insists on, a placeholder whose source is genuinely unknown — is **disclosed in the record's statement**, in words, naming the rule. A runbook delivered with a known lint finding and no disclosure is exactly the failure this gate exists to prevent.

Fixture: `bash plugins/notrest/skills/actionplan/scripts/fixture.sh` — exit 0 = every assertion held. It lints a canned good runbook, one canned runbook per way of breaking the laws above, and both honest degradations (shellcheck absent, chatroom's list unreachable).

## The runbook — `runbook/{topic}Runbook.md`

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

**Where this came from:** the `stepbystep` plan record it expands (`F-<n>`) · the environment profile gathered this session · `map.md`, if one was provided. This file is the deliverable; its record in the store points back here.

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

## The output — the record that tracks the runbook

**One `kind=result` record, written after the file, `relation=toward`.** Its job is to make the runbook findable and to say honestly what state it is in — a runbook with four open placeholders is not the same artifact as one that runs. The statement carries: what the runbook does, how many phases and destructive steps it holds, how many placeholders are still unfilled, and the environment it assumes. **The runbook's path is evidence** (`type=path`) — that is the link between the store and the deliverable, so it is never omitted and never paraphrased.

- **The lint result rides in the statement.** `runbook_lint.py` exited 0, or the statement names what it found and why that finding stands — the rule, the step, the reason. The lint runs *before* the record; a record written over an unlinted file is a claim nobody checked, and one written over a file whose findings were dropped is worse.
- `links` names the `stepbystep` decision record this expands (and its `[ONE-WAY]` findings, where they became ⛔ steps) — the chain from plan to commands should be walkable in one `track`.
- Verified command syntax rides as `[cited]` url evidence; a flag you could not confirm against the user's exact version rides as `[unverified]` and says so in the statement.
- If a later run rewrites the runbook for the same goal, `index.py supersede F-<old> --by F-<new>` — two live runbooks for one job is how the wrong one gets run.

### The snippet, filled

*(For the Postgres migration runbook above.)*

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/archivist/scripts/index.py" add --root . --json '{
  "session":"actionplan-2026-07-25",
  "skill":"actionplan",
  "kind":"result",
  "ask":"turn the Postgres migration plan into a copy-paste runbook",
  "statement":"Runbook written: 4 phases, 23 blocks, 2 destructive steps (both ⛔ with backup + restore paths), assumes Ubuntu 22.04 app host and managed PG 16. Three placeholders are still open — <APP_HOST>, <DB_HOST>, <DB_ADMIN> — so it is not runnable as-is; the values table says where to find each. The pg_dump --format=directory flag is verified against PG 16 docs; the systemd unit name is [unverified] and flagged in the file.",
  "evidence":[{"type":"path","ref":"runbook/migrate-app-database-to-postgresRunbook.md","label":"cited"},
              {"type":"url","ref":"https://www.postgresql.org/docs/16/app-pgdump.html","label":"cited"},
              {"type":"path","ref":"map.md","label":"cited"}],
  "relation":"toward",
  "links":["F-73"]}'
```

The `add` prints its `F-<n>`. A non-zero exit means the record was turned away with its rule named — fix it and re-run. The runbook file stands either way; the record is how anyone finds it.

## Self-check before finishing
Before declaring done, verify and fix any miss:
- **`runbook_lint.py` exited 0 on the delivered file** — or every finding it printed is disclosed in the record's statement with its rule. It mechanizes the items marked ✓ below (and the shell syntax of every block); run it rather than reading for them.
- **Records validated at the door (`add` exited 0)** — the id was printed by the script, nothing hand-appended, and the record's `path` evidence is the runbook's real relative path.
- Every command block is copy-paste runnable and in correct execution order.
- ✓ No invented hosts/paths/ports/credentials — all are real (from map.md/answers) or marked placeholders defined in the values table.
- ✓ Every destructive/irreversible step has a ⛔ warning and a backup/restore note; no secrets are hardcoded.
- ✓ Every step carries a "verify" check — and a rollback, or an explicit "no rollback" with the restore path.
- Offline constraints respected; artifacts needing pre-staging are flagged.
- Version/syntax-sensitive commands were verified or flagged to confirm.
- All open unknowns/assumptions are listed at the top.

## Finishing up

Write `runbook/{topic}Runbook.md` (the deliverable), run `scripts/runbook_lint.py` over it and fix what it finds, then emit the `kind=result` record that points at it — in that order, so the record describes a file that passed the gate. Give the user a short chat summary: what the runbook accomplishes, the environment it assumes, the most dangerous step to watch, any values they still need to fill, the path to the file, and the record id. Don't paste the runbook into chat. Offer to fill in placeholders once they share the missing details, or to expand any phase further — a rewritten runbook `supersede`s its old record rather than leaving two live.

## Notes on tone and rigor

- Pairs with `stepbystep` (run it first, then `/actionplan` on its decision record) and `director` (`stepbystep → actionplan`). Inside `director` or any non-interactive run, skip the Q&A and rely on `map.md` + labeled assumptions, listing unknowns up top.
- The runbook is executed by the user on their own machines — this skill writes it, it never runs commands.
- A placeholder the user fills in 10 seconds is safe; a guessed hostname that points at the wrong machine is not. Always prefer the placeholder.
- Lead each block with where to run it. The most common runbook failure is running the right command on the wrong host.
