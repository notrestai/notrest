#!/usr/bin/env python3
"""eval — the harness's law-conformance suite.

Doctrine: a law that is well-encoded leaves a STATIC FINGERPRINT in the shipped
files. This suite checks the fingerprint, not the behavior. Pure stdlib, pure
read, target < 2 seconds, zero model tokens. Never repairs, never bumps.

Exit: 0 all pass · 5 warnings only · 6 any FAIL · 2 usage error.
"""

import argparse
import glob
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import time

# ---------------------------------------------------------------------------
# constraints
# ---------------------------------------------------------------------------
# Arrangement/contract skills: they seat a session, they do not produce output.
# Exempt from the worker contract (self-check + finishing-up) by construction.
CONTRACT_SKILLS = {"fable-mode", "fable-director", "oracle", "agentswarm", "game-forge"}
# Skills that make claims and therefore owe an honesty grammar.
CLAIM_SKILLS = {"researcher", "factcheck", "marketresearcher", "explainer",
                "decider", "recap", "watch", "draft"}
LABEL_RE = re.compile(r"\[(cited|recall|estimate|unverified|model-opinion)\]", re.I)
VERDICT_RE = re.compile(r"\b(CONFIRMED|REFUTED|PLAUSIBLE|UNVERIFIABLE|MISLEADING|DEAD-SOURCE)\b")
# A spawn of a CLAUDE subagent is what the offload policy binds. `run_in_background`
# alone is not evidence — Bash jobs and vendor bridges (gpt) share that parameter.
SPAWN_MARK = re.compile(r"subagent_type|Agent tool|agent\(|model:\s*\"?opus", re.I)
DOWNGRADE_RE = re.compile(r"model[\"']?\s*[:=]\s*[\"']?\s*(sonnet|haiku)", re.I)
FORK_RE = re.compile(r"subagent_type:\s*[\"']?fork", re.I)
FORKBAN_RE = re.compile(r"^.*\bfork\b.*$", re.I | re.M)
NEGATION_RE = re.compile(r"never|ban|forbid|not allowed|no fork", re.I)
LEDGER_WRITE_RE = re.compile(
    r"(write|append|add|log)[^.\n]{0,80}(COORD(-AGENTS)?\.md|spend/ledger\.md|the ledger)", re.I)
LEDGER_OK_RE = re.compile(r"append-only|never hand-edit|never hand edit|\.py\s+log|spend\.py", re.I)
LEDGER_BAD_RE = re.compile(r"(edit|modify|rewrite)\s+(the\s+)?(ledger|COORD)", re.I)
SLASH_RE = re.compile(r"[\"'\s(]/[a-z][a-z0-9-]{2,}")

SAFETY_LAWS = {
    "draft": ("a draft is never sent — sending is the owner's act",
              re.compile(r"never sent|is never sent|sending is the owner", re.I)),
    "watch": ("a dead source is never a refutation",
              re.compile(r"the source died,? the claim did not|DEAD-SOURCE[^\n]*not a refutation|"
                         r"dead source is (not|never) a refutation", re.I)),
    "compile": ("a compiled runtime never auto-installs",
                re.compile(r"never auto-install|nothing installs itself|never install", re.I)),
    "fable-director": ("the metered-key / tombstone pin scope is stated",
                       re.compile(r"tombstone|metered", re.I)),
}


class R:
    """One judgment: a law, the file evidence, and a fix hint."""

    def __init__(self, check, status, law, evidence, fix=""):
        self.check, self.status, self.law = check, status, law
        self.evidence, self.fix = evidence, fix

    def as_dict(self):
        return {"check": self.check, "status": self.status, "law": self.law,
                "evidence": self.evidence, "fix": self.fix}


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def lineno(text, match_start):
    return text.count("\n", 0, match_start) + 1


def rel(root, path):
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def frontmatter(text):
    """Minimal YAML front-matter reader. Returns (fields, raw_desc_line, quoted)."""
    if not text.startswith("---"):
        return {}, "", False
    end = text.find("\n---", 3)
    if end < 0:
        return {}, "", False
    block = text[3:end]
    fields, key, buf, raw_desc, quoted = {}, None, [], "", False
    for line in block.splitlines():
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            if key:
                fields[key] = "\n".join(buf).strip()
            key, val = m.group(1), m.group(2)
            buf = [val]
            if key == "description":
                raw_desc = val
                quoted = val[:1] in ('"', "'") or val[:1] in (">", "|")
        elif key:
            buf.append(line.strip())
    if key:
        fields[key] = "\n".join(buf).strip()
    return fields, raw_desc, quoted


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------
def locate(root):
    """Return (plugin_dir, {skill_name: (dir, SKILL.md text)})."""
    cand = os.path.join(root, "plugins", "notrest")
    if not os.path.isdir(os.path.join(cand, "skills")):
        cand = root
    sk_root = os.path.join(cand, "skills")
    skills = {}
    if os.path.isdir(sk_root):
        for name in sorted(os.listdir(sk_root)):
            d = os.path.join(sk_root, name)
            f = os.path.join(d, "SKILL.md")
            if os.path.isfile(f):
                skills[name] = (d, read(f))
    return cand, skills


