"""Operational autonomous runtime for Underreach Alpha 0.1.

Canonical simulation and its SQLite Ledger live in this process.  HTTP and
Unreal are supervised, restartable projections; their health and controls can
never feed back into authoritative state.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from typing import Any

from fastapi.responses import PlainTextResponse

from .crawl_domain import Crawl, CrawlStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .feed_api import create_feed_app
from .feed_channel_registry import FeedChannelRegistry
from .headless_mvp_simulation import HeadlessCrawlMVP
from .live_camera_director import LiveCameraConfig
from .live_presentation_bridge import (
    LiveLedgerBuffer,
    LivePresentationScheduler,
    canonical_json,
    payload_digest,
)
from .runtime_checkpoint import AlphaCheckpointStore, CheckpointError, ledger_digest
from .spectator_api import SpectatorRepository


RUNTIME_PROTOCOL = "underreach.alpha-runtime.v1"
RUNTIME_VERSION = "28c2.1"
DEFAULT_SEED = "underreach-alpha-0.1-autonomous"
DEFAULT_DESCENDERS = tuple(f"live_descender_{index:03d}" for index in range(12))
PRESENTED_DESCENDERS = ("live_descender_004", "live_descender_005")


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    tick_interval_seconds: float
    checkpoint_interval_seconds: float
    health_interval_seconds: float
    metrics_interval_seconds: float
    floor_count: int
    checkpoint_retention: int
    delivery_retention: int
    viewer: bool
    unreal: bool
    dense_diagnostics: bool


PROFILES = {
    "qa": RuntimeProfile("qa", 1.5, 3.0, 0.5, 0.5, 8, 10, 256, True, True, True),
    # Alpha deliberately advances canonical time on a human-readable cadence.
    # Twelve deterministic Strata provide more than the 120 steps in a two-hour
    # acceptance soak without inflating every state validation with hundreds of
    # eagerly generated future floors.
    "alpha": RuntimeProfile("alpha", 60.0, 60.0, 2.0, 10.0, 12, 12, 256, True, True, False),
    "headless": RuntimeProfile("headless", 1.0, 30.0, 2.0, 5.0, 8, 12, 64, False, False, False),
}


@dataclass
class ComponentHealth:
    name: str
    status: str = "starting"
    pid: int | None = None
    last_heartbeat_unix_ms: int | None = None
    restart_count: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None
    last_healthy_tick: int = 0
    memory_bytes: int | None = None

    def healthy(self, tick: int, *, pid: int | None = None) -> None:
        self.status = "healthy"
        self.pid = pid if pid is not None else self.pid
        self.last_heartbeat_unix_ms = int(time.time() * 1000)
        self.consecutive_failures = 0
        self.last_error = None
        self.last_healthy_tick = int(tick)

    def fail(self, error: str, *, recovering: bool = False) -> None:
        self.status = "recovering" if recovering else "degraded"
        self.consecutive_failures += 1
        self.last_error = str(error)


def _atomic_json(path: Path, value: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return len(encoded)


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def _rss_bytes(pid: int) -> int | None:
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            handle = ctypes.windll.kernel32.OpenProcess(0x1000 | 0x0010, False, int(pid))
            if not handle:
                return None
            try:
                counters = Counters()
                counters.cb = ctypes.sizeof(counters)
                if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    return int(counters.WorkingSetSize)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        else:
            return int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError):
        return None
    return None


class RuntimeLock:
    def __init__(self, path: Path, runtime_id: str) -> None:
        self.path = path
        self.runtime_id = runtime_id

    @staticmethod
    def _alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return int(exit_code.value) == 259  # STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                existing = json.loads(self.path.read_text(encoding="utf-8"))
                pid = int(existing.get("pid", -1))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pid = -1
            if self._alive(pid):
                raise RuntimeError(f"state directory is already owned by runtime PID {pid}")
            self.path.unlink(missing_ok=True)
        _atomic_json(self.path, {
            "protocol": "underreach.alpha-runtime-lock.v1",
            "runtime_id": self.runtime_id,
            "pid": os.getpid(),
            "created_at_unix_ms": int(time.time() * 1000),
        })

    def release(self) -> None:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("runtime_id") == self.runtime_id and int(value.get("pid", -1)) == os.getpid():
                self.path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass


class UnderreachRuntimeSupervisor:
    def __init__(
        self,
        *,
        repo_root: Path,
        profile: RuntimeProfile,
        state_directory: Path,
        generated_directory: Path,
        viewer_static_directory: Path | None,
        viewer_port: int,
        seed: str,
        resume: bool,
        unreal_editor_cmd: Path | None,
        unreal_project: Path | None,
        fault_injection: bool = False,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.profile = profile
        self.state_directory = state_directory.resolve()
        self.generated_directory = generated_directory.resolve()
        self.viewer_static_directory = viewer_static_directory.resolve() if viewer_static_directory else None
        self.viewer_port = viewer_port
        self.seed = seed
        self.resume_requested = resume
        self.unreal_editor_cmd = unreal_editor_cmd
        self.unreal_project = unreal_project
        self.fault_injection = bool(fault_injection)
        identity = f"{int(time.time() * 1000)}:{os.getpid()}:{profile.name}:{seed}"
        self.runtime_id = f"runtime_{sha256(identity.encode()).hexdigest()[:20]}"
        self.started_wall = time.time()
        self.started_monotonic = time.monotonic()
        self.stop_event = threading.Event()
        self.state_lock = threading.RLock()
        self.lock = RuntimeLock(self.state_directory / "runtime.lock", self.runtime_id)
        self.components = {
            name: ComponentHealth(name)
            for name in ("simulation", "ledger_producer", "live_bridge", "feed_api", "viewer_server", "unreal_consumer", "camera_feed")
        }
        if not profile.viewer:
            self.components["feed_api"].status = "disabled"
            self.components["viewer_server"].status = "disabled"
        if not profile.unreal:
            self.components["unreal_consumer"].status = "disabled"
        self.overall_status = "starting"
        self.accept_controls = True
        self.viewer_available = True
        self.checkpoint_store = AlphaCheckpointStore(
            self.state_directory / "checkpoints", retention=profile.checkpoint_retention
        )
        self.latest_checkpoint: dict[str, Any] | None = None
        self.checkpoint_sizes: list[int] = []
        self.checkpoint_failures = 0
        self.checkpoint_recoveries = 0
        self.canonical_recovery_failures = 0
        self.presentation_backlog_skipped = 0
        self.canonical_failures = 0
        self.viewer_health_failures = 0
        self.feed_health_failures = 0
        self.unreal_health_failures = 0
        self.faults_exercised: list[str] = []
        self.server = None
        self.server_thread: threading.Thread | None = None
        self.unreal_process: subprocess.Popen | None = None
        self.unreal_started_monotonic: float | None = None
        self.unreal_streams: list[Any] = []
        self.restarts = 0
        self.recoveries = 0
        self.steps = 0
        self.frames_written = 0
        self.transport_paused_until: float | None = None
        self.paused_frames: list[dict[str, Any]] = []
        self.maximum_queue_depth = 0
        self.maximum_presentation_lag = 0
        self.initial_rss: int | None = None
        self.peak_rss = 0
        self.final_rss: int | None = None
        self.initial_disk = 0
        self.final_disk = 0
        self.metric_count = 0
        self._last_metric_cpu = time.process_time()
        self._last_metric_wall = time.monotonic()
        self.metrics_path = self.generated_directory / "runtime_soak_metrics.jsonl"
        self.report_path = self.generated_directory / "underreach_alpha_runtime_report.json"
        self.runtime_state_path = self.state_directory / "state" / "runtime.json"
        self.logs_directory = self.state_directory / "logs"
        self.spool = self.generated_directory / "LiveBridge"
        self.database_path = self.state_directory / "state" / "underreach.sqlite3"
        self.stop_request_path = self.state_directory / "stop.request"
        self.persistence: CrawlPersistence | None = None
        self.service: CrawlLifecycleService | None = None
        self.descent: Crawl | None = None
        self.simulation: HeadlessCrawlMVP | None = None
        self.buffer: LiveLedgerBuffer | None = None
        self.scheduler: LivePresentationScheduler | None = None
        self.registry: FeedChannelRegistry | None = None
        self.environment: dict[str, Any] = {}
        self.environment_digest = ""
        self._last_checkpoint_monotonic = 0.0
        self._last_health_monotonic = 0.0
        self._last_metrics_monotonic = 0.0
        self._fault_started = self.started_monotonic
        self.operational_started: float | None = None

    @property
    def uptime(self) -> float:
        return max(0.0, time.monotonic() - self.started_monotonic)

    def _events(self) -> list[Any]:
        assert self.persistence is not None and self.descent is not None
        return self.persistence.replay_events(self.descent.id)

    def _load_environment(self) -> dict[str, Any]:
        path = self.generated_directory / "environment_manifest.json"
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
        else:
            value = {"protocol": "crawl.presentation-environment.v1", "room_id": "accepted_stone_dungeon"}
        build_path = self.generated_directory / "unreal_build_result.json"
        if build_path.exists():
            build = json.loads(build_path.read_text(encoding="utf-8"))
            value["accepted_level_asset"] = build.get("level_asset")
            value["accepted_map_object"] = build.get("map_object")
        return value

    def _simulation_config(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "floor_count": self.profile.floor_count,
            "descender_ids": list(DEFAULT_DESCENDERS),
            "intermission_ticks": 2,
            "director_interval": 5,
            "profile": self.profile.name,
        }

    def _prepare_authority(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.persistence = CrawlPersistence(f"sqlite:///{self.database_path.as_posix()}")
        self.persistence.initialize()
        self.service = CrawlLifecycleService(self.persistence)
        restored_presentation = None
        restored_feed = None
        if self.resume_requested:
            loaded = self.checkpoint_store.load_latest()
            self.descent = loaded.crawl.model_copy(deep=True)
            self.seed = self.descent.seed
            removed = self.persistence.restore_checkpoint_state(self.descent)
            stored = self.persistence.replay_events(self.descent.id)
            cursor = loaded.payload["canonical"]["ledger_cursor"]
            if ledger_digest(stored) != cursor["ledger_digest"]:
                raise CheckpointError("durable Ledger digest does not match latest checkpoint")
            restored_presentation = loaded.payload.get("presentation")
            restored_feed = loaded.payload.get("feed")
            self.latest_checkpoint = {
                "path": str(loaded.path), "tick": self.descent.current_tick,
                "digest": loaded.payload["digest"], "created_at_unix_ms": loaded.payload["created_at_unix_ms"],
            }
            self.checkpoint_recoveries += 1
            self.recoveries += 1
            self.presentation_backlog_skipped += removed
        else:
            if self.database_path.exists() and self.persistence.list_crawls(limit=1):
                raise RuntimeError("state directory already contains a Descent; start with --resume or use a new state directory")
            self.descent = self.service.create_seeded_crawl(
                seed=self.seed,
                crawler_ids=DEFAULT_DESCENDERS,
                floor_count=self.profile.floor_count,
            )
            self.service.start(self.descent)
        assert self.descent is not None
        self.simulation = HeadlessCrawlMVP(self.service, intermission_ticks=2, director_interval=5)
        if not self.descent.encounters:
            self.simulation.prepare(self.descent)
        self.environment = self._load_environment()
        self.environment_digest = payload_digest(self.environment)
        self.buffer = LiveLedgerBuffer(self.descent.id, presentation_delay_ticks=3, maximum_events=2048)
        self.scheduler = LivePresentationScheduler(
            self.descent.id,
            presentation_seed=f"{self.seed}:alpha-28c2",
            focus_actor_ids=PRESENTED_DESCENDERS,
            seconds_per_tick=0.45,
            camera_config=LiveCameraConfig(presentation_delay_ticks=3, camera_lookahead_ticks=2),
        )
        self.registry = FeedChannelRegistry(self.descent.id, default_viewer_id="viewer_local_alpha")
        self.registry.register(self.descent)
        bootstrap = self.scheduler.bootstrap(self.descent, environment=self.environment)
        if restored_presentation:
            self.scheduler.restore_reconnect_snapshot(restored_presentation, self.descent)
        if restored_feed:
            self.registry.restore(restored_feed)
        transitions = self.registry.update(
            self.descent,
            [],
            presentation_tick=self.scheduler.frame_sequence,
            presentation_seconds=self.scheduler.presentation_seconds,
            buffered_tick=self.descent.current_tick,
            camera_available_ids=PRESENTED_DESCENDERS,
            camera_state=self.scheduler.camera_director.snapshot(),
        )
        for transition in transitions:
            self.scheduler.queue_focus_transition(transition.as_dict())
        self._write_bootstrap(bootstrap)
        for name in ("simulation", "ledger_producer", "live_bridge", "camera_feed"):
            self.components[name].healthy(self.descent.current_tick, pid=os.getpid())

    def _write_bootstrap(self, bootstrap: dict[str, Any] | None = None) -> None:
        assert self.descent is not None and self.scheduler is not None
        self.spool.mkdir(parents=True, exist_ok=True)
        (self.spool / "deliveries").mkdir(parents=True, exist_ok=True)
        if bootstrap is None:
            snapshot = self.scheduler.reconnect_snapshot(self.descent, environment_digest=self.environment_digest)
            body = {
                "protocol": "underreach.live-presentation.v1",
                "authoritative": False,
                "message_type": "bootstrap",
                "descent_id": self.descent.id,
                "scheduler_version": "28c2.1",
                "simulation_tick": self.descent.current_tick,
                "presentation": {"tick": self.scheduler.frame_sequence, "seconds": self.scheduler.presentation_seconds},
                "stratum_number": self.descent.current_floor,
                "sector_id": next((item.sector_id for item in self.scheduler.actors.values() if item.sector_id), None),
                "environment": self.environment,
                "actors": snapshot["actors"],
                "resume_cursor": snapshot["resume_cursor"],
            }
            bootstrap = {**body, "digest": payload_digest(body)}
        body = {key: value for key, value in bootstrap.items() if key not in {"digest", "presentation_profile"}}
        body["presentation_profile"] = "28c2_alpha_runtime"
        bootstrap = {**body, "digest": payload_digest(body)}
        _atomic_json(self.spool / "bootstrap.json", bootstrap)
        (self.spool / "producer_complete.json").unlink(missing_ok=True)

    def _runtime_health(self) -> dict[str, Any]:
        with self.state_lock:
            descent_tick = self.descent.current_tick if self.descent else 0
            presentation_tick = self.scheduler.frame_sequence if self.scheduler else 0
            buffered_tick = self.buffer.latest_authoritative_tick if self.buffer else 0
            lag = max(0, descent_tick - max(0, buffered_tick))
            checkpoint_age = None
            if self.latest_checkpoint:
                checkpoint_age = max(0.0, time.time() - self.latest_checkpoint["created_at_unix_ms"] / 1000.0)
            return {
                "protocol": RUNTIME_PROTOCOL,
                "runtime_version": RUNTIME_VERSION,
                "authoritative": False,
                "runtime_id": self.runtime_id,
                "profile": self.profile.name,
                "overall_status": self.overall_status,
                "uptime_seconds": round(self.uptime, 3),
                "simulation_tick": descent_tick,
                "ledger_tick": descent_tick,
                "presentation_tick": presentation_tick,
                "buffered_tick": buffered_tick,
                "presentation_lag_ticks": lag,
                "unreal_connected": self.components["unreal_consumer"].status == "healthy",
                "automatic_feed_active": bool(
                    self.registry and self.registry.active_focus("viewer_local_alpha").get("focus_mode") == "automatic"
                ),
                "latest_checkpoint": self.latest_checkpoint,
                "checkpoint_age_seconds": round(checkpoint_age, 3) if checkpoint_age is not None else None,
                "restart_count": self.restarts,
                "recovery_count": self.recoveries,
                "components": {name: asdict(value) for name, value in self.components.items()},
            }

    def _live_status(self) -> dict[str, Any]:
        assert self.descent is not None and self.scheduler is not None and self.registry is not None
        return {
            "protocol": "underreach.live-presentation.v1", "authoritative": False,
            "descent_id": self.descent.id, "status": "live" if self.overall_status != "failed" else "offline",
            "connected_presenter": self.components["unreal_consumer"].status == "healthy" or not self.profile.unreal,
            "simulation_tick": self.descent.current_tick, "presentation_tick": self.scheduler.frame_sequence,
            "frame_id": self.registry.latest_frame_id, "updated_at_unix_ms": int(time.time() * 1000),
        }

    def _live_camera(self) -> dict[str, Any]:
        assert self.scheduler is not None
        snapshot = self.scheduler.camera_director.snapshot()
        return {**snapshot, "authoritative": False, "status": "live" if snapshot.get("active_shot") else "waiting", "presentation_tick": self.scheduler.frame_sequence}

    def _start_server(self) -> None:
        if not self.profile.viewer:
            return
        import uvicorn
        assert self.persistence is not None and self.descent is not None and self.registry is not None and self.scheduler is not None
        repository = SpectatorRepository(self.persistence, self.descent.id)
        app = create_feed_app(
            repository,
            live_status_provider=self._live_status,
            live_camera_provider=self._live_camera,
            feed_channel_registry=self.registry,
            focus_transition_sink=self.scheduler.queue_focus_transition,
            viewer_static_directory=self.viewer_static_directory,
            runtime_health_provider=self._runtime_health,
        )

        @app.middleware("http")
        async def viewer_availability(request, call_next):
            if request.url.path == "/" and not self.viewer_available:
                return PlainTextResponse("Underreach viewer is recovering", status_code=503)
            return await call_next(request)

        config = uvicorn.Config(app, host="127.0.0.1", port=self.viewer_port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        self.server_thread = threading.Thread(target=self.server.run, name="underreach-feed-api", daemon=True)
        self.server_thread.start()
        deadline = time.monotonic() + 20.0
        while not self.server.started and self.server_thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not self.server.started:
            raise RuntimeError("Feed API did not start")
        self.components["feed_api"].healthy(self.descent.current_tick, pid=os.getpid())
        self.components["viewer_server"].healthy(self.descent.current_tick, pid=os.getpid())

    def _stop_server(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.server_thread is not None:
            self.server_thread.join(timeout=15.0)
        self.server = None
        self.server_thread = None

    def _rotate_log(self, path: Path, *, maximum_bytes: int = 8 * 1024 * 1024, keep: int = 4) -> None:
        if not path.exists() or path.stat().st_size <= maximum_bytes:
            return
        for index in range(keep - 1, 0, -1):
            older = path.with_suffix(path.suffix + f".{index}")
            newer = path.with_suffix(path.suffix + f".{index + 1}")
            if older.exists():
                os.replace(older, newer)
        os.replace(path, path.with_suffix(path.suffix + ".1"))

    def _start_unreal(self, *, restart: bool = False) -> None:
        if not self.profile.unreal:
            return
        if not self.unreal_editor_cmd or not self.unreal_project:
            raise RuntimeError("Unreal paths are required by this runtime profile")
        self._write_bootstrap(None)
        for marker in ("presenter_ready.json", "presenter_heartbeat.json"):
            (self.spool / marker).unlink(missing_ok=True)
        delivery_dir = self.spool / "deliveries"
        for item in delivery_dir.glob("*.json"):
            item.unlink(missing_ok=True)
        self.logs_directory.mkdir(parents=True, exist_ok=True)
        stdout_path = self.logs_directory / "unreal-stdout.log"
        stderr_path = self.logs_directory / "unreal-stderr.log"
        self._rotate_log(stdout_path)
        self._rotate_log(stderr_path)
        stdout = stdout_path.open("ab")
        stderr = stderr_path.open("ab")
        self.unreal_streams.extend([stdout, stderr])
        consumer = self.repo_root / "unreal" / "CrawlPresentation" / "Content" / "Python" / "consume_underreach_live_bridge.py"
        log_path = self.logs_directory / "unreal-runtime.log"
        args = [
            str(self.unreal_editor_cmd), str(self.unreal_project), f"-ExecutePythonScript={consumer}",
            "-unattended", "-nop4", "-nosplash", f"-abslog={log_path}",
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.unreal_process = subprocess.Popen(
            args, cwd=self.repo_root, stdout=stdout, stderr=stderr, creationflags=creationflags
        )
        self.unreal_started_monotonic = time.monotonic()
        if restart:
            self.components["unreal_consumer"].restart_count += 1
            self.restarts += 1
        self.components["unreal_consumer"].status = "starting"
        self.components["unreal_consumer"].pid = self.unreal_process.pid

    def _stop_unreal(self, *, graceful: bool = True) -> None:
        process = self.unreal_process
        if process is None:
            return
        if graceful and process.poll() is None:
            deadline = time.monotonic() + 45.0
            while process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.2)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10.0)
        self.unreal_process = None
        self.unreal_started_monotonic = None
        for stream in self.unreal_streams:
            try:
                stream.close()
            except OSError:
                pass
        self.unreal_streams.clear()

    def _persist_delivery(self, frame: dict[str, Any]) -> None:
        self.frames_written += 1
        _atomic_json(self.spool / "deliveries" / f"{self.frames_written:09d}.json", frame)
        retained = sorted((self.spool / "deliveries").glob("*.json"), key=lambda item: item.name)
        for stale in retained[:-self.profile.delivery_retention]:
            stale.unlink(missing_ok=True)

    def _write_delivery(self, frame: dict[str, Any]) -> None:
        if self.transport_paused_until is not None:
            self.paused_frames.append(json.loads(canonical_json(frame)))
            if len(self.paused_frames) > 64:
                self.paused_frames.pop(0)
                self.presentation_backlog_skipped += 1
            return
        self._persist_delivery(frame)

    def _recover_presentation_transport(self) -> None:
        if self.transport_paused_until is None or time.monotonic() < self.transport_paused_until:
            return
        for frame in self.paused_frames:
            self._persist_delivery(frame)
        self.paused_frames.clear()
        self.transport_paused_until = None
        self.components["unreal_consumer"].restart_count += 1
        self.restarts += 1
        self.recoveries += 1

    def _schedule_events(self, events: list[Any], *, flush: bool = False) -> None:
        assert self.buffer is not None and self.scheduler is not None and self.registry is not None and self.descent is not None
        if events:
            self.buffer.push(events)
        ready = self.buffer.consume_ready(flush=flush)
        depth = self.buffer.snapshot()["buffer_depth"]
        self.maximum_queue_depth = max(self.maximum_queue_depth, depth)
        transitions = self.registry.update(
            self.descent,
            ready,
            presentation_tick=self.scheduler.frame_sequence + (1 if ready else 0),
            presentation_seconds=self.scheduler.presentation_seconds,
            buffered_tick=self.buffer.latest_authoritative_tick,
            camera_available_ids=PRESENTED_DESCENDERS,
            camera_state=self.scheduler.camera_director.snapshot(),
        )
        for transition in transitions:
            self.scheduler.queue_focus_transition(transition.as_dict())
        lookahead = self.buffer.peek_lookahead(
            after_tick=max([item.tick for item in ready] or [self.descent.current_tick]),
            lookahead_ticks=2,
        )
        frame = self.scheduler.schedule(
            ready,
            authoritative_tick=self.descent.current_tick,
            camera_lookahead_events=lookahead,
        )
        if frame:
            self._write_delivery(frame)
            self.registry.latest_frame_id = frame["frame_id"]
            self.registry.viewers["viewer_local_alpha"].last_seen_frame_id = frame["frame_id"]
        lag = max(0, self.descent.current_tick - max(0, self.buffer.latest_authoritative_tick))
        self.maximum_presentation_lag = max(self.maximum_presentation_lag, lag)

    def _checkpoint(self, reason: str) -> None:
        assert self.descent is not None and self.scheduler is not None and self.registry is not None
        try:
            loaded = self.checkpoint_store.write(
                self.runtime_id,
                self.descent,
                self._events(),
                simulation_config=self._simulation_config(),
                presentation_snapshot=self.scheduler.reconnect_snapshot(self.descent, environment_digest=self.environment_digest),
                feed_snapshot=self.registry.reconnect_snapshot(),
                reason=reason,
                created_at_unix_ms=int(time.time() * 1000),
            )
            size = loaded.path.stat().st_size
            self.checkpoint_sizes.append(size)
            self.latest_checkpoint = {
                "path": str(loaded.path), "tick": self.descent.current_tick,
                "digest": loaded.payload["digest"], "created_at_unix_ms": loaded.payload["created_at_unix_ms"],
                "size_bytes": size,
            }
            self._last_checkpoint_monotonic = time.monotonic()
        except Exception:
            self.checkpoint_failures += 1
            raise

    def _sample_metrics(self) -> None:
        assert self.descent is not None and self.buffer is not None and self.scheduler is not None and self.registry is not None
        now = time.monotonic()
        rss = _rss_bytes(os.getpid())
        if rss is not None:
            self.peak_rss = max(self.peak_rss, rss)
        wall_delta = max(1e-6, now - self._last_metric_wall)
        cpu_now = time.process_time()
        cpu_percent = max(0.0, min(100.0, (cpu_now - self._last_metric_cpu) / wall_delta * 100.0))
        unreal_rss = _rss_bytes(self.unreal_process.pid) if self.unreal_process and self.unreal_process.poll() is None else None
        item = {
            "protocol": "underreach.alpha-runtime-metric.v1",
            "runtime_id": self.runtime_id,
            "unix_ms": int(time.time() * 1000),
            "uptime_seconds": round(self.uptime, 3),
            "simulation_tick": self.descent.current_tick,
            "ledger_event_count": len(self.descent.history_event_ids),
            "presentation_tick": self.scheduler.frame_sequence,
            "presentation_lag_ticks": max(0, self.descent.current_tick - max(0, self.buffer.latest_authoritative_tick)),
            "bridge_queue_depth": self.buffer.snapshot()["buffer_depth"],
            "scheduler_pending_intents": len(self.scheduler.pending_focus_transitions),
            "registry_recent_events": len(self.registry.recent_events),
            "registry_transitions": len(self.registry.transitions),
            "scheduler_dedup_ids": len(self.scheduler.processed_event_ids),
            "scheduler_commands_retained": len(self.scheduler.command_stream),
            "camera_shots_retained": len(self.scheduler.camera_director.shots),
            "delivery_files_retained": len(list((self.spool / "deliveries").glob("*.json"))),
            "checkpoint_size_bytes": self.checkpoint_sizes[-1] if self.checkpoint_sizes else 0,
            "runtime_disk_bytes": _directory_size(self.state_directory),
            "process_rss_bytes": rss,
            "unreal_rss_bytes": unreal_rss,
            "process_cpu_percent": round(cpu_percent, 3),
            "overall_status": self.overall_status,
        }
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self.metrics_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
        self.metric_count += 1
        self._last_metric_cpu = cpu_now
        self._last_metric_wall = now
        self._last_metrics_monotonic = now

    def _poll_health(self) -> None:
        assert self.descent is not None and self.buffer is not None
        tick = self.descent.current_tick
        for name in ("simulation", "ledger_producer", "live_bridge", "camera_feed"):
            self.components[name].healthy(tick, pid=os.getpid())
            self.components[name].memory_bytes = _rss_bytes(os.getpid())
        if self.profile.viewer:
            if self.server_thread and self.server_thread.is_alive() and self.server and self.server.started:
                self.components["feed_api"].healthy(tick, pid=os.getpid())
                if self.viewer_available:
                    self.components["viewer_server"].healthy(tick, pid=os.getpid())
            else:
                self.feed_health_failures += 1
                self.components["feed_api"].fail("HTTP server stopped", recovering=True)
                self.components["viewer_server"].fail("Feed API unavailable", recovering=True)
                self._stop_server()
                self._start_server()
                self.components["feed_api"].restart_count += 1
                self.components["viewer_server"].restart_count += 1
                self.restarts += 1
        if self.profile.unreal:
            heartbeat = self.spool / "presenter_heartbeat.json"
            process_ok = self.unreal_process is not None and self.unreal_process.poll() is None
            fresh = heartbeat.exists() and time.time() - heartbeat.stat().st_mtime < 12.0
            startup_age = (
                time.monotonic() - self.unreal_started_monotonic
                if self.unreal_started_monotonic is not None else float("inf")
            )
            if process_ok and fresh:
                self.components["unreal_consumer"].healthy(tick, pid=self.unreal_process.pid)
                self.components["unreal_consumer"].memory_bytes = _rss_bytes(self.unreal_process.pid)
            elif not process_ok or (startup_age > 180.0 and not fresh):
                self.unreal_health_failures += 1
                self.components["unreal_consumer"].fail("Unreal process or heartbeat unavailable", recovering=True)
                self._stop_unreal(graceful=False)
                self._start_unreal(restart=True)
        statuses = [item.status for item in self.components.values() if item.status != "disabled"]
        self.overall_status = "healthy" if statuses and all(item == "healthy" for item in statuses) else "recovering" if any(item == "recovering" for item in statuses) else "degraded"
        self._last_health_monotonic = time.monotonic()
        _atomic_json(self.runtime_state_path, self._runtime_health())

    def _inject_faults(self) -> None:
        if not self.fault_injection:
            return
        elapsed = max(0.0, time.monotonic() - (self.operational_started or time.monotonic()))
        if elapsed >= 8.0 and "viewer" not in self.faults_exercised and self.profile.viewer:
            before = self.descent.fingerprint()
            self.viewer_available = False
            self.viewer_health_failures += 1
            self.components["viewer_server"].fail("QA viewer outage", recovering=True)
            time.sleep(0.25)
            self.viewer_available = True
            self.components["viewer_server"].restart_count += 1
            self.restarts += 1
            if self.descent.fingerprint() != before:
                raise RuntimeError("viewer fault mutated canonical state")
            self.faults_exercised.append("viewer")
        if elapsed >= 12.0 and "feed_api" not in self.faults_exercised and self.profile.viewer:
            before = self.descent.fingerprint()
            self._stop_server()
            self.feed_health_failures += 1
            self.components["feed_api"].fail("QA API outage", recovering=True)
            self._start_server()
            self.components["feed_api"].restart_count += 1
            self.restarts += 1
            if self.descent.fingerprint() != before:
                raise RuntimeError("Feed API fault mutated canonical state")
            self.faults_exercised.append("feed_api")
        if (
            elapsed >= 16.0
            and "unreal" not in self.faults_exercised
            and self.profile.unreal
            and self.components["unreal_consumer"].status == "healthy"
        ):
            before = self.descent.fingerprint()
            self.unreal_health_failures += 1
            # UE 5.8 editor startup is intentionally expensive on this proof
            # project. Exercise the disposable bridge/consumer transport by
            # pausing delivery while the canonical simulation continues, then
            # replay the small bounded gap in order. Actual process death still
            # uses the full restart/bootstrap policy in _poll_health.
            self.components["unreal_consumer"].fail("QA bridge transport disconnect", recovering=True)
            self.transport_paused_until = time.monotonic() + 2.0
            if self.descent.fingerprint() != before:
                raise RuntimeError("Unreal fault mutated canonical state")
            self.faults_exercised.append("unreal")

    def _producer_complete(self) -> None:
        assert self.descent is not None and self.scheduler is not None
        camera = self.scheduler.camera_director.diagnostics(self.scheduler.presentation_seconds + 4.0)
        _atomic_json(self.generated_directory / "live_camera_debug.json", camera)
        _atomic_json(self.generated_directory / "live_scheduler_debug.json", self.scheduler.diagnostics())
        producer = {
            "protocol": "underreach.alpha-runtime-producer.v1",
            "runtime_id": self.runtime_id,
            "descent_id": self.descent.id,
            "incremental_frame_count": self.scheduler.frame_sequence,
            "intentional_duplicate_deliveries": 0,
            "simulation_tick": self.descent.current_tick,
            "ledger_event_count": len(self.descent.history_event_ids),
            "authoritative_fingerprint": self.descent.fingerprint(),
        }
        _atomic_json(self.spool / "producer_complete.json", producer)

    def _report(self, *, exit_status: str, error: str | None = None) -> dict[str, Any]:
        assert self.descent is not None
        events = self._events()
        duration = self.uptime
        self.final_rss = _rss_bytes(os.getpid())
        self.final_disk = _directory_size(self.state_directory)
        report = {
            "protocol": RUNTIME_PROTOCOL,
            "runtime_version": RUNTIME_VERSION,
            "runtime_id": self.runtime_id,
            "profile": self.profile.name,
            "exit_status": exit_status,
            "error": error,
            "seed": self.seed,
            "descent_id": self.descent.id,
            "requested_duration_seconds": getattr(self, "requested_duration_seconds", None),
            "actual_duration_seconds": round(duration, 3),
            "operational_duration_seconds": round(
                max(0.0, time.monotonic() - self.operational_started)
                if self.operational_started is not None else 0.0,
                3,
            ),
            "simulation_steps": self.steps,
            "simulation_ticks": self.descent.current_tick,
            "ledger_event_count": len(events),
            "final_fingerprint": self.descent.fingerprint(),
            "final_ledger_digest": ledger_digest(events),
            "checkpoint_count": len(self.checkpoint_sizes),
            "checkpoint_failures": self.checkpoint_failures,
            "checkpoint_recoveries": self.checkpoint_recoveries,
            "latest_checkpoint": self.latest_checkpoint,
            "checkpoint_average_size_bytes": sum(self.checkpoint_sizes) / max(1, len(self.checkpoint_sizes)),
            "checkpoint_maximum_size_bytes": max(self.checkpoint_sizes or [0]),
            "checkpoint_retention": self.profile.checkpoint_retention,
            "canonical_failures": self.canonical_failures,
            "canonical_recovery_failures": self.canonical_recovery_failures,
            "viewer_health_failures": self.viewer_health_failures,
            "feed_health_failures": self.feed_health_failures,
            "unreal_health_failures": self.unreal_health_failures,
            "restart_count": self.restarts,
            "recovery_count": self.recoveries,
            "faults_exercised": list(self.faults_exercised),
            "presentation_backlog_skipped": self.presentation_backlog_skipped,
            "maximum_queue_depth": self.maximum_queue_depth,
            "maximum_presentation_lag_ticks": self.maximum_presentation_lag,
            "metric_count": self.metric_count,
            "initial_process_rss_bytes": self.initial_rss,
            "peak_process_rss_bytes": self.peak_rss,
            "final_process_rss_bytes": self.final_rss,
            "process_rss_growth_bytes": (self.final_rss - self.initial_rss) if self.final_rss is not None and self.initial_rss is not None else None,
            "process_rss_growth_per_hour_bytes": ((self.final_rss - self.initial_rss) / max(duration / 3600.0, 1e-9)) if self.final_rss is not None and self.initial_rss is not None else None,
            "initial_disk_bytes": self.initial_disk,
            "final_disk_bytes": self.final_disk,
            "disk_growth_bytes": self.final_disk - self.initial_disk,
            "components": {name: asdict(value) for name, value in self.components.items()},
            "final_checkpoint_on_shutdown": bool(self.latest_checkpoint and self.latest_checkpoint["tick"] == self.descent.current_tick),
            "metrics_path": str(self.metrics_path),
            "state_directory": str(self.state_directory),
            "viewer_url": f"http://127.0.0.1:{self.viewer_port}" if self.profile.viewer else None,
            "no_github_actions": True,
        }
        _atomic_json(self.report_path, report)
        return report

    def run(self, duration_seconds: float | None = None) -> dict[str, Any]:
        if duration_seconds is not None and duration_seconds <= 0:
            raise ValueError("duration must be positive")
        self.requested_duration_seconds = duration_seconds
        self.lock.acquire()
        self.stop_request_path.unlink(missing_ok=True)
        if not self.resume_requested:
            self.metrics_path.unlink(missing_ok=True)
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.initial_disk = _directory_size(self.state_directory)
        self.initial_rss = _rss_bytes(os.getpid())
        if self.initial_rss is not None:
            self.peak_rss = self.initial_rss
        error: str | None = None
        exit_status = "completed"
        try:
            self._prepare_authority()
            if not self.resume_requested:
                self._schedule_events(self._events(), flush=True)
            self._checkpoint("startup")
            self._start_server()
            self._start_unreal()
            self._poll_health()
            self.operational_started = time.monotonic()
            print("Simulation: HEALTHY", flush=True)
            print("Feed API: " + ("HEALTHY" if self.profile.viewer else "DISABLED"), flush=True)
            if self.profile.viewer:
                print(f"Viewer: http://127.0.0.1:{self.viewer_port}", flush=True)
            print("Unreal: " + ("STARTING" if self.profile.unreal else "DISABLED"), flush=True)
            print("Auto Feed: ACTIVE", flush=True)
            print("Checkpointing: ACTIVE", flush=True)
            # Requested duration measures unattended operation after the stack
            # has become ready; startup asset/checkpoint work is reported in
            # total uptime but must not consume a short QA run.
            deadline = time.monotonic() + duration_seconds if duration_seconds else None
            next_step = time.monotonic()
            while not self.stop_event.is_set() and (deadline is None or time.monotonic() < deadline):
                if self.stop_request_path.exists():
                    try:
                        request = json.loads(self.stop_request_path.read_text(encoding="utf-8-sig"))
                    except (OSError, json.JSONDecodeError):
                        request = {}
                    if request.get("runtime_id") == self.runtime_id:
                        self.stop_event.set()
                        break
                now = time.monotonic()
                if now >= next_step:
                    if self.descent.status != CrawlStatus.RUNNING:
                        raise RuntimeError("long-running Descent completed before the requested runtime duration")
                    before_count = len(self.descent.history_event_ids)
                    try:
                        self.simulation.step(self.descent)
                    except Exception as exc:
                        self.canonical_failures += 1
                        self.components["simulation"].fail(str(exc), recovering=True)
                        loaded = self.checkpoint_store.load_latest()
                        self.descent = loaded.crawl.model_copy(deep=True)
                        self.persistence.restore_checkpoint_state(self.descent)
                        self.simulation = HeadlessCrawlMVP(self.service, intermission_ticks=2, director_interval=5)
                        self.checkpoint_recoveries += 1
                        self.recoveries += 1
                        continue
                    self.steps += 1
                    new_ids = self.descent.history_event_ids[before_count:]
                    new_events = self.persistence.events_by_ids(new_ids)
                    self._schedule_events(new_events)
                    next_step = now + self.profile.tick_interval_seconds
                if now - self._last_checkpoint_monotonic >= self.profile.checkpoint_interval_seconds:
                    self._checkpoint("scheduled")
                if now - self._last_health_monotonic >= self.profile.health_interval_seconds:
                    self._poll_health()
                if now - self._last_metrics_monotonic >= self.profile.metrics_interval_seconds:
                    self._sample_metrics()
                self._inject_faults()
                self._recover_presentation_transport()
                time.sleep(min(0.1, max(0.01, self.profile.tick_interval_seconds / 4.0)))
            self._schedule_events([], flush=True)
            self.transport_paused_until = 0.0 if self.transport_paused_until is not None else None
            self._recover_presentation_transport()
        except KeyboardInterrupt:
            exit_status = "stopped"
        except Exception as exc:
            exit_status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            self.overall_status = "failed"
            raise
        finally:
            self.accept_controls = False
            self.overall_status = "stopping"
            if self.descent is not None:
                try:
                    self._checkpoint("clean_shutdown")
                except Exception as checkpoint_exc:
                    self.checkpoint_failures += 1
                    if error is None:
                        error = f"shutdown checkpoint failed: {checkpoint_exc}"
                        exit_status = "failed"
                try:
                    self._producer_complete()
                except Exception as producer_exc:
                    if error is None:
                        error = f"producer finalization failed: {producer_exc}"
                        exit_status = "failed"
            # Stop accepting viewer controls before waiting for Unreal to
            # finish its presentation-only finalization.
            self._stop_server()
            self._stop_unreal(graceful=True)
            for item in self.components.values():
                if item.status != "disabled":
                    item.status = "stopped"
            self.overall_status = "stopped" if exit_status != "failed" else "failed"
            # Leave the durable operator snapshot in the same terminal state
            # as the final report.  The lock is the ownership authority, but a
            # stale "healthy" status after Ctrl+C is actively misleading when
            # inspecting an offline runtime directory.
            _atomic_json(self.runtime_state_path, self._runtime_health())
            report = self._report(exit_status=exit_status, error=error) if self.descent is not None else {}
            self.lock.release()
        return report

    def request_stop(self) -> None:
        self.stop_event.set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the unattended Underreach Alpha stack")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="alpha")
    parser.add_argument("--state-directory", type=Path, required=True)
    parser.add_argument("--generated-directory", type=Path, required=True)
    parser.add_argument("--viewer-static-directory", type=Path)
    parser.add_argument("--viewer-port", type=int, default=8011)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--unreal-editor-cmd", type=Path)
    parser.add_argument("--unreal-project", type=Path)
    parser.add_argument("--fault-injection", action="store_true")
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    supervisor = UnderreachRuntimeSupervisor(
        repo_root=args.repo_root,
        profile=profile,
        state_directory=args.state_directory,
        generated_directory=args.generated_directory,
        viewer_static_directory=args.viewer_static_directory,
        viewer_port=args.viewer_port,
        seed=args.seed,
        resume=args.resume,
        unreal_editor_cmd=args.unreal_editor_cmd,
        unreal_project=args.unreal_project,
        fault_injection=args.fault_injection,
    )

    def stop(_signum, _frame):
        supervisor.request_stop()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    report = supervisor.run(args.duration_seconds)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
