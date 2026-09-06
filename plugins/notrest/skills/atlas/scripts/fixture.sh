#!/bin/bash
# fixture.sh — asserts atlas.py against SCRATCH GIT REPOS built in a mktemp dir.
#
# It never touches the real repository (every repo here is `git init`ed inside $W), never
# reaches the network, and mints its keys into a scratch keyring — the real
# plugins/notrest/.access/keys.sha256 is never read and never written. Global git config
# is isolated too, so a machine-wide core.hooksPath or a missing user.email cannot make
# this fixture pass or fail for reasons that have nothing to do with atlas.
#
# Usage: bash <atlas-skill>/scripts/fixture.sh        (exit 0 = every assertion held)
#
# ATLAS_PY overrides the script under test — the estate's red-first convention: a new arm
# must be shown to FAIL against the previous revision before it is trusted to pass
# against this one.
set -u
# THE SAME LAW, APPLIED TO THIS HARNESS. This fixture builds scratch git repos, so a
# GIT_DIR/GIT_INDEX_FILE it inherited would aim its own `git -C` calls at somebody else's
# repository — which is exactly how it went red as a gate inside a post-commit hook while
# passing in every clean shell. A fixture that only passes in a clean environment is a
# fixture that lies wherever it matters most.
unset GIT_DIR GIT_INDEX_FILE GIT_PREFIX GIT_WORK_TREE
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_AUTHOR_DATE
unset GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_COMMITTER_DATE
unset NOTREST_ATLAS_BANKING
# EGRESS GUARD (4.9): the http adapter is real now. Every arm that does not point at the
# mock hub itself points at a port nothing listens on, so no run of this fixture can reach
# atlas.not.rest even on a machine that holds a live ingest secret.
export ATLAS_HUB_BASE="http://127.0.0.1:1"
A="${ATLAS_PY:-$(cd "$(dirname "$0")" && pwd)/atlas.py}"
W="$(mktemp -d)"
# The plugin root is pinned to the REAL tree so an ATLAS_PY copy under test still finds
# gate-check.py and the hook body — a mutation must fail on its own defect, not on its
# location.
export NOTREST_PLUGIN_ROOT="${NOTREST_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
cleanup(){ chmod -R u+w "$W" 2>/dev/null; rm -rf "$W"; return 0; }
trap cleanup EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }
hasnt(){ if grep -q -- "$2" "$1" 2>/dev/null; then no "$3 — found in $1"; else ok "$3"; fi; }
has(){ if grep -q -- "$2" "$1" 2>/dev/null; then ok "$3"; else no "$3 — not found in $1"; fi; }

# ── git isolation: this machine's config must not decide anything here ───────────────
export GIT_CONFIG_GLOBAL="$W/gitconfig" GIT_CONFIG_SYSTEM="$W/gitconfig-system"
export GIT_CONFIG_NOSYSTEM=1
cat > "$W/gitconfig" <<'CFG'
[user]
	name = atlas fixture
	email = fixture@notrest.local
[init]
	defaultBranch = main
[commit]
	gpgsign = false
CFG
: > "$W/gitconfig-system"
mkdir -p "$W/nohome"

