---
name: eval
description: "The harness's law-conformance suite — one static pass over the shipped files asking whether every law left a fingerprint: offload policy, honesty labels, scripts that compile, append-only ledgers, the worker contract, front-matter YAML accepts, safety laws, silent-on-failure hooks, the routing law's enforcer. Use on \"/eval\", \"check the laws\", \"conformance check\", \"does the harness obey its own rules\", or before any release. Zero model tokens, seconds, exits 0/5/6. doctor checks the INSTALL; eval checks the LAWS."
---

# eval — does the harness obey its own laws?

```bash
python3 plugins/notrest/skills/eval/scripts/eval.py check --root .
```

That is the whole ship gate. Add `--json` for machine output. Exit **0** all pass ·
**5** warnings only · **6** any FAIL · **2** usage.

## The doctrine: check the fingerprint, not the behavior

**A law that is well-encoded leaves a static fingerprint in the shipped text.** If the
offload policy is real, `model: "opus"` is written where spawns are written. If the
honesty grammar is real, the label vocabulary is in the skill that makes claims. If the
zero-token claim is real, a script exists and compiles. Those are facts about files, and
files can be read in 70 milliseconds for free.

The alternative was tried and killed. The external `claude plugin eval` runner spun a
**full agentic model session per case, per arm, per run**, plus LLM judges to grade the
transcripts: **~13 minutes per pass**, opaque to the seat (the failures arrived as
scores, not as file:line), and across **45 minutes of running it produced zero fixes**.
A grader that cannot name the line cannot be acted on. Deterministic-first,
model-last — the model is the *last* instrument you reach for, not the first.

Every check names the law it guards, cites the **file and line** it judged, and carries
a fix hint. A finding you cannot act on is a bug in this skill.

## The nine checks

| Check | The law |
|---|---|
| `OFFLOAD-POLICY` | every documented spawn of a Claude subagent names explicit **opus**; no sonnet/haiku directive; the fork ban is present wherever `subagent_type` is written; the SessionStart hook carries the rule |
| `HONESTY-LABELS` | every claim-making skill (researcher, factcheck, marketresearcher, explainer, decider, recap, watch, draft) defines or uses `[cited]/[recall]/[estimate]/[unverified]` or its documented verdict grammar |
| `SCRIPT-OWNS-SCANNING` | every cited scanner exists in the tree and `py_compile`s, and every shipped script is named by its SKILL.md — this is what backs "the scanner reads the files, the model never has to" |
| `ESTATE-WRITE` | anything that writes COORD, COORD-AGENTS or the spend ledger says **append-only** or routes through the owning script; a directive to hand-edit one is a FAIL |
| `WORKER-CONTRACT` | every worker skill ships a self-check section and a finishing-up/chains section (arrangement contracts — fable-mode, fable-director, oracle, agentswarm, game-forge — are exempt by construction) |
| `TRIGGER-SANITY` | front-matter `name` matches the directory; the description is a scalar YAML accepts (**an unquoted `": "` silently kills a skill while the file sits on disk**) and names at least one `/slash` trigger |
| `SAFETY-LAWS` | draft: *a draft is never sent*. watch: *a dead source is never a refutation*. compile: *never auto-install*. fable-director: the tombstone/metered-key scope |
| `HOOK-CONTRACT` | every hook is silent-on-failure — no `set -e`, always ends `exit 0` — and `hooks.json` references only files that exist |
| `ROUTER` | the routing law has an enforcer: `hooks/router.sh` is registered under **UserPromptSubmit**, `bash -n` accepts it, it is silent-on-failure, and every `/notrest:<skill>` its table can emit names a skill directory that exists |

A line that names sonnet, haiku or `fork` **alongside a negation** is the law being
stated, not a breach of it; the checker reads the line before judging it.

## What this is NOT

- **Not doctor.** doctor checks the **install and the estate** — manifest pins, version
  drift, gitignore that un-tracks a skill dir, whether the session is running the plugin
  you think it is. eval checks **law conformance in the shipped text**. A repo can be
  perfectly installed and still have quietly stopped obeying itself. Run both.
- **Not a repair tool.** It reads. It never edits a SKILL.md, never bumps a version,
  never commits.
- **Not a behavior grader.** It does not run the model, so it cannot tell you what a
  session *did* — only what the harness *told it to do*.

## The behavior-case boundary

`eval.py behavior --case <name>` is the **opt-in** model path, and it is deliberately
small:

```bash
python3 <skill>/scripts/eval.py behavior --case offload-spawn-directive
python3 <skill>/scripts/eval.py behavior --case graph-scanner-preference
```

It **prints** the exact bounded command (a single `claude -p … --model opus
--max-turns 1` one-shot) and the python grader that would judge the returned text. It
does not execute the model — `check` never spends a token, and behavior cases are
**never part of the ship gate**.

Three hard constraints on any case added here:

1. **One bounded one-shot per case.** No multi-turn sessions, no arms, no sweeps.
2. **Graders are python functions** over the returned text — regex or structure.
   **Never an LLM judge.** A judge turns a red test into an opinion.
3. **A case must earn its place** by guarding a law that leaves *no* static fingerprint.
   If a fingerprint exists, write a `check` instead — it is free and it names the line.

## Self-check before finishing

- Did every FAIL cite a real `file:line` a reader can open? A finding without an address
  is not a finding.
- Did the run finish in under two seconds and spend zero model tokens? If it grew slow,
  the suite has started doing the thing it replaced.
- Did I report the verdict **verbatim**, including WARNs, rather than summarizing it into
  "looks fine"?
- Did I resist repairing anything? eval reads; the fix is the owner's next move.
- If I added a check: does the fixture prove it flips **only** its own check?

## Finishing up

```bash
bash plugins/notrest/skills/eval/scripts/fixture.sh           # exit 0 = every assertion held
bash plugins/notrest/skills/eval/scripts/router-fixture.sh    # exit 0 = the routing law holds
```

`fixture.sh` builds a synthetic mini-harness that passes clean, then injects one violation
per check and asserts each flips exactly its own check to FAIL with exit 6. Run it after
any edit to `eval.py` — a conformance suite that cannot be falsified is decoration.

`router-fixture.sh` is the one behavior fixture in the suite that costs nothing: it pipes
real `UserPromptSubmit` payloads through `hooks/router.sh` and asserts each shape reaches
its verb, each suppression stays silent, and malformed stdin never breaks a prompt. Run it
after any edit to the routing table — a table nobody fires is a table nobody trusts.

**Chains:** `/doctor` for install and estate integrity → `/eval` for law conformance →
release. `/compile` when a check keeps finding the same violation by hand. `/spend` to
prove the routing law eval only reads about.
