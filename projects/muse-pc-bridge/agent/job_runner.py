#!/usr/bin/env python3
"""Durable job runner — muse-pc-bridge (durable job runner release).

A general-purpose, checkpointed runner for LONG jobs on the
owner's PC: LoRA training runs, the comic generation queue, the
stills harvester, Underreach asset GPU stages — anything whose
driver used to live on Muse's VM and died whenever the VM or
runtime restarted mid-run.

This is NOT the v1.2 resident queue (queue_runner.py). The queue
runs short, pre-approved single commands through the agent's own
executor (900 s cap, interrupted jobs failed on restart). This
runner is the opposite trade:

- its own supervised, detached process (a sibling of the agent,
  NOT a thread inside it), so jobs survive agent restarts, VM
  restarts, and run for hours — there is no stage-length cap
  unless the manifest sets one;
- multi-stage jobs with a checkpoint after every stage;
- an interrupted job RESUMES from its last completed stage
  instead of failing or starting over.

The runner is deliberately generic — zero domain knowledge. A
job is a JSON manifest; consumers bring their own stage commands
and scripts. The runner knows stages, checkpoints, flags, and
GPU yield. Nothing else.

Store, under the agent's configured state directory:

    <state_dir>/jobs/
      queue/        manifests waiting to be claimed (*.json)
      manifests/    the accepted manifest per job (<id>.json)
      state/        the checkpoint record per job (<id>.json)
      stop/         per-job stop flags (drop a file named <id>)
      logs/         merged stage output per job (<id>.log)
      PAUSED        global pause flag (owner's kill switch)
      events.jsonl  lifecycle audit (append-only)
      runner-status.json / runner-heartbeat.json

Control surface — files only, by design (see docs/JOB_RUNNER.md):
submit = write a manifest into queue/ (via the bridge file API,
an exec, or locally); status = read state/<id>.json; pause-all =
create PAUSED (the running stage's process tree is killed
promptly; the job returns to queued and resumes from the same
stage when the flag is removed); stop one job = create
stop/<id>. No HTTP routes: job submission must keep working
while the agent itself is down or restarting, which is the
failure this component exists to survive.

Manifest schema:

    {
      "name": "comic-ep3-batch",              (required)
      "workdir": "D:\\image-gen\\comic",       (required)
      "stages": [                              (required, >= 1)
        {"name": "generate",                    (optional)
         "command": ["python", "gen.py"],       argv list, OR
         "command": "python gen.py --all",      a string + "shell"
         "shell": "cmd",                        (string commands)
         "timeout_s": 7200,                     (optional; none = no cap)
         "retries": 1}                          (optional, default 0)
      ],
      "gpu": true,                             (optional, default false)
      "gpu_blockers": ["blender.exe"],         (optional extra
                                                contention exes)
      "rerun": false,                          (optional: on resume,
                                                re-run ALL stages)
      "id": "ep3-batch-2026-11-24"             (optional; auto uuid)
    }

Failure semantics: a stage exiting non-zero is retried up to its
`retries` count, then the job is marked failed with the stage
index and exit code in the state record. Nothing retries
silently beyond that. A stage orphaned by a runner crash is
killed at recovery (its output is unmonitored; two copies of a
GPU stage running at once is the failure being prevented) and
the stage re-runs from its checkpoint boundary.

GPU yield (`gpu: true` jobs): before the job starts and at every
stage boundary, presence.gpu_contention() must say the GPU is
free (no known game running — launchers do not count — and
utilization under the threshold). While contended the job waits,
checkpointed, state `waiting_for_gpu` — never failed for waiting.

Auditability: lifecycle events (submitted, stage_started,
stage_finished, stage_failed, pause_kill, stop_kill, resume,
orphan_killed, gpu_wait, completed, failed, ...) are appended to
events.jsonl. Manifest contents are archived under manifests/;
command text is not duplicated into the event log, and no
credential is ever written there.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import boot_beacon  # noqa: E402
import bridge_agent  # noqa: E402
import bridge_update  # noqa: E402
import presence  # noqa: E402

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SHELLS = ("powershell", "cmd", "posix")
_MAX_STAGES = 200
_POLL_S = 0.1


def _with_sharing_retry(op, attempts: int = 10, delay_s: float = 0.15):
    """Record-file operation with retries for transient Windows
    sharing violations (same pattern as queue_runner's)."""
    last: PermissionError | None = None
    for _ in range(max(1, attempts)):
        try:
            return op()
        except PermissionError as exc:
            last = exc
            time.sleep(delay_s)
    raise last  # type: ignore[misc]


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(obj, indent=2)

    def write_and_replace() -> None:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    _with_sharing_retry(write_and_replace)


# ---------------------------------------------------------------------------
# Manifest validation (pure — unit-tested)
# ---------------------------------------------------------------------------

def validate_manifest(obj) -> dict:
    """Validate a job manifest and return the normalized form.
    Raises ValueError on any schema problem."""
    if not isinstance(obj, dict):
        raise ValueError("manifest must be a JSON object")
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("field 'name' (non-empty string) is required")
    workdir = obj.get("workdir")
    if not isinstance(workdir, str) or not workdir.strip():
        raise ValueError("field 'workdir' (non-empty string) is required")
    stages_raw = obj.get("stages")
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ValueError("field 'stages' (non-empty list) is required")
    if len(stages_raw) > _MAX_STAGES:
        raise ValueError(f"too many stages (max {_MAX_STAGES})")
    stages = []
    for i, raw in enumerate(stages_raw):
        if not isinstance(raw, dict):
            raise ValueError(f"stage {i} must be an object")
        command = raw.get("command")
        shell = raw.get("shell")
        if isinstance(command, list):
            if not command or not all(
                    isinstance(a, str) and a for a in command):
                raise ValueError(
                    f"stage {i}: 'command' list must be non-empty "
                    f"strings")
            if shell is not None:
                raise ValueError(
                    f"stage {i}: 'shell' applies to string commands only")
            norm_command: list | str = list(command)
        elif isinstance(command, str) and command.strip():
            if shell is None:
                shell = bridge_agent.default_shell()
            if shell not in _SHELLS:
                raise ValueError(f"stage {i}: unknown shell {shell!r}")
            norm_command = command
        else:
            raise ValueError(
                f"stage {i}: 'command' (argv list or string) is required")
        timeout = raw.get("timeout_s")
        if timeout is not None:
            try:
                timeout = float(timeout)
            except (TypeError, ValueError):
                raise ValueError(f"stage {i}: timeout_s must be a number")
            if timeout <= 0:
                raise ValueError(f"stage {i}: timeout_s must be positive")
        retries = raw.get("retries", 0)
        if not isinstance(retries, int) or isinstance(retries, bool) \
                or retries < 0 or retries > 10:
            raise ValueError(f"stage {i}: retries must be an int in 0..10")
        stage_name = raw.get("name")
        if stage_name is not None and not isinstance(stage_name, str):
            raise ValueError(f"stage {i}: name must be a string")
        stages.append({
            "name": stage_name or f"stage-{i}",
            "command": norm_command,
            "shell": shell,
            "timeout_s": timeout,
            "retries": retries,
        })
    gpu = obj.get("gpu", False)
    if not isinstance(gpu, bool):
        raise ValueError("field 'gpu' must be a boolean")
    rerun = obj.get("rerun", False)
    if not isinstance(rerun, bool):
        raise ValueError("field 'rerun' must be a boolean")
    blockers = obj.get("gpu_blockers", [])
    if not isinstance(blockers, list) or not all(
            isinstance(b, str) and b for b in blockers):
        raise ValueError("field 'gpu_blockers' must be a list of strings")
    job_id = obj.get("id")
    if job_id is not None:
        if not isinstance(job_id, str) or not _ID_RE.match(job_id):
            raise ValueError(
                "field 'id' must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    return {
        "name": name.strip(),
        "workdir": workdir,
        "stages": stages,
        "gpu": gpu,
        "gpu_blockers": list(blockers),
        "rerun": rerun,
        "id": job_id,
    }


def _blocker_patterns(names) -> tuple:
    """Exact-name contention blockers as fullmatch patterns for
    presence.detect_games."""
    return tuple(re.compile(re.escape(str(n).lower()))
                 for n in (names or ()))


# ---------------------------------------------------------------------------
# Status (read-only; used by the CLI and the tests)
# ---------------------------------------------------------------------------

def jobs_status(jobs_dir: Path) -> dict:
    jobs_dir = Path(jobs_dir)
    counts: dict[str, int] = {}
    jobs: list[dict] = []
    state_dir_path = jobs_dir / "state"
    try:
        files = sorted(state_dir_path.glob("*.json"))
    except OSError:
        files = []
    for f in files:
        try:
            record = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        state = str(record.get("state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
        jobs.append({
            "id": record.get("id"), "name": record.get("name"),
            "state": state,
            "next_stage": record.get("next_stage"),
            "stage_count": len(record.get("stages") or []),
            "submitted_at": record.get("submitted_at"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "failed_stage": record.get("failed_stage"),
            "exit_code": record.get("exit_code"),
            "reason": record.get("reason"),
            "waiting_for_gpu": record.get("waiting_for_gpu"),
        })
    jobs.sort(key=lambda j: (j.get("submitted_at") or 0,
                             str(j.get("id"))))
    paused = (jobs_dir / "PAUSED").exists()
    return {"paused": paused, "counts": counts, "jobs": jobs}


# ---------------------------------------------------------------------------
# The runner engine
# ---------------------------------------------------------------------------

class JobRunner:
    """Sequential durable-job engine. One job at a time.

    The engine is transport-free: `run()` blocks until the stop
    event is set; tests drive it in a thread, the worker process
    drives it in main.
    """

    def __init__(self, jobs_dir: Path, state_dir: Path,
                 cfg: dict | None = None, *,
                 poll_interval_s: float = 0.25,
                 gpu_poll_s: float = 30.0,
                 gpu_threshold_pct: int = 90,
                 process_names_fn=None, gpu_fn=None):
        self.jobs_dir = Path(jobs_dir)
        self.state_dir = Path(state_dir)
        self.cfg = cfg or {}
        self.queue_dir = self.jobs_dir / "queue"
        self.manifests_dir = self.jobs_dir / "manifests"
        self.records_dir = self.jobs_dir / "state"
        self.stop_dir = self.jobs_dir / "stop"
        self.logs_dir = self.jobs_dir / "logs"
        self.pause_file = self.jobs_dir / "PAUSED"
        self.events_path = self.jobs_dir / "events.jsonl"
        self.heartbeat_path = self.jobs_dir / "runner-heartbeat.json"
        self._poll = max(0.02, float(poll_interval_s))
        self._gpu_poll = max(0.05, float(gpu_poll_s))
        self._gpu_threshold = int(gpu_threshold_pct)
        # Injectable probes (tests stub the process list / GPU).
        self._process_names_fn = process_names_fn
        self._gpu_fn = gpu_fn
        self._extra_patterns = _blocker_patterns(
            self.cfg.get("job_gpu_blockers") or ())
        self._events_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._kill_current = False
        self._current_proc: subprocess.Popen | None = None
        self._current_record: dict | None = None
        self._paused_known = False

    # -- events ------------------------------------------------------------

    def _event(self, event: str, record: dict | None = None,
               **fields) -> None:
        entry = {"ts": bridge_agent.utc_now_iso(), "event": event,
                 "runner_pid": os.getpid()}
        if record is not None:
            entry["job_id"] = record.get("id")
            entry["job_name"] = record.get("name")
        entry.update(fields)
        try:
            with self._events_lock:
                self.jobs_dir.mkdir(parents=True, exist_ok=True)
                with open(self.events_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry) + "\n")
        except OSError as exc:
            print(f"[job-runner] WARNING: event write failed: {exc}",
                  file=sys.stderr)

    # -- records -------------------------------------------------------------

    def _record_path(self, job_id: str) -> Path:
        return self.records_dir / f"{job_id}.json"

    def _write_record(self, record: dict) -> None:
        record["updated_at"] = time.time()
        _atomic_write_json(self._record_path(str(record["id"])), record)

    def _read_record(self, job_id: str) -> dict | None:
        try:
            obj = json.loads(self._record_path(job_id).read_text(
                encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return obj if isinstance(obj, dict) else None

    def _list_records(self) -> list[dict]:
        try:
            files = sorted(self.records_dir.glob("*.json"))
        except OSError:
            return []
        out = []
        for f in files:
            try:
                obj = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(obj, dict):
                out.append(obj)
        out.sort(key=lambda r: (r.get("queue_mtime_ns") or 0,
                                r.get("submitted_at") or 0,
                                str(r.get("id"))))
        return out

    # -- flags -----------------------------------------------------------------

    def _is_paused(self) -> bool:
        return self.pause_file.exists()

    def _stop_requested(self, job_id: str) -> bool:
        return (self.stop_dir / job_id).exists()

    def _consume_stop_flag(self, job_id: str) -> None:
        try:
            (self.stop_dir / job_id).unlink()
        except OSError:
            pass

    # -- submission ------------------------------------------------------------

    def scan_queue(self) -> None:
        """Claim every manifest waiting in queue/."""
        try:
            files = sorted(
                self.queue_dir.glob("*.json"),
                key=lambda f: (f.stat().st_mtime_ns, f.name))
        except OSError:
            return
        for f in files:
            try:
                self._claim(f)
            except Exception as exc:  # one bad file must not stall the rest
                print(f"[job-runner] claim failed for {f.name}: {exc}",
                      file=sys.stderr)

    def _claim(self, path: Path) -> None:
        try:
            mtime_ns = path.stat().st_mtime_ns
            raw = json.loads(path.read_text(encoding="utf-8"))
            manifest = validate_manifest(raw)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            job_id = uuid.uuid4().hex
            record = self._new_record(job_id, None, 0)
            record.update({
                "state": "failed", "reason": "invalid_manifest",
                "detail": str(exc)[:300], "finished_at": time.time(),
            })
            self._write_record(record)
            self._event("invalid_manifest", record,
                        detail=str(exc)[:300], source_file=path.name)
            self._retire_queue_file(path, ".rejected")
            return
        job_id = manifest["id"] or uuid.uuid4().hex
        if self._read_record(job_id) is not None:
            self._event("invalid_manifest", {"id": job_id,
                                             "name": manifest["name"]},
                        reason="duplicate_id", source_file=path.name)
            self._retire_queue_file(path, ".duplicate")
            return
        record = self._new_record(job_id, manifest, mtime_ns)
        _atomic_write_json(self.manifests_dir / f"{job_id}.json", manifest)
        self._write_record(record)
        self._event("submitted", record)
        self._retire_queue_file(path, None)

    def _retire_queue_file(self, path: Path, suffix: str | None) -> None:
        try:
            if suffix is None:
                _with_sharing_retry(path.unlink)
            else:
                _with_sharing_retry(
                    lambda: os.replace(path, path.with_name(
                        path.name + suffix)))
        except OSError:
            pass

    def _new_record(self, job_id: str, manifest: dict | None,
                    mtime_ns: int) -> dict:
        stages = []
        if manifest is not None:
            stages = [{"index": i, "name": s["name"], "status": "pending",
                       "attempts": 0, "started_at": None,
                       "finished_at": None, "exit_code": None,
                       "pid": None}
                      for i, s in enumerate(manifest["stages"])]
        return {
            "id": job_id,
            "name": manifest["name"] if manifest else None,
            "manifest": manifest,
            "state": "queued",
            "next_stage": 0,
            "stages": stages,
            "submitted_at": time.time(),
            "queue_mtime_ns": mtime_ns,
            "started_at": None,
            "finished_at": None,
            "failed_stage": None,
            "exit_code": None,
            "reason": None,
            "waiting_for_gpu": None,
            "pause_kills": 0,
            "runner_pid": None,
            "updated_at": time.time(),
        }

    # -- recovery ----------------------------------------------------------------

    def recover(self) -> list[str]:
        """Resume scan at worker start. Returns resumed job ids.

        A job left in state `running` was interrupted mid-flight
        (runner crash, agent/PC restart, reboot). Its completed
        stages stay completed; the interrupted stage's process —
        if somehow still alive — is killed (unmonitored output,
        and a duplicate GPU stage is the real hazard), the stage
        returns to pending, and the job goes back to queued.
        `rerun: true` manifests reset to stage 0 instead.
        """
        resumed = []
        for record in self._list_records():
            if record.get("state") != "running":
                continue
            manifest = record.get("manifest") or {}
            if manifest.get("rerun"):
                for stage in record.get("stages") or []:
                    stage.update({"status": "pending", "pid": None,
                                  "exit_code": None, "started_at": None,
                                  "finished_at": None})
                record["next_stage"] = 0
                record["state"] = "queued"
                record["waiting_for_gpu"] = None
                self._write_record(record)
                self._event("resume", record, mode="rerun_all")
                resumed.append(str(record["id"]))
                continue
            idx = int(record.get("next_stage") or 0)
            stages = record.get("stages") or []
            if 0 <= idx < len(stages):
                stage = stages[idx]
                pid = stage.get("pid")
                if stage.get("status") == "running" and pid:
                    if bridge_agent.pid_alive(int(pid)):
                        bridge_agent.kill_pid_tree(int(pid))
                        self._event("orphan_killed", record,
                                    stage=idx, pid=int(pid))
                    stage.update({"status": "pending", "pid": None})
            record["state"] = "queued"
            record["waiting_for_gpu"] = None
            self._write_record(record)
            self._event("resume", record, mode="from_checkpoint",
                        next_stage=idx)
            resumed.append(str(record["id"]))
        return resumed

    # -- main loop -----------------------------------------------------------------

    def request_stop(self, kill_current: bool = True) -> None:
        self._kill_current = kill_current
        self._stop_event.set()

    def run(self) -> None:
        for d in (self.queue_dir, self.manifests_dir, self.records_dir,
                  self.stop_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)
        resumed = self.recover()
        if resumed:
            try:
                boot_beacon.append_event(
                    self.state_dir, "jobs_resumed", resumed=resumed)
            except OSError:
                pass
        self._event("runner_started", None, resumed=resumed)
        self._paused_known = self._is_paused()
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:  # the runner must not die quietly
                print(f"[job-runner] loop error: {exc}", file=sys.stderr)
            self._write_heartbeat()
            self._stop_event.wait(self._poll)
        # Shutdown: leave any current job checkpointed, not failed.
        self._event("runner_stopped", None)
        try:
            _atomic_write_json(self.heartbeat_path, {
                "state": "stopped", "worker_pid": os.getpid(),
                "current_job": None, "updated_at": time.time()})
        except OSError:
            pass

    def _write_heartbeat(self) -> None:
        try:
            _atomic_write_json(self.heartbeat_path, {
                "state": "running",
                "worker_pid": os.getpid(),
                "current_job": (self._current_record or {}).get("id"),
                "paused": self._is_paused(),
                "updated_at": time.time()})
        except OSError:
            pass

    def _tick(self) -> None:
        self.scan_queue()
        paused = self._is_paused()
        if paused != self._paused_known:
            self._paused_known = paused
            self._event("paused" if paused else "unpaused", None,
                        via="PAUSED file")
        # Stop flags land on queued jobs too.
        for record in self._list_records():
            if record.get("state") == "queued" \
                    and self._stop_requested(str(record["id"])):
                self._consume_stop_flag(str(record["id"]))
                record.update({"state": "stopped",
                               "reason": "stop_flag",
                               "finished_at": time.time()})
                self._write_record(record)
                self._event("stopped", record, via="stop flag (queued)")
        if paused or self._stop_event.is_set():
            return
        record = self._next_queued()
        if record is not None:
            self._run_job(record)

    def _next_queued(self) -> dict | None:
        for record in self._list_records():
            if record.get("state") == "queued":
                return record
        return None

    # -- GPU yield -------------------------------------------------------------------

    def _contention(self, record: dict) -> str | None:
        manifest = record.get("manifest") or {}
        patterns = self._extra_patterns + _blocker_patterns(
            manifest.get("gpu_blockers") or ())
        return presence.gpu_contention(
            threshold_pct=self._gpu_threshold,
            process_names_fn=self._process_names_fn,
            gpu_fn=self._gpu_fn,
            extra_game_patterns=patterns)

    def _wait_for_gpu(self, record: dict) -> str:
        """Wait until the GPU is free. Returns "clear", "paused",
        "stopped", or "shutdown"."""
        reason = self._contention(record)
        if reason is None:
            return "clear"
        record["waiting_for_gpu"] = reason
        self._write_record(record)
        self._event("gpu_wait", record, reason=reason)
        while not self._stop_event.is_set():
            if self._is_paused():
                record["waiting_for_gpu"] = None
                self._write_record(record)
                return "paused"
            if self._stop_requested(str(record["id"])):
                record["waiting_for_gpu"] = None
                self._write_record(record)
                return "stopped"
            deadline = time.monotonic() + self._gpu_poll
            while time.monotonic() < deadline \
                    and not self._stop_event.is_set():
                time.sleep(min(0.25, self._gpu_poll))
            reason = self._contention(record)
            if reason is None:
                record["waiting_for_gpu"] = None
                self._write_record(record)
                self._event("gpu_clear", record)
                return "clear"
            if reason != record.get("waiting_for_gpu"):
                record["waiting_for_gpu"] = reason
                self._write_record(record)
        return "shutdown"

    # -- job execution -----------------------------------------------------------------

    def _run_job(self, record: dict) -> None:
        manifest = record.get("manifest") or {}
        record["state"] = "running"
        record["runner_pid"] = os.getpid()
        if record.get("started_at") is None:
            record["started_at"] = time.time()
        self._write_record(record)
        self._current_record = record
        self._event("job_started", record,
                    next_stage=int(record.get("next_stage") or 0))
        pm_engaged = False
        try:
            # Project Mode auto-engage: OFF unless the owner opted
            # in via config `job_project_mode_auto`. Only for
            # gpu:true jobs, and only disengaged afterwards if THIS
            # runner engaged it (an owner/API engagement is left
            # exactly as found).
            if manifest.get("gpu") \
                    and self.cfg.get("job_project_mode_auto"):
                pm_engaged = self._engage_project_mode(record)
            workdir = Path(str(manifest.get("workdir") or ""))
            if not workdir.is_dir():
                self._fail_job(record, None, "workdir_missing", None)
                return
            stages = manifest.get("stages") or []
            while int(record.get("next_stage") or 0) < len(stages):
                idx = int(record["next_stage"])
                if self._stop_requested(str(record["id"])):
                    self._consume_stop_flag(str(record["id"]))
                    record.update({"state": "stopped",
                                   "reason": "stop_flag",
                                   "finished_at": time.time()})
                    self._write_record(record)
                    self._event("stopped", record, via="stop flag")
                    return
                if self._is_paused():
                    record["state"] = "queued"
                    self._write_record(record)
                    self._event("paused", record,
                                via="PAUSED before stage")
                    return
                if manifest.get("gpu"):
                    gate = self._wait_for_gpu(record)
                    if gate == "paused":
                        record["state"] = "queued"
                        self._write_record(record)
                        self._event("paused", record,
                                    via="PAUSED during GPU wait")
                        return
                    if gate == "stopped":
                        self._consume_stop_flag(str(record["id"]))
                        record.update({"state": "stopped",
                                       "reason": "stop_flag",
                                       "finished_at": time.time()})
                        self._write_record(record)
                        self._event("stopped", record,
                                    via="stop flag during GPU wait")
                        return
                    if gate == "shutdown":
                        record["state"] = "queued"
                        self._write_record(record)
                        return
                outcome = self._run_stage(record, idx)
                if outcome in ("paused", "shutdown"):
                    record["state"] = "queued"
                    self._write_record(record)
                    return
                if outcome == "stopped":
                    record.update({"state": "stopped",
                                   "reason": "stop_flag",
                                   "finished_at": time.time()})
                    self._write_record(record)
                    self._event("stopped", record, via="stop flag")
                    return
                if outcome == "failed":
                    return  # _run_stage already recorded the failure
                # outcome == "done": next_stage advanced by _run_stage
            record.update({"state": "done", "finished_at": time.time(),
                           "exit_code": 0, "reason": None})
            self._write_record(record)
            self._event("completed", record)
        finally:
            if pm_engaged:
                self._disengage_project_mode(record)
            self._current_record = None

    def _engage_project_mode(self, record: dict) -> bool:
        try:
            import project_mode
            result = project_mode.engage(
                self.state_dir, source="runner", cfg=self.cfg)
            mine = bool(result.get("engaged")) \
                and not result.get("note")
            if mine:
                record["project_mode"] = "engaged_by_runner"
                self._write_record(record)
                self._event("project_mode_engaged", record)
            return mine
        except Exception as exc:
            print(f"[job-runner] project mode engage failed: {exc}",
                  file=sys.stderr)
            return False

    def _disengage_project_mode(self, record: dict) -> None:
        try:
            import project_mode
            project_mode.disengage(self.state_dir, source="runner")
            record["project_mode"] = "disengaged_by_runner"
            self._write_record(record)
            self._event("project_mode_disengaged", record)
        except Exception as exc:
            print(f"[job-runner] project mode disengage failed: "
                  f"{exc}", file=sys.stderr)

    def _fail_job(self, record: dict, stage_idx: int | None,
                  reason: str, exit_code) -> None:
        record.update({"state": "failed", "reason": reason,
                       "failed_stage": stage_idx,
                       "exit_code": exit_code,
                       "finished_at": time.time()})
        self._write_record(record)
        self._event("failed", record, reason=reason,
                    stage=stage_idx, exit_code=exit_code)

    def _run_stage(self, record: dict, idx: int) -> str:
        """Run one stage (with its retries). Returns "done",
        "failed", "paused", "stopped", or "shutdown". The
        checkpoint is written after every attempt boundary."""
        manifest = record.get("manifest") or {}
        spec = (manifest.get("stages") or [])[idx]
        stage_rec = record["stages"][idx]
        retries = int(spec.get("retries") or 0)
        attempt = 0
        while True:
            attempt += 1
            stage_rec.update({"status": "running",
                              "attempts": int(stage_rec.get("attempts")
                                              or 0) + 1,
                              "started_at": time.time(),
                              "finished_at": None, "exit_code": None,
                              "pid": None})
            self._write_record(record)
            self._event("stage_started", record, stage=idx,
                        attempt=attempt, name=spec.get("name"))
            kind, exit_code = self._spawn_and_wait(record, spec, stage_rec)
            stage_rec["finished_at"] = time.time()
            stage_rec["exit_code"] = exit_code
            stage_rec["pid"] = None
            if kind == "exit" and exit_code == 0:
                stage_rec["status"] = "done"
                record["next_stage"] = idx + 1
                self._write_record(record)
                self._event("stage_finished", record, stage=idx,
                            exit_code=0)
                return "done"
            if kind in ("paused", "stopped", "shutdown"):
                stage_rec["status"] = "pending"
                self._write_record(record)
                return kind
            # "exit" (non-zero), "timeout", or "spawn_failed":
            # a failed attempt.
            stage_rec["status"] = "failed"
            self._write_record(record)
            reason = {"exit": "exit_code", "timeout": "stage_timeout",
                      "spawn_failed": "spawn_failed"}[kind]
            self._event("stage_failed", record, stage=idx,
                        exit_code=exit_code, reason=reason,
                        attempt=attempt)
            if attempt <= retries:
                self._event("stage_retry", record, stage=idx,
                            attempt=attempt + 1)
                continue
            self._fail_job(record, idx, reason, exit_code)
            return "failed"

    def _spawn_and_wait(self, record: dict, spec: dict,
                        stage_rec: dict) -> tuple[str, int | None]:
        """Spawn one stage attempt and watch it. Returns
        (kind, exit_code): kind is "exit", "timeout",
        "spawn_failed", "paused", "stopped", or "shutdown"."""
        manifest = record.get("manifest") or {}
        command = spec["command"]
        if isinstance(command, list):
            target: list | str = list(command)
        else:
            argv = bridge_agent.build_command(spec["shell"], command)
            target = bridge_agent.popen_target(
                spec["shell"], argv, command)
        log_path = self.logs_dir / f"{record['id']}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        header = (f"\n===== stage {stage_rec['index']} "
                  f"{spec.get('name')!r} attempt "
                  f"{stage_rec.get('attempts')} "
                  f"{bridge_agent.utc_now_iso()} =====\n")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(header)
        log_fh = open(log_path, "ab")
        try:
            proc = subprocess.Popen(
                target, cwd=str(manifest.get("workdir")),
                stdout=log_fh, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                **bridge_agent.spawn_kwargs())
        except OSError:
            log_fh.close()
            # _run_stage records the failed attempt (single
            # stage_failed event, reason "spawn_failed").
            return "spawn_failed", None
        log_fh.close()
        self._current_proc = proc
        stage_rec["pid"] = proc.pid
        self._write_record(record)
        timeout = spec.get("timeout_s")
        deadline = None if timeout is None \
            else time.monotonic() + float(timeout)
        try:
            while True:
                code = proc.poll()
                if code is not None:
                    return "exit", code
                if deadline is not None and time.monotonic() >= deadline:
                    bridge_agent.kill_tree(proc)
                    proc.wait(timeout=10)
                    return "timeout", None
                if self._is_paused():
                    bridge_agent.kill_tree(proc)
                    proc.wait(timeout=10)
                    record["pause_kills"] = \
                        int(record.get("pause_kills") or 0) + 1
                    self._event("pause_kill", record,
                                stage=stage_rec["index"], pid=proc.pid)
                    return "paused", None
                if self._stop_requested(str(record["id"])):
                    self._consume_stop_flag(str(record["id"]))
                    bridge_agent.kill_tree(proc)
                    proc.wait(timeout=10)
                    self._event("stop_kill", record,
                                stage=stage_rec["index"], pid=proc.pid)
                    return "stopped", None
                if self._stop_event.is_set():
                    if self._kill_current:
                        bridge_agent.kill_tree(proc)
                        proc.wait(timeout=10)
                    return "shutdown", None
                time.sleep(_POLL_S)
        finally:
            self._current_proc = None


# ---------------------------------------------------------------------------
# Supervisor (mirrors agent/supervisor.py: restart with backoff,
# status JSON; the worker is a child process, never a thread)
# ---------------------------------------------------------------------------

class RunnerSupervisor:
    def __init__(self, jobs_dir: Path, config_path: Path,
                 restart_base_delay: float = 2.0,
                 restart_max_delay: float = 30.0,
                 python_exe: str | None = None):
        self.jobs_dir = Path(jobs_dir)
        self.config_path = Path(config_path)
        self.restart_base_delay = restart_base_delay
        self.restart_max_delay = restart_max_delay
        self.python_exe = python_exe or sys.executable
        self._stop = False
        self._child: subprocess.Popen | None = None
        self.restarts = 0
        self._fast_crashes = 0

    def _write_status(self, state: str, **extra) -> None:
        obj = {"state": state,
               "worker_pid": self._child.pid if self._child else None,
               "restarts": self.restarts,
               "updated_at": time.time()}
        obj.update(extra)
        try:
            bridge_update._write_json(
                self.jobs_dir / "runner-status.json", obj)
        except OSError:
            pass
        print(f"[job-runner-supervisor] {state} "
              + (f"({extra})" if extra else ""), flush=True)

    def _worker_cmd(self) -> list[str]:
        return [self.python_exe, str(Path(__file__).resolve()),
                "--config", str(self.config_path), "--worker"]

    def _start_child(self) -> subprocess.Popen:
        self._child = subprocess.Popen(self._worker_cmd())
        return self._child

    def _stop_child(self, timeout: float = 10.0) -> None:
        child = self._child
        if child is None or child.poll() is not None:
            return
        try:
            child.terminate()
            child.wait(timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            try:
                child.kill()
            except OSError:
                pass

    def stop(self) -> None:
        self._stop = True
        self._stop_child()

    def run(self) -> int:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._write_status("starting")
        while not self._stop:
            child = self._start_child()
            self._write_status("running", worker_pid=child.pid)
            started = time.monotonic()
            exit_code = self._wait_child(child)
            if self._stop:
                break
            ran_for = time.monotonic() - started
            self.restarts += 1
            if ran_for < 10:
                self._fast_crashes += 1
            else:
                self._fast_crashes = 0
            delay = min(self.restart_max_delay,
                        self.restart_base_delay
                        * (2 ** self._fast_crashes))
            self._write_status("restarting", exit_code=exit_code,
                               delay_s=delay)
            self._sleep(delay)
        self._stop_child()
        self._write_status("stopped")
        return 0

    def _wait_child(self, child: subprocess.Popen) -> int | None:
        while not self._stop:
            code = child.poll()
            if code is not None:
                return code
            time.sleep(0.1)
        return child.poll()

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stop and time.monotonic() < deadline:
            time.sleep(0.1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _agent_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_cfg(config_path: Path) -> tuple[dict, Path, Path]:
    cfg = bridge_agent.load_config(config_path)
    state_dir = Path(cfg["state_dir"])
    return cfg, state_dir, state_dir / "jobs"


def _make_runner(cfg: dict, state_dir: Path, jobs_dir: Path) -> JobRunner:
    def _float(key, default):
        try:
            return float(cfg.get(key) or default)
        except (TypeError, ValueError):
            return default

    def _int(key, default):
        try:
            return int(cfg.get(key) or default)
        except (TypeError, ValueError):
            return default

    return JobRunner(
        jobs_dir, state_dir, cfg,
        poll_interval_s=_float("job_runner_poll_s", 0.25),
        gpu_poll_s=_float("job_gpu_poll_s", 30.0),
        gpu_threshold_pct=_int("job_gpu_util_threshold", 90))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="muse-pc-bridge durable job runner")
    parser.add_argument("--config", type=Path,
                        default=_agent_dir() / "config.json",
                        help="agent config.json (default: beside "
                             "bridge_agent.py)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--worker", action="store_true",
                      help="run the engine in this process")
    mode.add_argument("--supervise", action="store_true",
                      help="supervise a worker child (default)")
    mode.add_argument("--status", action="store_true",
                      help="print the jobs status JSON and exit")
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"[job-runner] No agent config at {args.config}. "
              f"Run bridge_agent.py --init first.", file=sys.stderr)
        return 1
    try:
        cfg, state_dir, jobs_dir = _load_cfg(args.config)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[job-runner] Could not read agent config: {exc}",
              file=sys.stderr)
        return 1

    if args.status:
        print(json.dumps(jobs_status(jobs_dir), indent=2))
        return 0

    if args.worker:
        runner = _make_runner(cfg, state_dir, jobs_dir)

        def _handle_signal(_signum, _frame):
            runner.request_stop(kill_current=True)

        signal.signal(signal.SIGINT, _handle_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_signal)
        print("[job-runner] worker running. Jobs directory: "
              f"{jobs_dir}", flush=True)
        runner.run()
        return 0

    supervisor = RunnerSupervisor(jobs_dir, args.config)

    def _handle_signal(_signum, _frame):
        supervisor.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)
    print("[job-runner] supervisor running. Stopping this process "
          "stops the worker; jobs resume from their checkpoints "
          "on the next start.")
    try:
        return supervisor.run()
    except KeyboardInterrupt:
        supervisor.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
