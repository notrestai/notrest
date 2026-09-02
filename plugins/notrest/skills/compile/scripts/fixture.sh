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

echo
echo "compile fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
