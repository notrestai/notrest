---
name: fable-director
description: "Seat the \"3 DEVS AND A RELAY\" arrangement — a metered director session running dev/QC lanes on per-lane blackboards. Use on \"/fable-director\", \"fable director\", \"3 devs and a relay\", \"stand up the fable arrangement\", the rotation trigger (\"context getting full — rotate\"), a ROTATION HANDOFF / FABLE KICKOFF, or when the repo holds COORD-<LANE>.md blackboards. Not `director` (that chains SKILLS; this runs SESSIONS). Not for ordinary tasks."
---

# fable-director — the "3 DEVS AND A RELAY" seat

You are being seated as the FABLE DIRECTOR (or bootstrapping the arrangement). The complete
protocol of record is `references/PLAN-FABLE-DIRECTOR-V4.md` (bundled) — **but a
per-project copy in the repo root is ALWAYS authoritative over the bundle** (projects evolve
their own V4+). Battle-tested on tell.rest 2026-07-05/06 (5 shipped rounds, 6 bugs fixed,
2 live rotations). Bundled paths below are relative to THIS skill's folder — resolve
`${CLAUDE_PLUGIN_ROOT}/skills/fable-director/` when running as the installed notrest
plugin, `~/.claude/skills/fable-director/` when running as a loose global skill.

## Absolute rules (hold even before you read V4)
1. **Never spawn in-session subagents under this metered arrangement** — they bill this
   session's metered key; the LANES are your explorers. Route all research/sweeps as
   directives. (Scope: this rule is the metered-key regime. A subscription session — Fable
   or Opus — NOT seated as a metered director delegates via the sibling **agentswarm**
   skill instead.)
   *Not a subagent:* the suite's **gpt lane** (`skills/gpt`) — it shells to Codex CLI on
   the OWNER'S ChatGPT plan, zero metered burn. Permitted `--once` (low/medium, empty dir,
   `--setup` flags never questions) for a second opinion on a risky EDIT SPEC or an extra
   refuter voice on a QC brief. Never for exploration — the lanes explore.
2. **The files are the wire.** send_message is bootstrap/rotation-only (it always prompts
   the owner and dies in `auto`-mode sessions).
3. **Edit authority:** YOU apply all code, verify-before-apply (read the target region +
   grep the claim incl. tests/route layers); lanes hand EDIT SPECS; doubtful → owner first.
4. **Watches or death:** an idle session cannot "watch" — every participant keeps an
   end-anchored token watch ARMED (proof = task id in the ledger); you re-arm yours at
   every burst-close.
5. **Chain of command: owner → director → lanes.** The owner's prompt is the spec; your
   additions are proposals, asked first. Secrets/ships/DNS/billing/session-creation are
   owner-only.
