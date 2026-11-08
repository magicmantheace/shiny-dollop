"""Disjoint feature validation, abstention cost and exact evidence replay."""
from __future__ import annotations

import copy
import math
import unittest

from developmental_ai.validated_abstention_memory import (
    ValidatedAbstainingMemory, SELECTION_WARMUP, VALIDATION, FIT_WINDOW,
    MIN_GAIN, MIN_HITS, MIN_ACTION_PROGRESS, MAX_ACTION_DAMAGE,
)
from developmental_ai.observable_affordances import digest
from benchmarks.validated_abstention_benchmark import (
    DEV,ADDITIONAL,STAGES,CHECKPOINTS,TEST_START,TEST_N,METHODS,
    models,evaluate,measure
)
from benchmarks.gated_composition_benchmark import ConditionalWorld,training


class ValidatedAbstentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.cost=training(cls.seed,"source",1000,240)

    def trained(self,events=None):
        learner=ValidatedAbstainingMemory()
        for event in (self.source if events is None else events):
            learner.observe(event)
        return learner

    def test_predictive_validation_is_separate_from_program_selection(self):
        active,_=training(self.seed,"conditional",2000,32)
        events=self.source+active
        original=self.trained(events).selection()[0]
        altered=copy.deepcopy(events)
        for event in altered[-16:]:
            event["progress"],event["damage"]=event["damage"],event["progress"]
        comparison=self.trained(altered).selection()[0]
        self.assertEqual(original["validated_names"],comparison["validated_names"])
        self.assertEqual(original["selected_kind"],comparison["selected_kind"])
        self.assertEqual(original["validation_fit_overlap"],0)
        self.assertEqual(original["validation_examples"],16)
        self.assertEqual(original["selection_training_excludes_validation"],True)
        self.assertNotEqual(original["mean_gain_over_null"],
                            comparison["mean_gain_over_null"])

    def test_source_warmup_frozen_without_using_validation_labels(self):
        choice=self.trained().selection()[0]
        self.assertEqual(choice["selected_kind"],"warmup_source")
        self.assertEqual(choice["validated_names"],["frozen_source_span"])
        self.assertEqual(choice["recorded_events"],240)
        self.assertIn(choice["meets_adequacy_gate"],(True,False))

    def test_selected_model_explicitly_abstains_when_adequacy_fails(self):
        original=self.trained()
        for event in self.source:
            self.assertEqual(set(event),{"features","progress","damage"})
        decision,predictor=original.selection()
        frame=ConditionalWorld(self.seed,"test",320000,"conditional").frame()
        if not decision["meets_adequacy_gate"]:
            self.assertIsNone(original.choose(frame))
        else:
            self.assertIn(original.choose(frame),
                          [None]+[x["id"] for x in frame["actions"]])
        self.assertFalse(hasattr(original,"step"))

    def test_replay_integrity_and_immutable_test(self):
        sample=training(self.seed,"xor",4000,64)[0]
        model=self.trained(self.source+sample)
        saved=model.record()
        recovered=ValidatedAbstainingMemory.restore(copy.deepcopy(saved))
        frame=ConditionalWorld(self.seed,"test",340000,"xor").frame()
        self.assertEqual(model.choose(frame),recovered.choose(frame))
        self.assertEqual(model.selection()[0],recovered.selection()[0])
        self.assertEqual(model.record(),saved)

    def test_foreign_feature_schema_and_forged_evidence_rejected(self):
        model=ValidatedAbstainingMemory()
        model.observe(self.source[0])
        state=model.record()
        with self.assertRaises(ValueError):
            model.observe({"features":{"not_a_sensor":0,"outlet":5},
                           "progress":True,"damage":False})
        self.assertEqual(model.record(),state)
        bad=copy.deepcopy(state)
        bad["state"]["events"][0]["progress"]=True
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            ValidatedAbstainingMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            ValidatedAbstainingMemory.restore(bad)

    def test_no_oracle_law_stage_or_actor_identity_in_persisted_memory(self):
        event=training(self.seed,"xor",4000,1)[0][0]
        model=self.trained(self.source+[event])
        record=model.record()
        self.assertEqual(set(record["state"]),{"schema","events"})
        self.assertEqual(set(record["state"]["events"][-1]),
                         {"features","progress","damage"})
        for word in ('"xor"','"conditional"','"physics"','"seed"',
                     '"oracle"','"action_id"'):
            self.assertNotIn(word,str(record))

    def test_all_policy_controls_and_abstention_is_task_failure(self):
        fitted=models(self.source)
        immutable=fitted["validated_abstain"].record()
        for method in METHODS:
            result=evaluate(self.seed,"xor",340000,method,fitted)
            self.assertIn(result["success"],(0,1))
            self.assertIn(result["harmful_actions"],(0,1))
            if method=="always_abstain":
                self.assertEqual(result["success"],0)
                self.assertEqual(result["abstained"],1)
                self.assertEqual(result["attempted"],0)
            if method=="perfect_action_oracle":
                self.assertEqual(result["success"],1)
        self.assertEqual(fitted["validated_abstain"].record(),immutable)

    def test_actor_outcome_cost_and_fixed_cohort_protocol(self):
        public,cost=training(self.seed,"source",1000,240)
        self.assertEqual(len(public),240)
        self.assertEqual(sum(cost[k] for k in
                             ("productive","harmful","neutral")),240)
        self.assertEqual((public,cost),training(self.seed,"source",1000,240))
        self.assertEqual(
            (SELECTION_WARMUP,VALIDATION,FIT_WINDOW,MIN_GAIN,MIN_HITS,
             MIN_ACTION_PROGRESS,MAX_ACTION_DAMAGE),
            (240,16,64,0.20,10,0.55,0.18))
        self.assertEqual(TEST_N,16)
        self.assertEqual(TEST_START,{
            "conditional":320000,"return_source":330000,"xor":340000})
        self.assertEqual([s[0] for s in STAGES],
                         ["source","conditional","return_source","xor"])
        self.assertEqual(CHECKPOINTS["xor"],
                         (0,8,16,24,32,48,64,96,128))
        self.assertEqual(len(METHODS),9)
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
