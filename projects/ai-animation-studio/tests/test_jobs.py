"""F5.1 background job queue: migration 3 (jobs table), the queue API
(atomic FIFO claims, complete/fail, stale requeue with max attempts),
the worker runner, the validate_scene preview + export_scene handlers,
and the enqueue/work/jobs CLI verbs."""
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from studio import jobs
from studio.cli import main
from studio.ipc import read_ipc
from studio.jobs import (MAX_ATTEMPTS, JobError, claim, complete, enqueue,
                         fail, get_job, list_jobs, requeue_stale, run_worker)
from studio.library import Library
from studio.migrations import DDL, applied_versions


def preview_scene() -> dict:
    """A small valid scene with ADR-009-known schedule numbers.

    boris speaks 44 chars at 500 ms -> hold 2934 (window 500..3434);
    anna speaks 30 chars at 1000 ms -> hold 2000 (window 1000..3000).
    Makespan 3434, 4 events.
    """
    return {
        "schema_version": "1.0.0",
        "scene_id": "preview_probe",
        "environment_id": "preview_stage",
        "actors": [
            {"id": "anna", "recipe_id": "anna_01", "color": "#aa3333"},
            {"id": "boris", "recipe_id": "boris_01", "color": "#3333aa"},
        ],
        "events": [
            {"at_ms": 0, "op": "spawn", "actor_id": "anna",
             "position": [0, 0, 0]},
            {"at_ms": 0, "op": "spawn", "actor_id": "boris",
             "position": [2, 0, 0]},
            {"at_ms": 500, "op": "speak", "actor_id": "boris",
             "line": "x" * 44},
            {"at_ms": 1000, "op": "speak", "actor_id": "anna",
             "line": "y" * 30},
        ],
    }


class JobTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.lib = Library(self.base / "test.db")
        self.addCleanup(self.lib.close)
        self.lib.init()

    def backdate_claim(self, job_id: int, seconds: int = 3600) -> None:
        self.lib.db.execute(
            "UPDATE jobs SET claimed_at = datetime('now', ?) WHERE job_id=?",
            (f"-{seconds} seconds", job_id))
        self.lib.db.commit()


class MigrationTests(JobTestCase):
    def test_fresh_db_has_jobs_table(self):
        self.assertEqual(applied_versions(self.lib.db), [1, 2, 3, 4, 5])
        cols = {r[1] for r in self.lib.db.execute("PRAGMA table_info(jobs)")}
        self.assertEqual(cols, {
            "job_id", "kind", "payload_json", "state", "worker_id",
            "attempts", "result_json", "error", "created_at",
            "claimed_at", "finished_at"})

    def test_v1_shaped_db_upgrades_and_can_enqueue(self):
        path = self.base / "legacy.db"
        raw = sqlite3.connect(str(path))
        raw.executescript(DDL.read_text(encoding="utf-8"))
        raw.execute(
            "INSERT INTO assets(asset_id,kind,uri,rig_id,status,tags_json,"
            "metadata_json) VALUES('legacy_prop','prop',"
            "'assets/props/legacy.glb',NULL,'approved','[]','{}')")
        raw.commit()
        raw.close()
        lib = Library(path)
        self.addCleanup(lib.close)
        lib.init()
        self.assertEqual(applied_versions(lib.db), [1, 2, 3, 4, 5])
        self.assertIsNotNone(lib.get_asset("legacy_prop"))
        job_id = enqueue(lib, "validate_scene", {"scene": preview_scene()})
        self.assertEqual(get_job(lib, job_id)["state"], "queued")


