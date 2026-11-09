"""Reward-only event selection, model binding, and exact restart evidence."""
import copy
import unittest

from developmental_ai.environment_api import digest
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.outcome_event_memory import OutcomeEventMemory, FocusedEventSession, TRAIN_START
from benchmarks.event_segmentation_benchmark import episode
from benchmarks.outcome_event_memory_benchmark import (context,preference,score,measure,TEST_START)


class OutcomeEventMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=14003
        cls.streams=[episode(cls.seed,'source_bursts','train',i)['observed'] for i in range(12)]
        cls.model=fit_event_model(cls.streams)

    def fitted(self, count=12, mode='hmm'):
        memory=OutcomeEventMemory(self.model, seed=self.seed,mode=mode)
        for j in range(count):
            ix=TRAIN_START+j
            sample=episode(self.seed,'source_bursts','train',ix)
            ctx=context(self.seed,'train',ix)
            choice=memory.propose(ctx,sample['observed'],split='train',index=ix)
            memory.feedback(score(choice,sample,preference(self.seed)[ctx]),split='train',index=ix)
        return memory

    def test_reward_only_model_no_hidden_fields(self):
        sample=episode(self.seed,'source_bursts','train',TRAIN_START)
        m=OutcomeEventMemory(self.model,seed=self.seed)
        with self.assertRaises(TypeError):m.propose(0,sample['observed'],split='train',index=TRAIN_START,hidden=sample['hidden'])
        action=m.propose(0,sample['observed'],split='train',index=TRAIN_START)
        self.assertEqual(set(action),{'start','end','label','center'})
        self.assertEqual(action['center'],(action['start']+action['end']-1)//2)
        self.assertNotIn('hidden',str(m.pending))

    def test_training_sequential_one_reward_only(self):
        m=OutcomeEventMemory(self.model,seed=self.seed)
        s=self.streams[0]
        with self.assertRaises(ValueError):m.propose(0,s,split='test',index=TRAIN_START)
        with self.assertRaises(ValueError):m.propose(0,s,split='train',index=TRAIN_START+1)
        m.propose(0,s,split='train',index=TRAIN_START)
        with self.assertRaises(ValueError):m.record()
        for reward in (1,0,'true',None,0.0):
            with self.assertRaises(ValueError):m.feedback(reward,split='train',index=TRAIN_START)
        with self.assertRaises(ValueError):m.feedback(True,split='test',index=TRAIN_START)
        m.feedback(True,split='train',index=TRAIN_START)
        with self.assertRaises(ValueError):m.feedback(True,split='train',index=TRAIN_START)

    def test_input_bounds(self):
        m=self.fitted()
        for context_bad in (-1,2,True,'0',None):
            with self.assertRaises(ValueError):m.choose(context_bad,self.streams[0])
        for seq in ([0,1,True],[9,0],[0]*129,[],['0',1]):
            with self.assertRaises(ValueError):m.choose(0,seq)
        with self.assertRaises(ValueError):OutcomeEventMemory(self.model,seed=4,mode='oracle')


    def test_model_snapshot_exact_restore(self):
        trained=self.fitted()
        record=trained.record()
        resumed=OutcomeEventMemory.restore(copy.deepcopy(record),self.model)
        self.assertEqual(record,resumed.record())
        self.assertEqual(trained.choose(0,self.streams[0]),resumed.choose(0,self.streams[0]))
        self.assertEqual(record,self.fitted().record())

    def test_rehashed_reward_or_count_mutations_rejected(self):
        record=self.fitted().record()
        for fault in ('decision','reward','count','index','label'):
            modified=copy.deepcopy(record)
            e=modified['state']['events'][0]
            if fault=='decision':e['selected']['center']+=1
            elif fault=='reward':e['success']=not e['success']
            elif fault=='count':modified['state']['counts']['0|0'][0]+=1
            elif fault=='index':e['index']+=1
            else:e['selected']['label']=(e['selected']['label']+1)%4
            modified['sha256']=digest(modified['state'])
            with self.assertRaises(ValueError,msg=fault):OutcomeEventMemory.restore(modified,self.model)

    def test_wrong_fitted_segmenter_and_mutation_rejected(self):
        trained=self.fitted()
        other=fit_event_model(self.streams[:6])
        with self.assertRaises(ValueError):OutcomeEventMemory.restore(trained.record(),other)
        trained.model.persistence=.5
        with self.assertRaises(ValueError):trained.choose(0,self.streams[0])

    def test_streaming_focus_exact_replay(self):
        fitted=self.fitted()
        sess=FocusedEventSession(fitted,1)
        for token in self.streams[0][:15]:sess.observe(token)
        saved=sess.snapshot()
        restored=FocusedEventSession.restore(copy.deepcopy(saved),fitted)
        self.assertEqual(saved,restored.snapshot())
        for token in self.streams[0][15:]:
            self.assertEqual(sess.observe(token),restored.observe(token))
        self.assertEqual(sess.snapshot(),restored.snapshot())

    def test_streaming_focus_forged_priority_rejected(self):
        fitted=self.fitted()
        sess=FocusedEventSession(fitted,0)
        for token in self.streams[0][:10]:sess.observe(token)
        altered=copy.deepcopy(sess.snapshot())
        altered['state']['selected']['label']=(altered['state']['selected']['label']+1)%4
        altered['sha256']=digest(altered['state'])
        with self.assertRaises(ValueError):FocusedEventSession.restore(altered,fitted)

    def test_bound_on_observation_and_model_record(self):
        fitted=self.fitted()
        focus=FocusedEventSession(fitted,0)
        with self.assertRaises(ValueError):focus.observe(True)
        with self.assertRaises(ValueError):focus.observe(4)
        with self.assertRaises(ValueError):FocusedEventSession.restore({'state':{}},fitted)

    def test_raw_run_control_uses_same_reward_api(self):
        m=self.fitted(mode='raw')
        self.assertEqual(m.record()['state']['mode'],'raw')
        self.assertEqual(m.record(),OutcomeEventMemory.restore(m.record(),self.model).record())
        selected=m.choose(0,self.streams[0])
        self.assertEqual(self.streams[0][selected['center']],selected['label'])

    def test_context_goal_hidden_from_public_training_record(self):
        m=self.fitted()
        record=m.record()
        self.assertNotIn('target',str(record))
        self.assertNotIn('oracle',str(record))
        self.assertEqual(set(record['state']['counts']),{f'{a}|{b}' for a in range(2) for b in range(4)})

    def test_frozen_cohort_enforced(self):
        with self.assertRaises(ValueError):measure([14003])
        with self.assertRaises(ValueError):measure([14003,14009,14033,27007])
        self.assertGreater(TEST_START,TRAIN_START+200)

if __name__=='__main__':unittest.main()
