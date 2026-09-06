#!/bin/bash
# fixture.sh — asserts doctor.py against a synthetic harness. Self-relative: runs from any
# cwd, writes only inside its own mktemp dir, touches no real project.
#
# HERMETIC BY CONSTRUCTION. Three of doctor's checks read the machine, so the fixture hands
# them a machine of its own instead of asserting against whatever this laptop happens to
# have installed:
#   - $CLAUDE_CONFIG_DIR is redirected at a scratch config tree, so INSTALL FRESHNESS sees
#     exactly the skills-dir links and installs the fixture puts there — nothing else.
#   - $CLAUDE_APP_SUPPORT_DIR is redirected at a scratch app-support tree, so SHADOW-APPSIDE
#     reads the packs the fixture planted and never this laptop's real desktop-app store
#     (which on the machine this was written on holds a genuine 19-verb collision).
#   - a `claude` shim goes on PATH ahead of the real CLI, so TOKEN BUDGET reads a figure
#     the fixture chose ($FIXTURE_ALWAYS_ON) rather than the real plugin's cost.
# Usage: bash <doctor-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
# This corpus proves the historical Claude diagnostics. Host variables from a Codex caller
# must not silently select the other arm; Codex-specific checks have their own cases below.
unset CODEX_THREAD_ID CODEX_SANDBOX
DOC="$(cd "$(dirname "$0")" && pwd)/doctor.py"
PY="$(command -v python3)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }

# ── the scratch machine ───────────────────────────────────────────────────────────────
export CLAUDE_CONFIG_DIR="$W/config"          # empty: no links, no installs, no clone
mkdir -p "$CLAUDE_CONFIG_DIR"
export CLAUDE_APP_SUPPORT_DIR="$W/appsupport" # empty: no desktop-app provisioning store
mkdir -p "$CLAUDE_APP_SUPPORT_DIR"
mkdir -p "$W/bin"
cat > "$W/bin/claude" <<'SHIM'
#!/bin/bash
# fixture shim for `claude plugin details` — offline, deterministic, no real plugin read.
printf 'Component inventory\n  Skills (2)  alpha, beta\n\n'
printf 'Projected token cost\n'
printf '  Always-on:   ~%s tok   added to every session\n' "${FIXTURE_ALWAYS_ON:-1,200}"
printf '  Source: fixtureplug@inline\n'
exit 0
SHIM
chmod +x "$W/bin/claude"
cat > "$W/bin/codex" <<'SHIM'
#!/bin/bash
if [ "${1:-}" = plugin ] && [ "${2:-}" = list ]; then
  printf 'fixtureplug@fixture-codex-local installed, enabled  1.0.0  /fixture/cache\n'
  exit 0
fi
exit 2
SHIM
chmod +x "$W/bin/codex"
export PATH="$W/bin:$PATH"

