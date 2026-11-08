"""Tests require only public numeric measurements and observed deltas."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.observable_affordances import (
    ObservableWorld, NumericOutcomeMemory, check, outcome, digest
)
from benchmarks.observable_affordance_benchmark import (
    DEV, RESERVED, DOMAINS, POLICIES, fit, play, measure,
    TEST_EPISODES, TRAIN_EPISODES, TEST_START
)


class ObservableAffordanceTests(unittest.TestCase):
    def test_every_episode_has_independent_opaque_handles_and_numeric_features(self):
        a=ObservableWorld(DEV[0],"test",TEST_START,"collect").frame()
        b=ObservableWorld(DEV[0],"test",TEST_START+1,"collect").frame()
        self.assertIs(check(a),a)
        self.assertNotEqual({row["id"] for row in a["actions"]},
                            {row["id"] for row in b["actions"]})
        self.assertEqual(set(a),{"schema","episode","tick","budget",
                                 "sensors","goal","actions","done"})
        for forbidden in ("hidden_name","spoil","hazard","domain","route"):
            self.assertNotIn(forbidden,str(a))

    def test_one_event_is_observed_sensor_difference_not_a_hidden_label(self):
        world=ObservableWorld(DEV[0],"train",0,"collect")
        old=world.frame()
        action=old["actions"][0]["id"]
        after=world.step(action,old["tick"])
        event=outcome(old,action,after)
        self.assertEqual(set(event),{"features","progress","damage"})
        self.assertTrue(event["progress"]!=event["damage"] or
                        not event["progress"])
        self.assertNotIn(action,str(event))

    def test_reject_private_fields_invalid_features_and_injected_outcome(self):
        original=ObservableWorld(DEV[0],"train",1,"collect").frame()
        for key in ("hidden_rule","world","family"):
            bad=copy.deepcopy(original);bad[key]="route"
            with self.assertRaises(ValueError):check(bad)
        bad=copy.deepcopy(original);bad["actions"][0]["features"]=[1,True]
        with self.assertRaises(ValueError):check(bad)
        model=NumericOutcomeMemory()
        with self.assertRaises(ValueError):model.add({"features":[1,2],"progress":True,"damage":True})

    def test_memory_is_public_replayable_and_prevents_rehashed_fake_stats(self):
        mem,stats=fit(DEV[0])
        self.assertEqual(stats["episodes"],TRAIN_EPISODES)
        saved=mem.record()
        self.assertEqual(NumericOutcomeMemory.restore(copy.deepcopy(saved)).record(),saved)
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["features"]=[-1,2]
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):NumericOutcomeMemory.restore(bad)

    def test_zero_target_training_and_read_only_evaluation(self):
        memory,_=fit(DEV[0]);record=memory.record()
        for domain in DOMAINS:
            for method in POLICIES:
                stats=play(DEV[0],"test",TEST_START,domain,method,memory)
                self.assertLessEqual(stats["attempts"],7)
        self.assertEqual(memory.record(),record)

    def test_model_can_solve_source_and_target_with_positive_learning_evidence(self):
        model,_=fit(DEV[0])
        for domain in ("collect","route"):
            scores=[play(DEV[0],"test",TEST_START+i,domain,"numeric_knn",model)["success"]
                    for i in range(12)]
            self.assertGreaterEqual(sum(scores),7)

    def test_reversed_rule_is_not_silently_presented_as_generalization(self):
        model,_=fit(DEV[0])
        ordinary=sum(play(DEV[0],"test",TEST_START+i,"route","numeric_knn",model)["success"]
                     for i in range(12))
        reversal=sum(play(DEV[0],"test",TEST_START+i,"route-reversed","numeric_knn",model)["success"]
                     for i in range(12))
        self.assertGreater(ordinary,reversal)

    def test_privileged_oracle_is_reachable_in_all_domains(self):
        for domain in DOMAINS:
            for i in range(5):
                stats=play(DEV[0],"test",TEST_START+i,domain,"oracle")
                self.assertEqual(stats["success"],1)
                self.assertEqual(stats["hurt"],0)

    def test_no_hidden_seed_or_cohort_substitution(self):
        self.assertEqual(TEST_EPISODES,60)
        self.assertEqual(TRAIN_EPISODES,80)
        self.assertEqual(TEST_START,12000)
        for invalid in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)


if __name__=="__main__":unittest.main()
