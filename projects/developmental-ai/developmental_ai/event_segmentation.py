"""Observation-only, four-state event-boundary learning (optional D3 experiment).

An explicit four-state sticky categorical HMM is fitted by Baum-Welch from
unlabelled, bounded raw token streams. No ground-truth boundaries, task rewards,
or simulator internals enter fitting. Viterbi paths are read-only guesses. The
longest inferred span is an *engineered task-specific retrieval rule*.
"""
from __future__ import annotations

import json
import math
from developmental_ai.environment_api import canonical, digest

SCHEMA = "developmental-ai.event-segmentation/v1"
SESSION_SCHEMA = "developmental-ai.event-span-memory/v1"
ALPHABET = 4
MAX_LENGTH = 128
MAX_TRAIN = 300
ITERATIONS = 5
INIT_P, INIT_Q = 0.78, 0.72
PSEUDOCOUNT = 2.0


def check_stream(stream, *, min_length=2):
    if (type(stream) is not list or not min_length <= len(stream) <= MAX_LENGTH or
            any(type(x) is not int or x not in range(ALPHABET) for x in stream)):
        raise ValueError("expected bounded raw symbol sequence without hidden fields")


def _t(p, i, j):
    return p if i == j else (1.0-p)/3


def _e(q, state, observation):
    return q if state == observation else (1.0-q)/3


def _posterior(stream, p, q):
    """Scaled forward/backward with exact soft stay and emission counts."""
    n = len(stream)
    transition = [[_t(p,i,j) for j in range(4)] for i in range(4)]
    emission = [[_e(q,s,x) for s in range(4)] for x in stream]
    alpha = [[0.] * 4 for _ in range(n)]
    scales = [0.] * n
    for i in range(n):
        for s in range(4):
            alpha[i][s] = emission[i][s] * (0.25 if i == 0 else sum(
                alpha[i-1][a] * transition[a][s] for a in range(4)))
        scales[i] = sum(alpha[i])
        if not scales[i] > 0 or not math.isfinite(scales[i]):
            raise ValueError("invalid scaled HMM likelihood")
        alpha[i] = [a / scales[i] for a in alpha[i]]
    beta = [[1.] * 4 for _ in range(n)]
    for i in range(n - 2, -1, -1):
        beta[i] = [sum(transition[a][b] * emission[i+1][b] * beta[i+1][b]
                        for b in range(4)) / scales[i+1] for a in range(4)]
    emission_agreement, total_stays = 0., 0.
    for i in range(n):
        gamma = [alpha[i][s]*beta[i][s] for s in range(4)]
        mass = sum(gamma)
        emission_agreement += gamma[stream[i]] / mass
        if i < n - 1:
            edges = [[alpha[i][a] * transition[a][b] * emission[i+1][b] *
                      beta[i+1][b] / scales[i+1] for b in range(4)] for a in range(4)]
            z = sum(sum(row) for row in edges)
            total_stays += sum(edges[s][s] for s in range(4)) / z
    return emission_agreement, total_stays, sum(math.log(x) for x in scales)


def fit_event_model(streams, *, iterations=ITERATIONS):
    """Fit only raw training histories; fixed architecture and EM budget."""
    if (type(streams) is not list or not 2 <= len(streams) <= MAX_TRAIN or
            type(iterations) is not int or iterations != ITERATIONS):
        raise ValueError("invalid fit budget")
    for stream in streams:
        check_stream(stream)
    data = json.loads(canonical(streams))
    p, q = INIT_P, INIT_Q
    for _ in range(iterations):
        agreements, stays = 0., 0.
        for stream in data:
            a,b,_ = _posterior(stream,p,q)
            agreements += a
            stays += b
        ticks = sum(len(s) for s in data)
        p = max(.5, min(.985,(stays + PSEUDOCOUNT*INIT_P)/(ticks-len(data)+PSEUDOCOUNT)))
        q = max(.52,min(.98,(agreements+PSEUDOCOUNT*INIT_Q)/(ticks+PSEUDOCOUNT)))
    return EventSegmentationModel(data, p, q)


