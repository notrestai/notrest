#!/usr/bin/env python3
"""mentor.py — the deterministic half of the mentor-dev ritual.

Two PEER sessions in a teaching relationship: a MENTOR holding the laws, the gates and
the estate's memory, and a BUILDER holding the code and its context. The wire between
them is a chatroom room; the owner reads that room, not the traffic.

This script does the parts that never need judgment — chartering, escort assembly,
checkpoint accounting — so the model spends its tokens on rulings and gates instead of
bookkeeping. It NEVER sends a message (sending is the seat's act, and cross-session
messaging is a harness tool), NEVER reimplements rooms (every room touch shells the
chatroom skill's room.py, whose no-secrets screen is therefore inherited, not bypassed),
and NEVER writes outside the room and an explicitly named --out path.

Subcommands:
  charter --room <name> [--mentor H] [--builder H] [--engine PATH] [--note TEXT]
        create/annotate the room through room.py and post the charter from
        references/charter-template.md. IDEMPOTENT: an already-chartered room is
        reported and nothing is posted.
  escort --room <name> --engine <path> [--hold "reason"] [--out -|PATH]
        print the filled escort from references/escort-template.md: engine inventory
        read LIVE (version, skill count, instruments, HEAD), the reading order
        existence-checked against that engine, the checkpoint protocol, the traveling
        laws, and a HOLD block when one is in force. Prints; never sends.
  checkpoints --room <name> [--json] [--mentor H] [--builder H]
        the checkpoint ledger parsed out of the room: n, poster, what, evidence, NEEDS
        state, and whether a later mentor post gated it. Exit 3 if any is UNGATED.
  status --room <name> [--mentor H] [--builder H]
        one line: N checkpoints · M ungated · last activity · open NEEDS:owner items.

Four parsing rules, stated once so the output can be trusted:
  GATED   — a LATER post by the mentor handle that names that checkpoint number AND
            carries a gate mark (GATE/APPROVED/GREEN/HOLD/BLOCKED/REJECTED/RIDER…).
            Order matters: a mentor naming "CP4" before CP4 was posted is talking about
            the future, not gating it.
  NEEDS   — the pipe-anchored `| NEEDS: <state>` at the end of the line is the
            DECLARATION; a bare "NEEDS:" mid-body is prose and is read only when the
            checkpoint declared nothing.
  UNGATED — not gated AND the declaration is not `nothing`. A `NEEDS: nothing`
            checkpoint is the builder informing the mentor and proceeding: the protocol
            asks for no gate, so it is listed as UNGATED-INFO and never counted. Exit 3
            is therefore "a checkpoint is waiting on the mentor", which is the state a
            pulse can act on.
  OPEN    — an owner escalation is open while it is UNGATED. Gating is the only closure
            this script can see; it never infers resolution from prose. If the room has
            moved on and the item is still real, say so IN THE ROOM — the record is the
            room, not the parser.

Exit codes: 0 ok · 2 usage / no such room / unreadable engine / missing room.py
· 3 at least one ungated checkpoint · 5 REFUSED by the chatroom secret screen
(propagated verbatim from room.py: nothing was written, the matched text is never echoed).
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve()
SKILL_DIR = HERE.parents[1]
REFERENCES = SKILL_DIR / "references"
# The room mechanics live in ONE place: the chatroom skill. Reimplementing them here
# would fork the no-secrets screen, the flock discipline and the room layout.
DEFAULT_ROOM_PY = HERE.parents[2] / "chatroom" / "scripts" / "room.py"

CHARTER_MARK = "MENTOR-DEV CHARTER"
BIG_TAIL = 1000000

LINE_RE = re.compile(r"^\[(?P<ts>[^\]]+)\]\s+@(?P<handle>[^\s:]+):\s*(?P<body>.*)$")
ROLE_RE = re.compile(r"ROLES:\s*MENTOR\s+@([A-Za-z0-9._-]+).*?BUILDER\s+@([A-Za-z0-9._-]+)",
                     re.S | re.I)
# `CHECKPOINT 4:` · `CP4-AMENDMENT (drift notice absorbed):` · `CP 5-DISPATCH:`
CP_START_RE = re.compile(
    r"^(?:CHECKPOINT|CP)[ \t]*[-#]?[ \t]*(\d+)[ \t]*(?:-[ \t]*([A-Za-z][A-Za-z0-9-]*))?"
    r"[^:\n]{0,60}?:", re.I)
CP_REF_RE = re.compile(r"\b(?:CHECKPOINT|CP)[ \t]*[-#]?[ \t]*(\d+)\b", re.I)
GATE_MARK_RE = re.compile(
    r"\b(GATES?|GATED|GATING|APPROVED|GREEN|HOLD|BLOCKED|REJECTED|RIDERS?|"
    r"CHANGES REQUESTED)\b")
VERDICT_RE = re.compile(r"\b(APPROVED|GREEN|HOLD|BLOCKED|REJECTED|CHANGES REQUESTED)\b")
NEEDS_RE = re.compile(r"NEEDS:[ \t]*([A-Za-z][A-Za-z0-9-]*)[ \t]*(.*)$", re.I)
# The protocol puts `| NEEDS: <state>` at the END of the line, and a long checkpoint
# often quotes the word mid-body ("any raw-key demand = STOP + NEEDS: owner"). The
# pipe-anchored form is the declaration; a bare one is only read when there is no
# declaration at all. Live-proven against the rig-build room, where the last bare
# match read CP2 as NEEDS:owner when the builder had declared NEEDS:mentor-gate.
NEEDS_DECL_RE = re.compile(r"\|[ \t]*NEEDS:[ \t]*([A-Za-z][A-Za-z0-9-]*)[ \t]*(.*)$", re.I)
SPLIT_RE = re.compile(r"\s(?:->|→)\s")
NEEDS_STATES = ("nothing", "mentor-gate", "owner")
GLANCE = 160


# ── plumbing ────────────────────────────────────────────────────────────────
def die(msg, code=2):
    sys.stderr.write("mentor: %s\n" % msg)
    sys.exit(code)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def room_py():
    p = pathlib.Path(os.environ.get("MENTOR_ROOM_PY", str(DEFAULT_ROOM_PY)))
    if not p.is_file():
        die("no room.py at %s — the mentor ritual runs ON the chatroom skill and never "
            "reimplements it (set MENTOR_ROOM_PY to point at it)" % p)
    return p


def run_room(args):
    """Shell room.py. Returns (rc, stdout, stderr) — the caller decides what a code means."""
    proc = subprocess.run([sys.executable, str(room_py())] + list(args),
                          text=True, encoding="utf-8", stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def room_lines(name, must_exist=True):
    rc, out, err = run_room(["read", name, "--tail", str(BIG_TAIL)])
    if rc != 0:
        if not must_exist:
            return None
        die((err or out).strip() or "cannot read room %s" % name)
    return out.splitlines()


def room_post(name, handle, text):
    """Post through room.py. Exit 5 (the no-secrets refusal) is propagated verbatim:
    the screen is inherited, and routing around it is never this script's business."""
    rc, out, err = run_room(["post", name, handle, text])
    if rc == 5:
        sys.stderr.write(err or out)
        sys.exit(5)
    if rc != 0:
        die((err or out).strip() or "room.py post failed (exit %d)" % rc)
    return out.strip()


