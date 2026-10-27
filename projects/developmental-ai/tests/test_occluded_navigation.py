import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from developmental_ai.occluded_navigation import (
    DeadReckoning, OccludedBrain, OccludedWorld, episode_seed, canonical, verify_trace,
)
from developmental_ai.transfer import Layout


class OccludedNavigationTests(unittest.TestCase):
    def test_one_time_beacon_and_feedback_odometry(self):
        world = OccludedWorld(Layout.generate(episode_seed(3, "train", 0)))
        before = world.observe()
        self.assertIsNotNone(before["beacon"])
        mem = DeadReckoning("memory")
        first = mem.observe(before)
        available = [a for a in range(4) if not before["blocked"] & (1 << a)]
        self.assertTrue(available)
        action = available[0]
        original = mem.remaining
        reward, done, event = world.step(action)
        self.assertEqual(event, "move")
        self.assertIsNone(world.observe()["beacon"])
        mem.advance(action, event)
        from developmental_ai.transfer import DELTAS
        self.assertEqual(mem.remaining, (original[0] - DELTAS[action][0], original[1] - DELTAS[action][1]))
        self.assertIsNone(DeadReckoning("reactive").remaining)
        self.assertEqual(mem.observe(world.observe())[2], world.observe()["blocked"])

    def test_reactive_forgets_and_blocked_move_does_not_update(self):
        layout = Layout.generate(episode_seed(2, "train", 0))
        for mode in ("memory", "reactive"):
            world = OccludedWorld(layout)
            mem = DeadReckoning(mode)
            mem.observe(world.observe())
            initial = mem.remaining
            blocked = [a for a in range(4) if world.observe()["blocked"] & (1 << a)]
            self.assertTrue(blocked)
            _, _, event = world.step(blocked[0])
            self.assertEqual(event, "blocked")
            mem.advance(blocked[0], event)
            self.assertEqual(mem.remaining, initial if mode == "memory" else None)
            self.assertIsNone(world.observe()["beacon"])

    def test_seed_bound_checkpoint_and_eval_readonly(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "occluded.db"
            with OccludedBrain(path, 7, "memory") as b:
                b.train(70)
                prev = dict(b.q)
                training_count = b.trained
                self.assertEqual(b.evaluate(25)["episodes"], 25)
                self.assertEqual(b.q, prev)
                self.assertEqual(b.trained, training_count)
            before_bytes = path.read_bytes()
            with OccludedBrain(path, 7, "memory") as b:
                self.assertEqual(b.trained, 70)
                self.assertEqual(b.q, prev)
            self.assertEqual(before_bytes, path.read_bytes())
            with self.assertRaises(ValueError):
                OccludedBrain(path, 7, "reactive")
            with self.assertRaises(ValueError):
                OccludedBrain(path, 8, "memory")

    def test_restart_training_matches_uninterrupted(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.db", Path(d) / "b.db"
            with OccludedBrain(a, 13) as brain:
                brain.train(110)
                brain.train(90)
                expected = dict(brain.q), dict(brain.visits), brain.evaluate(25)
            with OccludedBrain(b, 13) as brain:
                brain.train(110)
            with OccludedBrain(b, 13) as brain:
                brain.train(90)
                actual = dict(brain.q), dict(brain.visits), brain.evaluate(25)
            self.assertEqual(expected, actual)

    def test_trace_replay_detects_recomputed_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            with OccludedBrain(Path(d) / "brain.db", 17) as brain:
                t = brain.trace(0, policy="oracle")
            self.assertTrue(verify_trace(t)["verified"])
            altered = copy.deepcopy(t)
            altered["outcome"]["events"][0]["observation"]["beacon"] = [9, 9]
            body = {k: v for k, v in altered.items() if k != "sha256"}
            altered["sha256"] = hashlib.sha256(canonical(body).encode()).hexdigest()
            with self.assertRaises(ValueError):
                verify_trace(altered)
            altered = copy.deepcopy(t)
            altered["outcome"]["events"][0]["memory_after"][0] += 1
            body = {k: v for k, v in altered.items() if k != "sha256"}
            altered["sha256"] = hashlib.sha256(canonical(body).encode()).hexdigest()
            with self.assertRaises(ValueError):
                verify_trace(altered)

    def test_splits_distinct_and_invalid_inputs(self):
        a = [episode_seed(5, "train", i) for i in range(50)]
        b = [episode_seed(5, "test", i) for i in range(50)]
        self.assertFalse(set(a) & set(b))
        with self.assertRaises(ValueError):
            episode_seed(5, "unknown", 0)
        with tempfile.TemporaryDirectory() as d:
            with OccludedBrain(Path(d) / "brain.db") as brain:
                with self.assertRaises(ValueError):
                    brain.run("test", 0, learn=True)
                with self.assertRaises(ValueError):
                    brain.run("train", 0, policy="oracle", learn=True)
                with self.assertRaises(ValueError):
                    brain.run("train", 0, epsilon=1.1)


if __name__ == "__main__":
    unittest.main()
