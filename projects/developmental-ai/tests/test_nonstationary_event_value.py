"""Causal online reward, frozen evaluation, replay and changed-context controls."""
import copy
import unittest
from developmental_ai.event_segmentation import fit_event_model
from developmental_ai.nonstationary_event_value import ChangingEventMemory, MODES, BOOTSTRAP
from developmental_ai.environment_api import digest
from benchmarks.event_segmentation_benchmark import episode, DEVELOPMENT
from benchmarks.nonstationary_event_value_benchmark import alternate, measure

class NonstationaryEventValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=14003
        cls.streams=[episode(cls.seed,'source_bursts','train',i)['observed'] for i in range(8)]
        cls.model=fit_event_model(cls.streams)

    def trained(self, mode='archive', count=BOOTSTRAP):
        m=ChangingEventMemory(self.model,self.seed,mode=mode)
        for i in range(count):
            choice=m.propose(i%2,self.streams[i%len(self.streams)],split='train',step=i)
            self.assertEqual(choice['center'],(choice['start']+choice['end']-1)//2)
            m.feedback((i%4==0),split='train',step=i)
        return m

    def test_live_feedback_requires_bool_and_order(self):
        m=ChangingEventMemory(self.model,self.seed)
        with self.assertRaises(ValueError):m.propose(0,self.streams[0],split='test',step=0)
        with self.assertRaises(ValueError):m.propose(0,self.streams[0],split='train',step=1)
        m.propose(0,self.streams[0],split='train',step=0)
        for bad in (1,0.0,'success',None):
            with self.assertRaises(ValueError):m.feedback(bad,split='train',step=0)
        m.feedback(False,split='train',step=0)
        with self.assertRaises(ValueError):m.feedback(True,split='train',step=0)

    def test_no_phase_or_truth_leak(self):
        m=ChangingEventMemory(self.model,self.seed)
        with self.assertRaises(TypeError):m.propose(0,self.streams[0],split='train',step=0,regime='A')
        with self.assertRaises(ValueError):m.propose(0,[0,True,1],split='train',step=0)
        with self.assertRaises(ValueError):m.propose(2,self.streams[0],split='train',step=0)

    def test_exact_checkpoint_replay_all_modes(self):
        for mode in MODES:
            m=self.trained(mode, count=BOOTSTRAP+12)
            save=m.record(); other=ChangingEventMemory.restore(copy.deepcopy(save),self.model)
            self.assertEqual(save,other.record())
            self.assertEqual(m.choose(0,self.streams[0]),other.choose(0,self.streams[0]))

    def test_rehash_cannot_forge_action_feedback_or_state(self):
        save=self.trained(count=BOOTSTRAP+16).record()
        for alteration in ('selected','success','count','active','switches'):
            x=copy.deepcopy(save)
            if alteration=='selected':x['state']['events'][0]['selected']['label']=(x['state']['events'][0]['selected']['label']+1)%4
            elif alteration=='success':x['state']['events'][0]['success']=not x['state']['events'][0]['success']
            elif alteration=='count':x['state']['events'].append(x['state']['events'][-1])
            elif alteration=='active':x['state']['active']='tampered'
            else:x['state']['switches'].append({'step':0,'to':'recent'})
            x['sha256']=digest(x['state'])
            with self.assertRaises(ValueError,msg=alteration):ChangingEventMemory.restore(x,self.model)

    def test_archive_preserves_original_evidence(self):
        m=self.trained(count=BOOTSTRAP+80)
        self.assertEqual(len(m.events),BOOTSTRAP+80)
        self.assertEqual(len(m._memory()),BOOTSTRAP if m.active=='anchor' else 32)
        self.assertTrue(all(0<=entry['step']<len(m.events) for entry in m.events))

    def test_no_test_feedback_or_premature_eval(self):
        m=self.trained(count=5)
        with self.assertRaises(ValueError):m.choose(0,self.streams[0])
        m=self.trained()
        record=m.record()
        m.choose(0,self.streams[0])
        self.assertEqual(m.record(),record)
        with self.assertRaises(ValueError):m.feedback(True,split='test',step=len(m.events))

    def test_wrong_segmenter_and_mutation_rejected(self):
        m=self.trained()
        other=fit_event_model(self.streams[:4])
        with self.assertRaises(ValueError):ChangingEventMemory.restore(m.record(),other)
        m.model.persistence=.5
        with self.assertRaises(ValueError):m.record()

    def test_phase_alternation_is_hidden_in_benchmark(self):
        from benchmarks.outcome_event_memory_benchmark import preference
        a=preference(self.seed);b=alternate(a)
        self.assertTrue(all(a[i]!=b[i] for i in a))
        self.assertEqual(alternate(b),a)

    def test_cohort_frozen(self):
        with self.assertRaises(ValueError):measure([14003])
        with self.assertRaises(ValueError):measure(list(DEVELOPMENT)+[27007])

if __name__=='__main__':unittest.main()

# Additional regression evidence (kept separate from benchmark scoring).
class ArchiveSwitchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=14009
        cls.streams=[episode(cls.seed,'source_bursts','train',i)['observed'] for i in range(8)]
        cls.segmenter=fit_event_model(cls.streams)

    def test_failure_trigger_and_cooldown_are_replayable(self):
        m=ChangingEventMemory(self.segmenter,self.seed,mode='archive')
        for step in range(BOOTSTRAP+28):
            m.propose(step%2,self.streams[step%8],split='train',step=step)
            m.feedback(False,split='train',step=step)
        self.assertTrue(m.switches)
        self.assertTrue(all(e['step']>=BOOTSTRAP for e in m.switches))
        self.assertTrue(all(b['step']-a['step']>=8 for a,b in zip(m.switches,m.switches[1:])))
        self.assertEqual(ChangingEventMemory.restore(m.record(),self.segmenter).record(),m.record())

    def test_window_never_forgets_immutable_checkpoint_history(self):
        m=ChangingEventMemory(self.segmenter,self.seed,mode='window')
        for step in range(BOOTSTRAP+45):
            m.propose(step%2,self.streams[step%8],split='train',step=step)
            m.feedback(step%3==0,split='train',step=step)
        self.assertEqual(len(m.events),245)
        self.assertEqual(len(m._memory()),32)
        self.assertEqual(len(ChangingEventMemory.restore(m.record(),self.segmenter).events),245)