RC=0
runjson(){ python3 "$DOC" check --root "$1" --json > "$W/out.json" 2>"$W/err.txt"; RC=$?; }
st(){ python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print(next((c['status'] for c in d['checks'] if c['check']==sys.argv[2]),'MISSING'))" "$W/out.json" "$1"; }
nfail(){ python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print(sum(1 for c in d['checks'] if c['status']=='FAIL'))" "$W/out.json"; }
nwarn(){ python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print(sum(1 for c in d['checks'] if c['status']=='WARN'))" "$W/out.json"; }
py(){ python3 -c "$1" "$2"; }

# ── the healthy synthetic harness ─────────────────────────────────────────────────────
H="$W/healthy"
mkdir -p "$H/.claude-plugin" "$H/.agents/plugins" \
         "$H/plugins/fixtureplug/.claude-plugin" "$H/plugins/fixtureplug/.codex-plugin" \
         "$H/plugins/fixtureplug/skills/alpha" "$H/plugins/fixtureplug/skills/beta" \
         "$H/plugins/fixtureplug/hooks" "$H/plugins/tomb/.claude-plugin" \
         "$H/docs" "$H/spend" "$H/compile"

cat > "$H/.gitignore" <<'EOF'
.DS_Store
# derived scan output at the REPO ROOT only — anchored, or these also ignore the skills'
# own directories (gitignore matches at any depth otherwise).
/graph/
/compile/
EOF

cat > "$H/plugins/fixtureplug/.claude-plugin/plugin.json" <<'EOF'
{
  "name": "fixtureplug",
  "version": "1.0.0",
  "description": "A synthetic harness — two natural-language-invocable skills ride on it.",
  "hooks": "./hooks/hooks.json"
}
EOF

cat > "$H/plugins/fixtureplug/.codex-plugin/plugin.json" <<'EOF'
{
  "name": "fixtureplug",
  "version": "1.0.0",
  "description": "A synthetic native Codex harness.",
  "author": { "name": "Fixture" },
  "skills": "./skills/",
  "interface": {
    "displayName": "Fixture",
    "shortDescription": "Synthetic harness",
    "longDescription": "Synthetic harness for Doctor's native package checks.",
    "developerName": "Fixture",
    "category": "Productivity",
    "capabilities": ["Read"]
  }
}
EOF

cat > "$H/.agents/plugins/marketplace.json" <<'EOF'
{
  "name": "fixture-codex-local",
  "interface": { "displayName": "Fixture" },
  "plugins": [
    {
      "name": "fixtureplug",
      "source": { "source": "local", "path": "./plugins/fixtureplug" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
EOF

cat > "$H/plugins/tomb/.claude-plugin/plugin.json" <<'EOF'
{
  "name": "oracle-suite",
  "version": "9.0.0",
  "description": "RENAMED — migration stub."
}
EOF

cat > "$H/.claude-plugin/marketplace.json" <<'EOF'
{
  "name": "fixtureplug",
  "metadata": { "description": "synthetic", "version": "1.0.0" },
  "plugins": [
    { "name": "fixtureplug", "source": "./plugins/fixtureplug", "version": "1.0.0",
      "description": "A synthetic harness — two natural-language-invocable skills ride on it: alpha and beta." },
    { "name": "oracle-suite", "source": "./plugins/tomb", "version": "9.0.0",
      "description": "RENAMED — migration stub." }
  ]
}
EOF

# alpha proves the CORRECT form survives: a quoted scalar may carry ': ' and escaped quotes.
cat > "$H/plugins/fixtureplug/skills/alpha/SKILL.md" <<'EOF'
---
name: alpha
description: "Alpha lane: the quoted form. Use on \"/alpha\", \"run alpha\" — colons and quotes are safe once quoted."
---

# alpha
EOF

cat > "$H/plugins/fixtureplug/skills/beta/SKILL.md" <<'EOF'
---
name: beta
description: Beta lane — a plain scalar with no colon-space is legal YAML and must not fire.
---

# beta
EOF

cat > "$H/plugins/fixtureplug/README.md" <<'EOF'
# fixtureplug
Two skills that compose: alpha and beta.
EOF

# M3: the ROSTER surfaces. The README is held to a TABLE ROW per skill (the table IS the
# roster); the other three need only name each skill in prose.
cat > "$H/README.md" <<'EOF'
# fixtureplug — a synthetic harness

Two skills ride on it.

| Skill | What it does |
|---|---|
| **alpha** | The first lane. |
| **beta** | The second lane. |
EOF

cat > "$H/plugins/fixtureplug/hooks/hooks.json" <<'EOF'
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "bash \"$CLAUDE_PLUGIN_ROOT/hooks/session-start.sh\"" } ] }
    ]
  }
}
EOF

cat > "$H/plugins/fixtureplug/hooks/session-start.sh" <<'EOF'
#!/bin/bash
echo "[fixtureplug] discipline anchored."
exit 0
EOF

cat > "$H/docs/TUTORIAL.md" <<'EOF'
# Tutorial
The harness — plus two skills — from install to the first working loop.

| You want to… | Say / invoke |
|---|---|
| Check the harness is healthy | "/doctor" → **doctor** |
| Run the first lane | "/alpha" → **alpha** |
| Run the second lane | "/beta" → **beta** |
EOF

cat > "$H/docs/oracle-skill-flow.html" <<'EOF'
<html><body><header>fixtureplug v1.0.0 — the two-skill harness</header><footer>v1.0.0</footer></body></html>
EOF

# HOOKS FIRED reads the clock, so the healthy estate is stamped NOW rather than with a
# frozen date — otherwise the fixture would start failing on its own two days after it
# was written, which is the worst possible property in a health checker's health checker.
NOW="$(date -u '+%Y-%m-%d %H:%M')Z"

cat > "$H/COORD.md" <<EOF
# COORD.md — session coordination ledger

Append-only, newest at the bottom.

## LEDGER
- [$NOW] [main] build the doctor -> skill landed | evidence: fixture exit 0
- [$NOW] [hook] session ended without /sessionend — auto-cushion: resume from this tail
EOF

cat > "$H/COORD-AGENTS.md" <<EOF
# COORD-AGENTS.md — agent activity ledger (auto-written by the fixtureplug SubagentStop hook)

## LEDGER
- [$NOW] agent=a1 model=claude-opus-5 bytes=10 | last: done | transcript: /tmp/a1.jsonl
EOF

cat > "$H/spend/ledger.md" <<EOF
# spend ledger — append-only via spend.py; grades: observed|estimate
[$NOW] lane=subagent model=claude-opus-5 tokens=1000 grade=observed purpose="doctor build lane"
EOF

echo '{"generated":"2026-07-24 10:03Z","candidates":[]}' > "$H/compile/candidates.json"

# ── A · the healthy harness is clean ──────────────────────────────────────────────────
echo "── A · healthy synthetic harness"
runjson "$H"; t "healthy harness exits 0" "$RC" "0"
t "--json parses" "$(py 'import json,sys;print("yes" if json.load(open(sys.argv[1]))["checks"] else "no")' "$W/out.json")" "yes"
t "fifteen checks reported" "$(py 'import json,sys;print(len(json.load(open(sys.argv[1]))["checks"]))' "$W/out.json")" "15"
t "verdict is HEALTHY" "$(py 'import json,sys;print(json.load(open(sys.argv[1]))["verdict"])' "$W/out.json")" "HEALTHY"
t "no check fails" "$(nfail)" "0"
t "no check warns" "$(nwarn)" "0"
t "quoted colon-space description does NOT false-fire" "$(st FRONTMATTER)" "PASS"
t "INSTALL FRESHNESS skips with no link and no clone" "$(st 'INSTALL FRESHNESS')" "SKIP"
grep -q 'rung 1 of 4' "$W/out.json" \
  && ok "the no-surface SKIP names runtime-ladder rung 1" \
  || no "the no-surface SKIP never names its rung"
t "SHADOW-APPSIDE skips with an empty app-support dir" "$(st 'SHADOW-APPSIDE')" "SKIP"
t "TOKEN BUDGET passes under the ceiling" "$(st 'TOKEN BUDGET')" "PASS"
t "HOOKS FIRED passes on a marked estate" "$(st 'HOOKS FIRED')" "PASS"
# the receipt is the point of a PASS here: assert the number reached the report
grep -q '1,200 tok' "$W/out.json" && ok "TOKEN BUDGET prints the number it read" \
  || no "TOKEN BUDGET printed no always-on figure"
# no CLI, no number, no guess — the honest SKIP (PATH without the shim or the real claude)
env PATH=/usr/bin:/bin "$PY" "$DOC" check --root "$H" --json > "$W/nocli.json" 2>/dev/null
t "TOKEN BUDGET skips when the CLI is absent" \
  "$(py 'import json,sys;print(next(c["status"] for c in json.load(open(sys.argv[1]))["checks"] if c["check"]=="TOKEN BUDGET"))' "$W/nocli.json")" "SKIP"
OUT="$(python3 "$DOC" check --root "$H" 2>&1)"; t "human mode exits 0" "$?" "0"
case "$OUT" in *"doctor: HEALTHY"*) ok "human mode prints one summary line";; *) no "summary line: $OUT";; esac

# ── B · one injected defect flips exactly its own check ───────────────────────────────
N=0
defect(){  # $1 label · $2 expected check · $3 python mutator (arg: repo dir)
  N=$((N+1)); D="$W/case$N"; rm -rf "$D"; cp -R "$H" "$D"
  python3 -c "$3" "$D" || { no "$1 — mutator failed"; return; }
  runjson "$D"
  t "$1 → exit 6" "$RC" "6"
  t "$1 → $2 FAILs" "$(st "$2")" "FAIL"
  t "$1 → nothing else fails" "$(nfail)" "1"
}

echo "── B · injected defect classes"
defect "unquoted colon-space description" "FRONTMATTER" '
import sys,io,os
p=os.path.join(sys.argv[1],"plugins/fixtureplug/skills/beta/SKILL.md")
io.open(p,"w",encoding="utf-8").write("---\nname: beta\ndescription: Beta lane: the unquoted form that silently kills the metadata.\n---\n\n# beta\n")'

# the marketplace side is bumped, not plugin.json — a plugin.json bump would ALSO (correctly)
# stale the render stamp, and this case asserts single-check precision.
defect "manifest version mismatch" "MANIFESTS" '
import sys,os,json
p=os.path.join(sys.argv[1],".claude-plugin/marketplace.json")
d=json.load(open(p)); d["metadata"]["version"]="1.0.1"; json.dump(d,open(p,"w"),indent=2)'

defect "tombstone bumped off its pin" "MANIFESTS" '
import sys,os,json
p=os.path.join(sys.argv[1],".claude-plugin/marketplace.json")
d=json.load(open(p))
for e in d["plugins"]:
    if e["name"]=="oracle-suite": e["version"]="9.0.1"
json.dump(d,open(p,"w"),indent=2)'

defect "broken hook syntax" "HOOKS" '
import sys,io,os
p=os.path.join(sys.argv[1],"plugins/fixtureplug/hooks/session-start.sh")
io.open(p,"w",encoding="utf-8").write("#!/bin/bash\nif [ -z \"$X\" ]; then\n  echo \"[fixtureplug] hi\"\n")'

defect "skill count drift" "SKILL COUNT" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/TUTORIAL.md")
t=io.open(p,encoding="utf-8").read().replace("two skills","three skills")
io.open(p,"w",encoding="utf-8").write(t)'

