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
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
EXIT_OK, EXIT_USAGE, EXIT_TARGET, EXIT_WARN, EXIT_FAIL = 0, 2, 3, 5, 6

# The always-on context every session pays for this plugin. Above this, the harness is
# taxing every session it rides in — the descriptions have to come back down.
# CALIBRATION LAW (2026-07-27): the ceiling catches OUR text growth, never the vendor's
# frame. The same unchanged tree measured ~3,515 under CLI 2.1.207 and ~5,127 under
# 2.1.220 (+~50/skill of platform listing overhead — verified per-component, text
# identical). Re-calibrate ONLY on a CLI-version frame change, with the receipt in the
# CHANGELOG; never raise it to absorb description bloat. Headroom target ≈ 70-90 tok.
ALWAYS_ON_CEILING = 5200
# How recent an estate write still counts as evidence a hook is firing.
LIVENESS_HOURS = 48

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


# ── runtime-surface helpers ───────────────────────────────────────────────────────────
def config_dir():
    """The Claude config root this machine is actually using ($CLAUDE_CONFIG_DIR wins)."""
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


def skills_dir_links():
    """Every symlink under <config>/skills -> [(link_path, resolved_target)].

    A symlink here is the in-place install: the CLI loads the linked directory as a
    plugin with no cache copy anywhere, so the running build IS a working tree."""
    base = os.path.join(config_dir(), "skills")
    out = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return out
    for n in names:
        p = os.path.join(base, n)
        if os.path.islink(p):
            out.append((p, os.path.realpath(p)))
    return out


def listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def installed_rows(name):
    """[(install_id, version)] for every installed plugin whose id is '<name>@...'."""
    inst, err = jload(os.path.join(config_dir(), "plugins", "installed_plugins.json"))
    if err or not isinstance(inst, dict):
        return []
    rows = []
    for key, entries in (inst.get("plugins") or {}).items():
        if key.split("@")[0] != name:
            continue
        for e in entries or []:
            if isinstance(e, dict):
                rows.append((key, e.get("version")))
    return rows


def installed_all():
    """[(install_id, version, install_path)] for EVERY installed plugin, whatever its name.

    installed_rows() is name-keyed by design — it answers 'has anything taken MY name'.
    That question is blind to a shadow that calls itself something else, which is half of
    T13: the verbs collide whether or not the names do. This is the verb-keyed view."""
    inst, err = jload(os.path.join(config_dir(), "plugins", "installed_plugins.json"))
    if err or not isinstance(inst, dict):
        return []
    rows = []
    for key, entries in (inst.get("plugins") or {}).items():
        for e in entries or []:
            if isinstance(e, dict):
                rows.append((key, e.get("version"), e.get("installPath")))
    return rows


def skill_names_at(plugin_dir):
    """The skill VERBS a plugin dir ships — <dir>/skills/<name>/SKILL.md.

    An absent path answers nothing rather than falling back to a RELATIVE 'skills' read of
    whatever directory doctor happens to be standing in."""
    if not plugin_dir:
        return set()
    base = os.path.join(plugin_dir, "skills")
    return set(n for n in listdir(base) if os.path.isfile(os.path.join(base, n, "SKILL.md")))


# ── the desktop app's provisioning store (a different estate from the CLI's) ───────────
def app_support_dirs():
    """Candidate roots for the DESKTOP APP's support dir. $CLAUDE_APP_SUPPORT_DIR wins —
    that is the seam the fixture uses to hand this check a machine of its own."""
    env = os.environ.get("CLAUDE_APP_SUPPORT_DIR")
    if env:
        return [env]
    home = os.path.expanduser("~")
    out = [os.path.join(home, "Library", "Application Support", "Claude"),  # macOS
           os.path.join(home, ".config", "Claude")]                        # linux
    if os.environ.get("APPDATA"):
        out.append(os.path.join(os.environ["APPDATA"], "Claude"))          # windows
    return out


def app_stores():
    """Every provisioning store on this machine — [] when the desktop app is not here."""
    return [s for s in (os.path.join(b, "local-agent-mode-sessions") for b in app_support_dirs())
            if os.path.isdir(s)]


# Both shapes were verified on a live machine (2026-07-27), not inferred:
#   <store>/<uuid>/<uuid>/rpm/<plugin_id>/      marketplace packs, indexed by rpm/manifest.json
#   <store>/skills-plugin/<uuid>/<uuid>/        the app's own bundled pack
APP_PACK_GLOBS = ((os.path.join("*", "*", "rpm", "*"), "rpm"),
                  (os.path.join("skills-plugin", "*", "*"), "skills-plugin"))


def app_packs(stores):
    """Every pack the desktop app has provisioned -> [{path,name,version,skills,hooks,shape}].

    READ ONLY, and deliberately so: this is another application's state. doctor reports it
    and never repairs it — there is no CLI verb that reaches this store, and writing into
    another app's files is not a health check."""
    packs, seen = [], set()
    for store in stores:
        for pattern, shape in APP_PACK_GLOBS:
            for d in sorted(glob.glob(os.path.join(store, pattern))):
                real = os.path.realpath(d)
                if real in seen or not os.path.isdir(d):
                    continue
                names = skill_names_at(d)
                if not names:
                    continue                      # manifest.json, artifacts, session dirs
                seen.add(real)
                meta, _ = jload(os.path.join(d, ".claude-plugin", "plugin.json"))
                meta = meta if isinstance(meta, dict) else {}
                packs.append({"path": d, "shape": shape,
                              "name": meta.get("name") or os.path.basename(d),
                              "version": meta.get("version"),
                              "skills": sorted(names),
                              "hooks": os.path.isfile(os.path.join(d, "hooks", "hooks.json"))})
    return packs


def head_version(t, manifest_path):
    """The plugin version as COMMITTED -> (version, note). Never guesses: if git cannot
    produce the manifest at HEAD the comparison is reported unread, not assumed equal."""
    rc, out = run(["git", "show", "HEAD:%s" % t.rel(manifest_path)], cwd=t.root)
    if rc != 0:
        first = (out or "").strip().split("\n")[0][:70]
        return None, first or "git could not read the manifest at HEAD"
    try:
        return (json.loads(out) or {}).get("version"), None
    except Exception as exc:
        return None, "the manifest at HEAD is not valid JSON: %s" % exc


STAMP_RE = re.compile(r"\[(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})Z\]")


