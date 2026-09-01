# drift-log — dated recheck cycles
> Append-only, newest block at the bottom. Written by `/watch run` only.

## 2026-07-26 — recheck cycle
**Result:** 2 HOLDS · 0 DRIFTED · 0 DEAD-SOURCE · 0 UNVERIFIABLE (of 2 due)
**Fetched this run:** https://code.claude.com/docs/en/plugins-reference (200) · https://code.claude.com/docs/en/hooks (200) · 0 searches
- ✅ HOLDS — W1 "SKILL.md edits apply live, hook/manifest changes need `/reload-plugins` or a restart" — first fetch, baseline set (sha256 4d6d2e39e280d778) — the reference's "Edit, reload, and disable a skills-directory plugin" section states that changes to a skill's SKILL.md take effect immediately in the current session, while changes to hooks/, .mcp.json, agents/ and output-styles/ do not and need /reload-plugins or a restart: the claim as written, from the primary source, read this run [cited: https://code.claude.com/docs/en/plugins-reference]
- ✅ HOLDS — W2 "The standard `hooks/hooks.json` is auto-loaded" — first fetch, baseline set (sha256 2f232b1c5bd070b9) — the hooks reference lists "Plugin hooks/hooks.json" as in scope "When plugin is enabled" and instructs "Define plugin hooks in hooks/hooks.json", whose hooks "merge with your user and project hooks"; no plugin.json key is named anywhere, which is exactly the premise the v3.6.1 hotfix acted on [cited: https://code.claude.com/docs/en/hooks]

## 2026-09-01 — recheck cycle
**Result:** 2 HOLDS · 0 DRIFTED · 0 DEAD-SOURCE · 0 UNVERIFIABLE (of 2 due)
**Fetched this run:** https://code.claude.com/docs/en/plugins-reference (200) · https://code.claude.com/docs/en/hooks (200) · 0 searches
- ✅ HOLDS — W1 "SKILL.md edits apply live, hook/manifest changes need `/reload-plugins` or a restart" — page content moved (sha changed) but the claim verified against the fresh body: /reload-plugins still documented, live-SKILL.md-edit vs reload/restart split intact [cited: https://code.claude.com/docs/en/plugins-reference]
- ✅ HOLDS — W2 "The standard `hooks/hooks.json` is auto-loaded" — fresh body still states hooks/hooks.json loads when the plugin is enabled, bundled with the plugin [cited: https://code.claude.com/docs/en/hooks]
