# D3 raw-token relationship learning (experimental, simulation only)

**Status:** optional research; D1 and D3 remain OPEN. This experiment removes the
prior learner's explicit integer *forecast-agreement* feature. It does **not**
remove designed token-slot alignment, a four-symbol vocabulary, engineered cue
offsets, the one-slot spatial memory, or the hand-coded greedy navigator.

## Protocol and permissions

The [frozen protocol](../benchmarks/raw_token_transfer_protocol.json) was
committed as `0475ac5` **before** examining any of this experiment's test
results. The earlier `dynamic_reliability` setup underlies the simulator:
one candidate forecasts public eight-symbol sensor outcomes more accurately,
with its correct source changing on each episode. Here the two symbol streams
have **disjoint literal alphabets**, and the simulator applies an unknown,
seed-fixed permutation to all forecast symbols. The model receives raw symbol
pairs, a candidate cue offset, and only **one terminal navigation success bit**
per `train` episode. No source labels, correct cue, hidden permutation, true
position, simulator internals or correct-source oracle enter the fit API.

- Six *previously examined* seeds: development 43103/50021/61031 and additional
  72019/83003/94009. The additional cohort was reserved in the protocol and
  evaluated without retuning, but is **not independently blind**.
- Exactly 360 fit episodes per seed in `train/88500..88859`; separate `test`
  indices `99200..99239`, 40 episodes per seed, identical budgets across methods.
  The spatial motion updater gets 24 additional public grid `train` episodes.
- The learned model collects source-independent **raw token-pair frequencies**
  from 360 random source selections (deterministic, seed-bound) and the outcome
  of each choice. At evaluation it ranks the complete candidate forecast
  using a Laplace-smoothed positive-vs-negative likelihood ratio. Neither a
  hidden substitution table nor literal agreement features are inputs.
- Stronger *unsupervised* baseline sees **all five candidate forecasts** during
  those same training episodes, with no reward; it fits the maximum cooccurrence
  one-to-one permutation (four symbols; 24 assignments). Other comparisons:
  identity-only success rates derived from the **same 360 chosen arms and
  outcomes**, literal comparison (expected to be meaningless), random source,
  correct public-cipher agreement (privileged benchmark reference), and correct
  target cue (oracle).
- Runtime output is only a simulated target-offset proposal. Checkpoints
  contain bounded action, raw sensor and terminal outcome history and are
  validated by deterministic choice/statistic replay. SHA-256 integrity is
  **not** authentication or consent. No online evaluation updates or OS actions.

## Frozen results: learned correlations work, simpler unsupervised wins

Navigation successes / 120 tasks per cohort; higher is better.

| Method | Development 3 seeds | Additional 3 seeds | Combined 6 seeds |
|---|---:|---:|---:|
| Reward-learned raw pair likelihood | 104 | 99 | **203/240 (84.6%)** |
| Source-identity bandit, same rewards | 22 | 23 | 45/240 (18.8%) |
| Literal token comparison | 25 | 21 | 46/240 (19.2%) |
| **Unsupervised cooccurrence alignment** | **107** | **101** | **208/240 (86.7%)** |
| Decoder-known max-agreement rule | 107 | 101 | 208/240 (86.7%) |
| Random source | 24 | 21 | 45/240 (18.8%) |
| Correct target cue, privileged upper bound | 112 | 108 | 220/240 (91.7%) |

The unsupervised procedure recovered the exact simulator token permutation in
**all six seeds**, while the reward-conditioned learner lost five more tasks.
Thus **reward-only learning is not necessary to solve this toy alignment**.
The relation is learnable from public cooccurrence without reward because the
simulator supplies aligned paired time steps, stationary token mapping and a
noticeable 75%-versus-25% forecast-quality asymmetry. This result does **not**
show understanding of free-form language, arbitrary sensory domains, new
alphabets, emergent attention, durable skill transfer or D3 acceptance.

The *test* benchmark computes true-source correctness for scoring only; never
passes it to any learned strategy. No changes to existing default navigator,
identity data, AthenZ, Synveil or downstream permission boundaries.

## Reproduce

```sh
python -m unittest tests.test_raw_token_transfer tests.test_dynamic_reliability tests.test_environment_api -v
python -m benchmarks.raw_token_transfer_benchmark --cohort development --out benchmarks/raw_token_transfer_results.json
python -m benchmarks.raw_token_transfer_benchmark --cohort additional --out benchmarks/raw_token_transfer_additional_results.json
python -m benchmarks.transfer_benchmark
```

The targeted tests and unchanged transfer benchmark passed in the reconstructed
checkout. Other legacy modules are not all present in that checkout, and no
complete fresh-clone suite, CI or hardware test is claimed.

## Next discriminating problem

Remove the **paired time-step alignment** or make the symbol mapping change
within episodes; include a relation that cannot be recovered by global
cooccurrence alone. Freeze an independent protocol and compare matched
reward-only, unsupervised, heuristic and oracle baselines. Do not promote any
model if a simpler learner wins. Preserve Version 2A before/overlapping 2B.
