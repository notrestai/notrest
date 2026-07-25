# background — release-ritual, the maiden compile

Companion to `release-ritualDossier.md` (the verdict) and `verdict.html` (the visual). This
file carries the working: what evidence was actually readable, the full reconstructed
contract, the partition, the per-scenario benchmark, and the refuter's findings with their
disposition.

Candidate: **release-ritual** — machine slug `ship-commit-fixtur` (an earlier scan generation
called the same cluster `commit-follow-lan`). Owner-picked for the maiden run of `/compile`.

---

## 1 · Evidence coverage — stated before anything is claimed

The compile doctrine's rule is that you never claim history you could not access. So:

| source | what was readable | what is missing |
|---|---|---|
| `COORD.md` + `COORD-ARCHIVE.md` | the ship lines across **2026-07-15 → 2026-07-25** | earlier ship lines predate the ledger's discipline; a ship that never got a COORD line is invisible to the scan |
| git history | commits **`9522ded` → `f3b148a`**; ten ships in the span; five replayed end-to-end | ships before `9522ded` were not walked |
| `spend/ledger.md` | `purpose=` strings for the lanes in the span | main-loop consumption is never exposed to the model — see §6 |
| session transcripts | **not required and not relied on**; the detector's `--transcripts` input was optional and the contract below is reconstructed from ledger + diffs | any reasoning that lived only in a compacted transcript is gone; nothing load-bearing here depends on it |

**Occurrence count is generation-dependent.** The candidate reports **10–18 occurrences**
depending on which scan generation you read — the low number is the COORD-only view, the high
number is after cross-source fusion folds the spend-ledger purposes and the sibling
`plugin-update-commit` rows (the `--install` half) into the same cluster. Both are true
statements about different views; neither is a bug. Quote the view with the number.

**What is compacted away:** the seat's own deliberation on each historical ship — why a
particular version number, why a given CHANGELOG framing. That judgment is exactly what the
compile leaves human (§3, bucket C), so its absence does not weaken the contract.

---

## 2 · The functional contract — twelve clauses

Reconstructed from the trail, then verified against the built runtime. Evidence tokens:
`[commit …]` = a real ship whose diff shows the clause being performed; `[README §N]` = the
runtime's own documented clause; `[exit N]` = the refusal code the seat exercised.
Nothing below is `[unverified]`.

| # | Responsibility | Evidence | Required for parity? | Owner today | Owner after | Why |
|---|---|---|---|---|---|---|
| 1 | Refuse to run without `--gates-passed` — the human ruling that the gates were checked | `[README §1]` `[exit 10]` seat-exercised | no — a gate, not a written surface | HUMAN (seat says "gates passed") | **HUMAN**, now enforced by CODE | The ruling is judgment. A script may enforce that it was made; it may never make it. |
| 2 | Bump **both** manifests — `plugins/notrest/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (metadata + the `notrest` entry) — while the `oracle-suite` tombstone stays pinned at 9.0.0 | `[commit f3b148a]` `[commit fbe1e07]` `[README §2]` `[exit 11/12]` | **yes** — 3 version fields + the tombstone | CODE (was: hand-edit) | **CODE** | Pure mechanics with one trap: two manifests must agree and a third entry must not move. Exactly what humans get wrong at 1am. |
| 3 | Reconcile the skill count across **six** prose surfaces from `ls plugins/notrest/skills/` | `[commit f3b148a]` (drift found) `[README §3]` `[exit 13]` | **partial** — 4 of 6 compared; root `README.md` / `CLAUDE.md` numerals rewritten but **not** compared | CODE (was: hand-edit, inconsistently) | **CODE** | Counting directories is arithmetic. History proves humans skipped surfaces (§5, drift=3). |
| 4 | Stamp `docs/oracle-skill-flow.html` header (`vX.Y.Z · N-skill harness`) and footer (`Manifest: notrest vX.Y.Z`), each matching exactly once | `[commit f3b148a]` `[README §4]` `[exit 14]` | **yes** — full text | CODE (was: hand-edit) | **CODE** | Two fixed patterns. "Exactly once" is the whole safety property. |
| 5 | Prepend the CHANGELOG section, asserting its first line reads `## X.Y.Z — YYYY-MM-DD` against `--version` and today UTC | `[commit f3b148a]` `[README §5]` `[exit 15]` | **yes** (round-trip — see §5) | HUMAN writes prose / CODE places it | **CODE places, HUMAN writes** | The insertion point and the date assertion are mechanics; the release narrative is not. |
| 6 | Append the COORD line(s), each required to start `- [` | `[commit f3b148a]` `[README §6]` `[exit 16]` | **yes** (round-trip — see §5) | HUMAN writes / CODE appends | **CODE appends, HUMAN writes** | Same split as §5. The ledger's format is mechanical; its content is testimony. |
| 7 | Run the **spend gate** — `spend.py report`; its exit 4 (model-routing violation) **aborts the ship** and prints the violation verbatim | `[README §7]` `[exit 17]` seat-exercised | no — a gate | HUMAN (remembered to run it) | **CODE** | The policy already existed; only its enforcement was optional. Now it is not. |
| 8 | `claude plugin validate .` — the only permitted skip is the CLI being absent entirely | `[README §8]` `[exit 18]` seat-exercised (repro re-run) | no — a gate | HUMAN | **CODE** | See refuter finding R2: this clause is where a plausible string-match nearly shipped a broken plugin. |
| 9 | `git add -A` and commit with the `Co-Authored-By: Claude Fable 5` trailer; abort if nothing staged | `[commit f3b148a]` `[README §9]` `[exit 19]` | no — not a compared file surface | CODE-ish (a typed command) | **CODE** | Mechanical, but the trailer is policy and was occasionally forgotten. |
| 10 | `--push`: resolve the branch (detached HEAD refused, never guessed), push the **exact commit object** to `<sha>:refs/heads/<branch>`, then verify with `ls-remote` (an empty result is its own failure) | `[README §10]` `[exit 20]` | no — never executed against a real remote | HUMAN | **HUMAN flag, CODE executes** | Irreversible. Stays an explicit flag forever. |
| 11 | `--install`: `claude plugin marketplace update notrest` then `claude plugin update notrest@notrest`, parsed for the target version | `[README §11]` `[exit 21]` | no — never executed | HUMAN | **HUMAN flag, CODE executes** | Mutates the user's installed toolchain. Explicit or nothing. |
| 12 | Emit one typed summary line: version · commit · pushed? · installed? · spend verdict | `[README §12]` | no | HUMAN (prose recap) | **CODE** | A typed terminal state beats a model's paragraph about what it thinks it did. |

