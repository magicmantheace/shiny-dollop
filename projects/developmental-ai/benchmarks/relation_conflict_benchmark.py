"""Frozen independent-seed conflict gate experiment (no actions on TRAIN).

New seeds and TEST indices, same deliberately engineered relation worlds.
Sources are never deleted. Four recent target events are held out from
target candidate fit before predictive model-selection. All comparisons
see exact matched public training events and disjoint TEST indices.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.gated_relation_memory import GatedRelationMemory
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory
from developmental_ai.observable_affordances import VariableOutcomeMemory
from benchmarks.relation_transfer_benchmark import (
    FAMILIES,TARGETS,INDEX,SOURCE_N,TARGET_N,TEST_N,RelationWorld,
    actor_event,observed,relation_model,raw_model,play,summarize
)

SCHEMA="developmental-ai.relation-conflict-benchmark/v1"
DEV=(162003,162021,162039)
ADDITIONAL=(163001,163017,163041)
CHECKPOINTS=(0,4,8,16,24,64)
TEST_START=55000
METHODS=("gated_relation","source_frozen_range","target_only_range",
         "raw_schema_memory","untrained_random","always_abstain",
         "privileged_oracle")


def trained(rows):
    result=GatedRelationMemory()
    for row in rows:
        result.observe(row)
    return result


def evaluate(seed,family,index,method,policies):
    if method not in METHODS:
        raise ValueError("not a precommitted gate comparison")
    actual="transfer_range" if method=="gated_relation" else method
    models={"transfer_range":policies["gated_relation"]} if method=="gated_relation" else policies
    return play(seed,family,index,actual,models)


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("cohort not precommitted")
    report={"schema":SCHEMA,"protocol":"benchmarks/relation_conflict_protocol.json",
            "blind":False,"learner_training_actions":0,
            "test_episodes_per_family_checkpoint_seed":TEST_N,"rows":[]}
    for seed in seeds:
        source=observed(seed,"basin",SOURCE_N)
        source_model=relation_model(source)
        target_evidence={f:observed(seed,f,TARGET_N) for f in TARGETS}
        training_cost={
            name:{"observations":len(rows),
                  "harmful":sum(int(r["damage"]) for r in rows),
                  "productive":sum(int(r["progress"]) for r in rows),
                  "neutral":sum(int(not r["progress"] and not r["damage"]) for r in rows)}
            for name,rows in (("basin",source),*target_evidence.items())}
        comparisons={}
        for target in TARGETS:
            checkpoints={}
            signature=target_evidence[target][0]["features"]
            source_signature=source[0]["features"]
            for n in CHECKPOINTS:
                events=source+target_evidence[target][:n]
                gate=GatedRelationMemory.restore(trained(events).record())
                frozen=RelationOutcomeMemory.restore(source_model.record())
                target_only=relation_model(target_evidence[target][:n])
                raw=raw_model(events)
                policies={"gated_relation":gate,"source_frozen_range":frozen,
                          "target_only_range":target_only,"raw_schema_memory":raw}
                snapshots={name:(m.record() if m.events else None)
                           for name,m in policies.items()}
                scores={
                    family:{
                        method:summarize([
                            evaluate(seed,family,TEST_START+i,method,policies)
                            for i in range(TEST_N)])
                        for method in METHODS}
                    for family in ("basin",target)}
                if any((m.record() if m.events else None)!=snapshots[name]
                       for name,m in policies.items()):
                    raise AssertionError("held-out outcome used to train")
                checkpoints[str(n)]={
                    "observed_target_events":n,"trained_total_events":len(events),
                    "source_revisit_gate":gate.selection(source_signature)[0],
                    "target_gate":gate.selection(signature)[0],
                    "checkpoint_sha256":snapshots["gated_relation"]["sha256"],
                    "scores":scores}
            comparisons[target]=checkpoints
        report["rows"].append({"seed":seed,"training_actor_costs":training_cost,
                               "comparisons":comparisons})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    args=p.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="development" else ADDITIONAL),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
