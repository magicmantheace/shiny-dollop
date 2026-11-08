#!/usr/bin/env python3
"""muse-pc-bridge client — Muse-side library + CLI for the agent.

Standard library only (urllib). Connection settings come from flags or
environment variables:

  --base   / MUSE_PC_BRIDGE_URL    e.g. http://100.64.0.2:8765
  --token  / MUSE_PC_BRIDGE_TOKEN  the token printed once by --init

Library use:

  from bridge_client import BridgeClient
  client = BridgeClient(base, token)
  job = client.exec_run("echo hello")            # submit + poll
  client.upload("big.zip", "big.zip")            # chunked, verified
  client.download("big.zip", "copy.zip")         # ranged, verified

CLI (v0 commands status/exec/list/get/put unchanged; v1 adds jobs,
processes, sessions, tree/mkdir/move/delete/hash, screenshot, input,
clipboard, uia, audit-tail, update):

  bridge_client.py status
  bridge_client.py exec [--shell S] [--timeout N] [--no-wait] <command...>
  bridge_client.py jobs | job <id> | job-cancel <id>
  bridge_client.py spawn <command...> | processes | kill <process-id>
  bridge_client.py list [path] | tree [path] | get <remote> <local>
  bridge_client.py put <local> <remote> | hash <remote>
  bridge_client.py mkdir <path> | move <src> <dst> | delete <path> [-r]
  bridge_client.py screenshot <local-path> [--format png|bmp]
  bridge_client.py clipboard-get | clipboard-set <text>
  bridge_client.py audit-tail [n]
  bridge_client.py update-status
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHUNK = 8 * 1024 * 1024

# Per-response output slice requested while polling jobs. Matches the
# agent's default max_output_bytes; job_wait asks for it explicitly so
# it can tell exactly how many bytes each response carried.
JOB_POLL_MAX_BYTES = 262144


class BridgeError(Exception):
    pass


class Client:
    """Transport + v1 API. (Named `Client` for v0 compatibility;
    `BridgeClient` below is the same class.)"""

    def __init__(self, base: str, token: str):
        if not base:
            raise BridgeError("no base URL: pass --base or set MUSE_PC_BRIDGE_URL")
        if not token:
            raise BridgeError("no token: pass --token or set MUSE_PC_BRIDGE_TOKEN")
        self.base = base.rstrip("/")
        self.token = token

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def request(self, method: str, path: str, payload: dict | None = None,
                timeout: float = 120) -> dict:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return self._send(method, path, data, headers, timeout)

    def request_raw(self, method: str, path: str, data: bytes,
                    content_type: str = "application/octet-stream",
                    timeout: float = 300) -> dict:
        return self._send(method, path, data,
                          {"Content-Type": content_type}, timeout)

    def _send(self, method: str, path: str, data: bytes | None,
              headers: dict, timeout: float) -> dict:
        url = self.base + path
        headers = dict(headers)
        headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise BridgeError(f"HTTP {exc.code} from agent: {body}") from exc
        except urllib.error.URLError as exc:
            raise BridgeError(f"cannot reach agent at {self.base}: "
                              f"{exc.reason}") from exc

    @staticmethod
    def _qs(params: dict) -> str:
        clean = {k: v for k, v in params.items() if v is not None}
        return ("?" + urllib.parse.urlencode(clean)) if clean else ""

    # ------------------------------------------------------------------
    # Status / audit / update
    # ------------------------------------------------------------------
    def status(self) -> dict:
        return self.request("GET", "/v1/status")

    def audit_tail(self, n: int = 50) -> dict:
        return self.request("GET", f"/v1/audit/tail?n={int(n)}")

    def update_status(self) -> dict:
        return self.request("GET", "/v1/update/status")

    def update_stage(self, source: str, sha256: str, version: str) -> dict:
        return self.request("POST", "/v1/update/stage", {
            "source": source, "sha256": sha256, "version": version})

    # ------------------------------------------------------------------
    # Jobs (async exec)
    # ------------------------------------------------------------------
    def exec_submit(self, command: str, shell: str | None = None,
                    timeout_s: float | None = None, cwd: str | None = None,
                    env: dict | None = None) -> dict:
        payload: dict = {"command": command}
        if shell:
            payload["shell"] = shell
        if timeout_s is not None:
            payload["timeout_s"] = timeout_s
        if cwd:
            payload["cwd"] = cwd
        if env:
            payload["env"] = env
        return self.request("POST", "/v1/exec", payload)

    def job_get(self, job_id: str, stdout_offset: int = 0,
                stderr_offset: int = 0,
                max_bytes: int | None = None) -> dict:
        qs = self._qs({"stdout_offset": stdout_offset,
                       "stderr_offset": stderr_offset,
                       "max_bytes": max_bytes})
        return self.request("GET", f"/v1/jobs/{job_id}{qs}")

    def jobs_list(self, state: str | None = None) -> dict:
        return self.request("GET", "/v1/jobs" + self._qs({"state": state}))

    def job_cancel(self, job_id: str) -> dict:
        return self.request("POST", f"/v1/jobs/{job_id}/cancel", {})

    def job_wait(self, job_id: str, poll_interval: float = 0.5,
                 timeout: float | None = None) -> dict:
        """Poll a job to completion, accumulating output incrementally.
        Returns the job object with full retained stdout/stderr. If the
        client-side timeout expires, BridgeError is raised — the job
        itself keeps running on the agent (fetch it later by id)."""
        out_off = err_off = 0
        out_parts: list[str] = []
        err_parts: list[str] = []
        deadline = None if timeout is None else time.time() + timeout
        while True:
            snap = self.job_get(job_id, out_off, err_off,
                                max_bytes=JOB_POLL_MAX_BYTES)
            out_text = snap.get("stdout", "")
            err_text = snap.get("stderr", "")
            out_parts.append(out_text)
            err_parts.append(err_text)
            # Advance only past the bytes this response actually
            # returned. stdout_bytes is the stream TOTAL: jumping
            # straight to it skips everything past one response slice
            # (256 KiB) whenever a job emits more than that between
            # polls. (For a truncated stream the totals count bytes
            # the agent has already discarded; the offsets then run
            # ahead of the retained data, reads come back empty, and
            # the terminal-drain check below ends the loop.)
            out_off += min(JOB_POLL_MAX_BYTES,
                           max(0, snap["stdout_bytes"] - out_off))
            err_off += min(JOB_POLL_MAX_BYTES,
                           max(0, snap["stderr_bytes"] - err_off))
            terminal = snap["state"] in ("done", "failed", "killed")
            drained = out_off >= snap["stdout_bytes"] and \
                err_off >= snap["stderr_bytes"]
            if terminal and (drained or (not out_text and not err_text)):
                snap["stdout"] = "".join(out_parts)
                snap["stderr"] = "".join(err_parts)
                return snap
            if deadline is not None and time.time() > deadline:
                raise BridgeError(
                    f"timed out waiting for job {job_id} "
                    f"(still {snap['state']} on the agent)")
            if not terminal:
                time.sleep(poll_interval)

    def exec_run(self, command: str, shell: str | None = None,
                 timeout_s: float | None = None, cwd: str | None = None,
                 env: dict | None = None,
                 wait_timeout: float | None = None) -> dict:
        job = self.exec_submit(command, shell=shell, timeout_s=timeout_s,
                               cwd=cwd, env=env)
        return self.job_wait(job["job_id"], timeout=wait_timeout)

    # ------------------------------------------------------------------
    # Wake-on-LAN
    # ------------------------------------------------------------------
    def wol(self, mac: str, broadcast: str | None = None,
            port: int | None = None) -> dict:
        """Ask the agent to send a Wake-on-LAN magic packet from the
        PC (for waking OTHER machines on its LAN — the agent cannot
        wake the PC it runs on)."""
        payload: dict = {"mac": mac}
        if broadcast:
            payload["broadcast"] = broadcast
        if port is not None:
            payload["port"] = port
        return self.request("POST", "/v1/wol", payload)

    # ------------------------------------------------------------------
    # Detached processes
    # ------------------------------------------------------------------
    def process_spawn(self, command: str | None = None,
                      shell: str | None = None,
                      cwd: str | None = None, env: dict | None = None,
                      gui: bool = False, executable: str | None = None,
                      args: list | None = None) -> dict:
        """Spawn a detached process.

        Default mode wraps ``command`` in a shell. With ``gui=True``
        the agent spawns ``executable`` (plus ``args``) directly, so
        the tracked pid is the GUI application itself — a shell
        wrapper exits as soon as it hands off to a GUI exe, which
        made shell-spawned GUI apps report dead instantly.
        """
        payload: dict = {}
        if gui:
            payload["gui"] = True
            payload["executable"] = executable
            if args:
                payload["args"] = list(args)
        else:
            payload["command"] = command
            if shell:
                payload["shell"] = shell
        if cwd:
            payload["cwd"] = cwd
        if env:
            payload["env"] = env
        return self.request("POST", "/v1/processes", payload)

    def processes_list(self) -> dict:
        return self.request("GET", "/v1/processes")

    def process_get(self, process_id: str, tail_bytes: int = 8192) -> dict:
        return self.request(
            "GET", f"/v1/processes/{process_id}?tail_bytes={int(tail_bytes)}")

    def process_kill(self, process_id: str) -> dict:
        return self.request("POST", f"/v1/processes/{process_id}/kill", {})

    # ------------------------------------------------------------------
    # Interactive sessions
    # ------------------------------------------------------------------
    def session_open(self, shell: str | None = None, cwd: str | None = None,
                     env: dict | None = None) -> dict:
        payload: dict = {}
        if shell:
            payload["shell"] = shell
        if cwd:
            payload["cwd"] = cwd
        if env:
            payload["env"] = env
        return self.request("POST", "/v1/sessions", payload)

    def session_read(self, session_id: str, offset: int = 0,
                     max_bytes: int | None = None) -> dict:
        qs = self._qs({"offset": offset, "max_bytes": max_bytes})
        return self.request("GET", f"/v1/sessions/{session_id}{qs}")

    def session_write(self, session_id: str, data: str,
                      close_stdin: bool = False) -> dict:
        return self.request("POST", f"/v1/sessions/{session_id}/input",
                            {"data": data, "close_stdin": close_stdin})

    def session_close(self, session_id: str) -> dict:
        return self.request("POST", f"/v1/sessions/{session_id}/close", {})

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------
    def file_list(self, path: str = ".", root: str | None = None) -> dict:
        return self.request("GET", "/v1/file/list" + self._qs(
            {"path": path, "root": root}))

    def file_tree(self, path: str = ".", root: str | None = None,
                  max_depth: int | None = None,
                  max_entries: int | None = None) -> dict:
        return self.request("GET", "/v1/file/tree" + self._qs(
            {"path": path, "root": root, "max_depth": max_depth,
             "max_entries": max_entries}))

    def file_hash(self, path: str, root: str | None = None) -> dict:
        return self.request("GET", "/v1/file/hash" + self._qs(
            {"path": path, "root": root}))

    def file_mkdir(self, path: str, root: str | None = None) -> dict:
        payload: dict = {"path": path}
        if root:
            payload["root"] = root
        return self.request("POST", "/v1/file/mkdir", payload)

    def file_move(self, source: str, dest: str, root: str | None = None,
                  dest_root: str | None = None) -> dict:
        payload: dict = {"from": source, "to": dest}
        if root:
            payload["root"] = root
        if dest_root:
            payload["to_root"] = dest_root
        return self.request("POST", "/v1/file/move", payload)

    def file_delete(self, path: str, recursive: bool = False,
                    root: str | None = None) -> dict:
        payload: dict = {"path": path, "recursive": recursive}
        if root:
            payload["root"] = root
        return self.request("POST", "/v1/file/delete", payload)

    def put_small(self, local: str | Path, remote: str,
                  root: str | None = None) -> dict:
        """Single-call upload (v0 path) — small files only (<=16 MiB)."""
        data = Path(local).read_bytes()
        payload: dict = {"path": remote,
                         "content_b64": base64.b64encode(data).decode("ascii")}
        if root:
            payload["root"] = root
        result = self.request("POST", "/v1/file/put", payload)
        digest = hashlib.sha256(data).hexdigest()
        if result.get("sha256") != digest:
            raise BridgeError(f"sha256 mismatch on upload: agent said "
                              f"{result.get('sha256')}, local file is {digest}")
        return result

    def get_small(self, remote: str, local: str | Path,
                  root: str | None = None) -> dict:
        """Single-call download (v0 path) — small files only (<=16 MiB)."""
        result = self.request("GET", "/v1/file/get" + self._qs(
            {"path": remote, "root": root}))
        data = base64.b64decode(result["content_b64"])
        digest = hashlib.sha256(data).hexdigest()
        if digest != result["sha256"]:
            raise BridgeError(f"sha256 mismatch on download: agent said "
                              f"{result['sha256']}, got {digest}")
        dest = Path(local)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return result

    def upload(self, local: str | Path, remote: str,
               root: str | None = None, upload_id: str | None = None,
               chunk_bytes: int = CHUNK) -> dict:
        """Chunked, resumable upload. The agent verifies size + SHA-256
        at completion; this client verifies the returned digest too.
        Pass a previous `upload_id` to resume an interrupted upload."""
        local_path = Path(local)
        data_size = local_path.stat().st_size
        digest = hashlib.sha256()
        with open(local_path, "rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(block)
        sha = digest.hexdigest()
        if upload_id is None:
            payload: dict = {"path": remote, "size": data_size,
                             "sha256": sha, "chunk_bytes": chunk_bytes}
            if root:
                payload["root"] = root
            started = self.request("POST", "/v1/file/upload/start", payload)
            upload_id = started["upload_id"]
        status = self.request("GET", f"/v1/file/upload/{upload_id}")
        # The agent's chunking is authoritative (it may clamp ours).
        server_chunk = int(status["chunk_size"])
        received = set(status["received_chunks"])
        total_chunks = int(status["chunk_count"])
        with open(local_path, "rb") as fh:
            for index in range(total_chunks):
                if index in received:
                    continue
                fh.seek(index * server_chunk)
                block = fh.read(server_chunk)
                self.request_raw("PUT", f"/v1/file/upload/{upload_id}/{index}",
                                 block)
        result = self.request("POST", f"/v1/file/upload/{upload_id}/complete",
                              {})
        if result.get("sha256") != sha:
            raise BridgeError(f"sha256 mismatch after chunked upload: agent "
                              f"said {result.get('sha256')}, local is {sha}")
        result["upload_id"] = upload_id
        return result

    def download(self, remote: str, local: str | Path,
                 root: str | None = None, chunk_bytes: int = CHUNK) -> dict:
        """Ranged download verified against the agent's SHA-256 endpoint."""
        info = self.file_hash(remote, root=root)
        size = info["size"]
        dest = Path(local)
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        offset = 0
        with open(dest, "wb") as out:
            while offset < size:
                length = min(chunk_bytes, size - offset)
                part = self.request("GET", "/v1/file/get" + self._qs(
                    {"path": remote, "root": root, "offset": offset,
                     "length": length}))
                block = base64.b64decode(part["content_b64"])
                if len(block) != length:
                    raise BridgeError(
                        f"short read at offset {offset}: got {len(block)}, "
                        f"wanted {length}")
                out.write(block)
                digest.update(block)
                offset += len(block)
        actual = digest.hexdigest()
        if actual != info["sha256"]:
            raise BridgeError(f"sha256 mismatch on download: agent hash "
                              f"endpoint said {info['sha256']}, got {actual}")
        return {"path": remote, "size": size, "sha256": actual,
                "local": str(dest)}

    # ------------------------------------------------------------------
    # Eyes / hands (Windows agent)
    # ------------------------------------------------------------------
    def screenshot(self, local: str | Path | None = None,
                   fmt: str = "png", monitor: int | None = None,
                   region: str | None = None) -> dict:
        result = self.request("GET", "/v1/screenshot" + self._qs(
            {"format": fmt, "monitor": monitor, "region": region}))
        if local is not None:
            data = base64.b64decode(result["content_b64"])
            if hashlib.sha256(data).hexdigest() != result["sha256"]:
                raise BridgeError("sha256 mismatch on screenshot download")
            dest = Path(local)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            result["local"] = str(dest)
        return result

    def input(self, actions: list[dict]) -> dict:
        return self.request("POST", "/v1/input", {"actions": actions})

    def mouse_pos(self) -> dict:
        return self.input([{"type": "mouse_pos"}])

    def clipboard_get(self) -> dict:
        return self.request("GET", "/v1/clipboard")

    def clipboard_set(self, text: str) -> dict:
        return self.request("POST", "/v1/clipboard", {"text": text})

    def uia(self, action: str, **params) -> dict:
        payload = {"action": action}
        payload.update(params)
        return self.request("POST", "/v1/uia", payload)


