# STATE — decisions, code, changes (newest on top)

## Session 2026-09-01 — Director session 3: the 4.6.1 audit, and the 4.6.2 build

### Decisions

- **The offload law was RULED AGAIN by the owner on 2026-09-01** — the ruling of record, banked
  at `briefs/amendment-2026-09-01-offload-policy.md`, superseding the 2026-08-30 sonnet clause.
  **The seat chooses each lane's model by the difficulty of the task and declares the choice**:
  opus for judgment-bearing work (design, debugging, root-cause, kernel surfaces, refuters,
  reviews, merges, anything under-specified), sonnet for bounded well-specified work (mechanical
  edits with an exact target, sweeps, conversions, fixture runs, any job whose done-when is a
  runnable check written before dispatch), and **when unsure, opus**.
  Haiku is never lawful (a tier declaration does not launder it) and `subagent_type: "fork"` is
  never an offload at all — a fork ignores the model parameter, inherits the seat and bills its
  credit. Omitting the model is a violation, not a default. Enforced at the door by
  `plugins/notrest/hooks/spawn-gate.sh` (PreToolUse); audited after the fact by
  `plugins/notrest/skills/spend/scripts/spend.py report` (exit 4). Where the prose and the gate disagree, **the gate wins**.
  Supersedes the 2026-07-15 opus-only rule recorded in the previous STATE entry.
- **Tiering was benchmarked and mostly lost (2026-09-01, four rounds).** A flat solo opus lane
  beat the tiered arm on the same judgment task on **both** axes — ~1.7x fewer tokens *and* a
  deeper result — losing only ~12% of wall-clock. The pre-registered hypothesis lost twice of
  two. The outcome is a narrow admission rule, not a recommendation: script it if it is
  compilable, flat solo opus by default, tier only for context overflow, wide parallel reads
  (`[unmeasured]`), or local models called as tools (`[operator-reported]`). Shipped as the
  32nd skill, `tieredswarm`, with the gate documented before the shape.
- **Teaching material is a release surface (4.6.1).** `RELEASE-SURFACE` correctly refused a
  release that ignored the 16-file workshop pack. Material that quotes version-specific
  behaviour — exit codes, verb counts — is now registered in
  `evals/golden-release-surface.txt` like any other shipped file.
- **A session opening in its own established estate IS resuming it (4.6.0).** The successor is
  handed the trail as an injected packet instead of being told to go find it; 4.6.1 then
  stood down the contradicting nudges after a field test showed a fresh session burning
  ~88,000 tokens re-deriving an orientation the packet had delivered for ~800 — and reading a
  START-HERE.md that was five weeks stale.
- **Audit before fix, and the seat re-runs every repro.** The 4.6.1 package audit ran as three
  find-only opus lanes with commissions banked *before* dispatch; no fix was commissioned until
  the owner said GO. All 22 findings were re-reproduced at the seat, so
  `docs/DOCKET-4.6.2.md` carries evidence rather than lane claims.
- **A kernel change ships only through a refuter round.** Reaffirmed for 4.6.2: the E2 stdin
  guard touches `plugins/notrest/hooks/**`, which `CLAUDE.md` names as a kernel surface.
