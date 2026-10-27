"""Numerical reference, train/test boundary, and exact replay tests."""
import copy
import itertools
import math
import unittest

from developmental_ai.environment_api import digest,EnvironmentSession
from developmental_ai.probabilistic_alignment import marginal_score
from developmental_ai.variable_correspondence import partitions,statistics,VariableCorrespondence
from benchmarks.variable_correspondence_benchmark import stream,train_model,DEV,ADDITIONAL,measure
from developmental_ai.probabilistic_alignment import TemporalCorrespondence


class VariableCorrespondenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=43103
        cls.map=(0,1,2,3)
        cls.obs,cls.cues,cls.truth,cls.common=stream(cls.seed,'train',90000,[2,-1])
        cls.pairs=[]
        for index in range(90000,90006):
            a,b,_,_=stream(cls.seed,'train',index,[2,-1])
            cls.pairs.append([a,b[0][2]])
        cls.model=VariableCorrespondence(cls.map,cls.pairs,training_digest='a'*64)

    def test_eight_pair_matches_previous_formula(self):
        a=self.obs;b=self.cues[0][2]
        self.assertAlmostEqual(math.log(partitions(a,b,self.map,.75)[8][0]),marginal_score(a,b,self.map),places=9)

    def test_eight_event_reference_exhaustive(self):
        a=['sensor-0','sensor-1','sensor-2','sensor-3']*2+['sensor-0']
        b=['forecast-0','forecast-1','forecast-2','forecast-3']*2+['forecast-1']
        partition,expected=partitions(a,b,self.map,.75)[8]
        mass=0.;matches=0.
        for aa in itertools.combinations(range(len(a)),8):
            for bb in itertools.combinations(range(len(b)),8):
                aligned=[int(a[i].split('-')[1]==b[j].split('-')[1]) for i,j in zip(aa,bb)]
                w=math.prod(3. if agree else 1/3 for agree in aligned)
                mass+=w;matches+=w*sum(aligned)
        self.assertAlmostEqual(partition,mass/81,places=9)
        self.assertAlmostEqual(expected,matches/mass,places=9)

    def test_bounded_posterior_is_normalized(self):
        r=statistics(self.obs,self.cues[0][2],self.map,.75,.7)
        self.assertAlmostEqual(sum(r['posterior'].values()),1)
        self.assertTrue(3<=r['expected_matches']<=8)
        self.assertTrue(0<=r['expected_agreements']<=r['expected_matches'])

    def test_synthetic_deletions_vary_unknown_correspondence(self):
        values={stream(self.seed,'train',i,[0,1])[3] for i in range(90000,90020)}
        self.assertGreater(len(values),1)
        self.assertTrue(all(4<=v<=8 for v in values))

    def test_deterministic_training_and_restore(self):
        cloned=VariableCorrespondence(self.map,copy.deepcopy(self.pairs),training_digest='a'*64)
        self.assertEqual(cloned.record(),self.model.record())
        restored=VariableCorrespondence.restore(self.model.record())
        self.assertEqual(restored.record(),self.model.record())
        self.assertEqual(restored.select(self.obs,self.cues),self.model.select(self.obs,self.cues))

    def test_forged_evidence_rejected_even_rehashed(self):
        for field in ('match_probability','survival','pairs','mapping'):
            bad=copy.deepcopy(self.model.record())
            if field=='pairs':bad['state'][field][0][0][0]='sensor-1' if bad['state'][field][0][0][0]!='sensor-1' else 'sensor-2'
            elif field=='mapping':bad['state'][field]=[3,2,1,0]
            else:bad['state'][field]=.6
            bad['sha256']=digest(bad['state'])
            with self.assertRaises(ValueError):VariableCorrespondence.restore(bad)

    def test_hidden_fields_and_boolean_rejected(self):
        bad=copy.deepcopy(self.cues);bad[0].append({'actual':self.truth})
        with self.assertRaises(ValueError):self.model.select(self.obs,bad)
        bad=copy.deepcopy(self.cues);bad[0][1][0]=True
        with self.assertRaises(ValueError):self.model.select(self.obs,bad)
        bad=copy.deepcopy(self.cues);bad[0][2].append('forecast-99')
        with self.assertRaises(ValueError):self.model.select(self.obs,bad)
        with self.assertRaises(ValueError):statistics(self.obs,self.cues[0][2],self.map,.75,True)

    def test_fit_uses_only_train_and_no_answer_labels(self):
        prior=TemporalCorrespondence(self.map,evidence_digest='b'*64,episodes=240)
        fitted=train_model(self.seed,prior)
        self.assertEqual(len(fitted.pairs),120)
        self.assertEqual(fitted.record(),VariableCorrespondence.restore(fitted.record()).record())
        self.assertNotIn('correct_cue',str(fitted.record()))

    def test_cohort_cannot_be_changed_after_freeze(self):
        with self.assertRaises(ValueError):measure((43103,))
        with self.assertRaises(ValueError):measure(tuple(DEV)+tuple(ADDITIONAL))


if __name__=='__main__':unittest.main()
