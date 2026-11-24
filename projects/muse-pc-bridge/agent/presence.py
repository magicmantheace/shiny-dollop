#!/usr/bin/env python3
"""Native presence — muse-pc-bridge (durable job runner release).

One snapshot of "what is the owner doing / what is the machine
doing", replacing the ad-hoc staged PowerShell preflight scripts
(the gab*_preflight.ps1 pattern: GetLastInputInfo for idle, a
Win32_Process name scan for games, nvidia-smi for GPU load).

    GET /v1/presence  ->  presence.snapshot()

Fields (each probe is independent; an unavailable probe yields
null plus a note, never a fabricated value):

- `input_idle_s` — seconds since the last keyboard/mouse input
  (Windows GetLastInputInfo). **Windows-only and only meaningful
  in the interactive session**, which is why the route is brokered
  to the session helper like the other desktop routes.
- `foreground` — {pid, title, executable} of the foreground
  window (Windows-only, same session caveat).
- `gaming` / `games` — whether a known game executable is
  running. Steam / Battle.net / other LAUNCHERS do NOT count:
  a launcher sitting open is not gaming. The game list is
  anchored full-name matches (seeded from the owner's own
  preflight script) so launcher/updater processes cannot trip
  it, and the launcher set is checked first regardless.
- `gpu` — {utilization_pct, memory_used_mib, memory_total_mib,
  source} from nvidia-smi when present; null otherwise (no
  stdlib way to read AMD/other GPU load — reported, not faked).

`gpu_contention()` is the shared yield check: the durable job
runner calls it before starting / between stages of a `gpu: true`
job; anything else that needs "is the GPU free" calls the same
function. One implementation, every caller.

All OS probes sit behind small functions so tests can stub the
process list / GPU reading off-Windows.
"""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

IS_WINDOWS = os.name == "nt"

# ---------------------------------------------------------------------------
# Game / launcher detection (pure — unit-tested with stubbed lists)
# ---------------------------------------------------------------------------

# Anchored patterns over the lowercase executable name. Seeded
# from the owner's gab preflight script (Wow, WoW Classic, FFXIV,
# Elden Ring, BG3, Cyberpunk, Witcher, Diablo, Overwatch,
# Valorant, CS2, Dota 2, League of Legends, GTA, RDR2, Starfield,
# Baldur's Gate) and kept to the game's own binaries.
GAME_PATTERNS = tuple(re.compile(p) for p in (
    r"wow(-64)?\.exe",
    r"wowclassic\.exe",
    r"ffxiv(_dx11)?\.exe",
    r"eldenring\.exe",
    r"bg3(_dx11)?\.exe",
    r"cyberpunk2077\.exe",
    r"witcher3\.exe",
    r"diablo( iv|4)?\.exe",
    r"overwatch\.exe",
    r"valorant(-win64-shipping)?\.exe",
    r"cs2\.exe",
    r"dota2\.exe",
    r"league of legends\.exe",
    r"gta5\.exe",
    r"rdr2\.exe",
    r"starfield\.exe",
))

# Launchers, updaters and storefronts: NEVER gaming, checked
# before the game patterns so nothing here can trip them.
LAUNCHER_EXECUTABLES = frozenset({
    "steam.exe", "steamwebhelper.exe", "steamservice.exe",
    "battle.net.exe", "agent.exe", "blizzard launcher.exe",
    "epicgameslauncher.exe", "eadesktop.exe", "origin.exe",
    "upc.exe", "galaxyclient.exe", "galaxyclient helper.exe",
    "riotclientservices.exe", "leagueclient.exe",
    "leagueclientux.exe", "ffxivboot.exe", "ffxivlauncher.exe",
    "playgtav.exe", "rockstar games launcher.exe",
    "rockstargameslauncher.exe", "launcher.exe",
})


def detect_games(process_names, extra_patterns=()) -> list[str]:
    """Sorted executable names (as observed) that are games.

    Pure: takes the process-name list, returns the matches.
    Launcher names are excluded even if a pattern would match.
    """
    patterns = GAME_PATTERNS + tuple(extra_patterns)
    found = set()
    for name in process_names or ():
        if not isinstance(name, str) or not name:
            continue
        lowered = name.lower()
        if lowered in LAUNCHER_EXECUTABLES:
            continue
        if any(p.fullmatch(lowered) for p in patterns):
            found.add(name)
    return sorted(found)


# ---------------------------------------------------------------------------
# OS probes (platform seams)
# ---------------------------------------------------------------------------