defect "unanchored gitignore rule" "GITIGNORE" '
import sys,io,os
p=os.path.join(sys.argv[1],".gitignore")
t=io.open(p,encoding="utf-8").read().replace("/graph/","graph/")
io.open(p,"w",encoding="utf-8").write(t)'

defect "stale render stamp" "RENDER SURFACES" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace("<footer>v1.0.0","<footer>v0.9.0")
io.open(p,"w",encoding="utf-8").write(t)'

defect "damaged COORD header" "ESTATE" '
import sys,io,os
p=os.path.join(sys.argv[1],"COORD.md")
io.open(p,"w",encoding="utf-8").write("notes\n- [2026-07-24 10:00Z] [main] x -> y | evidence: z\n")'

defect "broken candidates.json" "ESTATE" '
import sys,io,os
p=os.path.join(sys.argv[1],"compile/candidates.json")
io.open(p,"w",encoding="utf-8").write("{not json")'

# ── M3 · the roster is the promise; the dirs are the delivery ────────────────────────
# 4.6.1 shipped beam, mentor and tieredswarm with no README row and no mention anywhere a
# reader browses, and every gate passed: SKILL COUNT compares a NUMBER to a number, so a
# README that SAYS thirty-two while LISTING twenty-nine is arithmetically perfect.
defect "a skill with no README table row" "ROSTER PARITY" '
import sys,io,os,re
p=os.path.join(sys.argv[1],"README.md")
t=io.open(p,encoding="utf-8").read()
io.open(p,"w",encoding="utf-8").write(t.replace("| **beta** | The second lane. |\n",""))'

defect "a skill named nowhere in the tutorial" "ROSTER PARITY" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/TUTORIAL.md")
t=io.open(p,encoding="utf-8").read()
io.open(p,"w",encoding="utf-8").write(t.replace("| Run the second lane | \"/beta\" → **beta** |\n",""))'

defect "a skill absent from the marketplace description" "ROSTER PARITY" '
import sys,os,json
p=os.path.join(sys.argv[1],".claude-plugin/marketplace.json")
d=json.load(open(p))
for e in d["plugins"]:
    if e["name"]=="fixtureplug":
        e["description"]=e["description"].replace(": alpha and beta",": alpha")
json.dump(d,open(p,"w"),indent=2)'

# a mention is not a row — the exact shape 4.6.1's README had for the three missing skills
defect "a prose mention where the roster wants a row" "ROSTER PARITY" '
import sys,io,os
p=os.path.join(sys.argv[1],"README.md")
t=io.open(p,encoding="utf-8").read()
io.open(p,"w",encoding="utf-8").write(
    t.replace("| **beta** | The second lane. |\n","") + "\nbeta is also shipped.\n")'

# a mutation that must change NOTHING — the refuter's nits are false-FAIL bugs, and the
# only way to hold a false positive down is to assert the clean case out loud.
nodefect(){  # $1 label · $2 python mutator (arg: repo dir)
  N=$((N+1)); D="$W/case$N"; rm -rf "$D"; cp -R "$H" "$D"
  python3 -c "$2" "$D" || { no "$1 — mutator failed"; return; }
  runjson "$D"
  t "$1 → still exit 0" "$RC" "0"
  t "$1 → nothing fails" "$(nfail)" "0"
}

warndefect(){  # $1 label · $2 expected check · $3 python mutator (arg: repo dir)
  N=$((N+1)); D="$W/case$N"; rm -rf "$D"; cp -R "$H" "$D"
  python3 -c "$3" "$D" || { no "$1 — mutator failed"; return; }
  runjson "$D"
  t "$1 → exit 5" "$RC" "5"
  t "$1 → $2 WARNs" "$(st "$2")" "WARN"
  t "$1 → nothing fails" "$(nfail)" "0"
}

# ── F5 · a hyphen-joined suffix is still the name (refuter nit, 4.6.2) ────────────────
# `(?![A-Za-z0-9_-])` rejected a trailing hyphen, so the estate's own prose — "the
# mentor-dev ritual", "the oracle-suite core" — did not count as naming the skill, and the
# roster gate would have raised a FAIL against a README that names it perfectly well.
nodefect "a skill named with a hyphenated suffix still counts as named" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/TUTORIAL.md")
t=io.open(p,encoding="utf-8").read()
io.open(p,"w",encoding="utf-8").write(
    t.replace("| Run the second lane | \"/beta\" → **beta** |",
              "| Run the second lane | the beta-mode workflow |"))'
nodefect "…and so does a hyphenated suffix in the marketplace description" '
import sys,os,json
p=os.path.join(sys.argv[1],".claude-plugin/marketplace.json")
d=json.load(open(p))
for e in d["plugins"]:
    if e["name"]=="fixtureplug":
        e["description"]=e["description"].replace(": alpha and beta",": alpha-lane and beta-lane")
json.dump(d,open(p,"w"),indent=2)'
# …while a LETTER-joined suffix is a different word and must still be caught
defect "a plural is NOT a mention (the boundary still holds one way)" "ROSTER PARITY" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/TUTORIAL.md")
t=io.open(p,encoding="utf-8").read()
io.open(p,"w",encoding="utf-8").write(
    t.replace("| Run the second lane | \"/beta\" → **beta** |",
              "| Run the second lane | the betas workflow |"))'

# ── F3 · the render states a COUNT, and a count in prose drifts like a version stamp ──
defect "stale skill count in the render" "RENDER SURFACES" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace("two-skill","three-skill")
io.open(p,"w",encoding="utf-8").write(t)'

defect "…and the spelled form is read too" "RENDER SURFACES" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace("two-skill","31-skill")
io.open(p,"w",encoding="utf-8").write(t)'

# F7 (refuter nit, 4.6.2): unanchored, NSKILL_RE read ordinary prose as a count claim —
# "a one-skill install" → 1 → COUNT DRIFT against a 2-skill tree. A count claim now counts
# only where the page ALREADY makes a version claim: the text node the stamp lives in.
nodefect "prose elsewhere on the page is NOT a count claim" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace(
    "</body>", "<p>Start with a one-skill install, then add the two-skill bundle.</p></body>")
io.open(p,"w",encoding="utf-8").write(t)'
nodefect "…even when the prose count is wildly wrong" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace(
    "</body>", "<p>the ninety-nine-skill era is over</p></body>")
io.open(p,"w",encoding="utf-8").write(t)'
# …and the real thing is still caught, in the element the release bump edits
defect "drift INSIDE the stamped element is still caught" "RENDER SURFACES" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace(
    "v1.0.0 — the two-skill harness", "v1.0.0 — the seven-skill harness")
io.open(p,"w",encoding="utf-8").write(t)'
# R2 (review round, 4.6.2): anchoring to the stamp's own text node bought a SILENT PASS.
# A template edit that wraps the count in its own element splits it from the stamp, the
# anchor finds nothing, and the gate whose whole job is catching a stale count reports
# success. The anchor stays; its blind spot is now audible.
warndefect "a template edit that SPLITS the count from the stamp is not silent" "RENDER SURFACES" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace(
    "v1.0.0 — the two-skill harness", "v1.0.0 — the <b>two-skill</b> harness")
