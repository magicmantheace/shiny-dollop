"""Inspected development benchmark; fresh holdout indices, not blind seeds."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.adaptive_dynamics import KnownPhysicsOracle, navigate
from developmental_ai.online_dynamics import ModelBank, fit, score, trajectory, SCHEMA

REGIMES = (("standard", "fixed"), ("high", "shifted"))


def measure(seeds=(17,23,41), train_episodes=350, train_steps=12, iterations=10,
            probe_episodes=50, navigation_episodes=100):
    result={"schema": SCHEMA, "kind":"inspected-development-not-blind",
            "seeds":list(seeds),"train_episodes_per_regime":train_episodes,
            "train_steps":train_steps,"iterations":iterations,
            "probe_episodes":probe_episodes,"navigation_episodes":navigation_episodes,
            "note":"model fitting receives only initial beacon and action/odometry/landmark history, not simulator truth",
            "rows":[]}
    with tempfile.TemporaryDirectory(prefix="devai-online-dynamics-") as folder:
        for seed in seeds:
            models={}
            losses={}
            curves={}
            for condition in REGIMES:
                histories=[trajectory(seed,"train",i,*condition,steps=train_steps) for i in range(train_episodes)]
                models[condition],curve=fit(histories,iterations=iterations)
                curves[str(condition)]=[curve[0],curve[-1]]
            with ModelBank(Path(folder)/f"{seed}.db",seed) as bank:
                for condition in REGIMES:
                    bank.save("_".join(condition),models[condition],train_episodes)
                conditions={}
                for condition in REGIMES:
                    probes=[trajectory(seed,"test",i,*condition,steps=train_steps) for i in range(probe_episodes)]
                    selection=bank.select(probes)
                    selected=bank.get(selection["selected"])
                    navigation_indices=range(1000,1000+navigation_episodes)
                    def nav(model):
                        return round(sum(navigate(model,seed,i,*condition) for i in navigation_indices)/navigation_episodes,4)
                    conditions["_".join(condition)]={
                        "selected":selection["selected"],
                        "scores":selection["mean_log_likelihoods"],
                        "selected_navigation":nav(selected),
                        "wrong_model_navigation":nav(models[REGIMES[1] if condition==REGIMES[0] else REGIMES[0]]),
                        "oracle_navigation":nav(KnownPhysicsOracle(*condition)),
                        "selected_model_probe_log_likelihood":round(score(selected,probes),6),
                        "oracle_probe_log_likelihood":round(score(KnownPhysicsOracle(*condition),probes),6)
                    }
                result["rows"].append({"seed":seed,"optimization_curve_first_last":curves,"conditions":conditions})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41])
    p.add_argument("--train-episodes",type=int,default=350)
    p.add_argument("--train-steps",type=int,default=12)
    p.add_argument("--iterations",type=int,default=10)
    p.add_argument("--probe-episodes",type=int,default=50)
    p.add_argument("--navigation-episodes",type=int,default=100)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if len(a.seeds)!=len(set(a.seeds)) or not a.seeds or min(a.train_episodes,a.train_steps,a.iterations,a.probe_episodes,a.navigation_episodes)<1:
        p.error("invalid seed list or episode counts")
    result=measure(a.seeds,a.train_episodes,a.train_steps,a.iterations,a.probe_episodes,a.navigation_episodes)
    formatted=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.out:
        a.out.write_text(formatted,encoding="utf-8")
    print(formatted,end="")


if __name__=="__main__":
    main()
