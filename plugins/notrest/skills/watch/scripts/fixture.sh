#!/bin/bash
# fixture.sh — asserts watch.py against a synthetic watchlist and a real local HTTP
# server (127.0.0.1, ephemeral port). Self-relative: runs from any cwd, writes only
# inside its own mktemp dir, never touches a real watch/ directory and never reaches
# the network. Usage: bash <watch-skill>/scripts/fixture.sh   (exit 0 = all pass)
set -u
# WATCH_PY overrides the script under test — see the note in compile's fixture:
# a new arm must be shown to FAIL against the previous revision.
WP="${WATCH_PY:-$(cd "$(dirname "$0")" && pwd)/watch.py}"
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

  # ── E · add --from-findings: the factcheck→watch handoff as one command ────────────
  echo "── E · add --from-findings"
  # Seeded with explicit ts so First verified is deterministic (and the rows fall due).
  SEEDED=0
  seed(){ python3 "$IDX" add --root "$R" --json "$(cat)" >/dev/null 2>&1 && SEEDED=$((SEEDED+1)); }
  seed <<EOF
{"ts":"2026-06-01T00:00:00Z","session":"fixture","skill":"factcheck","kind":"finding",
 "statement":"The pricing page lists the on-demand rate.",
 "evidence":[{"type":"url","ref":"$U/pricing.html","label":"cited"}],"relation":"toward"}
EOF
  # 4.7: kind=result now REQUIRES ran/command/exit (archivist docket C) — TESTS is a
  # count of records each naming a command and an exit code, not a number someone typed.
  # This seed predates that rule and was rejected by the live store, which took six
  # arms down with it; it is the seed that is stale, not the rule.
  seed <<EOF
{"ts":"2026-06-01T00:00:00Z","session":"fixture","skill":"factcheck","kind":"result",
 "statement":"Two independent registries agree on the state count.",
 "ran":"cross-read both registry pages","command":"bash scripts/cross-read-registries.sh","exit":0,
 "evidence":[{"type":"url","ref":"$U/registry.html","label":"cited"},
             {"type":"url","ref":"$U/pricing.html","label":"cited"}],"relation":"toward"}
EOF
  seed <<EOF
{"ts":"2026-06-01T00:00:00Z","session":"fixture","skill":"researcher","kind":"finding",
 "statement":"The pool ceiling is 32 by default.",
 "evidence":[{"type":"path","ref":"src/pool.py:12","label":"cited"}],"relation":"toward"}
EOF
  seed <<EOF
{"ts":"2026-06-01T00:00:00Z","session":"fixture","skill":"decider","kind":"decision",
 "statement":"Ship the read path on the registry feed.",
 "evidence":[{"type":"url","ref":"$U/registry.html","label":"cited"}],"relation":"toward"}
EOF
  seed <<EOF
{"ts":"2026-06-01T00:00:00Z","session":"fixture","skill":"factcheck","kind":"finding",
 "statement":"The vendor claims four nines of uptime.",
 "evidence":[{"type":"url","ref":"$U/uptime.html","label":"cited"}],"relation":"toward"}
