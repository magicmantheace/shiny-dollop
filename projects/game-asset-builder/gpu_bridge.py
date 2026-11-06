"""GPU-stage dispatch: run the mesh/texture stages on the owner's PC
through the Muse PC Bridge HTTP API (stdlib only).

The bridge is the sanctioned route to the PC (see the muse-pc-bridge
project). Configuration comes from the environment — never from files,
never committed:

  GAB_BRIDGE_URL    default http://100.104.193.31:8765
  GAB_BRIDGE_TOKEN  required (the bridge agent's bearer token)
  GAB_BRIDGE_PROXY  optional explicit proxy URL, or "none" for direct
  GAB_LAB_DIR       PC-side lab directory, default D:\\asset-forge-lab

The PC lab holds the model venvs and the bake-off's stage_runner.py
(spec-driven runner that samples nvidia-smi and reports peak/after-exit
VRAM). This module uploads the project's stage scripts + inputs, runs
each stage as its own job, and downloads the outputs — the mesh process
has fully exited (and its VRAM release is verified) before the texture
stage is dispatched, so the unload discipline is structural.
"""

import base64
import hashlib
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

CHUNK = 8 * 1024 * 1024
DEFAULT_URL = "http://100.104.193.31:8765"
DEFAULT_LAB = r"D:\asset-forge-lab"


