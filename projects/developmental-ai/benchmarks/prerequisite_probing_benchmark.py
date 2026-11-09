"""Post-hoc development study: observable blocked-action evidence and skill reuse.

This uses the same manually designed symbolic ontology as earlier studies.
Even changed opaque action IDs do NOT make this independent cross-family transfer.
"""
from __future__ import annotations

import argparse
import json
from developmental_ai.outcome_skills import OutcomeSkills
from developmental_ai.prerequisite_probing import PrerequisiteProber, constraints
from benchmarks.outcome_skills_benchmark import (
    DEV, EXTRA, SkillWorld, learn, run, GOAL,
)

SCHEMA = 'developmental-ai.prerequisite-probing-benchmark/v1'
TRAIN_START = 130000
EVAL_START = 97000
STAGES = (0, 1, 2, 4, 8, 20)
EVAL_EPISODES = 30
VALIDATION_START = 230000
VALIDATION_EPISODES = 16


def trial(seed, family, split, index, prober, *, learning=False):
    """No hidden recipe/goal rule information is read by the prober."""
    world = SkillWorld(seed, family, split, index)
    blocked_at = {}
    blocked_count = 0
    while not world.done:
        before = world.frame()
        action = prober.choose(before, blocked_at)
        if action is None:
            break
        after = world.step(action, before['tick'])
        glyph = next(a['glyph'] for a in before['actions'] if a['id'] == action)
        if learning:
            prober.observe(glyph, before['facts'], after['frame']['facts'], after['accepted'])
        if after['accepted']:
            blocked_at.pop(action, None)
        else:
            blocked_count += 1
            blocked_at[action] = list(before['facts'])
    return {'success': GOAL[family] in world.completed,
            'attempts': world.tick, 'stalled': not world.done,
            'blocked': blocked_count}


def summarize(rows):
    return {'success': sum(int(r['success']) for r in rows),
            'episodes': len(rows),
            'mean_attempts': round(sum(r['attempts'] for r in rows)/len(rows), 3),
            'stalled': sum(int(r.get('stalled', False)) for r in rows)}


def measure(seeds=DEV):
    if type(seeds) not in (tuple, list) or tuple(seeds) not in (DEV, EXTRA):
        raise ValueError('only previously inspected development cohorts')
    output = {'schema': SCHEMA, 'blind': False, 'shared_engineered_ontology': True,
              'post_hoc': True, 'training_indices': [TRAIN_START, TRAIN_START+STAGES[-1]-1],
              'test_indices': [EVAL_START, EVAL_START+EVAL_EPISODES-1],
              'validation_indices': [VALIDATION_START, VALIDATION_START+VALIDATION_EPISODES-1],
              'stages': list(STAGES), 'rows': []}
    for seed in seeds:
        source = learn(seed)
        source_record = source.record()
        probe = PrerequisiteProber.from_source(source)
        target_only = PrerequisiteProber(OutcomeSkills())
        legacy = OutcomeSkills.restore(source_record)
        curves = []
        current = 0
        for target_train in STAGES:
            for offset in range(current, target_train):
                index = TRAIN_START + offset
                trial(seed, 'delivery', 'train', index, probe, learning=True)
                trial(seed, 'delivery', 'train', index, target_only, learning=True)
                run(seed, 'delivery', 'train', index, legacy, 'learned', True)
            current = target_train
            if source.record() != source_record:
                raise AssertionError('frozen source changed')
            probe_record = probe.record()
            restored = PrerequisiteProber.restore(probe_record)
            if restored.record() != probe_record:
                raise AssertionError('checkpoint failed exact replay')
            evaluation_record = restored.record()
            # Controller selection uses train-namespace evaluation ONLY.
            # Ties and retention regressions choose the historical controller.
            new_valid = summarize([trial(seed,'delivery','train',VALIDATION_START+i,
                                          restored) for i in range(VALIDATION_EPISODES)])
            old_valid = summarize([run(seed,'delivery','train',VALIDATION_START+i,
                                        legacy) for i in range(VALIDATION_EPISODES)])
            new_retain = summarize([trial(seed,'assembly','train',VALIDATION_START+i,
                                           restored) for i in range(VALIDATION_EPISODES)])
            old_retain = summarize([run(seed,'assembly','train',VALIDATION_START+i,
                                         legacy) for i in range(VALIDATION_EPISODES)])
            gate_prober = (new_valid['success'] > old_valid['success'] and
                           new_retain['success'] >= old_retain['success'])
            evaluation_mode = 'probe' if gate_prober else 'legacy'
            target = {
                'probe': summarize([trial(seed,'delivery','test',EVAL_START+i,restored)
                                    for i in range(EVAL_EPISODES)]),
                'legacy': summarize([run(seed,'delivery','test',EVAL_START+i,legacy)
                                     for i in range(EVAL_EPISODES)]),
                'target_only_probe': summarize([trial(seed,'delivery','test',EVAL_START+i,
                                                      target_only)
                                                for i in range(EVAL_EPISODES)]),
                'frozen_source': summarize([run(seed,'delivery','test',EVAL_START+i,source)
                                             for i in range(EVAL_EPISODES)]),
                'oracle': summarize([run(seed,'delivery','test',EVAL_START+i,
                                          policy='oracle')
                                     for i in range(EVAL_EPISODES)]),
            }
            target['train_validation_gate'] = {
                'chosen': evaluation_mode, 'probe_success': new_valid['success'],
                'legacy_success': old_valid['success'],
                'probe_retention': new_retain['success'],
                'legacy_retention': old_retain['success'],
            }
            target['validated_controller'] = (target['probe'] if gate_prober
                                               else target['legacy'])
            retention = {
                'probe': summarize([trial(seed,'assembly','test',EVAL_START+i,restored)
                                     for i in range(EVAL_EPISODES)]),
                'legacy': summarize([run(seed,'assembly','test',EVAL_START+i,legacy)
                                      for i in range(EVAL_EPISODES)]),
                'source': summarize([run(seed,'assembly','test',EVAL_START+i,source)
                                      for i in range(EVAL_EPISODES)]),
            }
            retention['validated_controller'] = (retention['probe'] if gate_prober
                                                 else retention['legacy'])
            if restored.record() != evaluation_record:
                raise AssertionError('read-only evaluation mutated learned memory')
            curves.append({'target_train_episodes':target_train, 'target':target,
                           'retention':retention,
                           'known_glyphs':len(restored.memory.knowledge()),
                           'learned_failed_contexts':sum(x['failures'] for x in constraints(restored.memory).values()),
                           'checkpoint_sha256':probe_record['sha256']})
        output['rows'].append({'seed':seed,'curves':curves})
    return output


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cohort',choices=('dev','additional'),default='dev')
    args=p.parse_args()
    print(json.dumps(measure(DEV if args.cohort=='dev' else EXTRA),indent=2,sort_keys=True))


if __name__ == '__main__':
    main()
