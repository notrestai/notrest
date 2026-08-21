---
name: doctor
description: "The harness's own self-check — one read-only pass, PASS/WARN/FAIL per check with the exact fix: front-matter YAML would reject, manifest + tombstone pins, skill-count drift, hooks that parse and ever fired, estate integrity, which build is really running, the always-on token budget, gitignore rules that swallow skills, stale stamps. Use on \"/doctor\", \"health check\", \"check the install\", \"why isn't X triggering\". Reads only."
---

# doctor — the harness's self-check

**Runtime adapter.** Run `doctor.py check --surface auto`; use `--surface codex` or
`--surface claude` for a deliberate arm. Codex mode validates the native
`.codex-plugin/plugin.json`, repo-local `.agents/plugins/marketplace.json`, and Codex's
installed inventory. Claude hook liveness, app-side shadows, and Claude token receipts are
SKIP on Codex—not PASS—because Codex v4.3 does not expose those surfaces. Resolve
`<plugin-root>` from this selected `SKILL.md`; never execute a literal placeholder.

```bash
python3 <plugin-root>/skills/doctor/scripts/doctor.py check --surface auto --root .
```

That is the whole skill. Eleven named checks, one line each, a fix command on every WARN and
FAIL — each naming **which rung of its ladder failed**, because a status says something is
wrong and only the rung says which remedy is the right one — and one summary line at the end. `--root` defaults to the git root of the cwd, so bare
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
| **INSTALL FRESHNESS** | *which build the session is really running*, in the vocabulary of the mode it is in — plus any installed plugin whose **skill names** overlap ours, whatever that plugin calls itself — see below | **the stale marketplace clone, 2026-07-15**, and **the mislabelled surface, 2026-07-25.** First the session ran a build two versions behind the repo it was editing and nothing said so. Then the machine moved to an in-place install and the check *kept using cache vocabulary* — reporting a "marketplace clone" version it had never read. A check that names the wrong surface is worse than a silent one: it is confidently wrong. |
| **SHADOW-APPSIDE** | every pack in the **desktop app's own provisioning store**, intersected against this tree's skill names — the pack, its version, its path, the colliding verbs, and whether it registers hooks | **the app-side ghost, found 2026-07-26.** A stale clone of this very plugin (`oracle-suite` v2.13.0, **19** name collisions, four live hooks) sat in the desktop app's store and served agent-mode sessions for a week while every CLI-side check reported healthy — because every other surface doctor reads belongs to the *CLI*, and this store belongs to the *app*. Four shadow incidents paid for it. **WARN-grade, never FAIL:** it reports another application's state, which this repo does not control. |
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

**A shadow does not have to wear your name.** The original shadow test asked one name-keyed
question — *is anything installed as `notrest`?* — and that question is blind to half the
cases, because what a session actually resolves is the **verb**, not the plugin name. Two
plugins shipping `skills/oracle/` collide whether or not their manifests ever agree. So the
check also reads every installed plugin's own `skills/` directory and reports any whose names
overlap this tree's:

```
SHADOW CANDIDATE (by verbs, not by name) — otherplug@elsewhere v7.0.0 carries 3 of this
tree's 30 verbs: draft, oracle, recap
```

That is a **WARN with the count**, never a FAIL: an overlapping install may be entirely
wanted. What is not acceptable is not knowing it is there.

## The two ladders — a fix that names the rung it bottomed out at

A status tells you something is wrong. It does not tell you *which* remedy is the right one,
and these remedies are not interchangeable — uninstalling, repointing a symlink, committing a
release and toggling a pack in another application's panel fix four different worlds. So each
of these checks climbs a named ladder, and the fix string says which rung it fell off.

**The runtime ladder** (INSTALL FRESHNESS), four rungs, in this order:

| rung | the question | when it fails |
|---|---|---|
| 1 of 4 | a runtime surface exists at all | SKIP — nothing on this machine claims to run the plugin |
| 2 of 4 | the name is free | `claude plugin uninstall <id>` then restart — an installed plugin outranks the link |
| 3 of 4 | the surface resolves to **THIS** tree | `ln -sfn <repo> <link>` then restart — the link loads another copy |
| 4 of 4 | what runs here is what everyone else sees | `git add -A && git commit` (in-place), or `claude plugin marketplace update && claude plugin update` (cache) |

**The shadow ladder**, three rungs, by *where the shadow lives* — the two shadow findings share
it, which is why an app-side pack is always rung 3:

| rung | the shadow | the only thing that removes it |
|---|---|---|
| 1 of 3 | exact name, CLI-installed | `claude plugin uninstall <id>` |
| 2 of 3 | a different name carrying our verbs, CLI-installed | `claude plugin uninstall <id>`, or keep it knowingly |
| 3 of 3 | an app-side pack in the desktop app's store | the desktop app's plugin panel — **no CLI verb reaches it** |

A rung-2 finding on the runtime ladder is also rung 1 on the shadow ladder, and the fix says
both: the first names what broke, the second names where the shadow came from.

## SHADOW-APPSIDE — the store the CLI never mentions

Every other surface doctor reads belongs to the CLI. The desktop app provisions its own packs
into an estate no `claude plugin` verb lists, and doctor was blind to it until a stale clone of
this plugin served sessions out of it for a week. Two shapes, both **read off a live machine
before they were coded** rather than assumed:

```
<app-support>/local-agent-mode-sessions/<uuid>/<uuid>/rpm/<plugin_id>/    marketplace packs
<app-support>/local-agent-mode-sessions/skills-plugin/<uuid>/<uuid>/      the app's own pack
```

