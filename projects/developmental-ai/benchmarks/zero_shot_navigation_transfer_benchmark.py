"""Exploratory D3 zero-shot policy reuse; grid-trained Q never trains in occluded.

Development seeds already inspected by cross-family D1 test. This is NOT a
blind or preregistered independent D3 claim, and retains manual dead reckoning.
"""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
from developmental_ai.cross_family_transfer import SCHEMA,trial
from developmental_ai.transfer import TransferBrain

SEEDS=(2749,6607,9901)


def measure(*, seeds=SEEDS, train=1200, test=64):
    if (type(train) is not int or not 1 <= train <= 10000 or type(test) is not int or not 1 <= test <= 1000 or
            type(seeds) not in (tuple,list) or not seeds or any(type(s) is not int for s in seeds)):
        raise ValueError("invalid transfer benchmark configuration")
    result={"schema":SCHEMA,"train_family":"grid","zero_shot_family":"occluded",
        "train_episodes":train,"test_episodes_per_family":test,"train_split":"train",
        "test_split":"test","evaluation_start_index":70000,
        "blind":False,"notes":"Previously inspected development seeds. Grid Q policy is frozen and evaluated zero-shot on occluded. One-time beacon dead-reckoning is engineered, not learned. No hidden map access.","rows":[]}
    for seed in seeds:
        with tempfile.TemporaryDirectory() as d:
            brain=TransferBrain(Path(d)/"trained.db",seed=seed)
            try:
                brain.train(train)
                for family in ("grid","occluded"):
                    for policy in ("untrained","greedy","trained_grid"):
                        outcomes=[trial(brain,family=family,seed=seed,split="test",index=70000+i,policy=policy) for i in range(test)]
                        result["rows"].append({"seed":seed,"family":family,"policy":policy,"successes":sum(o["success"] for o in outcomes),
                            "success_rate":round(sum(o["success"] for o in outcomes)/test,5),
                            "mean_steps":round(sum(o["steps"] for o in outcomes)/test,5)})
            finally:brain.close()
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",type=int,nargs="+",default=list(SEEDS))
    p.add_argument("--train",type=int,default=1200)
    p.add_argument("--test",type=int,default=64)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    data=json.dumps(measure(seeds=a.seeds,train=a.train,test=a.test),sort_keys=True,indent=2)+"\n"
    if a.out:a.out.write_text(data,encoding="utf8")
    print(data,end="")

if __name__=="__main__":main()
