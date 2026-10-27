"""Pre-frozen D3 reward-only cue alignment study (NOT paired or blind).

Training selector receives 5 cues and their opaque labels, then ONLY terminal
navigation success/failure. Benchmark synthesizes false cues from a PUBLIC
initial beacon but never passes this reference to the learner. Comparisons
include an equivalently trained direct contextual lookup, a context-blind
bandit, simple cue-order policies and a privileged reference oracle.
"""
from __future__ import annotations

import argparse
import json
import random

from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.learned_spatial_memory import PortableOffsetMemory, train_grid_updates
from developmental_ai.occluded_navigation import greedy_action
from developmental_ai.reward_aliases import RewardAliasLearner, FIRST_INDEX
from benchmarks.grounded_aliases_benchmark import stream

SCHEMA='developmental-ai.reward-only-alignment-benchmark/v1'
DEVELOPMENT=(2749,6607,9901)
ADDITIONAL=(17431,24869,37021)
TRAIN_EPISODES=360
TEST_EPISODES=40
TEST_START=98000


def navigate(seed,index,updater,selected,*,split):
    world=EnvironmentSession('occluded',seed,split,index)
    mem=PortableOffsetMemory(updater)
    rng=random.Random(seed*100000+index)
    terminal=None
    while not world.done:
        frame=world.frame()
        if frame['tick']==0:
            frame={**frame,'observation':{**frame['observation'],'beacon':list(selected)}}
        action=greedy_action(mem.features(frame),rng)
        result=world.step(action,expected_tick=frame['tick'])
        mem.feedback(action,result)
        terminal=result['event']
    return terminal=='collected'


def train(seed,updater,*,blind=False,episodes=TRAIN_EPISODES):
    learner=RewardAliasLearner(seed,ignore_context=blind)
    successes=0
    for i in range(episodes):
        index=FIRST_INDEX+i
        # Public reference is accessed solely by the benchmark generator.
        world=EnvironmentSession('occluded',seed,'train',index)
        beacon=list(world.frame()['observation']['beacon'])
        sample=stream(seed,index,beacon)
        chosen=learner.propose(sample['context'],sample['cues'],split='train',index=index)
        success=navigate(seed,index,updater,chosen,split='train')
        learner.feedback(success,split='train',index=index)
        successes+=success
    return RewardAliasLearner.restore(learner.record()), successes


def measure(seeds=DEVELOPMENT,*,episodes=TEST_EPISODES,training=TRAIN_EPISODES):
    if (type(seeds) not in (tuple,list) or tuple(seeds) not in (DEVELOPMENT,ADDITIONAL) or
            type(episodes) is not int or episodes!=TEST_EPISODES or
            type(training) is not int or training!=TRAIN_EPISODES):
        raise ValueError('benchmark schedule is frozen; do not change for post-hoc tuning')
    result={'schema':SCHEMA,'blind':False,
            'precommitted_protocol':'benchmarks/reward_only_alignment_protocol.json',
            'train_target_episodes':TRAIN_EPISODES,'test_target_episodes':TEST_EPISODES,
            'train_namespace':'train/78000..78359','test_namespace':'test/98000..98039',
            'reward_is_terminal_success_only':True,'paired_reference_to_learner':False,'rows':[]}
    for seed in seeds:
        updater=train_grid_updates(seed,24)
        learned,train_success=train(seed,updater)
        no_context,blind_train_success=train(seed,updater,blind=True)
        scores={m:0 for m in ('reward_only','direct_lookup','context_blind','first','last','random','oracle')}
        chosen_correct={m:0 for m in scores}
        for i in range(TEST_EPISODES):
            index=TEST_START+i
            world=EnvironmentSession('occluded',seed,'test',index)
            ref=list(world.frame()['observation']['beacon'])
            sample=stream(seed,index,ref)
            cues=sample['cues'];context=sample['context']
            rng=random.Random(seed*31+index)
            learned_source=learned.best_source(context,cues)
            selections={
                'reward_only':learned.predict(context,cues),
                'direct_lookup':next(list(c[2]) for c in cues if c[0]==learned_source),
                'context_blind':no_context.predict(context,cues),
                'first':list(cues[0][2]),'last':list(cues[-1][2]),
                'random':list(cues[rng.randrange(5)][2]),'oracle':ref,
            }
            for mode,selected in selections.items():
                chosen_correct[mode]+=selected==ref
                scores[mode]+=navigate(seed,index,updater,selected,split='test')
        result['rows'].append({'seed':seed,'train_success_reward_only':train_success,
                'train_success_context_blind':blind_train_success,
                'scores':scores,'chosen_cue_matches_public_reference_scoring_only':chosen_correct,
                'record_digest':learned.record()['digest'],
                'source_selection':{c:learned.best_source(c,stream(seed,TEST_START,[1,2])['cues'])
                                    for c in sorted(learned.contexts)}})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cohort',choices=('development','additional'),default='development')
    p.add_argument('--out')
    args=p.parse_args()
    seeds=DEVELOPMENT if args.cohort=='development' else ADDITIONAL
    result=json.dumps(measure(seeds),indent=2,sort_keys=True)+'\n'
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(result)
    print(result,end='')

if __name__=='__main__':main()
