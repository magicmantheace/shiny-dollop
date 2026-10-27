"""Frozen alternating two-context hidden-graph plan replay experiment."""
from __future__ import annotations
import argparse
import json
from developmental_ai.context_plan_memory import ContextPlanMemory, NovelProcedure, labels

SCHEMA = 'developmental-ai.context-plan-benchmark/v1'
DEV = (14003,14009,14033)
ADDITIONAL = (27007,27011,27017)
START = 85000
EPISODES = 80


def trial(seed,index,agent,method):
    world=NovelProcedure(seed,'test',index)
    blocked=0
    steps=0
    oracle_roles=labels(seed)[0]
    plan=([oracle_roles[0],oracle_roles[1],oracle_roles[2],oracle_roles[6]] if index%2==0 else
          [oracle_roles[3],oracle_roles[4],oracle_roles[5],oracle_roles[6]])
    while not world.done:
        frame=world.frame()
        if method=='oracle':
            role=next(role for role in plan if world.names[role] not in world.completed)
            action=world.names[role]
        elif method=='lexical':
            action=min(frame['available_actions'],key=lambda a:frame['roles'][a])
        else:
            action=agent.propose(frame)
            if action is None:break
        result=world.step(action,expected_tick=frame['tick'])
        if agent is not None:agent.feedback(result)
        steps+=1;blocked+=not result['accepted']
    return {'success':world.goal in world.completed,'attempts':steps,'blocked':blocked,'stalled':not world.done,
            'context':world.context}


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('unapproved evaluation cohort')
    out={'schema':SCHEMA,'protocol':'benchmarks/context_plan_transfer_protocol.json',
         'blind':False,'split':'test','start':START,'episodes':EPISODES,'rows':[]}
    for seed in seeds:
        agents={m:ContextPlanMemory(seed,mode=m) for m in ('context','latest','reset')}
        trials={m:[] for m in ('context','latest','reset','lexical','oracle')}
        for index in range(START,START+EPISODES):
            for m in trials:
                if m=='reset':
                    agent=ContextPlanMemory(seed,mode=m) # no persistence across episodes
                else:agent=agents.get(m)
                trials[m].append(trial(seed,index,agent,m))
        result={}
        for m,records in trials.items():
            result[m]={'success':sum(r['success'] for r in records),
                       'cold20':sum(r['success'] for r in records[:20]),
                       'warm60':sum(r['success'] for r in records[20:]),
                       'by_context':{str(j):sum(r['success'] for r in records[j::2]) for j in range(2)},
                       'mean_blocked':round(sum(r['blocked'] for r in records)/EPISODES,4),
                       'mean_attempts':round(sum(r['attempts'] for r in records)/EPISODES,4),
                       'stalled':sum(r['stalled'] for r in records)}
        artifact=agents['context'].record()
        if ContextPlanMemory.restore(artifact).record()!=artifact:
            raise AssertionError('plan evidence did not replay')
        out['rows'].append({'seed':seed,'methods':result,
                            'learned_context_plans':{ctx:len(actions) for ctx,actions in agents['context'].plans.items()},
                            'plan_sha256':artifact['sha256']})
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cohort',choices=('development','additional'),default='development')
    p.add_argument('--out')
    args=p.parse_args()
    data=json.dumps(measure(DEV if args.cohort=='development' else ADDITIONAL),indent=2,sort_keys=True)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(data,encoding='utf8')
    print(data,end='')

if __name__=='__main__':main()
