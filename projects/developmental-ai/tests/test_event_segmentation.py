"""Raw-only fit, bounded streaming recall and independent checkpoint replay."""
import copy
import math
import unittest
from developmental_ai.environment_api import digest
from developmental_ai.event_segmentation import EventSpanMemory, fit_event_model, EventSegmentationModel, _posterior
from benchmarks.event_segmentation_benchmark import episode, longest_raw_run, measure, DEVELOPMENT

class EventSegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.streams=[episode(14003,"source_bursts","train",i)["observed"] for i in range(12)]
        cls.model=fit_event_model(cls.streams)

    def test_generated_family_shift_changes_event_lengths(self):
        a=episode(14003,"source_bursts","train",15)
        b=episode(14003,"shifted_bursts","test",92000)
        self.assertEqual(len(a["observed"]),len(a["hidden"]))
        self.assertEqual(len(b["observed"]),len(b["hidden"]))
        self.assertEqual(len(a["true_spans"]),5)
        self.assertEqual(len(b["true_spans"]),6)
        self.assertEqual(a,episode(14003,"source_bursts","train",15))

    def test_fit_receives_no_target_or_latent_data(self):
        with self.assertRaises(ValueError):fit_event_model([{"observed":self.streams[0],"target":1},self.streams[1]])
        with self.assertRaises(ValueError):fit_event_model([[0,1,True],[1,2]])
        with self.assertRaises(ValueError):fit_event_model([[0,4,1],[1,2]])
        with self.assertRaises(ValueError):fit_event_model([self.streams[0]],iterations=5)
        with self.assertRaises(ValueError):fit_event_model(self.streams,iterations=6)

    def test_probabilistic_training_parameters_are_finite(self):
        self.assertTrue(.5<=self.model.persistence<=.985)
        self.assertTrue(.52<=self.model.sensor_accuracy<=.98)
        em,stay,log_lik=_posterior(self.streams[0],self.model.persistence,self.model.sensor_accuracy)
        self.assertTrue(math.isfinite(log_lik))
        self.assertTrue(0<=em<=len(self.streams[0]))
        self.assertTrue(0<=stay<=len(self.streams[0])-1)

    def test_viterbi_and_raw_run_on_clean_segments(self):
        stream=[0]*12+[1]*3+[2]*4
        self.assertEqual(self.model.recall(stream),0)
        self.assertEqual(longest_raw_run(stream),0)
        self.assertEqual(len(self.model.decode(stream)),len(stream))
        self.assertEqual(self.model.spans(stream)[0]["start"],0)

    def test_model_restore_exact_training_replay(self):
        record=self.model.record()
        self.assertEqual(EventSegmentationModel.restore(copy.deepcopy(record)).record(),record)
        self.assertEqual(fit_event_model(self.streams).record(),record)

    def test_rehashed_forged_parameters_rejected(self):
        r=copy.deepcopy(self.model.record())
        r["state"]["persistence"]=.5
        r["sha256"]=digest(r["state"])
        with self.assertRaises(ValueError):EventSegmentationModel.restore(r)

    def test_streaming_memory_replay_and_restart(self):
        session=EventSpanMemory(self.model)
        for item in self.streams[0][:15]:session.observe(item)
        snap=session.snapshot()
        recovered=EventSpanMemory.restore(copy.deepcopy(snap),self.model)
        self.assertEqual(session.snapshot(),recovered.snapshot())
        for item in self.streams[0][15:]:
            self.assertEqual(session.observe(item),recovered.observe(item))
        self.assertEqual(session.snapshot(),recovered.snapshot())

    def test_memory_rehashed_forged_spans_and_model_mismatch(self):
        memory=EventSpanMemory(self.model)
        for token in self.streams[0][:5]:memory.observe(token)
        r=memory.snapshot()
        bad=copy.deepcopy(r)
        bad["state"]["retained"]=(bad["state"]["retained"]+1)%4
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):EventSpanMemory.restore(bad,self.model)
        other=fit_event_model(self.streams[:6])
        with self.assertRaises(ValueError):EventSpanMemory.restore(r,other)

    def test_bounds_and_bool_inputs(self):
        memory=EventSpanMemory(self.model)
        for token in (True,-1,4,"0",None):
            with self.assertRaises(ValueError):memory.observe(token)
        with self.assertRaises(ValueError):self.model.decode([True,1])
        with self.assertRaises(ValueError):self.model.decode([])

    def test_mid_session_model_mutation_fails_closed(self):
        memory=EventSpanMemory(self.model)
        memory.observe(0)
        memory.model.persistence=.5
        with self.assertRaises(ValueError):memory.observe(1)
        with self.assertRaises(ValueError):memory.snapshot()
        self.assertEqual(memory.tokens,[0])

    def test_bad_checkpoint_structure(self):
        memory=EventSpanMemory(self.model)
        memory.observe(0)
        record=memory.snapshot()
        forged=copy.deepcopy(record)
        forged["state"]["tokens"].append(True)
        forged["sha256"]=digest(forged["state"])
        with self.assertRaises(ValueError):EventSpanMemory.restore(forged,self.model)

    def test_frozen_protocol_rejects_noncohort(self):
        with self.assertRaises(ValueError):measure([14003])
        with self.assertRaises(ValueError):measure(list(DEVELOPMENT)+[27007])

if __name__=="__main__":unittest.main()
