# Spatial posterior calibration (`spatial-calibration/v1`)

**Optional, simulation-only, read-only uncertainty diagnostics.** This experiment does not change the navigation controller, model fitting, bank, permissions, AthenZ identity, or Synveil OS. It is **supervised calibration**, not independent discovery of environmental dynamics or evidence of a subjective mind.

## Motivation and method

The learned Bayesian position filter often assigns spatial probabilities that are too diffuse or otherwise poorly calibrated. Accurate *uncertainty reporting* matters separately from task completion: blindly acting on an unreliable belief can be worse than abstaining.

Given an existing learned `DynamicsModel` and its output `p(position | sensor history)`, temperature scaling reports

`q(position) = p(position)^(1/T) / sum_j p(j)^(1/T)`.

`T=1` preserves the original probabilities, `T<1` sharpens diffuse beliefs, and `T>1` flattens them. A small fixed temperature grid is chosen by minimizing location **negative log likelihood** on a **separate, privileged, instrumented calibration set**. The temperature is fitted **only after** an observation-only world-model fit has finished. No true position is supplied to the world model, its sensor filter, or the deployment-time read-only `calibrated_posterior` function. True position **is** supplied to the calibration fitter and measurement harness. The benchmark itself supplies the environmental regime; this module does not discover or select regimes.

The profile is bound to a SHA-256 fingerprint of the learned dynamics model, the evidence digest, explicit `train/5000+` provenance and a strict read-only scope, with validation on load/use. These hashes detect accidental modification, **not** authenticated user approval. Calibration/test samples and private databases must not be committed; committed JSON aggregates contain only measurements.

## Reproduction and evidence separation

```sh
python -m unittest discover -s tests -v
python -m benchmarks.spatial_calibration_benchmark --seeds 17 23 41 --fit 60 --iterations 5 --calibration 40 --evaluation 40 --out benchmarks/spatial_calibration_results.json
python -m benchmarks.spatial_calibration_benchmark --seeds 1009 1013 1031 --fit 60 --iterations 5 --calibration 40 --evaluation 40 --out benchmarks/spatial_calibration_audit_results.json
python -m benchmarks.transfer_benchmark
```

- Model fitting: `train/0..59`, 60 twelve-step **unlabeled** histories per seed/regime; five forward-backward EM iterations.
- Calibration: separate `train/5000..5039`, 40 twelve-step **position-labeled** histories, no model fitting and no evaluation/test evidence.
- Evaluation: `test/40000..40039`, 40 separate twelve-step histories, never used to pick temperature. All seeds are **inspected** and the ring topology, sensor vocabulary, regime grouping and action policy are fixed. Neither cohort is a blinded challenge.
- Metrics: location NLL, multiclass Brier loss, top-1 localization, mean assigned mass to true location, and coverage/size of the smallest 80%-posterior-mass set. The set can overshoot 80% because positions are discrete; exact 80% realized coverage is **not** guaranteed even for a well-calibrated model.
- `KnownPhysicsOracle` knows the correct simulator probability distribution but **not** the real-time hidden position. Its likelihood provides a reference ceiling for predictive-model errors.

## Results and limitations

Mean held-out location negative log likelihood (lower is better; three seeds per cohort):

| Cohort | Condition | Uncalibrated | Calibrated | Correct physics oracle |
| --- | --- | ---: | ---: | ---: |
| Development 17/23/41 | Original | 1.2284 | **1.0862** | 0.8856 |
| Development 17/23/41 | Changed/high noise | 1.6314 | **1.6182** | 1.2500 |
| Inspected audit 1009/1013/1031 | Original | 1.3318 | **1.2270** | 0.9872 |
| Inspected audit 1009/1013/1031 | Changed/high noise | 1.8142 | **1.8100** | 1.2973 |

Six of six original-world seed fits chose `T=0.5` and reduced held-out log-loss. Three of six changed/high-noise seed fits chose `T=1` (no change); three chose `T=0.8` and reduced log-loss. Changed-world uncertainty remains substantially worse than physics-oracle localization. Full per-seed measurements, including any metric regressions and 80% credible-region coverage, are in the two tracked JSON result files.

**No navigation benefit is claimed or measured in this experiment.** Power-posterior scaling does not learn physics, fix landmark misidentification or improve a goal controller. It can be misleading under different distributions, missing sensors or wrong model selection. In particular, the `instrumented_stream` function is an offline research harness reading hidden simulator state and must never be used as the input to a deployment-time agent. No formal risk guarantee, consent assertion, signed profile or human-like cognition is demonstrated. New environments, a general service adapter, and independent prospective reliability trials remain open.
