"""Evidence-based alternative-landmark-map diagnostic for simulated ring worlds.

Tests counterfactual map offsets against an immutable existing one/two-model bank.
All model/sensor inputs are observation-only.  Known ring lengths, distinguishable
half-separated landmarks and emission roles are ENGINEERED assumptions.  This is
an optional diagnostic; it cannot authorize actions or install a new model.
"""
from __future__ import annotations

import copy
import math

from developmental_ai.adaptive_dynamics import index_of, reading_index
from developmental_ai.novelty_guard import _bounded_stream
from developmental_ai.switching_belief import SwitchingBelief, _bank, _digest

SCHEMA = 'layout-novelty/v1'
MIN_STEPS = 8
MAX_EVENTS = 55


def _validate_observation(action, observation):
    if (type(action) is not int or action not in (0, 1, 2) or
            type(observation) is not dict or set(observation) != {'beacon', 'odometry', 'landmark'} or
            observation['beacon'] is not None):
        raise ValueError('expected ordinary post-initial sensor event')
    index_of(observation['odometry'])
    reading_index(observation['landmark'])


class LayoutGuard:
    """Read-only, bounded sequential counterfactual-map evidence monitor.

    The null is a switching bank of saved models. Alternatives reuse precisely
    the saved models' learned movement, odometry and emission probabilities,
    changing *only* the landmark origin on the observed ring. No test labels,
    actual positions, simulator rewards or new learned weights are accessed.
    The maximum prefix improvement is calibrated on distinct train histories.
    """

    def __init__(self, initial, goal, n, models, *, hazard=0.):
        self.bank = _bank(models)
        self.models = copy.deepcopy(models)
        self.base = SwitchingBelief(initial, goal, n, self.models, hazard=hazard)
        alternatives = {}
        for name, model in sorted(self.models.items()):
            for offset in range(n):
                if offset == model.offsets[str(n)]:
                    continue
                candidate = copy.deepcopy(model)
                candidate.offsets[str(n)] = offset
                label = f'{name}_offset_{offset}'
                alternatives[label] = SwitchingBelief(initial, goal, n, {label: candidate})
        self.alternatives = alternatives
        self.steps = 0
        self.max_gain = 0.
        self.first_alarm = None
        self.log = []

    def advance(self, action, observation, *, threshold=None):
        _validate_observation(action, observation)
        if (_bank(self.models) != self.bank or len(self.log) >= MAX_EVENTS or
                (threshold is not None and (type(threshold) not in (int,float) or
                 not math.isfinite(threshold) or threshold < 0))):
            raise ValueError('invalid bank, exhausted monitor or cutoff')
        self.base.advance(action, observation)
        for alternative in self.alternatives.values():
            alternative.advance(action, observation)
        self.steps += 1
        self.log.append([action, dict(observation)])
        if self.steps >= MIN_STEPS:
            gain = max((candidate.log_evidence - self.base.log_evidence
                        for candidate in self.alternatives.values()),default=0.)
            self.max_gain = max(0., self.max_gain, gain)
        if threshold is not None and self.first_alarm is None and self.max_gain > threshold:
            self.first_alarm = self.steps
        return {'steps':self.steps,'max_gain':self.max_gain,
                'alarm':self.first_alarm is not None, 'first_alarm_step':self.first_alarm}

    def snapshot(self):
        state={'schema':SCHEMA,'bank':self.bank,'hazard':self.base.hazard,
               'start':[self.base.initial,self.base.goal,self.base.n],
               'log':self.log,'max_gain':self.max_gain,'first_alarm':self.first_alarm}
        return {'state':state,'sha256':_digest(state)}

    @classmethod
    def restore(cls, snapshot, models, receipt):
        conf=verify_layouts(receipt,models)
        if (type(snapshot) is not dict or set(snapshot) != {'state','sha256'} or
                type(snapshot['state']) is not dict or
                snapshot.get('sha256') != _digest(snapshot['state'])):
            raise ValueError('invalid layout snapshot')
        s=snapshot['state']
        if (set(s) != {'schema','bank','hazard','start','log','max_gain','first_alarm'} or
                s['schema'] != SCHEMA or s['bank'] != conf['bank'] or
                s['hazard'] != conf['hazard'] or
                type(s['start']) is not list or len(s['start']) != 3 or
                type(s['log']) is not list or len(s['log'])>MAX_EVENTS):
            raise ValueError('incompatible layout snapshot')
        try:
            obj=cls(*s['start'],models,hazard=conf['hazard'])
            for event in s['log']:
                if type(event) is not list or len(event) != 2:
                    raise ValueError('invalid layout event')
                obj.advance(*event,threshold=conf['threshold'])
        except (KeyError,IndexError,TypeError) as e:
            raise ValueError('invalid layout snapshot history') from e
        if obj.snapshot()!=snapshot:
            raise ValueError('layout snapshot evidence replay mismatch')
        return obj


