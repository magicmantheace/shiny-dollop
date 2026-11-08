#!/usr/bin/env python3
"""muse-pc-bridge supervisor — service form of the agent (v1 §4).

Runs `bridge_agent.py` as a child process and:

- restarts it automatically if it crashes (exponential backoff),
- applies a staged self-update at the restart boundary, health-checks
  the new agent, and **rolls back automatically** if the health check
  fails,
- writes its state to `<state_dir>/supervisor-status.json` so start /
  stop / status tooling (and humans) can see what is running,
- publishes `<state_dir>/display-state.json` (the resolved avatar
  display state) from the same signals — since v1.1 this is the
  supervisor's job in every form, so the file stays fresh even when
  no avatar window is open (local apps such as a desktop pet read
  it; it carries no token material).

Forms (v1.1 topology — see docs/INSTALL_WINDOWS.md):

- **Console** (`python supervisor.py`): the original form. The
  console is the visible indicator; closing it (or Ctrl+C) stops the
  supervisor AND the agent — the kill switch.
- **Headless core** (`pythonw supervisor.py --headless`): the boot
  form, started by the "Muse PC Bridge (core)" boot task as SYSTEM
  before any logon (scripts/bridge-core.ps1). No console exists, so
  prints go to `<state_dir>/supervisor-core.log`. The kill switches
  for this form are the task controls and scripts/bridge-core.ps1
  -Action stop. It never opens a window or touches GUI state.
- **GUI/avatar**: supervisor_gui.py embeds this same Supervisor in
  its own process — or, when a core is already running, attaches to
  it display-only (see that module).

Usage:
  python supervisor.py [--headless]
                       [--config C:\\path\\config.json]
                       [--install-root C:\\path\\projects\\muse-pc-bridge]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_update  # noqa: E402
import display_state  # noqa: E402


def _agent_dir() -> Path:
    return Path(__file__).resolve().parent


class Supervisor:
    def __init__(self, install_root: Path, config_path: Path,
                 state_dir: Path,
                 restart_base_delay: float = 2.0,
                 restart_max_delay: float = 30.0,
                 health_timeout_s: float = 20.0,
                 health_interval_s: float = 0.5,
                 python_exe: str | None = None):
        self.install_root = Path(install_root)
        self.config_path = Path(config_path)
        self.state_dir = Path(state_dir)
        self.restart_base_delay = restart_base_delay
        self.restart_max_delay = restart_max_delay
        self.health_timeout_s = health_timeout_s
        self.health_interval_s = health_interval_s
        self.python_exe = python_exe or sys.executable
        self._stop = False
        self._child: subprocess.Popen | None = None
        self.restarts = 0
        self._fast_crashes = 0
        self._last_status: dict | None = None
        # display-state publishing (see _publish_display_state)
        self._display_state: str | None = None
        self._display_since: float = 0.0
        self._agent_down_since: float | None = None

    # -- state file ----------------------------------------------------------
    def _write_status(self, state: str, **extra) -> None:
        obj = {
            "state": state,
            "agent_pid": self._child.pid if self._child else None,
            "restarts": self.restarts,
            "updated_at": time.time(),
        }
        obj.update(extra)
        self._last_status = obj
        try:
            bridge_update._write_json(
                self.state_dir / "supervisor-status.json", obj)
        except OSError:
            pass
        print(f"[supervisor] {state} "
              + (f"({extra})" if extra else ""), flush=True)

    # -- agent process ---------------------------------------------------------
    def _agent_cmd(self) -> list[str]:
        return [self.python_exe,
                str(self.install_root / "agent" / "bridge_agent.py"),
                "--config", str(self.config_path)]

    def _start_child(self) -> subprocess.Popen:
        kwargs: dict = {}
        if os.name == "nt":
            # Own process group so _stop_child can deliver
            # CTRL_BREAK_EVENT to the agent alone (a graceful stop),
            # not to every process sharing this console.
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        self._child = subprocess.Popen(self._agent_cmd(), **kwargs)
        return self._child

    def _stop_child(self, timeout: float = 10.0) -> None:
        child = self._child
        if child is None or child.poll() is not None:
            return
        try:
            if os.name == "nt" and hasattr(signal, "CTRL_BREAK_EVENT"):
                # Graceful first: the agent maps SIGBREAK to its
                # audited shutdown path (server_stop in the audit
                # log). TerminateProcess would bypass it entirely.
                child.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # SIGTERM on POSIX — the agent handles it the same
                # graceful way.
                child.terminate()
            child.wait(timeout=timeout)
        except (OSError, subprocess.SubprocessError, ValueError):
            try:
                child.kill()
            except OSError:
                pass

    # -- health check ------------------------------------------------------------
    def _health_check(self) -> bool:
        """Poll the agent's /v1/status with its own token until 200."""
        try:
            cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        host = str(cfg.get("host", "127.0.0.1"))
        port = int(cfg.get("port", 8765))
        token = str(cfg.get("token", ""))
        url = f"http://{host}:{port}/v1/status"
        deadline = time.time() + self.health_timeout_s
        while time.time() < deadline and not self._stop:
            if self._child is not None and self._child.poll() is not None:
                return False        # agent died during startup
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {token}"})
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(self.health_interval_s)
        return False

    # -- display-state publishing -------------------------------------------
    def _fetch_agent_status(self) -> dict | None:
        """The agent's /v1/status body, or None when unreachable."""
        try:
            cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            host = str(cfg.get("host", "127.0.0.1"))
            port = int(cfg.get("port", 8765))
            token = str(cfg.get("token", ""))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        req = urllib.request.Request(
            f"http://{host}:{port}/v1/status",
            headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return None
        return None

    def _publish_display_state(self) -> None:
        """Resolve the display state and write display-state.json on
        change. Same inputs and mapping the avatar window uses; the
        supervisor owns the file so it stays fresh with no window
        open (headless core) exactly as with one (either GUI form).
        """
        agent = self._fetch_agent_status()
        if agent is None:
            if self._agent_down_since is None:
                self._agent_down_since = time.time()
        else:
            self._agent_down_since = None
        sup = self._last_status or {"state": "starting"}
        update = bridge_update.update_status(self.state_dir)
        view = display_state.resolve_display(
            sup, agent, update, down_since=self._agent_down_since)
        if view["state"] != self._display_state:
            self._display_state = view["state"]
            self._display_since = time.time()
            try:
                bridge_update._write_json(
                    self.state_dir / "display-state.json",
                    {"state": view["state"], "art": view["art"],
                     "label": view["label"],
                     "since": self._display_since,
                     "updated_at": time.time()})
            except OSError:
                pass

    def _display_loop(self) -> None:
        while not self._stop:
            try:
                self._publish_display_state()
            except Exception:  # publishing must never kill the core
                pass
            self._sleep(1.0)

    # -- main loop ------------------------------------------------------------
    def stop(self) -> None:
        self._stop = True
        self._stop_child()

    def run(self) -> int:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._write_status("starting")
        threading.Thread(target=self._display_loop, daemon=True,
                         name="display-state").start()
        while not self._stop:
            applied = None
            pending = bridge_update._read_json(
                self.state_dir / "update-pending.json")
            if pending is not None:
                try:
                    applied = bridge_update.apply_staged(
                        self.state_dir, self.install_root)
                    self._write_status(
                        "update_applied", version=applied["version"])
                except (ValueError, OSError) as exc:
                    bridge_update.record_result(self.state_dir, {
                        "outcome": "apply_failed", "error": str(exc)})
                    self._write_status("update_apply_failed", error=str(exc))
            child = self._start_child()
            self._write_status("running", agent_pid=child.pid)
            if applied is not None:
                if self._health_check():
                    bridge_update.record_result(self.state_dir, {
                        "outcome": "applied_ok",
                        "version": applied["version"]})
                    self._write_status("update_healthy",
                                       version=applied["version"])
                else:
                    self._write_status("update_unhealthy_rolling_back",
                                       version=applied["version"])
                    self._stop_child()
                    try:
                        bridge_update.rollback(
                            self.state_dir, self.install_root,
                            reason="post-update health check failed")
                    except (ValueError, OSError) as exc:
                        bridge_update.record_result(self.state_dir, {
                            "outcome": "rollback_failed", "error": str(exc)})
                    child = self._start_child()
                    self._write_status("running_after_rollback",
                                       agent_pid=child.pid)
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
                        self.restart_base_delay * (2 ** self._fast_crashes))
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


