# Continuous dynamics detection (`continuous-dynamics/v1`)

This is a **simulation-only**, reviewable experiment in reusing prior learned dynamics without knowing the current environment's label. It is not a continuously conscious agent, general world model, autonomous new-regime training, real-time action controller, or a stable AthenZ/Synveil service API.

## Protocol and trust boundary

- Train two models offline using `online_dynamics.fit` on ordinary (initial beacon, commanded action, odometry, landmark) histories. The fitter knows ring topology and the observation vocabulary, **not hidden subsequent positions**. No human source records are included.
- Store the two models as immutable, seed-bound SQLite records using `ModelBank.save`. Preserve each model's SHA-256 content hash and schema. An opened `StreamMonitor` binds itself to the complete bank fingerprint. If the bank is changed, it rejects a stored monitor state until a new reviewed monitor session is started.
- The caller supplies **one bounded episode's history at a time**. This is continuous *episode-by-episode* detection, **not per-frame inference** and not an unattended system daemon. A four-episode rolling window is scored against known models with marginal latent-state observation likelihood, using no simulator regime identifiers.
- With at least four episodes, require the leading model's log-likelihood per observation to exceed the runner-up by 0.12 and repeat the same candidate decision twice before selecting it. The selector can report `warming`, `uncertain`, `switch`, or `stable`. An absolute likelihood floor can instead report `unknown`; the floor is a heuristic **not yet calibrated for novel-environment detection**. A status of `unknown` or no selected model should prevent acting in a real adapter (none exists).
- The state and a hash-linked, simulation-only event record are committed in one SQLite transaction. Reload validates schema, seed, configuration, bank fingerprint, checkpoint digest and the last event. `events()` validates the full event sequence. These digests reveal ordinary accidents or unsophisticated edits; they are **not signatures, independent execution attestations, or authorization credentials**. No shell, network, model install/promotion, privacy-sensitive identity import, or OS mutation is implemented.

## Reproduce

```sh
python -m unittest discover -s tests -v
python -m benchmarks.continuous_dynamics_benchmark --seeds 17 23 41 --out benchmarks/continuous_dynamics_results.json
python -m benchmarks.continuous_dynamics_benchmark --seeds 1009 1013 1031 --out benchmarks/continuous_dynamics_audit_results.json
python -m benchmarks.continuous_dynamics_benchmark --seeds 1009 1013 1031 --train-episodes 160 --iterations 6 --phase-episodes 20 --navigation-episodes 10 --out benchmarks/continuous_dynamics_low_budget_results.json
python -m benchmarks.transfer_benchmark
```

Example for manual streaming (model bank is created independently by `python -m developmental_ai.online_dynamics train` with two different model names):

```sh
python -m developmental_ai.continuous_dynamics --models-db private-models.db --monitor-db private-stream.db --noise standard --layout fixed --episodes 20 --start-index 6000
python -m developmental_ai.continuous_dynamics --models-db private-models.db --monitor-db private-stream.db --noise high --layout shifted --episodes 20 --start-index 6020
```

**Do not commit database files.** Example regime flags above are used to generate a synthetic test stream; the selector receives only observation histories. Use different, non-overlapping index ranges when resuming.

## Development results (not blind)

The deterministic benchmark uses three 25-episode phases: standard motion/fixed landmarks → high noise/shifted landmarks → original conditions again. All training comes from the `train` namespace; all stream evidence comes from the `test` namespace (indices starting at 6000). Navigation uses other `test` indices (starting at 10000), scored separately at the **end** of each phase. Model selection never sees navigation outcomes. Each model is fitted from 350 twelve-step histories and ten EM iterations; trials are generated deterministically from the fixed seeds.

| Seed | First original selection | First changed selection | First returned-original selection | Changed-world navigation, selected vs fixed-original vs true-physics oracle |
| --- | ---: | ---: | ---: | --- |
| 17 | 5 | 4 | 3 | 26.7% / 6.7% / 46.7% |
| 23 | 5 | 4 | 4 | 33.3% / 20.0% / 26.7% |
| 41 | 9 | 4 | 4 | 46.7% / 20.0% / 53.3% |

A separately checked set of seeds 1009/1013/1031, with the **same full training and evaluation budget**, selected the changed regime after 5/5/8 episodes and the restored original after 5/4/4 episodes. Changed-world navigation with selected models was 53.3%/46.7%/53.3%, versus 13.3%/26.7%/20.0% using the wrong, original model. These seeds were not tuned in this pass, but this is still an internally inspected audit, **not an independently administered blind benchmark**.

**Training-budget sensitivity (retained negative result):** with 160 histories, six EM iterations and a 20-episode phase, the same three audit seeds failed to select the changed model on 1009 and 1031; 1013 switched only after episode 13. Different navigation-trial counts and phase lengths mean the two budgets cannot be used as a controlled comparison of navigation percentages. This failure is important: more robust model uncertainty estimation and calibration data efficiency are still open problems.

## Limitations and next gates

1. Observations are from a known 9/11-position ring, with an explicit first-position beacon, a fixed two-action vocabulary, and two already-trained models. The environment is simulated and regime transitions happen only **between** episodes.
2. The selector's thresholds and two known environments were inspected during development. There is no guarantee it will recognize truly novel regimes, sensor dropout, an adversary, or out-of-family geometries. A scoring margin is not a calibrated confidence probability.
3. A returned snapshot can preserve prior knowledge, but this is **model retrieval**, not solved lifelong learning or automatic new-model discovery. There is no learner policy change or automatic weight promotion.
4. End-of-phase navigation is evaluated using the selected model, not a fully integrated closed-loop online controller that changes models mid-navigation. Simulation outcomes are not exposed to selection.
5. Next: causal on-device per-step streaming, independent ablation of likelihood/margin/window choices, more diverse hidden regimes, calibrated novelty detection with abstention, and bounded candidate-model training with human-reviewed promotion. Keep AthenZ identity and Synveil action-policy boundaries separate.
