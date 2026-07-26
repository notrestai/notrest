---
name: doctor
description: "The harness's own self-check — one read-only pass reporting PASS/WARN/FAIL per check with the exact fix: front-matter YAML would reject (the unquoted colon-space that makes a skill invisible), manifest + tombstone pins, skill-count drift, hooks that parse and hooks that ever fired, estate integrity, which build is really running, the always-on token budget, gitignore rules that swallow skill dirs, stale version stamps. Use on \"/doctor\", \"health check\", \"check the install\", \"why isn't X triggering\", after any release. Reads only."
---

# doctor — the harness's self-check

```bash
python3 plugins/notrest/skills/doctor/scripts/doctor.py check --root .
```

That is the whole skill. Ten named checks, one line each, a fix command on every WARN and
FAIL, one summary line at the end. `--root` defaults to the git root of the cwd, so bare
`doctor.py check` works from anywhere inside the repo. Add `--json` for machine output.

**Router shape:** `health-check` — the UserPromptSubmit router (`hooks/router.sh`) nudges a
prompt here when it looks like *"health check"*, *"is the harness healthy"*, or *"check the
install"* — including the *"why isn't X triggering"* case, which is almost always an install
fact. *"check the laws"* is a different shape and goes to `/eval`.

Point it at what a session is actually *running* instead of the repo it edits — only
needed in cache mode, since a skills-dir install runs the repo itself:

```bash
python3 .../doctor.py check --plugin ~/.claude/plugins/cache/notrest/notrest/3.1.0
```

## Exit codes

| exit | meaning |
|---|---|
| 0 | every applicable check passed |
| 5 | warnings only — drift worth knowing, nothing broken |
| 6 | at least one FAIL — something in the harness is lying or dead |
| 3 | the target is unusable (no plugin there) |
| 2 | usage error |

A check whose inputs are absent reports **SKIP** and does not colour the exit code — a plugin
cache dir legitimately has no `marketplace.json`, no `docs/`, no estate.

## What each check guards — and the defect it descends from

Every check here is a scar. None of them were invented.

| check | guards | origin |
|---|---|---|
| **FRONTMATTER** | every `plugins/*/skills/*/SKILL.md` parses; `name` present, `description` non-empty; unquoted scalars carrying `": "`, a run-on `" #"`, or unbalanced quotes | **dead YAML metadata, 2026-07-25.** Three skills — recap, oracle, agentswarm — had descriptions whose plain scalar contained a colon-space. YAML reads that as a nested mapping, the front-matter fails to load, and the skill goes *invisible to the model while the file sits on disk*. Nothing errors. Nothing logs. The skill simply stops existing. Fix: quote the scalar. |
| **MANIFESTS** | `plugin.json` + `marketplace.json` are valid JSON, their three versions agree, and the `oracle-suite` tombstone is pinned at exactly `9.0.0` | the rename left a migration stub whose only job is telling old installs where the harness went. Bump it and you re-offer a dead plugin id to every existing install. |
| **SKILL COUNT** | the number of skill dirs on disk against the count spelled in `docs/TUTORIAL.md`, the inner `README.md`, and both manifest descriptions | the count is *prose in four places*. Every skill that lands drifts it, and a marketplace description that undercounts is the first thing a stranger reads. |
| **HOOKS** | `hooks.json` is valid, every `$CLAUDE_PLUGIN_ROOT` script exists and clears `bash -n`, and the SessionStart echo announces the current plugin name | **rename residue + the glob false-fire.** A hook that will not parse fails *silently* at session start — the discipline anchor just never appears. And `COORD-*.md` once matched the machine-written ledgers (`COORD-AGENTS.md`, `COORD-ARCHIVE.md`), so a lane-blackboard nudge false-fired in every repo. Hook bugs are invisible by construction; this check is the only thing that looks. |
| **HOOKS FIRED** | whether anything has *actually run*: a `[hook]`-tagged line in the active COORD volume's last 200 lines, or a `COORD-AGENTS.md` + `spend/ledger.md` pair both written inside 48h | **HOOKS proves the scripts parse; nothing proved one ever ran.** A hook that is wired, valid and never fires leaves no error, no log and no gap anyone notices — a shadowed plugin, for instance, runs no hooks at all while `hooks.json` stays perfect. This is a **liveness heuristic and never FAILs**: a fresh repo and a quiet weekend look identical to a dead hook, so it reports WARN and says which evidence it looked for. |
| **ESTATE** | `COORD.md` header + parseable ledger lines, the `COORD-AGENTS.md` machine header, `spend/ledger.md` through `spend.py report`, `compile/candidates.json` as valid JSON | recap, compile and graph all *parse* these files. A damaged header does not break the file — it breaks every reader downstream, quietly. `spend.py report` exiting **4** is not a doctor failure: it is the routing gate firing correctly, reported as WARN with the verdict. |
| **INSTALL FRESHNESS** | *which build the session is really running*, in the vocabulary of the mode it is in — see below | **the stale marketplace clone, 2026-07-15**, and **the mislabelled surface, 2026-07-25.** First the session ran a build two versions behind the repo it was editing and nothing said so. Then the machine moved to an in-place install and the check *kept using cache vocabulary* — reporting a "marketplace clone" version it had never read. A check that names the wrong surface is worse than a silent one: it is confidently wrong. |
| **TOKEN BUDGET** | the always-on context cost the CLI reports for this plugin, against a ceiling of **3600 tok** | every skill description is loaded into **every** session whether the skill fires or not, so the harness taxes work it never does. The number is read from `claude plugin details` — the CLI's figure, never doctor's estimate — and the check SKIPs honestly when no CLI or no id will answer, rather than guessing. |
| **GITIGNORE** | `/graph/` and `/compile/` present *and anchored*, and the skills' own `graph/` and `compile/` dirs not ignored | **the unanchored gitignore, v2.16.0.** `graph/` without the leading slash matches at *any* depth — it un-tracked `plugins/notrest/skills/graph/`, so the shipped plugin was missing a skill and `git status` stayed clean about it. |
| **RENDER SURFACES** | the version stamps in `docs/oracle-skill-flow.html` match `plugin.json` | a rendered doc is a shipped surface. A stale stamp ships a lie to whoever opens it. |

