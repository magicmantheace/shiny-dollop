"""Sequential calibration and staged-shift audit regression tests."""
from __future__ import annotations

import unittest

from developmental_ai.observable_affordances import NumericOutcomeMemory
from benchmarks.observable_reversal_calibration_benchmark import fit_reversed
from benchmarks.observable_affordance_benchmark import DEV, RESERVED, fit
from benchmarks.sequential_probe_benchmark import (
    METHODS, TEST_N, EARLIEST, CAL_MAX,
    calibrate, evaluate, measure
)


class SequentialCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,_=fit(cls.seed)
        cls.changed,_=fit_reversed(cls.seed)

    def test_sequential_writes_public_replayable_evidence_only(self):
        row=calibrate(self.seed,"route",self.source,self.changed,"adaptive_stop")
        self.assertIn(row["choice"],("source","changed","abstain"))
        self.assertGreaterEqual(row["probes"],EARLIEST)
        self.assertLessEqual(row["probes"],CAL_MAX)
        self.assertEqual(len(row["sha256"]),64)

    def test_original_twelve_probe_budget_is_unchanged(self):
        for world in ("route","route-reversed"):
            row=calibrate(self.seed,world,self.source,self.changed,"fixed12")
            self.assertEqual(row["probes"],CAL_MAX)

    def test_forced_four_and_adaptive_probe_budgets(self):
        for world in ("route","route-reversed"):
            forced=calibrate(self.seed,world,self.source,self.changed,"forced4")
            adaptive=calibrate(self.seed,world,self.source,self.changed,"adaptive_stop")
            self.assertEqual(forced["probes"],EARLIEST)
            self.assertGreaterEqual(adaptive["probes"],forced["probes"])
            self.assertLessEqual(adaptive["probes"],CAL_MAX)

    def test_adverse_intervention_shift_is_named_benchmark_only(self):
        for mode in ("stale_shift_adaptive","stale_shift_fixed12"):
            row=calibrate(self.seed,"route-reversed",self.source,self.changed,mode)
            self.assertGreaterEqual(row["probes"],EARLIEST)
            self.assertLessEqual(row["probes"],CAL_MAX)
            self.assertGreaterEqual(row["calibration_harm"],0)

    def test_zero_action_abstention_not_credit_for_task_completion(self):
        for world in ("route","route-reversed"):
            row=evaluate(self.seed,world,"abstain",self.source,self.changed)
            self.assertEqual(row["successes"],0)
            self.assertEqual(row["stalled"],TEST_N)
            self.assertEqual(row["hurt"],0)
            self.assertEqual(row["mean_attempts"],0)

    def test_privileged_upper_bound_is_feasible(self):
        for world in ("route","route-reversed"):
            ref=evaluate(self.seed,world,"oracle",self.source,self.changed)
            self.assertEqual(ref["successes"],TEST_N)
            self.assertEqual(ref["hurt"],0)

    def test_all_modes_preserve_source_and_changed_evidence(self):
        old=(self.source.record(),self.changed.record())
        for world in ("route","route-reversed"):
            for mode in METHODS[:5]:
                calibrate(self.seed,world,self.source,self.changed,mode)
        self.assertEqual(old,(self.source.record(),self.changed.record()))
        self.assertEqual(NumericOutcomeMemory.restore(old[0]).record(),old[0])

    def test_seed_and_method_validation(self):
        self.assertEqual(TEST_N,60)
        for bad in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(bad)
        with self.assertRaises(ValueError):
            calibrate(self.seed,"unknown",self.source,self.changed,"adaptive_stop")
        with self.assertRaises(ValueError):
            calibrate(self.seed,"route",self.source,self.changed,"oracle")


if __name__=="__main__":
    unittest.main()
