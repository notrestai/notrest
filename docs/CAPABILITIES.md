# CAPABILITIES.md — the harness capability register

Drafted 2026-07-25 (v3.7.0 tree). One entry per skill and per toolset: what it does,
the mechanics that matter, and the concrete upgrades that would make it *way more
capable* — every upgrade buildable (a script, a hook, an MCP, a flag), none vague.
Skill entries come from a three-lane Opus analyst pass over every SKILL.md and shipped
script; toolset entries are seat-written from the day's live work.

> **v3.8.0 shipped from this register (2026-07-25):** the findings-store architecture
> (archivist owns `archive/findings.jsonl`; researcher/decider/factcheck rewired; the
> door validator absorbs the dossier-lint family), the river (`graph.py river` +
> `links`/`orphans`/`stale`), the live-policy spend gate + stop-event receipt dedup,
> doctor→10 checks (SHADOWED · TOKEN BUDGET · HOOKS FIRED), eval→10 checks
> (REFERENCES-CITED · `--baseline`), chatroom's enforced no-secrets screen + `join` +
> bridge receipts, `watch.py`, `gpt.sh`, refuter's `brief.py`+`verdict_lint.py`.
> Entries below describe the pre-3.8.0 state where they conflict with this note;
> still-open upgrades remain accurate. Remaining dossier writers (marketresearcher,
> critic, explainer, recap) migrate to the findings sink next.
>
> **The successor backlog lives in [JOURNEY.md](JOURNEY.md):** its journey-gaps
> section (G1–G18) supersedes the priority list below where they overlap — the
> journeys expose the missing handoffs the register could not see.
> **v3.9.0: all eighteen shipped in one batch** — the gap section is now a build
> record; the open items are the journey page's disclosed residuals (8 skills without
> Chains sections, prose-only handoffs) and this register's unshipped niceties.

## The law this register serves

Sessions must use the suite's verbs for matching work — research-shaped asks run
`researcher`, decisions run `decider`, verification runs `factcheck`, and so on.
Enforcement is layered: oracle's intake routes at session start; the **router hook**
(UserPromptSubmit, shipping as v3.7.0) nudges per-prompt with one targeted line;
fable-mode carries the routing law; eval fingerprints all of it statically.
Overriding a route deliberately is fine. Silently ad-hoc'ing the same job is not.

---

## Toolsets — hooks (plugins/notrest/hooks/, all silent-on-failure, always exit 0)

### session-start.sh
does: anchors the discipline + offload laws into every session; conditional resume/COORD/compile nudges; background `git pull --ff-only` self-update. Since 2026-08-02 the root is git root OR an established non-git cwd (a `COORD.md` there earns the full treatment); a project-like non-git dir with no ledger gets ONE nudge to say `/notrest` and is never auto-scaffolded.
how: 2 standing echoes (~680 chars post-diet) + 3 conditional nudges; the pull is real under skills-dir (was a silent no-op on cache installs).
upgrades: 1) skip nudges when the session is itself a subagent lane (env-detectable) — lanes never need resume hints. 2) echo the loaded version+HEAD short-hash on drift (pull moved the tree) so staleness is visible at a glance.

### coord-nudge.sh
does: per-prompt one-line COORD ledger reminder (96 chars). Since 2026-08-02 it resolves git root, else the nearest `COORD.md` at cwd/parent/grandparent — so established non-git projects get the discipline too.
upgrades: 1) sibling router.sh (in flight, v3.7.0). 2) suppress on prompts that are themselves /notrest: skill invocations — the skill's own contract already owns the ledger line.

### agent-ledger.sh
does: SubagentStop auto-receipt — appends COORD-AGENTS.md + spend/ledger.md, flock'd, idempotent-by-intent, honest grading (observed vs estimate). Since 2026-08-02 the old line-17 git bail is a COORD-root walk (git root, else cwd/parent/grandparent) — the exact hole the ungoverned non-git session fell through.
upgrades: 1) close the guard hole (identical duplicate lines passed the agent-id guard; race fixed at root in 3.6.1, guard still latent — chip open). 2) record duration + tool-call count when the payload carries them: free speed-law instrumentation per lane.

### session-end.sh
does: crash cushion — auto-appends a resume line when a session dies without /sessionend; rolls COORD.md into sealed volumes at 500 lines (fsync-then-replace, inode guard). Since 2026-08-02 it uses the same COORD-root resolver, so non-git projects get the cushion and the roll.
upgrades: 1) cushion line should carry version + HEAD + dirty-file count — a cold resume currently learns those separately. 2) roll COORD-AGENTS at its 1000-line law in the same pass (verify it actually does).

### pre-compact.sh
does: re-anchors the discipline before auto-compaction (~409 chars, fires rarely).
upgrades: none needed now — re-measure after the router ships.

## Toolsets — scripts and runtimes

### doctor.py (8 checks, exit 0/5/6, read-only)
does: install + estate physical — frontmatter, manifests/tombstone, count drift, hooks, estate integrity, install freshness, gitignore anchors, render stamps.
upgrades: 1) **token-budget gate**: `claude plugin details` always-on ≤ budget (~3.6k) or FAIL with the diet command — locks the rightsizing as law. 2) skills-dir freshness: verify `~/.claude/skills/notrest` symlink resolves to this repo and `plugin list` says ✔ loaded (today it just SKIPs). 3) root README/CLAUDE.md count surfaces (coverage gap parked since v3.3.0).

