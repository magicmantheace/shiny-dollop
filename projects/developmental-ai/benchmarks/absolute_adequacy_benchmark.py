"""Noisy known worlds and untrained third outcome law: adequacy gate audit.

Frozen before candidate implementation. Engineered numerical action
features, but no world label in candidate observations. Calibration is
disposable and harmful attempts are recorded. 60 TEST tasks per seed/world.
"""
from __future__ import annotations

import argparse
import json

from developmental_ai.observable_affordances import outcome
from developmental_ai.absolute_adequacy import AbsoluteAdequacy,METHODS as GATES
from developmental_ai.novel_feature_world import NovelFeatureWorld,CONDITIONS
from benchmarks.observable_affordance_benchmark import fit,summary
from benchmarks.observable_reversal_calibration_benchmark import fit_reversed

SCHEMA="developmental-ai.absolute-adequacy-evaluation/v1"
DEV=(93001,93013,93031)
RESERVED=(94011,94023,94029)
METHODS=("adequacy8","relative8","recent8",
         "source_only","changed_only","always_abstain","oracle")
TRAIN_START=2000
CALIBRATION_N=8
TEST_START=22000
TEST_N=60


def calibrate(seed,condition,src,changed):
    agent=AbsoluteAdequacy(src,changed)
    harm=0
    for i in range(CALIBRATION_N):
        world=NovelFeatureWorld(seed,"train",TRAIN_START+i,condition)
        before=world.frame()
        action=agent.probe(before)
        after=world.step(action,before["tick"])
        e=agent.observe(before,action,after)
        harm+=int(e["damage"])
    checkpoint=agent.record("adequacy8")
    if AbsoluteAdequacy.restore(src,changed,checkpoint).record("adequacy8")!=checkpoint:
        raise AssertionError("uncertainty checkpoint changed on replay")
    return agent,{"probes":CALIBRATION_N,"calibration_damage":harm,
                  "receipt_sha256":checkpoint["sha256"]}


def episode(seed,condition,index,selection,src,changed):
    world=NovelFeatureWorld(seed,"test",index,condition)
    model=src if selection=="source" else changed if selection=="changed" else None
    if selection in ("unknown","abstain"):
        return {"success":0,"hurt":0,"stalled":1,"attempts":0}
    harm=0
    for _ in range(world.frame()["budget"]):
        frame=world.frame()
        if frame["done"]:
            break
        if selection=="oracle":
            # Oracle is *privileged* about the world rule and the
            # hidden simulated consequence of each action.
            suitable=[row["id"] for row in frame["actions"]
                      if world._effect(row["id"])=="progress"]
            action=suitable[0] if suitable else None
        else:
            action=model.choose(frame)
        if action is None:
            break
        after=world.step(action,frame["tick"])
        e=outcome(frame,action,after)
        harm+=int(e["damage"])
    return {"success":int(world.success()),"hurt":harm,
            "stalled":int(not world.success()),"attempts":world.tick}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError("only frozen development or reserved seed lists")
    out={"schema":SCHEMA,"blind":False,"third_training_episodes":0,
         "noise":"10 percent of known-rule events become neutral",
         "train_calibration":[TRAIN_START,TRAIN_START+CALIBRATION_N-1],
         "test_indices":[TEST_START,TEST_START+TEST_N-1],"rows":[]}
    for seed in seeds:
        src,_=fit(seed)
        changed,_=fit_reversed(seed)
        frozen=(src.record(),changed.record())
        worlds={}
        for condition in CONDITIONS:
            agent,calibration=calibrate(seed,condition,src,changed)
            scores={}
            for method in METHODS:
                decision=(agent.decision(method) if method in GATES else
                          {"selected":"source" if method=="source_only" else
                           "changed" if method=="changed_only" else
                           "abstain" if method=="always_abstain" else "oracle",
                           "first":None,"recent":None,"conflict":False})
                choice=decision["selected"]
                rows=[episode(seed,condition,TEST_START+i,choice,src,changed)
                      for i in range(TEST_N)]
                scores[method]={"decision":decision,
                                "evaluation":summary(rows)}
            worlds[condition]={"calibration":calibration,"policies":scores}
        if frozen!=(src.record(),changed.record()):
            raise AssertionError("test observations mutated trained models")
        out["rows"].append({"seed":seed,"scores":worlds,
                           "source_sha256":frozen[0]["sha256"],
                           "changed_sha256":frozen[1]["sha256"]})
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cohort",choices=("development","reserved"),
                        default="development")
    args=parser.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="development" else RESERVED),
                     indent=2,sort_keys=True))


if __name__=="__main__":
    main()
