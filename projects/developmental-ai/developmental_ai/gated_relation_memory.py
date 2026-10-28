"""Predictive, replayable source-vs-new-schema relation selection.

An independent four-observation validation tail decides whether a target-only
model (trained on earlier target observations) predicts recent outcomes
better than the inherited source model. Original evidence is never erased.
Exact feature-key signatures are engineered; this is not true domain
discovery, provenance verification, or a safety guarantee.
"""
from __future__ import annotations

import json
import math

from developmental_ai.observable_affordances import (
    VariableOutcomeMemory, MAX_SAMPLES, canonical, digest, variable_feature_check,
)
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory

SCHEMA="developmental-ai.gated-relation-outcomes/v1"
TAIL=4
MIN_TARGET=8


class GatedRelationMemory:
    def __init__(self):
        self.events=[]

    def observe(self,event):
        if len(self.events) >= MAX_SAMPLES:
            raise ValueError("bounded relation experience exceeded")
        probe=RelationOutcomeMemory()
        probe.observe(event)
        self.events.append(probe.events[0])

    @staticmethod
    def signature(features):
        variable_feature_check(features)
        return tuple(sorted(features))

    @staticmethod
    def model(rows):
        m=RelationOutcomeMemory()
        for row in rows:
            m.observe(row)
        return m

    @staticmethod
    def log_evidence(model,events):
        total=0.0
        for row in events:
            estimate=model.estimate(row["features"])
            key="progress" if row["progress"] else "damage" if row["damage"] else None
            p=estimate[key] if key is not None else (
                1.0-estimate["progress"]-estimate["damage"])
            if p<=0 or not math.isfinite(p):
                raise ValueError("invalid conditional feedback likelihood")
            total+=math.log(p)
        return total

    def selection(self,features):
        if not self.events:
            raise ValueError("untrained relation source")
        signature=self.signature(features)
        original=self.signature(self.events[0]["features"])
        old=[row for row in self.events
             if self.signature(row["features"])==original]
        if not old:
            raise AssertionError("empty source")
        source=self.model(old)
        if signature==original:
            return {"source":"source","target_observations":0,
                    "validation_events":0,"log_margin":0.0},source
        target=[row for row in self.events
                if self.signature(row["features"])==signature]
        if len(target)<MIN_TARGET:
            return {"source":"source","target_observations":len(target),
                    "validation_events":0,"log_margin":0.0},source
        fit=self.model(target[:-TAIL])
        tail=target[-TAIL:]
        delta=self.log_evidence(fit,tail)-self.log_evidence(source,tail)
        if delta>0:
            return {"source":"target","target_observations":len(target),
                    "validation_events":TAIL,"log_margin":round(delta,6)},fit
        return {"source":"source","target_observations":len(target),
                "validation_events":TAIL,"log_margin":round(delta,6)},source

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        # Reject mixed signatures in the same frame, avoiding an
        # implicit handcrafted per-action model selection shortcut.
        signatures={self.signature(a["features"]) for a in frame["actions"]}
        if len(signatures)!=1:
            raise ValueError("mixed unknown schema in action frame")
        _,model=self.selection(frame["actions"][0]["features"])
        return model.choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("no source learning evidence")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
            type(record["state"]) is not dict or
            type(record["sha256"]) is not str or
            digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid gate checkpoint hash")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA or
            type(state["events"]) is not list or
            not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid gate checkpoint structure")
        m=cls()
        for event in state["events"]:
            m.observe(event)
        if m.record()!=record:
            raise ValueError("cannot replay gated relation evidence")
        return m
