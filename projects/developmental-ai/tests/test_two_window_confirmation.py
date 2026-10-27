"""Public-only two-window confirmation regression and negative controls."""
from __future__ import annotations
import copy
import unittest

from developmental_ai.observable_affordances import ObservableWorld, digest
from developmental_ai.two_window_confirmation import TwoWindowConfirmation
from benchmarks.observable_affordance_benchmark import DEV, RESERVED, fit
from benchmarks.observable_reversal_calibration_benchmark import fit_reversed
from benchmarks.two_window_confirmation_benchmark import (
    calibration,evaluation,schedule,target_world,CONDITIONS,METHODS,CAL_MAX,TEST_N,measure,
)


class TwoWindowConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,_=fit(cls.seed)
        cls.changed,_=fit_reversed(cls.seed)

    def test_public_frames_exclude_hidden_switch_labels(self):
        for condition in CONDITIONS:
            for i in (0,4):
                frame=ObservableWorld(self.seed,"train",960+i,schedule(condition,i)).frame()
                self.assertEqual(set(frame),{"schema","episode","tick","budget",
                                             "sensors","goal","actions","done"})
                for private in ("world","reverse","domain","correct"):
                    self.assertNotIn(private,str(frame))

    def test_changed_physics_only_at_window_boundary(self):
        self.assertEqual([schedule("normal_to_reversed",i) for i in range(8)],
                         ["route"]*4+["route-reversed"]*4)
        self.assertEqual([schedule("reversed_to_normal",i) for i in range(8)],
                         ["route-reversed"]*4+["route"]*4)

    def test_probes_count_damage_and_never_succeed_by_abstention(self):
        for condition in CONDITIONS:
            a=calibration(self.seed,condition,"confirmed8",self.source,self.changed)
            self.assertEqual(a["probes"],8)
            self.assertGreaterEqual(a["harm"],0)
            r=evaluation(self.seed,condition,"abstain",self.source,self.changed)
            self.assertEqual(r["successes"],0)
            self.assertEqual(r["hurt"],0)
            self.assertEqual(r["stalled"],TEST_N)

    def test_each_method_preserves_train_only_models(self):
        old=(self.source.record(),self.changed.record())
        for condition in CONDITIONS:
            for method in METHODS:
                calibration(self.seed,condition,method,self.source,self.changed)
        self.assertEqual(old,(self.source.record(),self.changed.record()))

    def test_stopping_and_confirmation_replay_exactly(self):
        for method in ("early4","confirmed8","recent8","cumulative8"):
            learner=TwoWindowConfirmation(self.source,self.changed)
            for i in range(4 if method=="early4" else CAL_MAX):
                world=ObservableWorld(self.seed,"train",960+i,
                                      schedule("normal_to_reversed",i))
                before=world.frame();action=learner.choose(before)
                after=world.step(action,before["tick"])
                learner.feedback(before,action,after)
            saved=learner.record(method)
            restored=TwoWindowConfirmation.restore(self.source,self.changed,
                                                   copy.deepcopy(saved))
            self.assertEqual(restored.record(method),saved)
            broken=copy.deepcopy(saved)
            broken["state"]["decision"]["choice"]="oracle"
            broken["sha256"]=digest(broken["state"])
            with self.assertRaises(ValueError):
                TwoWindowConfirmation.restore(self.source,self.changed,broken)

    def test_eight_window_disagreement_abstains_in_shift(self):
        for condition in ("normal_to_reversed","reversed_to_normal"):
            row=calibration(self.seed,condition,"confirmed8",self.source,self.changed)
            self.assertEqual(row["chosen"],"abstain")
            self.assertTrue(row["contradiction"])
            self.assertEqual(row["first"]["samples"],4)
            self.assertEqual(row["recent"]["samples"],4)

    def test_uncertain_checkpoint_rejects_wrong_memory(self):
        learner=TwoWindowConfirmation(self.source,self.changed)
        for i in range(4):
            w=ObservableWorld(self.seed,"train",960+i,"route")
            frame=w.frame();choice=learner.choose(frame)
            learner.feedback(frame,choice,w.step(choice,frame["tick"]))
        wrong,_=fit_reversed(DEV[1])
        with self.assertRaisesRegex(ValueError,"different learned memories"):
            TwoWindowConfirmation.restore(self.source,wrong,learner.record("early4"))

    def test_frozen_cohorts_and_bounds(self):
        self.assertEqual(TEST_N,60)
        self.assertEqual(CAL_MAX,8)
        for invalid in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)
        with self.assertRaises(ValueError):
            calibration(self.seed,"missing","recent8",self.source,self.changed)
        with self.assertRaises(ValueError):
            TwoWindowConfirmation(self.source,self.changed).decision("recent8")


if __name__=="__main__":
    unittest.main()
