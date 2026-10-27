# Stable numeric action descriptors and observational hazard memory

**Status:** Optional, simulation-only development experiment. No promotion,
integration work, real-world action authority, or D3 acceptance claim.

## What changed

The preceding [anonymous-action cross-dynamics experiment](OPAQUE_CAUSAL_GENERALIZATION.md)
could not reliably avoid a harmful cargo action: every action ID changed each
episode and the public record contained no stable descriptor to recognize it.
The source-trained strategy selector was identical to a fixed heuristic;
cargo reached 147/360 versus cyclic 145/360 and oracle 360/360. That negative
result is **unchanged**.

This study explicitly supplies a new engineered feature: each available
action gets a **stable two-byte numeric descriptor**. Opaque action handles
and public sensor channel order still rotate per episode. The feature is
constructed by hashing the simulator's private action kind together with the
seed and environment family; **this is a disguised stable action identity,
not automatically learned semantic perception or cross-domain skill
transfer**. The generated public frame contains only numeric descriptors,
rotating handles, sensor values and goals. The learner cannot inspect
the simulator's private action table or plan.

`RiskMemory` stores up to 80 training episodes of public action signature
and accepted/blocked evidence, public sensor increases/decreases and the
terminal goal-success bit. It computes *observational* failure association:

- At least three failures with the accepted action.
- At most 10% successful episodes with that action (floor of one).
- At least three successful episodes without the action.

These thresholds and an optional risk veto are **hand-engineered priors**,
not calibrated confidence or causal proof. Actions correlated with failure
may be innocent; excluding necessary actions could worsen performance.
The default `OpaqueEpisodePolicy` is unchanged.

The memory is versioned and SHA-256 checksummed and reconstructs its
statistics from bounded event history upon restart. A direct `save`/`load`
interface now writes a size-limited (2 MiB maximum) JSON checkpoint to a
caller-selected **local** path through atomic replacement with file
flush/fsync and checksum/replay validation at load. The saved state is
never automatically published or used to promote a policy.
This proves internal consistency only; it cannot authenticate a forged
coherent training history or owner consent. Test evaluation is read-only.
Model updates cannot promote themselves to a default policy.

Example with the repository's ignored `private/` directory:

```python
from pathlib import Path
from developmental_ai.affordance_memory import RiskMemory
from benchmarks.affordance_benchmark import learn

memory, _ = learn(31013)
path = Path("private/affordance-risks.json")
memory.save(path)
restarted = RiskMemory.load(path)
assert restarted.record() == memory.record()
```

## Frozen development protocol

See [the protocol](../benchmarks/affordance_protocol.json), committed first
as `9de944a6`, before implementing the learner. The implementation was
corrected to match its **two-byte descriptor** definition before reporting
benchmark results. The task generators are identical to the earlier
`OpaqueWorld`; only public numeric descriptor observations are added.

- Development seeds: 31013, 31019, 31033.
- Reserved seeds: 43013, 43019, 43033. Once executed, these too become
  inspected development cohorts.
- **Training**: cargo `train/0..79`, **80** unfiltered novel-first
  exploration episodes per seed. The learner receives the same
  observations and outcomes as this control; this is not a privileged
  recipe-training run.
- **Testing**: cargo and relay `test/8200..8259`, 60 episodes per
  seed per family, with 18 attempts max and no learning at evaluation.
- Comparisons: trained risk veto, original untrained novel-first, cyclic,
  random, descriptor-shuffled test ablation, privileged spoilage-code
  oracle using the same novel-first controller, and privileged complete
  action-order oracle.
- Outcomes: completed tasks, number of attempts, blocked attempts,
  spoilage, negative sensor steps and early stall. Sensor decreases can
  also be necessary, productive consumption; never conflate all
  negative steps with harmful acts.
- No held-out task reward, hidden name or simulator recipe may appear in
  the learner's scoring or memory updates.

### What success can and cannot show

