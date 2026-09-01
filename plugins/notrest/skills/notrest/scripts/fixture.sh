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
# gone. The READ-ONLY DIRECTORY arm is what kills that mutant today: a de-atomized
# open(w) SUCCEEDS on an existing writable file in an unwritable directory (opening an
# existing file for writing needs the file's bit, not the directory's), while mkstemp
# cannot — so the arm's "exit 6, no .notrest-*.tmp debris, target byte-untouched" holds
# only for the atomic path. (Its old partner — a read-only CLAUDE.md that tmp+replace
# overwrote — asserted the defect: 4.5 docket item 3 made that a REFUSAL, and the arm now
# asserts the refusal.) An assertion that cannot fail is decoration.
# Usage: bash <notrest-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
# HOST-SIGNAL HERMETICITY (4.5 docket item 1). detect_surface is decided by HOST SIGNALS,
# so a fixture that inherits its caller's host variables is a fixture whose surface arms
# depend on which runtime ran it. Every establish.py call below therefore runs with the
# Codex AND Claude signal variables stripped — the corpus runs on the documented
# no-signal default (claude), and an arm that wants a host STATES it on the command line.
unset CODEX_THREAD_ID CODEX_SANDBOX
CLEAR_HOST=""
for _v in $(env | sed -n 's/^\(CLAUDE[A-Za-z0-9_]*\)=.*/\1/p'); do CLEAR_HOST="$CLEAR_HOST -u $_v"; done
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
mode_of(){ python3 -c "import os,sys;print('%o' % (os.stat(sys.argv[1]).st_mode & 0o777))" "$1"; }
# An arm that WANTS a host states it in NR_HOST — a plain `CLAUDECODE=1 est …` prefix
# would be stripped again by CLEAR_HOST, since `env` applies its -u options before the
# assignments it is given. NR_HOST is applied AFTER the strip, so it is the only host the
# run sees, whatever the fixture's own caller was running under.
NR_HOST=""
# shellcheck disable=SC2086 — CLEAR_HOST/NR_HOST are token lists, split on purpose.
est(){ env $CLEAR_HOST ${NR_HOST:-} python3 "$EST" "$@"; }
pyest(){ env $CLEAR_HOST ${NR_HOST:-} python3 "$@"; }

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
has "block carries the Codex model map too" "gpt-5.6-sol" "$P1/CLAUDE.md"
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

echo "── establish.py: the Codex adapter"

PC="$W/proj-codex"; mkdir -p "$PC"; : > "$PC/README.md"
est establish --surface codex --root "$PC" > "$W/o" 2>&1
t "Codex establish → exit" "$?" "0"
t "Codex foundation is AGENTS.md" "$([ -f "$PC/AGENTS.md" ] && echo y || echo n)" "y"
t "Codex establish does not invent CLAUDE.md" "$([ -f "$PC/CLAUDE.md" ] && echo y || echo n)" "n"
has "Codex block is protocol v2" "notrest:protocol v2" "$PC/AGENTS.md"
has "Codex block pins the Codex worker" "gpt-5.6-sol" "$PC/AGENTS.md"
has "Codex block discloses the hook boundary" "Never claim a hook ran on Codex" "$PC/AGENTS.md"
PCK="$(ckt "$PC/AGENTS.md")"
est establish --surface codex --root "$PC" >/dev/null 2>&1
t "Codex establish is byte-idempotent" "$(ckt "$PC/AGENTS.md")" "$PCK"
est check --surface codex --root "$PC" > "$W/o" 2>&1
t "Codex check → established" "$?" "0"
has "Codex check names its surface" "AGENTS-BLOCK" "$W/o"

PA="$W/proj-auto-codex"; mkdir -p "$PA"; : > "$PA/README.md"
NR_HOST=CODEX_THREAD_ID=fixture-thread est establish --root "$PA" > "$W/o" 2>&1
# 4.5 docket item 5: this arm asserted exit 0 ONLY, and survived a killed codex branch in
# detect_surface (mutation-proven) — exit 0 is what the Claude adapter returns too. It now
# asserts the PROPERTY its two neighbours assert: which surface the run actually selected.
t "Codex runtime variable → establish exit" "$?" "0"
has "Codex runtime variable selects Codex automatically" "(surface=codex)" "$W/o"
t "…and the block landed in AGENTS.md" "$(nblk "$PA/AGENTS.md")" "1"
t "auto Codex wrote AGENTS.md" "$([ -f "$PA/AGENTS.md" ] && echo y || echo n)" "y"
t "auto Codex left CLAUDE.md absent" "$([ -f "$PA/CLAUDE.md" ] && echo y || echo n)" "n"

PB="$W/proj-both"; mkdir -p "$PB"; : > "$PB/README.md"
est establish --surface both --root "$PB" >/dev/null 2>&1
t "both adapter writes AGENTS.md" "$([ -f "$PB/AGENTS.md" ] && echo y || echo n)" "y"
t "both adapter writes CLAUDE.md" "$([ -f "$PB/CLAUDE.md" ] && echo y || echo n)" "y"
est check --surface both --root "$PB" > "$W/o" 2>&1
t "both adapter grades both foundations" "$?" "0"

echo "── 4.5 docket 1 · F2: HOST SIGNALS decide the runtime; files only narrow within one"

# Pre-fix, the Claude branch of detect_surface probed CLAUDE_PLUGIN_ROOT / CLAUDE_CONFIG_DIR
# — variables a real Claude session does NOT export — so that branch was DEAD and the FILE
# TIE-BREAK governed every `auto` run: a Claude session in a repo carrying an upstream
# AGENTS.md and no CLAUDE.md established the WRONG runtime's foundation and exited 0
# (confirmed live at the v4.3.0 ship). Owner ruling (a): host signals decide the runtime,
# files may only narrow WITHIN a detected host, and no signal → claude.
# REPAIR ROUND, refuter RA-3: the guard was ONE-DIRECTIONAL. It refused to create
# AGENTS.md for an undetected host — and then created CLAUDE.md over a codex-shaped repo
# without a word, which is the same wrong-runtime write in the other direction. With NO
# signal at all and AGENTS.md the ONLY foundation present, the honest move is to ASK.
F2A="$W/f2-upstream-agents"; mkdir -p "$F2A"; : > "$F2A/README.md"
printf '# upstream agents file\n' > "$F2A/AGENTS.md"; A2A="$(ckt "$F2A/AGENTS.md")"
est establish --root "$F2A" > "$W/o" 2>&1
t "no host signal + AGENTS.md is the ONLY foundation → refuses to guess" "$?" "2"
has "…and asks for the flag by name" "pass --surface codex|claude|both" "$W/o"
t "…no CLAUDE.md was invented over a codex-shaped repo" \
  "$([ -f "$F2A/CLAUDE.md" ] && echo wrote || echo none)" "none"
t "…and the upstream AGENTS.md is byte-untouched" "$(ckt "$F2A/AGENTS.md")" "$A2A"
t "…no COORD.md either — the refusal happens before any write" \
  "$([ -f "$F2A/COORD.md" ] && echo wrote || echo none)" "none"
