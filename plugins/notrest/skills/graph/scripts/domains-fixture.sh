#!/usr/bin/env bash
# domains-fixture — the lane partitioner, asserted on graphs whose shape is known
# exactly.
#
# The river fixture builds a synthetic estate because a river is a drawing of
# data; the journey runs against the real repo because it draws this harness's
# own door. `domains` is arithmetic over a link graph, so the fixture that means
# anything is one where the RIGHT ANSWER IS KNOWN BEFORE THE COMMAND RUNS —
# scratch repos with hand-built edges, every count checked against a graph drawn
# on purpose. Two properties are asserted everywhere, not just where they are
# interesting: lanes are DISJOINT (a file in two lanes is the collision this
# command exists to prevent) and every scoped file is ACCOUNTED FOR (lanes plus
# seat_held equals the scope — a dropped file is a lane silently losing work).
#
# The rulings this fixture pins, each earned:
#   ORDER   — hubs out FIRST, components SECOND. Phase D is the star: N files all
#             linking one manifest. Components-first returns ONE lane and the
#             command is decorative; hubs-first returns N.
#   THRESH  — hub iff degree >= max(4, 3 x median degree). Phase E proves BOTH
#             arms: a 20-file scope where degree-8 is held and degree-5 is not
#             (the multiplier binds), and a 9-file scope where degree-4 is held
#             and degree-3 is not (the floor binds).
#   EMPTY   — an empty scope exits 2 three ways. A silent lanes:[] is the moment
#             a seat shrugs and hand-partitions from memory instead.
#
# Exit 0 = every assertion held. No network, no model calls, no writes outside
# mktemp (the one real-repo phase READS this repo and writes nothing).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
GRAPH="$HERE/graph.py"
ROOT="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] || ROOT="$(cd "$HERE/../../../../.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/notrest-domains-fixture.XXXXXX")"
PASSES=0
FAILS=0

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

ok()  { PASSES=$((PASSES+1)); echo "PASS  $1"; }
bad() { FAILS=$((FAILS+1));   echo "FAIL  $1"; }
chk() { # chk <label> <expected> <actual>
  if [ "$2" = "$3" ]; then ok "$1 = $2"; else bad "$1: expected $2, got $3"; fi
}
has() { # has <label> <needle> <file>
  if grep -qF -- "$2" "$3"; then ok "$1"; else bad "$1: '$2' not in $3"; fi
}
hasnt() { # hasnt <label> <needle> <file>
  if grep -qF -- "$2" "$3"; then bad "$1: '$2' IS in $3"; else ok "$1"; fi
}

gitq() { d="$1"; shift; git -C "$d" -c user.email=fixture@invalid \
         -c user.name=fixture -c commit.gpgsign=false "$@"; }
mkrepo() { mkdir -p "$1"; gitq "$1" init -q >/dev/null 2>&1; }
seal()  { gitq "$1" add -A >/dev/null 2>&1; gitq "$1" commit -qm "${2:-seal}" >/dev/null 2>&1; }

# run <label-file-stem> <dir> [args...] -> sets RC, writes $TMP/<stem>.out (+ .json)
run() {
  stem="$1"; shift
  python3 "$GRAPH" domains "$@" > "$TMP/$stem.out" 2> "$TMP/$stem.err"
  RC=$?
  return 0
}
runj() { # same, but --json into $TMP/<stem>.json
  stem="$1"; shift
  python3 "$GRAPH" domains "$@" --json > "$TMP/$stem.json" 2> "$TMP/$stem.err"
  RC=$?
  return 0
}

# jq() { } — no jq on a clean machine; python3 stdlib is the whole dependency set.
J() { # J <json-file> <expr over d>
  python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))" "$1" "$2" 2>/dev/null || echo "<ERR>"
}

