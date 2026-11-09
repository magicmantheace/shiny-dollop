"""Regression tests for fail-closed selective step decisions."""
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from developmental_ai.decision_abstention import decide, train_gate, load_gate, verify_gate
from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.step_dynamics import StepDetector


class AbstentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed = 17
        self.bank_path = self.root / "bank.db"
        with ModelBank(self.bank_path, self.seed) as bank:
            for name, regime in [("normal", ("standard", "fixed")), ("changed", ("high", "shifted"))]:
                model, _ = fit([trajectory(self.seed, "train", i, *regime) for i in range(35)], iterations=3)
                bank.save(name, model, 35)

    def events(self):
        out = []
        with ModelBank(self.bank_path, self.seed) as bank, StepDetector(self.root/"monitor.db", bank, margin=0.03) as det:
            for regime, params, start in [("normal", ("standard", "fixed"), 5100),
                                          ("changed", ("high", "shifted"), 5200)]:
                for i in range(5):
                    h=trajectory(self.seed,"train",start+i,*params)
                    det.begin(h["n"],h["initial"])
                    for step in h["observations"]:
                        out.append((det.step(*step),regime))
                    det.finish()
        return out

    def test_disagreement_and_nonfinite_fail_closed(self):
        names = {"a": None, "b": None}
        event = {"kind":"observation", "active":"a", "scores":{"a":-2.0,"b":-1.0},"status":"stable"}
        self.assertIsNone(decide(event,names,gap=0))
        event["scores"] = {"a":-1.0,"b":-2.0}
        self.assertEqual(decide(event,names,gap=.5),"a")
        self.assertIsNone(decide(event,names,gap=1.01))
        event["status"]="unknown"
        self.assertIsNone(decide(event,names,gap=0))
        event["scores"]["a"] = float("nan")
        with self.assertRaises(ValueError):decide(event,names,gap=0)

    def test_train_bind_and_tamper_detected(self):
        events=self.events()
        with ModelBank(self.bank_path,self.seed) as bank:
            profile=train_gate(bank,events,max_empirical_error=.35,min_accepted=12)
            self.assertEqual(verify_gate(bank,profile),profile.gap)
            self.assertEqual(verify_gate(bank,load_gate(json.dumps(profile.as_dict()))),profile.gap)
            with self.assertRaises(ValueError):verify_gate(bank,dataclasses.replace(profile,gap=0.00001))
            with self.assertRaises(ValueError):train_gate(bank,events[:20])
            with self.assertRaises(ValueError):train_gate(bank,events+[({},"normal")])
            bank.save("extra",bank.get("normal"),1)
            with self.assertRaises(ValueError):verify_gate(bank,profile)

    def test_incompatible_profile_never_accepted(self):
        with ModelBank(self.bank_path,self.seed) as bank:
            with self.assertRaises(ValueError):load_gate('{"schema":"oops"}')
            with self.assertRaises(ValueError):train_gate(bank,[],max_empirical_error=1)

if __name__=="__main__":unittest.main()