def latest_stamp(path):
    """Newest '[YYYY-MM-DD HH:MMZ]' stamp in a file, as a naive-UTC datetime."""
    latest = None
    for m in STAMP_RE.finditer(read(path) or ""):
        try:
            dt = datetime.datetime(*[int(g) for g in m.groups()])
        except ValueError:
            continue
        if latest is None or dt > latest:
            latest = dt
    return latest


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


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
    def __init__(self, root, mode, plugins, primary, surface="auto"):
        self.root = root
        self.mode = mode              # "repo" | "plugin"
        self.plugins = plugins        # every plugin dir carrying a .claude-plugin/plugin.json
        self.primary = primary        # the plugin dir that owns the skills
        self.surface = self._surface(surface)
        self.marketplace = os.path.join(root, ".claude-plugin", "marketplace.json")
        if not os.path.isfile(self.marketplace):
            self.marketplace = None
        self.tutorial = self._first(os.path.join(root, "docs", "TUTORIAL.md"),
                                    os.path.join(primary or root, "docs", "TUTORIAL.md"))
        self.readme = self._first(os.path.join(root, "README.md"))
        self.inner_readme = self._first(os.path.join(primary, "README.md")) if primary else None
        self.html = self._first(os.path.join(root, "docs", "oracle-skill-flow.html"))
        self.gitignore = self._first(os.path.join(root, ".gitignore"))
        self.coord = self._first(os.path.join(root, "COORD.md"))
        self.coord_agents = self._first(os.path.join(root, "COORD-AGENTS.md"))
        self.ledger = self._first(os.path.join(root, "spend", "ledger.md"))
        self.candidates = self._first(os.path.join(root, "compile", "candidates.json"))

    def _surface(self, requested):
        if requested and requested != "auto":
            return requested
        # Mirrors establish.py's host-signal law (review round, 2026-09-01: this
        # sibling still carried the dead CLAUDE_PLUGIN_ROOT branch and file-tiebreak,
        # so THE SHIP GATE graded itself a codex host on a Claude machine — skipping
        # the Claude checks exactly when they are load-bearing). Claude signals that
        # actually exist; claude-preferred when both families appear (a stale codex
        # var must not flip the gate); the file tie-break only with no signal at all.
        claude = bool(os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_PID")
                      or any(k.startswith("CLAUDE_CODE_") for k in os.environ))
        codex = bool(os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SANDBOX"))
        if claude:
            return "claude"
        if codex:
            return "codex"
        if self.primary and os.path.isfile(os.path.join(self.primary, ".codex-plugin",
                                                        "plugin.json")):
            return "codex"
        return "claude"

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

    def codex_manifest(self, plugin_dir):
        return os.path.join(plugin_dir, ".codex-plugin", "plugin.json")


def resolve(args):
    if args.plugin:
        root = os.path.abspath(args.plugin)
        if not os.path.isdir(root):
            return None, "no such directory: %s" % root
        if not os.path.isfile(os.path.join(root, ".claude-plugin", "plugin.json")):
            return None, "%s is not a plugin dir (no .claude-plugin/plugin.json)" % root
        return Target(root, "plugin", [root], root, getattr(args, "surface", "auto")), None

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

    tmp = Target(root, "repo", plugins, plugins[0], getattr(args, "surface", "auto"))
    primary = max(plugins, key=lambda p: len(tmp.skill_dirs(p)))
    mk, _ = jload(tmp.marketplace) if tmp.marketplace else (None, None)
    if isinstance(mk, dict) and mk.get("name"):
        for p in plugins:
            man, _ = jload(os.path.join(p, ".claude-plugin", "plugin.json"))
            if isinstance(man, dict) and man.get("name") == mk.get("name"):
                primary = p
                break
    return Target(root, "repo", plugins, primary, getattr(args, "surface", "auto")), None


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
    detail, status, fix = [], PASS, None
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

    # The Codex package is a parallel adapter, never inferred from Claude compatibility.
    # A source tree at v4.3+ must carry the native manifest, and the base versions agree.
    cman = t.codex_manifest(t.primary)
    cobj, cerr = jload(cman) if os.path.isfile(cman) else (None, "absent")
    if cerr:
        status = FAIL
        detail.append("%s — native Codex manifest %s" % (t.rel(cman), cerr))
        fix = "add a valid .codex-plugin/plugin.json; do not claim Codex through Claude compatibility alone"
    else:
        cver = cobj.get("version")
        detail.append("%s = %s v%s" % (t.rel(cman), cobj.get("name"), cver))
        required = ("name", "version", "description", "author", "interface")
        absent = [k for k in required if not cobj.get(k)]
        if cobj.get("name") != name or cver != version or absent:
            status = FAIL
            detail.append("CODEX MANIFEST MISMATCH: name=%s version=%s missing=%s"
                          % (cobj.get("name"), cver, ",".join(absent) or "-"))
            fix = ("make .codex-plugin/plugin.json name/version match the Claude manifest "
                   "and include the required Codex interface fields")
        if "hooks" in cobj:
            status = FAIL
            detail.append("Codex manifest declares unsupported hooks — Claude lifecycle hooks do not run there")
            fix = "remove hooks from .codex-plugin/plugin.json and keep them in the Claude adapter"

    codex_market = os.path.join(t.root, ".agents", "plugins", "marketplace.json")
    if t.mode == "repo" and os.path.isfile(codex_market):
        cmk, cmerr = jload(codex_market)
        centry = next((e for e in (cmk or {}).get("plugins", [])
                       if isinstance(e, dict) and e.get("name") == name), None)
        if cmerr or not centry:
            status = FAIL
            detail.append("%s has no usable '%s' Codex entry" % (t.rel(codex_market), name))
            fix = "repair the repo-local Codex marketplace entry"
        else:
            policy = centry.get("policy") or {}
            source = centry.get("source") or {}
            good = (source.get("source") == "local" and
                    source.get("path") == "./plugins/%s" % os.path.basename(t.primary) and
                    policy.get("installation") in ("AVAILABLE", "INSTALLED_BY_DEFAULT") and
                    policy.get("authentication") in ("ON_INSTALL", "ON_USE") and
                    bool(centry.get("category")))
            detail.append("%s entry[%s] source=%s policy=%s/%s"
                          % (t.rel(codex_market), name, source.get("path"),
                             policy.get("installation"), policy.get("authentication")))
            if not good:
                status = FAIL
                fix = "repair source.path, policy, and category in the Codex marketplace entry"

    if t.marketplace is None:
        detail.append("no marketplace.json under this target — cross-manifest match SKIPPED")
        return status, detail, fix

    mk, err = jload(t.marketplace)
    if err:
        return FAIL, detail + ["%s is not valid JSON: %s" % (t.rel(t.marketplace), err)], \
            "repair the JSON (python3 -m json.tool .claude-plugin/marketplace.json)"

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


# M3: a bold-name cell in a markdown table row — `| **beam** | …` — which is the shape
# every roster table in this estate uses. The row is the promise; the dir is the delivery.
ROSTER_ROW_RE = re.compile(r"^\s*\|\s*\**`?([A-Za-z0-9][A-Za-z0-9._-]*)`?\**\s*\|", re.M)


def _names(text, name):
    """Is this skill NAMED here? Case-insensitive, bounded so `graph` does not match
    `graphs` and `oracle` DOES match the prose form ORACLE.

    F5 (refuter, 4.6.2): the trailing guard also rejected a HYPHEN, so the estate's own
    prose — "the mentor-dev ritual", "the oracle-suite core" — did not count as naming
    `mentor` or `oracle`, and the roster gate would have raised a FAIL against a README
    that names the skill perfectly well. A hyphen-joined suffix is still the name; a
    LETTER-joined one ("mentors", "graphs") is a different word. The leading guard keeps
    the hyphen, so "non-mentor" is not a mention of `mentor`."""
    return bool(re.search(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_])" % re.escape(name),
                          text or "", re.I))


