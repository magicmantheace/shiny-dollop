"""Experimental learned action-priority reuse across public DAG task families.

The action graph, goal, and dependency-closure computation are DEVELOPER-GIVEN.
Only per-feature action values are learned from task feedback. This is not
self-discovered planning, skill composition, a language agent or permission.
No files/network/tools are controlled by this module.
"""
from __future__ import annotations

import hashlib
import json
import math
import random

SCHEMA = "developmental-ai.procedural-skill/v1"
FRAME_SCHEMA = "developmental-ai.procedural-frame/v1"
MODEL_SCHEMA = "developmental-ai.procedural-policy/v1"
FAMILIES = ("workshop", "repair")
MAX_STEPS = 6
MAX_TRAIN = 600
ACTIONS_PER_EPISODE = 7


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _random(seed, family, split, index, purpose):
    if (type(seed) is not int or family not in FAMILIES or split not in ("train", "test") or
            type(index) is not int or not 0 <= index < 1000000 or type(purpose) is not str):
        raise ValueError("invalid procedural episode namespace")
    b = f"{SCHEMA}/{seed}/{family}/{split}/{index}/{purpose}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(b).digest()[:8], "big"))


class ProceduralWorld:
    """A public dependency graph with opaque, per-episode action names."""

    def __init__(self, seed, family, split, index):
        generator = _random(seed, family, split, index, "graph")
        self.config = {"seed":seed, "family":family, "split":split, "index":index}
        names = [f"{'wrk' if family=='workshop' else 'rpr'}_{x:02d}" for x in range(ACTIONS_PER_EPISODE)]
        generator.shuffle(names)
        if family == "workshop":
            prereq_indices = ((), (), (0,1), (2,), (), (), ())
            goal_index = 3
        else:
            prereq_indices = ((), (0,), (0,), (1,2), (3,), (), ())
            goal_index = 4
        self.graph = {names[i]:[names[j] for j in requirements]
                      for i,requirements in enumerate(prereq_indices)}
        self.goal=names[goal_index]
        self.done=False
        self.completed=[]
        self.tick=0
        self._ancestors = ancestor_closure(self.graph, self.goal)
        self._initial_hash=digest({"schema":SCHEMA,"config":self.config,"graph":self.graph,"goal":self.goal})

    def frame(self):
        if self.done:
            available=[]
        else:
            available=sorted(k for k,v in self.graph.items() if k not in self.completed and
                             all(p in self.completed for p in v))
        return {"schema":FRAME_SCHEMA,"family":self.config["family"],
                "episode_id":self._initial_hash,"tick":self.tick,"goal":self.goal,
                "prerequisites":{k:list(v) for k,v in sorted(self.graph.items())},
                "completed":list(self.completed),"available_actions":available,
                "remaining":MAX_STEPS-self.tick,"done":self.done,"scope":"simulation-only"}

    def step(self, action, *, expected_tick):
        frame=self.frame()
        if (self.done or type(action) is not str or action not in frame["available_actions"] or
                type(expected_tick) is not int or expected_tick!=self.tick):
            raise ValueError("illegal or stale procedural action")
        self.completed.append(action)
        self.tick+=1
        success=action==self.goal
        self.done=success or self.tick>=MAX_STEPS
        reward=3.0 if success else (0.15 if action in self._ancestors else -0.30)
        if self.done and not success:reward-=1.0
        return {"frame":self.frame(),"reward":reward,"event":"goal" if success else
                "timeout" if self.done else "progress" if action in self._ancestors else "distractor"}


def ancestor_closure(graph, goal):
    """Engineer-supplied public DAG feature, not a learned representation."""
    if (type(graph) is not dict or not graph or len(graph)>20 or type(goal) is not str or
            goal not in graph or any(type(k) is not str or type(v) is not list or
            any(type(x) is not str or x not in graph for x in v) or len(set(v))!=len(v)
            for k,v in graph.items())):
        raise ValueError("invalid public goal-dependency graph")
    visited=set();active=set()
    def walk(k):
        if k in active:raise ValueError("cyclic procedural graph")
        if k in visited:return
        active.add(k)
        for predecessor in graph[k]:walk(predecessor)
        active.remove(k);visited.add(k)
    for k in graph:walk(k)
    chain=set()
    def goal_walk(k):
        if k in chain:return
        chain.add(k)
        for predecessor in graph[k]:goal_walk(predecessor)
    goal_walk(goal)
    return chain


