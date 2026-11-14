#!/usr/bin/env python3
"""muse-pc-bridge agent — full-shell HTTP agent for Muse, stdlib only.

Runs on the owner's Windows PC, binds (by configuration) to the PC's
Tailscale IP, and exposes a JSON API:

  GET  /v1/status                     agent info + capabilities (v1: richer)
  POST /v1/exec                       submit an async job (returns job_id;
                                      optional wait_s for inline completion)
  GET  /v1/jobs                       list recent jobs
  GET  /v1/jobs/{id}                  job state + incremental output
  POST /v1/jobs/{id}/cancel           terminate a running job
  POST /v1/wol                        send a Wake-on-LAN magic packet
                                      from this machine
  POST /v1/processes                  spawn a detached process (with
                                      "gui": true + "executable"/"args":
                                      launch a GUI app directly, no shell)
  GET  /v1/processes                  list tracked detached processes
  GET  /v1/processes/{id}             inspect one (+ log tails)
  POST /v1/processes/{id}/kill       terminate a detached process
  POST /v1/sessions                   open an interactive shell session
  GET  /v1/sessions/{id}              session state + incremental output
  POST /v1/sessions/{id}/input        send input to a session
  POST /v1/sessions/{id}/close        close a session
  GET  /v1/screenshot                 native screen capture (Windows)
  POST /v1/input                      host mouse/keyboard injection (Windows)
  POST /v1/uia                        UI Automation helper (Windows)
  GET  /v1/clipboard                  read host clipboard (Windows)
  POST /v1/clipboard                  set host clipboard (Windows)
  GET  /v1/file/list?path=<rel>       list a directory in a file root
  GET  /v1/file/tree?path=<rel>       recursive listing
  GET  /v1/file/get?path=<rel>        whole file or byte range (offset/length)
  GET  /v1/file/hash?path=<rel>       server-side SHA-256 of a file
  POST /v1/file/put                   small-file upload (base64, v0 compat)
  POST /v1/file/upload/start          begin a chunked, resumable upload
  PUT  /v1/file/upload/{id}/{index}   send one raw chunk
  GET  /v1/file/upload/{id}           upload progress
  POST /v1/file/upload/{id}/complete  assemble + verify + place the file
  DELETE /v1/file/upload/{id}         discard an upload
  POST /v1/file/mkdir                 create a directory in a root
  POST /v1/file/move                  move/rename within or across roots
  POST /v1/file/delete                delete a file or (recursive) directory
  GET  /v1/audit/tail?n=<count>       last audit entries (v1 hardening)
  GET  /v1/audit?since=&limit=        audit entries at/after a unix
                                      timestamp, oldest first, paged
                                      via next_since (v1.2; reads ONLY
                                      the agent's own audit file)
  GET  /v1/update/status              staged-update state
  POST /v1/update/stage               stage a release bundle for the supervisor

Every /v1/* request requires `Authorization: Bearer <token>`. Every
request — including auth failures — is appended to a JSONL audit log.
The token is never written to the audit log.

Full shell access is the owner's explicit choice (2026-11-04). The
audit log is non-negotiable: if it cannot be written, the failure is
reported on stderr but the server keeps running (a broken audit write
must not crash the agent).

Usage:
  python bridge_agent.py --init      # write config.json, print token once
  python bridge_agent.py             # run with ./config.json
  python bridge_agent.py --config C:\\path\\config.json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import ntpath
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zlib
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = "1.1.0"
AGENT_NAME = "muse-pc-bridge"
MAX_GET_BYTES = 16 * 1024 * 1024          # whole-file /v1/file/get limit
MAX_RANGE_BYTES = 64 * 1024 * 1024        # per-call range-read limit
MAX_BODY_BYTES = 40 * 1024 * 1024         # JSON request body hard limit
CHUNK_SIZE = 8 * 1024 * 1024              # chunked-upload chunk size
MAX_CHUNK_BYTES = 16 * 1024 * 1024        # one uploaded chunk, hard limit
IS_WINDOWS = os.name == "nt"

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8765,
    "token": "",
    "allowed_file_root": "./bridge-files",
    "file_roots": None,                    # [{"name": ..., "path": ...}, ...]
    "state_dir": "./state",
    "max_output_bytes": 262144,
    "default_timeout_s": 60,
    "max_timeout_s": 900,
    "audit_log": "./logs/audit.jsonl",
    "audit_max_bytes": 10 * 1024 * 1024,   # rotate the audit log past this
    "audit_keep": 5,                       # rotated files to keep (0 = no rotation)
    "job_history_limit": 100,              # finished jobs retained in memory
    "job_output_cap_bytes": 8 * 1024 * 1024,  # per-stream capture cap per job
    "session_idle_timeout_s": 1800,
    "session_broker": True,              # proxy desktop routes to the
                                         # interactive session helper
    "uac_poll_interval_s": 2.0,          # UAC consent prompt polling
    "auth_fail_limit": 5,                  # failures inside the window ...
    "auth_fail_window_s": 60,              # ... trigger a temporary block
    "auth_block_s": 30,
}

_DRIVE_RE = re.compile(r"^[a-zA-Z]:")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def default_shell() -> str:
    return "powershell" if IS_WINDOWS else "posix"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def agent_dir() -> Path:
    return Path(__file__).resolve().parent


def _resolve_beside(base: Path, value: str) -> str:
    p = Path(str(value))
    if not p.is_absolute():
        p = (base / p).resolve()
    return str(p)


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(raw)
    base = config_path.resolve().parent
    # Relative file root / audit / state paths resolve beside the config.
    cfg["allowed_file_root"] = _resolve_beside(base, cfg["allowed_file_root"])
    cfg["audit_log"] = _resolve_beside(base, cfg["audit_log"])
    cfg["state_dir"] = _resolve_beside(base, cfg["state_dir"])
    # File roots: explicit list wins; otherwise the legacy single root.
    roots = []
    if cfg.get("file_roots"):
        for entry in cfg["file_roots"]:
            roots.append({"name": str(entry["name"]),
                          "path": _resolve_beside(base, entry["path"])})
    else:
        roots.append({"name": "default", "path": cfg["allowed_file_root"]})
    if not roots:
        raise ValueError("config defines no file roots")
    cfg["roots"] = roots
    cfg["config_path"] = str(config_path)
    return cfg


def init_config(config_path: Path) -> str:
    """Write a fresh config.json with a generated token; return the token."""
    token = secrets.token_urlsafe(32)
    cfg = dict(DEFAULT_CONFIG)
    cfg["token"] = token
    cfg.pop("roots", None)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    return token


# --------------------------------------------------------------------------
# Process helpers (shared by jobs, processes, sessions)
# --------------------------------------------------------------------------

# -- Shell executable resolution -------------------------------------------
#
# Why this exists (defect found live at the v1.1 boot-core activation,
# 2026-11-08): under the session-0 core running as SYSTEM, every
# PowerShell job failed at spawn with WinError 1920 ("The file cannot
# be accessed by the system") while cmd jobs under the same core
# worked. build_command resolved the PowerShell executable with a
# bare-name shutil.which() over the process PATH, and in the
# boot-task environment that search returns the per-user WindowsApps
# execution alias for powershell.exe -- a reparse stub inside the
# interactive user's profile that no other account (SYSTEM included)
# can execute. cmd survived only because it was passed bare and
# Windows' own CreateProcess search order found System32\cmd.exe.
# Resolution therefore never trusts a PATH hit that lives under
# WindowsApps or any user profile, and prefers the fixed System32
# locations outright.

def _shell_path_is_blocked(path: str, env) -> bool:
    """True if a resolved shell path must never be spawned: a
    WindowsApps execution alias, or anything under a user profile /
    per-user AppData. Such paths are per-user reparse stubs or
    profile content that a service account cannot (or must not)
    execute."""
    norm = str(path).replace("/", "\\").lower()
    if "\\windowsapps\\" in norm or norm.endswith("\\windowsapps"):
        return True
    if re.search(r"\\users\\[^\\]+\\appdata\\", norm):
        return True
    for var in ("USERPROFILE", "LOCALAPPDATA", "APPDATA"):
        base = str(env.get(var) or "").replace("/", "\\").rstrip("\\").lower()
        if base and norm.startswith(base + "\\"):
            return True
    return False


def _resolve_windows_shell_exe(shell: str, env, which, exists) -> str | None:
    """Resolve a Windows shell name to an absolute executable path.

    Pure seam: env/which/exists are injected so the contract is
    testable off-Windows (the SYSTEM context itself cannot be
    reproduced in the suite). Preference order for "powershell": a
    vetted pwsh on PATH (unchanged from the historical behaviour),
    then the fixed System32 WindowsPowerShell path, then a vetted
    PATH hit for powershell; if nothing exists, the System32 path is
    returned anyway -- it is present on every Windows install, and a
    genuinely missing shell must fail against its real path, never
    against an alias stub. "cmd": System32 first, then a vetted PATH
    hit, then System32 regardless. "pwsh": a vetted, existing PATH
    hit or None.
    """
    system_root = str(env.get("SystemRoot") or env.get("windir")
                      or r"C:\Windows")
    system32 = system_root.rstrip("\\") + r"\System32"
    ps_system32 = system32 + r"\WindowsPowerShell\v1.0\powershell.exe"
    cmd_system32 = system32 + r"\cmd.exe"

    def vetted(candidate):
        if not candidate or not ntpath.isabs(candidate):
            return None
        if _shell_path_is_blocked(candidate, env):
            return None
        return candidate

    if shell == "powershell":
        for candidate in (vetted(which("pwsh")), ps_system32,
                          vetted(which("powershell"))):
            if candidate and exists(candidate):
                return candidate
        return ps_system32
    if shell == "pwsh":
        candidate = vetted(which("pwsh"))
        return candidate if candidate and exists(candidate) else None
    if shell == "cmd":
        for candidate in (cmd_system32, vetted(which("cmd"))):
            if candidate and exists(candidate):
                return candidate
        return cmd_system32
    return None


def resolve_shell_exe(shell: str) -> str | None:
    """Absolute executable for a shell name, or None if unavailable.

    On Windows this is the vetted, System32-first resolution above.
    Off Windows (dev machines), "posix" keeps its fixed location and
    powershell/cmd keep the historical PATH behaviour.
    """
    if IS_WINDOWS:
        return _resolve_windows_shell_exe(
            shell, os.environ, shutil.which, os.path.exists)
    if shell == "posix":
        return "/bin/sh"
    if shell in ("powershell", "pwsh"):
        return shutil.which("pwsh") or shutil.which("powershell")
    if shell == "cmd":
        return shutil.which("cmd")
    return None


def build_command(shell: str, command: str) -> list[str]:
    if shell == "powershell":
        exe = resolve_shell_exe("powershell") or "powershell"
        return [exe, "-NoProfile", "-NonInteractive", "-Command", command]
    if shell == "cmd":
        exe = resolve_shell_exe("cmd") or "cmd"
        return [exe, "/d", "/s", "/c", command]
    if shell == "posix":
        return ["/bin/sh", "-c", command]
    raise ValueError(f"unknown shell: {shell!r}")


def shell_argv(shell: str) -> list[str]:
    """Argv for an interactive shell of the given kind."""
    if shell == "powershell":
        exe = resolve_shell_exe("powershell") or "powershell"
        return [exe, "-NoProfile", "-NoExit", "-Command", "-"]
    if shell == "cmd":
        exe = resolve_shell_exe("cmd") or "cmd"
        return [exe]
    if shell == "posix":
        return ["/bin/sh", "-i"]
    raise ValueError(f"unknown shell: {shell!r}")


def _declare_process_signatures(kernel32) -> None:
    """Declare argtypes/restype for the kernel32 process calls in
    pid_alive.

    Same defect class the capture-signature fix removed from the
    screenshot path: OpenProcess returns a HANDLE, which is
    pointer-sized in this 64-bit process. With the default c_int
    restype ctypes truncates that handle, and passing it on to
    GetExitCodeProcess / CloseHandle with undeclared argtypes
    converts the Python int through the platform C long — 32-bit on
    Windows — which raises ``OverflowError: int too long to
    convert`` for handle values above INT_MAX. A jobs/process
    liveness check would then fail intermittently, depending only
    on the handle value the OS happened to hand out. Declaring
    every handle slot as c_void_p removes that failure class.
    """
    import ctypes
    P = ctypes.c_void_p
    I = ctypes.c_int
    UL = ctypes.c_ulong
    kernel32.OpenProcess.argtypes = [UL, I, UL]
    kernel32.OpenProcess.restype = P
    kernel32.GetExitCodeProcess.argtypes = [P, ctypes.POINTER(UL)]
    kernel32.GetExitCodeProcess.restype = I          # BOOL
    kernel32.CloseHandle.argtypes = [P]
    kernel32.CloseHandle.restype = I                 # BOOL


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            _declare_process_signatures(kernel32)
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                code = ctypes.c_ulong(0)
                ok = kernel32.GetExitCodeProcess(handle,
                                                 ctypes.byref(code))
                return bool(ok) and code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# ---------------------------------------------------------------------------
# Interactive-session broker (v1.1 topology fix)
#
# Desktop-class operations — screen capture, input injection, UI
# automation, the clipboard, launching a GUI window — act on the
# INTERACTIVE user's desktop. An agent running as SYSTEM under the
# boot task lives in session 0, whose desktop is not the owner's:
# serving those routes locally there would silently capture/inject
# into the wrong desktop. So in the boot topology the agent PROXIES
# desktop routes to a small helper server that the avatar process
# hosts inside the interactive session (agent/session_helper.py),
# and — when no helper is registered — answers an honest 501 for
# them instead of touching session 0's desktop. The helper registers
# itself in <state_dir>/session-helper.json with a heartbeat; only a
# fresh registration with a live pid is trusted.
# ---------------------------------------------------------------------------

HELPER_REGISTRY_NAME = "session-helper.json"
HELPER_FRESH_S = 20.0        # heartbeat is 5 s; 20 s of silence = gone
# The /v1/status merge of helper-owned processes is bounded by its
# READERS' deadlines, not the listing's: avatar status readers time
# out at 1.5 s and the supervisor's update health check at 3 s, so
# a live-but-hung helper must never stall status past them (Codex
# PR #47 finding). The status path therefore fetches with a
# sub-second timeout, serves a fresh-enough last-known merge
# without touching the network, and backs off briefly after a
# failed fetch — see BridgeHandler._helper_processes_for_status.
HELPER_STATUS_TIMEOUT_S = 0.75   # one status-path fetch attempt
HELPER_MERGE_CACHE_S = 2.0       # a merge this fresh is served as-is
HELPER_MERGE_RETRY_S = 1.0       # min gap between failed status fetches


def current_session_id() -> int | None:
    """This process's Windows session id, or None off Windows /
    when it cannot be determined. Session 0 is the non-interactive
    services session."""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        session_id = ctypes.c_ulong(0)
        ok = kernel32.ProcessIdToSessionId(
            os.getpid(), ctypes.byref(session_id))
        return int(session_id.value) if ok else None
    except Exception:
        return None


def read_session_helper(state_dir: Path, *,
                        now: float | None = None) -> dict | None:
    """The session helper's live registration, or None.

    A registration counts only when it is fresh (heartbeat within
    HELPER_FRESH_S), names a live pid, and does not claim session 0
    (a helper in the services session is no better than the agent
    itself). Anything else — missing file, stale heartbeat, dead
    pid — means there is no helper to broker through.
    """
    now = time.time() if now is None else now
    try:
        reg = json.loads(
            (Path(state_dir) / HELPER_REGISTRY_NAME).read_text(
                encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(reg, dict):
        return None
    port = reg.get("port")
    pid = reg.get("pid")
    updated = reg.get("updated_at")
    if not isinstance(port, int) or not 0 < port < 65536:
        return None
    if not isinstance(pid, int) or not pid_alive(pid):
        return None
    if not isinstance(updated, (int, float)) \
            or now - float(updated) > HELPER_FRESH_S:
        return None
    if reg.get("session_id") == 0:
        return None
    return reg


# ---------------------------------------------------------------------------
# Wake-on-LAN
# ---------------------------------------------------------------------------

_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}([:-]?[0-9A-Fa-f]{2}){5}$")
_WOL_DEFAULT_BROADCAST = "255.255.255.255"
_WOL_DEFAULT_PORT = 9


def normalize_mac(value) -> str:
    """Canonical 'AA:BB:CC:DD:EE:FF' form of a MAC address.

    Accepts colon, dash, or bare hex forms in any case; anything
    else is a ValueError (the route turns it into a 400).
    """
    if not isinstance(value, str) or not _MAC_RE.match(value.strip()):
        raise ValueError(f"invalid MAC address: {value!r}")
    digits = re.sub(r"[^0-9A-Fa-f]", "", value).upper()
    return ":".join(digits[i:i + 2] for i in range(0, 12, 2))


def build_magic_packet(mac: str) -> bytes:
    """The 102-byte magic packet: 6 x 0xFF, then the MAC 16 times."""
    raw = bytes.fromhex(normalize_mac(mac).replace(":", ""))
    return b"\xff" * 6 + raw * 16


def validate_wol_payload(payload: dict) -> tuple[str, str, int]:
    """Return (mac, broadcast, port) for a /v1/wol request body."""
    mac = normalize_mac(payload.get("mac"))
    broadcast = payload.get("broadcast") or _WOL_DEFAULT_BROADCAST
    if not isinstance(broadcast, str):
        raise ValueError("broadcast must be an IP address string")
    try:
        socket.inet_aton(broadcast)
    except OSError:
        raise ValueError(
            f"invalid broadcast address: {broadcast!r}") from None
    port = payload.get("port", _WOL_DEFAULT_PORT)
    if isinstance(port, bool) or not isinstance(port, int) \
            or not 0 < port < 65536:
        raise ValueError("port must be an integer in 1..65535")
    return mac, broadcast, port


def send_magic_packet(mac: str, broadcast: str, port: int) -> dict:
    """Send one magic packet by UDP broadcast from this machine."""
    packet = build_magic_packet(mac)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (broadcast, port))
    finally:
        sock.close()
    return {"mac": mac, "broadcast": broadcast, "port": port,
            "bytes": len(packet)}


# ---------------------------------------------------------------------------
# UAC consent detection (Windows)
# ---------------------------------------------------------------------------

def _declare_snapshot_signatures(kernel32) -> None:
    """Declare argtypes/restype for the Toolhelp32 snapshot calls.

    Same handle discipline as _declare_process_signatures: the
    snapshot handle is pointer-sized, so every handle slot is
    c_void_p — an undeclared restype would truncate it to a C int.
    Kept separate from _declare_process_signatures because the two
    declaration sets cover different calls.
    """
    import ctypes
    P = ctypes.c_void_p
    I = ctypes.c_int
    UL = ctypes.c_ulong
    kernel32.CreateToolhelp32Snapshot.argtypes = [UL, UL]
    kernel32.CreateToolhelp32Snapshot.restype = P
    kernel32.Process32FirstW.argtypes = [P, P]
    kernel32.Process32FirstW.restype = I          # BOOL
    kernel32.Process32NextW.argtypes = [P, P]
    kernel32.Process32NextW.restype = I           # BOOL
    kernel32.CloseHandle.argtypes = [P]
    kernel32.CloseHandle.restype = I              # BOOL


def consent_prompt_active() -> bool:
    """True while Windows is showing a UAC consent prompt.

    consent.exe runs (in the SYSTEM session) for exactly the
    lifetime of an elevation prompt on the secure desktop, so its
    presence in the process list is the classic signal. Windows
    only: everywhere else this is False, and any probe failure is
    also False — a phantom "needs you" would be worse than none.
    Presence only: nothing about the prompt's contents is read, and
    nothing about any credential is ever observed or logged.

    PC-VERIFICATION PENDING: the Toolhelp32 path is written against
    the documented Win32 ABI but has never run on Windows (see
    docs/TEST_PLAN.md); the monitor's transition logic is what the
    VM suite exercises, with this probe stubbed.
    """
    if not IS_WINDOWS:
        return False
    import ctypes

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong),
            ("th32DefaultHeapID", ctypes.c_void_p),   # ULONG_PTR
            ("th32ModuleID", ctypes.c_ulong),
            ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    TH32CS_SNAPPROCESS = 0x00000002
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        _declare_snapshot_signatures(kernel32)
        handle = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not handle or handle == ctypes.c_void_p(-1).value:
            return False
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            ok = kernel32.Process32FirstW(handle, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower() == "consent.exe":
                    return True
                ok = kernel32.Process32NextW(handle, ctypes.byref(entry))
            return False
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # a broken probe must never claim a prompt
        return False


class UacMonitor:
    """Polls the consent probe and tracks prompt state transitions.

    Surfaces: snapshot() feeds /v1/status ("uac_prompt") and the
    avatar's display-state mapping; transitions are written to the
    audit log as uac_prompt_shown / uac_prompt_cleared events. The
    probe is injectable so the transition logic is unit-testable on
    any platform.
    """

    def __init__(self, core: "BridgeCore", probe=None):
        self._core = core
        self._probe = probe if probe is not None else consent_prompt_active
        try:
            self._poll_s = float(core.cfg.get("uac_poll_interval_s") or 2.0)
        except (TypeError, ValueError):
            self._poll_s = 2.0
        self._poll_s = max(0.5, self._poll_s)
        self._lock = threading.Lock()
        self._active = False
        self._since: float | None = None

    def check_once(self, now: float | None = None) -> bool:
        """Run one probe; audit and record any transition."""
        now = time.time() if now is None else now
        try:
            active = bool(self._probe())
        except Exception:  # a failing probe reads as "no prompt"
            active = False
        with self._lock:
            was = self._active
            if active and not was:
                self._active = True
                self._since = now
            elif was and not active:
                self._active = False
                waited = now - (self._since or now)
                self._since = None
            else:
                waited = None
        if active and not was:
            self._core.audit({
                "event": "uac_prompt_shown", "ip": None, "method": None,
                "path": None,
                "summary": "UAC consent prompt is awaiting the owner",
                "status": None, "duration_ms": None,
            })
        elif was and not active:
            self._core.audit({
                "event": "uac_prompt_cleared", "ip": None, "method": None,
                "path": None,
                "summary": f"UAC consent prompt cleared after "
                           f"{waited:.0f}s",
                "status": None, "duration_ms": None,
            })
        return active

    def snapshot(self) -> dict:
        with self._lock:
            since = None
            if self._active and self._since is not None:
                since = datetime.fromtimestamp(
                    self._since, timezone.utc).isoformat(
                    timespec="milliseconds").replace("+00:00", "Z")
            return {"active": self._active, "since": since}

    def run(self) -> None:
        """Poll loop for the lifetime of the agent (daemon thread).

        A no-op off Windows: there is no consent prompt to detect,
        and the status field simply reports inactive.
        """
        if not IS_WINDOWS:
            return
        while True:
            self.check_once()
            time.sleep(self._poll_s)


def _uac_watch(core: "BridgeCore") -> None:
    core.uac.run()


# ---------------------------------------------------------------------------
# UAC pre-flight assessment (v1.2 §1)
#
# A submission is assessed BEFORE it executes: static heuristics over
# the command/script text flag the operations that normally raise a
# UAC consent prompt, and the live consent state from the v1.1
# monitor says whether a prompt is already on screen. Heuristics
# cannot prove a negative — "likely": false is advisory, never a
# guarantee — so the default behaviour is unchanged (execute and
# report); only an explicit "require_no_uac": true turns a likely
# assessment into a 409 refusal that executes nothing.
# ---------------------------------------------------------------------------

def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# (reason, pattern) — one entry per spec §1 heuristic family.
_UAC_TEXT_RULES: list[tuple[str, re.Pattern]] = [
    ("installer invocation (msiexec)",
     _rx(r"\bmsiexec(?:\.exe)?\b")),
    ("installer invocation (setup*.exe)",
     _rx(r"\bsetup[\w.\-]*\.exe\b")),
    ("installer package (.msi)",
     _rx(r"\.msi\b")),
    ("elevation via Start-Process -Verb RunAs / runas",
     _rx(r"(?:start-process\b[^|;&\n]*-verb\s+[\"']?runas"
         r"|\brunas(?:\.exe)?\b)")),
    ("write under HKLM:",
     _rx(r"(?:\bHKLM:|\bHKEY_LOCAL_MACHINE\b)")),
    ("system location (Program Files / %SystemRoot%)",
     _rx(r"(?:\bprogram files\b|%programfiles(?:\(x86\))?%|%systemroot%"
         r"|%windir%)")),
    ("service control (net start/stop)",
     _rx(r"\bnet(?:\.exe)?\s+(?:start|stop)\b")),
    ("service control (sc config/create)",
     _rx(r"\bsc(?:\.exe)?\s+(?:config|create)\b")),
    ("machine-scope Set-ExecutionPolicy",
     _rx(r"set-executionpolicy\b[^|;&\n]*-scope\s+[\"']?localmachine\b")),
    ("system servicing tool (dism/sfc/bcdedit)",
     _rx(r"\b(?:dism|sfc|bcdedit)(?:\.exe)?(?![\w\-])")),
    ("driver install (pnputil /add-driver)",
     _rx(r"\bpnputil(?:\.exe)?\b[^|;&\n]*/add-driver\b")),
]

_UAC_SCHTASKS_RE = _rx(r"\bschtasks(?:\.exe)?\b")
_UAC_CREATE_RE = _rx(r"/create\b")
_UAC_RU_SYSTEM_RE = _rx(r"/ru\s+[\"']?system\b")


def uac_static_assessment(text: str) -> tuple[bool, list[str]]:
    """Static heuristic pass over command/script text.

    Returns (likely, reasons) with one human-readable reason per
    matched family. Pure and platform-independent so the contract
    is fully testable off Windows.
    """
    text = text or ""
    reasons = [reason for reason, pattern in _UAC_TEXT_RULES
               if pattern.search(text)]
    if (_UAC_SCHTASKS_RE.search(text) and _UAC_CREATE_RE.search(text)
            and _UAC_RU_SYSTEM_RE.search(text)):
        reasons.append("scheduled task as SYSTEM (schtasks /create /RU SYSTEM)")
    return bool(reasons), reasons


def assess_uac(core: "BridgeCore", text: str) -> dict:
    """The full pre-flight object for a submission: static
    likelihood + reasons, and the live consent state from the
    core's UAC monitor (a prompt already on screen)."""
    likely, reasons = uac_static_assessment(text)
    return {
        "likely": likely,
        "reasons": reasons,
        "consent_pending": bool(core.uac.snapshot().get("active")),
    }


