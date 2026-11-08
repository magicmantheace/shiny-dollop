"""Optional same-observation-schema regime competition, simulation-only.

All learned state consists of a chronological public numeric feature/outcome
stream. Source anchor length, recency and confidence threshold are deliberate
developer-engineered priors. No regime names, labels, or hidden dynamics enter.
An abstained task is a failure, not a successful harm-free solution.
"""
from __future__ import annotations

import json
import math

from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest
)
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory

SCHEMA = "developmental-ai.same-schema-switch-memory/v1"
ANCHOR = 192
RECENT_TRAIN = 12
VALIDATION_TAIL = 4
MAX_MEAN_SURPRISE = 1.5


class SameSchemaSwitchMemory:
    """Compete an early immutable skill with a truly disjoint recent skill.

    The first 192 examples become a long-term anchor, not an externally
    labelled phase. New candidate predictions use the 12 events immediately
    before 4 scoring events; no scoring event enters their fit.
    """

    def __init__(self):
        self.events = []

    def observe(self, event):
        if len(self.events) >= MAX_SAMPLES:
            raise ValueError("too many public outcome events")
        model = RelationOutcomeMemory()
        model.observe(event)
        row = model.events[0]
        if self.events and tuple(sorted(row["features"])) != tuple(sorted(self.events[0]["features"])):
            raise ValueError("same-schema research mode rejects changed feature keys")
        self.events.append(row)

    @staticmethod
    def _fit(events):
        fitted = RelationOutcomeMemory()
        for row in events:
            fitted.observe(row)
        return fitted

    @staticmethod
    def _likelihood(model, events):
        score=0.0
        for row in events:
            probs=model.estimate(row["features"])
            probability = (probs["progress"] if row["progress"] else
                           probs["damage"] if row["damage"] else
                           1.0-probs["progress"]-probs["damage"])
            if probability<=0 or not math.isfinite(probability):
                raise ValueError("invalid public outcome probability")
            score+=math.log(probability)
        return score

    def selection(self):
        if len(self.events)<ANCHOR+RECENT_TRAIN+VALIDATION_TAIL:
            raise ValueError("not enough independent source and scoring evidence")
        anchor=self._fit(self.events[:ANCHOR])
        tail=self.events[-VALIDATION_TAIL:]
        recent=self._fit(self.events[-(VALIDATION_TAIL+RECENT_TRAIN):-VALIDATION_TAIL])
        scores=[("anchor",anchor,self._likelihood(anchor,tail)),
                ("recent",recent,self._likelihood(recent,tail))]
        chosen=max(scores,key=lambda item:(item[2],int(item[0]=="anchor")))
        abstain=chosen[2]/VALIDATION_TAIL < -MAX_MEAN_SURPRISE
        result={
            "source":chosen[0],
            "abstain":abstain,
            "anchor_score":round(scores[0][2],6),
            "recent_score":round(scores[1][2],6),
            "evidence_events":VALIDATION_TAIL,
            "candidate_train_overlap":0,
            "recorded_events":len(self.events)
        }
        return result, chosen[1]

    def choose(self, frame):
        # Strict inherited public frame validation; never source family labels.
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        plan,model=self.selection()
        if plan["abstain"]:
            return None
        return model.choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("no observed outcomes")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
            or type(record["state"]) is not dict
            or type(record["sha256"]) is not str
            or digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid same-schema checkpoint checksum")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA
            or type(state["events"]) is not list
            or not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid same-schema checkpoint structure")
        obj=cls()
        for event in state["events"]:
            obj.observe(event)
        if obj.record()!=record:
            raise ValueError("same-schema evidence replay mismatch")
        return obj
