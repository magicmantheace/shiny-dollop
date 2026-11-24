"""v1.4.0 tests: durable-runner completion notification by email.

When a job reaches a terminal state (done / failed) and the
feature is configured, the runner sends ONE notification email
so completion is learned event-driven instead of by polling.
Covered here:

- success path: a completed job sends exactly once; the record
  is marked notified; a `notify_sent` event is written;
- failure path: a failing SMTP send logs `notify_failed`, the
  job's own outcome is untouched, and the send is retried at
  most once on the next runner start before `notify_gave_up`;
- unconfigured path: the feature is dark — nothing is sent,
  no notify events, records behave exactly as before;
- restart path: a job already notified is never re-sent;
- the real SMTP composition path, driven through a fake SMTP
  factory (no network): subject/body essentials, STARTTLS +
  login with the password taken from the environment variable
  only, and the password appearing in NO event, record, or
  status output;
- a failed job's email names the failing stage and carries
  the last log line.

No real network and no real credentials anywhere: the password
used here is an obvious dummy.
"""

from __future__ import annotations

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

import job_runner  # noqa: E402

PY = sys.executable
DUMMY_PASSWORD = "dummy-app-password-not-real"
CFG_ON = {"notify_email_enabled": True,
          "notify_smtp_user": "owner@example.com",
          "notify_recipient": "nyx-adam@muse.ai"}


def wait_for(predicate, timeout=20.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


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


def read_events(jobs_dir: Path, job_id: str) -> list[dict]:
    try:
        lines = (jobs_dir / "events.jsonl") \
            .read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [e for e in (json.loads(x) for x in lines)
            if e.get("job_id") == job_id]


def event_names(jobs_dir: Path, job_id: str) -> list[str]:
    return [e["event"] for e in read_events(jobs_dir, job_id)]


def append_cmd(marker: Path) -> list[str]:
    return [PY, "-c",
            f"open({str(marker)!r}, 'a').write('x\\n')"]


class RecordingSender:
    """Injectable notify_fn: records the records it was asked
    to send for; optionally raises like a dead SMTP server."""

    def __init__(self, fail: bool = False):
        self.calls: list[dict] = []
        self.fail = fail

    def __call__(self, record):
        self.calls.append({"id": record.get("id"),
                           "state": record.get("state")})
        if self.fail:
            raise RuntimeError("smtp unreachable (fake)")


class NotifyCase(unittest.TestCase):
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

    def _start(self, cfg=None, sender=None, **kw):
        runner = job_runner.JobRunner(
            self.jobs_dir, self.state_dir, cfg,
            poll_interval_s=0.05, gpu_poll_s=0.1,
            shutdown_grace_s=0.2, shutdown_fn=lambda: False,
            notify_fn=sender, **kw)
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


class CompletedJobNotifyTests(NotifyCase):
    def test_completed_job_sends_once_and_never_resends(self):
        sender = RecordingSender()
        runner1 = self._start(CFG_ON, sender)
        m1 = self.workdir / "s1.txt"
        submit(self.jobs_dir, self.manifest("job-notify-ok", [
            {"name": "only", "command": append_cmd(m1)},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-notify-ok")
                     or {}).get("notified") is True))
        record = read_record(self.jobs_dir, "job-notify-ok")
        self.assertEqual(record["state"], "done")
        self.assertEqual(record["notify_attempts"], 1)
        self.assertFalse(record["notify_pending"])
        self.assertEqual(len(sender.calls), 1)
        self.assertEqual(sender.calls[0]["state"], "done")
        names = event_names(self.jobs_dir, "job-notify-ok")
        self.assertIn("completed", names)
        self.assertIn("notify_sent", names)
        self.assertNotIn("notify_failed", names)
        self._stop(runner1)
        # A fresh runner over the same store must not re-send.
        self._start(CFG_ON, sender)
        time.sleep(0.6)
        self.assertEqual(len(sender.calls), 1)


class FailedSendTests(NotifyCase):
    def test_failed_send_never_fails_the_job_and_retries_once(self):
        bad = RecordingSender(fail=True)
        runner1 = self._start(CFG_ON, bad)
        m1 = self.workdir / "s1.txt"
        submit(self.jobs_dir, self.manifest("job-notify-flaky", [
            {"command": append_cmd(m1)},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-notify-flaky")
                     or {}).get("notify_attempts") == 1))
        record = read_record(self.jobs_dir, "job-notify-flaky")
        # The job itself completed normally.
        self.assertEqual(record["state"], "done")
        self.assertFalse(record["notified"])
        self.assertTrue(record["notify_pending"])
        self.assertIn("notify_failed",
                      event_names(self.jobs_dir, "job-notify-flaky"))
        self._stop(runner1)
        # Next runner start retries — once — and now it lands.
        good = RecordingSender()
        self._start(CFG_ON, good)
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-notify-flaky")
                     or {}).get("notified") is True))
        self.assertEqual(len(good.calls), 1)
        record = read_record(self.jobs_dir, "job-notify-flaky")
        self.assertEqual(record["notify_attempts"], 2)

    def test_second_failure_gives_up_and_stays_given_up(self):
        bad = RecordingSender(fail=True)
        runner1 = self._start(CFG_ON, bad)
        m1 = self.workdir / "s1.txt"
        submit(self.jobs_dir, self.manifest("job-notify-dead", [
            {"command": append_cmd(m1)},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-notify-dead")
                     or {}).get("notify_attempts") == 1))
        self._stop(runner1)
        runner2 = self._start(CFG_ON, bad)
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-notify-dead")
                     or {}).get("notify_given_up") is True))
        self.assertEqual(len(bad.calls), 2)
        names = event_names(self.jobs_dir, "job-notify-dead")
        self.assertIn("notify_gave_up", names)
        self._stop(runner2)
        # A third start makes no further attempt.
        self._start(CFG_ON, bad)
        time.sleep(0.6)
        self.assertEqual(len(bad.calls), 2)


