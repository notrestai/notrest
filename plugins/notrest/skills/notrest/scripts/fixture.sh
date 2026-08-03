#!/bin/bash
# fixture.sh — asserts establish.py AND the hook-closure patches it depends on.
# Self-relative: runs from any cwd, writes only inside its own mktemp dir, touches no
# real project. Runnable from a clean clone — python3, bash and git are the only
# prerequisites, and nothing here stands on a gitignored artifact.
#
# HERMETIC BY CONSTRUCTION. The hooks are COPIED into the sandbox before they are run,
# for one specific reason: session-start.sh resolves its own directory and fires a
# background `git pull --ff-only` at that repo. Run in place, a fixture would pull the
# owner's working tree. Copied to a non-git sandbox dir, `dirname $0` resolves to a
# directory git knows nothing about and the self-update path is dead by construction.
#
# MUTATION-AWARE (2026-08-02 adversarial round). The first version of this fixture passed
# 78/0 against a DE-ATOMIZED atomic_write — every assertion held while the property was
# gone. Two assertions below exist to kill that mutant: a read-only CLAUDE.md in a
# writable directory (tmp+os.replace SUCCEEDS, since replace needs the directory bit and
# not the file's; a plain open(w) cannot) and a read-only directory (a failed write must
# leave no .notrest-*.tmp behind and the target byte-untouched). An assertion that cannot
# fail is decoration.
# Usage: bash <notrest-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
EST="$HERE/establish.py"
HOOKS_SRC="$(cd "$HERE/../../../hooks" && pwd)"
W="$(mktemp -d)"; trap 'chmod -R u+w "$W" 2>/dev/null; rm -rf "$W"' EXIT
WR="$(cd "$W" && pwd -P)"          # realpath: macOS mktemp hands back a /var symlink
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
has(){ if grep -qF -- "$2" "$3" 2>/dev/null; then ok "$1"; else no "$1 — [$2] not in $3"; fi; }
hasnt(){ if grep -qF -- "$2" "$3" 2>/dev/null; then no "$1 — [$2] unexpectedly in $3"; else ok "$1"; fi; }
ckt(){ cksum < "$1" | awk '{print $1"-"$2}'; }
nblk(){ grep -c '<!-- notrest:protocol v' "$1" 2>/dev/null || true; }
est(){ python3 "$EST" "$@"; }

# ── the sandboxed hooks (estate-root.sh included — it is what they all source) ────────
mkdir -p "$W/hooks"
for h in session-start session-end coord-nudge agent-ledger estate-root; do
  cp "$HOOKS_SRC/$h.sh" "$W/hooks/$h.sh"
done
GITTOP="$(cd "$W" && git rev-parse --show-toplevel 2>/dev/null || true)"
t "sandbox is outside any git repo" "${GITTOP:-none}" "none"

echo "── establish.py: the establishment contract"

P1="$W/proj1"; mkdir -p "$P1"; : > "$P1/README.md"
est check --root "$P1" > "$W/o" 2>&1; t "fresh marker dir → check" "$?" "6"
has "check names COORD absent" "COORD.md absent" "$W/o"
has "check verdict NOT ESTABLISHED" "NOT ESTABLISHED" "$W/o"

est establish --root "$P1" > "$W/o" 2>&1; t "establish → exit" "$?" "0"
t "COORD.md created" "$([ -f "$P1/COORD.md" ] && echo y || echo n)" "y"
t "CLAUDE.md created" "$([ -f "$P1/CLAUDE.md" ] && echo y || echo n)" "y"
has "COORD scaffold title" "# COORD.md — session coordination ledger" "$P1/COORD.md"
has "COORD scaffold ledger marker" "## LEDGER" "$P1/COORD.md"
has "COORD scaffold ledger line" "[notrest] COORD.md scaffolded by /notrest establish" "$P1/COORD.md"
t "exactly ONE protocol block" "$(nblk "$P1/CLAUDE.md")" "1"
t "block is closed" "$(grep -c '<!-- /notrest:protocol -->' "$P1/CLAUDE.md")" "1"
has "block carries the offload rule" "opus" "$P1/CLAUDE.md"
t "plain establish NEVER runs git init" "$([ -d "$P1/.git" ] && echo initted || echo none)" "none"

C1="$(ckt "$P1/COORD.md")"; K1="$(ckt "$P1/CLAUDE.md")"
est establish --root "$P1" > "$W/o" 2>&1; t "establish twice → exit" "$?" "0"
t "COORD byte-identical after re-establish" "$(ckt "$P1/COORD.md")" "$C1"
t "CLAUDE byte-identical after re-establish" "$(ckt "$P1/CLAUDE.md")" "$K1"
t "still exactly ONE block" "$(nblk "$P1/CLAUDE.md")" "1"
has "re-establish says it wrote nothing" "wrote: nothing (already established)" "$W/o"

