#!/usr/bin/env python3
"""doctor.py — the harness's self-check.

Reads a notrest/oracle-family repo (or an installed plugin cache dir) and reports one
named PASS/WARN/FAIL line per check, each carrying the command that fixes it.

Constraints this file is built under:
  - python3 stdlib ONLY (no yaml, no requests) — doctor must run on a bare interpreter,
    including inside a plugin cache dir with no project virtualenv anywhere near it.
  - doctor READS. It never repairs, never writes, never bumps. Every FAIL carries a fix
    command for the owner/seat to run.
  - a check whose inputs are absent reports SKIP, never a false FAIL (the --plugin cache
    dir legitimately has no marketplace.json, no docs/, no estate).

Exit codes: 0 all pass · 5 warnings only · 6 any fail · 3 target unusable · 2 usage.
"""

import argparse
import json
import os
import re
import subprocess
import sys

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
EXIT_OK, EXIT_USAGE, EXIT_TARGET, EXIT_WARN, EXIT_FAIL = 0, 2, 3, 5, 6

# The migration stub for the oracle-suite -> notrest rename. Pinned forever: bumping it
# would re-offer the dead plugin to existing installs instead of pointing them at the new id.
TOMBSTONE_NAME = "oracle-suite"
TOMBSTONE_VERSION = "9.0.0"


# ── number words ──────────────────────────────────────────────────────────────────────
def _word_numbers():
    units = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
             "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
             "seventeen", "eighteen", "nineteen"]
    tens = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    out = {w: i for i, w in enumerate(units)}
    for t, word in enumerate(tens):
        out[word] = (t + 2) * 10
        for u in range(1, 10):
            out["%s-%s" % (word, units[u])] = (t + 2) * 10 + u
    return out


WORD2NUM = _word_numbers()


def spelled_count(text):
    """First number (word or digits) that qualifies the word 'skills' within a short span."""
    if not text:
        return None
    for m in re.finditer(r"\b([A-Za-z]+(?:-[A-Za-z]+)?|\d{1,3})\b(?=.{0,45}?\bskills\b)",
                         text, re.I | re.S):
        tok = m.group(1).lower()
        n = int(tok) if tok.isdigit() else WORD2NUM.get(tok)
        if n is not None:
            return n
    return None


# ── io helpers ────────────────────────────────────────────────────────────────────────
def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return None


def jload(path):
    """-> (obj, error_string). Never raises: a broken manifest is a finding, not a crash."""
    raw = read(path)
    if raw is None:
        return None, "unreadable"
    try:
        return json.loads(raw), None
    except Exception as exc:
        return None, str(exc)


def run(cmd, cwd=None, timeout=45):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return None, str(exc)


# ── minimal front-matter parse (check 1) ──────────────────────────────────────────────
BLOCK_INDICATORS = ("|", ">", "|-", ">-", "|+", ">+")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*):(?:[ \t]+(.*))?$")


def scalar_errors(key, value, line_no):
    """Reject exactly what a real YAML load rejects in a front-matter scalar — no more."""
    errs = []
    if value == "":
        return errs
    q = value[0]
    if q in "\"'":
        if len(value) < 2 or value[-1] != q:
            errs.append("line %d: '%s' opens with %s and never closes it" % (line_no, key, q))
            return errs
        inner = value[1:-1]
        stray = (re.sub(r"\\.", "", inner).count('"') if q == '"'
                 else inner.replace("''", "").count("'"))
        if stray:
            errs.append("line %d: '%s' carries %d unescaped %s inside its quoted scalar"
                        % (line_no, key, stray, q))
        return errs
    if ": " in value or value.endswith(":"):
        errs.append("line %d: '%s' is an UNQUOTED scalar containing ': ' — YAML reads that as a "
                    "nested mapping, the front-matter fails to load, and the skill goes invisible"
                    % (line_no, key))
    if " #" in value:
        errs.append("line %d: '%s' is an UNQUOTED scalar containing ' #' — YAML truncates the "
                    "value at the comment" % (line_no, key))
    if value[0] in "[{&*!%@`":
        errs.append("line %d: '%s' starts with the YAML indicator '%s' — quote the value"
                    % (line_no, key, value[0]))
    return errs


