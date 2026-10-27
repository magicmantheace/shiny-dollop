# Bounded nonlinear feature composition — frozen study

**October 23, 2026. Optional Developmental AI research only.** No controller promotion, PR merge, real-world actuation or AthenZ/Synveil integration. D1–D10 and V2A/V2B roadmap priorities remain intact.

## Registered experiment and scientific distinction

The [protocol](../benchmarks/composed_feature_protocol.json) was committed **first**, at `ad83c3f`, before the feature learner `9510fce`, simulator `8a279f1`, tests `83efaec` or benchmark scores. Six developer-selected seeds were preregistered and are now inspected: development `242003,242021,242039` and additional `243001,243017,243041`. They are not independently blinded third-party evaluations.

Earlier `FeatureHypothesisMemory` learned to **select a finished arithmetic representation** from four hand-coded alternatives. The new `ComposedFeatureMemory` instead builds candidate programs generically from a fixed grammar of arithmetic **multiplication, addition, integer coefficients and modulo** over exactly two public integer inputs. The simulator privately uses two nonlinear outcome rules that the previous fixed candidate menu did not contain:

- **Product target:** `(a*b+a+hidden_seed_salt)%7`. Residues 0/1 progress; 2/3/4 damage; 5/6 neutral.
- **Square target:** `(a*a+b+hidden_seed_salt)%5`. Residues 0/1 progress; 2/3 damage; 4 neutral.

Original source/returned-source uses the previous seed-band relationship `abs(a-b)`. All phases expose exactly the same `inlet/outlet` keys and anonymous action frame; the learner sees neither physics name, private salt, source band, phase marker nor hidden action category.

**Critical research qualification:** The 48 enumerated generated quadratic programs include the exact target formulas after generic enumeration. The model does **not** have target-specific hard-coded *named* candidates, but the full grammar, its operator choices, degree, coefficient set and moduli were chosen by the developer. This is **bounded program synthesis and evidence-based selection**, not open-ended invention of new operators, unconstrained causal discovery or independent scientific creativity.

## Training, TEST and model operation

Per seed, external independent one-action random simulator actors collect **240 source**, **128 product**, **64 original-rule return** and **128 square** observed TRAIN outcomes. The evaluated learner initiates **zero training interventions**. This study uses truthful **deterministic** simulator outcomes; earlier stochastic outcome and deliberately falsified public-report weaknesses are *not* retested. Public stored records contain only `features/progress/damage`, with strict schema validation, append-only history, 1,000-event cap, SHA256 consistency and exact deterministic restart replay. SHA256 **does not authenticate external observations**.

Each invented public task is artificially assembled from **five productive, four damaging and three neutral candidate actions**. A damaging action terminates its episode. The guaranteed good-action mixture makes the benchmark unusually favorable, while serious harm remains possible under wrong knowledge.

Generated programs have the form `(cq*(x*y)+cl*z)%m`, where `x,y,z` are public inputs, `cq/cl` each 1 or 2, `m` is 5 or 7, and `x*y` is one of `a*a,a*b,b*b`. This gives **48 generated expressions**. The model also compares a frozen first-192 source span learner against recent span, checksum and ordered **fixed** baselines. Outcome probabilities are smoothed by 0.25 per class. The last **12** public outcomes are scored by a genuine **prequential** log-likelihood: every candidate scoring predictor fits the preceding up to 24 observations, **excluding its own scored event**. A fixed 0.25 log penalty is applied to each quadratic expression. Selected decision-time models use the latest 32 feedback events; source uses frozen first192. The inherited action utility is `3*P(progress)-10*P(damage)`. This candidate does not abstain.

TEST indices are `260000..260015` for product, `270000..270015` for return source, `280000..280015` for square, 16 tasks per seed × six seeds = **96 TEST tasks per checkpoint**. TEST outcomes never train the learner. TEST indices **repeat across checkpoints**, so those scores are correlated, not independent new episodes across stages.

## Verified benchmark

[**Focused GitHub Actions 39997552852: PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39997552852): **24 unit and historical tests passed**, both preregistered three-seed cohorts passed, and full JSON output artifacts uploaded.

**Composed learner TEST successes /96:**

