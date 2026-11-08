# D3 experiment: learned event segmentation and bounded span memory

**Status: optional research; not D1/D3 completion or a production capability.** The frozen six-seed protocol was committed to `benchmarks/event_segmentation_protocol.json` before any new evaluation. The two evaluation families are **parameter variants of one synthetic generator**, not independently developed real-world tasks. All six seeds were examined during this pass and are **not blind**.

## What was learned

`developmental_ai.event_segmentation` fits a four-state, symmetric categorical hidden Markov model to **unlabelled raw observation tokens** from 160 source-generator training episodes per seed. Five scaled forward/backward EM iterations infer (1) latent event persistence and (2) sensor emission accuracy. The system does not see true event boundaries, labels, target event, or external task rewards. Its Viterbi decoder returns a latent per-tick hypothesis and inferred contiguous event spans. A bounded streaming `EventSpanMemory` holds a raw observation log and retrieves the **longest inferred span**; the latter retrieval rule is hard-coded, not learned. It checks its frozen model digest when observing and snapshots/restores the event history by replay.

The *meaning* of a task-relevant event is engineered: the simulator's correct response is the symbol associated with the **uniquely longest latent event**. The 4-symbol vocabulary, symmetric HMM state topology, state transitions and emissions, seed namespace, memory capacity, and downstream selection rule are explicitly provided. This is not an emergent ontology, open-ended episodic memory, or a generally transferable time model.

## Frozen evaluation

- Development seeds: 14003, 14009, 14033; additional inspected seeds: 27007, 27011, 27017.
- Train: `source_bursts/train/0..159`, five events, duration 3–11 and 76% raw-token accuracy; fitting uses only raw tokens.
- Evaluate 64 test episodes per seed in each of two conditions, `test/92000..92063`: familiar five-event durations/noise; shifted six-event durations 2–17 with 62% raw-token accuracy.
- Compare trained HMM, hand-fixed `(p=.78,q=.72)` HMM, longest unbroken identical-token run, global symbol majority, first/last raw token, and privileged true event label. All methods see identical test episodes and no test updates fitted parameters.
- Report label-recall counts, latent-frame agreement, exact boundary recall and estimated number of event spans. A successful longest-span label is **not** a reliable estimate of exact event boundaries.

## Results

**384 episodes per condition total across six examined seeds.** Higher is better for longest-event symbol recall.

| Method | Familiar source generator | Shifted duration and noise |
| --- | ---: | ---: |
| Learned source-HMM | **298/384 (77.6%)** | 250/384 (65.1%) |
| Fixed-parameter HMM | 281/384 (73.2%) | **253/384 (65.9%)** |
| Raw longest identical-token run | 214/384 (55.7%) | 167/384 (43.5%) |
| Global token majority | 246/384 (64.1%) | 214/384 (55.7%) |
| Privileged longest true event | 384/384 | 384/384 |

Per seed, in order (learned vs fixed HMM), shifted-world successes were: 14003 **45 vs 46**, 14009 **46 vs 38**, 14033 **37 vs 37**, 27007 **42 vs 42**, 27011 **37 vs 45**, and 27017 **43 vs 45**. Thus the shift has **one clear improvement, three regressions, two ties**. The learned model's cross-generator aggregate is slightly worse than the fixed HMM and must **not** be promoted as an improvement in generalization.

The source-world mean exact-boundary recall is about **62%**, dropping to about **42%** on shifted observations. Some seeds oversegment dramatically: the decoder produces about **12 spans instead of 6** on shifted seeds 14009 and 27011. The inferred event count and retrieved label are different metrics; neither should be called exact temporal understanding. The broader, more optimistic result is that a trained HMM can outperform purely raw-symbol first/last, majority and longest-run controls on **both** conditions, while leaving significant errors.

## Reproducibility and integrity

```sh
python -m unittest tests.test_event_segmentation tests.test_cross_family_temporal tests.test_variable_correspondence tests.test_temporal_correspondence -q
python -m benchmarks.event_segmentation_benchmark --cohort development --out benchmarks/event_segmentation_results.json
python -m benchmarks.event_segmentation_benchmark --cohort additional --out benchmarks/event_segmentation_additional_results.json
python -m benchmarks.transfer_benchmark
```

**12 new tests** cover raw-only input, bounded symbol streams, deterministic training, scaled probabilities, recorded-model replay, modified-model rejection, streaming session recovery, rehashed but forged snapshots, and frozen cohort validation. **129 local relevant and available regression tests** passed in three separate groups. Two *other* historical test modules could not import because this reconstructed local checkout lacks `benchmarks.grounded_aliases_benchmark` and `developmental_ai.cross_family_transfer`; therefore neither a full-repository pass nor GitHub CI/hardware pass is claimed. The unchanged transfer benchmark still reports 76%, 69%, and 66.67% on seeds 17/23/41.

SHA-256 digests are tamper checks on self-consistent snapshots, **not authenticated provenance, verified user approval, or a guarantee against an adversary who can fully rewrite a plausible training history**. The module accepts no external actions, personal training data, AthenZ identity records or Synveil permissions.

## Next substantive work

1. Test truly distinct generators with nonstationary temporal structure and unseen observation alphabets; this experiment varies only a single burst generator's parameters.
2. Learn *which* reconstructed events should be retained from delayed task outcomes, instead of hard-coding "longest span." Compare strong task-specific recency/length and fixed-HMM baselines.
3. Build independent D1 evaluation and run the remaining historical regressions from a complete repository checkout. D2 production integration, D3 generalization, D4 skills and later milestones remain open. The post-core **V2A before/partly alongside V2B** sequence is unchanged.
