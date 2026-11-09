"""Public-sensor learned update and replay checks. No hidden state in policy."""
import copy
import random
import tempfile
import unittest
from pathlib import Path

from developmental_ai.environment_api import EnvironmentSession, digest
from developmental_ai.learned_spatial_memory import (
    LearnedOffsetUpdater, PortableOffsetMemory, train_grid_updates,
)
from benchmarks.learned_memory_transfer_benchmark import measure, trial
from developmental_ai.transfer import TransferBrain


class LearnedMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = train_grid_updates(2749, episodes=24)

    def test_public_grid_learning_discovers_action_updates(self):
        expected = {0:(0,1), 1:(0,-1), 2:(1,0), 3:(-1,0)}
        for action, change in expected.items():
            self.assertEqual(self.model.update(action,"move"),change)
            self.assertEqual(self.model.update(action,"blocked"),(0,0))
        self.assertEqual(self.model.update(4,"empty_eat"),(0,0))

    def test_restart_training_is_deterministic_and_model_bound(self):
        other = train_grid_updates(2749, episodes=24)
        self.assertEqual(self.model.record(), other.record())
        self.assertEqual(self.model.record(), LearnedOffsetUpdater.restore(self.model.record()).record())
        self.assertNotEqual(self.model.fingerprint, train_grid_updates(6607,episodes=24).fingerprint)

    def test_only_public_sensor_snapshots_are_accepted(self):
        nav = PortableOffsetMemory(self.model)
        session = EnvironmentSession("occluded",2749,"test",99211)
        frame = session.frame()
        invalid = copy.deepcopy(frame)
        invalid["observation"]["true_position"]=[1,2]
        with self.assertRaises(ValueError): nav.features(invalid)
        self.assertEqual(nav.tick,0)
        nav.features(frame)
        bad = copy.deepcopy(frame)
        bad["tick"]=1
        with self.assertRaises(ValueError): nav.features(bad)

    def test_occluded_memory_matches_accumulated_learned_transitions(self):
        nav = PortableOffsetMemory(self.model)
        session = EnvironmentSession("occluded",2749,"test",99211)
        total = None
        for _ in range(10):
            if session.done: break
            frame = session.frame()
            features = nav.features(frame)
            if total is None: total = list(frame["observation"]["beacon"])
            self.assertEqual(features[:2],tuple(max(-3,min(3,v)) for v in total))
            action = next(a for a in frame["available_actions"] if a<4 and not (frame["observation"]["blocked"] & (1<<a)))
            result = session.step(action,expected_tick=frame["tick"])
            update = self.model.update(action,result["event"])
            nav.feedback(action,result)
            for j in range(2): total[j] += update[j]
            self.assertEqual(nav.snapshot()["data"]["remaining"],total)

    def test_snapshot_exact_replay_mid_episode(self):
        nav = PortableOffsetMemory(self.model)
        session=EnvironmentSession("occluded",2749,"test",99211)
        for _ in range(8):
            if session.done:break
            frame=session.frame()
            nav.features(frame)
            action=0
            result=session.step(action,expected_tick=frame["tick"])
            nav.feedback(action,result)
        record=nav.snapshot()
        restored=PortableOffsetMemory.restore(copy.deepcopy(record),self.model)
        self.assertEqual(record,restored.snapshot())
        if not session.done:
            f=session.frame()
            self.assertEqual(nav.features(f),restored.features(f))
            outcome=session.step(1, expected_tick=f["tick"])
            nav.feedback(1,outcome)
            restored.feedback(1,outcome)
            self.assertEqual(nav.snapshot(),restored.snapshot())

    def test_corrupt_memory_rejected_even_when_digest_recomputed(self):
        nav=PortableOffsetMemory(self.model)
        s=EnvironmentSession("occluded",2749,"test",99211)
        nav.features(s.frame())
        nav.feedback(1,s.step(1,expected_tick=0))
        snapshot=nav.snapshot()
        modified=copy.deepcopy(snapshot)
        modified["data"]["remaining"]=[8,8]
        modified["digest"]=digest(modified["data"])
        with self.assertRaises(ValueError):PortableOffsetMemory.restore(modified,self.model)
        changed=copy.deepcopy(snapshot)
        changed["data"]["events"][0]=[0,"move"]
        changed["digest"]=digest(changed["data"])
        with self.assertRaises(ValueError):PortableOffsetMemory.restore(changed,self.model)

    def test_wrong_model_rejected_and_malformed_sensor_rejected(self):
        nav=PortableOffsetMemory(self.model)
        session=EnvironmentSession("occluded",2749,"test",99211)
        nav.features(session.frame())
        with self.assertRaises(ValueError):
            PortableOffsetMemory.restore(nav.snapshot(),train_grid_updates(6607,episodes=24))
        with self.assertRaises(ValueError):nav.feedback(True,{"frame":session.frame(),"reward":0.0,"event":"move"})

    def test_reactive_ablation_forgets_cue_after_first_action(self):
        nav=PortableOffsetMemory(self.model, retain=False)
        session=EnvironmentSession("occluded",2749,"test",99211)
        self.assertNotEqual(nav.features(session.frame())[:2],(0,0))
        nav.feedback(0,session.step(0,expected_tick=0))
        self.assertEqual(nav.features(session.frame())[:2],(0,0))

    def test_evaluation_is_reproducible_and_disjoint_from_training(self):
        data=measure(seeds=(2749,),train_q=50,train_memory=24,episodes=8,start_index=81000)
        self.assertEqual(data,measure(seeds=(2749,),train_q=50,train_memory=24,episodes=8,start_index=81000))
        self.assertEqual({r["mode"] for r in data["rows"]},{"learned","engineered","forget","random"})
        self.assertFalse(data["blind"])

    def test_bad_mode_and_parameter_types_rejected(self):
        with self.assertRaises(ValueError):train_grid_updates(2749,0)
        with self.assertRaises(ValueError):self.model.update(True,"move")
        with self.assertRaises(ValueError):self.model.update(0,"secret_event")
        with self.assertRaises(ValueError):LearnedOffsetUpdater.restore({"data":self.model.record()["data"],"digest":"bad"})
        with self.assertRaises(ValueError):measure(seeds=(2749,2749))

if __name__=="__main__":unittest.main()
