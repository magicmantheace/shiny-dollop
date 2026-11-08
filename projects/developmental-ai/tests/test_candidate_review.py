"""Independent predictive review for quarantined models, never auto-promote."""
from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.step_dynamics import CandidateStore, catalogue


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=self.root/'bank.db'
        self.stage_path=self.root/'stage.db'
        self.seed=17
        # Only a shifted/high-noise model is known: candidate has useful new
        # standard/fixed experience and should beat this specific reference.
        with ModelBank(self.db,self.seed) as bank:
            model,_=fit([trajectory(self.seed,'train',i,'high','shifted')
                         for i in range(70)],iterations=5)
            bank.save('shifted',model,70)
            self.fingerprint=catalogue(bank)[1]
        with CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            for i in range(75):
                stage.add(trajectory(self.seed,'train',2000+i,'standard','fixed'),
                          catalogue=self.fingerprint)
            self.ticket=stage.propose(iterations=5)

    def holdout(self,count=32,offset=5000):
        return [trajectory(self.seed,'train',offset+i,'standard','fixed') for i in range(count)]

    def test_approval_only_after_passed_review_and_exact_digest(self):
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            with self.assertRaises(ValueError):
                stage.promote(bank,'candidate',approval_digest=self.ticket['model_digest'])
            ticket=stage.review(bank,self.holdout(),min_gain=.02)
            self.assertTrue(ticket['passed'],ticket)
            self.assertGreater(ticket['gain'],.02)
            self.assertEqual(ticket,stage.get_review(bank))
            with self.assertRaises(PermissionError):
                stage.promote(bank,'candidate',approval_digest=self.ticket['model_digest'])
            with self.assertRaises(PermissionError):
                stage.promote(bank,'candidate',approval_digest='0'*64)
            self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],1)
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            self.assertEqual(stage.get_review(bank),ticket)
            self.assertEqual(stage.promote(bank,'candidate',approval_digest=ticket['review_digest']),
                             self.ticket['model_digest'])
            self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],2)

    def test_training_overlap_duplicates_and_privileged_truth_rejected(self):
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            with self.assertRaises(ValueError):
                stage.review(bank,[trajectory(self.seed,'train',2000+i,'standard','fixed')
                                   for i in range(30)])
            duplicate=self.holdout()
            duplicate[2]=copy.deepcopy(duplicate[0])
            with self.assertRaises(ValueError):stage.review(bank,duplicate)
            bad=self.holdout()
            bad[0]['hidden_position']=5
            with self.assertRaises(ValueError):stage.review(bank,bad)
            self.assertEqual(stage._holdout(),[])
            self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],1)

    def test_rejected_review_blocks_even_digest_matched_approval(self):
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            ticket=stage.review(bank,self.holdout(),min_gain=1.0)
            self.assertFalse(ticket['passed'])
            with self.assertRaises(PermissionError):
                stage.promote(bank,'never',approval_digest=ticket['review_digest'])
            with self.assertRaises(ValueError):stage.review(bank,self.holdout())
            self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],1)

    def test_review_and_evidence_tampering_fail_closed_on_restart(self):
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            stage.review(bank,self.holdout())
        with sqlite3.connect(self.stage_path) as con:
            con.execute("UPDATE candidate_holdout SET body='{}' WHERE hash=(SELECT MIN(hash) FROM candidate_holdout)")
        with self.assertRaises(ValueError):
            CandidateStore(self.stage_path,self.seed,self.fingerprint)

    def test_tampered_report_and_bank_mismatch_fail_closed(self):
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            stage.review(bank,self.holdout())
        with sqlite3.connect(self.stage_path) as con:
            con.execute("UPDATE candidate_review SET body='{}'")
        with self.assertRaises(ValueError):CandidateStore(self.stage_path,self.seed,self.fingerprint)

    def test_model_bank_change_invalidates_review(self):
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            report=stage.review(bank,self.holdout())
            bank.save('other',bank.get('shifted'),1)
            with self.assertRaises(ValueError):stage.get_review(bank)
            with self.assertRaises(ValueError):
                stage.promote(bank,'candidate',approval_digest=report['review_digest'])

    def test_review_requires_enough_fresh_observations(self):
        with ModelBank(self.db,self.seed) as bank, CandidateStore(self.stage_path,self.seed,self.fingerprint) as stage:
            with self.assertRaises(ValueError):stage.review(bank,self.holdout(11))
            with self.assertRaises(ValueError):stage.review(bank,self.holdout(),min_gain=float('nan'))
            with self.assertRaises(ValueError):stage.review(bank,self.holdout(),min_holdout=501)

if __name__=='__main__':
    unittest.main()
