# Conservative selective-decision gate (`decision-abstention/v1`)

This module is a **simulation-only readout filter** for the existing incremental `StepDetector`. It does not make the underlying filter more accurate or change the learned dynamics models. It refuses to return a model name when the detector's active selection disagrees with the leading instantaneous rolling evidence, the margin is too small, or the detector is warming, unknown or uncertain. A consumer **must use** the gate result rather than `StepDetector`'s unguarded `active` field if abstention is desired.

## Data separation and protocol

- The model bank is fitted with `train` histories indexed `0..129` (130 per regime, six EM iterations).
- A **separate** labeled offline calibration stream is generated from `train` indices `5000..` (40 episodes per phase, original → changed → original). Regime labels are used only here to find a cutoff with at most 10% *empirical* wrong answers among non-abstentions. They never enter the online decision function.
- Test streams use only `test` indices `6000..` (12 episodes per phase) and are not used to tune the profile. `decision_abstention.train_gate` is given 1,440 independently emitted observation records and their offline labels. Cutoffs are selected by sorted evidence gaps, and the entire calibration profile is checksum- and model-bank-bound.
- A profile with no feasible cutoff fails closed with a large no-acceptance gap. A checksum is neither a signature nor proof that the supplied histories actually used the claimed split. The benchmark enforces namespace separation in its own construction; an external caller must enforce it too.
- The classifier uses **known ring topology, a seeded first-location beacon, and existing pre-trained models**. Its thresholds were developed with these two regime families in view. Results below are development/audit measurements, **not blind independent evaluation or guarantees about real systems**.

Run from repository root:

```sh
python -m unittest discover -s tests -v
python -m benchmarks.abstention_benchmark --seeds 17 23 41 --out benchmarks/abstention_results.json
python -m benchmarks.abstention_benchmark --seeds 1009 1013 1031 --out benchmarks/abstention_audit_results.json
python -m benchmarks.transfer_benchmark
```

## Results: all tested seeds, no cherry-picking

Each group has 1,296 individual observation decisions (three seeds × three phases × 12 episodes × 12 observations).

| Inspected seed group | Detector | Correct | Wrong | Abstained | Coverage | Conditional wrong rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 17, 23, 41 | Original frozen detector | 904 | 336 | 56 | 95.68% | 27.10% |
| 17, 23, 41 | Selective gate | 358 | 3 | 935 | 27.85% | 0.83% |
| 1009, 1013, 1031 | Original frozen detector | 1,016 | 214 | 66 | 94.91% | 17.40% |
| 1009, 1013, 1031 | Selective gate | 498 | 21 | 777 | 40.05% | 4.05% |

**Negative finding:** the price of reducing unsupported choices is substantial. The gate declines to name a regime on 60–72% of observations, so it does not solve reliable autonomous switching. Seed 1031 still has **17 wrong selections** behind the gate. The 10% calibration goal is an *in-sample empirical rate*, not a bound on independent-test error (even when observations are nominally disjoint, adjacent timesteps are correlated). There are no statistical confidence guarantees.

## Integration boundaries

- `train_gate(bank, labelled_offline_events)` produces an immutable, digest-bound profile. `verify_gate(bank, profile)` rejects bank/configuration mismatches. `decide(event, model_names, gap=profile.gap)` returns either an approved *model name* from the existing bank or `None` (abstain).
- The gate accepts no shell instructions or real-world tool calls, never mutates the bank, and never promotes staged candidates. AthenZ and Synveil remain optional external projects; no live integration was added in this milestone.
- Candidate validation is still incomplete: `CandidateStore.promote` requires a manually supplied digest but does **not** yet require independent predictive validation. That remains a separate development gate; never treat this new abstention profile as authority to promote models.

Next: evaluate risk–coverage curves on new distributions, account for correlated timesteps in empirical risk estimation, add frozen independent candidate holdout reviews, and test confidence calibration under unseen sensor failures. Do not optimize against the published audit seed scores.
