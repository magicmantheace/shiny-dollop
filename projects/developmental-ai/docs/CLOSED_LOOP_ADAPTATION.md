# Closed-loop adaptation (experimental, `closed-loop-adaptation/v1`)

The bounded navigation session combines **offline observation-only mixed-regime discovery**, a separate **train-calibrated model-switching hazard**, and **live in-simulator actions**. It is not the default navigator or an AthenZ service. Models are frozen for each session; it cannot fit/promote a new model, alter permissions, execute code, read human records, or control an OS.

## Interface and integrity

`NavigationSession(proposal, initial, goal, n, receipt, mode="switching")` exposes `select_action()` to suggest one of left/right/collect and `advance(action, observation, done=...)` to acknowledge it using only odometry and landmark sensor readings. It rejects hidden position/regime fields, incorrect actions, and further actions after termination. **Model selection confidence is diagnostic, never authorization.**

`NavigationCheckpoint` persists the versioned, bounded action/sensor record and probability state locally in SQLite; restoration replays sensor evidence to check the posterior, action sequence, model bank, and hazard receipt. A model is copied on session creation and mutation of the active model causes a fail-closed error. SHA-256 protects accidental integrity, not signed human consent. The harness-supplied `done` flag does not prove a task or real-world action actually succeeded.

## Reproduce

```bash
python -m unittest discover -s tests -p test_closed_loop_adaptation.py -v
python -m benchmarks.closed_loop_adaptation_benchmark --seeds 17 23 41 --out benchmarks/closed_loop_adaptation_results.json
python -m benchmarks.closed_loop_adaptation_benchmark --seeds 1009 1013 1031 --out benchmarks/closed_loop_adaptation_audit_results.json
python -m benchmarks.transfer_benchmark
```

Identical budgets per seed: fit 48 mixed `train/0+` histories with 2 EM iterations, validate on 16 disjoint `train/10000+` histories, select the hazard from 12 `train/40000+` unlabelled 36-step streams, and measure 24 navigation episodes per method/schedule on `test/99000+`. The simulated physics changes at step 4 and returns at step 14; short episodes may finish before both changes. Regime labels and hidden position stay **in the scoring harness only**. The physics-law reference knows the true regime schedule, not current position; it is a heuristic, not an optimal-policy bound.

## Actual results (all six previously inspected seeds)

Navigation success; each cohort contains 72 test episodes per schedule and method.

| Schedule / seeds | Single mixed model | Static mixture | Switching mixture | Privileged physics-law reference |
| --- | ---: | ---: | ---: | ---: |
| Switch, development 17/23/41 | 61.1% | **68.1%** | 62.5% | 80.6% |
| Switch, inspected audit 1009/1013/1031 | 65.3% | 63.9% | **79.2%** | 75.0% |
| Original stationary, development | 75.0% | 72.2% | 75.0% | 79.2% |
| Original stationary, inspected audit | 59.7% | 73.6% | 75.0% | 80.6% |
| Changed/high-noise stationary, development | 13.9% | **29.2%** | 23.6% | 50.0% |
| Changed/high-noise stationary, inspected audit | **29.2%** | 25.0% | 23.6% | 47.2% |

Changing-environment **per-seed static → switching** (24 episodes each):
- Development seed 17: 19 → 17; seed 23: 13 → 13; seed 41: 17 → 15.
- Inspected audit seed 1009: 12 → 17; seed 1013: 14 → 19; seed 1031: 20 → 21.
- Seed 23 discovered only one model; its calibrated hazard was zero, correctly preventing fictitious switching.
- On **always high noise**, switching regressed relative to the static mixture in both cohorts. The test seeds have been repeatedly inspected; there is **no independent blind result**. Rates above the physics-law heuristic in isolated cohorts are sampling/policy variation, not better privileged knowledge.

## Open gates

The system still assumes a known 9/11-cell ring, one-time initial position beacon, two fixed-spaced landmark roles, and a frozen bank of at most two observation-learned models. A change schedule was chosen by the researcher for hazard calibration. It does **not** learn a new regime during navigation, generalize to unknown task families, prove calibrated model confidence, or implement a stable/authenticated AthenZ or Synveil service. **D2/D3/v1.0 remain open.**

Keep the existing navigator the default: the within-episode performance is mixed and stationary high-noise reliability is worse. The next experiment should test generalization in unfamiliar environments and whether rejecting weak model hypotheses is more useful than switching continually. Versions 2A and 2B remain roadmap-only.