class EventSegmentationModel:
    def __init__(self, training, persistence, sensor_accuracy):
        if (type(training) is not list or not 2 <= len(training) <= MAX_TRAIN or
                any(type(s) is not list for s in training) or
                type(persistence) is not float or not .5 <= persistence <= .985 or
                type(sensor_accuracy) is not float or not .52 <= sensor_accuracy <= .98 or
                not all(math.isfinite(x) for x in (persistence,sensor_accuracy))):
            raise ValueError("invalid learned model")
        for s in training:check_stream(s)
        self.training=json.loads(canonical(training))
        self.persistence=persistence
        self.sensor_accuracy=sensor_accuracy

    def decode(self, stream):
        check_stream(stream, min_length=1)
        p,q=self.persistence,self.sensor_accuracy
        scores=[math.log(.25)+math.log(_e(q,k,stream[0])) for k in range(4)]
        back=[]
        for x in stream[1:]:
            prev=[];new=[]
            for state in range(4):
                opts=[scores[old]+math.log(_t(p,old,state)) for old in range(4)]
                prior=max(range(4),key=lambda k:(opts[k],-k))
                new.append(opts[prior]+math.log(_e(q,state,x)))
                prev.append(prior)
            scores=new;back.append(prev)
        state=max(range(4),key=lambda k:(scores[k],-k))
        path=[state]
        for prev in reversed(back):
            path.append(prev[path[-1]])
        path.reverse()
        return path

    def spans(self, stream):
        decoded=self.decode(stream)
        out=[];start=0
        for i in range(1,len(decoded)+1):
            if i == len(decoded) or decoded[i]!=decoded[i-1]:
                out.append({"start":start,"end":i,"label":decoded[start]})
                start=i
        return out

    def recall(self, stream):
        spans=self.spans(stream)
        winner=max(spans,key=lambda s:(s["end"]-s["start"],-s["start"],-s["label"]))
        return winner["label"]

    def record(self):
        state={"schema":SCHEMA,"iterations":ITERATIONS,"training":self.training,
               "persistence":self.persistence,"sensor_accuracy":self.sensor_accuracy}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
                type(record["state"]) is not dict or type(record["sha256"]) is not str or
                digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid model checkpoint")
        data=record["state"]
        if (set(data)!={"schema","iterations","training","persistence","sensor_accuracy"} or
                data["schema"]!=SCHEMA or data["iterations"]!=ITERATIONS):
            raise ValueError("unknown segmentation schema")
        restored=fit_event_model(data["training"])
        if restored.record()!=record:
            raise ValueError("checkpoint parameters inconsistent with raw training replay")
        return restored


class EventSpanMemory:
    """Incremental read-only observation memory with replay-checked recovery."""
    def __init__(self, model):
        if not isinstance(model,EventSegmentationModel):
            raise ValueError("segmentation model required")
        self.model=EventSegmentationModel.restore(model.record())
        self.model_digest=self.model.record()["sha256"]
        self.tokens=[]

    def observe(self,token):
        if self.model.record()["sha256"] != self.model_digest:
            raise ValueError("learned model changed during observation session")
        if (type(token) is not int or token not in range(4) or len(self.tokens)>=MAX_LENGTH):
            raise ValueError("invalid or exhausted raw observation")
        self.tokens.append(token)
        return {"step":len(self.tokens),"latest_event":self.model.decode(self.tokens)[-1],
                "retained_event":self.model.recall(self.tokens),"span_count":len(self.model.spans(self.tokens))}

    def snapshot(self):
        if self.model.record()["sha256"] != self.model_digest:
            raise ValueError("learned model changed during observation session")
        state={"schema":SESSION_SCHEMA,"model_sha256":self.model_digest,"tokens":self.tokens,
               "spans":self.model.spans(self.tokens) if self.tokens else [],
               "retained":self.model.recall(self.tokens) if self.tokens else None}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls, record,model):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
                type(record["state"]) is not dict or digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid event memory snapshot")
        s=record["state"]
        if set(s)!={"schema","model_sha256","tokens","spans","retained"} or s["schema"]!=SESSION_SCHEMA:
            raise ValueError("incompatible event memory snapshot")
        restored=cls(model)
        if s["model_sha256"]!=restored.model_digest or type(s["tokens"]) is not list:
            raise ValueError("wrong learned model or observation log")
        for token in s["tokens"]:
            restored.observe(token)
        if restored.snapshot()!=record:
            raise ValueError("replayed memory state differs from checkpoint")
        return restored