def check_roster_parity(t):
    """M3: SKILL COUNT compares a NUMBER against a number, so a README that says
    thirty-two and lists twenty-nine passed the gate for five weeks (4.6.1 shipped
    beam/mentor/tieredswarm undiscoverable). This check compares the ROSTER against the
    dirs: every skill on disk must be NAMED on every shipped surface a reader browses.
    The README is held to the stricter bar — a table ROW, not a passing mention — because
    the README table IS the roster; the other three surfaces need only name it."""
    dirs = [os.path.basename(d) for d in t.skill_dirs(t.primary)]
    if not dirs:
        return SKIP, ["no skills/ dir under %s" % t.rel(t.primary)], None

    checks = []          # (label, missing_names) — a source absent from the tree is skipped
    absent_sources = []

    # In --plugin mode the root README IS the plugin's README; check it once, as prose.
    if t.readme and t.readme != t.inner_readme:
        txt = read(t.readme) or ""
        rows = set(n.lower() for n in ROSTER_ROW_RE.findall(txt))
        if rows:
            # This README carries a roster TABLE, so the table is the promise: a passing
            # mention in prose is not a row, and 4.6.1 shipped three skills that had one
            # and not the other. An estate whose README has no table at all is held to the
            # ordinary naming bar instead — the strict bar would be inventing a convention.
            checks.append(("%s table rows" % t.rel(t.readme),
                           [n for n in dirs if n.lower() not in rows]))
        else:
            checks.append(("%s (no roster table — naming bar only)" % t.rel(t.readme),
                           [n for n in dirs if not _names(txt, n)]))
    elif not t.readme:
        absent_sources.append("README.md")

    if t.inner_readme:
        txt = read(t.inner_readme)
        checks.append((t.rel(t.inner_readme), [n for n in dirs if not _names(txt, n)]))
    else:
        absent_sources.append("the plugin's own README.md")

    if t.marketplace:
        man, _ = jload(t.manifest(t.primary))
        mk, _ = jload(t.marketplace)
        entry = next((e for e in (mk or {}).get("plugins", [])
                      if isinstance(e, dict) and e.get("name") == (man or {}).get("name")), None)
        if entry:
            desc = entry.get("description", "")
            checks.append(("%s (%s entry description)" % (t.rel(t.marketplace),
                                                          (man or {}).get("name")),
                           [n for n in dirs if not _names(desc, n)]))
        else:
            absent_sources.append("the marketplace entry for this plugin")
    else:
        absent_sources.append("marketplace.json")

    if t.tutorial:
        txt = read(t.tutorial)
        checks.append((t.rel(t.tutorial), [n for n in dirs if not _names(txt, n)]))
    else:
        absent_sources.append("docs/TUTORIAL.md")

    if not checks:
        return SKIP, ["no roster surface found (%s)" % ", ".join(absent_sources)], None

    detail = ["%d skill dirs on disk" % len(dirs)]
    for label, missing in checks:
        detail.append("%s: %s" % (label, "names all %d" % len(dirs) if not missing
                                  else "MISSING %d — %s" % (len(missing), ", ".join(missing))))
    if absent_sources:
        detail.append("not present, not checked: %s" % ", ".join(absent_sources))

    short = [(l, m) for l, m in checks if m]
    if short:
        return FAIL, detail + ["ROSTER DRIFT: a shipped skill nobody can find is a skill "
                               "nobody ships"], \
            ("name %s in %s — the README needs a TABLE ROW (`| **<name>** | … |`), the other "
             "surfaces need the name in their prose"
             % (", ".join(sorted(set(n for _l, m in short for n in m))),
                ", ".join(l for l, _m in short)))
    return PASS, detail + ["every skill dir is named on every roster surface"], None


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

    # 4.6.3: the LEARNINGS LOOP, reported as a FACT — no new status. Doctor's job here is
    # to say what the estate holds; whether the loop is being HONOURED is eval's
    # LEARNING-LOOP check, which audits triggers against citations. A store with no
    # learnings is a young loop, not a sick install, and must never redden an install gate.
    store = os.path.join(t.root, "archive", "findings.jsonl")
    if os.path.isfile(store):
        seen = True
        total, newest = 0, None
        for line in (read(store) or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue                    # one bad line is not a broken store
            if not isinstance(rec, dict) or rec.get("kind") != "learning":
                continue
            total += 1
            ts = str(rec.get("ts", ""))
            if ts and (newest is None or ts > newest):
                newest = ts
        if not total:
            detail.append("learnings: 0 records — the loop is armed but nothing banked yet")
        else:
            age = "unknown age"
            try:
                dt = datetime.datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ")
                hrs = (utc_now() - dt).total_seconds() / 3600.0
                age = ("%.1fh ago" % hrs) if hrs < 48 else ("%.0fd ago" % (hrs / 24.0))
            except (TypeError, ValueError):
                pass
            detail.append("learnings: %d records, newest %s" % (total, age))

    if not seen:
        return SKIP, ["no estate files here (COORD.md / COORD-AGENTS.md / spend / compile)"], None
    return status, detail, fix


# ── the two ladders (T16) — a fix that names the rung it bottomed out at ──────────────
# THE RUNTIME LADDER (INSTALL FRESHNESS), four rungs, climbed in this order:
#   1 a runtime surface exists at all   2 the name is free   3 the surface resolves to
#   THIS tree   4 what runs here is what everyone else sees.
# THE SHADOW LADDER (both shadow findings), three rungs by WHERE the shadow lives:
#   1 exact name, CLI-installed   2 a different name carrying our verbs, CLI-installed
#   3 an app-side pack in the desktop app's store — no CLI verb reaches it.
# A status without a rung tells you something is wrong; the rung tells you which remedy
# is the right one, and they are not interchangeable (uninstall vs repoint vs commit vs a
# toggle in another application's panel).
RUNG = {1: "rung 1 of 4 (a runtime surface exists)",
        2: "rung 2 of 4 (the name is free)",
        3: "rung 3 of 4 (the surface resolves to THIS tree)",
        4: "rung 4 of 4 (what runs here is what everyone else sees)"}
SHADOW_RUNG = {1: "shadow ladder rung 1 of 3 (exact name, CLI-installed)",
               2: "shadow ladder rung 2 of 3 (a different name, the same verbs, CLI-installed)",
               3: "shadow ladder rung 3 of 3 (an app-side pack, not a CLI install)"}


def check_install_freshness(t):
    """Which build is the session actually running — and is it this one?

    Two worlds, two vocabularies, and doctor must never describe one in the other's
    words. skills-dir mode symlinks a working tree straight into <config>/skills, so
    there is no clone and no cache and the running build is whatever is on disk right
    now; cache mode copies a published version and the question becomes version drift.
    Naming the wrong surface was the original defect: the check read git state and
    reported it as 'marketplace clone=...'."""
    if t.surface == "codex":
        return check_codex_install_freshness(t)

    man, _ = jload(t.manifest(t.primary))
    name = (man or {}).get("name")
    tree_v = (man or {}).get("version")
    if not name:
        return SKIP, ["no plugin name in the manifest"], None

    primary_real = os.path.realpath(t.primary)
    links = skills_dir_links()
    in_place = [l for l in links if l[1] == primary_real]
    if in_place:
        status, detail, fix = freshness_skills_dir(t, name, tree_v, in_place[0])
    else:
        misdirected = [l for l in links if os.path.basename(l[0]) == name]
        if misdirected:
            link, target = misdirected[0]
            status, detail, fix = WARN, [
                "runtime=skills-dir(foreign tree) · tree=v%s · %s -> %s"
                % (tree_v, tilde(link), target),
                "the '%s' skills-dir link does NOT resolve to this repo (%s) — the session "
                "loads that other copy in place, so nothing checked here is what runs"
                % (name, primary_real)], \
                ("%s — the link points at another copy: ln -sfn %s %s   (then restart)"
                 % (RUNG[3], primary_real, link))
        else:
            status, detail, fix = freshness_cache(t, name, tree_v)

    return overlap_shadow(t, name, status, detail, fix)


def check_codex_install_freshness(t):
    """Read Codex's own plugin inventory. It proves the loaded id/version, not source-tree
    identity; that limit is stated instead of borrowing Claude's cache vocabulary."""
    obj, err = jload(t.codex_manifest(t.primary))
    if err or not isinstance(obj, dict):
        return FAIL, ["native Codex manifest unreadable: %s" % err], \
            "repair .codex-plugin/plugin.json, then reinstall the local plugin"
    name, tree_v = obj.get("name"), obj.get("version")
    rc, out = run(["codex", "plugin", "list"], timeout=45)
    if rc is None or rc != 0:
        return SKIP, ["Codex inventory unavailable — codex plugin list exit %s: %s"
                      % (rc, (out or "").strip()[:160])], None
    rows = [ln.strip() for ln in out.splitlines() if ln.strip().startswith(name + "@")]
    if not rows:
        return WARN, ["runtime=codex · tree=v%s · no installed '%s@…' row" % (tree_v, name)], \
            "install the repo-local Codex marketplace build, then start a new task"
    enabled = [ln for ln in rows if " installed, enabled " in ln]
    versions = []
    for ln in enabled:
        m = re.search(r"installed, enabled\s+([^\s]+)", ln)
        if m:
            versions.append(m.group(1))
    detail = ["runtime=codex · tree=v%s · installed rows: %s"
              % (tree_v, " | ".join(rows))]
    base_versions = [v.split("+", 1)[0] for v in versions]
    if tree_v in base_versions:
        detail.append("Codex inventory carries the same base version; start a new task after updates")
        return PASS, detail, None
    return WARN, detail + ["INSTALL DRIFT — no enabled Codex row matches base v%s" % tree_v], \
        "reinstall notrest from the confirmed local marketplace and start a new task"


def overlap_shadow(t, name, status, detail, fix):
    """T13, second half: a shadow that calls itself something else.

    The name-keyed question ('is anything installed as notrest?') answers only the case
    where the impostor wears our name. What actually shadows a session is the VERB: two
    plugins shipping skills/oracle collide whether or not their plugin names ever match.
    Reported as WARN and never FAIL — an overlapping install may be perfectly wanted; what
    is not acceptable is not knowing it is there."""
    ours = set()
    for p in t.plugins:
        ours.update(os.path.basename(d) for d in t.skill_dirs(p))
    if not ours:
        return status, detail, fix

    hits, selves = [], set(os.path.realpath(p) for p in t.plugins)
    for key, ver, path in installed_all():
        if key.split("@")[0] == name:
            continue                              # the exact-name case, already rung 2
        if path and os.path.realpath(path) in selves:
            continue                              # --plugin aimed AT an install is not a shadow
        shared = sorted(skill_names_at(path) & ours)
        if shared:
            hits.append((key, ver, shared))
    if not hits:
        return status, detail, fix

    for key, ver, shared in hits:
        detail.append("SHADOW CANDIDATE (by verbs, not by name) — %s v%s carries %d of this "
                      "tree's %d verbs: %s" % (key, ver or "?", len(shared), len(ours),
                                               ", ".join(shared)))
    ov_fix = ("%s — claude plugin uninstall %s%s if it is not wanted, or keep it knowingly and "
              "expect the verb to resolve twice; a name-keyed check never sees this one"
              % (SHADOW_RUNG[2], hits[0][0],
                 " (and %d other overlapping install(s))" % (len(hits) - 1) if len(hits) > 1 else ""))
    return WARN, detail, (fix + "  ·  " + ov_fix) if fix else ov_fix


def freshness_skills_dir(t, name, tree_v, link):
    """In-place mode: the runtime IS this tree, so the honest question is not 'is the
    install current' but 'does anyone else see what this session is running'."""
    link_path, target = link
    head_v, note = head_version(t, t.manifest(t.primary))
    status, fix = PASS, None
    detail = ["runtime=skills-dir(in-place) · tree=v%s · HEAD=v%s"
              % (tree_v, head_v or "unread"),
              "link %s -> %s" % (tilde(link_path), target)]

    shadow = installed_rows(name)
    if not shadow:
        detail.append("no installed plugin owns the name '%s' — the session loads this working "
                      "tree itself; no marketplace clone and no cache copy is read" % name)
    else:
        status = WARN
        detail.append("SHADOWED — %s is installed as %s, and an installed plugin outranks the "
                      "skills-dir copy, so this tree is NOT the build the session loaded"
                      % (", ".join("v%s" % v for _k, v in shadow),
                         ", ".join(k for k, _v in shadow)))
        fix = ("%s — the name is taken by an installed plugin: claude plugin uninstall %s   "
               "then restart (an installed plugin outranks the link, so until it is gone %s "
               "is ignored) · %s"
               % (RUNG[2], shadow[0][0], tilde(link_path), SHADOW_RUNG[1]))

    if head_v is None:
        detail.append("tree-vs-HEAD comparison UNREAD: %s" % note)
    elif head_v != tree_v:
        status = WARN
        detail.append("UNCOMMITTED RELEASE — the running tree says v%s, HEAD still says v%s"
                      % (tree_v, head_v))
        fix = fix or ("%s — the release is bumped but uncommitted: git add -A && git commit "
                      "(in skills-dir mode the session runs the WORKING TREE, so every reader "
                      "at HEAD sees a build that does not exist on this machine)" % RUNG[4])
    elif status == PASS:
        detail.append("tree and HEAD agree at v%s — the in-place runtime is the committed build"
                      % tree_v)
    return status, detail, fix


def freshness_cache(t, name, repo_v):
    clone = os.path.join(config_dir(), "plugins", "marketplaces", name)
    if not os.path.isdir(clone):
        return SKIP, ["%s: no skills-dir link and no marketplace clone at %s — nothing on "
                      "this machine claims to run %s" % (RUNG[1], tilde(clone), name)], None

    clone_v = None
    for cand in (os.path.join(clone, "plugins", name, ".claude-plugin", "plugin.json"),
                 os.path.join(clone, ".claude-plugin", "marketplace.json")):
        obj, err = jload(cand)
        if not err and isinstance(obj, dict):
            clone_v = obj.get("version") or (obj.get("metadata") or {}).get("version")
            if clone_v:
                break

    rows = installed_rows(name)
    installed_v = rows[0][1] if rows else None

    detail = ["runtime=marketplace-cache · repo=v%s · marketplace clone=v%s · installed=v%s"
              % (repo_v, clone_v, installed_v)]
    seen = [v for v in (clone_v, installed_v) if v]
    if not seen:
        return WARN, detail + ["neither the clone nor installed_plugins.json states a version"], \
            ("%s — the running version is UNREAD, so drift cannot be ruled out: claude plugin "
             "marketplace update %s && claude plugin update %s@%s"
             % (RUNG[4], name, name, name))
    if all(v == repo_v for v in seen):
        return PASS, detail + ["installed build matches the repo"], None
    return WARN, detail + ["INSTALL DRIFT — the session is running a different build than this repo"], \
        ("%s — the installed copy is not this repo: claude plugin marketplace update %s && "
         "claude plugin update %s@%s   (then restart; the hook's git self-update no-ops on a "
         "marketplace-cache install)" % (RUNG[4], name, name, name))


def check_shadow_appside(t):
    """The shadow doctor could not see: the DESKTOP APP's own provisioning store.

    Every other surface doctor reads belongs to the CLI — <config>/skills, the marketplace
    clone, installed_plugins.json. The desktop app provisions its own packs into a store
    the CLI never mentions, and a stale clone of THIS plugin (oracle-suite v2.13.0, 19 name
    collisions, four live hooks) served sessions out of it for a week while every CLI-side
    check reported healthy. Four shadow incidents paid for this check.

    WARN-GRADE BY CONSTRUCTION, never FAIL: it reports another application's state, which
    this repo does not control and doctor must not touch. A collision is a fact worth
    knowing, not a broken harness."""
    if t.surface == "codex":
        return SKIP, ["Claude desktop provisioning store is outside the Codex adapter"], None

    ours = set()
    for p in t.plugins:
        ours.update(os.path.basename(d) for d in t.skill_dirs(p))
    if not ours:
        return SKIP, ["no skills under this target — nothing an app-side pack could collide "
                      "with"], None

    stores = app_stores()
    if not stores:
        return SKIP, ["no desktop-app provisioning store on this machine (looked for "
                      "local-agent-mode-sessions under: %s) — this check is honestly silent "
                      "on a machine that does not run the desktop app"
                      % "; ".join(tilde(b) for b in app_support_dirs())], None

    packs = app_packs(stores)
    head = "%d app-side pack(s) in %d store(s) · this tree ships %d verbs · store: %s" \
           % (len(packs), len(stores), len(ours), "; ".join(tilde(s) for s in stores))
    if not packs:
        return SKIP, [head, "the store exists but holds no pack with a skills/ dir — nothing "
                            "to intersect"], None

    colliding = [(p, sorted(set(p["skills"]) & ours)) for p in packs]
    colliding = [(p, c) for p, c in colliding if c]
    if not colliding:
        return PASS, [head, "no app-side pack carries any of this tree's skill names"], None

    detail = [head]
    for p, c in colliding:
        detail.append("APP-SIDE SHADOW — pack '%s' v%s (%s shape) carries %d of this tree's "
                      "verbs and %s: %s"
                      % (p["name"], p["version"] or "?", p["shape"], len(c),
                         "REGISTERS HOOKS (hooks/hooks.json)" if p["hooks"]
                         else "registers no hooks", ", ".join(c)))
        detail.append("    at %s" % tilde(p["path"]))
    detail.append("provisioned is not proven active — the store records provisioning, not the "
                  "app's live per-pack toggle, so a pack disabled in the panel can still "
                  "appear here; doctor reports what the filesystem shows and nothing more")
    return WARN, detail, \
        ("%s — disable the pack in the desktop app's plugin panel, then start a fresh session. "
         "NO CLI VERB REACHES THIS STORE: `claude plugin uninstall` only knows the CLI's own "
         "installs, and doctor will not write into another application's files"
         % SHADOW_RUNG[3])


ALWAYS_ON_RE = re.compile(r"Always-on:\s*~?\s*([\d,]+)\s*tok", re.I)
SOURCE_RE = re.compile(r"^\s*Source:\s*(\S+)\s*$", re.M)


def check_token_budget(t):
    """The always-on context tax, read off the CLI that charges it.

    Every skill description is loaded into every session whether the skill fires or not.
    The number the CLI prints is the receipt; anything else is a guess, so when the CLI
    cannot be asked this check SKIPs and says which ids it tried."""
    if t.surface == "codex":
        return SKIP, ["Claude's always-on token receipt is not a Codex measurement; "
                      "Codex skill descriptions remain front-matter checked"], None
    man, _ = jload(t.manifest(t.primary))
    name = (man or {}).get("name")
    if not name:
        return SKIP, ["no plugin name in the manifest"], None
    if not shutil.which("claude"):
        return SKIP, ["the `claude` CLI is not on PATH — the always-on cost is unmeasurable "
                      "here (it is the CLI's number, never doctor's estimate)"], None

    attempts = [
        # The tree first: --plugin-dir loads THIS directory in place, so the number
        # describes what is being checked rather than whatever build is installed.
        (["claude", "--plugin-dir", t.primary, "plugin", "details", name],  # label = tree-read; the id form varies by CLI version
         "%s via --plugin-dir %s" % (name, t.rel(t.primary))),
        (["claude", "plugin", "details", "%s@skills-dir" % name], "%s@skills-dir" % name),
        (["claude", "plugin", "details", "%s@%s" % (name, name)], "%s@%s" % (name, name)),
        (["claude", "plugin", "details", name], name),
    ]
    tried = []
    for cmd, label in attempts:
        tried.append(label)
        _rc, out = run(cmd, cwd=t.root, timeout=60)
        m = ALWAYS_ON_RE.search(out or "")
        if not m:
            continue
        tokens = int(m.group(1).replace(",", ""))
        src = SOURCE_RE.search(out or "")
        _rcv, ver = run(["claude", "--version"], cwd=t.root, timeout=15)
        cli_ver = (ver or "").strip().split()[0] if (ver or "").strip() else "?"
        detail = ["always-on ~%s tok · ceiling %s · read from %s · cli %s"
                  % ("{:,}".format(tokens), "{:,}".format(ALWAYS_ON_CEILING),
                     src.group(1) if src else label, cli_ver)]
        if tokens > ALWAYS_ON_CEILING:
            return FAIL, detail + ["OVER BUDGET by %s tok — every session pays this before it "
                                   "does anything" % "{:,}".format(tokens - ALWAYS_ON_CEILING)], \
                "diet the fattest descriptions (see docs/CAPABILITIES.md)"
        return PASS, detail + ["%s tok of headroom under the ceiling"
                               % "{:,}".format(ALWAYS_ON_CEILING - tokens)], None

    return SKIP, ["no plugin id answered `claude plugin details` (tried: %s) — the plugin is "
                  "neither installed nor loadable from this tree" % "; ".join(tried)], None


HOOK_TAGGED_RE = re.compile(r"^- \[[^\]]*\]\s*\[hook\]", re.M)


def check_hooks_fired(t):
    """Liveness, not syntax. HOOKS proves the scripts exist and parse; nothing there
    proves one ever RAN. A hook that is wired, parses, and never fires is invisible —
    it leaves no error, no log, and no gap anyone notices. This looks for the marks a
    firing hook leaves on the estate. It is a heuristic and never FAILs: absence of a
    mark is absence of evidence (a fresh repo has none), not proof of a dead hook."""
    if t.surface == "codex":
        return SKIP, ["Codex v4.3 exposes no Claude lifecycle hooks; explicit harness "
                      "actions and instruments carry the discipline"], None
    if not t.coord and not t.coord_agents:
        return SKIP, ["no COORD.md / COORD-AGENTS.md here — nothing a hook would have "
                      "written to look at"], None

    detail, evidence = [], []

    if t.coord:
        tail = "\n".join((read(t.coord) or "").split("\n")[-200:])
        tagged = HOOK_TAGGED_RE.findall(tail)
        stamps = [m for m in STAMP_RE.finditer(tail)]
        newest = None
        for m in HOOK_TAGGED_RE.finditer(tail):
            s = STAMP_RE.search(tail[m.start():m.end() + 30])
            if s:
                newest = s.group(0)
        if tagged:
            evidence.append("coord-tag")
            detail.append("COORD.md tail(200 lines, %d stamped): %d [hook]-tagged line(s)%s"
                          % (len(stamps), len(tagged), ", newest %s" % newest if newest else ""))
        else:
            detail.append("COORD.md tail(200 lines): no [hook]-tagged line — the SessionStart / "
                          "SessionEnd writers have left no mark in the active volume")
    else:
        detail.append("no COORD.md — the [hook]-tag probe is SKIPPED")

    now = utc_now()
    pair = []
    for label, path in (("COORD-AGENTS.md", t.coord_agents), ("spend/ledger.md", t.ledger)):
        if not path:
            pair.append("%s absent" % label)
            continue
        stamp = latest_stamp(path)
        if stamp is None:
            pair.append("%s unstamped" % label)
            continue
        age = (now - stamp).total_seconds() / 3600.0
        pair.append("%s newest %sZ (%.1fh)" % (label, stamp.strftime("%Y-%m-%d %H:%M"), age))
        if 0 <= age <= LIVENESS_HOURS:
            pair[-1] += " FRESH"
    fresh = sum(1 for p in pair if p.endswith("FRESH"))
    if fresh >= 2:
        evidence.append("fresh-agent+spend-pair")
    detail.append(" · ".join(pair) + "  [window %dh]" % LIVENESS_HOURS)

    if evidence:
        return PASS, ["hooks look LIVE by heuristic (%s) — this is liveness evidence, not proof: "
                      "a mark on the estate means something wrote it, not that every hook fires"
                      % ", ".join(evidence)] + detail, None
    return WARN, ["no evidence any hook has FIRED — heuristic only, never a failure: a fresh "
                  "repo, a quiet 48h, or a hand-pruned COORD.md all look like this"] + detail, \
        ("run a session in this repo and re-check — if the marks still never appear, the hooks "
         "are wired but dead: check `claude plugin list` (a shadowed or unloaded plugin runs no "
         "hooks at all) rather than the scripts, which HOOKS already proved parse")


def check_gitignore(t):
    if not t.gitignore:
        return SKIP, ["no .gitignore at the target root"], None
    lines = [l.strip() for l in (read(t.gitignore) or "").split("\n")]
    rules = [l for l in lines if l and not l.startswith("#")]
    status, detail, fix = PASS, [], None

    for derived in ("graph", "compile"):
        anchored, unanchored = "/%s/" % derived, "%s/" % derived
        # A dir-wide anchored rule is one valid shape. The other is per-file rules for the
        # genuinely derived outputs — required when the dir also holds SOURCE (compile/<slug>/
        # runtimes are hand-built and must stay tracked). Either shape passes.
        per_file = [r for r in rules if r.startswith(anchored) and not r.endswith("/")]
        if anchored in rules:
            detail.append("%s present (anchored to the repo root)" % anchored)
        elif per_file:
            detail.append("%s derived-file rules present (%s) — dir holds source, so per-file is correct"
                          % (anchored, ", ".join(sorted(per_file))))
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

    # F6: the mirror-image defect. The rules above keep the SKILL dirs tracked; nothing
    # kept DERIVED output out of the package. A scan run from inside the plugin wrote
    # plugins/notrest/graph/{graph,river}.{html,json} — 125 KB the root-anchored /graph/
    # rule does not cover — and it shipped to every consumer for five weeks, referenced by
    # nothing. Derived output under a plugin dir is a packaging defect, so it FAILS here.
    rc, _ = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=t.root)
    if rc != 0:
        detail.append("not a git work tree — tracked-derived-output probe SKIPPED")
        return status, detail, fix
    shipped = []
    for p in t.plugins:
        for derived in ("graph", "compile"):
            rel = os.path.relpath(os.path.join(p, derived), t.root)
            code, out = run(["git", "ls-files", "-z", "--", rel], cwd=t.root)
            if code != 0:
                continue
            for f in [x for x in out.split("\0") if x]:
                if f.lower().endswith((".json", ".html")):
                    shipped.append(f)
    if shipped:
        status = FAIL
        detail.append("DERIVED OUTPUT SHIPPED: %d tracked file(s) under a plugin's derived "
                      "dir — %s" % (len(shipped), ", ".join(sorted(shipped)[:6])))
        fix = ("git rm -r the derived output (%s) and add an anchored rule "
               "('plugins/*/graph/', 'plugins/*/compile/candidates.*') to .gitignore — "
               "scan output is regenerated per run and must never ride in the package"
               % ", ".join(sorted(set(os.path.dirname(f) for f in shipped))))
    else:
        detail.append("no tracked derived graph/compile output under any plugin dir")
    return status, detail, fix