est check --root "$P1" > "$W/o" 2>&1; t "check after establish" "$?" "0"
has "check verdict ESTABLISHED" "notrest: ESTABLISHED" "$W/o"
has "adoption facts are INFO" "INFO  LEDGER-LINES" "$W/o"

P2="$W/proj2"; mkdir -p "$P2"
printf '# Their project\n\nTheir own rules. Do not touch.\n' > "$P2/CLAUDE.md"
est establish --root "$P2" > "$W/o" 2>&1; t "establish over existing CLAUDE.md" "$?" "0"
head -3 "$P2/CLAUDE.md" > "$W/head3"; printf '# Their project\n\nTheir own rules. Do not touch.\n' > "$W/orig3"
t "existing content survives byte-for-byte" "$(ckt "$W/head3")" "$(ckt "$W/orig3")"
t "one block appended, not two" "$(nblk "$P2/CLAUDE.md")" "1"

echo "── F-12(a): the hostile CLAUDE.md corpus"

P7="$W/proj7"; mkdir -p "$P7"; : > "$P7/README.md"
printf '# Windows project\r\n\r\nCaf\351 notes: r\351sum\351.\r\n' > "$P7/CLAUDE.md"
cp "$P7/CLAUDE.md" "$W/orig7"; OS7=$(wc -c < "$W/orig7" | tr -d ' ')
est establish --root "$P7" > "$W/o" 2>&1; t "CRLF+latin-1 CLAUDE.md → establish" "$?" "0"
head -c "$OS7" "$P7/CLAUDE.md" > "$W/pre7"
t "original bytes survive EXACTLY (CRLF + latin-1)" "$(ckt "$W/pre7")" "$(ckt "$W/orig7")"
t "CRLF count preserved" "$(tr -cd '\r' < "$P7/CLAUDE.md" | wc -c | tr -d ' ')" "3"
t "no U+FFFD replacement char written" \
  "$(grep -c $'\xef\xbf\xbd' "$P7/CLAUDE.md" 2>/dev/null || true)" "0"
t "the block still landed" "$(nblk "$P7/CLAUDE.md")" "1"

P8="$W/proj8"; mkdir -p "$P8"; : > "$P8/README.md"
{ printf '# Docs\n\nHere is what the block looks like:\n\n'
  printf '```markdown\n'
  printf '<!-- notrest:protocol v1 (do not edit inside markers; managed by /notrest) -->\n'
  printf 'example body\n'
  printf '<!-- /notrest:protocol -->\n'
  printf '```\n'; } > "$P8/CLAUDE.md"
K8="$(ckt "$P8/CLAUDE.md")"
# The example is MASKED — it is never treated as the block (F-3). But the raw text does
# carry an opener, and appending past that disagreement is how a masking bug becomes an
# unbounded pile of blocks (N-1), so the honest move is to write nothing and say why.
est check --root "$P8" > "$W/o" 2>&1; t "fenced EXAMPLE is not the block → check" "$?" "5"
has "check names the fence/mask disagreement" "inside a fenced/masked region" "$W/o"
hasnt "check never claims the example IS the block" "block present at v1" "$W/o"
est establish --root "$P8" > "$W/o" 2>&1; t "fenced example → establish appends NOTHING" "$?" "5"
t "the fenced example survives byte-for-byte" "$(ckt "$P8/CLAUDE.md")" "$K8"
t "no second block was appended beside it" "$(grep -c 'notrest:protocol v1' "$P8/CLAUDE.md")" "1"

P9="$W/proj9"; mkdir -p "$P9"; : > "$P9/README.md"
{ printf '<!-- notrest:protocol v1 (do not edit inside markers; managed by /notrest) -->\n'
  printf '\nIRREPLACEABLE USER CONTENT\n\n'
  printf '<!-- notrest:protocol v0 (do not edit inside markers; managed by /notrest) -->\n'
  printf 'old body\n'
  printf '<!-- /notrest:protocol -->\n'; } > "$P9/CLAUDE.md"
K9="$(ckt "$P9/CLAUDE.md")"
est check --root "$P9" > "$W/o" 2>&1; t "stray open marker → check is PARTIAL" "$?" "5"
has "check names the ambiguity" "multiple/ambiguous protocol markers" "$W/o"
est establish --root "$P9" > "$W/o" 2>&1; t "stray open marker → establish refuses" "$?" "5"
has "establish names the ambiguity" "multiple/ambiguous protocol markers" "$W/o"
has "refusal says nothing was written" "nothing was written" "$W/o"
t "the file is byte-untouched" "$(ckt "$P9/CLAUDE.md")" "$K9"
has "USER CONTENT survives" "IRREPLACEABLE USER CONTENT" "$P9/CLAUDE.md"

