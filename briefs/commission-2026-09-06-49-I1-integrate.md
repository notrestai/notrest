# Commission 4.9 · I1 · integrate token/login/helper into atlas.py — model: opus (tier: judgment; the verifier is a kernel-adjacent surface) — RESUMES lane A2

Read COMMON (incl. Amendments) first. You wrote atlas_token.py; now wire it in. Facts the seat probed:
- Hooks accept the verifier ONLY through its stdout sentinel `notrest-access: ok ring=<12hex> path=<ring>` (atlas.py
  `SENTINEL`, line ~240; estate-root.sh:192-197 matches the substring `notrest-access: ok ring=<12hex of the ring FILE>`;
  atlas-bank-hook.sh:63 matches the prefix). The 12 hex is sha256 of the committed ring file's bytes — it proves atlas.py
  read the same ring the hook hashed, and is independent of HOW the machine was admitted.
- Therefore: **token admission emits the SAME sentinel** with the same ring hash, plus the suffix ` via=token`
  (no sub, no seat — nothing personal on hook stdout). Ring admission emits it unchanged. Hooks need no change.

**Change `plugins/notrest/skills/atlas/scripts/atlas.py` — only these sections:**
1. `cmd_key --check` (and `key_ok` if the hooks' path goes through it): order = (a) `atlas_token.verdict(home)` → ok ⇒ sentinel
   + ` via=token`, exit 0; (b) else the existing ring match (access-key holding `nrk_…`) ⇒ sentinel, exit 0; (c) else exit 7.
   With `--quiet`, stdout is exactly the sentinel line on 0 and nothing on 7 (unchanged contract). When the token verdict fails
   for a reason other than `token: absent` and the ring also fails, `--check` without `--quiet` prints `RED <reason>` on stderr.
   Import atlas_token lazily (only when a token file exists) so the ring path's cost does not grow. Measure both paths (ms).
2. New subcommand `login [--base B] [--home H] [--install-helper]` → `atlas_auth.device_login(...)`, then when `--install-helper`
   (default ON) → `atlas_helper.install(base_url)`; prints the two login lines, then `atlas-token: ok …`, then
   `helper: installed for <host>` ; exit 0 / 7. `NOTREST_HOME` resolution = the amendment.
3. New subcommand `helper --install|--check|--uninstall [--hub URL]` → atlas_helper. Exit 0/1.
4. `key --list` also reports whether a token is present (`token: present (sub=…, exp=…)` / `token: none`) — this is the ONLY
   place a sub is printed, and only without --quiet.
5. SKILL.md: not yours (B3). Docs: not yours.

**Fixture:** extend `plugins/notrest/skills/atlas/scripts/fixture.sh` (the atlas fixture the gate runs) with red-first arms:
token admitted → sentinel with the ring's 12hex and ` via=token`, exit 0 (mint through mockhub.py or the node generator);
ring admitted → sentinel unchanged; both absent → 7 and empty stdout under --quiet; expired token + valid ring → 0 via ring;
expired token + no ring → 7 with `RED exp: expired` on stderr; `login` happy path against mockhub (auto-approve) → token 0600 +
helper installed in a sandboxed HOME (never the real ~/.gitconfig); `helper --check` → 0. The existing 62 arms stay green.

**TOUCH-ONLY:** `atlas.py` (the sections above), `fixture.sh`. **DONE-WHEN:** `bash plugins/notrest/skills/atlas/scripts/fixture.sh`
→ exit 0, `0 failed`; AND `bash plugins/notrest/skills/atlas/scripts/fixture-token.sh` → 0; AND the hooks still admit this Mac:
`bash -c 'echo "{}" | /usr/bin/env CLAUDE_PLUGIN_ROOT=$PWD/plugins/notrest bash plugins/notrest/hooks/estate-root.sh'` exits 0 (state what it printed).
