# Early same-schema surprise response — 2026-10-22

**Status:** Optional headless experiment only. No controller promotion, PR merge, AthenZ/Synveil integration, real-world actuation or autonomy granted.

## Question, freeze and source boundaries

The previous `SameSchemaSwitchMemory` used a **12-event candidate fit and 4 separate scoring events** to select an old learned outcome model or a newer one. This often took 12–16 new outcomes to recover, badly trailing an unconditional recent-eight baseline during the first eight observations of a hidden A→reversed B shift.

The new hypothesis was frozen in [`fast_shock_protocol.json`](../benchmarks/fast_shock_protocol.json) at Git commit `3f327f4`, **before** implementation, tests or outcome inspection. Source model implementation commit `44a4dde`, benchmark `3b1b9b3`, tests `4490dd2`. Both developer-controlled seed cohorts are now **inspected**: development 182003/182021/182039 and additional 183001/183017/183041.

We reused the same manually authored `SameSchemaWorld` simulator, including precisely identical public action/feature frames and anonymous handles during original A, reversed B, and return A. No hidden regime or phase name, ground-truth rule, new key, time of switch or causal graph is given to the learning policy. The fixed numeric `max(features)-min(features)` statistic remains engineered, not independently discovered.

Training stream per seed: **240 A original first-action outcomes**, **64 reversed-B**, then **48 returned-A**; every action is performed by an **independent seeded random one-action simulator actor**, not by the evaluated learner. The outcome memory stores only `features,progress,damage` and is strictly replay-validated. The learning system has no action to collect its own training samples. The actor's harmful simulated interventions are not discarded from accounting.

## New optional learner — FastShockMemory

- Fixed long-term anchor: first **192** validated public outcome events.
- Predict the outcome class of each of the latest eight events under that anchor, with Laplace-smoothed `RelationOutcomeMemory` probabilities.
- Define a contradiction as an outcome having predicted probability **below 0.125** under the anchor. Select a `RelationOutcomeMemory` trained on the **latest eight events** if there are at least **two contradictions in the latest four** or exactly **one in the latest four and at least three in the latest eight**. Otherwise select the anchor.
- Predict the next held-out test episode's action using the selected model. Retain every source and new event in a replayable hash-checked checkpoint, without changing the project's default agent.
- There is **no automatic abstention** in this candidate. It will make confidently harmful decisions when past evidence is wrong.

**Critical optimistic-fitting warning:** The eight events used to fit the recent candidate **also participate in triggering** its selection. This is *not* honest held-out model selection. Its rapid early adaptation might overfit noisy, adversarial or nonstationary data. The previous `SameSchemaSwitchMemory` with disjoint model-selection evidence and the exact recent-eight baseline were therefore required as controls. Do **not** claim general calibrated confidence, robust uncertainty or reliable safe switching from these results.

## Tests, scores and harms

[**Focused GitHub Actions run 39852314056 — success**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39852314056): **35 focused and related tests passed**, both frozen three-seed cohorts executed, full JSON output artifacts stored for each.

Each checkpoint is **180 held-out episodes** (six seeds × 30 distinct TEST episodes), with independent test index namespaces B: `test/80000..80029`, return-A: `test/90000..90029`. Test episodes are intentionally **repeated across checkpoints**, hence cross-checkpoint task counts are not independent. Test evaluation never updates any trained model.

### A→B: successful tasks out of 180

| New B TRAIN outcomes | Fast shock | Previous disjoint gate | Recent eight | Recent 32 | Frozen A | Fast harmful TEST actions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | 0 | **180** |
| 2 | 27 | 0 | 27 | 0 | 0 | **153** |
| 4 | 40 | 0 | 40 | 0 | 0 | **140** |
| 6 | **161** | 1 | **161** | 0 | 0 | **19** |
| 8 | **180** | 26 | **180** | 1 | 0 | **0** |
| 12 | 154 | **157** | 154 | 12 | 0 | **26** |
| 16 | 146 | **180** | 146 | 52 | 0 | **34** |
| 24 | 162 | **180** | 162 | 173 | 0 | **18** |
| 32 | 136 | **180** | 136 | **180** | 0 | **44** |
| 48 | 143 | **168** | 143 | **180** | 0 | **37** |
| 64 | 156 | **180** | 156 | **180** | 0 | **24** |

