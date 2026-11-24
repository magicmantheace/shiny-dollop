#!/usr/bin/env python3
"""Boot beacon — muse-pc-bridge (durable job runner release).

Records boot-scoped lifecycle events to `<state_dir>/boot-log.jsonl`
so a human (or Muse) can answer, after the fact and without
asking anyone: did the PC reboot, when, did the bridge come back,
and which durable-runner jobs were mid-flight and got resumed.

Three writers, one log, all best-effort (a beacon failure must
never take down the writer):

- the supervisor appends `supervisor_start` when it starts,
- the agent appends `agent_start` when its server is created,
- the durable job runner appends `jobs_resumed` after its
  start-up recovery scan.

Each event carries the machine's boot time (epoch seconds) and a
`fresh_boot` flag: True when the boot time differs from the one
recorded by the previous beacon writer (kept in
`<state_dir>/boot-beacon.json`), i.e. this process start follows
a real reboot rather than a mere agent/supervisor restart. This
passively answers the reboot-survival question that has been
held open since v1: after a reboot, the log shows a fresh boot,
an agent start for that boot, and the runner's resume record —
or it shows their absence.

Boot time source: Windows — GetTickCount64 (ms since boot);
POSIX — /proc/stat `btime`. Anything else: None, and events are
still written with `fresh_boot` null (unknown, not guessed).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

BEACON_STATE_NAME = "boot-beacon.json"
BEACON_LOG_NAME = "boot-log.jsonl"
# Same-boot tolerance: the Windows boot time is derived as
# now - GetTickCount64, so clock corrections between two writers
# can shift it by seconds; distinct boots are minutes apart.
_FRESH_TOLERANCE_S = 30.0

_lock = threading.Lock()


def system_boot_time() -> float | None:
    """Epoch seconds when this machine booted, or None."""
    if os.name == "nt":
        try:
            import ctypes
            import time as _time
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            kernel32.GetTickCount64.argtypes = []
            uptime_s = kernel32.GetTickCount64() / 1000.0
            return _time.time() - uptime_s
        except Exception:
            return None
    try:
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("btime "):
                    return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


def _read_beacon_state(state_dir: Path) -> dict | None:
    try:
        obj = json.loads((state_dir / BEACON_STATE_NAME).read_text(
            encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _write_beacon_state(state_dir: Path, obj: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / BEACON_STATE_NAME
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def append_event(state_dir: Path, event: str, **fields) -> dict:
    """Append one event to the boot log; returns the entry.

    Computes and stores the boot fields itself. Never raises for
    JSON/shape problems in `fields`; may raise OSError on a truly
    unwritable state dir — callers that must not fail (agent,
    supervisor, runner) wrap this in try/except.
    """
    state_dir = Path(state_dir)
    boot_time = system_boot_time()
    with _lock:
        previous = _read_beacon_state(state_dir)
        prev_boot = previous.get("boot_time") if previous else None
        if boot_time is None or not isinstance(prev_boot, (int, float)):
            fresh = None if boot_time is None else True
        else:
            fresh = abs(float(boot_time) - float(prev_boot)) \
                > _FRESH_TOLERANCE_S
        entry = {
            "ts": _utc_now_iso(),
            "event": event,
            "boot_time": boot_time,
            "fresh_boot": fresh,
        }
        entry.update(fields)
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / BEACON_LOG_NAME, "a",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        if boot_time is not None:
            _write_beacon_state(state_dir, {
                "boot_time": boot_time,
                "last_event": event,
                "updated_at": entry["ts"],
            })
    return entry


def note_boot(state_dir: Path, source: str, **fields) -> dict:
    """Append a `<source>_start` event and return the entry."""
    return append_event(state_dir, f"{source}_start", source=source,
                        **fields)
