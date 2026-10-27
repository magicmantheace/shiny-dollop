"""Unlabelled mixed-experience proposals; no simulator truth in fit inputs."""
import copy
import math
import unittest

from developmental_ai.mixed_experience import (
    MixedProposal, _agreement, _partition, _validated, fit_mixed,
    mixture_log_likelihood, validation_score, _digest,
)
from developmental_ai.online_dynamics import trajectory, forward_backward
from developmental_ai.structured_landmarks import StructuredModel


def example(seed=17, number=24):
    conditions = [("standard","fixed"), ("high","shifted")]
    fit = [trajectory(seed, "train", i, *conditions[i % 2]) for i in range(number)]
    validation = [trajectory(seed, "train", 10000+i, *conditions[i % 2]) for i in range(12)]
    return fit, validation


class MixedExperienceTests(unittest.TestCase):
    def test_single_model_equivalence(self):
        history = trajectory(17, "test", 70500)
        model = StructuredModel()
        self.assertAlmostEqual(mixture_log_likelihood([model],history),
                               forward_backward(model,history),places=10)
        self.assertAlmostEqual(validation_score([model],[history]),
                               forward_backward(model,history)/12,places=10)

    def test_two_identical_models_are_same_likelihood(self):
        h = trajectory(17,"test",70501)
        model = StructuredModel()
        self.assertAlmostEqual(mixture_log_likelihood([model,model],h),
                               forward_backward(model,h),places=10)

    def test_odometry_initialization_uses_observed_information(self):
        fit,_ = example()
        before = copy.deepcopy(fit)
        groups = _partition(fit,"odometry",10)
        self.assertEqual(len(groups),2)
        self.assertEqual(groups[0]|groups[1],set(range(len(fit))))
        self.assertFalse(groups[0]&groups[1])
        self.assertEqual(fit,before)
        self.assertTrue(all(0 <= _agreement(h) <= 1 for h in fit))

    def test_one_model_fallback_returns_existing_baseline(self):
        fit,validation = example()
        p = fit_mixed(fit,validation,iterations=1,rounds=1, min_validation_gain=.5)
        self.assertFalse(p.accepted)
        self.assertEqual(p.kind,"single")
        self.assertEqual(len(p.models),1)
        self.assertEqual(p.models[0].state(),p.baseline.state())
        self.assertEqual(p.select(validation[:2]),0)

    def test_prevents_privileged_regime_and_position_records(self):
        fit,validation = example()
        modified = copy.deepcopy(fit)
        modified[0]["condition"] = "high"
        with self.assertRaises(ValueError):
            fit_mixed(modified,validation,iterations=1,rounds=1)
        modified = copy.deepcopy(fit)
        modified[0]["position"] = 3
        with self.assertRaises(ValueError):
            fit_mixed(modified,validation,iterations=1,rounds=1)

    def test_overlapping_evidence_rejected(self):
        fit, validation = example()
        validation[0] = copy.deepcopy(fit[2])
        with self.assertRaisesRegex(ValueError,"overlap"):
            fit_mixed(fit,validation,iterations=1,rounds=1)

    def test_duplicate_evidence_rejected(self):
        fit,validation = example()
        fit[0] = copy.deepcopy(fit[1])
        with self.assertRaises(ValueError):
            fit_mixed(fit,validation,iterations=1,rounds=1)

    def test_invalid_hyperparameters_rejected(self):
        fit,validation = example()
        for options in ({"iterations":0}, {"rounds":0}, {"min_validation_gain":-.01},
                        {"seed":True},{"min_group":100}):
            with self.subTest(options=options),self.assertRaises(ValueError):
                fit_mixed(fit,validation,**options)

    def test_mixed_fit_is_deterministic_and_does_not_mutate_evidence(self):
        fit,validation=example()
        original=copy.deepcopy((fit,validation))
        first=fit_mixed(fit,validation,iterations=2,rounds=1)
        second=fit_mixed(fit,validation,iterations=2,rounds=1)
        self.assertEqual(first.record(),second.record())
        self.assertEqual((fit,validation),original)

    def test_roundtrip_seed_model_and_evidence_bound(self):
        fit,validation=example()
        proposed=fit_mixed(fit,validation,iterations=1,rounds=1)
        record=proposed.record()
        restored=MixedProposal.restore(copy.deepcopy(record),17)
        self.assertEqual(restored.record(),record)
        self.assertEqual(restored.evidence["fit_count"],len(fit))
        self.assertEqual(restored.evidence["validation_count"],len(validation))
        with self.assertRaises(ValueError):
            MixedProposal.restore(record,23)

    def test_digest_and_schema_tampering_rejected(self):
        fit,validation=example()
        p=fit_mixed(fit,validation,iterations=1,rounds=1)
        r=p.record()
        altered=copy.deepcopy(r)
        altered["state"]["validation"]["delta"]=123
        with self.assertRaises(ValueError):
            MixedProposal.restore(altered,17)
        altered["sha256"]=_digest(altered["state"])
        altered["state"]["models"][0]["schema"]="random-schema"
        altered["sha256"]=_digest(altered["state"])
        with self.assertRaises(ValueError):
            MixedProposal.restore(altered,17)

    def test_select_abstains_when_evidence_weak(self):
        fit,validation=example()
        proposal=fit_mixed(fit,validation,iterations=1,rounds=1)
        if proposal.accepted:
            # Near-identical hypotheses produce an honest abstention.
            proposal.models=(proposal.models[0], proposal.models[0])
            self.assertIsNone(proposal.select(validation[:2],threshold=.8))
        else:
            self.assertEqual(proposal.select(validation[:2]),0)
        with self.assertRaises(ValueError):
            proposal.select(validation[:2],threshold=1.5)

if __name__ == "__main__":unittest.main()
