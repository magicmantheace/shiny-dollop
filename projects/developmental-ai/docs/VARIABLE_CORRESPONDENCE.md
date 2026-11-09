# D3 experimental variable-correspondence and insertion/deletion uncertainty

**Status:** optional, headless, simulation-only. Does **not** complete D1/D3 or replace the default navigator. [Precommitted protocol](../benchmarks/variable_correspondence_protocol.json) was pushed as `8555dc80507b35e72a114b1d9e3cb40bb4dc2302` before running the new evaluation. The six seeds were already inspected during earlier work, so this is **not independently blind**.

## Specific problem

The previous [eight-event probabilistic alignment](TEMPORAL_CORRESPONDENCE.md) averaged over unknown *positions*, but hard-coded **exactly eight corresponding events**. The new generator starts with eight synthetic underlying events and independently deletes 0–2 of them from the observed stream and each candidate forecast; it then independently inserts 2–4 unlabelled noise symbols in each. Stream lengths remain 8–12 and the actual number of common underlying event indices can range from four to eight. Insertion/deletion labels and the true correspondence count are withheld from every learner and baseline selector.

The model retains **engineered** monotone ordering, a known four-token vocabulary, a fixed **maximum of eight** possible shared events, and a possible correspondence range of **3–8**. It does not infer a new representation or independently determine the number of physical events. The token permutation is fitted beforehand by the previous unsupervised public-stream learner, not supplied from simulator truth.

## Learning and inference

`variable_correspondence.py` computes a normalized, sum-product alignment likelihood for each candidate shared-event count K=3..8 and marginalizes those likelihoods under a truncated binomial prior. An expectation-semiring DP also yields the probability-weighted expected symbol agreement count without supplying a true alignment. A **three-iteration bounded EM** update estimates an emission agreement probability and an approximate event-overlap survival prior from 120 public training sensor/forecast pairs per seed (`train/90000..90119`).

The *candidate pairs* used for EM are selected by the **frozen earlier eight-event marginal selector**, not by simulator truth, reward labels, cue correctness, or privileged event identifiers. The resulting parameters are thus **pseudo-label-dependent estimates**, not independently calibrated confidence or a physical insertion/deletion-channel law. Checkpoints include all public training pairs and are restored by deterministic re-fitting; this rejects inconsistent parameter claims even if someone recomputes an SHA-256 checksum, but cannot authenticate a wholly rewritten coherent history.

All inference methods see the same public action/observation fields. Candidate offsets drive the same existing simulator-only navigation controller; no real actions, private human memories, deployment permissions or AthenZ/Synveil dependency are introduced.

## Frozen comparison

The original unaligned token-permutation training is untouched (`train/89400..89639`), with an independent 120-episode public-stream EM fit as described above. Evaluation uses `test/99800..99839`, 40 episodes per seed, for development 43103/50021/61031 and previously inspected additional 72019/83003/94009. The original frozen tests/benchmarks remain unchanged.

| Seed | Fixed-source identity | Prior reward-pair scoring | Previous max-path DP | Previous fixed-eight marginal | New variable marginal | Correct cue |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 43103 | 8 | 14 | 16 | 15 | **21** | 38 |
| 50021 | 3 | 20 | **22** | 19 | 21 | 37 |
| 61031 | 9 | 15 | 14 | 19 | **21** | 37 |
| 72019 | 7 | 11 | 17 | **22** | 20 | 40 |
| 83003 | 10 | 21 | 24 | 22 | **25** | 39 |
| 94009 | 6 | 12 | 16 | 16 | **17** | 35 |
| **Total / 240** | **43** | **93** | **109** | **113** | **125 (52.1%)** | **226 (94.2%)** |

The new method beats the previous fixed-eight marginal on **five seeds**, regresses on **one**, and gains **12 tasks / 240** in aggregate. It beats the older max-path alignment on five seeds and loses on one. All results are simulation outcomes on previously examined seed families. The correct cue is a privileged scoring reference, not an equally informed controller. Supplying the true hidden token permutation to the new variable-count aligner gave the *same* results as its already-exact learned permutation on these seeds (125/240), leaving a very substantial correspondence/observation-noise gap.

### Event-count diagnosis — important negative result

Across seeds, the new model predicted **6.136** matched events on average for the true candidate, versus **6.117** underlying shared events counted **by the benchmark only**. These similar means do **not** prove accurate per-episode estimates. The **post-result supplemental** absolute-error comparisons are:

| Method | Mean absolute error, events |
| --- | ---: |
| Learned correspondence posterior mean | **0.811** |
| Always guess six common events | 0.775 |
| Simple heuristic: mean public stream length minus four | **0.585** |

The length heuristic is a hand-engineered diagnostic that uses the known noise-generation regime, and it **outperforms** the learned model at exact event-count estimation. It was added as an openly labeled **post-hoc diagnostic**; it was not a predefined target for model selection or used to tune the learner. In other words, the improvement in navigation is from *averaging several alignment explanations*, not demonstrated learning of the actual number of underlying events.

The fitted survival parameters ranged approximately **0.769–0.800**, and symbol agreement approximately **0.794–0.831** across six seeds. These are model parameters, **not measured or calibrated event survival probabilities**.

## Reproduction and tests

```bash
python -m unittest tests.test_variable_correspondence tests.test_temporal_correspondence tests.test_unaligned_stream tests.test_raw_token_transfer tests.test_dynamic_reliability -q
python -m benchmarks.variable_correspondence_benchmark --cohort development --out benchmarks/variable_correspondence_results.json
python -m benchmarks.variable_correspondence_benchmark --cohort additional --out benchmarks/variable_correspondence_additional_results.json
python -m benchmarks.transfer_benchmark
```

**44 relevant tests passed** locally on a reconstructed checkout, including nine new tests comparing the DP against exhaustive enumeration and checking restart and tamper failures. The historical transfer benchmark remained **76.0%, 69.0%, 66.7%** on seeds 17, 23, 41. **Not** a full GitHub-source test run, CI run, independent blind study, physical device test or validation of real-world safety.

## Next D3 experiment

Retain the strong count/length heuristics when evaluating future changes. Next test models that infer event duration and alignment from **different task families** and **different noise mechanisms**; avoid overclaiming improvement to count inference. The genuinely held-out D1 protocol, standalone authenticated D2 bridge and D3 out-of-family transfer remain open. Versions 2A affective cognition and 2B virtual home retain their approved post-core sequence.