# every phase runs this: lanes disjoint, nothing lost, nothing invented
LAWS() { # LAWS <label> <json-file>
  R="$(python3 - "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
lanes = d["lanes"]
held = [h["file"] for h in d["seat_held"]]
seen, dupes = set(), []
for l in lanes:
    for f in l["files"]:
        if f in seen:
            dupes.append(f)
        seen.add(f)
    if l["files"] != sorted(l["files"]):
        dupes.append("UNSORTED:%s" % l["id"])
bad = []
if dupes:
    bad.append("a file in two lanes: %s" % ",".join(sorted(set(dupes))))
both = sorted(seen & set(held))
if both:
    bad.append("in a lane AND seat-held: %s" % ",".join(both))
if len(seen) + len(held) != d["scope_count"]:
    bad.append("accounting: %d lane files + %d held != scope_count %d"
               % (len(seen), len(held), d["scope_count"]))
ids = [l["id"] for l in lanes]
if ids != list(range(1, len(lanes) + 1)):
    bad.append("lane ids not 1..n: %s" % ids)
for l in lanes:
    for b in l["boundary"]:
        if b["from"] not in l["files"]:
            bad.append("boundary from outside its own lane: %s" % b["from"])
        if b["to"] in l["files"]:
            bad.append("boundary to a file in the SAME lane: %s" % b["to"])
print("; ".join(bad) or "-")
PY
)"
  chk "$1: lanes disjoint, complete, self-consistent" "-" "$R"
}

echo "── phase A: two disjoint pairs — 2 lanes, no boundary ──────────────────"
A="$TMP/pairs"; mkrepo "$A"
printf 'see [x](a2.md)\n'          > "$A/a1.md"
printf 'leaf\n'                    > "$A/a2.md"
printf 'see [x](b2.md) and more\n' > "$A/b1.md"
printf 'leaf\n'                    > "$A/b2.md"
seal "$A"
runj pairs --root "$A" --all
chk "exit code"        0 "$RC"
chk "scope count"      4 "$(J "$TMP/pairs.json" 'd["scope_count"]')"
chk "lanes"            2 "$(J "$TMP/pairs.json" 'len(d["lanes"])')"
chk "files per lane" "2,2" "$(J "$TMP/pairs.json" '",".join(str(len(l["files"])) for l in d["lanes"])')"
chk "boundary lines"   0 "$(J "$TMP/pairs.json" 'sum(len(l["boundary"]) for l in d["lanes"])')"
chk "seat-held"        0 "$(J "$TMP/pairs.json" 'len(d["seat_held"])')"
chk "each pair stayed whole" "True" \
    "$(J "$TMP/pairs.json" 'sorted(sorted(l["files"]) for l in d["lanes"]) == [["a1.md","a2.md"],["b1.md","b2.md"]]')"
LAWS "phase A" "$TMP/pairs.json"

echo "── phase B: a chain is never split ─────────────────────────────────────"
B="$TMP/chain"; mkrepo "$B"
printf 'to [x](c2.md)\n' > "$B/c1.md"
printf 'to [x](c3.md)\n' > "$B/c2.md"
printf 'end\n'           > "$B/c3.md"
printf 'alone\n'         > "$B/d.md"
seal "$B"
runj chain2 --root "$B" --all --lanes 2
chk "chain+isolate, --lanes 2: exit"  0 "$RC"
chk "chain+isolate, --lanes 2: lanes" 2 "$(J "$TMP/chain2.json" 'len(d["lanes"])')"
chk "the 3-chain survives as one lane" "True" \
    "$(J "$TMP/chain2.json" '["c1.md","c2.md","c3.md"] in [l["files"] for l in d["lanes"]]')"
chk "the isolate is its own lane" "True" \
    "$(J "$TMP/chain2.json" '["d.md"] in [l["files"] for l in d["lanes"]]')"
chk "no merge note (2 asked, 2 exist)" 0 \
    "$(J "$TMP/chain2.json" 'sum(1 for n in d["notes"] if "merged" in n)')"
LAWS "phase B" "$TMP/chain2.json"

# the sharp version: ONE component, two lanes asked for. Splitting it would
# manufacture the collision; the answer is 1 lane and an honest note.
C1="$TMP/onecomp"; mkrepo "$C1"
printf 'to [x](c2.md)\n' > "$C1/c1.md"
printf 'to [x](c3.md)\n' > "$C1/c2.md"
printf 'end\n'           > "$C1/c3.md"
seal "$C1"
runj split --root "$C1" --all --lanes 2
chk "one component, --lanes 2: exit"  0 "$RC"
chk "one component, --lanes 2: lanes" 1 "$(J "$TMP/split.json" 'len(d["lanes"])')"
chk "the component is intact" "True" \
    "$(J "$TMP/split.json" 'd["lanes"][0]["files"] == ["c1.md","c2.md","c3.md"]')"
