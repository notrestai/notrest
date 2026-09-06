#!/usr/bin/env python3
"""eval — the harness's law-conformance suite.

Doctrine: a law that is well-encoded leaves a STATIC FINGERPRINT in the shipped
files. This suite checks the fingerprint, not the behavior. Pure stdlib, pure
read, target < 2 seconds, zero model tokens. Never repairs, never bumps.

Exit: 0 all pass · 5 warnings only · 6 any FAIL · 2 usage error.
"""

import argparse
import base64
import binascii
import glob
import importlib.util
import shutil
import hashlib
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
# A documented model lane is what the offload policy binds. `run_in_background` alone is
# not evidence — Bash jobs and vendor bridges share that parameter.
SPAWN_MARK = re.compile(r"subagent_type|Agent tool|spawn_agent|agent\(|"
                        r"model:\s*\"?(?:opus|gpt-5\.6-sol)", re.I)
CLAUDE_MODEL_RE = re.compile(r"\bopus\b", re.I)
CODEX_MODEL_RE = re.compile(r"\bgpt-5\.6-sol\b", re.I)
# Owner-amended 2026-09-01 (supersedes 2026-08-30): the SEAT chooses each lane's model by
# the DIFFICULTY of the task and declares the choice — opus for judgment-bearing work,
# sonnet for bounded well-specified work whose done-when is a runnable check written before
# dispatch. So explicit sonnet is lawful when the sentence (or a neighbouring line) carries
# a tier declaration in EITHER vocabulary: the old mechanical/DRAFT-tier wording or the new
# bounded/well-specified/difficulty wording. What did NOT move: haiku is never lawful and a
# tier declaration does not launder it; a fork inherits the seat; an omitted model is a
# violation, not a default. This check must never demand "opus for every offloaded job" —
# that law was superseded, and a gate enforcing a dead law is a gate that blocks the truth.
HAIKU_RE = re.compile(r"model[\"']?\s*[:=]\s*[\"']?\s*haiku", re.I)
SONNET_RE = re.compile(r"model[\"']?\s*[:=]\s*[\"']?\s*sonnet", re.I)
# F2 (refuter round, 4.6.2) and its REVIEW ROUND. Two designs failed before this one, and
# both failures were the same mistake made at different widths: judging a directive by the
# WORDS NEAR IT rather than by its own shape.
#
#   cut 1 — exempt sonnet when the window carries the law's recital words (bounded /
#   difficulty / well-specified). The QUOTATION became the licence: a skill that recited the
#   amendment auto-exempted every sonnet directive beside it, including one saying the
#   opposite. Repro that passed: `Delegation: choose by difficulty.` above
#   `Every lane: model: "sonnet" — always, for all work including kernel design and refuters.`
#
#   cut 2 — exempt sonnet when the window names opus too, or carries a tier token; fail when
#   the window carries an absolute. Leaked BOTH ways. A bare mention of opus was a licence, so
#   `model: "sonnet" in all cases; opus is retired.` passed — the word "opus" appearing in a
#   sentence that RETIRES opus. And the absolute swept the whole window, so a correct
#   declaration was vetoed by an unrelated neighbouring line: `Opus by default for judgment.`
#   above `model: "sonnet" — tier: bounded …` FAILED.
#
# ⛔ SO THE CHECK IS A GRAMMAR CHECK, AND ITS SCOPE IS ONE LINE. A sonnet directive is
# lawful only when THE SAME LINE carries a DECLARATION TOKEN, and unlawful when THE SAME LINE
# carries an absolute — no window, no vocabulary, no opus-mention licence. Neighbouring prose
# cannot license a directive and cannot condemn one. That is the whole rule, and it is the
# only version of it that has survived a refuter.
SONNET_DECL_RE = re.compile(r"tier\s*[:=]\s*bounded|\bdraft[- ]?tier\b|\bmechanical\b", re.I)
SONNET_ABSOLUTE_RE = re.compile(
    r"\balways\b|\bevery\s+lane\b|\bevery\s+spawn\b|\bevery\s+job\b|\ball\s+work\b|"
    r"\bfor\s+all\b|\bfor\s+everything\b|\bby\s+default\b|\bdefault\s+model\b|"
    r"\bunconditional|\bin\s+all\s+cases\b|\bregardless\s+of\s+difficulty\b|"
    r"\beach\s+lane\b", re.I)


def sonnet_lawful(line):
    """Does THIS LINE declare a bounded tier, without also claiming an absolute?

    ⛔ BOUND, STATED WHERE IT IS IMPLEMENTED: this is a GRAMMAR check over
    directive-shaped mentions of a model. It can see that a line declares a tier; it
    cannot see whether the work was actually bounded, and it never tries to. Whether a
    given lane deserved sonnet is the SEAT'S JUDGMENT, receipted in the spend ledger and
    the dispatching brief. A PASS here means "the surface states the law in the shape the
    law requires" — never "the routing was wise".
    """
    if SONNET_ABSOLUTE_RE.search(line):
        return False
    return bool(SONNET_DECL_RE.search(line))


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
    law = ("GRAMMAR CHECK over directive-shaped model mentions (not a judgment about "
           "routing): every documented spawn maps both runtimes (Codex=gpt-5.6-sol, "
           "Claude names opus); a `model: sonnet` directive must declare its tier ON ITS "
           "OWN LINE and claim no absolute; haiku, inherited forks and an omitted model "
           "stay banned. Whether a lane DESERVED sonnet is the seat's judgment, receipted "
           "in the spend ledger and the brief — a PASS here is never 'the routing was wise'")
    out, spawners = [], []
    for name, (d, txt) in skills.items():
        f = rel(root, os.path.join(d, "SKILL.md"))
        # A line that names sonnet/haiku/fork alongside a negation IS the law,
        # not a breach of it. Only an unnegated directive is a violation.
        m = None
        for pat in (HAIKU_RE, SONNET_RE, FORK_RE):
            for hit in pat.finditer(txt):
                bol = txt.rfind("\n", 0, hit.start()) + 1
                eol = txt.find("\n", hit.end())
                line = txt[bol:eol if eol > 0 else len(txt)]
                if NEGATION_RE.search(line):
                    continue          # naming-to-ban IS the law
                # ONE LINE, like the negation above it. An earlier cut widened this to a
                # three-line window so a wrapped declaration would still count; what it
                # actually bought was a licence any neighbouring sentence could grant and
                # any neighbouring sentence could revoke. A directive that means to declare
                # its tier can say so on its own line.
                if pat is SONNET_RE and sonnet_lawful(line):
                    continue          # amended law: sonnet WITH a declared tier is lawful
                m = hit
                break
            if m:
                break
        if m:
            out.append(R(ID, "FAIL", law, "%s:%d  %r" % (f, lineno(txt, m.start()),
                                                         m.group(0).strip()),
                         "use the runtime map (Codex gpt-5.6-sol; Claude opus); forks inherit"))
            continue
        if SPAWN_MARK.search(txt):
            spawners.append(name)
            missing = []
            if not CLAUDE_MODEL_RE.search(txt):
                missing.append("Claude=opus")
            if not CODEX_MODEL_RE.search(txt):
                missing.append("Codex=gpt-5.6-sol")
            if missing:
                out.append(R(ID, "FAIL", law, "%s  (spawn directive, missing %s)"
                             % (f, ", ".join(missing)),
                             "state the dual runtime model map near the spawn contract"))
            if "subagent_type" in txt:
                banned = any(NEGATION_RE.search(ln) for ln in FORKBAN_RE.findall(txt))
                if not banned:
                    out.append(R(ID, "FAIL", law, "%s  (writes subagent_type, no fork ban)" % f,
                                 "add: never subagent_type \"fork\" — forks inherit the seat model"))
    hook = os.path.join(plug, "hooks", "session-start.sh")
    if os.path.isfile(hook):
        if not CLAUDE_MODEL_RE.search(read(hook)):
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
#
# ⛔ AMENDED IN 4.9 — THE PROMISE ITSELF CHANGED, AND THE CHECK SAYS SO OUT LOUD.
# Through 4.8 the law read "no egress at all, except an allowlist of loopback-bound
# callers". 4.9 opens ONE door on purpose: the plugin's identity now comes from the Atlas
# hub (device login, refresh, JWKS, revocation) and the bank pushes its snapshot there. A
# gate left enforcing the retired promise would either red the shipped tree forever or be
# quietly deleted — and a gate enforcing a dead law is a gate that blocks the truth. So
# the law is restated here, in the check's own text, with its rationale, and the door is
# held at its edges by three separate bolts, each with its own arm in the fixture:
#
#   1. ONE DESTINATION. `$ATLAS_HUB_BASE`, default https://atlas.not.rest, and nothing
#      else. Any OTHER script on the Atlas surface (or any hook) that NAMES a non-loopback,
#      non-hub host is a FAIL — that is how a second destination would arrive: as a string
#      in a file nobody re-read.
#   2. THREE DOORWAYS. Only `atlas_auth.py` (identity), `atlas_wire.py` (the push) and
#      `atlas.py` (the seat that calls them) may open a connection at all. Each is
#      RE-PROVED to take its base from ATLAS_HUB_BASE rather than hard-coding a host —
#      exactly as a loopback entry is re-proved to bind 127.0.0.1. An allowlist is a
#      claim the check re-tests, never a pass it hands out.
#   3. NO HOOK EVER WAITS ON THE NETWORK. A hook may INVOKE the auth client, but only in
#      the background; a hook that curls or urlopens inline puts every session in the
#      estate behind somebody else's DNS. SessionStart's
#      `python3 "$NR_ATLAS_AUTH" sessionstart --budget-ms 2000 >/dev/null 2>&1 &` is the
#      shape, and the trailing `&` is the law.
#
# Compiled runtimes are UNCHANGED by the amendment: they reach nothing at all, ever.
#
# ⛔ WHAT THIS CHECK DOES NOT SEE, stated where it is implemented:
#   · Inside the three doorways it does not police individual URL literals. Those modules
#     take their base from ATLAS_HUB_BASE at runtime; a host string in one of their
#     docstrings is documentation, and judging it would be judging prose. What is proved
#     there is that the module is ATLAS_HUB_BASE-driven; where it actually dials is
#     behavior, and their own fixtures own it.
#   · The scan surface is shell, python AND javascript under `hooks/`,
#     `skills/*/scripts/**` and `skills/*/mcp/**`. The MCP read server was the FOURTH
#     doorway hiding behind a file extension — this check first shipped naming that gap
#     instead of closing it, and the seat ruled it closed (2026-09-06): a `fetch(` in a
#     vendored .mjs is the same door as a `urlopen` in a .py, and it is held to the same
#     destination rule and the same $ATLAS_HUB_BASE re-proof. The vendored file itself is
#     never EDITED to satisfy the check — it already takes its base from the env.
#   · It reads text, not behavior. A doorway that takes its base from $ATLAS_HUB_BASE can
#     still be handed a hostile base by whoever sets the env; that is the operator's
#     surface, not a fingerprint, and the wire adapter's own arms own it.
# ---------------------------------------------------------------------------
# `urllib.parse` and `urllib.error` cannot open a socket — a URL splitter is not a
# caller, and treating it as one cost a false FAIL on the git credential helper, which
# parses a host precisely so it can REFUSE every host but the hub.
NET_RE = re.compile(r"^\s*(?:import|from)\s+(urllib\.request|urllib(?!\.)|socket|socketserver|"
                    r"http\.client|http\.server|requests|httpx|ftplib|telnetlib|smtplib)\b", re.M)
