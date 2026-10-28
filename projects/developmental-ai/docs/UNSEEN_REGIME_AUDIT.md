# Unknown descriptor remapping C — adversarial controls (2026-10-21)

**Status: experimental, simulation-only and post-hoc. All cohorts are
already inspected. No default policy changes or integration.**

## Why this comparison is necessary

The [cue-free diagnostic result](NO_CUE_DIAGNOSTIC.md) showed that one
public action outcome can distinguish two *already trained* cargo regimes:
360/360 test completions at original A, switched B and return A across
six previously inspected seeds. On changed B, the same probe followed by
a fixed A memory succeeded only 147/360. This is useful evidence that
selecting between known memories can matter.

But that comparison lacked an even simpler policy: **avoid every action
descriptor flagged as risky by either stored memory**, without identifying
a regime or spending an action on a diagnostic probe. That rule may work
particularly well because, in the hand-authored simulator, the risky
action code merely swaps with a **harmless distractor**. The union of the
two known risk sets would then exclude both irrelevant operations while
leaving the productive recipe intact. This cannot be used as proof that
context inference was necessary for task completion.

The stronger stress test also adds an entirely **untrained mapping C**.
C swaps the two-byte descriptor identities for harmful `spoil` and
**necessary productive** `fuel`. Hidden cargo physics, public numeric
sensors, action budget and opaque per-episode handles are unchanged.
The remembered hazard sets cover only known A/B descriptors. A policy
trained on A and B therefore has no justified method of identifying the
new harmful descriptor from its prior signature alone. C should expose
the risk of blindly trusting either the inferred known-regime mapping or
a union of known risk codes.

## Frozen before evaluation

See [the protocol](../benchmarks/unseen_regime_protocol.json), committed
as `09d9cb290ad4493602dde99718cb2ae7a32b28cb` before new policy
or benchmark code. The six seeds and both A/B histories were already
inspected; this is **not** blind validation of generalization.
C was specifically constructed **after** the earlier A/B success to
probe an identifiability gap. Do not cherry-pick replacement seeds,
retune parameters against C and call the result a fresh held-out test.

- Training: only the old A `train/0..79` and B
  `train/300..379` histories; **zero C training episodes**.
- Evaluation: `test/9000..9059` in A, B and C, 60 episodes per
  seed and world. Two cohorts: 51001, 51013, 51031 and
  61001, 61013, 61031 (all previously inspected).
- Methods: prior cue-free one-step diagnostic selecting A/B memory;
  read-only union of all learned risk tokens; frozen A-only;
  frozen B-only; untrained novel-first; simulator-privileged
  **true-hazard-code** oracle.
- Every learner receives only public rotating handles, stable
  engineered numeric identity codes, sensor vectors, accepted/blocked
  outcomes and goal predicates. No variant label, perfect context
  beacon, hidden action names or internal recipe is available to the
  learner. Privileged labels are for scoring/oracle only.
- Metrics: success, accepted spoilage, blocked attempts, average
  attempted actions, diagnostic probes and stalled trials.
- Read-only comparison: stored histories must not change.
- The conservative union is **not a safety guarantee**. It can block
  necessary productive actions when their numeric codes alias known
  risk codes, and new hazards can exist outside the union.

## What the result will establish

A/B performance equal to the diagnostic policy would undermine a claim
that active context inference was required to solve *these* A/B tasks.
A collapse on C would show that two-known-regime selection and
risk-code union cannot handle arbitrary unknown remappings.
Shorter failed episodes or refusal to act must never be described
as successful harm prevention.

This is an important distinction between:
- retaining memories in a known world,
- identifying which known memory to retrieve, and
- learning to cope with a **truly unfamiliar** action mapping.

Only the third would move the research toward robust continual
generalization. None is yet validated on independently designed
environments, stochastic physical consequences, or human tasks.

## Reproduce

```sh
python -m unittest tests.test_unseen_regime -v
python -m benchmarks.unseen_regime_benchmark --cohort development
python -m benchmarks.unseen_regime_benchmark --cohort inspected-additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

**CI:** The benchmark and new tests have been added to
`.github/workflows/standalone-validation.yml`. An exact-commit
GitHub execution is required before numerical claims. Preserve all
controls and bad outcomes in the PR report.

## Next genuinely discriminating direction

Train and test on fresh independent action/observation generators with
stable *behavioral* features rather than simulator-assigned identity
codes. Estimate uncertainty and abstain from potentially irreversible
unknown actions. Use independent held-out worlds, intervention-cost
accounting, matched source/target experience and online
A→B→C→A retention. No real-world action authority, automatic policy
promotion, or Synveil/AthenZ integration during this phase.
