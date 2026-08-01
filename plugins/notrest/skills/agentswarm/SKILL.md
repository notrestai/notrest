---
name: agentswarm
description: "The default delegation arrangement — the seat keeps decompose/judge/apply/gate, background lanes do the rest. MODEL POLICY: every offloaded job sets model \"opus\" explicitly — no sonnet, no haiku, never subagent_type \"fork\" (forks inherit the seat). Builds run ONE persistent lane, resumed for feedback. Use on \"/agentswarm\", \"swarm this\", \"offload this\", legacy \"/fable-swarm\", or BY DEFAULT whenever a session delegates substantial work. Multi-day arrangements: fable-director."
---

# agentswarm — the seat and the swarm

**THE SEAT is the main session's model** — Fable when Fable is driving, otherwise the
latest Opus. The arrangement is the same either way: the seat decomposes, judges, applies,
and gates; the swarm does everything else. Nothing here depends on which model holds the
seat, and the few genuinely Fable-specific laws are marked as such where they appear.

Fable-director's blackboard-and-watch machinery exists for one constraint: a metered
API-key director whose in-session subagents would bill Fable-priced credit. Where that
constraint doesn't hold — a session in Claude Code with the Agent and Workflow tools —
the machinery is pure drag. This skill is the fast arrangement for that case:
same roles, same discipline, **the harness as the wire**. It deletes fable-director's
three worst failure classes by construction: deaf lanes (no watches to re-arm —
completion notifications are guaranteed), queued ≠ delivered (no message hops), and
split-brain rotation (no successor sessions). A round trip that took minutes and owner
confirm-clicks becomes: one message spawns N concurrent lanes, results return in
seconds to minutes, zero clicks.

## The model rule (owner-set 2026-07-15, absolute — regardless of what the seat is)

**Every offloaded job runs on Opus.** Set `model: "opus"` explicitly — the alias, which
floats to the latest Opus — on every Agent call and every Workflow `agent()` call: no
sonnet, no haiku, and never a silently inherited seat model. This holds whatever model
holds the seat. The owner chose closest-to-seat quality on all delegated work over
per-token savings; it supersedes the earlier sonnet/haiku difficulty ladder wherever the
swarm operates. Three guards stay on:

- **Fable never rides in a subagent.** (Fable-specific law — it is about Fable credit and
  stays absolute.) Under a Fable seat an omitted `model` silently inherits Fable, and the
  omission is the violation. Under any seat, an omitted `model` is still a violation: the
  lane must be explicitly labeled. The spend report's exit-4 gate makes this checkable.
- **Never spawn `subagent_type: "fork"` — from any seat.** Forks IGNORE the `model`
  parameter and always inherit the PARENT model. Under a Fable seat that is a policy
  violation (the lane rides Fable while the ledger records the intended opus — one the
  exit-4 gate cannot catch); under an Opus seat it is an unlabeled lane that defeats the
  ledger's explicitness. Banned either way. Use a fresh non-fork Opus agent and hand it
  the context it needs.
- **Receipts, not vibes.** Opus fan-out costs real tokens; the spend ledger receipts
  every lane so the policy can be revisited with numbers, not guesses.

