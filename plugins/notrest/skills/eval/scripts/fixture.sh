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
         "$P/skills/draft/references" "$P/skills/oracle" "$P/hooks" \
         "$P/skills/archivist/scripts"
# LEARNING-LOOP reads its trigger regex out of archivist's index.py — the ONE home both
# it and lane H's Stop hook read. The synthetic harness carries the REAL file (not a
# stub) so the parity arm below compares what actually ships, not a copy of it.
cp "$(cd "$(dirname "$0")/../../archivist/scripts" && pwd)/index.py" \
   "$P/skills/archivist/scripts/index.py"
cat > "$P/skills/archivist/SKILL.md" <<'EOF'
---
name: archivist
description: "The findings store and the learnings loop. Use on /archivist."
---
# archivist
Records land through `scripts/index.py add` — the store is **append-only**, never
hand-edited. `scripts/index.py learnings` renders the banked lessons.
## Self-check
- every record was validated at the door (exit 2 names the rule it broke)
EOF

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

inject "sonnet spawn directive (no tier declared)"  OFFLOAD-POLICY \
  'printf "\nSpawn the lane with model: \"sonnet\" for cheapness.\n" >> "$P/skills/agentswarm/SKILL.md"'
inject "haiku spawn directive (tier language does NOT launder it)"  OFFLOAD-POLICY \
  'printf "\nSpawn the mechanical DRAFT-tier lane with model: \"haiku\".\n" >> "$P/skills/agentswarm/SKILL.md"'
# The amended lawful form must NOT flip the check: sonnet + a declared tier on the
# same line stays green (owner amendment 2026-08-30). Same mutation shape as inject,
# but asserting exit 0 — a lawful sentence that reds the gate means the gate is stale.
W="$TMP/w"; rm -rf "$W"; cp -R "$BASE" "$W"; P="$W/plugins/notrest"
printf '\nUse model: "sonnet" only where the brief names the work mechanical (DRAFT-tier).\n' >> "$P/skills/agentswarm/SKILL.md"
python3 "$EVAL" check --root "$W" > "$TMP/out" 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then ok "sonnet WITH declared tier stays lawful, exit 0"; else
  bad "sonnet WITH tier flipped the suite (exit $rc)"; grep -E '^FAIL ' "$TMP/out"; fi

# ── owner amendment 2026-09-01: the SEAT chooses by DIFFICULTY and declares it ────────
# The gate must accept the NEW law without becoming a rubber stamp for anything that
# QUOTES it. F2 (refuter, 4.6.2) is the scar: the first cut exempted sonnet whenever the
# window carried the law's recital words (bounded / difficulty / well-specified), so the
# quotation became the licence and a blanket "sonnet for everything" sailed through while
# reciting the very rubric it violated. The exemption now keys on the SHAPE of a
# declaration — an absolute always fails; otherwise the window must name opus too, or
# carry an explicit tier declaration.
lawful(){  # $1 label · $2 the sentence(s) appended to a spawn-documenting SKILL.md
  W="$TMP/w"; rm -rf "$W"; cp -R "$BASE" "$W"; P="$W/plugins/notrest"
  printf '\n%b\n' "$2" >> "$P/skills/agentswarm/SKILL.md"
  python3 "$EVAL" check --root "$W" > "$TMP/out" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then ok "$1 stays lawful, exit 0"; else
    bad "$1 flipped the suite (exit $rc)"; grep -E '^FAIL ' "$TMP/out"; fi
}
unlawful(){  # $1 label · $2 the sentence(s) that MUST red OFFLOAD-POLICY
  W="$TMP/w"; rm -rf "$W"; cp -R "$BASE" "$W"; P="$W/plugins/notrest"
  printf '\n%b\n' "$2" >> "$P/skills/agentswarm/SKILL.md"
  python3 "$EVAL" check --root "$W" > "$TMP/out" 2>&1
  rc=$?
  got="$(grep -E '^FAIL ' "$TMP/out" | awk '{print $2}' | sort -u | tr '\n' ' ' | sed 's/ $//')"
  if [ "$rc" -eq 6 ] && [ "$got" = "OFFLOAD-POLICY" ]; then
    ok "$1 -> OFFLOAD-POLICY only, exit 6"
  else
    bad "$1 -> got [$got] exit $rc (want [OFFLOAD-POLICY] exit 6)"
    grep -E '^FAIL ' "$TMP/out"
  fi
}

