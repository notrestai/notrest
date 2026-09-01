#!/bin/bash
# notrest SubagentStop hook — auto-index every completed agent.
# The harness already writes each subagent's full transcript to disk; this hook
# adds the zero-model-token index layer: one machine-written line per agent into
# COORD-AGENTS.md at the git root, so the repo carries the session's decision
# pattern (which agents were consulted, what each concluded, where the full
# transcript lives). COORD.md is the human ledger; this is its agent estate.
#
# Absolutely silent on success AND on every failure: no stdout, no stderr, always
# exit 0 — a broken hook must never break a session. The whole body is wrapped so
# any error still exits 0.

# ── capture the payload off stdin, then decide the estate root early (no stdin
# needed for the root).
PAYLOAD="$(cat 2>/dev/null || true)"

# ── estate root: ONE resolver, shared by every estate hook (hooks/estate-root.sh).
# git root, else the nearest COORD.md walking up at most 3 levels — stopping at any
# directory carrying its OWN project marker (a project boundary is never walked through,
# 2026-08-02 adversarial round) and never reaching $HOME or /. An escaping-symlink
# COORD.md is skipped, never adopted. Neither answer: exit 0 silently, having written
# nothing, exactly as before. The variable keeps its historical name; it is the ESTATE
# root, not only a git one.
. "$(cd "$(dirname "$0")" && pwd)/estate-root.sh" 2>/dev/null || true
GIT_ROOT="${NR_ESTATE_ROOT:-}"
[ -z "$GIT_ROOT" ] && exit 0

# ── everything else in python3 (stdlib only): defensive JSON parse of the
# SubagentStop payload (schema unverified — tries several key spellings),
# transcript scrape for model + last-assistant snippet, and a flock'd append
# (chatroom/room.py's concurrency pattern — shell flock one-liners aren't
# reliable on macOS). Payload rides in via env so the heredoc stays python's
# script and stdin is free. Note: the env carrier has the ~1 MB ARG_MAX ceiling —
# a payload above it silently drops the entry (harmless: SubagentStop payloads
# carry only paths/ids, orders of magnitude under the limit).
NR_HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
# ── (S50) THE IMPORT ABOVE IS RIGHT AND IT IS NOT FREE.
# `_tasks_bases()` imports the watcher's resolver rather than keeping a second copy of it --
# a corrected constant in two files is the same defect with a newer value, so the import stays.
# But importing a module makes CPython write `__pycache__/` NEXT TO IT, and that module lives
# inside the plugin repo. This hook fires on every subagent stop, so the running install was
# dirtying its own git working tree continuously.
#
# That is worse than untidiness HERE specifically: the running install IS a working tree, and a
# seat seeing unexplained dirt in it cannot tell harmless bytecode from someone's uncommitted
# work without stopping to look. The estate paid 119 irreversible ledger rows this afternoon for
# a neighbouring confusion.
#
# STOPS THE WRITE rather than hiding it -- a .gitignore would have hidden the dirt and left the
# write in place, and hiding a write is not the same as not writing.
# MEASURED COST: ~2 ms per hook fire (41 ms vs 38 ms over the cached path, n=2 each) -- the
# module is recompiled every fire instead of being read back from disk.
export PYTHONDONTWRITEBYTECODE=1
export GIT_ROOT PAYLOAD NR_HOOK_DIR
python3 <<'PY' 2>/dev/null || true
import os, sys, re, json, fcntl
from datetime import datetime, timezone


