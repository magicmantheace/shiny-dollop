# D3 experimental reward-only grounding of unfamiliar cue sources

**Status:** optional simulator-only research. Frozen evaluation protocol was committed to
`benchmarks/reward_only_alignment_protocol.json` before this experiment's test results.
This is not blind, not zero-shot target-domain adaptation, not semantic inference,
and does not complete D1 or D3.

## What changed from paired alias calibration

The earlier `grounded_aliases.py` receives public paired training examples
`{context, cues, reference}`. The new `reward_aliases.py` **never accepts** the
reference or a correct-source label during fit, inference, feedback, or restore.
Instead, during `train/78000..78359`, it chooses one of five unfamiliar named
sources in one of two unfamiliar contexts, runs a simulated navigation episode,
and receives only whether the task was completed. It retains context/source
success counts and learns which source has yielded better outcomes. Source
selection uses an exploration bonus during training and a smoothed empirical
success rate for frozen test selection.

The benchmark's synthetic cue constructor still reads a **public initial
beacon** to generate one correct and four incorrect candidate offsets; that
reference is not passed to the learned model. In particular, the learner may
see each candidate *offset* (a public observation) but cannot compare it to the
true beacon. The navigation policy, the learned motion-update model, cue
vocabulary and the two-context structure remain engineered. Successful
navigation is an imperfect proxy for correct cue selection because the
navigation policy itself occasionally fails.

## Frozen evaluation and matched alternatives

The protocol was committed first; no post-result change to evaluation seeds,
indices, budgets or reported modes. Train/evaluation namespaces are disjoint:

- Six **previously inspected** seeds: development 2749/6607/9901 and additional
  17431/24869/37021 (NOT independently blind).
- Per seed: 360 reward-only target-domain `train` episodes at indices 78000–78359;
  one existing grid-trained motion updater fit on 24 disjoint grid `train` episodes;
  40 `test` episodes at indices 98000–98039.
- Methods: contextual reward-only selector; direct context/source lookup derived
  from precisely the **same reward evidence**; separately trained context-blind
  reward-only selector on the same number of episodes; first/latest/random cue;
  privileged true-beacon oracle for **benchmark comparison only**.
- Every method uses the same deterministic navigation policy and task episodes.
  Only the selector changes. The public beacon used by the cue generator is
  not accessible to either learned selector at inference time.
- Replay of checkpoint evidence recomputes each training action and count and
  rejects contradictory choices or counts even if the caller recomputes SHA-256.
  Checksums are integrity tests, **not authenticated provenance or consent**.

## Result: reward-only grounding works, but is not better than lookup

| Cohort (120 navigation episodes each) | Reward-only | Direct lookup | No context | First | Last | Random | Oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Development (2749/6607/9901) | **107** | **107** | 52 | 25 | 19 | 21 | 107 |
| Additional inspected (17431/24869/37021) | **110** | **110** | 45 | 17 | 29 | 15 | 110 |
| Combined (240 episodes) | **217 (90.4%)** | **217 (90.4%)** | 97 | 42 | 48 | 36 | 217 |

All six individually learned a source mapping consistent with the public
beacon (the oracle score matches), but the equally trained direct lookup
achieved identical outcomes. This task **does not demonstrate a measurable
benefit from the transferred memory controller or a generic alignment
architecture**; the source/context identity correlations are stable and can
be memorized by a small contextual bandit. A source-agnostic, context-blind
ablation drops to 97/240, demonstrating the task depends on the engineered
context label. Six already inspected seeds and one deterministic task family
provide no independent uncertainty bound.

## Reproduce

```sh
python -m unittest tests.test_reward_aliases tests.test_grounded_aliases tests.test_online_memory_gate tests.test_environment_api -v
python -m benchmarks.reward_only_alignment_benchmark --cohort development --out benchmarks/reward_only_alignment_results.json
python -m benchmarks.reward_only_alignment_benchmark --cohort additional --out benchmarks/reward_only_alignment_additional_results.json
python -m benchmarks.transfer_benchmark
```

The local rebuilt checkout passed 47 selected tests including six additional
legacy modules, plus the unchanged transfer benchmark. A full reconstructed
suite run encountered missing historical modules; full repository-wide green
status or CI is **not** claimed.

## Next discriminating D3 test

Freeze a new task family whose correct observation source **changes per
instance**, where simple context/source lookup is insufficient, and where
relations between cues (e.g. consistency over time, predictive agreement with
public feedback) must be learned. Compare a learned conditional mechanism to
target-domain contextual lookup at the **same interaction budget**; do not
promote on a tie. No automatic model promotion, system action authority,
human-origin memory handling or AthenZ/Synveil dependency is introduced.
Versions 2A affective cognition and 2B virtual home remain post-core.
