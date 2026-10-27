# Calibrated environment model, adaptation and retention (experimental)

**Status:** local simulated calibration, not a general learned world model, autonomous exploration, or real-world robotics.

## Research question

Can a small agent **estimate** movement, odometry and landmark statistics from labeled experiences, use those estimates to maintain a hidden-position belief, and adapt when the simulator's physical rules change? Can it preserve a prior model rather than overwrite it completely?

## Protocol and information separation

- `CalibrationWorld` is a 9- or 11-location ring with an initial target beacon, stochastic movement, noisy odometry, and intermittent landmarks.
- During **calibration**, a privileged simulation instrument provides the realized movement delta and true resulting position. These truth values are used to estimate three categorical models: `P(realized motion | commanded motion)`, `P(odometry | realized motion)`, and `P(landmark reading | exact position, ring size)`.
- The model learns by counting instrumented outcomes with Dirichlet smoothing and exponential decay (`0.997` per observation). This is parameter estimation from **supervised ground-truth instrumentation**, not latent dynamics learned from ordinary observations alone.
- During **navigation**, the policy receives only odometry, landmark observations and a one-time goal beacon. The filter uses the learned probabilities; it never receives the privileged calibration position. A **hand-coded** greedy controller chooses movements; this milestone trains no neural policy and invents no goals.
- The environment transitions from `standard/fixed` to `high/shifted`: correct movement and odometry become less likely; both landmark locations shift by two positions. Experimental condition labels are supplied to the *benchmark simulator* and calibration procedure, not to the navigator as a hidden target position. One fixed model is compared with an adapted model in the **same** changed evaluation environment.
- Independent seeds are used for procedurally generated `train` and `test` samples by SHA-256 namespace. Reported seeds `17,23,41` were inspected during development: **not a blind study**. Landmark positions, classes and ring geometry remain engineered and known.
- A privileged `KnownPhysicsOracle` is included to quantify remaining performance headroom. The oracle is not available to the learning agent.

## Benchmark

```bash
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
python -m benchmarks.adaptive_dynamics_benchmark --seeds 17 23 41 --calibration-samples 1800 --test-episodes 300 --out benchmarks/adaptive_dynamics_results.json
```

Each seed trains on 1,800 supervised standard/fixed samples, preserves a named snapshot, then trains on 1,800 supervised high/shifted samples. Each condition evaluates against 300 held-out generated environments. Results below are averages of three **inspected** development seeds; complete per-seed records are in `benchmarks/adaptive_dynamics_results.json`.

| Model/condition | Held-out mean negative log likelihood (lower better) | Navigation success |
| --- | ---: | ---: |
| Uniform uninformed model / changed | 3.296 | 0.0% |
| Trained standard / original | 1.786 | 86.9% |
| Frozen standard / changed | 3.433 | 16.7% |
| Adapted to high-noise shifted-landmarks / changed | 2.268 | 53.4% |
| Privileged true-probability oracle / changed | 2.218 | 57.8% |
| Adapted model / original (without model selection) | 2.817 | 13.1% |
| Saved original snapshot / original | 1.786 | 86.9% |

Adaptation significantly improves the new task relative to using an obsolete model, but also **causes catastrophic forgetting** if the updated model is used for the old regime. Immutable named snapshots retain the original model; selecting the correct snapshot is currently a **manual caller responsibility**. No automatic context detection or learned model routing is implemented.

## Run directly

```bash
python -m developmental_ai.adaptive_dynamics train --db local_calibration.db --seed 17 --samples 1800 --noise standard --layout fixed
python -m developmental_ai.adaptive_dynamics snapshot --db local_calibration.db --seed 17 --name original
python -m developmental_ai.adaptive_dynamics train --db local_calibration.db --seed 17 --samples 1800 --noise high --layout shifted
python -m developmental_ai.adaptive_dynamics evaluate --db local_calibration.db --seed 17 --samples 300 --noise high --layout shifted
python -m developmental_ai.adaptive_dynamics evaluate-snapshot --db local_calibration.db --seed 17 --name original --samples 300 --noise standard --layout fixed
```

Training persists only at the **end of each explicitly invoked batch**. The checkpoint stores a seed, schema, monotonic training index and model parameters in SQLite. Snapshots are immutable name-keyed parameter copies and use a SHA-256 corruption check; hashes do not authenticate authorship or prevent a malicious database editor from recomputing them. Snapshots are not a complete backup of any AthenZ profile and do not include any human-origin information.

## Limitations and next steps

This is a small supervised calibration benchmark, not self-supervised model learning. There are no real sensors, inference network, unrestricted tools, neural weights, AthenZ integration, or Synveil services. A meaningful next stage must infer sensor reliability from uninstrumented interaction, learn when to switch between memory models using observations, test new unseen regime families, and retain previous task performance under model changes. A fully blind evaluation protocol must be frozen before reporting generalization claims.
