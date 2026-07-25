---
name: director
description: Chain other ORACLE skills into a pipeline — parse the ordered skill list + seed input, run every stage for real (reading each skill's SKILL.md from disk; isolated subagent per stage where available), hand each stage's output to the next, and produce a numbered run folder + pipeline summary (or --quick). Use on /director or asks to run skills in sequence, chain, pipeline, or "do X then Y then Z" (e.g. "research this, critique it, then plan it"). For orchestrating SESSIONS instead, see fable-director.
---

# Director

A conductor for the other skills. Given an ordered list of skills and a starting prompt, it runs them one after another and chains them: the output of each stage becomes the input to the next, until the sequence finishes. You are the executor — there is no API that "calls" a skill; you run each skill by reading its `SKILL.md` and performing its workflow yourself, in order.

The cardinal rule: **actually run every stage.** The failure mode of an orchestrator is pretending a stage ran and inventing its output. Never summarize or hand-wave a sub-skill — read its file and do its full workflow, producing its real files, before moving on.

## The prompt

The prompt names (a) the **ordered sequence of skills** to run and (b) the **seed input** for the first one. Use `$ARGUMENTS` if populated; otherwise the text after `/director`. Accept natural phrasings and separators — "researcher then stepbystep", "marketresearcher → critic → stepbystep", "run A, B, C on …". Parse out the skill list and the topic. If you can't tell which skills are meant, or the seed topic is missing, ask one clarifying question, then proceed.

## Locating the skills

Resolve each named skill's `SKILL.md` by checking these locations **in order**, and read the first that exists:
1. **`${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md`** — when this suite runs as an **installed plugin** (`notrest`), the director and its siblings ship together here. `CLAUDE_PLUGIN_ROOT` is set by Claude Code for plugin code; expand it and look here FIRST. (If your shell doesn't expose it, the plugin's skills sit alongside this `director/` folder — i.e. `../<name>/SKILL.md` relative to this file.)
2. **`.claude/skills/<name>/SKILL.md`** — a project-level skill.
3. **`~/.claude/skills/<name>/SKILL.md`** — a global/user skill.

For every skill in the sequence, read its `SKILL.md` before the run. If a named skill can't be found in any of those locations, **stop and report it** — list the skills you did find and ask how to proceed. Don't substitute a different skill or invent the missing one's behavior.

> **How the director runs a skill (important):** it **reads the skill's `SKILL.md` from disk and performs that workflow** — it must **never** invoke a sub-skill via the Skill tool, even though the sub-skills are individually invocable. Two reasons, both structural: a nested Skill invocation dumps the sub-skill's full contract into the director's own context (defeating stage isolation), and it detaches the stage from the pipeline's file/checklist discipline. File-read-and-follow is the only mechanism that keeps stages isolated, resumable, and auditable.

## Quick mode (`--quick`)
If the invocation includes `--quick` (or "quick" / "brief" / "no files"), run the chain lightweight:
- **No files.** Write nothing to disk — skip the pipeline folder, the per-stage files, the background, and the dossier.
- **Run each stage in quick mode too**, carrying each stage's short summary forward **in-context** as the handoff (instead of via files).
- **Output in chat only:** the plain-language **What Happened** recap (per stage: what it found, what it changed) and the final result summary. No references.
- Because everything stays in context, this suits **short chains**; for long chains use the normal file-backed mode.
- End with one line: *"Quick read — not sourced or saved; run without `--quick` for the full file-backed pipeline."*

## Setup & output files

Derive a `{topic}` slug from the seed prompt. Create a `pipeline/` directory containing:

- **`pipeline/{topic}background.md`** — the orchestration log (parsed chain, validation, the handoff decisions per step, any deviations or failures).
- **`pipeline/{topic}Dossier.md`** — the consolidated pipeline summary (the main read).
- **`pipeline/NN-<skill>/`** — one numbered subfolder per stage (`01-researcher/`, `02-critic/`, …). Run each sub-skill normally but write its two output files **into its numbered subfolder** instead of the skill's own default directory, so the whole run lives in one place.

If `pipeline/` already exists from a prior run, suffix the topic with `-2` (then `-3`, etc.).

## Honesty & integrity rules (apply throughout)

- **Run every stage for real.** No fabricated or skipped stages. Each sub-skill's full workflow and its own rules (honesty labels, confidence scoring, caps, self-checks) are executed in full — the director never shortcuts them.
- **The handoff must be genuine.** Stage N+1's input is the actual designated output of stage N — not your memory of it, not a paraphrase you wish it said. Re-read the produced file when handing off.
- **Surface failures, don't paper over them.** If a stage fails, produces something too thin to chain, or a skill is missing, stop and report it rather than improvising a fake result to keep the pipeline moving.
- **Preserve labels and confidence across the chain.** The final result inherits the confidence and caveats of the last stage; don't launder a low-confidence finding into a confident one by passing it through more skills.
- **Read from disk, never invoke as a tool.** Locate and read each sub-skill's `SKILL.md` with file tools and follow it. Never call the Skill tool for a sub-skill — a nested invocation floods the director's context and breaks the stage isolation and on-disk checklist this design depends on.
- **Isolate each stage so context can't run out.** A chain stacked into one conversation exhausts the context window, and the deepest (last) stages get dropped or "forgotten" — the classic "it skipped the last skill" failure. Run each stage in its own context (Phase 3). The director thread stays light — chain, handoffs, checklist — and never carries a stage's full working.

## The phases

### Phase 1 — Parse & plan the pipeline → `{topic}background.md`
**First, resume or start.** Check whether a `pipeline/` for this topic already exists with a partly-ticked checklist — from an earlier turn in this conversation, or a fresh conversation where the user re-uploaded the pipeline files. If it does, **resume**: read the checklist, find the first unticked stage, and continue from there using the prior stage's dossier on disk. Do **not** restart or redo completed stages. Only if there's no existing run, plan it fresh:
- **Sequence:** the ordered list of skills.
- **Seed input:** the topic/prompt that feeds stage 1.
- **Resolve everything up front:** locate and confirm **every** skill in the sequence exists — read each `SKILL.md`'s path *before running any stage*. If one is missing, stop and report it now; don't discover it mid-run.
- **Pin the chain to disk:** write the ordered sequence and a completion checklist (`[ ] 01-<skill>`, `[ ] 02-<skill>`, … `[ ] NN-<skill>`) into `{topic}background.md` as the very first thing. This file — not your fading memory of the prompt — is the source of truth you re-read before each stage, and it's what makes the run resumable.
- **Handoff plan:** for each adjacent pair, state *what* output of stage N feeds stage N+1, and *how* it maps to stage N+1's expected input. Read the receiving skill's own "prompt/input" section and frame the handoff to match it. For example: a `researcher` Dossier handed to `stepbystep` becomes the goal "build/implement the recommendation in this dossier," with the dossier as the attached document; a dossier handed to `critic` becomes "critique this document."
- **Sanity note:** if an ordering's handoff is unclear or weak (e.g. a skill that produces no document feeding one that needs one), flag it now.

### Phase 2 — Go (run autonomously, no confirmation)
**Do not ask the user to confirm, and do not pause for permission.** Once invoked, run the chain straight through to the end. Never stop merely to check in, to summarize-and-wait, or to ask "continue?". The *only* thing that may ever justify a question is a genuinely unparseable request — you truly cannot tell which skills to run or what the seed input is — and even then, strongly prefer to proceed on a clearly-stated assumption rather than stop. If you can determine the chain and the seed (you usually can — explicit `/skill` names and the documents/prompt in context are enough), just go.

### Phase 3 — Execute the chain (one isolated stage at a time)
**The director runs in the main thread and stays light.** Before each stage, **re-read the pinned chain and checklist** from `{topic}background.md` and **re-read that stage's `SKILL.md` from disk** — never run a stage from what you remember earlier in the conversation. Then execute it:

**Preferred — isolated subagent per stage** (use whenever subagents / the Task tool are available, e.g. Claude Code or Cowork). Spawn a subagent for the stage and hand it exactly three things: (a) the path to the stage's `SKILL.md`; (b) the input — the seed prompt for stage 1, or the prior stage's output **file path** for later stages, framed per the Phase-1 handoff plan; (c) the output path `pipeline/NN-<skill>/`. Instruct it to read the skill file, perform the full workflow, write its two files there, and return **only** its dossier path plus a ~3-line summary. **Stage subagents carry an explicit model — never an inherited Fable** (HARD RULE when the director session runs on `claude-fable-5`, where an unset model silently bills Fable credit): **opus** for every stage (owner offload policy 2026-07-15 — no sonnet, no haiku, and never `subagent_type: "fork"`, which ignores the model parameter and inherits the parent). The director seat may be Fable; its stages never are. The heavy work (searches, passes, drafts) happens in the subagent's fresh context; the director's context barely grows, so it cannot run out before the final stage. The director must not itself be forked — a fork can't spawn forks, so director stays in the main thread and spawns the stages.

**Fallback for claude.ai (no subagents) — run continuously, checkpoint to disk, auto-resume.** You can't isolate context here, so externalize aggressively and run straight through *without pausing*:
- **Externalize as you go.** Each stage writes its full working (searches, passes, drafts) to its background file immediately; only a dossier path + ~3-line summary stays in the conversation. Prior stages' heavy content must not re-enter context — re-read a file only when you actually need it. This is what lets the run get as far as possible before any context limit.
- **Run every stage back-to-back. Do not stop to ask "continue?"** — autonomy means no voluntary pauses, no check-ins, no waiting.
- **Checkpoint each stage durably.** As each stage finishes, write its two files and tick its checklist box on disk. This means the *only* thing that can interrupt the run is claude.ai's hard context-window limit (which no skill can remove) — never a choice you made.
- **If the platform does cut a turn off mid-chain, resume is automatic and silent.** The Phase-1 resume check reads the checklist and continues from the next unticked stage, asking nothing and redoing nothing. The user just lets it keep going; never re-ask anything you already determined.
- **A single stage too heavy for one turn** (e.g. a high-cap `stepbystep`) may itself be truncated by the window — staging can't shrink one oversized stage. If that's a risk, quietly lower that skill's cap for the run; don't pause to ask. For a hard guarantee on very long chains, the answer is Claude Code's subagent isolation, not a different claude.ai trick.

After each stage, in either mode: **tick its box** in the on-disk checklist and log the handoff (what came in, what went out, which file carries forward). When the suite's **spend** skill is present, also append one ledger line per stage subagent (its model + observed tokens, `--lane subagent`) so the pipeline ends with a checkable routing verdict. Honor each sub-skill's internal caps (e.g. `stepbystep`'s iteration cap). **Do not declare the run finished until every checklist box is ticked** — an empty last box means the last stage never ran, which is the exact failure this design exists to prevent.

### Phase 4 — Consolidate → `{topic}Dossier.md`
Write the pipeline summary (below) once the chain is done. This includes the plain-language **What Happened** recap: for each stage, what it found and what it *changed*, then what the whole run achieved — written so a non-expert understands the journey from that section alone.

## The dossier — `pipeline/{topic}Dossier.md`

The single read that explains the whole run. **Read Me First up top, then the chain, then the final result.**

```markdown
# <Seed topic> — Pipeline Summary

## 📌 Read Me First
Plain-language, 3–5 bullets, skimmable in 20 seconds.
- **What ran:** <skill A → skill B → skill C> on <topic>.
- **The end result:** <the final output in one plain sentence>.
- **How sure to be:** <inherited from the final stage, in plain words>.
- **The catch:** <the biggest caveat carried through the chain>.

**Where everything lives:**
- **`{topic}background.md`** — the orchestration log (how the chain was planned and how outputs were handed off).
- **`NN-<skill>/`** — each stage's own two files (its background + dossier).
- **`{topic}Dossier.md`** (this file) — the summary tying it together.

---

## The Pipeline
Ordered stages, with the handoff shown between each.
1. **<skill>** — input: <seed/what came in> → output: <what it produced> → `01-<skill>/`
   ↓ handoff: <the specific artifact passed forward>
2. **<skill>** — input: <from stage 1> → output: <…> → `02-<skill>/`
   ↓ handoff: <…>
3. ...

## Final Result
<The end-of-chain output, summarized — what the user actually came for — carrying the final stage's confidence and caveats.>

## What Happened — In Plain Language
A jargon-free recap of the run: what each stage found, what that changed, and what it all achieved. A reader should get the whole journey from this section alone.
- **Stage 1 — <skill>:** <what it found, plainly>. This established <the starting picture>.
- **Stage 2 — <skill>:** <what it found>. **What changed:** <how this moved things from the last stage — e.g. ruled an option out, exposed a risk, turned an idea into a concrete plan>.
- **Stage 3 — <skill>:** <what it found>. **What changed:** <…>.
- **What it achieved:** <the net result in 1–2 plain sentences — what you can do now that you couldn't before the run, and how much to trust it>.

## Stage Index
- Stage 1 — <skill>: `01-<skill>/{topic}Dossier.md` (+ background)
- Stage 2 — <skill>: `02-<skill>/{topic}Dossier.md` (+ background)
- ...

## Notes & caveats
- <any stage that was thin, any deviation from the plan, any failure handled>
```

### Example — what a good run looks like
*(Illustrative: `/director marketresearcher → critic → stepbystep: a SaaS scheduling tool for independent dentists`.)*

> 1. **marketresearcher** — input: the idea → output: opportunity dossier; best opening = "automated insurance pre-auth for sub-5-chair practices." → `01-marketresearcher/`
>    ↓ handoff: the opportunity dossier, passed to critic as "critique this opportunity."
> 2. **critic** — input: stage-1 dossier → output: verdict = 🟠 serious (willingness-to-pay unproven), surviving form = "validate with 10 design partners before building." → `02-critic/`
>    ↓ handoff: dossier + critique, passed to stepbystep as the goal "plan the validation-then-build for the surviving opportunity," with both docs attached.
> 3. **stepbystep** — input: stages 1–2 → output: a converged action plan starting with the design-partner validation. → `03-stepbystep/`
>
> Final result inherits stepbystep's confidence (Medium) and the critic's unresolved willingness-to-pay risk — not laundered into false certainty.
>
> *What Happened (plain language):* **marketresearcher** found the sharpest unmet need was insurance pre-auth for tiny practices. **critic** then changed the picture — it showed customers' willingness to pay wasn't proven, so "build it" became "validate with 10 design partners first." **stepbystep** turned that into a concrete, ordered plan beginning with the validation. *Achieved:* you now have a de-risked, step-ordered plan to test the idea before spending on a build — with the open question (will they pay?) flagged, not hidden.

## Self-check before finishing
Before declaring done, verify and fix any miss:
- Every named skill was found and **actually executed** in full — no stage faked or summarized in place of running it.
- Each stage's input was the real, designated output of the prior stage, framed for the receiving skill.
- Each sub-skill's own workflow, honesty rules, and self-check were followed (not shortcut by the director).
- Outputs are in numbered subfolders with a pipeline summary that links every stage.
- The final result preserves the last stage's confidence/caveats — nothing was laundered into false certainty.
- Any missing skill, failed stage, or weak handoff was reported, not papered over.
- The plain-language **What Happened** recap is present and, for each stage, says what it found and what it changed — jargon-free — ending with what the run achieved.
- **Every checklist box is ticked — the last stage actually ran** (the failure mode to guard against); nothing was skipped because context filled.
- No stage was invoked via the Skill tool; each was located and read from disk, then performed.
- Stages ran in isolated subagents where available; where inline, each stage's working was offloaded to its background file to protect the director's context.
- Every stage subagent was spawned with an explicit opus model (never a fork) — none inherited a Fable director's model.

## Finishing up

Write `{topic}background.md` as you go (logging each handoff), and `{topic}Dossier.md` at the end. Then give the user a short chat summary built from the **What Happened** recap: in plain language, what each stage found and what it changed, then what the whole run achieved — plus the final inherited confidence and the path to the pipeline folder (point them to `{topic}Dossier.md`). Don't paste the files into chat. Offer to re-run the chain with a different sequence, or to expand any single stage.

## Notes on tone and rigor

- The director's value is faithful orchestration, not new analysis — its job is to run the others correctly and chain them honestly, then get out of the way.
- A chain is only as trustworthy as its weakest stage; carry that stage's uncertainty all the way to the final result.
- Good default chains: `researcher → critic` (find an answer, then red-team it); `marketresearcher → critic → stepbystep` (opportunity → stress-test → plan); `stepbystep → critic` (plan, then attack the plan); `researcher → factcheck` (research, then verify the load-bearing claims); `researcher → decider` (gather evidence, then structure the choice); `stepbystep → actionplan` (plan, then make it copy-paste).
- It runs autonomously — no confirmations, no check-ins, no "continue?" prompts. In Claude Code it finishes the whole chain in one pass via subagent isolation; in claude.ai it runs continuously and, if the platform's context limit ever cuts a turn off, resumes silently from the on-disk checklist. The only honest limit is that very long chains may not fit one claude.ai turn — that's a platform ceiling, not a reason to start asking the user questions.
