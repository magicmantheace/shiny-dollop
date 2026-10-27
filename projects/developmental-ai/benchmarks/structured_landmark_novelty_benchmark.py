"""Simulated *novel* landmark offset, unobserved by learner, structured vs full EM.

This is an inspected development benchmark, NOT an independently blind test:
the offset is selected by the benchmark, but never appears in the learner's
records. Map geometry (two sites n//2 apart) remains a strong inductive bias.
"""
from __future__ import annotations
import argparse
import json
import random
from developmental_ai.adaptive_dynamics import ACTIONS, CalibrationWorld, AdaptiveNavigator, KnownPhysicsOracle
from developmental_ai.online_dynamics import fit, score
from developmental_ai.structured_landmarks import fit_structured, SCHEMA
from developmental_ai.uncertain_navigation import seed_for

class UnseenOffsetWorld(CalibrationWorld):
    def __init__(self,seed,split,index,*,offset=3,noise="high"):
        self.unseen_offset=offset
        super().__init__(seed,split,index,noise,"fixed")
        if type(offset) is not int or offset < 0 or offset > 8:
            raise ValueError("invalid experimental offset")

    def _landmark(self):
        a,b=self.unseen_offset,(self.unseen_offset+self.n//2)%self.n
        m=0 if self.pos==a else 1 if self.pos==b else None
        draw=self.rng.random()
        if m is None:return 0 if draw < .01 else 1 if draw < .02 else None
        return m if draw < .85 else 1-m if draw < .86 else None

class OffsetOracle(KnownPhysicsOracle):
    def __init__(self,offset):
        super().__init__("high","fixed")
        self.offset=offset
    def landmark_probs(self,n,position):
        mark=0 if position==self.offset else 1 if position==(self.offset+n//2)%n else None
        return (.98,.01,.01) if mark is None else (.14,.85,.01) if mark==0 else (.14,.01,.85)


def trajectory_offset(seed,split,index,*,offset=3,steps=12):
    world=UnseenOffsetWorld(seed,split,index,offset=offset)
    start=world.initial_observation()["beacon"][0]
    rng=random.Random(seed_for(seed,split,index,"policy"))
    observations=[]
    for _ in range(steps):
        act=rng.randrange(2)
        seen,_,_,_=world.step(act)
        observations.append((ACTIONS[act],seen["odometry"],seen["landmark"]))
    return {"n":world.n,"initial":start,"observations":observations}


def navigate_offset(model,seed,index,offset):
    world=UnseenOffsetWorld(seed,"test",index,offset=offset)
    nav=AdaptiveNavigator(world.initial,world.goal,world.n,model)
    outcome=None
    while not world.done:
        action=nav.heuristic()
        obs,_,_,outcome=world.step(action)
        nav.advance(action,obs)
    return int(outcome=="success")


def measure(seeds=(17,23,41),*,offset=3,train_episodes=90,iterations=6,test_episodes=40,navigation_episodes=60):
    if (type(seeds) not in (tuple,list) or not seeds or len(set(seeds))!=len(seeds) or
            any(type(s) is not int for s in seeds) or type(offset) is not int or not 0 <= offset <= 8 or
            any(type(x) is not int or x<1 for x in (train_episodes,iterations,test_episodes,navigation_episodes))):
        raise ValueError("invalid novelty protocol")
    out={"schema":SCHEMA,"kind":"inspected-novel-layout-not-blind","offset_for_simulator_only":offset,
         "seed_list":list(seeds),"train_episodes":train_episodes,"iterations":iterations,
         "test_episodes":test_episodes,"navigation_episodes":navigation_episodes,"rows":[]}
    for seed in seeds:
        data=[trajectory_offset(seed,"train",i,offset=offset) for i in range(train_episodes)]
        test=[trajectory_offset(seed,"test",41000+i,offset=offset) for i in range(test_episodes)]
        full,_=fit(data,iterations=iterations)
        structured,_=fit_structured(data,iterations=iterations)
        models={"unconstrained_em":full,"structured_map":structured,"physics_oracle":OffsetOracle(offset)}
        out["rows"].append({"seed":seed,"learned_offsets":dict(structured.offsets),
                           "test_mean_log_likelihood":{k:round(score(m,test),5) for k,m in models.items()},
                           "navigation_success":{k:round(sum(navigate_offset(m,seed,47000+i,offset) for i in range(navigation_episodes))/navigation_episodes,5) for k,m in models.items()}})
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',nargs='+',type=int,default=[17,23,41])
    p.add_argument('--offset',type=int,default=3)
    p.add_argument('--train',type=int,default=90)
    p.add_argument('--iterations',type=int,default=6)
    p.add_argument('--test',type=int,default=40)
    p.add_argument('--navigation',type=int,default=60)
    p.add_argument('--out');a=p.parse_args()
    result=json.dumps(measure(a.seeds,offset=a.offset,train_episodes=a.train,iterations=a.iterations,test_episodes=a.test,navigation_episodes=a.navigation),indent=2,sort_keys=True)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(result)
    print(result,end='')

if __name__=='__main__':main()
