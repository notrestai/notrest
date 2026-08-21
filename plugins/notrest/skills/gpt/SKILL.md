---
name: gpt
description: "Chat-first GPT lane — /gpt talks to a persistent GPT-5.6 conversation (Codex CLI). Flags when asked: --once, --task, --vs, --new, --setup. Use on /gpt, \"ask gpt\", \"chat with gpt\", \"continue the gpt chat\", \"leave gpt a task\", \"gpt second opinion\". Opinions never sources ([model-opinion]); prompts leave the machine to OpenAI — no secrets, ever."
---

# gpt — the chat-first cross-model lane

**Codex boundary.** In a Codex task, the current seat is already GPT/Codex, so `/gpt` is
redundant by default. Do not shell back into Codex and call that a second opinion. Use this
skill on Codex only when the user explicitly asks for a separate persistent comparison/task;
otherwise answer in the current task and label model opinion normally. The no-secrets rule
still applies whenever a prompt leaves the current task.

`/gpt <anything>` is a conversation with GPT that remembers. One setup moment, then it's
just talking. Everything agentic is opt-in, explained, and verified before it's trusted.

## First use — the 2-question setup

No profile at `$GPT_LANE_ROOT/chats/main.profile` (default `~/.claude/gpt-lane/`, so the
conversation and its settings survive the session that started them) → run setup BEFORE
sending anything.
Ask both questions in one round (AskUserQuestion where available; plain numbered questions
otherwise), each option in plain words:

**Q1 — Thinking level** (how hard GPT reasons per reply):
- **low** — fast and cheap; small talk, quick lookups, routine turns.
- **medium** (recommended) — normal questions; the sensible default.
- **high** — slow, heavy on your plan quota; keep for genuinely hard reasoning.

**Q2 — How agentic may GPT be?**
- **chat-only** (recommended) — GPT answers in text; writes nothing, reads nothing.
- **worker** — you can also hand it background jobs (`--task`): it writes real files in
  its own empty workspace, and Claude verifies every deliverable before relaying.
- **repo-aware** — additionally allows `--here` runs where GPT reads the current
  directory; every such run is preceded by a stated secrets check.

Save both answers to `main.profile` (`LEVEL=medium\nMODE=worker`), then send the first
message with `gpt.sh chat` — it parses `session id: <uuid>` from the header and saves
`main.id` itself. Greet with one line stating the active settings so the user knows what
they got.

**Non-interactive setup (orchestrators, unattended sessions):** `--setup think=<level>
mode=<chat-only|worker|repo-aware>` skips the questionnaire — REQUIRED form for
fable-director and any auto-mode session; never block an unattended session on questions.

## Every message after — the resume loop

```bash
bash plugins/notrest/skills/gpt/scripts/gpt.sh chat "<MESSAGE>"
```

That is the whole loop. `scripts/gpt.sh` holds the flag order, the empty-cwd isolation,
the session-id capture, and the receipt — the four things that were being retyped from
memory and getting subtly wrong. It prints codex's output verbatim (header included, so
the `reasoning effort:` echo stays visible as proof the level applied) and writes the
session id on first use.

| Call | Shape | Sandbox |
|---|---|---|
| `gpt.sh chat "<msg>" [--think L] [--chat NAME]` | resumes the persistent conversation; fresh session + saved id on first use | read-only |
| `gpt.sh once "<q>" [--think L]` | one-shot, nothing saved — the director-safe form | read-only |
| `gpt.sh task <slug> "<job>" [--think L]` | background job in a fresh EMPTY workspace; follow-ups resume it | **workspace-write** |
| `gpt.sh parse <transcript>` | prints `SESSION=` / `TOKENS=` / `EFFORT=` from a codex transcript | — |

Exit codes: 0 ok · 2 usage (including a `--think` outside the low/medium/high ladder) ·
3 codex CLI absent (it hands over the install block and stops, never attempting auth
repair) · 4 codex itself returned non-zero. Env: `GPT_LANE_ROOT` (state, default
`~/.claude/gpt-lane`), `GPT_CODEX_BIN`, `GPT_SPEND_ROOT`, `GPT_NO_SPEND=1`.

Relay the answer quoted + `[model-opinion]`, tokens-used line included. **The receipt is
automatic:** every call logs through the spend skill's `spend.py` (append-only) on
`--lane gpt` — the count parsed from codex's own `tokens used` echo graded `observed`,
and a chars/4 `estimate` when that echo is missing, so the cross-model lane can never
quietly cost nothing in the routing report. `--chat <name>` runs parallel named
conversations (own `.id`/`.profile`). `--new` re-runs setup. If the id file is lost,
`resume --last` recovers the most recent session — say you did.

Fixture: `bash plugins/notrest/skills/gpt/scripts/fixture.sh` — exit 0 = every assertion
held. It runs against a stub codex, so it spends no quota and makes no network call: the
stub records its own argv, which is how the resume flag order, the read-only/workspace-write
split, and the empty-cwd rule are asserted rather than trusted.

## Extras (each one sentence to invoke, details on use)