def kill_tree(proc: subprocess.Popen) -> None:
    """Terminate a process and (POSIX) its process group."""
    try:
        if IS_WINDOWS:
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
    except OSError:
        pass


def kill_pid_tree(pid: int) -> None:
    """Best-effort kill of a detached pid. On Windows uses taskkill /T."""
    if IS_WINDOWS:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=15)
        except (OSError, subprocess.SubprocessError):
            pass
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


# --------------------------------------------------------------------------
# Thread-safe bounded output capture
# --------------------------------------------------------------------------

class OutputBuffer:
    """Append-only byte capture with a hard cap.

    Bytes past the cap are counted but discarded (``truncated``), so a
    runaway command cannot exhaust agent memory. Readers use absolute
    byte offsets against the *logical* stream (``total``), which makes
    incremental polling stable even after truncation.
    """

    def __init__(self, cap: int):
        self.cap = cap
        self._data = bytearray()
        self.total = 0
        self.truncated = False
        self._lock = threading.Lock()

    def append(self, chunk: bytes) -> None:
        if not chunk:
            return
        with self._lock:
            self.total += len(chunk)
            room = self.cap - len(self._data)
            if room > 0:
                self._data += chunk[:room]
            if len(chunk) > max(room, 0):
                self.truncated = True

    def read(self, offset: int = 0, max_bytes: int | None = None) -> tuple[bytes, int]:
        with self._lock:
            start = max(0, min(offset, len(self._data)))
            end = len(self._data) if max_bytes is None else min(
                len(self._data), start + max_bytes)
            return bytes(self._data[start:end]), self.total

    def text(self, offset: int = 0, max_bytes: int | None = None) -> tuple[str, int]:
        data, total = self.read(offset, max_bytes)
        return data.decode("utf-8", errors="replace"), total


# --------------------------------------------------------------------------
# Core: audit log, rate limiting, file roots, runtime registries
# --------------------------------------------------------------------------

def _lock_file_exclusive(fh) -> bool:
    """Take an OS-level exclusive lock on an open file. The lock is
    released by closing the file or via _unlock_file. Separate opens
    conflict even within one process (flock is per open-file
    description; Windows byte-range locks are per handle), which is
    what makes this usable as a cross-writer mutex."""
    if IS_WINDOWS:
        import msvcrt
        fh.seek(0, os.SEEK_END)
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        return True
    try:
        import fcntl
    except ImportError:
        return False
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    return True


def _try_lock_file_exclusive(fh) -> bool:
    """Non-blocking variant of _lock_file_exclusive: True when the
    lock was taken, False when another holder (process or open file
    description) already has it. Used for ownership claims that
    must fail fast rather than queue (the session helper's
    state-dir ownership). On a platform with no lock primitive at
    all, returns True — the caller proceeds unguarded rather than
    never starting (the session-helper registration freshness
    check remains as the sequential guard there)."""
    if IS_WINDOWS:
        import msvcrt
        fh.seek(0, os.SEEK_END)
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        fh.seek(0)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    try:
        import fcntl
    except ImportError:
        return True
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock_file(fh) -> None:
    try:
        if IS_WINDOWS:
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except (OSError, ImportError):
        pass


_AUDIT_PATH_LOCKS: dict[str, threading.Lock] = {}
_AUDIT_PATH_LOCKS_GUARD = threading.Lock()


def _audit_lock_for(audit_path: Path) -> threading.Lock:
    """The process-local audit lock for a log path, SHARED by every
    core writing to that path. Two cores in one process (the test
    fixtures run the agent and the helper as two servers in one
    process) must not rely on the file lock alone: Windows
    byte-range locks have per-handle semantics quite unlike flock
    — including dropping a process's locks on a file when ANY of
    its handles to that file closes — so co-hosted serialization
    is made independent of those subtleties by sharing this plain
    threading lock. Keyed by the resolved path so differently
    spelled references to one log still share the lock."""
    key = str(Path(audit_path).resolve())
    with _AUDIT_PATH_LOCKS_GUARD:
        lock = _AUDIT_PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _AUDIT_PATH_LOCKS[key] = lock
        return lock


@contextmanager
def _audit_file_lock(audit_path: Path):
    """Serialize one audit append (+ its rotation) across processes.

    The main agent and the session helper append to the SAME audit
    log from two processes; each core's threading lock serializes
    only its own writers, so two cores could both decide to rotate
    from the same stale file state and shift the archives twice,
    discarding entries that should have been retained (Codex PR #47
    finding). Within one process the writers share a threading lock
    (see _audit_lock_for); this is the cross-process layer. It lives
    in a sidecar file (audit log name + ".lock") because rotation
    renames the log itself; the sidecar name never changes.
    Acquisition failure never takes auditing down with it: on
    OSError the caller proceeds unlocked, with a stderr warning —
    the uncoordinated behaviour is the fallback, never a crash and
    never a silently dropped entry.
    """
    lock_path = audit_path.with_name(audit_path.name + ".lock")
    fh = None
    locked = False
    try:
        try:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(lock_path, "a+b")
            locked = _lock_file_exclusive(fh)
            if not locked:
                print("[bridge] WARNING: no file-lock primitive on "
                      "this platform; audit append proceeding "
                      "without cross-process coordination",
                      file=sys.stderr)
        except OSError as exc:
            print(f"[bridge] WARNING: audit lock unavailable: {exc}; "
                  f"append proceeding unlocked", file=sys.stderr)
        yield
    finally:
        if fh is not None:
            if locked:
                _unlock_file(fh)
            try:
                fh.close()
            except OSError:
                pass


