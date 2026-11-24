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

Completion notification (v1.4.0): when a job reaches a terminal
state (`done` / `failed`) and notification is configured, the
runner emails the owner-side inbox (default
nyx-adam@muse.ai) exactly once — event-driven, so completion
is learned without polling. Best-effort by design: a send
failure is recorded (events `notify_failed` / `notify_sent` /
`notify_gave_up`), never fails the job, and a failed send is
retried at most once on the next runner start. The SMTP app
password is read ONLY from the environment variable
BRIDGE_NOTIFY_APP_PASSWORD — never from the config file, never
written to any record, event, or log. Unconfigured (the
default) the runner behaves exactly as before. See
docs/JOB_RUNNER.md, "Completion notification".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import smtplib
import ssl
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import boot_beacon  # noqa: E402
import bridge_agent  # noqa: E402
import bridge_update  # noqa: E402
import presence  # noqa: E402

#: Environment variable holding the SMTP app password. The one
#: and only place the secret is read from.
NOTIFY_PASSWORD_ENV = "BRIDGE_NOTIFY_APP_PASSWORD"
NOTIFY_DEFAULT_RECIPIENT = "nyx-adam@muse.ai"
_TERMINAL_STATES = ("done", "failed")

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
            "notified": record.get("notified"),
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
                 process_names_fn=None, gpu_fn=None,
                 shutdown_grace_s: float = 10.0,
                 shutdown_fn=None,
                 notify_fn=None, smtp_factory=None):
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
        self._shutdown_grace_s = max(0.0, float(shutdown_grace_s))
        # Injectable probe (tests stub the shutdown state).
        self._shutdown_fn = shutdown_fn \
            if shutdown_fn is not None \
            else bridge_agent.system_shutting_down
        # Completion notification seams (tests inject a fake
        # sender / SMTP factory; production uses SMTP below).
        self._notify_fn = notify_fn
        self._smtp_factory = smtp_factory
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

    # -- completion notification (v1.4.0) -----------------------------------

    def _notify_enabled(self) -> bool:
        return bool(self.cfg.get("notify_email_enabled"))

    def _notify_terminal(self, record: dict) -> None:
        """Mark a terminal job as owing a notification and try
        to send it now. No-op when the feature is unconfigured.
        Never raises: notification is best-effort and must not
        disturb the job's recorded outcome."""
        if record.get("state") not in _TERMINAL_STATES:
            return
        if not self._notify_enabled():
            return
        if record.get("notified") or record.get("notify_given_up"):
            return
        if not record.get("notify_pending"):
            record["notify_pending"] = True
            try:
                self._write_record(record)
            except OSError:
                pass
        self._attempt_notify(record)

    def _attempt_notify(self, record: dict) -> None:
        """One send attempt. Exactly-once is anchored on the
        record: `notified` is written after a successful send,
        and attempts are capped at 2 (the initial send plus one
        retry on a later runner start), after which the runner
        gives up and logs it."""
        if record.get("notified") or record.get("notify_given_up"):
            return
        record["notify_attempts"] = \
            int(record.get("notify_attempts") or 0) + 1
        attempt = int(record["notify_attempts"])
        try:
            self._write_record(record)
        except OSError:
            pass
        try:
            self._send_notification(record)
        except Exception as exc:  # best-effort: never propagate
            summary = self._scrub_secret(
                f"{type(exc).__name__}: {exc}")[:200]
            if attempt >= 2:
                record["notify_given_up"] = True
                record["notify_pending"] = False
            try:
                self._write_record(record)
            except OSError:
                pass
            self._event("notify_failed", record, attempt=attempt,
                        error=summary)
            if record.get("notify_given_up"):
                self._event("notify_gave_up", record,
                            attempts=attempt)
            print(f"[job-runner] notification failed for job "
                  f"{record.get('id')}: {summary}", file=sys.stderr)
            return
        record["notified"] = True
        record["notify_pending"] = False
        try:
            self._write_record(record)
        except OSError:
            pass
        self._event("notify_sent", record, attempt=attempt,
                    recipient=self._notify_recipient())

    def _retry_pending_notifications(self) -> None:
        """At runner start: jobs that reached a terminal state
        but whose notification never landed (send failed, or the
        runner died between recording the outcome and sending)
        get their one retry here. Records already notified or
        given up are never touched again."""
        if not self._notify_enabled():
            return
        for record in self._list_records():
            if record.get("state") not in _TERMINAL_STATES:
                continue
            if not record.get("notify_pending"):
                continue
            if record.get("notified") \
                    or record.get("notify_given_up"):
                continue
            if int(record.get("notify_attempts") or 0) >= 2:
                continue
            self._attempt_notify(record)

    def _notify_recipient(self) -> str:
        return str(self.cfg.get("notify_recipient")
                   or NOTIFY_DEFAULT_RECIPIENT)

    def _scrub_secret(self, text: str) -> str:
        """Defence in depth: the SMTP password must never land
        in an event, record, or log — strip it if an exception
        message somehow contains it."""
        password = os.environ.get(NOTIFY_PASSWORD_ENV) or ""
        if password:
            text = text.replace(password, "***")
        return text

    def _send_notification(self, record: dict) -> None:
        """Deliver one notification. Raises on any failure; the
        caller (_attempt_notify) owns the bookkeeping."""
        if self._notify_fn is not None:
            self._notify_fn(record)
            return
        subject, body = self.build_notification(record)
        user = str(self.cfg.get("notify_smtp_user") or "")
        password = os.environ.get(NOTIFY_PASSWORD_ENV) or ""
        if not user or not password:
            raise RuntimeError(
                "notification SMTP not configured: "
                "notify_smtp_user and the "
                f"{NOTIFY_PASSWORD_ENV} environment variable "
                "are both required")
        host = str(self.cfg.get("notify_smtp_host")
                   or "smtp.gmail.com")
        try:
            port = int(self.cfg.get("notify_smtp_port") or 587)
        except (TypeError, ValueError):
            port = 587
        try:
            timeout = float(self.cfg.get("notify_smtp_timeout_s")
                            or 15.0)
        except (TypeError, ValueError):
            timeout = 15.0
        msg = EmailMessage()
        msg["From"] = user
        msg["To"] = self._notify_recipient()
        msg["Subject"] = subject
        msg.set_content(body)
        factory = self._smtp_factory or smtplib.SMTP
        with factory(host, port, timeout=timeout) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(user, password)
            server.send_message(msg)

    @staticmethod
    def _fmt_ts(value) -> str:
        try:
            ts = float(value)
        except (TypeError, ValueError):
            return "unknown"
        return datetime.fromtimestamp(ts, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC")

    def _last_log_line(self, record: dict) -> str | None:
        """Last non-empty line of the job's stage log (bounded
        tail read), for failure emails. None when unavailable."""
        try:
            path = self.logs_dir / f"{record['id']}.log"
            with open(path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 65536))
                tail = fh.read().decode("utf-8", "replace")
        except OSError:
            return None
        for line in reversed(tail.splitlines()):
            if line.strip():
                return line.strip()[:300]
        return None

    def build_notification(self, record: dict) -> tuple[str, str]:
        """(subject, plain-text body) for a terminal record.
        Pure apart from the bounded log-tail read on failures."""
        outcome = "completed" if record.get("state") == "done" \
            else "failed"
        subject = (f"[pc-bridge] job {record.get('id')} {outcome}")
        lines = [
            f"Job: {record.get('id')}",
            f"Name: {record.get('name') or '(unnamed)'}",
            f"Outcome: {outcome}",
            f"Submitted: {self._fmt_ts(record.get('submitted_at'))}",
            f"Started: {self._fmt_ts(record.get('started_at'))}",
            f"Finished: {self._fmt_ts(record.get('finished_at'))}",
        ]
        started, finished = record.get("started_at"), \
            record.get("finished_at")
        if isinstance(started, (int, float)) \
                and isinstance(finished, (int, float)) \
                and finished >= started:
            lines.append(f"Duration: {finished - started:.1f} s")
        if record.get("reason"):
            lines.append(f"Reason: {record.get('reason')}")
        if record.get("failed_stage") is not None:
            lines.append(
                f"Failed stage: {record.get('failed_stage')}")
        if record.get("exit_code") is not None:
            lines.append(f"Exit code: {record.get('exit_code')}")
        lines.append("")
        lines.append("Stages:")
        stages = record.get("stages") or []
        if stages:
            for stage in stages:
                lines.append(
                    f"  {stage.get('index')}. "
                    f"{stage.get('name')}: "
                    f"{stage.get('status')} "
                    f"(attempts: {stage.get('attempts')}, "
                    f"exit code: {stage.get('exit_code')})")
        else:
            lines.append("  (none recorded)")
        if outcome == "failed":
            last = self._last_log_line(record)
            if last:
                lines.append("")
                lines.append(f"Last log line: {last}")
        return subject, "\n".join(lines) + "\n"

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
            self._notify_terminal(record)
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
            "notified": False,
            "notify_pending": False,
            "notify_attempts": 0,
            "notify_given_up": False,
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
        self._retry_pending_notifications()
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
            self._notify_terminal(record)
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
        self._notify_terminal(record)

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

    def _shutdown_interruption(self, record: dict, stage_rec: dict,
                               exit_code: int) -> bool:
        """Decide whether a stage's non-zero exit is really the
        machine shutting down underneath it.

        On a graceful Windows shutdown the OS terminates stage
        processes (console children) seconds before the runner
        worker (a console-less pythonw), so the worker's first
        sight of a shutdown is its stage dying with a generic
        exit code — indistinguishable from a real failure unless
        the shutdown itself is probed. Deploy smoke, 2026-11-24:
        a demo job's sleep stage exited 1 as the PC rebooted and
        the job was marked failed, leaving nothing to resume.
        So: probe immediately, then keep probing for the grace
        window (the flag can lag the kills). A shutdown found at
        any point converts the exit into an interruption — the
        stage returns to pending and the job resumes on the next
        worker start. A worker stop during the window converts
        too (the job is being left, not failed). Only a full
        quiet window lets the failure verdict through, delayed
        by at most the grace.
        """
        if self._shutdown_fn():
            self._event("shutdown_interrupted", record,
                        stage=stage_rec["index"], exit_code=exit_code)
            return True
        deadline = time.monotonic() + self._shutdown_grace_s
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return True
            if self._shutdown_fn():
                self._event("shutdown_interrupted", record,
                            stage=stage_rec["index"],
                            exit_code=exit_code)
                return True
            time.sleep(0.1)
        return False

    def _spawn_and_wait(self, record: dict, spec: dict,
                        stage_rec: dict) -> tuple[str, int | None]:
        """Spawn one stage attempt and watch it. Returns
        (kind, exit_code): kind is "exit", "timeout",
        "spawn_failed", "paused", "stopped", or "shutdown".
        A non-zero exit is arbitrated by _shutdown_interruption
        before it may be reported as a failure, and a shutdown
        that begins while the stage still runs is reported as
        "shutdown" without killing the stage tree (the OS reaps
        it; recover() orphan-kills it on the next start if it
        somehow survives)."""
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
                    if code != 0 and self._shutdown_interruption(
                            record, stage_rec, code):
                        return "shutdown", None
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
                if self._shutdown_fn():
                    # The machine is going down while the stage
                    # still runs: checkpoint now (the stage goes
                    # back to pending) instead of waiting to be
                    # killed mid-write.
                    self._event("shutdown_interrupted", record,
                                stage=stage_rec["index"], pid=proc.pid)
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
        gpu_threshold_pct=_int("job_gpu_util_threshold", 90),
        shutdown_grace_s=_float("job_shutdown_grace_s", 10.0))


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