def load_template(fn):
    p = REFERENCES / fn
    if not p.is_file():
        die("missing template %s" % p)
    return p.read_text(encoding="utf-8")


def fill(tpl, mapping):
    out = tpl
    for k, v in mapping.items():
        out = out.replace("{{%s}}" % k, v)
    left = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", out)))
    if left:
        die("template placeholder(s) never filled: %s" % ", ".join(left))
    return out


# ── the engine, read live ───────────────────────────────────────────────────
def plugin_dir(root):
    """The plugin dir inside an engine tree: <root>/plugins/<name> or <root> itself."""
    cands = [root / "plugins" / "notrest", root]
    cands += sorted(p for p in (root / "plugins").glob("*") if p.is_dir()) \
        if (root / "plugins").is_dir() else []
    for c in cands:
        if (c / "skills").is_dir():
            return c
    return None


def git_head(root):
    try:
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                              text=True, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        head = (proc.stdout or "").strip()
        return head if proc.returncode == 0 and head else "unknown (not a git repo here)"
    except OSError:
        return "unknown (git unavailable)"


def inventory(root):
    """Everything the escort states about the engine, read from the engine itself."""
    root = pathlib.Path(root).expanduser()
    if not root.is_dir():
        die("no engine tree at %s" % root)
    pd = plugin_dir(root)
    inv = {"root": str(root), "head": git_head(root), "plugin_dir": str(pd) if pd else None,
           "version": "unknown (no plugin.json read)", "skills": [], "instruments": [],
           "gates": []}
    if pd is None:
        return inv
    man = pd / ".claude-plugin" / "plugin.json"
    if man.is_file():
        try:
            inv["version"] = json.loads(man.read_text(encoding="utf-8")).get(
                "version", "unstated in plugin.json")
        except (ValueError, OSError) as exc:
            inv["version"] = "unreadable plugin.json (%s)" % exc.__class__.__name__
    for d in sorted((pd / "skills").iterdir()):
        if not (d / "SKILL.md").is_file():
            continue
        inv["skills"].append(d.name)
        scripts = sorted(p.name for p in (d / "scripts").glob("*.py")) \
            if (d / "scripts").is_dir() else []
        for s in scripts:
            inv["instruments"].append("%s/%s" % (d.name, s))
            if s in ("doctor.py", "eval.py"):
                inv["gates"].append("%s/scripts/%s check --root ." % (d.name, s))
    return inv


