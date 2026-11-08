"""Passive-outcome learning from a separate public-only simulator actor.

The learner NEVER chooses its data-collection interventions; the
independent random / old-policy actor does. Actor-caused harm is NOT
zero and must be reported. The hand-authored third rule remains a
within-simulator study, not general causal understanding.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.novel_feature_world import NovelFeatureWorld
from developmental_ai.observable_affordances import outcome, digest
from developmental_ai.passive_outcome_learning import PassiveOutcomeArchive
from benchmarks.observable_affordance_benchmark import fit,summary
from benchmarks.observable_reversal_calibration_benchmark import fit_reversed

SCHEMA="developmental-ai.passive-third-rule-benchmark/v1"
DEV=(95003,95021,95039)
RESERVED=(96001,96017,96041)
METHODS=("guarded_random240","raw_random240","guarded_random24",
         "guarded_oldpolicy240","old_normal_model","old_reversed_model",
         "always_abstain","privileged_oracle")
RANDOM_START=3000
BIASED_START=3300
OBSERVATIONS=240
SMALL=24
TEST_START=23000
TEST_N=60


def collect(seed,start,episodes,actor,old_model=None):
    if actor not in ("random","old_normal") or type(episodes) is not int or not 1<=episodes<=OBSERVATIONS:
        raise ValueError("invalid passive actor settings")
    if actor=="old_normal" and old_model is None:
        raise ValueError("old actor needs its earlier source policy")
    archive=PassiveOutcomeArchive()
    for index in range(start,start+episodes):
        sim=NovelFeatureWorld(seed,"train",index,"third_rule")
        before=sim.frame()
        if actor=="random":
            rng=random.Random(int(digest(["independent-public-actor",
                                          before["episode"]])[:16],16))
            action=rng.choice(before["actions"])["id"]
        else:
            action=old_model.choose(before)
        # Only the separate simulator harness actually acts.
        after=sim.step(action,before["tick"])
        archive.observe(before,action,after)
    copy=PassiveOutcomeArchive.restore(archive.record())
    if copy.record()!=archive.record():
        raise AssertionError("independent observations failed replay")
    return copy


def episode(seed,index,method,archives,source,reversed_model):
    if method not in METHODS:
        raise ValueError("invalid previously frozen passive policy")
    world=NovelFeatureWorld(seed,"test",index,"third_rule")
    observers={"guarded_random240":archives["random240"],
               "raw_random240":archives["random240"],
               "guarded_random24":archives["random24"],
               "guarded_oldpolicy240":archives["oldpolicy240"]}
    passive=observers.get(method)
    memory=(passive.memory() if passive is not None and method=="raw_random240"
            else source if method=="old_normal_model"
            else reversed_model if method=="old_reversed_model" else None)
    harmful=0
    abstained=False
    for _ in range(world.frame()["budget"]):
        frame=world.frame()
        if frame["done"]:
            break
        if passive is not None and method!="raw_random240":
            action=passive.guarded_choose(frame)
        elif method=="always_abstain":
            action=None
        elif method=="privileged_oracle":
            # Only benchmark oracle can inspect private true simulator effects.
            good=[r["id"] for r in frame["actions"]
                  if world._effect(r["id"])=="progress"]
            action=good[0] if good else None
        else:
            action=memory.choose(frame)
        if action is None:
            abstained=True
            break
        after=world.step(action,frame["tick"])
        public=outcome(frame,action,after)
        harmful+=int(public["damage"])
    return {"success":int(world.success()),
            "hurt":harmful,"stalled":int(not world.success()),
            "attempts":world.tick,"abstained":int(abstained)}


def score(rows):
    return {**summary(rows),"abstained":sum(r["abstained"] for r in rows)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("cannot change precommitted passive seed cohorts")
    out={"schema":SCHEMA,"blind":False,
         "independent_actor_public_only":True,
         "learner_generated_training_actions":0,
         "train_random":[RANDOM_START,RANDOM_START+OBSERVATIONS-1],
         "train_old_policy":[BIASED_START,BIASED_START+OBSERVATIONS-1],
         "held_out_test":[TEST_START,TEST_START+TEST_N-1],
         "rows":[]}
    for seed in seeds:
        old,_=fit(seed)
        reversed_model,_=fit_reversed(seed)
        source_snapshot=old.record()
        reverse_snapshot=reversed_model.record()
        random240=collect(seed,RANDOM_START,OBSERVATIONS,"random")
        oldpolicy240=collect(seed,BIASED_START,OBSERVATIONS,"old_normal",old)
        random24=PassiveOutcomeArchive()
        for row in random240.events[:SMALL]:
            random24.observe(row["before"],row["action"],row["after"])
        archives={"random240":random240,"random24":random24,
                  "oldpolicy240":oldpolicy240}
        snapshots={name:archive.record() for name,archive in archives.items()}
        scores={}
        for method in METHODS:
            rows=[episode(seed,TEST_START+i,method,archives,old,reversed_model)
                  for i in range(TEST_N)]
            scores[method]=score(rows)
        if (old.record()!=source_snapshot or reversed_model.record()!=reverse_snapshot
            or any(archive.record()!=snapshots[name]
                   for name,archive in archives.items())):
            raise AssertionError("held-out test mutated training/observer evidence")
        out["rows"].append({"seed":seed,"scores":scores,
            "actor_evidence":{name:archive.stats() for name,archive in archives.items()},
            "observer_digests":{name:archive.record()["sha256"] for name,archive in archives.items()},
            "source_sha256":source_snapshot["sha256"],
            "reversed_sha256":reverse_snapshot["sha256"]})
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","reserved"),default="development")
    args=p.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