# M3/F3: "31-skill harness" — the render's own claim about how big the harness is.
# Digits or the spelled form ("thirty-one-skill"); WORD2NUM turns the word into a number.
#
# F7 (refuter, 4.6.2): unanchored, this reads ORDINARY PROSE as a count claim — "a one-skill
# install", "our two-skill starter kit" — and FAILs the render against the tree with a number
# nobody was claiming. So a count claim is only counted where the page ALREADY makes a
# version claim: the same text node the vX.Y.Z stamp lives in. That is exactly the shape the
# render uses ("v4.6.2 · 32-skill harness · …"), it is the element a release bump edits, and
# it is the only place the page speaks in its own voice about what it is. Prose elsewhere is
# prose. A page that states a count NOWHERE near a stamp is reported as not-stated, never
# guessed — a gate that invents the claim it checks is worse than no gate.
VERSION_STAMP_RE = re.compile(r"v\d+\.\d+\.\d+")
NSKILL_RE = re.compile(r"\b(\d{1,3}|[A-Za-z]+(?:-[A-Za-z]+)?)-skill\b", re.I)
TEXT_NODE_RE = re.compile(r"<[^>]*>")


def stamped_nodes(html):
    """Text nodes that carry a vX.Y.Z stamp — where the page speaks about itself."""
    return [n for n in TEXT_NODE_RE.split(html or "") if VERSION_STAMP_RE.search(n)]


