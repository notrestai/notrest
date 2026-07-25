#!/usr/bin/env bash
# fixture.sh — one full run: five historical replays, the refusal battery (10-20), count
# reconciliation, the reordered-key manifest repro, and parity asserts made INDEPENDENTLY of
# ship.py's own comparator. Self-relative; writes only inside .fixture-scratch/.
# Pushes go to a throwaway local bare repo — never to a real remote.

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SHIP="$HERE/ship.py"
SCRATCH="$HERE/.fixture-scratch"
rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"

pass=0; fail=0
ok(){ echo "PASS  $1"; pass=$((pass+1)); }
no(){ echo "FAIL  $1 -- $2"; fail=$((fail+1)); }
check_rc(){ [ "$2" = "$3" ] && ok "$1 (exit $3)" || no "$1" "expected exit $3, got $2"; }
has(){ grep -q -- "$2" "$1" && ok "$3" || no "$3" "pattern not found: $2"; }
hasre(){ grep -qE -- "$2" "$1" && ok "$3" || no "$3" "regex not matched: $2"; }
clean_tree(){ [ -z "$(git -C "$1" status --porcelain)" ] && ok "$2" || no "$2" "tree dirty: $(git -C "$1" status --porcelain | head -3)"; }
clone(){ git clone --quiet "$REPO" "$SCRATCH/$1" || { echo "clone failed"; exit 9; }; }
# Independent of ship.py's table on purpose, and 1-indexed positional params so the lookup
# behaves the same under bash and zsh.
word_for(){ _i=$(( $1 - 19 )); set -- twenty twenty-one twenty-two twenty-three twenty-four \
  twenty-five twenty-six twenty-seven twenty-eight twenty-nine thirty thirty-one thirty-two \
  thirty-three thirty-four thirty-five thirty-six thirty-seven thirty-eight thirty-nine; \
  eval "echo \${$_i}"; }

echo "=== (a) replay v3.1.0 f3b148a ==="
python3 "$SHIP" replay --at f3b148a --scratch "$SCRATCH/a" --time > "$SCRATCH/a.log" 2>&1
check_rc "a: replay f3b148a exits clean" "$?" 0
has "$SCRATCH/a.log" "surfaces=9 · differs=0" "a: 9 surfaces, 0 differs"
has "$SCRATCH/a.log" "PARITY PASS" "a: PARITY PASS"
hasre "$SCRATCH/a.log" "docs/TUTORIAL\.md +DRIFT" "a: TUTORIAL drift detected + classified"
hasre "$SCRATCH/a.log" "^  TOTAL" "a: --time reports stages"
sed -n '/--- parity/,/^REPLAY/p' "$SCRATCH/a.log"

echo "=== (b) replay v3.0.0 fbe1e07 (rename ship) ==="
python3 "$SHIP" replay --at fbe1e07 --scratch "$SCRATCH/b" > "$SCRATCH/b.log" 2>&1
check_rc "b: replay fbe1e07 exits clean" "$?" 0
has "$SCRATCH/b.log" "surfaces=9 · differs=0 · drift=0" "b: 9 surfaces, 0 differs, 0 drift"
sed -n '/--- parity/,/^REPLAY/p' "$SCRATCH/b.log"

echo "=== (b2) parity re-checked INDEPENDENTLY of ship.py's comparator ==="
if diff -q <(git -C "$REPO" show fbe1e07:docs/TUTORIAL.md) "$SCRATCH/b/clone/docs/TUTORIAL.md" >/dev/null 2>&1
then ok "b2: TUTORIAL.md byte-identical to git show fbe1e07:"; else no "b2: TUTORIAL.md" "differs"; fi
if diff -q <(git -C "$REPO" show fbe1e07:plugins/notrest/README.md) "$SCRATCH/b/clone/plugins/notrest/README.md" >/dev/null 2>&1
then ok "b2: plugin README byte-identical to git show fbe1e07:"; else no "b2: plugin README" "differs"; fi
python3 - "$REPO" "$SCRATCH/b/clone" fbe1e07 > "$SCRATCH/indep.log" 2>&1 <<'PY'
import json, subprocess, sys
repo, clone, sha = sys.argv[1:4]
def show(p):
    return subprocess.run(["git", "-C", repo, "show", "%s:%s" % (sha, p)],
                          capture_output=True, text=True).stdout
PJ = "plugins/notrest/.claude-plugin/plugin.json"; MJ = ".claude-plugin/marketplace.json"
bad = []
if json.loads(show(PJ))["description"] != json.load(open(clone + "/" + PJ))["description"]:
    bad.append("plugin.json description")