class BridgeError(Exception):
    pass


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class BridgeRunner:
    def __init__(self, base: str | None = None, token: str | None = None,
                 proxy: str | None = None, lab_dir: str | None = None):
        self.base = (base or os.environ.get("GAB_BRIDGE_URL")
                     or DEFAULT_URL).rstrip("/")
        self.token = (token or os.environ.get("GAB_BRIDGE_TOKEN")
                      or os.environ.get("BRIDGE_TOKEN"))
        if not self.token:
            raise BridgeError(
                "no bridge token: set GAB_BRIDGE_TOKEN in the environment")
        self.lab_dir = lab_dir or os.environ.get("GAB_LAB_DIR") \
            or DEFAULT_LAB
        proxy = proxy if proxy is not None \
            else os.environ.get("GAB_BRIDGE_PROXY")
        handler = urllib.request.ProxyHandler(
            {} if proxy in (None, "", "none")
            else {"http": proxy, "https": proxy})
        self._opener = urllib.request.build_opener(handler)
        self._file_root = None

    # -- transport ------------------------------------------------------
    def _send(self, method, path, data, headers, timeout):
        # GETs are idempotent and are retried with backoff: the route to
        # the agent occasionally drops a connection mid-poll, and a
        # dropped poll must not kill a stage — jobs live server-side and
        # keep running (learned the hard way during the Ember Dragon
        # run: the paint job finished fine after the poller died).
        attempts = 5 if method == "GET" else 1
        last_exc = None
        for attempt in range(attempts):
            req = urllib.request.Request(self.base + path, data=data,
                                         method=method)
            for key, value in headers.items():
                req.add_header(key, value)
            req.add_header("Authorization", f"Bearer {self.token}")
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                raise BridgeError(f"HTTP {exc.code} from agent: {body}") \
                    from exc
            except (urllib.error.URLError, ConnectionError,
                    http.client.HTTPException, TimeoutError,
                    OSError) as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(2 * (attempt + 1) ** 2)
        raise BridgeError(f"cannot reach agent at {self.base}: "
                          f"{last_exc}") from last_exc

    def request(self, method, path, payload=None, timeout=120):
        data = headers = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
        return self._send(method, path, data, headers or {}, timeout)

    def request_raw(self, method, path, data, timeout=300):
        return self._send(method, path, data,
                          {"Content-Type": "application/octet-stream"},
                          timeout)

    @staticmethod
    def _qs(params):
        clean = {k: v for k, v in params.items() if v is not None}
        return ("?" + urllib.parse.urlencode(clean)) if clean else ""

    # -- API ------------------------------------------------------------
    def status(self):
        return self.request("GET", "/v1/status")

    @property
    def file_root(self) -> str:
        if self._file_root is None:
            self._file_root = self.status()["file_root"]
        return self._file_root

    def upload(self, local: str, remote: str) -> dict:
        size = os.path.getsize(local)
        sha = _sha256_file(local)
        started = self.request("POST", "/v1/file/upload/start", {
            "path": remote, "size": size, "sha256": sha,
            "chunk_bytes": CHUNK})
        upload_id = started["upload_id"]
        status = self.request("GET", f"/v1/file/upload/{upload_id}")
        server_chunk = int(status["chunk_size"])
        received = set(status["received_chunks"])
        with open(local, "rb") as fh:
            for index in range(int(status["chunk_count"])):
                if index in received:
                    continue
                fh.seek(index * server_chunk)
                self.request_raw(
                    "PUT", f"/v1/file/upload/{upload_id}/{index}",
                    fh.read(server_chunk))
        result = self.request(
            "POST", f"/v1/file/upload/{upload_id}/complete", {})
        if result.get("sha256") != sha:
            raise BridgeError("sha256 mismatch after chunked upload")
        return result

    def file_hash(self, remote: str) -> dict:
        return self.request("GET", "/v1/file/hash"
                            + self._qs({"path": remote}))

    def download(self, remote: str, local: str) -> dict:
        info = self.file_hash(remote)
        size = info["size"]
        os.makedirs(os.path.dirname(local) or ".", exist_ok=True)
        digest = hashlib.sha256()
        offset = 0
        with open(local, "wb") as out:
            while offset < size:
                length = min(CHUNK, size - offset)
                part = self.request("GET", "/v1/file/get" + self._qs(
                    {"path": remote, "offset": offset, "length": length}))
                block = base64.b64decode(part["content_b64"])
                if len(block) != length:
                    raise BridgeError(
                        f"short read at {offset}: {len(block)} != {length}")
                out.write(block)
                digest.update(block)
                offset += len(block)
        if digest.hexdigest() != info["sha256"]:
            raise BridgeError("sha256 mismatch on download")
        return {"path": remote, "size": size,
                "sha256": digest.hexdigest(), "local": local}

    # -- exec jobs --------------------------------------------------------
    def exec_job(self, command, timeout_s=600, poll_s=5.0,
                 shell="powershell"):
        job = self.request("POST", "/v1/exec", {
            "command": command, "shell": shell, "timeout_s": timeout_s})
        return self.wait_job(job["job_id"], timeout_s=timeout_s,
                             poll_s=poll_s)

    def wait_job(self, job_id, timeout_s=600, poll_s=5.0):
        """Poll an existing job to completion. Also the reattach path:
        if a caller died while a stage job kept running server-side,
        wait_job(job_id) picks it back up."""
        out_off = err_off = 0
        out_parts, err_parts = [], []
        deadline = time.time() + timeout_s + 300
        while True:
            snap = self.request("GET", f"/v1/jobs/{job_id}" + self._qs(
                {"stdout_offset": out_off, "stderr_offset": err_off}))
            out_parts.append(snap.get("stdout", ""))
            err_parts.append(snap.get("stderr", ""))
            out_off = snap["stdout_bytes"]
            err_off = snap["stderr_bytes"]
            if snap["state"] in ("done", "failed", "killed"):
                snap["stdout"] = "".join(out_parts)
                snap["stderr"] = "".join(err_parts)
                return snap
            if time.time() > deadline:
                raise BridgeError(f"job {job_id} still {snap['state']} "
                                  "after deadline")
            time.sleep(poll_s)

    def powershell(self, script: str, timeout_s=300):
        return self.exec_job(script, timeout_s=timeout_s)

    # -- lab staging ------------------------------------------------------
    def _copy_on_pc(self, src: str, dst: str):
        def q(p):
            return "'" + p.replace("'", "''") + "'"
        job = self.powershell(
            f"New-Item -ItemType Directory -Force "
            f"-Path (Split-Path {q(dst)}) | Out-Null; "
            f"Copy-Item {q(src)} {q(dst)} -Force; "
            f"(Get-Item {q(dst)}).Length")
        if job["state"] != "done" or job.get("exit_code") != 0:
            raise BridgeError(f"PC copy {src} -> {dst} failed: "
                              f"{job.get('stderr', '')[:400]}")
        return job

    def stage_to_lab(self, local: str, lab_rel: str) -> str:
        """Upload a local file into the lab via the bridge file root."""
        name = os.path.basename(local)
        self.upload(local, name)
        dst = self.lab_dir + "\\" + lab_rel
        self._copy_on_pc(self.file_root + "\\" + name, dst)
        return dst

    def fetch_from_lab(self, lab_rel: str, local: str) -> dict:
        staged = "gab_" + os.path.basename(lab_rel)
        self._copy_on_pc(self.lab_dir + "\\" + lab_rel,
                         self.file_root + "\\" + staged)
        return self.download(staged, local)

    def gpu_used_mib(self) -> int:
        job = self.powershell(
            "nvidia-smi --query-gpu=memory.used "
            "--format=csv,noheader,nounits")
        return int(job["stdout"].strip().splitlines()[0])

    def run_lab_stage(self, spec: dict, timeout_s: int) -> dict:
        """Run one lab stage via the bake-off's stage_runner.py and
        return its result JSON (exit code, wall time, VRAM samples)."""
        spec_name = "spec_gab_" + spec["name"] + ".json"
        local_spec = os.path.join(
            os.environ.get("TMPDIR", "/tmp"), spec_name)
        with open(local_spec, "w", encoding="utf-8") as fh:
            json.dump(spec, fh, indent=1)
        self.stage_to_lab(local_spec, "scripts\\" + spec_name)
        runner = self.lab_dir + r"\venvs\hunyuan\Scripts\python.exe"
        stage_runner = self.lab_dir + r"\scripts\stage_runner.py"
        spec_path = self.lab_dir + "\\scripts\\" + spec_name
        job = self.exec_job(
            f"& '{runner}' '{stage_runner}' '{spec_path}'",
            timeout_s=timeout_s, poll_s=10.0)
        result_rel = spec["result"].replace(self.lab_dir + "\\", "")
        local_result = local_spec.replace(".json", "_result.json")
        self.fetch_from_lab(result_rel, local_result)
        with open(local_result, encoding="utf-8") as fh:
            result = json.load(fh)
        result["job_state"] = job["state"]
        result["job_stdout_tail"] = job.get("stdout", "")[-500:]
        return result
