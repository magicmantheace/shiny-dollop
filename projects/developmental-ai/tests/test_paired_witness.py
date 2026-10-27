"""Signed witness research tests: event integrity is not truth."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.paired_witness import (
    PairedWitnessGate,sign_observation,sign_archive,RECORDS
)
from developmental_ai.passive_outcome_learning import PassiveOutcomeArchive
from benchmarks.paired_witness_benchmark import (
    DEV,RESERVED,TEST_N,TRAIN_START,keys_for_seed,
    training_and_claims,simulate_test,measure
)


class PairedWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        (cls.actor,cls.forged,cls.changes,cls.keys,
         cls.claims)=training_and_claims(cls.seed)
        cls.verifier=PairedWitnessGate(cls.keys)

    def test_independently_keyed_honest_pair_can_be_verified(self):
        accepted=self.verifier.assess(*self.claims["two_honest_signers"])
        self.assertTrue(accepted["approved"])
        self.assertTrue(accepted["fixture_signatures_verified"])
        self.assertFalse(accepted["physical_truth_verified"])
        self.assertEqual(accepted["paired_events"],RECORDS)
        self.assertEqual(accepted["archive"].record(),self.actor.record())

    def test_independent_honest_witness_catches_changed_claims(self):
        rejected=self.verifier.assess(*self.claims["forged_primary_honest_witness"])
        self.assertFalse(rejected["approved"])
        self.assertEqual(rejected["reason"],"witness_disagreement")
        self.assertIsNone(rejected["archive"])

    def test_missing_witness_must_not_deploy_observer_model(self):
        rejected=self.verifier.assess(*self.claims["missing_witness"])
        self.assertFalse(rejected["approved"])
        self.assertEqual(rejected["reason"],"missing_witness_or_count")

    def test_post_signature_tampering_is_rejected(self):
        rejected=self.verifier.assess(*self.claims["post_signature_tamper"])
        self.assertFalse(rejected["approved"])
        self.assertEqual(rejected["reason"],"invalid_witness_mac")

    def test_two_colluding_fixture_signers_can_authorize_a_lie(self):
        compromised=self.verifier.assess(*self.claims["forged_primary_colluding_witness"])
        self.assertTrue(compromised["approved"])
        self.assertTrue(compromised["fixture_signatures_verified"])
        self.assertFalse(compromised["physical_truth_verified"])
        self.assertEqual(compromised["archive"].record(),self.forged.record())
        self.assertGreater(self.changes,0)

    def test_swapped_keys_and_duplicate_roles_are_rejected(self):
        with self.assertRaises(ValueError):
            PairedWitnessGate({"primary":self.keys["primary"],
                               "witness":self.keys["primary"]})
        verifier=PairedWitnessGate({"primary":self.keys["witness"],
                                    "witness":self.keys["primary"]})
        result=verifier.assess(*self.claims["two_honest_signers"])
        self.assertFalse(result["approved"])
        self.assertEqual(result["reason"],"invalid_primary_mac")

    def test_signed_record_with_wrong_role_or_key_fails(self):
        record=self.actor.events[0]
        with self.assertRaises(ValueError):
            sign_observation(record,"third",self.keys["primary"])
        wrong=sign_observation(record,"witness",self.keys["primary"])
        honest=sign_archive(self.actor,"primary",self.keys["primary"])
        witness=copy.deepcopy(self.claims["two_honest_signers"][1])
        witness[0]=wrong
        result=self.verifier.assess(honest,witness)
        self.assertEqual(result["reason"],"invalid_witness_mac")

    def test_pair_receipt_contains_no_secret_keys(self):
        result=self.verifier.assess(*self.claims["two_honest_signers"])
        receipt=self.verifier.receipt(result)
        self.assertEqual(len(receipt["sha256"]),64)
        self.assertNotIn(self.keys["primary"].hex(),str(receipt))
        self.assertNotIn(self.keys["witness"].hex(),str(receipt))
        self.assertFalse(receipt["state"]["physical_truth_verified"])

    def test_train_action_harm_is_not_duplicated_by_forgery(self):
        self.assertEqual(len(self.actor.events),RECORDS)
        self.assertEqual(self.actor.stats()["actor_harmful_actions"]-
                         self.forged.stats()["actor_harmful_actions"],
                         self.changes)
        self.assertEqual(self.actor.stats()["learner_generated_training_actions"],0)

    def test_sandbox_oracle_feasible_and_no_witness_means_no_tasks(self):
        case=simulate_test(self.seed,25000,"privileged_true_effect_oracle",None)
        self.assertEqual(case["success"],1)
        self.assertEqual(case["hurt"],0)
        missing=simulate_test(self.seed,25000,"missing_witness",None)
        self.assertEqual(missing["success"],0)
        self.assertEqual(missing["abstained"],1)

    def test_frozen_cohorts_and_sizes(self):
        self.assertEqual((RECORDS,TEST_N),(240,60))
        for bad in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):
                measure(bad)


if __name__=="__main__":
    unittest.main()
