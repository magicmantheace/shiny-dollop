"""Frozen workshop-to-repair action-skill reuse comparison, no target learning."""
from __future__ import annotations
import argparse
import json
from developmental_ai.procedural_skill import (ProceduralWorld,ProceduralSkill,ancestor_closure,
                                                   _random,MAX_STEPS)
SCHEMA="developmental-ai.procedural-skill-benchmark/v1"
DEV=(14003,14009,14033)
ADDITIONAL=(27007,27011,27017)
TRAIN=600
TEST=100
START=70000


def evaluate_one(seed,family,index,mode,learned=None,ablated=None):
    world=ProceduralWorld(seed,family,'test',index)
    rng=_random(seed,family,'test',index,'evaluation-random')
    wasted=0
    while not world.done:
        f=world.frame();options=f['available_actions'];lineage=ancestor_closure(f['prerequisites'],f['goal'])
        if mode=='random':choice=rng.choice(options)
        elif mode in ('greedy','oracle'):
            # Oracle uses an entire public graph, but does not access hidden outcomes.
            choice=next(k for k in options if k in lineage)
        elif mode=='learned':choice=learned.choose(f)
        elif mode=='feature_ablation':choice=ablated.choose(f)
        else:raise ValueError('invalid mode')
        wasted+=int(choice not in lineage)
        world.step(choice,expected_tick=f['tick'])
    return {'success':world.goal in world.completed,'wasted':wasted,'steps':world.tick}


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError('not a frozen evaluation cohort')
    modes=('random','greedy','oracle','learned','feature_ablation')
    output={'schema':SCHEMA,'protocol':'benchmarks/procedural_skill_protocol.json',
            'blind':False,'training_family':'workshop','training_split':'train/0..599',
            'evaluation_split':'test/70000..70099','episodes_per_seed_family':TEST,
            'no_target_reward_fit':True,'rows':[]}
    for seed in seeds:
        learned=ProceduralSkill(seed).train(TRAIN)
        ablated=ProceduralSkill(seed,use_ancestor=False).train(TRAIN)
        learned=ProceduralSkill.restore(learned.record())
        ablated=ProceduralSkill.restore(ablated.record())
        record={'seed':seed,'learned_sha256':learned.record()['sha256'],
                'ablation_sha256':ablated.record()['sha256'],'training_table':learned.record()['state']['weights'],
                'families':{}}
        for family in ('workshop','repair'):
            outcomes={mode:[evaluate_one(seed,family,START+i,mode,learned,ablated) for i in range(TEST)] for mode in modes}
            record['families'][family]={'success':{m:sum(x['success'] for x in seq) for m,seq in outcomes.items()},
                'wasted':{m:sum(x['wasted'] for x in seq) for m,seq in outcomes.items()},
                'mean_steps':{m:round(sum(x['steps'] for x in seq)/TEST,3) for m,seq in outcomes.items()}}
        output['rows'].append(record)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort',choices=('development','additional'),default='development')
    parser.add_argument('--out')
    args=parser.parse_args()
    result=measure(DEV if args.cohort=='development' else ADDITIONAL)
    data=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(data,encoding='utf-8')
    print(data,end='')
if __name__=='__main__':main()
