"""Public-outcome calibration after reversed numeric-feature consequences.

Two TRAIN-only kNN models (normal source, changed outcome rule); 12 separate
disposable training episodes supply one public action/outcome each to a
replay-verified model selector. All test episodes remain read-only.
The calibration episodes may incur simulated harm; they are NEVER a
recommendation to experiment on a live system.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.observable_affordances import (
    ObservableWorld, NumericOutcomeMemory,
)
from developmental_ai.observable_reversal_calibration import OutcomeCalibration
from benchmarks.observable_affordance_benchmark import (
    DEV, RESERVED, fit, play, summary,
)

SCHEMA = "developmental-ai.observable-reversal-calibration-evaluation/v1"
WORLDS = ("route", "route-reversed")
METHODS = ("offline_selected","source_only","changed_only",
           "wrong_calibration","always_abstain","untrained_random","oracle")
TRAIN_START = 300
TRAIN_N = 80
CALIBRATION_START = 900
CALIBRATION_N = 12
TEST_START = 14000
TEST_N = 60


def fit_reversed(seed):
    changed = NumericOutcomeMemory()
    outcomes=[]
    for i in range(TRAIN_N):
        result, events=play(seed,"train",TRAIN_START+i,"route-reversed",
                            "random",collect=True)
        for event in events:
            changed.add(event)
        outcomes.append(result)
    if NumericOutcomeMemory.restore(changed.record()).record()!=changed.record():
        raise AssertionError("changed model did not replay")
    return changed,summary(outcomes)


def calibrate(seed,world,source,changed):
    if world not in WORLDS:
        raise ValueError("invalid offline calibration world")
    policy=OutcomeCalibration(source,changed)
    hurt=0
    for i in range(CALIBRATION_N):
        simulated=ObservableWorld(seed,"train",CALIBRATION_START+i,world)
        before=simulated.frame()
        action=policy.probe(before)
        after=simulated.step(action,before["tick"])
        event=policy.observe(before,action,after)
        hurt+=int(event["damage"])
    record=policy.record()
    recovered=OutcomeCalibration.restore(source,changed,record)
    if recovered.record()!=record:
        raise AssertionError("calibration restart changed outcome history")
    return recovered,{"decision":recovered.decision(),
                      "harmful_calibration_probes":hurt,
                      "record_sha256":record["sha256"]}


def score_policy(seed,world,method,source,changed,decisions):
    if method not in METHODS or world not in WORLDS:
        raise ValueError("invalid frozen test method")
    if method=="offline_selected":
        choice=decisions[world]["decision"]["chosen"]
    elif method=="wrong_calibration":
        opposite="route-reversed" if world=="route" else "route"
        choice=decisions[opposite]["decision"]["chosen"]
    elif method=="source_only":
        choice="source"
    elif method=="changed_only":
        choice="changed"
    elif method=="always_abstain":
        choice="abstain"
    elif method=="untrained_random":
        choice="random"
    else:
        choice="oracle"
    model=source if choice=="source" else changed if choice=="changed" else None
    if choice=="abstain":
        return {**summary([{"success":0,"hurt":0,"stalled":1,"attempts":0}
                          for _ in range(TEST_N)]),
                "chosen":choice}
    method_name=("numeric_knn" if choice in ("source","changed")
                 else "oracle" if choice=="oracle" else "random")
    result=[play(seed,"test",TEST_START+i,world,method_name,model)
            for i in range(TEST_N)]
    return {**summary(result),"chosen":choice}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("only frozen already inspected cohorts allowed")
    report={"schema":SCHEMA,"blind":False,"source_training":[0,79],
            "changed_training":[TRAIN_START,TRAIN_START+TRAIN_N-1],
            "calibration_indices":[CALIBRATION_START,
                                   CALIBRATION_START+CALIBRATION_N-1],
            "test_indices":[TEST_START,TEST_START+TEST_N-1],
            "engineered_numeric_features":True,
            "offline_disposable_harm_counts":True,"rows":[]}
    for seed in seeds:
        source,source_training=fit(seed)
        changed,changed_training=fit_reversed(seed)
        before_source=source.record()
        before_changed=changed.record()
        evidence={}
        for world in WORLDS:
            _,evidence[world]=calibrate(seed,world,source,changed)
        results={}
        for world in WORLDS:
            results[world]={method:score_policy(
                seed,world,method,source,changed,evidence)
                for method in METHODS}
        if source.record()!=before_source or changed.record()!=before_changed:
            raise AssertionError("held-out evaluation mutated trained model")
        report["rows"].append({
            "seed":seed,"source_training":source_training,
            "changed_training":changed_training,
            "calibration":evidence,
            "source_sha256":before_source["sha256"],
            "changed_sha256":before_changed["sha256"],
            "scores":results})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","inspected-additional"),
                   default="development")
    a=p.parse_args()
    print(json.dumps(measure(DEV if a.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