# ---------------------------------------------------------------------------
# checks — each returns list[R]
# ---------------------------------------------------------------------------
def check_offload(root, plug, skills):
    ID = "OFFLOAD-POLICY"
    law = "every documented spawn names explicit opus; never sonnet/haiku; forks banned"
    out, spawners = [], []
    for name, (d, txt) in skills.items():
        f = rel(root, os.path.join(d, "SKILL.md"))
        # A line that names sonnet/haiku/fork alongside a negation IS the law,
        # not a breach of it. Only an unnegated directive is a violation.
        m = None
        for pat in (DOWNGRADE_RE, FORK_RE):
            for hit in pat.finditer(txt):
                bol = txt.rfind("\n", 0, hit.start()) + 1
                eol = txt.find("\n", hit.end())
                line = txt[bol:eol if eol > 0 else len(txt)]
                if not NEGATION_RE.search(line):
                    m = hit
                    break
            if m:
                break
        if m:
            out.append(R(ID, "FAIL", law, "%s:%d  %r" % (f, lineno(txt, m.start()),
                                                         m.group(0).strip()),
                         "replace with model: \"opus\"; forks inherit the seat model"))
            continue
        if SPAWN_MARK.search(txt):
            spawners.append(name)
            if not re.search(r"\bopus\b", txt, re.I):
                out.append(R(ID, "FAIL", law, "%s  (spawn directive, no model named)" % f,
                             "state model: \"opus\" on every spawn in this skill"))
            if "subagent_type" in txt:
                banned = any(NEGATION_RE.search(ln) for ln in FORKBAN_RE.findall(txt))
                if not banned:
                    out.append(R(ID, "FAIL", law, "%s  (writes subagent_type, no fork ban)" % f,
                                 "add: never subagent_type \"fork\" — forks inherit the seat model"))
    hook = os.path.join(plug, "hooks", "session-start.sh")
    if os.path.isfile(hook):
        if not re.search(r"\bopus\b", read(hook), re.I):
            out.append(R(ID, "FAIL", law, "%s  (SessionStart carries no opus rule)" % rel(root, hook),
                         "echo the offload policy in the SessionStart anchor"))
    else:
        out.append(R(ID, "SKIP", law, "no hooks/session-start.sh under %s" % rel(root, plug)))
    if not out:
        out.append(R(ID, "PASS", law, "%d spawn-documenting skills clean: %s"
                     % (len(spawners), ", ".join(spawners) or "-")))
    return out


def check_labels(root, _plug, skills):
    ID = "HONESTY-LABELS"
    law = "a skill that produces claims defines or uses a label/verdict grammar"
    out, seen = [], []
    for name in sorted(CLAIM_SKILLS):
        if name not in skills:
            out.append(R(ID, "SKIP", law, "skill %s not present" % name))
            continue
        d, txt = skills[name]
        f = rel(root, os.path.join(d, "SKILL.md"))
        if LABEL_RE.search(txt) or VERDICT_RE.search(txt):
            seen.append(name)
        else:
            out.append(R(ID, "FAIL", law, "%s  (no [cited]/[estimate]/verdict grammar)" % f,
                         "label every claim: [cited]/[recall]/[estimate]/[unverified]"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%d claim-making skills carry a grammar: %s"
                        % (len(seen), ", ".join(seen))))
    return out


def check_scripts(root, _plug, skills):
    ID = "SCRIPT-OWNS-SCANNING"
    law = "a shipped script is referenced by its SKILL.md and compiles (the zero-token claim)"
    out, ok = [], []
    tmp = os.path.join(tempfile.gettempdir(), "notrest-eval-pyc")
    # Citations cross skills (`<skill>/scripts/spend.py`), so a cited script is
    # satisfied by any skill in the tree shipping it — but by nothing less.
    shipped = set()
    for _n, (d, _t) in skills.items():
        sd = os.path.join(d, "scripts")
        if os.path.isdir(sd):
            shipped.update(os.listdir(sd))
    for name, (d, txt) in skills.items():
        sdir = os.path.join(d, "scripts")
        f = rel(root, os.path.join(d, "SKILL.md"))
        # A cited-but-absent scanner is the worst case: the economics claim is
        # made and nothing backs it.
        for ref in sorted(set(re.findall(r"scripts/([A-Za-z0-9_.-]+\.py)", txt))):
            if ref not in shipped:
                out.append(R(ID, "FAIL", law, "%s  (cites scripts/%s — no skill ships it)" % (f, ref),
                             "ship the script or stop citing it"))
        if not os.path.isdir(sdir):
            continue
        for fn in sorted(os.listdir(sdir)):
            p = os.path.join(sdir, fn)
            if not os.path.isfile(p):
                continue
            referenced = fn in txt
            if fn.endswith(".py"):
                if not referenced:
                    out.append(R(ID, "FAIL", law, "%s  (never names scripts/%s)" % (f, fn),
                                 "cite the script path in SKILL.md or delete the script"))
                    continue
                try:
                    py_compile.compile(p, cfile=os.path.join(tmp, fn + "c"), doraise=True)
                    ok.append("%s/%s" % (name, fn))
                except (py_compile.PyCompileError, OSError) as exc:
                    out.append(R(ID, "FAIL", law, "%s  (py_compile failed)" % rel(root, p),
                                 str(exc).splitlines()[0][:120]))
            elif not referenced:
                out.append(R(ID, "WARN", law, "%s  (ships scripts/%s, never names it)" % (f, fn),
                             "name it in SKILL.md so the reader can run it"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%d python scanners referenced + compiling: %s"
                        % (len(ok), ", ".join(ok))))
    return out


def check_estate(root, _plug, skills):
    ID = "ESTATE-WRITE"
    law = "estate ledgers are append-only or script-routed; machine files are never hand-edited"
    out, ok = [], []
    for name, (d, txt) in sorted(skills.items()):
        f = rel(root, os.path.join(d, "SKILL.md"))
        bad = LEDGER_BAD_RE.search(txt)
        if bad and not re.search(r"never\s+(edit|modify|rewrite)", txt[max(0, bad.start() - 40):bad.end()], re.I):
            out.append(R(ID, "FAIL", law, "%s:%d  %r" % (f, lineno(txt, bad.start()),
                                                         bad.group(0).strip()),
                         "ledgers are append-only — route the write through the script"))
            continue
        w = LEDGER_WRITE_RE.search(txt)
        if w:
            if LEDGER_OK_RE.search(txt):
                ok.append(name)
            else:
                out.append(R(ID, "FAIL", law, "%s:%d  %r" % (f, lineno(txt, w.start()),
                                                             w.group(0).strip()),
                             "say append-only, or route the write through the owning script"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%d estate-writing skills declare append-only/script-routed: %s"
                        % (len(ok), ", ".join(ok) or "-")))
    return out


