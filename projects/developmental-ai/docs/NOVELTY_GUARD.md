# Experimental novelty guard: pause on mismatched sensor evidence

This is an **optional**, local-only, bounded simulation experiment. It does **not** authorize tool use, execute OS operations, learn new physics, or promote a world model. It answers a limited question: *does a stream of ordinary observations fit a previously trained model bank poorly enough to warrant a diagnostic pause?* The established navigator is unchanged.

## Mechanism

1. Fit one or two `StructuredModel` candidates on mixed, observation-only `train` data using the existing `fit_mixed` path; separately select the existing `SwitchingBelief` hazard from `train` records.
2. Hold those models and hazard fixed. Collect **separate** ordinary action/odometry/landmark streams in the `train` namespace. None includes a hidden position, regime, outcome or reward.
3. For each reference stream, compute **the maximum of cumulative mean negative log sensor likelihood** over prefixes 4..36. This is one statistic **per entire stream**, not correlated steps treated as independent samples.
4. Choose an upper-tail threshold with rank `ceil((N+1)*(1-alpha))` across complete reference streams, requiring enough streams for a finite rank. The receipt is bound to model digests, hazard, calibration-evidence digest and version; SHA-256 is **not** a signed authorization or proof that sources are genuine.
5. On a live episode, monitor that same maximum prefix statistic and **latch** an `unknown` diagnostic if the threshold is exceeded. The optional `GuardedNavigation` adapter then **stops suggesting further actions** (`None`), never fabricates a new action, and never updates the trained models. A paused run requires an explicit new session or external intervention; a warning has no system privileges.

The guard stores an inspectable bounded event log, a versioned model-bound snapshot and exact replay-based restart validation. `GuardedCheckpoint` atomically saves the navigation session and guard record in SQLite. Neither normal app UI text nor the monitor's diagnostic state represents subjective experience, confidence about safety, or owner permission.

The quantile is only a *conditional*, exchangeability-dependent statistical construction. Changing action-selection policy, sensor distribution, correlation across episodes, or calibration data selection can invalidate the assumed false-alarm behavior. In particular, calibrating from random probe motions does not guarantee an alpha false-stop rate under closed-loop navigation.

## Reproduction

```sh
python -m unittest tests.test_novelty_guard tests.test_closed_loop_adaptation tests.test_switching_belief tests.test_mixed_experience tests.test_structured_landmarks -q
python -m benchmarks.novelty_guard_benchmark --seeds 17 23 41 --train 48 --validation 16 --hazard-calibration 12 --reference 64 --iterations 2 --rounds 1 --episodes 24 --out benchmarks/novelty_guard_results.json
python -m benchmarks.novelty_guard_benchmark --seeds 1009 1013 1031 --train 48 --validation 16 --hazard-calibration 12 --reference 64 --iterations 2 --rounds 1 --episodes 24 --out benchmarks/novelty_guard_audit_results.json
python -m benchmarks.transfer_benchmark
```

The test seeds are **previously inspected**; this is not blind validation. Each seed fits 48 mixed histories, validates on 16 distinct histories, selects hazard on 12 more streams, and calibrates surprise on 64 independently indexed streams (32 stationary, 32 known within-episode changes). Five test sensor conditions each have 24 episodes and 36 observations, for 144 held-out episodes per condition across six seeds. A second 24-episode-per-seed closed-loop test checks whether an alarm actually pauses action suggestions.

Fit `train/0+`, model validation `train/10000+`, hazard selection `train/40000+`, guard reference `train/50000+`, evaluation `test/93000+` and task rollout `test/97000+` are separated. Evaluation observations and positions do not enter calibration. The benchmark-only simulator selects regimes and generates injected sensor failures. The guard itself sees only the start beacon, commanded actions, noisy odometry and landmark readings.

## Results (six inspected seeds)

| Sensor process | Alarmed episodes | Rate | Interpretation |
| --- | ---: | ---: | --- |
| Normal stationary known environment | 8 / 144 | 5.6% | Unnecessary false alarms |
| Known mid-episode dynamics change | 10 / 144 | 6.9% | Unnecessary alarms; bank knows both regimes |
| Landmark channel stuck reporting 0 | **144 / 144** | **100.0%** | Strong detection of this specific simulated failure |
| Odometry channel stuck reporting 0 | 44 / 144 | 30.6% | Most failures **missed** |
| Landmarks shifted to previously unseen offset 3 | 48 / 144 | 33.3% | Most unfamiliar maps **missed** |

In the **closed-loop task comparison**, without the diagnostic pause, 105/144 ordinary-world episodes succeeded. With guard-based pausing, **101/144** succeeded; 9 normal episodes were interrupted early, with 10 total alarm flags (one occurring on a terminal step). In the stuck-landmark fault condition, the baseline navigated successfully in 25/144 and the guard-paused variant in **21/144**; the guard paused **122/144** faulty runs before completion. This protects against continued unsupported action suggestions, **not** task success, and even decreases completion on these tasks.

Per-seed data and alarm delays are preserved in [`novelty_guard_results.json`](../benchmarks/novelty_guard_results.json) and [`novelty_guard_audit_results.json`](../benchmarks/novelty_guard_audit_results.json). One seed discovers only one model (seed 23); the gate never invents additional hypotheses. Its strong stuck-landmark result is specific to the chosen fault injection; it **does not** prove general anomaly detection, calibrated posterior probabilities, robust navigation, safe autonomous goal choice, or independently learned geometry.

## Decision

**Do not replace the default controller or expand autonomy.** The monitor catches an obvious landmark-sensor failure, but needs better unknown-environment representation, independent unseen sensor families, verified calibration under the *deployed action policy*, and fewer false pauses before more autonomy can be considered. V2A emotional development and V2B virtual home stay scheduled after core v1.0 gates.