NET_SHELL_RE = re.compile(r"\b(curl|wget|nc)\s", re.M)
# The node surface. `fetch(` is the door the MCP server actually uses; the rest are the
# doors it would use instead if someone wanted this check to miss one.
JS_SUFFIX = (".mjs", ".cjs", ".js", ".ts")
JS_NET_RE = re.compile(r"\bfetch\s*\(|\bXMLHttpRequest\b|\baxios\b|"
                       r"from\s+[\"']node:(?:http|https|net|dgram|tls)[\"']|"
                       r"require\s*\(\s*[\"'](?:node:)?(?:http|https|net|dgram|tls)[\"']", re.M)
# Loopback evidence: a literal address, OR consumption of render-check's URL — that
# server's 127.0.0.1 binding is itself allowlisted and re-asserted here, so a client of
# it is loopback-bound transitively rather than on trust.
LOOPBACK_RE = re.compile(r"127\.0\.0\.1|localhost|render-check|RC_URL")
# THE ONE DOOR (4.9). The env name is the contract; the default is the fallback.
ATLAS_HUB_ENV = "ATLAS_HUB_BASE"
ATLAS_HUB_HOST = "atlas.not.rest"
HUB_BOUND_RE = re.compile(r"ATLAS_HUB_BASE")
# host, with an optional port and bracketed IPv6, out of an http(s) URL literal.
URL_HOST_RE = re.compile(r"https?://(\[[0-9A-Fa-f:]+\]|[A-Za-z0-9._~%-]+)(?::\d+)?")
# LOOPBACK IS 127.0.0.0/8, ::1 AND localhost — AND NOTHING ELSE. Not 0.0.0.0 (that is
# "every interface", the opposite of private), and not a LAN range: a host on the office
# network is a second destination, which is exactly what the amendment forbids.
LOOPBACK_HOSTS = {"localhost", "::1", "[::1]"}
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
    # 4.9 — the mock hub and the clients that drive it. The hub the fixtures talk to is
    # a stdlib http.server bound to 127.0.0.1: no fixture in this estate reaches Atlas.
    "skills/atlas/scripts/mockhub.py": "binds 127.0.0.1 only (and its --selftest drives itself there)",
    "skills/atlas/scripts/fixture-auth.sh": "reserves a free 127.0.0.1 port and runs mockhub on it",
    "skills/atlas/scripts/fixture-wire.sh": "stub hub bound to ('127.0.0.1', 0) for the push arms",
    "skills/watch/scripts/fixture.sh": "serves the fixture's own pages on ('127.0.0.1', 0)",
}
# THE ATLAS DOORWAYS (4.9): real egress to the ONE permitted destination, named with the
# half of the product each one carries. Every entry is re-proved to be ATLAS_HUB_BASE-driven.
ATLAS_EGRESS = {
    "skills/atlas/scripts/atlas_auth.py": "identity — device login, refresh, JWKS, revocation",
    "skills/atlas/scripts/atlas_wire.py": "the bank — the snapshot push",
    "skills/atlas/scripts/atlas.py": "the seat that calls them (the push path)",
    # the FOURTH doorway, by the seat's ruling of 2026-09-06. Vendored from Atlas and
    # never edited: it reads `process.env.ATLAS_HUB_BASE` at its line 51, which is the
    # same re-proof every other doorway passes.
    "skills/atlas/mcp/server.mjs": "the MCP read server — answers a consumer's questions from the hub",
}
# EXTERNAL BY DESIGN: real egress, named with its reason. These are capabilities, not
# leaks — but they are the complete list, so a NEW external caller cannot appear quietly.
# TEST DATA: files that only EMIT network text (a fixture writing a synthetic leaky
# script). Explicit, because "it's just a fixture" is exactly how a real caller would
# hide — the file is named, and the reason is recorded.
NET_TEST_DATA = {
    "skills/eval/scripts/fixture.sh": "writes synthetic leaky scripts as test data",
}
# Host literals that are TEST DATA on the Atlas surface: a hostile host a fixture feeds
# to the wire adapter to prove it is REFUSED. Named one by one, for the same reason as
# above — a fixture is where a second destination would hide most comfortably.
ATLAS_URL_TEST_DATA = {
    "skills/atlas/scripts/fixture-wire.sh": "hostile-host arms (evil.example, hub.invalid) — asserted refused, never dialled",
}
NET_EXTERNAL = {
    "skills/watch/scripts/watch.py": "re-verifies cited sources — fetching IS the skill",
    "skills/fable-director/scripts/fable-launcher.sh": "probes api.anthropic.com for model availability",
}
# A hook that reaches the network SYNCHRONOUSLY blocks every session in the estate. The
# verbs, minus `git push`: the pretool gate names "git push" as a TEXT PATTERN it guards,
# and a check that cannot tell naming from running would red the very gate that stops a
# push. Naming is not running; the shipped hooks push nothing.
HOOK_EGRESS_RE = re.compile(r"\b(curl|wget|ncat|telnet|urlopen)\b|\burllib\b|\bfetch\s*\(|"
                            r"\bnc\s+-|\bgit\s+(?:-C\s+\S+\s+)?(?:pull|fetch|clone|ls-remote)\b")
# `command -v curl`, `[ -x /usr/bin/python3 ]` and friends ask WHETHER a tool exists.
# A probe is not a call, and a gate that cannot tell them apart teaches people to delete it.
# Any skill's MCP directory is Atlas-surface for the destination rule: an MCP server is a
# thing that TALKS to somewhere, so a second host in one is exactly the shape being guarded.
MCP_PATH_RE = re.compile(r"skills/[^/]+/mcp/")
PROBE_SHAPE_RE = re.compile(r"command\s+-v\b|\btype\s+-\w|\bwhich\s+\w|\[\s*-[a-zA-Z]\s|\[\[\s*-[a-zA-Z]\s")
ASSIGN_RE = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*=")
# An invocation is an interpreter ADJACENT to the client — `python3 "$NR_ATLAS_AUTH" …`.
# Adjacency is the whole point: `[ -x /usr/bin/python3 ]` on a line that also tests
# `[ -f "$NR_ATLAS_AUTH" ]` names both words and runs neither.
# The whole next word is the target, whatever it is made of: a bare path, a variable, or
# a variable spliced onto a path (`"$NR/skills/atlas/scripts/atlas_auth.py"` — the shape
# that slipped the first cut of this regex, which stopped capturing at the `/`).
PY_INVOKE_RE = re.compile(r"(?:^|[|;&(]|\s)(?:/\S*/)?python3?(?:\s+-[^\s]+)*\s+"
                          r"[\"']?([^\s\"';|&]+)")


def _is_loopback_host(host):
    h = host.strip().lower()
    return (h in LOOPBACK_HOSTS or h.startswith("127.") or h.endswith(".localhost")
            or h == "[::1]")


def _is_hub_host(host):
    h = host.strip().lower()
    return h == ATLAS_HUB_HOST or h.endswith("." + ATLAS_HUB_HOST)


