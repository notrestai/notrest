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
         "$P/skills/draft/references" "$P/skills/oracle" "$P/hooks"

cat > "$P/skills/agentswarm/SKILL.md" <<'EOF'
---
name: agentswarm
description: "The delegation arrangement — the seat keeps decompose/judge/apply/gate. Use on /agentswarm."
---
# agentswarm
Runtime map: Claude uses `model: "opus"`; Codex uses `model: "gpt-5.6-sol"` with
`fork_turns: "none"` or a bounded recent-turn fork. Spawn with the host's agent tool.
- **Never spawn `subagent_type: "fork"`** — forks ignore the model parameter.
EOF

cat > "$P/skills/researcher/SKILL.md" <<'EOF'
---
name: researcher
description: "Research anything into a dossier. Use on /researcher."
---
# researcher
**Router shape:** `research`
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
**Router shape:** `file-graph`
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
**Router shape:** `outbound`
A draft is never sent — sending is the owner's act, in the owner's client.
Labels survive: [estimate] stays hedged.
Per-channel shapes live in `references/formats.md`.
## Self-check before finishing
- Every sentence traces to the source.
## Finishing up
- Hand the draft to the owner.
EOF
printf '# formats\nemail · memo · slack\n' > "$P/skills/draft/references/formats.md"

# the routing table's second authority: what the intake TELLS the user must be what the
# hook FIRES at them.
cat > "$P/skills/oracle/SKILL.md" <<'EOF'
---
name: oracle
description: "Session intake and resume — the suite's front door. Use on /oracle."
---
# oracle
- **Route to the right tool:** research a question → `/researcher` · write the memo → `/draft` — or say "no skill needed, working directly."
EOF

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
  *" research"*) SKILL=researcher; SHAPE=research ;;
  *" write the memo"*) SKILL=draft; SHAPE=outbound ;;
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

# Both authorities are moved to the ghost verb together, so the tables still AGREE and
# only "that skill does not exist" is left to find. One defect, one check.
inject "router verb with no skill dir" ROUTER \
  'sed -i.bak "s/SKILL=researcher/SKILL=nosuchskill/" "$P/hooks/router.sh" && rm -f "$P/hooks/router.sh.bak" &&
   sed -i.bak "s|/researcher|/nosuchskill|" "$P/skills/oracle/SKILL.md" && rm -f "$P/skills/oracle/SKILL.md.bak"'

# ---------------------------------------------------- the two authorities disagree
# the hook now fires a verb the intake never promises (and stops firing one it does)
inject "router arm the intake never mirrors" ROUTE-TABLE-PARITY \
  'sed -i.bak "s/SKILL=researcher; SHAPE=research/SKILL=graph; SHAPE=file-graph/" "$P/hooks/router.sh" && rm -f "$P/hooks/router.sh.bak"'

# and the other direction: the intake promises a route no prompt can ever trigger
inject "intake verb the router cannot emit" ROUTE-TABLE-PARITY \
  'sed -i.bak "s|research a question|map the files -> \`/graph\` and research a question|" "$P/skills/oracle/SKILL.md" && rm -f "$P/skills/oracle/SKILL.md.bak"'

# G9: the destination has to acknowledge the shape that lands on it. A routed skill whose
# body never says so is a route the reader of that skill cannot see.
inject "routed skill with no Router-shape line" ROUTE-TABLE-PARITY \
  'sed -i.bak "/^\*\*Router shape:\*\*/d" "$P/skills/researcher/SKILL.md" && rm -f "$P/skills/researcher/SKILL.md.bak"'

# The bullet is the mirror; losing it entirely is worse than any single disagreement.
inject "intake routing bullet deleted" ROUTE-TABLE-PARITY \
  'sed -i.bak "/Route to the right tool/d" "$P/skills/oracle/SKILL.md" && rm -f "$P/skills/oracle/SKILL.md.bak"'

# A ghost reference is the .py case's blind spot: SCRIPT-OWNS-SCANNING only ever looked
# at scripts/*.py, so a SKILL.md could promise a references/ file that was never shipped
# and nothing said a word.
inject "reference cited but never shipped" REFERENCES-CITED \
  'printf "\nThe long form lives in \`references/ghost.md\`.\n" >> "$P/skills/draft/SKILL.md"'

# and the boundary in the other direction: deleting a cited .py must stay SCRIPT-OWNS-
# SCANNING's finding alone. Two checks firing on one defect is a report nobody can act on.
inject "cited .py deleted stays one check" SCRIPT-OWNS-SCANNING \
  'rm -f "$P/skills/graph/scripts/graph.py"'

# A shape token that drifted still routes — the doc just names the shape wrong. That is
# a WARN, and a check that cannot tell the two apart teaches the reader to ignore it.
WS="$TMP/ws"; rm -rf "$WS"; cp -R "$BASE" "$WS"
sed -i.bak 's/^\*\*Router shape:\*\* `research`$/**Router shape:** `recap`/' \
  "$WS/plugins/notrest/skills/researcher/SKILL.md"
