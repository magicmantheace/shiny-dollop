import copy
import unittest

from developmental_ai.cross_task_retention import RetentionGate, fit_gate, delayed_success, _trial, _validate_frame
from developmental_ai.environment_api import EnvironmentSession, digest
from benchmarks.cross_task_retention_benchmark import measure


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate=fit_gate(2749,episodes=120,validation=48)

    def test_fitted_gate_prefers_initial_information(self):
        self.assertEqual(self.gate.strategy,"initial")
        self.assertGreater(self.gate.scores["initial"],self.gate.scores["latest"])

    def test_restore_and_deterministic_refit(self):
        self.assertEqual(self.gate.record(),fit_gate(2749,episodes=120,validation=48).record())
        self.assertEqual(self.gate.record(),RetentionGate.restore(self.gate.record()).record())

    def test_tampered_snapshot_is_rejected(self):
        record=copy.deepcopy(self.gate.record())
        record["state"]["strategy"]="latest"
        with self.assertRaises(ValueError):RetentionGate.restore(record)
        record["digest"]=digest(record["state"])
        with self.assertRaises(ValueError):RetentionGate.restore(record)

    def test_bad_table_and_nonfinite_inputs_rejected(self):
        r=copy.deepcopy(self.gate.record())
        r["state"]["q"]["initial"]["2"][0]=float("nan")
        with self.assertRaises(ValueError):RetentionGate.restore(r)
        with self.assertRaises(ValueError):fit_gate(2749,episodes=True)
        with self.assertRaises(ValueError):_trial(2749,0,"bad")

    def test_public_observation_schema_rejects_privileged_fields(self):
        frame=EnvironmentSession("delayed",2749,"train",0,variant="short").frame()
        x=copy.deepcopy(frame)
        x["observation"]["correct_action"]=1
        with self.assertRaises(ValueError):_validate_frame(x,0)
        x=copy.deepcopy(frame);x["tick"]+=1
        with self.assertRaises(ValueError):_validate_frame(x,0)

    def test_long_holdout_evaluation_is_read_only(self):
        before=self.gate.record()
        self.assertIsInstance(delayed_success(self.gate,85000),bool)
        self.assertEqual(self.gate.record(),before)

    def test_distinct_train_and_test_index_spaces(self):
        r=measure(seeds=(2749,),train=70,validation=30,episodes=6,updater_episodes=10)
        self.assertFalse(r["blind"])
        self.assertEqual(r["test_indices"]["delayed"],"test/85000+")
        self.assertEqual(set(r["rows"][0]["occluded"]),{"initial","latest","learned"})

    def test_benchmark_reproducible(self):
        a=measure(seeds=(2749,),train=70,validation=30,episodes=5,updater_episodes=10)
        b=measure(seeds=(2749,),train=70,validation=30,episodes=5,updater_episodes=10)
        self.assertEqual(a,b)

if __name__=="__main__":unittest.main()
