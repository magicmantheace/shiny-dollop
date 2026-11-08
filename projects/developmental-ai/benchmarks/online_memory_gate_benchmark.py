"""Frozen-condition exploratory write/keep and cross-task navigation experiment.

Navigation candidate hints are generated from a PUBLIC initial target beacon;
channel/context semantics, hint generation and motion memory are engineered.
No held-out cohort here is blind. Does not claim new D1/D3 gates.
"""
from __future__ import annotations
import argparse
import json
import random
from developmental_ai.online_memory_gate import MemoryGate, CueMemory
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import PortableOffsetMemory,train_grid_updates
from developmental_ai.occluded_navigation import greedy_action

DEVELOPMENT=(2749,6607,9901)
ADDITIONAL=(17431,24869,37021)
SCHEMA='developmental-ai.online-gate-benchmark/v1'


def cue_stream(seed,index,original):
    """Synthetic public competing observations, never simulator hidden state."""
    rng=random.Random((seed*1000003+index*9419)^0x5bf42)
    ctx=rng.randrange(2)
    alternate=tuple(max(-8,min(8,original[j]+rng.choice([-3,-2,2,3]))) for j in (0,1))
    good='A' if ctx==0 else 'B'
    candidates=[]
    for ch in ('A','B'):
        candidates.append((ch, tuple(original) if ch==good else alternate))
    for _ in range(3):
        decoy=tuple(max(-8,min(8,original[j]+rng.choice([-3,-2,2,3]))) for j in (0,1))
        candidates.append(('N',decoy))
    rng.shuffle(candidates)
    return ctx,[(ch,i,offset) for i,(ch,offset) in enumerate(candidates)]


def choose_beacon(gate,mode,ctx,candidates,seed,index):
    if mode not in ('learned','first','last','random','oracle','no_context'):
        raise ValueError('invalid controller')
    rng=random.Random(seed*97+index*193)
    held=None
    session=CueMemory(gate,ctx if mode!='no_context' else 0) if mode in ('learned','no_context') else None
    for channel,token,offset in candidates:
        if session is not None:
            result=session.observe(channel,token % 4,offset)
            write=result['operation']=='write'
        elif held is None:write=True
        elif mode=='first':write=False
        elif mode=='last':write=True
        elif mode=='random':write=bool(rng.randrange(2))
        elif mode=='oracle':write=(channel==('A' if ctx==0 else 'B'))
        else:
            raise AssertionError('unhandled baseline mode')
        if write:held=(channel,token,offset)
    if session is not None and session.held["payload"]!=list(held[2]):
        raise AssertionError("public cue selector diverged")
    return held[2]


def navigate(seed,index,updater,gate,mode):
    session=EnvironmentSession('occluded',seed,'test',index)
    first=session.frame()
    ctx,candidates=cue_stream(seed,index,first['observation']['beacon'])
    selected=choose_beacon(gate,mode,ctx,candidates,seed,index)
    memory=PortableOffsetMemory(updater)
    rng=random.Random(seed*100000+index)
    last=None
    while not session.done:
        frame=session.frame()
        if frame['tick']==0:
            frame={**frame,'observation':{**frame['observation'],'beacon':list(selected)}}
        features=memory.features(frame)
        action=greedy_action(features,rng)
        result=session.step(action,expected_tick=frame['tick'])
        memory.feedback(action,result)
        last=result['event']
    return last=='collected'


def measure(seeds=DEVELOPMENT,*,train=1800,episodes=40,updater_episodes=24):
    if (type(seeds) not in (tuple,list) or not seeds or len(set(seeds))!=len(seeds) or
        any(type(s) is not int for s in seeds) or type(train) is not int or not 1<=train<=10000 or
        type(episodes) is not int or not 1<=episodes<=150 or type(updater_episodes) is not int or not 1<=updater_episodes<=200):
        raise ValueError('invalid evaluation configuration')
    output={'schema':SCHEMA,'blind':False,'seeds':list(seeds),'train':train,
            'train_split':'train/0..N-1 (competing signals); grid train for motion updater',
            'test_splits':{'signals':'test/93000+','occluded':'test/94000+'},
            'episodes_per_seed':episodes,'rows':[]}
    for seed in seeds:
        gate=MemoryGate(seed).train(train)
        updater=train_grid_updates(seed,updater_episodes)
        row={'seed':seed,'gate_digest':gate.record()['digest'],
             'source_scores':{k:round(v[0],5) for k,v in sorted(gate.source.items())},
             'competing_signals':sum(gate.trial('test',93000+i)['success'] for i in range(episodes)),
             'navigation':{}}
        for mode in ('learned','first','last','random','oracle','no_context'):
            row['navigation'][mode]=sum(navigate(seed,94000+i,updater,gate,mode) for i in range(episodes))
        output['rows'].append(row)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',type=int,nargs='+',default=list(DEVELOPMENT))
    p.add_argument('--train',type=int,default=1800)
    p.add_argument('--episodes',type=int,default=40)
    p.add_argument('--out')
    opts=p.parse_args()
    data=json.dumps(measure(opts.seeds,train=opts.train,episodes=opts.episodes),indent=2,sort_keys=True)+'\n'
    if opts.out:
        from pathlib import Path
        Path(opts.out).write_text(data,encoding='utf8')
    print(data,end='')

if __name__=='__main__':main()
