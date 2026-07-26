#!/usr/bin/env python3
"""beam.py — checkpoint an in-flight lane, publish it, respawn it elsewhere, fold it home.

THE PHYSICS (pinned, and the reason this script exists): nothing teleports process memory.
A running agent lane cannot be "moved" — it can only be CHECKPOINTED and RESPAWNED. A
lane's movable state is exactly three things: its brief (why it exists), a digest of what
it has done so far, and the files it was holding. Everything else — context window,
tool history, the model's train of thought — dies at the checkpoint and is not recoverable
by any mechanism, cloud or otherwise. beam is honest about that: it moves the recoverable
part and says so.

THE ESTATE IS THE WIRE. The payload is plain files under `beam/<ts>/`, published as a git
ref (`refs/heads/beam/<ts>`). A remote lane clones the ref, works, and COMMITS its
deliverables back to that ref; recall reads the ref. Nothing depends on a live session
being reachable, because a live session is exactly the thing that just went away.

THE SEAT/SCRIPT SPLIT. The MODEL owns what only the harness exposes: which lanes are live,
what each was told, how far each got — a script cannot read the harness's task list or a
lane's output. The model writes those into brief/progress files. This SCRIPT owns storage,
manifest bookkeeping, and every git mechanic. Neither guesses at the other's job.

Subcommands:
  bank     --root . --ts ID --lane LABEL --brief F --progress F [--files F]
  manifest --root . --ts ID                     (also writes CHECKPOINT.md)
  snapshot --root . --ts ID [--push] [--remote origin]
  mark     --root . --ts ID --lane LABEL --state BANKED|SPAWNED:<id>|RECALLED
                                                [--session-url URL] [--meta PATH]
  rail     --root . --ts ID [--lane LABEL]
  down     --root . --ts ID [--fetch] [--remote origin]
  status   --root .

HARNESS CARRIAGE. User-scoped configuration does not travel: a session started elsewhere
lands with no ~/.claude skills, no user CLAUDE.md, and none of this harness. Project
settings on the ref DO travel, so `snapshot` merges the marketplace + enabledPlugins keys
into the ref's `.claude/settings.json` — REF ONLY, via the temp index, leaving the working
copy byte-untouched — and the clone installs the harness for itself. (The shadow-guard law
against installing notrest@notrest is machine-scoped: on a cloud VM it is the correct move.)

THE NO-TOUCH LAW (`snapshot`). The tree beam runs in is frequently a LIVE tree — on the
author's machine it is a plugin loaded in place, where a checkout would swap the running
harness out from under the session. So `snapshot` never runs checkout, switch, stash, or
reset. It builds the published commit entirely with plumbing against a TEMPORARY index
(GIT_INDEX_FILE): read-tree from HEAD, add the dirty tracked paths and the payload dir,
write-tree, commit-tree parented on HEAD, update-ref, push. HEAD, the real index, and the
worktree are byte-identical before and after — snapshot prints the proof line itself, and
scripts/fixture.sh proves it independently.

Exit: 0 ok · 2 usage/argument error · 3 `down` found a lane with nothing delivered
      · 1 a git operation failed (message on stderr).
"""

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
STATE_RE = re.compile(r"^(BANKED|RECALLED|(SPAWNED|FORCED):\S.*)$")
# The pinned honesty sentence for a lane that was STOPPED to be beamed. A mid-flight
# checkpoint is never lossless: the stride between the last durable artifact and the kill
# is gone, and the respawn re-derives it. Saying so is not optional.
LOSS_LINE = ("LOSS-ESTIMATE: stopped mid-flight at {when}; progress banked through last "
             "durable artifact; the respawn re-derives the unbanked stride.")
# read-only git verbs: run them with --no-optional-locks so a status/diff can never
# rewrite .git/index behind our back (the stat-cache refresh would muddy the proof).
RO_VERBS = {"rev-parse", "diff", "status", "ls-tree", "show", "merge-base",
            "cat-file", "for-each-ref", "log"}

# HARNESS CARRIAGE. User-scoped configuration does not travel: a cloud session lands with
# no ~/.claude skills, no user CLAUDE.md, and no user-enabled plugins — i.e. with none of
# this harness. Project-scoped settings on the ref DO travel, so the beam ref carries a
# merged .claude/settings.json that makes the cloud clone install the harness for itself.
# Merged ONLY into the published tree, never into the working copy.
SETTINGS_PATH = ".claude/settings.json"
HARNESS_SETTINGS = {
    "extraKnownMarketplaces": {
        "notrest": {"source": {"source": "git",
                               "url": "https://github.com/notrestai/notrest.git"}}},
    "enabledPlugins": {"notrest@notrest": True},
}

LAWS = """## THE LAWS (this lane runs remote — they are not optional)

1. **Model.** You are an OPUS lane. Every agent you spawn sets `model: "opus"` explicitly —
   never `subagent_type: "fork"` (a fork inherits the seat's model), and never omit the
   field (an omission silently bills the seat's model and breaks the offload policy).
2. **Deliverables commit to the beam ref.** Work that exists only in your session does not
   exist: the session that recalls you will never see your transcript, and no one can fetch
   a live process. Commit every deliverable to `refs/heads/beam/{ts}` and push it.
3. **Records.** Wherever the brief above said to emit a finding record, still emit one —
   through the archivist door, validated, honesty label intact. A payload the door would
   reject is not a payload.
4. **Return tight.** Write `beam/{ts}/lane-{label}/RETURN.md` and commit it: what landed
   (paths), what was proven (command + exit code), what is deliberately not done. No
   transcript, no narration — recall reads this file, not your history.
5. **Stay in your lane.** Touch only what the brief and the file list name. You cannot see
   the seat's other lanes; a file you were not handed is a file someone else is holding.
"""

