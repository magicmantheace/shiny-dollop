# D3: Navigation-trained temporal model on delayed-choice recall

**Status:** experimental, simulation-only. This is a deliberately adverse **cross-task-family test**, **not** completion of D1/D3, independent blindness, a general temporal understanding module or a deployment decision.

## Precommitted method

The evaluation protocol was added to GitHub in commit `028b859668ada03b1cef43240a74b1d13556f043` **before** the new evaluation results. Its development cohort is seeds 43103/50021/61031, and its previously inspected additional cohort is 72019/83003/94009. There are 40 separate `test/99900..99939` delayed-choice trials per seed. The algorithm was not changed between cohorts or adjusted on test outcomes.

The existing *navigation*-family unsupervised token permutation is fitted from public `train/89400..89639` sensor and forecast streams only. Thirty separate navigation `train/90500..90529` stream pairs, pseudo-selected by the pre-existing fixed-eight marginal aligner, fit the existing `VariableCorrespondence` emission and overlap parameters. This **same checkpoint** is restored into a strict read-only `CrossFamilyTemporal` adapter for every delayed-choice trial. It sees no delayed-family reward, first cue, underlying event indices, true cipher or correct candidate at training/inference time. Test observations never update the model.

The benchmark constructs a synthetic **side channel** from the original delayed-choice simulator's *public initial cue*. The generator sees that cue to produce one noisy sensor history and five candidate forecast histories, only one tagged with the correct cue label. Four underlying eight-symbol templates have identical token histograms but different temporal orders. The sensor channel independently deletes 0–3 and inserts 3–4 tokens, the forecast channel independently deletes 0–2 and inserts 2–4. These insertions and deletions are unlabelled to the agent. Candidates explicitly advertise a proposed discrete cue `[0..3, 0]`, and a separately trained cue-to-button association learned from delayed-family train rewards translates the selected cue into an action. The same frozen response policy is shared by **every** baseline. This is an engineered extra observation task, **not** native sensory transfer from the delayed environment.

Cue-to-button learning uses the existing `cross_task_retention.fit_gate` on delayed `train/0..299` and disjoint validation `train/5000..5059`. No test episode trains either the temporal model or response model. On these six seeds that response learner answers all 240 trials correctly when given the true cue; hence navigation/task success equals cue recovery in these runs. The benchmark scores candidate identity and underlying event overlap with generator truth **only after selection**. Source-name assignment changes by episode.

## Results (40 episodes per seed)

| Seed | Bag frequency | Previous fixed-eight marginal | Previous max-path | **Navigation-trained variable** | Last-token rule | True cue |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 43103 | 9 | 23 | 21 | **21** | 26 | 40 |
| 50021 | 8 | 19 | 20 | **24** | 27 | 40 |
| 61031 | 10 | 14 | 16 | **18** | 18 | 40 |
| 72019 | 6 | 19 | 14 | **15** | 27 | 40 |
| 83003 | 10 | 19 | 21 | **19** | 27 | 40 |
| 94009 | 9 | 18 | 18 | **18** | 28 | 40 |
| **Total / 240** | **52** | **112** | **110** | **115 (47.9%)** | **153 (63.8%)** | **240** |

The navigation-trained model beats the fixed-eight marginal baseline on **three seeds**, ties on **one**, and loses on **two**. It improves aggregate success by only **3/240**. It loses to the simple **last observed token** template-specific heuristic by **38/240**. The hidden-permutation oracle matches the learned model exactly (**115/240**) because the navigation-learned cipher was already exact for every seed. This further isolates the deficit to alignment/evidence ambiguity, not token mapping. The last-token heuristic exploits developer-known template order; it is a strong but task-specific control, not universally valid.

### Event-count negative control

For the correctly generated source (generator-only scoring), mean absolute error in estimated common events across all six equally sized cohorts:

| Count estimate | Mean absolute error |
| --- | ---: |
| Learned variable model posterior | 0.9303 |
| Always six events | 1.0292 |
| Simple `(observed length + forecast length)/2 - 4` | **0.6312** |

As in the source task, the public-length heuristic beats the learned exact count estimate. **There is no validated improvement in event-count recognition or robust temporal transfer.** The artificial common vocabulary, cue labels, templates, eight-event generative assumption, and monotone order remain manually defined.

## Boundary, reproducibility, and next work

`CrossFamilyTemporal` enforces bounded observations and cue proposals and checkpoints a copy of the navigation-trained model. The model checkpoint rejects mismatched parameter claims by recomputing fit from saved public pairs; its SHA-256 integrity hash is not authentication, owner authorization, or evidence of private identity provenance.

```sh
python -m unittest tests.test_cross_family_temporal tests.test_variable_correspondence tests.test_temporal_correspondence tests.test_unaligned_stream tests.test_environment_api tests.test_delayed_choice tests.test_cross_task_retention -q
python -m benchmarks.cross_family_temporal_benchmark --cohort development --out benchmarks/cross_family_temporal_results.json
python -m benchmarks.cross_family_temporal_benchmark --cohort additional --out benchmarks/cross_family_temporal_additional_results.json
python -m benchmarks.transfer_benchmark
```

**55 targeted and related tests passed** on the reconstructed local checkout. The original, unchanged three-seed transfer benchmark remained **76.0%, 69.0%, 66.67%**. The full GitHub repository suite, CI, device tests, production AthenZ service, and Synveil integration were **not verified**.

**Next:** reject reliance on fixed templates by evaluating learned, variable-duration event segmentation with distractors across independently specified task generators, with a stronger simple recency, length and predictive-baseline family. The D1 independent holdout and D3 out-of-family adaptive skill-transfer criteria are still unmet. Keep V2A affective cognition ahead of and overlapping V2B virtual-home development; neither is implemented here.