def wrap(items, width=76, indent="    "):
    if not items:
        return "none found in this engine"
    lines, cur = [], ""
    for it in items:
        add = it if not cur else cur + " · " + it
        if len(add) > width and cur:
            lines.append(cur)
            cur = it
        else:
            cur = add
    lines.append(cur)
    return ("\n" + indent).join(lines)


RO_LINE_RE = re.compile(r"^-\s+(\S+)\s+—")


def check_reading_order(text, root):
    """Existence-check every path the reading order names, against THIS engine. A cited
    path that does not exist is a promise the escort cannot keep, so it is dropped from
    the list and named as absent instead."""
    root, out, absent, in_ro = pathlib.Path(root), [], [], False
    for ln in text.splitlines():
        if ln.startswith("## "):
            if in_ro and absent:
                out.append("- absent in this engine (not promised, so not listed above): %s"
                           % ", ".join(absent))
                out.append("")
            in_ro = ln.upper().startswith("## READING ORDER")
            out.append(ln)
            continue
        m = RO_LINE_RE.match(ln) if in_ro else None
        if m and not (root / m.group(1)).exists():
            absent.append(m.group(1))
            continue
        out.append(ln)
    if in_ro and absent:
        out.append("- absent in this engine (not promised, so not listed above): %s"
                   % ", ".join(absent))
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


# ── the room, parsed ────────────────────────────────────────────────────────
def messages(lines):
    """Room lines -> messages. A line without the `[ts] @handle:` prefix is a
    continuation of the message above it (hand-edited rooms happen); a stray line
    before any message is ignored rather than fatal."""
    msgs = []
    for ln in lines:
        m = LINE_RE.match(ln)
        if m:
            msgs.append({"ts": m.group("ts").strip(), "handle": m.group("handle"),
                         "body": m.group("body").strip()})
        elif msgs:
            msgs[-1]["body"] += " " + ln.strip()
    return msgs


