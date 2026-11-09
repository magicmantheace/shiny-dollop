# Relation transfer, catastrophic interference and predictive conflict gating
**October 22, 2026 — two separately precommitted synthetic studies.**
**Status:** simulation-only optional research, draft PR #2 unmerged, no default promotion, no integration with AthenZ/Synveil, no real-world action authority.

## Research question and scientific boundaries

We are testing whether a model can learn a **measured relation** between otherwise anonymously named numeric observations and safely recover when the relation stops predicting outcomes. This follows the earlier **variable-schema** study, which acquired skills in multiple worlds but **did not outperform a target-only learner** on a new task.

The first protocol was frozen at commit `568897f` in [`relation_transfer_protocol.json`](../benchmarks/relation_transfer_protocol.json), **before** implementation and outcome inspection. The second, corrective follow-up protocol was frozen **after the first study's negative findings**, at commit `8ac9ac1` in [`relation_conflict_protocol.json`](../benchmarks/relation_conflict_protocol.json), before its adaptive implementation and independent seeded outcomes. This means the second experiment is a transparently motivated follow-up, not independent confirmation that the feature statistic generalizes beyond the author's chosen simulator.

### Mechanism and task construction

`RelationOutcomeMemory` fits a three-class conditional outcome estimate to the **numeric span** `max(observed_values) - min(observed_values)`. No source/target family name, band center, ground-truth effect function, stable handle or action-label dictionary is fed into the model. It reuses source evidence on new three- and four-feature target frames, regardless of numeric feature names. **The span statistic is hardcoded by a developer**; the learned portion is the empirical relationship from range to observed progress/damage. It is not a learned universal physical ontology.

The synthetic source `basin` uses two readings. Compatible `lattice` and `prism` use three and four different keys. A per-seed hidden band center among 2, 4, 6 determines a *shared* positive, neutral and harmful interval based on the span. The generator provides five potentially productive, four potentially damaging and three neutral anonymous action options per episode (an intentionally balanced toy setup). `counterphase` has three different keys and **swaps progress and damage** for the same span relation.

The model does NOT learn raw text meaning, distinguish arbitrary unconnected dynamics, discover which relation is causally relevant, or understand sensor provenance. This is controlled zero-target-feedback transfer **under deliberately engineered common physics**, not independently administered novel-task generalization.

Each model test is **read-only** on disjoint `test` indices. The training feedback is acquired by a separately seeded independent random simulator actor, *one action per disposable training episode*, with every harmful actor action counted **once**. The agent itself takes **zero learning-acquisition actions**, not a claim that obtaining observations is cost-free.

## Study 1 — source transfer versus controls

[**Focused Actions 39823733322 — success**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39823733322). **36 focused and historical regression tests** passed. Both frozen three-seed cohorts (development 152003/152021/152039; additional 153001/153017/153041) completed and were inspected. Complete per-seed JSON artifacts are archived with that run.

Each number below is **successful held-out tasks of 240** (six seeds × 40 episodes). The exact same TEST episode indices are repeated for different checkpoints, so those repeated measurements are **not independent**.

| Target / learner | 0 target obs (zero-shot) | 8 | 24 | 64 |
| --- | ---: | ---: | ---: | ---: |
| Lattice — learned source relation | **240** | 240 | 240 | 240 |
| Lattice — target-only relation | 37 | 228 | 240 | 240 |
| Lattice — fixed range band 4 | 85 | 85 | 85 | 85 |
| Lattice — fixed max-span | 51 | 51 | 51 | 51 |
| Lattice — untrained random | 31 | 31 | 31 | 31 |
| Prism — learned source relation | **240** | 240 | 240 | 240 |
| Prism — target-only relation | 22 | 213 | 240 | 240 |
| Prism — fixed range band 4 | 83 | 83 | 83 | 83 |
| Prism — fixed max-span | 62 | 62 | 62 | 62 |
| Prism — untrained random | 29 | 29 | 29 | 29 |
| Counterphase — old relation | **0** | 0 | 0 | 0 |
| Counterphase — target-only relation | 31 | 214 | 240 | 240 |
| Counterphase — fixed range band 4 | 22 | 22 | 22 | 22 |
| Counterphase — fixed max-span | 108 | 108 | 108 | 108 |
| Counterphase — fixed min-span | 132 | 132 | 132 | 132 |
| Counterphase — untrained random | 29 | 29 | 29 | 29 |

The **source-frozen range learner** matched source-transfer on the compatible environments at every checkpoint and stayed at **0/240** on counterphase. `raw_schema_memory` saw different feature-key sets and had no zero-shot evidence (matching the target-only zero-evidence random-handle rule: 37/240 lattice, 22/240 prism). The privileged oracle achieved 240/240 throughout, and abstention achieved 0/240 without TEST harm.

**Strong controlled positive:** after 240 source feedback examples per seed and **no target observations**, the source-trained range relation solves all **480/480** compatible new-schema tasks, better than all listed fixed heuristics and source-frozen raw-key transfer.

