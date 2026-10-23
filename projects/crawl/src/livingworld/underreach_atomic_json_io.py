"""Resilient atomic JSON writes for the long-running Underreach runtime.

Windows may temporarily deny ``os.replace`` while another process has the
existing JSON file open without delete sharing (for example a viewer, indexer,
or antivirus scanner). A transient presentation/status-file lock must not take
down the deterministic Crawl runtime.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
from typing import Any


DEFAULT_REPLACE_ATTEMPTS = 12
DEFAULT_RETRY_DELAY_SECONDS = 0.05
MAX_RETRY_DELAY_SECONDS = 0.5


def atomic_json(
    path: Path,
    value: Any,
    *,
    replace_attempts: int = DEFAULT_REPLACE_ATTEMPTS,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
) -> int:
    """Write JSON durably and atomically, tolerating short-lived file locks.

    A unique temporary filename prevents concurrent writers from trampling the
    same ``.tmp`` path. ``PermissionError`` during the final replace is retried
    with bounded backoff; every other write error still fails immediately.
    """
    if replace_attempts < 1:
        raise ValueError("replace_attempts must be positive")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds cannot be negative")

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(
        f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}"
    )

    try:
        with temporary.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())

        delay = retry_delay_seconds
        for attempt in range(1, replace_attempts + 1):
            try:
                os.replace(temporary, path)
                return len(encoded)
            except PermissionError:
                if attempt >= replace_attempts:
                    raise
                if delay > 0:
                    time.sleep(delay)
                delay = min(MAX_RETRY_DELAY_SECONDS, max(retry_delay_seconds, delay * 1.75))
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

    raise RuntimeError("atomic JSON replacement ended without success or an exception")


__all__ = [
    "DEFAULT_REPLACE_ATTEMPTS",
    "DEFAULT_RETRY_DELAY_SECONDS",
    "MAX_RETRY_DELAY_SECONDS",
    "atomic_json",
]
