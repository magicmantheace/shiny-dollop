"""Optional persistent numeric affordance-risk learning; simulation only.

Stable numeric descriptors are ENGINEERED by the simulator from hidden action
kinds; the learner does not discover the descriptors from raw perception.
Risk is an observational association with failed episodes, not causality.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from developmental_ai.outcome_skills import canonical, digest
from developmental_ai.opaque_causal import OpaqueWorld, validate as validate_base

SCHEMA = "developmental-ai.affordance-risk/v1"
MAX_TRAIN = 80
MAX_ACTIONS = 10
MAX_STEPS = 18
MAX_CHANNELS = 12
MAX_CHECKPOINT_BYTES = 2 * 1024 * 1024


def signature(seed, family, hidden_name):
    """SIMULATOR-ONLY identity encoding; must never run inside a policy."""
    raw = hashlib.sha256(f"{SCHEMA}/{seed}/{family}/{hidden_name}".encode()).digest()
    return [raw[0], raw[1]]


def token(value):
    if (type(value) is not list or len(value) != 2 or
        any(type(x) is not int or not 0 <= x <= 255 for x in value)):
        raise ValueError("invalid bounded numeric descriptor")
    return ".".join(str(v) for v in value)


def check(frame):
    if type(frame) is not dict or set(frame) != {"base", "descriptors"}:
        raise ValueError("invalid descriptor observation")
    base = validate_base(frame["base"])
    rows = frame["descriptors"]
    if type(rows) is not list or len(rows) != len(base["actions"]):
        raise ValueError("descriptors not aligned with action handles")
    seen=set()
    for row, action in zip(rows, base["actions"]):
        if (type(row) is not dict or set(row) != {"id","signature"} or
            row["id"] != action):
            raise ValueError("descriptor source mismatch")
        code=token(row["signature"])
        if code in seen:
            raise ValueError("ambiguous public signatures")
        seen.add(code)
    return frame


class DescribedWorld:
    """Add stable NUMERIC action labels to unchanged hidden simulator rules."""
    def __init__(self, seed, split, index, family, *, remap=False):
        self.base=OpaqueWorld(seed,split,index,family)
        self.seed=seed
        self.family=family
        self.remap=remap
        self._features={name:signature(seed,family,name)
                        for name in self.base._names}
        if remap:
            # Ablation: descriptors retain shape but rotate independently each
            # episode. No semantic information survives a new episode.
            codes=[signature(seed, family, f"randomized/{index}/{i}")
                   for i in range(len(self.base._names))]
            self._features=dict(zip(self.base._names,codes))
        if len({token(x) for x in self._features.values()}) != len(self._features):
            raise ValueError("descriptor hash collision")

    def frame(self):
        f=self.base.frame()
        return check({"base":f,"descriptors":[
            {"id":a,"signature":list(self._features[self.base._lookup[a]])}
            for a in f["actions"]]})

    def step(self, action, tick):
        result=self.base.step(action,tick)
        return {"accepted":result["accepted"],"frame":self.frame()}

    def public_success(self):
        b=self.frame()["base"]
        return b["channels"][b["goal"]["channel"]]>=b["goal"]["at_least"]


def record_step(before, action, accepted, after):
    check(before);check(after)
    a=before["base"];b=after["base"]
    if (type(action) is not str or action not in a["actions"] or
        type(accepted) is not bool or a["episode"]!=b["episode"] or
        b["tick"]!=a["tick"]+1 or b["goal"]!=a["goal"] or
        b["remaining"]!=a["remaining"]-1):
        raise ValueError("invalid observable outcome")
    old=set(a["actions"]);new=set(b["actions"])
    if accepted:
        if not b["done"] and new!=old-{action}:
            raise ValueError("accepted action still visible")
        if a["channels"]==b["channels"]:
            raise ValueError("accepted action had no sensor effect")
    elif a["channels"]!=b["channels"] or (not b["done"] and new!=old):
        raise ValueError("blocked action altered visible state")
    if b["done"] and b["actions"]:
        raise ValueError("terminal action list not hidden")
    descriptor=next(r["signature"] for r in before["descriptors"] if r["id"]==action)
    delta=[y-x for x,y in zip(a["channels"],b["channels"])]
    return {"signature":list(descriptor),"accepted":accepted,
            "increases":sum(d>0 for d in delta),
            "decreases":sum(d<0 for d in delta)}


class RiskMemory:
    """Replayable bounded history of public attempted action codes and outcome."""
    def __init__(self):
        self.events=[]

    def add(self, index, events, success):
        if (type(index) is not int or index!=len(self.events) or index>=MAX_TRAIN
            or type(events) is not list or not 1<=len(events)<=MAX_STEPS
            or type(success) is not bool):
            raise ValueError("invalid training episode boundary")
        rows=[]
        for event in events:
            if (type(event) is not dict or
                set(event)!={"signature","accepted","increases","decreases"} or
                type(event["accepted"]) is not bool or
                type(event["increases"]) is not int or
                type(event["decreases"]) is not int or
                not 0<=event["increases"]<=MAX_CHANNELS or
                not 0<=event["decreases"]<=MAX_CHANNELS):
                raise ValueError("invalid event record")
            token(event["signature"])
            if not event["accepted"] and (event["increases"] or event["decreases"]):
                raise ValueError("blocked event cannot change sensors")
            if event["accepted"] and not (event["increases"] or event["decreases"]):
                raise ValueError("accepted event without sensor effect")
            rows.append(json.loads(canonical(event)))
        self.events.append({"index":index,"steps":rows,"success":success})

    def analysis(self):
        """Correlated failures, not supervised ground-truth labels."""
        success_total=sum(row["success"] for row in self.events)
        tokens=set()
        for row in self.events:
            tokens.update(token(step["signature"]) for step in row["steps"]
                          if step["accepted"])
        out={}
        for key in sorted(tokens):
            with_rows=[r for r in self.events if key in {
                token(s["signature"]) for s in r["steps"] if s["accepted"]}]
            failed=sum(not r["success"] for r in with_rows)
            successes=sum(r["success"] for r in with_rows)
            out[key]={"accepted_episodes":len(with_rows),
                      "successes_with":successes,"failures_with":failed,
                      "successes_without":success_total-successes,
                      "risk_candidate":(failed>=3 and successes<=max(1, len(with_rows)//10)
                                        and success_total-successes>=3)}
        return out

    def avoid(self):
        return {name for name,row in self.analysis().items() if row["risk_candidate"]}

    def record(self):
        if not self.events:
            raise ValueError("untrained memory")
        state={"schema":SCHEMA,"episodes":self.events,
               "statistics":self.analysis()}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    def save(self, path):
        """Persist replay-verifiable learning evidence via atomic replacement.

        The caller chooses a PRIVATE local path; this never writes to a
        repository, remote service, or external model process automatically.
        """
        target=Path(path)
        payload=(canonical(self.record())+"\n").encode("utf-8")
        if len(payload)>MAX_CHECKPOINT_BYTES:
            raise ValueError("affordance checkpoint exceeds configured limit")
        target.parent.mkdir(parents=True,exist_ok=True)
        pending=None
        try:
            with tempfile.NamedTemporaryFile("wb",dir=target.parent,
                                             prefix=".affordance-pending-",
                                             delete=False) as stream:
                pending=Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending,target)
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)

    @classmethod
    def load(cls, path):
        target=Path(path)
        if target.stat().st_size>MAX_CHECKPOINT_BYTES:
            raise ValueError("affordance checkpoint exceeds configured limit")
        data=json.loads(target.read_text(encoding="utf-8"))
        return cls.restore(data)

    @classmethod
    def restore(cls, saved):
        if (type(saved) is not dict or set(saved)!={"state","sha256"} or
            type(saved["state"]) is not dict or saved["sha256"]!=digest(saved["state"])):
            raise ValueError("invalid local checkpoint integrity")
        state=saved["state"]
        if (set(state)!={"schema","episodes","statistics"} or
            state["schema"]!=SCHEMA or type(state["episodes"]) is not list or
            not 1<=len(state["episodes"])<=MAX_TRAIN):
            raise ValueError("invalid checkpoint schema")
        obj=cls()
        for idx,row in enumerate(state["episodes"]):
            if (type(row) is not dict or set(row)!={"index","steps","success"}):
                raise ValueError("invalid checkpoint event")
            obj.add(row["index"],row["steps"],row["success"])
            if row["index"]!=idx:
                raise ValueError("training episode order mismatch")
        if obj.record()!=saved:
            raise ValueError("training evidence does not replay")
        return obj


class FilteredNovel:
    """Existing novel-first local exploration with optional memory-based veto."""
    def __init__(self, memory=None):
        if memory is not None and not isinstance(memory,RiskMemory):
            raise TypeError("optional RiskMemory required")
        self.memory=memory
        self.history=[]

    def choose(self, frame):
        check(frame)
        base=frame["base"]
        if base["done"] or base["tick"]!=len(self.history):
            raise ValueError("invalid episode step")
        if self.history and self.history[-1]["after"]!=base:
            raise ValueError("state discontinuity")
        risk=self.memory.avoid() if self.memory is not None else set()
        handles={row["id"]:token(row["signature"]) for row in frame["descriptors"]}
        known={event["action"] for event in self.history}
        untried=[a for a in base["actions"] if a not in known and handles[a] not in risk]
        seen={}
        for event in self.history:
            seen[event["action"]]=event
        rest=[a for a in base["actions"] if a in seen and not seen[a]["accepted"]
              and seen[a]["before"]["channels"] != base["channels"] and
              handles[a] not in risk]
        rest.sort(key=lambda a:(-sum(v>u for u,v in zip(
            seen[a]["before"]["channels"],base["channels"])),a))
        return (untried+rest)[0] if untried or rest else None

    def feedback(self, before, action, accepted, after):
        observed=record_step(before,action,accepted,after)
        if self.choose(before)!=action:
            raise ValueError("action not selected by bounded policy")
        self.history.append({"action":action,"before":json.loads(canonical(before["base"])),
                             "after":json.loads(canonical(after["base"])),
                             "accepted":accepted,"effect":observed})
        return observed
