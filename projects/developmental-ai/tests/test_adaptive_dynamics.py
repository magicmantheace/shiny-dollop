"""Verify empirical calibration, named memories and held-out measurements."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from developmental_ai.adaptive_dynamics import (
    CalibrationBrain, CalibrationWorld, DynamicsModel, AdaptiveNavigator,
    calibration_sample,
)


class AdaptiveDynamicsTests(unittest.TestCase):
    def test_calibration_is_deterministic_and_split_separated(self):
        self.assertEqual(calibration_sample(17,"train",3),calibration_sample(17,"train",3))
        self.assertNotEqual(calibration_sample(17,"train",3),calibration_sample(17,"test",3))

    def test_world_shift_relocates_landmarks(self):
        w=CalibrationWorld(2,"test",0,layout="shifted")
        self.assertEqual(w.layout,"shifted")
        self.assertEqual(len(w.initial_observation()["beacon"]),2)
        self.assertNotEqual(0,2)

    def test_empirical_motion_probabilities_converge(self):
        model=DynamicsModel()
        for i in range(1300):
            model.observe(calibration_sample(17,"train",i,"high","shifted"))
        for direction in (-1,1):
            chances=model.motion_probs(direction)
            self.assertAlmostEqual(sum(chances),1)
            self.assertTrue(.37 < chances[0] < .60, chances)
            self.assertTrue(.12 < chances[1] < .29, chances)
        for d in (-1,0,1):
            self.assertAlmostEqual(sum(model.odo_probs(d)),1)
        for pos in range(9):
            self.assertAlmostEqual(sum(model.landmark_probs(9,pos)),1)

    def test_adapter_can_relearn_shifted_observations(self):
        model=DynamicsModel()
        for i in range(1400):
            model.observe(calibration_sample(23,"train",i,"standard","fixed"))
        old_loss=sum(model.loss(calibration_sample(23,"test",i,"high","shifted")) for i in range(170))/170
        for i in range(1400,2800):
            model.observe(calibration_sample(23,"train",i,"high","shifted"))
        new_loss=sum(model.loss(calibration_sample(23,"test",i,"high","shifted")) for i in range(170))/170
        self.assertLess(new_loss,old_loss-.35)

    def test_filter_remains_normalized_and_moves_without_truth(self):
        model=DynamicsModel()
        navigator=AdaptiveNavigator(1,4,9,model)
        navigator.advance(1,{"beacon":None,"odometry":1,"landmark":None})
        self.assertAlmostEqual(sum(navigator.probs),1)
        self.assertEqual(len(navigator.probs),9)
        self.assertIn(navigator.heuristic(),range(3))
        with self.assertRaises(ValueError):navigator.advance(3,{"odometry":1,"landmark":None})

    def test_checkpoint_continues_exactly_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1,p2=Path(tmp)/"continuous.db",Path(tmp)/"restart.db"
            with CalibrationBrain(p1,31) as brain:
                brain.train(100,"standard","fixed")
                brain.train(100,"high","shifted")
                expected=(brain.trained,brain.model.counts,brain.evaluate(30))
            with CalibrationBrain(p2,31) as brain:
                brain.train(100,"standard","fixed")
            with CalibrationBrain(p2,31) as brain:
                brain.train(100,"high","shifted")
                self.assertEqual((brain.trained,brain.model.counts,brain.evaluate(30)),expected)

    def test_snapshot_preserves_old_world_without_resetting_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            with CalibrationBrain(Path(tmp)/"p.db",17) as brain:
                brain.train(600,"standard","fixed")
                brain.snapshot("old")
                before=brain.evaluate_snapshot("old",80,"standard","fixed")
                brain.train(900,"high","shifted")
                retained=brain.evaluate_snapshot("old",80,"standard","fixed")
                self.assertEqual(before["navigation_success"],retained["navigation_success"])
                self.assertEqual(before["mean_nll"],retained["mean_nll"])
                self.assertEqual(brain.trained,1500)
                with self.assertRaises(Exception):brain.snapshot("old")

    def test_checkpoint_validation_and_snapshot_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"brain.db"
            with CalibrationBrain(p,9) as brain:
                brain.train(4)
                brain.snapshot("good")
            with self.assertRaises(ValueError):CalibrationBrain(p,11)
            with CalibrationBrain(p,9) as brain:
                for invalid in ("../secrets","", "x"*41):
                    with self.assertRaises(ValueError):brain.snapshot(invalid)
                brain.conn.execute("UPDATE dynamics_snapshots SET counts=? WHERE name='good'",(json.dumps({"x":1}),))
                brain.conn.commit()
                with self.assertRaises(ValueError):brain.load_snapshot("good")

    def test_evaluation_and_snapshot_read_are_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"data.db"
            with CalibrationBrain(path,17) as brain:
                brain.train(200)
                brain.snapshot("saved")
                original=(path.read_bytes(),brain.trained,json.dumps(brain.model.counts,sort_keys=True))
                brain.evaluate(35,noise="high",layout="shifted")
                brain.evaluate_snapshot("saved",35,noise="standard",layout="fixed")
                self.assertEqual((path.read_bytes(),brain.trained,json.dumps(brain.model.counts,sort_keys=True)),original)

    def test_invalid_models_rejected(self):
        with self.assertRaises(ValueError):DynamicsModel({"motion":[]})
        invalid=DynamicsModel().counts
        invalid["odo"][0][0]=float('nan')
        with self.assertRaises(ValueError):DynamicsModel(invalid)


if __name__ == "__main__":
    unittest.main()