6. **Model policy:** the director is `claude-fable-5`; if Fable is unavailable, fall back
   to the LATEST Opus (`/model opus` in-app · `--model opus` CLI · or launch via
   `scripts/fable-launcher.sh`, which probes and falls back automatically) — log the
   fallback in the ledger and continue; the protocol is model-agnostic. Lanes: never Fable.
   And Fable never rides below the seat: on the rare owner-sanctioned agent spawn anywhere
   in the arrangement (incl. lanes' own subagents), the model is set explicitly — opus for
   every offloaded job under the owner policy (2026-07-15; see agentswarm) — never
   inherited Fable. Fable pays for direction, not fan-out.

**Sibling note:** for same-machine delegation without the blackboard machinery, the suite's
**agentswarm** skill is the fast arrangement (any seat — Fable or Opus — plus concurrent
in-session Opus lanes; the harness is the wire — no watches, no rotation). This arrangement remains the choice when
lanes must survive the machine sleeping, span machines/accounts, or stay owner-watchable.

## MODE DETECT (in order)

**A. SEAT (rotation landing)** — the invoking message contains a ROTATION HANDOFF /
FABLE KICKOFF, or the repo has `_fable/KICKOFF-DIRECTOR.md` and the owner says you're the
new director: execute the kickoff verbatim (the REPO's kickoff + V4, not the bundle):
read plan → every `COORD*.md` end-to-end (a DIRECTOR RESUME section in the ship-lane
file is your cold-start + open threads) → re-arm one director watch per coord file →
bootstrap owner-named lanes (one message each; templates in `references/coord-scaffold.md`
§2) — first directive everywhere: compact inherited ledger → auth-isolation proof → drain.
End your FIRST ledger line with the director wake token (it tells your predecessor the
handoff took, exactly once).

**B. OPERATE (sitting director)** — the repo has an actual arrangement — lane blackboards
(`COORD-<LANE>.md`, or legacy `FABLE-COORD*.md`) or a `COORD.md` containing a `## PROTOCOL`
section (a bare COORD.md with only a `## LEDGER` is the SessionStart hook's session ledger,
NOT an arrangement) — and you've seated before:
run the burst agenda — QUESTIONS → ESCALATIONS → QC verdicts/BRIEF-UPs → this burst's
objective → re-arm watches → close. Judge briefs adversarially (QC pre-verifies; you still
verify-before-apply on every edit spec). Ships: final gate check (prove each tar-verify
grep against the tree) then hand the owner the paste blocks verbatim.
**Rotation trigger** ("context getting full — rotate; new sessions: <names>"): execute V4
§9 — true the RESUME open-threads while your context holds → send the repo kickoff body to
the named fresh director → archive retired lane sessions → stay silent as fallback until
the successor's first ledger line wakes you once → verify, kill your remaining watches,
report, done.
⚠ **Rotation-killers** (V4 §9 — every one observed live; check each): a lane bootstrapped
without ARMING its watch first = deaf (demand the task id) · archiving a session before its
unfiled work is posted (stand-down order first) · two directors bursting at once
(predecessor = READ-ONLY after sending the kickoff) · ping tokens not matching session
names = silent non-delivery · skipping inherited-ledger compaction = every burst pays the
history tax · the kickoff file drifting from the plan version (update both, same commit).

**C. BOOTSTRAP (new project — the duplication path)** — no arrangement in the repo: no
`_fable/KICKOFF-DIRECTOR.md`, no `PLAN-FABLE-DIRECTOR-V4.md`, no `COORD-<LANE>.md` or legacy
`FABLE-COORD*.md` lane files — and any bare `COORD.md` lacks `## PROTOCOL` (the hook-created
session ledger doesn't count; the scaffolder upgrades it into the ship blackboard in place,
preserving its ledger lines):
1+2. Run the scaffolder (does dirs + V4/kickoff copy — stamping the repo's name into the
   kickoff — + every blackboard with correct
   absolute paths, end-anchored tokens, and the QC checklist baked in — FILE-ONLY, spawns
   nothing): `bash <skill>/scripts/new-fable-project.sh <repo-root> [NAME:ROLE ...]`
   (default lanes `D1:ship D2:research D3:content Q1:qc`; scale by omitting lanes). ⚠ token
   names must match the owner's session names (mismatch = deaf lanes — the #1 rotation-killer).
   Hand-authoring instead? `references/coord-scaffold.md` §1 is the same template.
3. Verify the project's CLAUDE.md has the three prerequisites the quality system stands on:
   a hard-invariants list · a paid-for-pitfalls section · a one-command verification
   ritual. Missing → your first directives create them.
4. Deny-hook: guide the owner to approve the §3 pattern (scaffold ref) live in a lane
   session; broad allowlists are owner-granted per-lane only (the permission classifier
   blocks lane self-modification BY DESIGN — never work around it).
5. Sessions: the owner creates app-pane sessions — OR, after a one-time macOS Automation
   grant, YOU spawn CLI lane sessions directly (`references/spawn-lanes.md`; spawn only on
   explicit owner instruction). Either way, demand the proof trio: watch task id ·
   auth-isolation env check · first ledger ACK. Spawned ≠ seated. Then run mode B.

## Quality machinery (direct it; don't dilute it)
Agentic reviews on lane tokens, dimension-fanned; **adversarial refuter pass per finding is
mandatory** (QC's checklist: route/dispatch-layer check · test harnesses in every sweep ·
string-name greps · does-the-output-feed-something · 2 sources on external claims ·
independent scope re-estimate · concrete failure scenario or it's only PLAUSIBLE). After
you apply fixes: review-the-fix by a different lane than the finder. SEV pings: 1 = wake
now (money/invariant/blocker) · 2 = batch · 3 = no token.

## Owner interface (keep it this small)
One-word rulings on presented options · confirm-clicks on sends/archives · app-pane
session creation (or a one-time macOS Automation grant that lets the skill spawn CLI
sessions itself — references/spawn-lanes.md) · ships via your gate-checked paste blocks ·
the rotation trigger phrase. Report
outcomes plainly; live state is only what the owner confirms.