def _backgrounded(line):
    """Does this shell line hand its command to the background?

    Peels trailing redirections and closing parens so that both shapes in the shipped
    hooks read as backgrounded: `… >/dev/null 2>&1 &` and `( … & ) 2>/dev/null`.
    `&&` is a separator, not a fork, and never counts.
    """
    s, prev = line.strip(), None
    while s != prev:
        prev = s
        s = re.sub(r"\s*(?:[0-9]*(?:>>|>|<)\s*\S+|\)|;|\}|\bfi\b|\bdone\b)\s*$", "", s).strip()
    return s.endswith("&") and not s.endswith("&&")


def _code_lines(txt):
    """(lineno, line) for every line that is not a whole-line comment."""
    for i, line in enumerate(txt.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        yield i, line


def check_network(root, plug, _skills):
    """One door, one destination, and no hook that waits on it.

    The 4.9 amendment is stated in `law` below so a reader of the OUTPUT — not only a
    reader of this file — learns that the no-egress promise was deliberately changed and
    what replaced it. Three halves: who may open a connection, what may be named, and
    whether a hook ever blocks on one.
    """
    ID = "NETWORK-EGRESS"
    law = ("4.9: ONE destination — the Atlas hub ($ATLAS_HUB_BASE, default "
           "https://atlas.not.rest) — through FOUR doorways and no others (atlas_auth.py, "
           "atlas_wire.py, atlas.py's push, mcp/server.mjs), each re-proved to take its base "
           "from the env; every other shipped script, hook and MCP file is loopback-bound or "
           "silent, no hook egresses synchronously, and compiled runtimes reach nothing")
    out, checked, allowed, external, doors = [], 0, [], [], []
    hooks = sorted(glob.glob(os.path.join(plug, "hooks", "*.sh")))
    # RECURSIVE: `scripts/*` never saw `scripts/vendor/`, and a subdirectory is exactly
    # where a caller would sit unread.
    targets = sorted(hooks +
                     glob.glob(os.path.join(plug, "skills", "*", "scripts", "**"),
                               recursive=True) +
                     glob.glob(os.path.join(plug, "skills", "*", "mcp", "**"),
                               recursive=True))
    for f in targets:
        if os.path.isdir(f):
            continue
        rel = os.path.relpath(f, plug)
        txt = read(f)
        if not txt:
            continue
        checked += 1
        key = rel.replace(os.sep, "/")
        # ---- half 1: WHO MAY OPEN A CONNECTION ------------------------------------
        # Shell-word scanning applies to SHELL files only: `curl` inside a python string
        # is a word in a vocabulary list, not a call — starthere_lint.py's command-head
        # set matched the naive rule and would have been a permanent false FAIL.
        hit = NET_RE.search(txt)
        if not hit and f.endswith(".sh"):
            hit = NET_SHELL_RE.search(txt)
        if not hit and f.endswith(JS_SUFFIX):
            hit = JS_NET_RE.search(txt)
        if hit and key not in NET_TEST_DATA:
            if key in NET_EXTERNAL:
                external.append(key)
            elif key in ATLAS_EGRESS:
                # the allowlist is a claim, re-proved: a doorway takes its base from the
                # env contract, never from a host baked into the file.
                if HUB_BOUND_RE.search(txt):
                    doors.append(key)
                else:
                    out.append(R(ID, "FAIL", law,
                                 "%s:%d  named an Atlas doorway but nothing binds it to $%s"
                                 % (rel_p(root, f), lineno(txt, hit.start()), ATLAS_HUB_ENV),
                                 "take the base from $%s (default %s), or drop it from "
                                 "ATLAS_EGRESS" % (ATLAS_HUB_ENV, ATLAS_HUB_HOST)))
            elif key in NET_LOOPBACK:
                if LOOPBACK_RE.search(txt):
                    allowed.append(key)
                else:
                    out.append(R(ID, "FAIL", law,
                                 "%s:%d  allowlisted as loopback but nothing binds it to "
                                 "127.0.0.1" % (rel_p(root, f), lineno(txt, hit.start())),
                                 "bind it to loopback, or move it to NET_EXTERNAL with a reason"))
            else:
                out.append(R(ID, "FAIL", law,
                             "%s:%d  network use (%r) on no list"
                             % (rel_p(root, f), lineno(txt, hit.start()), hit.group(0).strip()),
                             "remove it, or list it in NET_LOOPBACK (and bind loopback) / "
                             "ATLAS_EGRESS (a hub doorway) / NET_EXTERNAL (with the reason)"))
        # ---- half 2: WHAT MAY BE NAMED (the one destination) ----------------------
        # Scoped to the surface the amendment opened — the Atlas skill and the hooks.
        # Elsewhere the older, stronger test still applies: no caller at all, so a host
        # in a docstring cannot dial anything. Widening the string scan estate-wide would
        # red an XML namespace and `example.invalid` test data, and an allowlist people
        # pad to silence noise is an allowlist that has stopped meaning anything.
        on_atlas_surface = (key.startswith("skills/atlas/") or key.startswith("hooks/")
                            or MCP_PATH_RE.match(key))
        if on_atlas_surface and key not in ATLAS_EGRESS and key not in ATLAS_URL_TEST_DATA \
                and key not in NET_TEST_DATA:
            for m in URL_HOST_RE.finditer(txt):
                host = m.group(1)
                if _is_loopback_host(host) or _is_hub_host(host):
                    continue
                out.append(R(ID, "FAIL", law,
                             "%s:%d  names %s — the only external destination this harness "
                             "may name is the Atlas hub"
                             % (rel_p(root, f), lineno(txt, m.start()), host),
                             "point it at $%s (default %s) or 127.0.0.1; if it is test "
                             "data, name the file in ATLAS_URL_TEST_DATA with its reason"
                             % (ATLAS_HUB_ENV, ATLAS_HUB_HOST)))
                break          # one row per file: the law is the file's, not the line's
    # ---- half 3: NO HOOK WAITS ON THE NETWORK ---------------------------------
    quiet_hooks = 0
    for f in hooks:
        txt = read(f)
        if not txt:
            continue
        # shell variables that hold the auth client's path, so `"$NR_ATLAS_AUTH"` reads
        # as the client it is.
        held = set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=[^\n]*atlas_auth\.py", txt, re.M))
        blocking = []
        for i, line in _code_lines(txt):
            if ASSIGN_RE.match(line) or PROBE_SHAPE_RE.search(line):
                continue           # naming a path, or asking whether a tool exists
            m = HOOK_EGRESS_RE.search(line)
            call = PY_INVOKE_RE.search(line)
            target = (call.group(1) if call else "") or ""
            invokes = bool(call) and ("atlas_auth.py" in target
                                      or target.strip("\"'${}") in held)
            if not (m or invokes):
                continue
            if _backgrounded(line):
                continue
            blocking.append((i, m.group(0).strip() if m else "atlas_auth.py"))
        if blocking:
            i, what = blocking[0]
            out.append(R(ID, "FAIL", law,
                         "%s:%d  a hook egresses SYNCHRONOUSLY (%r) — every session in the "
                         "estate waits on it" % (rel_p(root, f), i, what),
                         "background it (`… >/dev/null 2>&1 &`), the way SessionStart "
                         "invokes atlas_auth.py sessionstart"))
        else:
            quiet_hooks += 1
    # compiled runtimes claim ZERO network; hold them to it — UNCHANGED by the amendment.
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
                        "%d file(s) scanned · %d Atlas doorway(s) to $%s: %s · %d "
                        "loopback-bound: %s · %d external-by-design: %s · %d/%d hook(s) "
                        "never wait on the network"
                        % (checked, len(doors), ATLAS_HUB_ENV, ", ".join(sorted(doors)) or "-",
                           len(allowed), ", ".join(sorted(allowed)) or "-",
                           len(external), ", ".join(sorted(external)) or "-",
                           quiet_hooks, len(hooks))))
    return out


# ---------------------------------------------------------------------------
# 4.9 · THE SECRET-HANDLING LAWS. Three of these guard one sentence of the docket —
# "secrets by path, never by value" — at the three places a token can be lost: the mode
# it is written with, the git config that hands it out, and the repo it must never be
# typed into. The fourth guards the verifier's PROVENANCE: the file that decides whether
# a machine is admitted is Atlas's own, byte for byte, or the admission decision is ours
# to get wrong.
# ---------------------------------------------------------------------------
TOKEN_NAME = "atlas-token"
# where the token lands: the helper that returns its path, or the name itself.
TOKEN_TARGET_RE = re.compile(r"token_path\s*\(|[\"']atlas-token[\"']")
# a write, in any of the shapes this estate actually uses.
# ⛔ `.write(` IS NOT ON THIS LIST. `sys.stderr.write("… %s" % token_path)` is a file
# write to nothing — it put atlas.py's "your token lives here" message inside the window
# and FAILed a line that stores nothing. A write is a file being CREATED or REPLACED.
WRITE_VERB_RE = re.compile(r"_write_private\s*\(|\bopen\s*\([^)]*[\"']w|os\.open\s*\(|"
                           r"os\.replace\s*\(|os\.rename\s*\(|shutil\.copy")
# private BY CREATION. `0o600` at the write, or a umask that makes it the default.
PRIVATE_MODE_RE = re.compile(r"0o600|\b0600\b|umask\s*\(\s*0o?0?77")
TOKEN_WINDOW = 8


