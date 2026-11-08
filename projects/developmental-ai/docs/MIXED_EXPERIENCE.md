# Mixed, unlabelled experience (experimental `mixed-experience/v1`)

The previous prototype fitted separate environmental models from **pre-labelled simulator regime groups**. This experiment asks whether a known-ring learner can identify useful alternative world models from a **single pool of ordinary observation histories** when regime labels are not provided to the learner.

**What is and is not learned.** Training input is only `{n, initial, observations}` where each observation is `(movement_command, noisy_odometry, optional_landmark)`. The initial beacon and 9/11-cell ring topology are provided. There are **two known distinguishable marker symbols** with the engineered assumption that marker sites lie half a ring apart, and each episode is assumed stationary. The underlying `StructuredModel` is still a hand-designed latent-state model. Ground-truth simulator positions, actual movement deltas, condition names and rewards are absent from every fit, model-choice and probe input. The simulator harness knows noise/layout parameters to construct environments and score outcomes; there is no general task inference, unsupervised physics discovery or automatic perpetual learning.

## Protocol and implementation

1. Separate `train/0+` episode records from `train/10000+` validation records by full-content fingerprints (reject duplicates/overlap). Test likelihood uses `test/70000+`, contextual probe inference uses `test/65000+` and navigation uses independent `test/77000+`. No `test` samples are used to fit or accept model parameters. Per-seed streams deliberately contain both standard/fixed and high-noise/shifted environments, with no regime identifiers in the records. Conditions are known to the **benchmark** but not the learning method. Previously inspected seeds are NOT blind.
2. Fit a *single* stationary structured-landmark baseline to the mixed evidence.
3. Initialize two-model proposals by clustering observations according to **command-vs-odometry agreement** or splitting by observed temporal order. Fit each model using forward/backward latent-state EM; reassign **whole episodes** by their marginal observation likelihood. Require minimum group sizes and both ring sizes; do not force a collapsed cluster.
4. On separate validation evidence, compare the whole-episode **mixture log likelihood** to the single model, with the fixed per-observation minimum gain `0.007`. Only a passing proposal is retained. This is not a statistical model-selection guarantee and cannot trigger model installation or privilege changes.
5. Use five separate, unlabelled contextual probe episodes to select a bank model (diagnostic selection at 80% heuristic posterior; uncertain selections fall back to the single baseline) for **new** navigation episodes. The probability is a heuristic derived under model assumptions, not calibrated confidence or authorization. Original default policy and bank/review systems are unchanged.
6. Persist and restore model proposals as versioned, seed/evidence-fingerprint-bound records with SHA-256 integrity hashes. Hashes catch accidental modification, not malicious tampering; not authenticated user approvals. No private human data are stored or committed.

## Reproduction

```bash
python -m unittest discover -s tests -p test_mixed_experience.py -v
python -m unittest discover -s tests -v
python -m benchmarks.mixed_experience_benchmark --seeds 17 23 41 --out benchmarks/mixed_experience_results.json
python -m benchmarks.mixed_experience_benchmark --seeds 1009 1013 1031 --out benchmarks/mixed_experience_audit_results.json
python -m benchmarks.mixed_experience_benchmark --seeds 17 23 41 --schedule original_only --out benchmarks/mixed_experience_control_results.json
python -m benchmarks.transfer_benchmark
```

Common budgets: **72 unlabelled fit episodes**, **24 train-namespace validation episodes**, **3 EM iterations**, **2 reassignment rounds**, **28 untouched predictive test episodes per regime**, **five unlabelled model-context probes**, and **24 navigation episodes per regime per seed**. For labelled *reference only*, a structured model trained on 36 separate observations from the actual test regime is scored as a privileged regime-grouped baseline. The physics oracle knows the true sensor and motion probability law, but not the live position. Neither is supplied to the unsupervised proposal.

### Results — all previously inspected seeds

Navigation success, mean of three seeds in each cohort (72 navigation episodes per regime and cohort). **Higher is better.**

| Cohort / regime | One-model baseline | Unlabelled discovered-model selection | Known-regime-grouped model reference | Physics oracle |
| --- | ---: | ---: | ---: | ---: |
| Development 17/23/41, changed high noise | 15.3% | **48.6%** | 44.4% | 61.1% |
| Additional inspected 1009/1013/1031, changed high noise | 15.3% | **44.4%** | 48.6% | 54.2% |
| Development 17/23/41, original | **84.7%** | 83.3% | 83.3% | 83.3% |
| Additional inspected 1009/1013/1031, original | **88.9%** | 86.1% | 84.7% | 87.5% |

Mean marginal sensor log-likelihood per step, higher (less negative) is better:

| Cohort / regime | One model | Two-model proposal | Regime-labelled model reference | Physics oracle |
| --- | ---: | ---: | ---: | ---: |
| Development changed | -1.7486 | **-1.6981** | -1.6627 | -1.6268 |
| Inspected audit changed | -1.7278 | **-1.7100** | -1.6661 | -1.6235 |
| Development original | **-1.4908** | -1.4957 | -1.4559 | -1.4507 |
| Inspected audit original | **-1.4451** | -1.4484 | -1.4156 | -1.4066 |

**All six two-regime seeds** proposed two models based on train-only validation. On the **single-regime original-only negative control**, all three development seeds rejected the unnecessary split and kept one model; its navigation success remained identical. Initializations and threshold were chosen as research heuristics; these seed groups have been repeatedly used during development. No new blind claims are justified. A short earlier *48-episode blocked-order seed-17 pilot* also accepted two regimes, but has a different training budget and is **not part of the matched headline results**.

## Remaining limitations and release decision

- **Do not enable as the default or autonomous promoter.** Navigation on original-world episodes regressed slightly, and the changed-world model still lags the correct physics oracle.
- The simulator supplies an initial beacon, tiny known ring geometry, 12-step episodes, two known marker symbols and stationary within-episode physics. `order` initialization exploits temporal continuity, not simulator labels; a shuffled, open-ended world or an environment with new sensor semantics is untested.
- This is offline two-hypothesis discovery with externally supplied fitting batches and contextual probes. There is no autonomous novelty threshold with a statistical guarantee, no within-episode change detection, no new objective families, and no authenticated AthenZ permission approval. SHA checksums do not prevent adversarial edits.
- The single-vs-mixture comparison is against the structured-landmark learner, **not every earlier model architecture**. Data are synthetic, and the test seeds have been inspected. Training evidence fingerprints cannot prove that two differently represented records did not arise from the same physical episode.
- Next: frozen independent blind seeds, abrupt changes inside episodes, novel landmark counts/semantics, stable versioned API for D2, longer-history replay, and a formally separate owner review before any model bank promotion. Preserve V2A affect and V2B virtual-home plans after core v1.
