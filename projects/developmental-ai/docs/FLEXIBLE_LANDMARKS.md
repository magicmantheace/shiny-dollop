# Flexible landmark geometry (`flexible-landmarks/v1`)

**Experimental and simulation-only. It is not the default navigator or an authorization mechanism.** This study relaxes the older `structured-landmarks/v1` assumption that two known landmark symbols must be located exactly `n//2` cells apart on a ring. It does not establish general navigation, general geometry learning, independent goal selection, or autonomous adaptation across changing regimes.

## What the learner actually knows

- The environment is a ring with known size **9 or 11** and a one-time initial-position beacon.
- Movement commands are left/right; noisy odometry has three outcomes; observations can be `None`, marker `0` or marker `1`.
- The **two possible marker identities, shared categorical emissions and single stationary map for each ring size** are engineered assumptions. Either marker site can be absent, permitting zero, one or two distinct sites; positions are independent, not forced to a fixed spacing.
- It receives **no true positions after the beacon**, simulator regime name, realized displacement, privileged map, or reward while fitting. The benchmark harness knows the regime and true map only to generate simulated experiences and report evaluation results.
- The benchmark still groups training histories by simulator condition **externally**. It has not discovered different regimes from a single unlabelled continuous experience; handling mixed-regime histories is a remaining research objective.

## Algorithm

1. Initialize shared motion, odometry and landmark-role emission assumptions.
2. For **each ring size separately**, enumerate missing/present candidate sites for marker 0 and marker 1, excluding overlaps, and score marginal sensor-history likelihood on a bounded **train-only** subset. Penalize each inferred site by 3.0 log-likelihood units to reduce spurious sites.
3. Fit emission, motion and odometry count parameters using ordinary-observation latent-state forward/backward EM on the training histories. Halfway through fitting, run a deterministic coordinate refinement over site positions on **train-only** histories, then finish EM. Selection is not guaranteed to find the best map.
4. Persist optional `FlexibleModel` states in SQLite with schema/seed binding and SHA-256 accidental-edit detection; no cryptographic authentication or approval token is implied.

This algorithm can fail through local optima, noisy beacon-to-landmark associations, mismatched motion priors, or misleading sparse observations. It neither learns new sensor symbols nor permits more than two marker sites. A robust multi-map or regime detector would require another separate, measured implementation.

## Reproduction and evaluation leakage boundaries

```bash
python -m unittest discover -s tests -v
python -m benchmarks.flexible_landmarks_benchmark --seeds 17 23 41 --train 40 --iterations 4 --map-histories 16 --test 20 --navigation 30 --out benchmarks/flexible_landmarks_results.json
python -m benchmarks.flexible_landmarks_benchmark --seeds 1009 1013 1031 --train 40 --iterations 4 --map-histories 16 --test 20 --navigation 30 --out benchmarks/flexible_landmarks_audit_results.json
python -m benchmarks.transfer_benchmark
```

Training uses `train/0..39`, held-out prediction uses `test/51000..51019`, and navigation uses `test/57000..57029`. The exact published files were assembled from identical smaller **condition-scoped runs** to keep execution bounded; each entry still used the same budgets and splits, and each source condition run is fully reproducible with `--conditions known_half`, `--conditions unequal_two`, `--conditions one_site`, or `--conditions no_sites`.

All six seeds (17/23/41 and 1009/1013/1031) have been inspected during development. **The audit cohort is not blind.** Initial map and coordinate refinement were explored after inspecting pilot data; these results cannot be used as independently blind evidence or to justify a production default.

The benchmark compares independent-site model, unchanged half-spacing model, unchanged unconstrained latent EM, and a **privileged** physics-and-map-probability oracle (whose true location remains hidden). It reports held-out observation log likelihood, every map (learned versus true for scoring), and actual navigation success with the **same existing heuristic** for all models. No tool, system or private-data permission is granted.

## Navigation results

All percentages are means across three seeds in each group, **30 navigation episodes per seed per condition**; both individual-seed metrics and observation likelihoods are in the machine-readable result files. No regression was discarded.

| Condition | Development half-spacing | Development flexible | Audit half-spacing | Audit flexible |
| --- | ---: | ---: | ---: | ---: |
| Known half-spacing, high noise | 55.6% | **51.1%** | 43.3% | **33.3%** |
| **Previously unsupported unequal spacing, high noise** | 31.1% | **41.1%** | 32.2% | **54.4%** |
| One landmark, standard noise | 66.7% | **64.4%** | 65.6% | **55.6%** |
| No landmarks, standard noise | 31.1% | **25.6%** | 31.1% | **24.4%** |

For the unfamiliar unequal-distance map, the physics oracle reached **58.9% development** and **57.8% audit** navigation success. This indicates that loosening the geometric assumption improves transfer in the tested family, though not consistently to oracle performance. For the known-half and sparse conditions, flexible mapping often **regresses** relative to the simpler, stronger prior; it must not replace the prior as the default.

The new mapper accurately found both missing marker sites on **all six no-landmark seed tests**, and the single-site map on **five of six** seeds. It recovered the exact two-marker unequal geometry on **three of six** seeds; extra mistakes include shifted or missing inferred sites. Exact map recovery is therefore **not reliable in high noise**, despite higher average navigation success there.

## Next research steps

- Train from histories *not* grouped by simulator regime; detect meaningful changed-map boundaries without privileged labels, preserve earlier learned maps, and avoid unapproved promotions.
- Add more varied map cardinalities, multiple identical landmarks, missing initial beacons, and new ring sizes/topologies while keeping independent evaluation seeds frozen.
- Evaluate proper calibration of posterior location and site uncertainty, not just a single maximum-likelihood geometry.
- Improve computational cost: exhaustive geometry proposals and forward/backward likelihood evaluation are costly relative to older fixed-offset search.

This work preserves the current core v1.0 sequence, with V2A emotional development before V2B virtual home, both planned after the foundational learning and interface gates.
