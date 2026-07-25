#!/usr/bin/env bash
# fixture — prove the findings store at the door: every kind lands, every
# validation rule turns its record away with exit 2 and names itself, the track
# round-trips, supersede/refute resolve without editing a byte, find sees
# statements and dossier bodies, and the legacy index still reads the estate.
# Exit 0 = every assertion held. No network, no model calls, no repo writes.

IDX="$(cd "$(dirname "$0")" && pwd)/index.py"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/notrest-archivist-fixture.XXXXXX")"
R="$TMP/root"
PASSES=0
FAILS=0

cleanup() { rm -rf "$TMP"; }
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
grep -q "findings store — 9 record(s), 7 live" "$R/oracle-index.md" \
  && ok "scan points the index at the findings store" || bad "index has no findings entry"

# ------------------------------------------------------------------- find
python3 "$IDX" find "RESP3" --root "$R" > "$TMP/find1.out" 2>&1
grep -q "^## findings — 1 record" "$TMP/find1.out" && grep -q "^F-1 " "$TMP/find1.out" \
  && ok "find hits a statement term in the store" || { bad "find missed the statement"; cat "$TMP/find1.out"; }

python3 "$IDX" find "Redis" --root "$R" > "$TMP/find2.out" 2>&1
grep -q "### Cache choice — Dossier — 2025-01-15" "$TMP/find2.out" \
  && ok "find still hits legacy index entries" || { bad "find lost the index entries"; cat "$TMP/find2.out"; }

# 'quorum-free' lives only in the dossier BODY — never in the Read Me First head,
# so the index alone was blind to it.
grep -q "quorum-free" "$R/oracle-index.md" && bad "term leaked into the index head (fixture wrong)" \
  || ok "'quorum-free' is body-only (invisible to the index)"
python3 "$IDX" find "quorum-free" --root "$R" > "$TMP/find3.out" 2>&1
grep -q "\[body match\]" "$TMP/find3.out" \
  && ok "find reads dossier bodies (body-blindness closed)" || { bad "body sweep missed it"; cat "$TMP/find3.out"; }

python3 "$IDX" find "zzz-no-such-term" --root "$R" 2>&1 | grep -q "^no findings, index entries, or dossier bodies match" \
  && ok "find reports an honest miss" || bad "find miss message wrong"

# ------------------------------------------------------------------ verdict
echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
