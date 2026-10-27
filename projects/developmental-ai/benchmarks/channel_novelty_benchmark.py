"""Compare the unchanged model-surprise guard with an optional run-length overlay.

Matched seeds and streams from novelty_guard_benchmark; no test-label inputs to
calibration. Rates measure injected *sensor stuck* faults, not generic novelty.
"""
from __future__ import annotations

import argparse
import json

from benchmarks.novelty_guard_benchmark import CONDITIONS, readings
from benchmarks.switching_belief_benchmark import HAZARDS, mixed_histories
from developmental_ai.closed_loop_adaptation import models_from_proposal, NavigationSession
from developmental_ai.mixed_experience import fit_mixed
from developmental_ai.novelty_guard import NoveltyGuard, GuardedNavigation, calibrate_guard
from developmental_ai.channel_novelty import ChannelGuard, LayeredGuard, LayeredNavigation, calibrate_channels
from developmental_ai.switching_belief import calibrate_hazard, verified_hazard
from developmental_ai.adaptive_dynamics import CalibrationWorld


def benchmark(seeds=(17,23,41),*,train=48,validation=16,hazard_calibration=12,
              reference=64,episodes=24,iterations=2,rounds=1):
    if (type(seeds) not in (list,tuple) or not seeds or len(set(seeds))!=len(seeds)
            or any(type(seed) is not int for seed in seeds) or
            type(episodes) is not int or not 1<=episodes<=150 or
            type(reference) is not int or not 40<=reference<=200 or reference%2 or
            type(train) is not int or train<20 or train%2 or type(validation) is not int or validation<10 or validation%2 or
            type(hazard_calibration) is not int or not 2<=hazard_calibration<=100 or
            type(iterations) is not int or not 1<=iterations<=10 or type(rounds) is not int or not 1<=rounds<=4):
        raise ValueError('invalid benchmark budget')
    result={'schema':'channel-novelty/v1','kind':'inspected-seeds-not-blind','seeds':list(seeds),
            'budgets':{'train':train,'validation':validation,'hazard_calibration':hazard_calibration,
                       'reference':reference,'episodes_per_condition':episodes,
                       'iterations':iterations,'rounds':rounds},
            'partitions':{'fit':'train/0+','validation':'train/10000+','hazard':'train/40000+',
                          'references':'train/50000+','evaluation':'test/93000+'},
            'notes':'Stuck odometry and landmark faults are artificially injected. Both guards have independent train-only alpha=.10 calibrations, so their OR is not calibrated at 10%. Same frozen bank, hazard and all evaluation streams. Conditions and seeds were previously inspected; no out-of-family proof, navigation benefit, or statistical guarantee.',
            'rows':[]}
    for seed in seeds:
        proposal=fit_mixed(mixed_histories(seed,train,0),mixed_histories(seed,validation,10000),
                           seed=seed,iterations=iterations,rounds=rounds)
        models=models_from_proposal(proposal)
        haz=[readings(seed,'train',40000+i,'known-shift') for i in range(hazard_calibration)]
        hazard_receipt=calibrate_hazard(models,haz,candidates=HAZARDS)
        hz=verified_hazard(hazard_receipt,models)
        refs=[readings(seed,'train',50000+i,'normal' if i%2==0 else 'known-shift') for i in range(reference)]
        old=calibrate_guard(models,refs,hazard=hz,alpha=.10)
        new=calibrate_channels(models,refs,alpha=.10)
        row={'seed':seed,'model_count':len(models),'switch_hazard':hz,
             'model_surprise_cutoff':round(old['state']['threshold'],8),
             'run_cutoffs':new['state']['cutoffs'],'conditions':{}}
        for kind in CONDITIONS:
            counters={'old_alarms':0,'channel_alarms':0,'combined_alarms':0,
                      'channel_only_alarms':0,'zero_odometry_alarms':0,'constant_landmark_alarms':0}
            times={'old':[],'channel':[],'combined':[]}
            for i in range(episodes):
                r=readings(seed,'test',93000+i,kind)
                old_guard=NoveltyGuard(r['initial'],r['goal'],r['n'],models,old)
                channel=ChannelGuard(models,new)
                first_old=first_channel=first_combined=None
                for step,(action,ob) in enumerate(r['observations'],start=1):
                    a=old_guard.advance(action,ob)['alarm']
                    b=channel.advance(action,ob)['alarm']
                    if a and first_old is None:first_old=step
                    if b and first_channel is None:first_channel=step
                    if a or b:
                        if first_combined is None:first_combined=step
                counters['old_alarms']+=int(old_guard.alarm)
                counters['channel_alarms']+=int(channel.alarm)
                counters['combined_alarms']+=int(old_guard.alarm or channel.alarm)
                counters['channel_only_alarms']+=int(channel.alarm and not old_guard.alarm)
                for typ in ('zero_odometry','constant_landmark'):
                    counters[typ+'_alarms']+=int(typ in channel.alarms)
                for key,t in [('old',first_old),('channel',first_channel),('combined',first_combined)]:
                    if t is not None:times[key].append(t)
            row['conditions'][kind]={**counters,'episodes':episodes,'first_alarm_mean_step':{
                k:round(sum(v)/len(v),3) if v else None for k,v in times.items()}}
        # Observe the operational cost of a diagnostic pause, using identical
        # closed-loop simulations. No policies or learned models are changed.
        closed_loop={}
        for condition in ('normal','odometry-fault','landmark-fault'):
            counts={'unmodified_success':0,'original_guard_success':0,'layered_guard_success':0,
                    'original_guard_pauses':0,'layered_guard_pauses':0}
            for i in range(episodes):
                for mode in ('unmodified','original_guard','layered_guard'):
                    world=CalibrationWorld(seed,'test',97000+i,'standard','fixed')
                    if mode=='unmodified':
                        agent=NavigationSession(proposal,world.initial,world.goal,world.n,
                                                hazard_receipt,mode='switching')
                    elif mode=='original_guard':
                        agent=GuardedNavigation(proposal,hazard_receipt,old,world.initial,world.goal,world.n)
                    else:
                        agent=LayeredNavigation(proposal,hazard_receipt,old,new,world.initial,world.goal,world.n)
                    result_event=''
                    while not world.done:
                        act=agent.select_action()
                        if act is None:break
                        obs,_,done,result_event=world.step(act)
                        if condition=='odometry-fault':obs['odometry']=0
                        if condition=='landmark-fault':obs['landmark']=0
                        agent.advance(act,obs,done=done)
                    counts[mode+'_success']+=int(result_event=='success')
                    if mode!='unmodified':
                        counts[mode+'_pauses']+=int((agent.guard.alarm if mode=='original_guard' else agent.alarm) and not world.done)
            closed_loop[condition]={**counts,'episodes':episodes}
        row['closed_loop_pause_comparison']=closed_loop
        result['rows'].append(row)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',nargs='+',type=int,default=[17,23,41])
    p.add_argument('--train',type=int,default=48);p.add_argument('--validation',type=int,default=16)
    p.add_argument('--hazard-calibration',type=int,default=12);p.add_argument('--reference',type=int,default=64)
    p.add_argument('--episodes',type=int,default=24);p.add_argument('--iterations',type=int,default=2)
    p.add_argument('--rounds',type=int,default=1);p.add_argument('--out')
    a=p.parse_args()
    obj=benchmark(a.seeds,train=a.train,validation=a.validation,hazard_calibration=a.hazard_calibration,
                  reference=a.reference,episodes=a.episodes,iterations=a.iterations,rounds=a.rounds)
    value=json.dumps(obj,indent=2,sort_keys=True)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(value,encoding='utf-8')
    print(value,end='')

if __name__=='__main__':main()