The **gpt lane** is unaffected (it bills the owner's ChatGPT plan, not this session).

## The seat contract — what the seat keeps

The seat stays the seat regardless of model. It keeps exactly the work where its judgment
earns its price, nothing else:

1. **Decompose** — cut the objective into lane-sized jobs with grep-able done-whens.
2. **Judge** — read lane briefs adversarially; a lane's "done" is a claim, not a fact.
3. **Apply** — all edits land by the seat's hands, verify-before-apply unchanged:
   read the target region, grep the claim including tests and route/dispatch layers.
4. **Gate** — ships, secrets, DNS, billing, anything irreversible: seat + owner only.
5. **Talk to the owner** — one voice; lanes never address the owner.

Two standing prohibitions at the seat, true for every seat: never `/model`-switch (the
prompt cache is per-model, so a switch re-reads the context cold — delegation via
subagents costs no cache at all; a model change is a subagent or a handoff), and never do
lane-work inline that a lane could do concurrently (the seat's context is the scarcest
resource in the arrangement).

## The wire — how lanes run

- **Agent tool, background by default.** Batch independent spawns in ONE message so
  they run concurrently. The harness notifies on completion — no polling, no watches.
- **Tight returns.** Every lane prompt ends with an explicit return contract:
  conclusions, paths, and evidence — never file dumps. The seat consumes results, not
  raw material a lane already read.
- **Workflow for structured fan-outs** — reviews, sweeps, migrations, research
  pipelines. Every `agent()` call carries `model: "opus"`. Schema-forced outputs keep
  returns machine-tight.
- **Blocked ≠ stopped.** A lane hitting a wall doesn't idle the swarm: the seat keeps
  every unblocked lane moving and re-probes the blocked path cheaply next turn.

### No caps — as many lanes, as many swarms, as the job needs

- **No numeric limit.** The swarm caps nothing: not lanes, not concurrent fan-outs, not
  simultaneous swarms. Scale is decided by the job's decomposition, never by a count —
  spawning the 15th narrow lane is cheaper than making the 3rd broad one.
- **Proven scale** (owner's dig.rest DIR sessions, measured from transcripts on this
  machine, 2026-07-23): single sessions ran 16, 15, and 11 concurrent-era agents; one lane
  returned a ~1 MB transcript; that repo's `COORD-AGENTS.md` carries 40 machine-written
  entries. The arrangement held and the estate recorded all of it.
- **The only real ceilings are HARNESS-level — the owner's dials, not the skill's.** The
  Workflow tool runs ~16 concurrent agent slots per run and queues the excess
  automatically (pass 100 items and they all complete); the app's workflow-size guideline
  is adjustable via "Dynamic workflow size" in `/config`; Agent-tool lanes have no
  practical cap. **Never present a harness queue as a reason to shrink the job.**
- **Multiple swarms compose.** Several persistent builder lanes (one per domain) plus
  diagnosis fan-outs plus refuter panels can all run at once — and separate SESSIONS each
  running their own swarm on the same repo coexist safely: the estate files are
  append-only / flock-guarded, and `COORD-AGENTS.md` receipts every lane from every
  session (the DIR + DIR2 precedent).
- **What makes uncapped safe is already law:** narrow lanes, tight returns, receipts per
  lane, trail-walk at the gate. Scale the count, never loosen the contract.

## Persistent builder lanes — the seat-builder ritual (owner-ratified 2026-07-21)

For substantive BUILDS, the swarm runs one level deeper than fire-and-forget lanes.
The seat never hand-builds a feature; it specs, gates, and ships:

1. **Spec at the seat** — objective, constraints, exact deliverables, grep-able
   done-when. The spec is the lane's whole onboarding; write it like a directive.
2. **One persistent Opus builder lane per domain** — spawn it once; it builds and
   returns tight (paths + what changed + how verified, never dumps).
3. **Feedback rounds RESUME THE SAME LANE** (SendMessage to its id/name) — never a
   fresh spawn. The lane's accumulated context of the code it wrote is both the
   token saving (round N costs the delta, not a re-onboarding) and the quality
   keeper (proven across 6+ rounds live). A fresh lane per round forfeits both.
4. **The seat gates every round:** verification commands exit-code-checked — never
   piped through `| tail`/`| head` (they eat the exit code); grep the actual
   bundle/artifact for the claimed change; bank the round as a ledger line.
5. **Scope the lanes by domain** — two domains = two builder lanes, not one
   mega-lane; diagnosis and exploration stay parallel one-shot lanes (fan out,
   consume conclusions, discard).
6. **Gate every return, multiple ways** — the seat NEVER accepts a lane's
   self-reported verification. It re-runs the verification itself, exit-code-checked
   (never `| tail`/`| head` — they eat the exit code); parse-checks each artifact by
   kind (`bash -n` for shell, `json.load` for JSON, `py_compile` for python); greps
   every claimed edit against the tree; reads the core artifact's code at the seat;
   sends the riskiest artifact to an independent refuter lane (review-the-fix by a
   different lane than the builder); and when the deliverable RENDERS (an HTML page,
   a diagram, a UI) opens it and looks — screenshot both themes, console clean —
   before accepting (the game-forge no-unrun-ships ethos). A gate that only reads the
   lane's report is not a gate.
7. **Decompose greenfield builds — the DOMAIN is the unit, not the deliverable.** A new
   skill or feature is not one lane's job just because it ships as one thing. Split it
   along **file boundaries** into parallel narrow lanes — the core script/artifact lane
   ∥ the contract/SKILL lane ∥ a docs-rows one-shot — and hand each one a tight
   **interface spec inline** (exact filenames, exact command signatures, exact table
   columns) so they compose without ever talking to each other. The **core artifact's
   lane is the persistent one** for feedback rounds; the rest are one-shots that finish
   and are discarded. Wall-clock is the slowest lane, not the sum, and the arithmetic is
   measured on this machine: **~20-tool-call lanes land in ≈3.5 min; 72–77-call monolith
   lanes take ≈22–24 min** — near-linear in tool calls. One lane doing three domains is
   therefore three times the wall-clock for the same tokens.
8. **Domains are computed, not guessed.** Rules 5 and 7 command domain-scoped lanes split
   along file boundaries — but a TOUCH-ONLY list drawn from the seat's memory of the tree
   is a guess. When lanes will touch a SHARED tree, the seat runs the partitioner and
   reads the answer: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/graph/scripts/graph.py domains
   --root . (--paths P1 P2 ... | --changed | --all) [--lanes N] [--json]`. Lanes are the
   connected components of the file-link graph restricted to the scope — hubs are
   extracted FIRST, then components are found on the remainder, and **a component is
   never split**; `--lanes N` merges the smallest first (by bytes) toward N. Each lane's
   **TOUCH ONLY** list is lifted verbatim from `lanes[].files`. Files everyone links to
   belong to no lane: **`seat_held`** (in-scope degree ≥ `max(4, 3 × median in-scope
   degree)`) stays at the seat — manifests, shared config, the contracts the lanes compose
   against. An empty scope is exit 2, never a silent `lanes: []` — a quiet no-op is the
   moment a seat shrugs and hand-partitions from memory. Every `boundary` line is pasted into the commission that owns its `from` side
   as **"you may READ `<to>`, never edit; the interface is `<name it>`"** — naming the
   interface is the seat's job, not the tool's. The command **exits 2 rather than
   guessing**: no scope flag, a named path missing from the tree, a non-git root.
   *Worked example.* `lanes:[{id:1,files:["scripts/graph.py","tests/test_graph.py"]},
   {id:2,files:["SKILL.md"]}]`, `seat_held:[{file:"plugin.json",degree:6}]`, `boundary:
   SKILL.md -> scripts/graph.py (lane 1)` → lane 1's commission reads *"TOUCH ONLY
   scripts/graph.py, tests/test_graph.py"*; lane 2's reads *"TOUCH ONLY SKILL.md — you may
   READ scripts/graph.py, never edit; the interface is the `domains` argv contract"*; and
   `plugin.json` is in neither commission because the seat edits it after both land.
   **THE GRAPH KNOWS LINKS, NOT SEMANTICS.** Two files with no edge between them can still
   collide at runtime — same output path, same port, same env var, same fixture directory
   — and no link scanner can see it. The tool **PROPOSES** the partition; the seat
   **REVIEWS** it before dispatch. A partition accepted unreviewed is a guess wearing a
   uniform.

## Synthesis at fan-in — digest, never verdict

When a round returns **4+ lanes at once** — or returns totalling roughly **200+ lines** —
reading them all at the seat spends the scarcest resource in the arrangement on
secretarial work. The seat spawns ONE synthesis lane to do it instead. Same rules as every
lane, no exceptions: `model: "opus"` set explicitly, receipted in the spend ledger, banked
by the SubagentStop hook.

Its commission is narrow by construction:

- **Input is the N return blocks, VERBATIM** — pasted into the prompt. The lane runs **NO
  tools and opens NO files**; anything it cannot confirm from the returns alone is marked
  **"unverifiable in digest"** rather than looked up. A digest lane that reads the tree has
  become an unbriefed reviewer.
- **Output is per-lane** — *claimed / evidence cited / deviations & disclosures / counts* —
  plus ONE **CONTRADICTIONS** section naming every shared fact two lanes report
  differently: a count, a file's state, an exit code, whether a thing exists at all.
- **No recommendation, and no ship/accept vocabulary.** Not "looks good", not "ready", not
  "all green". Its output is labeled **"digest, not verdict"** — that label is VERBATIM and
  load-bearing, because a digest arriving without it reads as a verdict, which is the
  failure it exists to prevent.

The seat still reads **every lane's verdict line itself** and still gates per builder-lane
rule 6 — re-running the verification exit-code-checked, grepping each claimed edit against
the tree, refuting the riskiest artifact. The digest spends one lane's context instead of
the seat's; it never spends the seat's judgment. **Why the split is law: a summarizer that
also gates is how "all lanes green" becomes a claim nobody checked.**

## Trail-walk — how the seat judges

Before the seat accepts a lane's work, chooses between conflicting findings, or gates a
ship, it walks the recorded trail IN TIMESTAMP ORDER instead of judging from memory:

1. **COORD.md ledger tail** — what each prompt actually landed, with evidence.
2. **The relevant COORD-AGENTS.md entries** — what each agent was asked and concluded,
   in the sequence they finished.
3. **The transcript paths on those entries** — when a one-line conclusion isn't enough
   evidence, `grep` the full record instead of trusting the summary.
4. **git diff** — what actually changed in the tree, not what a lane said changed.
5. **The spend ledger** — what the round cost.

Decisions cite trail entries, not recollection. When the seat's memory and the trail
disagree, **THE TRAIL WINS** — it was written when the work landed (the same tiebreaker as
COORD vs HANDOFF). The trail also survives compaction and rotation: a successor seat
reconstructs why every decision was made by replaying it in order, with no live context.

## Speed discipline — wall-clock is the slowest lane

Speed discipline is the OWNER-EXPERIENCE contract of the swarm — the owner keeps a
responsive seat that answers while lanes work, and results land as fast as the slowest
NARROW lane; a seat that idles waiting on one broad lane is the arrangement failing its user.

1. **Narrow lanes in parallel beat one broad lane** — wall-clock equals the slowest lane,
   not the sum; three refuters with two attack surfaces each finish in a third of one
   six-surface refuter (same tokens, same policy).
2. **Hand the lane its material inline** — paste the artifact and the exact contract into
   the prompt; every read round-trip saved is wall-clock saved; a lane should attack at
   call 1, not forage. **This applies hardest to builders: never send a builder a reading
   list.** "Read these five skills first to absorb the house voice" costs 5–10 round trips
   before the first written line; the seat pastes a ~20-line **style capsule** inline
   instead — the voice, the frontmatter shape, the honesty-rules pattern, the self-check
   pattern — and the lane writes at call 1.
3. **Budget empirical lanes** — ~10 tool calls; past budget, PLAUSIBLE-with-scenario beats
   a third reproduction (root-cause-with-a-budget, applied to QC).
4. **Tier the gate by blast radius** — full multi-way gate + refuter for executable /
   load-bearing artifacts; grep-and-read for docs; nothing for cosmetic.
5. **Persistent QC lane** — resume the same refuter per round like the builder; round N
   refutation costs the delta.
6. **Never idle the seat** — only ship-blocking lanes are worth waiting for; everything
   else lands async and is read next turn.
7. **One fixture run per lane, at the end.** The seat re-runs the whole suite at the gate
   anyway, so a mid-build full-suite rerun is duplicate spend *and* duplicate minutes.
   Targeted spot-checks while building are fine and encouraged — it is the full suite,
   run repeatedly by the lane, that buys nothing.
8. **Release slicing — gated work ships.** Work that has passed the gate is never held
   hostage to an unrelated lane that is still running; batch a release only when the
   pieces are genuinely **file-coupled** (shared counts, shared manifests, one CHANGELOG
   entry that must be true). The owner waiting on the slowest lane of an *uncoupled*
   batch is the arrangement failing its user.

## QC — the refuter, as code

Fable-director's QC relay becomes a verification stage that runs automatically, not a
session you hope pings back. Before the seat acts on any lane finding graded
CONFIRMED, an independent Opus refuter lane attacks it (V4 §6, inlined):

- "never called / never passed" claims → check route/dispatch layers, string-keyed
  handlers (onclick / event maps / `window.*`), AND test harnesses in scope.
- External claims → two independent sources, labeled.
- Every finding needs a **concrete failure scenario** (inputs → wrong outcome) or it
  is downgraded to PLAUSIBLE.
- **Review-the-fix by a different lane than the finder.**

In Workflow form this is one verify stage after every find stage — the refuter runs
while other lanes still work; no barrier unless dedup genuinely needs one.

## Receipts and estate

- **spend** — log every completed lane at the moment the notification shows its count. The
  ledger records the model id **exactly as observed in the lane transcript**, verbatim — never
  a remembered or assumed pin (`opus` resolves to whatever the latest Opus is, and the receipt
  must say which one actually ran):
  `python3 <spend-skill>/scripts/spend.py log --lane subagent --model <the id observed in the
  lane transcript, e.g. claude-opus-5> --tokens <N> --grade observed --purpose "..."`. Close
  with `spend.py report`; exit 4 is surfaced verbatim, never smoothed.
- **archivist** — before any research fan-out, consult `oracle-index.md`; a question
  the estate already answered costs one grep, not a lane.
- **compile** — before spawning a lane for a job, check `compile/` — a compiled runtime
  the estate already paid for beats re-deriving it at model prices.
- **Agent activity records itself.** Every completed lane is auto-written to
  `COORD-AGENTS.md` by the SubagentStop hook — id · model · last conclusion · transcript
  path · brief pointer — at zero prompt overhead. Never instruct a lane to write a
  process/summary file; the harness writes the transcript and the hook writes the index.
  The seat consumes tight returns; the durable record lands for free.
- **Commission transparency is a CORE VALUE, not a courtesy.** *Transparency about what we
  ask our agents is a core value: the commission is never hidden — named at dispatch,
  banked on disk, marked in the pictures.* It binds at three moments:
  - **At dispatch** — the seat names each lane's commission to the user in plain language,
    as it dispatches. When the ask is the owner's scope, the seat shows the **full prompt**,
    not a paraphrase — and never leaves it to be discovered in the lane brief alone. A
    commission the owner has to go looking for was not disclosed.
  - **At rest** — every commission is banked by construction: the SubagentStop hook
    extracts the exact prompt to `briefs/agent-<id>.md`, so the owner reads any prompt
    without asking anyone. Written once and never rewritten, a brief is what was actually
    sent — not a later account of it.
  - **Under narrowing** — a brief that narrows the owner's ask must say so in its first
    lines (fable-mode 12a). Disclosure at delivery is the floor; the extraction is what
    makes it auditable at any scale, because the seat's account is checkable against the
    prompt on disk.
- **Estate files (STATE / HANDOFF / coord) are banking and crash insurance, NOT a
  message bus.** Lanes die with the app — so the seat BANKs at every seam: what's
  dispatched, what's landed, the exact resume payload. A cold session re-seats the
  swarm from the estate in one read.

## When fable-director instead

Honest boundary: the swarm's lanes live inside this session. Reach for fable-director
when the arrangement must **survive the machine sleeping** (multi-day builds), span
**multiple machines or accounts**, or when the owner wants **watchable lanes in app
panes**. Otherwise the swarm is faster, cheaper to coordinate, and has strictly fewer
failure modes.

## Self-check before finishing

- Every spawned lane carried `model: "opus"` — transcript-verifiable, and logged to
  the spend ledger with its observed token count (or named as unobservable and why).
- The seat never `/model`-switched and never rode a lane's workload inline.
- Every CONFIRMED finding the seat acted on survived an independent refuter lane.
- The estate was banked at every seam; a cold session could re-seat the swarm from it.
- `spend.py report` ran at close; the verdict line is in the transcript.

## Finishing up

Chains: `/spend` (the receipts are the policy's audit trail), `/archivist` (index
before fan-out), `/critic --panel` (its lenses run as swarm lanes), `/sessionend`
(banks the estate and reports the spend). Fable-director remains the sibling for the
multi-session case — and its V4 discipline (edit specs, refuter checklist, ship gates)
is exactly what this skill runs, minus the sessions.