io.open(p,"w",encoding="utf-8").write(t)'
warndefect "…and so is a page that states no count at all" "RENDER SURFACES" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace(" — the two-skill harness","")
io.open(p,"w",encoding="utf-8").write(t)'
# …while the LIVE shape — stamp and count in one element — still passes clean
nodefect "the live render shape (count beside the stamp) passes with no warning" '
import sys,io,os
p=os.path.join(sys.argv[1],"docs/oracle-skill-flow.html")
t=io.open(p,encoding="utf-8").read().replace(
    "<header>fixtureplug v1.0.0 — the two-skill harness</header>",
    "<header><span class=\"sub\">v1.0.0 &middot; two-skill harness &middot; intake</span></header>")
io.open(p,"w",encoding="utf-8").write(t)'

# TOKEN BUDGET's defect does not live in the tree — it lives in what the tree COSTS, which
# only the CLI can say. The shim carries the injection, so the assertion stays offline.
export FIXTURE_ALWAYS_ON="9,999"
runjson "$H"
t "over-budget always-on cost → exit 6" "$RC" "6"
t "over-budget always-on cost → TOKEN BUDGET FAILs" "$(st 'TOKEN BUDGET')" "FAIL"
t "over-budget always-on cost → nothing else fails" "$(nfail)" "1"
unset FIXTURE_ALWAYS_ON

# ── B1b · derived output must not ride in the package (F6) ───────────────────────────
# 4.6.1 shipped plugins/notrest/graph/{graph,river}.{html,json} — 125 KB of scan output the
# root-anchored /graph/ rule never covered, referenced by nothing, in every consumer's
# install for five weeks. The probe needs a real work tree, so this case builds one.
echo "── B1b · derived scan output tracked inside a plugin (F6)"
G="$W/gitcase"; rm -rf "$G"; cp -R "$H" "$G"
(
  cd "$G" || exit 1
  git init -q 2>/dev/null
  git config user.name Fixture; git config user.email fixture@example.com
  git config commit.gpgsign false
  git add -A >/dev/null 2>&1
  git -c commit.gpgsign=false commit -qm "the clean package" >/dev/null 2>&1
) || { no "F6 git setup failed"; }
runjson "$G"
t "a clean work tree keeps GITIGNORE passing" "$(st GITIGNORE)" "PASS"
grep -q 'no tracked derived graph/compile output' "$W/out.json" \
  && ok "…and says so out loud, rather than staying silent" \
  || no "the clean case never reported the tracked-output probe"
mkdir -p "$G/plugins/fixtureplug/graph"
echo '{"derived":true}' > "$G/plugins/fixtureplug/graph/graph.json"
echo '<html>derived</html>' > "$G/plugins/fixtureplug/graph/graph.html"
(cd "$G" && git add -f plugins/fixtureplug/graph >/dev/null 2>&1 && \
   git -c commit.gpgsign=false commit -qm "oops: shipped the scan output" >/dev/null 2>&1)
runjson "$G"
t "tracked derived output → exit 6" "$RC" "6"
t "tracked derived output → GITIGNORE FAILs" "$(st GITIGNORE)" "FAIL"
t "tracked derived output → nothing else fails" "$(nfail)" "1"
grep -q 'DERIVED OUTPUT SHIPPED' "$W/out.json" && ok "…named as a packaging defect" \
  || no "the finding never named itself"
grep -q 'plugins/fixtureplug/graph/graph.json' "$W/out.json" \
  && ok "…listing the tracked files by path" || no "no path was named"
# UNTRACKED derived output is not a packaging defect — it never reaches a consumer
(cd "$G" && git rm -r -q --cached plugins/fixtureplug/graph >/dev/null 2>&1 && \
   printf 'plugins/*/graph/\n' >> .gitignore && git add -A >/dev/null 2>&1 && \
   git -c commit.gpgsign=false commit -qm "untrack it" >/dev/null 2>&1)
runjson "$G"
t "untracking it clears the finding, files still on disk" "$(st GITIGNORE)" "PASS"
t "…and the anchored plugins/*/ rule does not ignore the skill dirs" "$(nfail)" "0"

# ── 4.7 H · LOOP HEALTH · the dashboard beside eval's gate ───────────────────────────
# ⛔ WARN-GRADE, NEVER FAIL. A loop that is behind is a fact about how the estate is being
# WORKED, not a broken install — and doctor's exit code gates SHIPPING. eval's
# LEARNING-LOOP is the check with teeth; this one is the number beside it.
echo "── 4.7 · LOOP HEALTH (WARN-grade, never a ship blocker)"
LH="$W/loophealth"; rm -rf "$LH"; cp -R "$H" "$LH"
runjson "$LH"
t "no findings store at all → LOOP HEALTH SKIPs" "$(st 'LOOP HEALTH')" "SKIP"
t "…and the harness is still healthy" "$RC" "0"
mkdir -p "$LH/archive"
cat > "$LH/archive/findings.jsonl" <<'FJ'
{"id":"L-1","ts":"2026-09-01T00:00:00Z","kind":"learning","tag":"RULED","statement":"a banked lesson","evidence":[{"type":"coord-line","ref":"[2026-09-01 00:00Z]","label":"cited"}],"scope":["estate"],"source":"seat","status":"live"}
FJ
runjson "$LH"
t "a store with a learning and no debt → PASS" "$(st 'LOOP HEALTH')" "PASS"
t "…and the exit code is untouched" "$RC" "0"
grep -q 'learnings: 1 banked' "$W/out.json" && ok "…reporting how many are banked" \
  || no "the learnings count is missing"
grep -q 'open questions: none' "$W/out.json" && ok "…and that nothing is open" \
  || no "the open line is missing"
# an OVERDUE open question is a WARN, never a FAIL
cat >> "$LH/archive/findings.jsonl" <<'FJ'
{"id":"O-1","ts":"2026-09-01T00:00:00Z","kind":"open","statement":"the consumer flow was never run","closes_when":"the documented flow exits 0","owner":"seat","recheck":"2020-01-01","evidence":[{"type":"coord-line","ref":"[2026-09-01 00:00Z]","label":"cited"}],"scope":["estate"],"source":"seat","status":"live"}
FJ
runjson "$LH"
t "an open question past its recheck date → WARN" "$(st 'LOOP HEALTH')" "WARN"
t "…exit 5, never 6 — this must not block a ship" "$RC" "5"
t "…and nothing FAILs" "$(nfail)" "0"
grep -q '1 past their recheck date' "$W/out.json" && ok "…counting the overdue ones" \
  || no "the overdue count is missing"
grep -q 'open questions: 1' "$W/out.json" && ok "…and the open total with its oldest age" \
  || no "the open total is missing"
# a superseded open question stops asking
python3 - "$LH/archive/findings.jsonl" <<'PY5'
import sys
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write('{"id":"O-2","ts":"2026-09-02T00:00:00Z","kind":"open","statement":"closed one",'
            '"closes_when":"x","owner":"seat","recheck":"2020-01-01","evidence":[{"type":'
            '"command","ref":"abc1234","label":"cited"}],"scope":["estate"],"source":"seat",'
            '"status":"superseded"}\n')
PY5
runjson "$LH"
grep -q 'open questions: 1' "$W/out.json" \
  && ok "a superseded open question stops asking" || no "a superseded open is still counted"
