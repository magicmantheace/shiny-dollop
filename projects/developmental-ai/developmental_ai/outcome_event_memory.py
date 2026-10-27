"""Experimental outcome-guided recall of an inferred event (simulation only).

The memory selects one event span from a fixed four-state event segmenter.
Context-to-reward meaning is acquired only from terminal booleans, never from
hidden boundaries or truth labels. This is a contextual bandit over engineered
labels, NOT generic episodic attention, online skill acquisition or permission.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter

from developmental_ai.environment_api import canonical, digest
from developmental_ai.event_segmentation import EventSegmentationModel, check_stream

SCHEMA = 'developmental-ai.outcome-event-memory/v1'
SESSION_SCHEMA = 'developmental-ai.outcome-event-session/v1'
TRAIN_START = 2000
MAX_TRAIN = 200


def _spans(tokens, model, mode):
    check_stream(tokens)
    if mode == 'hmm':
        return model.spans(tokens)
    if mode != 'raw':
        raise ValueError('unknown span policy')
    out = []
    start = 0
    for end in range(1, len(tokens) + 1):
        if end == len(tokens) or tokens[end] != tokens[end - 1]:
            out.append({'start': start, 'end': end, 'label': tokens[start]})
            start = end
    return out


def _center(span):
    return (span['start'] + span['end'] - 1) // 2


def _hashchoice(seed, i, n):
    value = hashlib.sha256(f'{SCHEMA}/{seed}/{i}'.encode()).digest()
    return int.from_bytes(value[:8], 'big') % n


class OutcomeEventMemory:
    """Reward-only contextual label utility; one selected inferred event span.

    Uses a fixed model fitted on a separate RAW-only train namespace. An
    independent reward-only raw-run control uses the same class and budget.
    Inference is read-only; success from test episodes cannot update counts.
    """

    def __init__(self, model, *, seed, mode='hmm'):
        if not isinstance(model, EventSegmentationModel) or type(seed) is not int or mode not in ('hmm', 'raw'):
            raise ValueError('invalid fitted event model or memory policy')
        self.model = model
        self.model_sha = model.record()['sha256']
        self.seed = seed
        self.mode = mode
        self.counts = {(context, label): [0, 0] for context in range(2) for label in range(4)}
        self.events = []
        self.pending = None

    def _check(self, context, tokens):
        if self.model.record()['sha256'] != self.model_sha:
            raise ValueError('event model mutated')
        if type(context) is not int or context not in (0, 1):
            raise ValueError('invalid public context')
        check_stream(tokens)
        return _spans(tokens, self.model, self.mode)

    def _choose(self, context, tokens, training, index):
        spans = self._check(context, tokens)
        stats = []
        for span in spans:
            wins, total = self.counts[(context, span['label'])]
            value = (wins + 1) / (total + 2)
            if training:
                value += .45 * math.sqrt(math.log(len(self.events) + 2) / (total + 1))
            stats.append(value)
        # Explicit exploration, stable across restart; only train actions explore.
        if training and _hashchoice(self.seed, index + 700000, 5) == 0:
            chosen = _hashchoice(self.seed, index + 800000, len(spans))
        else:
            chosen = max(range(len(spans)), key=lambda i: (stats[i], -spans[i]['start']))
        span = spans[chosen]
        return {'start': span['start'], 'end': span['end'], 'label': span['label'],
                'center': _center(span)}

    def propose(self, context, tokens, *, split, index):
        if (self.pending is not None or split != 'train' or type(index) is not int or
                index != TRAIN_START + len(self.events) or len(self.events) >= MAX_TRAIN):
            raise ValueError('invalid or duplicate training proposal')
        selected = self._choose(context, tokens, True, index)
        self.pending = {'context': context, 'tokens': list(tokens), 'index': index, 'selected': selected}
        return dict(selected)

    def feedback(self, success, *, split, index):
        if (type(success) is not bool or self.pending is None or split != 'train' or
                type(index) is not int or index != self.pending['index']):
            raise ValueError('invalid reward, episode, or pending proposal')
        event = {**self.pending, 'success': success}
        key = (event['context'], event['selected']['label'])
        self.counts[key][0] += int(success)
        self.counts[key][1] += 1
        self.events.append(event)
        self.pending = None

    def choose(self, context, tokens):
        if self.pending is not None or not self.events:
            raise ValueError('untrained or pending model')
        return self._choose(context, tokens, False, 0)

    def record(self):
        if self.model.record()['sha256'] != self.model_sha:
            raise ValueError('event model changed since training')
        if self.pending is not None or not self.events:
            raise ValueError('unfinished memory training')
        state = {'schema': SCHEMA, 'seed': self.seed, 'mode': self.mode, 'model_sha256': self.model_sha,
                 'events': self.events, 'counts': {f'{a}|{b}': value for (a,b),value in sorted(self.counts.items())}}
        return {'state': json.loads(canonical(state)), 'sha256': digest(state)}

    @classmethod
    def restore(cls, record, model):
        if (type(record) is not dict or set(record) != {'state', 'sha256'} or
                type(record['state']) is not dict or type(record['sha256']) is not str or
                digest(record['state']) != record['sha256']):
            raise ValueError('altered event priority record')
        s = record['state']
        if (set(s) != {'schema','seed','mode','model_sha256','events','counts'} or
                s['schema'] != SCHEMA or type(s['events']) is not list or
                not 1 <= len(s['events']) <= MAX_TRAIN):
            raise ValueError('incompatible outcome-memory state')
        fresh = cls(model, seed=s['seed'], mode=s['mode'])
        if fresh.model_sha != s['model_sha256']:
            raise ValueError('incorrect segmenter for priority evidence')
        for j, e in enumerate(s['events']):
            if type(e) is not dict or set(e) != {'context','tokens','index','selected','success'}:
                raise ValueError('invalid training event')
            picked = fresh.propose(e['context'],e['tokens'],split='train',index=TRAIN_START+j)
            if picked != e['selected']:
                raise ValueError('forged or inconsistent event selection')
            fresh.feedback(e['success'],split='train',index=TRAIN_START+j)
        if fresh.record() != record:
            raise ValueError('reward history differs from replay')
        return fresh


class FocusedEventSession:
    """Streaming bounded event focus with public context and replayed tokens.

    A full token log is retained for verification; this is a *one-item focus*,
    not a strict one-slot storage capacity or actual autonomous memory system.
    """
    def __init__(self, learner, context):
        if not isinstance(learner, OutcomeEventMemory) or learner.pending is not None or not learner.events:
            raise ValueError('fitted memory required')
        if type(context) is not int or context not in (0, 1):
            raise ValueError('invalid context')
        self.learner = OutcomeEventMemory.restore(learner.record(), learner.model)
        self.context = context
        self.tokens = []
        self.selected = None

    def observe(self, token):
        if self.learner.model.record()['sha256'] != self.learner.model_sha:
            raise ValueError('event model changed during focus session')
        if type(token) is not int or token not in range(4) or len(self.tokens) >= 128:
            raise ValueError('invalid or exhausted event sensor')
        self.tokens.append(token)
        self.selected = self.learner.choose(self.context, self.tokens) if len(self.tokens) >= 2 else None
        return None if self.selected is None else dict(self.selected)

    def snapshot(self):
        state = {'schema': SESSION_SCHEMA, 'learner_sha256': self.learner.record()['sha256'],
                 'context': self.context, 'tokens': list(self.tokens), 'selected': self.selected}
        return {'state': json.loads(canonical(state)), 'sha256': digest(state)}

    @classmethod
    def restore(cls, record, learner):
        if (type(record) is not dict or set(record) != {'state','sha256'} or
                type(record['state']) is not dict or digest(record['state']) != record['sha256']):
            raise ValueError('altered event focus')
        s=record['state']
        if set(s) != {'schema','learner_sha256','context','tokens','selected'} or s['schema'] != SESSION_SCHEMA or type(s['tokens']) is not list:
            raise ValueError('unknown event focus schema')
        fresh=cls(learner,s['context'])
        if fresh.learner.record()['sha256'] != s['learner_sha256']:
            raise ValueError('wrong learned priority model')
        for token in s['tokens']:
            fresh.observe(token)
        if fresh.snapshot() != record:
            raise ValueError('focused event diverges from replay')
        return fresh
