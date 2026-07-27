# Changelog — the notrest harness

## 3.13.0 — 2026-07-27

**Commission transparency, by construction — the owner's core value in three surfaces.**

- **Owner's law, verbatim in agentswarm:** "Transparency about what we ask our agents is
  a core value: the commission is never hidden — named at dispatch, banked on disk,
  marked in the pictures." Born from a real failure (a lane brief silently narrowed the
  owner's ask; fable-mode 12a/12b carry the scars).
- **Banked on disk:** the SubagentStop hook extracts every stopped lane's exact prompt —
  the first user message of its transcript — to `briefs/agent-<id>.md`, verbatim, never
  edited, never summarized. Write-once by O_EXCL (the filesystem refuses a second
  writer); receipts gain ` | brief: briefs/agent-<id>.md`; tool-result decoys fenced out
  by a seen-assistant guard. The end-to-end probe's synthetic commission contained
  "SCOPE NARROWED: owner asked for X and Y; I am only commissioning X" — extracted
  verbatim, which is the entire point. seat-tax fixture 54→79.
- **Marked in the river:** lane ticks whose receipts point at a banked brief render a
  ruled-sheet commission glyph; the hover card shows the prompt's first ~200 chars and
  the full-text path. Six honest states (banked · missing · none · outside-root ·
  unreadable · unresolvable) — a pointer resolving outside the root is refused unread.
  Today's real river truthfully reports 0/143 lanes commissioned (all predate the hook);
  it lights up by itself as new receipts carry pointers. river fixture 66→86.
- **Named at dispatch:** standing seat behavior — every lane dispatch names its
  commission to the owner in plain language, full prompt shown when the ask is the
  owner's scope. CLAUDE.md Protocol carries the core value.
- History correction, on the record: commit 74f1564 (`git add -A`) swept the ledger
  lane's in-flight hook edits under a completion-audit message — content verified
  byte-identical, nothing lost; the ledger carries the correction and the standing rule
  is explicit-file-list commits while any lane is in flight.
- Gate: seat-tax 79/0 · river 86/0 · journey 36/0 seat-run · eval 12/12 · doctor 10/10 ·
  validate 0. Live-fire of the brief hook is [unverified] until reload by construction —
  the fixture and an end-to-end probe on the real hook binary are the pre-reload proof.

## 3.12.1 — 2026-07-27

**The identity line — the shadow saga's root cause was a UI trap, and this is the vaccine.**

- The shadow mystery resolved by the owner's own words: the `/plugin` UI does not list
  skills-dir runtimes, so notrest looked uninstalled; the owner reinstalled it from the
  marketplace four times, each copy silently shadowing the invisible real one. Nobody's
  fault; a genuine UX trap now on record (concept C-1 in the library).
- SessionStart now opens with one self-identity line — `[notrest] v<X> @skills-dir —
  live from the repo tree (the /plugin UI hides skills-dir plugins; verify with:
  claude plugin list)` — version read live from plugin.json at fire time, never stale.
  Every session answers the question that caused four incidents, forever (~45 tok).
- Estate slimmed on owner order (audit's drop list executed): eight never-used plugins
  uninstalled (~2,713 always-on tokens recovered), codex orphan manifest deleted, five
  stale July-10 skill drafts archived to ~/.claude/skills-archive/ — the stale
  FABLE-COORD-era triggers are out of the trigger space.

## 3.12.0 — 2026-07-27

**The library learns to think in concepts, verify itself, and crown settled answers —
and its first mechanical discovery was the estate's own recurring wound, mid-recurrence.**

- **Concepts:** `library concepts --rebuild` clusters every record across every
  registered project with compile.py's df-weighted machinery, imported as a donor —
  never reimplemented (39ms importlib load; exit 2 `donor-missing` rather than a silent
  second implementation). Deterministic, zero model tokens, append-only generations at
  the shelf; `--dry-run` exists because the builder's own threshold sweep stuck to the
  append-only shelf (the law worked; the flag prevents the repeat). The seat christens
  (`--name C-1 "…"`); the script only records. First real run on five records found
  **C-1 "shadow-reinstall recurrence"** (F-1+F-5, cohesion 0.74) — minutes before the
  fourth live recurrence (F-6) proved the concept again.
- **The updater:** `library update [--due|--all]` re-probes every live url-evidenced
  record shelf-wide via watch.py's fetch (donor-imported), STANDS/DRIFTED/DEAD-SOURCE at
  zero model tokens; command/path/record evidence lists as NEEDS-SESSION-RECHECK, never
  auto-executed. Append-only `update-log.md` with dated blocks. First real run: an
  honest all-recheck result (five records, zero network calls) proving the honesty paths
  on real data. Drift is never banked as the new baseline.
- **Convergence:** `library crown C-<n> --statement … --by <members>` records a
  CONVERGED result into the local store and flips the concept — with refusals
  (`crown-member-refuted`, `crown-contested`, non-member `--by`) — and **a crown buys no
  immunity**: refute a member later and the crown itself returns CITES-REFUTED.
- **Cross-project refuted ground:** the updater walks record-evidence refs one hop —
  a live record citing an effectively-refuted record in another reachable project flags
  CITES-REFUTED (the seam v3.11.0 disclosed, closed).
- Fixture 102→**144**, hermetic, deterministic across re-runs; two design defects the
  fixture forced out (--project scope no longer narrows citation resolution; cross-
  project tombstones print qualified ids).
- **Plugin estate audit** (docs/PLUGIN-AUDIT-2026-07-26.md): notrest has ZERO hard
  dependencies (grep-proven; codex binary + scheduled-tasks MCP both optional and
  degrade-proven). The shadow mechanism identified: interactive /plugin UI installs —
  invisible to a PreToolUse-on-Bash guard by construction. Self-collision found: nine
  verbs triple-registered app-side, "hey oracle" claimed by three oracles. Keep/drop
  table with owner-run commands (~2,713 always-on tokens recoverable). Next-build
  candidates banked: SessionStart SHADOWED announcement, doctor name-collision check,
  description mistrigger evals, hook-linter absorption.

## 3.11.0 — 2026-07-26

**The estate gets a heartbeat rhythm, and the archivist becomes a library.**

- **Pulse rhythm.** `pulse.sh --if-stale <hours>`: the newest `[pulse]` ledger stamp wins,
  and every failure mode (no COORD, unparseable stamp, future stamp, bad window) runs the
  full sweep — fail-open toward checking. oracle's intake pulses at a 6-hour window and
  surfaces health-grade reds BEFORE question 1 — offering a live re-check rather than
  asserting a carried red is still true; sessionend's close pulses at 1 hour so the
  ledger's last word on a session is a measured verdict, not a claim. The daily 9:09
  scheduled pulse (owner-authorized in plain words; consent is a ledger line) covers the
  silence between sessions — only the first toucher of the day pays for the sweep.
  Fixture 48→79 asserting against stub-call counters (fresh = ZERO instruments invoked,
  measured not assumed). Found and fixed a live hang: `--root` with no value looped
  forever; now a guarded exit 2 with watchdog-bounded regression tests.
- **THE LIBRARY — federation core.** Every project's findings store stays in its repo
  (local truth, versioned, beam-able); `~/.claude/notrest-library/registry.jsonl`
  federates them. `library register|list|find|track`: cross-project knowledge search at
  zero model tokens, hits prefixed `<project>:F-<n>`; unreachable roots reported, never
  fatal. Registration also feeds `~/.claude/oracle-projects.txt` — the PM cross-project
  graph has its first registered project, and **the last never-proven claim from the
  v3.5.0 handoff is closed**. The evidence grammar gains type `record` (`F-<n>` local,
  `<project>:F-<n>` cross-project; existence-checked when reachable, accepted-with-note
  when offline — federation never fails closed); the river renders it, proven by live
  render not assumption. researcher now consults the library BEFORE spending a search
  budget: a question the library already answers is a budget you do not spend. Fixture
  58→102, fully hermetic via NOTREST_LIBRARY_ROOT. Live-proven on the real shelf: this
  repo registered, `library find shadow` → F-1/F-2/F-5 with prefixes.
- **Library doctrine banked** (owner-ratified): concepts · the updater · convergence —
  the compile doctrine applied to knowledge. Phase 2 builds in the same lane next
  release; the federation core shipped with its hooks already in place (--json find
  carries raw ask+statement; registry lines tolerate future keys).
- Gate: pulse 79/0 + archivist 102/0 seat-re-run · eval 12/12 0-fail · doctor 10/10 ·
  validate 0 · one-owner-per-file conflict audit clean.

## 3.10.0 — 2026-07-26

**Teeth, a heartbeat, a proven watch, and a transporter — the four vectors' first rungs land together.**

- **beam — the 29th skill** (`/beam up` · `/beam down`): in-flight lanes checkpoint to a
  pushed `beam/<ts>` ref and respawn in the cloud; results recall home with receipts.
  Physics honored: nothing teleports process memory — bank (brief + progress digest +
  files) → snapshot (temp-index git plumbing publishes the ref WITHOUT touching the live
  worktree; no-touch proven five independent ways incl. reflog length) → rail (prints,
  never spawns: PRIMARY `claude --cloud` with checkout-the-ref-first; scheduled-kick via
  routines with the untrusted-fire-text law; Desktop Continue-in-Web; the gated
  `isolation:"remote"` fast path with its mandatory `remote_launched` assertion — verified
  to DEGRADE SILENTLY otherwise) → down (fetches to a recall ref, DELIVERED/MISSING per
  lane, exit 3 on missing, folds by instruction only). Harness carriage: the ref's own
  `.claude/settings.json` gains project-scoped notrest installation (user config never
  travels to cloud VMs — verified), working copy byte-untouched. `--force` stops running
  lanes after banking, and every forced lane carries a written LOSS-ESTIMATE — a
  mid-flight checkpoint is never pretended lossless. The resume-prompt law block rides in
  every payload (opus-explicit, commit-to-ref, records through the door, tight RETURN.md,
  stay in your lane). Fixture: 170 assertions incl. fake-cloud round trip.
- **pretool-gate.sh — the first HARD gate** (PreToolUse on Bash, exit-2 blocking verified
  against the binary): `git push` in this repo blocks while doctor/eval are red (codes
  printed raw); the consumer install flow that shadowed the runtime three times today
  blocks anywhere on this machine. `NOTREST_GATE_OVERRIDE=1` honored in BOTH env forms
  (the natural prefix spelling would otherwise have been a documented lie); fail-open on
  the gate's own errors; 1.9ms miss path; 35-assertion fixture. Arms on `/reload-plugins`
  or restart.
- **pulse.sh — the autonomy heartbeat:** one unattended run of every instrument + river
  refresh, one flock'd COORD line, exit 1 on health reds only (workload signals — due
  claims, ripe candidates — are data, not sirens; `--strict` restores the literal
  reading). Scheduling remains the owner's click, by law. 48-assertion fixture.