# ⛔ THE REFUTER'S OWN REPRO AND EVERY LEAK THE REVIEW ROUND FOUND, VERBATIM. Two designs
# died here. Cut 1 exempted on the law's recital words, so quoting the law licensed
# breaking it. Cut 2 exempted on a window that mentioned opus, so a sentence RETIRING opus
# licensed itself — and condemned correct declarations whose neighbours said "by default".
# The rule is now one line wide: a declaration token on the directive's OWN line, and no
# absolute on that same line. These arms are the shape of both failures; if any of them
# flips, the check has gone back to reading the neighbourhood.
unlawful "F2: the refuter's blanket-sonnet sentence (recites the law, breaks it)" \
  'Delegation: choose by difficulty.\nEvery lane: model: "sonnet" — always, for all work including kernel design and refuters.'
unlawful "F2: recital words ALONE never launder a bare sonnet directive" \
  'Use model: "sonnet" for bounded, well-specified work the seat has scoped.'
# — review round (a): a bare mention of opus is NOT a licence. Each of these named opus and
#   passed the previous cut; three of them name it only to say it is not being used.
unlawful "F2a: 'in all cases' beside a retired opus" \
  'model: "sonnet" in all cases; opus is retired.'
unlawful "F2a: 'regardless of difficulty' with opus unused" \
  'Regardless of difficulty, model: "sonnet". opus unused.'
unlawful "F2a: 'for each lane' with opus reserved for nothing" \
  'model: "sonnet" for each lane. opus is reserved for nothing.'
unlawful "F2a: sonnet ON THE KERNEL, opus named only as the thing it is cheaper than" \
  'Kernel surfaces and refuters: model: "sonnet" (cheaper than opus).'
unlawful "F2a: naming both sides is not a declaration — the LINE must declare its tier" \
  'The seat picks model: "opus" for judgment and model: "sonnet" for a bounded lane.'
unlawful "F2: an absolute on the same line beats a real tier declaration" \
  'model: "sonnet" — tier: bounded — is used for all work, always.'

# — review round (b): a neighbouring line can no longer VETO a correct declaration.
lawful "F2b: 'by default' on the line ABOVE does not condemn a declared directive" \
  'Opus by default for judgment.\nmodel: "sonnet" — tier: bounded for a runnable done-when.'
lawful "F2b: 'always' in unrelated prose above does not condemn it either" \
  'The gate always runs before a ship.\nmodel: "sonnet" — tier: bounded for a runnable done-when.'
# …and the lawful shapes still pass, or the gate blocks the law it enforces.
lawful "the amendment's OWN bullet declares the tier on the directive's line" \
  '- **Declared, not implied:** the dispatching brief\n  states `model: opus — tier: judgment` or `model: sonnet — tier: bounded` with one line of\n  why, so the receipt is checkable against the choice.'
lawful "a tier declaration with no opus anywhere near it" \
  'model: "sonnet" — tier: bounded — done-when is the runnable check written before dispatch.'
lawful "the unspaced form tier:bounded is the same declaration" \
  'model: "sonnet" tier:bounded — done-when is a runnable check.'
lawful "the OLD mechanical/DRAFT wording still passes (no flag day)" \
  'Use model: "sonnet" only where the brief names the work mechanical (DRAFT-tier).'

# what did NOT move: haiku and forks are banned however the line is worded.
unlawful "haiku beside the NEW bounded wording is still banned" \
  'For bounded, well-specified work spawn with model: "haiku".'
unlawful "haiku beside a REAL tier declaration is still banned (no token launders it)" \
  'model: "haiku" — tier: bounded — for a mechanical DRAFT-tier sweep.'