**Completeness note.** No hard responsibility was dropped to flatter the benchmark. Clauses
10 and 11 are the expensive, irreversible ones and they are *in* the contract and *in* the
runtime — they are simply the ones the replay harness cannot exercise, which is disclosed
rather than hidden (§7, KNOWN GAPS).

---

## 3 · The partition

| bucket | contents |
|---|---|
| **A · deterministic runtime** | Clauses 2, 3, 4, 12 entirely; the placement/assertion halves of 5 and 6; the invocation-and-interpretation of gates 7 and 8; the staging and commit of 9; the exact-object push and `ls-remote` verification of 10; the install invocation and version assertion of 11. **853 lines, python3 stdlib only.** Shells out to `git`, `spend.py`, and the `claude` CLI — nothing else. |
| **B · bounded model call** | **EMPTY. Zero model calls at runtime.** This is the finding, not a shortcut: once the three prose artifacts are supplied by the seat, every remaining step is arithmetic, string placement with an assertion, or a subprocess whose exit code is the answer. No step needed semantic judgment at runtime, so no step got a model. |
| **C · human approval** | The `--gates-passed` ruling; the three prose inputs (`--changelog-file`, `--coord-line`, `--message`); the `--push` and `--install` flags. Five human decisions, all preserved, none of them softened into a default. |
| **D · thin activation** | One `ship` command line. One `replay` command line for the demo tier. Thin means thin. |

Bucket B being empty is the strongest possible compile result *and* the thing to be most
suspicious of — which is why the refuter lane was pointed straight at it (§6) and why the
evidence label is DIRECTIONAL rather than PROVEN (§5).

---

## 4 · Benchmark — Method A, the estate is the historical side

Method A per the doctrine: the old workflow's behavior is what the trail recorded; the
compiled side replays from **equivalent raw inputs at the same point in time**. The replay
harness clones the repo into scratch, puts the worktree at the ship commit with HEAD at its
parent, **removes only what the ritual writes** (version stamps, the changelog section, the
COORD line — nothing else, because the script never owned anything else), extracts that
ship's real inputs from the repo's own history (`git show <sha>:CHANGELOG.md`, the COORD line
from the commit's own diff, `git log -1 --format=%B`, version from the commit's
`plugin.json`), runs the full pipeline without `--push`/`--install`, and diffs against
`git show <sha>:<path>`.

**Fair-input proof:** the compiled side never receives intermediate work the historical seat
had to produce. It receives the same three prose artifacts a human wrote that day plus a
tree at `sha~1`. Additionally, the count surfaces are **de-shipped to their `sha~1` state**,
so reconciliation is a real operation in every replay and not a no-op against already-correct
files.

