"""Observation-only channel novelty tests; no simulator truth accepted."""
import copy
import unittest

from developmental_ai.channel_novelty import (
    ChannelGuard, LayeredGuard, _profile, calibrate_channels, verify_channels,
)
from developmental_ai.novelty_guard import calibrate_guard
from developmental_ai.online_dynamics import trajectory
from developmental_ai.structured_landmarks import StructuredModel
from developmental_ai.switching_belief import _digest


def make(seed,index,split='train'):
    h=trajectory(seed,split,index)
    return {'initial':h['initial'],'goal':0,'n':h['n'],
            'observations':[[0 if cmd==-1 else 1,{'beacon':None,'odometry':odo,'landmark':m}]
                            for cmd,odo,m in h['observations']]}


class ChannelGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models={'m':StructuredModel()}
        cls.refs=[make(17,45000+i) for i in range(50)]
        cls.profile=calibrate_channels(cls.models,cls.refs)
        cls.base=calibrate_guard(cls.models,cls.refs)

    def test_ordinary_data_and_receipt(self):
        rec=verify_channels(self.profile,self.models)
        self.assertGreaterEqual(rec['cutoffs']['zero_odometry'],5)
        self.assertGreaterEqual(rec['cutoffs']['constant_landmark'],4)
        self.assertEqual(rec['reference_size'],50)

    def test_reject_duplicate_and_privileged_reference(self):
        with self.assertRaises(ValueError):calibrate_channels(self.models,[self.refs[0]]*50)
        z=copy.deepcopy(self.refs);z[0]['position']=0
        with self.assertRaises(ValueError):calibrate_channels(self.models,z)

    def test_one_sided_run_threshold_and_no_actions_without_sensors(self):
        g=ChannelGuard(self.models,self.profile)
        ob={'beacon':None,'odometry':0,'landmark':None}
        limit=self.profile['state']['cutoffs']['zero_odometry']
        for i in range(limit):
            self.assertFalse(g.advance(0,ob)['alarm'])
        self.assertEqual(g.advance(0,ob)['channels'],['zero_odometry'])
        self.assertTrue(g.alarm)

    def test_landmark_stick_and_ignores_collect(self):
        g=ChannelGuard(self.models,self.profile)
        ob={'beacon':None,'odometry':-1,'landmark':1}
        for _ in range(self.profile['state']['cutoffs']['constant_landmark']+1):
            g.advance(0,ob)
        self.assertIn('constant_landmark',g.alarms)
        c=ChannelGuard(self.models,self.profile)
        for _ in range(30):c.advance(2,{'beacon':None,'odometry':0,'landmark':1})
        self.assertFalse(c.alarm)

    def test_exact_restart_and_identity_binding(self):
        h=make(17,90010,'test')
        g=ChannelGuard(self.models,self.profile)
        for a,ob in h['observations'][:6]:g.advance(a,ob)
        b=ChannelGuard.restore(g.snapshot(),self.models,self.profile)
        for a,ob in h['observations'][6:]:
            self.assertEqual(g.advance(a,ob),b.advance(a,ob))
        self.assertEqual(g.snapshot(),b.snapshot())
        changed=copy.deepcopy(self.models);changed['m'].motion[0][0]+=2
        with self.assertRaises(ValueError):ChannelGuard.restore(g.snapshot(),changed,self.profile)

    def test_forgery_cannot_change_alarm_with_recomputed_digest(self):
        g=ChannelGuard(self.models,self.profile)
        g.advance(0,{'beacon':None,'odometry':0,'landmark':None})
        snap=g.snapshot()
        snap['state']['alarms']=['zero_odometry'];snap['sha256']=_digest(snap['state'])
        with self.assertRaises(ValueError):ChannelGuard.restore(snap,self.models,self.profile)

    def test_bad_sensor_does_not_mutate(self):
        g=ChannelGuard(self.models,self.profile)
        original=g.snapshot()
        with self.assertRaises(ValueError):g.advance(0,{'beacon':None,'odometry':0,'landmark':0,'truth_position':0})
        with self.assertRaises(ValueError):g.advance(True,{'beacon':None,'odometry':0,'landmark':0})
        self.assertEqual(original,g.snapshot())

    def test_combined_equal_observation_replay(self):
        h=make(17,90010,'test')
        g=LayeredGuard(h['initial'],h['goal'],h['n'],self.models,self.base,self.profile)
        for a,ob in h['observations'][:7]:g.advance(a,ob)
        r=LayeredGuard.restore(g.snapshot(),self.models,self.base,self.profile)
        self.assertEqual(g.snapshot(),r.snapshot())
        for a,ob in h['observations'][7:]:
            self.assertEqual(g.advance(a,ob),r.advance(a,ob))
        self.assertEqual(g.snapshot(),r.snapshot())

    def test_composite_rejects_diverging_histories(self):
        h=make(17,90010,'test')
        g=LayeredGuard(h['initial'],h['goal'],h['n'],self.models,self.base,self.profile)
        g.advance(*h['observations'][0]);s=g.snapshot()
        s['state']['channels']['state']['log'][0][1]['odometry']=0
        s['state']['channels']['state']['stats']['zero_count']=42
        s['state']['channels']['sha256']=_digest(s['state']['channels']['state'])
        s['sha256']=_digest(s['state'])
        with self.assertRaises(ValueError):LayeredGuard.restore(s,self.models,self.base,self.profile)