class FailedJobNotifyTests(NotifyCase):
    def test_failed_job_also_notifies(self):
        sender = RecordingSender()
        self._start(CFG_ON, sender)
        submit(self.jobs_dir, self.manifest("job-notify-fail", [
            {"name": "boom",
             "command": [PY, "-c", "import sys; sys.exit(3)"]},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-notify-fail")
                     or {}).get("notified") is True))
        record = read_record(self.jobs_dir, "job-notify-fail")
        self.assertEqual(record["state"], "failed")
        self.assertEqual(len(sender.calls), 1)
        self.assertEqual(sender.calls[0]["state"], "failed")
        self.assertIn("notify_sent",
                      event_names(self.jobs_dir, "job-notify-fail"))


class UnconfiguredTests(NotifyCase):
    def test_unconfigured_sends_nothing(self):
        sender = RecordingSender()
        self._start({}, sender)  # no notify keys at all
        m1 = self.workdir / "s1.txt"
        submit(self.jobs_dir, self.manifest("job-notify-dark", [
            {"command": append_cmd(m1)},
        ]))
        self.assertTrue(wait_for(
            lambda: (read_record(self.jobs_dir, "job-notify-dark")
                     or {}).get("state") == "done"))
        time.sleep(0.4)
        self.assertEqual(sender.calls, [])
        record = read_record(self.jobs_dir, "job-notify-dark")
        self.assertFalse(record["notified"])
        self.assertEqual(record["notify_attempts"], 0)
        names = event_names(self.jobs_dir, "job-notify-dark")
        self.assertNotIn("notify_sent", names)
        self.assertNotIn("notify_failed", names)


class FakeSMTP:
    """smtplib.SMTP stand-in: records everything, sends nothing."""
    instances: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.started_tls = False
        self.login_args = None
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.started_tls = True
        self.tls_context = context

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.messages.append(msg)


