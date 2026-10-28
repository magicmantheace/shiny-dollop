"""Regression and hidden-change boundary tests for adaptive memory horizons."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.adaptive_horizon_memory import (
    AdaptiveHorizonMemory, ANCHOR, RECENT, LONG_WINDOW, LONG_SURPRISE_MIN
)
from developmental_ai.observable_affordances import digest
from benchmarks.adaptive_horizon_benchmark import (
    DEV, ADDITIONAL, CHECKPOINTS, TEST_START, TEST_N, METHODS,
    build_models, eval_trial, measure,
)
from benchmarks.same_schema_switch_benchmark import SameSchemaWorld, training


def public_event(progress=True):
    return {"features": {"inlet": 0, "outlet": 5},
            "progress": bool(progress), "damage":not bool(progress)}


class AdaptiveHorizonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = DEV[0]
        cls.source = training(cls.seed, "original", 1000, 240)

    def test_short_then_long_then_restored_archive_without_stage_labels(self):
        model = AdaptiveHorizonMemory()
        for _ in range(240):
            model.observe(public_event(True))
        self.assertEqual(model.selection()[0]["source"], "archive")
        for _ in range(8):
            model.observe(public_event(False))
        early, _ = model.selection()
        self.assertEqual(early["source"], "recent8")
        self.assertEqual(early["latest_eight_surprises"], 8)
        for _ in range(16):
            model.observe(public_event(False))
        late, _ = model.selection()
        self.assertEqual(late["source"], "recent32")
        self.assertGreaterEqual(late["latest_thirty_two_surprises"],
                                LONG_SURPRISE_MIN)
        for _ in range(4):
            model.observe(public_event(True))
        returned, _ = model.selection()
        self.assertEqual(returned["source"], "archive")
        self.assertEqual(returned["latest_four_surprises"], 0)

    def test_individual_noise_does_not_force_new_regime(self):
        model=AdaptiveHorizonMemory()
        for _ in range(240):
            model.observe(public_event(True))
        model.observe(public_event(False))
        decision,_=model.selection()
        self.assertEqual(decision["source"],"archive")
        self.assertEqual(decision["latest_four_surprises"],1)

    def test_exact_checkpoint_restore_and_immutable_test_state(self):
        model=AdaptiveHorizonMemory()
        for event in self.source:
            model.observe(event)
        for row in training(self.seed,"reversed",2000,24):
            model.observe(row)
        before=model.record()
        restored=AdaptiveHorizonMemory.restore(copy.deepcopy(before))
        frame=SameSchemaWorld(self.seed,"test",110000,"reversed").frame()
        self.assertEqual(model.selection()[0],restored.selection()[0])
        self.assertEqual(model.choose(frame),restored.choose(frame))
        self.assertEqual(model.record(),before)
        self.assertEqual(restored.record(),before)

    def test_unknown_sensor_schema_refused_without_partial_mutation(self):
        model=AdaptiveHorizonMemory()
        model.observe(public_event(True))
        snapshot=model.record()
        with self.assertRaises(ValueError):
            model.observe({"features":{"inlet":0,"new_sensor":5},
                           "progress":True,"damage":False})
        self.assertEqual(model.record(),snapshot)

    def test_bad_or_reforged_invalid_record_rejected(self):
        model=AdaptiveHorizonMemory()
        model.observe(public_event(True))
        bad=copy.deepcopy(model.record())
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            AdaptiveHorizonMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            AdaptiveHorizonMemory.restore(bad)

    def test_no_phase_or_simulator_hidden_rule_in_persistent_state(self):
        model=AdaptiveHorizonMemory()
        for row in self.source:
            model.observe(row)
        state=model.record()["state"]
        self.assertEqual(set(state),{"schema","events"})
        self.assertEqual(set(state["events"][0]),
                         {"features","progress","damage"})
        for forbidden in ('"B"', '"return_A"', '"phase"', '"physics"',
                          '"episode"', '"hidden"'):
            self.assertNotIn(forbidden,str(state))

    def test_same_initial_public_state_hidden_reversed_physics(self):
        a=SameSchemaWorld(self.seed,"test",110000,"original")
        b=SameSchemaWorld(self.seed,"test",110000,"reversed")
        self.assertEqual(a.frame(),b.frame())
        pick=next(x["id"] for x in a.frame()["actions"]
                  if a._effect(x["features"])=="progress")
        self.assertEqual(a.step(pick,0)["progress"],1)
        self.assertEqual(b.step(pick,0)["damage"],1)

    def test_baselines_read_only_and_abstention_is_failure(self):
        fitted=build_models(self.source)
        self.assertEqual(len(fitted),7)
        initial=fitted["adaptive_horizon"].record()
        for method in METHODS:
            measured=eval_trial(self.seed,"original",110000,method,fitted)
            self.assertIn(measured["success"],(0,1))
            self.assertIn(measured["harmful_actions"],(0,1))
            if method=="always_abstain":
                self.assertEqual(measured["success"],0)
                self.assertEqual(measured["abstained"],1)
        self.assertEqual(fitted["adaptive_horizon"].record(),initial)
        self.assertFalse(hasattr(fitted["adaptive_horizon"],"step"))

    def test_precommitted_seeds_horizons_and_test_indices(self):
        self.assertEqual((ANCHOR,RECENT,LONG_WINDOW,LONG_SURPRISE_MIN),
                         (192,8,32,15))
        self.assertEqual(TEST_N,30)
        self.assertEqual(TEST_START,{"B":110000,"return_A":120000})
        self.assertEqual(CHECKPOINTS["B"],(0,2,4,6,8,12,16,24,32,48,64))
        self.assertEqual(len(METHODS),10)
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(DEV))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
