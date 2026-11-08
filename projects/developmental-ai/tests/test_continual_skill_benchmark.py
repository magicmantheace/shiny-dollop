"""Development-only sequential learning, retention and persistence checks."""
from __future__ import annotations

import json
import unittest
from developmental_ai.outcome_skills import OutcomeSkills
from benchmarks.outcome_skills_benchmark import DEV, EXTRA, EPISODES, learn, run
from benchmarks.continual_skill_benchmark import (
    EVAL_EPISODES, EVAL_START, STAGES, TARGET_TRAIN_START, measure,
)


class ContinualSkillsTests(unittest.TestCase):
    def test_protocol_separates_training_evaluation_indices(self):
        self.assertEqual(STAGES, (0, 1, 2, 4, 8, 20))
        self.assertNotEqual(TARGET_TRAIN_START, EVAL_START)
        self.assertGreater(TARGET_TRAIN_START, EVAL_START + EVAL_EPISODES)
        self.assertGreater(TARGET_TRAIN_START, 0)
        self.assertGreater(EPISODES, 0)

    def test_single_invalid_cohort_cannot_masquerade_as_frozen(self):
        for bad in ((DEV[0],), (*EXTRA, 987), (1,2,3)):
            with self.assertRaises(ValueError):
                measure(bad)

    def test_source_memory_remains_unchanged_in_read_only_target_trial(self):
        source = learn(DEV[0])
        before = json.dumps(source.record(), sort_keys=True)
        run(DEV[0], "delivery", "test", EVAL_START, source, "learned", False)
        self.assertEqual(before, json.dumps(source.record(), sort_keys=True))

    def test_sequential_learning_and_restart_preserve_assembly(self):
        seed = DEV[0]
        learner = learn(seed)
        before = run(seed, "assembly", "test", EVAL_START, learner)
        self.assertTrue(before["success"])
        self.assertFalse(run(seed, "delivery", "test", EVAL_START, learner)["success"])
        for index in range(20):
            run(seed, "delivery", "train", TARGET_TRAIN_START+index,
                learner, "learned", True)
        memory = OutcomeSkills.restore(learner.record())
        after = run(seed, "assembly", "test", EVAL_START, memory)
        self.assertTrue(after["success"])
        self.assertTrue(run(seed, "delivery", "test", EVAL_START, memory)["success"])

    def test_matched_delivery_only_budget_does_not_copy_source_skills(self):
        seed = DEV[0]
        learner = OutcomeSkills()
        for index in range(20):
            run(seed, "delivery", "train", TARGET_TRAIN_START+index,
                learner, "learned", True)
        self.assertFalse(run(seed, "delivery", "test", EVAL_START, learner)["success"])
        self.assertFalse(run(seed, "assembly", "test", EVAL_START, learner)["success"])

    def test_evaluation_read_only_and_restart_exact(self):
        agent = learn(DEV[0])
        for index in range(4):
            run(DEV[0], "delivery", "train", TARGET_TRAIN_START+index,
                agent, "learned", True)
        saved = agent.record()
        restored = OutcomeSkills.restore(saved)
        left = run(DEV[0], "delivery", "test", EVAL_START, agent)
        right = run(DEV[0], "delivery", "test", EVAL_START, restored)
        self.assertEqual(left, right)
        self.assertEqual(saved, agent.record())
        self.assertEqual(saved, restored.record())


if __name__ == "__main__":
    unittest.main()
