"""mockhub.py — a mock Atlas hub for notrest fixtures (docket 4.9, lane A1).

One stdlib `http.server` on 127.0.0.1 that plays the Atlas hub well enough for
fixtures to drive the device-login flow, token refresh, revocation, and the
snapshot/board push endpoints without ever touching the network. Contract:
briefs/atlas-contract/IDENTITY-CONTRACT.md sections 1, 2, 4 and
briefs/atlas-contract/HUB-CONTRACT.md section 2.

/usr/bin/python3 (3.9), stdlib only. The one exception: python cannot sign
Ed25519, so token minting shells out to `node -e` exactly as
briefs/atlas-contract/kit/test-verify-token.sh's fixture generator does
(`crypto.sign(null, ..., key)`). If node is missing this exits 6.

Never logs or prints a bearer value, a token, or a private key.

Usage:
    mockhub.py --port 8901 [--auto-approve-after 2] [--mode ok|expired|denied|slow] [--print-port]
    mockhub.py --selftest
"""

import argparse
import base64
import hashlib
import http.server
import importlib.util
import json
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

EXIT_NODE_REQUIRED = 6

ISS = "https://atlas.not.rest"
AUD = "notrest-plugin"

SNAPSHOT_LIMIT = 2 * 1024 * 1024   # 2 MiB, IDENTITY-CONTRACT.md section 3
BOARD_LIMIT = 4 * 1024 * 1024      # 4 MB, IDENTITY-CONTRACT.md section 3

# ---------------------------------------------------------------------------
# node shell-outs — the only non-stdlib-python step (Ed25519 signing)
# ---------------------------------------------------------------------------

_KEYGEN_JS = r"""
const crypto = require('crypto');
const kp = crypto.generateKeyPairSync('ed25519');
process.stdout.write(JSON.stringify({
  pem: kp.privateKey.export({ type: 'pkcs8', format: 'pem' }),
  jwk: kp.publicKey.export({ format: 'jwk' })
}));
"""

_SIGN_JS = r"""
const crypto = require('crypto');
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { data += c; });
process.stdin.on('end', () => {
  const req = JSON.parse(data);
  const priv = crypto.createPrivateKey(req.pem);
  const sig = crypto.sign(null, Buffer.from(req.input, 'utf8'), priv);
  const b64u = sig.toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  process.stdout.write(b64u);
});
"""


def _check_node():
    """Exit 6 with one line if node >= 18 is not available to sign with."""
    import shutil

    node = shutil.which("node")
    ok = False
    if node:
        try:
            proc = subprocess.run(
                [node, "-p", "process.versions.node.split('.')[0]"],
                capture_output=True, text=True, timeout=10,
            )
            if proc.returncode == 0:
                ok = int(proc.stdout.strip()) >= 18
        except Exception:
            ok = False
    if not ok:
        sys.stderr.write("mockhub: node >= 18 required to sign\n")
        sys.exit(EXIT_NODE_REQUIRED)


