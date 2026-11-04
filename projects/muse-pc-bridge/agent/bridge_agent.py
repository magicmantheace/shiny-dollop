#!/usr/bin/env python3
"""muse-pc-bridge agent — full-shell HTTP agent for Muse, stdlib only.

Runs on the owner's Windows PC, binds (by configuration) to the PC's
Tailscale IP, and exposes a small JSON API:

  GET  /v1/status
  POST /v1/exec
  GET  /v1/file/list?path=<rel>
  GET  /v1/file/get?path=<rel>
  POST /v1/file/put

Every /v1/* request requires `Authorization: Bearer <token>`. Every
request — including auth failures — is appended to a JSONL audit log.
The token is never written to the audit log.

Full shell access is the owner's explicit choice (2026-11-04). The
audit log is non-negotiable: if it cannot be written, the failure is
reported on stderr but the server keeps running (a broken audit write
must not crash the agent).

Usage:
  python bridge_agent.py --init      # write config.json, print token once
  python bridge_agent.py             # run with ./config.json
  python bridge_agent.py --config C:\\path\\config.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = "0.1.0"
AGENT_NAME = "muse-pc-bridge"
MAX_GET_BYTES = 16 * 1024 * 1024          # /v1/file/get hard limit
MAX_BODY_BYTES = 40 * 1024 * 1024         # request body hard limit
IS_WINDOWS = os.name == "nt"

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8765,
    "token": "",
    "allowed_file_root": "./bridge-files",
    "max_output_bytes": 262144,
    "default_timeout_s": 60,
    "max_timeout_s": 900,
    "audit_log": "./logs/audit.jsonl",
}

_DRIVE_RE = re.compile(r"^[a-zA-Z]:")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def default_shell() -> str:
    return "powershell" if IS_WINDOWS else "posix"


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def agent_dir() -> Path:
    return Path(__file__).resolve().parent


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(raw)
    base = config_path.resolve().parent
    # Relative file root / audit paths resolve beside the config file.
    for key in ("allowed_file_root", "audit_log"):
        p = Path(str(cfg[key]))
        if not p.is_absolute():
            cfg[key] = str((base / p).resolve())
    cfg["config_path"] = str(config_path)
    return cfg


def init_config(config_path: Path) -> str:
    """Write a fresh config.json with a generated token; return the token."""
    token = secrets.token_urlsafe(32)
    cfg = dict(DEFAULT_CONFIG)
    cfg["token"] = token
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    return token


# --------------------------------------------------------------------------
# Core: audit log + file-root safety (shared by the HTTP handler)
# --------------------------------------------------------------------------

class BridgeCore:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.token = str(cfg.get("token", ""))
        self.file_root = Path(cfg["allowed_file_root"])
        self.file_root.mkdir(parents=True, exist_ok=True)
        self.audit_path = Path(cfg["audit_log"])
        self.started_at = time.time()
        self._audit_lock = threading.Lock()

    # -- audit -------------------------------------------------------------
    def audit(self, entry: dict) -> None:
        record = {"ts": utc_now_iso()}
        record.update(entry)
        line = json.dumps(record, ensure_ascii=False)
        try:
            with self._audit_lock:
                self.audit_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.audit_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except OSError as exc:  # never crash the server on audit failure
            print(f"[bridge] WARNING: audit write failed: {exc}", file=sys.stderr)

    def log_start(self) -> None:
        self.audit({
            "event": "server_start",
            "ip": None, "method": None, "path": None,
            "summary": f"{AGENT_NAME} {VERSION} listening on "
                       f"{self.cfg['host']}:{self.cfg['port']}",
            "status": None, "duration_ms": None,
        })

    def log_stop(self) -> None:
        self.audit({
            "event": "server_stop",
            "ip": None, "method": None, "path": None,
            "summary": f"{AGENT_NAME} shutting down",
            "status": None, "duration_ms": None,
        })

    # -- file root safety ----------------------------------------------------
    def resolve_rel(self, rel: str) -> Path:
        """Resolve a client-supplied relative path inside the file root.

        Raises ValueError for anything absolute or escaping the root.
        """
        if rel is None:
            rel = "."
        rel = str(rel).replace("\\", "/") if IS_WINDOWS else str(rel)
        if IS_WINDOWS and _DRIVE_RE.match(rel):
            raise ValueError("absolute/drive paths are not allowed")
        p = Path(rel)
        if p.is_absolute():
            raise ValueError("absolute paths are not allowed")
        root = self.file_root.resolve()
        target = (root / p).resolve()
        if target != root and root not in target.parents:
            raise ValueError("path escapes the allowed file root")
        return target

    def rel_display(self, target: Path) -> str:
        root = self.file_root.resolve()
        try:
            return target.resolve().relative_to(root).as_posix()
        except ValueError:
            return "."


# --------------------------------------------------------------------------
# Command execution
# --------------------------------------------------------------------------

def build_command(shell: str, command: str) -> list[str]:
    if shell == "powershell":
        exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [exe, "-NoProfile", "-NonInteractive", "-Command", command]
    if shell == "cmd":
        return ["cmd", "/d", "/s", "/c", command]
    if shell == "posix":
        return ["/bin/sh", "-c", command]
    raise ValueError(f"unknown shell: {shell!r}")


def run_command(core: BridgeCore, payload: dict) -> tuple[int, dict]:
    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return 400, {"error": "field 'command' (non-empty string) is required"}
    shell = payload.get("shell") or default_shell()
    if shell not in ("powershell", "cmd", "posix"):
        return 400, {"error": f"unknown shell: {shell!r}"}
    argv = build_command(shell, command)

    cfg = core.cfg
    timeout = payload.get("timeout_s", cfg["default_timeout_s"])
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        return 400, {"error": "timeout_s must be a number"}
    timeout = max(0.1, min(timeout, float(cfg["max_timeout_s"])))

    cwd = payload.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str) or not Path(cwd).is_dir():
            return 400, {"error": f"cwd does not exist: {cwd!r}"}
    else:
        cwd = str(agent_dir())

    env = dict(os.environ)
    extra_env = payload.get("env")
    if extra_env is not None:
        if not isinstance(extra_env, dict):
            return 400, {"error": "env must be an object of string values"}
        for k, v in extra_env.items():
            env[str(k)] = str(v)

    max_out = int(cfg["max_output_bytes"])
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            start_new_session=not IS_WINDOWS,
        )
    except OSError as exc:
        return 500, {"error": f"failed to start shell: {exc}"}
    try:
        out_b, err_b = proc.communicate(timeout=timeout)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = None
        try:
            if IS_WINDOWS:
                proc.kill()
            else:
                os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        out_b, err_b = proc.communicate()
    duration_ms = int((time.monotonic() - started) * 1000)

    truncated = len(out_b) > max_out or len(err_b) > max_out
    result = {
        "exit_code": exit_code,
        "stdout": out_b[:max_out].decode("utf-8", errors="replace"),
        "stderr": err_b[:max_out].decode("utf-8", errors="replace"),
        "duration_ms": duration_ms,
        "timed_out": timed_out,
        "truncated": truncated,
    }
    return 200, result


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------

class BridgeHandler(BaseHTTPRequestHandler):
    server_version = f"{AGENT_NAME}/{VERSION}"
    protocol_version = "HTTP/1.1"

    # Quieten default stderr logging; the audit log is the record.
    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        pass

    @property
    def core(self) -> BridgeCore:
        return self.server.core  # type: ignore[attr-defined]

    # -- plumbing ------------------------------------------------------------
    def _send_json(self, status: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization") or ""
        expected = f"Bearer {self.core.token}"
        return bool(self.core.token) and hmac.compare_digest(header, expected)

    def _client_ip(self) -> str:
        return self.client_address[0] if self.client_address else ""

    def _audit_request(self, summary: str, status: int, started: float,
                       exit_code=None, auth_failed: bool = False) -> None:
        entry = {
            "event": "auth_failed" if auth_failed else "request",
            "ip": self._client_ip(),
            "method": self.command,
            "path": self.path,
            "summary": summary,
            "status": status,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        if exit_code is not None:
            entry["exit_code"] = exit_code
        self.core.audit(entry)

    # -- routing ---------------------------------------------------------------
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        started = time.monotonic()
        parsed = urlparse(self.path)
        route = parsed.path
        if not route.startswith("/v1/"):
            self._send_json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._audit_request("auth failed", 401, started, auth_failed=True)
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            if method == "GET" and route == "/v1/status":
                status, obj, summary = self._handle_status()
            elif method == "POST" and route == "/v1/exec":
                status, obj, summary = self._handle_exec()
            elif method == "GET" and route == "/v1/file/list":
                status, obj, summary = self._handle_file_list(parsed)
            elif method == "GET" and route == "/v1/file/get":
                status, obj, summary = self._handle_file_get(parsed)
            elif method == "POST" and route == "/v1/file/put":
                status, obj, summary = self._handle_file_put()
            else:
                status, obj, summary = 404, {"error": "not found"}, "no route"
            exit_code = obj.get("exit_code") if isinstance(obj, dict) else None
            self._audit_request(summary, status, started, exit_code=exit_code)
            self._send_json(status, obj)
        except ValueError as exc:
            self._audit_request(f"bad request: {exc}", 400, started)
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # keep the server alive on handler bugs
            self._audit_request(f"server error: {exc}", 500, started)
            self._send_json(500, {"error": f"internal error: {exc}"})

    # -- endpoints -------------------------------------------------------------
    def _handle_status(self):
        core = self.core
        obj = {
            "agent": AGENT_NAME,
            "version": VERSION,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uptime_s": round(time.time() - core.started_at, 3),
            "shell_default": default_shell(),
            "file_root": str(core.file_root),
        }
        return 200, obj, "status"

    def _handle_exec(self):
        payload = self._read_json_body()
        status, obj = run_command(self.core, payload)
        cmd = str(payload.get("command", ""))[:500]
        summary = f"exec[{payload.get('shell') or default_shell()}]: {cmd}"
        return status, obj, summary

    def _query_path(self, parsed) -> str:
        qs = parse_qs(parsed.query)
        values = qs.get("path")
        return values[0] if values else "."

    def _handle_file_list(self, parsed):
        rel = self._query_path(parsed)
        target = self.core.resolve_rel(rel)
        if not target.exists():
            return 404, {"error": f"no such path: {rel}"}, f"list {rel} (missing)"
        if not target.is_dir():
            return 400, {"error": f"not a directory: {rel}"}, f"list {rel} (not dir)"
        entries = []
        for child in target.iterdir():
            is_dir = child.is_dir()
            entries.append({
                "name": child.name,
                "type": "dir" if is_dir else "file",
                "size": None if is_dir else child.stat().st_size,
            })
        entries.sort(key=lambda e: e["name"])
        return 200, {"path": self.core.rel_display(target), "entries": entries}, \
            f"list {rel} ({len(entries)} entries)"

    def _handle_file_get(self, parsed):
        rel = self._query_path(parsed)
        target = self.core.resolve_rel(rel)
        if not target.exists() or not target.is_file():
            return 404, {"error": f"no such file: {rel}"}, f"get {rel} (missing)"
        size = target.stat().st_size
        if size > MAX_GET_BYTES:
            return 413, {"error": f"file too large to transfer ({size} bytes > "
                                   f"{MAX_GET_BYTES})"}, f"get {rel} (too large)"
        data = target.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        obj = {
            "path": self.core.rel_display(target),
            "size": size,
            "sha256": digest,
            "content_b64": base64.b64encode(data).decode("ascii"),
        }
        return 200, obj, f"get {rel} size={size} sha256={digest}"

    def _handle_file_put(self):
        payload = self._read_json_body()
        rel = payload.get("path")
        if not isinstance(rel, str) or not rel.strip() or rel.strip() in (".", "./"):
            return 400, {"error": "field 'path' (relative file path) is required"}, \
                "put (no path)"
        content_b64 = payload.get("content_b64")
        if not isinstance(content_b64, str):
            return 400, {"error": "field 'content_b64' (string) is required"}, \
                f"put {rel} (no content)"
        try:
            data = base64.b64decode(content_b64, validate=True)
        except (ValueError, TypeError):
            return 400, {"error": "content_b64 is not valid base64"}, f"put {rel} (bad b64)"
        target = self.core.resolve_rel(rel)
        if target == self.core.file_root.resolve():
            return 400, {"error": "path must name a file, not the root"}, f"put {rel} (root)"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        obj = {"path": self.core.rel_display(target), "size": len(data), "sha256": digest}
        return 200, obj, f"put {rel} size={len(data)} sha256={digest}"


def create_server(cfg: dict) -> ThreadingHTTPServer:
    core = BridgeCore(cfg)
    server = ThreadingHTTPServer((str(cfg["host"]), int(cfg["port"])), BridgeHandler)
    server.core = core  # type: ignore[attr-defined]
    server.daemon_threads = True
    core.log_start()
    return server


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="muse-pc-bridge agent")
    parser.add_argument("--config", type=Path, default=agent_dir() / "config.json",
                        help="path to config.json (default: beside this script)")
    parser.add_argument("--init", action="store_true",
                        help="write a fresh config.json with a generated token, "
                             "print the token once, and exit")
    args = parser.parse_args(argv)

    if args.init:
        if args.config.exists():
            print(f"[bridge] {args.config} already exists; refusing to overwrite. "
                  f"Delete it first if you really want a new token.", file=sys.stderr)
            return 1
        token = init_config(args.config)
        print(f"[bridge] Wrote {args.config}")
        print(f"[bridge] Token (shown ONCE — hand it to Muse out-of-band): {token}")
        print("[bridge] Next: edit 'host' in config.json to this PC's Tailscale "
              "100.x IP, then start the agent.")
        return 0

    if not args.config.exists():
        print(f"[bridge] No config at {args.config}. Run with --init first.",
              file=sys.stderr)
        return 1
    cfg = load_config(args.config)
    if not cfg.get("token"):
        print("[bridge] Config has no token. Delete config.json and re-run --init.",
              file=sys.stderr)
        return 1
    if str(cfg["host"]) in ("0.0.0.0", "::"):
        print("=" * 72, file=sys.stderr)
        print("[bridge] *** WARNING: host is a wildcard address — the agent will "
              "listen on ALL interfaces, not just Tailscale. ***", file=sys.stderr)
        print("[bridge] *** Set 'host' to this PC's Tailscale 100.x IP instead "
              "unless you really mean this. ***", file=sys.stderr)
        print("=" * 72, file=sys.stderr)

    server = create_server(cfg)
    host, port = server.server_address[0], server.server_address[1]
    print(f"[bridge] {AGENT_NAME} {VERSION} listening on http://{host}:{port} "
          f"(shell default: {default_shell()})")
    print(f"[bridge] File root: {cfg['allowed_file_root']}")
    print(f"[bridge] Audit log: {cfg['audit_log']}")
    print("[bridge] Running. Closing this window (or Ctrl+C) stops the agent — "
          "that is the kill switch.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] Ctrl+C received; shutting down.")
    finally:
        server.core.log_stop()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