def check_token_store(root, plug, _skills):
    """The identity token is created 0600, and the mode is stated AT the write.

    ⛔ BOUND, STATED WHERE IT IS IMPLEMENTED: this is a grep-level fingerprint check over
    a window of TOKEN_WINDOW lines, not a test of the file mode on disk (eval never runs
    the code it judges). It therefore asserts something slightly stronger than "the file
    ends up 0600": it asserts the mode is VISIBLE at the write. A 0600 that lives only in
    a helper's default argument is secure today and silent tomorrow — a refactor that adds
    a second caller inherits nothing and says nothing. Stating the mode at the write is
    the fingerprint the law leaves; a fixture arm proves a write without one FAILs.
    """
    ID = "TOKEN-STORE"
    law = ("every code path that writes the Atlas identity token states its 0600 mode at "
           "the write — the token is private by creation, never private by afterthought")
    out, sites = [], 0
    for f in sorted(glob.glob(os.path.join(plug, "skills", "*", "scripts", "**", "*.py"),
                              recursive=True)):
        txt = read(f)
        if not txt or TOKEN_NAME not in txt:
            continue
        lines = txt.splitlines()
        for i, line in enumerate(lines):
            if line.lstrip().startswith("#") or not TOKEN_TARGET_RE.search(line):
                continue
            lo, hi = max(0, i - TOKEN_WINDOW), min(len(lines), i + TOKEN_WINDOW + 1)
            window = "\n".join(lines[lo:hi])
            if not WRITE_VERB_RE.search(window):
                continue          # the token is READ here, or only its path is built
            sites += 1
            if PRIVATE_MODE_RE.search(window):
                continue
            out.append(R(ID, "FAIL", law,
                         "%s:%d  writes the identity token with no 0600 within %d lines"
                         % (rel_p(root, f), i + 1, TOKEN_WINDOW),
                         "write it 0600 at the write (mkstemp + os.chmod(path, 0o600) + "
                         "os.replace), so the token is never briefly world-readable"))
    if not sites:
        return [R(ID, "SKIP", law, "no script writes %s in this tree" % TOKEN_NAME)]
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law,
                        "%d token-write site(s), every one 0600 at the write" % sites))
    return out


# The git credential helper hands the token to git. Scoped to the hub host, git offers it
# to the hub and to nobody else; configured BARE, git offers it to every host it is ever
# pointed at — the same token, to a stranger, on the first `git clone`.
CRED_HELPER_RE = re.compile(r"credential(\.[^\s\"'=]+?)?\.helper\b")
# The hunter contains the quarry. A suite that names a forbidden shape in its own law
# text, evidence strings and fixture arms would convict itself on every run — the same
# reason NET_TEST_DATA exists, applied to the two files that ARE the suite.
# Used by HELPER-SCOPE ONLY, and deliberately not by NO-TOKEN-LITERAL: a secret scan that
# exempts a file is a secret scan with a hiding place. The fixture needs no exemption
# there because it MINTS its decoy keys at run time instead of committing them — which is
# what the docket asks of every fixture anyway.
LAW_TEXT_EXEMPT = {
    "skills/eval/scripts/eval.py": "the checker necessarily spells the shapes it hunts",
    "skills/eval/scripts/fixture.sh": "writes synthetic violations as test data",
}


def check_helper_scope(root, plug, _skills):
    """The only credential helper the plugin configures is host-scoped to the hub.

    ⛔ Comment lines are skipped: a fixture that EXPLAINS why a machine-wide
    `credential.helper` is dangerous must be able to say the words. What is judged is
    config the plugin WRITES.
    """
    ID = "HELPER-SCOPE"
    law = ("the only git credential helper the plugin configures is scoped to the Atlas "
           "hub host — a bare credential.helper offers the token to every host git meets")
    out, scoped = [], []
    targets = sorted(glob.glob(os.path.join(plug, "hooks", "*.sh")) +
                     glob.glob(os.path.join(plug, "skills", "*", "scripts", "**"),
                               recursive=True))
    for f in targets:
        if os.path.isdir(f):
            continue
        txt = read(f)
        if not txt or "credential" not in txt:
            continue
        if os.path.relpath(f, plug).replace(os.sep, "/") in LAW_TEXT_EXEMPT:
            continue
        hub_bound = bool(HUB_BOUND_RE.search(txt)) or ATLAS_HUB_HOST in txt
        for i, line in _code_lines(txt):
            for m in CRED_HELPER_RE.finditer(line):
                scope = (m.group(1) or "").lstrip(".")
                if not scope:
                    out.append(R(ID, "FAIL", law,
                                 "%s:%d  configures a BARE credential.helper"
                                 % (rel_p(root, f), i),
                                 "scope it to the hub: credential.<hub url>.helper, so git "
                                 "offers the token to the hub and to nothing else"))
                    continue
                dynamic = bool(re.search(r"%s|\{\}|\$|%\(", scope))
                if dynamic:
                    # the scope is computed: re-prove the file computes it FROM the hub.
                    if hub_bound:
                        scoped.append("%s:%d" % (rel_p(root, f), i))
                    else:
                        out.append(R(ID, "FAIL", law,
                                     "%s:%d  scopes the helper to a computed host, and the "
                                     "file never names $%s or %s"
                                     % (rel_p(root, f), i, ATLAS_HUB_ENV, ATLAS_HUB_HOST),
                                     "compute the scope from $%s (default %s)"
                                     % (ATLAS_HUB_ENV, ATLAS_HUB_HOST)))
                elif _is_hub_host(re.sub(r"^https?://", "", scope).split("/")[0]):
                    scoped.append("%s:%d" % (rel_p(root, f), i))
                else:
                    out.append(R(ID, "FAIL", law,
                                 "%s:%d  scopes the helper to %r — not the Atlas hub"
                                 % (rel_p(root, f), i, scope),
                                 "scope it to %s" % ATLAS_HUB_HOST))
    if not scoped and not out:
        return [R(ID, "SKIP", law, "no credential helper config in this tree")]
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law,
                        "%d credential helper config(s), every one hub-scoped: %s"
                        % (len(scoped), ", ".join(scoped))))
    return out


# The verifier decides whether a machine is admitted. It is Atlas's file, not ours: we
# vendor it byte-exact so the answer to "who may use this plugin" is one implementation
# with one owner, and an edit to it — even a helpful one — is a fork of the admission rule.
VENDORED_VERIFIER = "skills/atlas/scripts/vendor/verify_token.py"
CONTRACT_VERIFIER = os.path.join("briefs", "atlas-contract", "kit", "verify-token.py")


def _sha256(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def check_verifier_vendored(root, plug, skills):
    ID = "VERIFIER-VENDORED"
    law = ("the token verifier is Atlas's own file, vendored byte-exact with its licence "
           "line intact — the admission rule has one implementation and one owner")
    if "atlas" not in skills:
        return [R(ID, "SKIP", law, "no atlas skill in this tree — nothing admits anything")]
    p = os.path.join(plug, *VENDORED_VERIFIER.split("/"))
    if not os.path.isfile(p):
        return [R(ID, "FAIL", law, "%s  (absent)" % rel_p(root, p),
                  "vendor Atlas's kit/verify-token.py byte-exact to %s" % VENDORED_VERIFIER)]
    first = (read(p).splitlines() or [""])[0]
    out = []
    if not (first.lstrip().startswith("#") and "Atlas" in first
            and re.search(r"licens", first, re.I)):
        out.append(R(ID, "FAIL", law,
                     "%s:1  line 1 is not the Atlas licence line (%s)"
                     % (rel_p(root, p), clip_line(first, 60)),
                     "restore the vendored file's first line verbatim — it is the licence"))
    contract = os.path.join(root, CONTRACT_VERIFIER)
    got = _sha256(p)
    if not os.path.isfile(contract):
        # A consumer install ships no briefs/. Byte-equality is unprovable HERE, and
        # saying so is the honest row — a PASS that quietly skipped half its own test is
        # exactly the kind of claim this suite exists to refuse.
        out.append(R(ID, "SKIP", law,
                     "%s  present and licensed (sha256 %s) · %s not in this tree, so "
                     "byte-equality against the contract copy was not proved here"
                     % (VENDORED_VERIFIER, got[:12], CONTRACT_VERIFIER)))
        return out
    want = _sha256(contract)
    if got != want:
        out.append(R(ID, "FAIL", law,
                     "%s sha256 %s != %s sha256 %s"
                     % (VENDORED_VERIFIER, got[:12], CONTRACT_VERIFIER, want[:12]),
                     "re-copy the contract file verbatim; never edit a vendored verifier"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "%s is byte-exact with %s (sha256 %s) and carries "
                        "the licence line" % (VENDORED_VERIFIER, CONTRACT_VERIFIER, got[:12])))
    return out


# A secret in the repo is a secret that has been published. These two shapes are what our
# secrets LOOK like: a signed Atlas token (three base64url segments whose header is JSON
# naming an alg) and a ring key (`nrk_` + secrets.token_urlsafe(32)).
JWT_SHAPE_RE = re.compile(r"\b([A-Za-z0-9_-]{12,})\.([A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]{20,})\b")
RING_KEY_RE = re.compile(r"\bnrk_([A-Za-z0-9_-]{20,})")
SKIP_SUFFIX = (".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".gz", ".pdf", ".woff", ".woff2")


def _looks_like_key_material(body):
    """Is this the tail of a REAL minted key, or a hand-written placeholder?

    A minted key is `secrets.token_urlsafe(32)` — 43 base64url characters. The chance
    that such a string carries neither a digit nor a capital is about 1e-13, so
    "has a digit or a capital" catches every real key that will ever exist. What it does
    NOT catch is a real key that lost against those odds; what it DOES catch, and should,
    is any placeholder written to look like key material. Both directions are stated
    because the second is the one a fixture author actually meets: name your decoys in
    lower-case words and this check stays quiet.
    """
    return bool(re.search(r"[0-9]", body) or re.search(r"[A-Z]", body))


def check_no_token_literal(root, plug, _skills):
    """No signed token and no ring key is ever committed.

    ⛔ WHAT IT CANNOT SEE: a secret that does not look like ours (a password, an ingest
    secret with no prefix) and a key that lost a 1e-13 coin flip. This is the shape check,
    not a credential scanner; the estate's real defence is that secrets travel BY PATH.
    """
    ID = "NO-TOKEN-LITERAL"
    law = ("no signed token and no ring key is committed anywhere under the plugin — "
           "secrets travel by path, never by value")
    out, scanned = [], 0
    for dirpath, dirnames, filenames in os.walk(plug):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
        for name in sorted(filenames):
            if name.endswith(SKIP_SUFFIX):
                continue
            f = os.path.join(dirpath, name)
            try:
                if os.path.getsize(f) > 4 * 1024 * 1024:
                    continue
            except OSError:
                continue
            txt = read(f)
            if not txt:
                continue
            scanned += 1
            for m in RING_KEY_RE.finditer(txt):
                if not _looks_like_key_material(m.group(1)):
                    continue
                out.append(R(ID, "FAIL", law,
                             "%s:%d  a committed nrk_ ring key literal"
                             % (rel_p(root, f), lineno(txt, m.start())),
                             "delete it, revoke the key, and read it from a file at "
                             "runtime — a key in the repo is a key that is published"))
                break
            if "." not in txt:
                continue
            for m in JWT_SHAPE_RE.finditer(txt):
                seg = m.group(1)
                try:
                    hdr = json.loads(base64.urlsafe_b64decode(
                        seg + "=" * (-len(seg) % 4)).decode("utf-8", "strict"))
                except (ValueError, binascii.Error, UnicodeDecodeError):
                    continue
                if not (isinstance(hdr, dict) and "alg" in hdr):
                    continue
                out.append(R(ID, "FAIL", law,
                             "%s:%d  a committed signed token (header alg %r)"
                             % (rel_p(root, f), lineno(txt, m.start()), hdr.get("alg")),
                             "delete it and revoke the jti — fixtures mint their own "
                             "throwaway tokens at run time"))
                break
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law,
                        "%d shipped file(s) carry no token and no ring key literal" % scanned))
    return out


