# Two-window action-outcome confirmation (experimental)

## Verified two-cohort outcomes — 2026-10-21

[Focused GitHub Actions run 39716302649](https://github.com/magicmantheace/Developmental-AI/actions/runs/39716302649)
passed all **8** dedicated tests and both **three-seed** benchmark
cohorts. All six seeds were *previously inspected*; these results are
post-hoc mechanics evidence, not blind generalization. Test evaluation
used 60 independent tasks per seed and condition, totaling **360** for
each test condition. Reported harm counts distinguish offline probe
damage from later test damage.

| Policy | Stationary normal | Stationary reversed | Normal→reversed | Reversed→normal |
| --- | ---: | ---: | ---: | ---: |
| `early4` (first 4) | 360/360 | 360/360 | **0/360** | **0/360** |
| `confirmed8` (agree first/last 4) | 360/360 | **300/360** | **0/360** | **0/360** |
| `recent8` (last 4) | 360/360 | **300/360** | **300/360** | 360/360 |
| `cumulative8` (pool all 8) | 360/360 | 360/360 | **0/360** | **240/360** |
| `always_abstain` | 0/360 | 0/360 | 0/360 | 0/360 |
| `oracle` (private rule, unequal) | 360/360 | 360/360 | 360/360 | 360/360 |

Test damage (successful harmful sensor changes) on rule-switch
conditions only:
- `early4`: **720 harmful test actions** (360 in each switch direction).
- `confirmed8`: **zero test damage** but **720/720 task failures
  by abstention** in switched conditions; one additional false
  abstention (60/360) in stationary reversed tasks.
- `recent8`: **zero test damage** on switched conditions, but
  **60/720 task failures by abstention**.
- `cumulative8`: **60 harmful test actions** under
  normal→reversed, and 240/720 switched-condition completions;
  pooling old and current evidence can retain obsolete conclusions.
- `always_abstain`: no test damage but no completed tasks.

Across the six seeds and **four** conditions, the `early4` policy
used **96** disposable calibration actions and incurred **32**
damaging calibration attempts. Every eight-probe policy
(`confirmed8`, `recent8`, `cumulative8`) used **192**
disposable actions and incurred **58** damaging attempts. Thus
confirming a second time incurs **26 additional harmful simulator
interventions** even before test actions are considered. These
interventions are not considered safe because they occurred in a
throwaway training simulator.

**Scientific finding:** first/last public evidence contradiction
can identify some changes between two already engineered outcome
laws, at the cost of increased probing and loss of useful action.
A recent-only selector exploits the known single change point,
but its performance does not imply reliable detection of unannounced
future switches or noisy/irreversible dynamics. The static feature
semantics, consequence rules, and two candidate models remain
human-engineered. **No version should be automatically deployed.**



This is a **post-hoc, simulation-only** response to the earlier
sequential-calibration finding: four public outcome probes reduced
damaging *disposable* calibration actions from 56/72 to 19/24 across
six inspected seeds while scoring 360/360 in each stationary world,
but early stopping failed all 360 reversed-rule tasks when its
first four observations preceded a rule change.

The [new precommitted protocol](../benchmarks/two_window_confirmation_protocol.json)
tests two *separate* four-sample windows with unchanged trained
source/reversed models, unchanged likelihood threshold, and no hidden
phase labels or action-name identities in model input. It is NOT a
blind test; the six seeds have been inspected repeatedly.

Methods, all evaluated on test/15100..15159:
- **early4:** choose from first four observed outcomes only.
- **confirmed8:** agree on source/changed in *both* public
  observation windows or **abstain**. Conflicting windows indicate
  evidence inconsistency, not proven physical regime change.
- **recent8:** choose according to the most recent four observations.
- **cumulative8:** pooled eight-observation likelihood.
- **always abstain:** zero harm AND zero completed tasks.
- **oracle:** unfair hidden-rule benchmark reference.

Both stationary rule environments and switches at the exact window
boundary are included: normal→reversed and reversed→normal. The
*simulator only* knows which physical dynamics generated each
training-namespace disposable probe. Probes may harm the simulated
environment and must be counted separately from evaluation harm.
A confirming policy may avoid a stale catastrophic model by
abstaining on a shifted context, **but this is not solving the task**.
A recent-only policy might succeed immediately after a known switch,
but remains vulnerable to yet another switch or noisy observations.

The policy and the original NumericOutcomeMemory never train on test
episodes. Checkpoint restoration recomputes each public observation
and the selected decision. SHA-256 protects integrity only; it is
not owner-authenticated consent or safe automatic promotion.

```sh
python -m unittest tests.test_two_window_confirmation -v
python -m benchmarks.two_window_confirmation_benchmark --cohort development
python -m benchmarks.two_window_confirmation_benchmark --cohort inspected-additional
```

All results including model-selection errors, task completions,
spoilage actions, abstentions and calibration harm must be published.
Do not alter historical study results, promote to default or claim
newly invented model semantics. Keep V2A before/overlapping V2B,
and cross-project integration deferred.
