#!/usr/bin/env python3
"""atlas_token — the identity half of Atlas, on the estate side.

WHAT THIS IS. One Ed25519-signed token (IDENTITY-CONTRACT.md §2) admits the harness on
this machine, authenticates the bank's push, and attributes every snapshot to a user and
a seat. This module is the local half: it finds the token, works out what machine this
is, and asks the vendored verifier — offline, in pure python, with no network and no
third-party import — whether the token admits THIS machine RIGHT NOW. Every failure is
the plugin's exit 7, the same one the access ring returns today.

THE DIVISION OF LABOUR, stated once so neither half drifts:

  · `vendor/verify_token.py` is Atlas's file, vendored BYTE-EXACT (its first line is the
    license line; it is never edited here — if it does not fit, it gets wrapped). It owns
    the rule set and the reason strings. This module never re-implements a check it makes
    and never decorates a reason it returns: `verdict()` hands back the verifier's
    one-fact string verbatim.
  · This module owns the PATHS (which file holds the token, which holds the caches),
    the MACHINE FINGERPRINT, and the order in which the two are consulted. Those are the
    plugin's business, and the hub only ever sees the fingerprint as an opaque string.

THE FINGERPRINT (RULINGS-2026-09-06.md §1). sha256 of a machine id that is, in order:
Linux `/etc/machine-id` (fallback `/var/lib/dbus/machine-id`) → macOS `IOPlatformUUID`
from `ioreg` → a random 32-byte id generated ONCE and persisted 0600 at
`${NOTREST_HOME}/machine-id` (the container case, and only that case). **The hostname is
never an input** — the portal shows the human-chosen machine name separately, and a
laptop that gets renamed must not thereby lose its token.

SECRETS BY PATH, NEVER BY VALUE. The token is read from a file and passed to the verifier
in memory. It is never printed, logged, put in argv or an env value, and never appears in
this module's output on any path — `check` prints a sentinel built from three claims,
`claims` prints the claims (which do not contain the token), and every failure prints one
fact. The fixture greps for the token's own bytes in every stream to keep that true.

VERBS AND EXIT CODES:

  atlas_token.py check [--quiet] [--home H] [--now N]
      0 = a valid token admits this machine; stdout is exactly
          atlas-token: ok sub=<sub> seat=<seat> exp=<iso>
      7 = no valid token; stdout is exactly `RED <reason>`
  atlas_token.py fingerprint [--home H]     this machine's fingerprint, exit 0
  atlas_token.py claims [--home H] [--now N]  the claims as JSON on 0, `RED <reason>` on 7

  0  ok · 2  usage · 7  no valid key/token   (the plugin's codes, unchanged)

IMPORT COST. The hooks call this on every session, inside a ~100 ms budget, so the
verifier — which builds a window table and self-checks the curve constants at import — is
loaded LAZILY, on the first call that actually needs it. `import atlas_token` therefore
costs a few stdlib imports and nothing else, and a process that only wants the
fingerprint never pays for the arithmetic.
"""

import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NO_VALID_KEY = 7

TOKEN_FILE = "atlas-token"          # the identity token (RULING §2)
LEGACY_KEY_FILE = "access-key"      # the ring key today; may hold a JWT in transition
JWKS_CACHE = "atlas-jwks.json"
REVOKED_CACHE = "atlas-revoked.json"
MACHINE_ID_FILE = "machine-id"      # containers only — see machine_id()

RING_PREFIX = "nrk_"

# The release pin (IDENTITY-CONTRACT.md §2, "the plugin pins the current public key").
# Empty until the hub publishes a signing kid: an empty pin is honest — `verdict` says
# `keys: none pinned or cached` rather than trusting whatever a cache happens to hold.
PINNED_JWKS = {"keys": []}

_HERE = os.path.dirname(os.path.abspath(__file__))
_VERIFY_TOKEN = None                # the lazily-loaded vendored verifier
_MID_CACHE = {}                     # home -> machine id, one probe per process

_IOPLATFORM_RE = re.compile(r'"IOPlatformUUID"\s*=\s*"([^"]+)"')
_B64URL_OK = re.compile(r"^[A-Za-z0-9_-]+$")