est establish --surface claude --root "$F2A" > "$W/o" 2>&1
t "…and the operator's explicit answer is honoured" "$?" "0"
t "…creating exactly the surface they named" "$(nblk "$F2A/CLAUDE.md")" "1"

# REVIEW ROUND (2026-09-01) verdict, followed: the refusal is a WRITE-safety rule. The
# READ verbs grade what exists — an established codex estate must never get a usage
# error from its own drift check just because the environment is signal-less (cron/CI),
# and if the unverified CODEX vars are ever wrong, reads degrade to a report, never to
# silence. establish alone keeps the exit-2 ask.
F2AR="$W/f2-read-verbs"; mkdir -p "$F2AR"; : > "$F2AR/README.md"
est establish --surface codex --root "$F2AR" >/dev/null 2>&1
est check --root "$F2AR" > "$W/o" 2>&1
t "no signal: CHECK grades the codex estate instead of refusing" "$?" "0"
has "…with the ambiguity handed to the seat as a WARN" "WARN  SURFACE" "$W/o"
has "…grading the foundation that exists" "AGENTS-BLOCK" "$W/o"
est continuation --root "$F2AR" > "$W/o" 2>&1
t "no signal: CONTINUATION hands over the packet instead of refusing" "$?" "0"
has "…and the packet carries the surface warning" "# WARN surface:" "$W/o"

# The other two no-signal legs are UNCHANGED, and asserted so the refusal cannot creep:
# nothing present → the stated claude default still creates CLAUDE.md; both present →
# proceed on both blocks and create nothing.
F2A2="$W/f2-nosignal-bare"; mkdir -p "$F2A2"; : > "$F2A2/README.md"
est establish --root "$F2A2" > "$W/o" 2>&1
t "no signal + NO foundation → the claude default still establishes" "$?" "0"
has "…on the claude surface" "(surface=claude)" "$W/o"
F2A3="$W/f2-nosignal-both"; mkdir -p "$F2A3"; : > "$F2A3/README.md"
est establish --surface both --root "$F2A3" >/dev/null 2>&1
BA3="$(ckt "$F2A3/AGENTS.md")"; BC3="$(ckt "$F2A3/CLAUDE.md")"
est establish --root "$F2A3" > "$W/o" 2>&1
t "no signal + BOTH foundations present → proceeds, does not ask" "$?" "0"
has "…across both blocks" "(surface=both)" "$W/o"
has "…creating nothing" "wrote: nothing (already established)" "$W/o"
t "…and touching neither file" \
  "$(ckt "$F2A3/AGENTS.md")-$(ckt "$F2A3/CLAUDE.md")" "$BA3-$BC3"

# A DETECTED host outranks the files, in both directions.
F2B="$W/f2-claude-signal"; mkdir -p "$F2B"; : > "$F2B/README.md"
printf '# upstream agents file\n' > "$F2B/AGENTS.md"
NR_HOST=CLAUDECODE=1 est establish --root "$F2B" > "$W/o" 2>&1
has "CLAUDECODE=1 selects Claude in an AGENTS.md-only tree" "(surface=claude)" "$W/o"
t "…and CLAUDE.md is what it wrote" "$([ -f "$F2B/CLAUDE.md" ] && echo y || echo n)" "y"
F2C="$W/f2-claude-code-family"; mkdir -p "$F2C"; : > "$F2C/README.md"
printf '# upstream agents file\n' > "$F2C/AGENTS.md"
NR_HOST=CLAUDE_CODE_ENTRYPOINT=cli est establish --root "$F2C" > "$W/o" 2>&1
has "a CLAUDE_CODE_* variable is a Claude signal too" "(surface=claude)" "$W/o"
F2D="$W/f2-codex-signal"; mkdir -p "$F2D"; : > "$F2D/README.md"
printf '# their claude file\n' > "$F2D/CLAUDE.md"; K2D="$(ckt "$F2D/CLAUDE.md")"
NR_HOST=CODEX_THREAD_ID=fixture-thread est establish --root "$F2D" > "$W/o" 2>&1
has "a Codex signal outranks a CLAUDE.md-only tree" "(surface=codex)" "$W/o"
t "…and the CLAUDE.md it did not pick is byte-untouched" "$(ckt "$F2D/CLAUDE.md")" "$K2D"

# AMBIGUOUS host — both families signal. REPAIR ROUND, refuter RA-1: letting the files
# NARROW here resurrected F2 whole. CODEX_THREAD_ID is exported by a Codex session and
# INHERITED by everything that session ever launches, so a Claude seat started from a
# Codex shell carries a stale codex signal forever — and "narrow to the file we see" then
# handed an AGENTS.md-only repo straight back to the codex surface. The rule now: both
# signals means CLAUDE-PREFERRED, and the files may only WIDEN to `both` when both
# foundations already exist. They can never take the surface to codex-only.
F2E="$W/f2-ambiguous"; mkdir -p "$F2E"; : > "$F2E/README.md"
printf '# upstream agents file\n' > "$F2E/AGENTS.md"; E2E="$(ckt "$F2E/AGENTS.md")"
NR_HOST="CLAUDECODE=1 CODEX_THREAD_ID=stale" est establish --root "$F2E" > "$W/o" 2>&1
has "both signals + AGENTS.md only → claude-preferred, NOT narrowed to codex" \
  "(surface=claude)" "$W/o"
t "…CLAUDE.md is what a claude-preferred session wrote" "$(nblk "$F2E/CLAUDE.md")" "1"
t "…and the stale signal never touched the AGENTS.md" "$(ckt "$F2E/AGENTS.md")" "$E2E"
F2F="$W/f2-ambiguous-bare"; mkdir -p "$F2F"; : > "$F2F/README.md"
NR_HOST="CLAUDECODE=1 CODEX_THREAD_ID=stale" est establish --root "$F2F" > "$W/o" 2>&1
has "both signals + nothing to widen with → claude, not both" "(surface=claude)" "$W/o"
t "…so no AGENTS.md was invented for a stale signal" \
  "$([ -f "$F2F/AGENTS.md" ] && echo wrote || echo none)" "none"
F2H="$W/f2-ambiguous-widen"; mkdir -p "$F2H"; : > "$F2H/README.md"
est establish --surface both --root "$F2H" >/dev/null 2>&1
NR_HOST="CLAUDECODE=1 CODEX_THREAD_ID=stale" est establish --root "$F2H" > "$W/o" 2>&1
has "both signals + BOTH foundations present → files may WIDEN to both" "(surface=both)" "$W/o"
# The refuter's d7 shape: a different variable from each family, same law.
F2I="$W/f2-ambiguous-d7"; mkdir -p "$F2I"; : > "$F2I/README.md"
printf '# upstream agents file\n' > "$F2I/AGENTS.md"
NR_HOST="CLAUDE_CODE_ENTRYPOINT=cli CODEX_SANDBOX=seatbelt" est establish --root "$F2I" > "$W/o" 2>&1
has "…and the law holds whichever variable of each family signals" "(surface=claude)" "$W/o"

