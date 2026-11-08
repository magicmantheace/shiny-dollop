"""Precommitted faster reversal response, A->B->A with same public schema.

The simulator and independently seeded training actor are reused unchanged.
No phase indicator, hidden band, simulator label or privileged world objects
are passed to any policy. TEST episodes never enter model fitting.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.same_schema_switch_memory import SameSchemaSwitchMemory
from developmental_ai.observable_affordances import digest
from benchmarks.same_schema_switch_benchmark import (
    SameSchemaWorld, training, STAGES, eval_episode as previous_episode
)
from benchmarks.relation_transfer_benchmark import relation_model, summarize

SCHEMA="developmental-ai.fast-shock-benchmark/v1"
DEV=(182003,182021,182039)
ADDITIONAL=(183001,183017,183041)
TEST_N=30
TEST_START={"B":80000,"return_A":90000}
CHECKPOINTS={"B":(0,2,4,6,8,12,16,24,32,48,64),
             "return_A":(0,2,4,6,8,12,16,24,48)}
METHODS=("fast_shock","legacy_disjoint_12plus4","recent8","recent32",
         "frozen_A","cumulative_range","untrained_random",
         "always_abstain","privileged_oracle")


def _trained(rows,cls):
    model=cls()
    for row in rows:
        model.observe(row)
    return cls.restore(model.record())


def models(history):
    return {
        "fast_shock":_trained(history,FastShockMemory),
        "legacy_disjoint_12plus4":_trained(history,SameSchemaSwitchMemory),
        "recent8":relation_model(history[-8:]),
        "recent32":relation_model(history[-32:]),
        "frozen_A":relation_model(history[:192]),
        "cumulative_range":relation_model(history),
    }


def eval_trial(seed,physics,index,method,available):
    if method not in METHODS:
        raise ValueError("not a precommitted method")
    # The historical runner includes audited, identical action/world semantics.
    # The method adapters are explicit: no method sees scoring truth.
    mapping={
        "fast_shock":"adaptive_same_schema",
        "legacy_disjoint_12plus4":"adaptive_same_schema",
        "recent8":"recent_8_range",
        "recent32":"recent_32_range",
        "frozen_A":"frozen_A",
        "cumulative_range":"cumulative_range",
        "untrained_random":"untrained_random",
        "always_abstain":"always_abstain",
        "privileged_oracle":"privileged_oracle"}
    mapped=mapping[method]
    return previous_episode(seed,physics,index,mapped,
                {mapped:available[method]} if method in available else {})


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("seeds differ from frozen fast shock protocol")
    result={
        "schema":SCHEMA,
        "protocol":"benchmarks/fast_shock_protocol.json",
        "blind":False,
        "learner_training_actions":0,
        "scoring_episodes_per_seed_stage_checkpoint":TEST_N,
        "heldout_indices_reused_across_checkpoints":True,
        "rows":[],
    }
    for seed in seeds:
        archive=[]
        actor_cost={}
        scored={}
        for stage,physics,start,n in STAGES:
            batch=training(seed,physics,start,n)
            actor_cost[stage]={
                "observations":len(batch),
                "harmful":sum(int(e["damage"]) for e in batch),
                "productive":sum(int(e["progress"]) for e in batch),
                "neutral":sum(int(not e["progress"] and not e["damage"]) for e in batch)}
            if stage=="A":
                archive.extend(batch)
                continue
            stages={}
            for checkpoint in CHECKPOINTS[stage]:
                history=archive+batch[:checkpoint]
                learners=models(history)
                snapshots={name:learner.record() for name,learner in learners.items()}
                selection=learners["fast_shock"].selection()[0]
                old_selection=learners["legacy_disjoint_12plus4"].selection()[0]
                policy_scores={
                    method:summarize([
                        eval_trial(seed,physics,TEST_START[stage]+i,
                                   method,learners)
                        for i in range(TEST_N)])
                    for method in METHODS}
                if any(learner.record()!=snapshots[name]
                       for name,learner in learners.items()):
                    raise AssertionError("read-only TEST scoring updated training events")
                stages[str(checkpoint)]={
                    "new_observations":checkpoint,
                    "total_events":len(history),
                    "fast_selection":selection,
                    "legacy_selection":old_selection,
                    "fast_checkpoint_sha256":snapshots["fast_shock"]["sha256"],
                    "scores":policy_scores}
            scored[stage]=stages
            archive.extend(batch)
        result["rows"].append({"seed":seed,
                               "training_actor":actor_cost,
                               "stages":scored,
                               "total_observations":len(archive)})
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    a=p.parse_args()
    cohort=DEV if a.cohort=="development" else ADDITIONAL
    print(json.dumps(measure(cohort),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
