"""Observation-only map-alternative novelty tests and restart protection."""
import copy
import unittest
from developmental_ai.structured_landmarks import StructuredModel
from developmental_ai.online_dynamics import trajectory
from developmental_ai.layout_novelty import (LayoutGuard, CalibratedLayoutGuard,
                                              calibrate_layouts, verify_layouts)
from developmental_ai.switching_belief import _digest


def sensor_stream(seed,index,split='train'):
    h=trajectory(seed,split,index)
    return {'initial':h['initial'],'goal':0,'n':h['n'],
            'observations':[[0 if a==-1 else 1,{'beacon':None,'odometry':b,'landmark':c}]
                            for a,b,c in h['observations']]}


class LayoutNoveltyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models={'saved':StructuredModel()}
        cls.refs=[sensor_stream(17,47000+i) for i in range(45)]
        cls.receipt=calibrate_layouts(cls.models,cls.refs)

    def test_train_only_compatible_receipt(self):
        r=verify_layouts(self.receipt,self.models)
        self.assertEqual(r['reference_size'],45)
        self.assertGreaterEqual(r['threshold'],0)

    def test_alternative_offsets_without_hidden_world_state(self):
        guard=LayoutGuard(0,1,9,self.models)
        self.assertEqual(len(guard.alternatives),8)
        self.assertEqual(set(guard.snapshot()['state']['start']),{0,1,9})
        self.assertNotIn('position', guard.snapshot()['state'])

    def test_refuses_privileged_observations_without_mutation(self):
        g=CalibratedLayoutGuard(0,3,9,self.models,self.receipt)
        start=g.snapshot()
        with self.assertRaises(ValueError):g.advance(0,{'beacon':None,'odometry':0,'landmark':1,'truth_position':3})
        with self.assertRaises(ValueError):g.advance(True,{'beacon':None,'odometry':0,'landmark':1})
        self.assertEqual(g.snapshot(),start)

    def test_duplicate_or_privileged_training_evidence_refused(self):
        with self.assertRaises(ValueError):calibrate_layouts(self.models,[self.refs[0]]*45)
        bad=copy.deepcopy(self.refs)
        bad[1]['true_regime']='shifted'
        with self.assertRaises(ValueError):calibrate_layouts(self.models,bad)

    def test_restart_exact_and_replay_checked(self):
        stream=sensor_stream(17,33000,'test')
        g=CalibratedLayoutGuard(stream['initial'],stream['goal'],stream['n'],self.models,self.receipt)
        for act,obs in stream['observations'][:6]:g.advance(act,obs)
        recovered=CalibratedLayoutGuard.restore(g.snapshot(),self.models,self.receipt)
        self.assertEqual(g.snapshot(),recovered.snapshot())
        for act,obs in stream['observations'][6:]:
            self.assertEqual(g.advance(act,obs),recovered.advance(act,obs))
        self.assertEqual(g.snapshot(),recovered.snapshot())

    def test_replay_detects_recomputed_hash_forgery(self):
        g=CalibratedLayoutGuard(0,3,9,self.models,self.receipt)
        g.advance(0,{'beacon':None,'odometry':-1,'landmark':None})
        forged=g.snapshot()
        forged['state']['max_gain']=80.
        forged['sha256']=_digest(forged['state'])
        with self.assertRaises(ValueError):CalibratedLayoutGuard.restore(forged,self.models,self.receipt)

    def test_reject_model_or_receipt_mutation(self):
        changed=copy.deepcopy(self.models)
        changed['saved'].motion[0][0]+=1
        with self.assertRaises(ValueError):verify_layouts(self.receipt,changed)
        changed_receipt=copy.deepcopy(self.receipt)
        changed_receipt['state']['threshold']=999
        with self.assertRaises(ValueError):verify_layouts(changed_receipt,self.models)

    def test_counterfactual_scores_known_rotated_site(self):
        def simulate_offset(origin):
            g=LayoutGuard(0,1,9,self.models)
            pos=0
            for _ in range(36):
                pos=(pos+1)%9
                marker=0 if pos==origin else 1 if pos==(origin+4)%9 else None
                g.advance(1,{'beacon':None,'odometry':1,'landmark':marker})
            return g.max_gain
        self.assertGreater(simulate_offset(3),simulate_offset(0)+2)

    def test_stricter_train_rank_not_more_permissive(self):
        strict=calibrate_layouts(self.models,self.refs,alpha=.04)
        self.assertGreaterEqual(strict['state']['threshold'],self.receipt['state']['threshold'])
        self.assertNotEqual(strict['sha256'],self.receipt['sha256'])

    def test_budget_validation_and_no_baseline_change(self):
        from developmental_ai.switching_belief import SwitchingBelief
        h=sensor_stream(17,33000,'test')
        g=LayoutGuard(h['initial'],h['goal'],h['n'],self.models)
        b=SwitchingBelief(h['initial'],h['goal'],h['n'],self.models)
        for act,obs in h['observations']:
            g.advance(act,obs)
            b.advance(act,obs)
        self.assertAlmostEqual(g.base.log_evidence,b.log_evidence,places=9)
        self.assertGreaterEqual(g.max_gain,0)

if __name__=='__main__':unittest.main()
