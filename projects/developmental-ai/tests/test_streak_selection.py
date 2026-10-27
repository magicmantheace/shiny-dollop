"""Research selector: calibration provenance, ordering, persistence and fail-closed behavior."""
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from developmental_ai.decision_abstention import train_gate
from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.step_dynamics import StepDetector
from developmental_ai.streak_selection import (StreakSelector, train_profile, verify_profile,
                                                load_profile, SCHEMA)
from benchmarks.abstention_benchmark import stream, REGIMES


class StreakSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name)
        cls.seed = 17
        with ModelBank(cls.path / "bank.db", cls.seed) as bank:
            for name, condition in REGIMES.items():
                histories = [trajectory(cls.seed, "train", i, *condition) for i in range(38)]
                model, _ = fit(histories, iterations=3)
                bank.save(name, model, len(histories))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def calibration(self, bank):
        with StepDetector(self.path / ("cal-"+self.id().replace(".","-")+".db"), bank) as detector:
            return [(ev, truth) for truth, ev in stream(detector, self.seed, split="train", index_base=5000, count=6)]

    def test_profile_roundtrip_and_model_bank_binding(self):
        with ModelBank(self.path / "bank.db", self.seed) as bank:
            profile = train_profile(bank, self.calibration(bank), min_accepted=4)
            self.assertEqual(verify_profile(bank, load_profile(json.dumps(profile.as_dict()))), profile)
            with self.assertRaises(ValueError):
                verify_profile(bank, dataclasses.replace(profile, threshold=0.0))
            with self.assertRaises(ValueError):
                train_profile(bank, [], max_empirical_error=.02)
            with self.assertRaises(ValueError):
                train_profile(bank, self.calibration(bank), min_streak=1)

    def test_restart_is_selection_exact(self):
        with ModelBank(self.path / "bank.db", self.seed) as bank:
            profile = train_profile(bank, self.calibration(bank), min_accepted=4)
            with StepDetector(self.path / ("eval-"+self.id().replace(".","-")+".db"), bank) as detector:
                events = [ev for _, ev in stream(detector,self.seed,split="test",index_base=6000,count=3)]
            one = StreakSelector(bank,profile)
            original = [one.observe(event) for event in events]
            before = StreakSelector(bank,profile)
            first = [before.observe(event) for event in events[:19]]
            recovered = StreakSelector(bank,profile,checkpoint=json.loads(json.dumps(before.checkpoint())))
            rest = [recovered.observe(event) for event in events[19:]]
            self.assertEqual(original,first+rest)
            self.assertEqual(one.checkpoint(),recovered.checkpoint())

    def test_replay_and_checkpoint_tampering_rejected(self):
        with ModelBank(self.path / "bank.db", self.seed) as bank:
            profile = train_profile(bank, self.calibration(bank), min_accepted=4)
            with StepDetector(self.path / ("eval-"+self.id().replace(".","-")+".db"), bank) as detector:
                events = [ev for _,ev in stream(detector,self.seed,split="test",index_base=6100,count=1)]
            selector=StreakSelector(bank,profile)
            selector.observe(events[0])
            state=selector.checkpoint()
            with self.assertRaises(ValueError): selector.observe(events[0])
            with self.assertRaises(ValueError): selector.observe(events[2])
            self.assertEqual(selector.checkpoint(),state)
            changed=json.loads(json.dumps(state));changed["state"]["lead"]="unknown"
            with self.assertRaises(ValueError): StreakSelector(bank,profile,changed)
            with self.assertRaises(ValueError): StreakSelector(bank,dataclasses.replace(profile,min_streak=5),state)

    def test_nonfinite_evidence_and_unknown_status_fail_closed(self):
        with ModelBank(self.path / "bank.db", self.seed) as bank:
            profile=train_profile(bank,self.calibration(bank),min_accepted=4)
            selector=StreakSelector(bank,profile)
            event={"kind":"observation","episode":1,"step":1,"seq":2,
                   "scores":{"changed":-1.0,"original":-2.0},"active":None,"status":"warming"}
            self.assertIsNone(selector.observe(event))
            bad={**event,"step":2,"seq":3,"scores":{"changed":float('nan'),"original":-2.0}}
            with self.assertRaises(ValueError): selector.observe(bad)
            self.assertEqual(selector.state["step"],1)
            unknown={**event,"step":2,"seq":3,"status":"unknown"}
            self.assertIsNone(selector.observe(unknown))

    def test_too_strict_calibration_abstains(self):
        with ModelBank(self.path / "bank.db", self.seed) as bank:
            profile=train_profile(bank,self.calibration(bank),min_accepted=10000)
            self.assertEqual(profile.threshold,1e6)
            selector=StreakSelector(bank,profile)
            with StepDetector(self.path / ("eval-"+self.id().replace(".","-")+".db"), bank) as detector:
                events=[ev for _,ev in stream(detector,self.seed,split="test",index_base=6200,count=2)]
            self.assertTrue(all(selector.observe(ev) is None for ev in events))

    def test_monotonic_stream_cannot_skip_new_episode(self):
        with ModelBank(self.path / "bank.db",self.seed) as bank:
            profile=train_profile(bank,self.calibration(bank),min_accepted=4)
            selector=StreakSelector(bank,profile)
            with StepDetector(self.path / ("eval-"+self.id().replace(".","-")+".db"),bank) as detector:
                events=[ev for _,ev in stream(detector,self.seed,split="test",index_base=6300,count=2)]
            self.assertIsNone(selector.observe(events[0]))
            with self.assertRaises(ValueError):selector.observe(events[24])

    def test_three_consecutive_leaders_needed_and_current_active_not_required(self):
        # This opt-in policy is deliberately distinct from the conservative gate.
        # It reads the observation score leader, never a ground-truth regime.
        with ModelBank(self.path / "bank.db",self.seed) as bank:
            profile=train_profile(bank,self.calibration(bank),min_accepted=4)
            selector=StreakSelector(bank,profile)
            for i in range(1,4):
                event={"kind":"observation","episode":1,"step":i,"seq":i+1,
                       "scores":{"changed":-1.0,"original":-100.0},
                       "active":"original","status":"pending"}
                selected=selector.observe(event)
                self.assertEqual(selected,"changed" if i==3 else None)
            # Unknown status cannot produce a decision, even with a large gap.
            event={"kind":"observation","episode":1,"step":4,"seq":5,
                   "scores":{"changed":-1.0,"original":-100.0},
                   "active":"original","status":"unknown"}
            self.assertIsNone(selector.observe(event))


if __name__=="__main__": unittest.main()