def _audit_entry_epoch(entry: dict) -> float | None:
    """Unix timestamp of an audit entry's ISO ``ts`` field, or None
    when the field is missing or unparseable (foreign lines in the
    log are not bridge entries and carry no trustworthy time)."""
    ts = entry.get("ts")
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(
            ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class BridgeCore:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.token = str(cfg.get("token", ""))
        if "roots" not in cfg:
            # Configs built without load_config() (e.g. tests): derive.
            derived = []
            if cfg.get("file_roots"):
                for entry in cfg["file_roots"]:
                    derived.append({"name": str(entry["name"]),
                                    "path": str(entry["path"])})
            else:
                derived.append({"name": "default",
                                "path": str(cfg["allowed_file_root"])})
            cfg = dict(cfg)
            cfg["roots"] = derived
            self.cfg = cfg
        self.roots: dict[str, Path] = {}
        for entry in cfg["roots"]:
            p = Path(entry["path"])
            p.mkdir(parents=True, exist_ok=True)
            self.roots[entry["name"]] = p
        self.default_root_name = cfg["roots"][0]["name"]
        # v0 attribute kept for compat with older client/tests language.
        self.file_root = self.roots[self.default_root_name]
        self.state_dir = Path(cfg["state_dir"])
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.audit_path = Path(cfg["audit_log"])
        self.started_at = time.time()
        # Shared with every other core writing to the same log in
        # this process (see _audit_lock_for) — a private lock per
        # core left the rotation race open between co-hosted cores.
        self._audit_lock = _audit_lock_for(self.audit_path)
        # auth rate limiting (per source IP)
        self._auth_lock = threading.Lock()
        self._auth_failures: dict[str, deque] = {}
        self._auth_blocked_until: dict[str, float] = {}
        # runtime registries
        self.jobs: dict[str, "Job"] = {}
        self._jobs_lock = threading.Lock()
        self.processes: dict[str, "DetachedProcess"] = {}
        self._processes_lock = threading.Lock()
        self.sessions: dict[str, "Session"] = {}
        self._sessions_lock = threading.Lock()
        self.uploads: dict[str, "Upload"] = {}
        self._uploads_lock = threading.Lock()
        # Last-known merge of session-helper-owned process records,
        # for the deadline-bound /v1/status path: (monotonic
        # fetched-at, registration port, records) plus the last
        # failed fetch (monotonic, port). See
        # BridgeHandler._helper_processes_for_status.
        self._helper_merge_lock = threading.Lock()
        self._helper_merge_cache: tuple[float, int, list] | None = None
        self._helper_merge_failed: tuple[float, int] | None = None
        # UAC consent-prompt monitor (polled by a thread started in
        # create_server; inert off Windows).
        self.uac = UacMonitor(self)
        # True when this core belongs to the interactive session
        # helper (agent/session_helper.py) rather than the main
        # agent: helpers serve desktop routes directly and never
        # broker onward.
        self.is_helper = bool(cfg.get("session_helper"))
        self._load_processes()
        self._load_uploads()

    # -- interactive-session broker --------------------------------------
    def session_helper_registration(self) -> dict | None:
        """The live session-helper registration to broker desktop
        routes through, or None. Helpers never broker, and the
        broker can be switched off in config."""
        if self.is_helper or not self.cfg.get("session_broker", True):
            return None
        return read_session_helper(self.state_dir)

    def desktop_unavailable_reason(self) -> str | None:
        """Why desktop routes cannot be served right now, or None
        when they can (directly, or via the session helper).

        Only one case blocks: this agent is in Windows session 0
        (the SYSTEM boot core) and no interactive session helper is
        registered. Serving capture/input/clipboard/GUI-launch from
        session 0 would act on the wrong desktop, so the routes
        answer 501 with this reason instead. (Off Windows the
        session id is None, which never equals 0 — no block.)
        """
        if self.is_helper:
            return None
        if self.session_helper_registration() is not None:
            return None
        if current_session_id() != 0:
            return None
        return ("desktop features need the interactive session: this "
                "agent is running in session 0 (boot core) and no "
                "session helper is registered — log on so the avatar "
                "starts the helper, or use a logon form of the bridge")

    # -- audit -------------------------------------------------------------
    def audit(self, entry: dict) -> None:
        record = {"ts": utc_now_iso()}
        record.update(entry)
        line = json.dumps(record, ensure_ascii=False)
        if self.token:
            # Invariant (spec §0/§2): the token is NEVER written to
            # the audit log. Command summaries are audit content, so
            # a command that happens to contain the token string
            # (e.g. a test echoing it) would otherwise leak the
            # credential into the log — and, via GET /v1/audit, back
            # out over the API. Scrub the exact token value from
            # every line at write time; the command still executes
            # verbatim, only the audit copy is masked.
            line = line.replace(self.token, "***")
        try:
            with self._audit_lock:
                # The session helper appends to this same log (in
                # production from another process). _audit_lock is
                # shared per log path within this process, and the
                # file lock below coordinates across processes;
                # together they make rotation + append atomic
                # across BOTH writers (see _audit_lock_for and
                # _audit_file_lock).
                with _audit_file_lock(self.audit_path):
                    self.audit_path.parent.mkdir(
                        parents=True, exist_ok=True)
                    self._rotate_audit_if_needed(len(line) + 1)
                    with open(self.audit_path, "a",
                              encoding="utf-8") as fh:
                        fh.write(line + "\n")
        except OSError as exc:  # never crash the server on audit failure
            print(f"[bridge] WARNING: audit write failed: {exc}", file=sys.stderr)

    def _rotate_audit_if_needed(self, incoming: int) -> None:
        """Size-based rotation (v1 §5). Caller holds both audit
        locks (the per-core threading lock and the cross-process
        audit file lock), so the size check and the archive renames
        cannot interleave with another writer's rotation."""
        max_bytes = int(self.cfg.get("audit_max_bytes") or 0)
        keep = int(self.cfg.get("audit_keep") or 0)
        if max_bytes <= 0 or keep <= 0:
            return
        try:
            size = self.audit_path.stat().st_size
        except OSError:
            return
        if size == 0 or size + incoming <= max_bytes:
            return
        # audit.jsonl.(keep-1) -> .(keep), ..., current -> .1
        for i in range(keep - 1, 0, -1):
            src = self.audit_path.with_name(self.audit_path.name + f".{i}")
            dst = self.audit_path.with_name(self.audit_path.name + f".{i + 1}")
            try:
                if src.exists():
                    os.replace(src, dst)
            except OSError:
                pass
        try:
            os.replace(self.audit_path,
                       self.audit_path.with_name(self.audit_path.name + ".1"))
        except OSError:
            pass

    def audit_tail(self, n: int) -> list[dict]:
        """Return the last ``n`` audit entries from the current log file."""
        n = max(1, min(n, 1000))
        try:
            lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines[-n:]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append({"raw": line})
        return out

    def audit_read(self, since: float | None = None,
                   limit: int = 200) -> dict:
        """Entries at/after ``since`` (unix ts), oldest first (v1.2 §2).

        Reads ONLY this core's configured audit file — the path is
        never request-supplied, so the endpoint cannot be pointed at
        any other file. ``limit`` defaults to 200 and is hard-capped
        at 1000. When more entries remain, the result's
        ``next_since`` is a cursor strictly past the last returned
        entry (audit timestamps are millisecond-resolution, so the
        cursor is the last timestamp + 0.5 ms: it can never repeat
        the boundary entry, and a page never splits a group of
        entries sharing one millisecond — such a group is returned
        whole, slightly over the limit, rather than losing its tail
        behind the cursor). Pass it back as ``since`` to page.
        Read-only: nothing here truncates, rotates, or rewrites the
        log (rotation stays where it has always been: in audit()).
        """
        limit = max(1, min(int(limit), 1000))
        try:
            lines = self.audit_path.read_text(
                encoding="utf-8").splitlines()
        except OSError:
            return {"entries": [], "count": 0, "next_since": None}
        entries: list[dict] = []
        last_ts: float | None = None
        more = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            ts = _audit_entry_epoch(entry)
            if since is not None and (ts is None or ts < since):
                continue
            if len(entries) >= limit and not (ts is not None
                                              and ts == last_ts):
                more = True
                break
            entries.append(entry)
            if ts is not None:
                last_ts = ts
        next_since = None
        if more and last_ts is not None:
            next_since = last_ts + 0.0005
        return {"entries": entries, "count": len(entries),
                "next_since": next_since}

    def log_start(self) -> None:
        self.audit({
            "event": "server_start",
            "ip": None, "method": None, "path": None,
            "summary": f"{AGENT_NAME} {VERSION} listening on "
                       f"{self.cfg['host']}:{self.cfg['port']}",
            "status": None, "duration_ms": None,
        })

    def log_stop(self) -> None:
        self.audit({
            "event": "server_stop",
            "ip": None, "method": None, "path": None,
            "summary": f"{AGENT_NAME} shutting down",
            "status": None, "duration_ms": None,
        })

    # -- auth rate limiting --------------------------------------------------
    def auth_blocked(self, ip: str) -> float:
        """Seconds the IP must still wait, or 0 if not blocked."""
        with self._auth_lock:
            until = self._auth_blocked_until.get(ip, 0.0)
            remaining = until - time.monotonic()
            return remaining if remaining > 0 else 0.0

    def note_auth_failure(self, ip: str) -> None:
        limit = int(self.cfg.get("auth_fail_limit") or 0)
        if limit <= 0:
            return
        window = float(self.cfg.get("auth_fail_window_s") or 60)
        block = float(self.cfg.get("auth_block_s") or 30)
        now = time.monotonic()
        with self._auth_lock:
            dq = self._auth_failures.setdefault(ip, deque())
            dq.append(now)
            while dq and now - dq[0] > window:
                dq.popleft()
            if len(dq) >= limit:
                self._auth_blocked_until[ip] = now + block

    def note_auth_success(self, ip: str) -> None:
        with self._auth_lock:
            self._auth_failures.pop(ip, None)
            self._auth_blocked_until.pop(ip, None)

    # -- file roots ------------------------------------------------------------
    def root_path(self, name: str | None) -> Path:
        if name is None:
            return self.roots[self.default_root_name]
        if name not in self.roots:
            raise ValueError(f"unknown file root: {name!r} "
                             f"(configured: {', '.join(sorted(self.roots))})")
        return self.roots[name]

    def resolve_in_root(self, root_name: str | None, rel: str) -> Path:
        """Resolve a client-supplied relative path inside a named root.

        Raises ValueError for anything absolute or escaping the root.
        """
        root = self.root_path(root_name).resolve()
        if rel is None:
            rel = "."
        rel = str(rel).replace("\\", "/") if IS_WINDOWS else str(rel)
        if IS_WINDOWS and _DRIVE_RE.match(rel):
            raise ValueError("absolute/drive paths are not allowed")
        p = Path(rel)
        if p.is_absolute():
            raise ValueError("absolute paths are not allowed")
        target = (root / p).resolve()
        if target != root and root not in target.parents:
            raise ValueError("path escapes the allowed file root")
        return target

    def resolve_rel(self, rel: str) -> Path:
        """v0 compat: resolve inside the default root."""
        return self.resolve_in_root(None, rel)

    def rel_display(self, target: Path, root_name: str | None = None) -> str:
        root = self.root_path(root_name).resolve()
        try:
            return target.resolve().relative_to(root).as_posix()
        except ValueError:
            return "."

    # -- detached-process registry persistence --------------------------------
    def _processes_file(self) -> Path:
        return self.state_dir / "processes.json"

    def _save_processes(self) -> None:
        try:
            data = [p.record() for p in self.processes.values()]
            tmp = self._processes_file().with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, self._processes_file())
        except OSError as exc:
            print(f"[bridge] WARNING: process registry save failed: {exc}",
                  file=sys.stderr)

    def _load_processes(self) -> None:
        try:
            raw = json.loads(self._processes_file().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for item in raw if isinstance(raw, list) else []:
            try:
                proc = DetachedProcess.from_record(self, item)
            except (KeyError, TypeError, ValueError):
                continue
            self.processes[proc.id] = proc

    # -- upload registry persistence -------------------------------------------
    def _uploads_dir(self) -> Path:
        d = self.state_dir / "uploads"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_uploads(self) -> None:
        base = self._uploads_dir()
        for meta_file in sorted(base.glob("*/meta.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                up = Upload(self, meta)
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            self.uploads[up.id] = up


# --------------------------------------------------------------------------
# Incremental pipe reads
# --------------------------------------------------------------------------

def _read_available(stream, size: int = 65536) -> bytes:
    """One incremental read from a pipe-backed stream.

    ``BufferedReader.read(n)`` blocks until *n* bytes arrive or EOF.
    A job's process exit (EOF) eventually flushes that wait, but an
    interactive session's shell never EOFs — a few hundred bytes of
    session output starved indefinitely behind a 64 KiB read (found
    by the first Windows suite run: session round-trips returned
    empty forever). ``read1()`` performs a single raw read and
    returns promptly with whatever is available. Streams without
    ``read1`` fall back to a plain ``read``.
    """
    read1 = getattr(stream, "read1", None)
    if read1 is not None:
        return read1(size)
    return stream.read(size)


# --------------------------------------------------------------------------
# Async jobs (v1 §1)
# --------------------------------------------------------------------------

class Job:
    """One exec invocation running as a background job.

    The HTTP request that submits a job returns immediately; the job's
    process, output buffers, and deadline live here, independent of
    any client connection. A dropped client therefore never loses work
    or leaves its state ambiguous.
    """

    def __init__(self, core: BridgeCore, payload: dict, argv: list[str],
                 cwd: str, env: dict, timeout: float | None):
        self.core = core
        self.id = uuid.uuid4().hex[:12]
        self.shell = str(payload.get("shell") or default_shell())
        self.command_summary = str(payload.get("command", ""))[:500]
        self.argv = argv
        self.cwd = cwd
        self.env = env
        self.timeout = timeout
        cap = int(core.cfg["job_output_cap_bytes"])
        self.stdout = OutputBuffer(cap)
        self.stderr = OutputBuffer(cap)
        self.state = "queued"          # queued|running|done|failed|killed
        self.exit_code: int | None = None
        self.timed_out = False
        self.proc: subprocess.Popen | None = None
        self.started_wall = time.time()
        self.started_mono = time.monotonic()
        self.ended_mono: float | None = None
        self._done = threading.Event()
        self._lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        thread = threading.Thread(target=self._run, daemon=True,
                                  name=f"job-{self.id}")
        thread.start()

    def _pump(self, stream, buffer: OutputBuffer) -> None:
        try:
            while True:
                chunk = _read_available(stream)
                if not chunk:
                    break
                buffer.append(chunk)
        except (OSError, ValueError):
            pass

    def _run(self) -> None:
        self.state = "running"
        try:
            self.proc = subprocess.Popen(
                self.argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                env=self.env,
                start_new_session=not IS_WINDOWS,
            )
        except OSError as exc:
            self.state = "failed"
            self.stderr.append(f"[bridge] failed to start shell: {exc}".encode())
            self._finish()
            return
        pumps = [
            threading.Thread(target=self._pump, args=(self.proc.stdout, self.stdout),
                             daemon=True),
            threading.Thread(target=self._pump, args=(self.proc.stderr, self.stderr),
                             daemon=True),
        ]
        for t in pumps:
            t.start()
        try:
            self.exit_code = self.proc.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            self.timed_out = True
            kill_tree(self.proc)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            # v0 contract: exit_code is null when a command timed out,
            # even though the kill produced a raw return code.
            self.exit_code = None
        for t in pumps:
            t.join(timeout=5)
        with self._lock:
            if self.state == "running":
                self.state = "done" if not self.timed_out else "failed"
        self._finish()

    def _finish(self) -> None:
        self.ended_mono = time.monotonic()
        self._done.set()
        out_bytes, _ = self.stdout.read(0, self.stdout.total)
        err_bytes, _ = self.stderr.read(0, self.stderr.total)
        # v1 §5: job completions are audited with output hashes (the
        # hash covers the captured prefix if the stream was capped).
        self.core.audit({
            "event": "job_finish",
            "ip": None, "method": None, "path": None,
            "summary": f"job {self.id} {self.state}: {self.command_summary}",
            "status": None,
            "duration_ms": int((self.ended_mono - self.started_mono) * 1000)
            if self.ended_mono else None,
            "job_id": self.id,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "stdout_sha256": sha256_hex(out_bytes),
            "stderr_sha256": sha256_hex(err_bytes),
            "stdout_bytes": self.stdout.total,
            "stderr_bytes": self.stderr.total,
        })

    def cancel(self) -> bool:
        with self._lock:
            if self.state not in ("queued", "running"):
                return False
            self.state = "killed"
        if self.proc is not None and self.proc.poll() is None:
            kill_tree(self.proc)
        return True

    def wait(self, seconds: float) -> bool:
        return self._done.wait(timeout=seconds)

    @property
    def duration_ms(self) -> int | None:
        if self.ended_mono is None:
            return None
        return int((self.ended_mono - self.started_mono) * 1000)

    def describe(self) -> dict:
        return {
            "job_id": self.id,
            "state": self.state,
            "shell": self.shell,
            "command": self.command_summary,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "started_at": datetime.fromtimestamp(
                self.started_wall, timezone.utc).isoformat(
                timespec="milliseconds").replace("+00:00", "Z"),
            "duration_ms": self.duration_ms,
            "stdout_bytes": self.stdout.total,
            "stderr_bytes": self.stderr.total,
        }

    def output(self, stdout_offset: int, stderr_offset: int,
               max_bytes: int) -> dict:
        obj = self.describe()
        out_text, _ = self.stdout.text(stdout_offset, max_bytes)
        err_text, _ = self.stderr.text(stderr_offset, max_bytes)
        obj.update({
            "stdout": out_text,
            "stderr": err_text,
            "stdout_truncated": self.stdout.truncated,
            "stderr_truncated": self.stderr.truncated,
            "truncated": self.stdout.truncated or self.stderr.truncated,
        })
        return obj


def validate_exec_payload(core: BridgeCore, payload: dict):
    """Shared validation for exec/jobs/processes/sessions submissions.

    Returns (argv, cwd, env, timeout) or raises ValueError.
    """
    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("field 'command' (non-empty string) is required")
    shell = payload.get("shell") or default_shell()
    if shell not in ("powershell", "cmd", "posix"):
        raise ValueError(f"unknown shell: {shell!r}")
    argv = build_command(shell, command)

    cfg = core.cfg
    if payload.get("timeout_s") is None:
        timeout: float | None = float(cfg["default_timeout_s"])
    else:
        try:
            timeout = float(payload["timeout_s"])
        except (TypeError, ValueError):
            raise ValueError("timeout_s must be a number")
        if timeout <= 0:
            timeout = None            # explicit 0/null-ish => no deadline
        else:
            timeout = min(timeout, float(cfg["max_timeout_s"]))

    cwd = payload.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str) or not Path(cwd).is_dir():
            raise ValueError(f"cwd does not exist: {cwd!r}")
    else:
        cwd = str(agent_dir())

    return argv, cwd, _merged_env(payload), timeout


def _merged_env(payload: dict) -> dict:
    """The process environment for a spawn: ours plus payload extras."""
    env = dict(os.environ)
    extra_env = payload.get("env")
    if extra_env is not None:
        if not isinstance(extra_env, dict):
            raise ValueError("env must be an object of string values")
        for k, v in extra_env.items():
            env[str(k)] = str(v)
    return env


def submit_job(core: BridgeCore, payload: dict) -> Job:
    argv, cwd, env, timeout = validate_exec_payload(core, payload)
    job = Job(core, payload, argv, cwd, env, timeout)
    with core._jobs_lock:
        core.jobs[job.id] = job
        # Prune finished jobs beyond the retention limit (oldest first).
        finished = [j for j in core.jobs.values()
                    if j.state in ("done", "failed", "killed")]
        excess = len(finished) - int(core.cfg["job_history_limit"])
        if excess > 0:
            finished.sort(key=lambda j: j.started_wall)
            for old in finished[:excess]:
                core.jobs.pop(old.id, None)
    job.start()
    return job


# --------------------------------------------------------------------------
# Detached processes (v1 §1)
# --------------------------------------------------------------------------

class DetachedProcess:
    """A long-lived process spawned detached from any request.

    Output goes to per-process log files under the state dir; the
    registry persists to state/processes.json so inspection survives
    an agent restart (aliveness is then checked at the OS level).
    """

    def __init__(self, core: BridgeCore, pid: int, name: str,
                 command_summary: str, shell: str,
                 proc: subprocess.Popen | None = None,
                 started_wall: float | None = None,
                 proc_id: str | None = None,
                 gui: bool = False):
        self.core = core
        self.id = proc_id or uuid.uuid4().hex[:12]
        self.pid = pid
        self.name = name
        self.command_summary = command_summary
        self.shell = shell
        self.proc = proc
        self.gui = gui
        self.started_wall = started_wall or time.time()

    @property
    def out_log(self) -> Path:
        return self.core.state_dir / "processes" / f"{self.id}.out.log"

    @property
    def err_log(self) -> Path:
        return self.core.state_dir / "processes" / f"{self.id}.err.log"

    def alive(self) -> bool:
        if self.proc is not None:
            return self.proc.poll() is None
        return pid_alive(self.pid)

    def exit_code(self) -> int | None:
        if self.proc is not None:
            return self.proc.poll()
        return None

    def record(self) -> dict:
        return {
            "id": self.id, "pid": self.pid, "name": self.name,
            "command": self.command_summary, "shell": self.shell,
            "gui": self.gui,
            "started_at": self.started_wall,
        }

    @classmethod
    def from_record(cls, core: BridgeCore, item: dict) -> "DetachedProcess":
        return cls(core, pid=int(item["pid"]), name=str(item.get("name", "")),
                   command_summary=str(item.get("command", "")),
                   shell=str(item.get("shell", "")),
                   started_wall=float(item.get("started_at") or time.time()),
                   proc_id=str(item["id"]),
                   gui=bool(item.get("gui", False)))

    def describe(self, tail_bytes: int = 0) -> dict:
        obj = {
            "process_id": self.id,
            "pid": self.pid,
            "name": self.name,
            "command": self.command_summary,
            "shell": self.shell,
            "gui": self.gui,
            "alive": self.alive(),
            "exit_code": self.exit_code(),
            "started_at": datetime.fromtimestamp(
                self.started_wall, timezone.utc).isoformat(
                timespec="milliseconds").replace("+00:00", "Z"),
            "stdout_log": str(self.out_log),
            "stderr_log": str(self.err_log),
        }
        if tail_bytes > 0:
            for key, path in (("stdout_tail", self.out_log),
                              ("stderr_tail", self.err_log)):
                try:
                    data = path.read_bytes()[-tail_bytes:]
                    obj[key] = data.decode("utf-8", errors="replace")
                except OSError:
                    obj[key] = ""
        return obj


def _gui_launch_argv(payload: dict) -> tuple[list[str], str, str]:
    """Validate a GUI-mode spawn payload; return (argv, cwd, summary).

    GUI mode exists because the shell-wrapped spawn cannot track a
    GUI application: the wrapper shell (powershell -Command "app")
    returns as soon as it has handed off to the GUI exe, so the
    registry marked the *wrapper* dead while the app kept running —
    the defect the Milky Way Godot launches hit (2026-11-06), worked
    around at the time with exec + Start-Process. GUI mode spawns
    the executable directly, so the tracked pid IS the application.
    A command string is deliberately not accepted here: it cannot
    be split into argv safely.
    """
    exe = payload.get("executable")
    if not isinstance(exe, str) or not exe.strip():
        raise ValueError(
            "gui spawn requires field 'executable' (path to the .exe)")
    if not Path(exe).is_file():
        raise ValueError(f"executable does not exist: {exe!r}")
    args = payload.get("args") or []
    if not isinstance(args, list) \
            or not all(isinstance(a, str) for a in args):
        raise ValueError("field 'args' must be a list of strings")
    cwd = payload.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str) or not Path(cwd).is_dir():
            raise ValueError(f"cwd does not exist: {cwd!r}")
    else:
        cwd = str(agent_dir())
    argv = [exe, *args]
    return argv, cwd, " ".join(argv)[:500]


def spawn_detached(core: BridgeCore, payload: dict) -> DetachedProcess:
    gui = payload.get("gui") is True
    if gui:
        argv, cwd, summary = _gui_launch_argv(payload)
        env = _merged_env(payload)
        shell_name = ""
    else:
        argv, cwd, env, _timeout = validate_exec_payload(core, payload)
        summary = str(payload.get("command", ""))[:500]
        shell_name = str(payload.get("shell") or default_shell())
    name = str(payload.get("name") or "")
    proc_id = uuid.uuid4().hex[:12]
    log_dir = core.state_dir / "processes"
    log_dir.mkdir(parents=True, exist_ok=True)
    out_fh = open(log_dir / f"{proc_id}.out.log", "ab")
    err_fh = open(log_dir / f"{proc_id}.err.log", "ab")
    kwargs: dict = {}
    breakaway = False
    if IS_WINDOWS:
        flags = (subprocess.CREATE_NEW_PROCESS_GROUP
                 | subprocess.DETACHED_PROCESS)
        if gui:
            # Best effort: keep the app out of any job object that
            # dies with the agent (a Task Scheduler / supervisor
            # chain can be one). Not every job permits breakaway —
            # Popen then raises and we retry without the flag.
            flags |= subprocess.CREATE_BREAKAWAY_FROM_JOB
            breakaway = True
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    try:
        try:
            proc = subprocess.Popen(argv, stdout=out_fh, stderr=err_fh,
                                    stdin=subprocess.DEVNULL, cwd=cwd,
                                    env=env, **kwargs)
        except OSError:
            if not breakaway:
                raise
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS)
            proc = subprocess.Popen(argv, stdout=out_fh, stderr=err_fh,
                                    stdin=subprocess.DEVNULL, cwd=cwd,
                                    env=env, **kwargs)
    finally:
        out_fh.close()
        err_fh.close()
    record = DetachedProcess(core, pid=proc.pid, name=name,
                             command_summary=summary,
                             shell=shell_name,
                             proc=proc, proc_id=proc_id, gui=gui)
    with core._processes_lock:
        core.processes[record.id] = record
        core._save_processes()
    return record


