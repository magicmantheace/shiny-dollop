"""Opt-in recovery from independently supplied public observations.

This model does not perform or authorize observation-acquisition actions.
A benchmark/controller can offer a bounded batch from an independent actor
*only when* model adequacy has failed. That actor may itself cause harmful
outcomes and the benchmark must count them. The only learned content is
validated public features/progress/damage; witness_count is a budget counter.
"""
from __future__ import annotations

import json

from developmental_ai.validated_abstention_memory import ValidatedAbstainingMemory
from developmental_ai.observable_affordances import MAX_SAMPLES, canonical, digest

SCHEMA="developmental-ai.independent-witness-recovery/v1"
BATCH=8
MAX_WITNESS=32


class WitnessRecoveryMemory(ValidatedAbstainingMemory):
    """A bounded request/offer protocol with no simulator or actor handle."""

    def __init__(self):
        super().__init__()
        self.witness_count=0

    def can_request_witness(self):
        if len(self.events)<240 or self.witness_count+BATCH>MAX_WITNESS:
            return False
        return not self.selection()[0]["meets_adequacy_gate"]

    def accept_witness(self,public_batch):
        if not self.can_request_witness():
            raise ValueError("witness observation not requested or budget exhausted")
        if type(public_batch) is not list or len(public_batch)!=BATCH:
            raise ValueError("witness must be exactly eight public observations")
        if len(self.events)+BATCH>MAX_SAMPLES:
            raise ValueError("witness would exceed bounded evidence history")
        # Transactional validation: never partially add a malformed report.
        staged=type(self)()
        staged.events=list(self.events)
        for observation in public_batch:
            staged.observe(observation)
        self.events=staged.events
        self.witness_count+=BATCH
        self._cache=None

    def record(self):
        if not self.events:
            raise ValueError("no public feedback to save")
        state={"schema":SCHEMA,"events":self.events,
               "witness_count":self.witness_count}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str or
                digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid witnessed evidence checkpoint integrity")
        s=record["state"]
        if (set(s)!={"schema","events","witness_count"} or
                s["schema"]!=SCHEMA or type(s["events"]) is not list
                or not 1<=len(s["events"])<=MAX_SAMPLES or
                type(s["witness_count"]) is not int or
                s["witness_count"]<0 or s["witness_count"]>MAX_WITNESS or
                s["witness_count"]%BATCH!=0 or
                len(s["events"])<s["witness_count"]):
            raise ValueError("invalid witnessed checkpoint structure")
        result=cls()
        for event in s["events"]:
            result.observe(event)
        result.witness_count=s["witness_count"]
        if result.record()!=record:
            raise ValueError("cannot replay witnessed public evidence")
        return result
