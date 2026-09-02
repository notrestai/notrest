# Handoff — 2026-09-01 (Director session 3, "notrest plugin Dir3")

- **This session did:** seated as the project **Director** and verified at tier 0 against the
  auto-continuation packet rather than re-deriving the trail (the 4.6.1 mechanism working as
  designed). Then, on the owner's ask "check plugin package 4.6.1 for errors, fixes and
  missing", dispatched **three find-only opus audit lanes** (package/install surface ·
  scripts+fixtures in a scratch copy · docs/claims vs tree), each with its commission banked in
  `briefs/` *before* dispatch. Every return was seat-gated by re-running its repro:
  **22 of 22 findings reproduce.** The merged docket is `docs/DOCKET-4.6.2.md`. On the owner's
  GO ("fix the remaining items as well and then ship the 4.6.2"), three **build** commissions
  were banked with disjoint TOUCH-ONLY scopes and dispatched.
- **Current status:** shipped tree is **v4.6.1** (`git log -1` for the exact commit; do not
  trust a hash written in prose). **v4.6.2 is in the working tree, uncommitted** — the lanes
  leave their work for the seat to gate and stamp. Gates on the shipped tree: `doctor` **exit 5**
  (11 checks · 9 pass · 2 warn · 0 fail), `eval` **exit 0** (15 checks · 0 fail),
  `spend report` **exit 0**, routing CLEAN.
- **What 4.6.2 is fixing** (all from `docs/DOCKET-4.6.2.md`, each with a repro):
  - **E1** `recap walk.py` dies `KeyError: 'entries'` on this estate — and its fixture had zero
    arms for that path, so it was 100/0 green while the primary verb was broken.
  - **E2** five hooks read stdin unbounded and block forever on an open idle stdin; `plugins/notrest/hooks/hooks.json`
    declares a timeout only on `Stop`. **Kernel surface — a refuter round is required.**
    Reachability in a real session is `[unverified]`.
  - **F1–F7 / M1–M3** the docs-currency class (superseded offload-law text, five-week-stale
    continuity files, stale version stamps and counts, README naming 29 of 32 skills, `mentor`
    undiscoverable) plus `plugins/notrest/skills/introspect/scripts/score_snapshot.py`'s error posture, derived output shipped in the
    package, and the gates that let all of it through.
- **Next up (in order):**
  1. **Gate the three build lanes' returns** — exit-code-checked, never `| tail`. The hooks and
     scripts lanes each owe a **refuter round** before their work can ship (kernel law).
  2. **Stamp the release at the seat**: both manifests (versions must match), `CHANGELOG.md`,
     the README table, both stamps in `docs/oracle-skill-flow.html`, and
     `evals/golden-release-surface.txt` — none of which any lane may touch.
  3. **Re-run the full gate** (`doctor` + `eval` + the fixture battery) and only then commit
     and push.
  4. **Decide F5 and F7** — deliberately deferred: profile `plugins/notrest/skills/compile/scripts/compile.py scan` (rc=0, 117 s,
     no progress output) before optimizing it, and the inert `+x` bits on 4 hook files.
- **Open questions / blockers:**
  - **The plan of record is not on this machine.** It moved to the NAS on 2026-08-26 and no
    milestone has been handed to a Director here since — so this repo's frontier is local.
  - **E2's production reachability is unproven.** The CLI normally closes stdin after the
    payload, so the impact is bounded by the default hook timeout, not demonstrated live.
  - **The consumer install/update/marketplace flow cannot be checked from here** — running it
    on this machine shadows the skills-dir runtime. `claude plugin validate` passes at both
    levels and `plugin list` shows no shadow; end-to-end remains `[unverified]`.
  - **Hook behavior on Linux/CI under a stripped PATH is `[unverified]`.**
- **Must-know for next session:**
  - **You are resumed by a packet, not by this file.** `plugins/notrest/skills/notrest/scripts/establish.py continuation --brief`
    emits it (~20 lines, ~800 tokens) and the SessionStart hook injects it. This file is
    commentary on that packet; when they disagree, the packet and `COORD.md` are newer. The
    packet now names `protocol_current` / `protocol_stale`: **the estate protocol block went
    v2 → v3 in 4.6.2**, a v2 block reports STALE at exit 5 instead of passing as "already
    established", and the packet keeps emitting while it says so.
  - **`doctor` exit 5 with exactly two warns is the expected state** (one unparseable COORD
    line from 2026-08-27; app-side shadow packs only the owner can disable). A third warn is a
    finding.
  - **The offload law was ruled again 2026-09-01** (`briefs/amendment-2026-09-01-offload-policy.md`):
    the seat picks each lane's model by the difficulty of the task and declares the choice in the
    brief — opus for judgment, sonnet for bounded work, opus when unsure. Never haiku, never a
    fork, and omitting the model is a violation.
    `plugins/notrest/hooks/spawn-gate.sh` refuses it at the door.
  - **Receipts write themselves.** The SubagentStop hook banks each finished lane's brief to
    `briefs/` and its receipt to `spend/ledger.md`. Hand-logging double-counts.
  - **Teaching material is a release surface** (4.6.1): the 16-file workshop pack is registered
    in `evals/golden-release-surface.txt`, so a release that changes a verb's exit codes cannot
    ship without the pack being considered.
- **Spend verdict (estate lifetime, verbatim from
  `python3 plugins/notrest/skills/spend/scripts/spend.py report --root .`):** `entries: 206 ·
  tokens (known): 473,076,217 · estimate-grade: 87 (~0 tok, never summed into known)` —
  opus-5 98% / sonnet-5 1% / opus-4.8 0% — **routing: CLEAN** (110 offload entries evidenced,
  0 violations; **86 unverifiable — routing is NOT provable for those, and they are not
  evidence of cleanliness**). The main loop's own consumption is invisible to the model and is
  not in that total.
