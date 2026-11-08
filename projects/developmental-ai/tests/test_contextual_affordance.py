"""Tests for replayed context memories, changing descriptor meaning, A-B-A."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from developmental_ai.contextual_affordance import (
    CUES, ContextMemory, ContextNovel, ShiftedCargo, check, validate_cue
)
from developmental_ai.affordance_memory import signature, token
from developmental_ai.outcome_skills import digest
from benchmarks.contextual_affordance_benchmark import (
    DEVELOPMENT, RESERVED, TRAIN_N, TEST_N, fit, trial, measure
)


class ContextualAffordanceTests(unittest.TestCase):
    def test_swapped_action_codes_preserve_hidden_cargo_physics(self):
        a = ShiftedCargo(DEVELOPMENT[0],"test",8400,"A")
        b = ShiftedCargo(DEVELOPMENT[0],"test",8400,"B")
        self.assertEqual(a.frame()["public"]["base"],b.frame()["public"]["base"])
        self.assertNotEqual(a.frame()["cue"],b.frame()["cue"])
        self.assertEqual(a.world._features["spoil"],b.world._features["wash"])
        self.assertEqual(a.world._features["wash"],b.world._features["spoil"])

    def test_frozen_seed_collision_is_repaired_without_changing_protocol(self):
        seed=51013  # Frozen before code; raw load/spoil two-byte hashes collide.
        a=ShiftedCargo(seed,"test",8400,"A")
        b=ShiftedCargo(seed,"test",8400,"B")
        for obj in (a,b):
            fingerprints=[token(obj.world._features[name])
                          for name in obj.world.base._names]
            self.assertEqual(len(fingerprints),len(set(fingerprints)))
        self.assertNotEqual(a.world._features["spoil"],
                            a.world._features["load"])
        self.assertEqual(a.world._features["spoil"],
                         b.world._features["wash"])
        self.assertEqual(trial(seed,"test",8400,"A","risk_oracle")["success"],1)
        self.assertEqual(trial(seed,"test",8400,"B","risk_oracle")["success"],1)

    def test_public_context_has_no_private_names_or_recipes(self):
        for phase in ("A","B"):
            obj=ShiftedCargo(DEVELOPMENT[0],"test",8401,phase).frame()
            self.assertIs(check(obj),obj)
            for forbidden in ("spoil","wash","phase","hidden_rule","family"):
                self.assertNotIn(forbidden,str(obj))
            self.assertEqual(set(obj),{"public","cue"})
        with self.assertRaises(ValueError):validate_cue([False,2])
        with self.assertRaises(ValueError):validate_cue([1,1,1])

    def test_dangerous_descriptor_changes_between_phases(self):
        a,_=fit(DEVELOPMENT[0],"A")
        b,_=fit(DEVELOPMENT[0],"B")
        code_a=token(signature(DEVELOPMENT[0],"cargo","spoil"))
        code_b=token(signature(DEVELOPMENT[0],"cargo","wash"))
        self.assertEqual(a.avoid(),{code_a})
        self.assertEqual(b.avoid(),{code_b})
        self.assertNotEqual(a.avoid(),b.avoid())

    def test_context_selection_keeps_old_and_new_memories(self):
        a,_=fit(DEVELOPMENT[0],"A")
        b,_=fit(DEVELOPMENT[0],"B")
        model=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        self.assertEqual(model.choose_memory(CUES["A"]).avoid(),a.avoid())
        self.assertEqual(model.choose_memory(CUES["B"]).avoid(),b.avoid())
        # Deliberately ambiguous cue: both contexts are equidistant,
        # fixed tie selection is alphabetical and cannot detect phase.
        self.assertEqual(model.choose_memory([1,1]).avoid(),a.avoid())

    def test_replay_restart_a_b_a_goals(self):
        seed=DEVELOPMENT[0]
        a,_=fit(seed,"A")
        b,_=fit(seed,"B")
        model=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        restarted=ContextMemory.restore(copy.deepcopy(model.record()))
        self.assertEqual(restarted.record(),model.record())
        for phase,index in (("A",8400),("B",8400),("A",8500)):
            self.assertEqual(trial(seed,"test",index,phase,"context",model)["success"],1)
            self.assertEqual(trial(seed,"test",index,phase,"context",restarted)["success"],1)
        self.assertEqual(restarted.record(),model.record())

    def test_old_new_and_ambiguous_controls_can_fail_changed_context(self):
        seed=DEVELOPMENT[0]
        a,_=fit(seed,"A")
        b,_=fit(seed,"B")
        model=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        outcomes={method:sum(trial(seed,"test",8400+i,"B",method,model)["success"]
                             for i in range(12))
                  for method in ("context","A_only","ambiguous_cue")}
        self.assertEqual(outcomes["context"],12)
        self.assertLess(outcomes["A_only"],12)
        self.assertEqual(outcomes["A_only"],outcomes["ambiguous_cue"])

    def test_record_roundtrip_disk_and_stale_digest_rejected(self):
        seed=DEVELOPMENT[0]
        a,_=fit(seed,"A")
        b,_=fit(seed,"B")
        model=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"private"/"context-risk.json"
            model.save(path)
            restored=ContextMemory.load(path)
            self.assertEqual(model.record(),restored.record())
            path.write_text('{"tampered":true}',encoding="utf-8")
            with self.assertRaises(ValueError):ContextMemory.load(path)

    def test_size_limit_and_internal_evidence_tampering_rejected(self):
        seed=DEVELOPMENT[0]
        a,_=fit(seed,"A")
        b,_=fit(seed,"B")
        model=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        bad=copy.deepcopy(model.record())
        one=bad["state"]["contexts"][0]["memory"]
        first=next(iter(one["state"]["statistics"]))
        one["state"]["statistics"][first]["failures_with"]+=1
        one["sha256"]=digest(one["state"])
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):ContextMemory.restore(bad)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"too-large.json"
            path.write_bytes(b"x"*(4*1024*1024+1))
            with self.assertRaisesRegex(ValueError,"too large"):ContextMemory.load(path)

    def test_injected_or_mid_episode_context_change_is_rejected(self):
        seed=DEVELOPMENT[0]
        a,_=fit(seed,"A");b,_=fit(seed,"B")
        agent=ContextNovel(ContextMemory([[CUES["A"],a],[CUES["B"],b]]))
        world=ShiftedCargo(seed,"test",8402,"B")
        first=world.frame()
        choice=agent.choose(first)
        outcome=world.step(choice,first["public"]["base"]["tick"])
        broken=copy.deepcopy(outcome["frame"])
        broken["cue"]=list(CUES["A"])
        with self.assertRaisesRegex(ValueError,"mid-episode"):
            agent.feedback(first,choice,outcome["accepted"],broken)
        forged=copy.deepcopy(first);forged["private_action_names"]=["spoil"]
        with self.assertRaises(ValueError):check(forged)

    def test_frozen_cohorts_and_source_training_budget(self):
        self.assertEqual(TRAIN_N,80)
        self.assertEqual(TEST_N,60)
        for cohort in ((DEVELOPMENT[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(cohort)

    def test_privileged_oracle_is_reachable_in_both_phases(self):
        for phase in ("A","B"):
            self.assertEqual(trial(DEVELOPMENT[0],"test",8403,phase,
                                   "full_oracle")["success"],1)
            self.assertEqual(trial(DEVELOPMENT[0],"test",8403,phase,
                                   "risk_oracle")["spoilage"],0)


if __name__=="__main__":
    unittest.main()