# THE WRITE GUARD (ruling (b), folded in): under `auto`, an undetected host never gets a
# foundation file CREATED for it. Asserted against the WRITER directly — detect_surface can
# no longer route there, and an invariant that holds only while its caller stays correct is
# not an invariant. Reads still grade whatever files exist (read-only honesty, unchanged).
F2G="$W/f2-guard"; mkdir -p "$F2G"; : > "$F2G/README.md"
t "auto + no Codex signal → AGENTS.md is never CREATED on a hunch" "$(pyest -c "
import sys, os, io, contextlib
sys.path.insert(0, os.path.dirname('$EST'))
import establish
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    establish.write_foundation('$F2G', 'codex', [], requested='auto')
print(('created' if os.path.exists('$F2G/AGENTS.md') else 'refused')
      + ('|names-the-flag' if '--surface codex' in buf.getvalue() else '|silent'))" 2>&1)" \
  "refused|names-the-flag"
t "…and an EXPLICIT --surface codex still creates it" \
  "$(est establish --surface codex --root "$F2G" >/dev/null 2>&1; nblk "$F2G/AGENTS.md")" "1"

# Review round (2026-09-01): a CREATED foundation honors the umask like open(w) would
# — mkstemp's 0600 made every fresh CLAUDE.md owner-only, unreadable to a teammate.
PMODE="$W/proj-createmode"; mkdir -p "$PMODE"; : > "$PMODE/README.md"
( umask 022 && est establish --root "$PMODE" >/dev/null 2>&1 )
t "a CREATED foundation honors the umask (022 → 644)" \
  "$(stat -f%Lp "$PMODE/CLAUDE.md" 2>/dev/null || stat -c%a "$PMODE/CLAUDE.md")" "644"

echo "── F-12(a): the hostile CLAUDE.md corpus"

P7="$W/proj7"; mkdir -p "$P7"; : > "$P7/README.md"
printf '# Windows project\r\n\r\nCaf\351 notes: r\351sum\351.\r\n' > "$P7/CLAUDE.md"
cp "$P7/CLAUDE.md" "$W/orig7"; OS7=$(wc -c < "$W/orig7" | tr -d ' ')
est establish --root "$P7" > "$W/o" 2>&1; t "CRLF+latin-1 CLAUDE.md → establish" "$?" "0"
head -c "$OS7" "$P7/CLAUDE.md" > "$W/pre7"
t "original bytes survive EXACTLY (CRLF + latin-1)" "$(ckt "$W/pre7")" "$(ckt "$W/orig7")"
t "CRLF count preserved" \
  "$(python3 -c "import sys;print(open(sys.argv[1],'rb').read().count(b'\\r'))" "$P7/CLAUDE.md")" "3"
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
hasnt "check never claims the example IS the block" "block present at v2" "$W/o"
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
has "block upgraded to v2" "notrest:protocol v2" "$P3/CLAUDE.md"
hasnt "stale body gone" "stale body" "$P3/CLAUDE.md"
has "text above the block survives" "TOP LINE" "$P3/CLAUDE.md"
has "text below the block survives" "BOTTOM LINE" "$P3/CLAUDE.md"
has "in-block edits announced, not silent" "in-block edits discarded" "$W/o"
t "the discarded body was banked" \
  "$([ -f "$P3/CLAUDE.md.notrest-v0.bak" ] && echo y || echo n)" "y"
has "the backup holds the old body" "stale body WITH A HAND EDIT" "$P3/CLAUDE.md.notrest-v0.bak"

echo "── F-12(b): atomicity, proven by a mutant that would survive without it"

# 4.5 docket item 3 (F4). This arm asserted the OLD contract — that tmp+os.replace WINS
# over a read-only target, since os.replace needs the DIRECTORY bit and not the file's.
# Winning there IS the defect: the owner marked the file read-only and the tool rewrote it
# anyway (and reset its mode to 0600 on the way through). The refusal is the contract now.
P11="$W/proj11"; mkdir -p "$P11"; : > "$P11/README.md"
printf 'read-only foundation\n' > "$P11/CLAUDE.md"; chmod 444 "$P11/CLAUDE.md"
K11="$(ckt "$P11/CLAUDE.md")"
est establish --root "$P11" > "$W/o" 2>&1
t "read-only CLAUDE.md → REFUSED, not rewritten" "$?" "5"
has "the refusal names the read-only target and its mode" "is read-only (mode 0444)" "$W/o"
has "…and the tail counts it as a failed write" "writes failed: CLAUDE.md" "$W/o"
t "the read-only file is byte-untouched" "$(ckt "$P11/CLAUDE.md")" "$K11"
t "…and its MODE is untouched too" "$(mode_of "$P11/CLAUDE.md")" "444"
has "its original line survives" "read-only foundation" "$P11/CLAUDE.md"
chmod 644 "$P11/CLAUDE.md"

# REPAIR ROUND, refuter RA-4: the backup-failure branch ABANDONS the upgrade it was asked
# to make and said so in a WARN — but never counted it, so the tail read `wrote: COORD.md`
# with no mention that the block it came for was left at v1.
F4B="$W/f4-bak"; mkdir -p "$F4B"; : > "$F4B/README.md"
{ printf '# CLAUDE.md\n\n<!-- notrest:protocol v1 (managed by /notrest) -->\nhand edited\n'
  printf '<!-- /notrest:protocol -->\n'; } > "$F4B/CLAUDE.md"
KF4B="$(ckt "$F4B/CLAUDE.md")"
printf 'old\n' > "$F4B/CLAUDE.md.notrest-v1.bak"; chmod 444 "$F4B/CLAUDE.md.notrest-v1.bak"
est establish --root "$F4B" > "$W/o" 2>&1
t "read-only stale .bak → the upgrade is abandoned, PARTIAL" "$?" "5"
has "…the WARN still explains itself" "the backup failed" "$W/o"
has "…and the tail now says a write FAILED" "writes failed: CLAUDE.md" "$W/o"
t "…the v1 block is left exactly as it was" "$(ckt "$F4B/CLAUDE.md")" "$KF4B"
t "…and the stale backup was not overwritten" "$(cat "$F4B/CLAUDE.md.notrest-v1.bak")" "old"
chmod 644 "$F4B/CLAUDE.md.notrest-v1.bak"

# The other half of F4: a WRITABLE target keeps the mode its owner gave it. mkstemp
# creates 0600, so pre-fix every foundation file this tool rewrote came back 0600 — a
# silent re-permissioning of somebody else's file.
F4M="$W/f4-mode"; mkdir -p "$F4M"; : > "$F4M/README.md"
printf 'their foundation\n' > "$F4M/CLAUDE.md"; chmod 640 "$F4M/CLAUDE.md"
est establish --root "$F4M" > "$W/o" 2>&1; t "append into a mode-0640 foundation → exit" "$?" "0"
t "the target's MODE survives the atomic replace" "$(mode_of "$F4M/CLAUDE.md")" "640"
t "…and the block still landed" "$(nblk "$F4M/CLAUDE.md")" "1"
has "…and the original content survives" "their foundation" "$F4M/CLAUDE.md"
hasnt "no message claims the FILE was untouched when it was replaced" "content untouched" "$W/o"
has "…it says what actually happened instead" "preserved byte for byte" "$W/o"

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
has "non-git WARN: self-update" "WARN  GIT-DEGRADED  — automatic self-update is unavailable" "$W/o"
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

echo "── 4.5 docket 2 · F3: the REPORT never escapes the root, and the tail never lies"

