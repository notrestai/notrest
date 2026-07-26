#!/usr/bin/env bash
# journey-fixture — the journey render, asserted against THE REAL REPO.
#
# The river fixture can build a synthetic estate because a river is a drawing of
# data. The journey is a drawing of THIS harness's own front door — router.sh,
# oracle's intake bullet, every skill's chain lines — so the only fixture worth
# having runs against the real tree and asserts arithmetic that must hold there:
# every skill on disk gets a node, every router verb lands as a routed skill,
# routed + by-name-only accounts for all of them, and the page re-renders byte
# for byte. Then a synthetic phase proves the DEGRADE path: a plugin tree with no
# router.sh draws no shapes and says so instead of quietly drawing nothing.
#
# Exit 0 = every assertion held. No network, no model calls, no repo writes
# (every render goes to a temp dir).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
GRAPH="$HERE/graph.py"
RC="$HERE/../../doctor/scripts/render-check.sh"
ROOT="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] || ROOT="$(cd "$HERE/../../../../.." && pwd)"
PLUG="$ROOT/plugins/notrest"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/notrest-journey-fixture.XXXXXX")"
PASSES=0
FAILS=0

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

ok()  { PASSES=$((PASSES+1)); echo "PASS  $1"; }
bad() { FAILS=$((FAILS+1));   echo "FAIL  $1"; }
chk() { # chk <label> <expected> <actual>
  if [ "$2" = "$3" ]; then ok "$1 = $2"; else bad "$1: expected $2, got $3"; fi
}
ge()  { # ge <label> <floor> <actual>
  if [ "$3" -ge "$2" ] 2>/dev/null; then ok "$1 = $3 (>= $2)"
  else bad "$1: expected at least $2, got $3"; fi
}
val() { python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split('.'):
    d = d[int(k)] if k.lstrip('-').isdigit() else d[k]
print(d)" "$1" "$2" 2>/dev/null || echo "<ERR>"; }

[ -d "$PLUG/skills" ] || { echo "no skill tree at $PLUG/skills — wrong root: $ROOT"; exit 2; }

echo "── phase A: the real repo ──────────────────────────────────────────────"
J="$TMP/journey.json"
H="$TMP/journey.html"
python3 "$GRAPH" journey --root "$ROOT" --out "$H" > "$TMP/a.out" 2>&1
A=$?
if [ "$A" -eq 0 ] && [ -f "$J" ] && [ -f "$H" ]; then
  ok "journey exits 0 and writes both files"
else
  bad "journey run: exit $A"; sed 's/^/      /' "$TMP/a.out"
fi
sed 's/^/      /' "$TMP/a.out"

# ---- the counts, against what is actually on disk
DISK_SKILLS=$(find "$PLUG/skills" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')
ROUTER_VERBS=$(grep -oE '\bSKILL=[a-z][a-z0-9-]*' "$PLUG/hooks/router.sh" 2>/dev/null \
               | sort -u | wc -l | tr -d ' ')

ge  "router shape nodes"        14 "$(val "$J" counts.shapes)"
chk "skill nodes"               28 "$(val "$J" counts.skills)"
chk "skill nodes == SKILL.md files on disk" "$DISK_SKILLS" "$(val "$J" counts.skills)"
ge  "routed skills"    "$ROUTER_VERBS" "$(val "$J" counts.routed)"
ge  "phrase pills"              40 "$(val "$J" counts.phrases)"
ge  "chain arrows"              20 "$(val "$J" counts.chains)"

ACCT=$(python3 - "$J" <<'PY'
import json,sys
d = json.load(open(sys.argv[1]))
c = d["counts"]
print("%s" % (c["routed"] + c["by_name_only"] == c["skills"]))
PY
)
chk "routed + by-name-only accounts for every skill" "True" "$ACCT"

# every skill directory on disk must own exactly one node — nothing silently dropped
MISSING=$(python3 - "$J" "$PLUG/skills" <<'PY'
import json,os,sys
d = json.load(open(sys.argv[1]))
drawn = {n["name"] for n in d["nodes"] if n["kind"] == "skill"}
disk = {n for n in os.listdir(sys.argv[2])
        if os.path.isfile(os.path.join(sys.argv[2], n, "SKILL.md"))}
print(",".join(sorted(disk ^ drawn)) or "-")
PY
)
chk "every skill dir drawn, nothing invented" "-" "$MISSING"

# every verb the router can emit must appear as a ROUTED skill on the page
UNROUTED=$(python3 - "$J" "$PLUG/hooks/router.sh" <<'PY'
import json,re,sys
d = json.load(open(sys.argv[1]))
verbs = set(re.findall(r"\bSKILL=([a-z][a-z0-9-]*)", open(sys.argv[2]).read()))
routed = {n["name"] for n in d["nodes"] if n["kind"] == "skill" and n["routed"]}
print(",".join(sorted(verbs - routed)) or "-")
PY
)
chk "every router verb lands as a routed skill" "-" "$UNROUTED"

# chain arrows may only join nodes that exist
DANGLE=$(python3 - "$J" <<'PY'
import json,sys
d = json.load(open(sys.argv[1]))
ids = {n["id"] for n in d["nodes"]} | {p["id"] for p in d["pills"]}
print(sum(1 for e in d["edges"] if e["from"] not in ids or e["to"] not in ids))
PY
)
chk "dangling edges" 0 "$DANGLE"

echo "── phase B: the reproducibility law ────────────────────────────────────"
cp "$H" "$TMP/first.html"; cp "$J" "$TMP/first.json"
python3 "$GRAPH" journey --root "$ROOT" --out "$H" >/dev/null 2>&1
if cmp -s "$TMP/first.html" "$H" && cmp -s "$TMP/first.json" "$J"; then
  ok "re-render is byte-identical (sorted, no clock read)"
else
  bad "re-render differs — the render is not reproducible"
fi
chk "stamp source" "git-head" "$(val "$J" stamp_from)"
HEAD="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null)"
STAMP="$(val "$J" generated)"
if [ -n "$HEAD" ] && [ "${STAMP%%+*}" = "$HEAD" ]; then
  ok "stamped from git HEAD ($STAMP) — not a wall clock, not an mtime"
else
  bad "stamp '$STAMP' does not match git HEAD '$HEAD'"
fi
if grep -q "$HEAD" "$H"; then ok "the page carries the commit stamp"
else bad "the commit stamp never reached the page"; fi

echo "── phase C: the page's own laws ────────────────────────────────────────"
if grep -q "prefers-color-scheme: dark" "$H" \
   && grep -q 'data-theme="dark"' "$H" \
   && grep -q 'data-theme="light"' "$H"; then
  ok "both themes present (media query + explicit data-theme overrides)"
else
  bad "theme hooks missing from journey.html"
fi
EXT=$(grep -oE '(src|href)="[^"]+"|https?://[^"'"'"' )]+' "$H" \
      | grep -v 'www.w3.org/2000/svg' | wc -l | tr -d ' ')
chk "external assets referenced" 0 "$EXT"
SIZE=$(wc -c < "$H" | tr -d ' ')
if [ "$SIZE" -lt 204800 ]; then ok "journey.html is $SIZE bytes (< 200KB)"
else bad "journey.html is $SIZE bytes — over the 200KB target"; fi
for TOKEN in "WHAT SOMEONE TYPES" "SHAPE — router.sh" "BY NAME ONLY"; do
  if grep -q "$TOKEN" "$H"; then ok "column caption present: $TOKEN"
  else bad "missing column caption: $TOKEN"; fi
done

echo "── phase D: the render gate (serve + HTTP 200) ─────────────────────────"
if [ -f "$RC" ]; then
  RCOUT="$(bash "$RC" "$H" 2>&1)"
  RCX=$?
  PORT="$(printf '%s\n' "$RCOUT" | sed -n 's/^PORT: *//p')"
  if [ "$RCX" -eq 0 ] && printf '%s' "$RCOUT" | grep -q "HTTP 200"; then
    ok "render-check served journey.html: HTTP 200"
  else
    bad "render-check exit $RCX"; printf '%s\n' "$RCOUT" | sed 's/^/      /'
  fi
  [ -n "$PORT" ] && bash "$RC" --close "$PORT" >/dev/null 2>&1
else
  bad "render-check.sh not found at $RC"
fi

echo "── phase E: the degrade path (a plugin tree with no router) ────────────"
D="$TMP/mini"
mkdir -p "$D/plugins/notrest/skills/alpha" "$D/plugins/notrest/skills/beta" \
         "$D/plugins/notrest/skills/oracle"
printf -- '---\nname: alpha\n---\n# alpha\n\n## Chains\n\nHand off to `/beta` when done.\n' \
  > "$D/plugins/notrest/skills/alpha/SKILL.md"
printf -- '---\nname: beta\n---\n# beta\n\nNo chains section here at all.\n' \
  > "$D/plugins/notrest/skills/beta/SKILL.md"
printf -- '---\nname: oracle\n---\n# oracle\n\n- **Route to the right tool:** pick one — do a thing → `/alpha`\n' \
  > "$D/plugins/notrest/skills/oracle/SKILL.md"

python3 "$GRAPH" journey --root "$D" --out "$TMP/mini.html" > "$TMP/e.out" 2>&1
EX=$?
MJ="$TMP/mini.json"
chk "no-router tree still exits 0" 0 "$EX"
chk "shape nodes without a router" 0 "$(val "$MJ" counts.shapes)"
chk "skills drawn"                 3 "$(val "$MJ" counts.skills)"
chk "intake route still parsed"    1 "$(val "$MJ" counts.intake_phrases)"
chk "alpha's chain arrow parsed"   1 "$(val "$MJ" counts.chains)"
chk "beta + oracle land by name only" 2 "$(val "$MJ" counts.by_name_only)"
if grep -q "no hooks/router.sh" "$TMP/e.out"; then
  ok "the missing router is DISCLOSED, not silently drawn empty"
else
  bad "no note about the missing router"; sed 's/^/      /' "$TMP/e.out"
fi
if grep -q "no Chains / Finishing-up section to parse in" "$TMP/e.out"; then
  ok "skills with no chains section are named, not guessed at"
else bad "the unparsed-chains disclosure is missing"; fi
if grep -q "(no git HEAD)" "$TMP/mini.html"; then
  ok "outside git the page says it carries no commit stamp"
else bad "a non-repo render did not disclose the missing stamp"; fi

python3 "$GRAPH" journey --root "$TMP" --out "$TMP/none.html" >/dev/null 2>&1
chk "a root with no skill tree exits 2" 2 "$?"

echo "── phase F: the stamp is the COMMIT, not an mtime ──────────────────────"
# Why this matters: mtimes are rewritten by every clone, so an mtime stamp makes
# two checkouts of the same commit render differently. Proved on a throwaway repo
# rather than the real one — a fixture must never touch a tree it does not own.
G="$TMP/gitmini"
cp -R "$D" "$G"
GC="git -C $G -c user.email=fixture@invalid -c user.name=fixture -c commit.gpgsign=false"
( $GC init -q 2>/dev/null || git -C "$G" init -q ) >/dev/null 2>&1
$GC add -A >/dev/null 2>&1
$GC commit -qm "fixture tree" >/dev/null 2>&1
GHEAD="$(git -C "$G" rev-parse --short HEAD 2>/dev/null)"
if [ -z "$GHEAD" ]; then
  bad "could not stand up a throwaway git repo — stamp assertions skipped"
else
  python3 "$GRAPH" journey --root "$G" --out "$TMP/g1.html" >/dev/null 2>&1
  chk "clean tree stamps the bare commit" "$GHEAD" "$(val "$TMP/g1.json" generated)"
  touch "$G/plugins/notrest/skills/alpha/SKILL.md"
  python3 "$GRAPH" journey --root "$G" --out "$TMP/g2.html" >/dev/null 2>&1
  chk "a touched input does NOT move the stamp" "$GHEAD" "$(val "$TMP/g2.json" generated)"
  if cmp -s "$TMP/g1.html" "$TMP/g2.html"; then
    ok "a touched input re-renders byte-identically (mtime is not an input)"
  else bad "touching a file changed the render — an mtime leaked into the page"; fi
  printf '\nHand off to `/oracle` too.\n' >> "$G/plugins/notrest/skills/alpha/SKILL.md"
  python3 "$GRAPH" journey --root "$G" --out "$TMP/g3.html" >/dev/null 2>&1
  chk "an EDITED input marks the stamp dirty" "${GHEAD}+dirty" "$(val "$TMP/g3.json" generated)"
  chk "the edit is actually read (a second chain arrow)" 2 "$(val "$TMP/g3.json" counts.chains)"
fi

echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
