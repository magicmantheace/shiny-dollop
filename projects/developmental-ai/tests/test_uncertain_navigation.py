"""Deterministic checks of uncertain navigation and checkpoint integrity."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from developmental_ai.uncertain_navigation import (
    RingBrain, RingWorld, Navigator, canonical, verify_trace,
)


class UncertainNavigationTests(unittest.TestCase):
    def test_goal_is_visible_only_initially(self):
        w = RingWorld(7, "train", 0)
        first = w.initial_observation()
        self.assertEqual(first["beacon"], [w.initial, w.goal])
        sensed, _, _, _ = w.step(0)
        self.assertIsNone(sensed["beacon"])
        self.assertIn(sensed["odometry"], (-1, 0, 1))

    def test_probabilities_and_missing_landmarks(self):
        n = Navigator(1, 4, 9, "belief", "standard", False)
        n.advance(1, {"beacon":None, "odometry":1, "landmark":None})
        self.assertAlmostEqual(sum(n.probs), 1)
        self.assertGreater(n.probs[2], n.probs[1])
        n.advance(1, {"beacon":None, "odometry":-1, "landmark":None})
        self.assertAlmostEqual(sum(n.probs), 1)

    def test_real_landmark_sharpens_estimate(self):
        n = Navigator(1, 4, 9, "belief", "standard", True)
        n.advance(0,{"beacon":None,"odometry":-1,"landmark":0})
        self.assertGreater(n.probs[0], .80)

    def test_checkpoint_exact_continuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"continuous.db", Path(tmp)/"restart.db"
            with RingBrain(a, 19) as brain:
                brain.train(90)
                brain.train(90)
                expected = (brain.trained, brain.q.copy(), brain.evaluate(40))
            with RingBrain(b, 19) as brain:
                brain.train(90)
            with RingBrain(b, 19) as brain:
                brain.train(90)
                self.assertEqual((brain.trained, brain.q, brain.evaluate(40)), expected)

    def test_checkpoint_rejects_wrong_seed_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"brain.db"
            with RingBrain(p, 19) as brain:brain.train(10)
            with self.assertRaises(ValueError):RingBrain(p, 20)
            with self.assertRaises(ValueError):RingBrain(p, 19, "dead")

    def test_eval_and_trace_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"brain.db"
            with RingBrain(path, 23) as brain:
                brain.train(25)
                before = (path.read_bytes(),brain.q.copy(),brain.trained)
                brain.evaluate(15, noise="high")
                trace = brain.trace(1, noise="high", landmarks=False)
                self.assertEqual(verify_trace(trace)["verified"],True)
                self.assertEqual((path.read_bytes(),brain.q,brain.trained),before)

    def test_replay_rejects_recomputed_digest_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            with RingBrain(Path(tmp)/"brain.db", 29) as brain:
                trace=brain.trace(0,policy="heuristic")
                self.assertTrue(verify_trace(trace)["verified"])
                altered=copy.deepcopy(trace)
                altered["outcome"]["events"][0]["observation"]["odometry"] = 999
                body = {k:v for k,v in altered.items() if k!="sha256"}
                altered["sha256"] = hashlib.sha256(canonical(body).encode()).hexdigest()
                with self.assertRaises(ValueError):verify_trace(altered)

    def test_memory_ablation_excludes_target(self):
        nav=Navigator(1,7,9,"reactive","standard",True)
        self.assertEqual(nav.features()[0],9)
        self.assertFalse(nav.known)
        self.assertEqual(nav.heuristic(),0)


if __name__=="__main__":unittest.main()
