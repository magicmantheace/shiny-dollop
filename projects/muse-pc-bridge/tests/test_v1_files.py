"""V1-S4 tests: chunked/resumable transfers, hash endpoint, ranged
reads, recursive ops, multiple file roots, and the client library
round-tripping against a real (loopback) agent."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))
sys.path.insert(0, str(PROJECT_DIR / "client"))

import bridge_agent  # noqa: E402
import bridge_client  # noqa: E402

TOKEN = "test-token-v1-files"
CHUNK = 64 * 1024


class Http:
    def __init__(self, base: str, token: str):
        self.base = base
        self.token = token

    def request(self, method, path, payload=None, raw=None):
        headers = {"Authorization": f"Bearer {self.token}"}
        data = raw
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                return resp.status, (json.loads(body.decode("utf-8"))
                                     if body else {})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}


class FilesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.files_root = root / "bridge-files"
        cls.extra_root = root / "extra-files"
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(cls.files_root),
            "file_roots": [
                {"name": "default", "path": str(cls.files_root)},
                {"name": "extra", "path": str(cls.extra_root)},
            ],
            "audit_log": str(root / "logs" / "audit.jsonl"),
            "state_dir": str(root / "state"),
        })
        cls.server = bridge_agent.create_server(cfg)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.http = Http(cls.base, TOKEN)
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.client = bridge_client.BridgeClient(cls.base, TOKEN)

    @classmethod
    def tearDownClass(cls):
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def payload(self, size: int) -> bytes:
        # Deterministic pseudo-random content.
        return bytes((i * 31 + 7) % 256 for i in range(size))

    # -- hash + ranged get ------------------------------------------------
    def test_hash_and_ranged_get(self):
        data = self.payload(150_000)
        status, obj = self.http.request("POST", "/v1/file/put", {
            "path": "blob.bin",
            "content_b64": base64.b64encode(data).decode()})
        self.assertEqual(status, 200)
        status, h = self.http.request("GET", "/v1/file/hash?path=blob.bin")
        self.assertEqual(status, 200)
        self.assertEqual(h["size"], len(data))
        self.assertEqual(h["sha256"], hashlib.sha256(data).hexdigest())
        status, part = self.http.request(
            "GET", "/v1/file/get?path=blob.bin&offset=100000&length=1000")
        self.assertEqual(status, 200)
        self.assertEqual(base64.b64decode(part["content_b64"]),
                         data[100000:101000])
        self.assertEqual(part["offset"], 100000)

    # -- chunked upload -----------------------------------------------------
    def test_chunked_upload_roundtrip_via_client(self):
        data = self.payload(200_000)
        local = Path(self.tmp.name) / "up.bin"
        local.write_bytes(data)
        result = self.client.upload(local, "big/up.bin", chunk_bytes=CHUNK)
        self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(result["size"], len(data))
        status, h = self.http.request("GET", "/v1/file/hash?path=big/up.bin")
        self.assertEqual(h["sha256"], hashlib.sha256(data).hexdigest())
        # And back down again through the client's ranged download.
        down = Path(self.tmp.name) / "down.bin"
        got = self.client.download("big/up.bin", down)
        self.assertEqual(got["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(down.read_bytes(), data)

    def test_upload_resume_after_partial(self):
        data = self.payload(200_000)
        local = Path(self.tmp.name) / "resume.bin"
        local.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        status, started = self.http.request("POST", "/v1/file/upload/start", {
            "path": "resumed.bin", "size": len(data), "sha256": sha,
            "chunk_bytes": CHUNK})
        self.assertEqual(status, 201)
        upload_id = started["upload_id"]
        total = started["chunk_count"]
        self.assertGreaterEqual(total, 3)
        # Simulate an interrupted client: send only the first two chunks.
        for index in (0, 1):
            status, _ = self.http.request(
                "PUT", f"/v1/file/upload/{upload_id}/{index}",
                raw=data[index * CHUNK:(index + 1) * CHUNK])
            self.assertEqual(status, 200)
        status, prog = self.http.request("GET", f"/v1/file/upload/{upload_id}")
        self.assertEqual(prog["received_chunks"], [0, 1])
        # Resume through the client library with the same upload id.
        result = self.client.upload(local, "resumed.bin", upload_id=upload_id,
                                    chunk_bytes=CHUNK)
        self.assertEqual(result["sha256"], sha)
        status, h = self.http.request("GET", "/v1/file/hash?path=resumed.bin")
        self.assertEqual(h["sha256"], sha)

    def test_upload_hash_mismatch_rejected(self):
        data = self.payload(70_000)
        status, started = self.http.request("POST", "/v1/file/upload/start", {
            "path": "bad.bin", "size": len(data), "sha256": "0" * 64,
            "chunk_bytes": CHUNK})
        self.assertEqual(status, 201)
        upload_id = started["upload_id"]
        for index in range(started["chunk_count"]):
            self.http.request("PUT", f"/v1/file/upload/{upload_id}/{index}",
                              raw=data[index * CHUNK:(index + 1) * CHUNK])
        status, obj = self.http.request(
            "POST", f"/v1/file/upload/{upload_id}/complete", {})
        self.assertEqual(status, 400)
        self.assertIn("sha256", obj["error"])
        status, _ = self.http.request("GET", "/v1/file/hash?path=bad.bin")
        self.assertEqual(status, 404)

    def test_upload_wrong_chunk_size_rejected(self):
        status, started = self.http.request("POST", "/v1/file/upload/start", {
            "path": "x.bin", "size": 100, "chunk_bytes": CHUNK})
        self.assertEqual(status, 201)
        status, _ = self.http.request(
            "PUT", f"/v1/file/upload/{started['upload_id']}/0", raw=b"short")
        self.assertEqual(status, 400)

    def test_upload_discard(self):
        status, started = self.http.request("POST", "/v1/file/upload/start", {
            "path": "gone.bin", "size": 10, "chunk_bytes": CHUNK})
        self.assertEqual(status, 201)
        status, _ = self.http.request(
            "DELETE", f"/v1/file/upload/{started['upload_id']}")
        self.assertEqual(status, 200)
        status, _ = self.http.request(
            "GET", f"/v1/file/upload/{started['upload_id']}")
        self.assertEqual(status, 404)

    # -- recursive ops + roots ---------------------------------------------
    def test_tree_mkdir_move_delete(self):
        s, _ = self.http.request("POST", "/v1/file/mkdir",
                                 {"path": "dir/sub"})
        self.assertEqual(s, 200)
        status, _ = self.http.request("POST", "/v1/file/put", {
            "path": "dir/sub/a.txt",
            "content_b64": base64.b64encode(b"alpha").decode()})
        self.assertEqual(status, 200)
        s, tree = self.http.request("GET", "/v1/file/tree?path=dir")
        self.assertEqual(s, 200)
        names = json.dumps(tree)
        self.assertIn("sub", names)
        self.assertIn("a.txt", names)
        s, _ = self.http.request("POST", "/v1/file/move",
                                 {"from": "dir/sub/a.txt",
                                  "to": "dir/b.txt"})
        self.assertEqual(s, 200)
        s, _ = self.http.request("GET", "/v1/file/hash?path=dir/sub/a.txt")
        self.assertEqual(s, 404)
        s, h = self.http.request("GET", "/v1/file/hash?path=dir/b.txt")
        self.assertEqual(s, 200)
        # Non-recursive delete of a non-empty dir must fail...
        s, _ = self.http.request("POST", "/v1/file/delete", {"path": "dir"})
        self.assertEqual(s, 400)
        # ...and recursive delete works; the root itself is protected.
        s, _ = self.http.request("POST", "/v1/file/delete",
                                 {"path": "dir", "recursive": True})
        self.assertEqual(s, 200)
        s, _ = self.http.request("POST", "/v1/file/delete",
                                 {"path": ".", "recursive": True})
        self.assertEqual(s, 400)

    def test_tree_does_not_follow_symlink_out_of_root(self):
        # Codex PR #27: /v1/file/tree recursed through directory
        # symlinks with no containment check on descendants (only the
        # requested path went through resolve_in_root), leaking the
        # names/sizes of files outside the configured root.
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir(exist_ok=True)
        (outside / "secret-outside.txt").write_text("shh",
                                                    encoding="utf-8")
        try:
            os.symlink(outside, self.files_root / "escape-link",
                       target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("cannot create symlinks on this platform")
        s, tree = self.http.request("GET", "/v1/file/tree?path=.")
        self.assertEqual(s, 200)
        blob = json.dumps(tree)
        self.assertNotIn("secret-outside.txt", blob)
        self.assertNotIn("escape-link", blob)
        # A symlink whose target stays INSIDE the root is still listed
        # and followed — only escapes are skipped.
        real_dir = self.files_root / "real-dir"
        real_dir.mkdir(exist_ok=True)
        (real_dir / "inside.txt").write_text("ok", encoding="utf-8")
        try:
            os.symlink(real_dir, self.files_root / "inside-link",
                       target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        s, tree = self.http.request("GET", "/v1/file/tree?path=.")
        self.assertEqual(s, 200)
        self.assertIn("inside.txt", json.dumps(tree))

    def test_second_named_root(self):
        result = self.client.put_small(self._write_local("note.txt", b"hi"),
                                       "note.txt", root="extra")
        self.assertEqual(result["root"], "extra")
        info = self.client.file_hash("note.txt", root="extra")
        self.assertEqual(info["sha256"],
                         hashlib.sha256(b"hi").hexdigest())
        status, _ = self.http.request(
            "GET", "/v1/file/hash?path=note.txt&root=nope")
        self.assertEqual(status, 400)
        # Not visible in the default root.
        status, _ = self.http.request("GET", "/v1/file/hash?path=note.txt")
        self.assertEqual(status, 404)

    def test_escape_still_confined(self):
        status, _ = self.http.request(
            "GET", "/v1/file/get?path=" + "..%2F..%2Fsecret.txt")
        self.assertIn(status, (400, 403, 404))
        status, _ = self.http.request("POST", "/v1/file/mkdir",
                                      {"path": "../evil"})
        self.assertIn(status, (400, 403))

    def _write_local(self, name: str, data: bytes) -> Path:
        path = Path(self.tmp.name) / name
        path.write_bytes(data)
        return path

    # -- client library exec -------------------------------------------------
    def test_client_exec_run(self):
        if os.name == "nt":
            cmd, shell = "echo client-hello", "cmd"
        else:
            cmd, shell = "echo client-hello", "posix"
        result = self.client.exec_run(cmd, shell=shell)
        self.assertEqual(result["state"], "done")
        self.assertIn("client-hello", result["stdout"])
        self.assertEqual(result["exit_code"], 0)

    def test_client_job_wait_drains_large_output(self):
        # Codex PR #27: job_wait() advanced its poll offsets straight
        # to the stream totals (stdout_bytes), but one response carries
        # at most max_output_bytes (256 KiB) of text — everything past
        # the first slice was skipped, even for a finished job.
        # 600_000 bytes are retained in full (cap is 8 MiB), so every
        # byte must come back through job_wait, untruncated.
        if os.name == "nt":
            cmd = "[Console]::Out.Write('x' * 600000)"
            shell = "powershell"
        else:
            cmd = "head -c 600000 /dev/zero | tr '\\0' 'x'"
            shell = "posix"
        result = self.client.exec_run(cmd, shell=shell)
        self.assertEqual(result["state"], "done")
        self.assertFalse(result["stdout_truncated"])
        if os.name == "nt":
            self.assertGreaterEqual(result["stdout"].count("x"), 600000)
        else:
            self.assertEqual(result["stdout"], "x" * 600000)


if __name__ == "__main__":
    unittest.main()
