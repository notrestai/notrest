#!/usr/bin/env python3
"""director.py — the pipeline's structural instrument. Scaffold, hand off, VERIFY.

The director's own named failure mode is "the last stage never ran". Until now the
only guard against it was a checklist the MODEL ticks — the same model that would be
wrong about having run the stage. A box ticked by the party under audit is not
evidence. This script makes the three structural facts checkable by a machine:

  plan    --chain a,b,c --topic X [--root .] [--run DIR]
          Resolve every named skill's SKILL.md BEFORE any work starts (exit 2 on the
          first one that cannot be found — fail fast beats discovering it at stage 3),
          then scaffold the run: `NN-<skill>/` folders, the checklist file, run.json.

  handoff --run DIR --stage NN [--input P] [--output P]
          Write that stage's handoff manifest: input path + output path + sha256 of
          each. The sha is the point — it is what lets `verify` say the file that was
          handed forward is the file that is there now.

  verify  --run DIR
          Exit 3 on: an unticked checklist box, a stage folder that does not exist,
          an empty stage folder, a stage with no output file, a manifest whose input
          or output has gone missing, or a file whose sha256 no longer matches the
          manifest that promised it. Exit 0 only when the whole run is structurally
          sound.

What this script does NOT do, and must never be read as doing: it cannot tell whether
a stage's CONTENT is any good, whether the skill's workflow was actually performed, or
whether the handoff was semantically faithful. It checks that the artifacts exist, are
non-empty, are pointed at each other, and have not drifted. Structure is checkable;
faithfulness is the seat's job and the sub-skill's own self-check.

The escape hatch for post-3.8.0 record-writing skills: a stage folder may be empty IF
its handoff manifest names an output that exists elsewhere (a findings record, a file
in another tree). The work landing outside the folder is fine; the work being
unlocatable is not.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone

RUN_JSON = "run.json"
HANDOFF_JSON = "handoff.json"
CHECK_RE = re.compile(r"^\s*-\s*\[(?P<mark>[ xX])\]\s*(?P<label>\d{2}-[A-Za-z0-9._-]+)\s*$", re.M)
DOSSIER_RE = re.compile(r"dossier\.md$", re.I)
IGNORED_OUTPUTS = {HANDOFF_JSON, ".DS_Store"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def slugify(text, cap=48):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:cap].rstrip("-") or "run")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── skill resolution ─────────────────────────────────────────────────────────
def skill_search_paths(name, root):
    """The SKILL.md locations, in the order the skill body documents them.

    The sibling path is second on purpose: when this suite runs as an installed
    plugin, CLAUDE_PLUGIN_ROOT is set and wins; when it does not reach the shell,
    the siblings still sit next to this script's own skill directory, which is the
    one location that is true by construction.
    """
    here = pathlib.Path(__file__).resolve().parent          # .../skills/director/scripts
    out = []
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        out.append(pathlib.Path(env).expanduser() / "skills" / name / "SKILL.md")
    out.append(here.parent.parent / name / "SKILL.md")      # .../skills/<name>/SKILL.md
    out.append(pathlib.Path(root) / ".claude" / "skills" / name / "SKILL.md")
    out.append(pathlib.Path.home() / ".claude" / "skills" / name / "SKILL.md")
    return out


def resolve_skill(name, root):
    for p in skill_search_paths(name, root):
        if p.is_file():
            return p
    return None


# ── run-dir helpers ──────────────────────────────────────────────────────────
def pick_run_dir(root, explicit):
    """`pipeline/` for the first run; `pipeline-2/`, `-3/`, … for later ones.

    The skill body's rule is "suffix on collision"; suffixing the DIRECTORY rather
    than the topic keeps each run's numbered stage folders from colliding with the
    previous run's, which suffixing only the file names would not.
    """
    if explicit:
        return pathlib.Path(explicit).expanduser()
    base = pathlib.Path(root) / "pipeline"
    if not (base / RUN_JSON).exists():
        return base
    for n in range(2, 100):
        cand = pathlib.Path(root) / ("pipeline-%d" % n)
        if not (cand / RUN_JSON).exists():
            return cand
    sys.exit("too many pipeline runs under %s — archive some" % root)


def load_run(run_dir):
    p = pathlib.Path(run_dir).expanduser() / RUN_JSON
    if not p.is_file():
        print("[director] no %s under %s — this is not a planned run dir "
              "(run: director.py plan --chain … --topic …)" % (RUN_JSON, run_dir))
        sys.exit(2)
    try:
        return json.loads(p.read_text(encoding="utf-8")), p
    except ValueError as exc:
        print("[director] %s is not readable JSON: %s" % (p, exc))
        sys.exit(2)


def stage_by_number(run, nn):
    want = int(str(nn).lstrip("0") or "0")
    for st in run["chain"]:
        if st["n"] == want:
            return st
    return None


def stage_files(sdir):
    """Real output files in a stage folder — the manifest and OS litter excluded."""
    if not sdir.is_dir():
        return []
    return sorted(p for p in sdir.iterdir()
                  if p.is_file() and p.name not in IGNORED_OUTPUTS
                  and not p.name.startswith("."))


def pick_output(sdir):
    files = stage_files(sdir)
    if not files:
        return None
    dossiers = [p for p in files if DOSSIER_RE.search(p.name)]
    pool = dossiers or [p for p in files if p.suffix.lower() == ".md"] or files
    return max(pool, key=lambda p: p.stat().st_size)


# ── plan ─────────────────────────────────────────────────────────────────────
CHECKLIST_HEADING = "## Stage checklist (machine-verified — `director.py verify`)"


def background_text(run):
    b = ["# %s — pipeline background (orchestration log)" % run["topic"],
         "",
         "Planned %s by `director.py plan`. Chain: %s"
         % (run["created"], " → ".join(st["skill"] for st in run["chain"])),
         "",
         "Every stage is run by READING its `SKILL.md` from disk and performing that",
         "workflow — never by invoking the sub-skill through the Skill tool. This file is",
         "the source of truth the director re-reads before each stage, not its memory of",
         "the prompt.",
         "",
         "| # | skill | SKILL.md resolved at | stage folder |",
         "|---|---|---|---|"]
    for st in run["chain"]:
        b.append("| %02d | %s | `%s` | `%s/` |" % (st["n"], st["skill"], st["skill_md"], st["dir"]))
    b += ["",
          CHECKLIST_HEADING,
          "",
          "Tick a box only after that stage's files are on disk. `director.py verify`",
          "checks the boxes against the folders, so a tick with an empty folder behind it",
          "is caught rather than believed.",
          ""]
    for st in run["chain"]:
        b.append("- [ ] %s" % st["label"])
    b += ["",
          "## Handoff plan",
          "",
          "For each adjacent pair: what output of stage N feeds stage N+1, and how it maps",
          "to stage N+1's expected input. Fill this in during Phase 1; record the actual",
          "handoff with `director.py handoff --run <dir> --stage NN` as each stage lands.",
          ""]
    prev = None
    for st in run["chain"]:
        src = "seed: %s" % run["topic"] if prev is None else "output of %s" % prev
        b.append("- **%s** ← %s → _<how it is framed for %s>_" % (st["label"], src, st["skill"]))
        prev = st["label"]
    b += ["", "## Log", "", "- [%s] planned" % run["created"], ""]
    return "\n".join(b) + "\n"


def cmd_plan(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    chain = [s.strip() for s in re.split(r"[,\s]+|→|->", a.chain) if s.strip()]
    if not chain:
        print("[director] --chain named no skills")
        return 2

    # Resolve EVERYTHING before creating anything. A run half-scaffolded around a
    # missing skill is worse than no run: it looks resumable.
    resolved, missing = [], []
    for name in chain:
        p = resolve_skill(name, root)
        (resolved if p else missing).append((name, p))
    if missing:
        print("[director] cannot resolve %d skill(s) in the chain — nothing scaffolded:"
              % len(missing))
        for name, _ in missing:
            print("  %s — looked in:" % name)
            for cand in skill_search_paths(name, root):
                print("      %s" % cand)
        print("[director] fix the chain or ship the skill, then re-run plan "
              "(a missing skill is reported now, never discovered mid-run)")
        return 2

    run_dir = pick_run_dir(root, a.run)
    slug = slugify(a.topic)
    run = {
        "topic": a.topic,
        "slug": slug,
        "root": root.as_posix(),
        "run_dir": run_dir.expanduser().resolve().as_posix(),
        "created": now(),
        "checklist": "%sbackground.md" % slug,
        "dossier": "%sDossier.md" % slug,
        "chain": [{"n": i, "skill": name, "label": "%02d-%s" % (i, name),
                   "dir": "%02d-%s" % (i, name),
                   "skill_md": str(path)}
                  for i, (name, path) in enumerate(resolved, 1)],
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    for st in run["chain"]:
        (run_dir / st["dir"]).mkdir(exist_ok=True)
    (run_dir / run["checklist"]).write_text(background_text(run), encoding="utf-8")
    (run_dir / RUN_JSON).write_text(json.dumps(run, indent=1) + "\n", encoding="utf-8")

    print("[director] planned %d stage(s) in %s" % (len(run["chain"]), run_dir))
    for st in run["chain"]:
        print("  %s  →  %s/  (skill: %s)" % (st["label"], st["dir"], st["skill_md"]))
    print("[director] checklist: %s" % (run_dir / run["checklist"]))
    print("[director] next: run stage 01 by reading its SKILL.md and performing it; "
          "then director.py handoff --run %s --stage 01" % run_dir)
    return 0


# ── handoff ──────────────────────────────────────────────────────────────────
def cmd_handoff(a):
    run_dir = pathlib.Path(a.run).expanduser()
    run, _ = load_run(run_dir)
    st = stage_by_number(run, a.stage)
    if st is None:
        print("[director] no stage %s in this run (stages: %s)"
              % (a.stage, ", ".join(s["label"] for s in run["chain"])))
        return 2
    sdir = run_dir / st["dir"]

    # output — explicit, else the stage's dossier, else its biggest markdown file
    if a.output:
        out_p = pathlib.Path(a.output).expanduser()
        if not out_p.is_file():
            print("[director] --output %s does not exist" % out_p)
            return 3
    else:
        out_p = pick_output(sdir)
        if out_p is None:
            print("[director] stage %s has no output files in %s — run the stage before "
                  "recording its handoff (or pass --output for a record that landed "
                  "elsewhere)" % (st["label"], sdir))
            return 3

    # input — explicit, else the previous stage's recorded output, else the seed
    seed = False
    if a.input:
        in_p = pathlib.Path(a.input).expanduser()
        if not in_p.is_file():
            print("[director] --input %s does not exist" % in_p)
            return 3
        inp = {"path": in_p.as_posix(), "sha256": sha256(in_p), "bytes": in_p.stat().st_size}
    elif st["n"] == 1:
        seed = True
        inp = {"path": "(seed) %s" % run["topic"], "sha256": sha256_text(run["topic"]),
               "bytes": len(run["topic"].encode("utf-8")), "kind": "seed"}
    else:
        prev = stage_by_number(run, st["n"] - 1)
        prev_man = run_dir / prev["dir"] / HANDOFF_JSON
        prev_out = None
        if prev_man.is_file():
            try:
                prev_out = pathlib.Path(json.loads(prev_man.read_text(encoding="utf-8"))
                                        ["output"]["path"])
            except (ValueError, KeyError):
                prev_out = None
        if prev_out is None or not prev_out.is_file():
            prev_out = pick_output(run_dir / prev["dir"])
        if prev_out is None:
            print("[director] stage %s has nothing to hand forward — record %s's handoff "
                  "first, or pass --input" % (prev["label"], prev["label"]))
            return 3
        inp = {"path": prev_out.as_posix(), "sha256": sha256(prev_out),
               "bytes": prev_out.stat().st_size, "from": prev["label"]}

    man = {"stage": st["n"], "label": st["label"], "skill": st["skill"],
           "written": now(), "input": inp,
           "output": {"path": out_p.as_posix(), "sha256": sha256(out_p),
                      "bytes": out_p.stat().st_size},
           "external_output": os.path.relpath(str(out_p.resolve()),
                                              str(sdir.resolve())).startswith("..")}
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / HANDOFF_JSON).write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    print("[director] %s handoff recorded" % st["label"])
    print("   in : %s%s  sha256:%s"
          % (inp["path"], " (seed text)" if seed else "", inp["sha256"][:12]))
    print("   out: %s  sha256:%s  %d bytes"
          % (man["output"]["path"], man["output"]["sha256"][:12], man["output"]["bytes"]))
    return 0


# ── verify ───────────────────────────────────────────────────────────────────
def read_checklist(run_dir, run):
    p = run_dir / run.get("checklist", "")
    if not p.is_file():
        return None, p
    return {m.group("label"): m.group("mark").lower() == "x"
            for m in CHECK_RE.finditer(p.read_text(encoding="utf-8"))}, p


def cmd_verify(a):
    run_dir = pathlib.Path(a.run).expanduser()
    run, run_p = load_run(run_dir)
    fails, notes = [], []

    boxes, check_p = read_checklist(run_dir, run)
    if boxes is None:
        fails.append("checklist file missing: %s — plan wrote it; a run without it is "
                     "unresumable" % check_p)
        boxes = {}
    else:
        unknown = sorted(set(boxes) - {st["label"] for st in run["chain"]})
        if unknown:
            notes.append("checklist carries %d box(es) not in the chain: %s"
                         % (len(unknown), ", ".join(unknown)))

    print("[director] verifying %s (%d stages, planned %s)"
          % (run_dir, len(run["chain"]), run.get("created", "?")))
    for st in run["chain"]:
        sdir = run_dir / st["dir"]
        problems = []
        ticked = boxes.get(st["label"])
        man_p = sdir / HANDOFF_JSON
        man = None
        if man_p.is_file():
            try:
                man = json.loads(man_p.read_text(encoding="utf-8"))
            except ValueError:
                problems.append("handoff.json is not readable JSON")

        if not sdir.is_dir():
            problems.append("stage folder missing")
        else:
            files = stage_files(sdir)
            ext_ok = False
            if man:
                for side in ("input", "output"):
                    ref = (man.get(side) or {})
                    path = ref.get("path", "")
                    if ref.get("kind") == "seed":
                        continue
                    p = pathlib.Path(path)
                    if not p.is_file():
                        problems.append("handoff %s is gone: %s" % (side, path))
                        continue
                    if ref.get("sha256") and sha256(p) != ref["sha256"]:
                        problems.append("handoff %s changed since it was recorded: %s "
                                        "(re-run handoff, or the chain moved under you)"
                                        % (side, path))
                    elif side == "output":
                        ext_ok = True
            if not files and not ext_ok:
                problems.append("stage folder is empty and no handoff names an output "
                                "elsewhere — the stage produced nothing locatable")
            elif not files and ext_ok:
                notes.append("%s: outputs live outside the stage folder (%s) — allowed, "
                             "manifest-verified" % (st["label"], man["output"]["path"]))
            elif files and man is None:
                notes.append("%s: no handoff.json (input/output not manifested)" % st["label"])

        if ticked is None:
            problems.append("no checklist box for this stage")
        elif not ticked:
            problems.append("checklist box is UNTICKED")

        n_files = len(stage_files(sdir)) if sdir.is_dir() else 0
        status = "OK  " if not problems else "FAIL"
        print("  %s %s  files=%d  box=%s%s"
              % (status, st["label"], n_files,
                 {True: "[x]", False: "[ ]", None: "—"}[ticked],
                 "  handoff=yes" if man else ""))
        for pr in problems:
            print("        · %s" % pr)
        fails += ["%s: %s" % (st["label"], pr) for pr in problems]

    for n in notes:
        print("  note: %s" % n)
    if fails:
        # Repeated flat and label-prefixed on purpose: a gate log is grepped, and one
        # grep should return every problem with the stage it belongs to attached.
        print("problems:")
        for f in fails:
            print("  %s" % f)
        print("pipeline: INCOMPLETE — %d structural problem(s) across %d stage(s); "
              "the run may not be declared finished" % (len(fails), len(run["chain"])))
        return 3
    print("pipeline: VERIFIED — %d stage(s), every box ticked, every stage folder carries "
          "output, every recorded handoff still matches its sha256" % len(run["chain"]))
    print("NOTE: structure only — this says the artifacts exist and have not drifted, "
          "never that a stage's workflow was performed or its content is any good.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="scaffold, hand off and verify a director run")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="resolve the chain and scaffold the run folder")
    p.add_argument("--chain", required=True, help="ordered skills, comma/space/arrow separated")
    p.add_argument("--topic", required=True, help="the seed topic (also the file slug)")
    p.add_argument("--root", default=".")
    p.add_argument("--run", default=None, help="explicit run dir (default: pipeline/, then pipeline-2/…)")
    p.set_defaults(f=cmd_plan)

    h = sub.add_parser("handoff", help="record a stage's input/output manifest with sha256")
    h.add_argument("--run", required=True)
    h.add_argument("--stage", required=True, help="stage number, e.g. 01")
    h.add_argument("--input", default=None, help="override the auto-detected input path")
    h.add_argument("--output", default=None, help="override the auto-detected output path")
    h.set_defaults(f=cmd_handoff)

    v = sub.add_parser("verify", help="exit 3 on an unticked box, an empty stage, or drift")
    v.add_argument("--run", required=True)
    v.set_defaults(f=cmd_verify)

    a = ap.parse_args()
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
