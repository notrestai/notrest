#!/bin/bash
# fixture.sh — asserts walk.py against a synthetic estate. Self-relative: runs
# from any cwd, writes only inside its own mktemp dir, touches no real project.
# Usage: bash <recap-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
WP="$(cd "$(dirname "$0")" && pwd)/walk.py"
TPL="$(cd "$(dirname "$0")/.." && pwd)/assets/decision-map-template.html"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — not found: $2"; fi; }
hasnt(){ if grep -qF "$2" "$3" 2>/dev/null; then no "$1 — unexpectedly found: $2"; else ok "$1"; fi; }

R="$W/repo"; mkdir -p "$R/spend" "$R/archive" "$R/docs" "$R/briefs" "$W/tr"

# ── two COORD volumes: one sealed, one active ────────────────────────────────
cat > "$R/COORD-001.md" <<'EOF'
# COORD.md — session coordination ledger
## LEDGER
- [2026-01-02 09:00Z] [main] set up the parser -> scaffold landed | evidence: docs/plan.md
- [2026-01-02 10:00Z] [main] owner ruling: the ledger rolls, never compacts -> law recorded | evidence: notes/gone.md
- [2026-01-03 08:00Z] [main] pivot the exporter -> in progress, nothing shipped | evidence: none yet
EOF
cat > "$R/COORD.md" <<'EOF'
# COORD.md — session coordination ledger
## LEDGER
- [2026-01-04 11:00Z] [main] cut the release -> v1.2.0 shipped, manifest bumped | evidence: docs/plan.md
- this line is prose, not a ledger entry at all
- [not-a-timestamp] [main] malformed clock -> nothing | evidence: none
- [2026-01-05 12:00Z] [main] correction: the earlier exporter claim was reversed -> fixed | evidence: docs/plan.md
EOF
# a lane blackboard — same COORD-*.md glob, deliberately NOT a volume
cat > "$R/COORD-BUILD.md" <<'EOF'
# COORD-BUILD.md — lane blackboard
- [2026-01-09 09:00Z] [build] LANEBLACKBOARDLINE -> should never be walked | evidence: none
EOF
echo "the plan" > "$R/docs/plan.md"

# ── agents: present, thin-with-meta, present-with-brief, unrecoverable ───────
cat > "$R/COORD-AGENTS.md" <<EOF
# COORD-AGENTS.md — agent activity ledger (auto-written by the oracle-suite SubagentStop hook)
## LEDGER
- [2026-01-02 09:30Z] agent=a111 model=claude-opus-5 bytes=100 | last: found the parser bug | transcript: $W/tr/agent-a111.jsonl
- [2026-01-03 09:30Z] agent=a222 model=? bytes=? | last: ? | transcript: $W/tr/agent-a222.jsonl
- [2026-01-04 09:30Z] agent=a333 model=claude-opus-5 bytes=200 | last: shipped the release | transcript: $W/tr/agent-a333.jsonl | brief: briefs/agent-a333.md
- [2026-01-05 09:30Z] agent=a444 model=? bytes=? | last: ? | transcript: $W/tr/agent-a444.jsonl
- a line the hook never finished writing
EOF
echo '{}' > "$W/tr/agent-a111.jsonl"
echo '{}' > "$W/tr/agent-a333.jsonl"
echo '{"description":"the exporter lane","model":"claude-opus-5"}' > "$W/tr/agent-a222.meta.json"
echo "brief" > "$R/briefs/agent-a333.md"
# a222 + a444 transcripts are deliberately absent

# ── spend: strict, strict, off-shape-but-timestamped, unparseable ────────────
cat > "$R/spend/ledger.md" <<'EOF'
# spend ledger — append-only via spend.py; grades: observed|estimate
[2026-01-02 10:00Z] lane=subagent model=claude-opus-5 tokens=1000 grade=observed purpose="parser lane" agent=a111
[2026-01-04 11:05Z] lane=subagent model=claude-opus-5 tokens=2000 grade=observed purpose="release lane"
[2026-01-05 13:00Z] lane=subagent model=claude-opus-5 tokens=oops
[garbage] this line has no parseable clock at all
EOF

