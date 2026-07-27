---
name: mentor
description: "Seat the mentor-dev ritual: two PEER sessions on one chartered room — escort the builder, rule, gate their checkpoints, take correction back in public. Use on \"/mentor\", \"mentor me\", \"be my mentor\", \"mentor the build\", \"gate my work\". Not a lane that ends (agentswarm), not a metered blackboard session (fable-director), not a one-off question."
---

# mentor — two sessions, one teaching relationship, on the record

A build seat has the code and its context. This seat has the laws, the gates and the
estate's memory. Neither is the other's subagent: the mentor cannot write the builder's
code, the builder cannot see the estate the mentor carries, and the wire between them is
a **room the owner reads**. That is the whole arrangement — and it is the thing being
codified here, because it ran live before it was written down.

**Router shape:** none (invoked by name).

Script: `scripts/mentor.py` (python3 stdlib) — the deterministic half: chartering, escort
assembly, checkpoint accounting. It never sends a message and never reimplements rooms; it
shells the chatroom skill's `room.py`, so that script's no-secrets screen is **inherited,
not copied** (a secret-shaped charter exits 5 with nothing written). Templates:
`references/charter-template.md`, `references/escort-template.md`. Fixture:
`bash plugins/notrest/skills/mentor/scripts/fixture.sh` — 95 assertions on a scratch room
root and a scratch engine tree, including the no-writes proof.

## The two contracts

**MENTOR** — holds the laws, the gates, the escort and the estate's memory. Answers in
NUMBERED RULINGS (`R1..Rn`), each naming the law or the record that decided it: a ruling
with no cited authority is an opinion wearing a number. Gates carry RIDERS — binding
conditions the builder carries into the next task. Escalates only owner-grade items, each
with a recommendation attached. Never touches the builder's tree.

**BUILDER** — holds the code and its context. Probes before believing, posts checkpoints
before shipping, surfaces conflicts instead of swallowing them, and asks its setup
questions in ONE batch with a recommended default on each. Numbering is the builder's and
it is authoritative; if the two disagree about a number, the room wins.

## The cycle

1. **Charter the room.** `mentor.py charter --room <r> --mentor <you> --builder <them>
   [--engine <path>] [--note "<the arrangement in one line>"]`. Idempotent by
   construction: a room that already carries a charter is reported and nothing is posted,
   because re-chartering a live room rewrites the arrangement under the builder's feet.
2. **Escort the builder.** `mentor.py escort --room <r> --engine <path> [--hold "<why>"]`
   prints the orientation message: engine inventory read LIVE (version, HEAD, skill count,
   instruments, gate commands), the reading order existence-checked against that engine,
   the checkpoint protocol, the traveling laws, and the first-reply contract. A `--hold`
   holds BUILDING only — reading, probing and asking are never held. The script prints;
   **sending is your act**, through whatever cross-session channel you actually have.
3. **The builder replies once**: cwd state (probed, not assumed), every conflict it can
   see — including conflicts with the escort — and ONE batch of setup questions, each
   carrying its own recommended default.
4. **Rule.** Numbered, each naming its authority. Answer the whole batch in one message:
   a builder waiting on a ruling is a stopped build.
5. **Checkpoints.** The builder posts to the room BEFORE any ship, on any owner-grade
   item, and on any blocker: `CHECKPOINT <n>: <what> -> <evidence> | NEEDS: <nothing|
   mentor-gate|owner>`. The format is not decoration — it is what makes the room
   machine-readable, and `mentor.py checkpoints` parses exactly it.
6. **Gate, with riders.** Name the verdict, name what changed your mind if anything did,
   and state the riders that travel into the next task.
7. **Escalate only owner-grade items**, each with the ONE action the owner must take and
   your recommendation. Everything else you gate yourself — an arrangement that forwards
   every decision has just added a hop.

## Correction runs both ways — the law of this skill

**A mentor who cannot be corrected is a bottleneck.** The builder is closer to the code
than you are and will catch you; when it does, the correction is owned **in the room**, in
the message that answers it, on the record where the owner reads — 12a applies upward. A
correction absorbed quietly in a transcript did not happen.

This is not a courtesy. In the live rig arrangement the builder caught the mentor twice in
one hour — an escort that arrived after the work it was meant to precede, and a
msg-1/msg-2 sequencing contradiction about what gated what — and both were owned in-room
with the builder's reading named as the correct one. That is the record the owner should
be able to find, and it is why this skill exists as a skill instead of a habit.

## What the script owns, and what only you can

`mentor.py` owns the bookkeeping so your tokens go to judgment:

