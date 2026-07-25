#!/bin/bash
# fixture.sh — asserts compile.py against a synthetic estate. Self-relative: runs
# from any cwd, writes only inside its own mktemp dir, touches no real project.
# Usage: bash <compile-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
CP="$(cd "$(dirname "$0")" && pwd)/compile.py"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — not found: $2"; fi; }
hasnt(){ if grep -qF "$2" "$3" 2>/dev/null; then no "$1 — unexpectedly found: $2"; else ok "$1"; fi; }

# ── synthetic estate: 4 same-shape release entries + 2 genuine one-offs ────────
R="$W/repo"; mkdir -p "$R/spend"
cat > "$R/COORD.md" <<'EOF'
# COORD.md — session coordination ledger
## LEDGER
- [2026-01-02 10:00Z] [main] cut the release for the parser -> v1.2.0 shipped, changelog and manifest bumped | evidence: commit aa11bb2, tests green
- [2026-01-05 10:00Z] [main] cut the release for the exporter -> v1.3.0 shipped, changelog and manifest bumped | evidence: commit bb22cc3, tests green
- [2026-01-09 10:00Z] [main] cut the release for the indexer -> v1.4.0 shipped, changelog and manifest bumped | evidence: commit cc33dd4, tests green
- [2026-01-14 10:00Z] [main] cut the release for the viewer -> v1.5.0 shipped, changelog and manifest bumped | evidence: commit dd44ee5, tests green
- [2026-01-16 10:00Z] [main] owner interview about pricing tiers -> notes captured, nothing built | evidence: notes/pricing.md
- [2026-01-18 10:00Z] [main] investigate flaky dns resolution on the laptop -> root-caused to a stale resolver cache | evidence: dig output in transcript
EOF
cat > "$R/spend/ledger.md" <<'EOF'
# spend ledger — append-only via spend.py; grades: observed|estimate
[2026-01-02 10:05Z] lane=subagent model=claude-opus-5 tokens=1000 grade=observed purpose="release lane: changelog and manifest bumped for the parser, v1.2.0 shipped, commit"
[2026-01-05 10:05Z] lane=subagent model=claude-opus-5 tokens=1100 grade=observed purpose="release lane: changelog and manifest bumped for the exporter, v1.3.0 shipped, commit"
[2026-01-09 10:05Z] lane=subagent model=claude-opus-5 tokens=1200 grade=observed purpose="release lane: changelog and manifest bumped for the indexer, v1.4.0 shipped, commit"
[2026-01-16 10:05Z] lane=subagent model=claude-opus-5 tokens=900 grade=observed purpose="pricing interview transcription tidy-up"
[2026-01-18 10:05Z] lane=subagent model=claude-opus-5 tokens=800 grade=observed purpose="dns resolver diagnosis one-shot on the laptop"
EOF

# ── synthetic transcripts: one Bash command repeated three times ──────────────
T="$W/transcripts"; mkdir -p "$T"
CMD='python3 scripts/release.py bump --manifest plugin.json'
for f in s1 s2; do
  : > "$T/$f.jsonl"
  echo '{"type":"user","message":{"content":"hello"}}' >> "$T/$f.jsonl"
  echo "{\"type\":\"assistant\",\"message\":{\"content\":[{\"type\":\"tool_use\",\"name\":\"Bash\",\"input\":{\"command\":\"$CMD\"}}]}}" >> "$T/$f.jsonl"
done
echo "{\"type\":\"assistant\",\"message\":{\"content\":[{\"type\":\"tool_use\",\"name\":\"Bash\",\"input\":{\"command\":\"$CMD\"}}]}}" >> "$T/s2.jsonl"
echo 'not json at all {"Bash"' >> "$T/s2.jsonl"

O="$R/compile"
J(){ python3 -c "
import json,sys
d=json.load(open('$O/candidates.json'))
print(eval(sys.argv[1], {'d':d,'c':d['candidates'],'top':d['candidates'][0] if d['candidates'] else {}}))
" "$1"; }

echo "── A · report before any scan is hook-safe"
OUT="$(python3 "$CP" report --root "$R" 2>&1)"; t "report with no scan exits 0" "$?" "0"
case "$OUT" in *"no scan yet"*) ok "report says no scan yet";; *) no "report message: $OUT";; esac

echo "── B · scan the synthetic estate"
python3 "$CP" scan --root "$R" >/dev/null 2>&1; t "scan exits 0" "$?" "0"
has "candidates.md is marked machine-written" "NEVER hand-edit" "$O/candidates.md"
has "candidates.md states repetition != value" "Ranking measures REPETITION, not value" "$O/candidates.md"
has "absent source named, not omitted" "| COORD-AGENTS.md | NO |" "$O/candidates.md"
t "exactly one RIPE candidate" "$(J "sum(1 for x in c if x['ripe'])")" "1"
t "the ripe candidate is the release ritual" "$(J "'ship' in top['signature'] and '<ver>' in top['signature']")" "True"
t "release ritual counts every recorded occurrence" "$(J "top['occurrences'] >= 4")" "True"
t "cross-source fusion folded the spend purposes in" "$(J "sorted(top['sources'])")" "['coord', 'spend']"
t "same-shape ratio is reported" "$(J "0 < top['shape'] <= 1")" "True"
hasnt "the dns one-off is not ripe" "| RIPE | NEW | estate | coord=1" "$O/candidates.md"
t "one-offs stayed out of the release candidate" "$(J "not any('dns' in e['text'] for e in top['evidence'])")" "True"

