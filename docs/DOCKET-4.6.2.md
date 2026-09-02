# 4.6.2 docket — PROPOSED by the Director (session 3), 2026-09-01. Not yet owner-approved.

Source: the 4.6.1 package audit (three find-only opus lanes, commissions banked at
`briefs/commission-2026-09-01-audit-461-{package,scripts,docs}.md`; returns seat-gated by
re-running every repro — COORD.md lines 21:35Z–21:40Z). Tree audited: `54cb763` = v4.6.1.
Every item below reproduced under a seat-run command unless labeled otherwise.

## ERRORS — broken behavior

### E1 · `/recap` walk dies on this estate — KERNEL-adjacent (estate-ledger consumer)
`skills/recap/scripts/walk.py:675` appends the `STAMP-ORDER` inventory row without the
`entries/malformed/first/last` keys that `emit_inventory` (`:712`) and `cmd_prefill` (`:974`)
read → `KeyError: 'entries'`, rc=1, on any estate where a stamp contradicts append order
(this one). `walk`, `walk --json`, `walk --since`, `prefill` all die; `spans` survives.
Repro: `python3 plugins/notrest/skills/recap/scripts/walk.py walk --root .` → rc=1.
Paired defect: `skills/recap/scripts/fixture.sh` has **zero** arms for the stamp-clamp path
(`grep -c "STAMP-ORDER\|monotone\|clamped"` → 0) — 100/0 green while the primary verb is
broken. The vacuous-pass species. Fix ships WITH a red-first arm.

### E2 · Five hooks block forever on an open, idle stdin — KERNEL SURFACE (refuter round required)
`router.sh:7`, `spawn-gate.sh:26`, `agent-ledger.sh:15`, `completion-gate.sh:31`,
`session-end.sh:24` read stdin unbounded (`cat` / `json.load(sys.stdin)`). Only
`pretool-gate.sh:34` guards it (`read -r -d '' -t 5`) and its own comment names the hazard.
`hooks/hooks.json` declares `timeout` only on Stop (line 86); the other six events ride the
CLI default. Repro: fifo held open by a sleeper, `timeout 6 bash <hook> < fifo` → rc=124 for
all five, rc=0 for pretool-gate. Reachability in production is **[unverified]** — the CLI
normally closes stdin after the payload — so the impact is bounded by the default hook
timeout, not proven live. Fix = propagate the timed read to all six and declare explicit
per-event timeouts; refuter attacks the guard before ship.

## FIXES — wrong but working

- **F1 · Superseded law text on two surfaces.** `README.md:71,76` and
  `skills/fable-mode/SKILL.md:101-105,265` still state opus-only ("never sonnet/haiku");
  the 2026-08-30 sonnet amendment that `hooks/spawn-gate.sh:11` enforces appears in neither
  (0 hits for `2026-08-30`). 4.5.1's "one law on every surface" missed fable-mode.
- **F2 · Frozen continuity docs.** `START-HERE.md:3-4`, `HANDOFF.md:7-8` describe v3.5.0,
  28 skills, commit `5a67231`, doctor HEALTHY 8/8 (now 11 checks, exit 5). mtime 2026-07-27.
  This is the "five weeks stale" harm 4.6.1 named; the nudge was silenced, the file was not
  rewritten. `STATE.md` same era.
- **F3 · Stale version stamps.** `docs/MAP.md:3` maps v4.5.0/`bd9fec0` (golden release
  surface); `docs/UNDERSTANDING.md:183` says v4.2.0 in present tense (golden surface);
  `CHANGELOG.md:36` pins the brief packet at "18 lines" — it emits 20 lines / 3044 B now;
  `docs/oracle-skill-flow.html:96` says "31-skill harness" (tree = 32; doctor RENDER pins the
  version stamps only, so the count slips the gate).
- **F4 · `score_snapshot.py` error posture.** Missing `--output-file` → raw
  `FileNotFoundError` traceback, rc=1 (`:83`); every sibling lint refuses in one line at
  rc=2. Its documented verbless form (`introspect/SKILL.md:85`) is absent from `--help`
  (which lists only `{score,append,report}`) — works, undiscoverable.
- **F5 · `compile.py scan` runtime undisclosed.** Lane measured 105 s idle / rc=124 under a
  120 s bound during the battery, no progress output, no stated runtime in `compile/SKILL.md`.
  Seat rerun (concurrent with three finished lanes, machine otherwise idle): rc=0 dur=117s. Reproduced.
- **F6 · Derived output shipped in the package.** `plugins/notrest/graph/{graph,river}.{html,json}`
  — 4 tracked files, 125 KB, generated 2026-07-27, referenced by nothing; `.gitignore`'s
  `/graph/` is root-anchored so this copy escapes; doctor's GITIGNORE check never looks here.
- **F7 · Minor hook cosmetics.** `session-start.sh` banner prints `v?` when
  `CLAUDE_PLUGIN_ROOT` is unset (no `$0`-dir fallback); `completion-gate.sh` is the one hook
  that leaks stderr (99 B, honest fail-open notice) on empty stdin; +x bits on 4 of 12 hook
  files (inert — hooks.json invokes via `bash`).

## MISSING — promised, not shipped

- **M1 · README roster 29 of 32.** `README.md:38` claims thirty-two; table has 29 rows;
  `beam`, `mentor`, `tieredswarm` have no row and no mention.
- **M2 · `mentor` is undiscoverable.** Absent from the marketplace description (names 31),
  `plugins/notrest/README.md`, and `docs/TUTORIAL.md` (0/0/0).
- **M3 · Gates that let the above through.** doctor SKILL COUNT matches the literal "32",
  not the roster (→ M1 passed); RENDER SURFACES checks versions, not counts (→ F3 html);
  GITIGNORE check skips `plugins/notrest/graph/` (→ F6); recap fixture lacks the clamp arm
  (→ E1). A roster-parity check (every skill dir named on README + marketplace description)
  closes M1/M2/F3-html as a class.

## Could not be checked from this machine
- The consumer install/update/marketplace flow end-to-end — banned here (shadow law);
  `claude plugin validate` passes at both levels, `plugin list` shows no shadow. [unverified]
- E2's reachability in a real session (see above). [unverified]
- Hook behavior on Linux/CI under a stripped PATH. [unverified]

## Recommended shape for 4.6.2
1. **Kernel round (refuter required):** E2 stdin guard + explicit hooks.json timeouts.
2. **One builder lane, non-kernel:** E1 fix + red-first fixture arm; F4 refusal; M3 roster-
   parity + RENDER-count + GITIGNORE-package checks (so the docs class cannot drift again);
   untrack F6.
3. **Docs currency sweep (same lane or a DRAFT-tier sonnet lane — mechanical):** F1, F2, F3,
   M1, M2. START-HERE/HANDOFF rewritten from the ledger, not from memory.
4. **Leave / measure later:** F5 (profile before optimizing), F7 +x bits.
Ship gate unchanged: doctor + eval green, battery 30/0, plus the new arms red-first.
