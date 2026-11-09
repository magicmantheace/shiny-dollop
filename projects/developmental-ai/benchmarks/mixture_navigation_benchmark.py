"""Matched experimental comparison of a two-model spatial belief filter.

Model fits: only train-namespace observations, regimes GROUPED by the harness.
Agent: one-time start/goal beacon plus commands/odometry/landmarks only.
True position/regime and hidden movement remain benchmark-only scoring fields.
"""
from __future__ import annotations

import argparse
import json
import math
import random

from developmental_ai.adaptive_dynamics import AdaptiveNavigator, CalibrationWorld, KnownPhysicsOracle
from developmental_ai.mixture_navigation import MixtureNavigator, SCHEMA, probe_priors
from developmental_ai.online_dynamics import fit, trajectory
from developmental_ai.uncertain_navigation import seed_for

REGIMES={"original":("standard","fixed"),"changed":("high","shifted")}


def passive_probe(models, seed, regime_name, *, episodes):
    condition=REGIMES[regime_name]
    total=0
    sums={"mixture_brier":0.,"correct_model_brier":0.,"wrong_model_brier":0.,
          "physics_oracle_brier":0.,"mixture_true_probability":0.,"mixture_top1":0.,
          "credible80_coverage":0.,"mixture_observation_log_loss":0.}
    identified=abstained=0
    for episode in range(episodes):
        index=22000+episode
        world=CalibrationWorld(seed,"test",index,*condition)
        start,goal=world.initial_observation()["beacon"]
        mixture=MixtureNavigator(start,goal,world.n,models)
        correct=AdaptiveNavigator(start,goal,world.n,models[regime_name])
        other=AdaptiveNavigator(start,goal,world.n,models["changed" if regime_name=="original" else "original"])
        oracle=AdaptiveNavigator(start,goal,world.n,KnownPhysicsOracle(*condition))
        rng=random.Random(seed_for(seed,"test",index,"policy"))
        for _ in range(12):
            action=rng.randrange(2)
            observation,_,_,_=world.step(action)
            surprise=mixture.advance(action,observation)
            correct.advance(action,observation)
            other.advance(action,observation)
            oracle.advance(action,observation)
            truth=world.pos  # inaccessible to the navigators
            for key,belief in (("mixture_brier",mixture.probs),("correct_model_brier",correct.probs),
                               ("wrong_model_brier",other.probs),("physics_oracle_brier",oracle.probs)):
                sums[key]+=sum((p-float(i==truth))**2 for i,p in enumerate(belief))
            sums["mixture_true_probability"]+=mixture.probs[truth]
            sums["mixture_top1"]+=int(max(range(world.n),key=lambda i:mixture.probs[i])==truth)
            ranking=sorted(range(world.n),key=lambda i:(-mixture.probs[i],i))
            confidence=0.
            limit_index=world.n
            for rank,i in enumerate(ranking,1):
                confidence+=mixture.probs[i]
                if confidence>=.8-1e-12:
                    limit_index=rank
                    break
            sums["credible80_coverage"]+=int(truth in ranking[:limit_index])
            sums["mixture_observation_log_loss"]-=surprise
            total+=1
        selected=mixture.select()
        identified+=int(selected==regime_name)
        abstained+=int(selected is None)
    return {**{k:round(v/total,5) for k,v in sums.items()},
            "model_correct_at_end":identified,"model_abstained_at_end":abstained,
            "episodes":episodes,"steps":total}


def nav_success(model, seed, index, condition, *, mixture=False, priors=None):
    world=CalibrationWorld(seed,"test",index,*condition)
    initial,goal=world.initial_observation()["beacon"]
    nav=(MixtureNavigator(initial,goal,world.n,model,priors=priors) if mixture
         else AdaptiveNavigator(initial,goal,world.n,model))
    last=None
    while not world.done:
        action=nav.heuristic()
        observation,_,_,last=world.step(action)
        nav.advance(action,observation)
    return int(last=="success")


def measure(seeds=(17,23,41), *, fit_episodes=90, iterations=6,
            probe_episodes=40, nav_episodes=60):
    if (type(seeds) not in (list,tuple) or not seeds or
        any(type(s) is not int for s in seeds) or len(set(seeds))!=len(seeds) or
        any(type(x) is not int or x<=0 for x in (fit_episodes,iterations,probe_episodes,nav_episodes)) or
        fit_episodes>1000 or iterations>40 or probe_episodes>500 or nav_episodes>500):
        raise ValueError("invalid benchmark config")
    output={"schema":SCHEMA,"kind":"inspected-development-not-blind",
            "seeds":list(seeds),"fit_episodes_per_model":fit_episodes,
            "iterations":iterations,"probe_episodes":probe_episodes,
            "navigation_episodes":nav_episodes,
            "data_partitions":{"model_fitting":"train/0+","passive_probe":"test/22000+",
                               "closed_loop_navigation":"test/30000+", "probe_priors":"test/19000+"},
            "notes":"Models are pre-fitted in known regime groups (not true-position supervised). The mixture never sees the regime or positions; benchmark reads truth for metrics. Bayesian mixture assumes one regime per episode. Oracle has true physics parameters, not true live position. Seeds previously inspected; not blind.","rows":[]}
    for seed in seeds:
        models={}
        for name,condition in REGIMES.items():
            training=[trajectory(seed,"train",i,*condition) for i in range(fit_episodes)]
            models[name],_=fit(training,iterations=iterations)
        row={"seed":seed,"regimes":{}}
        for name,condition in REGIMES.items():
            passive=passive_probe(models,seed,name,episodes=probe_episodes)
            # Observation-only probe histories are disjoint from fitting and
            # navigation episodes. Do not show regime labels to probe_priors.
            probes=[trajectory(seed,"test",19000+i,*condition) for i in range(20)]
            priors=probe_priors(models,probes)
            methods={"mixture":[],"probe_informed_mixture":[],"correct_known_model":[],"wrong_known_model":[],"physics_oracle":[]}
            for i in range(nav_episodes):
                index=30000+i
                methods["mixture"].append(nav_success(models,seed,index,condition,mixture=True))
                methods["probe_informed_mixture"].append(nav_success(models,seed,index,condition,mixture=True,priors=priors))
                methods["correct_known_model"].append(nav_success(models[name],seed,index,condition))
                methods["wrong_known_model"].append(nav_success(models["changed" if name=="original" else "original"],seed,index,condition))
                methods["physics_oracle"].append(nav_success(KnownPhysicsOracle(*condition),seed,index,condition))
            row["regimes"][name]={"passive_probe":passive,
                                  "probe_priors":{k:round(v,6) for k,v in priors.items()},
                                  "navigation_success":{k:round(sum(v)/len(v),5) for k,v in methods.items()}}
        output["rows"].append(row)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41])
    p.add_argument("--fit",type=int,default=90)
    p.add_argument("--iterations",type=int,default=6)
    p.add_argument("--probe",type=int,default=40)
    p.add_argument("--navigation",type=int,default=60)
    p.add_argument("--out")
    a=p.parse_args()
    obj=measure(a.seeds,fit_episodes=a.fit,iterations=a.iterations,
                probe_episodes=a.probe,nav_episodes=a.navigation)
    output=json.dumps(obj,indent=2,sort_keys=True)+"\n"
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(output,encoding="utf-8")
    print(output,end="")

if __name__=="__main__":
    main()
