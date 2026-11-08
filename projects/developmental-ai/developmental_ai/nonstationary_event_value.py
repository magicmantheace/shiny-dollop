"""Experimental change-responsive event retrieval from binary outcomes.

No phase, true target, hidden span or simulator state enters a learner. A static
anchor, a bounded recent window and an explicit switch-on-failures controller
are engineering priors. This is not an autonomous skill or a safety classifier.
"""
from __future__ import annotations

import hashlib
import json
from collections import deque
from developmental_ai.environment_api import canonical, digest
from developmental_ai.event_segmentation import EventSegmentationModel
from developmental_ai.outcome_event_memory import _spans, _center

SCHEMA = 'developmental-ai.nonstationary-event-value/v1'
MODES = ('frozen', 'cumulative', 'window', 'archive', 'raw_window')
BOOTSTRAP = 200
MAX_EVENTS = 440
WINDOW = 32


def _hash_choice(seed, step, salt, n):
    h = hashlib.sha256(f'{SCHEMA}/{seed}/{step}/{salt}'.encode()).digest()
    return int.from_bytes(h[:8], 'big') % n


def _values(history, context):
    counts = {i:[0,0] for i in range(4)}
    for e in history:
        if e['context'] == context:
            label = e['selected']['label']
            counts[label][0] += int(e['success'])
            counts[label][1] += 1
    return {i:(counts[i][0]+1)/(counts[i][1]+2) for i in range(4)}


class ChangingEventMemory:
    """One reward at a time; static/whole-history/window/archive controls.

    Archive snapshots the initial, observation-only *reward experience* after
    BOOTSTRAP items; after that it cannot be edited. The active hypothesis may
    toggle after three failures in four evaluated actions, with an eight-action
    cooldown. Neither schedule nor simulator change labels are accepted.
    """
    def __init__(self, segmenter, seed, *, mode='archive'):
        if not isinstance(segmenter, EventSegmentationModel) or type(seed) is not int or mode not in MODES:
            raise ValueError('invalid model, seed or mode')
        self.model = EventSegmentationModel.restore(segmenter.record())
        self.model_digest = self.model.record()['sha256']
        self.seed, self.mode = seed, mode
        self.events = []
        self.pending = None
        self.active = 'anchor'
        self.failures = deque(maxlen=4)
        self.cooldown = 0
        self.switches = []

    def _check(self, context, tokens):
        if self.model.record()['sha256'] != self.model_digest:
            raise ValueError('segmenter mutated')
        if type(context) is not int or context not in (0,1):
            raise ValueError('invalid context')
        return _spans(tokens, self.model, 'raw' if self.mode == 'raw_window' else 'hmm')

    def _memory(self):
        if self.mode == 'frozen' or (self.mode == 'archive' and self.active == 'anchor'):
            return self.events[:BOOTSTRAP]
        if self.mode == 'cumulative':
            return self.events
        return self.events[-WINDOW:]

    def _choose(self, context, tokens, step, *, training):
        spans = self._check(context, tokens)
        values = _values(self._memory(), context)
        if training and _hash_choice(self.seed, step, 'explore', 5) == 0:
            i = _hash_choice(self.seed, step, 'alternative', len(spans))
        else:
            i = max(range(len(spans)), key=lambda n:(values[spans[n]['label']],-spans[n]['start']))
        s=spans[i]
        return {'start':s['start'], 'end':s['end'], 'label':s['label'], 'center':_center(s)}

    def propose(self, context, tokens, *, split, step):
        if (split != 'train' or self.pending is not None or type(step) is not int or
                step != len(self.events) or step >= MAX_EVENTS):
            raise ValueError('wrong training step, split, or pending action')
        selection = self._choose(context, tokens, step, training=True)
        self.pending = {'context':context,'tokens':list(tokens),'step':step,
                        'selected':selection,'active_before':self.active}
        return dict(selection)

    def feedback(self, success, *, split, step):
        if (type(success) is not bool or split != 'train' or self.pending is None or
                type(step) is not int or step != self.pending['step']):
            raise ValueError('invalid reward or pending step')
        self.events.append({**self.pending, 'success':success})
        self.pending = None
        if self.mode == 'archive' and len(self.events) > BOOTSTRAP:
            self.failures.append(not success)
            if self.cooldown:
                self.cooldown -= 1
            elif len(self.failures) == 4 and sum(self.failures) >= 3:
                self.active = 'recent' if self.active == 'anchor' else 'anchor'
                self.switches.append({'step':step,'to':self.active})
                self.failures.clear()
                self.cooldown = 8

    def choose(self, context, tokens):
        if self.pending is not None or len(self.events) < BOOTSTRAP:
            raise ValueError('not trained or pending')
        return self._choose(context,tokens,len(self.events),training=False)

    def record(self):
        if self.pending is not None or not self.events or self.model.record()['sha256'] != self.model_digest:
            raise ValueError('unfinished or modified model')
        state={'schema':SCHEMA,'seed':self.seed,'mode':self.mode,
               'model_sha256':self.model_digest,'events':self.events,'active':self.active,
               'failures':list(self.failures),'cooldown':self.cooldown,'switches':self.switches}
        return {'state':json.loads(canonical(state)),'sha256':digest(state)}

    @classmethod
    def restore(cls, record, segmenter):
        if (type(record) is not dict or set(record) != {'state','sha256'} or
                type(record['state']) is not dict or type(record['sha256']) is not str or
                digest(record['state']) != record['sha256']):
            raise ValueError('invalid event memory checkpoint')
        state=record['state']
        if (set(state) != {'schema','seed','mode','model_sha256','events','active','failures','cooldown','switches'}
                or state['schema']!=SCHEMA or type(state['events']) is not list
                or not 1<=len(state['events'])<=MAX_EVENTS):
            raise ValueError('invalid adaptive schema')
        obj=cls(segmenter,state['seed'],mode=state['mode'])
        if obj.model_digest!=state['model_sha256']:
            raise ValueError('wrong learned event segmenter')
        for j,event in enumerate(state['events']):
            if (type(event) is not dict or set(event) != {'context','tokens','step','selected','active_before','success'}
                    or type(event['success']) is not bool or type(event['step']) is not int or
                    event['step'] != j):
                raise ValueError('malformed reward history')
            action=obj.propose(event['context'],event['tokens'],split='train',step=j)
            if action!=event['selected'] or obj.active != event['active_before']:
                raise ValueError('unreplayable decision evidence')
            obj.feedback(event['success'],split='train',step=j)
        if obj.record()!=record:
            raise ValueError('checkpoint diverges from reward replay')
        return obj
