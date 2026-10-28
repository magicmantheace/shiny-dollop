"""Persistent arbitrary public feature-schema learning, replay and limits."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.observable_affordances import (
    VariableOutcomeMemory, NumericOutcomeMemory, digest,
)
from benchmarks.variable_affordance_benchmark import (
    VariableWorld, SCHEMA, FAMILIES, METHODS, DEV, ADDITIONAL,
    SOURCE_N, TARGET_N, TEST_N, CHECKPOINTS, train_events,
    actor_event, public_outcome, memory, play, measure,
)


class VariableAffordanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.samples={f:train_events(cls.seed,f,8) for f in FAMILIES}

    def test_distinct_feature_vocabulary_and_physics_without_domain_field(self):
        shapes = [set(self.samples[f][0]["features"]) for f in FAMILIES]
        self.assertEqual([len(s) for s in shapes],[2,3,4])
        self.assertTrue(all(a.isdisjoint(b) for i,a in enumerate(shapes)
                            for b in shapes[i+1:]))
        for family in FAMILIES:
            frame=VariableWorld(self.seed,"test",40000,family).frame()
            self.assertEqual(frame["schema"],SCHEMA)
            self.assertEqual(set(frame),
                             {"schema","episode","tick","budget","progress",
                              "damage","target","actions","done"})
            self.assertNotIn("family",str(frame))
            self.assertNotIn("physics",str(frame))

    def test_learn_unknown_schema_from_its_own_outcomes_without_removing_source(self):
        bank=memory(self.samples["quarry"]+self.samples["coolant"])
        relay_event=self.samples["relay"][0]
        self.assertEqual(bank.estimate(relay_event["features"])["evidence"],0)
        source_before=bank.estimate(self.samples["quarry"][0]["features"])
        bank.observe(relay_event)
        self.assertEqual(bank.estimate(relay_event["features"])["evidence"],1)
        self.assertEqual(bank.estimate(self.samples["quarry"][0]["features"]),source_before)
        self.assertEqual(sorted(bank.signatures().values()),[1,8,8])

    def test_no_privileged_family_name_in_saved_learning(self):
        bank=memory(sum(self.samples.values(),[]))
        state=bank.record()["state"]
        self.assertEqual(set(state),{"schema","events"})
        self.assertEqual(set(state["events"][0]),{"features","progress","damage"})
        for marker in ('"quarry"', '"coolant"', '"relay"', '"true_rule"'):
            self.assertNotIn(marker,str(state))

    def test_exact_resume_and_held_out_prediction_does_not_mutate(self):
        bank=memory(sum(self.samples.values(),[]))
        saved=bank.record()
        restored=VariableOutcomeMemory.restore(copy.deepcopy(saved))
        self.assertEqual(restored.record(),saved)
        for family in FAMILIES:
            frame=VariableWorld(self.seed,"test",40000,family).frame()
            self.assertEqual(restored.choose(frame),bank.choose(frame))
        self.assertEqual(restored.record(),saved)

    def test_modified_hash_and_invalid_rehashed_public_event_rejected(self):
        bank=memory(self.samples["quarry"])
        saved=bank.record()
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["damage"]=not bad["state"]["events"][0]["damage"]
        with self.assertRaises(ValueError):
            VariableOutcomeMemory.restore(bad)
        bad["state"]["events"][0]["features"]["grade"]=99
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            VariableOutcomeMemory.restore(bad)

    def test_public_replay_effect_and_stale_action_rejected(self):
        sim=VariableWorld(self.seed,"train",1000,"quarry")
        before=sim.frame()
        chosen=before["actions"][0]["id"]
        after=sim.step(chosen,before["tick"])
        event=public_outcome(before,chosen,after)
        self.assertEqual(set(event),{"features","progress","damage"})
        self.assertLessEqual(int(event["progress"])+int(event["damage"]),1)
        with self.assertRaises(ValueError):
            sim.step(chosen,before["tick"])
        with self.assertRaises(ValueError):
            public_outcome(before,"a_"+"f"*18,after)

    def test_public_memory_refuses_invalid_observation_types(self):
        bank=VariableOutcomeMemory()
        for bad in (
            {"features":{"phase":True,"pulse":1},"progress":True,"damage":False},
            {"features":{"phase":1,"pulse":1},"progress":True,"damage":True},
            {"features":{"a":1},"progress":True,"damage":False},
            {"features":{"a":1,"b":2},"progress":1,"damage":False},
        ):
            with self.assertRaises(ValueError):
                bank.observe(bad)
        self.assertFalse(hasattr(bank,"probe"))
        self.assertFalse(hasattr(bank,"step"))
        self.assertFalse(hasattr(NumericOutcomeMemory(),"signatures"))

    def test_oracle_and_abstain_controls_on_distinct_families(self):
        for family in FAMILIES:
            oracle=play(self.seed,family,40000,"privileged_oracle",{})
            empty=play(self.seed,family,40000,"always_abstain",{})
            self.assertEqual(oracle["success"],1)
            self.assertEqual(oracle["hurt"],0)
            self.assertEqual(empty["success"],0)
            self.assertEqual(empty["abstained"],1)

    def test_separate_random_actor_provides_exact_one_training_event(self):
        first=actor_event(self.seed,"quarry",1000)
        self.assertEqual(first,actor_event(self.seed,"quarry",1000))
        self.assertEqual(set(first),{"features","progress","damage"})
        self.assertNotIn("action",first)
        self.assertNotIn("simulator",first)

    def test_precommitted_test_budget_and_rejected_seed_substitution(self):
        self.assertEqual((SOURCE_N,TARGET_N,TEST_N),(180,160,40))
        self.assertEqual(CHECKPOINTS,(0,16,48,160))
        self.assertNotEqual(DEV,ADDITIONAL)
        for bad in ((1,2,3),tuple(reversed(ADDITIONAL)),(DEV[0],)):
            with self.assertRaises(ValueError):
                measure(bad)


if __name__=="__main__":
    unittest.main()