FORCED_BLOCK = """
> **!! THIS LANE WAS STOPPED MID-FLIGHT.** {loss}
> Read that literally: the digest below ends at the last thing the previous lane wrote to
> disk, and it had almost certainly done more thinking than that. Re-derive the difference
> from the files before you build on it. Do not assume the last step in the digest was the
> last step taken.
"""

TEMPLATE = """# RESUME — lane `{label}` (beamed {ts})

You are picking up a lane that was already running somewhere else. It was CHECKPOINTED,
not paused: no process, no context window, and no tool history came with it. Everything
that survived is in this file and in the ref named at the bottom. Where the digest below
is thinner than you would like, re-derive from the files — do not invent the missing part.
{forced_block}
## The brief (unchanged — this is still the job)

{brief}

## Done so far (the previous lane's own digest — treat as [recall]; verify what you lean on)

{progress}

## Files this lane was holding

{files_block}

## Where you are

Snapshot ref: `refs/heads/beam/{ts}` — it carries the seat's working tree as of the beam
(tracked dirty files included, not just the last commit) plus this payload under
`beam/{ts}/`. Your payload directory is `beam/{ts}/lane-{label}/`; the brief, the digest,
and the file list above are the files in it.

{laws}"""

CHECKPOINT = """# CHECKPOINT — beam {ts}

You are a session started to finish work that was checkpointed onto this branch. Read this
file top to bottom before you do anything else. It is the whole instruction: the prompt that
started you is one line on purpose, because a prompt is context-bounded and a repository
is not.

## Step 0 — get onto the beam ref (FIRST, before anything else)

```
git fetch origin beam/{ts} && git checkout beam/{ts}
```

Cloud sessions and scheduled runs clone the repository's current-or-default branch, which is
NOT this one. Everything below — the payloads, the manifest, the harness settings — exists
only on `beam/{ts}`. If the checkout fails, stop and report; do not work on the wrong branch.

## Step 1 — the harness

This ref carries `.claude/settings.json` enabling `notrest@notrest` from its marketplace, so
this session can install the harness for itself. User-scoped skills and CLAUDE.md did NOT
travel — nothing outside this repository came with you.

## Step 2 — the lanes, in this order

{lane_block}

Spawn ONE background agent per lane, in the order listed. For each: `subagent_type`
`general-purpose`, **`model: "opus"` explicit**, and the prompt is the FULL contents of that
lane's `resume-prompt.md`. Never `subagent_type: "fork"` — a fork inherits this session's
model. You are the seat here: decompose, judge, apply, gate — do not do the lanes' work
yourself.

## Step 3 — the laws (they bind you and every lane you spawn)

{laws}

## Step 4 — deliver

Every deliverable is committed to `beam/{ts}` and pushed:

```
git add -A && git commit -m "beam {ts}: <what landed>" && git push origin HEAD:beam/{ts}
```

An uncommitted file does not travel — untracked work is invisible to the recall, and the
owner's machine will never see this session's disk.

## Step 5 — sign off

When the lanes are done (or you are stopping for any reason), APPEND your completion note to
`beam/{ts}/CLOUD-DONE.md` and push it: what ran, what landed and where, what is still
missing, and anything the recall must not assume. That file is how the owner learns this
session FINISHED rather than merely started — the recall reads commits, and a commit cannot
say "I gave up".
"""


def merge_harness(existing_text):
    """Deep-merge the harness keys into a repo's settings. Returns (json_text, error).

    Every key already in the file survives, and an existing notrest entry WINS — the owner
    pinning a fork or a local marketplace outranks our default. Returns (None, reason) if
    the file cannot be parsed: overwriting settings we could not read would be a silent
    config edit, which is never worth a harness install.
    """
    base = {}
    if existing_text.strip():
        try:
            base = json.loads(existing_text)
        except ValueError as exc:
            return None, "does not parse (%s)" % str(exc).split("\n")[0]
        if not isinstance(base, dict):
            return None, "is not a JSON object"
    for key, add in HARNESS_SETTINGS.items():
        cur = base.get(key)
        if isinstance(cur, dict):
            merged = dict(cur)
            for k, v in add.items():
                merged.setdefault(k, v)
            base[key] = merged
        elif cur is None:
            base[key] = json.loads(json.dumps(add))
        else:
            return None, "key %r is a %s, not an object" % (key, type(cur).__name__)
    return json.dumps(base, indent=2, sort_keys=True) + "\n", ""


def die(msg, code=2):
    sys.stderr.write("beam: %s\n" % msg)
    raise SystemExit(code)