def check_render_surfaces(t):
    if not t.html:
        return SKIP, ["no docs/oracle-skill-flow.html under this target"], None
    man, _ = jload(t.manifest(t.primary))
    version = (man or {}).get("version")
    html = read(t.html) or ""
    stamps = VERSION_STAMP_RE.findall(html)
    detail, status, fix = [], PASS, None

    if not stamps:
        status, fix = WARN, ("stamp the render with v%s (header + footer) so staleness is "
                             "visible" % version)
        detail.append("%s carries no vX.Y.Z stamp" % t.rel(t.html))
    else:
        off = sorted(set(x for x in stamps if x != "v%s" % version))
        detail.append("%s: %d stamps, %s"
                      % (t.rel(t.html), len(stamps), ", ".join(sorted(set(stamps)))))
        if off:
            status = FAIL
            detail.append("STALE STAMP: expected v%s, found %s" % (version, ", ".join(off)))
            fix = ("update the version stamps in %s (header + footer) to v%s — the rendered flow "
                   "is a shipped surface and a stale stamp ships a lie" % (t.rel(t.html), version))
        else:
            detail.append("matches plugin.json v%s" % version)

    # F3: the render also states a COUNT, and until 4.6.2 this check pinned only the
    # version — so the page shipped "31-skill harness" beside 32 skill dirs and passed.
    # A number in prose drifts exactly like a version stamp does; gate it the same way.
    n = len(t.skill_dirs(t.primary))
    claims = []
    for tok in NSKILL_RE.findall(" \n".join(stamped_nodes(html))):
        low = tok.lower()
        val = int(low) if low.isdigit() else WORD2NUM.get(low)
        if val is not None:
            claims.append((tok, val))
    if not claims:
        # R2 (review round, 4.6.2): anchoring the claim to the stamp's own text node made a
        # SILENT PASS possible — a template edit that wraps the count in its own element
        # ("… v1.0.0 — the <b>two-skill</b> harness") splits the two apart, the anchor finds
        # nothing, and the gate that exists to catch a stale count reports success. The
        # anchor stays (prose elsewhere is still prose), but its own blind spot is now
        # audible: if the page stamps a version and states no count beside it, say so.
        if stamps:
            status = WARN if status == PASS else status
            detail.append("render states no skill count beside its version stamp — the "
                          "count claim is unchecked (a count in its own element, or none "
                          "at all, both land here)")
            fix = (fix + " ; " if fix else "") + \
                ("state the count in the same element as the version stamp in %s "
                 "(e.g. 'v%s · %d-skill harness') so a release bump edits both at once, or "
                 "confirm the page deliberately states no count"
                 % (t.rel(t.html), version, n))
        else:
            detail.append("no version stamp, so no anchored count claim to check")
    else:
        wrong = sorted(set(tok for tok, val in claims if val != n))
        detail.append("render claims %s-skill · %d skill dirs on disk"
                      % ("/".join(sorted(set(tok for tok, _v in claims))), n))
        if wrong:
            status = FAIL
            detail.append("COUNT DRIFT: the render says %s-skill, the tree holds %d"
                          % (", ".join(wrong), n))
            fix = (fix + " ; " if fix else "") + \
                ("update the 'N-skill' phrase in %s to %d-skill — a rendered count is a claim "
                 "the reader believes" % (t.rel(t.html), n))
    return status, detail, fix