def parse_frontmatter(text):
    """-> (keys, errors). '---' fences, 'key: value' lines, folded continuations, block
    scalars. Stdlib only, so this is deliberately narrow: SKILL.md front-matter is a flat
    string map and anything richer is reported rather than guessed at."""
    if text is None:
        return {}, ["file is unreadable"]
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, ["no opening '---' fence on line 1"]
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, ["front-matter fence is never closed"]

    keys, order, errors, cur, block = {}, [], [], None, False
    for n in range(1, end):
        line = lines[n]
        if not line.strip():
            if not block:
                cur = None
            continue
        indented = line[:1].isspace()
        m = None if indented else KEY_RE.match(line)
        if m:
            cur = m.group(1)
            raw = (m.group(2) or "").strip()
            if cur in keys:
                errors.append("line %d: duplicate key '%s'" % (n + 1, cur))
            block = raw in BLOCK_INDICATORS
            keys[cur] = "" if block else raw
            if not block:
                order.append((cur, n + 1))
        elif cur is not None:
            # continuation: folded into the value (block scalar content or a wrapped scalar)
            keys[cur] = (keys[cur] + " " + line.strip()).strip()
        else:
            errors.append("line %d: neither a 'key: value' line nor a continuation" % (n + 1))
    for key, line_no in order:
        errors.extend(scalar_errors(key, keys[key], line_no))
    return keys, errors


# ── target resolution ─────────────────────────────────────────────────────────────────
class Target(object):
    def __init__(self, root, mode, plugins, primary):
        self.root = root
        self.mode = mode              # "repo" | "plugin"
        self.plugins = plugins        # every plugin dir carrying a .claude-plugin/plugin.json
        self.primary = primary        # the plugin dir that owns the skills
        self.marketplace = os.path.join(root, ".claude-plugin", "marketplace.json")
        if not os.path.isfile(self.marketplace):
            self.marketplace = None
        self.tutorial = self._first(os.path.join(root, "docs", "TUTORIAL.md"),
                                    os.path.join(primary or root, "docs", "TUTORIAL.md"))
        self.inner_readme = self._first(os.path.join(primary, "README.md")) if primary else None
        self.html = self._first(os.path.join(root, "docs", "oracle-skill-flow.html"))
        self.gitignore = self._first(os.path.join(root, ".gitignore"))
        self.coord = self._first(os.path.join(root, "COORD.md"))
        self.coord_agents = self._first(os.path.join(root, "COORD-AGENTS.md"))
        self.ledger = self._first(os.path.join(root, "spend", "ledger.md"))
        self.candidates = self._first(os.path.join(root, "compile", "candidates.json"))

    @staticmethod
    def _first(*paths):
        for p in paths:
            if p and os.path.isfile(p):
                return p
        return None

    def rel(self, path):
        try:
            return os.path.relpath(path, self.root)
        except Exception:
            return path

    def skill_dirs(self, plugin_dir):
        base = os.path.join(plugin_dir, "skills")
        if not os.path.isdir(base):
            return []
        return sorted(os.path.join(base, d) for d in os.listdir(base)
                      if os.path.isfile(os.path.join(base, d, "SKILL.md")))

    def manifest(self, plugin_dir):
        return os.path.join(plugin_dir, ".claude-plugin", "plugin.json")


def resolve(args):
    if args.plugin:
        root = os.path.abspath(args.plugin)
        if not os.path.isdir(root):
            return None, "no such directory: %s" % root
        if not os.path.isfile(os.path.join(root, ".claude-plugin", "plugin.json")):
            return None, "%s is not a plugin dir (no .claude-plugin/plugin.json)" % root
        return Target(root, "plugin", [root], root), None

    root = os.path.abspath(args.root) if args.root else None
    if root is None:
        rc, out = run(["git", "rev-parse", "--show-toplevel"], cwd=os.getcwd())
        root = out.strip() if rc == 0 and out.strip() else os.getcwd()
    if not os.path.isdir(root):
        return None, "no such directory: %s" % root

    plugins_dir = os.path.join(root, "plugins")
    plugins = []
    if os.path.isdir(plugins_dir):
        for d in sorted(os.listdir(plugins_dir)):
            p = os.path.join(plugins_dir, d)
            if os.path.isfile(os.path.join(p, ".claude-plugin", "plugin.json")):
                plugins.append(p)
    if not plugins and os.path.isfile(os.path.join(root, ".claude-plugin", "plugin.json")):
        plugins = [root]
    if not plugins:
        return None, ("%s holds no plugin (expected plugins/*/.claude-plugin/plugin.json). "
                      "Point --root at the marketplace repo or use --plugin." % root)

    tmp = Target(root, "repo", plugins, plugins[0])
    primary = max(plugins, key=lambda p: len(tmp.skill_dirs(p)))
    mk, _ = jload(tmp.marketplace) if tmp.marketplace else (None, None)
    if isinstance(mk, dict) and mk.get("name"):
        for p in plugins:
            man, _ = jload(os.path.join(p, ".claude-plugin", "plugin.json"))
            if isinstance(man, dict) and man.get("name") == mk.get("name"):
                primary = p
                break
    return Target(root, "repo", plugins, primary), None