# a corrupt store line must not take the check down
printf 'not json at all\n' >> "$LH/archive/findings.jsonl"
runjson "$LH"
t "a corrupt store line does not break LOOP HEALTH" "$(nfail)" "0"
grep -q 'learnings: 1 banked' "$W/out.json" && ok "…and the readable records still report" \
  || no "one bad line took the whole check down"
# drafted-but-undecided compile candidates are the fourth number
python3 - "$LH/compile/candidates.json" <<'PY6'
import json, sys
json.dump({"generated": "2026-09-05 00:00Z",
           "candidates": [{"slug": "release-ritual", "status": "DRAFTED"},
                          {"slug": "other", "status": "ADOPTED"}]},
          open(sys.argv[1], "w"))
PY6
runjson "$LH"
grep -q '1 drafted/proposed but undecided' "$W/out.json" \
  && ok "a drafted candidate nobody ruled on is counted" || no "the candidate count is wrong"
t "…still WARN, still not a FAIL" "$(nfail)" "0"

# ── B2 · doctor surfaces the proposals awaiting the seat's review ────────────────────
cat >> "$LH/archive/findings.jsonl" <<'FJ'
{"id":"L-9","ts":"2026-09-03T00:00:00Z","kind":"learning","tag":"LEARNED","statement":"a lane's unreviewed claim","evidence":[{"type":"coord-line","ref":"[2026-09-01 00:00Z]","label":"cited"}],"scope":["estate"],"source":"lane:a1","status":"proposed"}
FJ
runjson "$LH"
t "an unreviewed lane proposal → WARN, never a FAIL" "$(st 'LOOP HEALTH')" "WARN"
t "…exit 5, so it cannot block a ship" "$RC" "5"
grep -qE 'proposed: 1 awaiting review' "$W/out.json" && ok "…and doctor counts it awaiting review" \
  || no "the proposed count is missing"
python3 - "$LH/archive/findings.jsonl" <<'PY8'
import sys
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write('{"id":"F-70","ts":"2026-09-04T00:00:00Z","kind":"decision","statement":'
            '"accepts L-9 — reviewed by the seat.","evidence":[{"type":"record","ref":'
            '"L-9","label":"cited"}],"relation":"back","links":["L-9"],"status":"live"}\n')
PY8
runjson "$LH"
# bites BOTH ways: the count must clear AND the check must still say it looked.
# 'proposed: none awaiting review' also contains the phrase, so the count is what is
# matched — an arm that cannot tell "none" from "one" is not an arm.
if grep -qE 'proposed: [0-9]+ awaiting review' "$W/out.json"; then
  no "an accepted proposal is still counted"
elif grep -q 'proposed: none awaiting review' "$W/out.json"; then
  ok "…and once the seat accepts it, the count clears"
else
  no "LOOP HEALTH stopped reporting the proposed line entirely"
fi

# ── 4.8 · ACCESS KEY · doctor REPORTS the gate, it never verifies it ─────────────────
# ⛔ THE VERDICT COMES FROM atlas.py. A second key check here would be a second policy, and
# the copy that drifts is the one nobody watches. What doctor adds is WHY the gate is
# quiet: an inert gate (no verifier shipped) looks exactly like a passing one, and telling
# those apart is the whole job of this line.
echo "── 4.8 · ACCESS KEY + ATLAS"
AKD="$W/accesskey"; rm -rf "$AKD"; cp -R "$H" "$AKD"
ASTUB="$W/atlasstub"; mkdir -p "$ASTUB"
cat > "$ASTUB/atlas.py" <<'ASTUBPY'
#!/usr/bin/env python3
import os, sys
mode = os.environ.get("STUB_MODE", "valid")
if len(sys.argv) > 2 and sys.argv[1] == "key" and "--check" in sys.argv:
    if mode == "valid":   print("valid"); sys.exit(0)
    if mode == "empty":   print("keyring empty"); sys.exit(4)
    print("no valid key"); sys.exit(1)
if len(sys.argv) > 1 and sys.argv[1] == "status":
    print("bank hook: wired · last snapshot: 0.2h · hub: none configured"); sys.exit(0)
sys.exit(2)
ASTUBPY
akrun() { env NOTREST_ATLAS_PY="$ASTUB/atlas.py" STUB_MODE="$1" \
          python3 "$DOC" check --root "$AKD" --json > "$W/out.json" 2>"$W/err.txt"; RC=$?; }

# (1) no keyring and no verifier: the gate is NOT DEPLOYED, and doctor says exactly that
env NOTREST_ATLAS_PY="$W/nope.py" PATH=/usr/bin:/bin python3 "$DOC" check --root "$AKD" \
  --json > "$W/out.json" 2>&1; RC=$?
t "no keyring, no verifier → ACCESS KEY passes (nothing to enforce)" "$(st 'ACCESS KEY')" "PASS"
grep -q 'the access gate is not deployed in this tree' "$W/out.json" \
  && ok "…saying the gate is not deployed" || no "the not-deployed state is not named"
grep -q 'access key: NOT CHECKED' "$W/out.json" \
  && ok "…and that no verifier means NOT CHECKED, not 'fine'" || no "an inert gate reads as passing"

# (2) a keyring with keys + a valid key
mkdir -p "$AKD/plugins/fixtureplug/.access"
python3 -c "
open('$AKD/plugins/fixtureplug/.access/keys.sha256','w').write(
  '# notrest access keyring — sha256(key):label:date\n' + '0'*64 + ':fixture:2026-09-06\n')"
akrun valid
t "a populated keyring + valid key → PASS" "$(st 'ACCESS KEY')" "PASS"
grep -q 'access key: present and valid' "$W/out.json" && ok "…reported present and valid" \
  || no "a valid key was not reported"
grep -q '1 key(s)' "$W/out.json" && ok "…and the keyring's key count is stated" \
  || no "the key count is missing"
# the line now leads with lane A's exit-code meaning, then whatever status said
grep -q 'atlas: green' "$W/out.json" && grep -q 'bank hook: wired' "$W/out.json" \
  && ok "…and the ATLAS line reads atlas.py status --json (exit 0 = green)" \
  || no "the ATLAS line is missing"

# (3) an EMPTY keyring is a WARN — no machine but this one can run the harness
python3 -c "
open('$AKD/plugins/fixtureplug/.access/keys.sha256','w').write(
  '# notrest access keyring — sha256(key):label:date\n')"
akrun empty
t "an EMPTY keyring warns" "$(st 'ACCESS KEY')" "WARN"
t "…exit 5, never blocking a ship" "$RC" "5"
t "…and nothing FAILs" "$(nfail)" "0"
grep -q 'KEYRING EMPTY' "$W/out.json" && ok "…naming the empty keyring" || no "not named"
grep -q 'atlas.py key --mint' "$W/out.json" && ok "…with the mint command as the fix" \
  || no "the fix does not say how to mint"

# (4) a keyring with keys but NO valid key on this machine: WARN, and it names exit 7
python3 -c "
open('$AKD/plugins/fixtureplug/.access/keys.sha256','w').write(
  '# ring\n' + '0'*64 + ':fixture:2026-09-06\n')"