def _tasks_bases():
    """Host-portable `<tmp>/claude-<uid>` bases — SHARED WITH THE SWARM WATCHER.

    S37. This hook and swarm.py each carried their own copy of the constant
    `/private/tmp/claude-501`, and the copy was wrong on this host in both. The fix is
    not a corrected constant in two files — that is the same defect with a newer value.
    The watcher's `tasks_bases()` is IMPORTED here so the two cannot drift apart again.

    The local probe below runs only if that import fails, and it DERIVES rather than
    hardcodes, so even the fallback cannot reintroduce a foreign host's path. The hook's
    silence law still governs: any failure here yields an empty list and the scrape
    simply finds nothing, which is the honest outcome rather than a wrong one.
    """
    hd = os.environ.get("NR_HOOK_DIR", "")
    if hd:
        sp = os.path.join(hd, "..", "skills", "agentswarm", "scripts")
        if sp not in sys.path:
            sys.path.insert(0, sp)
    try:
        from swarm import tasks_bases
        return tasks_bases()
    except Exception:
        pass
    import tempfile as _tf
    uid = getattr(os, "getuid", lambda: None)()
    out = []
    if uid is None:
        return out
    for t in (os.environ.get("TMPDIR"), _tf.gettempdir(), "/tmp", "/private/tmp"):
        if not t:
            continue
        c = os.path.join(t.rstrip("/") or "/", "claude-%d" % uid)
        if os.path.isdir(c) and c not in out:
            out.append(c)
    return out

