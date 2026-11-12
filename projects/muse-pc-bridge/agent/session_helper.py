#!/usr/bin/env python3
"""muse-pc-bridge interactive session helper (v1.1 topology fix).

Desktop-class bridge operations — screen capture, input injection,
UI automation, the clipboard, launching a GUI window — act on the
INTERACTIVE user's desktop. The boot-topology agent runs as SYSTEM
in session 0, whose desktop is not the owner's, so it cannot serve
those routes itself. This helper is the other half of that design:

- The avatar process (supervisor_gui.py, running in the owner's
  logon session) starts this helper when it ATTACHES to a core.
- The helper is a small HTTP server bound to 127.0.0.1 on an
  ephemeral port, authenticated with the SAME bridge token, serving
  ONLY the desktop routes (a whitelist — exec, files, jobs and
  everything else answer 404 here).
- It registers itself in <state_dir>/session-helper.json with a
  heartbeat; the main agent proxies desktop routes to a fresh
  registration and answers an honest 501 when none exists.
- It holds an exclusive ownership lock
  (<state_dir>/session-helper-owner.lock) for its whole lifetime:
  exactly one helper may own a state directory, so a second avatar
  window can never start a rival helper against the same
  registration file (its start is refused with
  HelperOwnershipError and the GUI reuses the live helper).
- It shares the main audit log (its entries are marked
  "via": "session-helper"; the proxying agent marks its own
  "via": "session-broker"), and keeps its own process registry in
  <state_dir>/session-helper/ so GUI processes it spawns never
  collide with the main agent's registry files.
- It stops when the avatar stops: closing the avatar stops desktop
  brokering (the core keeps running; desktop routes go back to 501
  until an avatar/helper runs again).

It can also be run standalone for diagnosis:
  python session_helper.py [--config C:\\path\\config.json]

Stdlib only, like the rest of the project.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_agent  # noqa: E402
import bridge_update  # noqa: E402

HEARTBEAT_S = 5.0

# Single-helper ownership of a state directory. Two helpers against
# one state dir overwrite the same session-helper.json registration
# while keeping divergent process registries, so brokered processes
# vanish depending on whose heartbeat landed last (Codex PR #47
# finding). The owner holds an OS exclusive lock on this sidecar
# file for its whole lifetime; the lock dies with the process, so
# a crashed owner never needs a janitor.
HELPER_OWNER_LOCK_NAME = "session-helper-owner.lock"


class HelperOwnershipError(RuntimeError):
    """Another live session helper already owns this state dir."""

# The ONLY routes this server serves. Anything else is a 404: the
# helper exists to put desktop operations in the interactive
# session, not to become a second full agent on loopback.
_PROC_ROUTE = re.compile(r"/v1/processes(?:/([0-9a-f]+)(?:/(kill))?)?")


def is_desktop_route(method: str, route: str) -> bool:
    if method == "GET" and route == "/v1/screenshot":
        return True
    if method == "POST" and route in ("/v1/input", "/v1/uia"):
        return True
    if route == "/v1/clipboard" and method in ("GET", "POST"):
        return True
    match = _PROC_ROUTE.fullmatch(route)
    if match:
        if method == "POST" and (match.group(1) is None
                                 or match.group(2) == "kill"):
            return True
        if method == "GET":
            return True
    return False


class HelperHandler(bridge_agent.BridgeHandler):
    """BridgeHandler restricted to the desktop route whitelist."""

    def _route(self, method: str, route: str, parsed):
        if not is_desktop_route(method, route):
            return 404, {"error": "not a desktop route"}, \
                "helper: not a desktop route", {}
        return super()._route(method, route, parsed)


def build_helper_config(config_path: Path) -> dict:
    """The main agent's config, adapted for the helper: loopback
    ephemeral port, helper flag set, and a private state subdir for
    its own registries. Token, file roots and the audit log are the
    main agent's (shared on purpose — one audit trail)."""
    cfg = bridge_agent.load_config(config_path)
    cfg["host"] = "127.0.0.1"
    cfg["port"] = 0
    cfg["session_helper"] = True
    helper_state = Path(cfg["state_dir"]) / "session-helper"
    helper_state.mkdir(parents=True, exist_ok=True)
    cfg["state_dir"] = str(helper_state)
    return cfg


