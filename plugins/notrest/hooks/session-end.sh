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

# ── STDIN IS NOT READ AT ALL, AND THAT IS THE FIX (refuter F1, 2026-09-01).
# This hook never used the SessionEnd payload — the estate root is its only input — and
# the `cat` here existed solely so the writer would not see a broken pipe. It cost the
# one thing this hook cannot spend: TIME. A PLUGIN SessionEnd hook runs under the CLI's
# shared ~1.5 s SessionEnd abort no matter what `timeout` hooks.json declares (the
# budget raise consults settings.json and agent hooks, never plugin hooks) — so the 5 s
# bounded read every other hook uses could outlive the real budget and the cushion line,
# the entire point of this hook, would never be written. [cited: refuter's read of CLI
# 2.1.237; UNVERIFIED live by this lane.]
# A sub-second read is not available here: this machine's /bin/bash is 3.2.57, whose
# `read -t` rejects a fractional timeout ("invalid timeout specification") and whose
# `-t 0` fails even when data is waiting — measured, both. So the honest choice is zero
# wait, not a small one. Two shipped hooks (coord-nudge.sh, pre-compact.sh) have never
# read stdin either, so an unread payload is already the normal case on this surface.
# AND THE WRITER'S EPIPE IS SWALLOWED, NOT MERELY TOLERATED: on the CLI's synchronous
# hook path the stdin error handler is attached and the promise is resolved on the SAME
# TICK as the write/end, so an EPIPE rejection can never settle it — it cannot surface
# as a hook failure. The async path goes further and logs "hook command likely exited
# without reading stdin", i.e. the harness ANTICIPATES a non-reading hook rather than
# treating one as an error. [read off the 2.1.237 binary by the refuter; unverified live.]
# The 20 s in hooks.json stays: it is the INNER timer, and it is the one that would
# matter if the pool ever stopped applying to plugin hooks.

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

    def safe(p):
        """CONTAINMENT (2026-08-02 adversarial round): a symlinked COORD.md pointing out
        of the estate made this hook append its cushion — and seal its volume — into
        another tree entirely. Returns the REALPATH to operate on, so an in-root link
        keeps working and SURVIVES the roll's atomic replace (which would otherwise
        destroy the link and orphan its target); returns None when the target escapes,
        and the caller writes nothing."""
        try:
            r = os.path.realpath(git_root)
            rp = os.path.realpath(p)
            return rp if rp == r or rp.startswith(r + os.sep) else None
        except Exception:
            return None

    COORD = safe(os.path.join(git_root, "COORD.md"))
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
        if COORD and os.path.exists(COORD):
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
        # The SEAL belongs to the ESTATE ROOT (2026-08-02 round 2). /recap's walk.py and
        # compile.py glob COORD-*.md at the root, so a volume sealed beside a symlink's
        # TARGET silently disappears from both readers and the continues-pointer resolves
        # from the wrong directory. `d` is therefore the link's home — the root — while
        # only the fresh ACTIVE volume is written through the realpath, which is what lets
        # an in-root link survive the atomic replace.
        d = os.path.dirname(path) or "."
        path = safe(path)
        if not path or not os.path.exists(path):
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
        roll(os.path.join(git_root, "COORD.md"), "COORD", 500, COORD_FALLBACK)
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

# ── PULSE LAYER (2026-08-05): refresh the machine-written readings in the background.
# Detached exactly like the session-start git-pull — subshell + & — so this hook returns
# in milliseconds however long the instruments take. estate-pulse.sh debounces itself at
# 60s, so a swarm landing five lanes produces ONE refresh, and it never writes COORD.
( bash "$(cd "$(dirname "$0")" && pwd)/estate-pulse.sh" "$GIT_ROOT" session-end >/dev/null 2>&1 & ) 2>/dev/null

exit 0
