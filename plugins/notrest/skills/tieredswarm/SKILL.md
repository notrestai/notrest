---
name: tieredswarm
description: "The three-layer delegation shape — seat, opus lanes, sonnet workers — and the MEASURED routing gate that says when to use it: script it if compilable, flat solo opus by default, tier only for context overflow or wide parallel reads. Use on /tieredswarm, 'tiered swarm', 'sonnet workers', '3-layer', 'should I tier this', 'is tiering worth it'."
---

# tieredswarm — the three-layer shape, and the gate that admits it

This skill exists because the pattern was **benchmarked and mostly lost**. Four rounds on
2026-09-01 measured tiering against a flat solo lane on the same task, and the honest
result is a narrow admission rule rather than a recommendation. The shape is documented
here so it can be run correctly *when it is chosen* — and the gate is documented first so
it is usually not chosen.

`agentswarm` is the delegation arrangement (seat keeps decompose/judge/apply/gate). This
skill is one *topology* inside it, plus the evidence for when that topology pays.

## The routing gate — read this before tiering anything

Apply in order. The first rule that fires decides; do not skip to the shape.

1. **Script it if it is compilable.** If the reading can be done by `grep`/`awk`/a 30-line
   Python scan, the material never enters model context at all and every topology loses to
   the script. Round A proved this the expensive way. This is the `compile` thesis, and it
   is the single largest saving on the board.
2. **Flat solo opus by default.** For judgment work that fits in one lane's context, one
   opus lane, reading directly, is the measured winner — ~40% cheaper than the best tiered
   arm *and* deeper. Default means default: tiering needs a reason stated out loud.
3. **Tier only for (a) payloads that exceed one lane's context, or (b) wide parallelism
   with a lean fan-in.** Both of these are `[unmeasured]` — they are the regimes the
   pattern was born in and neither has been benchmarked. Say `[unmeasured]` when you
   invoke this rule; it is an argument, not a receipt.
4. **Sonnet workers only under a declared mechanical/DRAFT tier.** The dispatching text
   must carry that declaration verbatim, per the owner's 2026-08-30 amendment. Round B is
   why: sonnet workers on judgment material were dominated on **both** axes — more tokens
   *and* flatter output. Absent the declaration, workers are opus.
5. **Merging is judgment, so the merger stays opus.** The lane merges its own workers; the
   seat merges the lanes. A cheap merger is how a tiered run loses the quality it paid for.
6. **Depth stops at three.** A worker does not spawn. If a worker needs a worker, the
   decomposition was wrong one layer up — redraw the domains.
7. **Digest, never verdict — at BOTH merge points.** The lane compresses its workers
   without deciding for the seat; the seat's synthesis compresses without deciding for the
   owner. A verdict rendered two layers down is an oracle nobody can cross-examine.
8. **Depth-2 receipts are estimate-grade.** A nested worker receipts with `tokens=unknown`,
   so a `/spend` roll-up over a tiered run UNDER-COUNTS layer 3 rather than missing it.
   Enforcement is exact; accounting at depth 2 is lossy. Docket item 7, open — disclose it
   whenever you quote the cost of a tiered run.

## What was measured — the four-round matrix

One identical task each round: 31 skill files. Round A's deliverable was mechanical
extraction; rounds B/C/D's was per-skill judgment (core law, strongest guarantee, weakest
admitted limit, internal tension with a backing quote) — unscriptable by construction, so
the material had to transit model context in every arm.

| round | arm | tokens | wall | quality |
|---|---|---|---|---|
| **A** | **FLAT solo opus** (mechanical) | **60,832** | **70s** | won — it *scripted* the extraction |
| A | tiered, sonnet workers | 270,186 | 216s | 4.4x tokens, 3.1x wall — lost |
| **B** | **FLAT solo opus** (judgment) | **291,645** | 312s | **deepest table of the four** |
| B | tiered, sonnet workers | 502,687 | 278s | accurate but flattest — dominated |
| C | tiered, 3 fixed opus workers | 482,752 | 287s | deep — quality recovers |
| D | tiered, opus workers, self-routed | 469,917 | 222s | deep — same marquee catches as flat |

Read it in that order and the laws above fall out:

- **A → law 1.** The flat arm won by *not being a model problem*. The gap was not opus vs
  sonnet; it was context vs `grep`. Each worker also carries ~20k of fixed harness
  overhead that a small payload cannot amortize.