| New active-rule TRAIN observations | Product | Original returns | Square |
| ---: | ---: | ---: | ---: |
| 0 | 13 | 11 | 12 |
| 4 | 13 | 13 | 15 |
| 8 | 41 | 40 | 19 |
| 16 | 86 | **96** | 79 |
| 32 | **96** | **96** | **96** |
| 64 | **96** | **96** | **96** |
| 96 | **96** | — | **96** |
| 128 | **96** | — | **96** |

All three **preregistered targets passed**: product64 >=60/96, square64 >=60/96 and source-return16 >=60/96. By product32 and square32 all six seeds selected the exact same generated program that is benchmark-privately used for that nonlinear target: `composed_17` representing `(a*b+a)%7` and `composed_8` representing `(a*a+b)%5`. Hidden per-seed salts are learned as per-bucket category frequencies rather than supplied.

**Honest comparisons:**

| Stage and feedback | Composed learner | Previous fixed-hypothesis library | Privileged correct nonlinear feature | Omniscient action oracle |
| --- | ---: | ---: | ---: | ---: |
| Product 0 | 13 | 13 | 37 | 96 |
| Product 8 | **41** | 11 | **75** | 96 |
| Product 16 | **86** | 32 | 85 | 96 |
| Product 32 | **96** | 39 | **96** | 96 |
| Square 0 | 12 | 12 | 40 | 96 |
| Square 8 | 19 | 17 | **66** | 96 |
| Square 16 | **79** | 25 | **79** | 96 |
| Square 32 | **96** | 31 | **96** | 96 |
| Source return 0 | 11 | 12 | *not applicable* | 96 |
| Source return 8 | 40 | **96** | *not applicable* | 96 |
| Source return 16 | **96** | **96** | *not applicable* | 96 |

The benchmark-privileged feature controls know **which quadratic expression** is correct, but must still estimate its outcome probabilities from exactly the same last-32 public feedback events. The action oracle knows simulator physics directly and is explicitly **not** a learner baseline.

### Negative evidence and critical risks

At first unseen product feedback (0) the learner made **83 harmful TEST actions /96**; at square0 **84/96**; and at returned-source0 **85/96**, despite the frozen-source baseline being **96/96 successful** in the return phase. After four target observations, product remained at 13/96 and square only 15/96. At square8 only **19/96** succeeded, versus **66/96 for the privileged correct quadratic feature**. The larger generated search space slows selection and can be fooled by coincidental correlations; at return-source8 only **40/96** succeeded versus **96/96** for the previous fixed-library learner. The source archive is recovered by all six seeds at return-source16, not immediately.

Abstaining from every action would cause zero simulated harm but **96/96 task failures** at every checkpoint; it is not a successful solution. Wrong choices here generally produce a harmful action because the first damaging action ends the episode.

### True source-actor cost, not repeated TEST harm

| TRAIN phase | Unique actor actions | Harmful | Productive | Neutral |
| --- | ---: | ---: | ---: | ---: |
| Source | 1,440 | **505** | 626 | 309 |
| Product | 768 | **264** | 309 | 195 |
| Original returns | 384 | **123** | 157 | 104 |
| Square | 768 | **224** | 339 | 205 |
| **Total** | **3,360** | **1,116** | **1,431** | **813** |

These are separate **unique first-action TRAIN episodes**, not a sum of scores from repeated TEST checkpoints or different policies. The learner initiated no TRAIN actions.

## Interpretation and next falsification

Evidence supports finite feature-program composition from basic arithmetic and learning an appropriate generated nonlinear relation **when the necessary operations and program structure are already supplied**. It is a meaningful advance over directly selecting one of four finished formulas, but **not** proof of D3 unconstrained feature discovery, safe first-contact decisions, robustness to stochastic/forged reports, or general self-improving cognition. The old fixed learner recovers source faster; the composed model takes 16 feedback examples.

A stronger next test must freeze new physics **outside the generative grammar's closure** (for example conditions requiring conditional logic or independent memory), supply decoy programs, assess out-of-grammar detection and explicit abstention costs, and audit reporter authenticity. Do not tune existing test seeds.

### Reproduce

```bash
python -m unittest tests.test_composed_feature tests.test_cross_rule tests.test_regret_switch -v
python -m benchmarks.composed_feature_benchmark --cohort development
python -m benchmarks.composed_feature_benchmark --cohort additional
```

Full final-commit Linux/Windows validation remains separate. Preserve all previous work and negative research reports, draft unmerged PR #2 and D1–D10 plus V2A/V2B ordering; no AthenZ/Synveil development here.