def _learn_index(t):
    """archivist's index.py, imported by path — the ONE home of the trigger rule. doctor
    reports loop health; it never re-implements what a trigger is."""
    if not t.primary:
        return None
    path = os.path.join(t.primary, "skills", "archivist", "scripts", "index.py")
    if not os.path.isfile(path):
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_notrest_archivist_index", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod if hasattr(mod, "trigger_report") else None
    except Exception:
        return None


def _reviewed(recs):
    """Ids the seat has already ruled on (accepted or rejected), read the append-only way:
    a ruling record names its target in the statement head and in `links`."""
    out = set()
    for r in recs:
        m = re.match(r"^(accepts|rejects)\s+([FLOA]-\d+)\b",
                     str(r.get("statement", "")), re.I)
        if m and m.group(2).upper() in (r.get("links") or []):
            out.add(m.group(2).upper())
    return out


def check_loop_health(t):
    """Is the learnings loop being FED, or has it quietly stopped?

    ⛔ WARN-GRADE, NEVER FAIL. A loop that is behind is a fact about how the estate is
    being worked, not a broken install — and doctor's exit code gates SHIPPING. eval's
    LEARNING-LOOP is the check with teeth; this one is the dashboard beside it. Four
    numbers, because each fails differently: uncited triggers (lessons bought and not
    banked), open questions by age (what we admitted and never went back to), learnings
    per week (whether anyone is still feeding it), and candidates drafted but undecided
    (work the compiler did that nobody ruled on).
    """
    store = os.path.join(t.root, "archive", "findings.jsonl")
    if not os.path.isfile(store):
        return SKIP, ["no archive/findings.jsonl — the loop has no store here"], None

    recs = []
    for line in (read(store) or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            recs.append(rec)
    superseded = set(r.get("id") for r in recs
                     if str(r.get("status", "")) in ("superseded", "refuted"))
    learns = [r for r in recs if r.get("kind") == "learning"]
    opens = [r for r in recs if r.get("kind") == "open" and r.get("id") not in superseded]

    status, detail, fix = PASS, [], None

    mod = _learn_index(t)
    uncited = untested = None
    if mod is not None:
        try:
            rep = mod.trigger_report(t.root)
            if rep.get("armed"):
                uncited = len(rep.get("uncited") or [])
                untested = len(rep.get("untested") or [])
        except BaseException:            # SystemExit included — index.py's die() raises it
            uncited = untested = None
    if uncited is None:
        detail.append("uncited triggers: not readable (index.py absent or the loop is "
                      "unarmed)")
    else:
        detail.append("uncited triggers: %d · untested admissions with no open record: %d"
                      % (uncited, untested))
        if uncited or untested:
            status = WARN
            fix = ("bank what the estate paid for: `index.py add --kind learning …` for a "
                   "trigger, `--kind open …` for an admission (eval's LEARNING-LOOP is the "
                   "gate; this line is the dashboard)")

    now = utc_now()
    if not opens:
        detail.append("open questions: none")
    else:
        ages, overdue = [], 0
        for r in opens:
            try:
                dt = datetime.datetime.strptime(str(r.get("ts", "")), "%Y-%m-%dT%H:%M:%SZ")
                ages.append((now - dt).days)
            except (TypeError, ValueError):
                pass
            rc = str(r.get("recheck", ""))
            if re.match(r"^\d{4}-\d{2}-\d{2}$", rc) and rc < now.strftime("%Y-%m-%d"):
                overdue += 1
        oldest = max(ages) if ages else 0
        detail.append("open questions: %d (oldest %dd) · %d past their recheck date"
                      % (len(opens), oldest, overdue))
        if overdue:
            status = WARN
            fix = fix or ("re-check the overdue open questions (`watch.py due`) — an open "
                          "record past its date is an admission ageing into folklore")

    proposed = [r for r in recs if str(r.get("status", "")) == "proposed"
                and r.get("id") not in _reviewed(recs)]
    if proposed:
        status = WARN if status == PASS else status
        detail.append("proposed: %d awaiting review — a lane's claim is not estate law "
                      "until `index.py accept <id>`" % len(proposed))
        fix = fix or ("review the lane proposals: `index.py learnings --include-proposed`, "
                      "then `index.py accept <id>` or `reject <id> --why '...'`")
    else:
        detail.append("proposed: none awaiting review")
    if not learns:
        detail.append("learnings: none banked — the loop is armed but unfed")
    else:
        stamps = []
        for r in learns:
            try:
                stamps.append(datetime.datetime.strptime(str(r.get("ts", "")),
                                                         "%Y-%m-%dT%H:%M:%SZ"))
            except (TypeError, ValueError):
                pass
        if stamps:
            span_days = max(1.0, (now - min(stamps)).total_seconds() / 86400.0)
            detail.append("learnings: %d banked · %.1f/week over %.0fd · newest %.1fh ago"
                          % (len(learns), len(stamps) / (span_days / 7.0), span_days,
                             (now - max(stamps)).total_seconds() / 3600.0))
        else:
            detail.append("learnings: %d banked (no readable timestamps)" % len(learns))

    if t.candidates:
        obj, err = jload(t.candidates)
        if err or not isinstance(obj, dict):
            detail.append("compile candidates: unreadable")
        else:
            cands = obj.get("candidates") or []
            drafted = [c for c in cands
                       if isinstance(c, dict) and str(c.get("status", "")).upper()
                       in ("DRAFTED", "PROPOSED")]
            detail.append("compile candidates: %d drafted/proposed but undecided"
                          % len(drafted))
            if drafted:
                status = WARN if status == PASS else status
                fix = fix or ("rule on the drafted compile candidates (`compile.py decide "
                              "--slug <s> --status ADOPTED|DECLINED`) — a draft nobody "
                              "ruled on is work already paid for and not used")
    else:
        detail.append("compile candidates: no candidates.json")
    return status, detail, fix


CHECKS = [
    ("FRONTMATTER", check_frontmatter),
    ("MANIFESTS", check_manifests),
    ("SKILL COUNT", check_skill_count),
    ("ROSTER PARITY", check_roster_parity),
    ("HOOKS", check_hooks),
    ("HOOKS FIRED", check_hooks_fired),
    ("ESTATE", check_estate),
    ("INSTALL FRESHNESS", check_install_freshness),
    ("SHADOW-APPSIDE", check_shadow_appside),
    ("TOKEN BUDGET", check_token_budget),
    ("LOOP HEALTH", check_loop_health),
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
    chk.add_argument("--surface", choices=("auto", "codex", "claude"), default="auto",
                     help="runtime surface to diagnose (default: detect host/native manifest)")
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
        print(json.dumps({"root": target.root, "mode": target.mode,
                          "surface": target.surface, "verdict": verdict,
                          "checks": results, "counts": counts, "summary": summary,
                          "exit": code}, indent=1))
        return code

    print("doctor — %s (%s mode, %s surface)" % (target.root, target.mode, target.surface))
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