# ── checks ────────────────────────────────────────────────────────────────────────────
def check_frontmatter(t):
    files = []
    for p in t.plugins:
        files.extend(os.path.join(d, "SKILL.md") for d in t.skill_dirs(p))
    if not files:
        return SKIP, ["no SKILL.md files under this target"], None

    broken, quoted = [], 0
    for f in files:
        keys, errors = parse_frontmatter(read(f))
        if not keys.get("name"):
            errors.append("no 'name' key (or it is empty)")
        if not keys.get("description", "").strip():
            errors.append("no 'description' key (or it is empty)")
        if keys.get("description", "")[:1] == '"':
            quoted += 1
        if errors:
            broken.append((t.rel(f), errors))

    detail = ["%d SKILL.md scanned · %d description scalars quoted" % (len(files), quoted)]
    if not broken:
        return PASS, detail + ["every front-matter parses with name + description present"], None
    for path, errors in broken:
        detail.append("%s:" % path)
        detail.extend("    - %s" % e for e in errors)
    return FAIL, detail, ('quote the offending scalar: description: "..." (escape any interior "), '
                          "then re-run doctor; a skill whose front-matter fails to load is invisible "
                          "to the model even though the file is on disk")


def check_manifests(t):
    detail, status = [], PASS
    versions = {}
    for p in t.plugins:
        man = t.manifest(p)
        obj, err = jload(man)
        if err:
            return FAIL, ["%s is not valid JSON: %s" % (t.rel(man), err)], \
                "repair the JSON (python3 -m json.tool %s)" % t.rel(man)
        versions[obj.get("name") or t.rel(p)] = obj.get("version")
        detail.append("%s = %s v%s" % (t.rel(man), obj.get("name"), obj.get("version")))

    primary_man, _ = jload(t.manifest(t.primary))
    name = primary_man.get("name")
    version = primary_man.get("version")

    if t.marketplace is None:
        detail.append("no marketplace.json under this target — cross-manifest match SKIPPED")
        return status, detail, None

    mk, err = jload(t.marketplace)
    if err:
        return FAIL, detail + ["%s is not valid JSON: %s" % (t.rel(t.marketplace), err)], \
            "repair the JSON (python3 -m json.tool .claude-plugin/marketplace.json)"

    fix = None
    meta_v = (mk.get("metadata") or {}).get("version")
    entries = {e.get("name"): e for e in mk.get("plugins", []) if isinstance(e, dict)}
    entry_v = (entries.get(name) or {}).get("version")
    detail.append("marketplace.json metadata=v%s · entry[%s]=v%s" % (meta_v, name, entry_v))
    if not (version == meta_v == entry_v):
        status = FAIL
        detail.append("VERSION MISMATCH: plugin.json=v%s metadata=v%s entry=v%s"
                      % (version, meta_v, entry_v))
        fix = ("set all three to the same version (plugins/%s/.claude-plugin/plugin.json, "
               ".claude-plugin/marketplace.json metadata.version and the '%s' entry) before "
               "pushing — a mismatch installs a version that does not exist"
               % (os.path.basename(t.primary), name))

    tomb = entries.get(TOMBSTONE_NAME)
    if tomb is None:
        detail.append("no '%s' tombstone entry — pin check SKIPPED" % TOMBSTONE_NAME)
    else:
        tomb_local = None
        for p in t.plugins:
            obj, _ = jload(t.manifest(p))
            if isinstance(obj, dict) and obj.get("name") == TOMBSTONE_NAME:
                tomb_local = obj.get("version")
        bad = [x for x in (("marketplace entry", tomb.get("version")),
                           ("tombstone plugin.json", tomb_local))
               if x[1] is not None and x[1] != TOMBSTONE_VERSION]
        if bad:
            status = FAIL
            detail.append("TOMBSTONE UNPINNED: " + ", ".join("%s=v%s" % b for b in bad))
            fix = ("reset the %s tombstone to exactly v%s everywhere — it is a migration stub, "
                   "never bumped; bumping it re-offers the dead plugin id to existing installs"
                   % (TOMBSTONE_NAME, TOMBSTONE_VERSION))
        else:
            detail.append("%s tombstone pinned at v%s" % (TOMBSTONE_NAME, TOMBSTONE_VERSION))
    return status, detail, fix


