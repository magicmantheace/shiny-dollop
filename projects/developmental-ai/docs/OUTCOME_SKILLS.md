# Outcome-derived reusable skills — development study (October 20, 2026)

## Scope and non-claims

This **optional simulation-only** study begins to move beyond caching action
traces. `OutcomeSkills` learns a mapping from *public action glyph* to
*observed added fact* and retains intersections of facts present before
successful actions as **hypotheses** about prerequisites.

The simulator rotates **opaque action IDs every episode**. The learner does
not read `SkillWorld`'s hidden `RECIPES` mapping, and only `observe`/
`choose` operate on public facts, available action descriptors and
accepted/blocked outcomes.

**Major engineered shortcuts:** Public glyphs such as `smelt` and `cut`
retain their meanings across families. Fact names are shared. All actions add
exactly one monotonic fact when accepted; the designated final action is
provided in the public frame; training and evaluation families are assembled
from the same developer-written recipe library. The controller tries a new
goal once, then proactively completes previously learned subskills. It is not
a generally learned planner. Correlated facts can be mislabeled as
prerequisites, and a success does not prove causality.

These families are **not independently designed domains**. The result
supports a narrow claim of skill reuse and goal composition within one
symbolic action ontology, **not closure of D3 generalization or D4
general-purpose skill discovery**, nor human-level cognition.

## Development protocol

- Predeclared development seeds: `17011, 17021, 17027`.
- Predeclared supplemental seeds: `33011, 33023, 33031`.
- Source training: 80 alternating `metal` / `wood` episodes per seed.
- Evaluations: 60 `assembly` and 60 `delivery` episodes per seed in
  `test` namespace at indices `90000..90059`.
- Baselines: same-budget `target_only` training; `no_memory` reactive
  controller; random; **privileged recipe oracle**.
- Neither the seed cohorts nor the generator is blind: algorithm choices were
  made after inspecting development results, and the supplemental seed
  outcomes have now been inspected once as well.
- Fixed action-budget limits: metal/wood six actions, assembly eight,
  delivery ten. No environment or hidden prerequisite is supplied to the
  public learner.
- The protocol is documented **after** development tuning, rather than
  falsely portrayed as independently precommitted.

## Reproduced local simulation results

Each numerator below is the number of completed episodes out of 60.

| Seed | Assembly: transferred / target-only / random / oracle | Delivery: transferred / random / oracle |
| --- | --- | --- |
| 17011 | 60 / 0 / 4 / 60 | 0 / 0 / 60 |
| 17021 | 60 / 0 / 7 / 60 | 0 / 0 / 60 |
| 17027 | 60 / 0 / 5 / 60 | 0 / 0 / 60 |
| 33011 | 60 / 0 / 6 / 60 | 0 / 1 / 60 |
| 33023 | 60 / 0 / 5 / 60 | 0 / 0 / 60 |
| 33031 | 60 / 0 / 6 / 60 | 0 / 0 / 60 |

Totals:
- Assembly transferred: **360/360**, versus same-budget target-only **0/360**,
  memoryless **0/360**, random **33/360**, privileged oracle **360/360**.
- Delivery transferred: **0/360** versus oracle **360/360**. This negative
  result is preserved as a missing skill-composition capability.
- Assembly mean attempted actions: transferred **6.0**, oracle **5.0**.
  The extra failed goal probe means performance remains less efficient
  than an engineered recipe-aware planner.
- Delivery transferred always exhausted **10** actions; oracle needed **7**.

The target-only control also fails, showing that this particular short-budget
exploration strategy does not discover deep unseen recipes reliably. This
baseline is not a substitute for a stronger engineered heuristic. Existing
action outcomes in this study are deterministic; statistical significance
across six seeds of this one fixed recipe library should not be taken as
broad-distribution evidence.

## Local validation and persistence

From repository root:

```sh
python -m unittest tests.test_outcome_skills -v
python -m benchmarks.outcome_skills_benchmark --cohort dev
python -m benchmarks.outcome_skills_benchmark --cohort additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

In the isolated local copy of the **new files**, ten focused tests passed.
The **full upstream repository suite was not run**, because a working private
repository checkout is not available. GitHub's attempted private Actions
jobs failed before any test steps, with no relevant logs; do not claim CI
success or assume the existing PR is merge-ready.

The skill memory exports a versioned, size-bounded JSON record, supports
atomic local file replacement, and checks exact reconstructed knowledge upon
restore. A digest detects accidental/rehashed *summary* corruption but is
not authenticated provenance. A forged full event history and matching
digest cannot be distinguished from real outcomes; future trusted event
provenance must be handled separately.

**Example:**

```python
from developmental_ai.outcome_skills import OutcomeSkills

learned = OutcomeSkills()
learned.observe("collect_ore", [], ["ore"], True)
learned.observe("smelt", ["ore"], ["ingot", "ore"], True)
learned.save("private/outcome_skills.json")  # private/ is excluded by .gitignore

restored = OutcomeSkills.load("private/outcome_skills.json")
assert restored.knowledge() == learned.knowledge()
```

## Next scientific gate

A better test must introduce at least one independent environment family whose
observation structure, action ontology and reward mechanisms are **not**
hand-aligned to this module. Add genuinely new action kinds, uncertain
effects, negative effects, prerequisite interventions, uncertainty/abstention,
and a strong reactive planner. Test a frozen candidate once under independent
evaluation after the learning method and protocol are fixed. A returned
score must retain all failures and resource costs.

No changes to AthenZ or Synveil. Existing V2A-before/overlapping-V2B ordering
is preserved.
