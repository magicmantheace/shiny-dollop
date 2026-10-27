"""Bounded unaligned raw-token learning and checkpoint evidence tests."""
import copy
import unittest
from developmental_ai.environment_api import digest
from developmental_ai.unaligned_stream import (UnalignedRewardLearner, TRAIN_START, validate,
                                                 near_pairs, alignment_score)
from benchmarks.unaligned_stream_benchmark import stream, DEV, ADDITIONAL, measure

class UnalignedStreamTests(unittest.TestCase):
    def setUp(self):
        self.obs,self.cues,_=stream(43103,'train',TRAIN_START,[2,-1])

    def learner(self,episodes=18):
        m=UnalignedRewardLearner(43103)
        for i in range(episodes):
            obs,cues,_=stream(43103,'train',TRAIN_START+i,[2,-1])
            m.propose(obs,cues,split='train',index=TRAIN_START+i)
            m.feedback(i%3==0,split='train',index=TRAIN_START+i)
        return m

    def test_insertions_are_unaligned_and_not_marked(self):
        self.assertEqual(len(self.cues),5)
        self.assertNotEqual(len(self.obs),8)
        self.assertTrue(any(len(c[2])!=len(self.obs) for c in self.cues))
        self.assertEqual(len(validate(self.obs,self.cues)),5)

    def test_rejects_hidden_truth_and_extra_keys(self):
        for change in (lambda o,c:c[0].append({'truth':True}),
                       lambda o,c:o.append('sensor-9'),
                       lambda o,c:c[0][2].append('invalid'),
                       lambda o,c:c[0][1].__setitem__(0,True),
                       lambda o,c:c[0].__setitem__(0,c[1][0])):
            obs,cues=copy.deepcopy(self.obs),copy.deepcopy(self.cues)
            change(obs,cues)
            with self.assertRaises(ValueError):validate(obs,cues)

    def test_bounded_train_only_bool_feedback(self):
        m=UnalignedRewardLearner(43103)
        with self.assertRaises(ValueError):m.propose(self.obs,self.cues,split='test',index=TRAIN_START)
        with self.assertRaises(ValueError):m.propose(self.obs,self.cues,split='train',index=TRAIN_START+1)
        m.propose(self.obs,self.cues,split='train',index=TRAIN_START)
        with self.assertRaises(ValueError):m.record()
        for reward in (0,1,'correct',[True],None):
            with self.assertRaises(ValueError):m.feedback(reward,split='train',index=TRAIN_START)
        m.feedback(True,split='train',index=TRAIN_START)
        with self.assertRaises(ValueError):m.feedback(True,split='test',index=TRAIN_START)

    def test_exact_restore_matches_predictions(self):
        m=self.learner();r=m.record();other=UnalignedRewardLearner.restore(copy.deepcopy(r))
        self.assertEqual(r,other.record())
        self.assertEqual(m.predict(self.obs,self.cues),other.predict(self.obs,self.cues))

    def test_recomputed_hash_does_not_allow_impossible_selection(self):
        original=self.learner().record()
        for mutation in ('source','count','index','symbol'):
            r=copy.deepcopy(original)
            if mutation=='source':r['state']['history'][0]['chosen']='src_99'
            if mutation=='count':r['state']['positive'][0]+=3
            if mutation=='index':r['state']['history'][0]['index']+=1
            if mutation=='symbol':r['state']['history'][0]['forecast'][0]='forecast-99'
            r['digest']=digest(r['state'])
            with self.assertRaises(ValueError):UnalignedRewardLearner.restore(r)

    def test_monotone_dp_differs_from_unordered_bag(self):
        x=['sensor-0','sensor-1']*5
        y=['forecast-0','forecast-1']*5
        z=['forecast-1','forecast-0']*5
        weights=[1. if i==j else -1. for i in range(4) for j in range(4)]
        self.assertGreater(alignment_score(x,y,weights),alignment_score(x,z,weights))
        self.assertEqual(sum(weights[a*4+b] for a in range(2) for b in range(2)),0)

    def test_window_pairs_do_not_require_matching_indices(self):
        self.assertGreater(len(list(near_pairs(self.obs,self.cues[0][2]))),8)
        self.assertEqual(len(set(k for k,_ in near_pairs(self.obs,self.cues[0][2])))<=16,True)

    def test_frozen_cohorts_validation(self):
        with self.assertRaises(ValueError):measure([43103])
        with self.assertRaises(ValueError):measure(list(DEV)+[72019])
        self.assertNotEqual(DEV,ADDITIONAL)

if __name__=='__main__':unittest.main()
