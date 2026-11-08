"""Reward-only, simulation-scoped discovery of reliable cue source aliases.

Training consumes a list of competing public cues, makes one source choice,
then receives only the terminal task-success bit. It NEVER accepts a reference
cue, correct source, hidden position, or simulator regime. The source identities
and context strings are intentionally arbitrary. This contextual bandit is a
simple target-domain adaptation baseline, NOT learned semantics or zero-shot
cross-domain intelligence. No external tool or system action access.
"""
from __future__ import annotations

import hashlib
import json
import math
from developmental_ai.environment_api import canonical, digest

SCHEMA = 'developmental-ai.reward-only-aliases/v1'
FIRST_INDEX = 78000
MAX_TRAIN = 1000


def _cues(context, cues):
    if type(context) is not str or not 1 <= len(context) <= 40 or any(
        c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
        for c in context
    ) or type(cues) is not list or len(cues) != 5:
        raise ValueError('invalid public cue context or stream')
    sources = []
    for row in cues:
        if (type(row) is not list or len(row) != 3 or type(row[0]) is not str or
                not 1 <= len(row[0]) <= 40 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in row[0]) or
                type(row[1]) is not int or row[1] not in range(4) or
                type(row[2]) is not list or len(row[2]) != 2 or
                any(type(x) is not int or abs(x) > 8 for x in row[2])):
            raise ValueError('invalid, privileged or unbounded cue')
        sources.append(row[0])
    if len(set(sources)) != 5:
        raise ValueError('duplicate cue source')
    return sorted(sources)


class RewardAliasLearner:
    """One pending train episode; replay-verified reward-only source selection.

    The training selection policy first samples each arm, then uses smoothed
    success evidence and an exploration bonus. The evaluation policy is greedy.
    No policy update is allowed on a test episode.
    """

    def __init__(self, seed, *, ignore_context=False):
        if type(seed) is not int or type(ignore_context) is not bool:
            raise ValueError('invalid model seed or ablation')
        self.seed = seed
        self.ignore_context = ignore_context
        self.sources = None
        self.contexts = set()
        self.evidence = {}
        self.events = []
        self.pending = None

    def _key(self, context):
        return '*' if self.ignore_context else context

    def _stat(self, context, source):
        return self.evidence.get((self._key(context), source), (0, 0))

    def _select_train(self, context, sources):
        candidates = []
        total = sum(self._stat(context, s)[1] for s in sources)
        for source in sources:
            wins, n = self._stat(context, source)
            if n == 0:
                quality = float('inf')
            else:
                quality = (wins + 1)/(n + 2) + .50 * math.sqrt(math.log(total + 1)/n)
            candidates.append((quality,source))
        best=max(q for q,_ in candidates)
        tied=[src for q,src in candidates if q==best]
        # Deterministic tie order avoids runtime hash randomness and permits
        # exact independent checkpoint replay after every completed episode.
        return sorted(tied)[0]

    def _select_eval(self,context,sources):
        choices=[]
        for src in sources:
            wins,n=self._stat(context,src)
            choices.append(((wins+1)/(n+2),n,src))
        best=max((c[0],c[1]) for c in choices)
        return sorted(c[2] for c in choices if c[:2]==best)[0]

    def propose(self, context, cues, *, split, index):
        sources=_cues(context,cues)
        if (self.pending is not None or split != 'train' or
                type(index) is not int or index != FIRST_INDEX + len(self.events) or
                len(self.events)>=MAX_TRAIN):
            raise ValueError('invalid or repeated training proposal')
        if self.sources is not None and sources != self.sources:
            raise ValueError('source vocabulary changed during training')
        if context not in self.contexts and len(self.contexts)>=2:
            raise ValueError('unexpected third context')
        src=self._select_train(context,sources)
        self.sources=sources
        self.contexts.add(context)
        self.pending=(context, list(sources),src,index)
        return next(list(c[2]) for c in cues if c[0]==src)

    def feedback(self, success, *, split, index):
        if (type(success) is not bool or self.pending is None or split != 'train' or
                type(index) is not int or index != self.pending[3]):
            raise ValueError('invalid or unauthorized training reward')
        ctx,sources,src,_=self.pending
        key=(self._key(ctx),src)
        wins,n=self.evidence.get(key,(0,0))
        self.evidence[key]=(wins+int(success),n+1)
        self.events.append({'context':ctx,'sources':sources,'chosen':src,'success':success})
        self.pending=None

    def predict(self,context,cues):
        sources=_cues(context,cues)
        if self.pending is not None or self.sources != sources or context not in self.contexts or not self.events:
            raise ValueError('unfitted or unknown target-domain sources')
        src=self._select_eval(context,sources)
        return next(list(c[2]) for c in cues if c[0]==src)

    def best_source(self,context,cues):
        sources=_cues(context,cues)
        if self.sources!=sources or context not in self.contexts or not self.events:
            raise ValueError('unfitted or unknown cue source')
        return self._select_eval(context,sources)

    def record(self):
        if self.pending is not None or not self.events or self.sources is None or len(self.contexts)!=2:
            raise ValueError('incomplete training or pending outcome')
        state={'schema':SCHEMA,'seed':self.seed,'ignore_context':self.ignore_context,
               'first_index':FIRST_INDEX,'sources':self.sources,'events':self.events,
               'evidence':{f'{ctx}|{src}':[win,n] for (ctx,src),(win,n) in sorted(self.evidence.items())}}
        return {'state':json.loads(canonical(state)),'digest':digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={'state','digest'} or
                type(record['state']) is not dict or digest(record['state'])!=record['digest']):
            raise ValueError('invalid or altered reward-only snapshot')
        state=record['state']
        if (set(state)!={'schema','seed','ignore_context','first_index','sources','events','evidence'} or
                state['schema']!=SCHEMA or state['first_index']!=FIRST_INDEX or
                type(state['events']) is not list or not 1 <= len(state['events']) <= MAX_TRAIN):
            raise ValueError('invalid snapshot schema')
        obj=cls(state['seed'],ignore_context=state['ignore_context'])
        for i,event in enumerate(state['events']):
            if (type(event) is not dict or set(event)!={'context','sources','chosen','success'} or
                    type(event['sources']) is not list or len(event['sources'])!=5):
                raise ValueError('invalid reward training history')
            # Only the public source identities are needed to replay model
            # decisions; no target beacon or paired reference is persisted.
            fake=[[src,0,[0,0]] for src in event['sources']]
            obj.propose(event['context'],fake,split='train',index=FIRST_INDEX+i)
            if obj.pending[2]!=event['chosen']:
                raise ValueError('impossible stored source choice')
            obj.feedback(event['success'],split='train',index=FIRST_INDEX+i)
        if obj.record()!=record:
            raise ValueError('saved reward evidence differs from replay')
        return obj
