# Commission 4.9 · C1 · REFUTER — model: opus (tier: judgment) — read-only on the tree; the kernel law's round

Read COMMON (+Amendments), docs/DOCKET-4.9.md, CLAUDE.md "KERNEL SURFACES", the contracts under briefs/atlas-contract/, and
then the SURFACES: `plugins/notrest/hooks/session-start.sh` (+estate-root.sh, atlas-bank-hook.sh as callers), `atlas.py`
(key/login/helper/push sections), `atlas_token.py`, `atlas_auth.py`, `atlas_helper.py`, `atlas_wire.py`, `vendor/verify_token.py`
(vendored — attack its USE, not its math), `mcp/atlas-mcp.sh`, `.mcp.json`, `eval.py`'s NETWORK-EGRESS + 4 new checks.
**Attack, do not build.** Questions to answer with evidence (a command and its exit code / output), never with opinion:
- Can a machine be admitted without a valid token or ring? (alg none, foreign key, expired, revoked-after-cache, wrong mid,
  a JWT placed in access-key, a symlinked token file, a token with `\r\n`, an empty JWKS cache, a JWKS cache with a
  non-Ed25519 key first, clock skew edges at exactly 60 s.)
- Can a hook be made to wait, leak, or print a secret? (sessionstart hung, atlas_auth.py replaced by a symlink, NOTREST_HOME
  with a literal `~`, stderr budget, the banner under a 100-char hookdir, a hookdir with spaces.)
- Can the credential helper answer for a host other than the hub, or with an empty password, or put a token in argv/URL?
- Can the push send finding text, a `blocked`/`passed` vocabulary, a >2 MiB body, or an `evidence:proven` without a check?
  Can a rejected push be mistaken for a green bank? Can `status` call a fresh push red inside 120 s?
- Can the law be fooled? (a new script naming a second host in a comment vs code; a hook backgrounding a curl to a second
  host; a `.mjs` under mcp/ with a second host; a token literal split across lines.)
- Is anything claimed live that is only mock-proven? (grep the docs and SKILL.md for "live", "connected", "verified".)
**Verdict format:** `VERDICT: CLEAN` or `NOT CLEAN — n BLOCKERS, n DEFECTS, n NITS`, each finding as
`file:line · one fact · the reproducing command · exit code`. BLOCKER = admission/secrecy/law bypass; DEFECT = a wrong
answer; NIT = a wording. No fixes, no edits. **TOUCH-ONLY:** nothing (read-only; scratch copies in $TMPDIR only).