def roles(msgs, mentor=None, builder=None):
    """Who is who: the flags win, then the charter's own ROLES line, then the charter's
    poster, then the first checkpoint's poster for the builder, then nothing (and the
    gate rule degrades honestly — see parse())."""
    src = "flag"
    if not (mentor and builder):
        for m in msgs:
            if CHARTER_MARK in m["body"]:
                rm = ROLE_RE.search(m["body"])
                if rm:
                    mentor = mentor or rm.group(1)
                    builder = builder or rm.group(2)
                    src = "charter"
                else:
                    mentor = mentor or m["handle"]
                    src = "charter-poster"
                break
    if not builder:
        first = next((m for m in msgs if CP_START_RE.match(m["body"])), None)
        if first:
            builder = first["handle"]
            src = src if src in ("flag", "charter") else "first-checkpoint"
    return mentor, builder, src


def parse(lines, mentor=None, builder=None):
    msgs = messages(lines)
    mentor, builder, rsrc = roles(msgs, mentor, builder)
    cps = []
    for i, m in enumerate(msgs):
        cm = CP_START_RE.match(m["body"])
        if not cm:
            continue
        rest = m["body"][cm.end():].strip()
        needs, needs_note = "unstated", ""
        nm = list(NEEDS_DECL_RE.finditer(rest)) or list(NEEDS_RE.finditer(rest))
        if nm:
            needs = nm[-1].group(1).lower()
            needs_note = nm[-1].group(2).strip()
            rest = rest[:nm[-1].start()].strip().rstrip("|·-— ").strip()
        parts = SPLIT_RE.split(rest, 1)
        what = parts[0].strip() or "(unstated)"
        evidence = parts[1].strip() if len(parts) > 1 else ""
        cps.append({"n": int(cm.group(1)), "tag": (cm.group(2) or "CHECKPOINT").upper(),
                    "poster": m["handle"], "ts": m["ts"], "index": i,
                    "what": what, "evidence": evidence,
                    "needs": needs, "needs_note": needs_note,
                    "needs_known": needs in NEEDS_STATES,
                    "gated": False, "gate": None})
    for cp in cps:
        for m in msgs[cp["index"] + 1:]:
            # order matters: a mentor naming CP4 before CP4 was posted is talking about
            # the future, not gating it.
            is_mentor = (m["handle"] == mentor) if mentor else (m["handle"] != cp["poster"])
            if not is_mentor or CP_START_RE.match(m["body"]):
                continue
            if not GATE_MARK_RE.search(m["body"]):
                continue
            if str(cp["n"]) not in CP_REF_RE.findall(m["body"]):
                continue
            vm = VERDICT_RE.search(m["body"])
            cp["gated"] = True
            cp["gate"] = {"by": m["handle"], "ts": m["ts"],
                          "verdict": vm.group(1) if vm else "GATED (verdict unstated)",
                          "riders": bool(re.search(r"\bRIDERS?\b", m["body"]))}
            break
    # UNGATED means "owes a gate and has not got one". A checkpoint that declares
    # NEEDS: nothing is the builder INFORMING the mentor and proceeding — the protocol
    # does not ask for a gate on it, so counting it would leave a pulse permanently red
    # and the signal worthless. Those are reported separately, never hidden.
    return {"mentor": mentor, "builder": builder, "roles_from": rsrc,
            "messages": len(msgs), "last": msgs[-1] if msgs else None,
            "checkpoints": cps,
            "ungated": [c["n"] for c in cps
                        if not c["gated"] and c["needs"] != "nothing"],
            "ungated_info": [c["n"] for c in cps
                             if not c["gated"] and c["needs"] == "nothing"],
            "owner_open": [c["n"] for c in cps
                           if c["needs"] == "owner" and not c["gated"]]}


