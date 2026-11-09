"""Compare frozen decisions, conservative abstention and streak selection.

All calibration is from train indices 5000+, distinct from model fitting and
from test 6000+. Results are inspected research, NOT a confidence guarantee.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from benchmarks.abstention_benchmark import REGIMES, stream
from developmental_ai.decision_abstention import decide, train_gate, verify_gate
from developmental_ai.online_dynamics import ModelBank, fit, trajectory
from developmental_ai.step_dynamics import StepDetector
from developmental_ai.streak_selection import SCHEMA, StreakSelector, train_profile, verify_profile


def score_predictions(trials, predictions):
    counts={"correct":0,"wrong":0,"abstain":0}
    for (truth,_),pred in zip(trials,predictions):
        counts["abstain" if pred is None else "correct" if pred==truth else "wrong"]+=1
    assert sum(counts.values())==len(trials)
    return counts


def measure(seeds=(17,23,41), *, train_episodes=130, iterations=6,
            calibration_episodes=40, phase_episodes=12, max_empirical_error=.02):
    if (not seeds or len(set(seeds))!=len(seeds) or any(type(s) is not int for s in seeds)
            or any(type(v) is not int or v<=0 for v in
                   (train_episodes, iterations, calibration_episodes, phase_episodes))
            or train_episodes>1000 or iterations>50 or not 9<=calibration_episodes<=100
            or not 3<=phase_episodes<=100):
        raise ValueError("invalid benchmark arguments")
    rows=[]
    with tempfile.TemporaryDirectory(prefix="devai-streak-") as folder:
        for seed in seeds:
            root=Path(folder)
            with ModelBank(root/f"bank-{seed}.db",seed) as bank:
                for name, condition in REGIMES.items():
                    data=[trajectory(seed,"train",i,*condition) for i in range(train_episodes)]
                    model,_=fit(data,iterations=iterations)
                    bank.save(name,model,len(data))
                with StepDetector(root/f"cal-{seed}.db",bank,margin=.12) as d:
                    calibration=[(event,truth) for truth,event in
                                 stream(d,seed,split="train",index_base=5000,count=calibration_episodes)]
                strict=train_gate(bank,calibration,max_empirical_error=.10)
                profile=train_profile(bank,calibration,min_streak=3,
                                      max_empirical_error=max_empirical_error)
                verify_profile(bank,profile)
                with StepDetector(root/f"eval-{seed}.db",bank,margin=.12) as d:
                    test=[(truth,event) for truth,event in
                          stream(d,seed,split="test",index_base=6000,count=phase_episodes)]
                    d.events()
                selector=StreakSelector(bank,profile)
                preds=[selector.observe(ev) for truth,ev in test]
                # Replay without knowing environment labels.
                replay=StreakSelector(bank,profile)
                assert preds==[replay.observe(ev) for _,ev in test]
                rows.append({"seed":seed,"profile":profile.as_dict(),
                             "results":{
                              "frozen":score_predictions(test,[e["active"] if e["status"]!="unknown" else None for _,e in test]),
                              "conservative":score_predictions(test,[decide(e,REGIMES,gap=verify_gate(bank,strict)) for _,e in test]),
                              "streak":score_predictions(test,preds)}})
    return {"schema":SCHEMA,"kind":"inspected-development-not-blind",
            "seeds":list(seeds),"train_episodes_per_model":train_episodes,
            "iterations":iterations,"calibration_episodes_per_phase":calibration_episodes,
            "evaluation_episodes_per_phase":phase_episodes,
            "streak_length":3,"max_empirical_error":max_empirical_error,
            "data_separation":{"fit":"train 0..N-1","calibration":"train 5000+",
                               "test":"test 6000+"},
            "note":"Streak is an optional experimental policy. Strict remains default. Empirical risk calibration is not a statistical coverage or safety guarantee. All seeds inspected.",
            "rows":rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds",nargs="+",type=int,default=[17,23,41])
    parser.add_argument("--train-episodes",type=int,default=130)
    parser.add_argument("--iterations",type=int,default=6)
    parser.add_argument("--calibration-episodes",type=int,default=40)
    parser.add_argument("--phase-episodes",type=int,default=12)
    parser.add_argument("--max-empirical-error",type=float,default=.02)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    result=measure(args.seeds,train_episodes=args.train_episodes,iterations=args.iterations,
                   calibration_episodes=args.calibration_episodes,phase_episodes=args.phase_episodes,
                   max_empirical_error=args.max_empirical_error)
    output=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if args.out:args.out.write_text(output,encoding="utf-8")
    print(output,end="")

if __name__=="__main__":main()
