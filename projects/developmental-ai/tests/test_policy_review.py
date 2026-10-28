"""Review gates must be read-only until an explicitly approved promotion."""
from __future__ import annotations

import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from developmental_ai.policy_review import (
    SCHEMA, VALIDATION_START, StagedPolicyUpdate, _fingerprint,
)
from developmental_ai.transfer import TransferBrain, episode_seed


class PolicyReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "policy.db"
        self.brain = TransferBrain(self.path, seed=17)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def _identity(self):
        return _fingerprint(self.brain.seed, self.brain.trained,
                            self.brain.q, self.brain.visits)

    def test_candidate_review_does_not_change_original_memory_or_database(self):
        before = self._identity()
        proposal = StagedPolicyUpdate(self.brain, 20, validation_episodes=8)
        record = proposal.review()
        self.assertEqual(record["receipt"]["schema"], SCHEMA)
        self.assertEqual(record["receipt"]["validation_namespace"], "train")
        self.assertEqual(record["receipt"]["validation_start"], VALIDATION_START)
        self.assertEqual(record["receipt"]["training_episodes"], 20)
        self.assertEqual(self._identity(), before)
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertIsNone(conn.execute(
                "SELECT value FROM transfer_metadata WHERE name='trained'").fetchone())
        proposal.reject()
        self.assertEqual(before, self._identity())

    def test_candidate_requires_explicit_approval_and_survives_restart(self):
        proposal = StagedPolicyUpdate(
            self.brain, 60, validation_episodes=8, max_success_loss=1,
        )
        receipt = proposal.review()
        before = self._identity()
        with self.assertRaises(ValueError):
            proposal.promote(approved=False, receipt_sha256=receipt["sha256"])
        with self.assertRaises(ValueError):
            proposal.promote(approved=True, receipt_sha256="wrong")
        self.assertEqual(before, self._identity())
        proposal.promote(approved=True, receipt_sha256=receipt["sha256"])
        self.assertEqual(self.brain.trained, 60)
        self.assertNotEqual(before, self._identity())
        with self.assertRaises(ValueError):
            proposal.promote(approved=True, receipt_sha256=receipt["sha256"])
        self.brain.close()
        self.brain = TransferBrain(self.path, seed=17)
        self.assertEqual(self.brain.trained, 60)
        self.assertEqual(self._identity(), receipt["receipt"]["candidate_sha256"])

    def test_detects_stale_original_and_tampered_candidate(self):
        proposal = StagedPolicyUpdate(
            self.brain, 10, validation_episodes=8, max_success_loss=1,
        )
        receipt = proposal.review()
        self.brain.train(1)
        with self.assertRaisesRegex(ValueError, "base policy changed"):
            proposal.promote(approved=True, receipt_sha256=receipt["sha256"])

        second = StagedPolicyUpdate(
            self.brain, 10, validation_episodes=8, max_success_loss=1,
        )
        receipt2 = second.review()
        second._candidate_q[((0, 0, 0), 1)] = 1234
        with self.assertRaisesRegex(ValueError, "candidate mutated"):
            second.promote(approved=True, receipt_sha256=receipt2["sha256"])

    def test_regression_gate_blocks_promotion(self):
        strong = {"successes": 8, "episodes": 8, "mean_steps": 1,
                  "mean_reward": 1, "mean_blocked": 0}
        weak = {"successes": 0, "episodes": 8, "mean_steps": 1,
                "mean_reward": 0, "mean_blocked": 0}
        with patch("developmental_ai.policy_review._validation",
                   side_effect=[strong, weak]):
            proposal = StagedPolicyUpdate(self.brain, 10, validation_episodes=8)
        receipt = proposal.review()
        self.assertFalse(receipt["receipt"]["eligible_for_manual_approval"])
        with self.assertRaisesRegex(ValueError, "validation regression"):
            proposal.promote(approved=True, receipt_sha256=receipt["sha256"])
        self.assertEqual(self.brain.trained, 0)

    def test_validation_is_disjoint_from_training_and_published_test(self):
        self.assertNotEqual(episode_seed(17, "train", VALIDATION_START),
                            episode_seed(17, "train", 0))
        self.assertNotEqual(episode_seed(17, "train", VALIDATION_START),
                            episode_seed(17, "test", VALIDATION_START))
        self.assertNotEqual(episode_seed(17, "train", VALIDATION_START),
                            episode_seed(17, "test", 0))

    def test_invalid_inputs_and_review_copy(self):
        for value in (True, 0, -1, 2.5):
            with self.assertRaises(ValueError):
                StagedPolicyUpdate(self.brain, value)
        for count in (7, 257, True):
            with self.assertRaises(ValueError):
                StagedPolicyUpdate(self.brain, 5, validation_episodes=count)
        for loss in (-0.1, 2, float("nan"), True):
            with self.assertRaises(ValueError):
                StagedPolicyUpdate(self.brain, 5, max_success_loss=loss)
        proposal = StagedPolicyUpdate(self.brain, 10, validation_episodes=8)
        record = proposal.review()
        record["receipt"]["candidate_sha256"] = "edited"
        self.assertNotEqual(record, proposal.review())
        proposal.reject()
        with self.assertRaises(ValueError):
            proposal.reject()


if __name__ == "__main__":
    unittest.main()