# ── subcommands ─────────────────────────────────────────────────────────────
def cmd_charter(a):
    rc, out, err = run_room(["create", a.room])
    if rc != 0:
        die((err or out).strip() or "room.py create failed (exit %d)" % rc)
    path = out.strip()
    lines = room_lines(a.room)
    prior = next((m for m in messages(lines) if CHARTER_MARK in m["body"]), None)
    if prior:
        rm = ROLE_RE.search(prior["body"])
        print("already chartered: %s" % path)
        print("  charter posted %s by @%s%s" % (prior["ts"], prior["handle"],
              " · mentor @%s · builder @%s" % (rm.group(1), rm.group(2)) if rm else ""))
        print("  nothing posted — re-chartering a live room would rewrite the arrangement "
              "under the builder's feet. Post a ruling instead.")
        return 0
    engine = "not stated"
    if a.engine:
        inv = inventory(a.engine)
        engine = "%s · v%s · HEAD %s · %d skills" % (inv["root"], inv["version"],
                                                     inv["head"], len(inv["skills"]))
    note = ("NOTE: %s" % a.note) if a.note else \
        "(no arrangement note — the escort carries the build's specifics.)"
    text = fill(load_template("charter-template.md"),
                {"ROOM": a.room, "MENTOR": a.mentor, "BUILDER": a.builder,
                 "ENGINE": engine, "NOTE": note})
    room_post(a.room, a.mentor, text)
    print("chartered: %s" % path)
    print("  mentor @%s · builder @%s · engine %s" % (a.mentor, a.builder, engine))
    print("  next: mentor.py escort --room %s --engine <path>  (print it, then send it "
          "yourself — this script never sends)" % a.room)
    return 0


def cmd_escort(a):
    inv = inventory(a.engine)
    mentor, builder = a.mentor, a.builder
    lines = room_lines(a.room, must_exist=False)
    if lines is not None:
        m2, b2, _ = roles(messages(lines), a.mentor, a.builder)
        mentor, builder = m2 or mentor, b2 or builder
    hold = ("HOLD: %s\n\nDo not start building past this line. Post CHECKPOINT 1 with your "
            "cwd state, the conflicts you can see and your setup questions — the hold is on "
            "BUILDING, never on reading, probing or asking." % a.hold) if a.hold else \
        ("NO HOLD is in force. Read the order above, probe your cwd, then post CHECKPOINT 1: "
         "state, conflicts, one batch of setup questions.")
    text = fill(check_reading_order(load_template("escort-template.md"), inv["root"]),
                {"ROOM": a.room, "MENTOR": mentor or "mentor", "BUILDER": builder or "builder",
                 "DATE": now(), "ENGINE_PATH": inv["root"], "ENGINE_VERSION": str(inv["version"]),
                 "ENGINE_HEAD": inv["head"], "SKILL_COUNT": str(len(inv["skills"])),
                 "INSTRUMENTS": wrap(inv["instruments"]),
                 "GATES": wrap(inv["gates"]) if inv["gates"]
                 else "no doctor/eval instrument in this engine — say so rather than "
                      "promising a gate", "HOLD": hold})
    if a.out and a.out != "-":
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
        print("wrote %s (%d chars) — sending it is your act, not this script's" %
              (a.out, len(text)))
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


def glance(text, width=GLANCE):
    """The table is a glance surface; --json carries every checkpoint verbatim."""
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 1].rstrip() + "…"


