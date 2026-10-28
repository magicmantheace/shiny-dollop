"""Review-before-use, owner-action analogue and C sandbox adaptation tests.

These only simulate approval: they do not grant permissions or deploy an
actual new policy in Developmental AI/AthenZ/Synveil.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.affordance_memory import RiskMemory
from developmental_ai.quarantined_c import CandidateRoute, StagedCReview
from developmental_ai.contextual_affordance import CUES, ContextMemory
from developmental_ai.unseen_regime import UnseenDescriptorCargo
from developmental_ai.outcome_skills import digest
from benchmarks.quarantined_c_benchmark import (
    DEVELOPMENT, RESERVED, TRAIN_N, VALIDATION_N, TEST_N,
    stage, trial, train_c, measure,
)


class QuarantinedAdaptationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEVELOPMENT[0]
        cls.review,cls.sources,cls.candidate,cls.training=stage(cls.seed)

    def test_actual_C_training_is_distinct_and_replayable(self):
        self.assertEqual(TRAIN_N,80)
        self.assertEqual(self.training["episodes"],80)
        self.assertEqual(len(self.candidate.events),80)
        self.assertEqual(self.candidate.record(),
                         RiskMemory.restore(self.candidate.record()).record())
        self.assertEqual(len(self.candidate.avoid()),1)
        self.assertTrue(self.candidate.avoid().isdisjoint(
            self.sources.choose_memory(CUES["A"]).avoid() |
            self.sources.choose_memory(CUES["B"]).avoid()))

    def test_review_has_three_disjoint_train_validation_cohorts(self):
        receipt=self.review.review()
        self.assertEqual(receipt["receipt"]["validation_split"],"train")
        self.assertEqual(receipt["receipt"]["validation_indices"],[1200,1223])
        self.assertTrue(receipt["receipt"]["eligible_for_explicit_approval"])
        for name in ("A","B","C"):
            self.assertEqual(receipt["receipt"]["validation"][name],
                             {"successes":24,"episodes":24,
                              "spoilage":0,"stalled":0})

    def test_no_implicit_grant_or_wrong_digest(self):
        with self.assertRaises(ValueError):
            CandidateRoute(self.sources,self.candidate)
        with self.assertRaises(ValueError):
            self.review.approve(approved=False,
                                receipt_sha256=self.review.review()["sha256"])
        with self.assertRaises(ValueError):
            self.review.approve(approved=True,receipt_sha256="0"*64)

    def test_rehearsal_A_B_C_and_known_return_no_mutation(self):
        source=self.sources.record()
        candidate=self.candidate.record()
        for environment in ("A","B","C","A"):
            case=trial(self.seed,"test",9300,environment,
                       "staged_C",self.sources,self.candidate)
            self.assertEqual(case["success"],1)
            self.assertEqual(case["spoilage"],0)
            self.assertEqual(case["stalled"],0)
        self.assertEqual(source,self.sources.record())
        self.assertEqual(candidate,self.candidate.record())

    def test_rehearsal_checkpoint_replay_rejects_wrong_source(self):
        agent=self.review.preview()
        world=UnseenDescriptorCargo(self.seed,"test",9301,"C")
        for _ in range(5):
            before=world.frame()
            if before["base"]["done"]:break
            action=agent.choose(before)
            if action is None:break
            result=world.execute(action,before["base"]["tick"])
            agent.feedback(before,action,result["accepted"],result["public"])
            checkpoint=agent.record()
            recovered=self.review.restore_route(agent,checkpoint)
            self.assertEqual(recovered.record(),checkpoint)
            if not world.world.world.base.done:
                self.assertEqual(agent.choose(world.frame()),
                                 recovered.choose(world.frame()))
        self.assertEqual(agent.mode(),"quarantined-C-memory")

    def test_tampered_rehashed_mode_rejected(self):
        agent=self.review.preview()
        world=UnseenDescriptorCargo(self.seed,"test",9302,"A")
        first=world.frame()
        action=agent.choose(first)
        result=world.execute(action,first["base"]["tick"])
        agent.feedback(first,action,result["accepted"],result["public"])
        bad=copy.deepcopy(agent.record())
        bad["state"]["mode"]="quarantined-C-memory"
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            self.review.restore_route(agent,bad)

    def test_reject_and_stale_validation_cannot_promote(self):
        review,_,_,_=stage(DEVELOPMENT[1])
        review.reject()
        with self.assertRaises(ValueError):
            review.approve(approved=True,receipt_sha256=review.review()["sha256"])
        other,_,_,_=stage(DEVELOPMENT[2])
        other._candidate.events[0]["success"]=not other._candidate.events[0]["success"]
        with self.assertRaises(ValueError):
            other.approve(approved=True,receipt_sha256=other.review()["sha256"])

    def test_subthreshold_rehearsal_blocks_explicit_approval(self):
        bad={name:{"episodes":24,"successes":24,
                   "spoilage":0,"stalled":0}
             for name in ("A","B","C")}
        bad["C"]["successes"]=23
        rejected=StagedCReview(self.sources,self.candidate,bad)
        self.assertFalse(rejected.review()["receipt"]["eligible_for_explicit_approval"])
        with self.assertRaisesRegex(ValueError,"failed validation"):
            rejected.approve(approved=True,receipt_sha256=rejected.review()["sha256"])

    def test_c_candidate_does_not_gain_by_hidden_recipe(self):
        seed=DEVELOPMENT[0]
        memory, _ = train_c(seed)
        self.assertNotIn("spoil",str(memory.record()))
        self.assertNotIn("true_hazard",str(memory.record()))
        self.assertEqual(memory.avoid(),self.candidate.avoid())

    def test_existing_no_promotion_sentinel_abstains_in_C(self):
        case=trial(self.seed,"test",9300,"C",
                   "old_sentinel",self.sources,self.candidate)
        self.assertEqual(case["success"],0)
        self.assertEqual(case["spoilage"],0)
        self.assertEqual(case["stalled"],1)

    def test_declared_cohort_restrictions(self):
        self.assertEqual(VALIDATION_N,24)
        self.assertEqual(TEST_N,60)
        for invalid in ((DEVELOPMENT[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)


if __name__=="__main__":
    unittest.main()