### eval.py (8 static law checks, 0.06s, zero tokens)
does: law conformance as fingerprint — offload policy, honesty labels, script-owns-scanning, append-only estate, worker contract, trigger sanity, safety laws, hook contract.
upgrades: 1) check #9 ROUTER (in flight). 2) an opt-in behavioral arm via the CLI's native `claude plugin eval` (our case format runs first-class now, with a no-plugin baseline) — the old runner died, the cases in evals-legacy-external-runner/ did not.

### compile.py + compile/<slug>/ runtimes
does: zero-token estate scanner finds work done ≥3× (18 candidates today); the ritual compiles stable parts into isolated, fair-benchmarked runtimes; ship.py (853 lines, replay-proven) is the maiden compile — NOT live-verified, no version-monotonicity check.
upgrades: 1) add the monotonicity guard, then run ship.py in replay beside the next real ship and decide graduation. 2) compile the next ripe candidate. 3) scanner learns the speed law: flag candidates whose receipts show high wall-clock (compilation saves the most there).

### spend.py
does: append-only model-spend receipts; report exits 4 on a routing violation; hook-fed since 3.4.1.
upgrades: 1) per-session rollup line (tokens by model, lane count) appended at sessionend — today the report is on-demand only. 2) wall-clock + tool-call columns from the hook payload: the speed law becomes queryable.

### graph.py · archivist index.py · room.py · score_snapshot.py
does: file graph + PM merged view · dossier index · chatroom rooms · introspection scoring.
upgrades: 1) graph: register this project in ~/.claude/oracle-projects.txt and render the PM view — the cross-project claim has never been proven live. 2) archivist: becomes researcher's scripted step-0 (see researcher entry). 3) introspect/chatroom: no changes until used in anger.

### render-check.sh · gategrep.sh
does: serve-then-snapshot render verification (file:// pages snapshot stale) · wrap-safe grep (naive grep -F false-zeros on wrapped markdown).
upgrades: none — these ARE the paper-cut fixes.

### External lanes
gpt (Codex CLI on the owner's ChatGPT account, [model-opinion] labeled, no secrets) · scheduled-tasks MCP (watch's cadence engine) · the skills-dir runtime itself (SKILL.md hot-reload; hooks need /reload-plugins).

---

## Skills — knowledge verbs

### researcher
does: Five-pass research (baseline → ≥5 alternatives → evidence → comparison → disconfirmation) written to a background doc + decision dossier.
how: Prose contract only, no scripts; ~20 search/fetch budget; [cited]/[recall]/[estimate]/[unverified] + Tier 1-3 rules; `--quick` chat-only; archivist `find` before Pass 1.
upgrades: 1) Fan Pass 2/3 into one narrow background Opus lane per alternative with a fixed return card; seat merges — wall-clock ≈ slowest lane. 2) Ship `scripts/dossier_lint.py` (exit 1): unlabeled factual sentences, `[cited]` without URL, missing tier/date, Pass-2 options absent from Solution Space. 3) On dossier write, auto-append a `spend.py` receipt + COORD line and re-run `index.py scan` — estate bookkeeping leaves the seat.
gap: Zero scripts — every honesty rule and the whole self-check is unenforced honor system.

### marketresearcher
does: Seven-stage funnel — scope, two-way sizing, competitor map + graveyard, gap verdicts, feasibility scoring, drafted entry ideas.
how: Prose only; ~25 searches; strictest honesty (never invent a number), Tier 1-3, >10× top-down/bottom-up sanity flag, search log, disclaimer; two files.
upgrades: 1) `scripts/size_check.py` — takes both sizing inputs, computes the ratio, exits nonzero above 10×, prints the `[estimate]` arithmetic block. 2) One Opus lane per competitor segment (incumbents / challengers / substitutes / graveyard), fixed return schema, seat reconciles. 3) Numeric lint gate: every figure in the dossier must carry source + date + tier or the write is refused.
gap: The most fabrication-prone step (sizing reconciliation) is checked only by the model's own arithmetic.

### factcheck
does: Extracts load-bearing claims verbatim, verifies each, returns ✅/🟡/🔴/🔵/⚪ verdicts with daisy-chain and framing audits.
how: Prose only; ~3 searches/claim, ~25 total, ~10-claim cap; five-verdict grammar; search log makes "not found" auditable; two files; `--quick`.
upgrades: 1) One narrow Opus lane per claim (verbatim claim in, verdict card out) — ten claims in one wall-clock; seat keeps Pass 3/4 adjudication. 2) `scripts/verdict_lint.py`: ✅ requires ≥2 distinct source domains, 🔴 a contradicting URL, 🔵 the true/implied/fails triple, every claim quoted. 3) Script-emit `watch/watchlist.md` rows for every ✅ claim carrying a URL, so the factcheck→watch handoff costs zero tokens.
gap: Independence-of-origin — the skill's core rigor claim — is never mechanically checked.

