#!/bin/bash
# notrest SessionEnd hook — the estate's crash cushion.
# Fires when a session terminates, however it terminates (clean exit, /clear,
# crash, closed terminal). Two duties, both machine-written, both zero model
# tokens:
#   1. AUTO-CUSHION — if the session did not close deliberately with /sessionend,
#      append one line to COORD.md saying so, pointing the next session at the
#      tail, the agent ledger, and /notrest:oracle. The line's presence in a tail
#      is itself the signal that the previous session ended abruptly.
#   2. VOLUME ROLL — the ledger is permanent bookkeeping and is NEVER compacted.
#      Over threshold the WHOLE active file is SEALED byte-identical as the next
#      COORD-<NNN>.md (001, 002, 003…) and a fresh active COORD.md continues the
#      count. Archiving MOVES lines (a crash window, and the archive is never
#      read); sealing PRESERVES them — immutable, complete, chronological.
#      Sessions read the ACTIVE volume's tail; recap/compile read every volume.
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

    # ── duty 2: volume roll ──────────────────────────────────────────────────
    # OWNER LAW: the ledger is never compacted-and-archived. Over `threshold`
    # ledger lines the ACTIVE volume is SEALED WHOLE as the next free
    # `<prefix>-<NNN>.md` (zero-padded 3) and a fresh active file starts. Sealed
    # volumes are immutable — never edited, never appended to, never deleted.
    # Crash-safe order: the sealed copy is written + fsync'd FIRST, then the
    # active file is replaced atomically (tmp + os.replace) — so the worst crash
    # leaves a complete sealed copy beside an untouched active file (the next run
    # simply seals to the next free number), never a lost line.
    # LEGACY: COORD-ARCHIVE.md / COORD-AGENTS-ARCHIVE.md are the RETIRED scheme —
    # where a repo still has them they are left exactly as found: not migrated,
    # not appended to, not deleted (readers still read them for old history).
    def roll(path, prefix, threshold, fallback_header):
        if not os.path.exists(path):
            return
        d = os.path.dirname(path) or "."
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
                lines = text.splitlines(True)  # keepends: the seal is byte-exact
                mark = None
                for i, l in enumerate(lines):
                    if l.strip() == MARKER:
                        mark = i
                if mark is None:
                    return  # no ledger section: hand-damaged/foreign file, leave it
                if len([l for l in lines[mark + 1:]
                        if l.startswith("- ")]) <= threshold:
                    return

                n = 1
                while os.path.exists(os.path.join(d, "%s-%03d.md" % (prefix, n))):
                    n += 1
                sealed_name = "%s-%03d.md" % (prefix, n)

                # 1. SEAL: the whole active file, byte-identical, fsync'd.
                with open(os.path.join(d, sealed_name), "w",
                          encoding="utf-8", newline="") as sf:
                    sf.write(text)
                    sf.flush()
                    os.fsync(sf.fileno())

                # 2. FRESH ACTIVE VOLUME: this file's own header block (any prior
                # continues-line dropped so it never accumulates), the new
                # continues-line, the ledger marker, and the roll's own line.
                head = [l for l in lines[:mark] if not l.startswith("> Continues ")]
                while head and not head[-1].strip():
                    head.pop()
                if not [l for l in head if l.strip()]:
                    head = [fallback_header]
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
                fresh = ("".join(head).rstrip("\n") + "\n"
                         + "\n> Continues %s · volume %d\n\n" % (sealed_name, n + 1)
                         + MARKER + "\n"
                         + "- [%s] [hook] volume rolled — previous volume sealed "
                           "as %s\n" % (ts, sealed_name))
                tmp = path + ".sessionend.tmp"
                with open(tmp, "w", encoding="utf-8") as tf:
                    tf.write(fresh)
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(tmp, path)
            finally:
                try:
                    fcntl.flock(f, fcntl.LOCK_UN)
                except Exception:
                    pass

    # Fallback headers — used only when the rolled file had no header block of
    # its own (a file that starts straight at `## LEDGER`).
    COORD_FALLBACK = (
        "# COORD.md — session coordination ledger (active volume)\n"
        "\n"
        "Append-only, newest at the bottom, one line per substantive prompt when its work\n"
        "lands. Never compacted: past ~500 ledger lines this file is SEALED WHOLE as the next\n"
        "COORD-<NNN>.md and a fresh active volume starts. Sealed volumes are immutable —\n"
        "sessions read this tail; /recap, /compile and /archivist read every volume.\n"
    )
    AGENTS_FALLBACK = (
        "# COORD-AGENTS.md — agent activity ledger (active volume)\n"
        "\n"
        "Machine-written — never hand-edit. Never compacted: past ~1000 ledger lines this file\n"
        "is SEALED WHOLE as the next COORD-AGENTS-<NNN>.md and a fresh active volume starts.\n"
        "Sealed volumes are immutable and complete; the transcript path on each line is still\n"
        "the full record.\n"
    )

    try:
        roll(COORD, "COORD", 500, COORD_FALLBACK)
    except Exception:
        pass
    try:
        roll(os.path.join(git_root, "COORD-AGENTS.md"),
             "COORD-AGENTS", 1000, AGENTS_FALLBACK)
    except Exception:
        pass
except Exception:
    pass
sys.exit(0)
PY

exit 0