class SmtpCompositionTests(NotifyCase):
    def setUp(self):
        super().setUp()
        FakeSMTP.instances = []
        for d in (self.jobs_dir / "state", self.jobs_dir / "logs"):
            d.mkdir(parents=True, exist_ok=True)

    def _runner(self):
        return job_runner.JobRunner(
            self.jobs_dir, self.state_dir, CFG_ON,
            smtp_factory=FakeSMTP)

    def _terminal_record(self, **over):
        record = {
            "id": "job-smtp-1", "name": "SMTP test job",
            "state": "done", "next_stage": 1,
            "stages": [{"index": 0, "name": "generate",
                        "status": "done", "attempts": 2,
                        "started_at": 1000.0,
                        "finished_at": 1042.0, "exit_code": 0,
                        "pid": None}],
            "submitted_at": 990.0, "started_at": 1000.0,
            "finished_at": 1042.0, "failed_stage": None,
            "exit_code": 0, "reason": None,
            "notified": False, "notify_pending": False,
            "notify_attempts": 0, "notify_given_up": False,
        }
        record.update(over)
        return record

    def test_smtp_send_subject_body_and_secret_hygiene(self):
        runner = self._runner()
        record = self._terminal_record()
        runner._write_record(record)
        with mock.patch.dict(
                os.environ,
                {job_runner.NOTIFY_PASSWORD_ENV: DUMMY_PASSWORD}):
            runner._notify_terminal(record)
        self.assertEqual(len(FakeSMTP.instances), 1)
        smtp = FakeSMTP.instances[0]
        self.assertEqual((smtp.host, smtp.port),
                         ("smtp.gmail.com", 587))
        self.assertTrue(smtp.started_tls)
        self.assertEqual(smtp.login_args,
                         ("owner@example.com", DUMMY_PASSWORD))
        self.assertEqual(len(smtp.messages), 1)
        msg = smtp.messages[0]
        self.assertEqual(msg["To"], "nyx-adam@muse.ai")
        self.assertEqual(msg["Subject"],
                         "[pc-bridge] job job-smtp-1 completed")
        body = msg.get_content()
        self.assertIn("Name: SMTP test job", body)
        self.assertIn("Outcome: completed", body)
        self.assertIn("Duration: 42.0 s", body)
        self.assertIn("generate: done (attempts: 2, "
                      "exit code: 0)", body)
        # The secret appears NOWHERE it must not: not in the
        # email, the events log, or the job record.
        self.assertNotIn(DUMMY_PASSWORD, body)
        events_text = (self.jobs_dir / "events.jsonl") \
            .read_text(encoding="utf-8")
        self.assertIn("notify_sent", events_text)
        self.assertNotIn(DUMMY_PASSWORD, events_text)
        record_text = (self.jobs_dir / "state" / "job-smtp-1.json") \
            .read_text(encoding="utf-8")
        self.assertNotIn(DUMMY_PASSWORD, record_text)
        saved = read_record(self.jobs_dir, "job-smtp-1")
        self.assertTrue(saved["notified"])

    def test_failed_job_body_names_stage_and_last_log_line(self):
        (self.jobs_dir / "logs" / "job-smtp-2.log").write_text(
            "some output\nfinal boom: disk exploded\n",
            encoding="utf-8")
        runner = self._runner()
        record = self._terminal_record(
            id="job-smtp-2", state="failed", reason="exit_code",
            failed_stage=0, exit_code=3,
            stages=[{"index": 0, "name": "generate",
                     "status": "failed", "attempts": 1,
                     "started_at": 1000.0, "finished_at": 1001.0,
                     "exit_code": 3, "pid": None}])
        subject, body = runner.build_notification(record)
        self.assertEqual(subject,
                         "[pc-bridge] job job-smtp-2 failed")
        self.assertIn("Failed stage: 0", body)
        self.assertIn("Reason: exit_code", body)
        self.assertIn("generate: failed (attempts: 1, "
                      "exit code: 3)", body)
        self.assertIn("Last log line: final boom: disk exploded",
                      body)

    def test_missing_password_is_a_clean_notify_failure(self):
        runner = self._runner()
        record = self._terminal_record(id="job-smtp-3")
        runner._write_record(record)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(job_runner.NOTIFY_PASSWORD_ENV, None)
            runner._notify_terminal(record)
        self.assertEqual(FakeSMTP.instances, [])
        saved = read_record(self.jobs_dir, "job-smtp-3")
        self.assertFalse(saved["notified"])
        self.assertEqual(saved["notify_attempts"], 1)
        self.assertIn("notify_failed",
                      event_names(self.jobs_dir, "job-smtp-3"))


if __name__ == "__main__":
    unittest.main()
