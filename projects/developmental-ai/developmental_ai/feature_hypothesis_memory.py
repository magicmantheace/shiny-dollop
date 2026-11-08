"""Replayable selection among deliberately supplied numeric feature hypotheses.

Four hypotheses are prewritten by the developer. The learner estimates
category frequencies for each transform and selects by true prequential
prediction-before-update likelihood on last eight PUBLIC outcomes.
Neither task labels, physics parameters, privileged oracle nor simulator
state enter the evidence. This is not creation of causal laws.
"""
from __future__ import annotations

import json
import math

from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory

SCHEMA="developmental-ai.cross-rule-feature-hypothesis/v1"
FEATURES=("span","checksum","ordered")
CANDIDATES=("frozen_source_span","recent_span","recent_checksum","recent_ordered")
SOURCE=192
WARMUP=240
RECENT=24
TAIL=8
ALPHA=0.25


def feature_bucket(features,which):
    if type(features) is not dict or len(features)!=2:
        raise ValueError("requires exactly two validated numeric feature keys")
    a,b=(features[k] for k in sorted(features))
    if which=="span":
        return abs(a-b)
    if which=="checksum":
        return (2*a+b)%5
    if which=="ordered":
        return (a+3*b)%7
    raise ValueError("unregistered feature hypothesis")


class _Bucket:
    """Outcome probabilities conditioned on a registered feature transform."""

    def __init__(self,which,rows):
        if which not in FEATURES:
            raise ValueError("unknown feature transform")
        self.which=which
        self.counts=[[0,0,0] for _ in range(
            10 if which=="span" else 5 if which=="checksum" else 7)]
        for row in rows:
            bucket=feature_bucket(row["features"],which)
            label=0 if row["progress"] else 1 if row["damage"] else 2
            self.counts[bucket][label]+=1

    def estimate(self,features):
        counts=self.counts[feature_bucket(features,self.which)]
        total=sum(counts)+3*ALPHA
        return ((counts[0]+ALPHA)/total,
                (counts[1]+ALPHA)/total,
                (counts[2]+ALPHA)/total)

    def probability(self,event):
        vec=self.estimate(event["features"])
        return vec[0 if event["progress"] else 1 if event["damage"] else 2]

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        ranks=[]
        for action in frame["actions"]:
            p,d,_=self.estimate(action["features"])
            ranks.append((-(3*p-10*d),action["id"]))
        return min(ranks)[1] if ranks else None


class FeatureHypothesisMemory:
    def __init__(self):
        self.events=[]
        self._cache=None

    def observe(self,event):
        if len(self.events)>=MAX_SAMPLES:
            raise ValueError("feature hypothesis evidence cap reached")
        verifier=RelationOutcomeMemory()
        verifier.observe(event)
        item=verifier.events[0]
        if len(item["features"])!=2 or (
                self.events and set(item["features"])!=set(self.events[0]["features"])):
            raise ValueError("new sensor keys not allowed in same-schema study")
        self.events.append(item)
        self._cache=None

    def selection(self):
        if self._cache is not None:
            return self._cache
        if len(self.events)<WARMUP:
            raise ValueError("not enough public source observations")
        source=_Bucket("span",self.events[:SOURCE])
        scoring=[0.0]*len(CANDIDATES)
        for i in range(len(self.events)-TAIL,len(self.events)):
            event=self.events[i]
            past=self.events[max(0,i-RECENT):i]
            predictors=(source,_Bucket("span",past),
                        _Bucket("checksum",past),_Bucket("ordered",past))
            for idx,model in enumerate(predictors):
                likelihood=model.probability(event)
                if likelihood<=0 or not math.isfinite(likelihood):
                    raise ValueError("invalid predictive probability")
                scoring[idx]+=math.log(likelihood)
        # First registered candidate wins exact predictive ties.
        selected=max(range(len(CANDIDATES)),key=lambda j:scoring[j])
        if selected==0:
            chosen=source
        else:
            chosen=_Bucket(FEATURES[selected-1],self.events[-RECENT:])
        summary={
            "selected":CANDIDATES[selected],
            "prequential_log_scores":[round(v,6) for v in scoring],
            "scoring_events":TAIL,
            "scored_event_fit_overlap":0,
            "decision_fit_events":SOURCE if selected==0 else RECENT,
            "source_archive_retained":True,
            "recorded_events":len(self.events),
        }
        self._cache=(summary,chosen)
        return self._cache

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        if any(set(action["features"])!=set(self.events[0]["features"])
               for action in frame["actions"]):
            raise ValueError("public action features differ from observed schema")
        _,predictor=self.selection()
        return predictor.choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("empty public feature memory")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
                or type(record["state"]) is not dict or
                type(record["sha256"]) is not str or
                digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid feature memory checkpoint")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA
                or type(state["events"]) is not list or
                not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid public evidence structure")
        m=cls()
        for item in state["events"]:
            m.observe(item)
        if m.record()!=record:
            raise ValueError("feature memory replay mismatch")
        return m
