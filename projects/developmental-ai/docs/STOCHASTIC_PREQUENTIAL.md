# Stochastic, prequentially weighted lifelong relation memory

**23 October 2026. Status: optional, simulated, unpromoted; PR #2 must remain draft and unmerged.**

## Registered question and freezing

Earlier Developmental AI research on the deliberately authored `inlet/outlet` span-rule simulator found harmful false reversion and delayed true A reacquisition. The last `MultiSwitchContrastMemory` study reported **reversed-B long-term improvements**, but in an A→B→A→B experiment with **10%-sampled corrupt reported labels** it failed to recover true A quickly and still made harmful actions before receiving new feedback. That inspected result motivated a separately frozen research test, **not threshold tuning on the same cohort**.

[**Precommitted new protocol**](../benchmarks/stochastic_prequential_protocol.json) was Git committed as `4c439ea` before implementation (`116d1b8`), benchmark (`566d9ac`), tests (`5e5305a`), CI (`07b1c3d`) or scoring. Three development seeds **212003/212021/212039** and three additional seeds **213001/213017/213041** were all predeclared and are now **inspected**; this is not an independently blinded real-world evaluation.

## Actually stochastic simulator outcomes, not merely noisy labels

This study still uses the engineered numeric range statistic and original synthetic **same public keys**. Hidden physics is A→inverted B1→returned A→inverted B2. Each non-neutral **actual** simulator action probabilistically flips its true progress/damage category at rate **1/8**, using a reproducible hash of its seed/split/episode/anonymous action/tick. Neutral remains neutral. Thus identical policy decisions can experience different realized outcomes over otherwise separate episodes; **even a scoring-only oracle that knows the preferred base category cannot guarantee 100% task success**, and can occasionally be outperformed in finite samples by chance.

Additionally, each **external random actor's** nonneutral TRAIN public report independently flips its progress/damage label at a 1/20 hash-based draw, without altering true physical outcomes. The evaluated learner receives **only the possibly inaccurate reported `{features,progress,damage}`**, not the true source-actor harm or true simulator physics. This does not authenticate observations or model independently authored physical laws.

Per seed: 240 original A first-action TRAIN outcomes, 64 B1, 48 returned A, and 64 B2. Every action was executed by an independent random simulator actor in a disposable episode; the evaluated learner initiated **zero** TRAIN actions. Unique TEST episodes are from the reserved `test/160000..160015` B1, `170000..170015` returned A and `180000..180015` B2. Each checkpoint across six seeds contains **96 TEST episodes**. Same TEST indices are purposely repeated across checkpoints and methods (correlated checkpoint outcomes), but they **never train** the learner. TEST outcomes are themselves truly pseudorandomly sampled from the simulator at action time; there is no posthoc clean-label scoring.

## PrequentialEnsembleMemory design

The new opt-in model retains all public experience and scores **three outcome learners**: an immutable first-192-event relation source, recent 8, and recent 32. Its numerical `max(features)-min(features)` predictor was hand-authored in an earlier benchmark, not autonomously learned.

To calculate candidate weights:

- For each of the **last eight observed events**, each candidate is evaluated on that event using a model fit **only on events strictly before that observation**. The source model always fits initial 192; the two recent models fit the 8 or 32 events immediately preceding the scored observation. This is an actual **prequential prediction-before-update** comparison, not an in-sample training-score comparison.
- Add natural log-likelihood of the actual **publicly reported** outcome class. The three eight-event predictive scores then receive **manually specified** log priors of **-0.4**, **0.0**, and **0.2** and softmax temperature **2.0**. No hard change points, simulator phases or hand-supplied rule labels.
- At decision time, models are fit on *all current* observed evidence in their respective windows. For each anonymous public candidate action, blend predicted probability of progress and damage using the calculated weights. Pick the action maximizing **3×progress probability minus 10×damage probability**, breaking ties by the anonymous action handle. There is **no abstention**.
- Source archive and raw reports remain in an append-only, validated and SHA256-replayed checkpoint. Model weights are derived from recorded events and can be rebuilt on restart. Hash checks validate data integrity, **not that any report is true**.

This estimator is still carefully engineered: windows, priors, span statistic, outcome utilities, known source warmup and temperature were selected by a developer. The long-term ensemble weights may continue to assign risk to obsolete knowledge even when feedback changes. A predictive likelihood scored on *corrupt public labels* remains vulnerable to fake evidence.

## Validation

[**Dedicated Actions run 39972387822 — PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39972387822) — **34 focused/prior-model regressions passed**, exact frozen development and additional three-seed cohorts completed, full report artifacts uploaded.

All comparisons see identical TRAIN reports and held-out TEST tasks. Baselines: `MultiSwitchContrastMemory`, adaptive horizon, fast shock, fixed recent-eight, fixed recent-32, frozen early archive, random, always-abstain and a **privileged expected-category oracle**. That oracle knows only the hidden *pre-randomization category*, not the realized stochastic TEST action outcome; it is a reference, **not a theoretical performance ceiling**.

### First B1 reversal: successes out of 96 / stochastic TEST harmful actions

| New B1 feedback observations | Prequential success | Prequential harm | Contrastive success | Recent-eight success | Recent-32 success | Expected-category oracle success |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | **96** | 0 | 0 | 0 | 64 |
| 2 | 0 | **96** | 0 | 1 | 1 | 64 |
| 4 | 0 | **96** | 0 | 17 | 4 | 64 |
| 8 | **10** | **86** | 21 | **47** | 5 | 64 |
| 12 | 30 | 66 | 21 | **57** | 9 | 64 |
| 24 | **40** | 56 | 12 | 34 | **56** | 64 |
| 32 | **61** | 35 | 31 | 38 | **66** | 64 |
| 64 | **52** | 44 | 27 | **61** | **52** | 64 |

