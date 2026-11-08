"""No-cue controlled diagnostic: A-B-A retention without a regime beacon.

Both known environments are separately trained first. The experimental
policy receives only `ShiftedCargo.frame()["public"]`: numeric sensor
readings, anonymous action handles, stable engineered identity descriptors.
It does not receive a phase label, context cue, or hidden action recipe.

All six seeds were previously INSPECTED, including the reserved group.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.contextual_affordance import CUES, ContextMemory, ShiftedCargo, key
from developmental_ai.affordance_memory import FilteredNovel, record_step
from developmental_ai.no_cue_diagnostic import NoCueProbe, select_probe
from developmental_ai.outcome_skills import canonical
from benchmarks.contextual_affordance_benchmark import (
    DEVELOPMENT, RESERVED, TRAIN_N, TEST_N, fit, trial as old_trial
)

SCHEMA="developmental-ai.no-cue-diagnostic-evaluation/v1"
PERIODS=(("A",8700),("B",8700),("A_return",8800))
METHODS=("no_cue","probe_then_A","frozen_A","frozen_B","novel",
         "beacon_upper","privileged_risk_oracle")


def run(seed,split,index,phase,method,memories):
    if method not in METHODS or phase not in CUES:
        raise ValueError("invalid diagnostic test")
    if not isinstance(memories,ContextMemory):
        raise ValueError("two fitted training histories are mandatory")
    if method in ("beacon_upper","privileged_risk_oracle"):
        privileged_method="context" if method=="beacon_upper" else "risk_oracle"
        row=old_trial(seed,split,index,phase,privileged_method,memories)
        return {**row,"diagnosed":None,"probe":0,
                "correct":None,"abstained":0}

    world=ShiftedCargo(seed,split,index,phase)
    no_cue=(NoCueProbe(memories) if method in ("no_cue","probe_then_A") else None)
    if method=="frozen_A":
        controller=FilteredNovel(memories.choose_memory(CUES["A"]))
    elif method=="frozen_B":
        controller=FilteredNovel(memories.choose_memory(CUES["B"]))
    elif method=="novel":
        controller=FilteredNovel()
    else:
        controller=None
    probes=0
    failed=0
    spoiled=0
    prefix=None
    for step in range(18):
        public=world.frame()["public"]  # explicitly STRIP simulator cue
        if public["base"]["done"]:
            break
        if no_cue is not None and (method=="no_cue" or prefix is None):
            action=no_cue.choose(public)
        else:
            action=controller.choose(public)
        if action is None:
            break
        # Used for benchmark scoring ONLY, never policy or training inference.
        hidden_name=world.world.base._lookup[action]
        response=world.step(action,public["base"]["tick"])
        after=response["frame"]["public"]  # NO cue passed to policy
        if no_cue is not None and (method=="no_cue" or prefix is None):
            no_cue.feedback(public,action,response["accepted"],after)
            if step==0 and no_cue.diagnostic is not None and no_cue._probe_action is not None:
                probes+=1
            if method=="probe_then_A" and prefix is None:
                # Identical public diagnostic intervention, then *ignore*
                # the inferred context and always use frozen A memory.
                controller=FilteredNovel(memories.choose_memory(CUES["A"]))
                controller.history=list(no_cue._controller.history)
                prefix=True
        else:
            controller.feedback(public,action,response["accepted"],after)
        failed+=int(not response["accepted"])
        spoiled+=int(hidden_name=="spoil" and response["accepted"])
    if no_cue is not None:
        diagnosed=no_cue.selected
        if method=="no_cue" and no_cue.events:
            recovered=NoCueProbe.restore(memories,no_cue.record())
            if recovered.record()!=no_cue.record():
                raise AssertionError("diagnostic replay differs from observed run")
            if not world.world.base.done:
                if recovered.choose(world.frame()["public"])!=no_cue.choose(world.frame()["public"]):
                    raise AssertionError("diagnostic process restart changed next decision")
    else:
        diagnosed=None
    return {"success":int(world.success()),
            "attempts":world.world.base.tick,"blocked":failed,
            "spoilage":spoiled,"stalled":int(not world.world.base.done),
            "probe":probes,"diagnosed":diagnosed,
            "correct":int(diagnosed==key(CUES[phase])) if diagnosed is not None else None,
            "abstained":int(no_cue is not None and probes==0)}


def summarise(rows):
    return {"successes":sum(x["success"] for x in rows),
            "episodes":len(rows),
            "spoilage":sum(x["spoilage"] for x in rows),
            "mean_attempts":round(sum(x["attempts"] for x in rows)/len(rows),3),
            "mean_blocked":round(sum(x["blocked"] for x in rows)/len(rows),3),
            "stalled":sum(x["stalled"] for x in rows),
            "probed":sum(x["probe"] for x in rows),
            "correct_when_selected":sum(x["correct"] or 0 for x in rows),
            "abstentions":sum(x["abstained"] for x in rows)}


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,RESERVED):
        raise ValueError("all original cohorts fixed and already inspected")
    result={"schema":SCHEMA,"blind":False,"runtime_context_cue":False,
            "engineered_action_identity":True,
            "training":{"A":[0,TRAIN_N-1],"B":[300,300+TRAIN_N-1]},
            "evaluation":{name:[start,start+TEST_N-1] for name,start in PERIODS},
            "rows":[]}
    for seed in seeds:
        a,_=fit(seed,"A")
        b,_=fit(seed,"B")
        memories=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        snapshot=memories.record()
        descriptor=select_probe(memories)
        evaluations={}
        for period,start in PERIODS:
            true_phase="A" if period.startswith("A") else "B"
            evaluations[period]={}
            for method in METHODS:
                outcomes=[run(seed,"test",start+i,true_phase,method,memories)
                          for i in range(TEST_N)]
                evaluations[period][method]=summarise(outcomes)
        if memories.record()!=snapshot:
            raise AssertionError("evaluation updated source learning")
        result["rows"].append({"seed":seed,"diagnostic":descriptor,
                               "source_sha256":snapshot["sha256"],
                               "scores":evaluations})
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","inspected-additional"),default="development")
    a=p.parse_args()
    print(json.dumps(measure(DEVELOPMENT if a.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