def check_selfcheck(root, _plug, skills):
    ID = "WORKER-CONTRACT"
    law = "every worker skill ships a self-check section and a finishing-up/chains section"
    out, ok = [], []
    sc = re.compile(r"^#+ .*self-?check", re.I | re.M)
    fin = re.compile(r"^#+ .*(finishing up|chains|hand it over)", re.I | re.M)
    for name, (d, txt) in sorted(skills.items()):
        if name in CONTRACT_SKILLS:
            continue
        f = rel(root, os.path.join(d, "SKILL.md"))
        worker = "dossier" in txt.lower() or os.path.isdir(os.path.join(d, "scripts"))
        if not worker:
            continue
        miss = []
        if not sc.search(txt):
            miss.append("self-check")
        if not fin.search(txt) and "dossier" in txt.lower():
            miss.append("finishing-up/chains")
        if miss:
            out.append(R(ID, "FAIL", law, "%s  (missing: %s)" % (f, ", ".join(miss)),
                         "add '## Self-check before finishing' and '## Finishing up'"))
        else:
            ok.append(name)
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%d worker skills carry both sections" % len(ok)))
    return out


def check_triggers(root, _plug, skills):
    ID = "TRIGGER-SANITY"
    law = "front-matter has name == dir, a description YAML accepts, and a /slash trigger"
    out, ok = [], []
    for name, (d, txt) in sorted(skills.items()):
        f = rel(root, os.path.join(d, "SKILL.md"))
        fields, raw, quoted = frontmatter(txt)
        if not fields.get("name"):
            out.append(R(ID, "FAIL", law, "%s  (no name in front-matter)" % f,
                         "add 'name: %s'" % name))
            continue
        if fields["name"] != name:
            out.append(R(ID, "FAIL", law, "%s  (name %r != directory %r)"
                         % (f, fields["name"], name), "rename the directory or the name field"))
            continue
        desc = fields.get("description", "")
        if not desc:
            out.append(R(ID, "FAIL", law, "%s  (no description)" % f, "add a quoted description"))
            continue
        if not quoted and ": " in raw:
            out.append(R(ID, "FAIL", law, "%s  (unquoted description contains ': ' — YAML kills it)" % f,
                         "wrap the description scalar in double quotes"))
            continue
        if not SLASH_RE.search(" " + desc):
            out.append(R(ID, "FAIL", law, "%s  (description names no /slash trigger)" % f,
                         "add the explicit \"/%s\" trigger to the description" % name))
            continue
        ok.append(name)
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%d skills: name matches dir, description safe + /triggered"
                        % len(ok)))
    return out


def check_safety(root, _plug, skills):
    ID = "SAFETY-LAWS"
    out, ok = [], []
    for name, (statement, pat) in sorted(SAFETY_LAWS.items()):
        if name not in skills:
            out.append(R(ID, "SKIP", statement, "skill %s not present" % name))
            continue
        d, txt = skills[name]
        f = rel(root, os.path.join(d, "SKILL.md"))
        if pat.search(txt):
            ok.append(name)
        else:
            out.append(R(ID, "FAIL", statement, "%s  (law not stated in the shipped text)" % f,
                         "state the law verbatim in %s/SKILL.md: %s" % (name, statement)))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", "the named safety laws are present in the shipped text",
                        "%d laws held: %s" % (len(ok), ", ".join(ok))))
    return out


def check_hooks(root, plug, _skills):
    ID = "HOOK-CONTRACT"
    law = "hooks are silent-on-failure: no set -e, always exit 0; hooks.json points at real files"
    out, ok = [], []
    hdir = os.path.join(plug, "hooks")
    if not os.path.isdir(hdir):
        return [R(ID, "SKIP", law, "no hooks/ under %s" % rel(root, plug))]
    for fn in sorted(os.listdir(hdir)):
        if not fn.endswith(".sh"):
            continue
        p = os.path.join(hdir, fn)
        txt = read(p)
        m = re.search(r"^\s*set -e", txt, re.M)
        if m:
            out.append(R(ID, "FAIL", law, "%s:%d  'set -e' aborts the hook mid-write"
                         % (rel(root, p), lineno(txt, m.start())),
                         "drop set -e — a hook must never break the session"))
            continue
        tail = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if not tail or tail[-1] != "exit 0":
            out.append(R(ID, "FAIL", law, "%s  (last statement is %r, not 'exit 0')"
                         % (rel(root, p), tail[-1] if tail else ""),
                         "end the script with 'exit 0'"))
            continue
        ok.append(fn)
    hj = os.path.join(hdir, "hooks.json")
    if os.path.isfile(hj):
        try:
            blob = json.loads(read(hj))
            cmds = re.findall(r"hooks/([A-Za-z0-9._-]+)", json.dumps(blob))
            for c in sorted(set(cmds)):
                if not os.path.isfile(os.path.join(hdir, c)):
                    out.append(R(ID, "FAIL", law, "%s  (references hooks/%s — missing)"
                                 % (rel(root, hj), c), "ship the script or drop the entry"))
        except ValueError as exc:
            out.append(R(ID, "FAIL", law, "%s  (invalid JSON: %s)" % (rel(root, hj), exc),
                         "fix the JSON — the harness silently loads no hooks otherwise"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%d hooks silent-on-failure + wired: %s"
                        % (len(ok), ", ".join(ok))))
    return out


# A citation is judged against the CITING skill's own directory only when it is written
# bare. `<spend-skill>/scripts/spend.py` and `${CLAUDE_PLUGIN_ROOT}/skills/graph/scripts/
# graph.py` are deliberate cross-skill references and the leading path says so, so the
# lookbehind drops anything already carrying a path prefix.
CITE_RE = re.compile(r"(?<![A-Za-z0-9_./-])(references|scripts)/([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)")


