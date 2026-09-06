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
OUT="$(python3 "$A" bank --root "$R2" --no-board --no-gates --adapter http 2>&1)"
echo "$OUT" | grep -q "hub contract unverified — awaiting ATLAS-PLAYBOOK/WIRING" \
  && ok "http adapter reports the unverified contract, by name" \
  || no "http adapter did not name the unverified hub contract"
[ -e "$HTTPHUB" ] && no "the http adapter wrote something" || ok "the http adapter wrote nothing"
grep -qE '^[[:space:]]*(import|from)[[:space:]]+(urllib|socket|http\.client|requests|httpx|ftplib|telnetlib|smtplib)\b' "$A" \
  && no "atlas.py imports a network module — the http stub COULD send" \
  || ok "atlas.py imports no network module — the http stub cannot send"
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

echo "── J · --dry-run measures nothing and writes nothing"
D="$W/dry"; mkrepo "$D"; mkdir -p "$D/atlas"
printf 'PART: x — never run\nCLAIM: done\nTEST: touch %s/SIDE-EFFECT\n' "$D" > "$D/atlas/map.md"
commit "$D" init
python3 "$A" bank --root "$D" --no-board --no-gates --dry-run >/dev/null 2>&1
t "--dry-run exits 0" "$?" "0"
[ -e "$D/SIDE-EFFECT" ] && no "--dry-run ran a test" || ok "--dry-run ran no test"
[ -d "$D/atlas/snapshots" ] && no "--dry-run wrote a snapshot" || ok "--dry-run wrote no snapshot"

echo ""
echo "atlas fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
