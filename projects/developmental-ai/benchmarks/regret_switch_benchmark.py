"""Frozen measured predictive regret switch on stochastic A->B->A->B.

Identical authored physical dynamics to the prior stochastic study, with
FRESH frozen random seeds and TEST episode indices. Each matched public
TRAIN history is acquired by an independent one-action simulator actor.
TEST metrics do not update evidence or any policy.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.regret_switch_memory import RegretSwitchMemory
from developmental_ai.prequential_ensemble_memory import PrequentialEnsembleMemory
from developmental_ai.multi_switch_memory import MultiSwitchContrastMemory
from developmental_ai.adaptive_horizon_memory import AdaptiveHorizonMemory
from developmental_ai.fast_shock_memory import FastShockMemory
from benchmarks.stochastic_prequential_benchmark import (
    STAGES, public_train, fitted, evaluate as old_evaluate,
)
from benchmarks.relation_transfer_benchmark import relation_model, summarize

SCHEMA="developmental-ai.regret-switch-benchmark/v1"
DEV=(222003,222021,222039)
ADDITIONAL=(223001,223017,223041)
CHECKPOINTS={
    "B1":(0,2,4,8,12,24,32,64),
    "return_A":(0,2,4,8,12,24,48),
    "B2":(0,2,4,8,12,24,32,64),
}
TEST_START={"B1":200000,"return_A":210000,"B2":220000}
TEST_N=16
METHODS=("regret_switch","prequential_ensemble","contrastive_multi",
         "adaptive_horizon","fast_shock","recent8","recent32",
         "frozen_A","untrained_random","always_abstain",
         "privileged_expected_oracle")


def trained(history):
    return {
        "regret_switch":fitted(RegretSwitchMemory,history),
        "prequential_ensemble":fitted(PrequentialEnsembleMemory,history),
        "contrastive_multi":fitted(MultiSwitchContrastMemory,history),
        "adaptive_horizon":fitted(AdaptiveHorizonMemory,history),
        "fast_shock":fitted(FastShockMemory,history),
        "recent8":relation_model(history[-8:]),
        "recent32":relation_model(history[-32:]),
        "frozen_A":relation_model(history[:192]),
    }


def score_one(seed,physics,index,method,policies):
    if method not in METHODS:
        raise ValueError("unfrozen regret comparator")
    if method=="regret_switch":
        return old_evaluate(seed,physics,index,"prequential_ensemble",
                            {"prequential_ensemble":policies["regret_switch"]})
    return old_evaluate(seed,physics,index,method,policies)


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("unexpected unregistered cohort")
    report={"schema":SCHEMA,
            "protocol":"benchmarks/regret_switch_protocol.json",
            "blind":False,"learner_training_actions":0,
            "test_episodes_per_checkpoint_seed":TEST_N,
            "heldout_test_indices_repeated_across_checkpoints":True,
            "rows":[]}
    for seed in seeds:
        history=[]
        training_cost={}
        stages={}
        for stage,physics,start,n in STAGES:
            batch,cost=public_train(seed,physics,start,n)
            training_cost[stage]=cost
            if stage=="A":
                history.extend(batch)
                continue
            checks={}
            for n_obs in CHECKPOINTS[stage]:
                evid=history+batch[:n_obs]
                policies=trained(evid)
                frozen={name:p.record() for name,p in policies.items()}
                selected=policies["regret_switch"].selection()[0]
                metrics={
                    method:summarize([
                        score_one(seed,physics,TEST_START[stage]+i,method,policies)
                        for i in range(TEST_N)])
                    for method in METHODS}
                if any(policies[name].record()!=snapshot
                       for name,snapshot in frozen.items()):
                    raise AssertionError("TEST data leaked into learned checkpoint")
                checks[str(n_obs)]={
                    "observed_stage_outcomes":n_obs,
                    "recorded_total":len(evid),
                    "regret_selection":selected,
                    "checkpoint_sha256":frozen["regret_switch"]["sha256"],
                    "scores":metrics,
                }
            stages[stage]=checks
            history.extend(batch)
        report["rows"].append({
            "seed":seed,"actor_training_costs":training_cost,
            "stages":stages,"final_event_count":len(history),
        })
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","additional"),
                        default="development")
    args=parser.parse_args()
    selected=DEV if args.cohort=="development" else ADDITIONAL
    print(json.dumps(measure(selected),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
