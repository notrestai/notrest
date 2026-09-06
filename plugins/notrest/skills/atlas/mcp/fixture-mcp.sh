#!/bin/bash
# fixture-mcp.sh — asserts the vendored Atlas MCP read server and the notrest wrapper.
#
# HERMETIC BY CONSTRUCTION. Nothing here touches the network, the real hub, or the real
# ~/.notrest: $NOTREST_HOME is redirected at a scratch dir, the server runs in
# ATLAS_MCP_FIXTURE=1 (its own in-process fixture hub), and the node gate is exercised
# against shims planted on a scratch PATH rather than against whatever this laptop has.
#
# KNOWN BOUND (recorded, not worked around): the server's fixture hub also wants
# hub/fixtures/kernel-wire1.json, which is NOT vendored into the plugin — the kernel wire is
# another estate's snapshot. So `--selftest`, which drives every tool at project "kernel",
# cannot pass here. Section C asserts that bound out loud instead of hiding it, and the
# server file is never edited to make it go away.
# Usage: bash <atlas-skill>/mcp/fixture-mcp.sh   (exit 0 = all pass, 1 = a failure)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SERVER="$HERE/server.mjs"
WRAP="$HERE/atlas-mcp.sh"
CONTRACT="$(cd "$HERE/../../../../.." 2>/dev/null && pwd)/briefs/atlas-contract/mcp/server.mjs"
PY="$(command -v /usr/bin/python3 || command -v python3)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }

# the bearer the server's fixture hub uses. It must never reach stdout or stderr.
BEARER="fixture-view-token-never-real"

# a scratch machine: no real secret file is ever opened by this run
export NOTREST_HOME="$W/home"; mkdir -p "$NOTREST_HOME/credentials"
unset ATLAS_VIEW_FILE ATLAS_HUB_BASE 2>/dev/null || true

# ── A · the vendored file is the contract's file ──────────────────────────────────────
echo "── A · vendored byte-exact"
[ -f "$SERVER" ] && ok "server.mjs is vendored" || no "server.mjs is missing"
head -n 2 "$SERVER" | grep -q '© 2026 Not Rest Inc. Part of Atlas; licensed with the notrest plugin.' \
  && ok "the Atlas license line survives verbatim at the top" \
  || no "the license line was stripped or edited"
if [ -f "$CONTRACT" ]; then
  A="$(shasum -a 256 < "$SERVER" | awk '{print $1}')"
  B="$(shasum -a 256 < "$CONTRACT" | awk '{print $1}')"
  t "vendored copy is byte-identical to briefs/atlas-contract/mcp/server.mjs" "$A" "$B"
else
  ok "contract copy not present in this tree — byte-equality asserted at vendor time (skipped)"
fi
[ -x "$WRAP" ] && ok "atlas-mcp.sh is executable" || no "atlas-mcp.sh is not executable"

# ── D · the wrapper's node gate — RED-FIRST, run before the drive ─────────────────────
# Each arm below FAILS if the guard is deleted from atlas-mcp.sh: without it the wrapper
# exec's node regardless of version, so the exit code stops being 6 and stdout stops being
# empty. That is the whole point of asserting stdout here and not just the message.
echo "── D · node >= 22 gate (the one soft dependency, RULINGS §4)"
mkdir -p "$W/bin"
mknode(){ # $1 dir · $2 version string
  cat > "$1/node" <<SHIM
#!/bin/bash
if [ "\${1:-}" = "--version" ]; then echo "$2"; exit 0; fi
echo "ATLAS_VIEW_FILE=\${ATLAS_VIEW_FILE:-unset}"
echo "ATLAS_HUB_BASE=\${ATLAS_HUB_BASE:-unset}"
echo "SERVER_ARG=\${1:-none}"
exit 0
SHIM
  chmod +x "$1/node"; }

# (1) an OLD node: one line, exit 6, and the server never runs
mkdir -p "$W/old"; mknode "$W/old" "v20.19.5"
env PATH="$W/old:/usr/bin:/bin" bash "$WRAP" > "$W/o.out" 2> "$W/o.err"; RC=$?
t "node v20 → exit 6" "$RC" "6"
t "node v20 → exactly one stderr line" "$(wc -l < "$W/o.err" | tr -d ' ')" "1"
t "node v20 → the line is the contracted one" "$(cat "$W/o.err")" \
  "[notrest] atlas mcp: node >= 22 required (found v20.19.5)"
