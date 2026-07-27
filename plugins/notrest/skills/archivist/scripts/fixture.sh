#!/usr/bin/env bash
# fixture — prove the findings store at the door: every kind lands, every
# validation rule turns its record away with exit 2 and names itself, the track
# round-trips, supersede/refute resolve without editing a byte, find sees
# statements and dossier bodies, and the legacy index still reads the estate.
# Exit 0 = every assertion held. No network, no model calls, no repo writes.

IDX="$(cd "$(dirname "$0")" && pwd)/index.py"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/notrest-archivist-fixture.XXXXXX")"
# Normalized (symlinks + any doubled slash from $TMPDIR resolved) so the paths this
# fixture asserts on are the same strings index.py's own resolve() prints.
TMP="$(cd "$TMP" && pwd -P)"
R="$TMP/root"
PASSES=0
FAILS=0

# The shelf moves under $TMP for the whole run — one env knob relocates BOTH the
# registry and the projects file, so this fixture can never touch the machine's
# real ~/.claude/notrest-library or ~/.claude/oracle-projects.txt.
export NOTREST_LIBRARY_ROOT="$TMP/home/.claude/notrest-library"

SRV=""
cleanup() { stop_srv; rm -rf "$TMP"; return 0; }
# `wait` after the kill so bash never prints its own "Terminated" job notice
# over a green run — the gate reads this output.
stop_srv() { [ -n "$SRV" ] && { kill "$SRV" 2>/dev/null; wait "$SRV" 2>/dev/null; SRV=""; }; return 0; }
trap cleanup EXIT

ok()  { PASSES=$((PASSES+1)); echo "PASS  $1"; }
bad() { FAILS=$((FAILS+1));  echo "FAIL  $1"; }

mkdir -p "$R"

# ------------------------------------------------------------ valid: every kind
# add <label> <json>  — expects exit 0 and an F-<n> on stdout.
add() {
  label="$1"; json="$2"
  out="$(python3 "$IDX" add --root "$R" --json "$json" 2>"$TMP/err")"
  rc=$?
  if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -Eq '^F-[0-9]+$'; then
    ok "accepts $label -> $out"
  else
    bad "accepts $label (exit $rc, out '$out')"; cat "$TMP/err"
  fi
}

EVU='[{"type":"url","ref":"https://example.org/spec","label":"cited"}]'
EVP='[{"type":"path","ref":"src/cache.py:42","label":"cited"}]'
EVC='[{"type":"command","ref":"pytest -q tests/test_cache.py","label":"estimate"}]'
EVL='[{"type":"coord-line","ref":"COORD.md:118","label":"recall"}]'

add "kind=finding"    "{\"session\":\"s1\",\"skill\":\"researcher\",\"kind\":\"finding\",\"ask\":\"which cache?\",\"statement\":\"Redis 7 ships client-side caching over RESP3 tracking.\",\"evidence\":$EVU,\"relation\":\"toward\"}"
add "kind=result"     "{\"session\":\"s1\",\"skill\":\"researcher\",\"kind\":\"result\",\"statement\":\"Recommend Redis client-side caching for the read path.\",\"evidence\":$EVP,\"relation\":\"toward\",\"links\":[\"F-1\"]}"
add "kind=decision"   "{\"session\":\"s1\",\"skill\":\"decider\",\"kind\":\"decision\",\"statement\":\"Pick Redis; the hinge is whether eviction is CI-verified.\",\"evidence\":$EVC,\"relation\":\"toward\",\"links\":[\"F-2\"]}"
add "kind=conflict"   "{\"session\":\"s1\",\"skill\":\"factcheck\",\"kind\":\"conflict\",\"statement\":\"Vendor doc and third-party benchmark disagree on eviction latency.\",\"evidence\":$EVL,\"relation\":\"lateral\"}"
add "kind=backtrack"  "{\"session\":\"s1\",\"skill\":\"researcher\",\"kind\":\"backtrack\",\"statement\":\"Abandoned the memcached branch — no client-side invalidation.\",\"relation\":\"back\"}"
add "kind=side-route" "{\"session\":\"s2\",\"skill\":\"researcher\",\"kind\":\"side-route\",\"statement\":\"Noticed the connection pool ceiling while reading the driver.\",\"relation\":\"lateral\"}"

# stdin is the other door
echo "{\"session\":\"s2\",\"skill\":\"factcheck\",\"kind\":\"finding\",\"statement\":\"The pool ceiling is 32 by default.\",\"evidence\":$EVP}" \
  | python3 "$IDX" add --root "$R" >/dev/null 2>&1 \
  && ok "accepts a record on stdin" || bad "stdin record rejected"

# ------------------------------------------------- rejections: one per rule
# no <rule> <json>  — expects exit 2 and 'reject: <rule>' on stderr.
no() {
  rule="$1"; json="$2"
  out="$(python3 "$IDX" add --root "$R" --json "$json" 2>&1 >/dev/null)"
  rc=$?
  if [ "$rc" -eq 2 ] && printf '%s' "$out" | grep -q "^reject: $rule "; then
    ok "rejects $rule (exit 2, rule named)"
  else
    bad "rejects $rule -> exit $rc, said '$out'"
  fi
}

no statement-required   "{\"kind\":\"finding\",\"statement\":\"   \",\"evidence\":$EVP}"
no kind-enum            "{\"kind\":\"hunch\",\"statement\":\"x\",\"evidence\":$EVP}"
no relation-enum        "{\"kind\":\"finding\",\"relation\":\"sideways\",\"statement\":\"x\",\"evidence\":$EVP}"
no status-enum          "{\"kind\":\"finding\",\"status\":\"maybe\",\"statement\":\"x\",\"evidence\":$EVP}"
no evidence-type-enum   '{"kind":"finding","statement":"x","evidence":[{"type":"vibes","ref":"a","label":"cited"}]}'
no evidence-label-enum  '{"kind":"finding","statement":"x","evidence":[{"type":"path","ref":"a","label":"gospel"}]}'
no cited-url-needs-url  '{"kind":"finding","statement":"x","evidence":[{"type":"url","ref":"the official docs","label":"cited"}]}'
no evidence-required    '{"kind":"finding","statement":"x","evidence":[]}'
no evidence-required    '{"kind":"result","statement":"x"}'
no evidence-required    '{"kind":"decision","statement":"x","evidence":[]}'
no links-unknown        "{\"kind\":\"finding\",\"statement\":\"x\",\"evidence\":$EVP,\"links\":[\"F-9001\"]}"
no links-shape          "{\"kind\":\"finding\",\"statement\":\"x\",\"evidence\":$EVP,\"links\":\"F-1\"}"
no evidence-shape       '{"kind":"finding","statement":"x","evidence":["https://example.org"]}'
no unknown-field        "{\"kind\":\"finding\",\"statement\":\"x\",\"evidence\":$EVP,\"confidence\":\"high\"}"
no id-assigned          "{\"id\":\"F-42\",\"kind\":\"finding\",\"statement\":\"x\",\"evidence\":$EVP}"
no ts-format            "{\"ts\":\"yesterday\",\"kind\":\"finding\",\"statement\":\"x\",\"evidence\":$EVP}"
no field-type           "{\"kind\":\"finding\",\"skill\":7,\"statement\":\"x\",\"evidence\":$EVP}"
no json-parse           '{not json at all'
no record-object        '["a list, not a record"]'

