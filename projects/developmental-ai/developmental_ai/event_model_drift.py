"""Bounded read-only drift diagnostics for a frozen observation-fitted event HMM.

Only raw symbols enter the monitor. Training-only stationary reference streams
calibrate *empirical* thresholds; this is neither certified anomaly detection
nor a model-update, permission, or goal-selection mechanism.
"""
from __future__ import annotations

import json
import math
from developmental_ai.environment_api import canonical, digest
from developmental_ai.event_segmentation import EventSegmentationModel, _e, _t, check_stream

SCHEMA = 'developmental-ai.event-model-drift/v1'
RECEIPT = 'developmental-ai.event-model-drift-calibration/v1'
MAX_TICKS = 256
WARMUP, WINDOW, CUSUM_REFERENCE = 12, 16, .03
METHODS = ('cusum', 'window', 'change_rate')


def _validated_receipt(receipt, model):
    if (type(receipt) is not dict or set(receipt) != {'state', 'sha256'} or
            type(receipt['state']) is not dict or digest(receipt['state']) != receipt['sha256']):
        raise ValueError('invalid calibration record')
    s = receipt['state']
    if (set(s) != {'schema','model_sha256','evidence_digest','reference_loss',
                    'thresholds','streams','warmup','window','cusum_reference'} or
            s['schema'] != RECEIPT or s['model_sha256'] != model.record()['sha256'] or
            s['warmup'] != WARMUP or s['window'] != WINDOW or
            s['cusum_reference'] != CUSUM_REFERENCE or
            type(s['streams']) is not int or s['streams'] < 10 or s['streams'] > 200 or
            type(s['evidence_digest']) is not str or len(s['evidence_digest']) != 64 or
            type(s['reference_loss']) not in (int,float) or not math.isfinite(s['reference_loss']) or
            not 0 <= s['reference_loss'] <= 5 or type(s['thresholds']) is not dict or
            set(s['thresholds']) != set(METHODS) or any(
                type(v) not in (int,float) or not math.isfinite(v) or v < 0 or v > 256
                for v in s['thresholds'].values())):
        raise ValueError('malformed or model-mismatched calibration')
    return s


