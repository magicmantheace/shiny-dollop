"""Witness observations do not grant action authority or hide their source harm."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.witness_recovery_memory import (
    WitnessRecoveryMemory,BATCH,MAX_WITNESS
)
from developmental_ai.observable_affordances import digest
from benchmarks.independent_witness_benchmark import (
    DEV,ADDITIONAL,CHECKPOINTS,START,TEST_N,METHODS,
    fresh_witness,witnesses,eval_policy,measure,
)
from benchmarks.gated_composition_benchmark import training
from benchmarks.validated_abstention_benchmark import models as original_models


class WitnessRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,cls.cost=training(cls.seed,"source",1000,240)

    def test_unrequested_observation_batch_rejected(self):
        model=fresh_witness(self.source)
        before=model.record()
        if model.can_request_witness():
            # A source model generally passes adequacy. In the unlikely
            # case that it does not, use an invalid size for rejection.
            with self.assertRaises(ValueError):
                model.accept_witness([])
        else:
            batch=training(self.seed,"conditional",510000,8)[0]
            with self.assertRaises(ValueError):
                model.accept_witness(batch)
        self.assertEqual(model.record(),before)

    def test_witness_transaction_refuses_malformed_observation(self):
        model=fresh_witness(self.source)
        # Bypass predictive adequacy in this strictly syntactic test;
        # acceptance is still transactional and must not partially mutate.
        model._cache=({"meets_adequacy_gate":False},None)
        public=training(self.seed,"xor",530000,8)[0]
        public[4]={"features":{"fake":1,"outlet":2},
                   "progress":True,"damage":False}
        before=model.record()
        with self.assertRaises(ValueError):
            model.accept_witness(public)
        self.assertEqual(model.record(),before)
        self.assertEqual(model.witness_count,0)

    def test_witness_budget_enforced_and_round_trip(self):
        model=fresh_witness(self.source)
        for count in range(0,MAX_WITNESS,BATCH):
            model._cache=({"meets_adequacy_gate":False},None)
            self.assertTrue(model.can_request_witness())
            batch=training(self.seed,"xor",530100+count,BATCH)[0]
            model.accept_witness(batch)
            self.assertEqual(model.witness_count,count+BATCH)
            saved=model.record()
            restored=WitnessRecoveryMemory.restore(copy.deepcopy(saved))
            self.assertEqual(restored.record(),saved)
        self.assertFalse(model.can_request_witness())
        model._cache=({"meets_adequacy_gate":False},None)
        with self.assertRaises(ValueError):
            model.accept_witness(training(self.seed,"xor",530140,8)[0])

    def test_hashed_checkpoint_forgery_and_duplicate_metadata_rejected(self):
        model=fresh_witness(self.source)
        original=model.record()
        bad=copy.deepcopy(original)
        bad["state"]["witness_count"]=3
        with self.assertRaises(ValueError):
            WitnessRecoveryMemory.restore(bad)
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            WitnessRecoveryMemory.restore(bad)
        self.assertEqual(model.record(),original)

    def test_actor_costs_counted_as_independent_external_actions(self):
        policy=fresh_witness(self.source)
        trace=witnesses(self.seed,"conditional","conditional",0,policy)
        self.assertEqual(trace["witness_cost"]["observations"],
                         policy.witness_count)
        self.assertEqual(trace["witness_cost"]["observations"],
                         trace["witness_batches"]*BATCH)
        self.assertEqual(sum(trace["witness_cost"][key] for key in
                             ("harmful","productive","neutral")),
                         trace["witness_cost"]["observations"])
        self.assertLessEqual(trace["witness_batches"],4)
        self.assertEqual(set(policy.events[-1]),{"features","progress","damage"})
        self.assertFalse(hasattr(policy,"step"))

    def test_test_eval_readonly_and_explicit_abstention_failure(self):
        trained=original_models(self.source)
        trained["witness_recovery"]=fresh_witness(self.source)
        trained["selective_no_witness"]=trained["validated_abstain"]
        snap=trained["witness_recovery"].record()
        for method in METHODS:
            observation=eval_policy(self.seed,"xor",370000,method,trained)
            self.assertIn(observation["success"],(0,1))
            self.assertIn(observation["harmful_actions"],(0,1))
            if method=="always_abstain":
                self.assertEqual(observation["abstained"],1)
                self.assertEqual(observation["success"],0)
            if method=="perfect_action_oracle":
                self.assertEqual(observation["success"],1)
        self.assertEqual(snap,trained["witness_recovery"].record())

    def test_protocol_indices_no_overlap_with_heldout_TEST_or_base_TRAIN(self):
        self.assertEqual(BATCH,8)
        self.assertEqual(MAX_WITNESS,32)
        self.assertEqual(TEST_N,16)
        self.assertEqual(START,{"conditional":350000,
                                 "return_source":360000,"xor":370000})
        self.assertEqual(CHECKPOINTS["conditional"],(0,8,16,32,64,96))
        self.assertEqual(CHECKPOINTS["return_source"],(0,8,16,32,64))
        self.assertEqual(CHECKPOINTS["xor"],(0,8,16,32,64,96))
        self.assertEqual(len(METHODS),7)
        for phase in (1,2,3):
            for checkpoint in range(6):
                first=500000+phase*10000+checkpoint*100
                self.assertGreaterEqual(first,510000)
                self.assertLess(first+32,540000)
        self.assertNotEqual(DEV,ADDITIONAL)
        for invalid in ((1,2,3),(DEV[0],),tuple(reversed(ADDITIONAL))):
            with self.assertRaises(ValueError):
                measure(invalid)


if __name__=="__main__":
    unittest.main()
