"""Frozen stochastic actual outcomes and imperfect public reports.

Each simulated nonneutral action can flip its true outcome at an
independent hash-seeded 1/8 rate. An independent 1/20 sampling draw
may invert non-neutral *reported TRAIN* outcomes without changing
actual source harm. All policies see the exact same learner-visible
stream; scoring uses disjoint stochastic TEST episodes.
"""
from __future__ import annotations

import argparse
import json
import math
import random

from developmental_ai.observable_affordances import digest
from developmental_ai.prequential_ensemble_memory import PrequentialEnsembleMemory
from developmental_ai.multi_switch_memory import MultiSwitchContrastMemory
from developmental_ai.adaptive_horizon_memory import AdaptiveHorizonMemory
from developmental_ai.fast_shock_memory import FastShockMemory
from benchmarks.same_schema_switch_benchmark import SameSchemaWorld
from benchmarks.relation_transfer_benchmark import relation_model, summarize
from benchmarks.variable_affordance_benchmark import public_outcome

SCHEMA="developmental-ai.stochastic-prequential-benchmark/v1"
DEV=(212003,212021,212039)
ADDITIONAL=(213001,213017,213041)
STAGES=(("A","original",1000,240),("B1","reversed",2000,64),
        ("return_A","original",3000,48),("B2","reversed",4000,64))
CHECKPOINTS={
    "B1":(0,2,4,8,12,24,32,64),
    "return_A":(0,2,4,8,12,24,48),
    "B2":(0,2,4,8,12,24,32,64),
}
TEST_START={"B1":160000,"return_A":170000,"B2":180000}
TEST_N=16
METHODS=(
    "prequential_ensemble","contrastive_multi","adaptive_horizon",
    "fast_shock","recent8","recent32","frozen_A",
    "untrained_random","always_abstain","privileged_expected_oracle"
)


class StochasticWorld(SameSchemaWorld):
    """Hidden outcomes pseudo-randomly flip; public frame remains unchanged."""

    def __init__(self,seed,split,index,physics):
        super().__init__(seed,split,index,physics)
        self._split=split
        self._index=index

    def _sample_outcome(self,action,tick):
        base=self._effect(self._actions[action])
        if base=="neutral":
            return base
        draw=int(digest(["stochastic-physics/v1",self.seed,self._split,
                         self._index,action,tick])[:12],16) % 8
        if draw==0:
            return "progress" if base=="damage" else "damage"
        return base

    def step(self,action,tick):
        if (self.done or type(tick) is not int or tick!=self.tick
                or type(action) is not str or action not in self._actions
                or action in self._used):
            raise ValueError("stale or invalid stochastic action")
        result=self._sample_outcome(action,tick)
        self.tick+=1
        self.progress+=int(result=="progress")
        self.damage+=int(result=="damage")
        self._used.add(action)
        self.done=(self.progress>=self.goal or self.damage>0
                   or self.tick>=self.budget
                   or len(self._used)==len(self._actions))
        return self.frame()


def public_train(seed,physics,first,count):
    observed=[]
    cost={"observations":count,"actual_harmful":0,
          "actual_productive":0,"actual_neutral":0,
          "reported_harmful":0,"label_flips":0}
    for idx in range(first,first+count):
        world=StochasticWorld(seed,"train",idx,physics)
        before=world.frame()
        actor=random.Random(int(digest(["stochastic-external-actor/v1",
                                       world.episode])[:16],16))
        chosen=actor.choice(before["actions"])["id"]
        after=world.step(chosen,before["tick"])
        actual=public_outcome(before,chosen,after)
        cost["actual_harmful"]+=int(actual["damage"])
        cost["actual_productive"]+=int(actual["progress"])
        cost["actual_neutral"]+=int(not actual["progress"] and not actual["damage"])
        reported=dict(actual)
        flipped=(int(digest(["stochastic-report-noise/v1",seed,
                             idx])[:12],16) % 20 ==0)
        if flipped and (reported["progress"] or reported["damage"]):
            reported["progress"],reported["damage"]=(reported["damage"],
                                                     reported["progress"])
            cost["label_flips"]+=1
        cost["reported_harmful"]+=int(reported["damage"])
        observed.append(reported)
    return observed,cost


def fitted(cls,events):
    model=cls()
    for event in events:
        model.observe(event)
    return cls.restore(model.record())


def trained_models(history):
    return {
        "prequential_ensemble":fitted(PrequentialEnsembleMemory,history),
        "contrastive_multi":fitted(MultiSwitchContrastMemory,history),
        "adaptive_horizon":fitted(AdaptiveHorizonMemory,history),
        "fast_shock":fitted(FastShockMemory,history),
        "recent8":relation_model(history[-8:]),
        "recent32":relation_model(history[-32:]),
        "frozen_A":relation_model(history[:192]),
    }


def evaluate(seed,physics,index,method,models):
    if method not in METHODS:
        raise ValueError("unsupported stochastic benchmark policy")
    world=StochasticWorld(seed,"test",index,physics)
    random_policy=random.Random(int(digest(["stochastic-test-random/v1",
                                              world.episode])[:16],16))
    harm=0
    abstain=0
    for _ in range(world.budget):
        frame=world.frame()
        if frame["done"]:
            break
        if method in models:
            picked=models[method].choose(frame)
        elif method=="untrained_random":
            picked=random_policy.choice(frame["actions"])["id"]
        elif method=="always_abstain":
            picked=None
        else:
            # Privileged only as to expected hidden rule, not the
            # independently sampled outcome for this action.
            picked=next((x["id"] for x in frame["actions"]
                         if world._effect(x["features"])=="progress"),None)
        if picked is None:
            abstain=1
            break
        after=world.step(picked,frame["tick"])
        harm+=int(public_outcome(frame,picked,after)["damage"])
    return {"success":int(world.success()),"harmful_actions":harm,
            "abstained":abstain,"attempts":world.tick}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("cohort not precommitted")
    report={"schema":SCHEMA,
            "protocol":"benchmarks/stochastic_prequential_protocol.json",
            "blind":False,"learner_training_actions":0,
            "test_episodes_per_checkpoint_seed":TEST_N,
            "repeated_test_indices_across_checkpoints":True,
            "actual_outcomes_stochastic":True,"rows":[]}
    for seed in seeds:
        history=[]
        actor_costs={}
        stages={}
        for stage,physics,first,n in STAGES:
            train,cost=public_train(seed,physics,first,n)
            actor_costs[stage]=cost
            if stage=="A":
                history.extend(train)
                continue
            phase={}
            for k in CHECKPOINTS[stage]:
                observed=history+train[:k]
                models=trained_models(observed)
                checkpoint={name:obj.record() for name,obj in models.items()}
                weights=models["prequential_ensemble"].selection()[0]
                scores={
                    method:summarize([
                        evaluate(seed,physics,TEST_START[stage]+j,method,models)
                        for j in range(TEST_N)])
                    for method in METHODS
                }
                if any(models[name].record()!=saved
                       for name,saved in checkpoint.items()):
                    raise AssertionError("heldout test feedback contaminated training")
                phase[str(k)]={
                    "observations_in_stage":k,
                    "total_observed":len(observed),
                    "prequential":weights,
                    "checkpoint_sha256":checkpoint["prequential_ensemble"]["sha256"],
                    "scores":scores}
            stages[stage]=phase
            history.extend(train)
        report["rows"].append({"seed":seed,
                               "true_and_reported_training_costs":actor_costs,
                               "stages":stages,"final_training_count":len(history)})
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    a=p.parse_args()
    print(json.dumps(measure(DEV if a.cohort=="development" else ADDITIONAL),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
