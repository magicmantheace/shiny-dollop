# Information-seeking navigation (`information-navigation/v1`)

**Status:** optional research experiment, *not* a new default policy, real-world adaptation, independent conscious behavior, or V2A affective system. Synthetic 9/11-position ring, one-shot initial-position and target beacon, noisy motion/odometry, intermittent landmarks. The model knows the topology and observation vocabulary. The navigator sees only its probabilistic position belief and ordinary action/sensor results, not hidden simulator positions or regime labels.

## Motivation and mechanism

The existing engineered Bayesian navigator maximizes immediate expected progress toward the hidden target and collects when its belief on the target reaches 0.45. A seemingly plausible improvement is to take informative actions that help localize the agent before attempting the goal.

For each available movement, `information_navigation.expected_information_gain` enumerates the two-dimensional sensor output (three odometry values × three landmark readings), marginalizes three possible physical motions, and estimates **mutual information** between the next position and the observation. The optional controller uses

`utility = - expected next-step target distance + weight × expected information gain`.

`weight=0` follows the historical `AdaptiveNavigator.heuristic` *exactly* and is tested against it. The original Bayes posterior update and 0.45 collect threshold are unchanged. The controller itself is **hand-designed**. Its model may be fitted by observation-only EM, but its exploration objective is not a learned general skill.

## Reproduce the experiment

```sh
python -m unittest discover -s tests -v
python -m benchmarks.information_navigation_benchmark --seeds 17 23 41 --fit 65 --iterations 5 --tune 25 --test 60 --out benchmarks/information_navigation_results.json
python -m benchmarks.information_navigation_benchmark --seeds 1009 1013 1031 --fit 65 --iterations 5 --tune 25 --test 60 --out benchmarks/information_navigation_audit_results.json
python -m benchmarks.transfer_benchmark
```

For each seed and regime, EM model fitting uses only `train` indices 0–64, and possible exploration weights `(0, 0.5, 1.5)` are ranked only on **train** navigation episodes at indices 7000–7024; ties choose zero. Evaluation uses disjoint `test` indices 18000–18059. No test outcome is used to pick the exploration coefficient, although all six seeds have been inspected in previous development, so results are not independently blind. Training-only navigation outcomes are provided by a simulator and used for hyperparameter selection; the controller running a test receives no true positions or rewards.

The benchmark compares the frozen controller, the selected information-seeking controller, and a privileged-**probability** oracle under the frozen controller. It also reports diagnostic **location probability at the actual position**, mean multiclass Brier score, and empirical coverage of a smallest cumulative-80%-posterior credible set. **Only the benchmark scorer sees true position**, never the agent. The nominal 80% threshold is not a calibrated guarantee.

## Results (negative finding; retain all seeds)

**Three development seeds (17/23/41):**

| Regime | Historical heuristic success | Information policy success | Physics oracle success | Historical heuristic Brier | Information policy Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Standard motion / fixed landmarks | 67.2% | 66.1% | 78.9% | 0.511 | 0.513 |
| Higher noise / shifted landmarks | 21.7% | 21.7% | 56.7% | 0.749 | 0.749 |

**Three previously inspected audit seeds (1009/1013/1031):**

| Regime | Historical heuristic success | Information policy success | Physics oracle success | Historical heuristic Brier | Information policy Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Standard motion / fixed landmarks | 61.1% | 61.1% | 81.7% | 0.538 | 0.538 |
| Higher noise / shifted landmarks | 15.6% | 15.6% | 53.3% | 0.778 | 0.779 |

The selection protocol chose zero (i.e. retained the historical heuristic) in 9 of 12 seed/regime cases; in the other three cases weights of 0.5 or 1.5 were selected from training evidence but provided no reliable gain on held-out outcomes. The high-noise models' posterior error is also much higher than the privileged-probability oracle's, explaining why simply rewarding active sensing is unlikely to solve control. No new policy promotion is justified.

**Limitations:** short synthetic rings, engineered goal beacon, known sensor vocabulary, small episode counts (60 per seed/regime), no real-world observability, no novel task families, no independent evaluation team. The oracle uses ground-truth *physics probabilities*, not the agent's true position. The Brier calculation is summed across locations, not divided by number of categories.

## Next research priorities

1. Evaluate posterior calibration and localization reliability separately from task success. Identify model mismatch when the underlying terrain, markers, and sensors differ from training.
2. Improve learned landmark/transition representations; compare posterior error against oracle, ablate sensors, and report non-improvements.
3. Develop a controller that can plan longer than one step and learn when sensing is valuable, but do not deploy until a novel-condition held-out evaluation shows consistent gains and existing candidate-review gates remain intact.
4. Maintain separation from post-core **V2A affective cognition** and **V2B virtual home**. Neither emotional-state estimates nor synthetic world actions grant permissions or provide evidence of subjective experience.
