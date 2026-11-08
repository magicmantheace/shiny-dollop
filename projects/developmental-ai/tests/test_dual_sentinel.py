"""Positive retention AND explicit unknown-regime abstention tests."""
from __future__ import annotations

import copy
import unittest
from developmental_ai.contextual_affordance import CUES, ContextMemory
from developmental_ai.dual_sentinel import DualSentinel, sentinel_design
from developmental_ai.outcome_skills import digest
from developmental_ai.unseen_regime import UnseenDescriptorCargo
from benchmarks.contextual_affordance_benchmark import DEVELOPMENT, RESERVED, fit
from benchmarks.dual_sentinel_benchmark import (
    START, EPISODES, METHODS, sentinel_episode, measure
)


class DualSentinelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEVELOPMENT[0]
        a,_=fit(cls.seed,"A")
        b,_=fit(cls.seed,"B")
        cls.memories=ContextMemory([[CUES["A"],a],[CUES["B"],b]])

    def test_design_from_public_history_only(self):
        plan=sentinel_design(self.memories)
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan["codes"]),2)
        self.assertEqual(len(set(plan["codes"])),2)
        self.assertEqual(len(set(tuple(v) for v in plan["profiles"].values())),2)
        self.assertEqual(set(plan),{"codes","profiles"})
        for bad in ("spoil","wash","fuel","recipes"):
            self.assertNotIn(bad,str(plan))

    def test_known_regimes_retain_task_ability(self):
        for env in ("A","B"):
            row=sentinel_episode(self.seed,START,env,self.memories)
            self.assertEqual(row["success"],1)
            self.assertEqual(row["spoilage"],0)
            self.assertEqual(row["unknown"],0)
            self.assertEqual(row["known_match"],1)

    def test_untrained_regime_flagged_without_spoilage_but_task_not_completed(self):
        row=sentinel_episode(self.seed,START,"C",self.memories)
        self.assertEqual(row["unknown"],1)
        self.assertEqual(row["spoilage"],0)
        self.assertEqual(row["success"],0)
        self.assertEqual(row["stalled"],1)
        self.assertEqual(row["attempts"],2)

    def test_replay_known_and_unknown_actions(self):
        for variant in ("A","B","C"):
            world=UnseenDescriptorCargo(self.seed,"test",START,variant)
            agent=DualSentinel(self.memories)
            for _ in range(4):
                before=world.frame()
                action=agent.choose(before)
                if action is None:break
                result=world.execute(action,before["base"]["tick"])
                agent.feedback(before,action,result["accepted"],result["public"])
                checkpoint=agent.record()
                replica=DualSentinel.restore(self.memories,copy.deepcopy(checkpoint))
                self.assertEqual(replica.record(),checkpoint)
                if not world.world.world.base.done:
                    self.assertEqual(replica.choose(world.frame()),
                                     agent.choose(world.frame()))

    def test_tamper_rehashed_selected_context_rejected(self):
        world=UnseenDescriptorCargo(self.seed,"test",START,"A")
        agent=DualSentinel(self.memories)
        for _ in range(2):
            before=world.frame()
            action=agent.choose(before)
            result=world.execute(action,before["base"]["tick"])
            agent.feedback(before,action,result["accepted"],result["public"])
        broken=copy.deepcopy(agent.record())
        broken["state"]["unknown"]=True
        broken["sha256"]=digest(broken["state"])
        with self.assertRaises(ValueError):
            DualSentinel.restore(self.memories,broken)

    def test_forged_private_phase_information_rejected(self):
        world=UnseenDescriptorCargo(self.seed,"test",START,"B")
        public=world.frame()
        self.assertEqual(set(public),{"base","descriptors"})
        for text in ("phase","variant","spoil","fuel","cue"):
            self.assertNotIn(text,str(public))
        public["phase"]="B"
        with self.assertRaises(ValueError):
            DualSentinel(self.memories).choose(public)

    def test_reject_wrong_training_checkpoint(self):
        world=UnseenDescriptorCargo(self.seed,"test",START,"A")
        agent=DualSentinel(self.memories)
        before=world.frame();action=agent.choose(before)
        after=world.execute(action,before["base"]["tick"])
        agent.feedback(before,action,after["accepted"],after["public"])
        other_seed=DEVELOPMENT[1]
        a,_=fit(other_seed,"A");b,_=fit(other_seed,"B")
        other=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        with self.assertRaises(ValueError):
            DualSentinel.restore(other,agent.record())

    def test_no_test_mutation_or_silent_promotion(self):
        saved=self.memories.record()
        for variant in ("A","B","C"):
            sentinel_episode(self.seed,START,variant,self.memories)
        self.assertEqual(saved,self.memories.record())

    def test_benchmark_probe_summary_uses_shared_schema(self):
        # Prevent recurrence of the first focused-run KeyError('probe'):
        # the new episode and historical summarizer must agree.
        from benchmarks.dual_sentinel_benchmark import report_rows
        from benchmarks.unseen_regime_benchmark import summarise
        episode=sentinel_episode(self.seed,START,"C",self.memories)
        summary=report_rows([episode])
        self.assertEqual(summary["episodes"],1)
        self.assertEqual(summary["probed"],1)
        self.assertEqual(summary["unknown"],1)
        self.assertEqual(summary["successes"],0)
        self.assertEqual(summary["spoilage"],0)
        self.assertEqual(summarise([episode])["successes"],0)

    def test_frozen_cohorts_and_methods(self):
        self.assertEqual(EPISODES,60)
        self.assertEqual(METHODS[0],"sentinel")
        for bad in ((DEVELOPMENT[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):
                measure(bad)


if __name__=="__main__":
    unittest.main()
