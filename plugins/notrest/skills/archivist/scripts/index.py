#!/usr/bin/env python3
"""index.py — archivist: the findings store, plus the legacy dossier index.

The store is `archive/findings.jsonl` (repo-root relative): one JSON record per
line, APPEND-ONLY, written under an exclusive flock. Nothing is ever edited in
place — a status flip is a NEW tombstone record, and `track` resolves the
effective status by walking links.

Subcommands:
  add        validate one finding record at the door and append it; prints its id
  track      print the session track in ts order (--json for machines); a live record
             whose links name an effectively-refuted id carries RESTS-ON-REFUTED
  supersede  append a tombstone flipping a record to superseded
  refute     append a tombstone flipping a record to refuted, with evidence
  scan       rebuild oracle-index.md from every *Dossier.md found (legacy estate)
  find       search findings statements + index entries + dossier bodies
  library    the cross-project shelf: register / list / find / track — every
             registered project's store, read where it lives (see below)

THE LIBRARY IS FEDERATED, NOT CENTRAL. Each project's store stays in its own repo,
versioned and beamed with the code it describes. The library is an INDEX OF ROOTS
(~/.claude/notrest-library/registry.jsonl, append-only) so a question answered in
one project is findable — and citable — from another: evidence `{"type":"record",
"ref":"<project>:F-<n>"}`.

The index and the store are finding aids, never sources — cite the evidence ref.
Never hand-edit either one: re-run scan, or append a correcting record.
"""
import argparse
import fcntl
import hashlib
import fnmatch
import importlib.util
import json
import os
import pathlib
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- legacy index
DIRS = ["research", "market-research", "understanding", "decision", "factcheck",
        "critique", "action-plan", "runbook", "pipeline", "introspection", "recap",
        "draft"]
INDEX = "oracle-index.md"
LEDGER = "COORD-AGENTS.md"  # the SubagentStop hook's agent activity ledger
CANDIDATES = "compile/candidates.md"       # compile.py's repeated-work table
CANDIDATES_DATA = "compile/candidates.json"

# A dossier's own date line beats the filesystem's mtime (a copy or a re-clone
# rewrites mtime; the document's date is what the document claims).
DATE_DECL_RE = re.compile(
    r"^[\s>*_#|-]*(?:\*\*)?\s*"
    r"(?:date|dated|generated|written|last\s+(?:updated|scan)|as\s+of|run(?:\s+on)?)"
    r"\b[^0-9\n]{0,24}(\d{4}-\d{2}-\d{2})", re.I | re.M)
DATE_BARE_RE = re.compile(r"^[\s>*_-]*(\d{4}-\d{2}-\d{2})\s*$", re.M)
# An index block's pointer line is `folder: <d> · path: <rel>` — `path:` is NEVER at
# the start of the line, so an anchored pattern matched nothing and the body sweep
# re-reported every dossier the index had already answered for.
INDEX_PATH_RE = re.compile(r"\bpath: (\S+)")

# ---------------------------------------------------------------- the store
STORE = "archive/findings.jsonl"
FIELDS = ("id", "ts", "session", "skill", "kind", "ask", "statement",
          "evidence", "relation", "links", "status", "tag", "scope", "source",
          "closes_when", "owner", "recheck", "method", "when_to_try", "cost",
          "ran", "command", "exit")
KINDS = ("finding", "result", "decision", "conflict", "backtrack", "side-route",
         "learning", "open", "alternative")
RELATIONS = ("toward", "lateral", "back")
# 4.7 B2: `proposed` and `rejected` are the LANE lifecycle. A record a lane banked from
# its return card is a CLAIM until the seat reviews it — never estate law.
STATUSES = ("live", "superseded", "refuted", "proposed", "rejected")
EV_TYPES = ("url", "path", "command", "coord-line", "record")
EV_LABELS = ("cited", "estimate", "recall", "unverified", "model-opinion")
EVIDENCE_REQUIRED = ("finding", "result", "decision", "learning", "open")

# ── 4.7 · THE TWO KINDS THAT MAKE A RETURN HONEST ─────────────────────────────────────
# A lane return that lists only what WORKED is a report with its failures edited out. The
# store had no shape for the other half, so "not tested" lived in prose nobody could count
# and nobody could re-check. These two kinds give it one.
#
#   open        — what was NOT tested, or did not work. Required: what would CLOSE it (a
#                 runnable check, not a feeling), an OWNER who can close it, and a RECHECK
#                 date so it surfaces again instead of ageing quietly into folklore.
#   alternative — a path not taken. Required: the METHOD, WHEN it would be worth trying,
#                 and its COST. Evidence is NOT required here and that is deliberate: an
#                 alternative was never run, so demanding a citation would force a lie.
#
# `result` gains ran/command/exit for the same reason: TESTS becomes a COUNT OF RECORDS
# each naming a command and an exit code, instead of a number somebody typed.
OPEN_KIND = "open"
ALT_KIND = "alternative"
OPEN_REQUIRED = ("closes_when", "owner", "recheck")
ALT_REQUIRED = ("method", "when_to_try", "cost")
RESULT_REQUIRED = ("ran", "command", "exit")
RECHECK_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Which extra fields each kind may carry. Gated BOTH ways — a `recheck` riding on a
# finding is read by nobody and makes the field mean two things.
KIND_ONLY_FIELDS = {
    "learning": ("tag", "scope", "source"),
    OPEN_KIND: ("closes_when", "owner", "recheck", "scope", "source"),
    ALT_KIND: ("method", "when_to_try", "cost", "scope", "source"),
    "result": ("ran", "command", "exit"),
}
EXTRA_FIELDS = tuple(sorted({f for v in KIND_ONLY_FIELDS.values() for f in v}))

# ── THE LEARNINGS LOOP (4.6.3) ────────────────────────────────────────────────────────
# A learning is a lesson the estate has ALREADY PAID FOR, banked so the next session and
# the next lane inherit it instead of re-buying it. It rides in the same append-only store
# as every other record — one store, one grammar, one set of readers — and carries three
# extra fields that only this kind may use.
#
# ⛔ IT IS A RECORD, NOT A NOTE. A lesson with no evidence is a slogan: nobody downstream
# can check whether it was ever true, and an unfalsifiable rule is the thing that outlives
# its own reason. A lesson with no scope is worse — it applies everywhere, so it is quoted
# at every lane forever and the digest becomes noise nobody reads. Both are refused AT THE
# DOOR, where the cost of refusing is one error message, rather than downstream, where the
# cost is a session acting on a rule that was never earned.
LEARN_KIND = "learning"
LEARN_TAGS = ("INHERITED", "RULED", "LEARNED")
LEARN_ONLY_FIELDS = ("tag", "scope", "source")
# `seat`, a bare lane id, or the explicit `lane:<id>` provenance form a card-banked
# record carries. The prefix is what lets a reader tell an owner ruling from a sentence a
# lane wrote about itself — the whole point of B2.
LEARN_SOURCES_RE = re.compile(r"^(seat|lane:[A-Za-z0-9][A-Za-z0-9._-]*"
                              r"|[A-Za-z0-9][A-Za-z0-9._-]*)$")
