# Commission 4.9 · A6 · hooks — model: opus (tier: judgment; KERNEL SURFACE — refuter round before ship)

Read COMMON first. Contract: IDENTITY-CONTRACT.md §2 (refresh at SessionStart), §4 (revoked cached at SessionStart),
§1 (login command name). CLAUDE.md "KERNEL SURFACES". The hook fixture lives wherever `eval.py check` and the
hooks currently prove themselves — find it (grep for the hook names under plugins/notrest/skills/eval and
plugins/notrest/hooks) and extend THAT, never a new harness.

**Change** `plugins/notrest/hooks/session-start.sh` only:
1. The keyless banner (line ~27) becomes ONE line naming the remedy:
   `[notrest] notrest is part of Atlas — no Atlas identity on this machine. Log in:  python3 <abs hookdir>/../skills/atlas/scripts/atlas_auth.py login   (or place the owner's access key). The harness is inactive here.`
   Keep every other property (single line, stderr budget, exit code).
2. When the key check passes AND `${NOTREST_HOME:-~/.notrest}/atlas-token` exists: run
   `/usr/bin/python3 <hookdir>/../skills/atlas/scripts/atlas_auth.py sessionstart --budget-ms 2000` in the background
   of the hook (`( … ) >/dev/null 2>&1 &` with `disown`, or with a hard `timeout`-equivalent since macOS has no
   `timeout`) so the hook's own wall-clock does not grow by more than ~20 ms; nothing on stdout; fail-open silent.
   A3 delivers `atlas_auth.py`; until it exists, the call must be a no-op (test `-f` first).
3. Do NOT change `key --check` call sites or the verifier (the seat wires token acceptance into atlas.py).
Read `estate-root.sh` and `atlas-bank-hook.sh` only to confirm they need no change; say so in your return.

**Fixture arms** (red-first, in the existing hook fixture): banner text exact when keyless; with a fake atlas-token
file and no network the hook still exits within its budget (measure: before/after ms, report both); with
`atlas_auth.py` absent, no error; stdout byte-identical to before in the keyed case; `eval.py check --root .` exit 0
and `doctor.py check` ≤ 5 after your change.

**TOUCH-ONLY:** `plugins/notrest/hooks/session-start.sh`, the existing hook fixture file(s), `plugins/notrest/hooks/README*` if one documents the banner.
**DONE-WHEN:** the hook fixture → exit 0 AND `/usr/bin/python3 plugins/notrest/skills/eval/scripts/eval.py check --root .` → exit 0.
