#!/usr/bin/env python3
"""atlas_auth.py — the Atlas login client: device flow, refresh, JWKS and revocation caches.

IDENTITY-CONTRACT.md §1 (device flow and its exact statuses), §2 (the token, refresh, keys),
§4 (revocation). This module TALKS to the hub; `atlas_token.py` DECIDES about the token it
stored. Two files so the deciding half stays network-free and importable by every hook.

Laws this file keeps:
  · Secrets by path, never by value. The token crosses this module three times — the poll
    response, the refresh response, and the Authorization header — and is never printed,
    logged, put in argv, an env value or a URL. No response body is ever echoed: the 200
    body of a poll IS the secret, so errors carry a status code and nothing else.
  · stdlib only, python 3.9 (a hook may import this).
  · Silent on failure where the interface says silent: refresh/fetch_jwks/fetch_revoked
    return False and never raise, because a SessionStart hook that shouts is a broken hook.
    `device_login` is the one loud path — a human is watching it — and it fails with ONE
    fact, never a stack trace.

CLI:
    atlas_auth.py login       [--base B] [--home H]   exit 0 / 7
    atlas_auth.py refresh     [--base B] [--home H]   exit 0 / 1, silent
    atlas_auth.py jwks        [--base B] [--home H]   exit 0 / 1, silent
    atlas_auth.py revoked     [--base B] [--home H]   exit 0 / 1, silent
    atlas_auth.py sessionstart [--budget-ms 2000]     always exit 0, nothing on stdout
"""

import argparse
import json
import os
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request

CLIENT = "notrest-plugin"
DEFAULT_HUB = "https://atlas.not.rest"
REFRESH_WINDOW = 7 * 86400          # §2: refresh only inside the last 7 days of life
POLL_TIMEOUT_MAX = 10.0
SLOW_DOWN_STEP = 5                  # §1: 429 → interval += 5
EXIT_OK = 0
EXIT_NO_VALID_KEY = 7               # the plugin's "no valid key/token"

_TOKEN_MOD = None


# ---------------------------------------------------------------- paths & env

def notrest_home():
    """`${NOTREST_HOME:-~/.notrest}` — the one resolution, shared with atlas.py's notrest_home()
    and A2's atlas_token. expanduser wraps the WHOLE expression on purpose: a machine that sets
    `NOTREST_HOME=~/alt` must not get a literal `./~/alt` here and the real path in the hook —
    two answers to one gate question (COMMON amendment, 4.9 wave A)."""
    return os.path.expanduser(os.environ.get("NOTREST_HOME") or "~/.notrest")


def default_base():
    """The hub. Read at CALL time, never at import time: a fixture sets the env after import."""
    return (os.environ.get("ATLAS_HUB_BASE") or DEFAULT_HUB).rstrip("/")


def token_path(home):
    return os.path.join(home, "atlas-token")


def jwks_path(home):
    return os.path.join(home, "atlas-jwks.json")


def revoked_path(home):
    return os.path.join(home, "atlas-revoked.json")


