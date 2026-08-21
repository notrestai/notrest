---
name: eval
description: "The harness's law-conformance suite — one static pass asking whether every law left a fingerprint in the shipped files: offload policy, honesty labels, scripts that compile, cited files that exist, append-only ledgers, worker contracts, safe front-matter, safety laws, silent hooks, the routing enforcer. Use on \"/eval\", \"check the laws\", \"conformance check\", or before any release. Zero tokens, seconds. doctor checks the INSTALL; eval checks the LAWS."
---

# eval — does the harness obey its own laws?

**Runtime adapter.** OFFLOAD-POLICY is dual: every documented lane contract maps Codex
to explicit `model: "gpt-5.6-sol"` (with `fork_turns: "none"` or a bounded recent-turn
fork) and Claude to explicit `model: "opus"` (never `subagent_type: "fork"`). Claude hook
checks remain checks of the Claude adapter; their PASS does not claim Codex ran those
hooks. `behavior --surface codex|claude` prints the correct bounded host command.

```bash
python3 plugins/notrest/skills/eval/scripts/eval.py check --root .
```

That is the whole ship gate. Add `--json` for machine output. Exit **0** all pass ·
**5** warnings only · **6** any FAIL · **2** usage.

**Router shape:** `law-check` — the UserPromptSubmit router (`hooks/router.sh`) nudges a
prompt here when it looks like *"check the laws"* or *"conformance check"*. *"health check"*
is a different shape and goes to `/doctor`: doctor checks the INSTALL, eval checks the LAWS.

## The doctrine: check the fingerprint, not the behavior

**A law that is well-encoded leaves a static fingerprint in the shipped text.** If the
offload policy is real, the runtime model map is written where spawns are written. If the
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

## The twelve checks

| Check | The law |
|---|---|
| `OFFLOAD-POLICY` | every documented spawn maps **Codex=gpt-5.6-sol** and **Claude=opus**; inherited/full-history forks are banned; the Claude SessionStart hook carries the Claude rule |
| `HONESTY-LABELS` | every claim-making skill (researcher, factcheck, marketresearcher, explainer, decider, recap, watch, draft) defines or uses `[cited]/[recall]/[estimate]/[unverified]` or its documented verdict grammar |
| `SCRIPT-OWNS-SCANNING` | every cited scanner exists in the tree and `py_compile`s, and every shipped script is named by its SKILL.md — this is what backs "the scanner reads the files, the model never has to" |
| `REFERENCES-CITED` | every **bare** `references/…` or `scripts/…` path a SKILL.md cites exists in that skill's own directory. A path already carrying a prefix (`<spend-skill>/scripts/spend.py`) is a deliberate cross-skill reference and is left alone; a bare path that ships under a *different* skill WARNs unless the citing line names that skill; `.py` is left to `SCRIPT-OWNS-SCANNING`, so one defect never lights two checks |
| `ESTATE-WRITE` | anything that writes COORD, COORD-AGENTS or the spend ledger says **append-only** or routes through the owning script; a directive to hand-edit one is a FAIL |
| `WORKER-CONTRACT` | every worker skill ships a self-check section and a finishing-up/chains section (arrangement contracts — fable-mode, fable-director, oracle, agentswarm, game-forge — are exempt by construction) |
| `TRIGGER-SANITY` | front-matter `name` matches the directory; the description is a scalar YAML accepts (**an unquoted `": "` silently kills a skill while the file sits on disk**) and names at least one `/slash` trigger |
| `SAFETY-LAWS` | draft: *a draft is never sent*. watch: *a dead source is never a refutation*. compile: *never auto-install*. fable-director: the tombstone/metered-key scope |
| `HOOK-CONTRACT` | every hook is silent-on-failure — no `set -e`, always ends `exit 0` — and `hooks.json` references only files that exist |
| `ROUTER` | the routing law has an enforcer: `hooks/router.sh` is registered under **UserPromptSubmit**, `bash -n` accepts it, it is silent-on-failure, and every `/notrest:<skill>` its table can emit names a skill directory that exists |
| `ROUTE-TABLE-PARITY` | the routing table's **two authorities agree**: every verb `router.sh` can emit is named in oracle's `**Route to the right tool:**` bullet and vice-versa (a verb in one and not the other is a FAIL — the user is *told* one route and *nudged* another), and every routed skill acknowledges the shape that lands on it with a body line ``**Router shape:** `<shape>` `` (a token that drifted from the router arm is a WARN; a verb with no skill dir is left to `ROUTER`, so one defect never lights two checks) |
| `ROUTE-CONFORMANCE` | **WARN-grade, never a gate.** Every `routed to /<skill>` line the estate recorded left downstream evidence — a later COORD line naming that skill, a `skill=` record in `archive/findings.jsonl`, or a `COORD-AGENTS.md` entry. The newest **3** ledger lines are a grace window (a lane routed a minute ago has landed nothing yet), a route the line itself *declines* ("not routed to …") is the law being applied deliberately, and an estate with no route lines SKIPs |