- **B → laws 2 and 4.** The pre-registered hypothesis (tiering wins on judgment) **lost**,
  under its own stated losing condition. Sonnet spent ~14k/file against opus's ~9k/file on
  judgment material, and the no-re-read merge caps output quality at worker level.
- **C and D → law 4's other half.** With opus workers, depth comes back: C and D agree
  within 3%, so opus-tiered is replicated, not a fluke. The B loss was the **worker model**,
  not the topology — the confound was called before the rounds ran. The remaining ~1.6x
  premium is the topology itself: three boots plus a merge that cannot re-read.
- **D → law 4's teeth.** D's orchestrator was given free choice of worker models under the
  standing tier rule. It routed **all three workers to opus**, refused the tempting
  sonnet-on-the-shortest-batch split, and wrote that the tier rule *"genuinely constrained
  me — I could not have written the mechanical declaration honestly."* The wording holds
  under an invitation to bend it.

What is **not** claimed: that tiering wins anywhere. The two regimes law 3 admits were
never measured, and the earlier operator-reported gain remains `[operator-reported]` and
unquantified — a different regime, un-contradicted rather than confirmed.

## The shape — when the gate admits it

Three layers, each absorbing the flood for the layer above.

1. **The seat** (Fable or Opus) — decomposes into domains, dispatches ONE lane per domain,
   judges what returns, applies every edit, gates every ship. Never rides below itself.
2. **The lane** — owns its domain and may fan its mechanical breadth out to parallel
   workers for reads, sweeps and extractions. It merges its workers' raw returns itself
   (law 5). Claude lanes run `opus`; Codex lanes run `gpt-5.6-sol`, and
   never `subagent_type: "fork"` — forks inherit the seat's model and launder the policy.
3. **The workers** — bounded and mechanical, returning raw material and never conclusions.
   They are opus unless the dispatching text declares the mechanical/DRAFT tier, in which
   case `model: "sonnet"` is lawful (owner amendment 2026-08-30). `haiku` is never lawful
   at any depth, and no negation makes a fork lawful.

**The gate holds at depth 2.** Spawn-gate is a PreToolUse hook on `Agent|Task`, so a lane's
own spawns pass the same door the seat's do — live-proven 2026-09-01: an unlawful
model-omitted nested spawn was refused verbatim at the door, while a lawful declared-tier
worker ran, returned, and auto-receipted with its model recorded.

## Honest limits

- Laws 1, 2, 4, 5 and 6 are `[cited]` to the four rounds above. Law 3 is `[unmeasured]`.
- All four rounds ran one task family on one estate on one day. A different corpus could
  move the constants; it is unlikely to reverse a 1.7x with a quality win attached.
- Seat-side cost is invisible to the ledger by the estate's own spend law, and each lane
  return costs the seat ~9-11k tokens `[estimate]` that re-send thereafter — symmetric
  across topologies, so no round was skewed, but absent from every figure above.

## Self-check before finishing

- [ ] Did I apply the gate **in order**, and name the rule that fired?
- [ ] If I tiered: is the reason law 3, and did I label it `[unmeasured]`?
- [ ] If any worker is sonnet: does the dispatching text carry the mechanical/DRAFT tier
      declaration verbatim, and is the material genuinely mechanical?
- [ ] Is every merge point a digest, with the verdict left to the layer above?
- [ ] Depth ≤ 3, no worker spawning a worker?
- [ ] If I quoted a tiered run's cost: did I disclose the depth-2 estimate-grade limit?
- [ ] Did I avoid claiming a measured win for a regime the matrix never covered?

## Finishing up — chains

- **`/agentswarm`** — the arrangement this topology lives inside; go there for the seat
  contract, lane discipline, trail-walk and speed rules.
- **`/compile`** — where law 1 sends you: repeated mechanical work becomes a script.
- **`/spend`** — the receipts, with the depth-2 caveat of law 8 attached.
- **`/decider`** — when the tier-or-flat call is contested rather than gated.
- **`/refuter`** — before any change to the gate itself: this doctrine has already
  overstated the pattern once, and was amended by measurement rather than by argument.

Bank the routing decision on the COORD line that carries the work: which rule fired, and
what it cost. The matrix above exists because somebody wrote the numbers down.