- **watch PROVEN LIVE** — the last never-proven claim from the v3.5.0 handoff dies:
  two T1 doc claims (the very pages the cutover and the gate rest on) enrolled, probed
  over real HTTP (200 ×2), sha256 baselines set, re-probes UNCHANGED at zero model
  tokens, first real drift-log block written; UNVERIFIABLE→HOLDS earned, not carried
  (store record F-3).
- **UTC law:** watch.py stamped local time with a Z suffix (proven: 23:09 UTC emitted
  16:09Z; F-4) — fixed to timezone.utc; estate-writer audit found no other Z-liar.
- Housekeeping: third shadow reinstall purged (F-5, linked to F-1 — the river now shows
  recurring rocks on the same ground); five >500 descriptions dieted to fund beam under
  the 3,600 ceiling (always-on ~3,513); journey fixture derives its skill count from disk
  instead of pinning 28; HOOK-CONTRACT nuance documented (a PreToolUse hook exits 2 on
  its decision path by design — failure paths still exit 0).
- Gate: 18 fixtures (~1,150 assertions) seat-re-run exit 0 · eval 12/12 0-fail (29
  skills) · doctor 10/10 post-ritual · validate 0 · cross-lane conflict audit clean
  (every changed file traced to exactly one owner).

## 3.9.0 — 2026-07-25

**All eighteen journey gaps in one batch — the loop closes: every verb feeds the store, the store feeds the pictures, and refuted ground shows red.**

- **Six more writers feed the store** (G1/G2/G3): marketresearcher, critic, explainer,
  stepbystep, actionplan, game-forge emit validated finding records (all 10 shipped
  snippets pushed through the door for real: F-81–F-90 on a scratch root).
  marketresearcher/critic keep an optional `--dossier` card (the artifact people
  circulate); explainer/stepbystep lose their folders; actionplan's runbook file stays
  the deliverable, tracked by its record; game-forge records only on playtest exit 0.
- **Readers read the store** (G4/G5/G6): `watch.py add --from-findings` enrolls live
  cited-URL records idempotently (tombstones excluded — a status flip is bookkeeping,
  not a claim about the world); draft's source inventory starts from `track --json` and
  source-maps against record ids; recap walks the store as a sixth source and appends
  one result record per story.
- **RESTS-ON-REFUTED** (G7): a live record whose links contain an effectively-refuted id
  is flagged by `track` (`RESTS-ON-REFUTED F-<n>`, `rests_on_refuted` in `--json`) and
  painted in the river as a long-dashed red arc + ringed stone. Two independent
  implementations of one pinned rule (one-hop, live-only, tombstones never rest on what
  they killed); seat cross-check on a shared scratch store: agreement YES.
- **Routing hardened** (G8–G12): five new arms — health-check→doctor, law-check→eval,
  file-graph→graph, spend-audit→spend, "how did we get here"→recap. The graph/spend arms
  needed a SELFNAMED escape or the already-named-verb guard would have made them
  permanently dead (caught in-lane, fixture-pinned both directions). oracle's bullet now
  mirrors all 18 verbs (director reclassified — chains are not shapes — so parity is
  true set-equality with no allowlist). eval grows to **twelve checks**:
  ROUTE-TABLE-PARITY (verbs agree across both authorities + every routed skill
  acknowledges its shape in-body) and ROUTE-CONFORMANCE (WARN-grade: a recorded route
  must leave downstream evidence).
- **Four rituals became scripts** (G13–G17): sessionend's close refreshes graph + river
  behind an existence guard proven on both branches; `director.py plan|handoff|verify`
  (structure-verified pipelines, sha256 handoff manifests); `compile.py
  contract|scaffold` (Step-1 pre-filled with trail citations; the judgment columns come
  back blank by design); `score_snapshot.py append|report` (refuses trend claims under
  N=10); `spend.py --seat-estimate` (quarantined from measured totals — an estimate that
  can move a percentage is an estimate laundered into a measurement).
- **The journey render** (G18): `graph.py journey` — 28 skill nodes, 18 shapes, 87
  phrase pills, 56 chain arrows on the real repo at 59.9KB, stamped by git hash (+dirty
  when the tree is), byte-identical re-renders, zero model tokens.
- Gate: 15 fixtures (~810 assertions) seat-re-run exit 0 · eval 12/12 0-fail 0-warn ·
  doctor 10/10 · validate 0 · new-arm live smoke 4/4 · descriptions net SHORTER
  (always-on ~3,530 of the 3,600 ceiling).

## 3.8.0 — 2026-07-25

**The estate learns to remember as records and be seen as a river — and every defect the register found is fixed.**

- **The findings store** (`archive/findings.jsonl`, archivist-owned): skills emit compact
  finding records — ask · statement · labeled evidence · relation to the goal · status —
  validated at the door by 19 named rejection rules (one validator replacing a dozen
  per-skill lint scripts). Append-only; supersede/refute are tombstone records resolved by
  link-walking. researcher, decider, factcheck are rewired to the new sink (label and
  verdict grammars intact); marketresearcher/critic/explainer/recap migrate next release.
- **The river** (`graph.py river`): the session track drawn as a flow — main channel
  toward the goal bank, side channels merging back or dead-ending, backtrack loops,
  conflict rocks, a stone per finding, COORD milestones flying as flags on every render.
  Retroactively proven on today's real ledger: 53 records, 6 channels, 12 rocks,
  9 backtracks, 40 flags, 101KB self-contained, byte-identical re-renders. The
  token-efficiency law is in graph/SKILL.md: renders are script-built at zero model
  tokens — the model never hand-draws. Plus `links`/`orphans`/`stale` CLI queries.
- **The spend gate enforces the live policy** (was: the retired fable-only rule — a
  sonnet lane passed CLEAN): any post-2026-07-15 offload lane not on opus exits 4;
  policy-day entries grandfathered (the ledger cannot prove intra-day order; the
  day-after boundary is fixture-pinned); gpt/chatroom-gpt exempt-but-counted;
  `--since`/`--json`. Real ledger re-verdicts CLEAN — 0 post-policy violations, 1
  unverifiable `model=?` entry printed on its own line every run.
- **Receipt dedup at the stop-event key:** the COORD-AGENTS.md append had NO idempotency
  guard (the root cause of every duplicate — the flock was never the problem); 5 racing
  deliveries now land 1 line (negative control: HEAD's hook lands 2); resumed lanes still
  earn their new lines.
- **doctor grows to ten checks:** skills-dir-honest INSTALL FRESHNESS (UNCOMMITTED
  RELEASE / broken-link / SHADOWED — the third condition caught a live reinstall
  shadowing the runtime within minutes of existing), TOKEN BUDGET via `plugin details`
  (3,536 of the 3,600 ceiling — 64 headroom), HOOKS FIRED liveness heuristic. 73/73.
- **eval grows to ten checks:** REFERENCES-CITED (citing a reference you don't ship now
  fails, scoped to avoid cross-skill false positives) + `--baseline` diff mode. 18/18.
- **The no-secrets law is now code:** chatroom's post and gpt-bridge paths refuse 7
  secret classes (private keys, AWS/OpenAI/GitHub/Slack tokens, credential assignments,
  .env lines — a sha256 line still posts, asserted as the false-positive control),
  exit 5, class named, match never echoed. Plus `room.py join` and bridge spend receipts.
- **watch gets its script:** `watch.py due|probe|append` — dead sources and unchanged
  pages resolve at zero model tokens (strong-ETag conditional GETs; If-Modified-Since
  dropped after a real same-second-rewrite bug silently lost drift in fixture);
  `F-<id>` findings-store subjects work alongside legacy dossier paths.
- **gpt.sh + refuter gets teeth:** codex invocation, token parsing, and spend
  auto-receipt in one script (lane state persistent at `~/.claude/gpt-lane` — a
  conversation meant to remember cannot live in scratch; ratified); refuter briefs are
  minted by `brief.py` and returned reports lint-gated by `verdict_lint.py` (a CONFIRMED
  without a fenced reproduction is exit 5).
- Gate: 11 fixtures (500+ assertions) seat-re-run exit 0 · eval 10/10 exit 0 · doctor
  10/10 exit 0 · validate 0 · the store's first two real records (F-1 the shadow
  conflict, F-2 this release) rendered as river mode=findings+coord.

## 3.7.0 — 2026-07-25

**The routing law gets an enforcement layer — and the harness gets its capability register.**

- **`hooks/router.sh`** (second UserPromptSubmit hook): recognizes 14 task shapes and
  nudges the suite's verb in one ≤160-char line — prior-art→archivist (hoisted above
  research: "have we researched" is a superset), research→researcher, market-sizing,
  fact-check, decision, red-team, adversarial-review, planning, runbook, outbound,
  explanation, recap, handoff, recheck. Word-bounded matching; silent on slash commands,
  <4-word prompts, no match, or when the prompt already names the verb; every path exits
  0. The payload field was verified against the CLI binary, not assumed.
- **fable-mode Hard Rule 12 — the routing law:** overriding a route deliberately is fine;
  silently ad-hoc'ing a job a skill already owns is the violation. Authority: oracle's
  intake table.
