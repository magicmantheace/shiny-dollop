"""Optional observed-outcome probe: scoped deterministic regression tests."""
from __future__ import annotations

import copy
import unittest
from developmental_ai.outcome_skills import OutcomeSkills, digest
from developmental_ai.prerequisite_probing import PrerequisiteProber, constraints
from benchmarks.outcome_skills_benchmark import SkillWorld, learn, run
from benchmarks.prerequisite_probing_benchmark import (
    trial, measure, DEV, EXTRA, TRAIN_START, EVAL_START, VALIDATION_START
)


class PrerequisiteProbeTests(unittest.TestCase):
    def test_single_fact_failed_then_success_is_only_observational_evidence(self):
        m = OutcomeSkills()
        m.observe('smelt', [], [], False)
        m.observe('smelt', ['ore'], ['ingot', 'ore'], True)
        record = constraints(m)['smelt']
        self.assertEqual(record['single_fact_differences'], ['ore'])
        self.assertEqual(record['successes'], 1)
        self.assertEqual(record['failures'], 1)
        self.assertEqual(record['uncertainty'], 'observational')

    def test_multiple_difference_not_elevated_to_observed_requirement(self):
        m = OutcomeSkills()
        m.observe('smelt', [], [], False)
        m.observe('smelt', ['ore','wood'], ['ingot','ore','wood'], True)
        record = constraints(m)['smelt']
        self.assertEqual(record['single_fact_differences'], [])
        self.assertEqual(record['possible_prerequisites'], ['ore','wood'])
        self.assertEqual(record['uncertainty'], 'confounded')

    def test_blocked_only_has_explicit_unknown_uncertainty(self):
        m = OutcomeSkills()
        m.observe('package', [], [], False)
        self.assertEqual(constraints(m)['package']['uncertainty'], 'no-success')
        self.assertNotIn('package', m.knowledge())

    def test_source_skill_memory_not_mutated_by_eval(self):
        s = learn(17011)
        p = PrerequisiteProber.from_source(s)
        source_record = copy.deepcopy(s.record())
        probe_record = copy.deepcopy(p.record())
        trial(17011, 'assembly', 'test', EVAL_START, p)
        self.assertEqual(s.record(), source_record)
        self.assertEqual(p.record(), probe_record)

    def test_restart_exact_and_checksum_tampering_rejected(self):
        p = PrerequisiteProber.from_source(learn(17011))
        trial(17011, 'delivery', 'train', TRAIN_START, p, learning=True)
        record = p.record()
        restarted = PrerequisiteProber.restore(copy.deepcopy(record))
        self.assertEqual(restarted.record(),record)
        self.assertEqual(trial(17011,'delivery','test',EVAL_START,p),
                         trial(17011,'delivery','test',EVAL_START,restarted))
        tampered = copy.deepcopy(record)
        tampered['state']['knowledge']['smelt']['effects']['ingot'] += 1
        tampered['sha256'] = digest(tampered['state'])
        with self.assertRaises(ValueError): PrerequisiteProber.restore(tampered)

    def test_reject_privileged_frame(self):
        p = PrerequisiteProber.from_source(learn(17011))
        frame = SkillWorld(17011, 'assembly', 'test', EVAL_START).frame()
        frame['requirements'] = {'assemble': ['ingot','plank']}
        with self.assertRaises(ValueError): p.choose(frame)

    def test_reject_forged_failed_context(self):
        p = PrerequisiteProber.from_source(learn(17011))
        frame = SkillWorld(17011,'delivery','test',EVAL_START).frame()
        action = frame['actions'][0]['id']
        for payload in ({'non-action':[]}, {action:['secret']}, {action:[1]},
                        {action:['b','a']}, []):
            with self.assertRaises(ValueError):p.choose(frame, payload)

    def test_initial_assembly_success_and_delivery_baseline_not_overwritten(self):
        p = PrerequisiteProber.from_source(learn(17011))
        assembly = trial(17011, 'assembly', 'test', EVAL_START, p)
        self.assertTrue(assembly['success'])
        self.assertFalse(run(17011,'delivery','test',EVAL_START,learn(17011))['success'])

    def test_target_learning_regression_is_not_hidden(self):
        p = PrerequisiteProber.from_source(learn(17011))
        for i in range(20):
            trial(17011, 'delivery', 'train', TRAIN_START+i, p, learning=True)
        self.assertFalse(trial(17011,'delivery','test',EVAL_START,p)['success'])
        self.assertTrue(run(17011,'delivery','test',EVAL_START,policy='oracle')['success'])

    def test_cohorts_cannot_be_silently_relabelled(self):
        with self.assertRaises(ValueError):measure((DEV[0],))
        with self.assertRaises(ValueError):measure(tuple(reversed(EXTRA)))

    def test_protocol_uses_disjoint_train_validation_and_test_ranges(self):
        self.assertGreater(VALIDATION_START, TRAIN_START+20)
        self.assertNotEqual(VALIDATION_START,EVAL_START)


if __name__ == '__main__': unittest.main()
