"""Reward-only raw sequence relation learning and frozen evaluation controls."""
import copy
import unittest

from developmental_ai.environment_api import digest
from developmental_ai.raw_token_transfer import RewardTokenAligner, START, validate
from benchmarks.raw_token_transfer_benchmark import stream, cipher, measure, DEV, ADDITIONAL


class RawTokenTests(unittest.TestCase):
    def setUp(self):
        self.observed,self.candidates,_=stream(43103,'train',START,[2,-1])

    def learner(self, n=24):
        model=RewardTokenAligner(43103)
        for i in range(n):
            obs,cues,_=stream(43103,'train',START+i,[2,-1])
            model.propose(obs,cues,split='train',index=START+i)
            model.feedback(i % 5 == 0,split='train',index=START+i)
        return model

    def test_disjoint_vocab_no_supplied_agreement_score(self):
        self.assertTrue(all(x.startswith('sensor-') for x in self.observed))
        self.assertTrue(all(x.startswith('forecast-') for c in self.candidates for x in c[2]))
        self.assertFalse(set(self.observed).intersection({x for c in self.candidates for x in c[2]}))
        self.assertEqual(len(validate(self.observed,self.candidates)),5)

    def test_hidden_permutation_changes_by_seed(self):
        self.assertNotEqual(cipher(43103),cipher(50021))
        self.assertEqual(cipher(43103),cipher(43103))

    def test_rejects_oracle_fields_and_invalid_symbols(self):
        for change in (lambda o,c:o.append('sensor-0'),
                       lambda o,c:c[0].append({'true_source':'src_0'}),
                       lambda o,c:c[0][2].__setitem__(0,'sensor-0'),
                       lambda o,c:c[0].__setitem__(0,'src_99'),
                       lambda o,c:c[1].__setitem__(0,c[0][0]),
                       lambda o,c:c[0][1].__setitem__(0,True)):
            o,c=copy.deepcopy(self.observed),copy.deepcopy(self.candidates)
            change(o,c)
            with self.assertRaises(ValueError): validate(o,c)

    def test_monotonic_train_and_terminal_bool_only(self):
        m=RewardTokenAligner(43103)
        with self.assertRaises(ValueError):m.propose(self.observed,self.candidates,split='test',index=START)
        with self.assertRaises(ValueError):m.propose(self.observed,self.candidates,split='train',index=START+1)
        m.propose(self.observed,self.candidates,split='train',index=START)
        with self.assertRaises(ValueError):m.propose(self.observed,self.candidates,split='train',index=START)
        with self.assertRaises(ValueError):m.record()
        for invalid in (1,0.5,'success',[True],None):
            with self.assertRaises(ValueError):m.feedback(invalid,split='train',index=START)
        m.feedback(True,split='train',index=START)
        with self.assertRaises(ValueError):m.feedback(True,split='test',index=99200)
        self.assertEqual(len(m.events),1)

    def test_exact_restart_and_reproducible_policy(self):
        old=self.learner();other=self.learner()
        self.assertEqual(old.record(),other.record())
        recovered=RewardTokenAligner.restore(old.record())
        self.assertEqual(recovered.record(),old.record())
        self.assertEqual(recovered.predict(self.observed,self.candidates),old.predict(self.observed,self.candidates))

    def test_forged_choice_and_counts_fail_even_rehashed(self):
        original=self.learner().record()
        for tamper in ('choice','successes','forecast','index'):
            record=copy.deepcopy(original)
            if tamper=='choice':record['state']['events'][0]['chosen']='src_99'
            if tamper=='successes':record['state']['successes'][0]+=3
            if tamper=='forecast':record['state']['events'][0]['forecast'][0]='forecast-9'
            if tamper=='index':record['state']['events'][0]['index']+=1
            record['digest']=digest(record['state'])
            with self.assertRaises(ValueError):RewardTokenAligner.restore(record)

    def test_different_evaluation_alphabet_fails_closed(self):
        m=self.learner()
        bad=copy.deepcopy(self.candidates)
        bad[0][2][0]='unknown-foreign-alphabet'
        before=m.record()
        with self.assertRaises(ValueError):m.source(self.observed,bad)
        self.assertEqual(before,m.record())

    def test_fixed_cohorts_and_no_test_tuning(self):
        with self.assertRaises(ValueError):measure([43103])
        with self.assertRaises(ValueError):measure([43103,50021,11111])
        with self.assertRaises(ValueError):measure(list(DEV)+[72019])
        self.assertNotEqual(DEV,ADDITIONAL)


if __name__=='__main__':unittest.main()