has "the refusal to split is DISCLOSED" "manufactures the shared-file collision" "$TMP/split.json"
LAWS "phase B2" "$TMP/split.json"

echo "── phase C: --lanes 3 on 2 components — 2 lanes, honest note ───────────"
runj lanes3 --root "$A" --all --lanes 3
chk "exit"  0 "$RC"
chk "lanes returned, not padded" 2 "$(J "$TMP/lanes3.json" 'len(d["lanes"])')"
has "the shortfall is named" "asked for 3 lane(s); the graph yields 2" "$TMP/lanes3.json"
chk "no empty lane was invented" 0 \
    "$(J "$TMP/lanes3.json" 'sum(1 for l in d["lanes"] if not l["files"])')"
LAWS "phase C" "$TMP/lanes3.json"

echo "── phase D: THE STAR — hubs out first, or the tool is decorative ───────"
# 8 files, all linking one manifest, nothing else. Components computed on the
# FULL graph give ONE lane (everything reaches everything through the manifest)
# and --lanes can only merge, so the command would be a no-op on exactly the
# tree it exists for. Hubs-first gives 8.
D="$TMP/star"; mkrepo "$D"
printf 'the manifest\n' > "$D/hub.md"
for i in 1 2 3 4 5 6 7 8; do
  printf 'spoke %s reads [m](hub.md)\n%s\n' "$i" "$(printf 'x%.0s' $(seq 1 $((i*7))))" \
    > "$D/s$i.md"
done
seal "$D"
runj star --root "$D" --all
chk "exit"                 0 "$RC"
chk "scope"                9 "$(J "$TMP/star.json" 'd["scope_count"]')"
chk "the manifest is seat-held, alone" "hub.md" \
    "$(J "$TMP/star.json" '",".join(h["file"] for h in d["seat_held"])')"
chk "its degree"           8 "$(J "$TMP/star.json" 'd["seat_held"][0]["degree"]')"
chk "lanes after extraction (1 would mean components ran first)" 8 \
    "$(J "$TMP/star.json" 'len(d["lanes"])')"
chk "every lane holds exactly one spoke" "True" \
    "$(J "$TMP/star.json" 'all(len(l["files"]) == 1 for l in d["lanes"])')"
chk "every lane boundaries to the hub" 8 \
    "$(J "$TMP/star.json" 'sum(1 for l in d["lanes"] for b in l["boundary"] if b["to"]=="hub.md")')"
chk "and marks it seat-held, not a lane id" "True" \
    "$(J "$TMP/star.json" 'all(b["lane"]=="seat-held" for l in d["lanes"] for b in l["boundary"])')"
has "the hub rule states its own threshold" "hub rule at degree >= 4" "$TMP/star.json"
LAWS "phase D" "$TMP/star.json"

# and the star is mergeable — with the lane != domain disclosure on every merge
runj star3 --root "$D" --all --lanes 3
chk "star --lanes 3: lanes" 3 "$(J "$TMP/star3.json" 'len(d["lanes"])')"
chk "star --lanes 3: all 8 spokes still placed, none twice" "True" \
    "$(J "$TMP/star3.json" 'sorted(f for l in d["lanes"] for f in l["files"]) == sorted("s%d.md"%i for i in range(1,9))')"
MERGED=$(python3 - "$TMP/star3.json" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1]))
per = {}
for n in d["notes"]:
    m = re.match(r"lane (\d+) = (\d+) components merged", n)
    if m:
        per[int(m.group(1))] = int(m.group(2))
print(sum(per.get(l["id"], 1) for l in d["lanes"]))
PY
)
chk "merged-lane notes account for all 8 components" 8 "$MERGED"
has "a merged lane says it is NOT one domain" "not one" "$TMP/star3.json"
LAWS "phase D2" "$TMP/star3.json"

