# Learned cross-task retention choice (`cross-task-retention/v1`)

**Experimental, simulation-only. Does not complete D3 or provide general learned attention.** The common D2 `EnvironmentSession` interface supplies public observations, action lists and reward feedback. This experiment trains two candidate memory strategies in the delayed-choice task, then reuses the selected **retention decision** in occluded navigation.

## What is actually learned

- Two fixed retention hypotheses are provided by the experimenter: **initial** (write the first cue and keep it) and **latest** (overwrite the slot with every distractor). The state slot, cue/distractor identification, and mapping from the delayed-task token to a spatial goal beacon are *engineered*.
- Independently for each hypothesis, a four-symbol/four-action value table is trained from delayed-choice *terminal rewards*, without reading the hidden correct action. Both candidates train on the same `train/0..399` episodes; frozen candidates are evaluated on `train/5000..5119`. Their observed validation success counts select the retention strategy; the retained table and validation evidence are checksum-bound to a versioned snapshot.
- On the delayed task, evaluate the frozen learned response table and retention choice on `test/85000..85039`, **longer distractor intervals** than the short training band.
- On occluded navigation, use the *selected retention strategy* to control whether the initial target beacon is retained in the existing `PortableOffsetMemory`. Its movement update was learned separately from grid observations; its spatial state representation and the `greedy_action` controller are engineered. Neither delayed-choice training data nor navigation rewards are used to train a cross-task policy.
- A checksum detects accidental modifications; it is not an authentication signature or owner consent. No models are automatically deployed and no external actions are exposed.

## Reproduction

```sh
python -m unittest tests.test_cross_task_retention tests.test_environment_api tests.test_delayed_choice tests.test_selective_memory -v
python -m benchmarks.cross_task_retention_benchmark --seeds 2749 6607 9901 --out benchmarks/cross_task_retention_results.json
python -m benchmarks.cross_task_retention_benchmark --seeds 17431 24869 37021 --out benchmarks/cross_task_retention_additional_results.json
python -m benchmarks.transfer_benchmark
```

The six seeds, algorithm and test episodes were inspected during this development pass. **Neither cohort is a blinded, pre-registered independent evaluation**. No claim of statistical superiority over the hand-coded **initial** strategy: the chosen strategy reproduces that strategy exactly.

## Results (40 episodes per seed and family)

| Cohort | Retention selected | Delayed long: learned / latest | Occluded: learned / forget |
| --- | --- | --- | --- |
| Initial 2749/6607/9901 | initial on 3/3 | 120/120 vs 31/120 | 111/120 vs 0/120 |
| Additional 17431/24869/37021 | initial on 3/3 | 120/120 vs 28/120 | 114/120 vs 0/120 |
| Total | initial on 6/6 | 240/240 vs 59/240 | 225/240 vs 0/240 |

A trivial hand-coded initial-cue retention baseline is equally successful; this result shows the agent can **select** between two proposed retention policies by ordinary reward, then carry that policy preference to a second observation domain. It does **not** show that the agent discovered a general memory controller, inferred cross-modal semantics, selected arbitrary relevant facts or obtained humanlike cognitive development.

**Validation scope:** The new module's eight tests and related existing D2/delayed/selective-memory tests passed locally. The original unchanged transfer benchmark returned 76%, 69%, 66.67% success for seeds 17/23/41. The full reconstructed suite exceeded its execution time limit, and the reconstructed checkout does not contain every remote test module. No GitHub Actions or hardware test is claimed.

## Next D3 research

Unify the cue selection operation across richer *competing, same-channel* observations; train a per-observation write/keep controller rather than selecting only a two-way strategy at the episode level; test non-navigation tasks with unseen observation schemas. Freeze new evaluation seeds and protocols **before** examining results. Preserve separate training/validation/evaluation splits and matched simple baselines. D1, D2 production integration and D3 generalization stay open. V2A affect and V2B virtual home remain planned post-core.