class EventDrift:
    """Online model-surprise + raw-run diagnostics; no labels or boundary signal."""
    def __init__(self, model, receipt=None, *, reference_loss=None):
        if not isinstance(model, EventSegmentationModel):
            raise ValueError('event segmentation model required')
        self.model = EventSegmentationModel(model.training, model.persistence, model.sensor_accuracy)
        self.model_sha = self.model.record()['sha256']
        self.model_parameters = (self.model.persistence, self.model.sensor_accuracy)
        self.receipt = json.loads(canonical(receipt)) if receipt is not None else None
        if receipt is not None:
            r = _validated_receipt(receipt, self.model)
            reference_loss = r['reference_loss']
        if type(reference_loss) not in (int, float) or not math.isfinite(reference_loss) or not 0 <= reference_loss <= 5:
            raise ValueError('finite reference predictive loss required')
        self.reference_loss = float(reference_loss)
        self.posterior = [.25] * 4
        self.tokens = []
        self.losses = []
        self.values = {m: [] for m in METHODS}
        self.cusum = 0.

    def observe(self, token):
        if (self.model.persistence, self.model.sensor_accuracy) != self.model_parameters:
            raise ValueError('model parameters changed during monitoring')
        if type(token) is not int or token not in range(4) or len(self.tokens) >= MAX_TICKS:
            raise ValueError('invalid or exhausted observation')
        p,q = self.model.persistence,self.model.sensor_accuracy
        prior = ([.25]*4 if not self.tokens else [sum(self.posterior[i] * _t(p,i,j) for i in range(4)) for j in range(4)])
        terms = [prior[j]*_e(q,j,token) for j in range(4)]
        likelihood = sum(terms)
        if likelihood <= 0 or not math.isfinite(likelihood):
            raise ValueError('invalid sensor likelihood')
        self.posterior = [v/likelihood for v in terms]
        loss = -math.log(likelihood)
        old = self.tokens[-1] if self.tokens else None
        self.tokens.append(token)
        self.losses.append(loss)
        k = len(self.tokens)
        self.cusum = max(0., self.cusum+loss-self.reference_loss-CUSUM_REFERENCE)
        self.values['cusum'].append(self.cusum if k >= WARMUP else 0.)
        self.values['window'].append(max(0.,sum(self.losses[-WINDOW:])/min(k, WINDOW)-self.reference_loss) if k>=WARMUP else 0.)
        switches = sum(a!=b for a,b in zip(self.tokens[max(0,k-WINDOW-1):-1],self.tokens[max(0,k-WINDOW):]))
        self.values['change_rate'].append(switches/min(k-1,WINDOW) if k>=WARMUP else 0.)
        return {'step':k,'surprise':loss,'scores':{m:self.values[m][-1] for m in METHODS},
                'alarms':self.alarms() if self.receipt else None}

    def alarms(self):
        if self.receipt is None:
            raise ValueError('no stationary calibration receipt')
        limits=self.receipt['state']['thresholds']
        return {m:self.values[m][-1] > limits[m] if self.values[m] else False for m in METHODS}

    def snapshot(self):
        if self.receipt is None:
            raise ValueError('checkpoint requires calibration receipt')
        if self.model.record()['sha256'] != self.model_sha:
            raise ValueError('frozen model changed')
        state={'schema':SCHEMA,'model_sha256':self.model_sha,'receipt_sha256':self.receipt['sha256'],
               'tokens':list(self.tokens), 'scores':{k:list(v) for k,v in self.values.items()}}
        return {'state':state,'sha256':digest(state)}

    @classmethod
    def restore(cls, saved, model, receipt):
        if (type(saved) is not dict or set(saved) != {'state','sha256'} or
                type(saved['state']) is not dict or digest(saved['state']) != saved['sha256']):
            raise ValueError('invalid checkpoint')
        s=saved['state']
        if set(s) != {'schema','model_sha256','receipt_sha256','tokens','scores'} or s['schema'] != SCHEMA or type(s['tokens']) is not list:
            raise ValueError('invalid checkpoint schema')
        obj=cls(model,receipt)
        if s['model_sha256'] != obj.model_sha or s['receipt_sha256'] != receipt['sha256']:
            raise ValueError('wrong model or calibration')
        for token in s['tokens']:
            obj.observe(token)
        if canonical(obj.snapshot()) != canonical(saved):
            raise ValueError('checkpoint scores inconsistent with observation replay')
        return obj


def calibrate(model, streams):
    """Reference loss and all maxima use only disjoint stationary fit histories."""
    if (not isinstance(model,EventSegmentationModel) or type(streams) is not list or
            not 10 <= len(streams) <= 200):
        raise ValueError('invalid stationary reference')
    for stream in streams:
        check_stream(stream)
        if len(stream) < WARMUP or len(stream) > MAX_TICKS:
            raise ValueError('invalid calibration stream length')
    provisional=[EventDrift(model, reference_loss=0.) for _ in streams]
    all_losses=[]
    for obj,s in zip(provisional,streams):
        for t in s:all_losses.append(obj.observe(t)['surprise'])
    baseline = sum(all_losses)/len(all_losses)
    maxima={m:[] for m in METHODS}
    for s in streams:
        obj=EventDrift(model,reference_loss=baseline)
        for t in s:obj.observe(t)
        for m in METHODS:maxima[m].append(max(obj.values[m]))
    # At most floor(0.1 * N) strictly-greater maxima, with ties not counted.
    thresholds={m:sorted(v)[max(0,len(v)-1-len(v)//10)] for m,v in maxima.items()}
    state={'schema':RECEIPT,'model_sha256':model.record()['sha256'],
           'evidence_digest':digest(streams),'reference_loss':baseline,
           'thresholds':thresholds,'streams':len(streams),'warmup':WARMUP,
           'window':WINDOW,'cusum_reference':CUSUM_REFERENCE}
    return {'state':state,'sha256':digest(state)}
