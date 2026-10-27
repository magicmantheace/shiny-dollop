"""Multi-seed development benchmark for uncertain movement and landmarks.

IMPORTANT: Seeds here are inspected development-set evidence, not blind tests.
"""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
from developmental_ai.uncertain_navigation import RingBrain, SCHEMA


def measure(seeds=(17,23,41), train_episodes=3000, test_episodes=200):
    output={"schema":SCHEMA,"kind":"inspected-development-benchmark",
            "train_episodes":train_episodes,"test_episodes":test_episodes,
            "seeds":list(seeds),"results":[]}
    with tempfile.TemporaryDirectory(prefix="devai-uncertainty-") as temp:
        for seed in seeds:
            row={"seed":seed}
            with RingBrain(Path(temp)/f"{seed}-belief.db",seed,"belief") as brain:
                row["before"]=brain.evaluate(test_episodes)
                brain.train(train_episodes)
                row["learned"]=brain.evaluate(test_episodes)
                row["heuristic"]=brain.evaluate(test_episodes,"heuristic")
                row["high_noise"]=brain.evaluate(test_episodes,noise="high")
                row["no_landmarks"]=brain.evaluate(test_episodes,landmarks=False)
                row["oracle"]=brain.evaluate(test_episodes,"oracle")
            with RingBrain(Path(temp)/f"{seed}-dead.db",seed,"dead") as brain:
                brain.train(train_episodes)
                row["dead_learned"]=brain.evaluate(test_episodes)
                row["dead_heuristic"]=brain.evaluate(test_episodes,"heuristic")
            with RingBrain(Path(temp)/f"{seed}-reactive.db",seed,"reactive") as brain:
                brain.train(train_episodes)
                row["reactive_learned"]=brain.evaluate(test_episodes)
            output["results"].append(row)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds",type=int,nargs="+",default=[17,23,41])
    parser.add_argument("--train-episodes",type=int,default=3000)
    parser.add_argument("--test-episodes",type=int,default=200)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    if args.train_episodes < 1 or args.test_episodes < 1 or len(set(args.seeds)) != len(args.seeds):
        parser.error("positive episodes and unique seeds required")
    results=measure(args.seeds,args.train_episodes,args.test_episodes)
    result=json.dumps(results,indent=2,sort_keys=True)+"\n"
    if args.out:args.out.write_text(result,encoding="utf-8")
    print(result,end="")


if __name__=="__main__":main()
