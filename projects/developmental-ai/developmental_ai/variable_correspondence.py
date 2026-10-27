"""Optional, observation-only estimation of how many events correspond.

The known 4-symbol alphabet, monotone order, and upper bound of EIGHT possible
shared events remain engineered. An expectation-semiring alignment marginalizes
3..8 correspondences; three bounded EM updates infer overlap survival and
matched-symbol reliability from *public, pseudo-selected training pairs*.
Neither true alignment nor the generator's insertion/deletion flags are inputs.
This is not a general temporal world model or an action authority.
"""
from __future__ import annotations

import itertools
import json
import math

from developmental_ai.environment_api import canonical, digest
from developmental_ai.raw_token_transfer import OBS, FORECAST
from developmental_ai.probabilistic_alignment import _permutation
from developmental_ai.raw_token_transfer import SOURCES

SCHEMA = 'developmental-ai.variable-correspondence/v1'
K_VALUES = (3, 4, 5, 6, 7, 8)
ITERATIONS = 3


def _pair(observed, forecast):
    if (type(observed) is not list or type(forecast) is not list or
            not 8 <= len(observed) <= 12 or not 8 <= len(forecast) <= 12 or
            any(type(x) is not str or x not in OBS for x in observed) or
            any(type(x) is not str or x not in FORECAST for x in forecast)):
        raise ValueError('invalid observation-only pair')


def partitions(observed, forecast, mapping, match_probability):
    """For each K, return normalized likelihood ratio and expected symbol matches.

    Prefix DP sums products over all monotone K-subsequences. The parallel
    accumulator stores likelihood-weighted agreement counts. This is exact for
    the explicit emission model, and independent of any true event alignment.
    """
    _pair(observed,forecast)
    mapping=_permutation(mapping)
    if type(match_probability) not in (int,float) or not .52<=match_probability<=.94 or not math.isfinite(match_probability):
        raise ValueError('invalid emission probability')
    n,m=len(observed),len(forecast)
    match=[[int(mapping[OBS.index(x)]==FORECAST.index(y)) for y in forecast] for x in observed]
    weights=[[4*(match_probability if match[i][j] else (1-match_probability)/3) for j in range(m)] for i in range(n)]
    earlier=None
    output={}
    for k in range(1,max(K_VALUES)+1):
        p=[[0.]*m for _ in range(n)]
        q=[[0.]*m for _ in range(n)]
        for i in range(k-1,n):
            for j in range(k-1,m):
                if k==1:mass,stat=weights[i][j],weights[i][j]*match[i][j]
                else:
                    old_mass,old_stat=earlier
                    mass=weights[i][j]*old_mass[i][j]
                    stat=weights[i][j]*(old_stat[i][j]+match[i][j]*old_mass[i][j])
                p[i][j],q[i][j]=mass,stat
        def prefix(values):
            out=[[0.]*(m+1) for _ in range(n+1)]
            for i in range(n):
                for j in range(m):
                    out[i+1][j+1]=out[i][j+1]+out[i+1][j]-out[i][j]+values[i][j]
            return out
        # Shift indices to exclusive prefix for the next K.
        pp=prefix(p);qq=prefix(q)
        earlier=(pp,qq)
        if k in K_VALUES:
            total=pp[n][m]
            if total<=0 or not math.isfinite(total):raise ValueError('invalid alignment partition')
            output[k]=(total/(math.comb(n,k)*math.comb(m,k)),qq[n][m]/total)
    return output


def statistics(observed,forecast,mapping,match_probability,survival):
    if type(survival) not in (int,float) or not math.isfinite(survival) or not .4<=survival<=.95:
        raise ValueError('invalid retention estimate')
    parts=partitions(observed,forecast,mapping,match_probability)
    probs={k:math.comb(8,k)*survival**k*(1-survival)**(8-k) for k in K_VALUES}
    norm=sum(probs.values())
    mass={k:parts[k][0]*probs[k]/norm for k in K_VALUES}
    z=sum(mass.values())
    if z<=0 or not math.isfinite(z):raise ValueError('invalid mixture partition')
    post={k:mass[k]/z for k in K_VALUES}
    return {'log_likelihood_ratio':math.log(z),
            'expected_matches':sum(k*post[k] for k in K_VALUES),
            'expected_agreements':sum(parts[k][1]*post[k] for k in K_VALUES),
            'posterior':post}


