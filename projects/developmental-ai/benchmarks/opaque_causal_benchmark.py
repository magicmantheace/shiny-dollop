"""Frozen-development comparison of one observable-action learner on two dynamics.

No stable action names or state-channel identities transfer across episodes.
Source training selects only a *strategy family*, NOT learned action meanings.
Two generators share an engineered common numeric public contract.
"""
from __future__ import annotations

import argparse
import json
import random
from developmental_ai.opaque_causal import BUDGET, OpaqueWorld, OpaqueEpisodePolicy, POLICIES
from developmental_ai.outcome_skills import canonical, digest

SCHEMA="developmental-ai.opaque-causal-evaluation/v1"
DEV=(1103,1109,1123)
RESERVED=(2017,2027,2039)
TRAIN_N=48
VALIDATION_N=24
TEST_N=60
FAMILIES=("relay","cargo")
METHODS=("selected","novel","retry","switch","cyclic","random","oracle")


def _privileged_plan(world):
    # For the upper reference ONLY. No controller is handed these handles.
    names=(("power","switch","combine","gate","endpoint")
           if world.family=="relay"
           else ("extract","charge","refine","fuel","load","ship"))
    return [world._ids[name] for name in names]


def episode(seed, split, index, family, mode, *, collect_journal=False):
    world=OpaqueWorld(seed,split,index,family)
    if mode not in (*POLICIES,"cyclic","random","oracle"):
        raise ValueError("unknown experiment method")
    learner=OpaqueEpisodePolicy(mode) if mode in POLICIES else None
    oracle=_privileged_plan(world) if mode=="oracle" else None
    rng=random.Random(int(world.episode[:16],16)^0x5b331)
    blocked=0
    negative=0
    sabotage=0
    for _ in range(BUDGET):
        if world.done:
            break
        frame=world.frame()
        if learner is not None:
            action=learner.choose(frame)
        elif mode=="random":
            action=rng.choice(frame["actions"])
        elif mode=="cyclic":
            action=frame["actions"][frame["tick"]%len(frame["actions"])]
        else:
            action=oracle[frame["tick"]] if frame["tick"]<len(oracle) else None
        if action is None:
            break
        hidden_name=world._lookup[action]  # scoring only
        response=world.step(action,frame["tick"])
        after=response["frame"]
        if learner is not None:
            learner.feedback(frame,action,response["accepted"],after)
        blocked+=int(not response["accepted"])
        negative+=int(any(y<x for x,y in zip(frame["channels"],after["channels"])))
        sabotage+=int(hidden_name=="spoil" and response["accepted"])
    success=world._state[world._target]>=1  # scoring only
    result={"success":int(success),"attempts":world.tick,"blocked":blocked,
            "negative_steps":negative,"sabotage":sabotage,"stalled":int(not world.done)}
    if learner is not None and collect_journal and learner.history:
        saved=learner.record()
        restored=OpaqueEpisodePolicy.restore(saved)
        if restored.record()!=saved:
            raise AssertionError("observation-only learning journal did not replay")
        result["journal_sha256"]=saved["sha256"]
        if not world.done and restored.choose(world.frame())!=learner.choose(world.frame()):
            raise AssertionError("resume action differs")
    return result


def summarize(rows):
    if not rows:
        raise ValueError("empty outcome list")
    return {"successes":sum(r["success"] for r in rows),
            "episodes":len(rows),
            "mean_attempts":round(sum(r["attempts"] for r in rows)/len(rows),3),
            "mean_blocked":round(sum(r["blocked"] for r in rows)/len(rows),3),
            "negative_steps":sum(r["negative_steps"] for r in rows),
            "sabotage":sum(r["sabotage"] for r in rows),
            "stalled":sum(r["stalled"] for r in rows)}


