from __future__ import annotations

import json
from pathlib import Path

from livingworld import underreach_atomic_json_io as atomic_io


def test_atomic_json_retries_transient_permission_error(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "runtime.json"
    real_replace = atomic_io.os.replace
    attempts = {"count": 0}

    def flaky_replace(source, destination):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError(13, "transient Windows-style file lock")
        return real_replace(source, destination)

    monkeypatch.setattr(atomic_io.os, "replace", flaky_replace)
    written = atomic_io.atomic_json(
        target,
        {"tick": 42, "status": "healthy"},
        replace_attempts=4,
        retry_delay_seconds=0,
    )

    assert attempts["count"] == 3
    assert written == len(target.read_bytes())
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "healthy", "tick": 42}
    assert not list(tmp_path.glob("runtime.json.tmp.*"))


def test_atomic_json_raises_after_retry_budget(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "runtime.json"

    def locked_replace(_source, _destination):
        raise PermissionError(13, "locked")

    monkeypatch.setattr(atomic_io.os, "replace", locked_replace)

    try:
        atomic_io.atomic_json(
            target,
            {"tick": 7},
            replace_attempts=3,
            retry_delay_seconds=0,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("expected persistent file lock to raise PermissionError")

    assert not target.exists()
    assert not list(tmp_path.glob("runtime.json.tmp.*"))