# --------------------------------------------------------------------------
# Interactive sessions (v1 §1)
# --------------------------------------------------------------------------

class Session:
    """A persistent interactive shell.

    POSIX uses a real PTY (stdlib `pty`); Windows uses anonymous pipes
    (stdlib has no ConPTY binding), so Windows sessions are line-based
    rather than full-terminal. Output is merged into one buffer, read
    incrementally by offset — the terminal model.
    """

    def __init__(self, core: BridgeCore, shell: str, cwd: str, env: dict):
        self.core = core
        self.id = uuid.uuid4().hex[:12]
        self.shell = shell
        self.buffer = OutputBuffer(int(core.cfg["job_output_cap_bytes"]))
        self.state = "running"           # running|exited|closed
        self.exit_code: int | None = None
        self.last_activity = time.monotonic()
        self.started_wall = time.time()
        self._lock = threading.Lock()
        self._master_fd: int | None = None
        argv = shell_argv(shell)
        if not IS_WINDOWS and shell == "posix":
            import pty
            master, slave = pty.openpty()
            self.proc = subprocess.Popen(argv, stdin=slave, stdout=slave,
                                         stderr=slave, cwd=cwd, env=env,
                                         start_new_session=True, close_fds=True)
            os.close(slave)
            self._master_fd = master
            threading.Thread(target=self._pump_pty, daemon=True,
                             name=f"session-{self.id}").start()
        else:
            self.proc = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, cwd=cwd, env=env,
                start_new_session=not IS_WINDOWS)
            threading.Thread(target=self._pump_pipe, daemon=True,
                             name=f"session-{self.id}").start()
        threading.Thread(target=self._waiter, daemon=True).start()

    def _pump_pty(self) -> None:
        try:
            while True:
                data = os.read(self._master_fd, 65536)  # type: ignore[arg-type]
                if not data:
                    break
                self.buffer.append(data)
                self.last_activity = time.monotonic()
        except OSError:
            pass

    def _pump_pipe(self) -> None:
        try:
            while True:
                chunk = _read_available(self.proc.stdout)  # type: ignore[union-attr]
                if not chunk:
                    break
                self.buffer.append(chunk)
                self.last_activity = time.monotonic()
        except (OSError, ValueError):
            pass

    def _waiter(self) -> None:
        self.exit_code = self.proc.wait()
        with self._lock:
            if self.state == "running":
                self.state = "exited"

    def send(self, data: bytes) -> None:
        with self._lock:
            if self.state != "running":
                raise ValueError("session is not running")
            self.last_activity = time.monotonic()
        if self._master_fd is not None:
            os.write(self._master_fd, data)
        else:
            self.proc.stdin.write(data)  # type: ignore[union-attr]
            self.proc.stdin.flush()  # type: ignore[union-attr]

    def close_stdin(self) -> None:
        try:
            if self._master_fd is not None:
                pass  # PTY: EOF is Ctrl+D, sent as input by the client
            elif self.proc.stdin:
                self.proc.stdin.close()
        except OSError:
            pass

    def close(self) -> None:
        with self._lock:
            self.state = "closed"
        if self.proc.poll() is None:
            kill_tree(self.proc)

    def describe(self, offset: int = 0, max_bytes: int | None = None) -> dict:
        text, total = self.buffer.text(offset, max_bytes)
        return {
            "session_id": self.id,
            "state": self.state,
            "shell": self.shell,
            "exit_code": self.exit_code,
            "output": text,
            "output_bytes": total,
            "output_truncated": self.buffer.truncated,
            "started_at": datetime.fromtimestamp(
                self.started_wall, timezone.utc).isoformat(
                timespec="milliseconds").replace("+00:00", "Z"),
        }


# --------------------------------------------------------------------------
# Chunked uploads (v1 §3)
# --------------------------------------------------------------------------