mkrepo(){ mkdir -p "$1"; git -C "$1" init -q; git -C "$1" config --local core.hooksPath .git/hooks; }
commit(){ git -C "$1" add -A >/dev/null 2>&1; git -C "$1" commit -q --allow-empty -m "$2" >/dev/null 2>&1; }
headof(){ git -C "$1" rev-parse HEAD 2>/dev/null; }
snapof(){ echo "$1/atlas/snapshots/$(headof "$1").json"; }
field(){ python3 -c 'import json,sys
b=json.load(open(sys.argv[1]))
print(next((str(p[sys.argv[3]]) for p in b["parts"] if p["id"]==sys.argv[2]), "NO-SUCH-PART"))' "$1" "$2" "$3"; }
sumf(){ python3 -c 'import json,sys;print(str(json.load(open(sys.argv[1]))["summary"][sys.argv[2]]))' "$1" "$2"; }

echo "atlas fixture · $A"
echo "── A · the access key"
KR="$W/keys.sha256"
MINT="$(python3 "$A" key --mint --label fixture-one --keyring "$KR" 2>&1)"; t "mint exits 0" "$?" "0"
KEY="$(echo "$MINT" | grep -o 'nrk_[A-Za-z0-9_-]*' | head -1)"
[ -n "$KEY" ] && ok "mint printed a key" || no "mint printed no key"
t "mint printed it exactly once" "$(echo "$MINT" | grep -c -- "$KEY")" "1"
t "keyring line is sha256:label:date" \
  "$(grep -cE '^[0-9a-f]{64}:fixture-one:[0-9]{4}-[0-9]{2}-[0-9]{2}$' "$KR")" "1"
hasnt "$KR" "$KEY" "the key itself is never stored — only its hash"
python3 "$A" key --check --key "$KEY" --keyring "$KR" >/dev/null 2>&1; t "check a valid key" "$?" "0"
SENT="$(python3 "$A" key --check --key "$KEY" --keyring "$KR" 2>/dev/null)"
echo "$SENT" | grep -qE "^notrest-access: ok ring=[0-9a-f]{12} path=$KR$" \
  && ok "exit 0 prints the SENTINEL on stdout, with the ring it used" \
  || no "no sentinel on stdout — got [$SENT]"
t "the ring digest is sha256 of the keyring's real bytes" \
  "$(echo "$SENT" | sed 's/.*ring=\([0-9a-f]*\) .*/\1/')" \
  "$(shasum -a 256 "$KR" | cut -c1-12)"
t "--quiet KEEPS the sentinel (it is proof, not chatter)" \
  "$(python3 "$A" key --check --key "$KEY" --keyring "$KR" --quiet 2>/dev/null)" "$SENT"
t "an invalid key prints NOTHING on stdout" \
  "$(python3 "$A" key --check --key nrk_wrong --keyring "$KR" 2>/dev/null | wc -c | tr -d ' ')" "0"
ln -s "$KR" "$W/ring-link.sha256"
python3 "$A" key --check --key "$KEY" --keyring "$W/ring-link.sha256" >/dev/null 2>&1
t "a SYMLINKED keyring is refused (a re-pointable ring is a re-pointable gate)" "$?" "7"
mkdir -p "$W/ring-dir"
DIRERR="$(python3 "$A" key --check --key "$KEY" --keyring "$W/ring-dir" 2>&1 >/dev/null)"
t "a keyring that is not a regular file is refused" "$?" "7"
# The code alone does not discriminate here (an unreadable ring holds no keys either way),
# so the arm reads the REASON: refused for what it IS, not merely empty of keys.
echo "$DIRERR" | grep -q "not a regular file" \
  && ok "…and says WHY, rather than passing for 'no keys in it'" \
  || no "the refusal did not name the reason — got [$DIRERR]"
python3 "$A" key --check --key "nrk_not-a-real-key" --keyring "$KR" >/dev/null 2>&1
t "check an invalid key" "$?" "7"
(unset NOTREST_ACCESS_KEY; HOME="$W/nohome" python3 "$A" key --check --keyring "$KR" >/dev/null 2>&1)
t "check with no key anywhere" "$?" "7"
python3 "$A" key --mint --label fixture-one --keyring "$KR" >/dev/null 2>&1
t "minting a duplicate label is REFUSED" "$?" "5"
t "…and the keyring still holds one line for it" "$(grep -c ':fixture-one:' "$KR")" "1"
python3 "$A" key --mint --label 'bad:label' --keyring "$KR" >/dev/null 2>&1
t "a label carrying ':' is refused (it would break the format)" "$?" "2"
python3 "$A" key --list --keyring "$KR" 2>&1 | grep -q 'fixture-one' && ok "list names the label" || no "list omitted the label"
python3 "$A" key --list --keyring "$KR" 2>&1 | grep -q -- "$KEY" && no "list leaked the key" || ok "list never prints a key"
python3 "$A" key --revoke nope --keyring "$KR" >/dev/null 2>&1; t "revoke an unknown label" "$?" "7"
python3 "$A" key --revoke fixture-one --keyring "$KR" >/dev/null 2>&1; t "revoke exits 0" "$?" "0"
python3 "$A" key --check --key "$KEY" --keyring "$KR" >/dev/null 2>&1
t "a revoked key no longer checks out" "$?" "7"
# re-mint the key the rest of the fixture runs under
MINT="$(python3 "$A" key --mint --label fixture --keyring "$KR" 2>&1)"
KEY="$(echo "$MINT" | grep -o 'nrk_[A-Za-z0-9_-]*' | head -1)"
export NOTREST_KEYRING="$KR" NOTREST_ACCESS_KEY="$KEY" NOTREST_ATLAS_NO_BOARD=1

# PARITY WITH THE HOOKS (lane H, 4.8): the private store is ${NOTREST_HOME:-~/.notrest}.
# A machine that sets NOTREST_HOME must not get "the hook says licensed, atlas.py says no".
mkdir -p "$W/nhome" "$W/decoy/.notrest"
printf '%s\n' "$KEY" > "$W/nhome/access-key"
printf 'nrk_the-plain-copy-that-must-not-be-read\n' > "$W/decoy/.notrest/access-key"
(unset NOTREST_ACCESS_KEY; HOME="$W/decoy" NOTREST_HOME="$W/nhome" \
   python3 "$A" key --check --keyring "$KR" >/dev/null 2>&1)
t "NOTREST_HOME holds the key file, and the plain ~/.notrest copy is not read" "$?" "0"
printf 'nrk_wrong-key-in-the-private-store\n' > "$W/nhome/access-key"
printf '%s\n' "$KEY" > "$W/decoy/.notrest/access-key"
(unset NOTREST_ACCESS_KEY; HOME="$W/decoy" NOTREST_HOME="$W/nhome" \
   python3 "$A" key --check --keyring "$KR" >/dev/null 2>&1)
t "…and ~/.notrest is not consulted behind NOTREST_HOME's back" "$?" "7"

echo "── B · the status law"
R="$W/law"; mkrepo "$R"; mkdir -p "$R/atlas"
cat > "$R/atlas/map.md" <<'MAP'
PART: p1 — a done proved by a test that could fail
CLAIM: done
TEST: test -f real.txt

PART: p2 — a done with no test at all
CLAIM: done

PART: p3 — a done resting on a command that cannot fail
CLAIM: done
TEST: true

PART: p4 — a done whose test fails
CLAIM: done
TEST: test -f absent.txt

PART: p5 — red-first work
CLAIM: wip
TEST: false

PART: p6 — a wip whose test passes
CLAIM: wip
TEST: test -f real.txt

```
PART: fenced — documentation, never run
CLAIM: done
TEST: false
```
MAP
touch "$R/real.txt"; commit "$R" init
python3 "$A" bank --root "$R" --no-board --no-gates >/dev/null 2>&1
t "a claimed-done part with a failing test makes the bank RED" "$?" "5"
S="$(snapof "$R")"
t "done + passing falsifiable test  -> done"        "$(field "$S" p1 status)"   "done"
t "…and its evidence is 'passed'"                   "$(field "$S" p1 evidence)" "passed"
t "done + NO test                   -> wip"         "$(field "$S" p2 status)"   "wip"
t "…evidence 'none'"                                "$(field "$S" p2 evidence)" "none"
t "…and the demotion is REPORTED"                   "$(field "$S" p2 demoted)"  "True"
t "done + a test that cannot fail   -> wip"         "$(field "$S" p3 status)"   "wip"
t "…evidence 'unfalsifiable'"                       "$(field "$S" p3 evidence)" "unfalsifiable"
t "done + failing test              -> wip"         "$(field "$S" p4 status)"   "wip"
t "…and it is marked failing"                       "$(field "$S" p4 failing)"  "True"
t "…while the CLAIM is kept on the record"          "$(field "$S" p4 claim)"    "done"
t "wip + failing test               -> wip+failing" "$(field "$S" p5 failing)"  "True"
t "wip + PASSING test stays wip (evidence never promotes)" "$(field "$S" p6 status)" "wip"
t "a fenced PART is documentation, never a part"    "$(field "$S" fenced status)" "NO-SUCH-PART"
t "the board is RED"                                "$(sumf "$S" red)"          "True"
t "…and the demotions are counted"                  "$(sumf "$S" demoted)"      "2"

# the other side of the RED law: red-first work alone must NOT redden the board
R2="$W/redfirst"; mkrepo "$R2"; mkdir -p "$R2/atlas"
printf 'PART: only — red-first\nCLAIM: wip\nTEST: false\n' > "$R2/atlas/map.md"
commit "$R2" init
python3 "$A" bank --root "$R2" --no-board --no-gates >/dev/null 2>&1
t "a failing WIP alone is not RED (the board must not cry wolf)" "$?" "0"
t "…though the failure is still recorded" "$(sumf "$(snapof "$R2")" failing)" "1"

# an estate with no contract is never certified green
R3="$W/empty"; mkrepo "$R3"; mkdir -p "$R3/atlas"; commit "$R3" init
python3 "$A" bank --root "$R3" --no-board >/dev/null 2>&1
t "no map and no gates -> refuses to bank" "$?" "3"
mkdir -p "$W/not-a-repo"
python3 "$A" bank --root "$W/not-a-repo" --no-board >/dev/null 2>&1
t "a real directory that is not a git work tree -> exit 3" "$?" "3"
python3 "$A" bank --root "$W/does-not-exist" --no-board >/dev/null 2>&1
t "a root that does not exist -> exit 2 (usage, not a verdict)" "$?" "2"

echo "── C · the snapshot is immutable"
BEFORE="$(shasum "$S" | awk '{print $1}')"
MODE="$(ls -l "$S" | cut -c1-10)"
rm "$R/real.txt"                       # p1's test now FAILS — the derivation moved
OUT="$(python3 "$A" bank --root "$R" --no-board --no-gates 2>&1)"
t "re-banking the same commit leaves the snapshot byte-identical" \
  "$(shasum "$S" | awk '{print $1}')" "$BEFORE"
t "…p1 still reads 'passed' in the banked snapshot" "$(field "$S" p1 evidence)" "passed"
echo "$OUT" | grep -q "immutable" && ok "…and the run SAYS the snapshot stands" \
  || no "the run did not say the snapshot is immutable"
echo "$OUT" | grep -q "DIFFERS" && ok "…and says today's derivation differs" \
  || no "a differing derivation was not disclosed"
t "the snapshot file is read-only on disk" "$MODE" "-r--r--r--"
touch "$R/real.txt"; commit "$R" second
python3 "$A" bank --root "$R" --no-board --no-gates >/dev/null 2>&1
[ -f "$(snapof "$R")" ] && ok "a new commit gets its own snapshot" || no "no snapshot for the new commit"
t "two commits, two snapshots" "$(ls "$R/atlas/snapshots" | wc -l | tr -d ' ')" "2"

echo "── D · gates become parts claimed done"
G="$W/gates"; mkrepo "$G"; mkdir -p "$G/atlas" "$G/gates"
printf 'PART: solo — a part beside the gates\nCLAIM: planned\n' > "$G/atlas/map.md"
cat > "$G/gates/ACTIVE.md" <<'GA'
GATE: the green one
CHECK: true

GATE: the red one
CHECK: exit 3
GA
commit "$G" init
python3 "$A" bank --root "$G" --no-board >/dev/null 2>&1
t "a red gate reddens the board" "$?" "5"
SG="$(snapof "$G")"
t "the green gate is a part claimed done" "$(field "$SG" gate:the-green-one claim)" "done"
t "the red gate is demoted to wip"        "$(field "$SG" gate:the-red-one status)" "wip"
t "…and marked failing"                   "$(field "$SG" gate:the-red-one failing)" "True"
printf 'GATE: nothing armed here at all\n' > "$G/gates/ACTIVE.md"
commit "$G" "gates that declare nothing"
python3 "$A" bank --root "$G" --no-board >/dev/null 2>&1
t "a gates file that declares no gate is a RED part, never a silent absence" "$?" "5"
t "…named gates:contract" "$(field "$(snapof "$G")" gates:contract failing)" "True"

echo "── E · the push adapters"
HUB="$W/hub"
python3 "$A" bank --root "$R2" --no-board --no-gates --hub "$HUB" >/dev/null 2>&1
t "file adapter: a green board still exits 0 after pushing" "$?" "0"
C2="$(headof "$R2")"
[ -f "$HUB/redfirst/snapshots/$C2.json" ] && ok "file hub holds the snapshot" || no "no snapshot at the hub"
t "the hub's HEAD is the estate's HEAD" "$(cat "$HUB/redfirst/HEAD" 2>/dev/null)" "$C2"
[ -f "$HUB/redfirst/board.json" ] && ok "file hub holds the board" || no "no board at the hub"
python3 "$A" bank --root "$R2" --no-board --no-gates --hub "$HUB" >/dev/null 2>&1
t "re-pushing the same commit is not a failure" "$?" "0"
HTTPHUB="$W/never-written"
OUT="$(NOTREST_HOME="$W/nohub" python3 "$A" bank --root "$R2" --no-board --no-gates --adapter http 2>&1)"
t "http adapter with no ingest secret exits 4" "$?" "4"
echo "$OUT" | grep -q "no ingest secret at $W/nohub/credentials/atlas-ingest-redfirst" \
  && ok "…naming the file it wants, by PATH and by the ruling's name" \
  || no "http adapter did not name the ingest file it wants — [$OUT]"
[ -e "$HTTPHUB" ] && no "the http adapter wrote something" || ok "the http adapter wrote nothing"
grep -qE '^[[:space:]]*(import|from)[[:space:]]+(urllib|socket|http\.client|requests|httpx|ftplib|telnetlib|smtplib)\b' "$A" \
  && no "atlas.py imports a network module — the seam is supposed to delegate" \
  || ok "atlas.py still imports no network module — the transport lives in atlas_wire.py"
OUT="$(python3 "$A" bank --root "$R2" --no-board --no-gates --adapter none 2>&1)"
echo "$OUT" | grep -q "no hub configured" && ok "'no hub configured' is a state, not a failure" \
  || no "the none adapter did not say 'no hub configured'"

echo "── F · wire, idempotently and without clobbering"
python3 "$A" wire --root "$R2" >/dev/null 2>&1; t "wire exits 0" "$?" "0"
P="$R2/.git/hooks/post-commit"
[ -x "$P" ] && ok "post-commit is executable" || no "post-commit is not executable"
has "$P" "notrest-atlas-hook" "the shim carries atlas's mark"
OUT="$(python3 "$A" wire --root "$R2" 2>&1)"; t "wiring twice exits 0" "$?" "0"
echo "$OUT" | grep -q "already wired" && ok "…and says 'already wired'" || no "a second wire did not say so"
FOR="$W/foreign"; mkrepo "$FOR"; mkdir -p "$FOR/.git/hooks"
printf '#!/bin/sh\necho somebody elses hook\n' > "$FOR/.git/hooks/post-commit"
chmod +x "$FOR/.git/hooks/post-commit"
python3 "$A" wire --root "$FOR" >/dev/null 2>&1; t "a foreign post-commit hook is REFUSED" "$?" "5"
has "$FOR/.git/hooks/post-commit" "somebody elses hook" "…and left completely untouched"
python3 "$A" wire --root "$FOR" --force >/dev/null 2>&1; t "--force wires it" "$?" "0"
has "$FOR/.git/hooks/post-commit.pre-atlas" "somebody elses hook" "…keeping the original as .pre-atlas"
python3 "$A" wire --root "$FOR" --unwire >/dev/null 2>&1; t "--unwire exits 0" "$?" "0"
has "$FOR/.git/hooks/post-commit" "somebody elses hook" "…and restores the hook it displaced"

echo "── G · the hook actually fires, and the key gates it"
H="$W/hooked"; mkrepo "$H"; mkdir -p "$H/atlas"
printf 'PART: only — a part that passes\nCLAIM: done\nTEST: test -f keep.txt\n' > "$H/atlas/map.md"
touch "$H/keep.txt"
python3 "$A" wire --root "$H" >/dev/null 2>&1
commit "$H" "first, hook live"
[ -f "$(snapof "$H")" ] && ok "a real git commit banked a snapshot" || no "the hook did not bank"
python3 "$A" status --root "$H" >/dev/null 2>&1; t "status on a banked green HEAD" "$?" "0"
mkdir -p "$W/fakebin"
printf '#!/bin/sh\necho FAKE-INTERPRETER-RAN\nexit 0\n' > "$W/fakebin/python3"
chmod +x "$W/fakebin/python3"
OUT="$(PATH="$W/fakebin:$PATH" git -C "$H" commit -q --allow-empty -m "fake python3" 2>&1)"
t "a python3 that exits 0 without parsing atlas.py cannot pass the gate" \
  "$(echo -n "$OUT" | wc -c | tr -d ' ')" "0"
OUT="$(cd "$H" && unset NOTREST_ACCESS_KEY; HOME="$W/nohome" git -C "$H" commit -q --allow-empty -m "no key" 2>&1)"
t "a keyless commit is SILENT" "$(echo -n "$OUT" | wc -c | tr -d ' ')" "0"
[ -f "$(snapof "$H")" ] && no "the hook banked without a key" || ok "…and banks nothing without a key"
python3 "$A" status --root "$H" >/dev/null 2>&1
t "a commit that never banked turns the estate RED (exit 6)" "$?" "6"
commit "$H" "back with a key"
python3 "$A" status --root "$H" >/dev/null 2>&1; t "…and green again once it banks" "$?" "0"
python3 "$A" status --root "$R" >/dev/null 2>&1; t "status on a RED board" "$?" "5"
NOATLAS="$W/no-atlas"; mkrepo "$NOATLAS"; commit "$NOATLAS" init
python3 "$A" status --root "$NOATLAS" >/dev/null 2>&1
t "status where no atlas/ exists — not on the map, not red" "$?" "3"
BARE="$W/no-commit"; mkrepo "$BARE"; mkdir -p "$BARE/atlas"
python3 "$A" status --root "$BARE" >/dev/null 2>&1
t "a repo with no commit is 'nothing to bank' (3), never the born-red 6" "$?" "3"

echo "── H · the born-red proof"
OUT="$(python3 "$A" wire --root "$H" --prove 2>&1)"; PRC=$?
t "the proof passes" "$PRC" "0"
echo "$OUT" | grep -q "VERDICT: PASS" && ok "…with an explicit PASS verdict" || no "no PASS verdict printed"
echo "$OUT" | grep -q "step 2 · hook disabled  · commit .* · status exit 6" \
  && ok "…because step 2 was actually WATCHED going red" || no "step 2 did not go red"
[ -f "$H/atlas/born-red.json" ] && ok "the receipt lands at atlas/born-red.json" || no "no receipt written"
python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));sys.exit(0 if d["verdict"]=="PASS" and len(d["steps"])==3 else 1)' \
  "$H/atlas/born-red.json" && ok "the receipt records all three steps" || no "the receipt is incomplete"