P10="$W/proj10"; mkdir -p "$P10"; : > "$P10/README.md"
{ printf '<!-- notrest:protocol v0 (managed by /notrest) -->\nfirst\n<!-- /notrest:protocol -->\n'
  printf '\nmiddle\n\n'
  printf '<!-- notrest:protocol v1 (managed by /notrest) -->\nsecond\n<!-- /notrest:protocol -->\n'; } > "$P10/CLAUDE.md"
K10="$(ckt "$P10/CLAUDE.md")"
est check --root "$P10" > "$W/o" 2>&1; t "duplicate blocks → check" "$?" "5"
has "duplicate finding names the shape" "duplicate protocol blocks" "$W/o"
has "duplicate finding names an extra line number" "line 7" "$W/o"
est establish --root "$P10" > "$W/o" 2>&1; t "duplicate blocks → establish refuses" "$?" "5"
t "duplicate file byte-untouched" "$(ckt "$P10/CLAUDE.md")" "$K10"

P3="$W/proj3"; mkdir -p "$P3"; : > "$P3/README.md"
{ printf 'TOP LINE\n\n'
  printf '<!-- notrest:protocol v0 (do not edit inside markers; managed by /notrest) -->\n'
  printf 'stale body WITH A HAND EDIT\n'
  printf '<!-- /notrest:protocol -->\n\n'
  printf 'BOTTOM LINE\n'; } > "$P3/CLAUDE.md"
est check --root "$P3" > "$W/o" 2>&1; t "older block → check is PARTIAL" "$?" "5"
est establish --root "$P3" > "$W/o" 2>&1; t "older block → establish" "$?" "0"
t "still exactly ONE block after upgrade" "$(nblk "$P3/CLAUDE.md")" "1"
has "block upgraded to v1" "notrest:protocol v1" "$P3/CLAUDE.md"
hasnt "stale body gone" "stale body" "$P3/CLAUDE.md"
has "text above the block survives" "TOP LINE" "$P3/CLAUDE.md"
has "text below the block survives" "BOTTOM LINE" "$P3/CLAUDE.md"
has "in-block edits announced, not silent" "in-block edits discarded" "$W/o"
t "the discarded body was banked" \
  "$([ -f "$P3/CLAUDE.md.notrest-v0.bak" ] && echo y || echo n)" "y"
has "the backup holds the old body" "stale body WITH A HAND EDIT" "$P3/CLAUDE.md.notrest-v0.bak"

echo "── F-12(b): atomicity, proven by a mutant that would survive without it"

P11="$W/proj11"; mkdir -p "$P11"; : > "$P11/README.md"
printf 'read-only foundation\n' > "$P11/CLAUDE.md"; chmod 444 "$P11/CLAUDE.md"
est establish --root "$P11" > "$W/o" 2>&1; t "read-only CLAUDE.md → atomic write wins" "$?" "0"
t "the block reached the read-only file" "$(nblk "$P11/CLAUDE.md")" "1"
has "its original line survives" "read-only foundation" "$P11/CLAUDE.md"
chmod 644 "$P11/CLAUDE.md"

P12="$W/proj12"; mkdir -p "$P12"; : > "$P12/README.md"
printf 'untouchable\n' > "$P12/CLAUDE.md"; K12="$(ckt "$P12/CLAUDE.md")"; chmod 555 "$P12"
est establish --root "$P12" > "$W/o" 2>&1; t "read-only dir → establish exit" "$?" "6"
has "failure is named, not swallowed" "writes failed" "$W/o"
hasnt "never claims 'already established'" "already established" "$W/o"
t "no .notrest tmp debris survives" "$(ls -A "$P12" | grep -c '^\.notrest-' || true)" "0"
t "target byte-untouched after failed write" "$(ckt "$P12/CLAUDE.md")" "$K12"
chmod 755 "$P12"

echo "── F-12(e): COORD edge shapes"

P13="$W/proj13"; mkdir -p "$P13"; : > "$P13/README.md"; : > "$P13/COORD.md"
est check --root "$P13" > "$W/o" 2>&1; t "empty COORD.md reads as absent" "$?" "6"
est establish --root "$P13" > "$W/o" 2>&1; t "empty COORD.md is rescaffolded" "$?" "0"
has "rescaffolded with the ledger header" "## LEDGER" "$P13/COORD.md"

P14="$W/proj14"; mkdir -p "$P14"; : > "$P14/README.md"
printf '# my own coord\n\n- [2026-01-01 00:00Z] [me] a line\n' > "$P14/COORD.md"
K14="$(ckt "$P14/COORD.md")"
est establish --root "$P14" > "$W/o" 2>&1; t "headerless COORD.md → PARTIAL" "$?" "5"
has "the WARN names the one-line repair" "appending one line '## LEDGER'" "$W/o"
t "a foreign ledger is NEVER rewritten" "$(ckt "$P14/COORD.md")" "$K14"

