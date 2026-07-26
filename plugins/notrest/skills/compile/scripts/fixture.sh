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
# `ship`/`shipped` are ESTATE_STOP words now (they describe the harness, not the job),
# so the release ritual is identified by its parameters+verbs instead: a version
# placeholder and a commit. Same assertion, on tokens the stopword list cannot eat.
t "the ripe candidate is the release ritual" "$(J "'commit' in top['signature'] and '<ver>' in top['signature']")" "True"
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

echo "── I · estate vocabulary is not a workflow (stopwords + weak-source demotion)"
# Regression for the measured defect: the scanner's #1 candidate was `lan` at 31×,
# built entirely out of spend purposes that all said "lane"/"round"/"gate". Two
# defences, both asserted here: those words never reach the weighting, and a cluster
# with no COORD line behind it is demoted below one that has one.
R5="$W/vocab"; mkdir -p "$R5/spend"
cat > "$R5/COORD.md" <<'EOF'
# COORD.md
## LEDGER
- [2026-02-01 09:00Z] [main] regenerate the customer invoice pdf for acme -> pdf mailed, archive updated | evidence: invoice-acme.pdf
- [2026-02-03 09:00Z] [main] regenerate the customer invoice pdf for globex -> pdf mailed, archive updated | evidence: invoice-globex.pdf
- [2026-02-06 09:00Z] [main] regenerate the customer invoice pdf for initech -> pdf mailed, archive updated | evidence: invoice-initech.pdf
- [2026-02-07 09:00Z] [main] owner interview about tarot deck pricing -> notes captured | evidence: notes/tarot.md
- [2026-02-08 09:00Z] [main] chase the flaky dns resolver on the laptop -> stale cache blamed | evidence: dig output
- [2026-02-09 09:00Z] [main] draft the grocery budget spreadsheet formulas -> three columns rewritten | evidence: budget.xlsx
EOF
cat > "$R5/spend/ledger.md" <<'EOF'
# spend ledger — append-only via spend.py
[2026-02-01 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="comprehensive review: model-policy lane (round 2 gate, fixtures verified)"
[2026-02-02 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="visual-plan research lane (round 1, opus agents, receipts shipped)"
[2026-02-03 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="tarot deck illustration lane (round 3 gated, evidence shipped)"
[2026-02-04 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="dns latency probe lane (round 2, seat gate, tokens observed)"
[2026-02-05 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="grocery budget spreadsheet lane (round 1 fixture, receipt verified)"
[2026-02-06 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="nightly dashboard screenshot refresh lane (round 1)"
[2026-02-07 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="nightly dashboard screenshot refresh lane (round 2)"
[2026-02-08 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="nightly dashboard screenshot refresh lane (round 3)"
[2026-02-09 09:05Z] lane=subagent model=claude-opus-5 tokens=100 grade=observed purpose="nightly dashboard screenshot refresh lane (round 4)"
EOF
python3 "$CP" scan --root "$R5" >/dev/null 2>&1; t "scan of the vocabulary estate exits 0" "$?" "0"
J5(){ python3 -c "
import json,sys
d=json.load(open('$R5/compile/candidates.json')); c=d['candidates']
BAD=set('lan round gat seat fixtur ship opu agent model token purpos receipt evidenc spend ledger verif'.split())
def by(tok): return next((x for x in c if tok in ' '.join(x['core'])), None)
print(eval(sys.argv[1], {'d':d,'c':c,'by':by,'BAD':BAD}))
" "$1"; }
t "estate vocabulary never reaches a candidate core" \
  "$(J5 'not any(BAD.intersection(x["core"]) for x in c)')" "True"
t "the vocabulary-only purposes ripened nothing of their own" \
  "$(J5 'not any(x["ripe"] and x["sources"].get("spend",0) and any(w in " ".join(e["text"] for e in x["evidence"]) for w in ("tarot deck illustration","grocery budget spreadsheet lane")) for x in c)')" "True"
t "a COORD-supported candidate still ripens" \
  "$(J5 'bool(by("invoic") and by("invoic")["ripe"] and by("invoic")["sources"].get("coord",0) >= 3)')" "True"
t "the spend-only cluster is flagged weak-source" "$(J5 'by("dashboard")["weak_source"]')" "True"
t "…and is demoted below the COORD-supported one despite more occurrences" \
  "$(J5 'by("dashboard")["rank"] > by("invoic")["rank"] and by("dashboard")["occurrences"] > by("invoic")["occurrences"]')" "True"
has "candidates.md explains the weak-source mark" "purposes say what a lane was CALLED" "$R5/compile/candidates.md"
has "the weak-source row is marked in the table" "weak-source" "$R5/compile/candidates.md"

echo "── J · contract pre-fills Step 1 from the trail (and refuses to invent it)"
# The ripe candidate from section B is the release ritual; its slug is machine-derived,
# so the fixture asks for it by the slug the scanner actually produced.
python3 "$CP" scan --root "$R" >/dev/null 2>&1
SLUG="$(J "top['slug']")"
python3 "$CP" contract --root "$R" --slug "$SLUG" > "$W/contract.md" 2>&1
t "contract on a scanned candidate exits 0" "$?" "0"
has "carries the Step-1 table header verbatim" \
  "| # | Responsibility | Evidence | Required for parity? | Owner today | Owner after | Why |" "$W/contract.md"
has "says it is Step 1 half-done, not done" "This is Step 1 half-done" "$W/contract.md"
has "COORD rows cite in the ritual's grammar" "[COORD 2026-01-02" "$W/contract.md"
has "spend rows cite in the ritual's grammar" "[spend 2026-01-02" "$W/contract.md"
has "citations carry a source line ref" "COORD.md:4" "$W/contract.md"
has "owner-today is mined from the ledger, not assumed" "lane=subagent model=claude-opus-5" "$W/contract.md"
has "coverage section is present" "Evidence coverage" "$W/contract.md"
has "coverage names the absent ledger rather than omitting it" "| COORD-AGENTS.md (\`COORD-AGENTS.md\`) | NO |" "$W/contract.md"
has "coverage admits transcripts were not read" "Transcripts:** not read by this script" "$W/contract.md"
has "coverage admits compacted history is invisible" "Compacted history is invisible" "$W/contract.md"
has "the completeness law survives into the draft" "a parity claim over a subset is a lie" "$W/contract.md"
t "judgment columns are left blank, never guessed" \
  "$(python3 -c "
rows=[l for l in open('$W/contract.md',encoding='utf-8') if l.startswith('| 1 |')]
print(bool(rows) and rows[0].rstrip().endswith('| ? | ? |'))")" "True"
t "rows walk in timestamp order (Step 1's rule)" \
  "$(python3 -c "
import re
ts=re.findall(r'\[(?:COORD|spend) ([0-9-]+ [0-9:]+Z)\]', open('$W/contract.md',encoding='utf-8').read())
print(ts==sorted(ts))")" "True"
t "every cited line ref resolves to a real line in a real file" \
  "$(python3 -c "
import re,pathlib
refs=set(re.findall(r'\`([A-Za-z0-9./-]+\.md):(\d+)\`', open('$W/contract.md',encoding='utf-8').read()))
ok=all((pathlib.Path('$R')/f).is_file() and len((pathlib.Path('$R')/f).read_text().splitlines())>=int(n)
       for f,n in refs)
print(bool(refs) and ok)")" "True"
python3 "$CP" contract --root "$R" --slug quantum-basket-weaving > "$W/none.md" 2>&1
t "a slug with no trail evidence exits 3, with no invented rows" "$?" "3"
has "…and says why plainly" "there is nothing to reconstruct" "$W/none.md"
python3 "$CP" contract --root "$R" --slug "$SLUG" --write "$W/written.md" >/dev/null 2>&1
t "--write puts the draft on disk" "$([ -s "$W/written.md" ] && echo yes)" "yes"
python3 "$CP" contract --root "$R" --slug "$SLUG" --max-rows 2 > "$W/capped.md" 2>&1
t "--max-rows caps the table" \
  "$(grep -c '^| [0-9]* | _<rewrite' "$W/capped.md" | tr -d ' ')" "2"
has "…and says the cap was hit" "capped at --max-rows 2" "$W/capped.md"
# An unscanned root still yields a contract: the slug's own tokens are the query.
R6="$W/unscanned"; mkdir -p "$R6"; cp "$R/COORD.md" "$R6/"
python3 "$CP" contract --root "$R6" --slug "release-changelog" > "$W/unscanned.md" 2>&1
t "contract works with no scan on disk" "$?" "0"
has "…and says the row set is a grep, not a cluster" "a grep, not a cluster" "$W/unscanned.md"

echo "── K · scaffold creates an isolated runtime and never overwrites one"
python3 "$CP" scaffold --root "$R" --slug demo-runtime >/dev/null 2>&1
t "scaffold exits 0" "$?" "0"
for f in README.md runner.py fixture.sh BENCHMARK.md; do
  t "scaffold wrote $f" "$([ -f "$O/demo-runtime/$f" ] && echo yes)" "yes"
done
python3 "$O/demo-runtime/runner.py" --help >/dev/null 2>&1; t "the runner stub runs" "$?" "0"
python3 "$O/demo-runtime/runner.py" run >/dev/null 2>&1
t "an unimplemented runner exits 4, never a false success" "$?" "4"
bash -n "$O/demo-runtime/fixture.sh"; t "the fixture stub parses" "$?" "0"
bash "$O/demo-runtime/fixture.sh" >/dev/null 2>&1; t "the fixture stub passes its own sanity cases" "$?" "0"
has "README states installation is a release, not a flag" "installed nowhere" "$O/demo-runtime/README.md"
has "README keeps a 'what it does NOT do' section" "What it does NOT do" "$O/demo-runtime/README.md"
has "benchmark notes carry the symmetry checklist" "Symmetry checklist" "$O/demo-runtime/BENCHMARK.md"
has "benchmark notes keep the quality law above the numbers" "outranks every number" "$O/demo-runtime/BENCHMARK.md"
echo "SENTINEL" >> "$O/demo-runtime/runner.py"
python3 "$CP" scaffold --root "$R" --slug demo-runtime >/dev/null 2>&1
t "scaffolding over an existing runtime exits 2" "$?" "2"
has "…and the existing work is untouched" "SENTINEL" "$O/demo-runtime/runner.py"
python3 "$CP" scaffold --root "$R" --slug "///" >/dev/null 2>&1
t "an unusable slug is refused" "$?" "2"

echo
echo "compile fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