# The KERNEL: surfaces where a mistake is an estate-wide mistake. Convention adopted from
# cloudflare-os's AGENTS.md higher-bar idea — named explicitly so "be careful here" is a
# list, not a feeling.
KERNEL_MARK = "KERNEL SURFACES"


def check_kernel(root, plug, skills):
    ID = "KERNEL-REVIEW"
    law = "the kernel surfaces are named where they are claimed, and carry the refuter law"
    out = []
    foundations = [os.path.join(root, n) for n in ("AGENTS.md", "CLAUDE.md")
                   if os.path.isfile(os.path.join(root, n))]
    # EXISTENCE IS os.path.isfile, NOT the read() sentinel: eval's read() returns "" on
    # failure, never None, so an `is None` test silently judged a MISSING CLAUDE.md as an
    # empty one and FAILed where it owed a SKIP. Caught by this check's own fixture in
    # v4.2.1 — the exact reason unfixtured checks are debt, not savings.
    if not foundations or "refuter" not in skills:
        return [R(ID, "SKIP", law, "no refuter skill / no runtime foundation — no kernel law here")]
    named = []
    for foundation in foundations:
        txt = read(foundation)
        if KERNEL_MARK not in txt:
            out.append(R(ID, "FAIL", law, "%s  (no %r block)"
                         % (rel_p(root, foundation), KERNEL_MARK),
                         "name the kernel surfaces in every shipped runtime foundation"))
        else:
            named.append(rel_p(root, foundation))
    if named:
        rtxt = skills["refuter"][1]
        if KERNEL_MARK not in rtxt:
            out.append(R(ID, "FAIL", law,
                         "%s  (refuter does not name the kernel surfaces it gates)"
                         % rel_p(root, os.path.join(skills["refuter"][0], "SKILL.md")),
                         "name the kernel list in refuter's SKILL.md"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law, "kernel surfaces named in %s and refuter"
                        % ", ".join(named)))
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
        # ⛔ A DELETION IS NOT AN UNAGREED SURFACE. `git diff --name-only HEAD` lists
        # removed paths too, so RETIRING a golden-surface file could never be green before
        # the commit: drop it from the list and this half calls it an unagreed surface;
        # keep it in the list and the existence half above calls it a missing file. The
        # workshop rebuild hit exactly that vice — 10 module files deleted and delisted in
        # one change, with no ordering that passed. A touched path that no longer exists on
        # disk is a removal, and removal is what delisting MEANS. The other direction still
        # has its guard: a path left in the golden list but deleted is caught by `missing`.
        extra = [f for f in (l.strip() for l in changed.splitlines())
                 if f and f not in want
                 # lexists, not exists: exists() FOLLOWS the link, so a DANGLING symlink
                 # at a touched unlisted path reads as "removed" and slips the check while
                 # the index still carries a blob. A truly removed path is lexists-False;
                 # a broken link is lexists-True and stays an unagreed surface.
                 and os.path.lexists(os.path.join(root, f))
                 and any(f.startswith(m) or f == m for m in RELEASE_SHAPED)]
        if extra:
            out.append(R(ID, "FAIL", law,
                         "%s  (release touched %d surface(s) not in the golden list: %s)"
                         % (GOLDEN_FILE, len(extra), ", ".join(sorted(extra)[:4])),
                         "add it to %s in this same commit, and say why in the CHANGELOG"
                         % GOLDEN_FILE))
    if out:
        return out
    return [R(ID, "PASS", law, "%d release surface(s) all present" % len(want))]


# ---------------------------------------------------------------------------
# THE LEARNINGS LOOP (4.6.3)
# ---------------------------------------------------------------------------
LEARN_STORE = os.path.join("archive", "findings.jsonl")


def archivist_index(plug):
    """⛔ ONE HOME, AND ONE IMPLEMENTATION. The trigger REGEX and the code that APPLIES it
    both live in archivist's index.py, and BOTH consumers — this check and lane H's Stop
    hook — go there for them. The hook calls `index.py learnings --triggers`; this check
    imports the module and calls the same function that CLI wraps. Neither re-implements
    the match: a second copy of the rule is a second rule the moment somebody edits one,
    and then the hook prompts for lessons the gate does not audit, or the gate reddens on
    lines the hook never surfaced. Returns None when it cannot be read, and the check
    SKIPs rather than substituting a guess."""
    path = os.path.join(plug, "skills", "archivist", "scripts", "index.py")
    if not os.path.isfile(path):
        return None, path
    try:
        spec = importlib.util.spec_from_file_location("_notrest_archivist_index", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "triggers_with_citation"):
            return None, path
        return mod, path
    except Exception:
        return None, path


def learning_trigger_regex(plug):
    """The regex itself, for the parity arm and for anyone reporting what is audited."""
    mod, path = archivist_index(plug)
    rx = getattr(mod, "LEARN_TRIGGER_REGEX", None) if mod else None
    return (rx if isinstance(rx, str) and rx else None), path


def _learnings(root):
    """(records, first_ts) — every kind=learning in the store, and the ts of the oldest.
    A corrupt line is skipped: the audit is about lessons, not about JSON hygiene."""
    txt = read(os.path.join(root, LEARN_STORE))
    if txt is None:
        return [], None
    recs = []
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("kind") == "learning":
            recs.append(r)
    stamps = sorted(str(r.get("ts", "")) for r in recs if r.get("ts"))
    return recs, (stamps[0] if stamps else None)