# The write containment always held; the REPORT did not. foundation_state() followed the
# escaping link, so a foundation living OUTSIDE the estate graded PASS — and grade()
# ignored `failures`, so a run with a REFUSED write printed
# `ESTABLISHED · wrote: nothing (writes failed: AGENTS.md) · exit 0`: a PASS asserted from
# a file the estate does not own, exit 0 on a refused write, and a `wrote:` tail that was
# false about the writes that DID land.
F3SRC="$W/f3-src"; mkdir -p "$F3SRC"; : > "$F3SRC/README.md"
est establish --surface codex --root "$F3SRC" >/dev/null 2>&1
cp "$F3SRC/AGENTS.md" "$W/outside/AGENTS.md"; OUTA="$(ckt "$W/outside/AGENTS.md")"
F3="$W/f3-escape"; mkdir -p "$F3"; : > "$F3/README.md"
ln -s "$WR/outside/AGENTS.md" "$F3/AGENTS.md"
est establish --surface both --root "$F3" > "$W/o" 2>&1
t "escaping AGENTS.md carrying a VALID block outside → never exit 0" "$?" "5"
hasnt "…and never prints a clean ESTABLISHED verdict" "notrest: ESTABLISHED" "$W/o"
has "…the READ side refuses the escape too" "refusing to READ" "$W/o"
has "…the tail names the write that failed" "writes failed: AGENTS.md" "$W/o"
has "…and still tells the truth about what it DID write" "wrote: COORD.md, CLAUDE.md" "$W/o"
hasnt "…so a partial run never reports 'wrote: nothing'" "wrote: nothing" "$W/o"
t "…the file outside the root is byte-untouched" "$(ckt "$W/outside/AGENTS.md")" "$OUTA"
est check --surface both --root "$F3" > "$W/o" 2>&1
t "check refuses to grade a foundation from outside the root" "$?" "5"
est continuation --surface both --root "$F3" > "$W/o" 2>&1
t "continuation is not CONTINUABLE off an out-of-root foundation" "$?" "6"
# The grade leg on its own: states can be all-PASS and the run still be a failure.
t "grade() refuses to say ESTABLISHED while a write failed" "$(pyest -c "
import sys, os
sys.path.insert(0, os.path.dirname('$EST'))
import establish
print(establish.grade([establish.PASS, establish.PASS], ['AGENTS.md']))" 2>&1)" "5"

# REPAIR ROUND, refuter RA-2: the FOUNDATION read was contained, but every OTHER estate
# read was not. An escaping COORD.md let `check` grade another project's ledger PASS and
# `continuation` hand a successor seat a stranger's trail as this project's own history.
F3C="$W/f3-coord-escape"; mkdir -p "$F3C"; : > "$F3C/README.md"
DONOR="$W/donor-estate/donor"; mkdir -p "$DONOR"; : > "$DONOR/README.md"
est establish --root "$DONOR" >/dev/null 2>&1
{ echo "- [2026-08-01 09:00Z] [donor] someone else's work -> v9.9.9 shipped | evidence: not ours"
  echo "- [2026-08-02 09:00Z] [donor] more of it -> landed | evidence: not ours"; } >> "$DONOR/COORD.md"
DONORCK="$(ckt "$DONOR/COORD.md")"
cp "$DONOR/CLAUDE.md" "$F3C/CLAUDE.md"
ln -s "$WR/donor-estate/donor/COORD.md" "$F3C/COORD.md"
est check --root "$F3C" > "$W/o" 2>&1
t "escaping COORD.md → check is not a PASS" "$?" "5"
has "…the COORD finding names the escape" "resolves outside" "$W/o"
hasnt "…and never grades a stranger's ledger as this project's" "COORD.md present with the ledger header" "$W/o"
hasnt "…nor counts their ledger lines as adoption" "2 ledger line(s) beyond the scaffold" "$W/o"
est continuation --root "$F3C" > "$W/o" 2>&1
t "escaping COORD.md → NOT CONTINUABLE" "$?" "6"
has "…and the refusal names the boundary" "resolves outside" "$W/o"
hasnt "…the successor is never handed the donor's ships" "v9.9.9 shipped" "$W/o"
est establish --root "$F3C" > "$W/o" 2>&1
t "escaping COORD.md → establish refuses to write through it" "$?" "5"
t "…and the donor's ledger is byte-untouched" "$(ckt "$DONOR/COORD.md")" "$DONORCK"
# The same law for the other estate reads a packet makes.
F3D="$W/f3-agentledger-escape"; mkdir -p "$F3D"; : > "$F3D/README.md"
est establish --root "$F3D" >/dev/null 2>&1
printf '# COORD-AGENTS.md\n\n## LEDGER\n- [2026-08-04 12:01Z] agent=stranger | last: done\n' \
  > "$W/donor-estate/COORD-AGENTS.md"
ln -s "$WR/donor-estate/COORD-AGENTS.md" "$F3D/COORD-AGENTS.md"
mkdir -p "$W/donor-estate/spend"; printf '# ledger\nlane=stranger tokens=999 grade=observed\n' \
  > "$W/donor-estate/spend/ledger.md"
ln -s "$WR/donor-estate/spend" "$F3D/spend"
est continuation --root "$F3D" > "$W/o" 2>&1
t "…continuation still works with escaping side-ledgers" "$?" "0"
hasnt "…but never reads the stranger's agent tail" "agent=stranger" "$W/o"
hasnt "…nor their spend line" "tokens=999" "$W/o"

echo "── 4.5 docket 6 · F6: the hostile corpus, cloned for AGENTS.md"

# The F-12(a) corpus ran against CLAUDE.md only, and findings F3/F4 above sat in exactly
# that gap. Same shapes, same laws, the Codex surface.
A7="$W/agents-crlf"; mkdir -p "$A7"; : > "$A7/README.md"
printf '# Windows project\r\n\r\nCaf\351 notes: r\351sum\351.\r\n' > "$A7/AGENTS.md"
cp "$A7/AGENTS.md" "$W/origA7"; OSA7=$(wc -c < "$W/origA7" | tr -d ' ')
est establish --surface codex --root "$A7" > "$W/o" 2>&1
t "CRLF+latin-1 AGENTS.md → establish" "$?" "0"
head -c "$OSA7" "$A7/AGENTS.md" > "$W/preA7"
t "AGENTS.md original bytes survive EXACTLY (CRLF + latin-1)" "$(ckt "$W/preA7")" "$(ckt "$W/origA7")"
t "AGENTS.md CRLF count preserved" \
  "$(python3 -c "import sys;print(open(sys.argv[1],'rb').read().count(b'\\r'))" "$A7/AGENTS.md")" "3"
t "no U+FFFD written into AGENTS.md" \
  "$(grep -c $'\xef\xbf\xbd' "$A7/AGENTS.md" 2>/dev/null || true)" "0"
t "the AGENTS.md block still landed" "$(nblk "$A7/AGENTS.md")" "1"

A8="$W/agents-fenced"; mkdir -p "$A8"; : > "$A8/README.md"
{ printf '# Docs\n\nHere is what the block looks like:\n\n'
  printf '```markdown\n'
  printf '<!-- notrest:protocol v1 (do not edit inside markers; managed by /notrest) -->\n'
  printf 'example body\n'
  printf '<!-- /notrest:protocol -->\n'
  printf '```\n'; } > "$A8/AGENTS.md"