def _headless_stdio(state_dir: Path) -> None:
    """Under pythonw (the boot-task form) there is no console; give
    the supervisor's prints a home — a log beside the state files —
    instead of a None stream that would crash print()."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        log = open(state_dir / "supervisor-core.log", "a",
                   encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log
    except OSError:
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="muse-pc-bridge supervisor")
    parser.add_argument("--config", type=Path,
                        default=_agent_dir() / "config.json",
                        help="agent config.json (default: beside bridge_agent.py)")
    parser.add_argument("--install-root", type=Path,
                        default=_agent_dir().parent,
                        help="project folder (default: parent of agent/)")
    parser.add_argument("--headless", action="store_true",
                        help="boot-task form: no console, output to "
                             "<state_dir>/supervisor-core.log; started "
                             "by the 'Muse PC Bridge (core)' boot task "
                             "(scripts/bridge-core.ps1)")
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"[supervisor] No agent config at {args.config}. "
              f"Run bridge_agent.py --init first.", file=sys.stderr)
        return 1
    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[supervisor] Could not read agent config: {exc}",
              file=sys.stderr)
        return 1
    state_value = str(cfg.get("state_dir", "./state"))
    state_dir = Path(state_value)
    if not state_dir.is_absolute():
        state_dir = (args.config.resolve().parent / state_dir).resolve()

    if args.headless:
        _headless_stdio(state_dir)

    supervisor = Supervisor(args.install_root, args.config, state_dir)

    def _handle_signal(_signum, _frame):
        supervisor.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)
    if args.headless:
        print("[supervisor] muse-pc-bridge core running headless "
              "(boot form). Stop it with scripts/bridge-core.ps1 "
              "-Action stop or by disabling the boot task.")
    else:
        print("[supervisor] muse-pc-bridge supervisor running. "
              "Closing this window (or Ctrl+C) stops the agent — "
              "that is the kill switch.")
    try:
        return supervisor.run()
    except KeyboardInterrupt:
        supervisor.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