## INSTALL FRESHNESS — two worlds, two vocabularies

A plugin reaches a session by one of two routes, and the honest question is different in
each. doctor detects which one this machine is in before it says a word.

**skills-dir (in place).** A symlink under `<config>/skills/` points at a plugin directory
and the CLI loads *that directory* — no clone, no cache copy, no version to be behind.
The running build is whatever is on disk **right now**, so the question stops being "is the
install current" and becomes "does anyone else see what this session is running":

```
runtime=skills-dir(in-place) · tree=v3.7.0 · HEAD=v3.7.0
```

It WARNs on exactly three things, each with its own remedy: the tree is bumped but
**uncommitted** (live here, nonexistent everywhere else — commit it); the link resolves to
**some other tree** (nothing checked here is what runs — repoint it); or an installed
plugin holds the same name and **shadows** the link (`claude plugin list` shows it as *not
loaded* — uninstall the copy that took the name). `$CLAUDE_CONFIG_DIR` is honoured, so the
detection follows a relocated config.

**marketplace-cache.** A published version was copied into `~/.claude/plugins/cache/`. Here
the original question stands: repo vs clone vs `installed_plugins.json`, and drift WARNs
with the update command. The hook's git self-update silently no-ops on a cache install, so
this check is the only thing that says so.

If neither surface exists, doctor SKIPs and says nothing on this machine claims to run the
plugin — it never falls back to reading git state and calling it an install.

## Boundary — doctor reads, doctor never repairs

No writes. No bumps. No commits. No `git` mutation of any kind. Doctor's whole contract is
*observation plus the exact command that fixes what it saw* — the owner or the seat runs it.
This is deliberate: a self-check that repairs itself can hide a defect by fixing it before
anyone learns the defect class exists, and every scar in the table above is worth knowing.

When a FAIL lands, the fix line is copy-paste ready. When something is genuinely ambiguous
(no count stated anywhere, an undeterminable ignore status) doctor says WARN and states what
it could not determine, rather than guessing.

## When to run it

- **After every release** — before telling anyone it shipped. `INSTALL FRESHNESS` is the check
  that would have caught 2026-07-15 on the day.
- **When a skill stops triggering** — `FRONTMATTER` finds a dead description in one pass; the
  alternative is staring at a file that looks fine.
- **At `/sessionend`**, alongside the spend report, so the estate is proven intact before the
  session that knows the context disappears.
- **Against the installed cache dir** when a session's behaviour disagrees with the repo.

## The pulse — the estate's heartbeat in one command

`scripts/pulse.sh [--root .]` is every read-only instrument in the suite, run back to back
by something that is not a model. It calls `doctor.py check`, `eval.py check`, `watch.py due`,
`compile.py report` and `spend.py report`, then `graph.py river --no-open` and `graph.py scan`
(both guarded by existence — a repo without the graph skill still has a heartbeat), and banks
**one** line to `COORD.md`:

