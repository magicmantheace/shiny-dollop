"""Novel sensor-fault rejection with a frozen model bank and train-only receipts.

Known stationary and mid-episode-shift cases quantify false alarms. Unfamiliar
sensor faults are **benchmark-injected**, not learned unknown physics. The
monitor consumes only start/goal + action/odometry/marker, no truth/reward.
All seeds have been previously inspected, not blind evaluation.
"""
from __future__ import annotations

import argparse
import json
import random

from benchmarks.switching_belief_benchmark import HAZARDS, mixed_histories, stream
from developmental_ai.adaptive_dynamics import CalibrationWorld
from developmental_ai.mixed_experience import fit_mixed
from developmental_ai.closed_loop_adaptation import NavigationSession, models_from_proposal
from developmental_ai.switching_belief import calibrate_hazard, verified_hazard
from developmental_ai.novelty_guard import NoveltyGuard, GuardedNavigation, calibrate_guard, SCHEMA
from developmental_ai.uncertain_navigation import seed_for

CONDITIONS=("normal", "known-shift", "landmark-fault", "odometry-fault", "rotated-map")


def readings(seed, split, index, kind):
    if kind not in CONDITIONS or type(seed) is not int or split not in ("train","test") or type(index) is not int or index < 0:
        raise ValueError("invalid benchmark sensor stream")
    if kind == "rotated-map":
        world=CalibrationWorld(seed,split,index,"standard","fixed")
        def shifted():
            offset=3
            m=0 if world.pos == offset else 1 if world.pos == world.n//2+offset else None
            p=world.rng.random()
            return 0 if m is None and p < .01 else 1 if m is None and p < .02 else None if m is None else m if p < .85 else 1-m if p < .86 else None
        world._landmark=shifted
        rng=random.Random(seed_for(seed,split,index,"policy"))
        pairs=[]
        for _ in range(36):
            a=rng.randrange(2)
            ob,_,_,_=world.step(a)
            pairs.append([a,ob])
        return {"initial":world.initial,"goal":world.goal,"n":world.n,"observations":pairs}
    beacon, events=stream(seed,split,index,change=(kind=="known-shift"))
    pairs=[]
    for action,obs,*_ in events:
        obs=dict(obs)
        if kind=="landmark-fault":obs["landmark"]=0  # stuck indicator, valid sensor vocabulary
        if kind=="odometry-fault":obs["odometry"]=0  # stuck encoder, valid sensor vocabulary
        pairs.append([action,obs])
    return {"initial":beacon[0],"goal":beacon[1],"n":beacon[2],"observations":pairs}


