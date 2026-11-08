# Early-reversal learning and archive consistency — 2026-10-22

**Status:** Optional research code on draft, unmerged PR #2; no changes to the default agent. This is a **within-one-toy-simulator** continual learning result, not genuine unseen-family generalization, proof of source authenticity or real-world safe actuation.

## What changed in the learner?

The original `NumericOutcomeMemory` and `RegimeRetrievalMemory` remain unchanged. Two opt-in variants were added **in the existing numeric learning module**:

1. **`FastRegimeMemory`** chooses among complete old 64-observation chunks and a candidate fitted on the 8 events immediately **before** the last 4 feedback events. The last 4 are out-of-sample scoring evidence. The learner sees ordered numeric `features/progress/damage` observations, not regime names, phase labels, hidden dynamics or action-handle identities.
2. **`ConsistentRegimeMemory`** adds selection-only archive filtering. Each full old block is split into two halves: a learned 5-nearest-neighbor model fitted on the first 32 must predict the second 32, and vice versa. Mean held-out log likelihood below **-1.5** excludes the block *from candidate selection*, **not from the event record**. An engineered **0.75 log-likelihood-unit recency tolerance** prefers the most recent separately trained candidate when evidence is nearly tied.

Neither approach self-discovers its chunk/window sizes, predictive metric or threshold. They do **not** verify that an observer is honest; forged internally consistent outcomes remain a vulnerability.

## Frozen-before-code benchmarks

- [Early reacquisition protocol](../benchmarks/fast_reacquisition_protocol.json), committed at `c34d2f3`, with frozen random baseline added at `509ada1` before the corresponding evaluation harness. New fast learner introduced at `4f90578`; no test scoring or tuning against these seeds before protocol commit.
- [Archive consistency protocol](../benchmarks/archive_consistency_protocol.json), committed at `179029d` before consistency implementation `8fa18cf` and benchmark `de559d1`.
- Early learning 3+3 seeds: **122003, 122021, 122039, 123001, 123017, 123041**.
- Archive consistency 3+3 seeds: **132003, 132021, 132039, 133001, 133017, 133041**.
- All 12 seeds have now been **inspected**. The environment family and action-feature vocabulary were developer-authored; these are NOT independent future-generator blind claims.
- Both studies: A 160 initial training outcomes → reversed B 160 outcomes → return A 48 outcomes; independent seeded random simulator actor does exactly one initial TRAIN action per episode, while each learner receives only public outcomes. Evaluate unchanged 30 TEST episodes/seed at every named checkpoint (180 across six seeds, **repeated checkpoints share the same test episodes**, so counts are NOT independent across checkpoints).
- Tests are read-only, and each checkpoint is reconstructed from an exact SHA-256 event record to demonstrate restart/replay equivalence. Checkpoint checksums are not authentic origin verification.
- Matched baselines: frozen A memory, full-history 5NN, recent 8 5NN, recent 32 5NN, previous fixed-12 retrieval, random, abstain, privileged TEST-only oracle. Counts for abstentions are task failures.

## First prequential experiment: early fast retrieval

