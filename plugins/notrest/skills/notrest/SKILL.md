---
name: notrest
description: "Establish the harness in a project and bind this session to it — presence is not establishment. Use on \"/notrest\", \"establish notrest\", \"establish the harness\", \"set up the plugin in this project\", \"make this project follow the plugin\", or the drift check \"is this session following notrest?\". Writes COORD.md + a marked CLAUDE.md protocol block, idempotently; `check` reads only and never runs git init uninvited."
---

# notrest — the establishment verb

```bash
python3 plugins/notrest/skills/notrest/scripts/establish.py check       # is it established here?
python3 plugins/notrest/skills/notrest/scripts/establish.py establish   # make it so (idempotent)
```

**Router shape:** `establish` — the UserPromptSubmit router (`hooks/router.sh`) nudges a
prompt here when it looks like *"establish the harness"*, *"set up the plugin in this
project"*, or *"make this project follow the plugin"*. *"health check"* is a different
shape and goes to `/doctor`; *"check the laws"* goes to `/eval`.

## The defect this descends from

**2026-08-02.** The owner ran a whole session in a project folder believing the harness
governed it. It did not. The folder was not a git repo, and **every estate hook was
git-gated** — `session-start.sh` scaffolded `COORD.md` only at a git root,
`agent-ledger.sh` bailed on line 17 outside git, `coord-nudge.sh` and `session-end.sh`
did the same. So the session got the *discipline echoes* — the fable anchor, the offload
rule, the identity line, all unconditional — and **none of the estate**: no ledger, no
agent index, no cushion, no roll. Nothing errored. Nothing logged. The session simply had
no memory, and it looked exactly like one that did.

That is the gap this verb closes, and the shape of the gap is the lesson:

> **Presence is not establishment.** The plugin being installed means every session gets
> nudged. It does not mean any project has a ledger, a protocol block, or a trail. Those
> are files, and files have to be written by somebody.

## The four laws

1. **Establishment is files plus a contract, and both are checkable.** A project is
   established when it carries `COORD.md` (with the ledger header every estate reader
   parses) and a **marker-delimited, versioned protocol block** in `CLAUDE.md`. Two
   surfaces, two lines of output, one exit code. Anything softer is a feeling.
2. **The script reports; the seat judges.** `establish.py` emits establishment facts
   (which drive the exit code) and **adoption facts** — ledger lines beyond the scaffold,
   age of the newest line, whether the agent and spend ledgers exist — which are `INFO`
   and can **never** move the exit code. Whether a session is *actually following* the
   plugin is a judgment about behavior, and a judgment belongs to the seat reading the
   lines. An exit code that swung on how busy a ledger looked would make the fixture
   non-deterministic and the verdict unfalsifiable at once.
3. **Establishing writes; binding is the seat's own act.** The files are inert. The
   session that runs this verb must then *operate* under the protocol — from that turn
   on, not from the next session.
4. **The estate never scatters.** `establish.py` refuses any root that is neither a git
   repo nor carries a project marker (`CLAUDE.md`, `README.md`, `package.json`,
   `pyproject.toml`, `COORD.md`) and exits **2** naming what it looked for. Some refusals
   are **absolute** — `--root` cannot overrule them, because a stray `README.md` must never
   make one of these a project: **$HOME** (a `CLAUDE.md` there is loaded into every session
   on the machine), any **filesystem root**, the three **well-known home folders**
   `~/Desktop`, `~/Documents` and `~/Downloads` by exact path (their *subdirectories* are
   ordinary projects), and a **subdirectory of a git repo** (every estate hook resolves to
   the toplevel, so an estate below it would be written by nobody and read by nobody — the
   refusal names the toplevel to use instead). `.claude/` is deliberately *not* an
   establish-time marker: `~/.claude` exists on every machine, and while it was on that
   list `/notrest` from a home directory would have established the estate in $HOME.

## The ritual — PROBE · ESTABLISH · BIND · REPORT

**1 · PROBE.** Run `establish.py check` and *read its lines*. It tells you what already
exists; never assume a fresh project or a stale one.