commit "$H" "a commit after the proof"        # the immutable snapshot before it cannot change
python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));sys.exit(0 if d["born_red_proof"]["present"] else 1)' \
  "$(snapof "$H")" && ok "the proof rides on every later snapshot" || no "the snapshot does not carry the proof"
(unset NOTREST_ACCESS_KEY; HOME="$W/nohome" python3 "$A" wire --root "$H" --prove --no-receipt >/dev/null 2>&1)
t "the proof refuses to run without a key (it would go red for the wrong reason)" "$?" "7"

echo "── I · the board says stale out loud, and carries counts only"
python3 "$A" bank --root "$R2" --no-board --no-gates >/dev/null 2>&1
python3 -c 'import json,sys
b=json.load(open(sys.argv[1]))
s=b["sources"]
bad=[k for k,v in s.items() if v.get("ok") or not v.get("reason")]
sys.exit(1 if bad or len(s)!=3 else 0)' "$R2/atlas/board.json" \
  && ok "--no-board leaves every collector STALE with a reason" || no "a disabled collector claimed ok"
unset NOTREST_ATLAS_NO_BOARD
python3 "$A" bank --root "$R2" --no-gates --board-timeout 60 >/dev/null 2>&1
python3 -c 'import json,sys
b=json.load(open(sys.argv[1]))
ok_=[k for k,v in b["sources"].items() if v.get("ok")]
sys.exit(0 if ok_ else 1)' "$R2/atlas/board.json" \
  && ok "the real collectors produce a board" || no "no collector produced anything"
