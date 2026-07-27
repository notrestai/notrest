---
name: watch
description: "Facts have shelf lives — watch re-verifies them on schedule: pulls the load-bearing [cited] claims out of a dossier (or inline) into watch/watchlist.md, then re-verifies the due ones with factcheck's rigor and appends a dated DRIFT REPORT to watch/drift-log.md — HOLDS / DRIFTED / DEAD-SOURCE / UNVERIFIABLE, with what was actually fetched stamped on every run. Use on /watch, \"watch this claim\", \"keep this fresh\", \"recheck weekly\", \"has anything changed since\"."
---

# watch — facts have shelf lives

`factcheck` answers *is this true?* — as of the day it ran. Every dossier in the estate is a
snapshot with an expiry date nobody tracks: the pricing page changed, the standard was
superseded, "47 states" became 49, the primary source started 404ing. The project keeps
quoting the dossier anyway, because nothing ever told it not to.

**watch is factcheck's calendar-time sibling.** It keeps a short list of the claims this
project is actually *leaning on*, re-reads their sources on a cadence, and says loudly when
one has moved. Same rigor as the first verification, same verdict grammar — the only thing
that changed is the clock.

**What it is not:** a monitoring service (nothing runs unless a session or a scheduled task
runs it), an alerting system, or a re-run of the whole dossier. It watches ~10 claims per
dossier and hands the full re-run to `/factcheck` when one breaks.

**Router shape:** `recheck`

## Commands

| Invocation | What it does | Costs |
|---|---|---|
| `/watch add --from-findings` | build rows straight from the findings store — the factcheck→watch handoff, one command | free — zero model tokens |
| `/watch add <dossier-path \| claims>` | triage the load-bearing `[cited]` claims into `watch/watchlist.md` | no searches — reading only |
| `/watch run [--all]` | re-verify every **due** claim now, append a dated DRIFT REPORT | ~2 searches/fetches per due claim |
| `/watch list` | print the watchlist and what is due, read-only | free |

There is no `--quick`. The log **is** the deliverable — a recheck that writes nothing is a
recheck nobody can audit next month. `/watch list` is the free, chat-only mode.

## The script does the clock, the fetch, and the write

`scripts/watch.py` (python3, stdlib only) owns every part of the cycle that never needed a
model. **Run it; don't re-improvise it.**

| Call | Does | Exit |
|---|---|---|
| `watch.py add --from-findings --root .` | builds one row per watchable record in the findings store; idempotent | 0 (a re-run appends nothing) |
| `watch.py due --root .` | parses the table, computes what the cadence has made due | **3** = something is due · 0 = nothing (a hook can branch on this) |
| `watch.py probe <ID> --root .` | HEAD, then a conditional GET of that row's source; sha256 of the body against the row's stored `Hash` cell | **0** UNCHANGED · **3** CHANGED (body path printed) · **4** DEAD-SOURCE |
| `watch.py append --json <file> --root .` | writes the dated block and updates Last checked/Status/Hash | 0 written · **5** refused (see below) |

**What this buys:** two of the three outcomes cost zero model tokens. A source that 404s,
times out, or DNS-fails resolves to DEAD-SOURCE without a model reading anything; a page
whose bytes are identical to last run resolves to UNCHANGED the same way. **The model is
spent only on exit 3** — a page that genuinely moved — where it reads the body file the
probe wrote and decides whether the *claim* moved with it. That is the judgment call; the
rest is arithmetic and HTTP.

**Conditional on a strong `ETag` only.** `probe` never sends `If-Modified-Since`: HTTP
dates are second-granular, so a page edited within the same second as the last check
answers `304 Not Modified` while its bytes have moved — the one failure mode a watch
must not have. A weak `ETag` (`W/"…"`) promises only semantic equivalence and is refused
for the same reason. The saving was bandwidth; the cost would have been findings.

The `Hash` column is added automatically to a watchlist that predates it (one cell per
row, existing rows untouched otherwise). A **CHANGED** probe deliberately does *not*
overwrite the stored hash — retiring the drift before a model judged it would make the
next run report UNCHANGED and lose the finding. `append` banks the new hash for the rows
it records, because that is the moment the verdict exists. Validators (`ETag` /
`Last-Modified`) are cached in `watch/.probe-cache.json` — derived, machine-written,
safe to delete.

`append` **refuses (exit 5)** rather than write a block that lies: a `HOLDS` whose URL is
not on the `Fetched this run:` line, a `DRIFTED` with no contradicting evidence, a status
outside the four-word grammar, or a due count the findings do not account for. The
`**Result:**` counts are computed from the findings, so they cannot disagree with the
one-liners beneath them. Both files are prepared in full before either lands, and each
lands by rename — a reader never sees a half-written log, and re-running the same append
is a no-op instead of a duplicate block.

