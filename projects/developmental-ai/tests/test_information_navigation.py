"""Analytic information gain and no-privileged-state controller tests."""
import copy
import math
import unittest
from developmental_ai.adaptive_dynamics import KnownPhysicsOracle, AdaptiveNavigator, navigate
from developmental_ai.information_navigation import (
    InformationNavigator, anticipated_observations, entropy, expected_information_gain,
    run_navigation,
)


class InformationNavigationTests(unittest.TestCase):
    def setUp(self):
        self.model = KnownPhysicsOracle("high", "shifted")

    def test_deterministic_belief_and_uniform_information(self):
        b = [0.] * 9
        b[3] = 1.
        for action in (0, 1):
            gain, predicted = expected_information_gain(b, self.model, action)
            self.assertGreaterEqual(gain, 0)
            self.assertLessEqual(gain, math.log(9) + 1e-8)
            self.assertAlmostEqual(sum(predicted), 1)
        self.assertAlmostEqual(entropy([1.]+[0.]*8), 0)
        self.assertAlmostEqual(entropy([1/9]*9), math.log(9))

    def test_joint_probabilities_match_marginal_predictions(self):
        b = [0.17, 0.08, 0.06, 0.21, 0.04, 0.14, 0.1, 0.12, 0.08]
        for action in (0, 1):
            predicted, joint = anticipated_observations(b, self.model, action)
            for j in range(9):
                self.assertAlmostEqual(predicted[j], sum(joint[o][m][j] for o in range(3) for m in range(3)))

    def test_bayesian_posterior_matches_explicit_observation_conditioning(self):
        b = [1/9.] * 9
        predicted, joint = anticipated_observations(b, self.model, 1)
        navigator = InformationNavigator(0, 4, 9, self.model)
        navigator.probs = b[:]
        navigator.advance(1, {"odometry": 0, "landmark": 1})
        evidence = sum(joint[1][2])
        expected = [p/evidence for p in joint[1][2]]
        for actual, want in zip(navigator.probs, expected):
            self.assertAlmostEqual(actual, want)

    def test_zero_weight_matches_existing_heuristic(self):
        for n in (9, 11):
            for goal in range(n):
                for initial in range(n):
                    original = AdaptiveNavigator(initial, goal, n, self.model)
                    info = InformationNavigator(initial, goal, n, self.model, information_weight=0)
                    self.assertEqual(original.heuristic(), info.choose())
                    original.probs = [1/n]*n
                    info.probs = [1/n]*n
                    self.assertEqual(original.heuristic(), info.choose())

    def test_invalid_beliefs_and_parameters_rejected(self):
        for b in ([-.1]+[1.1/8]*8, [0.]*9, [float('nan')]+[0.]*8, [1.]*9):
            with self.assertRaises(ValueError):
                entropy(b)
        for w in (-1, float('nan'), float('inf'), 4.1, "1", True):
            with self.assertRaises(ValueError):
                InformationNavigator(0, 2, 9, self.model, information_weight=w)
        with self.assertRaises(ValueError):
            expected_information_gain([1/9]*9, self.model, 2)

    def test_legacy_navigation_matches_original_baseline(self):
        for noise, layout in (("standard", "fixed"), ("high", "shifted")):
            physics = KnownPhysicsOracle(noise, layout)
            for index in range(16):
                self.assertEqual(navigate(physics, 17, 18000 + index, noise, layout),
                                 run_navigation(physics, 17, 18000 + index, noise, layout, information_weight=0.))

    def test_benchmark_reproducibility_and_configuration(self):
        from benchmarks.information_navigation_benchmark import measure
        a = measure([17], fitting=3, iterations=1, tune_episodes=2, test_episodes=3)
        self.assertEqual(a, measure([17], fitting=3, iterations=1, tune_episodes=2, test_episodes=3))
        self.assertEqual(a["indices"]["evaluation"], "test/18000+")
        for name, rec in a["rows"][0]["regimes"].items():
            self.assertIn(rec["chosen_weight"], (0., .5, 1.5))
            self.assertTrue(0 <= rec["selected_information"]["cred80_covered"] <= 1)
            self.assertTrue(0 <= rec["selected_information"]["p_true"] <= 1)
        for kwargs in ({"seeds": [17, 17]}, {"seeds": []}, {"fitting": 0}, {"iterations": 51}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                measure(**kwargs)

    def test_does_not_mutate_inputs_and_replays_exactly(self):
        b = [1/9.]*9
        old = copy.deepcopy(b)
        expected_information_gain(b, self.model, 0)
        self.assertEqual(b, old)
        first = [run_navigation(self.model, 17, i, "high", "shifted", information_weight=.5) for i in range(5)]
        second = [run_navigation(self.model, 17, i, "high", "shifted", information_weight=.5) for i in range(5)]
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