A line that names sonnet, haiku or `fork` **alongside a negation** is the law being
stated, not a breach of it; the checker reads the line before judging it.

## `--baseline` — what MOVED

A green suite tells you the laws hold. It does not tell you what your edit *did*.

```bash
python3 <skill>/scripts/eval.py check --root . --json > /tmp/before.json
# …work…
python3 <skill>/scripts/eval.py check --root . --baseline /tmp/before.json
```

After the summary, a `CHANGED` section names every check whose status flipped and every
finding that appeared or disappeared, each with its `file:line`. Unchanged runs say
*nothing moved* in one line. `--json` puts the same diff under a `changed` key.

**The baseline never touches the verdict.** The exit code always reports this run — a
regression against a green baseline still exits 6, and a missing or corrupt baseline file
is reported in the section, never raised, with the exit code untouched. A diff is a
reporting mode; the gate stays the gate.

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
bash plugins/notrest/skills/eval/scripts/pretool-fixture.sh   # exit 0 = the hard gate has teeth
```

`fixture.sh` (28 assertions) builds a synthetic mini-harness that passes clean, then injects
one violation per check and asserts each flips exactly its own check to FAIL with exit 6. Run
it after any edit to `eval.py` — a conformance suite that cannot be falsified is decoration.
`pretool-fixture.sh` (35 assertions) proves the PreToolUse gate: rule blocks against stub
instruments, all four override forms, fail-open on garbage, and the miss-path timing bound.
One nuance the HOOK-CONTRACT law tolerates by design: a PreToolUse hook exits 2 on its
DECISION path — blocking is its job; its failure paths still exit 0 (fail-open).
It also asserts the boundaries that keep findings actionable: a deleted `.py` stays
`SCRIPT-OWNS-SCANNING`'s alone (never also `REFERENCES-CITED`); a ghost verb moved through
*both* authorities stays `ROUTER`'s alone (never also `ROUTE-TABLE-PARITY`); a drifted shape
token WARNs instead of failing; `ROUTE-CONFORMANCE` warns on an unbacked route but stays
silent for one a later line, a findings record, or the 3-line grace window covers, and for one
the ledger says was deliberately declined; and `--baseline` adds a section without moving the
exit code — unchanged, regressed, and missing-file all asserted.

`router-fixture.sh` (31 assertions) is the one behavior fixture in the suite that costs
nothing: it pipes real `UserPromptSubmit` payloads through `hooks/router.sh` and asserts each
shape reaches its verb, each suppression stays silent, and malformed stdin never breaks a
prompt. It also pins **first-match order** — a history question ("how did we get here") must
fall past the instrument arms to `/recap`, and a research question mentioning health checks
must reach `/researcher` — and the **self-named arms** (`project graph`, `spend report`),
where the trigger phrase contains the verb's own name and the "already named it" suppression
would otherwise leave the arm permanently dead. Run it after any edit to the routing table —
a table nobody fires is a table nobody trusts.

**Chains:** `/doctor` for install and estate integrity → `/eval` for law conformance →
release. `/compile` when a check keeps finding the same violation by hand. `/spend` to
prove the routing law eval only reads about.
