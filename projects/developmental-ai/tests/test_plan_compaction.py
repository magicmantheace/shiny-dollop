"""Outcome-guided plan ablation, feedback integrity and checkpoint replay."""
import copy
import unittest
from developmental_ai.plan_compaction import CompactionMemory, digest
from developmental_ai.plan_repair import RepairWorld
from benchmarks.plan_compaction_benchmark import trial, measure, DEV, ADDITIONAL, START


class CompactionTests(unittest.TestCase):
    def test_bounded_candidate_and_public_feedback(self):
        obj=CompactionMemory(34007)
        world=RepairWorld(34007,'test',START)
        frame=world.frame()
        act=obj.propose(frame)
        self.assertIn(act,frame['available_actions'])
        with self.assertRaises(ValueError):obj.propose(frame)
        response=world.step(act,expected_tick=0)
        corrupted=copy.deepcopy(response);corrupted['accepted']='yes'
        with self.assertRaises(ValueError):obj.feedback(corrupted)
        obj.feedback(response)

    def test_deterministic_plan_compaction(self):
        a=CompactionMemory(34007)
        b=CompactionMemory(34007)
        for index in range(START,START+80):
            self.assertEqual(trial(34007,index,a,'repair'),trial(34007,index,b,'repair'))
        self.assertEqual(a.record(),b.record())
        self.assertGreater(len(a.probe_outcomes),0)
        self.assertTrue(any(x['improved'] for x in a.probe_outcomes))

    def test_record_restore_across_phase_switch(self):
        mem=CompactionMemory(34007)
        for index in range(START,START+27):trial(34007,index,mem,'repair')
        saved=mem.record()
        resumed=CompactionMemory.restore(copy.deepcopy(saved))
        self.assertEqual(saved,resumed.record())
        for index in range(START+27,START+33):
            self.assertEqual(trial(34007,index,mem,'repair'),trial(34007,index,resumed,'repair'))
        self.assertEqual(mem.record(),resumed.record())

    def test_rehashed_omission_forgery_rejected(self):
        mem=CompactionMemory(34007)
        for index in range(START,START+30):trial(34007,index,mem,'repair')
        snap=mem.record()
        modified=copy.deepcopy(snap)
        modified['state']['probe_outcomes'][0]['improved']=not modified['state']['probe_outcomes'][0]['improved']
        modified['sha256']=digest(modified['state'])
        with self.assertRaises(ValueError):CompactionMemory.restore(modified)

    def test_wrong_version_or_mode_rejected(self):
        mem=CompactionMemory(34007)
        with self.assertRaises(ValueError):CompactionMemory.restore({'state':{},'sha256':'x'})
        f=RepairWorld(34007,'test',START).frame()
        f['privileged_graph']={'goal':'secret'}
        with self.assertRaises(ValueError):mem.propose(f)

    def test_frozen_cohorts(self):
        with self.assertRaises(ValueError):measure([DEV[0]])
        with self.assertRaises(ValueError):measure(list(DEV)+[ADDITIONAL[0]])

if __name__=='__main__':unittest.main()
