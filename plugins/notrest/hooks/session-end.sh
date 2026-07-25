#!/bin/bash
# notrest SessionEnd hook — the estate's crash cushion.
# Fires when a session terminates, however it terminates (clean exit, /clear,
# crash, closed terminal). Two duties, both machine-written, both zero model
# tokens:
#   1. AUTO-CUSHION — if the session did not close deliberately with /sessionend,
#      append one line to COORD.md saying so, pointing the next session at the
#      tail, the agent ledger, and /notrest:oracle. The line's presence in a tail
#      is itself the signal that the previous session ended abruptly.
#   2. COMPACTION — enforce the ~40-line ledger law that was documented but never
#      executed: over threshold, the OLDEST lines move WHOLE into an archive file
#      (COORD-ARCHIVE.md / COORD-AGENTS-ARCHIVE.md) and the live ledger keeps the
#      newest. Lines are moved byte-identical — never rewritten, never summarized.
#
# Absolutely silent on success AND on every failure: no stdout, no stderr, always
# exit 0 — a broken hook must never break a session teardown. The whole body is
# wrapped so any error still exits 0.

# ── drain stdin (the SessionEnd payload; unused — the git root is the only input
# this hook needs) so the writer never sees a broken pipe. Outside a git repo:
# exit 0 silently, having written nothing.
cat >/dev/null 2>&1 || true
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$GIT_ROOT" ] && exit 0

# ── everything else in python3 (stdlib only): shell can't do the whole-line
# move safely. Shared-file writes go through fcntl.flock (agent-ledger.sh /
# chatroom room.py pattern — shell flock one-liners aren't reliable on macOS).
export GIT_ROOT
python3 <<'PY' 2>/dev/null || true
import os, sys, fcntl
from datetime import datetime, timezone

try:
    git_root = os.environ.get("GIT_ROOT", "").strip()
    if not git_root:
        sys.exit(0)

    COORD = os.path.join(git_root, "COORD.md")
    MARKER = "## LEDGER"
    CUSHION_MARK = "auto-cushion"
    CLOSE_MARK = "[sessionend] session closed"

    def ledger_lines(text):
        # a ledger line is a top-level list item; everything else (header prose,
        # blanks, markers) is structure and is never moved or counted.
        return [l for l in text.splitlines() if l.startswith("- ")]

    # ── duty 1: auto-cushion ─────────────────────────────────────────────────
    # Guard is the LAST ledger line only: skip when the session closed properly
    # (/sessionend wrote its close line) and skip when the previous line is
    # already a cushion (so N consecutive read-only sessions add exactly one
    # cushion line, not N). Limitation by design: the cushion cannot tell a
    # session that did real work from one that only read — it marks the ledger's
    # tail as "resume point, not a deliberate close", which is true either way.
    try:
        if os.path.exists(COORD):
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
            entry = (f"- [{ts}] [hook] session ended without /sessionend — "
                     f"auto-cushion: resume from this tail; agents ledger "
                     f"COORD-AGENTS.md; run /notrest:oracle to resume properly\n")
            fd = os.open(COORD, os.O_RDWR | os.O_APPEND)
            with os.fdopen(fd, "a+", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.seek(0)
                    text = f.read()
                    lines = ledger_lines(text)
                    last = lines[-1] if lines else ""
                    if CLOSE_MARK not in last and CUSHION_MARK not in last:
                        if text and not text.endswith("\n"):
                            f.write("\n")
                        f.write(entry)
                        f.flush()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass

    # ── duty 2: compaction ───────────────────────────────────────────────────
    def compact(path, apath, threshold, keep, header):
        # Over `threshold` ledger lines: move the oldest (count - keep) into
        # `apath`, preserving order, byte-identical. Structure lines (header,
        # blanks) stay where they are. Ordering is archive-first + fsync, then
        # the live file is replaced atomically (temp + os.replace) — so the only
        # crash window duplicates a line into the archive, never loses one.
        if not os.path.exists(path):
            return
        fd = os.open(path, os.O_RDWR)
        with os.fdopen(fd, "r+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                # inode guard: if another writer replaced this path while we
                # waited on the lock, our read is stale — skip rather than
                # resurrect old content.
                try:
                    if os.stat(path).st_ino != os.fstat(f.fileno()).st_ino:
                        return
                except Exception:
                    return
                f.seek(0)
                text = f.read()
                lines = text.splitlines(True)  # keepends: whole-line moves
                mark = None
                for i, l in enumerate(lines):
                    if l.strip() == MARKER:
                        mark = i
                if mark is None:
                    return  # no ledger section: hand-damaged/foreign file, leave it
                body = lines[mark + 1:]
                idx = [i for i, l in enumerate(body) if l.startswith("- ")]
                if len(idx) <= threshold:
                    return
                move = set(idx[:len(idx) - keep])
                moved = [body[i] if body[i].endswith("\n") else body[i] + "\n"
                         for i in sorted(move)]
                kept = [l for i, l in enumerate(body) if i not in move]

                afd = os.open(apath, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
                with os.fdopen(afd, "a+", encoding="utf-8") as af:
                    fcntl.flock(af, fcntl.LOCK_EX)
                    try:
                        af.seek(0)
                        existing = af.read()
                        if "## ARCHIVE" not in existing and not existing.strip():
                            af.write(header)
                        af.write("".join(moved))
                        af.flush()
                        os.fsync(af.fileno())
                    finally:
                        fcntl.flock(af, fcntl.LOCK_UN)

                tmp = path + ".sessionend.tmp"
                with open(tmp, "w", encoding="utf-8") as tf:
                    tf.write("".join(lines[:mark + 1] + kept))
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(tmp, path)
            finally:
                try:
                    fcntl.flock(f, fcntl.LOCK_UN)
                except Exception:
                    pass

    COORD_HEADER = (
        "# COORD-ARCHIVE.md — archived COORD ledger lines "
        "(auto-written by the notrest SessionEnd hook)\n"
        "\n"
        "Machine-written — never hand-edit. Archived oldest ledger lines — moved whole, never\n"
        "edited, never summarized. Append-only, oldest at the top; COORD.md keeps the newest\n"
        "lines. Read this when a resume needs history older than the live ledger's tail.\n"
        "\n"
        "## ARCHIVE\n"
    )
    AGENTS_HEADER = (
        "# COORD-AGENTS-ARCHIVE.md — archived agent ledger lines "
        "(auto-written by the notrest SessionEnd hook)\n"
        "\n"
        "Machine-written — never hand-edit. Archived oldest COORD-AGENTS.md lines — moved whole,\n"
        "never edited. Append-only, oldest at the top; the transcript path on each line is still\n"
        "the full record. COORD-AGENTS.md keeps the newest lines.\n"
        "\n"
        "## ARCHIVE\n"
    )

    try:
        compact(COORD, os.path.join(git_root, "COORD-ARCHIVE.md"), 40, 30, COORD_HEADER)
    except Exception:
        pass
    try:
        compact(os.path.join(git_root, "COORD-AGENTS.md"),
                os.path.join(git_root, "COORD-AGENTS-ARCHIVE.md"), 100, 60, AGENTS_HEADER)
    except Exception:
        pass
except Exception:
    pass
sys.exit(0)
PY

exit 0
