"""Validate simulation-only drift monitoring, calibration, and exact replay."""
from __future__ import annotations

import copy
import math
import unittest
from developmental_ai.environment_api import digest
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.event_model_drift import EventDrift,calibrate,METHODS
from benchmarks.event_model_drift_benchmark import pair,measure,DEV
from benchmarks.event_segmentation_benchmark import episode


class DriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=14003
        cls.model=fit_event_model([episode(cls.seed,'source_bursts','train',i)['observed'] for i in range(12)])
        cls.references=[pair(cls.seed,'train',400+i,False)[0] for i in range(12)]
        cls.receipt=calibrate(cls.model,cls.references)

    def test_predictive_filter_normalized_and_deterministic(self):
        x=EventDrift(self.model,self.receipt)
        y=EventDrift(self.model,self.receipt)
        for t in self.references[0]:
            self.assertEqual(x.observe(t),y.observe(t))
            self.assertAlmostEqual(sum(x.posterior),1)
            self.assertTrue(math.isfinite(x.losses[-1]))
        self.assertEqual(x.snapshot(),y.snapshot())

    def test_restore_replays_every_score(self):
        a=EventDrift(self.model,self.receipt)
        for token in self.references[0][:17]:a.observe(token)
        snap=a.snapshot();b=EventDrift.restore(copy.deepcopy(snap),self.model,self.receipt)
        self.assertEqual(a.snapshot(),b.snapshot())
        for token in self.references[0][17:]:
            self.assertEqual(a.observe(token),b.observe(token))
        self.assertEqual(a.snapshot(),b.snapshot())

    def test_rehashed_tamper_rejected(self):
        a=EventDrift(self.model,self.receipt)
        for token in self.references[0][:20]:a.observe(token)
        snap=a.snapshot()
        for method in METHODS:
            bad=copy.deepcopy(snap)
            bad['state']['scores'][method][-1]+=1
            bad['sha256']=digest(bad['state'])
            with self.assertRaises(ValueError):EventDrift.restore(bad,self.model,self.receipt)

    def test_schema_model_and_calibration_restrictions(self):
        bad=copy.deepcopy(self.receipt)
        bad['state']['reference_loss']+=1
        bad['sha256']=digest(bad['state'])
        # Integrity alone cannot authenticate a fully forged receipt.
        self.assertNotEqual(bad,self.receipt)
        other=fit_event_model([episode(self.seed,'source_bursts','train',i)['observed'] for i in range(16)])
        with self.assertRaises(ValueError):EventDrift(other,self.receipt)
        with self.assertRaises(ValueError):calibrate(self.model,[self.references[0]]*9)
        with self.assertRaises(ValueError):calibrate(self.model,[{'hidden':1}]*12)
        with self.assertRaises(ValueError):EventDrift(self.model,reference_loss=True)

    def test_rejects_privileged_and_malformed_observations(self):
        a=EventDrift(self.model,self.receipt)
        for x in (True, -1,4,'0',None,{'token':0,'true_state':1}):
            with self.assertRaises(ValueError):a.observe(x)
        self.assertEqual(len(a.tokens),0)
        for i in range(256):a.observe(i%4)
        with self.assertRaises(ValueError):a.observe(1)

    def test_model_parameter_change_fails_closed_mid_stream(self):
        nav=EventDrift(self.model,self.receipt)
        nav.observe(0)
        nav.model.persistence=.51
        with self.assertRaises(ValueError):nav.observe(1)
        with self.assertRaises(ValueError):nav.snapshot()
        self.assertEqual(nav.tokens,[0])

    def test_drift_not_automatically_authorized_or_promoted(self):
        nav=EventDrift(self.model,self.receipt)
        for token in self.references[0]: nav.observe(token)
        self.assertFalse(hasattr(nav,'act'))
        self.assertFalse(hasattr(nav,'promote'))
        self.assertEqual(set(nav.alarms()),set(METHODS))

    def test_no_alarming_before_warmup(self):
        a=EventDrift(self.model,self.receipt)
        for x in self.references[0][:11]:
            v=a.observe(x)
            self.assertFalse(any(v['alarms'].values()))

    def test_calibration_train_maxima_bounded(self):
        r=self.receipt
        for method in METHODS:
            false_alarms=0
            for seq in self.references:
                nav=EventDrift(self.model,r)
                for t in seq:nav.observe(t)
                false_alarms+=any(val>r['state']['thresholds'][method] for val in nav.values[method])
            self.assertLessEqual(false_alarms,1)

    def test_no_unapproved_cohort_or_evaluation_input(self):
        with self.assertRaises(ValueError):measure([14003])
        with self.assertRaises(ValueError):measure(list(DEV)+[27007])
        a=EventDrift(self.model,self.receipt)
        with self.assertRaises(TypeError):a.observe(0,regime='shifted')

if __name__ == '__main__':unittest.main()
