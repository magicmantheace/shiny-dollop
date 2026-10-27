"""Prequential mixture of remembered relation models; simulator-only.

Predictive candidate weight is computed from actual *past* feedback using
models fitted strictly before the scored event. No feedback is used to fit
its own prequential predictor. Decision-time models may learn from all
currently observed feedback (normal online learning). No stage or hidden
physics enters; numeric range representation, priors and mixture are
handcrafted, not independent discovery or provenance attestation.
"""
from __future__ import annotations

import json
import math

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    VariableOutcomeMemory, MAX_SAMPLES, canonical, digest,
)

SCHEMA="developmental-ai.stochastic-prequential-mixture/v1"
SOURCE=192
WARMUP=240
VALIDATION=8
WINDOWS=(8,32)
PRIOR=(-0.4,0.0,0.2)
TEMPERATURE=2.0


class PrequentialEnsembleMemory(FastShockMemory):
    """Replayable mixture of fixed early skill, near-term and recent history."""

    def __init__(self):
        super().__init__()
        self._cache=None

    def observe(self,event):
        super().observe(event)
        self._cache=None

    @staticmethod
    def _observed_likelihood(model,event):
        probs=model.estimate(event["features"])
        if event["progress"]:
            return probs["progress"]
        if event["damage"]:
            return probs["damage"]
        return 1.0-probs["progress"]-probs["damage"]

    def selection(self):
        if self._cache is not None:
            return self._cache
        if len(self.events)<WARMUP:
            raise ValueError("needs source public evidence")
        early=self._model(self.events[:SOURCE])
        score=[0.0,0.0,0.0]
        heldout_indices=list(range(max(SOURCE+32,len(self.events)-VALIDATION),
                                   len(self.events)))
        if len(heldout_indices)!=VALIDATION:
            raise AssertionError("invalid prequential comparison length")
        for idx in heldout_indices:
            ev=self.events[idx]
            candidate_models=(
                early,
                self._model(self.events[idx-WINDOWS[0]:idx]),
                self._model(self.events[idx-WINDOWS[1]:idx]),
            )
            for j,model in enumerate(candidate_models):
                p=self._observed_likelihood(model,ev)
                if p<=0.0 or not math.isfinite(p):
                    raise ValueError("invalid prequential likelihood")
                score[j]+=math.log(p)
        logits=[(score[i]+PRIOR[i])/TEMPERATURE for i in range(3)]
        offset=max(logits)
        exp=[math.exp(value-offset) for value in logits]
        total=sum(exp)
        weights=[value/total for value in exp]
        live=(early,
              self._model(self.events[-WINDOWS[0]:]),
              self._model(self.events[-WINDOWS[1]:]))
        report={
            "candidates":["source192","recent8","recent32"],
            "predictive_scoring_events":VALIDATION,
            "scoring_fit_overlap":0,
            "scores":[round(s,6) for s in score],
            "weights":[round(w,6) for w in weights],
            "highest_weight":("source192","recent8","recent32")[weights.index(max(weights))],
            "trained_events":len(self.events),
            "source_retained":True,
        }
        self._cache=(report,weights,live)
        return self._cache

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        _,weights,models=self.selection()
        scored=[]
        for action in frame["actions"]:
            probabilities=[m.estimate(action["features"]) for m in models]
            progress=sum(w*p["progress"] for w,p in zip(weights,probabilities))
            harm=sum(w*p["damage"] for w,p in zip(weights,probabilities))
            scored.append((-(3.0*progress-10.0*harm),action["id"]))
        return min(scored)[1] if scored else None

    def record(self):
        if not self.events:
            raise ValueError("no prequential public evidence")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid prequential checkpoint hash")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA
                or type(state["events"]) is not list
                or not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid prequential checkpoint structure")
        m=cls()
        for event in state["events"]:
            m.observe(event)
        if m.record()!=record:
            raise ValueError("prequential checkpoint fails public replay")
        return m
