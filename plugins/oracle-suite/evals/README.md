# ORACLE suite — eval harness

Five cases that guard the suite's load-bearing behaviors, written for Claude Code's
built-in plugin eval runner (`claude plugin eval`, CLI 2.1.207).

**These cases cost real tokens.** Every case spins up a live agent run — twice per run
when the ablation arm is on (with-plugin, then without-plugin), plus a judge call per
LLM grader. This is a **release gate**, not a hook and not something to fire on every
commit. Run it before a version bump, read the delta, then ship.

## Run it

From the repo root:

```sh
CLAUDE_CODE_WALNUT_SPIRE=1 claude plugin eval plugins/oracle-suite \
  --ablation with-without \
  --judge-model sonnet \
  --output-dir evals/results \
  --threshold 0.7
```

- `CLAUDE_CODE_WALNUT_SPIRE=1` — **required.** `claude plugin eval` is gated behind an
  early-access flag; without it the command exits with
  `` `plugin eval` is currently in early access ``.
- `plugins/oracle-suite` — the target is a **path**, so the runner grades the working
  tree, not the installed marketplace copy. Cases are discovered under
  `plugins/oracle-suite/evals/`, and the plugin resolves by walking up from each case
  dir to `plugins/oracle-suite/.claude-plugin/plugin.json`.
- `--ablation with-without` — **must be explicit** for a path target (it only defaults
  on when you target a plugin *by name*). The headline number is Δ: the with-plugin
  score minus the without-plugin score. A case that scores 1.0 in both arms is not
  measuring the plugin.
- `--judge-model sonnet` — the default judge is haiku, which is too small for these
  rubrics. The judge must not be the agent model.
- `--threshold 0.7` — exit 1 if any case falls below. The runner's default is `1.0`,
  which is brittle against LLM graders; 0.7 means "both primaries or one primary plus
  the literal".

Cheaper variants while iterating:

```sh
# one case, one run, no baseline arm — smoke test after editing a grader
CLAUDE_CODE_WALNUT_SPIRE=1 claude plugin eval plugins/oracle-suite \
  --case offload-policy --runs 1 --ablation none --judge-model sonnet

# one tag's worth
CLAUDE_CODE_WALNUT_SPIRE=1 claude plugin eval plugins/oracle-suite --tag policy --runs 1

# strict budget — aborts and reports partial results (exit 2) when the ceiling is hit
... --max-cost-usd 5
```

Results land in `evals/results/<timestamp>/aggregate-result.json` at the repo root
(gitignored). Check `plugins` in that file is non-empty — if it's `[]` the plugin did
not load and the whole run is meaningless.

## What each case guards

| Case | Guards |
|---|---|
| `01-offload-policy` | The opus-only offload hard rule: every spawn call pins `model: opus`, and an explicit fork request is refused because forks inherit the seat's model. |
| `02-coord-discipline` | The BANK step: closing out substantive work produces a real `[UTC] [session] ask -> landed \| evidence` ledger line with checkable evidence, not a description of one. |
| `03-honesty-labels` | Honesty labels: unverifiable figures come back as `[recall]`/`[unverified]` with a way to check them, instead of being asserted as current fact. |
| `04-routing-intake` | The oracle front door: "hey oracle" starts the six-question intake one question at a time, instead of answering the dangled question. |
| `05-graph-zero-tokens` | Zero-token graph building: the answer is `graph.py scan`, not the model reading and grepping the repo to construct the graph in context. |

## Case format

One directory per case under `evals/`, exactly as the runner documents it:

```
evals/
├── 01-offload-policy/
│   ├── prompt.md
│   └── graders/
│       ├── opus-on-every-lane.md
│       ├── refuses-the-fork.md
│       └── states-opus.md
└── ...
```

**`prompt.md`** — YAML frontmatter between `---` fences, then the prompt as the body.
Recognized keys, and nothing else (the schema is strict — an unknown key is a hard
error): `schema_version`, `name`, `description`, `tags`, `plugins`, `runs`,
`expected_outcome`, `model`, `max_turns`, `timeout_seconds`, `allowed_tools`,
`append_system_prompt`, `env`.

**`graders/<name>.md`** — one file per grader; the filename is the grader name. Frontmatter
`type:` selects `regex` | `file_exists` | `llm` | `tool_used` | `tool_order`. The body
is the pattern for `regex` and the criteria for `llm`; it is ignored for the others.
Defaults: `target`/`focus` = `last_message`, `weight` = 1, `match` = `contains`,
`tool_used.min` = 1.

Conventions these cases follow:

- **Single-turn prompts, transcript-only graders.** No `scaffold_script`, no
  `file_exists`, no `Bash`/`Write`/`Edit` grants — nothing here needs `--allow-tools`,
  and no case touches the filesystem. Cases run in an empty sandbox cwd, so prompts
  never assume a repo is present and never use absolute paths or `~/`.
- **Primary grader is an outcome, literals are secondary.** Each case has one or two
  `llm` rubrics at `weight: 1` scoring what a user would notice, plus at most one
  regex literal at `weight: 0.5`. A format string is never the only scored check —
  changing a skill's wording should cost half a point, not fail the gate.
- **Rubrics are PASS/FAIL conditions, not vibes.** The judge is asked for one word, so
  every rubric spells out what passes and what fails, including the near-miss cases.
- **`arm:` is set where it matters.** `tool_used` on `Skill` uses `arm: with-only` —
  without it the grader is display-only under ablation, since the baseline arm has no
  skills to load. The "must not call this tool" grader in `05` uses `min: 0`, `max: 0`,
  `arm: both`.
- **`timeout_seconds` on every case.** An under-set timeout scores 0 and reads as a
  content failure rather than a timeout.

## Authoring more cases

`claude plugin eval init --bare <name>` (with the same env var) writes a blank
`prompt.md` + `graders/criteria.md` pair to copy. Keep new cases in the same shape:
cheap, single-turn, transcript-graded, and discriminating under ablation — if a case
passes just as well without the plugin, it is measuring the model, not the suite.
