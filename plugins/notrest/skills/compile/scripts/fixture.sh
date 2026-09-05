#!/bin/bash
# fixture.sh — asserts compile.py against a synthetic estate. Self-relative: runs
# from any cwd, writes only inside its own mktemp dir, touches no real project.
# Usage: bash <compile-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
# COMPILE_PY overrides the script under test. It exists so RED-FIRST is provable:
# point it at the previous revision and every arm for a new behavior must FAIL.
CP="${COMPILE_PY:-$(cd "$(dirname "$0")" && pwd)/compile.py}"
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
has "decisions.md explains its own format" \
  "Statuses: NEW | PROPOSED | DRAFTED | COMPILED | ADOPTED | PARKED | DECLINED" \
  "$O/decisions.md"
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
has "…via the refusal gate, named" "a cluster instead of a grep" "$W/none.md"
python3 "$CP" contract --root "$R" --slug "$SLUG" --write "$W/written.md" >/dev/null 2>&1
t "--write puts the draft on disk" "$([ -s "$W/written.md" ] && echo yes)" "yes"
python3 "$CP" contract --root "$R" --slug "$SLUG" --max-rows 2 > "$W/capped.md" 2>&1
t "--max-rows caps the table" \
  "$(grep -c '^| [0-9]* | _<rewrite' "$W/capped.md" | tr -d ' ')" "2"
has "…and says the cap was hit" "capped at --max-rows 2" "$W/capped.md"
# An unscanned root REFUSES rather than filling (contract changed upstream, merged
# 2026-08-31): no candidate means no contract, and the only safe output is no output.
# The old grep-fallback printed a table invented from the slug's own tokens.
R6="$W/unscanned"; mkdir -p "$R6"; cp "$R/COORD.md" "$R6/"
python3 "$CP" contract --root "$R6" --slug "release-changelog" > "$W/unscanned.md" 2>&1
t "contract on an unscanned root REFUSES, exit 3" "$?" "3"
has "…naming the law it applies" "a cluster instead of a grep" "$W/unscanned.md"
t "…and invents nothing resembling a contract table" \
  "$(grep -c '^| [0-9]* |' "$W/unscanned.md" | tr -d ' ')" "0"

# The empty-rows exit is a DIFFERENT condition (a real scanned candidate whose trail no
# longer yields rows) and was masked once the refusal gate landed ahead of it — this arm
# reaches it deliberately: scan first, then empty the trail, then ask.
R7="$W/emptied"; mkdir -p "$R7"; cp "$R/COORD.md" "$R7/"
python3 "$CP" scan --root "$R7" >/dev/null 2>&1
printf '# COORD.md — session coordination ledger\n\n## LEDGER\n' > "$R7/COORD.md"
python3 "$CP" contract --root "$R7" --slug "$SLUG" > "$W/emptied.md" 2>&1
t "a scanned candidate whose trail emptied exits 3" "$?" "3"
has "…via the empty-rows wording, not the refusal" "estate entries — there is nothing to reconstruct" "$W/emptied.md"

echo "── K · scaffold creates an isolated runtime and never overwrites one"
python3 "$CP" scaffold --root "$R" --slug demo-runtime >/dev/null 2>&1
t "scaffold exits 0" "$?" "0"
for f in README.md runner.py fixture.sh benchmark.sh BENCHMARK.md; do
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

echo "── L · auto: the standing authorization lives OUTSIDE the estate (docket 8c)"

# WHY IT MOVED (refuter, 2026-09-01 — PLAUSIBLE, now closed): compile/.auto-build sat
# INSIDE the repo, so any lane with write access to the tree could grant itself the
# owner's standing build authorization, and any clone carried someone else's opt-in.
# Authorization is now owner-private machine state at
#   ${NOTREST_HOME:-~/.notrest}/auto-build/<sha256 of the estate realpath>.json
# — unforgeable from inside the tree and uncopyable by a clone. NOTREST_HOME exists so
# this fixture never writes into the real home; the default is the only shipped path.
export NOTREST_HOME="$W/nrhome"
mk(){ python3 -c 'import hashlib, os, sys
base = os.environ.get("NOTREST_HOME") or os.path.expanduser("~/.notrest")
print(os.path.join(base, "auto-build",
      hashlib.sha256(os.path.realpath(sys.argv[1]).encode("utf-8")).hexdigest() + ".json"))' "$1"; }

A="$W/autoroot"; mkdir -p "$A"
MARK="$(mk "$A")"
LEGACY="$A/compile/.auto-build"

python3 "$CP" auto --root "$A" > "$W/auto.txt" 2>&1
t "bare auto with no marker exits 5" "$?" "5"
has "…and says how to turn it on" "auto --on" "$W/auto.txt"
t "…and wrote nothing" "$([ -e "$MARK" ] && echo wrote || echo none)" "none"

# Refuter F2 (2026-09-01, CONFIRMED pre-fix): auto wrote its marker at a cwd-relative
# root the hooks never read, and --off at the real root could not clear it. A --root
# that is not the estate root the hooks resolve is REFUSED, exit 2, naming it. The
# refusal survives the move: the marker's NAME is derived from that root.
G="$W/gitestate"; mkdir -p "$G/sub"; ( cd "$G" && git init -q ) >/dev/null 2>&1
python3 "$CP" auto --root "$G/sub" --on > "$W/auto-sub.txt" 2>&1
t "auto --on at a git SUBdir is refused" "$?" "2"
has "…naming the root the hooks resolve" "not the estate root the hooks resolve" "$W/auto-sub.txt"
t "…and no stray marker landed" "$([ -e "$(mk "$G/sub")" ] && echo stray || echo none)" "none"
python3 "$CP" auto --root "$G" --on >/dev/null 2>&1
t "auto --on at the git TOPLEVEL is accepted" "$?" "0"

python3 "$CP" auto --root "$A" --on > "$W/auto.txt" 2>&1
t "auto --on exits 0" "$?" "0"
t "…and the marker exists OUTSIDE the estate" "$([ -f "$MARK" ] && echo yes || echo no)" "yes"
t "…and NOTHING was written inside the estate" \
  "$(find "$A" -name '.auto-build*' 2>/dev/null | wc -l | tr -d ' ')" "0"
has "…and the opt-in restates the hard law where the owner reads it" \
  "never auto-installs" "$W/auto.txt"
has "…naming what it actually authorizes" "authorizes DISPATCH only" "$W/auto.txt"
has "…and prints the owner-private path it wrote" "$MARK" "$W/auto.txt"
t "the marker is ONE json line" "$(wc -l < "$MARK" | tr -d ' ')" "1"
t "the marker parses, and says opted=true" "$(python3 -c '
import json,sys
d = json.load(open(sys.argv[1]))
print(d.get("opted") is True and isinstance(d.get("stamp"), str) and bool(d["stamp"]))
' "$MARK")" "True"
t "…and names the estate it authorizes (a marker is never anonymous)" "$(python3 -c '
import json,os,sys
print(os.path.realpath(json.load(open(sys.argv[1]))["estate"]) == os.path.realpath(sys.argv[2]))
' "$MARK" "$A")" "True"
t "…with a UTC stamp in the estate's own grammar" "$(python3 -c '
import json,re,sys
print(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z",
                        json.load(open(sys.argv[1]))["stamp"])))
' "$MARK")" "True"
t "the marker file name is the sha256 of the estate realpath" "$(python3 -c '
import hashlib,os,sys
print(os.path.basename(sys.argv[1]) ==
      hashlib.sha256(os.path.realpath(sys.argv[2]).encode("utf-8")).hexdigest() + ".json")
' "$MARK" "$A")" "True"
t "the atomic write left no .tmp behind" \
  "$([ -e "$MARK.tmp" ] && echo left || echo none)" "none"

python3 "$CP" auto --root "$A" > "$W/auto.txt" 2>&1
t "bare auto with the marker exits 0" "$?" "0"
has "…and reports when it was opted" "auto-build: ON since" "$W/auto.txt"

# THE POINT OF THE MOVE: a marker written INSIDE the tree — by a lane, or carried in
# by a clone — is not an authorization any more.
python3 "$CP" auto --root "$A" --off >/dev/null 2>&1
mkdir -p "$A/compile"
printf '{"opted": true, "stamp": "2026-08-31 12:00Z"}\n' > "$LEGACY"
python3 "$CP" auto --root "$A" > "$W/auto-legacy.txt" 2>&1
t "an in-repo marker is NOT an authorization (a lane cannot grant it)" "$?" "5"
has "…and the migration is stated once, not left to be guessed" \
  "compile/.auto-build is IGNORED" "$W/auto-legacy.txt"
has "…naming where authorization actually lives now" "$MARK" "$W/auto-legacy.txt"

# A marker whose estate field names SOMEONE ELSE's tree is not this estate's opt-in,
# even if it lands under the right filename (a copied ~/.notrest, a restored backup).
python3 "$CP" auto --root "$A" --on >/dev/null 2>&1
python3 -c 'import json,sys
p = sys.argv[1]; d = json.load(open(p)); d["estate"] = "/somewhere/else"
open(p, "w").write(json.dumps(d) + "\n")' "$MARK"
python3 "$CP" auto --root "$A" >/dev/null 2>&1
t "a marker naming a DIFFERENT estate is refused (5)" "$?" "5"
rm -f "$LEGACY"

python3 "$CP" auto --root "$A" --on >/dev/null 2>&1
python3 "$CP" auto --root "$A" --off >/dev/null 2>&1
t "auto --off exits 0" "$?" "0"
t "…and the marker is gone" "$([ -e "$MARK" ] && echo left || echo none)" "none"
python3 "$CP" auto --root "$A" >/dev/null 2>&1
t "status after --off is 5 again" "$?" "5"
python3 "$CP" auto --root "$A" --off >/dev/null 2>&1
t "--off on an already-off estate is still 0" "$?" "0"

# A corrupt marker is NOT an opt-in — the same ruling the hook makes, made here too.
python3 "$CP" auto --root "$A" --on >/dev/null 2>&1
for BADMARK in 'garbage{' '{"opted": false}' '[]' '{}' ''; do
  printf '%s' "$BADMARK" > "$MARK"
  python3 "$CP" auto --root "$A" >/dev/null 2>&1
  t "malformed marker [$BADMARK] reads as NOT opted (5)" "$?" "5"
done
rm -f "$MARK"

python3 "$CP" auto --root "$A" --on --off >/dev/null 2>&1
t "--on and --off together are refused (2)" "$?" "2"

# ── RB-4 (refuter, MODERATE, 2026-09-01): NOTREST_HOME REOPENS 8c.
# The override exists so fixtures never write the real home — but nothing stopped it
# being pointed back INSIDE the estate, which reinstates exactly the hole the move
# closed: a store under the tree is writable by any lane and travels with a clone.
# Both readers now refuse a store whose realpath sits inside the estate root.
IN="$A/.nr"
NOTREST_HOME="$IN" python3 "$CP" auto --on --root "$A" > "$W/auto-in.txt" 2>&1
t "a store INSIDE the estate is refused by auto --on (2)" "$?" "2"
has "…naming why (an in-estate store is not owner-private)" \
  "inside the estate" "$W/auto-in.txt"
t "…and nothing was written into the estate" \
  "$(find "$A" -name '*.json' -path '*auto-build*' 2>/dev/null | wc -l | tr -d ' ')" "0"
# even a marker planted there by hand is not an authorization
mkdir -p "$IN/auto-build"
INMARK="$(NOTREST_HOME="$IN" mk "$A")"
printf '{"opted": true, "stamp": "2026-08-31 12:00Z", "estate": "%s"}\n' \
  "$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$A")" > "$INMARK"
NOTREST_HOME="$IN" python3 "$CP" auto --root "$A" > "$W/auto-in2.txt" 2>&1
# 2, not 5: 5 means "OFF, turn it on with --on" and --on is refused here too, so the
# refusal code is the honest one. What must never happen is a report of ON.
t "a hand-planted in-estate marker is refused, never reported ON (2)" "$?" "2"
hasnt "…and the status never says ON" "auto-build: ON" "$W/auto-in2.txt"

# ── RB-5: the STATUS path lacked the containment the hook already had, so `auto` said
# ON for a marker session-start refuses — a split verdict between the two readers of
# one file is worse than either verdict alone.
python3 "$CP" auto --root "$A" --on >/dev/null 2>&1
mkdir -p "$W/planted"
printf '{"opted": true, "stamp": "planted", "estate": "%s"}\n' \
  "$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$A")" \
  > "$W/planted/forged.json"
rm -f "$MARK"; ln -sf "$W/planted/forged.json" "$MARK"
python3 "$CP" auto --root "$A" > "$W/auto-esc.txt" 2>&1
t "a marker symlinked OUT of the store reads as OFF (5)" "$?" "5"
has "…and says the two readers agree on why" "escapes" "$W/auto-esc.txt"
rm -f "$MARK"

echo "── L2 · the SessionStart hook reads the owner-private marker, and only that"

