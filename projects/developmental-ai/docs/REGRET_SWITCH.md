# Prequential-regret switching on repeated stochastic A→B→A→B rules

**23 October 2026. Experimental only.** No controller promotion, real-world actuators, merge, AthenZ/Synveil integration or changes to D1–D10 and V2A/V2B sequencing.

## Pre-registration and research question

The previous [stochastic prequential ensemble](STOCHASTIC_PREQUENTIAL.md) made genuine prediction-before-update measurements, but soft mixture weights gave the inherited source too much influence early: B1-8 **10/96**, B2-8 **15/96**, both significantly behind a recent-eight baseline. This prompted **a distinct, frozen hard-selection study**, not a retuning of that already inspected experiment.

[**Frozen protocol**](../benchmarks/regret_switch_protocol.json), commit `2e19161`, was committed before learner `e063248`, benchmark `42af350`, regression tests `0b5f325`, and benchmark results. Seed cohorts fixed in advance: development `222003,222021,222039`; additional `223001,223017,223041`. Both are now inspected developer-selected seed cohorts, **not independent blinded tests**.

We reuse the same synthetic `StochasticWorld` rather than independently authored physics. Public sensor keys remain `inlet/outlet` throughout; underlying handcrafted range-rule A→inverted B1→returned A→inverted B2, no phase labels to the learner. Each non-neutral **real simulated action outcome** has hash-seeded probability 1/8 of inverting progress/damage. Separately, each externally collected non-neutral TRAIN outcome report has 1/20 sampled chance of a false progress/damage label. Neutral stays neutral. We count real actor harm separately from corrupt reported labels. Neither hidden physics nor uncorrupted outcomes are available to the learner.

Six seeds × 16 TEST episodes = **96 stochastic TEST tasks** per checkpoint, disjoint from TRAIN; test indices `test/200000..200015` B1, `210000..210015` return A, `220000..220015` B2. The same held-out test indices are deliberately reused across checkpoints, so results are **correlated across checkpoints**. No evaluated learner collects training data or updates from TEST.

## Optional learner: RegretSwitchMemory

The memory retains all original public numeric `{features,progress,damage}` records and rebuilds from a hash-checked deterministic checkpoint. Historical source is always the earliest **192** examples. Two additional trained predictors use latest **eight** and **32** observed records. The primitive numeric relationship `max(feature values)-min(feature values)`, Laplace-smoothing, windows, utilities and threshold values are manually authored.

For each of the **latest eight** public feedback events, it computes the log likelihood of the observed outcome under all three candidates, with the recent candidates fit **only to observations strictly earlier than the particular event**. This is genuinely prequential, out-of-sample predictive scoring of the *reported* event; it does not authenticate that report.

The hard selector follows its precommitted rules:
- If **at least two of the latest four** reports each have probability strictly less than **0.125** under the archived source, exclude the source and choose a recent model.
- Otherwise, select the source when **at least two of four** reports have source likelihood >= **0.55** and >= **twice** the short-term prequential likelihood, or when eight-event source log score exceeds the recent-eight score by **more than 1.0**.
- For a recent selection, choose recent32 only if its eight-event prequential log score exceeds recent8 by **at least 1.0** and >= **12** of the latest 32 records have source likelihood below **0.125**. Otherwise use recent8.
- Apply the existing chosen relation model's `3*p(progress)-10*p(damage)` action score. No automatic abstention: a harmful action is counted, not disguised as a safe failure.

**Limitations:** The regression thresholds and all windows are hand-designed. Although each *prequential-scoring predictor* excludes the particular scored event, the final action model trains on all currently available feedback, including selection evidence. An archive can still appear briefly credible due to stochastic reports. Checksum is not source provenance. These actions are simulation-only.

## Tests and frozen evaluation

[**Dedicated Actions run 39991366213 — PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39991366213): **33 related regression tests**, both precommitted three-seed cohorts, and full JSON results artifacts passed. All comparison methods receive exactly matched public TRAIN histories and are read-only at held-out TEST: regret selector, preceding soft prequential ensemble, earlier multi-switch contrastive learner, adaptive horizon, fast shock, simple recent8/recent32, frozen archive, random, always-abstain, and benchmark-only expected-class oracle (it does not know actual stochastic outcome).

### First B1 reversal: successes / 96 and candidate TEST harm

| New B1 observations | Regret successes | Regret harmful TEST actions | Soft ensemble successes | Recent8 | Recent32 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | **95** | 1 | 1 | 2 |
| 2 | 1 | **95** | 1 | 10 | 2 |
| 4 | 5 | **91** | 1 | 13 | 1 |
| 8 | **48** | **48** | 9 | **59** | 4 |
| 12 | 46 | 50 | 42 | 46 | 22 |
| 24 | 52 | 44 | 51 | 52 | 53 |
| 32 | 45 | **51** | **60** | 45 | **68** |
| 64 | 40 | **56** | **65** | 54 | 60 |