def check_skill_count(t):
    dirs = t.skill_dirs(t.primary)
    if not dirs:
        return SKIP, ["no skills/ dir under %s" % t.rel(t.primary)], None
    n = len(dirs)
    sources = [("skills/ dirs", n)]

    if t.tutorial:
        sources.append((t.rel(t.tutorial), spelled_count(read(t.tutorial))))
    if t.inner_readme:
        sources.append((t.rel(t.inner_readme), spelled_count(read(t.inner_readme))))
    man, _ = jload(t.manifest(t.primary))
    sources.append((t.rel(t.manifest(t.primary)),
                    spelled_count((man or {}).get("description", ""))))
    if t.marketplace:
        mk, _ = jload(t.marketplace)
        entry = next((e for e in (mk or {}).get("plugins", [])
                      if isinstance(e, dict) and e.get("name") == (man or {}).get("name")), None)
        if entry:
            sources.append((t.rel(t.marketplace), spelled_count(entry.get("description", ""))))

    detail = [" · ".join("%s=%s" % (s, v if v is not None else "not stated")
                         for s, v in sources)]
    off = [(s, v) for s, v in sources if v is not None and v != n]
    missing = [s for s, v in sources if v is None]
    if off:
        return FAIL, detail + ["COUNT DRIFT: %s disagree with the %d skill dirs on disk"
                               % (", ".join(s for s, _ in off), n)], \
            ("update the spelled count to %d in: %s (the number is prose in four places and "
             "drifts every time a skill lands)" % (n, ", ".join(s for s, _ in off)))
    if missing:
        return WARN, detail + ["no count stated in: %s" % ", ".join(missing)], \
            "state the skill count (%d) in %s so drift stays detectable" % (n, ", ".join(missing))
    return PASS, detail + ["all sources agree on %d" % n], None


HOOKPATH_RE = re.compile(r"\$\{?CLAUDE_PLUGIN_ROOT\}?(/[^\"'\s]+)")


def check_hooks(t):
    status, detail, fix = PASS, [], None
    seen = 0
    for p in t.plugins:
        hj = os.path.join(p, "hooks", "hooks.json")
        if not os.path.isfile(hj):
            continue
        seen += 1
        obj, err = jload(hj)
        if err:
            status = FAIL
            detail.append("%s is not valid JSON: %s" % (t.rel(hj), err))
            fix = "repair the JSON (python3 -m json.tool %s)" % t.rel(hj)
            continue
        man, _ = jload(t.manifest(p))
        name = (man or {}).get("name", "")
        events = obj.get("hooks", {}) if isinstance(obj, dict) else {}
        scripts, session_start = [], []
        for event, groups in events.items():
            for group in groups or []:
                for hook in (group or {}).get("hooks", []) or []:
                    m = HOOKPATH_RE.search(hook.get("command", "") or "")
                    if not m:
                        continue
                    path = os.path.join(p, m.group(1).lstrip("/"))
                    scripts.append((event, path))
                    if event == "SessionStart":
                        session_start.append(path)
        detail.append("%s: %d events · %d referenced scripts" % (t.rel(hj), len(events), len(scripts)))
        for event, path in scripts:
            if not os.path.isfile(path):
                status = FAIL
                detail.append("    MISSING %s -> %s" % (event, t.rel(path)))
                fix = "restore the missing hook script or drop its entry from hooks.json"
                continue
            if path.endswith(".sh"):
                rc, out = run(["bash", "-n", path])
                if rc != 0:
                    status = FAIL
                    detail.append("    SYNTAX %s -> %s: %s"
                                  % (event, t.rel(path), out.strip().split("\n")[0]))
                    fix = ("fix the shell syntax (bash -n %s) — a hook that will not parse fails "
                           "silently at session start" % t.rel(path))
        if session_start and name:
            marker = "[%s]" % name
            if not any(marker in (read(s) or "") for s in session_start if os.path.isfile(s)):
                status = FAIL
                detail.append("    RENAME RESIDUE: no SessionStart script announces '%s'" % marker)
                fix = ("update the SessionStart echo prefix to '%s' — the announcement still "
                       "carries the old plugin id after a rename" % marker)
    if not seen:
        return SKIP, ["no hooks.json under this target"], None
    return status, detail, fix


