# Joint spatial and model-regime inference (`mixture-navigation/v1`)

**Experimental, simulation-only; NOT the default navigator.** The earlier active-sensing policy did not improve high-noise navigation. This follow-up tests an alternative reason for low localization accuracy: a learned position filter becomes unreliable if it assumes the wrong environmental dynamics.

## What the agent receives

- A **one-time** starting position and goal beacon, and an externally supplied 9/11-cell ring topology.
- Each commanded action, noisy odometry and a possibly missing/misleading landmark observation.
- A **manually assembled bank of already fitted, immutable** dynamics models (ordinary observation-only EM fits from known regime-grouped `train` histories); it is **not** told which bank model is currently correct or the hidden position after reset.
- Optional unlabelled, separate **pre-navigation probe histories**. A capped likelihood softmax assigns an explicitly *heuristic*, non-calibrated prior across saved models. It never sees the regime name.

The filter tracks the joint posterior `P(model, location | observations, actions)` rather than prematurely committing to one model. It marginalizes location over model probabilities to choose a bounded left/right/collect action with the original heuristic, then updates the posterior from the next reading. Its model selection display may *abstain*. An observation or model score is not an authorization or consent credential.

## Methods and hard boundaries

- Explicit `mixture-navigation/v1` state records, model-count fingerprints and SHA-256 accidental-integrity digests; exact mid-episode SQLite restart. The checksums are **not authenticated signatures**.
- Training/fitting uses `train` indices starting at 0. Optional contextual probes use `test/19000+`; passive localization measurement uses `test/22000+`; closed-loop navigation uses `test/30000+`. Neither test partition is used to **fit learned model parameters**; probe histories are deliberately used for *online context conditioning* before a distinct navigation episode, never to tune evaluation thresholds or hyperparameters. Seed groups have already been inspected; **these are not fresh blind data**.
- The benchmark alone reads simulator hidden position and regime identity to score Brier error, top-1 position, credible-80% coverage, correct-regime selection and actual navigation success. The navigator and prior constructor refuse unsolicited simulator truth fields.
- The physical-parameter oracle baseline knows the actual physics distribution (not the live location). The `correct_known_model` baseline additionally receives the *privileged* correct bank selection. Neither reference is a deployable independent selector.
- The bank is assumed **stationary within each episode**, models require the known ring topology and action/sensor vocabularies, and fit groups are assembled externally. There is no new-regime invention, cross-task generalization, real-time OS connection, personalized data ingestion, or authority to change AthenZ/Synveil permissions.

## Reproduce

```sh
python -m unittest discover -s tests -v
python -m benchmarks.mixture_navigation_benchmark --seeds 17 23 41 --fit 90 --iterations 6 --probe 40 --navigation 60 --out benchmarks/mixture_navigation_results.json
python -m benchmarks.mixture_navigation_benchmark --seeds 1009 1013 1031 --fit 90 --iterations 6 --probe 40 --navigation 60 --out benchmarks/mixture_navigation_audit_results.json
python -m benchmarks.transfer_benchmark
```

## Evaluation notes

The benchmark compares `mixture` (uniform initial model prior), `probe_informed_mixture`, separately fitted `correct_known_model` / `wrong_known_model`, and a physics oracle, plus **position** calibration metrics on **identical passive observation streams**. Success is reported for each seed/regime without cherry-picking. The heuristic `effective_steps=16` and minimum floor `0.05` for probe weights are fixed in code rather than tuned to test outcomes; they are **not uncertainty guarantees**.

The mixture must **not become the default** unless further evaluation demonstrates reliable downstream improvement, high-noise localization and out-of-family calibration without new failure modes. Any calibration or experience-update changes require separate independent validation. Keep V2A (affect) and V2B (virtual room) after the core v1 goals.

## Observed results (previously inspected seeds, not blind)

All comparisons use **90 training histories per saved model, six EM iterations,
40 passive localization episodes and 60 navigation episodes per seed/regime**.
Reported navigation percentages average 180 trials per regime and cohort.

| Cohort/regime | Wrong saved | Uniform mixture | Probe-informed mixture | Correct saved (privileged) | Physics oracle |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development 17/23/41, original | 18.3% | 73.3% | 76.1% | 78.3% | 80.0% |
| Development 17/23/41, changed | 13.9% | 16.7% | 21.1% | 26.7% | 51.7% |
| Inspected audit 1009/1013/1031, original | 16.1% | 80.6% | 85.6% | 85.6% | 85.0% |
| Inspected audit 1009/1013/1031, changed | 12.2% | 11.7% | 12.8% | 14.4% | 56.1% |

On identical 12-step *passive* sensor streams, the uniform mixture's
mean spatial Brier error was 0.572/0.801 (development original/changed)
and 0.567/0.810 (audit original/changed); correctly selected saved models
scored 0.531/0.714 and 0.522/0.748. The smallest posterior set carrying
at least 80% belief contained the true location **96.4%/82.2%** of the time
in development original/changed conditions, and **96.3%/84.3%** on the
inspected audit. This is undercoverage/overcoverage relative to the intended
80%, showing the uncertainty estimates are **not calibrated**.

With a 90% threshold, the mixture abstained on 103/120 changed-world
probe episodes in development and 105/120 in the inspected audit. A stronger
spatial and landmark model, calibration under new noise regimes, and
independent blinded evaluation are needed. **No default policy change.**