def live(d): return [e for e in d["plugins"] if e["name"] == "notrest"][0]
wm, gm = json.loads(show(MJ)), json.load(open(clone + "/" + MJ))
if live(wm)["description"] != live(gm)["description"]:
    bad.append("marketplace description")
tomb = [e for e in gm["plugins"] if "tombstone" in e.get("source", "")]
if tomb and tomb[0]["version"] != "9.0.0":
    bad.append("tombstone de-pinned to %s" % tomb[0]["version"])
print("INDEP-FAIL: " + "; ".join(bad) if bad else "INDEP-OK")
PY
has "$SCRATCH/indep.log" "INDEP-OK" "b2: descriptions match + tombstone pinned (independent read)"

echo "=== (c) refusal battery ==="
clone c1
python3 "$SHIP" --repo "$SCRATCH/c1" ship --version 3.9.1 --message "fixture" >/dev/null 2>&1
check_rc "c1: no --gates-passed refuses" "$?" 10

clone c2
python3 - "$SCRATCH/c2/.claude-plugin/marketplace.json" <<'PY'
import json, re, sys
p = sys.argv[1]; t = open(p).read()
i = t.index('"./plugins/oracle-suite-tombstone"')
m = re.compile(r'("version"\s*:\s*")([^"]+)(")').search(t, i)
open(p, "w").write(t[:m.start()] + m.group(1) + "9.0.1" + m.group(3) + t[m.end():])
PY
python3 "$SHIP" --repo "$SCRATCH/c2" ship --version 3.9.1 --gates-passed --message "fixture" \
  >/dev/null 2>&1
check_rc "c2: tombstone tamper aborts" "$?" 11

clone c3
python3 - "$SCRATCH/c3/plugins/notrest/.claude-plugin/plugin.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["version"] = "3.0.9"
open(p, "w").write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
PY
python3 "$SHIP" --repo "$SCRATCH/c3" ship --version 3.9.1 --gates-passed --message "fixture" \
  >/dev/null 2>&1
check_rc "c3: manifest version skew aborts" "$?" 12

clone c4
printf '## 9.9.9 — 2000-01-01\n\nwrong header\n' > "$SCRATCH/c4-changelog.md"
python3 "$SHIP" --repo "$SCRATCH/c4" ship --version 3.9.1 --gates-passed --message "fixture" \
  --changelog-file "$SCRATCH/c4-changelog.md" >/dev/null 2>&1
check_rc "c4: bad changelog first line aborts" "$?" 15

clone c5
printf '#!/usr/bin/env python3\nprint("routing: VIOLATION — Fable rode in a subagent")\nraise SystemExit(4)\n' \
  > "$SCRATCH/c5/plugins/notrest/skills/spend/scripts/spend.py"
before=$(git -C "$SCRATCH/c5" rev-parse HEAD)
python3 "$SHIP" --repo "$SCRATCH/c5" ship --version 3.9.1 --gates-passed --message "fixture" \
  > "$SCRATCH/c5.log" 2>&1
check_rc "c5: spend exit 4 aborts the ship" "$?" 17
[ "$before" = "$(git -C "$SCRATCH/c5" rev-parse HEAD)" ] \
  && ok "c5: nothing committed" || no "c5: nothing committed" "HEAD moved"
has "$SCRATCH/c5.log" "rollback:" "c5: rollback ran after the abort"

clone c6
printf -- '\nThe twenty-sixth skill is a fixture artifact.\n' >> "$SCRATCH/c6/docs/TUTORIAL.md"
python3 "$SHIP" --repo "$SCRATCH/c6" ship --version 3.9.1 --gates-passed --message "fixture" \
  > "$SCRATCH/c6.log" 2>&1
check_rc "c6: count disagreement aborts" "$?" 13
has "$SCRATCH/c6.log" "twenty-sixth" "c6: die 13 quotes the offending token"
clean_tree "$SCRATCH/c6" "c6: rollback left a clean tree"

clone c7
python3 - "$SCRATCH/c7/docs/oracle-skill-flow.html" <<'PY'
import re, sys
p = sys.argv[1]; t = open(p).read()
m = re.search(r'<span class="sub">v[\d.]+ · \d+-skill harness[^<]*</span>', t)
open(p, "w").write(t[:m.end()] + "\n" + m.group(0) + t[m.end():])
PY
python3 "$SHIP" --repo "$SCRATCH/c7" ship --version 3.9.1 --gates-passed --message "fixture" \
  > "$SCRATCH/c7.log" 2>&1
check_rc "c7: duplicated flow stamp aborts" "$?" 14

clone c8
python3 "$SHIP" --repo "$SCRATCH/c8" ship --version 3.9.1 --gates-passed --message "fixture" \
  --coord-line "not a coord line" >/dev/null 2>&1