- **`--once "<q>"`** (`gpt.sh once`) — a one-shot outside any chat: fresh `codex exec`, no
  session saved. The director-safe form. `--think <level>` overrides the profile per call.
- **`--task <slug> "<job>"`** (worker/repo-aware profiles only; `gpt.sh task`) — background
  job in a fresh EMPTY workspace `$GPT_LANE_ROOT/work/<slug>/` with `--sandbox workspace-write`,
  spawned `run_in_background`. The prompt MUST name deliverable files. On the completion
  notification: read the deliverables and check them — content, not existence — before
  relaying as `[model-artifact]`. ⚠ Hardened after GPT's own review of this design: never
  feed the workspace untrusted files (embedded instructions steer the worker), and treat
  its network posture as unknown [unverified] — nothing secret goes in, period.
  Follow-ups resume the task's session in the same workspace.
- **`--vs "<question>"`** — blind comparison, reproducible: write the canonical question
  to `question.md` FIRST; write YOUR complete answer next (sealed, before GPT sees
  anything); send GPT the file's text verbatim; present both + a delta verdict (agreement
  = comfort not evidence; note that you judged the answers knowing which was whose —
  position bias disclosed, also per GPT's review).
- **`--here "<q>"`** (repo-aware profile only) — run in the current directory after a
  one-line stated secrets check (no .env/keys/credentials present). Never in a directory
  holding material the prompt must stay blind to (ledgers, answer keys).

## Fast paths (latency discipline — measured, not vibes)

Live timings: one-call image = 33s wall; the same job run conversationally = 2 serial
calls + inspection between them, roughly 3–4× longer. The rules that keep it fast:

- **One call per job.** For any known job, ONE prompt carries the whole contract: name
  the built-in tool directly ("use your image_gen tool — don't read docs first"), the
  exact deliverable filename, and the DONE-token reply. Discovery and execution must
  never be separate turns.
- **`--img "<prompt>" [out.png]`** — the canned image path: one workspace-write call at
  LOW effort (pixels need no reasoning), save + DONE contract, verify, display. ~33s.
- **Background by default for anything slow.** File-producing or >30s-expected jobs run
  as background tasks (the harness notifies on completion) — the user keeps working;
  latency becomes invisible, not merely smaller. Foreground is for quick chat turns.
- **Fan out, don't queue.** N independent jobs = N parallel background tasks, each in
  its own empty workspace. The CLI is serial per call; the harness is not.
- **Effort by job, not only profile:** mechanical output (images, conversions,
  boilerplate) → low; normal questions → profile level; hard reasoning → high on ask.
- **Right lane for the job:** speed, parallelism, cheap volume → the harness's native
  Claude subagents; a genuinely foreign prior or ChatGPT-plan capabilities (built-in
  imagegen) → this lane. Don't pay the bridge tax for work a native subagent does faster.

## For directors and orchestrators (fable-director)

This lane is NOT a metered subagent — it shells to Codex CLI on the OWNER'S ChatGPT plan,
so the director's never-spawn-subagents rule does not forbid it. Sanctioned uses: a
`--once` second opinion on a risky EDIT SPEC before applying; one extra refuter voice on
a QC brief. Always `--once`, low/medium thinking, empty dir, `--setup` flags not
questions. Never as an explorer — the lanes are the explorers.

## Verified facts (codex-cli 0.144.1 — don't relearn these)

- Effort ladder: **low | medium | high**. `minimal` → live API 400 on the 5.6 family.
  The run header echoes `reasoning effort:` — that echo is the proof the level applied.
- Resume flag ORDER: `--sandbox`/`-c` BEFORE the `resume` subcommand,
  `--skip-git-repo-check` after; other placements rejected. Memory across invocations
  verified live (token planted turn 1, recalled post-exit).
- `--skip-git-repo-check` mandatory outside trusted dirs; `</dev/null` kills the stdin
  wait; codex agentically reads its cwd → empty-dir isolation is the default everywhere.
- Session id: `session id: <uuid>` in the header. Answer follows the `codex` marker;
  `tokens used` follows the answer.

## Hard boundaries (unchanged, load-bearing)

- **Opinion ≠ source** — [model-opinion] carries zero evidentiary weight in
  factcheck/researcher; two models agreeing is one guess echoed.
- **Prompts leave the machine** — and in --here/--task, file contents do too. No secrets,
  no keys, nothing the user hasn't already decided to share with OpenAI.
- **Quota is the user's** — say when high effort is worth it and when it isn't.
- **Auth**: expired login → the user re-runs `codex login`; never attempt auth repair.
  Missing CLI → hand the install block and stop:
  `npm install -g @openai/codex && codex login && codex exec "reply with exactly: READY"`

## Self-check before finishing

- Profile honored: header's effort echo matches the saved LEVEL; mode gates respected
  (no --task on chat-only, no --here off repo-aware).
- Chat integrity: header `session id:` matches the stored id (or --last recovery stated).
- Task deliverables read and content-checked before "done"; artifacts labeled.
- --vs order provable: question.md, then your sealed answer, then the GPT call.
- Nothing sensitive entered a prompt; setup answers were saved so the user is never
  re-asked what they already chose.
