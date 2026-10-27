"""Cross-family correspondence testing without privileged cue/position inputs."""
import copy
import unittest
from developmental_ai.environment_api import digest,EnvironmentSession
from developmental_ai.cross_family_temporal import CrossFamilyTemporal,validate_cues
from benchmarks.cross_family_temporal_benchmark import (
    delayed_stream,train_nav_model,_response,measure,DEV,ADDITIONAL,
    TEST_START,TRAIN_MAPPING_START,TRAIN_PARAM_START,
)


class CrossFamilyTemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.model,cls.mapping=train_nav_model(cls.seed)
        cls.cue=EnvironmentSession("delayed",cls.seed,"test",TEST_START,variant="long").frame()["observation"]["token"]
        cls.observed,cls.candidates,cls.correct,cls.common=delayed_stream(cls.seed,"test",TEST_START,cls.cue)

    def test_deterministic_unaligned_different_family(self):
        self.assertEqual((self.observed,self.candidates,self.correct,self.common),delayed_stream(self.seed,"test",TEST_START,self.cue))
        self.assertEqual(len(self.candidates),5)
        self.assertEqual(set(x[1][0] for x in self.candidates),{0,1,2,3})
        self.assertEqual(sum(x[1][0]==self.cue for x in self.candidates),1)
        self.assertTrue(all(8<=len(row[2])<=12 for row in self.candidates))
        self.assertTrue(8<=len(self.observed)<=12)
        self.assertTrue(3<=self.common<=8)

    def test_model_source_does_not_inspect_reference_cue(self):
        report=self.model.evaluate(self.observed,self.candidates)
        self.assertIn(report["cue"],range(4))
        self.assertIn(report["source"],{x[0] for x in self.candidates})
        with self.assertRaises(TypeError):self.model.evaluate(self.observed,self.candidates,correct=self.cue)

    def test_rejects_hidden_labels_or_unexpected_shapes(self):
        for mutation in (lambda x:x[0].append(True), lambda x:x[0][1].__setitem__(0,True),
                         lambda x:x[0][1].__setitem__(0,4),lambda x:x[0][1].__setitem__(1,1),
                         lambda x:x[0][2].append('SECRET'),lambda x:x[0].__setitem__(0,x[1][0])):
            candidates=copy.deepcopy(self.candidates)
            mutation(candidates)
            with self.assertRaises(ValueError):validate_cues(self.observed,candidates)
        with self.assertRaises(ValueError):validate_cues(self.observed+['true_cue=1'],self.candidates)

    def test_recomputed_hash_does_not_allow_changed_model(self):
        record=self.model.record()
        self.assertEqual(record,CrossFamilyTemporal.restore(copy.deepcopy(record)).record())
        mutated=copy.deepcopy(record)
        mutated["state"]["model"]["state"]["match_probability"]=.94
        mutated["state"]["model"]["sha256"]=digest(mutated["state"]["model"]["state"])
        mutated["sha256"]=digest(mutated["state"])
        with self.assertRaises(ValueError):CrossFamilyTemporal.restore(mutated)

    def test_deterministic_navigation_training_and_recovery(self):
        model,mapping=train_nav_model(self.seed)
        self.assertEqual(mapping,self.mapping)
        self.assertEqual(model.record(),self.model.record())
        self.assertEqual(model.evaluate(self.observed,self.candidates),self.model.evaluate(self.observed,self.candidates))

    def test_frozen_cohorts_and_indices(self):
        self.assertNotEqual(DEV,ADDITIONAL)
        self.assertNotEqual(TRAIN_MAPPING_START,TRAIN_PARAM_START)
        self.assertGreater(TEST_START,TRAIN_PARAM_START+30)
        with self.assertRaises(ValueError):measure([DEV[0]])
        with self.assertRaises(ValueError):measure(list(DEV)+[ADDITIONAL[0]])

    def test_same_response_task_uses_only_proposed_cue(self):
        from developmental_ai.cross_task_retention import fit_gate
        response=fit_gate(self.seed,episodes=300,validation=60)
        score=_response(self.seed,TEST_START,"long",self.cue,response.q["initial"])
        self.assertTrue(score)
        self.assertFalse(_response(self.seed,TEST_START,"long",(self.cue+1)%4,response.q["initial"]))

    def test_train_sample_is_not_a_delayed_test_sample(self):
        model,_=train_nav_model(self.seed)
        self.assertEqual(model.model.record()["state"]["pairs"],self.model.model.record()["state"]["pairs"])
        self.assertNotIn('correct',str(model.model.record()))
        self.assertTrue(all(len(pair)==2 for pair in model.model.pairs))

if __name__=='__main__':unittest.main()
