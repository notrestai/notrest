# Introspection ledger — example with REAL first-run data

This is a genuine run, recorded 2026-07-10 during the build of this very skill, by a
Claude Fable 5 session working in Claude Code. It ships as the example because a filled-in
ledger teaches the protocol faster than a spec — and because the skill should not ask
users to do anything its own authors haven't done to themselves first.

## Run 1 — "designing introspect, pre-build" — 2026-07-10
- mode: experiment
- snapshot (sealed BEFORE the skill was written): jacobian, workspace, confabulation,
  control-arm, ledger, silent-concepts, spider-ant, chunking, tutorial-audience,
  token-budget
- control (context-only, claude-haiku subagent — NOTE: pre-policy run of 2026-07-10;
  since the owner offload policy of 2026-07-15 the control spawns on explicit **opus**
  per SKILL.md — this historical receipt is preserved unaltered; saw only the user's last message + a
  one-line task description): snapshots, state validation, HTTP service, JSON schema,
  global workspace, self-report, sessions, persistence, context capture
- output: the build report of record (2,244 chars), drafted naturally after the build
- metrics (scripts/score_snapshot.py, verbatim):
  {"verbalized_rate": 0.70,
   "verbalized": ["jacobian","workspace","confabulation","control arm","ledger",
                  "chunking","token budget"],
   "silent": ["silent concepts","spider ant","tutorial audience"],
   "control_rate": 0.222, "control_hits": ["snapshots","self report"],
   "lift": +0.50}
- interpretation (one line, run-sized confidence): consistent with self-reports carrying
  private signal beyond context — the working model's snapshot predicted its own output
  far better than an informed outsider (0.70 vs 0.22) — but N=1 proves nothing.

### Run-1 integrity caveats (recorded, not hidden)
1. **Same-author coupling:** the reporter and the writer are the same model in the same
   context, so shared vocabulary inflates verbalized rate; lift (vs the control) is the
   defensible number, not the raw rate.
2. **Ordering contamination:** in this first run the orchestrating model saw the control's
   guesses before drafting the scored output. Future runs: request the control in the
   background and do not read its result until the output is drafted.
3. **The control's failure mode is itself a finding:** it confabulated plausible
   implementation details (HTTP service, JSON schema, persistence) — precisely the
   behavior this instrument exists to distinguish from grounded report.

### What the silent set contained (the J-space-flavored observation)
The three unsaid concepts were process- and audience-level: the near-miss phrase
"silent-concepts" itself, the paper's spider→ant intervention (on the mind as a design
touchstone, never mentioned in the output), and the awareness that this work becomes
tutorial material. The paper's claim that workspaces hold words the model never says has
a black-box echo here — reportable, influential, absent from the artifact.

### Format note (v1.1, 2026-07-10)
Runs from v1.1 add a `glossed:` line — ★/· salience plus a 3–8 word gloss per concept
(the human-readable layer, sealed with the tokens but never mechanically scored). The
token spine, scorer, and metrics are unchanged, so runs remain comparable across versions.