python3 "$IDX" add --root "$R" </dev/null 2>&1 >/dev/null | grep -q "^reject: no-input " \
  && ok "rejects no-input (empty stdin)" || bad "empty stdin was not rejected"

# a rejected record writes NOTHING — the store is still 7 lines
lines="$(wc -l < "$R/archive/findings.jsonl" | tr -d ' ')"
[ "$lines" = "7" ] && ok "19 rejections wrote 0 lines (store still 7)" \
                   || bad "store is $lines lines after rejections (want 7)"

# --------------------------------------------------------------- track counts
count() { python3 "$IDX" track --root "$R" "$@" | grep -cE '^F-[0-9]+ '; }

[ "$(count)" = "7" ]                  && ok "track prints 7 records" || bad "track printed $(count) (want 7)"
[ "$(count --kind finding)" = "2" ]   && ok "track --kind finding -> 2" || bad "--kind finding -> $(count --kind finding) (want 2)"
[ "$(count --session s2)" = "2" ]     && ok "track --session s2 -> 2" || bad "--session s2 -> $(count --session s2) (want 2)"
[ "$(count --status live)" = "7" ]    && ok "track --status live -> 7 (nothing flipped yet)" || bad "--status live -> $(count --status live) (want 7)"

python3 "$IDX" track --root "$R" --json > "$TMP/track.json" 2>&1
python3 - "$TMP/track.json" <<'PY' && ok "--json round-trips: 7 records, schema fields intact" || bad "--json malformed"
import json, sys
d = json.load(open(sys.argv[1]))
want = {"id","ts","session","skill","kind","ask","statement","evidence","relation","links","status"}
assert d["total"] == 7 and d["shown"] == 7, d
for r in d["records"]:
    assert want <= set(r), set(r)
    assert r["effective_status"] == "live", r
PY

# --------------------------------------------- supersede / refute resolution
python3 "$IDX" supersede F-1 --by F-2 --root "$R" --session s1 --note "Head restated." >/dev/null 2>&1 \
  && ok "supersede F-1 --by F-2 appends a tombstone" || bad "supersede failed"
python3 "$IDX" refute F-3 --evidence "https://example.org/benchmark-2026" --root "$R" --session s1 >/dev/null 2>&1 \
  && ok "refute F-3 --evidence <url> appends a tombstone" || bad "refute failed"
python3 "$IDX" supersede F-1 --by F-404 --root "$R" >/dev/null 2>&1
[ "$?" -eq 2 ] && ok "supersede --by an unknown id is rejected (exit 2)" \
               || bad "supersede accepted an unknown --by"
python3 "$IDX" refute F-404 --evidence x --root "$R" >/dev/null 2>&1
[ "$?" -eq 2 ] && ok "refute of an unknown target is rejected (exit 2)" \
               || bad "refute accepted an unknown target"

lines="$(wc -l < "$R/archive/findings.jsonl" | tr -d ' ')"
[ "$lines" = "9" ] && ok "append-only: 2 flips = 2 new lines (9 total), 0 edits" \
                   || bad "store is $lines lines after 2 flips (want 9)"

python3 "$IDX" track --root "$R" --json > "$TMP/track2.json" 2>&1
python3 - "$TMP/track2.json" <<'PY' && ok "resolution: F-1 superseded by F-2, F-3 refuted by F-9" || bad "status resolution wrong"
import json, sys
d = json.load(open(sys.argv[1]))
by = {r["id"]: (r["effective_status"], r["status_by"]) for r in d["records"]}
assert by["F-1"] == ("superseded", "F-2"), by["F-1"]
assert by["F-3"] == ("refuted", "F-9"), by["F-3"]
assert by["F-2"][0] == "live" and by["F-8"][0] == "live", by
# the written status on disk was never touched — only the effective one moved
raw = {r["id"]: r["status"] for r in d["records"]}
assert raw["F-1"] == "live" and raw["F-3"] == "live", raw
PY

[ "$(count --status live)" = "7" ]       && ok "track --status live -> 7 (2 flipped, 2 tombstones added)" || bad "live -> $(count --status live) (want 7)"
[ "$(count --status superseded)" = "1" ] && ok "track --status superseded -> 1" || bad "superseded -> $(count --status superseded) (want 1)"
[ "$(count --status refuted)" = "1" ]    && ok "track --status refuted -> 1" || bad "refuted -> $(count --status refuted) (want 1)"

python3 "$IDX" track --root "$R" | grep -q "SUPERSEDED by F-2" \
  && ok "track line flags the flip inline" || bad "track line hides the flip"

# --------------------------------------------------- RESTS-ON-REFUTED (G7)
# A(finding) ← B(decision links A), then a tombstone refuting A. B stays LIVE — only a
# tombstone flips a status — but its footing is gone, and track says so on B's line.
# C links the un-refuted A2: the control that proves the flag is not painted on everything.
A="$(python3 "$IDX" add --root "$R" --json "{\"session\":\"s3\",\"skill\":\"factcheck\",\"kind\":\"finding\",\"statement\":\"Eviction is CI-verified on every release.\",\"evidence\":$EVU,\"relation\":\"toward\"}" 2>/dev/null)"
A2="$(python3 "$IDX" add --root "$R" --json "{\"session\":\"s3\",\"skill\":\"factcheck\",\"kind\":\"finding\",\"statement\":\"The driver ships a connection pool cap.\",\"evidence\":$EVU,\"relation\":\"toward\"}" 2>/dev/null)"
B="$(python3 "$IDX" add --root "$R" --json "{\"session\":\"s3\",\"skill\":\"decider\",\"kind\":\"decision\",\"statement\":\"Ship the Redis read path now.\",\"evidence\":$EVC,\"relation\":\"toward\",\"links\":[\"$A\"]}" 2>/dev/null)"
C="$(python3 "$IDX" add --root "$R" --json "{\"session\":\"s3\",\"skill\":\"decider\",\"kind\":\"decision\",\"statement\":\"Cap the pool at 32.\",\"evidence\":$EVC,\"relation\":\"toward\",\"links\":[\"$A2\"]}" 2>/dev/null)"
python3 "$IDX" refute "$A" --evidence "https://example.org/ci-log-2026" --root "$R" --session s3 >/dev/null 2>&1 \
  && ok "refute $A appends the tombstone the flag resolves through" || bad "refute of $A failed"