def git(root, *args, check=True):
    """Run one git command in `root`. Read-only verbs get --no-optional-locks."""
    top = ["git"]
    if args and args[0] in RO_VERBS:
        top.append("--no-optional-locks")
    top += ["-C", root]
    p = subprocess.run(top + list(args), capture_output=True, text=True)
    if check and p.returncode != 0:
        die("git %s failed: %s" % (" ".join(args[:2]), (p.stderr or p.stdout).strip()), 1)
    return p.returncode, (p.stdout or "").rstrip("\n"), (p.stderr or "").strip()


def git_index(root, index_path, *args):
    """Run one git command against a TEMPORARY index — never .git/index."""
    env = dict(os.environ, GIT_INDEX_FILE=index_path)
    p = subprocess.run(["git", "-C", root] + list(args),
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        die("git %s (temp index) failed: %s" % (args[0], (p.stderr or p.stdout).strip()), 1)
    return (p.stdout or "").rstrip("\n")


def repo_root(root):
    if not os.path.isdir(root):
        die("no such directory: %s" % root)
    rc, out, _ = git(root, "rev-parse", "--show-toplevel", check=False)
    if rc != 0:
        die("%s is not inside a git repository — the estate is the wire, and the wire is git"
            % root)
    return out


def ident(kind, value):
    if not value or not NAME_RE.match(value) or ".." in value or value.endswith(".lock"):
        die("bad %s %r — use [A-Za-z0-9][A-Za-z0-9._-]* (it becomes a directory AND a git "
            "ref component)" % (kind, value))
    return value


def beam_dir(root, ts, must_exist=False):
    d = os.path.join(root, "beam", ts)
    if must_exist and not os.path.isdir(d):
        die("no beam payload at %s — nothing was banked under ts %s"
            % (os.path.relpath(d, root), ts))
    return d


def lane_dir(root, ts, label, must_exist=False):
    d = os.path.join(beam_dir(root, ts, must_exist), "lane-%s" % label)
    if must_exist and not os.path.isdir(d):
        die("no lane %r under beam/%s" % (label, ts))
    return d


def lanes_of(root, ts):
    d = beam_dir(root, ts)
    if not os.path.isdir(d):
        return []
    return sorted(n[len("lane-"):] for n in os.listdir(d)
                  if n.startswith("lane-") and os.path.isdir(os.path.join(d, n)))


def read(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return default


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read_kv(path):
    out = {}
    for line in read(path).splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def loss_of(root, ts, label):
    """The lane's LOSS-ESTIMATE sentence, or "" if it was never force-stopped."""
    for ln in read(os.path.join(lane_dir(root, ts, label), "LOSS-ESTIMATE.md")).splitlines():
        if ln.startswith("LOSS-ESTIMATE:"):
            return ln.strip()
    return ""


def lane_state(root, ts, label):
    s = read(os.path.join(lane_dir(root, ts, label), "STATE")).strip()
    return s or "BANKED"


def file_list(path):
    """A newline list file → clean, de-duplicated, order-preserving paths."""
    seen, out = set(), []
    for raw in read(path).splitlines():
        p = raw.strip()
        if not p or p.startswith("#") or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def sha256(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return "-"


# ── bank ─────────────────────────────────────────────────────────────────────
def cmd_bank(a):
    root = repo_root(a.root)
    ts, label = ident("ts", a.ts), ident("lane", a.lane)
    for flag, path in (("--brief", a.brief), ("--progress", a.progress)):
        if not os.path.isfile(path):
            die("%s %s does not exist — the model writes the brief and the digest; a script "
                "cannot see a live lane" % (flag, path))
    d = lane_dir(root, ts, label)
    os.makedirs(d, exist_ok=True)
    brief, progress = read(a.brief).strip(), read(a.progress).strip()
    if not brief:
        die("--brief %s is empty — a lane with no brief cannot be resumed by anyone" % a.brief)
    files = file_list(a.files) if a.files else []
    if a.files and not os.path.isfile(a.files):
        die("--files %s does not exist" % a.files)

    write(os.path.join(d, "brief.md"), brief + "\n")
    write(os.path.join(d, "progress.md"), (progress or "(no digest banked)") + "\n")
    write(os.path.join(d, "files.txt"), "".join(p + "\n" for p in files))
    if files:
        block = "".join("- `%s`\n" % p for p in files).rstrip("\n")
    else:
        block = ("(none listed — the seat banked no file list. Infer scope from the brief "
                 "and touch nothing it does not name.)")
    # A force-stop is a fact about this lane's history, so the artifact is written once and
    # survives a later re-bank: you cannot un-stop a lane by banking it again.
    lp = os.path.join(d, "LOSS-ESTIMATE.md")
    if a.forced:
        loss = LOSS_LINE.format(when=a.stopped_at or ts)
        write(lp, "# %s — force-stopped\n\n%s\n\nThe seat stopped this lane to beam it. The "
                  "brief and the digest above are what survived; the stride between the last "
                  "durable artifact and the stop is not recoverable and was never claimed to "
                  "be.\n" % (label, loss))
    loss_line = loss_of(root, ts, label)
    forced_block = FORCED_BLOCK.format(loss=loss_line) if loss_line else ""
    write(os.path.join(d, "resume-prompt.md"),
          TEMPLATE.format(label=label, ts=ts, brief=brief, forced_block=forced_block,
                          progress=progress or "(no digest banked — the seat had nothing "
                                               "observable to bank; assume nothing landed)",
                          files_block=block, laws=LAWS.format(ts=ts, label=label)))
    # A re-bank refreshes the payload but never rewinds a state the lane already reached:
    # re-banking a SPAWNED lane is how you correct a brief, not how you un-spawn it.
    sp = os.path.join(d, "STATE")
    if not os.path.exists(sp):
        write(sp, "BANKED\n")
    print("BANKED lane %s → %s/" % (label, os.path.relpath(d, root)))
    for fn in ("brief.md", "progress.md", "files.txt", "resume-prompt.md"):
        print("  %s" % os.path.relpath(os.path.join(d, fn), root))
    print("  state: %s · files listed: %d" % (lane_state(root, ts, label), len(files)))
    if loss_line:
        print("  %s" % loss_line)
    print("next: beam.py manifest --ts %s   (then snapshot --push, then rail)" % ts)
    return 0


# ── manifest ─────────────────────────────────────────────────────────────────
def cmd_manifest(a):
    root = repo_root(a.root)
    ts = ident("ts", a.ts)
    beam_dir(root, ts, must_exist=True)
    print(write_manifest(root, ts))
    return 0


def write_checkpoint(root, ts):
    """The cloud session's whole instruction, as a file on the ref (not in a prompt)."""
    lanes = lanes_of(root, ts)
    block = "".join(
        "%d. lane `%s` — prompt: `beam/%s/lane-%s/resume-prompt.md` (state at beam time: %s)\n"
        % (i, label, ts, label, lane_state(root, ts, label))
        for i, label in enumerate(lanes, 1)) or "(no lanes banked — nothing to run)\n"
    text = CHECKPOINT.format(ts=ts, lane_block=block.rstrip("\n"),
                             laws=LAWS.format(ts=ts, label="<label>"))
    write(os.path.join(beam_dir(root, ts), "CHECKPOINT.md"), text)


def write_manifest(root, ts):
    """Regenerate MANIFEST.md (and CHECKPOINT.md) from the directory.

    Deterministic: same directory → same bytes. Nothing here reads a clock, so a
    regeneration is a no-op and `mark` can regenerate freely."""
    write_checkpoint(root, ts)
    d = beam_dir(root, ts)
    lanes = lanes_of(root, ts)
    snap = read_kv(os.path.join(d, "SNAPSHOT.txt"))
    ref = snap.get("ref", "refs/heads/beam/%s" % ts)
    L = ["# BEAM MANIFEST — %s" % ts, "",
         "Payload root: `beam/%s/` · cloud instruction: `beam/%s/CHECKPOINT.md`" % (ts, ts),
         "Snapshot ref: `%s`" % ref]
    if snap.get("commit"):
        L.append("Snapshot commit: `%s` (base `%s`) · pushed: %s"
                 % (snap["commit"][:12], snap.get("base", "?")[:12],
                    snap.get("pushed", "no")))
    else:
        L.append("Snapshot commit: NONE YET — run `beam.py snapshot --ts %s --push`, or the "
                 "payload exists only on this disk" % ts)
    L += ["", "| lane | state | payload | brief | digest | files |",
          "|------|-------|---------|-------|--------|-------|"]
    for label in lanes:
        ld = lane_dir(root, ts, label)
        L.append("| %s%s | %s | `beam/%s/lane-%s/` | %d ln | %d ln | %d |"
                 % (label, " ⚠force-stopped" if loss_of(root, ts, label) else "",
                    lane_state(root, ts, label), ts, label,
                    len(read(os.path.join(ld, "brief.md")).splitlines()),
                    len(read(os.path.join(ld, "progress.md")).splitlines()),
                    len(file_list(os.path.join(ld, "files.txt")))))
    if not lanes:
        L.append("| (none) | - | - | - | - | - |")
    L += ["",
          "States: `BANKED` payload written · `SPAWNED:<id>` a remote lane is carrying it · "
          "`FORCED:<id>` same, but the local lane was stopped mid-flight to send it · "
          "`RECALLED` its work is folded home.",
          ""]
    losses = [(label, loss_of(root, ts, label)) for label in lanes]
    losses = [(label, ln) for label, ln in losses if ln]
    if losses:
        L += ["## Loss estimates — lanes stopped mid-flight", ""]
        for label, ln in losses:
            L.append("- `%s` — %s" % (label, ln))
        L += ["", "A forced beam trades a known, bounded loss for an unbounded gain in "
                  "wall-clock. It is still a loss: when the deliverable comes home, compare "
                  "it against these lanes' briefs rather than assuming continuity.", ""]
    handles = [(label, read_kv(os.path.join(lane_dir(root, ts, label), "HANDLES")))
               for label in lanes]
    handles = [(label, h) for label, h in handles if h]
    if handles:
        L += ["## Durable handles", ""]
        for label, h in handles:
            for k in sorted(h):
                L.append("- `%s` %s: %s" % (label, k, h[k]))
        L.append("")
    L += ["## Recall checklist",
          "",
          "- [ ] `beam.py down --ts %s --fetch` — per-lane DELIVERED / MISSING (exit 3 if "
          "anything is MISSING)" % ts,
          "- [ ] fold: run the `git show` lines `down` prints. beam never folds for you — "
          "an overwrite of the live tree is the owner's act.",
          "- [ ] receipts: any remote lane the SubagentStop hook did not receipt gets a "
          "`spend.py log --lane beam-remote` line, graded by what is observable.",
          "- [ ] `beam.py mark --ts %s --lane <label> --state RECALLED` per folded lane" % ts,
          "- [ ] session-level recall, when you need the cloud session ITSELF and not just "
          "its commits: `claude --teleport <session-id>` (or `/tp <session-id>`). The ref "
          "carries the work; teleport carries the conversation.",
          "- [ ] COORD line: what landed, what is still MISSING, and where the ref is.",
          ""]
    text = "\n".join(L)
    write(os.path.join(d, "MANIFEST.md"), text)
    return "MANIFEST → beam/%s/MANIFEST.md (%d lane(s))" % (ts, len(lanes))


# ── snapshot ─────────────────────────────────────────────────────────────────
def dirty_tracked(root):
    """Tracked paths that differ from HEAD (staged or not). Untracked files are NOT
    swept in: the payload is deliberate, and a snapshot is not a junk drawer."""
    _rc, out, _ = git(root, "diff", "--name-only", "HEAD", "--")
    return [p for p in out.splitlines() if p.strip()]


def carry_harness(root, tindex):
    """Put a harness-enabling .claude/settings.json into the PUBLISHED tree only.

    The blob is hashed straight into the object database and stapled to the temporary
    index with update-index --cacheinfo, so the working copy is never opened for writing
    and an ignored settings file still travels. Returns a one-line report.
    """
    live = os.path.join(root, SETTINGS_PATH)
    text, err = merge_harness(read(live))
    if text is None:
        return ("SKIPPED — %s %s; the cloud clone will land WITHOUT the harness. Fix the "
                "file or install the plugin in the cloud session by hand." % (SETTINGS_PATH, err))
    p = subprocess.run(["git", "-C", root, "hash-object", "-w", "--stdin"],
                       input=text, capture_output=True, text=True)
    if p.returncode != 0:
        die("hash-object failed: %s" % (p.stderr or p.stdout).strip(), 1)
    blob = p.stdout.strip()
    git_index(root, tindex, "update-index", "--add",
              "--cacheinfo", "100644,%s,%s" % (blob, SETTINGS_PATH))
    return ("%s on the ref enables notrest@notrest (%s) — worktree copy untouched"
            % (SETTINGS_PATH, "merged into the existing file" if os.path.isfile(live)
               else "created; the repo had none"))


def cmd_snapshot(a):
    root = repo_root(a.root)
    ts = ident("ts", a.ts)
    d = beam_dir(root, ts, must_exist=True)
    if not lanes_of(root, ts):
        die("no lanes banked under beam/%s — bank at least one lane before snapshotting" % ts)
    ref = "refs/heads/beam/%s" % ts
    payload = os.path.relpath(d, root)

    _rc, head, _ = git(root, "rev-parse", "HEAD")
    idx = os.path.join(root, ".git", "index")
    before = (head, sha256(idx), dirty_tracked(root))

    with tempfile.TemporaryDirectory(prefix="beam-index-") as tmp:
        tindex = os.path.join(tmp, "index")
        git_index(root, tindex, "read-tree", "HEAD")
        if before[2]:
            git_index(root, tindex, "add", "--", *before[2])
        # -f only for the payload: a consumer repo that gitignores beam/ must not be able
        # to silently publish an empty checkpoint.
        git_index(root, tindex, "add", "-f", "--", payload)
        carriage = carry_harness(root, tindex)
        tree = git_index(root, tindex, "write-tree").strip()

    rc, parent, _ = git(root, "rev-parse", "--verify", "-q", ref, check=False)
    parent = parent.strip() if rc == 0 and parent.strip() else head
    msg = ("beam %s — snapshot of the live tree (%d dirty tracked file(s), %d lane(s))\n\n"
           "Built with plumbing against a temporary index: HEAD, .git/index and the "
           "worktree were not touched.\n" % (ts, len(before[2]), len(lanes_of(root, ts))))
    p = subprocess.run(["git", "-C", root, "commit-tree", tree, "-p", parent, "-m", msg],
                       capture_output=True, text=True)
    if p.returncode != 0:
        die("commit-tree failed: %s" % (p.stderr or p.stdout).strip(), 1)
    commit = p.stdout.strip()
    git(root, "update-ref", ref, commit)

    pushed = "no"
    if a.push:
        rc, out, err = git(root, "push", a.remote, "%s:%s" % (ref, ref), check=False)
        if rc != 0:
            sys.stderr.write((err or out) + "\n")
            die("push to %s failed. If a remote lane has already committed on %s, recall "
                "first (`beam.py down --ts %s --fetch`) — beam never force-pushes over a "
                "lane's work." % (a.remote, ref, ts), 1)
        pushed = a.remote

    write(os.path.join(d, "SNAPSHOT.txt"),
          "ref=%s\ncommit=%s\nbase=%s\ntree=%s\nparent=%s\npushed=%s\ndirty=%d\n"
          % (ref, commit, head, tree, parent, pushed, len(before[2])))
    after = (git(root, "rev-parse", "HEAD")[1], sha256(idx), dirty_tracked(root))

    print("SNAPSHOT %s" % ref)
    print("  commit %s (parent %s)" % (commit[:12], parent[:12]))
    print("  carries: %d dirty tracked file(s) + %s/" % (len(before[2]), payload))
    print("  harness carriage: %s" % carriage)
    print("  pushed: %s" % pushed)
    same = "UNCHANGED" if before == after else "CHANGED — STOP, INVESTIGATE"
    print("  NO-TOUCH PROOF: HEAD %s→%s · .git/index sha256 %s→%s · dirty set %d→%d · %s"
          % (before[0][:12], after[0][:12], before[1], after[1],
             len(before[2]), len(after[2]), same))
    if before != after:
        return 1
    print("next: beam.py rail --ts %s --lane <label>   (then mark --state SPAWNED:<id>)" % ts)
    return 0


# ── mark ─────────────────────────────────────────────────────────────────────
def cmd_mark(a):
    root = repo_root(a.root)
    ts, label = ident("ts", a.ts), ident("lane", a.lane)
    d = lane_dir(root, ts, label, must_exist=True)
    if not STATE_RE.match(a.state.strip()):
        die("bad --state %r — BANKED | SPAWNED:<remote-id> | RECALLED" % a.state)
    write(os.path.join(d, "STATE"), a.state.strip() + "\n")
    # Durable handles: what still points at the remote session after this session is gone.
    # Kept beside the payload, not in a transcript — that is the entire lesson of beam.
    hp = os.path.join(d, "HANDLES")
    handles = read_kv(hp)
    for key, val in (("session-url", a.session_url), ("meta", a.meta)):
        if val:
            handles[key] = val.strip()
    if handles:
        write(hp, "".join("%s=%s\n" % (k, handles[k]) for k in sorted(handles)))
    print("MARK %s → %s%s" % (label, a.state.strip(),
                              "  (handles: %s)" % ", ".join(sorted(handles)) if handles else ""))
    print(write_manifest(root, ts))
    return 0


# ── rail (THE BOUNDARY) ──────────────────────────────────────────────────────
# RAIL v1 — this subcommand is the ONLY place the rail lives. Everything else in this file
# is storage and git plumbing that stays true no matter how a remote session is started.
# When the rail's semantics change, this function changes and nothing else does.
#
# The order below is a verified finding, not a preference. The PRIMARY rail is a cloud
# SESSION (`claude --cloud`), which detaches for real — it survives the laptop closing.
# The Agent tool's isolation:"remote" is server-gated, and when the gate is shut it
# DEGRADES SILENTLY to a local agent that dies with this machine: it looks beamed and is
# not. So it is listed last, behind an assertion the seat has to actually make.
#
# beam.py NEVER spawns anything itself. It prints; the seat — which holds the tools and the
# owner's consent — decides whether to run any of it.
def cmd_rail(a):
    root = repo_root(a.root)
    ts = ident("ts", a.ts)
    lanes = lanes_of(root, ts)
    if not lanes:
        die("no lanes banked under beam/%s" % ts)
    label = ident("lane", a.lane) if a.lane else None
    if label and label not in lanes:
        die("no lane %r under beam/%s" % (label, ts))
    snap = read_kv(os.path.join(beam_dir(root, ts, must_exist=True), "SNAPSHOT.txt"))
    ref = snap.get("ref", "refs/heads/beam/%s" % ts)
    branch = ref.split("refs/heads/")[-1]
    one_line = ("git fetch origin %s && git checkout %s, then read beam/%s/CHECKPOINT.md "
                "and execute it" % (branch, branch, ts))

    print("RAIL v1 — the only place the rail lives. beam.py executes nothing below;")
    print("the seat makes the call. Ordered by what actually detaches.")
    print("")
    if snap.get("pushed", "no") == "no":
        print("!! NOT PUSHED — a cloud session clones the REMOTE, not this disk. Run first:")
        print("   beam.py snapshot --root . --ts %s --push --remote origin" % ts)
        print("")
    print("── (a) PRIMARY — cloud session (detaches for real; survives the laptop closing) ─")
    print("   claude --cloud \"%s\"" % one_line)
    print("")
    print("   Why the prompt checks out the ref itself: a cloud session clones the cwd")
    print("   repo's CURRENT branch, and this machine never switches branches — so nothing")
    print("   but that checkout puts the session on the beam ref. Why the prompt is one")
    print("   line: a prompt is context-bounded and a repository is not — CHECKPOINT.md")
    print("   carries the lanes, the order and the laws. Record the handle when you get it:")
    print("     beam.py mark --ts %s --lane <label> --state SPAWNED:<session-id> "
          "--session-url <url>" % ts)
    print("")
    print("── (b) SCHEDULED KICK — one-off routine / RemoteTrigger, to start later ────────")
    print("   Same one-line prompt as (a). Two things bite here:")
    print("   · a routine clones the DEFAULT branch, so the checkout-first step is not")
    print("     optional — it is the only reason the session finds the work;")
    print("   · the routine's fire-text arrives WRAPPED AS UNTRUSTED, so the saved prompt")
    print("     must say plainly that it is the owner's own beam instruction and name this")
    print("     exact ref — otherwise the session receiving it is right to refuse it.")
    print("   The owner creates the routine. The harness never self-schedules a beam.")
    print("")
    print("── (c) DESKTOP — Continue in → Claude Code on the Web ──────────────────────────")
    print("   Hand-off from the desktop app; it wants a clean tree, so snapshot first and")
    print("   let the ref carry the dirty state. Then open branch `%s` there." % branch)
    print("")
    print("── (d) GATED FAST PATH — Agent(isolation:\"remote\") ────────────────────────────")
    print("   Server-gated. When the gate is shut it DEGRADES SILENTLY to a local agent that")
    print("   dies with this session — it looks beamed and is not. Make this call ONLY if")
    print("   you then assert the result shows status \"remote_launched\"; anything else")
    print("   means it never left, and that lane must go out via (a).")
    for lb in ([label] if label else lanes):
        prompt = read(os.path.join(lane_dir(root, ts, lb), "resume-prompt.md"))
        if not prompt.strip():
            die("no resume-prompt.md for lane %s — run `beam.py bank` first" % lb)
        print("")
        print(json.dumps({"subagent_type": "general-purpose", "model": "opus",
                          "isolation": "remote", "run_in_background": True,
                          "description": "beam lane %s" % lb,
                          "prompt": prompt}, indent=2))
    print("")
    print("   model \"opus\" is explicit and never optional (offload policy 2026-07-15);")
    print("   never subagent_type \"fork\" — a fork inherits the seat's model.")
    print("")
    print("Transport laws: untracked files never travel — the payload is COMMITTED on the")
    print("ref (snapshot did that). The checkpoint lives in the repo; the prompt stays one")
    print("line. Any agent anywhere that can read git can be the rail — which is why the")
    print("estate, and not a session, is the wire.")
    return 0


# ── down ─────────────────────────────────────────────────────────────────────
def cmd_down(a):
    root = repo_root(a.root)
    ts = ident("ts", a.ts)
    d = beam_dir(root, ts, must_exist=True)
    lanes = lanes_of(root, ts)
    if not lanes:
        die("no lanes under beam/%s" % ts)
    home = "refs/heads/beam/%s" % ts
    recall = "refs/beam/recall/%s" % ts
    ref = None
    if a.fetch:
        rc, out, err = git(root, "fetch", a.remote, "+%s:%s" % (home, recall), check=False)
        if rc != 0:
            sys.stderr.write((err or out) + "\n")
            die("fetch of %s from %s failed — is the ref pushed?" % (home, a.remote), 1)
        ref = recall
    else:
        for cand in (home, recall):
            if git(root, "rev-parse", "--verify", "-q", cand, check=False)[0] == 0:
                ref = cand
                break
        if ref is None:
            die("neither %s nor %s exists locally — pass --fetch to pull it from the remote"
                % (home, recall))
    _rc, tip, _ = git(root, "rev-parse", ref)

    snap = read_kv(os.path.join(d, "SNAPSHOT.txt"))
    base = snap.get("commit")
    how = "snapshot commit"
    if not base:
        rc, mb, _ = git(root, "merge-base", ref, "HEAD", check=False)
        base, how = (mb.strip(), "merge-base with HEAD") if rc == 0 and mb.strip() else (None, "")
    if not base:
        die("no base commit to diff against (no SNAPSHOT.txt, no merge-base) — cannot say "
            "what the ref gained without inventing it", 1)

    _rc, out, _ = git(root, "diff", "--name-only", base, ref)
    changed = [p for p in out.splitlines() if p.strip()]

    print("BEAM DOWN — %s" % ts)
    print("  ref  : %s @ %s%s" % (ref, tip[:12], "  (fetched from %s)" % a.remote if a.fetch else ""))
    print("  base : %s @ %s (%s)" % (how, base[:12], "unchanged" if base == tip else "moved"))
    print("  the ref gained %d path(s) since the beam" % len(changed))
    done = "beam/%s/CLOUD-DONE.md" % ts
    if git(root, "cat-file", "-e", "%s:%s" % (ref, done), check=False)[0] == 0:
        note = git(root, "show", "%s:%s" % (ref, done))[1].strip().splitlines()
        print("  CLOUD-DONE.md — the cloud session signed off:")
        for ln in note[:6]:
            print("      %s" % ln)
        if len(note) > 6:
            print("      … (%d more lines — git show %s:%s)" % (len(note) - 6, ref, done))
    else:
        print("  no CLOUD-DONE.md on the ref — the cloud session has NOT signed off. It may")
        print("  still be running, or it may have died; the ref cannot tell you which.")
    print("")

    claimed, delivered, missing = {done}, [], []
    for label in lanes:
        ld = lane_dir(root, ts, label)
        pay = "beam/%s/lane-%s/" % (ts, label)
        listed = set(file_list(os.path.join(ld, "files.txt")))
        mine = [p for p in changed if p.startswith(pay) or p in listed]
        claimed.update(mine)
        state = lane_state(root, ts, label)
        if mine:
            delivered.append(label)
            print("lane %s  [%s]  DELIVERED (%d)" % (label, state, len(mine)))
            for p in mine:
                print("    %s" % p)
            print("  fold (you run these — beam never writes over your tree):")
            for p in mine:
                q = shlex.quote(p)
                print("    mkdir -p %s && git show %s:%s > %s"
                      % (shlex.quote(os.path.dirname(p) or "."), ref, q, q))
        else:
            missing.append(label)
            print("lane %s  [%s]  MISSING" % (label, state))
            print("    nothing under %s changed on the ref, and none of its %d listed file(s) "
                  "moved." % (pay, len(listed)))
            print("    A lane that spawned and delivered nothing is either still running or "
                  "it died —\n    the ref cannot tell you which. Check the remote lane before "
                  "you conclude either.")
        # A forced lane's deliverable is a RE-DERIVATION, not a continuation. Folding it as
        # if the original lane had simply carried on is how a lost stride becomes invisible.
        if state.startswith("FORCED") or loss_of(root, ts, label):
            print("  ⚠ FORCED BEAM — %s" % (loss_of(root, ts, label) or
                                            "the local lane was stopped mid-flight"))
            print("    Read this diff, do not skim it: the far side re-derived the unbanked stride")
            print("    and may well have solved it differently than the lane that was stopped.")
        print("")

    orphans = [p for p in changed if p not in claimed]
    if orphans:
        print("UNATTRIBUTED (%d) — on the ref, claimed by no lane's payload or file list:" % len(orphans))
        for p in orphans:
            print("    %s   →  git show %s:%s > %s" % (p, ref, shlex.quote(p), shlex.quote(p)))
        print("")

    for label in lanes:
        h = read_kv(os.path.join(lane_dir(root, ts, label), "HANDLES"))
        if h:
            print("handles %s: %s" % (label, " · ".join("%s=%s" % (k, h[k]) for k in sorted(h))))
    print("session-level recall — when you need the cloud session ITSELF and not just its")
    print("commits: `claude --teleport <session-id>` (or `/tp <session-id>`). The ref carries")
    print("the work; teleport carries the conversation.")
    print("")
    print("VERDICT: %d DELIVERED · %d MISSING" % (len(delivered), len(missing)))
    if missing:
        print("  → exit 3. Nothing was folded and nothing was marked: recall is not "
              "complete while a lane is still out.")
        return 3
    print("  → fold the commands above, log any un-receipted lane with spend.py, then "
          "`beam.py mark ... --state RECALLED` per lane.")
    return 0


# ── status ───────────────────────────────────────────────────────────────────
def cmd_status(a):
    root = repo_root(a.root)
    base = os.path.join(root, "beam")
    if not os.path.isdir(base):
        print("no beam/ payloads under %s — nothing has been beamed from this tree" % root)
        return 0
    rows = sorted(n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n)))
    if not rows:
        print("beam/ exists but holds no checkpoints")
        return 0
    for ts in rows:
        lanes = lanes_of(root, ts)
        counts = {"BANKED": 0, "SPAWNED": 0, "FORCED": 0, "RECALLED": 0}
        forced = 0
        for label in lanes:
            head = lane_state(root, ts, label).split(":")[0]
            counts[head] = counts.get(head, 0) + 1
            forced += 1 if loss_of(root, ts, label) else 0
        snap = read_kv(os.path.join(base, ts, "SNAPSHOT.txt"))
        print("%-24s lanes=%-3d BANKED=%d SPAWNED=%d FORCED=%d RECALLED=%d  ref=%s pushed=%s%s"
              % (ts, len(lanes), counts.get("BANKED", 0), counts.get("SPAWNED", 0),
                 counts.get("FORCED", 0), counts.get("RECALLED", 0),
                 snap.get("commit", "-")[:12] or "-", snap.get("pushed", "no"),
                 "  ⚠%d stopped mid-flight" % forced if forced else ""))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="beam.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *flags):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        if "ts" in flags:
            p.add_argument("--ts", required=True, metavar="ID")
        if "lane" in flags:
            p.add_argument("--lane", required=True, metavar="LABEL")
        p.set_defaults(f=fn)
        return p

    b = add("bank", cmd_bank, "ts", "lane")
    b.add_argument("--brief", required=True, metavar="FILE")
    b.add_argument("--progress", required=True, metavar="FILE")
    b.add_argument("--files", metavar="FILE", help="newline list of paths this lane holds")
    b.add_argument("--forced", action="store_true",
                   help="this lane was STOPPED mid-flight to beam it: writes the pinned "
                        "LOSS-ESTIMATE into the payload, the resume prompt and the manifest")
    b.add_argument("--stopped-at", dest="stopped_at", metavar="WHEN",
                   help="when it was stopped (defaults to the beam ts)")
    add("manifest", cmd_manifest, "ts")
    s = add("snapshot", cmd_snapshot, "ts")
    s.add_argument("--push", action="store_true")
    s.add_argument("--remote", default="origin")
    m = add("mark", cmd_mark, "ts", "lane")
    m.add_argument("--state", required=True, metavar="BANKED|SPAWNED:<id>|RECALLED")
    m.add_argument("--session-url", dest="session_url", metavar="URL",
                   help="durable handle: the cloud session's URL")
    m.add_argument("--meta", metavar="PATH",
                   help="durable handle: the remote-agent meta.json path")
    r = add("rail", cmd_rail, "ts")
    r.add_argument("--lane", metavar="LABEL", default=None,
                   help="one lane's payload; omit for every lane under the ts")
    dn = add("down", cmd_down, "ts")
    dn.add_argument("--fetch", action="store_true")
    dn.add_argument("--remote", default="origin")
    add("status", cmd_status)

    a = ap.parse_args()
    raise SystemExit(a.f(a))


if __name__ == "__main__":
    main()