class Upload:
    """Server-side state for one chunked, resumable upload."""

    def __init__(self, core: BridgeCore, meta: dict):
        self.core = core
        self.id = str(meta["id"])
        self.root_name = meta.get("root")
        self.rel = str(meta["path"])
        self.size = int(meta["size"])
        self.sha256 = meta.get("sha256")
        self.chunk_size = int(meta.get("chunk_size") or CHUNK_SIZE)
        self.created = float(meta.get("created") or time.time())

    @property
    def dir(self) -> Path:
        return self.core._uploads_dir() / self.id

    @property
    def chunk_count(self) -> int:
        return max(1, -(-self.size // self.chunk_size))

    def received(self) -> list[int]:
        out = []
        for i in range(self.chunk_count):
            if (self.dir / f"{i}.part").exists():
                out.append(i)
        return out

    def save_meta(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        meta = {"id": self.id, "root": self.root_name, "path": self.rel,
                "size": self.size, "sha256": self.sha256,
                "chunk_size": self.chunk_size, "created": self.created}
        (self.dir / "meta.json").write_text(json.dumps(meta, indent=2),
                                            encoding="utf-8")

    def describe(self) -> dict:
        got = self.received()
        return {
            "upload_id": self.id,
            "path": self.rel,
            "root": self.root_name or self.core.default_root_name,
            "size": self.size,
            "sha256": self.sha256,
            "chunk_size": self.chunk_size,
            "chunk_count": self.chunk_count,
            "received_chunks": got,
            "received_count": len(got),
            "complete": len(got) == self.chunk_count,
        }

    def discard(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)
        with self.core._uploads_lock:
            self.core.uploads.pop(self.id, None)

    def complete(self) -> tuple[Path, str]:
        """Assemble chunks, verify, and atomically place the file.

        Returns (target_path, sha256_of_content). Raises ValueError on
        missing chunks or a size/hash mismatch.
        """
        got = self.received()
        if len(got) != self.chunk_count:
            missing = [i for i in range(self.chunk_count) if i not in got]
            raise ValueError(f"upload incomplete; missing chunks: {missing[:10]}")
        target = self.core.resolve_in_root(self.root_name, self.rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f".upload-{self.id}")
        digest = hashlib.sha256()
        written = 0
        with open(tmp, "wb") as out:
            for i in range(self.chunk_count):
                data = (self.dir / f"{i}.part").read_bytes()
                digest.update(data)
                out.write(data)
                written += len(data)
        if written != self.size:
            tmp.unlink(missing_ok=True)
            raise ValueError(f"size mismatch: expected {self.size}, got {written}")
        hex_digest = digest.hexdigest()
        if self.sha256 and hex_digest != self.sha256:
            tmp.unlink(missing_ok=True)
            raise ValueError(f"sha256 mismatch: expected {self.sha256}, "
                             f"got {hex_digest}")
        os.replace(tmp, target)
        self.discard()
        return target, hex_digest


# --------------------------------------------------------------------------
# Platform services: screenshot / input / clipboard / UI Automation (v1 §2)
#
# Windows implementations use ctypes against user32/gdi32 (stdlib).
# Screen capture happens INSIDE this process via GDI BitBlt — never via
# an inline script pattern (Windows Defender AMSI flags script-based
# CopyFromScreen capture; the owner chose against that route). On
# non-Windows hosts these services report themselves unavailable (501)
# and /v1/status lists them under "platform_limited".
# --------------------------------------------------------------------------

class PlatformUnavailable(Exception):
    pass


def _require_windows(feature: str) -> None:
    if not IS_WINDOWS:
        raise PlatformUnavailable(f"{feature} requires a Windows host")


# -- image encoding (pure python, platform-independent, unit-tested) --------

def encode_png(width: int, height: int, rgba: bytes) -> bytes:
    """Encode raw RGBA pixels (row-major, top-down) as a PNG file."""
    if len(rgba) != width * height * 4:
        raise ValueError("pixel buffer size does not match dimensions")

    def chunk(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", binascii.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)                       # filter type 0 (none)
        raw += rgba[y * stride:(y + 1) * stride]
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


def encode_bmp(width: int, height: int, bgra: bytes) -> bytes:
    """Encode raw BGRA pixels (row-major, top-down) as a 32-bit BMP."""
    if len(bgra) != width * height * 4:
        raise ValueError("pixel buffer size does not match dimensions")
    header_size = 14 + 40
    file_size = header_size + len(bgra)
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, header_size)
    info_header = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0,
                              len(bgra), 2835, 2835, 0, 0)
    return file_header + info_header + bgra


def bgra_to_rgba(bgra: bytes) -> bytes:
    out = bytearray(len(bgra))
    out[0::4] = bgra[2::4]
    out[1::4] = bgra[1::4]
    out[2::4] = bgra[0::4]
    out[3::4] = b"\xff" * (len(bgra) // 4)   # BitBlt alpha is unreliable
    return bytes(out)


# -- screen capture (Windows, ctypes GDI) -------------------------------------

def _monitor_rects() -> list[tuple[int, int, int, int]]:
    """(x, y, w, h) for each monitor, in enumeration order."""
    import ctypes
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    rects: list[tuple[int, int, int, int]] = []

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(RECT), ctypes.c_void_p)   # LPARAM is pointer-sized

    def _cb(_hmon, _hdc, rect_ptr, _data):
        r = rect_ptr.contents
        rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return 1

    user32.EnumDisplayMonitors.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, callback_type, ctypes.c_void_p]
    user32.EnumDisplayMonitors.restype = ctypes.c_int
    user32.EnumDisplayMonitors(None, None, callback_type(_cb), 0)
    return rects


def _declare_capture_signatures(user32, gdi32) -> None:
    """Declare argtypes/restype for every user32/gdi32 call in the
    capture path.

    This is load-bearing, not decoration. The functions below take and
    return GDI handles (HDC/HBITMAP/HGDIOBJ), which are pointer-sized
    in this 64-bit process. With undeclared signatures, ctypes passes
    Python ints through the platform C long conversion — 32-bit on
    Windows — so any handle value above INT_MAX raises
    ``ArgumentError: argument 1: OverflowError: int too long to
    convert`` at capture time (observed live on the owner's PC:
    GET /v1/screenshot?format=png -> HTTP 500, while a later request
    whose handles happened to fit succeeded). Declaring every handle
    parameter and return as c_void_p removes that failure class.
    """
    import ctypes
    P = ctypes.c_void_p
    I = ctypes.c_int
    U = ctypes.c_uint
    user32.GetDC.argtypes = [P]
    user32.GetDC.restype = P
    user32.ReleaseDC.argtypes = [P, P]
    user32.ReleaseDC.restype = I
    user32.GetSystemMetrics.argtypes = [I]
    user32.GetSystemMetrics.restype = I
    gdi32.CreateCompatibleDC.argtypes = [P]
    gdi32.CreateCompatibleDC.restype = P
    gdi32.CreateCompatibleBitmap.argtypes = [P, I, I]
    gdi32.CreateCompatibleBitmap.restype = P
    gdi32.SelectObject.argtypes = [P, P]
    gdi32.SelectObject.restype = P
    gdi32.BitBlt.argtypes = [P, I, I, I, I, P, I, I, ctypes.c_ulong]
    gdi32.BitBlt.restype = I                       # BOOL
    gdi32.GetDIBits.argtypes = [P, P, U, U, P, P, U]
    gdi32.GetDIBits.restype = I
    gdi32.DeleteObject.argtypes = [P]
    gdi32.DeleteObject.restype = I                 # BOOL
    gdi32.DeleteDC.argtypes = [P]
    gdi32.DeleteDC.restype = I                     # BOOL


def capture_screen(region: tuple[int, int, int, int] | None = None,
                   monitor: int | None = None) -> tuple[int, int, bytes]:
    """Capture pixels; returns (width, height, bgra_bytes)."""
    _require_windows("screenshot")
    import ctypes
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    gdi32 = ctypes.windll.gdi32  # type: ignore[attr-defined]

    if region is not None:
        x, y, w, h = region
    elif monitor is not None:
        rects = _monitor_rects()
        if monitor < 0 or monitor >= len(rects):
            raise ValueError(f"monitor index out of range (have {len(rects)})")
        x, y, w, h = rects[monitor]
    else:
        x = user32.GetSystemMetrics(76)     # SM_XVIRTUALSCREEN
        y = user32.GetSystemMetrics(77)     # SM_YVIRTUALSCREEN
        w = user32.GetSystemMetrics(78)     # SM_CXVIRTUALSCREEN
        h = user32.GetSystemMetrics(79)     # SM_CYVIRTUALSCREEN
    if w <= 0 or h <= 0:
        raise ValueError("capture region has no area")

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_ulong), ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long), ("biPlanes", ctypes.c_ushort),
                    ("biBitCount", ctypes.c_ushort),
                    ("biCompression", ctypes.c_ulong),
                    ("biSizeImage", ctypes.c_ulong),
                    ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", ctypes.c_ulong),
                    ("biClrImportant", ctypes.c_ulong)]

    _declare_capture_signatures(user32, gdi32)
    screen_dc = user32.GetDC(None)
    if not screen_dc:
        raise PlatformUnavailable("GetDC failed")
    mem_dc = bmp = old = None
    try:
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bmp = gdi32.CreateCompatibleBitmap(screen_dc, w, h)
        if not mem_dc or not bmp:
            raise PlatformUnavailable("GDI object creation failed")
        old = gdi32.SelectObject(mem_dc, bmp)
        SRCCOPY = 0x00CC0020
        CAPTUREBLT = 0x40000000
        if not gdi32.BitBlt(mem_dc, 0, 0, w, h, screen_dc, x, y,
                            SRCCOPY | CAPTUREBLT):
            raise PlatformUnavailable("BitBlt failed")
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h                    # top-down rows
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0                # BI_RGB
        buffer = ctypes.create_string_buffer(w * h * 4)
        got = gdi32.GetDIBits(mem_dc, bmp, 0, h, buffer, ctypes.byref(bmi), 0)
        if got == 0:
            raise PlatformUnavailable("GetDIBits failed")
        return w, h, buffer.raw
    finally:
        if old and mem_dc:
            gdi32.SelectObject(mem_dc, old)
        if bmp:
            gdi32.DeleteObject(bmp)
        if mem_dc:
            gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)


# -- host input injection (Windows, SendInput) ---------------------------------

_VK = {
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "tab": 0x09, "space": 0x20, "backspace": 0x08, "delete": 0x2E,
    "del": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28,
    "left": 0x25, "right": 0x27, "ctrl": 0x11, "control": 0x11,
    "alt": 0x12, "shift": 0x10, "win": 0x5B, "capslock": 0x14,
}
for _i in range(1, 13):
    _VK[f"f{_i}"] = 0x70 + _i - 1
for _c in "abcdefghijklmnopqrstuvwxyz0123456789":
    _VK[_c] = ord(_c.upper())


def _send_inputs(events: list) -> int:
    import ctypes
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    arr = (events[0].__class__ * len(events))(*events)
    sent = user32.SendInput(len(events), arr, ctypes.sizeof(events[0]))
    if sent != len(events):
        raise PlatformUnavailable(f"SendInput sent {sent} of {len(events)} events")
    return sent


def _input_structs():
    import ctypes

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.c_void_p)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.c_void_p)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
                    ("wParamH", ctypes.c_ushort)]

    class _UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("u", _UNION)]

    return INPUT, MOUSEINPUT, KEYBDINPUT


def _virtual_screen() -> tuple[int, int, int, int]:
    import ctypes
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
            user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))


def _abs_coords(x: int, y: int) -> tuple[int, int]:
    vx, vy, vw, vh = _virtual_screen()
    nx = int((x - vx) * 65535 / max(1, vw - 1))
    ny = int((y - vy) * 65535 / max(1, vh - 1))
    return nx, ny


def mouse_position() -> tuple[int, int]:
    _require_windows("input")
    import ctypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))  # type: ignore[attr-defined]
    return pt.x, pt.y


def inject_input(actions: list[dict]) -> list[dict]:
    """Execute a sequence of input actions; returns per-action results."""
    _require_windows("input")
    INPUT, MOUSEINPUT, KEYBDINPUT = _input_structs()
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_VIRTUALDESK = 0x4000
    BUTTONS = {
        "left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
        "middle": (0x0020, 0x0040),
    }
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    results: list[dict] = []

    def mouse_event(flags: int, x: int | None = None, y: int | None = None):
        ev = INPUT()
        ev.type = 0
        if x is not None and y is not None:
            nx, ny = _abs_coords(x, y)
            ev.u.mi = MOUSEINPUT(nx, ny, 0,
                                 flags | MOUSEEVENTF_ABSOLUTE
                                 | MOUSEEVENTF_VIRTUALDESK, 0, None)
        else:
            ev.u.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
        return ev

    def key_event(vk: int = 0, scan: int = 0, flags: int = 0):
        ev = INPUT()
        ev.type = 1
        ev.u.ki = KEYBDINPUT(vk, scan, flags, 0, None)
        return ev

    def resolve_vk(action: dict) -> int:
        if "vk" in action:
            return int(action["vk"])
        name = str(action.get("key", "")).lower()
        if name in _VK:
            return _VK[name]
        raise ValueError(f"unknown key name: {name!r}")

    for action in actions:
        kind = str(action.get("type", ""))
        if kind == "sleep":
            time.sleep(min(60.0, float(action.get("ms", 0)) / 1000.0))
            results.append({"type": kind, "ok": True})
        elif kind == "mouse_pos":
            x, y = mouse_position()
            results.append({"type": kind, "ok": True, "x": x, "y": y})
        elif kind == "mouse_move":
            _send_inputs([mouse_event(MOUSEEVENTF_MOVE,
                                      int(action["x"]), int(action["y"]))])
            results.append({"type": kind, "ok": True})
        elif kind in ("mouse_down", "mouse_up"):
            button = str(action.get("button", "left"))
            if button not in BUTTONS:
                raise ValueError(f"unknown mouse button: {button!r}")
            down, up = BUTTONS[button]
            events = []
            if "x" in action and "y" in action:
                events.append(mouse_event(MOUSEEVENTF_MOVE,
                                          int(action["x"]), int(action["y"])))
            events.append(mouse_event(down if kind == "mouse_down" else up))
            _send_inputs(events)
            results.append({"type": kind, "ok": True})
        elif kind == "mouse_click":
            button = str(action.get("button", "left"))
            if button not in BUTTONS:
                raise ValueError(f"unknown mouse button: {button!r}")
            down, up = BUTTONS[button]
            events = []
            if "x" in action and "y" in action:
                events.append(mouse_event(MOUSEEVENTF_MOVE,
                                          int(action["x"]), int(action["y"])))
            for _ in range(max(1, min(5, int(action.get("clicks", 1))))):
                events.append(mouse_event(down))
                events.append(mouse_event(up))
            _send_inputs(events)
            results.append({"type": kind, "ok": True})
        elif kind == "mouse_drag":
            x1, y1 = int(action["from_x"]), int(action["from_y"])
            x2, y2 = int(action["to_x"]), int(action["to_y"])
            steps = max(1, min(100, int(action.get("steps", 10))))
            button = str(action.get("button", "left"))
            if button not in BUTTONS:
                raise ValueError(f"unknown mouse button: {button!r}")
            down, up = BUTTONS[button]
            events = [mouse_event(MOUSEEVENTF_MOVE, x1, y1),
                      mouse_event(down)]
            for i in range(1, steps + 1):
                events.append(mouse_event(
                    MOUSEEVENTF_MOVE,
                    round(x1 + (x2 - x1) * i / steps),
                    round(y1 + (y2 - y1) * i / steps)))
            events.append(mouse_event(up))
            _send_inputs(events)
            results.append({"type": kind, "ok": True})
        elif kind == "key":
            vk = resolve_vk(action)
            _send_inputs([key_event(vk), key_event(vk, flags=KEYEVENTF_KEYUP)])
            results.append({"type": kind, "ok": True})
        elif kind == "key_combo":
            names = [str(k).lower() for k in action.get("keys", [])]
            if not names:
                raise ValueError("key_combo requires a non-empty 'keys' list")
            vks = []
            for n in names:
                if n in _VK:
                    vks.append(_VK[n])
                else:
                    raise ValueError(f"unknown key name: {n!r}")
            events = [key_event(vk) for vk in vks]
            events += [key_event(vk, flags=KEYEVENTF_KEYUP)
                       for vk in reversed(vks)]
            _send_inputs(events)
            results.append({"type": kind, "ok": True})
        elif kind == "type":
            text = str(action.get("text", ""))
            events = []
            for ch in text:
                if ch == "\n":
                    events.append(key_event(0x0D))
                    events.append(key_event(0x0D, flags=KEYEVENTF_KEYUP))
                elif ch == "\t":
                    events.append(key_event(0x09))
                    events.append(key_event(0x09, flags=KEYEVENTF_KEYUP))
                else:
                    units = memoryview(ch.encode("utf-16-le")).cast("H")
                    for unit in units:
                        events.append(key_event(0, scan=int(unit),
                                                flags=KEYEVENTF_UNICODE))
                        events.append(key_event(0, scan=int(unit),
                                                flags=KEYEVENTF_UNICODE
                                                | KEYEVENTF_KEYUP))
            if events:
                _send_inputs(events)
            results.append({"type": kind, "ok": True, "chars": len(text)})
        else:
            raise ValueError(f"unknown input action type: {kind!r}")
    return results


# -- clipboard (Windows, ctypes) ------------------------------------------------