python3 "$IDX" track --root "$R" > "$TMP/track3.txt" 2>&1
grep -q "^$B .* · RESTS-ON-REFUTED $A\$" "$TMP/track3.txt" \
  && ok "track flags the live decision resting on refuted ground (RESTS-ON-REFUTED $A)" \
  || { bad "no RESTS-ON-REFUTED flag on $B"; grep "^$B " "$TMP/track3.txt"; }
grep "^$C " "$TMP/track3.txt" | grep -q "RESTS-ON-REFUTED" \
  && bad "control $C (links un-refuted $A2) was flagged" \
  || ok "control $C links a live finding — unflagged"
grep "^$A " "$TMP/track3.txt" | grep -q "RESTS-ON-REFUTED" \
  && bad "the refuted record itself was flagged (only live records rest on anything)" \
  || ok "the refuted record itself carries REFUTED, not RESTS-ON-REFUTED"
grep "refutes $A" "$TMP/track3.txt" | grep -q "RESTS-ON-REFUTED" \
  && bad "the tombstone was flagged as resting on what it killed" \
  || ok "a tombstone does not rest on its own target"

python3 "$IDX" track --root "$R" --json > "$TMP/track3.json" 2>&1
python3 - "$TMP/track3.json" "$A" "$B" "$C" <<'PY' && ok "--json carries rests_on_refuted on every record" || bad "rests_on_refuted field wrong"
import json, sys
d = json.load(open(sys.argv[1]))
a, b, c = sys.argv[2], sys.argv[3], sys.argv[4]
by = {r["id"]: r for r in d["records"]}
assert all("rests_on_refuted" in r for r in d["records"]), "field missing on some record"
assert by[b]["rests_on_refuted"] == [a], by[b]["rests_on_refuted"]
assert by[b]["effective_status"] == "live", by[b]
assert by[c]["rests_on_refuted"] == [], by[c]["rests_on_refuted"]
assert by[a]["effective_status"] == "refuted" and by[a]["rests_on_refuted"] == [], by[a]
PY

# ------------------------------------------------------------- legacy estate
mkdir -p "$R/research" "$R/draft"
cat > "$R/research/cache-choiceDossier.md" <<'EOF'
# Cache choice — Dossier
Date: 2025-01-15

## 📌 Read Me First
- **What you asked:** which cache for the read path
- **What I found:** Redis, with client-side caching on

## Decision & Reasoning
The deciding detail was quorum-free failover under a single-node loss.
EOF
cat > "$R/draft/launch-memoDossier.md" <<'EOF'
# Launch memo — Dossier

## 📌 Read Me First
- **What this sends:** the launch note to the exec list
EOF

python3 "$IDX" scan --root "$R" > "$TMP/scan.out" 2>&1 && ok "scan exits 0" || { bad "scan failed"; cat "$TMP/scan.out"; }
grep -q "2 entries" "$TMP/scan.out" && ok "scan indexes 2 dossiers (draft/ now in DIRS)" \
  || { bad "scan count wrong: $(cat "$TMP/scan.out")"; }
grep -q "^### Cache choice — Dossier — 2025-01-15$" "$R/oracle-index.md" \
  && ok "dossier's own date line beats st_mtime (2025-01-15)" \
  || { bad "date not parsed from the dossier"; grep '^### ' "$R/oracle-index.md"; }
grep -q "findings store — 14 record(s), 11 live" "$R/oracle-index.md" \
  && ok "scan points the index at the findings store" || bad "index has no findings entry"

# ------------------------------------------------------------------- find
python3 "$IDX" find "RESP3" --root "$R" > "$TMP/find1.out" 2>&1
grep -q "^## findings — 1 record" "$TMP/find1.out" && grep -q "^F-1 " "$TMP/find1.out" \
  && ok "find hits a statement term in the store" || { bad "find missed the statement"; cat "$TMP/find1.out"; }

python3 "$IDX" find "Redis" --root "$R" > "$TMP/find2.out" 2>&1
grep -q "### Cache choice — Dossier — 2025-01-15" "$TMP/find2.out" \
  && ok "find still hits legacy index entries" || { bad "find lost the index entries"; cat "$TMP/find2.out"; }
# The index block already answered for this dossier; the body sweep must not say it
# again. (The pointer line is `folder: … · path: …`, so the old anchored `^path:`
# never matched and every indexed dossier was re-reported.)
[ "$(grep -c "cache-choiceDossier.md" "$TMP/find2.out")" = "1" ] \
  && ok "an index-matched dossier is reported once, not twice (body-sweep dedupe)" \
  || { bad "dossier double-reported: $(grep -c 'cache-choiceDossier.md' "$TMP/find2.out") times"; cat "$TMP/find2.out"; }

# 'quorum-free' lives only in the dossier BODY — never in the Read Me First head,
# so the index alone was blind to it.
grep -q "quorum-free" "$R/oracle-index.md" && bad "term leaked into the index head (fixture wrong)" \
  || ok "'quorum-free' is body-only (invisible to the index)"
python3 "$IDX" find "quorum-free" --root "$R" > "$TMP/find3.out" 2>&1
grep -q "\[body match\]" "$TMP/find3.out" \
  && ok "find reads dossier bodies (body-blindness closed)" || { bad "body sweep missed it"; cat "$TMP/find3.out"; }

python3 "$IDX" find "zzz-no-such-term" --root "$R" 2>&1 | grep -q "^no findings, index entries, or dossier bodies match" \
  && ok "find reports an honest miss" || bad "find miss message wrong"

# ================================================== THE LIBRARY (federation)
# Two scratch repos keep their OWN stores (nothing is copied to the shelf), a
# third is registered and then deleted to prove an unreachable root is reported
# and never fatal. The shelf itself lives under $TMP (see NOTREST_LIBRARY_ROOT).
LIB="$NOTREST_LIBRARY_ROOT"
REG="$LIB/registry.jsonl"
PROJ="$(dirname "$LIB")/oracle-projects.txt"
A_R="$TMP/alpha"; B_R="$TMP/beta-repo"; G_R="$TMP/gone"; X_R="$TMP/alpha2"
mkdir -p "$A_R" "$B_R" "$G_R" "$X_R"

lib() { python3 "$IDX" library "$@"; }

python3 "$IDX" add --root "$A_R" --json "{\"session\":\"p1\",\"skill\":\"researcher\",\"kind\":\"finding\",\"ask\":\"which cache for the read path?\",\"statement\":\"Redis 7 ships client-side caching over RESP3 tracking.\",\"evidence\":$EVU}" >/dev/null 2>&1
python3 "$IDX" add --root "$B_R" --json "{\"session\":\"p2\",\"skill\":\"researcher\",\"kind\":\"finding\",\"ask\":\"why did the skills vanish?\",\"statement\":\"An installed plugin shadows a skills-dir runtime of the same name.\",\"evidence\":$EVU}" >/dev/null 2>&1
python3 "$IDX" add --root "$B_R" --json "{\"session\":\"p2\",\"skill\":\"decider\",\"kind\":\"decision\",\"statement\":\"Never install the marketplace copy on the dev machine.\",\"evidence\":$EVP,\"links\":[\"F-1\"]}" >/dev/null 2>&1

