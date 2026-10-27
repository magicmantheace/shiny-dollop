"""Isolated observational multi-start model fitting and leakage regression."""
import copy
import hashlib
import json
import unittest
import tempfile
from pathlib import Path

from developmental_ai.online_dynamics import ModelBank, fit, score, trajectory
from developmental_ai.robust_world_model import ensure_disjoint, fit_robust, seeded_start


class RobustWorldModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = [trajectory(17, "train", i) for i in range(15)]
        cls.valid = [trajectory(17, "train", 2500+i) for i in range(8)]

    def test_reject_overlap_and_duplicates(self):
        with self.assertRaises(ValueError):
            ensure_disjoint(self.train, self.train[:2])
        with self.assertRaises(ValueError):
            ensure_disjoint(self.train + self.train[:1], self.valid)
        with self.assertRaises(ValueError):
            ensure_disjoint(self.train, self.valid + self.valid[:1])

    def test_reject_privileged_labels(self):
        sample = copy.deepcopy(self.train)
        sample[0]["hidden_position"] = 2
        with self.assertRaises(ValueError):
            ensure_disjoint(sample, self.valid)
        with self.assertRaises(ValueError):
            seeded_start(sample, 17, 1)

    def test_reject_broken_settings(self):
        for kwargs in ({"seed": True}, {"seed": 17, "starts": 0},
                       {"seed": 17, "starts": 6}, {"seed": 17, "iterations": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                fit_robust(self.train, self.valid, **kwargs)

    def test_one_start_matches_frozen_baseline(self):
        baseline, _ = fit(self.train, iterations=2)
        robust, receipt = fit_robust(self.train, self.valid, seed=17, starts=1, iterations=2)
        self.assertEqual(baseline.counts, robust.counts)
        self.assertEqual(receipt["chosen_start"], 0)
        self.assertEqual(receipt["baseline_validation_score"], receipt["selected_validation_score"])

    def test_selection_never_worse_on_validation_and_repeatable(self):
        model, receipt = fit_robust(self.train, self.valid, seed=17, starts=3, iterations=2)
        model2, receipt2 = fit_robust(self.train, self.valid, seed=17, starts=3, iterations=2)
        self.assertEqual(receipt, receipt2)
        self.assertEqual(model.counts, model2.counts)
        self.assertGreaterEqual(receipt["selected_validation_score"], receipt["baseline_validation_score"])
        self.assertEqual(receipt["selected_model_sha256"], hashlib.sha256(json.dumps(model.counts,sort_keys=True,separators=(',',':')).encode()).hexdigest())

    def test_saved_model_reopens_identically_without_changing_existing(self):
        model, receipt = fit_robust(self.train, self.valid, seed=17, starts=2, iterations=2)
        with tempfile.TemporaryDirectory() as directory:
            with ModelBank(Path(directory) / "bank.db", 17) as bank:
                bank.save("baseline", fit(self.train, iterations=2)[0], len(self.train))
                original = bank.get("baseline").counts
                bank.save("optional_multistart", model, len(self.train))
            with ModelBank(Path(directory) / "bank.db", 17) as bank:
                self.assertEqual(bank.get("baseline").counts, original)
                self.assertEqual(bank.get("optional_multistart").counts, model.counts)
                self.assertEqual(receipt["selected_model_sha256"],
                                 hashlib.sha256(json.dumps(bank.get("optional_multistart").counts,
                                 sort_keys=True, separators=(',', ':')).encode()).hexdigest())

    def test_inputs_are_not_mutated(self):
        fit_inputs = copy.deepcopy(self.train)
        valid_inputs = copy.deepcopy(self.valid)
        fit_robust(self.train, self.valid, seed=17, starts=2, iterations=2)
        self.assertEqual(self.train, fit_inputs)
        self.assertEqual(self.valid, valid_inputs)


if __name__ == "__main__":
    unittest.main()