COORD_LINE_RE = re.compile(r"^- \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z\] ")


def spend_py(t):
    for p in t.plugins:
        cand = os.path.join(p, "skills", "spend", "scripts", "spend.py")
        if os.path.isfile(cand):
            return cand
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "spend", "scripts", "spend.py")
    return os.path.normpath(sibling) if os.path.isfile(sibling) else None


def check_estate(t):
    status, detail, fix, seen = PASS, [], None, 0

    def worse(new):
        order = {PASS: 0, WARN: 1, FAIL: 2}
        return new if order[new] > order[status] else status

    if t.coord:
        seen += 1
        text = read(t.coord) or ""
        lines = text.split("\n")
        head_ok = lines and lines[0].startswith("# COORD.md")
        ledger_ok = "## LEDGER" in text
        entries = [l for l in lines if l.startswith("- ")]
        bad = [l for l in entries if not COORD_LINE_RE.match(l)]
        if not head_ok or not ledger_ok:
            status = worse(FAIL)
            detail.append("COORD.md header damaged (h1=%s, '## LEDGER'=%s)" % (head_ok, ledger_ok))
            fix = ("restore the COORD.md header block ('# COORD.md — session coordination "
                   "ledger' + the format line + '## LEDGER') — recap/compile parse from it")
        elif bad:
            status = worse(WARN)
            detail.append("COORD.md: %d/%d ledger lines unparseable (first: %s)"
                          % (len(bad), len(entries), bad[0][:70]))
            fix = fix or ("reshape the odd COORD.md lines to "
                          "'- [YYYY-MM-DD HH:MMZ] [lane] ask -> landed | evidence: ...'")
        else:
            detail.append("COORD.md: header intact · %d ledger lines parse" % len(entries))

    if t.coord_agents:
        seen += 1
        first = (read(t.coord_agents) or "").split("\n")[0]
        if "auto-written" in first and "SubagentStop" in first:
            detail.append("COORD-AGENTS.md: machine header intact")
        else:
            status = worse(FAIL)
            detail.append("COORD-AGENTS.md: machine header missing (first line: %s)" % first[:70])
            fix = fix or ("restore the COORD-AGENTS.md machine header — the hook appends blind "
                          "and the file is the agent audit index")

    if t.ledger:
        seen += 1
        sp = spend_py(t)
        if sp:
            rc, out = run([sys.executable, sp, "report", "--root", t.root])
            verdict = next((l.strip() for l in out.split("\n") if l.startswith("routing:")), "")
            if rc == 0:
                detail.append("spend/ledger.md: spend.py report clean (%s)" % (verdict or "exit 0"))
            elif rc == 4:
                status = worse(WARN)
                detail.append("spend/ledger.md: spend.py report exit 4 — the routing gate FIRED "
                              "(healthy instrument, real finding): %s" % (verdict or out.strip()[:120]))
                fix = fix or ("read the flagged ledger entries (/spend report) — a lane ran below "
                              "the seat on the wrong model; exit 4 is the gate working, not a bug")
            else:
                status = worse(FAIL)
                detail.append("spend/ledger.md: spend.py report exit %s — %s"
                              % (rc, out.strip().split("\n")[-1][:120]))
                fix = fix or ("repair spend/ledger.md by hand ONLY as a last resort — it is "
                              "append-only via spend.py; re-run 'spend.py report --root .' to see the parse error")
        else:
            lines = [l for l in (read(t.ledger) or "").split("\n") if l.strip()
                     and not l.startswith("#")]
            bad = [l for l in lines if not l.startswith("[")]
            detail.append("spend/ledger.md: %d entries, parsed textually (spend.py not found)"
                          % len(lines))
            if bad:
                status = worse(WARN)
                fix = fix or "check spend/ledger.md — %d lines are not ledger-shaped" % len(bad)

    if t.candidates:
        seen += 1
        obj, err = jload(t.candidates)
        if err:
            status = worse(FAIL)
            detail.append("compile/candidates.json is not valid JSON: %s" % err)
            fix = fix or ("re-run the scan (compile.py scan --root .) — candidates.json is "
                          "derived and safe to regenerate")
        else:
            detail.append("compile/candidates.json: valid · %d candidates"
                          % len((obj or {}).get("candidates", [])))

    if not seen:
        return SKIP, ["no estate files here (COORD.md / COORD-AGENTS.md / spend / compile)"], None
    return status, detail, fix


