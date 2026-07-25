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
         "$P/skills/draft/references" "$P/hooks"

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
Per-channel shapes live in `references/formats.md`.
## Self-check before finishing
- Every sentence traces to the source.
## Finishing up
- Hand the draft to the owner.
EOF
printf '# formats\nemail · memo · slack\n' > "$P/skills/draft/references/formats.md"

cat > "$P/hooks/session-start.sh" <<'EOF'
#!/usr/bin/env bash
echo "[notrest] Fable discipline. Offload policy: every offloaded job runs on opus."
exit 0
EOF

cat > "$P/hooks/router.sh" <<'EOF'
#!/bin/bash
# routing law — a task shape routes to the suite's verb for it.
SKILL=""
case " $1 " in
  *" research"*) SKILL=researcher ;;
  *" write the memo"*) SKILL=draft ;;
esac
[ -n "$SKILL" ] || exit 0
echo "[notrest] route: /notrest:$SKILL"
exit 0
EOF

cat > "$P/hooks/hooks.json" <<'EOF'
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"bash \"$CLAUDE_PLUGIN_ROOT/hooks/session-start.sh\""}]}],"UserPromptSubmit":[{"hooks":[{"type":"command","command":"bash \"$CLAUDE_PLUGIN_ROOT/hooks/router.sh\""}]}]}}
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

# router.sh still on disk and still valid — only the UserPromptSubmit wire is cut,
# so this must flip ROUTER and nothing else.
inject "router present but unregistered" ROUTER \
  'printf "%s\n" "{\"hooks\":{\"SessionStart\":[{\"hooks\":[{\"type\":\"command\",\"command\":\"bash \\\"\$CLAUDE_PLUGIN_ROOT/hooks/session-start.sh\\\"\"}]}]}}" > "$P/hooks/hooks.json"'

inject "router verb with no skill dir" ROUTER \
  'sed -i.bak "s/SKILL=researcher/SKILL=nosuchskill/" "$P/hooks/router.sh" && rm -f "$P/hooks/router.sh.bak"'

# A ghost reference is the .py case's blind spot: SCRIPT-OWNS-SCANNING only ever looked
# at scripts/*.py, so a SKILL.md could promise a references/ file that was never shipped
# and nothing said a word.
inject "reference cited but never shipped" REFERENCES-CITED \
  'printf "\nThe long form lives in \`references/ghost.md\`.\n" >> "$P/skills/draft/SKILL.md"'

# and the boundary in the other direction: deleting a cited .py must stay SCRIPT-OWNS-
# SCANNING's finding alone. Two checks firing on one defect is a report nobody can act on.
inject "cited .py deleted stays one check" SCRIPT-OWNS-SCANNING \
  'rm -f "$P/skills/graph/scripts/graph.py"'

# ------------------------------------------------------- baseline: what MOVED
# The baseline is a reporting mode, not a gate: it may add a section, never a verdict.
python3 "$EVAL" check --root "$BASE" --baseline "$TMP/base.json" > "$TMP/same.out" 2>&1
rc=$?
if [ "$rc" -eq 0 ] && grep -q 'nothing moved' "$TMP/same.out"; then
  ok "baseline vs an unchanged tree: nothing moved, exit still 0"
else
  bad "baseline vs unchanged tree -> exit $rc"; tail -3 "$TMP/same.out"
fi

WB="$TMP/wb"; rm -rf "$WB"; cp -R "$BASE" "$WB"
printf '\nThe long form lives in `references/ghost.md`.\n' \
  >> "$WB/plugins/notrest/skills/draft/SKILL.md"
python3 "$EVAL" check --root "$WB" --baseline "$TMP/base.json" > "$TMP/moved.out" 2>&1
rc=$?
if [ "$rc" -eq 6 ] && grep -qE 'REFERENCES-CITED +PASS -> FAIL' "$TMP/moved.out"; then
  ok "baseline names the check that flipped; the exit code stays the run's own (6)"
else
  bad "baseline vs a regressed tree -> exit $rc"; tail -6 "$TMP/moved.out"
fi
grep -qE '^  \+ FAIL +REFERENCES-CITED' "$TMP/moved.out" \
  && ok "baseline lists the finding that appeared, with its address" \
  || bad "baseline reported no added finding"

python3 "$EVAL" check --root "$BASE" --baseline "$TMP/absent.json" > "$TMP/nob.out" 2>&1
rc=$?
if [ "$rc" -eq 0 ] && grep -q 'baseline unreadable' "$TMP/nob.out"; then
  ok "a missing baseline is reported, never raised, and the verdict stands"
else
  bad "missing baseline -> exit $rc"; tail -3 "$TMP/nob.out"
fi

# ------------------------------------------------------------------- verdict
echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
