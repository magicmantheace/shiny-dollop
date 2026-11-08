"""Tests for source-trained strategy selection on unrelated anonymous actions.

These tests are structural; do not assert any post-hoc target success rate.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.opaque_causal import (
    SCHEMA, BUDGET, POLICIES, OpaqueWorld, OpaqueEpisodePolicy, validate,
)
from developmental_ai.outcome_skills import digest
from benchmarks.opaque_causal_benchmark import (
    DEV, RESERVED, TRAIN_N, VALIDATION_N, TEST_N, StrategySelector,
    episode, measure,
)


class OpaqueCausalTests(unittest.TestCase):
    def test_action_labels_rotate_without_exposing_hidden_operations(self):
        one=OpaqueWorld(DEV[0],"test",8000,"relay").frame()
        another=OpaqueWorld(DEV[0],"test",8001,"relay").frame()
        self.assertNotEqual(one["actions"],another["actions"])
        self.assertNotIn("family",one)
        self.assertNotIn("recipes",one)
        self.assertNotIn("true_target",one)
        self.assertEqual(set(one),{"schema","episode","tick","remaining",
                                  "channels","actions","goal","done"})
        self.assertEqual(one["schema"],SCHEMA)
        self.assertEqual(validate(one),one)

    def test_distinct_hidden_dynamics_and_sensor_sizes(self):
        relay=OpaqueWorld(DEV[0],"test",8000,"relay")
        cargo=OpaqueWorld(DEV[0],"test",8000,"cargo")
        self.assertNotEqual(len(relay.frame()["channels"]),len(cargo.frame()["channels"]))
        self.assertNotEqual(len(relay.frame()["actions"]),len(cargo.frame()["actions"]))
        self.assertFalse(relay.frame()["done"])
        self.assertFalse(cargo.frame()["done"])

    def test_privileged_reference_reaches_both_goals(self):
        for family in ("relay","cargo"):
            result=episode(DEV[0],"test",8000,family,"oracle")
            self.assertEqual(result["success"],1)
            self.assertEqual(result["blocked"],0)
            self.assertLessEqual(result["attempts"],BUDGET)

    def test_rejects_privileged_or_invalid_sensor_data(self):
        f=OpaqueWorld(DEV[0],"test",8000,"relay").frame()
        for field in ("family","ground_truth","hidden_recipes","true_action_names"):
            fake=copy.deepcopy(f);fake[field]=1
            with self.assertRaises(ValueError):validate(fake)
        for bogus in (True, -1, 4, [], "0"):
            fake=copy.deepcopy(f);fake["channels"][0]=bogus
            with self.assertRaises(ValueError):validate(fake)
        fake=copy.deepcopy(f);fake["actions"].append(fake["actions"][0])
        with self.assertRaises(ValueError):validate(fake)

    def test_agent_only_uses_public_numeric_frame(self):
        for family in ("relay","cargo"):
            world=OpaqueWorld(DEV[0],"train",0,family)
            model=OpaqueEpisodePolicy("retry")
            for _ in range(4):
                frame=world.frame()
                action=model.choose(frame)
                if action is None:break
                after=world.step(action,frame["tick"])
                model.feedback(frame,action,after["accepted"],after["frame"])
                if world.done:break
            self.assertTrue(model.history)
            self.assertEqual(model.record(),OpaqueEpisodePolicy.restore(model.record()).record())

    def test_replay_preserves_continuation_action_mid_episode(self):
        for policy in POLICIES:
            world=OpaqueWorld(DEV[0],"train",3,"cargo")
            m=OpaqueEpisodePolicy(policy)
            for _ in range(3):
                frame=world.frame()
                action=m.choose(frame)
                out=world.step(action,frame["tick"])
                m.feedback(frame,action,out["accepted"],out["frame"])
            resumed=OpaqueEpisodePolicy.restore(copy.deepcopy(m.record()))
            self.assertEqual(resumed.choose(world.frame()),m.choose(world.frame()))

    def test_replay_detects_fake_action_even_with_rehashed_digest(self):
        world=OpaqueWorld(DEV[0],"train",4,"relay")
        m=OpaqueEpisodePolicy("novel")
        f=world.frame();a=m.choose(f);o=world.step(a,f["tick"])
        m.feedback(f,a,o["accepted"],o["frame"])
        saved=m.record()
        forged=copy.deepcopy(saved)
        forged["state"]["events"][0]["action"]="a_"+"f"*18
        forged["sha256"]=digest(forged["state"])
        with self.assertRaises(ValueError):OpaqueEpisodePolicy.restore(forged)

    def test_refuses_unverified_feedback(self):
        world=OpaqueWorld(DEV[0],"train",5,"cargo")
        m=OpaqueEpisodePolicy("retry")
        before=world.frame()
        action=m.choose(before);out=world.step(action,before["tick"])
        with self.assertRaises(ValueError):
            m.feedback(before,"a_"+"0"*18,out["accepted"],out["frame"])
        with self.assertRaises(ValueError):
            m.feedback(before,action,not out["accepted"],out["frame"])

    def test_unseen_target_has_no_stable_action_identity(self):
        relay=OpaqueWorld(DEV[0],"train",6,"relay")
        cargo=OpaqueWorld(DEV[0],"test",8000,"cargo")
        self.assertTrue(set(relay.frame()["actions"]).isdisjoint(cargo.frame()["actions"]))

    def test_selector_replay_and_prohibits_incomplete_freeze(self):
        learner=StrategySelector()
        with self.assertRaises(ValueError):learner.freeze()
        for i in range(TRAIN_N):
            learner.add(i,{mode:episode(DEV[0],"train",i,"relay",mode)
                           for mode in POLICIES})
        selected=learner.freeze()
        self.assertIn(selected,POLICIES)
        self.assertEqual(learner.record(),StrategySelector.restore(learner.record()).record())
        with self.assertRaises(ValueError):learner.freeze()

    def test_rejects_tampered_selection_even_with_rehashed_digest(self):
        learner=StrategySelector()
        for i in range(TRAIN_N):
            learner.add(i,{mode:episode(DEV[0],"train",i,"relay",mode)
                           for mode in POLICIES})
        learner.freeze()
        saved=copy.deepcopy(learner.record())
        saved["state"]["selection"]=next(m for m in POLICIES if m!=saved["state"]["selection"])
        saved["sha256"]=digest(saved["state"])
        with self.assertRaises(ValueError):StrategySelector.restore(saved)

    def test_cannot_relabel_cohorts_or_change_namespace_bounds(self):
        self.assertEqual((TRAIN_N,VALIDATION_N,TEST_N),(48,24,60))
        for bad in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(bad)

    def test_no_eval_learning_from_held_out_target(self):
        before=episode(DEV[0],"test",8000,"cargo","retry",collect_journal=True)
        after=episode(DEV[0],"test",8000,"cargo","retry",collect_journal=True)
        self.assertEqual(before,after)
        self.assertLessEqual(before["attempts"],BUDGET)
        self.assertIn(before["success"],(0,1))


if __name__ == "__main__":
    unittest.main()
