"""Independent sandbox feature worlds for known noisy and unseen third rules.

This is a hand-designed synthetic experiment. Rule names, action meanings,
and the noise switch stay inside this simulator. No action-name-derived
numeric identity is available in public observations. No external actions.
"""
from __future__ import annotations

import random

from developmental_ai.observable_affordances import SCHEMA as FRAME_SCHEMA, check, digest

WORLD_SCHEMA="developmental-ai.new-feature-rule-simulator/v1"
CONDITIONS=("normal_noisy","reversed_noisy","third_rule")
GOAL=4
BUDGET=7


class NovelFeatureWorld:
    def __init__(self,seed,split,index,condition):
        if (type(seed) is not int or split not in ("train","test")
            or type(index) is not int or not 0<=index<100000
            or condition not in CONDITIONS):
            raise ValueError("invalid synthetic environment")
        self.condition=condition  # SIMULATOR ONLY
        self.episode=digest([WORLD_SCHEMA,seed,split,index])
        rng=random.Random(int(self.episode[:16],16))
        lattice=[(a,b) for a in range(9) for b in range(9)]
        high=[x for x in lattice if x[1]>=x[0]+2]
        low=[x for x in lattice if x[0]>=x[1]+2]
        middle=[x for x in lattice if abs(x[0]-x[1])<=1]
        # Exactly four feasible progress actions under EACH hidden law.
        features=rng.sample(high,4)+rng.sample(low,4)+rng.sample(middle,4)
        rng.shuffle(features)
        handles=[f"a_{rng.getrandbits(72):018x}" for _ in features]
        if len(handles)!=len(set(handles)):
            raise RuntimeError("opaque action collision")
        self._features=dict(zip(handles,features))
        self._used=set()
        self.tick=0
        self.progress=0
        self.damage=0
        self.done=False

    def frame(self):
        rows=([{"id":name,"features":list(pair)}
               for name,pair in self._features.items() if name not in self._used]
              if not self.done else [])
        return check({"schema":FRAME_SCHEMA,"episode":self.episode,
                      "tick":self.tick,"budget":BUDGET,"sensors":[self.progress,self.damage],
                      "goal":GOAL,"actions":rows,"done":self.done})

    def _effect(self,action):
        x,y=self._features[action]
        if self.condition=="third_rule":
            if abs(x-y)<=1:
                return "progress"
            if x+y>=10:
                return "damage"
            return "neutral"
        if self.condition=="normal_noisy":
            label=("progress" if y>=x+2 else "damage" if x>=y+2 else "neutral")
        else:
            label=("progress" if x>=y+2 else "damage" if y>=x+2 else "neutral")
        # Deterministic 10% independent per-event perturbation to neutral.
        if (label!="neutral" and int(digest([WORLD_SCHEMA,self.episode,action,
                                             self.tick,"noise"])[:8],16)%100<10):
            return "neutral"
        return label

    def step(self,action,tick):
        if (self.done or type(tick) is not int or tick!=self.tick
            or type(action) is not str or action not in self._features
            or action in self._used):
            raise ValueError("stale or invalid action")
        effect=self._effect(action)
        self._used.add(action)
        self.tick+=1
        if effect=="progress":
            self.progress+=1
        elif effect=="damage":
            self.damage+=1
        self.done=(self.damage>0 or self.progress>=GOAL or
                   self.tick>=BUDGET or len(self._used)==len(self._features))
        return self.frame()

    def success(self):
        return self.progress>=GOAL and self.damage==0
