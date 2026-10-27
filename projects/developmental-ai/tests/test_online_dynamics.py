"""Small deterministic regression suite for unlabeled latent-state model learning."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.adaptive_dynamics import DynamicsModel
from developmental_ai.online_dynamics import (
    ModelBank, fit, forward_backward, initial_model, score, trajectory,
    validate_history,
)


class OnlineDynamicsTests(unittest.TestCase):
    def histories(self,seed=17,noise="standard",layout="fixed",count=65):
        return [trajectory(seed,"train",i,noise,layout,steps=10) for i in range(count)]

    def test_only_visible_observation_fields_exported(self):
        h=trajectory(17,"train",0,"high","shifted")
        self.assertEqual(set(h),{"n","initial","observations"})
        self.assertTrue(all(len(x)==3 for x in h["observations"]))
        self.assertTrue(all(x[0] in (-1,1) for x in h["observations"]))
        self.assertEqual(h,trajectory(17,"train",0,"high","shifted"))
        self.assertNotEqual(h,trajectory(17,"test",0,"high","shifted"))

    def test_invalid_and_privileged_records_rejected(self):
        good=trajectory(17,"train",0)
        bad=dict(good, actual_position=3)
        with self.assertRaises(ValueError):validate_history(bad)
        for malformed in (((True,0,None),), ((-1,0,False),), ((1,2,None),), ()):
            with self.assertRaises(ValueError):validate_history(dict(good,observations=malformed))
        for n,initial in ((True,0),(9,True),(8,0),(9,9)):
            with self.assertRaises(ValueError):validate_history(dict(good,n=n,initial=initial))

    def test_model_improves_observation_likelihood(self):
        examples=self.histories(count=110)
        before=score(initial_model(),examples)
        learned,curve=fit(examples,iterations=5)
        self.assertLess(before,score(learned,examples))
        self.assertEqual(len(curve),5)
        self.assertGreater(curve[-1],curve[0])
        self.assertAlmostEqual(sum(learned.motion_probs(1)),1)
        self.assertTrue(isinstance(forward_backward(learned,examples[0]),float))

    def test_exact_continuation_via_serialized_checkpoint(self):
        data=self.histories(count=45)
        full,_=fit(data,iterations=6)
        half,_=fit(data,iterations=3)
        with tempfile.TemporaryDirectory() as folder:
            with ModelBank(Path(folder)/"p.db",17) as bank:
                bank.save("partial",half,len(data))
            with ModelBank(Path(folder)/"p.db",17) as bank:
                rest,_=fit(data,iterations=3,start=bank.get("partial"))
                self.assertEqual(full.counts,rest.counts)

    def test_model_bank_selection_without_regime_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"p.db"
            with ModelBank(db,17) as bank:
                normal,_=fit(self.histories(count=125),iterations=6)
                shifted,_=fit(self.histories(noise="high",layout="shifted",count=125),iterations=6)
                bank.save("normal",normal,125)
                bank.save("shifted",shifted,125)
                tests=[trajectory(17,"test",i,"standard","fixed") for i in range(35)]
                before=db.read_bytes()
                selected=bank.select(tests)
                self.assertEqual(selected["selected"],"normal")
                self.assertEqual(db.read_bytes(),before)
                with self.assertRaises(sqlite3.IntegrityError):bank.save("normal",normal,125)

    def test_tampering_schema_digest_and_seed_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"p.db"
            with ModelBank(db,17) as bank:
                bank.save("original",initial_model(),1)
                for name in ("", "../secrets", "x"*41):
                    with self.assertRaises(ValueError):bank.get(name)
            with ModelBank(db,19) as bank:
                with self.assertRaises(ValueError):bank.get("original")
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE online_models SET counts = '{}' WHERE name = 'original'")
            with ModelBank(db,17) as bank:
                with self.assertRaises(ValueError):bank.get("original")

    def test_model_rows_and_zero_length_rejected(self):
        with self.assertRaises(ValueError):fit([])
        with self.assertRaises(ValueError):score(DynamicsModel(),[])
        with self.assertRaises(ValueError):fit(self.histories(count=1),iterations=0)


if __name__=="__main__":
    unittest.main()
