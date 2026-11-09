# Consecutive-evidence selective decisions (`streak-selection/v1`)

**Research-only. Not a deployment gate or real-world authorization layer.**
This optional classifier uses the sequence of ordinary per-step `StepDetector`
observation events. It permits a selection only after the same likelihood-leading
model appears on **three consecutive observed steps**, and its likelihood gap
exceeds a frozen offline-calibrated threshold. The online selector receives no
regime labels, no hidden positions, and no permission to act in AthenZ/Synveil.

The existing `decision_abstention/v1` remains the conservative default. This
experiment does **not** replace or change it. When `step_dynamics` reports an
`unknown` or `warming` status, the streak classifier always abstains. Otherwise
it can select the score leader even if the detector has not yet switched the
`active` model; that makes it an *independent experimental decision rule*, not
an authorization bypass to an existing trusted application.

## Protocol and reproducibility

- Fit a model bank on `train` indices `0..129`, 130 twelve-observation histories
  per known regime; use six EM iterations.
- Calibrate offline with labeled **separate** `train` indices `5000+`, 40
  episodes in each phase. The training budget is the same for all seeds.
- Freeze a three-observation minimum and 2% maximum **empirical** calibration
  error before the held-out comparison. The threshold maximizes calibration
  coverage among observed cutoffs that meet this constraint. If no threshold
  qualifies with at least 24 accepted examples, the selector abstains.
- Evaluate on disjoint `test` indices `6000+`, 12 episodes per phase. Compare
  `frozen` StepDetector, existing conservative abstention gate, and optional
  streak policy on exactly the same 432 observation steps per seed.
- `StreakSelector` is replayable and exports a versioned checksum-bound
  restart state. It rejects skipped/replayed/reordered observations, profile or
  model-bank mismatch, and malformed likelihoods. A checksum is **not** a
  signature or proof of permission. All model/profile data remain local.

```sh
python -m unittest discover -s tests -v
python -m benchmarks.streak_selection_benchmark --seeds 17 23 41 --out benchmarks/streak_selection_results.json
python -m benchmarks.streak_selection_benchmark --seeds 1009 1013 1031 --out benchmarks/streak_selection_audit_results.json
python -m benchmarks.transfer_benchmark
```

## Inspected results — **mixed**, no promotion recommended

Counts are **correct / wrong / abstained**, out of 432 steps per seed:

| Seed | Conservative existing gate | Experimental three-step streak |
| --- | --- | --- |
| 17 | 146 / 0 / 286 | 186 / 3 / 243 |
| 23 | 101 / 2 / 329 | 76 / 0 / 356 |
| 41 | 111 / 1 / 320 | 84 / 0 / 348 |
| **Development total** | **358 / 3 / 935** | **346 / 3 / 947** |
| 1009 | 175 / 4 / 253 | 209 / 5 / 218 |
| 1013 | 147 / 0 / 285 | 123 / 0 / 309 |
| 1031 | 176 / 17 / 239 | 195 / 17 / 220 |
| **Additional audit total** | **498 / 21 / 777** | **527 / 22 / 747** |

Overall the streak experiment gains just 17 correct decisions while adding
one wrong decision across all six seeds; it is **worse on coverage for several
individual seeds** and does not improve the default safety/coverage tradeoff
reliably. In particular, the existing model itself is inaccurate on some
streams. This research result is a reason to improve prediction/model quality,
not to relax real-world safety checks.

## Limitations and next experiments

Steps inside an episode are correlated, so a per-step empirical 2% calibration
error is neither a confidence interval nor a safety guarantee. We inspected
all six seeds; the extra three seeds are an internal audit, **not blind
external validation**. The world has known topology, two hand-specified
regimes and manually pre-trained models. No evaluation on completely new task
families is claimed. We do not train a recurrent world model, change the
underlying model probabilities, or promote any candidate model in this pass.

Next: fit more discriminative latent models, test out-of-family regimes, use
independent episode-level calibration and uncertainty bounds, and keep
approved model promotion behind separate held-out validation and owner review.