LANE_SOURCE_RE = re.compile(r"^lane:[A-Za-z0-9][A-Za-z0-9._-]*$")
# Only the kinds that get QUOTED AS LAW are gated. A lane's findings and results are DATA
# — they report what it saw and what it ran, they are never injected into a sibling's
# prompt as a rule, and gating them would just make lanes stop banking evidence.
LANE_GATED_KINDS = ("learning", "open", "alternative")
STATEMENT_MAX = 300
# The four shapes a learning may cite. Each is something a reader can GO AND LOOK AT: a
# ledger line, the commission that ordered the work, the commit that carries it, or another
# record. Prose is not evidence.
# D3 (refuter): a citation may carry a 1-based ORDINAL — `[ts]#2` — because a minute is
# not an identifier. 16 live stamps carry more than one ledger line, and a bare `[ts]`
# citation silently closed every one of them: two corrections written in the same minute
# were discharged by banking a lesson about one.
COORD_TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z)\](?:#(\d+))?")
LEARN_EV_SHAPES = (
    ("a COORD timestamp '[YYYY-MM-DD HH:MMZ]'", COORD_TS_RE.search),
    ("a briefs/ path", re.compile(r"(?:^|/)briefs/\S+").search),
    ("a commit hash", re.compile(r"^[0-9a-f]{7,40}$", re.I).fullmatch),
    ("a record id (F-/L-/O-/A-<n>)", re.compile(r"[FLOA]-\d+$").fullmatch),
)

# ⛔ ONE REGEX, ONE HOME. These are the COORD ledger lines that mean the estate just paid
# for a lesson: a correction, a refuter finding, a red gate, a halt. eval's LEARNING-LOOP
# check audits them and lane H's Stop hook prompts on them — and two copies of a regex are
# two regexes the moment somebody edits one. `index.py learnings --trigger-regex` prints
# THIS string, both consumers read it from here, and the eval fixture asserts they agree.
# ⛔ CASE-SENSITIVE, AND ONLY IN THE HEADLINE. The first cut matched case-insensitively
# over the WHOLE line and flagged 12 lines on this estate of which 7 were noise: a SHIP
# line that mentioned "refuter round (3 defects" in its report half, a plan-lane line
# mentioning "two corrections for the pack", lowercase summaries of work that went fine.
# A gate that cries at every mention of the word "correction" is a gate people switch off.
#
# The signal the estate actually writes is an UPPERCASE TAG IN THE HEADLINE — the text
# BEFORE the first "->", which is what the line CLAIMS rather than what it reports. So the
# match is case-SENSITIVE and runs on the headline only. `REFUTER[^>]*` cannot cross the
# arrow, so a refuter round that CLEARED is not a trigger while one that returned a
# DEFECT/BLOCKER/NOT CLEAN is.
#
# STOPPED IS IN THIS REGEX ON PURPOSE (seat gate 2026-09-05, confirmed). The ruling wrote
# the pattern with HALTED only, and on this estate that missed 02:17Z — "owner STOPPED the
# docs lane mid-correction; all workshop work halted" — whose uppercase tag is STOPPED and
# whose lowercase "halted" the case-sensitive rule correctly ignores. The ruling's PRINCIPLE
# is "an uppercase tag in the headline", not one particular verb, and STOPPED names exactly
# the event HALTED names. With it, the ruling's own expected partition holds exactly: 00:41Z,
# 01:10Z, 02:13Z, 02:16Z, 02:17Z fire; 01:14Z, 01:21Z, 01:25Z, 02:15Z, 04:34Z, 04:45Z and
# 09-01 08:07Z do not. It also catches one older line (2026-07-25 13:15Z, a lane STOPPED by
# the seat) which the FLOOR grandfathers.
#
# ⛔ THE HEADLINE IS BOUNDED: the text before the first "->", OR THE FIRST 120 CHARACTERS,
# WHICHEVER IS SHORTER. Live false positive, 2026-09-05: a 613-character ledger line with
# NO "->" separator became its own headline end to end, and the word STOPPED sitting at
# char 477 — inside a sentence DESCRIBING this very regex — fired the gate and blocked the
# seat. A tag that far into a line is a mention, not a claim. The estate's grammar puts the
# claim first; 120 characters is the whole claim on every well-formed line here, and a line
# that omits the arrow no longer gets to be one enormous headline.
LEARN_TRIGGER_REGEX = (
    r"OWNER CORRECTION|CORRECTION:|REFUTER[^>]*(DEFECT|BLOCKER|NOT CLEAN)|"
    r"\bRED:|HALTED|STOPPED")
LEDGER_LINE_RE = re.compile(r"^\s*-\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z)\]")

# ⛔ THE OTHER HALF OF AN HONEST RETURN. The trigger regex above catches lines where the
# estate PAID for a lesson; this one catches lines where it ADMITTED A GAP — "not tested",
# "could not verify", "[unverified]". Those admissions are the most perishable sentences in
# the ledger: they are true when written, nobody owns them, and six weeks later they read
# as though the work was done. An admission is closed by an `open` RECORD — which names
# what would close it, who owns it, and when to look again — not by a learning.
#
# Case-INSENSITIVE, unlike the trigger tags, and deliberately so: these are prose phrases a
# writer types mid-sentence, not uppercase tags they reach for. The 120-char headline bound
# still applies, so an admission buried deep in a report half is a mention, not a claim.
# ⛔ AND IT IS READ IN THE **BODY**, NOT THE HEADLINE — the outcome text AFTER the first
# "->". The two families live in different halves of a ledger line, on principle: a
# CORRECTION is a statement about the ASK (what we were told to do differently), so it
# lives in the headline; an ADMISSION OF A GAP is a statement about the RESULT (what we
# shipped without checking), so it lives in the body. Live false positive, 2026-09-05: the
# line "LANE H (card banking + untested block) RETURNED and seat-gated" fired on a headline
# that merely NAMES the feature and admits nothing. A line with no "->" has no body and
# therefore cannot admit anything.
#
# ⛔ ACCEPTED LIMIT, STATED HERE BECAUSE IT IS REAL: a quoted feature name in the BODY —
# "…untested blocks with the open-record comment…" — still fires. That is deliberate. A
# body mentioning "unverified" is more often an admission than a title, and the cost of a
# false fire is one `open` record that closes it in a line; the cost of a false silence is
# a gap nobody ever re-checks. A quoted admission is treated as an admission.
# ⛔ AN ADMISSION IS A VERDICT, NOT A WORD. Two earlier cuts read the vocabulary instead
# of the claim. The first matched the bare words anywhere in the body, and half the live
# list came back as this estate's own machinery — "untested admissions with no open
# record", "the untested block", "an untested trigger". The second bolted on a STOPLIST of
# the loop's nouns, which worked (6 → 3) but was a list that would have to grow forever:
# every feature named after the loop would need a new entry, and the entry would always be
# added one false fire too late. That history is why the grammar below is shaped this way.
#
# An admission is EITHER:
#   (a) a BRACKETED HONESTY LABEL — [unverified] / [untested] / [not tested]. The estate's
#       own grammar for "I did not check this"; a writer who reached for it meant it.
#   (b) a VERDICT — the phrase preceded by a verb that ASSERTS it: "is unverified",
#       "was not tested", "left untested", "remains unverified" — plus the standalone
#       phrases "could not verify" / "couldn't verify" / "not verified".
# A BARE NOUN USE IS NEVER AN ADMISSION: "adds untested)", "untested-admission list",
# "untested trigger" name a thing; they claim nothing about a result.
UNTESTED_VERBS = ("is", "are", "was", "were", "remains", "remain", "left", "still",
                  "stays", "stay")
UNTESTED_PHRASES = ("not tested", "unverified", "untested")
UNTESTED_LABEL_RE = r"\[(?:unverified|untested|not tested)\]"
# D4 (refuter): the first verdict cut caught only the simple copula. English admits a gap
# in more shapes than "is unverified", and five real sentences walked straight through it:
#   · the AUXILIARY PERFECT — "has not been verified", "had not been tested"
#   · the NEVER form       — "never ran", "never tested", "never verified", "never checked"
#   · a QUALIFIED negation — "not yet verified", "not fully verified", "not live-verified"
# Each is a verdict by any reading; missing them is the same defect as reading bare nouns,
# arriving from the other side.
UNTESTED_PERFECT_RE = (r"\b(?:has|have|had|was|were|is|are|remains?|stays?|left|still)\s+"
                       r"not\s+(?:yet\s+|fully\s+)?bee?n?\s+(?:verified|tested)\b")
UNTESTED_NEVER_RE = r"\bnever\s+(?:ran|tested|verified|checked)\b"
UNTESTED_NOTVERIFIED_RE = r"\bnot\s+(?:yet\s+|fully\s+|live[- ])?(?:verified|tested)\b"
UNTESTED_VERDICT_RE = (r"\b(?:%s)\s+(?:%s)\b|\b(?:could not verify|couldn't verify)\b"
                       r"|%s|%s|%s"
                       % ("|".join(UNTESTED_VERBS), "|".join(UNTESTED_PHRASES),
                          UNTESTED_PERFECT_RE, UNTESTED_NEVER_RE, UNTESTED_NOTVERIFIED_RE))
UNTESTED_REGEX = "%s|%s" % (UNTESTED_LABEL_RE, UNTESTED_VERDICT_RE)

# ⛔ AND A QUOTED SPAN IS SOMEBODY ELSE'S WORDS, NOT THIS LINE'S CLAIM. A ledger line
# REPORTING on the loop quotes its labels — `the SessionEnd pool "[unverified] live"` —
# and a report about an admission is not an admission. Double-quoted spans are removed
# before matching, so quoting a label can never be mistaken for asserting one.
QUOTED_SPAN_RE = re.compile(r'"[^"\n]*"')


def body(line):
    """The outcome half of a ledger line: everything after the FIRST '->'.

    A line with no arrow has no body and returns "" — it made no claim about a result, so
    it cannot have admitted a gap in one.
    """
    text = str(line or "")
    return text.split("->", 1)[1] if "->" in text else ''
STR_FIELDS = ("ts", "session", "skill", "ask")

URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://[^\s/]+", re.I)
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
ID_RE = re.compile(r"^F-(\d+)$")
LID_RE = re.compile(r"^L-(\d+)$")
ANY_ID_RE = re.compile(r"^([FLOA])-(\d+)$")
# One id space per kind that gets cited on its own: a learning is quoted at lanes, an open
# question is closed by id, an alternative is picked up later. Everything else stays F-.
KIND_PREFIX = {"learning": "L", OPEN_KIND: "O", ALT_KIND: "A"}
# The resolution grammar: a tombstone declares its flip in the statement HEAD and
# names its target in links. Both must hold, or the flip does not count.
# ⛔ EVERY ID SPACE, NOT JUST F-. This anchored on `F-` while `supersede`/`refute` happily
# wrote a tombstone for `L-5` — so the flip was RECORDED and never RESOLVED: the retired
# lesson stayed status=live, kept appearing in every digest, and went on being injected
# into lane prompts and the packet. A tombstone the resolver cannot read is a tombstone
# that does nothing.
TOMB_RE = re.compile(r"^(supersedes|refutes)\s+([FLOA]-\d+)\b", re.I)
REVIEW_RE = re.compile(r"^(accepts|rejects)\s+([FLOA]-\d+)\b", re.I)

# ---------------------------------------------------------------- the library
# The shelf is a REGISTRY OF ROOTS, never a copy of anyone's store: each project
# keeps its own archive/findings.jsonl, in its own repo, versioned with the code
# it describes. Registering only tells this machine where a store lives.
LIB_ENV = "NOTREST_LIBRARY_ROOT"
LIB_DEFAULT = pathlib.Path.home() / ".claude" / "notrest-library"
REGISTRY = "registry.jsonl"           # append-only {root, name, ts}
LIB_LEARNINGS = "learnings.jsonl"     # append-only, promoted lessons (4.7 E)
LIB_SCOPE = "library"                 # the scope token that makes one portable
PROJECTS = "oracle-projects.txt"      # graph.py's registry: one absolute root per line
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# THE CITATION GRAMMAR: `F-<n>` is this store; `<project>:F-<n>` is the library's.
# `[FLOA]` — every id space the store numbers is citable as `record` evidence. 4.6.3 added
# L- (learnings); 4.7 adds O- (open questions) and A- (alternatives), because the record
# that CLOSES an open question has to be able to point at the one it closes. Without this
# a closure had to smuggle the citation through `links`, which is the graph edge, not the
# evidence — two different claims sharing one field.
REC_REF_RE = re.compile(r"^(?:([A-Za-z0-9][A-Za-z0-9._-]*):)?([FLOA])-(\d+)$")
# THE QUALIFICATION RULE (F-19), in PROSE. Once two estates each number their own
# records, a bare `F-<n>` in a sentence is AMBIGUOUS — the same token names different
# records in different stores, so a re-recorded "amends F-9" resolves to the wrong
# decision in the wrong house. Every token this finds is a candidate; the lookarounds
# are what keep it honest, and each one was earned against the live estate:
#   lookbehind `[A-Za-z0-9._:/-]` — `:` is the whole point (`rig:F-9` is ALREADY
#     qualified and must never be flagged); the rest keep `F-<n>` from matching
#     inside a bigger token (`archive/F-9`, `v1.F-9`, a mid-word `xF-9`).
#   lookahead `[0-9A-Za-z_-]` — `F-9x` is not a record id, and the greedy `\d+`
#     plus this guard means `F-93` reads as 93, never as 9.
#   lookahead `\.[0-9A-Za-z]` — a trailing period is SENTENCE, not identifier:
#     `F-9.` at the end of a clause is a real citation and must be caught, while
#     `F-9.md` and `F-1.2` are not ids at all. (The first draft excluded every `.`
#     and silently missed every id that ended a sentence — a third of the live
#     estate's mentions. The regex earned this branch.)
BARE_REF_RE = re.compile(r"(?<![A-Za-z0-9._:/-])F-(\d+)(?![0-9A-Za-z_-])(?!\.[0-9A-Za-z])")

# ---------------------------------------------------------------- the storeys
CONCEPTS = "concepts.jsonl"           # append-only; last line per C-<n> wins
UPDATE_LOG = "update-log.md"          # append-only dated blocks (watch's drift-log shape)
UPDATE_CACHE = "update-cache.json"    # machine-written validators; safe to delete
CONCEPT_STATUSES = ("OPEN", "CONVERGED", "CONTESTED")
CID_RE = re.compile(r"^C-(\d+)$")
CROWN_RE = re.compile(r"^CONVERGED:", re.I)
SIM_DEFAULT = 0.24     # compile.py's swept df-weighted average-link threshold
MIN_DF_DEFAULT = 2     # records are fewer and longer than ledger lines, so the
                       # vocabulary floor drops; compile's own default is 3
MIN_MEMBERS = 2        # one record is not a concept, it is a record
MAX_AGE_DAYS = 7       # --due: a url unprobed for this long is due again
VERDICTS = ("STANDS", "DRIFTED", "DEAD-SOURCE", "BASELINE", "NEEDS-SESSION-RECHECK")

_DONORS = {}


def donor(name):
    """Load a sibling skill's script as a module — ONE implementation, never a copy.

    `compile.py` owns the df-weighted average-link clustering (its thresholds were
    swept against this repo's real estate; its estate-stopword list was written to
    fix a measured defect). `watch.py` owns the HTTP probe. Re-deriving either here
    would fork drift-prone logic that has already been measured — so the library
    imports them and says so out loud when they are missing."""
    if name in _DONORS:
        return _DONORS[name]
    p = pathlib.Path(__file__).resolve().parents[2] / name / "scripts" / ("%s.py" % name)
    if not p.is_file():
        die("donor-missing",
            "this verb borrows %s/scripts/%s.py and it is not at %s — the library does "
            "not carry a second copy of that logic on purpose" % (name, name, p))
    spec = importlib.util.spec_from_file_location("notrest_donor_%s" % name, p)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                                    # pragma: no cover
        die("donor-broken", "%s failed to load: %s: %s" % (p, exc.__class__.__name__, exc))
    _DONORS[name] = mod
    return mod


class Reject(Exception):
    """A record turned away at the door. Carries the rule it broke."""

    def __init__(self, rule, detail):
        super().__init__("%s: %s" % (rule, detail))
        self.rule, self.detail = rule, detail


def now_z():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def die(rule, detail):
    """A turned-away record always names the rule it broke, and always exits 2."""
    sys.stderr.write("reject: %s — %s\n" % (rule, detail))
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# validation — the door
# ---------------------------------------------------------------------------
def check_record_refs(refs, known_ids, lib, notes):
    """THE CROSS-PROJECT CITATION RULE. A `record` evidence ref is `F-<n>` (this
    store) or `<project>:F-<n>` (a project on the library shelf). The shape is
    always checked. A LOCAL id must exist, exactly like `links`. A CROSS-PROJECT
    id is existence-checked when that project is registered AND its store is
    reachable — and when it is not, the ref is ACCEPTED WITH A NOTE, never
    rejected: a parallel machine's repo may simply be offline, and federation
    that fails closed is federation nobody can use."""
    idx = None
    for ref in refs:
        m = REC_REF_RE.match(ref)
        if not m:
            raise Reject("record-ref-shape",
                         "record evidence ref %r must be F-/L-/O-/A-<n> (this "
                         "store) or <project>:F-<n> (the library)" % ref)
        proj, fid = m.group(1), "%s-%s" % (m.group(2), m.group(3))
        if not proj:
            if fid not in known_ids:
                raise Reject("record-ref-unknown",
                             "record evidence names %s — no such record in this store" % fid)
            continue
        if idx is None:
            idx = {p["name"]: p for p in read_registry(lib)}
        entry = idx.get(proj)
        if entry is None:
            notes.append("%s:%s cited — %r is not registered in %s; accepted unverified"
                         % (proj, fid, proj, registry_file(lib)))
            continue
        recs, _bad = load_store_safe(entry["root"])
        if recs is None:
            notes.append("%s:%s cited — %s is unreachable from here; accepted unverified"
                         % (proj, fid, entry["root"]))
            continue
        if fid not in {r.get("id") for r in recs}:
            raise Reject("record-ref-unknown",
                         "record evidence names %s:%s — that project's store holds no %s"
                         % (proj, fid, fid))


def unqualified_refs(rec):
    """THE QUALIFICATION RULE at WARN grade (F-19). Returns one warning per bare
    `F-<n>` the record's PROSE names but never DECLARES — first-appearance order,
    one per distinct id, `statement` before `ask`.

    A bare token is CLEAN when the record itself declares that id: in `links`, or as
    a `record` evidence ref in LOCAL form. `beta:F-1` declares nothing here — it is a
    different house's id, which is exactly the confusion the law exists to prevent.

    This is a NUDGE, not a gate, and it stays one on purpose: prose has legitimate
    reasons to name a record it is not citing. The law record F-19 trips this check
    itself — it writes `amends F-9` as an ILLUSTRATION of the ambiguity — and a rule
    that rejected that sentence would be a rule nobody could write the law in. Only
    `--strict-refs` promotes it to a rejection, for callers who want it enforced."""
    declared = set(rec.get("links") or [])
    for e in rec.get("evidence") or []:
        if isinstance(e, dict) and e.get("type") == "record":
            ref = (e.get("ref") or "").strip()
            if ID_RE.match(ref):
                declared.add(ref)
    out, seen = [], set()
    for field in ("statement", "ask"):
        for m in BARE_REF_RE.finditer(rec.get(field) or ""):
            fid = "F-%s" % m.group(1)
            if fid in declared or fid in seen:
                continue
            seen.add(fid)
            out.append("%s names %s which is not in links; cross-estate references "
                       "must be qualified <project>:%s" % (field, fid, fid))
    return out


def _check_evidence_ordinals(evidence, root):
    """Refuse `[ts]#k` where the stamp does not carry a k-th line."""
    if root is None:
        return
    counts = None
    for item in evidence:
        for m in COORD_TS_RE.finditer(str(item.get("ref", ""))):
            if not m.group(2):
                continue
            if counts is None:
                counts = {}
                for ts, _o, total, _l, _s in ledger_lines(root):
                    counts[ts] = total
            ts, k = m.group(1), int(m.group(2))
            total = counts.get(ts)
            if total is None:
                continue          # the stamp is not in this estate's ledger at all
            if k < 1 or k > total:
                raise Reject("evidence-ordinal-unknown",
                             "evidence cites [%s]#%d but that stamp carries %d line(s) — "
                             "an ordinal must name a line that exists, or the citation "
                             "discharges nothing while looking settled" % (ts, k, total))


def validate(raw, known_ids, lib=None, notes=None, root=None):
    """Return a normalized record, or raise Reject naming the rule it broke."""
    lib = lib or library_root(None)
    notes = notes if notes is not None else []
    if not isinstance(raw, dict):
        raise Reject("record-object", "record must be a JSON object, got %s"
                     % type(raw).__name__)
    unknown = [k for k in raw if k not in FIELDS]
    if unknown:
        raise Reject("unknown-field", "field(s) not in the schema: %s (schema: %s)"
                     % (", ".join(sorted(unknown)), ", ".join(FIELDS)))
    if "id" in raw:
        raise Reject("id-assigned", "id is assigned by the store, never by the caller")

    rec = {}
    for f in STR_FIELDS:
        v = raw.get(f, "")
        if v is None:
            v = ""
        if not isinstance(v, str):
            raise Reject("field-type", "%s must be a string, got %s" % (f, type(v).__name__))
        rec[f] = v.strip()
    rec["ts"] = rec["ts"] or now_z()
    if not TS_RE.match(rec["ts"]):
        raise Reject("ts-format", "ts must be ISO8601 Z (YYYY-MM-DDTHH:MM:SSZ), got %r"
                     % rec["ts"])

    stmt = raw.get("statement", "")
    if not isinstance(stmt, str) or not stmt.strip():
        raise Reject("statement-required", "statement is the finding — it cannot be empty")
    rec["statement"] = stmt.strip()

    kind = raw.get("kind")
    if kind not in KINDS:
        raise Reject("kind-enum", "kind %r outside %s" % (kind, list(KINDS)))
    rec["kind"] = kind

    relation = raw.get("relation", "toward")
    if relation not in RELATIONS:
        raise Reject("relation-enum", "relation %r outside %s" % (relation, list(RELATIONS)))
    rec["relation"] = relation

    status = raw.get("status", "live")
    if status not in STATUSES:
        raise Reject("status-enum", "status %r outside %s" % (status, list(STATUSES)))
    rec["status"] = status

    links = raw.get("links", [])
    if links is None:
        links = []
    if not isinstance(links, list) or any(not isinstance(x, str) for x in links):
        raise Reject("links-shape", "links must be a list of id strings")
    for lid in links:
        if lid not in known_ids:
            raise Reject("links-unknown", "links names %r — no such record in the store" % lid)
    rec["links"] = links

    ev = raw.get("evidence", [])
    if ev is None:
        ev = []
    if not isinstance(ev, list):
        raise Reject("evidence-shape", "evidence must be a list of {type, ref, label}")
    clean, rec_refs = [], []
    for item in ev:
        if not isinstance(item, dict):
            raise Reject("evidence-shape", "evidence item must be an object, got %s"
                         % type(item).__name__)
        extra = [k for k in item if k not in ("type", "ref", "label")]
        if extra:
            raise Reject("evidence-shape", "evidence item has field(s) %s — only type, ref, label"
                         % ", ".join(sorted(extra)))
        etype, ref, label = item.get("type"), item.get("ref"), item.get("label")
        if not isinstance(ref, str) or not ref.strip():
            raise Reject("evidence-shape", "evidence item needs a non-empty ref")
        if etype not in EV_TYPES:
            raise Reject("evidence-type-enum", "evidence type %r outside %s"
                         % (etype, list(EV_TYPES)))
        if label not in EV_LABELS:
            raise Reject("evidence-label-enum", "evidence label %r outside %s"
                         % (label, list(EV_LABELS)))
        if label == "cited" and etype == "url" and not URL_RE.match(ref.strip()):
            raise Reject("cited-url-needs-url",
                         "[cited] url evidence needs a real URL, got %r" % ref.strip())
        if etype == "record":
            rec_refs.append(ref.strip())
        clean.append({"type": etype, "ref": ref.strip(), "label": label})
    if rec_refs:
        check_record_refs(rec_refs, known_ids, lib, notes)
    # ⛔ AN ORDINAL MUST NAME A LINE THAT EXISTS. `[ts]#7` on a two-line minute is a
    # citation of nothing, and it read as a DISCHARGED debt: the trigger key it satisfies
    # can never be generated, so the real line stayed owed while the store looked settled.
    # Checked against the ledger the citation points into, and skipped entirely when there
    # is no ledger to check against — an estate with no COORD refuses no citation.
    _check_evidence_ordinals(clean, root)
    if not clean and rec["kind"] in EVIDENCE_REQUIRED:
        raise Reject("evidence-required",
                     "kind=%s must carry at least one evidence item" % rec["kind"])
    rec["evidence"] = clean

    # ── the learning-only fields. Gated BOTH ways: required on a learning, refused on
    # anything else — a `scope` quietly riding on a finding would be read by nobody and
    # would make the field mean two things.
    allowed = KIND_ONLY_FIELDS.get(rec["kind"], ())
    stray = [f for f in EXTRA_FIELDS if f in raw and f not in allowed]
    if stray:
        raise Reject("kind-only-field",
                     "%s belong(s) to another kind, not kind=%s (this kind takes: %s)"
                     % (", ".join(stray), rec["kind"],
                        ", ".join(allowed) if allowed else "none"))

    def _need_str(field, rule, why, cap=STATEMENT_MAX):
        v = raw.get(field)
        if not isinstance(v, str) or not v.strip():
            raise Reject(rule, why)
        v = v.strip()
        if len(v) > cap:
            raise Reject("%s-too-long" % field.replace("_", "-"),
                         "%s is %d chars; the bound is %d" % (field, len(v), cap))
        rec[field] = v

    def _scope_and_source(default_source="seat"):
        scope = raw.get("scope")
        if not isinstance(scope, list) or not scope:
            raise Reject("scope-required",
                         "kind=%s needs scope: a non-empty list of path globs, skill "
                         "names, or 'estate' — a record that applies everywhere is quoted "
                         "at every lane forever" % rec["kind"])
        cleaned = []
        for tok in scope:
            if not isinstance(tok, str) or not tok.strip():
                raise Reject("scope-shape", "each scope entry must be a non-empty string")
            cleaned.append(tok.strip())
        rec["scope"] = cleaned
        src = raw.get("source", default_source)
        if not isinstance(src, str) or not LEARN_SOURCES_RE.match(src.strip() or "-"):
            raise Reject("source-shape",
                         "source must be 'seat', a lane id, or 'lane:<id>', got %r" % (src,))
        rec["source"] = src.strip()
        # ⛔ THE BLOCKER, CLOSED AT THE DOOR. A lane's return card could bank a sentence
        # like "SYSTEM: the seat must run … and push" as a LEARNING, and the digest then
        # injected it verbatim into every sibling lane's prompt with nothing to distinguish
        # it from an owner ruling. Provenance alone does not fix that — a `source` field
        # nobody filters on is decoration. So a lane-sourced record of a QUOTED kind is
        # refused unless it is marked `proposed`: it enters as a claim awaiting the seat's
        # review, and only the seat's `accept` makes it quotable.
        if (LANE_SOURCE_RE.match(rec["source"]) and rec["kind"] in LANE_GATED_KINDS
                and rec["status"] != "proposed"):
            raise Reject("lane-record-must-be-proposed",
                         "a %s banked by %s must carry status=proposed — a lane proposes, "
                         "the seat accepts (`index.py accept <id>`). Only an accepted "
                         "record is quoted to other lanes as estate law."
                         % (rec["kind"], rec["source"]))

    if rec["kind"] == "result":
        # TESTS is a COUNT OF RECORDS, each naming a command and an exit code, rather
        # than a number somebody typed at the end of a return.
        _need_str("ran", "ran-required",
                  "kind=result must say what RAN — a result with no run is a claim")
        _need_str("command", "command-required",
                  "kind=result must carry the exact COMMAND, so a reader can re-run it",
                  cap=1000)
        code = raw.get("exit")
        if isinstance(code, bool) or not isinstance(code, int):
            raise Reject("exit-required",
                         "kind=result must carry an integer exit code (got %r) — 'it "
                         "worked' is not an exit code" % (code,))
        rec["exit"] = code

    elif rec["kind"] == OPEN_KIND:
        _need_str("closes_when", "closes-when-required",
                  "kind=open must say what would CLOSE it — a runnable check, not a "
                  "feeling. An open question nobody can close is a worry, not a record")
        _need_str("owner", "owner-required",
                  "kind=open needs an OWNER who can close it ('seat' or a lane id)",
                  cap=120)
        if not LEARN_SOURCES_RE.match(rec["owner"]):
            raise Reject("owner-shape", "owner must be 'seat' or a lane id, got %r"
                         % rec["owner"])
        rc = raw.get("recheck")
        if not isinstance(rc, str) or not RECHECK_RE.match(rc.strip()):
            raise Reject("recheck-required",
                         "kind=open needs a recheck date YYYY-MM-DD — without one it ages "
                         "quietly into folklore instead of surfacing again (got %r)" % (rc,))
        rec["recheck"] = rc.strip()
        _scope_and_source()

    elif rec["kind"] == ALT_KIND:
        _need_str("method", "method-required",
                  "kind=alternative must name the METHOD — the path not taken")
        _need_str("when_to_try", "when-to-try-required",
                  "kind=alternative must say WHEN it would be worth trying")
        _need_str("cost", "cost-required",
                  "kind=alternative must state its COST — an alternative with no cost is "
                  "an opinion", cap=120)
        _scope_and_source()

    if rec["kind"] != LEARN_KIND:
        pass
    else:
        tag = raw.get("tag")
        if tag not in LEARN_TAGS:
            raise Reject("tag-enum", "tag %r outside %s" % (tag, list(LEARN_TAGS)))
        rec["tag"] = tag

        if len(rec["statement"]) > STATEMENT_MAX:
            raise Reject("statement-too-long",
                         "a learning's statement is %d chars; the bound is %d — a lesson "
                         "nobody can quote in one line is a lesson nobody quotes"
                         % (len(rec["statement"]), STATEMENT_MAX))

        _scope_and_source()

        named = [shape for shape, test in LEARN_EV_SHAPES
                 if any(test(item["ref"]) for item in clean)]
        if not named:
            raise Reject("evidence-unwalkable",
                         "a learning must cite something a reader can go and look at — %s. "
                         "Got: %s" % (", ".join(shape for shape, _t in LEARN_EV_SHAPES),
                                      ", ".join(repr(i["ref"]) for i in clean) or "nothing"))

    return {f: rec[f] for f in FIELDS if f in rec}


# ---------------------------------------------------------------------------
# store I/O
# ---------------------------------------------------------------------------
def parse_lines(text, source=""):
    """Parse JSONL, skipping blank lines. A corrupt line is loud, not silent."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            die("store-corrupt", "line %s%d is not JSON: %s" % (source and source + ":", n, exc))
    return out


def load_store(root):
    p = root / STORE
    if not p.is_file():
        return []
    return parse_lines(p.read_text(encoding="utf-8", errors="replace"), STORE)


def load_store_safe(root):
    """Read a store that is NOT ours — another project's, on the library shelf.
    A corrupt line is counted and skipped, never fatal (the loud `parse_lines`
    is for this repo's own store, where a corruption is our bug to fix).
    Returns (records, bad_line_count), or (None, 0) when it is unreachable."""
    p = pathlib.Path(root).expanduser() / STORE
    try:
        if not p.is_file():
            return None, 0
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, 0
    recs, bad = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(obj, dict):
            recs.append(obj)
        else:
            bad += 1
    return recs, bad


# ---------------------------------------------------------------------------
# the library — where the shelf lives
# ---------------------------------------------------------------------------
def library_root(a=None):
    """`--library-root` beats $NOTREST_LIBRARY_ROOT beats ~/.claude/notrest-library.
    One knob moves the WHOLE shelf (registry + projects file), which is what makes
    the fixture provable without ever touching the real one."""
    v = getattr(a, "library_root", None) or os.environ.get(LIB_ENV) or ""
    return pathlib.Path(v).expanduser().resolve() if v.strip() else LIB_DEFAULT


def registry_file(lib):
    return lib / REGISTRY


def projects_file(lib):
    """graph.py's cross-project registry — the shelf's sibling, so ONE registration
    feeds both consumers (the library's find, and `graph.py all`'s PM view)."""
    return lib.parent / PROJECTS


def read_registry(lib):
    """Every registered project, in registration order, last entry per root winning.
    A corrupt or foreign line is skipped, never fatal — the registry is append-only
    and may be written by a newer version of this script than the one reading it.
    Keys beyond {root, name, ts} are CARRIED, not dropped: the line's shape is open
    on purpose, so per-project metadata can land later without a migration."""
    p = registry_file(lib)
    try:
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        root = str(rec.get("root") or "").strip()
        if not root:
            continue
        name = str(rec.get("name") or "").strip() or pathlib.Path(root).name
        entry = dict(rec)
        entry.update({"root": root, "name": name, "ts": str(rec.get("ts") or "")})
        out[root] = entry
    return list(out.values())


def read_projects(p):
    """graph.py's own reader, mirrored: one path per line, '#' comments, deduped."""
    try:
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line not in out:
            out.append(line)
    return out


def concepts_file(lib):
    return lib / CONCEPTS


def read_concepts(lib):
    """The concept shelf, APPEND-ONLY like the store: a rename, a crown, a rebuild
    all APPEND, and the LAST line for a `C-<n>` is the one that counts. Returns the
    resolved concepts in id order."""
    p = concepts_file(lib)
    try:
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and CID_RE.match(str(rec.get("id", ""))):
            out[rec["id"]] = rec
    return sorted(out.values(), key=lambda c: int(CID_RE.match(c["id"]).group(1)))


def append_concepts(lib, rows):
    p = concepts_file(lib)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def append_record(root, raw, lib=None, notes=None, warns=None, strict_refs=False):
    """Validate under the lock (links are checked against what is really there),
    assign the next id, append one line. Returns the assigned id.

    The qualification check runs on the VALIDATED record and BEFORE the write, so the
    schema rules keep their precedence (a record that is malformed *and* names a bare
    id is still turned away by the rule it actually broke) and `--strict-refs` leaves
    the store byte-identical. `warns` is opt-in: a caller that does not pass a list
    gets the old output shape exactly, which is why `supersede`/`refute`/`crown` are
    untouched by this."""
    p = root / STORE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0)
            existing = parse_lines(fh.read(), STORE)
            known = {r.get("id") for r in existing}
            # isinstance FIRST: validate() is what turns a non-dict payload away with a
            # named rule, and probing `raw` before it ran replaced that clean rejection
            # with an AttributeError traceback. The probe must never outrank the door.
            prefix = KIND_PREFIX.get(
                raw.get("kind") if isinstance(raw, dict) else None, "F")
            top = 0
            for r in existing:
                m = ANY_ID_RE.match(str(r.get("id", "")))
                if m and m.group(1) == prefix:
                    top = max(top, int(m.group(2)))
            rec = validate(raw, known, lib=lib, notes=notes, root=root)
            bare = unqualified_refs(rec)
            if bare and strict_refs:
                raise Reject("unqualified-record-ref", " · ".join(bare) + " [--strict-refs]")
            if warns is not None:
                warns.extend(bare)
            # Two id spaces in one store: learnings number L-1.. independently of F-1..,
            # so banking a lesson never renumbers a finding and a citation stays stable.
            rec["id"] = "%s-%d" % (prefix, top + 1)
            ordered = {f: rec[f] for f in FIELDS if f in rec}
            fh.seek(0, os.SEEK_END)
            fh.write(json.dumps(ordered, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return rec["id"]


def sort_key(rec):
    m = ANY_ID_RE.match(str(rec.get("id", "")))
    return (rec.get("ts", ""), int(m.group(2)) if m else 0)


def resolve(records):
    """THE RESOLUTION RULE. The store is append-only, so no record's status is
    ever rewritten. A record's EFFECTIVE status is its own written status unless
    a later tombstone (a) names it in `links` and (b) opens its statement with
    `supersedes F-<id>` or `refutes F-<id>`. The last such tombstone in ts order
    wins. Returns {id: (effective_status, by_id_or_None)}."""
    eff = {r.get("id"): (r.get("status", "live"), None) for r in records}
    for r in sorted(records, key=sort_key):
        m = TOMB_RE.match(r.get("statement", "") or "")
        if not m:
            continue
        verb, target = m.group(1).lower(), m.group(2).upper()
        if target not in eff or target not in (r.get("links") or []):
            continue
        by = next((l for l in (r.get("links") or []) if l != target), r.get("id"))
        eff[target] = ("superseded" if verb == "supersedes" else "refuted", by)
    # ⛔ THE SEAT'S REVIEW IS A TOMBSTONE TOO. The store is append-only, so accepting a
    # lane's proposal cannot rewrite its status — it appends a ruling that names it, and
    # the resolver reads that ruling exactly as it reads a supersede. A proposal the seat
    # never ruled on stays `proposed` forever, which is the honest state: unreviewed.
    for r in sorted(records, key=sort_key):
        m = REVIEW_RE.match(r.get("statement", "") or "")
        if not m:
            continue
        verb, target = m.group(1).lower(), m.group(2).upper()
        if target not in eff or target not in (r.get("links") or []):
            continue
        if eff[target][0] in ("superseded", "refuted"):
            continue                       # a retired record is not un-retired by review
        eff[target] = ("live" if verb == "accepts" else "rejected", r.get("id"))
    return eff


def rests_on_refuted(rec, eff):
    """THE RESTS-ON-REFUTED RULE. A record that is itself effectively LIVE, and whose
    `links` names an id whose EFFECTIVE status is `refuted`, is standing on ground the
    store has already knocked out — a live decision resting on a refuted finding. It is
    NOT flipped by this (only a tombstone flips a status); it is FLAGGED, so the reader
    sees the dependency the link-walk already knows about.

    Exactly one hop: the links this record itself declares, resolved through `resolve`.
    A record that is not effectively live is never flagged — a superseded record's
    footing is already reported by its own status. A tombstone does not rest on what it
    killed: the target of this record's own `supersedes`/`refutes` head is skipped.
    Returns the flagged ids in link order (possibly empty)."""
    if eff.get(rec.get("id"), (rec.get("status", "live"), None))[0] != "live":
        return []
    own = TOMB_RE.match(rec.get("statement", "") or "")
    killed = own.group(2).upper() if own else None
    out = []
    for lid in rec.get("links") or []:
        if lid == killed or lid in out:
            continue
        if eff.get(lid, (None, None))[0] == "refuted":
            out.append(lid)
    return out


def head(text, width=90):
    one = " ".join((text or "").split())
    return one if len(one) <= width else one[:width - 1] + "…"


def labels_of(rec):
    seen = []
    for e in rec.get("evidence") or []:
        if e.get("label") not in seen:
            seen.append(e.get("label"))
    return ",".join(seen) if seen else "-"


def track_line(rec, eff):
    status, by = eff.get(rec.get("id"), (rec.get("status", "live"), None))
    tail = "" if status == "live" else " · %s by %s" % (status.upper(), by or "?")
    rests = rests_on_refuted(rec, eff)
    if rests:
        tail += " · RESTS-ON-REFUTED %s" % ",".join(rests)
    return "%s · %s · %s · %s · [%s]%s" % (
        rec.get("id", "F-?"), rec.get("kind", "?"), rec.get("relation", "?"),
        head(rec.get("statement", "")), labels_of(rec), tail)


# ---------------------------------------------------------------------------
# legacy index
# ---------------------------------------------------------------------------
def dossier_date(text, path):
    """The dossier's own date line if it declares one in its first 40 lines;
    otherwise the filesystem mtime (labelled as such by the caller)."""
    headtext = "\n".join(text.splitlines()[:40])
    m = DATE_DECL_RE.search(headtext) or DATE_BARE_RE.search(headtext)
    if m:
        return m.group(1)
    return datetime.fromtimestamp(path.stat().st_mtime,
                                  timezone.utc).strftime("%Y-%m-%d")


def dossier_files(root):
    for d in DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*Dossier.md")):
            yield d, p


def entries(root):
    out = []
    for d, p in dossier_files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), p.stem)
        date = dossier_date(text, p)
        head_lines, in_rmf = [], False
        for l in lines:
            if re.match(r"^#{1,3} .*Read Me First", l):
                in_rmf = True
                continue
            if in_rmf:
                if l.startswith("#") or l.startswith("---"):
                    break
                if l.strip():
                    head_lines.append(l.strip()[:200])
                if len(head_lines) >= 6:
                    break
        out.append((d, title, date, p.relative_to(root).as_posix(), head_lines))
    return out


def agent_ledger(root):
    """One index entry for the hook-written agent activity ledger, if present at
    the repo root. Returns (rel_path, entry_count) or None; degrades silently if
    the file is unreadable. entry_count = lines that start '- [' (one per agent)."""
    p = root / LEDGER
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    count = sum(1 for l in text.splitlines() if l.startswith("- ["))
    return (p.relative_to(root).as_posix(), count)


def compile_candidates(root):
    """One index entry for compile.py's repeated-work table, if present. Returns
    (rel_path, ripe_count, total_count) or None; degrades silently when the table
    or its data file is missing or unreadable. Counts come from the JSON the same
    scan wrote — the markdown beside it is the reading copy."""
    p = root / CANDIDATES
    if not p.is_file():
        return None
    ripe = total = 0
    try:
        data = json.loads((root / CANDIDATES_DATA).read_text(encoding="utf-8"))
        cands = data.get("candidates", [])
        total = len(cands)
        ripe = sum(1 for c in cands if c.get("ripe"))
    except Exception:
        pass
    return (p.relative_to(root).as_posix(), ripe, total)


def findings_entry(root):
    """One index entry for the findings store, if present: counts, never a copy."""
    recs = load_store(root)
    if not recs:
        return None
    eff = resolve(recs)
    live = sum(1 for r in recs if eff.get(r.get("id"), ("live",))[0] == "live")
    return (STORE, len(recs), live)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_scan(a):
    root = pathlib.Path(a.root).resolve()
    es = entries(root)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    buf = ["# ORACLE index — generated by archivist; do not hand-edit (re-run scan)",
           f"Last scan: {now} · {len(es)} dossier(s)", ""]
    for d, title, date, rel, head_lines in es:
        buf.append(f"### {title} — {date}")
        buf.append(f"folder: {d} · path: {rel}")
        buf.extend(head_lines)
        buf.append("")
    suffix = ""
    fe = findings_entry(root)
    if fe is not None:
        rel, total, live = fe
        buf.append(f"### findings store — {total} record(s), {live} live")
        buf.append(f"folder: archive · path: {rel}")
        buf.append("the session track — every skill's finding records, append-only; "
                   "read it with: index.py track")
        buf.append("")
        suffix += f" + findings ({live}/{total} live)"
    led = agent_ledger(root)
    if led is not None:
        rel, count = led
        buf.append(f"### agent activity ledger — {count} entr{'y' if count == 1 else 'ies'}")
        buf.append(f"folder: (repo root) · path: {rel}")
        buf.append("agent activity ledger — which agents ran, what each concluded; "
                   "entries point at full transcripts")
        buf.append("")
        suffix += f" + agent ledger ({count})"
    cc = compile_candidates(root)
    if cc is not None:
        rel, ripe, total = cc
        buf.append(f"### compile candidates — {ripe} ripe of {total}")
        buf.append(f"folder: compile · path: {rel}")
        buf.append("compile candidates — repeated work the estate has recorded; "
                   "ripe rows are ready to compile")
        buf.append("")
        suffix += f" + compile candidates ({ripe}/{total} ripe)"
    (root / INDEX).write_text("\n".join(buf) + "\n", encoding="utf-8")
    print(f"{root / INDEX}: {len(es)} entries{suffix}")


def read_payload(a):
    if a.json:
        text = a.json
    else:
        text = sys.stdin.read()
    if not text.strip():
        die("no-input", "pass --json '<record>' or pipe the record on stdin")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        die("json-parse", str(exc))


def _evidence_from_flag(ref):
    """Turn a bare `--evidence` token into the store's evidence object.

    The type is INFERRED from the shape the record schema already names, so a model
    banking a lesson does not have to know the object grammar to obey it: a bracketed
    stamp is a coord-line, a path is a path, a record id is a record, anything else is a
    command (a commit hash lives there). The label is [cited] because a learning's
    evidence is always something the writer looked at — a guess is not evidence.
    """
    ref = str(ref).strip()
    if COORD_TS_RE.search(ref):
        return {"type": "coord-line", "ref": ref, "label": "cited"}
    if re.match(r"^[FLOA]-\d+$", ref) or REC_REF_RE.match(ref):
        return {"type": "record", "ref": ref, "label": "cited"}
    if URL_RE.match(ref):
        return {"type": "url", "ref": ref, "label": "cited"}
    if "/" in ref or ref.endswith(".md") or ref.endswith(".py"):
        return {"type": "path", "ref": ref, "label": "cited"}
    return {"type": "command", "ref": ref, "label": "cited"}


def payload_from_flags(a):
    """⛔ THE SEAM THE STOP GATE ACTUALLY USES. The hook's block reason tells the model to
    run `add --kind learning --tag ... --statement ... --evidence ... --scope ...`, and
    until 4.6.3 `add` took only --json/stdin — so the one instruction the gate gives at the
    exact moment a lesson is being banked was live-rejected with "unrecognized arguments".
    A gate that blocks on an instruction the tool refuses is a gate that teaches people to
    work around it.

    These flags BUILD the same dict the JSON form builds and hand it to the same
    `validate()`. There is no second validation path, so no rule can hold on one form and
    not the other.
    """
    rec = {"kind": a.kind, "statement": a.statement or "",
           "evidence": [_evidence_from_flag(e) for e in (a.evidence or [])]}
    if a.kind == LEARN_KIND:
        rec["tag"] = a.tag
    # Only the fields THIS kind may carry are copied across — the per-field form must not
    # be a back door around the same gate the JSON form goes through.
    for f in KIND_ONLY_FIELDS.get(a.kind, ()):
        if f in ("tag", "scope", "source"):
            continue
        v = getattr(a, f, None)
        if v is not None:
            rec[f] = v
    if "scope" in KIND_ONLY_FIELDS.get(a.kind, ()):
        rec["scope"] = list(a.scope or [])
        rec["source"] = a.source
    for f in ("session", "skill", "ask"):
        v = getattr(a, f, "") or ""
        if v:
            rec[f] = v
    return rec


def cmd_add(a):
    root = pathlib.Path(a.root).resolve()
    flagged = bool(a.kind or a.statement or a.tag or a.evidence or a.scope
                   or a.closes_when or a.owner or a.recheck or a.method
                   or a.when_to_try or a.cost or a.ran or a.command
                   or getattr(a, "exit", None) is not None)
    if flagged and a.json:
        die("mixed-input-form",
            "pass EITHER --json/stdin OR the per-field flags, never both — two payloads "
            "in one call is two records nobody can tell apart")
    if flagged:
        if not a.kind:
            die("kind-enum", "the per-field form needs --kind (e.g. --kind learning)")
        # ⛔ REFUSE, NEVER SILENTLY DROP. Copying only the fields this kind may carry made
        # `--kind finding --owner seat` succeed with the owner thrown away — the JSON form
        # rejects that exact record. A form that quietly discards half of what it was told
        # is worse than one that refuses: the caller believes it banked what it typed.
        allowed = KIND_ONLY_FIELDS.get(a.kind, ())
        stray = [f for f in EXTRA_FIELDS
                 if f not in allowed and f not in ("scope", "source")
                 and getattr(a, f, None) not in (None, "", [])]
        if a.tag and a.kind != LEARN_KIND:
            stray.append("tag")
        if a.scope and "scope" not in allowed:
            stray.append("scope")
        if stray:
            die("kind-only-field",
                "%s belong(s) to another kind, not kind=%s (this kind takes: %s)"
                % (", ".join(sorted(set(stray))), a.kind,
                   ", ".join(allowed) if allowed else "none"))
        raw = payload_from_flags(a)
    else:
        raw = read_payload(a)
    notes, warns = [], []
    try:
        # The id goes to stdout alone — callers capture it. Notes and warns go to
        # stderr, so a warned record still round-trips through `out="$(… add …)"`.
        rid = append_record(root, raw, lib=library_root(a), notes=notes,
                            warns=warns, strict_refs=getattr(a, "strict_refs", False))
    except Reject as r:
        die(r.rule, r.detail)
    print(rid)
    for n in notes:
        sys.stderr.write("note: %s\n" % n)
    for w in warns:
        sys.stderr.write("warn: unqualified-record-ref — %s\n" % w)


def select(records, a):
    eff = resolve(records)
    out = []
    for r in sorted(records, key=sort_key):
        if a.session and r.get("session") != a.session:
            continue
        if a.kind and r.get("kind") != a.kind:
            continue
        if a.status and eff.get(r.get("id"), ("live", None))[0] != a.status:
            continue
        out.append(r)
    return out, eff


# ---------------------------------------------------------------------------
# the learnings loop
# ---------------------------------------------------------------------------
DIGEST_MAX_BYTES = 200


def load_store_tolerant(root):
    """The store, read for a CONSUMER rather than for a writer.

    `load_store` is deliberately LOUD — it dies at exit 2 on a corrupt line, because for
    `add`/`track` this repo's own store being malformed is our bug to fix. The learnings
    loop has the opposite duty: it is read by a SessionStart/Stop hook and by the ship
    gate, and one bad byte in a JSONL file must never take a session or a gate down. So
    the read paths below skip what they cannot parse and carry on. Live-proven necessary:
    eval exited 2 through this call because `die()` raises SystemExit, which no
    `except Exception` catches.
    """
    p = pathlib.Path(root) / STORE
    if not p.is_file():
        return []
    out = []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def learning_records(records, include_superseded=False, include_proposed=False):
    """Every LIVE learning in the store, NEWEST FIRST — the order a reader wants.

    ⛔ A RETIRED LESSON MUST NOT KEEP TEACHING. Every read path here feeds something that
    ACTS on it — the spawn-gate digest injected into lane prompts, the packet block a
    successor reads as inherited law, the router line. A superseded learning that still
    appears in those is a rule the estate revoked and kept enforcing, which is worse than
    never having banked it: nobody downstream can tell it was withdrawn. It stays in the
    store and stays citable as evidence; it simply stops being quoted as current.
    """
    eff = resolve(records)
    out = []
    for r in records:
        if r.get("kind") != LEARN_KIND:
            continue
        status, by = eff.get(r.get("id"), ("live", None))
        if status == "proposed" and not include_proposed:
            continue
        if status in ("superseded", "refuted", "rejected") and not include_superseded:
            continue
        r = dict(r)
        r["status"] = status
        r["superseded_by"] = by
        out.append(r)
    return sorted(out, key=sort_key, reverse=True)


def scope_matches(rec, tokens):
    """Does this learning apply to any of `tokens`?

    'estate' in a record's scope means it applies to everything, so it always matches.
    Otherwise a token matches when it equals a scope entry, or when the entry is a glob
    the token satisfies, or when the token is a glob the ENTRY satisfies — the caller may
    be asking 'what applies to this file?' (token=path, entry=glob) or 'what applies
    anywhere under here?' (token=glob, entry=path), and both are the same question.
    """
    if not tokens:
        return True
    scope = rec.get("scope") or []
    if "estate" in scope:
        return True
    for tok in tokens:
        for entry in scope:
            if tok == entry or fnmatch.fnmatch(tok, entry) or fnmatch.fnmatch(entry, tok):
                return True
    return False


def _clip_bytes(text, limit):
    """Clip to a BYTE bound without splitting a character. The packet's line law is
    counted in bytes (a hook writes bytes), and a naive character clip on an estate
    full of em-dashes overshoots it."""
    b = text.encode("utf-8")
    if len(b) <= limit:
        return text
    return b[:limit].decode("utf-8", "ignore")


def digest_line(rec):
    """THE SHARED DIGEST FORMAT — packet, spawn-gate and router all render this.

    `| L-<n> [TAG] <statement clipped> — evidence: <first>`

    One line, framed with '| ' so nothing it contains can reach column 0 and be read as
    structure by whatever is quoting it, and clipped to 200 bytes so a long lesson cannot
    blow a hook's output budget. Control characters are rendered, never emitted raw.
    """
    ev = (rec.get("evidence") or [{}])[0].get("ref", "-")
    body = "%s [%s] %s — evidence: %s" % (rec.get("id", "L-?"), rec.get("tag", "?"),
                                          collapse_ctrl(rec.get("statement", "")),
                                          collapse_ctrl(ev))
    return _clip_bytes("| " + body, DIGEST_MAX_BYTES)


def collapse_ctrl(text):
    """Render control characters instead of emitting them (4.6.0 refuter invariant):
    a newline inside a statement would break the one-line law and let a record forge a
    second line of somebody else's output."""
    out = []
    for ch in str(text or ""):
        if ch in "\r\n":
            out.append("\\n")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("\\x%02x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def _norm_since(raw):
    """Accept either shape a caller has to hand: a record ts (2026-09-05T04:45:00Z) or a
    COORD ledger stamp (2026-09-05 04:45Z, with or without brackets). Returns a string
    comparable against a record's ISO ts, or None."""
    txt = (raw or "").strip()
    m = COORD_TS_RE.search(txt)
    if m:
        txt = m.group(1)
    if TS_RE.match(txt):
        return txt
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})Z?$", txt)
    if m:
        return "%sT%s:%s:00Z" % (m.group(1), m.group(2), m.group(3))
    if re.match(r"^\d{4}-\d{2}-\d{2}$", txt):
        return txt + "T00:00:00Z"
    return None


