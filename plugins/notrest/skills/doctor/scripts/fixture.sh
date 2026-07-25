#!/bin/bash
# fixture.sh — asserts doctor.py against a synthetic harness. Self-relative: runs from any
# cwd, writes only inside its own mktemp dir, touches no real project.
#
# HERMETIC BY CONSTRUCTION. Two of doctor's checks read the machine, so the fixture hands
# them a machine of its own instead of asserting against whatever this laptop happens to
# have installed:
#   - $CLAUDE_CONFIG_DIR is redirected at a scratch config tree, so INSTALL FRESHNESS sees
#     exactly the skills-dir links and installs the fixture puts there — nothing else.
#   - a `claude` shim goes on PATH ahead of the real CLI, so TOKEN BUDGET reads a figure
#     the fixture chose ($FIXTURE_ALWAYS_ON) rather than the real plugin's cost.
# Usage: bash <doctor-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
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
mkdir -p "$H/.claude-plugin" "$H/plugins/fixtureplug/.claude-plugin" \
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
      "description": "A synthetic harness — two natural-language-invocable skills ride on it." },
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
EOF

cat > "$H/docs/oracle-skill-flow.html" <<'EOF'
<html><body><header>fixtureplug v1.0.0</header><footer>v1.0.0</footer></body></html>
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
t "ten checks reported" "$(py 'import json,sys;print(len(json.load(open(sys.argv[1]))["checks"]))' "$W/out.json")" "10"
t "verdict is HEALTHY" "$(py 'import json,sys;print(json.load(open(sys.argv[1]))["verdict"])' "$W/out.json")" "HEALTHY"
t "no check fails" "$(nfail)" "0"
t "no check warns" "$(nwarn)" "0"
t "quoted colon-space description does NOT false-fire" "$(st FRONTMATTER)" "PASS"
t "INSTALL FRESHNESS skips with no link and no clone" "$(st 'INSTALL FRESHNESS')" "SKIP"
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

# TOKEN BUDGET's defect does not live in the tree — it lives in what the tree COSTS, which
# only the CLI can say. The shim carries the injection, so the assertion stays offline.
export FIXTURE_ALWAYS_ON="9,999"
runjson "$H"
t "over-budget always-on cost → exit 6" "$RC" "6"
t "over-budget always-on cost → TOKEN BUDGET FAILs" "$(st 'TOKEN BUDGET')" "FAIL"
t "over-budget always-on cost → nothing else fails" "$(nfail)" "1"
unset FIXTURE_ALWAYS_ON

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

echo
echo "doctor fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
