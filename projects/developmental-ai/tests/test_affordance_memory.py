"""Affordance-risk evidence, replay, and negative-control tests."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from developmental_ai.affordance_memory import (
    SCHEMA, DescribedWorld, FilteredNovel, RiskMemory, check, record_step,
    signature, token
)
from developmental_ai.outcome_skills import digest
from benchmarks.affordance_benchmark import (
    DEVELOPMENT, RESERVED, TRAIN_EPISODES, TEST_EPISODES, TEST_START, learn,
    run, measure
)
from benchmarks.opaque_causal_benchmark import episode as original_episode


class AffordanceMemoryTests(unittest.TestCase):
    def test_opaque_action_ids_change_but_public_numeric_descriptors_persist(self):
        a=DescribedWorld(DEVELOPMENT[0],"train",0,"cargo").frame()
        b=DescribedWorld(DEVELOPMENT[0],"train",1,"cargo").frame()
        self.assertNotEqual(a["base"]["actions"],b["base"]["actions"])
        self.assertEqual({token(x["signature"]) for x in a["descriptors"]},
                         {token(x["signature"]) for x in b["descriptors"]})
        self.assertNotIn("spoil",str(a))
        self.assertNotIn("hidden_name",str(a))

    def test_descriptor_shuffle_ablation_defeats_stable_reidentification(self):
        a=DescribedWorld(DEVELOPMENT[0],"test",TEST_START,"cargo").frame()
        b=DescribedWorld(DEVELOPMENT[0],"test",TEST_START,"cargo",remap=True).frame()
        self.assertEqual(a["base"],b["base"])
        self.assertNotEqual({token(v["signature"]) for v in a["descriptors"]},
                            {token(v["signature"]) for v in b["descriptors"]})

    def test_public_frame_refuses_forged_action_descriptor(self):
        a=DescribedWorld(DEVELOPMENT[0],"train",2,"cargo").frame()
        self.assertIs(check(a),a)
        bad=copy.deepcopy(a);bad["descriptors"][0]["id"]="a_"+"a"*18
        with self.assertRaises(ValueError):check(bad)
        bad=copy.deepcopy(a);bad["descriptors"][0]["signature"]=[0,False,4]
        with self.assertRaises(ValueError):check(bad)
        bad=copy.deepcopy(a);bad["simulator_name"]="spoil"
        with self.assertRaises(ValueError):check(bad)

    def test_episode_local_feedback_and_blocked_event_effects(self):
        world=DescribedWorld(DEVELOPMENT[0],"train",3,"cargo")
        policy=FilteredNovel()
        frame=world.frame()
        action=policy.choose(frame)
        response=world.step(action,frame["base"]["tick"])
        row=policy.feedback(frame,action,response["accepted"],response["frame"])
        self.assertEqual(row["accepted"],response["accepted"])
        if not row["accepted"]:
            self.assertEqual(row["increases"],0)
            self.assertEqual(row["decreases"],0)

    def test_disallows_injected_reward_and_hidden_label(self):
        world=DescribedWorld(DEVELOPMENT[0],"train",4,"cargo")
        before=world.frame();action=before["base"]["actions"][0]
        response=world.step(action,before["base"]["tick"])
        after=copy.deepcopy(response["frame"])
        after["reward"]=1
        with self.assertRaises(ValueError):
            record_step(before,action,response["accepted"],after)

    def test_risk_memory_discovers_correlated_failure_association(self):
        memory=RiskMemory()
        risk=[1,2];safe=[4,5]
        failure={"signature":risk,"accepted":True,"increases":1,"decreases":1}
        success={"signature":safe,"accepted":True,"increases":1,"decreases":0}
        for i in range(10):
            memory.add(i,[failure] if i<5 else [success],success=i>=5)
        self.assertEqual(memory.avoid(),{token(risk)})
        self.assertFalse(memory.analysis()[token(safe)]["risk_candidate"])

    def test_hash_and_signature_bounded(self):
        with self.assertRaises(ValueError):token([1,256])
        with self.assertRaises(ValueError):token([True,2])
        with self.assertRaises(ValueError):token(["1",2])
        self.assertEqual(len(signature(DEVELOPMENT[0],"cargo","spoil")),2)

    def test_train_memory_restores_and_does_not_change_on_test(self):
        seed=DEVELOPMENT[0]
        m,training=learn(seed)
        self.assertEqual(len(training),TRAIN_EPISODES)
        saved=m.record()
        replica=RiskMemory.restore(copy.deepcopy(saved))
        self.assertEqual(replica.record(),saved)
        first=run(seed,"test",TEST_START,"cargo","learned",replica)
        self.assertEqual(first,run(seed,"test",TEST_START,"cargo","learned",m))
        self.assertEqual(saved,m.record())
        self.assertEqual(saved,replica.record())

    def test_atomic_disk_checkpoint_survives_restart_and_corrupt_restore(self):
        trained,_=learn(DEVELOPMENT[0])
        with tempfile.TemporaryDirectory() as temporary:
            file=Path(temporary)/"private"/"learned-risks.json"
            trained.save(file)
            self.assertTrue(file.is_file())
            restored=RiskMemory.load(file)
            self.assertEqual(trained.record(),restored.record())
            self.assertEqual(
                run(DEVELOPMENT[0],"test",TEST_START,"cargo","learned",trained),
                run(DEVELOPMENT[0],"test",TEST_START,"cargo","learned",restored))
            file.write_text('{"bad":true}',encoding="utf-8")
            with self.assertRaises(ValueError):RiskMemory.load(file)

    def test_checkpoint_file_size_limit_rejects_invalid_large_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            file=Path(temporary)/"oversized.json"
            file.write_bytes(b"x"*(2*1024*1024+1))
            with self.assertRaisesRegex(ValueError,"exceeds configured limit"):
                RiskMemory.load(file)

    def test_record_rejects_corrupted_stats_even_rehashed(self):
        memory,_=learn(DEVELOPMENT[0])
        bad=copy.deepcopy(memory.record())
        first=next(iter(bad["state"]["statistics"]))
        bad["state"]["statistics"][first]["failures_with"]+=1
        bad["sha256"]=digest(bad["state"])
        with self.assertRaisesRegex(ValueError,"does not replay"):
            RiskMemory.restore(bad)

    def test_invalid_episode_order_and_injected_transitions(self):
        m=RiskMemory()
        accepted={"signature":[1,2],"accepted":True,"increases":1,"decreases":0}
        with self.assertRaises(ValueError):m.add(1,[accepted],True)
        with self.assertRaises(ValueError):m.add(0,[dict(accepted,script="run")],True)
        with self.assertRaises(ValueError):m.add(0,[dict(accepted,accepted=False)],True)
        m.add(0,[accepted],True)
        with self.assertRaises(ValueError):m.add(0,[accepted],True)

    def test_no_memory_matches_old_novel_first_baseline(self):
        for family in ("cargo","relay"):
            for i in range(4):
                old=original_episode(DEVELOPMENT[0],"test",TEST_START+i,family,"novel")
                new=run(DEVELOPMENT[0],"test",TEST_START+i,family,"novel")
                self.assertEqual(new["success"],old["success"])
                self.assertEqual(new["attempts"],old["attempts"])
                self.assertEqual(new["blocked"],old["blocked"])

    def test_privileged_oracle_completes_and_no_simulator_damage(self):
        for family in ("cargo","relay"):
            result=run(DEVELOPMENT[0],"test",TEST_START,family,"full_oracle")
            self.assertEqual(result["success"],1)
            self.assertEqual(result["spoilage"],0)

    def test_public_harm_filter_never_reads_privileged_source(self):
        m,_=learn(DEVELOPMENT[0])
        world=DescribedWorld(DEVELOPMENT[0],"test",TEST_START,"cargo")
        p=FilteredNovel(m)
        action=p.choose(world.frame())
        self.assertIn(action,world.frame()["base"]["actions"])
        visible={row["id"]:token(row["signature"]) for row in world.frame()["descriptors"]}
        self.assertNotIn(visible[action],m.avoid())

    def test_no_new_lookahead_or_test_leakage_in_cohort_definition(self):
        self.assertEqual(TRAIN_EPISODES,80)
        self.assertEqual(TEST_EPISODES,60)
        self.assertEqual(TEST_START,8200)
        for invalid in ((DEVELOPMENT[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)


if __name__=="__main__":
    unittest.main()