- **eval grows to nine checks:** #9 ROUTER — router.sh wired under UserPromptSubmit,
  compiles, no set -e, exits 0 everywhere, and every verb it can emit names a real skill
  dir. Fixtures: router-fixture.sh 21/21 (14 routes, 5 suppressions, 2 malformed-stdin);
  eval fixture 12/12 with two ROUTER-only injections. All seat re-run at the gate.
- **docs/CAPABILITIES.md — the capability register:** every skill and toolset cataloged
  (does · how · concrete upgrades · biggest gap) from a three-lane analyst pass plus a
  seat-written toolset half; build priorities re-ranked. Standout finding, now priority
  #2: `spend.py`'s exit-4 gate still enforces the retired fable-only rule — a
  sonnet/haiku lane passes CLEAN today. Fix scheduled next.
- Skills-dir reload note: hook changes apply on `/reload-plugins` or restart; SKILL.md
  edits hot-reload from the live tree.

## 3.6.1 — 2026-07-25

**Hotfix: the manifest's redundant hooks reference — the double-fire root cause, now a load failure.**

- Removed `"hooks": "./hooks/hooks.json"` from plugin.json. The standard `hooks/hooks.json`
  is auto-loaded; the explicit manifest reference made current CLIs (≥2.1.x) refuse the
  plugin outright ("Duplicate hooks file detected" — `claude plugin list` showed
  `✘ failed to load`, i.e. fresh sessions got NO harness), and on older loaders the same
  redundancy silently registered every hook TWICE — the confirmed root cause of the
  doubled SessionStart/UserPromptSubmit echoes, the duplicate SubagentStop receipts in
  COORD-AGENTS.md, and the spurious "session ended" auto-cushion lines.
- Dev-machine runtime switches to a skills-dir plugin (`notrest@skills-dir`): a symlink to
  the live git working tree, discovered in place — zero cache copies, `git pull` +
  SKILL.md live-reload replace the marketplace update dance. The marketplace flow remains
  the consumer install path and the release ritual is unchanged for it.

## 3.6.0 — 2026-07-25

**The rightsizing pass — the harness stops reciting its own laws.**

- **Standing per-session injection cut ~29%, measured** (true chars; tokens estimated at
  chars ÷ 3.8): 26,386 → 18,657 chars (≈6,944 → ≈4,910 tok) from the repo-side changes
  alone; ≈4,614 tok once the companion machine-side global-CLAUDE.md slim is applied.
  Every cut removes a restatement, not a rule — no law dropped, no trigger dropped.
- **Hook echoes become standing orders, not essays.** SessionStart discipline echo
  1,225 → 283 chars; offload-policy echo 1,805 → 397 and still operative standalone
  (explicit `model "opus"`, the fork ban and why, omission = violation, agentswarm,
  the persistent-builder-lane ritual, no seat `/model`-switch). The per-prompt COORD
  nudge went 177 → 96 chars — and its stale "compact at ~40 lines" instruction, which
  contradicted the ROLLS-at-500 law, is gone.
- **Sixteen skill descriptions dieted to ≤500 chars** (the always-on listing:
  18,253 → 13,816 chars, −24%). A description is a trigger-router, not a manifesto —
  rationale prose belongs to the on-invoke body. All 28 front-matters re-verified with
  a real YAML load; every `/slash` trigger kept; agentswarm's description still carries
  the explicit-opus + fork-ban fingerprint that eval checks for.
- **Foundation dedupe:** repo CLAUDE.md 2,422 → 1,480 chars — Protocol is three pointer
  lines; every Project fact (manifest pair, tombstone pin, release ritual, ledger laws,
  ship gate) kept. Each law now has one authoritative home plus pointers instead of
  4–5 always-on recitals.
- Disclosed residual: the 12 already-lean descriptions were left alone (six sit just
  above 500 chars; dieting them buys ~160 tok more). Measurement and build receipts
  are in `spend/ledger.md`.

## 3.5.0 — 2026-07-25

**The maiden compile lands, the ledger becomes permanent, and the scanner learns to distrust its own vocabulary.**

- **COORD is never compacted again — it ROLLS (owner design).** Archiving *moves* lines (a
  crash window, and nobody ever reads the archive); sealing *preserves* them. Past 500
  ledger lines the active `COORD.md` is sealed byte-identical as `COORD-001.md` (then 002…)
  and a fresh volume opens carrying a `> Continues COORD-001.md · volume 2` pointer;
  `COORD-AGENTS.md` seals at 1000. Sealed volumes are immutable; sessions read the active
  tail; recap/compile/archivist read every volume. Crash-safe ordering (seal + fsync, then
  atomic replace). The director-detect glob now excludes numeric suffixes so a volume can
  never masquerade as a lane blackboard. 31-assertion fixture, md5 identity proven across
  two rolls. Legacy `COORD-ARCHIVE.md` files are left untouched.
- **MAIDEN COMPILE — the release ritual is now `compile/release-ritual/ship.py`:** 853 lines
  of stdlib Python making **zero model calls**, replaying **five historical ships**
  (v2.16.0 → v3.1.0, across the rename) at `surfaces=9 · differs=0 · PARITY PASS` each,
  ~775 ms per ship-pipeline. On the v3.1.0 replay it also *corrected* three count-surface
  inconsistencies the human ship had shipped. Evidence label is **DIRECTIONAL, not
  PROVEN** — stated on the verdict screen, not a footnote: two of the nine compared
  surfaces are round-trip identities that cannot fail, and two count surfaces are
  rewritten without being compared. An independent refuter returned 15 findings including
  three CONFIRMED criticals (a JSON key reorder that de-pinned the tombstone and committed
  at exit 0; a validator failure string-matched into "CLI absent → proceed" reaching
  push/install; the earlier parity overclaim) — all fixed in one bounded round, both
  critical repros re-run at the seat. One-time compilation cost, receipted and NEVER
  amortized: **542,492 observed opus tokens** across four lanes. The runtime stays
  **isolated and NOT installed**; USE IT is NOT-LIVE-VERIFIED; INSTALL IT is described,
  not executed. Dossier + background + render-gated verdict page ship beside it, and
  `.gitignore` was narrowed so hand-built runtimes are tracked as source while only the
  derived scan output stays ignored.
- **compile scanner defect fixed:** its top candidate was `lan` at 31× — it was clustering
  the seat's own word for a lane, because spend purposes share harness vocabulary by
  construction and the deliberate inverse-IDF weighting made those tokens heaviest. Now a
  24-word estate stopword list (lane, round, seat, gate, fixture, shipped…) plus
  weak-source demotion: a candidate whose evidence is >80% spend purposes with no COORD
  support can never outrank a COORD-supported one. COORD says what was *asked and landed*;
  spend says what a lane was *called*. The junk cluster no longer forms; the release ritual
  holds #1 at 18×, its alias carried across a slug change by signature match.
- **The retired external eval runner is quarantined:** `plugins/notrest/evals/` →
  `evals-legacy-external-runner/` (history preserved) under a RETIRED banner carrying its
  receipts; the live gate is `/eval` + `/doctor`, stated wherever the old dir was cited.
- doctor's gitignore check learned that a derived directory holding source takes per-file
  rules, not a blanket one — and a 28 MB fixture scratch tree that the narrowed ignore
  would have committed was caught and excluded.

Ship gate, both green on the shipped tree: **eval PASS — 28 skills, 0 fail, 0 warn, 0.06s,
0 model tokens**; **doctor HEALTHY — 8/8, exit 0**.

## 3.4.1 — 2026-07-25

**The seat stops doing bookkeeping — receipts write themselves.**

Measured tax: the seat hand-ran the same lane-close trio **34 times today** — grep the
agent transcript for its model, run `spend.py log` with the token count, append the COORD
line — roughly 150 tool calls of pure clerical work. The compile scanner had already
ranked that exact shape candidate #1 (15×) and #5; the estate saw it before the seat did.

- **Auto-receipt in the SubagentStop hook.** `agent-ledger.sh` already parsed every
  finished agent's transcript for model and size; it now also sums per-message usage and
  appends the spend receipt itself — fields byte-identical to `spend.py`'s own writer (so
  `report` still parses and still exits 4 on a routing violation), with the agent id as a
  trailing `agent=<id>` token so it never pollutes `purpose`. Idempotent by design: the
  guard is a substring test inside the flock'd critical section, so a re-fire or a
  concurrent replay cannot double-log (proven: two runs, identical md5, one line).
  Honest grading survives the automation — a transcript with usage data writes
  `grade=observed`; one without writes `tokens=unknown grade=estimate` rather than a
  guess. A repo with no `spend/` ledger is opted out: nothing is created.
- **`render-check.sh`** — the render gate as one command: serve on a free 127.0.0.1 port,
  prove HTTP 200, print the URL, reap with `--close`. Replaces a five-call dance the seat
  ran all week.
- **`gategrep.sh`** — whitespace-normalized phrase counting. A naive `grep -F` returns a
  false zero on a phrase wrapped across markdown lines; that defect burned the seat twice
  today, once nearly causing a bad gate call.
- 43-assertion fixture covering all three, plus the opt-out and no-usage paths.

Ship gate for this release, both green on the shipped tree: **eval PASS — 28 skills, 8
checks, 0 fail, 0 warn, 0.07s, 0 model tokens**; **doctor HEALTHY — 8/8, exit 0**.

## 3.4.0 — 2026-07-25

**We build our own instruments: /eval and /refuter. Twenty-eight skills.**

Owner ruling, with receipts: the external `claude plugin eval` is OUT. It spins a full
agentic model session per case per arm per run plus LLM judges — ~13 minutes and $4.58
per pass, opaque to the seat, uncancellable mid-flight, and in 45 minutes of grinding it
produced zero fixes. That is the exact anti-pattern this harness exists to kill.

