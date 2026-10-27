"""Precommitted A-B-A-B-A-A-control event-reward reversal protocol.

Learner never receives hidden phase, label, environment regime or alternatives.
The simulator uses hidden truth strictly for scoring selected event centers.
"""
from __future__ import annotations
import argparse
import json
from benchmarks.event_segmentation_benchmark import episode,DEVELOPMENT,ADDITIONAL
from benchmarks.outcome_event_memory_benchmark import preference,context,score
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.repeated_reversal import RepeatedReversalMemory, MODES, BOOTSTRAP

SCHEMA='developmental-ai.repeated-reversal-benchmark/v1'
PHASES=('A','B','A','B','A','A_control')
STEPS=80
TEST=40

def alternate(mapping):
    return {key:(value+2)%4 for key,value in mapping.items()}

def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,ADDITIONAL):
        raise ValueError('evaluation cohort locked')
    result={'schema':SCHEMA,'protocol':'benchmarks/repeated_reversal_schedule.json',
            'blind':False,'stages':list(PHASES),'train_per_stage':STEPS,
            'eval_per_seed_stage':TEST,'training':'train/2000..2199 bootstrap; shifted train/7000+ per stage',
            'evaluation':'shifted/test/96000 + 100*stage + 0..39; read-only',
            'rows':[]}
    for seed in seeds:
        segmenter=fit_event_model([episode(seed,'source_bursts','train',i)['observed'] for i in range(160)])
        models={m:RepeatedReversalMemory(segmenter,seed,mode=m) for m in MODES}
        original=preference(seed);changed=alternate(original)
        rewards={m:0 for m in MODES}
        for j in range(BOOTSTRAP):
            ix=2000+j
            trial=episode(seed,'source_bursts','train',ix)
            ctx=context(seed,'train',ix)
            for mode,mem in models.items():
                choice=mem.propose(ctx,trial['observed'],split='train',index=j)
                ok=score(choice,trial,original[ctx]);mem.feedback(ok,split='train',index=j)
                rewards[mode]+=int(ok)
        per_phase=[]
        for k,phase in enumerate(PHASES):
            actual=changed if phase=='B' else original
            online={m:0 for m in MODES}
            early={m:0 for m in MODES}
            for j in range(STEPS):
                ix=7000+k*100+j
                trial=episode(seed,'shifted_bursts','train',ix)
                ctx=context(seed,'train',ix)
                for mode,mem in models.items():
                    selected=mem.propose(ctx,trial['observed'],split='train',index=BOOTSTRAP+k*STEPS+j)
                    outcome=score(selected,trial,actual[ctx]);mem.feedback(outcome,split='train',index=BOOTSTRAP+k*STEPS+j)
                    online[mode]+=int(outcome)
                    if j<20:early[mode]+=int(outcome)
            successes={m:0 for m in MODES};successes['available_oracle']=0
            anchors=0
            for j in range(TEST):
                ix=96000+k*100+j
                trial=episode(seed,'shifted_bursts','test',ix)
                ctx=context(seed,'test',ix)
                for mode,mem in models.items():
                    picked=mem.choose(ctx,trial['observed'])
                    successes[mode]+=int(score(picked['selection'],trial,actual[ctx]))
                    if mode=='archive_recall' and picked['source']=='anchor':anchors+=1
                successes['available_oracle']+=int(actual[ctx] in trial['hidden'])
            per_phase.append({'phase':phase,'successes':successes,'online_reward':online,
                              'first_20_online':early,'archive_anchor_choices':anchors})
        for mem in models.values():
            if RepeatedReversalMemory.restore(mem.record(),segmenter).record()!=mem.record():
                raise ValueError('restart equivalence failed')
        result['rows'].append({'seed':seed,'bootstrap_success':rewards,'phases':per_phase,
                               'checkpoint_digests':{m:mem.record()['sha256'] for m,mem in models.items()}})
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=('development','additional'),default='development')
    p.add_argument('--out')
    a=p.parse_args()
    d=measure(DEVELOPMENT if a.cohort=='development' else ADDITIONAL)
    output=json.dumps(d,indent=2,sort_keys=True)+'\n'
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(output,encoding='utf8')
    print(output,end='')

if __name__=='__main__':main()
