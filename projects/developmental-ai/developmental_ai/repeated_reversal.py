"""Experimental reward-only event retrieval after repeated hidden goal reversals.

Five bounded baselines, including frozen-anchor versus recent reward-history
reidentification. This is simulation-only and does not discover transferable
skills, authorize actions, or certify drift. Hidden phases are never inputs.
"""
from __future__ import annotations
import hashlib
import json
import math
from developmental_ai.environment_api import canonical, digest
from developmental_ai.event_segmentation import EventSegmentationModel
from developmental_ai.outcome_event_memory import _spans, _center

SCHEMA = 'developmental-ai.repeated-reversal/v1'
MODES = ('frozen','cumulative','window32','archive_recall','raw_window32')
BOOTSTRAP = 200
MAX_EVENTS = 680
WINDOW = 32
COMPARISON = 16
MARGIN = 1.5


def values(events, context):
    counts = [[0,0] for _ in range(4)]
    for event in events:
        if event['context'] == context:
            row = counts[event['selected']['label']]
            row[0] += int(event['success'])
            row[1] += 1
    return [(wins+1)/(n+2) for wins,n in counts]


def _logscore(events, history):
    total = 0.
    predictions = {ctx:values(history,ctx) for ctx in (0,1)}
    for event in events:
        prob = predictions[event['context']][event['selected']['label']]
        total += math.log(prob if event['success'] else 1-prob)
    return total


class RepeatedReversalMemory:
    """One selected event and one binary terminal outcome per training step."""
    def __init__(self, model, seed, *, mode='archive_recall'):
        if not isinstance(model,EventSegmentationModel) or type(seed) is not int or mode not in MODES:
            raise ValueError('invalid learned model, seed, or mode')
        self.model=EventSegmentationModel(model.training,model.persistence,model.sensor_accuracy)
        self.model_sha=self.model.record()['sha256']
        self.frozen_params=(model.persistence,model.sensor_accuracy)
        self.frozen_training=json.loads(canonical(self.model.training))
        self.seed,self.mode=seed,mode
        self.history=[]
        self.pending=None

    def _check(self,context,tokens):
        if ((self.model.persistence,self.model.sensor_accuracy)!=self.frozen_params or
                self.model.training!=self.frozen_training):
            raise ValueError('frozen segmenter changed')
        if type(context) is not int or context not in (0,1):
            raise ValueError('invalid public context')
        return _spans(tokens,self.model,'raw' if self.mode=='raw_window32' else 'hmm')

    def _source(self):
        n=len(self.history)
        if n<=BOOTSTRAP or self.mode=='frozen':return 'anchor'
        if self.mode=='cumulative':return 'cumulative'
        if self.mode!='archive_recall':return 'recent'
        if n<BOOTSTRAP+2*COMPARISON:return 'recent'
        # Evaluate two *fixed historical* predictions on a later, disjoint
        # recent slice of the agent's own selected/rewarded episodes. This
        # is a heuristic likelihood contrast, NOT a change probability.
        eval_events=self.history[-COMPARISON:]
        prior_recent=self.history[-(WINDOW+COMPARISON):-COMPARISON]
        archive=self.history[:BOOTSTRAP]
        if _logscore(eval_events,archive)>_logscore(eval_events,prior_recent)+MARGIN:
            return 'anchor'
        return 'recent'

    def _choose(self,context,tokens,index,training):
        spans=self._check(context,tokens)
        source=self._source()
        history=(self.history[:BOOTSTRAP] if source=='anchor' else
                 self.history if source=='cumulative' else self.history[-WINDOW:])
        likelihoods=values(history,context)
        if training and int.from_bytes(hashlib.sha256(f'{SCHEMA}/{self.seed}/{index}/explore'.encode()).digest()[:8],'big')%5==0:
            pos=int.from_bytes(hashlib.sha256(f'{SCHEMA}/{self.seed}/{index}/choice'.encode()).digest()[:8],'big')%len(spans)
        else:
            pos=max(range(len(spans)),key=lambda i:(likelihoods[spans[i]['label']],-spans[i]['start']))
        span=spans[pos]
        return {'start':span['start'],'end':span['end'],'label':span['label'],
                'center':_center(span)},source

    def propose(self,context,tokens,*,split,index):
        if (split!='train' or self.pending is not None or type(index) is not int or
                index!=len(self.history) or index>=MAX_EVENTS):
            raise ValueError('training must advance monotonically with no pending action')
        selected,source=self._choose(context,tokens,index,True)
        self.pending={'index':index,'context':context,'tokens':list(tokens),
                      'selected':selected,'source':source}
        return dict(selected)

    def feedback(self,success,*,split,index):
        if (type(success) is not bool or split!='train' or self.pending is None or
                type(index) is not int or index!=self.pending['index']):
            raise ValueError('invalid terminal feedback or pending episode')
        self.history.append({**self.pending,'success':success})
        self.pending=None

    def choose(self,context,tokens):
        if self.pending is not None or len(self.history)<BOOTSTRAP:
            raise ValueError('not bootstrapped or pending training feedback')
        selection,source=self._choose(context,tokens,len(self.history),False)
        return {'selection':selection,'source':source}

    def record(self):
        if (self.pending is not None or not self.history or
                (self.model.persistence,self.model.sensor_accuracy)!=self.frozen_params or
                self.model.training!=self.frozen_training):
            raise ValueError('unfinished session or changed model')
        state={'schema':SCHEMA,'mode':self.mode,'seed':self.seed,
               'model_sha256':self.model_sha,'history':self.history}
        return {'state':json.loads(canonical(state)),'sha256':digest(state)}

    @classmethod
    def restore(cls,saved,model):
        if (type(saved) is not dict or set(saved)!={'state','sha256'} or
            type(saved['state']) is not dict or type(saved['sha256']) is not str or
            digest(saved['state'])!=saved['sha256']):
            raise ValueError('altered or malformed checkpoint')
        s=saved['state']
        if (set(s)!={'schema','mode','seed','model_sha256','history'} or
            s['schema']!=SCHEMA or type(s['history']) is not list or
            not 1<=len(s['history'])<=MAX_EVENTS):
            raise ValueError('unsupported checkpoint schema')
        rebuilt=cls(model,s['seed'],mode=s['mode'])
        if rebuilt.model_sha!=s['model_sha256']:
            raise ValueError('wrong frozen event model')
        for i,event in enumerate(s['history']):
            if (type(event) is not dict or set(event)!={'index','context','tokens','selected','source','success'} or
                type(event['success']) is not bool or type(event['index']) is not int or event['index']!=i):
                raise ValueError('invalid saved evidence')
            if rebuilt.propose(event['context'],event['tokens'],split='train',index=i)!=event['selected'] or rebuilt.pending['source']!=event['source']:
                raise ValueError('impossible archived memory action')
            rebuilt.feedback(event['success'],split='train',index=i)
        if rebuilt.record()!=saved:
            raise ValueError('event-memory history cannot be replayed')
        return rebuilt