**Early:** B1-8 **48/96**, exceeding preregistered >=35 goal and soft ensemble's 9/96, but trailing simple recent8's 59/96. **Later:** B1-32 **45/96**, missing >=50 goal and losing to soft ensemble (60) and recent32 (68). B1-64 the selector scored **40/96**, sometimes falling back to archived A despite B still active. Harmful TEST actions were **56/96**, worse than soft ensemble (31).

### Return to A: successes / 96

| Returned-A observations | Regret | Soft ensemble | Adaptive horizon | Frozen A | Regret harmful TEST |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 22 | 1 | 45 | **60** | **74** |
| 2 | 34 | 19 | **44** | **60** | 62 |
| 4 | 35 | 31 | **60** | **60** | 61 |
| 8 | **49** | **50** | **60** | **60** | **47** |
| 12 | 60 | **63** | 60 | 60 | **36** |
| 24 | 60 | 56 | 60 | 60 | **36** |
| 48 | 60 | 59 | 60 | 60 | **36** |

**Negative:** The precommitted return-A8 target >=50/96 was **missed by one**: 49/96 with 47 harmful TEST actions. Historical adaptive recovered to 60/96 after only four observations, so regret switching is not the best return mechanism. The historical expected-class oracle scores 70/96 on these stochastic TEST episodes, illustrating finite-sample variability.

### Second B2 reversal: successes / 96

| New B2 observations | Regret | Soft ensemble | Simple recent8 | Simple recent32 | Regret harmful TEST |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | **96** |
| 2 | 9 | 0 | 13 | 1 | **87** |
| 4 | 5 | 0 | 13 | 1 | **91** |
| 8 | **33** | 9 | **41** | 1 | **63** |
| 12 | 49 | 17 | **49** | 11 | **47** |
| 24 | 36 | 24 | 36 | 32 | **60** |
| 32 | **34** | **50** | 46 | **60** | **62** |
| 64 | 40 | **63** | 51 | **67** | **56** |

**Early:** B2-8 **33/96**, improving on ensemble 9/96 but **failing** precommitted >=35 criterion and trailing recent8 41. **Late:** B2-32 **34/96**, failing >=50 and trailing ensemble 50 and recent32 60. At B2-64 only **40/96** vs recent32 67/96, with 56 actual harmful TEST actions. The regret selector falsely reselected source A for two seeds, despite the simulator still running B2. Thus hard regret selection does not solve persistent false-reversion risk.

The candidate never abstained at any checkpoint. Always-abstain has zero harms but **0/96 successes and 96 task failures** at each checkpoint. The privileged expected-class oracle chooses a beneficial action according to the *unrandomized physics* only; the actual outcome is random and this is not a strict upper bound on every finite stochastic policy run.

## Externally acquired TRAIN outcomes: true cost and incorrect labels

**2,496 unique first-action TRAIN interventions across six seeds** (never multiplied across checkpoint, policy or TEST evaluations):

| TRAIN stage | Unique actions | True harmful | True productive | True neutral | Incorrect publicly reported labels |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 1,440 | **481** | 609 | 350 | **58** |
| B1 | 384 | **156** | 131 | 97 | **15** |
| Return A | 288 | **92** | 122 | 74 | **11** |
| B2 | 384 | **152** | 132 | 100 | **14** |
| **Total** | **2,496** | **881** | **994** | **621** | **98** |

The evaluated learner initiated **zero** TRAIN interventions. The independent actor made **881 genuinely harmful** simulated interventions, while learners were supplied **98 deliberately inaccurate** reports; those values must not be confused with repeat-scored TEST harms. Internal public-record consistency is insufficient to prove reports genuine.

## Scientific interpretation

Supported: a single-source-archive versus recent-model **prequential hard choice** can substantially accelerate early response on the frozen identical-schema stochastic A/B simulator compared with the previous soft mixture (B1-8 48 vs 9; B2-8 33 vs 9).

**Not supported:** better adaptation than simple recent8 early, sustained superiority late, safe interventions, calibrated risk or detection of genuine returns. **Four registered thresholds failed**: B2-8, return-A8, B1-32 and B2-32. Two reverse-phase final checkpoints still show harmful false returns to archived A. No evidence here establishes independent transfer to novel rules or physics, broader autonomous cognition, source truth or practical safe decision-making. An early fast selector can be damaging once windows age and reported outcomes become noisy.

**Next falsifiable direction:** precommit a genuinely different hidden causal family and an error detector with bounded loss of trust in obsolete source models; compare to simple recently trained policies, and evaluate explicit abstention as a trade-off, not a win. Do **not** tune these exact thresholds against now-inspected seeds.

## Reproduction

```bash
python -m unittest tests.test_regret_switch tests.test_stochastic_prequential tests.test_multi_switch tests.test_adaptive_horizon -v
python -m benchmarks.regret_switch_benchmark --cohort development
python -m benchmarks.regret_switch_benchmark --cohort additional
```

The focused workflow passed; exact final-HEAD Linux and Windows full regression is a separate gate.