def check_references(root, _plug, skills):
    ID = "REFERENCES-CITED"
    law = "every bare references/ or scripts/ path a SKILL.md cites exists in that skill's own dir"
    out, ok = [], 0
    # what the whole tree ships, so an attributed cross-skill citation can be resolved
    # instead of guessed at
    owners = {}
    for name, (d, _t) in skills.items():
        for sub in ("references", "scripts"):
            base = os.path.join(d, sub)
            for dirpath, dirnames, filenames in os.walk(base):
                for fn in list(dirnames) + filenames:
                    p = os.path.join(dirpath, fn)
                    owners.setdefault(os.path.relpath(p, d), set()).add(name)

    for name, (d, txt) in sorted(skills.items()):
        f = rel(root, os.path.join(d, "SKILL.md"))
        seen = set()
        for m in CITE_RE.finditer(txt):
            cited = ("%s/%s" % (m.group(1), m.group(2))).rstrip("/.")
            if cited in seen:
                continue
            seen.add(cited)
            # .py scanners are SCRIPT-OWNS-SCANNING's ground; two checks firing on one
            # defect turns a precise report into a pile.
            if cited.endswith(".py"):
                continue
            local = os.path.join(d, cited)
            if os.path.exists(local):
                ok += 1
                continue
            elsewhere = sorted(owners.get(cited, set()) - {name})
            line_start = txt.rfind("\n", 0, m.start()) + 1
            line_end = txt.find("\n", m.end())
            line = txt[line_start:line_end if line_end > 0 else len(txt)]
            if elsewhere and any(o in line for o in elsewhere):
                ok += 1                      # attributed cross-skill citation: honest
            elif elsewhere:
                out.append(R(ID, "WARN", law, "%s:%d  cites %s — it ships in %s, not here"
                             % (f, lineno(txt, m.start()), cited, "/".join(elsewhere)),
                             "name the owning skill on that line, or the reader opens the "
                             "wrong directory"))
            else:
                out.append(R(ID, "FAIL", law, "%s:%d  cites %s — no such file under %s/"
                             % (f, lineno(txt, m.start()), cited, name),
                             "ship the file or stop citing it — a cited path that does not "
                             "exist is a promise the skill cannot keep"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%d cited reference/script path(s) resolve" % ok))
    return out


ROUTE_RE = re.compile(r"\bSKILL=([a-z][a-z0-9-]*)")


def check_router(root, plug, skills):
    ID = "ROUTER"
    law = "the routing law has an enforcer: router.sh is wired to UserPromptSubmit and every verb it emits exists"
    out = []
    hdir = os.path.join(plug, "hooks")
    hj = os.path.join(hdir, "hooks.json")
    if not os.path.isfile(hj):
        return [R(ID, "SKIP", law, "no hooks/hooks.json under %s" % rel(root, plug))]
    # (a) registered under UserPromptSubmit — not merely present on disk
    try:
        blob = json.loads(read(hj))
        ups = json.dumps((blob.get("hooks") or {}).get("UserPromptSubmit", []))
    except (ValueError, AttributeError) as exc:
        return [R(ID, "FAIL", law, "%s  (unreadable: %s)" % (rel(root, hj), exc),
                  "fix hooks.json — an unloadable manifest silently wires nothing")]
    if "hooks/router.sh" not in ups:
        out.append(R(ID, "FAIL", law, "%s  (UserPromptSubmit does not run hooks/router.sh)" % rel(root, hj),
                     "register router.sh under UserPromptSubmit alongside coord-nudge.sh"))
    # (b) the script itself: exists, parses, silent-on-failure
    rs = os.path.join(hdir, "router.sh")
    if not os.path.isfile(rs):
        out.append(R(ID, "FAIL", law, "%s  (no router.sh — the routing law has no enforcer)" % rel(root, hdir),
                     "ship hooks/router.sh"))
        return out
    txt = read(rs)
    proc = subprocess.run(["bash", "-n", rs], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        out.append(R(ID, "FAIL", law, "%s  (bash -n rejects it)" % rel(root, rs),
                     proc.stdout.decode("utf-8", "replace").strip().splitlines()[0][:120]
                     if proc.stdout else "syntax error"))
    m = re.search(r"^\s*set -e", txt, re.M)
    if m:
        out.append(R(ID, "FAIL", law, "%s:%d  'set -e' aborts the router mid-prompt"
                     % (rel(root, rs), lineno(txt, m.start())),
                     "drop set -e — the router must never break a prompt"))
    tail = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not tail or tail[-1] != "exit 0":
        out.append(R(ID, "FAIL", law, "%s  (last statement is %r, not 'exit 0')"
                     % (rel(root, rs), tail[-1] if tail else ""),
                     "end the router with 'exit 0'"))
    # (c) every verb the table can emit is a skill that exists
    routes = sorted(set(ROUTE_RE.findall(txt)))
    if not routes:
        out.append(R(ID, "FAIL", law, "%s  (no SKILL= routing table found)" % rel(root, rs),
                     "keep the table a plain case chain with SKILL=<name> arms — greppable is checkable"))
    for name in routes:
        if name not in skills:
            out.append(R(ID, "FAIL", law, "%s  (routes to /notrest:%s — no such skill dir)"
                         % (rel(root, rs), name),
                         "fix the arm or ship skills/%s" % name))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "router.sh wired to UserPromptSubmit; %d verbs all exist: %s"
                        % (len(routes), ", ".join(routes))))
    return out


# ---------------------------------------------------------------------------
# the routing table has TWO authorities: hooks/router.sh (what the prompt hook
# fires) and skills/oracle/SKILL.md's routing bullet (what the intake tells the
# user). Two authorities that drift are worse than one — the user is told one
# thing and nudged another.
# ---------------------------------------------------------------------------
ROUTE_PAIR_RE = re.compile(r"\bSKILL=([a-z][a-z0-9-]*)\s*;\s*SHAPE=([a-z][a-z0-9-]*)")
ORACLE_BULLET_RE = re.compile(r"^-\s*\*\*Route to the right tool.*$", re.M | re.I)
ORACLE_VERB_RE = re.compile(r"`/([a-z][a-z0-9-]*)`")
SHAPE_LINE_RE = re.compile(r"^\*\*Router shape:\*\*[ \t]*`?([a-z][a-z0-9-]*)`?", re.M)


def rel_p(root, p):
    return rel(root, p)


def body_of(txt):
    """SKILL.md minus its front matter. A law has to be stated in the BODY — the
    description is a trigger, not a place a reader goes looking for the contract."""
    if txt.startswith("---"):
        end = txt.find("\n---", 3)
        if end >= 0:
            nl = txt.find("\n", end + 1)
            return txt[nl + 1:] if nl >= 0 else ""
    return txt


def check_route_parity(root, plug, skills):
    ID = "ROUTE-TABLE-PARITY"
    law = ("router.sh and oracle's routing bullet name the SAME verbs, and every routed "
           "skill acknowledges the shape that reaches it")
    rs = os.path.join(plug, "hooks", "router.sh")
    if not os.path.isfile(rs):
        return [R(ID, "SKIP", law, "no hooks/router.sh under %s" % rel(root, plug))]
    if "oracle" not in skills:
        return [R(ID, "SKIP", law, "no skills/oracle — no second authority to hold it to")]
    rtxt, out = read(rs), []
    od, otxt = skills["oracle"]
    of = rel(root, os.path.join(od, "SKILL.md"))
    m = ORACLE_BULLET_RE.search(otxt)
    if not m:
        return [R(ID, "FAIL", law,
                  "%s  (no '**Route to the right tool:**' bullet — the mirror is gone)" % of,
                  "restore the routing bullet: it is the table's second authority, and "
                  "without it the router answers to nothing")]
    bullet, bline = m.group(0), lineno(otxt, m.start())
    shapes = dict(ROUTE_PAIR_RE.findall(rtxt))
    routed = set(ROUTE_RE.findall(rtxt))
    named = set(ORACLE_VERB_RE.findall(bullet))
    for name in sorted(routed - named):
        hit = re.search(r"\bSKILL=%s\b" % re.escape(name), rtxt)
        out.append(R(ID, "FAIL", law,
                     "%s:%d  routes to /notrest:%s — oracle's routing bullet never names it"
                     % (rel(root, rs), lineno(rtxt, hit.start()) if hit else 0, name),
                     "add `/%s` to the routing bullet at %s:%d" % (name, of, bline)))
    for name in sorted(named - routed):
        out.append(R(ID, "FAIL", law,
                     "%s:%d  names /%s — router.sh has no arm that can emit it"
                     % (of, bline, name),
                     "add the router arm, or drop /%s from the bullet — a route the intake "
                     "promises and the hook never fires is half a law" % name))
    # G9: the destination acknowledges the shape that lands on it, in its own body.
    ack = []
    for name in sorted(routed):
        if name not in skills:
            continue              # a verb with no skill dir is ROUTER's finding, not this one
        d, txt = skills[name]
        f = rel(root, os.path.join(d, "SKILL.md"))
        sm = SHAPE_LINE_RE.search(body_of(txt))
        if not sm:
            out.append(R(ID, "FAIL", law,
                         "%s  (routed as %s — no '**Router shape:**' line in the body)"
                         % (f, shapes.get(name, "?")),
                         "add a body line: **Router shape:** `%s`" % shapes.get(name, "<shape>")))
        elif name in shapes and sm.group(1) != shapes[name]:
            out.append(R(ID, "WARN", law,
                         "%s  (acknowledges %r; router.sh sends %r)"
                         % (f, sm.group(1), shapes[name]),
                         "match the shape token to the router arm exactly"))
        else:
            ack.append(name)
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law,
                        "%d verbs agree across router.sh and %s; %d acknowledge their shape: %s"
                        % (len(routed), of, len(ack), ", ".join(ack) or "-")))
    return out