# The hooks are COPIED out of the plugin tree: session-start.sh self-updates its own
# clone in the background, and a fixture must never fire a git pull on this repo.
HKS="$W/hooks"; mkdir -p "$HKS"
cp "$(cd "$(dirname "$0")/../../../hooks" && pwd)"/*.sh "$HKS/" 2>/dev/null
AB="$W/hookestate"; mkdir -p "$AB/compile"; ( cd "$AB" && git init -q ) >/dev/null 2>&1
printf '{"candidates":[{"slug":"release-ritual","occurrences":7,"ripe":true,"status":"NEW"}]}\n' \
  > "$AB/compile/candidates.json"
ABMARK="$(mk "$AB")"

( cd "$AB" && bash "$HKS/session-start.sh" ) > "$W/o" 2>&1
t "no authorization → hook exits 0" "$?" "0"
has "no authorization → the OLD ripe nudge is unchanged" \
  "Ripe compile candidate: release-ritual seen 7x" "$W/o"
hasnt "no authorization → nothing claims one" "AUTO-BUILD opted in" "$W/o"

# the legacy in-repo marker: ignored by the hook too, and SAID so once.
printf '{"opted": true, "stamp": "2026-08-31 12:00Z"}\n' > "$AB/compile/.auto-build"
( cd "$AB" && bash "$HKS/session-start.sh" ) > "$W/o" 2>&1
t "legacy in-repo marker → hook still exits 0" "$?" "0"
hasnt "legacy in-repo marker grants NOTHING" "AUTO-BUILD opted in" "$W/o"
has "…and the hook says the authorization moved" "compile/.auto-build is IGNORED" "$W/o"
rm -f "$AB/compile/.auto-build"

python3 "$CP" auto --root "$AB" --on >/dev/null 2>&1
( cd "$AB" && bash "$HKS/session-start.sh" ) > "$W/o" 2>&1
t "owner-private marker → hook exits 0" "$?" "0"
has "…and the echo carries the authorization" "AUTO-BUILD opted in" "$W/o"
has "…and names ONE opus lane for the ripe candidate" \
  "dispatch ONE opus builder lane this session for ripe candidate release-ritual" "$W/o"
has "…and restates the hard law in the echo itself" \
  "NEVER installed: shipping stays the owner's act" "$W/o"
hasnt "…and REPLACES the old nudge rather than doubling it" "Ripe compile candidate" "$W/o"

for BADMARK in 'garbage{' '{"opted": false}' '[]' '{}' ''; do
  printf '%s' "$BADMARK" > "$ABMARK"
  ( cd "$AB" && bash "$HKS/session-start.sh" ) > "$W/o" 2>&1
  t "malformed marker [$BADMARK] → hook still exits 0" "$?" "0"
  hasnt "malformed marker [$BADMARK] claims no authorization" "AUTO-BUILD opted in" "$W/o"
  has "malformed marker [$BADMARK] falls back to the old nudge" \
    "Ripe compile candidate: release-ritual" "$W/o"
done

# containment, inherited from the COORD.md law: a marker that is a symlink OUT of the
# authorization store is not this machine's authorization.
mkdir -p "$W/elsewhere"
printf '{"opted": true, "stamp": "2026-08-31 12:00Z", "estate": "%s"}\n' "$AB" \
  > "$W/elsewhere/planted.json"
ln -sfn "$W/elsewhere/planted.json" "$ABMARK"
( cd "$AB" && bash "$HKS/session-start.sh" ) > "$W/o" 2>&1
t "escaping-symlink marker → hook still exits 0" "$?" "0"
hasnt "escaping-symlink marker claims NO authorization" "AUTO-BUILD opted in" "$W/o"
rm -f "$ABMARK"

# an opt-in is not a licence to invent work: with nothing ripe, neither echo fires.
AB2="$W/hookestate-noripe"; mkdir -p "$AB2/compile"; ( cd "$AB2" && git init -q ) >/dev/null 2>&1
printf '{"candidates":[{"slug":"cold","occurrences":2,"ripe":false,"status":"NEW"}]}\n' \
  > "$AB2/compile/candidates.json"
python3 "$CP" auto --root "$AB2" --on >/dev/null 2>&1
( cd "$AB2" && bash "$HKS/session-start.sh" ) > "$W/o" 2>&1
t "opted in but nothing ripe → hook exits 0" "$?" "0"
hasnt "opted in but nothing ripe → no AUTO-BUILD echo" "AUTO-BUILD opted in" "$W/o"

# RB-4, hook side: a store redirected INTO the estate authorizes nothing, and the hook
# says so rather than going quiet — a standing authorization that silently stops working
# is the failure mode this whole marker exists to avoid.
ABIN="$AB/.nr"; mkdir -p "$ABIN/auto-build"
INHOOK="$(NOTREST_HOME="$ABIN" mk "$AB")"
printf '{"opted": true, "stamp": "2026-08-31 12:00Z", "estate": "%s"}\n' \
  "$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$AB")" > "$INHOOK"
( cd "$AB" && NOTREST_HOME="$ABIN" bash "$HKS/session-start.sh" ) > "$W/o" 2>&1
t "in-estate store → hook still exits 0" "$?" "0"
hasnt "in-estate store grants NO authorization" "AUTO-BUILD opted in" "$W/o"
has "…and the hook says why it ignored it" "inside the estate" "$W/o"
has "…and falls back to the old nudge" "Ripe compile candidate: release-ritual" "$W/o"

echo "── M · a bounded corpus scans in bounded time, and says so while it works (F5)"
# The 4.6.1 audit lane killed `scan` at 120 s and filed it as a HANG. It was not hung: it
# printed nothing for the whole run, and a silent long-running tool is indistinguishable
# from a dead one. Two things are gated here, and neither is "it got faster" — speed is a
# means; the promises are (1) a bounded corpus finishes inside a bound the SKILL.md states,
# and (2) the run narrates itself so a reader can tell working from wedged.
#
# THE BOUND, AND WHY THIS NUMBER. 260 COORD entries over a ~48-token vocabulary — the shape
# of a real estate's largest family, and the size the profile was taken at. Measured
# 2026-09-01 on an idle M-series laptop: 2.1 s after the fix, 17.5 s before it. The gate is
# 10 s: ~4.6x headroom over the measured time so a loaded CI box does not flake, and well
# under the pre-fix cost so a regression to the old quadratic recomputation FAILS here
# rather than merely feeling slow. Cost grows with the SQUARE of the largest family, so
# raising this corpus means re-measuring the bound, not nudging it.
PERF="$W/perf"; mkdir -p "$PERF/spend"
python3 - "$PERF/COORD.md" 260 <<'PYGEN'
import sys, random
# seeded: the same corpus every run, or the bound is timing a different problem each time
random.seed(20260901)
vocab = ["parser","exporter","indexer","viewer","router","ledger","packet","fixture","gate",
         "hook","volume","ruling","refuter","scanner","manifest","changelog","resolver","cache",
         "budget","surface","transcript","commission","lane","estate","roster","render","stamp",
         "anchor","marker","protocol","upgrade","backup","clause","policy","offload","seat",
         "difficulty","bounded","judgment","dispatch","receipt","audit","docket","arm","corpus",
         "profile","merge","cluster","threshold","signature","vocabulary","entry","seal","probe"]
n = int(sys.argv[2])
L = ["# COORD.md — session coordination ledger", "## LEDGER"]
for i in range(n):
    L.append("- [2026-03-%02d %02d:00Z] [main] %s -> %s | evidence: commit %06x"
             % (1 + i % 28, i % 24, " ".join(random.sample(vocab, 7)),
                " ".join(random.sample(vocab, 7)), 0xaa0000 + i))
open(sys.argv[1], "w").write("\n".join(L) + "\n")
PYGEN
printf '# spend ledger — append-only via spend.py; grades: observed|estimate\n' > "$PERF/spend/ledger.md"
t "the perf corpus is the size the bound was measured at" \
  "$(grep -c '^- \[' "$PERF/COORD.md")" "260"

PSTART="$(python3 -c 'import time;print(time.time())')"
python3 "$CP" scan --root "$PERF" > "$W/perf.out" 2> "$W/perf.err"
PRC=$?
PELAPSED="$(python3 -c "import time;print('%.1f' % (time.time() - $PSTART))")"
t "the bounded scan exits 0" "$PRC" "0"
t "…inside the 10s bound (measured 2.1s; pre-fix 17.5s) — actual ${PELAPSED}s" \
  "$(python3 -c "print('under' if $PELAPSED < 10.0 else 'OVER')")" "under"
# (2) it must be VISIBLY alive: stdout stays the machine surface, stderr narrates.
t "progress went to stderr, not stdout" \
  "$(python3 -c "print('yes' if open('$W/perf.err').read().strip() else 'no')")" "yes"
has "…naming the tool, so a piped log says who is talking" "compile scan:" "$W/perf.err"
has "…and the family it is working on, with its entry count" "coord: clustering 260 entries" "$W/perf.err"
has "…and reporting when that family finished" "coord: done in" "$W/perf.err"
t "at least two progress lines reached stderr" \
  "$(python3 -c "print(sum(1 for l in open('$W/perf.err') if l.strip().startswith('compile scan:')) >= 2)")" "True"
hasnt "stdout stays clean of the narration" "compile scan:" "$W/perf.out"
# the optimization is only lawful if it changed nothing: same corpus, same candidates
cp "$PERF/compile/candidates.json" "$W/perf1.json"
python3 "$CP" scan --root "$PERF" >/dev/null 2>&1
t "…and the bounded scan is deterministic across runs" \
  "$(python3 -c "
import json
a=json.load(open('$W/perf1.json')); b=json.load(open('$PERF/compile/candidates.json'))
for d in (a,b): d.pop('generated',None)
print(a==b)")" "True"

echo "── N · draft: every ripe candidate scaffolded, at zero model tokens (docket B2)"
# The gap this closes: scanning was automatic and the nudge was automatic, and then a
# human had to type /compile before anything existed to work ON. The expensive half of
# Step 1 is a grep the script already does; the skeleton is a template. Neither waits.
R8="$W/pipeline"; cp -R "$R" "$R8"; rm -rf "$R8/compile"
python3 "$CP" scan --root "$R8" >/dev/null 2>&1
python3 "$CP" draft --root "$R8" --all-ripe > "$W/draft.txt" 2>&1
t "draft --all-ripe exits 0" "$?" "0"
J8(){ python3 -c "
import json,sys
d=json.load(open('$R8/compile/candidates.json'))
print(eval(sys.argv[1], {'d':d,'c':d['candidates'],'top':d['candidates'][0] if d['candidates'] else {}}))
" "$1"; }
S8="$(J8 "top['slug']")"
D8="$R8/compile/$S8"
for f in CONTRACT.md README.md runner.py fixture.sh benchmark.sh BENCHMARK.md; do
  t "draft wrote $f" "$([ -f "$D8/$f" ] && echo yes)" "yes"
done
has "the drafted contract IS the trail-cited Step-1 table" \
  "| # | Responsibility | Evidence | Required for parity? | Owner today | Owner after | Why |" \
  "$D8/CONTRACT.md"
has "…carrying real citations, not placeholders" "[COORD 2026-01-02" "$D8/CONTRACT.md"
has "the ruling was recorded as DRAFTED" "status=DRAFTED" "$R8/compile/decisions.md"
has "…saying plainly what a draft is NOT" "not built, not benchmarked, not adopted" \
  "$R8/compile/decisions.md"
python3 "$D8/runner.py" run >/dev/null 2>&1
t "a drafted runner still exits 4 — a scaffold cannot report success" "$?" "4"
bash "$D8/benchmark.sh" >/dev/null 2>&1
t "…and the benchmark harness exits 4 until it is written" "$?" "4"
has "…saying why, where the reader is" "no scenarios replayed" "$D8/benchmark.sh"
# IDEMPOTENCE IS THE WHOLE POINT: the pulse daemon calls this after every scan.
echo "SENTINEL-DRAFT" >> "$D8/runner.py"
python3 "$CP" draft --root "$R8" --all-ripe > "$W/draft2.txt" 2>&1
t "a second draft exits 0" "$?" "0"
has "…and SKIPS the existing slug, saying so" "already drafted — not counted against the cap" "$W/draft2.txt"
has "…and the lane's work is untouched" "SENTINEL-DRAFT" "$D8/runner.py"
t "…and no second DRAFTED line was appended" \
  "$(grep -c 'status=DRAFTED' "$R8/compile/decisions.md" | tr -d ' ')" "1"
python3 "$CP" scan --root "$R8" >/dev/null 2>&1
t "a DRAFTED candidate carries over the next scan" "$(J8 "top['status']")" "DRAFTED"
python3 "$CP" report --root "$R8" >/dev/null 2>&1
t "…so the ripe-and-unruled nudge stops firing" "$?" "0"
# hook-safety: the daemon calls draft on estates that have never been scanned
R9="$W/undrafted"; mkdir -p "$R9"
python3 "$CP" draft --root "$R9" --all-ripe > "$W/draft3.txt" 2>&1
t "draft on an unscanned estate is hook-safe (exit 0)" "$?" "0"
has "…and says so rather than inventing a candidate" "no scan yet" "$W/draft3.txt"
python3 "$CP" draft --root "$R8" --slug quantum-basket-weaving >/dev/null 2>&1
t "draft --slug for a candidate the scan never saw exits 3" "$?" "3"
python3 "$CP" draft --root "$R8" >/dev/null 2>&1
t "draft with neither --all-ripe nor --slug is a usage error (2)" "$?" "2"

echo "── O · ADOPTED is the one ruling that cannot be written on a say-so (docket B4)"
DEC8="$R8/compile/decisions.md"; cp "$DEC8" "$W/dec-before.md"
python3 "$CP" decide --root "$R8" --slug "$S8" --status ADOPTED > "$W/adopt0.txt" 2>&1
t "ADOPTED with no receipts is REFUSED (2)" "$?" "2"
has "…naming every receipt it needs" "missing: fixture, benchmark, refuter" "$W/adopt0.txt"
has "…and why the bar is there" "outranks any of them" "$W/adopt0.txt"
t "…and NOTHING was written" \
  "$(cmp -s "$DEC8" "$W/dec-before.md" && echo identical || echo mutated)" "identical"
python3 "$CP" decide --root "$R8" --slug "$S8" --status ADOPTED \
  --evidence "fixture=x/fixture.sh exit 0" --evidence "refuter=x/REFUTER.md CLEAN" \
  > "$W/adopt1.txt" 2>&1
t "two of three receipts is still REFUSED (2)" "$?" "2"
has "…naming exactly the missing one" "missing: benchmark" "$W/adopt1.txt"
python3 "$CP" decide --root "$R8" --slug "$S8" --status ADOPTED --evidence "bogus=x" \
  >/dev/null 2>&1
t "a receipt kind nobody reads is refused (2)" "$?" "2"
python3 "$CP" decide --root "$R8" --slug "$S8" --status ADOPTED --evidence "fixture" \
  >/dev/null 2>&1
t "an --evidence with no REF is refused (2)" "$?" "2"
t "…and still nothing was written" \
  "$(cmp -s "$DEC8" "$W/dec-before.md" && echo identical || echo mutated)" "identical"
python3 "$CP" decide --root "$R8" --slug "$S8" --status ADOPTED \
  --evidence "fixture=$S8/fixture.sh exit 0" --evidence "benchmark=$S8/benchmark.sh exit 0" \
  --evidence "refuter=$S8/REFUTER.md CLEAN" > "$W/adopt2.txt" 2>&1
t "all three receipts are accepted (0)" "$?" "0"
has "…and the receipts are IN the ledger line, re-readable" "evidence=\"fixture=" "$DEC8"
has "…with a COORD line the seat can paste verbatim" "COORD line: - [" "$W/adopt2.txt"
has "…that carries all three receipts" "refuter=$S8/REFUTER.md CLEAN" "$W/adopt2.txt"
# every other status is unchanged by this gate — the bar is on ADOPTED alone
python3 "$CP" decide --root "$R8" --slug "$S8" --status DECLINED --note "owner said no" \
  >/dev/null 2>&1
t "DECLINED still needs no receipts (0)" "$?" "0"

echo "── P · auto-run: the unattended pipeline, and every rail armed with a FAKE runner"
# ⛔ NO TEST HERE EVER SPENDS A TOKEN. The runner is injectable precisely so this section
# can exist: `--runner` takes a shell command, and the command below is a script this
# fixture writes. It reads the prompt on stdin exactly as `claude -p` does and answers
# with the CLI's own JSON shape. A rail nobody has watched fire is a rail nobody tested.
FAKE="$W/fake-runner.sh"
cat > "$FAKE" <<'FAKEEOF'
#!/bin/bash
# A fake headless runner. Contacts nothing. Behaviour is driven by FAKE_* env vars so one
# script can play every arm: a clean build, an auth failure, a crash, a defect, silence.
P="$(cat)"                      # the prompt arrives on stdin, like the real runner's
TOK="${FAKE_TOKENS:-1000}"
echo "${NOTREST_UNATTENDED:-unset}" >> "$FAKE_ENV_LOG"
# the env the child actually got: the scrub is asserted from the child's own side
{ echo "CLAUDECODE=${CLAUDECODE:-ABSENT}"
  echo "CLAUDE_CODE_ENTRYPOINT=${CLAUDE_CODE_ENTRYPOINT:-ABSENT}"
  echo "ANTHROPIC_API_KEY_PRESENT=$([ -n "${ANTHROPIC_API_KEY:-}" ] && echo yes || echo no)"
  # PRESENCE ONLY. The fixture must never write a credential's value anywhere, not even
  # its own scratch log — an arm that leaks a secret to prove a secret was passed has
  # tested the wrong thing.
  echo "OAUTH_PRESENT=$([ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && echo yes || echo no)"
} >> "$FAKE_ENV_LOG"
case "$P" in
  *BUILDER*)
    echo "build" >> "$FAKE_STEP_LOG"
    # The two auth shapes PROBED at the seat on this estate, 2026-09-05. `authexp` is the
    # one that matters: subtype "success", is_error true, and EXIT 0 — a runner judged on
    # its exit code alone reads it as a finished build.
    [ "${FAKE_BUILD:-ok}" = "auth" ] && { echo "Not logged in · Please run /login"; exit 1; }
    [ "${FAKE_BUILD:-ok}" = "authexp" ] && {
      printf '{"type":"result","subtype":"success","is_error":true,"result":"Failed to authenticate: OAuth session expired and could not be refreshed","total_cost_usd":0}'
      exit 0; }
    [ "${FAKE_BUILD:-ok}" = "iserror" ] && {
      printf '{"type":"result","subtype":"success","is_error":true,"result":"the model refused the prompt","usage":{"input_tokens":50,"output_tokens":0}}'
      exit 0; }
    [ "${FAKE_BUILD:-ok}" = "crash" ] && { echo "boom: could not open the contract" >&2; exit 9; }
    printf '#!/usr/bin/env python3\nimport sys\nprint("compiled")\nsys.exit(0)\n' > runner.py
    printf '#!/bin/bash\necho "  PASS  real logic exercised"\nexit %s\n' \
      "${FAKE_FIXTURE_RC:-0}" > fixture.sh
    printf '#!/bin/bash\necho "old 1000 tok / new 12 tok over 4 replayed scenarios"\nexit %s\n' \
      "${FAKE_BENCH_RC:-0}" > benchmark.sh
    chmod +x fixture.sh benchmark.sh
    # `nousage` withholds the usage BLOCK only — the build still produced a runtime, so an
    # arm about cap accounting is not quietly measuring a red benchmark instead.
    [ "${FAKE_BUILD:-ok}" = "nousage" ] && {
      printf '{"type":"result","is_error":false,"result":"BUILD: DONE"}'; exit 0; }
    printf '{"type":"result","is_error":false,"result":"BUILD: DONE","usage":{"input_tokens":%s,"output_tokens":0}}' "$TOK"
    ;;
  *REFUTER*)
    echo "refute" >> "$FAKE_STEP_LOG"
    case "${FAKE_REFUTE:-clean}" in
      defect) printf 'REFUTER: DEFECT the fixture mocks the parser it tests\n' > REFUTER.md
              printf '{"type":"result","is_error":false,"result":"REFUTER: DEFECT the fixture mocks the parser it tests","usage":{"input_tokens":%s,"output_tokens":0}}' "$TOK" ;;
      silent) printf '{"type":"result","is_error":false,"result":"I had a good look around.","usage":{"input_tokens":%s,"output_tokens":0}}' "$TOK" ;;
      nousage) printf 'attacked five ways, nothing held\nREFUTER: CLEAN\n' > REFUTER.md
              printf '{"type":"result","is_error":false,"result":"REFUTER: CLEAN"}' ;;
      *)      printf 'attacked five ways, nothing held\nREFUTER: CLEAN\n' > REFUTER.md
              printf '{"type":"result","is_error":false,"result":"REFUTER: CLEAN","usage":{"input_tokens":%s,"output_tokens":0}}' "$TOK" ;;
    esac
    ;;
esac
FAKEEOF
chmod +x "$FAKE"
# The credential the unattended runner needs. `claude setup-token` prints a long-lived
# token and does NOT log the CLI in, and the pulse daemon is spawned by hooks inside the
# app, so no shell export can ever reach it — a file under the owner-private root is the
# only place the two sides meet. Mode 0600 in an owner-only directory, checked, refused
# otherwise. NOTREST_HOME already points into this fixture's scratch dir.
CREDDIR="$NOTREST_HOME/credentials"; CRED="$CREDDIR/claude-oauth-token"
mkcred(){ mkdir -p "$CREDDIR"; chmod "${2:-700}" "$CREDDIR"
          printf 'fixture-token-never-a-real-one\n' > "$CRED"; chmod "${1:-600}" "$CRED"; }
mkcred
export FAKE_ENV_LOG="$W/fake-env.log" FAKE_STEP_LOG="$W/fake-steps.log"
: > "$FAKE_ENV_LOG"; : > "$FAKE_STEP_LOG"
TODAY="$(date -u +%F)"
AR(){ python3 "$CP" auto-run --root "$RA" --runner "$FAKE" --today "$TODAY" "$@"; }
ARM(){ python3 "$CP" decide --root "$RA" --slug "$SA" --status DRAFTED \
        --note "re-armed by the fixture" >/dev/null 2>&1; }

# A fresh estate, drafted and ready to build. git init so the estate-root check passes.
RA="$W/autorun"; cp -R "$R" "$RA"; rm -rf "$RA/compile"
( cd "$RA" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RA" >/dev/null 2>&1
python3 "$CP" draft --root "$RA" --all-ripe >/dev/null 2>&1
SA="$(python3 -c "
import json;print(json.load(open('$RA/compile/candidates.json'))['candidates'][0]['slug'])")"
LEDGER="$RA/spend/ledger.md"
LN(){ grep -c 'lane=daemon' "$LEDGER" 2>/dev/null | tr -d ' '; }

# ── authorization: unattended spending is a SEPARATE opt-in from dispatch ──
AR --next > "$W/ar-noauth.txt" 2>&1
t "auto-run on an unauthorized estate exits 5" "$?" "5"
has "…and says nothing was spent" "Nothing was run and nothing was spent" "$W/ar-noauth.txt"
t "…and no receipt was written" "$(LN)" "0"
python3 "$CP" auto --root "$RA" --on >/dev/null 2>&1
AR --next > "$W/ar-dispatch.txt" 2>&1
t "a DISPATCH-only marker still refuses to spend (5)" "$?" "5"
has "…naming the flag that would change that" "auto --on --unattended" "$W/ar-dispatch.txt"
t "…and still no receipt" "$(LN)" "0"

# ── the marker carries the budget, and `auto` prints every rail back ──
python3 "$CP" auto --root "$RA" --on --daily-cap 100 >/dev/null 2>&1
t "a cap without --unattended is refused (2)" "$?" "2"
python3 "$CP" auto --root "$RA" --unattended >/dev/null 2>&1
t "--unattended without --on is refused (2)" "$?" "2"
python3 "$CP" auto --root "$RA" --on --unattended --daily-cap 0 >/dev/null 2>&1
t "a zero cap is not a budget (2)" "$?" "2"
python3 "$CP" auto --root "$RA" --on --unattended --daily-cap 12000 --run-cap 9000 \
  --max-turns 40 > "$W/auto-un.txt" 2>&1
t "auto --on --unattended --daily-cap --run-cap --max-turns exits 0" "$?" "0"
has "…and says the daemon may now SPEND" "may run \`auto-run\` and SPEND tokens" "$W/auto-un.txt"
has "…and that it still never installs" "never installs anything" "$W/auto-un.txt"
python3 "$CP" auto --root "$RA" > "$W/auto-print.txt" 2>&1
t "bare auto exits 0 when opted in" "$?" "0"
has "auto prints the unattended state" "unattended: YES" "$W/auto-print.txt"
has "auto prints the daily cap" "daily cap  : 12,000 tokens/day" "$W/auto-print.txt"
has "auto prints the run cap" "run cap    : 9,000 tokens per auto-run" "$W/auto-print.txt"
has "auto prints the turn limit" "max turns  : 40 per headless runner call" "$W/auto-print.txt"
has "auto prints the two-strikes rule" "fails 2 times is PARKED" "$W/auto-print.txt"
has "auto prints the one-at-a-time lock" "one at a time: an estate-wide lock" "$W/auto-print.txt"
t "the marker carries the budget beside the opt-in" "$(python3 -c '
import json,sys
d = json.load(open(sys.argv[1]))
print(d.get("unattended") is True and d.get("daily_cap_tokens") == 12000
      and d.get("run_cap_tokens") == 9000 and d.get("max_turns") == 40)
' "$(mk "$RA")")" "True"

# ── --dry-run: the plan, and not one token ──
cp "$RA/compile/decisions.md" "$W/ar-dec-before.md"
AR --next --dry-run > "$W/ar-dry.txt" 2>&1
t "--dry-run exits 0" "$?" "0"
has "…printing the candidate it would run" "candidate     : $SA" "$W/ar-dry.txt"
has "…the steps in order" "BUILD (tokens) → fixture.sh (free) → REFUTE (tokens)" "$W/ar-dry.txt"
has "…the cap state it would run under" \
  "daily cap     : 0 spent today (conservative) of 12,000" "$W/ar-dry.txt"
has "…and that it spends nothing" "nothing is spent, no lock taken" "$W/ar-dry.txt"
t "…and it wrote no receipt" "$(LN)" "0"
t "…and ruled on nothing" \
  "$(cmp -s "$RA/compile/decisions.md" "$W/ar-dec-before.md" && echo identical || echo mutated)" \
  "identical"

# ── the green path, end to end ──
# Set the very variables a live session would have exported, so the scrub has something
# real to remove, plus a fake credential that must survive it.
: > "$FAKE_ENV_LOG"
export CLAUDECODE=1 CLAUDE_CODE_ENTRYPOINT=cli ANTHROPIC_API_KEY=fixture-not-a-real-key
AR --next > "$W/ar-green.txt" 2>&1
t "a fully green auto-run exits 0" "$?" "0"
has "…and adopts" "ADOPTED $SA" "$W/ar-green.txt"
has "…printing the COORD line for the estate to bank" "COORD line: - [" "$W/ar-green.txt"
has "…and restating that ADOPTED is not INSTALLED" "INSTALLED NOWHERE" "$W/ar-green.txt"
t "…the steps ran in the ruled order" "$(tr '\n' ' ' < "$FAKE_STEP_LOG" | tr -s ' ')" "build refute "
has "the ADOPTED ruling carries all three receipts" "status=ADOPTED" "$RA/compile/decisions.md"
t "…each one of them" "$(python3 -c "
line=[l for l in open('$RA/compile/decisions.md') if 'status=ADOPTED' in l][-1]
print(all(k in line for k in ('fixture=','benchmark=','refuter=')))")" "True"
t "every headless call left a receipt" "$(LN)" "2"
t "…each one naming the daemon lane and an explicit model" "$(python3 -c "
ls=[l for l in open('$LEDGER') if 'lane=daemon' in l]
print(all('lane=daemon' in l and 'model=opus' in l for l in ls) and len(ls)==2)")" "True"
t "…with the observed count from the runner's own JSON, not a guess" \
  "$(grep -c 'lane=daemon model=opus tokens=1000 grade=observed' "$LEDGER" | tr -d ' ')" "2"
has "the pulse log carries what happened while nobody watched" "ADOPTED $SA" \
  "$RA/pulse/auto-run.log"
t "NOTREST_UNATTENDED=1 was set on EVERY runner call" \
  "$(grep -c '^1$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"
# ⛔ THE SCRUB, ASSERTED FROM THE CHILD'S OWN SIDE. The pulse daemon is spawned by hooks
# inside a LIVE Claude session, so without the scrub a headless `claude -p` boots inside
# another Claude's environment. The fixture EXPORTS both variables before the run, so this
# arm fails if the scrub is ever removed.
t "the session's CLAUDECODE never reaches the runner" \
  "$(grep -c '^CLAUDECODE=ABSENT$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"
t "…nor any CLAUDE_CODE_* variable" \
  "$(grep -c '^CLAUDE_CODE_ENTRYPOINT=ABSENT$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"
t "…while a credential the owner supplied SURVIVES it (a daemon cannot answer /login)" \
  "$(grep -c '^ANTHROPIC_API_KEY_PRESENT=yes$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"
# the receipts must not turn spend's own gate red — an honest lane is a clean lane
SPY="$(cd "$(dirname "$0")/../../spend/scripts" && pwd)/spend.py"
python3 "$SPY" report --root "$RA" > "$W/ar-spend.txt" 2>&1
t "spend report stays CLEAN on the new daemon lane" "$?" "0"
has "…and counts the daemon calls as evidenced offloads" "routing: CLEAN" "$W/ar-spend.txt"

# ── THE OUROBOROS (found on this lane's own smoke test, before these arms existed):
# the daemon's receipts are ledger lines, so the scanner clustered the compiler's own
# spending into a ripe candidate that draft would scaffold and auto-run would then pay
# to compile. lane=daemon is dropped at the reader.
python3 "$CP" scan --root "$RA" >/dev/null 2>&1
t "the daemon's own receipts never become a candidate" "$(python3 -c "
import json
d=json.load(open('$RA/compile/candidates.json'))
print(not any('auto-run' in e['text'] for c in d['candidates'] for e in c['evidence']))")" "True"
# the estate's own 5 spend lines are still read; only the daemon's are dropped, and the
# count proves the drop happened at the READER rather than by a lucky stopword.
t "…because the lane is dropped at the reader, not stopworded" "$(python3 -c "
import json
d=json.load(open('$RA/compile/candidates.json'))
print([s['items'] for s in d['sources'] if s['name']=='spend/ledger.md'][0])")" "5"

# ── an ADOPTED slug is finished: --next never picks it again ──
AR --next > "$W/ar-done.txt" 2>&1
t "with nothing DRAFTED, auto-run exits 0 and says so" "$?" "0"
has "…naming why there was nothing to do" "nothing DRAFTED and buildable" "$W/ar-done.txt"
t "…and spent nothing doing it" "$(LN)" "2"

# ── RAIL (a) · ONE ESTATE LOCK: never two runs, never beside a live compile ──
ARM
python3 - "$RA/compile/.auto-run.lock" "$W/held" <<'LOCKPY' &
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX)
open(sys.argv[2], "w").write("held")
time.sleep(6)
LOCKPY
HOLDER=$!
for _ in $(seq 1 60); do [ -f "$W/held" ] && break; sleep 0.1; done
BEFORE_BUSY="$(LN)"
AR --next > "$W/ar-busy.txt" 2>&1
t "a second auto-run exits 0 while the lock is held" "$?" "0"
has "…saying BUSY rather than queueing behind it" "BUSY" "$W/ar-busy.txt"
has "…and that it started nothing" "Nothing started, nothing spent" "$W/ar-busy.txt"
t "…and it spent nothing" "$(LN)" "$BEFORE_BUSY"
kill "$HOLDER" 2>/dev/null; wait "$HOLDER" 2>/dev/null

# ── RAIL (d) · a not-logged-in runner stops the pipeline QUIETLY, with no retry ──
ARM
: > "$FAKE_STEP_LOG"
FAKE_BUILD=auth AR --next > "$W/ar-auth.txt" 2>&1
t "an auth failure exits 0 — a stop is not a crash" "$?" "0"
has "…naming it as an auth failure" "AUTH:" "$W/ar-auth.txt"
has "…quoting what the CLI actually said, not just a code" \
  "Not logged in · Please run /login" "$W/ar-auth.txt"
has "…and promising no retry storm" "NO retry" "$W/ar-auth.txt"
has "…because the slug is now in a cooldown" "cooldown (quiet stop 1 of 3" "$W/ar-auth.txt"
t "…it attempted exactly ONE call, then stopped" \
  "$(grep -c . "$FAKE_STEP_LOG" | tr -d ' ')" "1"
t "…the candidate's status is UNCHANGED" \
  "$(python3 -c "
rows=[l for l in open('$RA/compile/decisions.md') if 'slug=$SA ' in l]
print('status=DRAFTED' in rows[-1])")" "True"
t "…and the failed call was STILL receipted" "$(LN)" "3"
has "…as an unverifiable count, never as an invented number" \
  "tokens=unknown grade=estimate" "$LEDGER"
has "…saying where the number should have come from" "the CLI result carried no usage" \
  "$LEDGER"

# a runner that simply CRASHES is the same quiet stop — the pipeline never retries in-run
ARM
: > "$FAKE_STEP_LOG"
FAKE_BUILD=crash AR --next > "$W/ar-crash.txt" 2>&1
t "a crashing runner exits 0 (quiet stop)" "$?" "0"
has "…naming the exit code" "runner exited 9" "$W/ar-crash.txt"
t "…and made exactly one attempt" "$(grep -c . "$FAKE_STEP_LOG" | tr -d ' ')" "1"

# ── RAIL (c) · a result with no usage is receipted as UNKNOWN, never invented ──
# D1: an unknown-usage run is charged against the DAILY cap at the run ceiling, so this
# estate needs headroom — this arm is about the receipt, not about the cap.
python3 "$CP" auto --root "$RA" --on --unattended --daily-cap 90000000 --run-cap 9000 \
  --max-turns 40 >/dev/null 2>&1
ARM
BEFORE_NU="$(LN)"
FAKE_BUILD=nousage FAKE_REFUTE=clean AR --next >/dev/null 2>&1
t "a runner reporting no usage still completes (0)" "$?" "0"
t "…and still receipts every call" "$(python3 -c "print($(LN) - $BEFORE_NU)")" "2"
t "…with tokens=unknown, and no number anywhere near it" "$(python3 -c "
ls=[l for l in open('$LEDGER') if 'lane=daemon' in l]
bad=[l for l in ls if 'tokens=0 ' in l]
print(len(bad))")" "0"

# ── RAIL (b1) · the DAILY cap: 60% of it twice, and the next run is refused ──
# 11b, stated as a test: prove the cap FIRES, not that it is configured.
RB="$W/dailycap"; cp -R "$R" "$RB"; rm -rf "$RB/compile"
( cd "$RB" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RB" >/dev/null 2>&1
python3 "$CP" draft --root "$RB" --all-ripe >/dev/null 2>&1
SB="$(python3 -c "
import json;print(json.load(open('$RB/compile/candidates.json'))['candidates'][0]['slug'])")"
python3 "$CP" auto --root "$RB" --on --unattended --daily-cap 10000 --run-cap 900000 \
  >/dev/null 2>&1
ARB(){ python3 "$CP" auto-run --root "$RB" --runner "$FAKE" --today "$TODAY" "$@"; }
FAKE_TOKENS=6000 ARB --next > "$W/cap1.txt" 2>&1
t "run 1 completes: 6,000 then 6,000 against a 10,000 cap" "$?" "0"
t "…and both calls are on the ledger" \
  "$(grep -c 'lane=daemon.*tokens=6000' "$RB/spend/ledger.md" | tr -d ' ')" "2"
python3 "$CP" decide --root "$RB" --slug "$SB" --status DRAFTED --note "re-armed" \
  >/dev/null 2>&1
BEFORE_CAP="$(grep -c 'lane=daemon' "$RB/spend/ledger.md" | tr -d ' ')"
FAKE_TOKENS=6000 ARB --next > "$W/cap2.txt" 2>&1
t "the NEXT run is REFUSED by the daily cap (exit 6)" "$?" "6"
has "…before starting the step, not after paying for it" "REFUSED to start build" "$W/cap2.txt"
has "…naming the day's arithmetic" "12,000 of 10,000 daemon tokens" "$W/cap2.txt"
has "…and saying plainly that nothing was spent" "Nothing spent." "$W/cap2.txt"
t "…and no receipt was added" \
  "$(grep -c 'lane=daemon' "$RB/spend/ledger.md" | tr -d ' ')" "$BEFORE_CAP"
has "…the refusal is a pulse line, not a silence" "REFUSED to start build" \
  "$RB/pulse/auto-run.log"
t "…the day's cap is read from the LEDGER, so a fresh process cannot reset it" \
  "$(FAKE_TOKENS=6000 ARB --next >/dev/null 2>&1; echo $?)" "6"

# ── RAIL (b2) · the PER-RUN ceiling: a run that goes over is RECORDED as capped ──
RC="$W/runcap"; cp -R "$R" "$RC"; rm -rf "$RC/compile"
( cd "$RC" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RC" >/dev/null 2>&1
python3 "$CP" draft --root "$RC" --all-ripe >/dev/null 2>&1
SC_="$(python3 -c "
import json;print(json.load(open('$RC/compile/candidates.json'))['candidates'][0]['slug'])")"
python3 "$CP" auto --root "$RC" --on --unattended --daily-cap 90000000 --run-cap 500 \
  >/dev/null 2>&1
: > "$FAKE_STEP_LOG"
FAKE_TOKENS=1000 python3 "$CP" auto-run --root "$RC" --runner "$FAKE" --today "$TODAY" \
  --next > "$W/runcap.txt" 2>&1
t "a run whose first step blows the run cap exits 6" "$?" "6"
has "…and is RECORDED as capped, not merely printed" "auto-run CAPPED after build" \
  "$RC/compile/decisions.md"
has "…saying the candidate is not what went wrong" "it ran out of budget" \
  "$RC/compile/decisions.md"
t "…the pipeline stopped: the refuter was never called" \
  "$(grep -c refute "$FAKE_STEP_LOG" | tr -d ' ')" "0"
t "…and the candidate is still DRAFTED, for the next run to pick up" \
  "$(python3 -c "
rows=[l for l in open('$RC/compile/decisions.md') if 'slug=$SC_ ' in l]
print('status=DRAFTED' in rows[-1])")" "True"

# ── RAIL (e) · two strikes and the slug is PARKED ──
RD="$W/strikes"; cp -R "$R" "$RD"; rm -rf "$RD/compile"
( cd "$RD" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RD" >/dev/null 2>&1
python3 "$CP" draft --root "$RD" --all-ripe >/dev/null 2>&1
SD_="$(python3 -c "
import json;print(json.load(open('$RD/compile/candidates.json'))['candidates'][0]['slug'])")"
python3 "$CP" auto --root "$RD" --on --unattended --daily-cap 90000000 >/dev/null 2>&1
ARD(){ python3 "$CP" auto-run --root "$RD" --runner "$FAKE" --today "$TODAY" "$@"; }
FAKE_REFUTE=defect ARD --next > "$W/strike1.txt" 2>&1
t "a refuter DEFECT is a red gate (exit 3)" "$?" "3"
has "…counted as strike 1 of 2" "strike 1/2" "$W/strike1.txt"
has "…with the reason banked where the next run reads it" "auto-run RED refute (strike 1/2)" \
  "$RD/compile/decisions.md"
t "…and the status is unchanged, so it will be retried" \
  "$(python3 -c "
rows=[l for l in open('$RD/compile/decisions.md') if 'slug=$SD_ ' in l]
print('status=DRAFTED' in rows[-1])")" "True"
FAKE_REFUTE=defect ARD --next > "$W/strike2.txt" 2>&1
t "the second failure exits 3" "$?" "3"
has "…and PARKS the slug" "slug PARKED" "$W/strike2.txt"
has "…naming how the owner re-arms it" "decide --slug $SD_ --status DRAFTED" \
  "$RD/compile/decisions.md"
ARD --next > "$W/strike3.txt" 2>&1
t "a PARKED slug is never picked again (exit 0, nothing to do)" "$?" "0"
python3 "$CP" auto-run --root "$RD" --slug "$SD_" --runner "$FAKE" --today "$TODAY" \
  > "$W/strike4.txt" 2>&1
t "…and naming it explicitly still refuses to run it (0)" "$?" "0"
has "…saying it is parked, not that there is nothing to do" "is PARKED after" "$W/strike4.txt"
has "…and how to re-arm it" "decide --slug $SD_ --status DRAFTED" "$W/strike4.txt"
python3 "$CP" decide --root "$RD" --slug "$SD_" --status DRAFTED --note "owner re-armed" \
  >/dev/null 2>&1
ARD --next >/dev/null 2>&1
t "…and an owner re-arm makes it runnable again, with the strike count reset" "$?" "0"

# A CAP STOP IS NOT AN ARMING. It re-asserts DRAFTED like a red line does, so if it reset the
# counter a slug could alternate red · capped · red · capped and never reach two strikes —
# the retry loop this rail exists to stop, wearing a budget line as camouflage.
python3 "$CP" decide --root "$RD" --slug "$SD_" --status DRAFTED --note "armed" >/dev/null 2>&1
FAKE_REFUTE=defect ARD --next >/dev/null 2>&1
t "one red recorded" "$?" "3"
python3 "$CP" auto --root "$RD" --on --unattended --daily-cap 90000000 --run-cap 500 \
  >/dev/null 2>&1
FAKE_TOKENS=1000 ARD --next >/dev/null 2>&1
t "…then a cap stop (exit 6)" "$?" "6"
python3 "$CP" auto --root "$RD" --on --unattended --daily-cap 90000000 --run-cap 900000 \
  >/dev/null 2>&1
FAKE_REFUTE=defect ARD --next > "$W/strike5.txt" 2>&1
has "…and the NEXT red is still strike 2, not strike 1" "strike 2/2" "$W/strike5.txt"
has "…so the slug parks as it should" "slug PARKED" "$W/strike5.txt"

# ── fail-closed: SILENCE from the refuter is a defect, never a pass ──
RE_="$W/silent"; cp -R "$R" "$RE_"; rm -rf "$RE_/compile"
( cd "$RE_" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RE_" >/dev/null 2>&1
python3 "$CP" draft --root "$RE_" --all-ripe >/dev/null 2>&1
python3 "$CP" auto --root "$RE_" --on --unattended --daily-cap 90000000 >/dev/null 2>&1
FAKE_REFUTE=silent python3 "$CP" auto-run --root "$RE_" --runner "$FAKE" --today "$TODAY" \
  --next > "$W/ar-silent.txt" 2>&1
t "a refuter that returns no verdict is RED (exit 3)" "$?" "3"
has "…because silence must never promote a runtime" "silence reads as a defect" \
  "$W/ar-silent.txt"
hasnt "…and nothing was adopted" "status=ADOPTED" "$RE_/compile/decisions.md"

# ── the free gates: a red fixture and a stub benchmark both block adoption ──
RF="$W/redgates"; cp -R "$R" "$RF"; rm -rf "$RF/compile"
( cd "$RF" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RF" >/dev/null 2>&1
python3 "$CP" draft --root "$RF" --all-ripe >/dev/null 2>&1
SF="$(python3 -c "
import json;print(json.load(open('$RF/compile/candidates.json'))['candidates'][0]['slug'])")"
python3 "$CP" auto --root "$RF" --on --unattended --daily-cap 90000000 >/dev/null 2>&1
: > "$FAKE_STEP_LOG"
FAKE_FIXTURE_RC=1 python3 "$CP" auto-run --root "$RF" --runner "$FAKE" --today "$TODAY" \
  --next > "$W/ar-fixred.txt" 2>&1
t "a failing fixture is a red gate (exit 3)" "$?" "3"
t "…caught BEFORE the refuter was paid for" \
  "$(grep -c refute "$FAKE_STEP_LOG" | tr -d ' ')" "0"
python3 "$CP" decide --root "$RF" --slug "$SF" --status DRAFTED --note "re-armed" >/dev/null 2>&1
FAKE_BENCH_RC=4 python3 "$CP" auto-run --root "$RF" --runner "$FAKE" --today "$TODAY" \
  --next > "$W/ar-benchred.txt" 2>&1
t "a benchmark still at its stub blocks adoption (exit 3)" "$?" "3"
has "…and says the stub is what it is" "still the scaffold stub" "$W/ar-benchred.txt"
hasnt "…nothing was adopted on a green build alone" "status=ADOPTED" "$RF/compile/decisions.md"

echo "── Q · lessons are candidates too: a rule nobody encoded (docket F)"
# The compiled form of a lesson is a HOOK ARM or an EVAL CHECK, never another paragraph.
# Three records saying the same thing is the estate asking for a gate — so the scan reads
# the archivist's `learning` and `open` records alongside the ledgers.
RL="$W/lessons"; mkdir -p "$RL/archive"
cat > "$RL/COORD.md" <<'EOF'
# COORD.md
## LEDGER
- [2026-03-01 09:00Z] [main] one ordinary line so the estate is not empty -> landed | evidence: x
EOF
cat > "$RL/archive/findings.jsonl" <<'EOF'
{"id":"L-1","ts":"2026-03-01T10:00:00Z","kind":"learning","tag":"LEARNED","statement":"A fixture that mocks the thing it tests passes by agreeing with itself.","status":"live"}
{"id":"L-2","ts":"2026-04-02T10:00:00Z","kind":"learning","tag":"RULED","statement":"A fixture mocking the thing tested passes by agreeing with itself","status":"live"}
{"id":"O-1","ts":"2026-05-03T10:00:00Z","kind":"open","recheck":"2026-06-01","owner":"seat","statement":"A fixture that mocked the things it tests passes by agreeing with itself.","status":"live"}
{"id":"L-4","ts":"2026-06-04T10:00:00Z","kind":"learning","tag":"LEARNED","statement":"A superseded lesson that must never reach a candidate at all.","status":"superseded"}
{"id":"L-5","ts":"2026-06-05T10:00:00Z","kind":"learning","tag":"LEARNED","statement":"Never resolve an ambiguous ask from what the estate already contains.","status":"live"}
{"id":"L-6","ts":"2026-06-06T10:00:00Z","kind":"finding","statement":"A finding is not a lesson and must not be grouped as one, however often it repeats.","status":"live"}
{"id":"L-7","ts":"2026-06-07T10:00:00Z","kind":"finding","statement":"A finding is not a lesson and must not be grouped as one, however often it repeats.","status":"live"}
{"id":"L-8","ts":"2026-06-08T10:00:00Z","kind":"finding","statement":"A finding is not a lesson and must not be grouped as one, however often it repeats.","status":"live"}
not json at all
{"id":"L-9","ts":"2026-06-09T10:00:00Z","kind":"learning","tag":"LEARNED","statement":"it broke","status":"live"}
{"id":"L-10","ts":"2026-06-10T10:00:00Z","kind":"learning","tag":"LEARNED","statement":"it broke","status":"live"}
{"id":"L-11","ts":"2026-06-11T10:00:00Z","kind":"learning","tag":"LEARNED","statement":"it broke","status":"live"}
EOF
python3 "$CP" scan --root "$RL" > "$W/rule.out" 2>"$W/rule.err"
t "a scan over a store with lessons exits 0" "$?" "0"
JL(){ python3 -c "
import json,sys
d=json.load(open('$RL/compile/candidates.json')); c=d['candidates']
r=[x for x in c if x['kind']=='rule']
print(eval(sys.argv[1], {'d':d,'c':c,'r':r,'top':r[0] if r else {}}))
" "$1"; }
t "the recurring lesson became exactly one rule candidate" "$(JL "len(r)")" "1"
t "…counting all three recurrences, across BOTH lesson kinds" "$(JL "top['occurrences']")" "3"
t "…and it is ripe" "$(JL "top['ripe']")" "True"
t "…and it cites the record ids it was built from" \
  "$(JL "sorted(top['records'])")" "['L-1', 'L-2', 'O-1']"
t "…which include an `open` record, not only learnings" "$(JL "'O-1' in top['records']")" "True"
has "…and the ids are readable in the machine-written report" "records: \`L-1, L-2, O-1\`" \
  "$RL/compile/candidates.md"
has "…where the doc says what kind=rule means" "hook arm or an eval check" \
  "$RL/compile/candidates.md"
t "a SUPERSEDED lesson never reaches a candidate" \
  "$(JL "not any('superseded' in e['text'] for x in c for e in x['evidence'])")" "True"
t "a kind the loop does not read (finding) is not grouped, however often it repeats" \
  "$(JL "not any('however often it repeats' in e['text'] for x in r for e in x['evidence'])")" "True"
t "a statement too thin to have said anything is not a rule" \
  "$(JL "not any('broke' in ' '.join(x['core']) for x in r)")" "True"
has "the findings store is named as a source, present or not" "| archive/findings.jsonl | yes |" \
  "$RL/compile/candidates.md"
# 7 = the store's learning|open records minus the superseded one; the three findings and
# the unparsable line are never counted, and the unparsable one is never fatal.
t "…with the count it actually read (malformed lines skipped, not fatal)" \
  "$(JL "[s['items'] for s in d['sources'] if s['name']=='archive/findings.jsonl'][0]")" "7"
# an estate with no store at all is a state, not a failure
R10="$W/nostore"; mkdir -p "$R10"; cp "$R/COORD.md" "$R10/"
python3 "$CP" scan --root "$R10" >/dev/null 2>&1
t "a scan with no findings store exits 0" "$?" "0"
has "…and names the absent source rather than omitting it" "| archive/findings.jsonl | NO |" \
  "$R10/compile/candidates.md"
# a rule can be ruled on like any other candidate
RSLUG="$(JL "top['slug']")"
python3 "$CP" decide --root "$RL" --slug "$RSLUG" --status DECLINED \
  --note "already enforced by the refuter step" >/dev/null 2>&1
python3 "$CP" scan --root "$RL" >/dev/null 2>&1
t "a ruling on a rule candidate carries over like any other" "$(JL "top['status']")" "DECLINED"

echo "── R · a quiet stop backs off, is diagnosable, and says so in one line (live finding)"
# LIVE, 2026-09-05: the marker was armed, the pulse ran this pipeline for real, and the
# builder failed on three consecutive pulses (06:12Z, 06:18Z x2). Each line read "strike 0
# of 2" — a stop is deliberately not a strike — so the SAME slug was retried every pulse
# with no back-off. Nothing was spent only because the CLI failed BEFORE reporting usage.
# The cause was invisible: "runner exited 1", no stderr. Both halves are armed here.
RG="$W/backoff"; cp -R "$R" "$RG"; rm -rf "$RG/compile"
( cd "$RG" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RG" >/dev/null 2>&1
python3 "$CP" draft --root "$RG" --all-ripe >/dev/null 2>&1
SG="$(python3 -c "
import json;print(json.load(open('$RG/compile/candidates.json'))['candidates'][0]['slug'])")"
python3 "$CP" auto --root "$RG" --on --unattended --daily-cap 90000000 --stop-cooldown 6 \
  > "$W/auto-cool.txt" 2>&1
t "auto --on --unattended --stop-cooldown exits 0" "$?" "0"
has "…and the cooldown is printed with the other rails" "stop cooldown: 6h" "$W/auto-cool.txt"
has "…including what a run of stops costs" "3 consecutive stops count as one strike" \
  "$W/auto-cool.txt"
t "…and it is stored on the marker beside the budget" "$(python3 -c '
import json,sys; print(json.load(open(sys.argv[1])).get("stop_cooldown_hours"))
' "$(mk "$RG")")" "6"
ARG(){ python3 "$CP" auto-run --root "$RG" --runner "$FAKE" --today "$TODAY" "$@"; }
STAT="$RG/pulse/auto-run.status"
DECG="$RG/compile/decisions.md"

# ── the shape that would have walked straight past a code-only check ──
: > "$FAKE_STEP_LOG"
FAKE_BUILD=authexp ARG --next > "$W/bo-authexp.txt" 2>&1
t "is_error:true with subtype success and EXIT 0 is still a stop (exit 0)" "$?" "0"
has "…recognised as AUTH, not as a finished build" "AUTH:" "$W/bo-authexp.txt"
has "…quoting the CLI's own words" "OAuth session expired" "$W/bo-authexp.txt"
t "…and the refuter was NEVER called against a dead session" \
  "$(grep -c refute "$FAKE_STEP_LOG" | tr -d ' ')" "0"
has "…the receipt carries the reason too, not just a token count" \
  "STOPPED: AUTH: Failed to authenticate" "$RG/spend/ledger.md"
t "…and the status line says BLOCKED, which is what a banner branches on" \
  "$(sed -n 's/^\[[^]]*\] \([A-Z]*\).*/\1/p' "$STAT")" "BLOCKED"
