"""Compositional hypothesis synthesis under privately different nonlinear laws."""
from __future__ import annotations

import copy
import math
import unittest

from developmental_ai.composed_feature_memory import (
    ComposedFeatureMemory,_ComposedBucket,PROGRAMS,MODEL_NAMES,
    bucket_for,SOURCE,WARMUP,RECENT_TRAIN,ACTION_TRAIN,TAIL,
)
from developmental_ai.observable_affordances import digest
from benchmarks.composed_feature_benchmark import (
    DEV,ADDITIONAL,STAGES,CHECKPOINTS,TEST_START,TEST_N,METHODS,
    TRUE_COMPOSITIONS,ComposedWorld,effect,training,models,evaluate,measure
)


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.cost=training(cls.seed,"source",1000,240)

    def test_generated_generic_programs_contain_but_do_not_name_true_formulas(self):
        self.assertEqual(len(PROGRAMS),48)
        self.assertEqual(len(MODEL_NAMES),52)
        for name,hidden in TRUE_COMPOSITIONS.items():
            self.assertIn(hidden,PROGRAMS)
            self.assertNotIn(name,MODEL_NAMES)
        self.assertEqual(bucket_for(((0,1),0,1,1,7),
                                    {"inlet":3,"outlet":4}),(3*4+3)%7)
        self.assertEqual(bucket_for(((0,0),1,1,1,5),
                                    {"inlet":3,"outlet":4}),(3*3+4)%5)

    def test_non_linear_true_rule_cannot_be_expressed_by_old_affine_grammar(self):
        for law in ("product","square"):
            entries={(a,b):effect(self.seed,law,{"inlet":a,"outlet":b})
                     for a in range(10) for b in range(10)}
            self.assertGreater(len(set(entries.values())),2)
            self.assertTrue(any(
                entries[a,b]!=entries[b,a]
                for a in range(10) for b in range(10)))
            self.assertTrue(any(
                entries[a,b]!=effect(self.seed,"source",
                                     {"inlet":a,"outlet":b})
                for a in range(10) for b in range(10)))

    def test_public_frame_unchanged_across_hidden_compositions(self):
        for law in ("source","product","square"):
            world=ComposedWorld(self.seed,"test",260000,law)
            frame=world.frame()
            self.assertEqual(len(frame["actions"]),12)
            self.assertEqual(set(frame["actions"][0]["features"]),
                             {"inlet","outlet"})
            self.assertEqual({category:sum(
                world._effect(action["features"])==category
                for action in frame["actions"])
                for category in ("progress","damage","neutral")},
                {"progress":5,"damage":4,"neutral":3})
            for forbidden in ('"product"','"square"','"law"'):
                self.assertNotIn(forbidden,str(frame))

    def test_only_public_feedback_training_and_real_actor_costs(self):
        for law,start in (("source",1000),("product",2000),("square",4000)):
            stream,cost=training(self.seed,law,start,16)
            self.assertEqual(len(stream),16)
            self.assertEqual(sum(cost[x] for x in
                                 ("harmful","productive","neutral")),16)
            self.assertEqual(set(stream[0]),{"features","progress","damage"})
            self.assertEqual(training(self.seed,law,start,16),(stream,cost))

    def test_prequential_fit_disjoint_and_checkpoint_replay(self):
        m=ComposedFeatureMemory()
        for event in self.source:
            m.observe(event)
        selection,learner=m.selection()
        self.assertEqual(selection["scoring_events"],12)
        self.assertEqual(selection["scoring_fit_overlap"],0)
        self.assertEqual(selection["generated_program_count"],48)
        self.assertIn(selection["selected"],MODEL_NAMES)
        self.assertTrue(math.isfinite(selection["prequential_score"]))
        saved=m.record()
        restored=ComposedFeatureMemory.restore(copy.deepcopy(saved))
        frame=ComposedWorld(self.seed,"test",260000,"product").frame()
        self.assertEqual(m.choose(frame),restored.choose(frame))
        self.assertEqual(m.selection()[0],restored.selection()[0])
        self.assertEqual(m.record(),saved)
        self.assertEqual(restored.record(),saved)
        self.assertFalse(hasattr(m,"step"))

    def test_corrupt_event_and_unknown_keys_cannot_mutate_saved_evidence(self):
        m=ComposedFeatureMemory()
        m.observe(self.source[0])
        checkpoint=m.record()
        with self.assertRaises(ValueError):
            m.observe({"features":{"wrong":1,"other":2},
                       "progress":True,"damage":False})
        self.assertEqual(m.record(),checkpoint)
        bad=copy.deepcopy(checkpoint)
        bad["state"]["events"][0]["progress"]=True
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            ComposedFeatureMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            ComposedFeatureMemory.restore(bad)

    def test_readonly_competitors_and_abstention_accounting(self):
        trained=models(self.source)
        snap=trained["composed_grammar"].record()
        for method in METHODS:
            scored=evaluate(self.seed,"product",260000,method,trained)
            self.assertIn(scored["success"],(0,1))
            self.assertIn(scored["harmful_actions"],(0,1))
            if method=="always_abstain":
                self.assertEqual((scored["success"],scored["abstained"]),(0,1))
        self.assertEqual(trained["composed_grammar"].record(),snap)

    def test_frozen_protocol_and_no_arbitrary_seed_sweep(self):
        self.assertEqual((SOURCE,WARMUP,RECENT_TRAIN,ACTION_TRAIN,TAIL),
                         (192,240,24,32,12))
        self.assertEqual([name for name,_,_,_ in STAGES],
                         ["source","product","return_source","square"])
        self.assertEqual(TEST_START,{"product":260000,"return_source":270000,
                                      "square":280000})
        self.assertEqual(TEST_N,16)
        self.assertEqual(len(METHODS),10)
        self.assertEqual(CHECKPOINTS["product"],(0,4,8,16,32,64,96,128))
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
