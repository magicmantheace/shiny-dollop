# Offline-calibrated step detection (`calibrated-step/v1`)

**Scope:** simulation-only learning research. This is an explicit *supervised calibration of an offline decision threshold*, not self-calibrated confidence, a new neural learner, consciousness, or unrestricted action selection. The online `StepDetector` still receives no regime labels. Its action `active` is a model preference and MUST NOT be interpreted as an authorization to perform external actions. Every older benchmark result is retained, including failed detections.

## Why a separate calibration experiment?

The unchanged step-dynamics/v1 detector uses a heuristic `margin=0.12` between rolling per-step average log likelihoods. On seeds 23 and 41 that margin was too large relative to the ~0.06 per-step separation between the two pretrained physics models. The resulting detector never switched in the changed-world phase. Lowering it arbitrarily on the known evaluation seeds would overfit; instead the **new** procedure uses independent offline calibration histories.

1. Train each known named regime's latent-state dynamics model on `train` indices `0..129` (130 trajectories; 6 EM iterations), as in the original experiment.
2. Generate **40 distinct calibration histories per regime** from the `train` namespace, indices `5000..5039` (neither model fitting nor test indices). Labels identifying the generating regime are supplied to **offline calibration only**. Identical histories in two calibration groups are rejected.
3. Compute each regime model's held-out mean observation log likelihood on those histories. Compute its signed advantage over the strongest competing saved model. If any named regime is *not identifiable* (advantage <= 0), **refuse to calibrate**.
4. Set a shared decision threshold to `min(0.12, 0.5 × weakest positive calibration advantage)`; this multiplier is a prespecified heuristic. Persist the numeric threshold with an unsigned hash of calibration inputs, bank fingerprint, and an artifact-integrity checksum. The checkpointed detector itself stores the threshold in its configuration.
5. Evaluate on separate `test` indices `6000..6035`, in three 12-episode phases: original → changed → original. Keep the same 24-observation window, 3 confirmations, 5-step minimum, and -3.3 anomaly floor as the original detector. Compare to the **unchanged `margin=0.12` baseline** on the exact same test trajectories and compute correct, wrong and abstained step fractions.

The production agent has no knowledge of the regime label; **the offline calibration does**, which is why this is not autonomous discovery. The calibration input digest detects ordinary mismatch/tampering but cannot attest the data's origin or prove leakage-free provenance. A real deployment would need identity/consent controls external to this project.

## Reproduce

```sh
python -m unittest discover -s tests -v
python -m benchmarks.calibrated_step_benchmark --seeds 17 23 41 --out benchmarks/calibrated_step_results.json
python -m benchmarks.calibrated_step_benchmark --seeds 1009 1013 1031 --out benchmarks/calibrated_step_audit_results.json
python -m benchmarks.step_dynamics_benchmark --seeds 17 23 41
python -m benchmarks.transfer_benchmark
```

The benchmark uses no extra packages, credentials or GPU. Do not use evaluation feedback to tune threshold constants; change the protocol only with an explicit version bump and a new untouched-seed suite.

## Development results, % correct per phase

| Seed | Threshold | Initial old → calibrated | Changed old → calibrated | Return old → calibrated |
|---|---:|---:|---:|---:|
|17|0.022044|79.17 → 87.50|79.17 → **74.31** (regression)|87.50 → 87.50|
|23|0.049568|86.11 → 87.50|0.00 → 24.31|100.00 → 100.00|
|41|0.045907|95.83 → 95.83|0.00 → 45.14|100.00 → 100.00|

Across the three development seeds, changed-world correct-step selection improves from **26.4% to 47.9%**, but the wrong-model fraction remains **52.1%**. During the initial original-world phase, calibration creates **2.3% wrong selections** where the previous threshold made none, even though total correct selections rose due to fewer undecided steps. The original-world return phase stays at 95.8% correct.

## Additional inspected audit seeds (not blind)

| Seed | Threshold | Initial old → calibrated | Changed old → calibrated | Return old → calibrated |
|---|---:|---:|---:|---:|
|1009|0.038746|95.83 → 95.83|79.17 → 87.50|93.06 → 95.83|
|1013|0.043524|62.50 → 92.36|53.47 → 54.17|87.50 → 93.75|
|1031|0.022686|95.83 → 95.83|50.69 → 54.17|87.50 → 87.50|

Changed-world correct selection improves from **61.1% to 65.3%** averaged over these three audit seeds. The effect is modest and there is no guarantee of transfer beyond this simulator family. All six seeds were examined in the development process; *neither table is an independent blind evaluation*. The audit reused the predeclared calibration algorithm and budgets without seed-specific changes.

## Boundaries and next tests

- Calibration improves model discrimination but is not statistically calibrated uncertainty or out-of-family novelty detection; the absolute anomaly floor is still heuristic.
- The ring geometry, action alphabet, start beacon, number of stored regimes, and observation model are predefined. Regime changes happen **between** 12-step episodes, not within a live world trajectory.
- The environment with unfamiliar physics is still not reliably detected, and no automatic candidate promotion is enabled. Existing candidate training still has held-out predictive failures for two of three initial seeds.
- The detector retains the previously active selection during uncertain intervals; external adapters MUST treat `unknown` and `uncertain` states as non-authorizing regardless of `active`.
- Next: confidence and novel-regime detection calibration from a wider distribution of held-out environments, within-trajectory shifts, and properly reviewed candidate validation before installation. Preserve model snapshots and fail closed on unrecognized model banks.