def validate_frame(frame):
    if (type(frame) is not dict or set(frame)!={"schema","family","episode_id","tick","goal",
            "prerequisites","completed","available_actions","remaining","done","scope"} or
            frame["schema"]!=FRAME_SCHEMA or frame["family"] not in FAMILIES or
            frame["scope"]!="simulation-only" or type(frame["episode_id"]) is not str or
            type(frame["tick"]) is not int or type(frame["remaining"]) is not int or
            frame["remaining"]+frame["tick"]!=MAX_STEPS or not 0<=frame["tick"]<=MAX_STEPS or
            type(frame["done"]) is not bool or type(frame["completed"]) is not list or
            type(frame["available_actions"]) is not list):
        raise ValueError("invalid public procedural frame")
    graph=frame["prerequisites"]
    closure=ancestor_closure(graph,frame["goal"])
    completed=frame["completed"]
    if (any(type(x) is not str or x not in graph for x in completed) or
            len(set(completed))!=len(completed) or len(completed)!=frame["tick"] or
            frame["done"]!=(frame["goal"] in completed or frame["tick"]==MAX_STEPS)):
        raise ValueError("inconsistent public frame history")
    for i,k in enumerate(completed):
        if any(parent not in completed[:i] for parent in graph[k]):
            raise ValueError("inconsistent completed dependency order")
    expected=[] if frame["done"] else sorted(k for k,req in graph.items() if
                     k not in completed and all(p in completed for p in req))
    if frame["available_actions"]!=expected:
        raise ValueError("forged available actions")
    return closure


def features(frame, action, *, use_ancestor=True):
    chain=validate_frame(frame)
    if type(action) is not str or action not in frame["available_actions"] or type(use_ancestor) is not bool:
        raise ValueError("invalid candidate action")
    # Deliberately engineered feature: public goal ancestry, no hidden truth.
    return f"{int(action==frame['goal'])}|{int(action in chain) if use_ancestor else 0}"


def policy_choice(frame, weights, *, use_ancestor=True, explore=None):
    if type(weights) is not dict:
        raise ValueError("invalid policy weights")
    options=frame["available_actions"]
    validate_frame(frame)
    if not options:raise ValueError("no actions available")
    if explore is not None:
        if not isinstance(explore,random.Random):raise ValueError("invalid exploration rng")
        if explore.random()<.3:
            return explore.choice(options)
    def value(name):
        wins,total=weights.get(features(frame,name,use_ancestor=use_ancestor),(0.,0))
        return (wins+0.2)/(total+1)
    return max(options,key=lambda name:(value(name),-options.index(name)))


class ProceduralSkill:
    """Learns state-action priorities from WORKSHOP only; uses no target feedback."""
    def __init__(self,seed,*,use_ancestor=True):
        if type(seed) is not int or type(use_ancestor) is not bool:raise ValueError("invalid policy")
        self.seed=seed;self.use_ancestor=use_ancestor;self.episodes=[];self.weights={}

    def _run_train(self,index):
        if type(index) is not int or index!=len(self.episodes) or index>=MAX_TRAIN:
            raise ValueError("train index out of sequence")
        world=ProceduralWorld(self.seed,"workshop","train",index)
        rng=_random(self.seed,"workshop","train",index,"policy-exploration")
        choices=[]
        while not world.done:
            f=world.frame();act=policy_choice(f,self.weights,use_ancestor=self.use_ancestor,explore=rng)
            key=features(f,act,use_ancestor=self.use_ancestor)
            result=world.step(act,expected_tick=f["tick"])
            s,n=self.weights.get(key,(0.,0));self.weights[key]=(s+result["reward"],n+1)
            choices.append(act)
        self.episodes.append(choices)
        return choices

    def train(self,episodes):
        if type(episodes) is not int or episodes<1 or len(self.episodes)+episodes>MAX_TRAIN:
            raise ValueError("invalid training budget")
        for _ in range(episodes):self._run_train(len(self.episodes))
        return self

    def choose(self,frame):
        if not self.episodes:raise ValueError("untrained skill")
        return policy_choice(frame,self.weights,use_ancestor=self.use_ancestor)

    def record(self):
        if not self.episodes:raise ValueError("no training history")
        state={"schema":MODEL_SCHEMA,"seed":self.seed,"use_ancestor":self.use_ancestor,
               "episodes":self.episodes,"weights":{k:[v[0],v[1]] for k,v in sorted(self.weights.items())}}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
                type(record["state"]) is not dict or type(record["sha256"]) is not str or
                digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid saved skill")
        state=record["state"]
        if (set(state)!={"schema","seed","use_ancestor","episodes","weights"} or
                state["schema"]!=MODEL_SCHEMA or type(state["episodes"]) is not list or
                not 1<=len(state["episodes"])<=MAX_TRAIN):
            raise ValueError("invalid skill schema")
        fresh=cls(state["seed"],use_ancestor=state["use_ancestor"])
        for i, actions in enumerate(state["episodes"]):
            if type(actions) is not list or actions!=fresh._run_train(i):
                raise ValueError("impossible stored training action")
        if fresh.record()!=record:
            raise ValueError("skill values differ from full environment replay")
        return fresh