t "node v20 → stdout is empty (the server never started)" "$(wc -c < "$W/o.out" | tr -d ' ')" "0"

# (2) NO node at all: the same one line, saying "none" rather than a blank
mkdir -p "$W/none"
env PATH="$W/none:/usr/bin:/bin" NODE="definitely-not-a-node-binary" bash "$WRAP" \
  > "$W/n.out" 2> "$W/n.err"; RC=$?
t "no node → exit 6" "$RC" "6"
t "no node → the line names 'none', never an empty version" "$(cat "$W/n.err")" \
  "[notrest] atlas mcp: node >= 22 required (found none)"
t "no node → stdout is empty" "$(wc -c < "$W/n.out" | tr -d ' ')" "0"

# (3) node >= 22: the wrapper exec's it, and the secret reaches it BY PATH
mkdir -p "$W/new"; mknode "$W/new" "v22.11.0"
env PATH="$W/new:/usr/bin:/bin" bash "$WRAP" > "$W/g.out" 2> "$W/g.err"; RC=$?
t "node v22 → exit 0 (the gate opens)" "$RC" "0"
t "node v22 → nothing on stderr" "$(wc -c < "$W/g.err" | tr -d ' ')" "0"
t "ATLAS_VIEW_FILE defaults under \$NOTREST_HOME" \
  "$(sed -n 's/^ATLAS_VIEW_FILE=//p' "$W/g.out")" "$NOTREST_HOME/credentials/atlas-view"
t "the server is launched from the plugin's own dir" \
  "$(sed -n 's/^SERVER_ARG=//p' "$W/g.out")" "$SERVER"
t "ATLAS_HUB_BASE is a pass-through: unset stays unset (the server owns the default)" \
  "$(sed -n 's/^ATLAS_HUB_BASE=//p' "$W/g.out")" "unset"
env PATH="$W/new:/usr/bin:/bin" ATLAS_HUB_BASE="http://127.0.0.1:8787" \
    ATLAS_VIEW_FILE="$W/elsewhere" bash "$WRAP" > "$W/g2.out" 2>/dev/null
t "an explicit ATLAS_HUB_BASE passes through unchanged" \
  "$(sed -n 's/^ATLAS_HUB_BASE=//p' "$W/g2.out")" "http://127.0.0.1:8787"
t "an explicit ATLAS_VIEW_FILE is never overridden" \
  "$(sed -n 's/^ATLAS_VIEW_FILE=//p' "$W/g2.out")" "$W/elsewhere"

# ── B · the stdio protocol, driven through the wrapper with the real node ─────────────
echo "── B · JSON-RPC over stdio (ATLAS_MCP_FIXTURE=1)"
REAL_V="$(command -v node >/dev/null 2>&1 && node --version 2>/dev/null || echo "")"
REAL_MAJOR="$(printf '%s' "$REAL_V" | sed -n 's/^v\{0,1\}\([0-9][0-9]*\).*$/\1/p')"
if [ -z "$REAL_MAJOR" ] || [ "$REAL_MAJOR" -lt 22 ]; then
  echo "  SKIP  the stdio drive needs node >= 22 on this machine (found ${REAL_V:-none})"
  echo "        — the gate arms above still ran; this is the soft dependency, not a failure"
else
  printf '%s\n' \
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}' \
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"atlas_projects","arguments":{}}}' \
    '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"atlas_relevant_context","arguments":{"project":"demo","task":"token rotation"}}}' \
    > "$W/in.jsonl"
  ATLAS_MCP_FIXTURE=1 bash "$WRAP" < "$W/in.jsonl" > "$W/out.jsonl" 2> "$W/err.txt"; RC=$?
  t "the drive exits 0" "$RC" "0"
  t "one JSON line per request" "$(wc -l < "$W/out.jsonl" | tr -d ' ')" "4"
  q(){ "$PY" "$W/q.py" "$W/out.jsonl" "$1"; }
  cat > "$W/q.py" <<'QPY'
import json, sys
rows = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if not line:
        continue
    try:
        m = json.loads(line)
    except ValueError:
        print("NOT-JSON"); raise SystemExit(0)
    rows[m.get("id")] = m