def run(seeds=(17,23,41), *, train=48, validation=16, hazard_calibration=12,
        reference=64, episodes=24, iterations=2, rounds=1, alpha=.10):
    if (type(seeds) not in (tuple,list) or not seeds or len(set(seeds)) != len(seeds) or
            any(type(seed) is not int for seed in seeds) or
            any(type(n) is not int for n in (train,validation,hazard_calibration,reference,episodes,iterations,rounds)) or
            train < 20 or train>300 or train%2 or validation < 10 or validation>250 or validation%2 or
            not 2<=hazard_calibration<=100 or not 40<=reference<=200 or reference%2 or
            not 1<=episodes<=150 or not 1<=iterations<=10 or not 1<=rounds<=4):
        raise ValueError("invalid benchmark budget")
    data={"schema":SCHEMA,"kind":"previously-inspected-not-blind", "seeds":list(seeds),
          "budgets":{"fit":train,"validation":validation,"hazard":hazard_calibration,
                     "reference":reference,"evaluation_per_condition":episodes,"iterations":iterations,
                     "rounds":rounds,"alpha":alpha},
          "partitions":{"model_fit":"train/0+","validation":"train/10000+",
                        "hazard":"train/40000+","novelty_reference":"train/50000+",
                        "evaluation":"test/93000+"},
          "notes":"The same action policy is used to collect all 36-step streams. Faults artificially override a valid sensor channel. Rotated two-mark layout is still within the known small-ring family. Training uses ordinary trajectories, but the harness constructs their regimes. Alarm is observational only and does not change navigation or grant any permission. Known-schedule calibration mix is not identical to every test condition; no distribution-free false alarm guarantee. Original seeds inspected repeatedly.",
          "rows":[]}
    for seed in seeds:
        proposal=fit_mixed(mixed_histories(seed,train,0),mixed_histories(seed,validation,10000),
                           seed=seed,iterations=iterations,rounds=rounds)
        models=models_from_proposal(proposal)
        hazard_streams=[readings(seed,"train",40000+i,"known-shift") for i in range(hazard_calibration)]
        hazard_receipt=calibrate_hazard(models,hazard_streams,candidates=HAZARDS)
        hazard=verified_hazard(hazard_receipt,models)
        references=[readings(seed,"train",50000+i,"normal" if i%2==0 else "known-shift")
                    for i in range(reference)]
        receipt=calibrate_guard(models,references,hazard=hazard,alpha=alpha)
        conditions={}
        for kind in CONDITIONS:
            alarms=[]; first=[]; final_surprise=[]
            for i in range(episodes):
                r=readings(seed,"test",93000+i,kind)
                monitor=NoveltyGuard(r["initial"],r["goal"],r["n"],models,receipt)
                at=None
                for action,ob in r["observations"]:
                    result=monitor.advance(action,ob)
                    if result["alarm"] and at is None:at=result["steps"]
                alarms.append(at is not None)
                first.append(at)
                final_surprise.append(monitor.max_surprise)
            detected=[x for x in first if x is not None]
            conditions[kind]={"alarms":sum(alarms),"episodes":episodes,
                              "alarm_rate":round(sum(alarms)/episodes,6),
                              "first_alarm_mean_step":round(sum(detected)/len(detected),4) if detected else None,
                              "mean_max_prefix_surprise":round(sum(final_surprise)/episodes,6)}
        data["rows"].append({"seed":seed,"model_count":len(models),"discovery_accepted":proposal.accepted,
                             "switch_hazard":hazard,"threshold":round(receipt["state"]["threshold"],8),
                             "reference_sha256":receipt["state"]["calibration_digest"],
                             "conditions":conditions})
        # A second, honest operational check: the novelty warning is used to
        # PAUSE (never alter) the existing optional controller. Calibration
        # streams use a random action policy, so closed-loop false stops may
        # differ materially from the passive-probe false-alarm results.
        task={}
        for kind in ("normal", "landmark-fault"):
            outcomes={"baseline_success":0,"guard_success":0,"guard_paused":0,"guard_alarms":0}
            for i in range(episodes):
                for guarded in (False,True):
                    world=CalibrationWorld(seed,"test",97000+i,"standard","fixed")
                    session=(GuardedNavigation(proposal,hazard_receipt,receipt,world.initial,world.goal,world.n)
                             if guarded else NavigationSession(proposal,world.initial,world.goal,world.n,hazard_receipt,mode="switching"))
                    last=""
                    while not world.done:
                        action=session.select_action()
                        if action is None:
                            break  # a diagnostic pause never invents a replacement act
                        observation,_,done,last=world.step(action)
                        if kind=="landmark-fault":
                            observation["landmark"]=0
                        session.advance(action,observation,done=done)
                    if guarded:
                        outcomes["guard_success"]+=int(last=="success")
                        outcomes["guard_alarms"]+=int(session.guard.alarm)
                        outcomes["guard_paused"]+=int(session.guard.alarm and not world.done)
                    else:
                        outcomes["baseline_success"]+=int(last=="success")
            task[kind]={**outcomes,"episodes":episodes}
        data["rows"][-1]["closed_loop_pause_comparison"]=task
    return data


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41]);p.add_argument("--train",type=int,default=48)
    p.add_argument("--validation",type=int,default=16);p.add_argument("--hazard-calibration",type=int,default=12)
    p.add_argument("--reference",type=int,default=64);p.add_argument("--episodes",type=int,default=24)
    p.add_argument("--iterations",type=int,default=2);p.add_argument("--rounds",type=int,default=1)
    p.add_argument("--out")
    a=p.parse_args()
    result=run(a.seeds,train=a.train,validation=a.validation,hazard_calibration=a.hazard_calibration,
               reference=a.reference,episodes=a.episodes,iterations=a.iterations,rounds=a.rounds)
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(text,encoding="utf-8")
    print(text,end="")

if __name__=="__main__":main()
