"""No target training, strict public graph, deterministic replay, frozen cohorts."""
import copy
import unittest
from developmental_ai.procedural_skill import (ProceduralWorld,ProceduralSkill,ancestor_closure,
  validate_frame,features,policy_choice,digest)
from benchmarks.procedural_skill_benchmark import measure,DEV,ADDITIONAL,evaluate_one

class ProceduralSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill=ProceduralSkill(14003).train(35)
        cls.ablation=ProceduralSkill(14003,use_ancestor=False).train(35)

    def test_generators_distinct_and_opaque(self):
        w=ProceduralWorld(14003,'workshop','train',2)
        r=ProceduralWorld(14003,'repair','train',2)
        self.assertEqual(len(ancestor_closure(w.graph,w.goal)),4)
        self.assertEqual(len(ancestor_closure(r.graph,r.goal)),5)
        self.assertNotEqual(w.graph,r.graph)
        self.assertEqual(w.frame(),ProceduralWorld(14003,'workshop','train',2).frame())

    def test_strict_frames_hide_latent_goal_solution(self):
        w=ProceduralWorld(14003,'workshop','test',70000)
        f=w.frame();self.assertNotIn('required_actions',f)
        bad=copy.deepcopy(f);bad['privileged_answer']=[w.goal]
        with self.assertRaises(ValueError):validate_frame(bad)
        bad=copy.deepcopy(f);bad['available_actions']=[]
        with self.assertRaises(ValueError):validate_frame(bad)
        self.assertEqual(validate_frame(f),ancestor_closure(f['prerequisites'],f['goal']))

    def test_rejects_cycle_and_forged_completed_history(self):
        with self.assertRaises(ValueError):ancestor_closure({'a':['b'],'b':['a']},'a')
        w=ProceduralWorld(14003,'repair','test',70000)
        f=w.frame(); bad=copy.deepcopy(f);bad['completed']=['bad'];bad['tick']=1;bad['remaining']=5
        with self.assertRaises(ValueError):validate_frame(bad)

    def test_stale_and_invalid_actions(self):
        w=ProceduralWorld(14003,'workshop','test',70000)
        f=w.frame();act=f['available_actions'][0]
        with self.assertRaises(ValueError):w.step(act,expected_tick=1)
        with self.assertRaises(ValueError):w.step(True,expected_tick=0)
        w.step(act,expected_tick=0)
        with self.assertRaises(ValueError):w.step(act,expected_tick=0)

    def test_policy_learns_from_outcomes_not_target(self):
        record=self.skill.record()
        self.assertIn('1|1',record['state']['weights'])
        self.assertNotIn('correct_action',str(record))
        w=ProceduralWorld(14003,'repair','test',70005)
        a=self.skill.choose(w.frame())
        self.assertIn(a,w.frame()['available_actions'])
        self.assertEqual(record,self.skill.record())

    def test_no_target_training_method(self):
        with self.assertRaises(TypeError):self.skill.train(1,family='repair')
        with self.assertRaises(ValueError):ProceduralSkill(14003).train(0)
        with self.assertRaises(ValueError):ProceduralWorld(14003,'other','train',0)

    def test_restore_exact_and_wrong_parameter_rejection(self):
        record=self.skill.record()
        self.assertEqual(ProceduralSkill.restore(copy.deepcopy(record)).record(),record)
        self.assertNotEqual(self.ablation.record(),record)

    def test_rehashed_tamper_decisions_and_values_rejected(self):
        record=self.skill.record()
        for mutation in ('actions','counts','seed','bool'):
            altered=copy.deepcopy(record)
            if mutation=='actions':altered['state']['episodes'][0][0]='made_up'
            if mutation=='counts':
                k=next(iter(altered['state']['weights']))
                altered['state']['weights'][k][0]+=2
            if mutation=='seed':altered['state']['seed']+=1
            if mutation=='bool':altered['state']['use_ancestor']=None
            altered['sha256']=digest(altered['state'])
            with self.assertRaises(ValueError):ProceduralSkill.restore(altered)

    def test_incomplete_and_forged_public_frame(self):
        f=ProceduralWorld(14003,'repair','test',70000).frame()
        bad=copy.deepcopy(f);bad['prerequisites'][f['goal']]=['unknown']
        with self.assertRaises(ValueError):self.skill.choose(bad)
        with self.assertRaises(ValueError):features(f,'unknown')

    def test_replay_test_fixed_actions(self):
        a=evaluate_one(14003,'repair',70004,'learned',self.skill,self.ablation)
        b=evaluate_one(14003,'repair',70004,'learned',self.skill,self.ablation)
        self.assertEqual(a,b)

    def test_frozen_cohorts(self):
        self.assertNotEqual(DEV,ADDITIONAL)
        for seeds in ((14003,),list(DEV)+[27007],[]):
            with self.assertRaises(ValueError):measure(seeds)

if __name__=='__main__':unittest.main()
