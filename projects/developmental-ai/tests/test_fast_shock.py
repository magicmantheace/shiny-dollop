"""Fast surprise policy: replay, same-schema boundary, and early harm controls."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.fast_shock_memory import (
    FastShockMemory,ANCHOR,RECENT,SURPRISE_WINDOW,SURPRISE_PROBABILITY
)
from developmental_ai.observable_affordances import digest
from benchmarks.fast_shock_benchmark import (
    DEV,ADDITIONAL,CHECKPOINTS,TEST_N,TEST_START,METHODS,
    models,eval_trial,measure
)
from benchmarks.same_schema_switch_benchmark import SameSchemaWorld,training


def example(progress):
    return {"features":{"inlet":0,"outlet":5},
            "progress":progress,"damage":not progress}


class FastShockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source=training(cls.seed,"original",1000,240)

    def test_shock_on_identical_feature_keys_without_phase(self):
        m=FastShockMemory()
        for _ in range(240):m.observe(example(True))
        self.assertEqual(m.selection()[0]["source"],"anchor")
        for _ in range(4):m.observe(example(False))
        state,model=m.selection()
        self.assertEqual(state["source"],"recent")
        self.assertEqual(state["last4_unexpected"],4)
        self.assertEqual(state["recent_selection_training_overlap"],8)
        self.assertTrue(model.estimate({"inlet":0,"outlet":5})["damage"]>0.4)
        for _ in range(4):m.observe(example(True))
        self.assertEqual(m.selection()[0]["source"],"anchor")

    def test_one_surprise_not_automatically_overturn_archive(self):
        m=FastShockMemory()
        for _ in range(240):m.observe(example(True))
        m.observe(example(False))
        plan,_=m.selection()
        self.assertEqual(plan["source"],"anchor")
        self.assertEqual(plan["last4_unexpected"],1)

    def test_replay_unchanged_and_predict_action_read_only(self):
        m=FastShockMemory()
        for row in self.source:m.observe(row)
        frame=SameSchemaWorld(self.seed,"test",80000,"reversed").frame()
        saved=m.record()
        restored=FastShockMemory.restore(copy.deepcopy(saved))
        self.assertEqual(m.choose(frame),restored.choose(frame))
        self.assertEqual(restored.record(),saved)
        self.assertEqual(m.record(),saved)
        self.assertFalse(hasattr(m,"step"))
        self.assertFalse(hasattr(m,"probe"))

    def test_reject_change_in_observation_schema_without_partial_write(self):
        m=FastShockMemory()
        m.observe(example(True))
        record=m.record()
        with self.assertRaises(ValueError):
            m.observe({"features":{"inlet":0,"another":5},
                       "progress":True,"damage":False})
        self.assertEqual(m.record(),record)

    def test_rejects_invalid_digest_even_if_rehashed_invalid_evidence(self):
        m=FastShockMemory()
        m.observe(example(True))
        orig=m.record()
        bad=copy.deepcopy(orig)
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):FastShockMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):FastShockMemory.restore(bad)

    def test_frozen_training_source_and_no_inferred_change_labels(self):
        m=FastShockMemory()
        for row in self.source:m.observe(row)
        state=m.record()["state"]
        self.assertEqual(set(state),{"schema","events"})
        self.assertEqual(set(state["events"][0]),{"features","progress","damage"})
        for forbidden in ('"B"','"return_A"','"stage"','"physics"','"episode"'):
            self.assertNotIn(forbidden,str(state))

    def test_existing_legacy_and_recent_models_unchanged(self):
        fitted=models(self.source)
        self.assertEqual(set(fitted),{"fast_shock","legacy_disjoint_12plus4",
                                     "recent8","recent32","frozen_A","cumulative_range"})
        archive=fitted["fast_shock"].record()
        for method in METHODS:
            score=eval_trial(self.seed,"original",80000,method,fitted)
            self.assertIn(score["success"],(0,1))
            self.assertIn(score["harmful_actions"],(0,1))
            if method=="always_abstain":
                self.assertEqual((score["abstained"],score["success"]),(1,0))
        self.assertEqual(fitted["fast_shock"].record(),archive)

    def test_same_visible_frame_yields_different_rule_results(self):
        good=SameSchemaWorld(self.seed,"test",80000,"original")
        bad=SameSchemaWorld(self.seed,"test",80000,"reversed")
        self.assertEqual(good.frame(),bad.frame())
        pick=next(a["id"] for a in good.frame()["actions"]
                  if good._effect(a["features"])=="progress")
        self.assertEqual(good.step(pick,0)["progress"],1)
        self.assertEqual(bad.step(pick,0)["damage"],1)

    def test_precommitted_cohorts_indices_and_limits(self):
        self.assertEqual((ANCHOR,RECENT,SURPRISE_WINDOW,SURPRISE_PROBABILITY),
                         (192,8,4,0.125))
        self.assertEqual(TEST_N,30)
        self.assertEqual(TEST_START,{"B":80000,"return_A":90000})
        self.assertEqual(CHECKPOINTS["B"],(0,2,4,6,8,12,16,24,32,48,64))
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):measure(invalid)


if __name__=="__main__":
    unittest.main()
