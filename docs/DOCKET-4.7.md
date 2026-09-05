# 4.7 docket — owner-approved 2026-09-05 ("yes i want them all automatic … i agree with all the judgment calls … i love all the 6 additions as well have them build and tested we are shipping 4.7")

Folds in the 4.6.3 learnings loop (in flight). One release: **v4.7.0**. Kernel items (hooks,
establish.py, ledger consumers) ship only through a refuter round.

## A · Learnings loop (from 4.6.3)
Record kind `learning` (INHERITED/RULED/LEARNED, evidence, scope) · `index.py learnings` (digest,
scope, since, triggers --uncited with an ARMING FLOOR = earliest learning evidence ts) · Stop gate
blocks on an uncited trigger (UPPERCASE headline tags; one implementation in index.py) · spawn-gate
injects the scoped digest via `updatedInput` · router one-liner · packet LEARNINGS block · eval
LEARNING-LOOP · doctor ESTATE detail · `add` per-field flags for learnings.

## B · Compiler: everything automatic (owner ruling supersedes "installation owner-gated forever")
1. **Authorization restored + never silently dropped again:** `auto --on` re-run 2026-09-05; the
   4.5.0 move ignored the legacy `compile/.auto-build` without migrating — `auto` and the
   SessionStart hook now WARN when a legacy marker exists and the new one does not.
2. **Draft automatic:** the pulse daemon, after a scan, scaffolds every ripe NEW candidate into its
   isolated `compile/<slug>/` (contract + skeleton + benchmark harness) — zero tokens, unattended.
3. **Build + refuter automatic, UNATTENDED (owner ruling 2026-09-05: "the daemon should spend tokens
   too, make it fully unattended"):** `compile.py auto-run --next` is the pipeline runner the pulse daemon
   calls after a scan: pick the oldest DRAFTED candidate → run the BUILDER as a headless `claude -p
   --model opus --output-format json` with the contract as the prompt → run the REFUTER the same way
   against the built runtime → run the FAIR benchmark (script) → adopt (step 4). Honesty rails, each
   armed: one estate-wide lock (never two runs, never during a live session's own compile); the marker
   carries `unattended: true` and a `daily_cap_tokens` the owner sets (`auto --on --unattended
   --daily-cap N`) — the runner refuses to start a step that would breach it and the refusal is a
   pulse line; every headless run is receipted to spend/ledger.md via `spend.py log` with the observed
   token count from the CLI's JSON result (lane=daemon, model explicit); an auth failure ("not logged
   in") stops the pipeline quietly with one pulse line and no retry storm; the runner is injectable
   (`--runner <cmd>`) so fixtures never spend a token; `NOTREST_UNATTENDED=1` is set on every headless
   run and the hooks honor it: no AUTO-BUILD echo, no lane spawns from inside an unattended run.
4. **Adopt automatic:** fixture green + FAIR benchmark green + refuter CLEAN → `decide --status
   ADOPTED` is written by the seat's gate step with the receipt line; the estate uses the runtime.
   `decide --status DECLINED` revokes. Every step leaves a ledger line.

## C · Archivist expansion
Kinds `open` (what was not tested / did not work, what would close it, owner) and `alternative`
(method, when to try, cost); `result` gains required fields (ran, command, exit) so TESTS is a count
of records; `index.py card` renders TESTS / OPEN / FINDINGS / LEARNINGS with counts; the Stop gate
gains a trigger: a lane return or ledger line saying not tested / could not verify / unverified with
no `open` record behind it.

## D · Lane returns in card form, auto-banked (suggestion 1)
The agentswarm brief template ends every return with the four boxes as a fixed block; the
agent-ledger hook parses it and banks each item as a record (result/open/finding/learning) with the
lane id as source and the brief path as evidence. A lane that forgot to bank cannot exist.

## E · Lessons travel (suggestion 2)
A learning with scope `library` is promoted to `~/.claude/notrest-library` (the shelf index.py
already has); every estate's packet carries the library's newest learnings.

## F · Learnings compile (suggestion 3)
`compile scan` reads learning + open records alongside the ledgers; a lesson recurring three times
becomes a candidate of kind `rule` (a hook arm or an eval check) and enters the same pipeline.

## G · Open questions on watch (suggestion 4)
`open` records carry a re-check date; `watch.py due` lists them; closing one writes the closing
record and cites the open id.

## H · Loop health in doctor (suggestion 5)
One WARN line: uncited triggers, open records by age, learnings per week, candidates drafted but
undecided.

## I · Commission done-when becomes the Stop contract (suggestion 6)
The spawn gate reads a `DONE-WHEN:` / `CHECK:` block from the Agent prompt and appends the gates to
`gates/ACTIVE.md` under the lane id; the completion gate runs them; agent-ledger retires them when
the lane returns.