def _declare_clipboard_signatures(user32, kernel32) -> None:
    """Declare argtypes/restype for every user32/kernel32 call in
    the clipboard path.

    Same defect class as the capture/process signature fixes: the
    clipboard handle (HGLOBAL) is pointer-sized in this 64-bit
    process. The handle-returning calls already had c_void_p
    restypes declared, but no argtypes were declared anywhere, so
    passing the handle on to GlobalLock / GlobalUnlock /
    GlobalFree / SetClipboardData converted the Python int through
    the platform C long — 32-bit on Windows — raising
    ``OverflowError: int too long to convert`` for handle values
    above INT_MAX. GlobalAlloc's size parameter is SIZE_T
    (pointer-sized) for the same reason. Declaring the full table
    removes that failure class.
    """
    import ctypes
    P = ctypes.c_void_p
    I = ctypes.c_int
    U = ctypes.c_uint
    user32.OpenClipboard.argtypes = [P]
    user32.OpenClipboard.restype = I                    # BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = I                   # BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = I                   # BOOL
    user32.GetClipboardData.argtypes = [U]
    user32.GetClipboardData.restype = P                 # HANDLE
    user32.SetClipboardData.argtypes = [U, P]
    user32.SetClipboardData.restype = P                 # HANDLE
    kernel32.GlobalAlloc.argtypes = [U, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = P                    # HGLOBAL
    kernel32.GlobalLock.argtypes = [P]
    kernel32.GlobalLock.restype = P                     # LPVOID
    kernel32.GlobalUnlock.argtypes = [P]
    kernel32.GlobalUnlock.restype = I                   # BOOL
    kernel32.GlobalFree.argtypes = [P]
    kernel32.GlobalFree.restype = P                     # HLOCAL (NULL on success)


def clipboard_get() -> str:
    _require_windows("clipboard")
    import ctypes
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    CF_UNICODETEXT = 13
    _declare_clipboard_signatures(user32, kernel32)
    for _attempt in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise PlatformUnavailable("could not open the clipboard")
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def clipboard_set(text: str) -> None:
    _require_windows("clipboard")
    import ctypes
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    _declare_clipboard_signatures(user32, kernel32)
    data = (text + "\x00").encode("utf-16-le")
    for _attempt in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise PlatformUnavailable("could not open the clipboard")
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise PlatformUnavailable("GlobalAlloc failed")
        ptr = kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise PlatformUnavailable("SetClipboardData failed")
        # On success the system owns the handle; do not free it.
    finally:
        user32.CloseClipboard()


# -- UI Automation (Windows, bundled PowerShell helper) ---------------------------

def run_uia(core: "BridgeCore", payload: dict) -> dict:
    """Drive the bundled helpers/uia.ps1 and return its JSON result.

    The helper is a fixed, agent-shipped script (window enumeration,
    control-tree reads, find-by-name, invoke, get/set value) — the
    client supplies only JSON parameters, never script text.
    """
    _require_windows("UI automation")
    helper = agent_dir() / "helpers" / "uia.ps1"
    if not helper.exists():
        raise PlatformUnavailable(f"UIA helper not installed: {helper}")
    exe = resolve_shell_exe("powershell")
    if not exe:
        raise PlatformUnavailable("PowerShell not found")
    action = str(payload.get("action", ""))
    if action not in ("windows", "tree", "find", "invoke",
                      "get_value", "set_value"):
        raise ValueError(f"unknown uia action: {action!r}")
    inbox = core.state_dir / f"uia-{uuid.uuid4().hex[:8]}.json"
    inbox.write_text(json.dumps(payload), encoding="utf-8")
    try:
        proc = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
             "Bypass", "-File", str(helper), "-In", str(inbox)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    finally:
        inbox.unlink(missing_ok=True)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()[:500]
        raise ValueError(f"uia helper failed ({proc.returncode}): {err or out[:200]}")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise ValueError(f"uia helper returned non-JSON output: {out[:200]!r}")


# --------------------------------------------------------------------------
# Capabilities (v1 §4: clients feature-detect from /v1/status)
# --------------------------------------------------------------------------

def capability_lists() -> tuple[list[str], list[str]]:
    available = [
        "exec", "jobs", "processes", "sessions",
        "files.list", "files.get", "files.put", "files.range",
        "files.chunked", "files.tree", "files.ops", "files.hash",
        "audit.tail", "update.stage", "wol",
    ]
    limited: list[str] = []
    if IS_WINDOWS:
        available += ["screenshot", "input", "uia", "clipboard"]
    else:
        limited = ["screenshot", "input", "uia", "clipboard"]
    return sorted(available), sorted(limited)


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------

class BridgeHandler(BaseHTTPRequestHandler):
    server_version = f"{AGENT_NAME}/{VERSION}"
    protocol_version = "HTTP/1.1"

    # Quieten default stderr logging; the audit log is the record.
    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        pass

    @property
    def core(self) -> BridgeCore:
        return self.server.core  # type: ignore[attr-defined]

    # -- plumbing ------------------------------------------------------------
    def _send_json(self, status: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body_bytes(self, limit: int) -> bytes:
        """The request body, read at most once: the session broker
        peeks at the body to decide routing (GUI spawns), and the
        route handler then reads the same bytes from this cache."""
        cached = getattr(self, "_cached_body", None)
        if cached is None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > limit:
                raise ValueError(
                    f"request body too large ({length} > {limit})")
            cached = self.rfile.read(length) if length else b""
            self._cached_body = cached
        if len(cached) > limit:
            raise ValueError(
                f"request body too large ({len(cached)} > {limit})")
        return cached

    def _read_json_body(self) -> dict:
        raw = self._body_bytes(MAX_BODY_BYTES)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _read_raw_body(self, limit: int) -> bytes:
        return self._body_bytes(limit)

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization") or ""
        expected = f"Bearer {self.core.token}"
        return bool(self.core.token) and hmac.compare_digest(header, expected)

    def _client_ip(self) -> str:
        return self.client_address[0] if self.client_address else ""

    def _audit_request(self, summary: str, status: int, started: float,
                       exit_code=None, auth_failed: bool = False,
                       job_id: str | None = None,
                       output_sha256: str | None = None,
                       extra: dict | None = None) -> None:
        entry = {
            "event": "auth_failed" if auth_failed else "request",
            "ip": self._client_ip(),
            "method": self.command,
            "path": self.path,
            "summary": summary,
            "status": status,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        if exit_code is not None:
            entry["exit_code"] = exit_code
        if job_id is not None:
            entry["job_id"] = job_id
        if output_sha256 is not None:
            entry["output_sha256"] = output_sha256
        if extra:
            entry.update(extra)
        if getattr(self.server, "is_helper", False):
            # This request was served by the interactive session
            # helper (brokered here by the main agent, which writes
            # its own entry marked via=session-broker).
            entry.setdefault("via", "session-helper")
        self.core.audit(entry)

    # -- routing ---------------------------------------------------------------
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        started = time.monotonic()
        self._cached_body = None
        parsed = urlparse(self.path)
        route = parsed.path
        if not route.startswith("/v1/"):
            self._send_json(404, {"error": "not found"})
            return
        ip = self._client_ip()
        if not self._authorized():
            blocked_for = self.core.auth_blocked(ip)
            if blocked_for > 0:
                self.core.note_auth_failure(ip)   # extends the block
                self._audit_request("auth failed (rate limited)", 429, started,
                                    auth_failed=True,
                                    extra={"rate_limited": True})
                self._send_json(429, {"error": "too many failed auth attempts",
                                      "retry_after_s": round(blocked_for, 1)})
                return
            self.core.note_auth_failure(ip)
            self._audit_request("auth failed", 401, started, auth_failed=True)
            self._send_json(401, {"error": "unauthorized"})
            return
        self.core.note_auth_success(ip)
        try:
            status, obj, summary, audit_kw = self._route(method, route, parsed)
            self._audit_request(summary, status, started, **audit_kw)
            self._send_json(status, obj)
        except PlatformUnavailable as exc:
            self._audit_request(f"unavailable: {exc}", 501, started)
            self._send_json(501, {"error": str(exc), "platform_limited": True})
        except FileNotFoundError as exc:
            self._audit_request(f"not found: {exc}", 404, started)
            self._send_json(404, {"error": str(exc)})
        except ValueError as exc:
            self._audit_request(f"bad request: {exc}", 400, started)
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # keep the server alive on handler bugs
            self._audit_request(f"server error: {exc}", 500, started)
            self._send_json(500, {"error": f"internal error: {exc}"})

    def _route(self, method: str, route: str, parsed):
        """Returns (status, obj, summary, audit_kwargs)."""
        core = self.core
        job_match = re.fullmatch(r"/v1/jobs/([0-9a-f]+)(?:/(cancel))?", route)
        proc_match = re.fullmatch(r"/v1/processes/([0-9a-f]+)(?:/(kill))?", route)
        sess_match = re.fullmatch(
            r"/v1/sessions/([0-9a-f]+)(?:/(input|close))?", route)
        upload_match = re.fullmatch(
            r"/v1/file/upload/([0-9a-f]+)(?:/(complete))?", route)
        chunk_match = re.fullmatch(r"/v1/file/upload/([0-9a-f]+)/(\d+)", route)

        # -- interactive-session broker (desktop routes) ----------------
        # Screenshot / input / UIA / clipboard act on the interactive
        # desktop: broker them to the session helper when one is
        # registered, and refuse them (501) from session 0 without
        # one. GUI spawns and helper-owned process records follow
        # the same rule. Everything else is served locally as usual.
        desktop_direct = (
            (method == "GET" and route == "/v1/screenshot")
            or (method == "POST" and route == "/v1/input")
            or (method == "POST" and route == "/v1/uia")
            or (route == "/v1/clipboard" and method in ("GET", "POST")))
        if desktop_direct:
            body = self._body_bytes(MAX_BODY_BYTES) \
                if method in ("POST", "PUT") else None
            proxied = self._broker_or_block(method, route, parsed, body)
            if proxied is not None:
                return proxied
        if method == "POST" and route == "/v1/processes":
            raw = self._body_bytes(MAX_BODY_BYTES)
            try:
                peek = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                peek = {}
            if isinstance(peek, dict) and peek.get("gui") is True:
                proxied = self._broker_or_block(
                    method, route, parsed, raw)
                if proxied is not None:
                    return proxied
        if proc_match and ((method == "GET" and not proc_match.group(2))
                           or (method == "POST"
                               and proc_match.group(2) == "kill")):
            with core._processes_lock:
                known_locally = proc_match.group(1) in core.processes
            if not known_locally:
                reg = core.session_helper_registration()
                if reg is not None:
                    body = self._body_bytes(MAX_BODY_BYTES) \
                        if method in ("POST", "PUT") else None
                    return self._proxy_request(
                        method, route, parsed, body, reg)

        if method == "GET" and route == "/v1/status":
            obj = self._status_obj()
            return 200, obj, "status", {}
        if method == "POST" and route == "/v1/exec":
            return self._handle_exec_submit()
        if method == "GET" and route == "/v1/jobs":
            with core._jobs_lock:
                jobs = sorted(core.jobs.values(),
                              key=lambda j: j.started_wall, reverse=True)
            listing = [j.describe() for j in jobs[:100]]
            return 200, {"jobs": listing}, f"jobs list ({len(listing)})", {}
        if method == "GET" and job_match and not job_match.group(2):
            return self._handle_job_get(job_match.group(1), parsed)
        if method == "POST" and job_match and job_match.group(2) == "cancel":
            return self._handle_job_cancel(job_match.group(1))
        if method == "POST" and route == "/v1/wol":
            return self._handle_wol()
        if method == "POST" and route == "/v1/processes":
            return self._handle_process_spawn()
        if method == "GET" and route == "/v1/processes":
            with core._processes_lock:
                procs = list(core.processes.values())
            listing = [p.describe() for p in procs]
            # Brokered GUI spawns live in the helper's registry;
            # merge them in so the listing covers every process
            # this agent can inspect or kill.
            listing += self._helper_processes()
            return 200, {"processes": listing}, \
                f"processes list ({len(listing)})", {}
        if method == "GET" and proc_match and not proc_match.group(2):
            return self._handle_process_get(proc_match.group(1), parsed)
        if method == "POST" and proc_match and proc_match.group(2) == "kill":
            return self._handle_process_kill(proc_match.group(1))
        if method == "POST" and route == "/v1/sessions":
            return self._handle_session_open()
        if method == "GET" and sess_match and not sess_match.group(2):
            return self._handle_session_get(sess_match.group(1), parsed)
        if method == "POST" and sess_match and sess_match.group(2) == "input":
            return self._handle_session_input(sess_match.group(1))
        if method == "POST" and sess_match and sess_match.group(2) == "close":
            return self._handle_session_close(sess_match.group(1))
        if method == "GET" and route == "/v1/screenshot":
            return self._handle_screenshot(parsed)
        if method == "POST" and route == "/v1/input":
            return self._handle_input()
        if method == "POST" and route == "/v1/uia":
            return self._handle_uia()
        if method == "GET" and route == "/v1/clipboard":
            text = clipboard_get()
            return 200, {"text": text}, f"clipboard get ({len(text)} chars)", {}
        if method == "POST" and route == "/v1/clipboard":
            payload = self._read_json_body()
            text = payload.get("text")
            if not isinstance(text, str):
                raise ValueError("field 'text' (string) is required")
            clipboard_set(text)
            return 200, {"ok": True, "chars": len(text)}, \
                f"clipboard set ({len(text)} chars)", {}
        if method == "GET" and route == "/v1/file/list":
            return self._handle_file_list(parsed)
        if method == "GET" and route == "/v1/file/tree":
            return self._handle_file_tree(parsed)
        if method == "GET" and route == "/v1/file/get":
            return self._handle_file_get(parsed)
        if method == "GET" and route == "/v1/file/hash":
            return self._handle_file_hash(parsed)
        if method == "POST" and route == "/v1/file/put":
            return self._handle_file_put()
        if method == "POST" and route == "/v1/file/upload/start":
            return self._handle_upload_start()
        if method == "PUT" and chunk_match:
            return self._handle_upload_chunk(chunk_match.group(1),
                                             int(chunk_match.group(2)))
        if method == "GET" and upload_match and not upload_match.group(2):
            return self._handle_upload_get(upload_match.group(1))
        if method == "POST" and upload_match and upload_match.group(2) == "complete":
            return self._handle_upload_complete(upload_match.group(1))
        if method == "DELETE" and upload_match and not upload_match.group(2):
            return self._handle_upload_delete(upload_match.group(1))
        if method == "POST" and route == "/v1/file/mkdir":
            return self._handle_mkdir()
        if method == "POST" and route == "/v1/file/move":
            return self._handle_move()
        if method == "POST" and route == "/v1/file/delete":
            return self._handle_delete()
        if method == "GET" and route == "/v1/audit/tail":
            qs = parse_qs(parsed.query)
            n = int(qs.get("n", ["50"])[0])
            entries = core.audit_tail(n)
            return 200, {"entries": entries, "count": len(entries)}, \
                f"audit tail ({len(entries)})", {}
        if method == "GET" and route == "/v1/audit":
            # v1.2 §2: read access to the agent's OWN audit file.
            # No path parameter exists by design — the file read is
            # always core.audit_path, so the request cannot be aimed
            # at any other file. The read itself is audited by the
            # generic request entry written in _dispatch.
            qs = parse_qs(parsed.query)
            since_raw = qs.get("since", [None])[0]
            limit_raw = qs.get("limit", ["200"])[0]
            try:
                since = float(since_raw) if since_raw else None
                limit = int(limit_raw)
            except (TypeError, ValueError):
                raise ValueError("since/limit must be numbers")
            result = core.audit_read(since, limit)
            return 200, result, f"audit read ({result['count']} entries)", {}
        if method == "GET" and route == "/v1/update/status":
            import bridge_update
            obj = bridge_update.update_status(core.state_dir)
            obj["current_version"] = VERSION
            return 200, obj, "update status", {}
        if method == "POST" and route == "/v1/update/stage":
            return self._handle_update_stage()
        return 404, {"error": "not found"}, "no route", {}

    # -- session broker ---------------------------------------------------
    def _broker_or_block(self, method: str, route: str, parsed,
                         body: bytes | None):
        """Route a desktop request: proxy it to the session helper
        when one is registered, raise PlatformUnavailable when this
        agent is in session 0 without one, or return None to serve
        it locally (this agent IS in the interactive session)."""
        core = self.core
        reg = core.session_helper_registration()
        if reg is not None:
            return self._proxy_request(method, route, parsed, body, reg)
        reason = core.desktop_unavailable_reason()
        if reason is not None:
            raise PlatformUnavailable(reason)
        return None

    def _proxy_request(self, method: str, route: str, parsed,
                       body: bytes | None, reg: dict):
        """Forward a desktop route to the interactive session helper
        and return its response verbatim. The helper re-checks the
        same token itself; both sides audit the request (this side
        marks its entry via=session-broker)."""
        url = f"http://127.0.0.1:{reg['port']}{route}"
        if parsed.query:
            url += f"?{parsed.query}"
        headers = {"Authorization": f"Bearer {self.core.token}"}
        data = None
        if method in ("POST", "PUT"):
            data = body if body is not None else b""
            headers["Content-Type"] = \
                self.headers.get("Content-Type") or "application/json"
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=70) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        except (urllib.error.URLError, OSError) as exc:
            raise PlatformUnavailable(
                f"session helper registered but not answering: {exc}")
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            obj = {"error": "session helper returned a non-JSON response"}
            status = 502
        return status, obj, \
            f"{route} via session helper (port {reg['port']})", \
            {"extra": {"via": "session-broker"}}

    def _fetch_helper_processes(self, reg: dict,
                                timeout_s: float) -> list[dict] | None:
        """One bounded fetch of the helper's process listing.

        Returns the merged records (tagged via=session-helper), or
        None when the helper did not answer within timeout_s —
        unreachable, hung, or a bad payload. Callers decide what a
        failure means; the distinction from an empty list matters
        (a live helper with no processes is a success)."""
        url = f"http://127.0.0.1:{reg['port']}/v1/processes"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.core.token}"},
            method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                obj = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, UnicodeDecodeError,
                json.JSONDecodeError):
            return None
        procs = obj.get("processes") if isinstance(obj, dict) \
            else None
        if not isinstance(procs, list):
            return None
        merged = []
        for item in procs:
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("via", "session-helper")
                merged.append(item)
        return merged

    def _note_helper_merge(self, reg: dict,
                           records: list[dict] | None) -> None:
        """Record a helper-merge outcome for the status path."""
        core = self.core
        with core._helper_merge_lock:
            if records is None:
                core._helper_merge_failed = (time.monotonic(),
                                             reg["port"])
            else:
                core._helper_merge_cache = (time.monotonic(),
                                            reg["port"], records)
                core._helper_merge_failed = None

    def _cached_helper_merge(self, reg: dict) -> list[dict] | None:
        """The last-known merge for THIS registration, if any."""
        with self.core._helper_merge_lock:
            cache = self.core._helper_merge_cache
        if cache is not None and cache[1] == reg["port"]:
            return cache[2]
        return None

    def _helper_processes(self) -> list[dict]:
        """Process records owned by the registered session helper.

        GUI spawns brokered to the helper live ONLY in the helper's
        registry (inspect/kill by id already forward there); without
        this merge the public listing and the status counts showed
        only local records, so clients could not rediscover a
        brokered process after losing the spawn response (Codex
        PR #47 finding). Records are tagged via=session-helper.
        Returns [] when no helper is registered or it does not
        answer — a listing must never fail because the helper is
        gone; the local records are still the truth locally. The
        listing keeps the generous fetch budget; /v1/status uses
        _helper_processes_for_status instead (see there why).
        """
        core = self.core
        reg = core.session_helper_registration()
        if reg is None:
            return []
        records = self._fetch_helper_processes(reg, timeout_s=5)
        self._note_helper_merge(reg, records)
        if records is not None:
            return records
        cached = self._cached_helper_merge(reg)
        return cached if cached is not None else []

    def _helper_processes_for_status(self) -> list[dict]:
        """The helper merge for /v1/status, bounded by its readers.

        Avatar status readers time out at 1.5 s and the
        supervisor's update health check at 3 s — a helper that is
        alive but hung must not make a healthy agent look dead to
        them (it once could: status shared the listing's 5 s fetch
        synchronously — Codex PR #47 finding). So this path serves
        a fresh-enough cached merge without touching the network,
        backs off briefly after a failed fetch instead of stalling
        every poll, and otherwise makes ONE fetch attempt with a
        sub-second timeout. Worst case the status counts lag the
        helper's registry by a few seconds; the degradation stays
        local to the counts — status itself always answers.
        """
        core = self.core
        reg = core.session_helper_registration()
        if reg is None:
            return []
        now = time.monotonic()
        with core._helper_merge_lock:
            cache = core._helper_merge_cache
            failed = core._helper_merge_failed
        if cache is not None and cache[1] == reg["port"] \
                and now - cache[0] < HELPER_MERGE_CACHE_S:
            return cache[2]
        if failed is not None and failed[1] == reg["port"] \
                and now - failed[0] < HELPER_MERGE_RETRY_S:
            cached = self._cached_helper_merge(reg)
            return cached if cached is not None else []
        records = self._fetch_helper_processes(
            reg, timeout_s=HELPER_STATUS_TIMEOUT_S)
        self._note_helper_merge(reg, records)
        if records is not None:
            return records
        cached = self._cached_helper_merge(reg)
        return cached if cached is not None else []

    # -- status ------------------------------------------------------------------
    def _status_obj(self) -> dict:
        core = self.core
        caps, limited = capability_lists()
        with core._jobs_lock:
            jobs_running = sum(1 for j in core.jobs.values()
                               if j.state in ("queued", "running"))
            jobs_total = len(core.jobs)
        with core._processes_lock:
            procs_alive = sum(1 for p in core.processes.values() if p.alive())
            procs_total = len(core.processes)
        # Helper-owned (brokered) processes count too: without them
        # the avatar reported idle while a GUI app it brokered was
        # still running. The merge goes through the deadline-bound
        # status path, never the listing's 5 s fetch.
        helper_procs = self._helper_processes_for_status()
        procs_total += len(helper_procs)
        procs_alive += sum(1 for p in helper_procs if p.get("alive"))
        with core._sessions_lock:
            sessions_open = sum(1 for s in core.sessions.values()
                                if s.state == "running")
        try:
            usage = shutil.disk_usage(str(core.file_root))
            disk = {"total_bytes": usage.total, "free_bytes": usage.free}
        except OSError:
            disk = {"total_bytes": None, "free_bytes": None}
        try:
            audit_bytes = core.audit_path.stat().st_size
        except OSError:
            audit_bytes = 0
        return {
            "agent": AGENT_NAME,
            "version": VERSION,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uptime_s": round(time.time() - core.started_at, 3),
            "shell_default": default_shell(),
            "file_root": str(core.file_root),
            "file_roots": {name: str(p) for name, p in core.roots.items()},
            "capabilities": caps,
            "platform_limited": limited,
            "jobs_running": jobs_running,
            "jobs_total": jobs_total,
            "processes_alive": procs_alive,
            "processes_tracked": procs_total,
            "sessions_open": sessions_open,
            "uac_prompt": core.uac.snapshot(),
            "session_helper": {
                "registered":
                    core.session_helper_registration() is not None,
                "session_id": current_session_id(),
            },
            "disk": disk,
            "audit_log": str(core.audit_path),
            "audit_bytes": audit_bytes,
        }

    # -- exec / jobs ---------------------------------------------------------------
    def _handle_exec_submit(self):
        payload = self._read_json_body()
        # v1.2 §1: the UAC pre-flight assessment is computed BEFORE
        # anything executes, and rides on the response either way.
        uac = assess_uac(self.core, str(payload.get("command") or ""))
        if payload.get("require_no_uac") and uac["likely"]:
            # Refused: nothing is submitted, nothing executes. The
            # refusal itself is a normal audited request (409).
            return 409, {"error": "uac_likely", "uac": uac}, \
                f"exec refused, UAC likely: " \
                f"{str(payload.get('command') or '')[:500]}", {}
        job = submit_job(self.core, payload)
        wait_s = payload.get("wait_s")
        if payload.get("wait") is True:
            wait_s = job.timeout if job.timeout is not None else 3600.0
        audit_kw: dict = {"job_id": job.id}
        if wait_s is not None:
            try:
                wait_s = float(wait_s)
            except (TypeError, ValueError):
                raise ValueError("wait_s must be a number")
            job.wait(max(0.0, wait_s))
            obj = job.output(0, 0, int(self.core.cfg["max_output_bytes"]))
            obj["waited"] = True
            obj["uac"] = uac
            if job.state in ("done", "failed", "killed"):
                out_b, _ = job.stdout.read(0, job.stdout.total)
                audit_kw["exit_code"] = job.exit_code
                audit_kw["output_sha256"] = sha256_hex(out_b)
            summary = f"exec[{job.shell}]: {job.command_summary} (job {job.id})"
            return 200, obj, summary, audit_kw
        obj = job.describe()
        obj["uac"] = uac
        obj["note"] = "job submitted; poll GET /v1/jobs/{id}"
        return 202, obj, f"exec submit[{job.shell}]: {job.command_summary}", audit_kw

    def _handle_job_get(self, job_id: str, parsed):
        core = self.core
        with core._jobs_lock:
            job = core.jobs.get(job_id)
        if job is None:
            return 404, {"error": f"no such job: {job_id}"}, f"job {job_id} (missing)", {}
        qs = parse_qs(parsed.query)
        try:
            out_off = int(qs.get("stdout_offset", ["0"])[0])
            err_off = int(qs.get("stderr_offset", ["0"])[0])
            max_b = int(qs.get("max_bytes",
                               [str(int(core.cfg["max_output_bytes"]))])[0])
        except ValueError:
            raise ValueError("offset/max_bytes must be integers")
        obj = job.output(max(0, out_off), max(0, err_off),
                         max(1, min(max_b, 16 * 1024 * 1024)))
        return 200, obj, f"job {job_id} poll", {"job_id": job_id}

    def _handle_job_cancel(self, job_id: str):
        core = self.core
        with core._jobs_lock:
            job = core.jobs.get(job_id)
        if job is None:
            return 404, {"error": f"no such job: {job_id}"}, \
                f"job {job_id} cancel (missing)", {}
        cancelled = job.cancel()
        return 200, {"job_id": job_id, "cancelled": cancelled,
                     "state": job.state}, \
            f"job {job_id} cancel", {"job_id": job_id}

    # -- detached processes -----------------------------------------------------------
    def _handle_wol(self):
        payload = self._read_json_body()
        # ValueError from validation becomes a 400 in the router.
        mac, broadcast, port = validate_wol_payload(payload)
        try:
            result = send_magic_packet(mac, broadcast, port)
        except OSError as exc:
            return 500, {"error": f"wake-on-LAN send failed: {exc}"}, \
                f"wol send failed -> {mac}", {}
        return 200, result, \
            f"wol magic packet -> {mac} via {broadcast}:{port}", {}

    def _handle_process_spawn(self):
        payload = self._read_json_body()
        record = spawn_detached(self.core, payload)
        return 201, record.describe(), \
            f"process spawn: {record.command_summary} (pid {record.pid})", {}

    def _handle_process_get(self, proc_id: str, parsed):
        core = self.core
        with core._processes_lock:
            record = core.processes.get(proc_id)
        if record is None:
            return 404, {"error": f"no such process: {proc_id}"}, \
                f"process {proc_id} (missing)", {}
        qs = parse_qs(parsed.query)
        try:
            tail = int(qs.get("tail_bytes", ["0"])[0])
        except ValueError:
            raise ValueError("tail_bytes must be an integer")
        return 200, record.describe(tail_bytes=max(0, min(tail, 1024 * 1024))), \
            f"process {proc_id} inspect", {}

    def _handle_process_kill(self, proc_id: str):
        core = self.core
        with core._processes_lock:
            record = core.processes.get(proc_id)
        if record is None:
            return 404, {"error": f"no such process: {proc_id}"}, \
                f"process {proc_id} kill (missing)", {}
        was_alive = record.alive()
        if was_alive:
            if record.proc is not None:
                kill_tree(record.proc)
            else:
                kill_pid_tree(record.pid)
        return 200, {"process_id": proc_id, "pid": record.pid,
                     "killed": was_alive, "alive": record.alive()}, \
            f"process {proc_id} kill", {}

    # -- sessions -----------------------------------------------------------------
    def _handle_session_open(self):
        payload = self._read_json_body()
        shell = payload.get("shell") or default_shell()
        if shell not in ("powershell", "cmd", "posix"):
            raise ValueError(f"unknown shell: {shell!r}")
        cwd = payload.get("cwd")
        if cwd is not None:
            if not isinstance(cwd, str) or not Path(cwd).is_dir():
                raise ValueError(f"cwd does not exist: {cwd!r}")
        else:
            cwd = str(agent_dir())
        env = dict(os.environ)
        extra = payload.get("env")
        if extra is not None:
            if not isinstance(extra, dict):
                raise ValueError("env must be an object of string values")
            for k, v in extra.items():
                env[str(k)] = str(v)
        session = Session(self.core, shell, cwd, env)
        with self.core._sessions_lock:
            self.core.sessions[session.id] = session
        return 201, session.describe(), f"session open ({shell})", {}

    def _get_session(self, session_id: str) -> Session:
        with self.core._sessions_lock:
            session = self.core.sessions.get(session_id)
        if session is None:
            raise ValueError(f"no such session: {session_id}")
        return session

    def _handle_session_get(self, session_id: str, parsed):
        session = self._get_session(session_id)
        qs = parse_qs(parsed.query)
        try:
            offset = int(qs.get("offset", ["0"])[0])
            max_b = int(qs.get("max_bytes",
                               [str(int(self.core.cfg["max_output_bytes"]))])[0])
        except ValueError:
            raise ValueError("offset/max_bytes must be integers")
        return 200, session.describe(offset=max(0, offset),
                                     max_bytes=max(1, max_b)), \
            f"session {session_id} read", {}

    def _handle_session_input(self, session_id: str):
        session = self._get_session(session_id)
        payload = self._read_json_body()
        if payload.get("close_stdin"):
            session.close_stdin()
            return 200, {"session_id": session_id, "ok": True}, \
                f"session {session_id} stdin closed", {}
        if isinstance(payload.get("data_b64"), str):
            data = base64.b64decode(payload["data_b64"], validate=True)
        elif isinstance(payload.get("data"), str):
            data = payload["data"].encode("utf-8")
        else:
            raise ValueError("field 'data' or 'data_b64' is required")
        session.send(data)
        return 200, {"session_id": session_id, "ok": True,
                     "bytes": len(data)}, f"session {session_id} input", {}

    def _handle_session_close(self, session_id: str):
        session = self._get_session(session_id)
        session.close()
        return 200, {"session_id": session_id, "state": session.state}, \
            f"session {session_id} close", {}

    # -- eyes and hands ------------------------------------------------------------
    def _handle_screenshot(self, parsed):
        qs = parse_qs(parsed.query)
        fmt = (qs.get("format", ["png"])[0]).lower()
        if fmt not in ("png", "bmp"):
            raise ValueError("format must be 'png' or 'bmp'")
        region = None
        if "region" in qs:
            parts = qs["region"][0].split(",")
            if len(parts) != 4:
                raise ValueError("region must be 'x,y,w,h'")
            try:
                region = tuple(int(p) for p in parts)  # type: ignore[assignment]
            except ValueError:
                raise ValueError("region must be 'x,y,w,h' (integers)")
        monitor = None
        if "monitor" in qs:
            try:
                monitor = int(qs["monitor"][0])
            except ValueError:
                raise ValueError("monitor must be an integer")
        w, h, bgra = capture_screen(region=region, monitor=monitor)
        if fmt == "png":
            data = encode_png(w, h, bgra_to_rgba(bgra))
        else:
            data = encode_bmp(w, h, bgra)
        obj = {
            "format": fmt, "width": w, "height": h, "size": len(data),
            "sha256": sha256_hex(data),
            "content_b64": base64.b64encode(data).decode("ascii"),
        }
        return 200, obj, f"screenshot {w}x{h} {fmt} size={len(data)}", {}

    def _handle_input(self):
        payload = self._read_json_body()
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("field 'actions' (non-empty list) is required")
        if len(actions) > 200:
            raise ValueError("too many actions in one request (max 200)")
        results = inject_input(actions)
        kinds = ",".join(str(a.get("type")) for a in actions[:10])
        return 200, {"ok": True, "results": results}, f"input: {kinds}", {}

    def _handle_uia(self):
        payload = self._read_json_body()
        obj = run_uia(self.core, payload)
        return 200, obj, f"uia {payload.get('action')}", {}

    # -- files ---------------------------------------------------------------------
    def _root_arg(self, payload: dict | None = None, parsed=None) -> str | None:
        if payload is not None and payload.get("root"):
            return str(payload["root"])
        if parsed is not None:
            qs = parse_qs(parsed.query)
            values = qs.get("root")
            if values:
                return values[0]
        return None

    def _query_path(self, parsed) -> str:
        qs = parse_qs(parsed.query)
        values = qs.get("path")
        return values[0] if values else "."

    def _handle_file_list(self, parsed):
        rel = self._query_path(parsed)
        root_name = self._root_arg(parsed=parsed)
        target = self.core.resolve_in_root(root_name, rel)
        if not target.exists():
            return 404, {"error": f"no such path: {rel}"}, f"list {rel} (missing)", {}
        if not target.is_dir():
            return 400, {"error": f"not a directory: {rel}"}, f"list {rel} (not dir)", {}
        entries = []
        for child in target.iterdir():
            is_dir = child.is_dir()
            entries.append({
                "name": child.name,
                "type": "dir" if is_dir else "file",
                "size": None if is_dir else child.stat().st_size,
            })
        entries.sort(key=lambda e: e["name"])
        return 200, {"path": self.core.rel_display(target, root_name),
                     "root": root_name or self.core.default_root_name,
                     "entries": entries}, f"list {rel} ({len(entries)} entries)", {}

    def _handle_file_tree(self, parsed):
        rel = self._query_path(parsed)
        root_name = self._root_arg(parsed=parsed)
        qs = parse_qs(parsed.query)
        try:
            max_depth = int(qs.get("max_depth", ["6"])[0])
            max_entries = int(qs.get("max_entries", ["2000"])[0])
        except ValueError:
            raise ValueError("max_depth/max_entries must be integers")
        target = self.core.resolve_in_root(root_name, rel)
        if not target.exists():
            return 404, {"error": f"no such path: {rel}"}, f"tree {rel} (missing)", {}
        root_resolved = self.core.root_path(root_name).resolve()
        counter = {"n": 0, "truncated": False}

        def build(node: Path, depth: int) -> dict:
            counter["n"] += 1
            is_dir = node.is_dir()
            item = {"name": node.name or self.core.rel_display(node, root_name),
                    "type": "dir" if is_dir else "file",
                    "size": None if is_dir else node.stat().st_size}
            if is_dir and depth < max_depth:
                children = []
                for child in sorted(node.iterdir(), key=lambda c: c.name):
                    if counter["n"] >= max_entries:
                        counter["truncated"] = True
                        break
                    # Containment applies to every descendant, not
                    # just the requested path: a symlink (or junction)
                    # whose target escapes the file root is skipped —
                    # never listed, never followed (AGENTS.md §10).
                    try:
                        resolved = child.resolve()
                    except OSError:
                        continue
                    if resolved != root_resolved and \
                            root_resolved not in resolved.parents:
                        continue
                    children.append(build(child, depth + 1))
                item["children"] = children
            elif is_dir:
                counter["truncated"] = True
            return item

        tree = build(target, 0)
        return 200, {"path": self.core.rel_display(target, root_name),
                     "root": root_name or self.core.default_root_name,
                     "tree": tree, "truncated": counter["truncated"]}, \
            f"tree {rel} ({counter['n']} nodes)", {}

    def _handle_file_get(self, parsed):
        rel = self._query_path(parsed)
        root_name = self._root_arg(parsed=parsed)
        target = self.core.resolve_in_root(root_name, rel)
        qs = parse_qs(parsed.query)
        if not target.exists() or not target.is_file():
            return 404, {"error": f"no such file: {rel}"}, f"get {rel} (missing)", {}
        size = target.stat().st_size
        try:
            offset = int(qs.get("offset", ["0"])[0])
            length_raw = qs.get("length", [None])[0]
            length = int(length_raw) if length_raw is not None else None
        except ValueError:
            raise ValueError("offset/length must be integers")
        ranged = "offset" in qs or "length" in qs
        if not ranged:
            if size > MAX_GET_BYTES:
                return 413, {"error": f"file too large to transfer whole "
                                       f"({size} bytes > {MAX_GET_BYTES}); "
                                       f"use offset/length ranges"}, \
                    f"get {rel} (too large)", {}
            offset, length = 0, size
        offset = max(0, min(offset, size))
        if length is None:
            length = size - offset
        length = max(0, min(length, size - offset, MAX_RANGE_BYTES))
        with open(target, "rb") as fh:
            fh.seek(offset)
            data = fh.read(length)
        obj = {
            "path": self.core.rel_display(target, root_name),
            "root": root_name or self.core.default_root_name,
            "size": len(data),
            "total_size": size,
            "offset": offset,
            "eof": offset + len(data) >= size,
            "sha256": sha256_hex(data),
            "content_b64": base64.b64encode(data).decode("ascii"),
        }
        return 200, obj, f"get {rel} @{offset}+{len(data)} sha256={obj['sha256']}", {}

    def _handle_file_hash(self, parsed):
        rel = self._query_path(parsed)
        root_name = self._root_arg(parsed=parsed)
        target = self.core.resolve_in_root(root_name, rel)
        if not target.exists() or not target.is_file():
            return 404, {"error": f"no such file: {rel}"}, f"hash {rel} (missing)", {}
        digest = hashlib.sha256()
        size = 0
        with open(target, "rb") as fh:
            while True:
                block = fh.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
                size += len(block)
        hex_digest = digest.hexdigest()
        return 200, {"path": self.core.rel_display(target, root_name),
                     "root": root_name or self.core.default_root_name,
                     "size": size, "sha256": hex_digest}, \
            f"hash {rel} size={size} sha256={hex_digest}", {}

    def _handle_file_put(self):
        payload = self._read_json_body()
        rel = payload.get("path")
        root_name = self._root_arg(payload)
        if not isinstance(rel, str) or not rel.strip() or rel.strip() in (".", "./"):
            return 400, {"error": "field 'path' (relative file path) is required"}, \
                "put (no path)", {}
        content_b64 = payload.get("content_b64")
        if not isinstance(content_b64, str):
            return 400, {"error": "field 'content_b64' (string) is required"}, \
                f"put {rel} (no content)", {}
        try:
            data = base64.b64decode(content_b64, validate=True)
        except (ValueError, TypeError):
            return 400, {"error": "content_b64 is not valid base64"}, \
                f"put {rel} (bad b64)", {}
        target = self.core.resolve_in_root(root_name, rel)
        if target == self.core.root_path(root_name).resolve():
            return 400, {"error": "path must name a file, not the root"}, \
                f"put {rel} (root)", {}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        digest = sha256_hex(data)
        obj = {"path": self.core.rel_display(target, root_name),
               "root": root_name or self.core.default_root_name,
               "size": len(data), "sha256": digest}
        return 200, obj, f"put {rel} size={len(data)} sha256={digest}", {}

    # -- chunked uploads -------------------------------------------------------------
    def _handle_upload_start(self):
        payload = self._read_json_body()
        rel = payload.get("path")
        root_name = self._root_arg(payload)
        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("field 'path' (relative file path) is required")
        try:
            size = int(payload.get("size"))
        except (TypeError, ValueError):
            raise ValueError("field 'size' (integer bytes) is required")
        if size < 0:
            raise ValueError("size must be >= 0")
        expected = payload.get("sha256")
        if expected is not None and not re.fullmatch(r"[0-9a-fA-F]{64}",
                                                     str(expected)):
            raise ValueError("sha256 must be 64 hex characters")
        # Validate the destination now so failures surface before data flows.
        self.core.resolve_in_root(root_name, rel)
        # The client may request a chunk size (small chunks make tests
        # and resumable transfers over slow links practical); clamp it.
        try:
            chunk_size = int(payload.get("chunk_bytes")
                             or payload.get("chunk_size") or CHUNK_SIZE)
        except (TypeError, ValueError):
            raise ValueError("chunk_bytes must be an integer")
        chunk_size = max(64 * 1024, min(16 * 1024 * 1024, chunk_size))
        upload = Upload(self.core, {
            "id": uuid.uuid4().hex[:12],
            "root": root_name, "path": rel, "size": size,
            "sha256": str(expected).lower() if expected else None,
            "chunk_size": chunk_size, "created": time.time(),
        })
        upload.save_meta()
        with self.core._uploads_lock:
            self.core.uploads[upload.id] = upload
        return 201, upload.describe(), \
            f"upload start {rel} size={size} id={upload.id}", {}

    def _get_upload(self, upload_id: str) -> Upload:
        with self.core._uploads_lock:
            upload = self.core.uploads.get(upload_id)
        if upload is None:
            raise FileNotFoundError(f"no such upload: {upload_id}")
        return upload

    def _handle_upload_chunk(self, upload_id: str, index: int):
        upload = self._get_upload(upload_id)
        if index < 0 or index >= upload.chunk_count:
            raise ValueError(f"chunk index out of range: {index}")
        data = self._read_raw_body(MAX_CHUNK_BYTES)
        expected_len = (upload.size - index * upload.chunk_size
                        if index == upload.chunk_count - 1
                        else upload.chunk_size)
        if upload.size == 0:
            expected_len = 0
        if len(data) != expected_len:
            raise ValueError(f"chunk {index} must be {expected_len} bytes, "
                             f"got {len(data)}")
        part = upload.dir / f"{index}.part"
        part.write_bytes(data)
        return 200, upload.describe(), \
            f"upload {upload_id} chunk {index} ({len(data)} bytes)", {}

    def _handle_upload_get(self, upload_id: str):
        upload = self._get_upload(upload_id)
        return 200, upload.describe(), f"upload {upload_id} status", {}

    def _handle_upload_complete(self, upload_id: str):
        upload = self._get_upload(upload_id)
        target, digest = upload.complete()
        root_name = upload.root_name
        obj = {"path": self.core.rel_display(target, root_name),
               "root": root_name or self.core.default_root_name,
               "size": upload.size, "sha256": digest}
        return 200, obj, \
            f"upload {upload_id} complete size={upload.size} sha256={digest}", {}

    def _handle_upload_delete(self, upload_id: str):
        upload = self._get_upload(upload_id)
        upload.discard()
        return 200, {"upload_id": upload_id, "discarded": True}, \
            f"upload {upload_id} discarded", {}

    # -- recursive file ops ------------------------------------------------------------
    def _handle_mkdir(self):
        payload = self._read_json_body()
        rel = payload.get("path")
        root_name = self._root_arg(payload)
        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("field 'path' is required")
        target = self.core.resolve_in_root(root_name, rel)
        target.mkdir(parents=True, exist_ok=True)
        return 200, {"path": self.core.rel_display(target, root_name),
                     "root": root_name or self.core.default_root_name,
                     "created": True}, f"mkdir {rel}", {}

    def _handle_move(self):
        payload = self._read_json_body()
        src_rel = payload.get("from")
        dst_rel = payload.get("to")
        if not isinstance(src_rel, str) or not isinstance(dst_rel, str):
            raise ValueError("fields 'from' and 'to' are required")
        src_root = payload.get("from_root") or payload.get("root")
        dst_root = payload.get("to_root") or payload.get("root")
        src = self.core.resolve_in_root(src_root, src_rel)
        dst = self.core.resolve_in_root(dst_root, dst_rel)
        if not src.exists():
            return 404, {"error": f"no such path: {src_rel}"}, \
                f"move {src_rel} (missing)", {}
        if src == self.core.root_path(src_root).resolve():
            raise ValueError("cannot move a file root")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return 200, {"from": src_rel, "to": self.core.rel_display(dst, dst_root),
                     "root": dst_root or self.core.default_root_name}, \
            f"move {src_rel} -> {dst_rel}", {}

    def _handle_delete(self):
        payload = self._read_json_body()
        rel = payload.get("path")
        root_name = self._root_arg(payload)
        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("field 'path' is required")
        target = self.core.resolve_in_root(root_name, rel)
        if target == self.core.root_path(root_name).resolve():
            raise ValueError("cannot delete a file root")
        if not target.exists():
            return 404, {"error": f"no such path: {rel}"}, \
                f"delete {rel} (missing)", {}
        if target.is_dir():
            if not payload.get("recursive"):
                raise ValueError("deleting a directory requires "
                                 "\"recursive\": true")
            shutil.rmtree(target)
        else:
            target.unlink()
        return 200, {"path": rel, "deleted": True}, f"delete {rel}", {}

    # -- self-update staging --------------------------------------------------------------
    def _handle_update_stage(self):
        import bridge_update
        payload = self._read_json_body()
        source = payload.get("source")
        expected = payload.get("sha256")
        version = payload.get("version")
        if not isinstance(source, str) or not source:
            raise ValueError("field 'source' (path or URL) is required")
        if not isinstance(expected, str) or \
                not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ValueError("field 'sha256' (64 hex chars) is required")
        if not isinstance(version, str) or not version:
            raise ValueError("field 'version' is required")
        install_root = agent_dir().parent
        obj = bridge_update.stage_update(
            source=source, expected_sha256=expected.lower(), version=version,
            install_root=install_root, state_dir=self.core.state_dir)
        return 201, obj, f"update staged {version}", {}