**Catastrophic negative transfer:** on the deliberately contradicted target, the same learned source model caused **240 harmful TEST actions in 240 test episodes**, finishing **zero** successfully even after 64 target observations. The un-gated model cannot prioritize new conflicting evidence when a larger source corpus dominates. **Do not deploy** this unqualified prior in unknown-rule environments.

**Independent source actor cost:** 2,592 unique TRAIN actions (1,440 basin and 384 per each of three targets) caused **868 harmful** simulated outcomes, **1,056 productive** and **668 neutral**. Model TRAIN acquisition actions: zero.

## Study 2 — evidence-based selection of a target-specific model

To address the above failure, `GatedRelationMemory` keeps all source history and uses exact observed feature-key signatures (an **engineered novelty indicator**) to group target feedback. After at least **8 target observations**, it fits one candidate model on target observations **excluding the latest four** and asks whether that candidate or the source model better predicts the **four separate held-out target outcomes**. The more likely model is selected for the read-only subsequent action proposal. The source history is not deleted. The gate is not self-invented and cannot handle hidden rule switches that retain the same feature signature.

[**Focused Actions 39824486995 — success**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39824486995). **36 focused plus historical regression tests passed**, along with both newly frozen three-seed cohorts (development 162003/162021/162039; additional 163001/163017/163041). All six are now inspected. Detailed JSON artifacts retained in Actions.

| New target feedback | Compatible lattice, gate /240 | Compatible prism, gate /240 | Contradicted counterphase, gate /240 | Counterphase target-only /240 | Counterphase harmful TEST actions, gate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | **240** | **240** | 0 | 37 | **240** |
| 4 | **240** | **240** | 0 | 173 | **240** |
| 8 | **240** | **240** | **173** | **221** | **67** |
| 16 | **240** | **240** | **224** | **235** | **16** |
| 24 | **240** | **240** | **240** | **240** | **0** |
| 64 | **240** | **240** | **240** | **240** | **0** |

At all four evidenced checkpoints with enough observations, all six seeds selected the inherited source relation on compatible lattice/prism and the target-only relation on counterphase. Source-basin revisit stayed at **240/240 successes with zero harmful TEST actions**, including after 64 counterphase observations. The original frozen source model still scored **0/240** on counterphase at all checkpoints.

**Measured recovery:** the gate went from **0/240** counterphase completions with 240 harmful TEST actions at zero target feedback to **173/240** and 67 harms after 8, **224/240** and 16 harms after 16, then **240/240** and zero harms after 24 observations. This retains the compatible tasks' zero-shot scores.

**Limitations and critical negative findings:**
- The gate is *not safe before contradictory feedback*: 0/240 and 240 harmful TEST actions at zero and four target observations.
- At 8 observations, the simple target-only learner is *better* (221 vs 173): the gate uses only the first four target observations to fit its model while reserving the latest four for selection. At 16 observations, target-only still wins (235 vs 224). Thus this is not generally optimal early adaptation.
- All environments deliberately share a single feature-engineered span statistic; the reversal target was known to the **experiment designer**, though not the learner.
- Exact public feature-key signatures are a programmed novelty detector. Same-schema hidden shifts, noise, adversarial observers, non-stationary phenomena, and unknown family generation are **not resolved**.
- A SHA-256 checkpoint plus replay proves internal integrity, not source truth. Even rehashed, internally consistent fabricated feedback cannot be distinguished from honest reality. Earlier collusion evidence remains valid.
- No independent long-term goals, emotions, consciousness, authentic life-history modeling, safety, human control, new hardware/OS features or cross-project integrations follow from these scores.

**Independent actor cost, new separate study:** 2,592 unique first-action TRAIN observations (1,440 basin and 384 per target). **816 harmful, 1,120 productive and 656 neutral** simulator outcomes, counted once, separate from the first study's costs. Learner-issued TRAIN actions: zero.

## Reproduce

```bash
python -m unittest tests.test_relation_transfer tests.test_relation_conflict tests.test_variable_affordance tests.test_regime_retrieval -v
python -m benchmarks.relation_transfer_benchmark --cohort development
python -m benchmarks.relation_transfer_benchmark --cohort additional
python -m benchmarks.relation_conflict_benchmark --cohort development
python -m benchmarks.relation_conflict_benchmark --cohort additional
```

Full Linux/Windows historical validation of the final commit is a separate CI gate and must never be assumed from dedicated focused successes.

## Next scientific gates

1. **Same-signature hidden switch** and noisy or contradictory feedback, with safety-aware rejection/abstention and explicit harm accounting. Current selection's feature-signature shortcut makes it too optimistic.
2. **Relation discovery rather than hand-written range features**, with several candidate invariant statistics and independently generated unrelated task laws. Precommit selection and evaluate honest transfer against strong fixed controls. Demonstrate new-family advantage even at matched source/target budgets.
3. **Online selection sample efficiency:** protect selection evidence *without permanently discarding it from training*, evaluate 0/2/4/8-response harm and uncertainty, and compare with a pure target-only model.
4. Separate credible external verification of source data authenticity from internal predictive consistency; no fake-witness agreement should be treated as truth.

Keep the established D1–D10 roadmap, and V2A before and partially overlapping V2B; AthenZ/Synveil integration is deferred.
