"""Precommitted D3 variable-deletion benchmark. No truth enters inference.

Eight underlying synchronized events undergo independent deletions and
unlabelled insertions on each channel; observed overlap is variable. True
common-event IDs are used only to score the estimator, never to train it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from developmental_ai.environment_api import EnvironmentSession,digest
from developmental_ai.learned_spatial_memory import train_grid_updates
from developmental_ai.probabilistic_alignment import TemporalCorrespondence,marginal_score
from developmental_ai.unaligned_stream import alignment_score
from developmental_ai.raw_token_transfer import OBS,FORECAST,SOURCES
from developmental_ai.variable_correspondence import VariableCorrespondence
from benchmarks.raw_token_transfer_benchmark import stream as base_stream,cipher
from benchmarks.unaligned_stream_benchmark import fit,choose,DEV,ADDITIONAL
from benchmarks.dynamic_reliability_benchmark import navigate

SCHEMA='developmental-ai.variable-correspondence-benchmark/v1'
TRAIN_START=90000
TRAIN_EPISODES=120
TEST_START=99800
TEST_EPISODES=40


def _rng(seed,split,index,label):
    raw=f'{SCHEMA}/{seed}/{split}/{index}/{label}'.encode()
    return random.Random(int.from_bytes(hashlib.sha256(raw).digest()[:8],'big'))


def _channel(values,alphabet,rng):
    if len(values)!=8:raise ValueError('unexpected core stream size')
    dropped=set(rng.sample(range(8),rng.randint(0,2)))
    kept=[(v,i) for i,v in enumerate(values) if i not in dropped]
    for _ in range(rng.randint(2,4)):
        kept.insert(rng.randrange(len(kept)+1),(rng.choice(alphabet),None))
    return [v for v,_ in kept],{i for _,i in kept if i is not None}


def stream(seed,split,index,reference):
    if split not in ('train','test') or type(index) is not int or index<0:raise ValueError('invalid split/index')
    observed,cues,correct=base_stream(seed,split,index,reference)
    x,sensor_ids=_channel(observed,OBS,_rng(seed,split,index,'sensor'))
    candidates=[];common=None
    for name,offset,forecast in cues:
        y,ids=_channel(forecast,FORECAST,_rng(seed,split,index,name))
        candidates.append([name,offset,y])
        if name==correct:common=len(ids & sensor_ids)
    return x,candidates,correct,common


def train_model(seed,old_selector):
    pairs=[]
    for i in range(TRAIN_EPISODES):
        index=TRAIN_START+i
        reference=list(EnvironmentSession('occluded',seed,'train',index).frame()['observation']['beacon'])
        obs,cues,_,_=stream(seed,'train',index,reference)
        chosen=min(SOURCES,key=lambda name:(-marginal_score(obs,next(c[2] for c in cues if c[0]==name),old_selector.mapping),name))
        forecast=next(row[2] for row in cues if row[0]==chosen)
        pairs.append([obs,forecast])
    return VariableCorrespondence.restore(VariableCorrespondence(old_selector.mapping,pairs,training_digest=old_selector.evidence_digest).record())


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('locked protocol cohorts only')
    out={'schema':SCHEMA,'protocol':'benchmarks/variable_correspondence_protocol.json','blind':False,
         'train':'train/90000..90119','test':'test/99800..99839','train_supervision':'public pseudo-selected streams only',
         'rows':[]}
    for seed in seeds:
        updater=train_grid_updates(seed,24)
        learned,perm,identity=fit(seed,updater)
        old=TemporalCorrespondence(perm,evidence_digest=digest({'seed':seed,'fit':learned.record()['digest'],'perm':perm}),episodes=240)
        model=train_model(seed,old)
        oracle=VariableCorrespondence(cipher(seed),model.pairs,training_digest=old.evidence_digest) # cipher for scoring ONLY
        source_identity=min(identity,key=lambda name:(-(identity[name][0]+1)/(identity[name][1]+2),name))
        methods=('fixed_identity','old_reward','old_max_path','old_marginal_8','estimated_variable','oracle_cipher_variable','correct_cue')
        successes={method:0 for method in methods};hits={method:0 for method in methods}
        estimated_k=[];true_k=[];abs_error={"learned_model":[],"constant_6":[],"public_length_minus_4":[]}
        weights=[1. if perm[i]==j else -1. for i in range(4) for j in range(4)]
        for j in range(TEST_EPISODES):
            index=TEST_START+j
            beacon=list(EnvironmentSession('occluded',seed,'test',index).frame()['observation']['beacon'])
            obs,candidates,correct,common=stream(seed,'test',index,beacon)
            detail=model.details(obs,candidates)
            selected={'fixed_identity':source_identity,'old_reward':choose(obs,candidates,learned.scores()),
                      'old_max_path':choose(obs,candidates,weights),
                      'old_marginal_8':min(SOURCES,key=lambda name:(-marginal_score(obs,next(c[2] for c in candidates if c[0]==name),perm),name)),
                      'estimated_variable':detail['selected'],
                      'oracle_cipher_variable':oracle.select(obs,candidates),
                      'correct_cue':correct}
            estimated=detail['reports'][correct]['expected_matches']
            estimated_k.append(estimated)
            true_k.append(common)
            forecast=next(c[2] for c in candidates if c[0]==correct)
            abs_error['learned_model'].append(abs(estimated-common))
            abs_error['constant_6'].append(abs(6-common))
            abs_error['public_length_minus_4'].append(abs((len(obs)+len(forecast))/2-4-common))
            cache={}
            for method,name in selected.items():
                hits[method]+=name==correct
                if name not in cache:
                    chosen=next(c[1] for c in candidates if c[0]==name)
                    cache[name]=navigate(seed,'test',index,updater,chosen)
                successes[method]+=cache[name]
        out['rows'].append({'seed':seed,'navigation_successes':successes,'correct_source':hits,
                            'inferred_match_probability':round(model.match_probability,6),
                            'inferred_survival':round(model.survival,6),
                            'mean_predicted_common_events_on_true_candidate_scoring_only':round(sum(estimated_k)/len(estimated_k),5),
                            'mean_generator_common_event_count_scoring_only':round(sum(true_k)/len(true_k),5),
                            'training_digest':model.record()['sha256'],
                            'permutation_correct':perm==cipher(seed),
                            'supplemental_posthoc_absolute_count_error':{name:round(sum(values)/len(values),4) for name,values in abs_error.items()}})
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=('development','additional'),default='development');p.add_argument('--out')
    a=p.parse_args();res=json.dumps(measure(DEV if a.cohort=='development' else ADDITIONAL),indent=2,sort_keys=True)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(res)
    print(res,end='')
if __name__=='__main__':main()
