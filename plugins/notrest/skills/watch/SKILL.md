---
name: watch
description: "Facts have shelf lives — watch re-verifies them on schedule: pulls the load-bearing [cited] claims out of a dossier (or inline) into watch/watchlist.md, then re-verifies the due ones with factcheck's rigor and appends a dated DRIFT REPORT to watch/drift-log.md — HOLDS / DRIFTED / DEAD-SOURCE / UNVERIFIABLE, with what was actually fetched stamped on every run. Use on /watch, \"watch this claim\", \"keep this fresh\", \"recheck weekly\", \"has anything changed since\", \"re-verify the dossier\"."
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

## Commands

| Invocation | What it does | Costs |
|---|---|---|
| `/watch add <dossier-path \| claims>` | triage the load-bearing `[cited]` claims into `watch/watchlist.md` | no searches — reading only |
| `/watch run [--all]` | re-verify every **due** claim now, append a dated DRIFT REPORT | ~2 searches/fetches per due claim |
| `/watch list` | print the watchlist and what is due, read-only | free |

There is no `--quick`. The log **is** the deliverable — a recheck that writes nothing is a
recheck nobody can audit next month. `/watch list` is the free, chat-only mode.

**Files** (created on first `add`, in the working directory):
- `watch/watchlist.md` — what is being watched. Rows are appended; only `Last checked` and
  `Status` are ever edited in place (the history of those edits lives in the drift log, so
  nothing is lost). **Never delete a row** — retire it by setting its cadence to `retired`.
- `watch/drift-log.md` — strictly append-only. One dated block per run, newest at the bottom.

## `/watch add` — building the watchlist

The subject is a dossier path (`factcheck/…Dossier.md`, `research/…Dossier.md`, any file with
cited claims), a natural ask ("watch the pricing claims in the market dossier"), or claims
pasted inline. If the dossier isn't in context, read it first.

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

**Due:** a row is due when `Last checked + cadence ≤ today`. Compute it from the table; check
only what is due (`--all` overrides). Rows with cadence `retired` are never due.
**Budget:** ~2 searches/fetches per due claim, ~15 per run. Spend the depth on the load-bearing
ones; if the budget runs out, stop and say which rows went unchecked — an unchecked row keeps
its old `Last checked` date. Never move a date you didn't earn.

For each due claim:
1. **Re-read the recorded source first.** Fetch the URL in the row. What does it say *now*?
2. **Then look for movement** — one search, aimed at whether the fact changed (a newer figure,
   a superseding standard, a retraction), not at re-confirming what you already believe.
3. **Verdict in factcheck's grammar**, then map it to the watch status:

| Re-verification verdict | Watch status | When |
|---|---|---|
| ✅ CONFIRMED | **HOLDS** ✅ | the source was re-read this run and still says it |
| 🔴 REFUTED · 🔵 MISLEADING-now · figure moved | **DRIFTED** 🔴 | contradicting evidence read this run |
| 🟡 PLAUSIBLE where it was CONFIRMED | **DRIFTED** 🔴 | soft drift — the support decayed; say which way |
| ⚪ UNVERIFIABLE — the source is gone (404, removed, paywalled, redirected to nothing) | **DEAD-SOURCE** ⚫ | the source died, the claim did not |
| ⚪ UNVERIFIABLE — source alive, answer no longer checkable there | **UNVERIFIABLE** ⚪ | scope/definition changed, page no longer reports it |

4. **Update the row** — `Last checked` = today, `Status` = the mapped status. Nothing else.
5. **Write the block** (below), then one COORD line:
   `- [YYYY-MM-DD HH:MMZ] [watch] recheck: N due -> X holds / Y drifted / Z dead | evidence: watch/drift-log.md <date>`

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
