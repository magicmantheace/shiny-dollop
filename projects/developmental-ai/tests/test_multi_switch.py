"""Regression tests for same-schema repeated shifts and untrusted public reports."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.multi_switch_memory import (
    MultiSwitchContrastMemory, WARMUP, ENTRY_TAIL, ENTRY_ERRORS,
    ARCHIVE_SUPPORT_PROB, ARCHIVE_ADVANTAGE_RATIO,
    RETURN_SUPPORT_EVENTS, LONG_AFTER_RECENT
)
from developmental_ai.observable_affordances import digest
from benchmarks.multi_switch_benchmark import (
    DEV, ADDITIONAL, STAGES, CHECKPOINTS, START, TEST_N, METHODS,
    public_train, policies, play, measure
)
from benchmarks.same_schema_switch_benchmark import SameSchemaWorld


def event(progress=None):
    return {
        "features": {"inlet": 0, "outlet": 5 if progress is not None else 3},
        "progress": progress is True, "damage": progress is False,
    }


class MultiSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = DEV[0]

    def test_identical_public_schema_across_hidden_reversals(self):
        a=SameSchemaWorld(self.seed,"test",130000,"original")
        b=SameSchemaWorld(self.seed,"test",130000,"reversed")
        self.assertEqual(a.frame(),b.frame())
        self.assertNotIn("physics",str(a.frame()))
        action=next(x["id"] for x in a.frame()["actions"]
                    if a._effect(x["features"])=="progress")
        self.assertEqual(a.step(action,0)["progress"],1)
        self.assertEqual(b.step(action,0)["damage"],1)

    def test_repeated_reversal_and_return_without_phase_markers(self):
        learner=MultiSwitchContrastMemory()
        for _ in range(WARMUP):
            learner.observe(event(True))
        self.assertEqual(learner.selection()[0]["source"],"archive")
        for _ in range(12):
            learner.observe(event(False))
        self.assertEqual(learner.selection()[0]["source"],"recent8")
        for _ in range(36):
            learner.observe(event(False))
        self.assertEqual(learner.selection()[0]["source"],"recent32")
        for _ in range(4):
            learner.observe(event(True))
        self.assertEqual(learner.selection()[0]["source"],"archive")
        for _ in range(12):
            learner.observe(event(False))
        self.assertEqual(learner.selection()[0]["source"],"recent8")
        changes=[x["source"] for x in learner.selection()[0]["inferred_transitions"]]
        self.assertEqual(changes,["recent","archive","recent"])

    def test_neutral_outcomes_do_not_cause_false_reversion(self):
        learner=MultiSwitchContrastMemory()
        for _ in range(WARMUP):
            learner.observe(event(True))
        for _ in range(36):
            learner.observe(event(False))
        self.assertEqual(learner.selection()[0]["source"],"recent32")
        for _ in range(8):
            learner.observe(event(None))
        self.assertNotEqual(learner.selection()[0]["source"],"archive")

    def test_observed_label_flip_is_distinct_from_actual_actor_harm(self):
        observed,stats=public_train(self.seed,"original",1000,240)
        self.assertEqual(len(observed),240)
        self.assertEqual(stats["observations"],240)
        self.assertGreater(stats["label_flips"],0)
        self.assertEqual(public_train(self.seed,"original",1000,240),
                         (observed,stats))
        self.assertEqual(sum(int(x["damage"]) for x in observed),
                         stats["reported_harmful"])
        self.assertEqual(set(observed[0]),{"features","progress","damage"})
        self.assertEqual(stats["actual_harmful"]+stats["actual_productive"]+
                         stats["actual_neutral"],240)

    def test_read_only_test_scoring_checkpoint_replay(self):
        source,_=public_train(self.seed,"original",1000,240)
        learner=policies(source)["contrastive_multi"]
        record=learner.record()
        resumed=MultiSwitchContrastMemory.restore(copy.deepcopy(record))
        frame=SameSchemaWorld(self.seed,"test",130000,"reversed").frame()
        self.assertEqual(learner.selection()[0],resumed.selection()[0])
        self.assertEqual(learner.choose(frame),resumed.choose(frame))
        for method in METHODS:
            result=play(self.seed,"reversed",130000,method,policies(source))
            self.assertIn(result["success"],(0,1))
            if method=="always_abstain":
                self.assertEqual((result["success"],result["abstained"]),(0,1))
        self.assertEqual(learner.record(),record)

    def test_resume_refuses_invalid_rehashed_feedback_and_new_keys(self):
        learner=MultiSwitchContrastMemory()
        learner.observe(event(True))
        saved=learner.record()
        with self.assertRaises(ValueError):
            learner.observe({"features":{"new":0,"outlet":5},
                             "progress":True,"damage":False})
        self.assertEqual(learner.record(),saved)
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            MultiSwitchContrastMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            MultiSwitchContrastMemory.restore(bad)

    def test_only_three_public_event_fields_in_persistent_memory(self):
        reported,_=public_train(self.seed,"original",1000,240)
        learner=MultiSwitchContrastMemory()
        for row in reported:
            learner.observe(row)
        state=learner.record()["state"]
        self.assertEqual(set(state),{"schema","events"})
        for row in state["events"]:
            self.assertEqual(set(row),{"features","progress","damage"})
        for forbidden in ('"B1"','"B2"','"return_A"','"phase"','"physics"',
                          '"episode"','"actor_actual"'):
            self.assertNotIn(forbidden,str(state))

    def test_frozen_cohorts_and_horizon_policy_contract(self):
        self.assertEqual((WARMUP,ENTRY_TAIL,ENTRY_ERRORS),(240,4,2))
        self.assertEqual((ARCHIVE_SUPPORT_PROB,ARCHIVE_ADVANTAGE_RATIO),
                         (0.55,4.0))
        self.assertEqual((RETURN_SUPPORT_EVENTS,LONG_AFTER_RECENT),(2,24))
        self.assertEqual(TEST_N,20)
        self.assertEqual(START,{"B1":130000,"return_A":140000,"B2":150000})
        self.assertEqual(len(METHODS),10)
        self.assertEqual([x[0] for x in STAGES],["A","B1","return_A","B2"])
        self.assertEqual(CHECKPOINTS["B2"],(0,2,4,8,12,16,24,32,64))
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
