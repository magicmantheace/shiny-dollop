"""Pre-frozen cross-generator event segmentation and retention study (D3).

The generator holds ground truth only for EVALUATION SCORING. Learner.fit and
EventSpanMemory see bounded public raw tokens and never a target or boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter

from developmental_ai.event_segmentation import (
    EventSegmentationModel, EventSpanMemory, fit_event_model, INIT_P, INIT_Q
)

SCHEMA="developmental-ai.event-segmentation-benchmark/v1"
DEVELOPMENT=(14003,14009,14033)
ADDITIONAL=(27007,27011,27017)
FIT=160
TEST=64
START=92000
FAMILIES={"source_bursts":{"segments":5,"min":3,"max":11,"accuracy":.76},
          "shifted_bursts":{"segments":6,"min":2,"max":17,"accuracy":.62}}
METHODS=("learned_hmm","fixed_hmm","raw_longest_run","global_majority","first","last","oracle_segments")


def episode(seed,family,split,index):
    if (type(seed) is not int or family not in FAMILIES or split not in ("train","test") or
            type(index) is not int or not 0 <= index < 1000000):
        raise ValueError("invalid episode configuration")
    r=FAMILIES[family]
    raw=f"{SCHEMA}/{seed}/{family}/{split}/{index}".encode()
    rng=random.Random(int.from_bytes(hashlib.sha256(raw).digest()[:8],"big"))
    for _ in range(1000):
        durations=[rng.randint(r["min"],r["max"]) for _ in range(r["segments"])]
        top=sorted(durations,reverse=True)
        if top[0]-top[1]>=2:break
    else:raise RuntimeError("no uniquely long source event")
    labels=[rng.randrange(4)]
    for _ in durations[1:]:
        labels.append(rng.choice([x for x in range(4) if x!=labels[-1]]))
    hidden=[];targets=[]
    for label,duration in zip(labels,durations):
        hidden.extend([label]*duration)
        targets.append({"label":label,"duration":duration})
    observations=[token if rng.random()<r["accuracy"] else rng.choice([x for x in range(4) if x!=token])
                  for token in hidden]
    if len(observations)>128:raise RuntimeError("stream length exceeds memory budget")
    return {"observed":observations,"target":labels[durations.index(max(durations))],
            "hidden":hidden,"true_spans":targets}


def longest_raw_run(tokens):
    start=0;best=None
    for i in range(1,len(tokens)+1):
        if i==len(tokens) or tokens[i]!=tokens[i-1]:
            item=(i-start,-start,-tokens[start],tokens[start])
            if best is None or item[:3]>best[:3]:best=item
            start=i
    return best[3]


def majority(tokens):
    c=Counter(tokens)
    return min(t for t,n in c.items() if n==max(c.values()))


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,ADDITIONAL):
        raise ValueError("cohort not in frozen protocol")
    out={"schema":SCHEMA,"protocol":"benchmarks/event_segmentation_protocol.json",
         "independent_blind":False,"train":"source_bursts/train/0..159",
         "test":"test/92000..92063","episodes_per_seed_and_family":TEST,"rows":[]}
    for seed in seeds:
        streams=[episode(seed,"source_bursts","train",i)["observed"] for i in range(FIT)]
        learned=EventSegmentationModel.restore(fit_event_model(streams).record())
        fixed=EventSegmentationModel(streams,INIT_P,INIT_Q)
        record={"seed":seed,"fitted_p":round(learned.persistence,6),"fitted_q":round(learned.sensor_accuracy,6),
                "learned_model_sha256":learned.record()["sha256"],"families":{}}
        for family in FAMILIES:
            success={method:0 for method in METHODS}
            total_frames=0;correct_frames=0;exact_boundaries=0;true_boundaries=0
            predicted_segments=0;true_segments=0
            for i in range(TEST):
                trial=episode(seed,family,"test",START+i)
                tokens=trial["observed"]; target=trial["target"]
                predictions={"learned_hmm":learned.recall(tokens),
                             "fixed_hmm":fixed.recall(tokens),
                             "raw_longest_run":longest_raw_run(tokens),
                             "global_majority":majority(tokens),
                             "first":tokens[0],"last":tokens[-1],
                             "oracle_segments":target}
                for method,guess in predictions.items():success[method]+=int(guess==target)
                path=learned.decode(tokens)
                total_frames+=len(tokens)
                correct_frames+=sum(a==b for a,b in zip(path,trial["hidden"]))
                boundaries={j for j in range(1,len(path)) if path[j]!=path[j-1]}
                actual={j for j in range(1,len(trial["hidden"])) if trial["hidden"][j]!=trial["hidden"][j-1]}
                exact_boundaries+=len(boundaries & actual)
                true_boundaries+=len(actual)
                predicted_segments+=1+len(boundaries)
                true_segments+=1+len(actual)
            record["families"][family]={"successes":success,
                 "framewise_latent_accuracy":round(correct_frames/total_frames,5),
                 "exact_boundary_recall":round(exact_boundaries/true_boundaries,5),
                 "mean_predicted_segments":round(predicted_segments/TEST,4),
                 "mean_true_segments":round(true_segments/TEST,4)}
        out["rows"].append(record)
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cohort",choices=("development","additional"),default="development")
    ap.add_argument("--out")
    args=ap.parse_args()
    data=json.dumps(measure(DEVELOPMENT if args.cohort=="development" else ADDITIONAL),sort_keys=True,indent=2)+"\n"
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(data,encoding="utf-8")
    print(data,end="")

if __name__=="__main__":main()