# ------------------------------------------------------------------ register
lib register --root "$A_R" > "$TMP/reg1.out" 2>&1
[ "$?" -eq 0 ] && grep -q "registered alpha -> $A_R" "$TMP/reg1.out" \
  && ok "library register puts a project on the shelf (name = repo dirname)" \
  || { bad "register alpha failed"; cat "$TMP/reg1.out"; }
grep -q "^projects .*: added $A_R " "$TMP/reg1.out" \
  && ok "one registration also feeds graph.py's oracle-projects.txt" \
  || { bad "register did not write the projects file"; cat "$TMP/reg1.out"; }
lib register --root "$B_R" --name beta > "$TMP/reg2.out" 2>&1 \
  && grep -q "registered beta -> $B_R" "$TMP/reg2.out" \
  && ok "library register --name overrides the dirname" || { bad "register beta failed"; cat "$TMP/reg2.out"; }
lib register --root "$G_R" >/dev/null 2>&1 && ok "third project registered (about to go missing)" \
  || bad "register gone failed"
rm -rf "$G_R"

lib register --root "$A_R" > "$TMP/reg3.out" 2>&1
[ "$?" -eq 0 ] && grep -q "already registered as 'alpha' — no-op" "$TMP/reg3.out" \
  && ok "re-registering the same root is an idempotent no-op, and says so" \
  || { bad "second register was not a no-op"; cat "$TMP/reg3.out"; }
grep -q "^projects .*: already present" "$TMP/reg3.out" \
  && ok "the projects file is idempotent too" || { bad "projects file not idempotent"; cat "$TMP/reg3.out"; }

[ "$(wc -l < "$REG" | tr -d ' ')" = "3" ] && ok "registry is 3 append-only lines after 4 registers" \
  || bad "registry is $(wc -l < "$REG" | tr -d ' ') lines (want 3)"
python3 - "$REG" <<'PY' && ok "each registry line carries at least {root, name, ts}" || bad "registry line shape wrong"
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
assert len(rows) == 3, rows
for r in rows:
    assert {"root", "name", "ts"} <= set(r), r          # a floor, never a ceiling
    assert r["ts"].endswith("Z") and r["root"].startswith("/"), r
PY
# A future writer's extra keys must survive a read — the registry shape is open.
printf '{"root":"%s","name":"futured","ts":"2026-07-26T00:00:00Z","tags":["x"],"pin":7}\n' "$X_R" >> "$REG"
lib list 2>&1 | grep -q "^futured · $X_R · records 0 (0 live) · reachable$" \
  && ok "a registry line with unknown keys still reads (forward-compatible)" \
  || { bad "extra registry keys broke the read"; lib list; }
