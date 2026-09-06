# Commission 4.9 · B4 · mechanical docs — model: sonnet (tier: bounded; the content is given, the lint is the judge)

Read COMMON, docs/DOCKET-4.9.md (the one-paragraph change + rulings), docs/ATLAS-CONNECT.md, briefs/atlas-contract/RULINGS-2026-09-06.md.
Edit with the Write/Edit tools, never by piping the consumer install commands through Bash (the gate refuses them).
1. `CHANGELOG.md`: a top entry `## 4.9.0 — unreleased` (the ship stamps the date) listing: portal-issued Atlas identity token
   (EdDSA, verified offline with the vendored RFC 8032 verifier), `atlas.py login` (device flow) and `helper`, the ring kept as
   the owner's break-glass, the snapshot→atlas-hub/1 wire and http push by ingest secret, the Atlas MCP read server inside the
   plugin (`.mcp.json`), the SessionStart identity refresh, the amended NETWORK-EGRESS law (one destination), the connect text.
   Bounds: live hub unproven (sandbox), Linux machine-id branch unexercised, pinned JWKS empty until Atlas publishes its key.
2. `README.md`: the version table row stays 4.8.1 (the ship bumps it); add a short "Atlas identity" section pointing at
   docs/ATLAS-CONNECT.md and stating the one egress destination and secrets-by-path.
3. `NOTREST-ON-THE-NAS.md` → v2: replace the hand-carried access-key install with the connect flow (link docs/ATLAS-CONNECT.md,
   path B), keep the ingest-secret paragraph updated to `credentials/atlas-ingest-<project>` per the RULINGS, keep the hub-owes list
   updated (the contract arrived; the hub phases I-A..I-C are Atlas's), keep "no secrets in this file".
4. `docs/MAP.md`: rows for docs/ATLAS-CONNECT.md, docs/DOCKET-4.9.md, briefs/atlas-contract/, the new atlas scripts and mcp dir.
**TOUCH-ONLY:** those four files. **DONE-WHEN:** `starthere_lint.py check --file <f> --root .` → 0 for each of the four (paste the 4 rcs).
