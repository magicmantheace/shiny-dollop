"""v1.3.2 regression tests: graceful-shutdown job interruption.

Deploy smoke, 2026-11-24: a durable-runner demo job was mid
stage-2 (a sleep) when the PC rebooted gracefully. Windows
terminated the stage's powershell seconds before the runner
worker (a console-less pythonw), so the worker saw a plain
non-zero exit and marked the job FAILED — nothing was left for
recover() to resume, and the reboot-survival claim failed for
the common reboot kind. The abrupt-kill leg (worker + stage
force-killed) resumed correctly in the same smoke.

The fix: bridge_agent.system_shutting_down() probes
GetSystemMetrics(SM_SHUTTINGDOWN), and the runner arbitrates
every non-zero stage exit against that probe (immediately,
then across a grace window) before it may record a failure;
a shutdown that begins while a stage runs also returns the
stage to pending without killing its tree.

Windows behaviour is NOT proven here: the probe's Windows
branch is exercised with a stubbed ctypes.windll under
simulated platform flags, and the runner tests stub the probe
through the runner's injectable shutdown_fn. The real
SM_SHUTTINGDOWN path is verified on the owner's PC at deploy
time.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402
import job_runner  # noqa: E402

PY = sys.executable


def wait_for(predicate, timeout=20.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def submit(jobs_dir: Path, manifest: dict) -> Path:
    queue = jobs_dir / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    path = queue / f"{manifest['id']}.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def read_record(jobs_dir: Path, job_id: str) -> dict | None:
    try:
        return json.loads((jobs_dir / "state" / f"{job_id}.json")
                          .read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def event_names(jobs_dir: Path, job_id: str) -> list[str]:
    try:
        lines = (jobs_dir / "events.jsonl") \
            .read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [e["event"] for e in (json.loads(x) for x in lines)
            if e.get("job_id") == job_id]


def append_cmd(marker: Path) -> list[str]:
    return [PY, "-c",
            f"open({str(marker)!r}, 'a').write('x\\n')"]


def fail_once_cmd(marker: Path, flag: Path) -> list[str]:
    """Append, then exit 1 on the first run and 0 afterwards."""
    script = (
        f"import os, sys, time\n"
        f"open({str(marker)!r}, 'a').write('x\\n')\n"
        f"first = not os.path.exists({str(flag)!r})\n"
        f"open({str(flag)!r}, 'w').write('1') if first else None\n"
        f"time.sleep(0.3)\n"
        f"sys.exit(1 if first else 0)\n")
    return [PY, "-c", script]


def append_and_maybe_sleep_cmd(marker: Path, flag: Path,
                               seconds: int = 30) -> list[str]:
    script = (
        f"import os, time\n"
        f"open({str(marker)!r}, 'a').write('x\\n')\n"
        f"time.sleep({seconds}) if os.path.exists({str(flag)!r}) "
        f"else None\n")
    return [PY, "-c", script]


class _StubUser32:
    def __init__(self, value):
        self._value = value

    def GetSystemMetrics(self, metric):
        assert metric == 0x2000  # SM_SHUTTINGDOWN
        return self._value


class _StubWindll:
    def __init__(self, value):
        self.user32 = _StubUser32(value)


class ShutdownProbeTests(unittest.TestCase):
    def test_probe_false_on_posix(self):
        self.assertFalse(bridge_agent.system_shutting_down())

    def test_probe_true_under_simulated_windows_shutdown(self):
        with mock.patch.object(bridge_agent, "IS_WINDOWS", True), \
                mock.patch.object(os, "name", "nt"), \
                mock.patch.object(ctypes, "windll",
                                  _StubWindll(1), create=True):
            self.assertTrue(bridge_agent.system_shutting_down())

    def test_probe_false_under_simulated_windows_no_shutdown(self):
        with mock.patch.object(bridge_agent, "IS_WINDOWS", True), \
                mock.patch.object(os, "name", "nt"), \
                mock.patch.object(ctypes, "windll",
                                  _StubWindll(0), create=True):
            self.assertFalse(bridge_agent.system_shutting_down())

    def test_probe_false_when_the_api_raises(self):
        class Boom:
            @property
            def user32(self):
                raise OSError("no user32")
        with mock.patch.object(bridge_agent, "IS_WINDOWS", True), \
                mock.patch.object(os, "name", "nt"), \
                mock.patch.object(ctypes, "windll", Boom(),
                                  create=True):
            self.assertFalse(bridge_agent.system_shutting_down())


class RunnerShutdownCase(unittest.TestCase):
    """Two sequential runners over one jobs dir: the first is
    stopped after the interruption (the worker dying with the
    machine), the second is the post-reboot worker."""

    shutdown_fn = None
    grace_s = 5.0

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.jobs_dir = self.root / "state" / "jobs"
        self.state_dir = self.root / "state"
        self.workdir = self.root / "work"
        self.workdir.mkdir(parents=True)
        self.addCleanup(self.tmp.cleanup)
        self._threads: list[tuple] = []
        self.addCleanup(self._stop_all)

    def _start(self, shutdown_fn, grace_s=None):
        runner = job_runner.JobRunner(
            self.jobs_dir, self.state_dir,
            poll_interval_s=0.05, gpu_poll_s=0.1,
            shutdown_grace_s=self.grace_s if grace_s is None
            else grace_s,
            shutdown_fn=shutdown_fn)
        thread = threading.Thread(target=runner.run, daemon=True)
        thread.start()
        self._threads.append((runner, thread))
        return runner

    def _stop(self, runner):
        runner.request_stop(kill_current=True)
        for r, t in self._threads:
            if r is runner:
                t.join(timeout=10)

    def _stop_all(self):
        for runner, thread in self._threads:
            runner.request_stop(kill_current=True)
        for runner, thread in self._threads:
            thread.join(timeout=10)

    def manifest(self, job_id: str, stages: list) -> dict:
        return {"id": job_id, "name": f"test {job_id}",
                "workdir": str(self.workdir), "stages": stages}


class StageExitDuringShutdownTests(RunnerShutdownCase):
    def test_exit_during_shutdown_is_interrupted_not_failed(self):
        sd = threading.Event()
        runner1 = self._start(sd.is_set)
        m1, m2, m3 = (self.workdir / n
                      for n in ("s1.txt", "s2.txt", "s3.txt"))
        flag = self.workdir / "failed-once"
        submit(self.jobs_dir, self.manifest("job-shutdown-exit", [
            {"command": append_cmd(m1)},
            {"command": fail_once_cmd(m2, flag)},
            {"command": append_cmd(m3)},
        ]))
        # Stage 2 starts with no shutdown in progress; the
        # shutdown begins while it runs (its exit 1 lands inside
        # the shutdown either way it is observed).
        self.assertTrue(wait_for(
            lambda: "stage_started" in event_names(
                self.jobs_dir, "job-shutdown-exit")
            and count_lines(m2) == 1))
        sd.set()
        self.assertTrue(wait_for(
            lambda: "shutdown_interrupted" in event_names(
                self.jobs_dir, "job-shutdown-exit")))
        self._stop(runner1)
        # The checkpoint contract: job left resumable, the
        # interrupted stage pending, stage 1 done exactly once.
        record = read_record(self.jobs_dir, "job-shutdown-exit")
        self.assertEqual(record["state"], "queued")
        self.assertEqual(record["stages"][0]["status"], "done")
        self.assertEqual(record["stages"][1]["status"], "pending")
        self.assertEqual(count_lines(m1), 1)
        self.assertNotIn("failed",
                         event_names(self.jobs_dir,
                                     "job-shutdown-exit"))
        self.assertNotIn("stage_failed",
                         event_names(self.jobs_dir,
                                     "job-shutdown-exit"))
        # The next worker (no shutdown now) finishes the job
        # without re-running stage 1; the flaky stage's second
        # attempt succeeds.
        self._start(lambda: False)
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir,
                                 "job-shutdown-exit") or {})
            .get("state") == "done"))
        self.assertEqual(count_lines(m1), 1)
        self.assertEqual(count_lines(m2), 2)
        self.assertEqual(count_lines(m3), 1)


class RunningStageShutdownTests(RunnerShutdownCase):
    def test_running_stage_returns_to_pending_on_shutdown(self):
        sd = threading.Event()
        runner1 = self._start(sd.is_set)
        m1, m2, m3 = (self.workdir / n
                      for n in ("s1.txt", "s2.txt", "s3.txt"))
        sleep_flag = self.workdir / "sleep"
        sleep_flag.write_text("1", encoding="utf-8")
        submit(self.jobs_dir, self.manifest("job-shutdown-run", [
            {"command": append_cmd(m1)},
            {"command": append_and_maybe_sleep_cmd(m2, sleep_flag)},
            {"command": append_cmd(m3)},
        ]))
        # Stage 2 is asleep; the shutdown begins.
        self.assertTrue(wait_for(lambda: count_lines(m2) == 1))
        sd.set()
        self.assertTrue(wait_for(
            lambda: "shutdown_interrupted" in event_names(
                self.jobs_dir, "job-shutdown-run")))
        self._stop(runner1)
        record = read_record(self.jobs_dir, "job-shutdown-run")
        self.assertEqual(record["state"], "queued")
        self.assertEqual(record["stages"][1]["status"], "pending")
        self.assertEqual(record["stages"][1]["attempts"], 1)
        # After the reboot the sleep flag is gone; the resumed
        # stage runs through and the job completes.
        sleep_flag.unlink()
        self._start(lambda: False)
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir,
                                 "job-shutdown-run") or {})
            .get("state") == "done"))
        self.assertEqual(count_lines(m1), 1)
        self.assertEqual(count_lines(m2), 2)
        self.assertEqual(count_lines(m3), 1)
        self.assertNotIn("failed",
                         event_names(self.jobs_dir,
                                     "job-shutdown-run"))


class GenuineFailureTests(RunnerShutdownCase):
    grace_s = 0.3

    def test_genuine_failure_still_fails(self):
        self._start(lambda: False)
        m1 = self.workdir / "s1.txt"
        submit(self.jobs_dir, self.manifest("job-genuine-fail", [
            {"command": append_cmd(m1)},
            {"command": [PY, "-c", "import sys; sys.exit(3)"]},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir,
                                 "job-genuine-fail") or {})
            .get("state") == "failed"))
        record = read_record(self.jobs_dir, "job-genuine-fail")
        self.assertEqual(record["reason"], "exit_code")
        self.assertEqual(record["exit_code"], 3)
        self.assertEqual(record["failed_stage"], 1)
        names = event_names(self.jobs_dir, "job-genuine-fail")
        self.assertIn("stage_failed", names)
        self.assertIn("failed", names)
        self.assertNotIn("shutdown_interrupted", names)
        # The verdict waited out the grace window (the stage
        # itself exits in well under 0.1 s).
        stage = record["stages"][1]
        self.assertGreaterEqual(
            stage["finished_at"] - stage["started_at"], 0.25)


if __name__ == "__main__":
    unittest.main()
