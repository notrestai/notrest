#!/usr/bin/env python3
"""ship.py — the notrest release ritual, compiled from 10 real ships.

Runtime constraints (enforced by construction, not by convention):
  - python3 stdlib only; ZERO model calls at runtime.
  - every failure exits with its own code and prints a typed reason (10-21; 30 = parity).
  - irreversible steps (--push, --install) are explicit flags, never defaults.
  - the judgment gate (--gates-passed) stays human: this script never rules on quality.
  - every write is atomic (tmp + os.replace) and rolled back on any later abort, so a failed
    ship leaves a clean tree.
"""

import argparse
import datetime
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

TRAILER = "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
TOMBSTONE_SOURCE = "./plugins/oracle-suite-tombstone"
TOMBSTONE_PIN = "9.0.0"          # the migration stub is pinned forever; any drift aborts
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Spelled counts appear as words in prose surfaces; the table the ships used is 20-39.
_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_TENS = {20: "twenty", 30: "thirty"}


def num_to_word(n):
    if n in _TENS:
        return _TENS[n]
    t, o = divmod(n, 10)
    if t * 10 in _TENS and 1 <= o <= 9:
        return _TENS[t * 10] + "-" + _ONES[o]
    return None


def word_to_num(w):
    w = (w or "").lower().replace(" ", "-")
    for n in range(20, 40):
        if num_to_word(n) == w:
            return n
    return None


# REWRITER: strict. The trailing (?![-\w]) keeps ordinals out — "twenty-sixth" must not be
# rewritten into "twenty-six-sixth".
SPELL_RE = re.compile(
    r"\b(twenty|thirty)(?:[-\s](one|two|three|four|five|six|seven|eight|nine))?\b(?![-\w])"
    r"(?=[^.\n]{0,80}?skill)",
    re.IGNORECASE,
)
# CHECKER: deliberately WIDER than the rewriter. Anything shaped like a spelled count sitting
# in a counted context must equal the target word, including tokens the rewriter refuses to
# touch — otherwise surfaces disagree and nothing notices.
COUNT_SCAN_RE = re.compile(
    r"\b(twenty|thirty)(?:[-\s]\w+)?\b(?=[^.\n]{0,80}?skill)", re.IGNORECASE)
# Numeral surfaces: the repo-root README.md and CLAUDE.md carry "(N skills".
NUM_RE = re.compile(r"\b(\d{1,3}) skills?\b")

FLOW_FOOT_RE = re.compile(r"Manifest: (?:notrest|oracle-suite) v\d+\.\d+\.\d+")
# Pre-rename trees stamp a different vocabulary: "N-skill suite" / "Manifest: oracle-suite"
# (verified at 5c422ed, f115695, 4c78590). The header noun comes from the path profile. The
# footer pattern accepts either name on purpose: the rename ship must re-stamp a page whose
# footer still carries the old one, and the replacement name always comes from the profile.


def flow_head_re(P):
    return re.compile(r"v\d+\.\d+\.\d+ · \d+-skill " + P["flow_word"])


# Rollback ledger: armed for real ships, never for a replay scratch (whose HEAD is the
# pre-ship commit — a checkout there would destroy the payload the replay just seeded).
ROLLBACK = {"repo": None, "files": []}


def die(code, kind, msg):
    print("FAIL[%d] %s: %s" % (code, kind, msg), file=sys.stderr)
    repo, files = ROLLBACK["repo"], ROLLBACK["files"]
    if repo and files:
        p = subprocess.run(["git", "checkout", "--"] + files, cwd=repo,
                           capture_output=True, text=True)
        print("rollback: %d file(s) restored%s"
              % (len(files), "" if p.returncode == 0 else " — FAILED: " + p.stderr.strip()),
              file=sys.stderr)
    sys.exit(code)


