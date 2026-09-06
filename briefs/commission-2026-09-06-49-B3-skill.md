# Commission 4.9 · B3 · SKILL.md + workshop delta — model: opus (tier: judgment; every command in it must run)

Read COMMON (+Amendments), docs/DOCKET-4.9.md, docs/ATLAS-CONNECT.md. `eval.py check` fails SCRIPT-OWNS-SCANNING because
`plugins/notrest/skills/atlas/SKILL.md` does not name the new scripts. **Rewrite SKILL.md** so it names EVERY shipped file under
skills/atlas: `scripts/atlas.py` (key · login · helper · bank · wire · status, with the exit codes), `scripts/atlas_token.py`,
`scripts/atlas_auth.py`, `scripts/atlas_helper.py`, `scripts/atlas_wire.py`, `scripts/mockhub.py` (fixtures only),
`scripts/vendor/verify_token.py` (vendored; license line; never edited), `scripts/fixture*.sh`, `mcp/server.mjs`,
`mcp/atlas-mcp.sh`, `mcp/fixture-mcp.sh`. State the identity model in ≤ 12 lines (token by the portal, verified offline, the
ring as the owner's break-glass), the ONE egress destination, secrets by path, and the sandbox bound (live hub unproven until
the owner wires it). Every command shown must run as written on this machine (the lint checks the paths; you run the commands).
**Workshop delta:** append to `WORKSHOP-SLIDES.md` a section "4.9 delta — three slides" (Atlas identity; the connect flow;
the read server) in the deck's existing boxed-slide style — do not edit existing slides.
**TOUCH-ONLY:** `plugins/notrest/skills/atlas/SKILL.md`, `WORKSHOP-SLIDES.md`, `plugins/notrest/skills/atlas/references/*` if
you cite them. **DONE-WHEN:** `/usr/bin/python3 plugins/notrest/skills/eval/scripts/eval.py check --root . 2>&1 | grep -c "SCRIPT-OWNS-SCANNING"`
prints 0 FAIL lines for that check (paste the eval SUMMARY line), AND `starthere_lint.py check --file plugins/notrest/skills/atlas/SKILL.md --root .` → 0.