echo "── F-4 / F-8: roots that must be refused"

BARE="$W/bare"; mkdir -p "$BARE"
( cd "$BARE" && est check ) > "$W/o" 2>&1; t "bare dir, no --root → refusal" "$?" "2"
has "refusal names the markers it looked for" "no project marker" "$W/o"
t "refusal wrote nothing" "$(ls -A "$BARE" | wc -l | tr -d ' ')" "0"
DOTC="$W/dotclaude"; mkdir -p "$DOTC/.claude"
( cd "$DOTC" && est check ) > "$W/o" 2>&1; t ".claude alone is NOT a project marker" "$?" "2"
est establish --root "$HOME" > "$W/o" 2>&1; t "--root \$HOME → refused" "$?" "2"
has "the HOME refusal explains itself" "HOME directory, not a project" "$W/o"
est establish --root / > "$W/o" 2>&1; t "--root / → refused" "$?" "2"
G2="$W/gitsub"; mkdir -p "$G2/inner"; ( cd "$G2" && git init -q ) >/dev/null 2>&1
: > "$G2/inner/README.md"
est establish --root "$G2/inner" > "$W/o" 2>&1; t "--root inside a git repo → refused" "$?" "2"
has "refusal names the toplevel to use instead" "Use --root" "$W/o"
t "…and wrote nothing in the subdir" \
  "$([ -f "$G2/inner/COORD.md" ] && echo wrote || echo none)" "none"

echo "── non-git honesty, --git-init, symlinks"

est establish --root "$P1" > "$W/o" 2>&1
has "non-git WARN: self-update" "WARN  GIT-DEGRADED  — self-update is dead" "$W/o"
has "non-git WARN: ship gates" "ship gates are weaker" "$W/o"
has "non-git WARN: trail not diffable" "the trail is not diffable" "$W/o"
has "non-git names --git-init as opt-in" "opt-in only, never automatic" "$W/o"

P4="$W/proj4"; mkdir -p "$P4"; : > "$P4/README.md"
est establish --root "$P4" --git-init > "$W/o" 2>&1; t "--git-init → exit" "$?" "0"
t ".git created" "$([ -d "$P4/.git" ] && echo y || echo n)" "y"
t "nothing was committed" "$(cd "$P4" && git rev-list --all --count 2>/dev/null || echo 0)" "0"

mkdir -p "$W/real/proj5"; : > "$W/real/proj5/README.md"; ln -s "$WR/real/proj5" "$W/link5"
est establish --root "$W/link5" > "$W/o" 2>&1; t "symlinked root → exit" "$?" "0"
has "verdict names the resolved real path" "$WR/real/proj5" "$W/o"
t "files landed in the real dir" "$([ -f "$WR/real/proj5/COORD.md" ] && echo y || echo n)" "y"

P15="$W/proj15"; mkdir -p "$P15/inner"; : > "$P15/README.md"
printf 'inner foundation\n' > "$P15/inner/real-claude.md"
ln -s "$WR/proj15/inner/real-claude.md" "$P15/CLAUDE.md"
est establish --root "$P15" > "$W/o" 2>&1; t "in-root symlinked CLAUDE.md → exit" "$?" "0"
t "the link SURVIVES (not replaced by a file)" \
  "$([ -L "$P15/CLAUDE.md" ] && echo link || echo regular)" "link"
t "the real file received the block" "$(nblk "$P15/inner/real-claude.md")" "1"
has "the real file kept its content" "inner foundation" "$P15/inner/real-claude.md"

mkdir -p "$W/outside"; printf 'OUTSIDE — must never change\n' > "$W/outside/CLAUDE.md"
OUT1="$(ckt "$W/outside/CLAUDE.md")"
P6="$W/proj6"; mkdir -p "$P6"; : > "$P6/README.md"; ln -s "$WR/outside/CLAUDE.md" "$P6/CLAUDE.md"
est establish --root "$P6" > "$W/o" 2>&1; t "escaping symlink → PARTIAL" "$?" "5"
has "escape is refused by name" "resolves outside" "$W/o"
t "the file outside the root is untouched" "$(ckt "$W/outside/CLAUDE.md")" "$OUT1"

echo "── F-12(g): ONE resolver — all four hooks source it and agree"

for h in session-start coord-nudge agent-ledger session-end; do
  if grep -q 'estate-root.sh' "$HOOKS_SRC/$h.sh"; then ok "$h.sh sources the shared resolver"
  else no "$h.sh sources the shared resolver — it has its own copy"; fi
