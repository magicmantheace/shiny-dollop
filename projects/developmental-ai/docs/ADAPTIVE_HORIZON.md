# Adaptive memory horizon study: short-term recovery versus long-term stability

**Date:** October 22, 2026. **Status:** Optional simulated research; PR #2 remains open/draft/unmerged; no default policy promotion, real-world actuation or AthenZ/Synveil integration.

## Scientific question and precommit

Previous two-policy designs exposed competing failures:

- `FastShockMemory` was fast at an unchanged-schema rule reversal but, on its own frozen cohort, later deteriorated, often losing to a fixed recent-32 learner.
- `SameSchemaSwitchMemory` used a 12+4 independent fit/validation split and was steadier later, but was much slower at initial reversal.
- Both had severely harmful actions before enough contradictory observations; neither proved safe deployment or independent novel-domain transfer.

**Precommitted study**: [`benchmarks/adaptive_horizon_protocol.json`](../benchmarks/adaptive_horizon_protocol.json) committed as `41e5df2`, before policy implementation `9c01e14`, simulation wrapper `699d231`, regression tests `11e53d7` and any target score inspection. Frozen cohorts (development: 192003, 192021, 192039; additional: 193001, 193017, 193041) were run exactly once each and are **now inspected**, not blind independent evaluator data.

The simulator deliberately reuses the deterministic developer-authored `SameSchemaWorld`: identical public `inlet/outlet` feature names and frames during A (240 observed first-action outcomes) → reversed B (64) → restored A (48). The evaluated learner sees only `features,progress,damage` events and read-only action candidates, not simulator phase labels, hidden band parameters, action semantics or change points. The learner's `max-minus-min` numeric relation representation, original archive, thresholds and windows are **engineered**, not discovered.

## Optional candidate: AdaptiveHorizonMemory

The new event-sourced model retains the entire validated history with deterministic SHA256 record and exact replay and inherits the strict same-key numeric-event validator. The earliest 192 observations form an immutable learned anchor. For each newest observed outcome, the anchor supplies its smoothed probability under the numeric span relation; an event is surprising when predicted probability is strictly **less than 0.125**.

**Archive/recency selection (registered in advance):**

- If at least **two of the latest four** observations are surprising, or exactly one of four and at least three of eight are surprising, choose recent learning; otherwise use archive.
- When choosing recent learning, if the **latest 32 observations contain at least 15 surprising outcomes**, fit `RelationOutcomeMemory` to those 32; otherwise fit to the last **eight** observations.
- No candidate abstention is allowed. An always-abstain control separately quantifies the trade-off.
- All recent feedback used to trigger selection **also enters the selected recent model's fitting sample**. This is a deliberate optimistic-selection flaw, not a disjoint predictive model-selection test. No measured probabilities should be described as calibrated confidence.

This does *not* learn latent regimes in a principled sense: it recognizes hardcoded surprise-count patterns and is particularly vulnerable to neutral feedback, noisy outcomes, drift, ambiguous contexts and evidence forgery. SHA256 protects internal record integrity, **not observation authenticity**.

## Validation

[**Focused GitHub Actions run 39890296668 — PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39890296668). The run completed **34 focused/historical regression tests**, development and additional frozen three-seed cohorts, and archived complete per-seed JSON artifacts.

All policies receive the **same public TRAIN history** at each checkpoint. An independent seeded random simulator actor takes exactly one first action in each disposable training episode, and simulated harmful interventions are counted once, **separate from read-only TEST outcomes**. The learner initiates **zero** training interventions. Every checkpoint scores **180 TEST episodes** (6 seeds × 30 episode indices), with a different namespace for B (`test/110000..110029`) and returned A (`test/120000..120029`). Checkpoints intentionally **reuse TEST indices** and their results are correlated, not independent evidence.

### Reversed B rule — successes and harmful TEST actions / 180

| B observations | Adaptive successes | Adaptive harmful | Fast-shock successes | Disjoint-selector successes | Recent-eight successes | Recent-32 successes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | **180** | 0 | 0 | 0 | 0 |
| 2 | 2 | **178** | 2 | 0 | 2 | 0 |
| 4 | 45 | **135** | 45 | 0 | 46 | 0 |
| 6 | 135 | **45** | 135 | 0 | 135 | 0 |
| 8 | **170** | **10** | 170 | 12 | 170 | 6 |
| 12 | 149 | 31 | 149 | 124 | 149 | 18 |
| 16 | 159 | 21 | 159 | **170** | 159 | 103 |
| 24 | **165** | 15 | 121 | 159 | 121 | **165** |
| 32 | **180** | **0** | 128 | 151 | 128 | **180** |
| 48 | **180** | **0** | 119 | **180** | 119 | **180** |
| 64 | **150** | **30** | 144 | 146 | 150 | **180** |