# ── findings: live, superseded-with-dead-evidence, bad json, bad ts ──────────
cat > "$R/archive/findings.jsonl" <<'EOF'
{"id":"F-1","ts":"2026-01-02T10:00:45Z","session":"s","skill":"doctor","kind":"finding","ask":"a","statement":"the resolver cache was stale","evidence":[{"type":"path","ref":"docs/plan.md","label":"cited"}],"relation":"lateral","links":[],"status":"live"}
{"id":"F-2","ts":"2026-01-05T14:00:00Z","session":"s","skill":"recap","kind":"result","ask":"b","statement":"the story holds","evidence":[{"type":"path","ref":"docs/missing-dossier.md","label":"cited"}],"relation":"toward","links":["F-1"],"status":"superseded"}
this line is not json at all
{"id":"F-3","ts":"not-a-clock","statement":"unparseable ts"}
EOF

# ── git: one commit authored in a NON-UTC zone, to prove the UTC handling ────
(
  cd "$R" || exit 1
  git init -q 2>/dev/null
  git config user.name "Fixture"; git config user.email "fixture@example.com"
  git config commit.gpgsign false
  export GIT_AUTHOR_NAME=Fixture GIT_AUTHOR_EMAIL=fixture@example.com
  export GIT_COMMITTER_NAME=Fixture GIT_COMMITTER_EMAIL=fixture@example.com
  add(){ git add -A >/dev/null 2>&1; GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1" \
         git commit -q -m "$2" >/dev/null 2>&1; }
  echo a > f1; add "2026-01-01T12:00:00+00:00" "initial scaffold"
  # 05:00:30 in UTC-5 IS 10:00:30Z — a naive `--date=format:` read prints 05:00Z
  echo b > f2; add "2026-01-02T05:00:30-05:00" "parser groundwork"
  echo c > f3; add "2026-01-04T11:02:00+00:00" "v1.2.0 — the release"
) || { echo "git setup failed"; exit 1; }

python3 "$WP" walk --root "$R" --json > "$W/walk.json" 2>"$W/walk.err"
J(){ python3 -c "
import json,sys
d=json.load(open('$W/walk.json'))
e=d['entries']
print(eval(sys.argv[1], {'d':d,'e':e,'inv':d['inventory'],'ex':d['extras']}))
" "$1"; }

echo "── A · usage and exit codes"
python3 "$WP" >/dev/null 2>&1;                       t "no subcommand exits 2" "$?" "2"
python3 "$WP" walk --root "$W/nope" >/dev/null 2>&1; t "a missing --root exits 2" "$?" "2"
python3 "$WP" walk --root "$R" --since "yesterday" >/dev/null 2>&1
t "an unparseable --since exits 2" "$?" "2"
mkdir -p "$W/empty"
python3 "$WP" walk --root "$W/empty" >/dev/null 2>&1;    t "walk on an empty estate exits 3" "$?" "3"
python3 "$WP" spans --root "$W/empty" >/dev/null 2>&1;   t "spans on an empty estate exits 3" "$?" "3"
python3 "$WP" prefill --root "$W/empty" >/dev/null 2>&1; t "prefill on an empty estate exits 3" "$?" "3"
python3 "$WP" walk --root "$R" >/dev/null 2>&1;          t "walk on a real estate exits 0" "$?" "0"

echo "── B · the inventory names every source, present or absent"
python3 "$WP" walk --root "$R" > "$W/walk.txt" 2>&1
t "both COORD volumes were walked" "$(J "sum(1 for r in inv if r['source'].startswith('COORD-001') or r['source']=='COORD.md')")" "2"
t "sealed volume entry count" "$(J "[r['entries'] for r in inv if r['source']=='COORD-001.md'][0]")" "3"
t "active volume entry count (2 parse, 2 do not)" "$(J "[r['entries'] for r in inv if r['source']=='COORD.md'][0]")" "2"
t "the active volume's malformed line is COUNTED, not fatal" "$(J "[r['malformed'] for r in inv if r['source']=='COORD.md'][0]")" "1"
has "the lane blackboard is named as NOT walked" "COORD-BUILD.md" "$W/walk.txt"
hasnt "…and its line never entered the stream" "LANEBLACKBOARDLINE" "$W/walk.txt"
t "agents ledger counted (4 parse, 1 does not)" "$(J "[r['entries'] for r in inv if r['source']=='COORD-AGENTS.md'][0]")" "4"
t "spend keeps the off-shape line and drops the clockless one" "$(J "[(r['entries'],r['malformed']) for r in inv if r['source'].endswith('ledger.md')][0]")" "(3, 1)"
t "findings: 2 valid, 2 malformed" "$(J "[(r['entries'],r['malformed']) for r in inv if r['source'].endswith('findings.jsonl')][0]")" "(2, 2)"
t "git found 3 commits" "$(J "[r['entries'] for r in inv if r['source']=='git'][0]")" "3"
THIN="$W/thin"; mkdir -p "$THIN"; cp "$R/COORD.md" "$THIN/"
python3 "$WP" walk --root "$THIN" > "$W/thin.txt" 2>&1; t "a thin estate still exits 0" "$?" "0"
has "an absent agent ledger is NAMED, not omitted" "COORD-AGENTS.md | NO" "$W/thin.txt"
has "…and an absent spend ledger says costs are absent, not zero" "costs are absent from this recap, not zero" "$W/thin.txt"

echo "── C · three clock shapes, one instant (merge order + a same-minute tie)"
t "the whole estate merged into one stream" "$(J "len(e)")" "17"
t "merged in strict epoch order" "$(J "all(e[i]['epoch']<=e[i+1]['epoch'] for i in range(len(e)-1))")" "True"
t "the estate opens with the oldest commit" "$(J "(e[0]['source'], e[0]['ts'])")" "('git', '2026-01-01 12:00Z')"
# 10:00:00Z coord · 10:00:00Z spend · 10:00:30Z git · 10:00:45Z finding
t "same-minute tie resolves coord, spend, git, findings" \
  "$(J "[x['source'] for x in e if 1767348000<=x['epoch']<1767348060]")" \
  "['coord', 'spend', 'git', 'findings']"
t "a non-UTC author date lands on the right UTC instant" \
  "$(J "[x['ts'] for x in e if x['source']=='git' and 'parser groundwork' in x['head']][0]")" \
  "2026-01-02 10:00Z"
t "COORD keeps its own clock shape verbatim" "$(J "[x['ts'] for x in e if 'owner ruling' in x['head']][0]")" "2026-01-02 10:00Z"
t "a store record keeps ISO8601Z verbatim, un-normalized" "$(J "[x['ts'] for x in e if x['id']=='F-1'][0]")" "2026-01-02T10:00:45Z"
t "…while merging on the same normalized instant" "$(J "[x['ts_iso'] for x in e if x['id']=='F-1'][0]")" "2026-01-02T10:00:45Z"

echo "── D · kinds, flags and citation tokens"
t "an owner ruling is classified ruling" "$(J "[x['kind'] for x in e if 'owner ruling' in x['head']][0]")" "ruling"
t "a version-bump commit is a ship" "$(J "[x['kind'] for x in e if x['source']=='git' and 'v1.2.0' in x['head']][0]")" "ship"
t "a plain commit is not a ship" "$(J "[x['kind'] for x in e if x['source']=='git' and 'scaffold' in x['head']][0]")" "commit"
t "'in progress' raises the open-thread flag" "$(J "'open-thread' in [x for x in e if 'pivot the exporter' in x['head']][0]['flags']")" "True"
t "'reversed / correction' raises the reversal flag" "$(J "'reversal' in [x for x in e if 'correction' in x['head']][0]['flags']")" "True"
t "a superseded record carries its status as a flag" "$(J "'superseded' in [x for x in e if x['id']=='F-2'][0]['flags']")" "True"
t "…and its links are carried for the informed-by edge" "$(J "'links:F-1' in [x for x in e if x['id']=='F-2'][0]['flags']")" "True"
t "COORD cite token" "$(J "[x['cite'] for x in e if 'owner ruling' in x['head']][0]")" "[COORD 2026-01-02 10:00Z]"
t "spend cite token" "$(J "[x['cite'] for x in e if x['source']=='spend'][0]")" "[spend 2026-01-02 10:00Z]"
t "findings cite token is the id" "$(J "[x['cite'] for x in e if x['id']=='F-1'][0]")" "[F-1]"
t "a live transcript cites with the arrow token" "$(J "[x['cite'] for x in e if x['id']=='a111'][0]")" "[COORD-AGENTS a111 → transcript]"
t "a dead transcript says so in the token itself" "$(J "[x['cite'] for x in e if x['id']=='a444'][0]")" "[COORD-AGENTS a444 — transcript missing]"
t "a commit cites by short sha" "$(J "[x['cite'].startswith('[commit ') for x in e if x['source']=='git'][0]")" "True"

echo "── E · a ledger line is an index, not a source (dead pointers)"
t "every emitted pointer was existence-checked" "$(J "sum(len(x['paths']) for x in e)>=6")" "True"
t "the live transcript is marked present" "$(J "[p['exists'] for x in e if x['id']=='a111' for p in x['paths']][0]")" "True"
t "the missing transcript is marked dead" "$(J "[p['exists'] for x in e if x['id']=='a444' for p in x['paths']][0]")" "False"
t "a thin line recovers its description from the sibling meta.json" \
  "$(J "'from-meta' in [x for x in e if x['id']=='a222'][0]['flags'] and 'exporter lane' in [x for x in e if x['id']=='a222'][0]['summary']")" "True"
t "no transcript and no meta = unrecoverable, said out loud" \
  "$(J "'unrecoverable' in [x for x in e if x['id']=='a444'][0]['flags']")" "True"
t "a dossier path named in a COORD evidence clause is checked too" \
  "$(J "'dead-pointer' in [x for x in e if 'owner ruling' in x['head']][0]['flags']")" "True"
t "…and a COORD path that DOES exist is not flagged" \
  "$(J "'dead-pointer' not in [x for x in e if 'set up the parser' in x['head']][0]['flags']")" "True"
t "a record's dead evidence path is flagged" "$(J "'dead-pointer' in [x for x in e if x['id']=='F-2'][0]['flags']")" "True"
has "dead pointers are listed under the walk, by cite" "!! DEAD:" "$W/walk.txt"
has "…and the law is printed where the reader is" "a ledger line is an index, not a source" "$W/walk.txt"

echo "── F · windows"
python3 "$WP" walk --root "$R" --since 2026-01-04 --json > "$W/since.json" 2>&1
t "--since keeps only entries at or after it" \
  "$(python3 -c "import json;d=json.load(open('$W/since.json'));print(all(x['ts_iso']>='2026-01-04' for x in d['entries']))")" "True"
t "--since count" "$(python3 -c "import json;print(len(json.load(open('$W/since.json'))['entries']))")" "8"
python3 "$WP" walk --root "$R" --until 2026-01-02 --json > "$W/until.json" 2>&1
t "a bare --until date means END of that day, not midnight" \
  "$(python3 -c "import json;d=json.load(open('$W/until.json'));print(any(x['id']=='F-1' for x in d['entries']))")" "True"
t "--until excludes the following day" \
  "$(python3 -c "import json;d=json.load(open('$W/until.json'));print(all(x['ts_iso']<'2026-01-03' for x in d['entries']))")" "True"
python3 "$WP" walk --root "$R" --since 2030-01-01 > "$W/none.txt" 2>&1
t "an empty WINDOW is exit 0, not exit 3" "$?" "0"
has "…and says the window is empty while the estate is not" "the estate is not empty" "$W/none.txt"
t "--head 0 never truncates" \
  "$(python3 "$WP" walk --root "$R" --head 0 | grep -c '…')" "0"

echo "── G · spans"
python3 "$WP" spans --root "$R" --json > "$W/spans.json" 2>&1; t "spans exits 0" "$?" "0"
S(){ python3 -c "
import json,sys
d=json.load(open('$W/spans.json'))
print(eval(sys.argv[1], {'d':d,'ps':d['per_source'],'pd':d['per_day'],'ss':d['sessions']}))
" "$1"; }
t "per-source counts add up to the walk" "$(S "sum(v['count'] for v in ps.values())")" "17"
t "per-source coord count" "$(S "ps['coord']['count']")" "5"
t "per-source agents count" "$(S "ps['agents']['count']")" "4"
t "five distinct UTC days" "$(S "len(pd)")" "5"
t "the per-day breakdown re-totals to the walk" "$(S "sum(x['total'] for x in pd)")" "17"
t "2026-01-02 holds all five sources at once" "$(S "sorted([x for x in pd if x['day']=='2026-01-02'][0]['sources'])")" "['agents', 'coord', 'findings', 'git', 'spend']"
t "a 90-minute gap finds 6 sittings across 5 days (01-05 splits in two)" "$(S "len(ss)")" "6"
t "each session carries an anchor citation" "$(S "all(x['anchor_cite'].startswith('[') for x in ss)")" "True"
t "a tighter gap splits more" "$(python3 "$WP" spans --root "$R" --gap 5 --json | python3 -c "import json,sys;print(len(json.load(sys.stdin)['sessions'])>5)")" "True"

echo "── H · prefill matches the template it fills"
python3 "$WP" prefill --root "$R" --out "$W/block.js" >/dev/null 2>&1; t "prefill exits 0" "$?" "0"
python3 - "$TPL" "$W/block.js" > "$W/spliced.html" <<'PY'
import sys, pathlib
tpl = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
blk = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
a = tpl.index("/* ============================ RECAP_DATA")
b = tpl.index("/* ========================== END RECAP_DATA")
sys.stdout.write(tpl[:a] + blk + tpl[b:])
PY
t "the block splices into the template between its own markers" "$?" "0"
t "the spliced page still carries the generic logic below the block" \
  "$(grep -c 'END RECAP_DATA' "$W/spliced.html")" "1"
# the template's own contract, read from the template — not from memory
TPL_KINDS="$(grep -oE '^  (ruling|decision|consult|ship): ' "$TPL" | tr -d ' :' | sort | tr '\n' ',')"
t "the template still declares exactly four lanes" "$TPL_KINDS" "consult,decision,ruling,ship,"
has "the template falls back to the raw cite type (nothing is hard-enumerated)" \
    "CITE_LABEL[c.type] || c.type" "$TPL"
P(){ python3 -c "
import json,re,sys
src=open('$W/block.js',encoding='utf-8').read()
body=src[src.index('const RECAP_DATA'):]
nodes=re.findall(r'kind:(\"[a-z]+\")', body)
kinds=[json.loads(x) for x in nodes]
ids=[json.loads(x) for x in re.findall(r'id:(\"n[0-9]+\")', body)]
ctypes=[json.loads(x) for x in re.findall(r'\{type:(\"[a-z]+\")', body)]
print(eval(sys.argv[1], {'k':kinds,'ids':ids,'ct':ctypes,'src':src}))
" "$1"; }
t "every emitted node kind is one the template renders" "$(P "sorted(set(k)) and all(x in ('ruling','decision','consult','ship') for x in k)")" "True"
t "node ids are n1..nN in order" "$(P "ids == ['n%d'%(i+1) for i in range(len(ids))]")" "True"
t "every node carries a cite" "$(P "len(ct) == len(k)")" "True"
t "cite types stay inside the labelled set plus the documented fallback" \
  "$(P "all(x in ('coord','commit','transcript','spend','dossier','note','finding') for x in ct)")" "True"
t "the unrecoverable agent line is NOT promoted to a node" "$(P "'a444' not in src")" "True"
t "a dead transcript node is flagged unverified" "$(P "'MISSING — dead pointer' in src")" "True"
has "edges are left for the model, explicitly" "MODEL FILLS THIS" "$W/block.js"
t "…and no edge object was invented" "$(python3 -c "
import re
s=open('$W/block.js',encoding='utf-8').read()
print(re.sub(r'/\*.*?\*/','',s,flags=re.S).count('from:'))")" "0"
has "the block says who filled it" "MACHINE-PREFILLED by recap/scripts/walk.py" "$W/block.js"
has "timestamps are marked verbatim for the model" "Never reformat, never re-timezone" "$W/block.js"
t "generated defaults to the newest walked entry, not the wall clock" \
  "$(grep -o 'generated: \"[0-9-]*\"' "$W/block.js")" "generated: \"2026-01-05\""
python3 "$WP" prefill --root "$R" --now 2030-06-01 --project Demo > "$W/block2.js" 2>&1
t "--now overrides generated" "$(grep -o 'generated: \"[0-9-]*\"' "$W/block2.js")" "generated: \"2030-06-01\""
t "--project overrides the project name" "$(grep -c 'project: \"Demo\"' "$W/block2.js")" "1"
python3 "$WP" prefill --root "$R" --max-nodes 2 > "$W/block3.js" 2>&1
t "--max-nodes caps the node count" "$(grep -c 'id:\"n' "$W/block3.js")" "2"
has "…and the drop is reported inside the block, never silently" "dropped by --max-nodes" "$W/block3.js"
if command -v node >/dev/null 2>&1; then
  node --check "$W/block.js" >/dev/null 2>&1; t "the emitted block is valid JavaScript" "$?" "0"
  node -e "
    const D=new Function(require('fs').readFileSync('$W/block.js','utf8')+';return RECAP_DATA;')();
    if(!D.nodes.length||D.edges.length!==0) process.exit(1);
    if(!D.nodes.every(n=>n.cites&&n.cites.length&&n.ts&&n.title)) process.exit(1);
  " >/dev/null 2>&1
  t "…and evaluates to a RECAP_DATA object the template can render" "$?" "0"
else
  ok "node absent — JS syntax check skipped (block shape asserted structurally above)"
  ok "node absent — RECAP_DATA evaluation skipped"
fi

echo "── I · determinism: identical inputs, byte-identical output"
python3 "$WP" walk --root "$R" > "$W/d1.txt" 2>&1; python3 "$WP" walk --root "$R" > "$W/d2.txt" 2>&1
cmp -s "$W/d1.txt" "$W/d2.txt"; t "walk re-runs byte-identical" "$?" "0"
python3 "$WP" walk --root "$R" --json > "$W/j1.json" 2>&1; python3 "$WP" walk --root "$R" --json > "$W/j2.json" 2>&1
cmp -s "$W/j1.json" "$W/j2.json"; t "walk --json re-runs byte-identical" "$?" "0"
python3 "$WP" spans --root "$R" > "$W/s1.txt" 2>&1; python3 "$WP" spans --root "$R" > "$W/s2.txt" 2>&1
cmp -s "$W/s1.txt" "$W/s2.txt"; t "spans re-runs byte-identical" "$?" "0"
python3 "$WP" prefill --root "$R" > "$W/p1.js" 2>&1; python3 "$WP" prefill --root "$R" > "$W/p2.js" 2>&1
cmp -s "$W/p1.js" "$W/p2.js"; t "prefill re-runs byte-identical" "$?" "0"
t "no subcommand reads the wall clock" "$(grep -cE 'datetime\.now|time\.time|utcnow|date\.today' "$WP")" "0"

echo "── J · malformed input is tolerated, never fatal"
printf 'garbage\n\x00\xff binary-ish\n- [zzz] nope\n' > "$W/repo2.tmp"
R2="$W/repo2"; mkdir -p "$R2/spend" "$R2/archive"
cp "$W/repo2.tmp" "$R2/COORD.md"; cp "$W/repo2.tmp" "$R2/spend/ledger.md"
cp "$W/repo2.tmp" "$R2/archive/findings.jsonl"
python3 "$WP" walk --root "$R2" >/dev/null 2>&1
t "an estate of pure garbage exits 3, not a traceback" "$?" "3"
cp "$R/COORD.md" "$R2/COORD.md"; cat "$W/repo2.tmp" >> "$R2/COORD.md"
python3 "$WP" walk --root "$R2" > "$W/garb.txt" 2>&1
t "one good volume beside garbage still walks" "$?" "0"
hasnt "no traceback reached the output" "Traceback" "$W/garb.txt"
python3 "$WP" spans --root "$R2" >/dev/null 2>&1;   t "spans survives the same garbage" "$?" "0"
python3 "$WP" prefill --root "$R2" >/dev/null 2>&1; t "prefill survives the same garbage" "$?" "0"

echo
echo "recap fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
