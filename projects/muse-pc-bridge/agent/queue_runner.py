#!/usr/bin/env python3
"""Resident queue runner — muse-pc-bridge v1.2 §3.

A thread inside the existing agent process that drains a file-backed
queue of pre-approved jobs while Muse is not connected. It inherits
the v1.1 boot topology (SYSTEM core + supervisor): no new service,
scheduled task, or autostart entry is created.

Store, under the agent's configured state directory:

    <state_dir>/queue/
      pending/    one JSON file per queued job
      running/    the job currently executing (at most one)
      done/       completed jobs, with result summary
      failed/     failed / skipped / cancelled jobs, with reason
      PAUSED      presence of this file pauses the runner

The state directory IS the agent's state root (config "state_dir",
resolved by load_config) — the queue lives at <state_dir>/queue,
never <state_dir>/state/queue.

Job file schema (spec §3): id, submitted_at, kind ("exec"|"script"),
command (kind=exec), script + script_sha256 (kind=script,
sandbox-relative, hash-pinned), shell, timeout_s, uac_policy
("skip-if-likely"|"run-anyway"), on_failure ("stop"|"continue"),
note. The runner adds state/started_at/finished_at/exit_code/
reason/exec_job_id/waiting_uac as the job moves.

Execution reuses the agent's own job executor (bridge_agent.
submit_job), so output capture, timeouts with process-tree kill,
and the job_finish audit entries are identical to /v1/exec.
Scripts are re-hashed immediately before execution: a mismatch
fails with script_hash_mismatch and NEVER executes — what was
approved is what runs. The runner never clicks UAC consent; a
prompt appearing mid-run marks the job waiting_uac and, after the
configured grace (queue_uac_grace_s, default 120 s), fails it with
uac_timeout. On start, a job found in running/ is moved to failed/
with reason core_restarted — interrupted jobs are never silently
re-run.

Every transition is an audit entry carrying the queue job id:
queue_submitted, queue_started, queue_finished (with exit code),
queue_failed (with reason), queue_waiting_uac, queue_paused,
queue_resumed, queue_cancelled.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_agent  # noqa: E402

QUEUE_STATES = ("pending", "running", "done", "failed")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def validate_queue_payload(core, payload: dict) -> dict:
    """Validate a POST /v1/queue body and build the stored record.

    Raises ValueError (-> HTTP 400) on any schema problem. The §1
    pre-flight assessment is computed here, at submission, and
    stored in the record ("uac") — the runner's skip policy reads
    the stored assessment, exactly as spec §3 requires.
    """
    if not isinstance(payload, dict):
        raise ValueError("JSON object body is required")
    kind = payload.get("kind") or "exec"
    if kind not in ("exec", "script"):
        raise ValueError(f"unknown queue job kind: {kind!r}")
    shell = payload.get("shell") or bridge_agent.default_shell()
    if shell not in ("powershell", "cmd", "posix"):
        raise ValueError(f"unknown shell: {shell!r}")
    timeout_raw = payload.get("timeout_s")
    if timeout_raw is None:
        timeout = 900.0
    else:
        try:
            timeout = float(timeout_raw)
        except (TypeError, ValueError):
            raise ValueError("timeout_s must be a number")
        if timeout <= 0:
            raise ValueError("timeout_s must be positive")
        timeout = min(timeout,
                      float(core.cfg.get("max_timeout_s") or timeout))
    uac_policy = payload.get("uac_policy") or "skip-if-likely"
    if uac_policy not in ("skip-if-likely", "run-anyway"):
        raise ValueError(f"unknown uac_policy: {uac_policy!r}")
    on_failure = payload.get("on_failure") or "stop"
    if on_failure not in ("stop", "continue"):
        raise ValueError(f"unknown on_failure: {on_failure!r}")
    note = payload.get("note") or ""
    if not isinstance(note, str):
        raise ValueError("note must be a string")
    record = {
        "id": uuid.uuid4().hex,
        "submitted_at": int(time.time()),
        "kind": kind,
        "shell": shell,
        "timeout_s": timeout,
        "uac_policy": uac_policy,
        "on_failure": on_failure,
        "note": note,
        "state": "pending",
    }
    if kind == "exec":
        command = payload.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError(
                "field 'command' (non-empty string) is required "
                "for kind=exec")
        record["command"] = command
        assess_text = command
    else:
        script = payload.get("script")
        if not isinstance(script, str) or not script.strip():
            raise ValueError(
                "field 'script' (sandbox-relative path) is required "
                "for kind=script")
        sha = payload.get("script_sha256")
        if not isinstance(sha, str) or not _SHA256_RE.match(sha):
            raise ValueError(
                "field 'script_sha256' (64 hex chars) is required "
                "for kind=script")
        record["script"] = script
        record["script_sha256"] = sha.lower()
        # Resolve at submit time: a path escaping the file sandbox
        # is a 400 now, not a surprise at run time. The file itself
        # need not exist yet (the queue is a buffer), but when it
        # does, its text feeds the pre-flight assessment.
        target = core.resolve_in_root(None, script)
        assess_text = ""
        try:
            assess_text = target.read_text(encoding="utf-8",
                                           errors="replace")
        except OSError:
            pass
    record["uac"] = bridge_agent.assess_uac(core, assess_text)
    return record


class QueueRunner:
    """Sequential, file-backed queue drainer. One job at a time."""

    def __init__(self, core, *, poll_interval_s: float = 0.25):
        self.core = core
        self.queue_dir = Path(core.state_dir) / "queue"
        self.dirs = {state: self.queue_dir / state
                     for state in QUEUE_STATES}
        self.pause_file = self.queue_dir / "PAUSED"
        self._poll = max(0.02, float(poll_interval_s))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._paused_known = False
        self._halted = False          # set by on_failure == "stop"
        self.current_id: str | None = None

    # -- paths / records ---------------------------------------------------

    def _record_path(self, state: str, qid: str) -> Path:
        return self.dirs[state] / f"{qid}.json"

    def _write_record(self, state: str, record: dict) -> None:
        d = self.dirs[state]
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / (record["id"] + ".json.tmp")
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(tmp, self._record_path(state, record["id"]))

    def _read_record(self, state: str, qid: str) -> dict | None:
        try:
            obj = json.loads(self._record_path(state, qid).read_text(
                encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return obj if isinstance(obj, dict) else None

    def _list_records(self, state: str) -> list[dict]:
        d = self.dirs[state]
        try:
            files = sorted(d.glob("*.json"))
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
        out.sort(key=lambda r: (r.get("submitted_at") or 0,
                                str(r.get("id"))))
        return out

    def _move(self, record: dict, src: str, dst: str, **updates) -> dict:
        record = dict(record)
        record.update(updates)
        record["state"] = dst
        self._write_record(dst, record)
        try:
            self._record_path(src, record["id"]).unlink()
        except OSError:
            pass
        return record

    # -- audit ----------------------------------------------------------------

    def _audit(self, event: str, summary: str,
               record: dict | None = None, **extra) -> None:
        entry = {"event": event, "ip": None, "method": None,
                 "path": None, "summary": summary, "status": None,
                 "duration_ms": None}
        if record is not None:
            entry["queue_job_id"] = record.get("id")
        entry.update(extra)
        self.core.audit(entry)

    # -- public API (used by the HTTP handlers) --------------------------------

    def submit(self, record: dict) -> dict:
        with self._lock:
            self._write_record("pending", record)
        self._audit("queue_submitted",
                    f"queue job {record['id']} submitted "
                    f"({record['kind']}, shell {record['shell']})",
                    record)
        return record

    def is_paused(self) -> bool:
        return self.pause_file.exists()

    @property
    def halted(self) -> bool:
        return self._halted

    def set_paused(self, paused: bool) -> None:
        """Toggle the PAUSED file (the API path; the owner dropping
        the file directly is observed by the run loop instead)."""
        if paused:
            self.queue_dir.mkdir(parents=True, exist_ok=True)
            if not self.pause_file.exists():
                self.pause_file.write_text(
                    bridge_agent.utc_now_iso() + "\n", encoding="utf-8")
                self._paused_known = True
                self._audit("queue_paused", "queue paused (PAUSED set)")
        else:
            self.resume()

    def resume(self) -> None:
        """Clear PAUSED and any on_failure halt."""
        self._halted = False
        if self.pause_file.exists():
            try:
                self.pause_file.unlink()
            except OSError:
                pass
            self._paused_known = False
            self._audit("queue_resumed", "queue resumed (PAUSED cleared)")

    def cancel(self, qid: str) -> tuple[str, dict | None]:
        """Cancel a PENDING job. Returns (outcome, record): outcome
        is "cancelled", the job's current state when it exists but
        is not pending, or "missing"."""
        with self._lock:
            record = self._read_record("pending", qid)
            if record is not None:
                record = self._move(record, "pending", "failed",
                                    reason="cancelled",
                                    finished_at=time.time())
                self._audit("queue_cancelled",
                            f"queue job {qid} cancelled while pending",
                            record, reason="cancelled")
                return "cancelled", record
            for state in ("running", "done", "failed"):
                record = self._read_record(state, qid)
                if record is not None:
                    return state, record
        return "missing", None

    def status(self) -> dict:
        jobs: dict[str, list[dict]] = {}
        counts: dict[str, int] = {}
        for state in QUEUE_STATES:
            records = self._list_records(state)
            counts[state] = len(records)
            jobs[state] = [self._summarize(r, state) for r in records]
        return {"paused": self.is_paused(), "halted": self._halted,
                "counts": counts, "jobs": jobs}

    @staticmethod
    def _summarize(record: dict, state: str) -> dict:
        out = {"id": record.get("id"), "kind": record.get("kind"),
               "state": state,
               "submitted_at": record.get("submitted_at"),
               "shell": record.get("shell"),
               "note": record.get("note", "")}
        for key in ("command", "script", "started_at", "finished_at",
                    "exit_code", "reason", "exec_job_id", "waiting_uac",
                    "on_failure", "uac_policy"):
            if record.get(key) is not None:
                out[key] = record[key]
        return out

    # -- lifecycle ---------------------------------------------------------------

    def start(self) -> None:
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        self._recover_interrupted()
        self._paused_known = self.is_paused()
        self._thread = threading.Thread(target=self._run_loop,
                                        daemon=True, name="queue-runner")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _recover_interrupted(self) -> None:
        """A job left in running/ by a previous core process was
        interrupted mid-flight: fail it (core_restarted), never
        silently re-run it."""
        try:
            files = sorted(self.dirs["running"].glob("*.json"))
        except OSError:
            return
        for f in files:
            try:
                record = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(record, dict):
                    raise ValueError("not an object")
            except (OSError, json.JSONDecodeError, ValueError):
                record = {"id": f.stem, "kind": "unknown",
                          "submitted_at": None}
            record.setdefault("id", f.stem)
            with self._lock:
                record = self._move(record, "running", "failed",
                                    reason="core_restarted",
                                    finished_at=time.time())
            self._audit("queue_failed",
                        f"queue job {record['id']} interrupted by a "
                        f"core restart; failed, not re-run",
                        record, reason="core_restarted")

    # -- run loop ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:  # the runner must not die quietly
                print(f"[bridge] queue runner error: {exc}",
                      file=sys.stderr)
            self._stop.wait(self._poll)

    def _tick(self) -> None:
        paused = self.is_paused()
        if paused != self._paused_known:
            # The owner dropped/removed the PAUSED file directly —
            # a local kill switch that needs no network or token.
            self._paused_known = paused
            self._audit("queue_paused" if paused else "queue_resumed",
                        "queue paused (PAUSED file appeared)" if paused
                        else "queue resumed (PAUSED file removed)")
        if paused or self._halted:
            return
        record = self._next_pending()
        if record is None:
            return
        self._run_one(record)

    def _next_pending(self) -> dict | None:
        try:
            files = sorted(self.dirs["pending"].glob("*.json"))
        except OSError:
            return None
        candidates = []
        for f in files:
            try:
                obj = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(obj, dict) or not obj.get("id"):
                    raise ValueError("not a job record")
                mtime_ns = f.stat().st_mtime_ns
            except (OSError, json.JSONDecodeError, ValueError):
                self._fail_orphan(f)
                continue
            candidates.append((obj.get("submitted_at") or 0, mtime_ns,
                               str(obj.get("id")), obj))
        if not candidates:
            return None
        # FIFO: submitted_at is whole seconds (spec schema), so jobs
        # submitted within one second tie — the job files' write
        # order (mtime) is the tiebreak, never the random job id.
        candidates.sort(key=lambda c: (c[0], c[1], c[2]))
        return candidates[0][3]

    def _fail_orphan(self, path: Path) -> None:
        record = {"id": path.stem, "kind": "unknown", "state": "failed",
                  "reason": "invalid_job_file",
                  "submitted_at": None, "finished_at": time.time()}
        with self._lock:
            self._write_record("failed", record)
            try:
                path.unlink()
            except OSError:
                pass
        self._audit("queue_failed",
                    f"queue job {path.stem} had an unreadable job "
                    f"file; failed without executing",
                    record, reason="invalid_job_file")

    def _run_one(self, record: dict) -> None:
        qid = record["id"]
        with self._lock:
            record = self._move(record, "pending", "running",
                                started_at=time.time())
        self.current_id = qid
        self._audit("queue_started", f"queue job {qid} started", record)
        try:
            ok, updates = self._execute(record)
        except Exception as exc:  # never strand a record in running/
            ok, updates = False, {"reason": "runner_error",
                                  "detail": str(exc)[:200]}
        finally:
            self.current_id = None
        updates["finished_at"] = time.time()
        with self._lock:
            record = self._move(record, "running",
                                "done" if ok else "failed", **updates)
        if ok:
            self._audit("queue_finished",
                        f"queue job {qid} finished "
                        f"(exit {updates.get('exit_code')})",
                        record, exit_code=updates.get("exit_code"))
        else:
            self._audit("queue_failed",
                        f"queue job {qid} failed "
                        f"({updates.get('reason')})",
                        record, reason=updates.get("reason"),
                        exit_code=updates.get("exit_code"))
            if record.get("on_failure") == "stop":
                # The runner takes no new work until resumed.
                self._halted = True

    # -- execution -------------------------------------------------------------------

    def _uac_grace_s(self) -> float:
        try:
            return max(0.0, float(
                self.core.cfg.get("queue_uac_grace_s") or 120))
        except (TypeError, ValueError):
            return 120.0

    def _update_running(self, record: dict, **fields) -> None:
        record.update(fields)
        with self._lock:
            self._write_record("running", record)

    def _execute(self, record: dict) -> tuple[bool, dict]:
        """Run one claimed job through the bridge's job executor.
        Returns (ok, record updates). Never raises for job-level
        problems — they become failure reasons."""
        qid = record["id"]
        if record["kind"] == "script":
            problem = self._script_problem(record)
            if problem is not None:
                return False, {"reason": problem}
            target = self.core.resolve_in_root(None, record["script"])
            try:
                command = target.read_text(encoding="utf-8",
                                           errors="replace")
            except OSError:
                return False, {"reason": "script_missing"}
        else:
            command = record["command"]
        # The stored pre-flight assessment drives the skip policy.
        assessment = record.get("uac") or {}
        if (record.get("uac_policy") == "skip-if-likely"
                and assessment.get("likely")):
            return False, {"reason": "uac_likely"}
        payload = {"command": command, "shell": record["shell"],
                   "timeout_s": record["timeout_s"]}
        try:
            job = bridge_agent.submit_job(self.core, payload)
        except ValueError as exc:
            return False, {"reason": "invalid_job",
                           "detail": str(exc)[:200]}
        self._update_running(record, exec_job_id=job.id)
        return self._await_job(record, job)

    def _script_problem(self, record: dict) -> str | None:
        """Hash-pin verification, immediately before execution:
        None when the script is exactly what was approved."""
        try:
            target = self.core.resolve_in_root(None, record["script"])
        except ValueError:
            return "script_path_invalid"
        if not target.is_file():
            return "script_missing"
        try:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError:
            return "script_missing"
        if digest != str(record.get("script_sha256") or "").lower():
            return "script_hash_mismatch"
        return None

    def _await_job(self, record: dict, job) -> tuple[bool, dict]:
        """Wait for the executor job, watching for a UAC prompt
        appearing mid-run. The runner never clicks consent: after
        the configured grace the job is failed (uac_timeout) via
        the existing job-cancel path and the queue moves on."""
        grace = self._uac_grace_s()
        waiting_since: float | None = None
        while not job.wait(0.2):
            if self._stop.is_set():
                # Core is shutting down; the record stays in
                # running/ and restart recovery will fail it.
                job.cancel()
                return False, {"reason": "core_stopped",
                               "exec_job_id": job.id}
            active = bool(self.core.uac.snapshot().get("active"))
            now = time.monotonic()
            if active:
                if waiting_since is None:
                    waiting_since = now
                    self._update_running(record, waiting_uac=True)
                    self._audit(
                        "queue_waiting_uac",
                        f"queue job {record['id']} is waiting on a "
                        f"UAC consent prompt (grace {grace:.0f}s)",
                        record)
                elif now - waiting_since >= grace:
                    job.cancel()
                    job.wait(10)
                    return False, {"reason": "uac_timeout",
                                   "exec_job_id": job.id}
            elif waiting_since is not None:
                waiting_since = None
                self._update_running(record, waiting_uac=False)
        if job.state == "done" and job.exit_code == 0:
            return True, {"exit_code": 0, "exec_job_id": job.id}
        if job.timed_out:
            return False, {"reason": "timeout",
                           "exit_code": job.exit_code,
                           "exec_job_id": job.id}
        if job.state == "killed":
            return False, {"reason": "killed",
                           "exit_code": job.exit_code,
                           "exec_job_id": job.id}
        if job.state == "failed":
            return False, {"reason": "executor_failed",
                           "exit_code": job.exit_code,
                           "exec_job_id": job.id}
        # state "done" with a nonzero exit code.
        return False, {"reason": "exit_code",
                       "exit_code": job.exit_code,
                       "exec_job_id": job.id}
