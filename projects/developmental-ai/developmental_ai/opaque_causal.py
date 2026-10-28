"""Anonymous-action intervention study across two distinct hidden rule systems.

Simulation-only. Agent receives numeric sensors, opaque per-episode action IDs,
a public target channel, and accept/blocked feedback, NOT hidden causal rules,
action descriptions, family labels, or a stable name-to-effect mapping.
The shared numeric I/O contract and policies ARE engineered priors.
"""
from __future__ import annotations

import hashlib
import json
import random

from developmental_ai.outcome_skills import canonical, digest

SCHEMA = "developmental-ai.opaque-causal/v1"
POLICIES = ("novel", "retry", "switch")
BUDGET = 18
MAX_ACTIONS = 10
MAX_SENSORS = 12


def validate(frame):
    if (type(frame) is not dict or
        set(frame) != {"schema", "episode", "tick", "remaining", "channels", "actions", "goal", "done"} or
        frame["schema"] != SCHEMA or
        type(frame["episode"]) is not str or len(frame["episode"]) != 64 or
        any(c not in "0123456789abcdef" for c in frame["episode"]) or
        type(frame["tick"]) is not int or not 0 <= frame["tick"] <= BUDGET or
        type(frame["remaining"]) is not int or frame["remaining"] != BUDGET - frame["tick"] or
        type(frame["channels"]) is not list or not 1 <= len(frame["channels"]) <= MAX_SENSORS or
        any(type(x) is not int or not 0 <= x <= 3 for x in frame["channels"]) or
        type(frame["actions"]) is not list or len(frame["actions"]) > MAX_ACTIONS or
        any(type(a) is not str or len(a) != 20 or not a.startswith("a_") or
            any(c not in "0123456789abcdef" for c in a[2:]) for a in frame["actions"]) or
        len(frame["actions"]) != len(set(frame["actions"])) or
        type(frame["goal"]) is not dict or set(frame["goal"]) != {"channel", "at_least"} or
        type(frame["goal"]["channel"]) is not int or
        not 0 <= frame["goal"]["channel"] < len(frame["channels"]) or
        type(frame["goal"]["at_least"]) is not int or frame["goal"]["at_least"] != 1 or
        type(frame["done"]) is not bool or
        (frame["done"] and frame["actions"])):
        raise ValueError("invalid anonymous causal observation")
    return frame


def rng_for(seed, split, index, family):
    if (type(seed) is not int or split not in ("train", "test") or
        type(index) is not int or not 0 <= index < 100000 or
        family not in ("relay", "cargo")):
        raise ValueError("invalid experiment episode")
    value = hashlib.sha256(canonical([SCHEMA, seed, split, index, family]).encode()).digest()
    return random.Random(int.from_bytes(value[:8], "big"))


class OpaqueWorld:
    """Only the simulator sees action effects and prerequisites."""
    def __init__(self, seed, split, index, family):
        rng = rng_for(seed, split, index, family)
        self.episode = digest([SCHEMA, seed, split, index, family])
        self.family = family
        self.tick = 0
        self.done = False
        if family == "relay":
            self._names = ("power", "switch", "combine", "gate", "endpoint", "decoy", "isolate")
            self._state = [0]*7
            self._target = 4
        else:
            self._names = ("extract", "charge", "refine", "fuel", "load", "ship", "spoil", "wash")
            self._state = [0]*8
            self._target = 5
        ids = [f"a_{rng.getrandbits(72):018x}" for _ in self._names]
        if len(set(ids)) != len(ids):
            raise RuntimeError("colliding action IDs")
        self._ids = dict(zip(self._names, ids))
        self._lookup = {v:k for k,v in self._ids.items()}
        self._channel_order = list(range(len(self._state)))
        rng.shuffle(self._channel_order)
        self._order = list(self._names)
        rng.shuffle(self._order)
        self._used = set()

    def frame(self):
        # Channel permutation is per episode and not known to the learner.
        return validate({"schema":SCHEMA, "episode":self.episode,
            "tick":self.tick, "remaining":BUDGET-self.tick,
            "channels":[self._state[i] for i in self._channel_order],
            "actions":[self._ids[name] for name in self._order if name not in self._used] if not self.done else [],
            "goal":{"channel":self._channel_order.index(self._target),"at_least":1},
            "done":self.done})

    def _relay(self, name):
        x=self._state
        rules={
            "power":((),0), "switch":((),1), "combine":((0,1),2),
            "gate":((2,),3), "endpoint":((3,),4),
            "decoy":((),5), "isolate":((),6),
        }
        prereqs,effect=rules[name]
        if not all(x[r]>=1 for r in prereqs):
            return False
        x[effect]=1
        return True

    def _cargo(self, name):
        x=self._state
        if name=="extract":x[0]=2;return True
        if name=="charge":x[1]=1;return True
        if name=="fuel":x[3]=1;return True
        if name=="wash":x[6]=1;return True
        if name=="spoil":
            if x[0]<1:return False
            x[0]-=1;x[7]=1;return True
        if name=="refine":
            if x[0]<2 or x[1]<1:return False
            x[0]-=2;x[1]-=1;x[2]=1;return True
        if name=="load":
            if x[2]<1 or x[3]<1:return False
            x[2]=0;x[3]=0;x[4]=1;return True
        if name=="ship":
            if x[4]<1:return False
            x[5]=1;return True
        raise AssertionError("unknown simulator operation")

    def step(self, action, tick):
        if (self.done or type(tick) is not int or tick != self.tick or
            type(action) is not str or action not in self._lookup or
            self._lookup[action] in self._used):
            raise ValueError("invalid stale/hidden action")
        name=self._lookup[action]
        before=list(self._state)
        accepted=self._relay(name) if self.family=="relay" else self._cargo(name)
        if not accepted and self._state != before:
            raise AssertionError("blocked action mutated hidden state")
        if accepted:
            self._used.add(name)
        self.tick += 1
        reached=self._state[self._target]>=1
        self.done=reached or self.tick==BUDGET or len(self._used)==len(self._names)
        return {"accepted":accepted,"frame":self.frame(),
                "success":reached}