# A recorded route is a claim about where work WENT. Downstream evidence is what turns
# it into a fact. WARN-grade on purpose: the ledger is a trail written by humans and
# lanes mid-flight, and a gate that fails on an unfinished sentence would be lied to
# rather than obeyed.
ROUTE_MENTION_RE = re.compile(r"routed to /(?:notrest:)?([a-z][a-z0-9-]*)", re.I)
ROUTE_NEG_RE = re.compile(r"\b(not|never|no|instead of|rather than|declined?|skipp?ed|"
                          r"without|overrode|overrid\w+|refused?)\b", re.I)
LEDGER_LINE_RE = re.compile(r"^-\s*\[")
GRACE_LINES = 3


def _names(text, name):
    return bool(re.search(r"\b%s\b" % re.escape(name), text, re.I))


def check_route_conformance(root, _plug, _skills):
    ID = "ROUTE-CONFORMANCE"
    law = ("a route the estate RECORDED left downstream evidence — the ledger says where the "
           "work landed, not only where it was sent")
    live = os.path.join(root, "COORD.md")
    try:
        sources = [os.path.join(root, fn) for fn in sorted(os.listdir(root))
                   if fn.startswith("COORD") and fn.endswith(".md") and fn != "COORD-AGENTS.md"]
    except OSError:
        sources = []
    if not sources:
        return [R(ID, "SKIP", law, "no COORD*.md ledger at the root — no routes recorded")]
    agents = read(os.path.join(root, "COORD-AGENTS.md"))
    findings = read(os.path.join(root, "archive", "findings.jsonl"))
    live_txt = read(live)
    out, seen = [], 0
    for path in sources:
        lines = read(path).splitlines()
        ledger = [i for i, ln in enumerate(lines) if LEDGER_LINE_RE.match(ln)]
        # the newest 3 ledger lines are in flight: a lane routed 40 seconds ago has not
        # landed anything yet, and warning about it would train the reader to ignore this.
        cutoff = (ledger[-GRACE_LINES] if len(ledger) >= GRACE_LINES else -1) \
            if os.path.abspath(path) == os.path.abspath(live) else -1
        for i, ln in enumerate(lines):
            if cutoff >= 0 and i >= cutoff:
                continue
            for m in ROUTE_MENTION_RE.finditer(ln):
                name = m.group(1).lower()
                # "not routed to /x", "skipped the route to /x" — the law being applied
                # deliberately is exactly what fable-mode Hard Rule 12 allows.
                if ROUTE_NEG_RE.search(ln[max(0, m.start() - 48):m.start()]):
                    continue
                seen += 1
                later = "\n".join(lines[i + 1:])
                if os.path.abspath(path) != os.path.abspath(live):
                    later += "\n" + live_txt          # a sealed volume's "later" is the live ledger
                if (_names(later, name)
                        or re.search(r'"skill"\s*:\s*"%s"' % re.escape(name), findings, re.I)
                        or _names(agents, name)):
                    continue
                out.append(R(ID, "WARN", law,
                             "%s:%d  routed to /%s — no later ledger line, findings record, or "
                             "agent entry names %s" % (rel(root, path), i + 1, name, name),
                             "append what landed (or say it was deliberately skipped) — a route "
                             "with no landing is a claim the estate cannot back"))
    if not seen:
        return [R(ID, "SKIP", law, "no 'routed to /<skill>' lines across %d ledger file(s)"
                  % len(sources))]
    if not out:
        out.append(R(ID, "PASS", law, "%d recorded route(s) all left downstream evidence" % seen))
    return out


