#!/usr/bin/env python3
"""Project Mode — muse-pc-bridge (durable job runner release).

A PC mode toggle that hands the machine's headroom to GPU jobs
and gives the desktop back untouched afterwards. The owner's PC
(RTX 3060, 12 GB) holds ~2.2 GB of VRAM at desktop idle — Lively
live-wallpaper rendering, hardware-accelerated apps, launcher
helpers. Project Mode exists to reclaim that on demand:

    POST /v1/project-mode/engage
    POST /v1/project-mode/disengage
    GET  /v1/project-mode

Engage performs five steps, each individually recorded in
`<state_dir>/project-mode.json`, appended to
`<state_dir>/project-mode-events.jsonl`, and reported in the
response — applied, skipped, or failed, never silently partial:

1. **power_plan** — record the active scheme GUID, switch to
   High Performance.
2. **lively** — gracefully close Lively wallpaper processes
   (rendering stops; the exe path is recorded for relaunch).
3. **close_list** — gracefully close processes named in the
   configurable close list (config `project_mode_close_list`).
   Shipped defaults are launcher BACKGROUND HELPERS ONLY
   (steamwebhelper.exe, EpicWebHelper.exe). Browsers and chat
   apps are NOT defaults — the owner curates the list. Closing
   is graceful-first and graceful-only: a window close request,
   a grace wait, and if the process is still alive it is LEFT
   RUNNING and the step says so. Nothing is ever force-killed
   (an app may hold unsaved work), and nothing not on the list
   is ever touched.
4. **onedrive** — quit the OneDrive client (sync pauses while
   the client is closed; relaunching on disengage resumes it).
5. **search_indexing** — stop the Windows Search service
   (WSearch) so indexing pauses.

Disengage restores EXACTLY what the state file recorded —
previous power-plan GUID, relaunch of precisely the processes
engage closed (by recorded exe path), service restart only if
engage stopped it — nothing more, nothing less. If engage
skipped a step, disengage has nothing to restore for it.

Elevation honesty: steps degrade individually. Reading/setting
the power plan, closing the owner's own processes, and quitting
OneDrive work unelevated. **Stopping WSearch needs an
administrator** — under the bridge's usual contexts the step
records `skipped` with "needs elevation" and the toggle still
succeeds overall. The response and the state file always show
which steps actually applied; there is no silent partial
success. See docs/JOB_RUNNER.md for the per-step table.

Presence integration: while engaged, the agent's
ProjectModeMonitor polls presence; a game launch, or fresh
owner input (idle time dropping between polls, after a short
settle window so the input that engaged the mode cannot
immediately disengage it), auto-disengages. The owner's use
always wins — the same ethic as the durable runner's GPU yield.
The runner may auto-engage before a `gpu: true` job only behind
config `job_project_mode_auto`, which defaults OFF.

Windows operations sit behind the Ops seam; off Windows every
machine step reports not-applicable rather than pretending.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_agent  # noqa: E402
import presence  # noqa: E402

IS_WINDOWS = os.name == "nt"
STATE_NAME = "project-mode.json"
EVENTS_NAME = "project-mode-events.jsonl"
HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
SEARCH_SERVICE = "WSearch"
ONEDRIVE_EXE = "onedrive.exe"
# Conservative defaults: launcher background helpers only. The
# owner curates via config `project_mode_close_list`.
DEFAULT_CLOSE_LIST = ("steamwebhelper.exe", "epicwebhelper.exe")
_CLOSE_GRACE_S = 5.0
_SETTLE_S = 15.0

_events_lock = threading.Lock()
_GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------

def parse_active_scheme(text: str) -> str | None:
    """The GUID in `powercfg /getactivescheme` output, or None."""
    match = _GUID_RE.search(text or "")
    return match.group(0).lower() if match else None


def parse_service_state(text: str) -> str | None:
    """'running' / 'stopped' from `sc query` output, or None."""
    for line in (text or "").splitlines():
        if "STATE" in line:
            upper = line.upper()
            if "RUNNING" in upper:
                return "running"
            if "STOPPED" in upper:
                return "stopped"
    return None


def close_candidates(processes, close_list) -> list[dict]:
    """Processes to close: exactly those whose executable name is
    on the close list. Pure — the unlisted are never returned."""
    wanted = {str(n).lower() for n in (close_list or ())}
    return [p for p in (processes or ())
            if str(p.get("name") or "").lower() in wanted]


def auto_disengage_reason(snapshot, prev_idle_s,
                          engaged_for_s) -> str | None:
    """Why Project Mode should auto-disengage, or None.

    Pure decision logic: a game launch always wins; fresh owner
    input (idle seconds DROPPING between polls — idle only grows
    while nobody touches the machine) wins after a settle window
    so the input that engaged the mode cannot undo it at once.
    """
    if engaged_for_s is None or engaged_for_s < _SETTLE_S:
        return None
    if snapshot.get("gaming"):
        games = snapshot.get("games") or []
        return f"game launched: {', '.join(games)}" if games \
            else "game launched"
    idle = snapshot.get("input_idle_s")
    if idle is not None and prev_idle_s is not None \
            and idle < prev_idle_s - 1.0:
        return "fresh user input"
    return None


# ---------------------------------------------------------------------------
# State + events
# ---------------------------------------------------------------------------

def _state_path(state_dir: Path) -> Path:
    return Path(state_dir) / STATE_NAME


def read_state(state_dir: Path) -> dict:
    try:
        obj = json.loads(_state_path(state_dir).read_text(
            encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"engaged": False}
    if not isinstance(obj, dict):
        return {"engaged": False}
    obj.setdefault("engaged", False)
    return obj


def is_engaged(state_dir: Path) -> bool:
    return bool(read_state(state_dir).get("engaged"))


def status(state_dir: Path) -> dict:
    return read_state(state_dir)


def _write_state(state_dir: Path, obj: dict) -> None:
    path = _state_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _event(state_dir: Path, event: str, audit=None, **fields) -> None:
    entry = {"ts": bridge_agent.utc_now_iso(), "event": event}
    entry.update(fields)
    try:
        with _events_lock:
            state_dir = Path(state_dir)
            state_dir.mkdir(parents=True, exist_ok=True)
            with open(state_dir / EVENTS_NAME, "a",
                      encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass
    if audit is not None:
        try:
            audit(event, f"project mode: {event}", **fields)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Platform seam
# ---------------------------------------------------------------------------

class Ops:
    """Platform operations. Every method is best-effort and
    reports honestly; machine-changing methods return
    (ok, detail). Tests substitute a fake."""

    def list_processes(self) -> list[dict]:
        raise NotImplementedError

    def close_process_graceful(self, pid: int,
                               grace_s: float) -> tuple[bool, str]:
        raise NotImplementedError

    def launch(self, exe: str) -> tuple[bool, str]:
        raise NotImplementedError

    def active_power_plan(self) -> str | None:
        raise NotImplementedError

    def set_power_plan(self, guid: str) -> tuple[bool, str]:
        raise NotImplementedError

    def service_state(self, name: str) -> str | None:
        raise NotImplementedError

    def stop_service(self, name: str) -> tuple[bool, str]:
        raise NotImplementedError

    def start_service(self, name: str) -> tuple[bool, str]:
        raise NotImplementedError


def _exe_for_pid(pid: int) -> str | None:
    """Full image path for a pid (Windows ctypes; POSIX /proc)."""
    if IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.OpenProcess.argtypes = [
                wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
            kernel32.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                ctypes.POINTER(wintypes.DWORD)]
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return None
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(
                        handle, 0, buf, ctypes.byref(size)):
                    return buf.value or None
                return None
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return None
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return None


class WindowsOps(Ops):
    """Real Windows operations. NOT exercised by the VM suite —
    verified only on the owner's PC (see docs/JOB_RUNNER.md)."""

    def list_processes(self) -> list[dict]:
        import csv
        import io
        try:
            out = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=20,
                **bridge_agent.hidden_spawn_kwargs())
        except (OSError, subprocess.SubprocessError):
            return []
        procs = []
        for row in csv.reader(io.StringIO(out.stdout or "")):
            if len(row) < 2:
                continue
            try:
                pid = int(row[1])
            except ValueError:
                continue
            procs.append({"name": row[0], "pid": pid,
                          "exe": _exe_for_pid(pid)})
        return procs

    def close_process_graceful(self, pid: int,
                               grace_s: float) -> tuple[bool, str]:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        WM_CLOSE = 0x0010
        windows = []
        try:
            import window_raise
            windows = [w for w in window_raise._enumerate_windows()
                       if w.get("pid") == pid]
        except Exception:
            windows = []
        user32.PostMessageW.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPARAM]
        posted = 0
        for win in windows:
            if user32.PostMessageW(win["hwnd"], WM_CLOSE, 0, 0):
                posted += 1
        method = f"WM_CLOSE to {posted} window(s)"
        if not windows:
            # No top-level window (tray/background helper): the
            # polite form of taskkill (no /F) is a close request,
            # not a force kill. If that does not take, we stop.
            try:
                res = subprocess.run(
                    ["taskkill", "/PID", str(pid)],
                    capture_output=True, text=True, timeout=15,
                    **bridge_agent.hidden_spawn_kwargs())
                method = "taskkill close request (no window)"
                if res.returncode != 0:
                    return False, (res.stderr or res.stdout or
                                   "close request refused")[:200]
            except (OSError, subprocess.SubprocessError) as exc:
                return False, f"close request failed: {exc}"
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            if not bridge_agent.pid_alive(pid):
                return True, method
            time.sleep(0.25)
        if not bridge_agent.pid_alive(pid):
            return True, method
        return False, f"still running after {grace_s:g}s grace " \
                      f"({method}); left running, never force-killed"

    def launch(self, exe: str) -> tuple[bool, str]:
        try:
            flags = (subprocess.CREATE_NEW_PROCESS_GROUP
                     | subprocess.DETACHED_PROCESS)
            try:
                subprocess.Popen(
                    [exe], cwd=str(Path(exe).parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=flags
                    | subprocess.CREATE_BREAKAWAY_FROM_JOB)
            except OSError:
                subprocess.Popen(
                    [exe], cwd=str(Path(exe).parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL, creationflags=flags)
            return True, "launched"
        except OSError as exc:
            return False, str(exc)[:200]

    def active_power_plan(self) -> str | None:
        try:
            out = subprocess.run(
                ["powercfg", "/getactivescheme"],
                capture_output=True, text=True, timeout=15,
                **bridge_agent.hidden_spawn_kwargs())
        except (OSError, subprocess.SubprocessError):
            return None
        return parse_active_scheme(out.stdout or "")

    def set_power_plan(self, guid: str) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["powercfg", "/setactive", guid],
                capture_output=True, text=True, timeout=15,
                **bridge_agent.hidden_spawn_kwargs())
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)[:200]
        if res.returncode == 0:
            return True, "scheme set"
        return False, (res.stderr or res.stdout
                       or f"powercfg exit {res.returncode}")[:200]

    def service_state(self, name: str) -> str | None:
        try:
            out = subprocess.run(
                ["sc.exe", "query", name],
                capture_output=True, text=True, timeout=15,
                **bridge_agent.hidden_spawn_kwargs())
        except (OSError, subprocess.SubprocessError):
            return None
        return parse_service_state(out.stdout or "")

    def _service_control(self, name: str,
                         verb: str) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["sc.exe", verb, name],
                capture_output=True, text=True, timeout=30,
                **bridge_agent.hidden_spawn_kwargs())
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)[:200]
        if res.returncode == 0:
            return True, f"service {verb} ok"
        detail = (res.stdout or "") + (res.stderr or "")
        if " 5 " in detail or "Access is denied" in detail:
            return False, "needs elevation (access denied)"
        return False, (detail.strip() or
                       f"sc {verb} exit {res.returncode}")[:200]

    def stop_service(self, name: str) -> tuple[bool, str]:
        return self._service_control(name, "stop")

    def start_service(self, name: str) -> tuple[bool, str]:
        return self._service_control(name, "start")


