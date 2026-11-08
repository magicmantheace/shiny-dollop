"""Predictive gating for harmful relation transfer, restart and limitations."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.gated_relation_memory import GatedRelationMemory,TAIL,MIN_TARGET
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory
from developmental_ai.observable_affordances import digest
from benchmarks.relation_conflict_benchmark import (
    DEV,ADDITIONAL,CHECKPOINTS,TEST_START,TEST_N,METHODS,
    trained,evaluate,measure
)
from benchmarks.relation_transfer_benchmark import (
    RelationWorld, observed, play
)


def feedback(features,positive):
    return {"features":features,"progress":bool(positive),
            "damage":not bool(positive)}


class RelationConflictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source=observed(cls.seed,"basin",20)

    def test_new_unknown_schema_uses_source_prior_before_target_feedback(self):
        m=trained(self.source)
        target={"north":1,"charge":4,"plume":6}
        choice,model=m.selection(target)
        self.assertEqual(choice["source"],"source")
        self.assertEqual(choice["target_observations"],0)
        self.assertEqual(model.record(),RelationOutcomeMemory.restore(
            model.record()).record())

    def test_independent_tail_detects_incompatible_relation(self):
        old={"inlet":0,"outlet":5}
        new={"north":0,"charge":3,"plume":5}
        m=trained([feedback(old,True) for _ in range(16)])
        for _ in range(7):
            m.observe(feedback(new,False))
        decision,_=m.selection(new)
        self.assertEqual(decision["source"],"source")
        m.observe(feedback(new,False))
        decision,_=m.selection(new)
        self.assertEqual(decision["source"],"target")
        self.assertEqual(decision["validation_events"],4)
        self.assertEqual(decision["target_observations"],8)
        self.assertGreater(decision["log_margin"],0)
        # Existing skill was not overwritten by new outcomes.
        self.assertEqual(m.selection(old)[0]["source"],"source")

    def test_compatible_new_schema_keeps_old_model(self):
        old={"inlet":0,"outlet":5}
        new={"north":0,"charge":3,"plume":5}
        m=trained([feedback(old,True) for _ in range(16)])
        for _ in range(8):
            m.observe(feedback(new,True))
        decision,_=m.selection(new)
        self.assertEqual(decision["source"],"source")

    def test_checkpoint_resume_same_action_and_evidence(self):
        source=observed(self.seed,"basin",30)
        target=observed(self.seed,"counterphase",10)
        m=trained(source+target)
        saved=m.record()
        restored=GatedRelationMemory.restore(copy.deepcopy(saved))
        self.assertEqual(saved,restored.record())
        frame=RelationWorld(self.seed,"test",55000,"counterphase").frame()
        self.assertEqual(m.choose(frame),restored.choose(frame))
        self.assertEqual(m.selection(frame["actions"][0]["features"])[0],
                         restored.selection(frame["actions"][0]["features"])[0])
        self.assertEqual(restored.record(),saved)

    def test_invalid_or_rehashed_malformed_event_rejected(self):
        m=trained(self.source)
        bad=copy.deepcopy(m.record())
        bad["state"]["events"][0]["damage"]=False
        with self.assertRaises(ValueError):
            GatedRelationMemory.restore(bad)
        bad["state"]["events"][0]["features"]["inlet"]=True
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            GatedRelationMemory.restore(bad)

    def test_no_stage_markers_or_action_identifiers_in_model_evidence(self):
        m=trained(self.source)
        data=m.record()["state"]
        self.assertEqual(set(data),{"schema","events"})
        self.assertEqual(set(data["events"][0]),{"features","progress","damage"})
        for forbidden in ('"lattice"','"counterphase"','"family"','"goal"','"action_id"'):
            self.assertNotIn(forbidden,str(data))

    def test_training_actor_is_separate_from_policy(self):
        m=trained(self.source)
        policies={"gated_relation":m}
        before=m.record()
        for family in ("basin","lattice","prism","counterphase"):
            outcome=evaluate(self.seed,family,55000,"gated_relation",policies)
            self.assertIn(outcome["success"],(0,1))
        self.assertEqual(m.record(),before)
        self.assertFalse(hasattr(m,"step"))
        self.assertFalse(hasattr(m,"probe"))

    def test_structural_controls_cohorts_and_evidence_budget(self):
        self.assertEqual((TAIL,MIN_TARGET),(4,8))
        self.assertEqual(CHECKPOINTS,(0,4,8,16,24,64))
        self.assertEqual(TEST_START,55000)
        self.assertEqual(TEST_N,40)
        self.assertEqual(len(METHODS),7)
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((5,6,7),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
