# release-ritual — the notrest ship, compiled

```
python3 compile/release-ritual/ship.py ship --version 3.2.0 --gates-passed \
  --message "v3.2.0 — <what landed>" \
  --changelog-file /tmp/section.md \
  --coord-line "- [2026-07-26 09:00Z] [fable-main] v3.2.0 shipped | evidence: ..." \
  --push --install
```

That is the whole release. Compiled from 10 real ships (COORD 2026-07-15 → 2026-07-25,
commits `9522ded` → `f3b148a`), with the sibling `plugin-update-commit` candidate folded in
as the `--install` half.

## What stays human

The script owns the **procedure**. The seat still owns:

- **The gates ruling.** `--gates-passed` is a refusal switch, not a checkbox the script can
  tick for itself. Without it the run exits 10 before touching a file.
- **Three prose inputs:** the changelog section (`--changelog-file`), the COORD line
  (`--coord-line`), and the commit message (`--message`).
- **The go, and how far it goes.** `--push` and `--install` are irreversible, so they are
  explicit flags. Omit `--push` and the run stops after the commit and says so. Omit
  `--install` and it prints the two CLI commands for you to run yourself.

**The runtime makes zero model calls.** Python 3 stdlib only; it shells out to `git`, to
`spend.py`, and to the `claude` CLI, and to nothing else.

**A failed ship leaves a clean tree.** Every write is atomic (temp file + `os.replace`) and
every written path is tracked; any abort after the first write restores those paths with
`git checkout --` before exiting. The rollback is armed for real ships only — never inside a
replay scratch, whose HEAD is deliberately the *pre*-ship commit.

## What it does, in order

1. `--gates-passed` or refuse (10).
2. Bump both manifests — `plugins/notrest/.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json` (metadata + the notrest entry). Entries are located **by
   name**, never by position or key order, so no manifest layout can make the writer walk into
   the neighbouring entry. The `oracle-suite` tombstone is pinned at 9.0.0 forever: a run that
   finds it altered aborts (11), and after the write both files are re-read from disk and
   re-asserted — all three versions equal the new one, the tombstone entry byte-for-byte
   unchanged — before anything is staged (12). Not a claim; a check.
3. Reconcile the skill count: count directories under `plugins/notrest/skills/`, then rewrite
   the spelled count ("Twenty-four skills") in `docs/TUTORIAL.md`, `plugins/notrest/README.md`
   and both manifest descriptions, and the numeral form ("24 skills") in the repo-root
   `README.md` and `CLAUDE.md` when they carry one. No-op when the count did not move. The
   **checker is wider than the rewriter**: it flags any spelled-count-shaped token sitting in
   a counted context, including ones the rewriter deliberately refuses to touch (ordinals such
   as "twenty-sixth"), and exits 13 quoting the offending line. *(The maiden replay caught real
   drift: at v3.1.0 three of the four spelled surfaces said "twenty-three" against 24
   directories, and the root `CLAUDE.md` still said 23 at HEAD.)*
4. Stamp `docs/oracle-skill-flow.html` — header `vX.Y.Z · N-skill harness`, footer
   `Manifest: notrest vX.Y.Z`. Each pattern must match exactly once (14).
5. Prepend the changelog section under the title line. Its first line must read
   `## X.Y.Z — YYYY-MM-DD`, matching `--version` and today UTC (15).
6. Append the COORD line(s); each must start `- [` (16).
7. Run `spend.py report`. Its verdict lines are always printed; **its** exit 4 (a
   model-routing violation) aborts the ship and prints the violation verbatim (17).
8. `claude plugin validate .` — the **only** skip is the CLI not being installed at all; any
   run that completes and exits nonzero is a failure and prints the validator's stderr (18).
9. `git add -A` and commit with the `Co-Authored-By: Claude Fable 5` trailer; abort if nothing
   staged (19).
10. `--push`: resolve the branch (`rev-parse --abbrev-ref HEAD`; a detached HEAD is refused,
    never guessed), push the **exact commit object** to that exact ref, then read the ref back
    with `ls-remote`. An empty `ls-remote` is its own failure, not a match (20).
11. `--install`: `claude plugin marketplace update notrest` then
    `claude plugin update notrest@notrest`, parsed for the target version (21).
12. One summary line: version · commit · pushed? · installed? · spend verdict.

## Replay

```
python3 compile/release-ritual/ship.py replay --at f3b148a --scratch /tmp/replay-a --time
python3 compile/release-ritual/ship.py --legacy-paths replay --at <pre-rename-sha> --scratch /tmp/replay-old
```

