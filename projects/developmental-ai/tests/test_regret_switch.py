"""Independent prequential scoring, public regret and freeze-boundary tests."""
from __future__ import annotations

import copy
import math
import unittest

from developmental_ai.regret_switch_memory import (
    RegretSwitchMemory, FAST_TAIL, SURPRISE_P, FAST_ERRORS,
    SOURCE_SUPPORT_P, SOURCE_RATIO, SOURCE_SUPPORT_MIN,
    SOURCE_REGRET_MARGIN, LONG_REGRET_MARGIN, LONG_SURPRISE_MIN,
)
from developmental_ai.observable_affordances import digest
from benchmarks.regret_switch_benchmark import (
    DEV, ADDITIONAL, CHECKPOINTS, TEST_N, TEST_START, METHODS,
    measure, trained, score_one,
)
from benchmarks.stochastic_prequential_benchmark import StochasticWorld, public_train


def row(progress,span=5):
    return {"features":{"inlet":0,"outlet":span},
            "progress":bool(progress),"damage":not progress}


class RegretSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.source_cost=public_train(cls.seed,"original",1000,240)

    def test_predictive_score_is_out_of_sample_and_finite(self):
        model=RegretSwitchMemory()
        for event in self.source:
            model.observe(event)
        decision,candidate=model.selection()
        self.assertEqual(decision["prequential_scoring_events"],8)
        self.assertEqual(decision["predictor_training_overlap"],0)
        self.assertEqual(len(decision["prequential_scores"]),3)
        self.assertTrue(all(math.isfinite(s) for s in decision["prequential_scores"]))
        self.assertIn(decision["source"],("source192","recent8","recent32"))
        self.assertGreater(len(candidate.events),0)

    def test_archival_contradictions_trigger_recent_model(self):
        model=RegretSwitchMemory()
        for _ in range(240):
            model.observe(row(True))
        for _ in range(8):
            model.observe(row(False))
        choice,_=model.selection()
        self.assertEqual(choice["source"],"recent8")
        self.assertEqual(choice["source_conflicts_latest4"],4)
        self.assertEqual(choice["reason"],"archive_contradicted")
        self.assertTrue(choice["source_retained"])

    def test_stochastic_public_events_are_same_schema(self):
        a=StochasticWorld(self.seed,"test",200000,"original")
        b=StochasticWorld(self.seed,"test",200000,"reversed")
        self.assertEqual(a.frame(),b.frame())
        model=RegretSwitchMemory()
        for event in self.source:
            model.observe(event)
        self.assertEqual(set(model.record()["state"]),{"schema","events"})
        self.assertEqual(set(model.events[0]),{"features","progress","damage"})
        for forbidden in ('"physics"','"phase"','"episode"','"split"','"seed"'):
            self.assertNotIn(forbidden,str(model.record()))

    def test_replay_exact_and_prediction_read_only(self):
        source=self.source
        reversed_evidence=public_train(self.seed,"reversed",2000,24)[0]
        model=RegretSwitchMemory()
        for event in source+reversed_evidence:
            model.observe(event)
        record=model.record()
        other=RegretSwitchMemory.restore(copy.deepcopy(record))
        frame=StochasticWorld(self.seed,"test",200000,"reversed").frame()
        self.assertEqual(model.choose(frame),other.choose(frame))
        self.assertEqual(model.selection()[0],other.selection()[0])
        self.assertEqual(record,model.record())
        self.assertEqual(record,other.record())
        self.assertFalse(hasattr(model,"step"))

    def test_invalid_new_features_or_forged_record_rejected(self):
        model=RegretSwitchMemory()
        model.observe(row(True))
        old=model.record()
        with self.assertRaises(ValueError):
            model.observe({"features":{"unseen":0,"outlet":5},
                           "progress":True,"damage":False})
        self.assertEqual(old,model.record())
        altered=copy.deepcopy(old)
        altered["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            RegretSwitchMemory.restore(altered)
        altered["sha256"]=digest(altered["state"])
        with self.assertRaises(ValueError):
            RegretSwitchMemory.restore(altered)

    def test_random_external_actor_costs_and_no_hidden_true_reports(self):
        data,cost=public_train(self.seed,"original",1000,240)
        self.assertEqual(len(data),240)
        self.assertEqual(public_train(self.seed,"original",1000,240),(data,cost))
        self.assertEqual(cost["actual_harmful"]+cost["actual_productive"]+
                         cost["actual_neutral"],240)
        self.assertNotIn("actual_harmful",str(data))
        self.assertEqual(set(data[0]),{"features","progress","damage"})

    def test_matched_baselines_and_failed_abstention(self):
        methods=trained(self.source)
        original=methods["regret_switch"].record()
        for mode in METHODS:
            trial=score_one(self.seed,"reversed",200000,mode,methods)
            self.assertIn(trial["success"],(0,1))
            self.assertIn(trial["harmful_actions"],(0,1))
            if mode=="always_abstain":
                self.assertEqual(trial["abstained"],1)
                self.assertEqual(trial["success"],0)
        self.assertEqual(methods["regret_switch"].record(),original)

    def test_registered_formula_seeds_and_all_checkpoints(self):
        self.assertEqual((FAST_TAIL,SURPRISE_P,FAST_ERRORS),(4,0.125,2))
        self.assertEqual((SOURCE_SUPPORT_P,SOURCE_RATIO,SOURCE_SUPPORT_MIN),
                         (0.55,2.0,2))
        self.assertEqual((SOURCE_REGRET_MARGIN,LONG_REGRET_MARGIN,LONG_SURPRISE_MIN),
                         (1.0,1.0,12))
        self.assertEqual(TEST_N,16)
        self.assertEqual(TEST_START,{"B1":200000,"return_A":210000,"B2":220000})
        self.assertEqual(CHECKPOINTS["B1"],(0,2,4,8,12,24,32,64))
        self.assertEqual(len(METHODS),11)
        self.assertNotEqual(DEV,ADDITIONAL)
        for unknown in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(unknown)


if __name__=="__main__":
    unittest.main()