- **New skill `eval` — law conformance as a STATIC FINGERPRINT.** The insight: a
  well-encoded law leaves a fingerprint in the shipped text; check the fingerprint, not
  the behavior. Eight checks read the files directly — every documented spawn names
  explicit opus and bans forks; every claim-making skill carries a label/verdict grammar;
  every "script owns the scanning" claim has a script that exists and compiles; every
  estate instruction is append-only or script-routed; every worker has its self-check and
  chains; frontmatter has name == dir, a description YAML accepts, and a real /slash
  trigger; the safety laws are literally present (a draft is never sent, a dead source is
  never a refutation, compile never auto-installs); hooks are silent-on-failure and wired.
  **0.08 seconds, zero model tokens, 28 skills** — roughly 10,000× faster than the runner
  it replaces, and it found two real defects on its first run that the expensive one never
  did (game-forge's description carried no /slash trigger; compile shipped a fixture its
  SKILL never named). Genuinely behavioral questions get a bounded opus one-shot with a
  CODE grader — never an LLM judge — opt-in, outside the ship gate.
- **New skill `refuter` — the adversarial reviewer, promoted from improvisation to
  contract.** Its standard: the run hours earlier that returned 15 findings on a compiled
  release runtime, three CONFIRMED criticals — a JSON key reorder that de-pinned a
  version-pinned tombstone and committed at exit 0; a validator failure string-matched
  into "CLI absent, proceed" reaching push/install; and proof that a "5/5 PARITY PASS" was
  overclaimed. Now shipped as a brief template, a six-rung attack ladder (irreversible
  paths → integrity invariants → claim honesty → partial-failure states → test honesty →
  environment), a verdict grammar where CONFIRMED requires a pasted reproduction and
  PLAUSIBLE requires a concrete scenario (anything else is deleted, not filed), the
  requirement to name what SURVIVED, and a ~12-call budget: three narrow refuters beat one
  broad one. It finds; it never fixes, and never grades its own findings.
- eval's own first verdicts fixed in the same release; doctor remains the install/estate
  check, eval is the law check — the distinction is stated in both skills.

## 3.3.0 — 2026-07-25

**/doctor — the harness passes its own physical. Twenty-six skills.**

A read-only self-check born from this week's silent failures, each of its eight checks
citing the real defect it descends from: SKILL frontmatter a YAML load would reject (the
unquoted colon-space that made three skills invisible for weeks), manifest + tombstone
version pins (tombstone forever 9.0.0), skill-count drift across every place the number is
spelled, hook scripts that exist and parse plus rename residue, estate integrity (COORD
header, agent ledger, spend report, compile candidates), installed-vs-repo-vs-clone drift
(the stale-marketplace-clone class), unanchored gitignore rules that swallow skill dirs,
and stale render stamps. Reads only — never repairs; every FAIL prints its fix command.
43-assertion fixture: nine injected defect classes each flip exactly one named check.

**It earned its keep before it shipped:** doctor's first live run against this repo failed
its own count check — 26 skill dirs vs four prose surfaces claiming 25/25/23/23, the
third count-drift incident in two releases (lowercase and rephrased variants kept dodging
narrow regexes). Counts reconciled robustly to twenty-six; the ship gate for this release
was doctor's own verdict: HEALTHY — 8/8, exit 0. That is Ring 1's thesis made mechanical:
the harness's claims about itself are now checked by the harness.

## 3.2.1 — 2026-07-25

**The crash cushion closes — a fifth hook completes the estate's insurance.**

- **New SessionEnd hook (`session-end.sh`):** when any session terminates in a git repo,
  (1) if the COORD ledger's last line is neither a deliberate [sessionend] close nor an
  existing cushion, it appends ONE auto-cushion line — so a session that dies without
  /sessionend still leaves a resume pointer (the cushion line's presence in a tail IS the
  abrupt-end signal); dedupe guard: never two cushions in a row. (2) Ledger auto-compaction,
  finally exercised for real: COORD.md >40 ledger lines → newest 30 kept, oldest moved whole
  into COORD-ARCHIVE.md (machine header, append-only); COORD-AGENTS.md >100 → newest 60.
  Archive-append+fsync lands BEFORE the live file is replaced (temp + os.replace), so the
  only crash window duplicates a line into the archive — never loses one; an inode guard
  yields to concurrent writers; a marker-less file is refused, not "fixed". Silent on
  success and failure, always exit 0. 53-assertion fixture seat-run green, including
  byte-identical archive⧺live reconstruction proofs.
- Honest gate notes, kept verbatim in the ledger: the lane corrected the seat's own brief
  with evidence (the "~40 lines" trigger figure was wc -l including headers; the real
  ledger was 31, so live compaction rightly did not fire — proven instead on a shadow copy
  seeded from the real file); and the lane's live test left a cushion line in an alive
  session's ledger — contextually false, corrected by appendix per the append-only law.
- sessionend Phase 3.6 documents the split: the hook is the always-on cushion; /sessionend
  remains the deliberate, richer close.

Known residual, deferred one slice: one marketplace-description count phrase
("twenty-three natural-language-invocable") survived two bump passes — the count-variant
whack-a-mole that doctor's check #3 exists to end; reconciles at doctor's ship.

## 3.2.0 — 2026-07-25

**/draft — the outbound verb. Twenty-five skills.**

Every other skill ends at "you now know / you decided"; draft turns the dossier into the
thing you SEND — email, exec memo, slack update, one-pager, status update, each a skeleton
with a hard length budget (references/formats.md). One law makes it trustworthy:
**[fact] vs [framing]** — every factual sentence traces to a source line in a
bottom-of-background source-map and keeps its honesty label; framing choices are LISTED as
choices; persuasion never upgrades a label ([estimate] stays hedged, [unverified] drops or
carries its hedge — never becomes fact). Numbers never invented, quotes never manufactured,
recipients never guessed — and A DRAFT IS NEVER SENT: sending is the owner's act in the
owner's client, and a draft file is never evidence a message was delivered. Chains:
decider/researcher/recap → draft → (high-stakes) critic → the owner sends. 21-assertion
fixture seat-run green; built in 13 tool calls / 3.7 minutes under the new speed law,
shipped alone under the new release-slicing law.

Also fixed at the gate: the v3.1.0 count bump missed two lowercase/rephrased count
variants — docs claimed twenty-three while twenty-four skills existed. Counts now
twenty-five everywhere; the incoming doctor skill's count check exists precisely for
this defect class.

## 3.1.0 — 2026-07-25

**/compile — the workflow compiler: the estate learns to optimize itself. Twenty-four skills. Plus the speed law.**

Adopted from the owner's "Agent Workflow Compiler" contract — but rethought before a line
was integrated, per the owner's explicit order. The original is a model-first mega-prompt;
in this architecture it split into three parts with different owners:

- **Detection is a script** (`compile.py scan` — stdlib, zero model tokens, graph.py
  economics): mines COORD.md ask-shapes, agent-ledger purposes, and spend receipts for the
  same job done ≥3 times; emits machine-written `compile/candidates.md` + `.json` with
  occurrence counts, evidence pointers into the ledgers, ripeness, and statuses that
  survive rescans (signature-matched carry-over, so a DECLINED ruling never resurfaces
  under a renamed slug). Maiden scan on this very repo: the release ritual, #1, 9
  occurrences, RIPE — found by df-weighted clustering with the threshold swept against
  real data and cited in-code.
- **Compilation is a ritual run**, not a mega-prompt: /compile <candidate> reconstructs
  the functional contract from the trail with recap-grade citations, one builder lane
  emits the isolated runtime under compile/<slug>/, an independent refuter attacks it,
  the seat gates multi-way and fair-benchmarks against the history it came from (the
  estate IS Method A's historical side; equivalent raw inputs; judge calls excluded;
  PROVEN/DIRECTIONAL/UNMEASURED evidence labels; one-time compilation cost receipted by
  spend and NEVER amortized). Cheaper-but-worse is failure; the owner is final arbiter.
- **Installation is a release**: compiled runtimes stay isolated until the owner ships
  them through the normal ritual. DEMO / USE / INSTALL tiers preserved from the original.

Known to every session, automatically: the SessionStart hook nudges when a ripe NEW
candidate exists (one line, reads the last scan, silent otherwise — corrupt-JSON-proven);
sessionend runs the scan at estate close and names the top candidate in the handoff;
oracle's intake reads the candidates file and its Leverage inventory offers compiled
runtimes as tooling; archivist indexes the candidates as the estate's third dimension;
agentswarm points lanes at compile/ before they re-derive paid-for work.

**The speed law (owner directive — 15-30 minute lanes are the arrangement failing its
user):** receipts showed wall-clock tracks tool calls near-linearly (20-call lanes ≈ 3.5
min; 72-77-call monoliths ≈ 22-24 min). Codified in agentswarm + the hook: greenfield
builds DECOMPOSE into parallel narrow lanes along file boundaries (core lane persists for
feedback rounds; docs rows are one-shots); builders get a ~20-line style capsule inline,
never a reading list; one fixture run per lane, at the end (the seat re-runs at the gate
anyway); and release slicing — gated work ships, never held hostage to an unrelated lane.
Proof it works: the round that wrote the law ran 28 calls in 4.4 minutes.

## 3.0.0 — 2026-07-25

**The harness gets the company's name: `oracle-suite` → `notrest`.**

It outgrew "a suite of skills." What ships now is a session HARNESS by Not Rest Inc. —
discipline auto-anchored into every session, delegation through agentswarm's Opus lanes,
an estate that writes itself (COORD per prompt, COORD-AGENTS per agent, spend per lane),
continuity with a flown successor escort, and an eval suite that grades the whole thing.
So it carries the company's name.

- **Install identity changed** — `claude plugin install notrest@notrest`; skills invoke as
  `/notrest:oracle`, `/notrest:agentswarm`, … The GitHub repo is now
  `notrestai/notrest` (owner-renamed; verified live before ship). `git mv` moved
  `plugins/oracle-suite/` → `plugins/notrest/` with history preserved — 77 entries staged
  as renames. Hook echo prefixes are `[notrest]`; every `oracle-suite:<skill>` reference
  swept. History files (CHANGELOG, COORD*, spend/ledger, evals/results) keep the old name
  verbatim — receipts are never rewritten.
