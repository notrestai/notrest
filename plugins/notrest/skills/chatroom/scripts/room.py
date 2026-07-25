#!/usr/bin/env python3
"""room.py — file-based chatroom for AI sessions (Claude sessions + GPT via Codex CLI).

The wire is an append-only markdown log; atomicity via fcntl.flock; wakes via a
watch subcommand that EXITS when new lines land (run it in the background — the
harness notifies on exit, same pattern as fable-director token watches).

Subcommands:
  create <room>                       make the room (idempotent)
  post   <room> <handle> <text...>    atomic append: [utc] @handle: text
  read   <room> [--tail N]            print last N lines (default 20)
  lines  <room>                       print current line count (arm watches with it)
  join   <room> [--handle H] [--tail N] [--no-watch]
                                      read the tail, print the re-arm line, and ARM the
                                      watch — one call (run it as a BACKGROUND task)
  watch  <room> --lines N [--interval S] [--timeout S]
                                      exit 0 printing new lines when count > N
  gpt-bridge <room> [--handle gpt] [--think low|medium|high] [--once] [--all]
                                      poll; when @handle is mentioned in new lines
                                      (or --all), ask the room's codex session and
                                      post the reply. Cursor + session id persist
                                      in the room dir. codex runs in an EMPTY
                                      subdir (agentic cwd isolation).

Rooms live under $CHATROOM_ROOT (default ~/.claude/chatrooms). NO SECRETS in
rooms: bridge prompts leave the machine to the GPT vendor — and that law is
ENFORCED here (see SECRET_PATTERNS), not merely asked for.

Exit codes: 0 ok · 3 watch timeout · 5 REFUSED (secret shape in a post or a
bridge prompt — nothing was written, nothing was sent).
"""
import argparse, fcntl, os, pathlib, re, subprocess, sys, time
from datetime import datetime, timezone

ROOT = pathlib.Path(os.environ.get("CHATROOM_ROOT",
                                   pathlib.Path.home() / ".claude" / "chatrooms"))

# ── the no-secrets law, enforced ────────────────────────────────────────────
# A room is a shared file AND a wire to another vendor's model: the bridge posts
# room text to OpenAI verbatim. Prose asked members not to paste credentials;
# this screens for them. Every write path (post) and every send path (bridge)
# runs the screen FIRST.
#
# Refusal names the CLASS ONLY. The matched text is never echoed, never logged,
# never posted — an error message that quotes the key has leaked the key.
SECRET_PATTERNS = [
    ("private-key-header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}")),
    # bare `sk-<20+>` plus the prefixed form (sk-proj-…, sk-ant-…), whose dash
    # would otherwise break the run of alphanumerics and slip through.
    ("openai-style-key",
     re.compile(r"\bsk-(?:[A-Za-z0-9]{20,}|[A-Za-z0-9]{2,12}-[A-Za-z0-9_-]{16,})")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    # no leading \b: the keyword is usually mid-identifier (AWS_SECRET_ACCESS_KEY=…),
    # where a word boundary never fires.
    ("generic-credential-assignment",
     re.compile(r"((?:api|access|secret|private|auth)[_-]?key|secret|token|password"
                r"|passwd|credentials?)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", re.I)),
    # .env shape: UPPER_KEY=<32+> at the start of a line (`export` prefix allowed).
    # Anchored and uppercase so a legitimate `sha256=<64 hex>` in chat is not refused.
    # `⏎` is an alternative anchor because posts fold newlines into that marker.
    ("dotenv-secret-line",
     re.compile(r"(?:^|⏎)[ \t]*(?:export[ \t]+)?[A-Z][A-Z0-9_]{2,}=['\"]?"
                r"[A-Za-z0-9+/=_\-]{32,}", re.M)),
]


def screen(text):
    """Return the list of secret-shape CLASS NAMES present in text (never the text)."""
    return [name for name, pat in SECRET_PATTERNS if pat.search(text)]


def refuse_secrets(text, where):
    """Screen before any write or send. On a match: say the class, exit 5, do nothing."""
    hits = screen(text)
    if not hits:
        return
    sys.stderr.write(
        "REFUSED (%s): the no-secrets law — content matches secret-shape class(es): %s\n"
        "nothing was written to the room and nothing was sent to the bridge.\n"
        "the matching text is deliberately NOT echoed. Remove it and re-run.\n"
        % (where, ", ".join(hits)))
    sys.exit(5)


def rdir(name):
    d = ROOT / name
    return d


