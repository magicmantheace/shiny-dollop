"""Precommitted hidden-prerequisite workshop/repair comparison.

Only the benchmark oracle reads hidden graph. The learner is workshop-only and
uses merely attempted actions, whether accepted, and public stable role tags.
"""
from __future__ import annotations
import argparse
import json
from developmental_ai.hidden_prerequisites import PreconditionSkill,run

SCHEMA='developmental-ai.hidden-prerequisite-benchmark/v1'
DEV=(14003,14009,14033)
ADDITIONAL=(27007,27011,27017)
TRAIN=360
TEST=80
START=81000
METHODS=('random','goal_first','role_order','learned','oracle')


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('evaluation cohort differs from frozen manifest')
    out={'schema':SCHEMA,'protocol':'benchmarks/hidden_prerequisite_protocol.json',
         'blind':False,'train':'workshop/train/0..359','test':'test/81000..81079',
         'train_episodes':TRAIN,'test_episodes_per_family_seed':TEST,'rows':[]}
    for seed in seeds:
        skill=PreconditionSkill.restore(PreconditionSkill(seed).train(TRAIN).record())
        row={'seed':seed,'learned_prerequisites':{r:sorted(v) for r,v in skill.prerequisites().items()},
             'checkpoint_sha256':skill.record()['sha256'],'families':{}}
        for family in ('workshop','repair'):
            sample={method:[run(seed,family,START+i,method,skill) for i in range(TEST)]
                    for method in METHODS}
            row['families'][family]={
                'successes':{m:sum(v['success'] for v in seq) for m,seq in sample.items()},
                'mean_attempts':{m:round(sum(v['attempts'] for v in seq)/TEST,3) for m,seq in sample.items()},
                'mean_blocked':{m:round(sum(v['blocked'] for v in seq)/TEST,3) for m,seq in sample.items()}}
        out['rows'].append(row)
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=('development','additional'),default='development')
    p.add_argument('--out');a=p.parse_args()
    data=json.dumps(measure(DEV if a.cohort=='development' else ADDITIONAL),indent=2,sort_keys=True)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(data,encoding='utf8')
    print(data,end='')

if __name__=='__main__':main()
