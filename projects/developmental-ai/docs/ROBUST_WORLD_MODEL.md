# Multiple-start observational world-model fitting (`robust-world-model/v1`)

This is an **optional, simulation-only experiment**, not a replacement for the previously published `online_dynamics.fit` or an autonomous selector. It addresses one limitation: categorical latent-state expectation maximization (EM) can converge to a weak solution from its fixed initialization.

## Contract

The learner sees only the known ring size, the initial-position beacon, movement commands, odometry and observed landmarks. It never sees hidden subsequent positions, realized motion, the simulator regime, reward or evaluation outcomes. Existing known-topology assumptions remain. The simulator knows its regime only to generate synthetic data and to label **benchmark results**.

`fit_robust(fitting, validation, seed, starts=3, iterations=8)`:

1. Checks each history against the strict ordinary-observation schema and rejects duplicated/overlapping content between fit and validation evidence.
2. Fits candidate zero from the **unchanged** default initializer. Candidate one uses observed (noisy) odometry to suggest weak landmark-location starting counts; further candidates use *seeded random* initial landmark-location and motion guesses.
3. Runs the same number of EM iterations with the same fit histories for every candidate.
4. Scores each candidate on **disjoint** validation histories and returns the highest-likelihood fit, preferring candidate zero on exact ties. Neither the test data nor simulator's hidden state chooses the fit.
5. Returns an auditable, content-digest-bearing lineage receipt. A digest checks accidental modification; it is not authentication, owner consent, a model-approval token or a permission to operate tools.

This design does **not** prevent validation overfitting or guarantee selection gains across unseen environments. Even perfect predictive likelihood need not improve downstream control. This experiment must remain optional pending stronger navigation and independent evaluation.

## Reproduce with equal budgets

```sh
python -m unittest discover -s tests -v
python -m benchmarks.robust_world_model_benchmark --seeds 17 23 41 --train-episodes 90 --validation-episodes 30 --test-episodes 40 --iterations 6 --starts 3 --navigation-episodes 12 --out benchmarks/robust_world_model_results.json
python -m benchmarks.robust_world_model_benchmark --seeds 1009 1013 1031 --train-episodes 90 --validation-episodes 30 --test-episodes 40 --iterations 6 --starts 3 --navigation-episodes 12 --out benchmarks/robust_world_model_audit_results.json
python -m benchmarks.transfer_benchmark
```

Partitions per seed and regime: fit uses `train` indexes 0..89; candidate choice uses `train` 2500..2529; after model selection, predictive testing uses `test` 9000..9039, model-bank regime discrimination uses `test` 16000..16039, and navigation uses independent `test` 14000..14011. These ranges are explicitly chosen and do not overlap. The fitted models never observe the evaluation index/labels while training or selection. All six seeds have previously been inspected by the project, so these are **development/audit** results, not independently blind results.

## Exact outcomes

Three development seeds (17, 23, 41):

| Regime | Baseline mean predictive log-likelihood per observation | Multi-start | Baseline navigation | Multi-start navigation |
| --- | ---: | ---: | ---: | ---: |
| Original | -1.52233 | **-1.48761** | 77.8% | 88.9% |
| Higher noise, shifted markers | -1.68965 | **-1.68842** | 19.4% | **13.9%** |

Three additional, previously inspected audit seeds (1009, 1013, 1031):

| Regime | Baseline mean predictive log-likelihood per observation | Multi-start | Baseline navigation | Multi-start navigation |
| --- | ---: | ---: | ---: | ---: |
| Original | -1.52288 | **-1.47693** | **83.3%** | 72.2% |
| Higher noise, shifted markers | -1.67588 | **-1.67191** | 11.1% | 13.9% |

All **12/12 predictive test pairs** improved slightly or substantially. However, navigation regressed for at least some seeds in each regime and group. Both methods identified both regimes from held-out 40-episode probe batches on all six seeds: **12/12 for each**, so no model-selection-accuracy gain is shown. The per-seed figures and privileged probability-oracle reference scores are preserved in the two machine-readable benchmark files. Navigation sample sizes are only twelve trials per seed and regime, which makes percentages especially noisy.

## Next work

- Learn a stronger representation of localization uncertainty and landmarks rather than only changing EM starting guesses.
- Test predictions and decision coverage on novel landmark patterns, sensor failure and out-of-family environments using pre-registered, untouched seeds.
- Benchmark held-out *navigation* outcomes before considering promotion. Keep a human-reviewed model gate and allow rollback.
- V2A affect/motivation and V2B virtual environment remain planned post-core features, not reasons to override these reliability gates.
