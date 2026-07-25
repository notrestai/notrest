---
name: agentswarm
description: The fast delegation arrangement (Oracle family) — the seat (the main session's model) keeps decompose/judge/apply/gate and instantly offloads everything else to in-session background Opus agents and Workflow pipelines; the harness is the wire (no blackboards, no watches, no rotation choreography). Applies to ANY seat — a Fable session or an Opus session alike. Use on "/agentswarm", "agent swarm", "swarm this", "offload this", or BY DEFAULT whenever a session delegates substantial work on this machine; the legacy "/fable-swarm" and "fable swarm" still mean this skill. MODEL POLICY (owner-set 2026-07-15) — every offloaded job runs on explicit OPUS: no sonnet, no haiku, never an inherited seat model. For multi-day / multi-machine / owner-watchable arrangements, use fable-director instead.
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
   call 1, not forage.
3. **Budget empirical lanes** — ~10 tool calls; past budget, PLAUSIBLE-with-scenario beats
   a third reproduction (root-cause-with-a-budget, applied to QC).
4. **Tier the gate by blast radius** — full multi-way gate + refuter for executable /
   load-bearing artifacts; grep-and-read for docs; nothing for cosmetic.
5. **Persistent QC lane** — resume the same refuter per round like the builder; round N
   refutation costs the delta.
6. **Never idle the seat** — only ship-blocking lanes are worth waiting for; everything
   else lands async and is read next turn.

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
- **Agent activity records itself.** Every completed lane is auto-written to
  `COORD-AGENTS.md` by the SubagentStop hook — id · model · last conclusion · transcript
  path — at zero prompt overhead. Never instruct a lane to write a process/summary file;
  the harness writes the transcript and the hook writes the index. The seat consumes tight
  returns; the durable record lands for free.
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
