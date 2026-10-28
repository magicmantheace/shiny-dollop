# Blocked-outcome prerequisite evidence — experimental study (2026-10-20)

## Motivation

The existing source-trained `OutcomeSkills` system succeeds on the simple
assembly composition test but is not generally competent at unfamiliar
multi-step delivery goals. Its successful-context intersection can treat
coincidentally present facts as necessary prerequisites. A new optional
`PrerequisiteProber` explores the use of observed blocked/successful
transitions, while preserving the **original** `OutcomeSkills` implementation
and all frozen historical benchmarks untouched.

This is **not** an independently causal or graph-free system. The code
uses the same developer-designed shared action glyph and fact vocabulary as
the earlier tests; hidden `RECIPES` are simulator-only and no external
action interface is introduced.

## Implementation

- Reuses `OutcomeSkills.events` directly, without a second persistent
  memory architecture, schema migration, or silent model promotion.
- `constraints()` records successes, failures, positive co-occurrence,
  and singleton differences between a failed fact set and a successful
  fact set. Singleton differences are **suggestive observational evidence,
  not proof of causation**; confounded or failure-only relationships
  explicitly report uncertainty.
- Rejects unexpected public frame keys and forged failed-action context.
- Uses an episode-local list of blocked actions and their observable
  fact sets, to avoid retrying the same action in the same unchanged state.
- Reuses learned producer/effect relations and makes bounded, hash-ordered
  unknown-action probes, returning `None` if no allowable action remains.
- Clones and restores the underlying `OutcomeSkills` versioned history,
  so exact checkpoint replay and read-only evaluation are retained.
- No automatic rollout. This remains an optional research controller.

## Post-hoc development evaluation

`benchmarks.prerequisite_probing_benchmark` reports:

- Source: 80 alternating metal/wood episodes (unchanged source learner).
- Target: delivery training after 0, 1, 2, 4, 8 and 20 episodes.
- Test: 30 delivery and 30 assembly episodes per seed at indices 97000–97029.
- Candidate: new prober. Controls: unchanged/continued old learner,
  frozen original memory, target-only prober, and privileged recipe oracle.
- **Train-only controller selection**: 16 delivery and 16 assembly
  validations at train indices 230000–230015. Select the new prober only
  when it improves delivery success and does not reduce assembly retention;
  ties select the historical learner. The final test results are
  *not* used for this controller selection.
- Development seeds: 17011, 17021, 17027. Previously inspected additional
  seeds: 33011, 33023, 33031. All six are known development cohorts.
- Scores must report action costs, retention, failure, uncertainty and
  selection decisions, not only successes.

### Local isolated-reconstruction results

The following are runs of an isolated local test tree containing the new
modules and manually reconstructed existing symbolic learner/simulator
modules. The **exact full private repository checkout was not tested**.
The new focused tests passed locally. These results are preliminary
until the actual repository tests run; they are **not blind**.

Each cell is completed delivery tasks out of **180** total across all
six inspected seeds (30 per seed):

| Delivery training episodes | Raw prober | Existing learner | Train-validation-selected controller | Oracle |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 40 | 0 | 40 | 180 |
| 1 | 0 | 0 | 0 | 180 |
| 2 | 0 | 0 | 0 | 180 |
| 4 | 0 | 180 | 180 | 180 |
| 8 | 0 | 180 | 180 | 180 |
| 20 | 0 | 180 | 180 | 180 |

**Critical negative result:** Raw prerequisite probing deteriorates after
additional training. It is **not** a superior replacement for the existing
learner. The training-namespace validation selection rejects it at the later
stages and falls back to the existing controller, but this is a *fixed
two-policy selector*, not proof of lifelong learning or automatic safe
promotion. No candidate was installed as a default.

The historical 0/360 **zero-shot delivery** result for the original system
is unchanged. The 40/180 initial prober result is an additional
post-hoc experiment and uses a different task index cohort.

The new train validation task still shares the same simulator ontology and
noisy post-hoc design decisions; it cannot replace an independent audit.
Repeated evaluation of the same test indices after each stage is a
development-learning curve, **not separate independent test sets**.

## Validation and next work

```sh
python -m unittest tests.test_prerequisite_probing -v
python -m benchmarks.prerequisite_probing_benchmark --cohort dev
python -m benchmarks.prerequisite_probing_benchmark --cohort additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

Private GitHub Actions have previously failed *before steps began*. Do not
interpret a failed runner startup as a failing test or claim a passing
full suite. Keep the PR draft/unmerged until actual execution is available.

Follow-up priorities:

1. Diagnose why additional observational evidence degrades decision-making.
   Isolate spurious prerequisite intersections, excessive exploration, and
   target-goal retry costs with interventions and matched action budgets.
2. Test learned graph representations against independent task generators
   that change action vocabulary and observation structure, including
   stochastic and nonmonotonic effects.
3. Require matched total experience/compute as well as target exposure in
   future controls, and estimate confidence intervals across independent
   new tasks.
4. Introduce longer A→B→C→A retention and post-restart evaluation before
   any default-policy changes.

No AthenZ/Synveil development, no autonomous OS actions, no changes to
V2A-before-overlapping-V2B plans.