def check_install_freshness(t):
    man, _ = jload(t.manifest(t.primary))
    name = (man or {}).get("name")
    repo_v = (man or {}).get("version")
    if not name:
        return SKIP, ["no plugin name in the manifest"], None
    clone = os.path.expanduser("~/.claude/plugins/marketplaces/%s" % name)
    if not os.path.isdir(clone):
        return SKIP, ["no marketplace clone at ~/.claude/plugins/marketplaces/%s" % name], None

    clone_v = None
    for cand in (os.path.join(clone, "plugins", name, ".claude-plugin", "plugin.json"),
                 os.path.join(clone, ".claude-plugin", "marketplace.json")):
        obj, err = jload(cand)
        if not err and isinstance(obj, dict):
            clone_v = obj.get("version") or (obj.get("metadata") or {}).get("version")
            if clone_v:
                break

    installed_v = None
    inst, err = jload(os.path.expanduser("~/.claude/plugins/installed_plugins.json"))
    if not err and isinstance(inst, dict):
        rows = (inst.get("plugins") or {}).get("%s@%s" % (name, name)) or []
        if rows and isinstance(rows[0], dict):
            installed_v = rows[0].get("version")

    detail = ["repo=v%s · marketplace clone=v%s · installed=v%s"
              % (repo_v, clone_v, installed_v)]
    seen = [v for v in (clone_v, installed_v) if v]
    if not seen:
        return WARN, detail + ["neither the clone nor installed_plugins.json states a version"], \
            "claude plugin marketplace update %s && claude plugin update %s@%s" % (name, name, name)
    if all(v == repo_v for v in seen):
        return PASS, detail + ["installed build matches the repo"], None
    return WARN, detail + ["INSTALL DRIFT — the session is running a different build than this repo"], \
        ("claude plugin marketplace update %s && claude plugin update %s@%s   (then restart; the "
         "hook's git self-update no-ops on a marketplace-cache install)" % (name, name, name))


def check_gitignore(t):
    if not t.gitignore:
        return SKIP, ["no .gitignore at the target root"], None
    lines = [l.strip() for l in (read(t.gitignore) or "").split("\n")]
    rules = [l for l in lines if l and not l.startswith("#")]
    status, detail, fix = PASS, [], None

    for derived in ("graph", "compile"):
        anchored, unanchored = "/%s/" % derived, "%s/" % derived
        if anchored in rules:
            detail.append("%s present (anchored to the repo root)" % anchored)
        elif unanchored in rules:
            status = FAIL
            detail.append("UNANCHORED '%s' — gitignore matches at ANY depth, so this also ignores "
                          "the %s SKILL's own directory" % (unanchored, derived))
            fix = ("anchor the rule: change '%s' to '%s' in .gitignore — the unanchored form "
                   "silently un-tracks plugins/*/skills/%s/" % (unanchored, anchored, derived))
        else:
            status = WARN if status == PASS else status
            detail.append("no ignore rule for the derived %s/ output dir" % derived)
            fix = fix or "add '/%s/' to .gitignore (derived scan output, regenerated every run)" % derived

    tracked = []
    for p in t.plugins:
        for derived in ("graph", "compile"):
            d = os.path.join(p, "skills", derived)
            if os.path.isdir(d):
                tracked.append(d)
    if tracked:
        rc, _ = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=t.root)
        if rc == 0:
            for d in tracked:
                code, _ = run(["git", "check-ignore", "-q", os.path.relpath(d, t.root)], cwd=t.root)
                if code == 0:
                    status = FAIL
                    detail.append("IGNORED SKILL DIR: %s is matched by a gitignore rule" % t.rel(d))
                    fix = ("anchor the offending rule (leading '/') so it only matches the repo "
                           "root — %s must stay tracked" % t.rel(d))
                elif code == 1:
                    detail.append("%s tracked (not ignored)" % t.rel(d))
                else:
                    status = WARN if status == PASS else status
                    detail.append("could not determine ignore status for %s" % t.rel(d))
        else:
            detail.append("not a git work tree — skill-dir ignore probe SKIPPED")
    return status, detail, fix


