"""Opt-in prequential selection of conditional arithmetic feature programs.

Grammar extension: combine one generic comparison (first public integer
greater than second) with two separately trained and selected existing
feature programs. XOR is NOT in this grammar. Human-written operators and
multiple-hypothesis search remain priors, not independent science.
"""
from __future__ import annotations

import json
import math

from developmental_ai.composed_feature_memory import (
    ComposedFeatureMemory, PROGRAMS, MODEL_NAMES,
    _ComposedBucket, SOURCE, ALPHA,
)
from developmental_ai.feature_hypothesis_memory import _Bucket
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)

SCHEMA="developmental-ai.gated-composition-memory/v1"
TAIL=16
FIT_WINDOW=64
GATE_PENALTY=2.0
MIN_SCORED_PER_BRANCH=3


def branch(features):
    vals=[features[k] for k in sorted(features)]
    return int(vals[0]>vals[1])


def predictor(index,events):
    if index<0 or index>=len(MODEL_NAMES):
        raise ValueError("unregistered arithmetic hypothesis")
    if index in (0,1):
        return _Bucket("span",events)
    if index==2:
        return _Bucket("checksum",events)
    if index==3:
        return _Bucket("ordered",events)
    return _ComposedBucket(PROGRAMS[index-4],events)


class _Gate:
    def __init__(self,low,high):
        self.branches=(low,high)

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        ranks=[]
        for item in frame["actions"]:
            p,d,_=self.branches[branch(item["features"])].estimate(item["features"])
            ranks.append((-(3*p-10*d),item["id"]))
        return min(ranks)[1] if ranks else None


class GatedCompositionMemory(ComposedFeatureMemory):
    """Choose old global or new two-arm conditional program by past evidence."""

    def selection(self):
        if self._cache is not None:
            return self._cache
        if len(self.events)<240:
            raise ValueError("insufficient observed source training")
        anchor=predictor(0,self.events[:SOURCE])
        global_scores=[0.0]*len(MODEL_NAMES)
        branch_scores=[[0.0]*len(MODEL_NAMES) for _ in range(2)]
        counts=[0,0]
        for i in range(len(self.events)-TAIL,len(self.events)):
            event=self.events[i]
            prior=self.events[max(0,i-FIT_WINDOW):i]
            side=branch(event["features"])
            counts[side]+=1
            arm=[r for r in prior if branch(r["features"])==side]
            for j in range(len(MODEL_NAMES)):
                global_model=(anchor if j==0 else predictor(j,prior))
                branch_model=(anchor if j==0 else predictor(j,arm))
                pg=global_model.probability(event)
                pb=branch_model.probability(event)
                if min(pg,pb)<=0 or not math.isfinite(pg) or not math.isfinite(pb):
                    raise ValueError("nonpositive/invalid prequential probability")
                global_scores[j]+=math.log(pg)
                branch_scores[side][j]+=math.log(pb)
        best_global=max(range(len(MODEL_NAMES)),key=lambda j:global_scores[j])
        best_arms=[max(range(len(MODEL_NAMES)),
                       key=lambda j:branch_scores[side][j])
                   for side in range(2)]
        best_conditional=sum(branch_scores[side][best_arms[side]]
                             for side in range(2))-GATE_PENALTY
        use_conditional=(min(counts)>=MIN_SCORED_PER_BRANCH and
                         best_conditional>global_scores[best_global])
        recent=self.events[-FIT_WINDOW:]
        if use_conditional:
            selected_models=[]
            for side,j in enumerate(best_arms):
                arm=[r for r in recent if branch(r["features"])==side]
                selected_models.append(anchor if j==0 else predictor(j,arm))
            actor=_Gate(*selected_models)
        else:
            actor=(anchor if best_global==0 else predictor(best_global,recent))
        report={
            "selected":"conditional" if use_conditional else "global",
            "global_name":MODEL_NAMES[best_global],
            "conditional_names":[MODEL_NAMES[x] for x in best_arms],
            "branch_scoring_counts":counts,
            "global_prequential":round(global_scores[best_global],6),
            "conditional_penalized_prequential":round(best_conditional,6),
            "scoring_examples":TAIL,
            "scored_event_fit_overlap":0,
            "generated_programs":len(PROGRAMS),
            "source_retained":True,
            "recorded_events":len(self.events),
        }
        self._cache=report,actor
        return self._cache

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        if any(set(a["features"])!=set(self.events[0]["features"])
               for a in frame["actions"]):
            raise ValueError("unknown public action sensors")
        return self.selection()[1].choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("empty gated memory")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
                or type(record["state"]) is not dict or
                type(record["sha256"]) is not str or
                digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid gated memory hash")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA or
                type(state["events"]) is not list or
                not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid gated memory structure")
        result=cls()
        for item in state["events"]:
            result.observe(item)
        if result.record()!=record:
            raise ValueError("gated memory replay failed")
        return result
