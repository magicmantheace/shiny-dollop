"""Precommitted reward-only reliability switching on simulated occluded navigation.

Generator alone uses the PUBLIC first-step target beacon to create 5 candidate
cues, one correct. Each candidate forecasts 8 public probe symbols, with
correct forecasts 75% accurate and distractors 25%; the correct source is
independently redrawn each episode. Neither learner sees the correct source,
beacon or hidden simulator state; only a terminal outcome trains it.
"""
import argparse
import hashlib
import json
import random

from developmental_ai.dynamic_reliability import DynamicReliability, SOURCES, START
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import PortableOffsetMemory, train_grid_updates
from developmental_ai.occluded_navigation import greedy_action

DEV = (43103,50021,61031)
RESERVED = (72019,83003,94009)
EPISODES = 40
TRAIN = 360


def _rng(seed,split,index):
    token=f'dynamic-reliability/v1/{seed}/{split}/{index}'.encode()
    return random.Random(int.from_bytes(hashlib.sha256(token).digest()[:8],'big'))


def stream(seed,split,index,reference):
    if (type(reference) is not list or len(reference)!=2 or
            any(type(v) is not int or not -8 <= v <= 8 for v in reference) or
            split not in ('train','test') or type(index) is not int):
        raise ValueError('invalid public simulation input')
    rng = _rng(seed,split,index)
    true_source = rng.choice(SOURCES)
    probes = [rng.randrange(4) for _ in range(8)]
    cues=[]
    for source in SOURCES:
        if source == true_source:
            offset = list(reference)
        else:
            while True:
                offset = [rng.randint(-8,8),rng.randint(-8,8)]
                if offset != reference:break
        acc = .75 if source==true_source else .25
        forecasts = [value if rng.random() < acc else rng.choice([v for v in range(4) if v!=value]) for value in probes]
        cues.append([source,offset,forecasts])
    rng.shuffle(cues)
    return probes,cues,true_source  # truth remains in BENCHMARK ONLY


def navigate(seed,split,index,updater,target):
    session = EnvironmentSession('occluded',seed,split,index)
    memory = PortableOffsetMemory(updater)
    rng = random.Random(seed*100000+index)
    last = None
    while not session.done:
        frame=session.frame()
        if frame['tick'] == 0:
            frame={**frame,'observation':{**frame['observation'],'beacon':list(target)}}
        action=greedy_action(memory.features(frame),rng)
        outcome=session.step(action,expected_tick=frame['tick'])
        memory.feedback(action,outcome)
        last=outcome['event']
    return last=='collected'


def train(seed,updater,basis):
    learner=DynamicReliability(seed,basis=basis)
    for i in range(TRAIN):
        index=START+i
        public = EnvironmentSession('occluded',seed,'train',index).frame()['observation']['beacon']
        probes,cues,_=stream(seed,'train',index,list(public))
        selected=learner.propose(probes,cues,split='train',index=index)
        reward=navigate(seed,'train',index,updater,selected)
        learner.feedback(reward,split='train',index=index)
    return DynamicReliability.restore(learner.record())


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,RESERVED):
        raise ValueError('cohort is precommitted; refusing test tuning')
    result={'schema':'developmental-ai.dynamic-reliability-benchmark/v1',
            'precommitted_protocol':'benchmarks/dynamic_reliability_protocol.json',
            'inspected_during_development':list(seeds)==list(DEV),
            'reward_only_training':True,'paired_reference_to_learner':False,
            'train_indices':[START,START+TRAIN-1],'test_indices':[99000,99000+EPISODES-1],
            'rows':[]}
    for seed in seeds:
        updater=train_grid_updates(seed,24)
        evidence=train(seed,updater,'evidence')
        identity=train(seed,updater,'identity')
        scores={k:0 for k in ('evidence','identity','max_agreement','first','last','random','oracle')}
        source_hits={k:0 for k in scores}
        for j in range(EPISODES):
            idx=99000+j
            ref=list(EnvironmentSession('occluded',seed,'test',idx).frame()['observation']['beacon'])
            probes,cues,truth=stream(seed,'test',idx,ref)
            counts={c[0]:sum(a==b for a,b in zip(c[2],probes)) for c in cues}
            max_name=min(k for k,v in counts.items() if v==max(counts.values()))
            picks={'evidence':evidence.source(probes,cues),'identity':identity.source(probes,cues),
                   'max_agreement':max_name,'first':cues[0][0],'last':cues[-1][0],
                   'random':random.Random(seed+idx).choice(cues)[0], 'oracle':truth}
            cached={}
            for mode,name in picks.items():
                source_hits[mode]+=name==truth
                if name not in cached:
                    target=next(c[1] for c in cues if c[0]==name)
                    cached[name]=navigate(seed,'test',idx,updater,target)
                scores[mode]+=cached[name]
        result['rows'].append({'seed':seed,'navigation_successes':scores,
            'cue_correct':source_hits,'evidence_stats':evidence.stats,
            'identity_stats':identity.stats,'record_digest':evidence.record()['digest']})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=('development','reserved'),default='development')
    p.add_argument('--out')
    opts=p.parse_args()
    result=measure(DEV if opts.cohort=='development' else RESERVED)
    data=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if opts.out:
        from pathlib import Path
        Path(opts.out).write_text(data)
    print(data,end='')

if __name__=='__main__':main()
