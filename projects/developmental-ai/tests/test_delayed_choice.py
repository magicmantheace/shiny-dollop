"""Deterministic memory-dependent learning, ablation, and trace integrity tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from developmental_ai.delayed_choice import (
    ACTIONS, DelayArena, DelayBrain, WorkingMemory, episode_seed, verify_trace, _json
)


class DelayedChoiceTests(unittest.TestCase):
    def test_future_observations_hide_initial_cue(self):
        arena = DelayArena(episode_seed(11, "test", 3, "long"), "long")
        cue = arena.observe()["token"]
        self.assertIn(cue, range(ACTIONS))
        for _ in range(arena.delay + 1):
            arena.step(ACTIONS)
        self.assertEqual(arena.observe(), {"phase": "decision", "token": None})
        with self.assertRaises(ValueError):
            arena.step(ACTIONS)

    def test_memory_gates_distractors_and_ablation(self):
        retained = WorkingMemory("retain")
        overwritten = WorkingMemory("overwrite")
        reactive = WorkingMemory("reactive")
        for memory in (retained, overwritten, reactive):
            memory.observe({"phase": "cue", "token": 3})
            memory.observe({"phase": "distractor", "token": 1})
            memory.observe({"phase": "decision", "token": None})
        self.assertEqual(retained.recall(), 3)
        self.assertEqual(overwritten.recall(), 1)
        self.assertIsNone(reactive.recall())

    def test_seed_namespace_separation(self):
        values = [episode_seed(7, split, i, band) for split in ("train", "test")
                  for i in range(10) for band in ("short", "long")]
        self.assertEqual(len(set(values)), len(values))
        for args in ((1, "blind", 1, "long"), (1, "train", -1, "short"),
                     (1, "test", 1, "unknown")):
            with self.assertRaises(ValueError):
                episode_seed(*args)

    def test_learning_outperforms_memoryless_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_retained = Path(tmp) / "retained.db"
            file_reactive = Path(tmp) / "reactive.db"
            with DelayBrain(file_retained, 11, "retain") as brain:
                before = brain.evaluate(200, "long")
                brain.train(800)
                trained = brain.evaluate(400, "long")
                self.assertLess(before["success_rate"], 0.4)
                self.assertGreaterEqual(trained["success_rate"], 0.90)
                self.assertEqual(brain.trained, 800)
            with DelayBrain(file_retained, 11, "retain") as restored:
                self.assertEqual(restored.evaluate(400, "long"), trained)
                with self.assertRaises(ValueError):
                    with DelayBrain(file_retained, 11, "reactive"):
                        pass
            with DelayBrain(file_reactive, 11, "reactive") as ablation:
                ablation.train(800)
                self.assertLess(ablation.evaluate(400, "long")["success_rate"], 0.40)

    def test_exact_restart_and_read_only_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.db", Path(tmp) / "b.db"
            with DelayBrain(a, 31) as first:
                first.train(600)
                frozen = dict(first.q)
                summary = first.evaluate(250, "short")
                self.assertEqual(frozen, first.q)
                self.assertEqual(summary, first.evaluate(250, "short"))
            with DelayBrain(b, 31) as interrupted:
                interrupted.train(160)
            with DelayBrain(b, 31) as resumed:
                resumed.train(440)
                self.assertEqual(resumed.q, frozen)
                self.assertEqual(resumed.evaluate(250, "short"), summary)

    def test_trace_replay_refuses_recomputed_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            with DelayBrain(Path(tmp) / "trace.db", 73) as brain:
                brain.train(500)
                trace = brain.trace(4)
                self.assertTrue(verify_trace(trace)["verified"])
                forged = json.loads(json.dumps(trace))
                forged["events"][-1]["event"] = "correct" if forged["events"][-1]["event"] != "correct" else "incorrect"
                body = {k: v for k, v in forged.items() if k != "sha256"}
                forged["sha256"] = hashlib.sha256(_json(body).encode()).hexdigest()
                with self.assertRaises(ValueError):
                    verify_trace(forged)
                missing = json.loads(json.dumps(trace))
                missing["events"].pop()
                missing_body = {k: v for k, v in missing.items() if k != "sha256"}
                missing["sha256"] = hashlib.sha256(_json(missing_body).encode()).hexdigest()
                with self.assertRaises(ValueError):
                    verify_trace(missing)

    def test_bad_action_and_params_fail_closed(self):
        arena = DelayArena(episode_seed(11, "train", 2, "short"))
        for action in (0, True, 6):
            with self.assertRaises(ValueError):
                arena.step(action)
        with tempfile.TemporaryDirectory() as tmp:
            with DelayBrain(Path(tmp) / "a.db", 11) as brain:
                for episodes in (0, -1, True):
                    with self.assertRaises(ValueError):
                        brain.train(episodes)
                with self.assertRaises(ValueError):
                    brain.evaluate(10, "unknown")


if __name__ == "__main__":
    unittest.main()