An improved cargo score would show **within-family reidentification** of a
harmful action after cargo training. It is not zero-shot transfer:
the agent received 80 cargo episodes first. The relay test is a
retention/no-interference check, **not** a demonstration of transfer,
because numeric descriptors are deliberately scoped to a seed and family.
Even strong gains would be evidence for one highly designed simulator
with stable identity features—not independent autonomous cognition.

Strong baselines and the shuffle ablation are essential. If filtering
underperforms fixed heuristics, preserve that result. All cohorts and
individual seeds must be reported; there is no automatic promotion.

## Measured development results — six inspected seeds

These are **within-cargo-family** test outcomes after cargo training.
The reserved cohort has now been evaluated and is **inspected**; it is
not available for subsequent independent tuning.

| Policy | Development /180 | Reserved /180 | Combined /360 |
| --- | ---: | ---: | ---: |
| **Learned descriptor-risk veto** | **180** | **180** | **360** |
| Same novel-first policy, no memory | 62 | 74 | 136 |
| Learned risk memory, descriptors shuffled each episode | 62 | 74 | 136 |
| Fixed cyclic | 69 | 65 | 134 |
| Random | 47 | 49 | 96 |
| Privileged simulator hazard-code veto | 180 | 180 | 360 |
| Privileged full-action-order oracle | 180 | 180 | 360 |

- Original unfiltered training succeeded on **158 of 480** tasks across
  six seeds (80 episodes each); no privileged semantic action labels entered
  the learner during training.
- Each seed's replayed memory identified **exactly one** candidate
  failure-associated numeric descriptor.
- Trained evaluation had **0 successful spoilage actions**; the
  untrained policy had **224/360 successful spoilage actions**, equal to
  its 224 failed cargo episodes.
- The descriptor-shuffle negative control exactly matched the
  no-memory baseline on these cases. This supports a narrower conclusion:
  recurrence of an **engineered stable descriptor** is necessary for
  this risk filter to work.
- The previously known relay-world test remained **360/360** with
  training-derived memory; relay also reaches 360/360 with simple
  fixed novel/cyclic methods. That measures no interference, not
  generalization or gain in relay proficiency.

Per-seed cargo trained results: 60/60 on each of
31013, 31019, 31033, 43013, 43019 and 43033.
Per-seed untrained results: 16, 23, 23, 29, 24, 21 successes
respectively, all out of 60.

**Interpretation:** The memory extracts a terminal-failure correlate
from public training outcomes. It can make future decisions on new
per-episode handles *because the numeric descriptor is stable*.
A disguised action-identity feature is a strong simulator prior; no
perceptual affordance representation is learned. A correlation that
identifies spoilage in one fixed environment might veto a productive
resource-consuming action when conditions change. The risk threshold is
not statistically calibrated, and the oracle and baseline share the
hand-designed environment. This does not establish independent causal
inference, transfer to different physics, real-world safety or D3
generalization.

### Verified GitHub checks

The [implementation's successful GitHub Actions run](https://github.com/magicmantheace/Developmental-AI/actions/runs/39594043121)
passed **537/537 Linux repository tests**, **79/79 Windows focused
tests**, the original three-seed transfer benchmark, all previous
optional cognitive experiments, and both new stable-descriptor cohorts.
Subsequent disk persistence and documentation changes require a new
successful HEAD check; prior green results cannot validate those new tests.

## Execution

```sh
python -m unittest tests.test_affordance_memory -v
python -m benchmarks.affordance_benchmark --cohort development
python -m benchmarks.affordance_benchmark --cohort reserved
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

**Validation:** The code-version GitHub run passed on both operating
systems; no automatic policy promotion or merge is authorized by this result.

## Next gate

Test whether stable features themselves can be learned from noisy
naturalistic observations instead of simulator-provided action identity.
Vary action-to-effect rules across episodes, require counterfactual
interventions to distinguish spoilage from productive consumption, and
measure performance against matched experience, cost and uncertainty
baselines on genuinely independent environments. Preserve V2A (computational
emotion) before and overlapping V2B (virtual environment); keep
AthenZ/Synveil integration deferred.