def _node_keygen():
    proc = subprocess.run(["node", "-e", _KEYGEN_JS],
                           capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        sys.stderr.write("mockhub: node >= 18 required to sign\n")
        sys.exit(EXIT_NODE_REQUIRED)
    return json.loads(proc.stdout)


def _node_sign(pem, signing_input):
    proc = subprocess.run(
        ["node", "-e", _SIGN_JS],
        input=json.dumps({"pem": pem, "input": signing_input}),
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError("mockhub: sign failed: %s" % proc.stderr.strip())
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError("mockhub: sign produced no output")
    return out


def _b64u(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mock_ts():
    now = time.time()
    ms = int((now - int(now)) * 1000)
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime(now)) + ("%03dZ" % ms)


def _iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def _find_repo_file(relpath):
    here = Path(__file__).resolve()
    for parent in [here.parent] + list(here.parents):
        candidate = parent / relpath
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# the hub
# ---------------------------------------------------------------------------


class MockHub(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_cls, mode="ok", auto_approve_after=None):
        super().__init__(server_address, handler_cls)
        self.lock = threading.Lock()
        self.mode = mode
        self.auto_approve_after = auto_approve_after
        self.devices = {}          # device_code -> {mid, seat, approved, poll_count, slowed, token}
        self.revoked_jti = set()
        self.revoked_sub = set()
        self.issued_tokens = {}    # token -> claims
        self.snapshots = {}        # project -> {wire, hash, head, stored}
        self.boards = {}           # project -> bytes
        keys = _node_keygen()
        self.priv_pem = keys["pem"]
        self.pub_jwk = keys["jwk"]
        self.kid = "mock-" + secrets.token_hex(4)

    def build_claims(self, mid, seat="mock-seat", sub="mock@atlas.test",
                      prj=None, scp=None, jti=None):
        now = int(time.time())
        return {
            "iss": ISS,
            "aud": AUD,
            "sub": sub,
            "seat": seat,
            "mid": mid,
            "prj": prj if prj is not None else ["*"],
            "scp": scp if scp is not None else ["harness", "push", "view"],
            "jti": jti or str(uuid.uuid4()),
            "iat": now,
            "exp": now + 30 * 86400,
        }

    def mint_token(self, claims):
        header = {"alg": "EdDSA", "typ": "JWT", "kid": self.kid}
        h = _b64u(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        p = _b64u(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
        signing_input = h + "." + p
        sig = _node_sign(self.priv_pem, signing_input)
        return signing_input + "." + sig


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "mockhub/1.0"

    def log_message(self, fmt, *args):
        pass  # never log requests (bearer values ride in headers)

    # -- plumbing -------------------------------------------------------

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_body(self, limit=None):
        length = int(self.headers.get("Content-Length") or 0)
        if limit is not None and length > limit:
            try:
                self.rfile.read(min(length, limit))
            except Exception:
                pass
            return None, length
        data = self.rfile.read(length) if length else b""
        return data, length

    def _bearer(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        val = auth[len("Bearer "):].strip()
        return val or None

    def _push_authorized(self, bearer, project):
        if not bearer:
            return False
        if bearer == "mock-ingest-%s" % project:
            return True
        srv = self.server
        with srv.lock:
            claims = srv.issued_tokens.get(bearer)
        return bool(claims and "push" in (claims.get("scp") or []))

    # -- dispatch ---------------------------------------------------------

    def do_POST(self):
        try:
            self._dispatch_post()
        except Exception as exc:  # never take the whole hub down
            self._send_json(500, {"error": "internal: %r" % (exc,)})

    def do_GET(self):
        try:
            self._dispatch_get()
        except Exception as exc:
            self._send_json(500, {"error": "internal: %r" % (exc,)})

    def _dispatch_post(self):
        path = self.path.split("?", 1)[0]
        if path == "/v1/auth/device/start":
            return self._device_start()
        if path == "/v1/auth/device/poll":
            return self._device_poll()
        if path == "/v1/auth/refresh":
            return self._refresh()
        if path == "/_mock/approve":
            return self._mock_approve()
        if path == "/_mock/revoke":
            return self._mock_revoke()
        if path.startswith("/v1/snapshot/") and path.count("/") == 3:
            return self._snapshot_push(path[len("/v1/snapshot/"):])
        if path.startswith("/v1/board/") and path.count("/") == 3:
            return self._board_push(path[len("/v1/board/"):])
        self._send_json(404, {"error": "not_found"})

    def _dispatch_get(self):
        path = self.path.split("?", 1)[0]
        if path == "/v1/auth/revoked":
            return self._revoked_list()
        if path == "/.well-known/atlas-jwks.json":
            return self._jwks()
        if path.startswith("/v1/snapshot/") and path.count("/") == 3:
            return self._snapshot_get(path[len("/v1/snapshot/"):])
        self._send_json(404, {"error": "not_found"})

    # -- device flow (IDENTITY-CONTRACT.md section 1) --------------------

    def _device_start(self):
        data, _ = self._read_body()
        try:
            obj = json.loads(data or b"{}")
        except ValueError:
            return self._send_json(400, {"error": "body: not parseable JSON"})
        machine = obj.get("machine") or {}
        mid = machine.get("fp") or ""
        seat = machine.get("name") or "mock-seat"
        device_code = secrets.token_urlsafe(16)
        user_code = "%s-%s" % (secrets.token_hex(2).upper(), secrets.token_hex(2).upper())
        srv = self.server
        with srv.lock:
            srv.devices[device_code] = {
                "mid": mid, "seat": seat, "approved": False,
                "poll_count": 0, "slowed": False, "token": None,
            }
            port = srv.server_address[1]
        self._send_json(200, {
            "device_code": device_code,
            "user_code": user_code,
            "verification_uri": "http://127.0.0.1:%d/activate" % port,
            "interval": 1,
            "expires_in": 30,
        })

    def _device_poll(self):
        data, _ = self._read_body()
        try:
            obj = json.loads(data or b"{}")
        except ValueError:
            return self._send_json(400, {"error": "body: not parseable JSON"})
        device_code = obj.get("device_code")
        srv = self.server
        with srv.lock:
            rec = srv.devices.get(device_code)
            if rec is None:
                result = (400, {"error": "unknown_device_code"})
            else:
                rec["poll_count"] += 1
                if srv.mode == "expired":
                    result = (410, {"error": "expired_token"})
                elif srv.mode == "denied":
                    result = (403, {"error": "access_denied"})
                elif srv.mode == "slow" and not rec["slowed"]:
                    rec["slowed"] = True
                    result = (429, {"error": "slow_down"})
                else:
                    if (not rec["approved"] and srv.auto_approve_after is not None
                            and rec["poll_count"] >= srv.auto_approve_after):
                        rec["approved"] = True
                    if not rec["approved"]:
                        result = (428, {"error": "authorization_pending"})
                    else:
                        if rec["token"] is None:
                            claims = srv.build_claims(rec["mid"], seat=rec["seat"])
                            rec["token"] = srv.mint_token(claims)
                            srv.issued_tokens[rec["token"]] = claims
                        token = rec["token"]
                        exp = srv.issued_tokens[token]["exp"]
                        port = srv.server_address[1]
                        result = (200, {
                            "token": token,
                            "expires_at": exp,
                            "jwks": "http://127.0.0.1:%d/.well-known/atlas-jwks.json" % port,
                            "kid": srv.kid,
                        })
        self._send_json(*result)

    def _mock_approve(self):
        data, _ = self._read_body()
        try:
            obj = json.loads(data or b"{}")
        except ValueError:
            return self._send_json(400, {"error": "body: not parseable JSON"})
        device_code = obj.get("device_code")
        srv = self.server
        with srv.lock:
            rec = srv.devices.get(device_code)
            if rec is not None:
                rec["approved"] = True
        self._send_json(200, {"approved": True})

    # -- token refresh / revocation (IDENTITY-CONTRACT.md sections 2, 4) --

    def _refresh(self):
        self._read_body()
        bearer = self._bearer()
        srv = self.server
        with srv.lock:
            claims = srv.issued_tokens.get(bearer) if bearer else None
            if claims is None:
                result = None
            else:
                new_claims = srv.build_claims(
                    claims["mid"], seat=claims["seat"], sub=claims["sub"],
                    prj=claims.get("prj"), scp=claims.get("scp"),
                )
                new_token = srv.mint_token(new_claims)
                srv.issued_tokens[new_token] = new_claims
                result = (200, {"token": new_token, "expires_at": new_claims["exp"]})
        if result is None:
            return self._send_json(401, {"error": "authorization: bad bearer"})
        self._send_json(*result)

    def _mock_revoke(self):
        data, _ = self._read_body()
        try:
            obj = json.loads(data or b"{}")
        except ValueError:
            return self._send_json(400, {"error": "body: not parseable JSON"})
        jti = obj.get("jti")
        sub = obj.get("sub")
        srv = self.server
        with srv.lock:
            if jti:
                srv.revoked_jti.add(jti)
            if sub:
                srv.revoked_sub.add(sub)
        self._send_json(200, {"revoked": True})

    def _revoked_list(self):
        srv = self.server
        with srv.lock:
            jtis = sorted(srv.revoked_jti)
            subs = sorted(srv.revoked_sub)
        self._send_json(200, {"jti": jtis, "sub": subs, "as_of": _iso_now()})

    def _jwks(self):
        srv = self.server
        self._send_json(200, {"keys": [
            {"kty": "OKP", "crv": "Ed25519", "kid": srv.kid, "x": srv.pub_jwk["x"]},
        ]})

    # -- push (HUB-CONTRACT.md section 2, IDENTITY-CONTRACT.md section 3) -

    def _snapshot_push(self, project):
        data, length = self._read_body(limit=SNAPSHOT_LIMIT)
        if data is None:
            return self._send_json(413, {
                "error": "body: %d bytes exceeds limit %d" % (length, SNAPSHOT_LIMIT)})
        bearer = self._bearer()
        if not self._push_authorized(bearer, project):
            return self._send_json(401, {"error": "authorization: bad bearer"})
        try:
            wire = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._send_json(400, {"error": "body: not parseable JSON"})
        if not isinstance(wire, dict):
            return self._send_json(400, {"error": "body: not parseable JSON"})
        sv = wire.get("schema_version")
        if sv not in ("atlas-hub/0", "atlas-hub/1"):
            return self._send_json(422, {
                "error": "schema_version: expected one of \"atlas-hub/0\" | \"atlas-hub/1\", got %r" % (sv,)})
        nodes = wire.get("nodes") or []
        for i, node in enumerate(nodes):
            parts = (node or {}).get("parts") or []
            for j, part in enumerate(parts):
                if part.get("evidence") == "proven" and not part.get("check"):
                    return self._send_json(422, {
                        "error": "nodes[%d].parts[%d].check: evidence \"proven\" requires a non-empty check" % (i, j)})
        body_hash = hashlib.sha256(data).hexdigest()
        head = wire.get("head")
        srv = self.server
        with srv.lock:
            prev = srv.snapshots.get(project)
            if prev is not None and prev["head"] == head and prev["hash"] == body_hash:
                result = (200, {"stored": prev["stored"], "idempotent": True})
            else:
                stored_key = "snap:%s:%s" % (project, _mock_ts())
                srv.snapshots[project] = {
                    "wire": wire, "hash": body_hash, "head": head, "stored": stored_key}
                result = (201, {"stored": stored_key, "project": project, "nodes": len(nodes)})
        self._send_json(*result)

    def _board_push(self, project):
        data, length = self._read_body(limit=BOARD_LIMIT)
        if data is None:
            return self._send_json(413, {
                "error": "body: %d bytes exceeds limit %d" % (length, BOARD_LIMIT)})
        bearer = self._bearer()
        if not self._push_authorized(bearer, project):
            return self._send_json(401, {"error": "authorization: bad bearer"})
        srv = self.server
        with srv.lock:
            srv.boards[project] = data
        self._send_json(201, {"stored": "board:%s" % project, "project": project, "bytes": len(data)})

    def _snapshot_get(self, project):
        srv = self.server
        with srv.lock:
            rec = srv.snapshots.get(project)
            wire = rec["wire"] if rec else None
        if wire is None:
            return self._send_json(404, {"error": "not_found"})
        self._send_json(200, wire)


# ---------------------------------------------------------------------------
# --selftest
# ---------------------------------------------------------------------------


def _http(method, url, body=None, headers=None):
    headers = dict(headers or {})
    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
            code = resp.getcode()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        code = exc.code
    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except ValueError:
        parsed = raw
    return code, parsed


def _start(mode="ok", auto_approve_after=None):
    httpd = MockHub(("127.0.0.1", 0), _Handler, mode=mode, auto_approve_after=auto_approve_after)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, "http://127.0.0.1:%d" % port


def _stop(httpd):
    httpd.shutdown()
    httpd.server_close()


def _run_selftest():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    # -- default "ok" mode: the full happy-path plus the refusal arms -----
    httpd, base = _start(mode="ok")
    try:
        machine_fp = hashlib.sha256(b"mockhub-selftest-machine").hexdigest()
        code, obj = _http("POST", base + "/v1/auth/device/start", {
            "client": "notrest-plugin", "version": "4.9.0",
            "machine": {"name": "selftest-seat", "fp": machine_fp},
        })
        check("device/start 200", code == 200 and isinstance(obj, dict) and obj.get("device_code"),
              str((code, obj)))
        check("device/start fields", obj.get("interval") == 1 and obj.get("expires_in") == 30
              and obj.get("user_code") and obj.get("verification_uri"), str(obj))
        device_code = obj.get("device_code")

        code, obj = _http("POST", base + "/v1/auth/device/poll", {"device_code": device_code})
        check("poll pending 428", code == 428 and obj.get("error") == "authorization_pending", str((code, obj)))

        code, obj = _http("POST", base + "/_mock/approve", {"device_code": device_code})
        check("mock approve 200", code == 200, str((code, obj)))

        code, obj = _http("POST", base + "/v1/auth/device/poll", {"device_code": device_code})
        check("poll approved 200", code == 200 and obj.get("token") and obj.get("kid") and obj.get("jwks"),
              str((code, obj)))
        token = obj.get("token")
        kid = obj.get("kid")

        code, jwks = _http("GET", base + "/.well-known/atlas-jwks.json")
        check("jwks 200", code == 200 and jwks.get("keys") and jwks["keys"][0].get("kid") == kid, str((code, jwks)))

        verify_path = _find_repo_file("briefs/atlas-contract/kit/verify-token.py")
        verified_ok = False
        verify_detail = "briefs/atlas-contract/kit/verify-token.py not found"
        if verify_path is not None and token:
            try:
                spec = importlib.util.spec_from_file_location("atlas_contract_verify_token", str(verify_path))
                vmod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(vmod)
                keys = vmod.keys_from_jwks(jwks)
                claims = vmod.verify(token, keys, expect_mid=machine_fp)
                verified_ok = claims.get("mid") == machine_fp and claims.get("iss") == ISS
                verify_detail = "claims: %s" % json.dumps(claims, sort_keys=True)
            except Exception as exc:
                verify_detail = "verify raised: %r" % (exc,)
        check("token verifies against contract verify-token.py", verified_ok, verify_detail)

        code, robj = _http("POST", base + "/v1/auth/refresh", body=b"",
                            headers={"Authorization": "Bearer " + (token or "")})
        check("refresh valid bearer 200", code == 200 and robj.get("token") and robj["token"] != token,
              str((code, robj)))
        new_token = robj.get("token")

        code, robj = _http("POST", base + "/v1/auth/refresh", body=b"",
                            headers={"Authorization": "Bearer garbage"})
        check("refresh bad bearer 401", code == 401, str((code, robj)))

        code, robj = _http("GET", base + "/v1/auth/revoked")
        check("revoked list starts empty", code == 200 and robj.get("jti") == [], str((code, robj)))

        payload_seg = new_token.split(".")[1]
        payload_seg += "=" * (-len(payload_seg) % 4)
        new_claims = json.loads(base64.urlsafe_b64decode(payload_seg))
        code, robj = _http("POST", base + "/_mock/revoke", {"jti": new_claims["jti"]})
        check("mock revoke 200", code == 200, str((code, robj)))
        code, robj = _http("GET", base + "/v1/auth/revoked")
        check("revoked list contains jti", code == 200 and new_claims["jti"] in (robj.get("jti") or []),
              str((code, robj)))

        project = "mockproj"
        good_wire = {
            "schema_version": "atlas-hub/1",
            "project": project,
            "stamp": "selftest",
            "taken_at": "2026-09-06T00:00:00Z",
            "playbook": "2.0",
            "head": "abc1234",
            "sources": {"git": "available", "tests": "unknown", "map": "available"},
            "nodes": [{"id": "estate", "kind": "component", "parts": [
                {"id": "p1", "label": "x", "status": "done", "evidence": "proven", "check": "TEST: x"},
            ]}],
            "edges": [],
            "findings": {"count": 0, "recurring": 0},
        }
        ingest_bearer = "mock-ingest-%s" % project
        code, robj = _http("POST", base + "/v1/snapshot/%s" % project, good_wire,
                            headers={"Authorization": "Bearer " + ingest_bearer})
        check("snapshot push 201", code == 201 and robj.get("nodes") == 1, str((code, robj)))

        code, robj = _http("POST", base + "/v1/snapshot/%s" % project, good_wire,
                            headers={"Authorization": "Bearer " + ingest_bearer})
        check("snapshot idempotent 200", code == 200 and robj.get("idempotent") is True, str((code, robj)))

        bad_schema = dict(good_wire)
        bad_schema["schema_version"] = "atlas-hub/9"
        code, robj = _http("POST", base + "/v1/snapshot/%s" % project, bad_schema,
                            headers={"Authorization": "Bearer " + ingest_bearer})
        check("snapshot bad schema_version 422", code == 422 and "schema_version" in (robj.get("error") or ""),
              str((code, robj)))

        no_check = json.loads(json.dumps(good_wire))
        no_check["head"] = "def5678"
        no_check["nodes"][0]["parts"][0]["check"] = ""
        code, robj = _http("POST", base + "/v1/snapshot/%s" % project, no_check,
                            headers={"Authorization": "Bearer " + ingest_bearer})
        check("snapshot proven-without-check 422", code == 422 and "check" in (robj.get("error") or ""),
              str((code, robj)))

        code, robj = _http("POST", base + "/v1/snapshot/%s" % project, "{not json",
                            headers={"Authorization": "Bearer " + ingest_bearer})
        check("snapshot unparseable 400", code == 400, str((code, robj)))

        too_big = dict(good_wire)
        too_big["head"] = "e" * (SNAPSHOT_LIMIT + 16)
        code, robj = _http("POST", base + "/v1/snapshot/%s" % project, too_big,
                            headers={"Authorization": "Bearer " + ingest_bearer})
        check("snapshot over 2MiB 413", code == 413, str((code, robj)))

        code, robj = _http("POST", base + "/v1/snapshot/%s" % project, good_wire, headers={})
        check("snapshot no bearer 401", code == 401, str((code, robj)))

        board_html = "<html><body>selftest board</body></html>"
        code, robj = _http("POST", base + "/v1/board/%s" % project, board_html.encode("utf-8"),
                            headers={"Authorization": "Bearer " + ingest_bearer, "Content-Type": "text/html"})
        check("board push 201", code == 201 and robj.get("bytes") == len(board_html.encode("utf-8")),
              str((code, robj)))

        code, robj = _http("GET", base + "/v1/snapshot/%s" % project)
        check("snapshot get 200", code == 200 and robj.get("head") == good_wire["head"], str((code, robj)))
    finally:
        _stop(httpd)

    # -- --mode expired / denied: unconditional, regardless of approval ---
    for mode, expect_code, expect_err in (("expired", 410, "expired_token"),
                                           ("denied", 403, "access_denied")):
        httpd, base = _start(mode=mode)
        try:
            _, sobj = _http("POST", base + "/v1/auth/device/start", {
                "client": "notrest-plugin", "version": "4.9.0",
                "machine": {"name": "s", "fp": "f"},
            })
            code, robj = _http("POST", base + "/v1/auth/device/poll", {"device_code": sobj.get("device_code")})
            check("mode=%s poll" % mode, code == expect_code and robj.get("error") == expect_err, str((code, robj)))
        finally:
            _stop(httpd)

    # -- --mode slow: 429 once, then normal --------------------------------
    httpd, base = _start(mode="slow", auto_approve_after=1)
    try:
        _, sobj = _http("POST", base + "/v1/auth/device/start", {
            "client": "notrest-plugin", "version": "4.9.0",
            "machine": {"name": "s", "fp": "f"},
        })
        device_code = sobj.get("device_code")
        code1, robj1 = _http("POST", base + "/v1/auth/device/poll", {"device_code": device_code})
        check("mode=slow first poll 429", code1 == 429 and robj1.get("error") == "slow_down", str((code1, robj1)))
        code2, robj2 = _http("POST", base + "/v1/auth/device/poll", {"device_code": device_code})
        check("mode=slow second poll normal", code2 == 200 and robj2.get("token"), str((code2, robj2)))
    finally:
        _stop(httpd)

    # -- --auto-approve-after N -------------------------------------------
    httpd, base = _start(mode="ok", auto_approve_after=2)
    try:
        _, sobj = _http("POST", base + "/v1/auth/device/start", {
            "client": "notrest-plugin", "version": "4.9.0",
            "machine": {"name": "s", "fp": "f"},
        })
        device_code = sobj.get("device_code")
        c1, r1 = _http("POST", base + "/v1/auth/device/poll", {"device_code": device_code})
        check("auto-approve-after: poll 1 still pending", c1 == 428, str((c1, r1)))
        c2, r2 = _http("POST", base + "/v1/auth/device/poll", {"device_code": device_code})
        check("auto-approve-after: poll 2 approved", c2 == 200 and r2.get("token"), str((c2, r2)))
    finally:
        _stop(httpd)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        line = "ok  " if ok else "FAIL"
        suffix = (": " + detail) if not ok and detail else ""
        print("%s %s%s" % (line, name, suffix))
    print("mockhub selftest: %d passed, %d failed" % (passed, len(failed)))
    return 0 if not failed else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mockhub.py", description="Mock Atlas hub for notrest fixtures.")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--auto-approve-after", type=int, default=None)
    ap.add_argument("--mode", choices=["ok", "expired", "denied", "slow"], default="ok")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--print-port", action="store_true")
    args = ap.parse_args(argv)

    _check_node()

    if args.selftest:
        return _run_selftest()

    port = args.port if args.port is not None else 0
    httpd = MockHub(("127.0.0.1", port), _Handler, mode=args.mode,
                     auto_approve_after=args.auto_approve_after)
    if args.print_port:
        print(httpd.server_address[1])
        sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _stop(httpd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
