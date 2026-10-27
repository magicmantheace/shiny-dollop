"""Regression and negative-evidence checks for previously unseen C mapping.

Do not assert success on C: the important question is whether the known
A/B history is sufficient; failing or stalled episodes must be reported.
"""
from __future__ import annotations

import unittest

from developmental_ai.affordance_memory import FilteredNovel, token
from developmental_ai.contextual_affordance import CUES, ContextMemory
from developmental_ai.unseen_regime import ConservativeUnionRisk, UnseenDescriptorCargo
from benchmarks.contextual_affordance_benchmark import DEVELOPMENT, RESERVED, fit
from benchmarks.unseen_regime_benchmark import (
    EPISODES, START, VARIANTS, METHODS, run, measure
)


class UnseenRegimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEVELOPMENT[0]
        a,_=fit(cls.seed,"A");b,_=fit(cls.seed,"B")
        cls.memory=ContextMemory([[CUES["A"],a],[CUES["B"],b]])

    def test_c_is_untrained_third_descriptor_mapping_not_new_physics(self):
        a=UnseenDescriptorCargo(self.seed,"test",START,"A")
        b=UnseenDescriptorCargo(self.seed,"test",START,"B")
        c=UnseenDescriptorCargo(self.seed,"test",START,"C")
        self.assertEqual(a.frame()["base"],b.frame()["base"])
        self.assertEqual(a.frame()["base"],c.frame()["base"])
        self.assertEqual(a.world.world._features["fuel"],c.world.world._features["spoil"])
        self.assertEqual(a.world.world._features["spoil"],c.world.world._features["fuel"])
        self.assertNotEqual(b.world.world._features["spoil"],
                            c.world.world._features["spoil"])

    def test_learner_receives_only_numeric_public_frame(self):
        for variant in VARIANTS:
            frame=UnseenDescriptorCargo(self.seed,"test",START,variant).frame()
            self.assertEqual(set(frame),{"base","descriptors"})
            for hidden in ("phase","cue","spoil","fuel","variant","recipes"):
                self.assertNotIn(hidden,str(frame))

    def test_union_risk_is_exact_union_and_training_state_immutable(self):
        before=self.memory.record()
        united=ConservativeUnionRisk(self.memory)
        a=self.memory.choose_memory(CUES["A"]).avoid()
        b=self.memory.choose_memory(CUES["B"]).avoid()
        self.assertEqual(united.avoid(),a|b)
        self.assertEqual(before,self.memory.record())
        self.assertEqual(united.history_digest,before["sha256"])

    def test_read_only_known_environment_union_comparison(self):
        before=self.memory.record()
        for variant in ("A","B"):
            wins=[run(self.seed,"test",START+i,variant,"union",self.memory)["success"]
                  for i in range(5)]
            self.assertEqual(wins,[1]*5)
        self.assertEqual(before,self.memory.record())

    def test_unseen_c_can_differ_from_frozen_model_predictions(self):
        c=UnseenDescriptorCargo(self.seed,"test",START,"C")
        actual_hazard=token(c.world.world._features["spoil"])
        known=ConservativeUnionRisk(self.memory).avoid()
        # In C the "spoil" signature is that of the previously productive
        # fuel action. This alias is outside A/B's learned risk union.
        self.assertNotIn(actual_hazard,known)
        result=run(self.seed,"test",START,"C","union",self.memory)
        self.assertIn(result["success"],(0,1))

    def test_no_cue_and_probed_episodes_are_bounded(self):
        for variant in VARIANTS:
            result=run(self.seed,"test",START,variant,"no_cue",self.memory)
            self.assertLessEqual(result["attempts"],18)
            self.assertEqual(result["probe"],1)
            self.assertIn(result["success"],(0,1))

    def test_privileged_oracle_is_feasible_in_c(self):
        for variant in VARIANTS:
            row=run(self.seed,"test",START,variant,"privileged_oracle",self.memory)
            self.assertEqual(row["success"],1)
            self.assertEqual(row["spoilage"],0)

    def test_frozen_cohorts_cannot_be_relabeled(self):
        self.assertEqual((START,EPISODES),(9000,60))
        self.assertEqual(VARIANTS,("A","B","C"))
        self.assertEqual(METHODS,("no_cue","union","frozen_A","frozen_B","novel","privileged_oracle"))
        for invalid in ((DEVELOPMENT[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)

    def test_conservative_union_does_not_mutate_memory_during_probing(self):
        before=self.memory.record()
        world=UnseenDescriptorCargo(self.seed,"test",START,"A")
        learner=FilteredNovel(ConservativeUnionRisk(self.memory))
        frame=world.frame()
        action=learner.choose(frame)
        outcome=world.execute(action,frame["base"]["tick"])
        learner.feedback(frame,action,outcome["accepted"],outcome["public"])
        self.assertEqual(self.memory.record(),before)


if __name__=="__main__":
    unittest.main()