### watch
does: Re-verifies dossier claims on a per-claim cadence and appends dated drift reports (HOLDS/DRIFTED/DEAD-SOURCE/UNVERIFIABLE).
how: SKILL.md only, **no scripts dir**; `watch/watchlist.md` table + append-only `watch/drift-log.md`; ~2 fetches per due claim; scheduled-tasks MCP offered, owner-confirmed; one COORD line per run.
upgrades: 1) `scripts/watch.py due|append` — parse the table, compute due rows, update Last-checked/Status in place, append the block with the Fetched-this-run stamp and COORD line. 2) Same script does HTTP HEAD/GET first: status codes plus ETag/content-hash diff vs stored hash, so DEAD-SOURCE and "byte-identical page" resolve at zero model tokens; the model judges only changed pages. 3) One Opus lane per due claim under the 2-fetch budget.
gap: A table/cadence/receipt protocol with no script — every due date, count, and status edit is hand-maintained.

### archivist
does: Scans ORACLE output folders into one greppable `oracle-index.md`; adds pointer entries for the agent ledger and compile candidates.
how: `scripts/index.py` (stdlib) `scan`/`find`; indexes `*Dossier.md` title + mtime date + path + Read-Me-First lines; counts `COORD-AGENTS.md` entries and `compile/candidates.json` ripe/total.
upgrades: 1) Add a `grep` subcommand searching dossier **bodies** — `find` splits the index on `### ` and matches only head lines, so body terms are invisible today. 2) Index the rest of the estate the same pointer way: `watch/watchlist.md` rows + drift-log dates, `recap/*map.html`, background docs, chatroom rooms. 3) Parse the dossier's own date instead of `st_mtime` (any clone/copy resets it) and stamp entry age + `[cited]`-claim count so `find` can recommend reuse vs re-verify unopened.
gap: `find` is blind to dossier bodies — the index answers "was this titled" not "was this said".

### explainer
does: Builds understanding — correct mental model, plain/working/expert layers, standard misconceptions, verify-it-yourself claims.
how: Prose only, no scripts; ~8 searches (may honestly be zero); labels + "every analogy states where it breaks"; `understanding/` two files; `--quick`.
upgrades: 1) Comprehension gate: a fresh Opus lane reads only the dossier and answers Pass 1's 3-5 questions; misses route back as revisions. 2) `scripts/layer_check.py` — jargon-in-Plain-layer word list, ~150-word cap, analogies with no stated breaking point, unlabeled non-obvious claims. 3) Emit a prediction/quiz block from Pass 2 and reuse it as the grading key for lane 1.
gap: Understanding is the stated bar but nothing measures whether the dossier actually teaches.

### recap
does: Walks COORD, COORD-AGENTS, git, spend, and dossier folders in timestamp order into a decision story plus a clickable HTML map.
how: `assets/decision-map-template.html` with a hand-filled `RECAP_DATA` block; **no script**; per-beat citation tokens; UTC git rule; mandatory render gate; three files.
upgrades: 1) `scripts/walk.py` — merge COORD volumes + agent ledger + `TZ=UTC git log` + spend lines into one sorted JSON, existence-check every transcript path, count spans; Steps 1-2 at zero model tokens. 2) Same script pre-fills `RECAP_DATA` nodes and `cites`; the model contributes only edges and narrative. 3) Point the render gate at the already-shipped `doctor/scripts/render-check.sh` (proves HTTP 200, exit 4 on failure, `--close`) instead of "browser tools, the preview pane, or open".
gap: The suite's biggest read — the whole estate, hand-merged in timestamp order — has no scanner.

### graph
does: Script-built Obsidian-style file/reference graph for a repo or all registered repos, rendered self-contained and opened.
how: `scripts/graph.py` (stdlib, 1089 lines): git-or-walk listing, wikilink/link/import/source/mention/transcript/pair edges, `graph/graph.{json,html}`, `register`/`all` merge with per-project cap 300; exit 0/2.
upgrades: 1) Add `links <path>` / `orphans` / `stale` query subcommands over `graph.json` — the description promises "what links to this file" but only the HTML can answer it. 2) Incremental scan: cache per-file mtime+hash in graph.json so re-scans re-read only changed files (READ_CAP is 200KB/file today). 3) Replace the inlined 8790-8799 port loop in SKILL.md with `doctor/scripts/render-check.sh`, which already does exactly that and proves the 200.
how (cockpit): `scripts/cockpit.py serve [--always] [--no-open]` + `status` — a loopback-only live window; `--always` writes `graph/.cockpit-always` with the bound port (atomic, after the bind), `status` probes `/health` in 0.5s and exits 0/5/6, and the SessionStart hook echoes one nudge when the marker is present. The hook never probes, spawns or opens — surfacing is the seat's job, doing is not the hook's.
gap: No CLI query path — every model-side graph question costs opening a page or slurping the JSON.

### introspect
does: Emits sealed workspace snapshots, scores them against later output versus a context-only control, logs to an append-only ledger.
how: `scripts/score_snapshot.py` — deterministic stem/substring matching → JSON (verbalized, silent, lift, turnover); ledger markdown written by hand; control is an explicit-Opus subagent; `references/example-ledger.md`.
upgrades: 1) Add `append` and `report` subcommands — parse ledger metric lines, print mean rates/lift/turnover with N and refuse trend claims under N=10; `/introspect report` currently claims an aggregation no script performs. 2) Ship a `--control-prompt` emitter plus a fixed one-shot Opus lane recipe so the baseline is spawned identically every run (protocol drift kills the control). 3) Write each run as `introspection/runs/*.json` so aggregates never depend on parsing prose.
gap: The instrument's data layer is hand-written markdown — scoring is deterministic, storage and aggregation are not.

