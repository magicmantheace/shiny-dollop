# Same-feature-schema latent reversal and recovery — 2026-10-22

**Status:** Optional, simulation-only continual-learning research; draft PR #2 stays unmerged. No default learner promotion, model authority to acquire training outcomes, or AthenZ/Synveil integration.

## Scientific motivation

Earlier `GatedRelationMemory` detected new conditions by comparing **different observed feature-key sets**, an engineered novelty shortcut. This experiment removes that shortcut: **the exact same** `inlet/outlet` observation keys and public action-frame structure persist through A → B → A, while hidden action outcome mechanics invert and later revert. Learning can only react to the chronological public `features/progress/damage` feedback; there are no phase names, domain labels, oracle physics, true change points, stable handles, or privileged hidden band values in learner memories.

The protocol was [precommitted](../benchmarks/same_schema_switch_protocol.json) at Git commit `96c0ae1` **before** learner implementation `68f5400`, benchmark `416ea52`, and test results. Six developer-controlled seed IDs were frozen before evaluation: development 172003/172021/172039 and additional 173001/173017/173041. **All are now inspected**, not third-party blind test cohorts.

Two identical-schema causal regimes are **hand-authored variants of one range-rule toy world**: A uses the original per-seed hidden band mapping; B swaps progress and damage, then A returns. A wrapper alters the simulator's step physics, but the public frame's keys, action handles and initial values are unchanged. The original action sampler produces five productive candidates in A, four in B, three neutral in both; this remains an engineered, artificially balanced test. A damaging action terminates the task. A source label or true phase is available only to the generator and reporting code, not the learner.

The independent random training actor supplies *one public first-action outcome* from each disposable simulator training episode. Collection incurs actual simulated damaging actions and is accounted separately. The learner never initiates training interventions. Training spans **240 A outcomes, 64 inverted B outcomes, then 48 returned-A outcomes**, retained in one append-only, replay-validated record. Test tasks use different indices and are read-only.

## New optional learner

`SameSchemaSwitchMemory` learns by replaying ordered public numeric outcomes and comparing two predictive candidates:

1. **Anchor:** one learned range/outcome model from the first **192** A examples.
2. **Recent:** a model fitted on the last **12** observations **before** four separate scoring observations. The four feedback events used for predictive comparison are never part of either candidate's training slice.
3. Select the candidate with the better held-out class log likelihood (0.25 Laplace smoothing inherited from the existing relation learner), breaking exact ties in favor of the anchor.
4. Abstain if the selected candidate's **mean** held-out log likelihood is below **-1.5**. Abstention is a failed task, not proof of successful harm avoidance.

The anchor's length, recency window, four-event evidence gate, and threshold are **hand-engineered**. The anchor is frozen by chronological index; it is not a self-discovered change point. The learner does not learn raw observations, discover new semantics or prove that a data source is trustworthy. The old `GatedRelationMemory` is included as a negative control; with identical observed schema keys its source-vs-target rule collapses to cumulative memory.

Checkpoints are SHA256-hashed, replayed from original ordered public events, and verified unchanged after TEST scoring. SHA256 is an **integrity check, not attested evidence authenticity**.

## Evaluation and controls

[**Focused CI: 39849488743 — PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39849488743): 36 dedicated and historical tests passed, plus both exact frozen three-seed benchmark cohorts. Complete per-seed JSON outputs are retained as Actions artifacts.

Each checkpoint has **180 TEST episodes** (six seeds × 30 distinct TEST indices). **Identical test indices are intentionally repeated across checkpoints**, so cross-checkpoint samples are not independent. B uses `test/60000..60029`; return-A uses `test/70000..70029`. Stages and checkpoints were precommitted. Nine controls were compared: adaptive selector, frozen anchor, cumulative range, recent eight, recent 32, historical key-gated learner, random, always-abstain and benchmark-private privileged oracle. No policy sees evaluation feedback.

### A to B switch: successful TEST episodes / 180

| New B outcomes | Adaptive | Frozen A | Cumulative | Recent-8 | Recent-32 | Adaptive harmful TEST actions | Adaptive abstentions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | 0 | **180** | 0 |
| 4 | 0 | 0 | 0 | 25 | 0 | **150** | 30 |
| 8 | 0 | 0 | 0 | **167** | 2 | **150** | 30 |
| 12 | 93 | 0 | 0 | **150** | 8 | **87** | 0 |
| 16 | **170** | 0 | 0 | 163 | 44 | **10** | 0 |
| 24 | **169** | 0 | 0 | 157 | 141 | **11** | 0 |
| 48 | **180** | 0 | 0 | 153 | **180** | **0** | 0 |
| 64 | 178 | 0 | 0 | 97 | **180** | **2** | 0 |

