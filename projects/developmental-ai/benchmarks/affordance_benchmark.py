"""Controlled stable-descriptor memory vs original anonymous-action policies.

Training is ONLY on cargo 0..79. Every learner sees 80 independent
unfiltered novel-first experiences and public outcomes; evaluation is frozen.
Harm labels and hidden action meanings are used for SCORING/ORACLES ONLY.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.opaque_causal import BUDGET
from developmental_ai.affordance_memory import (
    DescribedWorld, FilteredNovel, RiskMemory, signature, token
)
from developmental_ai.outcome_skills import canonical

SCHEMA="developmental-ai.affordance-benchmark/v1"
DEVELOPMENT=(31013,31019,31033)
RESERVED=(43013,43019,43033)
TRAIN_EPISODES=80
TEST_EPISODES=60
TEST_START=8200
FAMILIES=("cargo","relay")
POLICIES=("learned","novel","cyclic","random","descriptor_shuffled",
          "risk_oracle","full_oracle")


class FixedRisks(RiskMemory):
    """BENCHMARK ONLY: privileged stable signature of simulator 'spoil'."""
    def __init__(self, code):
        super().__init__()
        self.code=code

    def avoid(self):
        return {self.code}


def run(seed, split, index, family, policy, memory=None, *, collect=False):
    if policy not in POLICIES:
        raise ValueError("unsupported risk evaluation policy")
    shuffled=(policy=="descriptor_shuffled")
    world=DescribedWorld(seed,split,index,family,remap=shuffled)
    if policy in ("learned","descriptor_shuffled"):
        if not isinstance(memory,RiskMemory) or not memory.events:
            raise ValueError("risk transfer requires nonempty learned history")
        controller=FilteredNovel(memory)
    elif policy=="novel":
        controller=FilteredNovel()
    elif policy=="risk_oracle":
        # A deliberately unequal privileged reference. Relay has no hazard.
        privileged=FixedRisks(token(signature(seed,family,"spoil"))) if family=="cargo" else None
        controller=FilteredNovel(privileged)
    else:
        controller=None
    rng=random.Random(int(world.base.episode[:16],16)^0x5b331)
    sequence=(
        ("extract","charge","refine","fuel","load","ship")
        if family=="cargo" else
        ("power","switch","combine","gate","endpoint")
    )
    steps=[]
    attempts=0
    failed=0
    spoil=0
    negative=0
    for _ in range(BUDGET):
        before=world.frame()
        base=before["base"]
        if base["done"]:
            break
        if controller is not None:
            action=controller.choose(before)
        elif policy=="cyclic":
            action=base["actions"][base["tick"]%len(base["actions"])]
        elif policy=="random":
            action=rng.choice(base["actions"])
        else:
            action=world.base._ids[sequence[base["tick"]]] if base["tick"]<len(sequence) else None
        if action is None:
            break
        hidden=world.base._lookup[action]  # SCORING ONLY, never passed to policy
        response=world.step(action,base["tick"])
        after=response["frame"]
        if controller is not None:
            event=controller.feedback(before,action,response["accepted"],after)
        else:
            # Public observation evidence is still recorded for all controls.
            from developmental_ai.affordance_memory import record_step
            event=record_step(before,action,response["accepted"],after)
        steps.append(event)
        attempts+=1
        failed+=int(not response["accepted"])
        spoil+=int(hidden=="spoil" and response["accepted"])
        negative+=int(event["decreases"]>0)
    success=world.public_success()
    result={"success":int(success),"attempts":attempts,"blocked":failed,
            "spoilage":spoil,"negative_steps":negative,
            "stalled":int(not world.base.done)}
    if collect:
        return result,steps
    return result


def learn(seed):
    memory=RiskMemory()
    rows=[]
    for i in range(TRAIN_EPISODES):
        stats,steps=run(seed,"train",i,"cargo","novel",collect=True)
        memory.add(i,steps,bool(stats["success"]))
        rows.append(stats)
    recovered=RiskMemory.restore(memory.record())
    if memory.record()!=recovered.record():
        raise AssertionError("train-history replay mismatch")
    return recovered, rows


def summarize(rows):
    if not rows:
        raise ValueError("empty result group")
    return {"successes":sum(x["success"] for x in rows),
            "episodes":len(rows),
            "mean_attempts":round(sum(x["attempts"] for x in rows)/len(rows),3),
            "mean_blocked":round(sum(x["blocked"] for x in rows)/len(rows),3),
            "spoilage":sum(x["spoilage"] for x in rows),
            "negative_steps":sum(x["negative_steps"] for x in rows),
            "stalled":sum(x["stalled"] for x in rows)}


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,RESERVED):
        raise ValueError("cannot silently change frozen seed cohort")
    result={"schema":SCHEMA,"blind":False,
            "stable_numeric_identity_engineered":True,
            "train_family":"cargo","train_episodes":TRAIN_EPISODES,
            "train_indices":[0,TRAIN_EPISODES-1],
            "test_indices":[TEST_START,TEST_START+TEST_EPISODES-1],
            "test_families":list(FAMILIES),"rows":[]}
    for seed in seeds:
        memory,training=learn(seed)
        frozen=memory.record()
        scores={}
        for family in FAMILIES:
            scores[family]={}
            for policy in POLICIES:
                samples=[run(seed,"test",TEST_START+i,family,policy,memory)
                         for i in range(TEST_EPISODES)]
                scores[family][policy]=summarize(samples)
        if memory.record()!=frozen:
            raise AssertionError("test updated training memory")
        risky=sorted(memory.avoid())
        result["rows"].append({
            "seed":seed,"training":summarize(training),
            "learned_risk_tokens":risky,
            "num_learned_risks":len(risky),
            "memory_sha256":frozen["sha256"],"scores":scores})
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","reserved"),default="development")
    a=p.parse_args()
    print(json.dumps(measure(DEVELOPMENT if a.cohort=="development" else RESERVED),
                     sort_keys=True,indent=2))


if __name__=="__main__":
    main()