class QueueApiTests(JobTestCase):
    def test_enqueue_get_round_trip(self):
        payload = {"scene": {"scene_id": "s"}, "nested": {"list": [1, 2, 3]}}
        job_id = enqueue(self.lib, "validate_scene", payload)
        job = get_job(self.lib, job_id)
        self.assertEqual(job["kind"], "validate_scene")
        self.assertEqual(job["payload"], payload)
        self.assertEqual(job["state"], "queued")
        self.assertEqual(job["attempts"], 0)
        self.assertIsNone(job["worker_id"])
        self.assertIsNone(job["result"])
        self.assertIsNone(job["error"])
        self.assertIsNotNone(job["created_at"])
        self.assertIsNone(job["claimed_at"])
        self.assertIsNone(job["finished_at"])

    def test_get_unknown_job_returns_none(self):
        self.assertIsNone(get_job(self.lib, 9999))

    def test_enqueue_rejects_non_serializable_payload(self):
        with self.assertRaises(JobError):
            enqueue(self.lib, "validate_scene", {"bad": {1, 2, 3}})
        self.assertEqual(list_jobs(self.lib), [])

    def test_enqueue_rejects_bad_kind(self):
        for bad in ("", None, 42, "k" * 65):
            with self.subTest(kind=bad):
                with self.assertRaises(JobError):
                    enqueue(self.lib, bad, {})

    def test_claim_empty_queue_returns_none(self):
        self.assertIsNone(claim(self.lib, "w1"))

    def test_claim_is_fifo(self):
        ids = [enqueue(self.lib, "validate_scene", {"n": n}) for n in range(3)]
        claimed = [claim(self.lib, "w1")["job_id"] for _ in range(3)]
        self.assertEqual(claimed, ids)
        self.assertIsNone(claim(self.lib, "w1"))

    def test_double_claim_prevention_one_job(self):
        enqueue(self.lib, "validate_scene", {})
        first = claim(self.lib, "worker-a")
        self.assertIsNotNone(first)
        self.assertIsNone(claim(self.lib, "worker-b"))
        job = get_job(self.lib, first["job_id"])
        self.assertEqual(job["state"], "running")
        self.assertEqual(job["worker_id"], "worker-a")
        self.assertEqual(job["attempts"], 1)
        self.assertIsNotNone(job["claimed_at"])

    def test_two_workers_get_distinct_jobs(self):
        first_id = enqueue(self.lib, "validate_scene", {"n": 1})
        second_id = enqueue(self.lib, "validate_scene", {"n": 2})
        a = claim(self.lib, "worker-a")
        b = claim(self.lib, "worker-b")
        self.assertEqual({a["job_id"], b["job_id"]}, {first_id, second_id})
        self.assertEqual(a["job_id"], first_id)

    def test_complete_records_result_and_timestamps(self):
        job_id = enqueue(self.lib, "validate_scene", {})
        claim(self.lib, "w1")
        done = complete(self.lib, job_id, {"valid": True})
        self.assertEqual(done["state"], "done")
        self.assertEqual(done["result"], {"valid": True})
        self.assertIsNotNone(done["finished_at"])
        self.assertIsNone(done["error"])

    def test_complete_requires_running(self):
        job_id = enqueue(self.lib, "validate_scene", {})
        with self.assertRaises(JobError):
            complete(self.lib, job_id, {})
        claim(self.lib, "w1")
        complete(self.lib, job_id, {})
        with self.assertRaises(JobError):
            complete(self.lib, job_id, {})

    def test_complete_unknown_job_raises(self):
        with self.assertRaises(JobError):
            complete(self.lib, 4242, {})

    def test_complete_rejects_non_serializable_result(self):
        job_id = enqueue(self.lib, "validate_scene", {})
        claim(self.lib, "w1")
        with self.assertRaises(JobError):
            complete(self.lib, job_id, {"bad": object()})
        self.assertEqual(get_job(self.lib, job_id)["state"], "running")

    def test_fail_records_error(self):
        job_id = enqueue(self.lib, "validate_scene", {})
        claim(self.lib, "w1")
        failed = fail(self.lib, job_id, "boom: it broke")
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["error"], "boom: it broke")
        self.assertIsNotNone(failed["finished_at"])
        with self.assertRaises(JobError):
            fail(self.lib, job_id, "again")

    def test_list_jobs_order_and_state_filter(self):
        a = enqueue(self.lib, "validate_scene", {})
        b = enqueue(self.lib, "export_scene", {})
        claim(self.lib, "w1")
        complete(self.lib, a, {})
        self.assertEqual([j["job_id"] for j in list_jobs(self.lib)], [a, b])
        self.assertEqual([j["job_id"] for j in list_jobs(self.lib, "done")], [a])
        self.assertEqual([j["job_id"] for j in list_jobs(self.lib, "queued")], [b])
        with self.assertRaises(JobError):
            list_jobs(self.lib, "bogus")