KA8="$(ckt "$A8/AGENTS.md")"
est check --surface codex --root "$A8" > "$W/o" 2>&1
t "fenced EXAMPLE in AGENTS.md is not the block → check" "$?" "5"
has "…and names the fence/mask disagreement" "inside a fenced/masked region" "$W/o"
est establish --surface codex --root "$A8" > "$W/o" 2>&1
t "fenced example in AGENTS.md → establish appends NOTHING" "$?" "5"
t "…the fenced example survives byte-for-byte" "$(ckt "$A8/AGENTS.md")" "$KA8"

A9="$W/agents-stray"; mkdir -p "$A9"; : > "$A9/README.md"
{ printf '<!-- notrest:protocol v1 (do not edit inside markers; managed by /notrest) -->\n'
  printf '\nIRREPLACEABLE USER CONTENT\n\n'
  printf '<!-- notrest:protocol v0 (do not edit inside markers; managed by /notrest) -->\n'
  printf 'old body\n'
  printf '<!-- /notrest:protocol -->\n'; } > "$A9/AGENTS.md"
KA9="$(ckt "$A9/AGENTS.md")"
est establish --surface codex --root "$A9" > "$W/o" 2>&1
t "stray open marker in AGENTS.md → establish refuses" "$?" "5"
has "…names the ambiguity" "multiple/ambiguous protocol markers" "$W/o"
t "…and the file is byte-untouched" "$(ckt "$A9/AGENTS.md")" "$KA9"
has "…USER CONTENT survives" "IRREPLACEABLE USER CONTENT" "$A9/AGENTS.md"

A10="$W/agents-dup"; mkdir -p "$A10"; : > "$A10/README.md"
{ printf '<!-- notrest:protocol v0 (managed by /notrest) -->\nfirst\n<!-- /notrest:protocol -->\n'
  printf '\nmiddle\n\n'
  printf '<!-- notrest:protocol v1 (managed by /notrest) -->\nsecond\n<!-- /notrest:protocol -->\n'; } > "$A10/AGENTS.md"
KA10="$(ckt "$A10/AGENTS.md")"
est check --surface codex --root "$A10" > "$W/o" 2>&1
t "duplicate blocks in AGENTS.md → check" "$?" "5"
has "…names the shape" "duplicate protocol blocks" "$W/o"
est establish --surface codex --root "$A10" > "$W/o" 2>&1
t "duplicate blocks in AGENTS.md → establish refuses" "$?" "5"
t "…and the file is byte-untouched" "$(ckt "$A10/AGENTS.md")" "$KA10"

A11="$W/agents-unterminated"; mkdir -p "$A11"; : > "$A11/README.md"
{ printf '# theirs\n\n'
  printf '<!-- notrest:protocol v1 (managed by /notrest) -->\nbody with no closer\n'; } > "$A11/AGENTS.md"
KA11="$(ckt "$A11/AGENTS.md")"
est check --surface codex --root "$A11" > "$W/o" 2>&1
t "unterminated block in AGENTS.md → check is PARTIAL" "$?" "5"
has "…and says the block never closes" "unterminated" "$W/o"
est establish --surface codex --root "$A11" > "$W/o" 2>&1
t "unterminated block in AGENTS.md → establish leaves it alone" "$?" "5"
has "…and names the by-hand repair" "close the marker by hand" "$W/o"
t "…the file is byte-untouched" "$(ckt "$A11/AGENTS.md")" "$KA11"

printf 'OUTSIDE AGENTS — must never change\n' > "$W/outside/PLAIN-AGENTS.md"
OUTA2="$(ckt "$W/outside/PLAIN-AGENTS.md")"
A12="$W/agents-escape"; mkdir -p "$A12"; : > "$A12/README.md"
ln -s "$WR/outside/PLAIN-AGENTS.md" "$A12/AGENTS.md"
est establish --surface codex --root "$A12" > "$W/o" 2>&1
t "escaping AGENTS.md symlink → PARTIAL" "$?" "5"
has "…the escape is refused by name" "resolves outside" "$W/o"
t "…and the file outside the root is untouched" "$(ckt "$W/outside/PLAIN-AGENTS.md")" "$OUTA2"

A13="$W/agents-readonly"; mkdir -p "$A13"; : > "$A13/README.md"
printf 'read-only agents foundation\n' > "$A13/AGENTS.md"; chmod 444 "$A13/AGENTS.md"
KA13="$(ckt "$A13/AGENTS.md")"
est establish --surface codex --root "$A13" > "$W/o" 2>&1
t "read-only AGENTS.md → REFUSED, not rewritten" "$?" "5"
has "…the refusal names the mode" "is read-only (mode 0444)" "$W/o"
t "…the read-only AGENTS.md is byte-untouched" "$(ckt "$A13/AGENTS.md")" "$KA13"
chmod 644 "$A13/AGENTS.md"

A14="$W/agents-utf16"; mkdir -p "$A14"; : > "$A14/README.md"
python3 -c "open('$A14/AGENTS.md','wb').write('# UTF-16 foundation\n'.encode('utf-16'))"
KA14="$(ckt "$A14/AGENTS.md")"
est establish --surface codex --root "$A14" > "$W/o" 2>&1
t "UTF-16 AGENTS.md → PARTIAL" "$?" "5"
has "…the WARN names the encoding" "not UTF-8 (UTF-16" "$W/o"
t "…the UTF-16 file is byte-untouched" "$(ckt "$A14/AGENTS.md")" "$KA14"
est check --surface codex --root "$A14" > "$W/o" 2>&1
t "UTF-16 AGENTS.md → check also refuses" "$?" "5"

# A PARTIAL `both` run: one surface lands, the other is refused, and the verdict says
# WHICH — on the same screen, with a tail that names what was actually written.
A15="$W/agents-partial-both"; mkdir -p "$A15"; : > "$A15/README.md"
python3 -c "open('$A15/AGENTS.md','wb').write('# UTF-16 foundation\n'.encode('utf-16'))"
KA15="$(ckt "$A15/AGENTS.md")"
est establish --surface both --root "$A15" > "$W/o" 2>&1
t "partial both run (hostile AGENTS.md, clean CLAUDE.md) → PARTIAL" "$?" "5"
t "…the Claude half landed" "$(nblk "$A15/CLAUDE.md")" "1"
t "…the hostile AGENTS.md is byte-untouched" "$(ckt "$A15/AGENTS.md")" "$KA15"
has "…the tail names what it wrote" "wrote: COORD.md, CLAUDE.md" "$W/o"
has "…and the verdict names the unfinished surface" "AGENTS-BLOCK" "$W/o"

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
has "…and reports it at v2" "notrest:protocol block present at v2" "$W/o"
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

