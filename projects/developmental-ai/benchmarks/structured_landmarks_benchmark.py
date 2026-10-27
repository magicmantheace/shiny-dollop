"""Observation-only structured landmark model vs unconstrained EM baseline.

Truth labels choose the simulator regime and evaluate success; neither fitter
nor navigator sees post-beacon hidden positions, realized deltas or rewards.
Development/test seeds in this file are all inspectable, not blind.
"""
from __future__ import annotations
import argparse
import json
from developmental_ai.adaptive_dynamics import KnownPhysicsOracle, navigate
from developmental_ai.online_dynamics import fit, score, trajectory
from developmental_ai.structured_landmarks import fit_structured, SCHEMA

CONDITIONS={"original":("standard","fixed"),"changed":("high","shifted")}

def measure(seeds=(17,23,41),*,train_episodes=90,test_episodes=40,iterations=6,navigation_episodes=50):
    if (type(seeds) not in (list,tuple) or not seeds or any(type(s) is not int for s in seeds) or len(set(seeds))!=len(seeds) or
            any(type(x) is not int or x<1 for x in (train_episodes,test_episodes,iterations,navigation_episodes))):
        raise ValueError("invalid protocol")
    output={"schema":SCHEMA,"kind":"inspected-development-not-blind","seeds":list(seeds),
            "train_episodes":train_episodes,"test_episodes":test_episodes,"iterations":iterations,
            "navigation_episodes":navigation_episodes,"train_split":"train/0+", "test_split":"test/28000+",
            "navigation_split":"test/34000+", "rows":[]}
    for seed in seeds:
        row={"seed":seed,"regimes":{}}
        for regime,condition in CONDITIONS.items():
            train=[trajectory(seed,"train",i,*condition) for i in range(train_episodes)]
            test=[trajectory(seed,"test",28000+i,*condition) for i in range(test_episodes)]
            reference,_=fit(train,iterations=iterations)
            structure,curve=fit_structured(train,iterations=iterations)
            models={"unconstrained_em":reference,"structured_map":structure,"physics_oracle":KnownPhysicsOracle(*condition)}
            row["regimes"][regime]={
                "learned_map_offset_by_ring":dict(structure.offsets),
                "correct_map_offset_for_scoring_only":0 if regime=="original" else 2,
                "heldout_mean_log_likelihood_per_sensor":{name:round(score(model,test),5) for name,model in models.items()},
                "navigation_success":{name:round(sum(navigate(model,seed,34000+i,*condition) for i in range(navigation_episodes))/navigation_episodes,5) for name,model in models.items()},
                "fit_curve":curve,
            }
        output["rows"].append(row)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41]);p.add_argument("--train",type=int,default=90)
    p.add_argument("--test",type=int,default=40);p.add_argument("--iterations",type=int,default=6)
    p.add_argument("--navigation",type=int,default=50);p.add_argument("--out")
    a=p.parse_args();r=measure(a.seeds,train_episodes=a.train,test_episodes=a.test,iterations=a.iterations,navigation_episodes=a.navigation)
    result=json.dumps(r,indent=2,sort_keys=True)+"\n"
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(result,encoding="utf8")
    print(result,end="")

if __name__=="__main__":main()
