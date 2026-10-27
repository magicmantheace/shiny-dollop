"""Same sensor-key regime shifts, no phase supervision, honest harm totals."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.same_schema_switch_memory import (
    SameSchemaSwitchMemory,ANCHOR,RECENT_TRAIN,VALIDATION_TAIL
)
from developmental_ai.observable_affordances import digest
from benchmarks.same_schema_switch_benchmark import (
    DEV,ADDITIONAL,STAGES,CHECKPOINTS,TEST_N,METHODS,TEST_START,
    SameSchemaWorld,actor_event,training,build_models,eval_episode,measure
)


def row(positive):
    return {"features":{"inlet":0,"outlet":5},
            "progress":positive,"damage":not positive}


class SameSchemaSwitchTests(unittest.TestCase):
    def test_same_keys_and_action_list_for_reverse_physics(self):
        a=SameSchemaWorld(DEV[0],"test",60000,"original")
        b=SameSchemaWorld(DEV[0],"test",60000,"reversed")
        self.assertEqual(a.frame(),b.frame())
        self.assertNotIn("physics",str(a.frame()))
        self.assertNotIn("reversed",str(b.frame()))
        self.assertEqual(a.episode,b.episode)
        # Same handle, opposite hidden physics, public observed damage flips.
        pick=next(x["id"] for x in a.frame()["actions"]
                  if a._effect(x["features"])=="progress")
        self.assertTrue(a.step(pick,0)["progress"]==1)
        self.assertTrue(b.step(pick,0)["damage"]==1)

    def test_selection_responds_to_contradictory_feedback_without_label(self):
        m=SameSchemaSwitchMemory()
        for _ in range(240):m.observe(row(True))
        plan,_=m.selection()
        self.assertEqual(plan["source"],"anchor")
        for _ in range(24):m.observe(row(False))
        plan,_=m.selection()
        self.assertEqual(plan["source"],"recent")
        self.assertEqual(plan["candidate_train_overlap"],0)
        self.assertEqual(plan["evidence_events"],4)
        for _ in range(24):m.observe(row(True))
        plan,_=m.selection()
        self.assertEqual(plan["source"],"anchor")

    def test_unknown_signature_rejected_without_mutating_history(self):
        m=SameSchemaSwitchMemory()
        m.observe(row(True))
        saved=m.record()
        with self.assertRaises(ValueError):
            m.observe({"features":{"different":0,"outlet":5},
                       "progress":True,"damage":False})
        self.assertEqual(m.record(),saved)

    def test_same_schema_persistent_replay_and_action(self):
        m=SameSchemaSwitchMemory()
        for _ in range(240):m.observe(row(True))
        for _ in range(16):m.observe(row(False))
        snapshot=m.record()
        copy_m=SameSchemaSwitchMemory.restore(copy.deepcopy(snapshot))
        self.assertEqual(snapshot,copy_m.record())
        self.assertEqual(m.selection()[0],copy_m.selection()[0])
        frame=SameSchemaWorld(DEV[0],"test",60000,"reversed").frame()
        self.assertEqual(m.choose(frame),copy_m.choose(frame))

    def test_checksum_and_rehashed_invalid_event_refused(self):
        m=SameSchemaSwitchMemory()
        m.observe(row(True))
        saved=m.record()
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["damage"]=True
        with self.assertRaises(ValueError):
            SameSchemaSwitchMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            SameSchemaSwitchMemory.restore(bad)

    def test_no_phase_or_episode_identifier_in_training_memory(self):
        m=SameSchemaSwitchMemory()
        for i in range(8):
            m.observe(actor_event(DEV[0],"original",1000+i))
        self.assertEqual(set(m.record()["state"]),{"schema","events"})
        self.assertEqual(set(m.events[0]),{"features","progress","damage"})
        for forbidden in ('"B"','"return_A"','"phase"','"physics"','"episode"'):
            self.assertNotIn(forbidden,str(m.record()))

    def test_predictions_are_read_only_and_abstentions_fail(self):
        events=training(DEV[0],"original",1000,240)
        models=build_models(events)
        saved=models["adaptive_same_schema"].record()
        for method in METHODS:
            output=eval_episode(DEV[0],"reversed",60000,method,models)
            self.assertIn(output["success"],(0,1))
            self.assertIn(output["harmful_actions"],(0,1))
            if method=="always_abstain":
                self.assertEqual(output["success"],0)
                self.assertEqual(output["abstained"],1)
        self.assertEqual(models["adaptive_same_schema"].record(),saved)
        self.assertFalse(hasattr(models["adaptive_same_schema"],"step"))
        self.assertFalse(hasattr(models["adaptive_same_schema"],"probe"))

    def test_frozen_budgets_and_prohibited_alternative_cohorts(self):
        self.assertEqual((ANCHOR,RECENT_TRAIN,VALIDATION_TAIL),(192,12,4))
        self.assertEqual([a[0] for a in STAGES],["A","B","return_A"])
        self.assertEqual(CHECKPOINTS["B"],(0,4,8,12,16,24,48,64))
        self.assertEqual(TEST_N,30)
        self.assertEqual(TEST_START,{"B":60000,"return_A":70000})
        self.assertEqual(len(METHODS),9)
        for cohort in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):measure(cohort)


if __name__=="__main__":
    unittest.main()
