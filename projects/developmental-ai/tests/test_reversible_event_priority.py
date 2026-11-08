"""Event priority reversal: replay, observational boundaries and comparators."""
import copy
import unittest

from developmental_ai.environment_api import digest
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.reversible_event_priority import ReversibleEventPriority, MODES
from benchmarks.event_segmentation_benchmark import episode
from benchmarks.reversible_event_priority_benchmark import measure, phase_goals


class ReversiblePriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=14003
        cls.streams=[episode(cls.seed,'source_bursts','train',i)['observed'] for i in range(6)]
        cls.segmenter=fit_event_model(cls.streams)

    def sample(self,i):
        return episode(self.seed,'source_bursts','train',2000+i)['observed']

    def fitted(self,mode='bank',n=24):
        model=ReversibleEventPriority(self.segmenter,seed=self.seed,mode=mode)
        for i in range(n):
            choice=model.propose(i%2,self.sample(i),split='train',index=2000+i)
            model.feedback(choice['label']==(i%2),split='train',index=2000+i)
        return model

    def test_valid_modes_training_and_no_privileged_fields(self):
        for mode in MODES:self.assertEqual(self.fitted(mode=mode,n=8).mode,mode)
        learner=ReversibleEventPriority(self.segmenter,seed=self.seed)
        with self.assertRaises(TypeError):learner.propose(0,self.sample(0),split='train',index=2000,hidden_target=2)
        picked=learner.propose(0,self.sample(0),split='train',index=2000)
        self.assertEqual(set(picked),{'start','end','label','center'})
        self.assertNotIn('target',str(learner.pending))

    def test_fail_closed_for_train_and_feedback(self):
        learner=ReversibleEventPriority(self.segmenter,seed=self.seed)
        with self.assertRaises(ValueError):learner.propose(0,self.sample(0),split='test',index=2000)
        learner.propose(0,self.sample(0),split='train',index=2000)
        with self.assertRaises(ValueError):learner.record()
        with self.assertRaises(ValueError):learner.propose(1,self.sample(1),split='train',index=2001)
        for bad in (0,1,'yes',None,0.0):
            with self.assertRaises(ValueError):learner.feedback(bad,split='train',index=2000)
        learner.feedback(True,split='train',index=2000)
        with self.assertRaises(ValueError):learner.feedback(False,split='train',index=2000)
        with self.assertRaises(ValueError):learner.propose(0,self.sample(0),split='train',index=2000)

    def test_model_checkpoint_deterministic_replay(self):
        m=self.fitted(n=33)
        r=m.record()
        restored=ReversibleEventPriority.restore(copy.deepcopy(r),self.segmenter)
        self.assertEqual(r,restored.record())
        self.assertEqual(m.choose(0,self.sample(0)),restored.choose(0,self.sample(0)))
        for x in (m,restored):
            ix=2380
            decision=x.propose(1,self.sample(2),split='train',index=ix)
            x.feedback(decision['label']==2,split='train',index=ix)
        self.assertEqual(m.record(),restored.record())

    def test_impossible_choice_rejected_when_rehashed(self):
        r=self.fitted().record()
        for fault in ('wrong_action','counter','wrong_reward_type','index','bank','switch'):
            saved=copy.deepcopy(r);s=saved['state']
            if fault=='wrong_action':s['events'][0]['chosen']['center']+=1
            if fault=='counter':s['banks']['0'][0][0][0]+=3
            if fault=='wrong_reward_type':s['events'][0]['success']=1
            if fault=='index':s['events'][1]['index']=2000
            if fault=='bank':s['active']['0']=2
            if fault=='switch':s['switches'].append([22,0,0,1,'secret'])
            saved['sha256']=digest(s)
            with self.assertRaises(ValueError,msg=fault):ReversibleEventPriority.restore(saved,self.segmenter)

    def test_mutated_segmenter_and_wrong_binding(self):
        m=self.fitted();record=m.record()
        other=fit_event_model(self.streams[:4])
        with self.assertRaises(ValueError):ReversibleEventPriority.restore(record,other)
        m.model.sensor_accuracy=.7
        with self.assertRaises(ValueError):m.choose(1,self.sample(1))
        with self.assertRaises(ValueError):m.record()

    def test_rejects_unknown_context_and_privileged_tokens(self):
        m=self.fitted()
        for ctx in (True,2,-1,'0',None):
            with self.assertRaises(ValueError):m.choose(ctx,self.sample(0))
        for seq in ([True,0],[0,8],[0]*129,[]):
            with self.assertRaises(ValueError):m.choose(0,seq)

    def test_frozen_baseline_only_uses_first_200(self):
        m=self.fitted(mode='frozen',n=24)
        self.assertEqual(len(m.events),24)
        self.assertEqual(m.record()['state']['mode'],'frozen')

    def test_private_goal_switch_is_benchmark_only(self):
        source={0:0,1:2}
        self.assertEqual(phase_goals(source,'original'),source)
        self.assertEqual(phase_goals(source,'return'),source)
        self.assertEqual(phase_goals(source,'reversal'),{0:1,1:3})
        with self.assertRaises(ValueError):phase_goals(source,'unknown')

    def test_frozen_cohorts(self):
        for val in ([14003],[14003,14009,14033,27007],[],[1,2,3]):
            with self.assertRaises(ValueError):measure(val)

    def test_bank_archive_persists_without_disclosing_reward_map(self):
        m=self.fitted(n=24)
        rec=m.record()
        self.assertIn('banks',rec['state'])
        self.assertNotIn('hidden',str(rec))
        self.assertNotIn('preference',str(rec))
        self.assertNotIn('reward_rule',str(rec))

if __name__=='__main__':unittest.main()
