# D3/D4 research: outcome-guided retrieval of inferred events

**Status:** optional simulator-only experiment, not completed D3/D4, autonomous episodic memory, or general-purpose attention. The frozen protocol `benchmarks/outcome_event_memory_protocol.json` was committed as `b687fd07e7d4da312646ae7bb7bc18c0a899afbc` **before** evaluating the new benchmark. The six seeds have appeared in earlier studies and are **not blind**.

## Capability and trust boundary

`developmental_ai.outcome_event_memory.OutcomeEventMemory` combines the previously fitted raw-observation-only four-state HMM event segmenter with a contextual reward-only retrieval policy. During a separately namespaced source-generator training phase, it sees only (1) a public context `0/1`, (2) raw symbol streams, (3) its own chosen inferred event span, and (4) a single terminal success/failure boolean. It **does not receive** the true relevant label, hidden event boundaries, true event states, or a privileged oracle choice. It learns Beta-smoothed success frequencies for each `(public context, inferred label)` plus bounded deterministic UCB-style exploration during training.

At inference the learned policy is frozen and selects **one event span** for read-only retrieval. `FocusedEventSession` provides incremental event focus, keeping the bounded observation log for exact audit replay. It is **not** a one-slot total storage system, and cannot promote models or actuate any device. Model and session SHA256 records detect accidental changes, while rebuilding from recorded observations and rewards rejects locally inconsistent decisions/states. **SHA256 is not authenticated provenance** and a fully re-authored, internally consistent training history can be forged.

The benchmark simulator independently assigns each seed a hidden mapping from two public contexts to two distinct relevant event labels. Reward is true if the **hidden latent state at the chosen span's center** equals the task's contextual preference. Some episodes do not contain that target label at all, so privileged `oracle_available` is below 100%. Crucially this is still a *deliberately engineered* task whose label semantics remain stable across source and shifted generators. This is not experience valuation in an unrestricted world.

## Locked train and evaluation schedule

- Frozen HMM segmenter: `source_bursts/train/0..159`, exactly 160 raw streams and five pre-existing EM iterations. No outcome labels used in its fitting.
- Outcome selector training: `source_bursts/train/2000..2199`, 200 episodes and exactly one binary reward per episode. A separately reward-trained **raw-run** control receives the same episodes and its own action feedback, with an equal interaction budget.
- Frozen test: `test/93000..93063`, 64 trials for **each** seed/family, on development 14003/14009/14033 and additional previously inspected 27007/27011/27017. No test outcomes reach fit or preference updates.
- Families: familiar `source_bursts` (five segments, 3–11 frames, 76% sensor agreement) and shifted `shifted_bursts` (six segments, 2–17 frames, 62% sensor agreement). Identical hidden preference structure in both: the shift is in sensor noise and durations, **not relevance rules**.
- Controls: reward-learned raw-token runs; the longest and the most recent *HMM-inferred* event; raw-global-majority token; benchmark-only oracle with access to the true latent states. All controls run on identical evaluation episodes. No changes to prior benchmarks.

## Six-seed results: rewards earned out of 384 trial opportunities per family

| Retrieval rule | Familiar generator | Shifted generator |
| --- | ---: | ---: |
| **Learned event priorities with inferred spans** | **276/384 (71.9%)** | **246/384 (64.1%)** |
| Reward-trained raw event runs | 181/384 (47.1%) | 111/384 (28.9%) |
| Longest HMM-inferred event | 96/384 (25.0%) | 111/384 (28.9%) |
| Most recent HMM-inferred event | 95/384 (24.7%) | 109/384 (28.4%) |
| Raw globally most common symbol | 101/384 (26.3%) | 76/384 (19.8%) |
| Privileged *available-target* upper bound | 327/384 (85.2%) | 339/384 (88.3%) |

Per-seed learned selections (64 test episodes each):

| Seed | Familiar | Shifted |
| --- | ---: | ---: |
| 14003 | 46 | 51 |
| 14009 | 39 | 34 |
| 14033 | 45 | 41 |
| 27007 | 52 | 43 |
| 27011 | 43 | 27 |
| 27017 | 51 | 50 |

The machine-readable benchmark files retain all per-seed control counts and model digests. The additional seeds were previously inspected and are not blind.

This result supports *outcome-guided selection of inferred events over simple duration/recency and independently reward-trained noisy raw-run retrieval*. It does **not** establish learned significance semantics, unrestricted generalization, free-form event discovery or a reusable skill system. A context→state contextual lookup on clean state labels would also solve much of this artificial task; here those labels are hidden behind a noisy fitted segmenter. The shifted generator retains exactly the same relevance mapping, and the trained model loses about 7.8 percentage points after the shift.

## Reproduce

```sh
python -m unittest tests.test_outcome_event_memory tests.test_event_segmentation tests.test_environment_api tests.test_transfer -q
python -m benchmarks.outcome_event_memory_benchmark --cohort development --out benchmarks/outcome_event_memory_development_results.json
python -m benchmarks.outcome_event_memory_benchmark --cohort additional --out benchmarks/outcome_event_memory_additional_results.json
python -m benchmarks.transfer_benchmark
```

The new tests and available targeted/related tests ran in a reconstructed local checkout; this is **not** a claim of repository-wide CI or real-hardware validation. The old transfer benchmark remained 76.0%, 69.0%, and 66.67% on seeds 17, 23, 41. No private data or owner-origin memories enter the repository.

## Next gap

Future work needs evaluation where *relevance itself changes* across tasks, without stable context↔label pairings or developer-defined public contexts. A distinct new task family and an independent frozen evaluation cohort should precede any D3/D4 promotion; consider matched clean-state contextual lookup, delayed outcomes, multiple memory slots, and retention after restarts. AthenZ identity provenance and Synveil policy stay independent. Post-core V2A affective cognition precedes/overlaps V2B virtual home as approved.