hasnt "$R2/atlas/board.json" '"statement"' "the board carries COUNTS ONLY — no finding text on the wire"
export NOTREST_ATLAS_NO_BOARD=1

echo "── K · git's hook environment never reaches a gate or a test"
# Live finding (commit b60816c): a post-commit hook is handed GIT_DIR/GIT_INDEX_FILE/
# GIT_PREFIX and every child inherits them, so a gate that runs git was aimed at the
# estate's own .git whatever directory it was given.
cat > "$W/env-probe.sh" <<'PROBE'
#!/bin/sh
# Every GIT_* the child can see, minus the allowlist. A denylist arm would pass the day
# git invents a twentieth variable; this one cannot.
LEAK=$(env | sed -n 's/^\(GIT_[A-Za-z0-9_]*\)=.*/\1/p' \
       | grep -vE '^(GIT_TERMINAL_PROMPT|GIT_SSH_COMMAND|GIT_SSH)$' | tr '\n' ' ')
[ -n "$LEAK" ] && { echo "LEAKED $LEAK"; exit 1; }
[ -n "${NOTREST_ATLAS_BANKING:-}" ] && { echo "LEAKED the re-entrancy marker"; exit 1; }
exit 0
PROBE
E="$W/envleak"; mkrepo "$E"; mkdir -p "$E/atlas" "$E/gates"
printf 'PART: probe — the test sees a clean environment\nCLAIM: done\nTEST: sh %s/env-probe.sh\n' "$W" > "$E/atlas/map.md"
printf 'GATE: the gate sees a clean environment\nCHECK: sh %s/env-probe.sh\n' "$W" > "$E/gates/ACTIVE.md"
commit "$E" init

