"""Two 4-sample public-outcome windows, stationary and changed rules.

All identities in observations are per-episode random handles. Both
candidate models were trained earlier under known engineered regimes.
Calibration probes CAN be harmful and are included in the report.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.observable_affordances import ObservableWorld
from developmental_ai.two_window_confirmation import TwoWindowConfirmation
from benchmarks.observable_affordance_benchmark import DEV, RESERVED, fit, play, summary
from benchmarks.observable_reversal_calibration_benchmark import fit_reversed

SCHEMA="developmental-ai.two-window-confirmation-evaluation/v1"
CONDITIONS=("normal","reversed","normal_to_reversed","reversed_to_normal")
METHODS=("early4","confirmed8","recent8","cumulative8",
         "always_abstain","oracle")
CAL_START=960
CAL_MAX=8
TEST_START=15100
TEST_N=60


def schedule(condition,i):
    if condition not in CONDITIONS or type(i) is not int or i not in range(CAL_MAX):
        raise ValueError("invalid environment schedule")
    if condition=="normal":
        return "route"
    if condition=="reversed":
        return "route-reversed"
    if condition=="normal_to_reversed":
        return "route" if i<4 else "route-reversed"
    return "route-reversed" if i<4 else "route"


def target_world(condition):
    return schedule(condition,CAL_MAX-1)


def calibration(seed,condition,method,source,changed):
    if condition not in CONDITIONS or method not in METHODS:
        raise ValueError("invalid calibrator")
    if method in ("always_abstain","oracle"):
        return {"chosen":"abstain" if method=="always_abstain" else "oracle",
                "probes":0,"harm":0,"first":None,"recent":None,
                "contradiction":False,"sha256":None}
    obj=TwoWindowConfirmation(source,changed)
    harm=0
    budget=4 if method=="early4" else CAL_MAX
    for i in range(budget):
        world=ObservableWorld(seed,"train",CAL_START+i,schedule(condition,i))
        old=world.frame()
        action=obj.choose(old)
        now=world.step(action,old["tick"])
        observed=obj.feedback(old,action,now)
        harm+=int(observed["damage"])
    saved=obj.record(method)
    recovered=TwoWindowConfirmation.restore(source,changed,saved)
    if recovered.record(method)!=saved:
        raise AssertionError("two-window checkpoint replay differs")
    decision=obj.decision(method)
    return {"chosen":decision["choice"],"probes":budget,
            "harm":harm,"first":decision["first"],
            "recent":decision["recent"],
            "contradiction":decision["contradiction"],
            "sha256":saved["sha256"]}


def evaluation(seed,condition,selection,source,changed):
    if selection not in ("source","changed","abstain","oracle"):
        raise ValueError("invalid selected public model")
    if selection=="abstain":
        return summary([{"success":0,"hurt":0,"stalled":1,"attempts":0}
                        for _ in range(TEST_N)])
    model=source if selection=="source" else changed if selection=="changed" else None
    policy="oracle" if selection=="oracle" else "numeric_knn"
    return summary([play(seed,"test",TEST_START+i,target_world(condition),
                         policy,model) for i in range(TEST_N)])


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("frozen previously inspected cohorts only")
    result={"schema":SCHEMA,"blind":False,
            "source_train":[0,79],"reversed_train":[300,379],
            "calibration":[CAL_START,CAL_START+CAL_MAX-1],
            "test":[TEST_START,TEST_START+TEST_N-1],
            "calibration_harm_is_counted":True,"rows":[]}
    for seed in seeds:
        src,_=fit(seed)
        changed,_=fit_reversed(seed)
        frozen=(src.record(),changed.record())
        outcomes={}
        for condition in CONDITIONS:
            outcomes[condition]={}
            for method in METHODS:
                details=calibration(seed,condition,method,src,changed)
                outcomes[condition][method]={
                    "calibration":details,
                    "evaluation":evaluation(seed,condition,details["chosen"],
                                             src,changed)}
        if frozen!=(src.record(),changed.record()):
            raise AssertionError("test data contaminated source model")
        result["rows"].append({"seed":seed,"worlds":outcomes,
                               "source_sha256":frozen[0]["sha256"],
                               "changed_sha256":frozen[1]["sha256"]})
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","inspected-additional"),
                        default="development")
    opts=parser.parse_args()
    print(json.dumps(measure(DEV if opts.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
