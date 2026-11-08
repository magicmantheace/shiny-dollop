# Sequential numeric outcome retrieval — A → B → A

**October 22, 2026. Experimental draft PR only; not a promoted controller.**

## Scientific question

Can a single agent keep earlier *experienced* outcome associations available while
adapting to a reversed environment, then recover its original competence with
only 12 new examples? This is a narrow **continual-learning/retention** study,
not generalization to genuinely new task families. The learner is the existing
`NumericOutcomeMemory` kNN method with an **opt-in** block-retrieval component;
old behavior and previous test baselines remain unchanged.

### Freeze and separation

- Protocol committed at `1b75efa`, amended with explicit random baseline and
  holdout anti-leakage at `c723ddc`, both **before learner implementation**
  `546c8d1`: [regime_retrieval_protocol.json](../benchmarks/regime_retrieval_protocol.json).
- Six newly enumerated seeds in two cohorts: 112003/112021/112039 and
  113001/113017/113041. All have now been **inspected**; do not call them blind.
- Each seed: A/route: **160** independent random first-action observations;
  B/route-reversed: **160**; return to A: **12**. Test uses three disjoint
  60-episode cohorts per seed. Evaluation does not modify training memory.
- Separate random actor provides public numeric `features,progress,damage`
  from observed before-action-after frames; the learner never acts during
  training. Actor harms are recorded separately.
- The learner is NOT told domain names, phase labels or stage boundaries.
  A frozen 64-example chunk can be selected by log likelihood on the
  latest 12 events. A candidate chunk may not contain any of those 12
  scoring examples; tie breaks are deterministic. If the evidence threshold
  is unmet, no bank decision is made.
- Full ordered event checkpoint is SHA256-verified, schema-checked, and
  deterministically replayed; each phase tests a complete shutdown/restart.
  SHA integrity does **not** authenticate the data's origin.

## Outcomes

Focused run: [39777573677](https://github.com/magicmantheace/Developmental-AI/actions/runs/39777573677).
All **8 focused unit tests passed**, both three-seed benchmark cohorts
completed, detailed per-seed JSON in CI artifact. Counts below aggregate
six seeds, 360 TEST episodes per phase and method.

| Method | A successes | B successes | Return A successes | A/B/return harmful TEST actions |
| --- | ---: | ---: | ---: | ---: |
| **Retrieved earlier memory** | **360** | **360** | **360** | **0 / 0 / 0** |
| All-time cumulative 5NN | 360 | 0 | 160 | 0 / 360 / 200 |
| Recent 32 outcomes 5NN | 360 | 360 | 1 | 0 / 0 / 359 |
| Frozen A only 5NN | 360 | 0 | 360 | 0 / 360 / 0 |
| Untrained random | 26 | 27 | 17 | 334 / 333 / 343 |
| Always abstain (task failure) | 0 | 0 | 0 | 0 / 0 / 0 |
| Privileged simulator oracle (reference only) | 360 | 360 | 360 | 0 / 0 / 0 |

Independent training actor totals **1,992 first-action simulator events**:
**664 harmful, 1,016 productive and 312 neutral**. These harmful source
actions are *real within the simulator*, even though the learner itself
triggered zero training interventions. They are **not** the harmful
TEST actions listed above. No extra actor runs for each baseline.

### Interpretation

The retrieval method matches the most favorable simple specialist at
every stage; it beats both cumulative and recent-window baselines **on
the early return after 12 observations**, without sacrificing B at the
tested 160-observation point. This is measurable experience retention and
retrieval, not new causal representations. Frozen A is equally good on A
and return-to-A but fails catastrophically on B. Recency alone handles B
but forgets A, and cumulative history is misled by conflicting labels.

### Failures, limitations, and review barriers

- **No new task family:** A and B use opposite versions of *one*
  explicitly engineered feature-outcome simulator. The visual/input
  vocabulary and task goal are fixed; all public features are designed
  by developers. The benchmark is **not** D3 completion.
- Retrieval selects among learned, fixed **64-sample chunks** with a
  hand-chosen **12-sample scoring window** and known kNN/smoothing. Block
  boundaries can mix regimes and early reversal data may be inadequate.
- No authenticated source or collusion defense. A forged but internally
  consistent public record can poison all retrieval choices. Past
  paired-witness negative evidence remains unresolved.
- At least **12 new actions and feedback** are needed for the early return
  evaluation. The learner is not zero-shot, and independently caused
  simulated harm remains substantial.
- No test of noisy dynamics, drifting transitions, unseen observation
  vocabularies, new goals, three or more regimes, or uncertainty-aware
  refusal. The perfect 360/360 figure reflects the narrow task only.
- Results are from six now-inspected seeds. They have not been
  independently replicated by a fresh environment author. No claims of
  real-world safety, consciousness, identity reconstruction, or autonomous goals.

## How to reproduce

```bash
python -m unittest tests.test_regime_retrieval -v
python -m benchmarks.regime_retrieval_benchmark --cohort development
python -m benchmarks.regime_retrieval_benchmark --cohort additional
```

## Next falsifiable research gates

1. Freeze genuinely independent environment-family generators and feature
   vocabularies before seeing held-out results; compare to strong simple
   baselines at matched feedback and training costs.
2. Evaluate **prequential** switching after 0, 4, 8, 12, 24, and 48
   observations per reversal, counting all training harms and wrong
   interventions. Test corrupted and biased source records separately.
3. Extend to A→B→C→A→B long-run retention/retrieval with checkpoint
   interruption, noisy transition rules and explicit retrieval-confusion
   metrics versus replay, recent-window and cumulative alternatives.

This experiment remains opt-in on the **draft PR**. It does not change
main, authorize interventions, or integrate AthenZ or Synveil.