# THE 03:03 INCIDENT, armed. RA is the repository whose hook environment is inherited;
# RB is the estate atlas is told to work on. Everything below runs under RA's full env.
RA="$W/incident-A"; mkrepo "$RA"; commit "$RA" a1
RB="$W/incident-B"; mkrepo "$RB"; mkdir -p "$RB/atlas"
printf 'PART: b — B is its own estate\nCLAIM: done\nTEST: true\n' > "$RB/atlas/map.md"
commit "$RB" b1
INH="GIT_DIR=$RA/.git GIT_WORK_TREE=$RA GIT_INDEX_FILE=$RA/.git/index GIT_PREFIX= \
     GIT_OBJECT_DIRECTORY=$RA/.git/objects GIT_COMMON_DIR=$RA/.git \
     GIT_ALTERNATE_OBJECT_DIRECTORIES=$RA/.git/objects GIT_CEILING_DIRECTORIES=$W \
     GIT_NAMESPACE=leak GIT_EXEC_PATH=/nonexistent-exec-path GIT_EDITOR=false \
     GIT_AUTHOR_NAME=inherited GIT_COMMITTER_NAME=inherited NOTREST_ATLAS_BANKING=1"
eval env $INH python3 "$A" bank --root "$E" --no-board >/dev/null 2>&1
t "a TEST and a GATE see no GIT_* at all beyond the allowlist" "$?" "0"
ACOUNT="$(git -C "$RA" rev-list --count HEAD)"
eval env $INH python3 "$A" bank --root "$RB" --no-board --no-gates >/dev/null 2>&1
t "bank under RA's inherited env still exits on RB's own board" "$?" "0"
BHEAD="$(headof "$RB")"
[ -f "$RB/atlas/snapshots/$BHEAD.json" ] \
  && ok "…and certifies RB's OWN head, not the inherited repository's" \
  || no "the snapshot is not RB's HEAD — $(ls "$RB/atlas/snapshots" 2>/dev/null)"
t "…so exactly one snapshot exists in B" "$(ls "$RB/atlas/snapshots" | wc -l | tr -d ' ')" "1"
eval env $INH python3 "$A" wire --root "$RB" --prove --no-receipt >/dev/null 2>&1
t "--prove under the inherited env still passes" "$?" "0"
t "…and commits NOTHING into the inherited repository" \
  "$(git -C "$RA" rev-list --count HEAD)" "$ACOUNT"

echo "── J · --dry-run measures nothing and writes nothing"
D="$W/dry"; mkrepo "$D"; mkdir -p "$D/atlas"
printf 'PART: x — never run\nCLAIM: done\nTEST: touch %s/SIDE-EFFECT\n' "$D" > "$D/atlas/map.md"
commit "$D" init
python3 "$A" bank --root "$D" --no-board --no-gates --dry-run >/dev/null 2>&1
t "--dry-run exits 0" "$?" "0"
[ -e "$D/SIDE-EFFECT" ] && no "--dry-run ran a test" || ok "--dry-run ran no test"
[ -d "$D/atlas/snapshots" ] && no "--dry-run wrote a snapshot" || ok "--dry-run wrote no snapshot"

echo "── L · the identity token, beside the ring (4.9)"
# THE SHAPE IS THE CONTRACT, not the exit code. estate-root.sh matches the substring
# `notrest-access: ok ring=<12hex>` and atlas-bank-hook.sh matches the prefix, so a TOKEN
# admission has to emit that same line with the same ring hash — a second shape would be a
# hook change nobody asked for — plus ` via=token` so a human reading the stream can still
# tell which credential opened the gate. Every arm here asserts the LINE.
TOKMOD="$NOTREST_PLUGIN_ROOT/skills/atlas/scripts/atlas_token.py"
MOCKHUB="$NOTREST_PLUGIN_ROOT/skills/atlas/scripts/mockhub.py"
if ! command -v node >/dev/null 2>&1; then
  # Not a skip. A token gate that could not be exercised is not a green token gate, and
  # the wave's other fixtures (fixture-auth) refuse the same way.
  no "the token arms need node to sign fixtures — none on PATH, so this gate is not green"
elif [ ! -f "$TOKMOD" ]; then
  no "atlas_token.py is missing from this install — key --check cannot admit a token"
else
TH="$W/tokhome"; mkdir -p "$TH"
TFP="$(python3 "$TOKMOD" fingerprint --home "$TH" 2>/dev/null)"
RINGHASH="$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:12])' "$KR")"
cat > "$W/mktoken.js" <<'JSEOF'
// node (OpenSSL Ed25519) signs; atlas.py -> atlas_token.py -> the vendored verifier
// checks. Two implementations must agree. Fresh key each run, public half only.
const crypto = require('crypto'), fs = require('fs');
const HOME = process.argv[2], MID = process.argv[3], KIND = process.argv[4];
const b64u = (b) => Buffer.from(b).toString('base64')
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const k = crypto.generateKeyPairSync('ed25519');
fs.writeFileSync(HOME + '/atlas-jwks.json', JSON.stringify(
  { keys: [Object.assign({ kid: 'fixture-kid' }, k.publicKey.export({ format: 'jwk' }))] }));