LEDGER_PREFIX_RE = re.compile(
    r"^\s*-\s*\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z\]\s*(?:\[[^\]]*\]\s*)?")
# ⛔ A LINE WITHOUT AN ARROW MUST NOT BECOME ONE ENORMOUS HEADLINE (live, 2026-09-05).
HEADLINE_MAX_CHARS = 120


def headline(line, strip_prefix=False):
    """What a ledger line CLAIMS, not what it reports — and only the CLAIM.

    Two bounds, and the headline is whichever is SHORTER:
      · everything before the first "->". The estate's grammar is
        `ask -> landed | evidence`, so a SHIP line whose report half mentions "refuter
        round (3 defects fixed)" describes a round that CLOSED; reading the whole line
        makes the successful fix indistinguishable from the failure.
      · the first HEADLINE_MAX_CHARS characters. A 613-char line with no "->" mentioned
        STOPPED at char 477 while DESCRIBING this regex, fired the gate and blocked the
        seat. A tag that far in is a mention, not a claim.

    `strip_prefix` drops the `- [ts] [lane] ` bookkeeping for DISPLAY only. The MATCH runs
    on the un-stripped headline, so a lane id can never be the thing that fires a trigger
    and stripping can never change what counts as one.
    """
    text = str(line or "")
    # ⛔ THE CAP APPLIES ONLY WHERE THERE IS NO ARROW. Measured on this ledger: 207 of 338
    # ask-halves are longer than 120 characters, so capping an ARROWED line blinded the
    # correction regex on 43% of well-formed lines — the estate writes long asks, and the
    # arrow already says exactly where the claim ends. The cap exists solely for the
    # degenerate case it was added for: a line with NO arrow, where without a bound the
    # whole 600-character entry becomes its own headline and any tag anywhere fires.
    if "->" in text:
        head = text.split("->")[0]
    else:
        head = text[:HEADLINE_MAX_CHARS]
    return LEDGER_PREFIX_RE.sub("", head) if strip_prefix else head