- **A block one version behind is STALE, not absent (4.6.2).** The protocol block moved
  v2 → v3 to carry the 2026-09-01 offload ruling, and the old `found >= PROTOCOL_VERSION`
  reading would have told every v2 estate "already established" and left it there forever.
  Now `check` reports STALE and exits 5, the continuation packet keeps emitting while saying
  so (withholding the trail would punish the successor for the estate's age), `establish`
  upgrades in place byte-for-byte outside the markers, `BODY_V2` is kept as history rather
  than deleted, and a body hand-edited away from canonical v2 is banked to
  `<file>.notrest-v2.bak` before replacement — a local override is never silently relaxed.
  This repo's `CLAUDE.md` and `AGENTS.md` are already v3.
- **A long-running tool must narrate itself.** The 4.6.1 audit killed a silent 120 s
  `compile.py scan` and filed it as a hang; it was not hung, it was mute. 4.6.2 adds stderr
  progress and a permanent 10 s runtime arm over a seeded 260-entry corpus — the gate is not
  "it got faster" but "a bounded corpus finishes inside a stated bound, and a reader can tell
  working from wedged".
- **Every hook declares its own timeout.** Only `Stop` was bounded before; the rest rode the
  CLI default. The field sits on the command object, where the documented schema reads it.
- **The docs class is closed by a gate, not by a sweep.** Roster parity (every skill directory
  named on the README table and the marketplace description) is being added to `doctor`,
  because the previous gates matched the literal string "32" rather than the roster and so let
  M1/M2 through.

### Code & changes (load-bearing)

- `plugins/notrest/hooks/spawn-gate.sh` — PreToolUse. Denies an `Agent`/`Task` spawn that omits
  its model, names haiku, or asks for a fork; `NOTREST_GATE_OVERRIDE=1` permits with a loud
  receipt; any malformed payload passes through silently. The law in code, not in prose.
- `plugins/notrest/hooks/session-start.sh` — injects the discipline anchor, the amended offload
  rule, and (since 4.6.0) the auto-continuation packet; hoists the estate resolver above the
  continuity nudges so it never orders a session to fetch what the packet already carried.
  Session start on a large ledger went 13.71 s / 902 MB → 0.10 s / 18.4 MB.
- `plugins/notrest/skills/notrest/scripts/establish.py` — `continuation --brief` is the resume
  mechanism (~20 lines / ~3 KB on this repo). Hardened across three refuter rounds: records
  split on `\n` alone, control characters render visibly, every data line is framed `| ` so
  nothing quoted can reach column 0 or wear a `[notrest] ` prefix.
- `plugins/notrest/skills/{doctor,eval}/scripts/` — the ship gate. `plugins/notrest/skills/doctor/scripts/doctor.py` = the install
  and estate check (exit 0/5/6); `plugins/notrest/skills/eval/scripts/eval.py` = the law-conformance fingerprint (15 checks,
  ~0.2 s, zero model tokens). Doctor checks the install; eval checks the laws.
- `plugins/notrest/skills/sessionend/scripts/starthere_lint.py` — enforces that a resume file's
  every cited path exists and no instruction stands on a gitignored artifact. It is why this
  set of files can be trusted to run as written.
- `docs/MAP.md` (4.5.1) — the whole plugin probed live: hooks, instruments with their exit
  grammars, all 32 skills, the estate files by writer and reader.

### In progress / honest status

- **v4.6.2 is uncommitted work in the tree.** Three build lanes hold disjoint TOUCH-ONLY
  scopes; the seat owns the manifests, `CHANGELOG.md`, the HTML stamps, the golden list, and
  the commit. Do not read the docket as a list of things already done — check `git status`.
- **E2 (hooks blocking on idle stdin) is `[unverified]` in production.** The CLI normally
  closes stdin after the payload, so the impact is bounded by the default hook timeout rather
  than demonstrated live.
- **`doctor` exit 5 is the expected state**, with two standing warns: one COORD.md line from
  2026-08-27T20:07Z that does not parse (append-only, so it stays), and app-side plugin packs
  that shadow this tree's verbs and can only be disabled by the owner in the desktop app's
  plugin panel — no CLI verb reaches that store.
- **86 of the ledger's offload entries are unverifiable.** `spend report` says routing CLEAN on
  110 evidenced entries and says, in the same breath, that the 86 are not evidence of
  cleanliness. Quote both halves; never the first alone.
- **The consumer install flow is untestable from here.** Installing `notrest@notrest` on this
  machine shadows the in-place skills-dir runtime (live-proven 2026-07-25). Validation passes
  at both levels; end-to-end remains `[unverified]`.
- **The plan of record moved to the NAS on 2026-08-26** and no milestone has reached a Director
  on this machine since. Anything roadmap-shaped in this repo is local and may be superseded.
- **Deliberately deferred:** `plugins/notrest/skills/compile/scripts/compile.py scan` runs 117 s with no progress output and no stated
  runtime (measure before optimizing), and the inert `+x` bits on 4 of 12 hook files.
