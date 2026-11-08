"""Independent hidden-graph replay and simulation-only plan-memory boundaries."""
import copy
import unittest
from developmental_ai.context_plan_memory import ContextPlanMemory, NovelProcedure, digest, labels, validate_frame
from benchmarks.context_plan_benchmark import trial, measure, DEV, ADDITIONAL, START

class ContextPlanMemoryTests(unittest.TestCase):
    def setUp(self):
        self.seed=14003
        self.world=NovelProcedure(self.seed,'test',START)
        self.agent=ContextPlanMemory(self.seed)

    def advance(self):
        f=self.world.frame()
        name=self.agent.propose(f)
        if name is None:return False
        response=self.world.step(name,expected_tick=f['tick'])
        self.agent.feedback(response)
        return True

    def test_opaque_action_names_shuffle_and_context_alternates(self):
        a=NovelProcedure(self.seed,'test',START)
        b=NovelProcedure(self.seed,'test',START+1)
        self.assertNotEqual(a.frame()['context'],b.frame()['context'])
        self.assertNotEqual(a.frame()['roles'],b.frame()['roles'])
        self.assertEqual(set(a.frame()['roles'].values()),set(b.frame()['roles'].values()))
        self.assertNotIn('_requirements',a.frame())
        self.assertNotIn('hidden_graph',str(a.frame()))
        self.assertNotEqual(a._requirements,b._requirements)

    def test_hidden_graph_is_not_policy_input(self):
        before=self.world.frame()
        before['dependencies']={'goal':['secret']}
        with self.assertRaises(ValueError):self.agent.propose(before)

    def test_no_stale_commands_and_no_action_without_proposal(self):
        with self.assertRaises(ValueError):self.agent.feedback({'accepted':True})
        f=self.world.frame()
        choice=self.agent.propose(f)
        with self.assertRaises(ValueError):self.agent.propose(f)
        with self.assertRaises(ValueError):self.world.step(choice,expected_tick=f['tick']+1)
        self.agent.feedback(self.world.step(choice,expected_tick=f['tick']))

    def test_public_frame_rejects_inconsistent_actions(self):
        f=self.world.frame()
        f['available_actions'].pop()
        with self.assertRaises(ValueError):validate_frame(f)

    def test_privileged_fields_rejected(self):
        f=self.world.frame()
        f['true_order']=['secret']
        with self.assertRaises(ValueError):validate_frame(f)

    def test_feedback_rejects_boolean_imposter_and_preserves_state(self):
        f=self.world.frame();action=self.agent.propose(f)
        response=self.world.step(action,expected_tick=0)
        for bad in [1,'true',None,0.5]:
            v=copy.deepcopy(response);v['accepted']=bad
            with self.assertRaises(ValueError):self.agent.feedback(v)
            self.assertEqual(self.agent.events,[])
        self.agent.feedback(response)

    def test_feedback_rejects_altered_frame(self):
        f=self.world.frame();action=self.agent.propose(f)
        response=self.world.step(action,expected_tick=0)
        forged=copy.deepcopy(response);forged['frame']['context']='case_00000000'
        with self.assertRaises(ValueError):self.agent.feedback(forged)
        self.agent.feedback(response)

    def test_record_restore_mid_episode(self):
        for _ in range(3):self.advance()
        record=self.agent.record()
        rebuilt=ContextPlanMemory.restore(copy.deepcopy(record))
        self.assertEqual(rebuilt.record(),record)
        while not self.world.done:
            f=self.world.frame()
            a=self.agent.propose(f);b=rebuilt.propose(copy.deepcopy(f))
            self.assertEqual(a,b)
            if a is None:break
            result=self.world.step(a,expected_tick=f['tick'])
            self.agent.feedback(result);rebuilt.feedback(copy.deepcopy(result))
        self.assertEqual(self.agent.record(),rebuilt.record())

    def test_plan_saved_for_both_contexts_with_multiple_episodes(self):
        m=ContextPlanMemory(self.seed)
        for index in range(START,START+80):trial(self.seed,index,m,'context')
        self.assertEqual(len(m.plans),2)
        self.assertEqual(len(set(map(tuple,m.plans.values()))),2)
        self.assertEqual(m.record(),ContextPlanMemory.restore(m.record()).record())

    def test_current_episode_does_not_use_hidden_state(self):
        self.assertEqual(self.agent.propose(self.world.frame()) in self.world.frame()['available_actions'],True)
        self.assertTrue(all(not k.startswith('_') for k in self.agent.pending))

    def test_plan_memory_strict_mode_validation(self):
        with self.assertRaises(ValueError):ContextPlanMemory(14003,mode='unrestricted')
        with self.assertRaises(ValueError):ContextPlanMemory(True)
        with self.assertRaises(ValueError):NovelProcedure(self.seed,'prod',START)

    def test_rehashed_forged_choice_cannot_replay(self):
        for _ in range(4):self.advance()
        snapshot=self.agent.record()
        snapshot['state']['events'][0]['action']='other'
        snapshot['sha256']=digest(snapshot['state'])
        with self.assertRaises(ValueError):ContextPlanMemory.restore(snapshot)

    def test_rehashed_forged_plan_cannot_replay(self):
        agent=ContextPlanMemory(self.seed)
        for index in range(START,START+80):trial(self.seed,index,agent,'context')
        snapshot=agent.record()
        ctx=next(iter(snapshot['state']['plans']))
        snapshot['state']['plans'][ctx]=['fake_role']
        snapshot['sha256']=digest(snapshot['state'])
        with self.assertRaises(ValueError):ContextPlanMemory.restore(snapshot)

    def test_cannot_abandon_unfinished_episode(self):
        self.advance()
        other=NovelProcedure(self.seed,'test',START+1)
        with self.assertRaises(ValueError):self.agent.propose(other.frame())

    def test_frozen_evaluation_cohorts(self):
        with self.assertRaises(ValueError):measure([DEV[0]])
        with self.assertRaises(ValueError):measure(list(DEV)+[ADDITIONAL[0]])
        self.assertNotEqual(DEV,ADDITIONAL)

    def test_deterministic_single_episode(self):
        self.assertEqual(trial(self.seed,START,None,'oracle'),trial(self.seed,START,None,'oracle'))

if __name__=='__main__':unittest.main()