**2 · ESTABLISH.** Run `establish.py establish`. Report **exactly what was written versus
what was already present** — the script's own verdict line names it (`wrote: COORD.md,
CLAUDE.md` / `wrote: nothing (already established)`). "Established" over a project that
was already established is not a lie, but it is not news either, and the difference is
the whole value of the line.

**3 · BIND.** This is the part no script can do, and it happens **in this session,
immediately** — not deferred, not "from now on" in the abstract:

- Append **one** ledger line to `COORD.md` recording the establishment
  (`- [YYYY-MM-DD HH:MMZ] [notrest] established the harness -> COORD.md + CLAUDE.md
  protocol block v1 | evidence: establish.py exit 0`). `COORD.md` is **append-only** —
  add the line at the end; never rewrite COORD history.
- Operate under the protocol **from this turn on**: fable discipline (ORIENT → PROBE →
  ACT → PROVE → BANK, evidence or the word *unverified*), the offload HARD RULE (every
  spawned lane sets model `"opus"` explicitly; delegate via `/notrest:agentswarm`; a
  build runs ONE persistent lane and feedback resumes it), one honest ledger line per
  substantive prompt when its work lands, and `/sessionend` at the close.

**4 · REPORT.** Establishment status, the adoption facts as facts, and — when the root is
not a git repo — the warning, in the owner's hearing rather than in a footnote.

## `check` — the drift check

When someone asks *"is this session following the plugin?"*, that is this verb in
read-only mode. `check` writes nothing, and its INFO lines are the evidence you reason
from — an established project whose newest ledger line is four hours and nine prompts old
is a session that stopped banking, and **you say so plainly**. The honest answers are:

| what the lines show | the honest report |
|---|---|
| exit 0, ledger lines recent and plural | established, and the trail says the session is banking |
| exit 0, zero lines beyond the scaffold | established `[cited]`; *following* is **`[unverified]`** — nothing has been banked yet |
| exit 5 | partially established — name which surface is missing or which block version is stale |
| exit 6 | not established; the nudges a session sees are not an estate |

Never upgrade "the files are there" into "the session is following it." The files are
`[cited]`; adherence is an inference, and it carries its label.

## Exit codes

| exit | meaning |
|---|---|
| 0 | established — both surfaces present, block at the current version |
| 5 | partially established — a surface missing, damaged, or a block at an older version |
| 6 | not established |
| 2 | usage error, or a **refused root**: no project marker · $HOME · `/` · a subdirectory of a git repo |

The non-git warnings are **WARN lines that never move the exit code**: git is not part of
establishment, and a project established outside git is genuinely established.

## Outside git — what is real and what is weaker

All four estate hooks share ONE resolver — `hooks/estate-root.sh`, sourced by
`session-start`, `coord-nudge`, `agent-ledger` and `session-end`, because four hooks that
disagree about the root are four different estates. It answers: the git toplevel, else the
nearest `COORD.md` walking up at most three levels — **stopping at any directory that
carries a project marker of its own** (`CLAUDE.md`, `README.md`, `package.json`,
`pyproject.toml`, `.git`, `.claude` — the boundary list and the marker list are ONE list,
and leaving `CLAUDE.md` off it left the commonest shape of all, a CLAUDE.md-only
subproject, adopting its parent). An un-established subproject must never be adopted into
an unrelated parent's estate: that mistake wrote one project's ledger lines, its verbatim
commission briefs, and the parent's own compile candidates into another project's session.
A **broken ledger is itself a boundary** — a `COORD.md` that dangles or escapes means this
directory has an estate that is currently unusable, and walking past it to adopt a distant
one is exactly the wrong repair. It never reaches `$HOME`, `/`, or the well-known home
folders. So an
established non-git project gets the live-ledger nudge, the per-prompt COORD discipline,
the agent index and briefs, the spend receipt, the session-end cushion and the volume
roll. **What stays weaker, named rather than waved at:**

- **Self-update is dead** — the SessionStart hook's `git pull --ff-only` has no clone to
  pull, so the harness cannot update itself there.
- **Ship gates are weaker** — no commit, no diff, no HEAD-vs-tree comparison; *what
  changed* has no answer a machine can produce.
- **The trail is not diffable** — the ledger still records what landed, but nothing binds
  a ledger line to a revision of the files it describes.

`establish --git-init` runs `git init` **and nothing else** — no add, no commit. It is
**opt-in only**: `git init` changes what a directory *is*, and that is the owner's
decision, never a side effect of establishing a ledger. Offer it; wait for the yes.

## What this skill never does

- **Never runs `git init` uninvited.** Only behind the explicit `--git-init` flag.
- **Never installs, uninstalls, or updates a plugin.** Establishment is about *this
  project's* files. Install state is `/doctor`'s subject, and on the owner's machine a
  marketplace reinstall silently shadows the skills-dir runtime.
- **Never writes outside the resolved project root** — and neither do the hooks. Every
  write path, here and in the hooks' python halves, resolves its target and refuses one
  that lands outside the root; a link *inside* the root is written **through**, so it keeps
  working instead of being replaced by a regular file. The
  symlink-marching-out-of-the-repo defect class is a real scar here, twice over.
- **Never edits `CLAUDE.md` outside its own marker block.** Everything beyond
  `<!-- notrest:protocol v1 -->` … `<!-- /notrest:protocol -->` is the project's own text
  and survives **byte for byte** — the round trip preserves CRLF line endings and bytes
  that are not valid UTF-8, which a naive read-and-rewrite destroys silently. It is **not
  an encoding converter** and will not pretend to be one: a UTF-16 or UTF-32 `CLAUDE.md` is
  refused outright, since appending a UTF-8 block would "preserve every byte" while leaving
  the file unreadable to its own reader. An older
  block is replaced **in place** (and any hand-edit inside the markers is banked to
  `CLAUDE.md.notrest-v<N>.bak` first, and said out loud); a current one is left untouched;
  a missing one is appended at the end. Markers inside a fenced code block are
  documentation, not the block. If the markers are **ambiguous** — a stray opener above
  the block, or two blocks in one file — nothing is written at all and the finding names
  the line numbers: a tool that guesses which markers it owns eventually eats the file.
- **Never rewrites COORD history.** An existing `COORD.md` is left exactly as found —
  established means *the ledger exists*, not *the ledger is mine*.
- **Never claims a session is compliant** because the files are present. See law 2.

## Self-check before finishing

- Did I run `check` **before** `establish`, and report what was already there separately
  from what I wrote?
- Did I append the establishment line to `COORD.md` **in this session** — or did I write
  the files and call binding done?
- Am I actually operating under the protocol now (opus-only offload, ledger line per
  substantive prompt), or did I only describe it?
- If the root is not a git repo, did the owner *hear* which surfaces are degraded, and
  did I offer `--git-init` rather than running it?
- Did I keep adoption facts labeled as facts, and adherence labeled `[unverified]` when
  the ledger is empty?

## Finishing up

Chains: `/notrest` establishes → `/oracle` runs intake in the now-established project →
work → `/sessionend` closes it. `/doctor` answers the *install* question this verb
deliberately does not touch; `/eval` checks the laws; `/recap` reads the trail this verb
starts.

```bash
bash plugins/notrest/skills/notrest/scripts/fixture.sh   # exit 0 = every assertion held
```

187 assertions in a `mktemp` sandbox, over marker directories, non-git projects, a
hostile-`CLAUDE.md` corpus and two scratch git repos. The script contract: a fresh project
checks 6 and establishes to 0; establishing twice leaves **one** block and a
byte-identical `COORD.md`; a CRLF-and-latin-1 file round-trips with its bytes intact; a
fenced example is not the block; a stray opener, duplicate blocks, a read-only directory
and an escaping symlink each leave the file **byte-untouched**; `$HOME`, `/` and a git
subdirectory are refused; a hand-edited block is banked before it is replaced.

Two assertions exist only to kill a mutant: this fixture's first version passed **78/0
against a de-atomized `atomic_write`** — every assertion held while the property was gone.
A read-only `CLAUDE.md` in a writable directory now proves the atomic path (tmp+replace
succeeds where `open(w)` cannot), and a read-only directory proves a failed write leaves
no `.notrest-*.tmp` debris and an untouched target.

It also drives the **hooks themselves** — all four, through the shared resolver — in
non-git `COORD.md` projects, across a project boundary (where all four must agree there is
no estate), through in-root and escaping symlinks, and in a scratch git repo for the
regression, with the brief and spend-receipt legs exercised against a real transcript.
The hole this verb closes lived in the hooks, and a fix nobody exercised is a fix nobody
has.