has "…naming the cause on that one line" "BLOCKED auth: AUTH: Failed to authenticate" "$STAT"
t "the status file is ONE line, overwritten — not a log to read backwards" \
  "$(wc -l < "$STAT" | tr -d ' ')" "1"

# ── THE BACK-OFF: the same slug is not dialled again on the next pulse ──
: > "$FAKE_STEP_LOG"
ARG --next > "$W/bo-cool.txt" 2>&1
t "the very next run exits 0 without touching the slug" "$?" "0"
t "…and made NO runner call at all" "$(grep -c . "$FAKE_STEP_LOG" | tr -d ' ')" "0"
has "…saying it is cooling down, with the time left" "cooling down" "$W/bo-cool.txt"
has "…and the cooldown length it is honouring" "the cooldown is 6h" "$W/bo-cool.txt"
has "…the status line says COOLDOWN" "COOLDOWN" "$STAT"
t "…and no receipt was written for a call that never happened" \
  "$(grep -c 'lane=daemon' "$RG/spend/ledger.md" | tr -d ' ')" "1"
# naming the slug explicitly does not get past the cooldown either
python3 "$CP" auto-run --root "$RG" --slug "$SG" --runner "$FAKE" --today "$TODAY" \
  > "$W/bo-cool2.txt" 2>&1
