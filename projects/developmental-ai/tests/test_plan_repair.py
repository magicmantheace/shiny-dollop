"""Strict public role frames, shifting unlabelled graph, and exact replay."""
import copy
import unittest
from developmental_ai.plan_repair import (
    RepairWorld, RepairPlanMemory, opaque_roles, check_frame, digest, MAX_STEPS
)
from benchmarks.plan_repair_benchmark import trial, measure, DEV, ADDITIONAL, START

class RepairMemoryTests(unittest.TestCase):
    def setUp(self):
        self.seed=34007
        self.world=RepairWorld(self.seed,'test',START)
        self.agent=RepairPlanMemory(self.seed)

    def test_hidden_graph_changes_but_no_public_phase(self):
        a=RepairWorld(self.seed,'test',START)
        b=RepairWorld(self.seed,'test',START+21)
        self.assertNotEqual(a._requirements,b._requirements)
        self.assertNotIn('phase',a.frame())
        self.assertNotIn('requirements',a.frame())
        self.assertEqual(set(a.frame()['roles'].values()),set(b.frame()['roles'].values()))
        self.assertNotEqual(a.frame()['roles'],b.frame()['roles'])
        self.assertEqual(len(opaque_roles(self.seed)),7)

    def test_frame_only_public_values(self):
        frame=self.world.frame()
        self.assertEqual(check_frame(frame),frame)
        for key in ('phase','context','hidden_requirements','true_order'):
            bad=copy.deepcopy(frame)
            bad[key]='private'
            with self.assertRaises(ValueError):self.agent.propose(bad)

    def test_rejects_stale_commands_and_unrequested_feedback(self):
        with self.assertRaises(ValueError):self.agent.feedback({'accepted':True})
        f=self.world.frame(); action=self.agent.propose(f)
        with self.assertRaises(ValueError):self.agent.propose(f)
        with self.assertRaises(ValueError):self.world.step(action,expected_tick=1)
        self.agent.feedback(self.world.step(action,expected_tick=0))

    def test_checkpoint_replay_mid_episode(self):
        for _ in range(4):
            if self.world.done:break
            f=self.world.frame();a=self.agent.propose(f)
            if a is None:break
            self.agent.feedback(self.world.step(a,expected_tick=f['tick']))
        artifact=self.agent.record()
        copy_agent=RepairPlanMemory.restore(copy.deepcopy(artifact))
        self.assertEqual(artifact,copy_agent.record())
        while not self.world.done:
            f=self.world.frame()
            a=self.agent.propose(f);b=copy_agent.propose(copy.deepcopy(f))
            self.assertEqual(a,b)
            if a is None:break
            result=self.world.step(a,expected_tick=f['tick'])
            self.agent.feedback(result);copy_agent.feedback(copy.deepcopy(result))
        self.assertEqual(self.agent.record(),copy_agent.record())

    def test_restore_rejects_forged_choice_even_if_rehashed(self):
        f=self.world.frame()
        action=self.agent.propose(f)
        self.agent.feedback(self.world.step(action,expected_tick=0))
        artifact=self.agent.record()
        bad=copy.deepcopy(artifact)
        bad['state']['events'][0]['action']='not-an-action'
        bad['sha256']=digest(bad['state'])
        with self.assertRaises(ValueError):RepairPlanMemory.restore(bad)

    def test_restore_rejects_forged_plan(self):
        agent=RepairPlanMemory(self.seed)
        for index in range(START,START+80):trial(self.seed,index,agent,'repair')
        good=agent.record()
        self.assertGreater(len(agent.plans),0)
        changed=copy.deepcopy(good)
        changed['state']['plans']=[['imaginary']]
        changed['sha256']=digest(changed['state'])
        with self.assertRaises(ValueError):RepairPlanMemory.restore(changed)

    def test_resume_rejects_unfinished_cross_episode(self):
        f=self.world.frame();a=self.agent.propose(f)
        self.agent.feedback(self.world.step(a,expected_tick=0))
        with self.assertRaises(ValueError):self.agent.propose(RepairWorld(self.seed,'test',START+1).frame())

    def test_invalid_feedback_does_not_advance(self):
        f=self.world.frame();a=self.agent.propose(f)
        result=self.world.step(a,expected_tick=0)
        for fake in (1,'yes',None):
            bad=copy.deepcopy(result);bad['accepted']=fake
            with self.assertRaises(ValueError):self.agent.feedback(bad)
            self.assertEqual(self.agent.events,[])
        self.agent.feedback(result)

    def test_no_unbounded_and_type_violations(self):
        for val in (True,'34007',None):
            with self.assertRaises(ValueError):RepairPlanMemory(val)
        with self.assertRaises(ValueError):RepairPlanMemory(34007,mode='tool')
        with self.assertRaises(ValueError):RepairWorld(self.seed,'shell',START)
        f=self.world.frame();f['remaining']=MAX_STEPS+1
        with self.assertRaises(ValueError):check_frame(f)

    def test_frozen_cohorts(self):
        with self.assertRaises(ValueError):measure([DEV[0]])
        with self.assertRaises(ValueError):measure(list(DEV)+[ADDITIONAL[0]])

    def test_oracle_is_deterministic(self):
        self.assertEqual(trial(self.seed,START,None,'oracle'),trial(self.seed,START,None,'oracle'))

if __name__=='__main__':unittest.main()
