"""One-step diagnostic of a known descriptor remapping, without a cue.

All runtime inputs are *public* action descriptors, numeric sensors, and
accepted/blocked action outcomes. No simulator phase, true action name,
privileged recipe, or two-number context beacon is passed to this policy.

Limitations: both regimes and their outcome histories were segregated during
training; the descriptors still encode stable engineered action identities.
A first-step probe is comparatively safe ONLY in this zero-resource toy
simulator, not a general safe experiment selection algorithm.
"""
from __future__ import annotations

import json
from developmental_ai.affordance_memory import (
    FilteredNovel, record_step, check as check_public, token
)
from developmental_ai.contextual_affordance import ContextMemory
from developmental_ai.outcome_skills import canonical, digest

SCHEMA="developmental-ai.no-cue-diagnostic/v1"
MAX_STEPS=18
MIN_OBSERVATIONS=2
MIN_DIFFERENCE=0.30


def diagnostic_table(memories):
    """Fit Bernoulli acceptance for each token at training tick 0 only.

    Only public first-step events are used. Their records have no hidden
    stage IDs, initial recipes, or private action names.
    """
    if not isinstance(memories,ContextMemory):
        raise TypeError("two replay-verified source histories required")
    result={}
    for context,(cue,memory) in sorted(memories._rows.items()):
        histogram={}
        for row in memory.events:
            first=row["steps"][0]
            identity=token(first["signature"])
            stats=histogram.setdefault(identity,[0,0])
            stats[0]+=int(first["accepted"])
            stats[1]+=1
        result[context]=histogram
    return result


def select_probe(memories):
    counts=diagnostic_table(memories)
    names=sorted(counts)
    if len(names)!=2:
        raise ValueError("exactly two candidate histories required")
    choices=[]
    for code in sorted(set(counts[names[0]]) & set(counts[names[1]])):
        x=counts[names[0]][code]
        y=counts[names[1]][code]
        if x[1]<MIN_OBSERVATIONS or y[1]<MIN_OBSERVATIONS:
            continue
        px=(x[0]+1)/(x[1]+2)
        py=(y[0]+1)/(y[1]+2)
        gap=abs(px-py)
        if gap>=MIN_DIFFERENCE:
            choices.append((gap,min(x[1],y[1]),code,px,py))
    if not choices:
        return None
    # Larger empirical disagreement and stronger minimum exposure win;
    # lexical deterministic tie breaker is not a hidden action label.
    choices.sort(key=lambda row:(-row[0],-row[1],row[2]))
    _,_,code,px,py=choices[0]
    return {"token":code,"likelihoods":{names[0]:px,names[1]:py}}


class NoCueProbe:
    """Public-feedback diagnostic followed by a known non-learning policy."""
    def __init__(self,memories):
        if not isinstance(memories,ContextMemory):
            raise TypeError("ContextMemory required")
        self.memories=memories
        self.diagnostic=select_probe(memories)
        self.memory_sha=memories.record()["sha256"]
        self._controller=None
        self._probe_action=None
        self.selected=None
        self.confidence=None
        self.events=[]
        self.episode=None

    def _normal(self, chosen):
        self.selected=chosen
        self._controller=FilteredNovel(self.memories._rows[chosen][1])

    def choose(self,frame):
        check_public(frame)
        base=frame["base"]
        if base["done"] or base["tick"] != len(self.events):
            raise ValueError("invalid episode step")
        if self.episode is None:
            if base["tick"]!=0:
                raise ValueError("cannot start diagnostic mid-episode")
            self.episode=base["episode"]
            if self.diagnostic is not None and all(x==0 for x in base["channels"]):
                for row in frame["descriptors"]:
                    if token(row["signature"])==self.diagnostic["token"]:
                        self._probe_action=row["id"]
                        return row["id"]
            self._normal(sorted(self.memories._rows)[0])
        if base["episode"]!=self.episode:
            raise ValueError("cross-episode memory contamination")
        if self._controller is None:
            if len(self.events)!=0 or self._probe_action not in base["actions"]:
                raise ValueError("lost or stale diagnostic probe")
            return self._probe_action
        return self._controller.choose(frame)

    def feedback(self,before,action,accepted,after):
        check_public(before)
        check_public(after)
        if action!=self.choose(before):
            raise ValueError("feedback does not match selected action")
        evidence=record_step(before,action,accepted,after)
        if self._controller is None:
            estimates=self.diagnostic["likelihoods"]
            chances={name:p if accepted else (1-p)
                     for name,p in estimates.items()}
            denominator=sum(chances.values())
            chosen=min(chances, key=lambda name:(-chances[name],name))
            self.confidence=chances[chosen]/denominator if denominator else 0.5
            self._normal(chosen)
            # The diagnostic is a REAL public action step. Preserve it in
            # the continuation policy's episode-local history and budget.
            self._controller.history.append({
                "action":action,"before":json.loads(canonical(before["base"])),
                "after":json.loads(canonical(after["base"])),
                "accepted":accepted,"effect":evidence})
        else:
            self._controller.feedback(before,action,accepted,after)
        self.events.append({"before":json.loads(canonical(before)),
                            "action":action,"accepted":accepted,
                            "after":json.loads(canonical(after))})
        return evidence

    def record(self):
        if not self.events:
            raise ValueError("no evaluated feedback")
        state={"schema":SCHEMA,"memory_sha256":self.memory_sha,
               "events":self.events,
               "selected":self.selected,
               "confidence":self.confidence}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,memories,saved):
        if (type(saved) is not dict or set(saved)!={"state","sha256"}
            or type(saved["state"]) is not dict
            or saved["sha256"]!=digest(saved["state"])):
            raise ValueError("invalid diagnostic checkpoint integrity")
        state=saved["state"]
        if (set(state)!={"schema","memory_sha256","events","selected","confidence"}
            or state["schema"]!=SCHEMA
            or type(state["events"]) is not list
            or not 1<=len(state["events"])<=MAX_STEPS):
            raise ValueError("invalid diagnostic checkpoint schema")
        obj=cls(memories)
        if obj.memory_sha!=state["memory_sha256"]:
            raise ValueError("diagnostic history belongs to other training state")
        for row in state["events"]:
            if type(row) is not dict or set(row)!={"before","action","accepted","after"}:
                raise ValueError("malformed public feedback")
            obj.feedback(row["before"],row["action"],row["accepted"],row["after"])
        if obj.record()!=saved:
            raise ValueError("diagnostic choice was not reproducible")
        return obj