### Per-scenario results — five historical ships

| # | commit | version | surfaces | differs | drift | verdict |
|---|---|---|---|---|---|---|
| 1 | `f3b148a` | 3.1.0 | 9 | **0** | **3** | **PARITY PASS** |
| 2 | `fbe1e07` | 3.0.0 (the rename ship — the hardest case) | 9 | **0** | 0 | **PARITY PASS** |
| 3 | `4c78590` | 2.17.0 | 9 | **0** | 0 | **PARITY PASS** |
| 4 | `f115695` | 2.16.1 | 9 | **0** | 0 | **PARITY PASS** |
| 5 | `5c422ed` | 2.16.0 | 9 | **0** | 0 | **PARITY PASS** |

Scenarios 3–5 run under `--legacy-paths`, which maps the manifest paths, the skills dir, the
README and `spend.py` to the pre-rename `plugins/oracle-suite/` layout **and** the pre-rename
flow-page vocabulary (`N-skill suite` / `Manifest: oracle-suite`). Pre-rename trees carry no
tombstone entry, so clause 2's pin check correctly skips what is not there. Scenario 2, the
rename ship itself, replays on current paths.

**The `drift=3` row is the most interesting result in the table.** At `f3b148a`, three of the
four spelled count surfaces said "twenty-three" against 24 actual skill directories, and the
repo-root `CLAUDE.md` still said 23 at HEAD. The ritual did not reproduce history — it
**corrected** it, and the correction is established by arithmetic (`git ls-tree` count vs the
word in the file), not by the script's opinion. Drift is reported and counted separately, it
never silences a real difference, and any count difference where history *was* self-consistent
fails as DIFFERS.

### Latency — wall-clock, observed

~1.2s per replayed scenario, decomposed (`--time`):

| stage | ms |
|---|---|
| clone | 290 |
| seed | 48 |
| extract | 58 |
| **ship-pipeline** | **775** |
| parity | 54 |

The **775ms ship-pipeline** figure is the one that corresponds to real work; clone/seed/extract
are replay-harness overhead that a live ship does not pay.

---

## 5 · THE HONESTY SECTION — why the label is DIRECTIONAL, not PROVEN

Five fair scenarios would earn **PROVEN** under the doctrine's table if every metric were
provenance-backed and the surface set were uniformly independent. It is not. Two disclosures:

**(a) Two of the nine surfaces are round-trip identities by construction.** `CHANGELOG.md`
and `COORD.md` are de-shipped by *removing* the section and the line the ritual writes, then
the ritual puts them back. The content is round-tripped, so the comparison proves the
**insertion point, ordering and whitespace** — it cannot prove the prose, and it **cannot
fail**. The tool labels these `round-trip` in its own output for exactly this reason. Read
`IDENTICAL` on those two rows as "placed correctly", never as "reproduced correctly".

**(b) Two surfaces are written but not compared.** The repo-root `README.md` and `CLAUDE.md`
numerals are rewritten by clause 3 and then excluded from the parity set, because no
historical ship kept them in sync — comparing them would fail every replay for a defect that
predates the script. Correct call, but it means clause 3's parity evidence covers 4 of its 6
surfaces.

So: **five fair scenarios, nine compared surfaces, of which two cannot fail and two more of
clause 3's surfaces are uncompared.** The surface set is not uniformly independent.
**Evidence label: DIRECTIONAL.** That belongs on the verdict screen, not in a footnote — and
in this deliverable it is on the verdict screen.

An earlier draft claimed a flat "5/5 PARITY PASS" without either disclosure. The refuter
caught it (R3 below). The honest statement is the one above.

---

## 6 · The refuter lane — 15 findings, all dispositioned

