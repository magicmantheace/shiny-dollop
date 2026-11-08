"""Precommitted A->B->A outcome-driven memory benchmark, no stage input to model."""
from __future__ import annotations
import argparse
import json
from benchmarks.event_segmentation_benchmark import episode, DEVELOPMENT, ADDITIONAL
from benchmarks.outcome_event_memory_benchmark import preference, context, score
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.nonstationary_event_value import ChangingEventMemory, MODES, BOOTSTRAP

SCHEMA='developmental-ai.nonstationary-event-value-benchmark/v1'
MODES_EVALUATE = MODES + ('available_oracle',)


def alternate(pref):
    return {ctx:(label+2)%4 for ctx,label in pref.items()}


def reward(model, trial, ctx, target, step):
    selection=model.propose(ctx,trial['observed'],split='train',step=step)
    succeeded=score(selection,trial,target[ctx])
    model.feedback(succeeded,split='train',step=step)
    return int(succeeded)


def measure(seeds=DEVELOPMENT):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT, ADDITIONAL):
        raise ValueError('unfrozen evaluation cohort')
    out={'schema':SCHEMA, 'protocol':'benchmarks/nonstationary_event_value_protocol.json',
         'blind':False,'initial':'source_bursts/train/2000..2199',
         'adaptation':'shifted_bursts/train/6000..6119 then 6200..6319',
         'evaluation':'shifted_bursts/test/95000+,95100+,95200+; no feedback updates','rows':[]}
    for seed in seeds:
        train=[episode(seed,'source_bursts','train',i)['observed'] for i in range(160)]
        segmenter=fit_event_model(train)
        models={mode:ChangingEventMemory(segmenter,seed,mode=mode) for mode in MODES}
        target_A=preference(seed)
        target_B=alternate(target_A)
        train_scores={mode:{'A':0,'B':0,'return_A':0} for mode in MODES}
        prequential={mode:{'B':[],'return_A':[]} for mode in MODES}
        row={'seed':seed,'families':{},'adaptation_rewards':train_scores}
        for i in range(BOOTSTRAP):
            index=2000+i
            t=episode(seed,'source_bursts','train',index)
            ctx=context(seed,'train',index)
            for mode,model in models.items():
                train_scores[mode]['A']+=reward(model,t,ctx,target_A,i)
        for stage,target,start,offset in [('A',target_A,95000,0),('B',target_B,95100,6000),('return_A',target_A,95200,6200)]:
            if stage!='A':
                for i in range(120):
                    index=offset+i
                    t=episode(seed,'shifted_bursts','train',index)
                    ctx=context(seed,'train',index)
                    for mode,model in models.items():
                        result=reward(model,t,ctx,target,BOOTSTRAP+(i if stage=='B' else 120+i))
                        train_scores[mode][stage]+=result
                        prequential[mode][stage].append(result)
            scores={name:0 for name in MODES_EVALUATE}
            for j in range(40):
                idx=start+j
                t=episode(seed,'shifted_bursts','test',idx)
                ctx=context(seed,'test',idx)
                for mode,m in models.items():
                    sel=m.choose(ctx,t['observed'])
                    scores[mode]+=int(score(sel,t,target[ctx]))
                scores['available_oracle']+=int(target[ctx] in t['hidden'])
            row['families'][stage]={'successes':scores, 'episodes':40,
                'archive_active':models['archive'].active,
                'archive_switches':len(models['archive'].switches)}
        row['adaptation_first_20_rewards']={mode:{stage:sum(prequential[mode][stage][:20]) for stage in ('B','return_A')} for mode in MODES}
        row['return_to_anchor_delay'] = next((e['step']-320 for e in models['archive'].switches if e['step'] >= 320 and e['to']=='anchor'), None)
        row['checkpoints']={name:ChangingEventMemory.restore(m.record(),segmenter).record()['sha256'] for name,m in models.items()}
        row['archive_switch_details']=models['archive'].switches
        out['rows'].append(row)
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cohort', choices=('development','additional'), default='development')
    ap.add_argument('--out')
    args=ap.parse_args()
    d=measure(DEVELOPMENT if args.cohort=='development' else ADDITIONAL)
    s=json.dumps(d,sort_keys=True,indent=2)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(s)
    print(s,end='')

if __name__=='__main__':main()