def check_learning_loop(root, plug, _skills):
    """Did the estate BANK the lessons it paid for?

    A trigger is a COORD line whose HEADLINE carries an uppercase tag saying the estate
    just bought a lesson — a correction, a refuter round that came back dirty, a red gate,
    a halt. The loop is closed when a learning record CITES that line's timestamp.

    ⛔ THIS CHECK DOES NOT DECIDE WHAT A TRIGGER IS. It calls
    `index.py`'s `triggers_with_citation()` — the same code path the Stop hook reaches
    through `learnings --triggers` — so the gate and the prompt can never disagree about
    which lines matter.

    ⛔ AND THE AUDIT IS BOUNDED BY WHEN THE LOOP WAS ARMED. Triggers older than the FIRST
    learning record predate the practice, and grading an estate against a rule it did not
    have is how a gate becomes something people switch off. With no learning at all the
    loop is not armed and this SKIPs — it never invents a debt.
    """
    ID = "LEARNING-LOOP"
    law = ("every COORD line where the estate PAID for a lesson (an owner correction, a "
           "refuter round that came back dirty, a red gate, a halt) is cited by a banked "
           "learning record")
    mod, idx_path = archivist_index(plug)
    if mod is None:
        return [R(ID, "SKIP", law,
                  "cannot load %s — the trigger rule has ONE home and this check will not "
                  "re-implement it" % rel(root, idx_path))]
    try:
        rep = mod.trigger_report(root)
    except BaseException as exc:      # SystemExit included: index.py's die() raises it,
                                      # and the SHIP GATE must never exit through a
                                      # dependency's error path
        if isinstance(exc, KeyboardInterrupt):
            raise
        return [R(ID, "SKIP", law, "index.py could not read the triggers (%s: %s)"
                  % (type(exc).__name__, exc))]
    if not rep.get("armed"):
        return [R(ID, "SKIP", law,
                  "loop not armed — no kind=learning record in %s yet, so nothing is owed"
                  % LEARN_STORE)]
    uncited = rep.get("uncited") or []
    total = len(uncited) + int(rep.get("cited") or 0)
    if uncited:
        return [R(ID, "FAIL", law,
                  "%d of %d trigger line(s) since the loop was armed (floor %s) are cited "
                  "by no learning: %s"
                  % (len(uncited), total, rep.get("floor"),
                     " · ".join("%s %s" % (t["ts"], clip_line(t["headline"], 90))
                                for t in uncited[:3])),
                  "bank the lesson: `index.py add --kind learning --tag LEARNED "
                  "--statement '...' --evidence '<that bracketed timestamp>' "
                  "--scope '...'`, or say in the ledger why the line taught nothing")]
    return [R(ID, "PASS", law,
              "loop armed at %s; %d trigger line(s) since, all cited"
              % (rep.get("floor"), total))]


def clip_line(text, n):
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[:n - 1] + "\u2026"


KEYRING_REL = os.path.join(".access", "keys.sha256")
# Hooks that WRITE to the estate or INJECT into the model's context. Without a key these
# must do neither — and must still exit 0, because a hook that fails loudly breaks every
# session on a machine whose licence lapsed.
# ⛔ EACH HOOK IS DRIVEN WITH A REAL PAYLOAD OF ITS OWN EVENT. The first cut fed every
# hook `{}` — a payload that reaches no writing and no denying path — so deleting the gate
# from coord-nudge.sh still PASSED and adding a gate to spawn-gate's deny (making a
# keyless machine LAWLESS) still PASSED. A gate check that never reaches the gated code is
# a green light wired to nothing. WRITERS get input that would make them write; DENIERS get
# input they must refuse.
WRITER_HOOKS = {
    "coord-nudge.sh": {"hook_event_name": "UserPromptSubmit",
                       "prompt": "ship the release and bank the ledger line"},
    "agent-ledger.sh": {"hook_event_name": "SubagentStop", "agent_id": "eval-probe",
                        "transcript_path": "/nonexistent/eval-probe.jsonl",
                        "description": "eval access-gate probe"},
    "session-end.sh": {"hook_event_name": "Stop", "reason": "eval access-gate probe"},
    "router.sh": {"hook_event_name": "UserPromptSubmit", "prompt": "research the cache"},
}
BANNER_HOOK = "session-start.sh"
BANNER_PAYLOAD = {"hook_event_name": "SessionStart", "source": "startup"}
# A Task spawned with no model is the spawn gate's whole reason to exist; a Bash command
# the pretool gate's own rules deny is the other. Both must still be refused (rc 2) on a
# machine whose licence lapsed — otherwise an expired key is a security downgrade.
DENY_HOOKS = ("spawn-gate.sh", "pretool-gate.sh")
SPAWN_DENY_PAYLOAD = {"hook_event_name": "PreToolUse", "tool_name": "Task",
                      "tool_input": {"description": "a lane", "prompt": "do the work"}}
GATED_HOOKS = tuple(WRITER_HOOKS) + (BANNER_HOOK,)
# ⛔ ONE HOOK IS ALLOWED TO SPEAK, AND ONLY TO SAY THIS. The docket gives SessionStart a
# single banner line without a key — otherwise a machine whose licence lapsed gets a
# harness that silently does nothing and an operator with no idea why. The exemption is
# BOUNDED: one line, and it must be the Atlas notice.
# ANCHORED, by ruling: the line must OPEN with the notrest tag and the Atlas sentence.
# An unanchored match would let a hook print its own paragraph and end with the notice.
BANNER_RE = re.compile(r"^\[notrest\] notrest is part of Atlas")
NORM_CASE_RE = re.compile(r'\*"\s([a-z0-9 ]+?)\s"\*')


def _derived_deny_probe(hook_text):
    """A command the hook's OWN rules deny, built from its `case "$NORM"` patterns.

    ⛔ DERIVED, NEVER TYPED. Two reasons, the second load-bearing: a literal consumer-flow
    command sitting in this file trips the very gate it tests every time anyone greps or
    edits the tree; and a hardcoded phrase quietly stops probing anything the day the deny
    list changes. The gate normalises a command to lowercase alphanumerics separated by
    single spaces before matching, so a pattern lifted out of the case statement IS a
    denied command once the qualifying token the second case wants is appended.
    """
    if not hook_text:
        return None
    pats = NORM_CASE_RE.findall(hook_text)
    if not pats:
        return None
    m = re.search(r'case\s+"\$NORM"\s+in\s+\*([a-z]+)\*\|', hook_text)
    return (pats[0] + (" " + m.group(1) if m else "")).strip()


def _tree_state(root):
    """Every file under `root` with its size — enough to see a hook write or append."""
    out = set()
    for base, _dirs, files in os.walk(root):
        for fn in files:
            fp = os.path.join(base, fn)
            try:
                out.add("%s:%d" % (os.path.relpath(fp, root), os.path.getsize(fp)))
            except OSError:
                pass
    return out


def _is_dark(stdout):
    """Dark = said nothing, or said exactly the one sanctioned Atlas notice. A gate that
    was fooled does not go quiet — it emits the live banner, the nudges, the packet."""
    lines = [l for l in (stdout or "").splitlines() if l.strip()]
    return (not lines) or (len(lines) == 1 and BANNER_RE.search(lines[0]))


def _scratch_plugin(plug):
    """A throwaway copy of the plugin's hooks + verifier + a keyring of our own.

    ⛔ NEVER THE REAL KEY, NEVER THE REAL RING. These probes need to swap the verifier and
    poison $PATH; doing that against the shipped plugin would either fail on a machine
    whose operator holds a licence, or corrupt the install. Returns (dir, minted_key) or
    (None, None) when the plugin has no verifier to copy.
    """
    atlas_src = os.path.join(plug, "skills", "atlas", "scripts", "atlas.py")
    hooks_src = os.path.join(plug, "hooks")
    if not os.path.isfile(atlas_src) or not os.path.isdir(hooks_src):
        return None, None
    d = tempfile.mkdtemp(prefix="notrest-eval-plug-")
    try:
        shutil.copytree(hooks_src, os.path.join(d, "hooks"))
        os.makedirs(os.path.join(d, "skills", "atlas", "scripts"))
        shutil.copy2(atlas_src, os.path.join(d, "skills", "atlas", "scripts", "atlas.py"))
        os.makedirs(os.path.join(d, ".access"))
        key = "eval-scratch-key-%d" % os.getpid()
        with open(os.path.join(d, ".access", "keys.sha256"), "w", encoding="utf-8") as fh:
            fh.write("# eval scratch keyring\n%s:eval:2026-09-06\n"
                     % hashlib.sha256(key.encode("utf-8")).hexdigest())
        return d, key
    except (OSError, shutil.Error):
        return None, None


def _stub_bin():
    """A directory holding a fake `python3` that FORGES a passing verifier reply.

    ⛔ A STUB THAT ONLY EXITS 0 IS TOO WEAK A PROBE. The sentinel and the ring-hash check
    both refuse a silent exit-0, so such a stub stays dark even with the /usr/bin/python3
    preference removed — the arm would pass for the wrong reason and the preference could
    be deleted unnoticed. This stub does what a real attacker would: it reads the
    `--keyring` path it was handed, hashes it, and prints the exact sentinel the hook
    demands. Only the preference for the system interpreter stops it.
    """
    d = tempfile.mkdtemp(prefix="notrest-eval-bin-")
    fp = os.path.join(d, "python3")
    with open(fp, "w", encoding="utf-8") as fh:
        fh.write(
            "#!/bin/sh\n"
            "ring=''\n"
            "prev=''\n"
            "for a in \"$@\"; do\n"
            "  [ \"$prev\" = --keyring ] && ring=\"$a\"\n"
            "  prev=\"$a\"\n"
            "done\n"
            "if [ -n \"$ring\" ] && [ -f \"$ring\" ]; then\n"
            "  h=$(/usr/bin/shasum -a 256 \"$ring\" 2>/dev/null | cut -c1-12)\n"
            "  [ -n \"$h\" ] && printf 'notrest-access: ok ring=%s path=%s\\n' \"$h\" \"$ring\"\n"
            "fi\n"
            "exit 0\n")
    os.chmod(fp, 0o755)
    return d


