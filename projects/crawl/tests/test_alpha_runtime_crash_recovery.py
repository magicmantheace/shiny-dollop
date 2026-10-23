"""Crash-recovery regression test: SIGKILL the real headless alpha runtime
mid-run, resume from checkpoint, and verify no duplicate canonical events.

This automates what was previously verified manually. Slow by design
(~2 minutes): it exercises the real subprocess, real checkpoints, and a
real kill -9.
"""
from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
ENTRY = ["-m", "livingworld.underreach_alpha_runtime_entry"]


def _runtime_cmd(state_dir: Path, gen_dir: Path, *, resume: bool, duration: float) -> list[str]:
    cmd = [
        sys.executable,
        *ENTRY,
        "--repo-root", str(REPO_ROOT),
        "--profile", "headless",
        "--state-directory", str(state_dir),
        "--generated-directory", str(gen_dir),
        "--duration-seconds", str(duration),
        "--seed", "sigkill-recovery-regression",
    ]
    if resume:
        cmd.append("--resume")
    return cmd


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _runtime_status(state_dir: Path) -> dict:
    path = state_dir / "state" / "runtime.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _final_report(gen_dir: Path) -> dict:
    path = gen_dir / "underreach_alpha_runtime_report.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _wait_for(predicate, timeout: float, interval: float = 1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.mark.slow
def test_sigkill_mid_run_resumes_without_duplicate_events(tmp_path):
    state_dir = tmp_path / "state"
    gen_dir = tmp_path / "generated"

    first = subprocess.Popen(_runtime_cmd(state_dir, gen_dir, resume=False, duration=300.0), env=_env())
    try:
        ready = _wait_for(
            lambda: (state_dir / "checkpoints" / "latest.json").exists()
            and _runtime_status(state_dir).get("simulation_tick", 0) >= 45,
            timeout=180.0,
        )
        assert ready, "runtime never reached a checkpointed tick before kill"
        first.kill()  # SIGKILL — no cleanup, like a real crash
        first.wait(timeout=30)
    finally:
        if first.poll() is None:
            first.kill()
            first.wait(timeout=30)

    # Resume in a fresh process; it must detect the checkpoint, not start over.
    resumed = subprocess.run(
        _runtime_cmd(state_dir, gen_dir, resume=True, duration=60.0),
        env=_env(),
        timeout=180,
    )
    assert resumed.returncode == 0, f"resumed runtime exited {resumed.returncode}"

    report = _final_report(gen_dir)
    assert report, "resumed runtime did not write its final report"
    assert report.get("checkpoint_recoveries", 0) >= 1, report
    assert report.get("canonical_failures", 0) == 0, report
    assert report.get("canonical_recovery_failures", 0) == 0, report

    db_path = state_dir / "state" / "underreach.sqlite3"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM crawl_events").fetchone()[0]
        unique = conn.execute("SELECT COUNT(DISTINCT id) FROM crawl_events").fetchone()[0]
    assert total > 0
    assert unique == total, f"{total - unique} duplicate event ids after crash recovery"
