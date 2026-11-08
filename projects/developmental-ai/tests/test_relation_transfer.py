"""Regressions for source-fitted relation transfer and negative transfer."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.relation_outcome_memory import (
    RelationOutcomeMemory, span, SCHEMA
)
from developmental_ai.observable_affordances import (
    NumericOutcomeMemory, VariableOutcomeMemory, digest
)
from benchmarks.relation_transfer_benchmark import (
    DEV, ADDITIONAL, FAMILIES, TARGETS, CHECKPOINTS, SOURCE_N, TARGET_N,
    TEST_N, METHODS, RelationWorld, actor_event, observed, relation_model,
    raw_model, play, band, effect_for, measure,
)


class RelationTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.examples=observed(cls.seed,"basin",32)

    def test_public_feature_vocabularies_change_across_all_families(self):
        seen=[]
        for family in FAMILIES:
            frame=RelationWorld(self.seed,"test",50000,family).frame()
            self.assertEqual(set(frame),{"schema","episode","tick","budget",
                                         "progress","damage","target","actions","done"})
            self.assertNotIn("family",frame)
            signature=set(frame["actions"][0]["features"])
            for previous in seen:
                self.assertTrue(signature.isdisjoint(previous))
            seen.append(signature)
        self.assertEqual([len(s) for s in seen],[2,3,4,3])

    def test_learned_gap_representation_handles_unknown_keys_dimensions(self):
        x={"a":3,"b":8}
        y={"west":3,"north":5,"beam":8}
        z={"m":3,"n":5,"p":6,"q":8}
        self.assertEqual([span(v) for v in (x,y,z)],[5,5,5])
        model=RelationOutcomeMemory()
        model.observe({"features":x,"progress":True,"damage":False})
        for payload in (x,y,z):
            self.assertEqual(model.estimate(payload)["evidence"],1)
            self.assertEqual(model.estimate(payload)["progress"],
                             model.estimate(x)["progress"])

    def test_source_trained_relation_predicts_both_new_vocabularies_zero_shot(self):
        model=relation_model(self.examples)
        self.assertGreater(sum(sum(row) for row in model.counts),0)
        for family in ("lattice","prism"):
            f=RelationWorld(self.seed,"test",50000,family).frame()
            self.assertTrue(any(model.estimate(a["features"])["evidence"]>0
                                for a in f["actions"]))
            self.assertIsInstance(model.choose(f),str)
        self.assertFalse(hasattr(model,"step"))
        self.assertFalse(hasattr(model,"probe"))

    def test_negative_environment_reverses_same_observed_span_effects(self):
        for gap in range(10):
            standard=effect_for(self.seed,"basin",{"x":0,"y":gap})
            counter=effect_for(self.seed,"counterphase",{"x":0,"y":gap})
            self.assertEqual(counter,{
                "progress":"damage","damage":"progress","neutral":"neutral"
            }[standard])

    def test_source_checkpoint_replay_and_read_only_test(self):
        model=relation_model(self.examples)
        snapshot=model.record()
        self.assertEqual(snapshot["state"]["schema"],SCHEMA)
        loaded=RelationOutcomeMemory.restore(copy.deepcopy(snapshot))
        self.assertEqual(snapshot,loaded.record())
        for family in FAMILIES:
            frame=RelationWorld(self.seed,"test",50000,family).frame()
            self.assertEqual(model.choose(frame),loaded.choose(frame))
        policy={"transfer_range":loaded}
        for family in FAMILIES:
            result=play(self.seed,family,50000,"transfer_range",policy)
            self.assertIn(result["success"],(0,1))
        self.assertEqual(loaded.record(),snapshot)

    def test_rehashed_fabrication_with_inconsistent_counts_refused(self):
        snapshot=relation_model(self.examples).record()
        corrupted=copy.deepcopy(snapshot)
        corrupted["state"]["outcome_counts"][0][0]+=3
        with self.assertRaises(ValueError):
            RelationOutcomeMemory.restore(corrupted)
        corrupted["sha256"]=digest(corrupted["state"])
        with self.assertRaises(ValueError):
            RelationOutcomeMemory.restore(corrupted)

    def test_source_actor_does_not_get_rule_or_action_identity(self):
        row=actor_event(self.seed,"basin",1000)
        self.assertEqual(set(row),{"features","progress","damage"})
        self.assertEqual(row,actor_event(self.seed,"basin",1000))
        self.assertEqual(type(row["progress"]),bool)
        self.assertEqual(type(row["damage"]),bool)

    def test_oracle_random_abstention_are_separate_benchmarks(self):
        for family in FAMILIES:
            oracle=play(self.seed,family,50000,"privileged_oracle",{})
            abstain=play(self.seed,family,50000,"always_abstain",{})
            self.assertEqual((oracle["success"],oracle["harmful_actions"]),(1,0))
            self.assertEqual(abstain["success"],0)
            self.assertEqual(abstain["abstained"],1)

    def test_previous_numeric_memory_untouched_and_schema_control(self):
        self.assertFalse(hasattr(NumericOutcomeMemory(),"estimate_range"))
        self.assertFalse(hasattr(VariableOutcomeMemory(),"estimate_range"))
        original=VariableOutcomeMemory()
        for event in self.examples:
            original.observe(event)
        new=relation_model(self.examples)
        target=RelationWorld(self.seed,"test",50000,"lattice").frame()
        self.assertTrue(all(original.estimate(a["features"])["evidence"]==0
                            for a in target["actions"]))
        self.assertTrue(any(new.estimate(a["features"])["evidence"]>0
                            for a in target["actions"]))

    def test_precommitted_group_and_sample_constraints(self):
        self.assertEqual((SOURCE_N,TARGET_N,TEST_N),(240,64,40))
        self.assertEqual(CHECKPOINTS,(0,8,24,64))
        self.assertEqual(len(METHODS),10)
        self.assertEqual(len(DEV),3)
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),tuple(reversed(DEV)),(DEV[0],)):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
