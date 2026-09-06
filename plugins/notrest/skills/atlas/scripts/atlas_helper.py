#!/usr/bin/env python3
"""atlas_helper — the git credential helper for the Atlas hub.

Two independent things live here, both answering the same question ("does this
process ever hold the token"): a pure git-credential-protocol function
(`credential_fill`) that a caller can feed stdin/stdout without touching the
filesystem itself, and the install/uninstall/check trio that manages the
*real* helper git actually invokes — the host-scoped shell one-liner from
IDENTITY-CONTRACT.md §9, copied byte-exact. `install` never reads the token;
it only writes the shell function that will read it later, at fill time, in a
process this script does not control. `check` proves the round trip works
without ever printing the secret — it compares lengths, not values.

Fixed interface (docket 4.9 wave A, COMMON):
  HOME = os.environ.get("NOTREST_HOME") or os.path.expanduser("~/.notrest")
  token file: HOME/atlas-token
  hub base: ATLAS_HUB_BASE env, default https://atlas.not.rest

CLI:
  atlas_helper.py fill                  stdin (git protocol) -> stdout (git protocol)
  atlas_helper.py install [--hub URL]   exit 0/1
  atlas_helper.py uninstall [--hub URL] exit 0/1
  atlas_helper.py check [--hub URL]     exit 0/1
"""
import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse

DEFAULT_HUB = "https://atlas.not.rest"

# IDENTITY-CONTRACT.md §9 — verbatim. Do not edit: reads the same token file
# §1/§10 write, at the moment git actually asks, in whatever shell git spawns
# it in. Kept as one literal string so nothing here can drift from the ruling.
HELPER_LINE = (
    '!f(){ echo username=atlas; echo "password=$(tr -d "\\r\\n" < '
    '"${NOTREST_HOME:-$HOME/.notrest}/atlas-token")"; }; f'
)


def notrest_home():
    return os.environ.get("NOTREST_HOME") or os.path.expanduser("~/.notrest")


def hub_host(hub_url):
    parsed = urlparse(hub_url)
    return parsed.netloc or parsed.path


def credential_fill(stdin_text, home, hub_host_):
    """Answer git's credential-fill protocol for one host only.

    stdin_text is git's `key=value` lines (protocol=..., host=..., ...).
    Returns the `username=atlas\\npassword=<token>\\n` block for the hub host,
    or "" for any other host, a missing token file, or an empty token.
    """
    fields = {}
    for line in stdin_text.splitlines():
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        fields[key] = value

    if fields.get("protocol") != "https" or fields.get("host") != hub_host_:
        return ""

    token_path = os.path.join(home, "atlas-token")
    try:
        with open(token_path, "r") as fh:
            token = fh.read().strip()
    except OSError:
        return ""
    if not token:
        return ""
    return "username=atlas\npassword=%s\n" % token


def _config_key(hub_url):
    return "credential.%s.helper" % hub_url


def install(hub_url=DEFAULT_HUB):
    r = subprocess.run(
        ["git", "config", "--global", _config_key(hub_url), HELPER_LINE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def uninstall(hub_url=DEFAULT_HUB):
    r = subprocess.run(
        ["git", "config", "--global", "--unset", _config_key(hub_url)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def check(hub_url=DEFAULT_HUB):
    """Round-trip `git credential fill` for the hub host. Never prints the
    password it receives — only whether one arrived, and how long it was."""
    payload = "protocol=https\nhost=%s\n\n" % hub_host(hub_url)
    try:
        r = subprocess.run(
            ["git", "credential", "fill"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
    if r.returncode != 0:
        return False

    got_username = False
    password_len = 0
    saw_password = False
    for line in r.stdout.splitlines():
        if line.startswith("username="):
            got_username = line[len("username="):] == "atlas"
        elif line.startswith("password="):
            saw_password = True
            password_len = len(line[len("password="):])
    return got_username and saw_password and password_len > 0


def _cli(argv):
    p = argparse.ArgumentParser(prog="atlas_helper.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fill")
    pi = sub.add_parser("install")
    pi.add_argument("--hub", default=DEFAULT_HUB)
    pu = sub.add_parser("uninstall")
    pu.add_argument("--hub", default=DEFAULT_HUB)
    pc = sub.add_parser("check")
    pc.add_argument("--hub", default=DEFAULT_HUB)
    args = p.parse_args(argv)

    if args.cmd == "fill":
        stdin_text = sys.stdin.read()
        base = os.environ.get("ATLAS_HUB_BASE", DEFAULT_HUB)
        sys.stdout.write(credential_fill(stdin_text, notrest_home(), hub_host(base)))
        return 0
    if args.cmd == "install":
        return 0 if install(args.hub) else 1
    if args.cmd == "uninstall":
        return 0 if uninstall(args.hub) else 1
    if args.cmd == "check":
        return 0 if check(args.hub) else 1
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
