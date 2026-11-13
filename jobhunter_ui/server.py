"""Local-only HTTP server (stdlib). Binds to 127.0.0.1; rejects foreign Host/Origin and cross-site POSTs."""
from __future__ import annotations

import json
import mimetypes
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .runner import Runner, TASKS
from .service import ActionError, Workspace

STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
MAX_BODY = 1_000_000


def make_server(root, host="127.0.0.1", port=8765, workspace: Workspace | None = None):
    ws = workspace or Workspace(root)
    runner = Runner(ws.root)

    class Handler(BaseHTTPRequestHandler):
        server_version = "JobHunterUI"
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):  # keep the console quiet
            pass

        # ----- helpers -----
        def _host_ok(self) -> bool:
            host = self.headers.get("Host") or ""
            name = host.split("]")[0] + "]" if host.startswith("[") else host.split(":")[0]
            return name in LOCAL_HOSTS

        def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

        def _err(self, code, ecode, msg):
            self._json({"error": {"code": ecode, "message": msg}}, code)

        def _guard(self, post=False) -> bool:
            if not self._host_ok():
                self._err(403, "bad_host", "Only local access is allowed.")
                return False
            if post:
                origin = self.headers.get("Origin")
                if origin and urllib.parse.urlparse(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
                    self._err(403, "bad_origin", "Cross-site request blocked.")
                    return False
                if self.headers.get("X-JobHunter") != "1":
                    self._err(403, "bad_request", "Missing request header.")
                    return False
            return True

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ActionError("too_big", "Request too large.", 413)
            if not n:
                return {}
            try:
                d = json.loads(self.rfile.read(n).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise ActionError("bad_json", "Invalid request body.")
            if not isinstance(d, dict):
                raise ActionError("bad_json", "Invalid request body.")
            return d

        def _dispatch(self, fn):
            try:
                fn()
            except ActionError as e:
                self._err(e.status, e.code, e.message)
            except Exception as e:  # never leak a traceback to the browser
                self._err(500, "internal", f"Unexpected error ({type(e).__name__}). See the terminal for details.")
                import traceback
                traceback.print_exc()

        # ----- GET -----
        def do_GET(self):
            if not self._guard():
                return
            self._dispatch(self._get)

        def _get(self):
            u = urllib.parse.urlparse(self.path)
            q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query).items()}
            path = u.path
            if path in ("/", "/index.html"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            m = re.fullmatch(r"/static/([A-Za-z0-9_.-]+)", path)
            if m and (STATIC / m.group(1)).is_file():
                ct = mimetypes.guess_type(m.group(1))[0] or "application/octet-stream"
                return self._send(200, (STATIC / m.group(1)).read_bytes(), ct + "; charset=utf-8" if ct.startswith("text") or ct.endswith("javascript") else ct)
            if path == "/api/setup":
                return self._json(ws.setup_status())
            if path == "/api/jobs":
                rec = [x for x in q.get("rec", "").split(",") if x]
                try:
                    mn = float(q.get("min", 0) or 0)
                except ValueError:
                    mn = 0.0
                return self._json(ws.list_jobs(
                    weights=q.get("weights") or None, min_score=mn, rec=rec or None, q=q.get("q", ""),
                    status=q.get("status", ""), hide_german=q.get("hide_german", "1") != "0",
                    only_ready=q.get("ready") == "1"))
            if path == "/api/pending":
                return self._json(ws.pending())
            m = re.fullmatch(r"/api/jobs/([0-9a-f]{12})", path)
            if m:
                return self._json(ws.job_detail(m.group(1)))
            if path == "/api/run":
                try:
                    since = int(q.get("since", 0))
                except ValueError:
                    since = 0
                return self._json({**runner.status(since), "tasks": {k: v[0] for k, v in TASKS.items()}})
            if path.startswith("/files/"):
                rel = urllib.parse.unquote(path[len("/files/"):])
                p = ws.servable(rel)
                if not p:
                    return self._err(404, "not_found", "File not found.")
                ct = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                if p.suffix == ".md":
                    ct = "text/plain; charset=utf-8"
                disp = "attachment" if q.get("download") == "1" else "inline"
                return self._send(200, p.read_bytes(), ct,
                                  {"Content-Disposition": f'{disp}; filename="{p.name}"'})
            self._err(404, "not_found", "Not found.")

        # ----- POST -----
        def do_POST(self):
            if not self._guard(post=True):
                return
            self._dispatch(self._post)

        def _post(self):
            path = urllib.parse.urlparse(self.path).path
            b = self._body()
            m = re.fullmatch(r"/api/jobs/([0-9a-f]{12})/(cv|cover|both|telegram|status)", path)
            if m:
                jid, act = m.groups()
                if act == "cv":
                    return self._json(ws.create_cv(jid, b.get("mode", "tailored")))
                if act == "cover":
                    return self._json(ws.create_cover(jid))
                if act == "both":
                    ws.create_cv(jid, b.get("mode", "tailored"))
                    return self._json(ws.create_cover(jid))
                if act == "telegram":
                    return self._json(ws.send_telegram(jid))
                return self._json(ws.set_status(jid, b.get("status"), b.get("note")))
            if path == "/api/run":
                if b.get("stop"):
                    return self._json(runner.stop())
                return self._json(runner.start(b.get("task", ""), b))
            if path == "/api/setup/cv":
                return self._json(ws.save_cv(b.get("text", "")))
            if path == "/api/setup/cv/convert":
                return self._json({"text": ws.convert_cv_with_ai(b.get("text", ""))})
            if path == "/api/setup/keys":
                return self._json(ws.save_keys(b.get("values", {})))
            if path == "/api/setup/profile":
                return self._json(ws.save_profile(b))
            self._err(404, "not_found", "Not found.")

    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    srv.workspace, srv.runner = ws, runner
    return srv