- **Nobody strands:** a frozen `oracle-suite` tombstone entry ships at v9.0.0 whose only
  behavior is one SessionStart line telling existing installs where the harness went and
  how to move. Pinned forever — never bump it.
- **Pre-existing bug caught by the rename gate and fixed:** three skills — `recap`,
  `oracle`, `agentswarm` — had unquoted YAML `description:` scalars containing colon-space
  (`track: a`, `off": load`, `OPUS: no`). Their frontmatter failed to parse, so at runtime
  they loaded with EMPTY METADATA — natural-language triggering silently dead for all
  three. Proven pre-existing (byte-identical to HEAD; reproduced from `git archive HEAD`),
  now quoted and validating. The lane was renaming files and found a live defect on the
  way past: exactly what gates are for.

## 2.17.0 — 2026-07-25

**The integration release — oracle notices what's installed, facts get shelf lives, and the suite grades itself. Twenty-three skills.**

Three Opus lanes in one batch, each seat-gated:

- **Leverage auto-inventory (oracle):** the Leverage question is never asked blind again —
  the session inventories its own environment first (context skill listing at zero tool
  calls; installed_plugins.json at most one read; MCP surfaces sorted live vs
  needs-connecting) and asks as a 2-5 item proposal filtered by the Objective. Domain
  packs route outward with the receipts kept inward: "domain packs are workbenches; the
  estate is the workshop." The inventory is a report, not a guess — auth-gated connectors
  are never counted as usable; an empty machine gets one honest line. The inventory seeds
  the scaffolded CLAUDE.md and rides the handoff template so successors inherit it.
- **New skill: `watch`** — factcheck's calendar-time sibling. `/watch add` pulls a
  dossier's load-bearing [cited] claims (verbatim, ~10 cap) into watch/watchlist.md;
  `/watch run` re-verifies the due ones (~2 searches/claim) into a dated drift log —
  HOLDS / DRIFTED / DEAD-SOURCE / UNVERIFIABLE, every run stamping what it actually
  fetched; a dead source is never a refutation. Scheduling through the scheduled-tasks
  MCP where present, always owner-confirmed, honestly manual where absent. 71-assertion
  fixture incl. a 17-case negative battery; the SKILL's own examples are validated by the
  same validator so doc and contract cannot drift.
- **Suite evals (release-gate):** 5 cases + 13 graders for Claude Code's plugin eval
  runner (format extracted from the runner itself and proven empirically — bad keys
  rejected at $0.00; early-access gate documented). First gated run, verbatim:
  graph-zero-tokens **with 1.00 / without 0.25 / Δ +0.75** — the plugin measurably causes
  the right behavior; offload-policy 0.20/0.00; coord-discipline 0.00/0.00;
  routing-intake 0.00/0.00; honesty-labels errored (exit 1). Mean Δ +0.19, $4.58, 792s.
  SEAT RULING, stated not smoothed: ship — day-one calibration findings, not regressions.
  The bare eval sandbox (no git root, no hooks, no session context) is far from a real
  session, so the three sub-threshold cases need --keep-temp diagnosis to split
  case-miscalibration from genuine gaps — that is the evals lane's standing round-2
  backlog, and the numbers stay in this changelog either way.

## 2.16.1 — 2026-07-25

**`/graph` now means "show me the graph" — scan, then open, no questions.**

