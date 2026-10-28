"""Absolute predictive adequacy vs relative preference for two known laws.

The source/reversed numeric models are already trained before calibration.
This gate is offline only and does not discover the third law. All probes
may incur simulated harm; rejection counts as task failure.
"""
from __future__ import annotations

import json
import math

from developmental_ai.observable_affordances import canonical,digest
from developmental_ai.observable_reversal_calibration import (
    OutcomeCalibration,probabilities,evidence_category
)
from developmental_ai.two_window_confirmation import TwoWindowConfirmation,window_prediction

SCHEMA="developmental-ai.absolute-adequacy-gate/v1"
WINDOW=4
MAX_MEAN_NLL=1.2
MIN_MARGIN=2.0
METHODS=("adequacy8","relative8","recent8")


def inspect_window(agent,rows):
    if len(rows)!=WINDOW:
        raise ValueError("exactly four observed outcomes required")
    scores={}
    for label,model in agent.models.items():
        scores[label]=sum(math.log(probabilities(model,event["event"]["features"])[
            evidence_category(event["event"])]) for event in rows)
    most=max(scores,key=lambda k:(scores[k],k))
    nll=-scores[most]/WINDOW
    difference=abs(scores["source"]-scores["changed"])
    if nll>MAX_MEAN_NLL:
        choice="unknown"
    elif difference<MIN_MARGIN:
        choice="abstain"
    else:
        choice=most
    return {"choice":choice,"nll":round(nll,6),
            "margin":round(difference,6),"samples":WINDOW}


class AbsoluteAdequacy:
    def __init__(self,source,changed):
        self.agent=TwoWindowConfirmation(source,changed)

    def probe(self,frame):
        return self.agent.choose(frame)

    def observe(self,before,action,after):
        return self.agent.feedback(before,action,after)

    def decision(self,method):
        if method not in METHODS or len(self.agent.agent.events)!=2*WINDOW:
            raise ValueError("invalid or incomplete known-law comparison")
        events=self.agent.agent.events
        first=inspect_window(self.agent.agent,events[:WINDOW])
        recent=inspect_window(self.agent.agent,events[WINDOW:])
        if method=="relative8":
            selected=self.agent.decision("confirmed8")["choice"]
        elif method=="recent8":
            selected=self.agent.decision("recent8")["choice"]
        else:
            if "unknown" in (first["choice"],recent["choice"]):
                selected="unknown"
            elif first["choice"]==recent["choice"]:
                selected=first["choice"]
            else:
                selected="abstain"
        return {"selected":selected,"first":first,"recent":recent,
                "conflict":first["choice"]!=recent["choice"]}

    def record(self,method):
        selected=self.decision(method)
        state={"schema":SCHEMA,"method":method,
               "evidence":self.agent.agent.record(),
               "decision":selected}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,source,changed,saved):
        if (type(saved) is not dict or set(saved)!={"state","sha256"}
            or type(saved["state"]) is not dict
            or saved["sha256"]!=digest(saved["state"])):
            raise ValueError("bad adequacy checkpoint digest")
        state=saved["state"]
        if (set(state)!={"schema","method","evidence","decision"}
            or state["schema"]!=SCHEMA or state["method"] not in METHODS):
            raise ValueError("bad adequacy checkpoint structure")
        restored=cls(source,changed)
        restored.agent.agent=OutcomeCalibration.restore(
            source,changed,state["evidence"])
        if restored.record(state["method"])!=saved:
            raise ValueError("adequacy decision did not replay")
        return restored
