"""Passive data evidence quality tests: coverage is not provenance."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.novel_feature_world import NovelFeatureWorld
from developmental_ai.passive_outcome_learning import PassiveOutcomeArchive
from developmental_ai.passive_quality import (
    PassiveEvidenceQuality,feature_bin,BINS
)
from benchmarks.observable_affordance_benchmark import fit
from benchmarks.passive_quality_benchmark import (
    DEV,RESERVED,RECORDS,MENU_EPISODES,TEST_N,RANDOM_START,
    BIASED_START,public_opportunities,fabricate_public_damage_as_progress,
    evaluate,measure
)
from benchmarks.passive_outcome_benchmark import collect


class PassiveQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,_=fit(cls.seed)
        cls.random=collect(cls.seed,RANDOM_START,RECORDS,"random")
        cls.biased=collect(cls.seed,BIASED_START,RECORDS,"old_normal",cls.source)
        cls.opportunities=public_opportunities(cls.seed)
        cls.forged,cls.forged_count=fabricate_public_damage_as_progress(cls.random)
        cls.archives={"random":cls.random,"biased":cls.biased,"forged":cls.forged}
        cls.coverage={name:PassiveEvidenceQuality(data,cls.opportunities)
                      for name,data in cls.archives.items()}

    def test_opportunities_have_no_actions_performed(self):
        self.assertEqual(len(self.opportunities),MENU_EPISODES)
        self.assertTrue(all(r["tick"]==0 and r["sensors"]==[0,0]
                            for r in self.opportunities))
        self.assertTrue(all(r["episode"] not in self.random._episodes
                            for r in self.opportunities))

    def test_reference_covers_all_three_public_numeric_regions(self):
        report=self.coverage["random"].report()
        self.assertEqual(set(report["bins"]),set(BINS))
        self.assertTrue(all(a["public_menu_fraction"]>0 for a in report["bins"].values()))
        self.assertEqual(report["recorded_episodes"],RECORDS)
        self.assertEqual(report["opportunity_episodes"],MENU_EPISODES)
        self.assertFalse(report["origin_authenticated"])

    def test_biased_actor_detection_and_unbiased_coverage(self):
        self.assertTrue(self.coverage["random"].report()["coverage_passed"])
        self.assertFalse(self.coverage["biased"].report()["coverage_passed"])

    def test_forged_coherent_public_observations_escape_coverage(self):
        self.assertEqual(self.forged_count,
                         min(60,self.random.stats()["actor_harmful_actions"]))
        self.assertTrue(self.coverage["forged"].report()["coverage_passed"])
        self.assertEqual(self.forged.stats()["observations"],RECORDS)
        self.assertEqual(self.forged.record(),
                         PassiveOutcomeArchive.restore(self.forged.record()).record())
        self.assertLess(self.forged.stats()["actor_harmful_actions"],
                        self.random.stats()["actor_harmful_actions"])
        self.assertFalse(self.coverage["forged"].report()["origin_authenticated"])

    def test_forgeries_not_counted_as_real_changes_to_actor_history(self):
        self.assertEqual(self.random.stats()["observations"],RECORDS)
        self.assertEqual(self.random.stats()["actor_harmful_actions"]-
                         self.forged.stats()["actor_harmful_actions"],self.forged_count)
        self.assertEqual(self.random.record(),
                         PassiveOutcomeArchive.restore(self.random.record()).record())

    def test_reference_overlap_rejected_even_with_rehashed_evidence(self):
        bad=copy.deepcopy(self.random.events[0]["before"])
        with self.assertRaises(ValueError):
            PassiveEvidenceQuality(self.random,[bad])

    def test_observations_can_only_be_replayed_not_authenticated(self):
        receipt=self.coverage["forged"].receipt()
        self.assertEqual(len(receipt["sha256"]),64)
        self.assertFalse(receipt["state"]["origin_authenticated"])
        self.assertTrue(receipt["state"]["coverage_passed"])

    def test_policy_abstains_when_distribution_is_imbalanced(self):
        bad=evaluate(self.seed,24000,"coverage_gated_biased240",
                     self.archives,self.coverage,self.source)
        self.assertEqual(bad,{"success":0,"hurt":0,"stalled":1,
                              "attempts":0,"abstained":1})
        good=evaluate(self.seed,24000,"coverage_gated_random240",
                      self.archives,self.coverage,self.source)
        self.assertIn(good["success"],(0,1))

    def test_privileged_task_solution_and_abstention(self):
        oracle=evaluate(self.seed,24000,"privileged_oracle",
                        self.archives,self.coverage,self.source)
        none=evaluate(self.seed,24000,"always_abstain",
                      self.archives,self.coverage,self.source)
        self.assertEqual(oracle["success"],1)
        self.assertEqual(oracle["hurt"],0)
        self.assertEqual(none["success"],0)
        self.assertEqual(none["abstained"],1)

    def test_feature_bins_are_validated(self):
        self.assertEqual(feature_bin([0,8]),"y_dominant")
        self.assertEqual(feature_bin([8,0]),"x_dominant")
        self.assertEqual(feature_bin([4,4]),"near_equal")
        with self.assertRaises(ValueError):feature_bin([9,3])

    def test_frozen_sizes_and_seed_groups(self):
        self.assertEqual((RECORDS,MENU_EPISODES,TEST_N),(240,60,60))
        for bad in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(bad)


if __name__=="__main__":
    unittest.main()
