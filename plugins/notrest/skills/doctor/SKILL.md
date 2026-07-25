---
name: doctor
description: "The harness's own self-check — one read-only pass that reports PASS/WARN/FAIL per check with the exact fix command: SKILL.md front-matter a real YAML load would reject (the unquoted colon-space that silently makes a skill invisible), manifest + tombstone version pins, skill-count drift across the four places the number is spelled, hook scripts that exist and parse plus rename residue in the SessionStart echo, estate integrity (COORD, agent ledger, spend ledger, compile candidates), installed-vs-repo-vs-clone drift, unanchored gitignore rules that swallow skill directories, and stale version stamps on rendered surfaces. Use on \"/doctor\", \"health check\", \"is the harness healthy\", \"check the install\", \"why isn't X triggering\", after any release, or when a skill stops firing. Reads only — never repairs, never bumps, never commits."
---

# doctor — the harness's self-check

```bash
python3 plugins/notrest/skills/doctor/scripts/doctor.py check --root .
```

That is the whole skill. Eight named checks, one line each, a fix command on every WARN and
FAIL, one summary line at the end. `--root` defaults to the git root of the cwd, so bare
`doctor.py check` works from anywhere inside the repo. Add `--json` for machine output.

Point it at what a session is actually *running* instead of the repo it edits:

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
| **ESTATE** | `COORD.md` header + parseable ledger lines, the `COORD-AGENTS.md` machine header, `spend/ledger.md` through `spend.py report`, `compile/candidates.json` as valid JSON | recap, compile and graph all *parse* these files. A damaged header does not break the file — it breaks every reader downstream, quietly. `spend.py report` exiting **4** is not a doctor failure: it is the routing gate firing correctly, reported as WARN with the verdict. |
| **INSTALL FRESHNESS** | repo version vs the marketplace clone vs `installed_plugins.json` | **the stale marketplace clone, 2026-07-15.** The session was running a build two versions behind the repo it was editing, and every "shipped" claim that day was made against code that was not installed. The hook's git self-update silently no-ops on a cache install, so nothing ever said so. |
| **GITIGNORE** | `/graph/` and `/compile/` present *and anchored*, and the skills' own `graph/` and `compile/` dirs not ignored | **the unanchored gitignore, v2.16.0.** `graph/` without the leading slash matches at *any* depth — it un-tracked `plugins/notrest/skills/graph/`, so the shipped plugin was missing a skill and `git status` stayed clean about it. |
| **RENDER SURFACES** | the version stamps in `docs/oracle-skill-flow.html` match `plugin.json` | a rendered doc is a shipped surface. A stale stamp ships a lie to whoever opens it. |

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

## Proving it

```bash
bash plugins/notrest/skills/doctor/scripts/fixture.sh   # exit 0 = every assertion held
```

The fixture builds a synthetic harness in a scratch dir, asserts it comes back clean at exit
0, then injects each defect class in turn — unquoted colon-space description, version
mismatch, tombstone bump, broken hook syntax, count drift, unanchored gitignore, stale render
stamp, damaged COORD header, broken `candidates.json` — and asserts each one flips **exactly**
its own named check to FAIL at exit 6, with every other check still passing. A health checker
that cries wolf is worse than none, so precision is asserted, not just detection.

## Companion utilities

Two small seat tools ship beside the checker (both `bash -n` clean, typed exits):

- `scripts/render-check.sh <file.html>` — serves the file on a free 127.0.0.1 port (8790-8799),
  proves HTTP 200, prints the URL to open, and reaps with `--close <port>`. The render gate,
  as one command instead of five.
- `scripts/gategrep.sh <file> <phrase> [expected]` — counts a phrase after normalizing
  whitespace, so a phrase wrapped across markdown lines still matches. A naive `grep -F`
  returns a false zero on wrapped text; this is the fix.
- `scripts/seat-tax-fixture.sh` — the contract test for both, plus the hook's auto-receipt.