def run(cmd, cwd=None, check=False, code=None, kind=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        die(code or 1, kind or "SUBPROCESS",
            "%s -> exit %d\n%s%s" % (" ".join(cmd), p.returncode, p.stdout, p.stderr))
    return p


def paths(legacy):
    """Pre-rename ships lived under plugins/oracle-suite/; --legacy-paths maps them."""
    slug = "oracle-suite" if legacy else "notrest"
    return {
        "name": slug,
        "flow_word": "suite" if legacy else "harness",
        "plugin_json": "plugins/%s/.claude-plugin/plugin.json" % slug,
        "market_json": ".claude-plugin/marketplace.json",
        "entry_source": "./plugins/%s" % slug,
        "skills_dir": "plugins/%s/skills" % slug,
        "readme": "plugins/%s/README.md" % slug,
        "tutorial": "docs/TUTORIAL.md",
        "flow": "docs/oracle-skill-flow.html",
        "changelog": "CHANGELOG.md",
        "coord": "COORD.md",
        "root_readme": "README.md",
        "root_claude": "CLAUDE.md",
        "spend": "plugins/%s/skills/spend/scripts/spend.py" % slug,
    }


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    """Atomic: a crash mid-ritual can never leave a half-written manifest."""
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".ship-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    repo = ROLLBACK["repo"]
    if repo:
        rel = os.path.relpath(path, repo)
        if not rel.startswith("..") and rel not in ROLLBACK["files"]:
            ROLLBACK["files"].append(rel)


# --------------------------------------------------------------------- manifest writing

def brace_span(text, i):
    """i indexes a '{'; return the index of its matching '}' (string- and escape-aware)."""
    depth, in_str, esc = 0, False, False
    for j in range(i, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError("unbalanced braces")


def entry_spans(text, array_key="plugins"):
    i = text.index('"%s"' % array_key)
    i = text.index("[", i)
    spans, j = [], i + 1
    while j < len(text):
        c = text[j]
        if c == "{":
            end = brace_span(text, j)
            spans.append((j, end))
            j = end + 1
        elif c == "]":
            break
        else:
            j += 1
    return spans


def set_key_in_span(text, span, key, value):
    """Replace one string scalar inside a span, leaving every other byte untouched."""
    s, e = span
    m = re.compile(r'("%s"\s*:\s*")((?:[^"\\]|\\.)*)(")' % re.escape(key)).search(text, s, e)
    if not m:
        return None
    esc = json.dumps(value, ensure_ascii=False)[1:-1]
    return text[:m.start()] + m.group(1) + esc + m.group(3) + text[m.end():]


def roundtrip_lossless(orig):
    try:
        return json.dumps(json.loads(orig), indent=2, ensure_ascii=False) + "\n" == orig
    except Exception:
        return False


def write_manifest(path, doc, orig, edits):
    """Write the mutated manifest.

    Preferred path (taken by every modern manifest, verified at runtime): dump the parsed
    document. Entries were selected by NAME, so a reordered key list can no longer make the
    writer walk past the live entry and bump the tombstone. Fallback for files whose own
    formatting is not json.dumps-shaped (true of every pre-rename manifest): edit only the
    located scalars in place, so a replay never reformats history into a false diff.
    """
    if roundtrip_lossless(orig):
        write(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        return "json"
    text = orig
    for where, key, value in edits:
        if where == "root":
            o = text.index("{")
            span = (o, brace_span(text, o))
        elif where == "metadata":
            m = re.search(r'"metadata"\s*:\s*\{', text)
            if not m:
                die(12, "MANIFEST", "no metadata block in %s" % path)
            o = text.index("{", m.end() - 1)
            span = (o, brace_span(text, o))
        else:
            span = None
            for s in entry_spans(text):
                if re.search(r'"name"\s*:\s*"%s"' % re.escape(where), text[s[0]:s[1]]):
                    span = s
                    break
            if span is None:
                die(12, "MANIFEST", "no entry named %r in %s" % (where, path))
        out = set_key_in_span(text, span, key, value)
        if out is None:
            die(12, "MANIFEST", "key %r not found in %s of %s" % (key, where, path))
        text = out
    write(path, text)
    return "scoped"


def json_or_die(path, code=12):
    try:
        return json.loads(read(path))
    except Exception as exc:  # an unreadable manifest is a hard stop, never a warning
        die(code, "MANIFEST", "%s unparseable: %s" % (path, exc))


def market_entries(doc, P):
    """Entries are found by NAME/SOURCE identity, never by position or key order."""
    live = tomb = None
    for e in doc.get("plugins", []):
        if e.get("source") == TOMBSTONE_SOURCE or "tombstone" in str(e.get("source", "")):
            tomb = e
        elif e.get("name") == P["name"] or e.get("source") == P["entry_source"]:
            live = e
    return live, tomb


def count_skills(repo, P):
    d = os.path.join(repo, P["skills_dir"])
    if not os.path.isdir(d):
        die(13, "COUNT", "skills dir absent: %s" % P["skills_dir"])
    return len([x for x in os.listdir(d)
                if os.path.isdir(os.path.join(d, x)) and not x.startswith(".")])


def respell(text, word):
    # Returns changes, not matches: a re-stamp of the same word is not a rewrite, and the
    # fixture's non-vacuity assert reads this number.
    target = word_to_num(word)
    changed = sum(1 for m in SPELL_RE.finditer(text) if word_to_num(m.group(0)) != target)

    def sub(m):
        return word.capitalize() if m.group(0)[0].isupper() else word
    return SPELL_RE.sub(sub, text), changed


def renumber(text, n):
    changed = sum(1 for m in NUM_RE.finditer(text) if int(m.group(1)) != n)
    return NUM_RE.sub(lambda _m: "%d skills" % n, text), changed


def spelled_counts(text):
    return [word_to_num(m.group(0)) for m in SPELL_RE.finditer(text or "")]


def quote_line(text, pos):
    s = text.rfind("\n", 0, pos) + 1
    e = text.find("\n", pos)
    return text[s:e if e != -1 else len(text)].strip()[:160]


# --------------------------------------------------------------------------- ship

def do_ship(a):
    repo = os.path.abspath(a.repo)
    P = paths(a.legacy_paths)
    if not VERSION_RE.match(a.version):
        die(2, "ARGS", "--version must be X.Y.Z, got %r" % a.version)

    # 1. the judgment gate stays human.
    if not a.gates_passed:
        die(10, "GATES", "refusing to ship without --gates-passed "
                         "(the seat's quality ruling is not automatable)")

    pj_path = os.path.join(repo, P["plugin_json"])
    mj_path = os.path.join(repo, P["market_json"])
    for p in (pj_path, mj_path):
        if not os.path.exists(p):
            die(12, "MANIFEST", "missing manifest: %s" % os.path.relpath(p, repo))

    pj_orig, mj_orig = read(pj_path), read(mj_path)
    pj, mj = json_or_die(pj_path), json_or_die(mj_path)
    live, tomb = market_entries(mj, P)
    if live is None:
        die(12, "MANIFEST", "no marketplace entry named %r" % P["name"])
    tomb_before = json.loads(json.dumps(tomb)) if tomb is not None else None

    # 2a. tombstone guard — pinned 9.0.0 forever; a tampered pin aborts before any write.
    if tomb is not None and tomb.get("version") != TOMBSTONE_PIN:
        die(11, "TOMBSTONE", "oracle-suite tombstone is %r, must stay pinned at %s "
                             "(migration stub for existing installs)"
            % (tomb.get("version"), TOMBSTONE_PIN))

    # 2b. the two old versions must have matched before the bump.
    old = {"plugin.json": pj.get("version"),
           "marketplace.metadata": mj.get("metadata", {}).get("version"),
           "marketplace.entry": live.get("version")}
    if len(set(old.values())) != 1:
        die(12, "VERSION-SKEW", "pre-bump versions disagree: %s" % old)
    old_version = pj.get("version")

    # 5. changelog input is validated before anything is written.
    section = None
    if a.changelog_file:
        if not os.path.exists(a.changelog_file):
            die(15, "CHANGELOG", "no such file: %s" % a.changelog_file)
        section = read(a.changelog_file)
        want_date = a.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        first = section.split("\n", 1)[0].strip()
        expect = "## %s — %s" % (a.version, want_date)
        if first != expect:
            die(15, "CHANGELOG", "first line must be %r, got %r" % (expect, first))

    # 6. coord input is validated before anything is written.
    for line in (a.coord_line or []):
        if not line.startswith("- ["):
            die(16, "COORD", "coord line must start '- [', got %r" % line[:40])

    n = count_skills(repo, P)
    word = num_to_word(n)
    if word is None:
        die(13, "COUNT", "%d skills is outside the spelled table (20-39)" % n)
    print("gates: passed (human ruling accepted) · %s -> %s · %d skills"
          % (old_version, a.version, n))

    # --- writes (rollback armed from here for real ships) -------------------
    if not getattr(a, "replay_mode", False):
        ROLLBACK["repo"], ROLLBACK["files"] = repo, []

    # 2c + 3a. manifests: version bump and the spelled count inside each description.
    pj["version"] = a.version
    mj.setdefault("metadata", {})["version"] = a.version
    live["version"] = a.version
    edits_pj = [("root", "version", a.version)]
    edits_mj = [("metadata", "version", a.version), (P["name"], "version", a.version)]
    rewrites = 0
    if isinstance(pj.get("description"), str):
        pj["description"], k = respell(pj["description"], word)
        rewrites += k
        edits_pj.append(("root", "description", pj["description"]))
    if isinstance(live.get("description"), str):
        live["description"], k = respell(live["description"], word)
        rewrites += k
        edits_mj.append((P["name"], "description", live["description"]))
    how_pj = write_manifest(pj_path, pj, pj_orig, edits_pj)
    how_mj = write_manifest(mj_path, mj, mj_orig, edits_mj)

    # 2d. post-write re-assert, re-read from disk, before anything is staged. This is what
    # makes "and the new ones match coming out" implemented rather than merely claimed.
    pj2, mj2 = json_or_die(pj_path), json_or_die(mj_path)
    live2, tomb2 = market_entries(mj2, P)
    bad = []
    if pj2.get("version") != a.version:
        bad.append("plugin.json=%r" % pj2.get("version"))
    if mj2.get("metadata", {}).get("version") != a.version:
        bad.append("marketplace.metadata=%r" % mj2.get("metadata", {}).get("version"))
    if live2 is None or live2.get("version") != a.version:
        bad.append("marketplace.%s=%r" % (P["name"], (live2 or {}).get("version")))
    if tomb_before is not None:
        if tomb2 is None:
            bad.append("tombstone entry vanished")
        elif tomb2 != tomb_before:
            bad.append("TOMBSTONE MUTATED %r -> %r"
                       % (tomb_before.get("version"), (tomb2 or {}).get("version")))
    if bad:
        die(12, "POST-WRITE", "manifest re-assert failed: " + "; ".join(bad))
    print("manifests: both written (%s/%s) · tombstone %s"
          % (how_pj, how_mj, "untouched" if tomb_before else "absent at this sha"))

    # 3b. prose surfaces: spelled words, plus the repo-root numeral forms.
    spelled_checked = [P["plugin_json"], P["market_json"]]
    for key in ("tutorial", "readme"):
        p = os.path.join(repo, P[key])
        if not os.path.exists(p):
            print("counts: %s absent — surface skipped" % P[key])
            continue
        t, k = respell(read(p), word)
        write(p, t)
        rewrites += k
        spelled_checked.append(P[key])
    numeral_checked = []
    for key in ("root_readme", "root_claude"):
        p = os.path.join(repo, P[key])
        if not os.path.exists(p):
            continue
        cur = read(p)
        if not NUM_RE.search(cur):
            continue                    # no numeral count on this surface — nothing to own
        t, k = renumber(cur, n)
        write(p, t)
        rewrites += k
        numeral_checked.append(P[key])

    # 3c. exit 13 when the surfaces still disagree after the rewrite. The checker is wider
    # than the rewriter on purpose, and quotes the offending line.
    for rel in spelled_checked:
        text = read(os.path.join(repo, rel))
        toks = list(COUNT_SCAN_RE.finditer(text))
        if not toks:
            die(13, "COUNT", "%s carries no spelled skill count — cannot reconcile" % rel)
        for m in toks:
            if word_to_num(m.group(0)) != n:
                die(13, "COUNT", "%s says %r, directory count is %d (%s)\n  %s"
                    % (rel, m.group(0), n, word, quote_line(text, m.start())))
    for rel in numeral_checked:
        text = read(os.path.join(repo, rel))
        for m in NUM_RE.finditer(text):
            if int(m.group(1)) != n:
                die(13, "COUNT", "%s says %r, directory count is %d\n  %s"
                    % (rel, m.group(0), n, quote_line(text, m.start())))
    print("counts: %d skills (%s) · %d surfaces agree · %d rewrites"
          % (n, word, len(spelled_checked) + len(numeral_checked), rewrites))

    # 4. flow-page stamps: each pattern must match exactly once.
    flow_path = os.path.join(repo, P["flow"])
    if not os.path.exists(flow_path):
        die(14, "FLOW", "missing %s" % P["flow"])
    flow = read(flow_path)
    head_new = "v%s · %d-skill %s" % (a.version, n, P["flow_word"])
    foot_new = "Manifest: %s v%s" % (P["name"], a.version)
    for rx, repl, what in ((flow_head_re(P), head_new, "header stamp"),
                           (FLOW_FOOT_RE, foot_new, "footer stamp")):
        hits = rx.findall(flow)
        if len(hits) != 1:
            die(14, "FLOW", "%s matched %d times in %s, expected exactly 1"
                % (what, len(hits), P["flow"]))
        flow = rx.sub(lambda _m: repl, flow, count=1)
    write(flow_path, flow)
    print("flow: stamped %r / %r" % (head_new, foot_new))

    # 5b. prepend the changelog section under the title line.
    if section is not None:
        cl_path = os.path.join(repo, P["changelog"])
        cl = read(cl_path)
        m = re.search(r"^## ", cl, re.M)
        head = cl[:m.start()] if m else (cl if cl.endswith("\n\n") else cl.rstrip("\n") + "\n\n")
        rest = cl[m.start():] if m else ""
        if not section.endswith("\n\n"):
            section = section.rstrip("\n") + "\n\n"
        write(cl_path, head + section + rest)
        print("changelog: section %s prepended (%d chars)" % (a.version, len(section)))
    else:
        print("changelog: no --changelog-file — CHANGELOG.md untouched")

    # 6b. append the coord line(s).
    if a.coord_line:
        co_path = os.path.join(repo, P["coord"])
        co = read(co_path) if os.path.exists(co_path) else ""
        if co and not co.endswith("\n"):
            co += "\n"
        write(co_path, co + "".join(l.rstrip("\n") + "\n" for l in a.coord_line))
        print("coord: %d line(s) appended" % len(a.coord_line))
    else:
        print("coord: no --coord-line — COORD.md untouched")

    # 7. spend gate — its exit 4 is a routing violation and aborts the ship.
    verdict = "n/a"
    spend_path = os.path.join(repo, P["spend"])
    if not os.path.exists(spend_path):
        print("spend: script absent at %s — gate skipped" % P["spend"])
    else:
        sp = run([sys.executable, spend_path, "report"], cwd=repo)
        out = (sp.stdout or "") + (sp.stderr or "")
        for line in out.rstrip("\n").split("\n"):
            print("spend| " + line)
        for line in out.split("\n"):
            if line.startswith("routing:"):
                verdict = line.strip()
        if sp.returncode == 4:
            die(17, "SPEND", "spend report exit 4 — model-routing violation:\n" + out)
        print("spend: report exit %d (only exit 4 aborts)" % sp.returncode)

    # 8. manifest validation. Absence of the CLI is the ONLY skip; any completed run that
    # exits nonzero is a failure, whatever its stderr happens to say.
    if a.skip_validate:
        print("validate: skipped by flag")
    else:
        try:
            vp = subprocess.run(["claude", "plugin", "validate", "."], cwd=repo,
                                capture_output=True, text=True)
        except FileNotFoundError:
            print("validate: claude CLI absent — gate skipped")
        else:
            if vp.returncode != 0:
                die(18, "VALIDATE", "claude plugin validate . -> exit %d\nstdout: %s\nstderr: %s"
                    % (vp.returncode, (vp.stdout or "").strip(), (vp.stderr or "").strip()))
            print("validate: passed")

    # 9. commit.
    run(["git", "add", "-A"], cwd=repo, check=True, kind="GIT")
    if run(["git", "diff", "--cached", "--quiet"], cwd=repo).returncode == 0:
        die(19, "EMPTY-COMMIT", "nothing staged — the ritual changed no tracked file")
    msg = a.message.rstrip("\n") + "\n\n" + TRAILER + "\n"
    cp = subprocess.run(["git", "commit", "-F", "-"], cwd=repo, input=msg,
                        capture_output=True, text=True)
    if cp.returncode != 0:
        die(19, "COMMIT", "git commit failed\n%s%s" % (cp.stdout, cp.stderr))
    sha = run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, kind="GIT").stdout.strip()
    ROLLBACK["repo"], ROLLBACK["files"] = None, []   # committed: nothing left to roll back
    print("commit: %s" % sha[:7])

    # 10. push (explicit flag). The exact object goes to the exact ref, and the ref is read
    # back: no branch guessing, and an empty ls-remote is its own failure, not a match.
    pushed = "no"
    if a.push:
        branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo,
                     check=True, code=20, kind="PUSH").stdout.strip()
        if branch == "HEAD":
            die(20, "PUSH-DETACHED", "HEAD is detached — refusing to guess a target branch")
        run(["git", "push", "origin", "%s:refs/heads/%s" % (sha, branch)], cwd=repo,
            check=True, code=20, kind="PUSH")
        ls = run(["git", "ls-remote", "origin", "refs/heads/%s" % branch], cwd=repo,
                 check=True, code=20, kind="PUSH")
        out = (ls.stdout or "").strip()
        if not out:
            die(20, "PUSH-VERIFY", "ls-remote reports no refs/heads/%s on origin — the push "
                                   "cannot be confirmed" % branch)
        remote = out.split()[0]
        if remote != sha:
            die(20, "PUSH-VERIFY", "origin %s is %s, local HEAD is %s"
                % (branch, remote[:7], sha[:7]))
        pushed = "yes"
        print("push: origin/%s == %s (ls-remote verified)" % (branch, sha[:7]))
    else:
        print("push: STOPPED after commit — rerun with --push to publish")

    # 11. install (explicit flag; parsed for the target version, never assumed).
    installed = "no"
    cmds = [["claude", "plugin", "marketplace", "update", "notrest"],
            ["claude", "plugin", "update", "notrest@notrest"]]
    if a.install:
        blob = ""
        for c in cmds:
            try:
                ip = subprocess.run(c, cwd=repo, capture_output=True, text=True)
            except FileNotFoundError:
                die(21, "INSTALL", "claude CLI absent — cannot install")
            blob += (ip.stdout or "") + (ip.stderr or "")
            print("install| %s -> exit %d" % (" ".join(c), ip.returncode))
        if a.version not in blob:
            die(21, "INSTALL", "install output never mentions %s:\n%s" % (a.version, blob))
        installed = "yes"
        print("install: %s confirmed in CLI output" % a.version)
    else:
        for c in cmds:
            print("install: run yourself -> %s" % " ".join(c))

    print("SHIP %s · commit %s · pushed=%s · installed=%s · spend=%s"
          % (a.version, sha[:7], pushed, installed, verdict))
    return 0


# ------------------------------------------------------------------------- replay

def git_show(repo, sha, path):
    p = run(["git", "show", "%s:%s" % (sha, path)], cwd=repo)
    return p.stdout if p.returncode == 0 else None


def hist_dir_count(repo, sha, P):
    p = run(["git", "ls-tree", "--name-only", "-d", "%s:%s" % (sha, P["skills_dir"])], cwd=repo)
    if p.returncode != 0:
        return None
    return len([x for x in p.stdout.split("\n") if x.strip()])


def top_section(changelog_text):
    m = re.search(r"^## ", changelog_text, re.M)
    if not m:
        return None
    m2 = re.search(r"^## ", changelog_text[m.end():], re.M)
    end = m.end() + m2.start() if m2 else len(changelog_text)
    return changelog_text[m.start():end]


def do_replay(a):
    src = os.path.abspath(a.repo)
    P = paths(a.legacy_paths)
    OTHER = paths(not a.legacy_paths)
    stages = []

    def stage(name, t0):
        stages.append((name, (time.perf_counter() - t0) * 1000.0))

    sha = run(["git", "rev-parse", a.at], cwd=src, check=True, kind="GIT").stdout.strip()
    scratch = os.path.abspath(a.scratch)
    clone = os.path.join(scratch, "clone")
    if os.path.exists(clone):
        die(2, "ARGS", "scratch clone already exists: %s" % clone)
    os.makedirs(scratch, exist_ok=True)

    t = time.perf_counter()
    run(["git", "clone", "--quiet", src, clone], check=True, kind="GIT")
    stage("clone", t)

    # Payload forward, procedure reverted: the worktree starts at the ship commit (so the
    # feature payload that ship carried is present, exactly as ship.py never owned it), and
    # only what the ritual writes is rolled back. HEAD sits at <sha>~1 so the commit stage
    # has a real diff to stage.
    t = time.perf_counter()
    run(["git", "checkout", "--quiet", "--detach", sha], cwd=clone, check=True, kind="GIT")
    run(["git", "reset", "--soft", "%s~1" % sha], cwd=clone, check=True, kind="GIT")

    prev_mj = git_show(src, sha + "~1", P["market_json"])
    prev_version = None
    if prev_mj:
        try:
            prev_version = json.loads(prev_mj).get("metadata", {}).get("version")
        except Exception:
            prev_version = None
    if not prev_version:
        pv = git_show(src, sha + "~1", P["plugin_json"]) or \
            git_show(src, sha + "~1", OTHER["plugin_json"])
        if pv:
            try:
                prev_version = json.loads(pv).get("version")
            except Exception:
                pass
    if not prev_version:
        die(2, "REPLAY", "cannot determine the pre-ship version at %s~1" % sha[:7])

    # de-ship: manifest versions back to the previous version (scalar edits only).
    for rel, edits in ((P["plugin_json"], [("root", "version", prev_version)]),
                       (P["market_json"], [("metadata", "version", prev_version),
                                           (P["name"], "version", prev_version)])):
        p = os.path.join(clone, rel)
        orig = read(p)
        write_manifest(p, json.loads(orig), orig, edits)

    # de-ship: flow stamps back to their pre-ship text. Only rolls back a stamp the current
    # profile recognises — the rename ship changed the page's vocabulary as payload, and
    # de-shipping payload is not this script's business.
    prev_flow = git_show(src, sha + "~1", P["flow"])
    flow_path = os.path.join(clone, P["flow"])
    if prev_flow and os.path.exists(flow_path):
        cur = read(flow_path)
        for rx in (flow_head_re(P), FLOW_FOOT_RE):
            pm, cm = rx.search(prev_flow), rx.search(cur)
            if pm and cm:
                cur = cur[:cm.start()] + pm.group(0) + cur[cm.end():]
        write(flow_path, cur)

    # de-ship: the spelled count on every count surface back to its pre-ship word, so the
    # reconciliation is a real operation in the replay and those surfaces can be compared.
    for key in ("tutorial", "readme", "plugin_json", "market_json"):
        prev = git_show(src, sha + "~1", P[key]) or git_show(src, sha + "~1", OTHER[key])
        p = os.path.join(clone, P[key])
        if prev is None or not os.path.exists(p):
            continue
        pw = [c for c in spelled_counts(prev) if c]
        if not pw:
            continue
        write(p, respell(read(p), num_to_word(pw[0]))[0])
    stage("seed+deship", t)

    # inputs extracted from the repo's own history — never re-authored here.
    t = time.perf_counter()
    at_pj = git_show(src, sha, P["plugin_json"])
    if not at_pj:
        die(2, "REPLAY", "no %s at %s (try --legacy-paths)" % (P["plugin_json"], sha[:7]))
    version = json.loads(at_pj).get("version")
    sect = top_section(git_show(src, sha, P["changelog"]) or "")
    cl_file = None
    date = None
    if sect:
        date = sect.split("\n", 1)[0].strip().split("—")[-1].strip()
        cl_file = os.path.join(scratch, "changelog-section.md")
        write(cl_file, sect)
    dp = run(["git", "show", sha, "--", P["coord"]], cwd=src)
    coord = [l[1:] for l in dp.stdout.split("\n")
             if l.startswith("+") and not l.startswith("+++") and l[1:].startswith("- [")]
    body = run(["git", "log", "-1", "--format=%B", sha], cwd=src, check=True, kind="GIT").stdout
    msg = "\n".join(l for l in body.split("\n")
                    if not l.startswith("Co-Authored-By:")).rstrip("\n")

    # De-ship the prose surfaces by REMOVING ONLY WHAT THE RITUAL WRITES, never by reverting
    # the file: v3.0.0 also retitled CHANGELOG.md, and that retitle is payload. Reverting
    # wholesale would ask the script to reproduce a payload edit it does not own.
    at_cl = git_show(src, sha, P["changelog"])
    if at_cl is not None and sect:
        write(os.path.join(clone, P["changelog"]), at_cl.replace(sect, "", 1))
    at_co = git_show(src, sha, P["coord"])
    if at_co is not None and coord:
        for line in coord:
            at_co = at_co.replace(line + "\n", "", 1)
        write(os.path.join(clone, P["coord"]), at_co)
    stage("extract-inputs", t)
    print("replay %s: version=%s date=%s coord-lines=%d changelog=%s"
          % (sha[:7], version, date, len(coord), "yes" if cl_file else "no"))

    t = time.perf_counter()
    sa = argparse.Namespace(repo=clone, version=version, gates_passed=True, message=msg,
                            changelog_file=cl_file, date=date, coord_line=coord,
                            push=False, install=False, legacy_paths=a.legacy_paths,
                            skip_validate=a.skip_validate, replay_mode=True)
    do_ship(sa)
    stage("ship-pipeline", t)

    # parity — nine ritual-owned surfaces. Feature payload stays out of scope by design: a
    # ship commit carries payload + procedure, and this script owns only the procedure.
    t = time.perf_counter()
    print("--- parity (nine ritual-owned surfaces) ---")
    hist_n = hist_dir_count(src, sha, P)
    counters = {"differs": 0, "drift": 0}

    def report(label, verdict, note="", got=None, want=None):
        print("PARITY %-52s %s%s" % (label, verdict, (" — " + note) if note else ""))
        if verdict == "DIFFERS" and got is not None:
            d = list(difflib.unified_diff((want or "").split("\n"), (got or "").split("\n"),
                                          "expected", "produced", lineterm=""))
            for line in d[:24]:
                print("  " + line)

    def cmp_plain(label, got, want, note=""):
        if got == want:
            report(label, "IDENTICAL", note)
        else:
            counters["differs"] += 1
            report(label, "DIFFERS", note, got, want)

    def cmp_counted(label, got, want):
        """Count surfaces. A difference that is ONLY the spelled count, against a historical
        file that disagreed with its OWN skills directory, is drift the ritual corrected —
        reported as DRIFT (verifiable arithmetic, not a judgement call). Anything else,
        including a count difference where history was self-consistent, is a real DIFFERS."""
        if got == want:
            report(label, "IDENTICAL")
            return
        hw = [c for c in spelled_counts(want) if c]
        norm_g = respell(got or "", "twenty")[0]
        norm_w = respell(want or "", "twenty")[0]
        if hw and hist_n is not None and norm_g == norm_w and hw[0] != hist_n:
            counters["drift"] += 1
            report(label, "DRIFT", "history says %s, that tree has %d skill dirs — ritual wrote %s"
                   % (num_to_word(hw[0]), hist_n, num_to_word(hist_n)))
        else:
            counters["differs"] += 1
            report(label, "DIFFERS", "", got, want)

    pj_path = os.path.join(clone, P["plugin_json"])
    mj_path = os.path.join(clone, P["market_json"])
    got_pj = json.loads(read(pj_path))
    want_pj = json.loads(git_show(src, sha, P["plugin_json"]))
    cmp_plain(P["plugin_json"] + " (version)", got_pj.get("version"), want_pj.get("version"))

    def mkey(doc):
        lv, tb = market_entries(doc, P)
        return "metadata=%s %s=%s tombstone=%s" % (
            doc.get("metadata", {}).get("version"), P["name"],
            (lv or {}).get("version"), (tb or {}).get("version", "absent"))
    got_mj = json.loads(read(mj_path))
    want_mj = json.loads(git_show(src, sha, P["market_json"]))
    cmp_plain(P["market_json"] + " (versions)", mkey(got_mj), mkey(want_mj))

    cmp_plain(P["changelog"], read(os.path.join(clone, P["changelog"])),
              git_show(src, sha, P["changelog"]), "round-trip")
    cmp_plain(P["flow"], read(os.path.join(clone, P["flow"])), git_show(src, sha, P["flow"]))
    co_p = os.path.join(clone, P["coord"])
    cmp_plain(P["coord"], read(co_p) if os.path.exists(co_p) else None,
              git_show(src, sha, P["coord"]), "round-trip")

    for key in ("tutorial", "readme"):
        p = os.path.join(clone, P[key])
        cmp_counted(P[key], read(p) if os.path.exists(p) else None, git_show(src, sha, P[key]))
    cmp_counted(P["plugin_json"] + " (description)",
                got_pj.get("description"), want_pj.get("description"))
    cmp_counted(P["market_json"] + " (description)",
                (market_entries(got_mj, P)[0] or {}).get("description"),
                (market_entries(want_mj, P)[0] or {}).get("description"))
    stage("parity", t)

    if a.time:
        print("--- timing (wall ms) ---")
        for name, ms in stages:
            print("  %-16s %8.1f" % (name, ms))
        print("  %-16s %8.1f" % ("TOTAL", sum(m for _, m in stages)))

    verdict = "FAIL" if counters["differs"] else "PASS"
    tail = "" if not counters["drift"] else \
        " (%d historical drift(s) corrected)" % counters["drift"]
    print("REPLAY %s · %s · surfaces=9 · differs=%d · drift=%d · PARITY %s%s"
          % (sha[:7], version, counters["differs"], counters["drift"], verdict, tail))
    return 30 if counters["differs"] else 0


def main():
    ap = argparse.ArgumentParser(prog="ship.py", description="the notrest release ritual as code")
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), help="repo root (default: this checkout)")
    ap.add_argument("--legacy-paths", action="store_true",
                    help="pre-rename layout and vocabulary: plugins/oracle-suite/*, N-skill suite")
    ap.add_argument("--skip-validate", action="store_true", help="skip claude plugin validate")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ship", help="run the release ritual")
    s.add_argument("--version", required=True)
    s.add_argument("--gates-passed", action="store_true", help="the human quality ruling")
    s.add_argument("--message", required=True, help="commit message (trailer is added)")
    s.add_argument("--changelog-file")
    s.add_argument("--date", help="changelog date (default: today UTC; replay passes history)")
    s.add_argument("--coord-line", action="append", default=[])
    s.add_argument("--push", action="store_true", help="irreversible: publishes to origin")
    s.add_argument("--install", action="store_true", help="irreversible: updates the local install")
    s.set_defaults(fn=do_ship)

    r = sub.add_parser("replay", help="re-run a historical ship and parity-diff it")
    r.add_argument("--at", required=True, help="ship commit sha")
    r.add_argument("--scratch", required=True)
    r.add_argument("--time", action="store_true", help="print wall-ms per stage")
    r.set_defaults(fn=do_replay)

    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
