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

# ── capture the payload off stdin, then decide git-root early (no stdin needed
# for git). Outside a git repo: exit 0 silently, having written nothing.
PAYLOAD="$(cat 2>/dev/null || true)"
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$GIT_ROOT" ] && exit 0

# ── everything else in python3 (stdlib only): defensive JSON parse of the
# SubagentStop payload (schema unverified — tries several key spellings),
# transcript scrape for model + last-assistant snippet, and a flock'd append
# (chatroom/room.py's concurrency pattern — shell flock one-liners aren't
# reliable on macOS). Payload rides in via env so the heredoc stays python's
# script and stdin is free. Note: the env carrier has the ~1 MB ARG_MAX ceiling —
# a payload above it silently drops the entry (harmless: SubagentStop payloads
# carry only paths/ids, orders of magnitude under the limit).
export GIT_ROOT PAYLOAD
python3 <<'PY' 2>/dev/null || true
import os, sys, re, json, fcntl
from datetime import datetime, timezone

try:
    git_root = os.environ.get("GIT_ROOT", "").strip()
    if not git_root:
        sys.exit(0)

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

    # ── scrape the transcript: model + byte size + the first ~160 chars of the
    # LAST assistant text (newlines flattened). Model comes from the assistant
    # message objects we already walk (msg.model, else obj.model on assistant
    # lines) — NOT a global "model" regex, which grabs decoy/tool-content or
    # "<synthetic>" keys. Keep the LAST real assistant's model, pairing it with
    # the same line whose text becomes the snippet.
    # tok_total/tok_seen also fund the spend auto-receipt below: summed from the
    # per-message usage objects the transcript actually carries (no guessing —
    # zero usage objects means no number is written at all).
    model, snippet, size = "?", "?", "?"
    tok_total, tok_seen = 0, False
    brief_text = None
    if tpath:
        p = tpath if os.path.isabs(tpath) else os.path.join(os.getcwd(), tpath)
        try:
            size = str(os.path.getsize(p))
        except Exception:
            size = "?"
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as tf:
                text = tf.read()
        except Exception:
            text = ""
        if text:
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
                            tok_total += uv
                            tok_seen = True
                # ── commission capture: the first user turn, before any assistant turn.
                if role == "user" and brief_text is None and not seen_assistant:
                    ut = flatten(content)
                    if ut and ut.strip():
                        brief_text = ut
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
                    model = m_here.strip()
                txt = flatten(content)
                if txt and txt.strip():
                    last = txt
            if last is not None:
                flat = re.sub(r"\s+", " ", last).strip()
                if flat:
                    snippet = flat[:160]

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
        ledger = os.path.join(git_root, "COORD-AGENTS.md")
        try:
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
            sledger = os.path.join(git_root, "spend", "ledger.md")
            if os.path.isfile(sledger):
                marker = f" agent={agent_id}"
                purpose = "" if snippet == "?" else snippet[:60]
                purpose = re.sub(r"\s+", " ", purpose).replace('"', "'").strip()
                stokens = str(tok_total) if tok_seen else "unknown"
                sgrade = "observed" if tok_seen else "estimate"
                sline = (f"[{ts}] lane=subagent model={model} tokens={stokens} "
                         f"grade={sgrade} purpose=\"auto-receipt: {purpose}\""
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

exit 0