| command | what it does | exit |
|---|---|---|
| `charter --room <r> [--mentor H] [--builder B] [--engine P] [--note T]` | creates the room through `room.py`, posts the charter from the template | 0 (an existing charter is reported, never replaced) · 5 refused by the secret screen |
| `escort --room <r> --engine <p> [--hold "why"] [--out -\|PATH]` | prints the filled escort, engine read live | 0 · 2 no such engine |
| `checkpoints --room <r> [--json]` | the checkpoint ledger: n, poster, what, evidence, NEEDS, and who gated it | 0 all clear · **3 something is waiting on you** |
| `status --room <r>` | one line: checkpoints, ungated, last activity, open owner escalations | 0 |

Four parsing rules, so the output can be trusted: a checkpoint is **GATED** by a LATER
post from the mentor handle that names it and carries a gate mark — a mentor naming "CP5"
before CP5 exists is talking about the future, not gating it; the **NEEDS declaration** is
the pipe-anchored `| NEEDS: <state>` at the end of the line, never a mid-body mention of
the word; **UNGATED** means ungated AND owing (a `NEEDS: nothing` post is the builder
informing you and proceeding, so it is listed as UNGATED-INFO and never counted, which is
what keeps exit 3 meaningful for a pulse); an **owner escalation is open while it is
ungated**, because gating is the only closure a parser can see — it never infers
resolution from prose.

What no script can do: read the builder's code, judge whether the evidence supports the
claim, decide which law applies, or notice that the builder is right and you were wrong.
That is the seat's whole job.

## When NOT to use this

- **A single task that ends** → `agentswarm`. A lane is commissioned, works, returns and
  is done; it does not get chartered, escorted or taught. If you find yourself dispatching
  rather than teaching, you wanted a lane.
- **A metered multi-session dev arrangement with blackboard files** → `fable-director`.
  That runs flat dev/QC sessions on a token budget; this is two peers, one of whom is
  learning the estate.
- **A one-off question** → just answer it. Chartering a room to answer "which port?" is
  ceremony, and ceremony is how a good protocol gets ignored.
- **Work you should be doing yourself** → do it. Mentoring is not a way to launder your
  own scope onto someone else's session; if the builder's reply would just be your own
  plan typed back, you did not need a builder.

## The worked example — the rig arrangement (2026-07-27)

The ritual was run before it was written: a mentor session in this engine and a builder
session standing up `rig.rest`. Charter posted to a chatroom room; escort sent with the
engine inventory and a HOLD while a spec was pending; the builder replied with its cwd
state, four surfaced conflicts and a four-question batch; rulings R1-R4 answered them
(fresh repo, scaffold approved, port range, auth tripwire); checkpoints CP1-CP5 landed
with exit-coded evidence, each gated in-room with riders; one item — an expired login —
went up to the owner with the single action they had to take. Decision record **F-12** in
`archive/findings.jsonl` carries the definition, and the room carries the proof.

Running `checkpoints` against that live room is also the honest test of this parser: it
reports CP1 as the one checkpoint still ungated, because its rulings were sent over the
session line and never posted to the room. That is a real gap in a real arrangement, found
by counting rather than by remembering — which is the entire argument for the room.

## Self-check before finishing (any mentor turn)

- Every checkpoint that owes a gate has one: `mentor.py checkpoints --room <r>` exits 0,
  or you can say in one line which one is still waiting and why.
- Every ruling you issued names the law or the record that decided it, and every gate that
  imposed a condition said the word RIDER — a condition the builder has to infer is a
  condition you did not set.
- Anything you got wrong is corrected IN THE ROOM, not in a transcript, in the message
  that answers it, with the builder's reading named where it was the correct one.
- Owner-grade items went up with ONE action and your recommendation; nothing else did.
- Nothing that matters lives only in a session: decisions are in the estate's records
  (findings store, COORD line — append-only, through the scripts that own them) and cited
  in the room by path.
- Any lane either of you spawned named `model: "opus"` explicitly; forks stay banned —
  never `subagent_type: "fork"`, which silently inherits the seat's model.

## Finishing up

Chains: `/chatroom` is the wire this rides on (`room.py join` keeps you awake to the
room); `/archivist` holds the decision records a ruling cites; `/decider` structures an
owner-grade choice before you escalate it; `/recap` and `/sessionend` carry the
arrangement across a session boundary — a mentor seat that ends without a handoff leaves
a builder talking to an empty room. The cockpit's chatroom panel is where the owner
watches all of it, which is the reason the room is the record and the traffic is not.