unlawful "a fork beside the NEW bounded wording is still banned" \
  'For bounded, well-specified work use subagent_type: "fork" to save tokens.'

# the law string must not let a reader mistake a grammar PASS for a judgment about routing
python3 "$EVAL" check --root "$BASE" > "$TMP/law" 2>&1 || true
grep -q 'GRAMMAR CHECK' "$TMP/law" && ok "the law string calls itself a grammar check" \
  || bad "the law string does not disclose that it is a grammar check"
grep -q "seat's judgment" "$TMP/law" && ok "…and says where the semantics actually live" \
  || bad "the law string does not name the seat/receipts as the semantic authority"

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

# ── RELEASE-SURFACE · a DELETION is not an unagreed surface ───────────────────────────
# `git diff --name-only HEAD` lists REMOVED paths as well as changed ones, so retiring a
# golden-surface file could never be green before the commit: delist it and the "touched
# but not agreed" half fires; keep it listed and the "named file does not exist" half
# fires. The workshop rebuild sat in exactly that vice — 10 module files deleted and
# delisted in one change, with no ordering that passed. These arms need a real work tree,
# so this block builds one.
gitsurface() {  # gitsurface <label> <want-exit> <want-FAIL-checks> <mutation>
  label="$1"; wantrc="$2"; wantfail="$3"; shift 3
  W="$TMP/w"; rm -rf "$W"; cp -R "$BASE" "$W"
  P="$W/plugins/notrest"
  mkdir -p "$W/docs" "$W/evals"
  printf "the retiring module\n" > "$W/docs/retiring-module.md"
  printf "docs/retiring-module.md\n" > "$W/evals/golden-release-surface.txt"
  (
    cd "$W" || exit 1
    git init -q 2>/dev/null
    git config user.name Fixture; git config user.email fixture@example.com
    git config commit.gpgsign false
    git add -A >/dev/null 2>&1
    git -c commit.gpgsign=false commit -qm "the agreed surface" >/dev/null 2>&1
  ) || { bad "$label — git setup failed"; return; }
  ( eval "$@" )
  python3 "$EVAL" check --root "$W" > "$TMP/out" 2>&1
  rc=$?
  got="$(grep -E '^FAIL ' "$TMP/out" | awk '{print $2}' | sort -u | tr '\n' ' ' | sed 's/ $//')"
  if [ "$rc" -eq "$wantrc" ] && [ "$got" = "$wantfail" ]; then
    ok "$label (exit $rc)"
  else
    bad "$label -> got [$got] exit $rc (want [$wantfail] exit $wantrc)"
    grep -E '^FAIL ' "$TMP/out"
  fi
}

# 1 · deleted on disk AND delisted, uncommitted — the retirement the ruling admits
gitsurface "a delisted file deleted but not yet committed is a RETIREMENT, not a breach" 0 "" \
  'rm -f "$W/docs/retiring-module.md"; : > "$W/evals/golden-release-surface.txt"'
# 2 · deleted but still named in the list — the other half must still catch it
gitsurface "…but a file still NAMED in the golden list and deleted is caught" 6 "RELEASE-SURFACE" \
  'rm -f "$W/docs/retiring-module.md"'
# 3 · a new release-shaped surface nobody agreed to — unchanged behaviour
gitsurface "an ADDED docs/ surface that is not in the golden list still FAILs" 6 "RELEASE-SURFACE" \
  'printf "new\n" > "$W/docs/unagreed-page.md"; (cd "$W" && git add docs/unagreed-page.md >/dev/null 2>&1)'
# 3b · a DANGLING SYMLINK is not a deletion. os.path.exists() follows the link, so a
# broken link at a touched unlisted path read as "removed" and slipped the unagreed-surface
# half while the index still carried a blob. lexists sees the link itself.
gitsurface "a dangling symlink at an unlisted touched path is NOT a deletion" 6 "RELEASE-SURFACE" \
  'printf "sneak\n" > "$W/docs/SNEAK.md"; (cd "$W" && git add docs/SNEAK.md >/dev/null 2>&1);
   rm -f "$W/docs/SNEAK.md"; ln -s /nonexistent-target "$W/docs/SNEAK.md"'