class StalePolicyTests(JobTestCase):
    def test_fresh_claim_is_not_stale(self):
        job_id = enqueue(self.lib, "validate_scene", {})
        claim(self.lib, "w1")
        self.assertEqual(requeue_stale(self.lib, 3600),
                         {"requeued": 0, "failed": 0})
        self.assertEqual(get_job(self.lib, job_id)["state"], "running")

    def test_stale_claim_requeues_and_can_be_reclaimed(self):
        job_id = enqueue(self.lib, "validate_scene", {})
        claim(self.lib, "dead-worker")
        self.backdate_claim(job_id)
        self.assertEqual(requeue_stale(self.lib, 60),
                         {"requeued": 1, "failed": 0})
        job = get_job(self.lib, job_id)
        self.assertEqual(job["state"], "queued")
        self.assertIsNone(job["worker_id"])
        self.assertIsNone(job["claimed_at"])
        self.assertEqual(job["attempts"], 1)
        reclaimed = claim(self.lib, "live-worker")
        self.assertEqual(reclaimed["job_id"], job_id)
        self.assertEqual(reclaimed["attempts"], 2)

    def test_stale_at_max_attempts_fails(self):
        job_id = enqueue(self.lib, "validate_scene", {})
        for cycle in range(MAX_ATTEMPTS):
            claimed = claim(self.lib, "flaky-worker")
            self.assertEqual(claimed["attempts"], cycle + 1)
            self.backdate_claim(job_id)
            outcome = requeue_stale(self.lib, 60)
            if cycle < MAX_ATTEMPTS - 1:
                self.assertEqual(outcome, {"requeued": 1, "failed": 0})
            else:
                self.assertEqual(outcome, {"requeued": 0, "failed": 1})
        job = get_job(self.lib, job_id)
        self.assertEqual(job["state"], "failed")
        self.assertIn("max attempts", job["error"])
        self.assertIsNotNone(job["finished_at"])
        self.assertIsNone(claim(self.lib, "w2"))

    def test_requeue_stale_rejects_bad_age(self):
        with self.assertRaises(JobError):
            requeue_stale(self.lib, -5)


