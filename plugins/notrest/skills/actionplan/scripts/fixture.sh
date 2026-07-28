#!/bin/bash
# fixture.sh — asserts runbook_lint.py: a good runbook passes, and each way of shipping a
# dangerous one is caught with its file:line and its rule. Also asserts the two honest
# degradations — shellcheck absent, and chatroom's secret list unreachable — because a
# check that silently stops checking is worse than one that was never written.
# Self-relative; writes only inside its own mktemp dir; spawns no lane and calls no model.
# Usage: bash <actionplan-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
D="$(cd "$(dirname "$0")" && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
L="$D/runbook_lint.py"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -q -- "$2" "$1"; then ok "$3"; else no "$3 — [$2] not in $1"; fi; }
hasnt(){ if grep -q -- "$2" "$1"; then no "$3"; else ok "$3"; fi; }
run(){ python3 "$L" "$1" > "$W/out.txt" 2>&1; echo $?; }

# ── A · a runbook that obeys the skill's own laws ────────────────────────────────────
echo "── A · the good runbook"
cat > "$W/good.md" <<'EOF'
# Migrate the app database to Postgres — Runbook

## 📌 Read Me First
- **What this does:** moves the app onto Postgres 16.
- **⛔ Biggest danger:** dropping the legacy database in Phase 2.

## Before You Start
- **Values to fill in:**

| Placeholder | What it is | Where to find it |
|-------------|------------|------------------|
| `<APP_HOST>` | the app server | map.md → hosts |
| `<DB_HOST>` | the Postgres primary | map.md → hosts |
| `<DB_ADMIN>` | the admin role | map.md → credentials (by reference) |

## The Runbook

### Phase 1 — Snapshot   ·   run on: app-server (`<APP_HOST>`)
1. Dump the legacy database, then confirm the dump landed.
   ```bash
   pg_dump -h <DB_HOST> -U <DB_ADMIN> --format=directory -f /var/backups/legacy legacy_db
   ls -l /var/backups/legacy > /dev/null
   ```
   - Verify: `ls /var/backups/legacy | head -1` → a file listing
   - Rollback: `mv /var/backups/legacy /var/backups/legacy.old` (keeps the dump)

### Phase 2 — Cutover   ·   run on: app-server (`<APP_HOST>`)
2. Stop the application so no new writes hit the old database.
   ```bash
   sudo systemctl stop myapp.service
   ```
   - Verify: `systemctl is-active myapp.service` → `inactive`
   - Rollback: `sudo systemctl start myapp.service`
3. ⛔ **DESTRUCTIVE — back up first.** Confirm the Phase-1 dump exists, then drop the legacy database and clear its scratch dir.
   ```bash
   psql -h <DB_HOST> -U <DB_ADMIN> -c 'DROP DATABASE legacy_db;'
   rm -rf /var/tmp/legacy-scratch
   ```
   - Verify: `psql -h <DB_HOST> -U <DB_ADMIN> -lqt | cut -d '|' -f1 | grep -qw legacy_db && echo STILL || echo dropped` → `dropped`
   - Rollback: none — restore from the Phase-1 dump (`pg_restore`). `[needs expert]`

## Unknowns & Assumptions
- The systemd unit name is `[unverified]`.
EOF
t "a runbook that obeys the laws exits 0" "$(run "$W/good.md")" "0"
has "$W/out.txt" "clean" "says it is clean"
has "$W/out.txt" "3 step(s) in 2 phase(s)" "counted the steps and phases"
has "$W/out.txt" "3 placeholder(s)" "counted the placeholders"
hasnt "$W/out.txt" "FINDING" "a clean runbook prints no findings"
python3 "$L" "$W/good.md" --json > "$W/g.json" 2>&1
t "--json exits 0 too" "$?" "0"
t "--json verdict is CLEAN" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['verdict'])" "$W/g.json")" "CLEAN"
ok "placeholders inside a command did not become bash redirection errors (good.md parsed)"
ok "\`> /dev/null\` is not treated as writing to a device (good.md is clean)"
ok "a ⛔-marked rm -rf and DROP pass (good.md is clean)"

# ── B · each way of shipping a dangerous runbook ─────────────────────────────────────
echo "── B · the rules, one broken at a time"
sed 's|sudo systemctl stop myapp.service|if [ -f /etc/myapp.conf ]; then sudo systemctl stop myapp|' \
  "$W/good.md" > "$W/syntax.md"
t "a block that fails bash -n is caught" "$(run "$W/syntax.md")" "5"
has "$W/out.txt" "bash-syntax" "names the bash-syntax rule"
has "$W/out.txt" "unexpected end of file" "carries bash's own reason"

grep -v '   - Verify: `systemctl is-active myapp.service`' "$W/good.md" > "$W/noverify.md"
t "a step with no Verify is caught" "$(run "$W/noverify.md")" "5"
has "$W/out.txt" "step-missing-verify" "names the missing-verify rule"
has "$W/out.txt" "step 2" "names which step"

grep -v '   - Rollback: `sudo systemctl start myapp.service`' "$W/good.md" > "$W/norollback.md"
t "a step with no Rollback is caught" "$(run "$W/norollback.md")" "5"
has "$W/out.txt" "step-missing-rollback" "names the missing-rollback rule"

