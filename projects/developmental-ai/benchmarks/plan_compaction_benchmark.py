"""Precommitted follow-up: outcome-only ablation of successful procedural plans."""
from __future__ import annotations
import argparse
import json
from developmental_ai.plan_compaction import CompactionMemory
from developmental_ai.plan_repair import RepairPlanMemory
from benchmarks.plan_repair_benchmark import trial, DEV, ADDITIONAL, START, EPISODES

SCHEMA = 'developmental-ai.plan-compaction-benchmark/v1'
MODES = ('compaction','cached_repair','reactive','role_order','oracle')


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('evaluation cohort is frozen')
    output={'schema':SCHEMA,'protocol':'benchmarks/plan_compaction_protocol.json',
            'blind':False,'split':'test','start':START,'episodes_per_seed':EPISODES,'rows':[]}
    for seed in seeds:
        agents={'compaction':CompactionMemory(seed),
                'cached_repair':RepairPlanMemory(seed,mode='repair'),
                'reactive':RepairPlanMemory(seed,mode='reactive')}
        outcomes={m:[] for m in MODES}
        for index in range(START,START+EPISODES):
            for mode in MODES:
                outcomes[mode].append(trial(seed,index,agents.get(mode),
                                            'repair' if mode=='compaction' else mode))
        scores={}
        for mode,records in outcomes.items():
            scores[mode]={'success':sum(r['success'] for r in records),
                 'first_A':sum(r['success'] for r in records[:20]),
                 'B':sum(r['success'] for r in records[20:60]),
                 'return_A':sum(r['success'] for r in records[60:]),
                 'mean_attempts':round(sum(r['attempts'] for r in records)/EPISODES,4),
                 'mean_blocked':round(sum(r['blocked'] for r in records)/EPISODES,4)}
        model=agents['compaction'];record=model.record()
        if CompactionMemory.restore(record).record()!=record:
            raise AssertionError('compaction cannot replay its history')
        output['rows'].append({'seed':seed,'methods':scores,
                 'stored_plan_lengths':[len(p) for p in model.plans],
                 'omission_trials':len(model.probe_outcomes),
                 'successful_omission_trials':sum(e['improved'] for e in model.probe_outcomes),
                 'checkpoint_sha256':record['sha256']})
    return output


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cohort',choices=('development','additional'),default='development')
    ap.add_argument('--out')
    opt=ap.parse_args()
    value=measure(DEV if opt.cohort=='development' else ADDITIONAL)
    content=json.dumps(value,sort_keys=True,indent=2)+'\n'
    if opt.out:
        from pathlib import Path
        Path(opt.out).write_text(content,encoding='utf8')
    print(content,end='')

if __name__=='__main__':main()
