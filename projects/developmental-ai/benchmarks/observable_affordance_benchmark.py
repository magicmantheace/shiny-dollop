"""Frozen source->target feature transfer and reversed-physics negative control.

All actions are new each episode. Public feature measurements are engineered;
the learned policy never sees simulator domain or true action consequences.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.observable_affordances import (
    ObservableWorld, NumericOutcomeMemory, outcome
)

SCHEMA = "developmental-ai.observable-affordance-benchmark/v1"
DEV = (71001,71013,71031)
RESERVED = (81001,81013,81031)
TRAIN_EPISODES = 80
TEST_EPISODES = 60
TEST_START = 12000
DOMAINS = ("collect", "route", "route-reversed")
POLICIES = ("numeric_knn", "novel", "random", "feature_shuffle", "oracle")


def play(seed,split,index,domain,policy,memory=None,*,collect=False):
    if policy not in POLICIES or domain not in DOMAINS:
        raise ValueError("invalid numeric affordance benchmark request")
    if policy in ("numeric_knn","feature_shuffle") and (
        not isinstance(memory, NumericOutcomeMemory) or not memory.examples):
        raise ValueError("trained public memory required")
    world=ObservableWorld(seed,split,index,domain)
    rng=random.Random(int(world.episode[16:32],16)^0x831a)
    trace=[]
    hurt=0
    for _ in range(world.budget):
        before=world.frame()
        if before["done"]:break
        actions=before["actions"]
        if policy=="oracle":
            # BENCHMARK REFERENCE ONLY: simulator's private rule exposed here.
            good=[]
            for row in actions:
                x,y=row["features"]
                if domain=="route-reversed":x,y=y,x
                if y>=x+2:good.append(row["id"])
            selected=good[0] if good else None
        elif policy=="random":selected=rng.choice(actions)["id"]
        elif policy=="novel":selected=actions[0]["id"]
        elif policy=="feature_shuffle":
            # Negative control: same action IDs, mismatched public physical
            # measurements. The action/effect world is NEVER changed.
            altered={**before,"actions":[
                {"id":row["id"],"features":list(actions[(k+3)%len(actions)]["features"])}
                for k,row in enumerate(actions)]}
            selected=memory.choose(altered)
        else:selected=memory.choose(before)
        if selected is None:break
        after=world.step(selected,before["tick"])
        event=outcome(before,selected,after)
        trace.append(event)
        hurt+=int(event["damage"])
    score={"success":int(world.success()),"hurt":hurt,
           "stalled":int(not world.success()),"attempts":world.tick}
    return (score,trace) if collect else score


def fit(seed):
    memory=NumericOutcomeMemory()
    training=[]
    for i in range(TRAIN_EPISODES):
        stats,events=play(seed,"train",i,"collect","random",collect=True)
        for event in events:memory.add(event)
        training.append(stats)
    if NumericOutcomeMemory.restore(memory.record()).record()!=memory.record():
        raise AssertionError("public training replay changed evidence")
    return memory, summary(training)


def summary(rows):
    return {"successes":sum(x["success"] for x in rows),
            "episodes":len(rows),"hurt":sum(x["hurt"] for x in rows),
            "stalled":sum(x["stalled"] for x in rows),
            "mean_attempts":round(sum(x["attempts"] for x in rows)/len(rows),3)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("frozen cohorts must not change")
    out={"schema":SCHEMA,"blind":False,"engineered_public_features":True,
         "hidden_name_identifiers_in_features":False,
         "train_source": [0,TRAIN_EPISODES-1],
         "target_training_episodes":0,"test_indices":[TEST_START,TEST_START+TEST_EPISODES-1],"rows":[]}
    for seed in seeds:
        memory,train_stats=fit(seed)
        before=memory.record()
        evals={}
        for domain in DOMAINS:
            evals[domain]={}
            for policy in POLICIES:
                results=[play(seed,"test",TEST_START+i,domain,policy,memory)
                         for i in range(TEST_EPISODES)]
                evals[domain][policy]=summary(results)
        if memory.record()!=before:
            raise AssertionError("evaluation mutated frozen public model")
        out["rows"].append({"seed":seed,"source_training":train_stats,
                            "observed_samples":len(memory.examples),
                            "memory_sha256":before["sha256"],"scores":evals})
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","reserved"),default="development")
    args=parser.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="development" else RESERVED),indent=2,sort_keys=True))


if __name__=="__main__":main()
