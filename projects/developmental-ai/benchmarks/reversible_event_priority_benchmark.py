"""Precommitted goal-reversal event memory study; private truth stays in scorer.

Three train-only feedback phases: original, unannounced reversal, return.
Held-out test namespace is read-only at every checkpoint; learned models do
not receive the goal preference, reward phase or hidden event labels.
"""
from __future__ import annotations

import argparse
import json

from benchmarks.event_segmentation_benchmark import episode, DEVELOPMENT, ADDITIONAL
from benchmarks.outcome_event_memory_benchmark import preference,context,score
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.reversible_event_priority import ReversibleEventPriority

SCHEMA="developmental-ai.reversible-event-priority-benchmark/v1"
PHASES=(("original",2000,200),("reversal",2300,96),("return",2500,96))
EVAL_START=(95000,95100,95200)
EVAL=48
MODES=("bank","cumulative","window","frozen")


def phase_goals(base, name):
    if name not in ("original","reversal","return"):
        raise ValueError("invalid benchmark phase")
    return {c:(label+1)%4 if name=="reversal" else label for c,label in base.items()}


def selected_success(choice, trial, target):
    return score(choice,trial,target)


def measure(seeds=DEVELOPMENT):
    if (type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,ADDITIONAL)):
        raise ValueError("unapproved cohort or evaluation schedule")
    out={"schema":SCHEMA,"protocol":"benchmarks/reversible_event_memory_protocol.json",
         "blind":False,"evaluation_feedback_updates_model":False,
         "fit":"source_bursts/train/0..159","phases":[],"rows":[]}
    for name,start,n in PHASES:
        out["phases"].append({"name":name,"train_indices":[start,start+n-1],
                               "eval_family":"shifted_bursts","eval_episodes":EVAL,
                               "eval_start":EVAL_START[len(out["phases"])]})
    for seed in seeds:
        training=[episode(seed,"source_bursts","train",i)["observed"] for i in range(160)]
        segmenter=fit_event_model(training)
        memories={mode:ReversibleEventPriority(segmenter,seed=seed,mode=mode) for mode in MODES}
        goal_map=preference(seed)
        result={"seed":seed,"segmenter_sha256":segmenter.record()["sha256"],"phases":{}}
        for p,(name,start,steps) in enumerate(PHASES):
            goals=phase_goals(goal_map,name)
            training_reward={mode:0 for mode in MODES}; online_early={mode:0 for mode in MODES}; online_late={mode:0 for mode in MODES}
            for j in range(steps):
                ix=start+j
                trial=episode(seed,"source_bursts","train",ix)
                ctx=context(seed,"train",ix)
                for mode,learner in memories.items():
                    if mode=="frozen" and p>0:continue
                    selection=learner.propose(ctx,trial["observed"],split="train",index=ix)
                    win=selected_success(selection,trial,goals[ctx])
                    learner.feedback(win,split="train",index=ix)
                    training_reward[mode]+=win
                    if j<20:online_early[mode]+=win
                    if j>=steps-20:online_late[mode]+=win
            # Model recovery is checked at each phase boundary, so outcomes
            # shown for the next phase are from fully validated checkpoints.
            memories={mode:ReversibleEventPriority.restore(model.record(),segmenter)
                      for mode,model in memories.items()}
            success={mode:0 for mode in MODES};success.update({"hmm_longest":0,"oracle_available":0})
            seen_at_test={mode:0 for mode in MODES}
            for j in range(EVAL):
                ix=EVAL_START[p]+j
                trial=episode(seed,"shifted_bursts","test",ix)
                ctx=context(seed,"test",ix)
                for mode,learner in memories.items():
                    selected=learner.choose(ctx,trial["observed"])
                    success[mode]+=selected_success(selected,trial,goals[ctx])
                    seen_at_test[mode]+=1
                spans=segmenter.spans(trial["observed"])
                longest=max(spans,key=lambda z:(z["end"]-z["start"],-z["start"],-z["label"]))
                center=(longest["start"]+longest["end"]-1)//2
                success["hmm_longest"]+=int(trial["hidden"][center]==goals[ctx])
                success["oracle_available"]+=int(goals[ctx] in trial["hidden"])
            result["phases"][name]={"successes":success,"train_feedback_successes":training_reward,
                      "train_first20":online_early,"train_last20":online_late,
                      "banks":{ctx:len(memories["bank"].banks[ctx]) for ctx in (0,1)},
                      "active_bank":dict(memories["bank"].active),
                      "switch_count":len(memories["bank"].switches),
                      "checkpoint_sha256":memories["bank"].record()["sha256"]}
        out["rows"].append(result)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    p.add_argument("--out")
    args=p.parse_args()
    data=json.dumps(measure(DEVELOPMENT if args.cohort=="development" else ADDITIONAL),sort_keys=True,indent=2)+"\n"
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(data,encoding="utf-8")
    print(data,end="")

if __name__=="__main__":main()
