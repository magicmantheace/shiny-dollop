# Learned one-slot selective memory — `selective-memory-v1`

**Research claim:** A small contextual-bandit-style learner can learn to keep a relevant signal in one memory slot when irrelevant signals compete to overwrite it. This is narrower than learned episodic memory, recurrence, self-directed attention, or human-like cognition.

## Observation and task design

Each trial presents a context bit (0/1) and a shuffled stream with precisely one `A` signal, one `B` signal, and 2–6 (`short`, train) or 10–20 (`long`, test) `N` noise signals. All channels carry one of four symbols. The current context determines whether A or B is informative, but neither observations nor the controller reveal the source rule or four-symbol target-to-button permutation. The first/last/learned memory agents only store **one** `(channel, symbol)` pair. After the signals disappear, a response is selected, and only terminal correctness is available as learning feedback.

This differs from the earlier delayed-choice task: **no signal is explicitly labeled as the cue** and informative channels appear at random positions among distractors. The context bit and channel identifiers are engineered, however; the model does not learn features from raw sensory data. Source relevance is stationary, the context is perfectly observable, only one relevant signal exists, and target distribution is fixed.

The learned memory gate uses a value estimate for `(context, channel)` to choose `write` versus `keep`. Its Q-style action lookup learns `(context, channel, symbol) → button` associations. The memory gate and response table update only from scalar terminal success/error. At evaluation, no exploration or updates occur. This is a **learned selection policy**, not a neural network, learned recurrent representation, biological brain, or generalized long-term memory.

## Controls and reproducibility

- `learned`: learns channel utility from reward feedback and chooses memory writes accordingly.
- `first`, `last`, `random`: alternative one-slot memory update schemes, each with the same trainable action table.
- `oracle`: knows the hidden relevance/response rule; this is the simulator upper bound, **not a learned result**.
- Train `train/short`, evaluate disjoint deterministic SHA-256-derived `test/short` and `test/long` namespaces, no evaluation-time updates.
- Three inspected **development seeds** (11/31/73), 6,000 training episodes and 400 held-out test trials per band, *per seed and mode*. These have been examined while developing the algorithm, so they are not independent blind replication.
- SQLite stores seed/mode/schema-bound action Q-values, gate estimates, and episode cursor. Train continuation after restarting reproduces uninterrupted training exactly.
- Deterministic source observations and in-simulator write/keep transitions can be checked by the trace replay validator. A SHA-256 checksum **does not authenticate** agent behavior or source provenance, and replay does not prove the stored Q-policy generated the trace.

## Results, test/long

| Seed | Learned gate | First signal | Last signal | Random overwrite | Oracle |
| --- | ---: | ---: | ---: | ---: | ---: |
| 11 | 100.0% | 32.25% | 27.25% | 31.75% | 100.0% |
| 31 | 100.0% | 30.50% | 32.25% | 26.75% | 100.0% |
| 73 | 100.0% | 31.50% | 27.50% | 33.00% | 100.0% |

These results **only** establish successful feature-conditioned signal selection in a toy simulation. Do not infer open-world memory, learning human priorities, or independent agency. Because the target rule is fixed and easy to distinguish by channel, the task is deliberately solvable by a small table.

## Commands

```bash
python -m unittest discover -s tests -v
python -m benchmarks.selective_memory_benchmark --seeds 11 31 73 --train-episodes 6000 --test-episodes 400
python -m developmental_ai.selective_memory train --db selection.db --episodes 6000
python -m developmental_ai.selective_memory evaluate --db selection.db --episodes 400 --band long
python -m developmental_ai.selective_memory trace --db selection.db --index 3 > trace.json
python -m developmental_ai.selective_memory verify --trace-file trace.json
```

`benchmarks/selective_memory_results.json` has complete per-seed, per-ablation results including memory retention and pre-training baselines. Training databases should remain outside Git.

## Next research failure modes

1. Multiple conflicting signals of the *same* channel, with relevance inferred from changing context over a long sequence.
2. Partial and noisy context observations, altered cue reliability, and distribution shifts without test-set tuning.
3. Learned recurrent gating and memory content *without* hand-coded channel labels or source identifiers.
4. Transfer selective-memory skills into unseen navigation/courier tasks where a target becomes occluded.
5. An independent evaluation protocol frozen before its new seeds are generated or inspected.
