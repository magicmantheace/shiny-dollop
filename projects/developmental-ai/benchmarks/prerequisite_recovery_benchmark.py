"""Post-hoc V2 recovery study; original frozen prober benchmark unchanged.

The symbolic worlds share engineered glyph/fact semantics and these seeds are
already inspected. The V2 controller hands off to historical OutcomeSkills as
soon as an action effect not seen in its source prefix is learned.
"""
from __future__ import annotations
import argparse
import json
from developmental_ai.outcome_skills import OutcomeSkills
from developmental_ai.prerequisite_probing import PrerequisiteProber
from developmental_ai.prerequisite_recovery import RecoveryProber
from benchmarks.outcome_skills_benchmark import DEV, EXTRA, learn, run
from benchmarks.prerequisite_probing_benchmark import trial, summarize

SCHEMA = 'developmental-ai.prerequisite-recovery-benchmark/v1'
TRAIN_START = 130000
EVAL_START = 97000
STAGES = (0, 1, 2, 4, 8, 20)
EVAL_EPISODES = 30


def score(seed, family, learner, policy):
    if policy == 'legacy':
        return summarize([run(seed,family,'test',EVAL_START+i,learner)
                          for i in range(EVAL_EPISODES)])
    if policy == 'oracle':
        return summarize([run(seed,family,'test',EVAL_START+i,policy='oracle')
                          for i in range(EVAL_EPISODES)])
    return summarize([trial(seed,family,'test',EVAL_START+i,learner)
                      for i in range(EVAL_EPISODES)])


def measure(seeds=DEV):
    if type(seeds) not in (tuple,list) or tuple(seeds) not in (DEV,EXTRA):
        raise ValueError('fixed inspected development cohorts only')
    output = {'schema':SCHEMA, 'blind':False, 'post_hoc':True,
              'same_engineered_action_ontology':True,
              'target_training_indices':[TRAIN_START,TRAIN_START+STAGES[-1]-1],
              'test_indices':[EVAL_START,EVAL_START+EVAL_EPISODES-1],
              'stages':list(STAGES), 'rows':[]}
    for seed in seeds:
        source=learn(seed)
        source_saved=source.record()
        candidate=RecoveryProber.from_source(source)
        old_prober=PrerequisiteProber.from_source(source)
        legacy=OutcomeSkills.restore(source_saved)
        target_only=RecoveryProber(OutcomeSkills())
        curves=[]
        trained=0
        for episodes in STAGES:
            for i in range(trained,episodes):
                idx=TRAIN_START+i
                trial(seed,'delivery','train',idx,candidate,learning=True)
                trial(seed,'delivery','train',idx,old_prober,learning=True)
                trial(seed,'delivery','train',idx,target_only,learning=True)
                run(seed,'delivery','train',idx,legacy,'learned',True)
            trained=episodes
            snapshot=candidate.record()
            restored=RecoveryProber.restore(snapshot)
            if snapshot!=restored.record() or source.record()!=source_saved:
                raise AssertionError('learned/source memory not restart-exact')
            read_only=snapshot
            targets={
                'recovery':score(seed,'delivery',restored,'recovery'),
                'raw_probe':score(seed,'delivery',old_prober,'raw_probe'),
                'historical':score(seed,'delivery',legacy,'legacy'),
                'target_only':score(seed,'delivery',target_only,'recovery'),
                'frozen_source':score(seed,'delivery',source,'legacy'),
                'oracle':score(seed,'delivery',None,'oracle'),
            }
            retained={
                'recovery':score(seed,'assembly',restored,'recovery'),
                'raw_probe':score(seed,'assembly',old_prober,'raw_probe'),
                'historical':score(seed,'assembly',legacy,'legacy'),
                'frozen_source':score(seed,'assembly',source,'legacy'),
            }
            if restored.record()!=read_only:
                raise AssertionError('read-only test evaluation changed memory')
            curves.append({'target_training_episodes':episodes,
                           'target':targets,'retention':retained,
                           'new_glyphs':len(restored.memory.knowledge())-len(source.knowledge()),
                           'sha256':snapshot['sha256']})
        output['rows'].append({'seed':seed,'curves':curves})
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cohort',choices=('dev','additional'),default='dev')
    args=parser.parse_args()
    print(json.dumps(measure(DEV if args.cohort=='dev' else EXTRA),sort_keys=True,indent=2))


if __name__=='__main__':main()
