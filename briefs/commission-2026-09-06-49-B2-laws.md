# Commission 4.9 · B2 · the laws catch up — model: opus (tier: judgment; eval is the law suite)

Read COMMON first, then docs/DOCKET-4.9.md ("Board state during the build" + the B2 row). Facts: `eval.py check --root .`
exits 6 today on NETWORK-EGRESS (atlas_auth.py, atlas_wire.py, mockhub.py) and SCRIPT-OWNS-SCANNING (SKILL.md naming — B3's,
NOT yours; leave those FAILs alone and say so).

**AMEND NETWORK-EGRESS in `plugins/notrest/skills/eval/scripts/eval.py` (ID at line ~801):** 4.9 deliberately changes the
no-egress promise. The amended law, stated in the check's own docstring/description so eval prints the rationale:
- The ONE permitted external destination is the Atlas hub: `ATLAS_HUB_BASE` env with default `https://atlas.not.rest`.
- Permitted ONLY from the named modules: `skills/atlas/scripts/atlas_auth.py`, `skills/atlas/scripts/atlas_wire.py`, and
  `skills/atlas/scripts/atlas.py` (its push path). Any other shipped script or hook naming a non-loopback URL/host is a FAIL.
- Loopback-bound servers are allowlisted by their bind (`127.0.0.1`/`localhost`): `mockhub.py` and any `--selftest`.
- Hooks never egress synchronously: `session-start.sh` may only INVOKE `atlas_auth.py sessionstart` in the background;
  a hook that calls `curl`/`urllib`/`fetch` inline is a FAIL. Encode this as its own arm.
- Compiled runtimes: unchanged (none at all).
Red-first: the eval fixture (find where eval proves itself — its own fixture/arms) gets arms: a scratch script under
skills/atlas/scripts naming `https://example.com` → FAIL; the same URL in `atlas_auth.py` → PASS; a hook with an inline
`curl https://atlas.not.rest` → FAIL; `mockhub.py` binding 127.0.0.1 → PASS.

**New eval checks (each red-first):** `TOKEN-STORE` — every code path that writes `atlas-token` sets mode 0600 (grep-level:
`os.chmod(..., 0o600)`/`umask` adjacent to the write in atlas_auth.py; a mutant without it fails); `HELPER-SCOPE` — the only
`credential.*.helper` config the plugin writes is host-scoped to the hub (no bare `credential.helper`); `VERIFIER-VENDORED` —
`skills/atlas/scripts/vendor/verify_token.py` exists, line 1 carries the Atlas license line, sha256 equals
`briefs/atlas-contract/kit/verify-token.py`; `NO-TOKEN-LITERAL` — no file under plugins/notrest contains a three-segment
base64url string with an `{"alg":"EdDSA"` header (a signed token), and no `nrk_` key literal.

**Doctor:** none (A9 added the MCP check; the seat may ask later).

**TOUCH-ONLY:** `eval.py`, eval's own fixture, `evals/**` (arms only — NOT the golden release-surface list, that is the ship's).
**DONE-WHEN:** `/usr/bin/python3 plugins/notrest/skills/eval/scripts/eval.py check --root .` exits 6 with ONLY the
SCRIPT-OWNS-SCANNING FAILs remaining (paste them) — i.e. NETWORK-EGRESS green and the four new checks green; AND eval's own
fixture → exit 0. State the count of checks before/after (17 → 21).
