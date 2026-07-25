#!/bin/bash
# fixture.sh — asserts watch.py against a synthetic watchlist and a real local HTTP
# server (127.0.0.1, ephemeral port). Self-relative: runs from any cwd, writes only
# inside its own mktemp dir, never touches a real watch/ directory and never reaches
# the network. Usage: bash <watch-skill>/scripts/fixture.sh   (exit 0 = all pass)
set -u
WP="$(cd "$(dirname "$0")" && pwd)/watch.py"
W="$(mktemp -d)"
# The trap must not decide the exit status: a `kill` of an already-dead server returns
# 1, and that would surface as a fixture failure nobody could reproduce. Kill first,
# delete second, return 0 always — the exit code reports assertions, nothing else.
cleanup(){ [ -n "${SRV:-}" ] && kill "$SRV" 2>/dev/null; rm -rf "$W"; return 0; }
trap cleanup EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -q -- "$2" "$1"; then ok "$3"; else no "$3 — not found in $1"; fi; }

# ── a real server on an ephemeral port: the probe paths are HTTP, not a mock ─────────
mkdir -p "$W/site" "$W/root/watch"
printf 'the H100 rents for $2.49/hr\n' > "$W/site/pricing.html"
printf 'eight US states require it\n'  > "$W/site/registry.html"
# The server script goes to a file rather than a heredoc: a heredoc on a BACKGROUNDED
# job leaks its own text onto stdout on bash 3.2, which would land after the summary.
cat > "$W/serve.py" <<'PY'
import sys, os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
os.chdir(sys.argv[1])
class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = ThreadingHTTPServer(("127.0.0.1", 0), Q)
open(sys.argv[2], "w").write(str(srv.server_address[1]))
srv.serve_forever()
PY
python3 "$W/serve.py" "$W/site" "$W/port" >/dev/null 2>&1 &
SRV=$!
disown "$SRV" 2>/dev/null || :   # no "Terminated" job notice after the summary
for _ in $(seq 1 50); do [ -s "$W/port" ] && break; sleep 0.1; done
P="$(cat "$W/port")"; U="http://127.0.0.1:$P"
[ -n "$P" ] && ok "local http server up on port $P" || no "server never bound a port"