def rlog(name):
    return rdir(name) / "room.md"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def read_lines(name):
    p = rlog(name)
    if not p.exists():
        sys.exit(f"no such room: {name} (expected {p})")
    return p.read_text(encoding="utf-8").splitlines()


def cmd_create(a):
    d = rdir(a.room)
    (d / ".gptwork").mkdir(parents=True, exist_ok=True)
    p = rlog(a.room)
    if not p.exists():
        p.write_text(f"# room: {a.room} — created {now()}\n", encoding="utf-8")
    print(p)


def cmd_post(a):
    p = rlog(a.room)
    if not p.exists():
        sys.exit(f"no such room: {a.room} — create it first")
    raw = " ".join(a.text)
    # Screen the RAW text (newlines intact, before the ⏎ fold) so line-anchored
    # shapes still match, and screen before the room file is even opened. The handle
    # goes on its OWN line: prefixing it inline would push a pasted `KEY=…` off the
    # start of its line and silently defeat the .env anchor.
    refuse_secrets("@%s\n%s" % (a.handle, raw), "post")
    text = raw.replace("\n", " ⏎ ").strip()
    if not text:
        sys.exit("empty message")
    with open(p, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(f"[{now()}] @{a.handle}: {text}\n")
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)
    print("posted")


def cmd_read(a):
    for ln in read_lines(a.room)[-a.tail:]:
        print(ln)


def cmd_lines(a):
    print(len(read_lines(a.room)))


def cmd_join(a):
    """Read + arm, in one call. Run it as a BACKGROUND task: it prints the tail and
    the re-arm line, then blocks in the watch until someone posts."""
    lines = read_lines(a.room)
    n = len(lines)
    for ln in lines[-a.tail:]:
        print(ln)
    me = pathlib.Path(__file__).resolve()
    arm = f"python3 {me} watch {a.room} --lines {n} --timeout {int(a.timeout)}"
    print(f"--- room {a.room} · {n} lines · handle @{a.handle}")
    print(f"--- re-arm: {arm}")
    if a.no_watch:
        return
    print("--- armed: exit 0 prints the new lines, exit 3 = timeout (re-arm at the new "
          "count)", flush=True)
    cmd_watch(argparse.Namespace(room=a.room, lines=n, interval=a.interval,
                                 timeout=a.timeout))


def cmd_watch(a):
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        lines = read_lines(a.room)
        if len(lines) > a.lines:
            for ln in lines[a.lines:]:
                print(ln)
            return
        time.sleep(a.interval)
    print("watch timeout — no new messages")
    sys.exit(3)


CODEX_FLAGS = ["--skip-git-repo-check", "--sandbox", "read-only"]
TOKENS_RE = re.compile(r"tokens used:?\s*([\d,]+)", re.I)


def spend_root():
    """Where spend/ledger.md lives: $CHATROOM_SPEND_ROOT, else the nearest ancestor
    of this script that already has one, else the cwd."""
    env = os.environ.get("CHATROOM_SPEND_ROOT")
    if env:
        return pathlib.Path(env)
    here = pathlib.Path(__file__).resolve()
    for d in here.parents:
        if (d / "spend" / "ledger.md").exists():
            return d
    return pathlib.Path.cwd()


def spend_log(out, prompt, model="gpt-5.6-codex", lane="chatroom-gpt"):
    """Receipt every bridge call in the suite's ledger: observed when codex echoed
    `tokens used`, estimate (chars/4) when it did not. A ledger failure is never
    allowed to break the room — it degrades to a printed note."""
    m = TOKENS_RE.search(out or "")
    if m:
        tokens, grade = int(m.group(1).replace(",", "")), "observed"
    else:
        tokens, grade = max(1, (len(prompt) + len(out or "")) // 4), "estimate"
    script = pathlib.Path(__file__).resolve().parents[2] / "spend" / "scripts" / "spend.py"
    if os.environ.get("CHATROOM_NO_SPEND") or not script.exists():
        print(f"bridge: tokens={tokens} grade={grade} (no ledger written)", flush=True)
        return tokens, grade
    try:
        r = subprocess.run([sys.executable, str(script), "log", "--model", model,
                            "--tokens", str(tokens), "--lane", lane, "--grade", grade,
                            "--purpose", "chatroom gpt-bridge reply",
                            "--root", str(spend_root())],
                           text=True, timeout=30, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        if r.returncode != 0:
            print(f"bridge: spend receipt failed (exit {r.returncode}) — "
                  f"tokens={tokens} grade={grade}", flush=True)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"bridge: spend receipt failed ({exc.__class__.__name__}) — "
              f"tokens={tokens} grade={grade}", flush=True)
    return tokens, grade


def codex_call(room, prompt, think):
    # The send path. Everything below this line leaves the machine — screen first.
    refuse_secrets(prompt, "gpt-bridge send")
    d = rdir(room)
    work = d / ".gptwork"
    work.mkdir(exist_ok=True)
    sess_file = d / ".gpt-session"
    eff = f"model_reasoning_effort={think}"  # no embedded quotes: list-form args
    if sess_file.exists():
        cmd = ["codex", "exec", "--sandbox", "read-only", "-c", eff,
               "resume", sess_file.read_text().strip(),
               "--skip-git-repo-check", prompt]
    else:
        cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only",
               "-c", eff, prompt]
    out = subprocess.run(cmd, cwd=work, text=True, stdin=subprocess.DEVNULL,
                         timeout=240, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT).stdout
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)  # strip ANSI (context-dependent)
    m = re.search(r"session id: ([0-9a-f-]+)", out)
    if m and not sess_file.exists():
        sess_file.write_text(m.group(1))
    spend_log(out, prompt)
    # answer = text after the last '\ncodex\n' marker, cut at 'tokens used'
    parts = out.split("\ncodex\n")
    ans = parts[-1].split("\ntokens used")[0].strip() if len(parts) > 1 else ""
    return ans