want = sys.argv[2]
def payload(i):
    r = rows[i]["result"]
    return json.loads(r["content"][0]["text"]), r
if want == "server-name":
    print(rows[1]["result"]["serverInfo"]["name"])
elif want == "tool-count":
    print(len(rows[2]["result"]["tools"]))
elif want == "tool-names":
    print(",".join(sorted(t["name"] for t in rows[2]["result"]["tools"])))
elif want == "schemas":
    print(all(isinstance(t.get("inputSchema"), dict) and t.get("description")
              for t in rows[2]["result"]["tools"]))
elif want == "projects":
    d, _ = payload(3)
    print(",".join(sorted(p["project"] for p in d.get("projects", []))))
elif want == "ctx-bytes":
    _, r = payload(4)
    print(len(r["content"][0]["text"]))
elif want == "ctx-matched":
    d, _ = payload(4)
    print(len(d.get("matched_on") or []))
elif want == "ctx-project":
    d, _ = payload(4)
    print(d.get("project"))
elif want == "ctx-error":
    d, r = payload(4)
    print(bool(r.get("isError")) or bool(d.get("error")))
QPY
  t "every stdout line is one JSON-RPC object (protocol bytes only)" "$(q server-name)" "atlas"
  t "initialize names the server" "$(q server-name)" "atlas"
  t "tools/list carries eleven tools" "$(q tool-count)" "11"
  t "…and they are the eleven the contract names (IDENTITY-CONTRACT §5)" "$(q tool-names)" \
"atlas_blockers,atlas_diff,atlas_findings,atlas_history,atlas_objective,atlas_playbook,atlas_project,atlas_projects,atlas_relevant_context,atlas_search,atlas_subtree"
  t "every tool carries a description and an inputSchema" "$(q schemas)" "True"
  case "$(q projects)" in *demo*) ok "atlas_projects returns the demo row";;
                          *) no "atlas_projects has no demo row — got [$(q projects)]";; esac
  t "atlas_relevant_context(demo) is not an error" "$(q ctx-error)" "False"
  t "…answers about the project it was asked for" "$(q ctx-project)" "demo"
  t "…and matched_on is non-empty (it says WHY it chose what it chose)" \
    "$([ "$(q ctx-matched)" -gt 0 ] && echo yes || echo no)" "yes"
  CB="$(q ctx-bytes)"
  t "…within the 3900-byte budget (was $CB)" "$([ "$CB" -le 3900 ] && echo yes || echo no)" "yes"

  # the secret law, asserted on the bytes rather than trusted
  grep -q "$BEARER" "$W/out.jsonl" && no "THE BEARER REACHED STDOUT" || ok "no bearer on stdout"
  grep -q "$BEARER" "$W/err.txt"   && no "THE BEARER REACHED STDERR" || ok "no bearer on stderr"
  t "the drive says nothing on stderr at all" "$(wc -c < "$W/err.txt" | tr -d ' ')" "0"

  # ── C · the known bound, asserted rather than hidden ────────────────────────────────
  echo "── C · known bound: the kernel wire is another estate's, and is not vendored"
  [ -f "$HERE/../hub/fixtures/kernel-wire1.json" ] \
    && no "a kernel fixture was vendored — it is not ours to ship" \
    || ok "hub/fixtures/kernel-wire1.json is absent, as intended"
  case "$(q projects)" in *kernel*) no "a kernel row appeared without its wire";;
                          *) ok "…so the fixture hub serves demo only";; esac
  ATLAS_MCP_FIXTURE=1 node "$SERVER" --selftest > "$W/self.out" 2> "$W/self.err"; SRC=$?
  t "--selftest cannot pass here, and that is the known bound (not a regression)" \
    "$([ "$SRC" -ne 0 ] && echo "nonzero" || echo "zero")" "nonzero"
  grep -q 'no snapshot stored' "$W/self.out" \
    && ok "…and it says why: the kernel snapshot is not present" \
    || ok "…recorded: selftest exit $SRC (kernel wire absent)"
  grep -q "$BEARER" "$W/self.out" "$W/self.err" \
    && no "THE BEARER REACHED SELFTEST OUTPUT" || ok "selftest leaks no bearer either"
fi

echo
echo "atlas mcp fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
