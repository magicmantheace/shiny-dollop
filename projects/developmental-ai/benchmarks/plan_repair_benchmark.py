"""Frozen A/B/A hidden-prerequisite changes without a public context label."""
from __future__ import annotations

import argparse
import json
from developmental_ai.plan_repair import RepairPlanMemory, RepairWorld, opaque_roles

SCHEMA = 'developmental-ai.plan-repair-benchmark/v1'
DEV = (34007, 34019, 34031)
ADDITIONAL = (56003, 56009, 56017)
START = 87000
EPISODES = 80
MODES = ('repair','latest','reactive','reset','role_order','oracle')


def trial(seed, index, agent, method):
    world=RepairWorld(seed,'test',index)
    roles=opaque_roles(seed)
    blocked=0
    while not world.done:
        frame=world.frame()
        if method == 'oracle':
            goal_role = world.name_to_role[world.goal]
            def needed(role):
                for dep in world._requirements.get(role, ()):
                    if world.role_to_name[dep] not in world.completed:
                        return needed(dep)
                return world.role_to_name[role]
            action=needed(goal_role)
        elif method == 'role_order':
            # ENGINEERED role ordering knows both candidate requirement families.
            order=[roles[i] for i in (0,1,3,2,6,4,5)]
            action=next(world.role_to_name[r] for r in order if world.role_to_name[r] not in world.completed)
        else:
            action=agent.propose(frame)
            if action is None:break
        outcome=world.step(action,expected_tick=frame['tick'])
        blocked+=not outcome['accepted']
        if agent is not None:
            agent.feedback(outcome)
    return {'success':world.goal in world.completed,'blocked':blocked,'attempts':world.tick,
            'stalled':not world.done,'phase':'B' if 20 <= ((index-START)%80) < 60 else 'A'}


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('evaluation cohorts are frozen')
    out={'schema':SCHEMA,'protocol':'benchmarks/plan_repair_protocol.json',
         'blind':False,'cohort':list(seeds),'episode_start':START,
         'episodes_per_seed':EPISODES,'phases':{'first_A':[0,20],'B':[20,60],'return_A':[60,80]},
         'rows':[]}
    for seed in seeds:
        agents={m:RepairPlanMemory(seed,mode=m) for m in ('repair','latest','reactive')}
        data={m:[] for m in MODES}
        for idx in range(START,START+EPISODES):
            for method in MODES:
                agent=(RepairPlanMemory(seed,mode='reset') if method=='reset' else agents.get(method))
                data[method].append(trial(seed,idx,agent,method))
        summaries={}
        for mode,record in data.items():
            summaries[mode]={
                'total_success':sum(r['success'] for r in record),
                'first_A':sum(r['success'] for r in record[:20]),
                'B':sum(r['success'] for r in record[20:60]),
                'return_A':sum(r['success'] for r in record[60:]),
                'mean_blocked':round(sum(r['blocked'] for r in record)/EPISODES,4),
                'mean_attempts':round(sum(r['attempts'] for r in record)/EPISODES,4),
                'stalled':sum(r['stalled'] for r in record)}
        artifact=agents['repair'].record()
        if RepairPlanMemory.restore(artifact).record()!=artifact:
            raise AssertionError('learner memory checkpoint did not replay')
        out['rows'].append({'seed':seed,'methods':summaries,
                            'successful_plan_variants':len(agents['repair'].plans),
                            'plan_lengths':[len(p) for p in agents['repair'].plans],
                            'memory_sha256':artifact['sha256']})
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cohort',choices=('development','additional'),default='development')
    p.add_argument('--out')
    args=p.parse_args()
    x=measure(DEV if args.cohort=='development' else ADDITIONAL)
    s=json.dumps(x,indent=2,sort_keys=True)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(s,encoding='utf8')
    print(s,end='')

if __name__=='__main__':main()
