# Prerequisite recovery experiment — 2026-10-20

## Narrow research question

Can an optional, evidence-aware controller use source skills on an unfamiliar
symbolic goal, then continue learning without degrading old-task performance?

`developmental_ai.prerequisite_recovery.RecoveryProber` is a **post-hoc V2
research proposal** layered over the current replay-verifiable
`OutcomeSkills` memory, not a new brain and not a default-policy change.
The original `PrerequisiteProber` code, benchmark and negative results are
unchanged.

The source/action `glyph` vocabulary and the names of produced facts are
**engineered and shared** across the metal, wood, assembly and delivery
tasks. The only renamed part is an opaque per-episode action ID.
No independent action-semantic inference, causal discovery or genuinely
unrelated task family is demonstrated.

## Diagnosed failure

A stepwise investigation of the earlier raw prober revealed a failure mode:

1. It stored successful contexts containing unrelated facts as candidate
   prerequisites.
2. After learning a new action, it tried the action too soon and too often
   while its prerequisites were still missing.
3. It spent limited steps pursuing irrelevant learned tools instead of
   continuing toward the goal; training could **decrease success**.

The separate V2 recovery candidate uses isolated failed/successful observation
contrasts to prioritize preparation while all known glyphs are from source
training. On discovery of a newly **accepted** action effect, it hands
control to the pre-existing, more reliable `OutcomeSkills.choose` policy.
It remembers its initial source-glyph set through a separately versioned,
digest-checked, fully replayed source-history boundary. No simulator
`RECIPES` lookup is used in the agent. Test evaluation is read-only.

**Critical limitation:** This is an engineered controller handoff, not a fix
for the original prober's faulty prerequisite model. It cannot certify
retention, automatically promote weights, authenticate approval, or
generalize beyond the supported observations.

## Post-hoc benchmark

`benchmarks.prerequisite_recovery_benchmark` deliberately retains
the *already inspected* three development and three additional seeds.
Source training is 80 metal/wood episodes. Each controller independently
receives 0, 1, 2, 4, 8, then 20 delivery episodes. Test cases use indices
97000–97029 in the symbolic generator, with 30 delivery and 30 assembly
episodes per seed per stage. Stage evaluations reuse the same test cases:
**NOT a blind, independent assessment**.

Controls: raw original prober, historical outcome-skills policy
with identical target exposure, frozen original source policy,
target-only V2 (same target training episodes but 80 fewer total episodes),
and a privileged recipe-aware oracle. Retention, success and attempted
action cost are measured. Controller source checkpoint replay and
post-evaluation immutability are verified.

### Isolated local development results

The following are local scoped runs of the symbolic files, **prior to full
repository CI execution**. Numerators count delivery successes across six
inspected seeds (180 episodes per stage):

| Extra delivery training | V2 recovery | Original raw prober | Historical learner | Target-only V2 | Privileged oracle |
|---:|---:|---:|---:|---:|---:|
| 0 | 75 | 40 | 0 | 2 | 180 |
| 1 | 0 | 0 | 0 | 0 | 180 |
| 2 | 150 | 0 | 0 | 0 | 180 |
| 4 | 180 | 0 | 180 | 0 | 180 |
| 8 | 180 | 0 | 180 | 0 | 180 |
| 20 | 180 | 0 | 180 | 0 | 180 |

In the same scoped study, V2 recovery retained **180/180 assembly successes
at every stage**. This is useful *within this synthetic ontology*, and
the additional target-only control remains unsuccessful despite matched
delivery exposure. Do **not** interpret it as a statistically supported
generalizable improvement or experience-matched lifelong learner. The
V2 result at one episode is a conspicuous regression and is **not hidden**.

All algorithm choices and all seeds were inspected while developing this
study. More seeds from the same underlying code generator would still not
establish independent task-family generalization.

## Reproduction and acceptance

```sh
python -m unittest tests.test_prerequisite_recovery -v
python -m benchmarks.prerequisite_recovery_benchmark --cohort dev
python -m benchmarks.prerequisite_recovery_benchmark --cohort additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

Do not merge the branch until complete Linux and focused Windows suites are
verified on the **same commit**, including unchanged historical regressions.
Earlier CI was green at commit `8af13410`; that is not proof for later
commits. No authorization to install this candidate as the default.

## Next work

1. Move beyond fixed shared glyph/fact meanings with independently written
   navigation, resource management and manipulation generators.
2. Evaluate a genuinely task-agnostic representation, with matched compute
   and experience controls and externally selected holdout tasks.
3. Learn only well-evidenced prerequisites; seek counterexamples and model
   uncertainty instead of assuming observational intersections are causal.
4. Measure sequential A→B→C→A retention with stochastic effects and changing
   goals, preserving failed experiments and rollback gates.

AthenZ/Synveil integration remains deferred; V2A emotional state still
precedes and overlaps V2B virtual environment after basic learning.