> Cross-cutting finding (analyst lane): the four heavy research skills — researcher,
> marketresearcher, factcheck, explainer — never mention delegation, COORD, or spend;
> they run every pass serially in the seat and leave no receipt. `watch` is the only
> knowledge verb that writes a COORD line. The lane-parallel + auto-receipt upgrades
> above are one pattern applied four times.

## Skills — decision & outbound verbs

### decider
does: Six-pass decision structuring — options incl. do-nothing, weighted criteria, evidence, scored matrix, sensitivity hinge, pre-mortem.
how: Model-only. Since v3.8.0 emits `kind=decision` finding records (hinge in the statement) via archivist's validated `add`; labels [cited]/[estimate]/[recall]; ~10-search budget; `--quick`; archivist index consult.
upgrades: 1) `scripts/matrix.py` — weights+scores as TSV/JSON, computes weighted totals and auto-sweeps every ±10% weight perturbation, printing which flip the winner. 2) One background Opus lane per option for Pass 3 evidence, refuter-check the front-runner before Pass 6. 3) Zero-token dossier lint: weights sum to 100, every cell has a reason, do-nothing present, hinge section non-empty.
gap: The hinge/sensitivity claim — its whole value — is hand arithmetic nothing verifies.

### critic
does: Adversarial six-pass document review — steelman, tiered objections, disconfirmation, ≥3 alternatives, fair verdict.
how: Two files under `critique/`; 🔴/🟠/🟡 severity; `--quick`; `--panel` = 5 lenses (correctness, security, economics, adversary, feasibility), explicit `model: opus` per lens, forks banned. No scripts, no references dir.
upgrades: 1) Ship `references/lens-briefs.md` — five fill-in briefs plus the batch-spawn recipe, so `--panel` is a contract rather than improvised each run. 2) `scripts/adjudicate.py` — merge lens returns by claim id, mark multi-lens survivors (outrank single-lens) and tag perspective-dependent ones; today that synthesis is manual. 3) Import refuter's evidence grammar: every 🔴 carries a quoted source line or reproduction; grep-lint for objections with no label.
gap: `--panel` claims parallel lenses with nothing on disk to spawn or merge them.

### refuter
does: Adversarial reviewer for code — a non-builder lane attacks one narrow target and reports findings with reproductions.
how: `references/brief-template.md` (7 required sections), 6-rung attack ladder, ~12 tool calls, CONFIRMED/PLAUSIBLE grammar, severity irreversible-safety > claim-honesty > degrades > cosmetic, SURVIVED list; agentswarm gate step 4; spend receipt.
upgrades: 1) `scripts/brief.py` — take a target path, inline its bytes + sha, mint the scratch dir, stamp the budget, emit the filled brief; the seat stops hand-pasting. 2) `scripts/verdict-lint.py` — reject a returned report where a CONFIRMED lacks a fenced command+output, a PLAUSIBLE lacks the word or a scenario, or SURVIVED/budget is missing. 3) Prefill rung 1 by running `doctor/scripts/gategrep.sh` against the target so the lane starts from hits, not a blank sweep.
gap: An all-prose contract — nothing mechanically checks a returned report against it.

### stepbystep
does: Goal + docs into a dependency-ordered, per-step-verifiable plan, refined by research→critique loops until convergence.
how: 9 passes into `action-plan/` two files; H/M/L confidence per step, [ONE-WAY]/[needs expert] flags, delta + iteration log, 5-iteration cap, oscillation guard. All model-judged; no scripts.
upgrades: 1) Parallel Opus lanes for Pass 7 — one lane per high-risk/[ONE-WAY] step, tight returns; the loop is serial and slow by design. 2) `scripts/plan-lint.py` — parse the dossier: every step has "done when", dependency graph is acyclic and only references earlier steps, [ONE-WAY] has rollback, Low has mitigation. The self-check as an exit code. 3) Convergence receipt: compute a vN↔vN-1 diff ratio into the iteration log instead of the model declaring convergence.
gap: Convergence and dependency ordering are self-graded prose — the two things most worth checking.

### actionplan
does: Expands a stepbystep dossier into a copy-paste runbook — per-host commands, verify + rollback each, ⛔ before destructive ops.
how: 4 phases into `runbook/` two files; optional `map.md` env input; placeholders + values table; carries [ONE-WAY]/[needs expert] through; writes, never executes; `--quick`.
upgrades: 1) Ship `references/map-template.md` — `map.md` is a named input with no template anywhere on disk. 2) `scripts/runbook-lint.sh` — shellcheck every fenced block, assert each step has Verify and Rollback, each placeholder is in the values table, each `rm -rf`/`DROP`/`dd`/`mkfs` carries ⛔, no hardcoded secret patterns. Zero model tokens. 3) `--dryrun`: substitute placeholders into a scratch copy and execute only the verify commands (read-only) to prove they parse and resolve.
gap: Nothing checks a command is even syntactically valid before a human pastes it into production.