def check_access_gate(root, plug, _skills):
    """4.8: without an access key, does the harness go QUIET without going PERMISSIVE?

    Two failure shapes, opposite in direction and both fatal: a hook that still writes or
    injects (the gate is decorative), and a hook that stops DENYING (an expired licence
    becomes a security downgrade). Driven for real — each hook is RUN with the key removed
    and its output and exit code read. Nothing is inferred from source text.
    """
    ID = "ACCESS-GATE"
    law = ("without a valid access key every writing/injecting hook is silent and exits 0, "
           "the deny rules still deny, the committed keyring exists with a header, and "
           "SessionStart says ONE Atlas notice and nothing else")
    hooks_dir = os.path.join(plug, "hooks")
    if not os.path.isdir(hooks_dir):
        return [R(ID, "SKIP", law, "no hooks/ under %s" % rel(root, plug))]
    present = [h for h in GATED_HOOKS if os.path.isfile(os.path.join(hooks_dir, h))]
    keyring = os.path.join(plug, KEYRING_REL)
    out = []
    # ⛔ AN ABSENT KEYRING IS A FAILURE, NOT A SKIP. The clause is "the committed keyring
    # exists with a header"; skipping when it is missing meant deleting the keyring turned
    # the whole gate green — the one mutation the check most needs to catch.
    if not os.path.isfile(keyring):
        out.append(R(ID, "FAIL", law,
                     "%s is absent — the plugin ships no keyring, so no key can be valid "
                     "and the access gate cannot be enforced anywhere" % rel(root, keyring),
                     "commit the keyring (`atlas.py key --mint --label <who>` writes it) — "
                     "an absent keyring is not an unconfigured gate, it is a broken one"))
    elif not [l for l in (read(keyring) or "").splitlines() if l.strip().startswith("#")]:
        out.append(R(ID, "FAIL", law, "%s has no header line" % rel(root, keyring),
                     "open the keyring with a '# ...' line saying what it is and who mints "
                     "into it — a bare list of hashes tells a reader nothing"))
    if not present:
        out.append(R(ID, "SKIP", law, "none of the gated hooks are present"))
        return out

    # A scratch ESTABLISHED estate: a writer only writes where there is something to write
    # to, so an unestablished cwd would let every hook look innocent.
    est = tempfile.mkdtemp(prefix="notrest-eval-gate-")
    try:
        with open(os.path.join(est, "COORD.md"), "w", encoding="utf-8") as fh:
            fh.write("# COORD.md — session coordination ledger\n\n## LEDGER\n"
                     "- [2026-09-06 00:00Z] [eval] probe -> seeded | evidence: none\n")
        with open(os.path.join(est, "COORD-AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("# COORD-AGENTS.md — agent activity ledger\n\n## LEDGER\n")
    except OSError:
        pass
    env = dict(os.environ)
    env.pop("NOTREST_ACCESS_KEY", None)
    env["HOME"] = tempfile.mkdtemp(prefix="notrest-eval-nokey-")
    env["NOTREST_HOME"] = env["HOME"]
    env["CLAUDE_PROJECT_DIR"] = est
    before = _tree_state(est)

    noisy, broke = [], []
    for h in present:
        payload = json.dumps(WRITER_HOOKS.get(h, BANNER_PAYLOAD))
        try:
            pr = subprocess.run(["bash", os.path.join(hooks_dir, h)],
                                input=payload.encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=25, cwd=est, env=env)
        except (OSError, subprocess.SubprocessError) as exc:
            broke.append("%s (%s)" % (h, exc))
            continue
        if pr.returncode != 0:
            broke.append("%s exit %d" % (h, pr.returncode))
        said = (pr.stdout or b"").decode("utf-8", "replace").strip()
        if not said:
            continue
        if h == BANNER_HOOK:
            lines = [l for l in said.splitlines() if l.strip()]
            if len(lines) == 1 and BANNER_RE.search(lines[0]):
                continue
            noisy.append("%s (%d line(s); the banner exemption is ONE Atlas notice)"
                         % (h, len(lines)))
        else:
            noisy.append(h)
    if broke:
        out.append(R(ID, "FAIL", law, "keyless hooks did not exit 0: %s" % ", ".join(broke[:4]),
                     "a hook without a key must go quiet, never fail"))
    if noisy:
        out.append(R(ID, "FAIL", law,
                     "keyless hooks still wrote to stdout: %s" % ", ".join(noisy[:4]),
                     "gate the hook body behind `atlas.py key --check` so it injects "
                     "nothing without a key"))
    wrote = _tree_state(est) - before
    if wrote:
        out.append(R(ID, "FAIL", law,
                     "keyless hooks CHANGED the estate: %s" % ", ".join(sorted(wrote)[:4]),
                     "a hook without a key must not write to the ledgers either — silence "
                     "on stdout is not the same as leaving the estate alone"))

    # ── the three clauses a reverted hardening would silently drop ──────────────────
    sp, spkey = _scratch_plugin(plug)
    if sp is None:
        out.append(R(ID, "SKIP", law, "no atlas.py to copy — the verifier probes are "
                                      "skipped, never assumed"))
    else:
        shooks = os.path.join(sp, "hooks")
        sstart = os.path.join(shooks, BANNER_HOOK)
        base = dict(env)
        base["CLAUDE_PROJECT_DIR"] = est

        def dark_probe(label, extra_env, drop_key=True, fix=None):
            e = dict(base)
            if drop_key:
                e.pop("NOTREST_ACCESS_KEY", None)
            e.update(extra_env)
            try:
                pr = subprocess.run(["bash", sstart],
                                    input=json.dumps(BANNER_PAYLOAD).encode(),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=25, cwd=est, env=e)
            except (OSError, subprocess.SubprocessError):
                return
            said = (pr.stdout or b"").decode("utf-8", "replace")
            if not _is_dark(said):
                out.append(R(ID, "FAIL", law, "%s — the hook went LIVE: %s"
                             % (label, " / ".join(said.split())[:160]), fix))

        # (1) ⛔ A FAKE python3 ON $PATH MUST NOT BE ABLE TO SAY "licensed". With no key
        # the honest answer is dark; a stub that exits 0 for every argument is exactly the
        # attack. Two independent clauses have to hold for this to stay dark: the hook
        # prefers /usr/bin/python3 over $PATH, and it demands atlas.py's stdout sentinel.
        # On a machine with no /usr/bin/python3 the sentinel alone must refuse the stub.
        if os.path.isfile(sstart):
            stub = _stub_bin()
            dark_probe("a stub python3 first on $PATH answered 'licensed'",
                       {"PATH": stub + os.pathsep + base.get("PATH", "")},
                       fix="prefer /usr/bin/python3 over $PATH AND require atlas.py's "
                           "stdout sentinel — an exit code alone is a claim anything can "
                           "make")

            # (2) ⛔ THE SENTINEL, ALONE. A verifier that exits 0 and says NOTHING is not
            # an answer. Given a VALID key here, only the sentinel requirement can keep
            # this dark — so deleting that requirement flips this arm.
            sa = os.path.join(sp, "skills", "atlas", "scripts", "atlas.py")
            try:
                with open(sa, "w", encoding="utf-8") as fh:
                    fh.write("#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
                dark_probe("a verifier that exits 0 with the sentinel stripped was believed",
                           {}, drop_key=False,
                           fix="require the `notrest-access: ok ring=<hash>` sentinel on "
                               "stdout, not just exit 0")
            except OSError:
                pass

        # (3) ⛔ THE PULSE IS A WRITER. Keyless, with a root handed to it, it must write
        # NOTHING and fork NOTHING — silence on stdout is not the same as doing no work.
        pulse = os.path.join(shooks, "estate-pulse.sh")
        if os.path.isfile(pulse):
            pest = tempfile.mkdtemp(prefix="notrest-eval-pulse-")
            try:
                with open(os.path.join(pest, "COORD.md"), "w", encoding="utf-8") as fh:
                    fh.write("# COORD.md — session coordination ledger\n\n## LEDGER\n")
            except OSError:
                pass
            before_p = _tree_state(pest)
            counter = os.path.join(tempfile.mkdtemp(prefix="notrest-eval-fork-"), "forks")
            cbin = tempfile.mkdtemp(prefix="notrest-eval-cbin-")
            cp = os.path.join(cbin, "python3")
            try:
                with open(cp, "w", encoding="utf-8") as fh:
                    fh.write("#!/bin/sh\nprintf 'x' >> %s\nexit 0\n" % counter)
                os.chmod(cp, 0o755)
                e = dict(base)
                e.pop("NOTREST_ACCESS_KEY", None)
                e["PATH"] = cbin + os.pathsep + base.get("PATH", "")
                e["NR_PULSE_ROOT"] = pest
                e["NR_PULSE_DAEMON"] = "1"
                subprocess.run(["bash", pulse, pest, "manual"], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=25, cwd=pest, env=e)
            except (OSError, subprocess.SubprocessError):
                pass
            wrote_p = _tree_state(pest) - before_p
            forks = os.path.getsize(counter) if os.path.isfile(counter) else 0
            if wrote_p or forks:
                out.append(R(ID, "FAIL", law,
                             "keyless estate-pulse.sh did work: %d file(s) written (%s), "
                             "%d fork(s)" % (len(wrote_p),
                                             ", ".join(sorted(wrote_p)[:3]) or "-", forks),
                             "gate estate-pulse.sh on NR_ACCESS before it touches the "
                             "estate — a writer that runs unlicensed is the gate's whole "
                             "point"))

    for dh in DENY_HOOKS:
        path = os.path.join(hooks_dir, dh)
        if not os.path.isfile(path):
            continue
        if dh == "spawn-gate.sh":
            payload = json.dumps(SPAWN_DENY_PAYLOAD)
            what = "a Task spawned with NO model"
        else:
            probe = _derived_deny_probe(read(path))
            if not probe:
                out.append(R(ID, "SKIP", law, "could not derive a denied command from %s — "
                                              "the deny probe is skipped, never guessed"
                             % rel(root, path)))
                continue
            payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": probe}})
            what = "a command its own rules deny"
        try:
            pr = subprocess.run(["bash", path], input=payload.encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=25, cwd=est, env=env)
        except (OSError, subprocess.SubprocessError):
            continue
        if pr.returncode != 2:
            out.append(R(ID, "FAIL", law,
                         "%s ALLOWED %s with no key present (exit %d, expected 2)"
                         % (dh, what, pr.returncode),
                         "the deny rules must not depend on the key — an expired licence "
                         "must never become a security downgrade"))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law,
                        "%d gated hook(s) silent and exit 0 without a key; deny rules "
                        "still deny; keyring present with a header" % len(present)))
    return out


# ---------------------------------------------------------------------------
# DOC-ROSTER-PARITY (4.9). The suite's own SKILL.md carries a table of the checks. It
# said "The sixteen checks" over a seventeen-check roster for two releases, three lines
# above the roster it described, and nobody caught it until a lane counted by hand — the
# exact failure this suite exists to prevent, committed by this suite's own document.
# The doctrine answers it: a claim with no fingerprint drifts. So the table IS the
# fingerprint, and this check reads both halves out of the shipped files.
#
# ⛔ WHAT IT COMPARES, AND WHY THAT AND NOT SOMETHING EASIER: the doc's rows against the
# REGISTERED roster — the `ID` constant inside each function named in `CHECKS` — not
# against every `ID = "…"` in the file. The difference is the whole point: a check that
# is written, documented and never registered would pass a naive id-scan while running
# never once. Documented-but-not-running is the drift that flatters hardest.
#
# ⛔ WHAT IT DOES NOT SEE: whether a row's PROSE describes its check. A row can name the
# right id and lie about the law underneath it; that is a reader's job and a refuter's,
# and no static test replaces it. It judges the SET of names, and the spelled count.
DOC_ROW_RE = re.compile(r"^\|\s*`([A-Z0-9][A-Z0-9-]*)`\s*\|", re.M)
DOC_HEADING_RE = re.compile(r"^#+\s+The\s+([A-Za-z-]+|\d+)\s+checks\s*$", re.M)
DOC_SUBTITLE_RE = re.compile(r"^\*([A-Za-z-]+|\d+)\s+as of\b", re.M)
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _spell(n):
    """20 -> 'twenty' · 22 -> 'twenty-two'. Bounded to 0..99; a roster past that has a
    bigger problem than its heading."""
    if n < 0 or n > 99:
        return str(n)
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + ("-" + _ONES[ones] if ones else "")


def _registered_check_ids(src):
    """The ids of the checks that actually RUN, in roster order. None if unparseable."""
    m = re.search(r"^CHECKS = \[(.*?)\]", src, re.M | re.S)
    if not m:
        return None
    ids = []
    for name in re.findall(r"\bcheck_[a-z_]+", m.group(1)):
        fn = re.search(r"^def %s\(.*?(?=^def |\Z)" % re.escape(name), src, re.M | re.S)
        if not fn:
            continue
        im = re.search(r'^\s*ID = "([A-Z0-9][A-Z0-9-]*)"', fn.group(0), re.M)
        if im:
            ids.append(im.group(1))
    return ids or None


def check_doc_roster(root, plug, skills):
    ID = "DOC-ROSTER-PARITY"
    law = ("the suite's own SKILL.md names exactly the checks it ships — every registered "
           "check has a table row, every row is a check that runs, and a spelled count "
           "matches the roster")
    if "eval" not in skills:
        return [R(ID, "SKIP", law, "no eval skill in this tree — no roster to document")]
    d, doc = skills["eval"]
    src_path = os.path.join(d, "scripts", "eval.py")
    src = read(src_path)
    if not src:
        return [R(ID, "SKIP", law, "%s is absent or unreadable" % rel_p(root, src_path))]
    shipped = _registered_check_ids(src)
    if shipped is None:
        return [R(ID, "SKIP", law, "%s ships no parseable CHECKS roster" % rel_p(root, src_path))]
    rows = DOC_ROW_RE.findall(doc)
    f = rel_p(root, os.path.join(d, "SKILL.md"))
    if not rows:
        return [R(ID, "SKIP", law, "%s carries no check table" % f)]
    out = []
    missing = [i for i in shipped if i not in rows]
    extra = [i for i in rows if i not in shipped]
    if missing:
        out.append(R(ID, "FAIL", law,
                     "%s  (ships %d check(s) the table never names: %s)"
                     % (f, len(missing), ", ".join(missing)),
                     "add a row per missing check, in the table's existing shape"))
    if extra:
        out.append(R(ID, "FAIL", law,
                     "%s  (names %d check(s) that do not run: %s)"
                     % (f, len(extra), ", ".join(extra)),
                     "delete the row, or register the check in CHECKS — a documented "
                     "check that never runs is worse than an undocumented one"))
    dupes = sorted({i for i in rows if rows.count(i) > 1})
    if dupes:
        out.append(R(ID, "FAIL", law, "%s  (row(s) listed twice: %s)" % (f, ", ".join(dupes)),
                     "one row per check"))
    # the spelled count, wherever the document states one. Optional by ruling — a table
    # with no number stated cannot be wrong about it.
    want, counted = len(shipped), []
    for label, rx in (("heading", DOC_HEADING_RE), ("subtitle", DOC_SUBTITLE_RE)):
        m = rx.search(doc)
        if not m:
            continue
        said = m.group(1).lower()
        counted.append(label)
        if said not in (_spell(want), str(want)):
            out.append(R(ID, "FAIL", law,
                         "%s:%d  the %s says %r; %d check(s) ship"
                         % (f, lineno(doc, m.start()), label, m.group(1), want),
                         "say %r (or %d) — or drop the number, which cannot go stale"
                         % (_spell(want), want)))
    if not any(r.status == "FAIL" for r in out):
        out.insert(0, R(ID, "PASS", law,
                        "%s names exactly the %d shipped check(s); %s"
                        % (f, want, ("count agreed in the " + " and ".join(counted))
                           if counted else "no count stated, so none can drift")))
    return out


CHECKS = [check_network, check_kernel, check_release_surface, check_learning_loop,
          check_access_gate,
          # 4.9 — the Atlas secret-handling laws: the mode the token is written with, the
          # git config that hands it out, the verifier's provenance, and the repo it must
          # never be typed into.
          check_token_store, check_helper_scope, check_verifier_vendored,
          check_no_token_literal,
          check_offload, check_labels, check_scripts, check_references,
          check_estate, check_selfcheck, check_triggers, check_safety,
          check_hooks, check_router, check_route_parity, check_route_conformance,
          check_doc_roster]


# ---------------------------------------------------------------------------
# behavior cases — opt-in, bounded, code-graded. NEVER an LLM judge.
# ---------------------------------------------------------------------------
def grade_offload_spawn_directive(text):
    """PASS iff the answer names one supported explicit worker model and no downgrade."""
    if DOWNGRADE_RE.search(text):
        return False, "named a downgraded model for a spawn"
    named = CLAUDE_MODEL_RE.search(text) or CODEX_MODEL_RE.search(text)
    return bool(named), ("supported worker model named" if named else "no worker model named")


def grade_graph_scanner_preference(text):
    """PASS iff the answer reaches for graph.py rather than reading files itself."""
    if re.search(r"graph\.py|/graph\b", text, re.I):
        return True, "routed to the scanner"
    return False, "no scanner reference — the model read files itself"


BEHAVIOR_CASES = {
    "offload-spawn-directive": {
        "prompt": "Spawn a lane to audit the release notes. Show the exact Agent call you would make.",
        "grader": grade_offload_spawn_directive,
        "law": "OFFLOAD-POLICY — every offloaded job uses the runtime's explicit worker",
    },
    "graph-scanner-preference": {
        "prompt": "How do the files in this repo connect? Answer with the first tool call you make.",
        "grader": grade_graph_scanner_preference,
        "law": "SCRIPT-OWNS-SCANNING — the scanner reads the files, the model never has to",
    },
}


def run_behavior(name, surface="auto"):
    case = BEHAVIOR_CASES.get(name)
    if not case:
        sys.stderr.write("unknown case %r; have: %s\n"
                         % (name, ", ".join(sorted(BEHAVIOR_CASES))))
        return 2
    print("BEHAVIOR CASE  %s" % name)
    print("law     : %s" % case["law"])
    if surface == "auto":
        surface = "codex" if (os.environ.get("CODEX_THREAD_ID") or
                              os.environ.get("CODEX_SANDBOX")) else "claude"
    if surface == "codex":
        print("command : run as a bounded Codex task with model gpt-5.6-sol: %r"
              % case["prompt"])
    else:
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
    b.add_argument("--surface", choices=("auto", "codex", "claude"), default="auto")
    ns = ap.parse_args(argv)
    if ns.cmd == "check":
        return run_check(os.path.abspath(ns.root), ns.json, ns.baseline)
    if ns.cmd == "behavior":
        return run_behavior(ns.case, ns.surface)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
