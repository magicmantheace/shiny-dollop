"""Reward-only adaptation to per-episode cue reliability, never source labels.

A bounded simulation experiment: candidates contain an opaque source, a target
cue, and a public forecast of a short public observation sequence. The correct
source changes per episode. No ground-truth target, correct-source label,
privileged simulator state or reward enters the predictor. Training sees only
terminal success/failure after its proposed cue is used. The forecast-agreement
feature and four discrete bins are ENGINEERED; this is not general semantics.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from developmental_ai.environment_api import canonical, digest

SCHEMA = 'developmental-ai.dynamic-reliability/v1'
START = 88000
LIMIT = 360
SOURCES = ('src_0', 'src_1', 'src_2', 'src_3', 'src_4')
PROBES = 8


def validate(probes, cues):
    if (type(probes) is not list or len(probes) != PROBES or
            any(type(x) is not int or x not in range(4) for x in probes) or
            type(cues) is not list or len(cues) != 5):
        raise ValueError('invalid public probe or candidates')
    found = set()
    for cue in cues:
        if (type(cue) is not list or len(cue) != 3 or
                type(cue[0]) is not str or cue[0] not in SOURCES or cue[0] in found or
                type(cue[1]) is not list or len(cue[1]) != 2 or
                any(type(v) is not int or not -8 <= v <= 8 for v in cue[1]) or
                type(cue[2]) is not list or len(cue[2]) != PROBES or
                any(type(v) is not int or v not in range(4) for v in cue[2])):
            raise ValueError('invalid or privileged candidate')
        found.add(cue[0])
    if found != set(SOURCES):
        raise ValueError('missing public source')
    return {c[0]:sum(a == b for a, b in zip(probes, c[2])) for c in cues}


def bin_of(agreement):
    if type(agreement) is not int or not 0 <= agreement <= PROBES:
        raise ValueError('invalid feature')
    return min(3, agreement // 2)  # 0-1, 2-3, 4-5, 6-8


class DynamicReliability:
    """Learn a pooled reward table by evidence bucket, or identity-only ablation.

    The model sees public feature evidence at decision time; only task success
    is supplied at feedback time. All fits use train namespace, monotonic IDs.
    Checkpoints replay every choice and reward, not merely a checksum.
    """
    def __init__(self, seed, *, basis='evidence'):
        if type(seed) is not int or basis not in ('evidence', 'identity'):
            raise ValueError('invalid learner configuration')
        self.seed, self.basis = seed, basis
        self.stats = {}  # key -> [wins, visits]
        self.events = []
        self.pending = None

    def _key(self, name, agreement):
        return str(bin_of(agreement)) if self.basis == 'evidence' else name

    def _choose(self, feature, index, *, train):
        keys = sorted(feature)
        rng = random.Random(int.from_bytes(hashlib.sha256(
            f'{SCHEMA}/{self.seed}/{self.basis}/{index}'.encode()).digest()[:8], 'big'))
        if train and rng.random() < (0.75 if len(self.events) < 180 else 0.30):
            return rng.choice(keys)
        options = []
        for name in keys:
            wins, count = self.stats.get(self._key(name, feature[name]), [0, 0])
            if train:
                value = (wins+1)/(count+2) + .45*math.sqrt(math.log(len(self.events)+2)/(count+1))
            else:
                value = (wins+1)/(count+2)
            options.append((value, name))
        best = max(q for q,_ in options)
        return min(s for q,s in options if q == best)

    def propose(self, probes, cues, *, split, index):
        feature = validate(probes, cues)
        if (self.pending is not None or split != 'train' or
                type(index) is not int or index != START + len(self.events) or
                len(self.events) >= LIMIT):
            raise ValueError('training index, mode or pending choice invalid')
        name = self._choose(feature, index, train=True)
        self.pending = (index, feature, name)
        return next(list(c[1]) for c in cues if c[0] == name)

    def feedback(self, success, *, split, index):
        if (type(success) is not bool or self.pending is None or split != 'train' or
                type(index) is not int or index != self.pending[0]):
            raise ValueError('invalid reward or pending training episode')
        _, feature, name = self.pending
        key = self._key(name,feature[name])
        wins, n = self.stats.get(key,[0,0])
        self.stats[key] = [wins + int(success), n+1]
        self.events.append({'index':index,'feature':dict(feature), 'chosen':name,'success':success})
        self.pending = None

    def source(self, probes, cues):
        feature = validate(probes,cues)
        if self.pending is not None or not self.events:
            raise ValueError('incomplete or pending learner')
        return self._choose(feature, START + LIMIT, train=False)

    def predict(self,probes,cues):
        name = self.source(probes,cues)
        return next(list(c[1]) for c in cues if c[0] == name)

    def record(self):
        if self.pending is not None or not self.events:
            raise ValueError('incomplete reward history')
        state = {'schema':SCHEMA,'seed':self.seed,'basis':self.basis,
                 'events':self.events,'stats':self.stats}
        return {'state':json.loads(canonical(state)), 'digest':digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {'state','digest'} or
                type(record['state']) is not dict or record['digest'] != digest(record['state'])):
            raise ValueError('invalid or altered checkpoint')
        s = record['state']
        if (set(s) != {'schema','seed','basis','events','stats'} or s['schema'] != SCHEMA or
                type(s['events']) is not list or not 1 <= len(s['events']) <= LIMIT):
            raise ValueError('wrong checkpoint schema')
        obj = cls(s['seed'],basis=s['basis'])
        for idx,event in enumerate(s['events']):
            if (type(event) is not dict or set(event) != {'index','feature','chosen','success'} or
                    event['index'] != START+idx or type(event['success']) is not bool or
                    type(event['feature']) is not dict or set(event['feature']) != set(SOURCES) or
                    any(type(n) is not int or not 0 <= n <= PROBES for n in event['feature'].values()) or
                    event['chosen'] not in SOURCES):
                raise ValueError('invalid replay event')
            # Reconstruct a public, forecast-consistent witness with exactly
            # the stored agreement counts; offsets are irrelevant to selection.
            probes = [0]*PROBES
            cues = [[name,[0,0],[0]*count+[1]*(PROBES-count)]
                    for name,count in event['feature'].items()]
            obj.propose(probes,cues,split='train',index=START+idx)
            if obj.pending[2] != event['chosen']:
                raise ValueError('saved decision contradicts reward history')
            obj.feedback(event['success'],split='train',index=START+idx)
        if obj.record() != record:
            raise ValueError('replayed reward statistics differ')
        return obj
