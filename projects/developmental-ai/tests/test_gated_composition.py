"""Regressions: conditional assembly, XOR absence, public replay and controls."""
from __future__ import annotations

import copy
import math
import unittest

from developmental_ai.gated_composition_memory import (
    GatedCompositionMemory, branch, TAIL, FIT_WINDOW,
    GATE_PENALTY, MIN_SCORED_PER_BRANCH,
)
from developmental_ai.composed_feature_memory import PROGRAMS
from developmental_ai.observable_affordances import digest
from benchmarks.gated_composition_benchmark import (
    DEV, ADDITIONAL, STAGES, CHECKPOINTS, START, TEST_N, METHODS,
    TRUE_LOW, TRUE_HIGH, ConditionalWorld, effect, training,
    train_models, evaluate, measure,
)


class GatedCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.cost=training(cls.seed,"source",1000,240)

    def test_comparison_gate_and_two_distinct_existing_quadratic_bases(self):
        self.assertEqual(branch({"inlet":8,"outlet":3}),1)
        self.assertEqual(branch({"inlet":3,"outlet":8}),0)
        self.assertEqual(branch({"inlet":3,"outlet":3}),0)
        self.assertIn(TRUE_LOW,PROGRAMS)
        self.assertIn(TRUE_HIGH,PROGRAMS)
        self.assertNotEqual(TRUE_LOW,TRUE_HIGH)
        self.assertEqual(len(PROGRAMS),48)

    def test_target_conditional_law_not_old_global_rule(self):
        a=ConditionalWorld(self.seed,"test",290000,"source")
        b=ConditionalWorld(self.seed,"test",290000,"conditional")
        x=ConditionalWorld(self.seed,"test",310000,"xor")
        for w in (a,b,x):
            frame=w.frame()
            self.assertEqual(len(frame["actions"]),12)
            self.assertEqual(set(frame["actions"][0]["features"]),
                             {"inlet","outlet"})
            self.assertEqual({
                cls:sum(w._effect(item["features"])==cls
                        for item in frame["actions"])
                for cls in ("progress","damage","neutral")},
                {"progress":5,"damage":4,"neutral":3})
            for token in ('"conditional"','"xor"','"law"'):
                self.assertNotIn(token,str(frame))
        pairs=[{"inlet":i,"outlet":j}
               for i in range(10) for j in range(10)]
        self.assertTrue(any(effect(self.seed,"conditional",f)!=
                            effect(self.seed,"source",f) for f in pairs))
        self.assertTrue(any(effect(self.seed,"xor",f)!=
                            effect(self.seed,"source",f) for f in pairs))

    def test_public_training_actor_is_deterministic_and_not_learner(self):
        first,cost=training(self.seed,"conditional",2000,24)
        self.assertEqual((first,cost),
                         training(self.seed,"conditional",2000,24))
        self.assertEqual(cost["observations"],24)
        self.assertEqual(sum(cost[k] for k in
                             ("harmful","productive","neutral")),24)
        self.assertEqual(set(first[0]),{"features","progress","damage"})

    def test_prequential_selection_separates_fit_and_scored_rows(self):
        model=GatedCompositionMemory()
        for row in self.source:
            model.observe(row)
        report,predictor=model.selection()
        self.assertIn(report["selected"],("global","conditional"))
        self.assertEqual(report["scoring_examples"],16)
        self.assertEqual(report["scored_event_fit_overlap"],0)
        self.assertEqual(report["generated_programs"],48)
        self.assertEqual(sum(report["branch_scoring_counts"]),16)
        self.assertTrue(math.isfinite(report["global_prequential"]))
        self.assertTrue(math.isfinite(report["conditional_penalized_prequential"]))
        self.assertEqual(report["recorded_events"],240)

    def test_checkpoint_replay_and_test_selection_read_only(self):
        learner=GatedCompositionMemory()
        for event in self.source:
            learner.observe(event)
        for event in training(self.seed,"conditional",2000,32)[0]:
            learner.observe(event)
        saved=learner.record()
        rebuilt=GatedCompositionMemory.restore(copy.deepcopy(saved))
        frame=ConditionalWorld(self.seed,"test",290000,"conditional").frame()
        self.assertEqual(learner.choose(frame),rebuilt.choose(frame))
        self.assertEqual(learner.selection()[0],rebuilt.selection()[0])
        self.assertEqual(learner.record(),saved)
        self.assertFalse(hasattr(learner,"step"))

    def test_invalid_public_keys_and_invalid_rehashed_checkpoint_refused(self):
        learner=GatedCompositionMemory()
        learner.observe(self.source[0])
        saved=learner.record()
        with self.assertRaises(ValueError):
            learner.observe({"features":{"unknown":0,"outlet":3},
                             "progress":True,"damage":False})
        self.assertEqual(learner.record(),saved)
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["progress"]=True
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            GatedCompositionMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            GatedCompositionMemory.restore(bad)

    def test_all_frozen_baselines_and_abstention_failures(self):
        policies=train_models(self.source)
        snapshot=policies["gated_composition"].record()
        for name in METHODS:
            record=evaluate(self.seed,"conditional",290000,name,policies)
            self.assertIn(record["success"],(0,1))
            self.assertIn(record["harmful_actions"],(0,1))
            if name=="abstain":
                self.assertEqual((record["success"],record["abstained"]),(0,1))
        self.assertEqual(snapshot,policies["gated_composition"].record())

    def test_registered_study_contracts(self):
        self.assertEqual((TAIL,FIT_WINDOW,GATE_PENALTY,MIN_SCORED_PER_BRANCH),
                         (16,64,2.0,3))
        self.assertEqual(TEST_N,16)
        self.assertEqual(START,{"conditional":290000,
                                 "return_source":300000,"xor":310000})
        self.assertEqual([item[0] for item in STAGES],
                         ["source","conditional","return_source","xor"])
        self.assertEqual(CHECKPOINTS["xor"],(0,4,8,16,32,64,96,128))
        self.assertEqual(len(METHODS),10)
        self.assertNotEqual(DEV,ADDITIONAL)
        for wrong in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(wrong)


if __name__=="__main__":
    unittest.main()