echo "── phase E: the threshold, both arms ───────────────────────────────────"
# arm 1 — the MULTIPLIER binds. 20 files: h has degree 8, m has degree 5, and
# the median degree is 2, so the bar is max(4, 3x2) = 6. h is held; m rides in a
# lane. Under the replaced 0.30-of-scope rule the bar would have been 6 here too
# but 60 at 200 files — which is how a manifest linked by 25 files rode into a
# lane precisely when lanes matter most.
E="$TMP/median"; mkrepo "$E"
printf 'the hub\n' > "$E/h.md"
printf 'the mid\n' > "$E/m.md"
for i in 1 2 3 4 5; do printf 'reads [a](h.md) and [b](m.md)\n' > "$E/s0$i.md"; done
for i in 6 7 8;     do printf 'reads [a](h.md)\n'               > "$E/s0$i.md"; done
for i in 1 2 3 4 5 6 7 8 9; do printf 'next [n](p%s.md)\n' "$((i+1))" > "$E/p$i.md"; done
printf 'chain end\n' > "$E/p10.md"
seal "$E"
runj med --root "$E" --all
chk "scope"        20 "$(J "$TMP/med.json" 'd["scope_count"]')"
chk "median degree is 2 → bar is 6" "True" \
    "$(J "$TMP/med.json" 'any("degree >= 6" in n and "median in-scope degree 2" in n for n in d["notes"])')"
chk "the degree-8 file IS held" "h.md" \
    "$(J "$TMP/med.json" '",".join(x["file"] for x in d["seat_held"])')"
chk "the degree-5 file is NOT held (it rides in a lane)" "True" \
    "$(J "$TMP/med.json" '"m.md" in [f for l in d["lanes"] for f in l["files"]]')"
LAWS "phase E1" "$TMP/med.json"

# arm 2 — the FLOOR binds. 9 files, median degree 1, so 3x median is 3 and the
# floor of 4 is what decides: degree 4 is held, degree 3 is not. Without the
# floor a scope this sparse would call a degree-3 file a hub.
F="$TMP/floor"; mkrepo "$F"
printf 'four in\n'  > "$F/f.md"
printf 'three in\n' > "$F/g.md"
for i in 1 2 3 4; do printf 'reads [a](f.md)\n' > "$F/q$i.md"; done
for i in 1 2 3;   do printf 'reads [b](g.md)\n' > "$F/r$i.md"; done
seal "$F"
runj floor --root "$F" --all
chk "scope"        9 "$(J "$TMP/floor.json" 'd["scope_count"]')"
chk "median degree is 1 → the floor decides the bar" "True" \
    "$(J "$TMP/floor.json" 'any("degree >= 4" in n and "median in-scope degree 1" in n for n in d["notes"])')"
chk "degree 4 IS held" "f.md" "$(J "$TMP/floor.json" '",".join(x["file"] for x in d["seat_held"])')"
chk "degree 3 is NOT held" "True" \
    "$(J "$TMP/floor.json" '"g.md" in [f for l in d["lanes"] for f in l["files"]]')"
LAWS "phase E2" "$TMP/floor.json"

# arm 3 — the two rules DISAGREE here, so this is the one that would catch a
# quiet return to a share-of-scope threshold. 20 files, median degree 1, one
# file at degree 5. Median rule: bar = max(4, 3x1) = 4, so it is held and the
# scope falls into 12 lanes. A 0.30-of-scope rule: bar = max(4, 6) = 6, so it
# rides into a lane and drags its five spokes with it — 8 lanes. Outcome, not
# wording: no note text is consulted.
S3="$TMP/scale"; mkrepo "$S3"
printf 'five in\n' > "$S3/k.md"
for i in 1 2 3 4 5; do printf 'reads [a](k.md)\n' > "$S3/t$i.md"; done
for i in 1 3 5 7 9 11 13; do
  printf 'pair [x](v%s.md)\n' "$((i+1))" > "$S3/v$i.md"
  printf 'end\n'                         > "$S3/v$((i+1)).md"
done
seal "$S3"
runj scale --root "$S3" --all
chk "scope" 20 "$(J "$TMP/scale.json" 'd["scope_count"]')"
chk "the degree-5 file IS held at 20 files (a share rule would not hold it)" "k.md" \
    "$(J "$TMP/scale.json" '",".join(x["file"] for x in d["seat_held"])')"
