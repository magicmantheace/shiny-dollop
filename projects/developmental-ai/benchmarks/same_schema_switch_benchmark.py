"""Frozen A -> reversed B -> original A with identical public feature names.

No oracle physics, phase names, stage labels, trusted change points or
episode IDs are shown to any learned policy. Physics is selected ONLY by
the generator and benchmark scoring. External random actor takes one
training action per independent disposable episode; source harm is counted.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.same_schema_switch_memory import SameSchemaSwitchMemory
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory
from developmental_ai.gated_relation_memory import GatedRelationMemory
from developmental_ai.observable_affordances import digest
from benchmarks.relation_transfer_benchmark import (
    RelationWorld, effect_for, observed, relation_model,
    summarize, TEST_N as ORIGINAL_TEST_N
)
from benchmarks.variable_affordance_benchmark import public_outcome

SCHEMA="developmental-ai.same-schema-switch-evaluation/v1"
DEV=(172003,172021,172039)
ADDITIONAL=(173001,173017,173041)
STAGES=(("A","original",1000,240),
        ("B","reversed",2000,64),
        ("return_A","original",3000,48))
CHECKPOINTS={"B":(0,4,8,12,16,24,48,64),
             "return_A":(0,4,8,12,16,24,48)}
TEST_START={"B":60000,"return_A":70000}
TEST_N=30
METHODS=("adaptive_same_schema","frozen_A","cumulative_range",
         "recent_8_range","recent_32_range","untrained_random",
         "always_abstain","privileged_oracle","old_feature_signature_gate")


class SameSchemaWorld(RelationWorld):
    """Same frame schema and action descriptors; reversed hidden effect only."""

    def __init__(self,seed,split,index,physics):
        if physics not in ("original","reversed"):
            raise ValueError("unrecognized hidden physics")
        super().__init__(seed,split,index,"basin")
        self._physics=physics

    def _effect(self,features):
        original=effect_for(self.seed,"basin",features)
        if self._physics=="reversed":
            return {"progress":"damage","damage":"progress",
                    "neutral":"neutral"}[original]
        return original

    def step(self,action,tick):
        if (self.done or type(tick) is not int or tick!=self.tick
                or type(action) is not str or action not in self._actions
                or action in self._used):
            raise ValueError("invalid or stale simulated intervention")
        category=self._effect(self._actions[action])
        self.tick+=1
        self.progress+=int(category=="progress")
        self.damage+=int(category=="damage")
        self._used.add(action)
        self.done=(self.progress>=self.goal or self.damage>0
                   or self.tick>=self.budget
                   or len(self._used)==len(self._actions))
        return self.frame()


def actor_event(seed,physics,index):
    world=SameSchemaWorld(seed,"train",index,physics)
    frame=world.frame()
    rng=random.Random(int(digest(["same-schema-external-actor",world.episode])[:16],16))
    picked=rng.choice(frame["actions"])["id"]
    after=world.step(picked,frame["tick"])
    return public_outcome(frame,picked,after)


def training(seed,physics,start,n):
    return [actor_event(seed,physics,start+i) for i in range(n)]


def build_models(events):
    adaptive=SameSchemaSwitchMemory()
    gate=GatedRelationMemory()
    for row in events:
        adaptive.observe(row)
        gate.observe(row)
    return {
        "adaptive_same_schema":adaptive,
        "frozen_A":relation_model(events[:192]),
        "cumulative_range":relation_model(events),
        "recent_8_range":relation_model(events[-8:]),
        "recent_32_range":relation_model(events[-32:]),
        "old_feature_signature_gate":gate,
    }


def eval_episode(seed,physics,index,method,models):
    if method not in METHODS:
        raise ValueError("not precommitted evaluation policy")
    world=SameSchemaWorld(seed,"test",index,physics)
    rng=random.Random(int(digest(["same-schema-random-test",world.episode])[:16],16))
    hurt=0
    abstain=0
    for _ in range(world.budget):
        before=world.frame()
        if before["done"]:
            break
        if method in models:
            picked=models[method].choose(before)
        elif method=="always_abstain":
            picked=None
        elif method=="untrained_random":
            picked=rng.choice(before["actions"])["id"]
        else:
            # Privileged TEST-only oracle, not exposed to learned candidate.
            picked=next((a["id"] for a in before["actions"]
                         if world._effect(a["features"])=="progress"),None)
        if picked is None:
            abstain=1
            break
        after=world.step(picked,before["tick"])
        hurt+=int(public_outcome(before,picked,after)["damage"])
    return {"success":int(world.success()),
            "harmful_actions":hurt,"abstained":abstain,"attempts":world.tick}


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("not a precommitted seed cohort")
    result={"schema":SCHEMA,
            "protocol":"benchmarks/same_schema_switch_protocol.json",
            "blind":False,"learner_training_actions":0,
            "heldout_repeated_indices_per_checkpoint":True,
            "test_episodes_per_seed_checkpoint":TEST_N,
            "rows":[]}
    for seed in seeds:
        events=[]
        source_cost={}
        evaluations={}
        for stage,physics,start,n in STAGES:
            newly=training(seed,physics,start,n)
            source_cost[stage]={
                "observations":n,
                "harmful":sum(int(e["damage"]) for e in newly),
                "productive":sum(int(e["progress"]) for e in newly),
                "neutral":sum(int(not e["progress"] and not e["damage"]) for e in newly)}
            if stage=="A":
                events.extend(newly)
                continue
            checkpoints={}
            for checkpoint in CHECKPOINTS[stage]:
                history=events+newly[:checkpoint]
                models=build_models(history)
                saved={name:model.record() for name,model in models.items()}
                models["adaptive_same_schema"]=SameSchemaSwitchMemory.restore(
                    saved["adaptive_same_schema"])
                choice,_=models["adaptive_same_schema"].selection()
                scores={method:summarize([
                    eval_episode(seed,physics,TEST_START[stage]+i,method,models)
                    for i in range(TEST_N)])
                    for method in METHODS}
                if any(models[name].record()!=record for name,record in saved.items()):
                    raise AssertionError("heldout test contaminated training event memory")
                checkpoints[str(checkpoint)]={
                    "events_since_switch":checkpoint,
                    "total_training_events":len(history),
                    "selected_model":choice,
                    "checkpoint_sha256":saved["adaptive_same_schema"]["sha256"],
                    "test":scores}
            evaluations[stage]=checkpoints
            events.extend(newly)
        result["rows"].append({"seed":seed,"actor_by_stage":source_cost,
                               "evaluations":evaluations,
                               "final_event_count":len(events)})
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    a=p.parse_args()
    print(json.dumps(measure(DEV if a.cohort=="development" else ADDITIONAL),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
