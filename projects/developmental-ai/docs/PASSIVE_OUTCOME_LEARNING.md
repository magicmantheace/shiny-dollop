# Passive public-outcome observation under an unfamiliar rule

**Experimental simulation-only. No claim that observational data is
harmless to obtain, causally sufficient, or safe for real-world action.**

## Verified two-cohort results — October 21, 2026

[Focused GitHub Actions run 39718642738](https://github.com/magicmantheace/Developmental-AI/actions/runs/39718642738)
passed **11/11 focused regression tests** and both complete
3-seed cohorts. The development seeds (95003, 95021, 95039)
and initially precommitted reserved seeds (96001, 96017, 96041)
are **both now inspected**, so neither is a fresh blind holdout
after this result. The focused run retains the exact JSON data.

### Held-out third-rule task performance

Six seeds × 60 previously untouched TEST episodes per seed,
total **360 tasks per policy**:

| Policy | Completed | Accepted harmful TEST actions | Explicit abstentions |
| --- | ---: | ---: | ---: |
| Raw 5NN from **240 random passive outcomes** per seed | **253/360** | **10** | 0 |
| Guarded 5NN from same 240 random outcomes | **160/360** | **10** | 190 |
| Guarded 5NN from **24 subset outcomes** per seed | **22/360** | 0 | 334 |
| Guarded 5NN from **240 old-policy actor outcomes** per seed | **0/360** | 0 | 360 |
| Frozen normal outcome memory | 0/360 | 293 | 0 |
| Frozen reversed outcome memory | 0/360 | 296 | 0 |
| Always abstain | 0/360 | 0 | 360 |
| Privileged private-outcome oracle | **360/360** | 0 | 0 |

A zero-harm refusal is **not** a completed task, and the
guarded policy's 10 harmful test actions exactly match the
unfiltered passive learner's 10, while completions decreased
from 253 to 160. The guard therefore did **not** improve
measured safety on these cohorts, despite being conservative
about unsupported numeric neighborhoods. It must not be
promoted as a proven safety system. The raw policy also does
not meet zero-harm requirements.

### Cost and provenance of observational evidence

The learner issued **zero action commands** during data acquisition.
The **independent simulated actors** nevertheless caused harm:

| Observation stream (six seeds) | Actions | Harmful | Productive | Neutral |
| --- | ---: | ---: | ---: | ---: |
| Uniformly random, full corpus | **1,440** | **302** | 490 | 648 |
| Previous normal-rule actor, separate corpus | **1,440** | **450** | **13** | 977 |
| Random **24-observation prefix**, subset of full corpus | 144 | 34 | 51 | 59 |

The 144-event prefix **reuses** the first 24 observations
from each seed's full random corpus; its 34 harmful actor
events must **not** be added again to the 302 already
counted under the full corpus. The old-policy actor's severe
covariate/behavioral selection bias yielded only 13 productive
events in 1,440 attempts; its passive memory failed every
third-rule TEST task by abstention. This is evidence that
external observations may be insufficient or systematically
misleading, even if genuine and untampered.

The two distinct full observation corpora totaled **2,880
simulated actor actions and 752 harmful actions**, *not*
zero collection cost. Which corpus an actual independent
observer would make available is not guaranteed, and the
simulator's metadata alone does not establish owner consent,
independent third-party authorization or data authenticity.
The archive recomputes public sensor deltas and checks
digest integrity, but a determined producer could supply
entirely fabricated internally consistent transitions.

### What this advances—and what it does not

The learner gained a measurable third-rule capability
**after consuming 240 examples per seed** of previously
observed action outcomes, compared with its old normal/reversed
models' 0/360 performance on that rule. This is an
*observational, supervised-outcome* capability: it does not
derive the hidden physical law or perform counterfactual causal
inference. Models and action measurements are still engineered,
the simulator generator is familiar to the researchers, and the
observations are not naturalistic data or human demonstrations.
It still causes test harm. The model does not autonomously
decide what new history to trust or promote, cannot audit
consent, and has no OS/network authority.

**Next experiment:** precommit an **independent observation
generator** with unknown source quality and third-party
provenance, and test error bars/calibration on held-out action
features before letting observationally trained policies act.
Evaluate whether data bias and intentional corruption are
detectable from public records alone; do not claim that
mere checksums authenticate real-world truth. Preserve this
entire raw vs filtered negative comparison and all earlier
source/target studies as immutable baselines.



The previous [absolute adequacy study](ABSOLUTE_ADEQUACY.md)
identified all six already-inspected third-rule contexts as unknown,
but completed zero tasks. It used 48 disposable probes in that new
rule, **16 of which caused simulated harm**. This next experiment
separates WHO takes actions to generate evidence from the learner
which reads already observed outcomes.

The [frozen pre-implementation protocol](../benchmarks/passive_outcome_protocol.json)
uses the same hand-authored third-rule simulator, a disjoint TRAIN
observation namespace and two new precommitted seed cohorts.
An independent **simulated external actor** chooses actions from
public frames, with no true action labels. Its consequences are
observed by `PassiveOutcomeArchive`, which **cannot choose an
action or call the world simulator**. The actor is not a real person;
the provenance is controlled by a benchmark harness, not an
authenticated source. Exact before/action/after public sensor
changes are recomputed and replayable with SHA-256 integrity.

- Each seed: 240 random one-step actor observations from
  `train/3000..3239`, and 240 observations from a separate
  source-trained *normal-law* actor in `train/3300..3539`.
- 24-observation comparison uses the exact first 24 of random240,
  with no independently sampled data.
- Candidate is an ordinary numeric five-nearest-neighbor outcome
  learner fitted ONLY on the passive transitions. The guarded policy
  requires at least five neighbors, mean productive effect >=0.6,
  and **zero estimated damage in its five neighbors**; otherwise
  it declines the action. This is a heuristic, not a credible
  upper bound on unseen hazards.
- Read-only held-out test namespace `test/23000..23059` on the
  third rule (60 goals per seed). Controls: raw passive learner,
  guarded 24/240 observations, bias-affected actor observations,
  the unchanged old normal/reversed models, zero-action abstention,
  and unfair simulator-privileged oracle.
- The benchmark reports **learner-issued calibration actions = 0**,
  but separately reports EVERY *external simulated actor* action
  and its damage, productive effects and neutral results, plus
  later test completion, harmful actions and aborted tasks.
  An externally sourced dataset may have profound harms,
  distribution bias, consent, provenance, and privacy concerns.
  None of these are solved by a passive API.
- Original old-model memories and passive archives remain
  immutable throughout held-out testing. All seed lists are frozen;
  after either group is inspected it is not blind.

These results cannot establish transferable biological
perception, independent self-development, causal identification,
zero-risk learning or real-world action safety. Third-rule
physics and numeric features remain fixed and engineer-defined.
No automatic policy promotion, no actual external observer
connection, no changes to Synveil/AthenZ or project priorities.

```sh
python -m unittest tests.test_passive_outcome -v
python -m benchmarks.passive_outcome_benchmark --cohort development
python -m benchmarks.passive_outcome_benchmark --cohort reserved
```