# ---------------------------------------------------------------------------
# paths and small readers — none of these raise; a hook must not die on a file
# ---------------------------------------------------------------------------
def notrest_home():
    """`${NOTREST_HOME:-~/.notrest}` — the SAME resolution as atlas.py's notrest_home().

    Deliberately identical, expanduser and all: two answers to one gate question is worse
    than a closed gate, and a machine that sets NOTREST_HOME=~/alt must not get "the hook
    says licensed, atlas_token says no"."""
    return os.path.expanduser(os.environ.get("NOTREST_HOME") or "~/.notrest")


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (OSError, ValueError):
        return None


def _read_json(path):
    raw = _read(path)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _first_value(text):
    """The first non-empty, non-comment line, stripped. `` for nothing usable."""
    for line in (text or "").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def looks_like_token(value):
    """True when `value` is an Atlas token rather than a ring key.

    The rule the seat fixed: exactly two dots, and a header that parses as an object with
    `alg` EdDSA. Cheap, does not need the verifier, and errs toward "ring" — a ring key
    misread as a token would be verified and reported `token: malformed`, which is a lie
    about which credential the machine holds."""
    if not isinstance(value, str):
        return False
    value = value.strip()
    if value.count(".") != 2:
        return False
    head = value.split(".", 1)[0]
    if not head or not _B64URL_OK.match(head) or len(head) % 4 == 1:
        return False
    try:
        obj = json.loads(base64.urlsafe_b64decode(
            head + "=" * (-len(head) % 4)).decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return False
    return isinstance(obj, dict) and obj.get("alg") == "EdDSA"


def read_token(home=None):
    """The compact JWT for this machine, or None.

    `${HOME}/atlas-token` first, whatever it holds — a garbled identity file must report
    the verifier's `token: malformed`, not the softer `token: absent`. Then the legacy
    `${HOME}/access-key`, but ONLY if it holds a JWT: an `nrk_…` there is the access ring,
    which is a different gate and not this module's business."""
    home = home or notrest_home()
    value = _first_value(_read(os.path.join(home, TOKEN_FILE)))
    if value:
        return value
    legacy = _first_value(_read(os.path.join(home, LEGACY_KEY_FILE)))
    if legacy and looks_like_token(legacy):
        return legacy
    return None


# ---------------------------------------------------------------------------
# the machine fingerprint (RULINGS-2026-09-06.md §1)
# ---------------------------------------------------------------------------
def _linux_machine_id():
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        value = (_read(path) or "").strip()
        if value:
            return value
    return None


def _macos_machine_id():
    if sys.platform != "darwin":
        return None
    try:
        proc = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    match = _IOPLATFORM_RE.search(proc.stdout.decode("utf-8", "replace"))
    return match.group(1).strip() if match else None


def _persisted_machine_id(home):
    """The container case: 32 random bytes, hex, 0600, written ONCE.

    Written with O_EXCL so two hooks racing at first session cannot each mint an id and
    give this machine two fingerprints; the loser re-reads the winner's file."""
    path = os.path.join(home, MACHINE_ID_FILE)
    value = (_read(path) or "").strip()
    if value:
        return value
    minted = binascii.hexlify(os.urandom(32)).decode("ascii")
    try:
        os.makedirs(home, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, (minted + "\n").encode("ascii"))
        finally:
            os.close(fd)
        os.chmod(path, 0o600)
        return minted
    except OSError:
        value = (_read(path) or "").strip()
        return value or minted


def machine_id(home=None):
    """This machine's id, per the RULING's order. Never the hostname."""
    home = home or notrest_home()
    if home in _MID_CACHE:
        return _MID_CACHE[home]
    value = _linux_machine_id() or _macos_machine_id() or _persisted_machine_id(home)
    _MID_CACHE[home] = value
    return value


def fingerprint(home=None):
    """sha256(machine_id) hex — what the hub stores and compares as an opaque string."""
    return hashlib.sha256(machine_id(home).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# the vendored verifier, keys, revocation
# ---------------------------------------------------------------------------
def _verifier():
    """Import `vendor/verify_token.py` lazily; by package name, else by path.

    By path is the fallback that matters: a hook may import this module from a sys.path
    that already owns the name `vendor`, and a wrong `vendor.verify_token` must not be
    mistaken for Atlas's — hence the shape check before it is accepted."""
    global _VERIFY_TOKEN
    if _VERIFY_TOKEN is not None:
        return _VERIFY_TOKEN
    module = None
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    try:
        from vendor import verify_token as candidate  # noqa: F401
        if hasattr(candidate, "verify") and hasattr(candidate, "TokenError"):
            module = candidate
    except ImportError:
        module = None
    if module is None:
        import importlib.util
        path = os.path.join(_HERE, "vendor", "verify_token.py")
        spec = importlib.util.spec_from_file_location("atlas_verify_token", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    _VERIFY_TOKEN = module
    return module


def load_keys(home=None):
    """{kid: 32 raw bytes} — the release pin UNION the SessionStart JWKS cache.

    The cache is merged first and the pin written over it, so a poisoned cache cannot
    replace a pinned kid; a cache that is missing, unreadable, not JSON, or malformed is
    simply not there. An empty result is the caller's `keys: none pinned or cached`."""
    home = home or notrest_home()
    keys = {}
    for source in (_read_json(os.path.join(home, JWKS_CACHE)), PINNED_JWKS):
        if not isinstance(source, (dict, list)):
            continue
        try:
            keys.update(_verifier().keys_from_jwks(source))
        except Exception:
            # Malformed JWKS (ValueError), and also a vendor/ that is missing or
            # unloadable: a broken install must read as "this machine has no keys" and
            # exit 7, never as a traceback out of a hook.
            continue
    return keys


def load_revoked(home=None):
    """The cached revocation list as `{jti: [...], sub: [...]}`, or None.

    §4: there is no offline revocation. A machine with no cache is not "clean", it is
    UNINFORMED — it keeps working until `exp` and no longer, and this function saying
    None is exactly that admission."""
    home = home or notrest_home()
    obj = _read_json(os.path.join(home, REVOKED_CACHE))
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        return {"jti": [x for x in obj if isinstance(x, str)], "sub": []}
    return None


def verdict(home=None, now=None):
    """(ok, reason, claims) — the one call every hook makes.

    Order: token → keys → verify. `reason` is the verifier's one-fact string verbatim, or
    `token: absent` / `keys: none pinned or cached` for the two conditions the verifier
    never sees. On success it is `ok`."""
    home = home or notrest_home()
    token = read_token(home)
    if not token:
        return (False, "token: absent", None)
    keys = load_keys(home)
    if not keys:
        return (False, "keys: none pinned or cached", None)
    try:
        verifier = _verifier()
    except Exception:
        return (False, "keys: none pinned or cached", None)
    try:
        claims = verifier.verify(token, keys, now=now,
                                 expect_mid=fingerprint(home),
                                 revoked=load_revoked(home))
    except verifier.TokenError as exc:
        return (False, exc.reason, None)
    except Exception:
        # A hook may never die on a credential file. Anything the verifier did not
        # anticipate is a token this machine cannot use, said in its own vocabulary.
        return (False, "token: malformed", None)
    return (True, "ok", claims)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _iso(epoch):
    try:
        return datetime.fromtimestamp(int(epoch), timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError, TypeError):
        return "?"


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(
        prog="atlas_token.py",
        description="Verify the Atlas identity token for this machine, offline.")
    ap.add_argument("verb", choices=("check", "fingerprint", "claims"))
    ap.add_argument("--home", default=None,
                    help="the private store (default: ${NOTREST_HOME:-~/.notrest})")
    ap.add_argument("--now", type=int, default=None,
                    help="epoch seconds to verify at (default: the clock)")
    ap.add_argument("--quiet", action="store_true",
                    help="say nothing; the exit code is the whole answer")
    args = ap.parse_args(argv)
    home = args.home or notrest_home()

    def say(line):
        if not args.quiet:
            sys.stdout.write(line + "\n")

    if args.verb == "fingerprint":
        say(fingerprint(home))
        return EXIT_OK

    ok, reason, claims = verdict(home, now=args.now)
    if not ok:
        say("RED %s" % reason)
        return EXIT_NO_VALID_KEY
    if args.verb == "claims":
        say(json.dumps(claims, indent=2, sort_keys=True))
    else:
        say("atlas-token: ok sub=%s seat=%s exp=%s"
            % (claims.get("sub"), claims.get("seat"), _iso(claims.get("exp"))))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