### draft
does: Turns a dossier/decision into a sendable email · memo · slack · one-pager · status, facts traced and labels intact.
how: `references/formats.md` five skeletons with hard word budgets (200/500/120/700/300); `draft/{slug}background.md` (claims table, 3-line audience brief, framing list, source-map) + `{slug}.{format}.md`; never sends.
upgrades: 1) `scripts/draftcheck.py` — word count vs budget plus source-map coverage: every sentence of the deliverable must appear in the map table, exit non-zero otherwise. 2) Label-upgrade detector: for each mapped [estimate]/[unverified] claim, assert a hedge token survives in the final prose — that law is violated gradually by good writing, and only a script catches it. 3) Add `draft` to `archivist/scripts/index.py` `DIRS` (currently 11 folders, draft absent) so drafts are indexed and visibly unsent.
gap: The source-map law — the skill's whole contract — is pure honor system.

### gpt
does: Persistent GPT-5.6 chat lane through Codex CLI on the owner's ChatGPT account, plus one-shot, task, blind-compare, image modes.
how: Profile + session-id files under `<scratch>/gpt-lane/`; inline `codex exec … resume` bash; `[model-opinion]`; empty-dir isolation; `--sandbox workspace-write` for `--task`; spend `--lane gpt`; no secrets.
upgrades: 1) `scripts/gpt.sh` — the resume/once/task invocation, `session id:` and `tokens used` parsing, and the spend.py call in one script; chatroom's `room.py codex_call` is a working donor. 2) `--task` deliverable verifier: a promised-files manifest plus a content check (non-empty, expected type) enforced by script before anything is relayed as [model-artifact]. 3) Wrapper-side auto-receipt piping the echoed token count into `spend.py` so the cross-model lane cannot silently go unlogged.
gap: Zero scripts on disk — `codex exec` appears only in prose, re-improvised every call.

### chatroom
does: Append-only shared room files where any Claude session and GPT chat and coordinate; watches are the wakes.
how: `scripts/room.py` (create/post/read/lines/watch/gpt-bridge, 192 lines, stdlib); flock-atomic posts; watch exit 0=new, 3=timeout; per-room persistent codex session in `.gptwork`; 4 posts/min throttle; local machine only.
upgrades: 1) A `room.py join` subcommand doing read-tail + arm-watch + print the re-arm line in one call — the manual 3-step protocol is exactly where sessions go deaf. 2) Secrets guard inside `cmd_post` — regex scan for key/token/PEM/.env patterns and refuse; today "NO SECRETS ever" is prose while the bridge ships lines to OpenAI verbatim. 3) Log every `codex_call` to `spend.py --lane chatroom-gpt`; bridge spend is currently invisible to the ledger.
gap: The load-bearing no-secrets law has no enforcement in the script that does the sending.

### game-forge
does: Builds a complete playable game (browser Canvas default, pygame optional) with real loop, juice, procedural audio, and a pre-delivery playtest.
how: `assets/engine.html` + `engine.py` templates, 7 references (loop, juice, audio, pygame, 4 genre playbooks), `scripts/playtest.mjs` — headless Chromium, fails on console/page error, injects keys, blank-canvas detect, screenshot, exit code; `GAMEFORGE_SMOKETEST` env hook in engine.py.
upgrades: 1) `scripts/playtest.py` — the pygame SDL-dummy smoketest is instructions only; make it an exit-code runner matching the browser one. 2) Turn the anti-pattern list into playtest assertions: AudioContext created, no localStorage access, touch/pointer handler bound, and a 2-fps run whose game state matches a 60-fps run (frame-rate independence, mechanically proven). 3) Fuzz pass — N random input sequences over 30s to catch state-machine crashes a single Space press never reaches.
gap: The playtest proves it loads and draws, not that it plays.

## Skills — meta & estate verbs

### notrest
does: The establishment verb — writes the two surfaces that make a project governed (`COORD.md` with the ledger header, a marker-delimited versioned protocol block in `CLAUDE.md`), then binds the invoking session to the protocol. `check` is the read-only drift check for "is this session following the plugin?".
how: `establish.py check|establish [--root PATH] [--git-init]`, exits 0/5/6/2; every write idempotent and atomic (tmp + `os.replace`), the COORD scaffold reproduced verbatim from `session-start.sh` and asserted byte-equal by the fixture. Establishment facts drive the exit code; adoption facts (ledger lines beyond the scaffold, age of the newest line, agent/spend ledgers present) are INFO and can never move it — the script reports, the seat judges. A root that is neither a git repo nor carries a project marker is refused with exit 2. `fixture.sh` (78 asserts) also drives the four patched hooks in non-git and git roots.
upgrades: 1) A `--json` mode so a scheduler or a parent lane can consume the establishment verdict without parsing lines. 2) Block versions beyond v1 need a migration note per bump — today an older block is replaced wholesale, which is right for prose and would be wrong the moment the block carries project-specific values. 3) `check` could read the newest COORD stamps against session start and say *this session has banked nothing yet*, turning the drift judgment into evidence rather than an inference.
gap: It proves the FILES exist; it cannot prove a session is obeying them — adherence stays a labeled judgment, by construction.

