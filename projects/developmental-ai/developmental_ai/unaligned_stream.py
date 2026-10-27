"""Experimental reward-only source selection from unaligned raw symbol streams.

Observed and forecast streams retain temporal order but contain independent
insertions. Neither token correspondence, cipher, correct source nor target
position is exposed to this model. Fixed 4x4 pair statistics and a monotone
alignment DP are architectural priors, not learned general representations.
"""
from __future__ import annotations
import hashlib
import json
import math

from developmental_ai.environment_api import canonical, digest
from developmental_ai.raw_token_transfer import OBS, FORECAST, SOURCES

SCHEMA = 'developmental-ai.unaligned-stream/v1'
TRAIN_START = 89400
MAX_TRAIN = 240
MIN_LENGTH, MAX_LENGTH = 10, 12


def validate(observed, candidates):
    if (type(observed) is not list or not MIN_LENGTH <= len(observed) <= MAX_LENGTH or
            any(type(token) is not str or token not in OBS for token in observed) or
            type(candidates) is not list or len(candidates) != 5):
        raise ValueError('invalid sensor sequence or candidate list')
    names = set()
    for row in candidates:
        if (type(row) is not list or len(row) != 3 or type(row[0]) is not str or
                row[0] not in SOURCES or row[0] in names or
                type(row[1]) is not list or len(row[1]) != 2 or
                any(type(v) is not int or not -8 <= v <= 8 for v in row[1]) or
                type(row[2]) is not list or not MIN_LENGTH <= len(row[2]) <= MAX_LENGTH or
                any(type(v) is not str or v not in FORECAST for v in row[2])):
            raise ValueError('invalid or privileged raw forecast')
        names.add(row[0])
    if names != set(SOURCES):
        raise ValueError('incomplete source set')
    return {row[0]:list(row[2]) for row in candidates}


def near_pairs(observed, forecast):
    """Unsupervised time-proximity prior, *not* provided slot alignment."""
    n, m = len(observed), len(forecast)
    for i, token in enumerate(observed):
        for j, prediction in enumerate(forecast):
            relative = abs(i/(n-1)-j/(m-1))
            if relative <= .22:
                yield OBS.index(token)*4 + FORECAST.index(prediction), 1.0/(1+8*relative)


def alignment_score(observed, forecast, pair_scores, *, gap_penalty=.28):
    """Max monotone alignment of raw tokens with bounded insertion penalties."""
    n,m=len(observed),len(forecast)
    dp=[[0.0]*(m+1) for _ in range(n+1)]
    for i in range(1,n+1):dp[i][0]=-i*gap_penalty
    for j in range(1,m+1):dp[0][j]=-j*gap_penalty
    for i in range(1,n+1):
        for j in range(1,m+1):
            s=pair_scores[OBS.index(observed[i-1])*4+FORECAST.index(forecast[j-1])]
            dp[i][j]=max(dp[i-1][j-1]+s,dp[i-1][j]-gap_penalty,dp[i][j-1]-gap_penalty)
    return dp[n][m]/max(n,m)


class UnalignedRewardLearner:
    """Bandit learner with strict binary reward and exact recorded-decision replay."""
    def __init__(self,seed):
        if type(seed) is not int:raise ValueError('invalid seed')
        self.seed=seed
        self.positive=[0.0]*16
        self.negative=[0.0]*16
        self.history=[]
        self.pending=None

    def _choice(self,index):
        data=hashlib.sha256(f'{SCHEMA}/{self.seed}/{index}/explore'.encode()).digest()
        return SOURCES[int.from_bytes(data[:8],'big')%len(SOURCES)]

    def propose(self,observed,candidates,*,split,index):
        seqs=validate(observed,candidates)
        if (self.pending is not None or split!='train' or type(index) is not int or
                index!=TRAIN_START+len(self.history) or len(self.history)>=MAX_TRAIN):
            raise ValueError('out of sequence training proposal')
        name=self._choice(index)
        self.pending=(index,list(observed),seqs[name],name)
        return list(next(row[1] for row in candidates if row[0]==name))

    def feedback(self,success,*,split,index):
        if (type(success) is not bool or self.pending is None or split!='train' or
                type(index) is not int or index!=self.pending[0]):
            raise ValueError('invalid feedback or pending episode')
        _,obs,forecast,name=self.pending
        bank=self.positive if success else self.negative
        for key,weight in near_pairs(obs,forecast):bank[key]+=weight
        self.history.append({'index':index,'observed':obs,'forecast':forecast,
                             'chosen':name,'success':success})
        self.pending=None

    def scores(self):
        if not self.history or self.pending is not None:raise ValueError('unfitted learner')
        pos=sum(self.positive);neg=sum(self.negative)
        return [max(-1.,min(1.,math.log((self.positive[k]+1)/(pos+16))-
                         math.log((self.negative[k]+1)/(neg+16)))) for k in range(16)]

    def source(self,observed,candidates):
        seqs=validate(observed,candidates);weights=self.scores()
        values={src:alignment_score(observed,forecast,weights) for src,forecast in seqs.items()}
        return min(src for src in SOURCES if values[src]==max(values.values()))

    def predict(self,observed,candidates):
        source=self.source(observed,candidates)
        return list(next(row[1] for row in candidates if row[0]==source))

    def record(self):
        if self.pending is not None or not self.history:raise ValueError('incomplete episode history')
        state={'schema':SCHEMA,'seed':self.seed,'history':self.history,
               'positive':self.positive,'negative':self.negative}
        return {'state':json.loads(canonical(state)),'digest':digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={'state','digest'} or
                type(record['state']) is not dict or record['digest']!=digest(record['state'])):
            raise ValueError('invalid integrity record')
        state=record['state']
        if (set(state)!={'schema','seed','history','positive','negative'} or
                state['schema']!=SCHEMA or type(state['history']) is not list or
                not 1 <=len(state['history'])<=MAX_TRAIN):
            raise ValueError('invalid record schema')
        rebuilt=cls(state['seed'])
        for i,event in enumerate(state['history']):
            if (type(event) is not dict or set(event)!={'index','observed','forecast','chosen','success'} or
                    type(event['success']) is not bool or type(event['chosen']) is not str or
                    event['chosen'] not in SOURCES or event['index']!=TRAIN_START+i):
                raise ValueError('invalid saved episode')
            candidates=[[name,[0,0],list(event['forecast'] if name==event['chosen'] else
                           [FORECAST[0]]*len(event['forecast']))] for name in SOURCES]
            rebuilt.propose(event['observed'],candidates,split='train',index=TRAIN_START+i)
            if rebuilt.pending[3]!=event['chosen']:
                raise ValueError('unreplayable training selection')
            rebuilt.feedback(event['success'],split='train',index=TRAIN_START+i)
        if rebuilt.record()!=record:raise ValueError('training history or statistics mismatch')
        return rebuilt