EOF
  t "seeded 5 more records through the store's own door" "$SEEDED" "5"
  python3 "$IDX" refute F-6 --evidence "$U/outage-report.html" --root "$R" --session fixture \
    >/dev/null 2>&1 && ok "refuted F-6 (its row must never be created)" || no "refute F-6 failed"

  python3 "$WP" add --from-findings --root "$R" --today 2026-07-25 > "$W/add1.txt" 2>&1
  t "add --from-findings exits 0" "$?" "0"
  has "$W/add1.txt" "2 row(s) appended, 1 already watched, 4 left off (of 7 records)" \
      "counts every record it read and appends only the watchable ones"
  grep '^| W7 ' "$W/root/watch/watchlist.md" | grep -q 'F-2' \
    && ok "W7 carries F-2 in the Source cell (the store keeps owning the URL)" || no "W7 wrong"
  grep '^| W7 ' "$W/root/watch/watchlist.md" | grep -q 'weekly' \
    && ok "one [cited] url -> weekly cadence" || no "W7 cadence wrong"
  grep '^| W8 ' "$W/root/watch/watchlist.md" | grep -q 'monthly' \
    && ok "two [cited] urls -> monthly cadence" || no "W8 cadence wrong"
  grep '^| W7 ' "$W/root/watch/watchlist.md" | grep -q '2026-06-01' \
    && ok "First verified is the record's own ts, not today" || no "W7 date wrong"
  t "added exactly 2 rows (8 total)" "$(grep -c '^| W' "$W/root/watch/watchlist.md")" "8"
  grep -q 'F-4 ' "$W/root/watch/watchlist.md" && no "a path-evidence record became a row" \
    || ok "a record with no [cited] url is left off, not watched"
  grep -q 'F-5 ' "$W/root/watch/watchlist.md" && no "a kind=decision record became a row" \
    || ok "kind=decision is left off (rows come from finding|result)"
  grep -q 'F-6 ' "$W/root/watch/watchlist.md" && no "a refuted record became a row" \
    || ok "an effectively-refuted record is left off"
  grep -q 'F-7 ' "$W/root/watch/watchlist.md" && no "the refute tombstone became a row" \
    || ok "a status-flip tombstone is left off"
  has "$W/add1.txt" "url evidence — nothing re-readable" "says why F-4 was left off"
  has "$W/add1.txt" "not effectively live (refuted)" "says why F-6 was left off"
  # F-7 is the refute tombstone. It is `kind=decision` since the archivist's 4.7 change,
  # so it is left off one reason EARLIER than it used to be — by its kind, before its
  # shape is ever examined. The tombstone filter itself is still armed, on a tombstone
  # that WOULD have got past the kind gate: section F below.
  has "$W/add1.txt" "kind=decision (rows come from finding|result)" \
      "says why F-7 was left off"
  has "$W/add1.txt" "already watched" "F-1 was already on the list — skipped, not duplicated"

  BEFORE_ADD="$(cat "$W/root/watch/watchlist.md")"
  python3 "$WP" add --from-findings --root "$R" --today 2026-07-25 > "$W/add2.txt" 2>&1
  t "a second add exits 0 (idempotent)" "$?" "0"
  has "$W/add2.txt" "0 row(s) appended, 3 already watched" "the second run appends nothing"
  t "the second run changed no bytes" \
    "$([ "$BEFORE_ADD" = "$(cat "$W/root/watch/watchlist.md")" ] && echo identical || echo mutated)" "identical"

  python3 "$WP" due --root "$R" --today 2026-07-25 > "$W/due3.txt" 2>&1
  t "the appended rows parse and fall due like any other" "$?" "3"
  has "$W/due3.txt" "DUE  W7" "W7 is due (weekly, first verified 2026-06-01)"
  has "$W/due3.txt" "via F-2" "due resolved the new row through the store"

  # ── F · open questions are on the same calendar (docket G) ────────────────────────
  echo "── F · open questions on the clock"
  # The archivist's `open` kind records what was NOT tested and carries a recheck date.
  # That date only means something if something READS it — otherwise an open question
  # ages quietly into folklore, which is the failure the kind exists to prevent.
  oseed(){ python3 "$IDX" add --root "$R" --json "$(cat)" >/dev/null 2>&1; }
  oseed <<'EOF'
{"ts":"2026-05-01T00:00:00Z","session":"fixture","skill":"agentswarm","kind":"open",
 "statement":"The unattended pipeline was never run against a real estate overnight.",
 "closes_when":"bash scripts/fixture.sh exits 0 after a real overnight run",
 "owner":"seat","recheck":"2026-06-01","scope":["compile"],
 "evidence":[{"type":"path","ref":"briefs/commission.md","label":"cited"}],"relation":"toward"}
EOF
  oseed <<'EOF'
{"ts":"2026-05-02T00:00:00Z","session":"fixture","skill":"agentswarm","kind":"open",
 "statement":"Whether the daily cap holds across a DST boundary is untested.",
 "closes_when":"run the cap arm with TZ set either side of the change",
 "owner":"lane-c","recheck":"2099-01-01","scope":["compile"],
 "evidence":[{"type":"path","ref":"briefs/commission.md","label":"cited"}],"relation":"toward"}
EOF
  python3 "$WP" due --root "$R" --today 2026-07-25 > "$W/odue.txt" 2>&1
  t "due exits 3 with an open question past its recheck date" "$?" "3"
  has "$W/odue.txt" "OPEN O-1" "the overdue open question is listed by id"
  has "$W/odue.txt" "recheck=2026-06-01" "…with the date that brought it round"
  has "$W/odue.txt" "owner=seat" "…and the owner who can close it"
  has "$W/odue.txt" "closes when: bash scripts/fixture.sh exits 0" "…and its closing check"
  has "$W/odue.txt" "watch.py close O-1" "…and the exact command that closes it"
  grep -q "OPEN O-2" "$W/odue.txt" && no "a 2099 recheck must NOT be due" \
    || ok "an open question whose date has not come is not due"
  has "$W/odue.txt" "1 open question(s) due of 2 live open (0 already closed)" \
      "counts the open records it read"
  has "$W/odue.txt" "due of 8 rows" "…without disturbing the watchlist half of the count"

  # closing: through the store's own door, citing the open id
  python3 "$WP" close O-1 --root "$R" --exit 0 --ran "the compile fixture on a scratch copy" \
    > "$W/oclose.txt" 2>&1
  t "close exits 0" "$?" "0"
  has "$W/oclose.txt" "CLOSED O-1" "names what it closed"
  has "$W/oclose.txt" "COORD line:" "prints the COORD line for the session to bank"
  t "the closing record went in as a kind=result with a real exit code" "$(python3 -c "
import json
recs=[json.loads(l) for l in open('$R/archive/findings.jsonl') if l.strip()]
r=[x for x in recs if str(x.get('statement','')).startswith('closes O-1')][-1]
print(r['kind']=='result' and r['exit']==0 and bool(r['command']) and bool(r['ran']))")" "True"
  t "…citing the open id in links, where the store validates it" "$(python3 -c "