`<app-support>` is `~/Library/Application Support/Claude` on macOS, `~/.config/Claude` on Linux,
`%APPDATA%/Claude` on Windows, and `$CLAUDE_APP_SUPPORT_DIR` when set — the seam the fixture
uses. Each pack's `plugin.json` gives the name and version, its `skills/*/SKILL.md` gives the
verbs, its `hooks/hooks.json` says whether it registers hooks. **No store, no finding:** a
machine without the desktop app SKIPs, silently and honestly.

**The honest limit — provisioned is not proven active.** doctor sees what the filesystem shows.
Whether a pack is *switched on* is the app's live state, and the store records provisioning, not
that toggle: the 2026-07-26 audit looked and found only `installationPreference: "available"` on
every entry. So a pack the owner has already disabled in the panel can still appear here.
SHADOW-APPSIDE therefore says *this pack is provisioned and its verbs collide with yours* — it
never says *this pack is active*, and it never FAILs on someone else's estate.

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

### `--if-stale <hours>` — the rhythm, without the tax

A schedule checks the estate at a time; the in-session rhythm checks it at a **moment** — the
doors a session already walks through. `--if-stale <hours>` is what makes that affordable:
pulse reads the newest `[pulse]` line already in `COORD.md`, and **if it is younger than the
window, prints one line and exits 0 without running a single instrument**:

```
pulse: fresh (57m old, last: doctor=5 eval=0 watch-due=0 compile=ripe spend=CLEAN river=findings+coord)
```

Otherwise it runs the full sweep and banks its line as usual. The verdict travels forward, so
the caller learns the estate's colour either way — the second session of a morning pays
milliseconds for the answer the first one already bought.

**On the fresh path the exit code is always 0, even when the carried verdict is red** — pulse
did not measure, so it will not claim a measurement, and a caller that gates on the exit code
must not be told a close failed by a reading it never took. The colour is carried on the *line*,
under the word `last:`, and a red there is a red **as of that stamp** — recent, not current.
A consumer that needs the live answer drops the window: `pulse.sh --root .` measures now.

Two skills knock on this door, and neither is a schedule (both run inside a turn the user
started):

- **`oracle`** intake — `--if-stale 6`, between the foundation load and question 1. A red is
  surfaced *before* the six questions, because starting an hour of work on a broken estate is
  the expensive mistake.
- **`sessionend`** Phase 3.6 — `--if-stale 1`, so the close banks a fresh heartbeat unless one
  landed within the hour.

**The door fails OPEN, toward checking.** No `COORD.md`, no pulse line, an unparseable stamp, a
stamp from the *future* (a skewed clock, arithmetically "young" — the one input that could
silence the heartbeat forever), a non-numeric window, no `python3`: every one of them runs the
full pulse. The only path that skips work is a stamp that positively parses and is positively
young. `--if-stale 0` therefore always runs, and no flag at all means no door — the scheduled
path is untouched. Stamps are read and written **UTC only**.

### Scheduling it is the owner's click, never the harness's

pulse is what you would point a scheduler at — and **the harness never schedules itself.**
Creating, updating, pausing, or deleting a scheduled task is an owner-confirmed action, one
explicit yes per action, exactly as `watch` requires for its recheck cycle: *offer*, then wait.
Never write a fake schedule, never claim a task exists, and never imply something is running in
the background. A cron line the owner did not approve is a background process nobody consented
to. Absent an approved schedule, `bash pulse.sh --root .` by hand is the whole ritual.

The `--if-stale` doors above are **not** an exception to this law, and the distinction is the
whole reason they need no separate consent: an in-session pulse runs only inside a turn the
user themselves opened, in the foreground, printing what it did. A schedule runs when nobody
is there. The first is a skill doing its job; the second is a standing process, and only the
owner starts one.

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
installed plugin, an installed plugin under a **different name carrying our verbs**, an
**uncommitted release** under an in-place link — that one stands up a throwaway git repo,
commits v1.0.0 and bumps the whole release in the working tree, so tree-vs-HEAD is the only
disagreement left — and a **quiet estate** with no sign a hook ever fired. The clean in-place
run is asserted too, including that it never labels itself a cache install: the mislabel is
the defect this rewrite descends from. Every ladder string is asserted **on its own failure
path**, so a rung cannot quietly go missing or be pasted onto the wrong finding.

The app-side store gets a scratch store of its own: a colliding rpm-shape pack *with* hooks
(WARN naming pack, version, path, collisions and hooks), the same finding through the
`skills-plugin` shape at a different depth, a **non-colliding** pack that must stay silent, an
**absent** store that must SKIP, and a byte-for-byte snapshot proving doctor never writes into
another application's files. The app's own `rpm/manifest.json` is planted at the same glob
depth as a pack directory, so the scan is proven to step over non-directories rather than trip
on them.

Three of these checks read the machine rather than the repo, so the fixture hands them a
machine of its own: `$CLAUDE_CONFIG_DIR` is redirected at a scratch config tree (so INSTALL
FRESHNESS sees only the links and installs the fixture planted), `$CLAUDE_APP_SUPPORT_DIR` at
a scratch app-support tree (so SHADOW-APPSIDE never reads this laptop's real desktop-app
store — on the machine it was built on, that store holds a genuine 19-verb collision), and a
`claude` shim goes on PATH ahead of the real CLI (so TOKEN BUDGET reads a figure the fixture
chose). No network, no real install, no dependence on what this laptop happens to have. The estate is stamped with the
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
- `scripts/pulse-layer-fixture.sh` — the contract test for the machine-written **pulse layer**
  (`hooks/estate-pulse.sh`): files and JSON shape, five rapid fires producing one refresh, the
  caller returning in under a second, a detached refresh really landing, `/notrest` seeding it,
  the session-start echo firing with the file and silent without, and COORD proven
  byte-untouched. It reaps every background refresher it spawns before deleting its sandbox.