def _hidden_kwargs() -> dict:
    """CREATE_NO_WINDOW for probe children on Windows (mirrors
    bridge_agent.hidden_spawn_kwargs; kept local so this module
    stays importable without the agent)."""
    if IS_WINDOWS:
        return {"creationflags": getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def list_process_names() -> list[str]:
    """Executable names of running processes (no arguments).

    Windows: tasklist CSV. POSIX: ps comm. Best-effort: any
    failure returns an empty list (callers treat "no data" as
    "no games seen", and the snapshot notes the probe size).
    """
    try:
        if IS_WINDOWS:
            out = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=20,
                **_hidden_kwargs())
            names = []
            for row in csv.reader(io.StringIO(out.stdout or "")):
                if row and row[0]:
                    names.append(row[0])
            return names
        out = subprocess.run(
            ["ps", "-eo", "comm="],
            capture_output=True, text=True, timeout=20)
        return [line.strip() for line in (out.stdout or "").splitlines()
                if line.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def parse_nvidia_smi(text: str) -> dict | None:
    """Parse one `nvidia-smi --query-gpu=... --format=csv,noheader,
    nounits` line: utilization %, memory used MiB, memory total
    MiB. None when the text holds no reading."""
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        try:
            return {"utilization_pct": int(float(parts[0])),
                    "memory_used_mib": int(float(parts[1])),
                    "memory_total_mib": int(float(parts[2])),
                    "source": "nvidia-smi"}
        except ValueError:
            continue
    return None


def gpu_utilization() -> dict | None:
    """GPU load via nvidia-smi when present; None otherwise."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
            **_hidden_kwargs())
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return parse_nvidia_smi(out.stdout or "")


def input_idle_seconds() -> float | None:
    """Seconds since last input (Windows GetLastInputInfo).

    Windows-only; also only meaningful in the interactive
    session (session 0 has no user input stream). None elsewhere.
    """
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _LastInputInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT),
                        ("dwTime", wintypes.DWORD)]

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        user32.GetLastInputInfo.restype = wintypes.BOOL
        user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LastInputInfo)]
        kernel32.GetTickCount.restype = wintypes.DWORD
        kernel32.GetTickCount.argtypes = []
        info = _LastInputInfo()
        info.cbSize = ctypes.sizeof(_LastInputInfo)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        # DWORD millisecond ticks wrap at ~49.7 days; the unsigned
        # subtraction is the standard wrap-safe difference.
        elapsed_ms = (int(kernel32.GetTickCount()) - int(info.dwTime)) \
            & 0xFFFFFFFF
        return elapsed_ms / 1000.0
    except Exception:
        return None


def foreground_window() -> dict | None:
    """{pid, title, executable} of the foreground window.

    Windows-only, interactive session only (same caveat as idle).
    """
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetForegroundWindow.argtypes = []
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [
            wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        executable = None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if handle:
            try:
                path_buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(
                        handle, 0, path_buf, ctypes.byref(size)):
                    executable = path_buf.value.rsplit("\\", 1)[-1] \
                        or path_buf.value
            finally:
                kernel32.CloseHandle(handle)
        return {"pid": int(pid.value), "title": buf.value,
                "executable": executable}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Snapshot + the shared GPU yield check
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


def snapshot(*, process_names_fn=None, gpu_fn=None, idle_fn=None,
             foreground_fn=None, extra_game_patterns=()) -> dict:
    """Assemble the presence snapshot. Probe functions are
    injectable for tests; defaults are the real OS probes."""
    process_names_fn = process_names_fn or list_process_names
    gpu_fn = gpu_fn or gpu_utilization
    idle_fn = idle_fn or input_idle_seconds
    foreground_fn = foreground_fn or foreground_window
    names = process_names_fn()
    games = detect_games(names, extra_game_patterns)
    gpu = gpu_fn()
    idle = idle_fn()
    foreground = foreground_fn()
    notes = []
    if idle is None:
        notes.append("input idle unavailable (Windows interactive "
                     "session only)")
    if foreground is None:
        notes.append("foreground window unavailable (Windows "
                     "interactive session only)")
    if gpu is None:
        notes.append("GPU load unavailable (nvidia-smi not found "
                     "or failed)")
    if not names:
        notes.append("process list probe returned nothing")
    return {
        "observed_at": _utc_now_iso(),
        "input_idle_s": idle,
        "foreground": foreground,
        "gaming": bool(games),
        "games": games,
        "gpu": gpu,
        "processes_seen": len(names),
        "notes": notes,
    }


def gpu_contention(*, threshold_pct: int = 90, process_names_fn=None,
                   gpu_fn=None, extra_game_patterns=()) -> str | None:
    """Why the GPU is not free right now, or None when it is.

    Contended = a known game executable is running, or GPU
    utilization is at/over `threshold_pct`. This is THE yield
    check: the durable job runner calls it for `gpu: true` jobs;
    nothing else should re-implement it.
    """
    process_names_fn = process_names_fn or list_process_names
    gpu_fn = gpu_fn or gpu_utilization
    games = detect_games(process_names_fn(), extra_game_patterns)
    if games:
        return f"game running: {', '.join(games)}"
    gpu = gpu_fn()
    if gpu is not None and int(gpu.get("utilization_pct") or 0) \
            >= int(threshold_pct):
        return f"GPU utilization {gpu['utilization_pct']}% " \
               f">= threshold {threshold_pct}%"
    return None


if __name__ == "__main__":  # pragma: no cover - manual probe
    import json
    print(json.dumps(snapshot(), indent=2))
    sys.exit(0)
