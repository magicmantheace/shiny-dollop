"""Behavioral, restart and provenance checks for learned memory selection."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.selective_memory import (
    MODES, SignalTrial, SelectiveBrain, canonical, episode_seed, verify_trace,
)


class SelectiveMemoryTests(unittest.TestCase):
    def test_observations_hide_correct_source_and_answer(self):
        arena = SignalTrial(episode_seed(11, "test", 4, "long"), "long")
        observations = arena.observations()
        self.assertEqual(observations[0], {"kind": "context", "value": arena.context})
        self.assertEqual(observations[-1], {"kind": "decision"})
        self.assertEqual(sum(o.get("channel") == "A" for o in observations), 1)
        self.assertEqual(sum(o.get("channel") == "B" for o in observations), 1)
        self.assertGreaterEqual(sum(o.get("channel") == "N" for o in observations), 10)
        for observation in observations:
            self.assertNotIn("correct_action", observation)
            self.assertNotIn("correct_symbol", observation)

    def test_namespace_and_input_validation(self):
        self.assertNotEqual(episode_seed(11, "train", 0, "short"),
                            episode_seed(11, "test", 0, "short"))
        for args in ((True, "train", 0, "short"), (11, "other", 0, "short"),
                     (11, "test", -1, "long"), (11, "test", 0, "wrong")):
            with self.assertRaises(ValueError):
                episode_seed(*args)
        with tempfile.TemporaryDirectory() as tmp:
            with SelectiveBrain(Path(tmp) / "s.db", 11) as brain:
                for episode_count in (0, -1, True):
                    with self.assertRaises(ValueError):
                        brain.train(episode_count)
                with self.assertRaises(ValueError):
                    brain.evaluate(20, "missing")
                with self.assertRaises(ValueError):
                    brain.trial("test", 0, epsilon=2)
                with self.assertRaises(ValueError):
                    brain.trial("test", 0, learn=True)

    def test_learning_separates_signal_from_distractors(self):
        with tempfile.TemporaryDirectory() as root:
            with SelectiveBrain(Path(root) / "learned.db", 11) as learner:
                initial = learner.evaluate(240)
                learner.train(3500)
                result = learner.evaluate(300)
                self.assertLess(initial["accuracy"], 0.40)
                self.assertGreaterEqual(result["accuracy"], 0.90)
                self.assertGreaterEqual(result["target_retention"], 0.90)
            with SelectiveBrain(Path(root) / "last.db", 11, "last") as ablation:
                ablation.train(3500)
                self.assertLess(ablation.evaluate(300)["accuracy"], 0.45)

    def test_restart_replays_exact_training_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline, resumed = Path(tmp) / "baseline.db", Path(tmp) / "resumed.db"
            with SelectiveBrain(baseline, 31) as brain:
                brain.train(620)
                expected_gate, expected_q = dict(brain.gate), dict(brain.q)
                expected_eval = brain.evaluate(150)
            with SelectiveBrain(resumed, 31) as brain:
                brain.train(230)
            with SelectiveBrain(resumed, 31) as brain:
                brain.train(390)
                self.assertEqual(expected_gate, brain.gate)
                self.assertEqual(expected_q, brain.q)
                self.assertEqual(expected_eval, brain.evaluate(150))
                frozen_gate, frozen_q = dict(brain.gate), dict(brain.q)
                brain.trace(5)
                brain.evaluate(150, "short")
                self.assertEqual((frozen_gate, frozen_q), (brain.gate, brain.q))
            with SelectiveBrain(resumed, 31) as restored:
                self.assertEqual(restored.trained, 620)
            with self.assertRaises(ValueError):
                SelectiveBrain(resumed, 31, "last")
            with self.assertRaises(ValueError):
                SelectiveBrain(resumed, 99, "learned")

    def test_trace_replay_rejects_tampering_even_with_recomputed_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SelectiveBrain(Path(tmp) / "s.db", 73) as brain:
                brain.train(400)
                trace = brain.trace(3)
                self.assertTrue(verify_trace(trace)["verified"])
                bad = json.loads(json.dumps(trace))
                bad["outcome"]["events"][-1]["action"] = (bad["outcome"]["events"][-1]["action"] + 1) % 4
                body = {k: v for k, v in bad.items() if k != "sha256"}
                bad["sha256"] = hashlib.sha256(canonical(body).encode()).hexdigest()
                with self.assertRaises(ValueError):
                    verify_trace(bad)
                bad = json.loads(json.dumps(trace))
                bad["outcome"]["events"][1]["memory"] = ["N", 30]
                body = {k: v for k, v in bad.items() if k != "sha256"}
                bad["sha256"] = hashlib.sha256(canonical(body).encode()).hexdigest()
                with self.assertRaises(ValueError):
                    verify_trace(bad)

    def test_corrupt_checkpoint_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "bad.db"
            with SelectiveBrain(db, 11) as brain:
                brain.train(12)
            with sqlite3.connect(db) as conn:
                conn.execute("INSERT OR REPLACE INTO select_gate VALUES(?,?,?)", (0, "A", float('inf')))
            with self.assertRaises(ValueError):
                SelectiveBrain(db, 11)


if __name__ == "__main__":
    unittest.main()
