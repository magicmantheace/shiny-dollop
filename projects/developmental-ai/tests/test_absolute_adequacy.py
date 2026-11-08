"""Public adequacy under noisy known and rule-three outcomes."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.observable_affordances import check,digest,NumericOutcomeMemory
from developmental_ai.novel_feature_world import NovelFeatureWorld,CONDITIONS
from developmental_ai.absolute_adequacy import AbsoluteAdequacy,inspect_window
from benchmarks.observable_affordance_benchmark import fit
from benchmarks.observable_reversal_calibration_benchmark import fit_reversed
from benchmarks.absolute_adequacy_benchmark import (
    DEV,RESERVED,CALIBRATION_N,TEST_N,calibrate,episode,measure
)


class AbsoluteAdequacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.src,_=fit(cls.seed)
        cls.changed,_=fit_reversed(cls.seed)

    def test_frames_public_and_no_rule_identity(self):
        for condition in CONDITIONS:
            frame=NovelFeatureWorld(self.seed,"train",2000,condition).frame()
            self.assertIs(check(frame),frame)
            self.assertEqual(set(frame),{"schema","episode","tick","budget",
                                         "goal","sensors","actions","done"})
            for secret in ("third_rule","noisy","domain","true_outcome"):
                self.assertNotIn(secret,str(frame))

    def test_equal_initial_features_and_feasible_goal_for_three_laws(self):
        worlds=[NovelFeatureWorld(self.seed,"test",22000,condition)
                for condition in CONDITIONS]
        self.assertEqual([w.frame() for w in worlds],[worlds[0].frame()]*3)
        for w in worlds:
            progress=[a for a in w._features if w._effect(a)=="progress"]
            if w.condition=="third_rule":
                self.assertEqual(len(progress),4)
            else:
                self.assertLessEqual(len(progress),4)

    def test_public_probe_validation_and_replay(self):
        obj=AbsoluteAdequacy(self.src,self.changed)
        for i in range(CALIBRATION_N):
            w=NovelFeatureWorld(self.seed,"train",2000+i,"third_rule")
            before=w.frame();action=obj.probe(before)
            after=w.step(action,before["tick"])
            obj.observe(before,action,after)
        record=obj.record("adequacy8")
        restored=AbsoluteAdequacy.restore(self.src,self.changed,copy.deepcopy(record))
        self.assertEqual(restored.record("adequacy8"),record)
        corrupted=copy.deepcopy(record)
        corrupted["state"]["decision"]["selected"]="source"
        corrupted["sha256"]=digest(corrupted["state"])
        with self.assertRaises(ValueError):
            AbsoluteAdequacy.restore(self.src,self.changed,corrupted)

    def test_no_unobserved_new_rule_training(self):
        old=(self.src.record(),self.changed.record())
        for condition in CONDITIONS:
            agent,cal=calibrate(self.seed,condition,self.src,self.changed)
            self.assertEqual(cal["probes"],8)
            self.assertGreaterEqual(cal["calibration_damage"],0)
            self.assertIn(agent.decision("adequacy8")["selected"],
                          ("source","changed","unknown","abstain"))
        self.assertEqual(old,(self.src.record(),self.changed.record()))

    def test_abstention_zero_harm_but_no_task_completion(self):
        for condition in CONDITIONS:
            row=episode(self.seed,condition,22000,"abstain",self.src,self.changed)
            self.assertEqual(row,{"success":0,"hurt":0,"stalled":1,"attempts":0})

    def test_third_rule_is_solvable_by_privileged_oracle(self):
        for index in range(5):
            result=episode(self.seed,"third_rule",22000+index,
                           "oracle",self.src,self.changed)
            self.assertEqual(result["success"],1)
            self.assertEqual(result["hurt"],0)

    def test_untrusted_checkpoint_belongs_to_training_memories(self):
        original, _=calibrate(self.seed,"third_rule",self.src,self.changed)
        alternate,_=fit_reversed(DEV[1])
        with self.assertRaisesRegex(ValueError,"different learned memories"):
            AbsoluteAdequacy.restore(self.src,alternate,original.record("adequacy8"))

    def test_frozen_seed_lists_and_indices(self):
        self.assertEqual((CALIBRATION_N,TEST_N),(8,60))
        for wrong in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(wrong)


if __name__=="__main__":
    unittest.main()
