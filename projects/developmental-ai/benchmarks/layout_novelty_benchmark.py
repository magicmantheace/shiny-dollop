"""Compare counterfactual landmark novelty against the unchanged existing guards.

Strictly ordinary action/odometry/marker data enter detection. Simulator
fault labels appear only in test harness scoring; pre-fitted bank and hazard
are held constant between methods. Seeds have previously been inspected.
"""
from __future__ import annotations
import argparse
import json
from benchmarks.novelty_guard_benchmark import CONDITIONS, readings
from benchmarks.switching_belief_benchmark import HAZARDS, mixed_histories
from developmental_ai.mixed_experience import fit_mixed
from developmental_ai.closed_loop_adaptation import models_from_proposal
from developmental_ai.novelty_guard import NoveltyGuard, calibrate_guard
from developmental_ai.channel_novelty import ChannelGuard, calibrate_channels
from developmental_ai.layout_novelty import CalibratedLayoutGuard, calibrate_layouts, SCHEMA
from developmental_ai.switching_belief import calibrate_hazard, verified_hazard


def benchmark(seeds=(17,23,41), *,train=48,validation=16,hazard_calibration=12,
              reference=64,episodes=24,iterations=2,rounds=1,layout_alpha=.10):
    if (type(seeds) not in (tuple,list) or not seeds or len(set(seeds))!=len(seeds) or
            any(type(seed) is not int for seed in seeds) or
            type(train) is not int or not 20<=train<=300 or train%2 or
            type(validation) is not int or not 10<=validation<=200 or validation%2 or
            type(hazard_calibration) is not int or not 2<=hazard_calibration<=100 or
            type(reference) is not int or not 40<=reference<=200 or reference%2 or
            type(episodes) is not int or not 1<=episodes<=150 or
            type(iterations) is not int or not 1<=iterations<=10 or
            type(rounds) is not int or not 1<=rounds<=4 or
            type(layout_alpha) not in (float,int) or not .04<=layout_alpha<=.20):
        raise ValueError('invalid benchmark budget')
    out={'schema':SCHEMA,'seeds':list(seeds),'kind':'previously-inspected-seeds-not-blind',
         'budgets':{'fit':train,'validation':validation,'hazard':hazard_calibration,
                    'reference':reference,'evaluation_per_condition':episodes,
                    'iterations':iterations,'rounds':rounds,'layout_alpha':layout_alpha},
         'partitions':{'fit':'train/0+','model_validation':'train/10000+',
                       'hazard':'train/40000+','map_reference':'train/50000+',
                       'evaluation':'test/93000+'},
         'notes':'Alternative landmark offsets use the hardcoded two-half-separated-mark prior and learned bank roles, motion and odometry. Max-prefix threshold chosen on train-only 50/50 normal/known-switch streams. Runtime sees no true positions, regime or fault labels. Union across three detectors is not false-alarm calibrated. The map search is an observational diagnostic, not model learning or an authorization.',
         'rows':[]}
    for seed in seeds:
        proposal=fit_mixed(mixed_histories(seed,train,0),mixed_histories(seed,validation,10000),
                           seed=seed,iterations=iterations,rounds=rounds)
        models=models_from_proposal(proposal)
        hazard_streams=[readings(seed,'train',40000+i,'known-shift') for i in range(hazard_calibration)]
        hazard=verified_hazard(calibrate_hazard(models,hazard_streams,candidates=HAZARDS),models)
        refs=[readings(seed,'train',50000+i,'normal' if i%2==0 else 'known-shift') for i in range(reference)]
        old_rec=calibrate_guard(models,refs,hazard=hazard,alpha=.10)
        chan_rec=calibrate_channels(models,refs,alpha=.10)
        layout_rec=calibrate_layouts(models,refs,hazard=hazard,alpha=layout_alpha)
        row={'seed':seed,'model_count':len(models),'hazard':hazard,
             'layout_threshold':round(layout_rec['state']['threshold'],6),'conditions':{}}
        for kind in CONDITIONS:
            counts={'prior_layer_alarms':0,'layout_alarms':0,'combined_alarms':0,
                    'layout_only_alarms':0,'legacy_surprise_alarms':0,'channel_alarms':0}
            delays={'prior_layer':[],'layout':[],'combined':[]}
            for i in range(episodes):
                stream=readings(seed,'test',93000+i,kind)
                old=NoveltyGuard(stream['initial'],stream['goal'],stream['n'],models,old_rec)
                ch=ChannelGuard(models,chan_rec)
                lm=CalibratedLayoutGuard(stream['initial'],stream['goal'],stream['n'],models,layout_rec)
                first={'prior_layer':None,'layout':None,'combined':None}
                for step,(action,obs) in enumerate(stream['observations'],1):
                    a=old.advance(action,obs)['alarm']
                    b=ch.advance(action,obs)['alarm']
                    c=lm.advance(action,obs)['alarm']
                    for key,alarm in (('prior_layer',a or b),('layout',c),('combined',a or b or c)):
                        if alarm and first[key] is None:first[key]=step
                prior=old.alarm or ch.alarm
                counts['prior_layer_alarms']+=int(prior)
                counts['layout_alarms']+=int(lm.first_alarm is not None)
                counts['combined_alarms']+=int(prior or lm.first_alarm is not None)
                counts['layout_only_alarms']+=int(lm.first_alarm is not None and not prior)
                counts['legacy_surprise_alarms']+=int(old.alarm)
                counts['channel_alarms']+=int(ch.alarm)
                for k,v in first.items():
                    if v is not None:delays[k].append(v)
            row['conditions'][kind]={**counts,'episodes':episodes,
                 'first_alarm_mean_step':{k:round(sum(v)/len(v),3) if v else None for k,v in delays.items()}}
        out['rows'].append(row)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',nargs='+',type=int,default=[17,23,41])
    p.add_argument('--train',type=int,default=48);p.add_argument('--validation',type=int,default=16)
    p.add_argument('--hazard-calibration',type=int,default=12);p.add_argument('--reference',type=int,default=64)
    p.add_argument('--episodes',type=int,default=24);p.add_argument('--iterations',type=int,default=2)
    p.add_argument('--rounds',type=int,default=1);p.add_argument('--layout-alpha',type=float,default=.10);p.add_argument('--out')
    a=p.parse_args()
    result=benchmark(a.seeds,train=a.train,validation=a.validation,hazard_calibration=a.hazard_calibration,
                     reference=a.reference,episodes=a.episodes,iterations=a.iterations,rounds=a.rounds,
                     layout_alpha=a.layout_alpha)
    data=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(data,encoding='utf-8')
    print(data,end='')
if __name__=='__main__':main()
