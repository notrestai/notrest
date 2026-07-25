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
  watch  <room> --lines N [--interval S] [--timeout S]
                                      exit 0 printing new lines when count > N
  gpt-bridge <room> [--handle gpt] [--think low|medium|high] [--once] [--all]
                                      poll; when @handle is mentioned in new lines
                                      (or --all), ask the room's codex session and
                                      post the reply. Cursor + session id persist
                                      in the room dir. codex runs in an EMPTY
                                      subdir (agentic cwd isolation).

Rooms live under $CHATROOM_ROOT (default ~/.claude/chatrooms). NO SECRETS in
rooms: bridge prompts leave the machine to the GPT vendor.
"""
import argparse, fcntl, os, pathlib, re, subprocess, sys, time
from datetime import datetime, timezone

ROOT = pathlib.Path(os.environ.get("CHATROOM_ROOT",
                                   pathlib.Path.home() / ".claude" / "chatrooms"))


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
    text = " ".join(a.text).replace("\n", " ⏎ ").strip()
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


def codex_call(room, prompt, think):
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