class WorkerRunnerTests(JobTestCase):
    def test_validate_scene_preview_valid(self):
        job_id = enqueue(self.lib, "validate_scene",
                         {"scene": preview_scene()})
        summaries = run_worker(self.lib, "w1")
        self.assertEqual(summaries, [{"job_id": job_id,
                                      "kind": "validate_scene",
                                      "state": "done"}])
        result = get_job(self.lib, job_id)["result"]
        self.assertEqual(result, {
            "valid": True,
            "scene_id": "preview_probe",
            "event_count": 4,
            "makespan_ms": 3434,
            "actor_windows": {
                "anna": [{"start_ms": 1000, "end_ms": 3000}],
                "boris": [{"start_ms": 500, "end_ms": 3434}],
            },
        })

    def test_validate_scene_preview_invalid_scene_is_done(self):
        scene = preview_scene()
        scene["events"].append(
            {"at_ms": 2000, "op": "speak", "actor_id": "ghost",
             "line": "boo"})
        job_id = enqueue(self.lib, "validate_scene", {"scene": scene})
        summaries = run_worker(self.lib, "w1")
        self.assertEqual(summaries[0]["state"], "done")
        result = get_job(self.lib, job_id)["result"]
        self.assertFalse(result["valid"])
        self.assertIn("unknown actor", result["error"])

    def test_validate_scene_missing_scene_fails_job(self):
        job_id = enqueue(self.lib, "validate_scene", {"nope": 1})
        summaries = run_worker(self.lib, "w1")
        self.assertEqual(summaries[0]["state"], "failed")
        job = get_job(self.lib, job_id)
        self.assertEqual(job["state"], "failed")
        self.assertIn("scene", job["error"])

    def test_export_scene_writes_readable_envelope(self):
        out = self.base / "exported.json"
        scene = preview_scene()
        job_id = enqueue(self.lib, "export_scene",
                         {"scene": scene, "out": str(out)})
        summaries = run_worker(self.lib, "w1")
        self.assertEqual(summaries[0]["state"], "done")
        result = get_job(self.lib, job_id)["result"]
        self.assertEqual(result["written"], str(out))
        self.assertEqual(result["scene_id"], "preview_probe")
        self.assertEqual(result["ipc_version"], "1.0.0")
        self.assertEqual(read_ipc(out), scene)

    def test_handler_exception_fails_job_with_error_text(self):
        def explode(lib, payload):
            raise RuntimeError("kaboom")

        jobs.HANDLERS["explode"] = explode
        self.addCleanup(jobs.HANDLERS.pop, "explode", None)
        job_id = enqueue(self.lib, "explode", {})
        summaries = run_worker(self.lib, "w1")
        self.assertEqual(summaries[0]["state"], "failed")
        job = get_job(self.lib, job_id)
        self.assertEqual(job["state"], "failed")
        self.assertIn("RuntimeError", job["error"])
        self.assertIn("kaboom", job["error"])

    def test_unknown_kind_fails_with_named_error(self):
        job_id = enqueue(self.lib, "no_such_kind", {})
        summaries = run_worker(self.lib, "w1")
        self.assertEqual(summaries[0]["state"], "failed")
        self.assertIn("no handler registered",
                      get_job(self.lib, job_id)["error"])

    def test_worker_drains_queue_and_terminates(self):
        enqueue(self.lib, "validate_scene", {"scene": preview_scene()})
        enqueue(self.lib, "validate_scene", {"scene": preview_scene()})
        summaries = run_worker(self.lib, "w1")
        self.assertEqual(len(summaries), 2)
        self.assertEqual(run_worker(self.lib, "w1"), [])

    def test_worker_recovers_stale_job_in_same_pass(self):
        job_id = enqueue(self.lib, "validate_scene",
                         {"scene": preview_scene()})
        claim(self.lib, "crashed-worker")
        self.backdate_claim(job_id)
        summaries = run_worker(self.lib, "w2", stale_after_s=60)
        self.assertEqual(summaries, [{"job_id": job_id,
                                      "kind": "validate_scene",
                                      "state": "done"}])
        self.assertEqual(get_job(self.lib, job_id)["attempts"], 2)


class CliSmokeTests(JobTestCase):
    def run_cli(self, argv) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(argv)
        return rc, buf.getvalue()

    def test_enqueue_work_jobs_round_trip(self):
        db = str(self.base / "cli.db")
        payload_file = self.base / "payload.json"
        payload_file.write_text(
            json.dumps({"scene": preview_scene()}), encoding="utf-8")
        rc, out = self.run_cli(
            ["enqueue", "--db", db, "--kind", "validate_scene",
             "--payload", str(payload_file)])
        self.assertEqual(rc, 0)
        self.assertIn("Enqueued job 1", out)
        rc, out = self.run_cli(["work", "--db", db, "--once",
                                "--worker", "smoke"])
        self.assertEqual(rc, 0)
        self.assertIn("job 1 [validate_scene] done", out)
        rc, out = self.run_cli(["jobs", "--db", db])
        self.assertEqual(rc, 0)
        self.assertIn("job 1 [done] validate_scene", out)
        rc, out = self.run_cli(["jobs", "--db", db, "--state", "done"])
        self.assertIn("validate_scene", out)
        rc, out = self.run_cli(["jobs", "--db", db, "--state", "queued"])
        self.assertNotIn("validate_scene", out)


if __name__ == "__main__":
    unittest.main()