def plugin_version():
    """The shipped version, for the hub's `pulls:`/seat record. Never load-bearing: a copy of
    this file outside the plugin tree honestly says `unknown` rather than inventing a number."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        p = os.path.join(d, ".claude-plugin", "plugin.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    return str(json.load(fh).get("version") or "unknown")
            except (OSError, ValueError):
                return "unknown"
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return "unknown"


def _token_module():
    """atlas_token, imported by sibling path (A2's module; it owns every verdict)."""
    global _TOKEN_MOD
    if _TOKEN_MOD is None:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import atlas_token                      # noqa: E402  (deliberately lazy)
        _TOKEN_MOD = atlas_token
    return _TOKEN_MOD


# ---------------------------------------------------------------- errors & io

class AuthError(Exception):
    """One fact, no decoration. `.reason` is the line a human is shown."""

    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


class _NetError(Exception):
    """The hub could not be reached at all (DNS, refused, reset, timeout, TLS)."""


def _request(method, url, timeout, payload=None, token=None):
    """(status, body_bytes). Raises _NetError when there was no HTTP answer at all.

    The body is returned to the CALLER and never to a log: a 200 poll body holds the token."""
    data = None
    req = urllib.request.Request(url, method=method)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("content-type", "application/json")
        req.data = data
    req.add_header("accept", "application/json")
    req.add_header("user-agent", "%s/%s" % (CLIENT, plugin_version()))
    if token:
        req.add_header("authorization", "Bearer " + token)   # header only — never a URL
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as exc:                    # an answer, just not 2xx
        try:
            body = exc.read()
        except Exception:                                    # noqa: BLE001 — body is optional
            body = b""
        return exc.code, body
    except (urllib.error.URLError, socket.timeout, OSError, ValueError) as exc:
        raise _NetError(str(exc))


def _json(body, err):
    try:
        obj = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise AuthError(err)
    if not isinstance(obj, dict):
        raise AuthError(err)
    return obj


def _write_private(path, text, mode=0o600):
    """tmp + rename, inside the target dir, 0600 before it is ever named. A reader never sees
    half a token; a stray tmp file is never world-readable."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".atlas-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _store_token(home, token):
    if not isinstance(token, str) or not token.strip():
        raise AuthError("login: hub returned no token")
    _write_private(token_path(home), token.strip() + "\n", 0o600)


def _writeln(out, text):
    """Never let a terminal's encoding turn a login into a traceback."""
    try:
        out.write(text + "\n")
    except UnicodeEncodeError:
        out.write(text.encode("ascii", "replace").decode("ascii") + "\n")
    try:
        out.flush()
    except Exception:                                        # noqa: BLE001
        pass


# ---------------------------------------------------------------- §1 device flow

def device_login(home, base=None, out=sys.stderr):
    """§1. start → print URL + code → poll → store → verdict. Returns the claims.

    Raises AuthError with one fact on every failure. The only path in this file that speaks."""
    base = (base or default_base()).rstrip("/")
    tok = _token_module()
    payload = {
        "client": CLIENT,
        "version": plugin_version(),
        "machine": {
            # §1: the portal SHOWS a machine name; the identity is the fingerprint. The
            # hostname is a suggestion the human may overwrite, and is never an input to fp.
            "name": socket.gethostname(),
            "fp": tok.fingerprint(home),
        },
    }
    try:
        status, body = _request("POST", base + "/v1/auth/device/start", 10.0, payload=payload)
    except _NetError:
        raise AuthError("hub unreachable at %s" % base)
    if status != 200:
        raise AuthError("login: start refused with HTTP %d" % status)

    start = _json(body, "login: start returned unparseable JSON")
    device_code = start.get("device_code")
    user_code = start.get("user_code")
    uri = start.get("verification_uri")
    if not (isinstance(device_code, str) and isinstance(user_code, str) and isinstance(uri, str)):
        raise AuthError("login: start is missing device_code, user_code or verification_uri")
    try:
        # Floor and ceiling are ours, not the hub's: `interval: 0` from a broken or hostile
        # hub is a hot loop, and `expires_in: 86400` is a session that never comes back.
        interval = min(60.0, max(0.2, float(start.get("interval", 5))))
    except (TypeError, ValueError):
        interval = 5.0
    try:
        expires_in = min(3600, max(1, int(start.get("expires_in", 900))))
    except (TypeError, ValueError):
        expires_in = 900

    _writeln(out, "Open %s and enter the code: %s" % (uri, user_code))
    _writeln(out, "Waiting (expires in %d s)…" % expires_in)

    deadline = time.time() + expires_in
    token = None
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise AuthError("login: code expired — run login again")
        time.sleep(min(interval, max(0.0, remaining)))
        if time.time() >= deadline:
            raise AuthError("login: code expired — run login again")
        timeout = min(POLL_TIMEOUT_MAX, max(1.0, deadline - time.time()))
        try:
            status, body = _request("POST", base + "/v1/auth/device/poll", timeout,
                                    payload={"device_code": device_code})
        except _NetError:
            raise AuthError("hub unreachable at %s" % base)
        if status == 428:                                    # authorization_pending
            continue
        if status == 429:                                    # slow_down
            interval += SLOW_DOWN_STEP
            continue
        if status == 410:
            raise AuthError("login: code expired — run login again")
        if status == 403:
            raise AuthError("login: denied in the portal")
        if status == 200:
            token = _json(body, "login: poll returned unparseable JSON").get("token")
            break
        raise AuthError("login: poll refused with HTTP %d" % status)

    _store_token(home, token)
    del token                                                # out of this frame at once
    # Keys before the verdict: a token nobody can check is not a login.
    fetch_jwks(home, base)
    fetch_revoked(home, base)
    ok, reason, claims = tok.verdict(home)
    if not ok:
        raise AuthError("login: the stored token does not verify — %s" % reason)
    return claims


# ---------------------------------------------------------------- §2 refresh, keys

def refresh(home, base=None, timeout=2.0):
    """§2. Rotate only a token that is still valid and inside its last 7 days. Never raises.

    A refused, malformed or unverifiable rotation leaves the old token exactly where it was:
    the failure mode of a refresh must never be 'now you have no identity'."""
    try:
        base = (base or default_base()).rstrip("/")
        tok = _token_module()
        ok, _reason, claims = tok.verdict(home)
        if not ok or not isinstance(claims, dict):
            return False
        exp = claims.get("exp")
        if not isinstance(exp, int) or exp - time.time() >= REFRESH_WINDOW:
            return False                                     # nothing to do, and that is fine
        current = tok.read_token(home)
        if not current:
            return False
        status, body = _request("POST", base + "/v1/auth/refresh", timeout,
                                payload={}, token=current)
        if status != 200:
            return False
        fresh = json.loads(body.decode("utf-8")).get("token")
        if not isinstance(fresh, str) or not fresh.strip():
            return False
        if fresh.strip() == current.strip():
            return False
        _store_token(home, fresh)
        ok2, _r2, _c2 = tok.verdict(home)
        if not ok2:
            _write_private(token_path(home), current.strip() + "\n", 0o600)   # put it back
            return False
        return True
    except Exception:                                        # noqa: BLE001 — silent by contract
        return False


def fetch_jwks(home, base=None, timeout=2.0):
    """§2 keys. Cache `{keys:[…]}` at HOME/atlas-jwks.json. False, silently, on any failure."""
    try:
        base = (base or default_base()).rstrip("/")
        status, body = _request("GET", base + "/.well-known/atlas-jwks.json", timeout)
        if status != 200:
            return False
        obj = json.loads(body.decode("utf-8"))
        if not isinstance(obj, dict) or not isinstance(obj.get("keys"), list):
            return False                                     # never cache junk over good keys
        _write_private(jwks_path(home), json.dumps(obj, sort_keys=True) + "\n", 0o600)
        return True
    except Exception:                                        # noqa: BLE001
        return False


def fetch_revoked(home, base=None, timeout=2.0):
    """§4. Cache `{jti:[…], sub:[…], as_of}` at HOME/atlas-revoked.json. Auth: any valid token.

    §4 also says the quiet part: there is NO offline revocation. A machine that never gets
    here keeps working until exp, and this function returning False is exactly that case."""
    try:
        base = (base or default_base()).rstrip("/")
        try:
            current = _token_module().read_token(home)
        except Exception:                                    # noqa: BLE001
            current = None
        status, body = _request("GET", base + "/v1/auth/revoked", timeout, token=current)
        if status != 200:
            return False
        obj = json.loads(body.decode("utf-8"))
        if not isinstance(obj, dict) or not isinstance(obj.get("jti"), list) \
           or not isinstance(obj.get("sub"), list):
            return False
        _write_private(revoked_path(home), json.dumps(obj, sort_keys=True) + "\n", 0o600)
        return True
    except Exception:                                        # noqa: BLE001
        return False


def sessionstart(home, base=None, budget_ms=2000):
    """The hook's entry point: refresh + revoked + jwks inside ONE wall-clock budget.

    Returns a dict of what happened (for tests); the CLI prints none of it. A hook that
    blocks a session start is worse than a hook that skips a cache fetch, so every step is
    given only the budget that is LEFT and a step with no budget left is simply not made."""
    base = (base or default_base()).rstrip("/")
    deadline = time.time() + max(0.0, budget_ms / 1000.0)
    done = {"refresh": False, "revoked": False, "jwks": False}
    for name, fn in (("refresh", refresh), ("revoked", fetch_revoked), ("jwks", fetch_jwks)):
        left = deadline - time.time()
        if left <= 0.05:
            break
        try:
            done[name] = fn(home, base, timeout=left)
        except Exception:                                    # noqa: BLE001 — never raises
            done[name] = False
    return done


# ---------------------------------------------------------------- CLI

def _claims_line(claims):
    prj = claims.get("prj")
    if isinstance(prj, list):
        prj = ",".join(str(p) for p in prj)
    exp = claims.get("exp")
    when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp)) if isinstance(exp, int) else "?"
    return "atlas-token: ok · sub %s · seat %s · prj %s · exp %s" % (
        claims.get("sub"), claims.get("seat"), prj, when)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="atlas_auth.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    for name in ("login", "refresh", "jwks", "revoked", "sessionstart"):
        p = sub.add_parser(name)
        p.add_argument("--base", default=None)
        p.add_argument("--home", default=None)
        if name == "sessionstart":
            p.add_argument("--budget-ms", type=int, default=2000)
    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_usage(sys.stderr)
        return EXIT_NO_VALID_KEY
    home = args.home or notrest_home()
    base = args.base

    if args.cmd == "login":
        try:
            claims = device_login(home, base, out=sys.stderr)
        except AuthError as exc:
            sys.stderr.write("RED %s\n" % exc.reason)
            return EXIT_NO_VALID_KEY
        except KeyboardInterrupt:
            sys.stderr.write("RED login: interrupted\n")
            return EXIT_NO_VALID_KEY
        print(_claims_line(claims))
        return EXIT_OK

    if args.cmd == "sessionstart":
        try:
            sessionstart(home, base, args.budget_ms)
        except Exception:                                    # noqa: BLE001 — a hook never fails
            pass
        return EXIT_OK                                       # always 0, nothing on stdout

    fn = {"refresh": refresh, "jwks": fetch_jwks, "revoked": fetch_revoked}[args.cmd]
    return EXIT_OK if fn(home, base) else 1                  # silent by contract


if __name__ == "__main__":
    sys.exit(main())
