# Multi-switch contrastive learning with corrupted public feedback

**October 22, 2026 — optional simulation-only Developmental AI experiment**  
**Do not promote to default, merge draft PR #2, or integrate AthenZ/Synveil.** Existing D1–D10 and V2A/V2B roadmap sequencing remains unchanged.

## Research motivation and precommit

The previous optional `AdaptiveHorizonMemory` combined quick last-eight learning with longer last-32 evidence. But on one of six deliberately inspected seeds it **falsely reverted to archived A knowledge while physics remained B**, reducing B64 to 150/180 and inflicting 30 harmful TEST actions. That earlier result inspired this separate, *precommitted* experiment, not a posthoc change to the same study.

[**Frozen protocol**](../benchmarks/multi_switch_protocol.json) was committed at **`94efae2`** before implementation, benchmark, tests or results. The policy was committed at `444cd66` and updated to cache its deterministic replay at `aeb3289`; the external-actor/scoring benchmark was committed at `b528429`. Six new developer-controlled, predeclared seed values were used and have now been inspected: development `202003,202021,202039`, additional `203001,203017,203041`. This is **not an independent third-party blinded evaluation**.

## Experimental environment

The simulator reuses the same hand-authored two-numeric-field `SameSchemaWorld` dynamics. Every phase has precisely the same public `inlet/outlet` keys, anonymous action frame and engineered *max-minus-min* relation. Hidden physics changes **A→B→A→B**: B reverses the progress/damage effects of A, while neutral stays neutral. The learner sees no simulator phase labels, hidden band center, true switch time, privileged oracle data or actor identities.

For each seed, an independent deterministic random actor records the public outcome of its **first action from each disposable TRAIN episode**: 240 original A outcomes, 64 reversed B1, 48 returned A, 64 reversed B2. To study incorrect feedback, an authored deterministic 10% hash draw flips **progress to damage or damage to progress only** on non-neutral TRAIN outcomes. Neutral reports remain neutral. The actor's real simulator effects are retained **only by the benchmark** for source-harm counting. The **reported, possibly incorrect** `{features,progress,damage}` records are the *only* evidence exposed to the learner.

**This is an imperfect-reported-label experiment, not stochastic physics, adversarial source-provenance verification, independent world generation or safe real-world exploration.** The fixed 10% corruption process and original deterministic action consequences are engineered. A SHA256 checkpoint verifies replay consistency, not source authenticity.

TEST episodes are held out on `test/130000..130019` (B1), `140000..140019` (return A) and `150000..150019` (B2). Each stage/checkpoint has **120 TEST episodes** (six seeds × 20 episodes), with the **same held-out episode indices deliberately reused at later checkpoints**. Do not treat different checkpoints as independent samples. Read-only TEST actions/outcomes never train the learner.

## Learner: MultiSwitchContrastMemory

The policy stores only append-only public events. From the **first 192** outcomes it learns a fixed source archive; phases beyond the initially observed 240 examples are *inferred* via public feedback, not provided.

- **Entry to recent learning:** when the archive predicts an observed outcome with likelihood strictly below **0.125** for **at least two of the latest four events**, select a trained recent model.
- **Recent timescale:** use the latest **eight** observed examples until **24 events after the inferred recent-mode switch**; then select the latest **32**. These are programmed timescales, not a fully learned timescale.
- **Reentry to archive:** require **two** of the latest four public events where archived-class probability is **at least 0.55** and **at least four times** the probability under a recent model fitted on prior observations **excluding those latest four**. For this contrast, at least eight events must have elapsed since the inferred recent switch. The comparison uses observations, not phase labels. Neutral events that both models consider unsurprising should not alone trigger an archive return.
- **Replay:** recompute inferred change indices by deterministic chronological reprocessing of all public evidence; a performance-only cached predictor is invalidated when new feedback arrives. Saved checkpoints include the public event list and SHA256, not privileged stage labels.
- **Limit:** new recent model training still overlaps the evidence that triggers **entry and horizon selection**. Only the *archive-reentry contrast* excludes the four events used for its comparison. No fully disjoint model selection or calibrated confidence is claimed.

All parameters were manually authored, so this is a controlled predictive contrast, not an independent general regime-discovery system.

## Verifications

[**Focused GitHub Actions run 39892309615 — PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39892309615): **34 unit/historical regression tests**, exact frozen development and additional cohorts, and complete per-seed JSON artifacts. The competing policies all saw matched reported TRAIN evidence and independent read-only TEST. Baselines: adaptive horizon, fast shock, prior disjoint selector, recent-eight, recent-32, frozen A, untrained random, always-abstain, privileged benchmark oracle.

### B1: first unseen reversal

**Successful read-only TEST tasks out of 120.** With no abstentions, each unsuccessful learned-policy test in the table below incurred one harmful action.

| New B1 observations | Contrastive | Old adaptive horizon | Fast shock | Prior disjoint gate | Recent-eight | Recent-32 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 3 | 3 | 0 | 3 | 0 |
| 2 | 7 | 7 | 7 | 0 | 9 | 0 |
| 4 | 13 | 13 | 13 | 0 | 16 | 0 |
| 8 | **86** | 66 | 66 | 12 | **86** | 2 |
| 12 | **70** | 64 | 64 | 28 | **70** | 12 |
| 16 | 60 | 43 | 43 | **87** | 60 | 22 |
| 24 | **119** | 57 | 60 | 77 | **119** | 96 |
| 32 | 116 | 76 | 55 | 98 | 95 | **120** |
| 48 | 82 | 62 | 48 | **103** | 79 | **120** |
| 64 | 118 | 79 | 79 | 98 | 104 | **119** |

