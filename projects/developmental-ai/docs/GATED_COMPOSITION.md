# Conditional grammar expansion and unseen XOR-rule falsification

**23 October 2026 — optional, simulation-only Developmental AI study.** Keep PR #2 draft/unmerged, default controller unaltered, no outside actions or AthenZ/Synveil integration. Preserve all prior negative studies and D1–D10/V2A/V2B ordering.

## Precommit and scientific question

[**Protocol**](../benchmarks/gated_composition_protocol.json) committed **first**, SHA `6054581`, before policy `d8a8368`, benchmark `3ff2ef1`, tests `0b886ce` and frozen cohort scoring. Six **precommitted developer-selected seeds**, now inspected: development 252003/252021/252039, additional 253001/253017/253041. Not an independently blinded external benchmark. The existing 48 quadratic programs could express each branch's underlying arithmetic formula separately, but **could not express a conditional program using different formulas in different regions**. This study adds a generic comparison gate, and includes a deliberately unavailable bitwise XOR operator as a negative-control rule.

## Worlds, observable inputs and acquisition

All worlds use two integers `inlet=a` and `outlet=b` in 0..9 with the same public schema, anonymous action IDs and goal three productive actions before any damage; first damage ends task. Each synthetic TEST episode is secretly stratified into **five productive, four harmful, three neutral candidate actions**, an artificially favorable task mix that does not establish general safe learning.

Private physics:
- **Source and its return:** earlier original seed-band `abs(a-b)` outcome law.
- **Conditional target:** IF `a>b`, label by residue `(a*b+a+hidden_salt)%7` (progress 0/1, harm 2/3/4, else neutral); ELSE label by `(a*a+b+hidden_salt)%5` (progress 0/1, harm 2/3, else neutral).
- **XOR target:** label by residue `((a XOR b)+hidden_salt)%5` with progress 0/1, harm 2/3, neutral 4. **XOR is not a supplied operator in either grammar**. Absence of XOR syntax is not an impossibility theorem about approximating these finite 100 action pairs through other features.

Hidden phases, salts, class partitions and the expression names do not enter the learner's event record. The target rules are both **developer-authored**, not sampled from independent unknown science. Real task outcomes and TRAIN labels here are truthful and deterministic; prior noise/corruption failures remain unresolved.

External deterministic random actor records one public outcome per disposable TRAIN task, per seed: 240 source, 128 conditional, 64 source return, 128 XOR. The evaluated learner originates **zero** TRAIN actions. Six seeds means **3,360 distinct actor interventions**. TEST split uses `290000..290015` conditional, `300000..300015` return source and `310000..310015` XOR, **96 held-out episodes/checkpoint** (16 per seed). TEST episodes repeat across checkpoints and are not independent across those checkpoints; TEST scores never train models.

## GatedCompositionMemory (optional candidate)

The learner retains append-only validated public `features/progress/damage` rows and the first-192-outcome source archive, with SHA256 deterministic replay/checkpoint integrity. The hash does **not** authenticate incoming evidence.

Base hypotheses are the original frozen source span, recent span/checksum/ordered, and 48 generic quadratic programs. One **developer-supplied comparison operator** `a>b` partitions public outcomes into two branches. The learner independently selects the best of 52 existing alternatives for each arm. Thus the two-arm *finished* conditional program is **assembled from evidence** and is not presented as a named hidden-world option.

The model scores the most recent **16 public outcomes** with genuinely **prequential** log likelihood. Each scoring predictor is trained on preceding up to **64 public rows**, excluding the event whose outcome it predicts. For the conditional case, arm predictors train only on rows from their arm. Global winner is the single highest-score model over all 16 outcomes. Gated score is **the best score for each arm added together, minus a manually specified 2.0 log unit penalty**, and must have at least three scored examples on **each** arm. If the gated score beats global, choose the two-arm model; otherwise choose the global model. Decision-time models refit using recent64 rows, partitioned by arm where appropriate. Action policy uses `3*p(progress)-10*p(damage)` with stable tie breaks. **No automatic abstention**.

**Overfitting warning:** individual scoring events are excluded from their candidate predictor's training, but the model selects the **best of 52 alternatives per branch using those same scored observations**. That multiple-comparison winner's prequential score remains **optimistically selected**. The 2.0-unit penalty is hand-chosen, not statistically calibrated. This is **bounded program composition and predictive selection**, not automatic invention of comparison, causality, XOR or unbounded symbolic programming.

## Verified results and all important negatives

[**Focused GitHub Actions run 40004315180 — PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/40004315180): **24 regression tests**, both frozen cohorts, full matched baseline/harm statistics and per-seed JSON artifacts.

**Successful TEST tasks out of 96**, with every failure for the proposed learner corresponding to one harmful simulated action (zero selected-policy abstentions):

