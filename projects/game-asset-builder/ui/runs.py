"""Pipeline run management for the local UI.

A run is the existing CLI (``asset_builder.py run ...``) spawned as
a subprocess from the project directory, inheriting this process's
environment — which is how the bridge token reaches the GPU stages
(``GAB_BRIDGE_TOKEN`` / ``BRIDGE_TOKEN``; see gpu_bridge.py). Runs
are tracked in memory only: the durable record of a finished run is
the pipeline's own ``outputs/<slug>/run-manifest.json`` plus its
catalog entry, exactly as with a CLI run.

Inputs are validated before anything spawns; an invalid request
raises ValueError and starts nothing.
"""

import os
import subprocess
import sys
import threading
import time
import uuid

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = ("winged-creature", "quadruped", "biped")
ROTATIONS = (0, 90, 180, 270)
_MAX_OUTPUT_LINES = 500


def build_run_argv(spec: dict) -> list[str]:
    """Validate a run request and turn it into a CLI argv.

    ``spec`` keys mirror the CLI flags: concept, name, template,
    prop, ears, no_arms, rotate_z, target_verts, prop_target_verts,
    resume.
    """
    concept = (spec.get("concept") or "").strip()
    if not concept or not os.path.isfile(concept):
        raise ValueError(f"concept image not found: {concept!r}")
    name = (spec.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    template = spec.get("template") or "winged-creature"
    if template not in TEMPLATES:
        raise ValueError(f"unknown template: {template!r} "
                         f"(choose from {', '.join(TEMPLATES)})")
    rotate_z = int(spec.get("rotate_z") or 0)
    if rotate_z not in ROTATIONS:
        raise ValueError(f"rotate_z must be one of {ROTATIONS}")
    argv = [sys.executable,
            os.path.join(PROJECT_DIR, "asset_builder.py"), "run",
            "--concept", concept, "--name", name,
            "--template", template,
            "--rotate-z", str(rotate_z),
            "--target-verts", str(int(spec.get("target_verts") or 50000)),
            "--prop-target-verts",
            str(int(spec.get("prop_target_verts") or 30000))]
    if spec.get("prop"):
        argv.append("--prop")
    if spec.get("ears"):
        argv.append("--ears")
    if spec.get("no_arms"):
        argv.append("--no-arms")
    if spec.get("resume"):
        argv.append("--resume")
    return argv


class RunManager:
    """Starts and tracks pipeline subprocesses (one at a time is the
    norm — the GPU stages serialize on the owner's PC anyway — but
    nothing here forbids overlap)."""

    def __init__(self):
        self._runs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, spec: dict) -> dict:
        argv = build_run_argv(spec)  # raises ValueError before spawning
        run_id = uuid.uuid4().hex[:12]
        proc = subprocess.Popen(
            argv, cwd=PROJECT_DIR, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1)
        record = {
            "id": run_id,
            "state": "running",
            "exit_code": None,
            "started_at": time.time(),
            "finished_at": None,
            "name": spec.get("name"),
            "argv": argv[2:],  # the CLI words, for display
            "output": [],
        }
        with self._lock:
            self._runs[run_id] = record
        thread = threading.Thread(target=self._pump,
                                  args=(record, proc), daemon=True)
        thread.start()
        return self._public(record)

    def _pump(self, record: dict, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            record["output"].append(line.rstrip("\n"))
            del record["output"][:-_MAX_OUTPUT_LINES]
        proc.wait()
        record["exit_code"] = proc.returncode
        record["state"] = "done" if proc.returncode == 0 else "failed"
        record["finished_at"] = time.time()

    def _public(self, record: dict) -> dict:
        return {
            "id": record["id"],
            "state": record["state"],
            "exit_code": record["exit_code"],
            "started_at": record["started_at"],
            "finished_at": record["finished_at"],
            "name": record["name"],
            "argv": record["argv"],
            "output_tail": record["output"][-60:],
        }

    def get(self, run_id: str) -> dict | None:
        with self._lock:
            record = self._runs.get(run_id)
        return self._public(record) if record else None

    def list(self) -> list[dict]:
        with self._lock:
            records = list(self._runs.values())
        return [self._public(r) for r in
                sorted(records, key=lambda r: r["started_at"],
                       reverse=True)]