**Improvement:** contrastive recovery is much more stable at B24, B32 and B64 versus the previously failing adaptive horizon. All six B64 seeds selected a **recent** model instead of falsely accepting the old A archive, producing **118 successes and two harmful TEST actions**, versus the previous adaptive **79 successes and 41 harms**. It maintained B8's fast-style response (86/120), outperforming the prior adaptive's 66/120.

**Failure:** the contrastive model performs **worse than recent-32 at B32, B48 and B64**. At B48 it scored **82/120**, versus 120/120 for fixed recent-32 and 103/120 for the previous disjoint gate. One B48 seed even chose the obsolete archive; two other seeds selected recent-eight rather than the more stable long context. The method therefore **does not reliably prevent false reversion**, even though it improved the B64 outcome on these new seeds.

### Return to A: same observation schema and no switch marker

| New returned-A outcomes | Contrastive successes /120 | Previous adaptive successes | Fast shock successes | Prior disjoint successes | Frozen A successes | Contrastive harmful TEST actions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | **0** | 40 | 40 | 1 | **120** | **120** |
| 2 | 44 | 88 | 92 | 44 | **120** | 76 |
| 4 | **60** | **120** | **120** | **120** | **120** | **60** |
| 8 | **80** | **120** | **120** | **120** | **120** | **40** |
| 12 | **120** | **120** | **120** | **120** | **120** | **0** |
| 24 | **120** | **120** | **120** | **120** | **120** | **0** |
| 48 | **120** | **120** | **120** | **120** | **120** | **0** |

**Critical negative:** the preregistered return-A8 acceptance gate required at least 100/120 successes, but the new model managed **80/120**. It recovered only after 12 public feedback outcomes, while the previous adaptive and fast learners recovered after four. Requiring discriminating reentry evidence reduced false reversion but caused a material **delayed true reversion**. The frozen A learner already succeeded **120/120 at return-A0**, so reacquisition at A12 is not global superiority.

### B2: second unannounced reversal after re-learning A

| New B2 observations | Contrastive successes /120 | Previous adaptive | Fast shock | Prior disjoint | Recent-eight | Recent-32 | Contrastive harmful TEST actions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | **120** |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 | **120** |
| 4 | 2 | 2 | 2 | 0 | 3 | 0 | **118** |
| 8 | **68** | 45 | 45 | 4 | **70** | 0 | **52** |
| 12 | 64 | 46 | 46 | 32 | **84** | 3 | 56 |
| 16 | 53 | 71 | 71 | **92** | 71 | 20 | 67 |
| 24 | 76 | 3 | 3 | **85** | 74 | 72 | 44 |
| 32 | **109** | 72 | 72 | 65 | 92 | **115** | 11 |
| 64 | **116** | 78 | 78 | 72 | 114 | **116** | **4** |

**Outcome:** At B2-32 and B2-64, the contrastive learner is markedly better than prior adaptive on matched evidence, and matched fixed recent-32 at B2-64. But it lags the disjoint gate at B2-16 and B2-24, and still causes **120 harmful TEST actions out of 120 at B2 onset**, as the simulator supplies no advance warning.

## Data-acquisition harms and report corruption

**2,496 unique external random-actor TRAIN actions** across six frozen seeds, each counted only once, regardless of the number of checkpoints, policies or repeated TEST tasks:

| Stage | Actual actor actions | Actual harmful | Actual productive | Actual neutral | Flipped reported labels |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 1,440 | **495** | 573 | 372 | **101** |
| B1 | 384 | **141** | 134 | 109 | **31** |
| Return A | 288 | **92** | 106 | 90 | **20** |
| B2 | 384 | **148** | 139 | 97 | **34** |
| **Total** | **2,496** | **876** | **952** | **668** | **186** |

Actual actor harmful interventions (876) are not the same as its 10%-sampled flipped reports (186). **Only reported outcomes were supplied to the evaluated learner**; true outcomes remained benchmark-private. No learner-issued actions acquired these observations. SHA256 does not verify source truth, and 186 deliberately false observations illustrate the danger of learning from unverified testimony.

## Scientific conclusions

**Supported:** the optional contrastive memory produced better B-phase persistence and prevented the previous B64 false-archive failure for the six newly tested seeds. It also retained the ability to reacquire a previously learned source behavior through an additional repetition of B after A.

**Not supported:** universal false-reversion prevention, rapid A reacquisition, robust noise rejection, accurate uncertainty quantification, safe first action after regime changes, meaningful independent new-physics transfer or authentic autonomous cognitive development. The policy missed the precommitted return-A8 target and substantially lagged a simple recent-32 baseline at B48. A deterministic authored 10% feedback-label flip is not a substitute for real stochastic or adversarial environments.

**Next research targets (new precommit/new seeds required):**
1. Evidence-efficient, non-overlapping predictive model selection and minimum regrets, with neutral/ambiguous feedback, repeated A-B-C-A-B and stochastic outcome probabilities rather than simple A/B inversion.
2. Quantify the reliability/latency tradeoff of true-rule reentry versus false archived-rule reentry using out-of-sample regret, not just hindsight task success.
3. Gate destructive simulated actions under uncertainty and separately measure failures caused by abstention. No real-world permissions.
4. Independent, grounded observation integrity rather than accepting any rehashed fabricated public record.

## Reproduce

```bash
python -m unittest tests.test_multi_switch tests.test_adaptive_horizon tests.test_fast_shock tests.test_same_schema_switch -v
python -m benchmarks.multi_switch_benchmark --cohort development
python -m benchmarks.multi_switch_benchmark --cohort additional
```

The dedicated focused CI is **PASS**. Linux/Windows historical validation on the final documentation commit must be checked separately. Preserve every earlier negative experiment report and keep PR #2 draft and unmerged; no AthenZ/Synveil integration, default promotion or roadmap reordering.