| New TRAIN feedback outcomes | Conditional | Original returns | XOR |
| ---: | ---: | ---: | ---: |
| 0 | 8 | 9 | 7 |
| 4 | 16 | 9 | 15 |
| 8 | 22 | 19 | 11 |
| 16 | 12 | **96** | 23 |
| 32 | 57 | **96** | 10 |
| 64 | **96** | **96** | 39 |
| 96 | **96** | — | 34 |
| 128 | **96** | — | 39 |

**Both positive preregistered acceptance criteria passed.** Conditional64 **96/96 successes** (global-composed **36/96**) comfortably exceeded ≥65/96 and the ≥15/96 improvement gate. The selected two-arm hypothesis at conditional64 and later was **`composed_8` for a<=b** (`(a*a+b)%5`) and **`composed_17` for a>b** (`(a*b+a)%7`) in **all six seeds**. Original-source return16 **96/96**, meeting ≥65/96.

**Failures and negative controls:**
- **Early adaptation remains harmful.** Conditional0 made **88 harmful TEST actions/96**, conditional16 **84/96**, and only at conditional32 improved to **57/96 successful with 39 harmful**. The benchmark-privileged correct conditional feature scored **93/96** already at conditional32 and **96/96** at conditional64; the learner's choice process, not unavailability of a correct compositional formula, slowed adaptation.
- **Return to old rule is severely delayed.** At return-source0 and after four outcomes, the new learner still scored **9/96**, with **87 harmful TEST actions**, despite frozen source being **96/96 immediately**. At returned-source8 new learner only **19/96 vs previous fixed-hypothesis library 96/96 and previous global-composed 83/96**. It finally recovered to **96/96 after 16** public examples. Enlarging the hypothesis space created this significant switching-cost regression.
- **XOR held-out negative control remains unresolved.** XOR32 **10/96**, XOR64 **39/96**, XOR96 **34/96**, XOR128 **39/96** successful TEST tasks, and **57 harmful TEST actions/96 at XOR128**. A benchmark-only model privately given the correct XOR feature reached **96/96 by 32** and stayed there. After additional feedback the learner keeps choosing spurious in-grammar substitutes (both global and conditional) rather than correctly identifying an unsupported representation; it has **no out-of-grammar detection, uncertainty or abstention**. Neither source nor generated quadratic/conditional models learned XOR syntax.
- Benchmarked `random` policy 11/96 on conditional, 9/96 on source return, 13/96 on XOR; always-abstain 0 harmful actions but **0/96 completed tasks and 96 failed-by-abstention tasks** each checkpoint; privileged action oracle 96/96 on all checkpoints. Early harm is not hidden by abstentions.
- Earlier fixed and global models sometimes outperform the new learner before 64 feedback examples: conditional4 global 21/96 versus new16; conditional16 fixed library 24 versus new12; return-source8 fixed library 96 versus new19.

### True externally acquired TRAIN harms — unique, never multiplied by TEST score

| TRAIN phase | Unique simulated actor actions | Harmful | Productive | Neutral |
| --- | ---: | ---: | ---: | ---: |
| Source | 1,440 | **490** | 601 | 349 |
| Conditional | 768 | **255** | 331 | 182 |
| Return source | 384 | **122** | 158 | 104 |
| XOR | 768 | **250** | 314 | 204 |
| **Total** | **3,360** | **1,117** | **1,404** | **839** |

The learner **did not collect those observations through its own actions**. Actor-acquisition harm is separate from held-out TEST harms, which reuse task indices across checkpoints.

## Implications and next D3 gate

Positive evidence: **constructing and selecting a two-arm conditional arithmetic predictor** not expressible as one of the previous global quadratic expressions can learn the manually authored piecewise world after sufficient feedback. Negative evidence: the method cannot learn a bitwise XOR rule outside its primitive vocabulary, does not recognize its own representation limits, adapts poorly at first contact, and often recovers old source knowledge more slowly than smaller-model baselines. These results are **not** general artificial intelligence, spontaneous operator invention, safe adaptive control or proof of real-world transfer.

A new precommitted experiment should test **representation adequacy/out-of-library detection and explicitly costly abstention**, and compare to a simple safe no-act baseline, before exploring larger grammars. Separately vary physics, observation authenticity and noise. Do not adjust this study's penalty/threshold based on now-inspected seeds.

### Reproduce

```bash
python -m unittest tests.test_gated_composition tests.test_composed_feature tests.test_cross_rule -v
python -m benchmarks.gated_composition_benchmark --cohort development
python -m benchmarks.gated_composition_benchmark --cohort additional
```

Full exact-final-commit Linux/Windows regression is **a separate CI gate** from the passed focused study. Preserve prior reports, roadmap ordering, draft PR #2 and project separation.
