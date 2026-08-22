# SPEC — the harness/library split (notrest 5.0.0)

> ## ⏸ PARKED 2026-08-21 — not scheduled work
>
> The owner approved this, Round 1 was built and seat-gated, and then it was **parked
> ahead of the workshop**: a breaking 5.0 would change every attendee's install flow
> mid-course. The plugin stays **one product, 31 skills, v4.3.0**.
>
> **Round 1 is preserved on branch `split-5.0-parked` (commit `9ceb051`)** — 37 renames
> at 100% similarity, partition 18/13, doctor exit 5 with zero fails. Do not re-do it.
>
> **Two pieces were worth keeping and are separable from the split** — they deliver the
> owner's actual reason ("if someone is using their own verbs and skills they can keep
> using it") with no version bump and no breaking change:
> 1. `hooks/router.sh` should test that a skill directory exists before nudging, and stay
>    silent when it doesn't. Today it hard-codes 10 verbs. Latent while everything ships
>    together; a real defect the moment anything is unbundled or disabled. Kernel surface —
>    needs a refuter round, and `eval`'s ROUTER check must learn the guarded form.
> 2. The finding-record schema documented as a **public interface**, so a third-party
>    skill can emit a record and be indexed, graphed, and recapped with no notrest verb
>    installed.
>
> Everything below is the original spec, unchanged, for whenever this is revisited.

---

**Owner-approved 2026-08-21**, shape A of three (two plugins, one marketplace).
Owner's stated reason, and the governing constraint of this spec:

> *"i do not want the harness to be the harness and if someone is using their own verbs and
> skills they can keep using it."*

Read as: **the harness must be skill-agnostic.** It has to be fully useful to someone who
installs it alongside their *own* verbs, or no verbs at all. Every design call below is
resolved in favour of that.

## The partition

Computed, not guessed (`graph scan` + per-skill reference audit + a frontmatter measurement,
2026-08-21).

**`notrest` — the harness (18 skills).** The estate, the hooks, the instruments, continuity,
delegation, and the findings store:
`notrest · oracle · sessionend · fable-mode · doctor · eval · spend · graph · recap ·
compile · agentswarm · fable-director · mentor · beam · chatroom · refuter · director ·
archivist`

**`notrest-library` — the knowledge verbs (13 skills).** Everything that makes claims:
`researcher · marketresearcher · factcheck · explainer · decider · critic · draft ·
stepbystep · actionplan · watch · game-forge · gpt · introspect`

### Why `archivist` and the store stay with the harness — settled by evidence, not taste

`archive/findings.jsonl` is consumed by **harness instruments**: `graph.py` (17 references —
the river), `recap/walk.py` (14 — the decision story), `archivist/index.py` (15 — the index).
Two of those three are harness verbs. The store is estate infrastructure of the same kind as
`COORD.md`, and it must survive the library being absent (the instruments already tolerate a
missing file, because estates vary).

This is also what *delivers* the owner's constraint: the finding-record schema becomes the
harness's **public interface**. A third-party skill that emits a valid record is indexed,
graphed, and recapped for free — with no notrest verb installed at all.

### What the verbs actually depended on

Only `findings.jsonl`, in all 13. The `COORD.md` mentions in `decider` and `watch` are
"bank a line when the work lands" — convention, not dependency, and it survives the split
untouched because the hooks own that behaviour, not the skills.

## Version: 5.0.0, and it is breaking

`notrest@notrest` ships 31 verbs today; after the split it ships 18. **An existing consumer
who updates loses 13 skills** unless they also install the library. That is a major version
and it needs a migration line in the CHANGELOG and README:

```
claude plugin marketplace update notrest
claude plugin update notrest@notrest          # now the harness alone
claude plugin install notrest-library@notrest  # the knowledge verbs, if you want them
```

`plugins/oracle-suite-tombstone/` stays pinned at 9.0.0 — **never bump it.**

## Rounds

### Round 1 — the mechanical split (this round)
1. `git mv` the 13 library skills to `plugins/notrest-library/skills/`.
2. New `plugins/notrest-library/.claude-plugin/plugin.json` (v5.0.0) and a matching
   `.codex-plugin/plugin.json` — the 4.3.0 Codex adapter shape, hooks omitted as it does.
3. `.claude-plugin/marketplace.json` gains a second entry; both at 5.0.0; metadata bumped.
4. `plugins/notrest/.claude-plugin/plugin.json` → 5.0.0, skill count 31 → 18.
5. Library `README.md`; harness README/TUTORIAL/CAPABILITIES/UNDERSTANDING counts corrected.

*Done-when R1:* both manifests parse; `doctor.py check --surface claude` names both products
and its SKILL COUNT check agrees across every place the number is written; `eval.py check`
exits 0 over both trees; the harness alone (library dir moved aside) still passes both gates —
**that is the skill-agnostic claim, and it must be proven by exit code, not asserted.**

### Round 2 — the instruments learn there are two products
6. `doctor.py` SKILL COUNT: currently asserts one number across 5 surfaces. It must count
   **per product** and agree per product.
7. `eval.py` RELEASE-SURFACE: 43 surfaces today, all assuming one plugin. Split the surface
   set; a library-only or harness-only tree must still be gradeable.
8. Both fixtures extended: a harness-only tree, a library-only tree, and both-installed.

*Done-when R2:* fixtures prove each shape; a deliberately miscounted product FAILs (watch it
go red); `eval` still green.

### Round 3 — the contract made public
9. `docs/FINDING-RECORD.md`: the record schema as a **documented public interface**, with the
   validator named, so a third-party skill can emit one. This is the round that actually
   delivers the owner's reason for splitting.
10. Library SKILL.md bodies: replace any "the suite" framing that assumes co-installation.

*Done-when R3:* a hand-written record from a fake third-party skill validates, indexes, and
appears in the river and in `recap` — proven end-to-end with no notrest verb involved.

## Constraints (the estate's own laws — violating them fails this spec)

Zero new dependencies (bash + python3 stdlib) · hooks never `set -e`, always `exit 0` ·
append-only files stay append-only · **manifests, `doctor.py`, `eval.py` are kernel surfaces:
a refuter round before this ships** · every claim carries evidence (exit codes, transcripts)
or is labelled unverified · one commit series + one COORD line per round.

## Non-goals

No behaviour change to any skill · no estate migration in consumer projects · no change to
the hook set · no `stage:` frontmatter work · the 4.4 defect docket
(`docs/DOCKET-4.4.md`) is **not** folded in — it ships on its own schedule.

## What must not change

Solo behaviour byte-for-byte · the hook contract · the Codex adapter's honest SKIPs · the
tombstone pin · the always-on ceiling (the split should *reduce* harness-only cost by ~1,552
tokens of library frontmatter — measure it, do not assume it).
