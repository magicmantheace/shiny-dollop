# D3 research: reward-only learning from unaligned symbol streams

**Status: optional simulator-only experiment; not a passed D3 or D1 gate.** The evaluation protocol was committed first in `benchmarks/unaligned_stream_protocol.json` at `fe17adce44f594a92247b22cce8749bd4029cb97`. No model/parameter/evaluation adjustments were made after the development cohort was inspected.

## Hypothesis and changes

Prior `raw_token_transfer.py` assumes the eight observation symbols and forecast symbols line up one-for-one. Here the benchmark inserts **2–4 unlabeled, independent random symbols** into both observed and candidate forecast sequences without marking which are inserted. The underlying order is preserved. The forecast alphabet remains a hidden seed-fixed permutation of the observation alphabet. One candidate forecasts the real underlying stream better than four competitors, and source reliability changes every episode.

`UnalignedRewardLearner` receives only public observation and candidate sequences, public target offsets, and a *terminal navigation success boolean for its chosen cue* on each training episode. It does **not** receive the hidden token mapping, paired event positions, true goal, correct candidate name, hidden position or source reliability label. It samples source names uniformly by a deterministic hash at fit time. It accumulates reward-conditioned 4×4 token association statistics using a **hand-designed normalized time-proximity window**. At inference it applies a **hand-designed monotone dynamic-programming alignment with a fixed gap penalty** to score each candidate using learned token-pair association weights.

A one-slot spatial cue, learned grid movement updater, greedy navigation heuristic, small vocabularies, episode family and source names are still engineered. This learns neither a general representation nor a new algorithm for time alignment. The simulator generator accesses the public first beacon to synthesize a correct candidate, but **the learner cannot inspect that generator or its reference**.

## Locked evaluation

The six *previously inspected* seeds are 43103, 50021, 61031 and 72019, 83003, 94009; the second cohort was evaluated after the first **without algorithm changes** and is **not an independent blind holdout**. Train solely on `train/89400..89639` (240 episodes per seed) and score `test/99600..99639` (40 episodes per seed). The grid-derived motion updater is trained separately for 24 episodes. No test data updates the model. All methods use the same navigation task and test conditions.

Baseline definitions:

- **Identity-only:** success counts for each named source, drawn from precisely the same chosen training arms and terminal rewards.
- **Unordered bag:** the new learner's own learned pair scores, averaged across every possible pair without temporal positions.
- **Unsupervised alignment:** derive one token permutation from cooccurrence on **all public training streams** (without outcomes), then apply the same monotone alignment DP. This strong simple baseline has *more raw unlabeled input* per fit episode, but the same number of fit episodes; it has no reward labels.
- **Privileged cipher + DP:** provide the *hidden* correct token cipher to the same DP; evaluates how much sequence insertions hurt matching even when meanings are known.
- **Correct-cue reference:** provide the correct cue directly to downstream navigation; this is a task upper reference, not an equally informed method.
- **Random:** deterministic random candidate per episode.

## Navigation results

Each cohort has 120 episodes; each seed has 40.

| Approach | First three | Second three | Combined |
|---|---:|---:|---:|
| Random | 21 | 21 | 42/240 (17.5%) |
| Fixed source identity | 25 | 25 | 50/240 (20.8%) |
| Unordered reward pair statistics | 24 | 34 | 58/240 (24.2%) |
| **Reward-learned monotone alignment** | **63** | **59** | **122/240 (50.8%)** |
| Unsupervised token-permutation + monotone alignment | 74 | 68 | **142/240 (59.2%)** |
| Privileged token cipher + same alignment | 74 | 68 | 142/240 (59.2%) |
| Correct source upper reference | 112 | 110 | 222/240 (92.5%) |

The unsupervised method recovers the exact hidden 4-symbol permutation **on all six seeds**, yet even the privileged cipher cannot recover many correct sources from the independently inserted sequences. This points to a **sequence-correspondence problem**, beyond mapping symbol identities. The reward learner significantly improves over source memorization in these synthetic episodes but **regresses against the previous aligned-stream experiment** (203/240 learned in the prior benchmark; tasks have different generated observations and should not be treated as a paired estimate). It loses to the simple unsupervised baseline on every seed. There is **no promotion to default** and no claim of D3 completion.

## Testing and scope

Run:

```sh
python -m unittest tests.test_unaligned_stream tests.test_raw_token_transfer tests.test_dynamic_reliability tests.test_environment_api tests.test_online_memory_gate tests.test_reward_aliases tests.test_delayed_choice tests.test_occluded_navigation tests.test_selective_memory -q
python -m benchmarks.unaligned_stream_benchmark --cohort development --out benchmarks/unaligned_stream_results.json
python -m benchmarks.unaligned_stream_benchmark --cohort additional --out benchmarks/unaligned_stream_additional_results.json
python -m benchmarks.transfer_benchmark
```

**73/73** targeted and related tests passed on a reconstructed local checkout; the full remote suite was not run. The unchanged transfer benchmark reproduced seed 17 76.0%, 23 69.0%, 41 66.67%. No GitHub Actions or PC/hardware testing claimed. Versioned record digests and exact training-decision replay reject inconsistent records; they **do not authenticate** a fully forged yet internally consistent history, owner consent, or model promotion rights.

## Next development

Separate **symbol identity learning** from **temporal alignment confidence**. Test dynamic time warping, insertion/deletion channels and calibration of alignment uncertainty with strong unsupervised references. Only attempt task-family generalization after measurable improvement over the simple unsupervised method. D1 frozen independent blind verification and D3 genuinely different task families remain open; V2A affective cognition before/alongside V2B virtual home remains unchanged.
