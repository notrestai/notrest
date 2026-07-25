# Handoff — 2026-07-25

- **This session did:** took the harness from `oracle-suite` v2.8.1 to **`notrest` v3.5.0** —
  fifteen releases, twenty-eight skills, a plugin rename (id + repo + tombstone), and the
  estate's four verbs completed: record → narrate (`recap`) → map (`graph`) → optimize
  (`compile`). Built its own instruments after the external eval runner was ruled out.
- **Current status:** shipped, pushed (`5a67231`), installed at 3.5.0. Both self-checks green
  on the shipped tree — `doctor` HEALTHY 8/8, `eval` PASS (0 fail, 0.06s, zero model tokens).
- **Next up (in order):**
  1. The **rightsizing pass** the owner approved: run the built-in `claude doctor` over this
     repo and slim the SessionStart injections + fattest skill descriptions against Anthropic's
     Claude-5 context rules (the "unhobbling" guidance) — the hook echoes alone are ~350 words
     into every session on this machine, and every one of them was individually justified.
     Measure injected tokens per session before/after; `/spend` receipts the saving.
  2. Decide the maiden compile's fate: `compile/release-ritual/ship.py` is **isolated and NOT
     installed** — it is DEMO-proven and NOT-LIVE-VERIFIED. Promoting it to the ritual of
     record is a normal versioned release and the owner's call.
  3. Optionally prove a never-proven claim live (cheapest first: `watch`).
- **Open questions / blockers:**
  - `ship.py` has **no version-monotonicity check** — `ship --version 3.1.1` on a 3.5.0 tree
    succeeds. Known, disclosed, unfixed.
  - Three harness claims remain **never live-proven**: the successor escort (until this
    handoff), `watch` (no `watch/` dir has ever existed), and the PM cross-project graph
    (`~/.claude/oracle-projects.txt` absent — no project ever registered).
  - The eval-green baseline was **deferred, not achieved**: the external runner was killed
    mid-grind. Its diagnosis artifacts survive at `evals/results/diagnosis/`; the
    `--keep-temp` sandboxes did not.
- **Must-know for next session:**
  - **Receipts now write themselves.** The SubagentStop hook logs each finished agent to
    `spend/ledger.md` (idempotent, honest grading). Don't hand-log lanes.
  - **COORD never compacts — it rolls.** Sealed volumes (`COORD-001.md`…) at 500 lines;
    read the active tail, read all volumes for history.
  - **The cached plugin skill text can lag the repo.** The installed `sessionend` still
    describes the retired 40-line compaction. The repo is the truth; restart applies updates.
  - Every offloaded lane runs explicit **opus**; the seat never rides a subagent.
- **Spend verdict (this session, verbatim):** `entries: 40 · tokens (known): 4,272,059 ·
  estimate-grade: 0` — opus-5 73% / opus-4.8 23% / sonnet 4% — **routing: CLEAN — Fable never
  rode below the seat**. (Ledger covers observed spend only; the main loop's own consumption
  is not visible to the model and is not in that total.)
- **Repeated work worth compiling (from `/compile` scan):** `commit-follow-hook`
  (alias **release-ritual**) — seen **18×**, already **COMPILED** this session; next ripe
  candidate is `fil-plugin-oracl` at 13×, status NEW.
- **Compiled runtime + verdict docs:** `compile/release-ritual/` — `ship.py`, `README.md`,
  `fixture.sh`, `background.md`, `release-ritualDossier.md`, `verdict.html`
  (render-verified in both themes at the seat).
