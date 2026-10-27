# Anonymous-action causal discovery across different dynamics

**Status:** Optional standalone research experiment, not a replacement for
`OutcomeSkills`, `TransferBrain`, or any other default. October 20, 2026.

## Why this exists

Earlier source/assembly/delivery benchmarks used a **fixed manually shared
glyph/fact vocabulary**. Merely rotating an action's opaque ID did not test
whether the learner could function in an unfamiliar action ontology.

This experiment reuses the *same* observable-feedback controller on two
separately hand-authored environments with **different underlying physics**:

- `relay`: latched Boolean switches, one two-input AND prerequisite, a
  gate chain, and distractors. State changes are monotonic.
- `cargo`: multi-unit extraction, a charge requirement, consumptive
  processing, loading, shipment, a spoilage operation that can irreversibly
  prevent success, and a distractor. State changes can be **negative**.

Neither public observation contains `relay`, `cargo`, action meanings,
hidden recipes, semantic glyphs, privileged solution paths or stable action
identifiers. Action IDs and numeric sensor channel order rotate every
episode. The public goal is only an anonymized sensor channel and threshold.
The model sees the before/after vector and whether its selected action was
accepted.

**Shared engineered priors:** Both worlds expose one numeric sensor vector,
a list of anonymous action handles, one goal predicate, and one Boolean
accepted/blocked feedback; the learner is handed those structured fields.
It is not learning how to parse raw multimodal observations or natural
language. Two hand-authored families do **not** constitute an independently
administered generalization benchmark.

## Separate protocol committed before model implementation

See `benchmarks/opaque_causal_protocol.json` at commit `d3e9845`.
It lists all development and reserved seeds, indices, budgets, baselines,
outcome measures and explicit nonclaims before any model was executed.
No result-driven change to this protocol is permitted.

- Development seeds: 1103, 1109, 1123.
- Reserved seeds: 2017, 2027, 2039. These must be evaluated only once with
  the frozen candidate; thereafter call them **inspected**, not blind.
- Relay source train: `train/0..47` (48 episodes per policy).
- Separate relay source-validation diagnostic: `train/500..523`.
- Evaluation for relay and cargo: `test/8000..8059` (60 episodes each
  per seed and family).
- Episode action budget: **18** steps. Exploration parameters are frozen.
- Baselines: three original fixed heuristics (`novel`, `retry`,
  `switch`), simple cyclic and random, and a privileged **oracle**.
- Outcomes: task completions, attempted/blocked actions, steps with
  decreasing sensor values, and true spoilage actions (privileged for
  **benchmark scoring only**). Negative sensor changes can be productive
  consumption, so decreasing channels do **not** necessarily mean harm.

## Actual model

`OpaqueEpisodePolicy` learns during each episode: it remembers which
anonymous actions were attempted, at what observable state, and whether
they were blocked. It avoids retrying a blocked action without a state
change, and reconsiders it when sensor readings change. Three prewritten
variants differ in the priority given to untried versus newly retryable
actions. No mapping of action IDs or channels transfers across episodes,
because the handles are newly randomized and *no invariant action
description is supplied*.

`StrategySelector` uses observed completions and action costs from the
**relay source family only** to select one of these three engineered
strategies. Its persisted selection and episode feedback are replayed.
The selected strategy then runs **without cargo training** on the second
family. This is a small study of transferring an *exploration-strategy
choice* rather than acquired action/effect knowledge. Its design creates
an intrinsic ceiling on true zero-shot skill transfer; note failures.

**No hidden recipe access in the candidate:** `_relay` / `_cargo`
and `_privileged_plan` live in the simulator/benchmark and are not read
by `OpaqueEpisodePolicy` or `StrategySelector`.

Journal integrity: versioned SHA-256 with replay-validated policy decisions
and public state continuity. The digest is NOT authenticated provenance and
cannot prove a wholly forged yet internally consistent history is real.
The experiment does not touch human data, OS privileges, networks, or
third-party integrations.