akrun invalid
t "keys exist but this machine has none → WARN" "$(st 'ACCESS KEY')" "WARN"
t "…still exit 5, never 6" "$RC" "5"
grep -q 'NO VALID KEY' "$W/out.json" && ok "…named plainly" || no "an invalid key is not named"
grep -q 'exit 7' "$W/out.json" \
  && ok "…and doctor says what that means for establish (exit 7)" || no "the consequence is unstated"

# ── 4.9 · ATLAS MCP · a soft dependency, named in one line, never a failure ─────────
# ⛔ RULINGS 2026-09-06 §4: "doctor names a missing node in one line, never fails the harness
# on it." Every arm below therefore asserts TWO things — that the state is REPORTED, and that
# nothing FAILs. Hermetic: node comes from a shim on PATH, or from a $NODE name that cannot
# exist on any machine, never from whatever this laptop happens to have installed.
echo "── 4.9 · ATLAS MCP (node >= 22, soft)"
runjson "$H"
t "a harness shipping no atlas MCP server → an honest SKIP" "$(st 'ATLAS MCP')" "SKIP"
t "…and the skip costs nothing" "$RC" "0"

AMD="$W/atlasmcp"; rm -rf "$AMD"; cp -R "$H" "$AMD"
mkdir -p "$AMD/plugins/fixtureplug/skills/atlas/mcp"     # no SKILL.md: not a skill, just the server
printf '// fixture stand-in for the vendored server\n' \
  > "$AMD/plugins/fixtureplug/skills/atlas/mcp/server.mjs"
cat > "$AMD/plugins/fixtureplug/.mcp.json" <<'MJ'
{ "mcpServers": { "atlas": { "command": "${CLAUDE_PLUGIN_ROOT}/skills/atlas/mcp/atlas-mcp.sh" } } }
MJ
nodeshim(){ mkdir -p "$1"; printf '#!/bin/bash\necho "%s"\n' "$2" > "$1/node"; chmod +x "$1/node"; }
nodeshim "$W/node22" "v22.11.0"
nodeshim "$W/node20" "v20.19.5"

# (1) the server is here and node is new enough: PASS, and the exit code does not move
env PATH="$W/node22:$PATH" python3 "$DOC" check --root "$AMD" --json > "$W/out.json" 2>"$W/err.txt"
RC=$?
t "server present + node v22 → ATLAS MCP passes" "$(st 'ATLAS MCP')" "PASS"
t "…and doctor still exits 0" "$RC" "0"
t "…with nothing warning" "$(nwarn)" "0"
grep -q 'the read server can start' "$W/out.json" \
  && ok "…saying in words that the server can start" || no "the PASS states no consequence"
grep -q 'declared in .*mcp.json: atlas' "$W/out.json" \
  && ok "…and naming the declaration the host starts it from" || no "the MCP declaration is unread"

# (2) an OLD node: a WARN that never becomes a failure
env PATH="$W/node20:$PATH" python3 "$DOC" check --root "$AMD" --json > "$W/out.json" 2>"$W/err.txt"
RC=$?
t "node v20 → ATLAS MCP warns" "$(st 'ATLAS MCP')" "WARN"
t "…exit 5, never 6 — an old node never fails the harness" "$RC" "5"
t "…and nothing FAILs" "$(nfail)" "0"
grep -q 'v20.19.5' "$W/out.json" && ok "…the version it actually found is named" \
  || no "the WARN does not say which node it found"
grep -q 'nothing else in the harness is affected' "$W/out.json" \
  && ok "…and the blast radius is stated, not left to fear" || no "the blast radius is unstated"

# (3) NO node at all — asserted through $NODE so the arm cannot depend on this laptop
env NODE="notrest-fixture-no-such-node" python3 "$DOC" check --root "$AMD" --json \
  > "$W/out.json" 2>"$W/err.txt"; RC=$?
t "no node → ATLAS MCP warns" "$(st 'ATLAS MCP')" "WARN"
t "…still exit 5" "$RC" "5"
t "…still nothing FAILs" "$(nfail)" "0"
grep -q 'NOT ON PATH' "$W/out.json" && ok "…naming the absence plainly" || no "an absent node is not named"
grep -q 'atlas_\* read tools are absent' "$W/out.json" \
  && ok "…and saying exactly what is lost (the eleven read tools)" || no "the loss is unnamed"
grep -q 'install node >= 22' "$W/out.json" && ok "…with the one-line fix" || no "no fix is offered"

# ── B2 · the WARN classes: real findings that are not breakage ────────────────────────
# doctor must be able to say "this is worth knowing" without saying "this is broken".
echo "── B2 · warn-class findings (exit 5, nothing failing)"
runcfg(){  # $1 config dir · $2 repo root — run against a scratch machine, then restore
  SAVED="$CLAUDE_CONFIG_DIR"; export CLAUDE_CONFIG_DIR="$1"
  runjson "$2"
  export CLAUDE_CONFIG_DIR="$SAVED"
}
warncase(){  # $1 label · $2 the check expected to WARN
  t "$1 → exit 5" "$RC" "5"
  t "$1 → $2 WARNs" "$(st "$2")" "WARN"
  t "$1 → nothing fails" "$(nfail)" "0"
  t "$1 → nothing else warns" "$(nwarn)" "1"
}

# (i) skills-dir mode, healthy: the link resolves INTO the tree under test. No clone is
#     read, no cache is read, and doctor must say so in skills-dir vocabulary.
IP="$W/inplace"; cp -R "$H" "$IP"
CFG="$W/cfg-inplace"; mkdir -p "$CFG/skills"
ln -s "$IP/plugins/fixtureplug" "$CFG/skills/fixtureplug"
runcfg "$CFG" "$IP"
t "in-place skills-dir link → exit 0" "$RC" "0"
t "in-place skills-dir link → INSTALL FRESHNESS PASSes" "$(st 'INSTALL FRESHNESS')" "PASS"
grep -q 'skills-dir(in-place)' "$W/out.json" \
  && ok "in-place mode is named in skills-dir vocabulary, not marketplace vocabulary" \
  || no "in-place run did not report runtime=skills-dir(in-place)"
grep -q 'runtime=marketplace-cache' "$W/out.json" \
  && no "in-place run labelled itself marketplace-cache — the mislabel this check exists to kill" \
  || ok "in-place run never labels itself a cache install"

# (ii) the link exists under the plugin's name but points somewhere else — the session is
#      running a DIFFERENT copy, so nothing checked here is what runs.
FOR="$W/foreign"; mkdir -p "$FOR/.claude-plugin"
echo '{"name":"fixtureplug","version":"0.0.1"}' > "$FOR/.claude-plugin/plugin.json"
CFG2="$W/cfg-foreign"; mkdir -p "$CFG2/skills"
ln -s "$FOR" "$CFG2/skills/fixtureplug"
runcfg "$CFG2" "$IP"
warncase "skills-dir link into a foreign tree" "INSTALL FRESHNESS"
grep -q 'rung 3 of 4' "$W/out.json" \
  && ok "the foreign-tree fix names rung 3 (the surface resolves to THIS tree)" \
  || no "the foreign-tree fix never names its rung"