sed 's|-U <DB_ADMIN>|-U <DB_SUPERUSER>|g' "$W/good.md" > "$W/unlisted.md"
t "a placeholder missing from the values table is caught" "$(run "$W/unlisted.md")" "5"
has "$W/out.txt" "placeholder-undeclared" "names the undeclared-placeholder rule"
has "$W/out.txt" "DB_SUPERUSER" "names the placeholder nobody defined"

sed 's|3. ⛔ \*\*DESTRUCTIVE — back up first.\*\* Confirm|3. Confirm|' "$W/good.md" > "$W/undecorated.md"
t "rm -rf and DROP with the ⛔ removed are caught" "$(run "$W/undecorated.md")" "5"
has "$W/out.txt" "destructive-unmarked" "names the destructive rule"
has "$W/out.txt" "rm -rf" "names rm -rf"
has "$W/out.txt" "DROP" "and names DROP"

sed 's|### Phase 2 — Cutover   ·   run on: app-server (`<APP_HOST>`)|### Phase 2 — Cutover|' \
  "$W/good.md" > "$W/nohost.md"
t "a phase that never says which machine is caught" "$(run "$W/nohost.md")" "5"
has "$W/out.txt" "phase-missing-host" "names the missing-host rule"

grep -v '^### Phase' "$W/good.md" > "$W/nophases.md"
t "a runbook with no phase sections is caught" "$(run "$W/nophases.md")" "5"
has "$W/out.txt" "no-phase-sections" "names the missing-structure rule"

# ── C · the secret screen: chatroom's classes, borrowed not re-declared ──────────────
echo "── C · secret shapes (class named, matched text never echoed)"
sed 's|-U <DB_ADMIN> --format=directory|-U AKIAIOSFODNN7EXAMPLE --format=directory|' \
  "$W/good.md" > "$W/secret.md"
t "a hardcoded AWS key is refused" "$(run "$W/secret.md")" "5"
has "$W/out.txt" "secret-shape" "names the secret-shape rule"
has "$W/out.txt" "aws-access-key-id" "names the CLASS from chatroom's list"
hasnt "$W/out.txt" "AKIAIOSFODNN7EXAMPLE" "never echoes the matched text"
t "the class list is chatroom's, not a second copy" \
  "$(grep -c 'SECRET_PATTERNS *= *\[' "$L")" "0"
has "$L" "chatroom" "cites chatroom/scripts/room.py as the source of the classes"

NOTREST_ROOM_PY="$W/nope.py" python3 "$L" "$W/secret.md" > "$W/degrade.txt" 2>&1
t "with chatroom's list unreachable the run degrades, it does not pretend" "$?" "0"
has "$W/degrade.txt" "secret screen UNAVAILABLE" "says the screen did not run"
hasnt "$W/degrade.txt" "secret-shape" "and reports no secret finding it could not have made"

# ── D · shellcheck: present and absent, both honest ──────────────────────────────────
echo "── D · shellcheck present / absent"
cat > "$W/sc.md" <<'EOF'
## The Runbook
### Phase 1 — Check   ·   run on: app-server
1. Run the check.
   ```bash
   BADCHECK
   ```
   - Verify: `echo ok` → `ok`
   - Rollback: none — nothing was changed.
EOF
t "without shellcheck the runbook still passes bash -n" "$(run "$W/sc.md")" "0"
has "$W/out.txt" "shellcheck NOT installed" "prints the degradation note"
has "$W/out.txt" "never a failure here" "and says its absence is not a failure"

mkdir -p "$W/bin"
cat > "$W/bin/shellcheck" <<'EOF'
#!/bin/bash
if [ "${1:-}" = "--version" ]; then
  echo "ShellCheck - shell script analysis tool"; echo "version: 0.9.0-stub"; exit 0
fi
f=""; for a in "$@"; do case "$a" in /*) f="$a";; esac; done
if [ -n "$f" ] && grep -q BADCHECK "$f"; then
  echo "$f:1:1: error: stub: BADCHECK is forbidden [SC9999]"; exit 1
fi
exit 0
EOF
chmod +x "$W/bin/shellcheck"
PATH="$W/bin:$PATH" python3 "$L" "$W/sc.md" > "$W/sc.txt" 2>&1
t "with shellcheck present its error-level finding is reported (exit 5)" "$?" "5"
has "$W/sc.txt" "shellcheck 0.9.0-stub present" "names the version it found"
has "$W/sc.txt" "shellcheck-error" "names the shellcheck rule"
has "$W/sc.txt" "BADCHECK is forbidden" "carries shellcheck's own message"
PATH="$W/bin:$PATH" python3 "$L" "$W/good.md" > "$W/sc2.txt" 2>&1
t "and a clean runbook stays clean with shellcheck present" "$?" "0"

# ── E · parser edges ─────────────────────────────────────────────────────────────────
echo "── E · the parser is not fooled"
cat > "$W/fenced.md" <<'EOF'
## The Runbook
### Phase 1 — Inspect   ·   run on: app-server
1. Print the queue and read the numbered output.
   ```bash
   echo listing
   ```
   Expected output:
   ```
   1. first job
   2. second job
   ```
   - Verify: `echo ok` → `ok`
   - Rollback: none — read-only.
EOF
t "numbered lines inside a fenced block are not steps" "$(run "$W/fenced.md")" "0"
has "$W/out.txt" "1 step(s)" "counted exactly one real step"
has "$W/out.txt" "non-shell block" "and said which block it did not syntax-check"

python3 "$L" "$W/missing.md" > /dev/null 2>&1
t "a missing runbook exits 2" "$?" "2"

echo
echo "actionplan fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
