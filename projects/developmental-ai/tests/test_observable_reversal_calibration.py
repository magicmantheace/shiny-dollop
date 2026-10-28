"""Independent train-calibration and public-only reversal selection tests."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.observable_affordances import (
    ObservableWorld, NumericOutcomeMemory, digest
)
from developmental_ai.observable_reversal_calibration import (
    OutcomeCalibration, PROBES, MIN_PROBES, MIN_MARGIN,
)
from benchmarks.observable_reversal_calibration_benchmark import (
    DEV, RESERVED, WORLDS, TRAIN_N, CALIBRATION_N, TEST_N,
    fit, fit_reversed, calibrate, score_policy, measure,
)


class ObservableReversalCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,_=fit(cls.seed)
        cls.changed,_=fit_reversed(cls.seed)
        cls.cal={}
        for domain in WORLDS:
            _,cls.cal[domain]=calibrate(cls.seed,domain,cls.source,cls.changed)

    def test_public_probe_frame_contains_no_physics_domain_or_answer(self):
        frame=ObservableWorld(self.seed,"train",900,"route-reversed").frame()
        self.assertEqual(set(frame),{"schema","episode","tick","budget",
                                     "sensors","goal","actions","done"})
        for forbidden in ("domain","reverse","harmful","correct_action"):
            self.assertNotIn(forbidden,str(frame))
        agent=OutcomeCalibration(self.source,self.changed)
        self.assertIn(agent.probe(frame),{row["id"] for row in frame["actions"]})

    def test_calibration_uses_observed_action_effect_only(self):
        for domain in WORLDS:
            decision=self.cal[domain]["decision"]
            self.assertEqual(decision["probes"],CALIBRATION_N)
            self.assertIn(decision["chosen"],("source","changed","abstain"))
            self.assertGreaterEqual(self.cal[domain]["harmful_calibration_probes"],0)

    def test_paired_training_is_disjoint_from_calibration_and_eval(self):
        self.assertEqual((TRAIN_N,CALIBRATION_N,TEST_N),(80,12,60))
        self.assertEqual(PROBES,CALIBRATION_N)
        self.assertEqual(MIN_PROBES,4)
        self.assertEqual(MIN_MARGIN,2.)
        self.assertEqual(self.source.record(),
                         NumericOutcomeMemory.restore(self.source.record()).record())
        self.assertEqual(self.changed.record(),
                         NumericOutcomeMemory.restore(self.changed.record()).record())

    def test_checkpoint_replays_model_selection_and_detects_tampering(self):
        learner=OutcomeCalibration(self.source,self.changed)
        for i in range(5):
            world=ObservableWorld(self.seed,"train",900+i,"route-reversed")
            before=world.frame()
            action=learner.probe(before)
            after=world.step(action,before["tick"])
            learner.observe(before,action,after)
        saved=learner.record()
        replica=OutcomeCalibration.restore(self.source,self.changed,copy.deepcopy(saved))
        self.assertEqual(replica.record(),saved)
        forged=copy.deepcopy(saved)
        forged["state"]["decision"]["chosen"]="source"
        forged["sha256"]=digest(forged["state"])
        with self.assertRaises(ValueError):
            OutcomeCalibration.restore(self.source,self.changed,forged)

    def test_wrong_training_memory_rejects_calibration_checkpoint(self):
        learner=OutcomeCalibration(self.source,self.changed)
        world=ObservableWorld(self.seed,"train",900,"route")
        before=world.frame()
        chosen=learner.probe(before)
        learner.observe(before,chosen,world.step(chosen,before["tick"]))
        different,_=fit_reversed(DEV[1])
        with self.assertRaisesRegex(ValueError,"different learned memories"):
            OutcomeCalibration.restore(self.source,different,learner.record())

    def test_repeat_calibration_episode_and_wrong_action_rejected(self):
        learner=OutcomeCalibration(self.source,self.changed)
        world=ObservableWorld(self.seed,"train",901,"route")
        before=world.frame()
        correct=learner.probe(before)
        wrong=next(row["id"] for row in before["actions"] if row["id"]!=correct)
        after=world.step(correct,before["tick"])
        with self.assertRaises(ValueError):
            learner.observe(before,wrong,after)
        learner.observe(before,correct,after)
        with self.assertRaises(ValueError):
            learner.probe(before)

    def test_calibration_does_not_mutate_training_evidence(self):
        original=(self.source.record(),self.changed.record())
        for domain in WORLDS:
            score_policy(self.seed,domain,"offline_selected",
                         self.source,self.changed,self.cal)
            score_policy(self.seed,domain,"wrong_calibration",
                         self.source,self.changed,self.cal)
        self.assertEqual(original,(self.source.record(),self.changed.record()))

    def test_wrong_calibration_and_abstention_are_explicit_controls(self):
        for domain in WORLDS:
            baseline=score_policy(self.seed,domain,"always_abstain",
                                  self.source,self.changed,self.cal)
            self.assertEqual(baseline["successes"],0)
            self.assertEqual(baseline["hurt"],0)
            self.assertEqual(baseline["stalled"],TEST_N)
            self.assertEqual(baseline["mean_attempts"],0)
            privileged=score_policy(self.seed,domain,"oracle",
                                    self.source,self.changed,self.cal)
            self.assertEqual(privileged["successes"],TEST_N)
            self.assertEqual(privileged["hurt"],0)

    def test_no_cohort_substitution(self):
        for invalid in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)


if __name__=="__main__":
    unittest.main()