No fast-shock TEST abstentions at these checkpoints; its remaining B failure counts are actual harmful TEST outcomes. Privileged oracle completes all 180; untrained random scores **8/180** with **172 harmful TEST actions** at every B checkpoint. Cumulative memory scores **0/180** throughout B. Always-abstain scores zero completed tasks with zero harm, i.e. 180 task failures per checkpoint.

**Demonstrated:** Fast shock changes to the recent learned outcome rule much earlier than the conservative disjoint-evidence selector and improves sharply on B6/B8. After eight new independent public observations it solves **180/180** simulated reversal test episodes with zero harmful TEST actions on this *specific deterministic cohort*.

**Crucial limitations:** Its B scores exactly match the **simple recent-eight baseline at every tested checkpoint**, providing no demonstrated score advantage over that short-term policy while the reversed rule is active. At B16, B32, B48 and B64 it loses to the previous more conservative selector and often to recent32. This is an **early response versus long-term stability tradeoff**, not a uniformly better learner or architecture-wide success. At B0 it causes **180 harmful actions** — not safe first contact.

### B→A: successful returned-A tasks out of 180

| New A TRAIN outcomes | Fast shock | Previous disjoint gate | Recent eight | Frozen original A | Fast harmful TEST actions |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | **180** | **180** |
| 2 | 40 | **60** | 10 | **180** | **140** |
| 4 | **180** | **180** | 30 | **180** | **0** |
| 6 | **180** | **180** | 87 | **180** | **0** |
| 8 | **180** | **180** | 148 | **180** | **0** |
| 12 | **180** | **180** | 152 | **180** | **0** |
| 16 | **180** | **180** | 158 | **180** | **0** |
| 24 | **180** | **180** | 163 | **180** | **0** |
| 48 | **180** | **180** | 178 | **180** | **0** |

**Demonstrated:** The anchor can be reacquired rapidly when earlier dynamics return, reaching 180/180 success with zero harm after four fresh return-A observations. It markedly beats bare recent-eight there. **However, frozen old-model and cumulative baselines already scored 180/180 on returned A with zero return-A feedback**, so this is not overall superiority to all policies. At return-A0 fast shock still commits **180 harmful TEST actions**.

### Data collection harms — source actor, not test policy

Across six distinct seeds, **2,112 unique one-action TRAIN observations**, never multiplied by method or checkpoint:

| TRAIN stage | Observations | Harmful actions | Productive | Neutral |
| --- | ---: | ---: | ---: | ---: |
| Original A | 1,440 | 478 | 585 | 377 |
| Reversed B | 384 | 168 | 122 | 94 |
| Return A | 288 | 105 | 104 | 79 |
| **Total** | **2,112** | **751** | **811** | **550** |

The learner did not act to gather these observations, yet their generation incurred **751 simulated damaging actions**. Separate held-out TEST harm tables above measure autonomous decision quality using a restored learner. No trustworthy evidence-provenance mechanism is present.

## Reproduction and follow-up gates

```bash
python -m unittest tests.test_fast_shock tests.test_same_schema_switch tests.test_relation_conflict tests.test_relation_transfer -v
python -m benchmarks.fast_shock_benchmark --cohort development
python -m benchmarks.fast_shock_benchmark --cohort additional
```

The focused run is **not** the full final-HEAD Linux/Windows regression; that remains an independent CI condition.

**Next science gates**: Precommit a new, **separately seeded** research comparison with different *stable/unstable duration models*: choose short recency at suspected early switches but longer context after enough observations, without using simulator phase labels, test tuning, or an already-inspected target cohort. Evaluate both speed and stability with a Pareto view, plus noisy outcome labels, an actual stochastic generator, and source poisoning. Until then this experiment supports only **optional, engineered early adaptation**. It does not achieve D3 genuine independent novel-physics generalization, safe uncertain action selection, independently authenticated observation, or autonomous goals.

Keep D1–D10 sequence, V2A before partially overlapping V2B, and separate active AthenZ/Synveil work. PR #2 remains draft and unmerged.
