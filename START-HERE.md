# Start Here — notrest harness (this repo IS the plugin + marketplace)

> **Banked 2026-09-06 15:25Z at commit `4d072ea` (v4.8.1) — the plugin is part of Atlas; repo PRIVATE.**
> Resume: read this file, then `python3 plugins/notrest/skills/notrest/scripts/establish.py continuation --brief --root .`
> (needs the access key at ~/.notrest/access-key; `python3 plugins/notrest/skills/atlas/scripts/atlas.py key --check` exits 0). Gates: `python3 plugins/notrest/skills/doctor/scripts/doctor.py check` exit 5 / 0 fail,
> `python3 plugins/notrest/skills/eval/scripts/eval.py check --root .` exit 0 (17 checks), `python3 plugins/notrest/hooks/gate-check.py gates/ACTIVE.md --cwd .` 0 red, `python3 plugins/notrest/skills/atlas/scripts/atlas.py status --root .` GREEN.
> Open for the owner: LICENSE counsel review · carry ~/.notrest/credentials/keys/nas-notrest.key and atlas-hub.key to the NAS ·
> ATLAS-PLAYBOOK.md + WIRING.md for the hub push adapter (stub until then). Docketed 4.8.2: docs/DOCKET-4.8.md "Bounds stated at ship".
> Owner-owned untracked files at the root: NOTREST-ON-THE-NAS.md, WORKSHOP-SLIDES.md, WORKSHOP-SLIDES-live.js.


**Status in one line:** **v4.6.2 is being assembled** on top of shipped `v4.6.1` — 32 skills,
three build lanes working the `docs/DOCKET-4.6.2.md` items; the shipped tree's gates are
`doctor` **exit 5** (2 known warns, 0 fail) and `eval` **exit 0** (15 checks, 0 fail).

**Live line:** none. No predecessor session is alive to answer questions — the trail is the
only witness, so read it rather than asking for it.

**How you are meant to resume (since 4.6.0):** you do not re-derive this. Opening a session in
an established estate hands you the **auto-continuation packet** — the SessionStart hook
injects it, and when it carries the trail it also stands the old "read START-HERE.md first"
nudge down, because two instructions that contradict each other are worse than either alone
(4.6.1). If you did not get a packet, produce it yourself:

```
python3 plugins/notrest/skills/notrest/scripts/establish.py continuation --brief --root .
```

(~20 lines, ~800 tokens. That is the orientation; this file is the curated commentary on it.)

## Read these first, in order
1. **HANDOFF.md** — where we are and what is next (the curated snapshot).
2. **COORD.md** — the append-only ledger; its tail is current to the last prompt even when
   this file is not. `tail -20 COORD.md`. No volume has sealed yet (seals at 500 lines).
   The `CLAUDE.md` / `AGENTS.md` protocol block here is at **v3** (raised in 4.6.2 to carry the
   2026-09-01 offload ruling). If you open an estate whose block is v2, `plugins/notrest/skills/notrest/scripts/establish.py check`
   reports it **STALE and exits 5** — that is an upgrade to run, not a broken estate, and the
   continuation packet still emits.
3. **docs/DOCKET-4.6.2.md** — the 22 seat-reproduced findings 4.6.2 is fixing, each with a repro.
4. **STATE.md** — decisions + code, newest on top.
5. **CLAUDE.md** — the foundation (auto-read at repo root). `COORD-AGENTS.md` is the
   machine-written index of every agent that finished here.

## Then do this, in order
1. **Verify at tier 0 before believing anything below.** Run these three; they take seconds
   and spend zero model tokens:
   ```
   git log -1
   python3 plugins/notrest/skills/doctor/scripts/doctor.py check --root .   # expect exit 5
   python3 plugins/notrest/skills/eval/scripts/eval.py check --root .       # expect exit 0
   ```
   `doctor` exit 5 is the EXPECTED state, not a regression — see "Watch out for" below.
   `eval` exit 0 with 15 checks is the law gate; any fail names a file:line.
2. **Read the ledger tail and the docket** (`tail -20 COORD.md`, then `docs/DOCKET-4.6.2.md`)
   so you know which docket items have landed and which are still open in a lane.
3. **Check what the working tree actually holds** — `git status --short` and
   `git diff --stat` — because 4.6.2's lanes leave their work uncommitted for the seat to
   gate. Do not assume a docket item is done because the docket lists it.
4. **Then ship or continue.** The seat owns the release stamp: bump
   `plugins/notrest/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (they must
   match), CHANGELOG.md, the README table, and both version stamps in
   `docs/oracle-skill-flow.html`; re-run doctor + eval; then commit and push.

## Watch out for
- **`doctor` exit 5 is the expected gate result here, with exactly two warns.** (a) `ESTATE`:
  one COORD.md ledger line from `2026-08-27T20:07Z` does not parse — known, cosmetic, and
  COORD is append-only so it is never edited away. (b) `SHADOW-APPSIDE`: app-side plugin packs
  in the desktop app's store carry some of this tree's verbs; only the owner can disable those
  in the app's plugin panel, and no CLI verb reaches that store. A third warn, or any FAIL, is
  a real finding.
- **NEVER run the consumer plugin flow on this machine.** `claude plugin install/update` +
  `marketplace add` for `notrest@notrest` takes the name and silently SHADOWS the skills-dir
  runtime this repo loads in place (`~/.claude/skills/notrest` → `plugins/notrest`). Live-proven
  2026-07-25. Consumers install that way; this machine does not.
- **The offload law was ruled again by the owner on 2026-09-01 and is enforced in code**
  (`briefs/amendment-2026-09-01-offload-policy.md`). Every spawned lane names its model
  explicitly, and **the seat chooses it by the difficulty of the task and declares the choice
  in the brief**: opus for judgment-bearing work, sonnet for bounded well-specified work, and
  when unsure, opus. Never haiku, never `subagent_type: "fork"`,
  and omitting the model is a violation rather than a default. `plugins/notrest/hooks/spawn-gate.sh` denies a
  violating spawn at the door; `python3 plugins/notrest/skills/spend/scripts/spend.py report --root .`
  audits after the fact and exits 4 on a violation. Where prose and the gate disagree, the gate wins.
- **Don't hand-log lanes.** The SubagentStop hook writes `COORD-AGENTS.md` and the
  `spend/ledger.md` receipt itself, idempotently. Manual logging double-counts.
- **History files are never rewritten**: CHANGELOG.md, `COORD*.md`, `spend/ledger.md`,
  `briefs/`. Corrections are appended, never edited. COORD does not compact — it seals whole
  at 500 lines into `COORD-<NNN>.md` and opens a fresh volume (`COORD-AGENTS.md` at 1000).
- **The tombstone `plugins/oracle-suite-tombstone/` is pinned at 9.0.0 forever.** Never bump it.
- **Teaching material is a release surface.** `evals/golden-release-surface.txt` lists what a
  release must consider — including the 16-file workshop pack, added in 4.6.1 after
  RELEASE-SURFACE correctly refused a release that had ignored it.
- **The plan of record is not on this machine.** It moved to the NAS on 2026-08-26, and no
  milestone has been handed to a Director here since. Treat any roadmap you find in this repo
  as local and possibly superseded.