const now = Math.floor(Date.now() / 1000);
const over = KIND === 'expired' ? { iat: now - 40 * 86400, exp: now - 86400 } : {};
const c = Object.assign({
  iss: 'https://atlas.not.rest', aud: 'notrest-plugin',
  sub: 'fixture@nava.house', seat: 'fixture-seat', mid: MID,
  prj: ['notrest-plugin'], scp: ['harness', 'push'],
  jti: 'fixture-jti', iat: now, exp: now + 30 * 86400 }, over);
const h = b64u(JSON.stringify({ alg: 'EdDSA', typ: 'JWT', kid: 'fixture-kid' }));
const p = b64u(JSON.stringify(c));
fs.writeFileSync(HOME + '/atlas-token', h + '.' + p + '.'
  + b64u(crypto.sign(null, Buffer.from(h + '.' + p, 'ascii'), k.privateKey)) + '\n',
  { mode: 0o600 });
JSEOF
node "$W/mktoken.js" "$TH" "$TFP" good || no "could not sign a fixture token"

TOKOUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$TH" python3 "$A" key --check --keyring "$KR" 2>/dev/null)"; TOKRC=$?
t "a token admits this machine" "$TOKRC" "0"
t "…with the SAME sentinel and the SAME ring hash, plus via=token" \
  "$TOKOUT" "notrest-access: ok ring=$RINGHASH path=$KR via=token"
printf '%s' "$TOKOUT" | grep -qE '^notrest-access: ok ring=[0-9a-f]{12} ' \
  && ok "…and still matches the substring the hooks grep for" \
  || no "the hooks' substring no longer matches — [$TOKOUT]"
QOUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$TH" python3 "$A" key --check --quiet --keyring "$KR" 2>/dev/null)"
t "--quiet keeps the sentinel and nothing else" \
  "$QOUT" "notrest-access: ok ring=$RINGHASH path=$KR via=token"
printf '%s' "$TOKOUT$QOUT" | grep -qE 'fixture@nava.house|fixture-seat' \
  && no "a sub or a seat reached hook stdout" || ok "nothing personal on hook stdout"

RH="$W/ringhome"; mkdir -p "$RH"; printf '%s\n' "$KEY" > "$RH/access-key"
ROUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$RH" python3 "$A" key --check --keyring "$KR" 2>/dev/null)"; RRC=$?
t "a ring key still admits" "$RRC" "0"
t "…with the 4.8 sentinel, unchanged — no suffix" "$ROUT" "notrest-access: ok ring=$RINGHASH path=$KR"

NH="$W/nokeyhome"; mkdir -p "$NH"
NOUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$NH" HOME="$W/nohome" python3 "$A" key --check --quiet --keyring "$KR" 2>/dev/null)"; NRC=$?
t "neither credential → 7" "$NRC" "7"
t "…and --quiet stdout is empty on 7" "$(printf '%s' "$NOUT" | wc -c | tr -d ' ')" "0"

EH="$W/expiredring"; mkdir -p "$EH"; node "$W/mktoken.js" "$EH" "$TFP" expired
printf '%s\n' "$KEY" > "$EH/access-key"
EOUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$EH" python3 "$A" key --check --keyring "$KR" 2>/dev/null)"; ERC=$?
t "an expired token with a valid ring is admitted BY THE RING" "$ERC" "0"
t "…and the sentinel carries no via=token" "$EOUT" "notrest-access: ok ring=$RINGHASH path=$KR"

EN="$W/expirednoring"; mkdir -p "$EN"; node "$W/mktoken.js" "$EN" "$TFP" expired
EERR="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$EN" HOME="$W/nohome" python3 "$A" key --check --keyring "$KR" 2>&1 >/dev/null)"; EERC=$?
t "an expired token and no ring → 7" "$EERC" "7"
printf '%s\n' "$EERR" | grep -q '^RED exp: expired$' \
  && ok "…and the refusal says which fact, on stderr" \
  || no "no 'RED exp: expired' on stderr — got [$(printf '%s' "$EERR" | head -n1)]"

LOUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$TH" python3 "$A" key --list --keyring "$KR" 2>/dev/null)"
printf '%s' "$LOUT" | grep -q 'token: present (sub=fixture@nava.house, exp=' \
  && ok "key --list names the token's sub and expiry (the only place a sub is printed)" \
  || no "key --list did not name the token"
TOKVAL="$(cat "$TH/atlas-token" 2>/dev/null)"
if [ -z "$TOKVAL" ]; then no "no fixture token to grep for — the leak arm cannot run"
elif printf '%s' "$LOUT" | grep -qF -- "$TOKVAL"; then no "key --list leaked the token value"
else ok "key --list never prints the token itself"; fi
(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$NH" python3 "$A" key --list --keyring "$KR" 2>/dev/null | grep -q 'token: none')
t "…and says 'token: none' where there is none" "$?" "0"

echo "── L1 · login and the credential helper, against the mock hub"
if [ ! -f "$MOCKHUB" ]; then
  no "mockhub.py is missing from this install — the login arm cannot run"
else
LH="$W/loginhome"; mkdir -p "$LH"
RGC="$HOME/.gitconfig"
RGC_BEFORE="$(shasum -a 256 "$RGC" 2>/dev/null | cut -d' ' -f1)"
python3 "$MOCKHUB" --port 0 --mode ok --auto-approve-after 1 --print-port \
  > "$W/hub.port" 2>"$W/hub.log" &
HUBPID=$!
HUBURL=""; i=0
while [ $i -lt 150 ]; do
  p="$(head -n1 "$W/hub.port" 2>/dev/null)"
  case "$p" in ''|*[!0-9]*) ;; *) HUBURL="http://127.0.0.1:$p"; break ;; esac
  sleep 0.1; i=$((i + 1))
done
if [ -z "$HUBURL" ]; then
  no "mockhub never printed a port — $(head -n2 "$W/hub.log" 2>/dev/null)"