chk "so the spokes fall into their own lanes" 12 "$(J "$TMP/scale.json" 'len(d["lanes"])')"
LAWS "phase E3" "$TMP/scale.json"

echo "── phase F: the --json key set, exactly ────────────────────────────────"
KEYS=$(J "$TMP/star.json" '",".join(d.keys())')
chk "top-level keys, in order" "root,scope_count,lanes,seat_held,notes" "$KEYS"
chk "lane keys, in order"      "id,files,bytes,boundary" \
    "$(J "$TMP/star.json" '",".join(d["lanes"][0].keys())')"
chk "boundary keys, in order"  "from,to,lane" \
    "$(J "$TMP/star.json" '",".join(d["lanes"][0]["boundary"][0].keys())')"
chk "seat_held keys, in order" "file,degree" \
    "$(J "$TMP/star.json" '",".join(d["seat_held"][0].keys())')"
chk "notes is a list of strings" "True" \
    "$(J "$TMP/star.json" 'isinstance(d["notes"], list) and all(isinstance(n,str) for n in d["notes"])')"
chk "bytes is a real byte total" "True" \
    "$(J "$TMP/star.json" 'all(l["bytes"] > 0 for l in d["lanes"])')"
chk "root is the absolute root" "True" "$(J "$TMP/star.json" 'd["root"].startswith("/")')"
chk "--json prints JSON and nothing else" "" "$(cat "$TMP/star.err")"

echo "── phase G: the human block is commission-pasteable ────────────────────"
run starh --root "$D" --all
chk "human mode exit" 0 "$RC"
has "boundary line format"  "boundary: s1.md -> hub.md (seat-held)" "$TMP/starh.out"
has "the read/never-edit rule is stated" "you may READ that file, never edit it" "$TMP/starh.out"
has "seat-held block carries degrees" "degree 8" "$TMP/starh.out"
has "the honest limit rides along" "knows LINKS, not SEMANTICS" "$TMP/starh.out"
run lane2h --root "$A" --all --lanes 3
has "a lane header carries id, count and bytes" "lane 1 · 2 file(s) ·" "$TMP/lane2h.out"

echo "── phase H: what it REFUSES ────────────────────────────────────────────"
run miss --root "$A" --paths a1.md nope.md
chk "a named path that does not exist: exit" 2 "$RC"
has "…and it is NAMED"      "nope.md" "$TMP/miss.err"
has "…with the reason"      "does not partition fictions" "$TMP/miss.err"

NG="$TMP/nogit"; mkdir -p "$NG"; printf 'x\n' > "$NG/a.md"
run nogit --root "$NG" --all
chk "a non-git root: exit" 2 "$RC"
has "…and says why" "not a git repo" "$TMP/nogit.err"

run noscope --root "$A"
chk "no scope flag at all: exit" 2 "$RC"
has "…with usage" "--paths" "$TMP/noscope.err"
run twoscope --root "$A" --all --changed
chk "two scope flags: exit" 2 "$RC"

run badlanes --root "$A" --all --lanes 0
chk "--lanes 0: exit" 2 "$RC"
has "…named" "--lanes must be 1 or more" "$TMP/badlanes.err"

# EMPTY SCOPE IS FATAL, three ways. A silent lanes:[] is the moment a seat
# shrugs and hand-partitions from memory instead — the failure this prevents.
run cleanchg --root "$A" --changed
chk "empty scope (a clean tree, --changed): exit" 2 "$RC"
has "…named" "nothing in scope" "$TMP/cleanchg.err"

EMPTY="$TMP/emptyrepo"; mkrepo "$EMPTY"
run emptyall --root "$EMPTY" --all
chk "empty scope (an empty repo, --all): exit" 2 "$RC"
has "…named" "nothing in scope" "$TMP/emptyall.err"

IG="$TMP/ignored"; mkrepo "$IG"
printf 'blank/\n' > "$IG/.gitignore"
printf 'keep\n'   > "$IG/kept.md"
mkdir -p "$IG/blank"; printf 'invisible\n' > "$IG/blank/x.md"
seal "$IG"
run emptydir --root "$IG" --paths blank
chk "empty scope (a dir git lists nothing under): exit" 2 "$RC"
has "…named" "nothing in scope" "$TMP/emptydir.err"