- **Default behavior rebuilt as an imperative flow:** every `/graph` invocation refreshes
  the scan (cwd's git root; a path argument overrides; `all` builds the merged PM view),
  then ALWAYS OPENS the viewer via an environment decision list — browser pane over a
  localhost port loop (8790-99, curl-proven before handing over; the pane snapshots
  file:// pages, so serving is the reliable door), plain macOS via `open graph/graph.html`
  (self-contained file), else the absolute path — closing with nodes · edges · generated ·
  which door was used. The lane executed its own documented blocks verbatim as the test
  (81 nodes/149 edges, port 8790, pane JS alive). oracle's intake refresh stays scan-only
  and silent; the open belongs to the explicit ask.
- **Hook papercut fixed:** the director-detect nudge no longer false-fires on the
  machine-written ledgers (COORD-AGENTS.md, COORD-ARCHIVE.md, COORD-AGENTS-ARCHIVE.md —
  the third excluded proactively by the lane). Real lane blackboards and legacy
  FABLE-COORD*.md still trigger it. Three-case behavior verified at both the lane and the
  seat: ledgers-only silent, lane-file nudges, legacy nudges.

## 2.16.0 — 2026-07-25

**recap + graph — the estate learns to tell its story and draw its map. Twenty-two skills.**

- **New skill: `recap`** (the debrief, renamed simple) — walks the recorded trail in
  timestamp order (COORD, COORD-AGENTS, git, spend, dossiers) and delivers the complete
  decision track: a narrated timeline dossier, a who-was-consulted table with transcript
  citations, and a self-contained decision-map HTML (swimlanes over time; every node
  opens its trail citation). Claims cite trail lines or commits; anything without one is
  [unverified]. Fixture was the real thing: this repo's own v2.9→v2.15 story, three
  citations seat-verified against the ledgers (including the sonnet-lanes-pre-policy
  proof and the hook recording its own birth in the same minute as its ship commit).
  Timestamps mandate TZ=UTC git dates — author-local dates sort the story wrong.
- **New skill: `graph`** — the Obsidian-style file graph, script-built at zero model
  tokens (stdlib scanner: wikilinks, md links, imports, source/estate references; git
  ls-files scoping; binary sniff). Emits graph/graph.json + a self-contained
  force-directed viewer (vanilla canvas, both themes, drag/zoom/search/pin, estate nodes
  purple and provably central — COORD.md degree 27 on this repo). `register` + `all`
  merge every registered project into ONE connected map — the PM-session view
  (~/.claude/oracle-projects.txt is the registry; per-project cap so no repo drowns the
  view; estate filenames stoplisted from cross-linking so projects don't all wire to all).
  oracle intake now refreshes the scan (script-only, cheap) and offers registration once.
- **Gates that earned their keep, both directions:** the seat's render gate caught the
  viewer's canvas dpr/resize defect (stale backing store, no CSS pinning) — fixed with a
  sizeCanvas contract + ResizeObserver + per-frame guard, locked by 7 new fixture
  assertions (63/63); and the graph lane caught the SEAT's ship-blocker — an unanchored
  `graph/` gitignore line that was silently ignoring the entire new skill directory
  (anchored to `/graph/`; skill tracked, output still ignored). A gate that only reads
  the lane's report is not a gate — in either direction.
- sessionend puts a produced recap in the handoff; archivist indexes recap/ dossiers;
  README/TUTORIAL/manifests reconciled to twenty-two.

## 2.15.0 — 2026-07-25

**fable-swarm becomes agentswarm — the swarm was an arrangement, never a model; and it is uncapped by design.**

- **Renamed + seat-agnostic:** `git mv` to `skills/agentswarm` (history preserved; legacy
  `/fable-swarm` still triggers it). THE SEAT is the main session's model — Fable when
  Fable is driving, otherwise the latest Opus — and the seat stays the seat regardless:
  decompose, judge, apply, gate. Every law survives generalization: offloads on explicit
  `opus` (the alias) from ANY seat; the fork ban holds everywhere (under a Fable seat a
  fork is a billing violation, under an Opus seat an unlabeled lane defeating the ledger);
  never `/model`-switch the seat; and "Fable never rides in a subagent" stays verbatim as
  the one Fable-specific absolute. Hook, fable-mode, fable-director, both READMEs,
  TUTORIAL, foundation templates, manifests, repo CLAUDE.md all renamed; CHANGELOG,
  ledgers, and receipts stay history, untouched.
- **No caps — owner directive, evidence-backed:** the swarm imposes no numeric limit on
  lanes, fan-outs, or simultaneous swarms; scale is decided by the job's decomposition,
  never by a count. Proven scale cited in-skill from the owner's dig.rest DIR sessions
  (measured 2026-07-23): 16/15/11 agents in single sessions, a ~1 MB lane transcript, and
  40 machine-written COORD-AGENTS.md entries. Harness ceilings are the owner's dials
  (Workflow's ~16 concurrent slots auto-queue; "Dynamic workflow size" in /config);
  multiple swarms and separate sessions compose safely over the append-only, flock-guarded
  estate — the DIR + DIR2 precedent. Uncapped is safe because the contract is already law:
  narrow lanes, tight returns, receipts per lane, trail-walk at the gate.

## 2.14.0 — 2026-07-25

**The successor escort — handoffs become a flown window, not an instant; and the estate floats to latest Opus.**

- **Escort window (sessionend live-handoff-template):** the dig.rest DIR/DIR2 pattern,
  codified. Near context-full + "new session" = the trigger; sessionend runs files-first;
  the owner one-click-creates the successor (honest limit, probed: NO create-session tool
  exists — the session surface is read/write into existing sessions only); the predecessor
  sends the orientation immediately, then ESCORTS the successor's first ~10 responses —
  reading its turns via list_events and proactively correcting via send_message the moment
  it sees missing context, a wrong branch, or re-derivation of known ground. START-HERE's
  "Live line:" becomes a LIST with a domain per row when multiple predecessors are alive;
  referral etiquette (oracle side): trail first, then ONE consolidated batch per
  predecessor, domain-matched; stand-down is explicit, archive stays owner-confirmed.
- **Model unpin:** the estate never names an Opus point-version again — V4 topology,
  KICKOFF, and the spend example now say latest Opus / the `opus` alias / "the id observed
  in the lane transcript". Proven live this build: the same `model: "opus"` spawn ran
  claude-opus-4-8 lanes yesterday and claude-opus-5 lanes today, zero policy edits.
  History (receipts, changelog, example ledgers) stays verbatim — never rewritten.
- **First production day of the v2.13.0 agent ledger, self-proving:** COORD-AGENTS.md
  wrote itself during this very build — the escort lane's entry carries the real model
  (claude-opus-5), byte count, closing line, and transcript path. Two papercuts parked
  for a future round: duplicate SubagentStop firings produce twin lines, and a transcript
  absent at hook time yields model=?/bytes=? (contract held — silent, valid, id+path known).

## 2.13.0 — 2026-07-21

**The agent estate — every agent leaves a record; the seat judges by the trail; speed is the owner's experience.**

Built by one persistent Opus builder lane across THREE resumed rounds (the seat-builder
ritual's first full production run), refuter-hardened, every round seat-gated.

- **New SubagentStop hook (`agent-ledger.sh`):** every completed agent in a git repo is
  auto-indexed into `COORD-AGENTS.md` — id · model · last conclusion · transcript path —
  machine-written at zero model-token cost. Silent/exit-0/session-safe by contract;
  flock-serialized appends (60-way concurrency fixture-proven, zero torn lines).
  Refuter-confirmed fixes baked in: model read from the assistant messages themselves
  (never a decoy "model" string or an injected <synthetic> row), payload fields flattened
  so hostile ids can't forge ledger lines, whitespace-damaged files recover their header,
  all-? noise rows skipped. 44-assertion fixture across 8 cases, exit-checked at the gate.
- **archivist indexes the agent ledger:** `index.py` now surfaces COORD-AGENTS.md (path +
  entry count) in oracle-index.md — "which agents were consulted and what each concluded"
  becomes a searchable dimension of the project's decision pattern; entries point at full
  transcripts for deep audit.
- **Trail-walk — how the seat judges (fable-swarm):** before accepting lane work or gating
  a ship, walk the record in timestamp order — COORD tail → COORD-AGENTS entries →
  transcripts where a one-liner isn't evidence → git diff → spend. Decisions cite trail
  entries; when memory and the trail disagree, THE TRAIL WINS. Survives compaction and
  rotation. One-line PROVE amendment in fable-mode to match.
- **Gate every return, multiple ways (fable-swarm):** the seat never accepts a lane's
  self-reported verification — re-run it exit-code-checked, parse-check by artifact kind,
  grep every claimed edit, read the core code, refuter the riskiest artifact, and
  render-and-look when the deliverable is visual. "A gate that only reads the lane's
  report is not a gate."
- **Speed discipline (fable-swarm + hook):** the owner-experience contract — narrow
  parallel lanes over one broad lane (wall-clock is the slowest lane), material handed
  inline so lanes work at call 1, ~10-call budgets on empirical lanes, gate intensity
  tiered by blast radius, persistent QC lanes resumed like builders, and never idle the
  seat on a non-ship-blocking lane. The two most UX-critical levers ride the SessionStart
  hook into every session.

## 2.12.0 — 2026-07-21

**The seat-builder ritual — persistent builder lanes (owner-ratified 2026-07-21).**

- **fable-swarm gains "Persistent builder lanes":** substantive builds run through ONE
  persistent Opus builder lane per domain — the seat specs (grep-able done-when), the
  lane builds and returns tight, the seat gates every round (exit-code-checked
  verification, never piped through tail; bundle-grep the claimed change; ledger line
  per round) — and feedback rounds RESUME THE SAME LANE via SendMessage, never a fresh
  spawn. The lane's accumulated context of the code it wrote is both the token saving
  (round N costs the delta, not re-onboarding) and the quality keeper (proven across
  6+ live rounds). Diagnosis/exploration stays parallel one-shot lanes.
- SessionStart hook line + global foundation guidance updated to carry the ritual;
  also stamps docs/oracle-skill-flow.html to v2.12.0 per the release ritual.

## 2.11.0 — 2026-07-15

**Comprehensive four-lane swarm review — every cross-reference gap closed.**

Four concurrent Opus review lanes (continuity web · rename seams · model policy · docs/counts)
audited the whole estate; all transcript-verified on claude-opus-4-8 and receipted in the
spend ledger. 21 findings, all seat-verified before applying:

- **CRITICAL seam (rename lane): the hook-created COORD.md broke fable-director bootstrap.**
  The scaffolder's exists-check saw the hook's session-ledger stub and silently SKIPPED
  writing the SHIP blackboard; MODE DETECT's "no COORD*.md = new project" could never be
  true. Fixed + fixture-proven: the scaffolder now upgrades a PROTOCOL-less COORD.md in
  place (preserving its ledger lines), MODE DETECT keys on structure (## PROTOCOL, lane
  files, kickoff/plan presence — incl. legacy FABLE-COORD*.md), and the scaffolder's ledger
  stamps now match the hook format ([YYYY-MM-DD HH:MMZ]).
- **Continuity web (5):** fable-mode's ORIENT now includes the COORD ledger tail (it was
  the suite's most-read resume order and had the exact omission just fixed in START-HERE);
  BANK now names the per-prompt ledger append; pre-compact.sh points at the COORD line as
  the crash cushion when carrying on; the live-line opener + orientation message route
  through the ledger tail (claims without a ledger line are [unverified]); sessionend's
  "four files don't overlap" framing now names COORD.md as the fifth, hook-owned tiebreaker.
- **Model policy:** all 20 skills' spawn directives verified opus-only with fork-bans; the
  one gap was introspect's shipped example ledger showing a pre-policy haiku control — now
  carries a dated post-policy note (history preserved, not falsified).
- **Docs/counts (7):** inner plugin README "Nineteen"→"Twenty" + fable-swarm bullet added;
  TUTORIAL rewritten to reality (Twenty skills, THREE hooks incl. UserPromptSubmit/COORD,
  the HANDOFF → COORD tail → STATE → CLAUDE resume order, 8 missing skills added to the
  which-skill-when table, offload-policy + spend line in Costs, marketplace-cache update
  caveat); repo CLAUDE.md's stale version string replaced with a non-rotting pointer.

## 2.10.1 — 2026-07-15

- **START-HERE now routes through the COORD ledger:** the resume read order is
  HANDOFF (curated snapshot) → **COORD.md ledger tail** (per-prompt trail with evidence,
  current to the last prompt even when the session died before sessionend) → STATE →
  CLAUDE. Self-check adds: the status files must agree with the ledger tail — the trail
  is the tiebreaker, it was written when the work landed.

## 2.10.0 — 2026-07-15

**COORD.md everywhere — the fable-coord ledger, generalized to every session.**

- **`FABLE-COORD*.md` renamed to `COORD*.md`** across the whole suite (fable-director
  SKILL + V4 plan + kickoff + coord-scaffold + spawn-lanes + scaffolder script + hook +
  README): the ship/main file is `COORD.md`, lane blackboards are `COORD-<LANE>.md`,
  the archive is `COORD-ARCHIVE.md`. Legacy `FABLE-COORD*.md` repos still detected.
- **SessionStart auto-creates `COORD.md`** at the git root of any repo a session starts
  in (skips non-repos, never clobbers, honors legacy files): an append-only session
  coordination ledger — one line per substantive prompt when its work lands
  (`[UTC] [session] ask -> landed | evidence`), honest status, compact to
  COORD-ARCHIVE.md at ~40 lines.
- **New UserPromptSubmit hook (`coord-nudge.sh`)** — the mechanism that makes
  "every prompt writes to it" real: when COORD.md exists, each prompt carries a
  one-line append reminder. Deliberately one short line — it fires every prompt.
- **oracle** now reads the COORD ledger tail at intake (the trail of what prior
  prompts actually landed), appends an intake line, and carries the per-prompt
  discipline; **sessionend** appends the closing line and compacts the ledger past
  ~40 lines. Director arrangements are detected by lane files (`COORD-<LANE>.md`),
  distinct from the bare session ledger.

## 2.9.1 — 2026-07-15

**The swarm's first live run reviewed its own release — fork loophole closed, ladder residue purged.**

Two concurrent Opus lanes (a QC refuter on fable-swarm's contract, a repo-wide residue sweep)
ran as the v2.9.0 smoke test; both verified on `claude-opus-4-8` from their transcripts and
receipted in the spend ledger. Their findings, applied:

- **Fork loophole (CONFIRMED, refuter lane):** the Agent tool IGNORES `model` for
  `subagent_type: "fork"` — forks always inherit the parent, so a fork from a Fable seat
  rides Fable while the ledger records the intended opus, invisible to the exit-4 gate.
  Now banned in fable-swarm's model rule, the SessionStart hook line, director's stage
  spawns, critic's lens spawns, and the foundation guidance.
- **Ladder residue (sweep lane, 6 lines / 5 files):** sonnet/haiku-by-difficulty language
  survived v2.9.0 in the plugin README, introspect's control-arm spawn, director's stage
  routing + self-check, critic's panel lenses, and spend's own header. All now opus-only,
  consistent with the owner policy.
- **Scoping fixes (PLAUSIBLE findings, applied):** fable-director Rule 1's "never spawn
  subagents" now names its regime (metered-key) and points subscription sessions at
  fable-swarm; fable-mode's multi-agent profile now says the harness is the wire for
  in-session delegation and files-are-the-wire is the multi-session case.

## 2.9.0 — 2026-07-15

**fable-swarm — the fast delegation arrangement + the opus-only offload policy.**

- **New skill: `fable-swarm`.** Fable-director's blackboard/watch machinery was built for a
  metered-key constraint that doesn't hold in a Claude Code Fable session — there, it's pure
  drag (deaf lanes, queued≠delivered, split-brain rotation, minutes per hop, owner
  confirm-clicks). The swarm keeps the roles and the discipline and swaps the wire: the seat
  (Fable) keeps decompose / judge / apply-all-edits / gate-ships / owner-voice; everything
  else offloads to concurrent in-session background Opus agents and Workflow pipelines; the
  harness's completion notifications ARE the wire — no watches to re-arm, no rotation. The
  V4 §6 QC refuter runs as a verification stage after every finding; review-the-fix by a
  different lane. Estate files stay as banking + crash insurance, explicitly demoted from
  message bus. Honest boundary section: fable-director remains the choice when lanes must
  outlive the machine, span machines/accounts, or stay owner-watchable.
- **OWNER MODEL POLICY (2026-07-15): every offloaded job runs on OPUS** — no sonnet, no
  haiku, never inherited Fable. Owner chose closest-to-Fable quality on all delegated work
  over per-token savings; the spend ledger receipts the cost so the policy stays revisable
  with numbers. Supersedes the v2.7.0 sonnet/haiku difficulty ladder wherever it applied.
  Hardcoded in all four rule surfaces: the SessionStart hook (auto-deployed every session),
  fable-mode Hard Rule 11 (+ tool-graph fan-out bullet), fable-director Absolute Rule 6
  (+ sibling pointer to the swarm), and both CLAUDE.md foundation templates (oracle +
  sessionend copies now seed the policy into every scaffolded project foundation).
- **Seat cache rule made explicit everywhere the policy lands:** never `/model`-switch the
  seat mid-session — the prompt cache is per-model, so a switch re-reads the whole context
  cold; a subagent starts fresh and costs no cache at all. A model change is a subagent or
  a handoff, never a toggle.
- README: fable-swarm row, updated fable-mode row + hooks bullet (including the honest note
  that marketplace-cache installs don't self-update via git — `claude plugin update` is the
  real path). Manifests to 2.9.0/"Twenty skills".

## 2.8.1 — 2026-07-15

**archivist + spend wired into the suite — the skills now trigger each other.**

- **sessionend Phase 3.6 "Close the estate":** at every wrap-up, re-scan the oracle index
  (so the next session's intake starts already knowing the estate) and run `spend report`,
  pasting the verdict line into `HANDOFF.md` — ROUTING VIOLATIONS verbatim, never smoothed.
  New resumability self-check line to match.
- **oracle** now routes to both from the Objective ("what do we already know?" → `/archivist`,
  audit model spend/routing → `/spend`) — on top of the v2.8.0 intake index consult.
- **Consult-the-index-first** added to every search-budget skill — researcher (before Pass 1),
  marketresearcher (before Stage 1, date said out loud — market data ages), explainer (prior
  understanding dossier), decider (prior dossiers = ready-made Pass-3 evidence), factcheck
  (prior verdicts: reuse / re-verify / fresh). One `find` before spending; reuse/extend/fresh
  is always the user's choice.
- **Spend logging at every fan-out surface:** fable-mode Hard Rule 11 now closes with the
  receipt (log each spawn, report at close, exit 4 surfaced); director logs one ledger line
  per pipeline stage subagent; the gpt lane logs its tokens-used echo (`--lane gpt`).

**archivist + spend: the index and the receipt.**

- **New skill: `archivist`** (+ `scripts/index.py`, stdlib-only) — content continuity to
  match oracle/sessionend's session continuity: `scan` walks every ORACLE output folder
  (incl. `pipeline/NN-<skill>/` stages) and rebuilds one greppable `oracle-index.md` at the
  repo root — title, date, path, and each dossier's own 📌 Read Me First lines; `find`
  answers "what do we already know about X" for less than one web search. Consult-before-
  spending is the discipline: on a hit, offer reuse/extend/fresh instead of re-running the
  budget. Hard rules: the index is a finding aid never a source; a hit ≠ still true
  (re-verify load-bearing [cited] claims by age); never hand-edit (regenerate). `oracle`
  intake now consults/refreshes the index before routing. Fixture-proven on delivery:
  3-dossier scan (nested pipeline stage included), hit + miss both correct.
- **New skill: `spend`** (+ `scripts/spend.py`, flock-atomic appends — the room.py DNA) —
  the instrument behind v2.7.0's routing rule: every observed model spend (subagent
  completions, workflow totals, gpt-lane tokens-used echoes) gets one append-only
  `spend/ledger.md` line (model, lane, tokens|unknown, grade observed|estimate); `report`
  prints the per-model split and the routing verdict, **exiting 4 on any entry where Fable
  rode below the seat** — usable as a gate in scripts and ship rituals. Honest boundary
  stated on every report: the ledger covers observed spend only; the main loop's own
  consumption is not exposed to the model. Fixture-proven on delivery: deliberate
  violation caught (exit 4), seat-lane Fable correctly legal (exit 0, "routing: CLEAN").

## 2.7.0 — 2026-07-15

**Subagent model routing: Fable never rides in a subagent (the single biggest token-saving hard rule).**

- The problem: agents/subagents spawned from a Fable (`claude-fable-5`) session — ultracode/
  Workflow fan-outs, deep-research sweeps, review panels, pipeline stages — silently INHERIT
  the parent model when no model is set, billing Fable credit for work Sonnet does identically.
- New HARD RULE, hardcoded at two layers: the **SessionStart hook** now injects it
  unconditionally every session (so it reaches every fan-out surface even when no suite skill
  is loaded), and **fable-mode** carries it as Hard Rule 11 (+ the tool-graph fan-out bullet).
  Every spawned agent must set an explicit cheaper model, routed by difficulty: **sonnet**
  default (exploration, search fan-outs, reading/summarizing, drafting, control agents),
  **opus** only for judgment-heavy lanes (adversarial verification, architecture, complex
  debugging, final synthesis), **haiku** for trivial mechanical sweeps. The omission is the
  violation; Fable is the orchestrator seat, not the fan-out.
- Wired into every agent-spawning skill: **director** (stage subagents = sonnet; opus for
  critic/decider/high-cap stepbystep; new self-check line), **critic** `--panel` (sonnet per
  lens, opus for a spawned adjudicator), **introspect** (control agent = haiku/sonnet — it
  guesses from context, no frontier model needed), **fable-director** (rule 6 extended:
  "Fable pays for direction, not fan-out").
- The same rule is mirrored in the owner's global `~/.claude/CLAUDE.md` as a standing order
  (the second hardcode layer, outside the plugin).

## 2.6.0 — 2026-07-10

**chatroom: a shared floor where Claude sessions and GPT work together.**

- **New skill: `chatroom`** (+ `scripts/room.py`, stdlib-only) — rooms as append-only
  markdown files with flock-atomic posts; any Claude session joins via the script; wakes
  via `watch` (exits when new lines land — the fable-director token-watch DNA,
  generalized); GPT joins via `gpt-bridge` — a persistent codex session per room
  (remembers the conversation across runs), mention-triggered, 4-posts/min throttle,
  empty-subdir isolation. Live-proven on delivery: lobby room created, @gpt invited,
  bridge posted GPT's reply, and an armed watch woke on it (exit 0) — the full
  cross-vendor loop in one transcript. Paid-for fixes baked in: first-run cursor
  lookback (init-at-end swallowed the inviting mention), no embedded quotes in
  list-form subprocess args. Hard boundary: NO SECRETS — room content feeds other
  vendors' models. v1 local; z2m1 is the natural cross-machine v2 host.

## 2.5.1 — 2026-07-10

**Latency discipline for the gpt lane — measured fast paths.**

- New **Fast paths** section in `gpt`: one-call-per-job contracts (tool named directly +
  deliverable filename + DONE token — the discovery/execution two-turn split eliminated),
  the `--img` canned path (low effort, workspace-write, verify + display; **33s wall
  measured live**), background-by-default for slow jobs, parallel fan-out across
  workspaces, effort-by-job-type, and lane-selection guidance: native Claude subagents
  for speed and fan-out, codex for foreign opinions and ChatGPT-plan capabilities — like
  the built-in imagegen skill discovered live today (photorealistic PNGs, no API key).

## 2.5.0 — 2026-07-10

**gpt goes chat-first: a conversation by default, agentic by explained consent.**

- **/gpt is now simply a persistent conversation.** First use runs a 2-question guided
  setup — thinking level (low/medium/high, plainly described) and how agentic GPT may be
  (chat-only / worker / repo-aware) — saved to a profile; every later /gpt message resumes
  the chat with those settings (continuity live-verified: a token planted in turn 1 was
  recalled after process exit). One-shots moved behind `--once`.
- **`--task <slug>`** — background jobs in a dedicated empty workspace (workspace-write):
  deliverable filenames required up front, completion notification, verify-before-relay —
  contents read and checked, never exit-code-trusted. First live artifact: GPT's own
  3-point hostile review of this skill's design; its valid points (canonical `--vs`
  question file, untrusted-file injection + network-posture warnings, judge-side
  position-bias disclosure) are folded into this release.
- **Director wiring:** the lane is scriptable without questions (`--setup think=… mode=…`),
  and fable-director's never-subagents rule now documents the exception explicitly — gpt
  bills the owner's ChatGPT plan, not the metered key; sanctioned as `--once` second
  opinions on risky EDIT SPECS and as an extra QC refuter voice, never as an explorer.
- **Ladder corrected against the live API:** `minimal` 400s on the gpt-5.6 family — valid
  tiers are low | medium (default) | high. Resume flag order documented (exec flags BEFORE
  the resume subcommand).

## 2.4.0 — 2026-07-10

**gpt: the cross-model lane as a first-class skill.**

- **New skill: `gpt`** — one-line access to the GPT-5.6 family as a second-opinion
  subagent (Codex CLI on the user's ChatGPT account; no API billing): thinking-level
  control (`--think minimal|low|medium|high` → `model_reasoning_effort`, flag verified
  against codex-cli 0.144.1 with the header echo as proof), `--vs` blind comparisons
  (Claude's answer sealed to disk BEFORE GPT is called), `--here` repo-aware runs behind
  a secrets check, and empty-dir isolation by default (codex is agentic — it reads cwd).
  Hard boundaries baked in: `[model-opinion]` never counts as a source; prompts leave the
  machine, so no secrets. Born from introspect Run 5 — the suite's first cross-family
  predictive-lift control (+0.50 vs gpt-5.6-sol).

## 2.3.0 — 2026-07-10

**introspect v1.1: the two-layer snapshot — readable without losing its teeth.**

- Snapshots now seal TWO layers at once: the unchanged 6–10 token spine (deterministic
  scoring; plain single words preferred — the run-3 ledger lesson) plus ★-salience marks
  and a 3–8-word gloss per concept — the human-readable state description users asked for
  ("I can't read a bare word list"). Glosses are sealed with the tokens but never
  mechanically scored, so the confabulation-resistance of the measurement layer is
  untouched and prior-run ledgers stay directly comparable.
- Ledger format gains a `glossed:` line; `score_snapshot.py` unchanged.

## 2.2.0 — 2026-07-10

**introspect + game-forge: an instrument for the reportable workspace, and a maker with a playtest gate.**

- **New skill: `introspect`** — validated workspace self-reports, inspired by Anthropic's
  J-space/global-workspace paper (2026-07-06): fast sealed concept snapshots at checkpoints,
  scored deterministically (`scripts/score_snapshot.py`) for verbalized rate, the silent set,
  turnover, and **predictive lift vs a context-only control agent** — the honest black-box
  shadow of "privileged introspective access." Ships with a REAL first-run example ledger
  (lift +0.50 at N=1, integrity caveats recorded). Measures report validity; observes no
  activations, and says so on every artifact.
- **New skill: `game-forge`** (authored by Ethan in the desktop app, folded into the suite) —
  complete playable games on the fly: fixed-timestep engine templates (browser + pygame), genre
  playbooks, juice/audio references — and the suite's own rule applied to play: **no game ships
  unrun** (bundled headless playtest script). Portability notes added for non-claude.ai harnesses.

## 2.1.0 — 2026-07-09

**fable-mode v2: the full Fable behavioral contract.**

- Beyond the loop and hard rules, fable-mode now carries: **THE FABLE DIFFERENCE** (eight
  instinct→fable-move reflex swaps), a **consumer-side verification cookbook** (prove it at
  the surface that serves it — registry re-lists, UI structured-probes-before-pixels,
  run-the-generator-and-grep-its-output, both-sides checksums), a seven-step **outage
  playbook** (map the failure domain by experiment, reroute, chunk-stage-assemble,
  canary-with-value retries — distilled live from shipping v2.0.0 through a flapping
  tool-gate), **tool-graph craft** (failure-domain- and cost-aware tool choice; compose
  missing tools), and eight **situational profiles** (debugging, shipping, live-ops,
  research, data, long-horizon, multi-agent, degraded harness).
- **SessionStart anchor** gains the reroute clause (reroute instead of stalling; smallest
  probes; stage-then-assemble; keep unblocked lanes moving).

## 2.0.0 — 2026-07-09

**The public release: token-lean, verified, model-agnostic — and natural-language invocable.**

- **Three new skills fill the suite's own vision-verbs:**
  - **`explainer`** — genuine understanding of any topic/system/document: a correct mental model
    (analogies must state where they break), three depth layers (plain → working → expert), the
    standard misconceptions, and verify-it-yourself checks on the load-bearing claims.
  - **`decider`** — structured decisions: options incl. do-nothing/wait, user-weighted criteria
    (must-haves vs tradeables), evidence per option, a reasoned scoring matrix with a sensitivity
    check that names the hinge assumption, a pre-mortem on the front-runner, and a
    reversibility-aware recommendation (two-way vs one-way doors).
  - **`factcheck`** — claim-by-claim verification: verbatim claim extraction, primary-source
    hunting with true independence (daisy-chains traced to their single origin), and a five-verdict
    grammar — ✅ CONFIRMED / 🟡 PLAUSIBLE / 🔴 REFUTED / 🔵 MISLEADING (technically-true-but-
    framing-lies) / ⚪ UNVERIFIABLE — plus an auditable search log.
- **Natural-language invocation everywhere (breaking-ish, hence 2.0).** All working skills dropped
  `disable-model-invocation` — "research X", "should I…", "is this true", "wrap up the session"
  now trigger the right skill without memorizing commands. This also fixes a real 1.x defect: the
  PreCompact hook told the model to run `/sessionend`, which the flag made impossible. Every
  description was rewritten tighter (the always-loaded surface stays lean) with explicit
  "not for trivial asks" guards. `director` still runs sub-skills by reading them from disk —
  now for stage-isolation reasons, stated as such.
- **Token discipline made explicit:** search budgets in researcher (~20), marketresearcher (~25),
  explainer (~8), decider (~10), factcheck (~3/claim) — expandable only for load-bearing gaps or
  on user request, and said aloud when exceeded.
- **Consistency & routing:** `[estimate]` label added to researcher (math shown, matching
  marketresearcher); cross-skill handoffs at every Finishing-up (researcher→critic/factcheck,
  marketresearcher→critic/stepbystep, stepbystep→actionplan/critic); `oracle` intake now routes
  the stated Objective to the right skill/chain and defaults a skipped Evaluation to the suite's
  reliability standard; `director` gains default chains for the new skills.
- **Public docs:** README principles (token-lean · verified · model-agnostic), full 13-skill
  tables, and `docs/TUTORIAL.md` — install → the shape of every skill → the first full loop →
  which-skill-when → chains worth knowing.

## 1.3.0 — 2026-07-09

**The orchestration release: the fable arrangement, packaged for any repo.**

- **`fable-director` skill** — seats and operates **"3 DEVS AND A RELAY"**: a metered director
  (`claude-fable-5`, latest-Opus fallback via a probing launcher) orchestrating flat dev/QC
  lanes through per-lane `FABLE-COORD*.md` blackboard files with end-anchored token-watch
  wakes. Three modes: **SEAT** (rotation landing), **OPERATE** (burst agenda + ship gate +
  rotation ritual with the observed rotation-killers checklist), **BOOTSTRAP** (a FILE-ONLY
  scaffolder stands up a new repo in minutes — every blackboard with correct absolute paths,
  tokens named for your sessions, the QC refuter checklist baked in). Bundles the protocol of
  record (`PLAN-FABLE-DIRECTOR-V4.md`: the PING system, edit authority, QC relay charter,
  rotation ritual) — a per-project copy in the repo root stays authoritative over the bundle.
  Battle-tested on tell.rest (5 shipped rounds, 6 bugs fixed, 2 live rotations). Distinct from
  `director`, which chains *skills*; this one orchestrates *sessions*.
- **Packaging optimizations over the field version:** the kickoff prompt is
  project-parameterized (the scaffolder stamps the repo name into `<PROJECT>` on first copy),
  stale section cross-references fixed (DIRECTOR RESUME + edit-authority pointers), and the
  QC watch token generalized to the QC lane's own session name.
- **SessionStart hook now detects `FABLE-COORD*.md` blackboards** and nudges seating the
  fable-director — alongside the existing START-HERE/HANDOFF resume detection.

## 1.2.0 — 2026-07-08

**The discipline release: reliable working posture, bolted to the metal.**

- **`fable-mode` skill** — a working-discipline contract (not a capability; a process): the loop
  **ORIENT → PROBE → ACT → PROVE → BANK**, ten hard rules (empirical-first; verify handed-down
  claims against the live system; prove-then-claim with "should work" banned; show-before-run;
  root-cause-with-a-budget; blocked ≠ stopped; surface conflicts, never smooth; secrets never in
  context; momentum + honesty; own the estate of record), and a verification cookbook
  (405-vs-404 route probe, hash + container-start-time for "deployed = latest", `kill -9`-past-the-
  throttle for supervision claims, watch the receiver's logs for a clean cutover). Distilled from
  live Fable 5 sessions; makes any model — Opus especially — convert capability into reliability.
  Invoke with `/fable-mode`, "work like fable", or "2× reliability".
- **SessionStart hook now bolts the discipline to the metal.** Beyond the START-HERE/HANDOFF resume
  nudges, the hook unconditionally injects a compact fable-discipline anchor (the loop + the
  highest-value rules + a directive to load the full `fable-mode` contract) as session context —
  every session, no `/fable-mode` needed. Trivial single-question turns may skip; substantive work
  runs the loop. This is the "bolt to the metal" upgrade over relying on a CLAUDE.md instruction.

## 1.1.1 — 2026-07-02

- **Self-updating from git.** The `SessionStart` hook now quietly `git pull --ff-only`s the plugin's
  own clone (fire-and-forget: never blocks startup, never clobbers local edits; updates apply from
  the next session). Install the plugin from a git clone once and it stays current with the repo.
  Security note: this executes what origin ships — point it only at a repo you control.

## 1.1.0 — 2026-07-02

**The continuity release: the handoff stops depending on memory and discipline.**

- **Live cross-session handoff line.** `sessionend` gains Phase 5 ("Open the live line"): in
  multi-session environments (Claude Code desktop) the ending session stays alive, records a
  "Live line:" row in `START-HERE.md`, proactively sends the successor a six-part orientation
  message, and answers its setup questions from full context. `oracle` gains the receiving end:
  when resuming a continuation it finds the predecessor (Live-line row or `list_sessions`), reads
  the docs first, then messages one consolidated batch of questions — falling back to transcript
  search if the predecessor is closed. Templates: `skills/sessionend/references/live-handoff-template.md`.
  Proven in production on a real project handoff before shipping.
- **Automated continuity hooks** (new `hooks/`): `SessionStart` detects a `START-HERE.md` /
  `HANDOFF.md` in the working directory and injects a resume nudge as context; `PreCompact` (auto)
  reminds that a deliberate `/sessionend` handoff preserves more than compaction.
- **Memory layer.** `oracle` intake queries available persistent memory (Claude Code auto-memory or
  a memory MCP) before the Content question; `sessionend` Phase 3.5 deposits a handoff digest into
  writable memory. Files stay the source of truth; memory is the finding aid.
- **`critic --panel`**: multi-lens panel mode (correctness · security · economics · adversary ·
  feasibility) with cross-lens adjudication — findings that survive multiple lenses outrank any
  single lens's severity call.

## 1.0.0 — initial release
ORACLE session intake, researcher, marketresearcher, stepbystep, actionplan, critic, director,
sessionend — bookended by a shared CLAUDE.md foundation.
