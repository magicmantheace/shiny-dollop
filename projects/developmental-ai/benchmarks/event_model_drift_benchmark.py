"""Precommitted observation-only event-HMM drift diagnostic evaluation.

Both continuous streams look identical to the online monitor in schema; only
benchmark scoring knows where the two independently generated chunks meet.
"""
from __future__ import annotations

import argparse
import json
from statistics import median
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.event_model_drift import EventDrift,calibrate,METHODS
from benchmarks.event_segmentation_benchmark import episode

SCHEMA='developmental-ai.event-model-drift-benchmark/v1'
DEV=(14003,14009,14033)
AUDIT=(27007,27011,27017)
CAL=80
EVAL=40
START=94000


def pair(seed, split, index, changed):
    first=episode(seed,'source_bursts',split,index*2)['observed']
    second=episode(seed,'shifted_bursts' if changed else 'source_bursts',split,index*2+1)['observed']
    return first+second,len(first)


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,AUDIT):
        raise ValueError('cohort locked by precommitted protocol')
    result={'schema':SCHEMA,'protocol':'benchmarks/event_model_drift_protocol.json',
            'blind':False,'calibration':'train/800..879 (pairs)',
            'train':'source_bursts/train/0..159', 'evaluation':'test/94000..94039 (pairs)',
            'per_seed_per_condition':EVAL,'rows':[]}
    for seed in seeds:
        model=fit_event_model([episode(seed,'source_bursts','train',i)['observed'] for i in range(160)])
        # Using a separate train namespace, shared by all methods.
        baseline=[pair(seed,'train',400+i,False)[0] for i in range(CAL)]
        receipt=calibrate(model,baseline)
        rows={}
        for condition in ('stationary','shifted'):
            metrics={method:{'any_alarm':0,'early_alarm':0,'post_change_detected':0,
                             'delay':[],'first_alarm_steps':[],'clean_detected':0} for method in METHODS}
            losses=[]
            for i in range(EVAL):
                tokens,boundary=pair(seed,'test',START+i,condition=='shifted')
                nav=EventDrift(model,receipt)
                for token in tokens:nav.observe(token)
                losses.append(sum(nav.losses)/len(nav.losses))
                for method in METHODS:
                    threshold=receipt['state']['thresholds'][method]
                    indices=[j for j,x in enumerate(nav.values[method]) if x>threshold]
                    early=any(j<boundary for j in indices)
                    late=next((j for j in indices if j>=boundary),None)
                    values=metrics[method]
                    values['any_alarm']+=bool(indices)
                    values['early_alarm']+=early
                    if indices:values['first_alarm_steps'].append(indices[0]+1)
                    if condition=='shifted' and late is not None:
                        values['post_change_detected']+=1
                        if not early:values['clean_detected']+=1
                        values['delay'].append(late-boundary+1)
            rows[condition]={k:{'any_alarm':v['any_alarm'],'early_alarm':v['early_alarm'],
                'post_change_detected':v['post_change_detected'],
                'clean_detected':v['clean_detected'],
                'median_post_delay':median(v['delay']) if v['delay'] else None}
                for k,v in metrics.items()}
            rows[condition]['mean_log_loss']=round(sum(losses)/len(losses),6)
        result['rows'].append({'seed':seed,'hmm_p':round(model.persistence,6),
                'hmm_q':round(model.sensor_accuracy,6),
                'reference_loss':round(receipt['state']['reference_loss'],6),
                'calibration_thresholds':{k:round(v,6) for k,v in receipt['state']['thresholds'].items()},
                'conditions':rows})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=('development','additional'),default='development')
    p.add_argument('--out')
    a=p.parse_args()
    result=measure(DEV if a.cohort=='development' else AUDIT)
    text=json.dumps(result,sort_keys=True,indent=2)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(text)
    print(text,end='')

if __name__=='__main__':main()