import json
recs=[json.loads(l) for l in open('$R/archive/findings.jsonl') if l.strip()]
r=[x for x in recs if str(x.get('statement','')).startswith('closes O-1')][-1]
print(r['links'])")" "['O-1']"
  t "…defaulting the command to the record's own closes_when" "$(python3 -c "
import json
recs=[json.loads(l) for l in open('$R/archive/findings.jsonl') if l.strip()]
r=[x for x in recs if str(x.get('statement','')).startswith('closes O-1')][-1]
print(r['command'].startswith('bash scripts/fixture.sh'))")" "True"
  python3 "$WP" due --root "$R" --today 2026-07-25 > "$W/odue2.txt" 2>&1
  grep -q "OPEN O-1" "$W/odue2.txt" && no "a closed question must leave the calendar" \
    || ok "a closed question is off the calendar"
  has "$W/odue2.txt" "(1 already closed)" "…and is counted as closed, not vanished"
  python3 "$WP" close O-1 --root "$R" --exit 0 > "$W/oclose2.txt" 2>&1
  t "closing the same question twice is refused (5)" "$?" "5"
  has "$W/oclose2.txt" "already closed by" "…naming the record that closed it"
  python3 "$WP" close O-2 --root "$R" --exit 3 > "$W/oclose3.txt" 2>&1
  t "a non-zero closing check with no note is refused (2)" "$?" "2"
  has "$W/oclose3.txt" "is a finding, not a formality" "…saying why a note is required"
  python3 "$WP" close O-2 --root "$R" --exit 3 \
    --note "the vendor withdrew the API; its absence settles the question" > "$W/oclose4.txt" 2>&1
  t "…and IS allowed once the failure is explained (0)" "$?" "0"
  has "$W/oclose4.txt" "The question is closed because the failure settled it" \
      "…saying out loud that the check did not pass"
  python3 "$WP" close O-99 --root "$R" --exit 0 >/dev/null 2>&1
  t "closing a record that does not exist exits 2" "$?" "2"
  python3 "$WP" close F-1 --root "$R" --exit 0 > "$W/oclose5.txt" 2>&1
  t "closing a non-open id exits 2" "$?" "2"
  has "$W/oclose5.txt" "not an open-record id" "…saying which id space close reads"
  python3 "$WP" close O-1 --root "$R" >/dev/null 2>&1
  t "close without --exit is a usage error (2)" "$?" "2"

  # an unparsable recheck is DUE NOW and says so — a clock nobody can read is not a
  # reason to stop watching (the ruling next_due already makes for Last checked).
  printf '{"id":"O-3","ts":"2026-05-03T00:00:00Z","session":"fixture","skill":"x","kind":"open","statement":"A question whose clock was typed wrong.","closes_when":"read it","owner":"seat","recheck":"soon","scope":["x"],"source":"seat","evidence":[{"type":"path","ref":"briefs/commission.md","label":"cited"}],"relation":"toward","status":"live","links":[]}\n' \
    >> "$R/archive/findings.jsonl"
  python3 "$WP" due --root "$R" --today 2026-07-25 > "$W/odue3.txt" 2>&1
  has "$W/odue3.txt" "OPEN O-3" "an unparsable recheck date is due now"
  has "$W/odue3.txt" "treated as due now" "…and says why, rather than dropping the row"

  # an estate that keeps open questions but no watchlist still has a calendar
  RO="$W/opensonly"; mkdir -p "$RO"
  python3 "$IDX" add --root "$RO" --json '{"ts":"2026-05-01T00:00:00Z","session":"f","skill":"x","kind":"open","statement":"An estate with no watchlist can still owe an answer.","closes_when":"answer it","owner":"seat","recheck":"2026-06-01","scope":["x"],"evidence":[{"type":"path","ref":"a.md","label":"cited"}],"relation":"toward"}' \
    >/dev/null 2>&1
  WATCH_INDEX_PY="$IDX" python3 "$WP" due --root "$RO" --today 2026-07-25 > "$W/odue4.txt" 2>&1
  t "due works with open records and no watchlist at all (3)" "$?" "3"
  has "$W/odue4.txt" "OPEN O-1" "…listing the open question"
  RN="$W/nothing"; mkdir -p "$RN"
  WATCH_INDEX_PY="$IDX" python3 "$WP" due --root "$RN" >/dev/null 2>&1
  t "…and an estate with neither still exits 2, as before" "$?" "2"

  # the tombstone filter, armed on a tombstone that gets PAST the kind gate
  oseed <<EOF
{"ts":"2026-06-20T00:00:00Z","session":"fixture","skill":"factcheck","kind":"finding",
 "statement":"supersedes F-3 — the registry moved to a new host.",
 "evidence":[{"type":"url","ref":"$U/registry.html","label":"cited"}],"relation":"toward"}
EOF
  python3 "$WP" add --from-findings --root "$R" --today 2026-07-26 > "$W/add3.txt" 2>&1
  t "add --from-findings still exits 0 with a tombstone-shaped finding present" "$?" "0"
  has "$W/add3.txt" "a status-flip tombstone, not a claim about the world" \
      "a tombstone that clears the kind gate is still left off, by its shape"
fi

echo
echo "watch fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
