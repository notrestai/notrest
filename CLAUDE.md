Last updated: 2026-07-15

# CLAUDE.md — notrest harness foundation

## Protocol
- Fable discipline every substantive session (the SessionStart hook anchors it;
  `/fable-mode` loads the full contract).
- **Offload model policy (HARD RULE, owner-set 2026-07-15):** Fable never rides in a
  subagent; every job a Fable session offloads runs on **opus** — set `model: "opus"`
  on every Agent/Workflow call; no sonnet, no haiku. Delegate via **agentswarm**
  (seat-agnostic — the seat keeps decompose/judge/apply/gate); log every lane with `/spend`
  (`report` exits 4 on a violation); consult `/archivist` before research fan-outs.
- Never `/model`-switch the seat mid-session — the prompt cache is per-model, so a
  switch re-reads the context cold. A model change is a subagent or a handoff.

## Project
- This repo IS the `notrest` marketplace: `plugins/notrest/` (28 skills;
  current version lives in plugin.json), manifest at `plugins/notrest/.claude-plugin/plugin.json`, marketplace
  manifest at `.claude-plugin/marketplace.json` — **versions must match**. The plugin was
  renamed `oracle-suite` → `notrest`; `plugins/oracle-suite-tombstone/` is a migration stub
  pinned at 9.0.0 (one SessionStart line pointing at the new id) — **never bump it**.
- Release ritual: bump both manifests + CHANGELOG.md + README table + the version stamps
  in docs/oracle-skill-flow.html (header + footer) → commit → push →
  `claude plugin marketplace update notrest && claude plugin update notrest@notrest`
  (restart applies). The hook's git self-update no-ops on marketplace-cache installs
  (`~/.claude/plugins/cache/...` is not a git clone) — the CLI path above is the real one.
- Spend ledger: `spend/ledger.md` — append-only, via `spend.py` only, never hand-edited.
