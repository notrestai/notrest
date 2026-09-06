# Commission 4.9 · A4 · git credential helper — model: sonnet (tier: bounded; the helper line is given verbatim)

Read COMMON first. Contract: IDENTITY-CONTRACT.md §9 (Auth + the exact helper line), §10 step (2).

**Build** `plugins/notrest/skills/atlas/scripts/atlas_helper.py`:
- `credential_fill(stdin_text, home, hub_host)`: parse git's `key=value` lines; if `protocol=https` and
  `host==hub_host` → return `username=atlas\npassword=<contents of HOME/atlas-token stripped>\n`; any other host or
  a missing token → return `""`. Never print anything else.
- `install(hub_url)`: run `git config --global credential.<hub_url>.helper '<the §9 shell-function line, verbatim>'`
  (hub_url default `https://atlas.not.rest`); return True on exit 0. `uninstall(hub_url)` removes it. `check(hub_url)`:
  runs `git credential fill` with `protocol=https\nhost=<host>\n` and returns True iff username=atlas and a non-empty
  password came back — WITHOUT printing the password (compare length only).
- CLI: `atlas_helper.py fill` (stdin→stdout, the git protocol), `install [--hub URL]`, `uninstall`, `check` (exit 0/1).
- **Fixture isolation:** the fixture must never touch the real `~/.gitconfig`: set `HOME` to a temp dir and
  `NOTREST_HOME` under it for every git call.

**Fixture** `fixture-helper.sh` (new): arms — install writes exactly one `credential.https://atlas.not.rest.helper`
entry (read it back with `git config --global --get`); `git credential fill` for the hub host returns username=atlas
and a password whose length equals the token file's; for `github.com` returns nothing; missing token → empty;
uninstall removes the entry; grep arm: the token value appears in no file under the temp HOME other than the
token file itself (no token in .gitconfig, no token in a URL).

**TOUCH-ONLY:** `atlas_helper.py`, `fixture-helper.sh` (both new). **DONE-WHEN:** `bash plugins/notrest/skills/atlas/scripts/fixture-helper.sh` → exit 0.
