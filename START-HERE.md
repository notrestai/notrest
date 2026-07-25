# Start Here — notrest harness (this repo IS the plugin + marketplace)

**Status in one line:** shipped and healthy at **v3.5.0** (28 skills, commit `5a67231`,
installed) — `doctor` HEALTHY 8/8 and `eval` PASS 0-fail on the shipped tree.

**Live line (escort active):**
- "Notrest plugin DIR is now the seat" — the predecessor session that built v2.8.1 → v3.5.0
  is alive and answers for: the whole session's decisions, the compile ritual, the hooks,
  the rename, and why anything is the way it is. Message it before re-deriving anything.
  Read `COORD.md`'s tail and `COORD-AGENTS.md` **first**; ask the line only for what the
  trail doesn't carry.

## Read these first, in order
1. **HANDOFF.md** — where we are and what's next (the curated snapshot)
2. **COORD.md** — the ledger tail: the per-prompt trail with evidence, current to the last
   prompt even if this handoff is stale. Sealed volumes (`COORD-<NNN>.md`) hold older history;
   none exist yet (31 lines, seals at 500).
3. **STATE.md** — decisions + code, newest on top
4. **CLAUDE.md** — the foundation (auto-read at repo root)

## Then do this, in order
1. **Restart the app if you haven't** — v3.5.0 loads then; the cached skill text from an older
   version can otherwise contradict the repo (the installed `sessionend` still describes the
   retired 40-line COORD compaction; the repo's law is rolling volumes at 500).
2. **Sanity-check the harness with its own instruments** (seconds, zero tokens):
   `python3 plugins/notrest/skills/doctor/scripts/doctor.py check --root .` → expect HEALTHY 8/8
   `python3 plugins/notrest/skills/eval/scripts/eval.py check --root .` → expect PASS 0-fail
3. **Run the rightsizing pass** (owner-approved, not started): run the built-in `claude doctor`
   over this repo, then slim the SessionStart hook echoes and the fattest skill descriptions
   against Anthropic's Claude-5 context rules. Measure injected tokens per session before and
   after; receipt it with `/spend`. This is the top open item.
4. **Then decide** whether the compiled `compile/release-ritual/ship.py` graduates from
   isolated to the ritual of record (a normal versioned release; owner's call), and/or prove a
   never-proven claim live — `watch` is cheapest.

## Watch out for
- **Don't hand-log lanes.** The SubagentStop hook writes both `COORD-AGENTS.md` and the spend
  receipt automatically now. Manual logging double-counts.
- **Every offloaded lane must set `model: "opus"` explicitly** — never sonnet/haiku, never
  `subagent_type: "fork"` (forks ignore the model parameter). `spend.py report` exits 4 on a
  violation; surface it verbatim, never smooth it.
- **The ship ritual has a compiled runtime that is NOT installed.** Ship by hand (bump both
  manifests + CHANGELOG + flow-page stamps → validate → commit → push → marketplace update +
  plugin update), or run `compile/release-ritual/ship.py` knowingly: it is replay-proven but
  **has never executed a real ship**, and it does not check version monotonicity.
- **The tombstone `plugins/oracle-suite-tombstone/` is pinned at 9.0.0 forever.** Never bump it.
- **History files are never rewritten**: CHANGELOG, COORD*, `spend/ledger.md`, evals results.
  Corrections are appended, not edited.
