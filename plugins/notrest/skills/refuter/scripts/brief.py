#!/usr/bin/env python3
"""brief.py — mint a refuter brief from references/brief-template.md.

The brief is the seat's job, and the parts the seat keeps getting wrong are the
mechanical ones: pasting the artifact (so the bytes under review are pinned), naming an
isolated scratch dir, and stamping a budget. This fills those from the target itself and
leaves exactly two fields for the seat's judgment — the contract paragraph and the
specialized attack ladder — rather than letting a half-filled template reach a lane.

  brief.py --target <path> [--budget 12] [--minutes 20] [--scratch DIR]
           [--contract TEXT | --contract-file F] [--priorities FILE] [--no-inline]

stdout = the brief, ready to paste as the lane's whole prompt.
stderr = what the seat still has to fill in.
Exit: 0 written · 2 usage/missing target · 5 --strict and a seat field is unfilled.
"""
import argparse, hashlib, os, pathlib, re, sys, tempfile
from datetime import datetime

SEAT = ("<<< SEAT MUST FILL: %s — a lane cannot infer this, and a refuter that does not "
        "know it can only find crashes >>>")
FENCE = {".py": "python", ".sh": "bash", ".js": "javascript", ".ts": "typescript",
         ".json": "json", ".md": "markdown", ".yaml": "yaml", ".yml": "yaml"}


def die(msg, code=2):
    sys.stderr.write("brief: %s\n" % msg)
    sys.exit(code)


def build(a):
    tpl_path = pathlib.Path(__file__).resolve().parent.parent / "references" / "brief-template.md"
    if not tpl_path.exists():
        die("no template at %s" % tpl_path)
    tpl = tpl_path.read_text(encoding="utf-8")

    target = pathlib.Path(a.target).resolve()
    if not target.is_file():
        die("no such target file: %s" % target)
    raw = target.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    nbytes, nlines = len(raw), raw.count(b"\n") + 1

    scratch = pathlib.Path(a.scratch) if a.scratch else pathlib.Path(
        tempfile.gettempdir()) / "notrest-refuter" / ("%s-%s" % (
            re.sub(r"[^A-Za-z0-9_.-]", "-", target.stem),
            datetime.now().strftime("%Y%m%d-%H%M%S")))
    scratch.mkdir(parents=True, exist_ok=True)

    contract = a.contract or ""
    if a.contract_file:
        contract = pathlib.Path(a.contract_file).read_text(encoding="utf-8").strip()
    priorities = ""
    if a.priorities:
        priorities = pathlib.Path(a.priorities).read_text(encoding="utf-8").strip()

    if a.no_inline:
        artifact = ("`%s` — **current working tree, may change under you**; %d bytes, "
                    "%d lines, sha256 `%s` at brief time. Re-hash before you report, and "
                    "say so if it moved." % (target, nbytes, nlines, sha))
    else:
        lang = FENCE.get(target.suffix, "")
        text = raw.decode("utf-8", errors="replace")
        artifact = ("`%s` — %d bytes, %d lines, sha256 `%s`. These are the bytes under "
                    "review; if the file on disk no longer hashes to this, say so.\n\n"
                    "```%s\n%s\n```" % (target, nbytes, nlines, sha, lang,
                                        text.rstrip("\n")))

    subs = [
        (re.compile(r"`<absolute path or \"inline below\">`"),
         "`%s` — inlined below (sha256 `%s`)" % (target, sha[:16])),
        (re.compile(r"`<One paragraph:.*?>`", re.S),
         contract or (SEAT % "the target's CONTRACT in one paragraph: what must never "
                             "happen if this artifact is correct, plus its own success "
                             "banner verbatim")),
        (re.compile(r"`<Paste the artifact inline.*?>`", re.S), artifact),
        (re.compile(r"`<absolute path to an isolated scratch dir>`"), "`%s`" % scratch),
        (re.compile(r"`<Specialize the generic ladder.*?>`", re.S),
         priorities or (SEAT % "the attack ladder specialized in THIS target's nouns — "
                               "drop rungs that cannot apply, renumber; the order decides "
                               "what gets cut when the budget runs out")),
        (re.compile(r"~12 tool calls, `<N>` minutes\."),
         "~%d tool calls, %d minutes." % (a.budget, a.minutes)),
    ]
    out = tpl
    for pat, rep in subs:
        out, n = pat.subn(lambda _m, r=rep: r, out, count=1)
        if not n:
            sys.stderr.write("brief: WARNING — template placeholder not found for %r; "
                             "the template may have drifted from this script\n"
                             % pat.pattern[:40])
    return out, scratch, sha


def main():
    ap = argparse.ArgumentParser(description="mint a filled refuter brief")
    ap.add_argument("--target", required=True)
    ap.add_argument("--budget", type=int, default=12, help="tool calls (default 12)")
    ap.add_argument("--minutes", type=int, default=20)
    ap.add_argument("--scratch")
    ap.add_argument("--contract")
    ap.add_argument("--contract-file", dest="contract_file")
    ap.add_argument("--priorities")
    ap.add_argument("--no-inline", action="store_true",
                    help="cite the path instead of pinning the bytes inline")
    ap.add_argument("--strict", action="store_true",
                    help="exit 5 if a seat field is still unfilled")
    a = ap.parse_args()
    out, scratch, sha = build(a)
    sys.stdout.write(out if out.endswith("\n") else out + "\n")

    unfilled = out.count("<<< SEAT MUST FILL")
    sys.stderr.write("brief: target sha256 %s · scratch %s · budget %d calls / %d min\n"
                     % (sha[:16], scratch, a.budget, a.minutes))
    if unfilled:
        sys.stderr.write("brief: %d field(s) still need the SEAT — search the output for "
                         "'SEAT MUST FILL'. Do not send the brief with them in it: a lane "
                         "that does not know the contract can only find crashes.\n" % unfilled)
        if a.strict:
            sys.exit(5)
    else:
        sys.stderr.write("brief: complete — every field filled.\n")
    sys.stderr.write("brief: the lane runs on explicit model: \"opus\", a DIFFERENT lane "
                     "than the builder; receipt it with spend.py.\n")


if __name__ == "__main__":
    main()