### oracle
does: Session front door — load foundation, offer resume, six ORACLE questions, then recommend which sibling skill fits.
how: Prose-only skill (`SKILL.md` + `references/claude-foundation-template.md`); no scripts. Routing is ONE run-on bullet (line 131) of `topic → /skill` pairs; the COORD intake line `[oracle] intake done: … -> routed to /<skill>` is a model-written instruction. Nothing on disk parses `routed to`; neither eval.py nor doctor.py reads it.
upgrades: 1) `references/routes.md` as a machine-readable table (objective-shape · skill · done-when) + `oracle.py route --objective "…"` that prints the route and appends the COORD intake line deterministically. 2) eval check `ROUTE-CONFORMANCE`: parse COORD for `routed to /X`, assert a later ledger line, dossier folder, or agent entry from X exists — a route never taken becomes an exit-6 finding. 3) Script the Leverage auto-inventory (`installed_plugins.json` + skills dirs → the 2–5 shortlist), so inventory costs zero judgment and cannot hallucinate a plugin.
gap: Routing is unenforced prose — nothing checks the route was taken.

### sessionend
does: Writes START-HERE/HANDOFF/STATE/CLAUDE.md, verifies cold-resume, closes the estate, opens the live line.
how: Five phases + Phase 3.6 estate closes (archivist scan, `spend.py report` verdict into HANDOFF, `compile.py scan`, watch due-rows, COORD close line); `hooks/session-end.sh` is the always-on cushion and enforces the volume-seal law (COORD 500 / COORD-AGENTS 1000). Every cited mechanism exists on disk.
upgrades: 1) `sessionend.py close --root .` running the deterministic half — compile scan, spend report, archivist scan, COORD close line, checklist emitted — leaving the model only the prose files. 2) A `verify` mode that greps every path and command cited in START-HERE.md against the tree and exits nonzero on a dead reference (Phase 4's cold-reader check, as code). 3) STATE.md appends through a flock'd writer so concurrent sessions on one repo cannot clobber the receipts.
gap: Five phases of judgment with zero deterministic support — the whole close is hand-run.

### fable-mode
does: Loads the discipline contract — ORIENT→PROBE→ACT→PROVE→BANK, 11 hard rules, outage playbook, verification cookbook.
how: 254 lines of prose, no scripts, no references dir. The SessionStart hook echoes a one-line anchor unconditionally; Hard Rule 11 carries the opus-only offload policy.
upgrades: 1) `scripts/prove.sh <kind> <target>` implementing the cookbook's recipes (405 route probe, md5 both sides, kill-9 respawn wait, container start-time vs mtime) so PROVE emits receipts instead of describing them. 2) A BANK guard: script compares the COORD ledger tail's timestamp against session start and warns when substantive turns landed with no line — the one hard rule that is mechanically checkable. 3) Split into a ~40-line always-loaded core + `references/` for the outage playbook, cookbook, and situational profiles; the anchor is already in the hook, so the full load is largely duplicated.
gap: Wholly unenforceable prose — no instrument detects a violated rule.

### fable-director
does: Seats the metered multi-session "3 devs and a relay" arrangement — director + lane blackboards + token-watch wakes.
how: MODE DETECT A(seat)/B(operate)/C(bootstrap); `new-fable-project.sh` scaffolds dirs, V4 copy, blackboards, tokens; `fable-launcher.sh` probes Fable then falls back to Opus; repo's V4 always beats the bundle; in-session subagents banned under the metered key.
upgrades: 1) `director-check.sh` mechanizing the six rotation-killers: every lane blackboard has an armed-watch task id, token names match session names, kickoff version == plan version, no two directors bursting. 2) Turn `references/spawn-lanes.md` into a script that demands the proof trio (watch id · auth-isolation env check · first ledger ACK) as exit-coded assertions — "spawned ≠ seated" enforced. 3) A burst-agenda emitter appending each burst's QUESTIONS/ESCALATIONS/objective into COORD, so bursts are auditable rather than remembered.
gap: The rotation-killers — each one observed live — are checked by eyeball only.

### agentswarm
does: The default delegation arrangement — seat keeps decompose/judge/apply/gate; background Opus lanes do everything else.
how: Ships NO scripts or references; every mechanism it names lives elsewhere (spend.py, `hooks/agent-ledger.sh` auto-receipt). Batched background spawns, tight return contracts, `model: "opus"` + fork ban, one persistent builder lane per domain resumed via SendMessage, trail-walk judging.
upgrades: 1) `swarm.py verify --since <ts>` reading COORD-AGENTS.md + spend/ledger.md to prove every lane this session ran opus and got a receipt — the self-check turned into an exit code. 2) A lane-spec generator emitting the style capsule + interface spec + return contract + grep-able done-when, so specs come from a form instead of the seat's memory. 3) A persistent-lane registry (`domain → agent id`) written on spawn, so a post-compaction seat resumes the right builder lane instead of re-spawning and forfeiting its context.
gap: Every law it states is unverifiable prose; nothing proves fork-ban or lane-resume held.

