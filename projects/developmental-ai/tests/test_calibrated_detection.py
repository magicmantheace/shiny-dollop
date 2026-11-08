"""Offline calibration uses distinct model-fit, calibration, and evaluation data."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from developmental_ai.calibrated_detection import calibrate, load_calibration, verify_calibration
from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.step_dynamics import StepDetector


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "models.db"
        self.seed = 17
        self.regimes = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}
        with ModelBank(self.path, self.seed) as bank:
            for name, condition in self.regimes.items():
                data = [trajectory(self.seed, "train", i, *condition) for i in range(60)]
                bank.save(name, fit(data, iterations=5)[0], len(data))

    def evidence(self):
        return {name: [trajectory(self.seed, "train", 5000+i, *condition) for i in range(24)]
                for name, condition in self.regimes.items()}

    def test_threshold_derived_from_separate_histories_and_bound_to_bank(self):
        with ModelBank(self.path, self.seed) as bank:
            profile = calibrate(bank, self.evidence())
            self.assertGreater(profile.margin, 0)
            self.assertLess(profile.margin, .12)
            self.assertEqual(profile, load_calibration(json.dumps(profile.as_dict())))
            self.assertEqual(verify_calibration(bank, profile), profile.margin)
            with StepDetector(Path(self.tmp.name)/"step.db", bank, margin=profile.margin) as step:
                h = trajectory(self.seed, "test", 6000)
                step.begin(h["n"], h["initial"])
                for obs in h["observations"]:
                    step.step(*obs)
                step.finish()
                self.assertGreater(len(step.events()), 0)
        with ModelBank(self.path, self.seed + 1) as bank:
            with self.assertRaises(ValueError):
                verify_calibration(bank, profile)

    def test_calibration_rejects_missing_regime_and_repeated_histories(self):
        with ModelBank(self.path, self.seed) as bank:
            samples = self.evidence()
            with self.assertRaises(ValueError):
                calibrate(bank, {"original": samples["original"]})
            samples["changed"][0] = samples["original"][0]
            with self.assertRaises(ValueError):
                calibrate(bank, samples)

    def test_bad_threshold_and_metadata_rejected(self):
        with ModelBank(self.path, self.seed) as bank:
            for bad in (float("nan"), 0, -1, 2):
                with self.assertRaises(ValueError):
                    calibrate(bank, self.evidence(), fraction=bad)
            profile = calibrate(bank, self.evidence())
            tampered = profile.as_dict()
            tampered["catalogue"] = "0"*64
            with self.assertRaises(ValueError):
                verify_calibration(bank, load_calibration(json.dumps(tampered)))
            with self.assertRaises(ValueError):
                load_calibration(json.dumps({**tampered, "secret": "unused"}))
            changed = profile.as_dict()
            changed["margin"] = 0.00001
            with self.assertRaises(ValueError):
                load_calibration(json.dumps(changed))

    def test_non_discriminative_bank_refuses_calibration(self):
        other_path = Path(self.tmp.name) / "duplicates.db"
        with ModelBank(self.path, self.seed) as old, ModelBank(other_path, self.seed) as new:
            original = old.get("original")
            new.save("original", original, 50)
            new.save("changed", original, 50)
            with self.assertRaises(ValueError):
                calibrate(new, self.evidence())

    def test_independent_calibration_is_bit_reproducible(self):
        with ModelBank(self.path, self.seed) as bank:
            first = calibrate(bank, self.evidence())
            second = calibrate(bank, self.evidence())
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