# …while a REAL removal at the same shape still reads as the retirement it is
gitsurface "…and a real deletion beside it still passes" 0 "" \
  'rm -f "$W/docs/retiring-module.md"; : > "$W/evals/golden-release-surface.txt"'

# 4 · the deletion exclusion must not blind the check to a real addition beside it
gitsurface "…even when a legitimate retirement happens in the same change" 6 "RELEASE-SURFACE" \
  'rm -f "$W/docs/retiring-module.md"; : > "$W/evals/golden-release-surface.txt";
   printf "new\n" > "$W/docs/unagreed-page.md"; (cd "$W" && git add docs/unagreed-page.md >/dev/null 2>&1)'

# ── LEARNING-LOOP (4.6.3) · did the estate BANK the lessons it paid for? ─────────────
# ⛔ ONE REGEX, ONE HOME. eval and lane H's Stop hook both read LEARN_TRIGGER_REGEX out of
# archivist's index.py. Two copies is two regexes the moment somebody edits one — and then
# the hook prompts for lessons the gate does not audit, or the gate reddens on lines the
# hook never surfaced. This parity arm is the thing that makes the single home real.
IDXP="$BASE/plugins/notrest/skills/archivist/scripts/index.py"
if [ -f "$IDXP" ]; then
  RX_IDX="$(python3 "$IDXP" learnings --trigger-regex 2>/dev/null)"
  RX_EVAL="$(python3 -c "
import importlib.util,sys
sp=importlib.util.spec_from_file_location('e','$EVAL'); m=importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
rx,_p=m.learning_trigger_regex('$BASE/plugins/notrest')
sys.stdout.write(rx or '')" 2>/dev/null)"
  [ -n "$RX_IDX" ] && [ "$RX_IDX" = "$RX_EVAL" ] \
    && ok "eval's trigger regex IS index.py's, byte for byte" \
    || bad "trigger regex drift: index[$RX_IDX] eval[$RX_EVAL]"
else
  bad "archivist index.py is not in the synthetic harness — parity unprovable"
fi

# 4.7: the contract gained `untested` — ADDITIVELY, so the five original keys keep their
# exact meaning and a consumer reading only them is unaffected. eval must not fail on it.
python3 -c "
import importlib.util, json, sys, os
sp=importlib.util.spec_from_file_location('ix','$IDXP'); m=importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
rep=m.trigger_report('$BASE')
assert sorted(rep)==['armed','cited','floor','regex','uncited','untested'], sorted(rep)
" && ok "the trigger contract carries all six keys eval and the hook read" \
  || bad "the trigger contract keys are not what eval expects"

lloop() {  # lloop <label> <want-exit> <want-FAIL-checks> <mutation>
  label="$1"; wantrc="$2"; wantfail="$3"; shift 3
  W="$TMP/w"; rm -rf "$W"; cp -R "$BASE" "$W"
  P="$W/plugins/notrest"; mkdir -p "$W/archive"
  cat > "$W/COORD.md" <<'CO'
# COORD.md — session coordination ledger
## LEDGER
- [2026-09-05 04:00Z] [seat] ordinary work -> landed | evidence: exit 0
- [2026-09-05 04:45Z] [seat] owner CORRECTION: bank the lessons -> loop designed | evidence: brief
- [2026-09-05 04:47Z] [seat] REFUTER round found a DEFECT in the gate -> fixed | evidence: exit 0
CO
  ( eval "$@" )
  python3 "$EVAL" check --root "$W" > "$TMP/out" 2>&1
  rc=$?
  got="$(grep -E '^FAIL ' "$TMP/out" | awk '{print $2}' | sort -u | tr '\n' ' ' | sed 's/ $//')"
  if [ "$rc" -eq "$wantrc" ] && [ "$got" = "$wantfail" ]; then ok "$label (exit $rc)"
  else bad "$label -> got [$got] exit $rc (want [$wantfail] exit $wantrc)"; grep -E '^FAIL ' "$TMP/out"; fi
}
LSTAMP='[2026-09-05 04:45Z]'
mkrec() {  # mkrec <ts> <evidence-ref>  -> one learning record on stdout
  python3 -c "
import json,sys
print(json.dumps({'id':'L-1','ts':sys.argv[1],'session':'','skill':'','kind':'learning',
 'ask':'','statement':'a lesson the estate paid for','tag':'RULED',
 'evidence':[{'type':'coord-line','ref':sys.argv[2],'label':'cited'}],
 'relation':'toward','links':[],'status':'live','scope':['estate'],'source':'seat'}))" "$1" "$2"
}