else
  LOGOUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$LH" python3 "$A" login --base "$HUBURL" 2>/dev/null)"; LRC=$?
  t "login against the mock hub exits 0" "$LRC" "0"
  printf '%s' "$LOGOUT" | grep -q '^atlas-token: ok sub=' \
    && ok "login prints the token line" || no "login printed no token line — [$LOGOUT]"
  printf '%s' "$LOGOUT" | grep -q '^helper: installed for 127.0.0.1' \
    && ok "…and installs the credential helper by default" || no "no helper line — [$LOGOUT]"
  [ -f "$LH/atlas-token" ] && ok "the token is stored under NOTREST_HOME" || no "no token stored"
  t "…0600, and only 0600" \
    "$(python3 -c 'import os,sys;print(os.stat(sys.argv[1]).st_mode & 0o777)' "$LH/atlas-token" 2>/dev/null)" "384"
  LTOK="$(cat "$LH/atlas-token" 2>/dev/null)"
  if [ -z "$LTOK" ]; then no "login stored no token — the leak arm cannot run"
  elif printf '%s' "$LOGOUT" | grep -qF -- "$LTOK"; then no "login printed the token value"
  else ok "login never prints the token itself"; fi
  [ -n "$(git config --global --get "credential.$HUBURL.helper" 2>/dev/null)" ] \
    && ok "the helper landed in the SANDBOXED git config" \
    || no "no helper line in $GIT_CONFIG_GLOBAL"
  t "…and the real ~/.gitconfig is byte-identical afterwards" \
    "$(shasum -a 256 "$RGC" 2>/dev/null | cut -d' ' -f1)" "$RGC_BEFORE"
  (unset NOTREST_ACCESS_KEY; NOTREST_HOME="$LH" python3 "$A" key --check --quiet --keyring "$KR" >/dev/null 2>&1)
  t "the token login just stored admits this machine end-to-end" "$?" "0"
  # `git credential fill` never contacts the hub — it runs the configured helper — but it
  # asks for `protocol=https`, so the round trip is only observable over an https URL. The
  # mock hub is http, hence a second install here rather than a reuse of the login one.
  HTTPS_HUB="https://127.0.0.1:${HUBURL##*:}"
  (unset NOTREST_ACCESS_KEY; NOTREST_HOME="$LH" python3 "$A" helper --install --hub "$HTTPS_HUB" >/dev/null 2>&1)
  t "helper --install exits 0" "$?" "0"
  (unset NOTREST_ACCESS_KEY; NOTREST_HOME="$LH" python3 "$A" helper --check --hub "$HTTPS_HUB" >/dev/null 2>&1)
  t "helper --check round-trips git credential fill" "$?" "0"
  HCOUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$LH" python3 "$A" helper --check --hub "$HTTPS_HUB" 2>/dev/null)"
  if [ -z "$LTOK" ]; then no "no token to check the helper's silence against"
  elif printf '%s' "$HCOUT" | grep -qF -- "$LTOK"; then no "helper --check printed the token it received"
  else ok "helper --check says whether, never what"; fi
  (unset NOTREST_ACCESS_KEY; NOTREST_HOME="$LH" python3 "$A" helper --uninstall --hub "$HTTPS_HUB" >/dev/null 2>&1)
  t "helper --uninstall exits 0" "$?" "0"
  (unset NOTREST_ACCESS_KEY; NOTREST_HOME="$LH" python3 "$A" helper --check --hub "$HTTPS_HUB" >/dev/null 2>&1)
  t "…and --check then says 1" "$?" "1"
fi
kill "$HUBPID" 2>/dev/null; wait "$HUBPID" 2>/dev/null
fi

echo "── L3 · the http adapter really pushes (4.9), against the mock hub"
if [ ! -f "$MOCKHUB" ]; then
  no "mockhub.py is missing from this install — the http push arms cannot run"
else
PH="$W/pushhome"; mkdir -p "$PH/credentials"
PR="$W/pushed-estate"; mkrepo "$PR"; mkdir -p "$PR/atlas/board"
printf 'PART: wire — the estate declares one part\nCLAIM: done\nTEST: [ -f atlas/map.md ]\n' \
  > "$PR/atlas/map.md"
printf '<!doctype html><title>board</title><p>the estate board</p>\n' > "$PR/atlas/board/index.html"
printf '{"schema":"notrest.atlas.config/1","adapter":"http","project":"pushed-estate"}\n' \
  > "$PR/atlas/config.json"
commit "$PR" init
PSEC="mock-ingest-pushed-estate"
PCRED="$PH/credentials/atlas-ingest-pushed-estate"
printf '%s\n' "$PSEC" > "$PCRED"; chmod 600 "$PCRED"
python3 "$MOCKHUB" --port 0 --print-port > "$W/hub2.port" 2>"$W/hub2.log" &
HUBPID=$!
HUBURL=""; i=0
while [ $i -lt 150 ]; do
  p="$(head -n1 "$W/hub2.port" 2>/dev/null)"
  case "$p" in ''|*[!0-9]*) ;; *) HUBURL="http://127.0.0.1:$p"; break ;; esac
  sleep 0.1; i=$((i + 1))
done
L3LOG="$W/l3.log"; : > "$L3LOG"
# every push in this section, with its whole output banked for the leak arm below
pushbank(){ NOTREST_HOME="$PH" ATLAS_HUB_BASE="$HUBURL" python3 "$A" bank --root "$PR" \
              --no-board --no-gates "$@" >"$W/p.out" 2>"$W/p.err"; PRC=$?
            cat "$W/p.out" "$W/p.err" >> "$L3LOG"; return $PRC; }