### director
does: Chains sibling ORACLE skills into a pipeline, one numbered stage folder each, output of N feeds N+1.
how: Reads each `SKILL.md` from disk and performs it — never the Skill tool (stage isolation); isolated opus subagent per stage; `{topic}background.md` pins the ordered chain plus a `[ ] NN-<skill>` checklist as the resume source of truth; `--quick` is chat-only. No scripts.
upgrades: 1) `director.py plan --chain a,b,c --topic X` scaffolding the run folder, checklist and resolved SKILL.md paths, plus `verify` that exits nonzero on an unticked box or a stage folder missing its two files — precisely the failure the skill exists to prevent. 2) Per-stage handoff manifest (input path + output path + hash) so "the handoff must be genuine" is checkable rather than asserted. 3) Resolve-all-skills-before-stage-1 as a script check, so a missing skill fails in milliseconds instead of mid-run.
gap: No script — its own named failure mode ("the last stage never ran") is policed by the model.

### spend
does: Append-only model-spend ledger that makes offload routing checkable instead of asserted.
how: `spend.py` (97 lines, flock append), `log`/`report`, grades observed|estimate, report exits 4 on violation. The SubagentStop hook auto-writes `lane=subagent` receipts byte-compatibly. **Violation test is `lane not in {main,director,seat} and "fable" in model`** — only the retired pre-2026-07-15 rule. A sonnet or haiku lane prints `routing: CLEAN`.
upgrades: 1) Extend the gate to the live policy: any subagent/workflow lane whose model is not opus is a violation (exit 4), gpt lane allowlisted by name, with a policy-date guard so pre-2026-07-15 history stays lawful-at-the-time. 2) `--since` / `--session` filters and `--json`, so a per-round verdict can gate a ship ritual instead of only the whole-ledger verdict. 3) A `reconcile` mode diffing COORD-AGENTS.md entries against ledger lines to catch lanes that ran but were never receipted.
gap: The instrument enforces the retired fable-only rule; non-opus lanes pass CLEAN today.

### compile
does: Mines the estate for jobs done 3+ times, then a seat ritual compiles the stable parts into an isolated runtime.
how: `compile.py` (785 lines) scan/report/decide — df-weighted clustering with estate stopwords, cross-source fusion, weak-source demotion, report exit 3 on a ripe NEW; then a 9-step hand-run ritual (contract → partition → builder lane → refuter → gate → fair benchmark → quality law → cost → deliverable). `fixture.sh` + doctrine reference ship.
upgrades: 1) `compile.py contract --slug S` emitting the Step-1 responsibility table pre-filled with trail citations (COORD line · agent id · commit · spend line), so the seat judges rather than walking the trail by hand. 2) A runtime scaffolder producing the `compile/<slug>/` skeleton (runner, typed schema stubs, validator, replay-fixture dir, benchmark harness) so the builder lane writes at call 1. 3) A `bench` subcommand computing the historical side's cost straight from the ledger, so benchmark provenance grades come from files instead of inference.
gap: Detection is code; the nine-step compile ritual is entirely hand-run.

### doctor
does: Read-only install-and-estate self-check — eight named checks, PASS/WARN/FAIL with the exact fix command.
how: `doctor.py check --root|--plugin [--json]`, exits 0/5/6/3/2, SKIP for absent inputs; every check descends from a named scar. `fixture.sh` asserts each injected defect flips exactly its own check. Ships render-check.sh, gategrep.sh, seat-tax-fixture.sh, coord-volume-fixture.sh.
upgrades: 1) `--fix-script` emitting every fix line as one copy-paste block (still zero writes), turning a release close into a single paste. 2) New checks for what it cannot currently see: hooks that parse but never FIRED (assert a recent `[hook]` COORD line and a SubagentStop receipt for the last N agents), the loaded runtime mode (`notrest@skills-dir` symlink resolves to this tree), and the `claude plugin details` always-on token budget (≤ ~3.6k or FAIL with the diet command). 3) A `ship-gate.sh` composing doctor + eval + both fixtures into one exit code.
gap: It proves hooks parse, never that they fired — a silent hook passes every check.

### eval
does: Static law-conformance suite over the shipped text — eight checks, zero model tokens, seconds.
how: `eval.py check --root [--json]`, exits 0/5/6/2; negation-aware line reading; every finding cites `file:line` plus a fix hint. `behavior --case` prints a bounded one-shot and its grader but never executes it. `fixture.sh` proves each violation flips only its own check.
upgrades: 1) A `ROUTE-CONFORMANCE` check giving oracle's routing a fingerprint: the route table's targets all exist as skills, and a COORD `routed to /X` has downstream evidence. 2) A `references/*.md` citation check — `check_scripts` covers `scripts/*.py` only, so a skill citing a reference file it does not ship passes clean today. 3) `--baseline` diffing against the previous run so a release reports what conformance CHANGED, not just its current state.
gap: Judges shipped text only — any law without a textual fingerprint is invisible to it.

---

## The four vectors (owner-ratified 2026-07-25)

The roadmap's axes after v3.9.0. Each staged; a rung ships only when the one below is
fixture-proven.

