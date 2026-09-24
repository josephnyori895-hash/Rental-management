#!/usr/bin/env python3
"""
Rental OS — no-root static + API proxy server.
Serves built frontend (dist/) and proxies /api/ to backend :8011.
Run: python3 serve.py  (binds 0.0.0.0:8080, no root needed)
"""
import http.server
import socketserver
import urllib.request
import os

PORT = 8080
DIST = "/home/nyorii/Projects/rental-os/frontend/dist"
BACKEND = "http://127.0.0.1:8011"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIST, **kw)

    def do_GET(self):
        if self.path.startswith("/api/") or self.path in ("/health", "/docs", "/openapi.json"):
            self._proxy()
            return
        # SPA fallback
        fpath = os.path.join(DIST, self.path.lstrip("/"))
        if not os.path.isfile(fpath) and not self.path.startswith("/assets/"):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy()
            return
        self.send_error(404)

    def _proxy(self):
        url = BACKEND + self.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(url, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length"):
                req.add_header(k, v)
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            data = resp.read()
            self.send_response(resp.status)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, str(e))

    def log_message(self, *a):
        pass


with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print(f"Rental OS serving on http://0.0.0.0:{PORT}")
    httpd.serve_forever()