No candidate TEST abstentions. Frozen-A and cumulative range learners achieved **0/180** at every reversed-B checkpoint. The untrained random policy got 10/180 successes and 170 harmful TEST actions per B checkpoint; privileged oracle got 180/180, zero harms. Always-abstain got zero successes and zero harms **by failing all 180 tasks**.

**Registered outcomes and limitations:**

- B8 **170/180**, meeting the fast-equivalence acceptance criterion and strongly ahead of recent32/legacy at that point, but **matching fast shock and fixed recent-eight exactly**; no claimed gain over the fastest baseline.
- B24 **165/180** versus fast-shock **121/180**. All six seeds used the 32-observation horizon at that checkpoint, despite contamination from A examples, and matched the simple recent-32 baseline.
- B32 and B48 **180/180**, both matching simple recent-32 and beating fast shock (128 and 119 respectively), showing the intended early/late empirical combination **at those checkpoints**.
- **Important falsification at B64:** The adaptive policy regressed to **150/180 and 30 harmful TEST actions**, versus **180/180 and zero harm for fixed recent-32**. Five of six seeds selected recent32; **one seed erroneously fell back to archived A**, although the hidden rule was still B, leading to 30 failed/harmful episodes. Thus the protocol's B64 stability target **failed**. Do not silently adjust the hardcoded threshold after seeing this outcome; use a new registered cohort if correcting the failure.
- The disjoint-evidence legacy selector scored 170/180 at B16 (beating adaptive's 159/180), and 180/180 at B48 (tying adaptive). The adaptive method is **not uniformly best** and its predictive selection is not disjoint.

### Return to original A rule — successes and harms / 180

| New returned-A outcomes | Adaptive successes | Adaptive harmful TEST actions | Fast-shock successes | Legacy disjoint successes | Frozen-A successes | Simple recent-32 successes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 30 | **150** | 30 | 30 | **180** | 0 |
| 2 | 30 | **150** | 33 | **120** | **180** | 0 |
| 4 | **180** | **0** | **180** | **180** | **180** | 0 |
| 6 | **180** | **0** | **180** | **180** | **180** | 0 |
| 8 | **180** | **0** | **180** | **180** | **180** | 0 |
| 12 | **180** | **0** | **180** | **180** | **180** | 6 |
| 16 | **180** | **0** | **180** | **180** | **180** | 21 |
| 24 | **180** | **0** | **180** | **180** | **180** | 135 |
| 48 | **180** | **0** | **180** | **180** | **180** | **180** |

Recovery to 180/180 occurred after four feedback observations. However the original frozen memory was already **180/180 at return-A zero**; archive reacquisition is only a win over models that had learned B and did not realize A returned. The adaptive policy suffered **150 harmful TEST actions** at return-A0 and after two new feedback observations, **worse than the legacy disjoint selector's 60 harms after two**. This is **not** safe immediate reversion detection.

### Independent actor data acquisition cost

Exactly **2,112 unique simulated TRAIN interventions across six seeds**, never multiplied by checkpoint or policy:

| Source stage | Unique observed actions | Harmful | Productive | Neutral |
| --- | ---: | ---: | ---: | ---: |
| Original A | 1,440 | **481** | 599 | 360 |
| Reversed B | 384 | **150** | 138 | 96 |
| Return A | 288 | **101** | 127 | 60 |
| **Total** | **2,112** | **732** | **864** | **516** |

The evaluated learner did not initiate any TRAIN actions, but this externally collected stream inflicted **732 simulated damaging outcomes**. Distinguish these from harmful TEST actions reported above; combining repeated checkpoint TEST counts would double-count the same held-out test episodes.

## Reproduce

```bash
python -m unittest tests.test_adaptive_horizon tests.test_fast_shock tests.test_same_schema_switch tests.test_relation_conflict -v
python -m benchmarks.adaptive_horizon_benchmark --cohort development
python -m benchmarks.adaptive_horizon_benchmark --cohort additional
```

### Research conclusion / next experiment

The evidence demonstrates that a fixed public-prediction-error threshold can **combine early short-window learning and some later long-window stability** in a toy, same-sensor A→B→A reversal. It is a genuine measured improvement over *fast shock on certain later checkpoints*, but not an improvement over the individually selected best fixed short/long learner at every checkpoint, and it **fails the precommitted B64 stability goal** due to false reversion.

To address this failure scientifically, freeze **new seeds, noisy/outcome-mixed regimes and at least A→B→C→A→B** *before* developing an alternative selector with stability/hysteresis or disjoint validation. Do not use already inspected test results for threshold tuning without admitting this is follow-up design. Simulations lack independently administered novel physics, calibrated safe exploration, authenticated source evidence and general-purpose cognition. D3 gate remains open. D1–D10 and V2A/V2B sequencing preserved. Full final-commit Linux/Windows historical validation remains a separate required status check.
