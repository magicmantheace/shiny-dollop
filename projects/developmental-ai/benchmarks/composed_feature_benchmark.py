"""Precommitted nonlinear worlds absent from the former fixed hypothesis menu.

The private nonlinear target rules are authored here in the SIMULATOR.
The model instead receives only inlet/outlet and labels and can combine
generic multiplication, addition, scaling and modular reduction operators
via a bounded, developer-specified grammar. No oracle rule name, private
salt, actor handle or simulator class enters the model's event store.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.composed_feature_memory import (
    ComposedFeatureMemory,_ComposedBucket,PROGRAMS
)
from developmental_ai.feature_hypothesis_memory import FeatureHypothesisMemory,_Bucket
from developmental_ai.observable_affordances import digest
from benchmarks.cross_rule_benchmark import (
    CrossRuleWorld,effect as source_effect
)
from benchmarks.relation_transfer_benchmark import summarize
from benchmarks.variable_affordance_benchmark import public_outcome

SCHEMA="developmental-ai.composed-feature-benchmark/v1"
DEV=(242003,242021,242039)
ADDITIONAL=(243001,243017,243041)
STAGES=(("source","source",1000,240),
        ("product","product",2000,128),
        ("return_source","source",3000,64),
        ("square","square",4000,128))
CHECKPOINTS={
    "product":(0,4,8,16,32,64,96,128),
    "return_source":(0,4,8,16,32,64),
    "square":(0,4,8,16,32,64,96,128),
}
TEST_START={"product":260000,"return_source":270000,"square":280000}
TEST_N=16
METHODS=(
    "composed_grammar","prior_fixed_library","frozen_source",
    "recent8_span","recent32_span","recent32_product_privileged",
    "recent32_square_privileged","privileged_action_oracle",
    "untrained_random","always_abstain",
)
# Private evaluator-only programs: not exposed as named model
# hypotheses or passed as learner inputs.
TRUE_COMPOSITIONS={
    "product":((0,1),0,1,1,7),
    "square":((0,0),1,1,1,5),
}


def effect(seed,law,features):
    if law=="source":
        return source_effect(seed,"source",features)
    a=features["inlet"]
    b=features["outlet"]
    if law=="product":
        salt=int(digest(["composed-physics",seed,"product"])[:12],16)%7
        r=(a*b+a+salt)%7
        return "progress" if r<2 else "damage" if r<5 else "neutral"
    if law=="square":
        salt=int(digest(["composed-physics",seed,"square"])[:12],16)%5
        r=(a*a+b+salt)%5
        return "progress" if r<2 else "damage" if r<4 else "neutral"
    raise ValueError("unregistered private nonlinear world")


class ComposedWorld(CrossRuleWorld):
    def __init__(self,seed,split,index,law):
        if law not in ("source","product","square"):
            raise ValueError("unregistered rule family")
        # Reuse exact public frame and terminal dynamics, but freshly
        # generate causal actions using this world family's private law.
        super().__init__(seed,split,index,"source")
        self.law=law
        self.episode=digest([SCHEMA,seed,split,index,law])
        rng=random.Random(int(self.episode[:16],16))
        classes={"progress":[],"damage":[],"neutral":[]}
        for a in range(10):
            for b in range(10):
                f={"inlet":a,"outlet":b}
                classes[effect(seed,law,f)].append(f)
        actions=[]
        for outcome,n in (("progress",5),("damage",4),("neutral",3)):
            actions.extend(rng.sample(classes[outcome],n))
        rng.shuffle(actions)
        names=[f"a_{rng.getrandbits(72):018x}" for _ in actions]
        if len(set(names))!=len(names):
            raise AssertionError("simulated anonymous identifier collision")
        self._actions=dict(zip(names,actions))

    def _effect(self,features):
        return effect(self.seed,self.law,features)


def actor_event(seed,law,index):
    world=ComposedWorld(seed,"train",index,law)
    before=world.frame()
    actor=random.Random(int(digest(["composed-independent-actor",
                                   world.episode])[:16],16))
    action=actor.choice(before["actions"])["id"]
    return public_outcome(before,action,world.step(action,before["tick"]))


def training(seed,law,start,length):
    stream=[actor_event(seed,law,start+i) for i in range(length)]
    return stream,{
        "observations":len(stream),
        "harmful":sum(int(e["damage"]) for e in stream),
        "productive":sum(int(e["progress"]) for e in stream),
        "neutral":sum(int(not e["progress"] and not e["damage"]) for e in stream),
    }


def models(history):
    creative=ComposedFeatureMemory()
    fixed=FeatureHypothesisMemory()
    for e in history:
        creative.observe(e)
        fixed.observe(e)
    return {
        "composed_grammar":ComposedFeatureMemory.restore(creative.record()),
        "prior_fixed_library":FeatureHypothesisMemory.restore(fixed.record()),
        "frozen_source":_Bucket("span",history[:192]),
        "recent8_span":_Bucket("span",history[-8:]),
        "recent32_span":_Bucket("span",history[-32:]),
        "recent32_product_privileged":_ComposedBucket(
            TRUE_COMPOSITIONS["product"],history[-32:]),
        "recent32_square_privileged":_ComposedBucket(
            TRUE_COMPOSITIONS["square"],history[-32:]),
    }


def evaluate(seed,law,index,method,trained):
    if method not in METHODS:
        raise ValueError("unregistered comparator")
    world=ComposedWorld(seed,"test",index,law)
    actor=random.Random(int(digest(["composed-test-random",
                                   world.episode])[:16],16))
    harmful=0
    abstain=0
    for _ in range(world.budget):
        frame=world.frame()
        if frame["done"]:
            break
        if method in trained:
            picked=trained[method].choose(frame)
        elif method=="privileged_action_oracle":
            picked=next((x["id"] for x in frame["actions"]
                         if world._effect(x["features"])=="progress"),None)
        elif method=="untrained_random":
            picked=actor.choice(frame["actions"])["id"]
        else:
            picked=None
        if picked is None:
            abstain=1
            break
        after=world.step(picked,frame["tick"])
        harmful+=int(public_outcome(frame,picked,after)["damage"])
    return {"success":int(world.success()),"harmful_actions":harmful,
            "abstained":abstain,"attempts":world.tick}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("unregistered compositional cohort")
    report={"schema":SCHEMA,
            "protocol":"benchmarks/composed_feature_protocol.json",
            "blind":False,"learner_training_actions":0,
            "same_public_sensor_keys":True,
            "generated_grammar_includes_both_target_functions":True,
            "reuses_heldout_test_indices_across_checkpoints":True,
            "heldout_test_episodes_per_checkpoint_seed":TEST_N,
            "rows":[]}
    for seed in seeds:
        prior=[]
        costs={}
        phase_results={}
        for stage,law,first,n in STAGES:
            observed,actor_cost=training(seed,law,first,n)
            costs[stage]=actor_cost
            if stage=="source":
                prior.extend(observed)
                continue
            checkpoints={}
            for k in CHECKPOINTS[stage]:
                history=prior+observed[:k]
                trained=models(history)
                evidence_snap={
                    key:learner.record() for key,learner in trained.items()
                    if hasattr(learner,"record")
                }
                selection=trained["composed_grammar"].selection()[0]
                results={
                    method:summarize([
                        evaluate(seed,law,TEST_START[stage]+i,method,trained)
                        for i in range(TEST_N)])
                    for method in METHODS
                }
                if any(trained[name].record()!=record
                       for name,record in evidence_snap.items()):
                    raise AssertionError("held-out TEST contaminated public TRAIN evidence")
                checkpoints[str(k)]={
                    "observations_after_change":k,
                    "all_observations":len(history),
                    "composed_choice":selection,
                    "checkpoint_sha256":evidence_snap["composed_grammar"]["sha256"],
                    "scores":results,
                }
            phase_results[stage]=checkpoints
            prior.extend(observed)
        report["rows"].append({"seed":seed,"external_actor_costs":costs,
                               "stages":phase_results,"final_events":len(prior)})
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","additional"),
                        default="development")
    args=parser.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="development" else ADDITIONAL),
                     sort_keys=True,indent=2))


if __name__=="__main__":
    main()
