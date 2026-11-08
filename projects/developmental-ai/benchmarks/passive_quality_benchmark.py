"""Experiment: feature coverage, policy selection bias and internally
consistent forged public transitions under the *same* third-rule
simulator as the preceding passive-outcome experiment.

An independent external actor (benchmark harness) generates all
observations; no learner probes for training. Actor and test harm
are counted separately. SHA-256 integrity cannot verify truthfulness.
"""
from __future__ import annotations

import argparse
import copy
import json

from developmental_ai.novel_feature_world import NovelFeatureWorld
from developmental_ai.passive_outcome_learning import PassiveOutcomeArchive
from developmental_ai.passive_quality import PassiveEvidenceQuality
from developmental_ai.observable_affordances import outcome
from benchmarks.observable_affordance_benchmark import fit
from benchmarks.passive_outcome_benchmark import collect,episode as old_episode,score as old_score

SCHEMA="developmental-ai.passive-quality-benchmark/v1"
DEV=(97001,97019,97037)
RESERVED=(98003,98017,98041)
RANDOM_START=4000
BIASED_START=4300
REFERENCE_START=4600
RECORDS=240
MENU_EPISODES=60
TEST_START=24000
TEST_N=60
MAX_FORGED=60
METHODS=("raw_random240","coverage_gated_random240",
         "raw_biased240","coverage_gated_biased240",
         "raw_forged240","coverage_gated_forged240",
         "always_abstain","privileged_oracle")


def fabricate_public_damage_as_progress(original, maximum=MAX_FORGED):
    """Benchmark-only dishonest actor supplies counterfeit sensor evidence.

    It changes *public* after sensor readings and normal termination into
    a coherent productive first action. This does not modify the true
    underlying simulated actor consequences; record those separately.
    """
    if (not isinstance(original,PassiveOutcomeArchive)
        or type(maximum) is not int or not 0<=maximum<=MAX_FORGED):
        raise ValueError("invalid forgery specification")
    forged=PassiveOutcomeArchive()
    changed=0
    for row in original.events:
        before=copy.deepcopy(row["before"])
        after=copy.deepcopy(row["after"])
        if row["outcome"]["damage"] and changed<maximum:
            changed+=1
            after["sensors"]=[1,0]
            after["done"]=False
            after["actions"]=[copy.deepcopy(a) for a in before["actions"]
                              if a["id"]!=row["action"]]
        forged.observe(before,row["action"],after)
    return forged,changed


def public_opportunities(seed):
    # There is no action step, no hidden effect and no test features.
    return [NovelFeatureWorld(seed,"train",REFERENCE_START+i,"third_rule").frame()
            for i in range(MENU_EPISODES)]


def evaluate(seed,index,method,archives,coverage,source):
    if method not in METHODS:
        raise ValueError("invalid passive evidence comparison")
    if method=="privileged_oracle":
        original=old_episode(seed,index,"privileged_oracle",
                            {"random240":archives["random"],
                             "random24":archives["random"],
                             "oldpolicy240":archives["biased"]},
                            source,source)
        return original
    if method=="always_abstain":
        return {"success":0,"hurt":0,"stalled":1,"attempts":0,"abstained":1}
    selected=("random" if "random" in method else
              "biased" if "biased" in method else "forged")
    if method.startswith("coverage_gated") and not coverage[selected].report()["coverage_passed"]:
        return {"success":0,"hurt":0,"stalled":1,"attempts":0,"abstained":1}
    world=NovelFeatureWorld(seed,"test",index,"third_rule")
    model=archives[selected].memory()
    hurt=0
    for _ in range(world.frame()["budget"]):
        frame=world.frame()
        if frame["done"]:
            break
        action=model.choose(frame)
        if action is None:
            break
        after=world.step(action,frame["tick"])
        hurt+=int(outcome(frame,action,after)["damage"])
    return {"success":int(world.success()),"hurt":hurt,
            "stalled":int(not world.success()),"attempts":world.tick,
            "abstained":0}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("cannot relabel original passive evidence cohorts")
    out={"schema":SCHEMA,"blind":False,"training_actions_by_learner":0,
         "reference_has_no_interventions":True,
         "third_rule_training_source":"independent simulated actors",
         "train_random":[RANDOM_START,RANDOM_START+RECORDS-1],
         "train_biased":[BIASED_START,BIASED_START+RECORDS-1],
         "reference":[REFERENCE_START,REFERENCE_START+MENU_EPISODES-1],
         "test":[TEST_START,TEST_START+TEST_N-1],"rows":[]}
    for seed in seeds:
        source,_=fit(seed)
        source_before=source.record()
        random_obs=collect(seed,RANDOM_START,RECORDS,"random")
        biased_obs=collect(seed,BIASED_START,RECORDS,"old_normal",source)
        forged_obs,forged_count=fabricate_public_damage_as_progress(random_obs)
        archives={"random":random_obs,"biased":biased_obs,"forged":forged_obs}
        original_records={k:v.record() for k,v in archives.items()}
        public_frames=public_opportunities(seed)
        quality={name:PassiveEvidenceQuality(data,public_frames)
                 for name,data in archives.items()}
        audits={name:obj.report() for name,obj in quality.items()}
        scores={}
        for method in METHODS:
            results=[evaluate(seed,TEST_START+i,method,archives,quality,source)
                     for i in range(TEST_N)]
            scores[method]=old_score(results)
        if (source.record()!=source_before or
            any(archives[k].record()!=original_records[k] for k in archives)):
            raise AssertionError("evaluation contaminated source/observed records")
        out["rows"].append({"seed":seed,
                            "evidence_audit":audits,
                            "falsified_outcomes":forged_count,
                            "actual_actor_harm":{
                                "random":random_obs.stats()["actor_harmful_actions"],
                                "biased":biased_obs.stats()["actor_harmful_actions"]},
                            "recorded_harm_in_forged_dataset":
                                forged_obs.stats()["actor_harmful_actions"],
                            "scores":scores})
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","reserved"),
                   default="development")
    opt=p.parse_args()
    print(json.dumps(measure(DEV if opt.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
