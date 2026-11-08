"""Fast public-outcome contradiction trigger with an immediate short memory.

An archived model learned from first 192 outcomes remains intact. Only public
observed outcome likelihoods determine when a last-eight-event learner
temporarily replaces it. The trigger is an engineered diagnostic and the recent
model is fitted on the SAME observations that trigger it (selection optimism).
This is NOT safe first-contact detection or independent regime discovery.
"""
from __future__ import annotations

import json

from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest
)
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory

SCHEMA="developmental-ai.fast-shock-switch/v1"
ANCHOR=192
RECENT=8
SURPRISE_WINDOW=4
SURPRISE_PROBABILITY=0.125


class FastShockMemory:
    """Use historical knowledge until recent public contradictions recur."""

    def __init__(self):
        self.events=[]

    def observe(self,event):
        if len(self.events)>=MAX_SAMPLES:
            raise ValueError("shock-model event cap reached")
        probe=RelationOutcomeMemory()
        probe.observe(event)
        item=probe.events[0]
        if self.events and set(item["features"])!=set(self.events[0]["features"]):
            raise ValueError("shock model requires unchanged observed feature keys")
        self.events.append(item)

    @staticmethod
    def _model(rows):
        m=RelationOutcomeMemory()
        for event in rows:
            m.observe(event)
        return m

    @staticmethod
    def _probability(model,event):
        predicted=model.estimate(event["features"])
        return (predicted["progress"] if event["progress"] else
                predicted["damage"] if event["damage"] else
                1.0-predicted["progress"]-predicted["damage"])

    def selection(self):
        if len(self.events)<ANCHOR+RECENT:
            raise ValueError("insufficient observed evidence for anchor and recent")
        old=self._model(self.events[:ANCHOR])
        latest=self.events[-RECENT:]
        unexpected=[int(self._probability(old,e)<SURPRISE_PROBABILITY)
                    for e in latest]
        four=sum(unexpected[-SURPRISE_WINDOW:])
        eight=sum(unexpected)
        mode="recent" if four>=2 or (four==1 and eight>=3) else "anchor"
        learned=self._model(latest) if mode=="recent" else old
        detail={"source":mode,"last4_unexpected":four,"last8_unexpected":eight,
                "recent_training_events":RECENT,
                "recent_selection_training_overlap":RECENT if mode=="recent" else 0,
                "recorded_events":len(self.events)}
        return detail,learned

    def choose(self,frame):
        # Existing frame validation enforces numerical public affordances.
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        _,model=self.selection()
        return model.choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("untrained fast-shock memory")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
                or type(record["state"]) is not dict or
                type(record["sha256"]) is not str
                or digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid fast-shock checksum")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA
                or type(state["events"]) is not list
                or not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid fast-shock checkpoint")
        m=cls()
        for event in state["events"]:
            m.observe(event)
        if m.record()!=record:
            raise ValueError("fast-shock replay mismatch")
        return m
