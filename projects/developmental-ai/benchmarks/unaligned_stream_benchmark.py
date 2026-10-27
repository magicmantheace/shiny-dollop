"""Frozen matched test of raw independent sequence insertions (not blind)."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import random
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import train_grid_updates
from developmental_ai.raw_token_transfer import OBS,FORECAST,SOURCES
from developmental_ai.unaligned_stream import UnalignedRewardLearner, TRAIN_START, alignment_score, near_pairs, validate
from benchmarks.raw_token_transfer_benchmark import stream as base_stream, cipher
from benchmarks.dynamic_reliability_benchmark import navigate

SCHEMA='developmental-ai.unaligned-stream-benchmark/v1'
DEV=(43103,50021,61031)
ADDITIONAL=(72019,83003,94009)
TRAIN=240
TEST=40
TEST_START=99600


def _rng(seed,split,index,name):
    payload=f'{SCHEMA}/{seed}/{split}/{index}/{name}'.encode()
    return random.Random(int.from_bytes(hashlib.sha256(payload).digest()[:8],'big'))


def insert_noise(tokens,rng,alphabet):
    seq=list(tokens)
    for _ in range(rng.randint(2,4)):
        seq.insert(rng.randrange(len(seq)+1),rng.choice(alphabet))
    return seq


def stream(seed,split,index,reference):
    observed,cues,truth=base_stream(seed,split,index,reference)
    observed=insert_noise(observed,_rng(seed,split,index,'sensor'),OBS)
    candidates=[[name,offset,insert_noise(seq,_rng(seed,split,index,name),FORECAST)]
                for name,offset,seq in cues]
    validate(observed,candidates)
    return observed,candidates,truth


def fit(seed,updater):
    model=UnalignedRewardLearner(seed)
    cooc=[[0.]*4 for _ in range(4)]
    identity={name:[0,0] for name in SOURCES}
    for i in range(TRAIN):
        index=TRAIN_START+i
        ref=list(EnvironmentSession('occluded',seed,'train',index).frame()['observation']['beacon'])
        obs,cues,_=stream(seed,'train',index,ref)
        for _,_,forecast in cues:
            for k,w in near_pairs(obs,forecast):cooc[k//4][k%4]+=w
        selected=model.propose(obs,cues,split='train',index=index)
        success=navigate(seed,'train',index,updater,selected)
        model.feedback(success,split='train',index=index)
        name=model.history[-1]['chosen'];identity[name][0]+=int(success);identity[name][1]+=1
    perm=max(itertools.permutations(range(4)),key=lambda p:sum(cooc[i][p[i]] for i in range(4)))
    return UnalignedRewardLearner.restore(model.record()),perm,identity


def choose(observed,cues,weights):
    vals={name:alignment_score(observed,seq,weights) for name,_,seq in cues}
    return min(name for name in vals if vals[name]==max(vals.values()))


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('protocol cohort locked')
    out={'schema':SCHEMA,'protocol':'benchmarks/unaligned_stream_protocol.json',
         'blind':False,'train':'train/89400..89639','test':'test/99600..99639',
         'reward_training':'terminal success bit only','rows':[]}
    for seed in seeds:
        updater=train_grid_updates(seed,24)
        learned,perm,identity=fit(seed,updater)
        identity_name=min(SOURCES,key=lambda s:(-(identity[s][0]+1)/(identity[s][1]+2),s))
        unsup=[1. if p[i]==j else -1. for i in range(4) for j in range(4) for p in [perm]]
        oracle=[1. if p[i]==j else -1. for i in range(4) for j in range(4) for p in [cipher(seed)]]
        methods=('learned_raw','identity','bag_frequency','unsupervised_dp','oracle_cipher_dp','random','correct_cue')
        score={name:0 for name in methods};hits={name:0 for name in methods}
        for i in range(TEST):
            index=TEST_START+i
            ref=list(EnvironmentSession('occluded',seed,'test',index).frame()['observation']['beacon'])
            obs,cues,truth=stream(seed,'test',index,ref)
            # Bag baseline disregards token positions, but uses the SAME trained reward weights.
            weight=learned.scores()
            bag={name:sum(weight[OBS.index(x)*4+FORECAST.index(y)] for x in obs for y in seq)/(len(obs)*len(seq))
                 for name,_,seq in cues}
            bag_name=min(s for s in bag if bag[s]==max(bag.values()))
            selected={'learned_raw':learned.source(obs,cues),'identity':identity_name,
                      'bag_frequency':bag_name,'unsupervised_dp':choose(obs,cues,unsup),
                      'oracle_cipher_dp':choose(obs,cues,oracle),
                      'random':_rng(seed,'test',index,'random').choice(SOURCES),'correct_cue':truth}
            cache={}
            for method,name in selected.items():
                hits[method]+=name==truth
                if name not in cache:
                    offset=next(list(c[1]) for c in cues if c[0]==name)
                    cache[name]=navigate(seed,'test',index,updater,offset)
                score[method]+=cache[name]
        out['rows'].append({'seed':seed,'successes':score,'source_hits':hits,
              'unsupervised_mapping_exact':perm==cipher(seed),
              'checkpoint_sha256':learned.record()['digest'],
              'source_train_success_counts':identity})
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=('development','additional'),default='development')
    p.add_argument('--out')
    a=p.parse_args()
    data=json.dumps(measure(DEV if a.cohort=='development' else ADDITIONAL),indent=2,sort_keys=True)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(data)
    print(data,end='')

if __name__=='__main__':main()