try:
    git_root = os.environ.get("GIT_ROOT", "").strip()
    if not git_root:
        sys.exit(0)

    def safe(p):
        """CONTAINMENT (2026-08-02 adversarial round): never write through a symlink that
        escapes the estate root — a hostile or careless link turned this hook into a
        writer in someone else's tree, carrying the lane's verbatim commission with it.
        Returns the REALPATH to operate on, so an in-root link keeps working and survives
        the write; returns None when the target resolves outside, and the caller then
        writes nothing at all (the hook's silence law does the rest)."""
        try:
            r = os.path.realpath(git_root)
            rp = os.path.realpath(p)
            return rp if rp == r or rp.startswith(r + os.sep) else None
        except Exception:
            return None

    # ── defensive parse: tolerate absent/malformed JSON entirely.
    data = {}
    try:
        data = json.loads(os.environ.get("PAYLOAD", ""))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    # ── transcript path: try the plausible key spellings in order.
    tpath = ""
    for k in ("agent_transcript_path", "agentTranscriptPath",
              "transcript_path", "transcriptPath"):
        v = data.get(k)
        if isinstance(v, str) and v:
            tpath = v
            break

    # ── agent id: explicit keys, else derive from the filename agent-<id>.jsonl.
    agent_id = ""
    for k in ("agent_id", "agentId", "subagent_id", "subagentId"):
        v = data.get(k)
        if v:
            agent_id = str(v)
            break
    if not agent_id and tpath:
        m = re.match(r"agent-(.+?)\.jsonl$", os.path.basename(tpath))
        if m:
            agent_id = m.group(1)
    if not agent_id:
        agent_id = "?"

    # ── TRANSCRIPT RESOLUTION + THE META SIDECAR (2026-08-05).
    # ROOT CAUSE of 66 degraded receipts in 129: every field — model, tokens, snippet,
    # size — was read from ONE source, the payload's transcript_path, so when that file
    # was not on disk at stop time the whole receipt collapsed to `model=? tokens=unknown`
    # and the offload audit lost its only evidence. Two repairs, both cheap:
    #   (a) if the payload path does not resolve, look for the transcript where the
    #       harness conventionally writes it — <session-dir>/subagents/agent-<id>.jsonl —
    #       derived from the id we already have.
    #   (b) the `.meta.json` SIDECAR is written at SPAWN (observed: meta 23:07, jsonl
    #       23:08) and carries {"model": ...}. When the transcript is missing or still
    #       being flushed, the sidecar still names the model — which is the one field the
    #       routing policy is actually audited on. Sidecar is a FALLBACK, never an
    #       override: a model scraped from the real transcript always wins.
    def _resolve(tp, aid):
        if tp:
            cand = tp if os.path.isabs(tp) else os.path.join(os.getcwd(), tp)
            if os.path.isfile(cand):
                return cand
        if aid and aid != "?":
            base = os.path.dirname(tp) if tp else ""
            for d in ([base] if base else []):
                alt = os.path.join(d, "agent-%s.jsonl" % aid)
                if os.path.isfile(alt):
                    return alt
            # THE SESSION TASKS DIR (2026-08-05). A lane spawned by the Agent tool may
            # transcribe only to <tmp>/claude-<uid>/<slug>/<session>/tasks/<id>.output
            # — the same discovery gap that made the watcher read `watching 0`. One
            # discovery, two consumers: the watcher sweeps it, and so does this scrape.
            try:
                slug = "-" + os.path.realpath(os.environ.get("GIT_ROOT", "")).lstrip(
                    "/").replace("/", "-")
                for _base in _tasks_bases():
                    tb = os.path.join(_base, slug)
                    for sess in (os.listdir(tb) if os.path.isdir(tb) else []):
                        cand = os.path.join(tb, sess, "tasks", "%s.output" % aid)
                        if os.path.isfile(cand):
                            return cand
            except OSError:
                pass
        return tp if tp else ""

    tpath = _resolve(tpath, agent_id)

    def _meta_model(tp):
        if not tp:
            return ""
        try:
            mp = tp[:-6] + ".meta.json" if tp.endswith(".jsonl") else tp + ".meta.json"
            with open(mp, "r", encoding="utf-8", errors="replace") as mf:
                return str(json.load(mf).get("model") or "").strip()
        except Exception:
            return ""

    # ── scrape the transcript: model + byte size + the first ~160 chars of the
    # LAST assistant text (newlines flattened). Model comes from the assistant
    # message objects we already walk (msg.model, else obj.model on assistant
    # lines) — NOT a global "model" regex, which grabs decoy/tool-content or
    # "<synthetic>" keys. Keep the LAST real assistant's model, pairing it with
    # the same line whose text becomes the snippet.
    # tok_total/tok_seen also fund the spend auto-receipt below: summed from the
    # per-message usage objects the transcript actually carries (no guessing —
    # zero usage objects means no number is written at all).
    # ── THE SCRAPE — AND THE FLUSH RACE IT USED TO LOSE (docket item 7, 2026-08-31).
    #
    # A depth-2 lane on this estate receipted `model=sonnet tokens=unknown grade=estimate
    # purpose="auto-receipt: "` while its transcript on disk was perfectly intact — usage
    # object, model and text all present. The COORD line recorded bytes=44594; that file's
    # line boundaries are 503 / 10651 / 44594 / 45932. The hook read at exactly the byte
    # where the FINAL ASSISTANT LINE — the only line carrying usage, model and text — had
    # not yet been flushed. It is a WRITE RACE, not a schema difference, and short nested
    # lanes lose it most often because they finish inside a single flush.
    #
    # So the scrape is a FUNCTION, and it is called again while the file is still
    # growing. A complete transcript pays nothing: the first call answers and the settle
    # loop never runs.
    def _scrape(p):
        """One pass over a transcript → every field both ledgers carry. Pure enough to
        be called repeatedly: it only reads."""
        r = {"model": "?", "snippet": "?", "last_full": "", "size": "?",
             "tok_total": 0, "tok_seen": False, "calls": 0,
             "first_ts": "", "last_ts": "", "brief": None}
        try:
            r["size"] = str(os.path.getsize(p))
        except Exception:
            return r
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as tf:
                text = tf.read()
        except Exception:
            return r
        if not text:
            return r
        last = None
        # ── the LANE BRIEF. The first user-role message in an agent transcript IS
        # the prompt the seat passed — the commission, in the seat's own words.
        # It is captured only before the first assistant turn, so tool results and
        # follow-up turns (also role=user) can never be mistaken for the ask.
        seen_assistant = False

        def flatten(c):
            """Content blocks → plain text; one rule for user and assistant alike."""
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                parts = []
                for b in c:
                    if isinstance(b, dict) and b.get("type") in (None, "text") \
                            and isinstance(b.get("text"), str):
                        parts.append(b["text"])
                    elif isinstance(b, str):
                        parts.append(b)
                return " ".join(parts)
            return ""

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            for _tk in ("timestamp", "ts", "time"):
                _tv = obj.get(_tk)
                if isinstance(_tv, str) and _tv:
                    if not r["first_ts"]:
                        r["first_ts"] = _tv
                    r["last_ts"] = _tv
                    break
            role = obj.get("role") or obj.get("type")
            msg = obj.get("message")
            if isinstance(msg, dict):
                role = msg.get("role", role)
                content = msg.get("content", obj.get("content"))
            else:
                content = obj.get("content")
            # ── token usage: one usage object per line at most (message-level
            # first, else top-level) so nothing is counted twice. Every
            # numeric *_tokens field is summed — input, output, and both
            # cache legs — because that is the whole billed footprint.
            usage = None
            if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
                usage = msg["usage"]
            elif isinstance(obj.get("usage"), dict):
                usage = obj["usage"]
            if usage:
                for uk, uv in usage.items():
                    if isinstance(uv, bool) or not isinstance(uv, int):
                        continue
                    if uk.endswith("_tokens") and uv >= 0:
                        r["tok_total"] += uv
                        r["tok_seen"] = True
            # ── commission capture: the first user turn, before any assistant turn.
            if role == "user" and r["brief"] is None and not seen_assistant:
                ut = flatten(content)
                if ut and ut.strip():
                    r["brief"] = ut
            if role != "assistant":
                continue
            seen_assistant = True
            # model from THIS assistant line (msg-level first, then top-level);
            # skip empty and the "<synthetic>" placeholder.
            m_here = None
            if isinstance(msg, dict) and isinstance(msg.get("model"), str):
                m_here = msg.get("model")
            elif isinstance(obj.get("model"), str):
                m_here = obj.get("model")
            if m_here and m_here.strip() and m_here.strip() != "<synthetic>":
                r["model"] = m_here.strip()
            _c = msg.get("content") if isinstance(msg, dict) else obj.get("content")
            if isinstance(_c, list):
                for _b in _c:
                    if isinstance(_b, dict) and _b.get("type") == "tool_use":
                        r["calls"] += 1
            txt = flatten(content)
            if txt and txt.strip():
                last = txt
        if last is not None:
            r["last_full"] = last
            flat = re.sub(r"\s+", " ", last).strip()
            if flat:
                r["snippet"] = flat[:160]
        return r

    def _settle(p):
        """Read again while the transcript is still being written.

        BOUNDED, and bounded twice over: at most ~2 s of wall clock, and it gives up
        the moment the file has gone ~0.6 s without gaining a byte — a file that has
        stopped growing will not become more complete by being waited on. A transcript
        that was already whole costs exactly one stat and one read, as before.
        """
        r = _scrape(p)
        if (r["tok_seen"] and r["snippet"] != "?") or r["size"] == "?":
            return r
        import time as _time
        deadline = _time.time() + 2.0
        stable, prev = 0, r["size"]
        while _time.time() < deadline:
            _time.sleep(0.15)
            r2 = _scrape(p)
            if r2["size"] != "?":
                r = r2
            if r["tok_seen"] and r["snippet"] != "?":
                break
            stable = stable + 1 if r["size"] == prev else 0
            prev = r["size"]
            if stable >= 4:
                break
        return r

    model, snippet, size = "?", "?", "?"
    tok_total, tok_seen = 0, False
    calls, first_ts, last_ts = 0, "", ""
    brief_text = None
    last_full = ""
    _p = ""
    if tpath:
        _p = tpath if os.path.isabs(tpath) else os.path.join(os.getcwd(), tpath)
        _r = _settle(_p)
        model, snippet, size = _r["model"], _r["snippet"], _r["size"]
        tok_total, tok_seen = _r["tok_total"], _r["tok_seen"]
        calls, first_ts, last_ts = _r["calls"], _r["first_ts"], _r["last_ts"]
        brief_text, last_full = _r["brief"], _r["last_full"]

    if model == "?":
        _mm = _meta_model(tpath)
        if _mm:
            model = _mm

    def _secs(a, b):
        """Wall-clock between the transcript's first and last stamp. ISO-8601 only, and
        an unparseable pair yields "?" rather than a number nobody can trust."""
        try:
            from datetime import datetime as _dt
            f = lambda v: _dt.fromisoformat(v.replace("Z", "+00:00"))
            return str(int(round((f(b) - f(a)).total_seconds())))
        except Exception:
            return "?"

    secs = _secs(first_ts, last_ts) if (first_ts and last_ts) else "?"
    calls_s = str(calls) if tok_seen or calls else "?"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    # flatten the payload-derived fields so a hostile/malformed value carrying
    # newlines can't forge extra ledger lines (tpath stays raw above for file I/O).
    agent_id = re.sub(r"\s+", " ", agent_id).strip() or "?"
    tdisp = (re.sub(r"\s+", " ", tpath).strip() or "?") if tpath else "?"

    # all-unknown row (unrecognized schema / garbage payload) is pure ledger
    # noise — skip the append entirely; a silent no-write still honors the contract.
    if not (agent_id == "?" and tdisp == "?" and snippet == "?"):
        # ── brief extraction: make the COMMISSION estate-visible by construction.
        # The owner can read what any lane was actually asked without asking the seat
        # — a seat that narrows the ask can no longer do it invisibly, at any scale.
        #
        # Idempotent by O_CREAT|O_EXCL rather than by a lock: the filesystem itself
        # refuses the second writer, so racing redeliveries cannot rewrite a brief and
        # an existing brief is never touched. The pointer is set whenever the file
        # EXISTS (freshly written or already there), so every delivery of one stop
        # event composes a byte-identical ledger line and the dedup guard below still
        # collapses them. Extraction failure leaves the field off entirely — a missing
        # field is honest, a dead pointer is not.
        brief_rel = ""
        if brief_text and agent_id != "?":
            bname = "agent-%s.md" % agent_id
            bpath = os.path.join(git_root, "briefs", bname)
            bhdr = (f"# lane brief — {bname[:-3]}\n\n"
                    f"- extracted: {ts}\n"
                    f"- agent: {agent_id}\n"
                    f"- model: {model}\n"
                    f"- transcript: {tdisp}\n\n"
                    "Auto-extracted by the notrest SubagentStop hook: the first user-role\n"
                    "message of the agent transcript — the exact prompt the seat passed to\n"
                    "this lane. Reproduced verbatim below; never edited, never summarized.\n\n"
                    "---\n\n")
            try:
                os.makedirs(os.path.join(git_root, "briefs"), exist_ok=True)
                bpath = safe(bpath) or bpath
                if safe(bpath) is None:
                    raise OSError("brief path escapes the estate root")
                if not os.path.exists(bpath):
                    fd = os.open(bpath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                    with os.fdopen(fd, "w", encoding="utf-8") as bf:
                        bf.write(bhdr + brief_text.rstrip() + "\n")
                brief_rel = "briefs/" + bname
            except FileExistsError:
                brief_rel = "briefs/" + bname   # a racer won; the brief is there
            except Exception:
                brief_rel = ""

        entry = (f"- [{ts}] agent={agent_id} model={model} bytes={size} "
                 f"calls={calls_s} secs={secs} "
                 f"| last: {snippet} | transcript: {tdisp}"
                 + (f" | brief: {brief_rel}" if brief_rel else "") + "\n")

        header = (
            "# COORD-AGENTS.md — agent activity ledger (auto-written by the notrest SubagentStop hook)\n"
            "\n"
            "One line per completed agent, machine-written — never hand-edit (the COORD.md ledger is the\n"
            "human layer). The transcript path on each line is the full record: the entry is the index,\n"
            "the transcript is the audit. Compact the oldest lines into COORD-AGENTS-ARCHIVE.md at ~100 lines.\n"
            "\n"
            "## LEDGER\n"
        )

        # ── duplicate-delivery guard (the COORD half).
        # The harness can deliver the SAME SubagentStop more than once — observed in
        # this repo's own COORD-AGENTS.md as byte-identical pairs (27 duplicate lines
        # in 94), while spend/ledger.md held exactly one receipt per agent. Same
        # process, same flock, same payload: the flock was never the problem. The
        # spend receipt below CHECKED for its own prior line; this append did not
        # check anything, so every redelivered stop landed a second time. (hooks.json
        # registers this script once and one plugin is enabled, so the repeat is a
        # redelivery, not a double registration — and the guard below is deliberately
        # agnostic to how many times the event arrives.)
        #
        # The key is a STOP EVENT, not an agent: the entry with its timestamp stripped
        # — agent id + model + transcript size + snippet + path. A resumed lane
        # legitimately stops again with a GROWN transcript (real example in this
        # ledger: one lane stopped at bytes=1050279, then 1243214, then 1420927) and
        # must keep earning a line; a redelivered stop is identical and must not.
        # Dropping the timestamp also collapses a pair that straddles a minute
        # boundary, which an exact-line match would miss.
        stop_rx = re.compile(r"^- \[[^\]]*\] ")
        entry_sig = stop_rx.sub("", entry.rstrip("\n"))

        # ── concurrency-safe append: O_APPEND + fcntl.flock serialize writers, and
        # the guard runs INSIDE the lock so a racing pair cannot both pass it.
        # Header is written only when the file has no "## LEDGER" marker AND is
        # effectively blank (empty or whitespace-only) — so a whitespace-only file
        # still recovers its header, while a hand-damaged file with real content
        # but no marker just gets the entry appended (never a header mid-file).
        ledger = safe(os.path.join(git_root, "COORD-AGENTS.md"))
        try:
            if ledger is None:
                raise OSError("COORD-AGENTS.md escapes the estate root")
            fd = os.open(ledger, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
            with os.fdopen(fd, "a+", encoding="utf-8") as lf:
                fcntl.flock(lf, fcntl.LOCK_EX)
                try:
                    lf.seek(0)
                    existing = lf.read()
                    if "## LEDGER" not in existing and not existing.strip():
                        lf.write(header)
                    already = any(stop_rx.sub("", ln) == entry_sig
                                  for ln in existing.splitlines()
                                  if ln.startswith("- ["))
                    if not already:
                        lf.write(entry)
                    lf.flush()
                finally:
                    fcntl.flock(lf, fcntl.LOCK_UN)
        except Exception:
            pass

        # ── spend auto-receipt (the seat-tax cut): the transcript is already
        # parsed, so the ledger line the seat used to hand-run costs nothing
        # here. Rules:
        #   · APPEND ONLY to an existing <git_root>/spend/ledger.md — never
        #     create it, never mkdir spend/: a repo without a ledger has opted out.
        #   · IDEMPOTENT — the line carries a trailing "agent=<id>" token and we
        #     skip entirely if that token is already in the ledger, so replayed
        #     or duplicated SubagentStop events can never double-log. This key is
        #     deliberately COARSER than the COORD guard above (agent, not stop
        #     event): tok_total is summed over the WHOLE transcript, so receipting
        #     a resumed lane's later stops would re-bill every token of the earlier
        #     ones. One receipt per agent under-counts a resumed lane's tail; a
        #     per-stop receipt would over-count its head several times over. The
        #     under-count is the honest error and the shipped behavior — do not
        #     "align" this with the COORD key without also switching tok_total to a
        #     delta against the previously receipted size.
        #   · Format is byte-compatible with spend.py's own log writer (same
        #     field order, same flock'd O_APPEND discipline, same "unknown"
        #     rendering for a missing count). Replicated rather than imported
        #     because spend.py's cmd_log prints to stdout and creates the ledger —
        #     both forbidden here.
        #   · Honest grade: a real summed usage total is "observed"; a transcript
        #     carrying no usage objects yields tokens=unknown and "estimate".
        # Wrapped in its own try/except: a receipt failure must never disturb the
        # COORD-AGENTS write above.
        try:
            sledger = safe(os.path.join(git_root, "spend", "ledger.md"))
            # ── (S37) A RECEIPT THAT CANNOT RECORD THE AUDITED FIELD MUST NOT BE
            # WRITTEN AS A RECEIPT.
            #
            # This ledger exists to make the HARD offload rule ("every lane is opus")
            # CHECKABLE rather than asserted, and `model` is the single field the rule
            # is audited on. A row whose model is unknown does not weakly support the
            # rule — it cannot bear on it at all, while still counting as a line in a
            # file whose length reads as coverage. Measured before this change: 2,093
            # of 2,234 rows were `model=? tokens=unknown`, and 12 of 12 sampled hollow
            # ids resolved to NO artifact anywhere — not under the corrected tasks path,
            # not in the transcript store. Fixing the path (above) recovers almost none
            # of them; only refusing to write the row stops the inflation.
            #
            # WHY SILENCE AND NOT AN EXPLICIT `UNRESOLVED` GRADE, which was the other
            # option on the table: spend.py's `classify()` reads the MODEL token, and
            # its UNKNOWN_MODELS set is {"", "?", "-", "unknown", "none", "null"}. A row
            # reading `model=unresolved` therefore falls through to the final branch and
            # is judged a **violation** — a lane whose transcript merely went missing
            # would be recorded as one that BROKE the offload rule. That converts a
            # coverage-inflation defect into a false accusation, which is strictly worse
            # than the defect. An UNRESOLVED grade needs spend.py taught the token
            # first; that file is outside this commission's TOUCH-ONLY scope.
            #
            # The skipped count is not lost by staying silent: this hook still writes
            # one COORD-AGENTS.md line per completed lane, so lanes-stopped minus
            # receipts-written is the skip count, derivable from two ledgers already on
            # disk without inventing a third artifact to keep in sync.
            _model_known = str(model).strip().lower() not in (
                "", "?", "-", "unknown", "none", "null")
            if sledger and os.path.isfile(sledger) and _model_known:
                marker = f" agent={agent_id}"

                # ── TOKENS: a real figure where one exists, an honest estimate where
                # one can be derived, `unknown` only where genuinely nothing can be —
                # and in that last case the receipt SAYS SO (docket item 7).
                #
                # The old rule was `tok_seen or bust`, and bust meant `tokens=unknown`,
                # which spend.py scores as zero. A whole layer of a tiered swarm could
                # therefore vanish from the roll-up while every row still looked like a
                # row. A transcript with bytes on disk is not nothing: bytes/4 is the
                # conventional proxy, it is graded `estimate` (never `observed`), and
                # the derivation is written into the purpose so no reader can mistake
                # it for a measurement. That disclosure is the whole licence for the
                # number: an undisclosed estimate would be worse than the hole it fills.
                est_note = ""
                if tok_seen:
                    stokens, sgrade = str(tok_total), "observed"
                else:
                    sgrade = "estimate"
                    _bytes = int(size) if str(size).isdigit() else 0
                    if _bytes > 0:
                        stokens = str(max(1, _bytes // 4))
                        est_note = f"[est from {_bytes} transcript bytes]"
                    else:
                        stokens = "unknown"
                        est_note = ("[no transcript readable at stop — nothing was "
                                    "derivable; model came from the spawn sidecar]")

                # ── PURPOSE: the lane's own last words, else the COMMISSION it was
                # given. A lane that ends on a tool call has no closing text, and the
                # old writer left `purpose=""` — a receipt that says nothing about what
                # was bought. The first user turn is always on disk and is the ask
                # itself, so it is the honest fallback rather than an invented summary.
                purpose = "" if snippet == "?" else snippet[:60]
                if not purpose and brief_text:
                    purpose = "asked: " + re.sub(r"\s+", " ", brief_text).strip()[:53]
                purpose = re.sub(r"\s+", " ", purpose).replace('"', "'").strip()
                if est_note:
                    purpose = (purpose + " " + est_note).strip()

                # ── EVIDENCE FINGERPRINT (docket item 8d): bind the receipt to what the
                # lane actually said. `purpose` is a 60-char truncation and cannot serve
                # as evidence; this is the sha256 of the lane's FULL final text, so a
                # transcript can be re-hashed later and matched against its receipt.
                # Derived from the transcript tail when the lane left no closing text,
                # and OMITTED ENTIRELY when there is nothing to hash — a missing field is
                # honest, an invented fingerprint is not.
                #
                # THE TAIL FORM CARRIES ITS ANCHOR: `outsha=tail:<sha>@<size>` (refuter,
                # 2026-09-01). A transcript keeps GROWING after the stop that receipted
                # it — a resumed lane appends, and this hook's own settle loop exists
                # because the file is still being written. "the last 4096 bytes" is
                # therefore not a fixed window: a later reader recomputing it hashes
                # different bytes and concludes the receipt is wrong. Recording the size
                # the window was anchored on makes the field reproducible instead of
                # merely plausible. The full-text form needs no anchor: it hashes the
                # lane's final text, which does not change.
                sha_field = ""
                try:
                    import hashlib as _hl
                    if last_full.strip():
                        sha_field = " outsha=" + _hl.sha256(
                            last_full.encode("utf-8", "replace")).hexdigest()
                    elif str(size).isdigit() and int(size) > 0:
                        _sz = int(size)
                        with open(_p, "rb") as _tf2:
                            _tf2.seek(max(0, _sz - 4096))
                            sha_field = (" outsha=tail:%s@%d"
                                         % (_hl.sha256(_tf2.read()).hexdigest(), _sz))
                except Exception:
                    sha_field = ""

                # calls/secs go AFTER purpose: spend.py's ENTRY_RE stops at grade=, and
                # the seat-tax fixture pins `grade=<x> purpose="` as adjacent bytes. New
                # fields append; they never reshape a line other readers already parse.
                # `agent=` STAYS LAST: it is the idempotence key, matched as a trailing
                # token by this hook and by the fixtures.
                sline = (f"[{ts}] lane=subagent model={model} tokens={stokens} "
                         f"grade={sgrade} purpose=\"auto-receipt: {purpose}\""
                         f" calls={calls_s} secs={secs}{sha_field}"
                         f"{marker}\n")
                fd = os.open(sledger, os.O_RDWR | os.O_APPEND, 0o644)
                with os.fdopen(fd, "a+", encoding="utf-8") as sf:
                    fcntl.flock(sf, fcntl.LOCK_EX)
                    try:
                        sf.seek(0)
                        prior = sf.read()
                        # already receipted (exact trailing token) → write nothing
                        if agent_id != "?" and (marker + "\n") not in prior:
                            sf.write(sline)
                            sf.flush()
                    finally:
                        fcntl.flock(sf, fcntl.LOCK_UN)
        except Exception:
            pass
except Exception:
    pass
sys.exit(0)
PY

# ── PULSE LAYER (2026-08-05): refresh the machine-written readings in the background.
# Detached exactly like the session-start git-pull — subshell + & — so this hook returns
# in milliseconds however long the instruments take. estate-pulse.sh debounces itself at
# 60s, so a swarm landing five lanes produces ONE refresh, and it never writes COORD.
( bash "$(cd "$(dirname "$0")" && pwd)/estate-pulse.sh" "$GIT_ROOT" lane-stop >/dev/null 2>&1 & ) 2>/dev/null

exit 0