rm -f "$WS/plugins/notrest/skills/researcher/SKILL.md.bak"
python3 "$EVAL" check --root "$WS" > "$TMP/shape.out" 2>&1
rc=$?
if [ "$rc" -eq 5 ] && grep -qE "^WARN +ROUTE-TABLE-PARITY" "$TMP/shape.out"; then
  ok "a drifted shape token WARNs (exit 5) and never FAILs"
else
  bad "drifted shape token -> exit $rc (want 5 + a ROUTE-TABLE-PARITY WARN)"
  grep -E '^(WARN|FAIL) ' "$TMP/shape.out"
fi

# ------------------------------------- ROUTE-CONFORMANCE: WARN-grade, never a gate
# A recorded route claims work went somewhere. These assert the claim is judged against
# the trail — and that the check stays a WARN so a mid-flight ledger never blocks a ship.
# ------------------------------------- v4.2.1 · the three adopted checks
# Written INSIDE this harness's own helper scope this time, using its own idiom:
# inject <label> <expected-check-id> <mutation>, every path under $W/$P (the sandbox
# copy), never an absolute path. The previous attempt was written outside this scope
# and tried to write to /evals and /CHANGELOG.md — it failed only because the
# filesystem was read-only, which is luck, not a test.

# NETWORK-EGRESS · an unlisted network caller. Appended to a script the SKILL.md ALREADY
# names, so SCRIPT-OWNS-SCANNING stays green and exactly one check flips.
inject "unlisted network import" NETWORK-EGRESS \
  'printf "import urllib.request\n" >> "$P/skills/graph/scripts/graph.py"'

# NETWORK-EGRESS · allowlisted as loopback, but nothing binds it to 127.0.0.1. The
# SKILL.md gains the reference in the same mutation, so only this check reddens.
inject "allowlisted path that is not loopback-bound" NETWORK-EGRESS \
  'printf "import socket\n" > "$P/skills/graph/scripts/cockpit.py";
   printf "Script: \`scripts/cockpit.py\` — the live window.\n" >> "$P/skills/graph/SKILL.md"'

# NETWORK-EGRESS · a compiled runtime must import no network at all, as its own law says.
inject "compiled runtime reaching the network" NETWORK-EGRESS \
  'mkdir -p "$W/compile/demo" && printf "import socket\n" > "$W/compile/demo/run.py"'

# KERNEL-REVIEW · a tree that ships refuter + CLAUDE.md but never names the kernel.
inject "kernel surfaces unnamed" KERNEL-REVIEW \
  'mkdir -p "$P/skills/refuter";
   printf -- "---\nname: refuter\ndescription: \"Attack one target. Use on /refuter.\"\n---\n# refuter\n" > "$P/skills/refuter/SKILL.md";
   printf "# project\n" > "$W/CLAUDE.md"'

# KERNEL-REVIEW · named in CLAUDE.md but NOT in refuter — one home is not both.
inject "kernel named in only one of its two homes" KERNEL-REVIEW \
  'mkdir -p "$P/skills/refuter";
   printf -- "---\nname: refuter\ndescription: \"Attack one target. Use on /refuter.\"\n---\n# refuter\n" > "$P/skills/refuter/SKILL.md";
   printf "# project\n\n## KERNEL SURFACES\nhooks/, establish.py, ledger writers.\n" > "$W/CLAUDE.md"'

# RELEASE-SURFACE · the golden list names a file that does not exist.
inject "golden surface names a missing file" RELEASE-SURFACE \
  'mkdir -p "$W/evals" && printf "docs/does-not-exist.html\n" > "$W/evals/golden-release-surface.txt"'

# ---- the PASSING sides, asserted directly (inject only expresses failures) ----
passcase() {  # passcase <label> <mutation>
  label="$1"; shift
  W="$TMP/w"; rm -rf "$W"; cp -R "$BASE" "$W"
  P="$W/plugins/notrest"
  ( eval "$@" )
  python3 "$EVAL" check --root "$W" > "$TMP/out" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then ok "$label -> still exits 0"
  else bad "$label -> exit $rc"; grep -E '^FAIL ' "$TMP/out"; fi
}

passcase "a clean tree reaches no network" 'true'
passcase "kernel named in BOTH homes passes" \
  'mkdir -p "$P/skills/refuter";
   printf -- "---\nname: refuter\ndescription: \"Attack one target. Use on /refuter.\"\n---\n# refuter\n## KERNEL SURFACES\nhooks/, establish.py, ledger writers.\n" > "$P/skills/refuter/SKILL.md";
   printf "# project\n\n## KERNEL SURFACES\nhooks/, establish.py, ledger writers.\n" > "$W/CLAUDE.md"'
