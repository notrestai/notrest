# STATE — decisions, code, changes (newest on top)

## Session 2026-07-25 — oracle-suite v2.8.1 → notrest v3.5.0 (15 releases)

### Decisions

- **Opus-only offload (owner, 2026-07-15).** Every job a session offloads runs on explicit
  `opus`. Why: closest-to-Fable quality on delegated work; the spend ledger receipts the cost
  so the policy stays revisable with numbers. Alternative weighed: the v2.7.0 sonnet/haiku
  difficulty ladder (cheaper, lower quality) — superseded. `subagent_type: "fork"` banned from
  any seat: forks ignore the model parameter and inherit the parent, which the exit-4 gate
  cannot see.
- **The seat-builder ritual (owner-ratified).** One persistent Opus builder lane per domain;
  feedback rounds **resume the same lane**, never a fresh spawn. Why: the lane's context of the
  code it wrote is both the token saving and the quality keeper.
- **The speed law.** Receipts showed wall-clock tracks tool calls near-linearly (20-call lanes
  ≈ 3.5 min; 72–77-call monoliths ≈ 22–24 min). Greenfield builds decompose into parallel
  narrow lanes; builders get a style capsule inline, never a reading list; one fixture run per
  lane; **release slicing** — gated work ships, never held hostage to an unrelated lane.
- **Rename `oracle-suite` → `notrest`** (v3.0.0). Why: it outgrew "a suite of skills"; it is a
  session harness and should carry the company's name. Repo renamed to `notrestai/notrest`; a
  frozen `oracle-suite` tombstone at 9.0.0 keeps existing installs from stranding.
- **External `claude plugin eval` ruled OUT (owner).** Measured: ~13 min/pass, $4.58, opaque to
  the seat, **zero fixes in 45 minutes**. Replaced by in-house `/eval` — law conformance as a
  **static fingerprint** (a well-encoded law leaves a fingerprint in the shipped text). Result:
  0.06s, zero model tokens, and it found two real defects on its first run.
- **COORD rolls, never compacts (owner design).** Archiving *moves* lines (crash window, and
  the archive is never read); sealing *preserves* them. Seal at 500 → `COORD-001.md`, fresh
  volume with a continues-pointer; agents ledger at 1000.
- **The maiden compile is DIRECTIONAL, not PROVEN.** Five fair scenarios, but two of the nine
  compared surfaces are round-trip identities that cannot fail. The earlier "5/5 PROVEN" claim
  was withdrawn at the seat after the refuter proved the overclaim.

### Code & changes (load-bearing)

- `plugins/notrest/hooks/agent-ledger.sh` — SubagentStop: writes `COORD-AGENTS.md` **and** the
  spend receipt, idempotently (`agent=<id>` guard inside the flock'd critical section), honest
  grading (`observed` with usage, `tokens=unknown grade=estimate` without).
- `plugins/notrest/hooks/session-end.sh` — auto-cushion line + **volume rolling** (seal +
  fsync before atomic replace; inode guard; marker-less files refused).
- `plugins/notrest/skills/{eval,refuter,doctor,draft,recap,graph,compile,watch}/` — the
  session's new skills. `eval.py` (8 static checks), `doctor.py` (8 install/estate checks),
  `compile.py` (estate scanner: masking, df-weighting, **estate stopwords**, weak-source
  demotion), `graph.py` (file graph + PM merge).
- `compile/release-ritual/ship.py` — 853 lines, stdlib, **zero model calls**; the release
  ritual compiled. Five historical ships replay at `surfaces=9 · differs=0 · PARITY PASS`.
- `.gitignore` — narrowed: only derived scan output ignored; hand-built runtimes under
  `compile/<slug>/` are **source and tracked**; fixture scratch trees excluded (a 28 MB tree
  was caught before it could be committed).

### In progress / honest status

- **`ship.py` is isolated and NOT installed.** DEMO tier proven (replay); USE tier
  **NOT-LIVE-VERIFIED** (it has never executed a real ship); INSTALL tier described, not
  executed. Version monotonicity unchecked.
- **eval-green: deferred, not achieved.** Diagnosis artifacts kept; the kept-temp sandboxes
  were cleaned up, so trace-level root-causing must be redone if resumed.
- **Never live-proven claims:** successor escort (being proven by this very handoff), `watch`
  (no watchlist has ever existed), PM cross-project registry (absent).
- The Claude-5 "unhobbling" tension is **unresolved and named**: this harness grew its
  per-session injection all week while Anthropic's guidance says to cut overconstraint. The
  rightsizing pass is approved but not started.
