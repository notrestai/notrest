#!/usr/bin/env bash
# river-fixture — a synthetic estate whose river shape is known EXACTLY, so the
# renderer's counts are asserted against arithmetic rather than eyeballed.
#
# The ledger below exercises every kind, every relation, every status and every
# channel outcome: a main channel, a lateral run that merges back, an explicit
# side-route fork that dead-ends, a lateral that never rejoins, a backtrack loop,
# a conflict rock, a supersede and a refute. Then: the degrade path (no findings
# ledger), the node cap, the three query verbs, byte-identical re-render, the
# both-themes CSS hooks, and a real render-check (serve + HTTP 200).
#
# Exit 0 = every assertion held. No network, no model calls, no repo writes.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
GRAPH="$HERE/graph.py"
RC="$HERE/../../doctor/scripts/render-check.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/notrest-river-fixture.XXXXXX")"
R="$TMP/estate"
OUT="$R/graph"
PASSES=0
FAILS=0

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

ok()  { PASSES=$((PASSES+1)); echo "PASS  $1"; }
bad() { FAILS=$((FAILS+1));   echo "FAIL  $1"; }
chk() { # chk <label> <expected> <actual>
  if [ "$2" = "$3" ]; then ok "$1 = $2"; else bad "$1: expected $2, got $3"; fi
}
val() { python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split('.'):
    d = d[int(k)] if k.lstrip('-').isdigit() else d[k]
print(d)" "$1" "$2" 2>/dev/null || echo "<ERR>"; }

mkdir -p "$R/archive"

# ---------------------------------------------------------------- the findings
# id  rel/kind          channel     why
# F-1  toward finding   main        the journey starts
# F-2  toward result    main
# F-3  lateral finding  side 1      forks off F-2 …
# F-4  lateral result   side 1      … runs …
# F-5  toward decision  main        … and F-5 links it back: side 1 MERGES
# F-6  lateral/side-route  side 2   an EXPLICIT fork (kind side-route)
# F-7  lateral finding  side 2      … which nothing ever links again: DEAD END
# F-8  toward finding   main
# F-9  back backtrack   main        loops upstream to F-2
# F-10 toward conflict  main        a rock in the channel
# F-11 toward result    main        supersedes F-8
# F-12 toward finding   main        refutes F-3 (a second rock, by status)
# F-13 lateral finding  side 3      forks off F-11, never rejoins: DEAD END
# F-14 toward result    main        links F-11 (not adjacent) → a stray link edge
cat > "$R/archive/findings.jsonl" <<'EOF'
{"id":"F-1","ts":"2026-07-20T09:00:00Z","session":"lane-a","skill":"researcher","kind":"finding","ask":"where does the harness lose tokens","statement":"the listing is re-injected every session","evidence":[{"type":"path","ref":"plugins/notrest/README.md","label":"cited"}],"relation":"toward","links":[],"status":"live"}
{"id":"F-2","ts":"2026-07-20T09:20:00Z","session":"lane-a","skill":"researcher","kind":"result","ask":"measure the injection","statement":"26,386 chars measured at session start","evidence":[{"type":"command","ref":"wc -c on the hook echoes","label":"cited"}],"relation":"toward","links":["F-1"],"status":"live"}
{"id":"F-3","ts":"2026-07-20T09:40:00Z","session":"lane-a","skill":"critic","kind":"finding","ask":"could a cache warm-up explain it","statement":"warm cache would hide the cost, not remove it","evidence":[{"type":"model-opinion","ref":"reasoning only","label":"model-opinion"}],"relation":"lateral","links":["F-2"],"status":"live"}
{"id":"F-4","ts":"2026-07-20T10:00:00Z","session":"lane-a","skill":"critic","kind":"result","ask":"test the cache theory","statement":"cold and warm runs differ by 4%","evidence":[{"type":"command","ref":"two timed runs","label":"estimate"}],"relation":"lateral","links":["F-3"],"status":"live"}
{"id":"F-5","ts":"2026-07-20T10:30:00Z","session":"lane-a","skill":"decider","kind":"decision","ask":"do we rightsize the echoes","statement":"yes — trim the hook echoes to standing orders","evidence":[{"type":"coord-line","ref":"COORD.md:3","label":"cited"}],"relation":"toward","links":["F-4"],"status":"live"}
{"id":"F-6","ts":"2026-07-20T11:00:00Z","session":"lane-b","skill":"researcher","kind":"side-route","ask":"should we compress the descriptions instead","statement":"a separate route: shorten every description to a trigger router","evidence":[{"type":"path","ref":"plugins/notrest/skills","label":"cited"}],"relation":"lateral","links":["F-5"],"status":"live"}
{"id":"F-7","ts":"2026-07-20T11:30:00Z","session":"lane-b","skill":"researcher","kind":"finding","ask":"how far can descriptions shrink","statement":"500 chars is the practical floor","evidence":[{"type":"recall","ref":"prior release notes","label":"recall"}],"relation":"lateral","links":["F-6"],"status":"live"}
{"id":"F-8","ts":"2026-07-20T12:00:00Z","session":"lane-a","skill":"researcher","kind":"finding","ask":"what does the trim buy","statement":"roughly 2,000 tokens per session","evidence":[{"type":"command","ref":"char count delta","label":"estimate"}],"relation":"toward","links":["F-5"],"status":"live"}
{"id":"F-9","ts":"2026-07-20T12:30:00Z","session":"lane-a","skill":"factcheck","kind":"backtrack","ask":"re-check the baseline measurement","statement":"back to F-2: the first measure counted the listing twice","evidence":[{"type":"command","ref":"re-run of the count","label":"cited"}],"relation":"back","links":["F-2"],"status":"live"}
{"id":"F-10","ts":"2026-07-20T13:00:00Z","session":"lane-a","skill":"factcheck","kind":"conflict","ask":"do the two measurements agree","statement":"they do not: 26,386 vs 18,657 for the same tree","evidence":[{"type":"command","ref":"both runs","label":"cited"}],"relation":"toward","links":["F-9"],"status":"live"}
{"id":"F-11","ts":"2026-07-20T13:30:00Z","session":"lane-a","skill":"researcher","kind":"result","ask":"settle the number","statement":"supersedes F-8: the real saving is 6,944 -> 4,910 tokens","evidence":[{"type":"command","ref":"instrumented run","label":"cited"}],"relation":"toward","links":["F-8"],"status":"live"}
{"id":"F-12","ts":"2026-07-20T14:00:00Z","session":"lane-a","skill":"critic","kind":"finding","ask":"was the cache theory ever true","statement":"refutes F-3: the warm cache changes nothing at session start","evidence":[{"type":"command","ref":"cold/warm comparison","label":"cited"}],"relation":"toward","links":["F-3"],"status":"live"}
{"id":"F-13","ts":"2026-07-20T14:30:00Z","session":"lane-b","skill":"researcher","kind":"finding","ask":"could the docs move out of the plugin","statement":"an unexplored route — docs as a separate marketplace entry","evidence":[],"relation":"lateral","links":["F-11"],"status":"live"}
{"id":"F-14","ts":"2026-07-20T15:00:00Z","session":"lane-a","skill":"researcher","kind":"result","ask":"ship the rightsizing","statement":"trim landed, measured at the consumer","evidence":[{"type":"url","ref":"https://example.invalid/release","label":"unverified"}],"relation":"toward","links":["F-11"],"status":"live"}
EOF

# ------------------------------------------------------------- the mini estate
cat > "$R/COORD.md" <<'EOF'
# COORD.md — session coordination ledger

## LEDGER
- [2026-07-20 09:15Z] [lane-a] measure the injection -> baseline taken | evidence: two runs
- [2026-07-20 10:35Z] [lane-a] rightsizing decided -> v1.2.0 shipped | evidence: commit abc1234
- [2026-07-20 12:35Z] [lane-a] correction: the baseline double-counted the listing | evidence: re-run
- [2026-07-20 13:35Z] [lane-a] measurement settled -> gated at the seat | evidence: exit 0
- [2026-07-20 14:45Z] [lane-b] docs route scoped -> parked | evidence: this line
- [2026-07-20 15:05Z] [lane-a] rightsizing landed -> v1.3.0 shipped | evidence: commit def5678
EOF

cat > "$R/COORD-AGENTS.md" <<'EOF'
# COORD-AGENTS.md — agent activity ledger (auto-written)

## LEDGER
- [2026-07-20 09:30Z] agent=a1111111 model=claude-opus-5 bytes=1000 | last: measured the echoes | transcript: /tmp/a1.jsonl
- [2026-07-20 11:10Z] agent=a2222222 model=claude-opus-5 bytes=2000 | last: read every description | transcript: /tmp/a2.jsonl
- [2026-07-20 14:10Z] agent=a3333333 model=? bytes=? | last: ? | transcript: /tmp/a3.jsonl
EOF

echo "── phase A: the full river ─────────────────────────────────────────────"
python3 "$GRAPH" river --root "$R" --out "$OUT/river.html" > "$TMP/a.out" 2>&1
A=$?
J="$OUT/river.json"
if [ "$A" -eq 0 ] && [ -f "$J" ] && [ -f "$OUT/river.html" ]; then
  ok "river exits 0 and writes both files"
else
  bad "river run: exit $A"; sed 's/^/      /' "$TMP/a.out"
fi

chk "mode"            "findings+coord" "$(val "$J" mode)"
chk "records"         14 "$(val "$J" counts.records)"
chk "toward"           8 "$(val "$J" counts.toward)"
chk "lateral"          5 "$(val "$J" counts.lateral)"
chk "back"             1 "$(val "$J" counts.back)"
chk "side-route forks" 1 "$(val "$J" counts.side_route)"
chk "conflicts (kind)" 1 "$(val "$J" counts.conflicts)"
chk "rocks (kind+refuted)" 2 "$(val "$J" counts.rocks)"
chk "live"            12 "$(val "$J" counts.live)"
chk "superseded"       1 "$(val "$J" counts.superseded)"
chk "refuted"          1 "$(val "$J" counts.refuted)"
chk "channels"         4 "$(val "$J" counts.channels)"
chk "side channels"    3 "$(val "$J" counts.side_channels)"
chk "merged back"      1 "$(val "$J" counts.merged)"
chk "dead ends"        2 "$(val "$J" counts.dead_end)"
chk "edges"           18 "$(val "$J" counts.edges)"
chk "coord lines"      6 "$(val "$J" counts.coord_lines)"
chk "milestone flags"  4 "$(val "$J" counts.milestones)"
chk "  ships"          2 "$(val "$J" counts.ships)"
chk "  gates"          1 "$(val "$J" counts.gates)"
chk "  corrections"    1 "$(val "$J" counts.corrections)"
chk "lane ticks"       3 "$(val "$J" counts.lanes)"

# the SHAPE, not just the tallies
chk "side 1 outcome"  "merged"   "$(val "$J" channels.1.outcome)"
chk "side 1 rejoins at" "F-5"    "$(val "$J" channels.1.merge_into)"
chk "side 2 outcome"  "dead-end" "$(val "$J" channels.2.outcome)"
chk "side 3 outcome"  "dead-end" "$(val "$J" channels.3.outcome)"
chk "main outcome"    "goal"     "$(val "$J" channels.0.outcome)"

EFF=$(python3 - "$J" <<'PY'
import json,sys
n={x["id"]:x for x in json.load(open(sys.argv[1]))["nodes"]}
print("%s|%s|%s|%s" % (n["F-3"]["effective"], n["F-8"]["effective"],
      ",".join(n["F-8"]["superseded_by"]), n["F-3"]["rock"]))
PY
)
chk "link-walked status (F-3 refuted, F-8 superseded by F-11, F-3 is a rock)" \
    "refuted|superseded|F-11|True" "$EFF"

EK=$(python3 - "$J" <<'PY'
import json,sys
e=json.load(open(sys.argv[1]))["edges"]
c={}
for x in e: c[x["kind"]] = c.get(x["kind"],0)+1
print(" ".join("%s=%d" % kv for kv in sorted(c.items())))
PY
)
chk "edge kinds" "back=1 branch=3 flow=10 link=1 merge=1 refute=1 supersede=1" "$EK"

# deterministic: the same inputs must render the same bytes
cp "$OUT/river.html" "$TMP/first.html"; cp "$J" "$TMP/first.json"
python3 "$GRAPH" river --root "$R" --out "$OUT/river.html" >/dev/null 2>&1
if cmp -s "$TMP/first.html" "$OUT/river.html" && cmp -s "$TMP/first.json" "$J"; then
  ok "re-render is byte-identical (no clock read, everything sorted)"
else
  bad "re-render differs — the render is not reproducible"
fi
STAMP_SRC="$(val "$J" stamp_from)"
chk "stamp source" "newest-input" "$STAMP_SRC"

# self-contained + both themes
if grep -q "prefers-color-scheme: dark" "$OUT/river.html" \
   && grep -q 'data-theme="dark"' "$OUT/river.html" \
   && grep -q 'data-theme="light"' "$OUT/river.html"; then
  ok "both themes present (media query + explicit data-theme overrides)"
else
  bad "theme hooks missing from river.html"
fi
EXT=$(grep -oE '(src|href)="[^"]+"|https?://[^"'"'"' )]+' "$OUT/river.html" \
      | grep -v 'www.w3.org/2000/svg' | grep -v 'example.invalid' | wc -l | tr -d ' ')
chk "external assets referenced" 0 "$EXT"
SIZE=$(wc -c < "$OUT/river.html" | tr -d ' ')
if [ "$SIZE" -lt 204800 ]; then ok "river.html is $SIZE bytes (< 200KB)"
else bad "river.html is $SIZE bytes — over the 200KB target"; fi

echo "── phase B: the cap ────────────────────────────────────────────────────"
python3 "$GRAPH" river --root "$R" --out "$TMP/cap.html" --cap 5 >/dev/null 2>&1
chk "capped records"  5  "$(val "$TMP/cap.json" counts.records)"
chk "cap keeps total" 14 "$(val "$TMP/cap.json" counts.total_records)"
chk "cap is declared" 5  "$(val "$TMP/cap.json" capped.shown)"
if grep -q "showing the last 5 of 14" "$TMP/cap.json"; then
  ok "cap note says what was dropped"
else bad "cap note missing from the JSON"; fi

echo "── phase C: session filter ─────────────────────────────────────────────"
python3 "$GRAPH" river --root "$R" --out "$TMP/s.html" --session lane-b >/dev/null 2>&1
chk "lane-b records" 3 "$(val "$TMP/s.json" counts.records)"
chk "lane-b coord lines" 1 "$(val "$TMP/s.json" counts.coord_lines)"

echo "── phase D: the degrade path (no findings ledger) ──────────────────────"
mv "$R/archive/findings.jsonl" "$TMP/parked.jsonl"
python3 "$GRAPH" river --root "$R" --out "$TMP/co.html" >/dev/null 2>&1
CJ="$TMP/co.json"
chk "degrades to"      "coord-only" "$(val "$CJ" mode)"
chk "ledger lines become nodes" 6 "$(val "$CJ" counts.records)"
chk "flags still fly"  4 "$(val "$CJ" counts.milestones)"
INF=$(python3 -c "
import json,sys
n=json.load(open(sys.argv[1]))['nodes']
print(sum(1 for x in n if x['inferred']))" "$CJ")
chk "every node marked inferred" 6 "$INF"
chk "no invented supersessions" 0 "$(val "$CJ" counts.refuted)"
if grep -q "COORD-only" "$TMP/co.html"; then ok "the page says it is a COORD-only river"
else bad "degrade mode is not disclosed in the page"; fi
mv "$TMP/parked.jsonl" "$R/archive/findings.jsonl"

echo "── phase E: the render gate (serve + HTTP 200) ─────────────────────────"
if [ -x "$RC" ] || [ -f "$RC" ]; then
  RCOUT="$(bash "$RC" "$OUT/river.html" 2>&1)"
  RCX=$?
  PORT="$(printf '%s\n' "$RCOUT" | sed -n 's/^PORT: *//p')"
  if [ "$RCX" -eq 0 ] && printf '%s' "$RCOUT" | grep -q "HTTP 200"; then
    ok "render-check served river.html: HTTP 200"
  else
    bad "render-check exit $RCX"; printf '%s\n' "$RCOUT" | sed 's/^/      /'
  fi
  [ -n "$PORT" ] && bash "$RC" --close "$PORT" >/dev/null 2>&1
else
  bad "render-check.sh not found at $RC"
fi

echo "── phase F: the query verbs ────────────────────────────────────────────"
mkdir -p "$R/docs" "$R/src"
cat > "$R/README.md" <<'EOF'
# fixture repo
The guide lives at [guide](docs/guide.md).
EOF
cat > "$R/docs/guide.md" <<'EOF'
# guide
Run [the app](../src/app.py).
EOF
cat > "$R/src/app.py" <<'EOF'
from src.util import helper
print(helper())
EOF
printf 'def helper():\n    return 1\n' > "$R/src/util.py"
printf '# nothing points at this file\n' > "$R/orphan.md"

python3 "$GRAPH" scan --root "$R" > "$TMP/scan.out" 2>&1
chk "scan exits 0" 0 "$?"

python3 "$GRAPH" links src/util.py --root "$R" > "$TMP/links.out" 2>&1
LX=$?
if [ "$LX" -eq 0 ] && grep -q "src/app.py" "$TMP/links.out" \
   && grep -q "links in" "$TMP/links.out"; then
  ok "links src/util.py finds the importer"
else
  bad "links: exit $LX"; sed 's/^/      /' "$TMP/links.out"
fi
if grep -q "scanned" "$TMP/links.out"; then ok "links cites the scan it answered from"
else bad "links does not say when the scan ran"; fi

python3 "$GRAPH" orphans --root "$R" > "$TMP/orph.out" 2>&1
if grep -q "orphan.md" "$TMP/orph.out" && ! grep -q " src/util.py" "$TMP/orph.out"; then
  ok "orphans finds the unreferenced file and only that"
else
  bad "orphans output wrong"; sed 's/^/      /' "$TMP/orph.out"
fi
if grep -q "Check before deleting" "$TMP/orph.out"; then
  ok "orphans refuses to call a node dead"
else bad "orphans is missing its honesty line"; fi

python3 "$GRAPH" stale --root "$R" --days 0 > "$TMP/stale.out" 2>&1
if grep -q "untouched for 0+ days" "$TMP/stale.out" && grep -q "mtime is the filesystem" "$TMP/stale.out"; then
  ok "stale lists by age and says what mtime is worth"
else
  bad "stale output wrong"; sed 's/^/      /' "$TMP/stale.out"
fi

python3 "$GRAPH" links src/util.py --root "$R" --out "$TMP/nosuch" >/dev/null 2>&1
chk "query without a scan exits 2" 2 "$?"
python3 "$GRAPH" links nope.zzz --root "$R" >/dev/null 2>&1
chk "unknown path exits 2" 2 "$?"

echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
