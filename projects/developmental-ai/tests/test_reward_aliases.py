"""Reward-only alias learning: public-input boundary, exact replay, controls."""
import copy
import unittest

from developmental_ai.environment_api import digest
from developmental_ai.reward_aliases import RewardAliasLearner, FIRST_INDEX
from benchmarks.grounded_aliases_benchmark import stream
from benchmarks.reward_only_alignment_benchmark import train, navigate, measure
from developmental_ai.learned_spatial_memory import train_grid_updates


class RewardAliasesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=2749
        cls.updater=train_grid_updates(cls.seed,24)
        cls.gate,_=train(cls.seed,cls.updater,episodes=40)
        cls.sample=stream(cls.seed,98000,[2,-1])

    def test_no_paired_reference_in_learner_or_record(self):
        obj=RewardAliasLearner(2749)
        sample=copy.deepcopy(self.sample)
        sample['reference']=[2,-1]
        with self.assertRaises(TypeError):obj.propose(**sample,split='train',index=FIRST_INDEX)
        obj.propose(sample['context'],sample['cues'],split='train',index=FIRST_INDEX)
        with self.assertRaises(ValueError):obj.feedback([2,-1],split='train',index=FIRST_INDEX)
        obj.feedback(True,split='train',index=FIRST_INDEX)
        self.assertNotIn('reference',str(obj.events))

    def test_record_and_reward_only_replay(self):
        saved=self.gate.record()
        self.assertEqual(saved,RewardAliasLearner.restore(saved).record())
        for ctx in self.gate.contexts:
            self.assertEqual(self.gate.predict(ctx,self.sample['cues']),
                             RewardAliasLearner.restore(saved).predict(ctx,self.sample['cues']))

    def test_recomputed_digest_cannot_hide_impossible_choice(self):
        tampered=copy.deepcopy(self.gate.record())
        tampered['state']['events'][0]['chosen']='wrong-source'
        tampered['digest']=digest(tampered['state'])
        with self.assertRaises(ValueError):RewardAliasLearner.restore(tampered)

    def test_corrupted_reward_stats_rejected_even_if_rehashed(self):
        tampered=copy.deepcopy(self.gate.record())
        key=next(iter(tampered['state']['evidence']))
        tampered['state']['evidence'][key][0]+=4
        tampered['digest']=digest(tampered['state'])
        with self.assertRaises(ValueError):RewardAliasLearner.restore(tampered)

    def test_unfinished_training_cannot_checkpoint(self):
        obj=RewardAliasLearner(2749)
        obj.propose(self.sample['context'],self.sample['cues'],split='train',index=FIRST_INDEX)
        with self.assertRaises(ValueError):obj.record()
        with self.assertRaises(ValueError):obj.propose(self.sample['context'],self.sample['cues'],split='train',index=FIRST_INDEX+1)
        with self.assertRaises(ValueError):obj.feedback(True,split='test',index=FIRST_INDEX)
        with self.assertRaises(ValueError):obj.feedback(True,split='train',index=FIRST_INDEX+1)

    def test_unknown_source_and_privileged_fields_fail_closed(self):
        context=self.sample['context']
        mutated=copy.deepcopy(self.sample['cues']);mutated[0].append({'privileged':'answer'})
        with self.assertRaises(ValueError):self.gate.predict(context,mutated)
        mutated=copy.deepcopy(self.sample['cues']);mutated[0][0]='unknown_alias'
        with self.assertRaises(ValueError):self.gate.predict(context,mutated)
        with self.assertRaises(ValueError):self.gate.predict('new_context',self.sample['cues'])
        mutated=copy.deepcopy(self.sample['cues']);mutated[0][2]=[True,2]
        with self.assertRaises(ValueError):self.gate.predict(context,mutated)

    def test_train_requires_strict_sequence_and_bool_reward(self):
        obj=RewardAliasLearner(2749)
        with self.assertRaises(ValueError):obj.propose(self.sample['context'],self.sample['cues'],split='test',index=FIRST_INDEX)
        with self.assertRaises(ValueError):obj.propose(self.sample['context'],self.sample['cues'],split='train',index=FIRST_INDEX+1)
        obj.propose(self.sample['context'],self.sample['cues'],split='train',index=FIRST_INDEX)
        for bad in (1,0.0,{'correct':True},None):
            with self.assertRaises(ValueError):obj.feedback(bad,split='train',index=FIRST_INDEX)
        obj.feedback(False,split='train',index=FIRST_INDEX)

    def test_training_is_deterministic_from_same_reward_outcomes(self):
        duplicate,_=train(self.seed,self.updater,episodes=40)
        self.assertEqual(duplicate.record(),self.gate.record())

    def test_frozen_protocol_rejects_tuned_parameters_and_unapproved_cohort(self):
        with self.assertRaises(ValueError):measure((2749,),training=360)
        with self.assertRaises(ValueError):measure((2749,6607,9901),training=359)
        with self.assertRaises(ValueError):measure((2749,6607,9901),episodes=41)

    def test_direct_lookup_is_same_policy_on_shared_reward_evidence(self):
        for ctx in self.gate.contexts:
            source=self.gate.best_source(ctx,self.sample['cues'])
            selected=self.gate.predict(ctx,self.sample['cues'])
            self.assertEqual(selected,next(c[2] for c in self.sample['cues'] if c[0]==source))

if __name__=='__main__':unittest.main()