An independent lane (never the builder — agentswarm's review-the-fix law) attacked the
runtime with the brief: find the dropped responsibility, the unbounded model call, the test
that passes without exercising anything, the fixture that hands the compiled side pre-chewed
work, and the benchmark asymmetry. It returned **15 findings, three of them CONFIRMED
criticals.**

### The three confirmed criticals

| id | finding | concrete failure scenario | fix | seat verification |
|---|---|---|---|---|
| **R1** | **Tombstone de-pin.** The version bumper located manifest entries by position/key order. A JSON key reorder made it walk past the live entry and rewrite the `oracle-suite` **tombstone** — which is pinned at 9.0.0 forever — and the run **committed at exit 0**. | Reorder keys in `.claude-plugin/marketplace.json`; ship; the tombstone is now `3.2.0` and the migration stub is broken for every installed user. | Entries located **by name**, never by position or key order; after the write, both files are re-read from disk and re-asserted — all three versions equal the new one, tombstone entry **byte-for-byte unchanged** — before anything is staged (exit 12). | Seat re-ran the repro: reordered-key manifest → **ships correctly, tombstone still 9.0.0**. |
| **R2** | **Validator failure laundered into a skip.** A `claude plugin validate` failure whose stderr happened to contain the substring `not found` was string-matched into "CLI absent → proceed", and the run continued to push/install. | A skill with a missing referenced file makes the validator print `... not found`; the ship interprets a real failure as an absent CLI and pushes a broken plugin to the marketplace. | CLI absence is detected **only** by `FileNotFoundError`. Every run that completes and exits nonzero dies **18** and prints the validator's stderr. | Seat re-ran the repro: validator-fails → `FAIL[18] VALIDATE … rollback: 8 file(s) restored`, **HEAD unmoved**. |
| **R3** | **Overclaimed parity.** The "5/5 PARITY PASS" headline counted round-trip identities and ignored the uncompared count surfaces — a benchmark-asymmetry finding, not a code bug. | A reader takes PROVEN-grade confidence from DIRECTIONAL-grade evidence and installs on that basis. | Parity widened **5 → 9 surfaces**; round-trips labeled as such in the tool's own output; count surfaces de-shipped to `sha~1` so reconciliation is a real operation in every replay; the evidence label demoted to **DIRECTIONAL** with its reason stated on the verdict screen. | This document, §5. |

### The other twelve

Findings 4–15 were returned in the same lane report at non-critical severity. Their
individual texts are not reproduced in this document — that itemization was not carried into
this writer lane and is marked **[unverified here]** rather than paraphrased from memory. What
*is* seat-verified is their **disposition and the fix classes that landed with them**:

- **all 15 fixed in ONE bounded repair round** — the quality law's second and final round; nothing was deferred, nothing was ground past the limit;
- fix classes shipped in that round beyond R1–R3: **atomic writes** (temp file + `os.replace`) with every written path tracked, and **`git checkout --` rollback** of those paths on any abort after the first write (armed for real ships only — never inside a replay scratch, whose HEAD is deliberately the pre-ship commit); **exact-object push** (`<sha>:refs/heads/<branch>`, detached HEAD refused rather than guessed, empty `ls-remote` treated as its own failure); the **checker made wider than the rewriter** for count surfaces, so it flags spelled-count-shaped tokens in counted contexts that the rewriter deliberately refuses to touch (ordinals such as "twenty-sixth") and exits 13 quoting the offending line.

### Seat gate — what the seat re-ran itself, never accepting a lane's self-report

- `bash compile/release-ritual/fixture.sh` → **51/51, exit 0** (exit-code-checked, never piped through `| tail`).
- `py_compile` on `ship.py` → clean.
- All **five** replays re-run at the seat.
- The refuter's **two critical repros** re-run at the seat, both landing as recorded in the table above.

---

## 7 · Known gaps — disclosed, not discovered later

1. **Version monotonicity is unchecked.** `ship --version 3.1.1` on a 3.3.0 tree succeeds. The script asserts internal agreement across manifests, not that the new version is greater than the old one.
2. **Root `README.md` / `CLAUDE.md` numerals are rewritten but never parity-compared** (§5b). Clause 3's evidence covers 4 of 6 surfaces.
3. **The runtime has never executed a real ship.** Everything above is replay-proven. Clauses 10 and 11 — push and install — have run only in replay mode, where they are skipped by construction. Therefore **USE IT is NOT-LIVE-VERIFIED** and **INSTALL IT is described, NOT EXECUTED**.
4. **`--legacy-paths` is a compatibility shim**, exercised on three of five scenarios. It is correct for the shas replayed; it is not a general-purpose historical adapter.

---

## 8 · The one-time compilation cost

Receipted here and **never amortized** — no per-run allocation, no break-even math (the owner
did not ask for any).

| lane | observed opus tokens |
|---|---|
| builder round 1 | 108,400 |
| builder round 2 | 125,790 |
| builder round 3 | 208,275 |
| refuter | 100,027 |
| **total** | **542,492** |

Every lane carried `model: "opus"` explicitly, per the owner's standing policy.

**Spend's own caveat, stated rather than buried:** the ledger covers what the harness exposed.
The main loop's own consumption is **not visible to the model**, and seat orchestration is not
in the number above. **542,492 is not the session's bill** — it is the observed subagent
total, and calling it anything more would be laundering an estimate into an observation.
