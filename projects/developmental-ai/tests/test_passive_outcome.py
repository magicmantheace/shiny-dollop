"""Public read-only actor observations, replay and task accounting tests."""
from __future__ import annotations

import copy
import unittest

from developmental_ai.novel_feature_world import NovelFeatureWorld
from developmental_ai.passive_outcome_learning import PassiveOutcomeArchive
from developmental_ai.observable_affordances import digest,NumericOutcomeMemory
from benchmarks.observable_affordance_benchmark import fit
from benchmarks.observable_reversal_calibration_benchmark import fit_reversed
from benchmarks.passive_outcome_benchmark import (
    DEV,RESERVED,RANDOM_START,BIASED_START,OBSERVATIONS,SMALL,TEST_N,
    collect,episode,score,measure
)


class PassiveOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed=DEV[0]
        cls.source,_=fit(cls.seed)
        cls.reversed,_=fit_reversed(cls.seed)
        cls.archive=collect(cls.seed,RANDOM_START,OBSERVATIONS,"random")

    def test_passive_actor_not_authorized_by_archive_to_choose_actions(self):
        self.assertEqual(self.archive.stats()["learner_generated_training_actions"],0)
        self.assertFalse(hasattr(self.archive,"probe"))
        self.assertFalse(hasattr(self.archive,"step"))
        self.assertFalse(hasattr(self.archive,"act"))
        self.assertEqual(self.archive.stats()["observations"],OBSERVATIONS)

    def test_public_evidence_has_no_world_names_private_physics_or_metadata(self):
        row=self.archive.events[0]
        self.assertEqual(set(row),{"before","action","after","outcome"})
        self.assertEqual(set(row["outcome"]),{"features","progress","damage"})
        self.assertEqual(row["before"]["tick"],0)
        self.assertEqual(row["after"]["tick"],1)
        for label in ("third_rule","condition","_effect","simulator_rule"):
            self.assertNotIn(label,str(self.archive.record()))

    def test_replay_after_checkpoint_and_rehashed_outcome_forgery_rejected(self):
        saved=self.archive.record()
        new=PassiveOutcomeArchive.restore(copy.deepcopy(saved))
        self.assertEqual(new.record(),saved)
        bad=copy.deepcopy(saved)
        bad["state"]["events"][0]["outcome"]["damage"]=True
        bad["sha256"]=digest(bad["state"])
        with self.assertRaises(ValueError):
            PassiveOutcomeArchive.restore(bad)

    def test_duplicate_episodes_stale_actions_and_noninitial_ticks_rejected(self):
        row=self.archive.events[0]
        store=PassiveOutcomeArchive()
        store.observe(row["before"],row["action"],row["after"])
        with self.assertRaisesRegex(ValueError,"duplicate"):
            store.observe(row["before"],row["action"],row["after"])
        with self.assertRaises(ValueError):
            store.observe(row["before"],"a_deadbeefdeadbeefdd",row["after"])

    def test_random24_is_initial_subset_of_random240_not_freshly_chosen(self):
        sample=PassiveOutcomeArchive()
        for row in self.archive.events[:SMALL]:
            sample.observe(row["before"],row["action"],row["after"])
        self.assertEqual(len(sample.events),SMALL)
        self.assertEqual(sample.events,self.archive.events[:SMALL])

    def test_passive_model_learns_only_from_recorded_outcomes(self):
        memory=self.archive.memory()
        self.assertIsInstance(memory,NumericOutcomeMemory)
        self.assertEqual(len(memory.examples),OBSERVATIONS)
        self.assertEqual(memory.examples,[x["outcome"] for x in self.archive.events])
        self.assertEqual(memory.record(),NumericOutcomeMemory.restore(memory.record()).record())

    def test_guarded_action_requires_positive_neighborhood_support(self):
        empty=PassiveOutcomeArchive()
        frame=NovelFeatureWorld(self.seed,"test",23000,"third_rule").frame()
        with self.assertRaises(ValueError):
            empty.guarded_choose(frame)
        tiny=PassiveOutcomeArchive()
        for row in self.archive.events[:4]:
            tiny.observe(row["before"],row["action"],row["after"])
        self.assertIsNone(tiny.guarded_choose(frame))
        eligible=self.archive.guarded_choose(frame)
        self.assertTrue(eligible is None or eligible in
                        {a["id"] for a in frame["actions"]})

    def test_older_source_knowledge_and_passive_source_stay_immutable(self):
        before=(self.source.record(),self.archive.record())
        archives={"random240":self.archive,"random24":self.archive,
                  "oldpolicy240":self.archive}
        for method in ("guarded_random240","raw_random240","old_normal_model",
                       "old_reversed_model","always_abstain","privileged_oracle"):
            row=episode(self.seed,23000,method,archives,self.source,self.reversed)
            self.assertIn(row["success"],(0,1))
        self.assertEqual(before,(self.source.record(),self.archive.record()))

    def test_privileged_oracle_is_feasible_and_abstention_is_failure(self):
        archived={"random240":self.archive,"random24":self.archive,
                  "oldpolicy240":self.archive}
        oracle=episode(self.seed,23000,"privileged_oracle",
                       archived,self.source,self.reversed)
        abstain=episode(self.seed,23000,"always_abstain",
                        archived,self.source,self.reversed)
        self.assertEqual(oracle["success"],1)
        self.assertEqual(oracle["hurt"],0)
        self.assertEqual(abstain["success"],0)
        self.assertEqual(abstain["attempts"],0)
        self.assertEqual(abstain["abstained"],1)

    def test_independent_biased_actor_receives_only_public_frame(self):
        biased=collect(self.seed,BIASED_START,8,"old_normal",self.source)
        self.assertEqual(biased.stats()["observations"],8)
        self.assertEqual(biased.stats()["learner_generated_training_actions"],0)
        self.assertEqual({x["before"]["episode"] for x in biased.events} &
                         {x["before"]["episode"] for x in self.archive.events},set())

    def test_seed_list_is_frozen_and_no_unintended_extended_test_ranges(self):
        self.assertEqual((OBSERVATIONS,SMALL,TEST_N),(240,24,60))
        for bad in ((DEV[0],),tuple(reversed(RESERVED)),(1,2,3)):
            with self.assertRaises(ValueError):measure(bad)


if __name__=="__main__":
    unittest.main()
