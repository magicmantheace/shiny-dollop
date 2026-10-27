# Within-episode changing-world inference (`switching-belief/v1`, experimental)

**Purpose:** use an already-frozen bank of one or two previously discovered structured landmark hypotheses to estimate location while an environment's movement/odometry/landmark regime may change *during one experience*. Unlike the stationary mixture, this filter allows a small probability of switching which model applies before each subsequent observation. The filter consumes only the initial known ring position/goal, an allowed action, noisy odometry and landmark markers. No true position or regime labels enter its update.

## Scope and algorithm

- `SwitchingBelief` tracks a normalized joint posterior over `{model hypothesis, position}`. Its bounded `hazard` (0–0.3) is a prior probability of transitioning between existing models per step, **not** a learned proof that the environment changed. At hazard 0 its observation likelihood equals the original static episode mixture. It does **not** fit, create, approve or deploy any new model.
- The optional heuristic moves left or right to minimize expected distance and collects at the legacy 45% goal-belief threshold. The benchmark below is **passive random-action sensor evaluation**, **not** a navigation success test; no downstream task benefit is claimed.
- `SwitchingCheckpoint` binds checksummed, versioned per-step state and the exact immutable model fingerprints to a local SQLite file. Restarts continue identically. SHA-256 here detects accidental modifications; it is **not** a signature or consent authorization.
- `calibrate_hazard` accepts only ordinary sensor records (no hidden position, regime, reward, or simulator truth fields), rejects duplicate evidence, compares a frozen list of switching hazards on separate train-namespace observations, and emits a bank-bound, checksum-validated calibration receipt. `verified_hazard` fails closed if the bank differs. Calibration scores are **not** confidence guarantees.
- The simulation remains restricted to known 9/11-cell ring worlds, a one-time initial-position beacon, and two landmark types with a fixed relative distance assumption inherited from `fit_mixed`. No general spatial intelligence, online novel-regime discovery, physical autonomy, or AthenZ/Synveil connection is implemented. Preserve the current engine default.

## Reproduction

```sh
python -m unittest discover -s tests -p test_switching_belief.py -v
python -m unittest discover -s tests -p test_mixed_experience.py -v
python -m unittest discover -s tests -p test_structured_landmarks.py -v
python -m benchmarks.switching_belief_benchmark --seeds 17 23 41 --train 48 --validation 16 --calibration 8 --test 24 --iterations 2 --rounds 1 --out benchmarks/switching_belief_results.json
python -m benchmarks.switching_belief_benchmark --seeds 1009 1013 1031 --train 48 --validation 16 --calibration 8 --test 24 --iterations 2 --rounds 1 --out benchmarks/switching_belief_audit_results.json
python -m benchmarks.transfer_benchmark
```

Model fitting takes mixed, unlabelled stationary `train/0+` trajectories, with distinct validation histories `train/10000+`. The switching hazard is selected via predictive observation likelihood **only on** `train/40000+` streams whose simulator changes physics at steps 12 and 24 (original → high-noise/shifted → original) but gives the estimator no change labels. The untouched evaluation is on separate `test/85000+` switching and `test/86000+` stationary-control streams. All seed values were inspected in previous experiments. These are development and **non-blind** audit results; the known change schedule and hazard candidate list have been authored during development, not randomly hidden from developers.

**Full evaluation**: 48 mixed training histories, 16 validation, eight separate hazard-calibration streams, 24 switching and 24 stationary test streams per seed. Each evaluation stream has 36 observations, with common seeded random action sequences for both compared filters. Metrics: per-step negative log sensor likelihood (NLL, lower better), position Brier score (lower better), and fraction of steps where no model posterior reaches 80% (abstention, lower indicates greater coverage but NOT lower error). Hidden true positions and regime phase are read **only by the scoring harness**; the source fields are never passed to either filter.

## Six-seed results

| Previously inspected seed | Selected hazard | Two candidate models? | Switching-world NLL, static → dynamic | Switching-world position Brier, static → dynamic | Stationary control NLL, static → dynamic |
|---|---:|---|---:|---:|---:|
| 17 | 0.10 | Yes | 1.653765 → 1.631850 | 0.741227 → 0.698743 | 1.503832 → 1.505184 |
| 23 | 0.00 | **No** (single-model fallback) | 1.566595 → 1.566595 | 0.776528 → 0.776528 | 1.517498 → 1.517498 |
| 41 | 0.10 | Yes | 1.527035 → 1.518496 | 0.743512 → 0.689218 | 1.490271 → 1.494828 |
| 1009 | 0.04 | Yes | 1.621453 → 1.600108 | 0.792760 → 0.721073 | 1.459950 → 1.464874 |
| 1013 | 0.10 | Yes | 1.557733 → 1.546406 | 0.812945 → 0.772593 | 1.522896 → 1.521162 |
| 1031 | 0.00 | Yes | 1.584091 → 1.584091 | 0.743113 → 0.743113 | 1.518170 → 1.518170 |

On switching episodes, the selected filter improved both NLL and Brier in **4 of 6** seeds; the other two tied their baseline. On constant-regime control streams it made NLL worse in **3 of 6**, better in one, and tied in two. Model-selection abstention increased from 24.0% to 56.3% on development seeds and from 37.8% to 66.5% on the additional audit seeds (see JSON). A high switching hazard keeps competing model hypotheses alive and can prevent a confident model identification. Neither good prediction nor a checksum is a permission to autonomously promote models.

**Not yet resolved:** the two-model proposal may be rejected even in a mixed condition; change detection from a single trajectory is slow and uncertain; we have not measured closed-loop task improvement, truly blind seeds, arbitrary number of models, irregular abrupt transitions, unknown topologies, or long-run data retention. Do not call this a production-ready autonomous detector or continual learner.

## Validation status

- Targeted switching, mixed-experience, structured-landmark, online-dynamics, and flexible-landmark test modules passed locally after reconstructing available sources. The full reconstructed suite exceeded its execution-time limit; therefore **do not claim full-suite green**. This is not GitHub Actions or PC testing.
- The unchanged transfer benchmark reproduced 76.0%, 69.0% and 66.67% (seeds 17, 23 and 41).
