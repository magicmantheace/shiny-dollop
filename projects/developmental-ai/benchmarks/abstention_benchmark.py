"""Frozen detector vs. selective abstention on independent development and audit seeds.

Offline labels appear only in calibration and scoring. Predictions only receive
StepDetector event records; test histories never influence threshold selection.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.decision_abstention import SCHEMA, decide, train_gate, verify_gate
from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.step_dynamics import StepDetector

REGIMES = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}
ORDER = ("original", "changed", "original")


def stream(detector, seed, *, split, index_base, count):
    for phase, name in enumerate(ORDER):
        for i in range(count):
            history = trajectory(seed, split, index_base + phase * count + i, *REGIMES[name])
            detector.begin(history["n"], history["initial"])
            for observation in history["observations"]:
                yield name, detector.step(*observation)
            detector.finish()


def metrics(trials, names, gap):
    raw = {"correct":0, "wrong":0, "abstain":0}
    gated = {"correct":0, "wrong":0, "abstain":0}
    for truth, event in trials:
        for dest, selected in ((raw, event["active"]),
                               (gated, decide(event, names, gap=gap))):
            dest["abstain" if selected is None or event["status"] == "unknown" else
                 "correct" if selected == truth else "wrong"] += 1
    return {"frozen": raw, "selective": gated}


def measure(seeds=(17,23,41), *, train_episodes=130, iterations=6,
            calibration_episodes=40, phase_episodes=12, max_empirical_error=.10):
    if (not seeds or len(set(seeds)) != len(seeds)
            or any(type(seed) is not int for seed in seeds)
            or any(type(x) is not int or x <= 0 for x in
                   (train_episodes, iterations, calibration_episodes, phase_episodes))
            or train_episodes > 1000 or iterations > 50 or
            phase_episodes > 100 or calibration_episodes > 100):
        raise ValueError("invalid experiment parameters")
    result = {"schema": SCHEMA, "kind":"inspected-research-not-blind",
              "seeds": list(seeds), "train_episodes_per_model":train_episodes,
              "iterations":iterations, "calibration_episodes_per_phase":calibration_episodes,
              "evaluation_episodes_per_phase":phase_episodes,
              "fit_namespace":"train indices 0..", "calibration_namespace":"train indices 5000..",
              "evaluation_namespace":"test indices 6000..", "max_empirical_error":max_empirical_error,
              "notes":"train labels tune empirical rejection threshold only; neither test labels nor test events used in fitting; abstention counts reduce wrong outputs at a coverage cost, not a statistical safety guarantee",
              "rows":[]}
    with tempfile.TemporaryDirectory(prefix="devai-abstention-") as temp:
        for seed in seeds:
            path = Path(temp)
            with ModelBank(path / f"models-{seed}.db", seed) as bank:
                for name,condition in REGIMES.items():
                    data=[trajectory(seed,"train",i,*condition) for i in range(train_episodes)]
                    learned,_=fit(data,iterations=iterations)
                    bank.save(name,learned,len(data))
                with StepDetector(path / f"cal-{seed}.db",bank,margin=.12) as detector:
                    calibration=list(stream(detector,seed,split="train",index_base=5000,count=calibration_episodes))
                profile=train_gate(bank,[(event,truth) for truth,event in calibration],
                                   max_empirical_error=max_empirical_error)
                verified_gap=verify_gate(bank,profile)
                with StepDetector(path / f"test-{seed}.db",bank,margin=.12) as detector:
                    evaluation=list(stream(detector,seed,split="test",index_base=6000,count=phase_episodes))
                    detector.events()
                results=metrics(evaluation,REGIMES,verified_gap)
                result["rows"].append({"seed":seed,"profile":profile.as_dict(),"results":results})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41])
    p.add_argument("--train-episodes",type=int,default=130)
    p.add_argument("--iterations",type=int,default=6)
    p.add_argument("--calibration-episodes",type=int,default=40)
    p.add_argument("--phase-episodes",type=int,default=12)
    p.add_argument("--max-empirical-error",type=float,default=.10)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    result=measure(a.seeds,train_episodes=a.train_episodes,iterations=a.iterations,
                   calibration_episodes=a.calibration_episodes,phase_episodes=a.phase_episodes,
                   max_empirical_error=a.max_empirical_error)
    output=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.out:a.out.write_text(output,encoding="utf-8")
    print(output,end="")

if __name__=="__main__":main()
