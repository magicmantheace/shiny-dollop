"""Replayable first-versus-recent public outcome confirmation experiment.

Only numeric public features and observed sensor deltas are read by
this optional offline selector. Two candidate models already exist.
A disagreement is uncertainty, NOT causally verified regime drift.
"""
from __future__ import annotations

import json
import math

from developmental_ai.observable_affordances import canonical, digest
from developmental_ai.observable_reversal_calibration import (
    OutcomeCalibration, probabilities, evidence_category, MIN_MARGIN
)

SCHEMA="developmental-ai.two-window-confirmation/v1"
WINDOW=4
MAX_OBS=8
METHODS=("early4","confirmed8","recent8","cumulative8")


def window_prediction(agent, events):
    if not isinstance(agent,OutcomeCalibration) or type(events) not in (list,tuple):
        raise ValueError("requires a trained public evidence model and sample window")
    if len(events)<WINDOW:
        return {"choice":"abstain","margin":0.0,"samples":len(events)}
    scores={}
    for name,model in agent.models.items():
        scores[name]=sum(math.log(probabilities(model,row["event"]["features"])[
            evidence_category(row["event"])]) for row in events)
    gap=abs(scores["source"]-scores["changed"])
    choice=(max(scores,key=lambda k:(scores[k],k)) if gap>=MIN_MARGIN
            else "abstain")
    return {"choice":choice,"margin":round(gap,5),"samples":len(events)}


class TwoWindowConfirmation:
    def __init__(self, source, changed):
        self.agent=OutcomeCalibration(source,changed)

    def choose(self, public_frame):
        return self.agent.probe(public_frame)

    def feedback(self,before,action,after):
        if len(self.agent.events)>=MAX_OBS:
            raise ValueError("confirmation evidence limit exceeded")
        return self.agent.observe(before,action,after)

    def decision(self,method):
        if method not in METHODS:
            raise ValueError("unknown confirmation policy")
        events=self.agent.events
        required=WINDOW if method=="early4" else MAX_OBS
        if len(events)!=required:
            raise ValueError("incomplete or extra public calibration evidence")
        first=window_prediction(self.agent,events[:WINDOW])
        if method=="early4":
            return {"choice":first["choice"],"first":first,
                    "recent":None,"samples":len(events),
                    "contradiction":False}
        last=window_prediction(self.agent,events[WINDOW:MAX_OBS])
        whole=window_prediction(self.agent,events)
        contradiction=(first["choice"]!=last["choice"] and
                       first["choice"]!="abstain" and last["choice"]!="abstain")
        if method=="confirmed8":
            choice=(first["choice"] if first["choice"]==last["choice"]
                    else "abstain")
        elif method=="recent8":
            choice=last["choice"]
        else:
            choice=whole["choice"]
        return {"choice":choice,"first":first,"recent":last,
                "samples":len(events),"contradiction":contradiction}

    def record(self,method):
        selected=self.decision(method)
        state={"schema":SCHEMA,"method":method,
               "calibration":self.agent.record(),
               "decision":selected}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,source,changed,record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
            type(record["state"]) is not dict or
            record["sha256"]!=digest(record["state"])):
            raise ValueError("invalid confirmation receipt")
        state=record["state"]
        if (set(state)!={"schema","method","calibration","decision"} or
            state["schema"]!=SCHEMA or state["method"] not in METHODS):
            raise ValueError("invalid confirmation state")
        obj=cls(source,changed)
        obj.agent=OutcomeCalibration.restore(source,changed,state["calibration"])
        if obj.record(state["method"])!=record:
            raise ValueError("selection diverges after public evidence replay")
        return obj