# ---------------------------------------------------------------------------
# Adopted from cloudflare-os (Apache 2.0), whose sandbox pins globalOutbound:null so
# "no egress" is a fact about the runtime rather than a promise in prose. Ours is prose
# across many scripts; this makes it PROVABLE for our surfaces.
# ---------------------------------------------------------------------------
NET_RE = re.compile(r"^\s*(?:import|from)\s+(urllib\.request|urllib|socket|http\.client|"
                    r"requests|httpx|ftplib|telnetlib|smtplib)\b", re.M)
NET_SHELL_RE = re.compile(r"\b(curl|wget|nc)\s", re.M)
# Loopback evidence: a literal address, OR consumption of render-check's URL — that
# server's 127.0.0.1 binding is itself allowlisted and re-asserted here, so a client of
# it is loopback-bound transitively rather than on trust.
LOOPBACK_RE = re.compile(r"127\.0\.0\.1|localhost|render-check|RC_URL")
# Every allowlisted use must be LOOPBACK-BOUND, and that is asserted, not trusted.
# LOOPBACK: allowed, and each one is ASSERTED to bind 127.0.0.1 — the allowlist is not
# a promise, it is a claim the check re-proves on every run.
NET_LOOPBACK = {
    "skills/notrest/scripts/establish.py": "status probes 127.0.0.1/health",
    "skills/graph/scripts/cockpit.py": "serves 127.0.0.1 only, by law",
    "skills/doctor/scripts/render-check.sh": "binds 127.0.0.1 on a private port",
    "skills/graph/scripts/cockpit-fixture.sh": "a client against the loopback server",
    "skills/doctor/scripts/seat-tax-fixture.sh": "curls render-check's 127.0.0.1 URL",
    "skills/notrest/scripts/fixture.sh": "asserts NOTHING is listening on a loopback port",
    "skills/graph/scripts/river-fixture.sh": "render-check client, loopback only",
    "skills/graph/scripts/journey-fixture.sh": "render-check client, loopback only",
    "skills/chatroom/scripts/fixture.sh": "loopback only",
}
# EXTERNAL BY DESIGN: real egress, named with its reason. These are capabilities, not
# leaks — but they are the complete list, so a NEW external caller cannot appear quietly.
# TEST DATA: files that only EMIT network text (a fixture writing a synthetic leaky
# script). Explicit, because "it's just a fixture" is exactly how a real caller would
# hide — the file is named, and the reason is recorded.
NET_TEST_DATA = {
    "skills/eval/scripts/fixture.sh": "writes synthetic leaky scripts as test data",
}
NET_EXTERNAL = {
    "skills/watch/scripts/watch.py": "re-verifies cited sources — fetching IS the skill",
    "skills/fable-director/scripts/fable-launcher.sh": "probes api.anthropic.com for model availability",
}


def check_network(root, plug, _skills):
    ID = "NETWORK-EGRESS"
    law = ("shipped hooks and scripts make no network calls except an allowlist of "
           "loopback-bound ones; compiled runtimes make none at all")
    out, checked, allowed, external = [], 0, [], []
    targets = sorted(glob.glob(os.path.join(plug, "hooks", "*.sh")) +
                     glob.glob(os.path.join(plug, "skills", "*", "scripts", "*")))
    for f in targets:
        if os.path.isdir(f):
            continue
        rel = os.path.relpath(f, plug)
        txt = read(f)
        if not txt:
            continue
        checked += 1
        key = rel.replace(os.sep, "/")
        # Shell-word scanning applies to SHELL files only: `curl` inside a python string
        # is a word in a vocabulary list, not a call — starthere_lint.py's command-head
        # set matched the naive rule and would have been a permanent false FAIL.
        hit = NET_RE.search(txt)
        if not hit and f.endswith(".sh"):
            hit = NET_SHELL_RE.search(txt)
        if not hit:
            continue
        if key in NET_TEST_DATA:
            continue
        if key in NET_EXTERNAL:
            external.append(key)
            continue
        if key in NET_LOOPBACK:
            if LOOPBACK_RE.search(txt):
                allowed.append(key)
            else:
                out.append(R(ID, "FAIL", law,
                             "%s:%d  allowlisted as loopback but nothing binds it to "
                             "127.0.0.1" % (rel_p(root, f), lineno(txt, hit.start())),
                             "bind it to loopback, or move it to NET_EXTERNAL with a reason"))
            continue
        out.append(R(ID, "FAIL", law,
                     "%s:%d  network use (%r) on no list"
                     % (rel_p(root, f), lineno(txt, hit.start()), hit.group(0).strip()),
                     "remove it, or list it in NET_LOOPBACK (and bind loopback) / "
                     "NET_EXTERNAL (with the reason it must reach the network)"))
    # compiled runtimes claim ZERO network; hold them to it
    for f in sorted(glob.glob(os.path.join(root, "compile", "*", "**", "*.py"),
                              recursive=True)):
        txt = read(f)
        if txt and NET_RE.search(txt):
            m = NET_RE.search(txt)
            out.append(R(ID, "FAIL", law,
                         "%s:%d  a compiled runtime imports the network"
                         % (rel_p(root, f), lineno(txt, m.start())),
                         "compiled runtimes are offline by law — remove the import"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law,
                        "%d script(s) scanned · %d loopback-bound: %s · %d external-by-design: %s"
                        % (checked, len(allowed), ", ".join(sorted(allowed)) or "-",
                           len(external), ", ".join(sorted(external)) or "-")))
    return out


