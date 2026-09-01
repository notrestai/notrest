# 4.4 docket — owner-approved 2026-08-21

> **Naming note (2026-08-31):** v4.4.0 shipped without these items (it carried the
> owner's hardening sweep + the ship-gate battery fixes). Everything below now
> targets the next kernel round (4.5+). Content unchanged.

Source: the two v4.3.0 ship-time refuter rounds (finding lane + review-the-fix lane, both
transcripts under `briefs/`; ship `f6aab09`). Owner approved docketing 2026-08-21. Items 1,
4, 5 touch `establish.py` — **kernel: each ships only through a refuter round.**

## 1 · F2 — `--surface auto` picks the runtime by files, not by host — NEEDS OWNER RULING
A Claude session in a repo carrying an upstream `AGENTS.md` and no `CLAUDE.md` establishes
the **wrong runtime's** foundation and exits 0 ESTABLISHED (confirmed live). Neither
`CLAUDE_PLUGIN_ROOT` nor `CLAUDE_CONFIG_DIR` is exported in a real Claude session, so the
env branch is dead there and the file tie-break governs.
**Ruling needed at 4.4 kickoff — options:**
- (a) file tie-break may only *narrow within* a host detected by signals; no signal → claude (today's stated default, actually enforced)
- (b) `auto` on an undetected host never writes a *new* surface file — it reports and asks for `--surface`
- (c) drop `auto`; explicit-only
Until ruled: use explicit `--surface` on mixed repos (disclosed in the ship notes).

## 2 · F3 — the report escapes the root (inherited, both-surface amplified)
`foundation_state()` follows an escaping symlink and `grade()` ignores `failures`: a run
can print `ESTABLISHED · wrote: nothing (writes failed: AGENTS.md) · exit 0` — PASS
asserted from a file *outside* the root, exit 0 on a refused write, and a `wrote:` tail
that is false about real writes. Write containment itself held. Fix = grade consults
failures + state checks refuse escaping paths, same containment the writers already use.

## 3 · F4 — `atomic_write` discards the target's mode (inherited)
`mkstemp` + `os.replace` resets every foundation file to 0600 and rewrites files the owner
marked read-only. Fix = stat before, `os.chmod` the temp to match (or refuse on read-only),
and stop printing "existing content untouched" when the *file* changed.

## 4 · Case-variant bypass of the whole home-refusal family (pre-existing since 4.0)
On case-insensitive volumes (macOS default), `--root /users/…` defeats `$HOME`, Desktop,
and the new dot-dir refusals — string compares, not identity compares. Fix = an
`os.path.samefile`-based predicate (inode identity) across the family, with its own
refuter round; the review lane's transcripts carry the repro commands.

## 5 · F5 — vacuous fixture arm
`fixture.sh` "Codex runtime variable selects Codex automatically" asserts only exit 0 and
survives a killed `detect_surface` codex branch (mutation-proven). Re-point it at the
property (which file was written), like its two honest neighbours.

## 6 · F6 — no hostile `AGENTS.md` corpus
The F-12(a) hostile corpus (non-UTF-8, CRLF, fenced-example markers, duplicate/unterminated
markers, escaping symlink, read-only, partial `both`) runs against `CLAUDE.md` only. Clone
it for `AGENTS.md`; findings 2-3 above sit in exactly that gap.

## Also carried
- Cross-runtime pickup ritual made explicit in the notrest SKILL continuation section
  (`--surface both` as the one-time bridge; Codex takes the files-only mentor fallback;
  no hooks on Codex → the agent banks its own COORD lines). Two paragraphs, no new skill.