t "…and --slug cannot talk it round (0)" "$?" "0"
has "…same reason, named" "is cooling down" "$W/bo-cool2.txt"

# ── once the cooldown has passed, it runs again (the stamp is what decides) ──
python3 - "$DECG" <<'AGEPY'
import re, sys
# age the stop stamp by a day: the cooldown is computed from the RECORD, so this is the
# honest way to test expiry — no clock is mocked and no code path is special-cased.
p = sys.argv[1]
lines = open(p, encoding="utf-8").read().splitlines(True)
for i, l in enumerate(lines):
    if "auto-run STOPPED" in l:
        lines[i] = re.sub(r"^- \[\d{4}-\d{2}-\d{2} ", "- [2020-01-01 ", l)
open(p, "w", encoding="utf-8").write("".join(lines))
AGEPY
: > "$FAKE_STEP_LOG"
FAKE_BUILD=authexp ARG --next > "$W/bo-expired.txt" 2>&1
t "with the cooldown expired the slug IS retried (0)" "$?" "0"
t "…and the runner was called once" "$(grep -c . "$FAKE_STEP_LOG" | tr -d ' ')" "1"
has "…and this stop is counted as the SECOND in the run" "quiet stop 2 of 3" "$W/bo-expired.txt"

# ── three in a row is worth one strike: a runner that never works parks the slug ──
python3 - "$DECG" <<'AGEPY'
import re, sys
p = sys.argv[1]
lines = open(p, encoding="utf-8").read().splitlines(True)
for i, l in enumerate(lines):
    if "auto-run STOPPED" in l:
        lines[i] = re.sub(r"^- \[\d{4}-\d{2}-\d{2} ", "- [2020-01-01 ", l)
