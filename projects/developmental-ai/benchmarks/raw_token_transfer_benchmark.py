"""Frozen public raw-symbol cue alignment benchmark; no target pairing in fit.

A seed-fixed hidden token substitution changes the forecast alphabet. Pairwise
sequence position is still GIVEN to both learned and unsupervised baselines.
Model fit receives one terminal navigation success bit, not correct cue/truth.
"""
from __future__ import annotations
import argparse
import itertools
import hashlib
import json
import random

from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import train_grid_updates
from developmental_ai.raw_token_transfer import RewardTokenAligner, OBS, FORECAST, SOURCES, START, validate
from benchmarks.dynamic_reliability_benchmark import stream as base_stream, navigate

DEV = (43103,50021,61031)
ADDITIONAL = (72019,83003,94009)
TRAIN = 360
TEST = 40
TEST_START = 99200
SCHEMA = 'developmental-ai.raw-token-transfer-benchmark/v1'


def cipher(seed):
    rng = random.Random(int.from_bytes(hashlib.sha256(f'{SCHEMA}/{seed}/cipher'.encode()).digest()[:8],'big'))
    perm = list(range(4));rng.shuffle(perm)
    return tuple(perm)


def stream(seed, split, index, reference):
    p, cues, truth = base_stream(seed, split, index, reference)
    mapping = cipher(seed)
    public_obs = [OBS[i] for i in p]
    public_cues = [[name, list(offset), [FORECAST[mapping[x]] for x in prediction]]
                   for name,offset,prediction in cues]
    return public_obs, public_cues, truth


def fit(seed, updater):
    model = RewardTokenAligner(seed)
    # Unsupervised relation baseline sees exactly the same publicly visible
    # episode streams (ALL candidates), without any reward or hidden cipher.
    cooccurrence = [[0]*4 for _ in range(4)]
    source_rewards = {name:[0,0] for name in SOURCES}
    for i in range(TRAIN):
        index = START+i
        ref = list(EnvironmentSession('occluded',seed,'train',index).frame()['observation']['beacon'])
        obs, cues, _ = stream(seed,'train',index,ref)
        validate(obs,cues)
        for _,_,forecast in cues:
            for a,b in zip(obs,forecast):cooccurrence[OBS.index(a)][FORECAST.index(b)] += 1
        selected = model.propose(obs,cues,split='train',index=index)
        success = navigate(seed,'train',index,updater,selected)
        model.feedback(success,split='train',index=index)
        selected_name = model.events[-1]['chosen']
        source_rewards[selected_name][0] += int(success)
        source_rewards[selected_name][1] += 1
    perm = max(itertools.permutations(range(4)),key=lambda order:sum(cooccurrence[i][order[i]] for i in range(4)))
    return RewardTokenAligner.restore(model.record()), perm, source_rewards


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('evaluation cohort is frozen')
    out = {'schema':SCHEMA,'protocol':'benchmarks/raw_token_transfer_protocol.json',
           'blind':False,'fit':'train/88500..88859','eval':'test/99200..99239',
           'train_reward_only':True,'learned_pair_slots_are_aligned_by_design':True,'rows':[]}
    for seed in seeds:
        updater = train_grid_updates(seed,24)
        learner,unsup, source_rewards = fit(seed,updater)
        # Direct identity-only contextual bandit with the EXACT same 360
        # source choices and terminal outcomes as the learned pair scorer.
        identity_name = min(SOURCES, key=lambda name: (-(source_rewards[name][0]+1)/(source_rewards[name][1]+2), name))
        scores = {m:0 for m in ('learned_raw','identity','literal','unsupervised','decoded_oracle_rule','random','correct_cue')}
        source_hits = {m:0 for m in scores}
        for i in range(TEST):
            index = TEST_START+i
            ref = list(EnvironmentSession('occluded',seed,'test',index).frame()['observation']['beacon'])
            observed,cues,truth = stream(seed,'test',index,ref)
            def matches(mapping):
                return {name: sum(FORECAST[mapping[OBS.index(a)]]==b for a,b in zip(observed,forecast))
                        for name,_,forecast in cues}
            def pick(counts):
                highest=max(counts.values());return min(name for name,val in counts.items() if val==highest)
            # No matching token values across disjoint public alphabets.
            literal = {name:sum(a==b for a,b in zip(observed,forecast)) for name,_,forecast in cues}
            choices={'learned_raw':learner.source(observed,cues),
                     'identity':identity_name,
                     'literal':pick(literal),
                     'unsupervised':pick(matches(unsup)),
                     'decoded_oracle_rule':pick(matches(cipher(seed))),
                     'random':random.Random(seed+index).choice(cues)[0],
                     'correct_cue':truth}
            cache={}
            for name,src in choices.items():
                source_hits[name]+=src==truth
                if src not in cache:
                    target=next(list(c[1]) for c in cues if c[0]==src)
                    cache[src]=navigate(seed,'test',index,updater,target)
                scores[name]+=cache[src]
        out['rows'].append({'seed':seed,'tasks':scores,'correct_cue_selections':source_hits,
                            'learned_record_digest':learner.record()['digest'],
                            'unsupervised_permutation_equals_hidden':unsup==cipher(seed),
                            'positive_training_episodes':sum(1 for e in learner.events if e['success']),
                            'identity_reward_counts':source_rewards})
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort',choices=('development','additional'),default='development')
    ap.add_argument('--out')
    args=ap.parse_args()
    payload=json.dumps(measure(DEV if args.cohort=='development' else ADDITIONAL),sort_keys=True,indent=2)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(payload)
    print(payload,end='')

if __name__=='__main__':main()
