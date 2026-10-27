"""No-cue source-history selection tests. No private simulator recipes in policy."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.contextual_affordance import CUES, ContextMemory, ShiftedCargo, key
from developmental_ai.no_cue_diagnostic import (
    NoCueProbe, diagnostic_table, select_probe, MIN_OBSERVATIONS
)
from developmental_ai.outcome_skills import digest
from benchmarks.contextual_affordance_benchmark import fit
from benchmarks.no_cue_probe_benchmark import (
    DEVELOPMENT, RESERVED, TEST_N, PERIODS, run, measure
)


class NoCueProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEVELOPMENT[0]
        a,_=fit(cls.seed,"A")
        b,_=fit(cls.seed,"B")
        cls.memories=ContextMemory([[CUES["A"],a],[CUES["B"],b]])

    def test_only_public_frame_accepted_no_beacon_or_phase(self):
        f=ShiftedCargo(self.seed,"test",8700,"B").frame()["public"]
        self.assertEqual(set(f),{"base","descriptors"})
        self.assertNotIn("cue",str(f))
        self.assertNotIn("phase",str(f))
        agent=NoCueProbe(self.memories)
        self.assertIn(agent.choose(f),f["base"]["actions"])
        with self.assertRaises(ValueError):
            NoCueProbe(self.memories).choose({"public":f,"cue":CUES["B"]})

    def test_training_evidence_is_first_step_observation_not_privileged_label(self):
        table=diagnostic_table(self.memories)
        candidate=select_probe(self.memories)
        self.assertIsNotNone(candidate)
        self.assertEqual(set(candidate),{"token","likelihoods"})
        self.assertEqual(set(candidate["likelihoods"]),set(table))
        for name in table:
            self.assertGreaterEqual(table[name][candidate["token"]][1],
                                    MIN_OBSERVATIONS)
        self.assertNotIn("spoil",str(candidate))
        self.assertNotIn("wash",str(candidate))

    def test_first_step_probe_is_observed_without_hidden_context(self):
        for phase in ("A","B"):
            world=ShiftedCargo(self.seed,"test",8700,phase)
            agent=NoCueProbe(self.memories)
            frame=world.frame()["public"]
            self.assertTrue(all(x==0 for x in frame["base"]["channels"]))
            action=agent.choose(frame)
            observed=world.step(action,frame["base"]["tick"])
            agent.feedback(frame,action,observed["accepted"],
                           observed["frame"]["public"])
            self.assertEqual(agent.selected,key(CUES[phase]))
            self.assertEqual(len(agent.events),1)
            self.assertEqual(agent._controller.history[0]["action"],action)
            self.assertEqual(agent._controller.history[0]["accepted"],
                             observed["accepted"])

    def test_mid_episode_checkpoint_replays_same_next_action(self):
        for phase in ("A","B"):
            w=ShiftedCargo(self.seed,"test",8702,phase)
            learner=NoCueProbe(self.memories)
            for _ in range(4):
                f=w.frame()["public"]
                if f["base"]["done"]:break
                a=learner.choose(f)
                if a is None:break
                o=w.step(a,f["base"]["tick"])
                learner.feedback(f,a,o["accepted"],o["frame"]["public"])
            saved=learner.record()
            again=NoCueProbe.restore(self.memories,copy.deepcopy(saved))
            self.assertEqual(saved,again.record())
            if not w.world.base.done:
                f=w.frame()["public"]
                self.assertEqual(again.choose(f),learner.choose(f))

    def test_tampered_policy_selection_rejected_even_after_rehash(self):
        w=ShiftedCargo(self.seed,"test",8703,"A")
        agent=NoCueProbe(self.memories)
        f=w.frame()["public"];a=agent.choose(f)
        o=w.step(a,f["base"]["tick"])
        agent.feedback(f,a,o["accepted"],o["frame"]["public"])
        forged=copy.deepcopy(agent.record())
        forged["state"]["selected"]="fake-history"
        forged["sha256"]=digest(forged["state"])
        with self.assertRaises(ValueError):NoCueProbe.restore(self.memories,forged)

    def test_mismatched_prior_memory_is_rejected(self):
        w=ShiftedCargo(self.seed,"test",8704,"A")
        agent=NoCueProbe(self.memories)
        f=w.frame()["public"];a=agent.choose(f)
        o=w.step(a,f["base"]["tick"])
        agent.feedback(f,a,o["accepted"],o["frame"]["public"])
        other_a,_=fit(DEVELOPMENT[1],"A")
        other_b,_=fit(DEVELOPMENT[1],"B")
        other=ContextMemory([[CUES["A"],other_a],[CUES["B"],other_b]])
        with self.assertRaisesRegex(ValueError,"other training state"):
            NoCueProbe.restore(other,agent.record())

    def test_wrong_public_feedback_cannot_fake_context(self):
        w=ShiftedCargo(self.seed,"test",8705,"B")
        learner=NoCueProbe(self.memories)
        f=w.frame()["public"];a=learner.choose(f)
        o=w.step(a,f["base"]["tick"])
        with self.assertRaises(ValueError):
            learner.feedback(f,a,not o["accepted"],o["frame"]["public"])
        self.assertFalse(learner.events)

    def test_no_cue_diagnostics_and_fixed_probe_control_both_run(self):
        for phase in ("A","B"):
            normal=run(self.seed,"test",8700,phase,"no_cue",self.memories)
            fixed=run(self.seed,"test",8700,phase,"probe_then_A",self.memories)
            self.assertIn(normal["success"],(0,1))
            self.assertIn(fixed["success"],(0,1))
            self.assertEqual(normal["probe"],fixed["probe"])
            self.assertEqual(normal["correct"],1)
            self.assertEqual(normal["abstained"],0)

    def test_read_only_evaluations_do_not_update_source_histories(self):
        old=self.memories.record()
        for phase in ("A","B","A"):
            for n in range(3):
                run(self.seed,"test",8800+n,phase,"no_cue",self.memories)
        self.assertEqual(self.memories.record(),old)

    def test_invalid_cohorts_and_frozen_indices(self):
        self.assertEqual(TEST_N,60)
        self.assertEqual(PERIODS,(("A",8700),("B",8700),("A_return",8800)))
        for invalid in ((DEVELOPMENT[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)

    def test_future_action_feedback_requires_observation(self):
        model=NoCueProbe(self.memories)
        world=ShiftedCargo(self.seed,"test",8706,"A")
        frame=world.frame()["public"]
        selected=model.choose(frame)
        wrong=next(a for a in frame["base"]["actions"] if a!=selected)
        out=world.step(selected,frame["base"]["tick"])
        with self.assertRaises(ValueError):
            model.feedback(frame,wrong,out["accepted"],out["frame"]["public"])


if __name__=="__main__":
    unittest.main()
