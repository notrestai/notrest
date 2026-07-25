#!/bin/bash
# fixture.sh — asserts doctor.py against a synthetic harness. Self-relative: runs from any
# cwd, writes only inside its own mktemp dir, touches no real project. The synthetic plugin
# is named 'fixtureplug' on purpose — a name with no marketplace clone on this machine, so
# INSTALL FRESHNESS reports SKIP instead of a machine-dependent WARN.
# Usage: bash <doctor-skill>/scripts/fixture.sh   (exit 0 = all pass, 1 = a failure)
set -u
DOC="$(cd "$(dirname "$0")" && pwd)/doctor.py"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  PASS  $1"; }
no(){ FAIL=$((FAIL+1)); echo "  FAIL  $1"; }
t(){ if [ "$2" = "$3" ]; then ok "$1 ($2)"; else no "$1 — expected [$3] got [$2]"; fi; }

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

cat > "$H/COORD.md" <<'EOF'
# COORD.md — session coordination ledger

Append-only, newest at the bottom.

## LEDGER
- [2026-07-24 10:00Z] [main] build the doctor -> skill landed | evidence: fixture exit 0
EOF

cat > "$H/COORD-AGENTS.md" <<'EOF'
# COORD-AGENTS.md — agent activity ledger (auto-written by the fixtureplug SubagentStop hook)

## LEDGER
- [2026-07-24 10:01Z] agent=a1 model=claude-opus-5 bytes=10 | last: done | transcript: /tmp/a1.jsonl
EOF

cat > "$H/spend/ledger.md" <<'EOF'
# spend ledger — append-only via spend.py; grades: observed|estimate
[2026-07-24 10:02Z] lane=subagent model=claude-opus-5 tokens=1000 grade=observed purpose="doctor build lane"
EOF

echo '{"generated":"2026-07-24 10:03Z","candidates":[]}' > "$H/compile/candidates.json"

# ── A · the healthy harness is clean ──────────────────────────────────────────────────
echo "── A · healthy synthetic harness"
runjson "$H"; t "healthy harness exits 0" "$RC" "0"
t "--json parses" "$(py 'import json,sys;print("yes" if json.load(open(sys.argv[1]))["checks"] else "no")' "$W/out.json")" "yes"
t "eight checks reported" "$(py 'import json,sys;print(len(json.load(open(sys.argv[1]))["checks"]))' "$W/out.json")" "8"
t "verdict is HEALTHY" "$(py 'import json,sys;print(json.load(open(sys.argv[1]))["verdict"])' "$W/out.json")" "HEALTHY"
t "no check fails" "$(nfail)" "0"
t "quoted colon-space description does NOT false-fire" "$(st FRONTMATTER)" "PASS"
t "INSTALL FRESHNESS skips with no clone" "$(st 'INSTALL FRESHNESS')" "SKIP"
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
