# Public-outcome model selection after feature-rule reversal

**October 21, 2026. Experimental and simulation-only.** This study does
NOT authorize an autonomous agent to probe a real environment, deploy new
models, change its own permissions, or bypass owner review.

## Why this experiment exists

The [original numeric affordance study](../benchmarks/observable_affordance_benchmark.py)
trained a memory of action features and observed sensor effects using 80
`collect` episodes. It transferred successfully to the related
`route` task, but every reversed-rule evaluation caused damage.
The actions have new opaque IDs each episode and two **engineered
numeric measurements** that encode useful action affordances; those
measurements are not hidden-name identity hashes. The rule reverses
which measurements signal progress versus harm.

A zero-experience agent cannot determine from the unchanged observation
alone whether that relation is normal or reversed. This experiment
therefore deliberately pays for **offline, disposable evidence**.

## Precommitted protocol

See [frozen protocol](../benchmarks/observable_reversal_calibration_protocol.json)
committed before implementation at `a5a40f8`.

- Fit original `NumericOutcomeMemory` from 80 collect-source random
  `train/0..79` episodes, exactly as in the earlier study.
- Fit a separate candidate from 80 reversed-rule `train/300..379`
  episodes, using **only public before/after sensor differences**.
- For each actual environment, make **12 single-action disposable
  calibration interventions**, `train/900..911`. The action is
  chosen by the largest predicted disagreement between the two
  observed-outcome models. Every intervention counts toward cost,
  including harmful outcomes; these are NOT assumed safe.
- Use add-`0.05` probability smoothing and compare observation
  log likelihoods. Select a model if at least four events were observed
  and the log-likelihood margin is at least 2; otherwise abstain.
- Evaluate on disjoint `test/14000..14059` using a **frozen
  read-only** model, 60 target episodes per seed/world. Both existing
  six-seed groups (71001/71013/71031 and 81001/81013/81031) are
  **previously inspected**; this is not a new blind study.
- Controls: source-only, reversed-model-only, deliberately WRONG
  calibration from the other rule, zero-action abstention,
  untrained random and privileged hidden-rule oracle.
- Model and calibration histories are versioned and SHA-256
  replay-checked; every recorded decision is recomputed from
  public observations. Hashes verify internal consistency only,
  not consent or authenticated ownership.

## Complete measured results (six inspected seeds)

[Focused GitHub Actions run 39711814419](https://github.com/magicmantheace/Developmental-AI/actions/runs/39711814419)
passed the nine new tests and both complete seed cohorts.

| Policy | Normal route, /360 | Reversed route, /360 | Harm in tested tasks |
| --- | ---: | ---: | ---: |
| **Offline calibrated** | **360** | **360** | **0** |
| Source/normal model only | 360 | **0** | **360** |
| Changed/reversed model only | **0** | 360 | **360** |
| **Calibration from wrong rule** | **0** | **0** | **720** |
| No-action abstention | 0 | 0 | 0 |
| Untrained random | 23 | 27 | 670 |
| Privileged simulator oracle | 360 | 360 | 0 |

**Calibration cost is substantial:** across 6 seeds × 2 worlds ×
12 disposable interventions = **144 calibration actions**,
**56 of which caused simulated damage** (37 on the normal relation,
19 on the reversed relation). These harms happened in the offline
rehearsal worlds; evaluating only test harm would hide them. All six
normal calibration decisions chose `source`, and all six reversed
calibrations chose `changed`.

The wrong-calibration control causes an exact **720/720 failed
evaluations with harmful actions**. That is a strong warning:
without evidence that the calibration distribution still matches
the test world, successful past calibration cannot justify automatic
deployment. An always-abstain policy avoids harm but completes no
work. The privileged oracle uses the hidden rule and is an unequal
upper reference.

**Interpretation:** This shows two already trained models can be
selected via observed outcomes, rather than hidden simulator action
identity, after an engineer-specified rule reversal. It does NOT show
learning an entirely unknown dynamics model, diagnosing an unseen
third rule, reliable safe live probing, a lifelong autonomous agent,
general intelligence, or D3/D4 completion. Test-world physics remain
hand-authored and deterministic, actions have engineered meaningful
features, and the comparison has unequal training costs.
The rehearsal environment is a privileged affordance of this
simulator; such disposable experiments are not generally available.

## Reproduce

```sh
python -m unittest tests.test_observable_reversal_calibration -v
python -m benchmarks.observable_reversal_calibration_benchmark --cohort development
python -m benchmarks.observable_reversal_calibration_benchmark --cohort inspected-additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

The [dedicated focused workflow](../.github/workflows/observable-reversal-calibration.yml)
retains both JSON result files. The complete Linux/Windows historical
workflow remains the merge gate.

## What to build next

A **new, explicitly post-hoc protocol** can evaluate sequential
evidence collection and stopping early once the confidence margin
becomes decisive. It must compare task accuracy AND intervention harm
against the now-frozen 12-probe strategy, account for miscalibration
after new changes, and preserve a zero-harm abstention comparator.
No unapproved deployment or AthenZ/Synveil integration; maintain
the V2A-before/overlapping-V2B roadmap.
