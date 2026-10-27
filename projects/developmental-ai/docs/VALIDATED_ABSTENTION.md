# Held-out predictive adequacy and selective abstention

**23 October 2026 — optional simulated research only.** PR #2 remains draft and unmerged; no default learner promotion or AthenZ/Synveil integration.

## Freeze and purpose

[Precommitted protocol](../benchmarks/validated_abstention_protocol.json), frozen at `61cb13c` and clarified at `198c45b` **before implementation and result inspection**. This study tests whether disjoint predictive validation and an action risk filter can reduce damaging choices when the current arithmetic grammar lacks XOR.

Fresh frozen seeds: development 262003/262021/262039; additional 263001/263017/263041. Both cohorts are now inspected, not independently blinded.

The simulator reuses the authored source→conditional→source→XOR dynamics with unchanged public `inlet/outlet` keys. Its actions are artificially stratified five productive/four damaging/three neutral. Outcomes and public reports are deterministic/truthful here, so noise and provenance failures from earlier studies remain unaddressed. Separate random simulator actors collect unique first-action TRAIN outcomes; the evaluated learner initiates **zero** data acquisition actions. Each checkpoint is six seeds × 16 held-out TEST tasks = **96**, with intentionally reused TEST indices across checkpoints (correlated scores).

## Optional learner

`ValidatedAbstainingMemory` first selects a frozen global or two-arm arithmetic candidate with `GatedCompositionMemory`, **excluding the latest 16 public observations**. If the remaining prefix has fewer than 240 examples, select frozen original source memory. Next, for each of the latest 16 public outcomes, evaluate the selected hypothesis using a predictor trained only on the **preceding 64** observations. Compare its observed-class log likelihood against an unconditional three-class frequency null trained on those same preceding events.

Accept the hypothesis only when average predictive log-likelihood gain is at least **0.20 nats/event** and at least **10/16** top predicted outcome classes are correct. When accepted, act only if a candidate action's predicted `P(progress)>=0.55` and `P(damage)<=0.18`; otherwise abstain. All four numeric cutoffs and available operators are **developer-chosen and not calibrated**. Per-event validation outcomes are excluded from both the model-choice sample and their individual predictors' fitting sets; model selection *within* its earlier dataset still searches many handcrafted candidates. Checkpoint stores only append-only schema-validated public feedback, with SHA256 exact replay (not source authentication).

The policy never obtains new learning evidence by refusing to act; every abstention is counted as **task failure**, even if it prevents simulated harm.

## Verification and all key negative outcomes

[Focused GitHub Actions 40043938342 — PASS](https://github.com/magicmantheace/Developmental-AI/actions/runs/40043938342): **24 tests, both frozen three-seed cohorts** and complete per-seed JSON artifacts.

**Proposed policy TEST results:** each entry is **successful tasks / damaging actions / abstained tasks**, out of 96 at each checkpoint.

| New feedback | Conditional | Source returns | XOR |
|---:|:---:|:---:|:---:|
| 0 | 2 / 74 / 20 | 1 / 87 / 8 | 5 / 67 / 24 |
| 8 | 0 / 0 / 96 | 0 / 14 / 82 | 0 / 0 / 96 |
| 16 | 0 / 0 / 96 | 0 / 0 / 96 | 0 / 0 / 96 |
| 24 | 0 / 0 / 96 | 16 / 0 / 80 | 0 / 0 / 96 |
| 32 | 0 / 0 / 96 | **96 / 0 / 0** | 0 / 0 / 96 |
| 48 | 14 / 4 / 78 | **96 / 0 / 0** | 0 / 0 / 96 |
| 64 | **93 / 1 / 2** | **96 / 0 / 0** | 2 / 6 / 88 |
| 96 | **96 / 0 / 0** | — | **0 / 0 / 96** |
| 128 | **96 / 0 / 0** | — | 7 / 0 / 89 |

All three **precommitted acceptance gates passed**: XOR96 damaged TEST actions ≤35 and abstentions ≥40, conditional96 ≥60 successes, and returned-source32 ≥60 successes. Importantly, XOR96's zero damage also meant **zero successful tasks and 96 abstentions**. This is selective risk avoidance, **not learning the XOR operator**. At XOR128 the policy completed only 7/96 tasks, versus 96/96 for a private correct-XOR control. At XOR64 one seed incorrectly accepted a model and incurred **six damaging TEST actions**.

**Critical weaknesses:** at first contact, conditional0 caused **74** damaging test actions and XOR0 caused **67** because validation still favored old knowledge. At conditional48 the gated always-act learner completed **94/96** tasks; the selective learner completed **14/96**, abstaining on 78 tasks. On original source return at eight feedback observations it completed **zero**, abstained on **82** and caused **14** damaging actions, while the frozen source control already solved **96/96**. At return-source16 it abstained from **all 96** tasks even though the ordinary gated learner solved all 96. Thus reduced harm entails real delayed-adaptation and coverage penalties. Always-abstain control solves zero tasks and causes zero harm by definition; it is not a successful learning baseline.

## Independent actor costs, separate from repeated TEST

| TRAIN stage | Unique actions | Harmful | Productive | Neutral |
|---|---:|---:|---:|---:|
| Source | 1,440 | 462 | 622 | 356 |
| Conditional | 768 | 242 | 331 | 195 |
| Source returns | 384 | 133 | 165 | 86 |
| XOR | 768 | 247 | 315 | 206 |
| **Total** | **3,360** | **1,084** | **1,433** | **843** |

The learner initiated zero TRAIN actions. TEST metrics reuse tasks across checkpoints and cannot be summed as independent events.

## Meaning and next gate

The study supports **held-out model adequacy testing plus explicit action abstention** in authored sandbox worlds, not calibrated real-world safety, operator invention, authentic evidence validation, autonomous data acquisition, or rapid recognition of changed physics. Inadequate representations can still pass by chance, and previously adequate models remain overtrusted immediately after an unseen change.

Next work should preregister **risk/coverage curves**, passive independently sourced feedback during abstention, and more diverse stochastic/noisy worlds. Preserve the existing default, draft PR and D1–D10/V2A/V2B ordering.

Reproduce:

```bash
python -m unittest tests.test_validated_abstention tests.test_gated_composition tests.test_composed_feature -v
python -m benchmarks.validated_abstention_benchmark --cohort development
python -m benchmarks.validated_abstention_benchmark --cohort additional
```
