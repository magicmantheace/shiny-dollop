"""Probabilistic alignment exactness, public-only boundary and checkpoint tests."""
import copy
import math
import random
import unittest

from developmental_ai.environment_api import digest
from developmental_ai.probabilistic_alignment import (TemporalCorrespondence, marginal_score, exhaustive_score)
from benchmarks.temporal_correspondence_benchmark import measure
from benchmarks.unaligned_stream_benchmark import DEV, ADDITIONAL, stream

MAPPING = (2, 0, 3, 1)


class ProbabilisticCorrespondenceTests(unittest.TestCase):
    def setUp(self):
        self.obs, self.cues, _ = stream(43103, "train", 89400, [2, -1])
        self.model = TemporalCorrespondence(MAPPING, evidence_digest="d" * 64, episodes=240)

    def test_numerical_dp_matches_exhaustive_enumeration(self):
        for seed in range(8):
            rng = random.Random(seed)
            x = ["sensor-%d" % rng.randrange(4) for _ in range(rng.randrange(8, 10))]
            y = ["forecast-%d" % rng.randrange(4) for _ in range(rng.randrange(8, 10))]
            self.assertAlmostEqual(marginal_score(x, y, MAPPING), exhaustive_score(x, y, MAPPING), places=8)

    def test_independent_insertions_supported(self):
        report = self.model.ranked(self.obs, self.cues)
        self.assertEqual(set(report), {"selected", "ranking", "log_scores", "pseudo_posterior", "margin"})
        self.assertEqual(set(report["log_scores"]), set(c[0] for c in self.cues))
        self.assertAlmostEqual(sum(report["pseudo_posterior"].values()), 1.0)
        self.assertGreaterEqual(report["margin"], 0.)

    def test_order_changes_alignment_not_just_counts(self):
        x = ["sensor-0", "sensor-1"] * 4
        y = ["forecast-2", "forecast-0"] * 4
        z = list(reversed(y))
        self.assertNotAlmostEqual(marginal_score(x, y, MAPPING), marginal_score(x, z, MAPPING))

    def test_checkpoint_roundtrip_and_binding(self):
        record = self.model.record()
        restored = TemporalCorrespondence.restore(copy.deepcopy(record))
        self.assertEqual(record, restored.record())
        self.assertEqual(restored.ranked(self.obs, self.cues), self.model.ranked(self.obs, self.cues))

    def test_rejects_corruption_even_rehashed_if_invalid(self):
        for mutation in ("mapping", "schema", "episodes", "digest"):
            value = copy.deepcopy(self.model.record())
            if mutation == "mapping": value["state"]["mapping"] = [0, 0, 2, 3]
            if mutation == "schema": value["state"]["schema"] = "bad"
            if mutation == "episodes": value["state"]["episodes"] = 0
            if mutation == "digest": value["sha256"] = "broken"
            else: value["sha256"] = digest(value["state"])
            with self.assertRaises(ValueError): TemporalCorrespondence.restore(value)

    def test_rejects_privileged_or_malformed_tokens(self):
        for bad in (["sensor-4"] + self.obs[1:], self.obs + ["sensor-1"] * 2,
                    [True] + self.obs[1:]):
            with self.assertRaises(ValueError): self.model.ranked(bad, self.cues)
        changed = copy.deepcopy(self.cues)
        changed[0].append({"oracle": True})
        with self.assertRaises(ValueError): self.model.ranked(self.obs, changed)

    def test_bad_mapping_cannot_appear_as_float_or_duplicate(self):
        for perm in ([0., 1, 2, 3], [1, 1, 2, 3], True, [0, 1, 2]):
            with self.assertRaises(ValueError):TemporalCorrespondence(perm,evidence_digest="d"*64,episodes=240)

    def test_no_test_cohort_mutation(self):
        with self.assertRaises(ValueError): measure((43103,))
        with self.assertRaises(ValueError): measure(tuple(DEV) + tuple(ADDITIONAL))

if __name__ == "__main__": unittest.main()