class OpaqueEpisodePolicy:
    """Bounded episode-local learning from feedback; no stable action symbols.

    'novel', 'retry', 'switch' are engineered algorithms, not new weight
    learning. A test must not pass private causal rules or family identity.
    """
    def __init__(self, policy):
        if policy not in POLICIES:
            raise ValueError("invalid exploration policy")
        self.policy=policy
        self.episode=None
        self.history=[]
        self._start=None

    def _ready(self, frame):
        validate(frame)
        if frame["done"]:
            raise ValueError("episode complete")
        if self.episode is None:
            if frame["tick"] != 0:
                raise ValueError("cannot start mid-episode without replay")
            self.episode=frame["episode"]
            self._start=json.loads(canonical(frame))
        if frame["episode"] != self.episode or frame["tick"] != len(self.history):
            raise ValueError("unexpected episode/tick")
        if self.history and self.history[-1]["after"] != frame:
            raise ValueError("observation not continuous")
        return frame

    def choose(self, frame):
        self._ready(frame)
        attempted={}
        for e in self.history:
            attempted.setdefault(e["action"],[]).append(e)
        current=tuple(frame["channels"])
        untried=[a for a in frame["actions"] if a not in attempted]
        # Do not retry a failed action without any observed state changes.
        deferred=[a for a in frame["actions"] if a in attempted and
                  attempted[a][-1]["accepted"] is False and
                  tuple(attempted[a][-1]["before"]["channels"]) != current]
        # Reprioritize changed-state retries based on newly positive sensors.
        newly_changed=lambda a:sum(1 for before,now in zip(
            attempted[a][-1]["before"]["channels"],current) if now>before)
        deferred.sort(key=lambda a:(-newly_changed(a),a))
        if self.policy=="novel":
            candidates=untried+deferred
        elif self.policy=="retry":
            candidates=deferred+untried
        else:
            candidates=(deferred+untried if self.history and self.history[-1]["accepted"]
                        else untried+deferred)
        return candidates[0] if candidates else None

    def feedback(self, before, action, accepted, after):
        self._ready(before)
        validate(after)
        if (type(action) is not str or action not in before["actions"] or
            type(accepted) is not bool or
            after["episode"] != before["episode"] or after["tick"]!=before["tick"]+1 or
            after["goal"] != before["goal"] or
            after["remaining"] != before["remaining"]-1):
            raise ValueError("invalid causal action feedback")
        old=set(before["actions"]);new=set(after["actions"])
        if after["done"]:
            # The simulator hides all remaining handles at termination.
            if new:
                raise ValueError("terminal actions must be hidden")
        elif accepted:
            if new != old-{action}:
                raise ValueError("accepted action must disappear")
        elif new != old:
            raise ValueError("blocked action changed available actions")
        if not accepted and before["channels"] != after["channels"]:
            raise ValueError("blocked action changed public state")
        if accepted and before["channels"]==after["channels"]:
            raise ValueError("accepted action did not change observation")
        expected_done=(after["channels"][after["goal"]["channel"]]>=after["goal"]["at_least"]
                       or after["remaining"]==0 or not after["actions"])
        if after["done"] != expected_done:
            raise ValueError("inconsistent terminal event")
        if action != self.choose(before):
            raise ValueError("feedback did not match policy action")
        self.history.append({"before":json.loads(canonical(before)),"action":action,
                             "accepted":accepted,"after":json.loads(canonical(after))})

    def record(self):
        if not self.history:
            raise ValueError("empty episode evidence")
        state={"schema":SCHEMA,"policy":self.policy,"initial":self._start,
               "events":self.history}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
            type(record["state"]) is not dict or
            record["sha256"]!=digest(record["state"])):
            raise ValueError("invalid journal digest")
        s=record["state"]
        if (set(s)!={"schema","policy","initial","events"} or
            s["schema"]!=SCHEMA or type(s["events"]) is not list or
            not 1<=len(s["events"])<=BUDGET):
            raise ValueError("invalid causal journal")
        model=cls(s["policy"])
        if not isinstance(s["initial"],dict):
            raise ValueError("invalid initial state")
        for i,e in enumerate(s["events"]):
            if type(e) is not dict or set(e)!={"before","action","accepted","after"}:
                raise ValueError("invalid episode event")
            if i==0 and e["before"]!=s["initial"]:
                raise ValueError("wrong initial state")
            model.feedback(e["before"],e["action"],e["accepted"],e["after"])
        if model.record()!=record:
            raise ValueError("replayed decision history differs")
        return model
