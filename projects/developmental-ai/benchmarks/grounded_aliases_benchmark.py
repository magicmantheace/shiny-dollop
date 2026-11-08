"""Explicitly TRAIN-CALIBRATED new domain aliases; never zero-shot generality.

All cue streams are generated at a simulator boundary from a public initial
beacon. The adapter's target SELECT method never receives that reference.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from developmental_ai.online_memory_gate import MemoryGate
from developmental_ai.grounded_aliases import GroundedAliases
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import PortableOffsetMemory,train_grid_updates
from developmental_ai.occluded_navigation import greedy_action
from benchmarks.online_memory_gate_benchmark import cue_stream

SCHEMA='developmental-ai.grounded-aliases-benchmark/v1'
SEEDS=(2749,6607,9901)
CAL_EPISODES=48
TEST_EPISODES=40


def _seed(seed,label):
    return int.from_bytes(hashlib.sha256(f'{SCHEMA}/{seed}/{label}'.encode()).digest()[:8],'big')


def aliases(seed):
    rng=random.Random(_seed(seed,'alias-permutation'))
    sources=[f'foreign-{n}' for n in (13,28,47,66,91)]
    rng.shuffle(sources)
    contexts=['lunar','solar'];rng.shuffle(contexts)
    return {s:t for s,t in zip(('A','B','N0','N1','N2'),sources)},dict(zip((0,1),contexts))


def stream(seed,index,reference):
    src,cmap=aliases(seed)
    ctx,candidates=cue_stream(seed,index,reference)
    rng=random.Random(_seed(seed,f'tokens-{index}'))
    noisy=iter(('N0','N1','N2'))
    encoded=[]
    for ch,token,offset in candidates:
        code=src[next(noisy)] if ch=='N' else src[ch]
        encoded.append([code,rng.randrange(4),list(offset)])
    return {'context':cmap[ctx], 'cues':encoded}


def calibration(seed,episodes=CAL_EPISODES):
    rows=[]
    for i in range(episodes):
        session=EnvironmentSession('occluded',seed,'train',70000+i)
        ref=list(session.frame()['observation']['beacon'])
        sample=stream(seed,70000+i,ref)
        rows.append({**sample,'reference':ref})
    return rows


def navigate(seed,index,updater,gate,adapter,mode):
    world=EnvironmentSession('occluded',seed,'test',97000+index)
    # Only the benchmark's synthetic cue generator accesses the simulator's
    # initial public reference; the evaluated selector does not receive it.
    actual=world.frame()['observation']['beacon']
    sample=stream(seed,97000+index,actual)
    candidates=sample['cues']
    rng=random.Random(_seed(seed,f'baseline-{index}'))
    if mode=='adapted': selected=adapter.select(sample['context'],candidates)
    elif mode=='paired_lookup':
        # Strong non-transfer baseline: pick the source that matched public
        # calibration references for this context; no MemoryGate needed.
        known=adapter.alignment['reliable_sources'][sample['context']]
        selected=next(c[2] for c in candidates if c[0]==known)
    elif mode=='first': selected=candidates[0][2]
    elif mode=='last': selected=candidates[-1][2]
    elif mode=='random': selected=candidates[rng.randrange(5)][2]
    elif mode=='oracle':selected=actual
    elif mode=='wrong_context':
        other=next(c for c in adapter.alignment['contexts'] if c!=sample['context'])
        selected=adapter.select(other,candidates)
    else:raise ValueError('unknown baseline')
    memory=PortableOffsetMemory(updater)
    rng=random.Random(seed*100000+97000+index)
    last=None
    while not world.done:
        frame=world.frame()
        if frame['tick']==0:
            frame={**frame,'observation':{**frame['observation'],'beacon':list(selected)}}
        act=greedy_action(memory.features(frame),rng)
        result=world.step(act,expected_tick=frame['tick'])
        memory.feedback(act,result)
        last=result['event']
    return last=='collected'


def measure(seeds=SEEDS,*,train=1800,calibration_episodes=CAL_EPISODES,episodes=TEST_EPISODES):
    if (type(seeds) not in (tuple,list) or not seeds or len(seeds)!=len(set(seeds)) or
            any(type(s) is not int for s in seeds) or type(train) is not int or not 1<=train<=10000 or
            type(calibration_episodes) is not int or not 8<=calibration_episodes<=200 or
            type(episodes) is not int or not 1<=episodes<=150):
        raise ValueError('invalid benchmark parameters')
    result={'schema':SCHEMA,'blind':False,'calibration_is_supervised':True,
            'train_gate_episodes':train,'new_domain_public_pair_calibration':calibration_episodes,
            'test_episodes_per_seed':episodes,'calibration_split':'train/70000+',
            'test_split':'test/97000+','rows':[]}
    for seed in seeds:
        gate=MemoryGate(seed).train(train)
        adapter=GroundedAliases(gate,calibration(seed,calibration_episodes))
        updater=train_grid_updates(seed,24)
        scores={mode:sum(navigate(seed,i,updater,gate,adapter,mode) for i in range(episodes))
                for mode in ('adapted','paired_lookup','wrong_context','first','last','random','oracle')}
        result['rows'].append({'seed':seed,'scores':scores,'alignment':adapter.alignment,
                               'adapter_digest':adapter.record()['digest']})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',nargs='+',type=int,default=list(SEEDS))
    p.add_argument('--train',type=int,default=1800)
    p.add_argument('--episodes',type=int,default=40)
    p.add_argument('--calibration',type=int,default=48)
    p.add_argument('--out')
    o=p.parse_args()
    data=json.dumps(measure(o.seeds,train=o.train,episodes=o.episodes,calibration_episodes=o.calibration),indent=2,sort_keys=True)+'\n'
    if o.out:
        from pathlib import Path
        Path(o.out).write_text(data)
    print(data,end='')
if __name__=='__main__':main()
