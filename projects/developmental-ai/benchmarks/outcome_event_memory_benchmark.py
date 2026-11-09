"""Frozen reward-only event-retrieval study; truth only in scoring adapter.

The task's private seed-dependent context preferences are not passed to the
learner. Both reward learners receive the same training EPISODES but each
receives outcomes for its own chosen span (equal interaction budgets).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter

from benchmarks.event_segmentation_benchmark import episode, DEVELOPMENT, ADDITIONAL
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.outcome_event_memory import OutcomeEventMemory, TRAIN_START

SCHEMA='developmental-ai.outcome-event-memory-benchmark/v1'
FIT = 160
REWARD_TRAIN = 200
TEST_START = 93000
TEST = 64


def preference(seed):
    """Simulator-only private reward mapping; never supplied to a learner."""
    seedbytes=hashlib.sha256(f'{SCHEMA}/{seed}/preference'.encode()).digest()
    rng=random.Random(int.from_bytes(seedbytes[:8],'big'))
    targets=rng.sample(range(4),2)
    return dict(enumerate(targets))


def context(seed, split, index):
    b=hashlib.sha256(f'{SCHEMA}/{seed}/{split}/{index}/public-context'.encode()).digest()
    return b[0] % 2


def score(selected, trial, target):
    center=selected['center']
    if type(center) is not int or not 0 <= center < len(trial['observed']):
        raise ValueError('invalid selected event')
    return trial['hidden'][center] == target


def raw_majority(tokens):
    c=Counter(tokens)
    label=min(x for x,n in c.items() if n == max(c.values()))
    return next(i for i,v in enumerate(tokens) if v == label)


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,ADDITIONAL):
        raise ValueError('evaluation seeds must match locked protocol')
    results={'schema':SCHEMA,'protocol':'benchmarks/outcome_event_memory_protocol.json',
             'blind':False,'fit':'source_bursts/train/0..159',
             'reward':'source_bursts/train/2000..2199',
             'evaluation':'test/93000..93063','rows':[]}
    for seed in seeds:
        streams=[episode(seed,'source_bursts','train',i)['observed'] for i in range(FIT)]
        segmenter=fit_event_model(streams)
        bandit=OutcomeEventMemory(segmenter,seed=seed)
        raw_bandit=OutcomeEventMemory(segmenter,seed=seed,mode='raw')
        target_map=preference(seed)
        train_rewards={'inferred_event':0,'raw_event':0}
        for i in range(REWARD_TRAIN):
            ix=TRAIN_START+i
            trial=episode(seed,'source_bursts','train',ix)
            ctx=context(seed,'train',ix)
            for name,model in [('inferred_event',bandit),('raw_event',raw_bandit)]:
                selection=model.propose(ctx,trial['observed'],split='train',index=ix)
                result=score(selection,trial,target_map[ctx])
                model.feedback(result,split='train',index=ix)
                train_rewards[name]+=result
        bandit=OutcomeEventMemory.restore(bandit.record(),segmenter)
        raw_bandit=OutcomeEventMemory.restore(raw_bandit.record(),segmenter)
        row={'seed':seed,'training_reward_counts':train_rewards,
             'model_sha256':bandit.record()['sha256'],'families':{}}
        for family in ('source_bursts','shifted_bursts'):
            labels=['learned_inferred','learned_raw','hmm_longest','hmm_recent','raw_majority','oracle_available']
            success={label:0 for label in labels}
            for j in range(TEST):
                index=TEST_START+j
                trial=episode(seed,family,'test',index)
                tokens=trial['observed']
                ctx=context(seed,'test',index)
                selected={
                    'learned_inferred':bandit.choose(ctx,tokens)['center'],
                    'learned_raw':raw_bandit.choose(ctx,tokens)['center'],
                    'hmm_longest':None,
                    'hmm_recent':None,
                    'raw_majority':raw_majority(tokens),
                    'oracle_available':None,
                }
                spans=segmenter.spans(tokens)
                longest=max(spans,key=lambda s:(s['end']-s['start'],-s['start'],-s['label']))
                selected['hmm_longest']=(longest['start']+longest['end']-1)//2
                last=spans[-1]
                selected['hmm_recent']=(last['start']+last['end']-1)//2
                selected['oracle_available']=next((i for i,x in enumerate(trial['hidden']) if x==target_map[ctx]),None)
                for name,point in selected.items():
                    success[name]+=int(point is not None and trial['hidden'][point] == target_map[ctx])
            row['families'][family]={'successes':success,'episodes':TEST}
        results['rows'].append(row)
    return results


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cohort',choices=('development','additional'),default='development')
    a.add_argument('--out')
    cfg=a.parse_args()
    body=json.dumps(measure(DEVELOPMENT if cfg.cohort=='development' else ADDITIONAL),sort_keys=True,indent=2)+'\n'
    if cfg.out:
        from pathlib import Path
        Path(cfg.out).write_text(body)
    print(body,end='')

if __name__=='__main__':main()
