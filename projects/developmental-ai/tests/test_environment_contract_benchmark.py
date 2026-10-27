"""Evaluation split/manifest protection and cross-family adapter benchmark."""
import unittest
from benchmarks.environment_contract_benchmark import evaluate, load_protocol, run_episode, train_delayed_mapping


class CrossFamilyBenchmarkTests(unittest.TestCase):
    def test_manifest_is_fixed_and_reserved_unavailable_by_default(self):
        p, sha=load_protocol()
        self.assertEqual(len(sha),64)
        self.assertEqual(p["development"]["seeds"],[2749,6607,9901])
        self.assertEqual(p["reserved_not_yet_executed"]["seeds"],[32081,48779])
        with self.assertRaises(ValueError):evaluate(profile="reserved")

    def test_delayed_association_learns_from_reward_only(self):
        mapping=train_delayed_mapping(17,96)
        self.assertEqual(set(mapping),{0,1,2,3})
        self.assertEqual(len(set(mapping.values())),4)

    def test_three_task_types_run_without_privileged_observation(self):
        for family,variant in (("grid","default"),("occluded","default"),("delayed","long")):
            x=run_episode(family,variant,17,"test",60000,"random")
            self.assertGreater(x["steps"],0)
            self.assertGreaterEqual(x["valid_actions"],1)

    def test_deterministic_full_frozen_development_suite(self):
        first=evaluate()
        second=evaluate()
        self.assertEqual(first,second)
        self.assertEqual(len(first["rows"]),18)
        self.assertTrue(all(row["episodes"]==16 and row["valid_action_fraction"]==1 for row in first["rows"]))
        self.assertFalse(first["independent_blind"])

if __name__ == "__main__":unittest.main()
