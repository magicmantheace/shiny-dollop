"""Frozen independent-witness recovery experiment with acquisition accounting.

Witnesses are an externally authorized simulated random actor, NOT passive
sensors nor cost-free observations. The learner never acts to collect them.
Witness eligibility comes from public-model adequacy only, never TEST frames
or TEST outcomes. Fresh per-stage-checkpoint actor episodes are reused across
the same 16 read-only target tasks and counted just once.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.witness_recovery_memory import WitnessRecoveryMemory,BATCH,MAX_WITNESS
from developmental_ai.observable_affordances import digest
from benchmarks.gated_composition_benchmark import training
from benchmarks.validated_abstention_benchmark import (
    STAGES,models as old_models,evaluate as old_evaluate,summarize
)

SCHEMA="developmental-ai.independent-witness-benchmark/v1"
DEV=(272003,272021,272039)
ADDITIONAL=(273001,273017,273041)
CHECKPOINTS={
    "conditional":(0,8,16,32,64,96),
    "return_source":(0,8,16,32,64),
    "xor":(0,8,16,32,64,96),
}
START={"conditional":350000,"return_source":360000,"xor":370000}
STAGE_INDEX={"conditional":1,"return_source":2,"xor":3}
TEST_N=16
METHODS=("witness_recovery","selective_no_witness",
         "always_act_gated","frozen_source","always_abstain",
         "privileged_known_xor","perfect_action_oracle")


def fresh_witness(history):
    policy=WitnessRecoveryMemory()
    for row in history:
        policy.observe(row)
    return WitnessRecoveryMemory.restore(policy.record())


def witnesses(seed,stage,law,checkpoint_index,trained):
    """Offer 8-at-a-time actor reports, paying for *every* new actor action."""
    initial=trained.selection()[0]["meets_adequacy_gate"]
    cost={"observations":0,"harmful":0,"productive":0,"neutral":0}
    requested=0
    ordinal=STAGE_INDEX[stage]
    while trained.can_request_witness():
        if requested>=MAX_WITNESS//BATCH:
            raise AssertionError("witness budget not enforced")
        index=500000+ordinal*10000+checkpoint_index*100+requested*BATCH
        batch,paid=training(seed,law,index,BATCH)
        trained.accept_witness(batch)
        for key in cost:
            cost[key]+=paid[key]
        requested+=1
    return {
        "initial_model_adequate":initial,
        "final_model_adequate":trained.selection()[0]["meets_adequacy_gate"],
        "witness_batches":requested,
        "witness_cost":cost,
        "witness_budget_exhausted":(
            cost["observations"]==MAX_WITNESS and
            not trained.selection()[0]["meets_adequacy_gate"]
        ),
    }


def eval_policy(seed,law,index,method,policies):
    if method not in METHODS:
        raise ValueError("unregistered witness recovery comparator")
    if method=="witness_recovery":
        return old_evaluate(seed,law,index,"validated_abstain",
                            {"validated_abstain":policies["witness_recovery"]})
    if method=="selective_no_witness":
        return old_evaluate(seed,law,index,"validated_abstain",
                            {"validated_abstain":policies["selective_no_witness"]})
    if method=="always_abstain":
        return old_evaluate(seed,law,index,"always_abstain",{})
    return old_evaluate(seed,law,index,method,policies)


def measure(cohort=DEV):
    if type(cohort) not in (tuple,list) or tuple(cohort) not in (DEV,ADDITIONAL):
        raise ValueError("unfrozen independent-witness cohort")
    output={
        "schema":SCHEMA,
        "protocol":"benchmarks/independent_witness_protocol.json",
        "blind":False,
        "learner_initiated_training_actions":0,
        "actor_actions_are_harmful_and_costed":True,
        "heldout_TEST_indices_repeated_across_checkpoints":True,
        "test_tasks_per_seed_checkpoint":TEST_N,
        "rows":[],
    }
    for seed in cohort:
        history=[]
        source_cost={}
        phase_results={}
        for stage,law,first,length in STAGES:
            batch,paid=training(seed,law,first,length)
            source_cost[stage]=paid
            if stage=="source":
                history.extend(batch)
                continue
            results={}
            for ordinal,n in enumerate(CHECKPOINTS[stage]):
                public=history+batch[:n]
                baselines=old_models(public)
                policy=fresh_witness(public)
                trace=witnesses(seed,stage,law,ordinal,policy)
                baselines["witness_recovery"]=policy
                baselines["selective_no_witness"]=baselines["validated_abstain"]
                snapshot={name:m.record() for name,m in baselines.items()
                          if hasattr(m,"record")}
                scores={
                    name:summarize([
                        eval_policy(seed,law,START[stage]+j,name,baselines)
                        for j in range(TEST_N)
                    ])
                    for name in METHODS}
                if any(baselines[name].record()!=before
                       for name,before in snapshot.items()):
                    raise AssertionError("read-only TEST outcome contaminated learner")
                results[str(n)]={
                    "original_observations_into_stage":n,
                    "witness":trace,
                    "public_report_count_after_witness":len(policy.events),
                    "checkpoint_sha256":snapshot["witness_recovery"]["sha256"],
                    "scores":scores,
                }
            phase_results[stage]=results
            history.extend(batch)
        output["rows"].append({
            "seed":seed,"base_training_actor_cost":source_cost,
            "stages":phase_results,
            "base_public_events":len(history),
        })
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","additional"),
                        default="development")
    x=parser.parse_args()
    print(json.dumps(measure(DEV if x.cohort=="development" else ADDITIONAL),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
