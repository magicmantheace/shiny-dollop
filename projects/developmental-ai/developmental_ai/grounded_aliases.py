"""Train-only PUBLIC paired-cue grounding for differently named memory channels.

This is supervised domain calibration from a public reference cue, not blind,
zero-shot or autonomous semantic alignment. No hidden position or simulator
regime reaches the adapter. On evaluation it sees only context and cues.
"""
from __future__ import annotations
import json
from collections import Counter
from developmental_ai.environment_api import canonical, digest
from developmental_ai.online_memory_gate import MemoryGate, CueMemory

SCHEMA = 'developmental-ai.grounded-aliases/v1'
MAX_CALIBRATION = 200


def _sample(sample):
    if (type(sample) is not dict or set(sample) != {'context','cues','reference'} or
            type(sample['context']) is not str or not 1 <= len(sample['context']) <= 40 or
            type(sample['reference']) is not list or len(sample['reference']) != 2 or
            any(type(v) is not int or not -8 <= v <= 8 for v in sample['reference']) or
            type(sample['cues']) is not list or len(sample['cues']) != 5):
        raise ValueError('invalid public paired-cue calibration')
    seen = set()
    for cue in sample['cues']:
        if (type(cue) is not list or len(cue) != 3 or
                type(cue[0]) is not str or not 1 <= len(cue[0]) <= 40 or
                cue[0] in seen or type(cue[1]) is not int or cue[1] not in range(4) or
                type(cue[2]) is not list or len(cue[2]) != 2 or
                any(type(x) is not int or abs(x)>8 for x in cue[2])):
            raise ValueError('invalid or privileged paired cue')
        seen.add(cue[0])
    if len(seen) != 5:
        raise ValueError('missing source identities')


def _infer(samples):
    counts = {}
    contexts = set()
    sources = set()
    for record in samples:
        _sample(record)
        ctx = record['context']; contexts.add(ctx)
        for src, token, offset in record['cues']:
            sources.add(src)
            count = counts.setdefault((ctx,src), [0,0])
            count[0] += (offset == record['reference'])
            count[1] += 1
    if len(contexts) != 2 or len(sources) != 5:
        raise ValueError('expected two contexts and five distinct sources')
    ordered = sorted(contexts)
    good = {}
    for ctx in ordered:
        if any((ctx,src) not in counts for src in sources):
            raise ValueError('incomplete calibration coverage')
        score = sorted(((counts[(ctx,src)][0] / counts[(ctx,src)][1],src) for src in sources),reverse=True)
        if score[0][0] < .65 or score[0][0]-score[1][0] < .25:
            raise ValueError('insufficient evidence to ground source')
        good[ctx] = score[0][1]
    if good[ordered[0]] == good[ordered[1]]:
        raise ValueError('ambiguous cross-context channel grounding')
    # The two contexts are named arbitrarily; their learned reliable sources
    # are mapped to the source roles favored by the existing trained gate.
    mapping = {src:'N' for src in sources}
    mapping[good[ordered[0]]] = 'A'
    mapping[good[ordered[1]]] = 'B'
    return {'contexts': ordered, 'source_roles': mapping, 'reliable_sources': good}


class GroundedAliases:
    """Frozen model-bound adapter; restore recomputes alignment from evidence."""
    def __init__(self, gate, samples):
        if not isinstance(gate,MemoryGate) or type(samples) not in (tuple,list) or not 8 <= len(samples) <= MAX_CALIBRATION:
            raise ValueError('invalid calibration input')
        self.gate = MemoryGate.restore(gate.record())
        self.samples = json.loads(canonical(samples))
        if len({digest(s) for s in self.samples}) != len(self.samples):
            raise ValueError('duplicated calibration evidence')
        self.alignment = _infer(self.samples)
        self.gate_digest = self.gate.record()['digest']

    def select(self, context, cues):
        # No public reference is passed during evaluation.
        if type(context) is not str or context not in self.alignment['contexts'] or type(cues) is not list or len(cues) != 5:
            raise ValueError('unknown context or invalid cue stream')
        if any(type(c) is not list or len(c)!=3 for c in cues):
            raise ValueError('invalid target cue')
        probe = {'context':context, 'reference':[0,0], 'cues':cues}
        _sample(probe)
        if set(c[0] for c in cues) != set(self.alignment['source_roles']):
            raise ValueError('unknown alias source')
        mem = CueMemory(self.gate, self.alignment['contexts'].index(context))
        for src, token, offset in cues:
            mem.observe(self.alignment['source_roles'][src],token,offset)
        return list(mem.held['payload'])

    def record(self):
        state = {'schema':SCHEMA,'gate_digest':self.gate_digest,
                 'calibration':self.samples,'alignment':self.alignment}
        return {'state':json.loads(canonical(state)),'digest':digest(state)}

    @classmethod
    def restore(cls, record,gate):
        if (type(record) is not dict or set(record)!={'state','digest'} or
                type(record['state']) is not dict or record['digest'] != digest(record['state']) or
                set(record['state']) != {'schema','gate_digest','calibration','alignment'} or
                record['state']['schema'] != SCHEMA or not isinstance(gate,MemoryGate) or
                gate.record()['digest'] != record['state']['gate_digest']):
            raise ValueError('invalid or mismatched grounding snapshot')
        obj=cls(gate,record['state']['calibration'])
        if obj.record()!=record:
            raise ValueError('calibration alignment inconsistent with evidence')
        return obj