class SessionHelper:
    """Owns the helper HTTP server + its registration heartbeat."""

    def __init__(self, config_path: Path, state_dir: Path,
                 cfg: dict | None = None):
        self.config_path = Path(config_path)
        # The registry lives in the MAIN state dir (what the agent
        # reads), not the helper's private subdir.
        self.state_dir = Path(state_dir)
        self.cfg = cfg if cfg is not None \
            else build_helper_config(self.config_path)
        self.server = None
        self.port: int | None = None
        # Captured once at start: a process's session never changes,
        # and the heartbeat must not re-probe it.
        self.session_id = bridge_agent.current_session_id()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        # The state-dir ownership lock handle, held from start()
        # until stop() (or process exit). None until acquired.
        self._owner_fh = None

    # -- registration ------------------------------------------------------
    def _registry_obj(self) -> dict:
        return {
            "port": self.port,
            "pid": _os_getpid(),
            "session_id": self.session_id,
            "started_at": self._started_at,
            "updated_at": time.time(),
        }

    def _write_registry(self) -> None:
        try:
            bridge_update._write_json(
                self.state_dir / bridge_agent.HELPER_REGISTRY_NAME,
                self._registry_obj())
        except OSError:
            pass

    def _remove_registry(self) -> None:
        path = self.state_dir / bridge_agent.HELPER_REGISTRY_NAME
        try:
            reg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(reg, dict) and reg.get("pid") == _os_getpid():
            try:
                path.unlink()
            except OSError:
                pass

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_S):
            self._write_registry()

    # -- ownership ---------------------------------------------------------
    def _acquire_ownership(self) -> None:
        """Claim exclusive helper ownership of the state dir.

        Raises HelperOwnershipError when a live helper already
        holds it. The lock is the held-open file handle itself:
        closing it (stop(), or the process dying) releases the
        claim, so a stale REGISTRATION file alone never blocks a
        fresh helper — read_session_helper's freshness/pid checks
        decide whether a registration is trusted, this lock decides
        who may write it.
        """
        lock_path = self.state_dir / HELPER_OWNER_LOCK_NAME
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            fh = open(lock_path, "a+b")
        except OSError as exc:
            raise HelperOwnershipError(
                f"cannot claim helper ownership of {self.state_dir} "
                f"({exc})") from exc
        if not bridge_agent._try_lock_file_exclusive(fh):
            try:
                fh.close()
            except OSError:
                pass
            raise HelperOwnershipError(
                f"another session helper already owns "
                f"{self.state_dir}")
        self._owner_fh = fh

    def _release_ownership(self) -> None:
        fh, self._owner_fh = self._owner_fh, None
        if fh is not None:
            bridge_agent._unlock_file(fh)
            try:
                fh.close()
            except OSError:
                pass

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> "SessionHelper":
        self._started_at = time.time()
        # Ownership FIRST: a refused helper must not load the shared
        # registries or write a registration over the owner's.
        self._acquire_ownership()
        try:
            self.server = bridge_agent.create_server(self.cfg)
        except Exception:
            self._release_ownership()
            raise
        self.server.RequestHandlerClass = HelperHandler
        self.server.is_helper = True  # audit entries: via=session-helper
        self.port = int(self.server.server_address[1])
        self._write_registry()
        serve = threading.Thread(target=self.server.serve_forever,
                                 daemon=True, name="session-helper")
        serve.start()
        beat = threading.Thread(target=self._heartbeat, daemon=True,
                                name="session-helper-heartbeat")
        beat.start()
        self._threads = [serve, beat]
        return self

    def stop(self) -> None:
        self._stop.set()
        self._remove_registry()
        if self.server is not None:
            try:
                self.server.core.log_stop()
            except Exception:
                pass
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self._release_ownership()


def _os_getpid() -> int:
    import os
    return os.getpid()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="muse-pc-bridge interactive session helper")
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).resolve().parent
                        / "config.json")
    args = parser.parse_args(argv)
    if not args.config.exists():
        print(f"[session-helper] No agent config at {args.config}.",
              file=sys.stderr)
        return 1
    cfg = bridge_agent.load_config(args.config)
    state_value = str(cfg.get("state_dir", "./state"))
    state_dir = Path(state_value)
    if not state_dir.is_absolute():
        state_dir = (args.config.resolve().parent / state_dir).resolve()
    try:
        helper = SessionHelper(args.config, state_dir).start()
    except HelperOwnershipError as exc:
        print(f"[session-helper] {exc}; not starting a second one.",
              file=sys.stderr)
        return 1
    print(f"[session-helper] Desktop helper on 127.0.0.1:{helper.port} "
          f"(session {bridge_agent.current_session_id()}); "
          f"registered in {state_dir}. Ctrl+C stops it.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        helper.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