cat > "$W/root/watch/watchlist.md" <<EOF
# watchlist — facts under watch
> Rows are APPENDED. Only \`Last checked\` and \`Status\` are edited in place.

## factcheck/fixtureDossier.md · added 2026-01-01
| ID | Claim (verbatim) | Source | Tier | First verified | Last checked | Status | Cadence |
|----|------------------|--------|------|----------------|--------------|--------|---------|
| W1 | "An H100 rents for \$2.49/hr." | $U/pricing.html | T1 | 2026-01-01 | 2026-01-01 | HOLDS | weekly |
| W2 | "Eight US states require the disclosure." | $U/registry.html | T1 | 2026-01-01 | 2026-07-25 | HOLDS | monthly |
| W3 | "The spec has been stable." | $U/gone.html | T1 | 2026-01-01 | 2026-01-01 | HOLDS | quarterly |
| W4 | "A retired claim." | $U/pricing.html | T2 | 2026-01-01 | 2026-01-01 | DEAD-SOURCE | retired |
EOF
R="$W/root"

# ── A · due: the calendar, computed ──────────────────────────────────────────────────
echo "── A · due"
python3 "$WP" due --root "$R" --today 2026-07-25 > "$W/due.txt" 2>&1
t "exit 3 when rows are due" "$?" "3"
has "$W/due.txt" "DUE  W1" "W1 (weekly, last 2026-01-01) is due"
has "$W/due.txt" "DUE  W3" "W3 (quarterly, last 2026-01-01) is due"
grep -q "DUE  W2" "$W/due.txt" && no "W2 (monthly, checked today) must NOT be due" || ok "W2 not yet due"
grep -q "DUE  W4" "$W/due.txt" && no "W4 (retired) must never be due" || ok "W4 retired, never due"
has "$W/due.txt" "2 due of 4 rows" "counts the rows it parsed"
python3 "$WP" due --root "$R" --today 2026-01-01 > "$W/due0.txt" 2>&1
t "exit 0 when nothing is due" "$?" "0"

# ── B · probe: DEAD-SOURCE and UNCHANGED resolve without a model ─────────────────────
echo "── B · probe"
python3 "$WP" probe W3 --root "$R" --scratch "$W/scratch" > "$W/p3.txt" 2>&1
t "a 404 source exits 4 (DEAD-SOURCE)" "$?" "4"
has "$W/p3.txt" "verdict=DEAD-SOURCE" "reports the DEAD-SOURCE verdict"
has "$W/p3.txt" "http=404" "reports the status code"
has "$W/p3.txt" "the claim is not refuted" "states the law: a dead source is not a refutation"
python3 "$WP" probe W1 --root "$R" --scratch "$W/scratch" > "$W/p1a.txt" 2>&1
t "first probe of a hashless row exits 3 (BASELINE)" "$?" "3"
has "$W/p1a.txt" "verdict=BASELINE" "names the baseline"
has "$W/root/watch/watchlist.md" "Hash" "added the Hash column to a table that lacked it"
t "the migration kept every row" "$(grep -c '^| W' "$W/root/watch/watchlist.md")" "4"
python3 "$WP" probe W1 --root "$R" --scratch "$W/scratch" > "$W/p1b.txt" 2>&1
t "re-probing unchanged content exits 0 (UNCHANGED)" "$?" "0"
has "$W/p1b.txt" "verdict=UNCHANGED" "resolves UNCHANGED at zero model tokens"
printf 'the H100 now rents for $1.99/hr\n' > "$W/site/pricing.html"
python3 "$WP" probe W1 --root "$R" --scratch "$W/scratch" > "$W/p1c.txt" 2>&1
t "changed content exits 3 (the model's cue)" "$?" "3"
has "$W/p1c.txt" "verdict=CHANGED" "names the change"
BODY="$(sed -n 's/.*body=\([^ ]*\).*/\1/p' "$W/p1c.txt" | head -1)"
[ -s "$BODY" ] && ok "wrote the changed body to scratch ($BODY)" || no "no body file at [$BODY]"
grep -q '1.99' "$BODY" && ok "the scratch body is the new content" || no "scratch body is stale"
STORED="$(grep '^| W1' "$W/root/watch/watchlist.md" | awk -F'|' '{print $10}' | tr -d ' ')"
BASE="$(sed -n 's/.*sha256=\([0-9a-f]*\).*/\1/p' "$W/p1a.txt" | head -1)"
t "a CHANGED probe does NOT overwrite the stored hash" "$STORED" "$BASE"
# Regression: a page rewritten in the SAME SECOND as the previous probe. An
# If-Modified-Since conditional answers 304 here (HTTP dates are second-granular) and
# would report UNCHANGED over real drift — which is why only strong ETags are sent.
printf 'W2 rewritten immediately\n' > "$W/site/registry.html"
python3 "$WP" probe W2 --root "$R" --scratch "$W/scratch" >/dev/null 2>&1
printf 'W2 rewritten again, same second\n' > "$W/site/registry.html"
python3 "$WP" probe W2 --root "$R" --scratch "$W/scratch" > "$W/p2b.txt" 2>&1
t "a same-second content change still reads as CHANGED" "$?" "3"
grep -q "304" "$W/p2b.txt" && no "a date-based 304 masked a real change" || ok "no date-based 304 shortcut"
python3 "$WP" probe NOPE --root "$R" >/dev/null 2>&1; t "an unknown row id exits 2" "$?" "2"

# ── C · append: the honesty stamp is an exit code ────────────────────────────────────
echo "── C · append"
mk(){ cat > "$W/f.json"; python3 "$WP" append --json "$W/f.json" --root "$R" > "$W/a.txt" 2>&1; echo $?; }
RC="$(mk <<'EOF'
{"date":"2026-07-25","due":1,"searches":0,
 "findings":[{"id":"W1","status":"HOLDS","note":"re-read, unchanged"}]}
EOF
)"; t "HOLDS with no URL is refused (exit 5)" "$RC" "5"
has "$W/a.txt" "requires the source actually" "explains why an unfetched HOLDS is refused"
RC="$(mk <<'EOF'
{"date":"2026-07-25","due":1,"searches":0,
 "findings":[{"id":"W1","status":"DRIFTED","url":"http://x","http":"200"}]}
EOF
)"; t "DRIFTED with no evidence note is refused (exit 5)" "$RC" "5"
RC="$(mk <<'EOF'
{"date":"2026-07-25","due":1,"searches":0,
 "findings":[{"id":"W1","status":"MOSTLY-FINE","url":"http://x","http":"200"}]}
EOF
)"; t "a status outside the grammar is refused (exit 5)" "$RC" "5"
RC="$(mk <<'EOF'
{"date":"2026-07-25","due":4,"searches":0,
 "findings":[{"id":"W1","status":"HOLDS","url":"http://x","http":"200"}]}
EOF
)"; t "a due count the findings do not account for is refused (exit 5)" "$RC" "5"
has "$W/a.txt" "never shrink the denominator" "names the denominator law"
BEFORE="$(cat "$W/root/watch/watchlist.md")"
t "a refused append changed nothing" "$([ "$BEFORE" = "$(cat "$W/root/watch/watchlist.md")" ] && echo identical || echo mutated)" "identical"

RC="$(mk <<EOF
{"date":"2026-07-25","due":3,"searches":1,
 "findings":[
  {"id":"W1","status":"DRIFTED","note":"the page now says \$1.99/hr","url":"$U/pricing.html","http":"200","chain":"/factcheck","hash":"deadbeefdeadbeef"},
  {"id":"W2","status":"HOLDS","note":"registry re-read, unchanged","url":"$U/registry.html","http":"200"},
  {"id":"W3","status":"DEAD-SOURCE","note":"404 since this run","url":"$U/gone.html","http":"404"}],
 "not_due":["W4 (retired)"]}
EOF
)"; t "a well-formed cycle appends (exit 0)" "$RC" "0"
L="$W/root/watch/drift-log.md"
has "$L" "## 2026-07-25 — recheck cycle" "wrote the dated block"
has "$L" "1 HOLDS · 1 DRIFTED · 1 DEAD-SOURCE · 0 UNVERIFIABLE (of 3 due)" "counts are computed, not asserted"
has "$L" "Fetched this run:" "stamped what it fetched"
has "$L" "(404)" "the stamp carries each status code"
has "$L" "1 search" "the stamp carries the search count"
has "$L" "the source died, the claim did not" "DEAD-SOURCE line states the claim is not refuted"
t "DRIFTED leads the block" "$(grep -n '^- ' "$L" | head -1 | grep -c DRIFTED)" "1"
has "$L" "→ /factcheck" "carries the chain suggestion"
has "$W/root/watch/watchlist.md" "2026-07-25 | DRIFTED" "updated W1's Last checked + Status in place"
grep '^| W1' "$W/root/watch/watchlist.md" | grep -q deadbeefdeadbeef \
  && ok "banked the new hash on the judged row" || no "hash not updated on the judged row"
grep '^| W4' "$W/root/watch/watchlist.md" | grep -q '2026-01-01' \
  && ok "an unchecked row kept its old Last checked date" || no "W4's date moved without being checked"
has "$W/a.txt" "COORD line:" "prints the COORD line for the session to bank"
python3 "$WP" append --json "$W/f.json" --root "$R" > "$W/a2.txt" 2>&1
t "re-running the same append is safe (exit 0)" "$?" "0"
t "the block was not duplicated" "$(grep -c '## 2026-07-25 — recheck cycle' "$L")" "1"

# ── D · a findings-store subject (F-<id>) resolves like a dossier path ───────────────
echo "── D · findings-store subjects"
IDX="$(cd "$(dirname "$0")" && pwd)/../../archivist/scripts/index.py"
if [ ! -f "$IDX" ]; then
  echo "  SKIP  no archivist/scripts/index.py in this tree — findings subjects unverified"
else
  export WATCH_INDEX_PY="$IDX"
  python3 "$IDX" add --root "$R" --json "$(cat <<EOF
{"session":"fixture","skill":"factcheck","kind":"finding","ask":"what does the page say",
 "statement":"The registry lists eight US states.",
 "evidence":[{"type":"url","ref":"$U/registry.html","label":"cited"}],
 "relation":"toward","status":"live"}
EOF
)" > "$W/add.txt" 2>&1
  t "seeded one F-record through the store's own door" "$?" "0"
  cat >> "$W/root/watch/watchlist.md" <<EOF

## F-1 · added 2026-07-25
| ID | Claim (verbatim) | Source | Tier | First verified | Last checked | Status | Cadence | Hash |
|----|------------------|--------|------|----------------|--------------|--------|---------|------|
| W5 | "The registry lists eight US states." | F-1 | T1 | 2026-07-01 | 2026-07-01 | HOLDS | weekly |  |
EOF
  python3 "$WP" due --root "$R" --today 2026-07-25 > "$W/due2.txt" 2>&1
  t "a findings-store row is due like any other" "$?" "3"
  has "$W/due2.txt" "DUE  W5" "W5 (subject F-1) is due"
  has "$W/due2.txt" "registry.html" "due resolved F-1 to its url evidence"
  has "$W/due2.txt" "via F-1" "due says which record the URL came from"
  python3 "$WP" probe W5 --root "$R" --scratch "$W/scratch" > "$W/p5.txt" 2>&1
  t "probing a findings-store row exits 3 (first observation)" "$?" "3"
  has "$W/p5.txt" "F-1 resolved to" "probe names the resolution"
  has "$W/p5.txt" "verdict=BASELINE" "probe fetched the resolved URL"
  # legacy dossier rows must be untouched by any of this
  python3 "$WP" probe W2 --root "$R" --scratch "$W/scratch" >/dev/null 2>&1
  t "a legacy dossier-path row still probes by its Source cell" "$?" "3"
  # a subject naming a record that is not there fails loudly, not silently
  cat >> "$W/root/watch/watchlist.md" <<'EOF'
| W6 | "A claim whose record was never written." | F-99 | T1 | 2026-07-01 | 2026-07-01 | HOLDS | weekly |  |
EOF
  python3 "$WP" probe W6 --root "$R" > "$W/p6.txt" 2>&1
  t "an unresolvable finding id exits 2" "$?" "2"
  has "$W/p6.txt" "F-99 UNRESOLVED" "says which id could not be resolved"
fi

echo
echo "watch fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
