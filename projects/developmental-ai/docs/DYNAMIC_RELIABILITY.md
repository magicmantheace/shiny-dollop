# D3 exploratory reward-only selection under changing cue reliability

**Status:** optional, offline, simulation-only experiment. This does not close D1, D2 or D3, and does not authorize actions or promote models. The protocol `benchmarks/dynamic_reliability_protocol.json` was committed at `bcb315d2f9cfab685bbcf59ad3cfefbf5129b985` **before the first test evaluation**. These public, deterministic evaluations were performed by the developer during this pass; the reserved cohort was executed after the development cohort **without changing the implementation or hyperparameters**, but is not a genuinely blind third-party audit.

## Question and architecture

Previously, a reward-only learner could memorize which fixed source was correct for each context, tying simple source lookup. Here the correct source changes independently each episode across five identities. Every candidate supplies a proposed target-offset and a **forecast of eight ordinary public probe readings**. The simulator emits those eight observations before selection. One cue source forecasts each probe accurately with probability `.75`; others use `.25`. Correct source identity is redrawn each episode, with source order shuffled. Forecasts and outcomes are visible, but *correct source*, the simulator's initial public target beacon used by the test fixture, and hidden position are **not delivered to the selector**. The generator reads that initial **public** beacon solely to construct one valid candidate and four invalid candidates.

`developmental_ai.dynamic_reliability.DynamicReliability` makes an individual source choice based on the count of forecast/outcome agreements. It learns a smoothed reward-success table over **four manually defined agreement bins** using only the terminal task-completion bit after the chosen cue is used in an occluded-navigation simulation. A contextual source identity-only bandit is fit independently on the same 360 episodes, along with strong nonlearning comparators. The pretrained motion-memory updater, navigation controller and one-slot target cue are existing engineered or separately learned components. This is **a deliberately engineered public evidence feature**, not freely discovered semantics, model-based curiosity, nor generally learned relevance.

The experiment's fixed namespace per seed is `train/88000..88359`, with `test/99000..99039` untouched by fitting. The existing movement-memory updater uses 24 separate visible-grid training episodes. Test feedback never updates either selector. Fit and test seeds are independent procedural worlds within the *same* task family; neither transfers learned source-selection weights to an unrelated family. Integrity receipts are SHA-256 checksums, **not signatures or proof of authorized provenance**. Replay catches internally impossible choices and statistics; someone able to forge an entirely coherent history and recompute the digest is not cryptographically excluded.

## Frozen protocol and results

Six seeds: development `(43103, 50021, 61031)` and independently *reserved within this pass* `(72019, 83003, 94009)`. Forty navigation evaluations per seed; all seven methods use the same synthetic cue streams and navigation episode RNG. All seeds, metrics, per-seed successes, and negative outcomes are published in `benchmarks/dynamic_reliability_results.json` and `benchmarks/dynamic_reliability_reserved_results.json`.

| Cohort (120 navigation episodes) | Reward-trained evidence | Fixed identity | Maximum agreement, engineered | Random | Correct-cue oracle |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | **102** | 27 | **106** | 22 | 111 |
| Reserved | **104** | 13 | **103** | 24 | 110 |
| Combined | **206 (85.8%)** | 40 (16.7%) | **209 (87.1%)** | 46 (19.2%) | 221 (92.1%) |

The first and last cue baselines are also recorded per seed. Results demonstrate episode-level cue arbitration that cannot be reduced to a fixed source-name lookup. They **do not demonstrate improvement over the hand-engineered feature rule**: maximum forecast agreement is slightly better over both cohorts, and remains an essential baseline. The 3/240 outcome gap is not statistically conclusive. Even the oracle fails some navigation episodes because the navigator can fail after selecting the right cue. The model was never evaluated on different observation modalities, different forecast calibration, long history changes, or new task families. Therefore D3's genuine cross-family generalization gate stays open.

## Reproduction

```bash
python -m unittest tests.test_dynamic_reliability tests.test_environment_api tests.test_delayed_choice tests.test_occluded_navigation tests.test_transfer -v
python -m benchmarks.dynamic_reliability_benchmark --cohort development --out benchmarks/dynamic_reliability_results.json
python -m benchmarks.dynamic_reliability_benchmark --cohort reserved --out benchmarks/dynamic_reliability_reserved_results.json
python -m benchmarks.transfer_benchmark
```

The relevant reconstructed local checkout passed **34 tests**; the original three-seed transfer benchmark remained at `76.0%, 69.0%, 66.67%`. The reconstructed checkout is not a verified, complete repository mirror. No GitHub Actions, production integration, or hardware testing is claimed.

## Next falsification test

Use *previously unseen* probe alphabet sizes, imperfect/out-of-order probe evidence, nonstationary cue reliability, and task families where an elementary forecast-agreement statistic is not already provided. Freeze candidate representations, evaluation conditions, and baseline algorithms before observing test outcomes. Contrast both source-identity lookup **and** a reward-agnostic agreement heuristic under matched observations and interaction budgets. Prefer an independent evaluator. Default agent behavior, AthenZ identity controls, Synveil system permissions, and the V2A-before/overlapping-V2B roadmap sequence remain unchanged.