J(){ python3 -c 'import json,sys
b = json.load(open(sys.argv[1]))
print(b["push"][sys.argv[2]])' "$W/p.out" "$1" 2>/dev/null; }
if [ -z "$HUBURL" ]; then
  no "mockhub never printed a port — $(head -n2 "$W/hub2.log" 2>/dev/null)"
else
PHEAD="$(headof "$PR")"
pushbank --json; t "bank with the http adapter exits 0" "$?" "0"
t "…the hub took it" "$(J ok)" "True"
t "…and hub_commit IS the head we sent" "$(J hub_commit)" "$PHEAD"
grep -qF "stored snap:pushed-estate" "$W/p.out" \
  && ok "…reporting the hub's own stored key" || no "no stored key — [$(J reason)]"
grep -qF "board stored" "$W/p.out" \
  && ok "…and the board document landed too" || no "the board never landed — [$(J reason)]"
# A SECOND APART, DELIBERATELY: the snapshot's ts has second resolution, so two banks
# inside one second are byte-identical for the wrong reason and would pass this arm even
# if the adapter pushed today's re-derivation instead of the banked snapshot.
sleep 1.1
pushbank --json; t "re-banking the same commit exits 0" "$?" "0"
grep -qF "idempotent" "$W/p.out" \
  && ok "…and the hub calls the replay idempotent, not new news" \
  || no "the replay was not idempotent — [$(J reason)]"
t "…still the same hub_commit" "$(J hub_commit)" "$PHEAD"
SOUT="$(NOTREST_HOME="$PH" python3 "$A" status --root "$PR" 2>&1)"; echo "$SOUT" >> "$L3LOG"
printf '%s' "$SOUT" | grep -qF "pushed ${PHEAD:0:12}; the hub reflects it within ~2 min" \
  && ok "status reads a fresh 201 as pushed, never as a hub that is behind" \
  || no "status did not name the ~2 min reflection — [$SOUT]"
printf 'not-the-ingest-secret\n' > "$PCRED"
pushbank; t "a bad bearer exits 4" "$?" "4"
grep -qF "401 authorization: bad bearer" "$W/p.out" \
  && ok "…with the hub's one fact, verbatim" || no "the hub's fact was not passed through"
grep -q "^PUSH    : http — 401 authorization: bad bearer" "$W/p.out" \
  && ok "…on the bank's own PUSH line" || no "the PUSH line did not carry it"
SOUT="$(NOTREST_HOME="$PH" python3 "$A" status --root "$PR" 2>&1)"; echo "$SOUT" >> "$L3LOG"
printf '%s' "$SOUT" | grep -qF "last push FAILED: 401 authorization: bad bearer" \
  && ok "…and status says the last push failed, with the reason" \
  || no "status hid the failed push — [$SOUT]"
rm -f "$PCRED"
printf '%s\n' "$PSEC" > "$PH/credentials/atlas-token"; chmod 600 "$PH/credentials/atlas-token"
pushbank; t "the legacy credential name still pushes, and exits 0" "$?" "0"
t "…warning EXACTLY once" "$(grep -c 'legacy ingest secret' "$W/p.err")" "1"
grep -qF "credentials/atlas-ingest-pushed-estate" "$W/p.err" \
  && ok "…and naming the file it should be renamed to" || no "the warning named no new file"
rm -f "$PH/credentials/atlas-token"
pushbank; t "with no credential at all, bank exits 4 (push failed, not red)" "$?" "4"
grep -qF "no ingest secret at" "$W/p.out" \
  && ok "…naming the path it looked for" || no "no path named"
printf '%s\n' "$PSEC" > "$PCRED"; chmod 600 "$PCRED"
printf 'PART: red — a done whose test fails\nCLAIM: done\nTEST: exit 3\n' >> "$PR/atlas/map.md"
commit "$PR" "go red"
pushbank; t "a RED estate still exits 5, never the push's 4" "$?" "5"
grep -q "^RED: red — claims done" "$W/p.out" \
  && ok "…and says which part is red" || no "the red part was not named"
if [ -z "$PSEC" ]; then no "no secret to grep for"
elif grep -qF -- "$PSEC" "$L3LOG"; then no "the ingest secret value appeared in the output"
else ok "the ingest secret value never appears in any output of these arms"; fi
grep -qiF "authorization: bearer" "$L3LOG" \
  && no "a Bearer header was printed" || ok "no Bearer header was ever printed"
fi
kill "$HUBPID" 2>/dev/null; wait "$HUBPID" 2>/dev/null
fi

echo "── L2 · red-first: each new guard removed, its arm must go wrong"
amut(){ # NAME SED-EXPR — echoes the mutant path, or records a FAIL and returns 1
  local d="$W/amut/$1"; mkdir -p "$d"
  cp "$A" "$d/atlas.py"
  sed -i.bak "$2" "$d/atlas.py"; rm -f "$d/atlas.py.bak"
  if cmp -s "$A" "$d/atlas.py"; then
    no "mutant $1 — the sed changed nothing (the guard moved; this arm is asleep)"; return 1
  fi
  python3 -c 'import ast,sys;ast.parse(open(sys.argv[1]).read())' "$d/atlas.py" 2>/dev/null \
    || { no "mutant $1 — does not parse"; return 1; }
  echo "$d/atlas.py"
}
AM1="$(amut notoken 's/^    if tok_ok:$/    if False:/')"
[ -n "${AM1:-}" ] && {
  (unset NOTREST_ACCESS_KEY; NOTREST_HOME="$TH" python3 "$AM1" key --check --quiet --keyring "$KR" >/dev/null 2>&1)
  t "without the token branch, the token no longer admits" "$?" "7"
}
AM2="$(amut noviatag 's/ + " via=token"//')"
[ -n "${AM2:-}" ] && {
  M2OUT="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$TH" python3 "$AM2" key --check --quiet --keyring "$KR" 2>/dev/null)"
  [ "$M2OUT" = "notrest-access: ok ring=$RINGHASH path=$KR" ] \
    && ok "the via=token arm has teeth (a mutant that drops the suffix is caught)" \
    || no "dropping via=token changed nothing the arm can see — [$M2OUT]"
}
AM3="$(amut nored 's/if tok_reason != "token: absent":/if False:/g')"
[ -n "${AM3:-}" ] && {
  M3ERR="$(unset NOTREST_ACCESS_KEY; NOTREST_HOME="$EN" HOME="$W/nohome" python3 "$AM3" key --check --keyring "$KR" 2>&1 >/dev/null)"
  printf '%s' "$M3ERR" | grep -q 'RED exp: expired' \
    && no "the RED-on-stderr arm cannot fail — the mutant printed it anyway" \
    || ok "the RED-on-stderr arm has teeth"
}
AM4="$(amut nolisttoken 's/print("  token: none")/pass/')"
[ -n "${AM4:-}" ] && {
  (unset NOTREST_ACCESS_KEY; NOTREST_HOME="$NH" python3 "$AM4" key --list --keyring "$KR" 2>/dev/null | grep -q 'token: none')
  t "without the list line, 'token: none' disappears" "$?" "1"
}
fi

echo ""
echo "atlas fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