class StrategySelector:
    """Tiny observed-reward meta-learner: chooses one hand-coded strategy.

    Deliberately does not infer a reusable action ontology, hidden rule or
    policy network. The training objective includes action cost on failures.
    """
    def __init__(self):
        self.rows=[]
        self.selection=None

    def add(self,index, outcomes):
        if (self.selection is not None or type(index) is not int or
            index!=len(self.rows) or index>=TRAIN_N or type(outcomes) is not dict or
            set(outcomes)!=set(POLICIES)):
            raise ValueError("invalid source policy-fit episode")
        for method,score in outcomes.items():
            if (type(score) is not dict or
                set(score)!={"success","attempts","blocked","negative_steps","sabotage","stalled"} or
                type(score["success"]) is not int or score["success"] not in (0,1) or
                any(type(v) is not int or not 0<=v<=BUDGET for v in score.values()) or
                score["blocked"]>score["attempts"]):
                raise ValueError("invalid observed source reward")
        self.rows.append(json.loads(canonical(outcomes)))

    def freeze(self):
        if self.selection is not None or len(self.rows)!=TRAIN_N:
            raise ValueError("training cohort incomplete")
        scored={}
        for method in POLICIES:
            successes=sum(r[method]["success"] for r in self.rows)
            attempts=sum(r[method]["attempts"] for r in self.rows)
            # Primary: success. Secondary: cost, never rescued by test scores.
            scored[method]=(successes,-attempts)
        self.selection=min(method for method in POLICIES if scored[method]==max(scored.values()))
        return self.selection

    def record(self):
        if self.selection is None:
            raise ValueError("unfinished policy selection")
        state={"schema":SCHEMA,"rows":self.rows,"selection":self.selection}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,saved):
        if (type(saved) is not dict or set(saved)!={"state","sha256"} or
            type(saved["state"]) is not dict or saved["sha256"]!=digest(saved["state"])):
            raise ValueError("invalid meta-selection digest")
        s=saved["state"]
        if set(s)!={"schema","rows","selection"} or s["schema"]!=SCHEMA or type(s["rows"]) is not list:
            raise ValueError("invalid meta-selection schema")
        model=cls()
        for index,record in enumerate(s["rows"]):
            model.add(index,record)
        if model.freeze()!=s["selection"] or model.record()!=saved:
            raise ValueError("replayed strategy choice mismatch")
        return model


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("only precommitted seed cohorts")
    report={"schema":SCHEMA,"blind":False,"same_numeric_interface":True,
            "opaque_actions":True,"shared_glyphs":False,"train_family":"relay",
            "test_families":list(FAMILIES),
            "source_train_indices":[0,TRAIN_N-1],
            "validation_indices":[500,500+VALIDATION_N-1],
            "test_indices":[8000,8000+TEST_N-1],
            "rows":[]}
    for seed in seeds:
        fit=StrategySelector()
        for i in range(TRAIN_N):
            outcomes={m:episode(seed,"train",i,"relay",m) for m in POLICIES}
            fit.add(i,outcomes)
        selected=fit.freeze()
        fit_snapshot=fit.record()
        replay=StrategySelector.restore(fit_snapshot)
        if replay.selection!=selected:
            raise AssertionError("meta-learner checkpoint inconsistent")
        validation={m:summarize([episode(seed,"train",500+i,"relay",m)
                                 for i in range(VALIDATION_N)])
                    for m in POLICIES}
        families={}
        for family in FAMILIES:
            families[family]={}
            for method in METHODS:
                policy=selected if method=="selected" else method
                outcomes=[episode(seed,"test",8000+i,family,policy,
                                  collect_journal=(method=="selected" and i==0))
                          for i in range(TEST_N)]
                families[family][method]=summarize(outcomes)
        if fit.record()!=fit_snapshot:
            raise AssertionError("held-out evaluation mutated source strategy selection")
        report["rows"].append({"seed":seed,"source_selection":selected,
                               "source_sha256":fit.record()["sha256"],
                               "train":{m:summarize([r[m] for r in fit.rows])
                                        for m in POLICIES},
                               "source_validation":validation,
                               "evaluation":families})
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","reserved"),default="development")
    args=parser.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="development" else RESERVED),
                     sort_keys=True,indent=2))


if __name__=="__main__":
    main()
