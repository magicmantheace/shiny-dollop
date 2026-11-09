"""Hidden DAG boundary, action feedback, transfer and replay tests."""
import copy
import unittest
from developmental_ai.hidden_prerequisites import (
    HiddenProcedure,PreconditionSkill,validate_frame,digest,ROLES,MAX_ATTEMPTS,run)
from benchmarks.hidden_prerequisite_benchmark import measure,DEV,ADDITIONAL


class HiddenPrerequisiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill=PreconditionSkill(14003).train(30)

    def test_hidden_graph_not_exposed_and_deterministic(self):
        a=HiddenProcedure(14003,'workshop','train',0)
        b=HiddenProcedure(14003,'workshop','train',0)
        self.assertEqual(a.frame(),b.frame())
        self.assertNotIn('prerequisites',a.frame())
        self.assertNotIn('_requirements',a.frame())
        self.assertEqual(set(a.frame()['roles'].values()),set(ROLES))
        self.assertEqual(validate_frame(a.frame()),a.frame())

    def test_illegal_action_and_tick_are_rejected(self):
        w=HiddenProcedure(14003,'workshop','test',81000)
        action=w.frame()['goal']
        with self.assertRaises(ValueError):w.step(action,expected_tick=1)
        with self.assertRaises(ValueError):w.step('unknown',expected_tick=0)
        with self.assertRaises(ValueError):w.step(True,expected_tick=0)
        self.assertEqual(w.step(action,expected_tick=0)['event'],'blocked')
        self.assertEqual(w.tick,1)

    def test_block_feedback_does_not_leak_missing_requirement(self):
        w=HiddenProcedure(14003,'repair','test',81000)
        ret=w.step(w.frame()['goal'],expected_tick=0)
        self.assertEqual(set(ret),{'frame','event','accepted','reward'})
        self.assertEqual(ret['event'],'blocked')
        self.assertNotIn('missing',str(ret))

    def test_forged_public_frame_rejected(self):
        f=HiddenProcedure(14003,'repair','test',81000).frame()
        for mutation in ('hidden','mask','tick','done'):
            bad=copy.deepcopy(f)
            if mutation=='hidden':bad['prerequisites']={}
            if mutation=='mask':bad['available_actions']=[]
            if mutation=='tick':bad['tick']=1
            if mutation=='done':bad['done']=True
            with self.assertRaises(ValueError):validate_frame(bad)

    def test_training_discovers_workshop_predecessor_evidence(self):
        prior=PreconditionSkill(14003).train(300).prerequisites()
        self.assertTrue({'gather_a','gather_b'}.issubset(prior['assemble']))
        self.assertTrue({'assemble','gather_a','gather_b'}.issubset(prior['deliver']))
        self.assertEqual(prior['gather_a'],set())
        self.assertEqual(prior['gather_b'],set())

    def test_restore_after_training_is_exact(self):
        saved=self.skill.record()
        self.assertEqual(PreconditionSkill.restore(copy.deepcopy(saved)).record(),saved)

    def test_rehashed_forgery_rejected(self):
        for mutation in ('role','action','seed','observed'):
            wrong=copy.deepcopy(self.skill.record())
            if mutation=='role':wrong['state']['traces'][0][0][0]='unknown'
            elif mutation=='action':wrong['state']['traces'][0][0][1]='goal'
            elif mutation=='seed':wrong['state']['seed']+=1
            else:wrong['state']['observed']['assemble'].append(['gather_a'])
            wrong['sha256']=digest(wrong['state'])
            with self.assertRaises(ValueError):PreconditionSkill.restore(wrong)

    def test_transfer_keeps_skill_readonly(self):
        skill=self.skill
        before=skill.record()
        for family in ('workshop','repair'):
            result=run(14003,family,81000,'learned',skill)
            self.assertLessEqual(result['attempts'],MAX_ATTEMPTS)
        self.assertEqual(before,skill.record())

    def test_no_target_training_or_missing_model(self):
        with self.assertRaises(TypeError):self.skill.train(1,family='repair')
        with self.assertRaises(ValueError):PreconditionSkill(14003).train(0)
        with self.assertRaises(ValueError):PreconditionSkill(14003).choose(HiddenProcedure(14003,'repair','test',81000).frame(),blocked=9)

    def test_frozen_protocol_rejects_partial_seeds(self):
        for seeds in ([14003],list(DEV)+[27007],[]):
            with self.assertRaises(ValueError):measure(seeds)
        self.assertNotEqual(DEV,ADDITIONAL)

if __name__=='__main__':unittest.main()