if __name__=='__main__':unittest.main()


class LayeredNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from developmental_ai.mixed_experience import fit_mixed
        from developmental_ai.closed_loop_adaptation import models_from_proposal
        from developmental_ai.switching_belief import calibrate_hazard
        cls.proposal=fit_mixed([trajectory(31,'train',i) for i in range(20)],
                               [trajectory(31,'train',10000+i) for i in range(10)],
                               seed=31,iterations=1,rounds=1,min_group=5)
        models=models_from_proposal(cls.proposal)
        refs=[make(31,45000+i) for i in range(50)]
        cls.old=calibrate_guard(models,refs)
        cls.chan=calibrate_channels(models,refs)
        cls.hazard=calibrate_hazard(models,refs[:3],candidates=(0.,.01))

    def new(self):
        from developmental_ai.channel_novelty import LayeredNavigation
        return LayeredNavigation(self.proposal,self.hazard,self.old,self.chan,0,4,9)

    def test_pause_is_not_replacement_action(self):
        s=self.new()
        a=s.select_action()
        self.assertIn(a,(0,1,2))
        s.advance(a,{'beacon':None,'odometry':0,'landmark':None})
        s.channels.alarms.append('zero_odometry')
        self.assertIsNone(s.select_action())
        with self.assertRaises(ValueError):
            s.advance(a,{'beacon':None,'odometry':0,'landmark':None})

    def test_restart_pending_and_tamper(self):
        from developmental_ai.channel_novelty import LayeredNavigation
        s=self.new(); action=s.select_action()
        rebuilt=LayeredNavigation.restore(s.snapshot(),self.proposal,self.hazard,self.old,self.chan)
        self.assertEqual(s.snapshot(),rebuilt.snapshot())
        s.advance(action,{'beacon':None,'odometry':0,'landmark':None})
        rebuilt.advance(action,{'beacon':None,'odometry':0,'landmark':None})
        self.assertEqual(s.snapshot(),rebuilt.snapshot())
        damaged=s.snapshot()
        damaged['state']['channels']['state']['alarms']=['zero_odometry']
        damaged['state']['channels']['sha256']=_digest(damaged['state']['channels']['state'])
        damaged['sha256']=_digest(damaged['state'])
        with self.assertRaises(ValueError):
            LayeredNavigation.restore(damaged,self.proposal,self.hazard,self.old,self.chan)