def coord_volumes(root):
    """Every COORD ledger volume at the root, oldest name first. COORD-AGENTS.md is the
    agent index, not a ledger of asks, and is never a trigger source."""
    try:
        names = sorted(os.listdir(str(root)))
    except OSError:
        return []
    return [pathlib.Path(root) / n for n in names
            if n.startswith("COORD") and n.endswith(".md") and n != "COORD-AGENTS.md"]


def ledger_lines(root):
    """[(ts, ordinal, total, line, source)] for every stamped ledger line.

    `ordinal` is 1-based within the stamp, in FILE ORDER — the same order an append-only
    ledger was written in, which is the only ordering a minute-resolution stamp cannot
    supply for itself.
    """
    rows = []
    for path in coord_volumes(root):
        try:
            txt = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in txt.splitlines():
            m = LEDGER_LINE_RE.match(line)
            if m:
                rows.append([m.group(1), 0, 0, line, path.name])
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    seen = {}
    for r in rows:
        seen[r[0]] = seen.get(r[0], 0) + 1
        r[1], r[2] = seen[r[0]], counts[r[0]]
    return [tuple(r) for r in rows]


def cite_key(ts, ordinal, total):
    """How a line must be CITED. A stamp with one line is named by the stamp; a stamp with
    several is named by stamp + ordinal, because otherwise the citation is ambiguous and
    ambiguity here means a debt silently discharged."""
    return ts if total <= 1 else "%s#%d" % (ts, ordinal)


def trigger_lines(root, since=None):
    """⛔ THE ONE IMPLEMENTATION of 'what counts as a trigger'.

    Returns [{ts, headline, source}] — COORD lines whose HEADLINE carries an uppercase
    tag saying the estate just paid for a lesson. eval imports this function; lane H's
    Stop hook calls the CLI that wraps it. Neither re-implements the match, because two
    implementations of a rule are two rules the moment somebody edits one — and then the
    hook prompts for lessons the gate does not audit, or the gate reddens on lines the
    hook never surfaced.
    """
    rx = re.compile(LEARN_TRIGGER_REGEX)          # case-SENSITIVE, by ruling
    out = []
    for ts, ordinal, total, line, source in ledger_lines(root):
        if not rx.search(headline(line)):
            continue
        if since and ts[:16] < str(since)[:16].replace("T", " "):
            continue
        out.append({"ts": ts, "key": cite_key(ts, ordinal, total),
                    "ordinal": ordinal, "of": total,
                    "headline": " ".join(headline(line, strip_prefix=True).split()),
                    "source": source})
    out.sort(key=lambda t: (t["ts"], t["ordinal"]))
    return out


def _cite_keys(records, kinds=None):
    """The CITE KEYS a set of records name: 'ts' for a bare stamp, 'ts#k' for an ordinal.

    ⛔ A BARE STAMP NAMES A MINUTE, NOT A LINE. It therefore satisfies a stamp that carries
    exactly ONE line and nothing else — with two lines in a minute, a bare citation cannot
    say which one it discharged, and treating it as both is how one banked lesson closed
    two different debts."""
    seen = set()
    eff = resolve(records)
    for r in records:
        if kinds is not None and r.get("kind") not in kinds:
            continue
        # A superseded/refuted record was withdrawn; a withdrawn citation discharges
        # nothing, or a debt could be closed by a claim the estate has since retracted.
        if eff.get(r.get("id"), ("live", None))[0] != "live":
            continue          # proposed / rejected / retired all discharge nothing
        for item in (r.get("evidence") or []):
            if isinstance(item, dict):
                for m in COORD_TS_RE.finditer(str(item.get("ref", ""))):
                    seen.add("%s#%s" % (m.group(1), m.group(2)) if m.group(2)
                             else m.group(1))
    return seen


def cited_stamps(records):
    """Cite keys named by a LEARNING — what the correction half of the loop reads."""
    return _cite_keys(records, kinds=(LEARN_KIND,))


def learning_floor(records):
    """⛔ WHEN THE LOOP WAS ARMED — the line before which nothing is owed.

    The floor is the EARLIEST evidence timestamp any learning cites: the estate's own
    record of how far back the practice reaches. Everything older is GRANDFATHERED and is
    never returned, because grading an estate against a rule it did not have is how a gate
    becomes something people switch off — live-proven, 2026-09-05: with the floor missing,
    the Stop gate fired on a 2026-07-25 ledger line six weeks older than the first learning
    that ever existed.

    Fallback: a learning that cites only a commit hash or a briefs/ path pins no ledger
    stamp, so the earliest learning RECORD's own ts stands in — otherwise banking one such
    lesson would suddenly un-grandfather the entire history, which is the same defect
    arriving by a different door. Returns a ledger-shaped stamp, or None when unarmed.
    """
    learn = [r for r in records if r.get("kind") == LEARN_KIND]
    if not learn:
        return None
    stamps = sorted(k.split("#")[0] for k in cited_stamps(records))
    if stamps:
        return stamps[0]
    ts = sorted(str(r.get("ts", "")) for r in learn if r.get("ts"))
    return (ts[0][:16].replace("T", " ") + "Z") if ts else None