# (iii) in-place + an installed plugin holding the same name: the link is ignored, so the
#       tree on disk is not the build the session loaded.
CFG3="$W/cfg-shadow"; mkdir -p "$CFG3/skills" "$CFG3/plugins"
ln -s "$IP/plugins/fixtureplug" "$CFG3/skills/fixtureplug"
cat > "$CFG3/plugins/installed_plugins.json" <<'EOF'
{"plugins":{"fixtureplug@fixtureplug":[{"scope":"user","version":"0.9.0"}]}}
EOF
runcfg "$CFG3" "$IP"
warncase "skills-dir copy shadowed by an installed plugin" "INSTALL FRESHNESS"
grep -q 'SHADOWED' "$W/out.json" && ok "the shadow is named, not merely implied" \
  || no "shadowed run never says SHADOWED"
grep -q 'rung 2 of 4' "$W/out.json" \
  && ok "the exact-name shadow fix names rung 2 (the name is free)" \
  || no "the exact-name shadow fix never names its rung"
grep -q 'shadow ladder rung 1 of 3' "$W/out.json" \
  && ok "the exact-name shadow is placed on the shadow ladder too" \
  || no "the exact-name shadow never names its shadow-ladder rung"

# (iii-b) T13, the half a name-keyed check cannot see: an installed plugin under a DIFFERENT
#         name that ships our verbs. The names never collide; the verbs do, which is what a
#         session actually resolves.
OTH="$W/otherplug"; mkdir -p "$OTH/skills/alpha"
cat > "$OTH/skills/alpha/SKILL.md" <<'EOF'
---
name: alpha
description: "A foreign pack's alpha — same verb, different plugin name."
---
EOF
CFG3B="$W/cfg-overlap"; mkdir -p "$CFG3B/skills" "$CFG3B/plugins"
ln -s "$IP/plugins/fixtureplug" "$CFG3B/skills/fixtureplug"
cat > "$CFG3B/plugins/installed_plugins.json" <<EOF
{"plugins":{"otherplug@elsewhere":[{"scope":"user","version":"7.0.0","installPath":"$OTH"}]}}
EOF
runcfg "$CFG3B" "$IP"
warncase "differently-named install carrying our verbs" "INSTALL FRESHNESS"
grep -q 'SHADOW CANDIDATE (by verbs, not by name)' "$W/out.json" \
  && ok "the verb-keyed shadow is named as such" \
  || no "the verb-keyed shadow is not named"
grep -q "carries 1 of this tree's 2 verbs" "$W/out.json" \
  && ok "the overlap WARN carries the count" || no "the overlap WARN states no count"
grep -q 'shadow ladder rung 2 of 3' "$W/out.json" \
  && ok "the verb-keyed shadow fix names shadow-ladder rung 2" \
  || no "the verb-keyed shadow fix never names its rung"

# (iv) the uncommitted release: in skills-dir mode the session runs the WORKING TREE, so a
#      release that is bumped-but-uncommitted is live on this machine and nowhere else.
UC="$W/uncommitted"; cp -R "$H" "$UC"
( cd "$UC" && git init -q . && git add -A . && \
  git -c user.email=fixture@local -c user.name=fixture commit -qm "v1.0.0" ) >/dev/null 2>&1
python3 - "$UC" <<'PY'
import io, json, os, sys
d = sys.argv[1]
p = os.path.join(d, "plugins/fixtureplug/.claude-plugin/plugin.json")
o = json.load(open(p)); o["version"] = "1.0.1"; json.dump(o, open(p, "w"), indent=2)
p = os.path.join(d, "plugins/fixtureplug/.codex-plugin/plugin.json")
o = json.load(open(p)); o["version"] = "1.0.1"; json.dump(o, open(p, "w"), indent=2)
p = os.path.join(d, ".claude-plugin/marketplace.json")
o = json.load(open(p)); o["metadata"]["version"] = "1.0.1"
for e in o["plugins"]:
    if e["name"] == "fixtureplug":
        e["version"] = "1.0.1"
json.dump(o, open(p, "w"), indent=2)
# every other stamp moves with it, so tree-vs-HEAD is the ONLY disagreement left
h = os.path.join(d, "docs/oracle-skill-flow.html")
html = io.open(h, encoding="utf-8").read().replace("v1.0.0", "v1.0.1")
io.open(h, "w", encoding="utf-8").write(html)
PY
CFG4="$W/cfg-uncommitted"; mkdir -p "$CFG4/skills"
ln -s "$UC/plugins/fixtureplug" "$CFG4/skills/fixtureplug"
runcfg "$CFG4" "$UC"
warncase "uncommitted release under an in-place link" "INSTALL FRESHNESS"
grep -q 'UNCOMMITTED RELEASE' "$W/out.json" && ok "the uncommitted release is named as such" \
  || no "uncommitted-release run never says UNCOMMITTED RELEASE"
grep -q 'rung 4 of 4' "$W/out.json" \
  && ok "the uncommitted-release fix names rung 4 (what runs here is what others see)" \
  || no "the uncommitted-release fix never names its rung"

# (v) a quiet estate: no [hook] tag in the COORD tail and no fresh agent/spend pair. That
#     is absence of evidence, so it WARNs — a health checker that FAILs a fresh repo is
#     a health checker nobody runs twice.
QU="$W/quiet"; cp -R "$H" "$QU"
python3 - "$QU" <<'PY'
import io, os, re, sys
d = sys.argv[1]
p = os.path.join(d, "COORD.md")
t = "".join(l for l in io.open(p, encoding="utf-8") if "[hook]" not in l)
io.open(p, "w", encoding="utf-8").write(t)
for f in ("COORD-AGENTS.md", "spend/ledger.md"):
    p = os.path.join(d, f)
    t = re.sub(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z\]", "[2020-01-01 00:00Z]",
               io.open(p, encoding="utf-8").read())
    io.open(p, "w", encoding="utf-8").write(t)
PY
runjson "$QU"
warncase "estate with no sign a hook ever fired" "HOOKS FIRED"

# ── B3 · the app-side provisioning store (SHADOW-APPSIDE) ─────────────────────────────
# The store belongs to the DESKTOP APP, not the CLI: no $CLAUDE_CONFIG_DIR path reaches it
# and no `claude plugin` verb repairs it. Both on-disk shapes below were read off a live
# machine before they were coded — the fixture asserts the shapes doctor actually meets.
echo "── B3 · the desktop app's provisioning store"
runapp(){  # $1 app-support dir · $2 repo root
  SAVED_APP="$CLAUDE_APP_SUPPORT_DIR"; export CLAUDE_APP_SUPPORT_DIR="$1"
  runjson "$2"
  export CLAUDE_APP_SUPPORT_DIR="$SAVED_APP"
}
appskill(){ mkdir -p "$1"; printf -- '---\nname: %s\ndescription: "app-side %s"\n---\n' \
  "$(basename "$1")" "$(basename "$1")" > "$1/SKILL.md"; }