open(p, "w", encoding="utf-8").write("".join(lines))
AGEPY
FAKE_BUILD=authexp ARG --next > "$W/bo-strike.txt" 2>&1
t "the third consecutive quiet stop still exits 0" "$?" "0"
has "…but is counted as a strike" "counted as strike 1/2" "$W/bo-strike.txt"
has "…naming how many stops it took" "3 in a row" "$W/bo-strike.txt"
has "…and the strike is banked where the next run reads it" \
  "from 3 consecutive quiet stops" "$DECG"

# ── an explicit re-arm clears the cooldown AND the run of stops ──
python3 "$CP" decide --root "$RG" --slug "$SG" --status DRAFTED --note "owner re-armed" \
  >/dev/null 2>&1
: > "$FAKE_STEP_LOG"
FAKE_BUILD=crash ARG --next > "$W/bo-crash.txt" 2>&1
t "a re-armed slug runs immediately, cooldown cleared (0)" "$?" "0"
t "…the runner was called" "$(grep -c . "$FAKE_STEP_LOG" | tr -d ' ')" "1"
has "…and the count started again" "quiet stop 1 of 3" "$W/bo-crash.txt"
# DIAGNOSABILITY: the live report was three identical "runner exited 1" lines with no cause
has "a crashing runner's STDERR is in the log line, not just its code" \
  "could not open the contract" "$W/bo-crash.txt"
has "…and in the receipt, where the spend is explained" \
  "could not open the contract" "$RG/spend/ledger.md"
has "…and the pulse log keeps it for whoever reads it next" \
  "could not open the contract" "$RG/pulse/auto-run.log"

# ── a non-auth is_error is a stop too, and is NOT called an auth failure ──
python3 "$CP" decide --root "$RG" --slug "$SG" --status DRAFTED --note "re-armed" >/dev/null 2>&1
FAKE_BUILD=iserror ARG --next > "$W/bo-iserr.txt" 2>&1
t "is_error:true with a non-auth reason is a stop (0)" "$?" "0"
has "…named as what it is" "the CLI reported is_error" "$W/bo-iserr.txt"
has "…quoting the reason" "the model refused the prompt" "$W/bo-iserr.txt"
hasnt "…and NOT mislabelled as auth" "BLOCKED auth" "$STAT"
has "…so the status says COOLDOWN, not BLOCKED" "COOLDOWN" "$STAT"
t "…and its tokens were still receipted (the call happened)" \
  "$(grep -c 'lane=daemon model=opus tokens=50 grade=observed' "$RG/spend/ledger.md" | tr -d ' ')" "1"

# ── the other two words in the status grammar ──
RH="$W/statusidle"; cp -R "$R" "$RH"; rm -rf "$RH/compile"
( cd "$RH" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RH" >/dev/null 2>&1
python3 "$CP" auto --root "$RH" --on --unattended --daily-cap 90000000 >/dev/null 2>&1
python3 "$CP" auto-run --root "$RH" --runner "$FAKE" --today "$TODAY" --next >/dev/null 2>&1
t "an estate with nothing drafted exits 0" "$?" "0"
has "…and its status line is IDLE" "IDLE nothing drafted" "$RH/pulse/auto-run.status"
python3 "$CP" draft --root "$RH" --all-ripe >/dev/null 2>&1
python3 "$CP" auto-run --root "$RH" --runner "$FAKE" --today "$TODAY" --next >/dev/null 2>&1
t "…and a healthy adoption exits 0" "$?" "0"
has "…with an OK status, which a banner stays quiet about" "OK " "$RH/pulse/auto-run.status"

# ── BUSY is the lock working, and the log says so in those words ──
python3 - "$RH/compile/.auto-run.lock" "$W/held2" <<'LOCKPY' &
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX)
open(sys.argv[2], "w").write("held")
time.sleep(6)
LOCKPY
HOLDER2=$!
for _ in $(seq 1 60); do [ -f "$W/held2" ] && break; sleep 0.1; done
cp "$RH/pulse/auto-run.status" "$W/status-before-busy"
python3 "$CP" auto-run --root "$RH" --runner "$FAKE" --today "$TODAY" --next \
  > "$W/bo-busy.txt" 2>&1
t "two pulses racing: the second exits 0" "$?" "0"
has "…and the log says this is the lock working, not a fault" "THIS IS THE LOCK WORKING" \
  "$W/bo-busy.txt"
t "…and a BUSY run does not overwrite the status the OTHER run owns" \
  "$(cmp -s "$RH/pulse/auto-run.status" "$W/status-before-busy" && echo identical || echo mutated)" \
  "identical"
kill "$HOLDER2" 2>/dev/null; wait "$HOLDER2" 2>/dev/null
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT ANTHROPIC_API_KEY

