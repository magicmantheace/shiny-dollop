# D3 research: detecting when a learned temporal world model goes stale

**Status: experimental, read-only diagnostic. No automatic model switch, new-model training, skill promotion, or real-world actions.** The evaluation contract was committed first as [`benchmarks/event_model_drift_protocol.json`](../benchmarks/event_model_drift_protocol.json) at commit `96e797ee6b5fdf84ff7c7f00443b087f7c45886e`. Both seed cohorts had been inspected in earlier studies: **not blind validation**.

## Problem and method

An observation-only, four-state event HMM learned from `source_bursts` can lose predictive accuracy when event durations and sensor noise change. The existing segmented event memory does not have a calibrated warning when this happens. `developmental_ai/event_model_drift.py` adds bounded, headless, online **diagnostic** scores from the HMM's per-token predictive probability:

1. **Predictive surprise CUSUM:** accumulate excess negative log-likelihood above a stationary training baseline plus a fixed 0.03 reference allowance. This is not a probability of change.
2. **Predictive surprise 16-token window:** positive mean excess likelihood loss.
3. **Raw token-change rate:** the fraction of changed adjacent tokens over the last 16 positions, independent of the HMM. This is a deliberately strong and inexpensive negative control.

All methods use the same 12-token warmup. An empirical per-seed calibration receipt chooses each threshold from the maximum scores over **80 separate stationary training streams**, allowing no more than 10% *strictly greater* maxima in calibration. That **does not guarantee** any fixed false-alarm rate for fresh data or the combination of three scores. The frozen HMM was independently fitted on 160 source-family training episodes; calibration uses separate `train` indices. All three methods only receive public integer symbols from 0 to 3. They never see hidden event labels, the true change boundary, the simulator scenario, a reward, or an AthenZ/Synveil service.

The benchmark joins two independently generated streams into one continuous observation sequence. Stationary control: `source_bursts + source_bursts`. Changed stream: `source_bursts + shifted_bursts`, which has more variable event durations and noisier observations. The concatenation boundary is stored **only by the scorer**. The monitor is not told when or whether the change occurred.

## Frozen evaluation

- Previously inspected development seeds: 14003, 14009, 14033; previously inspected additional seeds: 27007, 27011, 27017.
- Fit: `source_bursts/train/0..159`, same EM iterations as the existing baseline.
- Train-only calibration: 80 independent stationary concatenations, derived from `source_bursts/train` indices 800 onward.
- Evaluation: 40 stationary and 40 changed `test` concatenations per seed from indices starting at 94000, for 240 per condition overall. No evaluation stream changes a model or threshold.
- Model snapshots and calibration receipts are SHA-256-bound for **integrity only, not authentication**. Checkpoints restore diagnostic scores by replaying every stored raw observation; even a correctly rehashed inconsistent score is rejected. A fully forged but internally consistent record is not prevented by a digest.

## Results

| Frozen method | Stationary streams with any false alarm /240 | Changed streams with any post-boundary alarm /240 | Changed streams detected with **no earlier alarm** /240 |
| --- | ---: | ---: | ---: |
| **HMM predictive-surprise CUSUM** | **26 (10.8%)** | **136 (56.7%)** | **131 (54.6%)** |
| HMM surprise moving window | 23 (9.6%) | 93 (38.8%) | 86 (35.8%) |
| Raw token-change rate | 13 (5.4%) | 70 (29.2%) | 66 (27.5%) |

CUSUM early-alarmed before the change in 5/240 shifted episodes, window in 15/240, raw rate in 6/240. For CUSUM's detected cases, **per-seed median post-change delays** were 37, 28, 21, 30, 35, and 41 observations. These delays are long. The mean predictive log-loss was higher on shifted streams on every seed (roughly 0.07–0.10 nats per token), but even the strongest diagnostic misses many changed streams. The evaluation is not a deployment safety or statistical confidence bound.

### Interpretation

This is an improvement over an inexpensive raw-rate alarm **at the cost of more false alarms**. That trade-off is measurable, not a general change-point solution. The transition from one simulator episode to another can itself be surprising, but controls use the same concatenation boundary, helping distinguish that artifact from actual distribution change. The study does not show learning a new world-model, continual adaptation, useful task completion after alarms, or transfer beyond this fixed four-symbol HMM architecture. It should remain *off by default*.

## Reproduce

```sh
python -m unittest tests.test_event_model_drift tests.test_event_segmentation tests.test_environment_api -q
python -m benchmarks.event_model_drift_benchmark --cohort development --out benchmarks/event_model_drift_results.json
python -m benchmarks.event_model_drift_benchmark --cohort additional --out benchmarks/event_model_drift_additional_results.json
python -m benchmarks.transfer_benchmark
```

The new and related tests were run on a **locally reconstructed checkout**. The historical transfer benchmark remained at seed 17 **76.0%**, seed 23 **69.0%**, and seed 41 **66.67%**. There is no claim of a full remote suite, GitHub Actions or PC/hardware validation.

## Next D1/D3/D4 work

Evaluate calibration on genuinely new event task families and sensor corruption mechanisms, with precommitted independent evaluation. Then measure whether pausing or seeking new information actually improves *task outcomes*. Pair a reliable detector with bounded, review-gated model adaptation rather than adding automatic authority or treating alerts as evidence of consciousness. Preserve AthenZ identity ownership and Synveil permissions. V2A affective cognition remains before, then overlapping with, V2B virtual home.
