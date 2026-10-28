# Transfer from public numeric action measurements, not action-name hashes

**Experimental development branch, October 21, 2026. Not a new default
learner, deployable safety mechanism, or evidence of consciousness.**

## Question

Previous A/B/C studies supplied *numeric descriptors constructed by hashing
the simulator's private action name*. A policy could succeed by recognizing
a disguised stable identity without learning how physical action qualities
predict outcomes.

This experiment asks a narrower, testable question: can a new model learn
the relation between publicly visible **numeric physical measurements**
and observed progress/damage outcomes, then apply it to an independent
task-family generator with entirely new opaque action handles?

The protocol was frozen before code in
[observable_affordance_protocol.json](../benchmarks/observable_affordance_protocol.json).

## What is actually implemented

`developmental_ai/observable_affordances.py` generates new anonymous
action handles every episode, independent of each action's two-number
public measurement `[x,y]` (both in 0..8). It does **not** use
`hash(hidden_action_name)` as a feature.

The simulator intentionally provides a **hand-engineered informative
feature law**: normally actions with `y >= x+2` produce useful
progress, actions with `x >= y+2` cause damage and terminate, and
remaining actions are neutral. The source family has 10 actions and
a 3-step progress goal; the target has 12 actions and a 4-step goal.
Both families sample fresh feature tuples every episode, with enough
productive and harmful options for meaningful choice. They **share
the same hidden feature-to-consequence law**: they are different
task generators, not independent scientific domains or real-world
physical discoveries.

The training policy attempts random actions in **80 source episodes
per seed**, and the model stores only the publicly observed action
features and progress/damage sensor differences. The optional
`NumericOutcomeMemory` fits a simple **five-nearest-neighbor**
predictor using these visible input/outcome pairs, then scores
candidate actions under an explicitly hand-set asymmetric
damage penalty. It does not receive an action kind, simulator rule,
family label, domain identity or privileged oracle label.
Its event list can be replayed from a SHA-256 checked checkpoint;
integrity is not owner authentication.

After source training, all evaluations are **read-only**. There are
**zero target-family training episodes**. Changed and new opaque
action handles cannot be matched to a persistent action-name ID.

## Frozen tests and controls

- Source `collect`, target `route`, negative-control
  `route-reversed` where identical public measurements have
  **reversed consequences**. The reversed world intentionally
  tests when formerly useful knowledge becomes dangerous.
- Source training: 80 `train/0..79` episodes per seed.
- Evaluation: `test/12000..12059`, 60 episodes per seed
  for each world, no test updates.
- Three development seeds: 71001, 71013, 71031;
  three separate reserved seeds: 81001, 81013, 81031,
  which become inspected once tested.
- Policies: trained numeric nearest-neighbor, no-memory first
  action, random action, **feature-shuffle ablation** that
  misaligns public features and actual actions, and
  simulator-privileged true-rule oracle.
- Report for **every policy and world**: task successes,
  damaging actions, stalls and mean attempts. No shorter
  harmful failure may be presented as a success.
- New tests reject hidden/private frame fields and malformed
  observations, verify fresh action handles, public-only
  evidence, exact memory replay and read-only evaluation.

### First local development-cohort reproduction

I ran the exact new files against the three **development** seeds,
60 tests each. These numbers are **local reproduction**, not a
substitute for current GitHub Actions on the final head. Pairs
below are completed tasks / accepted damaging actions out of 180:

| World | Trained numeric memory | Novel | Random | Features shuffled | Privileged oracle |
| --- | --- | --- | --- | --- | --- |
| Collect (source) | **180 / 0** | 36 / 144 | 41 / 139 | 28 / 152 | 180 / 0 |
| Route (zero-shot target-family) | **180 / 0** | 18 / 162 | 11 / 169 | 10 / 170 | 180 / 0 |
| Route-reversed (adverse control) | **0 / 180** | 9 / 171 | 10 / 170 | 16 / 164 | 180 / 0 |

The model therefore succeeds within two purposely aligned generators,
but **fails catastrophically** when the engineered feature rule
reverses. It does not autonomously recognize rule change or know
how to stop unsafe exploration.

### Verified GitHub cohorts (all six seeds)

The [dedicated GitHub Actions run](https://github.com/magicmantheace/Developmental-AI/actions/runs/39672714422)
completed with **9/9 dedicated tests passing**, both frozen
three-seed cohorts, and raw JSON tables retained as artifacts.
All reserved seeds are **now inspected**. The table below reports
task successes / damaging actions across **360 episodes** per world
(60 per seed, six seeds):

| World | Numeric KNN | Novel | Random | Shuffled features | Privileged oracle |
| --- | --- | --- | --- | --- | --- |
| Collect | **360 / 0** | 70 / 290 | 73 / 287 | 44 / 316 | 360 / 0 |
| Route, no target training | **360 / 0** | 31 / 329 | 21 / 339 | 16 / 344 | 360 / 0 |
| Route-reversed | **0 / 360** | 27 / 333 | 23 / 337 | 45 / 315 | 360 / 0 |

This reproduces the local development findings in the second
precommitted cohort. Although newly generated actions have unrelated
opaque handles and the learner receives no hidden categorical
action identity, the handcrafted feature law is an unusually
informative shared prior. **The 360/360 positive-domain scores
must be read alongside 0/360 and 360 damaging actions after the
feature rule reversal.** The system currently cannot detect that
its confident expectations have become invalid before harmful
consequences in this simulator. The full historical regression
workflow on the final documentation commit is a separate gate.

### Interpretation and next gate

This is an improvement over memorizing hidden action identities:
the features are *measurements* and the learner derives their
outcome associations from public training experiences. But the
measurements were designed to reveal a simple fixed relation, and
the two task families share it. A strong oracle still exploits the
simulator's private rule; risk penalties and nearest-neighbor
structure are manually chosen. The new model is a statistical
prototype, not a generally adaptable independent mind.

The important next development question is how to infer a likely
**change-point in observed consequences** with safe experimental
costs, abstain when risk is not bounded, and adapt to a genuinely
unseen feature-effect law. That will require separate held-out
generator designs, stochastic consequences, explicit confidence
calibration, safe intervention constraints and matched data/compute
baselines. Preserve all negative results and do not replace any
current default learning system.

## Run

```sh
python -m unittest tests.test_observable_affordances -v
python -m benchmarks.observable_affordance_benchmark --cohort development
python -m benchmarks.observable_affordance_benchmark --cohort reserved
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

GitHub's [dedicated full-output workflow](../.github/workflows/observable-affordances.yml)
saves both complete cohort result tables and runs all controls.
The existing full Linux/Windows suite also includes these tests and
benchmarks. No new AthenZ or Synveil integration has been made.