## Results on the precommitted cohorts (inspected development evidence)

The original one-family raw-token alignment and outcome-skill benchmarks
remain unchanged. The reserved cohort was first run in GitHub Actions
after the protocol and implementation were fixed. It is **now inspected**;
future changes cannot treat it as a fresh blind holdout.

Results are **successful tasks out of 180 episodes per cohort**, combining
three seeds and 60 test episodes per family per seed.

| Family / cohort | Trained-choice | Novel-first fixed | Retry-first fixed | Switch fixed | Cyclic | Random | Privileged oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Relay, development | 180 | 180 | 167 | 180 | 180 | 148 | 180 |
| Relay, reserved | 180 | 180 | 168 | 180 | 180 | 145 | 180 |
| Cargo, development | 67 | 67 | 53 | 59 | **68** | 42 | 180 |
| Cargo, reserved | 80 | 80 | 66 | 73 | 77 | 40 | 180 |
| **Cargo, combined / 360** | **147** | **147** | 119 | 132 | 145 | 82 | 360 |

Source training selected the *prewritten novel-first heuristic on every one
of six seeds*. The learned-choice column is therefore **identical** to the
unaltered novel-first baseline, not a distinct learned improvement.
Its net +2/360 cargo successes over cyclic exploration is negligible as
evidence for policy transfer; the cyclic baseline actually wins on the
development cohort (68 vs 67). Simple fixed methods saturate the relay
family. The oracle succeeds on both families, showing they are feasible.

### Diagnosed cargo failure — irreversible harm

Across all 360 cargo tasks, the selected method successfully executed the
hidden spoilage action **213 times**, versus **212** for cyclic. The selected
method failed exactly **213** cargo episodes in this generator. This strong
association is not evidence that the policy identified spoilage; the action
was scored by simulator-private labels **after** the public learner acted.

Spoilage irreversibly consumes cargo before processing; with no stable
semantic action descriptions or action-to-effect identity across episodes,
the agent cannot know which anonymous handle is harmful before trying it.
Its no-repeat rule reduces wasted blocked attempts, but cannot solve this
information deficit. The oracle has the hidden action meanings and avoids
spoilage entirely, so it is not a fair equally-informed comparator.

The learner's cargo action count is shorter than cyclic's, but some
episodes end early or stall, and shorter failed episodes are **not** a
quality improvement. Scores and costs must be read together.

**Scientific conclusion:** The mechanism learns episode-local
accepted/blocked histories and can replay them, but source policy selection
does **not** demonstrate a meaningful zero-shot cross-family advantage.
There is no learned stable action semantics, no learned causal graph shared
between worlds, and no evidence of semantic generalization.

### GitHub execution

[The initial full execution](https://github.com/magicmantheace/Developmental-AI/actions/runs/39542047394)
passed Linux full tests **523/523**, historical 3-seed transfer,
all previous symbolic/continual/prerequisite benchmarks, and both new
precommitted cohorts. The Windows focused suite passed **65/65**.
An additional benchmark immutability assertion was committed afterward;
check the latest run for an exact-current-HEAD pass.

```sh
python -m unittest tests.test_opaque_causal -v
python -m benchmarks.opaque_causal_benchmark --cohort development
python -m benchmarks.opaque_causal_benchmark --cohort reserved
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

## Next discriminating gate

The next real test should give the model a *learnable stable action
description* (rather than a meaningless rotating ID) that is expressed in
independently changing observation modalities; infer a latent
action/effect representation and compare it with a matched from-scratch
agent. Also evaluate unseen dynamics, longer tasks, stochastic and
nonstationary consequences, **matched total training cost**, and
forgetting on earlier tasks.

Until then, successful causal probing would demonstrate a bounded generic
algorithm on two structured toy simulators, not cognitive independence,
general intelligence, transferable semantic understanding or consciousness.
AthenZ/Synveil integration remains deferred. V2A computational affect stays
before/overlapping V2B virtual environment.