def _candidates(observed,candidates):
    if type(candidates) is not list or len(candidates)!=5:
        raise ValueError('invalid candidate stream count')
    rows={}
    for row in candidates:
        if (type(row) is not list or len(row)!=3 or type(row[0]) is not str or
                row[0] not in SOURCES or row[0] in rows or type(row[1]) is not list or
                len(row[1])!=2 or any(type(x) is not int or abs(x)>8 for x in row[1])):
            raise ValueError('invalid public candidate')
        _pair(observed,row[2])
        rows[row[0]]=row[2]
    if set(rows)!=set(SOURCES):raise ValueError('incomplete public sources')
    return rows


class VariableCorrespondence:
    """Fit two scalar channel parameters using train-only public pairs.

    Training pairs are chosen by a PRE-FROZEN older unsupervised model. This
    learner cannot inspect the correct source, symbol cipher, true positions,
    task rewards or insertion/deletion truth. Replay recomputes fitted scalars.
    """
    def __init__(self,mapping,pairs,*,training_digest):
        self.mapping=_permutation(mapping)
        if (type(training_digest) is not str or len(training_digest)!=64 or
                any(c not in '0123456789abcdef' for c in training_digest) or
                type(pairs) is not list or not 2<=len(pairs)<=120):
            raise ValueError('invalid bounded training configuration')
        self.training_digest=training_digest
        self.pairs=[]
        for pair in pairs:
            if type(pair) is not list or len(pair)!=2:raise ValueError('invalid training example')
            _pair(*pair)
            self.pairs.append([list(pair[0]),list(pair[1])])
        p,s=.75,.70
        for _ in range(ITERATIONS):
            aggregate=[statistics(a,b,self.mapping,p,s) for a,b in self.pairs]
            k=sum(x['expected_matches'] for x in aggregate)
            matching=sum(x['expected_agreements'] for x in aggregate)
            # Two pseudocounts stabilize noisy pseudolabels. Both are priors,
            # not evidence that the true insertion count is observed.
            p=min(.94,max(.52,(matching+2*.75)/(k+2)))
            s=min(.95,max(.4,(k+2*.7*8)/(8*(len(self.pairs)+2))))
        self.match_probability,self.survival=p,s

    def details(self,observed,candidates):
        seqs=_candidates(observed,candidates)
        reports={src:statistics(observed,seq,self.mapping,self.match_probability,self.survival) for src,seq in seqs.items()}
        selected=min(src for src in reports if reports[src]['log_likelihood_ratio']==max(x['log_likelihood_ratio'] for x in reports.values()))
        return {'selected':selected,'reports':reports}

    def select(self,observed,candidates):return self.details(observed,candidates)['selected']

    def record(self):
        state={'schema':SCHEMA,'mapping':list(self.mapping),'training_digest':self.training_digest,
               'pairs':self.pairs,'match_probability':self.match_probability,
               'survival':self.survival,'iterations':ITERATIONS}
        return {'state':json.loads(canonical(state)),'sha256':digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={'state','sha256'} or
                type(record['state']) is not dict or digest(record['state'])!=record['sha256']):
            raise ValueError('invalid checkpoint digest')
        s=record['state']
        if (set(s)!={'schema','mapping','training_digest','pairs','match_probability','survival','iterations'} or
                s['schema']!=SCHEMA or s['iterations']!=ITERATIONS):
            raise ValueError('invalid checkpoint schema')
        rebuilt=cls(s['mapping'],s['pairs'],training_digest=s['training_digest'])
        if rebuilt.record()!=record:raise ValueError('replayed training differs')
        return rebuilt
