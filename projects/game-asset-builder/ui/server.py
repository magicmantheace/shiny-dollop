"""Local UI server for the Game Asset Builder (P2) — stdlib only.

Serves a single-page UI over the catalog and pipeline on localhost:

  GET  /                        the page (ui/index.html)
  GET  /api/catalog             summaries of every catalogued asset
  GET  /api/catalog/<slug>      full metadata + live sha256 check
  GET  /api/stages              the stage registry (stages.py)
  GET  /api/doctor              this machine's per-stage fitness
  GET  /api/preview/<slug>/<f>  a preview render PNG from outputs/
  GET  /api/runs                pipeline runs started from the UI
  GET  /api/runs/<id>           one run's state + output tail
  POST /api/runs                start a run (JSON body, see ui/runs.py)

Binds to 127.0.0.1 unless told otherwise; there is no auth because
there is nothing to auth against on a single-user local tool — do
not expose it beyond localhost.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from ui import catalog_data
from ui.runs import RunManager

_HERE = os.path.dirname(os.path.abspath(__file__))


def make_handler(catalog_dir: str, outputs_dir: str,
                 runs: RunManager):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):  # keep the console clean
            pass

        # -- helpers ---------------------------------------------------
        def _send(self, code: int, body: bytes,
                  content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload) -> None:
            self._send(code, json.dumps(payload).encode("utf-8"),
                       "application/json")

        def _error(self, code: int, message: str) -> None:
            self._json(code, {"error": message})

        # -- routing ---------------------------------------------------
        def do_GET(self):
            parts = [unquote(p) for p in
                     urlparse(self.path).path.split("/") if p]
            if not parts:
                with open(os.path.join(_HERE, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(),
                                      "text/html; charset=utf-8")
            if parts[0] != "api":
                return self._error(404, "not found")
            route = parts[1:]
            if route == ["catalog"]:
                return self._json(
                    200, catalog_data.list_catalog(catalog_dir,
                                                   outputs_dir))
            if len(route) == 2 and route[0] == "catalog":
                detail = catalog_data.entry_detail(route[1], catalog_dir,
                                                   outputs_dir)
                if detail is None:
                    return self._error(404,
                                       f"unknown asset: {route[1]}")
                return self._json(200, detail)
            if route == ["stages"]:
                return self._json(200, catalog_data.stage_table())
            if route == ["doctor"]:
                return self._json(200, catalog_data.doctor_info())
            if len(route) == 3 and route[0] == "preview":
                path = catalog_data.preview_path(outputs_dir, route[1],
                                                 route[2])
                if path is None:
                    return self._error(404, "no such preview")
                with open(path, "rb") as fh:
                    return self._send(200, fh.read(), "image/png")
            if route == ["runs"]:
                return self._json(200, runs.list())
            if len(route) == 2 and route[0] == "runs":
                record = runs.get(route[1])
                if record is None:
                    return self._error(404, f"unknown run: {route[1]}")
                return self._json(200, record)
            return self._error(404, "not found")

        def do_POST(self):
            parts = [unquote(p) for p in
                     urlparse(self.path).path.split("/") if p]
            if parts != ["api", "runs"]:
                return self._error(404, "not found")
            try:
                length = int(self.headers.get("Content-Length") or 0)
                spec = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._error(400, "request body must be JSON")
            try:
                record = runs.start(spec)
            except ValueError as exc:
                return self._error(400, str(exc))
            return self._json(201, record)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8770,
          catalog_dir: str = catalog_data.CATALOG_DIR,
          outputs_dir: str = catalog_data.OUTPUTS_DIR) -> None:
    runs = RunManager()
    server = ThreadingHTTPServer(
        (host, port), make_handler(catalog_dir, outputs_dir, runs))
    print(f"Game Asset Builder UI: http://{host}:{port}/ "
          f"(catalog: {catalog_dir})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
