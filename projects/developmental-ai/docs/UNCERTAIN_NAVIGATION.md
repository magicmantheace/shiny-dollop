# Uncertain navigation: a noisy one-dimensional ring (experimental)

This milestone studies whether a **learned control policy** can use a **hand-engineered probability distribution over possible locations**, rather than pretending movement commands always succeeded. It is a second, separate simulated task family, **not** a recurrent world model, a biological brain, or autonomous goal generation.

## Protocol

- Independent SHA-256-namespaced train/test episodes; rings have 9 or 11 cells, randomized initial and hidden destination coordinates; the initial observation contains both positions **once**.
- Three actions: left, right, collect. On every attempted move, actual displacement can be correct, stalled, or reversed. Reported odometry is independently noisy. Intermittent, sometimes incorrect landmarks are emitted at two known anchors.
- The `belief` estimator applies an **engineered Bayesian filtering rule** using the configured movement and sensor error probabilities, including likelihoods of landmarks and the absence of detections. It knows the motion model and anchor coordinates. `dead` trusts the noisy displacement report; `reactive` discards the initial positions.
- A tabular Q-policy learns how to select actions from a compressed, hand-crafted location-belief representation. Rewards use hidden simulator distance-to-goal changes for training; **this privileged dense reward is not a sensory observation**. Neither the state estimator nor the observation vocabulary is learned.
- The hand-written heuristic uses the belief distribution to choose the next move, while the full-position oracle sees hidden simulator position and is therefore a privileged upper bound.
- `high` noise changes motion correctness from 70% to 48% and odometry accuracy from 72% to 48%. `no_landmarks` disables anchor detections. These are development-set distribution shifts, not blind independent environments.

```bash
python -m unittest discover -s tests -v
python -m benchmarks.uncertain_navigation_benchmark --seeds 17 23 41 --train-episodes 3000 --test-episodes 200
python -m developmental_ai.uncertain_navigation train --db private_ring.db --seed 17 --episodes 3000
python -m developmental_ai.uncertain_navigation evaluate --db private_ring.db --seed 17
python -m developmental_ai.uncertain_navigation trace --db private_ring.db --policy heuristic > ring_trace.json
python -m developmental_ai.uncertain_navigation verify --trace-file ring_trace.json
python -m developmental_ai.event_ledger export --trace-file ring_trace.json > ring_events.json
python -m developmental_ai.event_ledger verify --trace-file ring_trace.json --ledger-file ring_events.json
```

## Inspected development results

3,000 train episodes per seed, 200 deterministic test episodes per seed. These exact seeds were inspected while building the experiment, so the following is **development evidence**, not an untouched blind holdout. The saved machine-readable report is `benchmarks/uncertain_navigation_results.json`.

| Seed | Untrained | Learned belief | Belief heuristic | Learned high noise | Learned without landmarks | Dead reckoning learner | Reactive learner | Full-position oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 17 | 55.5% | 80.5% | 80.5% | 46.5% | 25.5% | 0% | 0% | 100% |
| 23 | 56.5% | 74.5% | 84.0% | 35.0% | 19.5% | 0% | 0% | 100% |
| 41 | 54.0% | 55.0% | 80.0% | 23.0% | 6.0% | 5.5% | 0% | 100% |

Important limitations:
- Learning is seed-sensitive; seed 41 barely improves after training.
- The untrained policy frequently succeeds through exploratory movement, so improvement is meaningful but modest.
- The estimator knows the actual sensor-error distribution. No adaptation to changed sensor statistics is learned: high-noise evaluation is provided a correctly calibrated alternative estimator and **still** degrades sharply.
- Disabling landmarks is a substantial challenge; 17% average success does not justify real-world navigation claims.
- `dead` and `reactive` use different state representations; comparisons measure a combined estimator-policy intervention, not a pure causal ablation of a single feature.
- The simulator reports dense distance progress as training reward, despite never exposing the destination again as an observation.
- There is no multi-step planning, dynamically learned map, arbitrary novel landmark classification, or human identity model.

## Deterministic recovery and evidence

Trained Q-values and a seed/mode/schema-bound episode counter are saved in SQLite. Train continuation is deterministic for the same episode sequence; evaluation does not alter saved state or weights. The simulation-only trace records sensed signals, compressed estimator states, actions, rewards and terminal results. Verification independently reruns the seeded simulator and estimator. The generic event-ledger exporter can convert verified traces into bounded, hash-chained, read-only simulation events.

Hashes are **not signatures** or proof of a live participant. No trace can authorize an external action; no human or biometric data belongs here.

## Next research gate

Use an uninspected, frozen evaluation protocol across sensor-calibration errors, disappearing or relocated landmarks, changed ring sizes, and an extended two-dimensional problem. Introduce learned observation models only after establishing baselines; keep both successful and failed seeds. The D3 gate remains open.
