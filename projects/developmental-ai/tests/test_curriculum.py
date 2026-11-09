import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.curriculum import (
    CurriculumBrain, TASKS, TaskArena, task_seed, verify_trace, _canonical,
)
from developmental_ai.transfer import Layout, _reachable


class CurriculumTests(unittest.TestCase):
    def test_task_semantics_and_explicit_goal_switch(self):
        layout = Layout(5, (0, 0), (2, 0), frozenset())
        arena = TaskArena(layout, "courier")
        self.assertEqual(arena.observe()[:2], (2, 0))
        for _ in range(2):
            arena.step(3)  # east
        self.assertEqual(arena.step(4)[-1], "pickup")
        self.assertFalse(arena.finished)
        self.assertEqual(arena.observe()[:2], (-2, 0))
        arena.step(2)
        arena.step(2)
        state, reward, done, event = arena.step(4)
        self.assertTrue(done)
        self.assertEqual(event, "delivered")
        self.assertGreater(reward, 0)
        self.assertEqual(state[:2], (0, 0))
        with self.assertRaises(RuntimeError):
            arena.step(4)
        collect = TaskArena(layout, "collect")
        collect.step(3)
        self.assertEqual(collect.step(4)[-1], "empty_interact")
        collect.step(3)
        self.assertEqual(collect.step(4)[-1], "collected")
        reach = TaskArena(layout, "reach")
        reach.step(3)
        self.assertEqual(reach.step(3)[-1], "reached")

    def test_task_namespaces_and_observation(self):
        seeds = {task_seed(17, split, task, n) for split in ("train", "test")
                 for task in TASKS for n in range(30)}
        self.assertEqual(len(seeds), 180)
        for task in TASKS:
            for index in range(15):
                layout = Layout.generate(task_seed(17, "test", task, index))
                self.assertTrue(_reachable(layout.start, layout.goal, layout.walls, layout.size))
                self.assertEqual(len(TaskArena(layout, task).observe()), 3)
        with self.assertRaises(ValueError):
            task_seed(17, "unapproved", "collect", 0)
        with self.assertRaises(ValueError):
            TaskArena(Layout(5, (0, 0), (0, 0), frozenset()), "collect")

    def test_trace_roundtrip_and_recomputed_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            with CurriculumBrain(Path(tmp) / "brain.db") as brain:
                for task in TASKS:
                    trace = brain.trace(task, 0, policy="oracle")
                    outcome = verify_trace(trace)
                    self.assertTrue(outcome["verified"])
                    self.assertEqual(outcome["task"], task)
                    self.assertTrue(trace["outcome"]["success"])
                damaged = copy.deepcopy(brain.trace("courier", 0, policy="oracle"))
                damaged["events"][0]["reward"] = 555
                with self.assertRaisesRegex(ValueError, "checksum"):
                    verify_trace(damaged)
                damaged["sha256"] = hashlib.sha256(_canonical({k: v for k, v
                                      in damaged.items() if k != "sha256"}).encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, "replay"):
                    verify_trace(damaged)
                partial = brain.trace("collect", 0, policy="oracle")
                partial["events"] = partial["events"][:-1]
                partial["sha256"] = hashlib.sha256(_canonical({k: v for k, v
                                      in partial.items() if k != "sha256"}).encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    verify_trace(partial)

    def test_checkpoint_resume_exact_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "resumed.sqlite3"
            with CurriculumBrain(path, seed=29) as brain:
                brain.train(65, ("collect", "reach"))
                before = brain.evaluate("courier", 20)
                snapshot = (dict(brain.q), dict(brain.visits))
                brain.evaluate("reach", 20, policy="greedy")
                brain.trace("collect", 5)
                self.assertEqual((dict(brain.q), dict(brain.visits)), snapshot)
            with CurriculumBrain(path, seed=29) as brain:
                self.assertEqual(brain.trained, 65)
                self.assertEqual(before, brain.evaluate("courier", 20))
                with self.assertRaisesRegex(ValueError, "different task"):
                    brain.train(1, ("collect",))
                brain.train(45, ("collect", "reach"))
                combined_q, combined_visits = dict(brain.q), dict(brain.visits)
            with CurriculumBrain(Path(tmp) / "continuous.sqlite3", seed=29) as control:
                control.train(110, ("collect", "reach"))
                self.assertEqual(control.q, combined_q)
                self.assertEqual(dict(control.visits), combined_visits)
            with self.assertRaisesRegex(ValueError, "seed mismatch"):
                CurriculumBrain(path, seed=17)
            conn = sqlite3.connect(path)
            try:
                conn.execute("UPDATE curriculum_meta SET value='curriculum-v99' WHERE name='schema'")
                conn.commit()
            finally:
                conn.close()
            with self.assertRaisesRegex(ValueError, "schema"):
                CurriculumBrain(path, seed=29)

    def test_single_task_learning_transfers_and_baselines_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with CurriculumBrain(Path(tmp) / "training.sqlite3", seed=13) as brain:
                before = {task: brain.evaluate(task, 70) for task in TASKS}
                brain.train(3000, ("collect",))
                after = {task: brain.evaluate(task, 70) for task in TASKS}
                self.assertGreater(after["collect"]["success_rate"], before["collect"]["success_rate"] + .2)
                self.assertGreater(after["courier"]["success_rate"], before["courier"]["success_rate"] + .2)
                self.assertGreater(after["courier"]["success_rate"], brain.evaluate("courier", 70, policy="random")["success_rate"])
                self.assertEqual(brain.evaluate("courier", 30, policy="oracle")["success_rate"], 1)
                frozen = (dict(brain.q), dict(brain.visits), brain.trained)
                for policy in ("learned", "random", "greedy", "oracle"):
                    brain.evaluate("reach", 30, policy=policy)
                self.assertEqual((dict(brain.q), dict(brain.visits), brain.trained), frozen)


if __name__ == "__main__":
    unittest.main()