# no learning at all -> the loop is NOT ARMED. It must SKIP, never invent a debt.
lloop "no learning record -> the loop SKIPs, it never invents a debt" 0 "" 'true'
python3 "$EVAL" check --root "$TMP/w" > "$TMP/out" 2>&1
grep -q 'SKIP  LEARNING-LOOP' "$TMP/out" && ok "…and says so as a SKIP line" || bad "no SKIP line"
grep -q 'loop not armed' "$TMP/out" && ok "…naming the reason" || bad "the SKIP did not name its reason"

# a learning that cites the trigger closes the loop for it; the LATER trigger does not
lloop "a trigger cited by no learning FAILs" 6 "LEARNING-LOOP" \
  "mkrec 2026-09-05T04:46:00Z '$LSTAMP' > \"\$W/archive/findings.jsonl\""
python3 "$EVAL" check --root "$TMP/w" > "$TMP/out" 2>&1
grep -q '04:47Z' "$TMP/out" && ok "…naming the uncited trigger by its timestamp" \
  || bad "the finding did not name the uncited line"
grep -q '04:45Z\].*cited by no learning' "$TMP/out" && bad "the CITED trigger was reported too" \
  || ok "…and the cited one is not reported"

# both triggers cited -> PASS
lloop "every trigger cited -> PASS" 0 "" \
  "{ mkrec 2026-09-05T04:46:00Z '$LSTAMP'; mkrec 2026-09-05T04:48:00Z '[2026-09-05 04:47Z]'; } > \"\$W/archive/findings.jsonl\""
python3 "$EVAL" check --root "$TMP/w" > "$TMP/out" 2>&1
grep -q 'PASS  LEARNING-LOOP' "$TMP/out" && ok "…reported as a PASS with counts" || bad "no PASS line"
grep -qE 'LEARNING-LOOP.*loop armed at .* trigger line\(s\) since, all cited' "$TMP/out" \
  && ok "…stating the floor it armed at and how many triggers it audited" \
  || bad "the PASS did not carry its counts"

# ⛔ THE AUDIT IS BOUNDED BY WHEN THE LOOP WAS ARMED. A trigger OLDER than the first
# learning predates the practice; grading an estate against a rule it did not have is how
# a gate becomes something people switch off.
lloop "a trigger OLDER than the first learning is not a debt" 0 "" \
  "mkrec 2026-09-05T04:46:30Z '[2026-09-05 04:47Z]' > \"\$W/archive/findings.jsonl\""
# an ordinary line is never a trigger, however many learnings exist
lloop "an ordinary ledger line is never a trigger" 0 "" \
  "{ mkrec 2026-09-05T04:46:00Z '$LSTAMP'; mkrec 2026-09-05T04:48:00Z '[2026-09-05 04:47Z]'; } > \"\$W/archive/findings.jsonl\""
python3 "$EVAL" check --root "$TMP/w" > "$TMP/out" 2>&1
grep -q '04:00Z' "$TMP/out" && bad "an ordinary line was audited as a trigger" \
  || ok "…the 04:00Z ordinary line is not audited"
# a corrupt store line must not take the check down
lloop "a corrupt store line does not break the check" 0 "" \
  "{ mkrec 2026-09-05T04:46:00Z '$LSTAMP'; echo 'not json'; mkrec 2026-09-05T04:48:00Z '[2026-09-05 04:47Z]'; } > \"\$W/archive/findings.jsonl\""

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