# The base harness ships a CLAUDE.md, so this case REMOVES it to reach the SKIP path —
# a check whose inputs are absent must skip, not redden (eval's own doctrine).
passcase "no CLAUDE.md at all SKIPs the kernel check" \
  'mkdir -p "$P/skills/refuter";
   printf -- "---\nname: refuter\ndescription: \"Attack one target. Use on /refuter.\"\n---\n# refuter\n" > "$P/skills/refuter/SKILL.md";
   rm -f "$W/CLAUDE.md"'
passcase "a golden list whose surfaces all exist" \
  'mkdir -p "$W/evals" && printf "CHANGELOG.md\n" > "$W/evals/golden-release-surface.txt";
   printf "x\n" > "$W/CHANGELOG.md"'

# THE SANDBOX LAW, now asserted: this fixture writes only inside its own mktemp dir.
if [ -e /evals ] || [ -e /golden-release-surface.txt ]; then
  bad "sandbox law: this fixture wrote outside its mktemp dir"
else
  ok "sandbox law: nothing was written outside the mktemp sandbox"
fi

mkcoord() { cat > "$TMP/coord.in"; }

# conform <label> <want-exit> <want-conformance-warns> [extra-setup-shell]
conform() {
  label="$1"; want_rc="$2"; want="$3"; shift 3
  WC="$TMP/wc"; rm -rf "$WC"; cp -R "$BASE" "$WC"
  cp "$TMP/coord.in" "$WC/COORD.md"
  W="$WC"; [ "$#" -eq 0 ] || ( eval "$@" )
  python3 "$EVAL" check --root "$WC" > "$TMP/conf.out" 2>&1
  rc=$?
  got="$(grep -cE '^WARN +ROUTE-CONFORMANCE' "$TMP/conf.out")"
  if [ "$rc" -eq "$want_rc" ] && [ "$got" -eq "$want" ]; then
    ok "$label -> $got conformance WARN(s), exit $rc"
  else
    bad "$label -> $got WARN(s), exit $rc (want $want, exit $want_rc)"
    grep -E '^(WARN|FAIL) ' "$TMP/conf.out"
  fi
}

mkcoord <<'EOF'
# COORD.md — session coordination ledger
- [2026-01-01 00:00Z] [main] intake done: O=vector deletes -> routed to /notrest:researcher | evidence: this line
- [2026-01-01 01:00Z] [main] unrelated parser work landed | evidence: exit 0
- [2026-01-01 02:00Z] [main] unrelated hook work landed | evidence: exit 0
- [2026-01-01 03:00Z] [main] unrelated docs work landed | evidence: exit 0
EOF
conform "a route with nothing downstream" 5 1

mkcoord <<'EOF'
# COORD.md — session coordination ledger
- [2026-01-01 00:00Z] [main] intake done: O=vector deletes -> routed to /notrest:researcher | evidence: this line
- [2026-01-01 01:00Z] [main] researcher dossier landed, 9 findings | evidence: research/vector-deletes.md
- [2026-01-01 02:00Z] [main] unrelated hook work landed | evidence: exit 0
- [2026-01-01 03:00Z] [main] unrelated docs work landed | evidence: exit 0
EOF
conform "a route a later ledger line backs" 0 0

mkcoord <<'EOF'
# COORD.md — session coordination ledger
- [2026-01-01 00:00Z] [main] unrelated parser work landed | evidence: exit 0
- [2026-01-01 01:00Z] [main] unrelated hook work landed | evidence: exit 0
- [2026-01-01 02:00Z] [main] intake done: O=vector deletes -> routed to /notrest:researcher | evidence: this line
EOF
conform "an in-flight route inside the 3-line grace window" 0 0

mkcoord <<'EOF'
# COORD.md — session coordination ledger
- [2026-01-01 00:00Z] [main] shape was research-shaped but deliberately NOT routed to /researcher — owner wanted it inline | evidence: this line
- [2026-01-01 01:00Z] [main] unrelated parser work landed | evidence: exit 0
- [2026-01-01 02:00Z] [main] unrelated hook work landed | evidence: exit 0
- [2026-01-01 03:00Z] [main] unrelated docs work landed | evidence: exit 0
EOF
conform "a route deliberately declined (negation-aware)" 0 0

mkcoord <<'EOF'
# COORD.md — session coordination ledger
- [2026-01-01 00:00Z] [main] intake done: O=vector deletes -> routed to /notrest:researcher | evidence: this line
- [2026-01-01 01:00Z] [main] unrelated parser work landed | evidence: exit 0
- [2026-01-01 02:00Z] [main] unrelated hook work landed | evidence: exit 0
- [2026-01-01 03:00Z] [main] unrelated docs work landed | evidence: exit 0
EOF
conform "a route the findings store backs" 0 0 \
  'mkdir -p "$W/archive" && printf %s\\n "{\"id\":\"F-1\",\"skill\":\"researcher\",\"statement\":\"vector deletes are tombstoned\"}" > "$W/archive/findings.jsonl"'

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
