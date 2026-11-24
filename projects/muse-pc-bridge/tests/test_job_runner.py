"""Durable job runner tests.

The runner core is platform-neutral; stages are trivial
`sys.executable -c` one-liners and execution is proven by marker
files (append counts), never by trusting return plumbing.

Covered: submit -> run -> complete; a failing stage marks the
job failed with stage + exit code; manifest retries; invalid
manifests become failed records; the PAUSED flag kills the
running stage's tree and blocks new starts until removed; a
per-job stop flag stops without failing; a gpu:true job waits
(checkpointed, not failed) while a stubbed process list shows a
game, then runs when it clears; and the centrepiece — a real
worker subprocess is SIGKILLed mid-stage-2 and a fresh worker
resumes from the checkpoint, skipping stage 1 and killing the
orphaned stage process.

Windows behaviour is NOT proven here: these tests run on POSIX
with POSIX stages. The runner's Windows seams (taskkill tree
kill via bridge_agent, presence probes) are covered by their
own unit tests and verified on the owner's PC at deploy time.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

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


def append_cmd(marker: Path) -> list[str]:
    return [PY, "-c",
            f"open({str(marker)!r}, 'a').write('x\\n')"]


def append_and_maybe_sleep_cmd(marker: Path, flag: Path,
                               seconds: int = 30) -> list[str]:
    script = (
        f"import os, time\n"
        f"open({str(marker)!r}, 'a').write('x\\n')\n"
        f"time.sleep({seconds}) if os.path.exists({str(flag)!r}) "
        f"else None\n")
    return [PY, "-c", script]


def count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def submit(jobs_dir: Path, manifest: dict,
           filename: str | None = None) -> Path:
    queue = jobs_dir / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    path = queue / (filename or f"{manifest.get('id', 'job')}.json")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def read_record(jobs_dir: Path, job_id: str) -> dict | None:
    try:
        return json.loads((jobs_dir / "state" / f"{job_id}.json")
                          .read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_events(jobs_dir: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in
                (jobs_dir / "events.jsonl")
                .read_text(encoding="utf-8").splitlines()]
    except OSError:
        return []


def event_names(jobs_dir: Path, job_id: str | None = None) -> list[str]:
    return [e["event"] for e in read_events(jobs_dir)
            if job_id is None or e.get("job_id") == job_id]


class RunnerCase(unittest.TestCase):
    """Base: a JobRunner in a thread over temp dirs."""

    runner_kwargs: dict = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.jobs_dir = self.root / "state" / "jobs"
        self.state_dir = self.root / "state"
        self.workdir = self.root / "work"
        self.workdir.mkdir(parents=True)
        self.runner = job_runner.JobRunner(
            self.jobs_dir, self.state_dir,
            poll_interval_s=0.05, gpu_poll_s=0.1,
            **self.runner_kwargs)
        self.thread = threading.Thread(target=self.runner.run,
                                       daemon=True)
        self.thread.start()
        # Cleanups run LIFO: register the temp dir FIRST so the
        # runner is stopped (and joined) before the tree goes
        # away — deleting first races the runner's heartbeat /
        # event writes ("Directory not empty" in cleanup).
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._stop_runner)

    def _stop_runner(self):
        self.runner.request_stop(kill_current=True)
        self.thread.join(timeout=10)

    def manifest(self, job_id: str, stages: list,
                 **extra) -> dict:
        obj = {"id": job_id, "name": f"test {job_id}",
               "workdir": str(self.workdir), "stages": stages}
        obj.update(extra)
        return obj


class BasicRunTest(RunnerCase):
    def test_submit_run_complete(self):
        m1, m2 = self.workdir / "s1.txt", self.workdir / "s2.txt"
        submit(self.jobs_dir, self.manifest("job-basic", [
            {"command": append_cmd(m1)},
            {"command": append_cmd(m2)},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-basic") or {})
            .get("state") == "done"))
        record = read_record(self.jobs_dir, "job-basic")
        self.assertEqual(record["next_stage"], 2)
        self.assertEqual([s["status"] for s in record["stages"]],
                         ["done", "done"])
        self.assertEqual(count_lines(m1), 1)
        self.assertEqual(count_lines(m2), 1)
        names = event_names(self.jobs_dir, "job-basic")
        for expected in ("submitted", "job_started", "stage_finished",
                         "completed"):
            self.assertIn(expected, names)

    def test_failing_stage_marks_job_failed(self):
        m2 = self.workdir / "never.txt"
        submit(self.jobs_dir, self.manifest("job-fail", [
            {"command": [PY, "-c", "import sys; sys.exit(3)"]},
            {"command": append_cmd(m2)},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-fail") or {})
            .get("state") == "failed"))
        record = read_record(self.jobs_dir, "job-fail")
        self.assertEqual(record["failed_stage"], 0)
        self.assertEqual(record["exit_code"], 3)
        self.assertEqual(record["reason"], "exit_code")
        self.assertFalse(m2.exists())
        self.assertIn("stage_failed",
                      event_names(self.jobs_dir, "job-fail"))

    def test_stage_retries_until_success(self):
        counter = self.workdir / "count.txt"
        script = (
            f"import os, sys\n"
            f"n = int(open({str(counter)!r}).read()) "
            f"if os.path.exists({str(counter)!r}) else 0\n"
            f"open({str(counter)!r}, 'w').write(str(n + 1))\n"
            f"sys.exit(0 if n >= 1 else 1)\n")
        submit(self.jobs_dir, self.manifest("job-retry", [
            {"command": [PY, "-c", script], "retries": 1},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-retry") or {})
            .get("state") == "done"))
        record = read_record(self.jobs_dir, "job-retry")
        self.assertEqual(record["stages"][0]["attempts"], 2)
        self.assertIn("stage_retry",
                      event_names(self.jobs_dir, "job-retry"))

    def test_invalid_manifests_become_failed_records(self):
        queue = self.jobs_dir / "queue"
        queue.mkdir(parents=True, exist_ok=True)
        (queue / "broken.json").write_text("{not json",
                                           encoding="utf-8")
        submit(self.jobs_dir,
               {"name": "no stages", "workdir": str(self.workdir),
                "stages": []},
               filename="schema-bad.json")
        self.assertTrue(wait_for(
            lambda: len([r for r in
                         (job_runner.jobs_status(self.jobs_dir)
                          .get("jobs") or [])
                         if r.get("state") == "failed"]) >= 2))
        self.assertTrue((queue / "broken.json.rejected").exists())
        self.assertTrue((queue / "schema-bad.json.rejected").exists())
        names = event_names(self.jobs_dir)
        self.assertGreaterEqual(names.count("invalid_manifest"), 2)


class PauseTest(RunnerCase):
    def test_paused_kills_running_and_blocks_new_starts(self):
        flag = self.workdir / "slow.flag"
        flag.write_text("1", encoding="utf-8")
        marker = self.workdir / "stage.txt"
        submit(self.jobs_dir, self.manifest("job-pause", [
            {"command": append_and_maybe_sleep_cmd(marker, flag)},
        ]))
        self.assertTrue(wait_for(lambda: count_lines(marker) == 1))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-pause") or {})
            .get("state") == "running"))
        (self.jobs_dir / "PAUSED").write_text("owner is gaming",
                                              encoding="utf-8")
        # The running stage is killed and the job returns to
        # queued — paused, never failed.
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-pause") or {})
            .get("state") == "queued"))
        record = read_record(self.jobs_dir, "job-pause")
        self.assertGreaterEqual(record["pause_kills"], 1)
        self.assertIn("pause_kill",
                      event_names(self.jobs_dir, "job-pause"))
        # A new submission does not start while PAUSED.
        m2 = self.workdir / "second.txt"
        submit(self.jobs_dir, self.manifest("job-blocked", [
            {"command": append_cmd(m2)},
        ]))
        time.sleep(1.0)
        self.assertFalse(m2.exists())
        self.assertEqual(
            (read_record(self.jobs_dir, "job-blocked") or {})
            .get("state"), "queued")
        # Unpause: both jobs run to completion (slow flag gone, so
        # the resumed stage no longer sleeps).
        flag.unlink()
        (self.jobs_dir / "PAUSED").unlink()
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-pause") or {})
            .get("state") == "done"))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-blocked") or {})
            .get("state") == "done"))
        self.assertEqual(count_lines(marker), 2)  # killed run + resume


class StopFlagTest(RunnerCase):
    def test_stop_flag_stops_job_and_restart_does_not_resume(self):
        flag = self.workdir / "slow.flag"
        flag.write_text("1", encoding="utf-8")
        marker = self.workdir / "stage.txt"
        submit(self.jobs_dir, self.manifest("job-stop", [
            {"command": append_and_maybe_sleep_cmd(marker, flag)},
        ]))
        self.assertTrue(wait_for(lambda: count_lines(marker) == 1))
        (self.jobs_dir / "stop").mkdir(parents=True, exist_ok=True)
        (self.jobs_dir / "stop" / "job-stop").write_text(
            "stop", encoding="utf-8")
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-stop") or {})
            .get("state") == "stopped"))
        self.assertIn("stop_kill",
                      event_names(self.jobs_dir, "job-stop"))
        # Restart the engine: a stopped job stays stopped.
        self._stop_runner()
        runner2 = job_runner.JobRunner(
            self.jobs_dir, self.state_dir,
            poll_interval_s=0.05, gpu_poll_s=0.1)
        thread2 = threading.Thread(target=runner2.run, daemon=True)
        thread2.start()
        try:
            time.sleep(1.0)
            self.assertEqual(
                (read_record(self.jobs_dir, "job-stop") or {})
                .get("state"), "stopped")
            self.assertEqual(count_lines(marker), 1)
        finally:
            runner2.request_stop(kill_current=True)
            thread2.join(timeout=10)


class GpuWaitTest(RunnerCase):
    def setUp(self):
        self.process_names = ["Wow.exe"]
        self.runner_kwargs = {
            "process_names_fn": lambda: list(self.process_names),
            "gpu_fn": lambda: None,
        }
        super().setUp()

    def test_gpu_job_waits_for_game_then_runs(self):
        marker = self.workdir / "gpu.txt"
        submit(self.jobs_dir, self.manifest("job-gpu", [
            {"command": append_cmd(marker)},
        ], gpu=True))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-gpu") or {})
            .get("waiting_for_gpu")))
        record = read_record(self.jobs_dir, "job-gpu")
        self.assertIn("Wow.exe", record["waiting_for_gpu"])
        self.assertFalse(marker.exists())  # waited, not failed
        self.assertIn("gpu_wait",
                      event_names(self.jobs_dir, "job-gpu"))
        self.process_names = []
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-gpu") or {})
            .get("state") == "done"))
        self.assertEqual(count_lines(marker), 1)
        self.assertIn("gpu_clear",
                      event_names(self.jobs_dir, "job-gpu"))


class ValidateManifestTest(unittest.TestCase):
    def test_minimal_string_command_normalizes(self):
        obj = job_runner.validate_manifest({
            "name": "x", "workdir": "/tmp",
            "stages": [{"command": "echo hi", "shell": "posix"}]})
        self.assertEqual(obj["stages"][0]["name"], "stage-0")
        self.assertEqual(obj["stages"][0]["retries"], 0)
        self.assertFalse(obj["gpu"])
        self.assertFalse(obj["rerun"])

    def test_rejects_bad_manifests(self):
        bad = [
            {"workdir": "/tmp", "stages": [{"command": "x"}]},
            {"name": "x", "workdir": "/tmp", "stages": []},
            {"name": "x", "workdir": "/tmp",
             "stages": [{"command": "x", "retries": 99}]},
            {"name": "x", "workdir": "/tmp",
             "stages": [{"command": ["a"], "shell": "posix"}]},
            {"name": "x", "workdir": "/tmp",
             "stages": [{"command": "x", "shell": "nope"}]},
            {"name": "x", "workdir": "/tmp",
             "stages": [{"command": "x"}], "gpu": "yes"},
        ]
        for obj in bad:
            with self.assertRaises(ValueError, msg=str(obj)):
                job_runner.validate_manifest(obj)


@unittest.skipIf(os.name == "nt",
                 "worker-kill proof uses POSIX signals")
class WorkerKillResumeTest(unittest.TestCase):
    """The centrepiece: SIGKILL the worker mid-stage-2; a fresh
    worker resumes from the checkpoint."""

    def test_resume_skips_completed_stages(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        state_dir = root / "state"
        jobs_dir = state_dir / "jobs"
        workdir = root / "work"
        workdir.mkdir(parents=True)
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0,
            "token": "dummy-token-for-tests",
            "allowed_file_root": str(root / "bridge-files"),
            "audit_log": str(root / "logs" / "audit.jsonl"),
            "state_dir": str(state_dir),
            "job_runner_poll_s": 0.1, "job_gpu_poll_s": 0.5,
        })
        config_path = root / "config.json"
        config_path.write_text(json.dumps(cfg), encoding="utf-8")
        flag = workdir / "slow.flag"
        flag.write_text("1", encoding="utf-8")
        s1, s2 = workdir / "s1.txt", workdir / "s2.txt"
        submit(jobs_dir, {
            "id": "job-resume", "name": "resume proof",
            "workdir": str(workdir),
            "stages": [
                {"command": append_cmd(s1)},
                {"command": append_and_maybe_sleep_cmd(s2, flag)},
            ]})
        worker_cmd = [PY, str(PROJECT_DIR / "agent" / "job_runner.py"),
                      "--worker", "--config", str(config_path)]
        env = dict(os.environ)
        worker1 = subprocess.Popen(
            worker_cmd, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env)
        try:
            # Stage 1 done, stage 2 running (appended + sleeping).
            self.assertTrue(wait_for(lambda: count_lines(s2) == 1))
            self.assertTrue(wait_for(
                lambda: (read_record(jobs_dir, "job-resume") or {})
                .get("next_stage") == 1))
            worker1.send_signal(signal.SIGKILL)
            worker1.wait(timeout=10)
        finally:
            if worker1.poll() is None:
                worker1.kill()
        # The orphaned stage-2 sleeper is still alive right now;
        # the new worker's recovery must kill it. The resumed
        # stage 2 must not sleep again (flag removed).
        flag.unlink()
        worker2 = subprocess.Popen(
            worker_cmd, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env)
        try:
            self.assertTrue(wait_for(
                lambda: (read_record(jobs_dir, "job-resume") or {})
                .get("state") == "done", timeout=30))
        finally:
            worker2.send_signal(signal.SIGTERM)
            try:
                worker2.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker2.kill()
        self.assertEqual(count_lines(s1), 1)   # never re-ran
        self.assertEqual(count_lines(s2), 2)   # interrupted + resumed
        names = event_names(jobs_dir, "job-resume")
        self.assertIn("resume", names)
        self.assertIn("orphan_killed", names)
        self.assertIn("completed", names)


if __name__ == "__main__":
    unittest.main()