# The KERNEL: surfaces where a mistake is an estate-wide mistake. Convention adopted from
# cloudflare-os's AGENTS.md higher-bar idea — named explicitly so "be careful here" is a
# list, not a feeling.
KERNEL_MARK = "KERNEL SURFACES"


def check_kernel(root, plug, skills):
    ID = "KERNEL-REVIEW"
    law = "the kernel surfaces are named where they are claimed, and carry the refuter law"
    out = []
    cm = os.path.join(root, "CLAUDE.md")
    # EXISTENCE IS os.path.isfile, NOT the read() sentinel: eval's read() returns "" on
    # failure, never None, so an `is None` test silently judged a MISSING CLAUDE.md as an
    # empty one and FAILed where it owed a SKIP. Caught by this check's own fixture in
    # v4.2.1 — the exact reason unfixtured checks are debt, not savings.
    if not os.path.isfile(cm) or "refuter" not in skills:
        return [R(ID, "SKIP", law, "no refuter skill / no CLAUDE.md — no kernel law here")]
    txt = read(cm)
    if KERNEL_MARK not in txt:
        out.append(R(ID, "FAIL", law, "%s  (no %r block)" % (rel_p(root, cm), KERNEL_MARK),
                     "name the kernel surfaces in CLAUDE.md"))
    if KERNEL_MARK in txt:
        rtxt = skills["refuter"][1]
        if KERNEL_MARK not in rtxt:
            out.append(R(ID, "FAIL", law,
                         "%s  (refuter does not name the kernel surfaces it gates)"
                         % rel_p(root, os.path.join(skills["refuter"][0], "SKILL.md")),
                         "name the kernel list in refuter's SKILL.md"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "kernel surfaces named in CLAUDE.md and refuter"))
    return out


# GOLDEN RELEASE SURFACE — adopted from cloudflare-os's golden-file manifest test. A ship
# touches exactly these files; one more or one fewer and the release is not the shape the
# repo agreed on.
GOLDEN_FILE = "evals/golden-release-surface.txt"


def check_release_surface(root, _plug, _skills):
    ID = "RELEASE-SURFACE"
    law = "a release touches exactly the agreed surface set — no more, no fewer"
    gf = os.path.join(root, GOLDEN_FILE)
    txt = read(gf)
    if txt is None:
        return [R(ID, "SKIP", law, "no %s — nothing to hold the release to" % GOLDEN_FILE)]
    want = [l.strip() for l in txt.splitlines() if l.strip() and not l.startswith("#")]
    missing = [w for w in want if not os.path.exists(os.path.join(root, w))]
    out = []
    if missing:
        out.append(R(ID, "FAIL", law,
                     "%s  (golden surface names %d file(s) that do not exist: %s)"
                     % (GOLDEN_FILE, len(missing), ", ".join(missing[:4])),
                     "fix the path, or regenerate: ls the surfaces and update %s" % GOLDEN_FILE))
    # THE OTHER HALF: a release that touches a surface nobody agreed on. Uncommitted
    # release-shaped edits are compared against the golden list; a tree with no git (a
    # fixture sandbox, a plugin cache dir) simply skips this half rather than guessing.
    rc, changed = 0, ""
    try:
        pr = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=root,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        rc, changed = pr.returncode, pr.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        rc = 1
    if rc == 0:
        RELEASE_SHAPED = ("CHANGELOG.md", "README.md", ".claude-plugin/", "docs/")
        extra = [f for f in (l.strip() for l in changed.splitlines())
                 if f and f not in want and any(f.startswith(m) or f == m
                                                for m in RELEASE_SHAPED)]
        if extra:
            out.append(R(ID, "FAIL", law,
                         "%s  (release touched %d surface(s) not in the golden list: %s)"
                         % (GOLDEN_FILE, len(extra), ", ".join(sorted(extra)[:4])),
                         "add it to %s in this same commit, and say why in the CHANGELOG"
                         % GOLDEN_FILE))
    if out:
        return out
    return [R(ID, "PASS", law, "%d release surface(s) all present" % len(want))]


CHECKS = [check_network, check_kernel, check_release_surface,
          check_offload, check_labels, check_scripts, check_references,
          check_estate, check_selfcheck, check_triggers, check_safety,
          check_hooks, check_router, check_route_parity, check_route_conformance]


# ---------------------------------------------------------------------------
# behavior cases — opt-in, bounded, code-graded. NEVER an LLM judge.
# ---------------------------------------------------------------------------
def grade_offload_spawn_directive(text):
    """PASS iff the answer names opus and never names sonnet/haiku as the spawn model."""
    if DOWNGRADE_RE.search(text):
        return False, "named a downgraded model for a spawn"
    return (bool(re.search(r"\bopus\b", text, re.I)),
            "opus named" if re.search(r"\bopus\b", text, re.I) else "no model named")


def grade_graph_scanner_preference(text):
    """PASS iff the answer reaches for graph.py rather than reading files itself."""
    if re.search(r"graph\.py|/graph\b", text, re.I):
        return True, "routed to the scanner"
    return False, "no scanner reference — the model read files itself"


