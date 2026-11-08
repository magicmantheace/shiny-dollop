"""Tests for outcome-learned per-event memory gate and replay boundary."""
import copy
import unittest

from developmental_ai.environment_api import digest,EnvironmentSession
from developmental_ai.online_memory_gate import MemoryGate,CueMemory
from benchmarks.online_memory_gate_benchmark import cue_stream, choose_beacon,measure


class OnlineGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate=MemoryGate(2749).train(160)

    def test_training_is_deterministic(self):
        self.assertEqual(self.gate.record(),MemoryGate(2749).train(160).record())
        self.assertEqual(MemoryGate.restore(self.gate.record()).record(),self.gate.record())

    def test_reward_learning_establishes_per_context_preferences(self):
        gate=MemoryGate(2749).train(1800)
        self.assertGreater(gate.source['0:A'][0],gate.source['0:B'][0])
        self.assertGreater(gate.source['0:A'][0],gate.source['0:N'][0])
        self.assertGreater(gate.source['1:B'][0],gate.source['1:A'][0])
        self.assertGreater(gate.source['1:B'][0],gate.source['1:N'][0])
        self.assertTrue(gate.decide(0,('N',0),('A',1)))
        self.assertFalse(gate.decide(1,('B',0),('N',1)))

    def test_individual_write_keep_decisions(self):
        gate=MemoryGate(2749).train(1800)
        memory=CueMemory(gate,0)
        self.assertEqual(memory.observe('B',0,[1,1])['operation'],'write')
        self.assertEqual(memory.observe('A',1,[2,2])['operation'],'write')
        self.assertEqual(memory.observe('N',2,[3,3])['operation'],'keep')
        self.assertEqual(memory.held['payload'],[2,2])

    def test_checkpoint_exact_replay_and_continue(self):
        memory=CueMemory(self.gate,0)
        memory.observe('A',1,[2,1]);memory.observe('N',0,[-1,0])
        restored=CueMemory.restore(memory.snapshot(),self.gate)
        self.assertEqual(memory.snapshot(),restored.snapshot())
        self.assertEqual(memory.observe('B',3,[0,-2]),restored.observe('B',3,[0,-2]))
        self.assertEqual(memory.snapshot(),restored.snapshot())

    def test_forged_choice_rejected_even_with_new_checksum(self):
        memory=CueMemory(self.gate,0)
        memory.observe('A',1,[2,1]);memory.observe('N',0,[-1,0])
        record=copy.deepcopy(memory.snapshot())
        record['state']['events'][0]['write']=False
        record['digest']=digest(record['state'])
        with self.assertRaises(ValueError):CueMemory.restore(record,self.gate)

    def test_forged_held_payload_rejected_with_rehash(self):
        memory=CueMemory(self.gate,0)
        memory.observe('A',1,[2,1]);memory.observe('N',0,[-1,0])
        record=copy.deepcopy(memory.snapshot())
        record['state']['held']={'source':'B','token':3,'payload':[4,4]}
        record['digest']=digest(record['state'])
        with self.assertRaises(ValueError):CueMemory.restore(record,self.gate)

    def test_model_mismatch_and_bad_digest_rejected(self):
        memory=CueMemory(self.gate,0)
        memory.observe('A',0,[2,1])
        with self.assertRaises(ValueError):CueMemory.restore(memory.snapshot(),MemoryGate(6607).train(160))
        record=copy.deepcopy(memory.snapshot());record['digest']='0'*64
        with self.assertRaises(ValueError):CueMemory.restore(record,self.gate)

    def test_strict_inputs_and_capacity(self):
        memory=CueMemory(self.gate,0)
        for bad in [('secret',0,[0,0]),('A',True,[0,0]),('A',0,[0,0,0]),('A',0,[100,0])]:
            with self.assertRaises(ValueError):memory.observe(*bad)
        for _ in range(64):memory.observe('A',0,[0,0])
        with self.assertRaises(ValueError):memory.observe('B',0,[1,1])
        with self.assertRaises(ValueError):self.gate.decide(0,('N',0),('A',0),epsilon=1.01)
        with self.assertRaises(ValueError):self.gate.trial('test',1,learn=True)

    def test_public_occluded_candidate_generation_and_order_controls(self):
        s=EnvironmentSession('occluded',2749,'test',94000)
        original=tuple(s.frame()['observation']['beacon'])
        context,cues=cue_stream(2749,94000,original)
        self.assertEqual(len(cues),5)
        self.assertEqual(choose_beacon(MemoryGate(2749).train(1800),'oracle',context,cues,2749,94000),original)
        self.assertEqual(choose_beacon(MemoryGate(2749).train(1800),'learned',context,cues,2749,94000),original)

    def test_small_benchmark_reproducible_and_not_blind(self):
        a=measure((2749,),train=100,episodes=3,updater_episodes=5)
        self.assertEqual(a,measure((2749,),train=100,episodes=3,updater_episodes=5))
        self.assertFalse(a['blind'])
        self.assertEqual(set(a['rows'][0]['navigation']),{'learned','first','last','random','oracle','no_context'})
        with self.assertRaises(ValueError):measure((2749,2749),train=100,episodes=3)

if __name__=='__main__':unittest.main()
