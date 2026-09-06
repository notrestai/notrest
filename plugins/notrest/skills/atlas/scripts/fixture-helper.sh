#!/bin/bash
# fixture-helper.sh — asserts atlas_helper.py against a SCRATCH HOME in a mktemp dir.
#
# It never touches the real ~/.gitconfig: HOME is repointed at a directory under
# mktemp for every git call this script or atlas_helper.py's subprocesses make, and
# NOTREST_HOME is repointed under that same scratch HOME. GIT_CONFIG_NOSYSTEM is set
# too, so a machine-wide /etc/gitconfig (e.g. a system credential.helper) cannot
# decide anything here. The token is a throwaway generated fresh for this run — never
# a real credential — and the fixture proves, by grep, that its value never lands
# anywhere under the scratch HOME except the one file it belongs in.
#
# Usage: bash <atlas-skill>/scripts/fixture-helper.sh   (exit 0 = every assertion held)
#
# ATLAS_HELPER_PY overrides the script under test — red-first: a new arm must be
# shown to FAIL against the previous revision before it is trusted to pass here.
set -u
unset GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM
unset XDG_CONFIG_HOME
H="${ATLAS_HELPER_PY:-$(cd "$(dirname "$0")" && pwd)/atlas_helper.py}"
W="$(mktemp -d)"
cleanup(){ chmod -R u+w "$W" 2>/dev/null; rm -rf "$W"; return 0; }
trap cleanup EXIT

PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }

# ── isolation: every git call below must land in the scratch HOME, never the real one ──
export HOME="$W/home"
mkdir -p "$HOME"
export NOTREST_HOME="$HOME/.notrest"
mkdir -p "$NOTREST_HOME"
export GIT_CONFIG_NOSYSTEM=1
git config --global user.name  "atlas helper fixture" >/dev/null 2>&1
git config --global user.email "fixture@notrest.local" >/dev/null 2>&1
git config --global init.defaultBranch main >/dev/null 2>&1
export GIT_TERMINAL_PROMPT=0

HUB="https://atlas.not.rest"
HUB_HOST="atlas.not.rest"
EXPECT_LINE='!f(){ t="${NOTREST_HOME:-$HOME/.notrest}/atlas-token"; [ -r "$t" ] || exit 0; echo username=atlas; echo "password=$(tr -d "\r\n" < "$t")"; }; f'
TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
TOKEN_FILE="$NOTREST_HOME/atlas-token"
printf '%s\n' "$TOKEN" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"

echo "atlas_helper fixture · $H"

# ── A · install writes exactly one credential.<hub>.helper entry ──────────────────
echo "── A · install"
python3 "$H" install >/dev/null 2>&1
t "install exits 0" "$?" "0"
CNT="$(git config --global --get-all "credential.$HUB.helper" 2>/dev/null | wc -l | tr -d ' ')"
t "install writes exactly one helper entry" "$CNT" "1"
GOT="$(git config --global --get "credential.$HUB.helper" 2>/dev/null)"
t "helper entry matches the §9 line verbatim" "$GOT" "$EXPECT_LINE"
python3 "$H" install >/dev/null 2>&1
CNT2="$(git config --global --get-all "credential.$HUB.helper" 2>/dev/null | wc -l | tr -d ' ')"
t "install is idempotent — still exactly one entry" "$CNT2" "1"

# ── B · git credential fill for the hub host, token present ───────────────────────
echo "── B · fill (hub host, token present)"
FILL_HUB="$(printf 'protocol=https\nhost=%s\n\n' "$HUB_HOST" | timeout 5 git credential fill 2>/dev/null)"
USER_LINE="$(echo "$FILL_HUB" | grep '^username=')"
PASS_LINE="$(echo "$FILL_HUB" | grep '^password=')"
t "fill returns username=atlas for the hub host" "$USER_LINE" "username=atlas"
GOT_PASS_LEN="$(( ${#PASS_LINE} - 9 ))"   # strip the literal "password=" prefix (9 chars)
WANT_PASS_LEN="${#TOKEN}"
t "fill's password length equals the token file's" "$GOT_PASS_LEN" "$WANT_PASS_LEN"
FILL_HUB_CLI="$(printf 'protocol=https\nhost=%s\n\n' "$HUB_HOST" | python3 "$H" fill)"
t "atlas_helper.py fill (python path): hub host also gets credentials" \
  "$(echo "$FILL_HUB_CLI" | grep -c '^username=atlas$')" "1"

# ── C · git credential fill for an unrelated host ──────────────────────────────────
echo "── C · fill (github.com — must get nothing)"
FILL_GH="$(printf 'protocol=https\nhost=github.com\n\n' | timeout 5 git credential fill 2>/dev/null)"
t "fill for github.com returns nothing" "$FILL_GH" ""
FILL_GH_CLI="$(printf 'protocol=https\nhost=github.com\n\n' | python3 "$H" fill)"
t "atlas_helper.py fill (python path): github.com returns empty" "$FILL_GH_CLI" ""

# ── D · check() round-trips true while token + helper are both present ────────────
echo "── D · check (installed, token present)"
python3 "$H" check >/dev/null 2>&1
t "check exits 0 with helper installed and token present" "$?" "0"
CHECK_OUT="$(python3 "$H" check 2>&1)"
case "$CHECK_OUT" in
  *"$TOKEN"*) no "check must never print the password — found it in check's own output" ;;
  *) ok "check's output never contains the token value" ;;
esac

# ── E · missing token ───────────────────────────────────────────────────────────────
echo "── E · missing token"
mv "$TOKEN_FILE" "$TOKEN_FILE.bak"
FILL_MISSING_REAL="$(printf 'protocol=https\nhost=%s\n\n' "$HUB_HOST" | timeout 5 git credential fill 2>/dev/null)"
t "installed helper declines outright (no username, no password) when the token file is missing" \
  "$FILL_MISSING_REAL" ""
FILL_MISSING_CLI="$(printf 'protocol=https\nhost=%s\n\n' "$HUB_HOST" | python3 "$H" fill)"
t "atlas_helper.py fill: missing token returns empty" "$FILL_MISSING_CLI" ""
python3 "$H" check >/dev/null 2>&1
t "check exits nonzero when the token is missing" "$?" "1"
mv "$TOKEN_FILE.bak" "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"

# ── F · uninstall removes the entry ─────────────────────────────────────────────────
echo "── F · uninstall"
python3 "$H" uninstall >/dev/null 2>&1
t "uninstall exits 0" "$?" "0"
git config --global --get "credential.$HUB.helper" >/dev/null 2>&1
t "uninstall removes the helper entry" "$?" "1"
python3 "$H" check >/dev/null 2>&1
t "check exits nonzero once uninstalled" "$?" "1"

# ── G · the token value appears nowhere under the scratch HOME but its own file ────
echo "── G · no leak of the token value under HOME"
HITS="$(grep -arl -- "$TOKEN" "$HOME" 2>/dev/null | grep -v -- "^$TOKEN_FILE\$")"
if [ -z "$HITS" ]; then
  ok "token value found in no file under HOME other than the token file"
else
  no "token value leaked into: $HITS"
fi

echo
echo "atlas_helper fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
