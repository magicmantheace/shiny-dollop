import tempfile
import unittest
from pathlib import Path
from developmental_ai.organism import ACTIONS, Arena, Memory, Organism
import random


class LearningTests(unittest.TestCase):
    def test_food_and_hazard_differ(self):
        world = Arena(random.Random(1), goal=0)
        # start (0,2): north north east east enters (2,0) hazard
        for action in (0, 0, 3):
            world.step(action)
        _, reward, _, event = world.step(3)
        self.assertEqual(event, 'hazard')
        self.assertLess(reward, -1)

    def test_can_eat_at_target(self):
        world = Arena(random.Random(1), goal=0)
        for action in (0, 0, 3, 3, 3, 3, 3):
            world.step(action)
        self.assertFalse(world.finished)
        _, reward, done, event = world.step(4)
        self.assertTrue(done)
        self.assertEqual(event, 'food')
        self.assertGreater(reward, 9)

    def test_memory_roundtrip_and_learning(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'brain.db'
            store = Memory(path)
            agent = Organism(store, seed=13)
            before = agent.evaluate(120)
            agent.train(2500)
            after = agent.evaluate(120)
            self.assertGreater(after['success_rate'], 0.8)
            self.assertGreater(after['success_rate'], before['success_rate'] + 0.4)
            store.close()
            store = Memory(path)
            restarted = Organism(store, seed=13)
            after_restart = restarted.evaluate(120)
            self.assertEqual(after, after_restart)
            inspect = store.inspect()
            self.assertGreater(inspect['total_episodes'], 0)
            self.assertGreater(len(inspect['learned_landmarks']), 0)
            self.assertGreater(inspect['learned_state_action_values'], 0)
            store.close()

    def test_watch_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Memory(Path(temp) / 'brain.db')
            organism = Organism(store)
            initial = store.inspect()
            actions = organism.watch(goal=1)
            self.assertGreater(len(actions), 1)
            self.assertEqual(store.inspect(), initial)
            store.close()

    def test_evaluate_does_not_mutate_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Memory(Path(temp) / 'brain.db')
            organism = Organism(store)
            organism.evaluate(30)
            self.assertEqual(store.inspect()['total_episodes'], 0)
            self.assertEqual(store.inspect()['learned_state_action_values'], 0)
            store.close()


if __name__ == '__main__':
    unittest.main()
