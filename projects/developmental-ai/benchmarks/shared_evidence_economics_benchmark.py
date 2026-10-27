"""Frozen economic comparison: new witness actions versus one shared observation bank.

A shared bank is collected by an independent TRAIN-split actor *once* at
the beginning of each private phase. It is NOT free/passive evidence:
all 32 upstream actor actions are counted even if no policy consumes them.
Checkpoint scenarios are independent counterfactual evaluations with
repeated held-out TEST indices, not sequential deployments.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.witness_recovery_memory import BATCH, MAX_WITNESS
from benchmarks.gated_composition_benchmark import training
from benchmarks.independent_witness_benchmark import fresh_witness
from benchmarks.validated_abstention_benchmark import (
    STAGES, models as baseline_models, evaluate as old_evaluate, summarize,
)

SCHEMA="developmental-ai.shared-evidence-economics-benchmark/v1"
DEV=(282003,282021,282039)
ADDITIONAL=(283001,283017,283041)
CHECKPOINTS={
    "conditional":(0,8,16,32,64,96),
    "return_source":(0,8,16,32,64),
    "xor":(0,8,16,32,64,96),
}
STAGE_NUM={"conditional":1,"return_source":2,"xor":3}
TEST_START={"conditional":410000,"return_source":420000,"xor":430000}
TEST_N=16
METHODS=("no_extra_evidence","fresh_witness","shared_bank",
         "always_act_gated","always_abstain","frozen_source",
         "privileged_known_xor","perfect_action_oracle")
COST_DAMAGE=10
COST_ABSTAIN=1
COST_EXTRA_ACTION=1


def zero_cost():
    return {"observations":0,"harmful":0,"productive":0,"neutral":0}


def add_cost(total,part):
    for key in total:
        total[key]+=part[key]


def feed_bank(learner,bank):
    """Offer cached public events with no new intervention at consumption."""
    accepted=0
    while learner.can_request_witness():
        if accepted+BATCH>len(bank):
            raise AssertionError("out of previously recorded bank evidence")
        learner.accept_witness(bank[accepted:accepted+BATCH])
        accepted+=BATCH
    return {
        "accepted_records":accepted,
        "model_adequate_after":learner.selection()[0]["meets_adequacy_gate"],
    }


def collect_on_demand(seed,stage,law,checkpoint_ordinal,learner):
    """Fresh external first-action interventions, budgeted separately."""
    cost=zero_cost()
    fetched=0
    while learner.can_request_witness():
        if fetched+BATCH>MAX_WITNESS:
            raise AssertionError("witness budget incorrectly exceeded")
        index=(650000+STAGE_NUM[stage]*10000+
               checkpoint_ordinal*100+fetched)
        public,batch_cost=training(seed,law,index,BATCH)
        learner.accept_witness(public)
        add_cost(cost,batch_cost)
        fetched+=BATCH
    return {
        "accepted_records":fetched,
        "external_actor_cost":cost,
        "model_adequate_after":learner.selection()[0]["meets_adequacy_gate"],
    }


def evaluate(seed,law,episode,method,models):
    if method not in METHODS:
        raise ValueError("unregistered policy")
    if method in ("no_extra_evidence","fresh_witness","shared_bank"):
        return old_evaluate(seed,law,episode,"validated_abstain",
                            {"validated_abstain":models[method]})
    return old_evaluate(seed,law,episode,method,models)


def study_costs(rows):
    """Author-fixed study loss; hold-out checkpoints not independent."""
    totals={name:{"successes":0,"harmful_TEST_actions":0,
                  "failed_by_abstention":0,"extra_actor_actions":0,
                  "extra_actor_harm":0} for name in METHODS}
    for row in rows:
        for stage in ("conditional","return_source","xor"):
            bank_cost=row["bank_actor_cost"][stage]
            totals["shared_bank"]["extra_actor_actions"]+=bank_cost["observations"]
            totals["shared_bank"]["extra_actor_harm"]+=bank_cost["harmful"]
            for k in CHECKPOINTS[stage]:
                check=row["stages"][stage][str(k)]
                on_demand=check["fresh_actor_cost"]
                totals["fresh_witness"]["extra_actor_actions"]+=on_demand["observations"]
                totals["fresh_witness"]["extra_actor_harm"]+=on_demand["harmful"]
                for name in METHODS:
                    score=check["scores"][name]
                    totals[name]["successes"]+=score["successes"]
                    totals[name]["harmful_TEST_actions"]+=score["harmful_actions"]
                    totals[name]["failed_by_abstention"]+=score["abstained"]
    for val in totals.values():
        val["precommitted_study_loss"]=(
            COST_DAMAGE*(val["harmful_TEST_actions"]+val["extra_actor_harm"])
            + COST_ABSTAIN*val["failed_by_abstention"]
            + COST_EXTRA_ACTION*val["extra_actor_actions"])
    return totals


def measure(cohort=DEV):
    if type(cohort) not in (tuple,list) or tuple(cohort) not in (DEV,ADDITIONAL):
        raise ValueError("seed cohort not precommitted")
    report={
        "schema":SCHEMA,
        "protocol":"benchmarks/shared_evidence_economics_protocol.json",
        "blind":False,"learner_training_actions":0,
        "shared_bank_is_costed_upfront_even_if_unused":True,
        "repeated_TEST_indices_across_checkpoints":True,
        "test_tasks_per_seed_checkpoint":TEST_N,
        "cost_weights":{"harmful_test_or_actor_action":COST_DAMAGE,
                        "failed_by_abstention":COST_ABSTAIN,
                        "new_actor_action":COST_EXTRA_ACTION},
        "rows":[],
    }
    for seed in cohort:
        base=[]
        base_actor_cost={}
        bank_actor_cost={}
        stages={}
        for stage,law,begin,count in STAGES:
            observed,source_cost=training(seed,law,begin,count)
            base_actor_cost[stage]=source_cost
            if stage=="source":
                base.extend(observed)
                continue
            # Pay ONCE per seed/stage for a fixed shared independent log.
            bank_start=600000+STAGE_NUM[stage]*10000
            bank,paid=training(seed,law,bank_start,MAX_WITNESS)
            bank_actor_cost[stage]=paid
            phase={}
            for ordinal,k in enumerate(CHECKPOINTS[stage]):
                history=base+observed[:k]
                models=baseline_models(history)
                selective=models["validated_abstain"]
                models["no_extra_evidence"]=selective
                models["fresh_witness"]=fresh_witness(history)
                models["shared_bank"]=fresh_witness(history)
                before_fresh=models["fresh_witness"].selection()[0]["meets_adequacy_gate"]
                before_bank=models["shared_bank"].selection()[0]["meets_adequacy_gate"]
                fresh=collect_on_demand(seed,stage,law,ordinal,models["fresh_witness"])
                shared=feed_bank(models["shared_bank"],bank)
                snapshots={name:model.record() for name,model in models.items()
                           if hasattr(model,"record")}
                scores={
                    name:summarize([
                        evaluate(seed,law,TEST_START[stage]+i,name,models)
                        for i in range(TEST_N)])
                    for name in METHODS}
                if any(models[name].record()!=prior
                       for name,prior in snapshots.items()):
                    raise AssertionError("TEST contaminated public evidence")
                phase[str(k)]={
                    "original_stage_feedback":k,
                    "adequate_before_fresh":before_fresh,
                    "adequate_before_shared":before_bank,
                    "fresh":fresh,
                    "shared":shared,
                    "fresh_actor_cost":fresh["external_actor_cost"],
                    "bank_cost_accounted_once_at_stage_entry":True,
                    "policy_record_sha256":{
                        name:models[name].record()["sha256"] for name in
                        ("no_extra_evidence","fresh_witness","shared_bank")},
                    "scores":scores,
                }
            stages[stage]=phase
            base.extend(observed)
        report["rows"].append({
            "seed":seed,"base_actor_cost":base_actor_cost,
            "bank_actor_cost":bank_actor_cost,"stages":stages,
            "base_training_event_count":len(base),
        })
    report["study_costs"]=study_costs(report["rows"])
    report["base_actor_harm"]=sum(
        stage_cost["harmful"] for row in report["rows"]
        for stage_cost in row["base_actor_cost"].values()
    )
    report["base_actor_actions"]=sum(
        stage_cost["observations"] for row in report["rows"]
        for stage_cost in row["base_actor_cost"].values()
    )
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    arg=p.parse_args()
    cohort=DEV if arg.cohort=="development" else ADDITIONAL
    print(json.dumps(measure(cohort),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