[Focused run 39780786198](https://github.com/magicmantheace/Developmental-AI/actions/runs/39780786198) **PASS**: historical regime tests plus new focused tests; both exact cohorts and full JSON stored in Actions artifact.

| Feedback observed after reversal | Fast B successes /180 | Recent-8 B /180 | Fixed-12 B /180 | Fast return-A /180 | Fixed-12 return-A /180 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | 0 |
| 4 | 0 | 71 | 0 | **154** | 26 |
| 8 | 71 | **179** | 0 | **180** | 54 |
| 12 | **179** | 160 | 0 | 159 | 159 |
| 24 | 174 | 172 | 0 | **180** | **180** |
| 48 | **88** | **179** | 1 | 150 | **180** |
| 160 | **180** | 175 | **180** | n/a | n/a |

**Explicit negative finding:** Fast retrieval matched or beat fixed-12 selection early but **regressed to 88/180 on B at 48 outcomes**, while recent-8 reached 179/180. A contaminated middle 64-observation chunk mixes the end of A and beginning of B (because chunks align to raw chronological positions, not actual rule changes). The recent-eight model is exceptionally competitive; fast retrieval is NOT universally better.

Independent TRAIN actor: **2,208 first-action events, 743 harmful**, 1,070 productive, 395 neutral across both three-seed cohorts. This observation-cost total belongs *only* to this first study and must not be merged/deduplicated with another separately generated cohort.

## Follow-up: cross-half consistency test on separate frozen seeds

[Focused run 39781740756](https://github.com/magicmantheace/Developmental-AI/actions/runs/39781740756) **PASS**: earlier focused memory checks, archive-consistency tests, both frozen cohorts, complete JSON artifacts.

| New observations since rule switch | Consistent B /180 | Fast B /180 | Recent-8 B /180 | Recent-32 B /180 | Consistent return-A /180 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 0 | 0 | 0 |
| 4 | 0 | 0 | 26 | 0 | **180** |
| 8 | 26 | 26 | **159** | 0 | **180** |
| 12 | 159 | 159 | **180** | 1 | **180** |
| 24 | 177 | 177 | **180** | 162 | **180** |
| 48 | **173** | 96 | 156 | **180** | **180** |
| 160 | **180** | **180** | 177 | **180** | n/a |

The internal criterion excluded the straddling archive block 2 on all six B-48 seed runs. At that checkpoint, **fast 96/180 versus consistent 173/180 (+77)**, and harmful TEST actions fell from **84 to 7**. At the same checkpoint, **recent-32 was still stronger (180/180)**. On return-A after four new observations, both consistent and earlier fast methods completed **180/180** in these seeds, so do not attribute that result exclusively to filtering.

Source actor across both new 3-seed cohorts: **2,208 independent TRAIN actions: 744 harmful, 1,105 productive and 359 neutral**, with zero learner-issued training actions. The 744 source harms are separate from TEST harms and not a claim of safe information acquisition.

## What has NOT been proven

- No genuine transfer to unseen task **families**, objectives, independent transition generators or observation vocabularies. A and B are reversals of the same engineered rule.
- No self-discovered prerequsites, causal theory, lifelong autonomous learner or novel independent goals.
- Failures at B-4/B-8 remain serious: the new filter completed **0/180** and **26/180** respectively while recent-8 completed **26/180** and **159/180**. This is a major efficiency gap, not solved.
- The new filter cannot guarantee it will distinguish a coherent poisoned archive from trustworthy outcomes. The earlier paired-witness collusion failure remains unresolved.
- Each method repeatedly re-evaluates the **same held-out TEST indices at different adaptation counts**. Test tasks are unseen by learners, but are not statistically independent checkpoints; selection parameters are fixed prior to their use and seeds are now inspected.
- Repeatedly collected independent observations are not risk-free. Simulated actor harmful counts remain a material cost even when the learner triggers no training interventions.
- This work is opt-in and unmerged. It is partial D4/D6 scientific evidence, **not** D3 completion, no default promotion and no AthenZ/Synveil integration.

## Reproduction

```bash
python -m unittest tests.test_regime_retrieval tests.test_fast_reacquisition tests.test_archive_consistency -v
python -m benchmarks.fast_reacquisition_benchmark --cohort development
python -m benchmarks.fast_reacquisition_benchmark --cohort additional
python -m benchmarks.archive_consistency_benchmark --cohort development
python -m benchmarks.archive_consistency_benchmark --cohort additional
```

Full Linux/Windows historical validation on the **exact final commit** remains a separate CI requirement.

## Next three highest-value research gates

1. A truly **unfamiliar family** with separately written transition laws, observation vocabularies and goals, frozen first, strong matched random/recent/replay baselines; no renaming-only transfer.
2. A mechanism for *prequential*, non-destructive **change-point inference** and sample-efficient updating that does not lose to recent-eight at B-4/B-8, with all harmful training actions counted.
3. A/B/C/A/B sequential recovery, noise, restart, and coherent forged-record source attacks, using newly frozen cohorts. Do not score corrupted-model task abstention as success.
