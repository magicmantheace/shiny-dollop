"""Online prerequisite evidence, action boundary, exact replay and frozen cohort tests."""
import copy
import unittest
from developmental_ai.hidden_prerequisites import HiddenProcedure, MAX_ATTEMPTS, digest
from developmental_ai.online_prerequisite_probing import OnlinePrerequisiteAgent
from benchmarks.online_prerequisite_probing_benchmark import online_trial, measure, DEV, ADDITIONAL, START

class OnlinePrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.seed = 14003
        self.agent = OnlinePrerequisiteAgent(self.seed)
        self.world = HiddenProcedure(self.seed, 'repair', 'test', START)

    def take(self):
        frame = self.world.frame()
        action = self.agent.propose(frame)
        if action is None:
            return None
        response = self.world.step(action, expected_tick=frame['tick'])
        self.agent.feedback(response)
        return response

    def test_one_step_goal_probe_and_public_only_state(self):
        f = self.world.frame()
        self.assertNotIn('_requirements', f)
        self.assertEqual(self.agent.propose(f), f['goal'])
        with self.assertRaises(ValueError): self.agent.propose(f)
        self.assertEqual(self.agent.events, [])

    def test_reject_privileged_public_frame(self):
        f = self.world.frame(); f['_requirements'] = {'verify': ['inspect']}
        with self.assertRaises(ValueError): self.agent.propose(f)

    def test_reject_stale_tick_and_unknown_action_feedback(self):
        frame = self.world.frame()
        name = self.agent.propose(frame)
        response = self.world.step(name, expected_tick=frame['tick'])
        invalid = copy.deepcopy(response)
        invalid['frame']['tick'] += 1
        with self.assertRaises(ValueError): self.agent.feedback(invalid)
        invalid = copy.deepcopy(response); invalid['frame']['completed'].append(name)
        with self.assertRaises(ValueError): self.agent.feedback(invalid)
        self.assertEqual(self.agent.events, [])
        self.agent.feedback(response)

    def test_reject_nonboolean_outcomes_and_unseen_feedback(self):
        with self.assertRaises(ValueError): self.agent.feedback({'accepted': True})
        f = self.world.frame(); self.agent.propose(f)
        r = self.world.step(f['goal'], expected_tick=0)
        for bad in (1, 'false', None):
            forged = copy.deepcopy(r); forged['accepted'] = bad
            with self.assertRaises(ValueError): self.agent.feedback(forged)
        self.agent.feedback(r)

    def test_exact_restart_mid_episode(self):
        for _ in range(3): self.take()
        saved = self.agent.record()
        clone = OnlinePrerequisiteAgent.restore(copy.deepcopy(saved))
        self.assertEqual(saved, clone.record())
        while not self.world.done:
            before=self.world.frame()
            selected=self.agent.propose(before)
            identical=clone.propose(copy.deepcopy(before))
            self.assertEqual(selected, identical)
            if selected is None: break
            result=self.world.step(selected,expected_tick=before['tick'])
            self.agent.feedback(result); clone.feedback(copy.deepcopy(result))
        self.assertEqual(self.agent.record(), clone.record())

    def test_rehashed_forged_choice_rejected(self):
        for _ in range(3): self.take()
        saved=self.agent.record()
        saved['state']['events'][0]['action'] = next(
            a for a in self.world.name_to_role if a != saved['state']['events'][0]['action'])
        saved['sha256'] = digest(saved['state'])
        with self.assertRaises(ValueError): OnlinePrerequisiteAgent.restore(saved)

    def test_rehashed_forged_posterior_rejected(self):
        for _ in range(5): self.take()
        saved=self.agent.record()
        saved['state']['weights']['repair']['verify'][0] += .12
        saved['sha256'] = digest(saved['state'])
        with self.assertRaises(ValueError): OnlinePrerequisiteAgent.restore(saved)

    def test_wrong_seed_checkpoint_rejected_after_rehash(self):
        for _ in range(4): self.take()
        saved=self.agent.record()
        saved['state']['seed']=999
        saved['sha256']=digest(saved['state'])
        with self.assertRaises(ValueError): OnlinePrerequisiteAgent.restore(saved)

    def test_budget_and_no_permission_escalation(self):
        result=online_trial(OnlinePrerequisiteAgent(self.seed),self.seed,'repair',START)
        self.assertTrue(result['success'])
        self.assertLessEqual(result['attempts'],MAX_ATTEMPTS)
        self.assertEqual(set(result),{'success','attempts','blocked','stalled'})

    def test_in_task_and_across_episodes_learning(self):
        agent=OnlinePrerequisiteAgent(self.seed)
        result=[online_trial(agent,self.seed,'repair',START+i) for i in range(5)]
        self.assertTrue(all(x['success'] for x in result))
        self.assertGreater(len(agent.events),5)
        self.assertTrue(any(any(x != y for x,y in zip(row,agent.weights['repair'][role]))
                            for role,row in agent.weights['workshop'].items()))

    def test_cannot_abandon_unfinished_episode(self):
        self.take()
        other=HiddenProcedure(self.seed,'repair','test',START+1)
        with self.assertRaises(ValueError): self.agent.propose(other.frame())

    def test_training_namespace_and_cohort_constraints(self):
        with self.assertRaises(ValueError): measure([DEV[0]])
        with self.assertRaises(ValueError): measure(list(DEV)+[ADDITIONAL[0]])
        self.assertNotEqual(DEV,ADDITIONAL)

if __name__=='__main__':unittest.main()
