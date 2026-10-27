"""Transfer frozen policy weights across changed observation visibility."""
import random
import tempfile
import unittest
from pathlib import Path
from developmental_ai.cross_family_transfer import SpatialEncoder,trial
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.transfer import TransferBrain
from benchmarks.zero_shot_navigation_transfer_benchmark import measure


class CrossFamilyTransferTests(unittest.TestCase):
    def test_public_adapter_updates_memory_from_movement_feedback_only(self):
        s=EnvironmentSession("occluded",2749,"test",70000)
        e=SpatialEncoder("occluded")
        old=e.features(s.frame())
        action=next((i for i in range(4) if not old[2]&(1<<i)),None)
        self.assertIsNotNone(action)
        result=s.step(action,expected_tick=0)
        e.feedback(action,result)
        self.assertEqual(e.features(s.frame())[:2],
            (max(-3,min(3,e._remaining[0])),max(-3,min(3,e._remaining[1]))))
        bad=s.frame();bad["observation"]["position"]=1
        with self.assertRaises(ValueError):e.features(bad)

    def test_no_repeat_beacon_and_invalid_family(self):
        with self.assertRaises(ValueError):SpatialEncoder("delayed")
        e=SpatialEncoder("occluded")
        s=EnvironmentSession("occluded",17,"train",0)
        frame=s.frame()
        e.features(frame)
        with self.assertRaises(ValueError):e.features(frame)

    def test_frozen_trained_brain_never_changes_when_evaluating_occluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=TransferBrain(Path(tmp)/"q.db",seed=17)
            try:
                b.train(80)
                original=dict(b.q)
                x=trial(b,family="occluded",seed=17,split="test",index=70010,policy="trained_grid")
                self.assertTrue(x["steps"]>0)
                self.assertEqual(b.q,original)
                self.assertEqual(b.trained,80)
            finally:b.close()

    def test_pilot_is_reproducible(self):
        a=measure(seeds=[17],train=30,test=4)
        b=measure(seeds=[17],train=30,test=4)
        self.assertEqual(a,b)
        self.assertEqual(len(a["rows"]),6)

if __name__=="__main__":unittest.main()