# N-5b (refuter F1, 2026-08-21): a dot config dir directly under $HOME is refused even
# when it carries a marker — ~/.codex/AGENTS.md is Codex's machine-wide instruction file,
# and pre-fix the new AGENTS.md marker made it an establishable root.
mkdir -p "$FH/.codex"; printf '# codex global\n' > "$FH/.codex/AGENTS.md"
HOME="$FH" est establish --root "$FH/.codex" > "$W/o" 2>&1
t "--root \$HOME/.codex → refused despite its AGENTS.md marker" "$?" "2"
has "the config-dir refusal explains itself" "dot-directory directly under your HOME" "$W/o"
t "…and nothing was written into ~/.codex" "$(cd "$FH/.codex" && ls | sort | tr '\n' ' ')" "AGENTS.md "
mkdir -p "$FH/.claude"; printf '# global\n' > "$FH/.claude/CLAUDE.md"
HOME="$FH" est establish --root "$FH/.claude" >/dev/null 2>&1
t "--root \$HOME/.claude → refused despite its CLAUDE.md marker" "$?" "2"
t "…and nothing was written into ~/.claude" "$(cd "$FH/.claude" && ls | sort | tr '\n' ' ')" "CLAUDE.md "

# N-5c (review-the-fix, 2026-08-21): the refusal must hold on the LEXICAL path too — a dot
# dir under $HOME that is a symlink out of HOME (the dotfiles-manager shape) is still
# ~/.codex to every tool that loads it, wherever its realpath lands.
mkdir -p "$FH/outside-dots/codexdir"; printf '# managed\n' > "$FH/outside-dots/codexdir/AGENTS.md"
ln -sfn "$FH/outside-dots/codexdir" "$FH/.codexlink"
HOME="$FH" est establish --root "$FH/.codexlink" > "$W/o" 2>&1
t "a dot dir symlinked OUT of HOME is still refused" "$?" "2"
t "…and the symlink target was left alone" "$(cd "$FH/outside-dots/codexdir" && ls | sort | tr '\n' ' ')" "AGENTS.md "
# …and the refusal survives ANCESTOR ALIASING (a symlinked $HOME / the macOS /var →
# /private/var shape): parent realpath'd, leaf judged as named.
mkdir -p "$FH/rh" "$FH/outside2/cdir"; printf '# managed\n' > "$FH/outside2/cdir/AGENTS.md"
ln -sfn "$FH/rh" "$FH/rhlink"
ln -sfn "$FH/outside2/cdir" "$FH/rh/.codexlink"
HOME="$FH/rhlink" est establish --root "$FH/rhlink/.codexlink" > "$W/o" 2>&1
t "…even when \$HOME itself is reached through a symlink alias" "$?" "2"
t "…and that aliased-route target was left alone" "$(cd "$FH/outside2/cdir" && ls | sort | tr '\n' ' ')" "AGENTS.md "
# HOME set-but-empty (launchd/CI shells) must not disable the home refusals. Only the
# REAL home demonstrates this (a fake HOME is invisible once the env var is blank), so the
# probe is resolve_root() only — pure resolution, no writes, against the pwd-derived home.
t "HOME='' still refuses the real \$HOME (pwd fallback)" "$(env HOME= python3 -c "
import sys, os, pwd
sys.path.insert(0, os.path.dirname('$EST'))
import establish
root, err = establish.resolve_root(pwd.getpwuid(os.getuid()).pw_dir)
print('refused' if err else 'established')" 2>&1)" "refused"

# 4.5 docket item 4: the whole home-refusal family compared STRINGS, so on a
# case-insensitive volume (macOS default) `--root /users/me` walked straight past $HOME,
# past Desktop/Documents/Downloads and past the dot-dir refusal — the same directory,
# spelled differently. The family now compares INODES (os.path.samefile, guarded for
# existence); the dot-LEAF stays lexical, because the leaf's own symlink is exactly what
# must not be followed before judging it.
# The arms adapt to the volume they run on: where the alt-case spelling IS the same
# directory the refusal must name the reason; on a case-sensitive volume it is simply a
# path that does not exist, and the arm says so rather than pretending to prove identity.
: > "$W/caseprobe"
if [ -e "$W/CASEPROBE" ]; then CI=yes; CIWHY="HOME directory, not a project"; CIWK="well-known home folder"; CIDOT="dot-directory directly under your HOME"
else CI=no; CIWHY="is not a directory"; CIWK="is not a directory"; CIDOT="is not a directory"; fi
rm -f "$W/caseprobe"
swapcase(){ python3 -c "import sys;print(sys.argv[1].swapcase())" "$1"; }