echo "── C · report branches on a ripe+NEW candidate"
OUT="$(python3 "$CP" report --root "$R" 2>&1)"; t "report exits 3 on ripe+NEW" "$?" "3"
case "$OUT" in *"[compile] RIPE"*) ok "report line is hook-shaped";; *) no "report line: $OUT";; esac

echo "── D · a ruling carries over the next scan"
SLUG="$(J "top['slug']")"
python3 "$CP" decide --root "$R" --slug "$SLUG" --status DECLINED --alias release-ritual \
  --note "owner: stays hand-run until the manifest count settles" >/dev/null 2>&1
t "decide exits 0" "$?" "0"
has "decisions.md explains its own format" "Statuses: NEW | PROPOSED | COMPILED | DECLINED" "$O/decisions.md"
has "decide recorded the sig for rename-proof matching" "sig=" "$O/decisions.md"
python3 "$CP" scan --root "$R" >/dev/null 2>&1
t "DECLINED carried over" "$(J "top['status']")" "DECLINED"
t "alias carried over" "$(J "top['alias']")" "release-ritual"
has "the ruling note survives into candidates.md" "stays hand-run" "$O/candidates.md"
python3 "$CP" report --root "$R" >/dev/null 2>&1; t "report exits 0 once nothing ripe is NEW" "$?" "0"

echo "── E · a ruling survives the scanner renaming its candidate"
R2="$W/repo2"; cp -R "$R" "$R2"; rm -rf "$R2/compile"; mkdir -p "$R2/compile"
CORE="$(python3 -c "
import json;d=json.load(open('$O/candidates.json'));print(','.join(d['candidates'][0]['core']))")"
printf -- '- [2026-01-20 10:00Z] slug=a-human-renamed-this status=COMPILED sig=%s note="hand-written line"\n' \
  "$CORE" > "$R2/compile/decisions.md"
python3 "$CP" scan --root "$R2" >/dev/null 2>&1
t "hand-written ruling matched by sig, not slug" \
  "$(python3 -c "import json;print(json.load(open('$R2/compile/candidates.json'))['candidates'][0]['status'])")" \
  "COMPILED"

echo "── F · transcripts are optional and additive"
R3="$W/repo3"; cp -R "$R" "$R3"; rm -rf "$R3/compile"
python3 "$CP" scan --root "$R3" --transcripts "$T" >/dev/null 2>&1; t "scan --transcripts exits 0" "$?" "0"
CMDN="$(python3 -c "
import json;d=json.load(open('$R3/compile/candidates.json'))
m=[x for x in d['candidates'] if x['kind']=='cmd'];print(m[0]['occurrences'] if m else 0)")"
t "the thrice-run command surfaced as a cmd candidate" "$CMDN" "3"
CMDL="$(python3 -c "
import json;d=json.load(open('$R3/compile/candidates.json'))
m=[x for x in d['candidates'] if x['kind']=='cmd'];print(m[0]['ripe'] if m else 'none')")"
t "the cmd candidate is ripe at 3" "$CMDL" "True"
has "transcripts counted as a source" "| transcripts | yes |" "$R3/compile/candidates.md"

echo "── G · a thin estate gets an honest empty table, not an invented one"
R4="$W/empty"; mkdir -p "$R4"
python3 "$CP" scan --root "$R4" >/dev/null 2>&1; t "scan of an empty root exits 0" "$?" "0"
has "empty table says so plainly" "nothing repeated twice yet" "$R4/compile/candidates.md"
python3 "$CP" report --root "$R4" >/dev/null 2>&1; t "report on an empty estate exits 0" "$?" "0"

echo "── H · determinism and argument handling"
cp "$O/candidates.md" "$W/first.md"
python3 "$CP" scan --root "$R" >/dev/null 2>&1
D="$(diff <(grep -v '^Last scan:' "$W/first.md") <(grep -v '^Last scan:' "$O/candidates.md") | wc -l | tr -d ' ')"
t "two scans of the same estate agree" "$D" "0"
python3 "$CP" bogus --root "$R" >/dev/null 2>&1; t "unknown subcommand exits 2" "$?" "2"
python3 "$CP" decide --root "$R" --slug x --status NONSENSE >/dev/null 2>&1
t "an invalid status is refused" "$?" "1"
python3 "$CP" scan --root "$R" --out "$W/elsewhere" >/dev/null 2>&1
t "--out honours an absolute path" "$([ -f "$W/elsewhere/candidates.md" ] && echo yes)" "yes"

echo
echo "compile fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
