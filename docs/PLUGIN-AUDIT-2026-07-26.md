# Plugin estate audit — 2026-07-26 (v3.11.0 seat, Opus analyst lane)

Owner ask: check every installed plugin and its skills, mine dev tips, prove notrest has
no dependency on any of them, recommend keep vs drop. Read-only audit; every removal is
an owner-run command. Seat annotations in [brackets].

## Headline findings

1. **Shadow incident #4 was live during the audit** — notrest@notrest 3.11.0 installed
   2026-07-27T00:27Z, shadowing the skills-dir runtime. [Seat purged it minutes later;
   record F-6 links the chain F-1→F-5→F-6 — concept C-1, "shadow-reinstall recurrence,"
   which the library's first clustering run had identified mechanically that same hour.]
2. **The mechanism, finally:** 15 plugin installs landed 17:21–17:27 local with ZERO
   `claude plugin install` strings in any shell history — the signature of the
   interactive `/plugin` marketplace UI. The PreToolUse shadow guard watches Bash
   command strings; it structurally cannot see UI installs. **The guard's blind side is
   the side actually in use.** Fix candidate: promote doctor's SHADOWED check to a loud
   SessionStart line (a hook can announce what it cannot block). [Scheduled: next build.]
3. **Self-collision is the severe trigger-space problem, not foreign packs:** nine
   notrest verbs are registered THREE times in the running app (stale `anthropic-skills`
   fork · stale ~v3.4 `oracle-suite` app copy · the repo), ten more twice — and
   `"hey oracle"` is claimed verbatim by three oracles, two of them model-invocable.
   [Fix candidate: doctor check — FAIL on any notrest-owned name resolving to a
   non-notrest path. Scheduled: next build.]
4. **notrest stands alone — zero hard dependencies** (grep-proven across the tree):
   foreign plugins NONE; foreign MCP tools NONE; scheduled-tasks MCP OPTIONAL-degrades
   (watch says so at three cited lines); codex CLI **binary** OPTIONAL-degrades,
   fixture-proven (a missing CLI hands over the install block and stops).

## Inventory (measured)

- **CLI-installed:** 15 plugins, ~6,754 tok always-on total (notrest ~3,513 of it).
  Eleven of the fourteen official ones were installed 2026-07-26 and never invoked.
  `plugin-dev` alone costs ~1,704 tok — 53% of the official load.
- **App-side domain packs (22 + anthropic-skills):** NOT CLI installs — materialized
  per-session by the desktop app under `~/Library/Application Support/Claude/
  local-agent-mode-sessions/…/rpm/plugin_<id>/`. Zero CLI cost; desktop-only. No CLI or
  settings toggle found — app UI only. The app-side `oracle-suite` (20 stale skills,
  ~v3.4 era, still carrying `fable-swarm`) has no local provenance — served from a
  server-side marketplace id.
- **`~/.claude/skills/` owner drafts** (fable-director, fable-mode, game-forge, gpt,
  introspect): bare skill dirs from Jul 9–10, 15–17 days stale, DIFFER from the notrest
  versions, and double-register triggerable skills today (the stale FABLE-COORD naming
  is live in this session's own skill list).
- **Codex residue:** orphan install-manifest `codex@openai-codex.json` (no matching
  install). The openai-codex marketplace stays registered — harmless; the gpt skill
  uses the codex BINARY, not the plugin.

## Keep / drop (owner decides; owner runs)

KEEP: **skill-creator** (~87 tok — the best eval/description tooling on the machine),
**claude-code-setup** (~101), **code-review** (~13), **agent-sdk-dev** (~169, weak keep —
only while SDK work is live). App-side packs: keep (zero CLI cost) — the problem to fix
is the stale oracle-suite copy, not the packs.

DROP (~2,713 tok back, 84% of the official always-on load): plugin-dev (mine its
hook-linter + validator scripts from the cache first — source survives uninstall),
cwc-makers, mcp-server-dev, mcp-tunnels, feature-dev (its agents aren't Opus-pinned —
silent policy violations waiting), frontend-design, playground, code-simplifier
(duplicates built-in /simplify). INVESTIGATE then likely drop: claude-md-management (an
auto-rewriter aimed at a hand-tuned CLAUDE.md is a risk, not a feature), ralph-loop
(lift the session-isolation guard from its stop-hook first).

ARCHIVE: the five `~/.claude/skills/` drafts (move to `~/.claude/skills-archive/`).
DELETE: the codex orphan manifest.

```bash
# the token drops (~2,713 tok back)
for p in plugin-dev cwc-makers mcp-server-dev mcp-tunnels feature-dev frontend-design playground code-simplifier; do claude plugin uninstall "$p@claude-plugins-official"; done
```

```bash
# stale owner drafts — archive, don't delete
mkdir -p ~/.claude/skills-archive && mv ~/.claude/skills/{fable-director,fable-mode,game-forge,gpt,introspect} ~/.claude/skills-archive/
```

```bash
# codex residue
rm ~/.claude/plugins/.install-manifests/codex@openai-codex.json
```

Reversible alternative to the uninstall loop: flip each to `false` under `enabledPlugins`
in `~/.claude/settings.json` — same token saving, instant undo.

## Dev tips adopted into the backlog (top of the mined list)

1. `argument-hint` frontmatter on flag-bearing skills (~10 tok each; zero-risk).
2. skill-creator's description evals — near-miss should-NOT-trigger queries, held-out
   scoring; the router + 29 descriptions have never been mistrigger-tested.
3. cold-start interview patterns for oracle: pause/resume marker, [PENDING] vs
   [PLACEHOLDER], never write a profile with silent gaps.
4. The ⚪ configured-but-untested third state for integration claims (doctor).
5. plugin-dev's hook-linter checks folded into doctor's HOOKS check.
6. ralph-loop's session-isolation guard pattern (state-file session_id vs hook stdin).
7. Description style law: generalize, don't enumerate (the always-on budget rule).
8. `user-invocable: false` as a finer dial for library-ish verbs.
9. Benchmark variance + screening fixtures for never-fails assertions.
10. New eval check idea: authoring-residue detector (stray fences, "Would you like me
    to…" tails) — found live in two official plugin agents.

REJECTED with reasons: model-side routing skills (router.sh does it at zero tokens —
stealing only degraded-capability routing + tiebreak order), `<example>` blocks in
always-on descriptions, >5,000-word skill bodies, `when_to_use` frontmatter.

## Could not determine (labeled)

App-side pack per-session token cost (est. 8–15k, inference); how to toggle individual
app-side packs (no persisted store found); why the stale oracle-suite is served
app-side; who clicked the 17:21–17:27 UI installs (no shell trace exists either way).