def cmd_bridge(a):
    d = rdir(a.room)
    cur_file = d / ".gpt-cursor"
    if cur_file.exists():
        cursor = int(cur_file.read_text())
    else:
        # first run: look back up to 10 lines so pre-bridge mentions are seen
        cursor = max(1, len(read_lines(a.room)) - 10)
    print(f"bridge: starting at cursor {cursor}", flush=True)
    posts_this_min, minute = 0, int(time.time() // 60)
    while True:
        lines = read_lines(a.room)
        new = [ln for ln in lines[cursor:] if f"@{a.handle}:" not in ln]
        trigger = any(f"@{a.handle}" in ln for ln in new) or (a.all and new)
        if trigger:
            m = int(time.time() // 60)
            if m != minute:
                minute, posts_this_min = m, 0
            if posts_this_min >= 4:
                time.sleep(15)
                continue
            context = "\n".join(lines[-30:])
            prompt = (f"You are @{a.handle}, a GPT participant in a multi-agent "
                      f"chatroom shared with Claude sessions and a human owner. "
                      f"Be concise and useful; plain text only — your reply is "
                      f"posted verbatim as one message. Never include secrets. "
                      f"NEW MESSAGES:\n" + "\n".join(new) +
                      f"\n\nRECENT CONTEXT:\n{context}\n\nYour single reply:")
            print(f"bridge: triggered by {len(new)} new line(s), calling codex…",
                  flush=True)
            ans = codex_call(a.room, prompt, a.think)
            if ans:
                a2 = argparse.Namespace(room=a.room, handle=a.handle,
                                        text=[ans.replace("\n", " ⏎ ")])
                cmd_post(a2)
                posts_this_min += 1
        cursor = len(read_lines(a.room))
        cur_file.write_text(str(cursor))
        if a.once:
            return
        time.sleep(a.interval)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("room"); c.set_defaults(f=cmd_create)
    p = sub.add_parser("post"); p.add_argument("room"); p.add_argument("handle")
    p.add_argument("text", nargs="+"); p.set_defaults(f=cmd_post)
    r = sub.add_parser("read"); r.add_argument("room")
    r.add_argument("--tail", type=int, default=20); r.set_defaults(f=cmd_read)
    l = sub.add_parser("lines"); l.add_argument("room"); l.set_defaults(f=cmd_lines)
    j = sub.add_parser("join"); j.add_argument("room")
    j.add_argument("--handle", default="claude"); j.add_argument("--tail", type=int, default=30)
    j.add_argument("--interval", type=float, default=3)
    j.add_argument("--timeout", type=float, default=3600)
    j.add_argument("--no-watch", action="store_true"); j.set_defaults(f=cmd_join)
    w = sub.add_parser("watch"); w.add_argument("room")
    w.add_argument("--lines", type=int, required=True)
    w.add_argument("--interval", type=float, default=3)
    w.add_argument("--timeout", type=float, default=3600); w.set_defaults(f=cmd_watch)
    b = sub.add_parser("gpt-bridge"); b.add_argument("room")
    b.add_argument("--handle", default="gpt"); b.add_argument("--think", default="low")
    b.add_argument("--once", action="store_true"); b.add_argument("--all", action="store_true")
    b.add_argument("--interval", type=float, default=5); b.set_defaults(f=cmd_bridge)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