def cmd_checkpoints(a):
    p = parse(room_lines(a.room), a.mentor, a.builder)
    if a.json:
        print(json.dumps({"room": a.room, "mentor": p["mentor"], "builder": p["builder"],
                          "roles_from": p["roles_from"], "messages": p["messages"],
                          "checkpoints": [{k: v for k, v in c.items() if k != "index"}
                                          for c in p["checkpoints"]],
                          "ungated": p["ungated"], "ungated_info": p["ungated_info"],
                          "owner_open": p["owner_open"]}, indent=2))
    else:
        print("room: %s · mentor @%s · builder @%s · %d checkpoint(s) · %d ungated"
              % (a.room, p["mentor"] or "?", p["builder"] or "?",
                 len(p["checkpoints"]), len(p["ungated"])))
        if p["mentor"] is None:
            print("  (no mentor handle: --mentor or a charter would pin it; gating is being "
                  "read as 'a later post by anyone but the poster')")
        for c in p["checkpoints"]:
            gate = "GATED by @%s %s (%s)%s" % (c["gate"]["by"], c["gate"]["verdict"],
                                               c["gate"]["ts"],
                                               " +RIDERS" if c["gate"]["riders"] else "") \
                if c["gated"] else ("UNGATED-INFO (declared NEEDS: nothing)"
                                    if c["needs"] == "nothing" else "UNGATED")
            print("CP %d [%s] @%s %s · NEEDS: %s%s · %s"
                  % (c["n"], c["tag"], c["poster"], c["ts"], c["needs"],
                     "" if c["needs_known"] else " (not a protocol state)", gate))
            print("    what: %s" % glance(c["what"]))
            print("    evidence: %s" % (glance(c["evidence"]) or
                                        "(unstated — the checkpoint format asks for one)"))
        if p["ungated"]:
            print("UNGATED: %s" % ", ".join("CP %d" % n for n in p["ungated"]))
        if p["ungated_info"]:
            print("UNGATED-INFO (no gate owed): %s"
                  % ", ".join("CP %d" % n for n in p["ungated_info"]))
        if p["owner_open"]:
            print("OPEN NEEDS:owner: %s" % ", ".join("CP %d" % n for n in p["owner_open"]))
    return 3 if p["ungated"] else 0


def cmd_status(a):
    p = parse(room_lines(a.room), a.mentor, a.builder)
    last = "no activity" if not p["last"] else \
        "last activity %s (@%s)" % (p["last"]["ts"], p["last"]["handle"])
    owner = "no open NEEDS:owner" if not p["owner_open"] else \
        "NEEDS:owner open: %s" % ", ".join("CP %d" % n for n in p["owner_open"])
    ung = "0 ungated" if not p["ungated"] else \
        "%d ungated (%s)" % (len(p["ungated"]), ", ".join("CP %d" % n for n in p["ungated"]))
    info = "" if not p["ungated_info"] else " · %d informational" % len(p["ungated_info"])
    print("%s: %d checkpoint(s) · %s%s · %s · %s"
          % (a.room, len(p["checkpoints"]), ung, info, last, owner))
    return 0


def main():
    ap = argparse.ArgumentParser(description="the deterministic half of the mentor-dev ritual")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("charter", help="create/annotate the room and post the charter")
    c.add_argument("--room", required=True)
    c.add_argument("--mentor", default="mentor")
    c.add_argument("--builder", default="builder")
    c.add_argument("--engine", help="engine tree named in the charter (read live)")
    c.add_argument("--note", default="", help="one arrangement-specific line")
    c.set_defaults(f=cmd_charter)

    e = sub.add_parser("escort", help="print the filled orientation escort (never sends)")
    e.add_argument("--room", required=True)
    e.add_argument("--engine", required=True)
    e.add_argument("--mentor")
    e.add_argument("--builder")
    e.add_argument("--hold", help="a HOLD reason: the builder reads and asks, but does not build")
    e.add_argument("--out", default="-", help="- (default, stdout) or a path you name")
    e.set_defaults(f=cmd_escort)

    k = sub.add_parser("checkpoints", help="the checkpoint ledger; exit 3 if any is ungated")
    k.add_argument("--room", required=True)
    k.add_argument("--mentor")
    k.add_argument("--builder")
    k.add_argument("--json", action="store_true")
    k.set_defaults(f=cmd_checkpoints)

    s = sub.add_parser("status", help="one line for a scheduler or a pulse")
    s.add_argument("--room", required=True)
    s.add_argument("--mentor")
    s.add_argument("--builder")
    s.set_defaults(f=cmd_status)

    a = ap.parse_args()
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