The preregistered early-change objective of at least **50/96 B1 successes at eight** was **not achieved**; prequential 10/96 compared with the fixed recent-eight 47/96. At B32 it substantially improved versus previous contrastive 31/96, but lost to fixed recent32 by 5. At B64 it regressed versus recent-eight 61/96 and caused **44 harmful TEST actions**.

### Return to A: successes out of 96

| Return-A feedback observations | Prequential | Contrastive | Adaptive horizon | Frozen A | Fixed recent-eight | Prequential harmful TEST actions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 13 | 33 | 52 | **63** | 1 | **83** |
| 2 | 12 | 33 | **63** | **63** | 8 | **84** |
| 4 | 26 | **63** | 57 | **63** | 16 | **70** |
| 8 | **65** | 63 | 63 | 63 | 43 | **31** |
| 12 | 54 | **63** | **63** | **63** | 27 | **42** |
| 24 | **71** | 58 | 63 | 63 | 46 | **25** |
| 48 | 61 | **68** | 63 | 63 | 48 | **35** |

**Critical failure:** The preregistered returned-A8 goal was >=75/96 successes; actual score was **65/96**. At A4 prequential performed much worse than old contrastive 26 vs 63. At A24 it exceeded frozen A's finite-sample score of 63 by 8 but was no longer highest at A48. The prior architecture is **not consistently worse**, and the stochastic expected-category oracle scores 61/96 on these fixed TEST episodes, **not a universal accuracy ceiling**.

### Second B2 reversal: successes out of 96

| New B2 feedback observations | Prequential | Contrastive | Adaptive horizon | Fixed recent-eight | Fixed recent-32 | Prequential harmful TEST actions |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | 0 | **96** |
| 2 | 1 | 0 | 0 | 3 | 1 | **95** |
| 4 | 1 | 9 | 9 | 20 | 1 | **95** |
| 8 | 15 | 11 | 21 | **57** | 3 | **81** |
| 12 | 33 | 14 | 20 | **41** | 14 | **63** |
| 24 | 25 | 12 | 0 | **42** | 41 | **71** |
| 32 | **58** | 27 | 17 | 52 | 56 | **38** |
| 64 | **62** | 28 | 10 | 58 | **62** | **34** |

The second preregistered eight-observation change objective **>=50/96 also failed** (15/96). At B32 and B64 it improved greatly over historical contrastive model, and at B64 matched fixed recent32. But **34 harmful TEST actions /96 remain**, even after 64 B2 feedback observations. This is not safe adaptation.

Across all phase/checkpoint TEST evaluations there were **no prequential abstentions**; its failure totals here were harmful actions, not harmless skips. Always-abstain scored 0 successes, 0 simulated harmful actions, and 96 failed tasks by abstention at each checkpoint. Random TEST policy succeeded 11/96 on B1, 8/96 on return A, 14/96 on B2, each with harmful outcomes. Because stochastic action consequences are pseudorandom rather than clean, progress can occasionally occur in actions whose expected category is bad.

## Actual data-acquisition cost, separate from TEST harms

Across **six** frozen seeds and **2,496 unique external TRAIN first-action episodes**, actual simulator outcomes vs publicly **reported** flipped labels:

| Stage | Observed TRAIN actions | Real harmful actions | Real productive | Neutral | Deliberately inverted reports |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 1,440 | **492** | 593 | 355 | **57** |
| B1 | 384 | **172** | 130 | 82 | **14** |
| Return A | 288 | **89** | 128 | 71 | **4** |
| B2 | 384 | **158** | 123 | 103 | **10** |
| **Total** | **2,496** | **911** | **974** | **611** | **85** |

These 911 actual harmful simulator interventions were performed by the external actor and were counted **once per unique training episode**, not multiplied by algorithm, checkpoint or TEST scoring. The evaluated learner generated **zero** data-acquisition actions. It saw the 85 deliberately incorrect outcome reports as if they were true. This setup does not model authentic evidence validation.

## Scientific conclusion

**Supported:** a simulated truly stochastic environment and **out-of-sample prequential selection scores** can be implemented with deterministic/replayable public evidence and occasional successful improvement versus the earlier contrastive learner after enough contradictory outcomes. The new policy B1-32, return-A24, B2-32 and B2-64 scores surpass contrastive scores on the inspected seeds. State restoration/read-only scoring and actor-harm accounting pass regressions.

**Unsupported:** efficient early reversal detection, superiority to straightforward short- or long-context baselines, stable selection across all phases, safe autonomy, general transfer to new physics, source-truth verification or genuine independent cognitive development. **All three registered B1-8/B2-8/return-A8 acceptance thresholds failed.** Heavy early harm and inconsistent convergence remain barriers. Source archive, statistical span and utility weights remain handwritten; source reports can be false, and no permission for autonomous external actions is granted.

**Next falsifiable work:** Precommit a new stochastic world with a changed causal structure beyond numeric range and a policy-selection control based on independent predictive regret. Compare against a simple recent-eight baseline, a recent32 model and pure archived source at *each* checkpoint, with real actor training harms, failed-by-abstention tasks and noise-provenance perturbations separately accounted. Do not retune softmax priors/temperature using these now-inspected seeds. Maintain draft PR #2, preserve D1–D10 and V2A/V2B, and do not integrate AthenZ or Synveil.

## Reproduction

```bash
python -m unittest tests.test_stochastic_prequential tests.test_multi_switch tests.test_adaptive_horizon tests.test_fast_shock -v
python -m benchmarks.stochastic_prequential_benchmark --cohort development
python -m benchmarks.stochastic_prequential_benchmark --cohort additional
```

The focused workflow above is green; **full Linux and Windows validation on the final documentation commit is a separate gate**.