# (i) an rpm-shape pack whose verbs collide, carrying hooks — the ghost this check exists for
GS="$W/app-ghost/local-agent-mode-sessions/4c5a94ac/f92345ac/rpm"
mkdir -p "$GS/plugin_ghost/.claude-plugin" "$GS/plugin_ghost/hooks"
echo '{"name":"ghostsuite","version":"2.13.0"}' > "$GS/plugin_ghost/.claude-plugin/plugin.json"
appskill "$GS/plugin_ghost/skills/alpha"; appskill "$GS/plugin_ghost/skills/beta"
echo '{"hooks":{"SessionStart":[]}}' > "$GS/plugin_ghost/hooks/hooks.json"
# the index the app writes beside its packs: a FILE at the same glob depth as a pack dir,
# so this also proves the scan skips non-directories instead of tripping on them.
echo '{"lastUpdated":1,"plugins":[{"id":"plugin_ghost","installationPreference":"available"}]}' \
  > "$GS/manifest.json"
runapp "$W/app-ghost" "$H"
warncase "app-side pack colliding with this tree's verbs" "SHADOW-APPSIDE"
grep -q "ghostsuite' v2.13.0" "$W/out.json" \
  && ok "the app-side WARN names the pack and its version" \
  || no "the app-side WARN does not name pack+version"
grep -q 'plugin_ghost' "$W/out.json" && ok "the app-side WARN names the path" \
  || no "the app-side WARN states no path"
grep -q "carries 2 of this tree's verbs" "$W/out.json" \
  && ok "the app-side WARN carries the collision count" || no "no collision count"
grep -q 'alpha, beta' "$W/out.json" && ok "the app-side WARN names the colliding verbs" \
  || no "the colliding verbs are not named"
grep -q 'REGISTERS HOOKS' "$W/out.json" && ok "a hook-registering app-side pack is called out" \
  || no "the app-side WARN never says whether the pack registers hooks"
grep -q 'shadow ladder rung 3 of 3' "$W/out.json" \
  && ok "the app-side fix names shadow-ladder rung 3" || no "the app-side fix names no rung"
grep -q 'plugin panel' "$W/out.json" \
  && ok "the app-side fix points at the app's panel, not a CLI verb" \
  || no "the app-side fix does not name the only surface that can fix it"

# (ii) the skills-plugin shape — a different depth and a different parent, same question
SP="$W/app-sp/local-agent-mode-sessions/skills-plugin/f92345ac/4c5a94ac"
mkdir -p "$SP/.claude-plugin"
echo '{"name":"anthropic-skills","version":"1.0.0"}' > "$SP/.claude-plugin/plugin.json"
appskill "$SP/skills/alpha"; appskill "$SP/skills/gamma"
runapp "$W/app-sp" "$H"
warncase "app-side pack in the skills-plugin shape" "SHADOW-APPSIDE"
grep -q 'skills-plugin shape' "$W/out.json" \
  && ok "the second store shape is scanned and named" || no "the skills-plugin shape is unread"

# (iii) a pack with no colliding verb is SILENT — a shadow check that flags every neighbour
#       is a shadow check nobody reads.
NC="$W/app-clean/local-agent-mode-sessions/4c5a94ac/f92345ac/rpm/plugin_clean"
mkdir -p "$NC/.claude-plugin"
echo '{"name":"cleanpack","version":"1.0.0"}' > "$NC/.claude-plugin/plugin.json"
appskill "$NC/skills/zulu"
runapp "$W/app-clean" "$H"
t "non-colliding app-side pack → exit 0" "$RC" "0"
t "non-colliding app-side pack → SHADOW-APPSIDE PASSes" "$(st 'SHADOW-APPSIDE')" "PASS"
t "non-colliding app-side pack → nothing warns" "$(nwarn)" "0"

# (iv) no store at all — the honest SKIP. Most machines are not desktop-app machines.
runapp "$W/no-such-app-support" "$H"
t "absent app-support dir → exit 0" "$RC" "0"
t "absent app-support dir → SHADOW-APPSIDE SKIPs" "$(st 'SHADOW-APPSIDE')" "SKIP"
t "absent app-support dir → nothing fails" "$(nfail)" "0"

# (v) the store is another application's state: doctor reads it and never writes to it.
BEFORE_APP="$(cd "$W/app-ghost" && find . -type f | sort | while read -r f; do \
  printf '%s %s\n' "$f" "$(cksum < "$f")"; done)"
runapp "$W/app-ghost" "$H"
AFTER_APP="$(cd "$W/app-ghost" && find . -type f | sort | while read -r f; do \
  printf '%s %s\n' "$f" "$(cksum < "$f")"; done)"
t "doctor never writes into the app-side store" \
  "$([ "$BEFORE_APP" = "$AFTER_APP" ] && echo identical || echo mutated)" "identical"

# ── C · argument handling and the --plugin mode ───────────────────────────────────────
echo "── C · arguments and modes"
python3 "$DOC" bogus --root "$H" >/dev/null 2>&1; t "unknown subcommand exits 2" "$?" "2"
python3 "$DOC" check --plugin "$W/nope" >/dev/null 2>&1; t "missing --plugin dir exits 3" "$?" "3"
python3 "$DOC" check --root "$W" >/dev/null 2>&1; t "a root holding no plugin exits 3" "$?" "3"
python3 "$DOC" check --plugin "$H/plugins/fixtureplug" --json > "$W/plug.json" 2>&1
t "--plugin mode exits 0 on a healthy plugin dir" "$?" "0"
t "--plugin mode is labelled" "$(py 'import json,sys;print(json.load(open(sys.argv[1]))["mode"])' "$W/plug.json")" "plugin"
t "--plugin mode skips the repo-only checks" \
  "$(py 'import json,sys
d=json.load(open(sys.argv[1]))
print(sum(1 for c in d["checks"] if c["status"]=="SKIP")>=2)' "$W/plug.json")" "True"
# the read-only boundary, asserted by content: every file byte-identical across a full run.
snap(){ (cd "$1" && find . -type f | sort | while read -r f; do printf '%s %s\n' "$f" "$(cksum < "$f")"; done); }
BEFORE="$(snap "$H")"; runjson "$H"; AFTER="$(snap "$H")"
t "doctor never writes into the target" "$([ "$BEFORE" = "$AFTER" ] && echo identical || echo mutated)" "identical"

# ── D · native Codex surface ─────────────────────────────────────────────────────────
echo "── D · native Codex surface"
python3 "$DOC" check --root "$H" --surface codex --json > "$W/codex.json" 2>&1
RC=$?
cp "$W/codex.json" "$W/out.json"
t "healthy Codex adapter exits 0" "$RC" "0"
t "Codex MANIFESTS pass" "$(st 'MANIFESTS')" "PASS"
t "Codex INSTALL FRESHNESS reads Codex inventory" "$(st 'INSTALL FRESHNESS')" "PASS"
t "Codex hook liveness is an honest SKIP" "$(st 'HOOKS FIRED')" "SKIP"
t "Codex Claude-token measurement is an honest SKIP" "$(st 'TOKEN BUDGET')" "SKIP"
t "Codex desktop-shadow probe is an honest SKIP" "$(st 'SHADOW-APPSIDE')" "SKIP"

HC="$W/codex-broken"; cp -R "$H" "$HC"
rm -f "$HC/plugins/fixtureplug/.codex-plugin/plugin.json"
python3 "$DOC" check --root "$HC" --surface codex --json > "$W/out.json" 2>&1
t "missing native Codex manifest exits 6" "$?" "6"
t "missing native Codex manifest fails MANIFESTS" "$(st 'MANIFESTS')" "FAIL"

echo
echo "doctor fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
