"""Post-hoc sequential public-outcome calibration with full harm accounting.

Reuse the original frozen pair of numeric-outcome models and thresholds.
Calibration can stop once sufficient evidence appears; a regime switch
AFTER the stopping point is a deliberate adverse control. Each probe
still acts in a disposable simulation and may cause irreversible damage.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.observable_affordances import ObservableWorld
from developmental_ai.observable_reversal_calibration import OutcomeCalibration
from benchmarks.observable_affordance_benchmark import DEV, RESERVED, fit, play, summary
from benchmarks.observable_reversal_calibration_benchmark import (
    fit_reversed, WORLDS, TEST_N
)

SCHEMA="developmental-ai.sequential-reversal-budget/v1"
METHODS=("adaptive_stop","fixed12","forced4",
         "stale_shift_adaptive","stale_shift_fixed12",
         "always_abstain","privileged_oracle")
CAL_START=900
CAL_MAX=12
EARLIEST=4
TEST_START=15000


def calibrate(seed,world,source,changed,method):
    if world not in WORLDS or method not in METHODS[:5]:
        raise ValueError("invalid calibration configuration")
    agent=OutcomeCalibration(source,changed)
    harm=0
    for i in range(CAL_MAX):
        # Deliberate adverse condition: early evidence from one regime
        # can become invalid after a physical-rule reversal. Phase labels
        # occur ONLY in the simulator harness, not policy observations.
        current=("route" if i<EARLIEST else "route-reversed") if method.startswith("stale_shift") else world
        sim=ObservableWorld(seed,"train",CAL_START+i,current)
        before=sim.frame()
        action=agent.probe(before)
        after=sim.step(action,before["tick"])
        e=agent.observe(before,action,after)
        harm+=int(e["damage"])
        if method=="forced4" and i+1>=EARLIEST:
            break
        if method in ("adaptive_stop","stale_shift_adaptive") and i+1>=EARLIEST:
            if agent.decision()["chosen"]!="abstain":
                break
    saved=agent.record()
    if OutcomeCalibration.restore(source,changed,saved).record()!=saved:
        raise AssertionError("sequential calibration history did not replay")
    return {"choice":agent.decision()["chosen"],"probes":len(agent.events),
            "calibration_harm":harm,"log_margin":agent.decision()["log_margin"],
            "sha256":saved["sha256"]}


def evaluate(seed,world,model_choice,source,changed):
    if model_choice not in ("source","changed","abstain","oracle"):
        raise ValueError("invalid held-out calibration selection")
    if model_choice=="abstain":
        return {**summary([{"success":0,"hurt":0,"stalled":1,"attempts":0}
                           for _ in range(TEST_N)]),
                "chosen":model_choice}
    model=source if model_choice=="source" else changed if model_choice=="changed" else None
    policy="oracle" if model_choice=="oracle" else "numeric_knn"
    trials=[play(seed,"test",TEST_START+i,world,policy,model)
            for i in range(TEST_N)]
    return {**summary(trials),"chosen":model_choice}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("predeclared inspected seed cohorts only")
    result={"schema":SCHEMA,"blind":False,
            "source_training":[0,79],"changed_training":[300,379],
            "calibration_indices":[CAL_START,CAL_START+CAL_MAX-1],
            "test_indices":[TEST_START,TEST_START+TEST_N-1],
            "probe_damage_disclosed":True,"rows":[]}
    for seed in seeds:
        source,_=fit(seed)
        changed,_=fit_reversed(seed)
        snapshots=(source.record(),changed.record())
        worlds={}
        for world in WORLDS:
            methods={}
            for mode in METHODS:
                if mode in ("always_abstain","privileged_oracle"):
                    calib={"choice":"abstain" if mode=="always_abstain" else "oracle",
                           "probes":0,"calibration_harm":0,
                           "log_margin":0.0,"sha256":None}
                else:
                    calib=calibrate(seed,world,source,changed,mode)
                methods[mode]={"calibration":calib,
                               "evaluation":evaluate(seed,world,calib["choice"],
                                                     source,changed)}
            worlds[world]=methods
        if snapshots!=(source.record(),changed.record()):
            raise AssertionError("read-only calibration/test mutated learned models")
        result["rows"].append({"seed":seed,"worlds":worlds,
                               "source_sha256":snapshots[0]["sha256"],
                               "changed_sha256":snapshots[1]["sha256"]})
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","inspected-additional"),
                   default="development")
    args=p.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