Replay clones the repo into scratch, puts the worktree at the ship commit and HEAD at its
parent, then **removes only what the ritual writes** — the version stamps, the changelog
section, the COORD line. Everything else the ship commit carried stays, because the script
never owned it. (v3.0.0 also retitled `CHANGELOG.md`; reverting that file wholesale would have
asked the script to reproduce a payload edit — the replay keeps it and removes only the
prepended section.) It extracts that ship's
real inputs from the repo's own history (changelog section from `git show <sha>:CHANGELOG.md`,
COORD line from the commit's own diff, message from `git log -1 --format=%B`, version from the
commit's `plugin.json`), runs the full pipeline without `--push`/`--install`, and diffs the
result against `git show <sha>:<path>`. `--time` prints wall-ms per stage. `--legacy-paths`
maps the two manifest paths, the skills dir, the README and `spend.py` to the pre-rename
`plugins/oracle-suite/` layout **and the pre-rename flow-page vocabulary** — those trees stamp
`vX.Y.Z · N-skill suite` and `Manifest: oracle-suite vX.Y.Z`, not `harness`/`notrest` (needed
for v2.16.0 / v2.16.1 / v2.17.0; v3.0.0, the rename ship itself, replays on current paths).
Pre-rename trees also carry no tombstone entry: clause 2's pin check skips what is not there.
Clauses 3 and 5 need no legacy branch — the count surfaces exist at those shas with correct
spelled words, and the changelog prepend anchors on the first `## ` heading, not on the title
line, so the v3.0.0 retitle is irrelevant to it.

### Why parity is scoped to nine surfaces

A ship commit carries **payload + procedure** — the feature that shipped, and the release
mechanics around it. `ship.py` owns only the procedure, so parity is asserted only where the
ritual writes:

| surface | compared |
| --- | --- |
| `plugins/notrest/.claude-plugin/plugin.json` | version field |
| `.claude-plugin/marketplace.json` | metadata + notrest + tombstone versions |
| `CHANGELOG.md` | full text (round-trip) |
| `docs/oracle-skill-flow.html` | full text |
| `COORD.md` | full text (round-trip) |
| `docs/TUTORIAL.md` | full text |
| `plugins/notrest/README.md` | full text |
| `plugin.json` description | string |
| marketplace entry description | string |

Feature-payload files are out of scope by design. Claiming parity over them would be claiming
the script writes the feature, which it does not and should not.

Two labels in that output mean something specific:

- **round-trip** — `CHANGELOG.md` and `COORD.md` are de-shipped by *removing* the section and
  the line the ritual writes, then the ritual puts them back. The content is round-tripped, so
  the test proves the insertion point, ordering and whitespace, not the prose. Said plainly
  because a reader would otherwise over-read the IDENTICAL.
- **DRIFT** — a count surface that differs *only* in the spelled count, where the historical
  file disagreed with its own skills directory at that commit. That is history being wrong and
  the ritual correcting it, established by arithmetic (`git ls-tree` count vs the word in the
  file), not by the script's opinion. Drift is reported and counted separately; it never
  silences a real difference, and any count difference where history *was* self-consistent
  fails as DIFFERS. The repo-root `README.md`/`CLAUDE.md` numerals are rewritten but not parity-
  compared: no historical ship kept them in sync, so comparing them would fail every replay
  for a defect that predates the script.

## Exit codes

| code | meaning |
| --- | --- |
| 10 | no `--gates-passed` — the human ruling is missing |
| 11 | the `oracle-suite` tombstone is not pinned at 9.0.0 |
| 12 | manifest versions disagree (before or after the bump) |
| 13 | skill-count surfaces disagree after reconciliation |
| 14 | a flow-page stamp did not match exactly once |
| 15 | changelog first line is not `## X.Y.Z — <today UTC>` |
| 16 | a `--coord-line` does not start `- [` |
| 17 | `spend.py report` exited 4 — model-routing violation |
| 18 | `claude plugin validate .` failed |
| 19 | nothing staged / commit failed |
| 20 | push did not land: `origin/main` != local HEAD |
| 21 | install output never mentions the target version |
| 30 | replay parity FAIL |
| 2 | usage / replay setup error |

## Fixture

```
bash compile/release-ritual/fixture.sh
```

One full run: replay v3.1.0 and v3.0.0 (the rename ship — the hardest case), the refusal
battery (10, 11, 12, 15, 17-with-nothing-committed), and count reconciliation against a
scratch clone with an extra skill directory. Prints PASS/FAIL per assert and exits nonzero on
any FAIL. It writes only inside `compile/release-ritual/.fixture-scratch/`.