Every B checkpoint's privileged oracle reached 180/180; random achieved **9/180** with 171 harmful TEST actions throughout, and always-abstain achieved zero successes with zero harmful test actions and **180 failed-by-abstention tasks**.

**Positive:** unlike the cumulative or old key-gate learners, the optional selector eventually learned that the same feature names represented reversed outcomes. It reached 170/180 at B16 and 180/180 at B48, while preserving old examples.

**Severe limitations:**
- At B0 it confidently performed an old learned skill and incurred **180 harmful test actions / 180**. The confidence threshold is NOT a first-contact safety mechanism.
- At B4 and B8, **0** tasks succeeded; 150 resulted in harm and 30 abstained. The **simple recent-eight learner was substantially faster** (167/180 at B8), showing the selector sacrifices early adaptation by holding out evidence and considering mixed A/B recent windows.
- At B64, adaptive unexpectedly regressed to 178/180 vs **180/180 for recent-32**. Do not cherry-pick the B48 plateau.

### B back to A: successful TEST episodes / 180

| New return-A outcomes | Adaptive | Frozen A | Cumulative | Recent-8 | Recent-32 | Adaptive harmful TEST actions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | **180** | **180** | 1 | 0 | **180** |
| 4 | **180** | **180** | **180** | 60 | 0 | **0** |
| 8 | **180** | **180** | **180** | 172 | 0 | **0** |
| 12 | **180** | **180** | **180** | **180** | 1 | **0** |
| 16 | **180** | **180** | **180** | 176 | 38 | **0** |
| 24 | **180** | **180** | **180** | 161 | 168 | **0** |
| 48 | **180** | **180** | **180** | 163 | **180** | **0** |

The adaptive selector switched back to the old archive after four return-A feedback events, reaching 180/180. **However, frozen A and cumulative memory already scored 180/180 at return-A zero**, so this is a successful recovery relative to recent-window B state, not proof of superiority to all controls. At the exact switch with no feedback the adaptive model suffered **180 harmful test actions**.

### Training actor cost: distinct from read-only TEST harm

Six seeds contributed **2,112 first-action TRAIN observations**, exactly counted once across checkpoint re-evaluations and methods:

| TRAIN stage | Observed actions | Harmful | Productive | Neutral |
| --- | ---: | ---: | ---: | ---: |
| A | 1,440 | 459 | 611 | 370 |
| B | 384 | 157 | 120 | 107 |
| Return A | 288 | 85 | 129 | 74 |
| **Total** | **2,112** | **701** | **860** | **551** |

None were initiated by the evaluated learner. Nevertheless **701 simulated harmful interventions** were needed by the external actor. A score that omits acquisition costs would exaggerate practical learning safety.

## Scientific conclusion and next gates

Evidence supports **bounded same-observation-schema rule-change detection and later recovery** using a public-outcome history and predictor competition. It does **not** support fast or safe adaptation upon an unexpected switch, general causal discovery, success on independently designed unseen physics, source provenance verification, autonomous goal development, human similarity or consciousness. D3 remains **open**; this is partial D4/D6 exploration only.

Next falsifiable studies should precommit:

1. **Earlier safe change detection** with a short-term, immediately updating policy baseline; compare success versus explicit test harms and abstentions at 0/2/4/8/12 observations. No permission to perform risky real-world interventions.
2. **Stochastic/noisy outcomes, drifting thresholds and A→B→C→A→B**, ensuring ambiguous evidence does not cause rapid catastrophic oscillation or forgetting.
3. **Corrupted observation-source adversaries and external evidence validation**; internal predictive agreement cannot attest truth. The prior colluding-witness failure remains unresolved.
4. **Independently authored new dynamics** instead of another inversion of an engineered range rule. No new zero-shot generalization claim until source knowledge provides value against target-only at matched feedback budgets.

### Reproduction

```bash
python -m unittest tests.test_same_schema_switch tests.test_relation_conflict tests.test_relation_transfer tests.test_variable_affordance -v
python -m benchmarks.same_schema_switch_benchmark --cohort development
python -m benchmarks.same_schema_switch_benchmark --cohort additional
```

The exact final commit's *full Linux and Windows historical regression* is a separate validation gate; do not claim it passes based solely on these focused results. Keep PR #2 draft and unmerged; preserve D1–D10 and V2A before and overlapping V2B, and do not integrate AthenZ or Synveil.
