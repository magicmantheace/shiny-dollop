"""Dynamic cue-reliability: no truth to learner, strict frames, exact replay."""
import copy
import unittest
from developmental_ai.dynamic_reliability import DynamicReliability, validate, START
from developmental_ai.environment_api import digest
from benchmarks.dynamic_reliability_benchmark import stream, measure, DEV, RESERVED


class DynamicReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.probes,self.cues,self.truth=stream(43103,'train',START,[2,-1])

    def learner(self, basis='evidence', n=20):
        model=DynamicReliability(43103,basis=basis)
        for i in range(n):
            p,c,_=stream(43103,'train',START+i,[2,-1])
            model.propose(p,c,split='train',index=START+i)
            model.feedback(i%3==0,split='train',index=START+i)
        return model

    def test_input_rejects_truth_and_invalid_probes(self):
        for bad in ([True]*8, [0]*7, ['0']*8):
            with self.assertRaises(ValueError):validate(bad,self.cues)
        bad=copy.deepcopy(self.cues);bad[0].append({'true_source':self.truth})
        with self.assertRaises(ValueError):validate(self.probes,bad)
        bad=copy.deepcopy(self.cues);bad[0][0]=bad[1][0]
        with self.assertRaises(ValueError):validate(self.probes,bad)
        bad=copy.deepcopy(self.cues);bad[0][1]=[True,0]
        with self.assertRaises(ValueError):validate(self.probes,bad)

    def test_per_episode_source_changes(self):
        truths=[]
        for i in range(20):
            p,c,src=stream(43103,'train',START+i,[2,-1]);truths.append(src)
            self.assertEqual(sum(row[0]==src and row[1]==[2,-1] for row in c),1)
            self.assertEqual(len(validate(p,c)),5)
        self.assertGreater(len(set(truths)),3)

    def test_train_requires_monotonic_index(self):
        m=DynamicReliability(43103)
        with self.assertRaises(ValueError):m.propose(self.probes,self.cues,split='test',index=START)
        with self.assertRaises(ValueError):m.propose(self.probes,self.cues,split='train',index=START+1)
        m.propose(self.probes,self.cues,split='train',index=START)
        with self.assertRaises(ValueError):m.propose(self.probes,self.cues,split='train',index=START)
        with self.assertRaises(ValueError):m.record()
        with self.assertRaises(ValueError):m.source(self.probes,self.cues)
        with self.assertRaises(ValueError):m.feedback(True,split='test',index=START)
        for invalid in (1, None, [], 0.0):
            with self.assertRaises(ValueError):m.feedback(invalid,split='train',index=START)
        m.feedback(False,split='train',index=START)

    def test_reward_only_replay_exact_and_predict_identical(self):
        for basis in ('evidence','identity'):
            m=self.learner(basis)
            restored=DynamicReliability.restore(m.record())
            self.assertEqual(restored.record(),m.record())
            self.assertEqual(restored.predict(self.probes,self.cues),m.predict(self.probes,self.cues))

    def test_modified_decision_detected_even_if_digest_reforged(self):
        bad=copy.deepcopy(self.learner().record())
        bad['state']['events'][0]['chosen']='src_99'
        bad['digest']=digest(bad['state'])
        with self.assertRaises(ValueError):DynamicReliability.restore(bad)

    def test_modified_features_detected_even_if_digest_reforged(self):
        bad=copy.deepcopy(self.learner().record())
        selected=bad['state']['events'][0]['chosen']
        current=bad['state']['events'][0]['feature'][selected]
        bad['state']['events'][0]['feature'][selected]=8 if current < 6 else 0
        bad['digest']=digest(bad['state'])
        with self.assertRaises(ValueError):DynamicReliability.restore(bad)

    def test_modified_stats_detected_even_if_digest_reforged(self):
        bad=copy.deepcopy(self.learner().record())
        key=next(iter(bad['state']['stats']))
        bad['state']['stats'][key][0]+=1
        bad['digest']=digest(bad['state'])
        with self.assertRaises(ValueError):DynamicReliability.restore(bad)

    def test_no_test_reward_updates(self):
        m=self.learner()
        before=m.record()
        with self.assertRaises(ValueError):m.feedback(True,split='test',index=99000)
        self.assertEqual(before,m.record())

    def test_invalid_model_and_source(self):
        with self.assertRaises(ValueError):DynamicReliability(43103,basis='oracle')
        with self.assertRaises(ValueError):DynamicReliability(True)
        bad=copy.deepcopy(self.cues);bad[0][0]='secret'
        with self.assertRaises(ValueError):self.learner().predict(self.probes,bad)

    def test_frozen_cohorts_reject_parameter_tuning(self):
        with self.assertRaises(ValueError):measure([43103])
        with self.assertRaises(ValueError):measure([43103,50021,99999])

    def test_replay_rejects_non_canonical_record(self):
        obj=self.learner();record=copy.deepcopy(obj.record());record['state']['events'].append(record['state']['events'][-1]);record['digest']=digest(record['state'])
        with self.assertRaises(ValueError):DynamicReliability.restore(record)


if __name__=='__main__':unittest.main()