done
ER="$W/hooks/estate-root.sh"
N2="$W/nogit2"; mkdir -p "$N2"; est establish --root "$N2" >/dev/null 2>&1
t "resolver adopts an established non-git project" \
  "$(cd "$N2" && bash "$ER")" "$(cd "$N2" && pwd -P)"
FH="$W/fakehome"; mkdir -p "$FH/Desktop/realproject" "$FH/Documents" "$FH/Downloads"
: > "$FH/README.md"; : > "$FH/Desktop/README.md"; : > "$FH/Desktop/realproject/README.md"
t "resolver refuses \$HOME" "$(cd "$FH" && HOME="$FH" bash "$ER")" ""
t "resolver refuses \$HOME/Desktop" "$(cd "$FH/Desktop" && HOME="$FH" bash "$ER")" ""
t "resolver refuses \$HOME/Documents" "$(cd "$FH/Documents" && HOME="$FH" bash "$ER")" ""
t "…but a project INSIDE Desktop is an ordinary root" \
  "$(cd "$FH/Desktop/realproject" && HOME="$FH" bash "$ER"; true)" ""
mkdir -p "$N2/sub/deeper"
t "resolver walks up to the COORD root" \
  "$(cd "$N2/sub/deeper" && bash "$ER")" "$(cd "$N2" && pwd -P)"
SUBP="$N2/subproject"; mkdir -p "$SUBP"; : > "$SUBP/README.md"
t "project boundary STOPS the walk (no adoption)" "$(cd "$SUBP" && bash "$ER")" ""
mkdir -p "$W/toodeep/a/b/c"; : > "$W/toodeep/COORD.md"
t "resolver stops at 3 levels" "$(cd "$W/toodeep/a/b/c" && bash "$ER")" ""

PAYLOAD='{"agent_id":"boundary-lane","transcript_path":"/nonexistent/agent-boundary-lane.jsonl"}'
( cd "$SUBP" && bash "$W/hooks/coord-nudge.sh" ) > "$W/o" 2>&1
t "boundary: coord-nudge silent" "$(wc -c < "$W/o" | tr -d ' ')" "0"
( cd "$SUBP" && printf '%s' "$PAYLOAD" | bash "$W/hooks/agent-ledger.sh" ) >/dev/null 2>&1
t "boundary: agent-ledger wrote no parent ledger" \
  "$([ -f "$N2/COORD-AGENTS.md" ] && echo wrote || echo none)" "none"