BridgeClient = Client


def print_json(obj: dict) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="muse-pc-bridge client")
    parser.add_argument("--base", default=os.environ.get("MUSE_PC_BRIDGE_URL", ""),
                        help="agent base URL (env MUSE_PC_BRIDGE_URL)")
    parser.add_argument("--token", default=os.environ.get("MUSE_PC_BRIDGE_TOKEN", ""),
                        help="agent token (env MUSE_PC_BRIDGE_TOKEN)")
    parser.add_argument("--root", default=None,
                        help="named file root (for file commands)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="agent status")

    p_exec = sub.add_parser("exec", help="run a command on the PC (job, polled)")
    p_exec.add_argument("--shell", choices=["powershell", "cmd", "posix"],
                        default=None)
    p_exec.add_argument("--timeout", type=float, default=None,
                        help="job timeout in seconds (agent-side)")
    p_exec.add_argument("--cwd", default=None, help="working directory on the PC")
    p_exec.add_argument("--no-wait", action="store_true",
                        help="submit only; print the job id and return")
    p_exec.add_argument("exec_command", nargs=argparse.REMAINDER,
                        help="the command line to run")

    sub.add_parser("jobs", help="list jobs")
    p_job = sub.add_parser("job", help="fetch one job (full output)")
    p_job.add_argument("job_id")
    p_jobc = sub.add_parser("job-cancel", help="cancel a running job")
    p_jobc.add_argument("job_id")

    p_spawn = sub.add_parser("spawn", help="start a detached process")
    p_spawn.add_argument("--shell", choices=["powershell", "cmd", "posix"],
                         default=None)
    p_spawn.add_argument("--cwd", default=None)
    p_spawn.add_argument("spawn_command", nargs=argparse.REMAINDER)
    p_gui = sub.add_parser(
        "spawn-gui",
        help="launch a GUI app directly (tracked pid is the app itself)")
    p_gui.add_argument("--cwd", default=None)
    p_gui.add_argument("executable")
    p_gui.add_argument("gui_args", nargs=argparse.REMAINDER,
                       help="arguments for the executable")
    p_wol = sub.add_parser(
        "wol", help="send a Wake-on-LAN magic packet from the PC")
    p_wol.add_argument("mac")
    p_wol.add_argument("--broadcast", default=None,
                       help="broadcast address (default 255.255.255.255)")
    p_wol.add_argument("--port", type=int, default=None,
                       help="UDP port (default 9)")
    sub.add_parser("processes", help="list detached processes")
    p_proc = sub.add_parser("process", help="inspect a detached process")
    p_proc.add_argument("process_id")
    p_proc.add_argument("--tail", type=int, default=8192)
    p_kill = sub.add_parser("kill", help="kill a detached process")
    p_kill.add_argument("process_id")

    p_list = sub.add_parser("list", help="list files under a file root")
    p_list.add_argument("path", nargs="?", default=".")
    p_tree = sub.add_parser("tree", help="recursive listing under a file root")
    p_tree.add_argument("path", nargs="?", default=".")
    p_tree.add_argument("--depth", type=int, default=None)
    p_get = sub.add_parser("get", help="download a file (ranged, hash-verified)")
    p_get.add_argument("remote")
    p_get.add_argument("local")
    p_put = sub.add_parser("put", help="upload a file (chunked, hash-verified)")
    p_put.add_argument("local")
    p_put.add_argument("remote")
    p_put.add_argument("--resume", default=None,
                       help="upload id from an interrupted upload to resume")
    p_hash = sub.add_parser("hash", help="server-side SHA-256 of a file")
    p_hash.add_argument("remote")
    p_mkdir = sub.add_parser("mkdir", help="create a directory in a file root")
    p_mkdir.add_argument("path")
    p_move = sub.add_parser("move", help="move/rename within a file root")
    p_move.add_argument("source")
    p_move.add_argument("dest")
    p_del = sub.add_parser("delete", help="delete a file (or dir with -r)")
    p_del.add_argument("path")
    p_del.add_argument("-r", "--recursive", action="store_true")

    p_shot = sub.add_parser("screenshot", help="capture the host screen")
    p_shot.add_argument("local")
    p_shot.add_argument("--format", choices=["png", "bmp"], default="png")
    p_shot.add_argument("--monitor", type=int, default=None)
    sub.add_parser("clipboard-get", help="read the host clipboard text")
    p_clip = sub.add_parser("clipboard-set", help="set the host clipboard text")
    p_clip.add_argument("text")
    p_uia = sub.add_parser("uia", help="UI Automation (JSON params)")
    p_uia.add_argument("uia_action")
    p_uia.add_argument("params", nargs="?", default="{}",
                       help="JSON object of extra parameters")

    p_tail = sub.add_parser("audit-tail", help="tail the agent audit log")
    p_tail.add_argument("n", nargs="?", type=int, default=50)
    sub.add_parser("update-status", help="self-update status")

    args = parser.parse_args(argv)
    try:
        client = Client(args.base, args.token)
        root = args.root
        if args.command == "status":
            print_json(client.status())
        elif args.command == "exec":
            if not args.exec_command:
                parser.error("exec requires a command")
            payload_cmd = " ".join(args.exec_command)
            if args.no_wait:
                print_json(client.exec_submit(
                    payload_cmd, shell=args.shell, timeout_s=args.timeout,
                    cwd=args.cwd))
                return 0
            result = client.exec_run(
                payload_cmd, shell=args.shell, timeout_s=args.timeout,
                cwd=args.cwd)
            print_json(result)
            code = result.get("exit_code")
            return 0 if code == 0 else 1
        elif args.command == "jobs":
            print_json(client.jobs_list())
        elif args.command == "job":
            print_json(client.job_get(args.job_id, 0, 0, 16 * 1024 * 1024))
        elif args.command == "job-cancel":
            print_json(client.job_cancel(args.job_id))
        elif args.command == "spawn":
            if not args.spawn_command:
                parser.error("spawn requires a command")
            print_json(client.process_spawn(
                " ".join(args.spawn_command), shell=args.shell,
                cwd=args.cwd))
        elif args.command == "spawn-gui":
            print_json(client.process_spawn(
                gui=True, executable=args.executable,
                args=args.gui_args, cwd=args.cwd))
        elif args.command == "wol":
            print_json(client.wol(args.mac, broadcast=args.broadcast,
                                  port=args.port))
        elif args.command == "processes":
            print_json(client.processes_list())
        elif args.command == "process":
            print_json(client.process_get(args.process_id,
                                          tail_bytes=args.tail))
        elif args.command == "kill":
            print_json(client.process_kill(args.process_id))
        elif args.command == "list":
            print_json(client.file_list(args.path, root=root))
        elif args.command == "tree":
            print_json(client.file_tree(args.path, root=root,
                                        max_depth=args.depth))
        elif args.command == "get":
            result = client.download(args.remote, args.local, root=root)
            print(f"wrote {result['local']} ({result['size']} bytes, "
                  f"sha256 {result['sha256']})")
        elif args.command == "put":
            print_json(client.upload(args.local, args.remote, root=root,
                                     upload_id=args.resume))
        elif args.command == "hash":
            print_json(client.file_hash(args.remote, root=root))
        elif args.command == "mkdir":
            print_json(client.file_mkdir(args.path, root=root))
        elif args.command == "move":
            print_json(client.file_move(args.source, args.dest, root=root))
        elif args.command == "delete":
            print_json(client.file_delete(args.path,
                                          recursive=args.recursive,
                                          root=root))
        elif args.command == "screenshot":
            print_json(client.screenshot(args.local, fmt=args.format,
                                         monitor=args.monitor))
        elif args.command == "clipboard-get":
            print_json(client.clipboard_get())
        elif args.command == "clipboard-set":
            print_json(client.clipboard_set(args.text))
        elif args.command == "uia":
            params = json.loads(args.params)
            if not isinstance(params, dict):
                parser.error("uia params must be a JSON object")
            print_json(client.uia(args.uia_action, **params))
        elif args.command == "audit-tail":
            print_json(client.audit_tail(args.n))
        elif args.command == "update-status":
            print_json(client.update_status())
        return 0
    except BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
