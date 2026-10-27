import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.transfer import Layout, TransferArena, TransferBrain, episode_seed, _reachable


class GeneralizationTests(unittest.TestCase):
    def test_split_layouts_are_disjoint_and_reachable(self):
        train = {episode_seed(17, "train", x) for x in range(100)}
        test = {episode_seed(17, "test", x) for x in range(100)}
        self.assertTrue(train.isdisjoint(test))
        for split in ("train", "test"):
            for x in range(40):
                layout = Layout.generate(episode_seed(17, split, x))
                self.assertTrue(_reachable(layout.start, layout.goal,
                                           layout.walls, layout.size))
                self.assertNotIn(layout.start, layout.walls)
                self.assertNotIn(layout.goal, layout.walls)

    def test_observation_does_not_expose_map_or_absolute_position(self):
        layout = Layout(5, (1, 1), (3, 1), frozenset({(1, 0)}))
        arena = TransferArena(layout)
        self.assertEqual(arena.observe(), (2, 0, 1))
        _, reward, _, event = arena.step(0)
        self.assertEqual(event, "blocked")
        self.assertEqual(arena.position, (1, 1))
        self.assertLess(reward, 0)

    def test_unseen_layout_learning_and_read_only_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brain.db"
            brain = TransferBrain(path, seed=17)
            before = brain.evaluate(100)
            brain.train(3600)
            after = brain.evaluate(100)
            self.assertGreater(after["success_rate"], before["success_rate"] + 0.35)
            self.assertGreaterEqual(after["success_rate"], 0.7)
            self.assertEqual(after, brain.evaluate(100))
            before_counts = dict(brain.visits)
            before_values = dict(brain.q)
            brain.evaluate(25)
            self.assertEqual(before_counts, brain.visits)
            self.assertEqual(before_values, brain.q)
            brain.close()
            reopened = TransferBrain(path, seed=17)
            self.assertEqual(reopened.evaluate(100), after)
            self.assertEqual(reopened.trained, 3600)
            with self.assertRaises(ValueError):
                TransferBrain(path, seed=999)
            reopened.close()
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("SELECT value FROM transfer_metadata "
                                              "WHERE name='trained'").fetchone()[0], '3600')


if __name__ == "__main__":
    unittest.main()
