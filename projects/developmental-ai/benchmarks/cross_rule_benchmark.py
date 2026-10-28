"""Falsifiable evaluation across independently different, handcrafted causal rules.

Source law is an absolute span/band. Target checksum and ordered laws
instead depend on asymmetric weighted integer residues, not on span.
The SAME two public sensor keys and anonymous action interface appear
in every law. No law name, task marker or hidden seed parameter is
included in the learner's append-only public evidence.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.feature_hypothesis_memory import (
    FeatureHypothesisMemory, _Bucket
)
from developmental_ai.observable_affordances import digest
from benchmarks.relation_transfer_benchmark import band, relation_model, summarize
from benchmarks.variable_affordance_benchmark import (
    SCHEMA as FRAME_SCHEMA, public_outcome,
)

SCHEMA="developmental-ai.cross-rule-hypothesis-benchmark/v1"
DEV=(232003,232021,232039)
ADDITIONAL=(233001,233017,233041)
STAGES=(
    ("source","source",1000,240),
    ("checksum","checksum",2000,96),
    ("return_source","source",3000,48),
    ("ordered","ordered",4000,96),
)
CHECKPOINTS={
    "checksum":(0,4,8,16,32,64,96),
    "return_source":(0,4,8,16,32,48),
    "ordered":(0,4,8,16,32,64,96),
}
TEST_START={"checksum":230000,"return_source":240000,"ordered":250000}
TEST_N=20
METHODS=(
    "hypothesis_selector","frozen_source_span",
    "recent8_span","recent32_span",
    "recent24_checksum","recent24_ordered",
    "recent24_true_rule_privileged",
    "untrained_random","always_abstain","privileged_action_oracle",
)


def effect(seed,law,features):
    a,b=features["inlet"],features["outlet"]
    if law=="source":
        k=band(seed)
        gap=abs(a-b)
        return ("progress" if gap in (k,k+1) else
                "damage" if gap<=k-2 or gap>=k+3 else "neutral")
    if law=="checksum":
        salt=int(digest([SCHEMA,seed,"checksum-salt"])[:12],16)%5
        r=(2*a+b+salt)%5
        return "progress" if r<2 else "damage" if r<4 else "neutral"
    if law=="ordered":
        salt=int(digest([SCHEMA,seed,"ordered-salt"])[:12],16)%7
        r=(a+3*b+salt)%7
        return "progress" if r<2 else "damage" if r<5 else "neutral"
    raise ValueError("not one of the frozen hidden physics families")


class CrossRuleWorld:
    def __init__(self,seed,split,index,law):
        if (type(seed) is not int or split not in ("train","test") or
                type(index) is not int or not 0<=index<1000000 or
                law not in ("source","checksum","ordered")):
            raise ValueError("invalid causal-family world")
        self.seed,self.law=seed,law
        self.episode=digest([SCHEMA,seed,split,index,law])
        self.tick=0
        self.budget=6
        self.goal=3
        self.progress=0
        self.damage=0
        self.done=False
        self._used=set()
        rng=random.Random(int(self.episode[:16],16))
        candidates={"progress":[],"damage":[],"neutral":[]}
        for a in range(10):
            for b in range(10):
                features={"inlet":a,"outlet":b}
                candidates[effect(seed,law,features)].append(features)
        # Stratified, independent, unique causal action frames. Candidate
        # distribution is intentionally artificially favorable.
        sampled=[]
        for outcome,count in (("progress",5),("damage",4),("neutral",3)):
            sampled.extend(rng.sample(candidates[outcome],count))
        rng.shuffle(sampled)
        handles=[f"a_{rng.getrandbits(72):018x}" for _ in sampled]
        if len(set(handles))!=12:
            raise AssertionError("unexpected anonymous handle collision")
        self._actions=dict(zip(handles,sampled))

    def frame(self):
        return {"schema":FRAME_SCHEMA,"episode":self.episode,
                "tick":self.tick,"budget":self.budget,
                "progress":self.progress,"damage":self.damage,
                "target":self.goal,"done":self.done,
                "actions":[{"id":name,"features":dict(f)}
                           for name,f in self._actions.items()
                           if name not in self._used] if not self.done else []}

    def _effect(self,features):
        return effect(self.seed,self.law,features)

    def step(self,action,tick):
        if (self.done or type(tick) is not int or tick!=self.tick
                or type(action) is not str or action not in self._actions
                or action in self._used):
            raise ValueError("invalid or stale simulator action")
        result=self._effect(self._actions[action])
        self.tick+=1
        self.progress+=int(result=="progress")
        self.damage+=int(result=="damage")
        self._used.add(action)
        self.done=(self.progress>=self.goal or self.damage>0 or
                   self.tick>=self.budget or
                   len(self._used)==len(self._actions))
        return self.frame()

    def success(self):
        return self.progress>=self.goal and self.damage==0


def actor_event(seed,law,index):
    world=CrossRuleWorld(seed,"train",index,law)
    before=world.frame()
    actor=random.Random(int(digest(["independent-cross-rule-actor",
                                   world.episode])[:16],16))
    picked=actor.choice(before["actions"])["id"]
    after=world.step(picked,before["tick"])
    return public_outcome(before,picked,after)


def external_training(seed,law,first,count):
    samples=[actor_event(seed,law,first+i) for i in range(count)]
    return samples,{
        "observations":len(samples),
        "harmful":sum(int(x["damage"]) for x in samples),
        "productive":sum(int(x["progress"]) for x in samples),
        "neutral":sum(int(not x["progress"] and not x["damage"])
                      for x in samples),
    }


def policies(history):
    hypothesis=FeatureHypothesisMemory()
    for event in history:
        hypothesis.observe(event)
    return {
        "hypothesis_selector":FeatureHypothesisMemory.restore(hypothesis.record()),
        "frozen_source_span":relation_model(history[:192]),
        "recent8_span":relation_model(history[-8:]),
        "recent32_span":relation_model(history[-32:]),
        "recent24_checksum":_Bucket("checksum",history[-24:]),
        "recent24_ordered":_Bucket("ordered",history[-24:]),
    }


def evaluate(seed,law,index,method,trained):
    if method not in METHODS:
        raise ValueError("method absent from frozen protocol")
    world=CrossRuleWorld(seed,"test",index,law)
    random_actor=random.Random(int(digest(["cross-rule-test-random",
                                          world.episode])[:16],16))
    if method=="recent24_true_rule_privileged":
        # This comparator sees the law *name* from the benchmark, which
        # the learner NEVER receives. The trained input events are identical.
        fixed=("span" if law=="source" else law)
        chosen=_Bucket(fixed,trained["_history"][-24:])
    hurt=0
    abstained=0
    for _ in range(world.budget):
        frame=world.frame()
        if frame["done"]:
            break
        if method in trained:
            action=trained[method].choose(frame)
        elif method=="recent24_true_rule_privileged":
            action=chosen.choose(frame)
        elif method=="untrained_random":
            action=random_actor.choice(frame["actions"])["id"]
        elif method=="always_abstain":
            action=None
        else:
            action=next((x["id"] for x in frame["actions"]
                         if world._effect(x["features"])=="progress"),None)
        if action is None:
            abstained=1
            break
        after=world.step(action,frame["tick"])
        hurt+=int(public_outcome(frame,action,after)["damage"])
    return {"success":int(world.success()),"harmful_actions":hurt,
            "abstained":abstained,"attempts":world.tick}


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("unregistered causal-family seed cohort")
    report={"schema":SCHEMA,"protocol":"benchmarks/cross_rule_protocol.json",
            "blind":False,"learner_training_actions":0,
            "same_public_sensor_keys":True,
            "manually_authored_hypothesis_formulas":True,
            "repeated_heldout_test_indices_by_checkpoint":True,
            "test_episodes_per_checkpoint_seed":TEST_N,
            "rows":[]}
    for seed in seeds:
        prior=[]
        actor_cost={}
        scores={}
        for stage,law,start,n in STAGES:
            batch,cost=external_training(seed,law,start,n)
            actor_cost[stage]=cost
            if stage=="source":
                prior.extend(batch)
                continue
            checkpoints={}
            for feedback in CHECKPOINTS[stage]:
                history=prior+batch[:feedback]
                fitted=policies(history)
                records={name:model.record() for name,model in fitted.items()
                         if hasattr(model,"record")}
                selection=fitted["hypothesis_selector"].selection()[0]
                fitted["_history"]=history  # benchmark-only, never in model
                measurements={
                    method:summarize([
                        evaluate(seed,law,TEST_START[stage]+j,method,fitted)
                        for j in range(TEST_N)])
                    for method in METHODS}
                if any(fitted[name].record()!=snapshot
                       for name,snapshot in records.items()):
                    raise AssertionError("heldout TEST modified trained state")
                checkpoints[str(feedback)]={
                    "recent_feedback_events":feedback,
                    "total_public_training_events":len(history),
                    "selection":selection,
                    "checkpoint_sha256":records["hypothesis_selector"]["sha256"],
                    "scores":measurements,
                }
            scores[stage]=checkpoints
            prior.extend(batch)
        report["rows"].append({"seed":seed,"source_actor_costs":actor_cost,
                               "stages":scores,"total_training_events":len(prior)})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),
                   default="development")
    a=p.parse_args()
    cohort=DEV if a.cohort=="development" else ADDITIONAL
    print(json.dumps(measure(cohort),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