def check_render_surfaces(t):
    if not t.html:
        return SKIP, ["no docs/oracle-skill-flow.html under this target"], None
    man, _ = jload(t.manifest(t.primary))
    version = (man or {}).get("version")
    stamps = re.findall(r"v\d+\.\d+\.\d+", read(t.html) or "")
    if not stamps:
        return WARN, ["%s carries no vX.Y.Z stamp" % t.rel(t.html)], \
            "stamp the render with v%s (header + footer) so staleness is visible" % version
    off = sorted(set(s for s in stamps if s != "v%s" % version))
    detail = ["%s: %d stamps, %s" % (t.rel(t.html), len(stamps), ", ".join(sorted(set(stamps))))]
    if off:
        return FAIL, detail + ["STALE STAMP: expected v%s, found %s" % (version, ", ".join(off))], \
            ("update the version stamps in %s (header + footer) to v%s — the rendered flow is a "
             "shipped surface and a stale stamp ships a lie" % (t.rel(t.html), version))
    return PASS, detail + ["matches plugin.json v%s" % version], None


CHECKS = [
    ("FRONTMATTER", check_frontmatter),
    ("MANIFESTS", check_manifests),
    ("SKILL COUNT", check_skill_count),
    ("HOOKS", check_hooks),
    ("ESTATE", check_estate),
    ("INSTALL FRESHNESS", check_install_freshness),
    ("GITIGNORE", check_gitignore),
    ("RENDER SURFACES", check_render_surfaces),
]


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="doctor.py",
        description="Health-check a notrest harness repo or an installed plugin dir. Reads only.")
    sub = ap.add_subparsers(dest="cmd")
    chk = sub.add_parser("check", help="run every check and report")
    chk.add_argument("--root", help="repo root (default: the git root of the cwd)")
    chk.add_argument("--plugin", help="an installed plugin dir instead of a repo")
    chk.add_argument("--json", action="store_true", help="machine output")
    args = ap.parse_args(argv)
    if args.cmd != "check":
        ap.print_usage(sys.stderr)
        sys.stderr.write("doctor: expected the 'check' subcommand\n")
        return EXIT_USAGE

    target, err = resolve(args)
    if err:
        if args.json:
            print(json.dumps({"error": err, "exit": EXIT_TARGET}, indent=1))
        else:
            sys.stderr.write("doctor: %s\n" % err)
        return EXIT_TARGET

    results = []
    for name, fn in CHECKS:
        try:
            status, detail, fix = fn(target)
        except Exception as exc:                      # a check must never take doctor down
            status, detail, fix = FAIL, ["check raised %s: %s" % (type(exc).__name__, exc)], \
                "report this — doctor's own check crashed, which is a doctor bug"
        results.append({"check": name, "status": status,
                        "detail": detail if isinstance(detail, list) else [detail], "fix": fix})

    counts = {s: sum(1 for r in results if r["status"] == s) for s in (PASS, WARN, FAIL, SKIP)}
    code = EXIT_FAIL if counts[FAIL] else (EXIT_WARN if counts[WARN] else EXIT_OK)
    verdict = ("UNHEALTHY" if counts[FAIL] else ("WARNINGS" if counts[WARN] else "HEALTHY"))
    summary = ("doctor: %s — %d checks · %d pass, %d warn, %d fail, %d skip (exit %d)"
               % (verdict, len(results), counts[PASS], counts[WARN], counts[FAIL],
                  counts[SKIP], code))

    if args.json:
        print(json.dumps({"root": target.root, "mode": target.mode, "verdict": verdict,
                          "checks": results, "counts": counts, "summary": summary,
                          "exit": code}, indent=1))
        return code

    print("doctor — %s (%s mode)" % (target.root, target.mode))
    for r in results:
        print("%-5s %-18s %s" % (r["status"], r["check"], r["detail"][0] if r["detail"] else ""))
        for extra in r["detail"][1:]:
            print("      %s" % extra)
        if r["fix"] and r["status"] in (WARN, FAIL):
            print("      fix: %s" % r["fix"])
    print(summary)
    return code


if __name__ == "__main__":
    sys.exit(main())
