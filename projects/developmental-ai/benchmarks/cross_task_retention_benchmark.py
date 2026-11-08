"""Cross-family retention transfer: delayed task feedback -> occluded navigation.

A learner chooses between two engineered retention hypotheses and learns a
response mapping. Only the retention choice transfers to the spatial task;
the spatial representation, motion updater and navigation heuristic remain
engineered or separately learned. Development seeds have been inspected.
"""
import argparse
import json
import random

from developmental_ai.cross_task_retention import fit_gate, delayed_success
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import PortableOffsetMemory, train_grid_updates
from developmental_ai.occluded_navigation import greedy_action

SCHEMA="developmental-ai.cross-task-retention-benchmark/v1"


def navigate(seed, index, updater, *, retain):
    session=EnvironmentSession("occluded",seed,"test",index)
    mem=PortableOffsetMemory(updater,retain=retain)
    rng=random.Random(seed*100000+index)
    last=None
    while not session.done:
        frame=session.frame()
        features=mem.features(frame)
        action=greedy_action(features,rng)
        result=session.step(action,expected_tick=frame["tick"])
        mem.feedback(action,result)
        last=result["event"]
    return last=="collected"


def measure(*,seeds=(2749,6607,9901),train=400,validation=120,episodes=40,updater_episodes=24):
    if (type(seeds) not in (tuple,list) or not seeds or any(type(s) is not int for s in seeds) or
            len(seeds)!=len(set(seeds)) or type(episodes) is not int or not 1<=episodes<=100 or
            type(updater_episodes) is not int or not 1<=updater_episodes<=200):
        raise ValueError("invalid benchmark configuration")
    results={"schema":SCHEMA,"blind":False,"seeds":list(seeds),"train_episodes":train,
             "validation_episodes":validation,"test_episodes_per_family_seed":episodes,
             "train_indices":"train/0..N-1","validation_indices":"train/5000+",
             "test_indices":{"delayed":"test/85000+","occluded":"test/86000+"},"rows":[]}
    for seed in seeds:
        gate=fit_gate(seed,episodes=train,validation=validation)
        updater=train_grid_updates(seed,updater_episodes)
        row={"seed":seed,"selected":gate.strategy,"validation":gate.scores,
             "gate_digest":gate.record()["digest"],
             "delayed_long":{strategy:sum(delayed_success(gate,85000+i,strategy=strategy) for i in range(episodes))
                             for strategy in ("initial","latest")},
             "occluded":{strategy:sum(navigate(seed,86000+i,updater,retain=(strategy=="initial")) for i in range(episodes))
                          for strategy in ("initial","latest")}}
        row["delayed_long"]["learned"]=row["delayed_long"][gate.strategy]
        row["occluded"]["learned"]=row["occluded"][gate.strategy]
        results["rows"].append(row)
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds",type=int,nargs="+",default=[2749,6607,9901])
    parser.add_argument("--train",type=int,default=400)
    parser.add_argument("--validation",type=int,default=120)
    parser.add_argument("--episodes",type=int,default=40)
    parser.add_argument("--out")
    opts=parser.parse_args()
    result=json.dumps(measure(seeds=opts.seeds,train=opts.train,validation=opts.validation,episodes=opts.episodes),indent=2,sort_keys=True)+"\n"
    if opts.out:
        from pathlib import Path
        Path(opts.out).write_text(result)
    print(result,end="")

if __name__=="__main__":main()
