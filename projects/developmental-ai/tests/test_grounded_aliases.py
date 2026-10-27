"""Public-reference calibration, strict target schema and replay-bound grounding."""
import copy
import unittest
from benchmarks.grounded_aliases_benchmark import aliases, calibration, stream, navigate, measure
from developmental_ai.grounded_aliases import GroundedAliases
from developmental_ai.online_memory_gate import MemoryGate
from developmental_ai.environment_api import digest


class GroundedAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate=MemoryGate(2749).train(1800)
        cls.samples=calibration(2749,48)
        cls.bridge=GroundedAliases(cls.gate,cls.samples)

    def test_names_are_distinct_and_not_shared_with_first_domain(self):
        src,contexts=aliases(2749)
        self.assertEqual(set(src),{'A','B','N0','N1','N2'})
        self.assertEqual(len(set(src.values())),5)
        self.assertEqual(set(contexts.values()),{'lunar','solar'})
        self.assertNotIn('A',src.values())

    def test_training_uses_public_pair_not_private_hidden_world_state(self):
        self.assertEqual(set(self.samples[0]),{'context','cues','reference'})
        self.assertEqual(len(self.samples),48)
        self.assertEqual(len(self.samples[0]['cues']),5)
        sample=copy.deepcopy(self.samples[0]);sample['hidden_position']=[0,0]
        with self.assertRaises(ValueError):GroundedAliases(self.gate,[sample]+self.samples[1:])

    def test_train_only_alignment_is_recoverable_from_evidence(self):
        pair=self.bridge.alignment
        self.assertEqual(set(pair['contexts']),{'lunar','solar'})
        self.assertEqual({x for x in pair['source_roles'].values()}, {'A','B','N'})
        self.assertEqual(len(set(pair['reliable_sources'].values())),2)
        for context,channel in pair['reliable_sources'].items():
            self.assertEqual(pair['source_roles'][channel], 'A' if context==pair['contexts'][0] else 'B')

    def test_frozen_adapter_selects_correct_target_cue_without_reference(self):
        for i in range(8):
            ref=[i-4,2]
            target=stream(2749,97000+i,ref)
            self.assertEqual(self.bridge.select(target['context'],target['cues']),ref)

    def test_snapshot_roundtrip_and_new_model_mismatch(self):
        record=self.bridge.record()
        self.assertEqual(GroundedAliases.restore(record,self.gate).record(),record)
        with self.assertRaises(ValueError):GroundedAliases.restore(record,MemoryGate(6607).train(1800))

    def test_forged_mapping_rejected_after_rehash(self):
        record=copy.deepcopy(self.bridge.record())
        role=next(k for k,v in record['state']['alignment']['source_roles'].items() if v=='A')
        record['state']['alignment']['source_roles'][role]='N'
        record['digest']=digest(record['state'])
        with self.assertRaises(ValueError):GroundedAliases.restore(record,self.gate)

    def test_checksum_cannot_authenticate_forged_but_consistent_evidence(self):
        record=copy.deepcopy(self.bridge.record())
        record['state']['calibration'][0]['reference']=[-8,-8]
        record['digest']=digest(record['state'])
        # A caller who can rewrite both the evidence and checksum may produce
        # equally plausible evidence. SHA-256 is integrity, not authentication.
        self.assertEqual(GroundedAliases.restore(record,self.gate).record(),record)

    def test_unknown_alias_and_privileged_target_input_fail_closed(self):
        sample=stream(2749,97000,[1,2])
        with self.assertRaises(ValueError):self.bridge.select('unknown',sample['cues'])
        bad=copy.deepcopy(sample['cues']);bad[0][0]='secret'
        with self.assertRaises(ValueError):self.bridge.select(sample['context'],bad)
        bad=copy.deepcopy(sample['cues']);bad[0].append('world_truth')
        with self.assertRaises(ValueError):self.bridge.select(sample['context'],bad)

    def test_insufficient_ambiguous_or_duplicate_calibration_rejected(self):
        with self.assertRaises(ValueError):GroundedAliases(self.gate,self.samples[:4])
        with self.assertRaises(ValueError):GroundedAliases(self.gate,[self.samples[0]]*8)
        bad=copy.deepcopy(self.samples)
        for s in bad:
            s['reference']=[8,8]
        with self.assertRaises(ValueError):GroundedAliases(self.gate,bad)

    def test_benchmark_reproducible_and_direct_lookup_control(self):
        result=measure((2749,),train=120,calibration_episodes=20,episodes=5)
        self.assertEqual(result,measure((2749,),train=120,calibration_episodes=20,episodes=5))
        self.assertEqual(set(result['rows'][0]['scores']),{'adapted','paired_lookup','wrong_context','first','last','random','oracle'})
        self.assertFalse(result['blind'])
        self.assertTrue(result['calibration_is_supervised'])
        with self.assertRaises(ValueError):measure((2749,2749),train=120,episodes=5)

if __name__=='__main__':unittest.main()
