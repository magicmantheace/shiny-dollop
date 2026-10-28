"""Frozen cross-rule hypothesis selection, no learner-visible law labels."""
from __future__ import annotations

import copy
import math
import unittest

from developmental_ai.feature_hypothesis_memory import (
    FeatureHypothesisMemory,_Bucket,feature_bucket,
    SOURCE,WARMUP,RECENT,TAIL,CANDIDATES
)
from developmental_ai.observable_affordances import digest
from benchmarks.cross_rule_benchmark import (
    DEV,ADDITIONAL,STAGES,CHECKPOINTS,TEST_START,TEST_N,METHODS,
    CrossRuleWorld,effect,external_training,policies,evaluate,measure
)


class CrossRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.cost=external_training(cls.seed,"source",1000,240)

    def test_rule_families_are_not_merely_reversed_span(self):
        labels=[(effect(self.seed,"source",{"inlet":a,"outlet":b}),
                 effect(self.seed,"checksum",{"inlet":a,"outlet":b}),
                 effect(self.seed,"ordered",{"inlet":a,"outlet":b}))
                for a in range(10) for b in range(10)]
        self.assertTrue(any(x[0]==x[1]==x[2] for x in labels))
        self.assertTrue(any(x[0]!=x[1] and x[0]!=x[2] for x in labels))
        self.assertTrue(any(x[1]!=x[2] for x in labels))
        # An asymmetric target rule: reversing sensor values sometimes
        # changes its effect, while range stays unchanged.
        self.assertTrue(any(
            effect(self.seed,"checksum",{"inlet":a,"outlet":b}) !=
            effect(self.seed,"checksum",{"inlet":b,"outlet":a})
            for a in range(10) for b in range(10)))
        self.assertTrue(all(
            effect(self.seed,"source",{"inlet":a,"outlet":b}) ==
            effect(self.seed,"source",{"inlet":b,"outlet":a})
            for a in range(10) for b in range(10)))

    def test_all_regimes_have_same_public_interface_and_action_counts(self):
        for law in ("source","checksum","ordered"):
            world=CrossRuleWorld(self.seed,"test",230000,law)
            frame=world.frame()
            self.assertEqual(set(frame),{"schema","episode","tick",
                              "budget","progress","damage","target","done","actions"})
            self.assertEqual(len(frame["actions"]),12)
            self.assertEqual(set(frame["actions"][0]["features"]),
                             {"inlet","outlet"})
            self.assertEqual({x:sum(world._effect(a["features"])==x
                                  for a in frame["actions"])
                              for x in ("progress","damage","neutral")},
                             {"progress":5,"damage":4,"neutral":3})
            self.assertNotIn("law",str(frame))
            self.assertNotIn("checksum",str(frame))
            self.assertNotIn("ordered",str(frame))

    def test_public_evidence_has_no_privileged_hidden_law(self):
        for law,begin,n in (("source",1000,8),("checksum",2000,8),
                             ("ordered",4000,8)):
            observations,cost=external_training(self.seed,law,begin,n)
            self.assertEqual(cost["observations"],8)
            self.assertEqual(sum(cost[k] for k in
                                 ("harmful","productive","neutral")),8)
            for e in observations:
                self.assertEqual(set(e),{"features","progress","damage"})
                self.assertEqual(set(e["features"]),{"inlet","outlet"})

    def test_registered_feature_hypotheses_and_public_order(self):
        features={"inlet":3,"outlet":7}
        self.assertEqual(feature_bucket(features,"span"),4)
        self.assertEqual(feature_bucket(features,"checksum"),(2*3+7)%5)
        self.assertEqual(feature_bucket(features,"ordered"),(3+3*7)%7)
        self.assertEqual(len(CANDIDATES),4)
        self.assertEqual((SOURCE,WARMUP,RECENT,TAIL),(192,240,24,8))
        # Raw feature names rather than source/target phase names are used.
        with self.assertRaises(ValueError):
            feature_bucket(features,"physics")

    def test_prequential_scores_finite_separate_and_checkpoint_replayed(self):
        m=FeatureHypothesisMemory()
        for e in self.source:
            m.observe(e)
        info,choice=m.selection()
        self.assertEqual(info["scoring_events"],8)
        self.assertEqual(info["scored_event_fit_overlap"],0)
        self.assertEqual(len(info["prequential_log_scores"]),4)
        self.assertTrue(all(math.isfinite(x) for x in info["prequential_log_scores"]))
        self.assertIn(info["selected"],CANDIDATES)
        saved=m.record()
        resumed=FeatureHypothesisMemory.restore(copy.deepcopy(saved))
        frame=CrossRuleWorld(self.seed,"test",230000,"checksum").frame()
        self.assertEqual(m.choose(frame),resumed.choose(frame))
        self.assertEqual(m.selection()[0],resumed.selection()[0])
        self.assertEqual(m.record(),saved)
        self.assertEqual(resumed.record(),saved)
        self.assertFalse(hasattr(m,"step"))

    def test_unknown_key_and_corrupt_checkpoint_rejected(self):
        m=FeatureHypothesisMemory()
        m.observe(self.source[0])
        saved=m.record()
        with self.assertRaises(ValueError):
            m.observe({"features":{"keel":2,"wisp":6},
                       "progress":True,"damage":False})
        self.assertEqual(m.record(),saved)
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["progress"]=True
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            FeatureHypothesisMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            FeatureHypothesisMemory.restore(bad)

    def test_readonly_competitors_and_abstention_failure(self):
        fitted=policies(self.source)
        snap=fitted["hypothesis_selector"].record()
        fitted["_history"]=self.source
        for policy in METHODS:
            row=evaluate(self.seed,"checksum",230000,policy,fitted)
            self.assertIn(row["success"],(0,1))
            self.assertIn(row["harmful_actions"],(0,1))
            if policy=="always_abstain":
                self.assertEqual(row["success"],0)
                self.assertEqual(row["abstained"],1)
        self.assertEqual(fitted["hypothesis_selector"].record(),snap)

    def test_frozen_cohort_and_protocol_counts(self):
        self.assertEqual([s[0] for s in STAGES],
                         ["source","checksum","return_source","ordered"])
        self.assertEqual(CHECKPOINTS["checksum"],(0,4,8,16,32,64,96))
        self.assertEqual(CHECKPOINTS["return_source"],(0,4,8,16,32,48))
        self.assertEqual(TEST_START,{"checksum":230000,
                                      "return_source":240000,
                                      "ordered":250000})
        self.assertEqual(TEST_N,20)
        self.assertEqual(len(METHODS),10)
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