**V1 — PreToolUse policy (enforcement with teeth).** The harness stops being
nudge-and-audit: hooks that BLOCK. Rung 1 (building): `hooks/pretool-gate.sh` — the ship
gate goes mechanical (`git push` in this repo blocked while doctor/eval are red) and the
SHADOW incident becomes impossible (`claude plugin install/update …notrest` blocked on
this machine); always with `NOTREST_GATE_OVERRIDE=1` as the logged escape hatch, always
fail-open on the gate's own errors. Rung 2: estate-write policy (hand-appends to
machine-owned ledgers warned). Rung 3: lane-spawn policy (a non-opus offload blocked at
the call, not discovered in the ledger).

**V2 — Autonomy (the harness runs without a seat).** Rung 1 (building):
`doctor/scripts/pulse.sh` — one unattended heartbeat: all instruments + river refresh,
one COORD line, exit 1 on any red. Rung 2 (owner's click, never self-installed): the
pulse on a daily schedule; watch's cadence on the scheduled-tasks MCP. Rung 3: a
scheduled session that acts on a red pulse (triage lane, bounded). The law stands: the
harness never schedules itself.

**V3 — Agent SDK (owning the loop).** The port path, in order: (1) a SPEC page — what
the shell owns (loop, session mgmt, surface) vs what ports untouched (the estate,
instruments, router, laws — all files + stdlib scripts + exit codes by design); (2) a
spike: a minimal claude-agent-sdk app that boots with the laws injected, the estate
mounted, and one verb end-to-end (researcher → record → river); (3) the port. Nothing
here blocks V1/V2/V4 — the plugin remains the spec and test-bed, and every law proven
in fixtures moves with us.

**V4 — Hardening (close the honesty gaps).** Rung 1 (building): watch proven LIVE on
real URLs (the last never-proven claim from the v3.5.0 handoff era dies). Rung 2: a
bounded behavioral eval arm via native `claude plugin eval` (does a research-shaped ask
actually invoke researcher? — routing measured, not asserted). Rung 3: Chains sections
for the 8 skills without them; the prose-only handoffs made mechanical. Rung 4:
multi-machine estate (the PM cross-project view proven, then the estate syncs).

## The library doctrine (owner-ratified 2026-07-26)

Reusability is a core value; the library is its instrument — **the compile doctrine
applied to knowledge**: compile detects repeated WORK and moves its stable parts into
scripts; the library detects repeated and converging KNOWLEDGE and moves it into
settled, reusable truths. Three storeys above the federation core:

1. **Concepts** — records clustered into named concepts (compile.py's df-weighted
   clustering is the donor machinery), each with the clear mapping the owner asked for:
   the asks it answers (why invoked) · the settled statement (what it does/found) · the
   member records across projects. Script clusters; the model names and bounds.
2. **The updater** — library-wide re-verification, on request and on intervals
   (watch.py's probe/hash machinery is the donor): url-evidenced records probed at zero
   model tokens (STANDS / DRIFTED / DEAD-SOURCE), drifted statements re-judged in
   session ("still true? better solution now?"), command/path-evidenced records flagged
   for session re-check rather than blindly re-executed. The scheduled pulse surfaces
   drift counts as workload data.
3. **Convergence** — when member records from multiple sessions/projects agree on one
   solution and nothing live contests it, a **crown record** (the tombstone pattern,
   inverted) marks the concept CONVERGED; `library find` surfaces the settled answer
   first. Live disagreement inside a concept = CONTESTED, surfaced never smoothed.

Status: federation core SHIPPED v3.11.0 (live-proven: this repo registered, cross-project
find returning prefixed records, PM registry fed — the last never-proven claim closed);
concepts/updater/convergence = phase 2, same builder lane, in flight toward v3.12.0.
Known seam for phase 2: RESTS-ON-REFUTED is one hop inside a single store — a refuted
record in project A does not yet flag a citing record in project B.

## Build priority (owner-redlineable)

1. **Router hook** — SHIPPED v3.7.0: the enforcement layer for "use the suite's verbs".
2. **spend.py gate upgrade** — jumped the queue on the analyst finding above: the exit-4 gate
   still enforces the retired fable-only rule, so a sonnet/haiku lane passes CLEAN today.
   Extend to the live opus-only policy (post-2026-07-15 entries, gpt lane allowlisted) +
   the COORD-AGENTS reconcile mode. The day's receipts cited a gate that can't see today's
   violations — that ends.
3. **doctor upgrades** — token-budget check via `plugin details` (≤ ~3.6k or FAIL),
   skills-dir freshness (symlink resolves to this tree), hooks-FIRED check.
4. **researcher/factcheck/marketresearcher/explainer script-first + lane-parallel** — the
   cross-cutting pattern: archivist step-0 scripted, per-option/per-claim Opus lanes,
   dossier lint gates, auto-receipts. The biggest "feels faster" lever for real work.
5. **watch.py + prove watch live** — the script makes the never-proven claim cheap to prove.
6. **Next compile** — 18 candidates scanned; each compiled ritual is zero-token repeats.
7. **On-invoke body diet** — director ~4.8k, fable-mode ~4.3k, recap ~4.1k per `plugin details`;
   fable-mode's core/references split is designed above.
8. **notrest MCP server** — the estate as typed tools (spend/COORD/archivist/compile queries).
9. **Behavioral eval baseline** — native `claude plugin eval` over the surviving cases.