CB="$(ckt "$N2/COORD.md")"
( cd "$SUBP" && bash "$W/hooks/session-end.sh" < /dev/null ) >/dev/null 2>&1
t "boundary: session-end left the parent ledger alone" "$(ckt "$N2/COORD.md")" "$CB"
( cd "$SUBP" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
has "boundary: session-start says ESTABLISH HERE" "Say /notrest to establish" "$W/o"
hasnt "boundary: session-start claims no live ledger" "COORD.md is live" "$W/o"

echo "── round 2: N-1 unclosed fences · N-2 boundary shapes · N-4 encodings · N-5 well-knowns"

# N-1: an UNCLOSED fence must hide nothing. The old masker blanked to EOF, so the block
# went invisible and every run appended another one — unbounded.
P16="$W/proj16"; mkdir -p "$P16"; : > "$P16/README.md"
est establish --root "$P16" >/dev/null 2>&1
python3 - "$P16/CLAUDE.md" <<'PY2'
import sys
p = sys.argv[1]
old = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write("# Notes\n\n```sh\necho never closed\n\n" + old)
PY2
est check --root "$P16" > "$W/o" 2>&1; t "unclosed fence → check still finds the block" "$?" "0"
has "…and reports it at v1" "notrest:protocol block present at v1" "$W/o"
est establish --root "$P16" >/dev/null 2>&1
est establish --root "$P16" >/dev/null 2>&1
est establish --root "$P16" >/dev/null 2>&1
t "3x establish behind an unclosed fence → still ONE block" "$(nblk "$P16/CLAUDE.md")" "1"
has "the unclosed fence itself survives" 'echo never closed' "$P16/CLAUDE.md"

# N-1 belt-and-braces: raw text carries an opener the masked search missed → never append.
P17="$W/proj17"; mkdir -p "$P17"; : > "$P17/README.md"
{ printf '```text\n'
  printf '<!-- notrest:protocol v1 (managed by /notrest) -->\nbody\n<!-- /notrest:protocol -->\n'
  printf '```\n'; } > "$P17/CLAUDE.md"
K17="$(ckt "$P17/CLAUDE.md")"
est establish --root "$P17" > "$W/o" 2>&1; t "closed fenced example → refuses to append" "$?" "5"
t "CLOSED fenced example is still masked (F-3 regression guard)" \
  "$(grep -c 'notrest:protocol v1' "$P17/CLAUDE.md")" "1"
t "…and nothing was written past the disagreement" "$(ckt "$P17/CLAUDE.md")" "$K17"

# N-4: a UTF-16 CLAUDE.md is refused, not appended to.
P18="$W/proj18"; mkdir -p "$P18"; : > "$P18/README.md"
python3 -c "open('$P18/CLAUDE.md','wb').write('# UTF-16 foundation\n'.encode('utf-16'))"
K18="$(ckt "$P18/CLAUDE.md")"
est establish --root "$P18" > "$W/o" 2>&1; t "UTF-16 CLAUDE.md → PARTIAL" "$?" "5"
has "the WARN names the encoding" "not UTF-8 (UTF-16" "$W/o"
t "the UTF-16 file is byte-untouched" "$(ckt "$P18/CLAUDE.md")" "$K18"
est check --root "$P18" > "$W/o" 2>&1; t "UTF-16 → check also refuses" "$?" "5"

# N-5: the well-known home folders are refused by EXACT path; subdirectories are not.
HOME="$FH" est establish --root "$FH/Desktop" > "$W/o" 2>&1
t "--root \$HOME/Desktop → refused" "$?" "2"
has "the well-known refusal explains itself" "well-known home folder" "$W/o"
t "…and Desktop was left alone" "$([ -f "$FH/Desktop/COORD.md" ] && echo wrote || echo none)" "none"
HOME="$FH" est establish --root "$FH/Downloads" >/dev/null 2>&1
t "--root \$HOME/Downloads → refused" "$?" "2"
HOME="$FH" est establish --root "$FH/Desktop/realproject" >/dev/null 2>&1
t "a project INSIDE Desktop still establishes" "$?" "0"

# N-2: a CLAUDE.md-ONLY subproject is the ordinary Claude Code shape and must never be
# adopted by an established parent. Parent carries a ripe compile candidate to prove no
# leakage of the parent's estate into the child's session.
PAR="$W/parent"; mkdir -p "$PAR"; est establish --root "$PAR" >/dev/null 2>&1
mkdir -p "$PAR/compile"
printf '{"candidates":[{"slug":"parent-only-candidate","occurrences":9,"ripe":true,"status":"NEW"}]}\n' \
  > "$PAR/compile/candidates.json"
( cd "$PAR" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
has "parent itself DOES surface its ripe candidate" "parent-only-candidate" "$W/o"
for kid in claudeonly dotclaudeonly; do
  mkdir -p "$PAR/$kid"
done
: > "$PAR/claudeonly/CLAUDE.md"; mkdir -p "$PAR/dotclaudeonly/.claude"
t "CLAUDE.md-only subproject is a BOUNDARY" "$(cd "$PAR/claudeonly" && bash "$ER")" ""
t ".claude-only subproject is a BOUNDARY" "$(cd "$PAR/dotclaudeonly" && bash "$ER")" ""
( cd "$PAR/claudeonly" && bash "$W/hooks/coord-nudge.sh" ) > "$W/o" 2>&1
t "N-2: coord-nudge silent in the subproject" "$(wc -c < "$W/o" | tr -d ' ')" "0"
PCK="$(ckt "$PAR/COORD.md")"
( cd "$PAR/claudeonly" && printf '%s' "$PAYLOAD" | bash "$W/hooks/agent-ledger.sh" ) >/dev/null 2>&1
t "N-2: agent-ledger wrote no parent agent ledger" \
  "$([ -f "$PAR/COORD-AGENTS.md" ] && echo wrote || echo none)" "none"
t "N-2: no parent briefs/ dir was created" \
  "$([ -d "$PAR/briefs" ] && echo wrote || echo none)" "none"
( cd "$PAR/claudeonly" && bash "$W/hooks/session-end.sh" < /dev/null ) >/dev/null 2>&1
t "N-2: session-end left the parent ledger alone" "$(ckt "$PAR/COORD.md")" "$PCK"
( cd "$PAR/claudeonly" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
has "N-2: session-start says ESTABLISH HERE" "Say /notrest to establish" "$W/o"
hasnt "N-2: never tells it to read the PARENT ledger" "COORD.md is live" "$W/o"
hasnt "N-2: zero parent compile-candidate leakage" "parent-only-candidate" "$W/o"

# N-2: a DANGLING COORD.md is itself a boundary — never walked past to a distant ledger.
DNG="$PAR/dangling"; mkdir -p "$DNG"; ln -s "$WR/nowhere/COORD.md" "$DNG/COORD.md"
t "dangling COORD.md is a BOUNDARY (no adoption)" "$(cd "$DNG" && bash "$ER")" ""

echo "── hook closure: the git-gate holes the live failure fell through"

N1="$W/nogit1"; mkdir -p "$N1"; : > "$N1/README.md"
( cd "$N1" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "session-start (non-git, no COORD) exit" "$?" "0"
has "prints the establish nudge" "Say /notrest to establish the harness in this project" "$W/o"
t "auto-scaffolded NOTHING" "$([ -f "$N1/COORD.md" ] && echo scaffolded || echo none)" "none"
( cd "$FH" && HOME="$FH" bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
hasnt "session-start never nudges in \$HOME" "Say /notrest to establish" "$W/o"

( cd "$N2" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "session-start (non-git, COORD) exit" "$?" "0"
has "prints the live-ledger line" "COORD.md is live in this repo" "$W/o"
hasnt "does NOT re-print the establish nudge" "Say /notrest to establish" "$W/o"

( cd "$N2" && bash "$W/hooks/coord-nudge.sh" ) > "$W/o" 2>&1
t "coord-nudge (non-git, COORD) exit" "$?" "0"
has "coord-nudge fires" "append one honest ledger line" "$W/o"
( cd "$N1" && bash "$W/hooks/coord-nudge.sh" ) > "$W/o" 2>&1
t "coord-nudge stays silent without COORD" "$(wc -c < "$W/o" | tr -d ' ')" "0"

# F-12(f): the brief + spend legs, exercised on a NON-git root with a REAL transcript.
mkdir -p "$N2/spend"; printf '# ledger\n' > "$N2/spend/ledger.md"
TR="$W/agent-real-lane.jsonl"
{ printf '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"BRIEF: close the git-gate holes"}]}}\n'
  printf '{"type":"assistant","message":{"role":"assistant","model":"claude-opus-4","content":[{"type":"text","text":"done: holes closed"}],"usage":{"input_tokens":100,"output_tokens":50}}}\n'
} > "$TR"
P_REAL="{\"agent_id\":\"real-lane\",\"transcript_path\":\"$TR\"}"
( cd "$N2" && printf '%s' "$P_REAL" | bash "$W/hooks/agent-ledger.sh" ) > "$W/o" 2>&1
t "agent-ledger (non-git, real transcript) exit" "$?" "0"
t "agent-ledger is silent on stdout" "$(wc -c < "$W/o" | tr -d ' ')" "0"
t "COORD-AGENTS.md written outside git" "$([ -f "$N2/COORD-AGENTS.md" ] && echo y || echo n)" "y"
has "the agent line landed" "agent=real-lane" "$N2/COORD-AGENTS.md"
has "the line carries the scraped model" "model=claude-opus-4" "$N2/COORD-AGENTS.md"
t "the BRIEF was banked outside git" \
  "$([ -f "$N2/briefs/agent-real-lane.md" ] && echo y || echo n)" "y"
has "the brief holds the verbatim commission" "BRIEF: close the git-gate holes" "$N2/briefs/agent-real-lane.md"
has "COORD-AGENTS points at the brief" "brief: briefs/agent-real-lane.md" "$N2/COORD-AGENTS.md"
has "the spend receipt landed outside git" "agent=real-lane" "$N2/spend/ledger.md"
has "the receipt summed real usage" "tokens=150 grade=observed" "$N2/spend/ledger.md"
( cd "$N2" && printf '%s' "$P_REAL" | bash "$W/hooks/agent-ledger.sh" ) >/dev/null 2>&1
t "receipt is idempotent on redelivery" "$(grep -c 'agent=real-lane' "$N2/spend/ledger.md")" "1"
( cd "$N1" && printf '%s' "$P_REAL" | bash "$W/hooks/agent-ledger.sh" ) >/dev/null 2>&1
t "agent-ledger writes nothing without a root" "$([ -f "$N1/COORD-AGENTS.md" ] && echo y || echo n)" "n"

# F-6: an escaping COORD.md is never adopted, so no hook writes through it.
NX="$W/nogit-escape"; mkdir -p "$NX"; : > "$NX/README.md"
printf '# outside ledger\n\n## LEDGER\n' > "$W/outside/COORD.md"
OUTC="$(ckt "$W/outside/COORD.md")"
ln -s "$WR/outside/COORD.md" "$NX/COORD.md"
t "resolver SKIPS an escaping COORD.md" "$(cd "$NX" && bash "$ER")" ""
( cd "$NX" && bash "$W/hooks/session-end.sh" < /dev/null ) >/dev/null 2>&1
t "session-end wrote nothing through the escaping link" "$(ckt "$W/outside/COORD.md")" "$OUTC"
( cd "$NX" && printf '%s' "$P_REAL" | bash "$W/hooks/agent-ledger.sh" ) >/dev/null 2>&1
t "agent-ledger wrote nothing outside" \
  "$([ -f "$W/outside/COORD-AGENTS.md" ] && echo y || echo n)" "n"

( cd "$N2" && bash "$W/hooks/session-end.sh" < /dev/null ) > "$W/o" 2>&1
t "session-end (non-git, COORD) exit" "$?" "0"
has "cushion line appended" "auto-cushion" "$N2/COORD.md"

N3="$W/nogit3"; mkdir -p "$N3"; est establish --root "$N3" >/dev/null 2>&1
python3 - "$N3/COORD.md" <<'PY'
import sys
with open(sys.argv[1], "a", encoding="utf-8") as f:
    for i in range(501):
        f.write("- [2026-08-02 00:%02dZ] [fixture] line %d -> landed | evidence: fixture\n"
                % (i % 60, i))
PY
( cd "$N3" && bash "$W/hooks/session-end.sh" < /dev/null ) >/dev/null 2>&1
t "volume roll outside git seals COORD-001.md" \
  "$([ -f "$N3/COORD-001.md" ] && echo y || echo n)" "y"
has "fresh volume points at the sealed one" "Continues COORD-001.md" "$N3/COORD.md"

N4="$W/nogit4"; mkdir -p "$N4/inner"; : > "$N4/README.md"
python3 - "$N4/inner/real-coord.md" <<'PY'
import sys
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write("# COORD.md — session coordination ledger\n\nheader\n\n## LEDGER\n")
    for i in range(501):
        f.write("- [2026-08-02 00:%02dZ] [fixture] line %d -> landed | evidence: fixture\n"
                % (i % 60, i))
PY
ln -s "$WR/nogit4/inner/real-coord.md" "$N4/COORD.md"
( cd "$N4" && bash "$W/hooks/session-end.sh" < /dev/null ) >/dev/null 2>&1
t "in-root ledger link SURVIVES the roll" \
  "$([ -L "$N4/COORD.md" ] && echo link || echo regular)" "link"
has "the real ledger rolled" "Continues COORD-001.md" "$N4/inner/real-coord.md"
# N-3: /recap (walk.py) and /compile glob COORD-*.md at the ESTATE ROOT. Assert with the
# consumers' own pattern — a seal they cannot see is sealed history that vanished.
t "the seal is visible to the consumers' root glob" \
  "$(cd "$N4" && ls COORD-[0-9]*.md 2>/dev/null | wc -l | tr -d ' ')" "1"
t "no seal was hidden in the link target's dir" \
  "$(cd "$N4/inner" && ls COORD-[0-9]*.md 2>/dev/null | wc -l | tr -d ' ')" "0"
t "the continues-pointer resolves from the root" \
  "$([ -f "$N4/$(grep -o 'COORD-[0-9]*\.md' "$N4/inner/real-coord.md" | head -1)" ] && echo y || echo n)" "y"

echo "── regression: inside git, every hook behaves exactly as before"

G="$W/gitrepo"; mkdir -p "$G"; ( cd "$G" && git init -q ) >/dev/null 2>&1
( cd "$G" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "session-start (git, no COORD) exit" "$?" "0"
t "git repo IS auto-scaffolded" "$([ -f "$G/COORD.md" ] && echo y || echo n)" "y"
has "scaffold announces itself" "COORD.md created at the repo root" "$W/o"
has "hook scaffold carries the hook's own ledger line" "scaffolded by notrest SessionStart" "$G/COORD.md"
grep -v '^- \[' "$G/COORD.md" > "$W/hookscaffold"
grep -v '^- \[' "$P1/COORD.md" > "$W/estscaffold"
t "establish.py scaffold == session-start.sh scaffold" "$(ckt "$W/hookscaffold")" "$(ckt "$W/estscaffold")"
( cd "$G" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
has "git repo with COORD → live-ledger line" "COORD.md is live in this repo" "$W/o"
( cd "$G" && bash "$W/hooks/coord-nudge.sh" ) > "$W/o" 2>&1
has "coord-nudge still fires in git" "append one honest ledger line" "$W/o"
( cd "$G" && printf '%s' "$P_REAL" | bash "$W/hooks/agent-ledger.sh" ) >/dev/null 2>&1
has "agent-ledger still writes in git" "agent=real-lane" "$G/COORD-AGENTS.md"
( cd "$G" && bash "$W/hooks/session-end.sh" < /dev/null ) >/dev/null 2>&1
has "session-end still cushions in git" "auto-cushion" "$G/COORD.md"
G3="$W/gitrepo3"; mkdir -p "$G3"; ( cd "$G3" && git init -q ) >/dev/null 2>&1
ln -s "$WR/outside/DANGLING.md" "$G3/COORD.md"
( cd "$G3" && bash "$W/hooks/session-start.sh" ) >/dev/null 2>&1
t "escaping COORD link is never scaffolded through" \
  "$([ -f "$W/outside/DANGLING.md" ] && echo wrote || echo none)" "none"

echo
echo "fixture: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
