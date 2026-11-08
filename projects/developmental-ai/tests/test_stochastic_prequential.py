"""Prequential scoring separation, stochastic hidden feedback, replay and harms."""
from __future__ import annotations

import copy
import math
import unittest

from developmental_ai.prequential_ensemble_memory import (
    PrequentialEnsembleMemory, SOURCE, WARMUP, VALIDATION,
    WINDOWS, PRIOR, TEMPERATURE,
)
from developmental_ai.observable_affordances import digest
from benchmarks.stochastic_prequential_benchmark import (
    DEV,ADDITIONAL,STAGES,CHECKPOINTS,TEST_START,TEST_N,
    METHODS,StochasticWorld,public_train,trained_models,evaluate,measure,
)


def example(outcome,span=5):
    return {"features":{"inlet":0,"outlet":span},
            "progress":outcome=="progress","damage":outcome=="damage"}


class PrequentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.cost=public_train(cls.seed,"original",1000,240)

    def test_weights_are_finite_and_respect_historical_source(self):
        model=PrequentialEnsembleMemory()
        for row in self.source:
            model.observe(row)
        decision,weights,candidates=model.selection()
        self.assertEqual(decision["candidates"],
                         ["source192","recent8","recent32"])
        self.assertEqual(decision["predictive_scoring_events"],8)
        self.assertEqual(decision["scoring_fit_overlap"],0)
        self.assertEqual(len(weights),3)
        self.assertAlmostEqual(sum(weights),1.0,places=12)
        self.assertTrue(all(math.isfinite(x) and 0<x<1 for x in weights))
        self.assertEqual(len(candidates[0].events),SOURCE)
        self.assertEqual(len(candidates[1].events),8)
        self.assertEqual(len(candidates[2].events),32)
        self.assertNotIn("stage",str(model.record()))
        self.assertEqual(set(model.events[0]),{"features","progress","damage"})

    def test_new_feedback_invalidates_cached_prequential_evidence(self):
        model=PrequentialEnsembleMemory()
        for row in self.source:
            model.observe(row)
        old=model.selection()
        self.assertIs(old,model.selection())
        model.observe(example("damage"))
        new=model.selection()
        self.assertIsNot(new,old)
        self.assertEqual(new[0]["trained_events"],241)

    def test_strict_replay_and_read_only_choice(self):
        model=PrequentialEnsembleMemory()
        for row in self.source:
            model.observe(row)
        for row in public_train(self.seed,"reversed",2000,8)[0]:
            model.observe(row)
        saved=model.record()
        restored=PrequentialEnsembleMemory.restore(copy.deepcopy(saved))
        frame=StochasticWorld(self.seed,"test",160000,"reversed").frame()
        self.assertEqual(model.choose(frame),restored.choose(frame))
        self.assertEqual(model.selection()[0],restored.selection()[0])
        self.assertEqual(model.record(),saved)
        self.assertFalse(hasattr(model,"step"))

    def test_reject_unknown_schema_or_invalid_rehashed_evidence(self):
        model=PrequentialEnsembleMemory()
        model.observe(example("progress"))
        saved=model.record()
        with self.assertRaises(ValueError):
            model.observe({"features":{"not_inlet":0,"outlet":5},
                           "progress":True,"damage":False})
        self.assertEqual(model.record(),saved)
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            PrequentialEnsembleMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            PrequentialEnsembleMemory.restore(bad)

    def test_actual_stochastic_outcomes_reproducible_and_visible_frame_stable(self):
        first=StochasticWorld(self.seed,"test",160000,"original")
        reverse=StochasticWorld(self.seed,"test",160000,"reversed")
        self.assertEqual(first.frame(),reverse.frame())
        self.assertEqual(first.frame()["actions"],reverse.frame()["actions"])
        flipped=0
        for idx in range(160000,160025):
            a=StochasticWorld(self.seed,"test",idx,"original")
            for action in a.frame()["actions"]:
                original=a._effect(action["features"])
                sampled=a._sample_outcome(action["id"],0)
                if sampled!=original:
                    flipped+=1
                self.assertEqual(sampled,
                    StochasticWorld(self.seed,"test",idx,"original")
                    ._sample_outcome(action["id"],0))
        self.assertGreater(flipped,0)
        self.assertLess(flipped,25*12)

    def test_actor_real_harm_and_reports_are_distinct(self):
        source,cost=public_train(self.seed,"original",1000,240)
        self.assertEqual(len(source),240)
        self.assertEqual((source,cost),
                         public_train(self.seed,"original",1000,240))
        self.assertGreater(cost["label_flips"],0)
        self.assertEqual(cost["actual_harmful"]+
                         cost["actual_productive"]+
                         cost["actual_neutral"],240)
        self.assertEqual(sum(int(e["damage"]) for e in source),
                         cost["reported_harmful"])
        self.assertNotIn("actual_harmful",str(source))

    def test_readonly_matched_test_baselines_and_abstentions(self):
        fitted=trained_models(self.source)
        checkpoint=fitted["prequential_ensemble"].record()
        for method in METHODS:
            outcome=evaluate(self.seed,"reversed",160000,method,fitted)
            self.assertIn(outcome["success"],(0,1))
            self.assertIn(outcome["harmful_actions"],(0,1))
            if method=="always_abstain":
                self.assertEqual(outcome["success"],0)
                self.assertEqual(outcome["abstained"],1)
        self.assertEqual(fitted["prequential_ensemble"].record(),checkpoint)

    def test_frozen_cohorts_and_counters(self):
        self.assertEqual((SOURCE,WARMUP,VALIDATION,WINDOWS,
                          PRIOR,TEMPERATURE),
                         (192,240,8,(8,32),(-0.4,0.0,0.2),2.0))
        self.assertEqual(TEST_N,16)
        self.assertEqual(TEST_START,{"B1":160000,"return_A":170000,
                                     "B2":180000})
        self.assertEqual(len(METHODS),10)
        self.assertEqual([x[0] for x in STAGES],
                         ["A","B1","return_A","B2"])
        self.assertEqual(CHECKPOINTS["B1"],
                         (0,2,4,8,12,24,32,64))
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