# REPAIR ROUND, refuter RA-P: the home family was derived from $HOME, so exporting HOME
# elsewhere — a harness, a launchd job, a plain `env HOME=… claude` — left the REAL
# account home completely unprotected, and that is the one directory whose CLAUDE.md is
# loaded into every session on the machine. The account home now comes from the password
# database ALWAYS, and a root matching EITHER home is refused.
# ⛔ These arms call resolve_root() ONLY — pure resolution, no writes, nothing created.
# Nothing in this fixture may ever run `establish` against the real home.
ACCT="$(python3 -c "import os,pwd;print(os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir))")"
rr(){ pyest -c "
import sys, os
sys.path.insert(0, os.path.dirname('$EST'))
import establish
root, err = establish.resolve_root(sys.argv[1])
print('refused' if err else 'RESOLVED')" "$1" 2>&1; }
mkdir -p "$W/not-my-home"
t "HOME exported elsewhere → the ACCOUNT home is STILL refused" \
  "$(HOME="$W/not-my-home" rr "$ACCT")" "refused"
t "…its well-known folders too" \
  "$(HOME="$W/not-my-home" rr "$ACCT/Desktop")" "refused"
t "…and its dot-directories" \
  "$(HOME="$W/not-my-home" rr "$ACCT/.claude")" "refused"
t "…while an ordinary project still resolves (no over-refusal)" \
  "$(HOME="$W/not-my-home" rr "$P1")" "RESOLVED"
t "…and the redirected HOME is refused as well — BOTH homes hold" \
  "$(HOME="$W/not-my-home" rr "$W/not-my-home")" "refused"
FHC="$W/fakehome-case"; mkdir -p "$FHC/Desktop" "$FHC/.codex"
: > "$FHC/README.md"; printf '# codex global\n' > "$FHC/.codex/AGENTS.md"
HOME="$FHC" est establish --root "$(swapcase "$FHC")" > "$W/o" 2>&1
t "case-variant \$HOME → refused (case-insensitive volume: $CI)" "$?" "2"
has "…and the refusal names the reason this volume gives" "$CIWHY" "$W/o"
HOME="$FHC" est establish --root "$(swapcase "$FHC")/Desktop" > "$W/o" 2>&1
t "case-variant \$HOME/Desktop → refused" "$?" "2"
has "…named" "$CIWK" "$W/o"
HOME="$FHC" est establish --root "$(swapcase "$FHC")/.codex" > "$W/o" 2>&1
t "case-variant \$HOME/.codex → refused" "$?" "2"
has "…named" "$CIDOT" "$W/o"
# NOT a directory-entry count: pointing $HOME at a sandbox makes macOS create ~/Library
# under it the first time anything runs there, and an arm that reds on the OS's own
# housekeeping teaches people to ignore it. Assert what THIS TOOL wrote instead.
t "…and no foundation or ledger was written anywhere in the aliased home" \
  "$(ls -A "$FHC" "$FHC/Desktop" "$FHC/.codex" 2>/dev/null \
     | grep -c -E '^(COORD\.md|CLAUDE\.md)$' || true)" "0"
t "…no COORD.md was written through the alias" \
  "$([ -f "$FHC/COORD.md" ] || [ -f "$FHC/Desktop/COORD.md" ] || [ -f "$FHC/.codex/COORD.md" ] \
    && echo wrote || echo none)" "none"

# N-2: a CLAUDE.md-ONLY subproject is the ordinary Claude Code shape and must never be
# adopted by an established parent. Parent carries a ripe compile candidate to prove no
# leakage of the parent's estate into the child's session.
# Scaffolded BY HAND, not via `est establish`: establish fires seed_pulse(), whose
# DETACHED estate-pulse.sh runs a real compile scan that races the hand-written
# candidates.json below (latent flake found 2026-09-01 while building the auto-build
# arms — this arm won the race only because it runs the hook once, promptly).
PAR="$W/parent"; mkdir -p "$PAR"
printf '# COORD.md — session coordination ledger\n\n## LEDGER\n' > "$PAR/COORD.md"
printf '# parent project\n' > "$PAR/README.md"
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

echo "── v3.20.0: the cockpit always-on nudge (surfacing, not doing)"

# Ports here are deliberately NOT 8788 (the owner's real cockpit) and not 8790-8799
# (render-check's range): this fixture must never collide with a window someone is using.
CKN="$W/cockpit-nogit"; mkdir -p "$CKN"; est establish --root "$CKN" >/dev/null 2>&1
( cd "$CKN" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "cockpit nudge: hook still exits 0 with no marker" "$?" "0"
hasnt "no marker → session-start says nothing about a cockpit" "Cockpit is opted always-on" "$W/o"

mkdir -p "$CKN/graph"; printf '{"port":8123}\n' > "$CKN/graph/.cockpit-always"
# Port 8123 is a shared machine resource (an unrelated dev server held it on 2026-08-21
# and turned this arm red) — so the no-server assertion below is a DELTA, not an absolute:
# capture the port's state before the hook runs, and assert the hook left it unchanged.
PRE_LISTEN="$(python3 -c "
import socket
s = socket.socket(); s.settimeout(0.4)
try:
    s.connect(('127.0.0.1', 8123)); print('listening')
except Exception:
    print('none')
finally:
    s.close()")"
( cd "$CKN" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "cockpit nudge: hook exits 0 with a marker" "$?" "0"
has "marker at a NON-GIT COORD root → the nudge fires" \
  "Cockpit is opted always-on here (port 8123)" "$W/o"
has "the nudge points at the built-in browser pane" "built-in browser pane" "$W/o"
has "the nudge names the probe verb" "cockpit.py status" "$W/o"

CKG="$W/cockpit-git"; mkdir -p "$CKG/graph"; ( cd "$CKG" && git init -q ) >/dev/null 2>&1
printf '{"port":8124}\n' > "$CKG/graph/.cockpit-always"
( cd "$CKG" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
has "marker at a GIT root → the nudge fires too" \
  "Cockpit is opted always-on here (port 8124)" "$W/o"

# A SessionStart hook must not do work: one echo, no probe, no spawn, no opener.
# Asserted as post==pre so an unrelated process already holding the port cannot red this
# arm — the hook's obligation is to CHANGE nothing, not to guarantee a quiet machine.
t "the nudge started NO server on the opted port (post==pre)" \
  "$(python3 -c "
import socket
s = socket.socket(); s.settimeout(0.4)
try:
    s.connect(('127.0.0.1', 8123)); print('listening')
except Exception:
    print('none')
finally:
    s.close()")" "$PRE_LISTEN"

for BADMARK in 'garbage{' '{\"port\":\"not-a-number\"}' '{\"port\":0}' '{}' ''; do
  printf '%s' "$BADMARK" > "$CKN/graph/.cockpit-always"
  ( cd "$CKN" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
  hasnt "malformed marker [$BADMARK] keeps the hook silent" "Cockpit is opted always-on" "$W/o"
done
rm -f "$CKN/graph/.cockpit-always"

echo "── v4.5: the auto-build standing authorization (owner-private, out of the repo)"

# v4.5 (docket 8c): the marker moved OUT of the estate — an in-repo file is writable by
# any lane and travels with a clone. Authorization now lives at
# ${NOTREST_HOME:-~/.notrest}/auto-build/<sha256-of-estate-realpath>.json, and the hook
# ignores the legacy in-repo path with a one-line migration note. These arms run against
# a SANDBOX store: NOTREST_HOME is exported so the real ~/.notrest is never read/written.
# A git root, NOT `est establish`: establish.py fires a DETACHED pulse refresher that
# would race the synthetic candidates.json.
export NOTREST_HOME="$W/nrhome"
AB="$W/autobuild"; mkdir -p "$AB/compile"; ( cd "$AB" && git init -q ) >/dev/null 2>&1
printf '{"candidates":[{"slug":"release-ritual","occurrences":7,"ripe":true,"status":"NEW"}]}\n' \
  > "$AB/compile/candidates.json"
# Arg-count decides valid-vs-literal: `mark <estate>` writes the canonical valid marker;
# `mark <estate> <body>` writes <body> VERBATIM — including the empty string, which a
# truthiness test would silently upgrade to valid (that bug shipped in this arm's first
# draft and turned the '' malformed case green for the wrong reason).
mark(){ python3 -c '
import hashlib, json, os, sys
est = os.path.realpath(sys.argv[1]); home = sys.argv[2]
d = os.path.join(home, "auto-build"); os.makedirs(d, exist_ok=True)
p = os.path.join(d, hashlib.sha256(est.encode()).hexdigest() + ".json")
body = (sys.argv[3] if len(sys.argv) > 3
        else json.dumps({"opted": True, "stamp": "2026-08-31 12:00Z", "estate": est}) + "\n")
open(p, "w").write(body)
os.chmod(p, 0o600); print(p)' "$1" "$NOTREST_HOME" ${2+"$2"}; }

( cd "$AB" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "auto-build: no marker in the store → hook exits 0" "$?" "0"
has "no marker → the OLD ripe nudge is unchanged" \
  "Ripe compile candidate: release-ritual seen 7x" "$W/o"
hasnt "no marker → nothing claims an authorization" "AUTO-BUILD opted in" "$W/o"

MP="$(mark "$AB")"
( cd "$AB" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "auto-build: store marker present → hook exits 0" "$?" "0"
has "marker → the echo carries the authorization" "AUTO-BUILD opted in" "$W/o"
has "…and names ONE opus lane for the ripe candidate" \
  "dispatch ONE opus builder lane this session for ripe candidate release-ritual" "$W/o"
has "…keeps the runtime isolated under compile/<slug>/" \
  "isolated under compile/release-ritual/" "$W/o"
has "…and restates the hard law in the echo itself" \
  "NEVER installed: shipping stays the owner's act" "$W/o"
hasnt "…and REPLACES the old nudge rather than doubling it" "Ripe compile candidate" "$W/o"

for BADMARK in 'garbage{' '{"opted": false}' '[]' '{}' ''; do
  mark "$AB" "$BADMARK" >/dev/null
  ( cd "$AB" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
  t "malformed store marker [$BADMARK] → hook still exits 0" "$?" "0"
  hasnt "malformed store marker [$BADMARK] claims no authorization" "AUTO-BUILD opted in" "$W/o"
  has "malformed store marker [$BADMARK] falls back to the old nudge" \
    "Ripe compile candidate: release-ritual" "$W/o"
done
rm -f "$MP"

# The LEGACY in-repo marker — valid content, correct old path — is IGNORED by law, with
# a one-line migration note so a standing authorization never silently disappears.
printf '{"opted": true, "stamp": "2026-08-31 12:00Z"}\n' > "$AB/compile/.auto-build"
( cd "$AB" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "legacy in-repo marker → hook exits 0" "$?" "0"
hasnt "legacy in-repo marker grants NO authorization" "AUTO-BUILD opted in" "$W/o"
has "…and the migration note says why and what to run" \
  "compile/.auto-build is IGNORED since v4.5" "$W/o"
rm -f "$AB/compile/.auto-build"

# An opt-in is not a licence to invent work: with nothing ripe, neither echo fires.
AB2="$W/autobuild-noripe"; mkdir -p "$AB2/compile"; ( cd "$AB2" && git init -q ) >/dev/null 2>&1
printf '{"candidates":[{"slug":"cold","occurrences":2,"ripe":false,"status":"NEW"}]}\n' \
  > "$AB2/compile/candidates.json"
mark "$AB2" >/dev/null
( cd "$AB2" && bash "$W/hooks/session-start.sh" ) > "$W/o" 2>&1
t "opted in but nothing ripe → hook exits 0" "$?" "0"
hasnt "opted in but nothing ripe → no AUTO-BUILD echo" "AUTO-BUILD opted in" "$W/o"
unset NOTREST_HOME

echo "── v4.0.0: the continuation packet"

# NOT established → the packet refuses and says what to run instead.
CU0="$W/cont-none"; mkdir -p "$CU0"; : > "$CU0/README.md"
est continuation --root "$CU0" > "$W/o" 2>&1; t "continuation on an unestablished root" "$?" "6"
has "…and names the remedy" "Run \`/notrest establish\` first" "$W/o"

# A seeded estate: ships, gates, corrections, a sealed volume, briefs, spend, agents.
CU="$W/cont"; mkdir -p "$CU"; ( cd "$CU" && git init -q ) >/dev/null 2>&1
est establish --root "$CU" >/dev/null 2>&1
{ echo "- [2026-08-01 09:00Z] [seat] built it -> v1.2.0 shipped | evidence: commit abc1234"
  echo "- [2026-08-02 10:00Z] [lane] gated the build -> doctor=5 eval=0 | evidence: exit codes"
  echo "- [2026-08-03 11:00Z] [seat] bad patch -> rollback landed | evidence: git revert"
  echo "- [2026-08-04 12:00Z] [seat] continuing -> in progress | evidence: none yet"; } >> "$CU/COORD.md"
cp "$CU/COORD.md" "$CU/COORD-001.md"
mkdir -p "$CU/briefs" "$CU/spend"; : > "$CU/briefs/agent-a.md"; : > "$CU/briefs/agent-b.md"
printf '# ledger\n[2026-08-04 12:00Z] lane=subagent model=claude-opus-4 tokens=150 grade=observed\n' \
  > "$CU/spend/ledger.md"
printf '# COORD-AGENTS.md\n\n## LEDGER\n- [2026-08-04 12:01Z] agent=x model=claude-opus-4 | last: done\n' \
  > "$CU/COORD-AGENTS.md"
est continuation --root "$CU" > "$W/o" 2>&1; t "continuation on an established estate" "$?" "0"
has "packet verdict is CONTINUABLE" "notrest: CONTINUABLE" "$W/o"
has "packet counts sealed volumes" "COORD volumes sealed: 1" "$W/o"
has "packet finds the newest SHIP" "v1.2.0 shipped" "$W/o"
has "packet finds the newest GATE" "gated the build" "$W/o"
has "packet finds the newest CORRECTION" "rollback landed" "$W/o"
has "packet counts banked briefs" "briefs banked: 2" "$W/o"
has "packet reads the spend ledger's own last line" "grade=observed" "$W/o"
hasnt "…and never shells to spend.py for a verdict" "routing: CLEAN" "$W/o"
has "packet carries the agent tail" "agent=x" "$W/o"
has "an EMPTY git repo is not reported as 'not a git repo'" "no commits yet" "$W/o"
( cd "$CU" && git add -A && git -c user.email=f@x -c user.name=f commit -qm "seed" ) >/dev/null 2>&1
est continuation --root "$CU" > "$W/o" 2>&1
has "packet reports git HEAD + last commit once there is one" "last commit: seed" "$W/o"

# DETERMINISM: same estate, same packet — the successor's read is never a moving target.
est continuation --root "$CU" > "$W/c1" 2>&1; est continuation --root "$CU" > "$W/c2" 2>&1
t "packet is byte-identical twice" "$(ckt "$W/c1")" "$(ckt "$W/c2")"
est continuation --root "$CU" --json > "$W/j1" 2>&1; est continuation --root "$CU" --json > "$W/j2" 2>&1
t "--json is byte-identical twice" "$(ckt "$W/j1")" "$(ckt "$W/j2")"
t "--json keys are sorted (stable order)" \
  "$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(list(d)==sorted(d))" "$W/j1")" "True"
t "--json carries every packet field" \
  "$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
need=['root','established','coord_tail','coord_sealed_volumes','agents_tail','newest_ships',
      'newest_gates','newest_corrections','briefs','spend_last_line','git_head',
      'git_dirty_files','git_last_subject','protocol_version']
print(all(k in d for k in need))" "$W/j1")" "True"

# TAIL CAPS: a long ledger must not dump the whole trail into a successor's context.
python3 - "$CU/COORD.md" <<'PY2'
import sys
with open(sys.argv[1], "a", encoding="utf-8") as f:
    for i in range(60):
        f.write("- [2026-08-05 00:%02dZ] [seat] filler %d -> landed | evidence: x\n" % (i % 60, i))
PY2
t "COORD tail is capped at 25" \
  "$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['coord_lines_shown'])" \
     <(est continuation --root "$CU" --json 2>/dev/null))" "25"

# GRACEFUL: non-git, and an estate whose ledger has no lines yet.
CU2="$W/cont-nogit"; mkdir -p "$CU2"; est establish --root "$CU2" >/dev/null 2>&1
est continuation --root "$CU2" > "$W/o" 2>&1; t "continuation outside git" "$?" "0"
has "…says the ledger is the whole trail there" "not a git repo" "$W/o"
CU3="$W/cont-bare"; mkdir -p "$CU3"; : > "$CU3/README.md"
est establish --root "$CU3" >/dev/null 2>&1
python3 - "$CU3/COORD.md" <<'PY3'
import sys
t = open(sys.argv[1], encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(
    l for l in t.splitlines() if not l.startswith("- ")) + "\n")
PY3
est continuation --root "$CU3" > "$W/o" 2>&1; t "continuation on a zero-line ledger" "$?" "0"
has "…still reports a continuable estate" "CONTINUABLE" "$W/o"

echo
echo "fixture: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
