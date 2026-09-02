#!/usr/bin/env python3
"""gate-check — run a commission's declared gates and record the evidence.

THE PROBLEM IT CLOSES (docket item 8a; the shape borrowed from leonxlnx/unlazy, owner-
pointed 2026-09-01). Every commission in this estate already carries a done-when clause,
and every one of them is PROSE: "tests green", "the fixture passes", "eval exits 0". A
lane reads that prose and then GRADES ITSELF against it, which is the one grading
arrangement this harness refuses everywhere else. The remedy is not more prose. It is to
let the commission carry the check as CODE, so the same sentence that states the
contract can be executed by something that is not the worker.

THE FORMAT — two line-oriented directives, anywhere in a markdown commission:

    CHECK: bash plugins/notrest/skills/eval/scripts/pretool-fixture.sh
    EXPECT: 0 failed

  · `CHECK:` opens a gate and is the shell line to run (bash -c, cwd = --cwd or the
    file's estate root).
  · `EXPECT:` is a regular expression that must be found in the combined output.
    Zero or more per gate; every one of them must match. A gate with no EXPECT passes
    on exit 0 alone.
  · `GATE:` immediately before a CHECK names it, so the report can say "fixture green"
    rather than quoting sixty characters of shell.
  · Directives inside a fenced code block are DOCUMENTATION and are never executed —
    a commission that shows you how to write a gate must not thereby run one.

A gate passes iff the command exits 0 AND every EXPECT matches. Anything else is red.

WHAT IT RECORDS. Each gate reports EVIDENCE: the exit code, the byte length and the
sha256 of the combined output, and (once, at the top) the resolved shell, the cwd and
the PATH the checks actually ran under — because "it passed on my machine" is a claim
about an environment, and an unfingerprinted pass cannot be told apart from a pass in
some other environment later.

EXIT CODES:  0 every gate green
             2 the file is missing or unreadable at the OS level
             3 the declared contract could not be PARSED — an unterminated fence, or a
               file that exists and yields no gates at all. Never a green: an existing
               gates file is a declaration that a contract exists, and failing to read
               one is not the same as having none.
             5 at least one gate is RED, each named

This is an INSTRUMENT, not a hook: it is loud, and it exits nonzero on purpose.
hooks/completion-gate.sh is the hook that consumes it and it does the fail-open work.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

# RB-8 (refuter, 2026-09-01): a CHECK is arbitrary shell and its output was captured
# whole. A gate emitting 20 MB cost ~100 MB RSS inside a Stop hook — measured. Output
# now lands in a temp file and only this window is ever read into memory; the total is
# still known (from the file size) and the truncation is STATED next to the fingerprint,
# because a sha over a silently clipped window fingerprints something other than what
# it names.
CAP = 1024 * 1024

# RB-2 (refuter, HIGH): EXPECT is a user-supplied regex run against user-supplied output.
# `(a+)+b` against 48 a's never returned — `timeout 15` had to kill the Stop hook. Every
# match now runs under this alarm, and a pattern that cannot be decided makes the gate
# RED rather than making the session hang.
EXPECT_MATCH_SECONDS = 5

CHECK_RE = re.compile(r"^\s{0,3}(?:[-*]\s+)?CHECK:\s*(.+?)\s*$")
EXPECT_RE = re.compile(r"^\s{0,3}(?:[-*]\s+)?EXPECT:\s*(.*?)\s*$")
NAME_RE = re.compile(r"^\s{0,3}(?:[-*]\s+)?GATE:\s*(.+?)\s*$")
FENCE_RE = re.compile(r"^\s{0,3}(```+|~~~+)")


def sha(b):
    if isinstance(b, str):
        b = b.encode("utf-8", "replace")
    return hashlib.sha256(b).hexdigest()


def parse(text):
    """→ (gates, problem). `problem` is a string when the file cannot be trusted to
    have been read as its author meant it — currently: a fence that never closes.

    RB-1 (refuter, HIGH, 2026-09-01). An unterminated fence used to swallow every gate
    below it and the report said "0 gates, 0 red · exit 0": the estate's real
    `CHECK: false` was inside the swallowed region and the contract came back GREEN.
    Skipping fenced text is right — a commission that SHOWS you how to write a gate must
    not run one — but a fence that never closes is not documentation, it is a file we
    failed to read. So the swallowed directives are counted and reported, and the caller
    turns that into a refusal rather than a pass.
    """
    gates, fence, fence_line = [], "", 0
    swallowed = 0
    pending_name = ""
    for n, raw in enumerate(text.splitlines(), 1):
        f = FENCE_RE.match(raw)
        if f:
            tok = f.group(1)
            if not fence:
                fence, fence_line = tok[0] * 3, n
            elif tok.startswith(fence):
                fence, fence_line = "", 0
            continue
        if fence:
            if CHECK_RE.match(raw) or EXPECT_RE.match(raw) or NAME_RE.match(raw):
                swallowed += 1
            continue
        m = NAME_RE.match(raw)
        if m:
            pending_name = m.group(1)
            continue
        m = CHECK_RE.match(raw)
        if m:
            gates.append({"name": pending_name or "", "check": m.group(1),
                          "expect": [], "line": n})
            pending_name = ""
            continue
        m = EXPECT_RE.match(raw)
        if m and gates and m.group(1):
            gates[-1]["expect"].append(m.group(1))
    for i, g in enumerate(gates, 1):
        if not g["name"]:
            g["name"] = "gate %d" % i
    problem = ""
    if fence:
        problem = ("unterminated code fence opened on line %d — it swallowed %d "
                   "CHECK/EXPECT/GATE directive(s) below it, so this file was not read "
                   "as its author wrote it" % (fence_line, swallowed))
    return gates, problem


def run_gate(g, cwd, timeout, shell):
    out, rc, total = "", None, 0
    # Output goes to a FILE, never straight into memory: only the first CAP bytes are
    # ever read back, while the file's size still gives the honest total.
    try:
        with tempfile.TemporaryFile() as fh:
            try:
                p = subprocess.run([shell, "-c", g["check"]], cwd=cwd, timeout=timeout,
                                   stdout=fh, stderr=subprocess.STDOUT)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = 124
            fh.flush()
            total = fh.tell()
            fh.seek(0)
            out = fh.read(CAP).decode("utf-8", "replace")
        if rc == 124 and not out.strip():
            out = "gate-check: TIMEOUT after %ss\n" % timeout
    except Exception as exc:                                  # unrunnable command
        out = "gate-check: could not run: %s\n" % exc
        rc, total = 127, 0
    truncated = total > CAP
    kept = min(total, CAP) if total else len(out.encode("utf-8", "replace"))

    missed, undecided = [], []
    for e in g["expect"]:
        verdict = _search(e, out)
        if verdict is None:
            undecided.append(e)
        elif not verdict:
            missed.append(e)
    return {"name": g["name"], "check": g["check"], "expect": list(g["expect"]),
            "line": g["line"], "exit": rc, "bytes": kept, "total_bytes": total,
            "truncated": truncated,
            "outsha": sha(out), "missed": missed, "undecided": undecided,
            "pass": rc == 0 and not missed and not undecided, "output": out}


class _MatchTimeout(Exception):
    pass


def _search(pattern, text):
    """True / False / None, where None means THE MATCH COULD NOT BE DECIDED.

    EXPECT is a regex; a pattern that is not valid regex falls back to substring, so a
    commission written by a human is never red for a stray bracket. And every match runs
    under an alarm: Python's engine backtracks, `(a+)+b` against a wall of a's never
    returns, and this code runs inside a Stop hook — an undecidable pattern must cost a
    RED gate, never a wedged session. SIGALRM is main-thread/Unix only; where it cannot
    be armed the match still runs, exactly as before, rather than being skipped.
    """
    armed = False
    try:
        def _boom(_sig, _frm):
            raise _MatchTimeout()
        signal.signal(signal.SIGALRM, _boom)
        signal.alarm(EXPECT_MATCH_SECONDS)
        armed = True
    except Exception:
        armed = False
    try:
        try:
            return re.search(pattern, text, re.M) is not None
        except re.error:
            return pattern in text
    except _MatchTimeout:
        return None
    finally:
        if armed:
            try:
                signal.alarm(0)
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(prog="gate-check.py", description=__doc__.split("\n")[0])
    ap.add_argument("file", help="a commission/gate file carrying CHECK:/EXPECT: blocks")
    ap.add_argument("--cwd", default=None, help="run the checks here (default: the file's dir)")
    ap.add_argument("--timeout", type=int, default=120, help="per-CHECK seconds (default 120)")
    ap.add_argument("--budget", type=int, default=0,
                    help="wall-clock seconds across ALL gates (0 = unbounded); gates the "
                         "budget cannot reach are RED, never skipped")
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    ap.add_argument("--quiet", action="store_true", help="only the verdict and the red gates")
    a = ap.parse_args()

    try:
        with open(a.file, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as exc:
        sys.stderr.write("gate-check: cannot read %s (%s)\n" % (a.file, exc))
        return 2

    cwd = a.cwd or os.path.dirname(os.path.abspath(a.file)) or "."
    shell = shutil.which("bash") or "/bin/bash"
    env = {"shell": shell, "cwd": os.path.realpath(cwd), "PATH": os.environ.get("PATH", "")}
    gates, problem = parse(text)

    # ── EXIT 3 · THE DECLARED CONTRACT COULD NOT BE READ (RB-1, seat ruling).
    # Two shapes, one verdict. An unterminated fence means the file was not read as
    # written. And a file that EXISTS but yields zero gates is the same failure wearing
    # a friendlier face: the file's existence IS the estate's declaration that it has a
    # contract, so "I found nothing in it" is a parse failure, never "you are done".
    # Absence of the file is the only silent-green path, and it lives in the hook.
    if problem or not gates:
        # Two different truths, one exit (review round, 2026-09-01): a swallowed or
        # broken parse is UNREADABLE; a clean parse that found nothing armed is a
        # DECLARED contract with no gate — both refuse to certify, with true sentences.
        if problem:
            detail = "CONTRACT UNREADABLE: %s" % problem
        else:
            problem = ("it declares no gate — a gates file with nothing armed cannot "
                       "certify completion; arm a CHECK: or delete the file")
            detail = "CONTRACT DECLARES NO GATE: %s" % problem
        if a.json:
            print(json.dumps({"file": os.path.abspath(a.file), "env": env,
                              "count": 0, "red": 0, "verdict": "UNREADABLE",
                              "problem": problem, "gates": []}, indent=2))
        else:
            print("gate-check: %s" % os.path.abspath(a.file))
            print(detail)
            print("gate-check: contract unreadable — no verdict was reached")
        sys.stderr.write(detail + "\n")
        return 3

    # Wall-clock budget across ALL gates (review round: N × --timeout blew past the
    # harness's 60s Stop cap, and a hook killed mid-verdict fails open — the one case
    # where the gate matters most). Gates that the budget could not reach are RED with
    # the reason: an unchecked gate is not a green gate.
    results = []
    deadline = (time.monotonic() + a.budget) if a.budget else None
    for g in gates:
        if deadline is not None:
            left = deadline - time.monotonic()
            if left <= 1:
                results.append({"name": g["name"], "check": g["check"],
                                "expect": list(g["expect"]), "line": g["line"],
                                "exit": None, "bytes": 0, "total_bytes": 0,
                                "truncated": False, "outsha": "",
                                "missed": list(g["expect"]), "undecided": [],
                                "pass": False,
                                "output": "NOT RUN — wall-clock budget exhausted "
                                          "before this gate; an unchecked gate is red"})
                continue
            results.append(run_gate(g, cwd, min(a.timeout, int(left)), shell))
        else:
            results.append(run_gate(g, cwd, a.timeout, shell))
    red = [r for r in results if not r["pass"]]

    if a.json:
        print(json.dumps({
            "file": os.path.abspath(a.file), "env": env,
            "count": len(results), "red": len(red),
            "verdict": "RED" if red else "GREEN",
            "gates": [{k: v for k, v in r.items() if k != "output"} for r in results],
        }, indent=2))
        return 5 if red else 0

    print("gate-check: %s" % os.path.abspath(a.file))
    print("ENV: shell=%s · cwd=%s · pathsha=%s" % (env["shell"], env["cwd"],
                                                   sha(env["PATH"])[:16]))
    for i, r in enumerate(results, 1):
        print("")
        print("GATE %d · %s   (line %d)" % (i, r["name"], r["line"]))
        print("  CHECK : %s" % r["check"])
        for e in r["expect"]:
            flag = ""
            if e in r["undecided"]:
                flag = "   <-- DID NOT COMPLETE"
            elif e in r["missed"]:
                flag = "   <-- UNMATCHED"
            print("  EXPECT: %s%s" % (e, flag))
        print("  EVIDENCE: exit=%s bytes=%d outsha=%s%s"
              % (r["exit"], r["bytes"], r["outsha"],
                 (" truncated=yes total_bytes=%d (sha covers the kept window only)"
                  % r["total_bytes"]) if r["truncated"] else ""))
        if not a.quiet and r["output"].strip():
            tail = r["output"].rstrip().splitlines()[-8:]
            for ln in tail:
                print("  | %s" % ln[:200])
        print("  RESULT: %s" % ("PASS" if r["pass"] else "RED"))
    print("")
    print("gate-check: %d gates, %d red" % (len(results), len(red)))
    if red:
        for r in red:
            if r["undecided"]:
                why = ("EXPECT did not complete (catastrophic pattern?) after %ss: %s"
                       % (EXPECT_MATCH_SECONDS, "; ".join(r["undecided"])))
            elif r["exit"] != 0:
                why = "exit=%s" % r["exit"]
            else:
                why = "EXPECT unmatched: %s" % "; ".join(r["missed"])
            print("RED: %s — %s   [%s]" % (r["name"], why, r["check"]))
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
