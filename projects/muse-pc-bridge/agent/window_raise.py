#!/usr/bin/env python3
"""Raise one window — muse-pc-bridge (durable job runner release).

    POST /v1/window/raise  {"pid": 1234}  or  {"title": "Godot"}

Brings ONE window to the foreground. Hard requirement, from the
2026-11-12 incident where an agent rearranged the owner's own
app windows to reach a test window: this call must never
minimize, move, resize, or otherwise disturb ANY other window,
and it does not move or resize the target either. The only
effects are on the target window itself: it is restored if (and
only if) it is minimized — raising a minimized window is
impossible otherwise — and it is raised in the z-order and,
when Windows grants it, made the foreground window.

Platform limit, stated plainly: Windows restricts which
processes may steal the foreground (the foreground lock). When
the grant is refused, the call still raises the window to the
top of the z-order (SetWindowPos with SWP_NOMOVE | SWP_NOSIZE,
which by construction cannot move or resize anything) and
reports `foreground: false` with the method used — it never
pretends the window is focused when it is not. The success
check is a read-back of GetForegroundWindow, not the API's
return value alone.

Windows-only: the window APIs do not exist elsewhere, and the
route is brokered to the interactive session helper like the
other desktop routes (a session-0 agent has no desktop).
"""

from __future__ import annotations

import os

IS_WINDOWS = os.name == "nt"


class WindowUnavailable(RuntimeError):
    """Raised when the raise cannot be attempted on this platform."""


def pick_window(windows, *, pid=None, title=None) -> dict | None:
    """Choose the window to raise from an enumerated list.

    Pure (unit-tested off-Windows): `windows` entries are dicts
    with hwnd/pid/title/visible. Selection: exact pid match, or
    case-insensitive title substring; visible windows win over
    hidden ones; first match in enumeration order otherwise.
    Exactly one of pid/title must be given.
    """
    if (pid is None) == (title is None):
        raise ValueError("exactly one of pid / title is required")
    matches = []
    for win in windows or ():
        if pid is not None:
            if win.get("pid") == pid:
                matches.append(win)
        else:
            win_title = str(win.get("title") or "")
            if title and title.lower() in win_title.lower():
                matches.append(win)
    if not matches:
        return None
    for win in matches:
        if win.get("visible"):
            return win
    return matches[0]


def _enumerate_windows() -> list[dict]:
    """Visible-state snapshot of top-level windows (Windows)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]

    windows: list[dict] = []

    enum_proc_type = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _collect(hwnd, _lparam):
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        if length:
            user32.GetWindowTextW(hwnd, buf, length + 1)
        windows.append({
            "hwnd": int(hwnd),
            "pid": int(pid.value),
            "title": buf.value,
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "minimized": bool(user32.IsIconic(hwnd)),
        })
        return True

    user32.EnumWindows(enum_proc_type(_collect), 0)
    return windows


def raise_window(*, pid=None, title=None) -> dict:
    """Raise the selected window; returns what actually happened:
    {hwnd, pid, title, restored, foreground, method}.

    `method` is "SetForegroundWindow" when Windows granted the
    foreground, or "SetWindowPos-top" when only the z-order raise
    landed (foreground lock). Raises WindowUnavailable off
    Windows, ValueError on a bad selector, and LookupError when
    no window matches.
    """
    if (pid is None) == (title is None):
        raise ValueError("exactly one of pid / title is required")
    if not IS_WINDOWS:
        raise WindowUnavailable(
            "window raise is Windows-only (Win32 window APIs)")
    import ctypes
    from ctypes import wintypes

    target = pick_window(_enumerate_windows(), pid=pid, title=title)
    if target is None:
        raise LookupError(
            f"no top-level window matches "
            f"{'pid ' + str(pid) if pid is not None else 'title ' + repr(title)}")
    hwnd = target["hwnd"]

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetForegroundWindow.argtypes = []
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT]

    SW_RESTORE = 9
    HWND_TOP = 0
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002

    restored = False
    if user32.IsIconic(hwnd):
        # The target itself only: a minimized window cannot be
        # raised without restoring it. No other window is touched.
        user32.ShowWindow(hwnd, SW_RESTORE)
        restored = True
    granted = bool(user32.SetForegroundWindow(hwnd))
    foreground = int(user32.GetForegroundWindow() or 0) == hwnd
    method = "SetForegroundWindow"
    if not foreground:
        # Foreground lock refused the steal: fall back to the
        # safest subset — top of the z-order with NOMOVE/NOSIZE,
        # which cannot move, resize, or disturb any window.
        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE)
        foreground = int(user32.GetForegroundWindow() or 0) == hwnd
        method = "SetWindowPos-top"
    return {"hwnd": hwnd, "pid": target["pid"],
            "title": target["title"], "restored": restored,
            "foreground": foreground, "set_foreground_granted": granted,
            "method": method}