check_rc "c8: malformed coord line aborts" "$?" 16

clone c9
mkdir -p "$SCRATCH/fakebin"
printf '#!/bin/sh\necho "error: plugin not found" >&2\nexit 1\n' > "$SCRATCH/fakebin/claude"
chmod +x "$SCRATCH/fakebin/claude"
PATH="$SCRATCH/fakebin:$PATH" python3 "$SHIP" --repo "$SCRATCH/c9" ship --version 3.9.1 \
  --gates-passed --message "fixture" > "$SCRATCH/c9.log" 2>&1
check_rc "c9: validator exit 1 with 'not found' in stderr FAILS" "$?" 18
has "$SCRATCH/c9.log" "plugin not found" "c9: die 18 prints the validator stderr"
clean_tree "$SCRATCH/c9" "c9: rollback left a clean tree"

clone c10
PATH=/usr/bin:/bin python3 "$SHIP" --repo "$SCRATCH/c10" ship --version 3.9.1 --gates-passed \
  --message "fixture: cli absent" > "$SCRATCH/c10.log" 2>&1
check_rc "c10: absent claude CLI skips the gate" "$?" 0
has "$SCRATCH/c10.log" "claude CLI absent" "c10: absence is reported, not silent"

echo "=== (c11) nothing-staged + push exactness ==="
clone c11
python3 "$SHIP" --repo "$SCRATCH/c11" ship --version 3.9.1 --gates-passed \
  --message "fixture: first ship" > "$SCRATCH/c11a.log" 2>&1
check_rc "c11: first ship succeeds" "$?" 0
python3 "$SHIP" --repo "$SCRATCH/c11" ship --version 3.9.1 --gates-passed \
  --message "fixture: same version again" > "$SCRATCH/c11b.log" 2>&1
check_rc "c11: re-ship with nothing to stage aborts" "$?" 19

git init --quiet --bare "$SCRATCH/origin.git"
clone p1
git -C "$SCRATCH/p1" remote set-url origin "$SCRATCH/origin.git"
python3 "$SHIP" --repo "$SCRATCH/p1" ship --version 3.9.1 --gates-passed \
  --message "fixture: push" --push > "$SCRATCH/p1.log" 2>&1
check_rc "p1: --push to a throwaway bare origin succeeds" "$?" 0
has "$SCRATCH/p1.log" "pushed=yes" "p1: summary reports pushed=yes"
[ "$(git -C "$SCRATCH/origin.git" rev-parse refs/heads/main 2>/dev/null)" = "$(git -C "$SCRATCH/p1" rev-parse HEAD)" ] \
  && ok "p1: bare origin main == local HEAD (independent check)" \
  || no "p1: bare origin main == local HEAD" "mismatch"

clone p2
git -C "$SCRATCH/p2" remote set-url origin "$SCRATCH/origin.git"
git -C "$SCRATCH/p2" checkout --quiet --detach
python3 "$SHIP" --repo "$SCRATCH/p2" ship --version 3.9.2 --gates-passed \
  --message "fixture: detached" --push > "$SCRATCH/p2.log" 2>&1
check_rc "p2: --push on detached HEAD refuses" "$?" 20
has "$SCRATCH/p2.log" "refusing to guess" "p2: refusal names the reason"

echo "=== (d) count reconciliation ==="
clone d1
mkdir -p "$SCRATCH/d1/plugins/notrest/skills/fixture-fake"
printf -- '---\nname: fixture-fake\ndescription: "Fixture-only skill that exists to move the count."\n---\n\nFixture.\n' \
  > "$SCRATCH/d1/plugins/notrest/skills/fixture-fake/SKILL.md"
n=$(ls -1 "$SCRATCH/d1/plugins/notrest/skills" | wc -l | tr -d ' ')
want=$(word_for "$n")
python3 "$SHIP" --repo "$SCRATCH/d1" ship --version 3.9.1 --gates-passed \
  --message "fixture: count reconciliation" > "$SCRATCH/d1.log" 2>&1
check_rc "d: ship with $n skills exits clean" "$?" 0
for f in docs/TUTORIAL.md plugins/notrest/README.md \
         plugins/notrest/.claude-plugin/plugin.json .claude-plugin/marketplace.json; do
  grep -qi -- "$want" "$SCRATCH/d1/$f" \
    && ok "d: $f reads $want" || no "d: $f reads $want" "not found"
done
grep -qE "\b$n skills?\b" "$SCRATCH/d1/CLAUDE.md" \
  && ok "d: root CLAUDE.md numeral reads $n" || no "d: root CLAUDE.md numeral" "not $n"