def untested_lines(root, since=None):
    """[{ts, key, headline}] — ledger lines admitting a gap, in body scope."""
    rx = re.compile(UNTESTED_REGEX, re.I)
    out = []
    for ts, ordinal, total, line, _src in ledger_lines(root):
        if not rx.search(QUOTED_SPAN_RE.sub(" ", body(line))):
            continue
        if since and ts[:16] < str(since)[:16].replace("T", " "):
            continue
        out.append({"ts": ts, "key": cite_key(ts, ordinal, total),
                    "ordinal": ordinal, "of": total,
                    "headline": " ".join(headline(line, strip_prefix=True).split())})
    out.sort(key=lambda t: (t["ts"], t["ordinal"]))
    return out


def open_cited_stamps(records):
    """COORD stamps carried forward by ANY record.

    ⛔ THE DEBT IS "CARRY IT FORWARD", NOT "FILE AN OPEN". An earlier cut demanded an
    `open` record specifically, which got the direction backwards: a `result` that went
    back and VERIFIED the claim (with its ran/command/exit) discharges the admission
    better than an open question ever could, and so does a decision that ruled it out or a
    learning that banked what it taught. Live case: "closing the last [unverified] ship
    gate" was verified in the same turn and banked as a result — under the old rule the
    estate would have been told it still owed an open question about something it had
    already proven. Any record citing the stamp satisfies it; `open` is simply the one to
    file when the answer is still "not yet".
    """
    return _cite_keys(records)


def _cite_token(t):
    """What a caller must paste into `add --evidence`. Bracketed, and carrying the ordinal
    whenever the minute holds more than one line — the shape a consumer READS is the shape
    it must WRITE."""
    return "[%s]%s" % (t["ts"], "#%d" % t["ordinal"] if t.get("of", 1) > 1 else "")


def trigger_report(root, since=None):
    """THE CONTRACT both consumers read. One dict, one shape, one home:

      {"armed": bool, "floor": "<ts>|null", "regex": "...",
       "uncited": [{"ts": "[YYYY-MM-DD HH:MMZ]", "headline": "..."}], "cited": <n>}

    `uncited[].ts` is BRACKETED — it is pasted straight into
    `add --evidence '[<ts>]'`, so the shape a caller reads is the shape it must write.
    `floor` is the bare stamp: it is a boundary, not a citation.
    """
    recs = load_store_tolerant(root)
    floor = learning_floor(recs)
    # `untested` is ADDITIVE (4.7): the five original keys keep their exact meaning, so a
    # consumer that reads only them is unaffected.
    report = {"armed": floor is not None, "floor": floor,
              "regex": LEARN_TRIGGER_REGEX, "uncited": [], "cited": 0, "untested": []}
    if floor is None:
        return report                       # unarmed: nothing is owed, and we say so
    cited = cited_stamps(recs)
    bound = floor[:16]
    if since:
        s_norm = str(since)[:16].replace("T", " ")
        bound = max(bound, s_norm)
    for t in trigger_lines(root):
        if t["ts"][:16] < bound:
            continue                        # grandfathered
        if t["key"] in cited:
            report["cited"] += 1
        else:
            report["uncited"].append({"ts": _cite_token(t),
                                      "headline": collapse_ctrl(t["headline"])})
    open_cited = open_cited_stamps(recs)
    for u in untested_lines(root):
        if u["ts"][:16] < bound or u["key"] in open_cited:
            continue
        report["untested"].append({"ts": _cite_token(u),
                                   "headline": collapse_ctrl(u["headline"])})
    return report


def triggers_with_citation(root, since=None):
    """Every trigger IN WINDOW, each marked cited or not — the list form of the report."""
    recs = load_store_tolerant(root)
    floor = learning_floor(recs)
    if floor is None:
        return []
    cited = cited_stamps(recs)
    bound = floor[:16]
    if since:
        bound = max(bound, str(since)[:16].replace("T", " "))
    out = []
    for t in trigger_lines(root):
        if t["ts"][:16] < bound:
            continue
        t["cited"] = t["key"] in cited
        out.append(t)
    return out


# ---------------------------------------------------------------------------
# THE CARD — the four-box block a lane return ends with, and the estate renders back
# ---------------------------------------------------------------------------
# ⛔ ONE GRAMMAR, TWO DIRECTIONS. `index.py card` RENDERS it from the store; the
# agent-ledger hook PARSES it out of a lane return and banks each line as a record. Both
# use the constants below, so a lane cannot write a block the estate cannot read.
#
#   TESTS (n)
#   - [x] <statement> — ran: <ran> · command: `<cmd>` · exit: <n>
#   OPEN (n)
#   - [ ] <statement> — closes when: <what> · owner: <who> · recheck: <YYYY-MM-DD>
#   FINDINGS (n)
#   - [x] <statement> — evidence: <ref>
#   LEARNINGS (n)
#   - [x] [TAG] <statement> — evidence: <ref>
#
# THE KIND COMES FROM THE BOX, never from the checkbox. `[ ]` means "still open" and only
# OPEN uses it; a parser that keyed on the checkbox would bank a half-finished TEST as an
# open question. The box header is the discriminator, and the field tail after " — " is
# `key: value` pairs joined by " · ".
CARD_BOXES = (("TESTS", "result"), ("OPEN", OPEN_KIND),
              ("FINDINGS", "finding"), ("LEARNINGS", LEARN_KIND))
CARD_HEADER_RE = re.compile(r"^\s*(TESTS|OPEN|FINDINGS|LEARNINGS)\s*\((\d+)\)\s*$")
CARD_ITEM_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+(.*\S)\s*$")
CARD_TAIL_SEP = " — "
CARD_PAIR_SEP = " · "
CARD_FIELD_KEYS = {"ran": "ran", "command": "command", "exit": "exit",
                   "closes when": "closes_when", "owner": "owner", "recheck": "recheck",
                   "evidence": "evidence", "method": "method",
                   "when to try": "when_to_try", "cost": "cost"}


def _card_tail(rec):
    """The ` — key: value · key: value` tail for one rendered line."""
    kind = rec.get("kind")
    pairs = []
    if kind == "result" and rec.get("command") is not None:
        pairs = [("ran", rec.get("ran", "?")),
                 ("command", "`%s`" % rec.get("command")),
                 ("exit", rec.get("exit"))]
    elif kind == "result":
        # A result banked BEFORE ran/command/exit were required. Rendering "command: `?` ·
        # exit: None" would dress a legacy record as a broken new one; it is neither. Show
        # what it actually carries, and say plainly that the run was not recorded.
        ev = (rec.get("evidence") or [{}])[0].get("ref", "-")
        pairs = [("evidence", ev), ("run", "not recorded (pre-4.7 record)")]
    elif kind == OPEN_KIND:
        pairs = [("closes when", rec.get("closes_when", "?")),
                 ("owner", rec.get("owner", "?")),
                 ("recheck", rec.get("recheck", "?"))]
    else:
        ev = (rec.get("evidence") or [{}])[0].get("ref", "-")
        pairs = [("evidence", ev)]
    return CARD_TAIL_SEP + CARD_PAIR_SEP.join("%s: %s" % (k, v) for k, v in pairs)


def card_line(rec):
    """One rendered card line. Control characters are rendered, never emitted: a record is
    content somebody typed, and a newline inside it would forge a second item."""
    box = "[ ]" if rec.get("kind") == OPEN_KIND else "[x]"
    stmt = collapse_ctrl(rec.get("statement", ""))
    if rec.get("kind") == LEARN_KIND:
        stmt = "[%s] %s" % (rec.get("tag", "?"), stmt)
    return "- %s %s%s" % (box, stmt, collapse_ctrl(_card_tail(rec)))


def card_report(root, scope=None):
    """{box: [records]} for the four boxes, newest first, optionally scope-filtered."""
    recs = load_store_tolerant(root)
    eff = resolve(recs)
    out = {}
    for label, kind in CARD_BOXES:
        sel = [r for r in recs if r.get("kind") == kind
               and eff.get(r.get("id"), ("live", None))[0] == "live"]
        if scope:
            # Only the scoped kinds can be filtered; a result or finding carries no scope,
            # so filtering them by one would silently empty two boxes.
            sel = [r for r in sel if not r.get("scope") or scope_matches(r, scope)]
        out[label] = sorted(sel, key=sort_key, reverse=True)
    return out


def parse_card(text):
    """⛔ THE PARSER THE HOOK CALLS, so a lane return and the estate cannot drift.

    Returns [{kind, statement, checked, <fields>}] in the order the block lists them. A
    line outside a box is ignored; an unknown key in the tail is kept verbatim under its
    own name rather than dropped, because silently discarding half a lane's return is the
    defect this whole card exists to prevent.
    """
    kind_of = dict(CARD_BOXES)
    out, box = [], None
    declared, seen = {}, {}
    for line in str(text or "").splitlines():
        h = CARD_HEADER_RE.match(line)
        if h:
            box = h.group(1)
            # N3 (refuter): the count was captured and thrown away. It is the ONE piece of
            # redundancy the card has — a lane that writes "OPEN (3)" and lists two has
            # either lost an item or miscounted, and both are worth knowing. It is recorded
            # and reported, never enforced by refusal: rejecting the whole card would throw
            # away three good items to punish one bad number, which is the opposite of what
            # this block is for.
            declared[box] = int(h.group(2))
            seen.setdefault(box, 0)
            continue
        m = CARD_ITEM_RE.match(line)
        if not m or box is None:
            continue
        checked, body = m.group(1).lower() == "x", m.group(2)
        item = {"kind": kind_of[box], "checked": checked}
        if CARD_TAIL_SEP in body:
            stmt, tail = body.split(CARD_TAIL_SEP, 1)
            for pair in tail.split(CARD_PAIR_SEP):
                if ":" not in pair:
                    continue
                k, v = pair.split(":", 1)
                key = CARD_FIELD_KEYS.get(k.strip().lower(), k.strip().lower())
                val = v.strip().strip("`")
                # ⛔ TYPE AT THE SOURCE, NOT AT THE BOUNDARY. `exit` is rendered as text
                # and `add` requires an INTEGER, so a parsed TESTS box could never bank —
                # every consumer would have had to coerce it, and the first one that
                # forgot would fail silently. Numeric here becomes an int; a NON-numeric
                # value is left exactly as written, so `add` refuses it with its own
                # exit-required rule rather than this parser inventing a 0.
                if key == "exit" and re.match(r"^[+-]?\d+$", val):
                    val = int(val)
                item[key] = val
        else:
            stmt = body
        stmt = stmt.strip()
        tagm = re.match(r"^\[([A-Z]+)\]\s+(.*)$", stmt)
        if tagm and item["kind"] == LEARN_KIND:
            item["tag"], stmt = tagm.group(1), tagm.group(2)
        item["statement"] = stmt
        seen[box] = seen.get(box, 0) + 1
        out.append(item)
    for b, n in declared.items():
        if seen.get(b, 0) != n:
            out.append({"kind": "_count_mismatch", "box": b, "declared": n,
                        "seen": seen.get(b, 0), "statement":
                        "%s header says %d, %d item(s) listed" % (b, n, seen.get(b, 0))})
    return out


def lib_learnings_file(lib):
    return lib / LIB_LEARNINGS


def read_lib_learnings(lib):
    """The shelf's promoted lessons, newest first. Tolerant: the shelf is shared with
    other estates and may be written by a newer version of this script than the one
    reading it, so one unreadable line never costs a session its digest."""
    p = lib_learnings_file(lib)
    out = []
    try:
        if not p.is_file():
            return []
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    out.sort(key=lambda r: str(r.get("ts", "")), reverse=True)
    return out


def cmd_review(a):
    """`accept` / `reject` — THE SEAT'S RULING on a lane's proposal.

    Append-only, like every other status flip: a ruling record names the target in its
    statement head and in `links`, and `resolve()` reads it. Accepting makes the record
    quotable — it joins the digest the spawn-gate injects, the packet block a successor
    reads, and the router line. Rejecting retires it with the reason on the record, so the
    next reader can see the claim was made AND that it was turned down; a silent delete
    would leave the lane's sentence looking like it was never proposed.
    """
    root = pathlib.Path(a.root).resolve()
    target = a.record.upper()
    recs = load_store_tolerant(root)
    match = [r for r in recs if str(r.get("id")) == target]
    if not match:
        die("no-such-record", "no record %s in %s" % (target, STORE))
    rec = match[0]
    eff = resolve(recs)
    status = eff.get(target, ("live", None))[0]
    verb = "accepts" if a.accepting else "rejects"
    if status in ("superseded", "refuted"):
        die("review-retired", "%s is already %s — a retired record is not reviewed"
                              % (target, status))
    if verb == "accepts" and status == "live":
        print("%s is already accepted" % target)
        return
    if not a.accepting and not (a.why or "").strip():
        die("why-required", "`reject` needs --why: a claim turned down without a reason "
                            "is indistinguishable from one that was lost")
    why = (" " + a.why.strip()) if a.why else ""
    stmt = "%s %s — reviewed by the seat.%s" % (verb, target, why)
    raw = {"ts": now_z(), "session": a.session, "skill": "archivist",
           "kind": "decision", "ask": "", "statement": stmt,
           "evidence": [{"type": "record", "ref": target, "label": "cited"}],
           "relation": "back", "links": [target], "status": "live"}
    try:
        rid = append_record(root, raw, lib=library_root(a), notes=[])
    except Reject as r:
        die(r.rule, r.detail)
    print(rid)


