"""Post-hoc unknown descriptor regime C, plus stronger union-risk baseline.

The *previous* A/B cue-free and perfect-cue studies remain unchanged.
C has no supervised histories. All seeds and A/B outcomes were already
inspected, so no claim of blind evaluation or causal safety is warranted.
"""
from __future__ import annotations

import argparse
import json
from developmental_ai.affordance_memory import FilteredNovel, RiskMemory, token
from developmental_ai.contextual_affordance import CUES, ContextMemory
from developmental_ai.no_cue_diagnostic import NoCueProbe
from developmental_ai.unseen_regime import ConservativeUnionRisk, UnseenDescriptorCargo
from benchmarks.contextual_affordance_benchmark import DEVELOPMENT, RESERVED, fit

SCHEMA="developmental-ai.unseen-regime-stress/v1"
START=9000
EPISODES=60
VARIANTS=("A","B","C")
METHODS=("no_cue","union","frozen_A","frozen_B","novel","privileged_oracle")


class PrivilegedRisk(RiskMemory):
    """Benchmark-only: reference uses true simulator mapping."""
    def __init__(self,code):
        super().__init__()
        self.code=code
    def avoid(self):
        return {self.code}


def run(seed,split,index,variant,method,histories):
    if variant not in VARIANTS or method not in METHODS:
        raise ValueError("invalid frozen stress scenario")
    if not isinstance(histories,ContextMemory):
        raise ValueError("two known source memories required")
    world=UnseenDescriptorCargo(seed,split,index,variant)
    learner=NoCueProbe(histories) if method=="no_cue" else None
    if method=="union":
        controller=FilteredNovel(ConservativeUnionRisk(histories))
    elif method=="frozen_A":
        controller=FilteredNovel(histories.choose_memory(CUES["A"]))
    elif method=="frozen_B":
        controller=FilteredNovel(histories.choose_memory(CUES["B"]))
    elif method=="novel":
        controller=FilteredNovel()
    elif method=="privileged_oracle":
        # Never passed to no_cue or union policy; simulation-only reference.
        controller=FilteredNovel(PrivilegedRisk(
            token(world.world.world._features["spoil"])))
    else:
        controller=None
    blocked=spoil=0
    for _ in range(18):
        frame=world.frame()
        if frame["base"]["done"]:
            break
        action=learner.choose(frame) if learner else controller.choose(frame)
        if action is None:
            break
        # Hidden label used exclusively by metrics, NOT any policy choice.
        private_name=world.world.world.base._lookup[action]
        result=world.execute(action,frame["base"]["tick"])
        if learner:
            learner.feedback(frame,action,result["accepted"],result["public"])
        else:
            controller.feedback(frame,action,result["accepted"],result["public"])
        blocked+=int(not result["accepted"])
        spoil+=int(private_name=="spoil" and result["accepted"])
    return {"success":int(world.success()),
            "spoilage":spoil, "attempts":world.world.world.base.tick,
            "blocked":blocked,"stalled":int(not world.world.world.base.done),
            "probe":int(learner is not None and learner._probe_action is not None)}


def summarise(rows):
    return {"successes":sum(x["success"] for x in rows),
            "episodes":len(rows),
            "spoilage":sum(x["spoilage"] for x in rows),
            "mean_attempts":round(sum(x["attempts"] for x in rows)/len(rows),3),
            "mean_blocked":round(sum(x["blocked"] for x in rows)/len(rows),3),
            "stalled":sum(x["stalled"] for x in rows),
            "probed":sum(x["probe"] for x in rows)}


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,RESERVED):
        raise ValueError("six inspected seeds frozen for stress audit")
    result={"schema":SCHEMA,"blind":False,"C_training_episodes":0,
            "engineered_stable_identity":True,
            "A_and_B_histories_train_episodes_each":80,
            "C_change":"spoil/fuel descriptor swap only",
            "test_indices":[START,START+EPISODES-1],"rows":[]}
    for seed in seeds:
        a,_=fit(seed,"A");b,_=fit(seed,"B")
        histories=ContextMemory([[CUES["A"],a],[CUES["B"],b]])
        saved=histories.record()
        scores={}
        for variant in VARIANTS:
            scores[variant]={}
            for method in METHODS:
                observed=[run(seed,"test",START+i,variant,method,histories)
                          for i in range(EPISODES)]
                scores[variant][method]=summarise(observed)
        if histories.record()!=saved:
            raise AssertionError("read-only evaluation changed source experience")
        result["rows"].append({"seed":seed,"sha256":saved["sha256"],
                               "known_union":sorted(ConservativeUnionRisk(histories).avoid()),
                               "scores":scores})
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","inspected-additional"),default="development")
    args=parser.parse_args()
    print(json.dumps(measure(DEVELOPMENT if args.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
