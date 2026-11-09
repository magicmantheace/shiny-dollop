# Unlabeled sensor history and automatic model reuse (`online-dynamics/v1`)

**Status: development experiment; no live AthenZ/Synveil integration.**

## What changed

Previous `adaptive_dynamics` calibration fits parameters from **privileged** labels: the actual movement displacement and true position after every action. This independent experimental module removes those labels from the learner. A simulator produces a sequence of ordinary **movement commands**, **noisy odometry**, and **intermittent landmark sightings**, plus the **initial position** that is legitimately shown in the first beacon. Neither later true positions nor actual displacements, goals, rewards, regime names or physics coefficients enter the fitting algorithm.

`fit()` performs forward-backward expected transition counting (categorical expectation maximization) over hidden ring positions. It estimates separate probabilities for commanded movement, odometry conditioned on hidden displacement, and landmark appearances at latent positions. The transition structure, number of positions (9 or 11), action vocabulary, and observation vocabulary are **engineered and known**. This is not a neural or universal world model, and it fits retrospectively to a collected batch rather than learning continuously on every live step.

A SQLite `ModelBank` saves **immutable**, digest-checked model snapshots. `select()` compares marginal observation log likelihood on a fresh batch of **ordinary probe sequences** and selects the highest-scoring candidate; it never receives the simulator's regime label. Probes are conducted before a separate set of navigation episodes in the benchmark. It does **not** identify the correct regime with certainty, discover new modes, select mid-episode, or autonomously decide when to collect probes. There is no system-action executor.

## Reproduce the development protocol

```sh
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
python -m benchmarks.adaptive_dynamics_benchmark --seeds 17 23 41 --calibration-samples 1800 --test-episodes 300
python -m benchmarks.online_dynamics_benchmark --seeds 17 23 41 --train-episodes 350 --train-steps 12 --iterations 10 --probe-episodes 50 --navigation-episodes 100
```

All reported online-model training uses indices `train/0..349`, selection uses `test/0..49`, and final navigation uses `test/1000..1099`. Source-world settings are used solely by the simulator to generate those histories and later to score the outcomes; they are **never** included in the model input. Benchmarked regimes are `(standard, fixed)` and `(high, shifted)`. Seeds are **inspected development seeds, not blind**. Report all three seeds, model-selection accuracy, predictive likelihood, navigation success and wrong-model/oracle comparisons; do not silently average away failures.

Note that the oracle knows the simulator probability distributions and is privileged. The learned model can sometimes exceed the oracle on 100 finite navigation episodes due to model misspecification, navigation heuristic interactions, and sampling noise; this should not be described as objectively better knowledge of physics. Predictive log likelihood is the proper distributional comparison.

## Recorded results

| Set | Regime | Selected bank model success | Wrong model | Known-physics oracle |
| --- | --- | ---: | ---: | ---: |
| Development (17/23/41) | Standard + fixed landmarks | 84.7% | 14.0% | 79.7% |
| Development (17/23/41) | High noise + shifted landmarks | 41.7% | 16.0% | 54.0% |
| Post-development audit (101/303/707) | Standard + fixed landmarks | 85.7% | 14.0% | 81.3% |
| Post-development audit (101/303/707) | High noise + shifted landmarks | 33.3% | 14.7% | 58.0% |

The bank selected the correct candidate on all 12 tested regime/seed combinations,
using separate probe sequences. The audit seeds were picked after the algorithm
and development protocol were fixed; no algorithm tuning followed inspection.
This is an additional **post-development seed audit**, not a statistically
representative blind, external evaluation. The high-noise audit performs worse
than development: **33.3% vs 58.0% for the oracle**. Do not hide this gap.
Exact six-seed per-regime predictive likelihoods, train schedules, selection
scores, and navigation outcomes are in `benchmarks/online_dynamics_results.json`
and `benchmarks/online_dynamics_audit_results.json`.

## Limits and next experiments

- Model learning assumes the initial true position is revealed and the ring size is known. Without a start-position beacon, latent coordinates are not anchored.
- Environment types, observation channel identities, and action effects are known. The agent does not discover new topology, invent sensors or adapt goals.
- Fitting is **batch EM** over unlabeled histories, not a live self-modifying daemon. Saved model names are caller-chosen; names do not act as classification labels inside the selector.
- Changing landmark meanings, unseen noise regimes, spurious landmarks, real-time changepoint detection and model-bank admission remain open.
- SHA-256 integrity checks detect accidental alteration, not adversarial rewriting or proof of simulator authenticity. Private experiments, snapshots and human records belong outside Git; the checked-in benchmark data are synthetic aggregate results only.
- AthenZ and Synveil are optional future consumers of read-only evidence, not direct arbiters of physical actions.