Fixture: `bash plugins/notrest/skills/watch/scripts/fixture.sh` — exit 0 = every assertion
held. It runs the probe paths against a real local HTTP server (ephemeral port, no
network), so 404, unchanged, and changed are exercised as HTTP rather than mocked; and it
seeds a real findings store to prove `add --from-findings` appends the watchable records
once, leaves the rest off by name, and appends nothing on a second run.

**Files** (created on first `add`, in the working directory):
- `watch/watchlist.md` — what is being watched. Rows are appended; only `Last checked` and
  `Status` are ever edited in place (the history of those edits lives in the drift log, so
  nothing is lost). **Never delete a row** — retire it by setting its cadence to `retired`.
- `watch/drift-log.md` — strictly append-only. One dated block per run, newest at the bottom.

## `/watch add` — building the watchlist

The subject is a **findings-store id** (`F-12` — the archivist's `archive/findings.jsonl`
record, and the direction this estate is heading), a dossier path (`factcheck/…Dossier.md`,
any file with cited claims — legacy, still fully supported), a natural ask ("watch the
pricing claims in the market dossier"), or claims pasted inline. If the dossier isn't in
context, read it first.

**Findings-store rows** put `F-<id>` in the `Source` cell (or name it in the `##` section
heading) instead of a URL, and `watch.py` resolves it through
`archivist/scripts/index.py track --json`: the record's `url` evidence refs are what gets
fetched, so the watchlist stops carrying a second copy of a URL the store already owns.
A record with no `url` evidence cannot be watched, and the script says so by name rather
than silently skipping the row; a record the store no longer calls live (superseded,
refuted) is still probed, but the resolution line says which, because watching a retired
finding is a fact the reader needs. An id with no record fails loudly (exit 2) — never as
a quiet pass.

### The factcheck→watch handoff — one command

`factcheck` (and `researcher`, and `decider`) already wrote what they found into the store.
Re-typing those claims into a table is transcription, not judgment, so it is a script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/watch/scripts/watch.py" add --from-findings --root .
```

It reads the store through `archivist/scripts/index.py track --json` — the same reader `due`
and `probe` use, so the resolution law (the tombstone link-walk) lives in exactly one place —
and appends one row per **watchable** record under a dated `## findings store` section.

**Watchable** is the watch law, not a preference. A record becomes a row only when it is
(a) **effectively live** — a superseded or refuted record is not a claim this project is
leaning on; (b) `kind=finding` or `kind=result` — a `decision` is a call, not a fact with a
source, and a `conflict`/`backtrack`/`side-route` is a note about the work; and (c) carrying
**≥1 evidence of `type=url` with `label=cited`** — the re-readable source rule from step 3
below, enforced instead of remembered. A `supersedes`/`refutes` tombstone is skipped even
though it satisfies (a)–(c): a status flip is bookkeeping about the store, not a claim about
the world. **Nothing is dropped silently** — every record left off prints a `LEFT` line
saying which rule it failed, which is the same law as "list what you left off" below.

| Cell | Comes from |
|---|---|
| `ID` | the next free `W<n>` — ids are never reused, and existing rows are never touched |
| `Claim (verbatim)` | the record's `statement`, verbatim (`\|` escaped as `&#124;`) — never a paraphrase |
| `Source` | `F-<id>`, **not** the URL — the store owns the URL, the row points at the record |
| `Tier` | `-`. The store has no source-tier field; an invented `T1` would be a fact nobody checked |
| `First verified` · `Last checked` | the record's own `ts` date — the day the finding was written, never today |
| `Status` | `HOLDS`, as the honest carry-over of the record's `[cited]` label — **not** a fresh verification. The first `/watch run` is what earns the next status |
| `Cadence` | by how many `[cited]` urls the record carries: 1 → `weekly`, 2 → `monthly`, 3+ → `quarterly` (corroboration buys time). `--cadence <c>` pins one for the whole run |

**Idempotent.** A record any row already names — in its `Source` cell or its `##` subject —
is skipped, so re-running after each factcheck adds only what is new and never a duplicate
row. The summary line reports appended / already watched / left off against the record count
it read, so the arithmetic is visible: `2 row(s) appended, 1 already watched, 4 left off
(of 7 records)`. Then `watch.py due --root .` treats the new rows exactly like any other.

The steps below are the **manual** path — a dossier, an inline paste, or a record the script
left off that you have decided to watch anyway.

1. **Extract verbatim.** Pull each candidate claim exactly as written — same rule as factcheck
   Pass 1. A paraphrase you wrote is not the claim the project is leaning on.
2. **Triage by load, cap at ~10 per dossier.** Which claims does the dossier's conclusion rest
   on? Those get watched. Ten claims rechecked properly beat forty rechecked thin — and the
   cap is what keeps a recheck cycle affordable enough to actually happen. List what you left
   off; never drop it silently.
3. **A watch needs a re-readable source.** Every row carries a URL that can be fetched again.
   A claim whose evidence was `[recall]`, a private dataset, a paywalled PDF, or "a colleague
   said" **cannot be watched** — say so and leave it off the list rather than adding a row
   that can never be checked. (Suggest `/factcheck` to source it first.)
4. **Carry the original dates.** `First verified` is the date the *dossier* verified it — not
   today. `Tier` is the source tier the dossier assigned (T1 primary / T2 reputable secondary
   / T3 restatement). On `add`, `Last checked` = `First verified` and `Status` = the honest
   carry-over: `HOLDS` only if the dossier confirmed it; otherwise `UNVERIFIABLE`.
5. **Pick a cadence per claim**, don't blanket-apply one: prices and rankings drift weekly,
   standards and statutes quarterly. Default `weekly` when the user has no preference.

### `watch/watchlist.md` — the format (this is the contract)

```markdown
# watchlist — facts under watch
> Rows are APPENDED. Only `Last checked` and `Status` are edited in place, by `/watch run`.
> Never delete a row — retire it by setting Cadence to `retired`. IDs are never reused.
> Cap: ~10 load-bearing claims per source dossier.
> Status: HOLDS · DRIFTED · DEAD-SOURCE · UNVERIFIABLE.
> Cadence: weekly · monthly · quarterly · on-demand · retired.
> A `|` inside a claim is escaped as `&#124;` so the row still parses.

## factcheck/gpu-pricing-2026Dossier.md · added 2026-07-24
| ID | Claim (verbatim) | Source | Tier | First verified | Last checked | Status | Cadence |
|----|------------------|--------|------|----------------|--------------|--------|---------|
| W1 | "An H100 80GB PCIe rents for $2.49/hr on-demand." | https://example.com/pricing | T1 | 2026-05-02 | 2026-07-24 | HOLDS | weekly |
| W2 | "Eight US states now require the disclosure." | https://example.gov/registry | T1 | 2026-05-02 | 2026-07-24 | DRIFTED | monthly |
| W3 | "The spec has been stable since v2." | https://example.org/changelog | T1 | 2026-05-02 | 2026-07-24 | HOLDS | quarterly |

## inline — vendor SLA claims · added 2026-07-24
| ID | Claim (verbatim) | Source | Tier | First verified | Last checked | Status | Cadence |
|----|------------------|--------|------|----------------|--------------|--------|---------|
| W4 | "Support is 24/5 &#124; 24/7 on Enterprise." | https://example.net/sla | T2 | 2026-07-24 | 2026-07-24 | HOLDS | weekly |
| W5 | "The 2024 uptime report showed 99.99%." | https://example.net/uptime-2024 | T1 | 2026-06-01 | 2026-07-24 | DEAD-SOURCE | retired |
```

One `##` section per source dossier (or `## inline — <topic>` for pasted claims), with the date
it was added. Claims stay in double quotes, verbatim.

## `/watch run` — the recheck cycle

Runs **now**, in this session. It is the same work factcheck does, scoped to one claim each.

**Due:** `watch.py due --root .` — it computes `Last checked + cadence ≤ today` from the table
so nobody does date arithmetic by eye. Check only what is due (`--all` overrides). Rows with
cadence `retired` are never due.
**Budget:** ~2 searches/fetches per due claim, ~15 per run. Spend the depth on the load-bearing
ones; if the budget runs out, stop and say which rows went unchecked — an unchecked row keeps
its old `Last checked` date. Never move a date you didn't earn.

For each due claim:
1. **Re-read the recorded source first** — `watch.py probe <ID>`. Exit 4 is DEAD-SOURCE and
   exit 0 is UNCHANGED: both are already resolved, and reading the page yourself adds nothing.
   Only on exit 3 do you open the body file it wrote and ask what the source says *now*.
2. **Then look for movement** — one search, aimed at whether the fact changed (a newer figure,
   a superseding standard, a retraction), not at re-confirming what you already believe. Skip
   it for a row the probe resolved UNCHANGED; spend it where the bytes moved.
3. **Verdict in factcheck's grammar**, then map it to the watch status:

| Re-verification verdict | Watch status | When |
|---|---|---|
| ✅ CONFIRMED | **HOLDS** ✅ | the source was re-read this run and still says it |
| 🔴 REFUTED · 🔵 MISLEADING-now · figure moved | **DRIFTED** 🔴 | contradicting evidence read this run |
| 🟡 PLAUSIBLE where it was CONFIRMED | **DRIFTED** 🔴 | soft drift — the support decayed; say which way |
| ⚪ UNVERIFIABLE — the source is gone (404, removed, paywalled, redirected to nothing) | **DEAD-SOURCE** ⚫ | the source died, the claim did not |
| ⚪ UNVERIFIABLE — source alive, answer no longer checkable there | **UNVERIFIABLE** ⚪ | scope/definition changed, page no longer reports it |

4. **Update the row and write the block in one call** — hand `watch.py append` the findings
   as JSON (`{"date","due","searches","findings":[{"id","status","note","url","http","hash",
   "chain"}],"not_due","unchecked"}`) and it renders the block, sets `Last checked` = today
   and `Status` = the mapped status on exactly those rows, and prints the COORD line for you
   to bank:
   `- [YYYY-MM-DD HH:MMZ] [watch] recheck: N due -> X holds / Y drifted / Z dead | evidence: watch/drift-log.md <date>`
   Hand-writing either file is how the counts drift out of step with the one-liners — the
   script exists so that cannot happen.

**Drift is never smoothed.** A drifted load-bearing claim goes at the top of the report, in the
chat summary, and carries its chain suggestion. "Mostly unchanged" is not a finding — name the
one that moved.

### `watch/drift-log.md` — the format (this is the contract)

```markdown
# drift-log — dated recheck cycles
> Append-only, newest block at the bottom. Written by `/watch run` only.

## 2026-07-24 — recheck cycle
**Result:** 2 HOLDS · 1 DRIFTED · 0 DEAD-SOURCE · 0 UNVERIFIABLE (of 3 due)
**Fetched this run:** https://example.gov/registry (200) · https://example.com/pricing (200) · https://example.org/changelog (200) · 1 search
- 🔴 DRIFTED — W2 "Eight US states now require the disclosure." — the registry now lists
  eleven states (accessed 2026-07-24) [cited: https://example.gov/registry] → the dossier's
  count is stale: run `/factcheck` on it, or `/researcher` if the question itself reopened.
- ✅ HOLDS — W1 "An H100 80GB PCIe rents for $2.49/hr on-demand." — pricing page re-read
  2026-07-24, figure unchanged [cited: https://example.com/pricing]
- ✅ HOLDS — W3 "The spec has been stable since v2." — changelog re-read 2026-07-24, no new
  release [cited: https://example.org/changelog]
**Not due:** W4 (next due 2026-07-31) · W5 (retired)
```

Rules for the block: the `**Result:**` counts must equal the actual one-liners below it and sum
to the "of N due" figure; the `**Fetched this run:**` line names **every URL actually retrieved**
(with its status) plus the search count — that line is the honesty stamp, and a claim whose URL
is not on it may not be reported as HOLDS; DRIFTED lines lead the block and carry a chain
suggestion; DEAD-SOURCE lines say plainly that the claim is *not* refuted.

## Scheduling the recheck (owner-confirmed, always)

A cadence nobody runs is a wish. When a scheduled-tasks MCP is available, offer to run the
cycle automatically — **offer**, then wait for a yes.

**Probe at runtime, don't assume.** The tools are usually deferred: `ToolSearch` with
`select:mcp__scheduled-tasks__list_scheduled_tasks,mcp__scheduled-tasks__create_scheduled_task,mcp__scheduled-tasks__update_scheduled_task,mcp__scheduled-tasks__delete_scheduled_task`
(or the keyword query `scheduled task`). If nothing loads, the MCP is absent.

**When present:**
1. `list_scheduled_tasks` first — a watch task for this repo may already exist. Never create a
   duplicate; update the existing one instead.
2. Propose it in one line and get an explicit yes: *"Schedule `/watch run` for this repo every
   Monday 9am (task id `watch-<repo>`)? I won't create it until you say so."*
3. Create it with a **fully self-contained prompt** — a scheduled run starts with no memory of
   this conversation, so the repo path and the whole job go in the prompt:

   ```
   cd /abs/path/to/repo and run the ORACLE watch skill's recheck cycle for this repo:
   re-verify every claim in watch/watchlist.md whose cadence is due, append a dated block
   to watch/drift-log.md, update each checked row's Last checked + Status, and append one
   COORD.md line. Budget ~2 searches per claim. If any claim DRIFTED, put it at the top of
   the report and name it. Do not create, update, or delete any scheduled task in this run.
   ```
   Cadence → cron (5-field, **local** time): weekly `0 9 * * 1` · monthly `0 9 1 * *` ·
   quarterly `0 9 1 1,4,7,10 *` · on-demand → no schedule. Use the *shortest* cadence on the
   watchlist so nothing is checked late.
4. Tell the user the honest limitation once: scheduled tasks run while the app is open; if it
   was closed when the task was due, it runs at next launch — so "weekly" means "weekly, when
   the machine is on".
5. **Creating, updating, deleting, or disabling a schedule is always owner-confirmed** — one
   explicit yes per action, never inferred from "set up a watch", never done as a side effect
   of a `/watch run`. Deleting is `delete_scheduled_task`; pausing is `update_scheduled_task
   enabled:false` — offer the pause first, it's reversible.

**When absent:** say it in one line — *"No scheduled-tasks MCP here, so nothing will run on its
own; `/watch run` when you want the cycle, and the watchlist tracks what's due."* — and carry
on. Never write a fake schedule, never claim a task exists, never imply a background process is
running. Watch works perfectly well as a manual ritual; the schedule is a convenience.

## Honesty rules

- **Re-verification is verification.** Same rigor, same grammar, same tiers. A recheck is not a
  glance at the headline you remember.
- **A failed fetch is DEAD-SOURCE, never DRIFTED or REFUTED.** A 404, a timeout, a paywall, or
  a robots block is a fact about the *source*, not about the claim. Absence of evidence is not
  contradiction — that is factcheck's rule, and it is the rule this skill breaks most easily.
- **"Unchanged" requires the source actually re-read.** If you did not retrieve it this run,
  the row does not get today's date and the block does not say HOLDS. Say "not checked".
- **Every run stamps what it fetched.** URLs, statuses, search count. An unstamped run is
  unauditable, which makes it worthless three months from now.
- **Drift is announced, never smoothed.** No "minor update to" — the number was 8, it is 11.
- **Verdicts attach to claims, not people**, and the watchlist judges the *claim*, not the
  dossier's author.
- **Never rewrite the drift log.** A wrong entry is corrected by the next block naming it, the
  way `spend` corrects with a new line. History stays.
- **The watchlist is not a source.** Cite the source URL, never the row — the row is a pointer
  with a date on it, same as archivist's index.

## Self-check before finishing

- Every watched row has a re-readable source URL and a verbatim claim; unwatchable claims were
  named, not silently dropped.
- The cycle went through `watch.py` — `due` for the calendar, `probe` per row, `append` for
  the write. A block composed by hand is a block whose counts nothing checked.
- Every claim reported HOLDS was actually fetched this run, and its URL is on the
  `**Fetched this run:**` line.
- Every DRIFTED verdict has contradicting evidence read this run — not a failed fetch.
- Every DEAD-SOURCE line says the claim is not refuted.
- The `**Result:**` counts match the one-liners and the due count; rows not checked kept their
  old `Last checked` date.
- The block is appended (nothing above it was edited), and one COORD line landed.
- Any schedule created/updated/deleted this session had an explicit yes; if the MCP was absent,
  that was stated once and nothing was faked.

## Finishing up

Give the user the headline in chat — *N due, X held, Y drifted*, the drifted ones by name — plus
the two paths. Don't paste the files.

Chains:
- **`/factcheck` → `/watch`** (inbound) — the handoff is a command, not a retyping job:
  `watch.py add --from-findings` turns the session's live `[cited]` records into rows and
  names what it left off. Run it at the end of a factcheck instead of dictating a table.
- **`/factcheck`** — a DRIFTED load-bearing claim means the dossier's conclusion is standing on
  a stale number. Watch checks one claim; factcheck re-runs the whole verdict set.
- **`/researcher`** — when what drifted isn't a figure but the answer (the recommended tool was
  deprecated, the market moved), the question itself has reopened.
- **`/recap`** — `watch/drift-log.md` is trail material: dated blocks in timestamp order, which
  a recap walks alongside COORD and git to show when the project's facts moved under it.
- **`/sessionend`** — due watches belong in the handoff, so the next session inherits the
  calendar and not just the conclusions.
- **`/archivist`** — its honesty rule ("a hit is not still true") is exactly the gap this skill
  fills: index a dossier, then watch the claims in it that would hurt to get wrong.