def _session_reaper(core: BridgeCore) -> None:
    """Close interactive sessions idle past the configured timeout."""
    idle_limit = float(core.cfg.get("session_idle_timeout_s") or 0)
    if idle_limit <= 0:
        return
    while True:
        time.sleep(30)
        now = time.monotonic()
        with core._sessions_lock:
            sessions = list(core.sessions.values())
        for session in sessions:
            if session.state == "running" and \
                    now - session.last_activity > idle_limit:
                session.close()


def create_server(cfg: dict) -> ThreadingHTTPServer:
    core = BridgeCore(cfg)
    server = ThreadingHTTPServer((str(cfg["host"]), int(cfg["port"])), BridgeHandler)
    server.core = core  # type: ignore[attr-defined]
    server.daemon_threads = True
    core.log_start()
    threading.Thread(target=_session_reaper, args=(core,), daemon=True,
                     name="session-reaper").start()
    if not cfg.get("session_helper"):
        # The session helper shares the audit log but must not run a
        # second UAC watch: one prompt would be audited twice.
        threading.Thread(target=_uac_watch, args=(core,), daemon=True,
                         name="uac-watch").start()
    return server


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="muse-pc-bridge agent")
    parser.add_argument("--config", type=Path, default=agent_dir() / "config.json",
                        help="path to config.json (default: beside this script)")
    parser.add_argument("--init", action="store_true",
                        help="write a fresh config.json with a generated token, "
                             "print the token once, and exit")
    args = parser.parse_args(argv)

    if args.init:
        if args.config.exists():
            print(f"[bridge] {args.config} already exists; refusing to overwrite. "
                  f"Delete it first if you really want a new token.", file=sys.stderr)
            return 1
        token = init_config(args.config)
        print(f"[bridge] Wrote {args.config}")
        print(f"[bridge] Token (shown ONCE — hand it to Muse out-of-band): {token}")
        print("[bridge] Next: edit 'host' in config.json to this PC's Tailscale "
              "100.x IP, then start the agent.")
        return 0

    if not args.config.exists():
        print(f"[bridge] No config at {args.config}. Run with --init first.",
              file=sys.stderr)
        return 1
    cfg = load_config(args.config)
    if not cfg.get("token"):
        print("[bridge] Config has no token. Delete config.json and re-run --init.",
              file=sys.stderr)
        return 1
    if str(cfg["host"]) in ("0.0.0.0", "::"):
        print("=" * 72, file=sys.stderr)
        print("[bridge] *** WARNING: host is a wildcard address — the agent will "
              "listen on ALL interfaces, not just Tailscale. ***", file=sys.stderr)
        print("[bridge] *** Set 'host' to this PC's Tailscale 100.x IP instead "
              "unless you really mean this. ***", file=sys.stderr)
        print("=" * 72, file=sys.stderr)

    server = create_server(cfg)
    # Graceful stop on SIGTERM (POSIX) / SIGBREAK (Windows): the
    # supervisor's normal stop terminates the child process, and
    # without a handler that bypasses the finally block below — the
    # audit log would hold server_start with no server_stop, against
    # the AGENTS.md rule that server start/stop are always audited.
    # Route those signals through the same shutdown path as Ctrl+C.
    def _signal_shutdown(_signum, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    for _sig in (getattr(signal, "SIGTERM", None),
                 getattr(signal, "SIGBREAK", None)):
        if _sig is not None:
            try:
                signal.signal(_sig, _signal_shutdown)
            except (ValueError, OSError):
                pass
    host, port = server.server_address[0], server.server_address[1]
    print(f"[bridge] {AGENT_NAME} {VERSION} listening on http://{host}:{port} "
          f"(shell default: {default_shell()})")
    roots_desc = ", ".join(f"{r['name']}={r['path']}" for r in cfg["roots"])
    print(f"[bridge] File roots: {roots_desc}")
    print(f"[bridge] Audit log: {cfg['audit_log']}")
    print("[bridge] Running. Closing this window (or Ctrl+C) stops the agent — "
          "that is the kill switch.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] Ctrl+C received; shutting down.")
    finally:
        server.core.log_stop()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
