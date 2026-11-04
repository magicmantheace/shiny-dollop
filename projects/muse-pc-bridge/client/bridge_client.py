#!/usr/bin/env python3
"""muse-pc-bridge client — Muse-side CLI for talking to the agent.

Standard library only (urllib). Connection settings come from flags or
environment variables:

  --base   / MUSE_PC_BRIDGE_URL    e.g. http://100.64.0.2:8765
  --token  / MUSE_PC_BRIDGE_TOKEN  the token printed once by --init

Usage:
  bridge_client.py status
  bridge_client.py exec [--shell powershell|cmd|posix] [--timeout N] <command...>
  bridge_client.py list [rel-path]
  bridge_client.py get <remote-rel> <local-path>
  bridge_client.py put <local-path> <remote-rel>
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class BridgeError(Exception):
    pass


class Client:
    def __init__(self, base: str, token: str):
        if not base:
            raise BridgeError("no base URL: pass --base or set MUSE_PC_BRIDGE_URL")
        if not token:
            raise BridgeError("no token: pass --token or set MUSE_PC_BRIDGE_TOKEN")
        self.base = base.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, payload: dict | None = None,
                timeout: float = 960) -> dict:
        url = self.base + path
        data = None
        headers = {"Authorization": f"Bearer {self.token}"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise BridgeError(f"HTTP {exc.code} from agent: {body}") from exc
        except urllib.error.URLError as exc:
            raise BridgeError(f"cannot reach agent at {self.base}: {exc.reason}") \
                from exc


def print_json(obj: dict) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="muse-pc-bridge client")
    parser.add_argument("--base", default=os.environ.get("MUSE_PC_BRIDGE_URL", ""),
                        help="agent base URL (env MUSE_PC_BRIDGE_URL)")
    parser.add_argument("--token", default=os.environ.get("MUSE_PC_BRIDGE_TOKEN", ""),
                        help="agent token (env MUSE_PC_BRIDGE_TOKEN)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="agent status")

    p_exec = sub.add_parser("exec", help="run a command on the PC")
    p_exec.add_argument("--shell", choices=["powershell", "cmd", "posix"],
                        default=None)
    p_exec.add_argument("--timeout", type=float, default=None,
                        help="timeout in seconds (clamped by the agent)")
    p_exec.add_argument("--cwd", default=None, help="working directory on the PC")
    p_exec.add_argument("exec_command", nargs=argparse.REMAINDER,
                        help="the command line to run")

    p_list = sub.add_parser("list", help="list files under the agent's file root")
    p_list.add_argument("path", nargs="?", default=".")

    p_get = sub.add_parser("get", help="download a file from the agent's file root")
    p_get.add_argument("remote")
    p_get.add_argument("local")

    p_put = sub.add_parser("put", help="upload a file into the agent's file root")
    p_put.add_argument("local")
    p_put.add_argument("remote")

    args = parser.parse_args(argv)
    try:
        client = Client(args.base, args.token)
        if args.command == "status":
            print_json(client.request("GET", "/v1/status"))
        elif args.command == "exec":
            if not args.exec_command:
                parser.error("exec requires a command")
            payload = {"command": " ".join(args.exec_command)}
            if args.shell:
                payload["shell"] = args.shell
            if args.timeout is not None:
                payload["timeout_s"] = args.timeout
            if args.cwd:
                payload["cwd"] = args.cwd
            result = client.request("POST", "/v1/exec", payload)
            print_json(result)
            return 0 if result.get("exit_code") == 0 else 1
        elif args.command == "list":
            qs = urllib.parse.urlencode({"path": args.path})
            print_json(client.request("GET", f"/v1/file/list?{qs}"))
        elif args.command == "get":
            qs = urllib.parse.urlencode({"path": args.remote})
            result = client.request("GET", f"/v1/file/get?{qs}")
            data = base64.b64decode(result["content_b64"])
            digest = hashlib.sha256(data).hexdigest()
            if digest != result["sha256"]:
                raise BridgeError(f"sha256 mismatch on download: agent said "
                                  f"{result['sha256']}, got {digest}")
            local = Path(args.local)
            if local.parent != Path(""):
                local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(data)
            print(f"wrote {local} ({len(data)} bytes, sha256 {digest})")
        elif args.command == "put":
            local = Path(args.local)
            data = local.read_bytes()
            result = client.request("POST", "/v1/file/put", {
                "path": args.remote,
                "content_b64": base64.b64encode(data).decode("ascii"),
            })
            print_json(result)
            digest = hashlib.sha256(data).hexdigest()
            if result.get("sha256") != digest:
                raise BridgeError(f"sha256 mismatch on upload: agent said "
                                  f"{result.get('sha256')}, local file is {digest}")
        return 0
    except BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