BEHAVIOR_CASES = {
    "offload-spawn-directive": {
        "prompt": "Spawn a lane to audit the release notes. Show the exact Agent call you would make.",
        "grader": grade_offload_spawn_directive,
        "law": "OFFLOAD-POLICY — every offloaded job runs on explicit opus",
    },
    "graph-scanner-preference": {
        "prompt": "How do the files in this repo connect? Answer with the first tool call you make.",
        "grader": grade_graph_scanner_preference,
        "law": "SCRIPT-OWNS-SCANNING — the scanner reads the files, the model never has to",
    },
}


def run_behavior(name):
    case = BEHAVIOR_CASES.get(name)
    if not case:
        sys.stderr.write("unknown case %r; have: %s\n"
                         % (name, ", ".join(sorted(BEHAVIOR_CASES))))
        return 2
    print("BEHAVIOR CASE  %s" % name)
    print("law     : %s" % case["law"])
    print("command : claude -p %r --model opus --max-turns 1" % case["prompt"])
    print("grader  : %s  (python regex over the returned text — never an LLM judge)"
          % case["grader"].__name__)
    print("run     : opt-in only. Not part of the ship gate; `eval.py check` never spends tokens.")
    return 0


# ---------------------------------------------------------------------------
# baseline diff — what MOVED since a recorded run
# ---------------------------------------------------------------------------
RANK = {"SKIP": 0, "PASS": 1, "WARN": 2, "FAIL": 3}


def aggregate(rows):
    """One status per check id: the worst row wins, because that is what the exit code
    already reflects."""
    out = {}
    for r in rows:
        cur = out.get(r["check"])
        if cur is None or RANK.get(r["status"], 0) > RANK.get(cur, 0):
            out[r["check"]] = r["status"]
    return out


def diff_baseline(path, current):
    """-> dict. A baseline never changes the verdict or the exit code; it only says what
    moved. An unreadable baseline is reported, not raised — a missing reference run is
    not a conformance failure."""
    try:
        with open(path, encoding="utf-8") as fh:
            prev = json.load(fh).get("results") or []
    except (OSError, ValueError, AttributeError) as exc:
        return {"path": path, "error": "%s: %s" % (type(exc).__name__, exc)}

    old_agg, new_agg = aggregate(prev), aggregate(current)
    flips = [{"check": k, "from": old_agg.get(k, "absent"), "to": new_agg.get(k, "absent")}
             for k in sorted(set(old_agg) | set(new_agg))
             if old_agg.get(k, "absent") != new_agg.get(k, "absent")]

    def key(r):
        return (r["check"], r["status"], r["evidence"])
    old_f, new_f = {key(r): r for r in prev}, {key(r): r for r in current}
    added = [new_f[k] for k in sorted(set(new_f) - set(old_f))]
    removed = [old_f[k] for k in sorted(set(old_f) - set(new_f))]
    return {"path": path, "flips": flips, "added": added, "removed": removed}


def print_changed(d):
    print("")
    if d.get("error"):
        print("CHANGED vs %s — baseline unreadable (%s); the verdict above stands unchanged"
              % (d["path"], d["error"]))
        return
    if not (d["flips"] or d["added"] or d["removed"]):
        print("CHANGED vs %s — nothing moved: same checks, same findings" % d["path"])
        return
    print("CHANGED vs %s" % d["path"])
    for f in d["flips"]:
        print("  %-22s %s -> %s" % (f["check"], f["from"], f["to"]))
    for r in d["added"]:
        print("  + %-5s %-22s %s" % (r["status"], r["check"], r["evidence"]))
    for r in d["removed"]:
        print("  - %-5s %-22s %s" % (r["status"], r["check"], r["evidence"]))
    print("  (%d check(s) flipped · %d finding(s) added · %d removed — the exit code above "
          "reports THIS run, never the diff)" % (len(d["flips"]), len(d["added"]),
                                                 len(d["removed"])))


def run_check(root, as_json, baseline=None):
    started = time.time()
    plug, skills = locate(root)
    if not skills:
        sys.stderr.write("no skills found under %s\n" % root)
        return 2
    results = []
    for fn in CHECKS:
        results.extend(fn(root, plug, skills))
    fails = sum(1 for r in results if r.status == "FAIL")
    warns = sum(1 for r in results if r.status == "WARN")
    elapsed = time.time() - started
    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")
    rows = [r.as_dict() for r in results]
    changed = diff_baseline(baseline, rows) if baseline else None
    if as_json:
        blob = {"verdict": verdict, "root": root, "skills": len(skills),
                "fails": fails, "warns": warns, "seconds": round(elapsed, 3),
                "results": rows}
        if changed is not None:
            blob["changed"] = changed
        print(json.dumps(blob, indent=2))
    else:
        for r in results:
            print("%-5s %-22s %s — %s" % (r.status, r.check, r.law, r.evidence))
            if r.fix and r.status in ("FAIL", "WARN"):
                print("      fix: %s" % r.fix)
        print("SUMMARY %s — %d skills, %d checks, %d fail, %d warn, %.2fs, 0 model tokens"
              % (verdict, len(skills), len(CHECKS), fails, warns, elapsed))
        if changed is not None:
            print_changed(changed)
    return 6 if fails else (5 if warns else 0)


def main(argv):
    ap = argparse.ArgumentParser(prog="eval.py", description="notrest law-conformance suite")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="static law conformance over the shipped files")
    c.add_argument("--root", default=os.getcwd())
    c.add_argument("--json", action="store_true")
    c.add_argument("--baseline", metavar="FILE.json",
                   help="a previous --json run; report what MOVED since it "
                        "(never changes the verdict or the exit code)")
    b = sub.add_parser("behavior", help="print an opt-in bounded model case (does not run it)")
    b.add_argument("--case", required=True)
    b.add_argument("--list", action="store_true")
    ns = ap.parse_args(argv)
    if ns.cmd == "check":
        return run_check(os.path.abspath(ns.root), ns.json, ns.baseline)
    if ns.cmd == "behavior":
        return run_behavior(ns.case)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
