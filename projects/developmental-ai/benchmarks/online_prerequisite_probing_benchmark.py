"""Frozen D3/D4 online target-task action-probing evaluation with matched controls."""
from __future__ import annotations
import argparse
import json
from developmental_ai.hidden_prerequisites import (
    HiddenProcedure, PreconditionSkill, _rng, _choose, run,
)
from developmental_ai.online_prerequisite_probing import OnlinePrerequisiteAgent

SCHEMA = 'developmental-ai.online-prerequisite-probing-benchmark/v1'
DEV = (14003,14009,14033)
ADDITIONAL = (27007,27011,27017)
FAMILIES = ('workshop','repair')
START = 83000
EPISODES = 80
COLD = 20


def online_trial(agent, seed, family, index):
    world=HiddenProcedure(seed,family,'test',index)
    attempts=0; blocked=0
    while not world.done:
        frame=world.frame()
        action=agent.propose(frame)
        if action is None: break
        result=world.step(action,expected_tick=frame['tick'])
        agent.feedback(result)
        attempts+=1; blocked+=not result['accepted']
    return {'success':world.role_to_name[world.goal_role] in world.completed,
            'attempts':attempts,'blocked':blocked,'stalled':not world.done}


def untried_trial(seed,family,index):
    world=HiddenProcedure(seed,family,'test',index)
    rng=_rng(seed,family,'test',index,'random-eval')
    blocked={};attempts=0;count=0
    while not world.done:
        frame=world.frame()
        if attempts==0:action=frame['goal']
        else:
            fresh=[a for a in frame['available_actions'] if a not in blocked or blocked[a]<len(frame['completed'])]
            if not fresh:break
            action=rng.choice(fresh)
        outcome=world.step(action,expected_tick=frame['tick'])
        attempts+=1;count+=not outcome['accepted']
        if not outcome['accepted']: blocked[action]=len(frame['completed'])
    return {'success':world.role_to_name[world.goal_role] in world.completed,
            'attempts':attempts,'blocked':count,'stalled':not world.done}


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('cohort must match precommitted protocol')
    out={'schema':SCHEMA,'protocol':'benchmarks/online_prerequisite_probing_protocol.json',
         'independent_blind':False,'first_index':START,'episodes_per_seed_family':EPISODES,
         'cold_episodes':COLD,'rows':[]}
    for seed in seeds:
        workshop=PreconditionSkill(seed).train(360)
        for family in FAMILIES:
            agent=OnlinePrerequisiteAgent(seed)
            trials={k:[] for k in ('online','random','goal_first','role_order','workshop_static','oracle','goal_then_untried')}
            for index in range(START,START+EPISODES):
                trials['online'].append(online_trial(agent,seed,family,index))
                for name in ('random','goal_first','role_order','oracle'):
                    trials[name].append(run(seed,family,index,name))
                trials['workshop_static'].append(run(seed,family,index,'learned',workshop))
                trials['goal_then_untried'].append(untried_trial(seed,family,index))
            per_method={}
            for name,values in trials.items():
                per_method[name]={'total_success':sum(v['success'] for v in values),
                    'cold_success':sum(v['success'] for v in values[:COLD]),
                    'warm_success':sum(v['success'] for v in values[COLD:]),
                    'mean_attempts':round(sum(v['attempts'] for v in values)/EPISODES,3),
                    'mean_blocked':round(sum(v['blocked'] for v in values)/EPISODES,3),
                    'stalled':sum(v.get('stalled',False) for v in values)}
            record=agent.record()
            if OnlinePrerequisiteAgent.restore(record).record()!=record:
                raise AssertionError('online checkpoint failed exact replay')
            out['rows'].append({'seed':seed,'family':family,'methods':per_method,
                'checkpoint_sha256':record['sha256'], 'evidence_events':len(agent.events)})
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort',choices=('development','additional'),default='development')
    ap.add_argument('--out')
    args=ap.parse_args()
    result=measure(DEV if args.cohort=='development' else ADDITIONAL)
    data=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(data,encoding='utf8')
    print(data,end='')

if __name__=='__main__':main()
