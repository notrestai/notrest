#!/bin/bash
# fixture.sh — proves beam.py against a scratch repo, a real bare remote, and a fake cloud.
#
# The load-bearing proof is the NO-TOUCH LAW: `snapshot` publishes the CURRENT tree state
# — dirty tracked files and all — onto a git ref without ever checking out, switching,
# stashing or resetting. On the author's machine this tree is a plugin loaded IN PLACE, so
# a checkout would swap the running harness out from under the session. The fixture proves
# it the only way worth trusting: HEAD sha, .git/index sha256, `git status --porcelain`
# bytes, the dirty set and the HEAD reflog length are captured before and after and
# compared exactly.
#
# The "cloud" is a second clone of the same bare remote. It commits deliverables to the
# beam ref exactly as a remote lane is instructed to — which is the whole reason the ref,
# not a live session, is the wire.
#
# Never touches the real repo: everything lives under one mktemp tree. Self-relative.
# PASS/FAIL per assertion, summary at the end, nonzero exit if anything failed.
set -uo pipefail

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAM="$SD/beam.py"
[ -f "$BEAM" ] || { echo "FATAL: missing $BEAM"; exit 9; }

PASS=0; FAIL=0
ok()  { PASS=$((PASS+1)); echo "PASS  $1"; }
no()  { FAIL=$((FAIL+1)); echo "FAIL  $1${2:+  — $2}"; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1" "want '$3' got '$2'"; fi; }
has() { if grep -qF -- "$2" "$1"; then ok "$3"; else no "$3" "no match: $2"; fi; }
non() { if grep -qF -- "$2" "$1"; then no "$3" "unexpected match: $2"; else ok "$3"; fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
R="$TMP/repo"; REMOTE="$TMP/remote.git"; CLOUD="$TMP/cloud"
OUT="$TMP/out.txt"
TS="2026-07-26T2340Z"
B="python3 $BEAM"

run() { python3 "$BEAM" "$@" >"$OUT" 2>&1; echo "$?"; }
gr()  { git --no-optional-locks -C "$R" "$@"; }
idxsha() { shasum -a 256 "$R/.git/index" | cut -d' ' -f1; }

echo "── 0. scratch estate: repo + bare remote"
git init -q -b main "$R" 2>/dev/null || git init -q "$R"
git -C "$R" config user.email fixture@beam.test
git -C "$R" config user.name "beam fixture"
git -C "$R" config commit.gpgsign false
mkdir -p "$R/src"
printf 'v1\n' > "$R/src/app.txt"
printf '# scratch\n' > "$R/README.md"
git -C "$R" add -A >/dev/null 2>&1
git -C "$R" commit -qm "init" >/dev/null 2>&1
git init -q --bare "$REMOTE"
git -C "$R" remote add origin "$REMOTE"
git -C "$R" push -q origin HEAD:refs/heads/main
git -C "$REMOTE" symbolic-ref HEAD refs/heads/main   # so the cloud clone checks out quietly
chk "scratch repo has one commit" "$(gr rev-list --count HEAD)" "1"

echo "── 1. static: the no-touch law is enforced in the source, not just in prose"
if grep -nE '"(checkout|switch|stash|reset)"' "$BEAM" >/dev/null; then
  no "beam.py never names checkout/switch/stash/reset as a git verb" "$(grep -nE '"(checkout|switch|stash|reset)"' "$BEAM" | head -3)"
else ok "beam.py never names checkout/switch/stash/reset as a git verb"; fi
grep -q "GIT_INDEX_FILE" "$BEAM" && ok "beam.py builds against a temporary index (GIT_INDEX_FILE)" \
  || no "beam.py builds against a temporary index (GIT_INDEX_FILE)"

echo "── 2. bank: the model's brief + digest + file list become a payload"
printf 'Build the widget parser and prove it with a fixture.\n' > "$TMP/brief-a.md"
printf -- '- parser skeleton landed in src/app.txt\n- tests NOT written yet\n' > "$TMP/prog-a.md"
printf 'src/app.txt\n\n# a comment line\nsrc/app.txt\n' > "$TMP/files-a.txt"
chk "bank lane a → exit 0" \
  "$(run bank --root "$R" --ts "$TS" --lane a --brief "$TMP/brief-a.md" \
        --progress "$TMP/prog-a.md" --files "$TMP/files-a.txt")" "0"
LA="$R/beam/$TS/lane-a"
for f in brief.md progress.md files.txt resume-prompt.md; do
  [ -f "$LA/$f" ] && ok "  payload has $f" || no "  payload has $f"
done
chk "  files.txt de-duplicated and stripped comments (1 path)" "$(wc -l < "$LA/files.txt" | tr -d ' ')" "1"
chk "  STATE starts BANKED" "$(cat "$LA/STATE")" "BANKED"
has "$LA/resume-prompt.md" "Build the widget parser" "  resume-prompt carries the brief verbatim"
has "$LA/resume-prompt.md" "tests NOT written yet" "  resume-prompt carries the progress digest"
has "$LA/resume-prompt.md" '- `src/app.txt`' "  resume-prompt points at the files the lane held"
has "$LA/resume-prompt.md" 'refs/heads/beam/'"$TS" "  resume-prompt names the beam ref it lives on"
echo "   laws block:"
has "$LA/resume-prompt.md" 'model: "opus"' "  LAW 1 names explicit opus"
has "$LA/resume-prompt.md" 'never `subagent_type: "fork"`' "  LAW 1 bans forks (they inherit the seat)"
has "$LA/resume-prompt.md" "Deliverables commit to the beam ref" "  LAW 2 puts deliverables on the ref, not in a session"
has "$LA/resume-prompt.md" "still emit one" "  LAW 3 keeps the original brief's finding records"
has "$LA/resume-prompt.md" "RETURN.md" "  LAW 4 demands a tight RETURN.md"
has "$LA/resume-prompt.md" "CHECKPOINTED" "  the physics is stated to the lane that inherits it"

printf 'Write the release notes for v4.0.0.\n' > "$TMP/brief-b.md"
printf -- '- nothing yet\n' > "$TMP/prog-b.md"
chk "bank lane b (no --files) → exit 0" \
  "$(run bank --root "$R" --ts "$TS" --lane b --brief "$TMP/brief-b.md" --progress "$TMP/prog-b.md")" "0"
chk "  files.txt is empty when no list was banked" "$(wc -l < "$R/beam/$TS/lane-b/files.txt" | tr -d ' ')" "0"
has "$R/beam/$TS/lane-b/resume-prompt.md" "(none listed" "  resume-prompt says so instead of implying scope"

echo "── 2b. bank --forced: a stopped lane must carry its loss, not hide it"
printf 'Refactor the loader.\n' > "$TMP/brief-c.md"
printf -- '- three files rewritten (last durable artifact)\n' > "$TMP/prog-c.md"
chk "bank --forced → exit 0" \
  "$(run bank --root "$R" --ts "$TS" --lane c --brief "$TMP/brief-c.md" \
        --progress "$TMP/prog-c.md" --forced --stopped-at "2026-07-26T2338Z")" "0"
LC="$R/beam/$TS/lane-c"
[ -f "$LC/LOSS-ESTIMATE.md" ] && ok "  payload carries LOSS-ESTIMATE.md" || no "  payload carries LOSS-ESTIMATE.md"
has "$LC/LOSS-ESTIMATE.md" "stopped mid-flight at 2026-07-26T2338Z" "  it names when the lane was stopped"
has "$LC/LOSS-ESTIMATE.md" "progress banked through last durable artifact" "  the pinned sentence, unedited"
has "$LC/LOSS-ESTIMATE.md" "re-derives the unbanked stride" "  and it never claims the checkpoint was lossless"
has "$LC/resume-prompt.md" "THIS LANE WAS STOPPED MID-FLIGHT" "  the respawned lane is TOLD it was stopped"
has "$LC/resume-prompt.md" "Do not assume the last step in the digest" "  and told not to trust the digest as complete"
has "$OUT" "LOSS-ESTIMATE:" "  bank echoes the loss estimate to the seat"
run bank --root "$R" --ts "$TS" --lane c --brief "$TMP/brief-c.md" --progress "$TMP/prog-c.md" >/dev/null
[ -f "$LC/LOSS-ESTIMATE.md" ] && ok "  a plain re-bank cannot un-stop the lane (artifact survives)" \
  || no "  a plain re-bank cannot un-stop the lane (artifact survives)"

echo "── 3. manifest: regenerated from the directory, byte-identical every time"
chk "manifest → exit 0" "$(run manifest --root "$R" --ts "$TS")" "0"
M="$R/beam/$TS/MANIFEST.md"
[ -f "$M" ] && ok "  MANIFEST.md written" || no "  MANIFEST.md written"
has "$M" "| a | BANKED |" "  lane a listed with its state"
has "$M" "| b | BANKED |" "  lane b listed with its state"
has "$M" "| c ⚠force-stopped | BANKED |" "  the force-stopped lane is flagged in its own row"
has "$M" "## Loss estimates — lanes stopped mid-flight" "  manifest carries a loss-estimate section"
has "$M" "- \`c\` — LOSS-ESTIMATE: stopped mid-flight" "  with the lane's pinned line"
has "$M" "\`FORCED:<id>\`" "  the state legend explains FORCED"
has "$M" "NONE YET" "  says plainly that nothing is snapshotted yet"
has "$M" "## Recall checklist" "  carries the recall checklist"
has "$M" "spend.py log --lane beam-remote" "  checklist routes un-receipted lanes to the ledger script"
has "$M" "claude --teleport" "  checklist carries the session-level recall pointer"
cp "$M" "$TMP/manifest-1.md"
CP="$R/beam/$TS/CHECKPOINT.md"
cp "$CP" "$TMP/checkpoint-1.md"
run manifest --root "$R" --ts "$TS" >/dev/null
if cmp -s "$TMP/manifest-1.md" "$M"; then ok "  regeneration is byte-identical (idempotent)"
else no "  regeneration is byte-identical (idempotent)" "$(diff "$TMP/manifest-1.md" "$M" | head -3)"; fi
if cmp -s "$TMP/checkpoint-1.md" "$CP"; then ok "  CHECKPOINT.md regeneration is byte-identical too"
else no "  CHECKPOINT.md regeneration is byte-identical too"; fi

echo "── 3b. CHECKPOINT.md — the cloud session's whole instruction, in the repo"
[ -f "$CP" ] && ok "  manifest writes CHECKPOINT.md" || no "  manifest writes CHECKPOINT.md"
has "$CP" "git fetch origin beam/$TS && git checkout beam/$TS" "  step 0 is the checkout-first law"
has "$CP" "NOT this one" "  says why: a clone lands on the wrong branch"
has "$CP" "notrest@notrest" "  tells the cloud session the harness is carried on the ref"
has "$CP" "1. lane \`a\`" "  lane execution order, lane a first"
has "$CP" "2. lane \`b\`" "  lane execution order, lane b second"
has "$CP" "3. lane \`c\`" "  lane execution order, lane c third"
has "$CP" 'model: "opus"' "  each lane spawns as an explicit opus agent"
has "$CP" 'never `subagent_type: "fork"`' "  fork ban restated to the cloud seat"
has "$CP" "git push origin HEAD:beam/$TS" "  deliverables are committed AND pushed back"
has "$CP" "beam/$TS/CLOUD-DONE.md" "  final step: the cloud session signs off in a file"

echo "── 4. snapshot: the live tree publishes WITHOUT the live tree moving"
printf 'v2-dirty\n' > "$R/src/app.txt"            # tracked + dirty: must travel
printf 'junk\n' > "$R/scratch.tmp"                # untracked + not payload: must NOT travel
BEFORE_HEAD="$(gr rev-parse HEAD)"
BEFORE_IDX="$(idxsha)"
gr status --porcelain > "$TMP/status-before.txt"
gr diff --name-only HEAD -- > "$TMP/dirty-before.txt"
BEFORE_REFLOG="$(gr reflog | wc -l | tr -d ' ')"
BEFORE_BRANCH="$(gr rev-parse --abbrev-ref HEAD)"

chk "snapshot --push → exit 0" "$(run snapshot --root "$R" --ts "$TS" --push --remote origin)" "0"
has "$OUT" "NO-TOUCH PROOF" "  prints its own no-touch proof line"
has "$OUT" "UNCHANGED" "  and the proof says UNCHANGED"
REF="refs/heads/beam/$TS"
gr rev-parse --verify -q "$REF" >/dev/null && ok "  local ref $REF exists" || no "  local ref $REF exists"
git --no-optional-locks -C "$REMOTE" rev-parse --verify -q "$REF" >/dev/null \
  && ok "  the BARE REMOTE has the ref (it is really published)" || no "  the BARE REMOTE has the ref"
chk "  the ref carries the DIRTY content, not HEAD's" "$(gr show "$REF:src/app.txt")" "v2-dirty"
gr ls-tree -r --name-only "$REF" > "$TMP/reftree.txt"
has "$TMP/reftree.txt" "beam/$TS/lane-a/brief.md" "  the ref carries lane a's payload"
has "$TMP/reftree.txt" "beam/$TS/lane-b/resume-prompt.md" "  the ref carries lane b's payload"
has "$TMP/reftree.txt" "beam/$TS/MANIFEST.md" "  the ref carries the manifest"
non "$TMP/reftree.txt" "scratch.tmp" "  untracked non-payload junk is NOT swept onto the ref"
chk "  the snapshot commit is parented on HEAD" "$(gr rev-parse "$REF^")" "$BEFORE_HEAD"

echo "   the proof (before → after):"
chk "  HEAD sha unchanged" "$(gr rev-parse HEAD)" "$BEFORE_HEAD"
chk "  .git/index sha256 unchanged" "$(idxsha)" "$BEFORE_IDX"
gr status --porcelain > "$TMP/status-after.txt"
if cmp -s "$TMP/status-before.txt" "$TMP/status-after.txt"; then ok "  git status --porcelain byte-identical"
else no "  git status --porcelain byte-identical" "$(diff "$TMP/status-before.txt" "$TMP/status-after.txt" | head -3)"; fi
gr diff --name-only HEAD -- > "$TMP/dirty-after.txt"
cmp -s "$TMP/dirty-before.txt" "$TMP/dirty-after.txt" && ok "  the dirty set is unchanged" || no "  the dirty set is unchanged"
chk "  HEAD reflog did not grow (no checkout happened)" "$(gr reflog | wc -l | tr -d ' ')" "$BEFORE_REFLOG"
chk "  still on the same branch" "$(gr rev-parse --abbrev-ref HEAD)" "$BEFORE_BRANCH"
chk "  the working file still holds the dirty bytes" "$(cat "$R/src/app.txt")" "v2-dirty"

S="$R/beam/$TS/SNAPSHOT.txt"
has "$S" "ref=$REF" "  SNAPSHOT.txt records the ref"
has "$S" "pushed=origin" "  SNAPSHOT.txt records where it was pushed"
grep -q "^commit=[0-9a-f]\{40\}$" "$S" && ok "  SNAPSHOT.txt records the commit sha" || no "  SNAPSHOT.txt records the commit sha"
run manifest --root "$R" --ts "$TS" >/dev/null
has "$M" "pushed: origin" "  manifest now shows the pushed snapshot"

echo "── 4b. harness carriage: the ref installs notrest; the worktree never changes"
# the repo has NO .claude/settings.json — the ref must gain one anyway, on the ref ONLY
gr show "$REF:.claude/settings.json" > "$TMP/settings-ref.json" 2>/dev/null \
  && ok "  the ref carries .claude/settings.json" || no "  the ref carries .claude/settings.json"
python3 -c "
import json,sys
d=json.load(open('$TMP/settings-ref.json'))
assert d['enabledPlugins']['notrest@notrest'] is True, 'plugin not enabled'
assert d['extraKnownMarketplaces']['notrest']['source']['url'].endswith('notrest.git'), 'marketplace missing'
" 2>/dev/null && ok "  it parses, enables notrest@notrest and knows the marketplace" \
  || no "  it parses, enables notrest@notrest and knows the marketplace" "$(cat "$TMP/settings-ref.json")"
[ ! -e "$R/.claude/settings.json" ] \
  && ok "  REF ONLY: the file still does not exist in the working tree" \
  || no "  REF ONLY: the file still does not exist in the working tree"

# now give the repo a real settings file with keys of its own, and re-snapshot: merge, not clobber
mkdir -p "$R/.claude"
cat > "$R/.claude/settings.json" <<'JSON'
{
  "permissions": {"allow": ["Bash(ls:*)"]},
  "extraKnownMarketplaces": {"other": {"source": {"source": "git", "url": "https://example.test/o.git"}}}
}
JSON
LIVE_SHA="$(shasum -a 256 "$R/.claude/settings.json" | cut -d' ' -f1)"
gr status --porcelain > "$TMP/status-before.txt"          # re-baseline: a new untracked file exists
chk "re-snapshot over an existing settings file → exit 0" \
  "$(run snapshot --root "$R" --ts "$TS" --push --remote origin)" "0"
has "$OUT" "merged into the existing file" "  reports the merge honestly"
gr show "$REF:.claude/settings.json" > "$TMP/settings-ref2.json"
python3 -c "
import json
d=json.load(open('$TMP/settings-ref2.json'))
assert d['permissions']['allow']==['Bash(ls:*)'], 'clobbered an unrelated key'
assert 'other' in d['extraKnownMarketplaces'], 'dropped the repo own marketplace'
assert 'notrest' in d['extraKnownMarketplaces'], 'did not add notrest'
assert d['enabledPlugins']['notrest@notrest'] is True
" 2>/dev/null && ok "  merged: repo keys preserved, notrest added alongside" \
  || no "  merged: repo keys preserved, notrest added alongside" "$(cat "$TMP/settings-ref2.json")"
chk "  the WORKING COPY of settings.json is byte-identical" \
  "$(shasum -a 256 "$R/.claude/settings.json" | cut -d' ' -f1)" "$LIVE_SHA"
gr status --porcelain > "$TMP/status-after2.txt"
cmp -s "$TMP/status-before.txt" "$TMP/status-after2.txt" \
  && ok "  re-snapshot left the worktree byte-identical too" || no "  re-snapshot left the worktree byte-identical too"
printf '{ not json' > "$R/.claude/settings.json"
run snapshot --root "$R" --ts "$TS" >/dev/null
has "$OUT" "SKIPPED" "  unparseable settings → carriage SKIPPED, never silently rewritten"
has "$OUT" "WITHOUT the harness" "  and it says out loud what the cloud clone will lack"
cat > "$R/.claude/settings.json" <<'JSON'
{
  "permissions": {"allow": ["Bash(ls:*)"]},
  "extraKnownMarketplaces": {"other": {"source": {"source": "git", "url": "https://example.test/o.git"}}}
}
JSON
run snapshot --root "$R" --ts "$TS" --push --remote origin >/dev/null
S_COMMIT="$(grep '^commit=' "$S" | cut -d= -f2)"

echo "── 5. mark: state flips, handles stick, manifest follows"
chk "mark a SPAWNED (+ durable handles) → exit 0" \
  "$(run mark --root "$R" --ts "$TS" --lane a --state "SPAWNED:remote-123" \
        --session-url "https://claude.ai/code/s/abc123" --meta "/tmp/meta.json")" "0"
chk "  STATE file holds it" "$(cat "$LA/STATE")" "SPAWNED:remote-123"
has "$M" "SPAWNED:remote-123" "  manifest regenerated with the remote id"
has "$M" "## Durable handles" "  manifest keeps the handles that outlive this session"
has "$M" "https://claude.ai/code/s/abc123" "  the session URL is recorded"
has "$M" "meta: /tmp/meta.json" "  the remote-agent meta.json path is recorded"
chk "mark b SPAWNED → exit 0" "$(run mark --root "$R" --ts "$TS" --lane b --state "SPAWNED:remote-456")" "0"
chk "mark c FORCED → exit 0 (a forced respawn is its own state)" \
  "$(run mark --root "$R" --ts "$TS" --lane c --state "FORCED:remote-789")" "0"
has "$M" "FORCED:remote-789" "  manifest distinguishes it from a clean spawn"
chk "mark with a nonsense state → exit 2" "$(run mark --root "$R" --ts "$TS" --lane a --state "FLYING")" "2"

echo "── 6. rail: the respawn instruction (the ONLY place the rail lives)"
chk "rail → exit 0" "$(run rail --root "$R" --ts "$TS" --lane a)" "0"
has "$OUT" "RAIL v1" "  labelled RAIL v1"
has "$OUT" "claude --cloud \"git fetch origin beam/$TS && git checkout beam/$TS, then read beam/$TS/CHECKPOINT.md and execute it\"" \
  "  (a) PRIMARY is the exact one-line cloud-session command"
has "$OUT" "(a) PRIMARY" "  (a) is labelled the primary path"
has "$OUT" "survives the laptop closing" "  (a) says why it is primary: it really detaches"
has "$OUT" "clones the cwd" "  (a) explains the checkout-first law"
has "$OUT" "--session-url" "  (a) tells the seat to record the durable handle"
has "$OUT" "clones the DEFAULT branch" "  (b) routine variant repeats the checkout-first law"
has "$OUT" "WRAPPED AS UNTRUSTED" "  (b) warns the fire-text arrives untrusted"
has "$OUT" "never self-schedules" "  (b) the owner creates the routine, not the harness"
has "$OUT" "Continue in" "  (c) the desktop hand-off path"
has "$OUT" "clean tree" "  (c) names its precondition"
has "$OUT" "DEGRADES SILENTLY" "  (d) the gated fast path is marked as silently degrading"
has "$OUT" 'status "remote_launched"' "  (d) demands the remote_launched assertion"
has "$OUT" '"subagent_type": "general-purpose"' "  (d) names the subagent type"
has "$OUT" '"model": "opus"' "  (d) sets model opus explicitly"
has "$OUT" '"isolation": "remote"' "  (d) asks for the remote rail"
has "$OUT" "Build the widget parser" "  (d) carries the resume prompt as the payload"
has "$OUT" 'never subagent_type "fork"' "  states the fork ban next to the call"
has "$OUT" "untracked files never travel" "  transport law: only committed payload travels"
has "$OUT" "prompt stays one" "  transport law: the checkpoint is in the repo, not the prompt"
chk "rail with no --lane → exit 0 (every lane)" "$(run rail --root "$R" --ts "$TS")" "0"
has "$OUT" "Write the release notes" "  the all-lanes form emits lane b's payload too"
run bank --root "$R" --ts NOTPUSHED --lane solo --brief "$TMP/brief-b.md" --progress "$TMP/prog-b.md" >/dev/null
chk "rail on an un-snapshotted ts → exit 0" "$(run rail --root "$R" --ts NOTPUSHED --lane solo)" "0"
has "$OUT" "NOT PUSHED" "  and it refuses to pretend a local-only payload is reachable"

echo "── 7. the fake cloud commits to the ref (a second clone — the wire is the ref)"
git clone -q "$REMOTE" "$CLOUD"
git -C "$CLOUD" config user.email cloud@beam.test
git -C "$CLOUD" config user.name "beam cloud lane"
git -C "$CLOUD" config commit.gpgsign false
git -C "$CLOUD" checkout -q -b work "origin/beam/$TS"
printf 'v3-from-the-cloud\n' > "$CLOUD/src/app.txt"
mkdir -p "$CLOUD/beam/$TS/lane-a"
printf '# RETURN — lane a\n\nparser done; fixture green.\n' > "$CLOUD/beam/$TS/lane-a/RETURN.md"
git -C "$CLOUD" add -A >/dev/null
git -C "$CLOUD" commit -qm "lane a delivers"
git -C "$CLOUD" push -q origin "HEAD:$REF"
ok "cloud clone committed a deliverable onto $REF"

echo "── 8. down: MISSING is loud, and nothing is folded for you"
DOWN_RC="$(run down --root "$R" --ts "$TS" --fetch --remote origin)"
chk "down --fetch with one lane still out → exit 3" "$DOWN_RC" "3"
has "$OUT" "lane a  [SPAWNED:remote-123]  DELIVERED" "  lane a reads DELIVERED with its state"
has "$OUT" "beam/$TS/lane-a/RETURN.md" "  names the RETURN.md the lane committed"
has "$OUT" "src/app.txt" "  names the source file the lane changed"
has "$OUT" "git show refs/beam/recall/$TS:src/app.txt > src/app.txt" "  emits a copy-paste fold command"
has "$OUT" "lane b  [SPAWNED:remote-456]  MISSING" "  lane b reads MISSING"
has "$OUT" "still running or it died" "  refuses to guess WHY a lane delivered nothing"
has "$OUT" "no CLOUD-DONE.md on the ref" "  says the cloud session has not signed off yet"
has "$OUT" "handles a:" "  replays the durable handles for the lane still out"
has "$OUT" "claude --teleport" "  points at session-level recall for the conversation itself"
has "$OUT" "1 DELIVERED · 2 MISSING" "  verdict counts every lane"
has "$OUT" "⚠ FORCED BEAM" "  the force-stopped lane stays flagged at recall"
chk "  the fold was NOT executed (local file untouched)" "$(cat "$R/src/app.txt")" "v2-dirty"
gr status --porcelain > "$TMP/status-down.txt"
cmp -s "$TMP/status-before.txt" "$TMP/status-down.txt" && ok "  down left the worktree byte-identical" \
  || no "  down left the worktree byte-identical"
chk "  --fetch did NOT clobber the local beam branch" "$(gr rev-parse "$REF")" "$(grep '^commit=' "$S" | cut -d= -f2)"
gr rev-parse --verify -q "refs/beam/recall/$TS" >/dev/null \
  && ok "  the fetched tip landed in its own recall namespace" || no "  the fetched tip landed in its own recall namespace"

echo "── 9. down again once every lane has delivered and the session signed off"
mkdir -p "$CLOUD/beam/$TS/lane-b" "$CLOUD/beam/$TS/lane-c"
printf '# RETURN — lane b\n\nrelease notes written.\n' > "$CLOUD/beam/$TS/lane-b/RETURN.md"
printf '# RETURN — lane c\n\nloader refactor re-derived from the files.\n' > "$CLOUD/beam/$TS/lane-c/RETURN.md"
printf '## cloud session sign-off\n\nall three lanes ran; nothing left running.\n' > "$CLOUD/beam/$TS/CLOUD-DONE.md"
git -C "$CLOUD" add -A >/dev/null
git -C "$CLOUD" commit -qm "lanes b and c deliver + sign-off"
git -C "$CLOUD" push -q origin "HEAD:$REF"
chk "down --fetch with everything home → exit 0" "$(run down --root "$R" --ts "$TS" --fetch --remote origin)" "0"
has "$OUT" "the cloud session signed off" "  reads the CLOUD-DONE.md sign-off"
has "$OUT" "all three lanes ran" "  and shows what it said"
has "$OUT" "3 DELIVERED · 0 MISSING" "  verdict is clean"
has "$OUT" "re-derived the unbanked stride" "  a delivered FORCED lane still warns before you fold it"
non "$OUT" "MISSING (" "  nothing is reported missing"
non "$OUT" "UNATTRIBUTED" "  the sign-off file is not misfiled as an orphan"
has "$OUT" "spend.py" "  points at the receipt before the recall is called done"

echo "── 10. status + RECALLED"
chk "status before recall → exit 0" "$(run status --root "$R")" "0"
has "$OUT" "FORCED=1" "  status counts forced respawns separately"
has "$OUT" "⚠1 stopped mid-flight" "  and never lets a force-stop go unmentioned"
chk "mark a RECALLED → exit 0" "$(run mark --root "$R" --ts "$TS" --lane a --state RECALLED)" "0"
run mark --root "$R" --ts "$TS" --lane b --state RECALLED >/dev/null
run mark --root "$R" --ts "$TS" --lane c --state RECALLED >/dev/null
chk "status → exit 0" "$(run status --root "$R")" "0"
has "$OUT" "$TS" "  status names the checkpoint"
has "$OUT" "lanes=3" "  status counts the lanes"
has "$OUT" "RECALLED=3" "  status shows every lane recalled"
has "$OUT" "pushed=origin" "  status shows where the ref went"

echo "── 11. malformed input exits 2 — never 0, never a traceback"
chk "no subcommand → 2" "$(run)" "2"
chk "unknown subcommand → 2" "$(run teleport --root "$R")" "2"
chk "bank without --brief → 2" "$(run bank --root "$R" --ts "$TS" --lane c --progress "$TMP/prog-b.md")" "2"
chk "bank with a nonexistent brief → 2" \
  "$(run bank --root "$R" --ts "$TS" --lane c --brief "$TMP/nope.md" --progress "$TMP/prog-b.md")" "2"
printf '' > "$TMP/empty.md"
chk "bank with an EMPTY brief → 2 (unresumable)" \
  "$(run bank --root "$R" --ts "$TS" --lane c --brief "$TMP/empty.md" --progress "$TMP/prog-b.md")" "2"
chk "path-traversing lane label → 2" \
  "$(run bank --root "$R" --ts "$TS" --lane "../evil" --brief "$TMP/brief-b.md" --progress "$TMP/prog-b.md")" "2"
chk "ts with a space → 2 (it becomes a git ref component)" \
  "$(run manifest --root "$R" --ts "foo bar")" "2"
chk "manifest for an unknown ts → 2" "$(run manifest --root "$R" --ts 2020-01-01)" "2"
chk "down for an unknown ts → 2" "$(run down --root "$R" --ts 2020-01-01)" "2"
chk "rail for an unknown lane → 2" "$(run rail --root "$R" --ts "$TS" --lane zzz)" "2"
mkdir -p "$R/beam/emptyts"
chk "snapshot with no lanes banked → 2" "$(run snapshot --root "$R" --ts emptyts)" "2"
chk "--root outside any git repo → 2" "$(run status --root "$TMP")" "2"

echo
echo "──────────────────────────────────────────────"
echo "beam fixture: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
