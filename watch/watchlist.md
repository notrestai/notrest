# watchlist — facts under watch
> Rows are APPENDED. Only `Last checked` and `Status` are edited in place, by `/watch run`.
> Never delete a row — retire it by setting Cadence to `retired`. IDs are never reused.
> Cap: ~10 load-bearing claims per source dossier.
> Status: HOLDS · DRIFTED · DEAD-SOURCE · UNVERIFIABLE.
> Cadence: weekly · monthly · quarterly · on-demand · retired.
> A `|` inside a claim is escaped as `&#124;` so the row still parses.

## CLAUDE.md:17-19 — the skills-dir in-place cutover · added 2026-07-26
| ID | Claim (verbatim) | Source | Tier | First verified | Last checked | Status | Cadence | Hash |
|----|------------------|--------|------|----------------|--------------|--------|---------|------|
| W1 | "SKILL.md edits apply live, hook/manifest changes need `/reload-plugins` or a restart" | https://code.claude.com/docs/en/plugins-reference | T1 | 2026-07-25 | 2026-07-26 | HOLDS | weekly | 4d6d2e39e280d778 |

## CHANGELOG.md:126-127 (v3.6.1) — the hooks auto-load contract · added 2026-07-26
| ID | Claim (verbatim) | Source | Tier | First verified | Last checked | Status | Cadence | Hash |
|----|------------------|--------|------|----------------|--------------|--------|---------|------|
| W2 | "The standard `hooks/hooks.json` is auto-loaded" | https://code.claude.com/docs/en/hooks | T1 | 2026-07-25 | 2026-07-26 | HOLDS | weekly | 2f232b1c5bd070b9 |
