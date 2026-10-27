"""Regression for per-step latent inference and human-reviewed candidate models."""
from __future__ import annotations
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from developmental_ai.online_dynamics import ModelBank, fit, trajectory, forward_backward
from developmental_ai.step_dynamics import StepDetector, CandidateStore, catalogue, _observation


class StepDynamicsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.seed = 17
        self.bank_path = self.root/'bank.db'
        self.state_path = self.root/'step.db'
        self.review_path = self.root/'candidate.db'
        with ModelBank(self.bank_path,self.seed) as bank:
            for name,noise,layout in [('original','standard','fixed'),('changed','high','shifted')]:
                model,_ = fit([trajectory(self.seed,'train',i,noise,layout) for i in range(50)],iterations=4)
                bank.save(name,model,50)

    def histories(self,count=1,noise='standard',layout='fixed', offset=5000):
        return [trajectory(self.seed,'test',offset+i,noise,layout) for i in range(count)]

    def feed(self,monitor,h):
        events=[monitor.begin(h['n'],h['initial'])]
        events.extend(monitor.step(*o) for o in h['observations'])
        events.append(monitor.finish())
        return events

    def test_per_step_forward_scores_match_full_marginal_likelihood(self):
        history=self.histories()[0]
        with ModelBank(self.bank_path,self.seed) as bank:
            for name in ('original','changed'):
                model=bank.get(name)
                alpha=[float(i==history['initial']) for i in range(history['n'])]
                ll=0.0
                for obs in history['observations']:
                    part,alpha=_observation(model,history['n'],alpha,*obs)
                    ll+=part
                self.assertAlmostEqual(ll,forward_backward(model,history),places=10)

    def test_each_step_is_event_and_restart_identical(self):
        h=self.histories()[0]
        with ModelBank(self.bank_path,self.seed) as bank, StepDetector(self.state_path,bank) as monitor:
            first=[monitor.begin(h['n'],h['initial'])]
            first += [monitor.step(*obs) for obs in h['observations'][:6]]
            checkpoint=copy.deepcopy(monitor.state)
        with ModelBank(self.bank_path,self.seed) as bank, StepDetector(self.state_path,bank) as monitor:
            self.assertEqual(checkpoint,monitor.state)
            second=[monitor.step(*obs) for obs in h['observations'][6:]]
            second.append(monitor.finish())
            self.assertEqual(monitor.events(),first+second)
        with ModelBank(self.bank_path,self.seed) as bank, StepDetector(self.root/'unbroken.db',bank) as clean:
            self.assertEqual(self.feed(clean,h),first+second)

    def test_atomic_invalid_step_and_strict_limits(self):
        h=self.histories()[0]
        with ModelBank(self.bank_path,self.seed) as bank, StepDetector(self.state_path,bank) as monitor:
            monitor.begin(h['n'],h['initial'])
            original=copy.deepcopy(monitor.state)
            for bad in [(0,0,0),(1,'bad',0),(1,0,99)]:
                with self.assertRaises(ValueError):monitor.step(*bad)
            self.assertEqual(original,monitor.state)
            with self.assertRaises(ValueError):monitor.begin(h['n'],h['initial'])
            for record in h['observations']:
                monitor.step(*record)
            monitor.finish()
            with self.assertRaises(ValueError):monitor.step(*h['observations'][0])

    def test_detect_switches_inside_episode_without_labels(self):
        with ModelBank(self.bank_path,self.seed) as bank, StepDetector(self.state_path,bank,window=6,confirmations=2) as monitor:
            batches=[]
            for noise,layout,offset in [('standard','fixed',5000),('high','shifted',6000)]:
                events=[]
                for h in self.histories(12,noise,layout,offset):
                    events.extend(self.feed(monitor,h))
                batches.append(events)
            self.assertTrue(any(e.get('kind')=='observation' and e.get('status')=='switch' for e in batches[0]))
            self.assertTrue(any(e.get('kind')=='observation' and e.get('status')=='switch' for e in batches[1]))
            self.assertNotIn('actual_regime',json.dumps(monitor.events()))

    def test_bank_and_checkpoint_tamper_rejected(self):
        with ModelBank(self.bank_path,self.seed) as bank, StepDetector(self.state_path,bank) as monitor:
            self.feed(monitor,self.histories()[0])
        with sqlite3.connect(self.state_path) as conn:
            conn.execute("UPDATE step_events SET body='{}' WHERE seq=2")
        with ModelBank(self.bank_path,self.seed) as bank:
            with self.assertRaises(ValueError):StepDetector(self.state_path,bank)
        with sqlite3.connect(self.state_path) as conn:
            conn.execute('DELETE FROM step_state')
            conn.execute('DELETE FROM step_events')
        with ModelBank(self.bank_path,self.seed) as bank, StepDetector(self.state_path,bank) as monitor:
            monitor.begin(9,0)
        with ModelBank(self.bank_path,self.seed) as bank:
            bank.save('extra',bank.get('original'),1)
            with self.assertRaises(ValueError):StepDetector(self.state_path,bank)

    def test_novel_history_staged_only_when_confirmed(self):
        h=self.histories(1,'high','fixed')[0]
        with ModelBank(self.bank_path,self.seed) as bank:
            _,fingerprint=catalogue(bank)
            with CandidateStore(self.review_path,self.seed,fingerprint) as stage:
                with StepDetector(self.state_path,bank,floor=-0.01,confirmations=2) as monitor:
                    monitor.begin(h['n'],h['initial'])
                    statuses=[monitor.step(*obs)['status'] for obs in h['observations']]
                    self.assertIn('unknown',statuses)
                    self.assertTrue(monitor.finish(stage)['staged'])
                    self.assertEqual(len(stage.histories()),1)
                    self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],2)

    def test_candidate_requires_evidence_and_explicit_digest_approval(self):
        with ModelBank(self.bank_path,self.seed) as bank:
            _,fingerprint=catalogue(bank)
            with CandidateStore(self.review_path,self.seed,fingerprint) as stage:
                for h in self.histories(13,'high','fixed',7000):
                    stage.add(h,catalogue=fingerprint)
                stage.add(self.histories(1,'high','fixed',7000)[0],catalogue=fingerprint)
                self.assertEqual(len(stage.histories()),13)
                review=stage.propose(min_histories=12,iterations=4)
                self.assertEqual(review['status'],'awaiting-human-review')
                self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],2)
                with self.assertRaises(ValueError):stage.promote(bank,'reviewed')
                with self.assertRaises(ValueError):stage.promote(bank,'reviewed',approval_digest='wrong')
                self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],2)
                with self.assertRaises(ValueError):stage.propose()
                with self.assertRaises(ValueError):stage.add(self.histories(1,'high','fixed',9000)[0],catalogue=fingerprint)
        with ModelBank(self.bank_path,self.seed) as bank, CandidateStore(self.review_path,self.seed,fingerprint) as stage:
            # Model checksum alone no longer authorizes installation. A separate
            # review over non-overlapping observations is now mandatory.
            with self.assertRaises(ValueError):
                stage.promote(bank,'reviewed',approval_digest=review['model_digest'])
            ticket=stage.review(bank,self.histories(30,'high','fixed',11000),min_holdout=24)
            self.assertEqual(ticket,stage.get_review(bank))
            if ticket['passed']:
                with self.assertRaises(PermissionError):
                    stage.promote(bank,'reviewed',approval_digest=review['model_digest'])
                result=stage.promote(bank,'reviewed',approval_digest=ticket['review_digest'])
                self.assertEqual(result,review['model_digest'])
            else:
                with self.assertRaises(PermissionError):
                    stage.promote(bank,'reviewed',approval_digest=ticket['review_digest'])
                self.assertEqual(bank.conn.execute('SELECT COUNT(*) FROM online_models').fetchone()[0],2)

    def test_cannot_stage_privileged_truth_or_mutate_candidate(self):
        with ModelBank(self.bank_path,self.seed) as bank:
            _,fingerprint=catalogue(bank)
            with CandidateStore(self.review_path,self.seed,fingerprint) as stage:
                record=self.histories()[0]
                record['hidden_position']=3
                with self.assertRaises(ValueError):stage.add(record,catalogue=fingerprint)
                del record['hidden_position']
                stage.add(record,catalogue=fingerprint)
            with sqlite3.connect(self.review_path) as conn:
                conn.execute("UPDATE candidate_history SET body='{}'")
            with self.assertRaises(ValueError):CandidateStore(self.review_path,self.seed,fingerprint)

    def test_wrong_bank_rejected_and_failed_review_non_mutating(self):
        with ModelBank(self.bank_path,self.seed) as bank:
            _,fingerprint=catalogue(bank)
            with CandidateStore(self.review_path,self.seed,fingerprint) as stage:
                with self.assertRaises(ValueError):stage.add(self.histories()[0],catalogue='wrong')
                with self.assertRaises(ValueError):stage.propose(min_histories=4)
                self.assertEqual(stage.histories(),[])
            with self.assertRaises(ValueError):CandidateStore(self.review_path,23,fingerprint)


if __name__=='__main__':
    unittest.main()
