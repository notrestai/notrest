# Changelog — ORACLE Suite

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
