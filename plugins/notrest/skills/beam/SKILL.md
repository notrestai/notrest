---
name: beam
description: "Checkpoint in-flight agent lanes and move the remaining work to the cloud — \"beam up\" banks each lane and respawns it as a remote Opus lane; \"beam down\" folds the work home. Use on \"/beam\", \"beam up\", \"beam down\", \"beam status\", or \"I have to leave — keep the lanes running\". Checkpoint→respawn: nothing teleports."
---

# beam — the lanes keep working after you close the lid

Mid-session, four background lanes are working. The owner has to leave. Today that means
one of two bad things: the lanes die with the session, or the owner sits in front of a
laptop they no longer want to be in front of, babysitting a progress bar.

`/beam up` takes the remaining work off this machine and puts it somewhere that does not
depend on this session staying alive. `/beam down` brings it home. That is the whole verb.

**Router shape:** none (invoked by name — `/beam up`, `/beam down`, `/beam status`).

Script: `scripts/beam.py` (python3 stdlib; git plumbing only). Fixture: `scripts/fixture.sh`
— 170 assertions over a scratch repo, a real bare remote and a fake cloud clone, including
the no-touch proof below.

## The physics — read this before you promise anything

**Nothing teleports process memory.** A running lane cannot be moved; it can only be
CHECKPOINTED and RESPAWNED. What survives is exactly three things:

- the **brief** — why the lane exists and what "done" means,
- a **digest of what it has done so far**, and
- the **files it was holding**.

Everything else — the context window, the tool history, the model's train of thought — dies
at the checkpoint. It is not recoverable by any mechanism, cloud or otherwise. Say this to
the owner in those words when you beam. A respawned lane that is told "you were paused" will
confidently narrate work it never did; a lane that is told "you were checkpointed, verify
what you lean on" re-derives instead.

**The estate is the wire.** The payload is plain files under `beam/<ts>/`, published as a
git ref (`refs/heads/beam/<ts>`). A remote session clones the ref, works, and **commits its
deliverables back to that ref**. Recall reads the ref. Nothing anywhere depends on a live
session being reachable — a live session is exactly the thing that just went away.

