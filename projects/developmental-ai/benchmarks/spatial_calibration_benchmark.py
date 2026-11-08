"""Calibration diagnostics in a known simulated ring; benchmark truth is privileged.

The learned world model sees unlabeled fit data. Temperature selection, unlike
model fitting, uses instrumented true positions from a disjoint TRAIN window.
All results are inspected development data, not blind generalization evidence.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.adaptive_dynamics import AdaptiveNavigator, CalibrationWorld, KnownPhysicsOracle
from developmental_ai.online_dynamics import fit, trajectory
from developmental_ai.spatial_calibration import SCHEMA, diagnostics, fit_profile, instrumented_stream
from developmental_ai.uncertain_navigation import seed_for
import random

REGIMES = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}


def oracle_stream(seed, first, episodes, noise, layout):
    """Oracle gets true physics but never true live position as input."""
    out = []
    for episode in range(first, first + episodes):
        world = CalibrationWorld(seed, "test", episode, noise, layout)
        nav = AdaptiveNavigator(world.initial, world.goal, world.n,
                                KnownPhysicsOracle(noise, layout))
        rng = random.Random(seed_for(seed, "test", episode, "policy"))
        for step in range(1, 13):
            action = rng.randrange(2)
            sensed, _, _, _ = world.step(action)
            nav.advance(action, sensed)
            out.append({"split": "test", "episode": episode, "step": step,
                        "posterior": nav.probs[:], "true_position": world.pos})
    return out


def measure(seeds=(17, 23, 41), *, fit_episodes=60, iterations=5,
            calibration_episodes=40, evaluation_episodes=40):
    if (type(seeds) not in (tuple, list) or not seeds or len(set(seeds)) != len(seeds) or
            any(type(s) is not int for s in seeds) or
            any(type(x) is not int or x < 1 for x in (fit_episodes, iterations, calibration_episodes, evaluation_episodes)) or
            fit_episodes > 500 or iterations > 40 or calibration_episodes > 500 or evaluation_episodes > 500):
        raise ValueError("invalid benchmark configuration")
    result={"schema": SCHEMA, "kind": "inspected-development-not-blind",
            "seeds": list(seeds), "fit_episodes": fit_episodes,
            "iterations": iterations, "calibration_episodes": calibration_episodes,
            "evaluation_episodes": evaluation_episodes,
            "windows": {"unsupervised_model_fit": "train/0+",
                        "supervised_temperature_fit": "train/5000+",
                        "read_only_evaluation": "test/40000+"},
            "notes": "Ground-truth location is revealed ONLY to offline temperature fitting and benchmark diagnostics, not the navigation filter. This is explicitly supervised calibration on a fixed ring, not self-supervised model learning. Model condition is supplied by the benchmark and not inferred at runtime.",
            "rows": []}
    for seed in seeds:
        metrics={}
        for regime, (noise, layout) in REGIMES.items():
            histories=[trajectory(seed, "train", i, noise, layout) for i in range(fit_episodes)]
            model,_=fit(histories, iterations=iterations)
            calibration=instrumented_stream(model,seed,split="train",first=5000,
                                            episodes=calibration_episodes,noise=noise,layout=layout)
            profile=fit_profile(model,calibration)
            heldout=instrumented_stream(model,seed,split="test",first=40000,
                                       episodes=evaluation_episodes,noise=noise,layout=layout)
            oracle=oracle_stream(seed,40000,evaluation_episodes,noise,layout)
            metrics[regime]={"temperature": profile["body"]["temperature"],
                             "train_calibration_nll_before": diagnostics(calibration)["nll"],
                             "train_calibration_nll_after": diagnostics(calibration,profile["body"]["temperature"])["nll"],
                             "test_uncalibrated": diagnostics(heldout),
                             "test_calibrated": diagnostics(heldout,profile["body"]["temperature"]),
                             "test_physics_oracle": diagnostics(oracle),
                             "calibration_record_count":len(calibration),
                             "test_record_count":len(heldout)}
        result["rows"].append({"seed":seed,"regimes":metrics})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41])
    p.add_argument("--fit",type=int,default=60)
    p.add_argument("--iterations",type=int,default=5)
    p.add_argument("--calibration",type=int,default=40)
    p.add_argument("--evaluation",type=int,default=40)
    p.add_argument("--out")
    a=p.parse_args()
    obj=measure(a.seeds,fit_episodes=a.fit,iterations=a.iterations,
                calibration_episodes=a.calibration,evaluation_episodes=a.evaluation)
    output=json.dumps(obj,indent=2,sort_keys=True)+"\n"
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(output,encoding="utf-8")
    print(output,end="")

if __name__=="__main__":main()