```
- [2026-07-26 23:05Z] [pulse] estate pulse -> doctor=5 eval=0 watch-due=2 compile=ripe spend=CLEAN river=findings+coord | evidence: pulse.sh
```

That append is the only thing pulse writes. It goes in under the same exclusive lock the
SessionEnd hook uses, and an identical line already in the file is a no-op, so a pulse is safe
to re-run and two racing pulses land two lines rather than one torn one.

**Exit 0 = green, exit 1 = something wants a human** — the whole point, because a scheduler can
only alert on a number. The colour is decided by **health** (doctor, eval, spend, graph); the
two instruments that use a non-zero exit as a *signal* rather than a fault — `watch.py due`
exit 3 (something is due) and `compile.py report` exit 3 (candidates are ripe) — are carried on
the line as **data**, not as alarms. An estate with a due watch and eleven ripe candidates is
the system working; wiring that to the siren would make the heartbeat permanently red, and an
alarm that is always on is an alarm nobody reads. `--strict` restores the literal reading (any
non-zero exits 1) for a caller who wants the unnuanced gate.

Silent-fail-open, like the hooks: no `set -e`, a missing instrument prints `-` instead of a
stack trace, and pulse's own plumbing never raises the alarm.

Fixture: `bash plugins/notrest/skills/doctor/scripts/pulse-fixture.sh` — exit 0 = every
assertion held.

### Scheduling it is the owner's click, never the harness's

pulse is what you would point a scheduler at — and **the harness never schedules itself.**
Creating, updating, pausing, or deleting a scheduled task is an owner-confirmed action, one
explicit yes per action, exactly as `watch` requires for its recheck cycle: *offer*, then wait.
Never write a fake schedule, never claim a task exists, and never imply something is running in
the background. A cron line the owner did not approve is a background process nobody consented
to. Run it by hand until the owner says otherwise — `bash pulse.sh --root .` is the whole ritual.

## Proving it

```bash
bash plugins/notrest/skills/doctor/scripts/fixture.sh   # exit 0 = every assertion held
```

The fixture builds a synthetic harness in a scratch dir, asserts it comes back clean at exit
0, then injects each defect class in turn — unquoted colon-space description, version
mismatch, tombstone bump, broken hook syntax, count drift, unanchored gitignore, stale render
stamp, damaged COORD header, broken `candidates.json`, an over-budget always-on cost — and
asserts each one flips **exactly** its own named check to FAIL at exit 6, with every other
check still passing. A health checker that cries wolf is worse than none, so precision is
asserted, not just detection.

The WARN classes get the same treatment at exit 5 (nothing failing, exactly one check
warning): an in-place link into a **foreign** tree, an in-place link **shadowed** by an
installed plugin, an **uncommitted release** under an in-place link — that one stands up a
throwaway git repo, commits v1.0.0 and bumps the whole release in the working tree, so
tree-vs-HEAD is the only disagreement left — and a **quiet estate** with no sign a hook ever
fired. The clean in-place run is asserted too, including that it never labels itself a cache
install: the mislabel is the defect this rewrite descends from.

Two of these checks read the machine rather than the repo, so the fixture hands them a
machine of its own: `$CLAUDE_CONFIG_DIR` is redirected at a scratch config tree (so INSTALL
FRESHNESS sees only the links the fixture planted) and a `claude` shim goes on PATH ahead of
the real CLI (so TOKEN BUDGET reads a figure the fixture chose). No network, no real
install, no dependence on what this laptop happens to have. The estate is stamped with the
current time rather than a frozen date — a fixture that starts failing on its own two days
after it was written is the worst possible property in a health checker's health checker.

## Companion utilities

Two small seat tools ship beside the checker (both `bash -n` clean, typed exits):

- `scripts/render-check.sh <file.html>` — serves the file on a free 127.0.0.1 port (8790-8799),
  proves HTTP 200, prints the URL to open, and reaps with `--close <port>`. The render gate,
  as one command instead of five.
- `scripts/gategrep.sh <file> <phrase> [expected]` — counts a phrase after normalizing
  whitespace, so a phrase wrapped across markdown lines still matches. A naive `grep -F`
  returns a false zero on wrapped text; this is the fix.
- `scripts/seat-tax-fixture.sh` — the contract test for both, plus the hook's auto-receipt.
- `scripts/coord-volume-fixture.sh` — the contract test for the COORD volume law (seal at 500,
  never compact) enforced by the SessionEnd hook.
