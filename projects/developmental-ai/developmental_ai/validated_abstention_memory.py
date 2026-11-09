"""Optional risk-aware action gating using disjoint predictive validation.

The candidate feature program is chosen on evidence EXCLUDING the last
sixteen observations. Only then is the *frozen program choice* evaluated
on the last sixteen outcomes, with per-event predictors fitted solely on
preceding evidence. All three thresholds are engineered and uncalibrated.
This is selective simulation policy, not proof of calibrated safety.
"""
from __future__ import annotations

import json
import math

from developmental_ai.gated_composition_memory import (
    GatedCompositionMemory, _Gate, predictor, branch, MODEL_NAMES,
)
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
from developmental_ai.composed_feature_memory import SOURCE

SCHEMA="developmental-ai.validated-abstention-memory/v1"
SELECTION_WARMUP=240
VALIDATION=16
FIT_WINDOW=64
MIN_GAIN=0.20
MIN_HITS=10
MIN_ACTION_PROGRESS=0.55
MAX_ACTION_DAMAGE=0.18
SMOOTH=0.25


def _null_probability(history,event):
    counts=[
        sum(int(row["progress"]) for row in history),
        sum(int(row["damage"]) for row in history),
        sum(int(not row["progress"] and not row["damage"])
            for row in history),
    ]
    cls=0 if event["progress"] else 1 if event["damage"] else 2
    return (counts[cls]+SMOOTH)/(len(history)+3*SMOOTH)


def _candidate(names,is_conditional,history,archive):
    if is_conditional:
        arms=[]
        for side,name in enumerate(names):
            arm=[row for row in history if branch(row["features"])==side]
            arms.append(archive if name==MODEL_NAMES[0] else
                        predictor(MODEL_NAMES.index(name),arm))
        return _Gate(*arms)
    name=names[0]
    return archive if name==MODEL_NAMES[0] else predictor(
        MODEL_NAMES.index(name),history)


def _probabilities(model,features):
    if isinstance(model,_Gate):
        return model.branches[branch(features)].estimate(features)
    return model.estimate(features)


class ValidatedAbstainingMemory(GatedCompositionMemory):
    """Reject poor predictive models and low-confidence action candidates."""

    def selection(self):
        if self._cache is not None:
            return self._cache
        if len(self.events)<SELECTION_WARMUP:
            raise ValueError("insufficient public source training")
        cutoff=len(self.events)-VALIDATION
        prior=self.events[:cutoff]
        archive=predictor(0,self.events[:SOURCE])
        # Do not let validation outcomes influence *which program* is tested.
        if len(prior)<SELECTION_WARMUP:
            names=(MODEL_NAMES[0],)
            is_conditional=False
            selection_kind="warmup_source"
        else:
            selector=GatedCompositionMemory()
            for observation in prior:
                selector.observe(observation)
            choice=selector.selection()[0]
            is_conditional=choice["selected"]=="conditional"
            names=(tuple(choice["conditional_names"]) if is_conditional else
                   (choice["global_name"],))
            selection_kind=choice["selected"]
        improvement=0.0
        correct=0
        for idx in range(cutoff,len(self.events)):
            previous=self.events[max(0,idx-FIT_WINDOW):idx]
            event=self.events[idx]
            model=_candidate(names,is_conditional,previous,archive)
            ps=_probabilities(model,event["features"])
            actual=0 if event["progress"] else 1 if event["damage"] else 2
            p=ps[actual]
            p_null=_null_probability(previous,event)
            if p<=0 or p_null<=0 or not math.isfinite(p):
                raise ValueError("invalid validation likelihood")
            improvement+=math.log(p)-math.log(p_null)
            correct+=int(max(range(3),key=lambda k:ps[k])==actual)
        mean_gain=improvement/VALIDATION
        adequate=(mean_gain>=MIN_GAIN and correct>=MIN_HITS)
        fitted=_candidate(names,is_conditional,self.events[-FIT_WINDOW:],archive)
        decision={
            "selected_kind":selection_kind,
            "validated_names":list(names),
            "source_retained":True,
            "selection_training_excludes_validation":True,
            "validation_examples":VALIDATION,
            "validation_fit_overlap":0,
            "mean_gain_over_null":round(mean_gain,6),
            "class_accuracy_count":correct,
            "meets_adequacy_gate":adequate,
            "recorded_events":len(self.events),
        }
        self._cache=(decision,fitted)
        return self._cache

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        if any(set(row["features"])!=set(self.events[0]["features"])
               for row in frame["actions"]):
            raise ValueError("unknown action sensor schema")
        decision,model=self.selection()
        if not decision["meets_adequacy_gate"]:
            return None
        ranked=[]
        for action in frame["actions"]:
            p,d,_=_probabilities(model,action["features"])
            if p>=MIN_ACTION_PROGRESS and d<=MAX_ACTION_DAMAGE:
                ranked.append((-(3*p-10*d),action["id"]))
        return min(ranked)[1] if ranked else None

    def record(self):
        if not self.events:
            raise ValueError("untrained adequate-risk model")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
                or type(record["state"]) is not dict or
                type(record["sha256"]) is not str or
                digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid selective model checkpoint hash")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA
                or type(state["events"]) is not list or
                not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid selective checkpoint structure")
        model=cls()
        for row in state["events"]:
            model.observe(row)
        if model.record()!=record:
            raise ValueError("selective checkpoint replay mismatch")
        return model
