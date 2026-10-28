"""Paired HMAC witness vs biased provenance and two-key collusion.

The external simulated actor generates each training action once; tampered
records are different claims about THE SAME actions. The learner never
controls training actions. The verifier's two fixture keys are supplied by
the benchmark as trusted reference material; they authenticate ONLY key
possession, not real observer identity or physical truth.
"""
from __future__ import annotations

import argparse
import copy
import json

from developmental_ai.observable_affordances import digest,outcome
from developmental_ai.novel_feature_world import NovelFeatureWorld
from developmental_ai.paired_witness import (
    PairedWitnessGate,sign_archive,RECORDS
)
from benchmarks.passive_outcome_benchmark import collect,score
from benchmarks.passive_quality_benchmark import fabricate_public_damage_as_progress

SCHEMA="developmental-ai.paired-witness-evaluation/v1"
DEV=(99211,99223,99239)
RESERVED=(99317,99329,99347)
TRAIN_START=4800
TEST_START=25000
TEST_N=60
METHODS=("two_honest_signers","forged_primary_honest_witness",
         "missing_witness","post_signature_tamper",
         "forged_primary_colluding_witness","single_forged_no_gate",
         "single_honest_no_gate","always_abstain",
         "privileged_true_effect_oracle")


def keys_for_seed(seed):
    # Deterministic and known by benchmark harness; DEMO ONLY.
    # Not key management, user authentication or secure attestation.
    return {role:bytes.fromhex(digest(["fixture-pair-secret",seed,role]))
            for role in ("primary","witness")}


def training_and_claims(seed):
    actor=collect(seed,TRAIN_START,RECORDS,"random")
    forged,changes=fabricate_public_damage_as_progress(actor)
    keys=keys_for_seed(seed)
    primary_good=sign_archive(actor,"primary",keys["primary"])
    witness_good=sign_archive(actor,"witness",keys["witness"])
    primary_bad=sign_archive(forged,"primary",keys["primary"])
    witness_bad=sign_archive(forged,"witness",keys["witness"])
    tampered=copy.deepcopy(witness_good)
    # Change claimed outcome AFTER signing, keeping its MAC unchanged.
    tampered[0]["event"]["outcome"]["progress"]=not tampered[0]["event"]["outcome"]["progress"]
    signed={
        "two_honest_signers":(primary_good,witness_good),
        "forged_primary_honest_witness":(primary_bad,witness_good),
        "missing_witness":(primary_good,None),
        "post_signature_tamper":(primary_good,tampered),
        "forged_primary_colluding_witness":(primary_bad,witness_bad),
    }
    return actor,forged,changes,keys,signed


def simulate_test(seed,index,method,model):
    if method=="always_abstain" or model is None and method!="privileged_true_effect_oracle":
        return {"success":0,"hurt":0,"stalled":1,"attempts":0,"abstained":1}
    world=NovelFeatureWorld(seed,"test",index,"third_rule")
    harmful=0
    for _ in range(world.frame()["budget"]):
        before=world.frame()
        if before["done"]:
            break
        if method=="privileged_true_effect_oracle":
            candidates=[x["id"] for x in before["actions"]
                        if world._effect(x["id"])=="progress"]
            action=candidates[0] if candidates else None
        else:
            action=model.choose(before)
        if action is None:
            break
        after=world.step(action,before["tick"])
        harmful+=int(outcome(before,action,after)["damage"])
    return {"success":int(world.success()),"hurt":harmful,
            "stalled":int(not world.success()),"attempts":world.tick,
            "abstained":int(world.tick==0)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("cannot replace frozen paired witness seed cohorts")
    report={"schema":SCHEMA,"blind":False,
            "observer_keys":"benchmark-fixture-only",
            "physical_truth_authenticated":False,
            "learner_generated_training_actions":0,
            "train":[TRAIN_START,TRAIN_START+RECORDS-1],
            "test":[TEST_START,TEST_START+TEST_N-1],
            "rows":[]}
    for seed in seeds:
        actor,forged,forgeries,keys,streams=training_and_claims(seed)
        truth_before=actor.record()
        forged_before=forged.record()
        verifier=PairedWitnessGate(keys)
        results={}
        for method in METHODS:
            if method in streams:
                decision=verifier.assess(*streams[method])
                receipt=verifier.receipt(decision)
                model=decision["archive"].memory() if decision["approved"] else None
                audit={**receipt["state"],"receipt_sha256":receipt["sha256"]}
            elif method=="single_forged_no_gate":
                model=forged.memory()
                audit={"approved":True,"reason":"ungated",
                       "fixture_signatures_verified":False,
                       "physical_truth_verified":False}
            elif method=="single_honest_no_gate":
                model=actor.memory()
                audit={"approved":True,"reason":"ungated",
                       "fixture_signatures_verified":False,
                       "physical_truth_verified":False}
            else:
                model=None
                audit={"approved":False,"reason":"oracle" if method=="privileged_true_effect_oracle" else "abstain",
                       "fixture_signatures_verified":False,
                       "physical_truth_verified":method=="privileged_true_effect_oracle"}
            trials=[simulate_test(seed,TEST_START+i,method,model)
                    for i in range(TEST_N)]
            results[method]={"audit":audit,"evaluation":score(trials)}
        if actor.record()!=truth_before or forged.record()!=forged_before:
            raise AssertionError("test observations modified source data")
        report["rows"].append({
            "seed":seed,
            "actual_training_actor_harm":actor.stats()["actor_harmful_actions"],
            "forged_outcomes":forgeries,
            "forged_claim_harm":forged.stats()["actor_harmful_actions"],
            "scores":results})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","reserved"),
                   default="development")
    opts=p.parse_args()
    print(json.dumps(measure(DEV if opts.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
