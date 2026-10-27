"""Explicitly supervised spatial belief calibration, not unlabelled learning."""
import copy
import math
import unittest
from developmental_ai.online_dynamics import initial_model
from developmental_ai.spatial_calibration import (
    TEMPERATURES, temper, fit_profile, validate_profile, calibrated_posterior,
    instrumented_stream, diagnostics, digest,
)

class SpatialCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.model=initial_model()
        self.records=instrumented_stream(self.model, 17, split="train", first=5000,
                                        episodes=2, noise="high", layout="shifted", steps=4)

    def test_temper_is_normalized_and_identity(self):
        p=[.6,.2,.1,.1]+[0.]*5
        self.assertAlmostEqual(sum(temper(p,2)),1.)
        for a,b in zip(temper(p,1),p):self.assertAlmostEqual(a,b,places=9)
        self.assertLess(temper(p,2)[0],p[0])
        self.assertGreater(temper(p,.5)[0],p[0])

    def test_profile_is_deterministic_and_model_bound(self):
        a=fit_profile(self.model,self.records)
        self.assertEqual(a,fit_profile(self.model,self.records))
        self.assertIn(validate_profile(self.model,a),TEMPERATURES)
        self.assertAlmostEqual(sum(calibrated_posterior(self.model,a,self.records[0]['posterior'])),1.)
        altered=initial_model();altered.counts['motion'][0][0]+=1
        with self.assertRaises(ValueError):validate_profile(altered,a)

    def test_test_namespace_refused_for_training(self):
        altered=copy.deepcopy(self.records);altered[0]['split']='test'
        with self.assertRaises(ValueError):fit_profile(self.model,altered)

    def test_duplicate_and_insufficient_evidence_refused(self):
        with self.assertRaises(ValueError):fit_profile(self.model,self.records+[self.records[0]])
        with self.assertRaises(ValueError):fit_profile(self.model,[])
        altered=copy.deepcopy(self.records);altered[0]['episode']=5
        with self.assertRaises(ValueError):fit_profile(self.model,altered)

    def test_tampering_detected_even_with_recalculated_checksum(self):
        p=fit_profile(self.model,self.records)
        altered=copy.deepcopy(p);altered['body']['scope']='tool-permission'
        altered['digest']=digest(altered['body'])
        with self.assertRaises(ValueError):validate_profile(self.model,altered)
        altered=copy.deepcopy(p);altered['body']['temperature']=500
        altered['digest']=digest(altered['body'])
        with self.assertRaises(ValueError):validate_profile(self.model,altered)

    def test_invalid_probability_and_privileged_fields_rejected(self):
        with self.assertRaises(ValueError):temper([float('nan')]+[0]*8,1)
        with self.assertRaises(ValueError):temper([.5]*9,1)
        with self.assertRaises(ValueError):temper([1]+[0]*8,0)
        altered=copy.deepcopy(self.records);altered[0]['secret_regime']='changed'
        with self.assertRaises(ValueError):fit_profile(self.model,altered)

    def test_supervised_fitting_reduces_its_own_nll(self):
        p=fit_profile(self.model,self.records)
        x=diagnostics(self.records,1.)['nll']
        y=diagnostics(self.records,p['body']['temperature'])['nll']
        self.assertLessEqual(y,x+1e-6)

    def test_instrumented_stream_deterministic_and_readonly(self):
        old=copy.deepcopy(self.model.counts)
        self.assertEqual(self.records,instrumented_stream(self.model,17,split='train',first=5000,episodes=2,noise='high',layout='shifted',steps=4))
        self.assertEqual(self.model.counts,old)
        with self.assertRaises(ValueError):instrumented_stream(self.model,17,split='train',first=10,episodes=1,noise='high',layout='shifted')

    def test_credible_coverage_valid(self):
        stats=diagnostics(self.records)
        self.assertGreaterEqual(stats['credible80_coverage'],0)
        self.assertLessEqual(stats['credible80_coverage'],1)
        self.assertGreaterEqual(stats['credible80_set_size'],1)

if __name__=='__main__':unittest.main()