def cmd_promote(a):
    """⛔ A LESSON TRAVELS ONLY WHEN ITS AUTHOR SAID IT SHOULD.

    Promotion copies a learning onto the machine-wide shelf, where every other estate's
    packet will quote it. That is a big claim to make on somebody else's behalf, so the
    gate is the record's OWN scope: it must carry `library`. A lesson scoped to this
    repo's hooks is true HERE; shipping it to an unrelated project would be the estate
    asserting something it never checked.

    The shelf copy keeps the origin (project name + local id) so a reader can walk back to
    the estate that paid for it, and promotion is IDEMPOTENT on that pair.
    """
    root = pathlib.Path(a.root).resolve()
    lib = library_root(a)
    recs = load_store_tolerant(root)
    match = [r for r in recs if str(r.get("id")) == a.record]
    if not match:
        die("no-such-record", "no record %r in %s" % (a.record, STORE))
    rec = match[0]
    if rec.get("kind") != LEARN_KIND:
        die("promote-kind", "only a learning travels; %s is kind=%s"
                            % (a.record, rec.get("kind")))
    if LIB_SCOPE not in (rec.get("scope") or []):
        die("promote-scope",
            "%s is not scoped `%s` — a lesson travels only when its author said it "
            "should. Its scope is: %s" % (a.record, LIB_SCOPE,
                                          ", ".join(rec.get("scope") or []) or "none"))
    name = a.project or root.name
    out = dict(rec)
    out["origin_project"] = name
    out["origin_id"] = rec.get("id")
    existing = read_lib_learnings(lib)
    for e in existing:
        if e.get("origin_project") == name and e.get("origin_id") == rec.get("id"):
            print("%s already on the shelf" % a.record)
            return
    p = lib_learnings_file(lib)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0, os.SEEK_END)
            fh.write(json.dumps(out, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    print("%s promoted to %s" % (a.record, tilde_path(p)))


def tilde_path(p):
    home = str(pathlib.Path.home())
    sp = str(p)
    return "~" + sp[len(home):] if sp.startswith(home) else sp


def proposed_counts(root):
    """{kind: n} of records a LANE proposed and the seat has not yet ruled on."""
    recs = load_store_tolerant(root)
    eff = resolve(recs)
    out = {}
    for r in recs:
        if eff.get(r.get("id"), ("live", None))[0] == "proposed":
            out[r.get("kind")] = out.get(r.get("kind"), 0) + 1
    return out


def cmd_card(a):
    root = pathlib.Path(a.root).resolve()
    rep = card_report(root, scope=a.scope)
    if a.json:
        print(json.dumps({"counts": {k: len(v) for k, v in rep.items()},
                          "boxes": rep}, ensure_ascii=False, indent=1))
        return
    prop = proposed_counts(root)
    if prop:
        print("PROPOSED (%d awaiting review): %s"
              % (sum(prop.values()),
                 ", ".join("%s %d" % (k, v) for k, v in sorted(prop.items()))))
    for label, _kind in CARD_BOXES:
        rows = rep[label]
        print("%s (%d)" % (label, len(rows)))
        for r in rows[:a.limit] if (a.limit is not None and a.limit >= 0) else rows:
            print(card_line(r))


def cmd_learnings(a):
    # --trigger-regex answers from the constant and stops: it is the ONE home of the
    # regex, and a consumer asking for it must not also have to have a store.
    if getattr(a, "trigger_regex", False):
        print(LEARN_TRIGGER_REGEX)
        return
    root = pathlib.Path(a.root).resolve()

    if getattr(a, "library", False):
        # The SHELF's lessons, not this estate's: what every other project paid for.
        recs = learning_records(read_lib_learnings(library_root(a)),
                                include_superseded=getattr(a, "include_superseded", False))
        if a.limit is not None and a.limit >= 0:
            recs = recs[:a.limit]
        if a.json:
            print(json.dumps({"count": len(recs), "records": recs},
                             ensure_ascii=False, indent=1))
            return
        for r in recs:
            line = digest_line(r)
            origin = r.get("origin_project")
            if origin and a.digest:
                line = _clip_bytes("%s [%s]" % (line, origin), DIGEST_MAX_BYTES)
            print(line)
        return

    # --triggers answers a different question from the rest of the verb: not "what have we
    # learned" but "what did we pay for that nobody has banked yet".
    if getattr(a, "triggers", False):
        since = None
        if a.since:
            since = _norm_since(a.since)
            if since is None:
                die("since-format", "--since must be a record ts, a ledger stamp or a "
                                    "date, got %r" % a.since)
        if a.json:
            print(json.dumps(trigger_report(root, since=since),
                             ensure_ascii=False, indent=1))
            return
        rep = trigger_report(root, since=since)
        if not rep["armed"]:
            print("loop not armed — no kind=learning record yet, so nothing is owed")
            return
        trigs = triggers_with_citation(root, since=since)
        if getattr(a, "uncited", False):
            trigs = [t for t in trigs if not t["cited"]]
        if a.limit is not None and a.limit >= 0:
            trigs = trigs[-a.limit:] if a.limit else []
        for t in trigs:
            print("%s %s" % (_cite_token(t),
                             _clip_bytes(collapse_ctrl(t["headline"]),
                                         DIGEST_MAX_BYTES)))
        return

    recs = learning_records(load_store_tolerant(root),
                            include_superseded=getattr(a, "include_superseded", False),
                            include_proposed=getattr(a, "include_proposed", False))

    if a.since:
        since = _norm_since(a.since)
        if since is None:
            die("since-format", "--since must be a record ts (YYYY-MM-DDTHH:MM:SSZ), a "
                                "ledger stamp (YYYY-MM-DD HH:MMZ) or a date, got %r" % a.since)
        recs = [r for r in recs if (r.get("ts") or "") > since]

    if a.scope:
        recs = [r for r in recs if scope_matches(r, a.scope)]

    if a.limit is not None and a.limit >= 0:
        recs = recs[:a.limit]

    if a.json:
        print(json.dumps({"count": len(recs), "records": recs}, ensure_ascii=False, indent=1))
        return
    if a.digest:
        for r in recs:
            print(digest_line(r))
        return
    if not recs:
        print("no learnings banked yet")
        return
    print("%d learning(s), newest first" % len(recs))
    for r in recs:
        print("%s  %s  [%s]  scope: %s  source: %s"
              % (r.get("id"), r.get("ts"), r.get("tag"),
                 ", ".join(r.get("scope") or []), r.get("source", "?")))
        print("    %s" % collapse_ctrl(r.get("statement", "")))
        for item in (r.get("evidence") or []):
            print("    evidence: %s %s [%s]"
                  % (item.get("type"), item.get("ref"), item.get("label")))


def cmd_track(a):
    root = pathlib.Path(a.root).resolve()
    records = load_store(root)
    shown, eff = select(records, a)
    if a.json:
        payload = {"generated": now_z(), "root": str(root), "store": STORE,
                   "total": len(records), "shown": len(shown), "records": []}
        for r in shown:
            status, by = eff.get(r.get("id"), (r.get("status", "live"), None))
            item = dict(r)
            item["effective_status"] = status
            item["status_by"] = by
            # Always present, so a consumer can test truthiness instead of membership.
            # Non-empty only on an effectively-live record (see rests_on_refuted).
            item["rests_on_refuted"] = rests_on_refuted(r, eff)
            payload["records"].append(item)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not records:
        print("no findings store at %s — nothing recorded yet (write one: index.py add)"
              % (root / STORE))
        return
    live = sum(1 for r in records if eff.get(r.get("id"), ("live",))[0] == "live")
    print("# session track — %d record(s), %d live · %s" % (len(records), live, STORE))
    for r in shown:
        print(track_line(r, eff))
    if not shown:
        print("(no record matches the filters)")


def tombstone(a, target, statement, evidence, also=None):
    root = pathlib.Path(a.root).resolve()
    ids = {r.get("id") for r in load_store(root)}
    if target not in ids:
        die("links-unknown", "no record %s in %s" % (target, STORE))
    links = [target] + [x for x in (also or []) if x and x != target]
    # ⛔ A TOMBSTONE IS A DECISION, NOT A TEST (4.7). It was written as kind=result, and
    # the moment `result` came to mean "something RAN, here is the command and the exit
    # code", every supersede and refute would have had to invent a command it never ran —
    # or the TESTS box would have counted status flips as tests. `decision` is what a
    # supersede/refute has always actually been; resolution keys on the statement head and
    # `links`, never on the kind, so nothing about the flip changes.
    raw = {"ts": a.ts or now_z(), "session": a.session, "skill": a.skill or "archivist",
           "kind": "decision", "ask": a.ask, "statement": statement,
           "evidence": evidence, "relation": "back", "links": links, "status": "live"}
    notes = []
    try:
        rid = append_record(root, raw, lib=library_root(a), notes=notes)
    except Reject as r:
        die(r.rule, r.detail)
    print(rid)
    for n in notes:
        sys.stderr.write("note: %s\n" % n)


def cmd_supersede(a):
    target, by = a.id.upper(), a.by.upper()
    note = (" " + a.note.strip()) if a.note else ""
    stmt = "supersedes %s — replaced by %s.%s" % (target, by, note)
    ev = [{"type": "path", "ref": "%s#%s" % (STORE, by), "label": "cited"}]
    tombstone(a, target, stmt, ev, also=[by])


def cmd_refute(a):
    target = a.id.upper()
    ref = a.evidence.strip()
    etype = a.type or ("url" if URL_RE.match(ref) else "path")
    note = (" " + a.note.strip()) if a.note else ""
    stmt = "refutes %s — contradicted by %s.%s" % (target, ref, note)
    ev = [{"type": etype, "ref": ref, "label": a.label}]
    tombstone(a, target, stmt, ev)


def cmd_find(a):
    root = pathlib.Path(a.root).resolve()
    term = a.term.lower()
    hits = 0

    records = [r for r in load_store(root)
               if term in (r.get("statement", "") or "").lower()
               or term in (r.get("ask", "") or "").lower()]
    if records:
        eff = resolve(load_store(root))
        print("## findings — %d record(s) match %r" % (len(records), a.term))
        for r in sorted(records, key=sort_key):
            print(track_line(r, eff))
        print()
        hits += len(records)

    indexed = set()
    p = root / INDEX
    if p.exists():
        blocks = p.read_text(encoding="utf-8").split("\n### ")
        matched = [b for b in blocks[1:] if term in b.lower()]
        for b in matched:
            m = INDEX_PATH_RE.search(b)
            if m:
                indexed.add(m.group(1))
            print("### " + b.strip() + "\n")
        hits += len(matched)
    else:
        print("(no %s — index entries not searched; run: index.py scan)" % INDEX)

    # Body sweep: the index carries only each dossier's Read Me First head, so a
    # term buried in the body was invisible. Read the files the index points at.
    body = 0
    for d, path in dossier_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in indexed:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [l.strip() for l in text.splitlines() if term in l.lower()]
        if not lines:
            continue
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")),
                     path.stem)
        print("### %s — %s  [body match]" % (title, dossier_date(text, path)))
        print("folder: %s · path: %s" % (d, rel))
        for l in lines[:2]:
            print("  " + head(l, 160))
        print()
        body += 1
    hits += body

    if not hits:
        print("no findings, index entries, or dossier bodies match %r "
              "(index may be stale — re-scan)" % a.term)


# ---------------------------------------------------------------------------
# library commands — the shelf, read where each store lives
# ---------------------------------------------------------------------------
def project_state(entry):
    """(records|None, bad_lines, reachable) for one shelf entry. A root that is
    gone is `missing`; a root that is there without a store has zero records."""
    root = pathlib.Path(entry["root"]).expanduser()
    if not root.is_dir():
        return None, 0, False
    recs, bad = load_store_safe(root)
    return (recs if recs is not None else []), bad, True


def shelf_index(lib, project=None):
    """{name: {entry, recs, eff, up}} for every registered project, resolved once.
    An unreachable project is carried with up=False — reported, never dropped."""
    out = {}
    for p in read_registry(lib):
        if project and p["name"] != project:
            continue
        recs, _bad, up = project_state(p)
        recs = recs or []
        out[p["name"]] = {"entry": p, "recs": recs, "eff": resolve(recs), "up": up}
    return out


# ---------------------------------------------------------------------------
# storey one — CONCEPTS: what this estate keeps thinking about
# ---------------------------------------------------------------------------
def concept_members(shelf):
    """Every clusterable record on the shelf, in a deterministic order.

    Tombstones are excluded: `supersedes F-3 — replaced by F-9` is bookkeeping about
    the store, and clustering it would name a concept after the estate's own filing
    verbs. CROWNS are excluded for a sharper reason: a crown is a record ABOUT a
    concept, so letting it join would change the membership the moment it is written —
    every crowned concept would come back from the next rebuild as a new, uncrowned id.
    Refuted records ARE included — a concept has to be able to show the ground that
    moved, and `crown` needs to see it to refuse."""
    rows = []
    for name in sorted(shelf):
        s = shelf[name]
        if not s["up"]:
            continue
        for r in sorted(s["recs"], key=sort_key):
            stmt = r.get("statement", "") or ""
            if TOMB_RE.match(stmt) or CROWN_RE.match(stmt):
                continue
            rows.append((name, r, s["eff"].get(r.get("id"), ("live", None))[0]))
    return rows


def build_concepts(lib, sim, min_df, min_members, project=None):
    """Cluster the shelf with compile.py's machinery. Deterministic given identical
    stores: the input order is (project, id) and every donor step is order-stable."""
    C = donor("compile")
    rows = concept_members(shelf_index(lib, project))
    if not rows:
        return [], 0
    items = [C.Item("record", "%s:%s" % (name, r.get("id")), r.get("ts", ""),
                    "%s %s" % (r.get("statement", "") or "", r.get("ask", "") or ""))
             for name, r, _st in rows]
    df = C.procedure_vocab(items, min_df, C.BOILER)
    for it in items:
        it.sig = frozenset(t for t in it.toks if t in df)
    clusters = C.agglomerate([i.sig for i in items], df, sim)

    prior = {frozenset(c.get("members") or []): c for c in read_concepts(lib)}
    used = {int(CID_RE.match(c["id"]).group(1)) for c in read_concepts(lib)}
    nxt = (max(used) + 1) if used else 1
    out = []
    for members in sorted(clusters, key=lambda m: (-len(m), items[m[0]].ref)):
        if len(members) < min_members:
            continue
        n = len(members)
        counts = Counter()
        for i in members:
            counts.update(items[i].sig)
        core = {t for t, c in counts.items() if c >= C.CORE_SHARE * n}
        terms = [t for t in sorted(core or counts,
                                   key=lambda t: (-counts[t], -df.get(t, 0), t))
                 if t not in C.NOISE_SLUG and not t.startswith("<")][:6]
        pairs = [(i, j) for k, i in enumerate(members) for j in members[k + 1:]]
        cohesion = (sum(len(items[i].sig & items[j].sig) / len(items[i].sig | items[j].sig)
                        for i, j in pairs if items[i].sig | items[j].sig)
                    / len(pairs)) if pairs else 1.0
        refs = sorted((items[i].ref for i in members),
                      key=lambda r: (r.split(":")[0], int(r.split("F-")[1])))
        asks, seen = [], set()
        for i in sorted(members, key=lambda i: items[i].ref):
            ask = " ".join((rows[i][1].get("ask", "") or "").split())
            if ask and ask.lower() not in seen:
                seen.add(ask.lower())
                asks.append(ask)
        # A concept KEEPS its identity across rebuilds when its membership is
        # unchanged: the id, the name the seat gave it, its verdict and its birth
        # stamp all carry forward. A rebuild that renamed everything would make
        # `--name` a joke and every citation of C-3 a lie.
        old = prior.get(frozenset(refs))
        if old:
            cid, ts, nm = old["id"], old.get("ts", now_z()), old.get("name", "?")
            settled, status = old.get("settled"), old.get("status", "OPEN")
        else:
            cid, ts, nm, settled, status = "C-%d" % nxt, now_z(), "?", None, "OPEN"
            nxt += 1
        out.append({"id": cid, "terms": terms, "name": nm, "members": refs,
                    "projects": sorted({r.split(":")[0] for r in refs}),
                    "asks": asks, "cohesion": round(cohesion, 2),
                    "settled": settled, "status": status, "ts": ts})
    return out, len(items)


def concept_line(c):
    return ("%s · %s · %d member(s) across %d project(s) · cohesion %.2f · %s\n"
            "    terms: %s\n    members: %s%s"
            % (c["id"], c.get("name") or "?", len(c.get("members") or []),
               len(c.get("projects") or []), c.get("cohesion", 0.0),
               c.get("status", "OPEN"), ", ".join(c.get("terms") or []) or "-",
               ", ".join(c.get("members") or []),
               "\n    settled: %s" % c["settled"] if c.get("settled") else ""))


def cmd_library_concepts(a):
    lib = library_root(a)
    if a.name:
        cid, newname = a.name[0].upper(), a.name[1].strip()
        cur = {c["id"]: c for c in read_concepts(lib)}
        if cid not in cur:
            die("concept-unknown", "no %s on the shelf (%s) — known: %s"
                % (cid, concepts_file(lib), ", ".join(sorted(cur)) or "(none)"))
        if not newname:
            die("concept-name-empty", "a christening needs a name")
        row = dict(cur[cid])
        row["name"] = newname
        row["ts_named"] = now_z()
        append_concepts(lib, [row])
        print("%s named %r (appended to %s)" % (cid, newname, concepts_file(lib)))
        return

    if not a.rebuild:
        cs = read_concepts(lib)
        if not cs:
            print("no concepts yet (%s) — build them: index.py library concepts --rebuild"
                  % concepts_file(lib))
            return
        print("# concepts — %d · %s" % (len(cs), concepts_file(lib)))
        for c in cs:
            print(concept_line(c))
        return

    cs, n_items = build_concepts(lib, a.sim, a.min_df, a.min_members, a.project)
    if not cs:
        print("# concepts — 0 from %d clusterable record(s) (sim %.2f · min-df %d · "
              "min-members %d)" % (n_items, a.sim, a.min_df, a.min_members))
        print("nothing recurred across the shelf yet — that is an honest answer, not an "
              "error: a concept needs %d records that share vocabulary." % a.min_members)
        return
    if not a.dry_run:
        append_concepts(lib, cs)
    print("# concepts — %d from %d clusterable record(s) (sim %.2f · min-df %d) · %s%s"
          % (len(cs), n_items, a.sim, a.min_df, concepts_file(lib),
             "  [DRY RUN — nothing appended]" if a.dry_run else ""))
    for c in cs:
        print(concept_line(c))
    print("name them: index.py library concepts --name %s \"<what this is>\"" % cs[0]["id"])


def cmd_library_register(a):
    root = pathlib.Path(a.root).expanduser().resolve()
    if not root.is_dir():
        die("library-root-missing", "not a directory: %s" % root)
    name = (a.name or root.name).strip()
    if not NAME_RE.match(name):
        die("library-name-shape",
            "project name %r must match %s — it is half of every cross-project "
            "citation (<project>:F-<n>)" % (name, NAME_RE.pattern))

    lib = library_root(a)
    reg, pf = registry_file(lib), projects_file(lib)
    projects = read_registry(lib)
    by_root = {p["root"]: p for p in projects}
    by_name = {p["name"]: p for p in projects}

    existing = by_root.get(str(root))
    if existing:
        extra = ""
        if a.name and a.name.strip() != existing["name"]:
            extra = (" (--name %r not applied — re-registration is a no-op; the "
                     "registry is append-only)" % a.name.strip())
        print("registry %s: already registered as %r — no-op, %d project(s)%s"
              % (reg, existing["name"], len(projects), extra))
    else:
        clash = by_name.get(name)
        if clash:
            die("library-name-taken",
                "%r already names %s — pass --name to register %s under another name"
                % (name, clash["root"], root))
        reg.parent.mkdir(parents=True, exist_ok=True)
        with open(reg, "a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(json.dumps({"root": str(root), "name": name, "ts": now_z()},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        print("registry %s: registered %s -> %s (%d project(s))"
              % (reg, name, root, len(projects) + 1))

    # ONE registration, TWO consumers: graph.py's `all` mode reads this file.
    roots = read_projects(pf)
    if str(root) in roots:
        print("projects %s: already present (%d root(s))" % (pf, len(roots)))
    else:
        pf.parent.mkdir(parents=True, exist_ok=True)
        with open(pf, "a", encoding="utf-8") as fh:
            fh.write(str(root) + "\n")
        print("projects %s: added %s (%d root(s))" % (pf, root, len(roots) + 1))


def cmd_library_list(a):
    lib = library_root(a)
    projects = read_registry(lib)
    if not projects:
        print("no projects on the shelf (%s) — register one: index.py library register --root ."
              % registry_file(lib))
        return
    print("# library — %d project(s) · %s" % (len(projects), registry_file(lib)))
    for p in projects:
        recs, bad, up = project_state(p)
        if not up:
            print("%s · %s · records — · missing" % (p["name"], p["root"]))
            continue
        eff = resolve(recs)
        live = sum(1 for r in recs if eff.get(r.get("id"), ("live",))[0] == "live")
        tail = " · %d unreadable line(s)" % bad if bad else ""
        print("%s · %s · records %d (%d live) · reachable%s"
              % (p["name"], p["root"], len(recs), live, tail))


def library_line(name, rec, eff):
    """The shelf's citation line: <project>:F-<n> · kind · statement-head · [labels].
    A non-live record says so — a citation grammar that let a refuted record travel
    between projects would launder exactly the thing the store exists to catch."""
    status, by = eff.get(rec.get("id"), (rec.get("status", "live"), None))
    tail = "" if status == "live" else " · %s by %s" % (status.upper(), by or "?")
    return "%s:%s · %s · %s · [%s]%s" % (
        name, rec.get("id", "F-?"), rec.get("kind", "?"),
        head(rec.get("statement", "")), labels_of(rec), tail)


def cmd_library_find(a):
    lib = library_root(a)
    projects = read_registry(lib)
    terms = [t.lower() for t in a.terms if t.strip()]
    if not projects:
        msg = ("no projects on the shelf (%s) — register one: "
               "index.py library register --root ." % registry_file(lib))
        print(json.dumps({"generated": now_z(), "registry": str(registry_file(lib)),
                          "terms": a.terms, "projects": [], "hits": [],
                          "index_hits": [], "unreachable": [], "total": 0,
                          "note": msg}, ensure_ascii=False, indent=2)
              if a.json else msg)
        return
    only = None
    if getattr(a, "concept", None):
        cid = a.concept.upper()
        c = next((x for x in read_concepts(lib) if x["id"] == cid), None)
        if c is None:
            die("concept-unknown", "no %s on the shelf (%s)" % (cid, concepts_file(lib)))
        only = set(c.get("members") or [])
    if not terms and only is None:
        die("no-input", "library find needs at least one term (or --concept C-<n>)")

    if not a.json:
        what = " ".join([repr(t) for t in a.terms]
                        + (["--concept %s" % a.concept.upper()] if only is not None else []))
        print("# library find %s — %d project(s) · %s"
              % (what, len(projects), registry_file(lib)))
    hits, hit_projects, down = 0, 0, []
    # --json is the machine surface: ask and statement travel WHOLE (the line
    # format's 90-char head is a reading convenience, never the record).
    out_hits, idx_hits, seen_projects = [], [], []
    for p in projects:
        recs, _bad, up = project_state(p)
        if not up:
            down.append(p)
            continue
        found = 0
        eff = resolve(recs)
        for r in sorted(recs, key=sort_key):
            if a.kind and r.get("kind") != a.kind:
                continue
            if only is not None and "%s:%s" % (p["name"], r.get("id")) not in only:
                continue
            hay = ("%s %s" % (r.get("statement", "") or "", r.get("ask", "") or "")).lower()
            if not all(t in hay for t in terms):
                continue
            status, by = eff.get(r.get("id"), (r.get("status", "live"), None))
            item = dict(r)
            item.update({"project": p["name"], "root": p["root"],
                         "ref": "%s:%s" % (p["name"], r.get("id")),
                         "effective_status": status, "status_by": by,
                         "rests_on_refuted": rests_on_refuted(r, eff)})
            out_hits.append(item)
            if not a.json:
                print(library_line(p["name"], r, eff))
            found += 1
        # The legacy estate is on the shelf too: index HEADS only, never bodies —
        # the library reads across repos, so it stays cheap by construction.
        idx = pathlib.Path(p["root"]).expanduser() / INDEX
        try:
            # A concept's members are RECORDS; the legacy heads are not on that shelf,
            # and with no terms to match they would otherwise all "match" vacuously.
            text = "" if only is not None else (
                idx.read_text(encoding="utf-8", errors="replace") if idx.is_file() else "")
        except OSError:
            text = ""
        for block in text.split("\n### ")[1:]:
            if not all(t in block.lower() for t in terms):
                continue
            m = INDEX_PATH_RE.search(block)
            entry = {"project": p["name"], "heading": block.splitlines()[0].strip(),
                     "path": m.group(1) if m else ""}
            idx_hits.append(entry)
            if not a.json:
                print("%s:index · %s%s"
                      % (p["name"], head(entry["heading"], 90),
                         " · " + entry["path"] if entry["path"] else ""))
            found += 1
        hits += found
        hit_projects += 1 if found else 0
        seen_projects.append({"name": p["name"], "root": p["root"],
                              "reachable": True, "records": len(recs), "hits": found})
    if a.json:
        print(json.dumps(
            {"generated": now_z(), "registry": str(registry_file(lib)),
             "terms": a.terms, "kind": a.kind,
             "projects": seen_projects + [{"name": p["name"], "root": p["root"],
                                           "reachable": False, "records": 0, "hits": 0}
                                          for p in down],
             "unreachable": [{"name": p["name"], "root": p["root"]} for p in down],
             "hits": out_hits, "index_hits": idx_hits, "total": hits},
            ensure_ascii=False, indent=2))
        return
    for p in down:
        print("(unreachable: %s · %s — never fatal; the repo may be on another machine)"
              % (p["name"], p["root"]))
    print("%d hit(s) in %d of %d project(s)%s"
          % (hits, hit_projects, len(projects),
             " · %d unreachable" % len(down) if down else ""))


def cmd_library_track(a):
    lib = library_root(a)
    projects = read_registry(lib)
    entry = next((p for p in projects if p["name"] == a.project), None)
    if entry is None:
        die("library-unknown-project",
            "%r is not on the shelf (%s) — registered: %s"
            % (a.project, registry_file(lib),
               ", ".join(p["name"] for p in projects) or "(none)"))
    root = pathlib.Path(entry["root"]).expanduser()
    if not root.is_dir():
        die("library-unreachable",
            "%s is registered at %s — that root is not reachable from here"
            % (a.project, entry["root"]))
    recs, bad = load_store_safe(root)
    if recs is None:
        recs, bad = [], 0
    # Remote read: the store is loaded from where it lives, nothing is copied here.
    shown, eff = select(recs, a)
    live = sum(1 for r in recs if eff.get(r.get("id"), ("live",))[0] == "live")
    print("# track — %s · %s · %d record(s), %d live%s"
          % (entry["name"], root / STORE, len(recs), live,
             " · %d unreadable line(s)" % bad if bad else ""))
    for r in shown:
        print(track_line(r, eff))
    if not shown:
        print("(no record matches the filters)")


# ---------------------------------------------------------------------------
# storey two — THE UPDATER: does the ground still hold?
# ---------------------------------------------------------------------------
def load_update_cache(lib):
    try:
        return json.loads((lib / UPDATE_CACHE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_update_cache(lib, cache):
    try:
        (lib / UPDATE_CACHE).parent.mkdir(parents=True, exist_ok=True)
        (lib / UPDATE_CACHE).write_text(json.dumps(cache, indent=1, sort_keys=True),
                                        encoding="utf-8")
    except OSError:                                              # pragma: no cover
        pass


def is_due(val, max_age):
    """Never probed, or probed longer ago than the window."""
    at = str(val.get("at") or "")
    if not at:
        return True
    try:
        when = datetime.strptime(at[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - when >= timedelta(days=max_age)


def probe(W, url, val, timeout):
    """One conditional GET → (verdict, digest, note, validators).

    The probe itself is watch.py's `fetch` — imported, not re-typed. THE ONE RULE
    RESTATED HERE (watch.py's cmd_probe embeds it in a CLI path this cannot call):
    condition on a STRONG ETag only. `If-Modified-Since` is never sent — HTTP dates
    have one-second granularity, so a page edited inside the same second as the last
    check answers 304 while its bytes moved, and the watch reports UNCHANGED over
    real drift. A weak `W/"…"` ETag promises only semantic equivalence and is refused
    for the same reason."""
    cond = {}
    etag = str(val.get("etag") or "")
    if etag and not etag.startswith("W/"):
        cond["If-None-Match"] = etag
    status, head, body, err = W.fetch(url, "GET", timeout, cond)
    stored = str(val.get("sha256") or "")
    if status is None or status >= 400:
        # A source that cannot be read is a fact about the SOURCE, never a
        # refutation of the claim that cited it.
        return "DEAD-SOURCE", "", (err or "HTTP %s" % status), {}
    if status == 304:
        return "STANDS", stored, "304 Not Modified (strong-ETag conditional GET)", {}
    digest = hashlib.sha256(body).hexdigest()[:16]
    val_new = {"etag": head.get("ETag", ""), "last-modified": head.get("Last-Modified", ""),
               "sha256": digest, "url": url, "at": now_z()[:10]}
    if not stored:
        return "BASELINE", digest, "first sight — baseline recorded, nothing judged", val_new
    if stored == digest:
        return "STANDS", digest, "", val_new
    # DRIFT IS NOT BANKED. The baseline hash and the old validators are deliberately
    # left in place: advancing them here would make the NEXT run report STANDS and
    # retire the drift before any model ever read what changed.
    return "DRIFTED", digest, "stored %s → now %s" % (stored, digest), {}


def cites_refuted(shelf, targets=None):
    """THE CROSS-PROJECT RESTS-ON-REFUTED WALK. A live record whose `record` evidence
    cites a record that is effectively REFUTED — here or in another project on the
    shelf — is standing on ground the estate has already knocked out, and no single
    store can see it. One hop, reachable projects only, never fatal: an offline
    project is reported as unchecked, never as clean.

    `shelf` supplies the SOURCE records; `targets` resolves the refs they cite. They
    differ under `--project`: narrowing which records are probed must never narrow the
    shelf a citation is resolved against, or filtering would manufacture clean runs."""
    targets = targets if targets is not None else shelf
    out, unchecked = [], []
    for name in sorted(shelf):
        s = shelf[name]
        if not s["up"]:
            continue
        for r in sorted(s["recs"], key=sort_key):
            fid = r.get("id")
            if s["eff"].get(fid, ("live", None))[0] != "live":
                continue
            for e in r.get("evidence") or []:
                if e.get("type") != "record":
                    continue
                m = REC_REF_RE.match(str(e.get("ref", "")).strip())
                if not m:
                    continue
                tproj, tid = (m.group(1) or name), "%s-%s" % (m.group(2), m.group(3))
                t = targets.get(tproj)
                if t is None or not t["up"]:
                    unchecked.append(("%s:%s" % (name, fid), "%s:%s" % (tproj, tid)))
                    continue
                st, by = t["eff"].get(tid, (None, None))
                if st == "refuted":
                    # The tombstone is named project-qualified too: a bare F-3 read from
                    # another project's line is an id in the wrong namespace.
                    out.append(("%s:%s" % (name, fid), "%s:%s" % (tproj, tid),
                                "%s:%s" % (tproj, by) if by else "?"))
    return out, unchecked


def cmd_library_update(a):
    lib = library_root(a)
    shelf = shelf_index(lib, a.project)
    if not shelf:
        die("library-unknown-project" if a.project else "library-empty",
            "%s on the shelf (%s)"
            % ("no project named %r" % a.project if a.project else "no projects",
               registry_file(lib)))
    W = donor("watch")
    cache = load_update_cache(lib)
    mode = "--all" if a.all else "--due"
    counts = Counter()
    rows, skipped = [], 0

    for name in sorted(shelf):
        s = shelf[name]
        if not s["up"]:
            continue
        for r in sorted(s["recs"], key=sort_key):
            fid, ref = r.get("id"), "%s:%s" % (name, r.get("id"))
            if s["eff"].get(fid, ("live", None))[0] != "live":
                continue
            if TOMB_RE.match(r.get("statement", "") or ""):
                continue
            ev = r.get("evidence") or []
            urls = [str(e.get("ref", "")).strip() for e in ev
                    if e.get("type") == "url" and str(e.get("ref", "")).strip()]
            others = sorted({str(e.get("type")) for e in ev if e.get("type") != "url"})
            if not urls:
                if others:
                    # A command or a path can only be re-checked by a session that
                    # runs it. The library NEVER executes evidence — it lists it.
                    counts["NEEDS-SESSION-RECHECK"] += 1
                    rows.append(("NEEDS-SESSION-RECHECK", ref, "",
                                 "evidence: %s — never auto-executed" % ",".join(others),
                                 head(r.get("statement", ""), 70)))
                continue
            url = urls[0]
            key = "%s|%s" % (ref, url)
            val = cache.get(key, {})
            if not a.all and not is_due(val, a.max_age):
                skipped += 1
                continue
            verdict, digest, note, fresh = probe(W, url, val, a.timeout)
            counts[verdict] += 1
            if fresh:
                cache[key] = fresh
            elif verdict == "DRIFTED":
                cur = dict(val)
                cur["drift"] = {"sha256": digest, "at": now_z()[:10]}
                cache[key] = cur
            rows.append((verdict, ref, url, note, head(r.get("statement", ""), 70)))

    refuted, unchecked = cites_refuted(shelf, shelf_index(lib) if a.project else shelf)
    for src, tgt, by in refuted:
        counts["CITES-REFUTED"] += 1
        rows.append(("CITES-REFUTED", src, "", "cites %s — refuted by %s" % (tgt, by), ""))
    save_update_cache(lib, cache)

    up = sorted(n for n in shelf if shelf[n]["up"])
    down = sorted(n for n in shelf if not shelf[n]["up"])
    order = {v: i for i, v in enumerate(
        ("DRIFTED", "DEAD-SOURCE", "CITES-REFUTED", "BASELINE", "STANDS",
         "NEEDS-SESSION-RECHECK"))}
    rows.sort(key=lambda t: (order.get(t[0], 9), t[1]))

    when = now_z()[:10]
    block = ["## %s — library update (%s)" % (when, mode),
             "**Shelf:** %s · %d project(s), %d reachable%s"
             % (registry_file(lib), len(shelf), len(up),
                " (unreachable: %s)" % ", ".join(down) if down else ""),
             "**Result:** %s%s"
             % (" · ".join("%d %s" % (counts.get(v, 0), v) for v in
                           ("STANDS", "DRIFTED", "DEAD-SOURCE", "BASELINE",
                            "NEEDS-SESSION-RECHECK", "CITES-REFUTED")),
                " · %d not due" % skipped if skipped else "")]
    for verdict, ref, url, note, stmt in rows:
        block.append("- %-22s %s%s%s%s"
                     % (verdict, ref, "  " + url if url else "",
                        "  (%s)" % note if note else "",
                        '  "%s"' % stmt if stmt else ""))
    if not rows:
        block.append("- (nothing due and nothing to list)")
    block.append("")
    p = lib / UPDATE_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            if p.stat().st_size == 0:
                fh.write("# library update log — append-only; each run adds one dated "
                         "block. Written by index.py; never hand-edit.\n\n")
            fh.write("\n".join(block) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    # The summary line: one row a heartbeat could carry, zero model tokens.
    print("library update: %s%s · %d/%d project(s) reachable · log %s"
          % (" · ".join("%d %s" % (counts.get(v, 0), v) for v in
                        ("STANDS", "DRIFTED", "DEAD-SOURCE", "BASELINE",
                         "NEEDS-SESSION-RECHECK", "CITES-REFUTED")),
             " · %d not due" % skipped if skipped else "",
             len(up), len(shelf), p))
    for verdict, ref, url, note, _s in rows:
        if verdict in ("DRIFTED", "DEAD-SOURCE", "CITES-REFUTED"):
            print("  %-14s %s%s%s" % (verdict, ref, "  " + url if url else "",
                                      "  (%s)" % note if note else ""))
    if unchecked:
        print("  note: %d record-evidence ref(s) point at unreachable projects — "
              "unchecked, not clean (%s)"
              % (len(unchecked), ", ".join("%s→%s" % u for u in unchecked[:3])))


# ---------------------------------------------------------------------------
# storey three — CONVERGENCE: the model decides, the script records
# ---------------------------------------------------------------------------
def cmd_library_crown(a):
    """`crown` does not judge convergence. A model reads the members, decides they
    say one settled thing, and writes that sentence; this records the decision as a
    citable record and marks the concept. The guards below are the only judgment the
    script makes, and they are refusals, never approvals."""
    lib = library_root(a)
    cid = a.concept.upper()
    concepts = {c["id"]: c for c in read_concepts(lib)}
    if cid not in concepts:
        die("concept-unknown", "no %s on the shelf (%s) — known: %s"
            % (cid, concepts_file(lib), ", ".join(sorted(concepts)) or "(none)"))
    concept = concepts[cid]
    members = concept.get("members") or []

    root = pathlib.Path(a.root).expanduser().resolve()
    local = next((p for p in read_registry(lib) if p["root"] == str(root)), None)
    if local is None:
        die("crown-unregistered",
            "%s is not on the shelf, so a crown written here could never be cited as "
            "<project>:F-<n> — register it first: index.py library register --root ." % root)

    by = [x.strip() for x in a.by.split(",") if x.strip()]
    for ref in by:
        if ref not in members:
            die("crown-by-not-member", "%s is not a member of %s (members: %s)"
                % (ref, cid, ", ".join(members)))
    shelf = shelf_index(lib)

    # An ASSERTION may not be made over ground that cannot be read. `find` degrades on
    # an unreachable project because reading is not claiming; crowning is claiming.
    for ref in by:
        proj = ref.split(":")[0]
        if proj not in shelf or not shelf[proj]["up"]:
            die("crown-unreachable",
                "%s names %s, which is not reachable from here — a convergence cannot be "
                "certified over a store this machine cannot read" % (ref, proj))

    refuted, contested = [], []
    for ref in by:
        proj, fid = ref.split(":")[0], ref.split(":")[1]
        s = shelf[proj]
        rec = next((r for r in s["recs"] if r.get("id") == fid), None)
        if rec is None:
            die("crown-by-not-member", "%s: that project's store holds no %s" % (ref, fid))
        st = s["eff"].get(fid, ("live", None))[0]
        if st == "refuted":
            refuted.append("%s (%s)" % (ref, st))
        elif rec.get("kind") == "conflict":
            contested.append("%s is kind=conflict" % ref)
        elif rests_on_refuted(rec, s["eff"]):
            contested.append("%s RESTS-ON-REFUTED %s"
                             % (ref, ",".join(rests_on_refuted(rec, s["eff"]))))
    if refuted:
        die("crown-member-refuted",
            "%s rests on refuted ground: %s — the estate already knocked that out; "
            "supersede or drop it before crowning" % (cid, "; ".join(refuted)))
    if contested and not a.contested:
        die("crown-contested",
            "%s's live members disagree: %s — re-run with --contested to mark the concept "
            "CONTESTED, or resolve it first" % (cid, "; ".join(contested)))

    stale = [m for m in members if m not in by
             and m.split(":")[0] in shelf and shelf[m.split(":")[0]]["up"]
             and shelf[m.split(":")[0]]["eff"].get(m.split(":")[1], ("live",))[0] == "refuted"]

    if a.contested and contested:
        row = dict(concept)
        row.update({"status": "CONTESTED", "settled": None, "contested_by": contested,
                    "ts_crowned": now_z()})
        append_concepts(lib, [row])
        print("%s marked CONTESTED (%s) — no crown record written; a contested concept "
              "has nothing settled to cite." % (cid, "; ".join(contested)))
        return

    local_ids = [m.split(":")[1] for m in by if m.split(":")[0] == local["name"]]
    ev = [{"type": "record", "label": "cited",
           "ref": m.split(":")[1] if m.split(":")[0] == local["name"] else m} for m in by]
    # A crown records "a convergence the MODEL decided" — a decision by its own definition,
    # and never a command that ran. Same reasoning as the tombstone above.
    raw = {"ts": now_z(), "session": a.session, "skill": "archivist", "kind": "decision",
           "ask": "concept %s: %s" % (cid, concept.get("name") or ", ".join(concept.get("terms") or [])),
           "statement": "CONVERGED: %s" % a.statement.strip(),
           "evidence": ev, "relation": "toward", "links": local_ids, "status": "live"}
    notes = []
    try:
        rid = append_record(root, raw, lib=lib, notes=notes)
    except Reject as r:
        die(r.rule, r.detail)

    row = dict(concept)
    row.update({"status": "CONVERGED", "settled": a.statement.strip(),
                "crown": "%s:%s" % (local["name"], rid), "crowned_by": by,
                "ts_crowned": now_z()})
    append_concepts(lib, [row])
    print(rid)
    print("%s CONVERGED — crown %s:%s written to %s, %d member(s) cited"
          % (cid, local["name"], rid, root / STORE, len(by)))
    for n in notes:
        sys.stderr.write("note: %s\n" % n)
    if stale:
        print("note: %d concept member(s) are refuted and were NOT cited: %s"
              % (len(stale), ", ".join(stale)))


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="archivist — findings store + dossier index")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="rebuild oracle-index.md (legacy dossier estate)")
    s.add_argument("--root", default=".")
    s.set_defaults(f=cmd_scan)

    f = sub.add_parser("find", help="search findings, index entries, dossier bodies")
    f.add_argument("term")
    f.add_argument("--root", default=".")
    f.set_defaults(f=cmd_find)

    ad = sub.add_parser("add", help="append one validated finding record")
    ad.add_argument("--json", help="the record as JSON; omit to read stdin")
    ad.add_argument("--root", default=".")
    ad.add_argument("--library-root", default="",
                    help="the shelf (default $%s or ~/.claude/notrest-library)" % LIB_ENV)
    ad.add_argument("--strict-refs", action="store_true",
                    help="promote the unqualified-record-ref WARN to a rejection (exit 2)")
    # The per-field form the Stop gate's block reason instructs a model to run. Same
    # validate(), same rules, same exit codes — only the typing is easier.
    ad.add_argument("--kind", choices=KINDS, help="per-field form: the record kind")
    ad.add_argument("--tag", choices=LEARN_TAGS, help="per-field form: a learning's tag")
    ad.add_argument("--statement", help="per-field form: the lesson, <=%d chars"
                                        % STATEMENT_MAX)
    ad.add_argument("--evidence", action="append", metavar="REF",
                    help="per-field form, repeatable: a COORD stamp '[YYYY-MM-DD HH:MMZ]', "
                         "a briefs/ path, a commit hash, or a record id")
    ad.add_argument("--scope", action="append", metavar="TOKEN",
                    help="per-field form, repeatable: a path glob, a skill name, or 'estate'")
    # kind=open
    ad.add_argument("--closes-when", dest="closes_when",
                    help="kind=open: the runnable check that would CLOSE this question")
    ad.add_argument("--owner", help="kind=open: who can close it ('seat' or a lane id)")
    ad.add_argument("--recheck", help="kind=open: re-check date, YYYY-MM-DD")
    # kind=alternative
    ad.add_argument("--method", help="kind=alternative: the path not taken")
    ad.add_argument("--when-to-try", dest="when_to_try",
                    help="kind=alternative: when it would be worth trying")
    ad.add_argument("--cost", help="kind=alternative: what it would cost")
    # kind=result
    ad.add_argument("--ran", help="kind=result: what was run")
    ad.add_argument("--command", help="kind=result: the exact command, so it can be re-run")
    ad.add_argument("--exit", dest="exit", type=int,
                    help="kind=result: the integer exit code")
    ad.add_argument("--source", default="seat",
                    help="per-field form: 'seat' or a lane id (default: seat)")
    ad.add_argument("--session", default="", help="per-field form: the session id")
    ad.add_argument("--skill", default="", help="per-field form: the skill that found it")
    ad.add_argument("--ask", default="", help="per-field form: what was asked")
    ad.set_defaults(f=cmd_add)

    lb = sub.add_parser("library", help="the cross-project shelf: register, list, find, track")
    lbs = lb.add_subparsers(dest="libcmd", required=True)

    def shelf(p):
        p.add_argument("--library-root", default="",
                       help="the shelf (default $%s or ~/.claude/notrest-library)" % LIB_ENV)
        return p

    lr = shelf(lbs.add_parser("register", help="put a project on the shelf (idempotent)"))
    lr.add_argument("--root", default=".")
    lr.add_argument("--name", default="", help="shelf name (default: the repo's dirname)")
    lr.set_defaults(f=cmd_library_register)

    shelf(lbs.add_parser("list", help="every registered project: records, reachable or missing")
          ).set_defaults(f=cmd_library_list)

    lf = shelf(lbs.add_parser("find", help="search every registered project's store"))
    lf.add_argument("terms", nargs="*", help="all terms must appear (statement + ask)")
    lf.add_argument("--kind", choices=KINDS)
    lf.add_argument("--concept", help="restrict to one concept's members (C-<n>)")
    lf.add_argument("--json", action="store_true",
                    help="machine surface: whole ask + statement, never the 90-char head")
    lf.set_defaults(f=cmd_library_find)

    lt = shelf(lbs.add_parser("track", help="another project's track, read where it lives"))
    lt.add_argument("--project", required=True)
    lt.add_argument("--session")
    lt.add_argument("--kind", choices=KINDS)
    lt.add_argument("--status", choices=STATUSES)
    lt.set_defaults(f=cmd_library_track)

    lc = shelf(lbs.add_parser("concepts", help="what the estate keeps thinking about"))
    lc.add_argument("--rebuild", action="store_true", help="recluster and append a generation")
    lc.add_argument("--dry-run", action="store_true",
                    help="show the clustering without appending it — sweep --sim/--min-df "
                         "freely; the shelf is append-only, so an experiment would stick")
    lc.add_argument("--name", nargs=2, metavar=("C-<n>", "NAME"), help="christen a concept")
    lc.add_argument("--project", help="cluster one project only")
    lc.add_argument("--sim", type=float, default=SIM_DEFAULT)
    lc.add_argument("--min-df", type=int, default=MIN_DF_DEFAULT)
    lc.add_argument("--min-members", type=int, default=MIN_MEMBERS)
    lc.set_defaults(f=cmd_library_concepts)

    lu = shelf(lbs.add_parser("update", help="re-probe url evidence across the shelf"))
    lu.add_argument("--due", action="store_true", help="only urls past the age window (default)")
    lu.add_argument("--all", action="store_true", help="every url, due or not")
    lu.add_argument("--project")
    lu.add_argument("--max-age", type=int, default=MAX_AGE_DAYS)
    lu.add_argument("--timeout", type=int, default=10)
    lu.set_defaults(f=cmd_library_update)

    lk = shelf(lbs.add_parser("crown", help="record a convergence the MODEL decided"))
    lk.add_argument("concept", help="C-<n>")
    lk.add_argument("--statement", required=True, help="the settled sentence")
    lk.add_argument("--by", required=True, help="<project>:F-<n>[,…] the crown rests on")
    lk.add_argument("--contested", action="store_true",
                    help="members disagree: mark CONTESTED instead of crowning")
    lk.add_argument("--session", default="")
    lk.add_argument("--root", default=".", help="the LOCAL store the crown lands in")
    lk.set_defaults(f=cmd_library_crown)

    ln = sub.add_parser("learnings", help="the banked lessons: digest, scope, since")
    ln.add_argument("--root", default=".")
    ln.add_argument("--digest", action="store_true",
                    help="framed '| ' lines, <=%d bytes each, newest first — the shared "
                         "format the packet, spawn-gate and router all render"
                         % DIGEST_MAX_BYTES)
    ln.add_argument("--scope", nargs="+", default=[], metavar="TOKEN",
                    help="only records whose scope matches a token (or is 'estate')")
    ln.add_argument("--limit", type=int, default=None, metavar="N",
                    help="at most N records, newest first")
    ln.add_argument("--since", default="", metavar="TS",
                    help="records newer than a record ts, a ledger stamp or a date")
    ln.add_argument("--json", action="store_true", help="machine output")
    ln.add_argument("--trigger-regex", dest="trigger_regex", action="store_true",
                    help="print the ONE trigger regex eval and the Stop hook both read")
    ln.add_argument("--triggers", action="store_true",
                    help="list COORD lines where the estate PAID for a lesson (ts + "
                         "headline); the ONE implementation both eval and the Stop hook "
                         "call. A HEADLINE is the text before the first '->' or the first "
                         "120 characters, WHICHEVER IS SHORTER — a tag beyond that bound "
                         "is a mention, not a claim, and a line with no arrow does not "
                         "become one enormous headline. Bounded by the loop's FLOOR "
                         "(the earliest evidence stamp "
                         "any learning cites): older lines are grandfathered and never "
                         "returned, and with no learning at all the loop is UNARMED and "
                         "nothing is owed. --json prints the contract: "
                         "{\"armed\": bool, \"floor\": \"<ts>|null\", \"regex\": \"...\", "
                         "\"uncited\": [{\"ts\": \"[YYYY-MM-DD HH:MMZ]\", \"headline\": "
                         "\"...\"}], \"cited\": <n>} — uncited[].ts is BRACKETED because it "
                         "is pasted straight into `add --evidence`")
    ln.add_argument("--include-proposed", dest="include_proposed", action="store_true",
                    help="also show records a LANE proposed and the seat has not reviewed "
                         "(never quoted to lanes or the packet until `accept`)")
    ln.add_argument("--include-superseded", dest="include_superseded",
                    action="store_true",
                    help="also show learnings a later record superseded or refuted "
                         "(they are excluded from every digest and injection by default)")
    ln.add_argument("--library", action="store_true",
                    help="read the machine-wide SHELF's promoted lessons instead of this "
                         "estate's store")
    ln.add_argument("--library-root", default="",
                    help="the shelf (default $%s or ~/.claude/notrest-library)" % LIB_ENV)
    ln.add_argument("--uncited", action="store_true",
                    help="with --triggers: only those no learning record cites")
    ln.set_defaults(f=cmd_learnings)

    for _v, _h in (("accept", "the seat ACCEPTS a lane's proposed record — it becomes "
                              "quotable to other lanes and to the packet"),
                   ("reject", "the seat REJECTS a lane's proposed record, with a reason")):
        rv = sub.add_parser(_v, help=_h)
        rv.add_argument("record", metavar="L-n|O-n|A-n", help="the proposed record")
        rv.add_argument("--root", default=".")
        rv.add_argument("--session", default="")
        rv.add_argument("--why", default="",
                        help="reject: why it was turned down (required)")
        rv.add_argument("--library-root", default="")
        rv.set_defaults(f=cmd_review, accepting=(_v == "accept"))

    pr = sub.add_parser("promote", help="copy a `library`-scoped learning onto the shelf")
    pr.add_argument("record", metavar="L-n", help="the learning to promote")
    pr.add_argument("--root", default=".")
    pr.add_argument("--project", default="", help="origin name (default: the root's name)")
    pr.add_argument("--library-root", default="",
                    help="the shelf (default $%s or ~/.claude/notrest-library)" % LIB_ENV)
    pr.set_defaults(f=cmd_promote)

    cd = sub.add_parser(
        "card", help="the four-box card: TESTS / OPEN / FINDINGS / LEARNINGS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "THE CARD GRAMMAR (rendered here, parsed by the agent-ledger hook — one\n"
            "grammar, two directions, so a lane cannot write a block the estate cannot read):\n"
            "  TESTS (n)\n"
            "  - [x] <statement> — ran: <ran> · command: `<cmd>` · exit: <n>\n"
            "  OPEN (n)\n"
            "  - [ ] <statement> — closes when: <what> · owner: <who> · recheck: <YYYY-MM-DD>\n"
            "  FINDINGS (n)\n"
            "  - [x] <statement> — evidence: <ref>\n"
            "  LEARNINGS (n)\n"
            "  - [x] [TAG] <statement> — evidence: <ref>\n"
            "\n"
            "THE KIND COMES FROM THE BOX, NEVER THE CHECKBOX. `[ ]` means still open and\n"
            "only OPEN uses it; a parser keyed on the checkbox banks a half-finished TEST\n"
            "as an open question.\n"
            "\n"
            "TWO RULINGS THE TEMPLATE AND THE PARSER BOTH OBEY:\n"
            "  1. `exit` is typed as an INT by parse_card when it is numeric, so a parsed\n"
            "     TESTS box banks through `add` without any caller coercing it. A\n"
            "     non-numeric exit is left as written and `add` refuses it (exit-required).\n"
            "  2. `ran` AND `command` are BOTH required on a result, and neither aliases\n"
            "     the other: a test whose exact command is missing cannot be rerun, and a\n"
            "     command with no account of what it exercised cannot be read."))
    cd.add_argument("--root", default=".")
    cd.add_argument("--scope", nargs="+", default=[], metavar="TOKEN",
                    help="filter the scoped kinds (open, alternative, learning) by scope")
    cd.add_argument("--limit", type=int, default=None, metavar="N",
                    help="at most N lines per box, newest first")
    cd.add_argument("--json", action="store_true",
                    help="machine output: {\"counts\": {BOX: n}, \"boxes\": {BOX: [records]}}")
    cd.set_defaults(f=cmd_card)

    t = sub.add_parser("track", help="print the session track")
    t.add_argument("--session")
    t.add_argument("--kind", choices=KINDS)
    t.add_argument("--status", choices=STATUSES)
    t.add_argument("--json", action="store_true")
    t.add_argument("--root", default=".")
    t.set_defaults(f=cmd_track)

    for name, fn in (("supersede", cmd_supersede), ("refute", cmd_refute)):
        c = sub.add_parser(name, help="append a %s tombstone (append-only status flip)" % name)
        c.add_argument("id")
        c.add_argument("--session", default="")
        c.add_argument("--skill", default="")
        c.add_argument("--ask", default="")
        c.add_argument("--ts", default="")
        c.add_argument("--note", default="")
        c.add_argument("--root", default=".")
        if name == "supersede":
            c.add_argument("--by", required=True, help="the record that replaces it")
        else:
            c.add_argument("--evidence", required=True, help="the contradicting ref")
            c.add_argument("--type", choices=EV_TYPES, default="")
            c.add_argument("--label", choices=EV_LABELS, default="cited")
        c.set_defaults(f=fn)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
