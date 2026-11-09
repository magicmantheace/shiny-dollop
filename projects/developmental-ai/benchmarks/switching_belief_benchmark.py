"""Frozen within-episode regime-shift experiment; test split never tunes hazard.

Fit models on mixed, unlabelled stationary train episodes. Pick a switching
hazard using train-only *unlabelled* sequences in which a separate simulator
schedule changes physical dynamics at steps 12 and 24. Evaluation reveals
regime/position only to the harness for diagnostics, never to either filter.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.adaptive_dynamics import CalibrationWorld
from developmental_ai.mixed_experience import fit_mixed
from developmental_ai.switching_belief import SwitchingBelief, SCHEMA, calibrate_hazard, verified_hazard
from developmental_ai.online_dynamics import trajectory
from developmental_ai.uncertain_navigation import seed_for

REGIMES = (("standard", "fixed"), ("high", "shifted"))
HAZARDS = (0., .01, .04, .10, .20)


def mixed_histories(seed, count, beginning):
    return [trajectory(seed, "train", beginning + i, *REGIMES[i % 2]) for i in range(count)]


def stream(seed, split, index, *, change=True):
    """Sensor-only alternating schedule; hidden truth returned for HARNESS use."""
    if split not in ("train", "test") or type(index) is not int or index < 0:
        raise ValueError("invalid observation partition")
    world = CalibrationWorld(seed, split, index, *REGIMES[0])
    rng = random.Random(seed_for(seed,split,index,"policy"))
    observations=[]
    for step in range(36):
        identity = int(change and 12 <= step < 24)
        world.noise, world.layout = REGIMES[identity]
        action = rng.randrange(2)
        sensed, _, _, _ = world.step(action)
        observations.append((action, sensed, identity, world.pos))
    return (world.initial, world.goal, world.n), observations


def evaluate_stream(models, seed, split, index, hazard, *, change):
    beacon, events = stream(seed,split,index,change=change)
    nav=SwitchingBelief(*beacon,models,hazard=hazard)
    nll=0.; brier=0.; abstained=0; phases=[{"abstain":0,"brier":0.} for _ in range(3)]
    for i,(action,ob,regime,true_position) in enumerate(events):
        nll-=nav.advance(action,ob)
        brier_i=sum((p-int(j==true_position))**2 for j,p in enumerate(nav.probs))
        predicted=nav.selected(threshold=.8)
        # Inferred hypothesis names are arbitrary; do not score as labels.
        phase=phases[i//12]
        phase["abstain"]+=int(predicted is None)
        phase["brier"]+=brier_i
        brier+=brier_i
        abstained+=int(predicted is None)
    return {"nll":nll/len(events),"brier":brier/len(events),
            "abstention":abstained/len(events),
            "phase_brier":[p["brier"]/12 for p in phases],
            "phase_abstention":[p["abstain"]/12 for p in phases]}


def run(seeds=(17,23,41),*,train=48,validation=16,calibration=12,test=30,iterations=2,rounds=1):
    if (type(seeds) not in (tuple,list) or not seeds or len(set(seeds))!=len(seeds) or
            any(type(s) is not int for s in seeds) or
            any(type(n) is not int or n<1 for n in (train,validation,calibration,test,iterations,rounds)) or
            train%2 or validation%2 or train < 20 or validation < 10 or train>300 or test>200 or calibration>100):
        raise ValueError("invalid benchmark configuration")
    output={"schema":SCHEMA,"seeds":list(seeds),"kind":"inspected-development-not-blind",
            "train":train,"validation":validation,"calibration":calibration,"test":test,
            "iterations":iterations,"rounds":rounds,"hazard_candidates":HAZARDS,
            "partitions":{"fit":"train/0+","discovery_validation":"train/10000+",
                          "hazard_selection":"train/40000+","switch_test":"test/85000+",
                          "stationary_test":"test/86000+"},
            "notes":"Known 9/11 ring and hardcoded two-landmark spacing; simulator changes noise/layout at steps 12 and 24, without sending transition/regime labels to filters. Fitting and hazard selection use separate train samples. Benchmark uses hidden position only for Brier. No blind seed, no new model trained during stream, no automatic rollout.","rows":[]}
    for seed in seeds:
        proposal=fit_mixed(mixed_histories(seed,train,0),mixed_histories(seed,validation,10000),
                           seed=seed,iterations=iterations,rounds=rounds)
        models={"h%d"%i:model for i,model in enumerate(proposal.models)}
        # Only ordinary sensor records enter hazard selection. Hidden positions
        # and condition labels are discarded before the calibration function.
        sensor_records=[]
        for i in range(calibration):
            beacon, events=stream(seed,"train",40000+i,change=True)
            sensor_records.append({"initial":beacon[0],"goal":beacon[1],"n":beacon[2],
                                   "observations":[[a,o] for a,o,*_ in events]})
        receipt=calibrate_hazard(models,sensor_records,candidates=HAZARDS)
        selected=verified_hazard(receipt,models)
        comparisons=[{"hazard":float(h),"mean_nll":receipt["state"]["scores"][str(h)]} for h in HAZARDS]
        by_schedule={}
        for label,change,offset in (("switching",True,85000),("stationary",False,86000)):
            per_method={}
            for h,name in ((0.,"stationary_mixture"),(selected,"selected_switching")):
                values=[evaluate_stream(models,seed,"test",offset+i,h,change=change) for i in range(test)]
                per_method[name]={key:round(sum(v[key] for v in values)/test,6) for key in ("nll","brier","abstention")}
                for key in ("phase_brier","phase_abstention"):
                    per_method[name][key]=[round(sum(v[key][j] for v in values)/test,6) for j in range(3)]
            by_schedule[label]=per_method
        output["rows"].append({"seed":seed,"proposal_two_models":proposal.accepted,
                               "proposal_validation":proposal.validation,
                               "hazard_calibration":[{"hazard":r["hazard"],"mean_nll":round(r["mean_nll"],6)} for r in comparisons],
                               "selected_hazard":selected,"calibration_receipt_digest":receipt["sha256"],"evaluation":by_schedule})
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41]);p.add_argument("--train",type=int,default=48)
    p.add_argument("--validation",type=int,default=16);p.add_argument("--calibration",type=int,default=12)
    p.add_argument("--test",type=int,default=30);p.add_argument("--iterations",type=int,default=2)
    p.add_argument("--rounds",type=int,default=1);p.add_argument("--out")
    a=p.parse_args();result=run(a.seeds,train=a.train,validation=a.validation,calibration=a.calibration,
                                test=a.test,iterations=a.iterations,rounds=a.rounds)
    s=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(s,encoding="utf-8")
    print(s,end="")

if __name__=="__main__":main()
