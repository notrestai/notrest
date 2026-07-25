#!/usr/bin/env bash
# fixture — build a synthetic mini-harness that PASSES, then inject one violation
# per check and assert each flips EXACTLY its own check to FAIL (exit 6).
# Exit 0 = every assertion held. No network, no model calls, no repo writes.

EVAL="$(cd "$(dirname "$0")" && pwd)/eval.py"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/notrest-eval-fixture.XXXXXX")"
BASE="$TMP/base"
PASSES=0
FAILS=0

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

ok()   { PASSES=$((PASSES+1)); echo "PASS  $1"; }
bad()  { FAILS=$((FAILS+1));  echo "FAIL  $1"; }

# ---------------------------------------------------------------- base harness
P="$BASE/plugins/notrest"
mkdir -p "$P/skills/agentswarm" "$P/skills/researcher" "$P/skills/graph/scripts" \
         "$P/skills/draft" "$P/hooks"

cat > "$P/skills/agentswarm/SKILL.md" <<'EOF'
---
name: agentswarm
description: "The delegation arrangement — the seat keeps decompose/judge/apply/gate. Use on /agentswarm."
---
# agentswarm
Spawn with the Agent tool, `model: "opus"` on every lane.
- **Never spawn `subagent_type: "fork"`** — forks ignore the model parameter.
EOF

cat > "$P/skills/researcher/SKILL.md" <<'EOF'
---
name: researcher
description: "Research anything into a dossier. Use on /researcher."
---
# researcher
Every claim carries [cited] / [recall] / [estimate] / [unverified].
Append the COORD.md ledger line — append-only, never hand-edit.
## Self-check before finishing
- Labels on every claim.
## Finishing up
- Hand the dossier over.
EOF

cat > "$P/skills/graph/SKILL.md" <<'EOF'
---
name: graph
description: "A file graph at zero model tokens. Use on /graph."
---
# graph
Script: `scripts/graph.py` — the scanner reads the files, the model never has to.
## Self-check before finishing
- The scanner ran; the model read nothing.
EOF
printf 'print("graph")\n' > "$P/skills/graph/scripts/graph.py"

cat > "$P/skills/draft/SKILL.md" <<'EOF'
---
name: draft
description: "Turn a dossier into the thing you send. Use on /draft."
---
# draft
A draft is never sent — sending is the owner's act, in the owner's client.
Labels survive: [estimate] stays hedged.
## Self-check before finishing
- Every sentence traces to the source.
## Finishing up
- Hand the draft to the owner.
EOF

cat > "$P/hooks/session-start.sh" <<'EOF'
#!/usr/bin/env bash
echo "[notrest] Fable discipline. Offload policy: every offloaded job runs on opus."
exit 0
EOF

cat > "$P/hooks/hooks.json" <<'EOF'
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"bash \"$CLAUDE_PLUGIN_ROOT/hooks/session-start.sh\""}]}]}}
EOF

# ------------------------------------------------------------------ base = 0
python3 "$EVAL" check --root "$BASE" > "$TMP/base.out" 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then ok "clean mini-harness exits 0"; else
  bad "clean mini-harness exits $rc (want 0)"; cat "$TMP/base.out"; fi

python3 "$EVAL" check --root "$BASE" --json > "$TMP/base.json" 2>&1
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d['verdict']=='PASS' and d['fails']==0 else 1)" "$TMP/base.json" \
  && ok "--json parses and reports verdict PASS" \
  || bad "--json did not parse or verdict wrong"

# ------------------------------------------------- one violation per check
# inject <label> <expected-check-id> <mutation-shell>
inject() {
  label="$1"; want="$2"; shift 2
  W="$TMP/w"; rm -rf "$W"; cp -R "$BASE" "$W"
  P="$W/plugins/notrest"
  ( eval "$@" )
  python3 "$EVAL" check --root "$W" > "$TMP/out" 2>&1
  rc=$?
  got="$(grep -E '^FAIL ' "$TMP/out" | awk '{print $2}' | sort -u | tr '\n' ' ' | sed 's/ $//')"
  if [ "$rc" -eq 6 ] && [ "$got" = "$want" ]; then
    ok "$label -> $want only, exit 6"
  else
    bad "$label -> got [$got] exit $rc (want [$want] exit 6)"
    grep -E '^FAIL ' "$TMP/out"
  fi
}

inject "sonnet spawn directive"  OFFLOAD-POLICY \
  'printf "\nSpawn the lane with model: \"sonnet\" for cheapness.\n" >> "$P/skills/agentswarm/SKILL.md"'

inject "label-less research skill" HONESTY-LABELS \
  'sed -i.bak "s/^Every claim carries.*$/Every claim is stated plainly./" "$P/skills/researcher/SKILL.md" && rm -f "$P/skills/researcher/SKILL.md.bak"'

inject "script cited but missing" SCRIPT-OWNS-SCANNING \
  'rm -f "$P/skills/graph/scripts/graph.py"'

inject "edit-the-ledger phrasing" ESTATE-WRITE \
  'sed -i.bak "s|^Append the COORD.md ledger line.*$|Edit the ledger when a lane lands.|" "$P/skills/researcher/SKILL.md" && rm -f "$P/skills/researcher/SKILL.md.bak"'

inject "missing self-check section" WORKER-CONTRACT \
  'sed -i.bak "/^## Self-check before finishing$/d" "$P/skills/researcher/SKILL.md" && rm -f "$P/skills/researcher/SKILL.md.bak"'

inject "unquoted description with colon-space" TRIGGER-SANITY \
  'sed -i.bak "s|^description: .*$|description: Research anything: into a dossier. Use on /researcher.|" "$P/skills/researcher/SKILL.md" && rm -f "$P/skills/researcher/SKILL.md.bak"'

inject "missing safety law" SAFETY-LAWS \
  'sed -i.bak "/^A draft is never sent/d" "$P/skills/draft/SKILL.md" && rm -f "$P/skills/draft/SKILL.md.bak"'

inject "hook with set -e" HOOK-CONTRACT \
  'sed -i.bak "2i\\
set -e
" "$P/hooks/session-start.sh" && rm -f "$P/hooks/session-start.sh.bak"'

# ------------------------------------------------------------------- verdict
echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
