#!/usr/bin/env python3
"""eval — the harness's law-conformance suite.

Doctrine: a law that is well-encoded leaves a STATIC FINGERPRINT in the shipped
files. This suite checks the fingerprint, not the behavior. Pure stdlib, pure
read, target < 2 seconds, zero model tokens. Never repairs, never bumps.

Exit: 0 all pass · 5 warnings only · 6 any FAIL · 2 usage error.
"""

import argparse
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


CHECKS = [check_offload, check_labels, check_scripts, check_estate,
          check_selfcheck, check_triggers, check_safety, check_hooks,
          check_router]


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
def run_check(root, as_json):
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
    if as_json:
        print(json.dumps({"verdict": verdict, "root": root, "skills": len(skills),
                          "fails": fails, "warns": warns,
                          "seconds": round(elapsed, 3),
                          "results": [r.as_dict() for r in results]}, indent=2))
    else:
        for r in results:
            print("%-5s %-22s %s — %s" % (r.status, r.check, r.law, r.evidence))
            if r.fix and r.status in ("FAIL", "WARN"):
                print("      fix: %s" % r.fix)
        print("SUMMARY %s — %d skills, %d checks, %d fail, %d warn, %.2fs, 0 model tokens"
              % (verdict, len(skills), len(CHECKS), fails, warns, elapsed))
    return 6 if fails else (5 if warns else 0)


def main(argv):
    ap = argparse.ArgumentParser(prog="eval.py", description="notrest law-conformance suite")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="static law conformance over the shipped files")
    c.add_argument("--root", default=os.getcwd())
    c.add_argument("--json", action="store_true")
    b = sub.add_parser("behavior", help="print an opt-in bounded model case (does not run it)")
    b.add_argument("--case", required=True)
    b.add_argument("--list", action="store_true")
    ns = ap.parse_args(argv)
    if ns.cmd == "check":
        return run_check(os.path.abspath(ns.root), ns.json)
    if ns.cmd == "behavior":
        return run_behavior(ns.case)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