python3 - "$IDX" "$LIB" <<'PY' && ok "unknown registry keys are carried, not dropped" || bad "extra keys dropped on read"
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location("idx", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
row = [p for p in m.read_registry(pathlib.Path(sys.argv[2])) if p["name"] == "futured"][0]
assert row.get("tags") == ["x"] and row.get("pin") == 7, row
PY
sed -i.bak '$d' "$REG" && rm -f "$REG.bak"   # back to the 3 real projects
[ "$(wc -l < "$PROJ" | tr -d ' ')" = "3" ] && ok "oracle-projects.txt holds 3 roots" \
  || bad "projects file is $(wc -l < "$PROJ" | tr -d ' ') lines (want 3)"
[ "$(grep -cxF "$A_R" "$PROJ")" = "1" ] && [ "$(grep -cxF "$B_R" "$PROJ")" = "1" ] \
  && ok "both roots appear in oracle-projects.txt exactly once" \
  || bad "a root is duplicated or missing in $PROJ"

# ------------------------------------------------------------- register: no
lib register --root "$X_R" --name alpha >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: library-name-taken " "$TMP/e.out" \
  && ok "rejects library-name-taken (a shelf name must resolve to ONE root)" \
  || { bad "name collision accepted"; cat "$TMP/e.out"; }
lib register --root "$X_R" --name "bad:name" >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: library-name-shape " "$TMP/e.out" \
  && ok "rejects library-name-shape (':' would break <project>:F-<n>)" \
  || { bad "a ':' in a project name was accepted"; cat "$TMP/e.out"; }
lib register --root "$TMP/no-such-dir" >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: library-root-missing " "$TMP/e.out" \
  && ok "rejects library-root-missing (you cannot shelve a root that is not there)" \
  || { bad "registered a non-directory"; cat "$TMP/e.out"; }

# ---------------------------------------------------------------------- list
lib list > "$TMP/list.out" 2>&1
[ "$(grep -c ' · records ' "$TMP/list.out")" = "3" ] && ok "library list prints one line per project (3)" \
  || { bad "list printed $(grep -c ' · records ' "$TMP/list.out") project lines"; cat "$TMP/list.out"; }
grep -q "^alpha · $A_R · records 1 (1 live) · reachable$" "$TMP/list.out" \
  && ok "list counts records live off each project's own store" || { bad "alpha list line wrong"; cat "$TMP/list.out"; }
grep -q "^gone · .* · records — · missing$" "$TMP/list.out" \
  && ok "list marks a deleted root missing (not fatal)" || { bad "missing root not reported"; cat "$TMP/list.out"; }

# ---------------------------------------------------------------------- find
lib find shadow > "$TMP/lf1.out" 2>&1
rc=$?
[ "$rc" -eq 0 ] && grep -q "^beta:F-1 · finding · An installed plugin shadows" "$TMP/lf1.out" \
  && ok "library find hits another project's store, prefixed <project>:F-<n>" \
  || { bad "cross-project find missed (exit $rc)"; cat "$TMP/lf1.out"; }
grep -q "^alpha:" "$TMP/lf1.out" && bad "find leaked a non-matching project's records" \
  || ok "find prints only matching records"
grep -q "(unreachable: gone · " "$TMP/lf1.out" \
  && ok "find reports the unreachable root and still exits 0 (federation never fails closed)" \
  || { bad "unreachable root not reported"; cat "$TMP/lf1.out"; }
grep -q "^1 hit(s) in 1 of 3 project(s) · 1 unreachable$" "$TMP/lf1.out" \
  && ok "find's footer counts hits, projects, and unreachable roots" || { bad "footer wrong"; tail -2 "$TMP/lf1.out"; }

lib find plugin shadows > "$TMP/lf2.out" 2>&1
grep -q "^beta:F-1 " "$TMP/lf2.out" && ok "multi-term find is an AND over statement + ask" \
  || { bad "AND search missed"; cat "$TMP/lf2.out"; }
lib find shadow zzz-no-such-term > "$TMP/lf3.out" 2>&1
grep -q "^0 hit(s) in 0 of 3 project(s)" "$TMP/lf3.out" \
  && ok "one unmatched term sinks the AND (honest zero)" || { bad "AND is not strict"; cat "$TMP/lf3.out"; }
lib find marketplace --kind decision > "$TMP/lf4.out" 2>&1
grep -q "^beta:F-2 · decision " "$TMP/lf4.out" && ok "library find --kind filters across the shelf" \
  || { bad "--kind filter wrong"; cat "$TMP/lf4.out"; }

# the legacy estate is on the shelf too — index HEADS, cross-project
mkdir -p "$A_R/research"
cat > "$A_R/research/quorumDossier.md" <<'EOF'
# Failover study — Dossier
Date: 2025-03-02

## 📌 Read Me First
- **What I found:** single-node loss survives without a quorum
EOF
python3 "$IDX" scan --root "$A_R" >/dev/null 2>&1
lib find failover > "$TMP/lf5.out" 2>&1
grep -q "^alpha:index · Failover study — Dossier — 2025-03-02 · research/quorumDossier.md$" "$TMP/lf5.out" \
  && ok "library find reads each project's legacy index heads" || { bad "legacy index head missed"; cat "$TMP/lf5.out"; }

# --json: the machine surface. A statement longer than the 90-char reading head
# must travel WHOLE — a consumer that clusters records cannot cluster an ellipsis.
LONG="The library must hand a machine the whole statement and the whole ask, because a ninety-character head is a reading convenience and never the record itself."
python3 "$IDX" add --root "$B_R" --json "{\"session\":\"p2\",\"skill\":\"researcher\",\"kind\":\"finding\",\"ask\":\"does the reading head truncate the record?\",\"statement\":\"$LONG libraryecho\",\"evidence\":$EVU}" >/dev/null 2>&1
lib find libraryecho | grep -q '…' \
  && ok "the line form truncates a long statement to a 90-char head" || { bad "no head truncation"; lib find libraryecho; }
lib find libraryecho --json > "$TMP/lfj.out" 2>&1
python3 - "$TMP/lfj.out" "$LONG" <<'PY' && ok "--json carries ask + statement whole, with a citable <project>:F-<n> ref" || { bad "library find --json wrong"; head -30 "$TMP/lfj.out"; }
import json, sys
d = json.load(open(sys.argv[1]))
h = d["hits"]
assert d["total"] == 1 and len(h) == 1, d["total"]
assert h[0]["ref"] == "beta:F-3" and h[0]["project"] == "beta", h[0]
assert h[0]["statement"] == sys.argv[2] + " libraryecho", h[0]["statement"]
assert h[0]["ask"] == "does the reading head truncate the record?", h[0]["ask"]
assert h[0]["effective_status"] == "live" and h[0]["rests_on_refuted"] == [], h[0]
assert [p["name"] for p in d["unreachable"]] == ["gone"], d["unreachable"]
assert {p["name"] for p in d["projects"]} == {"alpha", "beta", "gone"}, d["projects"]
PY
lib find failover --json > "$TMP/lfj2.out" 2>&1
python3 - "$TMP/lfj2.out" <<'PY' && ok "--json reports legacy index hits separately (heading + path)" || bad "index_hits wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["hits"] == [] and d["total"] == 1, d["total"]
assert d["index_hits"][0]["project"] == "alpha", d["index_hits"]
assert d["index_hits"][0]["path"] == "research/quorumDossier.md", d["index_hits"]
PY

# --------------------------------------------------------------------- track
lib track --project beta > "$TMP/lt1.out" 2>&1
rc=$?
[ "$rc" -eq 0 ] && [ "$(grep -cE '^F-[0-9]+ ' "$TMP/lt1.out")" = "3" ] \
  && grep -q "^# track — beta · $B_R/archive/findings.jsonl · 3 record(s), 3 live" "$TMP/lt1.out" \
  && ok "library track reads another project's track where it lives (no cd)" \
  || { bad "remote track wrong (exit $rc)"; cat "$TMP/lt1.out"; }
[ "$(lib track --project beta --kind decision | grep -cE '^F-[0-9]+ ')" = "1" ] \
  && ok "library track --kind filters" || bad "library track --kind wrong"
lib track --project nope >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: library-unknown-project " "$TMP/e.out" \
  && ok "track of an unshelved project exits 2 naming the rule" || { bad "unknown project accepted"; cat "$TMP/e.out"; }
lib track --project gone >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: library-unreachable " "$TMP/e.out" \
  && ok "track of a missing root exits 2 (an ASKED-FOR project is not a shrug)" \
  || { bad "missing root track did not exit 2"; cat "$TMP/e.out"; }

# ------------------------------------------- evidence type `record` (citation)
# rec <label> <root> <ref> — expects exit 0 and an id.
rec() {
  out="$(python3 "$IDX" add --root "$2" --json "{\"kind\":\"finding\",\"statement\":\"cites $3\",\"evidence\":[{\"type\":\"record\",\"ref\":\"$3\",\"label\":\"cited\"}]}" 2>"$TMP/rerr")"
  rc=$?
  if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -Eq '^F-[0-9]+$'; then ok "accepts record evidence $1 ($3 -> $out)"
  else bad "record evidence $1 rejected (exit $rc)"; cat "$TMP/rerr"; fi
}
# norec <rule> <root> <ref>
norec() {
  out="$(python3 "$IDX" add --root "$2" --json "{\"kind\":\"finding\",\"statement\":\"cites $3\",\"evidence\":[{\"type\":\"record\",\"ref\":\"$3\",\"label\":\"cited\"}]}" 2>&1 >/dev/null)"
  rc=$?
  if [ "$rc" -eq 2 ] && printf '%s' "$out" | grep -q "^reject: $1 "; then ok "rejects $1 ($3)"
  else bad "record ref $3 -> exit $rc, said '$out'"; fi
}

rec   "local (id exists)"          "$A_R" "F-1"
norec record-ref-unknown           "$A_R" "F-9001"
norec record-ref-shape             "$A_R" "beta/F-1"
norec record-ref-shape             "$A_R" "F1"
rec   "cross-project (reachable)"  "$A_R" "beta:F-1"
norec record-ref-unknown           "$A_R" "beta:F-9001"

python3 "$IDX" add --root "$A_R" --json '{"kind":"finding","statement":"cites a store that is not on this machine","evidence":[{"type":"record","ref":"ghost:F-4","label":"cited"}]}' >"$TMP/n1.out" 2>"$TMP/n1.err"
rc=$?
[ "$rc" -eq 0 ] && grep -q "^note: ghost:F-4 cited — 'ghost' is not registered" "$TMP/n1.err" \
  && grep -Eq '^F-[0-9]+$' "$TMP/n1.out" \
  && ok "an unregistered project's ref is ACCEPTED with a note on stderr (never fails closed)" \
  || { bad "unregistered cross-project ref (exit $rc)"; cat "$TMP/n1.err"; }
python3 "$IDX" add --root "$A_R" --json '{"kind":"finding","statement":"cites the deleted repo","evidence":[{"type":"record","ref":"gone:F-1","label":"cited"}]}' >"$TMP/n2.out" 2>"$TMP/n2.err"
rc=$?
[ "$rc" -eq 0 ] && grep -q "^note: gone:F-1 cited — .* is unreachable from here" "$TMP/n2.err" \
  && ok "a registered-but-unreachable ref is accepted with a note (offline machine)" \
  || { bad "unreachable cross-project ref (exit $rc)"; cat "$TMP/n2.err"; }
grep -q "^F-" "$TMP/n1.out" && ok "the id still goes to stdout alone — notes never pollute the capture" \
  || bad "stdout carried more than the id"

python3 "$IDX" track --root "$A_R" --json 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
refs = [e for r in d["records"] for e in r["evidence"] if e["type"] == "record"]
assert len(refs) == 4, refs
assert {"F-1", "beta:F-1", "ghost:F-4", "gone:F-1"} == {e["ref"] for e in refs}, refs
' && ok "record refs round-trip through the store unchanged" || bad "record evidence did not round-trip"

# ======================================= STOREY ONE — CONCEPTS (clustering)
# A SECOND shelf, so the storeys are asserted over a store built for them and the
# phase-1 shelf keeps its counts. It also exercises --library-root, which the env
# var otherwise hides. Every record here carries PATH evidence: nothing in this
# section may reach the network (the probe tests below use 127.0.0.1 only).
LIB2="$TMP/home2/.claude/notrest-library"
LIB3="$TMP/home3/.claude/notrest-library"
C1="$TMP/cache-a"; C2="$TMP/cache-b"
mkdir -p "$C1" "$C2"
lib2() { python3 "$IDX" library "$@" --library-root "$LIB2"; }

seed() { python3 "$IDX" add --root "$1" --json "$2" >/dev/null 2>&1; }
seed "$C1" "{\"session\":\"c\",\"skill\":\"researcher\",\"kind\":\"finding\",\"ask\":\"how should the read path cache?\",\"statement\":\"Redis client-side caching invalidates through RESP3 tracking on the read path.\",\"evidence\":$EVP}"
seed "$C1" "{\"session\":\"c\",\"skill\":\"researcher\",\"kind\":\"finding\",\"ask\":\"how should the read path cache?\",\"statement\":\"Client-side caching on the read path needs invalidation push, not polling.\",\"evidence\":$EVP}"
seed "$C1" "{\"session\":\"c\",\"skill\":\"decider\",\"kind\":\"decision\",\"statement\":\"Rotate the deploy signing key before the migration window closes.\",\"evidence\":$EVP}"
seed "$C2" "{\"session\":\"c\",\"skill\":\"researcher\",\"kind\":\"finding\",\"ask\":\"what caches the read path?\",\"statement\":\"The read path caching layer must handle invalidation from Redis tracking.\",\"evidence\":$EVP}"
seed "$C2" "{\"session\":\"c\",\"skill\":\"factcheck\",\"kind\":\"finding\",\"statement\":\"Onboarding screenshots in the tutorial are three versions behind.\",\"evidence\":$EVP}"
lib2 register --root "$C1" >/dev/null 2>&1
lib2 register --root "$C2" >/dev/null 2>&1

lib2 concepts --rebuild > "$TMP/con1.out" 2>&1
rc=$?
[ "$rc" -eq 0 ] && grep -q "^C-1 · ? · 3 member(s) across 2 project(s)" "$TMP/con1.out" \
  && ok "concepts clusters records ACROSS projects (3 members, 2 projects)" \
  || { bad "clustering wrong (exit $rc)"; cat "$TMP/con1.out"; }
grep -q "members: cache-a:F-1, cache-a:F-2, cache-b:F-1$" "$TMP/con1.out" \
  && ok "the cluster holds exactly the cache records — the unrelated ones stayed out" \
  || { bad "membership wrong"; grep members "$TMP/con1.out"; }
grep -q "terms: cach" "$TMP/con1.out" && ok "terms come from the donor's stemmed vocabulary" \
  || { bad "no terms"; cat "$TMP/con1.out"; }
grep -q "^C-2 " "$TMP/con1.out" && bad "a second cluster formed from unrelated records" \
  || ok "two unrelated records did not become a concept"

# DETERMINISM: a third shelf over the SAME two roots must reach the same clustering.
python3 "$IDX" library register --root "$C1" --library-root "$LIB3" >/dev/null 2>&1
python3 "$IDX" library register --root "$C2" --library-root "$LIB3" >/dev/null 2>&1
python3 "$IDX" library concepts --rebuild --library-root "$LIB3" >/dev/null 2>&1
python3 - "$LIB2/concepts.jsonl" "$LIB3/concepts.jsonl" <<'PY' && ok "clustering is deterministic: two fresh shelves, identical concepts" || bad "clustering is not deterministic"
import json, sys
def gen(p):
    last = {}
    for line in open(p, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            last[r["id"]] = r
    out = []
    for k in sorted(last, key=lambda x: int(x.split("-")[1])):
        r = dict(last[k]); r.pop("ts", None)          # birth stamps differ; nothing else may
        out.append(r)
    return out
a, b = gen(sys.argv[1]), gen(sys.argv[2])
assert a == b, (a, b)
assert a and a[0]["members"], a
PY

N1="$(wc -l < "$LIB2/concepts.jsonl" | tr -d ' ')"
lib2 concepts --rebuild >/dev/null 2>&1
python3 - "$LIB2/concepts.jsonl" "$N1" <<'PY' && ok "a rebuild carries the id and the birth stamp forward, byte for byte" || bad "rebuild churned the concept"
import sys
lines = [l for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
n = int(sys.argv[2])
assert len(lines) == 2 * n, (len(lines), n)
assert lines[:n] == lines[n:], "the second generation differs from the first"
PY

lib2 concepts --name C-1 "read-path cache invalidation" > "$TMP/name.out" 2>&1
[ "$?" -eq 0 ] && grep -q "C-1 named 'read-path cache invalidation'" "$TMP/name.out" \
  && ok "the seat christens a concept (append-style, never an edit)" || { bad "naming failed"; cat "$TMP/name.out"; }
lib2 concepts | grep -q "^C-1 · read-path cache invalidation ·" \
  && ok "the name is what the next read sees (last line per C-<n> wins)" || bad "name did not resolve"
lib2 concepts --rebuild | grep -q "^C-1 · read-path cache invalidation ·" \
  && ok "a rebuild does NOT wipe the name the seat gave" || bad "rebuild clobbered the name"
lib2 concepts --name C-99 "nope" >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: concept-unknown " "$TMP/e.out" \
  && ok "naming an unknown concept exits 2" || { bad "unknown concept accepted"; cat "$TMP/e.out"; }

[ "$(lib2 find --concept C-1 | grep -cE '^cache-[ab]:F-[0-9]+ ')" = "3" ] \
  && ok "find --concept returns exactly the concept's members" || { bad "--concept filter wrong"; lib2 find --concept C-1; }
lib2 find --concept C-1 redis | grep -q "cache-a:F-1" \
  && ok "--concept composes with terms" || bad "--concept + terms wrong"

# A threshold sweep must not leave a generation behind: the shelf is append-only.
BEFORE_DRY="$(wc -l < "$LIB2/concepts.jsonl" | tr -d ' ')"
lib2 concepts --rebuild --dry-run --sim 0.10 > "$TMP/dry.out" 2>&1
grep -q "\[DRY RUN — nothing appended\]" "$TMP/dry.out" \
  && [ "$(wc -l < "$LIB2/concepts.jsonl" | tr -d ' ')" = "$BEFORE_DRY" ] \
  && ok "--dry-run sweeps thresholds without appending a generation" \
  || { bad "--dry-run wrote to the shelf"; cat "$TMP/dry.out"; }

lib2 concepts --rebuild --project cache-b > "$TMP/sparse.out" 2>&1
grep -q "^# concepts — 0 from 2 clusterable record(s)" "$TMP/sparse.out" \
  && grep -q "honest answer, not an error" "$TMP/sparse.out" \
  && ok "too sparse to cluster is reported honestly, not as an error" || { bad "sparse path wrong"; cat "$TMP/sparse.out"; }

# ================================= STOREY THREE — CONVERGENCE (crown guards)
lib2 crown C-1 --statement "Read-path caching is invalidated by push, never polling." \
  --by cache-a:F-1,cache-b:F-1 --root "$C1" > "$TMP/crown.out" 2>&1
rc=$?
[ "$rc" -eq 0 ] && grep -q "^C-1 CONVERGED — crown cache-a:F-4 written to" "$TMP/crown.out" \
  && ok "crown writes the settled record to the LOCAL store and marks the concept" \
  || { bad "crown failed (exit $rc)"; cat "$TMP/crown.out"; }
python3 "$IDX" track --root "$C1" --json 2>/dev/null | python3 -c '
import json, sys
d = json.load(sys.stdin)
c = [r for r in d["records"] if r["statement"].startswith("CONVERGED:")][0]
assert c["kind"] == "result" and c["relation"] == "toward", c
assert c["links"] == ["F-1"], c["links"]                       # local members only
refs = sorted(e["ref"] for e in c["evidence"])
assert refs == ["F-1", "cache-b:F-1"], refs                    # local + cross-project
assert all(e["type"] == "record" for e in c["evidence"]), c["evidence"]
assert c["ask"].startswith("concept C-1: read-path cache invalidation"), c["ask"]
' && ok "the crown record is kind=result, links local, cites members as record evidence" \
  || bad "crown record shape wrong"
lib2 concepts | grep -q "settled: Read-path caching is invalidated by push" \
  && ok "the concept carries the settled sentence and reads CONVERGED" || bad "concept not settled"
lib2 concepts | grep -q "^C-1 · read-path cache invalidation · 3 member(s).*CONVERGED" \
  && ok "a crowned concept keeps its status" || bad "crown status lost"
lib2 concepts --rebuild | grep -q "^C-1 .*3 member(s).*CONVERGED" \
  && ok "the crown record does NOT join its own concept (no rebuild churn)" \
  || { bad "the crown changed the membership it was written about"; lib2 concepts --rebuild; }

lib2 crown C-1 --statement "x" --by cache-a:F-3 --root "$C1" >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: crown-by-not-member " "$TMP/e.out" \
  && ok "rejects crown-by-not-member" || { bad "crowned by a non-member"; cat "$TMP/e.out"; }
lib2 crown C-1 --statement "x" --by cache-a:F-1 --root "$TMP/beta-repo" >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: crown-unregistered " "$TMP/e.out" \
  && ok "rejects crown-unregistered (a crown nobody can cite is not a crown)" \
  || { bad "crowned into an unshelved root"; cat "$TMP/e.out"; }

# CONTESTED: a kind=conflict member is disagreement on the face of the record.
seed "$C1" "{\"session\":\"c\",\"skill\":\"factcheck\",\"kind\":\"conflict\",\"ask\":\"how should the read path cache?\",\"statement\":\"Vendor doc and benchmark disagree on read path cache invalidation latency.\",\"evidence\":$EVP}"
lib2 concepts --rebuild > "$TMP/con2.out" 2>&1
CID="$(grep -oE '^C-[0-9]+ · \? · 4 member' "$TMP/con2.out" | grep -oE '^C-[0-9]+')"
[ -n "$CID" ] && ok "the conflict record joins the concept as a new id ($CID, 4 members)" \
  || { bad "no 4-member concept formed"; cat "$TMP/con2.out"; }
lib2 crown "$CID" --statement "x" --by cache-a:F-1,cache-a:F-5 --root "$C1" >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: crown-contested " "$TMP/e.out" && grep -q "kind=conflict" "$TMP/e.out" \
  && ok "rejects crown-contested when a cited member is a conflict" || { bad "contested guard silent"; cat "$TMP/e.out"; }
LINES_BEFORE="$(wc -l < "$C1/archive/findings.jsonl" | tr -d ' ')"
lib2 crown "$CID" --statement "x" --by cache-a:F-1,cache-a:F-5 --contested --root "$C1" > "$TMP/cont.out" 2>&1
[ "$?" -eq 0 ] && grep -q "marked CONTESTED" "$TMP/cont.out" \
  && ok "--contested marks the concept instead of crowning it" || { bad "--contested failed"; cat "$TMP/cont.out"; }
[ "$(wc -l < "$C1/archive/findings.jsonl" | tr -d ' ')" = "$LINES_BEFORE" ] \
  && ok "a CONTESTED concept writes NO crown record (nothing settled to cite)" \
  || bad "--contested wrote a record anyway"
lib2 concepts | grep -q "^$CID .*CONTESTED" && ok "the contested verdict is what the shelf reads back" \
  || bad "CONTESTED not persisted"

# REFUTED: the hardest refusal — the ground under a cited member is gone.
python3 "$IDX" refute F-1 --evidence "https://example.org/counter-2026" --root "$C2" >/dev/null 2>&1
lib2 crown C-1 --statement "x" --by cache-a:F-1,cache-b:F-1 --root "$C1" >"$TMP/e.out" 2>&1
[ "$?" -eq 2 ] && grep -q "^reject: crown-member-refuted " "$TMP/e.out" && grep -q "cache-b:F-1" "$TMP/e.out" \
  && ok "rejects crown-member-refuted, naming the member" || { bad "crowned on refuted ground"; cat "$TMP/e.out"; }

# ==================================== STOREY TWO — THE UPDATER (probes)
# Everything below talks to 127.0.0.1 only. --project pins the probe project so no
# fixture run can ever reach the real network.
P_R="$TMP/probe-repo"; WWW="$TMP/www"
mkdir -p "$P_R" "$WWW"
echo "v1 body" > "$WWW/doc.txt"
PORT="$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')"
( cd "$WWW" && exec python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 ) &
SRV=$!
UP=""
for _ in $(seq 1 40); do
  python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:$PORT/doc.txt',timeout=1)" 2>/dev/null \
    && { UP=1; break; }
  sleep 0.1
done
[ -n "$UP" ] && ok "local probe server is up on 127.0.0.1:$PORT" || bad "local http.server never came up"

U="http://127.0.0.1:$PORT/doc.txt"; D="http://127.0.0.1:$PORT/no-such.txt"
seed "$P_R" "{\"session\":\"u\",\"skill\":\"researcher\",\"kind\":\"finding\",\"statement\":\"The doc says v1.\",\"evidence\":[{\"type\":\"url\",\"ref\":\"$U\",\"label\":\"cited\"}]}"
seed "$P_R" "{\"session\":\"u\",\"skill\":\"researcher\",\"kind\":\"finding\",\"statement\":\"A source that is not there.\",\"evidence\":[{\"type\":\"url\",\"ref\":\"$D\",\"label\":\"cited\"}]}"
seed "$P_R" "{\"session\":\"u\",\"skill\":\"decider\",\"kind\":\"decision\",\"statement\":\"Ship after the suite passes.\",\"evidence\":[{\"type\":\"command\",\"ref\":\"pytest -q\",\"label\":\"estimate\"}]}"
lib2 register --root "$P_R" --name probe >/dev/null 2>&1

lib2 update --all --project probe > "$TMP/u1.out" 2>&1
rc=$?
[ "$rc" -eq 0 ] && grep -q "1 BASELINE" "$TMP/u1.out" \
  && ok "first probe is BASELINE, never a verdict on a claim nobody has seen twice" \
  || { bad "baseline run wrong (exit $rc)"; cat "$TMP/u1.out"; }
grep -q "DEAD-SOURCE .*no-such.txt  (HTTP 404)" "$TMP/u1.out" \
  && ok "a 404 is DEAD-SOURCE — a fact about the source, not the claim" || { bad "no DEAD-SOURCE"; cat "$TMP/u1.out"; }
grep -q "1 NEEDS-SESSION-RECHECK" "$TMP/u1.out" \
  && ok "command-only evidence lists as NEEDS-SESSION-RECHECK" || { bad "no NEEDS-SESSION-RECHECK"; cat "$TMP/u1.out"; }
grep -q "never auto-executed" "$LIB2/update-log.md" \
  && ok "the log says out loud that evidence is never auto-executed" || bad "log missing the never-executed line"

lib2 update --all --project probe > "$TMP/u2.out" 2>&1
grep -q "1 STANDS" "$TMP/u2.out" && ok "an unchanged source STANDS on the next probe" \
  || { bad "second probe did not STAND"; cat "$TMP/u2.out"; }
echo "v2 body, changed" > "$WWW/doc.txt"
lib2 update --all --project probe > "$TMP/u3.out" 2>&1
grep -q "1 DRIFTED" "$TMP/u3.out" && grep -qE "DRIFTED .*\(stored [0-9a-f]+ → now [0-9a-f]+\)" "$TMP/u3.out" \
  && ok "changed bytes are DRIFTED, with both hashes on the line" || { bad "drift not caught"; cat "$TMP/u3.out"; }
lib2 update --all --project probe > "$TMP/u4.out" 2>&1
grep -q "1 DRIFTED" "$TMP/u4.out" \
  && ok "drift is NOT banked — the next run still reports it until a model judges it" \
  || { bad "drift was retired by the updater itself"; cat "$TMP/u4.out"; }

lib2 update --project probe > "$TMP/u5.out" 2>&1
grep -q "not due" "$TMP/u5.out" && ok "--due skips a url probed inside the age window" \
  || { bad "--due did not skip"; cat "$TMP/u5.out"; }

[ "$(grep -c '^## .* — library update' "$LIB2/update-log.md")" = "5" ] \
  && ok "the update log is append-only: 5 runs, 5 dated blocks" \
  || bad "log has $(grep -c '^## .* — library update' "$LIB2/update-log.md") blocks (want 5)"
head -1 "$LIB2/update-log.md" | grep -q "^# library update log — append-only" \
  && ok "the log names its own law in its first line" || bad "log header missing"
grep -q "1 BASELINE" "$LIB2/update-log.md" \
  && ok "the first run's block survives every later append" || bad "log rewrote history"

# CITES-REFUTED — the seam a single store cannot see: cache-a cites cache-b:F-1,
# which cache-b refuted above. Cross-project, one hop, resolved against the WHOLE
# shelf even though --project narrows what gets probed.
seed "$C1" "{\"session\":\"c\",\"skill\":\"decider\",\"kind\":\"decision\",\"statement\":\"Cap the read path cache at the tracking limit.\",\"evidence\":[{\"type\":\"record\",\"ref\":\"cache-b:F-1\",\"label\":\"cited\"}]}"
lib2 update --project cache-a > "$TMP/u6.out" 2>&1
rc=$?
[ "$rc" -eq 0 ] \
  && grep -qE "CITES-REFUTED +cache-a:F-6 +\(cites cache-b:F-1 — refuted by cache-b:F-[0-9]+\)" "$TMP/u6.out" \
  && ok "a live record citing another project's refuted record is flagged CITES-REFUTED" \
  || { bad "cross-project refuted citation missed (exit $rc)"; cat "$TMP/u6.out"; }
# The CROWN is flagged too, and that is the point: crowning a convergence buys no
# immunity from the ground moving underneath it afterwards.
grep -q "2 CITES-REFUTED" "$TMP/u6.out" \
  && grep -qE "CITES-REFUTED +cache-a:F-4 +\(cites cache-b:F-1" "$TMP/u6.out" \
  && ok "a crowned record is flagged when a member it cited is later refuted" \
  || { bad "the crown escaped the cross-project flag"; cat "$TMP/u6.out"; }
grep -q "CITES-REFUTED" "$LIB2/update-log.md" && ok "CITES-REFUTED lands in the append-only log" \
  || bad "flag not logged"

stop_srv

# ------------------------------------------------------------------ verdict
echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
