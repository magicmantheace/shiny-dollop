# Quarantined C learning and approval review (2026-10-21)

**Sandbox experiment; not a live update, self-promoting agent, real-world
safety authority or general intelligence benchmark.**

## Motivation and prior evidence

The two-sentinel public-feedback controller recognizes two previously
trained cargo mappings A and B. The [focused C stress run](https://github.com/magicmantheace/Developmental-AI/actions/runs/39641245853)
established **360/360** simulated task completions in A and B, with
zero successful spoilage actions. It flagged **360/360** unknown C
instances, likewise with zero spoilage, but completed **0/360** C tasks.
The prior no-cue policy completed **79/360** C tasks and the
untrained policy **120/360**; the privileged oracle completed 360/360.

Those results show the important limit of abstention: the safeguard
stops unsupported behavior, but is not a learning mechanism capable of
handling the unfamiliar mapping. C is still just a *descriptor
remapping* in the same small deterministic cargo simulator. It is
NOT new physics, real perceptual novelty, or an independently
selected domain.

## Protocol frozen before implementation

See [benchmarks/quarantined_c_protocol.json](../benchmarks/quarantined_c_protocol.json).

- Keep historical A and B source memories untouched, each trained on
  80 unfiltered episodes.
- Collect **80 NEW C episodes** from public simulator observations
  and outcomes only, using ordinary unfiltered novel-first
  exploration in an **offline disposable simulation**. Training
  namespace `train/600..679`; no privileged true action-name
  labels enter the candidate memory.
- Candidate memory is the existing deterministic replay-verifiable
  `RiskMemory`. The simulator still supplies two-byte numeric
  identifiers derived from hidden action names: **engineered identity
  is a major shortcut**, and all C seeds are already inspected.
- Train-only validation is separately scoped to indices
  `train/1200..1223`, 24 A, 24 B and 24 C tasks per seed.
  Rehearsal policy keeps the prior two diagnostic probes:
  recognized A/B uses prior memories, unknown C is routed to its
  newly trained memory *only in the offline rehearsal*.
- Predeclared gate: the isolated C memory must have exactly **one**
  observed failure-associated descriptor, disjoint from the two
  known risky descriptors; validation must complete **24/24**
  goals with **no spoilage** and **no stalls** in **each**
  A/B/C context. This deterministic toy threshold is
  **not** statistically calibrated evidence of general safety.
- The training source and candidate replay digests must remain
  unchanged. A single-use `StagedCReview` returns the full
  review receipt. It refuses `approved=False`, a wrong receipt
  hash, stale memories, or a failed review. The explicit approval
  method only issues an in-process sandbox route; it **cannot**
  install a default model or perform network/file/OS actions.
  Unit tests exercise approval using a *simulated caller*, NOT
  owner consent. SHA-256 receipts are integrity checks, NOT
  authenticated user authorization.
- After rehearsal, run read-only tests `test/9300..9359`
  for A/B/C (60 episodes per seed), alongside:
  original two-sentinel abstention, C-only memory without old
  context retrieval, raw untrained novel-first and a
  simulator-privileged hazard oracle. Measure successes,
  spoilage, stalls, attempts, active C routing and validation
  eligibility; include all six already-inspected seeds.

## Important scientific boundaries

1. C **receives 80 training episodes**. Any subsequent improvement
   is **within-family experience-based adaptation**, not zero-shot
   generalization.
2. The existing A/B histories are retained by separate storage rather
   than by learning one interference-resistant shared parameter set.
3. The preapproved in-process candidate can still be invalid
   under an unobserved D mapping; two sentinel probes may themselves
   harm in an environment with different resource dynamics.
4. A completely successful demonstration on the frozen toy
   simulator cannot justify autonomous self-approval, general
   causal reasoning, real OS authority, human equivalence, or
   milestone D3/D4 completion.
5. The benchmark's `approved=True` is **only a deliberate
   simulated approval call inside a testing harness**, never the
   human owner authorizing changes to a deployed system.
6. Code review and full unchanged historical regression tests remain
   necessary; the experimental PR stays draft/unmerged.

## Full inspected synthetic results — 2026-10-21

The [separate focused GitHub Actions run](https://github.com/magicmantheace/Developmental-AI/actions/runs/39645086099)
finished successfully. Its 11 dedicated unit tests passed, and both
complete three-seed development/previously-inspected additional cohorts
executed with all raw tables retained as CI artifacts.

Every seed completed its strict offline rehearsal gate (24/24 A,
24/24 B and 24/24 C tasks, zero spoilage/stalls), and the test harness
**simulated** `approved=True` only after validating the matching
receipt. **No owner authenticated approval was given** and no default
policy was changed.

The following outcomes are summed over **six previously inspected seeds**,
60 separate test episodes per seed and environment: **360 episodes per
environment**.

| Policy | A success | B success | C success |
| --- | ---: | ---: | ---: |
| **Offline staged C candidate** | **360/360** | **360/360** | **360/360** |
| Prior sentinel, abstaining on unknown | 360/360 | 360/360 | **0/360** |
| **C-only risk memory** (no context recall) | **0/360** | **0/360** | 360/360 |
| Untrained novel-first exploration | 138/360 | 138/360 | 138/360 |
| Privileged hazard oracle | 360/360 | 360/360 | 360/360 |

For staged C, **0 successful spoilage actions** and **0 stalls** occurred
across the 1,080 test tasks. The C-only baseline stalled on **all
720 A+B tasks** and recorded 442 accepted spoilage actions across
those two older environments (221 per environment). The untrained baseline completed only
138 per environment and caused 222 accepted spoilage actions per
environment. These old-task regressions are essential controls, not
errors to suppress. Source/candidate memories remained unchanged
through test evaluation and replay checks.

**Interpretation:** separate memory storage plus previously engineered
A/B diagnostic probes is enough to recover prior task success after
**additional C-specific simulation training**, while direct use of
the C memory on A/B fails. It does **not** prove online autonomous
adaptation, zero-shot C competence, general-purpose causal discovery,
cross-family generalization or real-world safety. Full repository CI
on the latest *documentation* commit must be checked separately;
the green focused run validates the unchanged candidate code.

## How to verify

```sh
python -m unittest tests.test_quarantined_c -v
python -m benchmarks.quarantined_c_benchmark --cohort development
python -m benchmarks.quarantined_c_benchmark --cohort inspected-additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

A [separate focused GitHub Actions workflow](../.github/workflows/quarantined-c-validation.yml)
records the full numerical result tables for both inspected cohorts
as retained artifacts. The original Linux/Windows full-validation
workflow and historical benchmarks are still the merge gate.

### Future work

Introduce an actual offline experimentation budget and a more realistic
novel environment that requires building action-effect representations
from non-identity features, include a genuine D holdout not used for
selection, compare with compute/experience-matched from-scratch agents,
and measure old-task interference after more than two changes.
Distinguish which low-risk interventions are *actually* safe rather
than relying on a hand-crafted resource-empty starting state.
V2A computational emotional state still precedes and overlaps V2B
virtual environment; Synveil/AthenZ integrations remain deferred.
