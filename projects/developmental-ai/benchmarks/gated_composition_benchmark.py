"""Frozen contrast: composition of branch rules vs absent bitwise-XOR operator.

Truthful deterministic simulator, independent first-action TRAIN actor,
matched held-out TEST episodes, no phase labels or hidden salt delivered to
the learner. Candidate actions deliberately include 5 good / 4 harmful /
3 neutral choices; this is a favorable synthetic setting.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.gated_composition_memory import GatedCompositionMemory,_Gate,branch
from developmental_ai.composed_feature_memory import ComposedFeatureMemory,_ComposedBucket
from developmental_ai.feature_hypothesis_memory import FeatureHypothesisMemory,_Bucket
from developmental_ai.observable_affordances import digest,VariableOutcomeMemory
from benchmarks.cross_rule_benchmark import CrossRuleWorld,effect as source_effect
from benchmarks.relation_transfer_benchmark import summarize
from benchmarks.variable_affordance_benchmark import public_outcome

SCHEMA="developmental-ai.gated-composition-benchmark/v1"
DEV=(252003,252021,252039)
ADDITIONAL=(253001,253017,253041)
STAGES=(("source","source",1000,240),
        ("conditional","conditional",2000,128),
        ("return_source","source",3000,64),
        ("xor","xor",4000,128))
CHECKPOINTS={
    "conditional":(0,4,8,16,32,64,96,128),
    "return_source":(0,4,8,16,32,64),
    "xor":(0,4,8,16,32,64,96,128),
}
START={"conditional":290000,"return_source":300000,"xor":310000}
TEST_N=16
METHODS=("gated_composition","prior_global_composed",
         "prior_fixed_hypotheses","source_span","recent32_span",
         "privileged_correct_conditional","privileged_correct_xor",
         "random","abstain","perfect_action_oracle")
TRUE_LOW=((0,0),1,1,1,5)
TRUE_HIGH=((0,1),0,1,1,7)


def effect(seed,law,features):
    if law=="source":
        return source_effect(seed,"source",features)
    a,b=features["inlet"],features["outlet"]
    if law=="conditional":
        salt=int(digest([SCHEMA,seed,"conditional-salt"])[:12],16)
        if a>b:
            r=(a*b+a+salt)%7
            return "progress" if r<2 else "damage" if r<5 else "neutral"
        r=(a*a+b+salt)%5
        return "progress" if r<2 else "damage" if r<4 else "neutral"
    if law=="xor":
        salt=int(digest([SCHEMA,seed,"xor-salt"])[:12],16)
        r=((a^b)+salt)%5
        return "progress" if r<2 else "damage" if r<4 else "neutral"
    raise ValueError("unregistered private rule")


class ConditionalWorld(CrossRuleWorld):
    def __init__(self,seed,split,index,law):
        if law not in ("source","conditional","xor"):
            raise ValueError("unsupported private rule")
        super().__init__(seed,split,index,"source")
        self.law=law
        self.episode=digest([SCHEMA,seed,split,index,law])
        rng=random.Random(int(self.episode[:16],16))
        groups={"progress":[],"damage":[],"neutral":[]}
        for a in range(10):
            for b in range(10):
                f={"inlet":a,"outlet":b}
                groups[effect(seed,law,f)].append(f)
        candidates=[]
        for cls,n in (("progress",5),("damage",4),("neutral",3)):
            candidates.extend(rng.sample(groups[cls],n))
        rng.shuffle(candidates)
        ids=[f"a_{rng.getrandbits(72):018x}" for _ in candidates]
        if len(set(ids))!=12:
            raise AssertionError("action-ID collision")
        self._actions=dict(zip(ids,candidates))

    def _effect(self,features):
        return effect(self.seed,self.law,features)


class _XorPredictor:
    """Benchmark-privileged feature representation, not learner code."""
    def __init__(self,events):
        self.counts=[[0,0,0] for _ in range(5)]
        for event in events:
            k=self._bucket(event["features"])
            cls=0 if event["progress"] else 1 if event["damage"] else 2
            self.counts[k][cls]+=1

    @staticmethod
    def _bucket(features):
        return (features["inlet"]^features["outlet"])%5

    def estimate(self,features):
        counts=self.counts[self._bucket(features)]
        total=sum(counts)+0.75
        return tuple((value+0.25)/total for value in counts)

    def choose(self,frame):
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        ranks=[]
        for action in frame["actions"]:
            p,d,_=self.estimate(action["features"])
            ranks.append((-(3*p-10*d),action["id"]))
        return min(ranks)[1] if ranks else None


def actor_event(seed,law,index):
    w=ConditionalWorld(seed,"train",index,law)
    frame=w.frame()
    actor=random.Random(int(digest(["gated-external-actor",w.episode])[:16],16))
    choice=actor.choice(frame["actions"])["id"]
    return public_outcome(frame,choice,w.step(choice,frame["tick"]))


def training(seed,law,start,n):
    evidence=[actor_event(seed,law,start+i) for i in range(n)]
    return evidence,{
        "observations":len(evidence),
        "harmful":sum(int(e["damage"]) for e in evidence),
        "productive":sum(int(e["progress"]) for e in evidence),
        "neutral":sum(int(not e["progress"] and not e["damage"]) for e in evidence),
    }


def fitted(cls,events):
    obj=cls()
    for row in events:
        obj.observe(row)
    return cls.restore(obj.record())


def train_models(history):
    recent=history[-64:]
    lower=[e for e in recent if branch(e["features"])==0]
    higher=[e for e in recent if branch(e["features"])==1]
    return {
        "gated_composition":fitted(GatedCompositionMemory,history),
        "prior_global_composed":fitted(ComposedFeatureMemory,history),
        "prior_fixed_hypotheses":fitted(FeatureHypothesisMemory,history),
        "source_span":_Bucket("span",history[:192]),
        "recent32_span":_Bucket("span",history[-32:]),
        "privileged_correct_conditional":_Gate(
            _ComposedBucket(TRUE_LOW,lower),
            _ComposedBucket(TRUE_HIGH,higher)),
        "privileged_correct_xor":_XorPredictor(recent),
    }


def evaluate(seed,law,index,method,trained):
    if method not in METHODS:
        raise ValueError("unregistered comparator")
    world=ConditionalWorld(seed,"test",index,law)
    rand=random.Random(int(digest(["gated-test-random",world.episode])[:16],16))
    harmful=0
    abstained=0
    for _ in range(world.budget):
        frame=world.frame()
        if frame["done"]:
            break
        if method in trained:
            action=trained[method].choose(frame)
        elif method=="random":
            action=rand.choice(frame["actions"])["id"]
        elif method=="abstain":
            action=None
        else:
            action=next((a["id"] for a in frame["actions"]
                         if world._effect(a["features"])=="progress"),None)
        if action is None:
            abstained=1
            break
        after=world.step(action,frame["tick"])
        harmful+=int(public_outcome(frame,action,after)["damage"])
    return {"success":int(world.success()),"harmful_actions":harmful,
            "abstained":abstained,"attempts":world.tick}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("unregistered gated-composition cohort")
    report={"schema":SCHEMA,"protocol":"benchmarks/gated_composition_protocol.json",
            "blind":False,"learner_training_actions":0,
            "heldout_test_indices_reused_across_checkpoints":True,
            "target_xor_operator_absent_from_learner":True,
            "test_episodes_per_seed_checkpoint":TEST_N,"rows":[]}
    for seed in seeds:
        history=[]
        actor_cost={}
        results={}
        for stage,law,first,n in STAGES:
            sample,cost=training(seed,law,first,n)
            actor_cost[stage]=cost
            if stage=="source":
                history.extend(sample)
                continue
            checkpoints={}
            for k in CHECKPOINTS[stage]:
                evidence=history+sample[:k]
                policies=train_models(evidence)
                before={name:m.record() for name,m in policies.items()
                        if hasattr(m,"record")}
                decision=policies["gated_composition"].selection()[0]
                scored={
                    name:summarize([
                        evaluate(seed,law,START[stage]+i,name,policies)
                        for i in range(TEST_N)])
                    for name in METHODS
                }
                if any(policies[name].record()!=record
                       for name,record in before.items()):
                    raise AssertionError("held-out TEST mutated training evidence")
                checkpoints[str(k)]={
                    "phase_observations":k,
                    "total_public_training_events":len(evidence),
                    "selection":decision,
                    "checkpoint_sha256":before["gated_composition"]["sha256"],
                    "scores":scored,
                }
            results[stage]=checkpoints
            history.extend(sample)
        report["rows"].append({"seed":seed,"actor_cost":actor_cost,
                               "stages":results,"total_events":len(history)})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    a=p.parse_args()
    cohorts=DEV if a.cohort=="development" else ADDITIONAL
    print(json.dumps(measure(cohorts),sort_keys=True,indent=2))


if __name__=="__main__":
    main()