grep -qE "counts: $n skills \($want\) · [0-9]+ surfaces agree · [1-9]" "$SCRATCH/d1.log" \
  && ok "d: rewrite was real (non-vacuous)" || no "d: rewrite was real" "no change counted"
ord_out=$(python3 - <<PY
import sys; sys.path.insert(0, "$HERE"); import ship
t = "the twenty-sixth skill and twenty-two skills"
out, _ = ship.respell(t, "thirty")
print("ORDINAL-OK" if "twenty-sixth" in out and "thirty skills" in out else "ORDINAL-FAIL: " + out)
PY
)
[ "$ord_out" = "ORDINAL-OK" ] && ok "d: ordinal 'twenty-sixth' survives the rewriter" \
  || no "d: ordinal survives the rewriter" "$ord_out"

echo "=== (f) reordered-key manifest (the tombstone de-pin repro) ==="
clone f1
python3 - "$SCRATCH/f1/.claude-plugin/marketplace.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
out = []
for e in d["plugins"]:
    if e.get("name") == "notrest":      # version BEFORE source: the anchor-walk repro
        head = [("name", e["name"]), ("version", e["version"]), ("source", e["source"])]
        e = dict(head + [(k, v) for k, v in e.items() if k not in ("name", "version", "source")])
    out.append(e)
d["plugins"] = out
open(p, "w").write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
PY
python3 "$SHIP" --repo "$SCRATCH/f1" ship --version 3.9.1 --gates-passed \
  --message "fixture: reordered keys" > "$SCRATCH/f1.log" 2>&1
check_rc "f1: reordered-key manifest ships correctly" "$?" 0
python3 - "$SCRATCH/f1/.claude-plugin/marketplace.json" "$SCRATCH/f1/plugins/notrest/.claude-plugin/plugin.json" > "$SCRATCH/f1chk.log" <<'PY'
import json, sys
m = json.load(open(sys.argv[1])); p = json.load(open(sys.argv[2]))
live = [e for e in m["plugins"] if e["name"] == "notrest"][0]
tomb = [e for e in m["plugins"] if "tombstone" in e.get("source", "")][0]
bad = []
if tomb["version"] != "9.0.0": bad.append("TOMBSTONE BUMPED to %s" % tomb["version"])
for label, v in (("metadata", m["metadata"]["version"]), ("entry", live["version"]),
                 ("plugin.json", p["version"])):
    if v != "3.9.1": bad.append("%s=%s" % (label, v))
print("F3-FAIL: " + "; ".join(bad) if bad else "F3-OK")
PY
has "$SCRATCH/f1chk.log" "F3-OK" "f1: tombstone still 9.0.0, all three bumped"

clone f2
python3 - "$SCRATCH/f2/.claude-plugin/marketplace.json" "$SCRATCH/f2/plugins/notrest/.claude-plugin/plugin.json" <<'PY'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
out = []
for e in d["plugins"]:
    if e.get("name") == "notrest":
        head = [("name", e["name"]), ("version", e["version"]), ("source", e["source"])]
        e = dict(head + [(k, v) for k, v in e.items() if k not in ("name", "version", "source")])
    out.append(e)
d["plugins"] = out
open(p, "w").write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
q = sys.argv[2]; j = json.load(open(q)); j["version"] = "2.0.0"
open(q, "w").write(json.dumps(j, indent=2, ensure_ascii=False) + "\n")
PY
python3 "$SHIP" --repo "$SCRATCH/f2" ship --version 3.9.1 --gates-passed \
  --message "fixture: reordered + skew" >/dev/null 2>&1
check_rc "f2: reordered keys WITH version skew still aborts" "$?" 12

echo "=== (e) legacy replays — pre-rename vocabulary (N-skill suite / Manifest: oracle-suite) ==="
for sha in 4c78590 f115695 5c422ed; do
  python3 "$SHIP" --legacy-paths replay --at "$sha" --scratch "$SCRATCH/e-$sha" \
    > "$SCRATCH/e-$sha.log" 2>&1
  check_rc "e: legacy replay $sha exits clean" "$?" 0
  { grep -q "surfaces=9 · differs=0" "$SCRATCH/e-$sha.log" && \
    grep -q "PARITY PASS" "$SCRATCH/e-$sha.log"; } \
    && ok "e: $sha PARITY PASS, 9 surfaces, 0 differs" \
    || no "e: $sha PARITY PASS" "$(grep '^REPLAY' "$SCRATCH/e-$sha.log")"
done
grep -h "^REPLAY" "$SCRATCH"/e-*.log

echo "=== summary ==="
echo "PASS=$pass FAIL=$fail"
[ "$fail" = "0" ] || exit 1