**Transport laws** (each one has cost somebody a night's work somewhere):

- **Untracked files never travel.** Whatever is not committed on the ref does not exist to
  the far side. `snapshot` commits the payload for you; a remote session that leaves work
  uncommitted has delivered nothing, however good its transcript reads.
- **Prompts are context-bounded; repositories are not.** The respawn prompt is ONE LINE —
  fetch, checkout, read `beam/<ts>/CHECKPOINT.md`, execute it. The instruction lives in the
  repo. Never paste a whole plan into a prompt that a scheduler may re-wrap.
- **The far side lands on the wrong branch by default.** Cloud sessions clone the current
  branch; scheduled runs clone the *default* branch. Neither is the beam ref, and this
  machine never switches branches — so checking out the ref is step 0 of the instruction,
  not an assumption.
- **The harness does not travel by itself.** User-scoped skills, agents and CLAUDE.md stay
  on this machine; a beamed session lands bare. `snapshot` therefore merges marketplace +
  `enabledPlugins` keys into the **ref's** `.claude/settings.json` (never the working copy)
  so the clone installs notrest for itself. The shadow-guard law — never install
  `notrest@notrest` here — is MACHINE-scoped: on a cloud VM with no skills-dir symlink,
  installing from the marketplace is the correct move, not a violation.

## The seat/script split

The **model** owns what only the harness exposes: which lanes are live, what each one was
told, and how far each got. No script can read the harness's task list or a lane's output
files — so the inventory and the per-lane digest are yours to write, honestly, from what you
can actually see.

`beam.py` owns everything else: payload layout, the manifest, the git mechanics, the recall
diff. Never hand-roll the git side — the plumbing constraints below are not decoration.

## Wait or force? — decide this before you bank anything

| the lane is… | do this | why |
|---|---|---|
| **finished** | no beam needed | its results are already in the receipts and the estate |
| **nearly done** | **wait** | the stride you would lose costs more than the minutes you would save |
| **long-running / early** | **force** | the loss is minutes of stride; the gain is hours of unattended work |
| **the seat itself** | see below | a seat is not a lane — it hands over, it does not respawn |

**The seat has two rails of its own**, and both are first-class — this is the harness's own
continuity flow (`/sessionend` → `START-HERE.md`), not a degraded mode:

- **Desktop:** *Continue in → Claude Code on the Web* — native hand-off, wants a clean tree.
- **Cold-boot successor:** the cloud session started by `claude --cloud` reads
  `CHECKPOINT.md` plus the banked estate and takes the seat from there.

## `/beam up`

Pick one `<ts>` id for the whole beam (e.g. `2026-07-26T2340Z`) — it is both a directory and
a git ref component, so keep it to `[A-Za-z0-9._-]`.

1. **Inventory the live lanes (model only).** Read the harness's task list and each lane's
   output. For every lane still in flight, name it: label, what it was told, what it has
   actually produced so far, which files it is holding. A lane you cannot describe is a lane
   you cannot beam — say so rather than banking a guess.
2. **Default: bank the finished and idle lanes; ASK about each running one.** Per running
   lane, one question to the owner: wait for it, or stop it and send it? Beaming spawns
   remote work and publishes a branch — the owner asks for it, and the harness never
   self-schedules a beam.
   **`/beam up --force` skips the asking**: every running lane is banked from its
   transcript-derived digest and the files it actually wrote, then **stopped**, then
   respawned from its payload. Force-stopped lanes are banked with `--forced` so the pinned
   LOSS-ESTIMATE lands in the payload, the resume prompt, the manifest row and `status`:
   *stopped mid-flight; progress banked through the last durable artifact; the respawn
   re-derives the unbanked stride.* Never let a forced beam be described as lossless — the
   trade is a known, bounded loss for an unbounded gain in wall-clock, and it is only worth
   making out loud.
3. **Write the per-lane files** — `brief.md` (the original job, unedited: the remote lane is
   doing the same work, not a summary of it) and `progress.md` (your digest, graded: what is
   `[cited]` from a lane's own output vs `[estimate]` from your reading of it). Optional
   newline file list of what the lane holds.
4. **Bank each lane:**
   `beam.py bank --root . --ts <ts> --lane <label> --brief <f> --progress <f> [--files <f>]`
5. **Manifest + checkpoint:** `beam.py manifest --root . --ts <ts>` writes `MANIFEST.md`
   (lanes, states, recall checklist) and `CHECKPOINT.md` — the cloud session's entire
   instruction: checkout first, install the harness, run the lanes in order as background
   opus agents, commit and push, sign off in `CLOUD-DONE.md`.
6. **Publish:** `beam.py snapshot --root . --ts <ts> --push --remote origin`. This commits
   the CURRENT tree — dirty tracked files included — onto the beam ref using a temporary
   index, merges the harness settings into the ref's copy only, and prints its own no-touch
   proof: HEAD, `.git/index` and the dirty set, before → after. If that line does not say
   `UNCHANGED`, stop and investigate. If the carriage line says `SKIPPED`, the far side will
   land without the harness — fix the settings file or say so out loud.
7. **Respawn:** `beam.py rail --root . --ts <ts>` prints the paths in the order that
   actually works. Take path (a) — a cloud session — unless you have a reason not to.
   `model: "opus"` is explicit and never optional; never `subagent_type: "fork"` — a fork
   inherits the seat's model.
8. **Record it:** `beam.py mark --root . --ts <ts> --lane <label> --state SPAWNED:<id>
   [--session-url <url>] [--meta <path>]` — or `--state FORCED:<id>` for a lane that was
   stopped mid-flight, so recall can tell a clean respawn from a re-derivation. Handles are
   how a future session finds this work without you in the room; a handle that lives only in
   a transcript is a handle that is already gone.
9. **Leave a trail:** append one COORD.md line — the ts, the ref, the lanes and their remote
   ids, and what recall will look like. The owner walks away from this line, not from you.

## `/beam down`

1. `beam.py down --root . --ts <ts> --fetch --remote origin` — fetches the ref into its own
   recall namespace (never clobbering the local branch) and prints per lane
   **DELIVERED** (with paths) or **MISSING**. Exit 3 means at least one lane is still out.
   It also reads `CLOUD-DONE.md`: a ref with deliverables but no sign-off means the far side
   never said it finished, which is a different fact from "a lane delivered nothing".
2. **Fold by hand.** `down` emits `git show <ref>:<path> > <path>` lines and executes none of
   them. Overwriting the owner's working tree is the owner's act, and a fold that lands on
   top of local edits is how a session eats a morning's work. Read the diffs first —
   especially for a `FORCED` lane, whose deliverable is a re-derivation and may have solved
   the unbanked stride differently than the lane that was stopped.
3. **Receipts.** A remote lane the SubagentStop hook did not receipt has no ledger line at
   all. Log one per lane: `spend.py log --lane beam-remote --model <what you set> --tokens
   <n if the harness printed one> --grade observed|estimate --purpose "beam <ts> <label>"`.
   Grade by what is actually observable — a remote lane's token count usually is not, and an
   estimate that is labelled is worth more than a number that is not. The ledger is
   append-only through `spend.py`; never hand-log what the hook already receipted.
4. **Mark:** `beam.py mark ... --state RECALLED` per lane you folded.
5. **Need the conversation, not just the commits?** `claude --teleport <session-id>` (or
   `/tp <session-id>`) reopens the cloud session itself. The ref carries the work; teleport
   carries the reasoning. Use it when a deliverable is puzzling, not as the recall path.
6. **COORD line:** what landed, what is still MISSING, where the ref is. A MISSING lane that
   goes unmentioned becomes a silently abandoned piece of work.

## `/beam status`

`beam.py status --root .` — one line per checkpoint: lane count, state split, ref, pushed.
Cheap, read-only, and the right first move when the owner comes back and asks "what's out?".

## The laws

- **Explicit opus on every respawn.** A respawn that omits the model silently inherits the
  seat's model and bills it. Never `subagent_type: "fork"`.
- **Deliverables live on the beam ref, never only in a session.** If a remote lane's work is
  not committed and pushed, it does not exist — the recall cannot fetch a transcript.
- **A payload the door would reject is not a payload.** Where the original brief said to
  emit finding records, the respawned lane still emits them, validated at the archivist
  door, honesty labels intact. Beaming is not a laundering step.
- **The harness never self-schedules.** A beam happens because the owner asked for one.
- **Never checkout, switch, stash or reset in the live tree.** On this machine the tree is a
  plugin loaded IN PLACE — a checkout would swap the running harness out from under the
  session. `beam.py` uses plumbing against a temporary index and proves it; the fixture
  re-proves it independently against HEAD, `.git/index`, `git status --porcelain` bytes and
  the HEAD reflog length.
- **Say what died at the checkpoint.** Every beam report names the physics: brief, digest and
  files travelled; context and tool history did not. A force-stopped lane additionally lost
  the stride since its last durable artifact, and the LOSS-ESTIMATE says so in writing.

## The rail — where the work actually goes

`beam.py rail` is the ONLY place the rail's semantics live: one subcommand, versioned
`RAIL v1`. Everything else here is storage and git plumbing that stays true no matter how a
remote session is started, so when the rail changes, that one function changes and nothing
else does. Do not invent rail behavior anywhere else. It prints four paths, in this order
for a verified reason:

- **(a) PRIMARY — a cloud session.** `claude --cloud "git fetch origin beam/<ts> && git
  checkout beam/<ts>, then read beam/<ts>/CHECKPOINT.md and execute it"`. This detaches for
  real: it keeps running with the laptop closed, and a reclaimed environment restores its
  history when reopened. This is the path the owner is actually asking for.
- **(b) SCHEDULED KICK — a one-off routine**, when the work should start later. Same one
  line. A routine clones the *default* branch, and its fire-text reaches the session wrapped
  as untrusted content — so the saved prompt must name this exact ref and say plainly that
  it is the owner's own beam instruction, or the receiving session is right to refuse it.
  The owner creates the routine; the harness never self-schedules.
- **(c) DESKTOP — Continue in → Claude Code on the Web.** Wants a clean tree, so snapshot
  first and let the ref carry the dirty state.
- **(d) GATED FAST PATH — `Agent(isolation: "remote")`.** Server-gated, and when the gate is
  shut it **degrades silently** to a local agent that dies with this session: it looks
  beamed and is not. Use it only if you then assert the result's status is
  `remote_launched`; anything else means it never left, and that lane goes out via (a).

`beam.py` never spawns anything itself — it prints; the seat, which holds the tools and the
owner's consent, decides whether to make the call.

## Self-check before finishing

- Every live lane is either banked or explicitly listed as **not** beamed, with a reason —
  and every running lane was either asked about or `--force`-banked with its LOSS-ESTIMATE.
- The snapshot printed `UNCHANGED`, the carriage line did not say `SKIPPED`, and the ref is
  really on the remote (`--push` succeeded) — a payload on this disk alone is not a beam.
- Every respawn named `model: "opus"`; every spawn that returned an id got a `mark` (with
  `FORCED:` where the lane was stopped); if path (d) was used, the result's status was
  actually asserted to be `remote_launched` rather than assumed.
- The physics was stated to the owner in plain words — nothing was described as "moved" or
  "still running" when it was checkpointed and restarted, and no forced beam was called
  lossless.
- On recall: exit 3 was surfaced verbatim, not smoothed; a missing `CLOUD-DONE.md` was
  reported as "did not sign off", not as success; nothing was folded silently; every remote
  lane has a ledger line or a stated reason it is unobservable.

## Finishing up

Chains: `/spend report` after recall (the beam lanes should show as opus); `/recap` reads
the COORD lines a beam leaves; `/archivist` holds the records the remote lanes emitted;
`/watch` can hold a MISSING lane on the calendar instead of in someone's memory. Pairs with
`agentswarm` — swarm decides what runs in parallel, beam decides where it runs when the
owner leaves the room.
