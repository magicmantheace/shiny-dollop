"""Precommitted disjoint adequacy validation versus XOR and conditional laws.

Fresh, frozen seed cohorts; no TEST outcome enters training or selection.
An abstention fails the task even if damage is avoided. Every source-actor
TRAIN action is counted exactly once, separately from held-out TEST damage.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.validated_abstention_memory import ValidatedAbstainingMemory
from developmental_ai.gated_composition_memory import GatedCompositionMemory
from developmental_ai.composed_feature_memory import ComposedFeatureMemory
from developmental_ai.feature_hypothesis_memory import _Bucket
from developmental_ai.observable_affordances import digest
from benchmarks.gated_composition_benchmark import (
    ConditionalWorld, _XorPredictor, training, fitted
)
from benchmarks.variable_affordance_benchmark import public_outcome

SCHEMA="developmental-ai.validated-abstention-benchmark/v1"
DEV=(262003,262021,262039)
ADDITIONAL=(263001,263017,263041)
STAGES=(("source","source",1000,240),
        ("conditional","conditional",2000,128),
        ("return_source","source",3000,64),
        ("xor","xor",4000,128))
CHECKPOINTS={
    "conditional":(0,8,16,24,32,48,64,96,128),
    "return_source":(0,8,16,24,32,48,64),
    "xor":(0,8,16,24,32,48,64,96,128),
}
TEST_START={"conditional":320000,"return_source":330000,"xor":340000}
TEST_N=16
METHODS=(
    "validated_abstain","always_act_gated","always_act_global",
    "frozen_source","recent32_span","privileged_known_xor",
    "always_abstain","random","perfect_action_oracle",
)


def models(history):
    return {
        "validated_abstain":fitted(ValidatedAbstainingMemory,history),
        "always_act_gated":fitted(GatedCompositionMemory,history),
        "always_act_global":fitted(ComposedFeatureMemory,history),
        "frozen_source":_Bucket("span",history[:192]),
        "recent32_span":_Bucket("span",history[-32:]),
        "privileged_known_xor":_XorPredictor(history[-64:]),
    }


def evaluate(seed,law,index,method,fitted_models):
    if method not in METHODS:
        raise ValueError("policy absent from precommitted comparison")
    world=ConditionalWorld(seed,"test",index,law)
    rand=random.Random(int(digest(["validated-test-random",world.episode])[:16],16))
    damage=0
    abstained=0
    for _ in range(world.budget):
        frame=world.frame()
        if frame["done"]:
            break
        if method in fitted_models:
            action=fitted_models[method].choose(frame)
        elif method=="always_abstain":
            action=None
        elif method=="random":
            action=rand.choice(frame["actions"])["id"]
        else:
            action=next((a["id"] for a in frame["actions"]
                         if world._effect(a["features"])=="progress"),None)
        if action is None:
            abstained=1
            break
        after=world.step(action,frame["tick"])
        damage+=int(public_outcome(frame,action,after)["damage"])
    return {"success":int(world.success()),
            "harmful_actions":damage,
            "abstained":abstained,
            "attempted":int(world.tick>0),
            "actions":world.tick}


def summarize(records):
    return {
        "successes":sum(t["success"] for t in records),
        "harmful_actions":sum(t["harmful_actions"] for t in records),
        "abstained":sum(t["abstained"] for t in records),
        "attempted_tasks":sum(t["attempted"] for t in records),
        "executed_actions":sum(t["actions"] for t in records),
    }


def measure(cohort=DEV):
    if type(cohort) not in (tuple,list) or tuple(cohort) not in (DEV,ADDITIONAL):
        raise ValueError("seed cohort outside precommit")
    report={
        "schema":SCHEMA,
        "protocol":"benchmarks/validated_abstention_protocol.json",
        "blind":False,"learner_training_actions":0,
        "heldout_TEST_indices_reused_across_checkpoints":True,
        "test_episodes_per_seed_checkpoint":TEST_N,
        "rows":[],
    }
    for seed in cohort:
        past=[]
        actor_cost={}
        results={}
        for stage,law,first,n in STAGES:
            sample,cost=training(seed,law,first,n)
            actor_cost[stage]=cost
            if stage=="source":
                past.extend(sample)
                continue
            checkpoints={}
            for count in CHECKPOINTS[stage]:
                observed=past+sample[:count]
                policies=models(observed)
                records={name:policy.record() for name,policy in policies.items()
                         if hasattr(policy,"record")}
                confidence=policies["validated_abstain"].selection()[0]
                metrics={
                    method:summarize([
                        evaluate(seed,law,TEST_START[stage]+idx,method,policies)
                        for idx in range(TEST_N)])
                    for method in METHODS
                }
                if any(policies[name].record()!=previous
                       for name,previous in records.items()):
                    raise AssertionError("TEST data contaminated training model")
                checkpoints[str(count)]={
                    "new_public_observations":count,
                    "total_public_observations":len(observed),
                    "validation":confidence,
                    "checkpoint_sha256":records["validated_abstain"]["sha256"],
                    "scores":metrics,
                }
            results[stage]=checkpoints
            past.extend(sample)
        report["rows"].append({
            "seed":seed,"external_actor_cost":actor_cost,
            "stages":results,"full_public_history_count":len(past)})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),
                   default="development")
    opts=p.parse_args()
    selected=DEV if opts.cohort=="development" else ADDITIONAL
    print(json.dumps(measure(selected),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