class PosixOps(Ops):
    """Off-Windows: process close works (SIGTERM is the graceful
    request); the Windows machine steps honestly report
    not-applicable via the step engine's None/False returns."""

    def list_processes(self) -> list[dict]:
        try:
            out = subprocess.run(
                ["ps", "-eo", "pid=,comm="],
                capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return []
        procs = []
        for line in (out.stdout or "").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            procs.append({"name": parts[1], "pid": pid,
                          "exe": _exe_for_pid(pid)})
        return procs

    def close_process_graceful(self, pid: int,
                               grace_s: float) -> tuple[bool, str]:
        import signal as _signal
        try:
            os.kill(pid, _signal.SIGTERM)
        except OSError as exc:
            return False, str(exc)[:200]
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            if not bridge_agent.pid_alive(pid):
                return True, "SIGTERM"
            time.sleep(0.1)
        return (not bridge_agent.pid_alive(pid)), "SIGTERM"

    def launch(self, exe: str) -> tuple[bool, str]:
        try:
            subprocess.Popen([exe], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL,
                             start_new_session=True)
            return True, "launched"
        except OSError as exc:
            return False, str(exc)[:200]

    def active_power_plan(self) -> str | None:
        return None

    def set_power_plan(self, guid: str) -> tuple[bool, str]:
        return False, "power plans are Windows-only"

    def service_state(self, name: str) -> str | None:
        return None

    def stop_service(self, name: str) -> tuple[bool, str]:
        return False, "Windows services only"

    def start_service(self, name: str) -> tuple[bool, str]:
        return False, "Windows services only"


def default_ops() -> Ops:
    return WindowsOps() if IS_WINDOWS else PosixOps()


# ---------------------------------------------------------------------------
# Engage / disengage
# ---------------------------------------------------------------------------

def _step(name: str, status: str, detail: str = "",
          **data) -> dict:
    step = {"step": name, "status": status, "detail": detail}
    step.update(data)
    return step


def _close_group(ops: Ops, procs: list[dict]) -> tuple[list, list]:
    """Gracefully close each process; returns (closed, failed)
    record lists. Graceful only — a survivor is reported, never
    force-killed."""
    closed, failed = [], []
    for proc in procs:
        ok, detail = ops.close_process_graceful(
            int(proc["pid"]), _CLOSE_GRACE_S)
        entry = {"name": proc.get("name"), "pid": proc.get("pid"),
                 "exe": proc.get("exe"), "detail": detail}
        (closed if ok else failed).append(entry)
    return closed, failed


def engage(state_dir: Path, *, source: str = "api", ops: Ops | None = None,
           audit=None, cfg: dict | None = None) -> dict:
    state_dir = Path(state_dir)
    ops = ops or default_ops()
    cfg = cfg or {}
    current = read_state(state_dir)
    if current.get("engaged"):
        return {**current, "note": "already engaged"}
    record: dict = {
        "engaged": True,
        "engaged_at": time.time(),
        "source": source,
        "engage_steps": [],
        "closed_processes": [],
        "previous_power_plan": None,
        "lively": {"was_running": False, "closed": []},
        "onedrive": {"was_running": False, "closed": False,
                     "exe": None},
        "wsearch": {"was_running": False, "stopped_by_us": False},
        "disengage_steps": [],
    }
    steps = record["engage_steps"]

    # 1 — power plan.
    prev = ops.active_power_plan()
    if prev is None:
        steps.append(_step("power_plan", "skipped",
                           "active scheme unreadable on this platform"))
    elif prev.lower() == HIGH_PERFORMANCE_GUID:
        record["previous_power_plan"] = prev
        steps.append(_step("power_plan", "applied",
                           "already on High Performance",
                           previous=prev))
    else:
        ok, detail = ops.set_power_plan(HIGH_PERFORMANCE_GUID)
        if ok:
            record["previous_power_plan"] = prev
        steps.append(_step("power_plan",
                           "applied" if ok else "failed",
                           detail, previous=prev))

    processes = ops.list_processes()

    # 2 — Lively wallpaper rendering.
    lively = [p for p in processes
              if str(p.get("name") or "").lower().startswith("lively")]
    if not lively:
        steps.append(_step("lively", "not_applicable",
                           "Lively is not running"))
    else:
        record["lively"]["was_running"] = True
        closed, failed = _close_group(ops, lively)
        record["lively"]["closed"] = closed
        record["closed_processes"] += closed
        status = "applied" if not failed else (
            "partial" if closed else "failed")
        steps.append(_step(
            "lively", status,
            f"closed {len(closed)}, left running {len(failed)}",
            closed=closed, failed=failed))

    # 3 — close list (owner-curated; conservative defaults).
    close_list = cfg.get("project_mode_close_list") \
        or list(DEFAULT_CLOSE_LIST)
    candidates = close_candidates(processes, close_list)
    if not candidates:
        steps.append(_step("close_list", "not_applicable",
                           "nothing on the close list is running",
                           close_list=list(close_list)))
    else:
        closed, failed = _close_group(ops, candidates)
        record["closed_processes"] += closed
        status = "applied" if not failed else (
            "partial" if closed else "failed")
        steps.append(_step(
            "close_list", status,
            f"closed {len(closed)}, left running {len(failed)}",
            close_list=list(close_list), closed=closed,
            failed=failed))

    # 4 — OneDrive sync (quit the client; relaunch resumes).
    onedrive = next(
        (p for p in processes
         if str(p.get("name") or "").lower() == ONEDRIVE_EXE), None)
    if onedrive is None:
        steps.append(_step("onedrive", "not_applicable",
                           "OneDrive is not running"))
    else:
        record["onedrive"] = {"was_running": True, "closed": False,
                              "exe": onedrive.get("exe")}
        ok, detail = ops.close_process_graceful(
            int(onedrive["pid"]), _CLOSE_GRACE_S)
        record["onedrive"]["closed"] = ok
        steps.append(_step("onedrive",
                           "applied" if ok else "failed",
                           (detail + "; sync pauses while the client "
                            "is closed") if ok else detail))

    # 5 — Windows Search indexing (stop WSearch; needs elevation).
    svc = ops.service_state(SEARCH_SERVICE)
    if svc is None:
        steps.append(_step("search_indexing", "skipped",
                           "service state unreadable on this platform"))
    elif svc == "stopped":
        steps.append(_step("search_indexing", "not_applicable",
                           "WSearch already stopped"))
    else:
        record["wsearch"]["was_running"] = True
        ok, detail = ops.stop_service(SEARCH_SERVICE)
        record["wsearch"]["stopped_by_us"] = ok
        steps.append(_step("search_indexing",
                           "applied" if ok else "skipped",
                           detail))

    _write_state(state_dir, record)
    for step in steps:
        _event(state_dir, "project_mode_step", audit=audit,
               phase="engage", step=step["step"],
               status=step["status"], detail=step["detail"])
    _event(state_dir, "project_mode_engaged", audit=audit,
           source=source,
           applied=[s["step"] for s in steps
                    if s["status"] == "applied"])
    return record


def disengage(state_dir: Path, *, source: str = "api",
              ops: Ops | None = None, audit=None) -> dict:
    state_dir = Path(state_dir)
    ops = ops or default_ops()
    record = read_state(state_dir)
    if not record.get("engaged"):
        return {"engaged": False, "note": "not engaged",
                "disengage_steps": []}
    steps: list[dict] = []

    # Restore in reverse engage order, from the record ONLY.
    if (record.get("wsearch") or {}).get("stopped_by_us"):
        ok, detail = ops.start_service(SEARCH_SERVICE)
        steps.append(_step("search_indexing",
                           "applied" if ok else "failed", detail))
    onedrive = record.get("onedrive") or {}
    if onedrive.get("closed") and onedrive.get("exe"):
        ok, detail = ops.launch(str(onedrive["exe"]))
        steps.append(_step("onedrive",
                           "applied" if ok else "failed", detail))
    elif onedrive.get("closed"):
        steps.append(_step("onedrive", "skipped",
                           "closed by engage but no exe path recorded"))
    relaunched = set()
    for entry in record.get("closed_processes") or []:
        exe = entry.get("exe")
        if not exe:
            steps.append(_step("relaunch", "skipped",
                               f"{entry.get('name')}: no exe path "
                               f"recorded"))
            continue
        if exe in relaunched:
            continue
        relaunched.add(exe)
        ok, detail = ops.launch(str(exe))
        steps.append(_step("relaunch",
                           "applied" if ok else "failed",
                           f"{entry.get('name')}: {detail}"))
    prev_plan = record.get("previous_power_plan")
    if prev_plan:
        current = ops.active_power_plan()
        if current is not None and current.lower() == str(
                prev_plan).lower():
            steps.append(_step("power_plan", "applied",
                               "already back on the recorded scheme"))
        else:
            ok, detail = ops.set_power_plan(str(prev_plan))
            steps.append(_step("power_plan",
                               "applied" if ok else "failed", detail))
    record["engaged"] = False
    record["disengaged_at"] = time.time()
    record["disengage_source"] = source
    record["disengage_steps"] = steps
    _write_state(state_dir, record)
    for step in steps:
        _event(state_dir, "project_mode_step", audit=audit,
               phase="disengage", step=step["step"],
               status=step["status"], detail=step["detail"])
    _event(state_dir, "project_mode_disengaged", audit=audit,
           source=source,
           restored=[s["step"] for s in steps
                     if s["status"] == "applied"])
    return record


# ---------------------------------------------------------------------------
# Presence monitor (auto-disengage; owner's use always wins)
# ---------------------------------------------------------------------------

class ProjectModeMonitor:
    """Polls presence while Project Mode is engaged and
    disengages on a game launch or fresh owner input."""

    def __init__(self, core, *, poll_s: float | None = None,
                 snapshot_fn=None):
        self.core = core
        self.state_dir = Path(core.state_dir)
        if poll_s is None:
            try:
                poll_s = float(
                    core.cfg.get("project_mode_watch_s") or 15)
            except (TypeError, ValueError):
                poll_s = 15.0
        self._poll = max(1.0, float(poll_s))
        self._snapshot_fn = snapshot_fn or presence.snapshot
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._prev_idle: float | None = None
        self._engaged_since: float | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="project-mode-watch")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _audit(self, event: str, summary: str, **fields) -> None:
        entry = {"event": event, "ip": None, "method": None,
                 "path": None, "summary": summary, "status": None,
                 "duration_ms": None}
        entry.update(fields)
        self.core.audit(entry)

    def check_once(self) -> str | None:
        """One poll. Returns the disengage reason when it fired."""
        if not is_engaged(self.state_dir):
            self._prev_idle = None
            self._engaged_since = None
            return None
        now = time.monotonic()
        if self._engaged_since is None:
            self._engaged_since = now
        snap = self._snapshot_fn()
        reason = auto_disengage_reason(
            snap, self._prev_idle, now - self._engaged_since)
        idle = snap.get("input_idle_s")
        if idle is not None:
            self._prev_idle = idle
        if reason is None:
            return None
        disengage(self.state_dir, source=f"auto: {reason}",
                  audit=self._audit)
        self._prev_idle = None
        self._engaged_since = None
        return reason

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.check_once()
            except Exception as exc:  # the watch must not die quietly
                print(f"[bridge] project mode watch error: {exc}",
                      file=sys.stderr)
            self._stop.wait(self._poll)