def _profile(models, stream, hazard):
    _bounded_stream(stream)
    monitor=LayoutGuard(stream['initial'],stream['goal'],stream['n'],models,hazard=hazard)
    for action,obs in stream['observations']:
        monitor.advance(action,obs)
    return monitor.max_gain


def calibrate_layouts(models, streams, *, hazard=0., alpha=.10):
    """Train-only max-prefix empirical cutoff (no guaranteed false alarm rate).

    Calibrates the entire search over offsets AND all prefixes jointly.  The
    reference observations must be disjoint from test-time evaluation streams.
    """
    bank=_bank(models)
    if (type(streams) not in (tuple,list) or not 40 <= len(streams) <= 300 or
            type(alpha) not in (int,float) or not math.isfinite(alpha) or not .04<=alpha<=.20 or
            type(hazard) not in (int,float) or not math.isfinite(hazard) or not 0<=hazard<=.3):
        raise ValueError('invalid layout calibration setup')
    hashes=[_digest(x) for x in streams]
    if len(set(hashes)) != len(hashes):
        raise ValueError('repeated calibration evidence')
    values=sorted(_profile(models,x,hazard) for x in streams)
    rank=math.ceil((len(values)+1)*(1-alpha))
    if rank>len(values):
        raise ValueError('insufficient evidence for requested quantile')
    state={'schema':SCHEMA,'bank':bank,'hazard':float(hazard),'alpha':float(alpha),
           'reference_size':len(streams),'min_steps':MIN_STEPS,
           'threshold':values[rank-1],'reference_digest':_digest(sorted(hashes))}
    return {'state':state,'sha256':_digest(state)}


def verify_layouts(receipt, models):
    if (type(receipt) is not dict or set(receipt) != {'state','sha256'} or
            type(receipt['state']) is not dict or
            receipt['sha256'] != _digest(receipt['state'])):
        raise ValueError('invalid layout calibration receipt')
    s=receipt['state']
    if (set(s) != {'schema','bank','hazard','alpha','reference_size','min_steps',
                   'threshold','reference_digest'} or s['schema'] != SCHEMA or
            s['bank'] != _bank(models) or s['min_steps'] != MIN_STEPS or
            type(s['reference_size']) is not int or not 40<=s['reference_size']<=300 or
            type(s['alpha']) not in (int,float) or not math.isfinite(s['alpha']) or
            not .04<=s['alpha']<=.20 or
            math.ceil((s['reference_size']+1)*(1-s['alpha'])) > s['reference_size'] or
            type(s['hazard']) not in (int,float) or not math.isfinite(s['hazard']) or
            not 0<=s['hazard']<=.3 or
            type(s['threshold']) not in (int,float) or not math.isfinite(s['threshold']) or
            s['threshold']<0 or
            type(s['reference_digest']) is not str or len(s['reference_digest'])!=64 or
            any(c not in '0123456789abcdef' for c in s['reference_digest'])):
        raise ValueError('invalid layout calibration configuration')
    return s


class CalibratedLayoutGuard(LayoutGuard):
    """Latching diagnostic warning; no actions, promotions or IO permissions."""

    def __init__(self, initial, goal, n, models, receipt):
        s=verify_layouts(receipt,models)
        super().__init__(initial,goal,n,models,hazard=s['hazard'])
        self.receipt=copy.deepcopy(receipt)

    def advance(self, action, observation):
        return super().advance(action,observation,
                               threshold=self.receipt['state']['threshold'])

    def snapshot(self):
        s=super().snapshot()
        s['state']['receipt_digest']=_digest(self.receipt)
        s['sha256']=_digest(s['state'])
        return s

    @classmethod
    def restore(cls, snapshot, models, receipt):
        if (type(snapshot) is not dict or type(snapshot.get('state')) is not dict or
                snapshot['state'].get('receipt_digest') != _digest(receipt)):
            raise ValueError('invalid layout receipt binding')
        state=copy.deepcopy(snapshot['state'])
        state.pop('receipt_digest')
        raw={'state':state,'sha256':_digest(state)}
        rebuilt=LayoutGuard.restore(raw,models,receipt)
        obj=cls(*snapshot['state']['start'],models,receipt)
        obj.base,obj.alternatives,obj.steps,obj.max_gain,obj.first_alarm,obj.log=(
            rebuilt.base,rebuilt.alternatives,rebuilt.steps,rebuilt.max_gain,
            rebuilt.first_alarm,rebuilt.log)
        if obj.snapshot()!=snapshot:
            raise ValueError('invalid layout receipt snapshot replay')
        return obj
