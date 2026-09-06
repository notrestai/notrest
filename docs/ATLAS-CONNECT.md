# Connect Claude Code to Atlas

The hub serves this page verbatim and the Atlas MCP tool `atlas_connect` returns it. Path A is for a machine with a browser; path B is for a headless one. Inside a path the order is load-bearing: the credential helper goes in before any marketplace command, because Claude Code clones a marketplace with the system git, which knows nothing about the plugin.

## A · Claude Code with a browser

1. **Write the token** `atlas_connect` returned — paste it, press Return, then Ctrl-D; `printf '%s'` leaves no trailing newline, which the hub would reject as part of the bearer, and `umask 077` makes the directory 0700 and the file 0600.

```bash
umask 077 && mkdir -p "${NOTREST_HOME:-$HOME/.notrest}" && printf '%s' "$(cat)" > "${NOTREST_HOME:-$HOME/.notrest}/atlas-token" && chmod 600 "${NOTREST_HOME:-$HOME/.notrest}/atlas-token"
```

2. **Install the host-scoped credential helper** — git now answers for the hub host only, reading the token from that file, so the token never enters a URL, a config value, or the clone command, and it declines, printing nothing, when the token file is absent, so git never sends an empty password.

```bash
git config --global credential.https://atlas.not.rest.helper '!f(){ t="${NOTREST_HOME:-$HOME/.notrest}/atlas-token"; [ -r "$t" ] || exit 0; echo username=atlas; echo "password=$(tr -d "\r\n" < "$t")"; }; f'
```

3. **Add the hub as a plugin marketplace** — this clone is the first thing the helper authenticates; run it before step 2 and git prompts for a password and fails.

```bash
claude plugin marketplace add https://atlas.not.rest/git/notrest.git
```

4. **Install the plugin** from that marketplace — the id is plugin-at-marketplace, and both names are `notrest`.

```bash
claude plugin install notrest@notrest
```

5. **Verify the identity offline** — a marketplace install lands under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>`, so the globs below resolve the installed version and the script; expect `atlas-token: ok sub=… seat=… exp=…` and exit 0, where a `RED` line and exit 7 mean no valid token on this machine.

```bash
python3 ~/.claude/plugins/cache/notrest/notrest/*/skills/atlas/scripts/atlas_token*.py check
```

6. **Open a new session** in your project — its first line reads `[notrest] v4.9.0 …`, and from then on the session's own trail is `COORD.md` in that project.

## B · Headless — a NAS or a container

There is no login before the plugin exists, so a token pasted from the portal carries the clone, and the plugin's own login replaces it once installed.

1. **Write the token** the portal showed once after you entered your code at https://atlas.not.rest/activate — it is `roaming` scope, so it verifies on a machine whose fingerprint the hub has never seen.

```bash
umask 077 && mkdir -p "${NOTREST_HOME:-$HOME/.notrest}" && printf '%s' "$(cat)" > "${NOTREST_HOME:-$HOME/.notrest}/atlas-token" && chmod 600 "${NOTREST_HOME:-$HOME/.notrest}/atlas-token"
```

2. **Install the host-scoped credential helper** — same line, same reason, still before the marketplace command, and it declines, printing nothing, when the token file is absent, so git never sends an empty password.

```bash
git config --global credential.https://atlas.not.rest.helper '!f(){ t="${NOTREST_HOME:-$HOME/.notrest}/atlas-token"; [ -r "$t" ] || exit 0; echo username=atlas; echo "password=$(tr -d "\r\n" < "$t")"; }; f'
```

3. **Add the hub as a plugin marketplace** — the helper answers the clone with the pasted token.

```bash
claude plugin marketplace add https://atlas.not.rest/git/notrest.git
```

4. **Install the plugin** from that marketplace.

```bash
claude plugin install notrest@notrest
```

5. **Run the device login** from the installed plugin — it prints a URL and a code for any browser you have, waits for the approval, and rewrites the same file with a token bound to this machine's fingerprint (`mid`), which the roaming one is not.

```bash
python3 ~/.claude/plugins/cache/notrest/notrest/*/skills/atlas/scripts/atlas[.]py login
```

6. **Verify the identity offline** — expect `atlas-token: ok sub=… seat=… exp=…` and exit 0, now with this machine's own `mid`; a session opened after this prints `[notrest] v4.9.0 …` and keeps its trail in `COORD.md`.

```bash
python3 ~/.claude/plugins/cache/notrest/notrest/*/skills/atlas/scripts/atlas_token*.py check
```

## What must never happen

- A token in a URL. Basic auth through the helper is the only path; a token in a clone URL is logged by every proxy it crosses and is written into the repo's git config.
- A token in a commit. The token file lives outside every repository, and nothing tracked ever holds its value.
- The marketplace command before the helper. The clone runs as the system git; without the helper it prompts, fails, and leaves a half-added marketplace behind.
- Two machines sharing one token file. Outside `roaming` scope a token names one machine's fingerprint, so a copied file fails verification on both — each machine logs in for itself.

## What you will see

Exit codes are the plugin's: `0` ok · `7` no valid key or token · `5` red · `6` nothing established, or HEAD not banked.

Until a token is in place every hook is silent and a session prints this one line, carrying the absolute path of your installed copy where the glob stands here:

```
[notrest] notrest is part of Atlas — no Atlas identity on this machine. Log in:  python3 ~/.claude/plugins/cache/notrest/notrest/*/skills/atlas/scripts/atlas[.]py login   (or place the owner's access key). The harness is inactive here.
```
