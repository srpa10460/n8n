"""Dev server: static app + sync endpoints (stdlib only). It holds NO per-operation domain API:
all editing runs on the device (offline-first). The server only receives, verifies and stores.
Binds 127.0.0.1. Data dir: $HOA_DATA or ./data.   Run: python3 -m hoa_field.server [port]

Sync protocol (idempotent; every step can be repeated):
  POST /api/sync/begin   package + base_rev  -> verifies hash with the SAME core, detects conflict, stages, lists missing assets
  PUT  /api/sync/asset   one photo, X-Sha256 verified, atomic write
  POST /api/sync/commit  checks all assets present+hash, then rev+=1 (previous rev archived, never deleted)
Auth: DEV-ONLY signed short-lived token (HOA_DEV_AUTH=1). Real authentication is NOT designed yet.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .catalog import Catalog
from .diff import diff_snapshots
from .engine import ID_RE, call

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent
MAX_ASSET = 8 * 1024 * 1024
CT = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
      ".wasm": "application/wasm", ".py": "text/plain; charset=utf-8", ".zip": "application/zip",
      ".webmanifest": "application/manifest+json", ".png": "image/png", ".svg": "image/svg+xml", ".map": "application/json"}


class ApiError(Exception):
    def __init__(self, msg, code=400, extra=None):
        super().__init__(msg)
        self.code, self.extra = code, extra or {}


def _atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Store:
    def __init__(self, data: Path, dev_auth: bool):
        self.data, self.dev_auth = data, dev_auth
        self.lock = threading.RLock()
        self.secret = secrets.token_bytes(32)
        self.cat_path = data / "server_catalog.json"
        self.catalog = Catalog.load(self.cat_path) if self.cat_path.exists() else Catalog()

    # --- auth (dev only)
    def make_token(self, user: str, ttl: int) -> str:
        body = base64.urlsafe_b64encode(json.dumps({"u": user, "exp": time.time() + ttl}).encode()).decode()
        return body + "." + hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()

    def check_token(self, header: str | None) -> str:
        if not self.dev_auth:
            raise ApiError("authentication is not configured on this server", 503)
        if not header or not header.startswith("Bearer "):
            raise ApiError("token_missing", 401)
        body, _, sig = header[7:].partition(".")
        if not hmac.compare_digest(sig, hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()):
            raise ApiError("token_invalid", 401)
        d = json.loads(base64.urlsafe_b64decode(body))
        if d["exp"] < time.time():
            raise ApiError("token_expired", 401)
        return d["u"]

    # --- project records
    def pdir(self, pid): return self.data / "server_projects" / pid
    def rec(self, pid):
        f = self.pdir(pid) / "current.json"
        return json.loads(f.read_text()) if f.exists() else None
    def asset_path(self, pid, aid): return self.data / "server_assets" / pid / aid
    def asset_ok(self, pid, aid, sha):
        f, m = self.asset_path(pid, aid), self.asset_path(pid, aid + ".sha256")
        return f.exists() and m.exists() and m.read_text() == sha and hashlib.sha256(f.read_bytes()).hexdigest() == sha


class Handler(BaseHTTPRequestHandler):
    store: Store
    asset_delay_s = 0.0   # TEST HOOK: slows asset uploads to exercise 'edit while sending'

    def log_message(self, *a): pass

    def send(self, code, body: bytes, ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def jsend(self, obj, code=200): self.send(code, json.dumps(obj, ensure_ascii=False).encode())

    def read_body(self, limit) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit: raise ApiError("body too large", 413)
        data = self.rfile.read(n)
        if len(data) != n: raise ApiError("incomplete body (connection cut)", 400)
        return data

    def jbody(self) -> dict:
        try: d = json.loads(self.read_body(64 * 1024 * 1024) or b"{}")
        except json.JSONDecodeError as e: raise ApiError(f"bad json: {e}")
        if not isinstance(d, dict): raise ApiError("json object expected")
        return d

    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_PUT(self): self.route("PUT")

    def route(self, m):
        u = urlparse(self.path)
        try:
            # Lock only sync writes/reads of project records. Static files (14 MB Pyodide) must never be
            # served under the lock: a stalled client would block every other request.
            if m != "GET" and u.path.startswith("/api/sync/") or u.path.startswith("/api/sync/project/"):
                with self.store.lock:
                    self.dispatch(m, u.path, parse_qs(u.query))
            else:
                self.dispatch(m, u.path, parse_qs(u.query))
        except ApiError as e:
            self.jsend({"error": str(e), **e.extra}, e.code)
        except (ValueError, KeyError) as e:
            self.jsend({"error": f"{type(e).__name__}: {e}"}, 400)
        except Exception as e:  # noqa: BLE001
            self.jsend({"error": f"internal error: {type(e).__name__}"}, 500)

    def static(self, rel: str):
        base = (ROOT / "static").resolve(); f = (base / rel).resolve()
        if base not in f.parents or not f.is_file(): raise ApiError("not found", 404)
        self.send(200, f.read_bytes(), CT.get(f.suffix, "application/octet-stream"),
                  {"Service-Worker-Allowed": "/"} if rel == "sw.js" else None)

    def dispatch(self, m, path, q):
        st = self.store
        if m == "GET" and path == "/api/ping":
            return self.jsend({"ok": True, "dev_auth": st.dev_auth, "server_time": time.time()})
        if m == "GET" and path == "/precache.json":
            # /py/manifest.json must be cached: bridge.load() fetches it on every boot.
            files = ["/", "/app.js", "/db.js", "/sync.js", "/bridge.js", "/manifest.webmanifest",
                     "/py/manifest.json"]
            files += ["/py/" + f.name for f in sorted(SRC.glob("*.py")) if f.name != "server.py"]
            pyo = ROOT / "static" / "vendor" / "pyodide"
            files += ["/vendor/pyodide/" + f.name for f in sorted(pyo.glob("*"))] if pyo.exists() else []
            return self.jsend({"version": "1", "files": files})
        if m == "GET" and path == "/py/manifest.json":
            return self.jsend({"files": [f.name for f in sorted(SRC.glob("*.py")) if f.name != "server.py"]})
        if m == "GET" and path.startswith("/py/"):
            f = (SRC / path[4:]).resolve()
            if f.parent != SRC or f.suffix != ".py" or f.name == "server.py" or not f.is_file(): raise ApiError("not found", 404)
            return self.send(200, f.read_bytes(), CT[".py"])
        if m == "GET" and (path == "/" or path == "/index.html"): return self.static("index.html")
        if m == "GET" and re.match(r"^/(app\.js|db\.js|sync\.js|bridge\.js|sw\.js|manifest\.webmanifest)$", path): return self.static(path[1:])
        if m == "GET" and path.startswith("/vendor/"): return self.static(path[1:])
        if m == "POST" and path == "/api/auth/dev-token":
            if not st.dev_auth: raise ApiError("dev auth disabled", 503)
            b = self.jbody()
            return self.jsend({"token": st.make_token(str(b.get("user", "dev-tester"))[:40], int(b.get("ttl_s", 3600))),
                               "note": "DEV-ONLY token; not a real authentication"})
        if path.startswith("/api/"):
            user = st.check_token(self.headers.get("Authorization"))
        if m == "GET" and path == "/api/sync/catalog":
            return self.jsend({"catalog": st.catalog.to_dict()})
        mp = re.match(r"^/api/sync/project/([A-Za-z0-9_.-]+)$", path)
        if m == "GET" and mp:
            r = st.rec(mp.group(1))
            if not r: raise ApiError("unknown project", 404)
            return self.jsend(r)
        if m == "GET" and path == "/api/sync/asset":
            pid, aid = q.get("project", [""])[0], q.get("asset", [""])[0]
            if not ID_RE.match(pid) or not re.match(r"^A-[0-9a-f]{12}$", aid): raise ApiError("bad ids")
            f = st.asset_path(pid, aid)
            if not f.exists(): raise ApiError("not found", 404)
            return self.send(200, f.read_bytes(), "application/octet-stream")
        if m == "POST" and path == "/api/sync/begin": return self.begin(user)
        if m == "PUT" and path == "/api/sync/asset": return self.put_asset(q)
        if m == "POST" and path == "/api/sync/commit": return self.commit(user)
        raise ApiError("not found", 404)

    # --- sync
    def _verify(self, b):
        pk = b["package"]
        pid = pk["project"]["project_id"]
        if not ID_RE.match(pid): raise ApiError("invalid project id")
        out = call("verify_package", {}, pk)["result"]
        if out["content_hash"] != pk["content_hash"] or out["data_version"] != pk["data_version"]:
            raise ApiError("package inconsistent: server recomputed hash differs from the claimed one")
        # catalog must be mergeable
        tmp = Catalog.from_dict(self.store.catalog.to_dict()); tmp.merge_definitions(pk["catalog"])
        return pid, pk, out

    def begin(self, user):
        st, b = self.store, self.jbody()
        pid, pk, out = self._verify(b)
        rec, base = st.rec(pid), b.get("base_rev")
        if rec and rec["received_hash"] == pk["content_hash"] and rec["client_id"] == b["client_id"]:
            return self.jsend({"already_received": True, "rev": rec["rev"], "received_hash": rec["received_hash"],
                               "need_assets": []})
        cur_rev = rec["rev"] if rec else 0
        if base != (rec["rev"] if rec else None):
            if rec is None:
                raise ApiError("conflict: server has no such project but base_rev was given", 409, {"server_rev": 0, "diff": []})
            srv = call("verify_package", {}, rec["package"])["result"]["snapshot"]
            raise ApiError("conflict", 409, {"server_rev": cur_rev, "server_client_id": rec["client_id"],
                                             "server_data_version": rec["package"]["data_version"],
                                             "diff": diff_snapshots(out["snapshot"], srv)})
        stage = st.pdir(pid) / "staged" / f"{b['client_id']}-{pk['data_version']}-{pk['content_hash'][:16]}.json"
        _atomic(stage, json.dumps({"package": pk, "client_id": b["client_id"], "base_rev": base}).encode())
        need = [a["asset_id"] for a in pk["assets"] if not st.asset_ok(pid, a["asset_id"], a["sha256"])]
        return self.jsend({"need_assets": need, "staged": stage.name, "server_rev": cur_rev})

    def put_asset(self, q):
        st = self.store
        pid, aid = q.get("project", [""])[0], q.get("asset", [""])[0]
        if not ID_RE.match(pid) or not re.match(r"^A-[0-9a-f]{12}$", aid): raise ApiError("bad ids")
        sha = self.headers.get("X-Sha256", "")
        data = self.read_body(MAX_ASSET)
        if self.asset_delay_s: time.sleep(self.asset_delay_s)
        real = hashlib.sha256(data).hexdigest()
        if real != sha or "A-" + real[:12] != aid: raise ApiError("asset hash mismatch; not stored")
        _atomic(st.asset_path(pid, aid), data)
        _atomic(st.asset_path(pid, aid + ".sha256"), real.encode())
        return self.jsend({"asset_id": aid, "stored": True, "bytes": len(data)})

    def commit(self, user):
        st, b = self.store, self.jbody()
        pid = b["project_id"]
        if not ID_RE.match(pid): raise ApiError("invalid project id")
        stage = st.pdir(pid) / "staged" / f"{b['client_id']}-{b['data_version']}-{b['content_hash'][:16]}.json"
        rec = st.rec(pid)
        if rec and rec["received_hash"] == b["content_hash"] and rec["client_id"] == b["client_id"]:
            return self.jsend({"rev": rec["rev"], "received_hash": rec["received_hash"], "assets_verified": len(rec["package"]["assets"]), "replayed": True})
        if not stage.exists(): raise ApiError("nothing staged for this version; call begin first", 409)
        sg = json.loads(stage.read_text()); pk = sg["package"]
        cur_rev = rec["rev"] if rec else 0
        if sg["base_rev"] != (cur_rev if rec else None):
            raise ApiError("conflict: server changed since begin", 409, {"server_rev": cur_rev})
        missing = [a["asset_id"] for a in pk["assets"] if not st.asset_ok(pid, a["asset_id"], a["sha256"])]
        if missing: raise ApiError("assets missing or corrupt on server", 409, {"missing": missing})
        out = call("verify_package", {}, pk)["result"]
        if out["content_hash"] != b["content_hash"]: raise ApiError("hash mismatch at commit")
        st.catalog.merge_definitions(pk["catalog"]); st.catalog.save(st.cat_path)
        if rec:
            _atomic(st.pdir(pid) / "history" / f"rev{rec['rev']}.json", json.dumps(rec).encode())  # never delete previous
        new = {"rev": cur_rev + 1, "client_id": b["client_id"], "received_hash": out["content_hash"],
               "received_at": time.time(), "received_by": user, "package": pk}
        _atomic(st.pdir(pid) / "current.json", json.dumps(new).encode())
        stage.unlink()
        return self.jsend({"rev": new["rev"], "received_hash": new["received_hash"], "assets_verified": len(pk["assets"])})


def make_server(port: int = 8765, data: Path | None = None, dev_auth: bool | None = None) -> ThreadingHTTPServer:
    d = data or Path(os.environ.get("HOA_DATA", ROOT / "data")); d.mkdir(parents=True, exist_ok=True)
    Handler.store = Store(d, os.environ.get("HOA_DEV_AUTH") == "1" if dev_auth is None else dev_auth)
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = make_server(port)
    print(f"HOMURA Field DX dev server: http://127.0.0.1:{port}/  data={Handler.store.data} dev_auth={Handler.store.dev_auth}")
    srv.serve_forever()
