# Commission 4.9 · I2 · swap the http push into atlas.py — model: opus — RESUMES lane A5

Read COMMON (+Amendments). I1 landed (atlas.py now has login/helper; the key section is done — do not touch it).
**Change `atlas.py` — only:** `push_http` (line ~784) delegates to `atlas_wire.push_http` after `atlas_wire.to_wire`
(project from `atlas/config.json` `"project"`, else the estate slug; base from config `"hub"` else `ATLAS_HUB_BASE` else the
default; board_url = `<base>/v1/board/<project>`); `credential_for(cfg, "http")` resolves `HOME/credentials/atlas-ingest-<project>`
(legacy `credentials/atlas-token` with the one warning; config `"credential"` overrides); `cmd_status` treats a 201 receipt as
pushed and says `pushed <head>; the hub reflects it within ~2 min` instead of calling a fresh mismatch red before 120 s.
`bank` exit codes unchanged (0 green · 3 nothing to derive · 4 push failed · 5 board red). Sources map may add `gates`.
**Fixture:** `fixture.sh` arms: `bank` with adapter http against mockhub → 0, hub_commit == head, board pushed; replay →
idempotent; bad bearer → exit 4 with the hub's fact verbatim; legacy credential name → one warning; the ingest value never in
any output. **TOUCH-ONLY:** atlas.py (those functions), fixture.sh. **DONE-WHEN:** `bash …/fixture.sh` → 0 AND `bash …/fixture-wire.sh` → 0.
