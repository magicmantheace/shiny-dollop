"""Bounded unannounced-reversal memory protocol: strict API, replay, controls."""
import copy
import unittest
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.environment_api import digest
from developmental_ai.repeated_reversal import RepeatedReversalMemory, MODES, BOOTSTRAP, MAX_EVENTS, _logscore,values
from benchmarks.event_segmentation_benchmark import episode
from benchmarks.repeated_reversal_benchmark import measure,PHASES

class RepeatedReversalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=fit_event_model([episode(14003,'source_bursts','train',i)['observed'] for i in range(12)])
        cls.stream=episode(14003,'source_bursts','train',300)['observed']

    def learner(self,steps=16,mode='archive_recall'):
        m=RepeatedReversalMemory(self.model,14003,mode=mode)
        for i in range(steps):
            m.propose(i%2,self.stream,split='train',index=i)
            m.feedback(i%3==0,split='train',index=i)
        return m

    def test_deterministic_restore(self):
        m=self.learner()
        self.assertEqual(m.record(),RepeatedReversalMemory.restore(m.record(),self.model).record())

    def test_all_baseline_modes_and_read_only_choice(self):
        for mode in MODES:
            m=self.learner(BOOTSTRAP,mode)
            before=m.record()
            choice=m.choose(0,self.stream)
            self.assertIn(choice['selection']['center'],range(len(self.stream)))
            self.assertEqual(before,m.record())

    def test_no_phase_label_and_no_reward_before_action(self):
        m=RepeatedReversalMemory(self.model,14003)
        with self.assertRaises(TypeError):m.propose(0,self.stream,split='train',index=0,phase='B')
        with self.assertRaises(ValueError):m.feedback(True,split='train',index=0)
        with self.assertRaises(ValueError):m.choose(0,self.stream)

    def test_invalid_train_order_and_reward(self):
        m=RepeatedReversalMemory(self.model,14003)
        with self.assertRaises(ValueError):m.propose(0,self.stream,split='test',index=0)
        with self.assertRaises(ValueError):m.propose(0,self.stream,split='train',index=1)
        m.propose(0,self.stream,split='train',index=0)
        with self.assertRaises(ValueError):m.propose(0,self.stream,split='train',index=0)
        for bad in (1,0,None,'true'):
            with self.assertRaises(ValueError):m.feedback(bad,split='train',index=0)
        m.feedback(False,split='train',index=0)

    def test_checksum_altered_replay_rejected(self):
        m=self.learner()
        for case in ('hash','reward','source','choice','length'):
            wrong=copy.deepcopy(m.record())
            if case=='hash':wrong['sha256']='bad'
            if case=='reward':wrong['state']['history'][0]['success']=not wrong['state']['history'][0]['success']
            if case=='source':wrong['state']['history'][0]['source']='wrong'
            if case=='choice':wrong['state']['history'][0]['selected']['center']+=2
            if case=='length':wrong['state']['history'][0]['tokens'].append(True)
            if case!='hash':wrong['sha256']=digest(wrong['state'])
            if case in ('reward',):
                # A fully consistent alternate history may be replayable.
                # Authentication is outside this research interface.
                continue
            with self.assertRaises(ValueError):RepeatedReversalMemory.restore(wrong,self.model)

    def test_wrong_model_and_extra_truth_rejected(self):
        m=self.learner()
        other=fit_event_model([episode(14009,'source_bursts','train',i)['observed'] for i in range(12)])
        with self.assertRaises(ValueError):RepeatedReversalMemory.restore(m.record(),other)
        with self.assertRaises(ValueError):m.propose(0,{'raw':self.stream,'true_label':2},split='train',index=len(m.history))

    def test_archive_contrast_behavior_and_limits(self):
        history=[{'context':0,'selected':{'label':0},'success':i%2==0} for i in range(16)]
        self.assertEqual(values(history,0)[0],.5)
        self.assertEqual(_logscore(history,history),16*__import__('math').log(.5))
        self.assertEqual(MAX_EVENTS,680)
        self.assertEqual(PHASES,('A','B','A','B','A','A_control'))

    def test_archive_source_can_reidentify_old_pattern_without_phase_input(self):
        learner=RepeatedReversalMemory(self.model,14003)
        base={'context':0,'selected':{'label':0}}
        anchor=[{**base,'success':True} for _ in range(BOOTSTRAP)]
        reversed_recent=[{**base,'success':False} for _ in range(32)]
        returned=[{**base,'success':True} for _ in range(16)]
        learner.history=anchor+reversed_recent+returned
        self.assertEqual(learner._source(),'anchor')
        learner.history=anchor+reversed_recent+reversed_recent[:16]
        self.assertEqual(learner._source(),'recent')

    def test_model_mutation_blocks_live_actions(self):
        learner=self.learner(BOOTSTRAP)
        learner.model.training[0][0]=(learner.model.training[0][0]+1)%4
        with self.assertRaises(ValueError):learner.choose(0,self.stream)
        with self.assertRaises(ValueError):learner.record()

    def test_replay_after_bootstrap_with_same_model(self):
        learner=self.learner(BOOTSTRAP+42)
        recovered=RepeatedReversalMemory.restore(learner.record(),self.model)
        self.assertEqual(learner.choose(1,self.stream),recovered.choose(1,self.stream))
        self.assertEqual(learner.record(),recovered.record())

    def test_eval_rejects_partial_cohorts(self):
        for group in ([14003], [14003,27007], []):
            with self.assertRaises(ValueError):measure(group)

if __name__=='__main__':unittest.main()
