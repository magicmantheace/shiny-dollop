# D3 experiment: marginalizing uncertain temporal correspondence

**Status:** optional simulation-only research, not a passed D1/D3 gate. The exact evaluation design was committed first as `benchmarks/temporal_correspondence_protocol.json` (`a69ef10623fe2ca7c0b51bab81ed85c2844b9321`). The evaluation episodes were not used to tune the algorithm. The six seeds had already been inspected in earlier experiments; neither cohort is genuinely independent blind testing.

## Question

The previous `unaligned_stream.py` and its unsupervised comparison choose a **single highest-scoring monotone alignment**, even though 2–4 unrelated tokens are inserted independently into each eight-event stream. Is it better to **sum the evidence across all possible latent correspondences** instead of committing to one alignment prematurely?

## New model and what it does *not* learn

`developmental_ai.probabilistic_alignment` computes a normalized sum-product dynamic-programming partition over all strictly order-preserving alignments of exactly eight matched positions between two sequences of length 10–12. Its pair likelihood ratios are fixed at `0.75 / 0.25 = 3` for matching decoded symbols and `(0.25 / 3) / 0.25 = 1/3` otherwise; skipped symbols are independent uniform noise. The score is the log of the **average** ratio over `C(n,8) × C(m,8)` alignments, not the maximum-score alignment. This is a **strong, explicitly engineered generative prior** reflecting the known benchmark generator, not an independently learned time model or learned count of underlying events.

The unknown mapping between the two four-symbol alphabets is estimated from exactly the **same 240 public training episodes** as the earlier unsupervised baseline, without rewards or hidden cipher. An immutable, hash-checked record binds the permutation to a *declared* training digest; the hash is **not proof** that training actually used the declared evidence, a signature, or permission to deploy. The emitted softmax distribution is a **relative ranking diagnostic**, not calibrated confidence that any cue is correct. No solver sees the reference beacon, hidden correct cue, cipher, true position, or reward during test-time selection. The benchmark uses such information solely to construct data and score outcomes. No real-world actions or OS permissions exist.

## Precommitted comparison

Training: unchanged unaligned-stream procedure at `train/89400..89639`, plus the separate 24-episode grid-derived movement updater. Frozen test: `test/99700..99739`, 40 episodes per seed, development seeds 43103/50021/61031 and previously inspected additional seeds 72019/83003/94009. None of the previously published `test/99600..99639` numbers have been overwritten. All methods run on **the same new evaluation episodes**:

- **Fixed source:** choose the source whose training terminal rewards were best, ignoring observations.
- **Previous reward learner:** existing reward-trained near-pair statistics and max-path score.
- **Previous unsupervised max-path:** same permutation estimated from public training streams; single highest-scoring monotone path.
- **New unsupervised marginal:** same permutation, but sum-product over all eight-pair alignments.
- **Privileged cipher + marginal:** reveal the actual cipher to the new scorer only as a benchmark check of mapping quality.
- **Correct cue:** true candidate directly supplied at scoring time, not an equally informed controller.

## Results, same-index navigation successes

| Method | Development /120 | Additional /120 | Total /240 |
| --- | ---: | ---: | ---: |
| Fixed source | 24 | 23 | 47 (19.6%) |
| Existing reward-trained unaligned scorer | 68 | 66 | 134 (55.8%) |
| Existing unsupervised max-path | 73 | 70 | 143 (59.6%) |
| **New unsupervised marginal correspondence** | **77** | **76** | **153 (63.8%)** |
| Privileged cipher + same marginal | 77 | 76 | 153 (63.8%) |
| Correct-cue reference | 114 | 108 | 222 (92.5%) |

The new scorer chooses the actual correct cue **167/240**, versus **153/240** for the old max-path scorer. It improves task completion on seeds 43103, 50021, 61031, 83003 and 94009, and regresses by two on 72019: **five improvements and one regression**. The underlying token permutation already matches the hidden simulator mapping on all six seeds; knowing that mapping perfectly cannot improve this particular result. The remaining gap is largely ambiguous noisy sequence correspondence and downstream policy errors.

These results do not establish statistical superiority on fresh independent worlds, calibration of the diagnostic softmax, generalizable skill learning, emergent temporal understanding or v1 completion. The model deliberately knows the latent eight-event count and emission probabilities. It stays **optional**, with the old policy unchanged.

## Validation and reproduction

```sh
python -m unittest tests.test_temporal_correspondence tests.test_unaligned_stream tests.test_raw_token_transfer tests.test_dynamic_reliability tests.test_environment_api -q
python -m benchmarks.temporal_correspondence_benchmark --cohort development --out benchmarks/temporal_correspondence_results.json
python -m benchmarks.temporal_correspondence_benchmark --cohort additional --out benchmarks/temporal_correspondence_additional_results.json
python -m benchmarks.transfer_benchmark
```

**42** local targeted and related tests passed. The new module has eight tests, including exhaustive enumeration of small sequence alignments, strict bounds, checkpoint hash checks, and altered-input rejection. The unchanged historical transfer benchmark reproduced 76.0%, 69.0% and 66.7% for seeds 17, 23, and 41. The full reconstructed test suite exceeded execution time; a clean full-suite pass, CI, hardware verification and independently blind evaluation are **not claimed**.

## Next research step

Learn or infer the latent event count and insertion channel from observations rather than fixing them from the generator. Test data generated with new noise mechanisms and genuinely new task families, while keeping this same-index comparison and the old unsupervised baseline. D1 and D3 remain open; V2A emotion development stays before/overlapping V2B virtual home, and AthenZ/Synveil integrations are not coupled to this simulator.
