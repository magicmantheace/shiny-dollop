"""Offline, public-outcome-only selection between normal and reversed models.

The two separately trained numeric-feature models exist BEFORE calibration.
A disposable simulator supplies one observed action outcome per independent
calibration episode. That action may cause irreversible simulated damage.
This does not establish safe real-world interventions or novel-rule discovery.
"""
from __future__ import annotations

import json
import math

from developmental_ai.observable_affordances import (
    NumericOutcomeMemory, check, outcome, canonical, digest,
)

SCHEMA = "developmental-ai.observable-reversal-calibration/v1"
PROBES = 12
MIN_PROBES = 4
MIN_MARGIN = 2.0
SMOOTHING = 0.05


def probabilities(model, features):
    if not isinstance(model, NumericOutcomeMemory) or not model.examples:
        raise ValueError("trained public outcome memory required")
    pred = model.estimate(features)
    progress, damage = pred["progress"], pred["damage"]
    if not all(type(x) is float and math.isfinite(x) and 0 <= x <= 1
               for x in (progress, damage)) or progress+damage>1.000001:
        raise ValueError("invalid probabilistic sensor prediction")
    raw = (progress+SMOOTHING, damage+SMOOTHING,
           max(0.0,1-progress-damage)+SMOOTHING)
    denom = sum(raw)
    return tuple(v/denom for v in raw)


def evidence_category(event):
    return 0 if event["progress"] else 1 if event["damage"] else 2


class OutcomeCalibration:
    """Paired source/changed hypotheses, no domain labels in observations."""

    def __init__(self, source, changed):
        if (not isinstance(source,NumericOutcomeMemory) or
            not isinstance(changed,NumericOutcomeMemory) or
            not source.examples or not changed.examples):
            raise ValueError("two trained memories required")
        self.models={"source":NumericOutcomeMemory.restore(source.record()),
                     "changed":NumericOutcomeMemory.restore(changed.record())}
        self.fingerprints={k:v.record()["sha256"] for k,v in self.models.items()}
        self.events=[]

    def probe(self, frame):
        check(frame)
        if frame["tick"]!=0 or frame["done"] or len(self.events)>=PROBES:
            raise ValueError("invalid offline probe frame")
        if any(e["episode"]==frame["episode"] for e in self.events):
            raise ValueError("reuse of a calibration episode")
        # Maximize total-variation distance of the two *learned*
        # predictive distributions. This does not consult hidden physics.
        ranked=[]
        for row in frame["actions"]:
            a=probabilities(self.models["source"],row["features"])
            b=probabilities(self.models["changed"],row["features"])
            gap=sum(abs(x-y) for x,y in zip(a,b))/2
            ranked.append((-gap,row["id"]))
        return min(ranked)[1] if ranked else None

    def observe(self,before,action,after):
        expected=self.probe(before)
        if expected is None or action!=expected:
            raise ValueError("observed action differs from public probe")
        event=outcome(before,action,after)
        self.events.append({
            "episode":before["episode"],
            "before":json.loads(canonical(before)),
            "action":action,
            "after":json.loads(canonical(after)),
            "event":event,
        })
        return event

    def decision(self):
        scores={"source":0.0,"changed":0.0}
        for row in self.events:
            category=evidence_category(row["event"])
            for name,model in self.models.items():
                probs=probabilities(model,row["event"]["features"])
                scores[name]+=math.log(probs[category])
        margin=abs(scores["source"]-scores["changed"])
        if len(self.events)<MIN_PROBES or margin<MIN_MARGIN:
            chosen="abstain"
        else:
            chosen=max(scores,key=lambda k:(scores[k],k))
        return {"chosen":chosen,"probes":len(self.events),
                "log_margin":round(margin,5)}

    def record(self):
        if not self.events:
            raise ValueError("calibration requires public action evidence")
        state={"schema":SCHEMA,"fingerprints":self.fingerprints,
               "events":self.events,"decision":self.decision()}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,source,changed,record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
            type(record["state"]) is not dict or
            record["sha256"]!=digest(record["state"])):
            raise ValueError("invalid calibration record digest")
        state=record["state"]
        if (set(state)!={"schema","fingerprints","events","decision"} or
            state["schema"]!=SCHEMA or type(state["events"]) is not list or
            not 1<=len(state["events"])<=PROBES):
            raise ValueError("invalid calibration record structure")
        restored=cls(source,changed)
        if restored.fingerprints!=state["fingerprints"]:
            raise ValueError("calibration belongs to different learned memories")
        for row in state["events"]:
            if (type(row) is not dict or
                set(row)!={"episode","before","action","after","event"} or
                row["episode"]!=row["before"].get("episode")):
                raise ValueError("invalid public calibration evidence")
            event=restored.observe(row["before"],row["action"],row["after"])
            if event!=row["event"]:
                raise ValueError("public outcome history is inconsistent")
        if restored.record()!=record:
            raise ValueError("calibration selection did not replay")
        return restored
