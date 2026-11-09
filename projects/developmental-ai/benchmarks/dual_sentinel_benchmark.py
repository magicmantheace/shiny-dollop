"""Two-risk-sentinel known-context audit versus full unseen-C baselines.

The previous C audit results remain frozen. This new policy explicitly
abstains on unmatched observations; score abstention as NO task completion.
All worlds are synthetic, all six seeds were already inspected.
"""
from __future__ import annotations

import argparse
import json
from developmental_ai.contextual_affordance import CUES, ContextMemory
from developmental_ai.dual_sentinel import DualSentinel, sentinel_design
from developmental_ai.unseen_regime import UnseenDescriptorCargo
from benchmarks.contextual_affordance_benchmark import DEVELOPMENT, RESERVED, fit
from benchmarks.unseen_regime_benchmark import (
    START, EPISODES, VARIANTS, METHODS as PRIOR_METHODS,
    run as old_run, summarise as old_summarise
)

SCHEMA = "developmental-ai.dual-sentinel-evaluation/v1"
METHODS = ("sentinel",) + PRIOR_METHODS


def sentinel_episode(seed, index, variant, memories):
    world = UnseenDescriptorCargo(seed,"test",index,variant)
    policy = DualSentinel(memories)
    blocked = spoiled = 0
    for _ in range(18):
        before = world.frame()
        if before["base"]["done"]:
            break
        action = policy.choose(before)
        if action is None:
            break
        # PRIVATE label used for benchmark metrics, never policy inference.
        hidden_name = world.world.world.base._lookup[action]
        outcome = world.execute(action,before["base"]["tick"])
        policy.feedback(before,action,outcome["accepted"],outcome["public"])
        blocked += int(not outcome["accepted"])
        spoiled += int(hidden_name == "spoil" and outcome["accepted"])
    if policy.events:
        saved = policy.record()
        recovered = DualSentinel.restore(memories,saved)
        if recovered.record() != saved:
            raise AssertionError("sentinel exact-replay failed")
        if not world.world.world.base.done:
            if recovered.choose(world.frame()) != policy.choose(world.frame()):
                raise AssertionError("checkpoint restart changed decision")
    return {"success":int(world.success()), "spoilage":spoiled,
            "attempts":world.world.world.base.tick, "blocked":blocked,
            "stalled":int(not world.world.world.base.done),
            "probe":int(len(policy.events)>0),
            "unknown":int(policy.unknown),
            "known_match":int(policy.selected is not None)}


def report_rows(rows):
    return {**old_summarise(rows),
            "unknown":sum(row["unknown"] for row in rows),
            "known_match":sum(row["known_match"] for row in rows)}


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,RESERVED):
        raise ValueError("frozen inspected cohorts only")
    output={"schema":SCHEMA,"blind":False,
            "simulator_provided_action_identity":True,
            "untrained_C":True, "task_success_required":True,
            "test_indices":[START,START+EPISODES-1],"rows":[]}
    for seed in seeds:
        a,_=fit(seed,"A")
        b,_=fit(seed,"B")
        histories=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        saved=histories.record()
        design=sentinel_design(histories)
        outcomes={}
        for variant in VARIANTS:
            outcomes[variant]={}
            for policy in METHODS:
                samples=( [sentinel_episode(seed,START+i,variant,histories)
                            for i in range(EPISODES)]
                         if policy=="sentinel" else
                         [old_run(seed,"test",START+i,variant,policy,histories)
                          for i in range(EPISODES)] )
                outcomes[variant][policy]=(report_rows(samples) if policy=="sentinel"
                                           else old_summarise(samples))
        if histories.record()!=saved:
            raise AssertionError("read-only sentinel audit mutated learning")
        output["rows"].append({"seed":seed,"design":design,
                               "sha256":saved["sha256"],"scores":outcomes})
    return output


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","inspected-additional"),
                   default="development")
    args=p.parse_args()
    print(json.dumps(measure(DEVELOPMENT if args.cohort=="development" else RESERVED),
                     sort_keys=True,indent=2))


if __name__=="__main__":
    main()