run ignpath --root "$IG" --paths blank/x.md
chk "an ignored FILE, named explicitly: exit" 2 "$RC"
has "…and the reason is the listing, not existence" "git's listing does not carry it" \
    "$TMP/ignpath.err"

echo "── phase I: --changed — the new side, and the deletion named ───────────"
G="$TMP/moved"; mkrepo "$G"
printf 'to [x](kept.md)\n' > "$G/old.md"
printf 'kept\n'            > "$G/kept.md"
printf 'doomed\n'          > "$G/gone.md"
printf 'still here\n'      > "$G/quiet.md"
seal "$G" "before"
gitq "$G" mv old.md new.md >/dev/null 2>&1
gitq "$G" rm -q gone.md    >/dev/null 2>&1
runj chg --root "$G" --changed
chk "exit" 0 "$RC"
SC="$(J "$TMP/chg.json" 'sorted(f for l in d["lanes"] for f in l["files"]) + [x["file"] for x in d["seat_held"]]')"
chk "the NEW side of the rename is scoped" "True" \
    "$(J "$TMP/chg.json" '"new.md" in [f for l in d["lanes"] for f in l["files"]]')"
chk "the old side is not"  "False" \
    "$(J "$TMP/chg.json" '"old.md" in [f for l in d["lanes"] for f in l["files"]]')"
chk "the deleted file is not scoped" "False" \
    "$(J "$TMP/chg.json" '"gone.md" in [f for l in d["lanes"] for f in l["files"]]')"
chk "an untouched file is not scoped" "False" \
    "$(J "$TMP/chg.json" '"quiet.md" in [f for l in d["lanes"] for f in l["files"]]')"
chk "the deletion is NOTED, not silently dropped" "True" \
    "$(J "$TMP/chg.json" 'any("gone.md" in n and "dropped" in n for n in d["notes"])')"
LAWS "phase I" "$TMP/chg.json"

echo "── phase J: the real repo — scoped by two skill dirs ───────────────────"
SMOKE=$(python3 - "$GRAPH" "$ROOT" <<'PY'
import subprocess, sys, time
t = time.perf_counter()
r = subprocess.run([sys.executable, sys.argv[1], "domains", "--root", sys.argv[2],
                    "--paths", "plugins/notrest/skills/graph",
                    "plugins/notrest/skills/doctor"], capture_output=True)
print("%d %.3f" % (r.returncode, time.perf_counter() - t))
PY
)
SRC="${SMOKE%% *}"; SECS="${SMOKE##* }"
chk "real repo, two skill dirs: exit" 0 "$SRC"
if python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) < 2.0 else 1)" "$SECS"; then
  ok "real repo runs in ${SECS}s (< 2s)"
else
  bad "real repo took ${SECS}s — over the 2s budget"
fi
runj real --root "$ROOT" --paths plugins/notrest/skills/graph plugins/notrest/skills/doctor
chk "real repo: exit" 0 "$RC"
chk "real repo: a partition actually happened" "True" \
    "$(J "$TMP/real.json" 'len(d["lanes"]) >= 2')"
chk "real repo: graph.py and its SKILL.md move together" "True" \
    "$(J "$TMP/real.json" 'any("plugins/notrest/skills/graph/scripts/graph.py" in l["files"] and "plugins/notrest/skills/graph/SKILL.md" in l["files"] for l in d["lanes"])')"
LAWS "phase J" "$TMP/real.json"
NOGRAPHJSON=$( [ -e "$ROOT/graph/graph.json" ] && echo present || echo absent )
run realh --root "$ROOT" --paths plugins/notrest/skills/graph
chk "no prior scan is required (a stranger's fresh clone): exit" 0 "$RC"
hasnt "and it writes no graph.json of its own" "graph/graph.json" "$TMP/realh.out"

echo "── phase K: determinism ────────────────────────────────────────────────"
runj det1 --root "$D" --all --lanes 3
cp "$TMP/det1.json" "$TMP/det1.keep"
runj det2 --root "$D" --all --lanes 3
if cmp -s "$TMP/det1.keep" "$TMP/det2.json"; then
  ok "the same tree partitions byte-identically twice"
else
  bad "two runs over one tree disagreed — the partition is not deterministic"
fi

echo "----"
echo "fixture: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
