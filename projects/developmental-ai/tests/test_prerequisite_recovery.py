"""Observational recovery research: no blind-generalization claims."""
from __future__ import annotations
import copy
import unittest
from developmental_ai.outcome_skills import OutcomeSkills, digest
from developmental_ai.prerequisite_recovery import RecoveryProber
from developmental_ai.prerequisite_probing import PrerequisiteProber
from benchmarks.outcome_skills_benchmark import SkillWorld, learn
from benchmarks.prerequisite_probing_benchmark import trial
from benchmarks.prerequisite_recovery_benchmark import (
    DEV, EXTRA, TRAIN_START, EVAL_START, STAGES, measure,
)


class RecoveryTests(unittest.TestCase):
    def test_initial_targeted_exploration_and_source_assembly(self):
        p=RecoveryProber.from_source(learn(DEV[0]))
        self.assertTrue(trial(DEV[0],'assembly','test',EVAL_START,p)['success'])
        self.assertFalse(set(p.memory.knowledge())-p._source_glyphs)
        frame=SkillWorld(DEV[0],'delivery','test',EVAL_START).frame()
        self.assertEqual(p.choose(frame),frame['goal'])

    def test_after_training_returns_to_original_controller(self):
        source=learn(DEV[0]);p=RecoveryProber.from_source(source)
        trial(DEV[0],'delivery','train',TRAIN_START,p,learning=True)
        self.assertTrue(set(p.memory.knowledge())-p._source_glyphs)
        frame=SkillWorld(DEV[0],'delivery','test',EVAL_START).frame()
        self.assertEqual(p.choose(frame),p.memory.choose(frame,set()))
        self.assertEqual(source.record(),learn(DEV[0]).record())

    def test_retained_skill_and_target_after_limited_adaptation(self):
        p=RecoveryProber.from_source(learn(DEV[0]))
        for idx in range(4):
            trial(DEV[0],'delivery','train',TRAIN_START+idx,p,learning=True)
        q=RecoveryProber.restore(p.record())
        self.assertTrue(trial(DEV[0],'delivery','test',EVAL_START,q)['success'])
        self.assertTrue(trial(DEV[0],'assembly','test',EVAL_START,q)['success'])

    def test_checkpoint_replay_and_read_only_evaluation(self):
        p=RecoveryProber.from_source(learn(DEV[0]))
        trial(DEV[0],'delivery','train',TRAIN_START,p,learning=True)
        saved=p.record();other=RecoveryProber.restore(copy.deepcopy(saved))
        self.assertEqual(saved,other.record())
        self.assertEqual(trial(DEV[0],'delivery','test',EVAL_START,p),
                         trial(DEV[0],'delivery','test',EVAL_START,other))
        self.assertEqual(p.record(),saved)
        self.assertEqual(other.record(),saved)

    def test_corruption_rehashed_but_wrong_source_boundary(self):
        p=RecoveryProber.from_source(learn(DEV[0]))
        saved=p.record();bad=copy.deepcopy(saved)
        bad['state']['source_glyphs']=['fictional']
        bad['sha256']=digest(bad['state'])
        with self.assertRaisesRegex(ValueError,'unreplayable'):
            RecoveryProber.restore(bad)

    def test_reject_unhashable_source_glyphs_before_set_operations(self):
        p=RecoveryProber.from_source(learn(DEV[0]))
        bad=copy.deepcopy(p.record())
        bad['state']['source_glyphs']=[['malformed']]
        bad['sha256']=digest(bad['state'])
        with self.assertRaises(ValueError):RecoveryProber.restore(bad)

    def test_forged_positive_memory_rejected_by_existing_replay(self):
        p=RecoveryProber.from_source(learn(DEV[0]))
        saved=p.record();bad=copy.deepcopy(saved)
        bad['state']['memory']['state']['knowledge']['smelt']['effects']['ingot']+=1
        bad['state']['memory']['sha256']=digest(bad['state']['memory']['state'])
        bad['sha256']=digest(bad['state'])
        with self.assertRaises(ValueError):RecoveryProber.restore(bad)

    def test_invalid_frame_and_failed_action_context(self):
        p=RecoveryProber.from_source(learn(DEV[0]))
        f=SkillWorld(DEV[0],'assembly','test',EVAL_START).frame()
        action=f['actions'][0]['id']
        for bad in ({'unknown':[]},{action:[1]}, {action:['not-a-fact']}, []):
            with self.assertRaises(ValueError):p.choose(f,bad)
        f['requirements']=['privileged']
        with self.assertRaises(ValueError):p.choose(f)

    def test_legacy_negative_study_is_unchanged(self):
        p=PrerequisiteProber.from_source(learn(DEV[0]))
        for i in range(4):trial(DEV[0],'delivery','train',TRAIN_START+i,p,learning=True)
        self.assertFalse(trial(DEV[0],'delivery','test',EVAL_START,p)['success'])

    def test_no_source_target_only_checkpoint_roundtrip(self):
        p=RecoveryProber(OutcomeSkills())
        self.assertEqual(p.record(),RecoveryProber.restore(p.record()).record())
        trial(DEV[0],'delivery','train',TRAIN_START,p,learning=True)
        self.assertEqual(p.record(),RecoveryProber.restore(p.record()).record())

    def test_protocol_disjoint_and_inspected(self):
        self.assertEqual(STAGES,(0,1,2,4,8,20))
        self.assertNotEqual(TRAIN_START,EVAL_START)
        for invalid in ((DEV[0],), tuple(reversed(EXTRA)), (1,2,3)):
            with self.assertRaises(ValueError):measure(invalid)


if __name__=='__main__':unittest.main()