echo "── S · the credential the daemon runs on: a file, a mode, and never in a log"
# `claude setup-token` prints a long-lived token and does NOT log the CLI in (live probe,
# 2026-09-05: `auth status` still said loggedIn false afterwards). And the pulse daemon is
# spawned by hooks INSIDE the app, so a shell export never reaches it — there is no shell
# in the chain. A file under the owner-private root is the only place the two can meet.
RK="$W/creds"; cp -R "$R" "$RK"; rm -rf "$RK/compile"
( cd "$RK" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RK" >/dev/null 2>&1
python3 "$CP" draft --root "$RK" --all-ripe >/dev/null 2>&1
SK="$(python3 -c "
import json;print(json.load(open('$RK/compile/candidates.json'))['candidates'][0]['slug'])")"
python3 "$CP" auto --root "$RK" --on --unattended --daily-cap 90000000 >/dev/null 2>&1
ARK(){ python3 "$CP" auto-run --root "$RK" --runner "$FAKE" --today "$TODAY" "$@"; }
STATK="$RK/pulse/auto-run.status"
ARMK(){ python3 "$CP" decide --root "$RK" --slug "$SK" --status DRAFTED \
          --note "re-armed" >/dev/null 2>&1; }

# ── 1 · file present at 0600 → the child gets the variable ──
mkcred 600 700
unset CLAUDE_CODE_OAUTH_TOKEN
: > "$FAKE_ENV_LOG"
ARK --next > "$W/cr-file.txt" 2>&1
t "with a 0600 credential file the pipeline runs (0)" "$?" "0"
t "…and the child DID receive the variable" \
  "$(grep -c '^OAUTH_PRESENT=yes$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"
has "…and the log names only the SOURCE, never the value" "credential: file" "$W/cr-file.txt"
t "…no part of the token appears in the pulse log" \
  "$(grep -c 'fixture-token' "$RK/pulse/auto-run.log" | tr -d ' ')" "0"
t "…nor in the spend ledger" \
  "$(grep -c 'fixture-token' "$RK/spend/ledger.md" | tr -d ' ')" "0"
t "…nor in the status line" "$(grep -c 'fixture-token' "$STATK" | tr -d ' ')" "0"
t "…nor in decisions.md" "$(grep -c 'fixture-token' "$RK/compile/decisions.md" | tr -d ' ')" "0"
t "…nor anywhere the run wrote at all" \
  "$(grep -rl 'fixture-token-never-a-real-one' "$RK" 2>/dev/null | wc -l | tr -d ' ')" "0"

# ── 2 · a group/world-readable file is REFUSED, and not passed ──
ARMK; mkcred 644 700
: > "$FAKE_ENV_LOG"
ARK --next > "$W/cr-644.txt" 2>&1
t "a 0644 credential file blocks the run (0, nothing spent)" "$?" "0"
t "…and the runner was never called" "$(grep -c . "$FAKE_ENV_LOG" | tr -d ' ')" "0"
has "…naming the MODE as the problem" "is mode 0644" "$W/cr-644.txt"
has "…and saying how to fix it" "chmod 600" "$W/cr-644.txt"
has "…with a BLOCKED status a banner can branch on" "BLOCKED auth: credential file unusable" \
  "$STATK"
t "…and no receipt was written for a call that never happened" \
  "$(grep -c 'lane=daemon' "$RK/spend/ledger.md" | tr -d ' ')" "2"
# the directory is checked too: a 0600 file in a 0755 dir is still reachable by a rename
ARMK; mkcred 600 755
ARK --next > "$W/cr-dir.txt" 2>&1
t "an owner-only FILE in a group-readable DIRECTORY is refused too (0)" "$?" "0"
has "…naming the directory this time" "the directory must be owner-only" "$W/cr-dir.txt"
has "…and how to fix that" "chmod 700" "$W/cr-dir.txt"

# ── 3 · OWNER RULING: the credential step is OPTIONAL. env → file → THE CLI'S OWN LOGIN.
# A user whose terminal is already logged in must never meet a credential step, so with
# neither env nor file we CALL THE RUNNER ANYWAY and let the CLI use its own login.
# Absence of a file is not evidence of absence of a login.
ARMK; rm -f "$CRED"
: > "$FAKE_ENV_LOG"
ARK --next > "$W/cr-cli.txt" 2>&1
t "with no env and no file the build still PROCEEDS (0)" "$?" "0"
has "…reporting the source as the CLI's own login" "credential: cli" "$W/cr-cli.txt"
t "…the runner WAS called" "$(grep -c '^OAUTH_PRESENT=no$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"
has "…and it ran all the way to adoption" "ADOPTED" "$W/cr-cli.txt"
hasnt "…with no credential step invented for a user who did not need one" \
  "BLOCKED" "$W/cr-cli.txt"

# …and ONLY an auth-shaped answer coming BACK from that call is a block.
ARMK
: > "$FAKE_ENV_LOG"
FAKE_BUILD=authexp ARK --next > "$W/cr-noauth.txt" 2>&1
t "an auth-shaped failure from the CLI's own login blocks (0)" "$?" "0"
has "…the status says BLOCKED auth" "BLOCKED auth" "$STATK"
has "…and names ONE command to fix it" "credential --setup" "$STATK"
has "…the log names it too" "credential --setup" "$W/cr-noauth.txt"
has "…saying which source was being relied on" "credential: cli" "$W/cr-noauth.txt"
t "…and the slug took NO strike for an estate-wide problem" \
  "$(python3 -c "
rows=[l for l in open('$RK/compile/decisions.md') if 'slug=$SK ' in l]
print('auto-run RED' not in rows[-1])")" "True"

# ── 4 · the environment wins, and the file is not read ──
# Proven WITHOUT comparing values: the file is left at a mode that would be REFUSED, so a
# clean run can only mean the file was never consulted.
ARMK; mkcred 644 700
export CLAUDE_CODE_OAUTH_TOKEN="from-the-environment-not-real"
: > "$FAKE_ENV_LOG"
ARK --next > "$W/cr-env.txt" 2>&1
t "an env credential runs even with an unusable FILE beside it (0)" "$?" "0"
has "…and reports the source as env" "credential: env" "$W/cr-env.txt"
hasnt "…never reading the file, so its mode is never complained about" "is mode 0644" \
  "$W/cr-env.txt"
t "…and the child still received the variable" \
  "$(grep -c '^OAUTH_PRESENT=yes$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"
t "…and that value never reached a log either" \
  "$(grep -rl 'from-the-environment-not-real' "$RK" 2>/dev/null | wc -l | tr -d ' ')" "0"
unset CLAUDE_CODE_OAUTH_TOKEN

# ── 5 · an empty file is not a credential ──
ARMK; mkdir -p "$CREDDIR"; chmod 700 "$CREDDIR"; : > "$CRED"; chmod 600 "$CRED"
ARK --next > "$W/cr-empty.txt" 2>&1
t "an empty credential file is refused (0)" "$?" "0"
has "…saying so plainly" "is empty" "$W/cr-empty.txt"

# ── 6 · a trailing newline is stripped, and only the first line is used ──
ARMK; printf 'fixture-token-never-a-real-one\n' > "$CRED"; chmod 600 "$CRED"
: > "$FAKE_ENV_LOG"
ARK --next >/dev/null 2>&1
t "a one-line file with a trailing newline works" "$?" "0"
t "…and the child got a variable with no newline in it" \
  "$(grep -c '^OAUTH_PRESENT=yes$' "$FAKE_ENV_LOG" | tr -d ' ')" "2"

# ── 7 · `auto` tells the owner where to put it, before they need it ──
rm -f "$CRED"
python3 "$CP" auto --root "$RK" > "$W/cr-auto.txt" 2>&1
t "auto still exits 0 with no credential" "$?" "0"
has "…saying the CLI's own login is used, so the step is optional" \
  "will use the CLI's OWN login" "$W/cr-auto.txt"
has "…and naming ONE command for when it is not" "credential --setup" "$W/cr-auto.txt"
has "…names the exact path" "credentials/claude-oauth-token" "$W/cr-auto.txt"
has "…the mode it requires" "mode 0600" "$W/cr-auto.txt"
mkcred 600 700
python3 "$CP" auto --root "$RK" > "$W/cr-auto2.txt" 2>&1
has "…and reports it present once it is there" "credential: file (present" "$W/cr-auto2.txt"
has "…promising the value is never printed" "never printed, logged or receipted" "$W/cr-auto2.txt"
t "…without printing it" "$(grep -c 'fixture-token' "$W/cr-auto2.txt" | tr -d ' ')" "0"
python3 "$CP" auto-run --root "$RK" --runner "$FAKE" --dry-run > "$W/cr-dry.txt" 2>&1
has "the dry-run plan names the credential source too" "credential    : file" "$W/cr-dry.txt"
rm -f "$CRED"
python3 "$CP" auto-run --root "$RK" --runner "$FAKE" --dry-run > "$W/cr-dry2.txt" 2>&1
has "…and with none stored it names the CLI login and the one command" \
  "credential --setup" "$W/cr-dry2.txt"
mkcred 600 700
has "…and that the session's own vars are scrubbed" "CLAUDECODE/CLAUDE_CODE_* scrubbed" \
  "$W/cr-dry.txt"

echo "── T · credential --setup: the one command, and the wrap that broke the owner"
# LIVE, 2026-09-05: the owner ran `claude setup-token`, the TERMINAL WRAPPED the printed
# token, the clipboard carried the wrap as a real line break, and the CLI rejected it —
# "a line break at character 80 (110 characters on 2 lines)". Every step there is normal
# behaviour by a terminal, a clipboard and a CLI. What was missing was something that took
# the paste and made it into a credential. A FAKE `claude` on PATH wraps its token exactly
# the same way, so this whole section runs without a real token or a real browser.
BIN="$W/fakebin"; mkdir -p "$BIN"
cat > "$BIN/claude" <<'CLAUDEEOF'
#!/bin/bash
# fake `claude`. Contacts nothing. Wraps its token across two lines, as the real one did.
if [ "$1" = "setup-token" ]; then
  [ "${FAKE_SETUP:-ok}" = "fail" ] && { echo "could not reach the browser" >&2; exit 3; }
  echo "Opening browser to authenticate..."
  echo ""
  if [ "${FAKE_SETUP:-ok}" = "none" ]; then
    echo "Authentication complete. Nothing further to display."
  elif [ "${FAKE_SETUP:-ok}" = "two" ]; then
    echo "sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    echo ""
    echo "sk-ant-oat01-CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
  else
    # the wrap: ONE token, printed across two lines by an 80-column terminal
    echo "sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    echo "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
  fi
  echo ""
  echo "This token will not be shown again."
  exit 0
fi
cat >/dev/null
if [ "${FAKE_CLI:-ok}" = "bad" ]; then
  printf '{"type":"result","subtype":"success","is_error":true,"result":"Failed to authenticate: OAuth token is invalid or expired"}'
  exit 0
fi
printf '{"type":"result","subtype":"success","is_error":false,"result":"ok","usage":{"input_tokens":8,"output_tokens":1}}'
CLAUDEEOF
chmod +x "$BIN/claude"
OLDPATH="$PATH"; export PATH="$BIN:$PATH"
CH="$W/credhome"; OLDNR="$NOTREST_HOME"
CREDC(){ NOTREST_HOME="$CH" python3 "$CP" credential "$@"; }
TOKF="$CH/credentials/claude-oauth-token"
SECRET='sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'

# ── the one command, end to end ──
rm -rf "$CH"
CREDC --setup > "$W/t-setup.txt" 2>&1
t "credential --setup exits 0" "$?" "0"
has "…telling the user the browser step is theirs" "complete the browser step" "$W/t-setup.txt"
has "…and that the token is not going to be echoed at them" "never printed here" "$W/t-setup.txt"
has "…printing exactly the verified verdict" "credential: ok" "$W/t-setup.txt"
t "…the file exists" "$([ -f "$TOKF" ] && echo yes)" "yes"
t "…at mode 0600" "$(stat -f '%Lp' "$TOKF")" "600"
t "…in a directory at mode 0700" "$(stat -f '%Lp' "$(dirname "$TOKF")")" "700"
t "THE WRAP IS REJOINED: the file holds ONE line" "$(wc -l < "$TOKF" | tr -d ' ')" "1"
t "…of the full 110-character token, not the first 80" \
  "$(awk '{print length($0)}' "$TOKF")" "110"
t "…which is byte-for-byte the token the CLI printed across two lines" \
  "$(tr -d '\n' < "$TOKF")" "$SECRET"
t "…and the report says how many lines it recovered it from" \
  "$(grep -c 'recovered from' "$W/t-setup.txt" | tr -d ' ')" "1"
# ⛔ THE VALUE IS NEVER PRINTED. Not on stdout, not on stderr, not in the report.
t "no part of the token reached the command's own output" \
  "$(grep -c 'AAAAAAAA' "$W/t-setup.txt" | tr -d ' ')" "0"
t "…and the report says only its LENGTH" \
  "$(grep -c '110 characters' "$W/t-setup.txt" | tr -d ' ')" "1"

# ── --setup verifies BEFORE writing: a bad token never becomes the file a 3am run needs ──
rm -rf "$CH"
FAKE_CLI=bad CREDC --setup > "$W/t-bad.txt" 2>&1
t "a token the probe rejects exits 5" "$?" "5"
has "…printing exactly the invalid verdict with the CLI's own words" \
  "credential: invalid — Failed to authenticate: OAuth token is invalid" "$W/t-bad.txt"
t "…and NOTHING was written" "$([ -f "$TOKF" ] && echo wrote || echo none)" "none"
t "…not even the token's characters in the error" \
  "$(grep -c 'AAAAAAAA' "$W/t-bad.txt" | tr -d ' ')" "0"

# ── the two ways the output can be unreadable, both refused rather than guessed ──
rm -rf "$CH"
FAKE_SETUP=none CREDC --setup > "$W/t-none.txt" 2>&1
t "no token in the output is refused (2)" "$?" "2"
has "…saying so rather than writing something" "no token in the output" "$W/t-none.txt"
t "…and nothing was written" "$([ -f "$TOKF" ] && echo wrote || echo none)" "none"
rm -rf "$CH"
FAKE_SETUP=two CREDC --setup > "$W/t-two.txt" 2>&1
t "TWO tokens in the output is refused, never guessed between (2)" "$?" "2"
has "…naming how many it found" "2 separate tokens" "$W/t-two.txt"
t "…and nothing was written" "$([ -f "$TOKF" ] && echo wrote || echo none)" "none"
rm -rf "$CH"
FAKE_SETUP=fail CREDC --setup > "$W/t-fail.txt" 2>&1
t "a setup-token that itself fails exits 5" "$?" "5"
has "…naming its exit code" "exited 3" "$W/t-fail.txt"

# ── --set stays as the paste fallback, and strips the same wrap ──
rm -rf "$CH"
printf 'sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n' \
  | CREDC --set --verify > "$W/t-set.txt" 2>&1
t "a WRAPPED paste through --set is accepted (0)" "$?" "0"
has "…and verified" "credential: ok" "$W/t-set.txt"
t "…rejoined to the same 110 characters" "$(awk '{print length($0)}' "$TOKF")" "110"
has "…and the report says it arrived on 2 lines" "from 2 pasted line(s)" "$W/t-set.txt"
printf '   \n\t\n' | CREDC --set > "$W/t-empty.txt" 2>&1
t "a whitespace-only paste is refused (2)" "$?" "2"
has "…saying it was empty once whitespace went" "empty once whitespace was removed" \
  "$W/t-empty.txt"
printf 'Token: sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n' | CREDC --set > "$W/t-label.txt" 2>&1
t "a paste that dragged a label along is refused (2)" "$?" "2"
has "…naming the characters no credential contains" "no credential contains" "$W/t-label.txt"
printf 'sk-ant-oat01-AAAA sk-ant-oat01-BBBB\n' | CREDC --set > "$W/t-multi.txt" 2>&1
t "two tokens pasted together are refused (2)" "$?" "2"
has "…as more than one credential" "more than one credential" "$W/t-multi.txt"
printf 'short\n' | CREDC --set > "$W/t-short.txt" 2>&1
t "a truncated paste is refused (2)" "$?" "2"
has "…as under the floor" "under the 16-character floor" "$W/t-short.txt"

# ── (1) THE READER strips all whitespace too: a file someone edited by hand still works ──
rm -rf "$CH"; mkdir -p "$CH/credentials"; chmod 700 "$CH/credentials"
printf 'sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n' \
  > "$TOKF"; chmod 600 "$TOKF"
NOTREST_HOME="$CH" python3 - "$CP" <<'RDPY'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("c", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tok, src, problem = m.read_credential()
# PRESENCE AND SHAPE ONLY — this arm must not print a credential either.
print("SRC=%s PROBLEM=%s LEN=%d WS=%s"
      % (src, problem or "-", len(tok or ""), any(c.isspace() for c in (tok or ""))))
RDPY
NOTREST_HOME="$CH" python3 - "$CP" > "$W/t-read.txt" 2>&1 <<'RDPY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("c", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tok, src, problem = m.read_credential()
print("SRC=%s LEN=%d WS=%s" % (src, len(tok or ""), any(c.isspace() for c in (tok or ""))))
RDPY
has "a TWO-LINE credential file is read as one token" "SRC=file" "$W/t-read.txt"
has "…with the wrap rejoined to the full length" "LEN=110" "$W/t-read.txt"
has "…and not one whitespace character left in it" "WS=False" "$W/t-read.txt"

# ── --status reports presence and modes, never the value ──
CREDC --status > "$W/t-stat.txt" 2>&1
t "credential --status with a usable file exits 0" "$?" "0"
has "…reporting the modes" "file mode 0600, directory mode 0700" "$W/t-stat.txt"
t "…and never the value" "$(grep -c 'AAAAAAAA' "$W/t-stat.txt" | tr -d ' ')" "0"
chmod 644 "$TOKF"
CREDC --status > "$W/t-stat2.txt" 2>&1
t "…and flags an unusable mode (5)" "$?" "5"
has "…naming it" "UNUSABLE" "$W/t-stat2.txt"
rm -rf "$CH"
CREDC --status > "$W/t-stat3.txt" 2>&1
t "…absent exits 5" "$?" "5"
has "…but says storing one is OPTIONAL" "OPTIONAL" "$W/t-stat3.txt"
has "…and names the one command" "credential --setup" "$W/t-stat3.txt"
export PATH="$OLDPATH"; export NOTREST_HOME="$OLDNR"

echo "── U · the refuter round: both ouroboros doors, and the cap's unknown-usage hole"
# B4 (BLOCKER) and D1, 2026-09-05. Both are the same shape of mistake: a rail that looked
# closed because the ONE path it was written for was closed.

# ── B4 · door two: the OPERATOR pastes what the compiler printed ──────────────
# `decide --status ADOPTED` prints a COORD line for a human to paste and `auto-run` prints
# another. The refuter pasted 12 adopt lines and 12 pulse lines; `scan` returned THREE ripe
# candidates, `slug-adopt-benchmark` at 12x among them — and with the marker merely opted,
# estate-pulse runs `draft --all-ripe` on every pulse. The compiler's own paperwork would
# have become a drafted runtime overnight.
RM="$W/ouroboros"; mkdir -p "$RM"
: > "$RM/COORD.md"
echo "# COORD.md" >> "$RM/COORD.md"
i=0
while [ "$i" -lt 12 ]; do
  printf -- '- [2026-09-05 %02d:00Z] [compile] adopt slug-%d -> ADOPTED | evidence: fixture.sh exit 0, benchmark.sh exit 0, REFUTER: CLEAN\n' \
    "$i" "$i" >> "$RM/COORD.md"
  printf -- '- [2026-09-05 %02d:00Z] [pulse] compile auto-run start slug-%d strike 0 of 2 runner=claude -> logged | pulse/auto-run.log\n' \
    "$i" "$i" >> "$RM/COORD.md"
  i=$((i+1))
done
t "the refuter's corpus is 24 machinery lines" \
  "$(grep -c '^- \[' "$RM/COORD.md" | tr -d ' ')" "24"
python3 "$CP" scan --root "$RM" > "$W/ouro.txt" 2>&1
t "scanning 24 machinery lines exits 0" "$?" "0"
t "…and yields ZERO candidates — the harness talking about itself is not work" \
  "$(python3 -c "
import json;d=json.load(open('$RM/compile/candidates.json'));print(len(d['candidates']))")" "0"
t "…because the lines never reached the reader at all" \
  "$(python3 -c "
import json;d=json.load(open('$RM/compile/candidates.json'))
print([s['items'] for s in d['sources'] if s['name']=='COORD.md'][0])")" "0"
# and a HUMAN line in the same file is still read: this drops machinery, not history
printf -- '- [2026-09-05 13:00Z] [main] cut the release for the parser -> v9.9.9 shipped, changelog and manifest bumped | evidence: commit ffee11\n' \
  >> "$RM/COORD.md"
python3 "$CP" scan --root "$RM" >/dev/null 2>&1
t "…while a human's own ledger line is still read" \
  "$(python3 -c "
import json;d=json.load(open('$RM/compile/candidates.json'))
print([s['items'] for s in d['sources'] if s['name']=='COORD.md'][0])")" "1"
for TAG in compile hook daemon pulse; do
  RT="$W/mach-$TAG"; mkdir -p "$RT"
  { echo "# COORD.md"
    n=0; while [ "$n" -lt 4 ]; do
      printf -- '- [2026-09-05 0%d:00Z] [%s] regenerate the customer invoice pdf for acme -> pdf mailed | evidence: x\n' \
        "$n" "$TAG" >> /dev/stdout
      n=$((n+1)); done; } > "$RT/COORD.md"
  python3 "$CP" scan --root "$RT" >/dev/null 2>&1
  t "a [$TAG]-tagged line is machinery, whatever it says" \
    "$(python3 -c "
import json;d=json.load(open('$RT/compile/candidates.json'))
print([s['items'] for s in d['sources'] if s['name']=='COORD.md'][0])")" "0"
done

# ── B4 · defence in depth: a candidates.json written BEFORE the filter existed ──
# Dropping the lines at the reader does nothing about a scan already on disk, which
# `draft --all-ripe` picks up on the very next pulse. So draft re-reads the cited rows.
RN="$W/stale-scan"; mkdir -p "$RN/compile"
head -25 "$RM/COORD.md" > "$RN/COORD.md"
python3 - "$RN" <<'STALEPY'
import json, sys
root = sys.argv[1]
ev = [{"ref": "COORD.md:%d" % i, "ts": "2026-09-05 00:00Z",
       "text": "adopt slug-%d -> ADOPTED | evidence: fixture.sh exit 0" % i}
      for i in range(2, 25, 2)]
json.dump({"generated": "before the filter", "root": root, "sources": [], "notes": [],
           "params": {}, "candidates": [
               {"slug": "slug-adopt-benchmark", "alias": "", "occurrences": 12,
                "shape": 0.8, "ripe": True, "status": "NEW", "kind": "estate",
                "core": ["adopt", "benchmark"], "signature": [], "sources": {"coord": 12},
                "weak_source": False, "rank": 1, "evidence": ev}]},
          open(root + "/compile/candidates.json", "w"))
STALEPY
python3 "$CP" draft --root "$RN" --all-ripe > "$W/stale.txt" 2>&1
t "draft on a pre-filter scan exits 0" "$?" "0"
has "…and REFUSES the machinery candidate" "REFUSE " "$W/stale.txt"
has "…counting the rows it re-read" "cited rows were written by the harness about itself" \
  "$W/stale.txt"
has "…and it is the MACHINERY rule that fired, not the narration one" \
  "tagged [compile]/[daemon]/[hook]/[pulse]" "$W/stale.txt"
t "…scaffolding nothing" \
  "$([ -d "$RN/compile/slug-adopt-benchmark" ] && echo built || echo none)" "none"
has "…and banking the refusal so it is not re-examined every pulse" \
  "draft REFUSED:" "$RN/compile/decisions.md"
has "…as a ruling that names who made it" "Ruled by the scanner, not the owner" \
  "$RN/compile/decisions.md"
python3 "$CP" draft --root "$RN" --all-ripe > "$W/stale2.txt" 2>&1
t "…so a second pulse re-examines nothing" \
  "$(grep -c 'REFUSE ' "$W/stale2.txt" | tr -d ' ')" "0"
t "…and decisions.md did not grow a second time" \
  "$(grep -c 'draft REFUSED:' "$RN/compile/decisions.md" | tr -d ' ')" "1"
# a candidate with a MINORITY of machinery rows is still real work and still drafts
RQ="$W/mixed"; cp -R "$R" "$RQ"; rm -rf "$RQ/compile"
printf -- '- [2026-09-05 20:00Z] [compile] adopt something -> ADOPTED | evidence: x\n' >> "$RQ/COORD.md"
python3 "$CP" scan --root "$RQ" >/dev/null 2>&1
python3 "$CP" draft --root "$RQ" --all-ripe > "$W/mixed.txt" 2>&1
t "a real candidate beside one machinery line still drafts (0)" "$?" "0"
has "…and was not refused" "DRAFT " "$W/mixed.txt"

# ── D1 · the daily cap had a hole the size of a missing `usage` field ──────────
# `daemon_spend_today` summed only the numeric receipts, so a runner reporting no usage
# cost ZERO against the cap: the disclosure line said "unverifiable" and gated nothing.
# An unknown run is now charged at the RUN CEILING — over-counting on purpose, because the
# thing being bounded is a bill and the safe direction to be wrong in is "stopped early".
RP="$W/capD1"; cp -R "$R" "$RP"; rm -rf "$RP/compile"
( cd "$RP" && git init -q ) >/dev/null 2>&1
python3 "$CP" scan --root "$RP" >/dev/null 2>&1
python3 "$CP" draft --root "$RP" --all-ripe >/dev/null 2>&1
SP="$(python3 -c "
import json;print(json.load(open('$RP/compile/candidates.json'))['candidates'][0]['slug'])")"
# 500,000 is chosen to isolate the DEFECT rather than the cap: two unknown runs are
# charged 400,000 each, so run 1 completes (400,000 < 500,000 at the refute step) and
# run 2 is refused (800,000 >= 500,000). Under the old numeric-only sum both runs
# proceeded forever, which is the hole.
python3 "$CP" auto --root "$RP" --on --unattended --daily-cap 500000 --run-cap 400000 \
  >/dev/null 2>&1
ARP(){ python3 "$CP" auto-run --root "$RP" --runner "$FAKE" --today "$TODAY" "$@"; }
FAKE_BUILD=nousage FAKE_REFUTE=nousage ARP --next > "$W/d1-run1.txt" 2>&1
t "the first unknown-usage run completes (0)" "$?" "0"
has "…and its receipt says what the cap charged it" \
  "tokens=unknown counted-as=400000" "$RP/spend/ledger.md"
t "…without inventing a token count on the line itself" \
  "$(grep -c 'lane=daemon model=opus tokens=unknown' "$RP/spend/ledger.md" | tr -d ' ')" "2"
python3 "$CP" decide --root "$RP" --slug "$SP" --status DRAFTED --note "re-armed" \
  >/dev/null 2>&1
BEFORE_D1="$(grep -c 'lane=daemon' "$RP/spend/ledger.md" | tr -d ' ')"
FAKE_BUILD=nousage FAKE_REFUTE=nousage ARP --next > "$W/d1-run2.txt" 2>&1
t "THE SECOND RUN IS REFUSED by the daily cap (exit 6)" "$?" "6"
has "…before starting the step" "REFUSED to start build" "$W/d1-run2.txt"
has "…counting the unreported runs at the run ceiling" \
  "run(s) whose usage the CLI never reported" "$W/d1-run2.txt"
has "…and saying why that is the honest direction to be wrong in" \
  "a cap with a hole in it" "$W/d1-run2.txt"
t "…and nothing more was spent" \
  "$(grep -c 'lane=daemon' "$RP/spend/ledger.md" | tr -d ' ')" "$BEFORE_D1"
python3 "$CP" auto-run --root "$RP" --runner "$FAKE" --today "$TODAY" --dry-run \
  > "$W/d1-dry.txt" 2>&1
has "--dry-run shows the CONSERVATIVE sum, not the observed one" \
  "spent today (conservative)" "$W/d1-dry.txt"
has "…naming how many unknown runs are in it" "unknown-usage run(s) charged at" "$W/d1-dry.txt"

echo "── V · the retroactive guard, and the deliberate git admission (seat follow-ups)"
# (1) RETROACTIVE. The machinery filter protects the FUTURE: new candidates are not built
# from machinery lines, and draft will not scaffold an old one. Neither touches a slug that
# was ALREADY scaffolded before the filter existed — and on this estate the pulse daemon
# made 36 of them. A guard that only protects the future leaves the exposure where it is.
RV="$W/retro"; mkdir -p "$RV/compile"
{ echo "# COORD.md"
  i=0; while [ "$i" -lt 6 ]; do
    printf -- '- [2026-09-05 0%d:00Z] [compile] adopt slug-%d -> ADOPTED | evidence: fixture.sh exit 0\n' "$i" "$i"
    printf -- '- [2026-09-05 0%d:30Z] [main] regenerate the customer invoice pdf for acme -> python3 bin/invoice.py exit 0, pdf mailed | evidence: out/inv.pdf\n' "$i"
    i=$((i+1)); done; } > "$RV/COORD.md"
# two slugs already on disk, drafted BEFORE the filter: one machinery, one real work.
for SL in machinery-slug honest-slug; do mkdir -p "$RV/compile/$SL"; done
{ echo "# Functional contract (DRAFT) — machinery-slug"; echo
  i=2; while [ "$i" -le 12 ]; do
    printf -- '| %d | _<rewrite>_ — adopt | [COORD 2026-09-05] `COORD.md:%d` | ? | seat | ? | ? |\n' "$i" "$i"
    i=$((i+2)); done; } > "$RV/compile/machinery-slug/CONTRACT.md"
{ echo "# Functional contract (DRAFT) — honest-slug"; echo
  i=3; while [ "$i" -le 13 ]; do
    printf -- '| %d | _<rewrite>_ — invoice | [COORD 2026-09-05] `COORD.md:%d` | ? | seat | ? | ? |\n' "$i" "$i"
    i=$((i+2)); done; } > "$RV/compile/honest-slug/CONTRACT.md"
printf -- '- [2026-09-05 10:00Z] slug=machinery-slug status=DRAFTED note="drafted before the filter"\n- [2026-09-05 10:01Z] slug=honest-slug status=DRAFTED note="drafted before the filter"\n' \
  > "$RV/compile/decisions.md"
python3 "$CP" draft --root "$RV" --recheck > "$W/retro.txt" 2>&1
t "draft --recheck exits 0" "$?" "0"
has "…DECLINES the slug built from the harness's own paperwork" "DECLINE machinery-slug" \
  "$W/retro.txt"
has "…counting the rows it re-read from today's ledgers" "machinery" "$W/retro.txt"
has "…and KEEPS the one built from work somebody did" "KEEP    honest-slug" "$W/retro.txt"
has "…reporting both counts" "1 declined, 1 kept" "$W/retro.txt"
has "…the ruling is banked, and names the scanner as its author" \
  "draft --recheck REFUSED:" "$RV/compile/decisions.md"
has "…with the owner's override" "re-rule with decide --status DRAFTED" "$RV/compile/decisions.md"
t "…and NOTHING was deleted — the directory is the owner's" \
  "$([ -d "$RV/compile/machinery-slug" ] && echo kept)" "kept"
has "…and it says so" "left on disk untouched" "$W/retro.txt"
t "the declined slug is out of auto-run's reach" \
  "$(python3 -c "
import json,subprocess,sys
rows=[l for l in open('$RV/compile/decisions.md') if 'slug=machinery-slug' in l]
print('status=DECLINED' in rows[-1])")" "True"
t "…while the honest one is still DRAFTED" \
  "$(python3 -c "
rows=[l for l in open('$RV/compile/decisions.md') if 'slug=honest-slug' in l]
print('status=DRAFTED' in rows[-1])")" "True"
python3 "$CP" draft --root "$RV" --recheck > "$W/retro2.txt" 2>&1
has "a second recheck re-judges only what is still DRAFTED" "1 DRAFTED slug(s)" "$W/retro2.txt"
t "…and does not re-decline what it already declined" \
  "$(grep -c 'draft --recheck REFUSED:' "$RV/compile/decisions.md" | tr -d ' ')" "1"
# a DRAFTED slug with no contract cannot be judged, and says so rather than guessing
mkdir -p "$RV/compile/no-contract"
printf -- '- [2026-09-05 10:02Z] slug=no-contract status=DRAFTED note="x"\n' >> "$RV/compile/decisions.md"
python3 "$CP" draft --root "$RV" --recheck > "$W/retro3.txt" 2>&1
has "a slug with no CONTRACT.md is reported unjudgeable, never declined by default" \
  "SKIP    no-contract" "$W/retro3.txt"
has "…and counted apart from the verdicts" "unjudgeable" "$W/retro3.txt"
python3 "$CP" draft --root "$W/undrafted" --recheck >/dev/null 2>&1
t "recheck on an estate with nothing drafted exits 0" "$?" "0"

# (2) THE GIT ADMISSION. DRAFTED scaffolds stay out of git — an unattended daemon that
# drafts 36 directories overnight must not also decide what the repository contains. So
# adoption prints the exact command a person runs to admit one.
python3 "$CP" decide --root "$R8" --slug "$S8" --status ADOPTED \
  --evidence "fixture=x/fixture.sh exit 0" --evidence "benchmark=x/benchmark.sh exit 0" \
  --evidence "refuter=x/REFUTER.md CLEAN" > "$W/gitadd.txt" 2>&1
t "an adoption ruling exits 0" "$?" "0"
has "…and prints the exact git command that admits the runtime" \
  "git add -f compile/$S8" "$W/gitadd.txt"
has "…saying why the command is needed at all" "gitignored while DRAFTED" "$W/gitadd.txt"
has "auto-run's own adoption prints it too" "git add -f compile/$SA" "$W/ar-green.txt"
python3 "$CP" auto-run --root "$RA" --runner "$FAKE" --dry-run > "$W/gitdry.txt" 2>&1
has "…and the dry-run plan names it before anything runs" "on adoption   : prints \`git add -f" \
  "$W/gitdry.txt"

echo "── W · job-likeness: which candidates are work, and how many per pass"
# ⛔ SCORED ON THE LEDGER LINE, NEVER ON THE CONTRACT ROW. Measured on the live estate
# first: every CONTRACT.md row carries its own citation by construction, so scoring the row
# scored the scaffolding and returned 1.00 for all 38 drafted slugs. The score reads the
# cited line's own body.
RW="$W/jobscore"; mkdir -p "$RW"
{ echo "# COORD.md"; echo "## LEDGER"
  # 4 RUNNABLE shapes — each row names something a machine did
  n=0; while [ "$n" -lt 4 ]; do
    printf -- '- [2026-04-%02d 09:00Z] [main] run the parser fixture for tenant-%d -> bash scripts/parser-fixture.sh exits 0, 44 cases green | evidence: fixture.log\n' "$((n+1))" "$n"
    printf -- '- [2026-04-%02d 10:00Z] [main] regenerate the invoice pdf for client-%d -> python3 bin/invoice.py --client %d exit 0 | evidence: out/invoice.pdf\n' "$((n+1))" "$n" "$n"
    printf -- '- [2026-04-%02d 11:00Z] [main] rebuild the search index for shard-%d -> make reindex exits 0, 12k docs | evidence: index/shard.json\n' "$((n+1))" "$n"
    printf -- '- [2026-04-%02d 12:00Z] [main] publish the nightly metrics roll-up for region-%d -> python3 jobs/rollup.py --region %d exit 0 | evidence: roll.json\n' "$((n+1))" "$n" "$n"
    n=$((n+1)); done
  # 6 NARRATION shapes — an account of a decision, with nothing runnable in it
  n=0; while [ "$n" -lt 4 ]; do
    printf -- '- [2026-05-%02d 09:00Z] [main] owner asked whether the pricing tiers should change for cohort %d -> we talked it through and agreed to wait\n' "$((n+1))" "$n"
    printf -- '- [2026-05-%02d 10:00Z] [main] discussed the hiring plan with the team for quarter %d -> everyone agreed the shape was right\n' "$((n+1))" "$n"
    printf -- '- [2026-05-%02d 11:00Z] [main] reviewed the brand direction with the studio round %d -> the owner liked the warmer palette\n' "$((n+1))" "$n"
    printf -- '- [2026-05-%02d 12:00Z] [main] considered whether to open an office in city %d -> parked until the headcount settles\n' "$((n+1))" "$n"
    printf -- '- [2026-05-%02d 13:00Z] [main] argued about the naming of the release train %d -> nobody minded enough to change it\n' "$((n+1))" "$n"
    printf -- '- [2026-05-%02d 14:00Z] [main] wondered aloud whether the roadmap for half %d was honest -> agreed it mostly was\n' "$((n+1))" "$n"
    n=$((n+1)); done; } > "$RW/COORD.md"
python3 "$CP" scan --root "$RW" >/dev/null 2>&1
t "the seeded corpus scans (0)" "$?" "0"
JW(){ python3 -c "
import json,sys
d=json.load(open('$RW/compile/candidates.json')); c=[x for x in d['candidates'] if x['ripe']]
print(eval(sys.argv[1], {'d':d,'c':c}))" "$1"; }
t "every candidate carries a job-likeness score" "$(JW "all('score' in x for x in c)")" "True"
t "…the runnable shapes score above zero" \
  "$(JW "all(x['score'] > 0 for x in c if any(k in x['slug'] for k in ('fixtur','invoic','index','rollup','parser','reindex')))")" "True"
t "…and the pure-narration shapes score exactly zero" \
  "$(JW "all(x['score'] == 0 for x in c if any(k in x['slug'] for k in ('agre','talk','discus','wonder','argu','consider')))")" "True"
has "candidates.md carries the score in its table" "| job |" "$RW/compile/candidates.md"
has "…and explains what it measures" "share of a candidate's cited rows carrying a" \
  "$RW/compile/candidates.md"
# The corpus seeds 4 runnable JOB SHAPES and 6 narration shapes, 4 rows each. The scanner
# clusters them on its own terms — shapes that share a procedure merge — so the arms below
# assert the PROPERTY (which side of zero each candidate lands on) rather than a candidate
# count the clusterer never promised.
t "the corpus seeds 16 runnable rows" \
  "$(grep -cE 'exits 0|exit 0' "$RW/COORD.md" | tr -d ' ')" "16"
t "…and 24 narration rows" \
  "$(grep -cE 'agreed|liked|parked until|nobody minded' "$RW/COORD.md" | tr -d ' ')" "24"
NRUN="$(JW "sum(1 for x in c if x['score'] > 0)")"
NNAR="$(JW "sum(1 for x in c if x['score'] == 0)")"
t "every candidate is on one side of zero or the other" \
  "$(JW "len(c)")" "$(python3 -c "print($NRUN + $NNAR)")"
t "…at least one candidate scores as runnable work" \
  "$(python3 -c "print($NRUN > 0)")" "True"
t "…and at least one scores as pure narration" \
  "$(python3 -c "print($NNAR > 0)")" "True"

# (2)+(3): at most N per pass, best first; narration never drafted at all
python3 "$CP" draft --root "$RW" --all-ripe > "$W/jw-draft.txt" 2>&1
t "draft --all-ripe exits 0" "$?" "0"
t "…drafting every candidate that scores above zero" \
  "$(grep -c '^DRAFT ' "$W/jw-draft.txt" | tr -d ' ')" "$NRUN"
t "…and refusing every candidate that scores exactly zero" \
  "$(grep -c '^REFUSE ' "$W/jw-draft.txt" | tr -d ' ')" "$NNAR"
has "…as narration rather than as a mistake" "narration, not a job" "$W/jw-draft.txt"
has "…banking the ruling with the owner's override" \
  "re-rule with decide --status NEW" "$RW/compile/decisions.md"
t "…so nothing narration-shaped reached the disk" \
  "$(ls "$RW/compile" | grep -cE 'agre|talk|discus|wonder' | tr -d ' ')" "0"
has "…and the pass reports its own cap" "held below the per-pass cap of 5" "$W/jw-draft.txt"

# the cap itself: 4 runnable under a cap of 2 leaves 2 waiting, best first
RW2="$W/jobscore2"; cp -R "$RW" "$RW2"; rm -rf "$RW2/compile"
python3 "$CP" scan --root "$RW2" >/dev/null 2>&1
python3 "$CP" draft --root "$RW2" --all-ripe --max 1 > "$W/jw-cap.txt" 2>&1
t "--max 1 drafts exactly one" "$(grep -c '^DRAFT ' "$W/jw-cap.txt" | tr -d ' ')" "1"
t "…and holds every other runnable candidate" \
  "$(grep -c '^HOLD ' "$W/jw-cap.txt" | tr -d ' ')" "$(python3 -c "print($NRUN - 1)")"
has "…saying why they were not drafted" "not drafted: below the per-pass cap" "$W/jw-cap.txt"
t "…the held ones are still NEW, waiting their turn" \
  "$(python3 -c "
import re
held=[l.split()[1] for l in open('$W/jw-cap.txt') if l.startswith('HOLD ')]
dec=open('$RW2/compile/decisions.md').read()
print(all('slug=%s status=DRAFTED' % h not in dec for h in held))")" "True"
t "…and the one it took outscores every one it held" \
  "$(python3 -c "
import json
d=json.load(open('$RW2/compile/candidates.json'))
by={x['slug']:x['score'] for x in d['candidates']}
took=[l.split()[1] for l in open('$W/jw-cap.txt') if l.startswith('DRAFT ')]
held=[l.split()[1] for l in open('$W/jw-cap.txt') if l.startswith('HOLD ')]
print(min(by[s] for s in took) >= max(by[s] for s in held))")" "True"
python3 "$CP" draft --root "$RW2" --all-ripe --max 1 > "$W/jw-cap2.txt" 2>&1
t "a second pass takes the next one — a cap is a queue, not a refusal" \
  "$(grep -c '^DRAFT ' "$W/jw-cap2.txt" | tr -d ' ')" "1"

# (4) auto-run --next takes the highest-scored DRAFTED slug, not the oldest
( cd "$RW" && git init -q ) >/dev/null 2>&1
python3 "$CP" auto --root "$RW" --on --unattended --daily-cap 90000000 >/dev/null 2>&1
TOPW="$(python3 -c "
import json
d=json.load(open('$RW/compile/candidates.json'))
dec=open('$RW/compile/decisions.md').read()
c=[x for x in d['candidates'] if 'slug=%s status=DRAFTED' % x['slug'] in dec]
print(sorted(c, key=lambda x:(-x['score'], -x['occurrences']))[0]['slug'])")"
python3 "$CP" auto-run --root "$RW" --runner "$FAKE" --dry-run --next > "$W/jw-next.txt" 2>&1
has "--next names the highest-scored DRAFTED slug, not the first armed" \
  "candidate     : $TOPW" "$W/jw-next.txt"

# (5) recheck applies the narration rule to slugs already on disk
RW3="$W/jobscore3"; mkdir -p "$RW3/compile/narration-slug"
head -3 "$RW/COORD.md" > /dev/null
{ echo "# COORD.md"; echo "## LEDGER"
  n=0; while [ "$n" -lt 6 ]; do
    printf -- '- [2026-05-%02d 09:00Z] [main] owner asked whether the pricing tiers should change for cohort %d -> we talked it through and agreed to wait\n' "$((n+1))" "$n"
    n=$((n+1)); done; } > "$RW3/COORD.md"
{ echo "# Functional contract (DRAFT) — narration-slug"; echo
  n=3; while [ "$n" -le 8 ]; do
    printf -- '| %d | _<rewrite>_ — talked | [COORD 2026-05-01] `COORD.md:%d` | ? | seat | ? | ? |\n' "$n" "$n"
    n=$((n+1)); done; } > "$RW3/compile/narration-slug/CONTRACT.md"
printf -- '- [2026-05-10 10:00Z] slug=narration-slug status=DRAFTED note="drafted before the score existed"\n' \
  > "$RW3/compile/decisions.md"
python3 "$CP" draft --root "$RW3" --recheck > "$W/jw-re.txt" 2>&1
t "draft --recheck exits 0" "$?" "0"
has "…declining a slug already on disk whose rows carry nothing runnable" \
  "DECLINE narration-slug" "$W/jw-re.txt"
has "…naming the reason" "narration, not a job" "$W/jw-re.txt"
has "…and banking it with the override" "re-rule with decide --status DRAFTED" \
  "$RW3/compile/decisions.md"
t "…while still deleting nothing" \
  "$([ -d "$RW3/compile/narration-slug" ] && echo kept)" "kept"

echo
echo "compile fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
